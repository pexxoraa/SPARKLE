from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sparkle.ai_system_builder import AISystemBlueprintStore
from sparkle.config import AppConfig
from sparkle.registry import ModelRegistry
from sparkle.system import SparkleSystem


def test_config() -> AppConfig:
    return AppConfig("127.0.0.1", 0, 4, 5, 5, False, False)


def valid_requirements() -> dict[str, object]:
    return {
        "name": "robotics_ai",
        "purpose": (
            "Research robotics evidence and produce bounded analytical outputs."
        ),
        "model_requirements": [{
            "capability": "reasoning",
            "modalities": ["text"],
        }],
        "agents": ["research", "data_analysis"],
        "tools": ["calculator", "knowledge_search"],
        "data_environments": [
            "knowledge_environment", "data_environment", "trace_environment",
        ],
        "interfaces": ["text", "api", "dashboard"],
        "workflow": [
            "Collect bounded evidence from approved sources.",
            "Analyze the evidence with the selected specialist agents.",
            "Return a traceable result and preserve evaluation evidence.",
        ],
        "evaluations": [{
            "name": "robotics_integration",
            "kind": "integration",
            "criterion": "The system preserves source and trace boundaries.",
        }],
        "deployment": {
            "environment_name": "staging",
            "target_kind": "server",
        },
    }


class AISystemBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {"SPARKLE_DATA_DIR": self.temp.name}, clear=False,
        )
        self.environment.start()
        self.system = SparkleSystem(
            config=test_config(), model_registry=ModelRegistry(),
        )

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def test_prepare_is_deterministic_registry_backed_and_non_mutating(self):
        requirements = valid_requirements()
        first = self.system.ai_system_builder.prepare(requirements).to_dict()
        second = self.system.ai_system_builder.prepare(
            copy.deepcopy(requirements)
        ).to_dict()
        self.assertEqual(first, second)
        self.assertEqual(first["protocol_version"], "SPARKLE-AI-SYSTEM-BLUEPRINT/1")
        route = first["architecture"]["model_routes"][0]
        self.assertEqual(route["record_id"], "nvidia-nemotron-3.5-lightning")
        self.assertEqual(route["provider"], "nvidia")
        self.assertEqual(
            route["model_id"], "nvidia/nemotron-3.5-lightning-30b-a3b",
        )
        self.assertEqual(route["modalities"], ["text"])
        self.assertFalse(first["model_calls_executed"])
        self.assertFalse(first["runtime_evaluation_executed"])
        self.assertFalse(first["external_deployment_executed"])
        self.assertEqual(self.system.ai_system_blueprints.list(), [])
        self.assertFalse(
            (Path(self.temp.name) / "applications" / "robotics_ai").exists()
        )

    def test_build_requires_approval_materializes_and_persists(self):
        requirements = valid_requirements()
        with self.assertRaisesRegex(ValueError, "explicit approval"):
            self.system.ai_system_builder.build(requirements, approved=False)
        result = self.system.ai_system_builder.build(requirements, approved=True)
        self.assertEqual(result["status"], "materialized_static_verified")
        self.assertEqual(
            [item["path"] for item in result["files"]],
            ["README.md", "SPARKLE_AI_SYSTEM.json"],
        )
        workspace = Path(result["workspace"])
        manifest = json.loads(
            (workspace / "SPARKLE_AI_SYSTEM.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], "robotics_ai")
        self.assertEqual(manifest["deployment"]["status"], "planned_unverified")
        reloaded = AISystemBlueprintStore().list()
        self.assertEqual(reloaded[0]["status"], "materialized_static_verified")
        self.assertEqual(reloaded[0]["workspace_build_id"], result["workspace_build_id"])

    def test_duplicate_build_records_safe_failure_type(self):
        requirements = valid_requirements()
        self.system.ai_system_builder.build(requirements, approved=True)
        with self.assertRaises(FileExistsError):
            self.system.ai_system_builder.build(requirements, approved=True)
        failed = self.system.ai_system_blueprints.list()[0]
        self.assertEqual(failed["status"], "materialization_failed")
        self.assertEqual(failed["error_type"], "FileExistsError")
        self.assertNotIn("error", failed)
        self.assertNotIn("Build file already exists", json.dumps(failed))

    def test_invalid_requirements_are_rejected_without_mutation(self):
        cases: list[dict[str, object]] = []
        provider_specific = valid_requirements()
        provider_specific["provider"] = "minimax"
        cases.append(provider_specific)
        unsupported_modality = valid_requirements()
        unsupported_modality["model_requirements"] = [{
            "capability": "vision", "modalities": ["image"],
        }]
        cases.append(unsupported_modality)
        duplicate_route = valid_requirements()
        duplicate_route["model_requirements"] = [
            {"capability": "reasoning", "modalities": ["text"]},
            {"capability": "reasoning", "modalities": ["text"]},
        ]
        cases.append(duplicate_route)
        unknown_agent = valid_requirements()
        unknown_agent["agents"] = ["not_installed"]
        cases.append(unknown_agent)
        unknown_tool = valid_requirements()
        unknown_tool["tools"] = ["not_registered"]
        cases.append(unknown_tool)
        inaccessible_tool = valid_requirements()
        inaccessible_tool["tools"] = ["workspace_scaffold"]
        cases.append(inaccessible_tool)
        duplicate_interface = valid_requirements()
        duplicate_interface["interfaces"] = ["text", "text"]
        cases.append(duplicate_interface)
        invalid_kind = valid_requirements()
        invalid_kind["evaluations"] = [{
            "name": "runtime", "kind": "live_provider",
            "criterion": "Call a provider.",
        }]
        cases.append(invalid_kind)
        malformed_kind = valid_requirements()
        malformed_kind["evaluations"] = [{
            "name": "runtime", "kind": ["integration"],
            "criterion": "Use the supported contract.",
        }]
        cases.append(malformed_kind)
        invalid_deployment = valid_requirements()
        invalid_deployment["deployment"] = {
            "environment_name": "production", "target_kind": "cloud_magic",
        }
        cases.append(invalid_deployment)

        for requirements in cases:
            with self.subTest(requirements=requirements):
                with self.assertRaises((ValueError, TypeError)):
                    self.system.ai_system_builder.prepare(requirements)
        self.assertEqual(self.system.ai_system_blueprints.list(), [])
        self.assertEqual(self.system.workspaces.list(), [])

    def test_store_retains_only_latest_one_thousand_attempts(self):
        blueprint = self.system.ai_system_builder.prepare(valid_requirements())
        store = self.system.ai_system_blueprints
        for number in range(1_002):
            requirements = valid_requirements()
            requirements["name"] = f"robotics_ai_{number}"
            store.create(requirements, blueprint)
        with store.connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM ai_system_blueprints"
            ).fetchone()[0]
            earliest = connection.execute(
                "SELECT MIN(id) FROM ai_system_blueprints"
            ).fetchone()[0]
        self.assertEqual(count, 1_000)
        self.assertEqual(earliest, 3)
        self.assertEqual(len(store.list(limit=10_000)), 100)


if __name__ == "__main__":
    unittest.main()
