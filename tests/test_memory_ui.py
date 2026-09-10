"""Deterministic DOM contract tests; not real-browser acceptance evidence."""
import shutil
import subprocess
import unittest
from pathlib import Path


class MemoryUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required for deterministic UI tests')
    def test_review_interactions(self):
        result = subprocess.run(
            ['node', '--test', str(Path(__file__).with_name('memory_review_ui.test.cjs'))],
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
