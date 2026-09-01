from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sparkle.ai_system_plan import AISystemImplementationPlanStore
from sparkle.ai_system_promotion import (
    ControlledPromotionWorkspace,
    ControlledSourcePromotionService,
    PromotionRejected,
    SourcePromotionStore,
)
from sparkle.ai_system_runtime import RuntimeEvaluationStore
from sparkle.ai_system_source import SourceCandidateStore, SourceCandidateWorkspace
from sparkle.cli import entrypoint, main
from sparkle.trace import TraceStore


class ControlledSourcePromotionTests(unittest.TestCase):
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
        self.store = SourcePromotionStore()
        self.workspace = ControlledPromotionWorkspace()
        self.service = ControlledSourcePromotionService(
            self.candidates,
            self.candidate_workspace,
            self.plans,
            self.evaluations,
            self.traces,
            self.store,
            self.workspace,
        )
        self.plan_id = self._plan()
        self.candidate_id = self._candidate(self.plan_id)
        self.evaluation_id = self._evaluation(self.candidate_id, self.plan_id)
        self.approval = self._approval(self.candidate_id, self.evaluation_id)

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def _plan(self, *, digest: str = "a" * 64) -> int:
        plan_id = self.plans.create(
            system_name="runtime_ai",
            blueprint_sha256="b" * 64,
            plan_sha256=digest,
            plan_bytes=500,
        )
        self.plans.finish(
            plan_id,
            status="materialized_static_verified",
            workspace_build_id=plan_id,
        )
        self.plans.approve_for_generation(plan_id, approved=True)
        return plan_id

    def _candidate(self, plan_id: int, *, name: str = "runtime_ai") -> int:
        plan = self.plans.get(plan_id)
        candidate_id = self.candidates.begin(
            disclosure_id=candidate_id_seed(plan_id),
            plan_id=plan_id,
            system_name=name,
            plan_sha256=plan["plan_sha256"],
        )
        _, files, digest = self.candidate_workspace.write(
            candidate_id=candidate_id,
            plan_id=plan_id,
            plan_sha256=plan["plan_sha256"],
            files=[
                {
                    "path": f"src/{name}/system.py",
                    "content": "def value():\n    return 42\n",
                },
                {
                    "path": f"src/{name}/__init__.py",
                    "content": "from .system import value\n",
                },
            ],
        )
        self.candidates.mark_generated(
            candidate_id,
            files=files,
            candidate_sha256=digest,
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
        return candidate_id

    def _evaluation(
        self,
        candidate_id: int,
        plan_id: int,
        *,
        success: bool = True,
    ) -> str:
        record = self.evaluations.create(
            candidate_id=candidate_id,
            plan_id=plan_id,
            digest="d" * 64,
            trace_id="SPK-2026-888888",
        )
        evaluation_id = record["evaluation_id"]
        self.evaluations.transition(evaluation_id, "requested", "queued")
        self.evaluations.transition(evaluation_id, "queued", "submitted")
        self.evaluations.transition(evaluation_id, "submitted", "running")
        if success:
            self.evaluations.transition(
                evaluation_id,
                "running",
                "completed",
                returncode=0,
                timed_out=0,
                response_verified=1,
                isolation_verified=0,
                output_sha256="e" * 64,
                output_chars=2,
            )
            self.evaluations.transition(
                evaluation_id,
                "completed",
                "evaluated",
                criteria_json=json.dumps([
                    {"name": "tests_pass", "kind": "worker_pass", "passed": True},
                ]),
            )
        else:
            self.evaluations.transition(
                evaluation_id,
                "running",
                "execution_failure",
                returncode=1,
                response_verified=1,
                failure_reason="WorkerExecutionFailed",
            )
        return evaluation_id

    def _approval(self, candidate_id: int, evaluation_id: str, **changes):
        values = {"actor": "release.operator", "source_origin": "operator"}
        values.update(changes)
        return self.service.approve(
            candidate_id,
            evaluation_id,
            approved=True,
            **values,
        )

    def contract(self, **changes):
        candidate = self.candidates.get(self.candidate_id)
        value = {
            "protocol_version": self.service.PROTOCOL,
            "request_id": "SPK-PROMO-REQ-" + "A" * 32,
            "candidate_id": self.candidate_id,
            "candidate_sha256": candidate["candidate_sha256"],
            "plan_id": self.plan_id,
            "plan_sha256": candidate["plan_sha256"],
            "evaluation_id": self.evaluation_id,
            "approval_id": self.approval["approval_id"],
            "destination": "staging/runtime_ai",
            "actor": "release.operator",
            "source_origin": "operator",
        }
        value.update(changes)
        return value

    def test_valid_promotion_is_exact_audited_and_stops_at_staging(self):
        self.assertEqual(self.service.eligibility()[0]["state"], "approval_recorded")
        result = self.service.request(self.contract(), approved=True)
        self.assertEqual(result["status"], "promoted")
        self.assertEqual(
            [event["state"] for event in result["lifecycle"]],
            ["requested", "promoting", "promoted"],
        )
        self.assertEqual(result["source_digest"], result["destination_digest"])
        self.assertTrue(result["artifact_id"].startswith("SPK-PROMOTED-"))
        promoted = self.workspace.load_destination("staging/runtime_ai")
        _, candidate = self.candidate_workspace.load(self.candidate_id)
        self.assertEqual(promoted, candidate)
        self.assertFalse(result["built"])
        self.assertFalse(result["packaged"])
        self.assertFalse(result["published"])
        self.assertFalse(result["deployed"])
        self.assertFalse(
            (Path(self.temp.name) / "applications" / "runtime_ai").exists()
        )
        trace = next(
            item for item in self.traces.recent(limit=20)
            if item["trace_id"] == result["trace_id"]
        )
        self.assertEqual(trace["processing_stage"], "promoted")
        self.assertFalse(trace["execution_metadata"]["isolation_verified"])
        self.assertFalse(trace["execution_metadata"]["deployed"])
        self.assertEqual(self.service.eligibility()[0]["state"], "promoted")

    def test_missing_candidate_plan_evaluation_and_approval_are_rejected(self):
        cases = [
            (
                self.contract(
                    candidate_id=999,
                    request_id="SPK-PROMO-REQ-" + "4" * 32,
                ),
                "candidate_missing",
            ),
            (
                self.contract(
                    plan_id=self.plan_id + 1,
                    request_id="SPK-PROMO-REQ-" + "5" * 32,
                ),
                "contract_identity_mismatch",
            ),
            (
                self.contract(
                    evaluation_id="SPK-EVAL-" + "F" * 32,
                    request_id="SPK-PROMO-REQ-" + "B" * 32,
                ),
                "evaluation_missing",
            ),
            (
                self.contract(
                    approval_id="SPK-PROMO-APP-" + "F" * 32,
                    request_id="SPK-PROMO-REQ-" + "C" * 32,
                ),
                "approval_missing",
            ),
        ]
        for contract, reason in cases:
            with self.subTest(reason=reason):
                result = self.service.request(contract, approved=True)
                self.assertEqual(result["status"], "rejected")
                self.assertEqual(result["error_type"], reason)

    def test_failed_evaluation_and_missing_explicit_approvals_refuse_promotion(self):
        failed_candidate = self._candidate(self.plan_id)
        failed_evaluation = self._evaluation(
            failed_candidate, self.plan_id, success=False,
        )
        with self.assertRaisesRegex(PromotionRejected, "evaluation_not_successful"):
            self._approval(failed_candidate, failed_evaluation)
        with self.assertRaisesRegex(ValueError, "explicit approval"):
            self.service.approve(
                self.candidate_id,
                self.evaluation_id,
                actor="release.operator",
                source_origin="operator",
                approved=False,
            )
        with self.assertRaisesRegex(ValueError, "explicit approval"):
            self.service.request(self.contract(), approved=False)
        self.assertEqual(self.store.list(), [])

    def test_approval_mismatch_and_stale_approval_are_rejected(self):
        mismatch = self.service.request(
            self.contract(
                actor="other.operator",
                request_id="SPK-PROMO-REQ-" + "D" * 32,
            ),
            approved=True,
        )
        self.assertEqual(mismatch["error_type"], "approval_mismatch")
        expired = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        with self.store.connect() as connection:
            connection.execute(
                "UPDATE source_promotion_approvals SET expires_at=? WHERE approval_id=?",
                (expired, self.approval["approval_id"]),
            )
        stale = self.service.request(
            self.contract(request_id="SPK-PROMO-REQ-" + "E" * 32),
            approved=True,
        )
        self.assertEqual(stale["error_type"], "approval_stale")

    def test_invalidated_and_superseded_candidates_are_rejected(self):
        self.service.exclude_candidate(
            self.candidate_id,
            status="invalidated",
            reason="Candidate is no longer eligible.",
            actor="release.operator",
            source_origin="operator",
            approved=True,
        )
        invalidated = self.service.request(self.contract(), approved=True)
        self.assertEqual(invalidated["error_type"], "candidate_invalidated")

        replacement = self._candidate(self.plan_id)
        evaluation = self._evaluation(replacement, self.plan_id)
        approval = self._approval(replacement, evaluation)
        successor = self._candidate(self.plan_id)
        self.service.exclude_candidate(
            replacement,
            status="superseded",
            replacement_candidate_id=successor,
            reason="A newer reviewed candidate replaces it.",
            actor="release.operator",
            source_origin="operator",
            approved=True,
        )
        candidate = self.candidates.get(replacement)
        superseded = self.service.request(self.contract(
            request_id="SPK-PROMO-REQ-" + "F" * 32,
            candidate_id=replacement,
            candidate_sha256=candidate["candidate_sha256"],
            evaluation_id=evaluation,
            approval_id=approval["approval_id"],
        ), approved=True)
        self.assertEqual(superseded["error_type"], "candidate_superseded")

    def test_candidate_content_and_metadata_tampering_are_rejected(self):
        candidate_root = (
            Path(self.temp.name) / "candidate_environment" / "source_candidates"
            / f"candidate-{self.candidate_id:06d}"
        )
        source = candidate_root / "src/runtime_ai/system.py"
        source.chmod(0o600)
        source.write_text("def value():\n    return 99\n", encoding="utf-8")
        tampered = self.service.request(self.contract(), approved=True)
        self.assertEqual(tampered["status"], "rejected")
        self.assertIn(tampered["error_type"], {
            "candidate_content_tampered", "candidate_digest_mismatch",
        })
        self.assertFalse(
            (Path(self.temp.name) / "promotion_environment" / "staging" / "runtime_ai").exists()
        )
        metadata_candidate = self._candidate(self.plan_id)
        metadata_evaluation = self._evaluation(metadata_candidate, self.plan_id)
        metadata_approval = self._approval(metadata_candidate, metadata_evaluation)
        with self.candidates.connect() as connection:
            connection.execute(
                "UPDATE source_candidates SET files_json='[]' WHERE id=?",
                (metadata_candidate,),
            )
        metadata = self.candidates.get(metadata_candidate)
        tampered_metadata = self.service.request(self.contract(
            request_id="SPK-PROMO-REQ-" + "7" * 32,
            candidate_id=metadata_candidate,
            candidate_sha256=metadata["candidate_sha256"],
            evaluation_id=metadata_evaluation,
            approval_id=metadata_approval["approval_id"],
        ), approved=True)
        self.assertEqual(tampered_metadata["error_type"], "candidate_metadata_mismatch")

    def test_invalid_path_destination_and_overwrite_are_refused(self):
        invalid = self.service.request(
            self.contract(destination="staging/../escape"), approved=True,
        )
        self.assertEqual(invalid["error_type"], "invalid_destination")
        successful = self.service.request(
            self.contract(request_id="SPK-PROMO-REQ-" + "1" * 32),
            approved=True,
        )
        self.assertEqual(successful["status"], "promoted")
        second_candidate = self._candidate(self.plan_id)
        second_evaluation = self._evaluation(second_candidate, self.plan_id)
        second_approval = self._approval(second_candidate, second_evaluation)
        second = self.candidates.get(second_candidate)
        overwrite = self.service.request(self.contract(
            request_id="SPK-PROMO-REQ-" + "2" * 32,
            candidate_id=second_candidate,
            candidate_sha256=second["candidate_sha256"],
            evaluation_id=second_evaluation,
            approval_id=second_approval["approval_id"],
        ), approved=True)
        self.assertEqual(overwrite["status"], "failed")
        self.assertEqual(overwrite["error_type"], "destination_exists")

    def test_replay_is_idempotent_and_conflicts_are_rejected(self):
        contract = self.contract()
        first = self.service.request(contract, approved=True)
        second = self.service.request(contract, approved=True)
        self.assertEqual(first["promotion_id"], second["promotion_id"])
        self.assertEqual(len(self.store.list()), 1)
        with self.assertRaisesRegex(PromotionRejected, "request_replay_conflict"):
            self.service.request({**contract, "actor": "other.operator"}, approved=True)
        with self.assertRaisesRegex(PromotionRejected, "candidate_promotion_conflict"):
            self.service.request(self.contract(
                request_id="SPK-PROMO-REQ-" + "3" * 32,
                destination="staging/other",
            ), approved=True)

    def test_concurrent_replay_creates_one_promotion_and_one_destination(self):
        contract = self.contract()
        entered = threading.Event()
        release = threading.Event()
        completed: list[dict[str, object]] = []
        original = self.workspace.promote

        def slow_promote(**values):
            entered.set()
            self.assertTrue(release.wait(timeout=5))
            return original(**values)

        def run_first():
            completed.append(self.service.request(contract, approved=True))

        with patch.object(self.workspace, "promote", side_effect=slow_promote):
            thread = threading.Thread(target=run_first)
            thread.start()
            self.assertTrue(entered.wait(timeout=5))
            replay = self.service.request(contract, approved=True)
            self.assertEqual(replay["status"], "promoting")
            release.set()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(completed[0]["status"], "promoted")
        self.assertEqual(len(self.store.list()), 1)
        self.assertTrue(
            (Path(self.temp.name) / "promotion_environment" / "staging" / "runtime_ai").is_dir()
        )

    def test_copy_failure_and_digest_failure_never_report_success(self):
        with patch.object(self.workspace, "promote", side_effect=OSError("interrupted")):
            interrupted = self.service.request(self.contract(), approved=True)
        self.assertEqual(interrupted["status"], "failed")
        self.assertEqual(interrupted["error_type"], "OSError")
        self.assertFalse(
            (Path(self.temp.name) / "promotion_environment" / "staging" / "runtime_ai").exists()
        )
        with self.assertRaisesRegex(ValueError, "lifecycle transition"):
            self.store.transition(
                interrupted["promotion_id"], "promoting", "promoted",
            )
        partial_approval = self._approval(
            self.candidate_id, self.evaluation_id,
        )
        with patch("sparkle.ai_system_promotion.os.write", side_effect=OSError("partial")):
            partial = self.service.request(self.contract(
                request_id="SPK-PROMO-REQ-" + "6" * 32,
                approval_id=partial_approval["approval_id"],
            ), approved=True)
        self.assertEqual(partial["status"], "failed")
        staging = Path(self.temp.name) / "promotion_environment" / "staging"
        self.assertFalse((staging / "runtime_ai").exists())
        self.assertEqual(list(staging.glob(".*.tmp")), [])
        self.assertEqual(list(staging.glob(".*.lock")), [])

        digest_approval = self._approval(self.candidate_id, self.evaluation_id)
        with patch.object(
            self.workspace,
            "promote",
            return_value=("f" * 64, "SPK-PROMOTED-INVALID"),
        ):
            digest_failure = self.service.request(self.contract(
                request_id="SPK-PROMO-REQ-" + "8" * 32,
                approval_id=digest_approval["approval_id"],
            ), approved=True)
        self.assertEqual(digest_failure["status"], "failed")
        self.assertEqual(digest_failure["error_type"], "destination_digest_mismatch")

        replacement_approval = self._approval(self.candidate_id, self.evaluation_id)
        retried = self.service.request(self.contract(
            request_id="SPK-PROMO-REQ-" + "9" * 32,
            approval_id=replacement_approval["approval_id"],
        ), approved=True)
        self.assertEqual(retried["status"], "promoted")
        self.assertNotEqual(retried["promotion_id"], interrupted["promotion_id"])

    def test_contract_validation_and_content_free_evidence(self):
        with self.assertRaisesRegex(ValueError, "contract fields"):
            self.service.request({"candidate_id": self.candidate_id}, approved=True)
        result = self.service.request(self.contract(), approved=True)
        serialized = json.dumps({
            "promotion": result,
            "approval": self.store.list_approvals()[0],
        })
        self.assertNotIn("def value", serialized)
        self.assertNotIn("return 42", serialized)
        self.assertNotIn("credentials", serialized.lower().replace(
            '"credentials_included": false', "",
        ))

    def test_cli_lists_evidence_and_refuses_unapproved_promotion(self):
        output = io.StringIO()
        error = io.StringIO()
        with (
            patch("sparkle.cli.SparkleSystem", return_value=PromotionSystemStub(self)),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(error),
        ):
            self.assertEqual(main(["ai-system-promotions"]), 0)
            self.assertEqual(
                entrypoint([
                    "ai-system-promotion-approve",
                    str(self.candidate_id),
                    self.evaluation_id,
                    "release.operator",
                ]),
                1,
            )
        self.assertIn(self.service.PROTOCOL, output.getvalue())
        self.assertIn("explicit approval", error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())


def candidate_id_seed(plan_id: int) -> int:
    return plan_id + 100


class PromotionSystemStub:
    def __init__(self, case: ControlledSourcePromotionTests):
        self.ai_system_source_promoter = case.service
        self.source_promotions = case.store


if __name__ == "__main__":
    unittest.main()
