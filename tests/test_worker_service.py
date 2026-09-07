from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sparkle.external_worker import ExternalWorkerClient
from sparkle.secrets import SecretNotFoundError, SecretResolver
from sparkle.worker_executor import (
    BubblewrapExecutor,
    ExecutorResult,
    FixedUnittestExecutor,
    WorkerJob,
    WorkerSourceFile,
)
from sparkle.worker_service import (
    ExternalWorkerService,
    WorkerAuthenticationError,
    WorkerConfig,
    WorkerConflictError,
    WorkerPayloadError,
    WorkerRequestValidator,
    WorkerServiceError,
    WorkerUnavailableError,
    build_server,
    resolve_worker_signing_key,
)
from sparkle.worker_diagnostics import AVAILABLE, WorkerIsolationDiagnostic


SIGNING_KEY = b"unit-test-worker-signing-key-32-bytes-minimum"
NOW = 1_800_000_000
JOB_ID = "SPK-WRK-0123456789ABCDEF0123456789ABCDEF"


def source(path: str, content: bytes) -> dict[str, str]:
    return {
        "path": path,
        "sha256": hashlib.sha256(content).hexdigest(),
        "content_base64": base64.b64encode(content).decode("ascii"),
    }


def request_value(*, job_id: str = JOB_ID) -> dict[str, object]:
    return {
        "protocol_version": ExternalWorkerClient.PROTOCOL,
        "job_id": job_id,
        "operation": ExternalWorkerClient.OPERATION,
        "project_name": "worker_app",
        "limits": {
            "timeout_seconds": 5,
            "max_output_chars": 12_000,
            "requested_network_isolation": True,
            "requested_filesystem_isolation": True,
            "requested_ephemeral": True,
        },
        "files": [
            source("main.py", b"def add(a, b): return a + b\n"),
            source(
                "tests/test_main.py",
                b"import unittest\nfrom main import add\n"
                b"class Ready(unittest.TestCase):\n"
                b"    def test_add(self): self.assertEqual(add(2, 3), 5)\n",
            ),
        ],
    }


def signed(value: dict[str, object]) -> tuple[dict[str, str], bytes]:
    body = ExternalWorkerClient._canonical_json(value)
    timestamp = str(NOW)
    return ({
        "Content-Type": "application/json",
        "X-SPARKLE-Worker-Protocol": "1",
        "X-SPARKLE-Worker-Timestamp": timestamp,
        "X-SPARKLE-Worker-Signature": ExternalWorkerClient._signature(
            SIGNING_KEY, timestamp, body,
        ),
    }, body)


class FakeExecutor:
    def __init__(self, *, available: bool = True, output: str = "2 tests passed"):
        self.available = available
        self.output = output
        self.calls = 0

    def status(self):
        return {
            "mode": "fake",
            "available": self.available,
            "preflight_passed": self.available,
            "filesystem_isolation": self.available,
            "network_isolation": self.available,
            "ephemeral_workspace": True,
            "resource_limits": True,
            "unsafe_process_mode": False,
            "failure_type": None if self.available else "IsolationUnavailable",
        }

    def execute(self, job: WorkerJob, *, worker_id: str):
        self.calls += 1
        return ExecutorResult(
            status="passed",
            returncode=0,
            timed_out=False,
            output=self.output,
            duration_ms=4.5,
            sandbox={
                "worker_id": worker_id,
                "filesystem_isolation": True,
                "network_isolation": True,
                "ephemeral": True,
                "resource_limits": True,
            },
        )


class ServiceResponse:
    def __init__(self, response):
        self.body = response.body
        self.headers = response.headers
        self.status = response.status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit: int = -1):
        return self.body if limit < 0 else self.body[:limit]

    def getcode(self):
        return self.status


class WorkerServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def config(self, **overrides):
        values = {
            "host": "127.0.0.1",
            "port": 8770,
            "worker_id": "test-worker",
            "state_dir": self.root / "worker-state",
            "executor_mode": "process",
            "allow_unsafe_process_executor": True,
        }
        values.update(overrides)
        return WorkerConfig(**values)

    def service(self, executor=None, **config_overrides):
        return ExternalWorkerService(
            self.config(**config_overrides),
            signing_key=SIGNING_KEY,
            executor=executor or FakeExecutor(),
            clock=lambda: NOW,
        )

    def test_config_is_bounded_and_non_loopback_requires_secure_transport(self):
        with self.assertRaisesRegex(ValueError, "direct TLS or trusted"):
            WorkerConfig(host="0.0.0.0").validate()
        WorkerConfig(host="0.0.0.0", trusted_tls_termination=True).validate()
        WorkerConfig(
            host="0.0.0.0",
            tls_certificate_file=Path("cert.pem"),
            tls_private_key_file=Path("key.pem"),
        ).validate()
        with self.assertRaisesRegex(ValueError, "requires"):
            WorkerConfig(executor_mode="process").validate()
        with self.assertRaisesRegex(ValueError, "SPARKLE_WORKER_PORT"):
            WorkerConfig.load({"SPARKLE_WORKER_PORT": "not-an-integer"})
        loaded = WorkerConfig.load({
            "CREDENTIALS_DIRECTORY": str(self.root / "credentials"),
            "SPARKLE_WORKER_SIGNING_KEY_FILE": str(
                self.root / "credentials/sparkle-worker-signing-key"
            ),
        })
        self.assertEqual(loaded.credentials_directory, self.root / "credentials")

    def test_host_diagnostic_is_credential_free_and_never_claims_level3(self):
        class ReadyBubblewrap:
            def status(self):
                return {
                    "available": True,
                    "filesystem_isolation": True,
                    "network_isolation": True,
                    "failure_type": None,
                    "canaries": {
                        name: True for name in FixedUnittestExecutor.CANARY_NAMES
                    },
                }

        def runner(command, **_kwargs):
            return subprocess.CompletedProcess(command, 0, "available\n", "")

        diagnostic = WorkerIsolationDiagnostic(
            runner=runner,
            executable_finder=lambda name: f"/usr/bin/{name}",
            bubblewrap_factory=ReadyBubblewrap,
        ).run()
        self.assertEqual(diagnostic["schema"], "SPARKLE-WORKER-HOST-DIAGNOSTIC/1")
        self.assertTrue(diagnostic["isolation_preflight_passed"])
        self.assertEqual(diagnostic["checks"]["user_namespace"]["state"], AVAILABLE)
        self.assertEqual(diagnostic["checks"]["mount_namespace"]["state"], AVAILABLE)
        self.assertEqual(diagnostic["checks"]["network_namespace"]["state"], AVAILABLE)
        self.assertEqual(diagnostic["checks"]["no_new_privileges"]["state"], AVAILABLE)
        self.assertEqual(diagnostic["level_3_status"], "BLOCKED")
        self.assertFalse(diagnostic["level_3_verified"])
        self.assertFalse(diagnostic["deployment_started"])

        project = Path(__file__).resolve().parents[1]
        secret = "diagnostic-must-not-print-this-secret"
        completed = subprocess.run(
            [sys.executable, "-m", "sparkle.worker_service", "--diagnose"],
            cwd=project,
            env={
                "PYTHONPATH": str(project / "src"),
                "SPARKLE_WORKER_SIGNING_KEY": secret,
            },
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        observed = json.loads(completed.stdout)
        self.assertFalse(observed["level_3_verified"])
        self.assertNotIn(secret, completed.stdout + completed.stderr)

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL is required")
    def test_development_tls_bootstrap_validates_certificate_and_hostname(self):
        project = Path(__file__).resolve().parents[1]
        script = project / "worker_environment/bootstrap-local-worker.sh"
        destination = self.root / "local-worker"
        completed = subprocess.run(
            [str(script), str(destination)],
            cwd=project,
            env={"PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("NON-ISOLATED", completed.stdout)
        self.assertIn("Level 3 remains BLOCKED", completed.stdout)
        key_file = destination / "worker-signing-key"
        certificate = destination / "tls/server.crt"
        private_key = destination / "tls/server.key"
        self.assertEqual(key_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(private_key.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(key_file.read_bytes().hex(), completed.stdout)

        values = {}
        for line in (destination / "worker.env").read_text(encoding="utf-8").splitlines():
            name, value = line.split("=", 1)
            values[name] = value
        config = WorkerConfig.load(values)
        config = WorkerConfig(**{
            name: getattr(config, name)
            for name in WorkerConfig.__dataclass_fields__
            if name != "port"
        }, port=0)
        service = ExternalWorkerService(config, executor=FakeExecutor())
        server = build_server(service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        try:
            trusted = ssl.create_default_context(cafile=str(certificate))
            with urllib.request.urlopen(
                f"https://localhost:{port}/health", context=trusted, timeout=5,
            ) as response:
                self.assertTrue(json.loads(response.read())["ok"])
            with self.assertRaises(urllib.error.URLError):
                urllib.request.urlopen(f"https://localhost:{port}/health", timeout=5)
            raw_socket = socket.create_connection(("127.0.0.1", port), timeout=5)
            try:
                wrong_hostname = ssl.create_default_context(cafile=str(certificate))
                with self.assertRaises(ssl.SSLCertVerificationError):
                    wrong_hostname.wrap_socket(
                        raw_socket, server_hostname="wrong.invalid",
                    )
            finally:
                raw_socket.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        refused = subprocess.run(
            [str(script), str(destination)],
            cwd=project,
            env={"PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("Refusing to overwrite", refused.stderr)

    def test_signing_key_file_requires_private_regular_file(self):
        key_file = self.root / "worker.key"
        key_file.write_bytes(SIGNING_KEY)
        key_file.chmod(0o600)
        config = self.config(signing_key_file=key_file)
        self.assertEqual(resolve_worker_signing_key(config), SIGNING_KEY)
        for exposed_mode in (0o640, 0o604):
            key_file.chmod(exposed_mode)
            with self.assertRaisesRegex(ValueError, "permissions"):
                resolve_worker_signing_key(config)
        key_file.chmod(0o600)
        link = self.root / "link.key"
        link.symlink_to(key_file)
        with self.assertRaises(SecretNotFoundError):
            resolve_worker_signing_key(self.config(signing_key_file=link))
        loaded = WorkerConfig.load({
            "SPARKLE_WORKER_SIGNING_KEY_FILE": str(link),
            "SPARKLE_WORKER_EXECUTOR": "process",
            "SPARKLE_WORKER_ALLOW_UNSAFE_PROCESS_EXECUTOR": "true",
        })
        self.assertEqual(loaded.signing_key_file, link)
        with self.assertRaises(SecretNotFoundError):
            resolve_worker_signing_key(loaded)
        key_file.write_bytes(b"too-short")
        with self.assertRaisesRegex(ValueError, "32-4096"):
            resolve_worker_signing_key(config)
        with self.assertRaises(SecretNotFoundError):
            resolve_worker_signing_key(
                self.config(signing_key_file=self.root / "missing.key")
            )

    def test_systemd_projected_signing_key_requires_exact_trusted_contract(self):
        credentials = self.root / "credentials"
        credentials.mkdir(mode=0o700)
        projected = credentials / "sparkle-worker-signing-key"
        projected.write_bytes(SIGNING_KEY)
        projected.chmod(0o440)
        config = self.config(
            signing_key_file=projected,
            credentials_directory=credentials,
        )
        real_fstat = os.fstat

        def root_owned_metadata(descriptor):
            metadata = real_fstat(descriptor)
            return SimpleNamespace(
                st_mode=metadata.st_mode,
                st_uid=0,
                st_gid=0,
                st_size=metadata.st_size,
            )

        with patch(
            "sparkle.worker_service.os.fstat",
            side_effect=root_owned_metadata,
        ):
            self.assertEqual(resolve_worker_signing_key(config), SIGNING_KEY)

            for invalid_mode in (0o400, 0o444, 0o640):
                projected.chmod(invalid_mode)
                with self.assertRaisesRegex(
                    ValueError, "root-owned with mode 0440",
                ):
                    resolve_worker_signing_key(config)
            projected.chmod(0o440)

        fstat_calls = 0

        def wrong_file_owner_metadata(descriptor):
            nonlocal fstat_calls
            fstat_calls += 1
            metadata = real_fstat(descriptor)
            return SimpleNamespace(
                st_mode=metadata.st_mode,
                st_uid=0 if fstat_calls == 1 else 1_000,
                st_gid=0,
                st_size=metadata.st_size,
            )

        with patch(
            "sparkle.worker_service.os.fstat",
            side_effect=wrong_file_owner_metadata,
        ), self.assertRaisesRegex(ValueError, "root-owned with mode 0440"):
            resolve_worker_signing_key(config)

        wrong_name = credentials / "caller-selected-key"
        wrong_name.write_bytes(SIGNING_KEY)
        wrong_name.chmod(0o440)
        with self.assertRaisesRegex(ValueError, "permissions"):
            resolve_worker_signing_key(self.config(
                signing_key_file=wrong_name,
                credentials_directory=credentials,
            ))

        def untrusted_directory_metadata(descriptor):
            metadata = real_fstat(descriptor)
            return SimpleNamespace(
                st_mode=metadata.st_mode,
                st_uid=1_000,
                st_gid=1_000,
                st_size=metadata.st_size,
            )

        with patch(
            "sparkle.worker_service.os.fstat",
            side_effect=untrusted_directory_metadata,
        ), self.assertRaisesRegex(ValueError, "directory is not trusted"):
            resolve_worker_signing_key(config)

        projected.unlink()
        source_key = self.root / "source.key"
        source_key.write_bytes(SIGNING_KEY)
        source_key.chmod(0o600)
        projected.symlink_to(source_key)
        with patch(
            "sparkle.worker_service.os.fstat",
            side_effect=root_owned_metadata,
        ), self.assertRaises(SecretNotFoundError):
            resolve_worker_signing_key(config)

    def test_validator_authenticates_and_materializes_exact_schema(self):
        headers, body = signed(request_value())
        job = WorkerRequestValidator(SIGNING_KEY, clock=lambda: NOW).validate(
            headers, body,
        )
        self.assertEqual(job.job_id, JOB_ID)
        self.assertEqual([item.path for item in job.files], [
            "main.py", "tests/test_main.py",
        ])
        self.assertEqual(job.request_hash, hashlib.sha256(body).hexdigest())

    def test_validator_rejects_authentication_failures(self):
        headers, body = signed(request_value())
        for changed in (
            {**headers, "X-SPARKLE-Worker-Signature": "sha256=" + "0" * 64},
            {**headers, "X-SPARKLE-Worker-Timestamp": str(NOW - 301)},
            {key: value for key, value in headers.items() if "Protocol" not in key},
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(WorkerAuthenticationError):
                    WorkerRequestValidator(SIGNING_KEY, clock=lambda: NOW).validate(
                        changed, body,
                    )

    def test_validator_rejects_schema_digest_paths_limits_and_secret(self):
        invalid_values: list[dict[str, object]] = []
        value = request_value()
        value["unexpected"] = True
        invalid_values.append(value)
        value = request_value()
        value["limits"]["requested_network_isolation"] = False  # type: ignore[index]
        invalid_values.append(value)
        value = request_value()
        value["files"][0]["path"] = "../main.py"  # type: ignore[index]
        invalid_values.append(value)
        value = request_value()
        value["files"][0]["sha256"] = "0" * 64  # type: ignore[index]
        invalid_values.append(value)
        value = request_value()
        value["files"][0] = source("main.py", SIGNING_KEY)  # type: ignore[index]
        invalid_values.append(value)
        for value in invalid_values:
            with self.subTest(value=value):
                headers, body = signed(value)
                with self.assertRaises(WorkerServiceError):
                    WorkerRequestValidator(SIGNING_KEY, clock=lambda: NOW).validate(
                        headers, body,
                    )
        headers, _body = signed(request_value())
        with self.assertRaises(WorkerPayloadError):
            WorkerRequestValidator(
                SIGNING_KEY, max_body_bytes=20, clock=lambda: NOW,
            ).validate(headers, b"x" * 21)

    def test_service_signs_response_redacts_secret_and_replays_idempotently(self):
        executor = FakeExecutor(output=f"result key={SIGNING_KEY.decode()}")
        service = self.service(executor)
        headers, body = signed(request_value())
        first = service.handle_job(headers, body)
        second = service.handle_job(headers, body)
        self.assertEqual(first.body, second.body)
        self.assertEqual(executor.calls, 1)
        self.assertNotIn(SIGNING_KEY, first.body)
        self.assertIn(b"[REDACTED]", first.body)
        response_timestamp = first.headers["X-SPARKLE-Worker-Timestamp"]
        self.assertEqual(
            first.headers["X-SPARKLE-Worker-Signature"],
            ExternalWorkerClient._signature(
                SIGNING_KEY, response_timestamp, first.body,
            ),
        )

    def test_replay_conflict_unavailable_executor_and_capacity_fail_closed(self):
        executor = FakeExecutor()
        service = self.service(executor)
        headers, body = signed(request_value())
        service.handle_job(headers, body)
        changed = request_value()
        changed["project_name"] = "changed_app"
        changed_headers, changed_body = signed(changed)
        with self.assertRaises(WorkerConflictError):
            service.handle_job(changed_headers, changed_body)

        unavailable = self.service(FakeExecutor(available=False))
        other_headers, other_body = signed(request_value(
            job_id="SPK-WRK-FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
        ))
        with self.assertRaises(WorkerUnavailableError):
            unavailable.handle_job(other_headers, other_body)
        unavailable.executor.available = True
        self.assertEqual(unavailable.handle_job(other_headers, other_body).status, 200)

        self.assertTrue(service.capacity.acquire(blocking=False))
        try:
            with self.assertRaises(WorkerUnavailableError):
                service.handle_job(headers, body)
        finally:
            service.capacity.release()

    def test_process_executor_runs_importing_tests_and_reports_no_isolation(self):
        headers, body = signed(request_value())
        job = WorkerRequestValidator(SIGNING_KEY, clock=lambda: NOW).validate(
            headers, body,
        )
        executor = FixedUnittestExecutor(allow_unsafe_process=True)
        result = executor.execute(job, worker_id="process-test")
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(result.sandbox["filesystem_isolation"])
        self.assertFalse(result.sandbox["network_isolation"])
        self.assertTrue(result.sandbox["ephemeral"])

    def test_process_executor_timeout_is_bounded(self):
        content = (
            b"import time, unittest\n"
            b"class Slow(unittest.TestCase):\n"
            b"    def test_slow(self): time.sleep(10)\n"
        )
        item = WorkerSourceFile(
            "tests/test_slow.py", content, hashlib.sha256(content).hexdigest(),
        )
        job = WorkerJob(
            JOB_ID, "worker_app", 1, 12_000, (item,), "0" * 64,
        )
        started = time.monotonic()
        result = FixedUnittestExecutor(allow_unsafe_process=True).execute(
            job, worker_id="timeout-test",
        )
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(result.status, "failed")
        self.assertTrue(result.timed_out)

    def test_bubblewrap_command_and_preflight_require_all_isolation_controls(self):
        captured: list[list[str]] = []

        def successful(command, **kwargs):
            captured.append(command)
            self.assertEqual(kwargs["env"], {
                "PATH": str(Path(command[0]).parent),
            })
            probe_index = command.index("-c") + 1
            probe = command[probe_index]
            host_canary = Path(command[probe_index + 1])
            allowed = set(command[probe_index + 3].split(","))
            self.assertTrue(host_canary.is_file())
            self.assertIn("host_root_canary = '/proc/1/root' + host_canary", probe)
            self.assertIn("not os.path.exists(host_canary)", probe)
            self.assertIn("not os.path.exists(host_root_canary)", probe)
            self.assertIn("for path in (host_canary, host_root_canary)", probe)
            self.assertNotIn("/escape-canary", probe)
            self.assertIn("sandbox_writable_area", probe)
            self.assertIn("set(os.environ) == allowed", probe)
            self.assertIn("os.environ.get('PWD') == '/workspace'", probe)
            self.assertEqual(allowed, {
                "PATH", "LANG", "LC_ALL", "PYTHONHASHSEED",
                "PYTHONDONTWRITEBYTECODE", "SPARKLE_TEST_SANDBOX", "PWD",
            })
            evidence = {
                name: True for name in FixedUnittestExecutor.CANARY_NAMES
            }
            return subprocess.CompletedProcess(
                command, 0, json.dumps(evidence), "",
            )

        # This test exercises command construction, not host dependency discovery.
        # The injected runner never executes the inert existing binary.
        executor = BubblewrapExecutor(
            bubblewrap_binary="/usr/bin/true",
            preflight_runner=successful,
        )
        status = executor.status()
        self.assertTrue(status["available"])
        command = captured[0]
        self.assertIn("--unshare-all", command)
        self.assertIn("--clearenv", command)
        self.assertNotIn("--share-net", command)
        self.assertIn("--ro-bind", command)
        self.assertTrue(any(
            command[index] == "--ro-bind" and command[index + 2] == "/workspace"
            for index in range(len(command) - 2)
        ))
        self.assertNotIn(SIGNING_KEY.decode(), " ".join(command))
        self.assertNotIn("UNRELATED_HOST_SECRET", " ".join(command))
        self.assertEqual(
            set(status["canaries"]), set(FixedUnittestExecutor.CANARY_NAMES),
        )
        self.assertTrue(all(status["canaries"].values()))

    def test_real_bubblewrap_preflight_is_honest_and_fail_closed(self):
        executor = BubblewrapExecutor()
        status = executor.status()
        self.assertEqual(status["filesystem_isolation"], status["available"])
        self.assertEqual(status["network_isolation"], status["available"])
        self.assertEqual(status["preflight_passed"], status["available"])
        if status["available"]:
            self.assertTrue(all(status["canaries"].values()))
        if not status["available"]:
            self.assertIsNotNone(status["failure_type"])
            content = b"import unittest\nclass T(unittest.TestCase): pass\n"
            job = WorkerJob(
                JOB_ID, "worker_app", 1, 1000,
                (WorkerSourceFile(
                    "tests/test_ready.py", content, hashlib.sha256(content).hexdigest(),
                ),),
                "0" * 64,
            )
            with self.assertRaisesRegex(Exception, "isolation is unavailable"):
                executor.execute(job, worker_id="blocked-worker")

    def test_bubblewrap_preflight_rejects_ambiguous_canary_evidence(self):
        def ambiguous(command, **_kwargs):
            return subprocess.CompletedProcess(command, 0, "{}", "")

        executor = BubblewrapExecutor(
            bubblewrap_binary="/usr/bin/true", preflight_runner=ambiguous,
        )
        status = executor.status()
        self.assertFalse(status["available"])
        self.assertFalse(status["hostile_canaries_passed"])
        self.assertEqual(status["failure_type"], "IsolationPreflightFailed")
        self.assertFalse(any(status["canaries"].values()))

    def test_client_to_service_to_real_executor_end_to_end(self):
        applications = self.root / "applications"
        project = applications / "worker_app"
        (project / "tests").mkdir(parents=True)
        (project / "main.py").write_text(
            "def add(a, b): return a + b\n", encoding="utf-8",
        )
        (project / "tests/test_main.py").write_text(
            "import unittest\nfrom main import add\n"
            "class Ready(unittest.TestCase):\n"
            "    def test_add(self): self.assertEqual(add(20, 22), 42)\n",
            encoding="utf-8",
        )
        service = self.service(
            FixedUnittestExecutor(allow_unsafe_process=True),
        )

        def opener(request, *, timeout):
            self.assertEqual(timeout, 15)
            response = service.handle_job(dict(request.header_items()), request.data)
            return ServiceResponse(response)

        client = ExternalWorkerClient(
            applications,
            self.root / "client-runs.sqlite3",
            enabled=True,
            endpoint="https://worker.example/v1/jobs",
            secret_resolver=SecretResolver({
                "SPARKLE_WORKER_SIGNING_KEY": SIGNING_KEY.decode(),
            }),
            opener=opener,
            clock=lambda: NOW,
            job_id_factory=lambda: JOB_ID,
        )
        result = client.run("worker_app")
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["response_verified"])
        self.assertFalse(result["isolation_verified"])
        self.assertFalse(result["sandbox_claims"]["filesystem_isolation"])
        self.assertIn("OK", result["output"])

    def test_loopback_http_health_job_and_unknown_route(self):
        service = self.service(FakeExecutor(), port=0)
        server = build_server(service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urllib.request.urlopen(base + "/health", timeout=5) as response:
                health = json.loads(response.read())
            self.assertTrue(health["ok"])
            headers, body = signed(request_value())
            request = urllib.request.Request(
                base + "/v1/jobs", data=body, headers=headers, method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                response_body = response.read()
                self.assertEqual(response.status, 200)
                timestamp = response.headers["X-SPARKLE-Worker-Timestamp"]
                self.assertEqual(
                    response.headers["X-SPARKLE-Worker-Signature"],
                    ExternalWorkerClient._signature(
                        SIGNING_KEY, timestamp, response_body,
                    ),
                )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(base + "/unknown", timeout=5)
            self.assertEqual(caught.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_status_and_error_surfaces_do_not_expose_credentials(self):
        executor = FakeExecutor(available=False, output=SIGNING_KEY.decode())
        service = self.service(executor)
        serialized = json.dumps(service.status())
        self.assertNotIn(SIGNING_KEY.decode(), serialized)
        self.assertNotIn(str(service.config.state_dir), serialized)
        self.assertFalse(service.status()["ready"])
        self.assertFalse(service.status()["credentials_exposed"])

    def test_deployment_assets_preserve_worker_security_boundaries(self):
        project = Path(__file__).resolve().parents[1]
        dockerfile = (project / "worker_environment/Dockerfile").read_text()
        compose = (project / "worker_environment/compose.yaml").read_text()
        unit = (project / "worker_environment/sparkle-worker.service").read_text()
        installer = (
            project / "worker_environment/install-systemd-worker.sh"
        ).read_text()
        local_bootstrap = (
            project / "worker_environment/bootstrap-local-worker.sh"
        ).read_text()
        worker_config = (
            project / "worker_environment/worker.conf.example"
        ).read_text()
        pyproject = (project / "pyproject.toml").read_text()
        combined = dockerfile + compose + unit + installer + local_bootstrap + worker_config
        self.assertIn('sparkle-worker = "sparkle.worker_service:entrypoint"', pyproject)
        self.assertIn("USER 10001:10001", dockerfile)
        self.assertIn('ENTRYPOINT ["python3", "-m", "sparkle.worker_service"]', dockerfile)
        self.assertIn("SPARKLE_WORKER_EXECUTOR=bubblewrap", dockerfile)
        self.assertIn("read_only: true", compose)
        self.assertIn('cap_drop: ["ALL"]', compose)
        self.assertIn('security_opt: ["no-new-privileges:true"]', compose)
        self.assertIn("internal: true", compose)
        self.assertNotIn("privileged:", compose)
        self.assertIn("NoNewPrivileges=yes", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn(
            "LoadCredential=sparkle-worker-signing-key:/etc/sparkle/worker-signing-key",
            unit,
        )
        self.assertIn(
            "SPARKLE_WORKER_SIGNING_KEY_FILE=%d/sparkle-worker-signing-key",
            unit,
        )
        self.assertNotIn("SPARKLE_WORKER_SIGNING_KEY=", unit)
        self.assertIn("pip install --no-deps", installer)
        self.assertIn("installed but not started", installer)
        self.assertIn("SPARKLE_WORKER_EXECUTOR=bubblewrap", worker_config)
        self.assertIn("SPARKLE_WORKER_EXECUTOR=process", local_bootstrap)
        self.assertIn("Refusing to overwrite", local_bootstrap)
        self.assertNotIn(SIGNING_KEY.decode(), combined)
        for script in (installer, local_bootstrap):
            checked = subprocess.run(
                ["sh", "-n"], input=script, capture_output=True, text=True,
                timeout=5, check=False,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)
        ci = (project / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        acceptance_workflow = (
            project / ".github/workflows/level3-worker-acceptance.yml"
        ).read_text(encoding="utf-8")
        acceptance_probe = (
            project / "worker_environment/level3_acceptance.py"
        ).read_text(encoding="utf-8")
        self.assertIn("controlled-execution-software", ci)
        self.assertIn("workflow_dispatch", acceptance_workflow)
        self.assertNotIn("push:", acceptance_workflow)
        self.assertIn("secrets.SPARKLE_WORKER_SIGNING_KEY", acceptance_workflow)
        self.assertIn('"level_3_complete": False', acceptance_probe)
        self.assertIn('"requires_approved_artifact_followup": True', acceptance_probe)
        self.assertNotIn(SIGNING_KEY.decode(), acceptance_workflow + acceptance_probe)
        blocked = subprocess.run(
            [sys.executable, str(project / "worker_environment/level3_acceptance.py")],
            cwd=project,
            env={"PYTHONPATH": str(project / "src")},
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(blocked.returncode, 1)
        self.assertNotIn("Traceback", blocked.stderr + blocked.stdout)
        self.assertFalse(json.loads(blocked.stdout)["isolation_verified"])


if __name__ == "__main__":
    unittest.main()
