from __future__ import annotations

from datetime import datetime
import unittest

from sparkle.presence import PresenceEngine
from sparkle.voice import (
    SpeechToText,
    TextToSpeech,
    VoiceService,
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
    def test_default_voice_service_is_explicitly_disabled(self):
        service = VoiceService()
        self.assertEqual(
            service.status(),
            {
                "stt": "disabled",
                "tts": "disabled",
                "shared_context": "core_orchestrator",
            },
        )
        with self.assertRaisesRegex(
            VoiceUnavailableError, "Speech-to-text is not configured",
        ):
            service.stt.transcribe(b"audio", "audio/wav")
        with self.assertRaisesRegex(
            VoiceUnavailableError, "Text-to-speech is not configured",
        ):
            service.tts.synthesize("hello")

    def test_injected_voice_adapters_preserve_provider_neutral_contracts(self):
        stt = DeterministicSpeechToText()
        tts = DeterministicTextToSpeech()
        service = VoiceService(stt=stt, tts=tts)

        self.assertEqual(
            service.status(),
            {
                "stt": "ready",
                "tts": "ready",
                "shared_context": "core_orchestrator",
            },
        )
        self.assertEqual(
            service.stt.transcribe(b"wave bytes", "audio/wav"),
            "deterministic transcript",
        )
        self.assertEqual(stt.received, (b"wave bytes", "audio/wav"))
        self.assertEqual(
            service.tts.synthesize("speak this"),
            (b"deterministic audio", "audio/wav"),
        )
        self.assertEqual(tts.received, "speak this")


class PresenceContractTests(unittest.TestCase):
    def test_initial_presence_state_is_bounded_to_interface_fields(self):
        status = PresenceEngine().status()
        self.assertEqual(
            set(status),
            {"mode", "activity", "agent", "trace_id", "updated_at"},
        )
        self.assertEqual(status["mode"], "idle")
        self.assertEqual(status["activity"], "Ready")
        self.assertIsNone(status["agent"])
        self.assertIsNone(status["trace_id"])
        datetime.fromisoformat(str(status["updated_at"]))

    def test_presence_transition_preserves_agent_and_trace_linkage(self):
        presence = PresenceEngine()
        presence.update(
            "working", "Researching evidence",
            agent="research", trace_id="SPK-2026-000001",
        )
        status = presence.status()
        self.assertEqual(status["mode"], "working")
        self.assertEqual(status["activity"], "Researching evidence")
        self.assertEqual(status["agent"], "research")
        self.assertEqual(status["trace_id"], "SPK-2026-000001")
        datetime.fromisoformat(str(status["updated_at"]))


if __name__ == "__main__":
    unittest.main()
