from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from sparkle.ai_system_plan import AISystemImplementationPlanStore
from sparkle.ai_system_runtime import RuntimeEvaluationStore
from sparkle.ai_system_source import SourceCandidateStore, SourceCandidateWorkspace
from sparkle.builders import WorkspaceManager
from sparkle.config import data_root
from sparkle.storage import SQLiteStore, utc_now
from sparkle.trace import TraceStore


def _digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


class PromotionRejected(ValueError):
    """A bounded, content-free promotion-policy refusal."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class SourcePromotionStore(SQLiteStore):
    """Promotion approvals, exclusions, and lifecycle evidence without source."""

    MAX_RECORDS = 1_000

    def __init__(self, path: Path | None = None):
        super().__init__(
            path or data_root() / "data_environment" / "source_promotions.sqlite3"
        )
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS source_promotion_approvals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    approval_id TEXT NOT NULL UNIQUE,
                    candidate_id INTEGER NOT NULL,
                    candidate_sha256 TEXT NOT NULL,
                    plan_id INTEGER NOT NULL,
                    plan_sha256 TEXT NOT NULL,
                    evaluation_id TEXT NOT NULL,
                    evaluation_contract_sha256 TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    source_origin TEXT NOT NULL,
                    status TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS source_promotion_exclusions (
                    candidate_id INTEGER PRIMARY KEY,
                    status TEXT NOT NULL,
                    replacement_candidate_id INTEGER,
                    reason_sha256 TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    source_origin TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS source_promotions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    promotion_id TEXT NOT NULL UNIQUE,
                    request_id TEXT NOT NULL UNIQUE,
                    contract_sha256 TEXT NOT NULL,
                    candidate_id INTEGER NOT NULL,
                    candidate_sha256 TEXT NOT NULL,
                    plan_id INTEGER NOT NULL,
                    plan_sha256 TEXT NOT NULL,
                    evaluation_id TEXT NOT NULL,
                    approval_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    source_origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    status TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    source_digest TEXT,
                    destination_digest TEXT,
                    artifact_id TEXT,
                    error_type TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS source_promotion_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    promotion_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_source_promotions_candidate
                ON source_promotions(candidate_id, id);
            """)

    def approve(
        self,
        *,
        candidate: dict[str, Any],
        evaluation: dict[str, Any],
        actor: str,
        source_origin: str,
        ttl_seconds: int,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        approved_at = now.isoformat()
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
        with self.connect() as connection:
            existing = connection.execute("""
                SELECT * FROM source_promotion_approvals
                WHERE candidate_id=? AND evaluation_id=? AND actor=?
                  AND source_origin=? AND status='approved'
                ORDER BY id DESC LIMIT 1
            """, (
                candidate["candidate_id"], evaluation["evaluation_id"], actor,
                source_origin,
            )).fetchone()
            if existing is not None:
                if datetime.fromisoformat(existing["expires_at"]) > now:
                    return self._approval(existing)
                connection.execute("""
                    UPDATE source_promotion_approvals SET status='expired'
                    WHERE id=? AND status='approved'
                """, (existing["id"],))
            approval_id = f"SPK-PROMO-APP-{uuid.uuid4().hex.upper()}"
            cursor = connection.execute("""
                INSERT INTO source_promotion_approvals(
                    approval_id,candidate_id,candidate_sha256,plan_id,
                    plan_sha256,evaluation_id,evaluation_contract_sha256,
                    actor,source_origin,status,approved_at,expires_at
                ) VALUES(?,?,?,?,?,?,?,?,?,'approved',?,?)
            """, (
                approval_id,
                candidate["candidate_id"],
                candidate["candidate_sha256"],
                candidate["plan_id"],
                candidate["plan_sha256"],
                evaluation["evaluation_id"],
                evaluation["contract_sha256"],
                actor,
                source_origin,
                approved_at,
                expires_at,
            ))
            self._prune(connection)
            row = connection.execute(
                "SELECT * FROM source_promotion_approvals WHERE id=?",
                (cursor.lastrowid,),
            ).fetchone()
        return self._approval(row)

    def approval(self, approval_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM source_promotion_approvals WHERE approval_id=?",
                (approval_id,),
            ).fetchone()
        if row is None:
            raise KeyError("Source promotion approval does not exist")
        return self._approval(row)

    def expire_approval(self, approval_id: str) -> None:
        with self.connect() as connection:
            connection.execute("""
                UPDATE source_promotion_approvals SET status='expired'
                WHERE approval_id=? AND status='approved'
            """, (approval_id,))

    def exclude(
        self,
        candidate_id: int,
        *,
        status: str,
        reason_sha256: str,
        actor: str,
        source_origin: str,
        replacement_candidate_id: int | None = None,
    ) -> dict[str, Any]:
        if status not in {"invalidated", "superseded"} or not _digest(reason_sha256):
            raise ValueError("Source promotion exclusion is invalid")
        with self.connect() as connection:
            connection.execute("""
                INSERT INTO source_promotion_exclusions(
                    candidate_id,status,replacement_candidate_id,reason_sha256,
                    actor,source_origin,created_at
                ) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(candidate_id) DO NOTHING
            """, (
                candidate_id, status, replacement_candidate_id, reason_sha256,
                actor, source_origin, utc_now(),
            ))
            row = connection.execute(
                "SELECT * FROM source_promotion_exclusions WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
        return dict(row)

    def exclusion(self, candidate_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM source_promotion_exclusions WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def create_or_find(
        self, contract: dict[str, Any], digest: str, trace_id: str,
    ) -> tuple[dict[str, Any], str]:
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            replay = connection.execute(
                "SELECT * FROM source_promotions WHERE request_id=?",
                (contract["request_id"],),
            ).fetchone()
            if replay is not None:
                return self._promotion_with_events(connection, replay), "replay"
            existing = connection.execute("""
                SELECT * FROM source_promotions
                WHERE candidate_id=? AND status IN ('requested','promoting','promoted')
                ORDER BY id DESC LIMIT 1
            """, (contract["candidate_id"],)).fetchone()
            if existing is not None:
                return self._promotion_with_events(connection, existing), "candidate_conflict"
            promotion_id = f"SPK-PROMO-{uuid.uuid4().hex.upper()}"
            cursor = connection.execute("""
                INSERT INTO source_promotions(
                    promotion_id,request_id,contract_sha256,candidate_id,
                    candidate_sha256,plan_id,plan_sha256,evaluation_id,
                    approval_id,actor,source_origin,destination,status,trace_id,
                    created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'requested',?,?,?)
            """, (
                promotion_id, contract["request_id"], digest,
                contract["candidate_id"], contract["candidate_sha256"],
                contract["plan_id"], contract["plan_sha256"],
                contract["evaluation_id"], contract["approval_id"],
                contract["actor"], contract["source_origin"],
                contract["destination"], trace_id, now, now,
            ))
            connection.execute("""
                INSERT INTO source_promotion_events(promotion_id,state,created_at)
                VALUES(?,'requested',?)
            """, (promotion_id, now))
            self._prune(connection)
            row = connection.execute(
                "SELECT * FROM source_promotions WHERE id=?", (cursor.lastrowid,),
            ).fetchone()
            return self._promotion_with_events(connection, row), "created"

    def begin_promotion(self, promotion_id: str, approval_id: str) -> dict[str, Any]:
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            approval = connection.execute("""
                UPDATE source_promotion_approvals
                SET status='consumed',consumed_at=?
                WHERE approval_id=? AND status='approved'
            """, (now, approval_id))
            if approval.rowcount != 1:
                raise PromotionRejected("approval_not_available")
            cursor = connection.execute("""
                UPDATE source_promotions SET status='promoting',started_at=?,updated_at=?
                WHERE promotion_id=? AND status='requested'
            """, (now, now, promotion_id))
            if cursor.rowcount != 1:
                raise ValueError("Source promotion lifecycle transition is invalid")
            connection.execute("""
                INSERT INTO source_promotion_events(promotion_id,state,created_at)
                VALUES(?,'promoting',?)
            """, (promotion_id, now))
            row = connection.execute(
                "SELECT * FROM source_promotions WHERE promotion_id=?",
                (promotion_id,),
            ).fetchone()
            return self._promotion_with_events(connection, row)

    def transition(
        self,
        promotion_id: str,
        expected: str,
        state: str,
        **values: Any,
    ) -> dict[str, Any]:
        if state not in {"rejected", "failed", "promoted"}:
            raise ValueError("Source promotion state is invalid")
        fields = {
            "source_digest", "destination_digest", "artifact_id", "error_type",
            "completed_at",
        }
        if set(values) - fields:
            raise ValueError("Source promotion result fields are invalid")
        now = utc_now()
        assignments = ["status=?", "updated_at=?"]
        parameters: list[Any] = [state, now]
        for key, value in values.items():
            assignments.append(f"{key}=?")
            parameters.append(value)
        if state in {"rejected", "failed", "promoted"} and "completed_at" not in values:
            assignments.append("completed_at=?")
            parameters.append(now)
        parameters.extend([promotion_id, expected])
        with self.connect() as connection:
            cursor = connection.execute(
                f"UPDATE source_promotions SET {','.join(assignments)} "
                "WHERE promotion_id=? AND status=?",
                parameters,
            )
            if cursor.rowcount == 1:
                connection.execute("""
                    INSERT INTO source_promotion_events(promotion_id,state,created_at)
                    VALUES(?,?,?)
                """, (promotion_id, state, now))
            row = connection.execute(
                "SELECT * FROM source_promotions WHERE promotion_id=?",
                (promotion_id,),
            ).fetchone()
            if cursor.rowcount != 1 or row is None:
                raise ValueError("Source promotion lifecycle transition is invalid")
            return self._promotion_with_events(connection, row)

    def by_promotion_id(self, promotion_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM source_promotions WHERE promotion_id=?",
                (promotion_id,),
            ).fetchone()
            if row is None:
                raise KeyError("Source promotion does not exist")
            return self._promotion_with_events(connection, row)

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT * FROM source_promotions ORDER BY id DESC LIMIT ?
            """, (max(1, min(limit, 100)),)).fetchall()
        return [self._promotion(row) for row in rows]

    def list_approvals(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT * FROM source_promotion_approvals ORDER BY id DESC LIMIT ?
            """, (max(1, min(limit, 100)),)).fetchall()
        return [self._approval(row) for row in rows]

    def _prune(self, connection: Any) -> None:
        connection.execute("""
            DELETE FROM source_promotions WHERE id NOT IN (
                SELECT id FROM source_promotions ORDER BY id DESC LIMIT ?
            )
        """, (self.MAX_RECORDS,))
        connection.execute("""
            DELETE FROM source_promotion_events WHERE promotion_id NOT IN (
                SELECT promotion_id FROM source_promotions
            )
        """)
        connection.execute("""
            DELETE FROM source_promotion_approvals WHERE id NOT IN (
                SELECT id FROM source_promotion_approvals ORDER BY id DESC LIMIT ?
            )
        """, (self.MAX_RECORDS,))

    @staticmethod
    def _approval(row: Any) -> dict[str, Any]:
        return {
            "approval_id": row["approval_id"],
            "candidate_id": row["candidate_id"],
            "candidate_sha256": row["candidate_sha256"],
            "plan_id": row["plan_id"],
            "plan_sha256": row["plan_sha256"],
            "evaluation_id": row["evaluation_id"],
            "evaluation_contract_sha256": row["evaluation_contract_sha256"],
            "actor": row["actor"],
            "source_origin": row["source_origin"],
            "status": row["status"],
            "approved_at": row["approved_at"],
            "expires_at": row["expires_at"],
            "consumed_at": row["consumed_at"],
            "credentials_included": False,
        }

    @staticmethod
    def _promotion(row: Any) -> dict[str, Any]:
        return {
            "promotion_id": row["promotion_id"],
            "request_id": row["request_id"],
            "contract_sha256": row["contract_sha256"],
            "candidate_id": row["candidate_id"],
            "candidate_sha256": row["candidate_sha256"],
            "plan_id": row["plan_id"],
            "plan_sha256": row["plan_sha256"],
            "evaluation_id": row["evaluation_id"],
            "approval_id": row["approval_id"],
            "actor": row["actor"],
            "source_origin": row["source_origin"],
            "destination": row["destination"],
            "status": row["status"],
            "trace_id": row["trace_id"],
            "source_digest": row["source_digest"],
            "destination_digest": row["destination_digest"],
            "artifact_id": row["artifact_id"],
            "error_type": row["error_type"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "built": False,
            "executed": False,
            "packaged": False,
            "published": False,
            "deployed": False,
            "production_source_modified": False,
        }

    @classmethod
    def _promotion_with_events(cls, connection: Any, row: Any) -> dict[str, Any]:
        value = cls._promotion(row)
        events = connection.execute("""
            SELECT state,created_at FROM source_promotion_events
            WHERE promotion_id=? ORDER BY id
        """, (row["promotion_id"],)).fetchall()
        value["lifecycle"] = [dict(event) for event in events]
        return value


class ControlledPromotionWorkspace:
    """Atomic exact-byte materialization into a dedicated staging root."""

    def __init__(self, root: Path | None = None):
        self.root = (
            root or data_root() / "promotion_environment" / "staging"
        ).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)

    @staticmethod
    def expected_destination(system_name: str) -> str:
        return f"staging/{system_name}"

    def _target(self, destination: str) -> Path:
        if not isinstance(destination, str) or not destination.startswith("staging/"):
            raise PromotionRejected("invalid_destination")
        name = destination.removeprefix("staging/")
        if WorkspaceManager.NAME_PATTERN.fullmatch(name) is None or "/" in name:
            raise PromotionRejected("invalid_destination")
        target = (self.root / name).resolve()
        if target.parent != self.root:
            raise PromotionRejected("destination_escape")
        return target

    @staticmethod
    def _metadata(
        files: dict[str, str], paths: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        ordered = paths or sorted(files)
        return [
            {
                "path": path,
                "bytes": len(content.encode("utf-8")),
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
            for path in ordered
            for content in [files[path]]
        ]

    @classmethod
    def digest(cls, files: dict[str, str], paths: list[str] | None = None) -> str:
        return hashlib.sha256(
            json.dumps(
                cls._metadata(files, paths), sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def load_destination(self, destination: str) -> dict[str, str]:
        target = self._target(destination)
        if target.is_symlink() or not target.is_dir():
            raise PromotionRejected("destination_missing")
        files: dict[str, str] = {}
        for path in sorted(target.rglob("*")):
            if path.is_symlink():
                raise PromotionRejected("destination_symlink")
            if path.is_file():
                relative = path.relative_to(target).as_posix()
                files[relative] = path.read_text(encoding="utf-8")
        return files

    def promote(
        self,
        *,
        promotion_id: str,
        destination: str,
        files: dict[str, str],
        metadata_paths: list[str],
        expected_digest: str,
    ) -> tuple[str, str]:
        target = self._target(destination)
        if target.exists() or target.is_symlink():
            raise PromotionRejected("destination_exists")
        lock = self.root / f".{target.name}.lock"
        temporary = self.root / f".{promotion_id}.tmp"
        descriptor: int | None = None
        created_target = False
        try:
            descriptor = os.open(
                lock,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_CLOEXEC", 0),
                0o600,
            )
            if temporary.exists() or temporary.is_symlink():
                raise PromotionRejected("partial_promotion_exists")
            if target.exists() or target.is_symlink():
                raise PromotionRejected("destination_exists")
            temporary.mkdir(mode=0o700)
            for raw_path, content in sorted(files.items()):
                relative = WorkspaceManager._validate_relative_path(raw_path)
                output = temporary.joinpath(*relative.parts)
                if temporary not in output.resolve().parents:
                    raise PromotionRejected("destination_escape")
                output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                fd = os.open(
                    output,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY
                    | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
                    0o400,
                )
                try:
                    value = content.encode("utf-8")
                    view = memoryview(value)
                    while view:
                        written = os.write(fd, view)
                        view = view[written:]
                    os.fsync(fd)
                finally:
                    os.close(fd)
            staged = {
                path.relative_to(temporary).as_posix(): path.read_text(encoding="utf-8")
                for path in sorted(temporary.rglob("*")) if path.is_file()
            }
            staged_digest = self.digest(staged, metadata_paths)
            if staged != files or staged_digest != expected_digest:
                raise PromotionRejected("destination_digest_mismatch")
            os.rename(temporary, target)
            created_target = True
            final_files = self.load_destination(destination)
            final_digest = self.digest(final_files, metadata_paths)
            if final_files != files or final_digest != expected_digest:
                raise PromotionRejected("destination_digest_mismatch")
            artifact_id = "SPK-PROMOTED-" + hashlib.sha256(
                f"{promotion_id}:{destination}:{expected_digest}".encode("utf-8")
            ).hexdigest()[:24].upper()
            return final_digest, artifact_id
        except Exception:
            if temporary.exists() and temporary.parent == self.root:
                shutil.rmtree(temporary, ignore_errors=True)
            if created_target and target.exists() and target.parent == self.root:
                shutil.rmtree(target, ignore_errors=True)
            raise
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if lock.exists() and lock.parent == self.root:
                lock.unlink()


class ControlledSourcePromotionService:
    PROTOCOL = "SPARKLE-AI-SYSTEM-SOURCE-PROMOTION/1"
    APPROVAL_TTL_SECONDS = 86_400
    ACTOR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{1,127}$")
    ORIGINS = {"cli", "authenticated_api", "operator"}
    REQUEST = re.compile(r"^SPK-PROMO-REQ-[A-F0-9]{32}$")

    def __init__(
        self,
        candidates: SourceCandidateStore,
        candidate_workspace: SourceCandidateWorkspace,
        plans: AISystemImplementationPlanStore,
        evaluations: RuntimeEvaluationStore,
        traces: TraceStore,
        store: SourcePromotionStore,
        workspace: ControlledPromotionWorkspace,
    ):
        self.candidates = candidates
        self.candidate_workspace = candidate_workspace
        self.plans = plans
        self.evaluations = evaluations
        self.traces = traces
        self.store = store
        self.workspace = workspace

    @classmethod
    def _identity(cls, actor: Any, source_origin: Any) -> tuple[str, str]:
        if not isinstance(actor, str) or cls.ACTOR.fullmatch(actor) is None:
            raise ValueError("Source promotion actor is invalid")
        if source_origin not in cls.ORIGINS:
            raise ValueError("Source promotion origin is invalid")
        return actor, source_origin

    @staticmethod
    def _successful_evaluation(evaluation: dict[str, Any]) -> bool:
        criteria = evaluation.get("criteria_results")
        return (
            evaluation["status"] == "evaluated"
            and evaluation["runtime_verified"] is True
            and evaluation["response_verified"] is True
            and evaluation["timed_out"] is False
            and evaluation["returncode"] == 0
            and isinstance(criteria, list)
            and bool(criteria)
            and all(
                isinstance(item, dict) and item.get("passed") is True
                for item in criteria
            )
        )

    def eligibility(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return bounded content-free promotion readiness, never source content."""
        evaluations = self.evaluations.list(limit=100)
        approvals = self.store.list_approvals(limit=100)
        promotions = self.store.list(limit=100)
        result: list[dict[str, Any]] = []
        for candidate in self.candidates.list(limit=max(1, min(limit, 100))):
            candidate_id = candidate["candidate_id"]
            exclusion = self.store.exclusion(candidate_id)
            successful = next((
                item for item in evaluations
                if item["candidate_id"] == candidate_id
                and self._successful_evaluation(item)
            ), None)
            approval = next((
                item for item in approvals if item["candidate_id"] == candidate_id
            ), None)
            promotion = next((
                item for item in promotions if item["candidate_id"] == candidate_id
            ), None)
            if exclusion is not None:
                state, reason = "not_eligible", f"candidate_{exclusion['status']}"
            elif candidate["status"] != "approved":
                state, reason = "not_eligible", "candidate_not_approved"
            elif successful is None:
                state, reason = "not_eligible", "runtime_evaluation_required"
            elif promotion is not None:
                state, reason = promotion["status"], promotion["error_type"]
            elif approval is None:
                state, reason = "awaiting_approval", None
            elif approval["status"] == "approved":
                state, reason = "approval_recorded", None
            else:
                state, reason = "not_eligible", f"approval_{approval['status']}"
            result.append({
                "candidate_id": candidate_id,
                "plan_id": candidate["plan_id"],
                "evaluation_id": successful["evaluation_id"] if successful else None,
                "state": state,
                "reason": reason,
                "built": False,
                "published": False,
                "deployed": False,
            })
        return result

    def _candidate_files(self, candidate: dict[str, Any]) -> dict[str, str]:
        try:
            manifest, files = self.candidate_workspace.load(candidate["candidate_id"])
        except Exception as exc:
            raise PromotionRejected("candidate_workspace_invalid") from exc
        required = {
            "protocol_version", "candidate_id", "plan_id", "plan_sha256",
            "status", "files", "candidate_sha256", "runtime_tests_executed",
            "external_deployment_executed",
        }
        if (
            not isinstance(manifest, dict)
            or set(manifest) != required
            or manifest.get("candidate_id") != candidate["candidate_id"]
            or manifest.get("plan_id") != candidate["plan_id"]
            or manifest.get("plan_sha256") != candidate["plan_sha256"]
            or manifest.get("candidate_sha256") != candidate["candidate_sha256"]
            or manifest.get("files") != candidate["files"]
        ):
            raise PromotionRejected("candidate_metadata_mismatch")
        metadata_paths = [item["path"] for item in candidate["files"]]
        if set(metadata_paths) != set(files) or len(metadata_paths) != len(files):
            raise PromotionRejected("candidate_metadata_mismatch")
        metadata = ControlledPromotionWorkspace._metadata(files, metadata_paths)
        if metadata != candidate["files"]:
            raise PromotionRejected("candidate_content_tampered")
        if ControlledPromotionWorkspace.digest(files, metadata_paths) != candidate["candidate_sha256"]:
            raise PromotionRejected("candidate_digest_mismatch")
        return files

    def _authoritative(
        self, candidate_id: int, evaluation_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
        try:
            candidate = self.candidates.get(candidate_id)
        except (KeyError, ValueError) as exc:
            raise PromotionRejected("candidate_missing") from exc
        if candidate["status"] != "approved":
            raise PromotionRejected("candidate_not_approved")
        exclusion = self.store.exclusion(candidate_id)
        if exclusion is not None:
            raise PromotionRejected(f"candidate_{exclusion['status']}")
        try:
            plan = self.plans.get(candidate["plan_id"])
        except (KeyError, ValueError) as exc:
            raise PromotionRejected("plan_missing") from exc
        if (
            plan["plan_sha256"] != candidate["plan_sha256"]
            or plan["system_name"] != candidate["system_name"]
            or plan["status"] != "materialized_static_verified"
            or plan["review_status"] != "approved_for_generation"
        ):
            raise PromotionRejected("plan_mismatch")
        try:
            evaluation = self.evaluations.by_evaluation_id(evaluation_id)
        except (KeyError, ValueError) as exc:
            raise PromotionRejected("evaluation_missing") from exc
        if (
            evaluation["candidate_id"] != candidate_id
            or evaluation["plan_id"] != candidate["plan_id"]
        ):
            raise PromotionRejected("evaluation_mismatch")
        if not self._successful_evaluation(evaluation):
            raise PromotionRejected("evaluation_not_successful")
        files = self._candidate_files(candidate)
        return candidate, plan, evaluation, files

    def approve(
        self,
        candidate_id: int,
        evaluation_id: str,
        *,
        actor: str,
        source_origin: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Source promotion approval requires explicit approval")
        actor, source_origin = self._identity(actor, source_origin)
        candidate, _, evaluation, _ = self._authoritative(
            candidate_id, evaluation_id,
        )
        return self.store.approve(
            candidate=candidate,
            evaluation=evaluation,
            actor=actor,
            source_origin=source_origin,
            ttl_seconds=self.APPROVAL_TTL_SECONDS,
        )

    def exclude_candidate(
        self,
        candidate_id: int,
        *,
        status: str,
        reason: str,
        actor: str,
        source_origin: str,
        approved: bool,
        replacement_candidate_id: int | None = None,
    ) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Source promotion exclusion requires explicit approval")
        actor, source_origin = self._identity(actor, source_origin)
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500:
            raise ValueError("Source promotion exclusion reason is invalid")
        self.candidates.get(candidate_id)
        if status == "superseded":
            if replacement_candidate_id == candidate_id:
                raise ValueError("A candidate cannot supersede itself")
            self.candidates.get(replacement_candidate_id or 0)
        elif replacement_candidate_id is not None:
            raise ValueError("Invalidation cannot name a replacement candidate")
        return self.store.exclude(
            candidate_id,
            status=status,
            replacement_candidate_id=replacement_candidate_id,
            reason_sha256=hashlib.sha256(reason.strip().encode("utf-8")).hexdigest(),
            actor=actor,
            source_origin=source_origin,
        )

    def validate(self, contract: dict[str, Any]) -> tuple[dict[str, Any], str]:
        fields = {
            "protocol_version", "request_id", "candidate_id",
            "candidate_sha256", "plan_id", "plan_sha256", "evaluation_id",
            "approval_id", "destination", "actor", "source_origin",
        }
        if not isinstance(contract, dict) or set(contract) != fields:
            raise ValueError("Source promotion contract fields are invalid")
        if contract["protocol_version"] != self.PROTOCOL:
            raise ValueError("Source promotion protocol is invalid")
        if not isinstance(contract["request_id"], str) or self.REQUEST.fullmatch(contract["request_id"]) is None:
            raise ValueError("Source promotion request ID is invalid")
        for field in ("candidate_id", "plan_id"):
            value = contract[field]
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"Source promotion {field} is invalid")
        if not _digest(contract["candidate_sha256"]) or not _digest(contract["plan_sha256"]):
            raise ValueError("Source promotion digest is invalid")
        if not isinstance(contract["evaluation_id"], str) or not contract["evaluation_id"].startswith("SPK-EVAL-"):
            raise ValueError("Source promotion evaluation ID is invalid")
        if not isinstance(contract["approval_id"], str) or not contract["approval_id"].startswith("SPK-PROMO-APP-"):
            raise ValueError("Source promotion approval ID is invalid")
        self._identity(contract["actor"], contract["source_origin"])
        if not isinstance(contract["destination"], str) or len(contract["destination"]) > 80:
            raise ValueError("Source promotion destination is invalid")
        canonical = json.dumps(
            contract, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        if len(canonical.encode("utf-8")) > 4_096:
            raise ValueError("Source promotion contract exceeds its size bound")
        return contract, hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def request(self, contract: dict[str, Any], *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Source promotion request requires explicit approval")
        contract, contract_digest = self.validate(contract)
        trace_id, started = self.traces.start(
            input_source="ai_system_source_promotion",
            agent="system",
            content_identifiers=[
                str(contract["candidate_id"]), contract["evaluation_id"],
                contract["request_id"],
            ],
            processing_stage="promotion_requested",
            execution_metadata={
                "candidate_id": contract["candidate_id"],
                "plan_id": contract["plan_id"],
                "evaluation_id": contract["evaluation_id"],
                "approval_id": contract["approval_id"],
            },
        )
        self.traces.finish(
            trace_id,
            started,
            status="success",
            agent="system",
            model=None,
            provider=None,
            processing_stage="promotion_requested",
            result_summary="Controlled source promotion request recorded",
        )
        record, disposition = self.store.create_or_find(
            contract, contract_digest, trace_id,
        )
        if disposition == "replay":
            if record["contract_sha256"] != contract_digest:
                raise PromotionRejected("request_replay_conflict")
            return record
        if disposition == "candidate_conflict":
            same = (
                record["contract_sha256"] == contract_digest
                or (
                    record["candidate_sha256"] == contract["candidate_sha256"]
                    and record["plan_sha256"] == contract["plan_sha256"]
                    and record["evaluation_id"] == contract["evaluation_id"]
                    and record["destination"] == contract["destination"]
                )
            )
            if same:
                return record
            raise PromotionRejected("candidate_promotion_conflict")
        promotion_id = record["promotion_id"]
        try:
            candidate, plan, evaluation, files = self._authoritative(
                contract["candidate_id"], contract["evaluation_id"],
            )
            if (
                contract["candidate_sha256"] != candidate["candidate_sha256"]
                or contract["plan_id"] != candidate["plan_id"]
                or contract["plan_sha256"] != plan["plan_sha256"]
            ):
                raise PromotionRejected("contract_identity_mismatch")
            expected_destination = self.workspace.expected_destination(
                candidate["system_name"]
            )
            if contract["destination"] != expected_destination:
                raise PromotionRejected("invalid_destination")
            try:
                approval = self.store.approval(contract["approval_id"])
            except KeyError as exc:
                raise PromotionRejected("approval_missing") from exc
            if datetime.fromisoformat(approval["expires_at"]) <= datetime.now(UTC):
                self.store.expire_approval(approval["approval_id"])
                raise PromotionRejected("approval_stale")
            approval_matches = (
                approval["status"] == "approved"
                and approval["candidate_id"] == candidate["candidate_id"]
                and approval["candidate_sha256"] == candidate["candidate_sha256"]
                and approval["plan_id"] == plan["plan_id"]
                and approval["plan_sha256"] == plan["plan_sha256"]
                and approval["evaluation_id"] == evaluation["evaluation_id"]
                and approval["evaluation_contract_sha256"]
                == evaluation["contract_sha256"]
                and approval["actor"] == contract["actor"]
                and approval["source_origin"] == contract["source_origin"]
                and approval["approved_at"] >= evaluation["updated_at"]
            )
            if not approval_matches:
                raise PromotionRejected("approval_mismatch")
            self.store.begin_promotion(promotion_id, approval["approval_id"])
            destination_digest, artifact_id = self.workspace.promote(
                promotion_id=promotion_id,
                destination=contract["destination"],
                files=files,
                metadata_paths=[item["path"] for item in candidate["files"]],
                expected_digest=candidate["candidate_sha256"],
            )
            if destination_digest != candidate["candidate_sha256"]:
                raise PromotionRejected("destination_digest_mismatch")
            final = self.store.transition(
                promotion_id,
                "promoting",
                "promoted",
                source_digest=candidate["candidate_sha256"],
                destination_digest=destination_digest,
                artifact_id=artifact_id,
            )
        except PromotionRejected as exc:
            current = self.store.by_promotion_id(promotion_id)
            expected = current["status"]
            state = "rejected" if expected == "requested" else "failed"
            final = self.store.transition(
                promotion_id, expected, state, error_type=exc.reason,
            )
        except Exception as exc:
            current = self.store.by_promotion_id(promotion_id)
            expected = current["status"]
            state = "rejected" if expected == "requested" else "failed"
            final = self.store.transition(
                promotion_id, expected, state,
                error_type=type(exc).__name__[:128],
            )
        self._trace(final, evaluation if "evaluation" in locals() else None)
        return final

    def _trace(
        self, result: dict[str, Any], evaluation: dict[str, Any] | None,
    ) -> None:
        self.traces.annotate_lifecycle(
            result["trace_id"],
            processing_stage=result["status"],
            transformations=[
                "approved_source_candidate", "runtime_evaluation",
                "promotion_approval", "promotion_integrity_check",
                "controlled_staging_materialization",
            ],
            data_accessed=["candidate_environment", "data_environment"],
            data_created=[f"source_promotion:{result['promotion_id']}"],
            storage_destinations=[
                "promotion_environment", "data_environment", "trace_environment",
            ],
            execution_metadata={
                "protocol_version": self.PROTOCOL,
                "promotion_id": result["promotion_id"],
                "candidate_id": result["candidate_id"],
                "plan_id": result["plan_id"],
                "evaluation_id": result["evaluation_id"],
                "approval_id": result["approval_id"],
                "destination": result["destination"],
                "actor": result["actor"],
                "source_origin": result["source_origin"],
                "lifecycle_state": result["status"],
                "source_digest": result["source_digest"],
                "destination_digest": result["destination_digest"],
                "runtime_verified": bool(
                    evaluation and evaluation["runtime_verified"]
                ),
                "isolation_verified": bool(
                    evaluation and evaluation["isolation_verified"]
                ),
                "built": False,
                "packaged": False,
                "published": False,
                "deployed": False,
                "production_verified": False,
            },
            result_summary="Controlled source promotion lifecycle updated",
        )
