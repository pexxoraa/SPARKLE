from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sparkle.builders import WorkspaceManager
from sparkle.development import DevelopmentVerifier, WorkspaceTestRunner
from sparkle.tooling import ToolError, WorkspaceTestTool, WorkspaceVerifyTool


class DevelopmentVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspaces = WorkspaceManager(
            self.root / "applications", self.root / "builds.sqlite3",
        )
        self.workspaces.scaffold("verified_app", {
            "src/main.py": "raise RuntimeError('must not execute')\n",
            "assets/app.js": "const answer = 42;\n",
            "config/settings.json": '{"enabled": true}\n',
            "src/broken.py": "if True print('broken')\n",
            "tests/test_sample.py": (
                "import os\nimport resource\nimport unittest\n\n"
                "class SampleTests(unittest.TestCase):\n"
                "    def test_environment_is_stripped(self):\n"
                "        print('token=unit-test-value')\n"
                "        self.assertNotIn('MINIMAX_API_KEY', os.environ)\n"
                "        self.assertEqual(resource.getrlimit(resource.RLIMIT_NOFILE)[0], 64)\n"
                "        self.assertEqual(resource.getrlimit(resource.RLIMIT_CORE)[0], 0)\n"
            ),
        })
        self.verifier = DevelopmentVerifier(
            self.workspaces.root, self.root / "verifications.sqlite3",
        )
        self.runner = WorkspaceTestRunner(
            self.workspaces.root,
            self.root / "test_runs.sqlite3",
            enabled=True,
            timeout_seconds=3,
            parent_environment={},
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_static_checks_pass_without_executing_python(self):
        result = self.verifier.verify("verified_app", [
            {"type": "python_compile", "path": "src/main.py"},
            {"type": "javascript_syntax", "path": "assets/app.js"},
            {"type": "json_parse", "path": "config/settings.json"},
        ])
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["passed"], 3)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(self.verifier.list()[0]["verification_id"], result["verification_id"])
        self.assertIn("without execution", result["checks"][0]["output"])

    def test_syntax_failure_is_recorded_as_evidence(self):
        result = self.verifier.verify("verified_app", [
            {"type": "python_compile", "path": "src/broken.py"},
        ])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["checks"][0]["status"], "failed")
        self.assertNotIn(str(self.workspaces.root), result["checks"][0]["output"])

    def test_rejects_escape_symlink_wrong_type_and_unknown_check(self):
        outside = self.root / "outside.py"
        outside.write_text("print('outside')\n", encoding="utf-8")
        (self.workspaces.root / "verified_app/link.py").symlink_to(outside)
        invalid = [
            {"type": "python_compile", "path": "../outside.py"},
            {"type": "python_compile", "path": "link.py"},
            {"type": "json_parse", "path": "src/main.py"},
            {"type": "shell", "path": "src/main.py"},
            {"type": "python_compile", "path": "src/main.py", "command": "run"},
        ]
        for check in invalid:
            with self.subTest(check=check), self.assertRaises(ValueError):
                self.verifier.verify("verified_app", [check])

    def test_tool_requires_explicit_approval(self):
        tool = WorkspaceVerifyTool(self.verifier)
        manifest = {
            "project_name": "verified_app",
            "checks": [{"type": "python_compile", "path": "src/main.py"}],
        }
        with self.assertRaises(ToolError):
            tool.run(manifest)
        manifest["approved"] = True
        self.assertEqual(tool.run(manifest)["status"], "passed")

    def test_missing_node_is_a_bounded_failed_check(self):
        verifier = DevelopmentVerifier(
            self.workspaces.root, self.root / "without-node.sqlite3", node_binary="",
        )
        result = verifier.verify("verified_app", [
            {"type": "javascript_syntax", "path": "assets/app.js"},
        ])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["checks"][0]["output"], "Node.js is unavailable in this runtime")

    def test_fixed_unittest_runner_passes_strips_environment_and_redacts(self):
        result = self.runner.run("verified_app")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["framework"], "python_unittest")
        self.assertEqual(result["test_files"], 1)
        self.assertIn("[REDACTED]", result["output"])
        self.assertNotIn("unit-test-value", result["output"])
        self.assertEqual(self.runner.list()[0]["test_run_id"], result["test_run_id"])
        self.assertFalse(self.runner.status()["network_isolation"])

    def test_runner_requires_opt_in_and_tool_approval(self):
        disabled = WorkspaceTestRunner(
            self.workspaces.root,
            self.root / "disabled_runs.sqlite3",
            enabled=False,
            parent_environment={},
        )
        tool = WorkspaceTestTool(disabled)
        with self.assertRaises(ToolError):
            tool.run({"project_name": "verified_app"})
        with self.assertRaisesRegex(ToolError, "Unsupported workspace test fields"):
            tool.run({
                "project_name": "verified_app",
                "approved": True,
                "command": "arbitrary command",
            })
        with self.assertRaisesRegex(ValueError, "disabled"):
            tool.run({"project_name": "verified_app", "approved": True})

    def test_runner_kills_wall_timeout_and_records_failure(self):
        self.workspaces.scaffold("slow_app", {
            "tests/test_slow.py": (
                "import time\nimport unittest\n\n"
                "class SlowTests(unittest.TestCase):\n"
                "    def test_slow(self):\n"
                "        time.sleep(10)\n"
            ),
        })
        runner = WorkspaceTestRunner(
            self.workspaces.root,
            self.root / "slow_runs.sqlite3",
            enabled=True,
            timeout_seconds=1,
            parent_environment={},
        )
        result = runner.run("slow_app")
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["timed_out"])
        self.assertLess(result["duration_ms"], 5_000)

    def test_runner_output_is_bounded_before_persistence(self):
        self.workspaces.scaffold("noisy_app", {
            "tests/test_noisy.py": (
                "import unittest\n\n"
                "class NoisyTests(unittest.TestCase):\n"
                "    def test_noisy(self):\n"
                "        print('x' * 100000)\n"
            ),
        })
        result = self.runner.run("noisy_app")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(result["output"]), self.runner.MAX_OUTPUT_CHARS)
        self.assertEqual(len(self.runner.list()[0]["output"]), self.runner.MAX_OUTPUT_CHARS)

    def test_runner_rejects_workspace_symlinks(self):
        outside = self.root / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        (self.workspaces.root / "verified_app" / "leak.txt").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.runner.run("verified_app")

    def test_runner_refuses_non_allowlisted_parent_environment(self):
        runner = WorkspaceTestRunner(
            self.workspaces.root,
            self.root / "secret_parent_runs.sqlite3",
            enabled=True,
            parent_environment={"SERVICE_TOKEN": "must-not-be-readable"},
        )
        with self.assertRaisesRegex(ValueError, "dedicated worker"):
            runner.run("verified_app")
        status = runner.status()
        self.assertFalse(status["sanitized_parent"])
        self.assertEqual(status["unexpected_parent_variables"], 1)
