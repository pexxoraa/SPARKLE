from __future__ import annotations

import unittest

from sparkle.content import ContentEnvelope, ContentPart
from sparkle.contracts import Message
from sparkle.model import ModelError
from sparkle.providers.nvidia import NVIDIAChatCompletionsAdapter


class NVIDIAMultimodalTransportTests(unittest.TestCase):
    def test_user_image_serializes_to_openai_compatible_data_url(self):
        envelope = ContentEnvelope([
            ContentPart.text("Describe the image."),
            ContentPart.binary(
                "image", b"fake-png-bytes", media_type="image/png"
            ),
        ])
        message = Message(role="user", content=envelope)

        payload = NVIDIAChatCompletionsAdapter._message(message)

        self.assertEqual(payload["role"], "user")
        self.assertEqual(
            payload["content"][0],
            {"type": "text", "text": "Describe the image."},
        )
        image = payload["content"][1]
        self.assertEqual(image["type"], "image_url")
        self.assertTrue(
            image["image_url"]["url"].startswith(
                "data:image/png;base64,"
            )
        )
        self.assertIn("image", NVIDIAChatCompletionsAdapter.supported_modalities)

    def test_unsupported_image_media_type_fails_before_provider_request(self):
        envelope = ContentEnvelope([
            ContentPart.binary(
                "image", b"fake-webp-bytes", media_type="image/webp"
            ),
        ])
        with self.assertRaisesRegex(ModelError, "media type is unsupported"):
            NVIDIAChatCompletionsAdapter._message(
                Message(role="user", content=envelope)
            )

    def test_audio_is_not_silently_flattened_to_text(self):
        envelope = ContentEnvelope([
            ContentPart.binary(
                "audio", b"fake-audio-bytes", media_type="audio/wav"
            ),
        ])
        with self.assertRaisesRegex(ModelError, "cannot serialize"):
            NVIDIAChatCompletionsAdapter._message(
                Message(role="user", content=envelope)
            )

    def test_non_user_binary_content_is_rejected(self):
        envelope = ContentEnvelope([
            ContentPart.binary(
                "image", b"fake-png-bytes", media_type="image/png"
            ),
        ])
        with self.assertRaisesRegex(ModelError, "only in user messages"):
            NVIDIAChatCompletionsAdapter._message(
                Message(role="assistant", content=envelope)
            )


if __name__ == "__main__":
    unittest.main()
