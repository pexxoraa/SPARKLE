from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sparkle.external_worker import ExternalWorkerClient, ExternalWorkerError
from sparkle.secrets import SecretResolver
from sparkle.tooling import ExternalWorkspaceTestTool, ToolError


SIGNING_KEY = "unit-test-worker-signing-key-32-bytes-minimum"
NOW = 1_800_000_000
JOB_ID = "SPK-WRK-0123456789ABCDEF0123456789ABCDEF"


class FakeResponse:
    def __init__(self, body: bytes, headers: dict[str, str], status: int = 200):
        self.body = body
        self.headers = headers
        self.status = status

    def read(self, limit: int = -1) -> bytes:
        return self.body if limit < 0 else self.body[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def getcode(self):
        return self.status


class SignedWorker:
    def __init__(self, mode: str = "ok"):
        self.mode = mode
        self.request = None
        self.timeout = None
        self.request_body = b""

    def __call__(self, request, *, timeout: int):
        self.request = request
        self.timeout = timeout
        self.request_body = request.data
        payload = json.loads(request.data)
        status = "passed"
        returncode = 0
        response_job_id = payload["job_id"]
        timestamp = str(NOW)
        response: dict[str, object] = {
            "protocol_version": ExternalWorkerClient.PROTOCOL,
            "job_id": response_job_id,
            "status": status,
            "returncode": returncode,
            "timed_out": False,
            "output": "test passed\ntoken=worker-output-value",
            "duration_ms": 12.25,
            "sandbox": {
                "worker_id": "fake-container-1",
                "filesystem_isolation": True,
                "network_isolation": True,
                "ephemeral": True,
                "resource_limits": True,
            },
        }
        if self.mode == "stale":
            timestamp = str(NOW - ExternalWorkerClient.MAX_CLOCK_SKEW_SECONDS - 1)
        elif self.mode == "mismatch":
            response["job_id"] = "SPK-WRK-FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
        elif self.mode == "unknown":
            response["unexpected"] = True
        elif self.mode == "inconsistent":
            response["status"] = "failed"
        elif self.mode == "oversized":
            response["output"] = "x" * ExternalWorkerClient.MAX_RESPONSE_BYTES
        body = ExternalWorkerClient._canonical_json(response)
        signature = ExternalWorkerClient._signature(
            SIGNING_KEY.encode(), timestamp, body,
        )
        if self.mode == "bad_signature":
            signature = "sha256=" + "0" * 64
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "X-SPARKLE-Worker-Protocol": "1",
            "X-SPARKLE-Worker-Timestamp": timestamp,
            "X-SPARKLE-Worker-Signature": signature,
        }
        status_code = 200
        if self.mode == "bad_content_type":
            headers["Content-Type"] = "text/plain"
        elif self.mode == "missing_protocol":
            headers.pop("X-SPARKLE-Worker-Protocol")
        elif self.mode == "bad_status_code":
            status_code = 202
        return FakeResponse(body, headers, status_code)


class ExternalWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run_db_index = 0
        self.apps = self.root / "applications"
        project = self.apps / "worker_app"
        (project / "tests").mkdir(parents=True)
        (project / "tests/test_ready.py").write_text(
            "import unittest\n\nclass Ready(unittest.TestCase):\n"
            "    def test_ready(self): self.assertTrue(True)\n",
            encoding="utf-8",
        )
        (project / "main.py").write_text("READY = True\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def client(self, worker=None, **overrides):
        options = {
            "enabled": True,
            "endpoint": "https://worker.example/v1/jobs",
            "secret_resolver": SecretResolver({"SPARKLE_WORKER_SIGNING_KEY": SIGNING_KEY}),
            "opener": worker or SignedWorker(),
            "clock": lambda: NOW,
            "job_id_factory": lambda: JOB_ID,
        }
        options.update(overrides)
        database = self.root / f"runs-{self.run_db_index}.sqlite3"
        self.run_db_index += 1
        return ExternalWorkerClient(
            self.apps, database,
            **options,
        )

    def test_signed_request_response_persistence_and_non_verified_claims(self):
        worker = SignedWorker()
        client = self.client(worker)
        result = client.run("worker_app")
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["response_verified"])
        self.assertFalse(result["isolation_verified"])
        self.assertTrue(result["sandbox_claims"]["network_isolation"])
        self.assertIn("[REDACTED]", result["output"])
        self.assertNotIn("worker-output-value", result["output"])
        self.assertEqual(worker.timeout, 15)

        request_headers = {name.lower(): value for name, value in worker.request.header_items()}
        request_timestamp = request_headers["x-sparkle-worker-timestamp"]
        self.assertEqual(
            request_headers["x-sparkle-worker-signature"],
            ExternalWorkerClient._signature(
                SIGNING_KEY.encode(), request_timestamp, worker.request_body,
            ),
        )
        payload = json.loads(worker.request_body)
        self.assertEqual(payload["operation"], "python_unittest")
        self.assertTrue(payload["limits"]["requested_network_isolation"])
        self.assertEqual([item["path"] for item in payload["files"]], [
            "main.py", "tests/test_ready.py",
        ])
        self.assertNotIn(SIGNING_KEY.encode(), worker.request_body)

        persisted = client.list()[0]
        self.assertTrue(persisted["response_verified"])
        self.assertFalse(persisted["isolation_verified"])
        serialized = json.dumps({"status": client.status(), "runs": client.list()})
        self.assertNotIn(SIGNING_KEY, serialized)
        self.assertNotIn("worker.example", serialized)
        self.assertNotIn("READY = True", serialized)

    def test_disabled_invalid_url_missing_or_short_key_fail_before_transport(self):
        cases = [
            ({"enabled": False}, "disabled"),
            ({"endpoint": "http://worker.example/jobs"}, "must be HTTPS"),
            ({"endpoint": "https://user:pass@worker.example/jobs"}, "must be HTTPS"),
            ({"secret_resolver": SecretResolver({})}, "not configured"),
            ({"secret_resolver": SecretResolver({"SPARKLE_WORKER_SIGNING_KEY": "short"})}, "32 bytes"),
        ]
        for overrides, message in cases:
            with self.subTest(overrides=overrides):
                worker = SignedWorker()
                client = self.client(worker, **overrides)
                with self.assertRaisesRegex(ExternalWorkerError, message):
                    client.run("worker_app")
                self.assertIsNone(worker.request)

    def test_source_bundle_rejects_symlink_sensitive_binary_and_oversized_files(self):
        outside = self.root / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        invalid_files = [
            ("link.txt", lambda path: path.symlink_to(outside)),
            (".env", lambda path: path.write_text("SECRET=value", encoding="utf-8")),
            ("private.pem", lambda path: path.write_text("key", encoding="utf-8")),
            ("app_secrets.json", lambda path: path.write_text("{}", encoding="utf-8")),
            ("binary.bin", lambda path: path.write_bytes(b"\xff\xfe")),
            (
                "large.txt",
                lambda path: path.write_bytes(b"x" * (ExternalWorkerClient.MAX_FILE_BYTES + 1)),
            ),
        ]
        for index, (name, create) in enumerate(invalid_files):
            with self.subTest(name=name):
                project_name = f"invalid_{index}"
                project = self.apps / project_name
                (project / "tests").mkdir(parents=True)
                (project / "tests/test_ready.py").write_text("pass\n", encoding="utf-8")
                create(project / name)
                with self.assertRaisesRegex(ValueError, "reject|UTF-8|exceeds"):
                    self.client().run(project_name)

    def test_source_bundle_rejects_the_configured_signing_key_value(self):
        project = self.apps / "key_leak"
        (project / "tests").mkdir(parents=True)
        (project / "tests/test_ready.py").write_text("pass\n", encoding="utf-8")
        (project / "leak.txt").write_text(SIGNING_KEY, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "configured secret value"):
            self.client().run("key_leak")

    def test_rejects_untrusted_response_variants_and_records_safe_error(self):
        for mode in (
            "bad_signature", "stale", "mismatch", "unknown", "inconsistent", "oversized",
            "bad_content_type", "missing_protocol", "bad_status_code",
        ):
            with self.subTest(mode=mode):
                client = self.client(SignedWorker(mode))
                with self.assertRaises(ExternalWorkerError):
                    client.run("worker_app")
                recorded = client.list()[0]
                self.assertEqual(recorded["status"], "error")
                self.assertFalse(recorded["response_verified"])
                self.assertEqual(recorded["output"], "")
                self.assertEqual(recorded["sandbox_claims"], {})
                self.assertEqual(recorded["error_type"], "ExternalWorkerError")

    def test_transport_errors_are_wrapped_without_endpoint_or_secret(self):
        def broken(_request, *, timeout):
            raise OSError(f"failed https://worker.example?key={SIGNING_KEY} after {timeout}")

        client = self.client(broken)
        with self.assertRaises(ExternalWorkerError) as caught:
            client.run("worker_app")
        message = str(caught.exception)
        self.assertNotIn(SIGNING_KEY, message)
        self.assertNotIn("worker.example", message)
        self.assertIn("OSError", message)
        self.assertEqual(client.list()[0]["error_type"], "OSError")

    def test_operator_tool_requires_approval_and_rejects_extra_fields(self):
        client = self.client()
        tool = ExternalWorkspaceTestTool(client)
        with self.assertRaisesRegex(ToolError, "explicit approval"):
            tool.run({"project_name": "worker_app"})
        with self.assertRaisesRegex(ToolError, "Unsupported"):
            tool.run({
                "project_name": "worker_app", "approved": True, "command": "rm -rf /",
            })
        self.assertEqual(
            tool.run({"project_name": "worker_app", "approved": True})["status"],
            "passed",
        )


if __name__ == "__main__":
    unittest.main()
