from __future__ import annotations

import json
import contextlib
import io
import os
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sparkle.ai_system_execution import (
    ControlledExecutionService,
    ControlledExecutionStore,
    ExecutionRejected,
)
from sparkle.external_worker import ExternalWorkerClient
from sparkle.cli import entrypoint, main
from sparkle.worker_executor import FixedUnittestExecutor
from sparkle.worker_service import ExternalWorkerService, WorkerConfig
from tests import test_ai_system_build as build_tests
from tests.test_worker_service import SIGNING_KEY, ServiceResponse


class DirectServiceOpener:
    def __init__(self, service: ExternalWorkerService):
        self.service = service
        self.calls = 0

    def __call__(self, request, timeout):
        self.calls += 1
        return ServiceResponse(self.service.handle_job(
            dict(request.header_items()), request.data,
        ))


class StubWorker:
    def __init__(self, changes=None):
        self.changes = changes or {}
        self.calls = 0

    def run_controlled_execution(self, _name, _workspace, *, execution_context, **_limits):
        self.calls += 1
        value = {
            "external_test_run_id": 1, "job_id": "SPK-WRK-" + "A" * 32,
            "worker_id": "stub-worker", "status": "passed", "returncode": 0,
            "timed_out": False, "output_limited": False, "output": "ok",
            "output_sha256": "1" * 64, "result_digest": "2" * 64,
            "response_verified": True, "isolation_verified": False,
            "execution_context": execution_context,
        }
        value.update(self.changes)
        return value


class ControlledExecutionTests(unittest.TestCase):
    def setUp(self):
        self.build_case = build_tests.ControlledBuildTests(
            "test_valid_build_is_promotion_bound_deterministic_and_non_executing"
        )
        self.build_case.setUp()
        self.addCleanup(self.build_case.tearDown)
        self.build = self.build_case.service.request(
            self.build_case.contract(), approved=True,
        )
        self.assertEqual(self.build["status"], "built")
        os.environ["SPARKLE_WORKER_SIGNING_KEY"] = SIGNING_KEY.decode()
        self.addCleanup(os.environ.pop, "SPARKLE_WORKER_SIGNING_KEY", None)
        worker_root = Path(self.build_case.temp.name) / "worker"
        worker_service = ExternalWorkerService(
            WorkerConfig(
                state_dir=worker_root, executor_mode="process",
                allow_unsafe_process_executor=True, worker_id="level2-local-worker",
            ), signing_key=SIGNING_KEY,
            executor=FixedUnittestExecutor(allow_unsafe_process=True),
        )
        self.worker_service = worker_service
        self.opener = DirectServiceOpener(worker_service)
        self.client = ExternalWorkerClient(
            enabled=True, endpoint="https://worker.example/v1/jobs",
            expected_worker_id="level2-local-worker",
            opener=self.opener,
            path=Path(self.build_case.temp.name) / "execution_worker.sqlite3",
        )
        self.store = ControlledExecutionStore()
        self.service = ControlledExecutionService(
            self.build_case.store, self.build_case.workspace,
            self.build_case.promotions, self.build_case.candidates,
            self.build_case.plans, self.build_case.evaluations,
            self.build_case.traces, self.store, self.client,
        )
        self.authorization = self.service.approve(
            self.build["build_id"], actor="execution.operator",
            source_origin="operator", approved=True,
        )

    def contract(self, **changes):
        promotion = self.build_case.promotion
        candidate = self.build_case.candidates.get(promotion["candidate_id"])
        value = {
            "protocol_version": self.service.PROTOCOL,
            "execution_request_id": "SPK-EXEC-REQ-" + "E" * 32,
            "authorization_id": self.authorization["authorization_id"],
            "build_id": self.build["build_id"], "artifact_id": self.build["artifact_id"],
            "artifact_sha256": self.build["artifact_sha256"],
            "promotion_id": promotion["promotion_id"],
            "candidate_id": candidate["candidate_id"], "plan_id": candidate["plan_id"],
            "evaluation_id": promotion["evaluation_id"], "execution_mode": "python_unittest",
            "timeout_seconds": 10, "max_output_chars": 12000,
            "actor": "execution.operator", "source_origin": "operator",
        }
        value["execution_policy"] = self.service.execution_policy(
            value["timeout_seconds"], value["max_output_chars"],
        )
        value.update(changes)
        return value

    def test_genuine_local_worker_executes_verified_artifact_and_stops_before_deployment(self):
        result = self.service.request(self.contract(), approved=True)
        self.assertEqual(result["status"], "verified")
        self.assertEqual([item["state"] for item in result["lifecycle"]], [
            "requested", "authorized", "queued", "submitted", "running", "completed", "verified",
        ])
        self.assertTrue(result["response_verified"])
        self.assertFalse(result["isolation_verified"])
        self.assertFalse(result["published"])
        self.assertFalse(result["deployed"])
        self.assertFalse(result["production_modified"])
        self.assertEqual(self.opener.calls, 1)
        self.assertFalse((Path(self.build_case.temp.name) / "execution_environment" / "requests" / result["execution_id"]).exists())

    def test_identity_authorization_staleness_and_replay_fail_closed(self):
        wrong = self.service.request(self.contract(
            execution_request_id="SPK-EXEC-REQ-" + "A" * 32,
            artifact_sha256="f" * 64,
        ), approved=True)
        self.assertEqual(wrong["status"], "artifact_mismatch")
        self.assertEqual(self.opener.calls, 0)

        authorization = self.service.approve(
            self.build["build_id"], actor="execution.operator",
            source_origin="operator", approved=True,
        )
        with self.store.connect() as connection:
            connection.execute(
                "UPDATE controlled_execution_authorizations SET expires_at=? WHERE authorization_id=?",
                ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), authorization["authorization_id"]),
            )
        stale = self.service.request(self.contract(
            execution_request_id="SPK-EXEC-REQ-" + "B" * 32,
            authorization_id=authorization["authorization_id"],
        ), approved=True)
        self.assertEqual(stale["status"], "authorization_failure")
        first = self.service.request(self.contract(), approved=True)
        replay = self.service.request(self.contract(), approved=True)
        self.assertEqual(first["execution_id"], replay["execution_id"])
        self.assertEqual(first["status"], "verified")
        self.assertEqual(self.opener.calls, 1)

    def test_artifact_tamper_and_invalidation_never_reach_worker(self):
        artifact = (
            Path(self.build_case.temp.name) / "build_environment" / "artifacts"
            / self.build["artifact_name"]
        )
        artifact.write_bytes(b"tampered")
        result = self.service.request(self.contract(), approved=True)
        self.assertEqual(result["status"], "artifact_mismatch")
        self.assertEqual(result["error_type"], "artifact_digest_mismatch")
        self.assertEqual(self.opener.calls, 0)

    def test_result_identity_timeout_output_and_execution_failures_are_distinct(self):
        cases = [
            ({"execution_context": {}}, "result_integrity_failure"),
            ({"timed_out": True, "status": "failed", "returncode": -9}, "timeout"),
            ({"output_limited": True, "status": "failed"}, "output_limit_failure"),
            ({"status": "failed", "returncode": 1}, "execution_failure"),
        ]
        for index, (changes, expected) in enumerate(cases):
            with self.subTest(expected=expected):
                store = ControlledExecutionStore(Path(self.build_case.temp.name) / f"exec-{index}.sqlite3")
                service = ControlledExecutionService(
                    self.build_case.store, self.build_case.workspace,
                    self.build_case.promotions, self.build_case.candidates,
                    self.build_case.plans, self.build_case.evaluations,
                    self.build_case.traces, store, StubWorker(changes),
                )
                authorization = service.approve(
                    self.build["build_id"], actor="execution.operator",
                    source_origin="operator", approved=True,
                )
                contract = self.contract(
                    execution_request_id="SPK-EXEC-REQ-" + f"{index + 1:X}" * 32,
                    authorization_id=authorization["authorization_id"],
                )
                result = service.request(contract, approved=True)
                self.assertEqual(result["status"], expected)

    def test_resigned_tampered_worker_result_digest_is_rejected(self):
        class TamperedOpener:
            def __init__(inner_self, service):
                inner_self.service = service

            def __call__(inner_self, request, timeout):
                response = inner_self.service.handle_job(
                    dict(request.header_items()), request.data,
                )
                value = json.loads(response.body)
                value["result_digest"] = "f" * 64
                body = ExternalWorkerClient._canonical_json(value)
                timestamp = response.headers["X-SPARKLE-Worker-Timestamp"]
                response.headers["X-SPARKLE-Worker-Signature"] = ExternalWorkerClient._signature(
                    SIGNING_KEY, timestamp, body,
                )
                response = type(response)(response.status, body, response.headers)
                return ServiceResponse(response)

        client = ExternalWorkerClient(
            enabled=True, endpoint="https://worker.example/v1/jobs",
            expected_worker_id="level2-local-worker",
            opener=TamperedOpener(self.worker_service),
            path=Path(self.build_case.temp.name) / "tampered-worker.sqlite3",
        )
        store = ControlledExecutionStore(Path(self.build_case.temp.name) / "tampered-execution.sqlite3")
        service = ControlledExecutionService(
            self.build_case.store, self.build_case.workspace,
            self.build_case.promotions, self.build_case.candidates,
            self.build_case.plans, self.build_case.evaluations,
            self.build_case.traces, store, client,
        )
        authorization = service.approve(
            self.build["build_id"], actor="execution.operator",
            source_origin="operator", approved=True,
        )
        result = service.request(self.contract(
            execution_request_id="SPK-EXEC-REQ-" + "D" * 32,
            authorization_id=authorization["authorization_id"],
        ), approved=True)
        self.assertEqual(result["status"], "result_integrity_failure")

    def test_artifact_exclusion_and_contract_schema_are_strict_and_content_free(self):
        exclusion = self.service.exclude_artifact(
            self.build["artifact_id"], status="invalidated", reason="operator withdrawal",
            actor="execution.operator", source_origin="operator", approved=True,
        )
        self.assertEqual(exclusion["status"], "invalidated")
        with self.assertRaisesRegex(ExecutionRejected, "invalidated"):
            self.service.approve(
                self.build["build_id"], actor="execution.operator",
                source_origin="operator", approved=True,
            )
        with self.assertRaisesRegex(ValueError, "contract fields"):
            self.service.request({"build_id": self.build["build_id"]}, approved=True)
        self.assertNotIn("def value", json.dumps({
            "authorization": self.authorization, "executions": self.store.list(),
        }))

    def test_cli_lists_execution_as_separate_from_deployment(self):
        output, error = io.StringIO(), io.StringIO()
        stub = type("ExecutionSystemStub", (), {
            "ai_system_controlled_executor": self.service,
            "controlled_executions": self.store,
        })()
        with (
            patch("sparkle.cli.SparkleSystem", return_value=stub),
            contextlib.redirect_stdout(output), contextlib.redirect_stderr(error),
        ):
            self.assertEqual(main(["ai-system-controlled-executions"]), 0)
            self.assertEqual(entrypoint([
                "ai-system-execution-approve", self.build["build_id"],
                "execution.operator",
            ]), 1)
        evidence = output.getvalue()
        self.assertIn(self.service.PROTOCOL, evidence)
        self.assertIn('"execution_is_deployment": false', evidence)
        self.assertIn("explicit approval", error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())

    def test_concurrent_request_claim_and_cancellation_are_deterministic(self):
        contract, digest = self.service.validate(self.contract())
        barrier = threading.Barrier(3)
        records = []

        def create():
            barrier.wait()
            records.append(self.store.create_or_find(contract, digest, "SPK-2026-777777"))

        threads = [threading.Thread(target=create) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()
        self.assertEqual(len({item[0]["execution_id"] for item in records}), 1)
        self.assertEqual({item[1] for item in records}, {"created", "replay"})
        cancelled = self.service.cancel(records[0][0]["execution_id"], approved=True)
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertFalse(cancelled["deployed"])

    def test_policy_worker_identity_and_lifecycle_graph_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "policy"):
            self.service.request(self.contract(execution_policy={}), approved=True)
        unpinned = ExternalWorkerClient(
            enabled=True, endpoint="https://worker.example/v1/jobs",
            opener=self.opener,
            path=Path(self.build_case.temp.name) / "unpinned-worker.sqlite3",
        )
        with self.assertRaisesRegex(Exception, "worker identity"):
            unpinned.run_controlled_execution(
                "execution_identity_test",
                Path(self.build_case.temp.name),
                execution_context={}, timeout_seconds=10, max_output_chars=100,
            )
        contract, digest = self.service.validate(self.contract(
            execution_request_id="SPK-EXEC-REQ-" + "9" * 32,
        ))
        record, _ = self.store.create_or_find(contract, digest, "SPK-2026-999999")
        with self.assertRaisesRegex(ValueError, "transition"):
            self.store.transition(record["execution_id"], "requested", "verified")

        wrong_client = ExternalWorkerClient(
            enabled=True, endpoint="https://worker.example/v1/jobs",
            expected_worker_id="different-worker",
            opener=self.opener,
            path=Path(self.build_case.temp.name) / "wrong-worker.sqlite3",
        )
        wrong_store = ControlledExecutionStore(
            Path(self.build_case.temp.name) / "wrong-worker-execution.sqlite3",
        )
        wrong_service = ControlledExecutionService(
            self.build_case.store, self.build_case.workspace,
            self.build_case.promotions, self.build_case.candidates,
            self.build_case.plans, self.build_case.evaluations,
            self.build_case.traces, wrong_store, wrong_client,
        )
        authorization = wrong_service.approve(
            self.build["build_id"], actor="execution.operator",
            source_origin="operator", approved=True,
        )
        rejected = wrong_service.request(self.contract(
            execution_request_id="SPK-EXEC-REQ-" + "8" * 32,
            authorization_id=authorization["authorization_id"],
        ), approved=True)
        self.assertEqual(rejected["status"], "worker_authentication_failure")


if __name__ == "__main__":
    unittest.main()
