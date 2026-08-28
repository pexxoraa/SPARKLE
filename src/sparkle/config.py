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


@dataclass(frozen=True, slots=True)
class AppConfig:
    host: str
    port: int
    max_tool_rounds: int
    memory_results: int
    knowledge_results: int
    allow_shell: bool
    allow_web: bool

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        source = load_json(path or project_root() / "application" / "config.json")
        return cls(
            host=os.environ.get("SPARKLE_HOST", str(source["server"]["host"])),
            port=int(os.environ.get("SPARKLE_PORT", source["server"]["port"])),
            max_tool_rounds=int(source["orchestrator"]["max_tool_rounds"]),
            memory_results=int(source["context"]["memory_results"]),
            knowledge_results=int(source["context"]["knowledge_results"]),
            allow_shell=bool(source["tools"]["allow_shell"]),
            allow_web=bool(source["tools"]["allow_web"]),
        )
