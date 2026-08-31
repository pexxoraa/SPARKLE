from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sparkle.ai_system_runtime import CandidateRuntimeEvaluator, RuntimeEvaluationStore
from sparkle.ai_system_source import SourceCandidateStore, SourceCandidateWorkspace
from sparkle.external_worker import ExternalWorkerError
from sparkle.trace import TraceStore


class WorkerStub:
    def __init__(self, result=None, error=None):
        self.error = error
        self.calls = 0
        self.result = result or {
            "external_test_run_id": 7, "job_id": "SPK-WRK-" + "A" * 32,
            "status": "passed", "returncode": 0, "timed_out": False,
            "output": "Ran 1 test\nOK\nEXPECTED-MARKER", "duration_ms": 12.5,
            "response_verified": True, "isolation_verified": False,
            "sandbox_claims": {"worker_id": "worker-contract-fixture"},
        }

    def run_directory(
        self, name, workspace, *, approved, timeout_seconds, max_output_chars,
    ):
        self.calls += 1
        if self.error:
            raise self.error
        self.workspace = workspace
        self.name = name
        self.approved = approved
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars
        return dict(self.result)


class RuntimeEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"SPARKLE_DATA_DIR": self.temp.name})
        self.env.start()
        self.candidates = SourceCandidateStore()
        self.workspace = SourceCandidateWorkspace()
        self.traces = TraceStore()
        self.store = RuntimeEvaluationStore()
        self.worker = WorkerStub()
        self.service = CandidateRuntimeEvaluator(
            self.candidates, self.workspace, self.traces, self.store, self.worker,
        )
        self.candidate_id = self._candidate(status="approved")

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def _candidate(self, *, status: str) -> int:
        candidate_id = self.candidates.begin(
            disclosure_id=1, plan_id=9, system_name="runtime_ai",
            plan_sha256="a" * 64,
        )
        _, files, digest = self.workspace.write(
            candidate_id=candidate_id, plan_id=9, plan_sha256="a" * 64,
            files=[{"path": "src/runtime_ai/system.py", "content": "def value():\n    return 42\n"}],
        )
        self.candidates.mark_generated(candidate_id, files=files, candidate_sha256=digest, trace_id="SPK-2026-999999")
        if status in {"reviewed", "approved"}:
            self.candidates.review(candidate_id, decision="accept", notes_sha256="b" * 64)
        if status == "approved":
            self.candidates.record_verification(candidate_id, {"status": "passed", "checks": [], "runtime_tests_executed": False})
            self.candidates.approve(candidate_id, approved=True)
        return candidate_id

    def contract(self, **changes):
        value = {
            "protocol_version": self.service.PROTOCOL,
            "candidate_id": self.candidate_id, "plan_id": 9,
            "requested_capabilities": ["python_runtime"],
            "runtime_requirements": {"language": "python", "framework": "unittest"},
            "input_data": {"case": "value"},
            "expected_behavior": "The candidate returns the declared deterministic value.",
            "execution_limits": {"timeout_seconds": 10, "max_output_chars": 12000},
            "evaluation_criteria": [
                {"name": "tests_pass", "kind": "worker_pass", "value": ""},
                {"name": "marker", "kind": "output_contains", "value": "EXPECTED-MARKER"},
            ],
            "test_files": [{"path": "tests/test_runtime.py", "content": "import unittest\nclass T(unittest.TestCase):\n    def test_value(self): self.assertEqual(42, 42)\n"}],
            "result_format": "SPARKLE-RUNTIME-RESULT/1",
        }
        value.update(changes)
        return value

    def test_success_persists_full_states_trace_and_no_promotion(self):
        result = self.service.request(self.contract(), approved=True)
        self.assertEqual(result["status"], "evaluated")
        self.assertEqual([item["state"] for item in result["lifecycle"]],
                         ["requested", "queued", "submitted", "running", "completed", "evaluated"])
        self.assertTrue(result["runtime_verified"])
        self.assertFalse(result["isolation_verified"])
        self.assertFalse(result["production_verified"])
        self.assertFalse(result["source_promoted"])
        self.assertEqual(self.store.list()[0]["evaluation_id"], result["evaluation_id"])
        trace = next(item for item in self.traces.recent(limit=20) if item["trace_id"] == result["trace_id"])
        self.assertEqual(trace["processing_stage"], "evaluated")
        self.assertFalse(trace["execution_metadata"]["isolation_verified"])
        self.assertTrue((self.worker.workspace / "src/runtime_ai/system.py").is_file())
        self.assertFalse((Path(self.temp.name) / "applications" / "runtime_ai").exists())
        self.assertEqual(self.worker.timeout_seconds, 10)
        self.assertEqual(self.worker.max_output_chars, 12000)

    def test_missing_approval_invalid_candidate_and_plan_fail_before_worker(self):
        with self.assertRaisesRegex(ValueError, "explicit approval"):
            self.service.request(self.contract(), approved=False)
        unapproved = self._candidate(status="reviewed")
        self.assertEqual(
            self.service.request(self.contract(candidate_id=unapproved), approved=True)["status"],
            "rejected",
        )
        self.assertEqual(self.service.request(self.contract(plan_id=10), approved=True)["status"], "rejected")
        self.assertEqual(self.service.request(self.contract(candidate_id=999), approved=True)["status"], "rejected")
        self.assertEqual(self.worker.calls, 0)

    def test_invalid_contract_rejected(self):
        cases = [
            self.contract(runtime_requirements={"language": "shell", "framework": "commands"}),
            self.contract(test_files=[{"path": "../escape.py", "content": "pass\n"}]),
            self.contract(execution_limits={"timeout_seconds": 0, "max_output_chars": 12000}),
        ]
        for contract in cases:
            with self.subTest(contract=contract):
                result = self.service.request(contract, approved=True)
                self.assertEqual(result["status"], "rejected")
                self.assertEqual(
                    [item["state"] for item in result["lifecycle"]],
                    ["requested", "rejected"],
                )

    def test_worker_unavailable_and_protocol_authentication_failures(self):
        for error, expected in [
            (ExternalWorkerError("External worker endpoint is not configured"), "worker_unavailable"),
            (ExternalWorkerError("External worker response signature is invalid"), "protocol_failure"),
            (ExternalWorkerError("External worker replay conflict"), "protocol_failure"),
        ]:
            with self.subTest(expected=expected):
                self.service.worker = WorkerStub(error=error)
                result = self.service.request(self.contract(), approved=True)
                self.assertEqual(result["status"], expected)
                self.assertFalse(result["runtime_verified"])

    def test_timeout_execution_and_evaluation_failures_are_distinct(self):
        cases = [
            ({"status": "failed", "returncode": -9, "timed_out": True}, "timeout"),
            ({"status": "failed", "returncode": 1, "timed_out": False}, "execution_failure"),
            ({"status": "passed", "returncode": 0, "timed_out": False, "output": "OK"}, "evaluation_failure"),
        ]
        for updates, expected in cases:
            with self.subTest(expected=expected):
                base = WorkerStub().result
                base.update(updates)
                self.service.worker = WorkerStub(result=base)
                result = self.service.request(self.contract(), approved=True)
                self.assertEqual(result["status"], expected)
                self.assertFalse(result["runtime_verified"])

    def test_result_evidence_is_content_free_and_bounded(self):
        result = self.service.request(self.contract(), approved=True)
        serialized = json.dumps(result)
        self.assertNotIn("def value", serialized)
        self.assertNotIn("EXPECTED-MARKER", serialized)
        self.assertRegex(result["output_sha256"], r"^[0-9a-f]{64}$")
        self.assertGreater(result["output_chars"], 0)

    def test_candidate_tamper_fails_to_start_without_worker_or_promotion(self):
        candidate_root = Path(self.temp.name) / "candidate_environment" / "source_candidates" / f"candidate-{self.candidate_id:06d}"
        source = candidate_root / "src/runtime_ai/system.py"
        source.chmod(0o600)
        source.unlink()
        outside = Path(self.temp.name) / "outside.py"
        outside.write_text("raise RuntimeError('must not run')\n", encoding="utf-8")
        source.symlink_to(outside)
        result = self.service.request(self.contract(), approved=True)
        self.assertEqual(result["status"], "failed_to_start")
        self.assertEqual(self.worker.calls, 0)
        self.assertFalse(result["runtime_verified"])
        self.assertFalse((Path(self.temp.name) / "applications" / "runtime_ai").exists())


if __name__ == "__main__":
    unittest.main()
