"""Operator-reviewed agent memory proposals; pending content is never retrieval input."""
from __future__ import annotations

import hashlib
import json
import math
import time
import uuid

from sparkle.storage import MemoryStore, utc_now
from sparkle.memory_evidence import MemoryEvidence


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class MemoryReview:
    def __init__(self, store: MemoryStore):
        self.store = store
        self.evidence = MemoryEvidence(store)
        with store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS memory_proposals (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL, reviewed_at TEXT,
                reviewer TEXT, memory_id INTEGER)''')

    @staticmethod
    def _current(db, category, key):
        row = db.execute('SELECT * FROM memories WHERE category=? AND memory_key=?',
                         (category, key)).fetchone()
        return _digest(dict(row) if row else None)

    def propose(self, arguments):
        if (not isinstance(arguments, dict) or set(arguments) - {'category', 'key', 'value', 'importance'}
                or not {'category', 'key', 'value'} <= set(arguments)):
            raise ValueError('Invalid memory proposal fields')
        category, key, value = (arguments[k] for k in ('category', 'key', 'value'))
        importance = arguments.get('importance', 0.5)
        if (not isinstance(category, str) or category not in MemoryStore.VALID_CATEGORIES - {'conversations'}
                or not isinstance(key, str) or not 1 <= len(key.strip()) <= 256
                or not isinstance(value, str) or not 1 <= len(value.strip()) <= 8000
                or type(importance) not in (int, float) or not math.isfinite(importance)
                or not 0 <= importance <= 1):
            raise ValueError('Invalid memory proposal values')
        proposal_id = uuid.uuid4().hex
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT count(*) FROM memory_proposals WHERE status='pending'").fetchone()[0] >= 1000:
                raise ValueError('Memory proposal capacity reached; review pending proposals')
            payload = dict(id=proposal_id, category=category, key=key.strip(), value=value.strip(),
                           importance=importance, expires_at=time.time() + 86400,
                           base_digest=self._current(db, category, key.strip()))
            digest = _digest(payload)
            db.execute('INSERT INTO memory_proposals(id,payload,digest,status,created_at) VALUES(?,?,?,?,?)',
                       (proposal_id, json.dumps(payload), digest, 'pending', utc_now()))
        return {'stored': False, 'proposal_id': proposal_id, 'digest': digest,
                'status': 'pending', 'requires_operator_review': True}

    def list(self, *, limit=50, status="pending"):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Proposal limit must be an integer from 1 to 100')
        if status not in ('pending', 'approved', 'rejected', 'all'):
            raise ValueError('Invalid memory proposal status filter')
        with self.store.connect() as db:
            where, parameters = ('', (limit,)) if status == 'all' else ('WHERE status=?', (status, limit))
            rows = db.execute(f'SELECT * FROM memory_proposals {where} ORDER BY created_at,id LIMIT ?', parameters).fetchall()
        return [dict(row) | {'payload': json.loads(row['payload'])} for row in rows]

    def validate(self, proposal_id, digest):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM memory_proposals WHERE id=?', (proposal_id,)).fetchone()
            if row is None or row['digest'] != digest:
                raise ValueError('Memory proposal identity mismatch')
            payload = json.loads(row['payload'])
            if _digest(payload) != digest or payload['id'] != proposal_id:
                raise ValueError('Memory proposal identity mismatch')
            result = self.evidence.evaluate(db, payload)
            result['proposal_digest'] = digest
            self.evidence.event(db, 'proposal_validated', proposal_id, result)
        return result

    def review(self, proposal_id, digest, decision, *, reviewer, require_verified=False):
        # This method is an operator boundary, deliberately absent from model tools.
        if (not isinstance(proposal_id, str) or not isinstance(digest, str)
                or decision not in ('approve', 'reject') or reviewer not in ('cli', 'authenticated_api', 'local_api')):
            raise ValueError('Invalid memory review request')
        if type(require_verified) is not bool:
            raise ValueError('Verification policy must be a boolean')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM memory_proposals WHERE id=?', (proposal_id,)).fetchone()
            if row is None or row['status'] != 'pending':
                raise ValueError('Memory proposal is missing or already reviewed')
            payload = json.loads(row['payload'])
            if digest != row['digest'] or _digest(payload) != digest or payload['id'] != proposal_id:
                raise ValueError('Memory proposal identity mismatch')
            verification = self.evidence.evaluate(db, payload)
            memory_id = None
            status = 'rejected'
            if decision == 'approve':
                if verification['status'] == 'REJECTED' or (require_verified and verification['status'] != 'VERIFIED'):
                    raise ValueError('Memory proposal does not satisfy factual verification policy')
                if time.time() >= payload['expires_at']:
                    raise ValueError('Memory proposal expired')
                if self._current(db, payload['category'], payload['key']) != payload['base_digest']:
                    raise ValueError('Memory changed since proposal; new review required')
                target = db.execute('SELECT revoked,expires_at FROM memories WHERE category=? AND memory_key=?',
                                    (payload['category'],payload['key'])).fetchone()
                if target and (target['revoked'] or (target['expires_at'] is not None and target['expires_at'] <= time.time())):
                    raise ValueError('Target memory is revoked or expired; resolve lifecycle policy first')
                now = utc_now()
                metadata = json.dumps({'source': 'operator_reviewed_agent_proposal',
                                       'proposal_id': proposal_id, 'proposal_digest': digest, 'reviewer': reviewer,
                                       'factual_verification': verification, 'require_verified': require_verified})
                db.execute('''INSERT INTO memories(category,memory_key,value,importance,metadata,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?) ON CONFLICT(category,memory_key) DO UPDATE SET
                    value=excluded.value,importance=excluded.importance,metadata=excluded.metadata,
                    archived=0,updated_at=excluded.updated_at''',
                    (payload['category'],payload['key'],payload['value'],payload['importance'],metadata,now,now))
                memory_id = db.execute('SELECT id FROM memories WHERE category=? AND memory_key=?',
                                       (payload['category'], payload['key'])).fetchone()[0]
                status = 'approved'
            db.execute('UPDATE memory_proposals SET status=?,reviewed_at=?,reviewer=?,memory_id=? WHERE id=?',
                       (status, utc_now(), reviewer, memory_id, proposal_id))
            self.evidence.event(db, 'proposal_reviewed', proposal_id, {'proposal_digest': digest,
                'status': status, 'reviewer': reviewer, 'verification': verification, 'memory_id': memory_id})
        return {'proposal_id': proposal_id, 'digest': digest, 'status': status, 'memory_id': memory_id,
                'verification': verification}
