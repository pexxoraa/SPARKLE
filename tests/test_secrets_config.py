from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sparkle.config import AppConfig
from sparkle.registry import ModelRegistry
from sparkle.secrets import SecretNotFoundError, SecretResolver


class SecretTests(unittest.TestCase):
    def test_lookup_order_and_presence_only(self):
        resolver = SecretResolver({"SECOND": "secret-value"})
        self.assertEqual(resolver.first(["FIRST", "SECOND"]), "secret-value")
        self.assertEqual(resolver.status(["FIRST", "SECOND"]), {"FIRST": False, "SECOND": True})

    def test_missing_secret_names_refs_not_values(self):
        with self.assertRaisesRegex(SecretNotFoundError, "FIRST, SECOND"):
            SecretResolver({}).first(["FIRST", "SECOND"])

    def test_recursive_redaction(self):
        value = {"authorization": "Bearer secret", "nested": {"api_key": "secret", "safe": "ok"}}
        self.assertEqual(SecretResolver.redact(value)["authorization"], "[REDACTED]")
        self.assertEqual(SecretResolver.redact(value)["nested"]["api_key"], "[REDACTED]")
        self.assertEqual(SecretResolver.redact(value)["nested"]["safe"], "ok")


class ConfigTests(unittest.TestCase):
    def test_loads_app_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({
                "server": {"host": "localhost", "port": 1234},
                "orchestrator": {"max_tool_rounds": 2},
                "context": {"memory_results": 3, "knowledge_results": 4},
                "tools": {"allow_shell": False, "allow_web": False},
            }))
            config = AppConfig.load(path)
        self.assertEqual(config.port, 1234)
        self.assertFalse(config.allow_shell)

    def test_model_registry_switch_enable_add_remove(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "models.json"
            base_record = {
                "id": "one", "provider": "minimax", "model_id": "MiniMax-M3",
                "adapter": "minimax_messages", "roles": ["general"], "enabled": True,
                "base_url": "https://api.minimax.io/anthropic/v1/messages", "secret_refs": ["MINIMAX_API_KEY"],
            }
            second = {**base_record, "id": "two", "roles": ["general", "coding"]}
            path.write_text(json.dumps({"active_model": "one", "models": [base_record, second], "routing": {"default": "one"}}))
            registry = ModelRegistry(path, SecretResolver({}))
            registry.activate("two")
            self.assertEqual(registry.active_id, "two")
            registry.set_enabled("one", False)
            self.assertFalse(next(item for item in registry.list() if item["id"] == "one")["enabled"])
            third = {**base_record, "id": "three"}
            registry.add(third)
            registry.remove("three")
            self.assertNotIn("three", {item["id"] for item in registry.list()})

    def test_model_registry_rejects_secret_value_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "models.json"
            record = {
                "id": "one", "provider": "minimax", "model_id": "MiniMax-M3", "adapter": "minimax_messages",
                "roles": ["general"], "enabled": True, "base_url": "https://api.minimax.io/anthropic/v1/messages",
                "secret_refs": ["MINIMAX_API_KEY"],
            }
            path.write_text(json.dumps({"active_model": "one", "models": [record], "routing": {"default": "one"}}))
            registry = ModelRegistry(path, SecretResolver({}))
            with self.assertRaises(ValueError):
                registry.add({**record, "id": "bad", "api_key": "secret"})
