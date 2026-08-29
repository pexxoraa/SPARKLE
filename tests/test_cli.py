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


class CLITests(unittest.TestCase):
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
