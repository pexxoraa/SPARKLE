from __future__ import annotations

from unittest.mock import patch

from sparkle.contracts import ModelResponse, ToolCall
from sparkle.orchestrator import _WorkflowBudget
from sparkle.providers.mock import DeterministicAdapter
from tests.test_orchestrator_api import SystemCase


class FreshIdLoopAdapter(DeterministicAdapter):
    def __init__(self):
        self.calls = 0
        self.requests = []

    def complete(self, request):
        self.calls += 1
        self.requests.append(request)
        if not request.tools:
            return ModelResponse(
                "Recovered from repeated tool observations.",
                self.model_id,
                self.provider,
                "stop",
            )
        return ModelResponse(
            "",
            self.model_id,
            self.provider,
            "tool_use",
            tool_calls=[
                ToolCall(
                    f"fresh-{self.calls}",
                    "calculator",
                    {"expression": "1+1"},
                )
            ],
        )


class AgentToolRecoveryTests(SystemCase):
    def test_same_signature_with_fresh_ids_executes_once_and_recovers(self):
        adapter = FreshIdLoopAdapter()
        self.registry.inject(self.registry.active_id, adapter)
        with patch.object(
            self.system.tools,
            "execute",
            wraps=self.system.tools.execute,
        ) as execute:
            result = self.system.orchestrator.run(
                "Calculate one plus one.",
                agent_name="personal",
            )

        self.assertEqual(result.text, "Recovered from repeated tool observations.")
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(
            result.tool_calls_executed,
            ["calculator", "calculator", "calculator"],
        )
        self.assertEqual(adapter.calls, 4)
        self.assertEqual(adapter.requests[-1].tools, [])
        trace = self.system.traces.recent()[0]
        self.assertEqual(trace["status"], "success")
        self.assertEqual(trace["execution_metadata"]["tool_signature_replays"], 2)
        self.assertEqual(trace["execution_metadata"]["tool_loop_recovery_completions"], 1)

    def test_replay_cache_is_scoped_to_agent_authority(self):
        budget = _WorkflowBudget(tool_limit=8, max_seconds=30)
        arguments = {"expression": "1+1"}
        replayed, signature, cached = budget.replay(
            "personal", "call-1", "calculator", arguments
        )
        self.assertFalse(replayed)
        self.assertIsNone(cached)
        budget.remember("personal", "call-1", signature, 2)

        replayed, _, cached = budget.replay(
            "personal", "call-2", "calculator", arguments
        )
        self.assertTrue(replayed)
        self.assertEqual(cached, 2)

        replayed, _, cached = budget.replay(
            "learning", "call-1", "calculator", arguments
        )
        self.assertFalse(replayed)
        self.assertIsNone(cached)

    def test_tool_policy_is_minimal_evidence_oriented(self):
        policy = self.system.orchestrator._tool_policy(
            {
                "calculator",
                "memory_write",
                "knowledge_search",
                "knowledge_verify",
                "research_workspace",
                "learning_progress",
                "file_read",
                "workspace_verify",
            }
        )
        self.assertIn("narrowest sufficient tool", policy)
        self.assertIn("Do not repeat an identical tool call", policy)
        self.assertIn("deterministic arithmetic", policy)
        self.assertIn("memory_write once", policy)
        self.assertIn("knowledge_search before heavier research/state tools", policy)
        self.assertIn("Do not invent citations", policy)
        self.assertIn("knowledge_verify only", policy)
        self.assertIn("research_workspace for genuinely persistent multi-step", policy)
        self.assertIn("learning_progress when the request concerns a named course", policy)
        self.assertIn("prefer workspace_verify", policy)

    def test_policy_is_injected_into_standard_model_request(self):
        adapter = FreshIdLoopAdapter()
        self.registry.inject(self.registry.active_id, adapter)
        self.system.orchestrator.run("Calculate one plus one.", agent_name="personal")
        first = adapter.requests[0]
        self.assertIn("TOOL USE POLICY", first.system)
        self.assertIn("deterministic arithmetic", first.system)
        self.assertIn("memory_write once", first.system)
        self.assertIn("Do not repeat an identical tool call", first.system)

    def test_builtin_prompts_prefer_direct_evidence_tools(self):
        personal = self.system.agents.get("personal").system_prompt()
        learning = self.system.agents.get("learning").system_prompt()
        research = self.system.agents.get("research").system_prompt()
        coding = self.system.agents.get("coding").system_prompt()
        self.assertIn("For requested exact arithmetic use calculator", personal)
        self.assertIn("explicit durable-memory request use memory_write once", personal)
        self.assertIn("invoke that tool once and report its observed failure", personal)
        self.assertIn("explicit learning-memory record use memory_write once", learning)
        self.assertIn("direct source lookup use knowledge_search", learning)
        self.assertIn("learning_progress only for named curriculum", learning)
        self.assertIn("call knowledge_search once even when generic retrieved context", research)
        self.assertIn("Never invent a citation", research)
        self.assertIn("use workspace_verify directly", coding)
