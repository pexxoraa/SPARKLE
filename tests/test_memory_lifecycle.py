import sqlite3
import tempfile
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from sparkle.storage import MemoryStore
from sparkle.memory_review import MemoryReview

class MemoryLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = MemoryStore(Path(self.temp.name)/'memory.db')
        self.mid = self.store.remember('goals','practice','Practice daily')

    def test_existing_database_migrates_once_under_concurrent_initialization(self):
        path = Path(self.temp.name)/'legacy.db'
        with closing(sqlite3.connect(path)) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript("""CREATE TABLE memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,category TEXT NOT NULL,memory_key TEXT NOT NULL,
                value TEXT NOT NULL,importance REAL NOT NULL DEFAULT 0.5,metadata TEXT NOT NULL DEFAULT '{}',
                archived INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
                UNIQUE(category,memory_key));
                INSERT INTO memories(category,memory_key,value,created_at,updated_at)
                VALUES('goals','legacy','Keep this fact','2026-01-01','2026-01-01');""")
        with ThreadPoolExecutor(2) as pool: stores=list(pool.map(lambda _:MemoryStore(path),range(2)))
        for store in stores:
            self.assertEqual(store.recent()[0]['value'],'Keep this fact')
            self.assertIsNone(store.recent()[0]['expires_at'])
            self.assertEqual(len(store.history()),1)
            self.assertEqual(store.history()[0]['action'],'migration_baseline')

    def test_expiry_boundary_excludes_search_recent_and_active_export(self):
        with patch('sparkle.storage.time.time',return_value=100): self.store.set_retention(self.mid,10)
        with patch('sparkle.storage.time.time',return_value=109.999): self.assertEqual(len(self.store.search('practice')),1)
        with patch('sparkle.storage.time.time',return_value=110):
            self.assertEqual(self.store.search('practice'),[])
            self.assertEqual(self.store.recent(),[])
            self.assertEqual(self.store.export(include_archived=False),[])
            self.assertFalse(self.store.restore(self.mid))
        self.assertEqual(len(self.store.export()),1)
        self.store.set_retention(self.mid,None)
        self.assertEqual(len(self.store.recent()),1)

    def test_archive_restore_revoke_cannot_be_bypassed_by_upsert(self):
        self.store.archive(self.mid); self.assertEqual(self.store.recent(),[])
        self.assertTrue(self.store.restore(self.mid))
        self.store.revoke(self.mid); self.assertEqual(self.store.recent(),[])
        self.assertFalse(self.store.restore(self.mid))
        self.store.remember('goals','practice','Updated explicit fact')
        self.assertEqual(self.store.recent(),[])
        self.assertTrue(self.store.export()[0]['revoked'])

    def test_updates_preserve_retention_and_history_survives_delete(self):
        self.store.set_retention(self.mid,60)
        expiry=self.store.export()[0]['expires_at']
        self.store.remember('goals','practice','Practice weekly')
        self.assertEqual(self.store.export()[0]['expires_at'],expiry)
        self.assertEqual(self.store.history()[0]['action'],'superseded')
        self.store.delete(self.mid)
        self.assertEqual(self.store.export(),[])
        events=self.store.history(self.mid)
        self.assertEqual(events[0]['action'],'deleted')
        self.assertEqual(events[-1]['snapshot']['value'],'Practice daily')
        self.assertEqual(MemoryStore(self.store.path).history(self.mid),events)

    def test_history_mutation_and_invalid_policy_fail_closed(self):
        for sql in ('DELETE FROM memory_versions','UPDATE memory_versions SET action="forged"'):
            with self.assertRaises(sqlite3.IntegrityError),self.store.connect() as db: db.execute(sql)
        for seconds in (True,0,-1,1.5,31536001):
            with self.assertRaises(ValueError): self.store.set_retention(self.mid,seconds)
        self.assertEqual(len(self.store.history()),1)

    def test_failed_write_rolls_back_snapshot_and_state(self):
        with self.store.connect() as db:
            db.execute("CREATE TRIGGER deny_update AFTER UPDATE ON memories BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.IntegrityError): self.store.remember('goals','practice','Changed')
        self.assertEqual(self.store.recent()[0]['value'],'Practice daily')
        self.assertEqual(len(self.store.history()),1)

    def test_pending_approval_cannot_revive_revoked_or_expired_target(self):
        review=MemoryReview(self.store)
        for state in ('revoked','expired'):
            with self.subTest(state=state):
                if state=='revoked': self.store.revoke(self.mid)
                else:
                    self.store.delete(self.mid); self.mid=self.store.remember('goals','practice','Practice daily')
                    with patch('sparkle.storage.time.time',return_value=1): self.store.set_retention(self.mid,1)
                p=review.propose({'category':'goals','key':'practice','value':'New goal'})
                with self.assertRaises(ValueError): review.review(p['proposal_id'],p['digest'],'approve',reviewer='cli')
                self.assertEqual(self.store.recent(),[])
