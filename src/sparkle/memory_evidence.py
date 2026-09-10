"""Exact-claim validation against operator-attested facts, never model assertions.

Trust is in the operator's attestation, not the source-reference string. This is
not natural-language inference, independent web verification, or source voting.
"""
from __future__ import annotations

import hashlib
import json
import time

from sparkle.storage import MemoryStore, utc_now

OPERATORS = ('cli', 'authenticated_api', 'local_api')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class MemoryEvidence:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS memory_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL,
                memory_key TEXT NOT NULL, value TEXT NOT NULL, source_ref TEXT NOT NULL,
                expires_at REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,
                revision INTEGER NOT NULL, operator TEXT NOT NULL,
                UNIQUE(category,memory_key,source_ref))''')
            db.execute('''CREATE TABLE IF NOT EXISTS memory_evidence_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                record_id TEXT NOT NULL, evidence TEXT NOT NULL, created_at TEXT NOT NULL)''')
            for operation in ('UPDATE', 'DELETE'):
                db.execute(f'''CREATE TRIGGER IF NOT EXISTS memory_evidence_no_{operation.lower()}
                    BEFORE {operation} ON memory_evidence_events BEGIN
                    SELECT RAISE(ABORT,'Memory evidence history is append-only'); END''')

    @staticmethod
    def event(db, kind, record_id, evidence):
        db.execute('INSERT INTO memory_evidence_events(kind,record_id,evidence,created_at) VALUES(?,?,?,?)',
                   (kind, str(record_id), json.dumps(evidence, sort_keys=True), utc_now()))

    def attest(self, category, key, value, source_ref, *, ttl_seconds=86400, operator):
        if (operator not in OPERATORS or not isinstance(category, str)
                or category not in MemoryStore.VALID_CATEGORIES - {'conversations'}
                or not isinstance(key, str) or not 1 <= len(key.strip()) <= 256
                or not isinstance(value, str) or not 1 <= len(value.strip()) <= 8000
                or not isinstance(source_ref, str) or not 1 <= len(source_ref.strip()) <= 512
                or type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 31536000):
            raise ValueError('Invalid operator fact attestation')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''INSERT INTO memory_facts(category,memory_key,value,source_ref,expires_at,revision,operator)
                VALUES(?,?,?,?,?,1,?) ON CONFLICT(category,memory_key,source_ref) DO UPDATE SET
                value=excluded.value,expires_at=excluded.expires_at,revoked=0,
                revision=memory_facts.revision+1,operator=excluded.operator''',
                (category,key.strip(),value.strip(),source_ref.strip(),time.time()+ttl_seconds,operator))
            row = dict(db.execute('SELECT * FROM memory_facts WHERE category=? AND memory_key=? AND source_ref=?',
                                  (category,key.strip(),source_ref.strip())).fetchone())
            self.event(db, 'fact_attested', row['id'], {'fact_digest': digest(row), 'revision': row['revision'], 'operator': operator})
        return {'fact_id': row['id'], 'revision': row['revision'], 'expires_at': row['expires_at']}

    def revoke(self, fact_id, *, operator):
        if type(fact_id) is not int or operator not in OPERATORS:
            raise ValueError('Invalid fact revocation')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM memory_facts WHERE id=?', (fact_id,)).fetchone()
            if row is None or row['revoked']:
                raise ValueError('Fact missing or already revoked')
            db.execute('UPDATE memory_facts SET revoked=1,revision=revision+1 WHERE id=?', (fact_id,))
            self.event(db, 'fact_revoked', fact_id, {'operator': operator, 'prior_digest': digest(dict(row))})
        return {'fact_id': fact_id, 'revoked': True}

    @staticmethod
    def evaluate(db, payload):
        rows = db.execute('''SELECT * FROM memory_facts WHERE category=? AND memory_key=?
            AND revoked=0 AND expires_at>? ORDER BY id LIMIT 65''',
            (payload['category'], payload['key'], time.time())).fetchall()
        values = {r['value'] for r in rows}
        status, reason = 'INCONCLUSIVE', 'missing_active_evidence'
        if len(rows) > 64:
            reason = 'evidence_limit'
        elif len(values) > 1:
            reason = 'conflicting_attestations'
        elif values:
            status = 'VERIFIED' if payload['value'] in values else 'REJECTED'
            reason = 'exact_attested_match' if status == 'VERIFIED' else 'contradicts_attested_value'
        return {'status': status, 'reason': reason, 'method': 'operator-attested-exact-claim/1',
                'fact_ids': [r['id'] for r in rows],
                'evidence_digest': digest([dict(r) for r in rows])}

    def history(self, *, limit=100):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Evidence history limit must be from 1 to 100')
        with self.store.connect() as db:
            rows = db.execute('SELECT * FROM memory_evidence_events ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        return [dict(r) | {'evidence': json.loads(r['evidence'])} for r in rows]

    def facts(self):
        with self.store.connect() as db:
            rows = db.execute('SELECT * FROM memory_facts ORDER BY id DESC LIMIT 100').fetchall()
        return [dict(r) for r in rows]
