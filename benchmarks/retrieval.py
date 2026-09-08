from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sparkle.retrieval import HashingTestEmbeddings, HybridRetriever, SemanticRetriever
from sparkle.context import ContextBuilder
from sparkle.storage import KnowledgeStore, MemoryStore

CORPUS = Path(__file__).with_name('corpus.json')


def load_corpus(store):
    data = json.loads(CORPUS.read_text())
    identities = {}
    for source in data['sources']:
        texts = [c['text'] for c in source['chunks']]
        sid = store.ingest_text(source['title'], '\n\n'.join(texts),
                                chunk_chars=max(map(len,texts)), source_uri='benchmark:'+source['id'])
        with store.connect() as conn:
            rows = conn.execute('SELECT id,content FROM chunks WHERE source_id=? ORDER BY position',(sid,)).fetchall()
        if [r['content'] for r in rows] != texts:
            raise ValueError('Benchmark chunk mapping mismatch')
        for row, chunk in zip(rows,source['chunks']):
            if chunk['id'] in identities.values():
                raise ValueError('Duplicate chunk identity')
            identities[row['id']] = chunk['id']
    for query in data['queries']:
        if not query['relevant'] or not set(query['relevant']) <= set(identities.values()):
            raise ValueError('Invalid relevance judgment')
    return data, identities


def metrics(rows):
    if not rows:
        raise ValueError('Evaluation requires queries')
    result = {}
    for k in (1,3,5):
        # Standard macro recall: fraction of judged relevant chunks retrieved.
        result[f'recall@{k}'] = sum(len(set(r['ranking'][:k]) & set(r['relevant'])) / len(set(r['relevant'])) for r in rows)/len(rows)
        result[f'hit@{k}'] = sum(bool(set(r['ranking'][:k]) & set(r['relevant'])) for r in rows)/len(rows)
    result['mrr'] = sum(next((1/i for i,c in enumerate(r['ranking'],1) if c in r['relevant']),0) for r in rows)/len(rows)
    return {key:round(value,6) for key,value in result.items()}


def run_retrieval(root):
    store = KnowledgeStore(root/'knowledge.sqlite3')
    corpus, identities = load_corpus(store)
    semantic = SemanticRetriever(store, HashingTestEmbeddings())
    retrievers = {'lexical':store, 'semantic_test_double':semantic,
                  'hybrid_test_double':HybridRetriever(store,semantic)}
    report = {'dataset_version':corpus['version'], 'dataset_sha256':hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
              'query_count':len(corpus['queries']), 'source_count':len(corpus['sources']), 'chunk_count':len(identities), 'real_semantic_evaluation':'pending',
              'definition':'Macro Recall@K = relevant chunks retrieved / all judged relevant chunks; Hit@K = any relevant hit; MRR = reciprocal first relevant rank within top 50 (zero if absent).',
              'systems':{}}
    for name,retriever in retrievers.items():
        rows=[]
        for query in corpus['queries']:
            rows.append({**query, 'ranking':[identities[r['chunk_id']] for r in retriever.search(query['text'],limit=50)]})
        report['systems'][name]={'metrics':metrics(rows),'queries':rows,
            'by_class':{c:metrics([r for r in rows if r['class']==c]) for c in sorted({r['class'] for r in rows})},
            'failures_at_5':[{'id':r['id'],'class':r['class']} for r in rows if not set(r['ranking'][:5]) & set(r['relevant'])]}
    context=ContextBuilder(MemoryStore(root/'memory.sqlite3'),store)
    context_rows=[]
    observed_bytes=[]
    for query in corpus['queries']:
        rendered=context.build(query['text']).render()
        payload=json.loads(rendered) if rendered else {'knowledge':[]}
        observed_bytes.append(len(rendered.encode('utf-8')))
        context_rows.append({**query,'ranking':[identities[r['chunk_id']] for r in payload['knowledge']]})
    report['context']={'metrics':metrics(context_rows),'max_bytes':12000,'max_knowledge_items':5,
                       'observed_max_bytes':max(observed_bytes), 'answer_quality':'not_measured'}
    return report
