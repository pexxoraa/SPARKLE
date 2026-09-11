from __future__ import annotations

from typing import Any

from sparkle.ai_system_execution import ControlledExecutionService, ExecutionRejected
from sparkle.level3_execution import Level3ExecutionMixin
from sparkle.storage import utc_now
from sparkle.worker_cancellation import WorkerCancellationClient


class CancellableControlledExecutionService(Level3ExecutionMixin, ControlledExecutionService):
    """Level-3 controlled execution with signed cancellation for running jobs."""

    def request(
        self,
        contract: dict[str, Any],
        *,
        approved: bool,
        requesting_agent: str = "system",
    ) -> dict[str, Any]:
        try:
            return super().request(
                contract,
                approved=approved,
                requesting_agent=requesting_agent,
            )
        except ValueError:
            request_id = contract.get("execution_request_id") if isinstance(contract, dict) else None
            if isinstance(request_id, str):
                with self.store.connect() as connection:
                    row = connection.execute(
                        "SELECT execution_id,status FROM controlled_executions WHERE execution_request_id=?",
                        (request_id,),
                    ).fetchone()
                if row is not None and row["status"] == "cancelled":
                    self._initialize_level3()
                    self._level3_force_terminal(
                        row["execution_id"], "cancelled", "cancellation",
                    )
                    return self._enrich_level3(
                        self.store.by_execution_id(row["execution_id"])
                    )
            raise

    def cancel(self, execution_id: str, *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Controlled execution cancellation requires explicit approval")
        # Legacy tests and migrations may construct the cancellable service around an
        # already-existing ControlledExecutionStore. Materialize the additive Level-3
        # ledger before attempting to mirror cancellation state.
        self._initialize_level3()
        current = self.store.by_execution_id(execution_id)
        if current["status"] in {"requested", "authorized", "queued"}:
            result = ControlledExecutionService.cancel(self, execution_id, approved=True)
            self._level3_force_terminal(execution_id, "cancelled", "cancellation")
            return self._enrich_level3(result)
        if current["status"] != "running":
            raise ExecutionRejected("execution_not_cancellable")
        WorkerCancellationClient(self.worker).cancel(execution_id)
        now = utc_now()
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """UPDATE controlled_executions
                   SET status='cancelled',error_type='OperatorCancelled',completed_at=?,updated_at=?
                   WHERE execution_id=? AND status='running'""",
                (now, now, execution_id),
            )
            if changed.rowcount != 1:
                latest = connection.execute(
                    "SELECT status FROM controlled_executions WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                if latest is None:
                    raise KeyError("Controlled execution does not exist")
                if latest["status"] in self.store.TERMINAL:
                    self._level3_force_terminal(execution_id, "cancelled", "cancellation")
                    return self._enrich_level3(
                        self.store.by_execution_id(execution_id)
                    )
                raise ExecutionRejected("execution_state_conflict")
            connection.execute(
                "INSERT INTO controlled_execution_events(execution_id,state,created_at) VALUES(?,'cancelled',?)",
                (execution_id, now),
            )
        self._level3_force_terminal(execution_id, "cancelled", "cancellation")
        result = self.store.by_execution_id(execution_id)
        self._trace(result)
        return self._enrich_level3(result)
