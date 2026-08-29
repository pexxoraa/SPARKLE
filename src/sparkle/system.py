from __future__ import annotations

from pathlib import Path
from typing import Any

from sparkle.agents import AgentRegistry, AgentRouter, GeneratedAgentStore
from sparkle.automation import AutomationRunner, AutomationStore, ProactiveEngine
from sparkle.builders import WorkspaceManager
from sparkle.config import AppConfig, data_root, project_root
from sparkle.context import ContextBuilder
from sparkle.development import DevelopmentVerifier
from sparkle.knowledge import KnowledgeIngestor
from sparkle.orchestrator import Orchestrator
from sparkle.presence import PresenceEngine
from sparkle.registry import ModelRegistry, ModelRouter
from sparkle.secrets import SecretResolver
from sparkle.security import APIAccessPolicy
from sparkle.storage import KnowledgeStore, MemoryStore
from sparkle.tooling import (
    AgentInstallTool,
    CalculatorTool,
    FileReadTool,
    KnowledgeSearchTool,
    MemorySearchTool,
    MemoryWriteTool,
    ToolRegistry,
    WorkspaceScaffoldTool,
    WorkspaceVerifyTool,
)
from sparkle.trace import TraceStore
from sparkle.voice import VoiceService


class SparkleSystem:
    def __init__(self, *, config: AppConfig | None = None, model_registry: ModelRegistry | None = None):
        self.config = config or AppConfig.load()
        self.secret_resolver = SecretResolver()
        self.api_access = APIAccessPolicy(
            self.secret_resolver,
            required=self.config.api_auth_required,
            token_refs=self.config.api_token_refs,
            allowed_origins=self.config.allowed_origins,
        )
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
        self.context = ContextBuilder(
            self.memory, self.knowledge,
            memory_limit=self.config.memory_results,
            knowledge_limit=self.config.knowledge_results,
        )
        self.workspaces = WorkspaceManager()
        self.development = DevelopmentVerifier(self.workspaces.root)
        self.tools = ToolRegistry()
        self.tools.register(CalculatorTool())
        self.tools.register(MemorySearchTool(self.memory))
        self.tools.register(MemoryWriteTool(self.memory))
        self.tools.register(KnowledgeSearchTool(self.knowledge))
        self.tools.register(FileReadTool(project_root()))
        self.tools.register(WorkspaceScaffoldTool(self.workspaces))
        self.tools.register(WorkspaceVerifyTool(self.development))
        self.generated_agents = GeneratedAgentStore()
        self.agents = AgentRegistry(
            self.generated_agents,
            allowed_tools=self.tools.names | {"agent_install"},
        )
        self.tools.register(AgentInstallTool(self.agents))
        self.agent_router = AgentRouter(self.agents)
        self.orchestrator = Orchestrator(
            models=self.model_router, agents=self.agents, agent_router=self.agent_router,
            context=self.context, tools=self.tools, traces=self.traces,
            max_tool_rounds=self.config.max_tool_rounds,
        )
        self.automation_runner = AutomationRunner(
            self.automations, self.orchestrator, self.proactive,
        )

    def status(self) -> dict[str, Any]:
        models = self.models.list()
        return {
            "name": "SPARKLE",
            "version": "0.6.0-alpha.1",
            "status": "ready" if any(model["configured"] for model in models) else "limited",
            "active_model": self.models.active_id,
            "models": models,
            "memory": {"status": "ready", "records": len(self.memory.recent(limit=100))},
            "knowledge": {"status": "ready", **self.knowledge.stats()},
            "trace": {"status": "ready", "recent": len(self.traces.recent(limit=100))},
            "agents": self.agents.list(),
            "generated_agents": {
                "status": "ready",
                "count": sum(1 for agent in self.agents.list() if agent["source"] == "generated"),
            },
            "tools": self.tools.status(),
            "api_security": self.api_access.status(),
            "voice": self.voice.status(),
            "automation": {
                "status": "ready", "count": len(self.automations.list()),
                "recent_runs": len(self.automations.list_runs(limit=100)),
            },
            "builders": {
                "status": "ready", "workspaces": len(self.workspaces.list(limit=100)),
                "verifications": len(self.development.list(limit=100)),
                "static_verification": True,
                "arbitrary_command_execution": False,
            },
            "proactive_alerts": self.proactive.inspect(),
            "presence": self.presence.status(),
            "data_root": str(data_root()),
        }
