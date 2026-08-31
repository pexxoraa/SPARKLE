from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sparkle.agents import AgentRegistry
from sparkle.artifacts import ArtifactManager
from sparkle.builders import WorkspaceManager
from sparkle.config import data_root
from sparkle.content import SUPPORTED_CONTENT_TYPES
from sparkle.registry import ModelRegistry
from sparkle.storage import SQLiteStore, utc_now
from sparkle.tooling import ToolRegistry


@dataclass(frozen=True, slots=True)
class AIModelRoute:
    capability: str
    modalities: tuple[str, ...]
    record_id: str
    provider: str
    model_id: str
    configured: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "modalities": list(self.modalities),
            "record_id": self.record_id,
            "provider": self.provider,
            "model_id": self.model_id,
            "configured": self.configured,
        }


@dataclass(frozen=True, slots=True)
class AISystemEvaluation:
    name: str
    kind: str
    criterion: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "kind": self.kind,
            "criterion": self.criterion,
        }


@dataclass(frozen=True, slots=True)
class AISystemBlueprint:
    protocol_version: str
    name: str
    purpose: str
    model_routes: tuple[AIModelRoute, ...]
    agents: tuple[str, ...]
    tools: tuple[str, ...]
    data_environments: tuple[str, ...]
    interfaces: tuple[str, ...]
    workflow: tuple[str, ...]
    evaluations: tuple[AISystemEvaluation, ...]
    deployment: dict[str, str]
    static_checks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "name": self.name,
            "purpose": self.purpose,
            "architecture": {
                "model_routes": [route.to_dict() for route in self.model_routes],
                "agents": list(self.agents),
                "tools": list(self.tools),
                "data_environments": list(self.data_environments),
                "interfaces": list(self.interfaces),
            },
            "workflow": list(self.workflow),
            "evaluations": [item.to_dict() for item in self.evaluations],
            "deployment": dict(self.deployment),
            "implementation_files": ["README.md", "SPARKLE_AI_SYSTEM.json"],
            "static_checks": list(self.static_checks),
            "status": "prepared_static_verified",
            "model_calls_executed": False,
            "runtime_evaluation_executed": False,
            "external_deployment_executed": False,
        }


class AISystemBlueprintStore(SQLiteStore):
    MAX_RECORDS = 1_000

    def __init__(self, path: Path | None = None):
        super().__init__(
            path or data_root() / "data_environment" / "ai_system_blueprints.sqlite3"
        )
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS ai_system_blueprints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    system_name TEXT NOT NULL,
                    requirements_json TEXT NOT NULL,
                    blueprint_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    workspace_build_id INTEGER,
                    error_type TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def create(
        self,
        requirements: dict[str, Any],
        blueprint: AISystemBlueprint,
    ) -> int:
        now = utc_now()
        requirements_json = json.dumps(
            requirements, ensure_ascii=False, separators=(",", ":"),
            sort_keys=True, allow_nan=False,
        )
        blueprint_json = json.dumps(
            blueprint.to_dict(), ensure_ascii=False, separators=(",", ":"),
            sort_keys=True, allow_nan=False,
        )
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO ai_system_blueprints(
                    system_name, requirements_json, blueprint_json, status,
                    workspace_build_id, error_type, created_at, updated_at
                ) VALUES(?,?,?,'materializing',NULL,NULL,?,?)
            """, (
                blueprint.name, requirements_json, blueprint_json, now, now,
            ))
            connection.execute("""
                DELETE FROM ai_system_blueprints WHERE id NOT IN (
                    SELECT id FROM ai_system_blueprints ORDER BY id DESC LIMIT ?
                )
            """, (self.MAX_RECORDS,))
        return int(cursor.lastrowid)

    def finish(
        self,
        blueprint_id: int,
        *,
        status: str,
        workspace_build_id: int | None = None,
        error_type: str | None = None,
    ) -> None:
        if status not in {"materialized_static_verified", "materialization_failed"}:
            raise ValueError("Unsupported AI System Blueprint status")
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE ai_system_blueprints
                SET status=?, workspace_build_id=?, error_type=?, updated_at=?
                WHERE id=? AND status='materializing'
            """, (
                status, workspace_build_id, error_type, utc_now(), blueprint_id,
            ))
        if cursor.rowcount != 1:
            raise RuntimeError("AI System Blueprint state transition failed")

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT id, system_name, blueprint_json, status,
                       workspace_build_id, error_type, created_at, updated_at
                FROM ai_system_blueprints ORDER BY id DESC LIMIT ?
            """, (max(1, min(limit, 100)),)).fetchall()
        return [
            {
                "blueprint_id": row["id"],
                "system_name": row["system_name"],
                "blueprint": json.loads(row["blueprint_json"]),
                "status": row["status"],
                "workspace_build_id": row["workspace_build_id"],
                "error_type": row["error_type"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]


class AISystemBlueprintBuilder:
    PROTOCOL = "SPARKLE-AI-SYSTEM-BLUEPRINT/1"
    MAX_REQUIREMENTS_BYTES = 64_000
    _NAME = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
    _CASE_NAME = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
    _ALLOWED_FIELDS = {
        "name", "purpose", "model_requirements", "agents", "tools",
        "data_environments", "interfaces", "workflow", "evaluations",
        "deployment",
    }
    _DATA_ENVIRONMENTS = {
        "memory_environment", "knowledge_environment", "data_environment",
        "trace_environment",
    }
    _INTERFACES = {
        "api", "automation", "cli", "dashboard", "multimodal", "text", "voice",
    }
    _EVALUATION_KINDS = {
        "agent_response_contract", "end_to_end", "integration", "static_contract",
    }

    def __init__(
        self,
        models: ModelRegistry,
        agents: AgentRegistry,
        tools: ToolRegistry,
        workspaces: WorkspaceManager,
        store: AISystemBlueprintStore,
    ):
        self.models = models
        self.agents = agents
        self.tools = tools
        self.workspaces = workspaces
        self.store = store

    def requirements_contract(self) -> dict[str, Any]:
        """Return the current provider-neutral vocabulary for draft generation."""
        model_records = self.models.list()
        return {
            "required_root_fields": sorted(self._ALLOWED_FIELDS),
            "model_capabilities": sorted({
                role
                for record in model_records
                if record["enabled"]
                for role in record["roles"]
            }),
            "model_modalities": sorted({
                modality
                for record in model_records
                if record["enabled"]
                for modality in record["modalities"]
            }),
            "agent_tools": {
                name: sorted(self.agents.get(name).tools)
                for name in sorted(self.agents.names)
            },
            "data_environments": sorted(self._DATA_ENVIRONMENTS),
            "interfaces": sorted(self._INTERFACES),
            "evaluation_kinds": sorted(self._EVALUATION_KINDS),
            "deployment_target_kinds": sorted(ArtifactManager.TARGET_KINDS),
        }

    @staticmethod
    def _strings(
        value: Any,
        *,
        field: str,
        minimum: int,
        maximum: int,
        max_chars: int,
        allowed: set[str] | None = None,
    ) -> tuple[str, ...]:
        if (
            not isinstance(value, list)
            or not minimum <= len(value) <= maximum
            or any(
                not isinstance(item, str)
                or not item.strip()
                or len(item.strip()) > max_chars
                for item in value
            )
        ):
            raise ValueError(
                f"AI system {field} must contain {minimum}-{maximum} "
                f"strings of at most {max_chars} characters"
            )
        normalized = tuple(item.strip() for item in value)
        if len({item.casefold() for item in normalized}) != len(normalized):
            raise ValueError(f"AI system {field} must not contain duplicates")
        if allowed is not None and not set(normalized) <= allowed:
            unknown = sorted(set(normalized) - allowed)
            raise ValueError(
                f"AI system {field} contains unsupported values: "
                + ", ".join(unknown)
            )
        return normalized

    def _model_routes(self, value: Any) -> tuple[AIModelRoute, ...]:
        if not isinstance(value, list) or not 1 <= len(value) <= 10:
            raise ValueError("AI system model_requirements must contain 1-10 entries")
        records = {record["id"]: record for record in self.models.list()}
        available_roles = {
            role for record in records.values() for role in record["roles"]
        }
        routes: list[AIModelRoute] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for raw in value:
            if not isinstance(raw, dict) or set(raw) != {"capability", "modalities"}:
                raise ValueError(
                    "AI system model requirements require capability and modalities"
                )
            capability = raw["capability"]
            if not isinstance(capability, str) or capability not in available_roles:
                raise ValueError("AI system model capability is unavailable")
            modalities = tuple(sorted(self._strings(
                raw["modalities"], field="model modalities", minimum=1,
                maximum=len(SUPPORTED_CONTENT_TYPES), max_chars=32,
                allowed=set(SUPPORTED_CONTENT_TYPES),
            )))
            key = (capability, modalities)
            if key in seen:
                raise ValueError("AI system model requirements must not contain duplicates")
            seen.add(key)
            preferred = self.models.routing.get(
                capability,
                self.models.routing.get("default", self.models.active_id),
            )
            ordered_ids = [preferred, *sorted(set(records) - {preferred})]
            selected = next((
                records[record_id]
                for record_id in ordered_ids
                if record_id in records
                and records[record_id]["enabled"]
                and capability in records[record_id]["roles"]
                and set(modalities) <= set(records[record_id]["modalities"])
            ), None)
            if selected is None:
                raise ValueError(
                    "No enabled model satisfies AI system capability/modalities: "
                    f"{capability}/{' + '.join(modalities)}"
                )
            routes.append(AIModelRoute(
                capability=capability,
                modalities=modalities,
                record_id=selected["id"],
                provider=selected["provider"],
                model_id=selected["model_id"],
                configured=bool(selected["configured"]),
            ))
        return tuple(routes)

    def _evaluations(self, value: Any) -> tuple[AISystemEvaluation, ...]:
        if not isinstance(value, list) or not 1 <= len(value) <= 20:
            raise ValueError("AI system evaluations must contain 1-20 entries")
        result: list[AISystemEvaluation] = []
        names: set[str] = set()
        for raw in value:
            if not isinstance(raw, dict) or set(raw) != {"name", "kind", "criterion"}:
                raise ValueError(
                    "AI system evaluations require name, kind, and criterion"
                )
            name = raw["name"]
            kind = raw["kind"]
            criterion = raw["criterion"]
            if not isinstance(name, str) or self._CASE_NAME.fullmatch(name) is None:
                raise ValueError("AI system evaluation name is invalid")
            if name in names:
                raise ValueError("AI system evaluation names must be unique")
            names.add(name)
            if not isinstance(kind, str) or kind not in self._EVALUATION_KINDS:
                raise ValueError("AI system evaluation kind is unsupported")
            if (
                not isinstance(criterion, str)
                or not criterion.strip()
                or len(criterion.strip()) > 500
            ):
                raise ValueError("AI system evaluation criterion is invalid")
            result.append(AISystemEvaluation(name, kind, criterion.strip()))
        return tuple(result)

    def _deployment(self, value: Any) -> dict[str, str]:
        if (
            not isinstance(value, dict)
            or set(value) != {"environment_name", "target_kind"}
        ):
            raise ValueError(
                "AI system deployment requires environment_name and target_kind"
            )
        environment = value["environment_name"]
        target = value["target_kind"]
        if not isinstance(environment, str) or self._NAME.fullmatch(environment) is None:
            raise ValueError("AI system deployment environment name is invalid")
        if not isinstance(target, str) or target not in ArtifactManager.TARGET_KINDS:
            raise ValueError("AI system deployment target kind is unsupported")
        return {
            "environment_name": environment,
            "target_kind": target,
            "status": "planned_unverified",
        }

    def prepare(self, requirements: dict[str, Any]) -> AISystemBlueprint:
        if not isinstance(requirements, dict):
            raise ValueError("AI system requirements must be an object")
        unknown = set(requirements) - self._ALLOWED_FIELDS
        if unknown:
            raise ValueError(
                "Unsupported AI system fields: " + ", ".join(sorted(unknown))
            )
        try:
            encoded = json.dumps(
                requirements, ensure_ascii=False, separators=(",", ":"),
                sort_keys=True, allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("AI system requirements must contain JSON values") from exc
        if len(encoded) > self.MAX_REQUIREMENTS_BYTES:
            raise ValueError("AI system requirements exceed 64000 bytes")
        name = requirements.get("name")
        purpose = requirements.get("purpose")
        if not isinstance(name, str) or self._NAME.fullmatch(name) is None:
            raise ValueError("AI system name must be a 2-64 character lowercase identifier")
        if (
            not isinstance(purpose, str)
            or not 10 <= len(purpose.strip()) <= 1_000
        ):
            raise ValueError("AI system purpose must contain 10-1000 characters")
        agents = self._strings(
            requirements.get("agents"), field="agents", minimum=1,
            maximum=16, max_chars=64,
        )
        unknown_agents = set(agents) - self.agents.names
        if unknown_agents:
            raise ValueError(
                "AI system references unknown agents: "
                + ", ".join(sorted(unknown_agents))
            )
        tools = self._strings(
            requirements.get("tools", []), field="tools", minimum=0,
            maximum=20, max_chars=64,
        )
        unknown_tools = set(tools) - self.tools.names
        if unknown_tools:
            raise ValueError(
                "AI system references unknown tools: "
                + ", ".join(sorted(unknown_tools))
            )
        agent_tool_union = set().union(*(
            set(self.agents.get(agent).tools) for agent in agents
        ))
        inaccessible = set(tools) - agent_tool_union
        if inaccessible:
            raise ValueError(
                "AI system tools are not allowed for selected agents: "
                + ", ".join(sorted(inaccessible))
            )
        data_environments = self._strings(
            requirements.get("data_environments"), field="data_environments",
            minimum=1, maximum=4, max_chars=32,
            allowed=self._DATA_ENVIRONMENTS,
        )
        interfaces = self._strings(
            requirements.get("interfaces"), field="interfaces", minimum=1,
            maximum=7, max_chars=32, allowed=self._INTERFACES,
        )
        workflow = self._strings(
            requirements.get("workflow"), field="workflow", minimum=1,
            maximum=20, max_chars=300,
        )
        return AISystemBlueprint(
            protocol_version=self.PROTOCOL,
            name=name,
            purpose=purpose.strip(),
            model_routes=self._model_routes(requirements.get("model_requirements")),
            agents=agents,
            tools=tools,
            data_environments=data_environments,
            interfaces=interfaces,
            workflow=workflow,
            evaluations=self._evaluations(requirements.get("evaluations")),
            deployment=self._deployment(requirements.get("deployment")),
            static_checks=(
                "requirements_schema", "model_capability_routes",
                "model_modality_routes", "agent_registry_references",
                "tool_registry_references", "agent_tool_access",
                "environment_separation", "evaluation_schema",
                "deployment_schema",
            ),
        )

    @staticmethod
    def _files(blueprint: AISystemBlueprint) -> dict[str, str]:
        value = blueprint.to_dict()
        manifest = json.dumps(
            value, ensure_ascii=False, separators=(",", ":"),
            sort_keys=True, allow_nan=False,
        ) + "\n"
        readme = (
            f"# {blueprint.name}\n\n"
            f"{blueprint.purpose}\n\n"
            "This workspace was generated from SPARKLE-AI-SYSTEM-BLUEPRINT/1.\n"
            "It is a statically validated architecture scaffold, not evidence of "
            "runtime evaluation or external deployment.\n"
        )
        return {
            "README.md": readme,
            "SPARKLE_AI_SYSTEM.json": manifest,
        }

    def build(
        self, requirements: dict[str, Any], *, approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("AI system materialization requires explicit approval")
        blueprint = self.prepare(requirements)
        blueprint_id = self.store.create(requirements, blueprint)
        try:
            build = self.workspaces.scaffold(
                blueprint.name, self._files(blueprint), overwrite=False,
            )
        except Exception as exc:
            self.store.finish(
                blueprint_id,
                status="materialization_failed",
                error_type=type(exc).__name__,
            )
            raise
        self.store.finish(
            blueprint_id,
            status="materialized_static_verified",
            workspace_build_id=build["build_id"],
        )
        value = blueprint.to_dict()
        value.update({
            "blueprint_id": blueprint_id,
            "workspace_build_id": build["build_id"],
            "workspace": build["workspace"],
            "files": build["files"],
            "status": "materialized_static_verified",
        })
        return value
