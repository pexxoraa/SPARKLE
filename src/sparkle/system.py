from __future__ import annotations

from sparkle.memory_review import MemoryReview

from pathlib import Path
from typing import Any

from sparkle.agents import AgentRegistry, AgentRouter, GeneratedAgentStore
from sparkle.agent_builder import AgentBlueprintBuilder, AgentBlueprintStore
from sparkle.agent_evaluation import AgentEvaluationStore, AgentResponseEvaluator
from sparkle.ai_system_builder import AISystemBlueprintBuilder, AISystemBlueprintStore
from sparkle.ai_system_draft import AISystemDraftStore, AISystemRequirementsCompiler
from sparkle.ai_system_plan import (
    AISystemImplementationPlanner,
    AISystemImplementationPlanStore,
)
from sparkle.ai_system_source import (
    AISystemSourceCandidateService,
    ProviderDisclosureStore,
    SourceCandidateStore,
    SourceCandidateWorkspace,
)
from sparkle.ai_system_runtime import CandidateRuntimeEvaluator, RuntimeEvaluationStore
from sparkle.ai_system_promotion import (
    ControlledPromotionWorkspace,
    ControlledSourcePromotionService,
    SourcePromotionStore,
)
from sparkle.ai_system_build import (
    ControlledBuildArtifactWorkspace,
    ControlledBuildService,
    ControlledBuildStore,
)
from sparkle.ai_system_execution import ControlledExecutionStore
from sparkle.controlled_execution_cancel import CancellableControlledExecutionService
from sparkle.artifacts import ArtifactManager
from sparkle.automation import AutomationRunner, AutomationStore, ProactiveEngine
from sparkle.builders import WorkspaceManager
from sparkle.config import AppConfig, data_root, project_root
from sparkle.context import ContextBuilder
from sparkle.content import content_contract_status
from sparkle.content_workflow import ContentReadTool, ContentWorkflowService
from sparkle.data_analysis import DataAnalysisService, DataAnalysisTool
from sparkle.development import DevelopmentVerifier, WorkspaceTestRunner
from sparkle.external_worker import ExternalWorkerClient
from sparkle.knowledge import KnowledgeIngestor
from sparkle.interaction import InteractionService
from sparkle.mastery import SkillMasteryStore
from sparkle.notifications import NotificationStore
from sparkle.orchestrator import Orchestrator
from sparkle.presence import PresenceEngine
from sparkle.projects import ProjectStore
from sparkle.project_tasks import ProjectTasks
from sparkle.learning import LearningService
from sparkle.registry import ModelRegistry, ModelRouter
from sparkle.secrets import SecretResolver
from sparkle.security import (
    APIAccessPolicy,
    APIAuditStore,
    APISessionManager,
    FixedWindowRateLimiter,
)
from sparkle.storage import KnowledgeStore, MemoryStore
from sparkle.tooling import (
    AgentInstallTool,
    CalculatorTool,
    FileReadTool,
    KnowledgeSearchTool,
    KnowledgeVerifyTool,
    MemorySearchTool,
    MemoryProposalTool,
    ProjectSearchTool,
    ProjectTasksTool,
    LearningReadTool,
    SkillSearchTool,
    ToolRegistry,
    WorkspaceScaffoldTool,
    WorkspacePackageTool,
    ExternalWorkspaceTestTool,
    WorkspaceTestTool,
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
        self.api_rate_limiter = FixedWindowRateLimiter(
            self.config.api_rate_limit_requests,
            self.config.api_rate_limit_window_seconds,
        )
        self.api_sessions = APISessionManager(
            enabled=(self.config.api_auth_required and self.config.session_auth_enabled),
            ttl_seconds=self.config.session_ttl_seconds,
            max_active=self.config.session_max_active,
            cookie_secure=self.config.session_cookie_secure,
        )
        self.api_audit = APIAuditStore()
        self.memory = MemoryStore()
        self.memory_review = MemoryReview(self.memory)
        self.knowledge = KnowledgeStore()
        self.knowledge_ingestor = KnowledgeIngestor(self.knowledge)
        self.traces = TraceStore()
        self.automations = AutomationStore()
        self.notifications = NotificationStore()
        self.projects = ProjectStore()
        self.project_tasks = ProjectTasks(self.projects)
        self.skills = SkillMasteryStore()
        self.learning = LearningService(self.skills)
        self.data_analysis = DataAnalysisService()
        self.content_workflows = ContentWorkflowService()
        self.proactive = ProactiveEngine(self.memory, self.knowledge, self.projects, self.skills)
        self.presence = PresenceEngine()
        self.voice = VoiceService()
        self.interactions = InteractionService()
        self.models = model_registry or ModelRegistry()
        self.model_router = ModelRouter(self.models)
        self.context = ContextBuilder(
            self.memory, self.knowledge,
            memory_limit=self.config.memory_results,
            knowledge_limit=self.config.knowledge_results,
        )
        self.workspaces = WorkspaceManager()
        self.development = DevelopmentVerifier(self.workspaces.root)
        self.artifacts = ArtifactManager(self.workspaces.root)
        self.workspace_tests = WorkspaceTestRunner(
            self.workspaces.root,
            enabled=self.config.workspace_tests_enabled,
            timeout_seconds=self.config.workspace_test_timeout_seconds,
        )
        self.external_worker = ExternalWorkerClient(
            self.workspaces.root,
            enabled=self.config.external_worker_enabled,
            endpoint=self.config.external_worker_url,
            secret_refs=self.config.external_worker_secret_refs,
            expected_worker_id=self.config.external_worker_id,
            request_timeout_seconds=self.config.external_worker_request_timeout_seconds,
            job_timeout_seconds=self.config.external_worker_job_timeout_seconds,
            max_payload_bytes=self.config.external_worker_max_payload_bytes,
            secret_resolver=self.secret_resolver,
        )
        self.external_worker_tool = ExternalWorkspaceTestTool(self.external_worker)
        self.tools = ToolRegistry()
        self.tools.register(CalculatorTool())
        self.tools.register(MemorySearchTool(self.memory))
        self.tools.register(MemoryProposalTool(self.memory_review))
        self.tools.register(KnowledgeSearchTool(self.knowledge))
        self.tools.register(KnowledgeVerifyTool(self.knowledge))
        self.tools.register(ProjectSearchTool(self.projects))
        self.tools.register(ProjectTasksTool(self.project_tasks))
        self.tools.register(LearningReadTool(self.learning))
        self.tools.register(SkillSearchTool(self.skills))
        self.tools.register(DataAnalysisTool(self.data_analysis))
        self.tools.register(ContentReadTool(self.content_workflows))
        self.tools.register(FileReadTool(project_root()))
        self.tools.register(WorkspaceScaffoldTool(self.workspaces))
        self.tools.register(WorkspaceVerifyTool(self.development))
        self.tools.register(WorkspacePackageTool(self.artifacts))
        self.tools.register(WorkspaceTestTool(self.workspace_tests))
        self.generated_agents = GeneratedAgentStore()
        self.agents = AgentRegistry(
            self.generated_agents,
            allowed_tools=self.tools.names | {"agent_install"},
        )
        self.agent_blueprints = AgentBlueprintStore()
        self.agent_builder = AgentBlueprintBuilder(self.agents, self.agent_blueprints)
        self.ai_system_blueprints = AISystemBlueprintStore()
        self.ai_system_builder = AISystemBlueprintBuilder(
            self.models, self.agents, self.tools, self.workspaces,
            self.ai_system_blueprints,
        )
        self.ai_system_implementation_plans = AISystemImplementationPlanStore()
        self.ai_system_planner = AISystemImplementationPlanner(
            self.ai_system_builder, self.workspaces,
            self.ai_system_implementation_plans,
        )
        self.tools.register(AgentInstallTool(self.agents))
        self.agent_router = AgentRouter(self.agents)
        self.orchestrator = Orchestrator(
            models=self.model_router,
            agents=self.agents,
            agent_router=self.agent_router,
            context=self.context,
            tools=self.tools,
            traces=self.traces,
            max_tool_rounds=self.config.max_tool_rounds,
            max_tool_calls=self.config.max_tool_calls,
            max_specialists=self.config.max_specialists,
        )
        self.ai_system_drafts = AISystemDraftStore()
        self.ai_system_compiler = AISystemRequirementsCompiler(
            self.ai_system_builder, self.orchestrator, self.ai_system_drafts,
        )
        self.source_provider_disclosures = ProviderDisclosureStore()
        self.source_candidates = SourceCandidateStore()
        self.source_candidate_workspace = SourceCandidateWorkspace()
        self.ai_system_source_candidates = AISystemSourceCandidateService(
            self.ai_system_planner,
            self.ai_system_implementation_plans,
            self.orchestrator,
            self.traces,
            self.source_provider_disclosures,
            self.source_candidates,
            self.source_candidate_workspace,
        )
        self.runtime_evaluations = RuntimeEvaluationStore()
        self.ai_system_runtime_evaluator = CandidateRuntimeEvaluator(
            self.source_candidates,
            self.source_candidate_workspace,
            self.traces,
            self.runtime_evaluations,
            self.external_worker,
        )
        self.source_promotions = SourcePromotionStore()
        self.source_promotion_workspace = ControlledPromotionWorkspace()
        self.ai_system_source_promoter = ControlledSourcePromotionService(
            self.source_candidates,
            self.source_candidate_workspace,
            self.ai_system_implementation_plans,
            self.runtime_evaluations,
            self.traces,
            self.source_promotions,
            self.source_promotion_workspace,
        )
        self.controlled_builds = ControlledBuildStore()
        self.controlled_build_workspace = ControlledBuildArtifactWorkspace(
            self.source_promotion_workspace,
        )
        self.ai_system_controlled_builder = ControlledBuildService(
            self.source_promotions,
            self.source_candidates,
            self.traces,
            self.controlled_builds,
            self.controlled_build_workspace,
        )
        self.controlled_executions = ControlledExecutionStore()
        self.ai_system_controlled_executor = CancellableControlledExecutionService(
            self.controlled_builds,
            self.controlled_build_workspace,
            self.source_promotions,
            self.source_candidates,
            self.ai_system_implementation_plans,
            self.runtime_evaluations,
            self.traces,
            self.controlled_executions,
            self.external_worker,
        )
        self.agent_evaluations = AgentEvaluationStore()
        self.agent_evaluator = AgentResponseEvaluator(
            self.agent_builder,
            self.agent_blueprints,
            self.orchestrator,
            self.agent_evaluations,
        )
        self.automation_runner = AutomationRunner(
            self.automations,
            self.orchestrator,
            self.proactive,
            self.notifications,
            self.traces,
        )

    def status(self) -> dict[str, Any]:
        models = self.models.list()
        active = next(model for model in models if model["active"])
        recent_model_requests = self.models.runtime.recent(limit=20)
        return {
            "name": "SPARKLE",
            "version": "0.30.0-alpha.1",
            "status": "ready" if any(model["configured"] for model in models) else "limited",
            "active_model": self.models.active_id,
            "active_provider": active["provider"],
            "active_model_id": active["model_id"],
            "models": models,
            "model_runtime": {
                "health_states": ["HEALTHY", "DEGRADED", "UNAVAILABLE"],
                "recent_requests": recent_model_requests,
                "last_routing": recent_model_requests[0] if recent_model_requests else None,
                "live_nemotron_verified": any(
                    item["provider"] == "nvidia"
                    and item["status"] == "success"
                    and not item["test_harness"]
                    for item in recent_model_requests
                ),
            },
            "memory": {"status": "ready", "records": len(self.memory.recent(limit=100))},
            "knowledge": {"status": "ready", **self.knowledge.stats()},
            "trace": {"status": "ready", "recent": len(self.traces.recent(limit=100))},
            "agents": self.agents.list(),
            "generated_agents": {
                "status": "ready",
                "count": sum(1 for agent in self.agents.list() if agent["source"] == "generated"),
                "blueprints": len(self.agent_blueprints.list(limit=100)),
                "evaluations": len(self.agent_evaluations.list(limit=100)),
            },
            "ai_systems": {
                "status": "ready",
                "blueprints": len(self.ai_system_blueprints.list(limit=100)),
                "protocol_version": self.ai_system_builder.PROTOCOL,
                "drafts": len(self.ai_system_drafts.list(limit=100)),
                "draft_protocol_version": self.ai_system_compiler.PROTOCOL,
                "implementation_plans": len(self.ai_system_implementation_plans.list(limit=100)),
                "implementation_plan_protocol_version": self.ai_system_planner.PROTOCOL,
                "provider_disclosures": len(self.source_provider_disclosures.list(limit=100)),
                "source_candidates": len(self.source_candidates.list(limit=100)),
                "source_candidate_protocol_version": self.ai_system_source_candidates.PROTOCOL,
                "runtime_evaluations": len(self.runtime_evaluations.list(limit=100)),
                "runtime_evaluation_protocol_version": self.ai_system_runtime_evaluator.PROTOCOL,
                "source_promotions": len(self.source_promotions.list(limit=100)),
                "source_promotion_approvals": len(self.source_promotions.list_approvals(limit=100)),
                "source_promotion_protocol_version": self.ai_system_source_promoter.PROTOCOL,
                "controlled_builds": len(self.controlled_builds.list(limit=100)),
                "controlled_build_approvals": len(self.controlled_builds.list_approvals(limit=100)),
                "controlled_build_protocol_version": self.ai_system_controlled_builder.PROTOCOL,
                "controlled_executions": len(self.controlled_executions.list(limit=100)),
                "controlled_execution_authorizations": len(self.controlled_executions.list_authorizations(limit=100)),
                "controlled_execution_protocol_version": self.ai_system_controlled_executor.PROTOCOL,
                "running_cancellation": True,
                "execution_is_deployment": False,
            },
            "tools": self.tools.status(),
            "api_security": {
                **self.api_access.status(),
                "rate_limit": self.api_rate_limiter.status(),
                "sessions": self.api_sessions.status(),
                "recent_audit_records": len(self.api_audit.recent(limit=100)),
            },
            "voice": self.voice.status(),
            "interaction": self.interactions.status(),
            "multimodal": content_contract_status(),
            "content_workflows": self.content_workflows.stats(),
            "automation": {
                "status": "ready",
                "count": len(self.automations.list()),
                "recent_runs": len(self.automations.list_runs(limit=100)),
                "service": self.automations.service_status(),
            },
            "notifications": {
                "status": "ready",
                "protocol_version": self.notifications.PROTOCOL,
                "channels": sorted(self.notifications.CHANNELS),
                **self.notifications.stats(),
            },
            "projects": {
                "status": "ready",
                "protocol_version": self.projects.PROTOCOL,
                **self.projects.stats(),
            },
            "learning": {"implemented": True, **self.learning.stats()},
            "data_analysis": self.data_analysis.stats(),
            "skills": {
                "status": "ready",
                "protocol_version": self.skills.PROTOCOL,
                **self.skills.stats(),
            },
            "builders": {
                "status": "ready",
                "workspaces": len(self.workspaces.list(limit=100)),
                "verifications": len(self.development.list(limit=100)),
                "static_verification": True,
                "test_runs": len(self.workspace_tests.list(limit=100)),
                "workspace_tests": self.workspace_tests.status(),
                "external_worker_runs": len(self.external_worker.list(limit=100)),
                "external_worker": self.external_worker.status(),
                "artifacts": len(self.artifacts.list(limit=100)),
                "deployment_records": len(self.artifacts.list_deployments(limit=100)),
                "arbitrary_command_execution": False,
            },
            "proactive_alerts": self.proactive.inspect(),
            "presence": self.presence.status(),
            "data_root": str(data_root()),
        }
