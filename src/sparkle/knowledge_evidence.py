"""Stored citation integrity, explicitly not external-source truth or entailment."""
from __future__ import annotations

import hashlib
import json
import re

from sparkle.knowledge_lifecycle import ACTIVE_SOURCE


def citation_digest(row):
    snapshot = {key: row[key] for key in (
        'source_id', 'chunk_id', 'position', 'title', 'source_uri', 'content',
    )}
    return hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def verify_citations(store, citations):
    if not isinstance(citations, list) or not 1 <= len(citations) <= 20:
        raise ValueError('Citations must contain 1 to 20 entries')
    checks = []
    with store.connect() as db:
        # All checks observe one read snapshot, including concurrent deletion.
        db.execute('BEGIN')
        for index, citation in enumerate(citations):
            status, reason = 'INCONCLUSIVE', 'invalid_citation'
            valid = (isinstance(citation, dict)
                     and set(citation) == {'source_id', 'chunk_id', 'digest', 'quote'}
                     and all(type(citation[k]) is int and 0 < citation[k] < 2**63
                             for k in ('source_id', 'chunk_id'))
                     and isinstance(citation['digest'], str)
                     and re.fullmatch('[a-f0-9]{64}', citation['digest']) is not None
                     and isinstance(citation['quote'], str)
                     and 0 < len(citation['quote']) <= 1800
                     and bool(citation['quote'].strip()))
            if valid:
                row = db.execute('''SELECT chunks.id AS chunk_id, chunks.source_id,
                    chunks.position, chunks.content, sources.title, sources.source_uri
                    FROM chunks JOIN sources ON sources.id=chunks.source_id
                    WHERE chunks.id=?''', (citation['chunk_id'],)).fetchone()
                if row is None:
                    status, reason = 'REJECTED', 'missing_stored_chunk'
                elif db.execute(f'SELECT 1 FROM sources WHERE id=? AND {ACTIVE_SOURCE}', (row['source_id'],)).fetchone() is None:
                    status, reason = 'REJECTED', 'source_ineligible'
                elif row['source_id'] != citation['source_id']:
                    status, reason = 'REJECTED', 'source_identity_mismatch'
                elif citation_digest(row) != citation['digest']:
                    status, reason = 'REJECTED', 'snapshot_mismatch'
                elif citation['quote'] not in row['content']:
                    status, reason = 'REJECTED', 'quote_not_present'
                else:
                    status, reason = 'VERIFIED', 'exact_stored_quote'
            checks.append({'index': index, 'status': status, 'reason': reason})
    statuses = [check['status'] for check in checks]
    overall = ('REJECTED' if 'REJECTED' in statuses else
               'INCONCLUSIVE' if 'INCONCLUSIVE' in statuses else 'VERIFIED')
    return {'citation_integrity': overall, 'claim_truth': 'INCONCLUSIVE',
            'external_source_verified': False, 'checks': checks}
