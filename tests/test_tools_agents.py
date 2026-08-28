from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sparkle.agents import AgentRegistry, AgentRouter
from sparkle.tooling import CalculatorTool, FileReadTool, ToolError, ToolRegistry


class ToolTests(unittest.TestCase):
    def test_calculator(self):
        self.assertEqual(CalculatorTool().run({"expression": "2 + 3 * 4"}), 14)

    def test_calculator_rejects_code(self):
        with self.assertRaises(ToolError):
            CalculatorTool().run({"expression": "__import__('os').system('id')"})

    def test_file_read_is_confined(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "safe.txt").write_text("safe")
            tool = FileReadTool(root)
            self.assertEqual(tool.run({"path": "safe.txt"})["content"], "safe")
            with self.assertRaises(ToolError):
                tool.run({"path": "../outside.txt"})

    def test_registry_enforces_agent_allowlist(self):
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        with self.assertRaises(ToolError):
            registry.execute("calculator", {"expression": "1+1"}, allowed=set())


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.registry = AgentRegistry()
        self.router = AgentRouter(self.registry)

    def test_all_initial_agents_exist(self):
        required = {"personal", "learning", "skill", "exam", "research", "coding", "software_engineering", "application_builder", "ai_builder", "agent_builder", "project", "data_analysis", "content", "productivity", "automation", "system"}
        self.assertEqual(required, self.registry.names)

    def test_routes_code_request(self):
        self.assertEqual(self.router.select("Debug this Python function").name, "coding")

    def test_routes_exam_request(self):
        self.assertEqual(self.router.select("Build a mock exam revision plan").name, "exam")
