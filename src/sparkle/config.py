from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_root() -> Path:
    configured = os.environ.get("SPARKLE_DATA_DIR")
    return Path(configured).expanduser().resolve() if configured else project_root() / "var"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Configuration root must be an object: {path}")
    return value


def environment_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


@dataclass(frozen=True, slots=True)
class AppConfig:
    host: str
    port: int
    max_tool_rounds: int
    memory_results: int
    knowledge_results: int
    allow_shell: bool
    allow_web: bool
    api_auth_required: bool = False
    api_token_refs: tuple[str, ...] = ("SPARKLE_API_TOKEN",)
    allowed_origins: tuple[str, ...] = ()

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        source = load_json(path or project_root() / "application" / "config.json")
        security = source.get("security") or {}
        if not isinstance(security, dict):
            raise ValueError("security configuration must be an object")
        token_refs = security.get("api_token_refs", ["SPARKLE_API_TOKEN"])
        allowed_origins = security.get("allowed_origins", [])
        if not isinstance(token_refs, list) or not token_refs or not all(
            isinstance(item, str) and item for item in token_refs
        ):
            raise ValueError("security.api_token_refs must contain secret reference names")
        if not isinstance(allowed_origins, list) or not all(
            isinstance(item, str) and item for item in allowed_origins
        ):
            raise ValueError("security.allowed_origins must be a string array")
        return cls(
            host=os.environ.get("SPARKLE_HOST", str(source["server"]["host"])),
            port=int(os.environ.get("SPARKLE_PORT", source["server"]["port"])),
            max_tool_rounds=int(source["orchestrator"]["max_tool_rounds"]),
            memory_results=int(source["context"]["memory_results"]),
            knowledge_results=int(source["context"]["knowledge_results"]),
            allow_shell=bool(source["tools"]["allow_shell"]),
            allow_web=bool(source["tools"]["allow_web"]),
            api_auth_required=environment_bool(
                "SPARKLE_API_AUTH_REQUIRED",
                bool(security.get("api_auth_required", False)),
            ),
            api_token_refs=tuple(token_refs),
            allowed_origins=tuple(allowed_origins),
        )
