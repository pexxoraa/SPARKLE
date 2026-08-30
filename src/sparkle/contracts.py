from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from sparkle.content import (
    MAX_PART_BYTES,
    MAX_REQUEST_CONTENT_BYTES,
    MAX_REQUEST_MESSAGES,
    ContentEnvelope,
    ContentValidationError,
)

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

    @classmethod
    def from_dict(cls, value: Any) -> ToolCall:
        if not isinstance(value, dict) or set(value) != {"id", "name", "arguments"}:
            raise ContentValidationError("Tool call payload is malformed")
        if not isinstance(value["arguments"], dict):
            raise ContentValidationError("Tool call arguments must be an object")
        return cls(str(value["id"]), str(value["name"]), value["arguments"])


@dataclass(slots=True)
class Message:
    role: Role
    content: str | ContentEnvelope
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    provider_state: Any | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant", "tool"}:
            raise ContentValidationError(f"Unsupported message role: {self.role}")
        if not isinstance(self.content, (str, ContentEnvelope)):
            raise ContentValidationError(
                "Message content must be text or a content envelope"
            )

    @property
    def text_content(self) -> str:
        if isinstance(self.content, str):
            return self.content
        return self.content.text_content

    @property
    def modalities(self) -> list[str]:
        if isinstance(self.content, str):
            return ["text"]
        return self.content.modalities

    @property
    def content_identifiers(self) -> list[str]:
        if isinstance(self.content, str):
            return []
        return self.content.content_identifiers

    def trace_metadata(self) -> dict[str, Any]:
        if isinstance(self.content, str):
            return {
                "content_protocol": "legacy-text",
                "part_count": 1,
                "total_bytes": len(self.content.encode("utf-8")),
                "mixed_modalities": False,
                "content": [],
            }
        return self.content.trace_metadata()

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "role": self.role,
            "content": (
                self.content if isinstance(self.content, str)
                else self.content.to_dict()
            ),
            "name": self.name,
            "tool_call_id": self.tool_call_id,
            "tool_calls": [asdict(call) for call in self.tool_calls],
        }
        return {key: value for key, value in data.items() if value is not None and value != []}

    @classmethod
    def from_dict(cls, value: Any) -> Message:
        if not isinstance(value, dict):
            raise ContentValidationError("Message must be an object")
        allowed = {"role", "content", "name", "tool_call_id", "tool_calls"}
        unknown = set(value) - allowed
        if unknown:
            raise ContentValidationError(
                "Unsupported message fields: " + ", ".join(sorted(unknown))
            )
        if "role" not in value or "content" not in value:
            raise ContentValidationError("Message requires role and content")
        raw_content = value["content"]
        content = (
            raw_content if isinstance(raw_content, str)
            else ContentEnvelope.from_dict(raw_content)
        )
        raw_calls = value.get("tool_calls", [])
        if not isinstance(raw_calls, list):
            raise ContentValidationError("Message tool_calls must be a list")
        return cls(
            role=value["role"],
            content=content,
            name=value.get("name"),
            tool_call_id=value.get("tool_call_id"),
            tool_calls=[ToolCall.from_dict(call) for call in raw_calls],
        )


@dataclass(slots=True)
class ModelRequest:
    messages: list[Message]
    system: str | None = None
    tools: list[ToolDefinition] = field(default_factory=list)
    temperature: float = 1.0
    max_output_tokens: int = 4096
    thinking: bool = True
    stream: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.messages, list) or not self.messages:
            raise ContentValidationError("Model request requires messages")
        if len(self.messages) > MAX_REQUEST_MESSAGES:
            raise ContentValidationError(
                f"Model request exceeds {MAX_REQUEST_MESSAGES} messages"
            )
        total = 0
        for message in self.messages:
            if not isinstance(message, Message):
                raise ContentValidationError("Model request contains an invalid message")
            if isinstance(message.content, str):
                size = len(message.content.encode("utf-8"))
                if size > MAX_PART_BYTES["text"]:
                    raise ContentValidationError("Model request text message is too large")
                total += size
            else:
                total += message.content.total_bytes
        if total > MAX_REQUEST_CONTENT_BYTES:
            raise ContentValidationError(
                f"Model request exceeds {MAX_REQUEST_CONTENT_BYTES} content bytes"
            )

    @property
    def input_modalities(self) -> list[str]:
        modalities: list[str] = []
        for message in self.messages:
            if message.role not in {"user", "assistant"}:
                continue
            for modality in message.modalities:
                if modality not in modalities:
                    modalities.append(modality)
        return modalities or ["text"]


@dataclass(slots=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass(slots=True)
class ModelResponse:
    text: str
    model: str
    provider: str
    finish_reason: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    provider_request_id: str | None = None
    raw_assistant_content: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("raw_assistant_content", None)
        return data


@dataclass(slots=True)
class AgentResult:
    agent: str
    text: str
    model: str
    provider: str
    trace_id: str
    finish_reason: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    tool_calls_executed: list[str] = field(default_factory=list)
    input_modalities: list[str] = field(default_factory=lambda: ["text"])
    output_modalities: list[str] = field(default_factory=lambda: ["text"])
    content_identifiers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
