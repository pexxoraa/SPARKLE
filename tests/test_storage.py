from __future__ import annotations

from contextlib import closing

import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sparkle.automation import AutomationStore, ProactiveEngine
from sparkle.knowledge import KnowledgeIngestError, KnowledgeIngestor
from sparkle.storage import KnowledgeStore, MemoryStore
from sparkle.trace import TraceStore


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.temp.name) / "memory.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_upsert_search_and_archive(self):
        memory_id = self.store.remember("goals", "python", "Learn Python fundamentals", importance=0.9)
        self.store.remember("goals", "python", "Build a Python application", importance=1.0)
        matches = self.store.search("Python application")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["id"], memory_id)
        self.assertEqual(matches[0]["value"], "Build a Python application")
        self.assertTrue(self.store.archive(memory_id))
        self.assertEqual(self.store.search("Python"), [])
        self.assertTrue(self.store.restore(memory_id))
        self.assertEqual(self.store.search("Python")[0]["id"], memory_id)
        exported = self.store.export()
        self.assertEqual(exported[0]["key"], "python")
        backup = self.store.backup(Path(self.temp.name) / "backups" / "memory.sqlite3")
        self.assertEqual(MemoryStore(backup).search("Python")[0]["id"], memory_id)
        self.assertTrue(self.store.delete(memory_id))
        self.assertEqual(self.store.export(), [])

    def test_rejects_unknown_category(self):
        with self.assertRaises(ValueError):
            self.store.remember("secrets", "key", "value")


class KnowledgeTests(unittest.TestCase):
    def test_ingest_chunk_search_and_stats(self):
        with tempfile.TemporaryDirectory() as directory:
            store = KnowledgeStore(Path(directory) / "knowledge.sqlite3")
            source_id = store.ingest_text("Robotics notes", "Inverse kinematics maps targets to joint angles.\n\nServos require torque calculations.", chunk_chars=50)
            matches = store.search("joint angles kinematics")
            self.assertEqual(matches[0]["source_id"], source_id)
            self.assertIn("kinematics", matches[0]["content"])
            self.assertEqual(store.stats(), {"sources": 1, "chunks": 2})
            self.assertEqual(store.list_sources()[0]["source_id"], source_id)
            backup = store.backup(Path(directory) / "backups" / "knowledge.sqlite3")
            self.assertEqual(KnowledgeStore(backup).stats(), {"sources": 1, "chunks": 2})
            self.assertTrue(store.delete_source(source_id))
            self.assertEqual(store.stats(), {"sources": 0, "chunks": 0})

    def test_file_ingestor_supports_markdown_and_rejects_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = KnowledgeStore(root / "knowledge.sqlite3")
            source = root / "notes.md"
            source.write_text("# Controls\n\nPID uses proportional, integral, and derivative terms.")
            ingestor = KnowledgeIngestor(store)
            self.assertGreater(ingestor.ingest(source), 0)
            unknown = root / "data.bin"
            unknown.write_bytes(b"binary")
            with self.assertRaises(KnowledgeIngestError):
                ingestor.ingest(unknown)

    def test_research_changes_use_bounded_non_disclosing_revision_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            knowledge = KnowledgeStore(root / "knowledge.sqlite3")
            memory = MemoryStore(root / "memory.sqlite3")
            now = datetime(2026, 8, 30, 12, tzinfo=UTC)
            monitored = {
                "research_monitor": True, "monitor_key": "robotics.papers",
            }
            with patch(
                "sparkle.storage.utc_now",
                return_value=(now - timedelta(hours=2)).isoformat(),
            ):
                previous_id = knowledge.ingest_text(
                    "Private paper title", "Private original finding",
                    source_uri="https://private.example/token",
                    metadata=monitored,
                )
            with patch(
                "sparkle.storage.utc_now",
                return_value=(now - timedelta(hours=1)).isoformat(),
            ):
                current_id = knowledge.ingest_text(
                    "Private paper title", "Private revised finding",
                    source_uri="https://private.example/token",
                    metadata=monitored,
                )

            unchanged = {
                "research_monitor": True, "monitor_key": "unchanged",
            }
            for age in (3, 2):
                with patch(
                    "sparkle.storage.utc_now",
                    return_value=(now - timedelta(hours=age)).isoformat(),
                ):
                    knowledge.ingest_text(
                        "Unchanged private", "Identical private content",
                        metadata=unchanged,
                    )
            invalid_cases = (
                {"research_monitor": False, "monitor_key": "disabled"},
                {"research_monitor": True, "monitor_key": "INVALID KEY"},
                {"research_monitor": True},
                {"research_monitor": "yes", "monitor_key": "invalid_type"},
                {"padding": "x" * 5_000},
            )
            for index, metadata in enumerate(invalid_cases):
                with self.assertRaises(ValueError):
                    with patch(
                        "sparkle.storage.utc_now",
                        return_value=(now - timedelta(minutes=index)).isoformat(),
                    ):
                        knowledge.ingest_text(
                            f"Invalid {index}", f"Private invalid {index}",
                            metadata=metadata,
                        )
            expired = {
                "research_monitor": True, "monitor_key": "expired",
            }
            for days, content in ((9, "Old one"), (8, "Old two")):
                with patch(
                    "sparkle.storage.utc_now",
                    return_value=(now - timedelta(days=days)).isoformat(),
                ):
                    knowledge.ingest_text("Expired", content, metadata=expired)

            alerts = [
                item for item in ProactiveEngine(memory, knowledge).inspect(now)
                if item["type"] == "research_change"
            ]
            self.assertEqual(len(alerts), 1)
            alert = alerts[0]
            self.assertEqual(alert["key"], "robotics.papers")
            self.assertEqual(alert["source_kind"], "knowledge")
            self.assertEqual(alert["source_id"], current_id)
            self.assertEqual(alert["source_knowledge_id"], current_id)
            self.assertEqual(alert["evidence"]["previous_source_id"], previous_id)
            self.assertEqual(alert["evidence"]["current_source_id"], current_id)
            self.assertEqual(alert["evidence"]["age_hours"], 1.0)
            self.assertEqual(alerts, [
                item for item in ProactiveEngine(memory, knowledge).inspect(now)
                if item["type"] == "research_change"
            ])
            serialized = json.dumps(alerts)
            digest = knowledge.monitor_observations()[0]["content_digest"]
            for private in ("Private", "private.example", "token", "finding", digest):
                self.assertNotIn(private, serialized)

    def test_knowledge_schema_migrates_content_digest_without_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "knowledge.sqlite3"
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.executescript("""
                    CREATE TABLE sources (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        source_uri TEXT,
                        media_type TEXT NOT NULL,
                        metadata TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE chunks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                        position INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        token_terms TEXT NOT NULL,
                        UNIQUE(source_id, position)
                    );
                """)
            store = KnowledgeStore(path)
            source_id = store.ingest_text(
                "Migrated", "Digest created after schema migration",
                metadata={"research_monitor": True, "monitor_key": "migration"},
            )
            observation = store.monitor_observations()[0]
            self.assertEqual(observation["source_id"], source_id)
            self.assertRegex(observation["content_digest"], r"^[0-9a-f]{64}$")

    def test_research_change_selection_is_deterministic_and_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            knowledge = KnowledgeStore(root / "knowledge.sqlite3")
            memory = MemoryStore(root / "memory.sqlite3")
            now = datetime(2026, 8, 30, 12, tzinfo=UTC)
            for monitor_key in ("gamma", "alpha", "beta"):
                metadata = {
                    "research_monitor": True, "monitor_key": monitor_key,
                }
                for revision in range(2):
                    with patch(
                        "sparkle.storage.utc_now",
                        return_value=(
                            now - timedelta(minutes=2 - revision)
                        ).isoformat(),
                    ):
                        knowledge.ingest_text(
                            monitor_key,
                            f"Private revision {revision} for {monitor_key}",
                            metadata=metadata,
                        )
            engine = ProactiveEngine(memory, knowledge)
            with patch.object(ProactiveEngine, "MAX_RESEARCH_CHANGES", 2):
                first = [
                    item for item in engine.inspect(now)
                    if item["type"] == "research_change"
                ]
                second = [
                    item for item in engine.inspect(now)
                    if item["type"] == "research_change"
                ]
            self.assertEqual(first, second)
            self.assertEqual([item["key"] for item in first], ["alpha", "beta"])


class TraceTests(unittest.TestCase):
    def test_sequential_ids_and_redaction(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TraceStore(Path(directory) / "traces.sqlite3")
            first, clock = store.start(input_source="text", agent="personal")
            store.finish(first, clock, status="success", agent="personal", model="m", provider="p", tools=[{"api_key": "secret"}], result_summary="ok")
            second, _ = store.start(input_source="text", agent="system")
            self.assertRegex(first, r"SPK-\d{4}-000001")
            self.assertRegex(second, r"SPK-\d{4}-000002")
            self.assertEqual(store.recent()[1]["tools"][0]["api_key"], "[REDACTED]")


class AutomationTests(unittest.TestCase):
    def test_due_and_condition_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AutomationStore(Path(directory) / "automation.sqlite3")
            past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
            store.create("Review", "once", {"type": "agent", "prompt": "Review"}, next_run_at=past)
            self.assertEqual(store.due()[0]["name"], "Review")
            automation_id = store.list()[0]["id"]
            self.assertTrue(store.set_enabled(automation_id, False))
            self.assertEqual(store.due(), [])
            self.assertTrue(store.set_enabled(automation_id, True))
            self.assertTrue(store.delete(automation_id))
            self.assertEqual(store.list(), [])
            with self.assertRaises(ValueError):
                store.create("Broken", "condition", {"type": "agent"})
            invalid_conditions = [
                {"type": "unknown", "alert": "overdue"},
                {"type": "memory_deadline", "alert": "weak_learning"},
                {"type": "proactive_alert", "alert": "invented"},
                {
                    "type": "proactive_alert", "alert": "weak_learning",
                    "category": "secrets",
                },
                {
                    "type": "proactive_alert", "alert": "weak_learning",
                    "extra": True,
                },
                {
                    "type": "proactive_alert", "alert": "weak_learning",
                    "key": "",
                },
                {
                    "type": "proactive_alert", "alert": "weak_learning",
                    "key": "x" * 201,
                },
                {
                    "type": "proactive_alert", "alert": "weak_learning",
                    "cooldown_minutes": 0,
                },
                {
                    "type": "proactive_alert", "alert": "weak_learning",
                    "cooldown_minutes": True,
                },
            ]
            for index, condition in enumerate(invalid_conditions):
                with self.subTest(condition=condition):
                    with self.assertRaises(ValueError):
                        store.create(
                            f"Invalid {index}",
                            "condition",
                            {"type": "agent", "prompt": "Review"},
                            condition=condition,
                        )

    def test_proactive_deadline_alerts(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = MemoryStore(Path(directory) / "memory.sqlite3")
            now = datetime(2026, 8, 28, tzinfo=UTC)
            memory.remember("tasks", "report", "Finish report", metadata={"deadline": (now + timedelta(hours=10)).isoformat()})
            alerts = ProactiveEngine(memory).inspect(now)
            self.assertEqual(alerts[0]["type"], "deadline_approaching")

    def test_proactive_rules_require_structured_bounded_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = MemoryStore(Path(directory) / "memory.sqlite3")
            now = datetime(2026, 8, 28, 12, tzinfo=UTC)
            memory.remember(
                "tasks", "late", "Sensitive task details",
                metadata={"deadline": (now - timedelta(hours=30)).isoformat()},
            )
            memory.remember(
                "skills", "python", "Private learning notes",
                metadata={
                    "evidence_count": 4, "mastery_level": 2, "target_level": 4,
                    "accuracy": 0.55, "target_accuracy": 0.8, "attempts": 12,
                },
            )
            memory.remember(
                "learning", "control", "Revision material",
                metadata={"next_review_at": (now - timedelta(hours=2)).isoformat()},
            )
            memory.remember(
                "projects", "robot", "Project details",
                metadata={"status": "blocked", "progress_percent": 42},
            )
            memory.remember(
                "mistakes", "sign_error", "Mistake details",
                metadata={"repeat_count": 3},
            )
            memory.remember(
                "goals", "unstructured", "This goal is overdue and weak",
                metadata={},
            )
            memory.remember(
                "exams", "invalid", "Invalid evidence",
                metadata={
                    "evidence_count": 2, "accuracy": "low",
                    "target_accuracy": 0.9, "attempts": 3,
                },
            )

            alerts = ProactiveEngine(memory).inspect(now)
            by_type = {alert["type"]: alert for alert in alerts}
            self.assertEqual(set(by_type), {
                "overdue", "weak_learning", "revision_due",
                "project_incomplete", "repeated_mistake",
            })
            self.assertEqual(
                by_type["weak_learning"]["evidence"]["mastery_gap"], 2,
            )
            self.assertEqual(by_type["project_incomplete"]["severity"], "high")
            self.assertEqual(by_type["overdue"]["protocol_version"], "SPARKLE-PROACTIVE/1")
            serialized = json.dumps(alerts)
            for absent in (
                "Sensitive task details", "Private learning notes",
                "Revision material", "Project details", "Mistake details",
                "This goal is overdue and weak",
            ):
                self.assertNotIn(absent, serialized)

    def test_schedule_conflicts_use_validated_safe_pair_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = MemoryStore(Path(directory) / "memory.sqlite3")
            now = datetime(2026, 8, 28, 12, tzinfo=UTC)
            first_id = memory.remember(
                "tasks", "robot_lab", "Private robot lab details",
                metadata={
                    "starts_at": (now + timedelta(hours=1)).isoformat(),
                    "ends_at": (now + timedelta(hours=3)).isoformat(),
                },
            )
            second_id = memory.remember(
                "exams", "controls_exam", "Private controls exam details",
                metadata={
                    "starts_at": (now + timedelta(hours=2)).isoformat(),
                    "ends_at": (now + timedelta(hours=4)).isoformat(),
                },
            )
            memory.remember(
                "projects", "later", "Non-overlapping project",
                metadata={
                    "starts_at": (now + timedelta(hours=6)).isoformat(),
                    "ends_at": (now + timedelta(hours=7)).isoformat(),
                },
            )
            invalid = [
                {"starts_at": (now + timedelta(hours=1)).isoformat()},
                {
                    "starts_at": (now + timedelta(hours=3)).isoformat(),
                    "ends_at": (now + timedelta(hours=2)).isoformat(),
                },
                {
                    "starts_at": now.isoformat(),
                    "ends_at": (now + timedelta(days=8)).isoformat(),
                },
                {"starts_at": "invalid", "ends_at": "invalid"},
                {
                    "starts_at": (now - timedelta(hours=3)).isoformat(),
                    "ends_at": (now - timedelta(hours=2)).isoformat(),
                },
            ]
            for index, metadata in enumerate(invalid):
                memory.remember(
                    "tasks", f"invalid_{index}", f"Private invalid {index}",
                    metadata=metadata,
                )

            engine = ProactiveEngine(memory)
            conflicts = [
                item for item in engine.inspect(now)
                if item["type"] == "schedule_conflict"
            ]
            self.assertEqual(len(conflicts), 1)
            conflict = conflicts[0]
            self.assertEqual(conflict["source_memory_id"], first_id)
            self.assertEqual(conflict["category"], "tasks")
            self.assertEqual(conflict["key"], "robot_lab")
            self.assertEqual(conflict["severity"], "high")
            self.assertEqual(conflict["evidence"]["overlap_minutes"], 60.0)
            self.assertEqual(
                conflict["evidence"]["conflicting_memory_id"], second_id,
            )
            self.assertEqual(
                conflict["evidence"]["conflicting_category"], "exams",
            )
            self.assertEqual(
                conflict["evidence"]["conflicting_key"], "controls_exam",
            )
            self.assertEqual(conflicts, [
                item for item in engine.inspect(now)
                if item["type"] == "schedule_conflict"
            ])
            serialized = json.dumps(conflicts)
            for private_value in (
                "Private robot lab details", "Private controls exam details",
                "Non-overlapping project", "Private invalid",
            ):
                self.assertNotIn(private_value, serialized)

    def test_schedule_conflict_boundaries_and_pair_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = MemoryStore(Path(directory) / "memory.sqlite3")
            now = datetime(2026, 8, 28, 12, tzinfo=UTC)
            start = now + timedelta(days=30, hours=-2)
            memory.remember("tasks", "first", "Private", metadata={
                "starts_at": start.isoformat(),
                "ends_at": (start + timedelta(hours=2)).isoformat(),
            })
            memory.remember("tasks", "second", "Private", metadata={
                "starts_at": (start + timedelta(hours=1, minutes=59)).isoformat(),
                "ends_at": (start + timedelta(hours=3)).isoformat(),
            })
            memory.remember("tasks", "third", "Private", metadata={
                "starts_at": (start + timedelta(hours=1)).isoformat(),
                "ends_at": (start + timedelta(hours=4)).isoformat(),
            })
            memory.remember("tasks", "touching", "Private", metadata={
                "starts_at": (start + timedelta(hours=4)).isoformat(),
                "ends_at": (start + timedelta(hours=5)).isoformat(),
            })
            with patch.object(ProactiveEngine, "MAX_SCHEDULE_CONFLICTS", 2):
                conflicts = [
                    item for item in ProactiveEngine(memory).inspect(now)
                    if item["type"] == "schedule_conflict"
                ]
            self.assertEqual(len(conflicts), 2)
            self.assertTrue(any(
                item["evidence"]["overlap_minutes"] == 1.0
                for item in conflicts
            ))

    def test_proactive_alerts_are_deterministic_and_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = MemoryStore(Path(directory) / "memory.sqlite3")
            now = datetime(2026, 8, 28, 12, tzinfo=UTC)
            memory.remember(
                "tasks", "urgent", "Private task",
                metadata={"deadline": (now - timedelta(hours=30)).isoformat()},
            )
            for index in range(100):
                memory.remember(
                    "mistakes", f"mistake-{index:03d}", "Private mistake",
                    metadata={"repeat_count": 3},
                )
                memory.remember(
                    "projects", f"project-{index:03d}", "Private project",
                    metadata={"status": "active", "progress_percent": 50},
                )
            engine = ProactiveEngine(memory)
            first = engine.inspect(now)
            self.assertEqual(len(first), engine.MAX_ALERTS)
            self.assertEqual(first, engine.inspect(now))
            severity = {"urgent": 0, "high": 1, "medium": 2}
            self.assertEqual(
                [severity[item["severity"]] for item in first],
                sorted(severity[item["severity"]] for item in first),
            )
