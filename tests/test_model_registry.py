from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sparkle.contracts import Message, ModelRequest, ModelResponse, TokenUsage
from sparkle.model import ModelAdapter, UnsupportedModalityError
from sparkle.registry import ModelRegistry, ModelRouter
from sparkle.secrets import SecretResolver


class LocalAdapter(ModelAdapter):
    provider = "local"
    supported_modalities = frozenset({"text"})

    def __init__(self, config, _secrets):
        self.model_id = config["model_id"]

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.validate_request(request)
        return ModelResponse(
            text="local response",
            model=self.model_id,
            provider=self.provider,
            finish_reason="complete",
            usage=TokenUsage(),
        )

    def health(self):
        return {
            "provider": self.provider,
            "model": self.model_id,
            "configured": True,
            "enabled": True,
        }


def record(record_id: str, *, roles=None, modalities=None):
    return {
        "id": record_id,
        "provider": "local",
        "model_id": f"local-{record_id}",
        "adapter": "local_adapter",
        "roles": roles or ["general"],
        "modalities": modalities or ["text"],
        "enabled": True,
        "secret_refs": [],
    }


class ModelRegistryContractTests(unittest.TestCase):
    def registry(self, value):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "models.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        registry = ModelRegistry(
            path,
            SecretResolver({}),
            adapter_factories={"local_adapter": LocalAdapter},
        )
        return registry

    def test_external_factory_is_provider_neutral_and_identity_bound(self):
        registry = self.registry({
            "active_model": "primary",
            "models": [record("primary")],
            "routing": {"default": "primary", "general": "primary"},
        })
        selected_id, adapter = ModelRouter(registry).select_with_record("general")
        response = adapter.complete(ModelRequest(messages=[Message("user", "hello")]))
        self.assertEqual(selected_id, "primary")
        self.assertEqual(response.provider, "local")
        self.assertEqual(registry.list()[0]["adapter"], "local_adapter")
        self.assertTrue(registry.list()[0]["configured"])

        class WrongIdentity(LocalAdapter):
            provider = "wrong"

        bad = self.registry({
            "active_model": "bad",
            "models": [record("bad")],
            "routing": {"default": "bad", "general": "bad"},
        })
        bad._adapter_factories["local_adapter"] = WrongIdentity
        with self.assertRaisesRegex(ValueError, "identity"):
            bad.adapter()

    def test_registry_schema_and_routing_fail_closed(self):
        base = {
            "active_model": "primary",
            "models": [record("primary")],
            "routing": {"default": "primary", "general": "primary"},
        }
        invalid_values = [
            {**base, "models": [{**record("primary"), "enabled": "true"}]},
            {**base, "models": [{**record("primary"), "roles": ["general", "general"]}]},
            {**base, "models": [{**record("primary"), "secret_refs": ["bad-ref"]}]},
            {**base, "models": [{**record("primary"), "nested": {"api_key": "value"}}]},
            {**base, "routing": {"default": "missing"}},
            {**base, "routing": {"coding": "primary"}},
        ]
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.registry(value)

    def test_failed_disable_and_remove_are_transactional(self):
        registry = self.registry({
            "active_model": "primary",
            "models": [
                record("primary"),
                record("coding", roles=["coding"]),
            ],
            "routing": {
                "default": "primary",
                "general": "primary",
                "coding": "coding",
            },
        })
        with self.assertRaisesRegex(ValueError, "routing"):
            registry.set_enabled("coding", False)
        self.assertTrue(registry.record("coding").enabled)
        with self.assertRaisesRegex(ValueError, "routing"):
            registry.remove("coding")
        self.assertEqual(registry.record("coding").id, "coding")

    def test_declared_modalities_and_deterministic_fallback_are_enforced(self):
        registry = self.registry({
            "active_model": "text",
            "models": [
                record("text", roles=["general", "reasoning"]),
                record("zeta", roles=["reasoning"]),
                record("alpha", roles=["reasoning"]),
            ],
            "routing": {"default": "text", "general": "text"},
        })

        class AllModalities(LocalAdapter):
            supported_modalities = frozenset({"text", "image", "audio", "document"})

        registry._adapter_factories["local_adapter"] = AllModalities
        with self.assertRaises(UnsupportedModalityError):
            ModelRouter(registry).select("reasoning", modalities={"text", "image"})

        fallback = self.registry({
            "active_model": "text",
            "models": [
                record("text", roles=["general"]),
                record("zeta", roles=["reasoning"]),
                record("alpha", roles=["reasoning"]),
            ],
            "routing": {"default": "text", "general": "text"},
        })
        selected_id, _adapter = ModelRouter(fallback).select_with_record("reasoning")
        self.assertEqual(selected_id, "alpha")


if __name__ == "__main__":
    unittest.main()
