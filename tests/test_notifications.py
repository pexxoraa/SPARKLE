from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from sparkle.automation import AutomationStore
from sparkle.notifications import NotificationStore


class NotificationStoreTests(unittest.TestCase):
    def test_refreshed_dedupe_record_uses_delivery_time_for_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            store = NotificationStore(Path(directory) / "notifications.sqlite3")
            times = [
                f"2026-08-30T12:00:0{index}+00:00" for index in range(4)
            ]
            with (
                patch.object(NotificationStore, "MAX_RECORDS", 2),
                patch("sparkle.notifications.utc_now", side_effect=times),
            ):
                store.deliver(
                    channel="dashboard", title="Tracked", body="First",
                    dedupe_key="tracked", source="system",
                )
                store.deliver(
                    channel="dashboard", title="Older", body="Second",
                    source="system",
                )
                store.deliver(
                    channel="dashboard", title="Tracked refreshed", body="Third",
                    dedupe_key="tracked", source="system",
                )
                store.deliver(
                    channel="dashboard", title="Newest", body="Fourth",
                    source="system",
                )
            self.assertEqual(
                [item["title"] for item in store.list()],
                ["Newest", "Tracked refreshed"],
            )

    def test_automation_notification_action_schema_is_strict(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AutomationStore(Path(directory) / "automations.sqlite3")
            due = datetime.now(UTC).isoformat()
            valid = {
                "type": "notification",
                "channel": "dashboard",
                "title": "Safe title",
                "body": "Safe body",
                "severity": "info",
                "dedupe_key": "safe.key",
            }
            self.assertGreater(
                store.create("Valid", "once", valid, next_run_at=due), 0,
            )
            invalid = (
                {**valid, "channel": "email"},
                {**valid, "unexpected": True},
                {**valid, "max_attempts": 4},
            )
            for index, action in enumerate(invalid):
                with self.assertRaises(ValueError):
                    store.create(
                        f"Invalid {index}", "once", action, next_run_at=due,
                    )
            self.assertEqual(len(store.list()), 1)

    def test_delivery_deduplication_read_state_and_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            store = NotificationStore(Path(directory) / "notifications.sqlite3")
            first = store.deliver(
                channel="dashboard",
                title="Robot project",
                body="Review the controls milestone",
                severity="warning",
                dedupe_key="project.controls",
                source="manual",
            )
            updated = store.deliver(
                channel="dashboard",
                title="Robot project updated",
                body="Review the revised controls milestone",
                severity="critical",
                dedupe_key="project.controls",
                source="automation",
            )
            self.assertEqual(
                first["notification_id"], updated["notification_id"],
            )
            self.assertEqual(store.stats(), {"total": 1, "unread": 1})
            self.assertEqual(store.list(unread_only=True)[0]["severity"], "critical")
            self.assertTrue(store.mark_read(updated["notification_id"]))
            self.assertFalse(store.mark_read(updated["notification_id"]))
            self.assertEqual(store.list(unread_only=True), [])
            self.assertEqual(store.stats(), {"total": 1, "unread": 0})

            with patch.object(NotificationStore, "MAX_RECORDS", 2):
                for index in range(3):
                    store.deliver(
                        channel="dashboard",
                        title=f"Bounded {index}",
                        body="Bounded body",
                        source="system",
                    )
            self.assertEqual(store.stats()["total"], 2)
            self.assertEqual(
                [item["title"] for item in store.list()],
                ["Bounded 2", "Bounded 1"],
            )

    def test_invalid_notifications_fail_before_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            store = NotificationStore(Path(directory) / "notifications.sqlite3")
            invalid = (
                {"channel": "email", "title": "Title", "body": "Body"},
                {"channel": "dashboard", "title": "", "body": "Body"},
                {
                    "channel": "dashboard", "title": "Title",
                    "body": "x" * 2_001,
                },
                {
                    "channel": "dashboard", "title": "Title", "body": "Body",
                    "severity": "unknown",
                },
                {
                    "channel": "dashboard", "title": "Title", "body": "Body",
                    "dedupe_key": "invalid key",
                },
            )
            for value in invalid:
                with self.assertRaises(ValueError):
                    store.deliver(source="manual", **value)
            self.assertEqual(store.stats(), {"total": 0, "unread": 0})
