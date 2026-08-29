from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

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

    def test_signing_key_file_requires_private_regular_file(self):
        key_file = self.root / "worker.key"
        key_file.write_bytes(SIGNING_KEY)
        key_file.chmod(0o600)
        config = self.config(signing_key_file=key_file)
        self.assertEqual(resolve_worker_signing_key(config), SIGNING_KEY)
        key_file.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "permissions"):
            resolve_worker_signing_key(config)
        key_file.chmod(0o600)
        link = self.root / "link.key"
        link.symlink_to(key_file)
        with self.assertRaises(SecretNotFoundError):
            resolve_worker_signing_key(self.config(signing_key_file=link))

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

        def successful(command, **_kwargs):
            captured.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

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
        self.assertNotIn(SIGNING_KEY.decode(), " ".join(command))

    def test_real_bubblewrap_preflight_is_honest_and_fail_closed(self):
        executor = BubblewrapExecutor()
        status = executor.status()
        self.assertEqual(status["filesystem_isolation"], status["available"])
        self.assertEqual(status["network_isolation"], status["available"])
        self.assertEqual(status["preflight_passed"], status["available"])
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
        pyproject = (project / "pyproject.toml").read_text()
        combined = dockerfile + compose + unit
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
        self.assertNotIn(SIGNING_KEY.decode(), combined)


if __name__ == "__main__":
    unittest.main()
