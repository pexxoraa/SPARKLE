from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from sparkle.agents import AgentRegistry, AgentRouter
from sparkle.config import AppConfig
from sparkle.providers.mock import DeterministicAdapter
from sparkle.registry import ModelRegistry
from sparkle.system import SparkleSystem


AGENT_EVALUATIONS = {
    "personal": {
        "prompt": "What personal goal and priority should I focus on today?",
        "capability": "reasoning",
        "instruction": "realistic priorities",
        "tools": {"memory_search", "memory_write"},
    },
    "learning": {
        "prompt": "Teach and explain this concept with a practice quiz",
        "capability": "reasoning",
        "instruction": "explain → ask → test → correct → apply → retest",
        "tools": {"knowledge_search", "memory_write"},
    },
    "skill": {
        "prompt": "Assess my skill mastery level and make a practice plan",
        "capability": "reasoning",
        "instruction": "demonstrations, projects, or tests",
        "tools": {"memory_search", "memory_write"},
    },
    "exam": {
        "prompt": "Review my exam syllabus, mock accuracy, and revision marks",
        "capability": "reasoning",
        "instruction": "accuracy, speed, attempts",
        "tools": {"knowledge_search", "memory_write"},
    },
    "research": {
        "prompt": "Research the latest paper sources and compare the evidence",
        "capability": "reasoning",
        "instruction": "Never invent sources",
        "tools": {"knowledge_search"},
    },
    "coding": {
        "prompt": "Debug this Python function and review the code",
        "capability": "coding",
        "instruction": "runnable changes",
        "tools": {"file_read", "workspace_verify"},
    },
    "software_engineering": {
        "prompt": "Refactor the software repository architecture for a release",
        "capability": "coding",
        "instruction": "architecture, security, tests",
        "tools": {"file_read", "workspace_verify"},
    },
    "application_builder": {
        "prompt": "Build a mobile app with frontend, backend, API, and dashboard",
        "capability": "coding",
        "instruction": "requirements, UX, implementation",
        "tools": {"workspace_scaffold", "workspace_verify", "workspace_package"},
    },
    "ai_builder": {
        "prompt": "Design a multimodal AI system with RAG, embeddings, and evaluation",
        "capability": "reasoning",
        "instruction": "model, data, evaluation",
        "tools": {"workspace_scaffold", "workspace_verify", "workspace_package"},
    },
    "agent_builder": {
        "prompt": "Build a multi-agent orchestrator with agent tool calling",
        "capability": "reasoning",
        "instruction": "purpose, tools, memory",
        "tools": {"agent_install", "workspace_scaffold", "workspace_verify"},
    },
    "project": {
        "prompt": "Review the project milestone, deadline, blocker, and roadmap task",
        "capability": "reasoning",
        "instruction": "status, priority, deadline",
        "tools": {"memory_search", "memory_write"},
    },
    "data_analysis": {
        "prompt": "Analyze this CSV spreadsheet with statistics, a chart, and forecast",
        "capability": "reasoning",
        "instruction": "suitable statistics",
        "tools": {"calculator", "file_read"},
    },
    "content": {
        "prompt": "Create a YouTube video script, hook, thumbnail, and publish plan",
        "capability": "reasoning",
        "instruction": "evidence standards",
        "tools": {"knowledge_search", "memory_write"},
    },
    "productivity": {
        "prompt": "Plan my day with a productivity schedule, time, and habit",
        "capability": "reasoning",
        "instruction": "Protect deep work",
        "tools": {"memory_search", "memory_write"},
    },
    "automation": {
        "prompt": "Automate a recurring schedule to monitor and remind me",
        "capability": "tool_use",
        "instruction": "trigger, action, failure policy",
        "tools": {"memory_search", "memory_write"},
    },
    "system": {
        "prompt": "Diagnose system status, config, environment, trace, health, and failure",
        "capability": "reasoning",
        "instruction": "configured, reachable, tested, and verified",
        "tools": {"file_read", "memory_search"},
    },
}


def test_config() -> AppConfig:
    return AppConfig("127.0.0.1", 0, 4, 5, 5, False, False)


class BuiltInAgentEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.registry = AgentRegistry()
        self.router = AgentRouter(self.registry)

    def test_all_builtin_agents_meet_their_domain_contract_and_route(self):
        self.assertEqual(self.registry.names, set(AGENT_EVALUATIONS))
        for name, evaluation in AGENT_EVALUATIONS.items():
            with self.subTest(agent=name):
                spec = self.registry.get(name)
                self.assertEqual(spec.capability, evaluation["capability"])
                self.assertIn(evaluation["instruction"], spec.instructions)
                self.assertTrue(evaluation["tools"].issubset(spec.tools))
                self.assertEqual(self.router.select(evaluation["prompt"]).name, name)

    def test_every_system_prompt_includes_common_evidence_guardrails(self):
        required = (
            "Distinguish facts, inferences, opinions, and uncertainty",
            "Never claim an action or test occurred unless tool evidence confirms it",
            "Store durable memory only when the user explicitly asks",
        )
        for name in sorted(self.registry.names):
            with self.subTest(agent=name):
                prompt = self.registry.get(name).system_prompt()
                self.assertTrue(all(value in prompt for value in required))
                self.assertIn(self.registry.get(name).instructions, prompt)

    def test_every_agent_executes_through_orchestrator_and_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False,
            ):
                models = ModelRegistry()
                models.inject(models.active_id, DeterministicAdapter())
                system = SparkleSystem(
                    config=test_config(), model_registry=models,
                )
                for name, evaluation in AGENT_EVALUATIONS.items():
                    with self.subTest(agent=name):
                        result = system.orchestrator.run(
                            evaluation["prompt"], agent_name=name,
                        )
                        self.assertEqual(result.agent, name)
                        self.assertEqual(result.provider, "deterministic")
                        self.assertEqual(result.input_modalities, ["text"])
                        trace = system.traces.recent(limit=1)[0]
                        self.assertEqual(trace["trace_id"], result.trace_id)
                        self.assertEqual(trace["agent"], name)
                        self.assertEqual(trace["status"], "success")


if __name__ == "__main__":
    unittest.main()
