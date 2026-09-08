from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from sparkle.automation import AutomationStore


class AutomationMigrationTests(unittest.TestCase):
    def test_initializer_waits_before_reading_stale_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'automations.sqlite3'
            store=AutomationStore(path)
            with store.connect() as connection:
                connection.execute('ALTER TABLE automations DROP COLUMN claim_token')
                connection.execute('ALTER TABLE automations DROP COLUMN claim_expires_at')
            started=threading.Event()
            class ObservedStore(AutomationStore):
                def connect(self):
                    connection=super().connect()
                    def observe(sql):
                        if sql.startswith('BEGIN IMMEDIATE') or sql.startswith('ALTER TABLE automations ADD'):
                            started.set()
                    connection.set_trace_callback(observe)
                    return connection
            with store.connect() as writer:
                writer.execute('BEGIN IMMEDIATE')
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending=pool.submit(ObservedStore,path)
                    try:
                        self.assertTrue(started.wait(3),'Observer did not attempt migration')
                        writer.execute('ALTER TABLE automations ADD COLUMN claim_token TEXT')
                        writer.execute('ALTER TABLE automations ADD COLUMN claim_expires_at TEXT')
                    finally:
                        writer.commit()
                    initialized=pending.result(timeout=5)
            with initialized.connect() as connection:
                names=[r['name'] for r in connection.execute('PRAGMA table_info(automations)')]
            self.assertEqual(names.count('claim_token'),1)
            self.assertEqual(names.count('claim_expires_at'),1)

    def test_concurrent_initializers_preserve_existing_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'automations.sqlite3'
            store=AutomationStore(path)
            ident=store.create('fixture','once',{'type':'agent','prompt':'Synthetic fixture','agent':'personal'},
                               next_run_at='2099-01-01T00:00:00Z')
            barrier=threading.Barrier(6)
            def initialize():
                barrier.wait(timeout=5)
                return AutomationStore(path).list()
            with ThreadPoolExecutor(max_workers=6) as pool:
                results=list(pool.map(lambda _:initialize(),range(6)))
            self.assertTrue(all(any(r['id']==ident for r in rows) for rows in results))
