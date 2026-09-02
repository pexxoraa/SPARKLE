from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from typing import Any

from sparkle.contracts import Message, ModelRequest, ModelResponse, TokenUsage, ToolCall
from sparkle.model import ModelAdapter, ModelError
from sparkle.secrets import SecretNotFoundError, SecretResolver


class NVIDIAChatCompletionsAdapter(ModelAdapter):
    """NVIDIA NIM Chat Completions adapter using only the standard library."""

    provider = "nvidia"
    supported_modalities = frozenset({"text"})

    def __init__(
        self,
        config: dict[str, Any],
        secrets: SecretResolver,
        *,
        opener: Callable[..., Any] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self._config = config
        self._secrets = secrets
        self._opener = opener or urllib.request.urlopen
        self._sleeper = sleeper
        self.model_id = str(config["model_id"])
        self._base_url = str(config["base_url"])
        self._secret_refs = list(config["secret_refs"])
        self._timeout = float(config.get("timeout_seconds", 120))
        retry = config.get("retry", {})
        self._attempts = max(1, int(retry.get("attempts", 3)))
        self._base_delay = max(0.0, float(retry.get("base_delay_seconds", 0.5)))

    def health(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model_id,
            "configured": any(self._secrets.status(self._secret_refs).values()),
            "endpoint": self._base_url,
            "enabled": bool(self._config.get("enabled", True)),
        }

    def _headers(self) -> dict[str, str]:
        key = self._secrets.first(self._secret_refs)
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SPARKLE/0.30",
        }

    @staticmethod
    def _tool_definition(tool: Any) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    @staticmethod
    def _message(message: Message) -> dict[str, Any]:
        if message.role == "system":
            return {"role": "system", "content": message.text_content}
        if message.role == "tool":
            return {
                "role": "tool",
                "content": message.text_content,
                "tool_call_id": message.tool_call_id,
            }
        if message.role == "assistant" and message.tool_calls:
            return {
                "role": "assistant",
                "content": message.text_content or None,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(
                                call.arguments, separators=(",", ":"), sort_keys=True,
                            ),
                        },
                    }
                    for call in message.tool_calls
                ],
            }
        return {"role": message.role, "content": message.text_content}

    def _payload(self, request: ModelRequest) -> dict[str, Any]:
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend(self._message(message) for message in request.messages)
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": min(
                request.max_output_tokens,
                int(self._config.get("max_output_tokens", request.max_output_tokens)),
            ),
            "temperature": request.temperature,
            "stream": request.stream,
        }
        if request.thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": True}
            budget = int(self._config.get("reasoning_budget", 0))
            if budget > 0:
                payload["reasoning_budget"] = min(budget, payload["max_tokens"])
        if request.tools:
            payload["tools"] = [self._tool_definition(tool) for tool in request.tools]
            payload["tool_choice"] = "auto"
        return payload

    @staticmethod
    def _safe_error(body: bytes, status: int | None = None) -> ModelError:
        detail = "NVIDIA request failed"
        try:
            parsed = json.loads(body.decode("utf-8"))
            error = parsed.get("error", {}) if isinstance(parsed, dict) else {}
            message = error.get("message") if isinstance(error, dict) else None
            if isinstance(message, str) and message:
                detail = f"NVIDIA request failed: {message[:300]}"
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            pass
        if status in {401, 403}:
            detail = "NVIDIA authentication failed; verify the configured server-side key"
        retryable = status in {408, 409, 429, 500, 502, 503, 504}
        return ModelError(detail, retryable=retryable, status_code=status)

    @staticmethod
    def _tool_calls(value: Any) -> list[ToolCall]:
        if not isinstance(value, list):
            return []
        result = []
        for item in value:
            if not isinstance(item, dict):
                raise TypeError("tool call is not an object")
            function = item.get("function")
            if not isinstance(function, dict):
                raise TypeError("tool function is not an object")
            arguments = function.get("arguments", "{}")
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            if not isinstance(arguments, dict):
                raise TypeError("tool arguments are not an object")
            result.append(ToolCall(
                id=str(item.get("id", "")),
                name=str(function.get("name", "")),
                arguments=arguments,
            ))
        return result

    @classmethod
    def _parse_response(cls, data: dict[str, Any]) -> ModelResponse:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise TypeError("response choices are missing")
        choice = choices[0]
        message = choice.get("message")
        if not isinstance(message, dict):
            raise TypeError("response message is missing")
        content = message.get("content")
        text = content if isinstance(content, str) else ""
        usage_data = data.get("usage") or {}
        if not isinstance(usage_data, dict):
            raise TypeError("response usage is invalid")
        raw_content = [{
            "type": "nvidia_chat_message",
            "content": text,
            "tool_calls": message.get("tool_calls", []),
        }]
        return ModelResponse(
            text=text,
            model=str(data.get("model", "")),
            provider="nvidia",
            finish_reason=str(choice.get("finish_reason", "unknown")),
            tool_calls=cls._tool_calls(message.get("tool_calls", [])),
            usage=TokenUsage(
                input_tokens=int(usage_data.get("prompt_tokens", 0) or 0),
                output_tokens=int(usage_data.get("completion_tokens", 0) or 0),
            ),
            provider_request_id=str(data.get("id")) if data.get("id") else None,
            raw_assistant_content=raw_content,
        )

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.validate_request(request)
        request.stream = False
        try:
            headers = self._headers()
        except SecretNotFoundError as exc:
            raise ModelError(str(exc), retryable=False) from exc
        body = json.dumps(self._payload(request), separators=(",", ":")).encode("utf-8")
        last_error: ModelError | None = None
        for attempt in range(self._attempts):
            http_request = urllib.request.Request(
                self._base_url, data=body, headers=headers, method="POST",
            )
            try:
                with self._opener(http_request, timeout=self._timeout) as response:
                    raw = response.read()
                value = json.loads(raw.decode("utf-8"))
                if not isinstance(value, dict):
                    raise TypeError("response root is not an object")
                return self._parse_response(value)
            except urllib.error.HTTPError as exc:
                last_error = self._safe_error(exc.read(), exc.code)
            except urllib.error.URLError as exc:
                last_error = ModelError(
                    f"NVIDIA network failure: {exc.reason}", retryable=True,
                )
            except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as exc:
                last_error = ModelError(
                    f"NVIDIA returned an invalid response: {type(exc).__name__}",
                    retryable=False,
                )
            if not last_error.retryable or attempt + 1 >= self._attempts:
                raise last_error
            delay = self._base_delay * (2**attempt)
            delay += random.uniform(0, self._base_delay / 4 if self._base_delay else 0)
            self._sleeper(delay)
        raise last_error or ModelError("NVIDIA request failed")

    def stream(self, request: ModelRequest) -> Iterator[str]:
        self.validate_request(request)
        request.stream = True
        try:
            headers = self._headers()
        except SecretNotFoundError as exc:
            raise ModelError(str(exc), retryable=False) from exc
        headers["Accept"] = "text/event-stream"
        body = json.dumps(self._payload(request), separators=(",", ":")).encode("utf-8")
        http_request = urllib.request.Request(
            self._base_url, data=body, headers=headers, method="POST",
        )
        try:
            with self._opener(http_request, timeout=self._timeout) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line.startswith("data:"):
                        continue
                    value = line[5:].strip()
                    if value == "[DONE]":
                        break
                    event = json.loads(value)
                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        yield content
        except urllib.error.HTTPError as exc:
            raise self._safe_error(exc.read(), exc.code) from exc
        except urllib.error.URLError as exc:
            raise ModelError(f"NVIDIA network failure: {exc.reason}", retryable=True) from exc
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
            raise ModelError(
                f"NVIDIA returned an invalid stream: {type(exc).__name__}",
                retryable=False,
            ) from exc
