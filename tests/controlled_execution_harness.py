"""TEST HARNESS ONLY.

This module exercises the controlled-execution protocol deterministically. It
does not create namespaces and must never be used as Level 3 isolation evidence.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sparkle.external_worker import ExternalWorkerError


class HarnessResponse:
    def __init__(self, status: int, body: bytes, headers: dict[str, str]):
        self.status = status
        self.body = body
        self.headers = headers

    def read(self, limit: int = -1) -> bytes:
        return self.body if limit < 0 else self.body[:limit]

    def getcode(self) -> int:
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


class AuthenticatedServiceTestHarness:
    """Routes signed requests directly to the real service without claiming TLS."""

    def __init__(
        self,
        service: Any,
        *,
        mutate: Callable[[Any], Any] | None = None,
        transport_error: Exception | None = None,
    ):
        self.service = service
        self.mutate = mutate
        self.transport_error = transport_error
        self.calls = 0
        self.request_bodies: list[bytes] = []

    def __call__(self, request: Any, timeout: int) -> HarnessResponse:
        self.calls += 1
        self.request_bodies.append(bytes(request.data))
        if self.transport_error is not None:
            raise self.transport_error
        response = self.service.handle_job(dict(request.header_items()), request.data)
        if self.mutate is not None:
            response = self.mutate(response)
        return HarnessResponse(response.status, response.body, response.headers)


class DeterministicWorkerTestHarness:
    """Simulates bounded worker outcomes; it is not an isolated worker."""

    SCENARIOS = {
        "success", "timeout", "output_limit", "execution_failure",
        "identity_mismatch", "result_tamper", "worker_failure",
    }

    def __init__(self, scenario: str = "success"):
        if scenario not in self.SCENARIOS:
            raise ValueError("Unknown controlled-execution test scenario")
        self.scenario = scenario
        self.calls = 0

    def run_controlled_execution(
        self, _name: str, _workspace: Any, *, execution_context: dict[str, Any],
        **_limits: Any,
    ) -> dict[str, Any]:
        self.calls += 1
        if self.scenario == "worker_failure":
            raise ExternalWorkerError("External worker transport failed (test harness)")
        value = {
            "external_test_run_id": 1,
            "job_id": "SPK-WRK-" + "A" * 32,
            "worker_id": "test-harness-worker",
            "status": "passed",
            "returncode": 0,
            "timed_out": False,
            "output_limited": False,
            "output": "test harness output",
            "output_sha256": "1" * 64,
            "result_digest": "2" * 64,
            "response_verified": True,
            "isolation_verified": False,
            "execution_context": execution_context,
        }
        if self.scenario == "timeout":
            value.update(status="failed", returncode=-9, timed_out=True)
        elif self.scenario == "output_limit":
            value.update(status="failed", output_limited=True)
        elif self.scenario == "execution_failure":
            value.update(status="failed", returncode=1)
        elif self.scenario == "identity_mismatch":
            value["execution_context"] = {}
        elif self.scenario == "result_tamper":
            value["result_digest"] = "f" * 64
            value["response_verified"] = False
        return value

    def evidence(self) -> dict[str, Any]:
        return {
            "test_harness": True,
            "isolated_production_worker": False,
            "level_3_evidence": False,
            "scenario": self.scenario,
            "calls": self.calls,
        }
