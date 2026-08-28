from __future__ import annotations

import json
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sparkle.config import data_root
from sparkle.secrets import SecretResolver
from sparkle.storage import SQLiteStore, utc_now


class TraceStore(SQLiteStore):
    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "trace_environment" / "traces.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS traces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT UNIQUE,
                    year INTEGER NOT NULL,
                    year_sequence INTEGER NOT NULL,
                    input_source TEXT NOT NULL,
                    agent TEXT,
                    model TEXT,
                    provider TEXT,
                    tools TEXT NOT NULL DEFAULT '[]',
                    data_accessed TEXT NOT NULL DEFAULT '[]',
                    data_created TEXT NOT NULL DEFAULT '[]',
                    transformations TEXT NOT NULL DEFAULT '[]',
                    storage_destinations TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL,
                    result_summary TEXT,
                    error_type TEXT,
                    duration_ms REAL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    UNIQUE(year, year_sequence)
                )
            """)

    def start(self, *, input_source: str, agent: str | None = None) -> tuple[str, float]:
        year = datetime.now(UTC).year
        started = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            next_sequence = int(connection.execute(
                "SELECT COALESCE(MAX(year_sequence), 0) + 1 FROM traces WHERE year=?", (year,)
            ).fetchone()[0])
            trace_id = f"SPK-{year}-{next_sequence:06d}"
            connection.execute("""
                INSERT INTO traces(trace_id, year, year_sequence, input_source, agent, status, started_at)
                VALUES(?,?,?,?,?,'running',?)
            """, (trace_id, year, next_sequence, input_source, agent, started))
        return trace_id, time.monotonic()

    def finish(
        self,
        trace_id: str,
        started_clock: float,
        *,
        status: str,
        agent: str,
        model: str | None,
        provider: str | None,
        tools: list[str] | None = None,
        data_accessed: list[str] | None = None,
        data_created: list[str] | None = None,
        transformations: list[str] | None = None,
        storage_destinations: list[str] | None = None,
        result_summary: str | None = None,
        error_type: str | None = None,
    ) -> None:
        safe_summary = result_summary[:500] if result_summary else None
        values = [
            SecretResolver.redact(item)
            for item in (tools or [], data_accessed or [], data_created or [], transformations or [], storage_destinations or [])
        ]
        encoded = [json.dumps(value, separators=(",", ":"), ensure_ascii=False) for value in values]
        with self.connect() as connection:
            connection.execute("""
                UPDATE traces SET status=?, agent=?, model=?, provider=?, tools=?, data_accessed=?,
                    data_created=?, transformations=?, storage_destinations=?, result_summary=?, error_type=?,
                    duration_ms=?, finished_at=? WHERE trace_id=?
            """, (
                status, agent, model, provider, *encoded, safe_summary, error_type,
                round((time.monotonic() - started_clock) * 1000, 3), utc_now(), trace_id,
            ))

    def recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM traces ORDER BY id DESC LIMIT ?", (max(1, min(limit, 100)),)
            ).fetchall()
        return [self._public(row) for row in rows]

    @staticmethod
    def _public(row: sqlite3.Row) -> dict[str, Any]:
        json_fields = {"tools", "data_accessed", "data_created", "transformations", "storage_destinations"}
        return {key: (json.loads(row[key]) if key in json_fields else row[key]) for key in row.keys() if key not in {"id", "year", "year_sequence"}}
