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
            "When a deterministic tool directly matches a requested calculation, retrieval, persistence action, or verification, prefer that tool over unaudited mental completion or indirect inspection. "
            "Choose the narrowest sufficient tool, use its observation, and do not repeat an identical call unless new evidence changes the arguments. "
            "Use only relevant retrieved context. Store durable memory only when the user explicitly asks or the fact materially improves future assistance."
        )


def _specs() -> list[AgentSpec]:
    shared = frozenset({"calculator", "memory_search", "knowledge_search"})
    project_read = frozenset({"project_search", "project_tasks"})
    skill_read = frozenset({"skill_search", "learning_progress"})
    engineering_read = frozenset({"engineering_inspect"})
    return [
        AgentSpec("personal", "reasoning", "Coordinate personal goals, priorities, context, and specialist work.", "Give realistic priorities and explicitly identify missing constraints. For requested exact arithmetic use calculator; for an explicit durable-memory request use memory_write once; when asked to verify that a safe tool rejects an invalid operation, invoke that tool once and report its observed failure rather than refusing without evidence.", shared | project_read | skill_read | {"memory_write"}, ("goal", "priority", "today", "tomorrow", "personal", "focus", "week")),
        AgentSpec("learning", "reasoning", "Teach concepts with active recall, exercises, correction, and retesting.", "Use the explain → ask → test → correct → apply → retest loop and inspect structured mastery evidence before choosing practice. For an explicit learning-memory record use memory_write once; for a direct source lookup use knowledge_search and cite its returned source identity; use learning_progress only for named curriculum or learner-progress state.", shared | skill_read | {"memory_write"}, ("learn", "teach", "explain", "lesson", "practice", "quiz", "concept")),
        AgentSpec("skill", "reasoning", "Plan and assess evidence-based skill mastery levels 0 through 6.", "Use structured mastery summaries; require demonstrations, projects, or tests backed by verified questions, exercises, implementations, or independent problem solving before claiming progress.", shared | skill_read | {"memory_write"}, ("skill", "mastery", "level", "practice plan")),
        AgentSpec("exam", "reasoning", "Manage syllabus, practice, timed tests, revision, and error analysis.", "Track accuracy, speed, attempts, weak topics, error categories, and coverage. Use persisted learning_progress; practice scores are not verified competence.", shared | skill_read | {"memory_write"}, ("exam", "syllabus", "mock", "revision", "marks", "accuracy")),
        AgentSpec("research", "reasoning", "Collect, cross-check, synthesize, and cite research.", "For direct source questions, call knowledge_search once even when generic retrieved context already contains candidate snippets, then cite the returned source identity and chunk position. Use research_workspace for persistent multi-step work and knowledge_verify only for exact stored quote/digest integrity. Never invent a citation when retrieval returns no evidence. Integrity never establishes claim truth or external source validity.", shared | {"knowledge_verify", "research_workspace"}, ("research", "source", "paper", "compare", "evidence", "latest")),
        AgentSpec("coding", "coding", "Implement, debug, test, and review code.", "Inspect repository identities and engineering plans with engineering_inspect. Prefer runnable changes, narrow diffs, and execution evidence. For explicitly approved static or syntax checks, use workspace_verify directly; use file_read only when source contents themselves are needed.", shared | engineering_read | {"file_read", "workspace_verify"}, ("code", "python", "javascript", "typescript", "debug", "function", "program")),
        AgentSpec("software_engineering", "coding", "Design and maintain reliable software systems.", "Use engineering_inspect for repository structure, work plans, release readiness and debt. Address architecture, security, tests, operations, and maintainability.", shared | engineering_read | {"file_read", "workspace_verify"}, ("software", "repository", "architecture", "refactor", "dependency", "release")),
        AgentSpec("application_builder", "coding", "Build complete desktop, web, mobile, CLI, and data applications.", "Cover requirements, UX, implementation, testing, packaging, and deployment.", shared | engineering_read | {"file_read", "workspace_scaffold", "workspace_verify", "workspace_package"}, ("app", "website", "dashboard", "frontend", "backend", "mobile", "desktop", "api")),
        AgentSpec("ai_builder", "reasoning", "Build complete model-agnostic AI systems.", "Define model, data, evaluation, agent, tool, storage, UI, and deployment boundaries.", shared | engineering_read | {"file_read", "workspace_scaffold", "workspace_verify", "workspace_package"}, ("ai system", "rag", "embedding", "model", "evaluation", "multimodal")),
        AgentSpec("agent_builder", "reasoning", "Design, implement, test, and deploy modular AI agents.", "Specify purpose, tools, memory, model needs, workflows, guardrails, and evaluation.", shared | engineering_read | {"file_read", "agent_install", "workspace_scaffold", "workspace_verify", "workspace_package"}, ("agent", "multi-agent", "orchestrator", "tool calling")),
        AgentSpec("project", "reasoning", "Track projects from idea through review.", "Use structured project evidence to track status, priority, deadline, dependencies, risks, milestones, blockers, and next action.", shared | project_read | {"memory_write"}, ("project", "milestone", "deadline", "blocker", "roadmap", "task")),
        AgentSpec("data_analysis", "reasoning", "Clean, analyze, visualize, forecast, and report data.", "Use data_analyze for deterministic transformations and statistics on imported datasets. State assumptions, preserve recipe evidence, and do not overstate causal or forecasting claims.", shared | {"file_read", "data_analyze"}, ("data", "csv", "spreadsheet", "analysis", "chart", "statistics", "forecast")),
        AgentSpec("content", "reasoning", "Develop researched content, scripts, hooks, visuals, and publishing workflows.", "Use content_search to inspect persistent briefs and drafts. Preserve evidence standards, audience constraints and approval state; do not claim external publication without execution evidence.", shared | {"content_search", "memory_write"}, ("content", "video", "script", "youtube", "hook", "thumbnail", "publish")),
        AgentSpec("productivity", "reasoning", "Turn priorities into realistic, actionable work plans.", "Protect deep work, respect available time, use structured project evidence, and avoid overloaded schedules.", shared | project_read | {"memory_write"}, ("productivity", "schedule", "plan my day", "time", "habit")),
        AgentSpec("automation", "tool_use", "Design and operate explicit, observable automations.", "Use automation_inspect to ground plans in current definitions, run history, retry evidence, and scheduler state. Creation, enable/disable, forced runs, and deletion remain operator-owned through approved API/CLI boundaries.", shared | {"memory_write", "automation_inspect"}, ("automate", "automation", "recurring", "monitor", "remind", "schedule")),
        AgentSpec("system", "reasoning", "Diagnose SPARKLE configuration, runtime, security, and operations.", "Do not expose secrets; distinguish configured, reachable, tested, and verified states.", shared | engineering_read | {"file_read"}, ("system", "status", "config", "environment", "trace", "health", "failure")),
    ]


class GeneratedAgentStore(SQLiteStore):
    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "data_environment" / "generated_agents.sqlite3"); self.initialize()
    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS generated_agents(name TEXT PRIMARY KEY,capability TEXT NOT NULL,purpose TEXT NOT NULL,instructions TEXT NOT NULL,tools_json TEXT NOT NULL,keywords_json TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
    def save(self, spec: AgentSpec, *, replace: bool = False) -> None:
        now=utc_now()
        with self.connect() as c:
            if c.execute("SELECT 1 FROM generated_agents WHERE name=?",(spec.name,)).fetchone() and not replace: raise ValueError(f"Generated agent already exists: {spec.name}")
            c.execute("""INSERT INTO generated_agents VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET capability=excluded.capability,purpose=excluded.purpose,instructions=excluded.instructions,tools_json=excluded.tools_json,keywords_json=excluded.keywords_json,updated_at=excluded.updated_at""",(spec.name,spec.capability,spec.purpose,spec.instructions,json.dumps(sorted(spec.tools),separators=(",",":")),json.dumps(list(spec.keywords),separators=(",",":")),now,now))
    def delete(self,name:str)->bool:
        with self.connect() as c: cursor=c.execute("DELETE FROM generated_agents WHERE name=?",(name,))
        return cursor.rowcount==1
    def load(self)->list[AgentSpec]:
        with self.connect() as c: rows=c.execute("SELECT * FROM generated_agents ORDER BY name").fetchall()
        return [self._spec(r) for r in rows]
    @staticmethod
    def _spec(r:sqlite3.Row)->AgentSpec:
        return AgentSpec(r["name"],r["capability"],r["purpose"],r["instructions"],frozenset(json.loads(r["tools_json"])),tuple(json.loads(r["keywords_json"])))


class AgentRegistry:
    NAME_PATTERN=re.compile(r"^[a-z][a-z0-9_]{1,63}$"); CAPABILITIES={"general","reasoning","coding","tool_use","vision"}
    def __init__(self,store:GeneratedAgentStore|None=None,*,allowed_tools:set[str]|None=None):
        builtins=_specs(); self._agents={s.name:s for s in builtins}; self._builtin_names=set(self._agents); self.store=store; self.allowed_tools=set(allowed_tools) if allowed_tools is not None else None
        if self.store:
            for spec in self.store.load():
                self._validate(spec)
                if spec.name in self._builtin_names: raise ValueError(f"Generated agent cannot replace a built-in agent: {spec.name}")
                self._agents[spec.name]=spec
    def _validate(self,spec:AgentSpec)->None:
        if not self.NAME_PATTERN.fullmatch(spec.name): raise ValueError("Agent name must be a 2-64 character lowercase identifier")
        if spec.capability not in self.CAPABILITIES: raise ValueError(f"Unsupported agent capability: {spec.capability}")
        if not 10<=len(spec.purpose.strip())<=500: raise ValueError("Agent purpose must contain 10-500 characters")
        if not 10<=len(spec.instructions.strip())<=4000: raise ValueError("Agent instructions must contain 10-4000 characters")
        if not spec.keywords or len(spec.keywords)>30: raise ValueError("Agent must define 1-30 routing keywords")
        if any(not k.strip() or len(k)>80 for k in spec.keywords): raise ValueError("Agent keywords must contain 1-80 characters")
        if self.allowed_tools is not None:
            unknown=set(spec.tools)-self.allowed_tools
            if unknown: raise ValueError(f"Agent references unknown tools: {', '.join(sorted(unknown))}")
    def validate(self,spec:AgentSpec)->None:
        self._validate(spec)
        if spec.name in self._builtin_names: raise ValueError(f"Generated agent cannot replace a built-in agent: {spec.name}")
    def install(self,spec:AgentSpec,*,replace:bool=False)->AgentSpec:
        if not self.store: raise RuntimeError("Generated-agent persistence is not configured")
        self._validate(spec)
        if spec.name in self._builtin_names: raise ValueError(f"Cannot replace built-in agent: {spec.name}")
        if spec.name in self._agents and not replace: raise ValueError(f"Agent already exists: {spec.name}")
        self.store.save(spec,replace=replace); self._agents[spec.name]=spec; return spec
    def remove(self,name:str)->bool:
        if name in self._builtin_names: raise ValueError(f"Cannot remove built-in agent: {name}")
        if not self.store: raise RuntimeError("Generated-agent persistence is not configured")
        removed=self.store.delete(name); self._agents.pop(name,None); return removed
    def get(self,name:str)->AgentSpec:
        try:return self._agents[name]
        except KeyError as exc: raise KeyError(f"Unknown agent: {name}") from exc
    def list(self)->list[dict[str,object]]:
        return [{"name":x.name,"capability":x.capability,"purpose":x.purpose,"tools":sorted(x.tools),"source":"built_in" if x.name in self._builtin_names else "generated"} for x in sorted(self._agents.values(),key=lambda s:s.name)]
    @property
    def names(self)->set[str]:return set(self._agents)


class AgentRouter:
    def __init__(self,registry:AgentRegistry):self.registry=registry
    @staticmethod
    def _score(text:str,spec:AgentSpec)->int:
        lowered=text.lower(); return sum(2 if " " in k else 1 for k in spec.keywords if re.search(rf"\b{re.escape(k)}\b",lowered))
    @classmethod
    def score(cls,text:str,spec:AgentSpec)->int:return cls._score(text,spec)
    def rank(self,text:str)->list[tuple[int,AgentSpec]]:
        ranked=[(self.score(text,self.registry.get(n)),self.registry.get(n)) for n in self.registry.names]; return sorted(ranked,key=lambda i:(i[0],i[1].name),reverse=True)
    def select(self,text:str)->AgentSpec:
        score,spec=self.rank(text)[0]; return spec if score else self.registry.get("personal")
    def select_many(self,text:str,*,limit:int=4)->list[AgentSpec]:
        ranked=[(s,p) for s,p in self.rank(text) if s>0]; selected=[p for _,p in ranked[:max(1,limit)]]; return selected or [self.registry.get("personal")]
