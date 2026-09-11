from __future__ import annotations

import json
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sparkle.config import data_root
from sparkle.storage import SQLiteStore, utc_now


class MotionUnavailableError(RuntimeError):
    pass


class MotionValidationError(ValueError):
    pass


@dataclass(slots=True)
class PresenceState:
    mode: str = "idle"
    activity: str = "Ready"
    agent: str | None = None
    trace_id: str | None = None
    updated_at: str = ""


@dataclass(frozen=True, slots=True)
class MotionCommand:
    kind: str
    parameters: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", self.kind):
            raise MotionValidationError("Motion command kind is invalid")
        if not isinstance(self.parameters, dict):
            raise MotionValidationError("Motion parameters must be an object")
        encoded = json.dumps(self.parameters, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(encoded.encode("utf-8")) > 8_192:
            raise MotionValidationError("Motion parameters exceed 8 KB")


@dataclass(frozen=True, slots=True)
class MotionResult:
    completed: bool
    evidence: str

    def __post_init__(self) -> None:
        if not isinstance(self.completed, bool):
            raise MotionValidationError("Motion completion status is invalid")
        if not isinstance(self.evidence, str) or len(self.evidence) > 2_000:
            raise MotionValidationError("Motion evidence is invalid")


class MotionAdapter(ABC):
    @abstractmethod
    def capabilities(self) -> set[str]:
        raise NotImplementedError

    @abstractmethod
    def execute(self, command: MotionCommand) -> MotionResult:
        raise NotImplementedError


class DisabledMotionAdapter(MotionAdapter):
    def capabilities(self) -> set[str]:
        return set()

    def execute(self, command: MotionCommand) -> MotionResult:
        raise MotionUnavailableError("Physical motion adapter is not configured")


class PresenceStore(SQLiteStore):
    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "data_environment" / "presence.sqlite3")
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS presence_state(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),mode TEXT NOT NULL,activity TEXT NOT NULL,
                agent TEXT,trace_id TEXT,updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS presence_history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,mode TEXT NOT NULL,activity TEXT NOT NULL,
                agent TEXT,trace_id TEXT,updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS motion_events(
                id TEXT PRIMARY KEY,kind TEXT NOT NULL,parameters_json TEXT NOT NULL,
                completed INTEGER NOT NULL,evidence TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL)""")


class PresenceEngine:
    """Durable embodiment-neutral presence and operator-owned motion adapter boundary."""

    MODES = {"idle", "listening", "thinking", "working", "speaking", "error", "offline"}
    MAX_HISTORY = 10_000

    def __init__(self, store: PresenceStore | None = None, motion: MotionAdapter | None = None):
        self.store = store or PresenceStore()
        self.motion = motion or DisabledMotionAdapter()
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM presence_state WHERE singleton=1").fetchone()
            if row is None:
                now = utc_now()
                db.execute("INSERT INTO presence_state VALUES(1,'idle','Ready',NULL,NULL,?)", (now,))
                db.execute("INSERT INTO presence_history(mode,activity,agent,trace_id,updated_at) VALUES('idle','Ready',NULL,NULL,?)", (now,))
        self.state = self._load()

    def _load(self) -> PresenceState:
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM presence_state WHERE singleton=1").fetchone()
        return PresenceState(row["mode"], row["activity"], row["agent"], row["trace_id"], row["updated_at"])

    @staticmethod
    def _optional_identifier(value: str | None, field: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 128:
            raise MotionValidationError(f"Presence {field} is invalid")
        return value.strip()

    def update(self, mode: str, activity: str, *, agent: str | None = None, trace_id: str | None = None) -> None:
        if mode not in self.MODES:
            raise MotionValidationError("Presence mode is invalid")
        if not isinstance(activity, str) or not activity.strip() or len(activity.strip()) > 500:
            raise MotionValidationError("Presence activity is invalid")
        agent = self._optional_identifier(agent, "agent")
        trace_id = self._optional_identifier(trace_id, "trace_id")
        now = utc_now()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE presence_state SET mode=?,activity=?,agent=?,trace_id=?,updated_at=? WHERE singleton=1",
                       (mode, activity.strip(), agent, trace_id, now))
            db.execute("INSERT INTO presence_history(mode,activity,agent,trace_id,updated_at) VALUES(?,?,?,?,?)",
                       (mode, activity.strip(), agent, trace_id, now))
            count = db.execute("SELECT count(*) FROM presence_history").fetchone()[0]
            if count > self.MAX_HISTORY:
                db.execute("DELETE FROM presence_history WHERE id IN (SELECT id FROM presence_history ORDER BY id ASC LIMIT ?)",
                           (count - self.MAX_HISTORY,))
        self.state = PresenceState(mode, activity.strip(), agent, trace_id, now)

    def status(self) -> dict[str, Any]:
        self.state = self._load()
        return asdict(self.state) | {
            "persistent": True,
            "motion": "externally_unconfigured" if isinstance(self.motion, DisabledMotionAdapter) else "configured",
            "motion_capabilities": sorted(self.motion.capabilities()),
            "live_motion_verified": False,
        }

    def history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise MotionValidationError("Presence history limit must be 1-100")
        with self.store.connect() as db:
            rows = db.execute("SELECT mode,activity,agent,trace_id,updated_at FROM presence_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def execute_motion(self, command: MotionCommand, *, approved: bool, actor: str = "operator") -> dict[str, Any]:
        if approved is not True:
            raise MotionValidationError("Physical motion requires explicit operator approval")
        if command.kind not in self.motion.capabilities():
            raise MotionUnavailableError("Motion command is not supported by the configured adapter")
        if not isinstance(actor, str) or not actor.strip() or len(actor.strip()) > 80:
            raise MotionValidationError("Motion actor identity is invalid")
        result = self.motion.execute(command)
        event_id = f"SPK-MOTION-{uuid.uuid4().hex.upper()}"
        now = utc_now()
        with self.store.connect() as db:
            db.execute("INSERT INTO motion_events VALUES(?,?,?,?,?,?,?)", (
                event_id, command.kind,
                json.dumps(command.parameters, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False),
                int(result.completed), result.evidence, actor.strip(), now,
            ))
        return {"event_id": event_id, "kind": command.kind, "completed": result.completed,
                "evidence": result.evidence, "created_at": now, "hardware_verified": False}
