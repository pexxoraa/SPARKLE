from __future__ import annotations

import hmac
import ipaddress
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from sparkle.config import data_root
from sparkle.secrets import SecretNotFoundError, SecretResolver
from sparkle.storage import SQLiteStore, utc_now


def is_loopback_host(host: str) -> bool:
    normalized = host.strip().strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _validated_origin(value: str) -> str:
    if len(value) > 2_048:
        raise ValueError("Allowed origin exceeds 2048 characters")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"Allowed origin must be an HTTP(S) origin: {value}")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


@dataclass(frozen=True, slots=True)
class APIAccessPolicy:
    resolver: SecretResolver
    required: bool = False
    token_refs: tuple[str, ...] = ("SPARKLE_API_TOKEN",)
    allowed_origins: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.token_refs or any(not reference for reference in self.token_refs):
            raise ValueError("API token references cannot be empty")
        validated = tuple(_validated_origin(origin) for origin in self.allowed_origins)
        object.__setattr__(self, "allowed_origins", validated)

    @property
    def configured(self) -> bool:
        return any(self.resolver.status(self.token_refs).values())

    def status(self) -> dict[str, object]:
        return {
            "authentication_required": self.required,
            "token_configured": self.configured,
            "allowed_origins": len(self.allowed_origins),
            "credentials_exposed": False,
        }

    def authorize(self, authorization: str | None) -> bool:
        if not self.required:
            return True
        if not authorization or len(authorization) > 4_096:
            return False
        scheme, separator, supplied = authorization.partition(" ")
        if separator != " " or scheme.lower() != "bearer" or not supplied:
            return False
        try:
            expected = self.resolver.first(self.token_refs)
        except SecretNotFoundError:
            return False
        return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))

    def origin_allowed(self, origin: str | None, host_header: str | None) -> bool:
        if not origin:
            return True
        try:
            normalized = _validated_origin(origin)
        except ValueError:
            return False
        if normalized in self.allowed_origins:
            return True
        if not host_header or any(character in host_header for character in " /\\@"):
            return False
        host = host_header.lower()
        return normalized in {f"http://{host}", f"https://{host}"}

    def cors_headers(self, origin: str | None, host_header: str | None) -> dict[str, str]:
        if not origin or not self.origin_allowed(origin, host_header):
            return {}
        return {
            "Access-Control-Allow-Origin": _validated_origin(origin),
            "Vary": "Origin",
        }

    def validate_bind(self, host: str) -> None:
        if self.required and not self.configured:
            raise SecretNotFoundError(
                "API authentication is required but no API token reference is configured"
            )
        if is_loopback_host(host):
            return
        if not self.required:
            raise ValueError("Non-loopback API binding requires authentication")


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class FixedWindowRateLimiter:
    """Thread-safe in-memory limiter; client identifiers are never persisted."""

    def __init__(
        self,
        limit: int = 120,
        window_seconds: int = 60,
        *,
        max_clients: int = 10_000,
    ):
        if not 1 <= limit <= 10_000:
            raise ValueError("API rate limit must be from 1 to 10000 requests")
        if not 1 <= window_seconds <= 3_600:
            raise ValueError("API rate-limit window must be from 1 to 3600 seconds")
        if not 1 <= max_clients <= 100_000:
            raise ValueError("API rate-limit client capacity must be from 1 to 100000")
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self._buckets: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def allow(self, client_key: str, *, now: float | None = None) -> RateLimitDecision:
        current = time.monotonic() if now is None else now
        with self._lock:
            if client_key not in self._buckets and len(self._buckets) >= self.max_clients:
                expired = [
                    key for key, (started, _) in self._buckets.items()
                    if current < started or current - started >= self.window_seconds
                ]
                for key in expired:
                    self._buckets.pop(key, None)
                if len(self._buckets) >= self.max_clients:
                    oldest = min(self._buckets, key=lambda key: self._buckets[key][0])
                    self._buckets.pop(oldest, None)
            started, count = self._buckets.get(client_key, (current, 0))
            if current - started >= self.window_seconds or current < started:
                started, count = current, 0
            count += 1
            self._buckets[client_key] = (started, count)
            retry_after = max(1, int(self.window_seconds - (current - started) + 0.999))
            return RateLimitDecision(
                allowed=count <= self.limit,
                limit=self.limit,
                remaining=max(0, self.limit - count),
                retry_after=retry_after,
            )

    def status(self) -> dict[str, int]:
        return {
            "requests": self.limit,
            "window_seconds": self.window_seconds,
            "max_clients": self.max_clients,
        }


class APIAuditStore(SQLiteStore):
    """Stores secret-free API access outcomes without client identifiers."""

    ROUTES = frozenset({
        "/api/health", "/api/models", "/api/models/activate", "/api/agents",
        "/api/agents/remove", "/api/memory", "/api/memory/archive",
        "/api/memory/restore", "/api/memory/delete", "/api/knowledge",
        "/api/knowledge/search", "/api/knowledge/sources",
        "/api/knowledge/delete", "/api/traces", "/api/automations",
        "/api/automations/run", "/api/automations/enable",
        "/api/automations/delete", "/api/automation-runs", "/api/builds",
        "/api/builds/verify", "/api/builds/test", "/api/verifications",
        "/api/test-runs", "/api/audit", "/api/chat",
    })
    UNKNOWN_ROUTE = "/api/[unknown]"
    OUTCOMES = {
        "success", "unauthorized", "origin_denied", "rate_limited",
        "client_error", "server_error",
    }

    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "trace_environment" / "api_audit.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS api_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    status INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def record(
        self,
        method: str,
        path: str,
        status: int,
        outcome: str,
        duration_ms: float,
    ) -> int:
        normalized_method = method.upper()
        if normalized_method not in {"GET", "POST", "OPTIONS"}:
            raise ValueError("Unsupported audited API method")
        if not path.startswith("/api/") or "?" in path:
            raise ValueError("Audited API path must be a query-free /api/ path")
        normalized_path = self.normalize_path(path)
        if outcome not in self.OUTCOMES:
            raise ValueError("Unsupported API audit outcome")
        if not 100 <= status <= 599:
            raise ValueError("Audited API status is invalid")
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO api_audit(method, path, status, outcome, duration_ms, created_at)
                VALUES(?,?,?,?,?,?)
            """, (
                normalized_method, normalized_path, status, outcome,
                max(0.0, min(float(duration_ms), 86_400_000.0)), utc_now(),
            ))
        return int(cursor.lastrowid)

    @classmethod
    def normalize_path(cls, path: str) -> str:
        return path if path in cls.ROUTES else cls.UNKNOWN_ROUTE

    def recent(self, *, limit: int = 20) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM api_audit ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [self._public(row) for row in rows]

    @staticmethod
    def _public(row: sqlite3.Row) -> dict[str, object]:
        return {
            "audit_id": row["id"],
            "method": row["method"],
            "path": row["path"],
            "status": row["status"],
            "outcome": row["outcome"],
            "duration_ms": row["duration_ms"],
            "created_at": row["created_at"],
        }
