from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from sparkle.automation import AutomationRunner, AutomationStore
from sparkle.storage import utc_now


class ReliableAutomationStore(AutomationStore):
    """Automation storage with immutable, claim-bound per-attempt evidence."""

    def initialize(self) -> None:
        super().initialize()
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS automation_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    automation_id INTEGER NOT NULL
                        REFERENCES automations(id) ON DELETE CASCADE,
                    claim_digest TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('success','failure')),
                    retry_allowed INTEGER NOT NULL,
                    trace_id TEXT,
                    error_type TEXT,
                    result_summary TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    UNIQUE(automation_id, claim_digest, attempt)
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_automation_attempts_automation
                ON automation_attempts(automation_id, id)
            """)

    @staticmethod
    def _attempt_public(row: Any) -> dict[str, Any]:
        return {
            "attempt_id": row["id"],
            "automation_id": row["automation_id"],
            "attempt": row["attempt"],
            "status": row["status"],
            "retry_allowed": bool(row["retry_allowed"]),
            "trace_id": row["trace_id"],
            "error_type": row["error_type"],
            "result_summary": row["result_summary"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
        }

    def record_attempt(
        self,
        item: dict[str, Any],
        attempt: int,
        *,
        status: str,
        retry_allowed: bool,
        started_at: str,
        trace_id: str | None = None,
        error_type: str | None = None,
        result_summary: str | None = None,
        finished_at: str | None = None,
    ) -> dict[str, Any]:
        token = item.get("_claim_token")
        if not isinstance(token, str) or not 16 <= len(token) <= 128:
            raise ValueError("Automation attempt requires an active claim token")
        if (
            isinstance(attempt, bool)
            or not isinstance(attempt, int)
            or not 1 <= attempt <= 3
        ):
            raise ValueError("Automation attempt number must be from 1 to 3")
        if status not in {"success", "failure"}:
            raise ValueError("Automation attempt status is invalid")
        if not isinstance(retry_allowed, bool):
            raise ValueError("Automation retry evidence must be boolean")
        if trace_id is not None and (
            not isinstance(trace_id, str) or len(trace_id) > 128
        ):
            raise ValueError("Automation attempt trace identity is invalid")
        if error_type is not None and (
            not isinstance(error_type, str) or len(error_type) > 200
        ):
            raise ValueError("Automation attempt error type is invalid")
        summary = result_summary[:1_000] if result_summary else None
        completed = finished_at or utc_now()
        claim_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                """SELECT 1 FROM automations
                   WHERE id=? AND last_status='running' AND claim_token=?""",
                (item["id"], token),
            ).fetchone()
            if current is None:
                raise RuntimeError("Automation attempt lost its active claim")
            cursor = connection.execute(
                """INSERT INTO automation_attempts(
                    automation_id,claim_digest,attempt,status,retry_allowed,
                    trace_id,error_type,result_summary,started_at,finished_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    item["id"],
                    claim_digest,
                    attempt,
                    status,
                    int(retry_allowed),
                    trace_id,
                    error_type,
                    summary,
                    started_at,
                    completed,
                ),
            )
            row = connection.execute(
                "SELECT * FROM automation_attempts WHERE id=?",
                (cursor.lastrowid,),
            ).fetchone()
        return self._attempt_public(row)

    def list_attempts(
        self,
        automation_id: int | None = None,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 200
        ):
            raise ValueError("Automation attempt limit must be from 1 to 200")
        parameters: tuple[Any, ...]
        if automation_id is None:
            sql = "SELECT * FROM automation_attempts ORDER BY id DESC LIMIT ?"
            parameters = (limit,)
        else:
            if (
                isinstance(automation_id, bool)
                or not isinstance(automation_id, int)
                or automation_id < 1
            ):
                raise ValueError("Automation identity is invalid")
            sql = (
                "SELECT * FROM automation_attempts "
                "WHERE automation_id=? ORDER BY id DESC LIMIT ?"
            )
            parameters = (automation_id, limit)
        with self.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [self._attempt_public(row) for row in rows]


class ReliableAutomationRunner(AutomationRunner):
    """Retries only failures with deterministic evidence that replay is safe."""

    store: ReliableAutomationStore

    def _latest_automation_trace(self) -> dict[str, Any] | None:
        if self.traces is None:
            return None
        for trace in self.traces.recent(limit=5):
            if trace.get("input_source") == "automation":
                return trace
        return None

    @staticmethod
    def _trace_identity(trace: dict[str, Any] | None) -> str | None:
        value = trace.get("trace_id") if trace else None
        return value if isinstance(value, str) else None

    def _retry_allowed_after_failure(
        self,
        item: dict[str, Any],
        before_trace_id: str | None,
    ) -> tuple[bool, str | None]:
        action = item["action"]
        action_type = action.get("type")
        if action_type == "notification":
            # NotificationStore dedupe makes a retried delivery idempotent only
            # when an explicit key binds all attempts to one logical delivery.
            key = action.get("dedupe_key")
            return bool(isinstance(key, str) and key.strip()), None
        if action_type != "agent":
            return False, None

        after = self._latest_automation_trace()
        after_id = self._trace_identity(after)
        if after is None or after_id == before_trace_id:
            # The failure happened before the orchestrator created execution
            # evidence (for example an unknown agent); no model/tool action ran.
            return True, None
        # A tool call may have committed an external or persistent side effect
        # before a later step failed. Never replay such an attempt automatically.
        tools = after.get("tools") or []
        created = after.get("data_created") or []
        if tools or created:
            return False, after_id
        return True, after_id

    def run_due(
        self,
        now: datetime | None = None,
        *,
        claim_token: str | None = None,
        lease_seconds: int = 3_600,
    ) -> list[dict[str, Any]]:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        claimed = self.store.claim_due(
            current.isoformat(),
            claim_token=claim_token,
            lease_seconds=lease_seconds,
        )
        alerts = self.proactive.inspect(current)
        for candidate in self.store.conditions():
            if self._condition_matches(candidate, alerts, current):
                item = self.store.claim_condition(
                    candidate["id"],
                    current.isoformat(),
                    claim_token=claim_token,
                    lease_seconds=lease_seconds,
                )
                if item:
                    claimed.append(item)

        runs: list[dict[str, Any]] = []
        for item in claimed:
            started_at = utc_now()
            max_attempts = int(item["action"].get("max_attempts", 1))
            attempts = 0
            result_summary = None
            trace_id = None
            error: Exception | None = None
            while attempts < max_attempts:
                attempts += 1
                attempt_started = utc_now()
                before_trace_id = self._trace_identity(
                    self._latest_automation_trace()
                )
                try:
                    result_summary, trace_id = self._execute(item)
                    self.store.record_attempt(
                        item,
                        attempts,
                        status="success",
                        retry_allowed=False,
                        started_at=attempt_started,
                        trace_id=trace_id,
                        result_summary="Automation attempt completed",
                    )
                    error = None
                    break
                except Exception as exc:
                    error = exc
                    retry_allowed, failed_trace_id = (
                        self._retry_allowed_after_failure(
                            item, before_trace_id
                        )
                    )
                    retry_allowed = (
                        retry_allowed and attempts < max_attempts
                    )
                    self.store.record_attempt(
                        item,
                        attempts,
                        status="failure",
                        retry_allowed=retry_allowed,
                        started_at=attempt_started,
                        trace_id=failed_trace_id,
                        error_type=type(exc).__name__,
                        result_summary="Automation attempt failed",
                    )
                    if not retry_allowed:
                        break
            if error is None:
                runs.append(
                    self.store.finish(
                        item,
                        status="success",
                        attempts=attempts,
                        started_at=started_at,
                        result_summary=result_summary,
                        trace_id=trace_id,
                        now=current,
                    )
                )
            else:
                runs.append(
                    self.store.finish(
                        item,
                        status="failure",
                        attempts=attempts,
                        started_at=started_at,
                        result_summary="Automation action failed",
                        error_type=type(error).__name__,
                        now=current,
                    )
                )
        return runs
