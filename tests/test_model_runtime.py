from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sparkle.contracts import Message, ModelRequest, ModelResponse, TokenUsage, ToolDefinition
from sparkle.model import ModelAdapter, ModelError, UnsupportedModalityError
from sparkle.model_runtime import ModelRuntimeStore
from sparkle.registry import ModelRegistry, ModelRouter
from sparkle.secrets import SecretResolver


class RuntimeAdapter(ModelAdapter):
    provider = "local"

    def __init__(self, config, _secrets):
        self.model_id = config["model_id"]
        self.failure = config.get("failure")
        self.report_usage = bool(config.get("report_usage", True))

    def complete(self, request):
        self.validate_request(request)
        if self.failure:
            raise ModelError(
                "safe failure", retryable=self.failure == "connectivity_failure",
                category=self.failure, attempts=2,
            )
        return ModelResponse(
            text="ok", model=self.model_id, provider=self.provider,
            finish_reason="stop", usage=TokenUsage(7, 3),
            usage_reported=self.report_usage, attempts=2,
            provider_request_id="provider-request",
        )

    def health(self):
        return {"configured": True}


def record(record_id, *, roles=None, secret_refs=None, **extra):
    return {
        "id": record_id,
        "provider": "local",
        "model_id": f"model-{record_id}",
        "adapter": "runtime",
        "roles": roles or ["general", "tool_use"],
        "modalities": ["text"],
        "enabled": True,
        "secret_refs": secret_refs or [],
        **extra,
    }


class ModelRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def registry(self, models, routing, *, secrets=None):
        root = Path(self.directory.name)
        path = root / f"models-{len(list(root.glob('models-*.json')))}.json"
        path.write_text(json.dumps({
            "active_model": models[0]["id"], "models": models, "routing": routing,
        }), encoding="utf-8")
        runtime = ModelRuntimeStore(root / f"runtime-{path.stem}.sqlite3")
        return ModelRegistry(
            path, SecretResolver(secrets or {}),
            adapter_factories={"runtime": RuntimeAdapter},
            runtime_store=runtime,
        )

    def test_health_requires_runtime_evidence_not_configuration_alone(self):
        registry = self.registry(
            [record("primary", secret_refs=["NVIDIA_API_KEY"])],
            {"default": "primary", "general": "primary"},
        )
        self.assertEqual(registry.list()[0]["health"], "UNAVAILABLE")
        self.assertEqual(registry.list()[0]["health_reason"], "configuration_failure")

        configured = self.registry(
            [record("primary", secret_refs=["NVIDIA_API_KEY"])],
            {"default": "primary", "general": "primary"},
            secrets={"NVIDIA_API_KEY": "not-recorded"},
        )
        self.assertEqual(configured.list()[0]["health"], "DEGRADED")
        decision, response = ModelRouter(configured).complete(
            ModelRequest(messages=[Message("user", "hello")]), "general",
        )
        self.assertEqual(decision.health, "DEGRADED")
        self.assertEqual(response.text, "ok")
        self.assertEqual(configured.list()[0]["health"], "HEALTHY")
        self.assertNotIn("not-recorded", json.dumps(configured.runtime.recent()))

    def test_policy_filters_capability_tools_and_streaming(self):
        registry = self.registry([
            record("primary", roles=["general"], supports_streaming=False),
            record("coding", roles=["coding", "tool_use"], supports_streaming=True),
        ], {"default": "primary", "general": "primary", "coding": "coding"})
        router = ModelRouter(registry)
        decision, _ = router.decide(
            "coding", tools_required=True, streaming_required=True,
        )
        self.assertEqual(decision.record_id, "coding")
        with self.assertRaises(UnsupportedModalityError):
            router.decide("general", tools_required=True)

    def test_policy_applies_latency_and_timeout_constraints(self):
        registry = self.registry([
            record("deep", latency_class="deep", timeout_seconds=90),
            record("fast", latency_class="fast", timeout_seconds=10),
        ], {"default": "deep", "general": "deep"})
        decision, _ = ModelRouter(registry).decide(
            "general", latency_policy="fast", max_timeout_seconds=20,
        )
        self.assertEqual(decision.record_id, "fast")
        with self.assertRaises(ValueError):
            ModelRouter(registry).decide("general", latency_policy="instant")
        with self.assertRaises(UnsupportedModalityError):
            ModelRouter(registry).decide(
                "general", max_timeout_seconds=5,
            )

    def test_failure_falls_back_and_records_retry_usage_and_reason(self):
        registry = self.registry([
            record("primary", failure="connectivity_failure"),
            record("fallback", allow_fallback=True),
        ], {"default": "primary", "general": "primary"})
        decision, response = ModelRouter(registry).complete(
            ModelRequest(messages=[Message("user", "hello")]), "general",
        )
        self.assertTrue(decision.fallback)
        self.assertEqual(decision.record_id, "fallback")
        evidence = registry.runtime.recent()
        self.assertEqual(evidence[0]["status"], "success")
        self.assertEqual(evidence[0]["attempts"], 2)
        self.assertEqual(evidence[0]["input_tokens"], 7)
        self.assertEqual(evidence[1]["status"], "failure")
        self.assertEqual(evidence[1]["attempts"], 2)
        self.assertEqual(evidence[1]["error_type"], "connectivity_failure")
        self.assertEqual(response.provider_request_id, "provider-request")

    def test_missing_usage_remains_unknown(self):
        registry = self.registry(
            [record("primary", report_usage=False)],
            {"default": "primary", "general": "primary"},
        )
        ModelRouter(registry).complete(
            ModelRequest(messages=[Message("user", "hello")]), "general",
        )
        evidence = registry.runtime.recent()[0]
        self.assertIsNone(evidence["input_tokens"])
        self.assertIsNone(evidence["output_tokens"])

    def test_authentication_failure_becomes_unavailable(self):
        registry = self.registry(
            [record("primary", failure="authentication_failure")],
            {"default": "primary", "general": "primary"},
        )
        with self.assertRaises(ModelError):
            ModelRouter(registry).complete(
                ModelRequest(messages=[Message("user", "hello")]), "general",
            )
        status = registry.list()[0]
        self.assertEqual(status["health"], "UNAVAILABLE")
        self.assertEqual(status["health_reason"], "authentication_failure")


if __name__ == "__main__":
    unittest.main()
