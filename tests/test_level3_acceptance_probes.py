from __future__ import annotations

import copy
import hashlib
import json
import unittest

from sparkle.ai_system_execution import ControlledExecutionService
from sparkle.level3_execution import Level3ExecutionMixin
from worker_environment.level3_full_acceptance import _verified_evidence
from worker_environment.level3_lifecycle_probe import _payload as lifecycle_payload
from worker_environment.level3_remote_probe import _authority_payload, _health_url


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


class Level3AcceptanceProbeTests(unittest.TestCase):
    def test_remote_probe_requires_exact_https_worker_url(self):
        self.assertEqual(
            _health_url("https://worker.example/v1/jobs"),
            "https://worker.example/health",
        )
        for invalid in (
            "http://worker.example/v1/jobs",
            "https://user@worker.example/v1/jobs",
            "https://worker.example/other",
            "https://worker.example/v1/jobs?token=x",
            "https://worker.example/v1/jobs#fragment",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                _health_url(invalid)

    def test_remote_authority_probe_builds_exact_signed_policy_identity(self):
        payload = _authority_payload()
        context = payload["execution_context"]
        limits = payload["limits"]
        policy = {
            "policy_version": ControlledExecutionService.POLICY_VERSION,
            "environment": "cleared_allowlist",
            "network": "disabled",
            "filesystem": "read_only_artifact_ephemeral_workspace",
            "memory_bytes": limits["memory_bytes"],
            "cpu_seconds": limits["cpu_seconds"],
            "max_processes": limits["max_processes"],
            "max_workspace_bytes": limits["max_workspace_bytes"],
            "timeout_seconds": limits["timeout_seconds"],
            "max_output_chars": limits["max_output_chars"],
        }
        self.assertEqual(context["requesting_agent"], "coding")
        self.assertEqual(context["authorized_capabilities"], ["python_unittest"])
        self.assertEqual(context["output_contract"], Level3ExecutionMixin.output_contract())
        self.assertEqual(
            context["execution_policy_sha256"],
            hashlib.sha256(canonical(policy)).hexdigest(),
        )

    def test_lifecycle_probe_policy_digest_matches_wire_limits(self):
        payload = lifecycle_payload(
            "import unittest\nclass T(unittest.TestCase): pass\n",
            project_name="level3_probe_test",
            timeout_seconds=7,
        )
        limits = payload["limits"]
        policy = {
            "policy_version": ControlledExecutionService.POLICY_VERSION,
            "environment": "cleared_allowlist",
            "network": "disabled",
            "filesystem": "read_only_artifact_ephemeral_workspace",
            "memory_bytes": limits["memory_bytes"],
            "cpu_seconds": limits["cpu_seconds"],
            "max_processes": limits["max_processes"],
            "max_workspace_bytes": limits["max_workspace_bytes"],
            "timeout_seconds": limits["timeout_seconds"],
            "max_output_chars": limits["max_output_chars"],
        }
        self.assertEqual(
            payload["execution_context"]["execution_policy_sha256"],
            hashlib.sha256(canonical(policy)).hexdigest(),
        )

    def chain(self):
        output_contract = Level3ExecutionMixin.output_contract()
        output_sha = hashlib.sha256(canonical(output_contract)).hexdigest()
        execution_id = "SPK-EXEC-" + "A" * 32
        authorization_id = "SPK-EXEC-AUTH-TEST"
        artifact_sha = "b" * 64
        result_digest = "c" * 64
        trace_id = "SPK-TRACE-LEVEL3-ACCEPTANCE"
        level3 = {
            "state": "completed",
            "requesting_agent": "coding",
            "authorized_capabilities": ["python_unittest"],
            "execution_policy_sha256": "d" * 64,
            "output_contract": output_contract,
            "output_contract_sha256": output_sha,
            "deployment_authorized": False,
            "events": [{"state": state} for state in (
                "requested", "authorized", "queued", "running", "collecting",
                "validated", "completed",
            )],
        }
        execution = {
            "execution_id": execution_id,
            "authorization_id": authorization_id,
            "artifact_id": 9,
            "artifact_sha256": artifact_sha,
            "build_id": "SPK-BUILD-TEST",
            "promotion_id": "SPK-PROMO-TEST",
            "evaluation_id": "SPK-EVAL-TEST",
            "status": "verified",
            "worker_id": "worker-01",
            "response_verified": True,
            "isolation_verified": True,
            "verification_complete": True,
            "result_digest": result_digest,
            "trace_id": trace_id,
            "published": False,
            "deployed": False,
            "production_modified": False,
            "level3": level3,
        }
        trace = {
            "trace_id": trace_id,
            "status": "success",
            "execution_metadata": {
                "execution_id": execution_id,
                "artifact_id": 9,
                "artifact_sha256": artifact_sha,
                "execution_approval_id": authorization_id,
                "worker_id": "worker-01",
                "result_digest": result_digest,
                "response_verified": True,
                "isolation_verified": True,
                "verification_complete": True,
                "deployed": False,
                "production_modified": False,
            },
        }
        return {
            "runtime_evaluation": {
                "evaluation_id": "SPK-EVAL-TEST",
                "status": "evaluated",
                "response_verified": True,
                "isolation_verified": True,
            },
            "promotion": {"promotion_id": "SPK-PROMO-TEST", "status": "completed"},
            "build": {
                "build_id": "SPK-BUILD-TEST",
                "artifact_id": 9,
                "artifact_sha256": artifact_sha,
                "status": "built",
            },
            "execution": execution,
            "trace": trace,
            "replay_worker_runs_after_first": 2,
            "replay_worker_runs_after_replay": 2,
        }

    def test_full_acceptance_verifier_requires_provenance_trace_and_no_deployment(self):
        evidence = _verified_evidence(self.chain())
        self.assertTrue(evidence["level_3_full_chain_verified"])
        self.assertTrue(evidence["artifact_provenance_verified"])
        self.assertTrue(evidence["trace_result_association_verified"])
        self.assertFalse(evidence["deployment_authorized"])

        deployed = copy.deepcopy(self.chain())
        deployed["execution"]["deployed"] = True
        with self.assertRaises(RuntimeError):
            _verified_evidence(deployed)


if __name__ == "__main__":
    unittest.main()
