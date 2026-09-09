import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from sparkle.memory_review import MemoryReview
from sparkle.storage import MemoryStore
from sparkle.tooling import MemoryProposalTool


class MemoryReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = MemoryStore(Path(self.temp.name) / 'memory.db')
        self.review = MemoryReview(self.store)
        self.args = dict(category='goals', key='practice', value='Practice daily')

    def propose(self):
        return MemoryProposalTool(self.review).run(self.args)

    def resolve(self, proposal, decision='approve'):
        return self.review.review(proposal['proposal_id'], proposal['digest'], decision, reviewer='cli')

    def test_pending_not_retrieved_and_exact_operator_approval_persists(self):
        p = self.propose()
        self.assertFalse(p['stored'])
        self.assertEqual(self.store.export(), [])
        self.assertEqual(self.store.search('practice'), [])
        result = self.resolve(p)
        self.assertEqual(result['status'], 'approved')
        row = self.store.search('practice')[0]
        self.assertEqual(row['value'], self.args['value'])
        self.assertEqual(row['metadata']['proposal_digest'], p['digest'])

    def test_rejection_and_replay_do_not_write(self):
        p = self.propose()
        self.assertEqual(self.resolve(p, 'reject')['status'], 'rejected')
        with self.assertRaises(ValueError): self.resolve(p)
        self.assertEqual(self.store.export(), [])

    def test_identity_and_payload_tamper_rejected(self):
        p = self.propose()
        with self.assertRaises(ValueError): self.resolve(p | {'digest': '0'*64})
        with self.store.connect() as db:
            payload = json.loads(db.execute('SELECT payload FROM memory_proposals').fetchone()[0])
            payload['value'] = 'Different claim'
            db.execute('UPDATE memory_proposals SET payload=?', (json.dumps(payload),))
        with self.assertRaises(ValueError): self.resolve(p)
        self.assertEqual(self.store.export(), [])

    def test_expired_approval_fails_but_rejection_allowed(self):
        with patch('sparkle.memory_review.time.time', return_value=1): p = self.propose()
        with self.assertRaises(ValueError): self.resolve(p)
        self.resolve(p, 'reject')
        self.assertEqual(self.store.export(), [])

    def test_changed_existing_memory_rejects_stale_overwrite(self):
        for change in ('write', 'archive', 'delete'):
            with self.subTest(change=change):
                mid = self.store.remember('goals', 'practice', 'Original')
                p = self.propose()
                if change == 'write': self.store.remember('goals','practice','New explicit fact')
                else: getattr(self.store, change)(mid)
                before = self.store.export()
                with self.assertRaises(ValueError): self.resolve(p)
                self.assertEqual(self.store.export(), before)

    def test_simultaneous_reviews_commit_exactly_once(self):
        p = self.propose()
        def attempt(_):
            try: return self.resolve(p)['status']
            except ValueError: return 'denied'
        with ThreadPoolExecutor(2) as pool: results = list(pool.map(attempt, range(2)))
        self.assertCountEqual(results, ['approved','denied'])
        self.assertEqual(len(self.store.export()), 1)

    def test_atomic_rollback_if_review_completion_fails(self):
        p = self.propose()
        with self.store.connect() as db:
            db.execute("CREATE TRIGGER fail_review BEFORE UPDATE ON memory_proposals BEGIN SELECT RAISE(ABORT,'test'); END")
        with self.assertRaises(Exception): self.resolve(p)
        self.assertEqual(self.store.export(), [])
        self.assertEqual(self.review.list()[0]['status'], 'pending')

    def test_invalid_values_and_model_approval_fields_rejected(self):
        for fields in ({'approved':True},{'importance':True},{'importance':float('nan')},
                       {'value':None},{'key':' '},{'category':'secrets'},{'value':'x'*8001}):
            with self.subTest(fields=list(fields)):
                with self.assertRaises(ValueError): MemoryProposalTool(self.review).run(self.args | fields)
        self.assertEqual(self.review.list(), [])
        p = self.propose()
        with self.assertRaises(ValueError): self.review.review(p['proposal_id'],p['digest'],'approve',reviewer='model')
