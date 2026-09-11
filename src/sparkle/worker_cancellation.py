from __future__ import annotations

import hashlib
import hmac
import json
import os
import signal
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from sparkle.external_worker import ExternalWorkerClient, ExternalWorkerError, _NoRedirectHandler
from sparkle.secrets import SecretNotFoundError
from sparkle.storage import utc_now
from sparkle.worker_executor import BubblewrapExecutor, ExecutorResult, FixedUnittestExecutor, WorkerExecutionError, WorkerJob
from sparkle.worker_service import (
    ExternalWorkerService,
    WorkerAuthenticationError,
    WorkerConfig,
    WorkerConflictError,
    WorkerHandler,
    WorkerHTTPResponse,
    WorkerNotFoundError,
    WorkerPayloadError,
    WorkerServiceError,
    WorkerUnavailableError,
    build_parser,
    resolve_worker_signing_key,
)


CANCEL_PROTOCOL = "SPARKLE-WORKER-CANCEL/1"


class WorkerCancellationClient:
    """Signed cancellation side channel for a configured ExternalWorkerClient."""

    def __init__(self, worker: ExternalWorkerClient):
        self.worker = worker

    def _endpoint(self) -> str:
        endpoint = self.worker._validated_endpoint()
        parsed = urlparse(endpoint)
        path = parsed.path.rstrip("/")
        if not path.endswith("/v1/jobs"):
            raise ExternalWorkerError("External worker endpoint must terminate in /v1/jobs for cancellation")
        return endpoint.rstrip("/") + "/cancel"

    def cancel(self, execution_id: str) -> dict[str, Any]:
        if not isinstance(execution_id, str) or not execution_id.startswith("SPK-EXEC-"):
            raise ValueError("Controlled execution identity is invalid")
        if not self.worker.enabled:
            raise ExternalWorkerError("External workspace worker is disabled")
        try:
            key = self.worker.secret_resolver.first(self.worker.secret_refs).encode("utf-8")
        except SecretNotFoundError as exc:
            raise ExternalWorkerError("External worker signing key is not configured") from exc
        if len(key) < 32:
            raise ExternalWorkerError("External worker signing key must contain at least 32 bytes")
        body = ExternalWorkerClient._canonical_json({
            "protocol_version": CANCEL_PROTOCOL,
            "execution_id": execution_id,
        })
        timestamp = str(int(self.worker.clock()))
        request = urllib.request.Request(
            self._endpoint(), data=body, method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-SPARKLE-Worker-Protocol": "1",
                "X-SPARKLE-Worker-Timestamp": timestamp,
                "X-SPARKLE-Worker-Signature": ExternalWorkerClient._signature(key, timestamp, body),
            },
        )
        try:
            with self.worker.opener(request, timeout=self.worker.request_timeout_seconds) as response:
                response_body = response.read(10_001)
                if len(response_body) > 10_000:
                    raise ExternalWorkerError("Worker cancellation response exceeds its bound")
                headers = dict(response.headers.items())
        except ExternalWorkerError:
            raise
        except Exception as exc:
            raise ExternalWorkerError(f"External worker cancellation transport failed ({type(exc).__name__})") from exc
        response_timestamp = next((v for k, v in headers.items() if k.lower() == "x-sparkle-worker-timestamp"), "")
        signature = next((v for k, v in headers.items() if k.lower() == "x-sparkle-worker-signature"), "")
        try:
            issued = int(response_timestamp)
        except ValueError as exc:
            raise ExternalWorkerError("Worker cancellation response authentication failed") from exc
        if abs(self.worker.clock() - issued) > ExternalWorkerClient.MAX_CLOCK_SKEW_SECONDS:
            raise ExternalWorkerError("Worker cancellation response authentication failed")
        expected = ExternalWorkerClient._signature(key, response_timestamp, response_body)
        if not hmac.compare_digest(signature, expected):
            raise ExternalWorkerError("Worker cancellation response signature failed")
        try:
            value = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExternalWorkerError("Worker cancellation response is invalid") from exc
        if value != {"cancel_requested": True, "execution_id": execution_id, "protocol_version": CANCEL_PROTOCOL}:
            raise ExternalWorkerError("Worker cancellation response identity mismatch")
        return value


class _CancellableExecutorMixin:
    """Execute the existing fixed command while polling one cancellation event."""

    def execute_cancellable(self, job: WorkerJob, *, worker_id: str, cancel_event: threading.Event) -> ExecutorResult:
        executor_status = self.status()
        if not executor_status["available"]:
            raise WorkerExecutionError("Worker executor isolation is unavailable")
        started = time.monotonic()
        timed_out = False
        cancelled = False
        with tempfile.TemporaryDirectory(prefix="sparkle-worker-") as directory:
            project = Path(directory) / "workspace"
            self._materialize(project, job.files)
            environment = {
                "PATH": str(Path(self.python_binary).parent), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
                "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "SPARKLE_TEST_SANDBOX": "1",
            }
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as output_file:
                try:
                    process = subprocess.Popen(
                        self._command(project, job.timeout_seconds), cwd=project, env=environment,
                        stdout=output_file, stderr=subprocess.STDOUT, start_new_session=True,
                    )
                except OSError as exc:
                    raise WorkerExecutionError(f"Fixed worker child could not start ({type(exc).__name__})") from exc
                deadline = time.monotonic() + job.timeout_seconds + 2
                while process.poll() is None:
                    if cancel_event.wait(0.05):
                        cancelled = True
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait()
                        break
                    if time.monotonic() >= deadline:
                        timed_out = True
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait()
                        break
                output_file.seek(0)
                output = output_file.read(job.max_output_chars + 1)
        duration_ms = round((time.monotonic() - started) * 1000, 2)
        output_limited = len(output or "") > job.max_output_chars
        safe_output = ExternalWorkerClient._safe_output(output or "")[:job.max_output_chars]
        if cancelled:
            status = "cancelled"
        else:
            status = "passed" if process.returncode == 0 and not timed_out else "failed"
        return ExecutorResult(
            status=status, returncode=max(-255, min(int(process.returncode), 255)), timed_out=timed_out,
            output=safe_output, duration_ms=duration_ms, sandbox=self._sandbox_claims(worker_id),
            output_limited=output_limited,
        )


class CancellableFixedUnittestExecutor(_CancellableExecutorMixin, FixedUnittestExecutor):
    pass


class CancellableBubblewrapExecutor(_CancellableExecutorMixin, BubblewrapExecutor):
    pass


class CancellableExternalWorkerService(ExternalWorkerService):
    """Worker service that registers controlled executions for signed cancellation."""

    def __init__(self, config: WorkerConfig, **kwargs: Any):
        provided_executor = kwargs.get("executor")
        super().__init__(config, **kwargs)
        if provided_executor is None:
            if config.executor_mode == "bubblewrap":
                self.executor = CancellableBubblewrapExecutor(
                    bubblewrap_binary=config.bubblewrap_binary or None,
                    python_binary=config.python_binary,
                )
            else:
                self.executor = CancellableFixedUnittestExecutor(
                    python_binary=config.python_binary,
                    allow_unsafe_process=config.allow_unsafe_process_executor,
                )
        self._cancel_lock = threading.Lock()
        self._cancel_events: dict[str, threading.Event] = {}

    def _register_cancel(self, job: WorkerJob) -> threading.Event | None:
        context = job.execution_context
        if context is None:
            return None
        execution_id = context["execution_id"]
        event = threading.Event()
        with self._cancel_lock:
            if execution_id in self._cancel_events:
                raise WorkerConflictError("Controlled execution is already registered")
            self._cancel_events[execution_id] = event
        return event

    def _unregister_cancel(self, job: WorkerJob) -> None:
        if job.execution_context is not None:
            with self._cancel_lock:
                self._cancel_events.pop(job.execution_context["execution_id"], None)

    def handle_cancel(self, headers: Mapping[str, str], body: bytes) -> WorkerHTTPResponse:
        if not body or len(body) > 4_096:
            raise WorkerPayloadError("Worker cancellation body exceeds its bound")
        self.validator._authenticate(headers, body)
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkerServiceError("Worker cancellation body is invalid") from exc
        if not isinstance(value, dict) or set(value) != {"protocol_version", "execution_id"}:
            raise WorkerServiceError("Worker cancellation schema is invalid")
        execution_id = value["execution_id"]
        if value["protocol_version"] != CANCEL_PROTOCOL or not isinstance(execution_id, str) or not execution_id.startswith("SPK-EXEC-"):
            raise WorkerServiceError("Worker cancellation identity is invalid")
        with self._cancel_lock:
            event = self._cancel_events.get(execution_id)
            if event is None:
                raise WorkerNotFoundError("Controlled execution is not running")
            event.set()
        response = ExternalWorkerClient._canonical_json({
            "protocol_version": CANCEL_PROTOCOL,
            "execution_id": execution_id,
            "cancel_requested": True,
        })
        return self._signed_response(response)

    def handle_job(self, headers: Mapping[str, str], body: bytes) -> WorkerHTTPResponse:
        if not self.capacity.acquire(blocking=False):
            raise WorkerUnavailableError("Worker concurrency limit reached")
        job: WorkerJob | None = None
        claimed = False
        cancel_event: threading.Event | None = None
        try:
            job = self.validator.validate(headers, body)
            claim_state, replay_body = self.store.claim(job)
            if claim_state == "replay":
                return self._signed_response(replay_body or b"")
            claimed = True
            if not self.executor.status()["available"]:
                raise WorkerUnavailableError("Worker executor isolation is unavailable")
            cancel_event = self._register_cancel(job)
            try:
                execution_started_at = utc_now()
                if cancel_event is not None and hasattr(self.executor, "execute_cancellable"):
                    result = self.executor.execute_cancellable(job, worker_id=self.config.worker_id, cancel_event=cancel_event)
                else:
                    result = self.executor.execute(job, worker_id=self.config.worker_id)
                execution_completed_at = utc_now()
            except WorkerExecutionError as exc:
                raise WorkerUnavailableError("Worker execution failed safely") from exc
            output = result.output
            try:
                secret_text = self.signing_key.decode("utf-8")
            except UnicodeDecodeError:
                secret_text = ""
            if secret_text:
                output = output.replace(secret_text, "[REDACTED]")
            response_value: dict[str, Any] = {
                "protocol_version": ExternalWorkerClient.EXECUTION_PROTOCOL if job.execution_context is not None else ExternalWorkerClient.PROTOCOL,
                "job_id": job.job_id, "status": result.status, "returncode": result.returncode,
                "timed_out": result.timed_out, "output": output[:job.max_output_chars],
                "duration_ms": result.duration_ms, "sandbox": result.sandbox,
            }
            if job.execution_context is not None:
                executor_evidence = self.executor.status()
                response_value["status"] = "failed" if result.output_limited else result.status
                response_value.update({
                    "execution_context": job.execution_context, "worker_id": self.config.worker_id,
                    "started_at": execution_started_at, "completed_at": execution_completed_at,
                    "output_sha256": hashlib.sha256(response_value["output"].encode("utf-8")).hexdigest(),
                    "output_limited": result.output_limited,
                    "isolation_evidence": {
                        "profile_version": executor_evidence.get("isolation_profile"),
                        "executor_mode": str(executor_evidence["mode"]),
                        "preflight_passed": bool(executor_evidence["preflight_passed"]),
                        "hostile_canaries_passed": bool(executor_evidence.get("hostile_canaries_passed", False)),
                        "canaries": dict(executor_evidence.get("canaries", {})),
                    },
                })
                response_value["result_digest"] = hashlib.sha256(ExternalWorkerClient._canonical_json(response_value)).hexdigest()
            response_body = ExternalWorkerClient._canonical_json(response_value)
            if len(response_body) > ExternalWorkerClient.MAX_RESPONSE_BYTES:
                raise WorkerUnavailableError("Worker response exceeded its bound")
            self.store.complete(job, response_body)
            claimed = False
            return self._signed_response(response_body)
        finally:
            if job is not None:
                self._unregister_cancel(job)
            if claimed and job is not None:
                self.store.release(job)
            self.capacity.release()


class CancellableWorkerHandler(WorkerHandler):
    service: CancellableExternalWorkerService

    def do_POST(self) -> None:
        if self.path != "/v1/jobs/cancel":
            return super().do_POST()
        try:
            if self.headers.get("Transfer-Encoding"):
                raise WorkerServiceError("Chunked worker requests are not accepted")
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip()
            if content_type != "application/json":
                raise WorkerServiceError("Worker request Content-Type is invalid")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise WorkerServiceError("Worker request length is invalid") from exc
            if length <= 0 or length > 4_096:
                raise WorkerPayloadError("Worker cancellation request exceeds its bound")
            body = self.rfile.read(length)
            if len(body) != length:
                raise WorkerServiceError("Worker request body is incomplete")
            response = self.service.handle_cancel(dict(self.headers.items()), body)
            self._send(response.status, response.body, response.headers)
        except WorkerServiceError as exc:
            self._error(exc)
        except Exception:
            self._error(WorkerUnavailableError("Worker internal failure"))


def build_cancellable_server(service: CancellableExternalWorkerService):
    from http.server import ThreadingHTTPServer
    handler = type("ConfiguredCancellableWorkerHandler", (CancellableWorkerHandler,), {"service": service})
    server = ThreadingHTTPServer((service.config.host, service.config.port), handler)
    if service.config.direct_tls:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certfile=str(service.config.tls_certificate_file), keyfile=str(service.config.tls_private_key_file))
        server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def main(argv: list[str] | None = None) -> int:
    import argparse
    args = build_parser().parse_args(argv)
    if args.diagnose:
        from sparkle.worker_diagnostics import WorkerIsolationDiagnostic
        print(json.dumps(WorkerIsolationDiagnostic().run(), indent=2, sort_keys=True))
        return 0
    config = WorkerConfig.load()
    service = CancellableExternalWorkerService(config)
    if args.check:
        value = service.status() | {"running_cancellation": True, "cancellation_protocol": CANCEL_PROTOCOL}
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0 if value["ready"] else 2
    server = build_cancellable_server(service)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def entrypoint(argv: list[str] | None = None) -> int:
    try:
        return main(argv)
    except (ValueError, SecretNotFoundError, WorkerServiceError) as exc:
        import sys
        print(str(exc), file=sys.stderr)
        return 1
