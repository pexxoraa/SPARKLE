from __future__ import annotations

from pathlib import Path
from typing import Any

from sparkle.agents import AgentRegistry, AgentRouter
from sparkle.automation import AutomationStore, ProactiveEngine
from sparkle.config import AppConfig, data_root, project_root
from sparkle.context import ContextBuilder
from sparkle.knowledge import KnowledgeIngestor
from sparkle.orchestrator import Orchestrator
from sparkle.presence import PresenceEngine
from sparkle.registry import ModelRegistry, ModelRouter
from sparkle.storage import KnowledgeStore, MemoryStore
from sparkle.tooling import CalculatorTool, FileReadTool, KnowledgeSearchTool, MemorySearchTool, MemoryWriteTool, ToolRegistry
from sparkle.trace import TraceStore
from sparkle.voice import VoiceService


class SparkleSystem:
    def __init__(self, *, config: AppConfig | None = None, model_registry: ModelRegistry | None = None):
        self.config = config or AppConfig.load()
        self.memory = MemoryStore()
        self.knowledge = KnowledgeStore()
        self.knowledge_ingestor = KnowledgeIngestor(self.knowledge)
        self.traces = TraceStore()
        self.automations = AutomationStore()
        self.proactive = ProactiveEngine(self.memory)
        self.presence = PresenceEngine()
        self.voice = VoiceService()
        self.models = model_registry or ModelRegistry()
        self.model_router = ModelRouter(self.models)
        self.agents = AgentRegistry()
        self.agent_router = AgentRouter(self.agents)
        self.context = ContextBuilder(
            self.memory, self.knowledge,
            memory_limit=self.config.memory_results,
            knowledge_limit=self.config.knowledge_results,
        )
        self.tools = ToolRegistry()
        self.tools.register(CalculatorTool())
        self.tools.register(MemorySearchTool(self.memory))
        self.tools.register(MemoryWriteTool(self.memory))
        self.tools.register(KnowledgeSearchTool(self.knowledge))
        self.tools.register(FileReadTool(project_root()))
        self.orchestrator = Orchestrator(
            models=self.model_router, agents=self.agents, agent_router=self.agent_router,
            context=self.context, tools=self.tools, traces=self.traces,
            max_tool_rounds=self.config.max_tool_rounds,
        )

    def status(self) -> dict[str, Any]:
        models = self.models.list()
        return {
            "name": "SPARKLE",
            "version": "0.3.0-alpha.1",
            "status": "ready" if any(model["configured"] for model in models) else "limited",
            "active_model": self.models.active_id,
            "models": models,
            "memory": {"status": "ready", "records": len(self.memory.recent(limit=100))},
            "knowledge": {"status": "ready", **self.knowledge.stats()},
            "trace": {"status": "ready", "recent": len(self.traces.recent(limit=100))},
            "agents": self.agents.list(),
            "tools": self.tools.status(),
            "voice": self.voice.status(),
            "automation": {"status": "ready", "count": len(self.automations.list())},
            "proactive_alerts": self.proactive.inspect(),
            "presence": self.presence.status(),
            "data_root": str(data_root()),
        }
