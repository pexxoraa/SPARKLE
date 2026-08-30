from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sparkle.agents import AgentRegistry, AgentRouter, AgentSpec
from sparkle.config import data_root
from sparkle.storage import SQLiteStore, utc_now


@dataclass(frozen=True, slots=True)
class AgentEvaluationCase:
    name: str
    prompt: str
    expected_route: str


@dataclass(frozen=True, slots=True)
class AgentBlueprint:
    protocol_version: str
    manifest: AgentSpec
    workflow: tuple[str, ...]
    guardrails: tuple[str, ...]
    evaluations: tuple[AgentEvaluationCase, ...]
    static_checks: tuple[str, ...]
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "manifest": {
                "name": self.manifest.name,
                "capability": self.manifest.capability,
                "purpose": self.manifest.purpose,
                "instructions": self.manifest.instructions,
                "tools": sorted(self.manifest.tools),
                "keywords": list(self.manifest.keywords),
            },
            "workflow": list(self.workflow),
            "guardrails": list(self.guardrails),
            "evaluations": [asdict(case) for case in self.evaluations],
            "static_checks": list(self.static_checks),
            "status": self.status,
            "semantic_evaluation_executed": False,
            "external_deployment_executed": False,
        }


class AgentBlueprintStore(SQLiteStore):
    def __init__(self, path: Path | None = None):
        super().__init__(
            path or data_root() / "data_environment" / "agent_blueprints.sqlite3"
        )
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS agent_blueprints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT NOT NULL,
                    requirements_json TEXT NOT NULL,
                    blueprint_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def save(
        self, agent_name: str, requirements: dict[str, Any], blueprint: AgentBlueprint,
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
                INSERT INTO agent_blueprints(
                    agent_name, requirements_json, blueprint_json, status, created_at
                ) VALUES(?,?,?,?,?)
            """, (
                agent_name, requirements_json, blueprint_json,
                "installed_static_verified", now,
            ))
        return int(cursor.lastrowid)

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT id, agent_name, blueprint_json, status, created_at
                FROM agent_blueprints ORDER BY id DESC LIMIT ?
            """, (max(1, min(limit, 100)),)).fetchall()
        return [
            {
                "blueprint_id": row["id"],
                "agent_name": row["agent_name"],
                "blueprint": json.loads(row["blueprint_json"]),
                "status": row["status"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]


class AgentBlueprintBuilder:
    PROTOCOL = "SPARKLE-AGENT-BLUEPRINT/1"
    MAX_REQUIREMENTS_BYTES = 32_000
    _CASE_NAME = re.compile(r"[a-z][a-z0-9_-]{1,63}\Z")
    _ALLOWED_FIELDS = {
        "name", "capability", "purpose", "tools", "keywords", "workflow",
        "guardrails", "evaluations",
    }

    def __init__(self, registry: AgentRegistry, store: AgentBlueprintStore):
        self.registry = registry
        self.store = store

    @staticmethod
    def _strings(
        value: Any,
        *,
        field: str,
        minimum: int,
        maximum: int,
        max_chars: int,
        unique: bool = False,
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
                f"Agent blueprint {field} must contain {minimum}-{maximum} "
                f"strings of at most {max_chars} characters"
            )
        normalized = tuple(item.strip() for item in value)
        if unique and len({item.casefold() for item in normalized}) != len(normalized):
            raise ValueError(f"Agent blueprint {field} must not contain duplicates")
        return normalized

    def prepare(self, requirements: dict[str, Any]) -> AgentBlueprint:
        if not isinstance(requirements, dict):
            raise ValueError("Agent blueprint requirements must be an object")
        unknown = set(requirements) - self._ALLOWED_FIELDS
        if unknown:
            raise ValueError(
                "Unsupported agent blueprint fields: " + ", ".join(sorted(unknown))
            )
        try:
            encoded = json.dumps(
                requirements, ensure_ascii=False, separators=(",", ":"),
                sort_keys=True, allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("Agent blueprint requirements must contain JSON values") from exc
        if len(encoded) > self.MAX_REQUIREMENTS_BYTES:
            raise ValueError("Agent blueprint requirements exceed 32000 bytes")

        for field in ("name", "capability", "purpose"):
            if not isinstance(requirements.get(field), str):
                raise ValueError(f"Agent blueprint {field} must be a string")

        workflow = self._strings(
            requirements.get("workflow"), field="workflow",
            minimum=1, maximum=20, max_chars=300,
        )
        guardrails = self._strings(
            requirements.get("guardrails"), field="guardrails",
            minimum=1, maximum=20, max_chars=300,
        )
        keywords = self._strings(
            requirements.get("keywords"), field="keywords",
            minimum=1, maximum=30, max_chars=80,
            unique=True,
        )
        tools = self._strings(
            requirements.get("tools", []), field="tools",
            minimum=0, maximum=20, max_chars=64,
            unique=True,
        )

        raw_evaluations = requirements.get("evaluations")
        if not isinstance(raw_evaluations, list) or not 1 <= len(raw_evaluations) <= 20:
            raise ValueError("Agent blueprint evaluations must contain 1-20 cases")
        evaluations: list[AgentEvaluationCase] = []
        evaluation_names: set[str] = set()
        for value in raw_evaluations:
            if not isinstance(value, dict) or set(value) != {"name", "prompt"}:
                raise ValueError("Agent evaluation cases require only name and prompt")
            name = value.get("name")
            prompt = value.get("prompt")
            if not isinstance(name, str) or self._CASE_NAME.fullmatch(name) is None:
                raise ValueError("Agent evaluation case name is invalid")
            if name in evaluation_names:
                raise ValueError("Agent evaluation case names must be unique")
            evaluation_names.add(name)
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt.strip()) > 2_000:
                raise ValueError("Agent evaluation prompt must contain 1-2000 characters")
            if not any(
                re.search(rf"\b{re.escape(keyword)}\b", prompt, re.IGNORECASE)
                for keyword in keywords
            ):
                raise ValueError(
                    f"Agent evaluation case lacks a routing keyword: {name}"
                )
            evaluations.append(AgentEvaluationCase(
                name=name, prompt=prompt.strip(),
                expected_route=str(requirements.get("name", "")),
            ))

        instructions = (
            "Execute this workflow:\n"
            + "\n".join(
                f"{index}. {step}" for index, step in enumerate(workflow, 1)
            )
            + "\nGuardrails:\n"
            + "\n".join(f"- {guardrail}" for guardrail in guardrails)
        )
        spec = AgentSpec(
            name=requirements["name"],
            capability=requirements["capability"],
            purpose=requirements["purpose"],
            instructions=instructions,
            tools=frozenset(tools),
            keywords=keywords,
        )
        self.registry.validate(spec)
        if spec.name in self.registry.names:
            raise ValueError(f"Agent already exists: {spec.name}")
        for case in evaluations:
            scores = [
                (
                    AgentRouter.score(case.prompt, self.registry.get(name)),
                    name,
                )
                for name in self.registry.names
            ]
            scores.append((AgentRouter.score(case.prompt, spec), spec.name))
            selected_score, selected_name = max(scores)
            if selected_score <= 0 or selected_name != spec.name:
                raise ValueError(
                    "Agent evaluation case does not route to the candidate: "
                    f"{case.name}"
                )
        return AgentBlueprint(
            protocol_version=self.PROTOCOL,
            manifest=spec,
            workflow=workflow,
            guardrails=guardrails,
            evaluations=tuple(evaluations),
            static_checks=(
                "manifest_schema", "registered_tools", "routing_keyword_coverage",
                "workflow_guardrails", "evaluation_schema",
                "deterministic_routing_cases",
            ),
            status="prepared_static_verified",
        )

    def build(
        self, requirements: dict[str, Any], *, approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Agent blueprint installation requires explicit approval")
        blueprint = self.prepare(requirements)
        self.registry.install(blueprint.manifest)
        try:
            blueprint_id = self.store.save(
                blueprint.manifest.name, requirements, blueprint,
            )
        except Exception:
            self.registry.remove(blueprint.manifest.name)
            raise
        value = blueprint.to_dict()
        value["status"] = "installed_static_verified"
        value["blueprint_id"] = blueprint_id
        return value
