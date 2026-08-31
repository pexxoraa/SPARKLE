from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from sparkle.ai_system_source import SourceCandidateStore, SourceCandidateWorkspace
from sparkle.config import data_root
from sparkle.external_worker import ExternalWorkerError
from sparkle.storage import SQLiteStore, utc_now
from sparkle.trace import TraceStore


class RuntimeEvaluationStore(SQLiteStore):
    """Content-free lifecycle and result evidence for candidate runtime requests."""

    MAX_RECORDS = 1_000

    def __init__(self, path: Path | None = None):
        super().__init__(path or data_root() / "data_environment" / "runtime_evaluations.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS runtime_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    evaluation_id TEXT NOT NULL UNIQUE,
                    candidate_id INTEGER NOT NULL,
                    plan_id INTEGER NOT NULL,
                    contract_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    worker_run_id INTEGER,
                    worker_job_id TEXT,
                    worker_id TEXT,
                    runtime_environment_id TEXT,
                    returncode INTEGER,
                    timed_out INTEGER NOT NULL DEFAULT 0,
                    duration_ms REAL,
                    output_sha256 TEXT,
                    output_chars INTEGER NOT NULL DEFAULT 0,
                    criteria_json TEXT NOT NULL DEFAULT '[]',
                    response_verified INTEGER NOT NULL DEFAULT 0,
                    isolation_verified INTEGER NOT NULL DEFAULT 0,
                    failure_reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS runtime_evaluation_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    evaluation_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def create(self, *, candidate_id: int, plan_id: int, digest: str, trace_id: str) -> dict[str, Any]:
        evaluation_id = f"SPK-EVAL-{uuid.uuid4().hex.upper()}"
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO runtime_evaluations(
                    evaluation_id,candidate_id,plan_id,contract_sha256,status,
                    trace_id,created_at,updated_at
                ) VALUES(?,?,?,?,'requested',?,?,?)
            """, (evaluation_id, candidate_id, plan_id, digest, trace_id, now, now))
            connection.execute(
                "INSERT INTO runtime_evaluation_events(evaluation_id,state,created_at) VALUES(?,'requested',?)",
                (evaluation_id, now),
            )
            connection.execute("""
                DELETE FROM runtime_evaluations WHERE id NOT IN (
                    SELECT id FROM runtime_evaluations ORDER BY id DESC LIMIT ?
                )
            """, (self.MAX_RECORDS,))
            connection.execute("""
                DELETE FROM runtime_evaluation_events WHERE evaluation_id NOT IN (
                    SELECT evaluation_id FROM runtime_evaluations
                )
            """)
        return self.get(int(cursor.lastrowid))

    def transition(self, evaluation_id: str, expected: str, state: str, **values: Any) -> dict[str, Any]:
        allowed = {
            "queued", "submitted", "running", "completed", "evaluated",
            "rejected", "failed_to_start", "timeout", "worker_unavailable",
            "protocol_failure", "execution_failure", "evaluation_failure",
        }
        if state not in allowed:
            raise ValueError("Runtime evaluation state is invalid")
        fields = {
            "worker_run_id", "worker_job_id", "worker_id", "runtime_environment_id",
            "returncode", "timed_out", "duration_ms", "output_sha256", "output_chars",
            "criteria_json", "response_verified", "isolation_verified", "failure_reason",
        }
        if set(values) - fields:
            raise ValueError("Runtime evaluation result fields are invalid")
        assignments = ["status=?", "updated_at=?"]
        parameters: list[Any] = [state, utc_now()]
        for key, value in values.items():
            assignments.append(f"{key}=?")
            parameters.append(value)
        parameters.extend([evaluation_id, expected])
        with self.connect() as connection:
            cursor = connection.execute(
                f"UPDATE runtime_evaluations SET {','.join(assignments)} WHERE evaluation_id=? AND status=?",
                parameters,
            )
            if cursor.rowcount == 1:
                connection.execute(
                    "INSERT INTO runtime_evaluation_events(evaluation_id,state,created_at) VALUES(?,?,?)",
                    (evaluation_id, state, utc_now()),
                )
        if cursor.rowcount != 1:
            raise ValueError("Runtime evaluation lifecycle transition is invalid")
        return self.by_evaluation_id(evaluation_id)

    def get(self, record_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM runtime_evaluations WHERE id=?", (record_id,)).fetchone()
        if row is None:
            raise KeyError("Runtime evaluation does not exist")
        return self._public(row)

    def by_evaluation_id(self, evaluation_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM runtime_evaluations WHERE evaluation_id=?", (evaluation_id,),
            ).fetchone()
            events = connection.execute(
                "SELECT state,created_at FROM runtime_evaluation_events WHERE evaluation_id=? ORDER BY id",
                (evaluation_id,),
            ).fetchall()
        if row is None:
            raise KeyError("Runtime evaluation does not exist")
        result = self._public(row)
        result["lifecycle"] = [dict(item) for item in events]
        return result

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runtime_evaluations ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [self._public(row) for row in rows]

    @staticmethod
    def _public(row: Any) -> dict[str, Any]:
        return {
            "runtime_evaluation_record_id": row["id"],
            "evaluation_id": row["evaluation_id"],
            "candidate_id": row["candidate_id"], "plan_id": row["plan_id"],
            "contract_sha256": row["contract_sha256"], "status": row["status"],
            "trace_id": row["trace_id"], "worker_run_id": row["worker_run_id"],
            "worker_job_id": row["worker_job_id"], "worker_id": row["worker_id"],
            "runtime_environment_id": row["runtime_environment_id"],
            "returncode": row["returncode"], "timed_out": bool(row["timed_out"]),
            "duration_ms": row["duration_ms"], "output_sha256": row["output_sha256"],
            "output_chars": row["output_chars"],
            "criteria_results": json.loads(row["criteria_json"]),
            "response_verified": bool(row["response_verified"]),
            "isolation_verified": bool(row["isolation_verified"]),
            "runtime_verified": row["status"] == "evaluated",
            "production_verified": False, "source_promoted": False,
            "published": False, "deployed": False,
            "failure_reason": row["failure_reason"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }


class CandidateRuntimeEvaluator:
    PROTOCOL = "SPARKLE-AI-SYSTEM-RUNTIME-EVALUATION/1"
    MAX_CONTRACT_BYTES = 128_000
    TERMINAL_FAILURES = {
        "rejected", "failed_to_start", "timeout", "worker_unavailable",
        "protocol_failure", "execution_failure", "evaluation_failure",
    }

    def __init__(
        self,
        candidates: SourceCandidateStore,
        candidate_workspace: SourceCandidateWorkspace,
        traces: TraceStore,
        store: RuntimeEvaluationStore,
        worker: Any,
        root: Path | None = None,
    ):
        self.candidates = candidates
        self.candidate_workspace = candidate_workspace
        self.traces = traces
        self.store = store
        self.worker = worker
        self.root = (root or data_root() / "runtime_environment" / "evaluations").resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _path(value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("Runtime evaluation test path is invalid")
        path = PurePosixPath(value)
        if (
            path.is_absolute() or ".." in path.parts or not path.parts
            or path.parts[0] != "tests" or not path.name.startswith("test_")
            or path.suffix != ".py" or len(path.as_posix()) > 240
        ):
            raise ValueError("Runtime evaluation test path is invalid")
        return path.as_posix()

    def validate(self, contract: dict[str, Any]) -> tuple[dict[str, Any], str]:
        fields = {
            "protocol_version", "candidate_id", "plan_id", "requested_capabilities",
            "runtime_requirements", "input_data", "expected_behavior",
            "execution_limits", "evaluation_criteria", "test_files", "result_format",
        }
        if not isinstance(contract, dict) or set(contract) != fields:
            raise ValueError("Runtime evaluation contract fields are invalid")
        if contract["protocol_version"] != self.PROTOCOL:
            raise ValueError("Runtime evaluation protocol is invalid")
        for field in ("candidate_id", "plan_id"):
            value = contract[field]
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"Runtime evaluation {field} is invalid")
        capabilities = contract["requested_capabilities"]
        if not isinstance(capabilities, list) or not 1 <= len(capabilities) <= 10 or any(
            not isinstance(item, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", item)
            for item in capabilities
        ) or len(set(capabilities)) != len(capabilities):
            raise ValueError("Runtime evaluation capabilities are invalid")
        runtime = contract["runtime_requirements"]
        if runtime != {"language": "python", "framework": "unittest"}:
            raise ValueError("Runtime evaluation supports only the fixed Python unittest runtime")
        limits = contract["execution_limits"]
        if not isinstance(limits, dict) or set(limits) != {"timeout_seconds", "max_output_chars"}:
            raise ValueError("Runtime evaluation limits are invalid")
        if not isinstance(limits["timeout_seconds"], int) or not 1 <= limits["timeout_seconds"] <= 60:
            raise ValueError("Runtime evaluation timeout is invalid")
        if not isinstance(limits["max_output_chars"], int) or not 100 <= limits["max_output_chars"] <= 12_000:
            raise ValueError("Runtime evaluation output limit is invalid")
        if not isinstance(contract["input_data"], (dict, list)):
            raise ValueError("Runtime evaluation input data is invalid")
        expected = contract["expected_behavior"]
        if not isinstance(expected, str) or not 10 <= len(expected) <= 2_000:
            raise ValueError("Runtime evaluation expected behavior is invalid")
        criteria = contract["evaluation_criteria"]
        if not isinstance(criteria, list) or not 1 <= len(criteria) <= 20:
            raise ValueError("Runtime evaluation criteria are invalid")
        for item in criteria:
            if not isinstance(item, dict) or set(item) != {"name", "kind", "value"}:
                raise ValueError("Runtime evaluation criterion fields are invalid")
            if item["kind"] not in {"worker_pass", "output_contains", "output_excludes"}:
                raise ValueError("Runtime evaluation criterion kind is invalid")
            if not isinstance(item["name"], str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", item["name"]):
                raise ValueError("Runtime evaluation criterion name is invalid")
            if not isinstance(item["value"], str) or len(item["value"]) > 200:
                raise ValueError("Runtime evaluation criterion value is invalid")
        tests = contract["test_files"]
        if not isinstance(tests, list) or not 1 <= len(tests) <= 20:
            raise ValueError("Runtime evaluation test files are invalid")
        seen: set[str] = set()
        for item in tests:
            if not isinstance(item, dict) or set(item) != {"path", "content"}:
                raise ValueError("Runtime evaluation test file fields are invalid")
            path = self._path(item["path"])
            if path in seen or not isinstance(item["content"], str) or not 1 <= len(item["content"].encode()) <= 64_000:
                raise ValueError("Runtime evaluation test file is invalid")
            seen.add(path)
        if contract["result_format"] != "SPARKLE-RUNTIME-RESULT/1":
            raise ValueError("Runtime evaluation result format is invalid")
        canonical = json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        if len(canonical.encode()) > self.MAX_CONTRACT_BYTES:
            raise ValueError("Runtime evaluation contract exceeds its size bound")
        return contract, hashlib.sha256(canonical.encode()).hexdigest()

    def _bundle(self, evaluation_id: str, candidate_id: int, tests: list[dict[str, str]]) -> Path:
        root = self.root / evaluation_id
        if root.exists() or root.is_symlink():
            raise ValueError("Runtime evaluation workspace already exists")
        manifest, source = self.candidate_workspace.load(candidate_id)
        root.mkdir(mode=0o700)
        try:
            for path, content in [*source.items(), *((item["path"], item["content"]) for item in tests)]:
                target = root.joinpath(*PurePosixPath(path).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                target.chmod(0o400)
            (root / "RUNTIME_EVALUATION.json").write_text(
                json.dumps({"evaluation_id": evaluation_id, "candidate_id": candidate_id,
                            "candidate_sha256": manifest["candidate_sha256"]},
                           sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8",
            )
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise
        return root

    def request(self, contract: dict[str, Any], *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Runtime evaluation request requires explicit approval")
        trace_id, started = self.traces.start(input_source="ai_system_runtime_evaluation", agent="system")
        self.traces.finish(
            trace_id,
            started,
            status="success",
            agent="system",
            model="external-worker-runtime",
            provider="external_worker",
            result_summary="Runtime evaluation request recorded",
        )
        try:
            contract, digest = self.validate(contract)
        except Exception as exc:
            safe = contract if isinstance(contract, dict) else {}
            canonical = json.dumps(safe, sort_keys=True, separators=(",", ":"), default=str)
            record = self.store.create(
                candidate_id=safe.get("candidate_id", 0) if isinstance(safe.get("candidate_id", 0), int) else 0,
                plan_id=safe.get("plan_id", 0) if isinstance(safe.get("plan_id", 0), int) else 0,
                digest=hashlib.sha256(canonical.encode()).hexdigest(),
                trace_id=trace_id,
            )
            final = self.store.transition(
                record["evaluation_id"], "requested", "rejected",
                failure_reason=type(exc).__name__,
            )
            self._trace(final)
            return final
        record = self.store.create(
            candidate_id=contract["candidate_id"],
            plan_id=contract["plan_id"],
            digest=digest,
            trace_id=trace_id,
        )
        evaluation_id = record["evaluation_id"]
        try:
            candidate = self.candidates.get(contract["candidate_id"])
            if candidate["status"] != "approved":
                raise ValueError("Runtime evaluation requires an approved source candidate")
            if candidate["plan_id"] != contract["plan_id"]:
                raise ValueError("Runtime evaluation plan does not match the candidate")
        except (KeyError, ValueError) as exc:
            final = self.store.transition(
                evaluation_id, "requested", "rejected",
                failure_reason=type(exc).__name__,
            )
            self._trace(final)
            return final
        self.store.transition(evaluation_id, "requested", "queued")
        try:
            bundle = self._bundle(evaluation_id, candidate["candidate_id"], contract["test_files"])
        except Exception:
            return self.store.transition(evaluation_id, "queued", "failed_to_start", failure_reason="BundlePreparationError")
        self.store.transition(evaluation_id, "queued", "submitted")
        self.store.transition(evaluation_id, "submitted", "running")
        try:
            result = self.worker.run_directory(
                f"runtime_eval_{record['runtime_evaluation_record_id']}",
                bundle,
                approved=True,
                timeout_seconds=contract["execution_limits"]["timeout_seconds"],
                max_output_chars=contract["execution_limits"]["max_output_chars"],
            )
        except ExternalWorkerError as exc:
            message = str(exc).lower()
            state = "worker_unavailable" if any(word in message for word in ("disabled", "not configured", "signing key")) else "protocol_failure"
            final = self.store.transition(evaluation_id, "running", state, failure_reason=type(exc).__name__)
            self._trace(final)
            return final
        except Exception as exc:
            final = self.store.transition(evaluation_id, "running", "failed_to_start", failure_reason=type(exc).__name__)
            self._trace(final)
            return final
        common = {
            "worker_run_id": result.get("external_test_run_id"), "worker_job_id": result.get("job_id"),
            "worker_id": result.get("sandbox_claims", {}).get("worker_id"),
            "runtime_environment_id": result.get("sandbox_claims", {}).get("worker_id"),
            "returncode": result.get("returncode"), "timed_out": int(bool(result.get("timed_out"))),
            "duration_ms": result.get("duration_ms"), "output_sha256": hashlib.sha256(result.get("output", "").encode()).hexdigest(),
            "output_chars": len(result.get("output", "")), "response_verified": int(bool(result.get("response_verified"))),
            "isolation_verified": int(bool(result.get("isolation_verified"))),
        }
        if result.get("timed_out"):
            final = self.store.transition(evaluation_id, "running", "timeout", **common, failure_reason="WorkerTimeout")
        elif not result.get("response_verified"):
            final = self.store.transition(evaluation_id, "running", "protocol_failure", **common, failure_reason="UnverifiedResponse")
        elif result.get("status") != "passed" or result.get("returncode") != 0:
            final = self.store.transition(evaluation_id, "running", "execution_failure", **common, failure_reason="WorkerExecutionFailed")
        else:
            self.store.transition(evaluation_id, "running", "completed", **common)
            output = result.get("output", "")
            criteria_results = []
            for criterion in contract["evaluation_criteria"]:
                passed = (
                    criterion["kind"] == "worker_pass"
                    or (criterion["kind"] == "output_contains" and criterion["value"] in output)
                    or (criterion["kind"] == "output_excludes" and criterion["value"] not in output)
                )
                criteria_results.append({"name": criterion["name"], "kind": criterion["kind"], "passed": passed})
            state = "evaluated" if all(item["passed"] for item in criteria_results) else "evaluation_failure"
            final = self.store.transition(evaluation_id, "completed", state,
                                          criteria_json=json.dumps(criteria_results, separators=(",", ":")),
                                          failure_reason=None if state == "evaluated" else "CriteriaNotMet")
        self._trace(final)
        return final

    def _trace(self, result: dict[str, Any]) -> None:
        self.traces.annotate_lifecycle(
            result["trace_id"], processing_stage=result["status"],
            transformations=["approved_source_candidate", "runtime_evaluation_request", "external_worker_submission", "runtime_observation", "criteria_evaluation"],
            data_accessed=["candidate_environment"], data_created=[f"runtime_evaluation:{result['evaluation_id']}"],
            storage_destinations=["data_environment", "trace_environment", "runtime_environment"],
            execution_metadata={"candidate_id": result["candidate_id"], "plan_id": result["plan_id"],
                                "evaluation_id": result["evaluation_id"], "response_verified": result["response_verified"],
                                "isolation_verified": result["isolation_verified"], "runtime_verified": result["runtime_verified"],
                                "production_verified": False, "source_promoted": False, "deployed": False},
            result_summary="Candidate runtime evaluation lifecycle updated",
        )
