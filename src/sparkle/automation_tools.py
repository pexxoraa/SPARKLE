from __future__ import annotations

from typing import Any

from sparkle.automation import AutomationStore
from sparkle.tooling import Tool, ToolError


class AutomationInspectTool(Tool):
    """Read bounded automation definitions and execution evidence without mutation."""

    name = "automation_inspect"
    description = (
        "Inspect supervised automation definitions, recent runs, per-attempt retry "
        "evidence, and scheduler service status. This tool is read-only; creating, "
        "enabling, disabling, running, or deleting automations remains operator-owned."
    )
    parameters = {
        "type": "object",
        "properties": {
            "automation_id": {"type": "integer", "minimum": 1},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "additionalProperties": False,
    }

    def __init__(self, store: AutomationStore):
        self.store = store

    def _automations(
        self, automation_id: int | None, limit: int,
    ) -> list[dict[str, Any]]:
        with self.store.connect() as connection:
            if automation_id is None:
                rows = connection.execute(
                    "SELECT * FROM automations ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM automations WHERE id=?", (automation_id,)
                ).fetchall()
        values = [self.store._public(row) for row in rows]
        if automation_id is not None and not values:
            raise ToolError("Unknown automation")
        return values

    def _runs(
        self, automation_id: int | None, limit: int,
    ) -> list[dict[str, Any]]:
        sql = """SELECT automation_runs.*, automations.name
            FROM automation_runs JOIN automations
            ON automations.id=automation_runs.automation_id"""
        parameters: tuple[Any, ...]
        if automation_id is None:
            sql += " ORDER BY automation_runs.id DESC LIMIT ?"
            parameters = (limit,)
        else:
            sql += (
                " WHERE automation_runs.automation_id=?"
                " ORDER BY automation_runs.id DESC LIMIT ?"
            )
            parameters = (automation_id, limit)
        with self.store.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [
            {
                "run_id": row["id"],
                "automation_id": row["automation_id"],
                "name": row["name"],
                "status": row["status"],
                "attempts": row["attempts"],
                "trace_id": row["trace_id"],
                "result_summary": row["result_summary"],
                "error_type": row["error_type"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
            }
            for row in rows
        ]

    def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(arguments, dict) or set(arguments) - {
            "automation_id", "limit"
        }:
            raise ToolError("Automation inspection fields are unsupported")
        automation_id = arguments.get("automation_id")
        limit = arguments.get("limit", 20)
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 50
        ):
            raise ToolError("Automation inspection limit must be from 1 to 50")
        if automation_id is not None and (
            isinstance(automation_id, bool)
            or not isinstance(automation_id, int)
            or automation_id < 1
        ):
            raise ToolError("Automation identity is invalid")

        automations = self._automations(automation_id, limit)
        runs = self._runs(automation_id, limit)
        list_attempts = getattr(self.store, "list_attempts", None)
        attempts: list[dict[str, Any]] = []
        if callable(list_attempts):
            attempts = list_attempts(automation_id, limit=limit)

        return {
            "automations": automations,
            "recent_runs": runs,
            "recent_attempts": attempts,
            "service": self.store.service_status(),
            "read_only": True,
            "mutation_requires_operator_interface": True,
        }
