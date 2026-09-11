from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import replace
from typing import Any, Mapping

from sparkle.ai_system_execution import ControlledExecutionService
from sparkle.external_worker import ExternalWorkerClient
from sparkle.secrets import SecretNotFoundError
from sparkle.worker_cancellation import (
    CancellableExternalWorkerService,
    build_cancellable_server,
)
from sparkle.worker_service import (
    WorkerConfig,
    WorkerRequestValidator,
    WorkerServiceError,
)


LEVEL3_CONTEXT_FIELDS = {
    "requesting_agent", "authorized_capabilities", "execution_policy_sha256",
    "output_contract", "trace_id",
}
LEVEL3_OUTPUT_SCHEMA = "SPARKLE-LEVEL3-OUTPUT/1"
LEVEL3_SERVICE_SCHEMA = "SPARKLE-LEVEL3-WORKER/1"
_AGENT = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def _expected_policy(limits: dict[str, Any]) -> dict[str, Any]:
    return {
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


def _expected_output_contract() -> dict[str, Any]:
    return {
        "schema": LEVEL3_OUTPUT_SCHEMA,
        "capability": "python_unittest",
        "required_status": "passed",
        "required_returncode": 0,
        "timed_out": False,
        "output_limited": False,
        "response_verified": True,
        "isolation_verified": True,
    }


class Level3WorkerRequestValidator(WorkerRequestValidator):
    """Require agent/capability/policy/output/trace identity on controlled jobs."""

    def validate(self, headers: Mapping[str, str], body: bytes):
        if not body or len(body) > self.max_body_bytes:
            return super().validate(headers, body)
        self._authenticate(headers, body)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return super().validate(headers, body)
        controlled = (
            isinstance(payload, dict)
            and payload.get("protocol_version") == ExternalWorkerClient.EXECUTION_PROTOCOL
        )
        if not controlled:
            return super().validate(headers, body)
        context = payload.get("execution_context")
        if not isinstance(context, dict):
            raise WorkerServiceError("Worker Level 3 execution context is invalid")
        expected_fields = self.EXECUTION_CONTEXT_FIELDS | LEVEL3_CONTEXT_FIELDS
        if set(context) != expected_fields:
            raise WorkerServiceError("Worker Level 3 execution context fields are invalid")
        requesting_agent = context.get("requesting_agent")
        capabilities = context.get("authorized_capabilities")
        policy_sha = context.get("execution_policy_sha256")
        output_contract = context.get("output_contract")
        trace_id = context.get("trace_id")
        if (
            not isinstance(requesting_agent, str)
            or not _AGENT.fullmatch(requesting_agent)
            or capabilities != ["python_unittest"]
            or not isinstance(policy_sha, str)
            or not _DIGEST.fullmatch(policy_sha)
            or output_contract != _expected_output_contract()
            or not isinstance(trace_id, str)
            or not 1 <= len(trace_id) <= 128
        ):
            raise WorkerServiceError("Worker Level 3 execution authority is invalid")
        limits = payload.get("limits")
        if not isinstance(limits, dict):
            raise WorkerServiceError("Worker Level 3 execution policy is invalid")
        expected_policy_sha = hashlib.sha256(_canonical(_expected_policy(limits))).hexdigest()
        if policy_sha != expected_policy_sha:
            raise WorkerServiceError("Worker Level 3 execution policy digest is invalid")

        legacy_payload = dict(payload)
        legacy_context = {
            name: context[name] for name in self.EXECUTION_CONTEXT_FIELDS
        }
        legacy_payload["execution_context"] = legacy_context
        legacy_body = _canonical(legacy_payload)
        timestamp = self._header(headers, "X-SPARKLE-Worker-Timestamp")
        synthetic_headers = dict(headers)
        synthetic_headers["X-SPARKLE-Worker-Signature"] = ExternalWorkerClient._signature(
            self.signing_key, timestamp, legacy_body,
        )
        job = super().validate(synthetic_headers, legacy_body)
        return replace(
            job,
            request_hash=hashlib.sha256(body).hexdigest(),
            execution_context=context,
        )


class Level3ExternalWorkerService(CancellableExternalWorkerService):
    """Cancellable worker service enforcing the complete Level-3 contract."""

    def __init__(self, config: WorkerConfig, **kwargs: Any):
        super().__init__(config, **kwargs)
        self.validator = Level3WorkerRequestValidator(
            self.signing_key,
            max_body_bytes=config.max_body_bytes,
            clock=self.clock,
        )

    def status(self) -> dict[str, Any]:
        return super().status() | {
            "level3_contract": LEVEL3_SERVICE_SCHEMA,
            "authorized_capabilities": ["python_unittest"],
            "requesting_agent_required": True,
            "execution_policy_digest_required": True,
            "output_contract_required": True,
            "trace_identity_required": True,
            "running_cancellation": True,
            "deployment_authorized": False,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sparkle-worker",
        description="SPARKLE Level-3 cancellable external worker",
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--diagnose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.diagnose:
        from sparkle.worker_diagnostics import WorkerIsolationDiagnostic
        report = WorkerIsolationDiagnostic().run()
        report["level_3_contract"] = LEVEL3_SERVICE_SCHEMA
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    config = WorkerConfig.load()
    service = Level3ExternalWorkerService(config)
    if args.check:
        value = service.status()
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0 if value["ready"] else 2
    server = build_cancellable_server(service)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def entrypoint(argv: list[str] | None = None) -> int:
    try:
        return main(argv)
    except (ValueError, SecretNotFoundError, WorkerServiceError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(entrypoint())
