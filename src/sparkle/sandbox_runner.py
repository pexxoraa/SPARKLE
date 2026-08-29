"""Trusted child-process entrypoint for fixed workspace unittest execution."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _apply_limits(timeout_seconds: int) -> None:
    try:
        import resource
    except ImportError as exc:  # pragma: no cover - the release runtime is POSIX
        raise RuntimeError("POSIX resource limits are unavailable") from exc

    memory_bytes = 512 * 1024 * 1024
    file_bytes = 10 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (timeout_seconds, timeout_seconds + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_bytes, file_bytes))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    if hasattr(resource, "RLIMIT_AS"):
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    if hasattr(resource, "RLIMIT_NPROC"):
        resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 2:
        raise ValueError("Sandbox runner requires a workspace and timeout")
    workspace = Path(arguments[0]).resolve()
    timeout_seconds = int(arguments[1])
    if not workspace.is_dir() or not 1 <= timeout_seconds <= 60:
        raise ValueError("Sandbox runner arguments are invalid")

    _apply_limits(timeout_seconds)
    os.chdir(workspace)
    command = [
        sys.executable,
        "-I",
        "-B",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test*.py",
        "-v",
    ]
    os.execve(sys.executable, command, dict(os.environ))
    return 1  # pragma: no cover - execve replaces the process


if __name__ == "__main__":
    raise SystemExit(main())
