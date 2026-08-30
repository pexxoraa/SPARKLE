from __future__ import annotations

import base64
import json
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from sparkle.api import SparkleHandler
from sparkle.config import AppConfig
from sparkle.content import (
    CONTENT_PROTOCOL,
    MAX_CONTENT_PARTS,
    MAX_PART_BYTES,
    ContentEnvelope,
    ContentPart,
    ContentValidationError,
)
from sparkle.contracts import Message, ModelRequest
from sparkle.model import UnsupportedModalityError
from sparkle.providers.minimax import MiniMaxMessagesAdapter
from sparkle.providers.mock import DeterministicAdapter
from sparkle.registry import ModelRegistry, ModelRouter
from sparkle.secrets import SecretResolver
from sparkle.system import SparkleSystem
from sparkle.trace import TraceStore


def test_config() -> AppConfig:
    return AppConfig("127.0.0.1", 0, 4, 5, 5, False, False)


def envelope(*parts: ContentPart) -> ContentEnvelope:
    return ContentEnvelope(list(parts))


class CapturingAdapter(DeterministicAdapter):
    def complete(self, request: ModelRequest):
        self.last_request = request
        return super().complete(request)


class ContentContractTests(unittest.TestCase):
    def test_legacy_text_message_remains_byte_for_byte_compatible(self):
        message = Message("user", "Teach Python")
        self.assertEqual(
            message.to_dict(), {"role": "user", "content": "Teach Python"},
        )
        restored = Message.from_dict(message.to_dict())
        self.assertIsInstance(restored.content, str)
        self.assertEqual(restored.content, "Teach Python")
        self.assertEqual(restored.modalities, ["text"])
        self.assertEqual(restored.content_identifiers, [])

    def test_image_audio_and_document_parts_are_explicit_and_bounded(self):
        image = ContentPart.binary(
            "image", b"\x89PNG\r\n", media_type="image/png",
            metadata={"height": 1, "width": 1},
        )
        audio = ContentPart.binary(
            "audio", b"RIFF-audio", media_type="audio/wav",
            metadata={"duration_ms": 20},
        )
        document = ContentPart.binary(
            "document", b"%PDF-document", media_type="application/pdf",
            metadata={"filename": "notes.pdf", "page_count": 1},
        )
        self.assertEqual(image.decoded_bytes(), b"\x89PNG\r\n")
        self.assertEqual(audio.type, "audio")
        self.assertEqual(document.media_type, "application/pdf")
        self.assertRegex(str(image.content_id), r"^spk-sha256:[0-9a-f]{64}$")
        self.assertNotIn(image.data, json.dumps(image.trace_dict()))

    def test_mixed_round_trip_and_serialization_are_deterministic(self):
        value = envelope(
            ContentPart.text("Compare these inputs", metadata={"language": "en"}),
            ContentPart.binary(
                "image", b"image", media_type="image/png",
                metadata={"width": 2, "height": 1},
            ),
            ContentPart.binary(
                "document", b"document", media_type="text/markdown",
                metadata={"filename": "notes.md"},
            ),
        )
        first = value.canonical_json()
        restored = ContentEnvelope.from_dict(json.loads(first))
        self.assertEqual(restored.canonical_json(), first)
        self.assertEqual(restored.modalities, ["text", "image", "document"])
        self.assertEqual(restored.text_content, "Compare these inputs")
        self.assertEqual(restored.to_dict(), value.to_dict())

    def test_rejects_empty_unsupported_and_malformed_content(self):
        invalid = [
            lambda: ContentEnvelope([]),
            lambda: ContentPart.text("   "),
            lambda: ContentPart("video", "data", "video/mp4", "base64"),
            lambda: ContentPart("image", "%%%", "image/png", "base64"),
            lambda: ContentPart("image", base64.b64encode(b"x").decode(), "audio/wav", "base64"),
            lambda: ContentPart.text("x", content_id="caller-controlled"),
            lambda: ContentEnvelope.from_dict({"protocol_version": "future", "parts": []}),
            lambda: ContentPart.from_dict({"type": "text", "data": "x", "extra": True}),
            lambda: Message.from_dict({"role": "user", "content": 12}),
        ]
        for operation in invalid:
            with self.subTest(operation=operation):
                with self.assertRaises(ContentValidationError):
                    operation()

    def test_rejects_oversized_parts_envelopes_and_duplicate_identifiers(self):
        with self.assertRaises(ContentValidationError):
            ContentPart.text("x" * (MAX_PART_BYTES["text"] + 1))
        too_many = [ContentPart.text(f"part-{index}") for index in range(MAX_CONTENT_PARTS + 1)]
        with self.assertRaises(ContentValidationError):
            ContentEnvelope(too_many)
        duplicate = ContentPart.text("same")
        with self.assertRaises(ContentValidationError):
            ContentEnvelope([duplicate, ContentPart.text("same")])
        with patch("sparkle.content.MAX_TOTAL_CONTENT_BYTES", 8):
            with self.assertRaises(ContentValidationError):
                ContentEnvelope([
                    ContentPart.binary("audio", b"12345", media_type="audio/wav"),
                    ContentPart.binary("document", b"6789", media_type="application/pdf"),
                ])

    def test_rejects_invalid_or_sensitive_metadata(self):
        invalid_metadata = [
            [],
            {"bad key": "value"},
            {"api_key": "secret"},
            {"score": float("nan")},
            {"value": {"a": {"b": {"c": {"d": {"e": 1}}}}}},
            {"value": {1, 2}},
        ]
        for metadata in invalid_metadata:
            with self.subTest(metadata=metadata):
                with self.assertRaises(ContentValidationError):
                    ContentPart("text", "valid", metadata=metadata)  # type: ignore[arg-type]

    def test_exact_part_and_total_boundaries_are_accepted(self):
        text = ContentPart.text("x" * MAX_PART_BYTES["text"])
        self.assertEqual(text.size_bytes, MAX_PART_BYTES["text"])
        with patch("sparkle.content.MAX_TOTAL_CONTENT_BYTES", text.size_bytes):
            self.assertEqual(ContentEnvelope([text]).total_bytes, text.size_bytes)

    def test_model_request_has_message_and_aggregate_content_bounds(self):
        with patch("sparkle.contracts.MAX_REQUEST_MESSAGES", 1):
            with self.assertRaises(ContentValidationError):
                ModelRequest(messages=[Message("user", "one"), Message("assistant", "two")])
        with patch("sparkle.contracts.MAX_REQUEST_CONTENT_BYTES", 8):
            with self.assertRaises(ContentValidationError):
                ModelRequest(messages=[Message("user", "12345"), Message("assistant", "6789")])
        with self.assertRaises(ContentValidationError):
            ModelRequest(messages=[])


class MultimodalSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {"SPARKLE_DATA_DIR": self.temp.name}, clear=False,
        )
        self.environment.start()
        self.registry = ModelRegistry()
        self.adapter = CapturingAdapter()
        self.registry.inject(self.registry.active_id, self.adapter)
        self.system = SparkleSystem(
            config=test_config(), model_registry=self.registry,
        )

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    @staticmethod
    def mixed_content() -> ContentEnvelope:
        return envelope(
            ContentPart.text("Inspect the supplied evidence"),
            ContentPart.binary(
                "image", b"PRIVATE-IMAGE-BYTES", media_type="image/png",
                metadata={"width": 10, "height": 10},
            ),
            ContentPart.binary(
                "audio", b"PRIVATE-AUDIO-BYTES", media_type="audio/wav",
                metadata={"duration_ms": 100},
            ),
            ContentPart.binary(
                "document", b"PRIVATE-DOCUMENT-BYTES", media_type="application/pdf",
                metadata={"filename": "evidence.pdf"},
            ),
        )

    def test_mixed_content_flows_through_orchestrator_adapter_and_trace(self):
        content = self.mixed_content()
        result = self.system.orchestrator.run(content=content, agent_name="research")
        self.assertEqual(
            result.input_modalities, ["text", "image", "audio", "document"],
        )
        self.assertEqual(result.output_modalities, ["text"])
        self.assertEqual(result.content_identifiers, content.content_identifiers)
        latest = self.adapter.last_request.messages[-1]
        self.assertIsInstance(latest.content, ContentEnvelope)
        self.assertEqual(latest.content.canonical_json(), content.canonical_json())
        trace = self.system.traces.recent()[0]
        self.assertEqual(trace["input_modalities"], result.input_modalities)
        self.assertEqual(trace["content_identifiers"], content.content_identifiers)
        self.assertEqual(trace["processing_stage"], "completed")
        self.assertEqual(trace["output_modalities"], ["text"])
        self.assertIn("content_validation", trace["transformations"])
        serialized_trace = json.dumps(trace)
        for raw in (
            "PRIVATE-IMAGE-BYTES", "PRIVATE-AUDIO-BYTES",
            "PRIVATE-DOCUMENT-BYTES",
            content.parts[1].data, content.parts[2].data, content.parts[3].data,
        ):
            self.assertNotIn(raw, serialized_trace)

    def test_image_only_text_image_and_text_document_requests_execute(self):
        image_result = self.system.orchestrator.run(
            content=envelope(ContentPart.binary(
                "image", b"pixels", media_type="image/png",
            )),
            agent_name="research",
        )
        self.assertEqual(image_result.input_modalities, ["image"])
        text_image_result = self.system.orchestrator.run(
            content=envelope(
                ContentPart.text("Describe"),
                ContentPart.binary(
                    "image", b"pixels-two", media_type="image/png",
                ),
            ),
            agent_name="research",
        )
        self.assertEqual(text_image_result.input_modalities, ["text", "image"])
        document_result = self.system.orchestrator.run(
            content=envelope(
                ContentPart.text("Summarize"),
                ContentPart.binary(
                    "document", b"notes", media_type="text/plain",
                ),
            ),
            agent_name="research",
        )
        self.assertEqual(document_result.input_modalities, ["text", "document"])

    def test_legacy_text_path_and_trace_transformations_remain_compatible(self):
        result = self.system.orchestrator.run(
            "Teach Python", agent_name="learning",
        )
        self.assertEqual(result.text, "SPARKLE processed: Teach Python")
        self.assertEqual(self.adapter.last_request.messages[-1].content, "Teach Python")
        trace = self.system.traces.recent()[0]
        self.assertEqual(trace["input_source"], "text")
        self.assertEqual(trace["input_modalities"], ["text"])
        self.assertEqual(trace["content_identifiers"], [])
        self.assertNotIn("content_validation", trace["transformations"])

    def test_text_only_model_fails_closed_and_records_safe_trace(self):
        text_only = DeterministicAdapter()
        text_only.supported_modalities = frozenset({"text"})
        self.registry.inject(self.registry.active_id, text_only)
        content = envelope(ContentPart.binary(
            "image", b"SECRET-PIXELS", media_type="image/png",
        ))
        with self.assertRaises(UnsupportedModalityError):
            self.system.orchestrator.run(content=content, agent_name="research")
        trace = self.system.traces.recent()[0]
        self.assertEqual(trace["status"], "failure")
        self.assertEqual(trace["error_type"], "UnsupportedModalityError")
        self.assertEqual(trace["processing_stage"], "failed")
        self.assertEqual(trace["model"], text_only.model_id)
        self.assertEqual(trace["provider"], text_only.provider)
        self.assertNotIn("SECRET-PIXELS", json.dumps(trace))

    def test_legacy_trace_schema_is_migrated(self):
        path = Path(self.temp.name) / "legacy-traces.sqlite3"
        with sqlite3.connect(path) as connection:
            connection.execute("""
                CREATE TABLE traces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT UNIQUE,
                    year INTEGER NOT NULL,
                    year_sequence INTEGER NOT NULL,
                    input_source TEXT NOT NULL,
                    agent TEXT,
                    model TEXT,
                    provider TEXT,
                    tools TEXT NOT NULL DEFAULT '[]',
                    data_accessed TEXT NOT NULL DEFAULT '[]',
                    data_created TEXT NOT NULL DEFAULT '[]',
                    transformations TEXT NOT NULL DEFAULT '[]',
                    storage_destinations TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL,
                    result_summary TEXT,
                    error_type TEXT,
                    duration_ms REAL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    UNIQUE(year, year_sequence)
                )
            """)
        migrated = TraceStore(path)
        trace_id, started = migrated.start(input_source="text", agent="personal")
        migrated.finish(
            trace_id, started, status="success", agent="personal",
            model="m", provider="p",
        )
        trace = migrated.recent()[0]
        self.assertEqual(trace["input_modalities"], ["text"])
        self.assertEqual(trace["output_modalities"], ["text"])


class MultimodalAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {"SPARKLE_DATA_DIR": self.temp.name}, clear=False,
        )
        self.environment.start()
        self.registry = ModelRegistry()
        self.adapter = CapturingAdapter()
        self.registry.inject(self.registry.active_id, self.adapter)
        self.system = SparkleSystem(
            config=test_config(), model_registry=self.registry,
        )
        handler = type(
            "MultimodalHandler",
            (SparkleHandler,),
            {"system": self.system, "log_message": lambda *args: None},
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.environment.stop()
        self.temp.cleanup()

    @staticmethod
    def mixed_content() -> ContentEnvelope:
        return MultimodalSystemTests.mixed_content()

    def request(self, path: str, value: dict | None = None):
        data = json.dumps(value).encode("utf-8") if value is not None else None
        request = urllib.request.Request(
            self.base + path,
            data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method="POST" if data else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_contract_endpoint_and_mixed_api_execution(self):
        status, contract = self.request("/api/content-contract")
        self.assertEqual(status, 200)
        self.assertEqual(contract["protocol_version"], CONTENT_PROTOCOL)
        self.assertEqual(
            contract["content_types"], ["audio", "document", "image", "text"],
        )
        self.assertFalse(contract["semantic_understanding_verified"])

        content = self.mixed_content()
        status, response = self.request(
            "/api/chat", {"content": content.to_dict(), "agent": "research"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            response["result"]["input_modalities"], content.modalities,
        )
        self.assertEqual(
            response["result"]["content_identifiers"],
            content.content_identifiers,
        )
        self.assertEqual(self.system.traces.recent()[0]["input_source"], "text")

    def test_api_rejects_empty_malformed_oversized_and_ambiguous_content(self):
        invalid = [
            {"content": {"protocol_version": CONTENT_PROTOCOL, "parts": []}},
            {"content": {"protocol_version": CONTENT_PROTOCOL, "parts": "bad"}},
            {"content": {"protocol_version": CONTENT_PROTOCOL, "parts": [{"type": "video", "data": "x"}]}},
            {
                "message": "ambiguous",
                "content": ContentEnvelope.from_text("duplicate").to_dict(),
            },
            {"message": 123},
            {"message": "valid", "unexpected": "not accepted"},
            {
                "content": ContentEnvelope.from_text(
                    "x" * MAX_PART_BYTES["text"]
                ).to_dict()
                | {"extra": True},
            },
        ]
        for value in invalid:
            with self.subTest(value=list(value)):
                status, response = self.request("/api/chat", value)
                self.assertEqual(status, 400)
                self.assertFalse(response["ok"])

        oversized = {
            "content": {
                "protocol_version": CONTENT_PROTOCOL,
                "parts": [{
                    "type": "text",
                    "data": "x" * (MAX_PART_BYTES["text"] + 1),
                    "media_type": "text/plain",
                    "encoding": "utf-8",
                    "metadata": {},
                }],
            }
        }
        status, response = self.request("/api/chat", oversized)
        self.assertEqual(status, 400)
        self.assertEqual(response["error_type"], "ContentValidationError")


class ProviderBoundaryTests(unittest.TestCase):
    def test_minimax_remains_text_only_without_provider_specific_multimodal_mapping(self):
        called = False

        def opener(*_args, **_kwargs):
            nonlocal called
            called = True
            raise AssertionError("provider request must not be made")

        adapter = MiniMaxMessagesAdapter(
            {
                "model_id": "MiniMax-M3",
                "base_url": "https://api.minimax.io/anthropic/v1/messages",
                "secret_refs": ["MINIMAX_API_KEY"],
                "enabled": True,
            },
            SecretResolver({"MINIMAX_API_KEY": "unit-test-secret"}),
            opener=opener,
        )
        request = ModelRequest(messages=[Message(
            "user",
            envelope(ContentPart.binary(
                "image", b"pixels", media_type="image/png",
            )),
        )])
        with self.assertRaises(UnsupportedModalityError):
            adapter.complete(request)
        self.assertFalse(called)

    def test_router_can_select_a_future_multimodal_adapter_without_core_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "models.json"
            base = {
                "provider": "minimax",
                "model_id": "MiniMax-M3",
                "adapter": "minimax_messages",
                "roles": ["general", "reasoning"],
                "enabled": True,
                "base_url": "https://api.minimax.io/anthropic/v1/messages",
                "secret_refs": ["MINIMAX_API_KEY"],
            }
            path.write_text(json.dumps({
                "active_model": "text",
                "models": [
                    {**base, "id": "text", "modalities": ["text"]},
                    {
                        **base, "id": "future-multimodal",
                        "modalities": ["text", "image", "audio", "document"],
                    },
                ],
                "routing": {"default": "text", "reasoning": "text"},
            }), encoding="utf-8")
            registry = ModelRegistry(path, SecretResolver({}))
            text_adapter = DeterministicAdapter()
            text_adapter.supported_modalities = frozenset({"text"})
            future_adapter = DeterministicAdapter()
            registry.inject("text", text_adapter)
            registry.inject("future-multimodal", future_adapter)
            selected = ModelRouter(registry).select(
                "reasoning", modalities=["text", "image"],
            )
            self.assertIs(selected, future_adapter)
            advertised = {item["id"]: item["modalities"] for item in registry.list()}
            self.assertEqual(advertised["text"], ["text"])
            self.assertEqual(
                advertised["future-multimodal"],
                ["text", "image", "audio", "document"],
            )

    def test_registry_rejects_unknown_or_duplicate_modalities(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "models.json"
            base = {
                "id": "bad", "provider": "minimax", "model_id": "MiniMax-M3",
                "adapter": "minimax_messages", "roles": ["general"],
                "enabled": True,
                "base_url": "https://api.minimax.io/anthropic/v1/messages",
                "secret_refs": ["MINIMAX_API_KEY"],
            }
            for modalities in (["text", "video"], ["text", "text"], []):
                with self.subTest(modalities=modalities):
                    path.write_text(json.dumps({
                        "active_model": "bad",
                        "models": [{**base, "modalities": modalities}],
                    }), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        ModelRegistry(path, SecretResolver({}))
