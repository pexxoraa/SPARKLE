from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

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


@dataclass(slots=True)
class Message:
    role: Role
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    provider_state: Any | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("provider_state", None)
        return {key: value for key, value in data.items() if value is not None and value != []}


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
