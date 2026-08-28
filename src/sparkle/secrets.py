from __future__ import annotations

import os
from collections.abc import Iterable


class SecretNotFoundError(RuntimeError):
    pass


class SecretResolver:
    """Resolves secrets by reference without exposing or persisting values."""

    def __init__(self, environ: dict[str, str] | None = None):
        self._environ = environ if environ is not None else os.environ

    def first(self, references: Iterable[str]) -> str:
        checked: list[str] = []
        for reference in references:
            checked.append(reference)
            value = self._environ.get(reference)
            if value:
                return value
        joined = ", ".join(checked)
        raise SecretNotFoundError(f"Required secret is not configured; checked: {joined}")

    def status(self, references: Iterable[str]) -> dict[str, bool]:
        return {reference: bool(self._environ.get(reference)) for reference in references}

    @staticmethod
    def redact(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: ("[REDACTED]" if any(token in key.lower() for token in ("key", "token", "secret", "authorization")) else SecretResolver.redact(item))
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [SecretResolver.redact(item) for item in value]
        return value
