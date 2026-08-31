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
                    input_modalities TEXT NOT NULL DEFAULT '["text"]',
                    content_identifiers TEXT NOT NULL DEFAULT '[]',
                    processing_stage TEXT NOT NULL DEFAULT 'received',
                    output_modalities TEXT NOT NULL DEFAULT '[]',
                    execution_metadata TEXT NOT NULL DEFAULT '{}',
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

            columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(traces)"
                ).fetchall()
            }
            migrations = {
                "input_modalities": "TEXT NOT NULL DEFAULT '[\"text\"]'",
                "content_identifiers": "TEXT NOT NULL DEFAULT '[]'",
                "processing_stage": "TEXT NOT NULL DEFAULT 'received'",
                "output_modalities": "TEXT NOT NULL DEFAULT '[]'",
                "execution_metadata": "TEXT NOT NULL DEFAULT '{}'",
            }
            for name, definition in migrations.items():
                if name not in columns:
                    connection.execute(
                        f"ALTER TABLE traces ADD COLUMN {name} {definition}"
                    )

    @staticmethod
    def _labels(
        values: list[str] | None,
        *,
        label: str,
        maximum: int = 16,
        chars: int = 128,
    ) -> list[str]:
        result = values or []
        if (
            not isinstance(result, list)
            or len(result) > maximum
            or any(
                not isinstance(item, str) or not item or len(item) > chars
                for item in result
            )
        ):
            raise ValueError(f"Trace {label} is invalid")
        return result

    @staticmethod
    def _execution_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("Trace execution metadata must be an object")
        safe = SecretResolver.redact(value)
        encoded = json.dumps(
            safe, separators=(",", ":"), ensure_ascii=False,
            sort_keys=True, allow_nan=False,
        )
        if len(encoded.encode("utf-8")) > 16_000:
            raise ValueError("Trace execution metadata is too large")
        return safe

    def start(
        self,
        *,
        input_source: str,
        agent: str | None = None,
        input_modalities: list[str] | None = None,
        content_identifiers: list[str] | None = None,
        processing_stage: str = "received",
        execution_metadata: dict[str, Any] | None = None,
    ) -> tuple[str, float]:
        modalities = self._labels(
            input_modalities or ["text"], label="input modalities", chars=32,
        )
        identifiers = self._labels(
            content_identifiers, label="content identifiers",
        )
        if not isinstance(processing_stage, str) or not processing_stage or len(processing_stage) > 64:
            raise ValueError("Trace processing stage is invalid")
        metadata = self._execution_metadata(execution_metadata)
        year = datetime.now(UTC).year
        started = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            next_sequence = int(connection.execute(
                "SELECT COALESCE(MAX(year_sequence), 0) + 1 FROM traces WHERE year=?", (year,)
            ).fetchone()[0])
            trace_id = f"SPK-{year}-{next_sequence:06d}"
            connection.execute("""
                INSERT INTO traces(
                    trace_id, year, year_sequence, input_source,
                    input_modalities, content_identifiers, processing_stage,
                    execution_metadata, agent, status, started_at
                ) VALUES(?,?,?,?,?,?,?,?,?,'running',?)
            """, (
                trace_id, year, next_sequence, input_source,
                json.dumps(modalities, separators=(",", ":")),
                json.dumps(identifiers, separators=(",", ":")),
                processing_stage,
                json.dumps(metadata, separators=(",", ":"), ensure_ascii=False, sort_keys=True),
                agent, started,
            ))
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
        processing_stage: str | None = None,
        output_modalities: list[str] | None = None,
        execution_metadata: dict[str, Any] | None = None,
        result_summary: str | None = None,
        error_type: str | None = None,
    ) -> None:
        safe_summary = result_summary[:500] if result_summary else None
        values = [
            SecretResolver.redact(item)
            for item in (tools or [], data_accessed or [], data_created or [], transformations or [], storage_destinations or [])
        ]
        encoded = [json.dumps(value, separators=(",", ":"), ensure_ascii=False) for value in values]
        stage = processing_stage or ("completed" if status == "success" else "failed")
        if not isinstance(stage, str) or not stage or len(stage) > 64:
            raise ValueError("Trace processing stage is invalid")
        outputs = self._labels(
            output_modalities or (["text"] if status == "success" else []),
            label="output modalities", chars=32,
        )
        metadata = self._execution_metadata(execution_metadata)
        with self.connect() as connection:
            connection.execute("""
                UPDATE traces SET status=?, agent=?, model=?, provider=?, tools=?, data_accessed=?,
                    data_created=?, transformations=?, storage_destinations=?, result_summary=?, error_type=?,
                    processing_stage=?, output_modalities=?, execution_metadata=?,
                    duration_ms=?, finished_at=? WHERE trace_id=?
            """, (
                status, agent, model, provider, *encoded, safe_summary, error_type,
                stage,
                json.dumps(outputs, separators=(",", ":")),
                json.dumps(metadata, separators=(",", ":"), ensure_ascii=False, sort_keys=True),
                round((time.monotonic() - started_clock) * 1000, 3), utc_now(), trace_id,
            ))

    def recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM traces ORDER BY id DESC LIMIT ?", (max(1, min(limit, 100)),)
            ).fetchall()
        return [self._public(row) for row in rows]

    def annotate_lifecycle(
        self,
        trace_id: str,
        *,
        processing_stage: str,
        transformations: list[str],
        data_accessed: list[str],
        data_created: list[str],
        storage_destinations: list[str],
        execution_metadata: dict[str, Any],
        result_summary: str,
    ) -> None:
        """Advance a completed trace with bounded content-free lifecycle evidence."""
        if (
            not isinstance(processing_stage, str)
            or not processing_stage
            or len(processing_stage) > 64
        ):
            raise ValueError("Trace processing stage is invalid")
        labels = [
            self._labels(transformations, label="transformations"),
            self._labels(data_accessed, label="data accessed"),
            self._labels(data_created, label="data created"),
            self._labels(storage_destinations, label="storage destinations"),
        ]
        metadata = self._execution_metadata(execution_metadata)
        safe_summary = result_summary[:500]
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE traces
                SET processing_stage=?, transformations=?, data_accessed=?,
                    data_created=?, storage_destinations=?, execution_metadata=?,
                    result_summary=?
                WHERE trace_id=? AND status IN ('success','failure')
            """, (
                processing_stage,
                *(json.dumps(value, separators=(",", ":")) for value in labels),
                json.dumps(
                    metadata, separators=(",", ":"), ensure_ascii=False,
                    sort_keys=True,
                ),
                safe_summary,
                trace_id,
            ))
        if cursor.rowcount != 1:
            raise ValueError("Trace lifecycle target does not exist")

    @staticmethod
    def _public(row: sqlite3.Row) -> dict[str, Any]:
        json_fields = {
            "tools", "data_accessed", "data_created", "transformations",
            "storage_destinations", "input_modalities", "content_identifiers",
            "output_modalities", "execution_metadata",
        }
        return {key: (json.loads(row[key]) if key in json_fields else row[key]) for key in row.keys() if key not in {"id", "year", "year_sequence"}}
