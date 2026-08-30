from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from sparkle.projects import ProjectStore
from sparkle.system import SparkleSystem
from sparkle.tooling import ToolError


def project_manifest(name: str = "sparkle_core") -> dict[str, object]:
    return {
        "name": name,
        "title": "SPARKLE core platform",
        "description": "Build and verify the provider-neutral personal AI platform.",
        "status": "implementation",
        "priority": "critical",
        "deadline": "2026-09-30T18:00:00+05:30",
        "dependencies": [],
        "risks": ["External provider verification is unavailable."],
        "milestones": [{
            "name": "Structured project tracking",
            "status": "in_progress",
            "due_at": "2026-09-05T12:00:00Z",
        }],
        "blockers": [],
        "next_action": "Complete the structured project-state integration.",
        "progress": 90,
    }


class ProjectStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {"SPARKLE_DATA_DIR": self.temp.name}, clear=False,
        )
        self.environment.start()
        self.store = ProjectStore()

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def test_create_update_reload_and_content_free_events(self):
        created = self.store.create(project_manifest())
        self.assertEqual(created["protocol_version"], "SPARKLE-PROJECT/1")
        self.assertEqual(created["deadline"], "2026-09-30T12:30:00+00:00")
        self.assertEqual(created["version"], 1)
        updated = self.store.update(
            "sparkle_core",
            {
                "status": "testing",
                "progress": 95,
                "next_action": "Run the complete v0.22 regression suite.",
                "milestones": [{
                    "name": "Structured project tracking",
                    "status": "complete",
                    "due_at": "2026-09-05T12:00:00Z",
                }],
            },
            expected_version=1,
        )
        self.assertEqual(updated["version"], 2)
        self.assertEqual(ProjectStore().get("sparkle_core"), updated)
        events = self.store.events("sparkle_core")
        self.assertEqual([item["action"] for item in events], ["updated", "created"])
        serialized = json.dumps(events)
        self.assertNotIn("personal AI platform", serialized)
        self.assertNotIn("External provider", serialized)
        self.assertNotIn("Run the complete", serialized)
        self.assertEqual(
            events[0]["changed_fields"],
            ["milestones", "next_action", "progress", "status"],
        )

    def test_validation_and_optimistic_conflicts_fail_closed(self):
        cases: list[dict[str, object]] = []
        unknown = project_manifest()
        unknown["provider"] = "minimax"
        cases.append(unknown)
        self_dependency = project_manifest()
        self_dependency["dependencies"] = ["sparkle_core"]
        cases.append(self_dependency)
        duplicate_risk = project_manifest()
        duplicate_risk["risks"] = ["same", "SAME"]
        cases.append(duplicate_risk)
        blocked_without_evidence = project_manifest()
        blocked_without_evidence["status"] = "blocked"
        cases.append(blocked_without_evidence)
        false_complete = project_manifest()
        false_complete["status"] = "complete"
        cases.append(false_complete)
        boolean_progress = project_manifest()
        boolean_progress["progress"] = True
        cases.append(boolean_progress)
        naive_deadline = project_manifest()
        naive_deadline["deadline"] = "2026-09-30T12:00:00"
        cases.append(naive_deadline)
        invalid_milestone = project_manifest()
        invalid_milestone["milestones"] = [{
            "name": "Boundary", "status": "pretend_done", "due_at": None,
        }]
        cases.append(invalid_milestone)
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.store.create(value)
        self.assertEqual(self.store.list(), [])

        self.store.create(project_manifest())
        with self.assertRaisesRegex(ValueError, "version conflict"):
            self.store.update(
                "sparkle_core", {"progress": 91}, expected_version=4,
            )
        self.assertEqual(self.store.get("sparkle_core")["progress"], 90)

    def test_priority_order_search_archive_and_stats(self):
        secondary = project_manifest("robot_dashboard")
        secondary["title"] = "Robot dashboard"
        secondary["priority"] = "medium"
        secondary["deadline"] = None
        secondary["progress"] = 30
        self.store.create(secondary)
        blocked = project_manifest("sparkle_core")
        blocked["status"] = "blocked"
        blocked["blockers"] = ["A named deployment target is unavailable."]
        self.store.create(blocked)
        self.assertEqual(
            [item["name"] for item in self.store.list()],
            ["sparkle_core", "robot_dashboard"],
        )
        self.assertEqual(self.store.search("dashboard")[0]["name"], "robot_dashboard")
        self.assertEqual(self.store.search("%"), [])
        self.assertEqual(
            {item["name"] for item in self.store.search("_")},
            {"sparkle_core", "robot_dashboard"},
        )
        self.assertEqual(self.store.search("!"), [])
        archived = self.store.archive("robot_dashboard", expected_version=1)
        self.assertTrue(archived["archived"])
        self.assertEqual(self.store.stats(), {"active": 1, "archived": 1, "blocked": 1})
        self.assertEqual([item["name"] for item in self.store.list()], ["sparkle_core"])
        self.assertEqual(len(self.store.list(include_archived=True)), 2)
        with self.assertRaisesRegex(ValueError, "Archived"):
            self.store.update(
                "robot_dashboard", {"progress": 40}, expected_version=2,
            )

    def test_project_search_tool_is_read_only_and_least_privileged(self):
        self.store.create(project_manifest())
        system = SparkleSystem()
        result = system.tools.execute(
            "project_search", {"query": "SPARKLE", "limit": 5},
            allowed=system.agents.get("project").tools,
        )
        self.assertEqual(result[0]["name"], "sparkle_core")
        self.assertIn("project_search", system.agents.get("personal").tools)
        self.assertIn("project_search", system.agents.get("productivity").tools)
        self.assertNotIn("project_search", system.agents.get("research").tools)
        with self.assertRaises(ToolError):
            system.tools.execute(
                "project_search", {"query": "SPARKLE"},
                allowed=system.agents.get("research").tools,
            )
        with self.assertRaises(ToolError):
            system.tools.execute(
                "project_search", {"query": "SPARKLE", "write": True},
                allowed=system.agents.get("project").tools,
            )

    def test_active_project_and_change_evidence_bounds(self):
        with patch.object(ProjectStore, "MAX_PROJECTS", 1):
            self.store.create(project_manifest())
            with self.assertRaisesRegex(ValueError, "1000 active-project bound"):
                self.store.create(project_manifest("second_project"))
            self.store.archive("sparkle_core", expected_version=1)
            self.store.create(project_manifest("second_project"))

        with patch.object(ProjectStore, "MAX_EVENTS", 2):
            self.store.update(
                "second_project", {"progress": 91}, expected_version=1,
            )
            self.store.update(
                "second_project", {"progress": 92}, expected_version=2,
            )
        with self.store.connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM project_events"
            ).fetchone()[0]
        self.assertEqual(count, 2)
        self.assertEqual(
            [event["version"] for event in self.store.events("second_project")],
            [3, 2],
        )

    def test_structured_projects_drive_content_free_proactive_evidence(self):
        project = project_manifest()
        project["status"] = "blocked"
        project["deadline"] = "2026-08-29T12:00:00Z"
        project["blockers"] = ["Private deployment target details are missing."]
        self.store.create(project)
        alerts = SparkleSystem().proactive.inspect(
            now=datetime(2026, 8, 30, 18, 0, tzinfo=UTC),
        )
        project_alerts = [
            item for item in alerts if item.get("source_kind") == "project"
        ]
        self.assertEqual(
            {item["type"] for item in project_alerts},
            {"project_incomplete", "overdue"},
        )
        incomplete = next(
            item for item in project_alerts
            if item["type"] == "project_incomplete"
        )
        self.assertEqual(incomplete["evidence"]["blocker_count"], 1)
        self.assertEqual(incomplete["evidence"]["open_milestone_count"], 1)
        serialized = json.dumps(project_alerts)
        self.assertNotIn("personal AI platform", serialized)
        self.assertNotIn("Private deployment", serialized)
        self.assertNotIn("External provider", serialized)


if __name__ == "__main__":
    unittest.main()
