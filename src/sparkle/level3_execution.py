from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sparkle.ai_system_execution import ExecutionRejected
from sparkle.external_worker import ExternalWorkerError
from sparkle.storage import utc_now


class Level3ExecutionMixin:
    """Adds the Level-3 contract/lifecycle to controlled execution.

    The existing controlled-execution record remains the immutable compatibility
    audit. This ledger adds the host-handoff contract and the explicit Level-3
    lifecycle without granting the model any approval authority.
    """

    LEVEL3_SCHEMA = "SPARKLE-LEVEL3-EXECUTION/1"
    OUTPUT_SCHEMA = "SPARKLE-LEVEL3-OUTPUT/1"
    AUTHORIZED_CAPABILITIES = ("python_unittest",)
    AGENT = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
    LEVEL3_TERMINAL = {
        "completed", "rejected", "cancelled", "timed_out", "failed",
        "policy_violation", "infrastructure_failure",
    }

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._initialize_level3()

    def _initialize_level3(self) -> None:
        with self.store.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS level3_execution_contracts (
                    execution_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    requesting_agent TEXT NOT NULL,
                    authorized_capabilities_json TEXT NOT NULL,
                    execution_policy_sha256 TEXT NOT NULL,
                    output_contract_json TEXT NOT NULL,
                    output_contract_sha256 TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    failure_stage TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS level3_execution_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_level3_execution_events_execution
                    ON level3_execution_events(execution_id,id);
            """)

    @staticmethod
    def _canonical(value: Any) -> bytes:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")

    @classmethod
    def output_contract(cls) -> dict[str, Any]:
        return {
            "schema": cls.OUTPUT_SCHEMA,
            "capability": "python_unittest",
            "required_status": "passed",
            "required_returncode": 0,
            "timed_out": False,
            "output_limited": False,
            "response_verified": True,
            "isolation_verified": True,
        }

    def _level3_create(
        self, execution_id: str, trace_id: str, requesting_agent: str,
        contract: dict[str, Any],
    ) -> None:
        if not isinstance(requesting_agent, str) or not self.AGENT.fullmatch(requesting_agent):
            raise ValueError("Level 3 requesting agent identity is invalid")
        policy_sha = hashlib.sha256(self._canonical(contract["execution_policy"])).hexdigest()
        output_contract = self.output_contract()
        output_json = self._canonical(output_contract).decode("utf-8")
        output_sha = hashlib.sha256(output_json.encode("utf-8")).hexdigest()
        now = utc_now()
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT execution_id FROM level3_execution_contracts WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
            if existing is not None:
                return
            connection.execute("""
                INSERT INTO level3_execution_contracts(
                    execution_id,schema_version,requesting_agent,
                    authorized_capabilities_json,execution_policy_sha256,
                    output_contract_json,output_contract_sha256,trace_id,state,
                    failure_stage,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,NULL,?,?)
            """, (
                execution_id, self.LEVEL3_SCHEMA, requesting_agent,
                json.dumps(list(self.AUTHORIZED_CAPABILITIES), separators=(",", ":")),
                policy_sha, output_json, output_sha, trace_id, "requested", now, now,
            ))
            connection.execute("""
                INSERT INTO level3_execution_events(execution_id,state,stage,created_at)
                VALUES(?,?,?,?)
            """, (execution_id, "requested", "request", now))

    def _level3_transition(
        self, execution_id: str, state: str, stage: str, *, failure_stage: str | None = None,
    ) -> None:
        allowed = {
            "requested": {"authorized", "rejected", "policy_violation", "cancelled"},
            "authorized": {"queued", "rejected", "policy_violation", "cancelled"},
            "queued": {"running", "rejected", "policy_violation", "cancelled", "infrastructure_failure"},
            "running": {"collecting", "timed_out", "failed", "policy_violation", "infrastructure_failure", "cancelled"},
            "collecting": {"validated", "timed_out", "failed", "policy_violation", "infrastructure_failure", "cancelled"},
            "validated": {"completed", "policy_violation", "failed"},
        }
        now = utc_now()
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state FROM level3_execution_contracts WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Level 3 execution contract does not exist")
            current = row["state"]
            if current == state:
                return
            if current in self.LEVEL3_TERMINAL or state not in allowed.get(current, set()):
                raise ValueError("Level 3 lifecycle transition is invalid")
            changed = connection.execute("""
                UPDATE level3_execution_contracts
                SET state=?,failure_stage=?,updated_at=?
                WHERE execution_id=? AND state=?
            """, (state, failure_stage, now, execution_id, current))
            if changed.rowcount != 1:
                raise ValueError("Level 3 lifecycle transition is stale")
            connection.execute("""
                INSERT INTO level3_execution_events(execution_id,state,stage,created_at)
                VALUES(?,?,?,?)
            """, (execution_id, state, stage, now))

    def _level3_force_terminal(
        self, execution_id: str, state: str, stage: str,
    ) -> None:
        if state not in self.LEVEL3_TERMINAL:
            raise ValueError("Level 3 terminal state is invalid")
        now = utc_now()
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state FROM level3_execution_contracts WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
            if row is None or row["state"] in self.LEVEL3_TERMINAL:
                return
            connection.execute("""
                UPDATE level3_execution_contracts
                SET state=?,failure_stage=?,updated_at=? WHERE execution_id=?
            """, (state, stage, now, execution_id))
            connection.execute("""
                INSERT INTO level3_execution_events(execution_id,state,stage,created_at)
                VALUES(?,?,?,?)
            """, (execution_id, state, stage, now))

    def _level3_context(
        self, contract: dict[str, Any], execution_id: str, trace_id: str,
        requesting_agent: str,
    ) -> dict[str, Any]:
        context = {name: contract[name] for name in (
            "execution_request_id", "artifact_id", "artifact_sha256", "build_id",
            "promotion_id", "candidate_id", "plan_id", "evaluation_id",
            "authorization_id", "execution_mode",
        )}
        context.update({
            "execution_id": execution_id,
            "requesting_agent": requesting_agent,
            "authorized_capabilities": list(self.AUTHORIZED_CAPABILITIES),
            "execution_policy_sha256": hashlib.sha256(
                self._canonical(contract["execution_policy"])
            ).hexdigest(),
            "output_contract": self.output_contract(),
            "trace_id": trace_id,
        })
        return context

    def _level3_record(self, execution_id: str) -> dict[str, Any] | None:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT * FROM level3_execution_contracts WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
            if row is None:
                return None
            events = connection.execute("""
                SELECT state,stage,created_at FROM level3_execution_events
                WHERE execution_id=? ORDER BY id
            """, (execution_id,)).fetchall()
        return {
            "schema": row["schema_version"],
            "execution_id": row["execution_id"],
            "requesting_agent": row["requesting_agent"],
            "authorized_capabilities": json.loads(row["authorized_capabilities_json"]),
            "execution_policy_sha256": row["execution_policy_sha256"],
            "output_contract": json.loads(row["output_contract_json"]),
            "output_contract_sha256": row["output_contract_sha256"],
            "trace_id": row["trace_id"],
            "state": row["state"],
            "failure_stage": row["failure_stage"],
            "events": [dict(item) for item in events],
            "deployment_authorized": False,
        }

    def _enrich_level3(self, record: dict[str, Any]) -> dict[str, Any]:
        value = dict(record)
        level3 = self._level3_record(record["execution_id"])
        if level3 is not None:
            value["level3"] = level3
        return value

    def request(
        self, contract: dict[str, Any], *, approved: bool,
        requesting_agent: str = "system",
    ) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Controlled execution request requires explicit approval")
        if not isinstance(requesting_agent, str) or not self.AGENT.fullmatch(requesting_agent):
            raise ValueError("Level 3 requesting agent identity is invalid")
        contract, digest = self.validate(contract)
        trace_id, started = self.traces.start(
            input_source="ai_system_controlled_execution", agent=requesting_agent,
            content_identifiers=[contract["build_id"], contract["execution_request_id"]],
            processing_stage="execution_requested",
        )
        self.traces.finish(
            trace_id, started, status="success", agent=requesting_agent, model=None,
            provider=None, result_summary="Controlled execution request recorded",
        )
        record, disposition = self.store.create_or_find(contract, digest, trace_id)
        if disposition == "replay":
            if record["contract_sha256"] != digest:
                raise ExecutionRejected("execution_request_replay_conflict")
            return self._enrich_level3(record)
        execution_id = record["execution_id"]
        self._level3_create(execution_id, trace_id, requesting_agent, contract)
        workspace: Path | None = None
        stage = "authorization"
        try:
            identities = self._authoritative(contract["build_id"])
            for name in (
                "artifact_id", "artifact_sha256", "promotion_id", "candidate_id",
                "plan_id", "evaluation_id", "execution_mode",
            ):
                if contract[name] != identities[name]:
                    raise ExecutionRejected(f"{name}_mismatch")
            try:
                authorization = self.store.authorization(contract["authorization_id"])
            except KeyError as exc:
                raise ExecutionRejected("authorization_missing") from exc
            if datetime.fromisoformat(authorization["expires_at"]) <= datetime.now(UTC):
                raise ExecutionRejected("authorization_stale")
            for name in (
                "build_id", "artifact_id", "artifact_sha256", "promotion_id",
                "candidate_id", "plan_id", "evaluation_id", "execution_mode",
                "timeout_seconds", "max_output_chars", "actor", "source_origin",
            ):
                if authorization[name] != contract[name]:
                    raise ExecutionRejected("authorization_mismatch")
            self.store.consume_and_authorize(execution_id, authorization["authorization_id"])
            self._level3_transition(execution_id, "authorized", "authorization")

            stage = "queueing"
            self.store.transition(execution_id, "authorized", "queued")
            workspace = self.workspace.extract(identities["build"], execution_id)
            if self.store.exclusion(contract["artifact_id"]):
                raise ExecutionRejected("artifact_invalidated_after_request")
            self._level3_transition(execution_id, "queued", "queueing")

            stage = "execution"
            self.store.transition(execution_id, "queued", "submitted")
            self.store.transition(execution_id, "submitted", "running", started_at=utc_now())
            self._level3_transition(execution_id, "running", "execution")
            context = self._level3_context(
                contract, execution_id, trace_id, requesting_agent,
            )
            result = self.worker.run_controlled_execution(
                f"execution_{execution_id.removeprefix('SPK-EXEC-')[:16].lower()}",
                workspace, execution_context=context,
                timeout_seconds=contract["timeout_seconds"],
                max_output_chars=contract["max_output_chars"],
            )

            stage = "artifact_collection"
            self._level3_transition(execution_id, "collecting", stage)
            common = {
                "worker_run_id": result.get("external_test_run_id"),
                "worker_job_id": result.get("job_id"),
                "worker_id": result.get("worker_id"),
                "returncode": result.get("returncode"),
                "timed_out": int(bool(result.get("timed_out"))),
                "output_limited": int(bool(result.get("output_limited"))),
                "output_sha256": result.get("output_sha256"),
                "output_chars": len(result.get("output", "")),
                "result_digest": result.get("result_digest"),
                "response_verified": int(bool(result.get("response_verified"))),
                "isolation_verified": int(bool(result.get("isolation_verified"))),
            }
            if result.get("job_id") and hasattr(self.worker, "connect"):
                with self.worker.connect() as connection:
                    connection.execute(
                        "UPDATE external_worker_runs SET isolation_verified=? WHERE job_id=?",
                        (int(bool(result.get("isolation_verified"))), result["job_id"]),
                    )

            if result.get("execution_context") != context or not result.get("result_digest"):
                final = self.store.transition(
                    execution_id, "running", "result_integrity_failure", **common,
                    error_type="ResultIdentityMismatch",
                )
                self._level3_force_terminal(execution_id, "policy_violation", "validation")
                self._trace(final)
                return self._enrich_level3(final)
            if result.get("timed_out"):
                final = self.store.transition(
                    execution_id, "running", "timeout", **common,
                    error_type="WorkerTimeout",
                )
                self._level3_force_terminal(execution_id, "timed_out", "resource_limits")
                self._trace(final)
                return self._enrich_level3(final)
            if result.get("output_limited"):
                final = self.store.transition(
                    execution_id, "running", "output_limit_failure", **common,
                    error_type="OutputLimitExceeded",
                )
                self._level3_force_terminal(execution_id, "policy_violation", "resource_limits")
                self._trace(final)
                return self._enrich_level3(final)
            if not result.get("response_verified"):
                final = self.store.transition(
                    execution_id, "running", "protocol_failure", **common,
                    error_type="UnverifiedResponse",
                )
                self._level3_force_terminal(execution_id, "policy_violation", "transport")
                self._trace(final)
                return self._enrich_level3(final)
            if not result.get("isolation_verified"):
                final = self.store.transition(
                    execution_id, "running", "isolation_failure", **common,
                    error_type="IsolationNotVerified",
                )
                self._level3_force_terminal(execution_id, "policy_violation", "isolation")
                self._trace(final)
                return self._enrich_level3(final)
            if result.get("status") != "passed" or result.get("returncode") != 0:
                final = self.store.transition(
                    execution_id, "running", "execution_failure", **common,
                    error_type="WorkerExecutionFailed",
                )
                self._level3_force_terminal(execution_id, "failed", "execution")
                self._trace(final)
                return self._enrich_level3(final)

            stage = "validation"
            expected_output = self.output_contract()
            observations = {
                "required_status": result.get("status"),
                "required_returncode": result.get("returncode"),
                "timed_out": bool(result.get("timed_out")),
                "output_limited": bool(result.get("output_limited")),
                "response_verified": bool(result.get("response_verified")),
                "isolation_verified": bool(result.get("isolation_verified")),
            }
            if any(observations[name] != expected_output[name] for name in observations):
                final = self.store.transition(
                    execution_id, "running", "result_integrity_failure", **common,
                    error_type="OutputContractMismatch",
                )
                self._level3_force_terminal(execution_id, "policy_violation", "validation")
                self._trace(final)
                return self._enrich_level3(final)
            self._level3_transition(execution_id, "validated", "validation")
            self.store.transition(execution_id, "running", "completed", **common)
            final = self.store.transition(execution_id, "completed", "verified")
            self._level3_transition(execution_id, "completed", "completion")
            self._trace(final)
            return self._enrich_level3(final)
        except ExecutionRejected as exc:
            current = self.store.by_execution_id(execution_id)
            legacy_state = (
                "artifact_mismatch" if "artifact" in exc.reason
                else "authorization_failure" if "authorization" in exc.reason
                else "rejected"
            )
            if current["status"] not in self.store.TERMINAL:
                current = self.store.transition(
                    execution_id, current["status"], legacy_state,
                    error_type=exc.reason,
                )
            self._level3_force_terminal(
                execution_id,
                "policy_violation" if legacy_state != "rejected" else "rejected",
                stage,
            )
            self._trace(current)
            return self._enrich_level3(current)
        except ExternalWorkerError as exc:
            current = self.store.by_execution_id(execution_id)
            message = str(exc).lower()
            legacy_state = (
                "worker_authentication_failure"
                if any(word in message for word in (
                    "signature", "authentication", "worker identity", "not authorized",
                ))
                else "result_integrity_failure"
                if any(word in message for word in (
                    "result digest", "output digest", "execution identity", "result identity",
                ))
                else "worker_unavailable"
                if any(word in message for word in (
                    "disabled", "configured", "transport", "unavailable",
                ))
                else "protocol_failure"
            )
            if current["status"] not in self.store.TERMINAL:
                current = self.store.transition(
                    execution_id, current["status"], legacy_state,
                    error_type=type(exc).__name__,
                )
            self._level3_force_terminal(
                execution_id,
                "infrastructure_failure" if legacy_state == "worker_unavailable" else "policy_violation",
                "transport",
            )
            self._trace(current)
            return self._enrich_level3(current)
        except Exception as exc:
            current = self.store.by_execution_id(execution_id)
            if current["status"] not in self.store.TERMINAL:
                current = self.store.transition(
                    execution_id, current["status"], "execution_failure",
                    error_type=type(exc).__name__,
                )
            self._level3_force_terminal(execution_id, "failed", stage)
            self._trace(current)
            return self._enrich_level3(current)
        finally:
            if workspace is not None:
                shutil.rmtree(workspace, ignore_errors=True)

    def inspect(self, execution_id: str) -> dict[str, Any]:
        return self._enrich_level3(super().inspect(execution_id))

    def result(self, execution_id: str) -> dict[str, Any]:
        value = super().result(execution_id)
        level3 = self._level3_record(execution_id)
        if level3 is not None:
            value["level3"] = level3
        return value

    def level3_status(self) -> dict[str, Any]:
        with self.store.connect() as connection:
            rows = connection.execute("""
                SELECT state,COUNT(*) AS count FROM level3_execution_contracts
                GROUP BY state ORDER BY state
            """).fetchall()
        counts = {row["state"]: int(row["count"]) for row in rows}
        return {
            "schema": self.LEVEL3_SCHEMA,
            "states": counts,
            "active": sum(counts.get(name, 0) for name in (
                "requested", "authorized", "queued", "running", "collecting", "validated",
            )),
            "completed": counts.get("completed", 0),
            "failed": sum(counts.get(name, 0) for name in (
                "rejected", "cancelled", "timed_out", "failed",
                "policy_violation", "infrastructure_failure",
            )),
            "authorized_capabilities": list(self.AUTHORIZED_CAPABILITIES),
            "output_contract_schema": self.OUTPUT_SCHEMA,
            "deployment_authorized": False,
        }
