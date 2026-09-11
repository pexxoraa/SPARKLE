from __future__ import annotations

import json
import re
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from sparkle.config import data_root
from sparkle.storage import SQLiteStore, utc_now


class InteractionUnavailableError(RuntimeError):
    pass


class InteractionSessionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BrowserRequest:
    url: str
    allowed_hosts: tuple[str, ...]
    timeout_seconds: int = 15
    max_text_chars: int = 20_000

    def __post_init__(self) -> None:
        try:
            parsed = urlsplit(self.url)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Browser request URL is invalid") from exc
        if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None or port not in {None, 443}:
            raise ValueError("Browser requests require credential-free HTTPS on port 443")
        normalized = tuple(host.lower() for host in self.allowed_hosts)
        if not normalized or len(normalized) > 32 or any(
            not isinstance(host, str) or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", host)
            for host in normalized
        ):
            raise ValueError("Browser allowed hosts are invalid")
        if parsed.hostname.lower() not in normalized:
            raise ValueError("Browser destination is not allowlisted")
        if not 1 <= self.timeout_seconds <= 60:
            raise ValueError("Browser timeout must be from 1 to 60 seconds")
        if not 1 <= self.max_text_chars <= 100_000:
            raise ValueError("Browser result bound is invalid")


@dataclass(frozen=True, slots=True)
class BrowserResult:
    final_url: str
    title: str
    text: str
    status_code: int

    def __post_init__(self) -> None:
        if len(self.final_url) > 2_048 or len(self.title) > 512 or len(self.text) > 100_000:
            raise ValueError("Browser result exceeds contract bounds")
        if not 100 <= self.status_code <= 599:
            raise ValueError("Browser status code is invalid")


@dataclass(frozen=True, slots=True)
class ComputerAction:
    kind: str
    x: int | None = None
    y: int | None = None
    text: str | None = None
    key: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"screenshot", "click", "type_text", "key"}:
            raise ValueError("Computer action is not supported")
        if self.kind == "click" and not (
            isinstance(self.x, int) and isinstance(self.y, int) and 0 <= self.x <= 32_767 and 0 <= self.y <= 32_767
        ):
            raise ValueError("Computer click coordinates are invalid")
        if self.kind == "type_text" and (
            not isinstance(self.text, str) or not self.text or len(self.text) > 4_096 or "\x00" in self.text
        ):
            raise ValueError("Computer text is invalid")
        if self.kind == "key" and (
            not isinstance(self.key, str) or not re.fullmatch(r"[A-Za-z0-9_+-]{1,32}", self.key)
        ):
            raise ValueError("Computer key is invalid")


@dataclass(frozen=True, slots=True)
class ComputerResult:
    kind: str
    completed: bool
    evidence: str

    def __post_init__(self) -> None:
        if self.kind not in {"screenshot", "click", "type_text", "key"}:
            raise ValueError("Computer result action is invalid")
        if not isinstance(self.completed, bool):
            raise ValueError("Computer result status is invalid")
        if not isinstance(self.evidence, str) or len(self.evidence) > 1_024:
            raise ValueError("Computer result evidence is invalid")


class BrowserAdapter(ABC):
    @abstractmethod
    def browse(self, request: BrowserRequest) -> BrowserResult:
        raise NotImplementedError


class ComputerAdapter(ABC):
    @abstractmethod
    def perform(self, action: ComputerAction) -> ComputerResult:
        raise NotImplementedError


class DisabledBrowserAdapter(BrowserAdapter):
    def browse(self, request: BrowserRequest) -> BrowserResult:
        raise InteractionUnavailableError("Browser execution is not configured in this environment")


class DisabledComputerAdapter(ComputerAdapter):
    def perform(self, action: ComputerAction) -> ComputerResult:
        raise InteractionUnavailableError("GUI computer execution is not configured in this environment")


class InteractionSessionStore(SQLiteStore):
    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "data_environment" / "interaction_sessions.sqlite3")
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS interaction_sessions(
                id TEXT PRIMARY KEY,mode TEXT NOT NULL,status TEXT NOT NULL,allowed_hosts_json TEXT NOT NULL,
                allowed_actions_json TEXT NOT NULL,expires_at REAL NOT NULL,revision INTEGER NOT NULL,
                created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS interaction_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,session_id TEXT NOT NULL,event TEXT NOT NULL,
                request_json TEXT NOT NULL,result_json TEXT NOT NULL,created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES interaction_sessions(id))""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_interaction_events ON interaction_events(session_id,id DESC)")


class InteractionService:
    """Provider-neutral browser/computer boundary with persistent operator-owned sessions."""

    COMPUTER_KINDS = {"screenshot", "click", "type_text", "key"}
    MAX_ACTIVE_SESSIONS = 500
    MAX_EVENTS_PER_SESSION = 5_000

    def __init__(
        self,
        browser: BrowserAdapter | None = None,
        computer: ComputerAdapter | None = None,
        session_store: InteractionSessionStore | None = None,
    ):
        self.browser = browser or DisabledBrowserAdapter()
        self.computer = computer or DisabledComputerAdapter()
        self.sessions = session_store or InteractionSessionStore()

    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)

    def browse(self, request: BrowserRequest) -> BrowserResult:
        result = self.browser.browse(request)
        try:
            parsed = urlsplit(result.final_url)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Browser result URL is invalid") from exc
        if (
            parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None
            or port not in {None, 443} or parsed.hostname.lower() not in tuple(host.lower() for host in request.allowed_hosts)
        ):
            raise ValueError("Browser result escaped the approved destination boundary")
        if len(result.text) > request.max_text_chars:
            raise ValueError("Browser result exceeds the request output limit")
        return result

    def perform(self, action: ComputerAction) -> ComputerResult:
        return self.computer.perform(action)

    def start_session(
        self, mode: str, *, ttl_seconds: int = 900,
        allowed_hosts: list[str] | None = None, allowed_actions: list[str] | None = None,
    ) -> dict[str, object]:
        if mode not in {"browser", "computer"}:
            raise InteractionSessionError("Interaction mode must be browser or computer")
        if type(ttl_seconds) is not int or not 30 <= ttl_seconds <= 86_400:
            raise InteractionSessionError("Session TTL must be 30-86400 seconds")
        hosts = sorted({str(host).lower() for host in (allowed_hosts or [])})
        actions = sorted(set(allowed_actions or []))
        if mode == "browser":
            if not hosts or len(hosts) > 32:
                raise InteractionSessionError("Browser sessions require 1-32 allowed hosts")
            BrowserRequest(f"https://{hosts[0]}/", tuple(hosts))
            if actions:
                raise InteractionSessionError("Browser sessions do not use computer action permissions")
        else:
            if hosts:
                raise InteractionSessionError("Computer sessions do not use browser hosts")
            if not actions or any(action not in self.COMPUTER_KINDS for action in actions):
                raise InteractionSessionError("Computer sessions require valid allowed actions")
        now = utc_now()
        with self.sessions.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            active = db.execute("SELECT count(*) FROM interaction_sessions WHERE status='active' AND expires_at>sparkle_now()").fetchone()[0]
            if active >= self.MAX_ACTIVE_SESSIONS:
                raise InteractionSessionError("Active interaction session limit reached")
            session_id = secrets.token_urlsafe(24)
            db.execute("INSERT INTO interaction_sessions VALUES(?,?,?,?,?,?,?,?,?)",
                       (session_id, mode, "active", self._json(hosts), self._json(actions), time.time() + ttl_seconds, 1, now, now))
        return self.session(session_id)

    def _raw_session(self, session_id: str):
        if not isinstance(session_id, str) or not 16 <= len(session_id) <= 128:
            raise InteractionSessionError("Invalid interaction session id")
        with self.sessions.connect() as db:
            row = db.execute("SELECT * FROM interaction_sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise InteractionSessionError("Unknown interaction session")
        return row

    def session(self, session_id: str) -> dict[str, object]:
        row = self._raw_session(session_id)
        if row["status"] == "active" and float(row["expires_at"]) <= time.time():
            now = utc_now()
            with self.sessions.connect() as db:
                db.execute("UPDATE interaction_sessions SET status='expired',revision=revision+1,updated_at=? WHERE id=? AND status='active'",
                           (now, session_id))
            row = self._raw_session(session_id)
        return {"id": row["id"], "mode": row["mode"], "status": row["status"],
                "allowed_hosts": json.loads(row["allowed_hosts_json"]), "allowed_actions": json.loads(row["allowed_actions_json"]),
                "expires_at": row["expires_at"], "revision": row["revision"], "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def _active(self, session_id: str, expected_revision: int) -> dict[str, object]:
        session = self.session(session_id)
        if session["status"] != "active":
            raise InteractionSessionError("Interaction session is not active")
        if type(expected_revision) is not int or session["revision"] != expected_revision:
            raise InteractionSessionError(f"Interaction session revision conflict: expected {expected_revision}, current {session['revision']}")
        return session

    def _record(self, session_id: str, event: str, request: object, result: object, expected_revision: int) -> int:
        now = utc_now()
        with self.sessions.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT count(*) FROM interaction_events WHERE session_id=?", (session_id,)).fetchone()[0]
            if count >= self.MAX_EVENTS_PER_SESSION:
                raise InteractionSessionError("Interaction event limit reached")
            cursor = db.execute("UPDATE interaction_sessions SET revision=revision+1,updated_at=? WHERE id=? AND status='active' AND revision=?",
                                (now, session_id, expected_revision))
            if cursor.rowcount != 1:
                raise InteractionSessionError("Interaction session changed concurrently")
            db.execute("INSERT INTO interaction_events(session_id,event,request_json,result_json,created_at) VALUES(?,?,?,?,?)",
                       (session_id, event, self._json(request), self._json(result), now))
        return expected_revision + 1

    def browse_session(self, session_id: str, url: str, *, expected_revision: int,
                       timeout_seconds: int = 15, max_text_chars: int = 20_000) -> dict[str, object]:
        session = self._active(session_id, expected_revision)
        if session["mode"] != "browser":
            raise InteractionSessionError("Session is not a browser session")
        request = BrowserRequest(url, tuple(session["allowed_hosts"]), timeout_seconds, max_text_chars)
        result = self.browse(request)
        output = {"final_url": result.final_url, "title": result.title, "text": result.text, "status_code": result.status_code}
        revision = self._record(session_id, "browse", {"url": url, "timeout_seconds": timeout_seconds, "max_text_chars": max_text_chars}, output, expected_revision)
        return output | {"session_revision": revision}

    def perform_session(self, session_id: str, action: dict[str, object], *, expected_revision: int) -> dict[str, object]:
        session = self._active(session_id, expected_revision)
        if session["mode"] != "computer":
            raise InteractionSessionError("Session is not a computer session")
        if not isinstance(action, dict) or set(action) - {"kind", "x", "y", "text", "key"}:
            raise InteractionSessionError("Computer action fields are invalid")
        kind = action.get("kind")
        if kind not in session["allowed_actions"]:
            raise InteractionSessionError("Computer action is not allowed in this session")
        request = ComputerAction(kind=str(kind), x=action.get("x"), y=action.get("y"), text=action.get("text"), key=action.get("key"))
        result = self.perform(request)
        output = {"kind": result.kind, "completed": result.completed, "evidence": result.evidence}
        revision = self._record(session_id, "computer_action", action, output, expected_revision)
        return output | {"session_revision": revision}

    def close_session(self, session_id: str, *, expected_revision: int) -> dict[str, object]:
        self._active(session_id, expected_revision)
        now = utc_now()
        with self.sessions.connect() as db:
            cursor = db.execute("UPDATE interaction_sessions SET status='closed',revision=revision+1,updated_at=? WHERE id=? AND status='active' AND revision=?",
                                (now, session_id, expected_revision))
            if cursor.rowcount != 1:
                raise InteractionSessionError("Interaction session changed concurrently")
        return self.session(session_id)

    def history(self, session_id: str, *, limit: int = 50) -> list[dict[str, object]]:
        self._raw_session(session_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise InteractionSessionError("History limit must be 1-100")
        with self.sessions.connect() as db:
            rows = db.execute("SELECT id,event,request_json,result_json,created_at FROM interaction_events WHERE session_id=? ORDER BY id DESC LIMIT ?",
                              (session_id, limit)).fetchall()
        return [{"id": row["id"], "event": row["event"], "request": json.loads(row["request_json"]),
                 "result": json.loads(row["result_json"]), "created_at": row["created_at"]} for row in rows]

    def status(self) -> dict[str, object]:
        browser_ready = not isinstance(self.browser, DisabledBrowserAdapter)
        computer_ready = not isinstance(self.computer, DisabledComputerAdapter)
        with self.sessions.connect() as db:
            active = db.execute("SELECT count(*) FROM interaction_sessions WHERE status='active' AND expires_at>sparkle_now()").fetchone()[0]
            total = db.execute("SELECT count(*) FROM interaction_sessions").fetchone()[0]
            events = db.execute("SELECT count(*) FROM interaction_events").fetchone()[0]
        return {
            "contract": "implemented",
            "session_lifecycle": "implemented",
            "browser": "configured" if browser_ready else "externally_unconfigured",
            "computer": "configured" if computer_ready else "externally_unconfigured",
            "active_sessions": active,
            "sessions": total,
            "events": events,
            "live_browser_verified": False,
            "live_computer_verified": False,
            "agent_tool_registered": False,
        }
