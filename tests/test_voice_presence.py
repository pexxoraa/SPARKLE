from __future__ import annotations

from datetime import datetime
import tempfile
import unittest
from pathlib import Path

from sparkle.presence import PresenceEngine
from sparkle.voice import (
    SpeechToText,
    TextToSpeech,
    VoiceService,
    VoiceSessionError,
    VoiceSessionStore,
    VoiceUnavailableError,
)


class DeterministicSpeechToText(SpeechToText):
    def __init__(self):
        self.received: tuple[bytes, str] | None = None

    def transcribe(self, audio: bytes, media_type: str) -> str:
        self.received = (audio, media_type)
        return "deterministic transcript"


class DeterministicTextToSpeech(TextToSpeech):
    def __init__(self):
        self.received: str | None = None

    def synthesize(self, text: str) -> tuple[bytes, str]:
        self.received = text
        return b"deterministic audio", "audio/wav"


class VoiceContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = VoiceSessionStore(Path(self.temp.name) / "voice.sqlite3")

    def test_default_voice_service_is_explicitly_unconfigured(self):
        service = VoiceService(session_store=self.store)
        status = service.status()
        self.assertEqual(status["stt"], "externally_unconfigured")
        self.assertEqual(status["tts"], "externally_unconfigured")
        self.assertEqual(status["session_lifecycle"], "implemented")
        self.assertFalse(status["live_stt_verified"])
        self.assertFalse(status["live_tts_verified"])
        with self.assertRaisesRegex(VoiceUnavailableError, "Speech-to-text is not configured"):
            service.stt.transcribe(b"audio", "audio/wav")
        with self.assertRaisesRegex(VoiceUnavailableError, "Text-to-speech is not configured"):
            service.tts.synthesize("hello")

    def test_session_stt_tts_lifecycle_persists_content_free_evidence(self):
        stt = DeterministicSpeechToText()
        tts = DeterministicTextToSpeech()
        service = VoiceService(stt=stt, tts=tts, session_store=self.store)
        session = service.start_session(ttl_seconds=60, language="en-US", voice="default")
        transcript = service.transcribe_session(session["id"], b"wave bytes", "audio/wav", expected_revision=1)
        self.assertEqual(transcript["text"], "deterministic transcript")
        self.assertEqual(transcript["session_revision"], 2)
        synthesis = service.synthesize_session(session["id"], "speak this", expected_revision=2)
        self.assertEqual(synthesis["audio"], b"deterministic audio")
        self.assertEqual(synthesis["session_revision"], 3)
        history = service.history(session["id"])
        self.assertEqual([item["direction"] for item in history], ["tts", "stt"])
        self.assertNotIn("wave bytes", str(history))
        self.assertNotIn("speak this", str(history))
        closed = service.close_session(session["id"], expected_revision=3)
        self.assertEqual(closed["status"], "closed")
        with self.assertRaisesRegex(VoiceSessionError, "not active"):
            service.synthesize_session(session["id"], "again", expected_revision=4)

    def test_session_revision_and_bounds_fail_closed(self):
        service = VoiceService(stt=DeterministicSpeechToText(), tts=DeterministicTextToSpeech(), session_store=self.store)
        session = service.start_session(ttl_seconds=60)
        service.transcribe_session(session["id"], b"audio", "audio/wav", expected_revision=1)
        with self.assertRaisesRegex(VoiceSessionError, "revision conflict"):
            service.transcribe_session(session["id"], b"audio", "audio/wav", expected_revision=1)
        with self.assertRaisesRegex(VoiceSessionError, "media type"):
            service.transcribe_session(session["id"], b"audio", "text/plain", expected_revision=2)
        with self.assertRaisesRegex(VoiceSessionError, "1-20000"):
            service.synthesize_session(session["id"], "", expected_revision=2)


class PresenceContractTests(unittest.TestCase):
    def test_initial_presence_state_is_bounded_to_interface_fields(self):
        status = PresenceEngine().status()
        self.assertEqual(set(status), {"mode", "activity", "agent", "trace_id", "updated_at"})
        self.assertEqual(status["mode"], "idle")
        self.assertEqual(status["activity"], "Ready")
        self.assertIsNone(status["agent"])
        self.assertIsNone(status["trace_id"])
        datetime.fromisoformat(str(status["updated_at"]))

    def test_presence_transition_preserves_agent_and_trace_linkage(self):
        presence = PresenceEngine()
        presence.update("working", "Researching evidence", agent="research", trace_id="SPK-2026-000001")
        status = presence.status()
        self.assertEqual(status["mode"], "working")
        self.assertEqual(status["activity"], "Researching evidence")
        self.assertEqual(status["agent"], "research")
        self.assertEqual(status["trace_id"], "SPK-2026-000001")
        datetime.fromisoformat(str(status["updated_at"]))


if __name__ == "__main__":
    unittest.main()
