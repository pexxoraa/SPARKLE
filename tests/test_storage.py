from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
            with self.assertRaises(ValueError):
                store.create("Broken", "condition", {"type": "agent"})

    def test_proactive_deadline_alerts(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = MemoryStore(Path(directory) / "memory.sqlite3")
            now = datetime(2026, 8, 28, tzinfo=UTC)
            memory.remember("tasks", "report", "Finish report", metadata={"deadline": (now + timedelta(hours=10)).isoformat()})
            alerts = ProactiveEngine(memory).inspect(now)
            self.assertEqual(alerts[0]["type"], "deadline_approaching")
