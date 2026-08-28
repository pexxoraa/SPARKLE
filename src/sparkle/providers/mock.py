from __future__ import annotations

from sparkle.contracts import ModelRequest, ModelResponse, TokenUsage
from sparkle.model import ModelAdapter


class DeterministicAdapter(ModelAdapter):
    provider = "deterministic"
    model_id = "deterministic-test-model"

    def complete(self, request: ModelRequest) -> ModelResponse:
        latest = next((message.content for message in reversed(request.messages) if message.role == "user"), "")
        return ModelResponse(
            text=f"SPARKLE processed: {latest}",
            model=self.model_id,
            provider=self.provider,
            finish_reason="end_turn",
            usage=TokenUsage(input_tokens=len(latest.split()), output_tokens=3),
        )

    def health(self) -> dict[str, object]:
        return {"provider": self.provider, "model": self.model_id, "configured": True, "enabled": True}
