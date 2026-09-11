import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sparkle.storage import KnowledgeStore
from sparkle.retrieval import SemanticRetriever, HybridRetriever, HashingTestEmbeddings
from sparkle.tooling import KnowledgeSearchTool, KnowledgeVerifyTool


class KnowledgeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=KnowledgeStore(Path(self.temp.name)/'knowledge.db')
        self.old=self.store.ingest_text('fixture old','fixture old evidence')
        self.new=self.store.ingest_text('fixture new','fixture new evidence')
        self.policy=self.store.lifecycle

    def change(self,action,revision=0,**kwargs):
        return self.policy.transition(self.old,action,revision,operator='cli',**kwargs)

    def test_archive_restore_excludes_all_rankers_and_citations(self):
        row=KnowledgeSearchTool(self.store).run({'query':'old'})[0]
        cite={'source_id':self.old,'chunk_id':row['chunk_id'],'digest':row['citation_digest'],'quote':'old evidence'}
        self.change('archive')
        semantic=SemanticRetriever(self.store,HashingTestEmbeddings())
        for retriever in (self.store,semantic,HybridRetriever(self.store,semantic)):
            self.assertTrue(all(r['source_id']!=self.old for r in retriever.search('fixture')))
        self.assertEqual(KnowledgeVerifyTool(self.store).run({'citations':[cite]})['checks'][0]['reason'],'source_ineligible')
        self.change('restore',1)
        self.assertEqual(self.store.search('old')[0]['source_id'],self.old)

    def test_revision_conflicts_and_terminal_states_fail_closed(self):
        self.change('supersede',replacement_id=self.new)
        for action in ('restore','retention','archive'):
            with self.assertRaises(ValueError):self.change(action,1)
        with self.assertRaises(ValueError):self.change('revoke')
        with self.assertRaises(ValueError):self.policy.transition(self.new,'supersede',0,operator='cli',replacement_id=self.old)
        self.assertEqual(len(self.policy.history(self.old)),1)

    def test_expiry_and_explicit_extension(self):
        with patch('sparkle.knowledge_lifecycle.time.time',return_value=1):self.change('retention',retention_seconds=1)
        self.assertEqual(self.store.search('old'),[])
        self.change('retention',1,retention_seconds=None)
        self.assertTrue(self.store.search('old'))
        self.change('revoke',2)
        with self.assertRaises(ValueError):self.change('retention',3)

    def test_embedding_callback_cannot_return_newly_archived_source(self):
        policy=self.policy;source=self.old
        class Embeddings:
            identity='deterministic-fixture';dimensions=2
            def embed(self,texts):
                policy.transition(source,'archive',0,operator='cli')
                return [[1.,0.] for _ in texts]
        results=HybridRetriever(self.store,SemanticRetriever(self.store,Embeddings())).search('fixture')
        self.assertEqual([r['source_id'] for r in results],[self.new])

    def test_audit_survives_deletion_and_is_append_only(self):
        self.change('archive');self.store.delete_source(self.old)
        self.assertEqual([e['action'] for e in self.policy.history(self.old)],['deleted','archive'])
        with self.assertRaises(Exception):
            with self.store.connect() as db:db.execute('DELETE FROM knowledge_source_events')
        KnowledgeStore(self.store.path)
        self.assertEqual(len(self.policy.history(self.old)),2)

    def test_invalid_changes_leave_no_policy_or_event(self):
        for kwargs in ({'replacement_id':self.old},{'replacement_id':999}):
            with self.assertRaises(ValueError):self.change('supersede',**kwargs)
        with self.assertRaises(ValueError):self.change('retention',retention_seconds=True)
        with self.assertRaises(ValueError):self.policy.transition(self.old,'archive',0,operator='model')
        self.assertEqual(self.policy.inspect(self.old)['revision'],0)
        self.assertEqual(self.policy.history(self.old),[])
