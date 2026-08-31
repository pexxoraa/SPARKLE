from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sparkle.cli import entrypoint, main
from sparkle.config import AppConfig
from sparkle.contracts import ModelRequest, ModelResponse, TokenUsage
from sparkle.model import ModelAdapter
from sparkle.registry import ModelRegistry
from sparkle.system import SparkleSystem


def test_config() -> AppConfig:
    return AppConfig("127.0.0.1", 0, 4, 5, 5, False, False)


def valid_requirements(name: str = "robotics_ai") -> dict[str, object]:
    return {
        "name": name,
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


class CandidateAdapter(ModelAdapter):
    provider = "candidate-provider"
    model_id = "candidate-model-v1"

    def __init__(self):
        self.payload = ""
        self.response_provider = self.provider
        self.response_model = self.model_id
        self.calls = 0

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.validate_request(request)
        self.calls += 1
        return ModelResponse(
            text=self.payload,
            model=self.response_model,
            provider=self.response_provider,
            finish_reason="end_turn",
            usage=TokenUsage(100, 20),
        )

    def health(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model_id,
            "configured": True,
            "enabled": True,
        }


class AISystemSourceCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {"SPARKLE_DATA_DIR": self.temp.name}, clear=False,
        )
        self.environment.start()
        self.registry = ModelRegistry()
        self.adapter = CandidateAdapter()
        self.registry.inject(self.registry.active_id, self.adapter)
        self.system = SparkleSystem(
            config=test_config(), model_registry=self.registry,
        )

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    @staticmethod
    def _valid_files(name: str) -> list[dict[str, str]]:
        return [{
            "path": f"src/{name}/system.py",
            "content": (
                "def build_system():\n"
                "    return {\"status\": \"candidate\"}\n"
            ),
        }]

    def _payload(
        self,
        plan_sha256: str,
        files: list[dict[str, str]],
    ) -> str:
        return json.dumps({
            "protocol_version": "SPARKLE-AI-SYSTEM-SOURCE-CANDIDATE/1",
            "plan_sha256": plan_sha256,
            "files": files,
        })

    def _approved_disclosure(
        self,
        requirements: dict[str, object],
    ) -> tuple[dict[str, object], dict[str, object]]:
        plan = self.system.ai_system_planner.materialize(
            requirements, approved=True,
        )
        reviewed = self.system.ai_system_source_candidates.review_plan(
            plan["plan_id"], approved=True,
        )
        self.assertEqual(reviewed["review_status"], "approved_for_generation")
        disclosure = self.system.ai_system_source_candidates.prepare_disclosure(
            plan["plan_id"],
            requirements,
            generation_task="Generate the declared provider-neutral core system module.",
        )
        disclosure = self.system.ai_system_source_candidates.approve_disclosure(
            disclosure["disclosure_id"], approved=True,
        )
        return plan, disclosure

    def _generate(
        self,
        requirements: dict[str, object],
        files: list[dict[str, str]] | None = None,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        plan, disclosure = self._approved_disclosure(requirements)
        self.adapter.payload = self._payload(
            plan["plan_sha256"],
            files or self._valid_files(str(requirements["name"])),
        )
        candidate = self.system.ai_system_source_candidates.generate(
            plan["plan_id"], requirements, disclosure["disclosure_id"],
            approved=True,
        )
        return plan, disclosure, candidate

    def test_provider_disclosure_is_separate_approved_and_content_free(self):
        requirements = valid_requirements()
        plan = self.system.ai_system_planner.materialize(
            requirements, approved=True,
        )
        with self.assertRaisesRegex(ValueError, "explicit approval"):
            self.system.ai_system_source_candidates.review_plan(
                plan["plan_id"], approved=False,
            )
        self.system.ai_system_source_candidates.review_plan(
            plan["plan_id"], approved=True,
        )
        disclosure = self.system.ai_system_source_candidates.prepare_disclosure(
            plan["plan_id"], requirements,
            generation_task="Generate the declared provider-neutral core system module.",
        )
        self.assertEqual(disclosure["status"], "disclosure_pending")
        self.assertEqual(disclosure["provider"], self.adapter.provider)
        self.assertEqual(disclosure["model"], self.adapter.model_id)
        self.assertEqual(disclosure["model_identifier"], self.registry.active_id)
        self.adapter.payload = self._payload(
            plan["plan_sha256"], self._valid_files("robotics_ai"),
        )
        with self.assertRaisesRegex(ValueError, "Approved provider disclosure"):
            self.system.ai_system_source_candidates.generate(
                plan["plan_id"], requirements, disclosure["disclosure_id"],
                approved=True,
            )
        with self.assertRaisesRegex(ValueError, "explicit approval"):
            self.system.ai_system_source_candidates.approve_disclosure(
                disclosure["disclosure_id"], approved=False,
            )
        self.system.ai_system_source_candidates.approve_disclosure(
            disclosure["disclosure_id"], approved=True,
        )
        candidate = self.system.ai_system_source_candidates.generate(
            plan["plan_id"], requirements, disclosure["disclosure_id"],
            approved=True,
        )
        evidence = self.system.source_provider_disclosures.get(
            disclosure["disclosure_id"],
        )
        self.assertEqual(evidence["generation_status"], "generated")
        self.assertEqual(evidence["candidate_id"], candidate["candidate_id"])
        self.assertEqual(evidence["files_generated"], ["src/robotics_ai/system.py"])
        self.assertFalse(evidence["credentials_included"])
        self.assertNotIn("build_system", json.dumps(evidence))
        with self.system.source_provider_disclosures.connect() as connection:
            columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(source_provider_disclosures)"
                ).fetchall()
            }
        self.assertNotIn("content", columns)

    def test_valid_candidate_requires_review_verification_and_approval(self):
        requirements = valid_requirements()
        _, _, candidate = self._generate(requirements)
        candidate_id = candidate["candidate_id"]
        self.assertEqual(candidate["status"], "generated_human_review_required")
        self.assertFalse(candidate["human_review_completed"])
        self.assertFalse(candidate["static_verification_executed"])
        self.assertFalse(candidate["runtime_tests_executed"])
        self.assertFalse(candidate["external_worker_called"])
        self.assertFalse(candidate["production_source_modified"])
        self.assertFalse(candidate["external_deployment_executed"])
        candidate_root = Path(candidate["workspace"])
        self.assertEqual(
            candidate_root.parent,
            Path(self.temp.name) / "candidate_environment" / "source_candidates",
        )
        production_path = (
            Path(self.temp.name) / "applications" / "robotics_ai"
            / "src" / "robotics_ai" / "system.py"
        )
        self.assertFalse(production_path.exists())
        with self.assertRaisesRegex(ValueError, "statically verified"):
            self.system.ai_system_source_candidates.approve(
                candidate_id, approved=True,
            )
        with self.assertRaisesRegex(ValueError, "explicit confirmation"):
            self.system.ai_system_source_candidates.review(
                candidate_id, decision="accept", notes="Reviewed source.",
                approved=False,
            )
        reviewed = self.system.ai_system_source_candidates.review(
            candidate_id,
            decision="accept",
            notes="Reviewed the bounded source and accepted it for static checks.",
            approved=True,
        )
        self.assertEqual(reviewed["status"], "reviewed")
        verified = self.system.ai_system_source_candidates.verify(
            candidate_id, requirements,
        )
        self.assertEqual(verified["status"], "statically_verified")
        self.assertEqual(verified["static_verification"]["status"], "passed")
        self.assertFalse(verified["static_verification"]["runtime_tests_executed"])
        with self.assertRaisesRegex(ValueError, "explicit approval"):
            self.system.ai_system_source_candidates.approve(
                candidate_id, approved=False,
            )
        approved = self.system.ai_system_source_candidates.approve(
            candidate_id, approved=True,
        )
        self.assertEqual(approved["status"], "approved")
        self.assertFalse(approved["runtime_tests_executed"])
        self.assertFalse(production_path.exists())
        self.assertEqual(
            [item["state"] for item in approved["lifecycle"]],
            [
                "generating", "generated_human_review_required", "reviewed",
                "statically_verified", "approved",
            ],
        )

    def test_missing_and_incorrect_provider_metadata_fail_closed(self):
        cases = [
            ("missing_metadata_ai", "", self.adapter.model_id, "missing"),
            ("wrong_metadata_ai", "wrong-provider", self.adapter.model_id, "incorrect"),
            ("wrong_model_ai", self.adapter.provider, "wrong-model", "incorrect"),
        ]
        for name, provider, model, message in cases:
            with self.subTest(name=name):
                requirements = valid_requirements(name)
                plan, disclosure = self._approved_disclosure(requirements)
                self.adapter.payload = self._payload(
                    plan["plan_sha256"], self._valid_files(name),
                )
                self.adapter.response_provider = provider
                self.adapter.response_model = model
                with self.assertRaisesRegex(ValueError, message):
                    self.system.ai_system_source_candidates.generate(
                        plan["plan_id"], requirements,
                        disclosure["disclosure_id"], approved=True,
                    )
                failed = self.system.source_candidates.list(limit=1)[0]
                self.assertEqual(failed["status"], "generation_failed")
                self.assertEqual(
                    self.system.source_provider_disclosures.get(
                        disclosure["disclosure_id"]
                    )["generation_status"],
                    "failed",
                )
                self.adapter.response_provider = self.adapter.provider
                self.adapter.response_model = self.adapter.model_id

    def test_malformed_invalid_path_and_plan_mismatch_generation_fail(self):
        cases = [
            ("malformed_ai", "not-json", "exact JSON"),
            (
                "invalid_path_ai",
                json.dumps({
                    "protocol_version": "SPARKLE-AI-SYSTEM-SOURCE-CANDIDATE/1",
                    "plan_sha256": "PLACEHOLDER",
                    "files": [{"path": "../escape.py", "content": "pass\n"}],
                }),
                "not declared",
            ),
            (
                "mismatched_plan_ai",
                json.dumps({
                    "protocol_version": "SPARKLE-AI-SYSTEM-SOURCE-CANDIDATE/1",
                    "plan_sha256": "0" * 64,
                    "files": [{
                        "path": "src/mismatched_plan_ai/system.py",
                        "content": "pass\n",
                    }],
                }),
                "digest does not match",
            ),
        ]
        for name, payload, message in cases:
            with self.subTest(name=name):
                requirements = valid_requirements(name)
                plan, disclosure = self._approved_disclosure(requirements)
                self.adapter.payload = payload.replace(
                    "PLACEHOLDER", str(plan["plan_sha256"]),
                )
                with self.assertRaisesRegex(ValueError, message):
                    self.system.ai_system_source_candidates.generate(
                        plan["plan_id"], requirements,
                        disclosure["disclosure_id"], approved=True,
                    )
                self.assertEqual(
                    self.system.source_candidates.list(limit=1)[0]["status"],
                    "generation_failed",
                )

    def test_static_verification_failure_and_rejected_review_do_not_approve(self):
        requirements = valid_requirements("unsafe_candidate_ai")
        _, _, candidate = self._generate(requirements, [{
            "path": "src/unsafe_candidate_ai/system.py",
            "content": "def unsafe(:\n    return eval('1 + 1')\n",
        }])
        candidate_id = candidate["candidate_id"]
        self.system.ai_system_source_candidates.review(
            candidate_id, decision="accept",
            notes="Reviewed and sent to static verification.", approved=True,
        )
        failed = self.system.ai_system_source_candidates.verify(
            candidate_id, requirements,
        )
        self.assertEqual(failed["status"], "static_verification_failed")
        self.assertGreater(failed["static_verification"]["failed"], 0)
        self.assertFalse(failed["runtime_tests_executed"])
        with self.assertRaisesRegex(ValueError, "statically verified"):
            self.system.ai_system_source_candidates.approve(
                candidate_id, approved=True,
            )

        rejected_requirements = valid_requirements("rejected_candidate_ai")
        _, _, rejected = self._generate(rejected_requirements)
        rejected = self.system.ai_system_source_candidates.review(
            rejected["candidate_id"], decision="reject",
            notes="Human reviewer rejected the proposed implementation.",
            approved=True,
        )
        self.assertEqual(rejected["status"], "review_rejected")
        self.assertTrue(rejected["human_review_completed"])
        with self.assertRaisesRegex(ValueError, "human-reviewed"):
            self.system.ai_system_source_candidates.verify(
                rejected["candidate_id"], rejected_requirements,
            )

    def test_plan_candidate_mismatch_and_candidate_isolation_tamper_fail(self):
        requirements = valid_requirements("isolated_candidate_ai")
        _, _, candidate = self._generate(requirements)
        candidate_id = candidate["candidate_id"]
        with self.assertRaisesRegex(ValueError, "not declared"):
            self.system.ai_system_source_candidates.read_file(
                candidate_id, "../outside.py",
            )
        self.system.ai_system_source_candidates.review(
            candidate_id, decision="accept", notes="Reviewed isolated source.",
            approved=True,
        )
        changed = valid_requirements("isolated_candidate_ai")
        changed["purpose"] = "A materially different approved purpose."
        with self.assertRaisesRegex(ValueError, "do not match"):
            self.system.ai_system_source_candidates.verify(candidate_id, changed)
        candidate_path = (
            Path(candidate["workspace"])
            / "src" / "isolated_candidate_ai" / "system.py"
        )
        outside = Path(self.temp.name) / "outside.py"
        outside.write_text("pass\n", encoding="utf-8")
        candidate_path.unlink()
        candidate_path.symlink_to(outside)
        failed = self.system.ai_system_source_candidates.verify(
            candidate_id, requirements,
        )
        self.assertEqual(failed["status"], "static_verification_failed")
        self.assertEqual(
            failed["static_verification"]["checks"][0]["type"],
            "candidate_isolation",
        )

    def test_manifest_digest_tamper_fails_static_verification(self):
        requirements = valid_requirements("digest_tamper_ai")
        _, _, candidate = self._generate(requirements)
        candidate_id = candidate["candidate_id"]
        self.system.ai_system_source_candidates.review(
            candidate_id, decision="accept", notes="Reviewed bounded source.",
            approved=True,
        )
        manifest_path = Path(candidate["workspace"]) / "SPARKLE_SOURCE_CANDIDATE.json"
        manifest_path.chmod(0o600)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["candidate_sha256"] = "0" * 64
        manifest_path.write_text(
            json.dumps(manifest, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        failed = self.system.ai_system_source_candidates.verify(
            candidate_id, requirements,
        )
        self.assertEqual(failed["status"], "static_verification_failed")
        failed_types = {
            check["type"] for check in failed["static_verification"]["checks"]
            if check["status"] == "failed"
        }
        self.assertIn("manifest_validation", failed_types)
        self.assertIn("candidate_digest_validation", failed_types)

    def test_trace_records_full_content_free_candidate_lifecycle(self):
        requirements = valid_requirements("trace_candidate_ai")
        _, disclosure, candidate = self._generate(requirements)
        candidate_id = candidate["candidate_id"]
        self.system.ai_system_source_candidates.review(
            candidate_id, decision="accept",
            notes="Human review accepts the bounded candidate.", approved=True,
        )
        self.system.ai_system_source_candidates.verify(candidate_id, requirements)
        approved = self.system.ai_system_source_candidates.approve(
            candidate_id, approved=True,
        )
        trace = next(
            item for item in self.system.traces.recent(limit=100)
            if item["trace_id"] == approved["trace_id"]
        )
        self.assertEqual(trace["provider"], self.adapter.provider)
        self.assertEqual(trace["model"], self.adapter.model_id)
        self.assertEqual(trace["processing_stage"], "approved")
        self.assertEqual(trace["transformations"], [
            "user_requirement", "blueprint_revalidation", "implementation_plan",
            "provider_disclosure", "source_candidate_generation", "human_review",
            "static_verification", "candidate_approval",
        ])
        self.assertEqual(
            trace["execution_metadata"]["disclosure_id"],
            disclosure["disclosure_id"],
        )
        self.assertFalse(trace["execution_metadata"]["runtime_tests_executed"])
        self.assertFalse(trace["execution_metadata"]["external_worker_called"])
        trace_json = json.dumps(trace)
        self.assertNotIn("build_system", trace_json)
        self.assertNotIn("Human review accepts", trace_json)

    def test_cli_exposes_explicit_gates_and_content_safe_listing(self):
        requirements = valid_requirements("cli_candidate_ai")
        source = Path(self.temp.name) / "requirements.json"
        task = Path(self.temp.name) / "task.txt"
        source.write_text(json.dumps(requirements), encoding="utf-8")
        task.write_text(
            "Generate the declared provider-neutral core system module.",
            encoding="utf-8",
        )
        plan = self.system.ai_system_planner.materialize(
            requirements, approved=True,
        )
        output = io.StringIO()
        error = io.StringIO()
        with (
            patch("sparkle.cli.SparkleSystem", return_value=self.system),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(error),
        ):
            self.assertEqual(entrypoint([
                "ai-system-plan-review", str(plan["plan_id"]),
            ]), 1)
            self.assertEqual(main([
                "ai-system-plan-review", str(plan["plan_id"]), "--approve",
            ]), 0)
            self.assertEqual(main([
                "ai-system-source-disclose", str(plan["plan_id"]),
                str(source), str(task),
            ]), 0)
            self.assertEqual(main(["ai-system-source-disclosures"]), 0)
            self.assertEqual(main(["ai-system-source-candidates"]), 0)
        self.assertIn("explicit approval", error.getvalue())
        self.assertIn("candidate-provider", output.getvalue())
        self.assertNotIn("build_system", output.getvalue())
        self.assertNotIn("Traceback", error.getvalue())


if __name__ == "__main__":
    unittest.main()
