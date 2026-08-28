from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from sparkle.contracts import ModelRequest, ModelResponse


class ModelError(RuntimeError):
    """Provider-neutral model failure with safe diagnostic metadata."""

    def __init__(self, message: str, *, retryable: bool = False, status_code: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


class ModelAdapter(ABC):
    provider: str
    model_id: str

    @abstractmethod
    def complete(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError

    def stream(self, request: ModelRequest) -> Iterator[str]:
        response = self.complete(request)
        if response.text:
            yield response.text

    @abstractmethod
    def health(self) -> dict[str, object]:
        raise NotImplementedError
