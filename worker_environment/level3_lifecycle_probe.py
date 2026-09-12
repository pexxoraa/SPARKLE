"""Exercise real-worker timeout, failure, cancellation, replay, and recovery.

These are worker lifecycle probes, not substitutes for the approved-artifact chain.
The full authorization/provenance path is verified separately by level3_acceptance.py.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import tempfile
import threading
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from sparkle.ai_system_execution import ControlledExecutionService
from sparkle.external_worker import ExternalWorkerClient, ExternalWorkerError, _NoRedirectHandler
from sparkle.level3_execution import Level3ExecutionMixin
from sparkle.worker_cancellation import WorkerCancellationClient
from worker_environment.level3_remote_probe import _load_health


SCHEMA = "SPARKLE-LEVEL3-LIFECYCLE-PROBE/1"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def _payload(
    source: str,
    *,
    project_name: str,
    timeout_seconds: int,
    max_output_chars: int = 4_000,
) -> dict[str, Any]:
    policy = {
        "policy_version": ControlledExecutionService.POLICY_VERSION,
        "environment": "cleared_allowlist",
        "network": "disabled",
        "filesystem": "read_only_artifact_ephemeral_workspace",
        "memory_bytes": 512 * 1024 * 1024,
        "cpu_seconds": timeout_seconds,
        "max_processes": 32,
        "max_workspace_bytes": ExternalWorkerClient.MAX_TOTAL_BYTES,
        "timeout_seconds": timeout_seconds,
        "max_output_chars": max_output_chars,
    }
    execution_id = "SPK-EXEC-" + uuid.uuid4().hex.upper()
    context = {
        "execution_id": execution_id,
        "execution_request_id": "SPK-EXEC-REQ-" + uuid.uuid4().hex.upper(),
        "artifact_id": 1,
        "artifact_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "build_id": "SPK-BUILD-LIFECYCLE-PROBE",
        "promotion_id": "SPK-PROMO-LIFECYCLE-PROBE",
        "candidate_id": 1,
        "plan_id": 1,
        "evaluation_id": "SPK-EVAL-LIFECYCLE-PROBE",
        "authorization_id": "SPK-EXEC-AUTH-LIFECYCLE-PROBE",
        "execution_mode": "python_unittest",
        "requesting_agent": "coding",
        "authorized_capabilities": ["python_unittest"],
        "execution_policy_sha256": hashlib.sha256(_canonical(policy)).hexdigest(),
        "output_contract": Level3ExecutionMixin.output_contract(),
        "trace_id": "SPK-LEVEL3-LIFECYCLE-" + uuid.uuid4().hex.upper(),
    }
    raw = source.encode("utf-8")
    return {
        "protocol_version": ExternalWorkerClient.EXECUTION_PROTOCOL,
        "job_id": "SPK-WRK-" + uuid.uuid4().hex.upper(),
        "operation": ExternalWorkerClient.OPERATION,
        "project_name": project_name,
        "limits": {
            "timeout_seconds": timeout_seconds,
            "max_output_chars": max_output_chars,
            "requested_network_isolation": True,
            "requested_filesystem_isolation": True,
            "requested_ephemeral": True,
            "memory_bytes": policy["memory_bytes"],
            "cpu_seconds": policy["cpu_seconds"],
            "max_processes": policy["max_processes"],
            "max_workspace_bytes": policy["max_workspace_bytes"],
            "network_policy": "disabled",
        },
        "files": [{
            "path": "tests/test_lifecycle.py",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "content_base64": base64.b64encode(raw).decode("ascii"),
        }],
        "execution_context": context,
    }


def _signed_request(endpoint: str, key: bytes, payload: dict[str, Any]) -> urllib.request.Request:
    body = _canonical(payload)
    timestamp = str(int(time.time()))
    return urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-SPARKLE-Worker-Protocol": "1",
            "X-SPARKLE-Worker-Timestamp": timestamp,
            "X-SPARKLE-Worker-Signature": ExternalWorkerClient._signature(
                key, timestamp, body,
            ),
        },
    )


def _execute(
    client: ExternalWorkerClient,
    key: bytes,
    payload: dict[str, Any],
    *,
    request_timeout: int = 30,
) -> tuple[dict[str, Any], bytes]:
    request = _signed_request(client._validated_endpoint(), key, payload)
    opener = urllib.request.build_opener(_NoRedirectHandler())
    with opener.open(request, timeout=request_timeout) as response:
        body = response.read(ExternalWorkerClient.MAX_RESPONSE_BYTES + 1)
        if len(body) > ExternalWorkerClient.MAX_RESPONSE_BYTES:
            raise RuntimeError("Lifecycle probe worker response exceeded its bound")
        value = client._validate_response(
            response,
            body,
            key=key,
            expected_job_id=payload["job_id"],
            expected_context=payload["execution_context"],
        )
    isolation = value.get("isolation_evidence", {})
    if not (
        isolation.get("profile_version") == ExternalWorkerClient.ISOLATION_PROFILE
        and isolation.get("preflight_passed") is True
        and isolation.get("hostile_canaries_passed") is True
        and isinstance(isolation.get("canaries"), dict)
        and set(isolation["canaries"]) == ExternalWorkerClient.ISOLATION_CANARIES
        and all(isolation["canaries"].values())
        and value.get("sandbox", {}).get("filesystem_isolation") is True
        and value.get("sandbox", {}).get("network_isolation") is True
    ):
        raise RuntimeError("Lifecycle probe result lacked verified isolation")
    return value, body


def _cancel_running(
    client: ExternalWorkerClient,
    key: bytes,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    outcome: dict[str, Any] = {}
    failure: list[BaseException] = []

    def execute() -> None:
        try:
            value, _body = _execute(client, key, payload, request_timeout=30)
            outcome.update(value)
        except BaseException as exc:  # propagated on the main thread
            failure.append(exc)

    thread = threading.Thread(target=execute, daemon=True)
    thread.start()
    cancellation: dict[str, Any] | None = None
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline and thread.is_alive():
        try:
            cancellation = WorkerCancellationClient(client).cancel(
                payload["execution_context"]["execution_id"]
            )
            break
        except ExternalWorkerError:
            time.sleep(0.1)
    if cancellation is None:
        raise RuntimeError("Signed running cancellation was never accepted by the worker")
    thread.join(timeout=15)
    if thread.is_alive():
        raise RuntimeError("Cancelled Level-3 worker request did not terminate")
    if failure:
        raise RuntimeError(
            f"Cancelled Level-3 worker request failed ({type(failure[0]).__name__})"
        ) from failure[0]
    return outcome, cancellation


def run_lifecycle(
    endpoint: str,
    worker_id: str,
    signing_key: bytes,
    root: Path,
) -> dict[str, Any]:
    client = ExternalWorkerClient(
        root=root / "applications",
        path=root / "lifecycle-client.sqlite3",
        enabled=True,
        endpoint=endpoint,
        expected_worker_id=worker_id,
        request_timeout_seconds=30,
    )

    timeout_source = (
        "import time, unittest\n\n"
        "class Slow(unittest.TestCase):\n"
        "    def test_timeout(self): time.sleep(3)\n"
    )
    timeout_payload = _payload(
        timeout_source, project_name="level3_timeout_probe", timeout_seconds=1,
    )
    timeout_result, timeout_body = _execute(client, signing_key, timeout_payload)
    if not (
        timeout_result["status"] == "failed"
        and timeout_result["timed_out"] is True
        and timeout_result["returncode"] != 0
    ):
        raise RuntimeError("Real worker timeout classification did not match the contract")
    replay_result, replay_body = _execute(client, signing_key, timeout_payload)
    if replay_body != timeout_body or replay_result["result_digest"] != timeout_result["result_digest"]:
        raise RuntimeError("Real worker duplicate request did not replay exact evidence")

    failure_source = (
        "import unittest\n\n"
        "class Failure(unittest.TestCase):\n"
        "    def test_failure(self): self.fail('expected lifecycle probe failure')\n"
    )
    failure_payload = _payload(
        failure_source, project_name="level3_failure_probe", timeout_seconds=5,
    )
    failure_result, _ = _execute(client, signing_key, failure_payload)
    if not (
        failure_result["status"] == "failed"
        and failure_result["timed_out"] is False
        and failure_result["returncode"] != 0
    ):
        raise RuntimeError("Real worker execution-failure classification did not match the contract")

    cancellation_source = (
        "import time, unittest\n\n"
        "class Cancel(unittest.TestCase):\n"
        "    def test_cancel(self): time.sleep(10)\n"
    )
    cancellation_payload = _payload(
        cancellation_source, project_name="level3_cancel_probe", timeout_seconds=20,
    )
    cancellation_result, cancellation = _cancel_running(
        client, signing_key, cancellation_payload,
    )
    if not (
        cancellation.get("cancel_requested") is True
        and cancellation_result.get("status") == "failed"
        and cancellation_result.get("timed_out") is False
        and cancellation_result.get("returncode") != 0
    ):
        raise RuntimeError("Real worker running-cancellation result did not match the contract")

    recovery_source = (
        "import unittest\n\n"
        "class Recovery(unittest.TestCase):\n"
        "    def test_recovery(self): self.assertTrue(True)\n"
    )
    recovery_payload = _payload(
        recovery_source, project_name="level3_recovery_probe", timeout_seconds=5,
    )
    recovery_result, _ = _execute(client, signing_key, recovery_payload)
    if not (
        recovery_result["status"] == "passed"
        and recovery_result["returncode"] == 0
        and recovery_result["timed_out"] is False
    ):
        raise RuntimeError("Real worker did not recover after timeout/failure/cancellation probes")

    health = _load_health(endpoint)
    recent = health.get("level3_jobs", {}).get("recent", [])
    cancellation_audit = next(
        (item for item in recent if item.get("job_id") == cancellation_payload["job_id"]),
        None,
    )
    if not isinstance(cancellation_audit, dict) or cancellation_audit.get("state") != "cancelled":
        raise RuntimeError("Worker cancellation lifecycle evidence was not persisted")

    return {
        "schema": SCHEMA,
        "worker_id": worker_id,
        "timeout_job_id": timeout_payload["job_id"],
        "timeout_verified": True,
        "duplicate_request_idempotent": True,
        "execution_failure_job_id": failure_payload["job_id"],
        "execution_failure_verified": True,
        "cancellation_job_id": cancellation_payload["job_id"],
        "running_cancellation_verified": True,
        "cancellation_audit_verified": True,
        "recovery_job_id": recovery_payload["job_id"],
        "post_failure_recovery_verified": True,
        "isolation_verified_for_all_results": True,
        "worker_process_interruption_verified": False,
        "worker_process_interruption_requires_host_operator": True,
        "deployment_authorized": False,
        "lifecycle_probe_passed": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    endpoint = os.environ.get("SPARKLE_EXTERNAL_WORKER_URL", "").strip()
    worker_id = os.environ.get("SPARKLE_EXTERNAL_WORKER_ID", "").strip()
    signing_key = os.environ.get("SPARKLE_WORKER_SIGNING_KEY", "").encode("utf-8")
    if not endpoint or not worker_id or not 32 <= len(signing_key) <= 4_096:
        raise RuntimeError("Level-3 external worker endpoint, identity, and signing credential are required")
    with tempfile.TemporaryDirectory(prefix="sparkle-level3-lifecycle-") as directory:
        evidence = run_lifecycle(endpoint, worker_id, signing_key, Path(directory))
    rendered = json.dumps(evidence, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "schema": SCHEMA,
            "status": "blocked",
            "error_type": type(exc).__name__,
            "lifecycle_probe_passed": False,
            "worker_process_interruption_verified": False,
            "worker_process_interruption_requires_host_operator": True,
            "deployment_authorized": False,
        }, indent=2, sort_keys=True))
        raise SystemExit(1) from None
