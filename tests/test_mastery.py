from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from sparkle.mastery import SkillMasteryStore
from sparkle.system import SparkleSystem
from sparkle.tooling import ToolError


def skill_manifest(name: str = "python") -> dict[str, object]:
    return {
        "name": name,
        "title": "Python software engineering",
        "description": "Build reliable Python applications independently.",
        "target_level": 6,
    }


def evidence(
    evidence_type: str = "question",
    *,
    name: str = "python",
    score: int = 90,
    verified: bool = True,
    sequence: int = 1,
) -> dict[str, object]:
    return {
        "skill_name": name,
        "evidence_type": evidence_type,
        "score": score,
        "verified": verified,
        "summary": f"Private evidence details {sequence}",
        "artifact_ref": f"artifact://private/{sequence}",
        "occurred_at": f"2026-08-{sequence:02d}T12:00:00+05:30",
    }


class SkillMasteryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {"SPARKLE_DATA_DIR": self.temp.name}, clear=False,
        )
        self.environment.start()
        self.store = SkillMasteryStore()

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def test_levels_are_derived_only_from_verified_evidence(self):
        created = self.store.create(skill_manifest())
        self.assertEqual(created["protocol_version"], "SPARKLE-SKILL/1")
        self.assertEqual(created["current_level"], 0)
        self.store.add_evidence(evidence("question", verified=False))
        self.assertEqual(self.store.get("python")["current_level"], 0)

        sequence = [
            "question", "exercise", "test", "project", "implementation",
            "question", "exercise", "independent_problem_solving", "test",
            "project",
        ]
        expected = [1, 2, 3, 3, 4, 4, 5, 5, 5, 6]
        for index, (kind, level) in enumerate(zip(sequence, expected), start=2):
            result = self.store.add_evidence(
                evidence(kind, sequence=index),
            )
            self.assertEqual(result["skill"]["current_level"], level)
        final = SkillMasteryStore().get("python")
        self.assertEqual(final["current_level_name"], "expert_research")
        self.assertEqual(final["verified_evidence_count"], 10)
        self.assertEqual(final["total_evidence_count"], 11)
        self.assertEqual(final["average_verified_score"], 90.0)
        self.assertEqual(final["next_level_requirements"], [])

    def test_strict_skill_and_evidence_validation(self):
        invalid = []
        extra = skill_manifest()
        extra["provider"] = "minimax"
        invalid.append(extra)
        boolean_level = skill_manifest()
        boolean_level["target_level"] = True
        invalid.append(boolean_level)
        invalid_name = skill_manifest("Python")
        invalid.append(invalid_name)
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.store.create(value)
        self.store.create(skill_manifest())
        cases = []
        wrong_type = evidence("pretend")
        cases.append(wrong_type)
        boolean_score = evidence()
        boolean_score["score"] = True
        cases.append(boolean_score)
        string_verified = evidence()
        string_verified["verified"] = "yes"
        cases.append(string_verified)
        naive_time = evidence()
        naive_time["occurred_at"] = "2026-08-01T12:00:00"
        cases.append(naive_time)
        extra_field = evidence()
        extra_field["model"] = "MiniMax-M3"
        cases.append(extra_field)
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.store.add_evidence(value)
        self.assertEqual(self.store.get("python")["total_evidence_count"], 0)

    def test_agent_view_is_bounded_and_excludes_private_evidence_content(self):
        self.store.create(skill_manifest())
        self.store.add_evidence(evidence())
        view = self.store.agent_search("Python", limit=5)
        self.assertEqual(view[0]["current_level"], 1)
        serialized = json.dumps(view)
        self.assertNotIn("Private evidence", serialized)
        self.assertNotIn("artifact://", serialized)
        self.assertNotIn("Build reliable", serialized)
        self.assertNotIn("summary", serialized)
        self.assertNotIn("artifact_ref", serialized)
        self.assertEqual(
            self.store.search("%")[0:] if self.store.search("%") else [], [],
        )
        self.assertEqual(self.store.search("!"), [])

    def test_update_archive_order_and_optimistic_conflicts(self):
        secondary = skill_manifest("robotics")
        secondary["title"] = "Robotics engineering"
        secondary["target_level"] = 3
        self.store.create(secondary)
        self.store.create(skill_manifest())
        self.assertEqual(
            [item["name"] for item in self.store.list()],
            ["python", "robotics"],
        )
        updated = self.store.update(
            "python", {"target_level": 5}, expected_version=1,
        )
        self.assertEqual(updated["version"], 2)
        with self.assertRaisesRegex(ValueError, "version conflict"):
            self.store.update(
                "python", {"target_level": 4}, expected_version=1,
            )
        archived = self.store.archive("python", expected_version=2)
        self.assertTrue(archived["archived"])
        with self.assertRaisesRegex(ValueError, "Archived"):
            self.store.add_evidence(evidence())
        self.assertEqual(self.store.stats(), {
            "active": 1, "archived": 1, "below_target": 1,
        })

    def test_active_skill_and_evidence_bounds(self):
        with patch.object(SkillMasteryStore, "MAX_SKILLS", 1):
            self.store.create(skill_manifest())
            with self.assertRaisesRegex(ValueError, "1000 active-skill bound"):
                self.store.create(skill_manifest("robotics"))
            self.store.archive("python", expected_version=1)
            self.store.create(skill_manifest("robotics"))
        with patch.object(SkillMasteryStore, "MAX_EVIDENCE_PER_SKILL", 1):
            self.store.add_evidence(evidence(name="robotics"))
            with self.assertRaisesRegex(ValueError, "100-evidence bound"):
                self.store.add_evidence(
                    evidence(name="robotics", sequence=2),
                )

    def test_timezone_normalization_and_evidence_read_boundary(self):
        self.store.create(skill_manifest())
        result = self.store.add_evidence(evidence())
        item = result["evidence"]
        self.assertEqual(item["occurred_at"], "2026-08-01T06:30:00+00:00")
        self.assertEqual(self.store.evidence("python"), [item])
        with self.assertRaisesRegex(ValueError, "Duplicate skill evidence"):
            self.store.add_evidence(evidence())
        self.assertEqual(self.store.get("python")["total_evidence_count"], 1)
        with self.assertRaises(ValueError):
            self.store.evidence_by_id(True)
        with self.assertRaises(KeyError):
            self.store.evidence_by_id(999)

    def test_skill_tool_is_read_only_and_least_privileged(self):
        self.store.create(skill_manifest())
        self.store.add_evidence(evidence())
        system = SparkleSystem()
        result = system.tools.execute(
            "skill_search", {"query": "Python", "limit": 5},
            allowed=system.agents.get("skill").tools,
        )
        self.assertEqual(result[0]["current_level"], 1)
        for agent in ("personal", "learning", "skill"):
            self.assertIn("skill_search", system.agents.get(agent).tools)
        self.assertNotIn("skill_search", system.agents.get("research").tools)
        with self.assertRaises(ToolError):
            system.tools.execute(
                "skill_search", {"query": "Python"},
                allowed=system.agents.get("research").tools,
            )
        with self.assertRaises(ToolError):
            system.tools.execute(
                "skill_search", {"query": "Python", "write": True},
                allowed=system.agents.get("skill").tools,
            )

    def test_structured_mastery_drives_content_free_proactive_evidence(self):
        self.store.create(skill_manifest())
        self.store.add_evidence(evidence())
        alerts = SparkleSystem().proactive.inspect(
            now=datetime(2026, 8, 30, 18, 0, tzinfo=UTC),
        )
        skill_alerts = [
            item for item in alerts if item.get("source_kind") == "skill"
        ]
        self.assertEqual(len(skill_alerts), 1)
        alert = skill_alerts[0]
        self.assertEqual(alert["type"], "weak_learning")
        self.assertEqual(alert["evidence"]["mastery_level"], 1)
        self.assertEqual(alert["evidence"]["target_level"], 6)
        self.assertEqual(alert["evidence"]["verified_evidence_count"], 1)
        serialized = json.dumps(skill_alerts)
        self.assertNotIn("Private evidence", serialized)
        self.assertNotIn("artifact://", serialized)
        self.assertNotIn("Build reliable", serialized)

    def test_structured_mastery_alert_runs_matching_conditional_automation(self):
        system = SparkleSystem()
        system.skills.create(skill_manifest())
        system.skills.add_evidence(evidence())
        system.automations.create(
            "Python mastery reminder",
            "condition",
            {
                "type": "notification",
                "channel": "dashboard",
                "title": "Python practice is due",
                "body": "Complete the next evidence-backed practice step.",
                "severity": "info",
            },
            condition={
                "type": "proactive_alert",
                "alert": "weak_learning",
                "category": "skills",
                "key": "python",
                "cooldown_minutes": 60,
            },
        )
        runs = system.automation_runner.run_due(
            datetime(2026, 8, 31, 2, 0, tzinfo=UTC),
        )
        self.assertEqual(runs[0]["status"], "success")
        self.assertEqual(system.notifications.stats()["total"], 1)


if __name__ == "__main__":
    unittest.main()
