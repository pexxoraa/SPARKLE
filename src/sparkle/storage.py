from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sparkle.config import data_root
from sparkle.knowledge_lifecycle import ACTIVE_SOURCE, KnowledgeLifecycle, initialize as initialize_knowledge_lifecycle


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class ClosingConnection(sqlite3.Connection):
    """Keep SQLite transaction semantics and release the handle on context exit."""
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


class StorageConnectionError(sqlite3.OperationalError):
    """Content-free infrastructure failure, never a model/validation outcome."""
    category = "storage_unavailable"

    def __init__(self):
        super().__init__("Storage connection initialization failed")

    def to_dict(self):
        return {"stage": "storage_initialization", "error_type": self.category}


class SQLiteStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = None
        try:
            connection = sqlite3.connect(self.path, timeout=10, factory=ClosingConnection)
            connection.row_factory = sqlite3.Row
            connection.create_function("sparkle_now", 0, time.time)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            return connection
        except BaseException as exc:
            # __exit__ has not been entered yet: setup owns this handle.
            if connection is not None:
                connection.close()
            if isinstance(exc, (sqlite3.Error, OSError)):
                raise StorageConnectionError() from None
            raise

    def backup(self, destination: Path) -> Path:
        target = destination.expanduser().resolve()
        if target == self.path.resolve():
            raise ValueError("Backup destination must differ from the live database")
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as source, sqlite3.connect(target, factory=ClosingConnection) as backup:
            source.backup(backup)
        return target


class MemoryStore(SQLiteStore):
    # A strict verified-memory policy is checked against current operator facts
    # at retrieval time, never just against a historical metadata success flag.
    VISIBILITY = """archived=0 AND revoked=0 AND (expires_at IS NULL OR expires_at>sparkle_now()) AND (
        json_extract(metadata, '$.require_verified') IS NOT 1 OR (
            EXISTS (SELECT 1 FROM memory_facts f WHERE f.category=memories.category
                AND f.memory_key=memories.memory_key AND f.revoked=0
                AND f.expires_at>sparkle_now() AND f.value=memories.value)
            AND NOT EXISTS (SELECT 1 FROM memory_facts f WHERE f.category=memories.category
                AND f.memory_key=memories.memory_key AND f.revoked=0
                AND f.expires_at>sparkle_now() AND f.value!=memories.value)
            AND (SELECT count(*) FROM memory_facts f WHERE f.category=memories.category
                AND f.memory_key=memories.memory_key AND f.revoked=0
                AND f.expires_at>sparkle_now())<=64))"""
    VALID_CATEGORIES = {
        "user", "goals", "preferences", "skills", "learning", "exams", "projects",
        "research", "content", "tasks", "decisions", "mistakes", "conversations", "summaries",
    }

    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "memory_environment" / "memory.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
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
            from sparkle.memory_lifecycle import initialize
            initialize(connection)
        from sparkle.memory_evidence import MemoryEvidence
        MemoryEvidence(self)

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
        terms = []
        for match in re.finditer(r"\w+", query.lower()):
            term = match.group()
            if (len(term) > 1 or any(ord(char) > 127 for char in term)) and term not in terms:
                terms.append(term)
                if len(terms) == 64:
                    break
        # An unmatched nonempty query is not a request to return recent memory.
        if query.strip() and not terms:
            return []
        where = [self.VISIBILITY]
        params: list[Any] = []
        if category:
            where.append("category=?")
            params.append(category)
        if terms:
            where.append("(" + " OR ".join("lower(value) LIKE ? ESCAPE '\\' OR lower(memory_key) LIKE ? ESCAPE '\\'" for _ in terms) + ")")
            for term in terms:
                literal = term.replace("\\", "\\\\").replace("_", "\\_").replace("%", "\\%")
                params.extend((f"%{literal}%", f"%{literal}%"))
        params.append(max(1, min(limit, 100)))
        sql = f"SELECT * FROM memories WHERE {' AND '.join(where)} ORDER BY importance DESC, updated_at DESC LIMIT ?"
        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._public(row) for row in rows]

    def recent(self, *, limit: int = 20, category: str | None = None) -> list[dict[str, Any]]:
        where, params = self.VISIBILITY, []
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
                "UPDATE memories SET archived=0, updated_at=? WHERE id=? AND revoked=0 AND (expires_at IS NULL OR expires_at>sparkle_now())", (utc_now(), memory_id)
            )
        return cursor.rowcount == 1

    def delete(self, memory_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        return cursor.rowcount == 1

    def set_retention(self, memory_id: int, seconds: int | None) -> bool:
        if type(memory_id) is not int or (seconds is not None and (type(seconds) is not int or not 1 <= seconds <= 31536000)):
            raise ValueError("Retention must be null or an integer from 1 to 31536000 seconds")
        with self.connect() as db:
            cursor = db.execute("UPDATE memories SET expires_at=?,updated_at=? WHERE id=?",
                (None if seconds is None else time.time()+seconds, utc_now(), memory_id))
        return cursor.rowcount == 1

    def revoke(self, memory_id: int) -> bool:
        if type(memory_id) is not int:
            raise ValueError("Memory ID must be an integer")
        with self.connect() as db:
            cursor = db.execute("UPDATE memories SET revoked=1,updated_at=? WHERE id=? AND revoked=0", (utc_now(),memory_id))
        return cursor.rowcount == 1

    def history(self, memory_id: int | None = None, *, limit=100):
        if (memory_id is not None and type(memory_id) is not int) or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Invalid memory history query")
        where, args = ("", (limit,)) if memory_id is None else ("WHERE memory_id=?", (memory_id,limit))
        with self.connect() as db:
            rows = db.execute(f"SELECT * FROM memory_versions {where} ORDER BY id DESC LIMIT ?",args).fetchall()
        return [dict(r) | {"snapshot":json.loads(r['snapshot'])} for r in rows]

    def export(self, *, include_archived: bool = True) -> list[dict[str, Any]]:
        where = "" if include_archived else " WHERE " + self.VISIBILITY
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
            "expires_at": row["expires_at"], "revoked": bool(row["revoked"]),
        }


class KnowledgeStore(SQLiteStore):
    MAX_METADATA_BYTES = 4_096
    MONITOR_KEY_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")

    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "knowledge_environment" / "knowledge.sqlite3")
        self.initialize()
        self.lifecycle = KnowledgeLifecycle(self)

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source_uri TEXT,
                    media_type TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    content_digest TEXT,
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
            columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(sources)"
                ).fetchall()
            }
            if "content_digest" not in columns:
                connection.execute(
                    "ALTER TABLE sources ADD COLUMN content_digest TEXT"
                )

            # Serialize the one-time migration with concurrent initializers. Index,
            # backfill and maintenance triggers commit together or roll back together.
            connection.commit()
            connection.execute("BEGIN IMMEDIATE")
            initialize_knowledge_lifecycle(connection)
            indexed = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='knowledge_search'"
            ).fetchone()
            if not indexed:
                connection.execute(
                    "CREATE VIRTUAL TABLE knowledge_search USING fts5("
                    "title, content, tokenize='unicode61 remove_diacritics 2')"
                )
                connection.execute("""
                    INSERT INTO knowledge_search(rowid, title, content)
                    SELECT chunks.id, sources.title, chunks.content
                    FROM chunks JOIN sources ON sources.id=chunks.source_id
                """)
                for statement in (
                    """CREATE TRIGGER knowledge_chunk_insert AFTER INSERT ON chunks BEGIN
                        INSERT INTO knowledge_search(rowid,title,content)
                        VALUES(new.id,(SELECT title FROM sources WHERE id=new.source_id),new.content);
                    END""",
                    """CREATE TRIGGER knowledge_chunk_delete AFTER DELETE ON chunks BEGIN
                        DELETE FROM knowledge_search WHERE rowid=old.id;
                    END""",
                    """CREATE TRIGGER knowledge_chunk_update AFTER UPDATE ON chunks BEGIN
                        UPDATE knowledge_search SET content=new.content,
                        title=(SELECT title FROM sources WHERE id=new.source_id)
                        WHERE rowid=old.id;
                    END""",
                    """CREATE TRIGGER knowledge_title_update AFTER UPDATE OF title ON sources BEGIN
                        UPDATE knowledge_search SET title=new.title
                        WHERE rowid IN (SELECT id FROM chunks WHERE source_id=new.id);
                    END""",
                ):
                    connection.execute(statement)

    @staticmethod
    def _terms(text: str) -> list[str]:
        return [term.lower() for term in re.findall(r"[^\W_]+", text, flags=re.UNICODE) if len(term) > 1]

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
        if type(chunk_chars) is not int or not 1 <= chunk_chars <= 100_000:
            raise ValueError("chunk_chars must be an integer between 1 and 100000")
        if not title.strip() or not content.strip():
            raise ValueError("Knowledge title and content cannot be empty")
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("Knowledge metadata must be an object")
        metadata_value = metadata or {}
        monitor_flag = metadata_value.get("research_monitor")
        monitor_key = metadata_value.get("monitor_key")
        if monitor_flag is not None and not isinstance(monitor_flag, bool):
            raise ValueError("research_monitor must be a boolean")
        if monitor_key is not None and (
            monitor_flag is not True
            or not isinstance(monitor_key, str)
            or self.MONITOR_KEY_PATTERN.fullmatch(monitor_key) is None
        ):
            raise ValueError(
                "monitor_key requires research_monitor=true and a 1-64 character safe identifier"
            )
        if monitor_flag is True and monitor_key is None:
            raise ValueError("research_monitor=true requires monitor_key")
        encoded_metadata = json.dumps(
            metadata_value, separators=(",", ":"), ensure_ascii=False,
        )
        if len(encoded_metadata.encode("utf-8")) > self.MAX_METADATA_BYTES:
            raise ValueError("Knowledge metadata exceeds 4096 bytes")
        content_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
        paragraphs = [part[offset:offset + chunk_chars] for part in paragraphs
                      for offset in range(0, len(part), chunk_chars)]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            candidate = f"{current}\n\n{paragraph}" if current else paragraph
            if current and len(candidate) > chunk_chars:
                chunks.append(current)
                current = paragraph
            else:
                current = candidate
        if current:
            chunks.append(current)
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO sources(title, source_uri, media_type, metadata, content_digest, created_at) VALUES(?,?,?,?,?,?)",
                (
                    title.strip(), source_uri, media_type,
                    encoded_metadata, content_digest, utc_now(),
                ),
            )
            source_id = int(cursor.lastrowid)
            connection.executemany(
                "INSERT INTO chunks(source_id, position, content, token_terms) VALUES(?,?,?,?)",
                ((source_id, index, chunk, " ".join(self._terms(chunk))) for index, chunk in enumerate(chunks)),
            )
        return source_id

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        if not isinstance(query, str):
            raise ValueError("Knowledge query must be text")
        # Bound retrieval work without rejecting an otherwise valid long chat request.
        query_terms = list(dict.fromkeys(self._terms(query[:16_384])))[:64]
        if not query_terms:
            return []
        # Only literal Unicode tokens enter MATCH; caller FTS operators are data.
        match = " OR ".join('"' + term + '"' for term in query_terms)
        with self.connect() as connection:
            rows = connection.execute(f"""
                SELECT chunks.id, chunks.source_id, chunks.position, chunks.content,
                       sources.title, sources.source_uri, sources.media_type,
                       bm25(knowledge_search, 3.0, 1.0) AS relevance
                FROM knowledge_search
                JOIN chunks ON chunks.id=knowledge_search.rowid
                JOIN sources ON sources.id=chunks.source_id
                WHERE knowledge_search MATCH ? AND {ACTIVE_SOURCE}
                ORDER BY relevance, chunks.id LIMIT ?
            """, (match, max(1, min(limit, 50)))).fetchall()
        return [
            {
                "chunk_id": row["id"], "source_id": row["source_id"], "title": row["title"],
                "source_uri": row["source_uri"], "media_type": row["media_type"],
                "position": row["position"], "content": row["content"],
                "score": -row["relevance"],
            }
            for row in rows
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

    def monitor_observations(self, *, limit: int = 200) -> list[dict[str, Any]]:
        """Return bounded internal revision evidence without content or source URIs."""
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT id, media_type, metadata, content_digest, created_at
                FROM sources ORDER BY id DESC LIMIT ?
            """, (max(1, min(limit, 1_000)),)).fetchall()
        return [
            {
                "source_id": row["id"],
                "media_type": row["media_type"],
                "metadata": json.loads(row["metadata"]),
                "content_digest": row["content_digest"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def delete_source(self, source_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM sources WHERE id=?", (source_id,))
        return cursor.rowcount == 1

    def filter_active_results(self, rows):
        if len(rows)>10000:
            raise ValueError('Knowledge result set exceeds bound')
        with self.connect() as db:
            db.execute('BEGIN')
            active=set()
            ids=list({row['source_id'] for row in rows})
            for offset in range(0,len(ids),200):
                batch=ids[offset:offset+200]
                marks=','.join('?' for _ in batch)
                active.update(row[0] for row in db.execute(
                    f'SELECT sources.id FROM sources WHERE sources.id IN ({marks}) AND {ACTIVE_SOURCE}',batch))
        return [row for row in rows if row['source_id'] in active]
