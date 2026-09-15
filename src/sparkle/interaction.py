from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import secrets
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from sparkle import __version__
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
            db.execute("""CREATE TABLE IF NOT EXISTS capability_acceptance(
                id TEXT PRIMARY KEY,capability TEXT NOT NULL,schema TEXT NOT NULL,
                checkset_version TEXT NOT NULL,sparkle_version TEXT NOT NULL,
                build_sha256 TEXT NOT NULL,adapter TEXT NOT NULL,approved_scope_sha256 TEXT NOT NULL,
                host_identity_sha256 TEXT NOT NULL,
                checks_json TEXT NOT NULL,started_at TEXT NOT NULL,completed_at TEXT NOT NULL,
                artifact_sha256 TEXT NOT NULL UNIQUE,artifact_ref TEXT NOT NULL,operator TEXT NOT NULL,
                expires_at REAL NOT NULL,created_at TEXT NOT NULL)""")
            acceptance_columns = {
                row["name"]
                for row in db.execute("PRAGMA table_info(capability_acceptance)")
            }
            if "host_identity_sha256" not in acceptance_columns:
                db.execute(
                    "ALTER TABLE capability_acceptance "
                    "ADD COLUMN host_identity_sha256 TEXT"
                )
            db.execute("""CREATE TABLE IF NOT EXISTS capability_acceptance_revocations(
                record_id TEXT PRIMARY KEY,operator TEXT NOT NULL,reason TEXT NOT NULL,
                revoked_at TEXT NOT NULL,FOREIGN KEY(record_id) REFERENCES capability_acceptance(id))""")
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_capability_acceptance "
                "ON capability_acceptance(capability,created_at DESC)"
            )


class InteractionService:
    """Provider-neutral browser/computer boundary with persistent operator-owned sessions."""

    COMPUTER_KINDS = {"screenshot", "click", "type_text", "key"}
    MAX_ACTIVE_SESSIONS = 500
    MAX_EVENTS_PER_SESSION = 5_000
    BROWSER_ACCEPTANCE_SCHEMA = "SPARKLE-BROWSER-ACCEPTANCE/1"
    BROWSER_ACCEPTANCE_CHECKSET = "safe-https-host-v1"
    BROWSER_ACCEPTANCE_ADAPTER = "sparkle.browser_runtime.SafeHTTPSBrowserAdapter"
    BROWSER_ACCEPTANCE_CHECKS = frozenset(
        {
            "public_https_success",
            "nonpublic_addresses_rejected",
            "tls_hostname_rejected",
            "redirect_revalidated",
            "output_bound_enforced",
            "persistent_session_lifecycle",
        }
    )
    BROWSER_ACCEPTANCE_HOSTS = (
        "127.0.0.1",
        "10.0.0.1",
        "192.0.2.1",
        "example.com",
        "httpbin.org",
        "wrong.host.badssl.com",
    )
    MAX_ACCEPTANCE_IMPORT_AGE_SECONDS = 86_400
    MAX_ACCEPTANCE_TTL_SECONDS = 90 * 86_400

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

    @classmethod
    def browser_build_sha256(cls) -> str:
        digest = hashlib.sha256()
        root = Path(__file__).resolve().parent
        for name in ("interaction.py", "browser_runtime.py", "interaction_cli.py"):
            digest.update(name.encode("utf-8"))
            digest.update(b"\0")
            digest.update((root / name).read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    @classmethod
    def browser_scope_sha256(cls) -> str:
        encoded = cls._json(list(cls.BROWSER_ACCEPTANCE_HOSTS)).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def browser_host_identity_sha256() -> str:
        prefix = b"SPARKLE-BROWSER-HOST/1\0"
        for location in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                raw = Path(location).read_text(encoding="ascii").strip().lower()
            except (OSError, UnicodeError):
                continue
            if re.fullmatch(r"[0-9a-f]{32}", raw):
                return hashlib.sha256(prefix + bytes.fromhex(raw)).hexdigest()
        if os.name == "nt":
            try:
                import winreg

                access = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Cryptography",
                    access=access,
                ) as key:
                    machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            except (ImportError, OSError):
                machine_guid = None
            if isinstance(machine_guid, str) and re.fullmatch(
                r"[0-9A-Fa-f-]{32,64}", machine_guid
            ):
                return hashlib.sha256(
                    prefix + machine_guid.lower().encode("ascii")
                ).hexdigest()
        node = platform.node().strip()
        if node:
            fallback = (
                platform.system().lower()
                + "\0"
                + node.lower()
                + "\0"
                + f"{uuid.getnode():012x}"
            ).encode("utf-8")
            return hashlib.sha256(prefix + fallback).hexdigest()
        raise InteractionSessionError(
            "Browser acceptance requires a stable host identity"
        )

    def _browser_adapter_identity(self) -> str:
        kind = type(self.browser)
        return f"{kind.__module__}.{kind.__qualname__}"

    @staticmethod
    def _acceptance_timestamp(raw: object, field: str) -> float:
        if not isinstance(raw, str) or not 10 <= len(raw) <= 64:
            raise InteractionSessionError(f"Browser acceptance {field} is invalid")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise InteractionSessionError(
                f"Browser acceptance {field} is invalid"
            ) from exc
        if parsed.tzinfo is None:
            raise InteractionSessionError(
                f"Browser acceptance {field} must include a timezone"
            )
        return parsed.timestamp()

    @staticmethod
    def _acceptance_operator(operator: object) -> str:
        if not isinstance(operator, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}", operator
        ):
            raise InteractionSessionError("Browser acceptance operator is invalid")
        return operator

    def record_browser_acceptance(
        self,
        evidence: dict[str, object],
        *,
        artifact_sha256: str,
        artifact_ref: str,
        operator: str,
        expires_at: float,
    ) -> dict[str, object]:
        required = {
            "schema",
            "capability",
            "checkset_version",
            "sparkle_version",
            "build_sha256",
            "adapter",
            "approved_hosts_sha256",
            "host_identity_sha256",
            "checks",
            "started_at",
            "completed_at",
            "passed",
        }
        allowed = required | {"failure_stage", "failure_reason"}
        if not isinstance(evidence, dict) or not required <= set(evidence) or set(evidence) - allowed:
            raise InteractionSessionError("Browser acceptance artifact fields are invalid")
        checks = evidence["checks"]
        if (
            evidence["schema"] != self.BROWSER_ACCEPTANCE_SCHEMA
            or evidence["capability"] != "browser"
            or evidence["checkset_version"] != self.BROWSER_ACCEPTANCE_CHECKSET
            or evidence["sparkle_version"] != __version__
            or evidence["build_sha256"] != self.browser_build_sha256()
            or evidence["adapter"] != self.BROWSER_ACCEPTANCE_ADAPTER
            or evidence["approved_hosts_sha256"] != self.browser_scope_sha256()
            or evidence["host_identity_sha256"] != self.browser_host_identity_sha256()
            or evidence["passed"] is not True
            or not isinstance(checks, dict)
            or set(checks) != self.BROWSER_ACCEPTANCE_CHECKS
            or any(value is not True for value in checks.values())
            or evidence.get("failure_stage") is not None
            or evidence.get("failure_reason") is not None
        ):
            raise InteractionSessionError(
                "Browser acceptance artifact does not match the current passing contract"
            )
        started = self._acceptance_timestamp(evidence["started_at"], "start time")
        completed = self._acceptance_timestamp(evidence["completed_at"], "completion time")
        now = time.time()
        if (
            completed < started
            or completed > now + 300
            or completed < now - self.MAX_ACCEPTANCE_IMPORT_AGE_SECONDS
        ):
            raise InteractionSessionError("Browser acceptance artifact is not current")
        if (
            isinstance(expires_at, bool)
            or not isinstance(expires_at, (int, float))
            or not now < float(expires_at) <= now + self.MAX_ACCEPTANCE_TTL_SECONDS
        ):
            raise InteractionSessionError("Browser acceptance expiry is invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
            raise InteractionSessionError("Browser acceptance artifact hash is invalid")
        if (
            not isinstance(artifact_ref, str)
            or not 1 <= len(artifact_ref) <= 2_048
            or any(char in artifact_ref for char in ("\0", "\n", "\r"))
        ):
            raise InteractionSessionError("Browser acceptance artifact reference is invalid")
        accepted_by = self._acceptance_operator(operator)
        record_id = secrets.token_urlsafe(18)
        created_at = utc_now()
        with self.sessions.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM capability_acceptance WHERE artifact_sha256=?",
                (artifact_sha256,),
            ).fetchone() is not None:
                raise InteractionSessionError(
                    "Browser acceptance artifact was already recorded"
                )
            db.execute(
                """INSERT INTO capability_acceptance(
                    id,capability,schema,checkset_version,sparkle_version,build_sha256,
                    adapter,approved_scope_sha256,host_identity_sha256,checks_json,
                    started_at,completed_at,
                    artifact_sha256,artifact_ref,operator,expires_at,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record_id,
                    "browser",
                    self.BROWSER_ACCEPTANCE_SCHEMA,
                    self.BROWSER_ACCEPTANCE_CHECKSET,
                    __version__,
                    self.browser_build_sha256(),
                    self.BROWSER_ACCEPTANCE_ADAPTER,
                    self.browser_scope_sha256(),
                    self.browser_host_identity_sha256(),
                    self._json(checks),
                    evidence["started_at"],
                    evidence["completed_at"],
                    artifact_sha256,
                    artifact_ref,
                    accepted_by,
                    float(expires_at),
                    created_at,
                ),
            )
        return self.browser_acceptance()

    def revoke_browser_acceptance(
        self, record_id: str, *, operator: str, reason: str
    ) -> dict[str, object]:
        if not isinstance(record_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{16,128}", record_id
        ):
            raise InteractionSessionError("Browser acceptance record id is invalid")
        revoked_by = self._acceptance_operator(operator)
        if (
            not isinstance(reason, str)
            or not 1 <= len(reason.strip()) <= 512
            or any(char in reason for char in ("\0", "\n", "\r"))
        ):
            raise InteractionSessionError("Browser acceptance revocation reason is invalid")
        with self.sessions.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT capability FROM capability_acceptance WHERE id=?", (record_id,)
            ).fetchone()
            if row is None or row["capability"] != "browser":
                raise InteractionSessionError("Unknown browser acceptance record")
            if db.execute(
                "SELECT 1 FROM capability_acceptance_revocations WHERE record_id=?",
                (record_id,),
            ).fetchone() is not None:
                raise InteractionSessionError(
                    "Browser acceptance record is already revoked"
                )
            db.execute(
                """INSERT INTO capability_acceptance_revocations(
                    record_id,operator,reason,revoked_at
                ) VALUES(?,?,?,?)""",
                (record_id, revoked_by, reason.strip(), utc_now()),
            )
        return self.browser_acceptance()

    def browser_acceptance(self) -> dict[str, object]:
        current_build = self.browser_build_sha256()
        current_adapter = self._browser_adapter_identity()
        with self.sessions.connect() as db:
            row = db.execute(
                """SELECT a.*,r.revoked_at
                FROM capability_acceptance a
                LEFT JOIN capability_acceptance_revocations r ON r.record_id=a.id
                WHERE a.capability='browser'
                ORDER BY a.created_at DESC,a.rowid DESC LIMIT 1"""
            ).fetchone()
        if row is None:
            return {
                "recorded": False,
                "verified": False,
                "reason": "no_acceptance_record",
                "record_id": None,
                "last_verified_at": None,
                "expires_at": None,
                "artifact_sha256": None,
                "build_sha256": current_build,
                "checkset_version": self.BROWSER_ACCEPTANCE_CHECKSET,
            }
        try:
            checks = json.loads(row["checks_json"])
        except (TypeError, json.JSONDecodeError):
            checks = {}
        revoked = row["revoked_at"] is not None
        expired = float(row["expires_at"]) <= time.time()
        valid_checks = (
            isinstance(checks, dict)
            and set(checks) == self.BROWSER_ACCEPTANCE_CHECKS
            and all(value is True for value in checks.values())
        )
        matches = (
            row["schema"] == self.BROWSER_ACCEPTANCE_SCHEMA
            and row["checkset_version"] == self.BROWSER_ACCEPTANCE_CHECKSET
            and row["sparkle_version"] == __version__
            and row["build_sha256"] == current_build
            and row["adapter"] == self.BROWSER_ACCEPTANCE_ADAPTER
            and row["approved_scope_sha256"] == self.browser_scope_sha256()
            and row["host_identity_sha256"] == self.browser_host_identity_sha256()
            and current_adapter == self.BROWSER_ACCEPTANCE_ADAPTER
            and valid_checks
        )
        verified = not revoked and not expired and matches
        if revoked:
            reason = "revoked"
        elif expired:
            reason = "expired"
        elif not matches:
            reason = "current_build_or_contract_mismatch"
        else:
            reason = "accepted"
        return {
            "recorded": True,
            "verified": verified,
            "reason": reason,
            "record_id": row["id"],
            "last_verified_at": row["completed_at"],
            "expires_at": row["expires_at"],
            "artifact_sha256": row["artifact_sha256"],
            "build_sha256": current_build,
            "checkset_version": self.BROWSER_ACCEPTANCE_CHECKSET,
        }

    def status(self) -> dict[str, object]:
        browser_ready = not isinstance(self.browser, DisabledBrowserAdapter)
        computer_ready = not isinstance(self.computer, DisabledComputerAdapter)
        with self.sessions.connect() as db:
            active = db.execute("SELECT count(*) FROM interaction_sessions WHERE status='active' AND expires_at>sparkle_now()").fetchone()[0]
            total = db.execute("SELECT count(*) FROM interaction_sessions").fetchone()[0]
            events = db.execute("SELECT count(*) FROM interaction_events").fetchone()[0]
        browser_acceptance = self.browser_acceptance()
        return {
            "contract": "implemented",
            "session_lifecycle": "implemented",
            "browser": "configured" if browser_ready else "externally_unconfigured",
            "browser_current_health": "not_probed",
            "browser_accepted": bool(browser_acceptance["verified"]),
            "browser_acceptance": browser_acceptance,
            "computer": "configured" if computer_ready else "externally_unconfigured",
            "active_sessions": active,
            "sessions": total,
            "events": events,
            "live_browser_verified": bool(browser_acceptance["verified"]),
            "live_computer_verified": False,
            "agent_tool_registered": False,
        }
