from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from sparkle.contracts import ModelRequest, ModelResponse


class ModelError(RuntimeError):
    """Provider-neutral model failure with safe diagnostic metadata."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
        category: str = "provider_failure",
        attempts: int = 1,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.category = category
        self.attempts = max(1, attempts)


class UnsupportedModalityError(ModelError):
    """The selected adapter cannot consume one or more request modalities."""

    def __init__(
        self,
        modalities: set[str] | list[str] | tuple[str, ...],
        *,
        model_id: str | None = None,
        provider: str | None = None,
    ):
        self.modalities = tuple(sorted(set(modalities)))
        self.model_id = model_id
        self.provider = provider
        super().__init__(
            "Selected model adapter does not support modalities: "
            + ", ".join(self.modalities),
            retryable=False,
        )


class ModelAdapter(ABC):
    provider: str
    model_id: str
    supported_modalities = frozenset({"text"})

    def supports(self, modalities: set[str] | list[str] | tuple[str, ...]) -> bool:
        return set(modalities).issubset(self.supported_modalities)

    def validate_request(self, request: ModelRequest) -> None:
        unsupported = set(request.input_modalities) - self.supported_modalities
        if unsupported:
            raise UnsupportedModalityError(
                unsupported, model_id=self.model_id, provider=self.provider,
            )

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
