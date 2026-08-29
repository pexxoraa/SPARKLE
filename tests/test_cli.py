from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sparkle.cli import main


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
