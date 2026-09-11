from __future__ import annotations

from typing import Any

from sparkle.ai_system_execution import ControlledExecutionService, ExecutionRejected
from sparkle.storage import utc_now
from sparkle.worker_cancellation import WorkerCancellationClient


class CancellableControlledExecutionService(ControlledExecutionService):
    """Controlled execution service with signed cancellation for RUNNING jobs."""

    def request(self, contract: dict[str, Any], *, approved: bool) -> dict[str, Any]:
        try:
            return super().request(contract, approved=approved)
        except ValueError:
            # A concurrent cancellation can make the legacy response-processing
            # transition stale after the worker process has already been killed.
            request_id = contract.get("execution_request_id") if isinstance(contract, dict) else None
            if isinstance(request_id, str):
                with self.store.connect() as connection:
                    row = connection.execute(
                        "SELECT execution_id,status FROM controlled_executions WHERE execution_request_id=?",
                        (request_id,),
                    ).fetchone()
                if row is not None and row["status"] == "cancelled":
                    return self.store.by_execution_id(row["execution_id"])
            raise

    def cancel(self, execution_id: str, *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Controlled execution cancellation requires explicit approval")
        current = self.store.by_execution_id(execution_id)
        if current["status"] in {"requested", "authorized", "queued"}:
            return super().cancel(execution_id, approved=True)
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
                    return self.store.by_execution_id(execution_id)
                raise ExecutionRejected("execution_state_conflict")
            connection.execute(
                "INSERT INTO controlled_execution_events(execution_id,state,created_at) VALUES(?,'cancelled',?)",
                (execution_id, now),
            )
        result = self.store.by_execution_id(execution_id)
        self._trace(result)
        return result
