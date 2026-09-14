from __future__ import annotations

import json
import subprocess
import unittest

from sparkle.worker_executor import BubblewrapExecutor, FixedUnittestExecutor


class WorkerPreflightDiagnosticTests(unittest.TestCase):
    def test_nonzero_preflight_reports_safe_stage_without_promoting_canaries(self):
        def runner(command, **_kwargs):
            return subprocess.CompletedProcess(command, 23, "", "sensitive host detail")

        executor = BubblewrapExecutor(
            bubblewrap_binary="/usr/bin/true",
            preflight_runner=runner,
        )
        status = executor.status()

        self.assertFalse(status["available"])
        self.assertEqual(status["failure_type"], "IsolationPreflightFailed")
        self.assertEqual(status["preflight_failure_stage"], "sandbox_probe")
        self.assertEqual(status["preflight_failure_reason"], "subprocess_nonzero")
        self.assertEqual(status["preflight_returncode"], 23)
        self.assertFalse(status["preflight_canary_evidence_complete"])
        self.assertFalse(any(status["canaries"].values()))
        self.assertNotIn("sensitive host detail", json.dumps(status))

    def test_failed_canary_evidence_is_preserved_without_weakening_readiness(self):
        evidence = {
            name: True for name in FixedUnittestExecutor.CANARY_NAMES
        }
        evidence["prohibited_network"] = False

        def runner(command, **_kwargs):
            return subprocess.CompletedProcess(command, 4, json.dumps(evidence), "")

        executor = BubblewrapExecutor(
            bubblewrap_binary="/usr/bin/true",
            preflight_runner=runner,
        )
        status = executor.status()

        self.assertFalse(status["available"])
        self.assertFalse(status["hostile_canaries_passed"])
        self.assertTrue(status["preflight_canary_evidence_complete"])
        self.assertFalse(status["canaries"]["prohibited_network"])
        self.assertTrue(status["canaries"]["host_filesystem_read"])
        self.assertEqual(status["preflight_failure_stage"], "sandbox_probe")
        self.assertEqual(status["preflight_returncode"], 4)

    def test_success_clears_failure_diagnostics_and_requires_all_canaries(self):
        evidence = {
            name: True for name in FixedUnittestExecutor.CANARY_NAMES
        }

        def runner(command, **_kwargs):
            return subprocess.CompletedProcess(command, 0, json.dumps(evidence), "")

        status = BubblewrapExecutor(
            bubblewrap_binary="/usr/bin/true",
            preflight_runner=runner,
        ).status()

        self.assertTrue(status["available"])
        self.assertTrue(status["hostile_canaries_passed"])
        self.assertTrue(all(status["canaries"].values()))
        self.assertIsNone(status["failure_type"])
        self.assertIsNone(status["preflight_failure_stage"])
        self.assertIsNone(status["preflight_failure_reason"])
        self.assertEqual(status["preflight_returncode"], 0)
        self.assertTrue(status["preflight_canary_evidence_complete"])


if __name__ == "__main__":
    unittest.main()
