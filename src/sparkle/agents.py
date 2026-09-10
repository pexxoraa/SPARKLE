from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from sparkle.config import data_root
from sparkle.storage import SQLiteStore, utc_now


@dataclass(frozen=True, slots=True)
class AgentSpec:
    name: str
    capability: str
    purpose: str
    instructions: str
    tools: frozenset[str]
    keywords: tuple[str, ...]

    def system_prompt(self) -> str:
        return (
            f"You are SPARKLE's {self.name}. Purpose: {self.purpose}\n"
            f"Operating instructions: {self.instructions}\n"
            "Distinguish facts, inferences, opinions, and uncertainty. Never claim an action or test occurred unless tool evidence confirms it. "
            "Use only relevant retrieved context. Store durable memory only when the user explicitly asks or the fact materially improves future assistance."
        )


def _specs() -> list[AgentSpec]:
    shared = frozenset({"calculator", "memory_search", "knowledge_search"})
    project_read = frozenset({"project_search"})
    skill_read = frozenset({"skill_search"})
    return [
        AgentSpec("personal", "reasoning", "Coordinate personal goals, priorities, context, and specialist work.", "Give realistic priorities and explicitly identify missing constraints.", shared | project_read | skill_read | {"memory_write"}, ("goal", "priority", "today", "tomorrow", "personal", "focus", "week")),
        AgentSpec("learning", "reasoning", "Teach concepts with active recall, exercises, correction, and retesting.", "Use the explain → ask → test → correct → apply → retest loop and inspect structured mastery evidence before choosing practice.", shared | skill_read | {"memory_write"}, ("learn", "teach", "explain", "lesson", "practice", "quiz", "concept")),
        AgentSpec("skill", "reasoning", "Plan and assess evidence-based skill mastery levels 0 through 6.", "Use structured mastery summaries; require demonstrations, projects, or tests backed by verified questions, exercises, implementations, or independent problem solving before claiming progress.", shared | skill_read | {"memory_write"}, ("skill", "mastery", "level", "practice plan")),
        AgentSpec("exam", "reasoning", "Manage syllabus, practice, timed tests, revision, and error analysis.", "Track accuracy, speed, attempts, weak topics, error categories, and coverage.", shared | {"memory_write"}, ("exam", "syllabus", "mock", "revision", "marks", "accuracy")),
        AgentSpec("research", "reasoning", "Collect, cross-check, synthesize, and cite research.", "Never invent sources; label uncertainty and separate evidence from inference. Use knowledge_verify with the retrieved citation_digest for exact stored quotes; integrity does not establish truth.", shared | {"knowledge_verify"}, ("research", "source", "paper", "compare", "evidence", "latest")),
        AgentSpec("coding", "coding", "Implement, debug, test, and review code.", "Prefer runnable changes, narrow diffs, and execution evidence.", shared | {"file_read", "workspace_verify"}, ("code", "python", "javascript", "typescript", "debug", "function", "program")),
        AgentSpec("software_engineering", "coding", "Design and maintain reliable software systems.", "Address architecture, security, tests, operations, and maintainability.", shared | {"file_read", "workspace_verify"}, ("software", "repository", "architecture", "refactor", "dependency", "release")),
        AgentSpec("application_builder", "coding", "Build complete desktop, web, mobile, CLI, and data applications.", "Cover requirements, UX, implementation, testing, packaging, and deployment.", shared | {"file_read", "workspace_scaffold", "workspace_verify", "workspace_package"}, ("app", "website", "dashboard", "frontend", "backend", "mobile", "desktop", "api")),
        AgentSpec("ai_builder", "reasoning", "Build complete model-agnostic AI systems.", "Define model, data, evaluation, agent, tool, storage, UI, and deployment boundaries.", shared | {"file_read", "workspace_scaffold", "workspace_verify", "workspace_package"}, ("ai system", "rag", "embedding", "model", "evaluation", "multimodal")),
        AgentSpec("agent_builder", "reasoning", "Design, implement, test, and deploy modular AI agents.", "Specify purpose, tools, memory, model needs, workflows, guardrails, and evaluation.", shared | {"file_read", "agent_install", "workspace_scaffold", "workspace_verify", "workspace_package"}, ("agent", "multi-agent", "orchestrator", "tool calling")),
        AgentSpec("project", "reasoning", "Track projects from idea through review.", "Use structured project evidence to track status, priority, deadline, dependencies, risks, milestones, blockers, and next action.", shared | project_read | {"memory_write"}, ("project", "milestone", "deadline", "blocker", "roadmap", "task")),
        AgentSpec("data_analysis", "reasoning", "Clean, analyze, visualize, forecast, and report data.", "State assumptions and use suitable statistics; do not overstate causal claims.", shared | {"file_read"}, ("data", "csv", "spreadsheet", "analysis", "chart", "statistics", "forecast")),
        AgentSpec("content", "reasoning", "Develop researched content, scripts, hooks, visuals, and publishing workflows.", "Preserve evidence standards while adapting to audience and platform.", shared | {"memory_write"}, ("content", "video", "script", "youtube", "hook", "thumbnail", "publish")),
        AgentSpec("productivity", "reasoning", "Turn priorities into realistic, actionable work plans.", "Protect deep work, respect available time, use structured project evidence, and avoid overloaded schedules.", shared | project_read | {"memory_write"}, ("productivity", "schedule", "plan my day", "time", "habit")),
        AgentSpec("automation", "tool_use", "Design and operate explicit, observable automations.", "Require a defined trigger, action, failure policy, and owner.", shared | {"memory_write"}, ("automate", "automation", "recurring", "monitor", "remind", "schedule")),
        AgentSpec("system", "reasoning", "Diagnose SPARKLE configuration, runtime, security, and operations.", "Do not expose secrets; distinguish configured, reachable, tested, and verified states.", shared | {"file_read"}, ("system", "status", "config", "environment", "trace", "health", "failure")),
    ]


class GeneratedAgentStore(SQLiteStore):
    """Persists user-created agent specifications outside application source."""

    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "data_environment" / "generated_agents.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS generated_agents (
                    name TEXT PRIMARY KEY,
                    capability TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    instructions TEXT NOT NULL,
                    tools_json TEXT NOT NULL,
                    keywords_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def save(self, spec: AgentSpec, *, replace: bool = False) -> None:
        now = utc_now()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT 1 FROM generated_agents WHERE name=?", (spec.name,)
            ).fetchone()
            if existing and not replace:
                raise ValueError(f"Generated agent already exists: {spec.name}")
            connection.execute("""
                INSERT INTO generated_agents(
                    name, capability, purpose, instructions, tools_json,
                    keywords_json, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET
                    capability=excluded.capability,
                    purpose=excluded.purpose,
                    instructions=excluded.instructions,
                    tools_json=excluded.tools_json,
                    keywords_json=excluded.keywords_json,
                    updated_at=excluded.updated_at
            """, (
                spec.name, spec.capability, spec.purpose, spec.instructions,
                json.dumps(sorted(spec.tools), separators=(",", ":")),
                json.dumps(list(spec.keywords), separators=(",", ":")),
                now, now,
            ))

    def delete(self, name: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM generated_agents WHERE name=?", (name,))
        return cursor.rowcount == 1

    def load(self) -> list[AgentSpec]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM generated_agents ORDER BY name"
            ).fetchall()
        return [self._spec(row) for row in rows]

    @staticmethod
    def _spec(row: sqlite3.Row) -> AgentSpec:
        return AgentSpec(
            name=row["name"], capability=row["capability"], purpose=row["purpose"],
            instructions=row["instructions"], tools=frozenset(json.loads(row["tools_json"])),
            keywords=tuple(json.loads(row["keywords_json"])),
        )


class AgentRegistry:
    NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
    CAPABILITIES = {"general", "reasoning", "coding", "tool_use", "vision"}

    def __init__(
        self,
        store: GeneratedAgentStore | None = None,
        *,
        allowed_tools: set[str] | None = None,
    ):
        builtins = _specs()
        self._agents = {spec.name: spec for spec in builtins}
        self._builtin_names = set(self._agents)
        self.store = store
        self.allowed_tools = set(allowed_tools) if allowed_tools is not None else None
        if self.store:
            for spec in self.store.load():
                self._validate(spec)
                if spec.name in self._builtin_names:
                    raise ValueError(f"Generated agent cannot replace a built-in agent: {spec.name}")
                self._agents[spec.name] = spec

    def _validate(self, spec: AgentSpec) -> None:
        if not self.NAME_PATTERN.fullmatch(spec.name):
            raise ValueError("Agent name must be a 2-64 character lowercase identifier")
        if spec.capability not in self.CAPABILITIES:
            raise ValueError(f"Unsupported agent capability: {spec.capability}")
        if not 10 <= len(spec.purpose.strip()) <= 500:
            raise ValueError("Agent purpose must contain 10-500 characters")
        if not 10 <= len(spec.instructions.strip()) <= 4_000:
            raise ValueError("Agent instructions must contain 10-4000 characters")
        if not spec.keywords or len(spec.keywords) > 30:
            raise ValueError("Agent must define 1-30 routing keywords")
        if any(not keyword.strip() or len(keyword) > 80 for keyword in spec.keywords):
            raise ValueError("Agent keywords must contain 1-80 characters")
        if self.allowed_tools is not None:
            unknown = set(spec.tools) - self.allowed_tools
            if unknown:
                raise ValueError(f"Agent references unknown tools: {', '.join(sorted(unknown))}")

    def validate(self, spec: AgentSpec) -> None:
        """Validate a generated specification without mutating the registry."""
        self._validate(spec)
        if spec.name in self._builtin_names:
            raise ValueError(f"Generated agent cannot replace a built-in agent: {spec.name}")

    def install(self, spec: AgentSpec, *, replace: bool = False) -> AgentSpec:
        if not self.store:
            raise RuntimeError("Generated-agent persistence is not configured")
        self._validate(spec)
        if spec.name in self._builtin_names:
            raise ValueError(f"Cannot replace built-in agent: {spec.name}")
        if spec.name in self._agents and not replace:
            raise ValueError(f"Agent already exists: {spec.name}")
        self.store.save(spec, replace=replace)
        self._agents[spec.name] = spec
        return spec

    def remove(self, name: str) -> bool:
        if name in self._builtin_names:
            raise ValueError(f"Cannot remove built-in agent: {name}")
        if not self.store:
            raise RuntimeError("Generated-agent persistence is not configured")
        removed = self.store.delete(name)
        self._agents.pop(name, None)
        return removed

    def get(self, name: str) -> AgentSpec:
        try:
            return self._agents[name]
        except KeyError as exc:
            raise KeyError(f"Unknown agent: {name}") from exc

    def list(self) -> list[dict[str, object]]:
        return [
            {
                "name": item.name,
                "capability": item.capability,
                "purpose": item.purpose,
                "tools": sorted(item.tools),
                "source": "built_in" if item.name in self._builtin_names else "generated",
            }
            for item in sorted(self._agents.values(), key=lambda spec: spec.name)
        ]

    @property
    def names(self) -> set[str]:
        return set(self._agents)


class AgentRouter:
    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    @staticmethod
    def _score(text: str, spec: AgentSpec) -> int:
        lowered = text.lower()
        return sum(2 if " " in keyword else 1 for keyword in spec.keywords if re.search(rf"\b{re.escape(keyword)}\b", lowered))

    @classmethod
    def score(cls, text: str, spec: AgentSpec) -> int:
        """Return the deterministic production routing score for a manifest."""
        return cls._score(text, spec)

    def rank(self, text: str) -> list[tuple[int, AgentSpec]]:
        ranked = [(self.score(text, self.registry.get(name)), self.registry.get(name)) for name in self.registry.names]
        return sorted(ranked, key=lambda item: (item[0], item[1].name), reverse=True)

    def select(self, text: str) -> AgentSpec:
        score, spec = self.rank(text)[0]
        return spec if score else self.registry.get("personal")

    def select_many(self, text: str, *, limit: int = 4) -> list[AgentSpec]:
        ranked = [(score, spec) for score, spec in self.rank(text) if score > 0]
        selected = [spec for _, spec in ranked[:max(1, limit)]]
        return selected or [self.registry.get("personal")]
