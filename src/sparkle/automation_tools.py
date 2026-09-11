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

        automations = self.store.list()
        if automation_id is not None:
            automations = [
                item for item in automations if item["id"] == automation_id
            ]
            if not automations:
                raise ToolError("Unknown automation")
        else:
            automations = automations[:limit]

        runs = self.store.list_runs(limit=limit)
        if automation_id is not None:
            runs = [
                item for item in runs if item["automation_id"] == automation_id
            ][:limit]

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
