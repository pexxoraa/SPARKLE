from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from sparkle.ai_system_execution import ControlledExecutionStore
from sparkle.controlled_execution_cancel import CancellableControlledExecutionService
from sparkle.external_worker import ExternalWorkerClient
from sparkle.worker_cancellation import CANCEL_PROTOCOL, CancellableExternalWorkerService, WorkerCancellationClient
from sparkle.worker_service import WorkerConfig


class FakeExecutor:
    def status(self):
        return {"available": True, "mode": "fake", "preflight_passed": True,
                "hostile_canaries_passed": False, "canaries": {}, "isolation_profile": None}


class NoopTrace:
    def annotate_lifecycle(self, *args, **kwargs):
        return None


class ControlledCancellationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_worker_signed_cancel_sets_registered_running_event(self):
        key = "k" * 32
        config = WorkerConfig(
            state_dir=self.root / "worker", executor_mode="process",
            allow_unsafe_process_executor=True,
        )
        with patch.dict("os.environ", {"SPARKLE_WORKER_SIGNING_KEY": key}, clear=False):
            service = CancellableExternalWorkerService(config, executor=FakeExecutor())
        execution_id = "SPK-EXEC-" + "A" * 32
        event = threading.Event()
        service._cancel_events[execution_id] = event
        body = ExternalWorkerClient._canonical_json({
            "protocol_version": CANCEL_PROTOCOL, "execution_id": execution_id,
        })
        timestamp = str(int(service.clock()))
        headers = {
            "X-SPARKLE-Worker-Protocol": "1",
            "X-SPARKLE-Worker-Timestamp": timestamp,
            "X-SPARKLE-Worker-Signature": ExternalWorkerClient._signature(service.signing_key, timestamp, body),
        }
        response = service.handle_cancel(headers, body)
        self.assertEqual(response.status, 200)
        self.assertTrue(event.is_set())
        value = json.loads(response.body)
        self.assertEqual(value["execution_id"], execution_id)
        self.assertTrue(value["cancel_requested"])

    def test_running_controller_cancel_is_durable_and_terminal(self):
        store = ControlledExecutionStore(self.root / "controlled.sqlite3")
        contract = {
            "execution_request_id": "SPK-EXEC-REQ-" + "B" * 32,
            "authorization_id": "auth", "build_id": "build", "artifact_id": 1,
            "artifact_sha256": "a" * 64, "promotion_id": "promo", "candidate_id": 1,
            "plan_id": 1, "evaluation_id": "eval", "execution_mode": "python_unittest",
            "timeout_seconds": 10, "max_output_chars": 100, "actor": "tester", "source_origin": "operator",
        }
        record, _ = store.create_or_find(contract, hashlib.sha256(b"contract").hexdigest(), "trace")
        execution_id = record["execution_id"]
        # Lifecycle setup uses direct store transitions except authorization consumption,
        # which is irrelevant to the cancellation state-machine behavior under test.
        with store.connect() as db:
            db.execute("UPDATE controlled_executions SET status='running',started_at=? WHERE execution_id=?", ("2026-09-11T00:00:00+00:00", execution_id))
            for state in ("authorized", "queued", "submitted", "running"):
                db.execute("INSERT INTO controlled_execution_events(execution_id,state,created_at) VALUES(?,?,?)", (execution_id, state, "2026-09-11T00:00:00+00:00"))
        service = CancellableControlledExecutionService.__new__(CancellableControlledExecutionService)
        service.store = store
        service.worker = object()
        service.traces = NoopTrace()
        with patch.object(WorkerCancellationClient, "cancel", return_value={"cancel_requested": True}) as cancel:
            result = service.cancel(execution_id, approved=True)
        cancel.assert_called_once_with(execution_id)
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(result["error_type"], "OperatorCancelled")
        self.assertEqual(result["lifecycle"][-1]["state"], "cancelled")


if __name__ == "__main__":
    unittest.main()
