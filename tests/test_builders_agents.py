from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sparkle.agents import AgentRegistry, AgentRouter, AgentSpec, GeneratedAgentStore
from sparkle.builders import WorkspaceManager
from sparkle.tooling import AgentInstallTool, ToolError, WorkspaceScaffoldTool


def robotics_agent() -> AgentSpec:
    return AgentSpec(
        name="robotics_research",
        capability="reasoning",
        purpose="Research robotics systems with evidence and engineering constraints.",
        instructions="Cross-check sources, state uncertainty, and produce testable engineering recommendations.",
        tools=frozenset({"calculator"}),
        keywords=("robotics research", "robot arm", "ros 2"),
    )


class GeneratedAgentTests(unittest.TestCase):
    def test_install_persist_reload_route_and_remove(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GeneratedAgentStore(Path(directory) / "agents.sqlite3")
            registry = AgentRegistry(store, allowed_tools={"calculator"})
            registry.install(robotics_agent())
            self.assertEqual(
                AgentRouter(registry).select("Run robotics research for a robot arm").name,
                "robotics_research",
            )

            reloaded = AgentRegistry(store, allowed_tools={"calculator"})
            self.assertEqual(reloaded.get("robotics_research").purpose, robotics_agent().purpose)
            self.assertEqual(
                next(item for item in reloaded.list() if item["name"] == "robotics_research")["source"],
                "generated",
            )
            self.assertTrue(reloaded.remove("robotics_research"))
            self.assertNotIn("robotics_research", AgentRegistry(store).names)

    def test_rejects_builtin_override_and_unknown_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = AgentRegistry(
                GeneratedAgentStore(Path(directory) / "agents.sqlite3"),
                allowed_tools={"calculator"},
            )
            invalid_tool = robotics_agent()
            invalid_tool = AgentSpec(
                invalid_tool.name, invalid_tool.capability, invalid_tool.purpose,
                invalid_tool.instructions, frozenset({"shell"}), invalid_tool.keywords,
            )
            with self.assertRaisesRegex(ValueError, "unknown tools"):
                registry.install(invalid_tool)
            builtin = robotics_agent()
            builtin = AgentSpec(
                "personal", builtin.capability, builtin.purpose, builtin.instructions,
                builtin.tools, builtin.keywords,
            )
            with self.assertRaisesRegex(ValueError, "built-in"):
                registry.install(builtin)

    def test_install_tool_requires_explicit_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = AgentRegistry(
                GeneratedAgentStore(Path(directory) / "agents.sqlite3"),
                allowed_tools={"calculator"},
            )
            tool = AgentInstallTool(registry)
            manifest = {
                "name": "robotics_research", "capability": "reasoning",
                "purpose": robotics_agent().purpose,
                "instructions": robotics_agent().instructions,
                "tools": ["calculator"], "keywords": ["robotics research"],
            }
            with self.assertRaises(ToolError):
                tool.run(manifest)
            manifest["approved"] = True
            self.assertTrue(tool.run(manifest)["installed"])


class WorkspaceBuilderTests(unittest.TestCase):
    def test_scaffolds_and_records_bounded_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = WorkspaceManager(root / "apps", root / "builds.sqlite3")
            result = manager.scaffold(
                "robot_dashboard",
                {"README.md": "# Robot dashboard\n", "src/main.py": "print('ready')\n"},
            )
            self.assertEqual(result["status"], "scaffolded")
            self.assertEqual((root / "apps/robot_dashboard/src/main.py").read_text(), "print('ready')\n")
            self.assertEqual(manager.list()[0]["project_name"], "robot_dashboard")
            with self.assertRaises(FileExistsError):
                manager.scaffold("robot_dashboard", {"README.md": "replace"})

    def test_rejects_path_escape_and_requires_tool_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = WorkspaceManager(root / "apps", root / "builds.sqlite3")
            with self.assertRaises(ValueError):
                manager.scaffold("unsafe_project", {"../escape.txt": "blocked"})
            tool = WorkspaceScaffoldTool(manager)
            with self.assertRaises(ToolError):
                tool.run({"project_name": "safe_project", "files": {"README.md": "safe"}})
            result = tool.run({
                "project_name": "safe_project", "files": {"README.md": "safe"},
                "approved": True,
            })
            self.assertEqual(result["project_name"], "safe_project")
