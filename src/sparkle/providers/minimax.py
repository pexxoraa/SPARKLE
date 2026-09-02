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

RETRYABLE_PROVIDER_CODES = {1000, 1001, 1002, 1024, 1033}
AUTH_PROVIDER_CODES = {1004, 2049}


class MiniMaxMessagesAdapter(ModelAdapter):
    """MiniMax Messages HTTP adapter with no third-party model SDK dependency."""

    provider = "minimax"

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
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }

    @staticmethod
    def _message(message: Message) -> dict[str, Any]:
        if message.provider_state is not None and message.role == "assistant":
            return {"role": "assistant", "content": message.provider_state}
        if message.role == "tool":
            return {
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.content,
                }],
            }
        if message.role == "assistant" and message.tool_calls:
            content: list[dict[str, Any]] = []
            if message.text_content:
                content.append({"type": "text", "text": message.text_content})
            content.extend(
                {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
                for call in message.tool_calls
            )
            return {"role": "assistant", "content": content}
        if message.role == "system":
            raise ValueError("System messages must be provided via ModelRequest.system")
        return {"role": message.role, "content": message.text_content}

    def _payload(self, request: ModelRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": [self._message(message) for message in request.messages if message.role != "system"],
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "stream": request.stream,
            "service_tier": self._config.get("service_tier", "standard"),
            "thinking": {"type": "adaptive" if request.thinking else "disabled"},
        }
        system_parts = [
            message.text_content for message in request.messages
            if message.role == "system"
        ]
        if request.system:
            system_parts.insert(0, request.system)
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        if request.tools:
            payload["tools"] = [self._tool_definition(tool) for tool in request.tools]
            payload["tool_choice"] = {"type": "auto"}
        if request.metadata.get("user_id"):
            payload["metadata"] = {"user_id": str(request.metadata["user_id"])}
        return payload

    @staticmethod
    def _safe_error(body: bytes, status: int | None = None) -> ModelError:
        provider_code: int | None = None
        message = "MiniMax request failed"
        try:
            parsed = json.loads(body.decode("utf-8"))
            base = parsed.get("base_resp", {}) if isinstance(parsed, dict) else {}
            provider_code = base.get("status_code") or parsed.get("error", {}).get("code")
            provider_message = base.get("status_msg") or parsed.get("error", {}).get("message")
            if provider_message:
                message = f"MiniMax request failed: {provider_message}"
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            pass
        if provider_code in AUTH_PROVIDER_CODES or status in {401, 403}:
            message = "MiniMax authentication failed; verify the configured server-side key"
        retryable = provider_code in RETRYABLE_PROVIDER_CODES or status in {408, 429, 500, 502, 503, 504}
        category = {
            401: "authentication_failure", 403: "authentication_failure",
            408: "timeout", 429: "rate_limited",
        }.get(status, "provider_failure")
        return ModelError(
            message, retryable=retryable, status_code=status or provider_code,
            category=category,
        )

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> ModelResponse:
        content = data.get("content") or []
        text = "".join(block.get("text", "") for block in content if block.get("type") == "text")
        calls = [
            ToolCall(
                id=str(block.get("id", "")),
                name=str(block.get("name", "")),
                arguments=block.get("input") if isinstance(block.get("input"), dict) else {},
            )
            for block in content
            if block.get("type") == "tool_use"
        ]
        usage_data = data.get("usage") or {}
        return ModelResponse(
            text=text,
            model=str(data.get("model", "MiniMax-M3")),
            provider="minimax",
            finish_reason=str(data.get("stop_reason", "unknown")),
            tool_calls=calls,
            usage=TokenUsage(
                input_tokens=int(usage_data.get("input_tokens", 0) or 0),
                output_tokens=int(usage_data.get("output_tokens", 0) or 0),
                cache_read_input_tokens=int(usage_data.get("cache_read_input_tokens", 0) or 0),
                cache_creation_input_tokens=int(usage_data.get("cache_creation_input_tokens", 0) or 0),
            ),
            provider_request_id=str(data.get("id")) if data.get("id") else None,
            usage_reported="usage" in data,
            raw_assistant_content=content,
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
            http_request = urllib.request.Request(self._base_url, data=body, headers=headers, method="POST")
            try:
                with self._opener(http_request, timeout=self._timeout) as response:
                    raw = response.read()
                data = json.loads(raw.decode("utf-8"))
                base = data.get("base_resp") if isinstance(data, dict) else None
                if isinstance(base, dict) and base.get("status_code") not in {None, 0}:
                    raise self._safe_error(raw)
                result = self._parse_response(data)
                result.attempts = attempt + 1
                return result
            except urllib.error.HTTPError as exc:
                last_error = self._safe_error(exc.read(), exc.code)
            except urllib.error.URLError as exc:
                last_error = ModelError(
                    f"MiniMax network failure: {exc.reason}", retryable=True,
                    category="connectivity_failure",
                )
            except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as exc:
                last_error = ModelError(f"MiniMax returned an invalid response: {type(exc).__name__}")
            except ModelError as exc:
                last_error = exc
            if not last_error.retryable or attempt + 1 >= self._attempts:
                last_error.attempts = attempt + 1
                raise last_error
            delay = self._base_delay * (2**attempt) + random.uniform(0, self._base_delay / 4 if self._base_delay else 0)
            self._sleeper(delay)
        raise last_error or ModelError("MiniMax request failed")

    def stream(self, request: ModelRequest) -> Iterator[str]:
        self.validate_request(request)
        request.stream = True
        try:
            headers = self._headers()
        except SecretNotFoundError as exc:
            raise ModelError(str(exc), retryable=False) from exc
        headers["Accept"] = "text/event-stream"
        body = json.dumps(self._payload(request), separators=(",", ":")).encode("utf-8")
        http_request = urllib.request.Request(self._base_url, data=body, headers=headers, method="POST")
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
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta") or {}
                        text = delta.get("text")
                        if text:
                            yield str(text)
        except urllib.error.HTTPError as exc:
            raise self._safe_error(exc.read(), exc.code) from exc
        except urllib.error.URLError as exc:
            raise ModelError(f"MiniMax network failure: {exc.reason}", retryable=True) from exc
