from __future__ import annotations

from sparkle.contracts import ModelRequest, ModelResponse, TokenUsage
from sparkle.model import ModelAdapter


class DeterministicAdapter(ModelAdapter):
    provider = "deterministic"
    model_id = "deterministic-test-model"
    supported_modalities = frozenset({"text", "image", "audio", "document"})

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.validate_request(request)
        latest_message = next(
            (message for message in reversed(request.messages) if message.role == "user"),
            None,
        )
        latest = latest_message.text_content if latest_message else ""
        descriptors = []
        if latest_message:
            descriptors = [
                modality for modality in latest_message.modalities if modality != "text"
            ]
        suffix = f" [{', '.join(descriptors)}]" if descriptors else ""
        return ModelResponse(
            text=f"SPARKLE processed: {latest}{suffix}",
            model=self.model_id,
            provider=self.provider,
            finish_reason="end_turn",
            usage=TokenUsage(input_tokens=len(latest.split()), output_tokens=3),
        )

    def health(self) -> dict[str, object]:
        return {"provider": self.provider, "model": self.model_id, "configured": True, "enabled": True}
