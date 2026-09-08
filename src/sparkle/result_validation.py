"""Deterministic post-execution validation against trusted, operator-owned criteria.

This stage does not trust an agent's success flag and never calls another model.
Unknown criteria or missing observations are inconclusive, not success.
"""
from __future__ import annotations

import math


def validate_result(criteria: list[dict], observations: dict) -> dict:
    if not isinstance(criteria, list) or len(criteria) > 128 or not isinstance(observations, dict):
        return {"validation_status": "inconclusive", "checks": [], "score": 0.0}
    checks = []
    for criterion in criteria:
        if not isinstance(criterion, dict) or set(criterion) != {'kind', 'key', 'expected'}:
            checks.append({'key': None, 'status': 'inconclusive', 'reason': 'invalid_criterion'})
            continue
        kind, key = criterion.get('kind'), criterion.get('key')
        if not isinstance(key, str) or not isinstance(kind, str):
            checks.append({'key': None, 'status': 'inconclusive', 'reason': 'invalid_criterion'})
            continue
        if kind not in {'equals', 'contains', 'number'} or key not in observations or 'expected' not in criterion:
            checks.append({'key': key, 'status': 'inconclusive', 'reason': 'unsupported_or_missing_evidence'})
            continue
        value, expected = observations[key], criterion['expected']
        if kind == 'number':
            try:
                passed = (type(value) in (int,float) and type(expected) in (int,float)
                          and math.isfinite(value) and math.isfinite(expected)
                          and abs(value - expected) <= 1e-9)
            except (OverflowError, ValueError):
                passed = False
        elif kind == 'contains':
            passed = isinstance(value, list) and isinstance(expected, list) and all(v in value for v in expected)
        else:
            passed = type(value) is type(expected) and value == expected
        checks.append({'key': key, 'status': 'validated' if passed else 'rejected',
                       'reason': None if passed else 'outcome_mismatch'})
    statuses = [check['status'] for check in checks]
    status = ('rejected' if 'rejected' in statuses else
              'inconclusive' if not statuses or 'inconclusive' in statuses else 'validated')
    return {'validation_status': status, 'checks': checks,
            'score': sum(s == 'validated' for s in statuses) / len(statuses) if statuses else 0.0}
