import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sparkle.memory_review import MemoryReview
from sparkle.storage import MemoryStore


class MemoryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = MemoryStore(Path(self.temp.name)/'memory.db')
        self.review = MemoryReview(self.store)
        self.claim = {'category':'preferences','key':'editor','value':'vim'}
        self.proposal = self.review.propose(self.claim)

    def attest(self, value='vim', source='user:settings'):
        return self.review.evidence.attest('preferences','editor',value,source,operator='cli')

    def validate(self):
        return self.review.validate(self.proposal['proposal_id'], self.proposal['digest'])

    def approve(self, strict=True):
        return self.review.review(self.proposal['proposal_id'],self.proposal['digest'],
                                  'approve',reviewer='cli',require_verified=strict)

    def test_review_listing_exposes_current_evidence_without_writing_audit(self):
        self.attest()
        with self.store.connect() as db:
            before = db.execute('SELECT COUNT(*) FROM memory_evidence_events').fetchone()[0]
        item = self.review.list()[0]
        self.assertEqual(item['verification']['status'], 'VERIFIED')
        self.assertEqual(item['evidence'][0]['source_ref'], 'user:settings')
        self.assertFalse(item['expired'])
        self.assertFalse(item['conflict'])
        self.assertFalse(item['target_blocked'])
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM memory_evidence_events').fetchone()[0], before)
        self.store.remember('preferences', 'editor', 'emacs')
        self.assertTrue(self.review.list()[0]['conflict'])

    def test_review_listing_rejects_tampered_payload(self):
        with self.store.connect() as db:
            db.execute("UPDATE memory_proposals SET payload=replace(payload, 'vim', 'emacs')")
        with self.assertRaises(ValueError):
            self.review.list()

    def test_unknown_stays_inconclusive_and_strict_approval_denied(self):
        self.assertEqual(self.validate()['status'],'INCONCLUSIVE')
        with self.assertRaises(ValueError): self.approve()
        self.assertEqual(self.store.export(), [])
        result = self.approve(False)
        self.assertEqual(result['verification']['status'],'INCONCLUSIVE')
        self.assertFalse(self.store.export()[0]['metadata']['require_verified'])

    def test_independent_exact_fact_verified_but_does_not_auto_approve(self):
        fact = self.attest()
        result = self.validate()
        self.assertEqual(result['status'],'VERIFIED')
        self.assertEqual(result['fact_ids'],[fact['fact_id']])
        self.assertEqual(self.store.export(), [])
        self.approve()
        self.assertEqual(self.store.export()[0]['metadata']['factual_verification']['status'],'VERIFIED')

    def test_contradiction_blocks_operator_approval(self):
        self.attest('emacs')
        self.assertEqual(self.validate()['status'],'REJECTED')
        for strict in (True,False):
            with self.assertRaises(ValueError): self.approve(strict)
        self.assertEqual(self.store.export(), [])

    def test_cross_source_agreement_and_conflict(self):
        self.attest(); self.attest(source='user:profile')
        self.assertEqual(self.validate()['status'],'VERIFIED')
        self.attest('emacs','user:conflict')
        result = self.validate()
        self.assertEqual(result['status'],'INCONCLUSIVE')
        self.assertEqual(result['reason'],'conflicting_attestations')
        with self.assertRaises(ValueError): self.approve()

    def test_expiry_revocation_and_changed_fact_invalidate_old_verification(self):
        with patch('sparkle.memory_evidence.time.time',return_value=1): self.attest()
        self.assertEqual(self.validate()['status'],'INCONCLUSIVE')
        fact = self.attest(); self.assertEqual(self.validate()['status'],'VERIFIED')
        self.review.evidence.revoke(fact['fact_id'],operator='cli')
        with self.assertRaises(ValueError): self.approve()
        self.attest(); previous = self.validate()['evidence_digest']
        self.attest('emacs')
        self.assertNotEqual(previous,self.validate()['evidence_digest'])
        with self.assertRaises(ValueError): self.approve()

    def test_strict_retrieval_rechecks_revocation_conflict_and_expiry(self):
        fact = self.attest(); self.approve()
        self.assertEqual(len(self.store.search('vim')),1)
        self.review.evidence.revoke(fact['fact_id'],operator='cli')
        self.assertEqual(self.store.search('vim'),[])
        self.assertEqual(self.store.recent(),[])
        self.assertEqual(self.store.export(include_archived=False),[])
        self.assertEqual(len(self.store.export()),1)
        self.attest(); self.assertEqual(len(self.store.recent()),1)
        other = self.attest('emacs','other')
        self.assertEqual(self.store.recent(),[])
        self.review.evidence.revoke(other['fact_id'],operator='cli')
        with self.store.connect() as db: db.execute('UPDATE memory_facts SET expires_at=1')
        self.assertEqual(self.store.recent(),[])

    def test_model_cannot_supply_attestation_or_verification_status(self):
        with self.assertRaises(ValueError): self.review.propose(self.claim | {'verified':True})
        with self.assertRaises(ValueError): self.review.evidence.attest('preferences','editor','vim','source',operator='model')
        with self.assertRaises(ValueError): self.review.evidence.attest('preferences','editor','vim','source',ttl_seconds=True,operator='cli')
        self.assertEqual(self.validate()['status'],'INCONCLUSIVE')

    def test_audit_is_append_only_content_free_and_survives_reopening(self):
        self.attest(); self.validate(); self.approve()
        events = self.review.evidence.history()
        self.assertEqual(len(events),3)
        self.assertNotIn('vim',json.dumps(events))
        self.assertNotIn('user:settings',json.dumps(events))
        for sql in ('DELETE FROM memory_evidence_events','UPDATE memory_evidence_events SET kind="forged"'):
            with self.assertRaises(sqlite3.IntegrityError), self.store.connect() as db: db.execute(sql)
        reopened = MemoryReview(MemoryStore(self.store.path))
        self.assertEqual(reopened.evidence.history(), events)

    def test_evidence_bound_is_inconclusive_and_wrong_digest_fails(self):
        for n in range(65): self.attest(source=f'user:{n}')
        self.assertEqual(self.validate()['reason'],'evidence_limit')
        with self.assertRaises(ValueError): self.review.validate(self.proposal['proposal_id'],'0'*64)
        self.assertEqual(self.store.export(), [])
