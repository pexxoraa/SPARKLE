"""Verify the real Level-3 worker boundary without executing an approved artifact.

The probe performs HTTPS health/identity/isolation checks and negative signed
authority checks. The full approved-artifact chain remains in level3_acceptance.py.
No secret, endpoint, source body, or response content is written to evidence.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from sparkle.ai_system_execution import ControlledExecutionService
from sparkle.external_worker import ExternalWorkerClient, _NoRedirectHandler
from sparkle.level3_execution import Level3ExecutionMixin
from sparkle.secrets import SecretResolver


SCHEMA = "SPARKLE-LEVEL3-REMOTE-PROBE/1"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def _health_url(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path.rstrip("/") != "/v1/jobs"
    ):
        raise ValueError(
            "SPARKLE_EXTERNAL_WORKER_URL must be an HTTPS /v1/jobs URL without credentials, query, or fragment"
        )
    return urlunparse((parsed.scheme, parsed.netloc, "/health", "", "", ""))


def _load_health(endpoint: str) -> dict[str, Any]:
    request = urllib.request.Request(
        _health_url(endpoint), headers={"Accept": "application/json"}, method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirectHandler())
    with opener.open(request, timeout=15) as response:
        if response.getcode() != 200:
            raise RuntimeError("Level-3 worker health did not return HTTP 200")
        body = response.read(100_001)
    if len(body) > 100_000:
        raise RuntimeError("Level-3 worker health response exceeded its bound")
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Level-3 worker health response is invalid") from exc
    if not isinstance(value, dict) or value.get("ok") is not True:
        raise RuntimeError("Level-3 worker is not ready")
    status = value.get("status")
    if not isinstance(status, dict):
        raise RuntimeError("Level-3 worker health status is invalid")
    return status


def _policy(timeout_seconds: int = 2, max_output_chars: int = 1_000) -> dict[str, Any]:
    return {
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


def _authority_payload(
    *, requesting_agent: str = "coding",
    capabilities: list[str] | None = None,
    trace_id: str = "SPK-LEVEL3-REMOTE-PROBE",
) -> dict[str, Any]:
    timeout_seconds = 2
    max_output_chars = 1_000
    source = (
        b"import unittest\n\n"
        b"class Probe(unittest.TestCase):\n"
        b"    def test_probe(self): self.assertTrue(True)\n"
    )
    policy = _policy(timeout_seconds, max_output_chars)
    context = {
        "execution_id": "SPK-EXEC-" + uuid.uuid4().hex.upper(),
        "execution_request_id": "SPK-EXEC-REQ-" + uuid.uuid4().hex.upper(),
        "artifact_id": 1,
        "artifact_sha256": "a" * 64,
        "build_id": "SPK-BUILD-REMOTE-PROBE",
        "promotion_id": "SPK-PROMO-REMOTE-PROBE",
        "candidate_id": 1,
        "plan_id": 1,
        "evaluation_id": "SPK-EVAL-REMOTE-PROBE",
        "authorization_id": "SPK-EXEC-AUTH-REMOTE-PROBE",
        "execution_mode": "python_unittest",
        "requesting_agent": requesting_agent,
        "authorized_capabilities": capabilities or ["python_unittest"],
        "execution_policy_sha256": hashlib.sha256(_canonical(policy)).hexdigest(),
        "output_contract": Level3ExecutionMixin.output_contract(),
        "trace_id": trace_id,
    }
    return {
        "protocol_version": ExternalWorkerClient.EXECUTION_PROTOCOL,
        "job_id": "SPK-WRK-" + uuid.uuid4().hex.upper(),
        "operation": ExternalWorkerClient.OPERATION,
        "project_name": "level3_remote_probe",
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
            "path": "tests/test_probe.py",
            "sha256": hashlib.sha256(source).hexdigest(),
            "content_base64": base64.b64encode(source).decode("ascii"),
        }],
        "execution_context": context,
    }


def _post_rejected(
    endpoint: str,
    signing_key: bytes,
    payload: dict[str, Any],
    *,
    expected_status: int,
    forged_signature: bool = False,
) -> bool:
    body = _canonical(payload)
    timestamp = str(int(time.time()))
    signature = (
        "sha256=" + "0" * 64
        if forged_signature
        else ExternalWorkerClient._signature(signing_key, timestamp, body)
    )
    request = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-SPARKLE-Worker-Protocol": "1",
            "X-SPARKLE-Worker-Timestamp": timestamp,
            "X-SPARKLE-Worker-Signature": signature,
        },
    )
    opener = urllib.request.build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=15):
            return False
    except urllib.error.HTTPError as exc:
        exc.read(4_097)
        return exc.code == expected_status


def run_probe(endpoint: str, expected_worker_id: str, signing_key: bytes) -> dict[str, Any]:
    status = _load_health(endpoint)
    if status.get("worker_id") != expected_worker_id:
        raise RuntimeError("Level-3 worker identity does not match the authorized worker")
    if status.get("level3_contract") != "SPARKLE-LEVEL3-WORKER/1":
        raise RuntimeError("Remote worker is not running the Level-3 contract")
    if status.get("authorized_capabilities") != ["python_unittest"]:
        raise RuntimeError("Remote worker capability authority is unexpected")
    agents = status.get("authorized_requesting_agents")
    if not isinstance(agents, list) or "coding" not in agents or "personal" in agents:
        raise RuntimeError("Remote worker requesting-agent authority is unexpected")
    if status.get("running_cancellation") is not True:
        raise RuntimeError("Remote worker cancellation support is not active")
    if status.get("deployment_authorized") is not False:
        raise RuntimeError("Remote worker must not authorize deployment")

    executor = status.get("executor")
    if not isinstance(executor, dict):
        raise RuntimeError("Remote worker executor status is missing")
    canaries = executor.get("canaries")
    if (
        executor.get("mode") != "bubblewrap"
        or executor.get("available") is not True
        or executor.get("preflight_passed") is not True
        or executor.get("hostile_canaries_passed") is not True
        or executor.get("filesystem_isolation") is not True
        or executor.get("network_isolation") is not True
        or executor.get("unsafe_process_mode") is not False
        or not isinstance(canaries, dict)
        or set(canaries) != ExternalWorkerClient.ISOLATION_CANARIES
        or not all(canaries.values())
    ):
        raise RuntimeError("Remote worker isolation preflight is not fully verified")

    forged_rejected = _post_rejected(
        endpoint, signing_key, _authority_payload(),
        expected_status=401, forged_signature=True,
    )
    wrong_agent_rejected = _post_rejected(
        endpoint, signing_key, _authority_payload(requesting_agent="personal"),
        expected_status=400,
    )
    capability_rejected = _post_rejected(
        endpoint, signing_key,
        _authority_payload(capabilities=["host_shell"]),
        expected_status=400,
    )
    malformed_rejected = _post_rejected(
        endpoint, signing_key, _authority_payload(trace_id=""),
        expected_status=400,
    )
    if not all((forged_rejected, wrong_agent_rejected, capability_rejected, malformed_rejected)):
        raise RuntimeError("One or more Level-3 authority rejection probes failed")

    return {
        "schema": SCHEMA,
        "worker_reachable": True,
        "tls_verified": True,
        "worker_identity_verified": True,
        "worker_id": expected_worker_id,
        "level3_contract_verified": True,
        "authorized_capability_verified": True,
        "requesting_agent_policy_verified": True,
        "forged_signature_rejected": forged_rejected,
        "wrong_agent_rejected": wrong_agent_rejected,
        "unauthorized_capability_rejected": capability_rejected,
        "malformed_authority_rejected": malformed_rejected,
        "bubblewrap_verified": True,
        "filesystem_isolation_verified": True,
        "network_isolation_verified": True,
        "hostile_canaries_verified": True,
        "secret_environment_protected": bool(canaries["secret_environment"]),
        "host_filesystem_read_blocked": bool(canaries["host_filesystem_read"]),
        "host_filesystem_write_blocked": bool(canaries["host_filesystem_write"]),
        "workspace_escape_blocked": bool(canaries["workspace_escape"]),
        "unauthorized_network_blocked": bool(canaries["prohibited_network"]),
        "host_process_access_blocked": bool(canaries["host_process_access"]),
        "artifact_modification_blocked": bool(canaries["artifact_modification"]),
        "running_cancellation_available": True,
        "deployment_authorized": False,
        "probe_passed": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    endpoint = os.environ.get("SPARKLE_EXTERNAL_WORKER_URL", "").strip()
    worker_id = os.environ.get("SPARKLE_EXTERNAL_WORKER_ID", "").strip()
    if not endpoint or not worker_id:
        raise RuntimeError("Level-3 external worker endpoint and identity are required")
    signing_key = SecretResolver().first(("SPARKLE_WORKER_SIGNING_KEY",)).encode("utf-8")
    if not 32 <= len(signing_key) <= 4_096:
        raise RuntimeError("Level-3 worker signing credential has an invalid length")
    evidence = run_probe(endpoint, worker_id, signing_key)
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
            "probe_passed": False,
            "deployment_authorized": False,
        }, indent=2, sort_keys=True))
        raise SystemExit(1) from None
