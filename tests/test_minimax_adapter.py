from __future__ import annotations

import json
import unittest
import urllib.error

from sparkle.contracts import Message, ModelRequest, ToolDefinition
from sparkle.model import ModelError
from sparkle.providers.minimax import MiniMaxMessagesAdapter
from sparkle.secrets import SecretResolver
from tests.helpers import FakeHTTPResponse


def config(**overrides):
    value = {
        "model_id": "MiniMax-M3", "base_url": "https://api.minimax.io/anthropic/v1/messages",
        "secret_refs": ["MINIMAX_API_KEY"], "enabled": True, "timeout_seconds": 3,
        "service_tier": "standard", "retry": {"attempts": 2, "base_delay_seconds": 0},
    }
    value.update(overrides)
    return value


class MiniMaxAdapterTests(unittest.TestCase):
    def test_maps_request_and_response(self):
        captured = {}
        response = {
            "id": "req-1", "model": "MiniMax-M3", "stop_reason": "tool_use",
            "content": [
                {"type": "thinking", "thinking": "private"},
                {"type": "text", "text": "Checking."},
                {"type": "tool_use", "id": "call-1", "name": "calculator", "input": {"expression": "2+2"}},
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.headers)
            captured["payload"] = json.loads(request.data)
            captured["timeout"] = timeout
            return FakeHTTPResponse(response)

        adapter = MiniMaxMessagesAdapter(config(), SecretResolver({"MINIMAX_API_KEY": "secret"}), opener=opener)
        result = adapter.complete(ModelRequest(
            messages=[Message("user", "Calculate")], system="System",
            tools=[ToolDefinition("calculator", "Calculate", {"type": "object"})],
        ))
        self.assertEqual(captured["url"], config()["base_url"])
        self.assertEqual(captured["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(captured["payload"]["model"], "MiniMax-M3")
        self.assertEqual(captured["payload"]["system"], "System")
        self.assertEqual(captured["payload"]["tools"][0]["input_schema"], {"type": "object"})
        self.assertEqual(result.text, "Checking.")
        self.assertEqual(result.tool_calls[0].arguments, {"expression": "2+2"})
        self.assertEqual(result.usage.input_tokens, 10)
        self.assertEqual(result.raw_assistant_content, response["content"])

    def test_preserves_provider_state_for_tool_followup(self):
        captured = {}
        state = [{"type": "thinking", "thinking": "preserve", "signature": "sig"}, {"type": "tool_use", "id": "x", "name": "calculator", "input": {}}]

        def opener(request, timeout):
            captured.update(json.loads(request.data))
            return FakeHTTPResponse({"model": "MiniMax-M3", "stop_reason": "end_turn", "content": [{"type": "text", "text": "done"}]})

        adapter = MiniMaxMessagesAdapter(config(), SecretResolver({"MINIMAX_API_KEY": "secret"}), opener=opener)
        adapter.complete(ModelRequest(messages=[
            Message("user", "go"), Message("assistant", "", provider_state=state),
            Message("tool", "4", tool_call_id="x"),
        ]))
        self.assertEqual(captured["messages"][1]["content"], state)
        self.assertEqual(captured["messages"][2]["content"][0]["type"], "tool_result")

    def test_missing_key_is_safe_failure(self):
        adapter = MiniMaxMessagesAdapter(config(), SecretResolver({}))
        with self.assertRaises(ModelError) as failure:
            adapter.complete(ModelRequest(messages=[Message("user", "hello")]))
        self.assertNotIn("Bearer", str(failure.exception))
        self.assertFalse(failure.exception.retryable)

    def test_retries_transient_error(self):
        calls = 0

        def opener(request, timeout):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise urllib.error.URLError("temporary")
            return FakeHTTPResponse({"model": "MiniMax-M3", "stop_reason": "end_turn", "content": [{"type": "text", "text": "ok"}]})

        adapter = MiniMaxMessagesAdapter(config(), SecretResolver({"MINIMAX_API_KEY": "secret"}), opener=opener, sleeper=lambda _: None)
        self.assertEqual(adapter.complete(ModelRequest(messages=[Message("user", "hello")])).text, "ok")
        self.assertEqual(calls, 2)

    def test_streams_text_deltas(self):
        lines = [
            'event: content_block_delta\n',
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hel"}}\n',
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"lo"}}\n',
            'data: [DONE]\n',
        ]
        adapter = MiniMaxMessagesAdapter(
            config(), SecretResolver({"MINIMAX_API_KEY": "secret"}), opener=lambda *_args, **_kwargs: FakeHTTPResponse(lines=lines)
        )
        self.assertEqual("".join(adapter.stream(ModelRequest(messages=[Message("user", "hello")]))), "Hello")
