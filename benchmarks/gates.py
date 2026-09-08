"""Frozen lexical contract. Updates require review, never automatic baseline blessing."""
from benchmarks.retrieval import metrics

FLOORS = {'recall@1':0.625, 'recall@3':0.75, 'recall@5':0.75, 'mrr':0.71875}


def check_retrieval(report, baseline):
    errors=[]
    if report['dataset_sha256'] != baseline['dataset_sha256']:
        errors.append('Corpus changed: review relevance judgments and version before rebasing')
    lexical=report['systems']['lexical']
    for key, floor in FLOORS.items():
        if lexical['metrics'][key] + 0.0000005 < floor:
            errors.append('Lexical regression: '+key)
    old={r['id']:r for r in baseline['systems']['lexical']['queries']}
    for row in lexical['queries']:
        if row['id'] not in old:
            errors.append('Unreviewed query: '+row['id']);continue
        if row['required']:
            if not set(row['ranking'][:1]) & set(row['relevant']):
                errors.append('Required first-hit regression: '+row['id'])
            if not set(row['relevant']) <= set(row['ranking'][:5]):
                errors.append('Required coverage regression: '+row['id'])
        if metrics([row])['mrr'] < metrics([old[row['id']]])['mrr']:
            errors.append('First-relevant rank regression: '+row['id'])
    if {r['id'] for r in lexical['queries']} != set(old):
        errors.append('Query set mismatch')
    return errors
