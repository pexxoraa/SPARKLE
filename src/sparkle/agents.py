from __future__ import annotations

import re
from dataclasses import dataclass


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
    return [
        AgentSpec("personal", "reasoning", "Coordinate personal goals, priorities, context, and specialist work.", "Give realistic priorities and explicitly identify missing constraints.", shared | {"memory_write"}, ("goal", "priority", "today", "tomorrow", "personal", "focus", "week")),
        AgentSpec("learning", "reasoning", "Teach concepts with active recall, exercises, correction, and retesting.", "Use the explain → ask → test → correct → apply → retest loop.", shared | {"memory_write"}, ("learn", "teach", "explain", "lesson", "practice", "quiz", "concept")),
        AgentSpec("skill", "reasoning", "Plan and assess evidence-based skill mastery levels 0 through 6.", "Require demonstrations, projects, or tests before increasing mastery.", shared | {"memory_write"}, ("skill", "mastery", "level", "practice plan")),
        AgentSpec("exam", "reasoning", "Manage syllabus, practice, timed tests, revision, and error analysis.", "Track accuracy, speed, attempts, weak topics, error categories, and coverage.", shared | {"memory_write"}, ("exam", "syllabus", "mock", "revision", "marks", "accuracy")),
        AgentSpec("research", "reasoning", "Collect, cross-check, synthesize, and cite research.", "Never invent sources; label uncertainty and separate evidence from inference.", shared, ("research", "source", "paper", "compare", "evidence", "latest")),
        AgentSpec("coding", "coding", "Implement, debug, test, and review code.", "Prefer runnable changes, narrow diffs, and execution evidence.", shared | {"file_read"}, ("code", "python", "javascript", "typescript", "debug", "function", "program")),
        AgentSpec("software_engineering", "coding", "Design and maintain reliable software systems.", "Address architecture, security, tests, operations, and maintainability.", shared | {"file_read"}, ("software", "repository", "architecture", "refactor", "dependency", "release")),
        AgentSpec("application_builder", "coding", "Build complete desktop, web, mobile, CLI, and data applications.", "Cover requirements, UX, implementation, testing, packaging, and deployment.", shared | {"file_read"}, ("app", "website", "dashboard", "frontend", "backend", "mobile", "desktop", "api")),
        AgentSpec("ai_builder", "reasoning", "Build complete model-agnostic AI systems.", "Define model, data, evaluation, agent, tool, storage, UI, and deployment boundaries.", shared | {"file_read"}, ("ai system", "rag", "embedding", "model", "evaluation", "multimodal")),
        AgentSpec("agent_builder", "reasoning", "Design, implement, test, and deploy modular AI agents.", "Specify purpose, tools, memory, model needs, workflows, guardrails, and evaluation.", shared | {"file_read"}, ("agent", "multi-agent", "orchestrator", "tool calling")),
        AgentSpec("project", "reasoning", "Track projects from idea through review.", "Track status, priority, deadline, dependencies, risks, milestones, blockers, and next action.", shared | {"memory_write"}, ("project", "milestone", "deadline", "blocker", "roadmap", "task")),
        AgentSpec("data_analysis", "reasoning", "Clean, analyze, visualize, forecast, and report data.", "State assumptions and use suitable statistics; do not overstate causal claims.", shared | {"file_read"}, ("data", "csv", "spreadsheet", "analysis", "chart", "statistics", "forecast")),
        AgentSpec("content", "reasoning", "Develop researched content, scripts, hooks, visuals, and publishing workflows.", "Preserve evidence standards while adapting to audience and platform.", shared | {"memory_write"}, ("content", "video", "script", "youtube", "hook", "thumbnail", "publish")),
        AgentSpec("productivity", "reasoning", "Turn priorities into realistic, actionable work plans.", "Protect deep work, respect available time, and avoid overloaded schedules.", shared | {"memory_write"}, ("productivity", "schedule", "plan my day", "time", "habit")),
        AgentSpec("automation", "tool_use", "Design and operate explicit, observable automations.", "Require a defined trigger, action, failure policy, and owner.", shared | {"memory_write"}, ("automate", "automation", "recurring", "monitor", "remind", "schedule")),
        AgentSpec("system", "reasoning", "Diagnose SPARKLE configuration, runtime, security, and operations.", "Do not expose secrets; distinguish configured, reachable, tested, and verified states.", shared | {"file_read"}, ("system", "status", "config", "environment", "trace", "health", "failure")),
    ]


class AgentRegistry:
    def __init__(self):
        self._agents = {spec.name: spec for spec in _specs()}

    def get(self, name: str) -> AgentSpec:
        try:
            return self._agents[name]
        except KeyError as exc:
            raise KeyError(f"Unknown agent: {name}") from exc

    def list(self) -> list[dict[str, object]]:
        return [{"name": item.name, "capability": item.capability, "purpose": item.purpose} for item in self._agents.values()]

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

    def rank(self, text: str) -> list[tuple[int, AgentSpec]]:
        ranked = [(self._score(text, self.registry.get(name)), self.registry.get(name)) for name in self.registry.names]
        return sorted(ranked, key=lambda item: (item[0], item[1].name), reverse=True)

    def select(self, text: str) -> AgentSpec:
        score, spec = self.rank(text)[0]
        return spec if score else self.registry.get("personal")

    def select_many(self, text: str, *, limit: int = 4) -> list[AgentSpec]:
        ranked = [(score, spec) for score, spec in self.rank(text) if score > 0]
        selected = [spec for _, spec in ranked[:max(1, limit)]]
        return selected or [self.registry.get("personal")]
