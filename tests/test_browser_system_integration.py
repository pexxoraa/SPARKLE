from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from sparkle.browser_runtime import SafeHTTPSBrowserAdapter
from sparkle.config import AppConfig
from sparkle.providers.mock import DeterministicAdapter
from sparkle.registry import ModelRegistry
from sparkle.system import SparkleSystem


def test_config() -> AppConfig:
    return AppConfig("127.0.0.1", 0, 4, 5, 5, False, False)


class BrowserSystemIntegrationTests(unittest.TestCase):
    def test_system_uses_safe_browser_without_claiming_live_verification(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False
        ):
            registry = ModelRegistry()
            registry.inject(registry.active_id, DeterministicAdapter())
            system = SparkleSystem(config=test_config(), model_registry=registry)
            self.assertIsInstance(
                system.interactions.browser, SafeHTTPSBrowserAdapter
            )
            status = system.status()["interaction"]
            self.assertEqual(status["browser"], "configured")
            self.assertFalse(status["live_browser_verified"])
            self.assertEqual(status["computer"], "externally_unconfigured")
            self.assertFalse(status["agent_tool_registered"])


if __name__ == "__main__":
    unittest.main()
