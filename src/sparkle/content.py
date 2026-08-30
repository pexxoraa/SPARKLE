from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Literal

ContentType = Literal["text", "image", "audio", "document"]

CONTENT_PROTOCOL = "SPARKLE-CONTENT/1"
SUPPORTED_CONTENT_TYPES = frozenset({"text", "image", "audio", "document"})
MAX_CONTENT_PARTS = 16
MAX_TOTAL_CONTENT_BYTES = 8_000_000
MAX_REQUEST_CONTENT_BYTES = 16_000_000
MAX_REQUEST_MESSAGES = 256
MAX_METADATA_BYTES = 4_096
MAX_METADATA_DEPTH = 4
MAX_METADATA_ITEMS = 64
MAX_METADATA_STRING_CHARS = 2_000
MAX_PART_BYTES = {
    "text": 1_000_000,
    "image": 5_000_000,
    "audio": 8_000_000,
    "document": 5_000_000,
}

_CONTENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_METADATA_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_MEDIA_TYPE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,63}/"
    r"[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,127}$"
)
_SENSITIVE_METADATA_TOKENS = (
    "api_key", "apikey", "authorization", "cookie", "credential",
    "password", "secret", "token",
)


def content_contract_status() -> dict[str, Any]:
    return {
        "protocol_version": CONTENT_PROTOCOL,
        "content_types": sorted(SUPPORTED_CONTENT_TYPES),
        "encodings": {"text": "utf-8", "binary": "base64"},
        "max_parts": MAX_CONTENT_PARTS,
        "max_total_bytes": MAX_TOTAL_CONTENT_BYTES,
        "max_request_bytes": MAX_REQUEST_CONTENT_BYTES,
        "max_request_messages": MAX_REQUEST_MESSAGES,
        "max_part_bytes": dict(sorted(MAX_PART_BYTES.items())),
        "max_metadata_bytes": MAX_METADATA_BYTES,
        "provider_neutral": True,
        "raw_content_traced": False,
        "semantic_understanding_verified": False,
    }


class ContentValidationError(ValueError):
    """Provider-neutral content failed a bounded contract validation."""


def _validate_metadata_value(
    value: Any,
    *,
    depth: int = 0,
    counter: list[int] | None = None,
) -> Any:
    if depth > MAX_METADATA_DEPTH:
        raise ContentValidationError("Content metadata nesting is too deep")
    counter = counter if counter is not None else [0]
    counter[0] += 1
    if counter[0] > MAX_METADATA_ITEMS:
        raise ContentValidationError("Content metadata contains too many values")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        if len(value) > MAX_METADATA_STRING_CHARS:
            raise ContentValidationError("Content metadata string is too long")
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContentValidationError("Content metadata numbers must be finite")
        return value
    if isinstance(value, list):
        return [
            _validate_metadata_value(item, depth=depth + 1, counter=counter)
            for item in value
        ]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key in value:
            if not isinstance(key, str) or not _METADATA_KEY.fullmatch(key):
                raise ContentValidationError("Content metadata key is invalid")
            lowered = key.lower()
            if any(token in lowered for token in _SENSITIVE_METADATA_TOKENS):
                raise ContentValidationError(
                    "Content metadata cannot contain credential-like fields"
                )
        for key in sorted(value):
            normalized[key] = _validate_metadata_value(
                value[key], depth=depth + 1, counter=counter,
            )
        return normalized
    raise ContentValidationError("Content metadata must contain JSON values only")


def _normalize_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContentValidationError("Content metadata must be an object")
    normalized = _validate_metadata_value(value)
    encoded = json.dumps(
        normalized, ensure_ascii=False, separators=(",", ":"),
        sort_keys=True, allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > MAX_METADATA_BYTES:
        raise ContentValidationError("Content metadata is too large")
    return normalized


@dataclass(slots=True)
class ContentPart:
    type: ContentType | str
    data: str
    media_type: str | None = None
    encoding: str | None = None
    content_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    _decoded: bytes = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.type not in SUPPORTED_CONTENT_TYPES:
            raise ContentValidationError(f"Unsupported content type: {self.type}")
        if not isinstance(self.data, str):
            raise ContentValidationError("Content data must be a string")
        if self.media_type is not None and not isinstance(self.media_type, str):
            raise ContentValidationError("Content media_type must be a string")

        if self.type == "text":
            self.encoding = self.encoding or "utf-8"
            self.media_type = self.media_type or "text/plain"
            if self.encoding != "utf-8":
                raise ContentValidationError("Text content encoding must be utf-8")
            if not self.data.strip():
                raise ContentValidationError("Text content cannot be empty")
            self._decoded = self.data.encode("utf-8")
        else:
            self.encoding = self.encoding or "base64"
            if self.encoding != "base64":
                raise ContentValidationError("Binary content encoding must be base64")
            if not self.data:
                raise ContentValidationError("Binary content cannot be empty")
            try:
                self._decoded = base64.b64decode(
                    self.data.encode("ascii"), validate=True,
                )
            except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
                raise ContentValidationError("Binary content is not valid base64") from exc
            if not self._decoded or base64.b64encode(self._decoded).decode("ascii") != self.data:
                raise ContentValidationError("Binary content must use canonical base64")
            if not self.media_type:
                raise ContentValidationError("Binary content requires media_type")

        if not self.media_type or not _MEDIA_TYPE.fullmatch(self.media_type):
            raise ContentValidationError("Content media_type is invalid")
        prefix = self.media_type.split("/", 1)[0].lower()
        if self.type == "text" and prefix != "text":
            raise ContentValidationError("Text content requires a text media type")
        if self.type == "image" and prefix != "image":
            raise ContentValidationError("Image content requires an image media type")
        if self.type == "audio" and prefix != "audio":
            raise ContentValidationError("Audio content requires an audio media type")
        if self.type == "document" and prefix in {"audio", "image", "video"}:
            raise ContentValidationError("Document content media type is incompatible")

        limit = MAX_PART_BYTES[str(self.type)]
        if len(self._decoded) > limit:
            raise ContentValidationError(
                f"{self.type.capitalize()} content exceeds {limit} bytes"
            )
        self.metadata = _normalize_metadata(self.metadata)
        identifier_digest = hashlib.sha256(
            str(self.type).encode("ascii") + b"\0"
            + self.media_type.encode("ascii") + b"\0" + self._decoded
        ).hexdigest()
        expected_identifier = f"spk-sha256:{identifier_digest}"
        self.content_id = self.content_id or expected_identifier
        if not isinstance(self.content_id, str) or not _CONTENT_ID.fullmatch(
            self.content_id
        ):
            raise ContentValidationError("Content identifier is invalid")
        if self.content_id != expected_identifier:
            raise ContentValidationError(
                "Content identifier does not match the validated content"
            )

    @classmethod
    def text(
        cls,
        value: str,
        *,
        content_id: str | None = None,
        media_type: str = "text/plain",
        metadata: dict[str, Any] | None = None,
    ) -> ContentPart:
        return cls(
            "text", value, media_type=media_type, encoding="utf-8",
            content_id=content_id, metadata=metadata or {},
        )

    @classmethod
    def binary(
        cls,
        content_type: Literal["image", "audio", "document"],
        value: bytes,
        *,
        media_type: str,
        content_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ContentPart:
        if not isinstance(value, bytes):
            raise ContentValidationError("Binary content value must be bytes")
        return cls(
            content_type,
            base64.b64encode(value).decode("ascii"),
            media_type=media_type,
            encoding="base64",
            content_id=content_id,
            metadata=metadata or {},
        )

    @property
    def size_bytes(self) -> int:
        return len(self._decoded)

    @property
    def digest(self) -> str:
        return hashlib.sha256(self._decoded).hexdigest()

    def decoded_bytes(self) -> bytes:
        return bytes(self._decoded)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "content_id": self.content_id,
            "media_type": self.media_type,
            "encoding": self.encoding,
            "data": self.data,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ContentPart:
        if not isinstance(value, dict):
            raise ContentValidationError("Content part must be an object")
        allowed = {
            "type", "content_id", "media_type", "encoding", "data", "metadata",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ContentValidationError(
                "Unsupported content part fields: " + ", ".join(sorted(unknown))
            )
        if "type" not in value or "data" not in value:
            raise ContentValidationError("Content part requires type and data")
        return cls(
            type=value["type"],
            data=value["data"],
            media_type=value.get("media_type"),
            encoding=value.get("encoding"),
            content_id=value.get("content_id"),
            metadata=value.get("metadata", {}),
        )

    def trace_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "content_id": self.content_id,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "sha256": self.digest,
        }


@dataclass(slots=True)
class ContentEnvelope:
    parts: list[ContentPart]
    protocol_version: str = CONTENT_PROTOCOL

    def __post_init__(self) -> None:
        if self.protocol_version != CONTENT_PROTOCOL:
            raise ContentValidationError("Unsupported content protocol version")
        if not isinstance(self.parts, list):
            raise ContentValidationError("Content parts must be a list")
        if not self.parts:
            raise ContentValidationError("Content envelope cannot be empty")
        if len(self.parts) > MAX_CONTENT_PARTS:
            raise ContentValidationError(
                f"Content envelope exceeds {MAX_CONTENT_PARTS} parts"
            )
        if any(not isinstance(part, ContentPart) for part in self.parts):
            raise ContentValidationError("Content envelope contains an invalid part")
        identifiers = [part.content_id for part in self.parts]
        if len(set(identifiers)) != len(identifiers):
            raise ContentValidationError("Content identifiers must be unique")
        if self.total_bytes > MAX_TOTAL_CONTENT_BYTES:
            raise ContentValidationError(
                f"Content envelope exceeds {MAX_TOTAL_CONTENT_BYTES} bytes"
            )

    @classmethod
    def from_text(cls, text: str) -> ContentEnvelope:
        return cls([ContentPart.text(text)])

    @property
    def total_bytes(self) -> int:
        return sum(part.size_bytes for part in self.parts)

    @property
    def modalities(self) -> list[str]:
        return list(dict.fromkeys(str(part.type) for part in self.parts))

    @property
    def content_identifiers(self) -> list[str]:
        return [str(part.content_id) for part in self.parts]

    @property
    def text_content(self) -> str:
        return "\n".join(part.data for part in self.parts if part.type == "text")

    def routing_text(self) -> str:
        sections = [self.text_content] if self.text_content else []
        sections.extend(
            f"[{part.type} content: {part.media_type}; id={part.content_id}]"
            for part in self.parts if part.type != "text"
        )
        return "\n".join(sections)

    def retrieval_text(self) -> str:
        sections = [self.text_content] if self.text_content else []
        sections.extend(
            f"{part.type} {part.media_type}"
            for part in self.parts if part.type != "text"
        )
        return "\n".join(sections)

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "parts": [part.to_dict() for part in self.parts],
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, separators=(",", ":"),
            sort_keys=True, allow_nan=False,
        )

    @classmethod
    def from_dict(cls, value: Any) -> ContentEnvelope:
        if not isinstance(value, dict):
            raise ContentValidationError("Content envelope must be an object")
        unknown = set(value) - {"protocol_version", "parts"}
        if unknown:
            raise ContentValidationError(
                "Unsupported content envelope fields: " + ", ".join(sorted(unknown))
            )
        if value.get("protocol_version") != CONTENT_PROTOCOL:
            raise ContentValidationError("Unsupported content protocol version")
        if not isinstance(value.get("parts"), list):
            raise ContentValidationError("Content envelope parts must be a list")
        return cls(
            parts=[ContentPart.from_dict(part) for part in value["parts"]],
            protocol_version=value["protocol_version"],
        )

    def trace_metadata(self) -> dict[str, Any]:
        return {
            "content_protocol": self.protocol_version,
            "part_count": len(self.parts),
            "total_bytes": self.total_bytes,
            "mixed_modalities": len(self.modalities) > 1,
            "content": [part.trace_dict() for part in self.parts],
        }
