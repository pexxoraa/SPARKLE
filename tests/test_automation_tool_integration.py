from __future__ import annotations

import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sparkle.config import AppConfig
from sparkle.providers.mock import DeterministicAdapter
from sparkle.registry import ModelRegistry
from sparkle.system import SparkleSystem


def test_config() -> AppConfig:
    return AppConfig("127.0.0.1", 0, 4, 5, 5, False, False)


class AutomationToolIntegrationTests(unittest.TestCase):
    def test_automation_agent_can_inspect_but_not_mutate_automations(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False
        ):
            registry = ModelRegistry()
            registry.inject(registry.active_id, DeterministicAdapter())
            system = SparkleSystem(config=test_config(), model_registry=registry)
            now = datetime.now(UTC)
            automation_id = system.automations.create(
                "Inspection target",
                "once",
                {"type": "agent", "prompt": "Inspect me", "agent": "automation"},
                next_run_at=(now + timedelta(hours=1)).isoformat(),
            )

            spec = system.agents.get("automation")
            self.assertIn("automation_inspect", spec.tools)
            definition_names = {
                definition.name
                for definition in system.tools.definitions(set(spec.tools))
            }
            self.assertIn("automation_inspect", definition_names)

            result = system.tools.execute(
                "automation_inspect",
                {"automation_id": automation_id, "limit": 10},
                allowed=set(spec.tools),
            )
            self.assertTrue(result["read_only"])
            self.assertTrue(result["mutation_requires_operator_interface"])
            self.assertEqual(result["automations"][0]["id"], automation_id)
            self.assertEqual(result["recent_runs"], [])
            self.assertEqual(result["recent_attempts"], [])

            with self.assertRaises(Exception):
                system.tools.execute(
                    "automation_delete",
                    {"automation_id": automation_id},
                    allowed=set(spec.tools),
                )
            self.assertEqual(
                system.tools.execute(
                    "automation_inspect",
                    {"automation_id": automation_id},
                    allowed=set(spec.tools),
                )["automations"][0]["id"],
                automation_id,
            )


if __name__ == "__main__":
    unittest.main()
