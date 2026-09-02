from __future__ import annotations

import time
import uuid
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sparkle.config import data_root
from sparkle.contracts import TokenUsage
from sparkle.model import ModelError
from sparkle.storage import SQLiteStore, utc_now


HEALTH_STATES = frozenset({"HEALTHY", "DEGRADED", "UNAVAILABLE"})
HEALTH_REASONS = frozenset({
    "verified_success", "not_verified", "configuration_failure",
    "authentication_failure", "connectivity_failure", "timeout",
    "model_unavailable", "rate_limited", "provider_failure", "disabled",
})


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    record_id: str
    provider: str
    model: str
    capability: str
    health: str
    selection_reason: str
    fallback: bool
    test_harness: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ModelRuntimeStore(SQLiteStore):
    """Content-free model health and request evidence."""

    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "ai_environment" / "model_runtime.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS model_health (
                    record_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    evidence_source TEXT NOT NULL DEFAULT 'provider'
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS model_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT UNIQUE NOT NULL,
                    record_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    health_at_selection TEXT NOT NULL,
                    selection_reason TEXT NOT NULL,
                    fallback INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    latency_ms REAL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    provider_request_id TEXT,
                    error_type TEXT
                    ,test_harness INTEGER NOT NULL DEFAULT 0
                )
            """)
            health_columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(model_health)"
                ).fetchall()
            }
            if "evidence_source" not in health_columns:
                connection.execute(
                    "ALTER TABLE model_health ADD COLUMN evidence_source TEXT NOT NULL DEFAULT 'provider'"
                )
            request_columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(model_requests)"
                ).fetchall()
            }
            if "test_harness" not in request_columns:
                connection.execute(
                    "ALTER TABLE model_requests ADD COLUMN test_harness INTEGER NOT NULL DEFAULT 0"
                )

    def health(self, record_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT record_id,state,reason,observed_at,evidence_source FROM model_health WHERE record_id=?",
                (record_id,),
            ).fetchone()
        return dict(row) if row else None

    def record_health(
        self, record_id: str, state: str, reason: str, *, evidence_source: str,
    ) -> None:
        if state not in HEALTH_STATES or reason not in HEALTH_REASONS:
            raise ValueError("Model health evidence is invalid")
        if evidence_source not in {"provider", "test_harness"}:
            raise ValueError("Model health evidence source is invalid")
        with self.connect() as connection:
            connection.execute("""
                INSERT INTO model_health(record_id,state,reason,observed_at,evidence_source)
                VALUES(?,?,?,?,?)
                ON CONFLICT(record_id) DO UPDATE SET
                    state=excluded.state,
                    reason=excluded.reason,
                    observed_at=excluded.observed_at,
                    evidence_source=excluded.evidence_source
            """, (record_id, state, reason, utc_now(), evidence_source))

    def start(self, decision: RoutingDecision) -> tuple[str, float]:
        request_id = "SPK-MODEL-" + uuid.uuid4().hex.upper()
        with self.connect() as connection:
            connection.execute("""
                INSERT INTO model_requests(
                    request_id,record_id,provider,model,capability,
                    health_at_selection,selection_reason,fallback,started_at,status,
                    test_harness
                ) VALUES(?,?,?,?,?,?,?,?,?,'running',?)
            """, (
                request_id, decision.record_id, decision.provider, decision.model,
                decision.capability, decision.health, decision.selection_reason,
                int(decision.fallback), utc_now(), int(decision.test_harness),
            ))
        return request_id, time.monotonic()

    def finish_success(
        self,
        request_id: str,
        started: float,
        *,
        attempts: int,
        usage: TokenUsage,
        usage_reported: bool,
        provider_request_id: str | None,
    ) -> None:
        safe_provider_request_id = (
            provider_request_id
            if isinstance(provider_request_id, str)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", provider_request_id)
            else None
        )
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE model_requests SET
                    finished_at=?,latency_ms=?,status='success',attempts=?,
                    input_tokens=?,output_tokens=?,provider_request_id=?
                WHERE request_id=? AND status='running'
            """, (
                utc_now(), round((time.monotonic() - started) * 1000, 3),
                max(1, attempts),
                usage.input_tokens if usage_reported else None,
                usage.output_tokens if usage_reported else None,
                safe_provider_request_id, request_id,
            ))
        if cursor.rowcount != 1:
            raise ValueError("Model request evidence is not running")

    def finish_failure(
        self,
        request_id: str,
        started: float,
        *,
        attempts: int,
        error_type: str,
    ) -> None:
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE model_requests SET
                    finished_at=?,latency_ms=?,status='failure',attempts=?,error_type=?
                WHERE request_id=? AND status='running'
            """, (
                utc_now(), round((time.monotonic() - started) * 1000, 3),
                max(1, attempts), error_type[:64], request_id,
            ))
        if cursor.rowcount != 1:
            raise ValueError("Model request evidence is not running")

    def recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM model_requests ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        result = []
        for row in rows:
            item = {key: row[key] for key in row.keys() if key != "id"}
            item["fallback"] = bool(item["fallback"])
            item["test_harness"] = bool(item["test_harness"])
            result.append(item)
        return result


class ModelHealthMonitor:
    def __init__(self, registry: Any, store: ModelRuntimeStore):
        self.registry = registry
        self.store = store

    def status(self, record_id: str) -> dict[str, Any]:
        record = self.registry._records[record_id]
        if not record.enabled:
            return {"state": "UNAVAILABLE", "reason": "disabled", "observed_at": None}
        secret_refs = record.config.get("secret_refs", [])
        configured = record_id in self.registry._injected_ids or not secret_refs or any(
            self.registry.secrets.status(secret_refs).values()
        )
        if not configured:
            return {
                "state": "UNAVAILABLE", "reason": "configuration_failure",
                "observed_at": None,
                "evidence_source": "configuration",
            }
        observed = self.store.health(record_id)
        return observed or {
            "state": "DEGRADED", "reason": "not_verified", "observed_at": None,
            "evidence_source": (
                "test_harness" if record_id in self.registry._injected_ids
                else "configuration"
            ),
        }

    def success(self, record_id: str) -> None:
        test_harness = record_id in self.registry._injected_ids
        self.store.record_health(
            record_id,
            "DEGRADED" if test_harness else "HEALTHY",
            "not_verified" if test_harness else "verified_success",
            evidence_source="test_harness" if test_harness else "provider",
        )

    def failure(self, record_id: str, error: ModelError) -> None:
        reason = error.category if error.category in HEALTH_REASONS else "provider_failure"
        state = "DEGRADED" if reason in {
            "rate_limited", "timeout", "connectivity_failure", "provider_failure",
        } else "UNAVAILABLE"
        self.store.record_health(
            record_id, state, reason,
            evidence_source=(
                "test_harness" if record_id in self.registry._injected_ids
                else "provider"
            ),
        )
