from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping

SUPPORTED_PLATFORMS = frozenset(
    {"linux", "windows", "macos", "android", "ios", "grapheneos"}
)
DESKTOP_PLATFORMS = frozenset({"linux", "windows", "macos"})
MOBILE_PLATFORMS = frozenset({"android", "ios", "grapheneos"})


def detect_platform(
    platform_value: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    values = os.environ if environ is None else environ
    override = values.get("SPARKLE_PLATFORM", "").strip().lower()
    if override:
        if override not in SUPPORTED_PLATFORMS:
            raise ValueError(
                "SPARKLE_PLATFORM must be one of: "
                + ", ".join(sorted(SUPPORTED_PLATFORMS))
            )
        return override
    value = (platform_value or sys.platform).lower()
    if value in {"win32", "cygwin", "msys"}:
        return "windows"
    if value == "darwin":
        return "macos"
    if value == "ios":
        return "ios"
    if value == "android":
        return "android"
    if value.startswith("linux"):
        if values.get("ANDROID_ROOT") or values.get("ANDROID_DATA"):
            return "android"
        return "linux"
    raise ValueError(f"Unsupported SPARKLE host platform: {value}")


def default_state_root(
    *,
    platform_name: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    values = os.environ if environ is None else environ
    platform_id = platform_name or detect_platform(environ=values)
    if platform_id not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported SPARKLE platform: {platform_id}")
    user_home = (home or Path.home()).expanduser()

    if platform_id == "windows":
        local = values.get("LOCALAPPDATA") or values.get("APPDATA")
        base = Path(local).expanduser() if local else user_home / "AppData" / "Local"
        return (base / "SPARKLE").resolve()

    if platform_id in {"macos", "ios"}:
        return (user_home / "Library" / "Application Support" / "SPARKLE").resolve()

    state_home = values.get("XDG_STATE_HOME")
    base = Path(state_home).expanduser() if state_home else user_home / ".local" / "state"
    return (base / "sparkle").resolve()


def platform_status(
    *,
    platform_name: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    platform_id = platform_name or detect_platform(environ=environ)
    desktop = platform_id in DESKTOP_PLATFORMS
    mobile = platform_id in MOBILE_PLATFORMS
    return {
        "platform": platform_id,
        "supported_platforms": sorted(SUPPORTED_PLATFORMS),
        "core_runtime": "supported" if desktop else "external_embedded_python_host_required",
        "dashboard_client": "supported",
        "filesystem_state_layout": "implemented",
        "browser": "stdlib_safe_https",
        "computer": "adapter_dependent",
        "voice": "adapter_dependent",
        "external_worker": (
            "software_supported_linux_only"
            if platform_id == "linux"
            else "external_linux_worker_required"
        ),
        "mobile_host_acceptance_required": mobile,
        "platform_verified_on_current_host": False,
    }
