"""Opt-in retrieval experiments. The production default remains KnowledgeStore.search."""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Protocol

from sparkle.storage import KnowledgeStore
from sparkle.knowledge_lifecycle import ACTIVE_SOURCE


class EmbeddingProvider(Protocol):
    identity: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingTestEmbeddings:
    """TEST DOUBLE: token hashing, not a semantic model or quality evidence."""
    identity = 'token-hash-test-double-v1'
    dimensions = 128

    def embed(self, texts):
        result = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token, count in Counter(re.findall(r'\w+', text.casefold())).items():
                index = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], 'big') % self.dimensions
                vector[index] += count
            result.append(vector)
        return result


class SemanticRetriever:
    """Small-corpus, bounded, replaceable embedding path; no persistent vector cache."""
    def __init__(self, store: KnowledgeStore, provider: EmbeddingProvider, *, max_chunks=1000):
        if type(max_chunks) is not int or not 1 <= max_chunks <= 10000:
            raise ValueError('Invalid semantic corpus limit')
        if type(provider.dimensions) is not int or not 1 <= provider.dimensions <= 8192:
            raise ValueError('Invalid embedding dimensions')
        self.store, self.provider, self.max_chunks = store, provider, max_chunks

    def search(self, query, *, limit=5):
        if not isinstance(query, str):
            raise ValueError('Query must be text')
        with self.store.connect() as connection:
            rows = connection.execute(f'''SELECT chunks.id AS chunk_id, chunks.source_id,
                chunks.position, chunks.content, sources.title, sources.source_uri,
                sources.media_type FROM chunks JOIN sources ON sources.id=chunks.source_id
                WHERE {ACTIVE_SOURCE} ORDER BY chunks.id LIMIT ?''', (self.max_chunks + 1,)).fetchall()
        if len(rows) > self.max_chunks:
            raise ValueError('Semantic corpus exceeds configured bound')
        if not rows:
            return []
        texts = [query[:16384]] + [(r['title'] + '\n' + r['content'])[:16384] for r in rows]
        vectors = self.provider.embed(texts)
        if len(vectors) != len(texts):
            raise ValueError('Embedding count mismatch')
        normalized = []
        for vector in vectors:
            if len(vector) != self.provider.dimensions or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                for v in vector
            ):
                raise ValueError('Invalid embedding vector')
            norm = math.hypot(*vector)
            if not math.isfinite(norm):
                raise ValueError('Invalid embedding norm')
            normalized.append([v / norm for v in vector] if norm else [0.0]*len(vector))
        ranked = []
        for row, vector in zip(rows, normalized[1:]):
            score = sum(a*b for a,b in zip(normalized[0], vector))
            if score > 0:
                ranked.append({**dict(row), 'score': score})
        return self.store.filter_active_results(sorted(ranked, key=lambda r: (-r['score'], r['chunk_id'])))[:max(1,min(limit,50))]


class HybridRetriever:
    """Equal-weight reciprocal-rank fusion, constant 60; lexical fallback is explicit."""
    def __init__(self, lexical, semantic):
        self.lexical, self.semantic = lexical, semantic
        self.last_evidence = {}

    def search(self, query, *, limit=5):
        lexical = self.lexical.search(query, limit=50)
        try:
            semantic = self.semantic.search(query, limit=50)
        except Exception:
            self.last_evidence = {'fallback': 'lexical', 'semantic_status': 'unavailable'}
            return self._eligible(lexical)[:max(1,min(limit,50))]
        self.last_evidence = {'fallback': None, 'semantic_status': 'completed'}
        scores, records = {}, {}
        for ranking in (lexical, semantic):
            for rank, row in enumerate(ranking, 1):
                key = row['chunk_id']
                records[key] = row
                scores[key] = scores.get(key, 0) + 1 / (60 + rank)
        return self._eligible([{**records[key], 'score': scores[key]} for key in sorted(
            scores, key=lambda key: (-scores[key], key)
        )])[:max(1,min(limit,50))]

    def _eligible(self, rows):
        filter_results = getattr(self.lexical, 'filter_active_results', None)
        return filter_results(rows) if filter_results else rows
