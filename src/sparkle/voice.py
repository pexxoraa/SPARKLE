from __future__ import annotations

from abc import ABC, abstractmethod


class VoiceUnavailableError(RuntimeError):
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


class VoiceService:
    def __init__(self, stt: SpeechToText | None = None, tts: TextToSpeech | None = None):
        self.stt = stt or DisabledSpeechToText()
        self.tts = tts or DisabledTextToSpeech()

    def status(self) -> dict[str, str]:
        return {
            "stt": "disabled" if isinstance(self.stt, DisabledSpeechToText) else "ready",
            "tts": "disabled" if isinstance(self.tts, DisabledTextToSpeech) else "ready",
            "shared_context": "core_orchestrator",
        }
