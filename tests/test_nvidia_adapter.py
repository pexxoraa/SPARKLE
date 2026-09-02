from __future__ import annotations

import json
import io
import unittest
import urllib.error

from sparkle.contracts import Message, ModelRequest, ToolCall, ToolDefinition
from sparkle.model import ModelError
from sparkle.providers.nvidia import NVIDIAChatCompletionsAdapter
from sparkle.secrets import SecretResolver
from tests.helpers import FakeHTTPResponse


def config(**overrides):
    value = {
        "model_id": "nvidia/nemotron-3.5-lightning-30b-a3b",
        "base_url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "secret_refs": ["NVIDIA_API_KEY"],
        "enabled": True,
        "timeout_seconds": 3,
        "max_output_tokens": 16384,
        "reasoning_budget": 8192,
        "retry": {"attempts": 2, "base_delay_seconds": 0},
    }
    value.update(overrides)
    return value


class NVIDIAAdapterTests(unittest.TestCase):
    def test_maps_request_response_tools_and_usage(self):
        captured = {}
        response = {
            "id": "chat-1",
            "model": config()["model_id"],
            "choices": [{
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": "Checking.",
                    "tool_calls": [{
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "calculator",
                            "arguments": "{\"expression\":\"2+2\"}",
                        },
                    }],
                },
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.headers)
            captured["payload"] = json.loads(request.data)
            captured["timeout"] = timeout
            return FakeHTTPResponse(response)

        adapter = NVIDIAChatCompletionsAdapter(
            config(), SecretResolver({"NVIDIA_API_KEY": "secret"}), opener=opener,
        )
        result = adapter.complete(ModelRequest(
            messages=[Message("user", "Calculate")],
            system="System",
            tools=[ToolDefinition("calculator", "Calculate", {"type": "object"})],
            max_output_tokens=20000,
        ))
        self.assertEqual(captured["url"], config()["base_url"])
        self.assertEqual(captured["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(captured["payload"]["messages"][0]["role"], "system")
        self.assertEqual(captured["payload"]["max_tokens"], 16384)
        self.assertTrue(captured["payload"]["chat_template_kwargs"]["enable_thinking"])
        self.assertEqual(captured["payload"]["tools"][0]["type"], "function")
        self.assertEqual(result.text, "Checking.")
        self.assertEqual(result.tool_calls[0].arguments, {"expression": "2+2"})
        self.assertEqual(result.usage.input_tokens, 10)
        self.assertEqual(result.provider_request_id, "chat-1")

    def test_maps_tool_followup_without_provider_specific_core_state(self):
        captured = {}

        def opener(request, timeout):
            captured.update(json.loads(request.data))
            return FakeHTTPResponse({
                "model": config()["model_id"],
                "choices": [{"finish_reason": "stop", "message": {"content": "done"}}],
            })

        adapter = NVIDIAChatCompletionsAdapter(
            config(), SecretResolver({"NVIDIA_API_KEY": "secret"}), opener=opener,
        )
        adapter.complete(ModelRequest(messages=[
            Message("user", "go"),
            Message("assistant", "", tool_calls=[ToolCall("x", "calculator", {"x": 1})]),
            Message("tool", "4", tool_call_id="x"),
        ]))
        self.assertEqual(captured["messages"][1]["tool_calls"][0]["function"]["name"], "calculator")
        self.assertEqual(captured["messages"][2]["role"], "tool")

    def test_missing_key_and_auth_failure_are_safe(self):
        adapter = NVIDIAChatCompletionsAdapter(config(), SecretResolver({}))
        with self.assertRaises(ModelError) as missing:
            adapter.complete(ModelRequest(messages=[Message("user", "hello")]))
        self.assertNotIn("Bearer", str(missing.exception))
        self.assertFalse(missing.exception.retryable)

        error = urllib.error.HTTPError(
            config()["base_url"], 401, "unauthorized", {},
            io.BytesIO(json.dumps({
                "error": {"message": "key=do-not-print"},
            }).encode("utf-8")),
        )
        rejected = NVIDIAChatCompletionsAdapter(
            config(), SecretResolver({"NVIDIA_API_KEY": "secret"}),
            opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
        )
        with self.assertRaisesRegex(ModelError, "authentication failed"):
            rejected.complete(ModelRequest(messages=[Message("user", "hello")]))

    def test_retries_transient_network_failure(self):
        calls = 0

        def opener(request, timeout):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise urllib.error.URLError("temporary")
            return FakeHTTPResponse({
                "model": config()["model_id"],
                "choices": [{"finish_reason": "stop", "message": {"content": "ok"}}],
            })

        adapter = NVIDIAChatCompletionsAdapter(
            config(), SecretResolver({"NVIDIA_API_KEY": "secret"}),
            opener=opener, sleeper=lambda _delay: None,
        )
        self.assertEqual(
            adapter.complete(ModelRequest(messages=[Message("user", "hello")])).text,
            "ok",
        )
        self.assertEqual(calls, 2)

    def test_streams_text_and_ignores_reasoning_only_chunks(self):
        lines = [
            'data: {"choices":[{"delta":{"reasoning_content":"private"}}]}\n',
            'data: {"choices":[{"delta":{"content":"Hel"}}]}\n',
            'data: {"choices":[{"delta":{"content":"lo"}}]}\n',
            'data: [DONE]\n',
        ]
        adapter = NVIDIAChatCompletionsAdapter(
            config(), SecretResolver({"NVIDIA_API_KEY": "secret"}),
            opener=lambda *_args, **_kwargs: FakeHTTPResponse(lines=lines),
        )
        self.assertEqual(
            "".join(adapter.stream(ModelRequest(messages=[Message("user", "hello")]))),
            "Hello",
        )


if __name__ == "__main__":
    unittest.main()
