from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sparkle.ai_system_plan import AISystemImplementationPlanStore
from sparkle.cli import entrypoint, main
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


class AISystemImplementationPlannerTests(unittest.TestCase):
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

    @staticmethod
    def _canonical(value: dict[str, object]) -> bytes:
        return (
            json.dumps(
                value, ensure_ascii=False, separators=(",", ":"),
                sort_keys=True, allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")

    def test_prepare_is_deterministic_provider_neutral_and_non_mutating(self):
        first = self.system.ai_system_planner.prepare(valid_requirements())
        second = self.system.ai_system_planner.prepare(
            copy.deepcopy(valid_requirements())
        )
        self.assertEqual(first, second)
        self.assertEqual(
            first["protocol_version"],
            "SPARKLE-AI-SYSTEM-IMPLEMENTATION-PLAN/1",
        )
        self.assertEqual(first["status"], "prepared_static_verified")
        self.assertTrue(first["human_review_required"])
        self.assertFalse(first["human_review_completed"])
        self.assertFalse(first["source_generation_executed"])
        self.assertEqual(first["generated_source_files"], [])
        self.assertFalse(first["runtime_evaluation_executed"])
        self.assertFalse(first["external_deployment_executed"])
        self.assertNotIn("minimax", json.dumps(first).lower())
        self.assertEqual(
            first["architecture_inputs"]["model_requirements"],
            [{"capability": "reasoning", "modalities": ["text"]}],
        )
        paths = [item["path"] for item in first["proposed_source_files"]]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertIn("src/robotics_ai/system.py", paths)
        self.assertIn("tests/test_robotics_integration.py", paths)
        plan_body = dict(first)
        plan_sha256 = plan_body.pop("plan_sha256")
        self.assertEqual(
            hashlib.sha256(self._canonical(plan_body)).hexdigest(),
            plan_sha256,
        )
        self.assertEqual(self.system.ai_system_implementation_plans.list(), [])
        self.assertEqual(self.system.workspaces.list(), [])
        status = self.system.status()["ai_systems"]
        self.assertEqual(status["implementation_plans"], 0)
        self.assertEqual(
            status["implementation_plan_protocol_version"],
            "SPARKLE-AI-SYSTEM-IMPLEMENTATION-PLAN/1",
        )

        colliding = valid_requirements()
        colliding["name"] = "robotics-ai"
        colliding["evaluations"] = [
            {
                "name": "case-a", "kind": "integration",
                "criterion": "The first normalized test path remains unique.",
            },
            {
                "name": "case_a", "kind": "static_contract",
                "criterion": "The second normalized test path remains unique.",
            },
        ]
        collision_plan = self.system.ai_system_planner.prepare(colliding)
        collision_paths = [
            item["path"] for item in collision_plan["proposed_source_files"]
        ]
        self.assertIn("src/robotics_ai/system.py", collision_paths)
        self.assertEqual(len(collision_paths), len(set(collision_paths)))
        self.assertFalse(any("-" in path for path in collision_paths))

    def test_materialize_requires_approval_and_adds_only_reviewable_plan(self):
        requirements = valid_requirements()
        with self.assertRaisesRegex(ValueError, "explicit approval"):
            self.system.ai_system_planner.materialize(
                requirements, approved=False,
            )
        self.assertEqual(self.system.ai_system_implementation_plans.list(), [])

        blueprint = self.system.ai_system_builder.build(
            requirements, approved=True,
        )
        result = self.system.ai_system_planner.materialize(
            requirements, approved=True,
        )
        self.assertEqual(result["status"], "materialized_static_verified")
        self.assertTrue(result["plan_materialization_approved"])
        self.assertEqual(result["generated_source_files"], [])
        self.assertFalse(result["source_generation_executed"])
        self.assertEqual(
            [item["path"] for item in result["files"]],
            ["SPARKLE_IMPLEMENTATION_PLAN.json"],
        )
        self.assertEqual(result["workspace"], blueprint["workspace"])
        workspace = Path(result["workspace"])
        manifest = json.loads(
            (workspace / "SPARKLE_IMPLEMENTATION_PLAN.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["status"], "prepared_static_verified")
        self.assertTrue(manifest["human_review_required"])
        self.assertFalse(manifest["human_review_completed"])
        self.assertFalse(manifest["source_generation_executed"])
        self.assertFalse((workspace / "src" / "robotics_ai" / "system.py").exists())

        evidence = AISystemImplementationPlanStore().list()[0]
        self.assertEqual(evidence["system_name"], "robotics_ai")
        self.assertEqual(evidence["status"], "materialized_static_verified")
        self.assertEqual(evidence["workspace_build_id"], result["workspace_build_id"])
        self.assertNotIn("purpose", evidence)
        self.assertNotIn("workflow", evidence)
        self.assertNotIn("criterion", evidence)

    def test_invalid_and_duplicate_materialization_fail_closed(self):
        invalid = valid_requirements()
        invalid["provider"] = "minimax"
        with self.assertRaisesRegex(ValueError, "Unsupported AI system fields"):
            self.system.ai_system_planner.prepare(invalid)
        self.assertEqual(self.system.ai_system_implementation_plans.list(), [])
        self.assertEqual(self.system.workspaces.list(), [])

        requirements = valid_requirements()
        self.system.ai_system_planner.materialize(requirements, approved=True)
        with self.assertRaises(FileExistsError):
            self.system.ai_system_planner.materialize(requirements, approved=True)
        failed = self.system.ai_system_implementation_plans.list()[0]
        self.assertEqual(failed["status"], "materialization_failed")
        self.assertEqual(failed["error_type"], "FileExistsError")

    def test_cli_prepares_and_materializes_only_with_approval(self):
        source = Path(self.temp.name) / "requirements.json"
        source.write_text(json.dumps(valid_requirements()), encoding="utf-8")
        output = io.StringIO()
        error = io.StringIO()
        with (
            patch("sparkle.cli.SparkleSystem", return_value=self.system),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(error),
        ):
            self.assertEqual(main(["ai-system-plan", str(source)]), 0)
            self.assertEqual(entrypoint([
                "ai-system-plan-build", str(source),
            ]), 1)
            self.assertEqual(main([
                "ai-system-plan-build", str(source), "--approve",
            ]), 0)
        self.assertIn(
            "SPARKLE-AI-SYSTEM-IMPLEMENTATION-PLAN/1", output.getvalue(),
        )
        self.assertIn("explicit approval", error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())


class AISystemImplementationPlanStoreTests(unittest.TestCase):
    def test_retention_is_bounded_to_latest_one_thousand_records(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AISystemImplementationPlanStore(
                Path(directory) / "implementation-plans.sqlite3"
            )
            digest = "a" * 64
            for number in range(1_002):
                latest = store.create(
                    system_name=f"robotics_ai_{number}",
                    blueprint_sha256=digest,
                    plan_sha256=digest,
                    plan_bytes=100,
                )
            with store.connect() as connection:
                count = connection.execute(
                    "SELECT COUNT(*) FROM ai_system_implementation_plans"
                ).fetchone()[0]
            self.assertEqual(count, 1_000)
            self.assertEqual(store.list(limit=1)[0]["plan_id"], latest)


if __name__ == "__main__":
    unittest.main()
