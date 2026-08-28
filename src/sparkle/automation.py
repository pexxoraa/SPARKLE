from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sparkle.config import data_root
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
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO automations(name, kind, schedule, condition_json, action_json, next_run_at, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?)
            """, (name, kind, schedule, json.dumps(condition), json.dumps(action), next_run_at, now, now))
        return int(cursor.lastrowid)

    def due(self, now: str | None = None) -> list[dict[str, Any]]:
        current = now or utc_now()
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT * FROM automations WHERE enabled=1 AND kind != 'condition'
                AND next_run_at IS NOT NULL AND next_run_at <= ? ORDER BY next_run_at
            """, (current,)).fetchall()
        return [self._public(row) for row in rows]

    def list(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM automations ORDER BY id DESC").fetchall()
        return [self._public(row) for row in rows]

    @staticmethod
    def _public(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "name": row["name"], "kind": row["kind"], "schedule": row["schedule"],
            "condition": json.loads(row["condition_json"]) if row["condition_json"] else None,
            "action": json.loads(row["action_json"]), "next_run_at": row["next_run_at"],
            "enabled": bool(row["enabled"]), "last_status": row["last_status"], "last_run_at": row["last_run_at"],
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
