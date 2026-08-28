from __future__ import annotations

import io
import json
from typing import Any


class FakeHTTPResponse:
    def __init__(self, value: dict[str, Any] | None = None, *, lines: list[str] | None = None):
        self.body = json.dumps(value or {}).encode("utf-8")
        self.lines = [line.encode("utf-8") for line in (lines or [])]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self.body

    def __iter__(self):
        return iter(self.lines)
