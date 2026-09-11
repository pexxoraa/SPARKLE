from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from sparkle.knowledge_lifecycle import KnowledgeLifecycle
from sparkle.retrieval import SemanticRetriever
from sparkle.storage import KnowledgeStore
from sparkle.vector_index import PersistentVectorIndex, VectorIndexError


class CountingEmbeddings:
    identity = "counting-test-embeddings-v1"
    dimensions = 3

    def __init__(self):
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        vectors = []
        for text in texts:
            lowered = text.casefold()
            vectors.append([
                float(lowered.count("alpha") + 1),
                float(lowered.count("beta") + 1),
                float(lowered.count("gamma") + 1),
            ])
        return vectors


class VectorIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.knowledge = KnowledgeStore(Path(self.temp.name) / "knowledge.sqlite3")
        self.knowledge.initialize()
        self.provider = CountingEmbeddings()
        self.index_path = Path(self.temp.name) / "vectors.sqlite3"
        self.index = PersistentVectorIndex(self.knowledge, self.index_path)

    def test_incremental_persistence_reopen_and_semantic_retrieval(self):
        alpha = self.knowledge.ingest_text("Alpha", "alpha alpha")
        beta = self.knowledge.ingest_text("Beta", "beta beta")
        first = self.index.synchronize(self.provider, max_chunks=100, batch_size=1)
        self.assertEqual(first["embedded"], 2)
        self.assertEqual(len(self.provider.calls), 2)

        calls = len(self.provider.calls)
        second = self.index.synchronize(self.provider, max_chunks=100, batch_size=2)
        self.assertEqual(second["embedded"], 0)
        self.assertEqual(second["unchanged"], 2)
        self.assertEqual(len(self.provider.calls), calls)

        reopened = PersistentVectorIndex(self.knowledge, self.index_path)
        retriever = SemanticRetriever(
            self.knowledge,
            self.provider,
            max_chunks=100,
            index=reopened,
        )
        results = retriever.search("alpha", limit=2)
        self.assertEqual(results[0]["source_id"], alpha)
        self.assertEqual({item["source_id"] for item in results}, {alpha, beta})
        self.assertTrue(retriever.last_evidence["persistent_index"])
        self.assertFalse(retriever.last_evidence["semantic_quality_verified"])
        self.assertFalse(reopened.stats()["semantic_quality_verified"])

    def test_lifecycle_and_content_changes_invalidate_stored_vectors(self):
        source = self.knowledge.ingest_text("Alpha", "alpha content")
        self.index.synchronize(self.provider, max_chunks=100)
        lifecycle = KnowledgeLifecycle(self.knowledge)
        lifecycle.transition(source, "archive", 0, operator="cli")
        self.assertEqual(self.index.search(self.provider, "alpha"), [])
        with self.index.connect() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM chunk_vectors WHERE source_id=?", (source,)
                ).fetchone()
            )

        lifecycle.transition(source, "restore", 1, operator="cli")
        self.index.synchronize(self.provider, max_chunks=100)
        with self.knowledge.connect() as db:
            db.execute("UPDATE sources SET title='Gamma' WHERE id=?", (source,))
        self.assertEqual(self.index.search(self.provider, "gamma"), [])
        before = len(self.provider.calls)
        sync = self.index.synchronize(self.provider, max_chunks=100)
        self.assertEqual(sync["embedded"], 1)
        self.assertEqual(len(self.provider.calls), before + 1)
        self.assertEqual(
            self.index.search(self.provider, "gamma")[0]["source_id"], source
        )

    def test_provider_binding_batches_and_vector_validation_fail_closed(self):
        for index in range(5):
            self.knowledge.ingest_text(f"Item {index}", f"alpha {index}")
        sync = self.index.synchronize(
            self.provider, max_chunks=100, batch_size=2
        )
        self.assertEqual(sync["embedded"], 5)
        self.assertEqual([len(call) for call in self.provider.calls], [2, 2, 1])

        class BadFinite:
            identity = "bad-finite-v1"
            dimensions = 2

            def embed(self, texts):
                return [[math.nan, 0.0] for _ in texts]

        with self.assertRaises(VectorIndexError):
            self.index.synchronize(BadFinite(), max_chunks=100)

        class BadDimensions:
            identity = "bad-dimensions-v1"
            dimensions = 2

            def embed(self, texts):
                return [[1.0] for _ in texts]

        with self.assertRaises(VectorIndexError):
            self.index.synchronize(BadDimensions(), max_chunks=100)

    def test_stored_vectors_must_remain_normalized(self):
        self.knowledge.ingest_text("Alpha", "alpha")
        self.index.synchronize(self.provider, max_chunks=100)
        with self.index.connect() as db:
            db.execute(
                "UPDATE chunk_vectors SET vector_json='[2.0,0.0,0.0]' "
                "WHERE provider_identity=?",
                (self.provider.identity,),
            )
        with self.assertRaisesRegex(VectorIndexError, "not normalized"):
            self.index.search(self.provider, "alpha")


if __name__ == "__main__":
    unittest.main()
