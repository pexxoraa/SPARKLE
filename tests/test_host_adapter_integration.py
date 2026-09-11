from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from sparkle.config import AppConfig
from sparkle.interaction import ComputerAction, ComputerAdapter, ComputerResult
from sparkle.presence import MotionAdapter, MotionCommand, MotionResult
from sparkle.providers.mock import DeterministicAdapter
from sparkle.registry import ModelRegistry
from sparkle.system import SparkleSystem
from sparkle.voice import SpeechToText, TextToSpeech


def test_config() -> AppConfig:
    return AppConfig("127.0.0.1", 0, 4, 5, 5, False, False)


class StubSTT(SpeechToText):
    def transcribe(self, audio: bytes, media_type: str) -> str:
        return "stub transcript"


class StubTTS(TextToSpeech):
    def synthesize(self, text: str) -> tuple[bytes, str]:
        return b"stub audio", "audio/wav"


class StubComputer(ComputerAdapter):
    def perform(self, action: ComputerAction) -> ComputerResult:
        return ComputerResult(action.kind, True, "stub host evidence")


class StubMotion(MotionAdapter):
    def capabilities(self) -> set[str]:
        return {"wave"}

    def execute(self, command: MotionCommand) -> MotionResult:
        return MotionResult(True, "stub motion evidence")


class HostAdapterIntegrationTests(unittest.TestCase):
    def test_system_accepts_external_host_adapters_without_core_patch(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False
        ):
            registry = ModelRegistry()
            registry.inject(registry.active_id, DeterministicAdapter())
            stt = StubSTT()
            tts = StubTTS()
            computer = StubComputer()
            motion = StubMotion()
            system = SparkleSystem(
                config=test_config(),
                model_registry=registry,
                speech_to_text=stt,
                text_to_speech=tts,
                computer_adapter=computer,
                motion_adapter=motion,
            )

            self.assertIs(system.voice.stt, stt)
            self.assertIs(system.voice.tts, tts)
            self.assertIs(system.interactions.computer, computer)
            self.assertIs(system.presence.motion, motion)
            self.assertEqual(system.voice.status()["stt"], "configured")
            self.assertEqual(system.voice.status()["tts"], "configured")
            self.assertEqual(system.interactions.status()["computer"], "configured")
            self.assertEqual(system.presence.status()["motion"], "configured")
            self.assertEqual(system.presence.status()["motion_capabilities"], ["wave"])
            self.assertFalse(system.voice.status()["live_stt_verified"])
            self.assertFalse(system.voice.status()["live_tts_verified"])
            self.assertFalse(system.interactions.status()["live_computer_verified"])
            self.assertFalse(system.presence.status()["live_motion_verified"])


if __name__ == "__main__":
    unittest.main()
