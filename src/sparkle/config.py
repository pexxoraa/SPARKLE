from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sparkle.platform_support import default_state_root


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_root() -> Path:
    configured = os.environ.get("SPARKLE_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    checkout = project_root()
    if (checkout / "application" / "config.json").is_file():
        return checkout / "var"
    return default_state_root()


def _materialize_default(target: Path, bundled: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_file():
            raise ValueError("SPARKLE configuration must be a regular non-symlink file")
        return target
    content = bundled.read_text(encoding="utf-8")
    try:
        with target.open("x", encoding="utf-8") as handle:
            handle.write(content)
        target.chmod(0o600)
    except FileExistsError:
        if target.is_symlink() or not target.is_file():
            raise ValueError("SPARKLE configuration must be a regular non-symlink file")
    return target


def application_config_path() -> Path:
    explicit = os.environ.get("SPARKLE_APPLICATION_CONFIG")
    if explicit:
        return Path(explicit).expanduser().resolve()
    checkout = project_root() / "application" / "config.json"
    if checkout.is_file() and not checkout.is_symlink():
        return checkout
    bundled = Path(__file__).with_name("defaults") / "application" / "config.json"
    return _materialize_default(
        data_root() / "application" / "config.json", bundled,
    )


def model_config_path() -> Path:
    explicit = os.environ.get("SPARKLE_MODEL_CONFIG")
    if explicit:
        return Path(explicit).expanduser().resolve()
    checkout = project_root() / "ai_environment" / "configurations" / "models.json"
    if checkout.is_file() and not checkout.is_symlink():
        return checkout
    bundled = (
        Path(__file__).with_name("defaults")
        / "ai_environment" / "configurations" / "models.json"
    )
    return _materialize_default(
        data_root() / "ai_environment" / "configurations" / "models.json",
        bundled,
    )


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
    external_worker_id: str = ""
    external_worker_request_timeout_seconds: int = 15
    external_worker_job_timeout_seconds: int = 10
    external_worker_max_payload_bytes: int = 8_000_000

    max_tool_calls: int = 16
    max_specialists: int = 4

    def __post_init__(self):
        for name, minimum, maximum in (
            ("max_tool_rounds", 0, 16),
            ("max_tool_calls", 1, 128),
            ("max_specialists", 1, 16),
        ):
            value = getattr(self, name)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(
                    f"{name} must be an integer from {minimum} to {maximum}"
                )

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        source = load_json(path or application_config_path())
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
            raise ValueError(
                "security.api_token_refs must contain secret reference names"
            )
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
            max_tool_rounds=source["orchestrator"]["max_tool_rounds"],
            max_tool_calls=source["orchestrator"].get("max_tool_calls", 16),
            max_specialists=source["orchestrator"].get("max_specialists", 4),
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
            external_worker_id=os.environ.get(
                "SPARKLE_EXTERNAL_WORKER_ID",
                str(development.get("external_worker_id", "")),
            ).strip(),
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
