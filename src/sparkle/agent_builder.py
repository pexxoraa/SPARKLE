from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sparkle.agents import AgentRegistry, AgentRouter, AgentSpec
from sparkle.config import data_root
from sparkle.storage import SQLiteStore, utc_now


@dataclass(frozen=True, slots=True)
class AgentResponseAssertions:
    contains_all: tuple[str, ...] = ()
    contains_any: tuple[str, ...] = ()
    excludes_all: tuple[str, ...] = ()
    min_chars: int | None = None
    max_chars: int | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {}
        if self.contains_all:
            value["contains_all"] = list(self.contains_all)
        if self.contains_any:
            value["contains_any"] = list(self.contains_any)
        if self.excludes_all:
            value["excludes_all"] = list(self.excludes_all)
        if self.min_chars is not None:
            value["min_chars"] = self.min_chars
        if self.max_chars is not None:
            value["max_chars"] = self.max_chars
        return value


@dataclass(frozen=True, slots=True)
class AgentEvaluationCase:
    name: str
    prompt: str
    expected_route: str
    assertions: AgentResponseAssertions | None = None

    def to_dict(self) -> dict[str, Any]:
        value = {
            "name": self.name,
            "prompt": self.prompt,
            "expected_route": self.expected_route,
        }
        if self.assertions is not None:
            value["assertions"] = self.assertions.to_dict()
        return value


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
            "evaluations": [case.to_dict() for case in self.evaluations],
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

    def latest_requirements(self, agent_name: str) -> tuple[int, dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute("""
                SELECT id, requirements_json FROM agent_blueprints
                WHERE agent_name=? ORDER BY id DESC LIMIT 1
            """, (agent_name,)).fetchone()
        if row is None:
            raise KeyError(f"No Agent Blueprint exists for: {agent_name}")
        requirements = json.loads(row["requirements_json"])
        if not isinstance(requirements, dict):
            raise ValueError("Stored Agent Blueprint requirements are invalid")
        return int(row["id"]), requirements


class AgentBlueprintBuilder:
    PROTOCOL = "SPARKLE-AGENT-BLUEPRINT/1"
    MAX_REQUIREMENTS_BYTES = 32_000
    _CASE_NAME = re.compile(r"[a-z][a-z0-9_-]{1,63}\Z")
    _ALLOWED_FIELDS = {
        "name", "capability", "purpose", "tools", "keywords", "workflow",
        "guardrails", "evaluations",
    }
    _ASSERTION_FIELDS = {
        "contains_all", "contains_any", "excludes_all", "min_chars",
        "max_chars",
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

    def _assertions(self, value: Any) -> AgentResponseAssertions | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("Agent evaluation assertions must be an object")
        unknown = set(value) - self._ASSERTION_FIELDS
        if unknown:
            raise ValueError(
                "Unsupported agent evaluation assertions: "
                + ", ".join(sorted(unknown))
            )
        collections: dict[str, tuple[str, ...]] = {}
        for field in ("contains_all", "contains_any", "excludes_all"):
            collections[field] = (
                self._strings(
                    value[field], field=f"assertions.{field}",
                    minimum=1, maximum=10, max_chars=200, unique=True,
                )
                if field in value else ()
            )
        bounds: dict[str, int | None] = {}
        for field in ("min_chars", "max_chars"):
            raw = value.get(field)
            if raw is not None and (
                isinstance(raw, bool) or not isinstance(raw, int)
                or not 0 <= raw <= 100_000
            ):
                raise ValueError(
                    f"Agent evaluation {field} must be an integer from 0 to 100000"
                )
            bounds[field] = raw
        if (
            bounds["min_chars"] is not None
            and bounds["max_chars"] is not None
            and bounds["min_chars"] > bounds["max_chars"]
        ):
            raise ValueError("Agent evaluation character bounds are reversed")
        if not any(collections.values()) and all(
            item is None for item in bounds.values()
        ):
            raise ValueError("Agent evaluation assertions cannot be empty")
        return AgentResponseAssertions(
            contains_all=collections["contains_all"],
            contains_any=collections["contains_any"],
            excludes_all=collections["excludes_all"],
            min_chars=bounds["min_chars"],
            max_chars=bounds["max_chars"],
        )

    def _prepare(
        self, requirements: dict[str, Any], *, allow_existing: bool,
    ) -> AgentBlueprint:
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
            if (
                not isinstance(value, dict)
                or not {"name", "prompt"} <= set(value)
                or set(value) - {"name", "prompt", "assertions"}
            ):
                raise ValueError(
                    "Agent evaluation cases require name, prompt, and optional assertions"
                )
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
                assertions=self._assertions(value.get("assertions")),
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
        if spec.name in self.registry.names and not allow_existing:
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

    def prepare(self, requirements: dict[str, Any]) -> AgentBlueprint:
        return self._prepare(requirements, allow_existing=False)

    def validate_installed(
        self, requirements: dict[str, Any],
    ) -> AgentBlueprint:
        blueprint = self._prepare(requirements, allow_existing=True)
        try:
            installed = self.registry.get(blueprint.manifest.name)
        except KeyError as exc:
            raise ValueError("Agent Blueprint agent is not installed") from exc
        if installed != blueprint.manifest:
            raise ValueError(
                "Installed agent no longer matches the latest Agent Blueprint"
            )
        return blueprint

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
