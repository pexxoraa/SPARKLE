from __future__ import annotations

import json
import math
import re
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sparkle.config import data_root
from sparkle.mastery import SkillMasteryStore
from sparkle.notifications import NotificationStore
from sparkle.orchestrator import Orchestrator
from sparkle.projects import ProjectStore
from sparkle.storage import KnowledgeStore, MemoryStore, SQLiteStore, utc_now
from sparkle.trace import TraceStore


class AutomationLeaseLostError(RuntimeError):
    """A recovered or cancelled claim can no longer commit a run result."""


PROACTIVE_ALERT_TYPES = frozenset({
    "deadline_approaching",
    "overdue",
    "project_incomplete",
    "repeated_mistake",
    "research_change",
    "revision_due",
    "schedule_conflict",
    "weak_learning",
})


class AutomationStore(SQLiteStore):
    VALID_KINDS = {"once", "daily", "weekly", "condition"}

    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "data_environment" / "automations.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS automations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL,
                    schedule TEXT,
                    condition_json TEXT,
                    action_json TEXT NOT NULL,
                    next_run_at TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_status TEXT,
                    last_run_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(automations)"
                ).fetchall()
            }
            if "claim_token" not in columns:
                connection.execute("ALTER TABLE automations ADD COLUMN claim_token TEXT")
            if "claim_expires_at" not in columns:
                connection.execute(
                    "ALTER TABLE automations ADD COLUMN claim_expires_at TEXT"
                )
            connection.execute("""
                CREATE TABLE IF NOT EXISTS automation_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    automation_id INTEGER NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    trace_id TEXT,
                    result_summary TEXT,
                    error_type TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL
                )
            """)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_automation_runs_automation ON automation_runs(automation_id, id)"
            )
            connection.execute("""
                CREATE TABLE IF NOT EXISTS automation_service_state (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    instance_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    heartbeat_at TEXT NOT NULL,
                    stopped_at TEXT,
                    last_cycle_at TEXT,
                    last_error_type TEXT,
                    interval_seconds REAL NOT NULL,
                    lease_seconds INTEGER NOT NULL,
                    cycles INTEGER NOT NULL,
                    recovered_claims INTEGER NOT NULL
                )
            """)

    def create(
        self, name: str, kind: str, action: dict[str, Any], *, schedule: str | None = None,
        condition: dict[str, Any] | None = None, next_run_at: str | None = None,
    ) -> int:
        if kind not in self.VALID_KINDS:
            raise ValueError(f"Unsupported automation kind: {kind}")
        if kind in {"once", "daily", "weekly"} and not next_run_at:
            raise ValueError("Scheduled automations require next_run_at")
        if kind == "condition" and not condition:
            raise ValueError("Conditional automations require a condition")
        if kind == "condition":
            self._validate_condition(condition)
        self._validate_action(action)
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO automations(name, kind, schedule, condition_json, action_json, next_run_at, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?)
            """, (name, kind, schedule, json.dumps(condition), json.dumps(action), next_run_at, now, now))
        return int(cursor.lastrowid)

    @staticmethod
    def _validate_action(action: dict[str, Any]) -> None:
        if not isinstance(action, dict):
            raise ValueError("Automation action must be an object")
        action_type = action.get("type")
        if action_type == "agent":
            prompt = action.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20_000:
                raise ValueError("Automation agent prompt must contain 1-20000 characters")
        elif action_type == "notification":
            allowed = {
                "type", "channel", "title", "body", "severity",
                "dedupe_key", "max_attempts",
            }
            unknown = set(action) - allowed
            if unknown:
                raise ValueError(
                    "Unsupported notification action fields: "
                    + ", ".join(sorted(unknown))
                )
            NotificationStore.validate(
                channel=action.get("channel"),
                title=action.get("title"),
                body=action.get("body"),
                severity=action.get("severity", "info"),
                dedupe_key=action.get("dedupe_key"),
                source="automation",
            )
        else:
            raise ValueError(
                "Automation action type must be 'agent' or 'notification'"
            )
        attempts = action.get("max_attempts", 1)
        if isinstance(attempts, bool) or not isinstance(attempts, int) or not 1 <= attempts <= 3:
            raise ValueError("Automation max_attempts must be an integer from 1 to 3")

    @staticmethod
    def _validate_condition(condition: dict[str, Any] | None) -> None:
        if not isinstance(condition, dict):
            raise ValueError("Automation condition must be an object")
        allowed = {"type", "alert", "category", "key", "cooldown_minutes"}
        unknown = set(condition) - allowed
        if unknown:
            raise ValueError(
                "Unsupported automation condition fields: "
                + ", ".join(sorted(unknown))
            )
        condition_type = condition.get("type")
        if condition_type not in {"memory_deadline", "proactive_alert"}:
            raise ValueError("Automation condition type is unsupported")
        alert = condition.get("alert")
        if alert not in PROACTIVE_ALERT_TYPES:
            raise ValueError("Automation proactive alert type is unsupported")
        if condition_type == "memory_deadline" and alert not in {
            "deadline_approaching", "overdue",
        }:
            raise ValueError("memory_deadline accepts only deadline alert types")
        category = condition.get("category")
        if category is not None and category not in MemoryStore.VALID_CATEGORIES:
            raise ValueError("Automation condition memory category is unsupported")
        key = condition.get("key")
        if key is not None and (
            not isinstance(key, str) or not key.strip() or len(key) > 200
        ):
            raise ValueError("Automation condition key must contain 1-200 characters")
        cooldown = condition.get("cooldown_minutes", 60)
        if (
            isinstance(cooldown, bool)
            or not isinstance(cooldown, (int, float))
            or not 1 <= cooldown <= 10_080
        ):
            raise ValueError("Condition cooldown_minutes must be from 1 to 10080")

    def due(self, now: str | None = None) -> list[dict[str, Any]]:
        current = now or utc_now()
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT * FROM automations WHERE enabled=1 AND kind != 'condition'
                AND next_run_at IS NOT NULL AND next_run_at <= ? ORDER BY next_run_at
            """, (current,)).fetchall()
        return [self._public(row) for row in rows]

    def conditions(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM automations WHERE enabled=1 AND kind='condition' ORDER BY id"
            ).fetchall()
        return [self._public(row) for row in rows]

    @staticmethod
    def _claim_values(
        now: str | None, claim_token: str | None, lease_seconds: int,
    ) -> tuple[str, str, str]:
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int):
            raise ValueError("Automation lease_seconds must be an integer")
        if not 30 <= lease_seconds <= 86_400:
            raise ValueError("Automation lease_seconds must be from 30 to 86400")
        current = now or utc_now()
        try:
            current_time = datetime.fromisoformat(current.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise ValueError("Automation claim time must be ISO-8601") from exc
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        token = claim_token or uuid.uuid4().hex
        if not isinstance(token, str) or not 16 <= len(token) <= 128 or not token.isalnum():
            raise ValueError("Automation claim token must be 16-128 alphanumeric characters")
        expires = (current_time + timedelta(seconds=lease_seconds)).isoformat()
        return current_time.isoformat(), token, expires

    def claim_due(
        self,
        now: str | None = None,
        *,
        claim_token: str | None = None,
        lease_seconds: int = 3_600,
    ) -> list[dict[str, Any]]:
        current, token, expires = self._claim_values(
            now, claim_token, lease_seconds,
        )
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("""
                SELECT * FROM automations WHERE enabled=1 AND kind != 'condition'
                AND next_run_at IS NOT NULL AND next_run_at <= ? ORDER BY next_run_at
            """, (current,)).fetchall()
            for row in rows:
                connection.execute(
                    """UPDATE automations SET enabled=0, last_status='running',
                       claim_token=?, claim_expires_at=?, updated_at=?
                       WHERE id=? AND enabled=1""",
                    (token, expires, current, row["id"]),
                )
        values = [self._public(row) for row in rows]
        for value in values:
            value["_claim_token"] = token
            value["_claim_expires_at"] = expires
        return values

    def claim_condition(
        self,
        automation_id: int,
        now: str | None = None,
        *,
        claim_token: str | None = None,
        lease_seconds: int = 3_600,
    ) -> dict[str, Any] | None:
        current, token, expires = self._claim_values(
            now, claim_token, lease_seconds,
        )
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM automations WHERE id=? AND enabled=1 AND kind='condition'",
                (automation_id,),
            ).fetchone()
            if not row:
                return None
            connection.execute(
                """UPDATE automations SET enabled=0, last_status='running',
                   claim_token=?, claim_expires_at=?, updated_at=?
                   WHERE id=? AND enabled=1""",
                (token, expires, current, automation_id),
            )
        value = self._public(row)
        value["_claim_token"] = token
        value["_claim_expires_at"] = expires
        return value

    def recover_stale_claims(self, now: str | None = None) -> int:
        current = now or utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("""
                SELECT id, updated_at FROM automations
                WHERE enabled=0 AND last_status='running'
                  AND claim_expires_at IS NOT NULL AND claim_expires_at <= ?
                ORDER BY id
            """, (current,)).fetchall()
            for row in rows:
                connection.execute("""
                    INSERT INTO automation_runs(
                        automation_id, status, attempts, trace_id,
                        result_summary, error_type, started_at, finished_at
                    ) VALUES(?, 'recovered', 0, NULL, NULL,
                             'AutomationLeaseExpired', ?, ?)
                """, (row["id"], row["updated_at"], current))
                connection.execute("""
                    UPDATE automations
                    SET enabled=1, last_status='recovered', claim_token=NULL,
                        claim_expires_at=NULL, updated_at=?
                    WHERE id=? AND enabled=0 AND last_status='running'
                """, (current, row["id"]))
        return len(rows)

    @staticmethod
    def _next_run(item: dict[str, Any], now: datetime) -> str | None:
        if item["kind"] not in {"daily", "weekly"}:
            return None
        interval = timedelta(days=1 if item["kind"] == "daily" else 7)
        source = item.get("next_run_at")
        try:
            candidate = datetime.fromisoformat(str(source).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            candidate = now
        if candidate.tzinfo is None:
            candidate = candidate.replace(tzinfo=UTC)
        while candidate <= now:
            candidate += interval
        return candidate.isoformat()

    def finish(
        self,
        item: dict[str, Any],
        *,
        status: str,
        attempts: int,
        started_at: str,
        result_summary: str | None = None,
        trace_id: str | None = None,
        error_type: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if status not in {"success", "failure"}:
            raise ValueError(f"Unsupported automation run status: {status}")
        current = now or datetime.now(UTC)
        finished_at = current.isoformat()
        next_run_at = self._next_run(item, current)
        enabled = item["kind"] in {"daily", "weekly", "condition"}
        safe_summary = result_summary[:1_000] if result_summary else None
        claim_token = item.get("_claim_token")
        if not isinstance(claim_token, str):
            raise AutomationLeaseLostError("Automation run has no active claim token")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute("""
                UPDATE automations SET enabled=?, last_status=?, last_run_at=?,
                    next_run_at=?, claim_token=NULL, claim_expires_at=NULL,
                    updated_at=?
                WHERE id=? AND last_status='running' AND claim_token=?
            """, (
                int(enabled), status, finished_at, next_run_at, finished_at,
                item["id"], claim_token,
            ))
            if updated.rowcount != 1:
                raise AutomationLeaseLostError(
                    "Automation claim expired, was recovered, or was cancelled"
                )
            cursor = connection.execute("""
                INSERT INTO automation_runs(
                    automation_id, status, attempts, trace_id, result_summary,
                    error_type, started_at, finished_at
                ) VALUES(?,?,?,?,?,?,?,?)
            """, (
                item["id"], status, attempts, trace_id, safe_summary,
                error_type, started_at, finished_at,
            ))
        return {
            "run_id": int(cursor.lastrowid), "automation_id": item["id"],
            "name": item["name"], "status": status, "attempts": attempts,
            "trace_id": trace_id, "result_summary": safe_summary,
            "error_type": error_type, "started_at": started_at,
            "finished_at": finished_at, "next_run_at": next_run_at,
        }

    def list(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM automations ORDER BY id DESC").fetchall()
        return [self._public(row) for row in rows]

    def set_enabled(self, automation_id: int, enabled: bool) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE automations SET enabled=?,
                   last_status=CASE WHEN last_status='running' THEN 'cancelled'
                                    ELSE last_status END,
                   claim_token=NULL, claim_expires_at=NULL, updated_at=? WHERE id=?""",
                (int(enabled), utc_now(), automation_id),
            )
        return cursor.rowcount == 1

    def service_start(
        self,
        instance_id: str,
        *,
        interval_seconds: float,
        lease_seconds: int,
        recovered_claims: int,
        now: str | None = None,
    ) -> None:
        current = now or utc_now()
        with self.connect() as connection:
            connection.execute("""
                INSERT INTO automation_service_state(
                    singleton, instance_id, state, started_at, heartbeat_at,
                    stopped_at, last_cycle_at, last_error_type,
                    interval_seconds, lease_seconds, cycles, recovered_claims
                ) VALUES(1,?, 'running',?,?,NULL,NULL,NULL,?,?,0,?)
                ON CONFLICT(singleton) DO UPDATE SET
                    instance_id=excluded.instance_id, state='running',
                    started_at=excluded.started_at,
                    heartbeat_at=excluded.heartbeat_at, stopped_at=NULL,
                    last_cycle_at=NULL, last_error_type=NULL,
                    interval_seconds=excluded.interval_seconds,
                    lease_seconds=excluded.lease_seconds, cycles=0,
                    recovered_claims=excluded.recovered_claims
            """, (
                instance_id, current, current, float(interval_seconds),
                lease_seconds, recovered_claims,
            ))

    def service_heartbeat(
        self,
        instance_id: str,
        *,
        state: str = "running",
        cycle_completed: bool = False,
        recovered_claims: int = 0,
        last_error_type: str | None = None,
        now: str | None = None,
    ) -> None:
        if state not in {"running", "degraded", "draining"}:
            raise ValueError("Automation service heartbeat state is invalid")
        if (
            isinstance(recovered_claims, bool)
            or not isinstance(recovered_claims, int)
            or recovered_claims < 0
        ):
            raise ValueError("Recovered automation claim count is invalid")
        current = now or utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE automation_service_state
                SET state=?, heartbeat_at=?,
                    last_cycle_at=CASE WHEN ? THEN ? ELSE last_cycle_at END,
                    cycles=cycles+?, recovered_claims=recovered_claims+?,
                    last_error_type=?
                WHERE singleton=1 AND instance_id=?
            """, (
                state, current, int(cycle_completed), current,
                int(cycle_completed), recovered_claims, last_error_type,
                instance_id,
            ))
        if cursor.rowcount != 1:
            raise RuntimeError("Automation service lost ownership of status state")

    def service_stop(
        self,
        instance_id: str,
        *,
        state: str = "stopped",
        last_error_type: str | None = None,
        now: str | None = None,
    ) -> None:
        if state not in {"stopped", "error"}:
            raise ValueError("Automation service stop state is invalid")
        current = now or utc_now()
        with self.connect() as connection:
            connection.execute("""
                UPDATE automation_service_state
                SET state=?, heartbeat_at=?, stopped_at=?, last_error_type=?
                WHERE singleton=1 AND instance_id=?
            """, (state, current, current, last_error_type, instance_id))

    def service_status(self, now: datetime | None = None) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM automation_service_state WHERE singleton=1"
            ).fetchone()
        if row is None:
            return {
                "state": "never_started", "active": False, "healthy": False,
                "stale": False, "cycles": 0, "recovered_claims": 0,
                "last_error_type": None,
            }
        current = now or datetime.now(UTC)
        heartbeat = datetime.fromisoformat(row["heartbeat_at"].replace("Z", "+00:00"))
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=UTC)
        stale_after = max(
            30.0,
            float(row["interval_seconds"]) * 3,
            float(row["lease_seconds"]),
        )
        active_state = row["state"] in {"running", "degraded", "draining"}
        stale = active_state and (current - heartbeat).total_seconds() > stale_after
        state = "stale" if stale else row["state"]
        return {
            "state": state,
            "active": active_state and not stale,
            "healthy": row["state"] == "running" and not stale,
            "stale": stale,
            "started_at": row["started_at"],
            "heartbeat_at": row["heartbeat_at"],
            "stopped_at": row["stopped_at"],
            "last_cycle_at": row["last_cycle_at"],
            "last_error_type": row["last_error_type"],
            "interval_seconds": row["interval_seconds"],
            "lease_seconds": row["lease_seconds"],
            "cycles": row["cycles"],
            "recovered_claims": row["recovered_claims"],
        }

    def delete(self, automation_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM automations WHERE id=?", (automation_id,))
        return cursor.rowcount == 1

    def list_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT automation_runs.*, automations.name
                FROM automation_runs JOIN automations ON automations.id=automation_runs.automation_id
                ORDER BY automation_runs.id DESC LIMIT ?
            """, (max(1, min(limit, 100)),)).fetchall()
        return [
            {
                "run_id": row["id"], "automation_id": row["automation_id"],
                "name": row["name"], "status": row["status"],
                "attempts": row["attempts"], "trace_id": row["trace_id"],
                "result_summary": row["result_summary"], "error_type": row["error_type"],
                "started_at": row["started_at"], "finished_at": row["finished_at"],
            }
            for row in rows
        ]

    @staticmethod
    def _public(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "name": row["name"], "kind": row["kind"], "schedule": row["schedule"],
            "condition": json.loads(row["condition_json"]) if row["condition_json"] else None,
            "action": json.loads(row["action_json"]), "next_run_at": row["next_run_at"],
            "enabled": bool(row["enabled"]), "last_status": row["last_status"],
            "last_run_at": row["last_run_at"],
        }


class ProactiveEngine:
    """Produces bounded alerts only from explicit structured evidence."""

    PROTOCOL = "SPARKLE-PROACTIVE/1"
    MAX_ALERTS = 200
    MAX_SCHEDULE_RECORDS = 200
    MAX_SCHEDULE_CONFLICTS = 200
    MAX_SCHEDULE_DURATION_DAYS = 7
    SCHEDULE_HORIZON_DAYS = 30
    MAX_RESEARCH_OBSERVATIONS = 200
    MAX_RESEARCH_CHANGES = 100
    RESEARCH_CHANGE_HORIZON_DAYS = 7
    _SEVERITY_ORDER = {"urgent": 0, "high": 1, "medium": 2}

    def __init__(
        self,
        memory: MemoryStore,
        knowledge: KnowledgeStore | None = None,
        projects: ProjectStore | None = None,
        skills: SkillMasteryStore | None = None,
    ):
        self.memory = memory
        self.knowledge = knowledge
        self.projects = projects
        self.skills = skills

    @staticmethod
    def _time(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value or len(value) > 100:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed

    @staticmethod
    def _number(value: Any, minimum: float, maximum: float) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        return number if math.isfinite(number) and minimum <= number <= maximum else None

    @classmethod
    def _alert(
        cls,
        item: dict[str, Any],
        alert_type: str,
        severity: str,
        evidence: dict[str, Any],
        **compatibility: Any,
    ) -> dict[str, Any]:
        return {
            "protocol_version": cls.PROTOCOL,
            "type": alert_type,
            "severity": severity,
            "category": item["category"],
            "key": item["key"],
            "source_kind": "memory",
            "source_id": item["id"],
            "source_memory_id": item["id"],
            "evidence": evidence,
            **compatibility,
        }

    @classmethod
    def _deadline_alert(
        cls, item: dict[str, Any], current: datetime,
    ) -> dict[str, Any] | None:
        metadata = item["metadata"]
        raw_due = metadata.get("deadline") or metadata.get("due_at")
        due = cls._time(raw_due)
        if due is None:
            return None
        hours = (due - current).total_seconds() / 3_600
        rounded = round(hours, 1)
        evidence = {"due_at": due.isoformat(), "hours_remaining": rounded}
        if hours < 0:
            severity = "urgent" if hours <= -24 else "high"
            return cls._alert(
                item, "overdue", severity, evidence, hours=rounded,
            )
        if hours <= 72:
            return cls._alert(
                item, "deadline_approaching", "high", evidence, hours=rounded,
            )
        return None

    @classmethod
    def _weak_learning_alert(cls, item: dict[str, Any]) -> dict[str, Any] | None:
        metadata = item["metadata"]
        evidence_count = metadata.get("evidence_count")
        if (
            isinstance(evidence_count, bool)
            or not isinstance(evidence_count, int)
            or not 1 <= evidence_count <= 1_000_000
        ):
            return None
        evidence: dict[str, Any] = {"evidence_count": evidence_count}
        gap_score = 0.0
        mastery = cls._number(metadata.get("mastery_level"), 0, 6)
        target_mastery = cls._number(metadata.get("target_level"), 0, 6)
        if mastery is not None and target_mastery is not None and mastery < target_mastery:
            evidence.update({
                "mastery_level": int(mastery),
                "target_level": int(target_mastery),
                "mastery_gap": int(target_mastery - mastery),
            })
            gap_score = max(gap_score, (target_mastery - mastery) / 6)
        accuracy = cls._number(metadata.get("accuracy"), 0, 1)
        target_accuracy = cls._number(metadata.get("target_accuracy"), 0, 1)
        attempts = metadata.get("attempts")
        if (
            accuracy is not None
            and target_accuracy is not None
            and accuracy < target_accuracy
            and isinstance(attempts, int)
            and not isinstance(attempts, bool)
            and 1 <= attempts <= 1_000_000
        ):
            evidence.update({
                "accuracy": round(accuracy, 4),
                "target_accuracy": round(target_accuracy, 4),
                "attempts": attempts,
                "accuracy_gap": round(target_accuracy - accuracy, 4),
            })
            gap_score = max(gap_score, target_accuracy - accuracy)
        if len(evidence) == 1:
            return None
        return cls._alert(
            item,
            "weak_learning",
            "high" if gap_score >= 0.2 else "medium",
            evidence,
        )

    @classmethod
    def _revision_alert(
        cls, item: dict[str, Any], current: datetime,
    ) -> dict[str, Any] | None:
        review = cls._time(item["metadata"].get("next_review_at"))
        if review is None or review > current:
            return None
        overdue_hours = round((current - review).total_seconds() / 3_600, 1)
        return cls._alert(
            item,
            "revision_due",
            "high" if overdue_hours >= 24 else "medium",
            {"next_review_at": review.isoformat(), "overdue_hours": overdue_hours},
        )

    @classmethod
    def _project_alert(cls, item: dict[str, Any]) -> dict[str, Any] | None:
        metadata = item["metadata"]
        status = metadata.get("status")
        progress = cls._number(metadata.get("progress_percent"), 0, 100)
        if status not in {"active", "blocked", "in_progress", "paused"}:
            return None
        if progress is None or progress >= 100:
            return None
        return cls._alert(
            item,
            "project_incomplete",
            "high" if status == "blocked" else "medium",
            {"status": status, "progress_percent": round(progress, 2)},
        )

    @classmethod
    def _mistake_alert(cls, item: dict[str, Any]) -> dict[str, Any] | None:
        repeat_count = item["metadata"].get("repeat_count")
        if (
            isinstance(repeat_count, bool)
            or not isinstance(repeat_count, int)
            or not 2 <= repeat_count <= 1_000_000
        ):
            return None
        return cls._alert(
            item,
            "repeated_mistake",
            "high" if repeat_count >= 3 else "medium",
            {"repeat_count": repeat_count},
        )

    @classmethod
    def _schedule_interval(
        cls, item: dict[str, Any], current: datetime,
    ) -> tuple[datetime, datetime] | None:
        metadata = item["metadata"]
        start = cls._time(metadata.get("starts_at"))
        end = cls._time(metadata.get("ends_at"))
        if start is None or end is None:
            return None
        start = start.astimezone(UTC)
        end = end.astimezone(UTC)
        duration = end - start
        if duration <= timedelta(0) or duration > timedelta(
            days=cls.MAX_SCHEDULE_DURATION_DAYS,
        ):
            return None
        if end <= current or start > current + timedelta(
            days=cls.SCHEDULE_HORIZON_DAYS,
        ):
            return None
        return start, end

    @classmethod
    def _schedule_alerts(
        cls, items: list[dict[str, Any]], current: datetime,
    ) -> list[dict[str, Any]]:
        recent = sorted(
            items, key=lambda item: int(item["id"]), reverse=True,
        )[: cls.MAX_SCHEDULE_RECORDS]
        intervals: list[tuple[datetime, datetime, dict[str, Any]]] = []
        for item in recent:
            interval = cls._schedule_interval(item, current)
            if interval is not None:
                intervals.append((*interval, item))
        intervals.sort(key=lambda value: (
            value[0], value[1], value[2]["category"], value[2]["key"],
            value[2]["id"],
        ))

        alerts: list[dict[str, Any]] = []
        horizon = current + timedelta(days=cls.SCHEDULE_HORIZON_DAYS)
        for index, (first_start, first_end, first) in enumerate(intervals):
            for second_start, second_end, second in intervals[index + 1:]:
                if second_start >= first_end:
                    break
                overlap_start = max(first_start, second_start)
                overlap_end = min(first_end, second_end)
                if (
                    overlap_start >= overlap_end
                    or overlap_end <= current
                    or overlap_start > horizon
                ):
                    continue
                primary, conflicting = sorted(
                    (first, second), key=lambda item: int(item["id"]),
                )
                hours_until = (
                    overlap_start - current
                ).total_seconds() / 3_600
                severity = (
                    "urgent" if hours_until <= 0
                    else "high" if hours_until <= 24
                    else "medium"
                )
                alerts.append(cls._alert(
                    primary,
                    "schedule_conflict",
                    severity,
                    {
                        "overlap_start": overlap_start.isoformat(),
                        "overlap_end": overlap_end.isoformat(),
                        "overlap_minutes": round(
                            (overlap_end - overlap_start).total_seconds() / 60,
                            2,
                        ),
                        "conflicting_memory_id": conflicting["id"],
                        "conflicting_category": conflicting["category"],
                        "conflicting_key": conflicting["key"],
                    },
                ))
                if len(alerts) >= cls.MAX_SCHEDULE_CONFLICTS:
                    return alerts
        return alerts

    def _research_alerts(self, current: datetime) -> list[dict[str, Any]]:
        if self.knowledge is None:
            return []
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in self.knowledge.monitor_observations(
            limit=self.MAX_RESEARCH_OBSERVATIONS,
        ):
            metadata = item.get("metadata")
            digest = item.get("content_digest")
            if (
                not isinstance(metadata, dict)
                or metadata.get("research_monitor") is not True
                or not isinstance(metadata.get("monitor_key"), str)
                or KnowledgeStore.MONITOR_KEY_PATTERN.fullmatch(
                    metadata["monitor_key"]
                ) is None
                or not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            ):
                continue
            grouped.setdefault(metadata["monitor_key"], []).append(item)

        alerts: list[dict[str, Any]] = []
        for monitor_key in sorted(grouped):
            observations = sorted(
                grouped[monitor_key], key=lambda item: int(item["source_id"]),
            )
            if len(observations) < 2:
                continue
            previous, latest = observations[-2:]
            if previous["content_digest"] == latest["content_digest"]:
                continue
            observed_at = self._time(latest.get("created_at"))
            if observed_at is None:
                continue
            observed_at = observed_at.astimezone(UTC)
            age = current - observed_at
            if (
                age < -timedelta(minutes=5)
                or age > timedelta(days=self.RESEARCH_CHANGE_HORIZON_DAYS)
            ):
                continue
            source_id = int(latest["source_id"])
            alerts.append({
                "protocol_version": self.PROTOCOL,
                "type": "research_change",
                "severity": "medium",
                "category": "research",
                "key": monitor_key,
                "source_kind": "knowledge",
                "source_id": source_id,
                "source_knowledge_id": source_id,
                "evidence": {
                    "previous_source_id": int(previous["source_id"]),
                    "current_source_id": source_id,
                    "observed_at": observed_at.isoformat(),
                    "age_hours": round(max(0.0, age.total_seconds() / 3_600), 1),
                },
            })
            if len(alerts) >= self.MAX_RESEARCH_CHANGES:
                break
        return alerts

    def _structured_project_alerts(
        self, current: datetime,
    ) -> list[dict[str, Any]]:
        if self.projects is None:
            return []
        alerts: list[dict[str, Any]] = []
        for project in self.projects.list(limit=100):
            if project["status"] == "complete":
                continue
            evidence: dict[str, Any] = {
                "status": project["status"],
                "priority": project["priority"],
                "progress_percent": project["progress"],
                "blocker_count": len(project["blockers"]),
                "open_milestone_count": sum(
                    item["status"] != "complete"
                    for item in project["milestones"]
                ),
            }
            alerts.append({
                "protocol_version": self.PROTOCOL,
                "type": "project_incomplete",
                "severity": (
                    "high"
                    if project["status"] == "blocked"
                    or project["priority"] == "critical"
                    else "medium"
                ),
                "category": "projects",
                "key": project["name"],
                "source_kind": "project",
                "source_id": project["name"],
                "source_project_name": project["name"],
                "evidence": evidence,
            })
            due = self._time(project["deadline"])
            if due is None:
                continue
            hours = (due.astimezone(UTC) - current).total_seconds() / 3_600
            if hours > 72:
                continue
            alerts.append({
                "protocol_version": self.PROTOCOL,
                "type": "overdue" if hours < 0 else "deadline_approaching",
                "severity": (
                    "urgent" if hours <= -24 else "high"
                ),
                "category": "projects",
                "key": project["name"],
                "source_kind": "project",
                "source_id": project["name"],
                "source_project_name": project["name"],
                "evidence": {
                    "due_at": due.astimezone(UTC).isoformat(),
                    "hours_remaining": round(hours, 1),
                },
                "hours": round(hours, 1),
            })
        return alerts

    def _structured_skill_alerts(self) -> list[dict[str, Any]]:
        if self.skills is None:
            return []
        alerts: list[dict[str, Any]] = []
        for skill in self.skills.list(limit=100):
            gap = skill["target_level"] - skill["current_level"]
            if gap <= 0:
                continue
            alerts.append({
                "protocol_version": self.PROTOCOL,
                "type": "weak_learning",
                "severity": "high" if gap >= 2 else "medium",
                "category": "skills",
                "key": skill["name"],
                "source_kind": "skill",
                "source_id": skill["name"],
                "source_skill_name": skill["name"],
                "evidence": {
                    "mastery_level": skill["current_level"],
                    "target_level": skill["target_level"],
                    "mastery_gap": gap,
                    "verified_evidence_count": skill[
                        "verified_evidence_count"
                    ],
                    "total_evidence_count": skill["total_evidence_count"],
                    "average_verified_score": skill[
                        "average_verified_score"
                    ],
                    "evidence_type_count": len(skill["evidence_types"]),
                },
            })
        return alerts

    def inspect(self, now: datetime | None = None) -> list[dict[str, Any]]:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        alerts: list[dict[str, Any]] = []
        schedule_items: list[dict[str, Any]] = []
        categories = (
            "tasks", "exams", "projects", "goals", "skills", "learning", "mistakes",
        )
        for category in categories:
            for item in self.memory.recent(limit=100, category=category):
                if category in {"tasks", "exams", "projects"}:
                    schedule_items.append(item)
                if category in {"tasks", "exams", "projects", "goals"}:
                    alert = self._deadline_alert(item, current)
                    if alert:
                        alerts.append(alert)
                if category in {"skills", "learning", "exams"}:
                    for alert in (
                        self._weak_learning_alert(item),
                        self._revision_alert(item, current),
                    ):
                        if alert:
                            alerts.append(alert)
                if category == "projects":
                    alert = self._project_alert(item)
                    if alert:
                        alerts.append(alert)
                if category == "mistakes":
                    alert = self._mistake_alert(item)
                    if alert:
                        alerts.append(alert)
        alerts.extend(self._schedule_alerts(schedule_items, current))
        alerts.extend(self._research_alerts(current))
        alerts.extend(self._structured_project_alerts(current))
        alerts.extend(self._structured_skill_alerts())
        alerts.sort(key=lambda alert: (
            self._SEVERITY_ORDER[alert["severity"]],
            alert["type"],
            alert["category"],
            alert["key"],
            (
                0, alert["source_id"]
            ) if isinstance(alert["source_id"], int) else (
                1, str(alert["source_id"])
            ),
        ))
        return alerts[: self.MAX_ALERTS]


class AutomationRunner:
    """Claims due work, invokes SPARKLE agents, and persists execution evidence."""

    def __init__(
        self,
        store: AutomationStore,
        orchestrator: Orchestrator,
        proactive: ProactiveEngine,
        notifications: NotificationStore | None = None,
        traces: TraceStore | None = None,
    ):
        self.store = store
        self.orchestrator = orchestrator
        self.proactive = proactive
        self.notifications = notifications
        self.traces = traces

    @staticmethod
    def _condition_matches(item: dict[str, Any], alerts: list[dict[str, Any]], now: datetime) -> bool:
        condition = item.get("condition") or {}
        if condition.get("type") not in {"memory_deadline", "proactive_alert"}:
            return False
        last_run = item.get("last_run_at")
        cooldown = condition.get("cooldown_minutes", 60)
        if isinstance(cooldown, bool) or not isinstance(cooldown, (int, float)) or not 1 <= cooldown <= 10_080:
            raise ValueError("Condition cooldown_minutes must be from 1 to 10080")
        if last_run:
            try:
                previous = datetime.fromisoformat(str(last_run).replace("Z", "+00:00"))
                if previous.tzinfo is None:
                    previous = previous.replace(tzinfo=UTC)
                if now - previous < timedelta(minutes=float(cooldown)):
                    return False
            except ValueError:
                pass
        expected = {
            "type": condition.get("alert"),
            "category": condition.get("category"),
            "key": condition.get("key"),
        }
        return any(
            all(value is None or alert.get(field) == value for field, value in expected.items())
            for alert in alerts
        )

    def _execute(self, item: dict[str, Any]) -> tuple[str, str]:
        action = item["action"]
        if action.get("type") == "notification":
            if self.notifications is None or self.traces is None:
                raise RuntimeError("Notification delivery is unavailable")
            trace_id, clock = self.traces.start(
                input_source="automation",
                agent="automation",
                input_modalities=["event"],
                content_identifiers=[f"automation:{item['id']}"],
                processing_stage="notification_delivery",
                execution_metadata={
                    "channel": action.get("channel"),
                    "severity": action.get("severity", "info"),
                },
            )
            try:
                notification = self.notifications.deliver(
                    channel=str(action["channel"]),
                    title=str(action["title"]),
                    body=str(action["body"]),
                    severity=str(action.get("severity", "info")),
                    dedupe_key=(
                        str(action["dedupe_key"])
                        if action.get("dedupe_key") is not None else None
                    ),
                    source="automation",
                )
            except Exception as exc:
                self.traces.finish(
                    trace_id,
                    clock,
                    status="failure",
                    agent="automation",
                    model=None,
                    provider=None,
                    processing_stage="notification_failed",
                    output_modalities=[],
                    execution_metadata={
                        "channel": action.get("channel"),
                        "severity": action.get("severity", "info"),
                    },
                    result_summary="Notification delivery failed",
                    error_type=type(exc).__name__,
                )
                raise
            self.traces.finish(
                trace_id,
                clock,
                status="success",
                agent="automation",
                model=None,
                provider=None,
                data_created=[
                    f"notification:{notification['notification_id']}"
                ],
                transformations=["notification_validated", "dashboard_delivered"],
                storage_destinations=["data_environment/notifications"],
                processing_stage="notification_delivered",
                output_modalities=["notification"],
                execution_metadata={
                    "channel": notification["channel"],
                    "severity": notification["severity"],
                },
                result_summary="Dashboard notification delivered",
            )
            return "Dashboard notification delivered", trace_id
        if action.get("type") != "agent":
            raise ValueError(
                f"Unsupported automation action type: {action.get('type')}"
            )
        prompt = str(action["prompt"])
        if action.get("multi_agent"):
            result = self.orchestrator.run_multi(
                prompt,
                agent_names=action.get("agents"),
                user_id=action.get("user_id"),
                input_source="automation",
            )
        else:
            result = self.orchestrator.run(
                prompt,
                agent_name=action.get("agent"),
                user_id=action.get("user_id"),
                input_source="automation",
            )
        return result.text, result.trace_id

    def run_due(
        self,
        now: datetime | None = None,
        *,
        claim_token: str | None = None,
        lease_seconds: int = 3_600,
    ) -> list[dict[str, Any]]:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        claimed = self.store.claim_due(
            current.isoformat(),
            claim_token=claim_token,
            lease_seconds=lease_seconds,
        )
        alerts = self.proactive.inspect(current)
        for candidate in self.store.conditions():
            if self._condition_matches(candidate, alerts, current):
                item = self.store.claim_condition(
                    candidate["id"],
                    current.isoformat(),
                    claim_token=claim_token,
                    lease_seconds=lease_seconds,
                )
                if item:
                    claimed.append(item)

        runs: list[dict[str, Any]] = []
        for item in claimed:
            started_at = utc_now()
            max_attempts = int(item["action"].get("max_attempts", 1))
            attempts = 0
            result_summary = None
            trace_id = None
            error: Exception | None = None
            while attempts < max_attempts:
                attempts += 1
                try:
                    result_summary, trace_id = self._execute(item)
                    error = None
                    break
                except Exception as exc:
                    error = exc
            if error is None:
                runs.append(self.store.finish(
                    item, status="success", attempts=attempts, started_at=started_at,
                    result_summary=result_summary, trace_id=trace_id, now=current,
                ))
            else:
                runs.append(self.store.finish(
                    item, status="failure", attempts=attempts, started_at=started_at,
                    result_summary=str(error), error_type=type(error).__name__, now=current,
                ))
        return runs
