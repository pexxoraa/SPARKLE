from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sparkle.config import AppConfig
from sparkle.providers.mock import DeterministicAdapter
from sparkle.registry import ModelRegistry
from sparkle.system import SparkleSystem


def test_config() -> AppConfig:
    return AppConfig("127.0.0.1", 0, 4, 5, 5, False, False)


class AutomationRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {"SPARKLE_DATA_DIR": self.temp.name}, clear=False)
        self.env_patch.start()
        registry = ModelRegistry()
        registry.inject(registry.active_id, DeterministicAdapter())
        self.system = SparkleSystem(config=test_config(), model_registry=registry)

    def tearDown(self):
        self.env_patch.stop()
        self.temp.cleanup()

    def test_once_executes_agent_disables_and_traces(self):
        now = datetime.now(UTC)
        automation_id = self.system.automations.create(
            "Daily focus",
            "once",
            {"type": "agent", "prompt": "What should I focus on?", "agent": "personal"},
            next_run_at=(now - timedelta(minutes=1)).isoformat(),
        )
        runs = self.system.automation_runner.run_due(now)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "success")
        self.assertRegex(runs[0]["trace_id"], r"SPK-\d{4}-\d{6}")
        record = next(item for item in self.system.automations.list() if item["id"] == automation_id)
        self.assertFalse(record["enabled"])
        self.assertEqual(record["last_status"], "success")
        self.assertEqual(self.system.traces.recent()[0]["input_source"], "automation")

    def test_recurring_reschedules_and_failure_retries_are_recorded(self):
        now = datetime.now(UTC)
        self.system.automations.create(
            "Weekly project review", "weekly",
            {"type": "agent", "prompt": "Review active projects", "agent": "project"},
            next_run_at=(now - timedelta(days=8)).isoformat(),
        )
        successful = self.system.automation_runner.run_due(now)[0]
        self.assertEqual(successful["status"], "success")
        self.assertGreater(datetime.fromisoformat(successful["next_run_at"]), now)

        self.system.automations.create(
            "Broken agent", "once",
            {
                "type": "agent", "prompt": "This must fail",
                "agent": "missing_agent", "max_attempts": 2,
            },
            next_run_at=(now - timedelta(minutes=1)).isoformat(),
        )
        failed = self.system.automation_runner.run_due(now)[0]
        self.assertEqual(failed["status"], "failure")
        self.assertEqual(failed["attempts"], 2)
        self.assertEqual(failed["error_type"], "KeyError")

    def test_deadline_condition_obeys_cooldown(self):
        now = datetime.now(UTC)
        self.system.memory.remember(
            "tasks", "report", "Finish the report",
            metadata={"deadline": (now + timedelta(hours=2)).isoformat()},
        )
        self.system.automations.create(
            "Deadline helper", "condition",
            {"type": "agent", "prompt": "Prioritize the report", "agent": "personal"},
            condition={
                "type": "memory_deadline", "alert": "deadline_approaching",
                "category": "tasks", "key": "report", "cooldown_minutes": 60,
            },
        )
        self.assertEqual(self.system.automation_runner.run_due(now)[0]["status"], "success")
        self.assertEqual(self.system.automation_runner.run_due(now + timedelta(minutes=10)), [])

    def test_structured_proactive_condition_obeys_cooldown(self):
        now = datetime.now(UTC)
        self.system.memory.remember(
            "skills",
            "python",
            "Python evidence",
            metadata={
                "evidence_count": 3,
                "mastery_level": 1,
                "target_level": 3,
            },
        )
        self.system.automations.create(
            "Weak skill helper",
            "condition",
            {"type": "agent", "prompt": "Plan Python practice", "agent": "learning"},
            condition={
                "type": "proactive_alert",
                "alert": "weak_learning",
                "category": "skills",
                "key": "python",
                "cooldown_minutes": 60,
            },
        )
        first = self.system.automation_runner.run_due(now)
        self.assertEqual(first[0]["status"], "success")
        self.assertEqual(
            self.system.automation_runner.run_due(now + timedelta(minutes=10)), [],
        )

    def test_schedule_conflict_condition_executes_once_per_cooldown(self):
        now = datetime.now(UTC)
        self.system.memory.remember(
            "tasks", "robot_lab", "Private lab details",
            metadata={
                "starts_at": (now + timedelta(hours=1)).isoformat(),
                "ends_at": (now + timedelta(hours=3)).isoformat(),
            },
        )
        self.system.memory.remember(
            "exams", "controls_exam", "Private exam details",
            metadata={
                "starts_at": (now + timedelta(hours=2)).isoformat(),
                "ends_at": (now + timedelta(hours=4)).isoformat(),
            },
        )
        self.system.automations.create(
            "Schedule helper",
            "condition",
            {
                "type": "agent", "prompt": "Resolve my schedule conflict",
                "agent": "productivity",
            },
            condition={
                "type": "proactive_alert",
                "alert": "schedule_conflict",
                "category": "tasks",
                "key": "robot_lab",
                "cooldown_minutes": 60,
            },
        )
        first = self.system.automation_runner.run_due(now)
        self.assertEqual(first[0]["status"], "success")
        self.assertEqual(
            self.system.automation_runner.run_due(now + timedelta(minutes=10)),
            [],
        )

    def test_research_change_condition_executes_once_per_cooldown(self):
        now = datetime.now(UTC)
        metadata = {
            "research_monitor": True, "monitor_key": "robotics.papers",
        }
        with patch("sparkle.storage.utc_now", return_value=now.isoformat()):
            self.system.knowledge.ingest_text(
                "Robotics source", "Original bounded research", metadata=metadata,
            )
            self.system.knowledge.ingest_text(
                "Robotics source", "Revised bounded research", metadata=metadata,
            )
        self.system.automations.create(
            "Research change helper", "condition",
            {
                "type": "agent", "prompt": "Review the research update",
                "agent": "research",
            },
            condition={
                "type": "proactive_alert",
                "alert": "research_change",
                "category": "research",
                "key": "robotics.papers",
                "cooldown_minutes": 60,
            },
        )
        first = self.system.automation_runner.run_due(now)
        self.assertEqual(first[0]["status"], "success")
        self.assertEqual(
            self.system.automation_runner.run_due(now + timedelta(minutes=10)),
            [],
        )

    def test_proactive_condition_delivers_dashboard_notification_and_trace(self):
        now = datetime.now(UTC)
        self.system.memory.remember(
            "tasks", "robot_report", "Private report details",
            metadata={"deadline": (now + timedelta(hours=2)).isoformat()},
        )
        self.system.automations.create(
            "Dashboard deadline alert", "condition",
            {
                "type": "notification",
                "channel": "dashboard",
                "title": "Robot report deadline",
                "body": "Review the robot report before its deadline.",
                "severity": "warning",
                "dedupe_key": "deadline.robot_report",
            },
            condition={
                "type": "proactive_alert",
                "alert": "deadline_approaching",
                "category": "tasks",
                "key": "robot_report",
                "cooldown_minutes": 60,
            },
        )
        runs = self.system.automation_runner.run_due(now)
        self.assertEqual(runs[0]["status"], "success")
        notification = self.system.notifications.list()[0]
        self.assertEqual(notification["source"], "automation")
        self.assertEqual(notification["status"], "delivered")
        trace = self.system.traces.recent()[0]
        self.assertEqual(trace["trace_id"], runs[0]["trace_id"])
        self.assertEqual(trace["processing_stage"], "notification_delivered")
        self.assertEqual(trace["output_modalities"], ["notification"])
        self.assertEqual(
            trace["storage_destinations"], ["data_environment/notifications"],
        )
        serialized_trace = json.dumps(trace)
        self.assertNotIn("Review the robot report", serialized_trace)
        self.assertNotIn("Private report details", serialized_trace)
        self.assertEqual(
            self.system.automation_runner.run_due(now + timedelta(minutes=10)),
            [],
        )
