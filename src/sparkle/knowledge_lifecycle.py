"""Operator-owned knowledge lifecycle; model retrieval cannot alter policy."""
from __future__ import annotations

import json
import time

# Alias contract: caller joins/queries sources as `sources`.
ACTIVE_SOURCE = """NOT EXISTS (SELECT 1 FROM knowledge_source_policy p
    WHERE p.source_id=sources.id AND
    (p.state!='active' OR (p.expires_at IS NOT NULL AND p.expires_at<=sparkle_now())))"""


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS knowledge_source_policy (
        source_id INTEGER PRIMARY KEY REFERENCES sources(id) ON DELETE CASCADE,
        state TEXT NOT NULL CHECK(state IN ('active','archived','revoked','superseded')),
        revision INTEGER NOT NULL, expires_at REAL, superseded_by INTEGER)''')
    db.execute('''CREATE TABLE IF NOT EXISTS knowledge_source_events (
        id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL, action TEXT NOT NULL,
        revision INTEGER NOT NULL, details TEXT NOT NULL, created_at REAL NOT NULL)''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_events_source ON knowledge_source_events(source_id,id)')
    for action in ('UPDATE','DELETE'):
        db.execute(f'''CREATE TRIGGER IF NOT EXISTS knowledge_events_no_{action.lower()}
            BEFORE {action} ON knowledge_source_events BEGIN
            SELECT RAISE(ABORT,'Knowledge event history is append-only'); END''')
    db.execute('''CREATE TRIGGER IF NOT EXISTS knowledge_source_deleted BEFORE DELETE ON sources BEGIN
        INSERT INTO knowledge_source_events(source_id,action,revision,details,created_at)
        VALUES(old.id,'deleted',COALESCE((SELECT revision FROM knowledge_source_policy WHERE source_id=old.id),0),
               '{}',sparkle_now()); END''')


class KnowledgeLifecycle:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def _id(value):
        if type(value) is not int or not 0 < value < 2**63:
            raise ValueError('Invalid source identity')

    @staticmethod
    def _state(db, source_id):
        if db.execute('SELECT 1 FROM sources WHERE id=?',(source_id,)).fetchone() is None:
            raise ValueError('Knowledge source is missing')
        row = db.execute('SELECT * FROM knowledge_source_policy WHERE source_id=?',(source_id,)).fetchone()
        return dict(row) if row else {'source_id':source_id,'state':'active','revision':0,
                                     'expires_at':None,'superseded_by':None}

    def inspect(self, source_id):
        self._id(source_id)
        with self.store.connect() as db:
            state = self._state(db,source_id)
        state['eligible'] = state['state']=='active' and (state['expires_at'] is None or state['expires_at']>time.time())
        return state

    def transition(self, source_id, action, expected_revision, *, operator,
                   retention_seconds=None, replacement_id=None):
        self._id(source_id)
        if operator not in ('cli','local_api','authenticated_api'):
            raise ValueError('Operator authorization required')
        if type(expected_revision) is not int or not 0 <= expected_revision < 2**63-1:
            raise ValueError('Invalid expected revision')
        if action not in ('archive','restore','revoke','supersede','retention'):
            raise ValueError('Invalid knowledge lifecycle action')
        if action != 'retention' and retention_seconds is not None:
            raise ValueError('Retention only applies to a retention action')
        if action != 'supersede' and replacement_id is not None:
            raise ValueError('Replacement only applies to supersession')
        if retention_seconds is not None and (type(retention_seconds) is not int or not 1 <= retention_seconds <= 31536000):
            raise ValueError('Retention must be 1 to 31536000 seconds or null')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            state = self._state(db,source_id)
            if state['revision'] != expected_revision:
                raise ValueError('Knowledge source revision conflict')
            if state['state'] in ('revoked','superseded'):
                raise ValueError('Terminal knowledge source cannot be reactivated')
            if action == 'restore':
                if state['state'] != 'archived' or (state['expires_at'] is not None and state['expires_at']<=time.time()):
                    raise ValueError('Only an unexpired archived source can be restored')
                state['state']='active'
            elif action == 'retention':
                state['expires_at']=None if retention_seconds is None else time.time()+retention_seconds
            elif action == 'supersede':
                self._id(replacement_id)
                if source_id == replacement_id:
                    raise ValueError('A source cannot supersede itself')
                replacement = self._state(db,replacement_id)
                if replacement['state']!='active' or (replacement['expires_at'] is not None and replacement['expires_at']<=time.time()):
                    raise ValueError('Replacement must be an active unexpired source')
                state['state']='superseded';state['superseded_by']=replacement_id
            else:
                state['state']={'archive':'archived','revoke':'revoked'}[action]
            state['revision']+=1
            db.execute('''INSERT INTO knowledge_source_policy VALUES(?,?,?,?,?)
                ON CONFLICT(source_id) DO UPDATE SET state=excluded.state,revision=excluded.revision,
                expires_at=excluded.expires_at,superseded_by=excluded.superseded_by''',
                tuple(state[k] for k in ('source_id','state','revision','expires_at','superseded_by')))
            db.execute('''INSERT INTO knowledge_source_events(source_id,action,revision,details,created_at)
                VALUES(?,?,?,?,?)''',(source_id,action,state['revision'],json.dumps(state|{'operator':operator}),time.time()))
        return state

    def history(self, source_id):
        self._id(source_id)
        with self.store.connect() as db:
            rows=db.execute('SELECT * FROM knowledge_source_events WHERE source_id=? ORDER BY id DESC LIMIT 100',(source_id,)).fetchall()
        return [dict(row)|{'details':json.loads(row['details'])} for row in rows]
