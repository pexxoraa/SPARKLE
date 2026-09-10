from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sparkle.cli import entrypoint, main
from sparkle.providers.mock import DeterministicAdapter
from sparkle.registry import ModelRegistry
from sparkle.system import SparkleSystem


class CLITests(unittest.TestCase):
    def test_memory_review_commands_require_exact_proposal(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"SPARKLE_DATA_DIR": directory}):
            system = SparkleSystem()
            proposal = system.memory_review.propose({"category":"goals", "key":"fixture", "value":"Practice daily"})
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["memory-proposals"]), 0)
            self.assertEqual(json.loads(output.getvalue())["proposals"][0]["id"], proposal["proposal_id"])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["memory-review",proposal["proposal_id"],proposal["digest"],"approve"]), 0)
            self.assertEqual(system.memory.export()[0]["metadata"]["reviewer"], "cli")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["memory-proposals", "--status", "approved"]), 0)
            self.assertEqual(json.loads(output.getvalue())["proposals"][0]["id"], proposal["proposal_id"])

    def test_model_request_evidence_command_is_content_free(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with (
                patch.dict(
                    os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False,
                ),
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(main(["model-requests", "--limit", "5"]), 0)
            payload = json.loads(output.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["model_requests"], [])

    def test_structured_project_create_update_list_and_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "project.json"
            manifest.write_text(json.dumps({
                "name": "sparkle_core",
                "title": "SPARKLE core platform",
                "description": "Build and verify the provider-neutral personal AI platform.",
                "status": "implementation",
                "priority": "critical",
                "deadline": "2026-09-30T12:30:00Z",
                "dependencies": [],
                "risks": ["External provider verification is unavailable."],
                "milestones": [{
                    "name": "Structured project tracking",
                    "status": "in_progress",
                    "due_at": "2026-09-05T12:00:00Z",
                }],
                "blockers": [],
                "next_action": "Complete structured project-state integration.",
                "progress": 90,
            }), encoding="utf-8")
            changes = Path(directory) / "changes.json"
            changes.write_text(json.dumps({
                "progress": 95,
                "next_action": "Run the complete project regression suite.",
            }), encoding="utf-8")
            output = io.StringIO()
            error = io.StringIO()
            with (
                patch.dict(
                    os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False,
                ),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(error),
            ):
                self.assertEqual(main([
                    "project-create", str(manifest),
                ]), 0)
                self.assertEqual(main([
                    "project-update", "sparkle_core", str(changes),
                    "--expected-version", "1",
                ]), 0)
                self.assertEqual(main([
                    "projects", "--query", "SPARKLE",
                ]), 0)
                self.assertEqual(entrypoint([
                    "project-archive", "sparkle_core",
                    "--expected-version", "2",
                ]), 1)
                self.assertEqual(main([
                    "project-archive", "sparkle_core",
                    "--expected-version", "2", "--approve",
                ]), 0)
                self.assertEqual(main([
                    "projects", "--include-archived",
                ]), 0)
            self.assertIn("SPARKLE-PROJECT/1", output.getvalue())
            self.assertIn('"version": 2', output.getvalue())
            self.assertIn('"archived": true', output.getvalue())
            self.assertIn("explicit approval", error.getvalue())
            self.assertNotIn("Traceback", error.getvalue())

    def test_structured_skill_evidence_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory) / "skill.json"
            skill.write_text(json.dumps({
                "name": "python",
                "title": "Python software engineering",
                "description": "Build reliable Python applications independently.",
                "target_level": 4,
            }), encoding="utf-8")
            evidence = Path(directory) / "evidence.json"
            evidence.write_text(json.dumps({
                "skill_name": "python",
                "evidence_type": "exercise",
                "score": 88,
                "verified": True,
                "summary": "Private exercise evidence.",
                "artifact_ref": "artifact://private/python-1",
                "occurred_at": "2026-08-31T01:00:00Z",
            }), encoding="utf-8")
            changes = Path(directory) / "skill-changes.json"
            changes.write_text(json.dumps({"target_level": 5}), encoding="utf-8")
            output = io.StringIO()
            error = io.StringIO()
            with (
                patch.dict(
                    os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False,
                ),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(error),
            ):
                self.assertEqual(main(["skill-create", str(skill)]), 0)
                self.assertEqual(main(["skill-evidence", str(evidence)]), 0)
                self.assertEqual(main([
                    "skill-update", "python", str(changes),
                    "--expected-version", "2",
                ]), 0)
                self.assertEqual(main(["skills", "--query", "Python"]), 0)
                self.assertEqual(entrypoint([
                    "skill-archive", "python", "--expected-version", "3",
                ]), 1)
                self.assertEqual(main([
                    "skill-archive", "python", "--expected-version", "3",
                    "--approve",
                ]), 0)
                self.assertEqual(main([
                    "skills", "--include-archived",
                ]), 0)
            self.assertIn("SPARKLE-SKILL/1", output.getvalue())
            self.assertIn('"current_level": 1', output.getvalue())
            self.assertIn('"archived": true', output.getvalue())
            self.assertIn("explicit approval", error.getvalue())
            self.assertNotIn("Traceback", error.getvalue())

    def test_ai_system_prepare_and_approved_materialization(self):
        with tempfile.TemporaryDirectory() as directory:
            requirements = Path(directory) / "robotics-ai.json"
            requirements.write_text(json.dumps({
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
                    "Analyze evidence with the selected specialist agents.",
                    "Return a traceable result and preserve evaluation evidence.",
                ],
                "evaluations": [{
                    "name": "robotics_integration",
                    "kind": "integration",
                    "criterion": "The system preserves source and trace boundaries.",
                }],
                "deployment": {
                    "environment_name": "staging", "target_kind": "server",
                },
            }), encoding="utf-8")
            output = io.StringIO()
            error = io.StringIO()
            with (
                patch.dict(
                    os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False,
                ),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(error),
            ):
                self.assertEqual(main([
                    "ai-system-prepare", str(requirements),
                ]), 0)
                self.assertEqual(entrypoint([
                    "ai-system-build", str(requirements),
                ]), 1)
                self.assertEqual(main([
                    "ai-system-build", str(requirements), "--approve",
                ]), 0)
                system = SparkleSystem()
            self.assertIn("explicit approval", error.getvalue())
            self.assertNotIn("Traceback", error.getvalue())
            self.assertIn("SPARKLE-AI-SYSTEM-BLUEPRINT/1", output.getvalue())
            self.assertIn("materialized_static_verified", output.getvalue())
            self.assertEqual(
                system.ai_system_blueprints.list()[0]["system_name"],
                "robotics_ai",
            )
            workspace = Path(directory) / "applications" / "robotics_ai"
            self.assertTrue((workspace / "README.md").is_file())
            self.assertTrue((workspace / "SPARKLE_AI_SYSTEM.json").is_file())

    def test_agent_blueprint_prepare_and_approved_build(self):
        with tempfile.TemporaryDirectory() as directory:
            def deterministic_system() -> SparkleSystem:
                registry = ModelRegistry()
                registry.inject(registry.active_id, DeterministicAdapter())
                return SparkleSystem(model_registry=registry)

            requirements = Path(directory) / "robotics-agent.json"
            requirements.write_text(json.dumps({
                "name": "robotics_research",
                "capability": "reasoning",
                "purpose": "Research robotics with evidence and engineering constraints.",
                "tools": ["calculator"],
                "keywords": ["robotics research", "robot arm"],
                "workflow": [
                    "Collect relevant robotics evidence.",
                    "Cross-check sources and state uncertainty.",
                ],
                "guardrails": ["Never fabricate sources or completed tests."],
                "evaluations": [{
                    "name": "robot_arm_evidence",
                    "prompt": "Perform robotics research for a robot arm.",
                    "assertions": {
                        "contains_all": ["SPARKLE processed", "robot arm"],
                        "max_chars": 500,
                    },
                }],
            }), encoding="utf-8")
            output = io.StringIO()
            error = io.StringIO()
            with (
                patch.dict(
                    os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False,
                ),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(error),
                patch("sparkle.cli.SparkleSystem", deterministic_system),
            ):
                self.assertEqual(main([
                    "agent-prepare", str(requirements),
                ]), 0)
                self.assertNotIn(
                    "robotics_research",
                    SparkleSystem().agents.names,
                )
                self.assertEqual(entrypoint([
                    "agent-build", str(requirements),
                ]), 1)
                self.assertEqual(main([
                    "agent-build", str(requirements), "--approve",
                ]), 0)
                self.assertEqual(entrypoint([
                    "agent-evaluate", "robotics_research",
                ]), 1)
                self.assertEqual(main([
                    "agent-evaluate", "robotics_research", "--approve",
                ]), 0)
                system = SparkleSystem()
            self.assertIn("explicit approval", error.getvalue())
            self.assertNotIn("Traceback", error.getvalue())
            self.assertIn("robotics_research", system.agents.names)
            self.assertEqual(
                system.agent_blueprints.list()[0]["agent_name"],
                "robotics_research",
            )
            self.assertIn('"prepared_static_verified"', output.getvalue())
            self.assertIn('"installed_static_verified"', output.getvalue())
            self.assertIn('"SPARKLE-AGENT-EVALUATION/1"', output.getvalue())
            self.assertIn("response evaluation requires explicit approval", error.getvalue())

    def test_ingest_monitor_key_detects_a_later_file_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "robotics.md"
            source.write_text("Original private research", encoding="utf-8")
            output = io.StringIO()
            with (
                patch.dict(
                    os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False,
                ),
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(main([
                    "ingest", str(source), "--monitor-key", "robotics.papers",
                ]), 0)
                source.write_text("Revised private research", encoding="utf-8")
                self.assertEqual(main([
                    "ingest", str(source), "--monitor-key", "robotics.papers",
                ]), 0)
                alerts = SparkleSystem().proactive.inspect()
            research = next(
                item for item in alerts if item["type"] == "research_change"
            )
            self.assertEqual(research["key"], "robotics.papers")
            self.assertNotIn("private research", json.dumps(research).lower())
            self.assertEqual(output.getvalue().count('"source_id"'), 2)

    def test_scaffold_then_verify_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scaffold = root / "scaffold.json"
            scaffold.write_text(json.dumps({
                "project_name": "cli_app",
                "files": {
                    "main.py": "print('compile only')\n",
                    "settings.json": '{"ready": true}\n',
                },
            }), encoding="utf-8")
            verification = root / "verification.json"
            verification.write_text(json.dumps({
                "project_name": "cli_app",
                "checks": [
                    {"type": "python_compile", "path": "main.py"},
                    {"type": "json_parse", "path": "settings.json"},
                ],
            }), encoding="utf-8")
            output = io.StringIO()
            with (
                patch.dict(os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False),
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(main(["scaffold", str(scaffold), "--approve"]), 0)
                self.assertEqual(
                    main(["verify-workspace", str(verification), "--approve"]), 0,
                )
            lines = output.getvalue()
            self.assertIn('"status": "scaffolded"', lines)
            self.assertIn('"status": "passed"', lines)

    def test_scaffold_then_run_fixed_workspace_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scaffold = root / "testable.json"
            scaffold.write_text(json.dumps({
                "project_name": "testable_app",
                "files": {
                    "tests/test_ready.py": (
                        "import unittest\n\n"
                        "class ReadyTests(unittest.TestCase):\n"
                        "    def test_ready(self):\n"
                        "        self.assertTrue(True)\n"
                    ),
                },
            }), encoding="utf-8")
            output = io.StringIO()
            with (
                patch.dict(os.environ, {
                    "SPARKLE_DATA_DIR": directory,
                    "SPARKLE_WORKSPACE_TESTS_ENABLED": "true",
                }, clear=True),
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(main(["scaffold", str(scaffold), "--approve"]), 0)
                self.assertEqual(
                    main(["test-workspace", "testable_app", "--approve"]), 0,
                )
            self.assertIn('"framework": "python_unittest"', output.getvalue())

    def test_entrypoint_reports_approval_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "scaffold.json"
            manifest.write_text(json.dumps({
                "project_name": "blocked_app",
                "files": {"README.md": "blocked"},
            }), encoding="utf-8")
            error = io.StringIO()
            with (
                patch.dict(os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False),
                contextlib.redirect_stderr(error),
            ):
                self.assertEqual(entrypoint(["scaffold", str(manifest)]), 1)
            self.assertIn("requires explicit approval", error.getvalue())
            self.assertNotIn("Traceback", error.getvalue())

    def test_external_workspace_cli_requires_approval_before_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            error = io.StringIO()
            with (
                patch.dict(os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False),
                contextlib.redirect_stderr(error),
            ):
                self.assertEqual(
                    entrypoint(["test-workspace-external", "worker_app"]), 1,
                )
            self.assertIn("requires explicit approval", error.getvalue())
            self.assertNotIn("Traceback", error.getvalue())

    def test_module_entrypoint_reports_bind_refusal_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = {
                **os.environ,
                "SPARKLE_DATA_DIR": directory,
                "SPARKLE_HOST": "0.0.0.0",
                "SPARKLE_API_AUTH_REQUIRED": "false",
            }
            completed = subprocess.run(
                [sys.executable, "-m", "sparkle", "serve"],
                capture_output=True,
                text=True,
                env=environment,
                timeout=10,
                check=False,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertIn("requires authentication", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)
