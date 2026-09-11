"""Opt-in retrieval experiments. The production default remains KnowledgeStore.search."""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Protocol

from sparkle.storage import KnowledgeStore
from sparkle.vector_index import PersistentVectorIndex


class EmbeddingProvider(Protocol):
    identity: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingTestEmbeddings:
    """TEST DOUBLE: token hashing, not a semantic model or quality evidence."""
    identity = "token-hash-test-double-v1"
    dimensions = 128

    def embed(self, texts):
        result = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token, count in Counter(re.findall(r"\w+", text.casefold())).items():
                index = (
                    int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big")
                    % self.dimensions
                )
                vector[index] += count
            result.append(vector)
        return result


class SemanticRetriever:
    """Bounded semantic retrieval backed by a persistent, lifecycle-aware vector index."""

    def __init__(
        self,
        store: KnowledgeStore,
        provider: EmbeddingProvider,
        *,
        max_chunks: int = 1000,
        batch_size: int = 64,
        index: PersistentVectorIndex | None = None,
        index_path: Path | None = None,
    ):
        if type(max_chunks) is not int or not 1 <= max_chunks <= 10_000:
            raise ValueError("Invalid semantic corpus limit")
        if type(batch_size) is not int or not 1 <= batch_size <= 256:
            raise ValueError("Invalid embedding batch size")
        if type(provider.dimensions) is not int or not 1 <= provider.dimensions <= 8192:
            raise ValueError("Invalid embedding dimensions")
        if index is not None and index_path is not None:
            raise ValueError("Specify either index or index_path, not both")
        self.store = store
        self.provider = provider
        self.max_chunks = max_chunks
        self.batch_size = batch_size
        self.index = index or PersistentVectorIndex(store, index_path)
        self.last_evidence: dict[str, object] = {}

    def synchronize(self, *, force: bool = False) -> dict[str, object]:
        evidence = self.index.synchronize(
            self.provider,
            max_chunks=self.max_chunks,
            batch_size=self.batch_size,
            force=force,
        )
        self.last_evidence = {
            "index": evidence,
            "semantic_quality_verified": False,
        }
        return evidence

    def search(self, query, *, limit=5):
        if not isinstance(query, str):
            raise ValueError("Query must be text")
        if not query.strip():
            self.last_evidence = {
                "provider_identity": self.provider.identity,
                "persistent_index": True,
                "semantic_quality_verified": False,
                "empty_query": True,
            }
            return []
        if len(query) > 16384:
            raise ValueError("Query exceeds 16384 characters")
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("Limit must be an integer from 1 to 50")
        self.synchronize()
        results = self.index.search(
            self.provider,
            query,
            limit=limit,
        )
        self.last_evidence = {
            **self.last_evidence,
            "provider_identity": self.provider.identity,
            "persistent_index": True,
            "semantic_quality_verified": False,
        }
        return results


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
            self.last_evidence = {
                "fallback": "lexical",
                "semantic_status": "unavailable",
                "semantic_quality_verified": False,
            }
            return self._eligible(lexical)[: max(1, min(limit, 50))]
        self.last_evidence = {
            "fallback": None,
            "semantic_status": "completed",
            "semantic_quality_verified": False,
        }
        scores, records = {}, {}
        for ranking in (lexical, semantic):
            for rank, row in enumerate(ranking, 1):
                key = row["chunk_id"]
                records[key] = row
                scores[key] = scores.get(key, 0) + 1 / (60 + rank)
        return self._eligible(
            [
                {**records[key], "score": scores[key]}
                for key in sorted(scores, key=lambda key: (-scores[key], key))
            ]
        )[: max(1, min(limit, 50))]

    def _eligible(self, rows):
        filter_results = getattr(self.lexical, "filter_active_results", None)
        return filter_results(rows) if filter_results else rows
