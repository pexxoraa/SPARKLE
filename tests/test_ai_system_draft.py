from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sparkle.ai_system_draft import AISystemDraftStore
from sparkle.cli import entrypoint, main
from sparkle.config import AppConfig
from sparkle.contracts import ModelRequest, ModelResponse, ToolCall
from sparkle.model import ModelAdapter
from sparkle.registry import ModelRegistry
from sparkle.system import SparkleSystem


def test_config() -> AppConfig:
    return AppConfig("127.0.0.1", 0, 4, 5, 5, False, False)


def valid_requirements() -> dict[str, object]:
    return {
        "name": "robotics_ai",
        "purpose": "Research robotics evidence and produce bounded analytical outputs.",
        "model_requirements": [{
            "capability": "reasoning", "modalities": ["text"],
        }],
        "agents": ["research", "data_analysis"],
        "tools": ["calculator", "knowledge_search"],
        "data_environments": [
            "knowledge_environment", "data_environment", "trace_environment",
        ],
        "interfaces": ["text", "api", "dashboard"],
        "workflow": [
            "Collect bounded evidence from approved sources.",
            "Analyze evidence with selected specialist agents.",
            "Return a traceable result and preserve evaluation evidence.",
        ],
        "evaluations": [{
            "name": "robotics_integration",
            "kind": "integration",
            "criterion": "The system preserves source and trace boundaries.",
        }],
        "deployment": {"environment_name": "staging", "target_kind": "server"},
    }


class DraftAdapter(ModelAdapter):
    provider = "draft-test-provider"
    model_id = "draft-test-model"

    def __init__(self, response: str):
        self.response = response
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(
            self.response, self.model_id, self.provider, "end_turn",
        )

    def health(self) -> dict[str, object]:
        return {"configured": True, "provider": self.provider, "model": self.model_id}


class ToolDraftAdapter(DraftAdapter):
    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(
            "", self.model_id, self.provider, "tool_use",
            [ToolCall("draft-tool", "calculator", {"expression": "1+1"})],
        )


class AISystemDraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {"SPARKLE_DATA_DIR": self.temp.name}, clear=False,
        )
        self.environment.start()
        self.adapter = DraftAdapter(json.dumps(valid_requirements()))
        registry = ModelRegistry()
        registry.inject(registry.active_id, self.adapter)
        self.system = SparkleSystem(
            config=test_config(), model_registry=registry,
        )

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def test_approved_draft_is_isolated_validated_traced_and_content_free(self):
        private_context = "PRIVATE_DRAFT_CONTEXT"
        natural_language = (
            "Build a robotics research AI with research and data analysis agents, "
            "bounded evidence, an API, and a dashboard."
        )
        self.system.memory.remember("preferences", "draft", private_context)
        with self.assertRaisesRegex(ValueError, "explicit approval"):
            self.system.ai_system_compiler.compile(
                natural_language, approved=False,
            )
        self.assertEqual(self.adapter.requests, [])
        self.assertEqual(self.system.ai_system_drafts.list(), [])

        result = self.system.ai_system_compiler.compile(
            natural_language, approved=True,
        )
        self.assertEqual(result["protocol_version"], "SPARKLE-AI-SYSTEM-DRAFT/1")
        self.assertEqual(result["status"], "draft_static_verified")
        self.assertEqual(result["requirements"]["name"], "robotics_ai")
        self.assertEqual(
            result["blueprint"]["protocol_version"],
            "SPARKLE-AI-SYSTEM-BLUEPRINT/1",
        )
        self.assertTrue(result["model_call_executed"])
        self.assertTrue(result["schema_validation_executed"])
        self.assertFalse(result["semantic_correctness_verified"])
        self.assertFalse(result["runtime_evaluation_executed"])
        self.assertFalse(result["external_deployment_executed"])

        request = self.adapter.requests[0]
        self.assertEqual(request.tools, [])
        self.assertNotIn(private_context, request.system or "")
        self.assertNotIn(private_context, request.messages[-1].text_content)
        self.assertIn(natural_language, request.messages[-1].text_content)
        self.assertIn("agent_tools", request.messages[-1].text_content)

        records = self.system.ai_system_drafts.list()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "draft_static_verified")
        self.assertEqual(len(records[0]["response_sha256"]), 64)
        serialized = json.dumps(records)
        self.assertNotIn(natural_language, serialized)
        self.assertNotIn("Research robotics evidence", serialized)
        self.assertNotIn(private_context, serialized)
        self.assertEqual(self.system.status()["ai_systems"]["drafts"], 1)

        trace = self.system.traces.recent()[0]
        self.assertEqual(trace["input_source"], "ai_system_draft")
        self.assertEqual(trace["data_accessed"], [])
        self.assertEqual(trace["tools"], [])
        self.assertEqual(
            trace["execution_metadata"]["execution_profile"], "evaluation",
        )
        self.assertEqual(trace["result_summary"], "Agent evaluation model call completed")

    def test_invalid_model_outputs_fail_closed_with_safe_evidence(self):
        outputs = [
            "```json\n{}\n```",
            '{"name":"first","name":"second"}',
            json.dumps({**valid_requirements(), "provider": "minimax"}),
        ]
        for response in outputs:
            with self.subTest(response=response[:40]):
                self.adapter.response = response
                with self.assertRaises(ValueError):
                    self.system.ai_system_compiler.compile(
                        "Build a bounded robotics research AI system.",
                        approved=True,
                    )
        records = self.system.ai_system_drafts.list()
        self.assertEqual(len(records), 3)
        self.assertTrue(all(item["status"] == "draft_failed" for item in records))
        self.assertTrue(all(item["error_type"] == "ValueError" for item in records))
        serialized = json.dumps(records)
        self.assertNotIn("first", serialized)
        self.assertNotIn("minimax", serialized)
        self.assertNotIn("```json", serialized)

    def test_input_bounds_precede_model_calls_and_persistence(self):
        for text in ("too short", "x" * 20_001):
            with self.subTest(length=len(text)):
                with self.assertRaisesRegex(ValueError, "20-20000"):
                    self.system.ai_system_compiler.compile(text, approved=True)
        self.assertEqual(self.adapter.requests, [])
        self.assertEqual(self.system.ai_system_drafts.list(), [])

    def test_tool_request_fails_without_tool_execution(self):
        adapter = ToolDraftAdapter(json.dumps(valid_requirements()))
        self.system.models.inject(self.system.models.active_id, adapter)
        with patch.object(
            self.system.tools,
            "execute",
            Mock(side_effect=AssertionError("draft tool must not execute")),
        ):
            with self.assertRaisesRegex(RuntimeError, "requested a tool"):
                self.system.ai_system_compiler.compile(
                    "Build a bounded robotics research AI system.",
                    approved=True,
                )
        self.assertEqual(adapter.requests[0].tools, [])
        self.assertEqual(self.system.ai_system_drafts.list()[0]["status"], "draft_failed")
        self.assertEqual(self.system.traces.recent()[0]["tools"], [])

    def test_cli_reads_requirements_from_file_and_requires_approval(self):
        source = Path(self.temp.name) / "requirements.txt"
        source.write_text(
            "Build a bounded robotics research AI system with an API.",
            encoding="utf-8",
        )
        output = io.StringIO()
        error = io.StringIO()
        with (
            patch("sparkle.cli.SparkleSystem", return_value=self.system),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(error),
        ):
            self.assertEqual(entrypoint([
                "ai-system-draft", str(source),
            ]), 1)
            self.assertEqual(main([
                "ai-system-draft", str(source), "--approve",
            ]), 0)
        self.assertIn("explicit approval", error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())
        self.assertIn("SPARKLE-AI-SYSTEM-DRAFT/1", output.getvalue())


class AISystemDraftStoreTests(unittest.TestCase):
    def test_retention_is_bounded_to_latest_one_thousand_records(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AISystemDraftStore(Path(directory) / "drafts.sqlite3")
            value = {
                "status": "draft_failed",
                "request_bytes": 20,
                "response_sha256": None,
                "response_chars": 0,
                "provider": None,
                "model": None,
                "trace_id": None,
                "error_type": "ModelError",
            }
            for _ in range(1_002):
                latest = store.save(value)
            with store.connect() as connection:
                count = connection.execute(
                    "SELECT COUNT(*) FROM ai_system_drafts"
                ).fetchone()[0]
            self.assertEqual(count, 1_000)
            self.assertEqual(store.list(limit=1)[0]["draft_id"], latest)


if __name__ == "__main__":
    unittest.main()
