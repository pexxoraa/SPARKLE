from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sparkle.config import data_root


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SQLiteStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def backup(self, destination: Path) -> Path:
        target = destination.expanduser().resolve()
        if target == self.path.resolve():
            raise ValueError("Backup destination must differ from the live database")
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as source, sqlite3.connect(target) as backup:
            source.backup(backup)
        return target


class MemoryStore(SQLiteStore):
    VALID_CATEGORIES = {
        "user", "goals", "preferences", "skills", "learning", "exams", "projects",
        "research", "content", "tasks", "decisions", "mistakes", "conversations", "summaries",
    }

    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "memory_environment" / "memory.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    importance REAL NOT NULL DEFAULT 0.5 CHECK(importance BETWEEN 0 AND 1),
                    metadata TEXT NOT NULL DEFAULT '{}',
                    archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(category, memory_key)
                )
            """)
            connection.execute("CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category, archived)")

    def remember(
        self,
        category: str,
        key: str,
        value: str,
        *,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        if category not in self.VALID_CATEGORIES:
            raise ValueError(f"Unsupported memory category: {category}")
        if not key.strip() or not value.strip():
            raise ValueError("Memory key and value cannot be empty")
        now = utc_now()
        encoded = json.dumps(metadata or {}, separators=(",", ":"), ensure_ascii=False)
        with self.connect() as connection:
            connection.execute("""
                INSERT INTO memories(category, memory_key, value, importance, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(category, memory_key) DO UPDATE SET
                    value=excluded.value, importance=excluded.importance, metadata=excluded.metadata,
                    archived=0, updated_at=excluded.updated_at
            """, (category, key.strip(), value.strip(), importance, encoded, now, now))
            row = connection.execute(
                "SELECT id FROM memories WHERE category=? AND memory_key=?", (category, key.strip())
            ).fetchone()
        return int(row["id"])

    def search(self, query: str, *, limit: int = 5, category: str | None = None) -> list[dict[str, Any]]:
        terms = [term for term in re.findall(r"[a-zA-Z0-9_]+", query.lower()) if len(term) > 1]
        where = ["archived=0"]
        params: list[Any] = []
        if category:
            where.append("category=?")
            params.append(category)
        if terms:
            where.append("(" + " OR ".join("lower(value) LIKE ? OR lower(memory_key) LIKE ?" for _ in terms) + ")")
            for term in terms:
                params.extend((f"%{term}%", f"%{term}%"))
        params.append(max(1, min(limit, 100)))
        sql = f"SELECT * FROM memories WHERE {' AND '.join(where)} ORDER BY importance DESC, updated_at DESC LIMIT ?"
        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._public(row) for row in rows]

    def recent(self, *, limit: int = 20, category: str | None = None) -> list[dict[str, Any]]:
        where, params = "archived=0", []
        if category:
            where += " AND category=?"
            params.append(category)
        params.append(max(1, min(limit, 100)))
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM memories WHERE {where} ORDER BY updated_at DESC LIMIT ?", params
            ).fetchall()
        return [self._public(row) for row in rows]

    def archive(self, memory_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE memories SET archived=1, updated_at=? WHERE id=?", (utc_now(), memory_id)
            )
        return cursor.rowcount == 1

    def restore(self, memory_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE memories SET archived=0, updated_at=? WHERE id=?", (utc_now(), memory_id)
            )
        return cursor.rowcount == 1

    def delete(self, memory_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        return cursor.rowcount == 1

    def export(self, *, include_archived: bool = True) -> list[dict[str, Any]]:
        where = "" if include_archived else " WHERE archived=0"
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM memories{where} ORDER BY id"
            ).fetchall()
        return [self._public(row) for row in rows]

    @staticmethod
    def _public(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "category": row["category"], "key": row["memory_key"],
            "value": row["value"], "importance": row["importance"],
            "metadata": json.loads(row["metadata"]), "created_at": row["created_at"],
            "updated_at": row["updated_at"], "archived": bool(row["archived"]),
        }


class KnowledgeStore(SQLiteStore):
    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "knowledge_environment" / "knowledge.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source_uri TEXT,
                    media_type TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    token_terms TEXT NOT NULL,
                    UNIQUE(source_id, position)
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id);
            """)

    @staticmethod
    def _terms(text: str) -> list[str]:
        return [term.lower() for term in re.findall(r"[a-zA-Z0-9_]+", text) if len(term) > 1]

    def ingest_text(
        self,
        title: str,
        content: str,
        *,
        source_uri: str | None = None,
        media_type: str = "text/plain",
        metadata: dict[str, Any] | None = None,
        chunk_chars: int = 1800,
    ) -> int:
        if not title.strip() or not content.strip():
            raise ValueError("Knowledge title and content cannot be empty")
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            candidate = f"{current}\n\n{paragraph}".strip()
            if current and len(candidate) > chunk_chars:
                chunks.append(current)
                current = paragraph
            else:
                current = candidate
        if current:
            chunks.append(current)
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO sources(title, source_uri, media_type, metadata, created_at) VALUES(?,?,?,?,?)",
                (title.strip(), source_uri, media_type, json.dumps(metadata or {}), utc_now()),
            )
            source_id = int(cursor.lastrowid)
            connection.executemany(
                "INSERT INTO chunks(source_id, position, content, token_terms) VALUES(?,?,?,?)",
                ((source_id, index, chunk, " ".join(self._terms(chunk))) for index, chunk in enumerate(chunks)),
            )
        return source_id

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        query_terms = self._terms(query)
        if not query_terms:
            return []
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT chunks.id, chunks.source_id, chunks.position, chunks.content, chunks.token_terms,
                       sources.title, sources.source_uri, sources.media_type
                FROM chunks JOIN sources ON sources.id=chunks.source_id
            """).fetchall()
        query_counts = Counter(query_terms)
        ranked: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            document_counts = Counter(row["token_terms"].split())
            score = sum(min(count, document_counts.get(term, 0)) for term, count in query_counts.items())
            if score:
                length_normalizer = max(1.0, len(document_counts) ** 0.25)
                ranked.append((score / length_normalizer, row))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "chunk_id": row["id"], "source_id": row["source_id"], "title": row["title"],
                "source_uri": row["source_uri"], "media_type": row["media_type"],
                "position": row["position"], "content": row["content"], "score": round(score, 4),
            }
            for score, row in ranked[:max(1, min(limit, 50))]
        ]

    def stats(self) -> dict[str, int]:
        with self.connect() as connection:
            source_count = connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
            chunk_count = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {"sources": int(source_count), "chunks": int(chunk_count)}

    def list_sources(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT sources.*, COUNT(chunks.id) AS chunk_count
                FROM sources LEFT JOIN chunks ON chunks.source_id=sources.id
                GROUP BY sources.id ORDER BY sources.id DESC LIMIT ?
            """, (max(1, min(limit, 1_000)),)).fetchall()
        return [
            {
                "source_id": row["id"], "title": row["title"],
                "source_uri": row["source_uri"], "media_type": row["media_type"],
                "metadata": json.loads(row["metadata"]),
                "created_at": row["created_at"], "chunks": row["chunk_count"],
            }
            for row in rows
        ]

    def delete_source(self, source_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM sources WHERE id=?", (source_id,))
        return cursor.rowcount == 1
