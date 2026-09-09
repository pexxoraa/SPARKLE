"""Literal, bounded memory lookup; no semantic retrieval claim."""
import tempfile
import unittest
from pathlib import Path

from sparkle.storage import MemoryStore, KnowledgeStore
from sparkle.context import ContextBuilder


class MemoryQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.memory = MemoryStore(self.root/'memory.sqlite3')
        self.memory.remember('goals', 'cycling', 'Cycle twice weekly')

    def test_unicode_query_does_not_return_unrelated_recent_records(self):
        self.assertEqual(self.memory.search('日本語'), [])
        self.memory.remember('learning', '日本語', '日本語を勉強する')
        self.assertEqual([r['key'] for r in self.memory.search('日本語')], ['日本語'])
        self.assertEqual([r['key'] for r in self.memory.search('語')], ['日本語'])

    def test_nonempty_unsearchable_query_is_empty_but_blank_keeps_recent(self):
        for query in ('!!!', '%', '_', 'a'):
            self.assertEqual(self.memory.search(query), [])
        self.assertEqual(len(self.memory.search('   ')), 1)

    def test_underscore_is_literal_not_sql_wildcard(self):
        self.memory.remember('goals', 'ab_cd', 'literal')
        self.memory.remember('goals', 'abXcd', 'distractor')
        self.assertEqual([r['key'] for r in self.memory.search('ab_cd')], ['ab_cd'])

    def test_large_query_is_bounded_and_category_archive_limits_survive(self):
        self.assertEqual(self.memory.search(' '.join('word'+str(i) for i in range(5000))), [])
        found = self.memory.remember('learning', 'cycles', 'Cycle practice')
        self.assertEqual(len(self.memory.search('cycle '*5000, limit=1)), 1)
        self.assertEqual([r['id'] for r in self.memory.search('cycle', category='learning')], [found])
        self.memory.archive(found)
        self.assertEqual(self.memory.search('cycle', category='learning'), [])

    def test_context_does_not_include_unrelated_memory_for_unicode_query(self):
        knowledge = KnowledgeStore(self.root/'knowledge.sqlite3')
        context = ContextBuilder(self.memory, knowledge)
        rendered = context.build('日本語').render()
        self.assertNotIn('Cycle twice weekly', rendered)
