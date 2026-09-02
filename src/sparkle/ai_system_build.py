from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sparkle.ai_system_promotion import (
    ControlledPromotionWorkspace,
    PromotionRejected,
    SourcePromotionStore,
    _digest,
)
from sparkle.ai_system_source import SourceCandidateStore
from sparkle.artifacts import ArtifactManager
from sparkle.config import data_root
from sparkle.storage import SQLiteStore, utc_now
from sparkle.trace import TraceStore


class BuildRejected(ValueError):
    """A bounded, content-free controlled-build policy refusal."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ControlledBuildStore(SQLiteStore):
    """Promotion-bound approvals and build evidence without source content."""

    MAX_RECORDS = 1_000

    def __init__(self, path: Path | None = None):
        super().__init__(
            path or data_root() / "data_environment" / "controlled_builds.sqlite3"
        )
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS controlled_build_approvals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    approval_id TEXT NOT NULL UNIQUE,
                    promotion_id TEXT NOT NULL,
                    promotion_digest TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    source_origin TEXT NOT NULL,
                    status TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS controlled_builds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    build_id TEXT NOT NULL UNIQUE,
                    request_id TEXT NOT NULL UNIQUE,
                    contract_sha256 TEXT NOT NULL,
                    promotion_id TEXT NOT NULL,
                    promotion_digest TEXT NOT NULL,
                    approval_id TEXT NOT NULL,
                    build_kind TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    source_origin TEXT NOT NULL,
                    status TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    artifact_id INTEGER,
                    artifact_name TEXT,
                    artifact_sha256 TEXT,
                    artifact_bytes INTEGER,
                    file_count INTEGER,
                    error_type TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS controlled_build_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    build_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_controlled_builds_promotion
                ON controlled_builds(promotion_id, id);
            """)
            columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(controlled_builds)"
                ).fetchall()
            }
            if "artifact_id" not in columns:
                connection.execute(
                    "ALTER TABLE controlled_builds ADD COLUMN artifact_id INTEGER"
                )

    def approve(
        self,
        *,
        promotion_id: str,
        promotion_digest: str,
        actor: str,
        source_origin: str,
        ttl_seconds: int,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        with self.connect() as connection:
            existing = connection.execute("""
                SELECT * FROM controlled_build_approvals
                WHERE promotion_id=? AND promotion_digest=? AND actor=?
                  AND source_origin=? AND status='approved'
                ORDER BY id DESC LIMIT 1
            """, (promotion_id, promotion_digest, actor, source_origin)).fetchone()
            if existing is not None:
                if datetime.fromisoformat(existing["expires_at"]) > now:
                    return self._approval(existing)
                connection.execute("""
                    UPDATE controlled_build_approvals SET status='expired'
                    WHERE id=? AND status='approved'
                """, (existing["id"],))
            approval_id = f"SPK-BUILD-APP-{uuid.uuid4().hex.upper()}"
            cursor = connection.execute("""
                INSERT INTO controlled_build_approvals(
                    approval_id,promotion_id,promotion_digest,actor,source_origin,
                    status,approved_at,expires_at
                ) VALUES(?,?,?,?,?,'approved',?,?)
            """, (
                approval_id, promotion_id, promotion_digest, actor, source_origin,
                now.isoformat(), (now + timedelta(seconds=ttl_seconds)).isoformat(),
            ))
            self._prune(connection)
            row = connection.execute(
                "SELECT * FROM controlled_build_approvals WHERE id=?",
                (cursor.lastrowid,),
            ).fetchone()
        return self._approval(row)

    def approval(self, approval_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM controlled_build_approvals WHERE approval_id=?",
                (approval_id,),
            ).fetchone()
        if row is None:
            raise KeyError("Controlled build approval does not exist")
        return self._approval(row)

    def expire_approval(self, approval_id: str) -> None:
        with self.connect() as connection:
            connection.execute("""
                UPDATE controlled_build_approvals SET status='expired'
                WHERE approval_id=? AND status='approved'
            """, (approval_id,))

    def create_or_find(
        self, contract: dict[str, Any], digest: str, trace_id: str,
    ) -> tuple[dict[str, Any], str]:
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            replay = connection.execute(
                "SELECT * FROM controlled_builds WHERE request_id=?",
                (contract["request_id"],),
            ).fetchone()
            if replay is not None:
                return self._with_events(connection, replay), "replay"
            existing = connection.execute("""
                SELECT * FROM controlled_builds
                WHERE promotion_id=? AND status IN ('requested','building','built')
                ORDER BY id DESC LIMIT 1
            """, (contract["promotion_id"],)).fetchone()
            if existing is not None:
                return self._with_events(connection, existing), "promotion_conflict"
            build_id = f"SPK-BUILD-{uuid.uuid4().hex.upper()}"
            cursor = connection.execute("""
                INSERT INTO controlled_builds(
                    build_id,request_id,contract_sha256,promotion_id,
                    promotion_digest,approval_id,build_kind,actor,source_origin,
                    status,trace_id,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,'requested',?,?,?)
            """, (
                build_id, contract["request_id"], digest,
                contract["promotion_id"], contract["promotion_digest"],
                contract["approval_id"], contract["build_kind"],
                contract["actor"], contract["source_origin"], trace_id, now, now,
            ))
            connection.execute("""
                INSERT INTO controlled_build_events(build_id,state,created_at)
                VALUES(?,'requested',?)
            """, (build_id, now))
            self._prune(connection)
            row = connection.execute(
                "SELECT * FROM controlled_builds WHERE id=?", (cursor.lastrowid,),
            ).fetchone()
            return self._with_events(connection, row), "created"

    def begin(self, build_id: str, approval_id: str) -> dict[str, Any]:
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            approval = connection.execute("""
                UPDATE controlled_build_approvals
                SET status='consumed',consumed_at=?
                WHERE approval_id=? AND status='approved'
            """, (now, approval_id))
            if approval.rowcount != 1:
                raise BuildRejected("approval_not_available")
            cursor = connection.execute("""
                UPDATE controlled_builds SET status='building',started_at=?,updated_at=?
                WHERE build_id=? AND status='requested'
            """, (now, now, build_id))
            if cursor.rowcount != 1:
                raise ValueError("Controlled build lifecycle transition is invalid")
            connection.execute("""
                INSERT INTO controlled_build_events(build_id,state,created_at)
                VALUES(?,'building',?)
            """, (build_id, now))
            row = connection.execute(
                "SELECT * FROM controlled_builds WHERE build_id=?", (build_id,),
            ).fetchone()
            return self._with_events(connection, row)

    def transition(
        self, build_id: str, expected: str, state: str, **values: Any,
    ) -> dict[str, Any]:
        if state not in {"rejected", "failed", "built"}:
            raise ValueError("Controlled build state is invalid")
        fields = {
            "artifact_name", "artifact_sha256", "artifact_bytes", "file_count",
            "artifact_id",
            "error_type", "completed_at",
        }
        if set(values) - fields:
            raise ValueError("Controlled build result fields are invalid")
        now = utc_now()
        assignments = ["status=?", "updated_at=?"]
        parameters: list[Any] = [state, now]
        for key, value in values.items():
            assignments.append(f"{key}=?")
            parameters.append(value)
        if "completed_at" not in values:
            assignments.append("completed_at=?")
            parameters.append(now)
        parameters.extend([build_id, expected])
        with self.connect() as connection:
            cursor = connection.execute(
                f"UPDATE controlled_builds SET {','.join(assignments)} "
                "WHERE build_id=? AND status=?", parameters,
            )
            if cursor.rowcount == 1:
                connection.execute("""
                    INSERT INTO controlled_build_events(build_id,state,created_at)
                    VALUES(?,?,?)
                """, (build_id, state, now))
            row = connection.execute(
                "SELECT * FROM controlled_builds WHERE build_id=?", (build_id,),
            ).fetchone()
            if cursor.rowcount != 1 or row is None:
                raise ValueError("Controlled build lifecycle transition is invalid")
            return self._with_events(connection, row)

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM controlled_builds ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [self._build(row) for row in rows]

    def by_build_id(self, build_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM controlled_builds WHERE build_id=?", (build_id,),
            ).fetchone()
            if row is None:
                raise KeyError("Controlled build does not exist")
            return self._with_events(connection, row)

    def list_approvals(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT * FROM controlled_build_approvals ORDER BY id DESC LIMIT ?
            """, (max(1, min(limit, 100)),)).fetchall()
        return [self._approval(row) for row in rows]

    def _prune(self, connection: Any) -> None:
        connection.execute("""
            DELETE FROM controlled_builds WHERE id NOT IN (
                SELECT id FROM controlled_builds ORDER BY id DESC LIMIT ?
            )
        """, (self.MAX_RECORDS,))
        connection.execute("""
            DELETE FROM controlled_build_events WHERE build_id NOT IN (
                SELECT build_id FROM controlled_builds
            )
        """)
        connection.execute("""
            DELETE FROM controlled_build_approvals WHERE id NOT IN (
                SELECT id FROM controlled_build_approvals ORDER BY id DESC LIMIT ?
            )
        """, (self.MAX_RECORDS,))

    @staticmethod
    def _approval(row: Any) -> dict[str, Any]:
        return {
            "approval_id": row["approval_id"],
            "promotion_id": row["promotion_id"],
            "promotion_digest": row["promotion_digest"],
            "actor": row["actor"],
            "source_origin": row["source_origin"],
            "status": row["status"],
            "approved_at": row["approved_at"],
            "expires_at": row["expires_at"],
            "consumed_at": row["consumed_at"],
            "credentials_included": False,
        }

    @staticmethod
    def _build(row: Any) -> dict[str, Any]:
        return {
            "build_id": row["build_id"],
            "request_id": row["request_id"],
            "contract_sha256": row["contract_sha256"],
            "promotion_id": row["promotion_id"],
            "promotion_digest": row["promotion_digest"],
            "approval_id": row["approval_id"],
            "build_kind": row["build_kind"],
            "actor": row["actor"],
            "source_origin": row["source_origin"],
            "status": row["status"],
            "trace_id": row["trace_id"],
            "artifact_id": row["artifact_id"],
            "artifact_name": row["artifact_name"],
            "artifact_sha256": row["artifact_sha256"],
            "artifact_bytes": row["artifact_bytes"],
            "file_count": row["file_count"],
            "error_type": row["error_type"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "source_executed": False,
            "published": False,
            "deployed": False,
        }

    @classmethod
    def _with_events(cls, connection: Any, row: Any) -> dict[str, Any]:
        value = cls._build(row)
        events = connection.execute("""
            SELECT state,created_at FROM controlled_build_events
            WHERE build_id=? ORDER BY id
        """, (row["build_id"],)).fetchall()
        value["lifecycle"] = [dict(event) for event in events]
        return value


class ControlledBuildArtifactWorkspace:
    """Deterministically packages only a verified promotion destination."""

    def __init__(
        self,
        promotion_workspace: ControlledPromotionWorkspace,
        *,
        artifact_root: Path | None = None,
        package_store_path: Path | None = None,
    ):
        root = data_root()
        self.promotion_workspace = promotion_workspace
        self.packager = ArtifactManager(
            workspace_root=promotion_workspace.root,
            artifact_root=artifact_root or root / "build_environment" / "artifacts",
            path=package_store_path
            or root / "data_environment" / "controlled_build_artifacts.sqlite3",
        )

    def build(
        self,
        *,
        destination: str,
        expected_digest: str,
        metadata_paths: list[str],
    ) -> dict[str, Any]:
        try:
            files = self.promotion_workspace.load_destination(destination)
        except PromotionRejected as exc:
            raise BuildRejected(exc.reason) from exc
        actual_digest = self.promotion_workspace.digest(files, metadata_paths)
        if actual_digest != expected_digest:
            raise BuildRejected("promotion_digest_mismatch")
        project_name = destination.removeprefix("staging/")
        try:
            artifact = self.packager.package(project_name)
        except (ValueError, RuntimeError, OSError) as exc:
            raise BuildRejected("artifact_build_failed") from exc
        target = self.packager.artifact_root.joinpath(*Path(artifact["artifact_name"]).parts)
        metadata_by_path = {
            item["path"]: item for item in artifact["manifest"]["files"]
        }
        artifact_metadata = [
            metadata_by_path[path] for path in metadata_paths
            if path in metadata_by_path
        ]
        artifact_source_digest = hashlib.sha256(json.dumps(
            artifact_metadata, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        if (
            set(metadata_by_path) != set(metadata_paths)
            or len(artifact_metadata) != len(metadata_paths)
            or artifact_source_digest != expected_digest
        ):
            self._remove_untrusted_artifact(artifact, target)
            raise BuildRejected("artifact_source_mismatch")
        if target.is_symlink() or not target.is_file():
            raise BuildRejected("artifact_missing")
        archive_digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if archive_digest != artifact["artifact_sha256"]:
            raise BuildRejected("artifact_digest_mismatch")
        return artifact

    def _remove_untrusted_artifact(
        self, artifact: dict[str, Any], target: Path,
    ) -> None:
        if artifact.get("reused") is not True:
            target.unlink(missing_ok=True)
            with self.packager.connect() as connection:
                connection.execute(
                    "DELETE FROM artifacts WHERE id=?", (artifact["artifact_id"],),
                )


class ControlledBuildService:
    PROTOCOL = "SPARKLE-AI-SYSTEM-CONTROLLED-BUILD/1"
    APPROVAL_TTL_SECONDS = 86_400
    ACTOR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{1,127}$")
    ORIGINS = {"cli", "authenticated_api", "operator"}
    REQUEST = re.compile(r"^SPK-BUILD-REQ-[A-F0-9]{32}$")
    BUILD_KINDS = {"source_bundle"}

    def __init__(
        self,
        promotions: SourcePromotionStore,
        candidates: SourceCandidateStore,
        traces: TraceStore,
        store: ControlledBuildStore,
        workspace: ControlledBuildArtifactWorkspace,
    ):
        self.promotions = promotions
        self.candidates = candidates
        self.traces = traces
        self.store = store
        self.workspace = workspace

    @classmethod
    def _identity(cls, actor: Any, source_origin: Any) -> tuple[str, str]:
        if not isinstance(actor, str) or cls.ACTOR.fullmatch(actor) is None:
            raise ValueError("Controlled build actor is invalid")
        if source_origin not in cls.ORIGINS:
            raise ValueError("Controlled build origin is invalid")
        return actor, source_origin

    def _authoritative(
        self, promotion_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
        try:
            promotion = self.promotions.by_promotion_id(promotion_id)
        except (KeyError, ValueError) as exc:
            raise BuildRejected("promotion_missing") from exc
        if promotion["status"] != "promoted":
            raise BuildRejected("promotion_not_completed")
        if (
            not _digest(promotion["source_digest"])
            or promotion["source_digest"] != promotion["destination_digest"]
            or not promotion["artifact_id"]
        ):
            raise BuildRejected("promotion_evidence_invalid")
        try:
            candidate = self.candidates.get(promotion["candidate_id"])
        except (KeyError, ValueError) as exc:
            raise BuildRejected("candidate_missing") from exc
        if (
            candidate["candidate_sha256"] != promotion["destination_digest"]
            or candidate["status"] != "approved"
        ):
            raise BuildRejected("promotion_candidate_mismatch")
        paths = [item["path"] for item in candidate["files"]]
        try:
            files = self.workspace.promotion_workspace.load_destination(
                promotion["destination"]
            )
        except PromotionRejected as exc:
            raise BuildRejected(exc.reason) from exc
        if (
            set(files) != set(paths)
            or self.workspace.promotion_workspace.digest(files, paths)
            != promotion["destination_digest"]
        ):
            raise BuildRejected("promotion_content_tampered")
        return promotion, candidate, paths

    def approve(
        self,
        promotion_id: str,
        *,
        actor: str,
        source_origin: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Controlled build approval requires explicit approval")
        actor, source_origin = self._identity(actor, source_origin)
        promotion, _, _ = self._authoritative(promotion_id)
        return self.store.approve(
            promotion_id=promotion_id,
            promotion_digest=promotion["destination_digest"],
            actor=actor,
            source_origin=source_origin,
            ttl_seconds=self.APPROVAL_TTL_SECONDS,
        )

    def validate(self, contract: dict[str, Any]) -> tuple[dict[str, Any], str]:
        fields = {
            "protocol_version", "request_id", "promotion_id",
            "promotion_digest", "approval_id", "build_kind", "actor",
            "source_origin",
        }
        if not isinstance(contract, dict) or set(contract) != fields:
            raise ValueError("Controlled build contract fields are invalid")
        if contract["protocol_version"] != self.PROTOCOL:
            raise ValueError("Controlled build protocol is invalid")
        if not isinstance(contract["request_id"], str) or self.REQUEST.fullmatch(contract["request_id"]) is None:
            raise ValueError("Controlled build request ID is invalid")
        if not isinstance(contract["promotion_id"], str) or not contract["promotion_id"].startswith("SPK-PROMO-"):
            raise ValueError("Controlled build promotion ID is invalid")
        if not _digest(contract["promotion_digest"]):
            raise ValueError("Controlled build promotion digest is invalid")
        if not isinstance(contract["approval_id"], str) or not contract["approval_id"].startswith("SPK-BUILD-APP-"):
            raise ValueError("Controlled build approval ID is invalid")
        if contract["build_kind"] not in self.BUILD_KINDS:
            raise ValueError("Controlled build kind is invalid")
        self._identity(contract["actor"], contract["source_origin"])
        canonical = json.dumps(
            contract, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        if len(canonical.encode("utf-8")) > 4_096:
            raise ValueError("Controlled build contract exceeds its size bound")
        return contract, hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def request(self, contract: dict[str, Any], *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Controlled build request requires explicit approval")
        contract, contract_digest = self.validate(contract)
        trace_id, started = self.traces.start(
            input_source="ai_system_controlled_build",
            agent="system",
            content_identifiers=[contract["promotion_id"], contract["request_id"]],
            processing_stage="build_requested",
            execution_metadata={
                "promotion_id": contract["promotion_id"],
                "approval_id": contract["approval_id"],
                "build_kind": contract["build_kind"],
            },
        )
        self.traces.finish(
            trace_id, started, status="success", agent="system", model=None,
            provider=None, processing_stage="build_requested",
            result_summary="Controlled build request recorded",
        )
        record, disposition = self.store.create_or_find(
            contract, contract_digest, trace_id,
        )
        if disposition == "replay":
            if record["contract_sha256"] != contract_digest:
                raise BuildRejected("request_replay_conflict")
            return record
        if disposition == "promotion_conflict":
            if (
                record["promotion_digest"] == contract["promotion_digest"]
                and record["build_kind"] == contract["build_kind"]
                and record["actor"] == contract["actor"]
                and record["source_origin"] == contract["source_origin"]
            ):
                return record
            raise BuildRejected("promotion_build_conflict")
        build_id = record["build_id"]
        try:
            promotion, _, paths = self._authoritative(contract["promotion_id"])
            if contract["promotion_digest"] != promotion["destination_digest"]:
                raise BuildRejected("contract_identity_mismatch")
            try:
                approval = self.store.approval(contract["approval_id"])
            except KeyError as exc:
                raise BuildRejected("approval_missing") from exc
            if datetime.fromisoformat(approval["expires_at"]) <= datetime.now(UTC):
                self.store.expire_approval(approval["approval_id"])
                raise BuildRejected("approval_stale")
            if not (
                approval["status"] == "approved"
                and approval["promotion_id"] == promotion["promotion_id"]
                and approval["promotion_digest"] == promotion["destination_digest"]
                and approval["actor"] == contract["actor"]
                and approval["source_origin"] == contract["source_origin"]
                and approval["approved_at"] >= promotion["completed_at"]
            ):
                raise BuildRejected("approval_mismatch")
            self.store.begin(build_id, approval["approval_id"])
            artifact = self.workspace.build(
                destination=promotion["destination"],
                expected_digest=promotion["destination_digest"],
                metadata_paths=paths,
            )
            result = self.store.transition(
                build_id, "building", "built",
                artifact_name=artifact["artifact_name"],
                artifact_id=artifact["artifact_id"],
                artifact_sha256=artifact["artifact_sha256"],
                artifact_bytes=artifact["artifact_bytes"],
                file_count=artifact["file_count"],
            )
            self._trace_result(result, "build_completed", "success")
            return result
        except BuildRejected as exc:
            current = self._safe_transition(build_id, exc.reason, "rejected")
            self._trace_result(current, "build_rejected", "error")
            return current
        except Exception as exc:
            current = self._safe_transition(build_id, type(exc).__name__, "failed")
            self._trace_result(current, "build_failed", "error")
            return current

    def eligibility(self, *, limit: int = 50) -> list[dict[str, Any]]:
        approvals = self.store.list_approvals(limit=100)
        builds = self.store.list(limit=100)
        result: list[dict[str, Any]] = []
        for promotion in self.promotions.list(limit=max(1, min(limit, 100))):
            approval = next((
                item for item in approvals
                if item["promotion_id"] == promotion["promotion_id"]
            ), None)
            build = next((
                item for item in builds
                if item["promotion_id"] == promotion["promotion_id"]
            ), None)
            if promotion["status"] != "promoted":
                state, reason = "not_eligible", "promotion_not_completed"
            elif build is not None:
                state, reason = build["status"], build["error_type"]
            elif approval is None:
                state, reason = "awaiting_approval", None
            elif approval["status"] == "approved":
                state, reason = "approval_recorded", None
            else:
                state, reason = "not_eligible", f"approval_{approval['status']}"
            result.append({
                "promotion_id": promotion["promotion_id"],
                "promotion_digest": promotion["destination_digest"],
                "state": state,
                "reason": reason,
                "source_executed": False,
                "published": False,
                "deployed": False,
            })
        return result

    def _safe_transition(
        self, build_id: str, error_type: str, state: str,
    ) -> dict[str, Any]:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT status FROM controlled_builds WHERE build_id=?", (build_id,),
            ).fetchone()
        if row is None:
            raise KeyError("Controlled build does not exist")
        if row["status"] in {"rejected", "failed", "built"}:
            return next(
                item for item in self.store.list(limit=100)
                if item["build_id"] == build_id
            )
        return self.store.transition(
            build_id, row["status"], state, error_type=error_type,
        )

    def _trace_result(self, result: dict[str, Any], stage: str, status: str) -> None:
        trace_id, started = self.traces.start(
            input_source="ai_system_controlled_build",
            agent="system",
            content_identifiers=[result["build_id"], result["promotion_id"]],
            processing_stage=stage,
            execution_metadata={
                "build_id": result["build_id"],
                "promotion_id": result["promotion_id"],
                "artifact_sha256": result["artifact_sha256"],
                "source_executed": False,
                "published": False,
                "deployed": False,
            },
        )
        self.traces.finish(
            trace_id, started, status=status, agent="system", model=None,
            provider=None, processing_stage=stage,
            result_summary=f"Controlled build {result['status']}",
        )
