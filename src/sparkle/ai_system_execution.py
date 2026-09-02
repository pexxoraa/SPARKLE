from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import stat
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from sparkle.ai_system_build import ControlledBuildArtifactWorkspace, ControlledBuildStore
from sparkle.ai_system_plan import AISystemImplementationPlanStore
from sparkle.ai_system_promotion import SourcePromotionStore, _digest
from sparkle.ai_system_runtime import RuntimeEvaluationStore
from sparkle.ai_system_source import SourceCandidateStore
from sparkle.artifacts import ArtifactManager
from sparkle.config import data_root
from sparkle.external_worker import ExternalWorkerError
from sparkle.external_worker import ExternalWorkerClient
from sparkle.storage import SQLiteStore, utc_now
from sparkle.trace import TraceStore


class ExecutionRejected(ValueError):
    """A bounded, content-free controlled-execution refusal."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ControlledExecutionStore(SQLiteStore):
    MAX_RECORDS = 1_000
    TERMINAL = {
        "verified", "rejected", "authorization_failure", "artifact_mismatch",
        "timeout", "worker_unavailable", "worker_authentication_failure",
        "protocol_failure", "execution_failure", "output_limit_failure",
        "isolation_failure", "result_integrity_failure", "cancelled",
    }

    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "data_environment" / "controlled_executions.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS controlled_execution_authorizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    authorization_id TEXT NOT NULL UNIQUE,
                    build_id TEXT NOT NULL, artifact_id INTEGER NOT NULL,
                    artifact_sha256 TEXT NOT NULL, promotion_id TEXT NOT NULL,
                    candidate_id INTEGER NOT NULL, plan_id INTEGER NOT NULL,
                    evaluation_id TEXT NOT NULL, execution_mode TEXT NOT NULL,
                    timeout_seconds INTEGER NOT NULL, max_output_chars INTEGER NOT NULL,
                    actor TEXT NOT NULL, source_origin TEXT NOT NULL,
                    status TEXT NOT NULL, approved_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL, consumed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS controlled_execution_exclusions (
                    artifact_id INTEGER PRIMARY KEY, artifact_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL, replacement_artifact_id INTEGER,
                    reason_sha256 TEXT NOT NULL, actor TEXT NOT NULL,
                    source_origin TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS controlled_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id TEXT NOT NULL UNIQUE,
                    execution_request_id TEXT NOT NULL UNIQUE,
                    contract_sha256 TEXT NOT NULL, authorization_id TEXT NOT NULL,
                    build_id TEXT NOT NULL, artifact_id INTEGER NOT NULL,
                    artifact_sha256 TEXT NOT NULL, promotion_id TEXT NOT NULL,
                    candidate_id INTEGER NOT NULL, plan_id INTEGER NOT NULL,
                    evaluation_id TEXT NOT NULL, execution_mode TEXT NOT NULL,
                    timeout_seconds INTEGER NOT NULL, max_output_chars INTEGER NOT NULL,
                    actor TEXT NOT NULL, source_origin TEXT NOT NULL,
                    status TEXT NOT NULL, trace_id TEXT NOT NULL,
                    worker_run_id INTEGER, worker_job_id TEXT, worker_id TEXT,
                    returncode INTEGER, timed_out INTEGER NOT NULL DEFAULT 0,
                    output_limited INTEGER NOT NULL DEFAULT 0,
                    output_sha256 TEXT, output_chars INTEGER NOT NULL DEFAULT 0,
                    result_digest TEXT, response_verified INTEGER NOT NULL DEFAULT 0,
                    isolation_verified INTEGER NOT NULL DEFAULT 0,
                    error_type TEXT, started_at TEXT, completed_at TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS controlled_execution_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, execution_id TEXT NOT NULL,
                    state TEXT NOT NULL, created_at TEXT NOT NULL
                );
            """)

    def approve(self, identities: dict[str, Any], *, actor: str, source_origin: str,
                timeout_seconds: int, max_output_chars: int, ttl_seconds: int) -> dict[str, Any]:
        now = datetime.now(UTC)
        authorization_id = f"SPK-EXEC-AUTH-{uuid.uuid4().hex.upper()}"
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO controlled_execution_authorizations(
                    authorization_id,build_id,artifact_id,artifact_sha256,promotion_id,
                    candidate_id,plan_id,evaluation_id,execution_mode,timeout_seconds,
                    max_output_chars,actor,source_origin,status,approved_at,expires_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'approved',?,?)
            """, (
                authorization_id, identities["build_id"], identities["artifact_id"],
                identities["artifact_sha256"], identities["promotion_id"],
                identities["candidate_id"], identities["plan_id"], identities["evaluation_id"],
                identities["execution_mode"], timeout_seconds, max_output_chars,
                actor, source_origin, now.isoformat(),
                (now + timedelta(seconds=ttl_seconds)).isoformat(),
            ))
            row = connection.execute(
                "SELECT * FROM controlled_execution_authorizations WHERE id=?",
                (cursor.lastrowid,),
            ).fetchone()
        return self._authorization(row)

    def authorization(self, authorization_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM controlled_execution_authorizations WHERE authorization_id=?",
                (authorization_id,),
            ).fetchone()
        if row is None:
            raise KeyError("Controlled execution authorization does not exist")
        return self._authorization(row)

    def create_or_find(self, contract: dict[str, Any], digest: str, trace_id: str) -> tuple[dict[str, Any], str]:
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM controlled_executions WHERE execution_request_id=?",
                (contract["execution_request_id"],),
            ).fetchone()
            if row is not None:
                return self._with_events(connection, row), "replay"
            execution_id = f"SPK-EXEC-{uuid.uuid4().hex.upper()}"
            cursor = connection.execute("""
                INSERT INTO controlled_executions(
                    execution_id,execution_request_id,contract_sha256,authorization_id,
                    build_id,artifact_id,artifact_sha256,promotion_id,candidate_id,plan_id,
                    evaluation_id,execution_mode,timeout_seconds,max_output_chars,actor,
                    source_origin,status,trace_id,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'requested',?,?,?)
            """, (
                execution_id, contract["execution_request_id"], digest,
                contract["authorization_id"], contract["build_id"], contract["artifact_id"],
                contract["artifact_sha256"], contract["promotion_id"], contract["candidate_id"],
                contract["plan_id"], contract["evaluation_id"], contract["execution_mode"],
                contract["timeout_seconds"], contract["max_output_chars"], contract["actor"],
                contract["source_origin"], trace_id, now, now,
            ))
            connection.execute(
                "INSERT INTO controlled_execution_events(execution_id,state,created_at) VALUES(?,'requested',?)",
                (execution_id, now),
            )
            row = connection.execute(
                "SELECT * FROM controlled_executions WHERE id=?", (cursor.lastrowid,),
            ).fetchone()
            return self._with_events(connection, row), "created"

    def consume_and_authorize(self, execution_id: str, authorization_id: str) -> dict[str, Any]:
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            used = connection.execute("""
                UPDATE controlled_execution_authorizations
                SET status='consumed',consumed_at=?
                WHERE authorization_id=? AND status='approved'
            """, (now, authorization_id))
            if used.rowcount != 1:
                raise ExecutionRejected("authorization_not_available")
            changed = connection.execute("""
                UPDATE controlled_executions SET status='authorized',updated_at=?
                WHERE execution_id=? AND status='requested'
            """, (now, execution_id))
            if changed.rowcount != 1:
                raise ExecutionRejected("execution_state_conflict")
            connection.execute(
                "INSERT INTO controlled_execution_events(execution_id,state,created_at) VALUES(?,'authorized',?)",
                (execution_id, now),
            )
            row = connection.execute(
                "SELECT * FROM controlled_executions WHERE execution_id=?", (execution_id,),
            ).fetchone()
            return self._with_events(connection, row)

    def transition(self, execution_id: str, expected: str, state: str, **values: Any) -> dict[str, Any]:
        allowed = self.TERMINAL | {"authorized", "queued", "submitted", "running", "completed"}
        fields = {
            "worker_run_id", "worker_job_id", "worker_id", "returncode", "timed_out",
            "output_limited", "output_sha256", "output_chars", "result_digest",
            "response_verified", "isolation_verified", "error_type", "started_at", "completed_at",
        }
        if state not in allowed or set(values) - fields:
            raise ValueError("Controlled execution lifecycle transition is invalid")
        now = utc_now()
        assignments, parameters = ["status=?", "updated_at=?"], [state, now]
        for name, value in values.items():
            assignments.append(f"{name}=?")
            parameters.append(value)
        if state in self.TERMINAL and "completed_at" not in values:
            assignments.append("completed_at=?")
            parameters.append(now)
        parameters.extend([execution_id, expected])
        with self.connect() as connection:
            cursor = connection.execute(
                f"UPDATE controlled_executions SET {','.join(assignments)} WHERE execution_id=? AND status=?",
                parameters,
            )
            if cursor.rowcount != 1:
                raise ValueError("Controlled execution lifecycle transition is invalid")
            connection.execute(
                "INSERT INTO controlled_execution_events(execution_id,state,created_at) VALUES(?,?,?)",
                (execution_id, state, now),
            )
            row = connection.execute(
                "SELECT * FROM controlled_executions WHERE execution_id=?", (execution_id,),
            ).fetchone()
            return self._with_events(connection, row)

    def exclude(self, artifact_id: int, artifact_sha256: str, *, status: str,
                replacement_artifact_id: int | None, reason_sha256: str,
                actor: str, source_origin: str) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute("""
                INSERT INTO controlled_execution_exclusions(
                    artifact_id,artifact_sha256,status,replacement_artifact_id,
                    reason_sha256,actor,source_origin,created_at
                ) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(artifact_id) DO NOTHING
            """, (artifact_id, artifact_sha256, status, replacement_artifact_id,
                  reason_sha256, actor, source_origin, utc_now()))
            row = connection.execute(
                "SELECT * FROM controlled_execution_exclusions WHERE artifact_id=?",
                (artifact_id,),
            ).fetchone()
        return dict(row)

    def exclusion(self, artifact_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM controlled_execution_exclusions WHERE artifact_id=?", (artifact_id,),
            ).fetchone()
        return dict(row) if row else None

    def by_execution_id(self, execution_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM controlled_executions WHERE execution_id=?", (execution_id,),
            ).fetchone()
            if row is None:
                raise KeyError("Controlled execution does not exist")
            return self._with_events(connection, row)

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM controlled_executions ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [self._execution(row) for row in rows]

    def list_authorizations(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM controlled_execution_authorizations ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [self._authorization(row) for row in rows]

    @staticmethod
    def _authorization(row: Any) -> dict[str, Any]:
        return {name: row[name] for name in row.keys()} | {"credentials_included": False}

    @staticmethod
    def _execution(row: Any) -> dict[str, Any]:
        value = {name: row[name] for name in row.keys() if name != "id"}
        for name in ("timed_out", "output_limited", "response_verified", "isolation_verified"):
            value[name] = bool(value[name])
        value.update({
            "executed": value["status"] in {"completed", "verified"},
            "verification_complete": value["status"] == "verified",
            "published": False, "deployed": False, "production_modified": False,
        })
        return value

    @classmethod
    def _with_events(cls, connection: Any, row: Any) -> dict[str, Any]:
        value = cls._execution(row)
        events = connection.execute(
            "SELECT state,created_at FROM controlled_execution_events WHERE execution_id=? ORDER BY id",
            (row["execution_id"],),
        ).fetchall()
        value["lifecycle"] = [dict(item) for item in events]
        return value


class ControlledArtifactExecutionWorkspace:
    """Verifies and extracts one immutable controlled-build ZIP without executing it."""

    def __init__(self, build_workspace: ControlledBuildArtifactWorkspace, root: Path | None = None):
        self.build_workspace = build_workspace
        self.root = (root or data_root() / "execution_environment" / "requests").resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def artifact_record(self, artifact_id: int) -> dict[str, Any]:
        with self.build_workspace.packager.connect() as connection:
            row = connection.execute("SELECT * FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
        if row is None:
            raise ExecutionRejected("artifact_missing")
        return ArtifactManager._public_artifact(row)

    def extract(self, build: dict[str, Any], execution_id: str) -> Path:
        if build["artifact_id"] is None:
            raise ExecutionRejected("artifact_identity_missing")
        artifact = self.artifact_record(build["artifact_id"])
        if any(artifact[name] != build[name] for name in (
            "artifact_id", "artifact_name", "artifact_sha256", "artifact_bytes", "file_count",
        )):
            raise ExecutionRejected("artifact_record_mismatch")
        target = self.build_workspace.packager.artifact_root.joinpath(
            *PurePosixPath(build["artifact_name"]).parts
        )
        archive = ArtifactManager._read_stable_regular(
            target, ArtifactManager.MAX_TOTAL_BYTES + 1_000_000,
        )
        if not hmac.compare_digest(hashlib.sha256(archive).hexdigest(), build["artifact_sha256"]):
            raise ExecutionRejected("artifact_digest_mismatch")
        destination = self.root / execution_id
        if destination.exists() or destination.is_symlink():
            raise ExecutionRejected("execution_workspace_conflict")
        destination.mkdir(mode=0o700)
        try:
            with zipfile.ZipFile(target) as bundle:
                infos = bundle.infolist()
                names = [item.filename for item in infos]
                if len(names) != len(set(names)) or ArtifactManager.MANIFEST_PATH not in names:
                    raise ExecutionRejected("artifact_archive_invalid")
                manifest = json.loads(bundle.read(ArtifactManager.MANIFEST_PATH).decode("utf-8"))
                if manifest != artifact["manifest"]:
                    raise ExecutionRejected("artifact_manifest_mismatch")
                expected = {item["path"]: item for item in manifest["files"]}
                if set(names) != set(expected) | {ArtifactManager.MANIFEST_PATH}:
                    raise ExecutionRejected("artifact_file_set_mismatch")
                total = 0
                for info in infos:
                    if info.filename == ArtifactManager.MANIFEST_PATH:
                        continue
                    path = PurePosixPath(info.filename)
                    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
                        raise ExecutionRejected("artifact_path_invalid")
                    mode = info.external_attr >> 16
                    if mode and not stat.S_ISREG(mode):
                        raise ExecutionRejected("artifact_entry_not_regular")
                    content = bundle.read(info)
                    total += len(content)
                    metadata = expected[info.filename]
                    if len(content) != metadata["bytes"] or hashlib.sha256(content).hexdigest() != metadata["sha256"]:
                        raise ExecutionRejected("artifact_entry_digest_mismatch")
                    content.decode("utf-8")
                    output = destination.joinpath(*path.parts)
                    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with output.open("xb") as handle:
                        handle.write(content)
                    output.chmod(0o400)
                if total != manifest["source_bytes"]:
                    raise ExecutionRejected("artifact_size_mismatch")
            # Close the packaging-to-submission race immediately before handoff.
            final = ArtifactManager._read_stable_regular(target, len(archive))
            if hashlib.sha256(final).hexdigest() != build["artifact_sha256"]:
                raise ExecutionRejected("artifact_changed_before_execution")
            return destination
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise


class ControlledExecutionService:
    PROTOCOL = "SPARKLE-AI-SYSTEM-CONTROLLED-EXECUTION/1"
    APPROVAL_TTL_SECONDS = 3_600
    ACTOR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{1,127}$")
    ORIGINS = {"cli", "authenticated_api", "operator"}
    REQUEST = re.compile(r"^SPK-EXEC-REQ-[A-F0-9]{32}$")
    MODES = {"python_unittest"}

    def __init__(self, builds: ControlledBuildStore, build_workspace: ControlledBuildArtifactWorkspace,
                 promotions: SourcePromotionStore, candidates: SourceCandidateStore,
                 plans: AISystemImplementationPlanStore, evaluations: RuntimeEvaluationStore,
                 traces: TraceStore, store: ControlledExecutionStore, worker: Any,
                 workspace: ControlledArtifactExecutionWorkspace | None = None):
        self.builds, self.promotions, self.candidates = builds, promotions, candidates
        self.plans, self.evaluations, self.traces = plans, evaluations, traces
        self.store, self.worker = store, worker
        self.workspace = workspace or ControlledArtifactExecutionWorkspace(build_workspace)

    @classmethod
    def _identity(cls, actor: Any, origin: Any) -> tuple[str, str]:
        if not isinstance(actor, str) or cls.ACTOR.fullmatch(actor) is None or origin not in cls.ORIGINS:
            raise ValueError("Controlled execution operator identity is invalid")
        return actor, origin

    def _authoritative(self, build_id: str) -> dict[str, Any]:
        try:
            build = self.builds.by_build_id(build_id)
        except KeyError as exc:
            raise ExecutionRejected("build_missing") from exc
        if build["status"] != "built" or not build["artifact_id"] or not _digest(build["artifact_sha256"]):
            raise ExecutionRejected("build_not_approved_artifact")
        try:
            promotion = self.promotions.by_promotion_id(build["promotion_id"])
            candidate = self.candidates.get(promotion["candidate_id"])
            plan = self.plans.get(promotion["plan_id"])
            evaluation = self.evaluations.by_evaluation_id(promotion["evaluation_id"])
        except (KeyError, ValueError) as exc:
            raise ExecutionRejected("authoritative_identity_missing") from exc
        if (
            promotion["status"] != "promoted"
            or promotion["destination_digest"] != build["promotion_digest"]
            or candidate["status"] != "approved"
            or candidate["candidate_sha256"] != promotion["candidate_sha256"]
            or plan["plan_id"] != promotion["plan_id"]
            or plan["plan_sha256"] != promotion["plan_sha256"]
            or evaluation["status"] != "evaluated"
            or not evaluation["response_verified"]
            or evaluation["candidate_id"] != candidate["candidate_id"]
        ):
            raise ExecutionRejected("authoritative_identity_mismatch")
        if self.store.exclusion(build["artifact_id"]):
            raise ExecutionRejected("artifact_invalidated_or_superseded")
        artifact = self.workspace.artifact_record(build["artifact_id"])
        if artifact["artifact_sha256"] != build["artifact_sha256"]:
            raise ExecutionRejected("artifact_record_mismatch")
        if (
            artifact["source_bytes"] > ExternalWorkerClient.MAX_TOTAL_BYTES
            or artifact["file_count"] > ExternalWorkerClient.MAX_FILES
            or any(
                item["bytes"] > ExternalWorkerClient.MAX_FILE_BYTES
                for item in artifact["manifest"]["files"]
            )
        ):
            raise ExecutionRejected("artifact_exceeds_execution_policy")
        return {
            "build_id": build_id, "artifact_id": build["artifact_id"],
            "artifact_sha256": build["artifact_sha256"],
            "promotion_id": promotion["promotion_id"], "candidate_id": candidate["candidate_id"],
            "plan_id": plan["plan_id"], "evaluation_id": evaluation["evaluation_id"],
            "execution_mode": "python_unittest", "build": build,
        }

    def approve(self, build_id: str, *, actor: str, source_origin: str, approved: bool,
                timeout_seconds: int = 10, max_output_chars: int = 12_000) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Controlled execution authorization requires explicit approval")
        actor, source_origin = self._identity(actor, source_origin)
        if not 1 <= timeout_seconds <= 60 or not 100 <= max_output_chars <= 12_000:
            raise ValueError("Controlled execution limits are invalid")
        return self.store.approve(
            self._authoritative(build_id), actor=actor, source_origin=source_origin,
            timeout_seconds=timeout_seconds, max_output_chars=max_output_chars,
            ttl_seconds=self.APPROVAL_TTL_SECONDS,
        )

    def validate(self, contract: dict[str, Any]) -> tuple[dict[str, Any], str]:
        fields = {
            "protocol_version", "execution_request_id", "authorization_id", "build_id",
            "artifact_id", "artifact_sha256", "promotion_id", "candidate_id", "plan_id",
            "evaluation_id", "execution_mode", "timeout_seconds", "max_output_chars",
            "actor", "source_origin",
        }
        if not isinstance(contract, dict) or set(contract) != fields:
            raise ValueError("Controlled execution contract fields are invalid")
        if contract["protocol_version"] != self.PROTOCOL or not self.REQUEST.fullmatch(contract["execution_request_id"]):
            raise ValueError("Controlled execution protocol identity is invalid")
        if contract["execution_mode"] not in self.MODES or not _digest(contract["artifact_sha256"]):
            raise ValueError("Controlled execution artifact or mode is invalid")
        for name in ("artifact_id", "candidate_id", "plan_id", "timeout_seconds", "max_output_chars"):
            if isinstance(contract[name], bool) or not isinstance(contract[name], int):
                raise ValueError("Controlled execution numeric identity is invalid")
        if not 1 <= contract["timeout_seconds"] <= 60 or not 100 <= contract["max_output_chars"] <= 12_000:
            raise ValueError("Controlled execution limits are invalid")
        self._identity(contract["actor"], contract["source_origin"])
        canonical = json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        if len(canonical) > 8_192:
            raise ValueError("Controlled execution contract exceeds its bound")
        return contract, hashlib.sha256(canonical).hexdigest()

    def request(self, contract: dict[str, Any], *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Controlled execution request requires explicit approval")
        contract, digest = self.validate(contract)
        trace_id, started = self.traces.start(
            input_source="ai_system_controlled_execution", agent="system",
            content_identifiers=[contract["build_id"], contract["execution_request_id"]],
            processing_stage="execution_requested",
        )
        self.traces.finish(trace_id, started, status="success", agent="system", model=None,
                           provider=None, result_summary="Controlled execution request recorded")
        record, disposition = self.store.create_or_find(contract, digest, trace_id)
        if disposition == "replay":
            if record["contract_sha256"] != digest:
                raise ExecutionRejected("execution_request_replay_conflict")
            return record
        execution_id = record["execution_id"]
        workspace: Path | None = None
        try:
            identities = self._authoritative(contract["build_id"])
            for name in ("artifact_id", "artifact_sha256", "promotion_id", "candidate_id", "plan_id", "evaluation_id", "execution_mode"):
                if contract[name] != identities[name]:
                    raise ExecutionRejected(f"{name}_mismatch")
            try:
                authorization = self.store.authorization(contract["authorization_id"])
            except KeyError as exc:
                raise ExecutionRejected("authorization_missing") from exc
            if datetime.fromisoformat(authorization["expires_at"]) <= datetime.now(UTC):
                raise ExecutionRejected("authorization_stale")
            for name in ("build_id", "artifact_id", "artifact_sha256", "promotion_id", "candidate_id", "plan_id", "evaluation_id", "execution_mode", "timeout_seconds", "max_output_chars", "actor", "source_origin"):
                if authorization[name] != contract[name]:
                    raise ExecutionRejected("authorization_mismatch")
            self.store.consume_and_authorize(execution_id, authorization["authorization_id"])
            self.store.transition(execution_id, "authorized", "queued")
            workspace = self.workspace.extract(identities["build"], execution_id)
            # Invalidation after queueing is checked at the last local boundary.
            if self.store.exclusion(contract["artifact_id"]):
                raise ExecutionRejected("artifact_invalidated_after_request")
            self.store.transition(execution_id, "queued", "submitted")
            self.store.transition(execution_id, "submitted", "running", started_at=utc_now())
            context = {name: contract[name] for name in (
                "execution_request_id", "artifact_id", "artifact_sha256", "build_id",
                "promotion_id", "candidate_id", "plan_id", "evaluation_id",
                "authorization_id", "execution_mode",
            )}
            context["execution_id"] = execution_id
            result = self.worker.run_controlled_execution(
                f"execution_{execution_id.removeprefix('SPK-EXEC-')[:16].lower()}",
                workspace, execution_context=context,
                timeout_seconds=contract["timeout_seconds"],
                max_output_chars=contract["max_output_chars"],
            )
            common = {
                "worker_run_id": result.get("external_test_run_id"),
                "worker_job_id": result.get("job_id"), "worker_id": result.get("worker_id"),
                "returncode": result.get("returncode"), "timed_out": int(bool(result.get("timed_out"))),
                "output_limited": int(bool(result.get("output_limited"))),
                "output_sha256": result.get("output_sha256"),
                "output_chars": len(result.get("output", "")),
                "result_digest": result.get("result_digest"),
                "response_verified": int(bool(result.get("response_verified"))),
                "isolation_verified": int(bool(result.get("isolation_verified"))),
            }
            if result.get("execution_context") != context or not result.get("result_digest"):
                final = self.store.transition(execution_id, "running", "result_integrity_failure", **common, error_type="ResultIdentityMismatch")
                self._trace(final)
                return final
            if result.get("timed_out"):
                final = self.store.transition(execution_id, "running", "timeout", **common, error_type="WorkerTimeout")
                self._trace(final)
                return final
            if result.get("output_limited"):
                final = self.store.transition(execution_id, "running", "output_limit_failure", **common, error_type="OutputLimitExceeded")
                self._trace(final)
                return final
            if not result.get("response_verified"):
                final = self.store.transition(execution_id, "running", "protocol_failure", **common, error_type="UnverifiedResponse")
                self._trace(final)
                return final
            if result.get("status") != "passed" or result.get("returncode") != 0:
                final = self.store.transition(execution_id, "running", "execution_failure", **common, error_type="WorkerExecutionFailed")
                self._trace(final)
                return final
            self.store.transition(execution_id, "running", "completed", **common)
            final = self.store.transition(execution_id, "completed", "verified")
            self._trace(final)
            return final
        except ExecutionRejected as exc:
            current = self.store.by_execution_id(execution_id)
            state = "artifact_mismatch" if "artifact" in exc.reason else "authorization_failure" if "authorization" in exc.reason else "rejected"
            if current["status"] not in self.store.TERMINAL:
                current = self.store.transition(execution_id, current["status"], state, error_type=exc.reason)
            self._trace(current)
            return current
        except ExternalWorkerError as exc:
            message = str(exc).lower()
            state = (
                "worker_authentication_failure"
                if any(word in message for word in ("signature", "authentication"))
                else "result_integrity_failure"
                if any(word in message for word in ("result digest", "output digest", "execution identity", "result identity"))
                else "worker_unavailable"
                if any(word in message for word in ("disabled", "configured", "transport"))
                else "protocol_failure"
            )
            current = self.store.transition(execution_id, "running", state, error_type=type(exc).__name__)
            self._trace(current)
            return current
        except Exception as exc:
            current = self.store.by_execution_id(execution_id)
            if current["status"] not in self.store.TERMINAL:
                current = self.store.transition(execution_id, current["status"], "execution_failure", error_type=type(exc).__name__)
            self._trace(current)
            return current
        finally:
            if workspace is not None:
                shutil.rmtree(workspace, ignore_errors=True)

    def cancel(self, execution_id: str, *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Controlled execution cancellation requires explicit approval")
        current = self.store.by_execution_id(execution_id)
        if current["status"] not in {"requested", "authorized", "queued"}:
            raise ExecutionRejected("execution_not_cancellable")
        return self.store.transition(execution_id, current["status"], "cancelled", error_type="OperatorCancelled")

    def exclude_artifact(self, artifact_id: int, *, status: str, reason: str,
                         actor: str, source_origin: str, approved: bool,
                         replacement_artifact_id: int | None = None) -> dict[str, Any]:
        if approved is not True or status not in {"invalidated", "superseded"}:
            raise ValueError("Controlled artifact exclusion is invalid")
        actor, source_origin = self._identity(actor, source_origin)
        artifact = self.workspace.artifact_record(artifact_id)
        if status == "superseded" and (not replacement_artifact_id or replacement_artifact_id == artifact_id):
            raise ValueError("Artifact supersession requires a distinct replacement")
        if replacement_artifact_id:
            self.workspace.artifact_record(replacement_artifact_id)
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500:
            raise ValueError("Controlled artifact exclusion reason is invalid")
        return self.store.exclude(
            artifact_id, artifact["artifact_sha256"], status=status,
            replacement_artifact_id=replacement_artifact_id,
            reason_sha256=hashlib.sha256(reason.strip().encode()).hexdigest(),
            actor=actor, source_origin=source_origin,
        )

    def _trace(self, result: dict[str, Any]) -> None:
        self.traces.annotate_lifecycle(
            result["trace_id"], processing_stage=result["status"],
            transformations=["immutable_artifact_verification", "controlled_worker_submission", "authenticated_result_verification"],
            data_accessed=["build_environment"], data_created=[f"controlled_execution:{result['execution_id']}"],
            storage_destinations=["data_environment", "trace_environment", "execution_environment"],
            execution_metadata={
                "execution_id": result["execution_id"], "artifact_sha256": result["artifact_sha256"],
                "response_verified": result["response_verified"], "isolation_verified": result["isolation_verified"],
                "verification_complete": result["verification_complete"], "published": False,
                "deployed": False, "production_modified": False,
            }, result_summary=f"Controlled execution {result['status']}",
        )
