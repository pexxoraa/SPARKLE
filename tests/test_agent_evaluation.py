from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sparkle.agent_evaluation import AgentEvaluationStore
from sparkle.config import AppConfig
from sparkle.contracts import ModelResponse, ToolCall
from sparkle.providers.mock import DeterministicAdapter
from sparkle.registry import ModelRegistry
from sparkle.system import SparkleSystem


def test_config() -> AppConfig:
    return AppConfig("127.0.0.1", 0, 4, 5, 5, False, False)


def requirements(*, passing: bool = True, assertions: bool = True) -> dict[str, object]:
    case: dict[str, object] = {
        "name": "robot_arm_evidence",
        "prompt": "Perform robotics research for a robot arm.",
    }
    if assertions:
        case["assertions"] = {
            "contains_all": [
                "SPARKLE processed",
                "robot arm" if passing else "phrase that is absent",
            ],
            "excludes_all": ["fabricated completion"],
            "min_chars": 20,
            "max_chars": 500,
        }
    return {
        "name": "robotics_research",
        "capability": "reasoning",
        "purpose": "Research robotics systems with evidence and engineering constraints.",
        "tools": ["calculator", "memory_search"],
        "keywords": ["robotics research", "robot arm"],
        "workflow": ["Collect evidence.", "Cross-check sources."],
        "guardrails": ["Never fabricate sources or completed tests."],
        "evaluations": [case],
    }


class CaptureAdapter(DeterministicAdapter):
    def __init__(self):
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return super().complete(request)


class ToolRequestingAdapter(DeterministicAdapter):
    def complete(self, request):
        return ModelResponse(
            text="",
            model=self.model_id,
            provider=self.provider,
            finish_reason="tool_use",
            tool_calls=[ToolCall("eval-tool", "calculator", {"expression": "1+1"})],
        )


class AgentResponseEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ, {"SPARKLE_DATA_DIR": self.temp.name}, clear=False,
        )
        self.env.start()
        self.adapter = CaptureAdapter()
        registry = ModelRegistry()
        registry.inject(registry.active_id, self.adapter)
        self.system = SparkleSystem(
            config=test_config(), model_registry=registry,
        )

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_approved_evaluation_is_isolated_persisted_and_content_free(self):
        self.system.memory.remember(
            "preferences", "evaluation_context", "PRIVATE_EVAL_CONTEXT",
        )
        built = self.system.agent_builder.build(requirements(), approved=True)
        with self.assertRaisesRegex(ValueError, "explicit approval"):
            self.system.agent_evaluator.evaluate(
                "robotics_research", approved=False,
            )
        self.assertEqual(self.adapter.requests, [])
        self.assertEqual(self.system.agent_evaluations.list(), [])

        result = self.system.agent_evaluator.evaluate(
            "robotics_research", approved=True,
        )
        self.assertEqual(result["protocol_version"], "SPARKLE-AGENT-EVALUATION/1")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["passed_count"], 1)
        self.assertEqual(result["blueprint_id"], built["blueprint_id"])
        self.assertTrue(result["response_contract_evaluation_executed"])
        self.assertFalse(result["semantic_evaluation_executed"])
        self.assertFalse(result["live_provider_verified"])
        self.assertEqual(self.adapter.requests[0].tools, [])
        self.assertNotIn(
            "PRIVATE_EVAL_CONTEXT", self.adapter.requests[0].system or "",
        )

        serialized = json.dumps(self.system.agent_evaluations.list())
        self.assertNotIn("Perform robotics research", serialized)
        self.assertNotIn("SPARKLE processed", serialized)
        self.assertNotIn("PRIVATE_EVAL_CONTEXT", serialized)
        record = self.system.agent_evaluations.list()[0]
        self.assertEqual(record["status"], "passed")
        self.assertEqual(len(record["cases"][0]["response_sha256"]), 64)
        trace = self.system.traces.recent()[0]
        self.assertEqual(trace["input_source"], "agent_evaluation")
        self.assertEqual(trace["data_accessed"], [])
        self.assertEqual(trace["tools"], [])
        self.assertEqual(
            trace["execution_metadata"]["execution_profile"], "evaluation",
        )
        self.assertEqual(
            trace["result_summary"], "Agent evaluation model call completed",
        )

    def test_failed_assertions_are_evidence_not_semantic_success(self):
        self.system.agent_builder.build(
            requirements(passing=False), approved=True,
        )
        result = self.system.agent_evaluator.evaluate(
            "robotics_research", approved=True,
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["passed_count"], 0)
        self.assertEqual(result["failed_count"], 1)
        self.assertFalse(result["cases"][0]["checks"][0]["passed"])
        self.assertIsNone(result["cases"][0]["error_type"])

    def test_missing_assertions_and_manifest_drift_fail_before_model_call(self):
        self.system.agent_builder.build(
            requirements(assertions=False), approved=True,
        )
        with self.assertRaisesRegex(ValueError, "requires response assertions"):
            self.system.agent_evaluator.evaluate(
                "robotics_research", approved=True,
            )
        self.assertEqual(self.adapter.requests, [])
        self.assertEqual(self.system.agent_evaluations.list(), [])

        self.system.agents.remove("robotics_research")
        altered = self.system.agent_builder.prepare(requirements()).manifest
        altered = type(altered)(
            altered.name, altered.capability,
            "A deliberately changed purpose that no longer matches its blueprint.",
            altered.instructions, altered.tools, altered.keywords,
        )
        self.system.agents.install(altered)
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            self.system.agent_evaluator.evaluate(
                "robotics_research", approved=True,
            )
        self.assertEqual(self.adapter.requests, [])

    def test_tool_request_fails_closed_without_executing_a_tool(self):
        self.system.agent_builder.build(requirements(), approved=True)
        adapter = ToolRequestingAdapter()
        self.system.models.inject(self.system.models.active_id, adapter)
        with patch.object(
            self.system.tools,
            "execute",
            Mock(side_effect=AssertionError("tool must not execute")),
        ):
            result = self.system.agent_evaluator.evaluate(
                "robotics_research", approved=True,
            )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["cases"][0]["error_type"], "RuntimeError")
        trace = self.system.traces.recent()[0]
        self.assertEqual(trace["status"], "failure")
        self.assertEqual(trace["tools"], [])
        self.assertEqual(
            trace["result_summary"], "Agent evaluation model call failed",
        )

    def test_assertion_schema_is_strict_and_bounded(self):
        cases = []
        unknown = requirements()
        unknown["evaluations"][0]["assertions"]["regex"] = ".*"
        cases.append(("Unsupported", unknown))
        empty = requirements()
        empty["evaluations"][0]["assertions"] = {}
        cases.append(("cannot be empty", empty))
        reversed_bounds = requirements()
        reversed_bounds["evaluations"][0]["assertions"] = {
            "min_chars": 100, "max_chars": 10,
        }
        cases.append(("reversed", reversed_bounds))
        boolean_bound = requirements()
        boolean_bound["evaluations"][0]["assertions"] = {"min_chars": True}
        cases.append(("integer", boolean_bound))
        duplicates = requirements()
        duplicates["evaluations"][0]["assertions"] = {
            "contains_all": ["evidence", "EVIDENCE"],
        }
        cases.append(("duplicates", duplicates))
        for message, value in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    self.system.agent_builder.prepare(value)
        self.assertEqual(self.adapter.requests, [])

    def test_isolated_profile_rejects_context_injection_before_model_call(self):
        self.system.agent_builder.build(requirements(), approved=True)
        for field, value in (
            ("additional_context", "private peer response"),
            ("history", []),
            ("user_id", "private-user"),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "rejects history"):
                    self.system.orchestrator.run(
                        "Perform robotics research for a robot arm.",
                        agent_name="robotics_research",
                        execution_profile="evaluation",
                        **{field: value},
                    )
        self.assertEqual(self.adapter.requests, [])


class AgentEvaluationStoreTests(unittest.TestCase):
    def test_retention_is_bounded_to_latest_1000_records(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AgentEvaluationStore(Path(directory) / "evaluations.sqlite3")
            base = {
                "blueprint_id": 1,
                "agent_name": "robotics_research",
                "status": "passed",
                "case_count": 0,
                "passed_count": 0,
                "failed_count": 0,
                "cases": [],
                "providers": [],
                "models": [],
                "trace_ids": [],
            }
            for _ in range(1_002):
                latest = store.save(base)
            with store.connect() as connection:
                count = connection.execute(
                    "SELECT COUNT(*) FROM agent_evaluations"
                ).fetchone()[0]
            self.assertEqual(count, 1_000)
            self.assertEqual(store.list(limit=1)[0]["evaluation_id"], latest)
