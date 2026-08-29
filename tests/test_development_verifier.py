from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sparkle.builders import WorkspaceManager
from sparkle.development import DevelopmentVerifier
from sparkle.tooling import ToolError, WorkspaceVerifyTool


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
        })
        self.verifier = DevelopmentVerifier(
            self.workspaces.root, self.root / "verifications.sqlite3",
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
