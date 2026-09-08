from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from sparkle.storage import KnowledgeStore


class KnowledgeRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = KnowledgeStore(Path(self.temp.name) / 'knowledge.sqlite3')
        self.store.initialize()

    def test_title_rank_unicode_and_stable_identity(self):
        title = self.store.ingest_text('Café résumé', 'The approved plan costs twelve units.')
        self.store.ingest_text('Other document', 'A cafe is nearby.')
        self.store.ingest_text('背景', '中文资料与设计，安全测试成功。')
        results = self.store.search('CAFE resume')
        self.assertEqual(results[0]['source_id'], title)
        self.assertGreater(results[0]['score'], results[1]['score'])
        self.assertEqual(results, self.store.search('CAFE resume'))
        self.assertEqual(self.store.search('中文资料与设计')[0]['title'], '背景')

    def test_literal_queries_limits_and_no_operator_injection(self):
        self.store.ingest_text('Alpha', 'An unrelated needle.')
        self.store.ingest_text('Beta', 'Different information.')
        self.assertEqual(len(self.store.search('"alpha" NOT absent*')), 1)
        self.assertEqual(self.store.search('" * () :'), [])
        self.assertEqual(self.store.search("'; DROP TABLE sources; --"), [])
        self.assertEqual(self.store.stats()['sources'], 2)
        self.assertEqual(self.store.search('x' * 16385 + ' alpha'), [])
        with self.assertRaises(ValueError):
            self.store.search(None)
        for index in range(60):
            self.store.ingest_text('Shared', f'Record {index}')
        self.assertEqual(len(self.store.search('shared', limit=500)), 50)

    def test_legacy_backfill_is_idempotent(self):
        source = self.store.ingest_text('Legacy title', 'Existing stored content.')
        with self.store.connect() as conn:
            for name in ('insert', 'delete', 'update'):
                conn.execute(f'DROP TRIGGER knowledge_chunk_{name}')
            conn.execute('DROP TRIGGER knowledge_title_update')
            conn.execute('DROP TABLE knowledge_search')
        self.store.initialize()
        self.store.initialize()
        results = self.store.search('legacy')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['source_id'], source)
        self.assertEqual(results[0]['content'], 'Existing stored content.')

    def test_delete_update_and_rollback_preserve_index_consistency(self):
        source = self.store.ingest_text('Oldtitle', 'Oldcontent')
        with self.store.connect() as conn:
            conn.execute('UPDATE sources SET title=? WHERE id=?', ('Newtitle', source))
            conn.execute('UPDATE chunks SET content=? WHERE source_id=?', ('Newcontent', source))
        self.assertEqual(self.store.search('oldtitle oldcontent'), [])
        self.assertEqual(len(self.store.search('newtitle newcontent')), 1)
        with self.assertRaises(RuntimeError):
            with self.store.connect() as conn:
                conn.execute('DELETE FROM sources WHERE id=?', (source,))
                raise RuntimeError('Rollback canary')
        self.assertEqual(len(self.store.search('newtitle')), 1)
        self.assertTrue(self.store.delete_source(source))
        self.assertEqual(self.store.search('newtitle newcontent'), [])
        with self.store.connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM knowledge_search').fetchone()[0], 0)

    def test_long_paragraphs_are_bounded_and_invalid_size_fails(self):
        content = 'bounded ' * 1000
        source = self.store.ingest_text('Long', content, chunk_chars=120)
        with self.store.connect() as conn:
            chunks = conn.execute('SELECT content FROM chunks WHERE source_id=? ORDER BY position', (source,)).fetchall()
        self.assertTrue(all(0 < len(row['content']) <= 120 for row in chunks))
        self.assertEqual(''.join(row['content'] for row in chunks), content.strip())
        for invalid in (0, -1, True, 1.5, 100001):
            with self.assertRaises(ValueError):
                self.store.ingest_text('Invalid', 'content', chunk_chars=invalid)

    def test_failed_migration_rolls_back_index_creation(self):
        # A genuine SQLite failure must abort, never silently substitute an empty index.
        with self.store.connect() as conn:
            for name in ('insert', 'delete', 'update'):
                conn.execute(f'DROP TRIGGER knowledge_chunk_{name}')
            conn.execute('DROP TRIGGER knowledge_title_update')
            conn.execute('DROP TABLE knowledge_search')
            conn.execute('CREATE TRIGGER knowledge_chunk_insert AFTER INSERT ON chunks BEGIN SELECT 1; END')
        with self.assertRaises(sqlite3.OperationalError):
            self.store.initialize()
        with self.store.connect() as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='knowledge_search'").fetchone())
