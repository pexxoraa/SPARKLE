from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sparkle.config import data_root
from sparkle.orchestrator import Orchestrator
from sparkle.storage import MemoryStore, SQLiteStore, utc_now


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
        if action.get("type") != "agent":
            raise ValueError("Automation action type must be 'agent'")
        prompt = action.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20_000:
            raise ValueError("Automation agent prompt must contain 1-20000 characters")
        attempts = action.get("max_attempts", 1)
        if isinstance(attempts, bool) or not isinstance(attempts, int) or not 1 <= attempts <= 3:
            raise ValueError("Automation max_attempts must be an integer from 1 to 3")

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

    def claim_due(self, now: str | None = None) -> list[dict[str, Any]]:
        current = now or utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("""
                SELECT * FROM automations WHERE enabled=1 AND kind != 'condition'
                AND next_run_at IS NOT NULL AND next_run_at <= ? ORDER BY next_run_at
            """, (current,)).fetchall()
            for row in rows:
                connection.execute(
                    "UPDATE automations SET enabled=0, last_status='running', updated_at=? WHERE id=?",
                    (current, row["id"]),
                )
        return [self._public(row) for row in rows]

    def claim_condition(self, automation_id: int, now: str | None = None) -> dict[str, Any] | None:
        current = now or utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM automations WHERE id=? AND enabled=1 AND kind='condition'",
                (automation_id,),
            ).fetchone()
            if not row:
                return None
            connection.execute(
                "UPDATE automations SET enabled=0, last_status='running', updated_at=? WHERE id=?",
                (current, automation_id),
            )
        return self._public(row)

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
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO automation_runs(
                    automation_id, status, attempts, trace_id, result_summary,
                    error_type, started_at, finished_at
                ) VALUES(?,?,?,?,?,?,?,?)
            """, (
                item["id"], status, attempts, trace_id, safe_summary,
                error_type, started_at, finished_at,
            ))
            connection.execute("""
                UPDATE automations SET enabled=?, last_status=?, last_run_at=?,
                    next_run_at=?, updated_at=? WHERE id=?
            """, (
                int(enabled), status, finished_at, next_run_at, finished_at, item["id"],
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
                "UPDATE automations SET enabled=?, updated_at=? WHERE id=?",
                (int(enabled), utc_now(), automation_id),
            )
        return cursor.rowcount == 1

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
    """Produces evidence-backed alerts from stored tasks, goals, exams, and projects."""

    def __init__(self, memory: MemoryStore):
        self.memory = memory

    def inspect(self, now: datetime | None = None) -> list[dict[str, Any]]:
        current = now or datetime.now(UTC)
        alerts: list[dict[str, Any]] = []
        for category in ("tasks", "exams", "projects", "goals"):
            for item in self.memory.recent(limit=100, category=category):
                due = item["metadata"].get("deadline") or item["metadata"].get("due_at")
                if not due:
                    continue
                try:
                    due_time = datetime.fromisoformat(due.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    continue
                hours = (due_time - current).total_seconds() / 3600
                if hours < 0:
                    alerts.append({"type": "overdue", "category": category, "key": item["key"], "hours": round(hours, 1)})
                elif hours <= 72:
                    alerts.append({"type": "deadline_approaching", "category": category, "key": item["key"], "hours": round(hours, 1)})
        return alerts


class AutomationRunner:
    """Claims due work, invokes SPARKLE agents, and persists execution evidence."""

    def __init__(self, store: AutomationStore, orchestrator: Orchestrator, proactive: ProactiveEngine):
        self.store = store
        self.orchestrator = orchestrator
        self.proactive = proactive

    @staticmethod
    def _condition_matches(item: dict[str, Any], alerts: list[dict[str, Any]], now: datetime) -> bool:
        condition = item.get("condition") or {}
        if condition.get("type") != "memory_deadline":
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
        if action.get("type") != "agent":
            raise ValueError(f"Unsupported automation action type: {action.get('type')}")
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

    def run_due(self, now: datetime | None = None) -> list[dict[str, Any]]:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        claimed = self.store.claim_due(current.isoformat())
        alerts = self.proactive.inspect(current)
        for candidate in self.store.conditions():
            if self._condition_matches(candidate, alerts, current):
                item = self.store.claim_condition(candidate["id"], current.isoformat())
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
