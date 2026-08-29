"""Trusted child-process entrypoint for fixed workspace unittest execution."""

from __future__ import annotations

import os
import sys
import unittest
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
    tests = workspace / "tests"
    if not tests.is_dir():
        raise ValueError("Sandbox workspace has no tests directory")
    sys.path[:] = [str(workspace), str(tests), *sys.path]
    suite = unittest.defaultTestLoader.discover(str(tests), pattern="test*.py")
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
