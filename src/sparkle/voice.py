from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from sparkle.config import data_root
from sparkle.storage import SQLiteStore, utc_now


class VoiceUnavailableError(RuntimeError):
    pass


class VoiceSessionError(ValueError):
    pass


class SpeechToText(ABC):
    @abstractmethod
    def transcribe(self, audio: bytes, media_type: str) -> str:
        raise NotImplementedError


class TextToSpeech(ABC):
    @abstractmethod
    def synthesize(self, text: str) -> tuple[bytes, str]:
        raise NotImplementedError


class DisabledSpeechToText(SpeechToText):
    def transcribe(self, audio: bytes, media_type: str) -> str:
        raise VoiceUnavailableError("Speech-to-text is not configured in this environment")


class DisabledTextToSpeech(TextToSpeech):
    def synthesize(self, text: str) -> tuple[bytes, str]:
        raise VoiceUnavailableError("Text-to-speech is not configured in this environment")


class VoiceSessionStore(SQLiteStore):
    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "data_environment" / "voice_sessions.sqlite3")
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS voice_sessions(
                id TEXT PRIMARY KEY,status TEXT NOT NULL,language TEXT,voice TEXT,expires_at REAL NOT NULL,
                revision INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS voice_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,session_id TEXT NOT NULL,direction TEXT NOT NULL,
                media_type TEXT,bytes INTEGER,content_sha256 TEXT,text_chars INTEGER NOT NULL,
                result_text TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(session_id) REFERENCES voice_sessions(id))""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_voice_events ON voice_events(session_id,id DESC)")


class VoiceService:
    MEDIA_TYPE = re.compile(r"^audio/[A-Za-z0-9!#$&^_.+-]{1,127}$")
    MAX_AUDIO_BYTES = 8_000_000
    MAX_TEXT_CHARS = 20_000
    MAX_TRANSCRIPT_CHARS = 100_000
    MAX_ACTIVE_SESSIONS = 200
    MAX_EVENTS_PER_SESSION = 2_000

    def __init__(self, stt: SpeechToText | None = None, tts: TextToSpeech | None = None,
                 session_store: VoiceSessionStore | None = None):
        self.stt = stt or DisabledSpeechToText()
        self.tts = tts or DisabledTextToSpeech()
        self.sessions = session_store or VoiceSessionStore()

    def start_session(self, *, ttl_seconds: int = 1800, language: str | None = None,
                      voice: str | None = None) -> dict[str, Any]:
        if type(ttl_seconds) is not int or not 30 <= ttl_seconds <= 86_400:
            raise VoiceSessionError("Voice session TTL must be 30-86400 seconds")
        if language is not None and (not isinstance(language, str) or not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})?", language)):
            raise VoiceSessionError("Voice language tag is invalid")
        if voice is not None and (not isinstance(voice, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", voice)):
            raise VoiceSessionError("Voice identifier is invalid")
        now = utc_now()
        with self.sessions.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            active = db.execute("SELECT count(*) FROM voice_sessions WHERE status='active' AND expires_at>sparkle_now()").fetchone()[0]
            if active >= self.MAX_ACTIVE_SESSIONS:
                raise VoiceSessionError("Active voice session limit reached")
            session_id = secrets.token_urlsafe(24)
            db.execute("INSERT INTO voice_sessions VALUES(?,?,?,?,?,?,?,?)",
                       (session_id, "active", language, voice, time.time() + ttl_seconds, 1, now, now))
        return self.session(session_id)

    def _raw(self, session_id: str):
        if not isinstance(session_id, str) or not 16 <= len(session_id) <= 128:
            raise VoiceSessionError("Invalid voice session id")
        with self.sessions.connect() as db:
            row = db.execute("SELECT * FROM voice_sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise VoiceSessionError("Unknown voice session")
        return row

    def session(self, session_id: str) -> dict[str, Any]:
        row = self._raw(session_id)
        if row["status"] == "active" and float(row["expires_at"]) <= time.time():
            with self.sessions.connect() as db:
                db.execute("UPDATE voice_sessions SET status='expired',revision=revision+1,updated_at=? WHERE id=? AND status='active'",
                           (utc_now(), session_id))
            row = self._raw(session_id)
        return {"id": row["id"], "status": row["status"], "language": row["language"], "voice": row["voice"],
                "expires_at": row["expires_at"], "revision": row["revision"], "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def _active(self, session_id: str, expected_revision: int) -> dict[str, Any]:
        session = self.session(session_id)
        if session["status"] != "active":
            raise VoiceSessionError("Voice session is not active")
        if type(expected_revision) is not int or session["revision"] != expected_revision:
            raise VoiceSessionError(f"Voice session revision conflict: expected {expected_revision}, current {session['revision']}")
        return session

    def _record(self, session_id: str, *, expected_revision: int, direction: str, media_type: str | None,
                payload: bytes | None, input_text: str, result_text: str) -> int:
        now = utc_now()
        with self.sessions.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT count(*) FROM voice_events WHERE session_id=?", (session_id,)).fetchone()[0]
            if count >= self.MAX_EVENTS_PER_SESSION:
                raise VoiceSessionError("Voice event limit reached")
            cursor = db.execute("UPDATE voice_sessions SET revision=revision+1,updated_at=? WHERE id=? AND status='active' AND revision=?",
                                (now, session_id, expected_revision))
            if cursor.rowcount != 1:
                raise VoiceSessionError("Voice session changed concurrently")
            digest = hashlib.sha256(payload).hexdigest() if payload is not None else None
            db.execute("INSERT INTO voice_events(session_id,direction,media_type,bytes,content_sha256,text_chars,result_text,created_at) VALUES(?,?,?,?,?,?,?,?)",
                       (session_id, direction, media_type, len(payload) if payload is not None else None, digest,
                        len(input_text), result_text[:1000], now))
        return expected_revision + 1

    def transcribe_session(self, session_id: str, audio: bytes, media_type: str, *, expected_revision: int) -> dict[str, Any]:
        self._active(session_id, expected_revision)
        if not isinstance(audio, bytes) or not audio or len(audio) > self.MAX_AUDIO_BYTES:
            raise VoiceSessionError("Voice audio must contain 1-8000000 bytes")
        if not isinstance(media_type, str) or not self.MEDIA_TYPE.fullmatch(media_type):
            raise VoiceSessionError("Voice media type is invalid")
        transcript = self.stt.transcribe(audio, media_type)
        if not isinstance(transcript, str) or len(transcript) > self.MAX_TRANSCRIPT_CHARS:
            raise VoiceSessionError("Speech transcript violates output bounds")
        revision = self._record(session_id, expected_revision=expected_revision, direction="stt", media_type=media_type,
                                payload=audio, input_text="", result_text=transcript)
        return {"text": transcript, "session_revision": revision,
                "audio_sha256": hashlib.sha256(audio).hexdigest(), "audio_bytes": len(audio), "media_type": media_type}

    def synthesize_session(self, session_id: str, text: str, *, expected_revision: int) -> dict[str, Any]:
        self._active(session_id, expected_revision)
        if not isinstance(text, str) or not text.strip() or len(text) > self.MAX_TEXT_CHARS:
            raise VoiceSessionError("Speech synthesis text must contain 1-20000 characters")
        audio, media_type = self.tts.synthesize(text)
        if not isinstance(audio, bytes) or not audio or len(audio) > self.MAX_AUDIO_BYTES:
            raise VoiceSessionError("Speech synthesis audio violates output bounds")
        if not isinstance(media_type, str) or not self.MEDIA_TYPE.fullmatch(media_type):
            raise VoiceSessionError("Speech synthesis media type is invalid")
        revision = self._record(session_id, expected_revision=expected_revision, direction="tts", media_type=media_type,
                                payload=audio, input_text=text, result_text="")
        return {"audio": audio, "media_type": media_type, "audio_sha256": hashlib.sha256(audio).hexdigest(),
                "audio_bytes": len(audio), "session_revision": revision}

    def close_session(self, session_id: str, *, expected_revision: int) -> dict[str, Any]:
        self._active(session_id, expected_revision)
        now = utc_now()
        with self.sessions.connect() as db:
            cursor = db.execute("UPDATE voice_sessions SET status='closed',revision=revision+1,updated_at=? WHERE id=? AND status='active' AND revision=?",
                                (now, session_id, expected_revision))
            if cursor.rowcount != 1:
                raise VoiceSessionError("Voice session changed concurrently")
        return self.session(session_id)

    def history(self, session_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        self._raw(session_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise VoiceSessionError("Voice history limit must be 1-100")
        with self.sessions.connect() as db:
            rows = db.execute("SELECT id,direction,media_type,bytes,content_sha256,text_chars,result_text,created_at FROM voice_events WHERE session_id=? ORDER BY id DESC LIMIT ?",
                              (session_id, limit)).fetchall()
        return [dict(row) for row in rows]

    def status(self) -> dict[str, Any]:
        with self.sessions.connect() as db:
            active = db.execute("SELECT count(*) FROM voice_sessions WHERE status='active' AND expires_at>sparkle_now()").fetchone()[0]
            total = db.execute("SELECT count(*) FROM voice_sessions").fetchone()[0]
            events = db.execute("SELECT count(*) FROM voice_events").fetchone()[0]
        return {
            "stt": "externally_unconfigured" if isinstance(self.stt, DisabledSpeechToText) else "configured",
            "tts": "externally_unconfigured" if isinstance(self.tts, DisabledTextToSpeech) else "configured",
            "session_lifecycle": "implemented",
            "active_sessions": active,
            "sessions": total,
            "events": events,
            "shared_context": "core_orchestrator",
            "live_stt_verified": False,
            "live_tts_verified": False,
        }
