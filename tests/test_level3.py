from __future__ import annotations

import base64
import hashlib
import json
import unittest
from pathlib import Path

from sparkle.ai_system_execution import ControlledExecutionStore
from sparkle.controlled_execution_cancel import CancellableControlledExecutionService
from sparkle.external_worker import ExternalWorkerClient, ExternalWorkerError
from sparkle.level3_execution import Level3ExecutionMixin
from sparkle.level3_worker import Level3WorkerRequestValidator
from sparkle.worker_service import WorkerServiceError
from tests import test_ai_system_build as build_tests


class IsolatedDeterministicWorker:
    """Software test double only; never accepted as host isolation evidence."""
    def __init__(self, scenario="success"): self.scenario, self.calls = scenario, 0
    def run_controlled_execution(self, _name, _workspace, *, execution_context, **_limits):
        self.calls += 1
        if self.scenario == "worker_failure":
            raise ExternalWorkerError("External worker transport failed (deterministic fixture)")
        value = {
            "external_test_run_id": 1, "job_id": "SPK-WRK-" + "A" * 32,
            "worker_id": "deterministic-level3-fixture", "status": "passed",
            "returncode": 0, "timed_out": False, "output_limited": False,
            "output": "deterministic fixture output",
            "output_sha256": hashlib.sha256(b"deterministic fixture output").hexdigest(),
            "result_digest": "2" * 64, "response_verified": True,
            "isolation_verified": self.scenario != "isolation_failure",
            "execution_context": execution_context,
        }
        if self.scenario == "timeout": value.update(status="failed", returncode=-9, timed_out=True)
        elif self.scenario == "failed": value.update(status="failed", returncode=1)
        return value


class Level3ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.build_case = build_tests.ControlledBuildTests("test_valid_build_is_promotion_bound_deterministic_and_non_executing")
        self.build_case.setUp(); self.addCleanup(self.build_case.tearDown)
        self.build = self.build_case.service.request(self.build_case.contract(), approved=True)

    def service(self, worker=None, suffix="main"):
        store = ControlledExecutionStore(Path(self.build_case.temp.name) / f"level3-{suffix}.sqlite3")
        service = CancellableControlledExecutionService(
            self.build_case.store, self.build_case.workspace, self.build_case.promotions,
            self.build_case.candidates, self.build_case.plans, self.build_case.evaluations,
            self.build_case.traces, store, worker or IsolatedDeterministicWorker(),
        )
        authorization = service.approve(self.build["build_id"], actor="execution.operator", source_origin="operator", approved=True)
        return service, store, authorization

    def contract(self, service, authorization, marker="E"):
        promotion = self.build_case.promotion
        candidate = self.build_case.candidates.get(promotion["candidate_id"])
        value = {
            "protocol_version": service.PROTOCOL, "execution_request_id": "SPK-EXEC-REQ-" + marker * 32,
            "authorization_id": authorization["authorization_id"], "build_id": self.build["build_id"],
            "artifact_id": self.build["artifact_id"], "artifact_sha256": self.build["artifact_sha256"],
            "promotion_id": promotion["promotion_id"], "candidate_id": candidate["candidate_id"],
            "plan_id": candidate["plan_id"], "evaluation_id": promotion["evaluation_id"],
            "execution_mode": "python_unittest", "timeout_seconds": 10, "max_output_chars": 12000,
            "actor": "execution.operator", "source_origin": "operator",
        }
        value["execution_policy"] = service.execution_policy(10, 12000)
        return value

    def test_complete_level3_lifecycle_and_authority_are_persisted(self):
        worker = IsolatedDeterministicWorker(); service, _store, auth = self.service(worker)
        result = service.request(self.contract(service, auth), approved=True, requesting_agent="coding")
        self.assertEqual(result["status"], "verified"); self.assertEqual(result["level3"]["state"], "completed")
        self.assertEqual([e["state"] for e in result["level3"]["events"]],
                         ["requested", "authorized", "queued", "running", "collecting", "validated", "completed"])
        self.assertEqual(result["level3"]["requesting_agent"], "coding")
        self.assertEqual(result["level3"]["authorized_capabilities"], ["python_unittest"])
        self.assertEqual(result["level3"]["output_contract"]["schema"], "SPARKLE-LEVEL3-OUTPUT/1")
        self.assertFalse(result["level3"]["deployment_authorized"]); self.assertEqual(worker.calls, 1)

    def test_success_exit_without_isolation_is_policy_violation(self):
        service, _store, auth = self.service(IsolatedDeterministicWorker("isolation_failure"), "isolation")
        result = service.request(self.contract(service, auth, "A"), approved=True)
        self.assertEqual(result["status"], "isolation_failure")
        self.assertEqual((result["level3"]["state"], result["level3"]["failure_stage"]), ("policy_violation", "isolation"))
        self.assertFalse(result["verification_complete"])

    def test_timeout_execution_failure_and_worker_failure_are_distinct(self):
        cases = [("timeout", "timeout", "timed_out"), ("failed", "execution_failure", "failed"),
                 ("worker_failure", "worker_unavailable", "infrastructure_failure")]
        for index, (scenario, legacy, level3) in enumerate(cases):
            with self.subTest(scenario=scenario):
                service, _store, auth = self.service(IsolatedDeterministicWorker(scenario), f"scenario-{index}")
                result = service.request(self.contract(service, auth, str(index + 1)), approved=True)
                self.assertEqual((result["status"], result["level3"]["state"]), (legacy, level3))

    def test_duplicate_request_replays_without_duplicate_worker_side_effect(self):
        worker = IsolatedDeterministicWorker(); service, _store, auth = self.service(worker, "replay")
        contract = self.contract(service, auth, "B")
        first = service.request(contract, approved=True); second = service.request(contract, approved=True)
        self.assertEqual(first["execution_id"], second["execution_id"]); self.assertEqual(worker.calls, 1)
        self.assertEqual(second["level3"]["state"], "completed")

    def test_prerun_cancellation_is_reflected_in_level3_ledger(self):
        service, store, auth = self.service(IsolatedDeterministicWorker(), "cancel")
        contract, digest = service.validate(self.contract(service, auth, "C"))
        record, _ = store.create_or_find(contract, digest, "SPK-LEVEL3-CANCEL-TRACE")
        service._level3_create(record["execution_id"], "SPK-LEVEL3-CANCEL-TRACE", "system", contract)
        cancelled = service.cancel(record["execution_id"], approved=True)
        self.assertEqual((cancelled["status"], cancelled["level3"]["state"]), ("cancelled", "cancelled"))


class Level3WorkerContractTests(unittest.TestCase):
    KEY = b"k" * 32
    def validator(self): return Level3WorkerRequestValidator(self.KEY, clock=lambda: 1000)

    def payload(self):
        content = b"import unittest\n"
        policy = {
            "policy_version": "SPARKLE-CONTROLLED-EXECUTION-POLICY/1", "environment": "cleared_allowlist",
            "network": "disabled", "filesystem": "read_only_artifact_ephemeral_workspace",
            "memory_bytes": 512 * 1024 * 1024, "cpu_seconds": 10, "max_processes": 32,
            "max_workspace_bytes": ExternalWorkerClient.MAX_TOTAL_BYTES, "timeout_seconds": 10,
            "max_output_chars": 1000,
        }
        context = {
            "execution_id": "SPK-EXEC-" + "1" * 32, "execution_request_id": "SPK-EXEC-REQ-" + "2" * 32,
            "artifact_id": 1, "artifact_sha256": "a" * 64, "build_id": "SPK-BUILD-TEST",
            "promotion_id": "SPK-PROMO-TEST", "candidate_id": 1, "plan_id": 1,
            "evaluation_id": "SPK-EVAL-TEST", "authorization_id": "SPK-EXEC-AUTH-TEST",
            "execution_mode": "python_unittest", "requesting_agent": "coding",
            "authorized_capabilities": ["python_unittest"],
            "execution_policy_sha256": hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "output_contract": Level3ExecutionMixin.output_contract(), "trace_id": "SPK-TRACE-LEVEL3-TEST",
        }
        return {
            "protocol_version": ExternalWorkerClient.EXECUTION_PROTOCOL, "job_id": "SPK-WRK-" + "A" * 32,
            "operation": ExternalWorkerClient.OPERATION, "project_name": "level3_test",
            "limits": {"timeout_seconds": 10, "max_output_chars": 1000,
                       "requested_network_isolation": True, "requested_filesystem_isolation": True,
                       "requested_ephemeral": True, "memory_bytes": 512 * 1024 * 1024,
                       "cpu_seconds": 10, "max_processes": 32,
                       "max_workspace_bytes": ExternalWorkerClient.MAX_TOTAL_BYTES, "network_policy": "disabled"},
            "files": [{"path": "tests/test_safe.py", "sha256": hashlib.sha256(content).hexdigest(),
                       "content_base64": base64.b64encode(content).decode()}], "execution_context": context,
        }

    def signed(self, payload):
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(); timestamp = "1000"
        return body, {"X-SPARKLE-Worker-Protocol": "1", "X-SPARKLE-Worker-Timestamp": timestamp,
                      "X-SPARKLE-Worker-Signature": ExternalWorkerClient._signature(self.KEY, timestamp, body)}

    def test_complete_level3_worker_context_is_accepted(self):
        payload = self.payload(); body, headers = self.signed(payload); job = self.validator().validate(headers, body)
        self.assertEqual(job.execution_context["requesting_agent"], "coding")
        self.assertEqual(job.execution_context["authorized_capabilities"], ["python_unittest"])
        self.assertEqual(job.request_hash, hashlib.sha256(body).hexdigest())

    def test_unauthorized_capability_agent_policy_output_and_trace_fail_closed(self):
        mutations = [lambda p: p["execution_context"].update(authorized_capabilities=["host_shell"]),
                     lambda p: p["execution_context"].update(requesting_agent="Coding Agent"),
                     lambda p: p["execution_context"].update(execution_policy_sha256="f" * 64),
                     lambda p: p["execution_context"].update(output_contract={"schema": "forged"}),
                     lambda p: p["execution_context"].update(trace_id="")]
        for mutate in mutations:
            payload = self.payload(); mutate(payload); body, headers = self.signed(payload)
            with self.assertRaises(WorkerServiceError): self.validator().validate(headers, body)


if __name__ == "__main__": unittest.main()
