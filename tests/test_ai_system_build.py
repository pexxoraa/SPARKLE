from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sparkle.ai_system_build import (
    BuildRejected,
    ControlledBuildArtifactWorkspace,
    ControlledBuildService,
    ControlledBuildStore,
)
from sparkle.ai_system_plan import AISystemImplementationPlanStore
from sparkle.ai_system_promotion import (
    ControlledPromotionWorkspace,
    ControlledSourcePromotionService,
    SourcePromotionStore,
)
from sparkle.ai_system_runtime import RuntimeEvaluationStore
from sparkle.ai_system_source import SourceCandidateStore, SourceCandidateWorkspace
from sparkle.cli import entrypoint, main
from sparkle.trace import TraceStore


class ControlledBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {"SPARKLE_DATA_DIR": self.temp.name}, clear=False,
        )
        self.environment.start()
        self.candidates = SourceCandidateStore()
        self.candidate_workspace = SourceCandidateWorkspace()
        self.plans = AISystemImplementationPlanStore()
        self.evaluations = RuntimeEvaluationStore()
        self.traces = TraceStore()
        self.promotions = SourcePromotionStore()
        self.promotion_workspace = ControlledPromotionWorkspace()
        self.promoter = ControlledSourcePromotionService(
            self.candidates, self.candidate_workspace, self.plans,
            self.evaluations, self.traces, self.promotions,
            self.promotion_workspace,
        )
        self.promotion = self._promote()
        self.store = ControlledBuildStore()
        self.workspace = ControlledBuildArtifactWorkspace(
            self.promotion_workspace,
        )
        self.service = ControlledBuildService(
            self.promotions, self.candidates, self.traces, self.store,
            self.workspace,
        )
        self.approval = self.service.approve(
            self.promotion["promotion_id"],
            actor="build.operator",
            source_origin="operator",
            approved=True,
        )

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def _promote(self) -> dict[str, object]:
        plan_id = self.plans.create(
            system_name="runtime_ai", blueprint_sha256="b" * 64,
            plan_sha256="a" * 64, plan_bytes=500,
        )
        self.plans.finish(
            plan_id, status="materialized_static_verified",
            workspace_build_id=plan_id,
        )
        self.plans.approve_for_generation(plan_id, approved=True)
        candidate_id = self.candidates.begin(
            disclosure_id=101, plan_id=plan_id, system_name="runtime_ai",
            plan_sha256="a" * 64,
        )
        _, files, digest = self.candidate_workspace.write(
            candidate_id=candidate_id, plan_id=plan_id,
            plan_sha256="a" * 64,
            files=[
                {
                    "path": "src/runtime_ai/system.py",
                    "content": "def value():\n    return 42\n",
                },
                {
                    "path": "src/runtime_ai/__init__.py",
                    "content": "from .system import value\n",
                },
                {
                    "path": "tests/test_runtime_ai.py",
                    "content": (
                        "import unittest\nfrom src.runtime_ai import value\n"
                        "class RuntimeAI(unittest.TestCase):\n"
                        "    def test_value(self): self.assertEqual(value(), 42)\n"
                    ),
                },
            ],
        )
        self.candidates.mark_generated(
            candidate_id, files=files, candidate_sha256=digest,
            trace_id="SPK-2026-999999",
        )
        self.candidates.review(
            candidate_id, decision="accept", notes_sha256="c" * 64,
        )
        self.candidates.record_verification(
            candidate_id,
            {"status": "passed", "checks": [], "runtime_tests_executed": False},
        )
        self.candidates.approve(candidate_id, approved=True)
        evaluation = self.evaluations.create(
            candidate_id=candidate_id, plan_id=plan_id, digest="d" * 64,
            trace_id="SPK-2026-888888",
        )
        evaluation_id = evaluation["evaluation_id"]
        self.evaluations.transition(evaluation_id, "requested", "queued")
        self.evaluations.transition(evaluation_id, "queued", "submitted")
        self.evaluations.transition(evaluation_id, "submitted", "running")
        self.evaluations.transition(
            evaluation_id, "running", "completed", returncode=0, timed_out=0,
            response_verified=1, isolation_verified=0, output_sha256="e" * 64,
            output_chars=2,
        )
        self.evaluations.transition(
            evaluation_id, "completed", "evaluated",
            criteria_json=json.dumps([
                {"name": "tests_pass", "kind": "worker_pass", "passed": True},
            ]),
        )
        approval = self.promoter.approve(
            candidate_id, evaluation_id, actor="release.operator",
            source_origin="operator", approved=True,
        )
        return self.promoter.request({
            "protocol_version": self.promoter.PROTOCOL,
            "request_id": "SPK-PROMO-REQ-" + "A" * 32,
            "candidate_id": candidate_id,
            "candidate_sha256": digest,
            "plan_id": plan_id,
            "plan_sha256": "a" * 64,
            "evaluation_id": evaluation_id,
            "approval_id": approval["approval_id"],
            "destination": "staging/runtime_ai",
            "actor": "release.operator",
            "source_origin": "operator",
        }, approved=True)

    def contract(self, **changes):
        value = {
            "protocol_version": self.service.PROTOCOL,
            "request_id": "SPK-BUILD-REQ-" + "B" * 32,
            "promotion_id": self.promotion["promotion_id"],
            "promotion_digest": self.promotion["destination_digest"],
            "approval_id": self.approval["approval_id"],
            "build_kind": "source_bundle",
            "actor": "build.operator",
            "source_origin": "operator",
        }
        value.update(changes)
        return value

    def test_valid_build_is_promotion_bound_deterministic_and_non_executing(self):
        self.assertEqual(self.service.eligibility()[0]["state"], "approval_recorded")
        result = self.service.request(self.contract(), approved=True)
        self.assertEqual(result["status"], "built")
        self.assertEqual(
            [event["state"] for event in result["lifecycle"]],
            ["requested", "building", "built"],
        )
        self.assertFalse(result["source_executed"])
        self.assertFalse(result["published"])
        self.assertFalse(result["deployed"])
        artifact = (
            Path(self.temp.name) / "build_environment" / "artifacts"
            / result["artifact_name"]
        )
        self.assertTrue(artifact.is_file())
        with zipfile.ZipFile(artifact) as archive:
            names = set(archive.namelist())
        self.assertEqual(names, {
            "SPARKLE_ARTIFACT_MANIFEST.json",
            "src/runtime_ai/__init__.py",
            "src/runtime_ai/system.py",
            "tests/test_runtime_ai.py",
        })
        serialized = json.dumps(result)
        self.assertNotIn("def value", serialized)
        self.assertNotIn("return 42", serialized)
        self.assertEqual(self.service.eligibility()[0]["state"], "built")

    def test_explicit_approval_and_exact_promotion_identity_are_required(self):
        with self.assertRaisesRegex(ValueError, "explicit approval"):
            self.service.request(self.contract(), approved=False)
        result = self.service.request(self.contract(
            promotion_digest="f" * 64,
        ), approved=True)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["error_type"], "contract_identity_mismatch")
        self.assertFalse((
            Path(self.temp.name) / "build_environment" / "artifacts"
            / "runtime_ai"
        ).exists())

    def test_missing_unfinished_and_mismatched_promotions_fail_closed(self):
        with self.assertRaisesRegex(BuildRejected, "promotion_missing"):
            self.service.approve(
                "SPK-PROMO-MISSING", actor="build.operator",
                source_origin="operator", approved=True,
            )
        with self.promotions.connect() as connection:
            connection.execute(
                "UPDATE source_promotions SET status='failed' WHERE promotion_id=?",
                (self.promotion["promotion_id"],),
            )
        with self.assertRaisesRegex(BuildRejected, "promotion_not_completed"):
            self.service.approve(
                self.promotion["promotion_id"], actor="build.operator",
                source_origin="operator", approved=True,
            )

    def test_tamper_after_approval_is_rejected_before_artifact_creation(self):
        target = (
            Path(self.temp.name) / "promotion_environment" / "staging"
            / "runtime_ai" / "src" / "runtime_ai" / "system.py"
        )
        target.chmod(0o600)
        target.write_text("def value():\n    return 99\n", encoding="utf-8")
        result = self.service.request(self.contract(), approved=True)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["error_type"], "promotion_content_tampered")

    def test_stale_and_cross_identity_approvals_are_rejected(self):
        mismatch = self.service.request(self.contract(
            actor="other.operator",
        ), approved=True)
        self.assertEqual(mismatch["error_type"], "approval_mismatch")
        with self.store.connect() as connection:
            connection.execute(
                "UPDATE controlled_build_approvals SET expires_at=? WHERE approval_id=?",
                ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                 self.approval["approval_id"]),
            )
        stale = self.service.request(self.contract(
            request_id="SPK-BUILD-REQ-" + "D" * 32,
        ), approved=True)
        self.assertEqual(stale["error_type"], "approval_stale")

    def test_replay_is_idempotent_and_conflicting_requests_are_refused(self):
        first = self.service.request(self.contract(), approved=True)
        second = self.service.request(self.contract(), approved=True)
        self.assertEqual(first["build_id"], second["build_id"])
        with self.assertRaisesRegex(BuildRejected, "promotion_build_conflict"):
            self.service.request(self.contract(
                request_id="SPK-BUILD-REQ-" + "C" * 32,
                build_kind="source_bundle",
                promotion_digest="f" * 64,
            ), approved=True)

    def test_concurrent_replay_creates_one_build_and_one_artifact(self):
        barrier = threading.Barrier(3)
        results = []

        def invoke():
            barrier.wait()
            results.append(self.service.request(self.contract(), approved=True))

        threads = [threading.Thread(target=invoke) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()
        self.assertEqual(len({item["build_id"] for item in results}), 1)
        self.assertEqual(len(self.store.list()), 1)
        artifacts = list((
            Path(self.temp.name) / "build_environment" / "artifacts"
        ).rglob("*.zip"))
        self.assertEqual(len(artifacts), 1)

    def test_build_failure_never_reports_success(self):
        with patch.object(
            self.workspace.packager, "package", side_effect=OSError("blocked"),
        ):
            result = self.service.request(self.contract(), approved=True)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["error_type"], "artifact_build_failed")
        self.assertIsNone(result["artifact_sha256"])

    def test_source_change_during_packaging_is_rejected_and_cleaned_up(self):
        original = self.workspace.packager.package
        target = (
            Path(self.temp.name) / "promotion_environment" / "staging"
            / "runtime_ai" / "src" / "runtime_ai" / "system.py"
        )

        def race(project_name):
            target.chmod(0o600)
            target.write_text("def value():\n    return 7\n", encoding="utf-8")
            return original(project_name)

        with patch.object(self.workspace.packager, "package", side_effect=race):
            result = self.service.request(self.contract(), approved=True)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["error_type"], "artifact_source_mismatch")
        self.assertEqual(list((
            Path(self.temp.name) / "build_environment" / "artifacts"
        ).rglob("*.zip")), [])

    def test_contract_is_strict_bounded_and_evidence_is_content_free(self):
        with self.assertRaisesRegex(ValueError, "contract fields"):
            self.service.request({"promotion_id": self.promotion["promotion_id"]}, approved=True)
        with self.assertRaisesRegex(ValueError, "build kind"):
            self.service.request(self.contract(build_kind="wheel"), approved=True)
        serialized = json.dumps({
            "approval": self.approval,
            "eligibility": self.service.eligibility(),
        })
        self.assertNotIn("def value", serialized)
        self.assertNotIn("return 42", serialized)

    def test_cli_lists_evidence_and_refuses_unapproved_build(self):
        output = io.StringIO()
        error = io.StringIO()
        stub = ControlledBuildSystemStub(self)
        with (
            patch("sparkle.cli.SparkleSystem", return_value=stub),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(error),
        ):
            self.assertEqual(main(["ai-system-controlled-builds"]), 0)
            self.assertEqual(entrypoint([
                "ai-system-controlled-build-approve",
                self.promotion["promotion_id"],
                "build.operator",
            ]), 1)
        self.assertIn(self.service.PROTOCOL, output.getvalue())
        self.assertIn("explicit approval", error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())


class ControlledBuildSystemStub:
    def __init__(self, case: ControlledBuildTests):
        self.ai_system_controlled_builder = case.service
        self.controlled_builds = case.store


if __name__ == "__main__":
    unittest.main()
