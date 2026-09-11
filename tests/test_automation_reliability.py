from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sparkle.automation_reliability import (
    ReliableAutomationRunner,
    ReliableAutomationStore,
)


class EmptyProactive:
    def inspect(self, now=None):
        return []


class TraceFixture:
    def __init__(self):
        self.items: list[dict[str, Any]] = []

    def recent(self, limit=5):
        return list(reversed(self.items))[:limit]


class ScriptedRunner(ReliableAutomationRunner):
    def __init__(self, store, outcomes, traces):
        super().__init__(
            store, object(), EmptyProactive(), notifications=None, traces=traces
        )
        self.outcomes = list(outcomes)
        self.calls = 0

    def _execute(self, item):
        self.calls += 1
        outcome = self.outcomes[self.calls - 1]
        if callable(outcome):
            return outcome()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class AutomationReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ReliableAutomationStore(
            Path(self.temp.name) / "automations.sqlite3"
        )
        self.now = datetime.now(UTC)

    def create(self, name, action):
        return self.store.create(
            name,
            "once",
            action,
            next_run_at=(self.now - timedelta(minutes=1)).isoformat(),
        )

    def test_pre_execution_failure_retries_and_records_each_attempt(self):
        automation_id = self.create(
            "retry preexecution",
            {
                "type": "agent",
                "prompt": "run",
                "agent": "missing_agent",
                "max_attempts": 2,
            },
        )
        traces = TraceFixture()
        runner = ScriptedRunner(
            self.store,
            [KeyError("missing"), KeyError("missing")],
            traces,
        )
        run = runner.run_due(self.now)[0]
        self.assertEqual(run["status"], "failure")
        self.assertEqual(run["attempts"], 2)
        self.assertEqual(runner.calls, 2)
        attempts = list(reversed(self.store.list_attempts(automation_id)))
        self.assertEqual([item["attempt"] for item in attempts], [1, 2])
        self.assertEqual(
            [item["retry_allowed"] for item in attempts], [True, False]
        )
        self.assertTrue(all("claim" not in key for item in attempts for key in item))

    def test_tool_side_effect_evidence_suppresses_retry(self):
        automation_id = self.create(
            "unsafe retry",
            {
                "type": "agent",
                "prompt": "run",
                "agent": "personal",
                "max_attempts": 3,
            },
        )
        traces = TraceFixture()

        def failed_after_tool():
            traces.items.append(
                {
                    "trace_id": "SPK-2026-000001",
                    "input_source": "automation",
                    "tools": ["memory_write"],
                    "data_created": ["memory_proposal:1"],
                }
            )
            raise RuntimeError("later failure")

        runner = ScriptedRunner(
            self.store,
            [failed_after_tool, ("should not run", "SPK-2026-000002")],
            traces,
        )
        run = runner.run_due(self.now)[0]
        self.assertEqual(run["status"], "failure")
        self.assertEqual(run["attempts"], 1)
        self.assertEqual(runner.calls, 1)
        attempt = self.store.list_attempts(automation_id)[0]
        self.assertFalse(attempt["retry_allowed"])
        self.assertEqual(attempt["trace_id"], "SPK-2026-000001")

    def test_notification_retry_requires_dedupe_key(self):
        base = {
            "type": "notification",
            "channel": "dashboard",
            "title": "Title",
            "body": "Body",
            "max_attempts": 2,
        }
        first_id = self.create("notification no dedupe", dict(base))
        first = ScriptedRunner(
            self.store,
            [RuntimeError("delivery"), ("unused", "trace")],
            TraceFixture(),
        )
        run = first.run_due(self.now)[0]
        self.assertEqual(run["attempts"], 1)
        self.assertFalse(
            self.store.list_attempts(first_id)[0]["retry_allowed"]
        )

        second_id = self.create(
            "notification with dedupe",
            dict(base, dedupe_key="notification.fixture"),
        )
        second = ScriptedRunner(
            self.store,
            [RuntimeError("delivery"), RuntimeError("delivery")],
            TraceFixture(),
        )
        later = self.now + timedelta(seconds=1)
        run = second.run_due(later)[0]
        self.assertEqual(run["attempts"], 2)
        attempts = list(reversed(self.store.list_attempts(second_id)))
        self.assertEqual(
            [item["retry_allowed"] for item in attempts], [True, False]
        )


if __name__ == "__main__":
    unittest.main()
