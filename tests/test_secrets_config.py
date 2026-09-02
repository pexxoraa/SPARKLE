from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from sparkle.config import AppConfig
from sparkle import config as sparkle_config
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
    def test_installed_default_uses_xdg_state_root(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.dict(os.environ, {"XDG_STATE_HOME": directory}, clear=True),
                patch.object(
                    sparkle_config,
                    "project_root",
                    return_value=Path(directory) / "no-checkout",
                ),
            ):
                self.assertEqual(
                    sparkle_config.data_root(), Path(directory) / "sparkle",
                )

    def test_packaged_defaults_match_checkout_and_materialize_when_installed(self):
        root = Path(__file__).resolve().parents[1]
        bundled_application = (
            root / "src/sparkle/defaults/application/config.json"
        )
        bundled_models = (
            root
            / "src/sparkle/defaults/ai_environment/configurations/models.json"
        )
        self.assertEqual(
            json.loads(bundled_application.read_text(encoding="utf-8")),
            json.loads((root / "application/config.json").read_text(encoding="utf-8")),
        )
        self.assertEqual(
            json.loads(bundled_models.read_text(encoding="utf-8")),
            json.loads(
                (root / "ai_environment/configurations/models.json").read_text(
                    encoding="utf-8"
                )
            ),
        )

        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            with (
                patch.dict(os.environ, {"SPARKLE_DATA_DIR": directory}, clear=True),
                patch.object(
                    sparkle_config, "project_root", return_value=runtime / "no-checkout",
                ),
            ):
                config = AppConfig.load()
                registry = ModelRegistry()
            application_path = runtime / "application/config.json"
            model_path = runtime / "ai_environment/configurations/models.json"
            self.assertEqual(config.port, 8765)
            self.assertEqual(
                registry.active_id, "nvidia-nemotron-3.5-lightning",
            )
            self.assertEqual(registry.path, model_path)
            self.assertTrue(application_path.is_file())
            self.assertTrue(model_path.is_file())
            self.assertEqual(stat.S_IMODE(application_path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(model_path.stat().st_mode), 0o600)

    def test_loads_app_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({
                "server": {"host": "localhost", "port": 1234},
                "orchestrator": {"max_tool_rounds": 2},
                "context": {"memory_results": 3, "knowledge_results": 4},
                "tools": {"allow_shell": False, "allow_web": False},
                "security": {
                    "api_auth_required": False,
                    "api_token_refs": ["SPARKLE_API_TOKEN"],
                    "allowed_origins": ["https://console.example"],
                    "rate_limit_requests": 80,
                    "rate_limit_window_seconds": 30,
                    "session_auth_enabled": True,
                    "session_cookie_secure": False,
                    "session_ttl_seconds": 900,
                    "session_max_active": 16,
                },
                "development": {
                    "workspace_tests_enabled": False,
                    "workspace_test_timeout_seconds": 12,
                    "external_worker_enabled": False,
                    "external_worker_url": "",
                    "external_worker_secret_refs": ["WORKER_KEY"],
                    "external_worker_id": "worker-primary",
                    "external_worker_request_timeout_seconds": 22,
                    "external_worker_job_timeout_seconds": 14,
                    "external_worker_max_payload_bytes": 7000000,
                },
            }))
            with patch.dict("os.environ", {
                "SPARKLE_API_AUTH_REQUIRED": "true",
                "SPARKLE_SESSION_COOKIE_SECURE": "true",
                "SPARKLE_WORKSPACE_TESTS_ENABLED": "true",
                "SPARKLE_EXTERNAL_WORKER_ENABLED": "true",
                "SPARKLE_EXTERNAL_WORKER_URL": "https://worker.example/jobs",
            }):
                config = AppConfig.load(path)
        self.assertEqual(config.port, 1234)
        self.assertFalse(config.allow_shell)
        self.assertTrue(config.api_auth_required)
        self.assertEqual(config.api_token_refs, ("SPARKLE_API_TOKEN",))
        self.assertEqual(config.allowed_origins, ("https://console.example",))
        self.assertEqual(config.api_rate_limit_requests, 80)
        self.assertEqual(config.api_rate_limit_window_seconds, 30)
        self.assertTrue(config.session_auth_enabled)
        self.assertTrue(config.session_cookie_secure)
        self.assertEqual(config.session_ttl_seconds, 900)
        self.assertEqual(config.session_max_active, 16)
        self.assertTrue(config.workspace_tests_enabled)
        self.assertEqual(config.workspace_test_timeout_seconds, 12)
        self.assertTrue(config.external_worker_enabled)
        self.assertEqual(config.external_worker_url, "https://worker.example/jobs")
        self.assertEqual(config.external_worker_secret_refs, ("WORKER_KEY",))
        self.assertEqual(config.external_worker_id, "worker-primary")
        self.assertEqual(config.external_worker_request_timeout_seconds, 22)
        self.assertEqual(config.external_worker_job_timeout_seconds, 14)
        self.assertEqual(config.external_worker_max_payload_bytes, 7000000)

    def test_rejects_invalid_api_rate_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({
                "server": {"host": "localhost", "port": 1234},
                "orchestrator": {"max_tool_rounds": 2},
                "context": {"memory_results": 3, "knowledge_results": 4},
                "tools": {"allow_shell": False, "allow_web": False},
                "security": {"rate_limit_requests": 0},
            }))
            with self.assertRaisesRegex(ValueError, "from 1 to 10000"):
                AppConfig.load(path)

    def test_rejects_invalid_session_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({
                "server": {"host": "localhost", "port": 1234},
                "orchestrator": {"max_tool_rounds": 2},
                "context": {"memory_results": 3, "knowledge_results": 4},
                "tools": {"allow_shell": False, "allow_web": False},
                "security": {"session_ttl_seconds": 59},
            }))
            with self.assertRaisesRegex(ValueError, "from 60 to 86400"):
                AppConfig.load(path)

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
