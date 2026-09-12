"""Execute and verify the full provenance-bearing Level-3 acceptance chain."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from sparkle.external_worker import ExternalWorkerClient
from sparkle.level3_execution import Level3ExecutionMixin
from worker_environment.level3_acceptance import _build_chain


SCHEMA = "SPARKLE-LEVEL3-FULL-ACCEPTANCE/3"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def _verified_evidence(chain: dict[str, Any]) -> dict[str, Any]:
    runtime = chain["runtime_evaluation"]
    promotion = chain["promotion"]
    build = chain["build"]
    execution = chain["execution"]
    trace = chain["trace"]
    level3 = execution.get("level3")
    if not isinstance(level3, dict):
        raise RuntimeError("Level-3 execution ledger evidence is missing")

    expected_lifecycle = [
        "requested", "authorized", "queued", "running", "collecting",
        "validated", "completed",
    ]
    expected_output_contract = Level3ExecutionMixin.output_contract()
    output_contract = level3.get("output_contract")
    if output_contract != expected_output_contract:
        raise RuntimeError("Level-3 output-contract identity is invalid")
    output_contract_sha = hashlib.sha256(_canonical(output_contract)).hexdigest()
    if level3.get("output_contract_sha256") != output_contract_sha:
        raise RuntimeError("Level-3 output-contract digest is invalid")
    if level3.get("requesting_agent") != "coding":
        raise RuntimeError("Level-3 requesting-agent association is invalid")
    if level3.get("authorized_capabilities") != ["python_unittest"]:
        raise RuntimeError("Level-3 capability authority is invalid")
    policy_sha = level3.get("execution_policy_sha256")
    if not isinstance(policy_sha, str) or len(policy_sha) != 64:
        raise RuntimeError("Level-3 execution-policy digest is invalid")
    if [item.get("state") for item in level3.get("events", [])] != expected_lifecycle:
        raise RuntimeError("Level-3 lifecycle evidence is incomplete")

    if not (
        runtime.get("status") == "evaluated"
        and runtime.get("response_verified") is True
        and runtime.get("isolation_verified") is True
        and promotion.get("status") == "completed"
        and build.get("status") == "built"
        and execution.get("status") == "verified"
        and execution.get("response_verified") is True
        and execution.get("isolation_verified") is True
        and execution.get("verification_complete") is True
        and level3.get("state") == "completed"
    ):
        raise RuntimeError("Full Level-3 chain did not reach verified completion")

    if not (
        execution.get("artifact_id") == build.get("artifact_id")
        and execution.get("artifact_sha256") == build.get("artifact_sha256")
        and execution.get("build_id") == build.get("build_id")
        and execution.get("promotion_id") == promotion.get("promotion_id")
        and execution.get("evaluation_id") == runtime.get("evaluation_id")
    ):
        raise RuntimeError("Level-3 artifact/result provenance identity is inconsistent")

    metadata = trace.get("execution_metadata")
    if not isinstance(metadata, dict):
        raise RuntimeError("Level-3 trace execution metadata is missing")
    if not (
        trace.get("trace_id") == execution.get("trace_id")
        and trace.get("status") == "success"
        and metadata.get("execution_id") == execution.get("execution_id")
        and metadata.get("artifact_id") == execution.get("artifact_id")
        and metadata.get("artifact_sha256") == execution.get("artifact_sha256")
        and metadata.get("execution_approval_id") == execution.get("authorization_id")
        and metadata.get("worker_id") == execution.get("worker_id")
        and metadata.get("result_digest") == execution.get("result_digest")
        and metadata.get("response_verified") is True
        and metadata.get("isolation_verified") is True
        and metadata.get("verification_complete") is True
        and metadata.get("deployed") is False
        and metadata.get("production_modified") is False
    ):
        raise RuntimeError("Level-3 trace/result association is invalid")

    duplicate_idempotent = (
        chain["replay_worker_runs_after_first"]
        == chain["replay_worker_runs_after_replay"]
    )
    if not duplicate_idempotent:
        raise RuntimeError("Controller duplicate request caused a second worker side effect")
    if any((
        execution.get("published") is not False,
        execution.get("deployed") is not False,
        execution.get("production_modified") is not False,
        level3.get("deployment_authorized") is not False,
    )):
        raise RuntimeError("Level-3 acceptance touched or authorized deployment")

    return {
        "schema": SCHEMA,
        "worker_id": execution["worker_id"],
        "runtime_evaluation_id": runtime["evaluation_id"],
        "runtime_response_verified": True,
        "runtime_isolation_verified": True,
        "promotion_id": promotion["promotion_id"],
        "build_id": build["build_id"],
        "artifact_id": build["artifact_id"],
        "artifact_sha256": build["artifact_sha256"],
        "execution_id": execution["execution_id"],
        "execution_authorization_id": execution["authorization_id"],
        "execution_requesting_agent": level3["requesting_agent"],
        "execution_authorized_capabilities": level3["authorized_capabilities"],
        "execution_policy_sha256": policy_sha,
        "output_contract_schema": output_contract["schema"],
        "output_contract_sha256": output_contract_sha,
        "execution_state": level3["state"],
        "execution_lifecycle": expected_lifecycle,
        "execution_response_verified": True,
        "execution_isolation_verified": True,
        "result_digest": execution["result_digest"],
        "trace_id": trace["trace_id"],
        "trace_status": trace["status"],
        "trace_result_association_verified": True,
        "artifact_provenance_verified": True,
        "duplicate_request_idempotent": True,
        "deployment_started": False,
        "deployment_authorized": False,
        "production_modified": False,
        "level_3_full_chain_verified": True,
    }


def _write(value: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(value, indent=2, sort_keys=True)
    print(rendered)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    endpoint = os.environ.get("SPARKLE_EXTERNAL_WORKER_URL", "").strip()
    worker_id = os.environ.get("SPARKLE_EXTERNAL_WORKER_ID", "").strip()
    if not endpoint or not worker_id:
        _write({
            "schema": SCHEMA,
            "status": "blocked",
            "error_type": "ExternalWorkerConfigurationMissing",
            "level_3_full_chain_verified": False,
            "deployment_started": False,
            "deployment_authorized": False,
        }, args.output)
        return 1

    try:
        with tempfile.TemporaryDirectory(prefix="sparkle-level3-full-acceptance-") as directory:
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
                evidence = _verified_evidence(_build_chain(root, worker))
            finally:
                if previous_data_dir is None:
                    os.environ.pop("SPARKLE_DATA_DIR", None)
                else:
                    os.environ["SPARKLE_DATA_DIR"] = previous_data_dir
    except Exception as exc:
        _write({
            "schema": SCHEMA,
            "status": "blocked",
            "error_type": type(exc).__name__,
            "level_3_full_chain_verified": False,
            "deployment_started": False,
            "deployment_authorized": False,
        }, args.output)
        return 1
    _write(evidence, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
