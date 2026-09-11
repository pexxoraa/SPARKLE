from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from sparkle.ai_system_execution import ControlledExecutionService
from sparkle.external_worker import ExternalWorkerClient
from sparkle.secrets import SecretNotFoundError
from sparkle.storage import SQLiteStore, utc_now
from sparkle.worker_cancellation import (
    CancellableExternalWorkerService,
    build_cancellable_server,
)
from sparkle.worker_service import (
    WorkerConfig,
    WorkerHTTPResponse,
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

        # Reuse the mature legacy structural/file/limit validator by validating a
        # signed projection containing only its known fields, then restore the full
        # signed Level-3 context and the original request hash for replay identity.
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


class Level3WorkerAuditStore(SQLiteStore):
    """Content-free worker-side lifecycle evidence for controlled jobs."""

    TERMINAL = {"completed", "failed", "cancelled", "rejected"}

    def __init__(self, path: Path):
        super().__init__(path)
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS level3_worker_jobs(
                    job_id TEXT PRIMARY KEY,
                    request_hash TEXT NOT NULL,
                    execution_id TEXT NOT NULL,
                    requesting_agent TEXT NOT NULL,
                    state TEXT NOT NULL,
                    failure_stage TEXT,
                    response_sha256 TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS level3_worker_events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_level3_worker_events_job
                    ON level3_worker_events(job_id,id);
            """)

    def begin(self, job) -> str:
        context = job.execution_context or {}
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT request_hash,state FROM level3_worker_jobs WHERE job_id=?",
                (job.job_id,),
            ).fetchone()
            if row is not None:
                if row["request_hash"] != job.request_hash:
                    raise WorkerServiceError("Worker Level 3 audit identity conflict")
                return str(row["state"])
            connection.execute("""
                INSERT INTO level3_worker_jobs(
                    job_id,request_hash,execution_id,requesting_agent,state,
                    failure_stage,response_sha256,created_at,updated_at
                ) VALUES(?,?,?,?,? ,NULL,NULL,?,?)
            """, (
                job.job_id, job.request_hash, context["execution_id"],
                context["requesting_agent"], "authorized", now, now,
            ))
            connection.execute("""
                INSERT INTO level3_worker_events(job_id,state,stage,created_at)
                VALUES(?,?,?,?)
            """, (job.job_id, "authorized", "authorization", now))
        return "authorized"

    def transition(
        self, job_id: str, state: str, stage: str, *,
        failure_stage: str | None = None, response_body: bytes | None = None,
    ) -> None:
        now = utc_now()
        response_sha = hashlib.sha256(response_body).hexdigest() if response_body else None
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state FROM level3_worker_jobs WHERE job_id=?", (job_id,),
            ).fetchone()
            if row is None:
                return
            if row["state"] in self.TERMINAL:
                return
            connection.execute("""
                UPDATE level3_worker_jobs
                SET state=?,failure_stage=?,response_sha256=COALESCE(?,response_sha256),updated_at=?
                WHERE job_id=?
            """, (state, failure_stage, response_sha, now, job_id))
            connection.execute("""
                INSERT INTO level3_worker_events(job_id,state,stage,created_at)
                VALUES(?,?,?,?)
            """, (job_id, state, stage, now))

    def cancel_execution(self, execution_id: str) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("""
                SELECT job_id FROM level3_worker_jobs
                WHERE execution_id=? AND state NOT IN ('completed','failed','cancelled','rejected')
            """, (execution_id,)).fetchall()
            for row in rows:
                connection.execute("""
                    UPDATE level3_worker_jobs SET state='cancelled',failure_stage='cancellation',updated_at=?
                    WHERE job_id=?
                """, (now, row["job_id"]))
                connection.execute("""
                    INSERT INTO level3_worker_events(job_id,state,stage,created_at)
                    VALUES(?,'cancelled','cancellation',?)
                """, (row["job_id"], now))

    def status(self) -> dict[str, Any]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT state,COUNT(*) AS count FROM level3_worker_jobs GROUP BY state
            """).fetchall()
            recent = connection.execute("""
                SELECT job_id,execution_id,requesting_agent,state,failure_stage,
                       response_sha256,updated_at
                FROM level3_worker_jobs ORDER BY updated_at DESC LIMIT 20
            """).fetchall()
        counts = {row["state"]: int(row["count"]) for row in rows}
        return {
            "states": counts,
            "active": sum(counts.get(name, 0) for name in ("authorized", "queued", "running")),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0) + counts.get("rejected", 0),
            "cancelled": counts.get("cancelled", 0),
            "recent": [dict(row) for row in recent],
        }


class Level3ExternalWorkerService(CancellableExternalWorkerService):
    """Cancellable worker service enforcing the complete Level-3 contract."""

    def __init__(self, config: WorkerConfig, **kwargs: Any):
        super().__init__(config, **kwargs)
        self.validator = Level3WorkerRequestValidator(
            self.signing_key,
            max_body_bytes=config.max_body_bytes,
            clock=self.clock,
        )
        self.level3_audit = Level3WorkerAuditStore(config.state_dir / "level3_jobs.sqlite3")

    def handle_job(self, headers: Mapping[str, str], body: bytes) -> WorkerHTTPResponse:
        # Validate once up front only to create content-free Level-3 lifecycle evidence.
        # The parent validates again before executing and remains authoritative for
        # replay, capacity, isolation and signed-response semantics.
        job = self.validator.validate(headers, body)
        controlled = job.execution_context is not None
        if not controlled:
            return super().handle_job(headers, body)
        prior = self.level3_audit.begin(job)
        if prior not in self.level3_audit.TERMINAL:
            self.level3_audit.transition(job.job_id, "queued", "queueing")
            self.level3_audit.transition(job.job_id, "running", "execution")
        try:
            response = super().handle_job(headers, body)
            value = json.loads(response.body.decode("utf-8"))
            status = value.get("status")
            if status == "cancelled":
                self.level3_audit.transition(
                    job.job_id, "cancelled", "cancellation", response_body=response.body,
                )
            elif status == "passed" and value.get("returncode") == 0:
                self.level3_audit.transition(
                    job.job_id, "completed", "completion", response_body=response.body,
                )
            else:
                stage = "resource_limits" if value.get("timed_out") or value.get("output_limited") else "execution"
                self.level3_audit.transition(
                    job.job_id, "failed", stage,
                    failure_stage=stage, response_body=response.body,
                )
            return response
        except Exception as exc:
            stage = (
                "authorization" if isinstance(exc, WorkerServiceError)
                else "execution"
            )
            self.level3_audit.transition(
                job.job_id, "failed", stage, failure_stage=stage,
            )
            raise

    def handle_cancel(self, headers: Mapping[str, str], body: bytes) -> WorkerHTTPResponse:
        response = super().handle_cancel(headers, body)
        try:
            value = json.loads(response.body.decode("utf-8"))
            execution_id = value.get("execution_id")
            if isinstance(execution_id, str):
                self.level3_audit.cancel_execution(execution_id)
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        return response

    def status(self) -> dict[str, Any]:
        return super().status() | {
            "level3_contract": LEVEL3_SERVICE_SCHEMA,
            "authorized_capabilities": ["python_unittest"],
            "requesting_agent_required": True,
            "execution_policy_digest_required": True,
            "output_contract_required": True,
            "trace_identity_required": True,
            "running_cancellation": True,
            "level3_jobs": self.level3_audit.status(),
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
        report.update({
            "level_3_contract": LEVEL3_SERVICE_SCHEMA,
            "level_3_status": "SOFTWARE_READY_EXTERNAL_ACCEPTANCE_REQUIRED",
            "level_3_verified": False,
            "deployment_started": False,
        })
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
