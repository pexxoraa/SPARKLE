from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from sparkle.agent_builder import AgentBlueprintBuilder, AgentBlueprintStore
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


def robotics_requirements() -> dict[str, object]:
    return {
        "name": "robotics_research",
        "capability": "reasoning",
        "purpose": "Research robotics systems with evidence and engineering constraints.",
        "tools": ["calculator"],
        "keywords": ["robotics research", "robot arm", "ros 2"],
        "workflow": [
            "Collect relevant robotics evidence.",
            "Cross-check the evidence and state uncertainty.",
            "Produce testable engineering recommendations.",
        ],
        "guardrails": [
            "Never fabricate sources or completed tests.",
            "Keep recommendations within the available evidence.",
        ],
        "evaluations": [
            {
                "name": "robot_arm_evidence",
                "prompt": "Perform robotics research for a robot arm.",
            },
            {
                "name": "ros_plan",
                "prompt": "Create an evidence-based ROS 2 research plan.",
            },
        ],
    }


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


class AgentBlueprintBuilderTests(unittest.TestCase):
    def _builder(self, root: Path) -> tuple[AgentBlueprintBuilder, AgentRegistry]:
        registry = AgentRegistry(
            GeneratedAgentStore(root / "agents.sqlite3"),
            allowed_tools={"calculator"},
        )
        return (
            AgentBlueprintBuilder(
                registry, AgentBlueprintStore(root / "blueprints.sqlite3"),
            ),
            registry,
        )

    def test_prepare_is_deterministic_static_and_non_mutating(self):
        with tempfile.TemporaryDirectory() as directory:
            builder, registry = self._builder(Path(directory))
            before = registry.names
            first = builder.prepare(robotics_requirements()).to_dict()
            second = builder.prepare(robotics_requirements()).to_dict()
            self.assertEqual(first, second)
            self.assertEqual(registry.names, before)
            self.assertEqual(first["protocol_version"], "SPARKLE-AGENT-BLUEPRINT/1")
            self.assertEqual(first["status"], "prepared_static_verified")
            self.assertEqual(first["manifest"]["name"], "robotics_research")
            self.assertEqual(first["evaluations"][0]["expected_route"], "robotics_research")
            self.assertFalse(first["semantic_evaluation_executed"])
            self.assertFalse(first["external_deployment_executed"])

    def test_build_requires_approval_installs_persists_reloads_and_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            builder, registry = self._builder(root)
            with self.assertRaisesRegex(ValueError, "explicit approval"):
                builder.build(robotics_requirements(), approved=False)
            self.assertNotIn("robotics_research", registry.names)
            self.assertEqual(builder.store.list(), [])

            result = builder.build(robotics_requirements(), approved=True)
            self.assertEqual(result["status"], "installed_static_verified")
            self.assertGreater(result["blueprint_id"], 0)
            self.assertEqual(
                AgentRouter(registry).select(
                    "Perform robotics research for a robot arm",
                ).name,
                "robotics_research",
            )
            reloaded = AgentRegistry(
                GeneratedAgentStore(root / "agents.sqlite3"),
                allowed_tools={"calculator"},
            )
            self.assertIn("robotics_research", reloaded.names)
            record = AgentBlueprintStore(root / "blueprints.sqlite3").list()[0]
            self.assertEqual(record["agent_name"], "robotics_research")
            self.assertEqual(record["blueprint"]["manifest"]["name"], "robotics_research")

            self.assertTrue(registry.remove("robotics_research"))
            rebuilt = builder.build(robotics_requirements(), approved=True)
            self.assertGreater(rebuilt["blueprint_id"], result["blueprint_id"])
            self.assertEqual(
                [item["agent_name"] for item in builder.store.list()],
                ["robotics_research", "robotics_research"],
            )

    def test_invalid_requirements_fail_before_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            builder, registry = self._builder(Path(directory))
            cases: list[tuple[str, dict[str, object]]] = []
            unknown = robotics_requirements()
            unknown["provider"] = "provider-specific"
            cases.append(("Unsupported", unknown))
            unknown_tool = robotics_requirements()
            unknown_tool["tools"] = ["shell"]
            cases.append(("unknown tools", unknown_tool))
            duplicate_keywords = robotics_requirements()
            duplicate_keywords["keywords"] = ["robot arm", "ROBOT ARM"]
            cases.append(("duplicates", duplicate_keywords))
            duplicate_cases = robotics_requirements()
            duplicate_cases["evaluations"] = [
                {"name": "robot_arm", "prompt": "robot arm evidence"},
                {"name": "robot_arm", "prompt": "robot arm tests"},
            ]
            cases.append(("unique", duplicate_cases))
            no_route = robotics_requirements()
            no_route["evaluations"] = [
                {"name": "unrouted", "prompt": "Analyze this system"},
            ]
            cases.append(("routing keyword", no_route))
            shadowed = robotics_requirements()
            shadowed["name"] = "aaa_research"
            shadowed["keywords"] = ["research"]
            shadowed["evaluations"] = [
                {"name": "shadowed", "prompt": "research this topic"},
            ]
            cases.append(("does not route", shadowed))
            bad_scalar = robotics_requirements()
            bad_scalar["purpose"] = ["not", "a", "string"]
            cases.append(("must be a string", bad_scalar))
            oversized = robotics_requirements()
            oversized["evaluations"] = [
                {
                    "name": f"large_{index}",
                    "prompt": "robot arm " + ("x" * 1_980),
                }
                for index in range(20)
            ]
            cases.append(("exceed 32000", oversized))

            for message, requirements in cases:
                with self.subTest(message=message):
                    with self.assertRaisesRegex(ValueError, message):
                        builder.prepare(requirements)
            self.assertNotIn("robotics_research", registry.names)
            self.assertEqual(builder.store.list(), [])

    def test_blueprint_persistence_failure_rolls_back_agent_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            builder, registry = self._builder(root)
            builder.store.save = Mock(side_effect=RuntimeError("storage unavailable"))
            with self.assertRaisesRegex(RuntimeError, "storage unavailable"):
                builder.build(robotics_requirements(), approved=True)
            self.assertNotIn("robotics_research", registry.names)
            self.assertNotIn(
                "robotics_research",
                AgentRegistry(
                    GeneratedAgentStore(root / "agents.sqlite3"),
                    allowed_tools={"calculator"},
                ).names,
            )


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
