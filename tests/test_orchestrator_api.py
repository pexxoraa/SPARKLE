from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from sparkle.api import SparkleHandler
from sparkle.config import AppConfig
from sparkle.contracts import ModelRequest, ModelResponse, TokenUsage, ToolCall
from sparkle.model import ModelAdapter
from sparkle.providers.mock import DeterministicAdapter
from sparkle.registry import ModelRegistry
from sparkle.system import SparkleSystem


class ToolCallingAdapter(ModelAdapter):
    provider = "scripted"
    model_id = "scripted"

    def __init__(self):
        self.calls = 0

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.calls == 1:
            content = [{"type": "tool_use", "id": "tool-1", "name": "calculator", "input": {"expression": "6*7"}}]
            return ModelResponse("", self.model_id, self.provider, "tool_use", [ToolCall("tool-1", "calculator", {"expression": "6*7"})], raw_assistant_content=content)
        self.last_messages = request.messages
        return ModelResponse("42", self.model_id, self.provider, "end_turn", usage=TokenUsage(5, 1))

    def health(self):
        return {"configured": True}


def test_config() -> AppConfig:
    return AppConfig("127.0.0.1", 0, 4, 5, 5, False, False)


class SystemCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {"SPARKLE_DATA_DIR": self.temp.name}, clear=False)
        self.env_patch.start()
        self.registry = ModelRegistry()
        self.registry.inject(self.registry.active_id, DeterministicAdapter())
        self.system = SparkleSystem(config=test_config(), model_registry=self.registry)

    def tearDown(self):
        self.env_patch.stop()
        self.temp.cleanup()


class OrchestratorTests(SystemCase):
    def test_single_agent_end_to_end_and_trace(self):
        result = self.system.orchestrator.run("Teach me inverse kinematics")
        self.assertEqual(result.agent, "learning")
        self.assertIn("SPARKLE processed", result.text)
        trace = self.system.traces.recent()[0]
        self.assertEqual(trace["status"], "success")
        self.assertEqual(trace["agent"], "learning")

    def test_tool_loop(self):
        adapter = ToolCallingAdapter()
        self.registry.inject(self.registry.active_id, adapter)
        result = self.system.orchestrator.run("Calculate 6 times 7", agent_name="personal")
        self.assertEqual(result.text, "42")
        self.assertEqual(result.tool_calls_executed, ["calculator"])
        self.assertEqual(adapter.last_messages[-1].content, "42")

    def test_multi_agent_synthesis(self):
        result = self.system.orchestrator.run_multi("Research robot arms and build an application dashboard", agent_names=["research", "application_builder"])
        self.assertEqual(result.agent, "personal")
        self.assertGreaterEqual(len(self.system.traces.recent()), 3)


class APITests(SystemCase):
    def setUp(self):
        super().setUp()
        handler = type("TestHandler", (SparkleHandler,), {"system": self.system, "log_message": lambda *args: None})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        super().tearDown()

    def request(self, path: str, value: dict | None = None):
        data = json.dumps(value).encode() if value is not None else None
        request = urllib.request.Request(self.base + path, data=data, headers={"Content-Type": "application/json"} if data else {}, method="POST" if data else "GET")
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers, exc.read()

    def test_health_and_security_headers(self):
        status, headers, body = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertTrue(json.loads(body)["ok"])

    def test_chat_endpoint(self):
        status, _, body = self.request("/api/chat", {"message": "Teach Python"})
        result = json.loads(body)["result"]
        self.assertEqual(status, 200)
        self.assertEqual(result["agent"], "learning")
        self.assertRegex(result["trace_id"], r"SPK-\d{4}-\d{6}")

    def test_memory_and_knowledge_endpoints(self):
        memory_body = json.loads(self.request(
            "/api/memory", {"category": "goals", "key": "robotics", "value": "Learn ROS 2"},
        )[2])
        knowledge_body = json.loads(self.request(
            "/api/knowledge", {"title": "ROS", "content": "ROS 2 uses nodes and topics."},
        )[2])
        memories = json.loads(self.request("/api/memory?q=ROS")[2])["memories"]
        knowledge = json.loads(self.request("/api/knowledge/search?q=nodes")[2])["results"]
        self.assertEqual(memories[0]["key"], "robotics")
        self.assertEqual(knowledge[0]["title"], "ROS")
        memory_id = memory_body["memory_id"]
        source_id = knowledge_body["source_id"]
        self.assertTrue(json.loads(self.request(
            "/api/memory/archive", {"memory_id": memory_id},
        )[2])["archived"])
        self.assertTrue(json.loads(self.request(
            "/api/memory/restore", {"memory_id": memory_id},
        )[2])["restored"])
        self.assertEqual(self.request(
            "/api/memory/delete", {"memory_id": memory_id},
        )[0], 400)
        self.assertTrue(json.loads(self.request(
            "/api/memory/delete", {"memory_id": memory_id, "approved": True},
        )[2])["deleted"])
        sources = json.loads(self.request("/api/knowledge/sources")[2])["sources"]
        self.assertEqual(sources[0]["source_id"], source_id)
        self.assertEqual(self.request(
            "/api/knowledge/delete", {"source_id": source_id},
        )[0], 400)
        self.assertTrue(json.loads(self.request(
            "/api/knowledge/delete", {"source_id": source_id, "approved": True},
        )[2])["deleted"])

    def test_dashboard_serves(self):
        status, _, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"SPARKLE", body)

    def test_generated_agent_build_and_automation_endpoints(self):
        agent = {
            "name": "robotics_research", "capability": "reasoning",
            "purpose": "Research robotics with evidence and engineering constraints.",
            "instructions": "Cross-check evidence and produce testable engineering recommendations.",
            "tools": ["calculator"], "keywords": ["robotics research"],
            "approved": True,
        }
        unapproved_agent = dict(agent)
        unapproved_agent["approved"] = False
        self.assertEqual(self.request("/api/agents", unapproved_agent)[0], 400)
        self.assertEqual(self.request("/api/agents", agent)[0], 201)
        agents = json.loads(self.request("/api/agents")[2])["agents"]
        generated = next(item for item in agents if item["name"] == "robotics_research")
        self.assertEqual(generated["source"], "generated")

        build = {
            "project_name": "robot_console",
            "files": {"README.md": "# Robot console\n", "main.py": "print('ready')\n"},
            "approved": True,
        }
        unapproved_build = dict(build)
        unapproved_build["approved"] = False
        self.assertEqual(self.request("/api/builds", unapproved_build)[0], 400)
        self.assertEqual(self.request("/api/builds", build)[0], 201)
        self.assertEqual(self.request("/api/builds", build)[0], 409)
        self.assertEqual(
            json.loads(self.request("/api/builds")[2])["builds"][0]["project_name"],
            "robot_console",
        )

        now = datetime.now(UTC)
        automation = {
            "name": "API focus review", "kind": "once",
            "action": {"type": "agent", "prompt": "Review my focus", "agent": "personal"},
            "next_run_at": (now - timedelta(minutes=1)).isoformat(),
        }
        self.assertEqual(self.request("/api/automations", automation)[0], 201)
        run = json.loads(self.request("/api/automations/run", {})[2])["runs"][0]
        self.assertEqual(run["status"], "success")
        self.assertEqual(
            json.loads(self.request("/api/automation-runs")[2])["runs"][0]["status"],
            "success",
        )
