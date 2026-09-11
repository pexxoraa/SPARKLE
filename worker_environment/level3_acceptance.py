"""Run SPARKLE's real external-worker Level-3 acceptance chain.

This script deliberately uses deterministic source content so the acceptance gate
measures SPARKLE's authorization, immutable-artifact, worker, isolation, result,
and trace architecture rather than model quality. It never deploys the artifact.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from sparkle.ai_system_build import (
    ControlledBuildArtifactWorkspace,
    ControlledBuildService,
    ControlledBuildStore,
)
from sparkle.ai_system_execution import ControlledExecutionStore
from sparkle.ai_system_plan import AISystemImplementationPlanStore
from sparkle.ai_system_promotion import (
    ControlledPromotionWorkspace,
    ControlledSourcePromotionService,
    SourcePromotionStore,
)
from sparkle.ai_system_runtime import CandidateRuntimeEvaluator, RuntimeEvaluationStore
from sparkle.ai_system_source import SourceCandidateStore, SourceCandidateWorkspace
from sparkle.controlled_execution_cancel import CancellableControlledExecutionService
from sparkle.external_worker import ExternalWorkerClient, ExternalWorkerError
from sparkle.trace import TraceStore


SCHEMA = "SPARKLE-LEVEL3-ACCEPTANCE/2"


def _runtime_contract(candidate_id: int, plan_id: int) -> dict[str, Any]:
    return {
        "protocol_version": CandidateRuntimeEvaluator.PROTOCOL,
        "candidate_id": candidate_id,
        "plan_id": plan_id,
        "requested_capabilities": ["python_unittest"],
        "runtime_requirements": {"language": "python", "framework": "unittest"},
        "input_data": {},
        "expected_behavior": "The deterministic Level-3 acceptance implementation returns forty two.",
        "execution_limits": {"timeout_seconds": 10, "max_output_chars": 4_000},
        "evaluation_criteria": [
            {"name": "worker_pass", "kind": "worker_pass", "value": ""},
        ],
        "test_files": [{
            "path": "tests/test_level3_runtime_acceptance.py",
            "content": (
                "import unittest\n"
                "from src.level3_acceptance import value\n\n"
                "class Level3RuntimeAcceptance(unittest.TestCase):\n"
                "    def test_value(self): self.assertEqual(value(), 42)\n"
            ),
        }],
        "result_format": "SPARKLE-RUNTIME-RESULT/1",
    }


def _build_chain(root: Path, worker: ExternalWorkerClient) -> dict[str, Any]:
    candidates = SourceCandidateStore()
    candidate_workspace = SourceCandidateWorkspace()
    plans = AISystemImplementationPlanStore()
    evaluations = RuntimeEvaluationStore()
    traces = TraceStore()

    plan_id = plans.create(
        system_name="level3_acceptance", blueprint_sha256="b" * 64,
        plan_sha256="a" * 64, plan_bytes=500,
    )
    plans.finish(
        plan_id, status="materialized_static_verified", workspace_build_id=plan_id,
    )
    plans.approve_for_generation(plan_id, approved=True)

    candidate_id = candidates.begin(
        disclosure_id=101, plan_id=plan_id, system_name="level3_acceptance",
        plan_sha256="a" * 64,
    )
    _manifest, files, candidate_digest = candidate_workspace.write(
        candidate_id=candidate_id, plan_id=plan_id, plan_sha256="a" * 64,
        files=[
            {
                "path": "src/level3_acceptance/__init__.py",
                "content": "from .system import value\n",
            },
            {
                "path": "src/level3_acceptance/system.py",
                "content": "def value():\n    return 42\n",
            },
            {
                "path": "tests/test_level3_acceptance.py",
                "content": (
                    "import unittest\n"
                    "from src.level3_acceptance import value\n\n"
                    "class Level3Acceptance(unittest.TestCase):\n"
                    "    def test_value(self): self.assertEqual(value(), 42)\n"
                ),
            },
        ],
    )
    candidates.mark_generated(
        candidate_id, files=files, candidate_sha256=candidate_digest,
        trace_id="SPK-LEVEL3-ACCEPTANCE-SOURCE",
    )
    candidates.review(candidate_id, decision="accept", notes_sha256="c" * 64)
    candidates.record_verification(
        candidate_id,
        {"status": "passed", "checks": [], "runtime_tests_executed": False},
    )
    candidates.approve(candidate_id, approved=True)

    runtime = CandidateRuntimeEvaluator(
        candidates, candidate_workspace, traces, evaluations, worker,
    )
    runtime_result = runtime.request(
        _runtime_contract(candidate_id, plan_id), approved=True,
    )
    if (
        runtime_result["status"] != "evaluated"
        or not runtime_result["response_verified"]
        or not runtime_result["isolation_verified"]
    ):
        raise RuntimeError(
            f"Real external runtime evaluation did not verify isolation: {runtime_result['status']}"
        )

    promotions = SourcePromotionStore()
    promotion_workspace = ControlledPromotionWorkspace()
    promoter = ControlledSourcePromotionService(
        candidates, candidate_workspace, plans, evaluations, traces,
        promotions, promotion_workspace,
    )
    promotion_approval = promoter.approve(
        candidate_id, runtime_result["evaluation_id"],
        actor="level3.acceptance.release", source_origin="operator", approved=True,
    )
    promotion = promoter.request({
        "protocol_version": promoter.PROTOCOL,
        "request_id": "SPK-PROMO-REQ-" + "A" * 32,
        "candidate_id": candidate_id,
        "candidate_sha256": candidate_digest,
        "plan_id": plan_id,
        "plan_sha256": "a" * 64,
        "evaluation_id": runtime_result["evaluation_id"],
        "approval_id": promotion_approval["approval_id"],
        "destination": "staging/level3_acceptance",
        "actor": "level3.acceptance.release",
        "source_origin": "operator",
    }, approved=True)
    if promotion["status"] != "completed":
        raise RuntimeError("Controlled Level-3 acceptance promotion did not complete")

    builds = ControlledBuildStore()
    build_workspace = ControlledBuildArtifactWorkspace(promotion_workspace)
    builder = ControlledBuildService(
        promotions, candidates, traces, builds, build_workspace,
    )
    build_approval = builder.approve(
        promotion["promotion_id"], actor="level3.acceptance.build",
        source_origin="operator", approved=True,
    )
    build = builder.request({
        "protocol_version": builder.PROTOCOL,
        "request_id": "SPK-BUILD-REQ-" + "B" * 32,
        "promotion_id": promotion["promotion_id"],
        "promotion_digest": promotion["destination_digest"],
        "approval_id": build_approval["approval_id"],
        "build_kind": "source_bundle",
        "actor": "level3.acceptance.build",
        "source_origin": "operator",
    }, approved=True)
    if build["status"] != "built":
        raise RuntimeError("Controlled Level-3 acceptance build did not complete")

    execution_store = ControlledExecutionStore()
    executor = CancellableControlledExecutionService(
        builds, build_workspace, promotions, candidates, plans, evaluations,
        traces, execution_store, worker,
    )
    execution_authorization = executor.approve(
        build["build_id"], actor="level3.acceptance.execution",
        source_origin="operator", approved=True,
    )
    candidate = candidates.get(candidate_id)
    contract = {
        "protocol_version": executor.PROTOCOL,
        "execution_request_id": "SPK-EXEC-REQ-" + "E" * 32,
        "authorization_id": execution_authorization["authorization_id"],
        "build_id": build["build_id"],
        "artifact_id": build["artifact_id"],
        "artifact_sha256": build["artifact_sha256"],
        "promotion_id": promotion["promotion_id"],
        "candidate_id": candidate_id,
        "plan_id": candidate["plan_id"],
        "evaluation_id": runtime_result["evaluation_id"],
        "execution_mode": "python_unittest",
        "timeout_seconds": 10,
        "max_output_chars": 4_000,
        "actor": "level3.acceptance.execution",
        "source_origin": "operator",
    }
    contract["execution_policy"] = executor.execution_policy(10, 4_000)
    before_replay = len(worker.list(limit=100))
    execution = executor.request(
        contract, approved=True, requesting_agent="coding",
    )
    after_first = len(worker.list(limit=100))
    replay = executor.request(
        contract, approved=True, requesting_agent="coding",
    )
    after_replay = len(worker.list(limit=100))
    if execution["status"] != "verified" or execution["level3"]["state"] != "completed":
        raise RuntimeError("Level-3 controlled execution did not reach verified completion")
    if not execution["response_verified"] or not execution["isolation_verified"]:
        raise RuntimeError("Level-3 controlled execution lacks verified worker isolation")
    expected_states = [
        "requested", "authorized", "queued", "running", "collecting",
        "validated", "completed",
    ]
    if [item["state"] for item in execution["level3"]["events"]] != expected_states:
        raise RuntimeError("Level-3 controlled execution lifecycle is incomplete")
    if replay["execution_id"] != execution["execution_id"] or after_replay != after_first:
        raise RuntimeError("Level-3 duplicate execution was not idempotent")
    trace = next(
        item for item in traces.recent(limit=100)
        if item["trace_id"] == execution["trace_id"]
    )
    if trace["status"] != "success":
        raise RuntimeError("Level-3 completion trace was not persisted")

    return {
        "runtime_evaluation": runtime_result,
        "promotion": promotion,
        "build": build,
        "execution": execution,
        "replay_worker_runs_before": before_replay,
        "replay_worker_runs_after_first": after_first,
        "replay_worker_runs_after_replay": after_replay,
        "trace": trace,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    endpoint = os.environ.get("SPARKLE_EXTERNAL_WORKER_URL", "").strip()
    worker_id = os.environ.get("SPARKLE_EXTERNAL_WORKER_ID", "").strip()
    if not endpoint or not worker_id:
        raise ExternalWorkerError("Level-3 external worker endpoint and identity are required")

    with tempfile.TemporaryDirectory(prefix="sparkle-level3-acceptance-") as directory:
        root = Path(directory)
        previous_data_dir = os.environ.get("SPARKLE_DATA_DIR")
        os.environ["SPARKLE_DATA_DIR"] = str(root / "state")
        try:
            worker = ExternalWorkerClient(
                root=root,
                path=root / "external-worker-evidence.sqlite3",
                enabled=True,
                endpoint=endpoint,
                expected_worker_id=worker_id,
            )
            chain = _build_chain(root, worker)
            execution = chain["execution"]
            runtime = chain["runtime_evaluation"]
            evidence = {
                "schema": SCHEMA,
                "worker_id": execution["worker_id"],
                "runtime_evaluation_id": runtime["evaluation_id"],
                "runtime_response_verified": runtime["response_verified"],
                "runtime_isolation_verified": runtime["isolation_verified"],
                "promotion_id": chain["promotion"]["promotion_id"],
                "build_id": chain["build"]["build_id"],
                "artifact_id": chain["build"]["artifact_id"],
                "artifact_sha256": chain["build"]["artifact_sha256"],
                "execution_id": execution["execution_id"],
                "execution_requesting_agent": execution["level3"]["requesting_agent"],
                "execution_state": execution["level3"]["state"],
                "execution_lifecycle": [
                    item["state"] for item in execution["level3"]["events"]
                ],
                "execution_response_verified": execution["response_verified"],
                "execution_isolation_verified": execution["isolation_verified"],
                "result_digest": execution["result_digest"],
                "trace_id": execution["trace_id"],
                "trace_status": chain["trace"]["status"],
                "duplicate_request_idempotent": (
                    chain["replay_worker_runs_after_first"]
                    == chain["replay_worker_runs_after_replay"]
                ),
                "deployment_started": False,
                "deployment_authorized": False,
                "level_3_full_chain_verified": True,
            }
        finally:
            if previous_data_dir is None:
                os.environ.pop("SPARKLE_DATA_DIR", None)
            else:
                os.environ["SPARKLE_DATA_DIR"] = previous_data_dir
    rendered = json.dumps(evidence, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ExternalWorkerError, RuntimeError, ValueError, KeyError) as exc:
        print(json.dumps({
            "schema": SCHEMA,
            "status": "blocked",
            "failure_stage": "external_acceptance",
            "error_type": type(exc).__name__,
            "level_3_full_chain_verified": False,
            "deployment_started": False,
            "deployment_authorized": False,
        }, indent=2, sort_keys=True))
        raise SystemExit(1) from None
