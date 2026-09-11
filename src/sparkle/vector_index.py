from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Protocol

from sparkle.config import data_root
from sparkle.knowledge_lifecycle import ACTIVE_SOURCE
from sparkle.storage import KnowledgeStore, SQLiteStore, utc_now


class EmbeddingProviderLike(Protocol):
    identity: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class VectorIndexError(ValueError):
    pass


class PersistentVectorIndex(SQLiteStore):
    """Provider-neutral persistent chunk embeddings with lifecycle revalidation."""

    MAX_DIMENSIONS = 8192
    MAX_CHUNKS = 50_000
    MAX_BATCH_SIZE = 256
    MAX_INPUT_CHARS = 16_384

    def __init__(self, knowledge: KnowledgeStore, path: Path | None = None):
        self.knowledge = knowledge
        super().__init__(path or data_root() / "knowledge_environment" / "vectors.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS chunk_vectors(
                chunk_id INTEGER NOT NULL,
                source_id INTEGER NOT NULL,
                provider_identity TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                content_sha256 TEXT NOT NULL,
                embedding_input_sha256 TEXT NOT NULL,
                vector_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(chunk_id,provider_identity)
            )""")
            columns = {
                row["name"] for row in db.execute("PRAGMA table_info(chunk_vectors)").fetchall()
            }
            if "embedding_input_sha256" not in columns:
                db.execute(
                    "ALTER TABLE chunk_vectors "
                    "ADD COLUMN embedding_input_sha256 TEXT NOT NULL DEFAULT ''"
                )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunk_vectors_provider "
                "ON chunk_vectors(provider_identity,source_id,chunk_id)"
            )

    @classmethod
    def _provider(cls, provider: EmbeddingProviderLike) -> tuple[str, int]:
        identity = getattr(provider, "identity", None)
        dimensions = getattr(provider, "dimensions", None)
        if (
            not isinstance(identity, str)
            or not identity.strip()
            or len(identity.strip()) > 200
        ):
            raise VectorIndexError("Embedding provider identity is invalid")
        if type(dimensions) is not int or not 1 <= dimensions <= cls.MAX_DIMENSIONS:
            raise VectorIndexError("Embedding provider dimensions are invalid")
        embed = getattr(provider, "embed", None)
        if not callable(embed):
            raise VectorIndexError("Embedding provider interface is invalid")
        return identity.strip(), dimensions

    @classmethod
    def _normalize_vector(cls, vector: Any, dimensions: int) -> list[float]:
        if type(dimensions) is not int or not 1 <= dimensions <= cls.MAX_DIMENSIONS:
            raise VectorIndexError("Embedding dimensions are invalid")
        if not isinstance(vector, list) or len(vector) != dimensions:
            raise VectorIndexError("Embedding vector dimensions do not match")
        values: list[float] = []
        for item in vector:
            if (
                isinstance(item, bool)
                or not isinstance(item, (int, float))
                or not math.isfinite(float(item))
            ):
                raise VectorIndexError("Embedding vectors must contain finite numbers")
            values.append(float(item))
        norm = math.hypot(*values)
        if not math.isfinite(norm):
            raise VectorIndexError("Embedding vector norm is invalid")
        return [value / norm for value in values] if norm else [0.0] * dimensions

    @classmethod
    def _stored_vector(cls, raw: str, dimensions: int) -> list[float]:
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise VectorIndexError("Stored embedding vector is invalid") from exc
        if not isinstance(value, list) or len(value) != dimensions:
            raise VectorIndexError("Stored embedding vector dimensions do not match")
        values: list[float] = []
        for item in value:
            if (
                isinstance(item, bool)
                or not isinstance(item, (int, float))
                or not math.isfinite(float(item))
            ):
                raise VectorIndexError("Stored embedding vector must contain finite numbers")
            values.append(float(item))
        norm = math.hypot(*values)
        if not math.isfinite(norm):
            raise VectorIndexError("Stored embedding vector norm is invalid")
        if norm and not math.isclose(norm, 1.0, rel_tol=1e-9, abs_tol=1e-9):
            raise VectorIndexError("Stored embedding vector is not normalized")
        if not norm and any(values):
            raise VectorIndexError("Stored embedding zero vector is invalid")
        return values

    @staticmethod
    def _digests(title: str, content: str) -> tuple[str, str]:
        content_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        embedding_input = (title + "\n" + content)[: PersistentVectorIndex.MAX_INPUT_CHARS]
        input_digest = hashlib.sha256(embedding_input.encode("utf-8")).hexdigest()
        return content_digest, input_digest

    @staticmethod
    def _embedding_text(title: str, content: str) -> str:
        return (title + "\n" + content)[: PersistentVectorIndex.MAX_INPUT_CHARS]

    def _active_rows(self, *, max_chunks: int) -> list[Any]:
        if type(max_chunks) is not int or not 1 <= max_chunks <= self.MAX_CHUNKS:
            raise VectorIndexError("Semantic corpus limit is invalid")
        with self.knowledge.connect() as db:
            rows = db.execute(
                f"""SELECT chunks.id AS chunk_id,chunks.source_id,chunks.content,sources.title
                    FROM chunks JOIN sources ON sources.id=chunks.source_id
                    WHERE {ACTIVE_SOURCE} ORDER BY chunks.id LIMIT ?""",
                (max_chunks + 1,),
            ).fetchall()
        if len(rows) > max_chunks:
            raise VectorIndexError("Knowledge corpus exceeds persistent vector-index bound")
        return rows

    def synchronize(
        self,
        provider: EmbeddingProviderLike,
        *,
        max_chunks: int = 10_000,
        batch_size: int = 64,
        force: bool = False,
    ) -> dict[str, Any]:
        """Incrementally index active chunks and remove stale provider rows."""
        identity, dimensions = self._provider(provider)
        if type(batch_size) is not int or not 1 <= batch_size <= self.MAX_BATCH_SIZE:
            raise VectorIndexError("Embedding batch size must be 1-256")
        if not isinstance(force, bool):
            raise VectorIndexError("Embedding synchronization force flag is invalid")

        rows = self._active_rows(max_chunks=max_chunks)
        prepared: list[tuple[Any, str, str]] = []
        eligible_ids: set[int] = set()
        for row in rows:
            content_digest, input_digest = self._digests(row["title"], row["content"])
            prepared.append((row, content_digest, input_digest))
            eligible_ids.add(int(row["chunk_id"]))

        with self.connect() as db:
            existing_rows = db.execute(
                "SELECT * FROM chunk_vectors WHERE provider_identity=? ORDER BY chunk_id",
                (identity,),
            ).fetchall()
        existing = {int(row["chunk_id"]): row for row in existing_rows}

        to_embed: list[tuple[Any, str, str]] = []
        for row, content_digest, input_digest in prepared:
            prior = existing.get(int(row["chunk_id"]))
            if (
                force
                or prior is None
                or int(prior["source_id"]) != int(row["source_id"])
                or int(prior["dimensions"]) != dimensions
                or prior["content_sha256"] != content_digest
                or prior["embedding_input_sha256"] != input_digest
            ):
                to_embed.append((row, content_digest, input_digest))

        stale_ids = sorted(set(existing) - eligible_ids)
        embedded = 0
        skipped_after_recheck = 0
        now = utc_now()

        for start in range(0, len(to_embed), batch_size):
            batch = to_embed[start : start + batch_size]
            texts = [self._embedding_text(row["title"], row["content"]) for row, _, _ in batch]
            vectors = provider.embed(texts)
            if not isinstance(vectors, list) or len(vectors) != len(batch):
                raise VectorIndexError("Embedding provider returned an invalid batch count")
            normalized = [self._normalize_vector(vector, dimensions) for vector in vectors]

            valid_records: list[tuple[int, int, str, str, list[float]]] = []
            invalid_ids: list[int] = []
            with self.knowledge.connect() as knowledge_db:
                knowledge_db.execute("BEGIN")
                for (row, content_digest, input_digest), vector in zip(
                    batch, normalized, strict=True
                ):
                    current = knowledge_db.execute(
                        f"""SELECT chunks.content,sources.title FROM chunks
                            JOIN sources ON sources.id=chunks.source_id
                            WHERE chunks.id=? AND chunks.source_id=? AND {ACTIVE_SOURCE}""",
                        (row["chunk_id"], row["source_id"]),
                    ).fetchone()
                    current_id = int(row["chunk_id"])
                    if current is None:
                        invalid_ids.append(current_id)
                        skipped_after_recheck += 1
                        continue
                    current_content_digest, current_input_digest = self._digests(
                        current["title"], current["content"]
                    )
                    if (
                        current_content_digest != content_digest
                        or current_input_digest != input_digest
                    ):
                        invalid_ids.append(current_id)
                        skipped_after_recheck += 1
                        continue
                    valid_records.append(
                        (
                            current_id,
                            int(row["source_id"]),
                            content_digest,
                            input_digest,
                            vector,
                        )
                    )

            with self.connect() as index_db:
                index_db.execute("BEGIN IMMEDIATE")
                for chunk_id in invalid_ids:
                    index_db.execute(
                        "DELETE FROM chunk_vectors WHERE provider_identity=? AND chunk_id=?",
                        (identity, chunk_id),
                    )
                for chunk_id, source_id, content_digest, input_digest, vector in valid_records:
                    index_db.execute(
                        """INSERT INTO chunk_vectors(
                            chunk_id,source_id,provider_identity,dimensions,
                            content_sha256,embedding_input_sha256,vector_json,updated_at
                        ) VALUES(?,?,?,?,?,?,?,?)
                        ON CONFLICT(chunk_id,provider_identity) DO UPDATE SET
                            source_id=excluded.source_id,
                            dimensions=excluded.dimensions,
                            content_sha256=excluded.content_sha256,
                            embedding_input_sha256=excluded.embedding_input_sha256,
                            vector_json=excluded.vector_json,
                            updated_at=excluded.updated_at""",
                        (
                            chunk_id,
                            source_id,
                            identity,
                            dimensions,
                            content_digest,
                            input_digest,
                            json.dumps(vector, separators=(",", ":"), allow_nan=False),
                            now,
                        ),
                    )
                    embedded += 1

        if stale_ids:
            with self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.executemany(
                    "DELETE FROM chunk_vectors WHERE provider_identity=? AND chunk_id=?",
                    [(identity, chunk_id) for chunk_id in stale_ids],
                )

        return {
            "provider_identity": identity,
            "dimensions": dimensions,
            "eligible_chunks": len(prepared),
            "embedded": embedded,
            "unchanged": len(prepared) - len(to_embed),
            "stale_removed": len(stale_ids),
            "skipped_after_recheck": skipped_after_recheck,
            "synchronized_at": now,
            "semantic_quality_verified": False,
        }

    def rebuild(
        self,
        provider: EmbeddingProviderLike,
        *,
        max_chunks: int = 10_000,
        batch_size: int = 64,
    ) -> dict[str, Any]:
        return self.synchronize(
            provider,
            max_chunks=max_chunks,
            batch_size=batch_size,
            force=True,
        )

    def search(
        self,
        provider: EmbeddingProviderLike,
        query: str,
        *,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        identity, dimensions = self._provider(provider)
        if not isinstance(query, str) or not query.strip() or len(query) > self.MAX_INPUT_CHARS:
            raise VectorIndexError("Semantic query must contain 1-16384 characters")
        if type(limit) is not int or not 1 <= limit <= 50:
            raise VectorIndexError("Semantic result limit must be 1-50")

        vectors = provider.embed([query])
        if not isinstance(vectors, list) or len(vectors) != 1:
            raise VectorIndexError("Embedding provider returned an invalid query vector")
        query_vector = self._normalize_vector(vectors[0], dimensions)

        with self.connect() as index_db:
            indexed = index_db.execute(
                """SELECT * FROM chunk_vectors
                   WHERE provider_identity=? AND dimensions=? ORDER BY chunk_id""",
                (identity, dimensions),
            ).fetchall()

        ranked: list[dict[str, Any]] = []
        stale_ids: list[int] = []
        with self.knowledge.connect() as knowledge_db:
            knowledge_db.execute("BEGIN")
            for item in indexed:
                row = knowledge_db.execute(
                    f"""SELECT chunks.id AS chunk_id,chunks.source_id,chunks.position,
                        chunks.content,sources.title,sources.source_uri,sources.media_type
                        FROM chunks JOIN sources ON sources.id=chunks.source_id
                        WHERE chunks.id=? AND chunks.source_id=? AND {ACTIVE_SOURCE}""",
                    (item["chunk_id"], item["source_id"]),
                ).fetchone()
                if row is None:
                    stale_ids.append(int(item["chunk_id"]))
                    continue
                content_digest, input_digest = self._digests(row["title"], row["content"])
                if (
                    content_digest != item["content_sha256"]
                    or input_digest != item["embedding_input_sha256"]
                ):
                    stale_ids.append(int(item["chunk_id"]))
                    continue
                vector = self._stored_vector(item["vector_json"], dimensions)
                score = sum(
                    left * right
                    for left, right in zip(query_vector, vector, strict=True)
                )
                if score > 0:
                    ranked.append(
                        dict(row)
                        | {
                            "score": score,
                            "embedding_provider": identity,
                            "semantic_quality_verified": False,
                        }
                    )

        if stale_ids:
            with self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.executemany(
                    "DELETE FROM chunk_vectors WHERE provider_identity=? AND chunk_id=?",
                    [(identity, chunk_id) for chunk_id in sorted(set(stale_ids))],
                )

        ranked.sort(key=lambda row: (-row["score"], row["chunk_id"]))
        return ranked[:limit]

    def stats(self) -> dict[str, Any]:
        with self.connect() as db:
            count = db.execute("SELECT count(*) FROM chunk_vectors").fetchone()[0]
            providers = db.execute(
                "SELECT count(DISTINCT provider_identity) FROM chunk_vectors"
            ).fetchone()[0]
        return {
            "status": "ready",
            "vectors": int(count),
            "providers": int(providers),
            "persistent": True,
            "semantic_quality_verified": False,
        }
