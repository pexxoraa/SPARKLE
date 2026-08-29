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


def environment_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    value = int(os.environ.get(name, default))
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be from {minimum} to {maximum}")
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
    api_auth_required: bool = False
    api_token_refs: tuple[str, ...] = ("SPARKLE_API_TOKEN",)
    allowed_origins: tuple[str, ...] = ()
    api_rate_limit_requests: int = 120
    api_rate_limit_window_seconds: int = 60
    session_auth_enabled: bool = True
    session_cookie_secure: bool = False
    session_ttl_seconds: int = 3_600
    session_max_active: int = 32
    workspace_tests_enabled: bool = False
    workspace_test_timeout_seconds: int = 10
    external_worker_enabled: bool = False
    external_worker_url: str = ""
    external_worker_secret_refs: tuple[str, ...] = ("SPARKLE_WORKER_SIGNING_KEY",)
    external_worker_request_timeout_seconds: int = 15
    external_worker_job_timeout_seconds: int = 10
    external_worker_max_payload_bytes: int = 8_000_000

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        source = load_json(path or project_root() / "application" / "config.json")
        security = source.get("security") or {}
        development = source.get("development") or {}
        if not isinstance(security, dict):
            raise ValueError("security configuration must be an object")
        if not isinstance(development, dict):
            raise ValueError("development configuration must be an object")
        token_refs = security.get("api_token_refs", ["SPARKLE_API_TOKEN"])
        allowed_origins = security.get("allowed_origins", [])
        worker_secret_refs = development.get(
            "external_worker_secret_refs", ["SPARKLE_WORKER_SIGNING_KEY"],
        )
        if not isinstance(token_refs, list) or not token_refs or not all(
            isinstance(item, str) and item for item in token_refs
        ):
            raise ValueError("security.api_token_refs must contain secret reference names")
        if not isinstance(allowed_origins, list) or not all(
            isinstance(item, str) and item for item in allowed_origins
        ):
            raise ValueError("security.allowed_origins must be a string array")
        if not isinstance(worker_secret_refs, list) or not worker_secret_refs or not all(
            isinstance(item, str) and item for item in worker_secret_refs
        ):
            raise ValueError(
                "development.external_worker_secret_refs must contain secret reference names"
            )
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
            api_rate_limit_requests=environment_int(
                "SPARKLE_API_RATE_LIMIT_REQUESTS",
                int(security.get("rate_limit_requests", 120)),
                minimum=1,
                maximum=10_000,
            ),
            api_rate_limit_window_seconds=environment_int(
                "SPARKLE_API_RATE_LIMIT_WINDOW_SECONDS",
                int(security.get("rate_limit_window_seconds", 60)),
                minimum=1,
                maximum=3_600,
            ),
            session_auth_enabled=environment_bool(
                "SPARKLE_SESSION_AUTH_ENABLED",
                bool(security.get("session_auth_enabled", True)),
            ),
            session_cookie_secure=environment_bool(
                "SPARKLE_SESSION_COOKIE_SECURE",
                bool(security.get("session_cookie_secure", False)),
            ),
            session_ttl_seconds=environment_int(
                "SPARKLE_SESSION_TTL_SECONDS",
                int(security.get("session_ttl_seconds", 3_600)),
                minimum=60,
                maximum=86_400,
            ),
            session_max_active=environment_int(
                "SPARKLE_SESSION_MAX_ACTIVE",
                int(security.get("session_max_active", 32)),
                minimum=1,
                maximum=1_000,
            ),
            workspace_tests_enabled=environment_bool(
                "SPARKLE_WORKSPACE_TESTS_ENABLED",
                bool(development.get("workspace_tests_enabled", False)),
            ),
            workspace_test_timeout_seconds=environment_int(
                "SPARKLE_WORKSPACE_TEST_TIMEOUT_SECONDS",
                int(development.get("workspace_test_timeout_seconds", 10)),
                minimum=1,
                maximum=60,
            ),
            external_worker_enabled=environment_bool(
                "SPARKLE_EXTERNAL_WORKER_ENABLED",
                bool(development.get("external_worker_enabled", False)),
            ),
            external_worker_url=os.environ.get(
                "SPARKLE_EXTERNAL_WORKER_URL",
                str(development.get("external_worker_url", "")),
            ).strip(),
            external_worker_secret_refs=tuple(worker_secret_refs),
            external_worker_request_timeout_seconds=environment_int(
                "SPARKLE_EXTERNAL_WORKER_REQUEST_TIMEOUT_SECONDS",
                int(development.get("external_worker_request_timeout_seconds", 15)),
                minimum=1,
                maximum=120,
            ),
            external_worker_job_timeout_seconds=environment_int(
                "SPARKLE_EXTERNAL_WORKER_JOB_TIMEOUT_SECONDS",
                int(development.get("external_worker_job_timeout_seconds", 10)),
                minimum=1,
                maximum=60,
            ),
            external_worker_max_payload_bytes=environment_int(
                "SPARKLE_EXTERNAL_WORKER_MAX_PAYLOAD_BYTES",
                int(development.get("external_worker_max_payload_bytes", 8_000_000)),
                minimum=1_000_000,
                maximum=20_000_000,
            ),
        )
