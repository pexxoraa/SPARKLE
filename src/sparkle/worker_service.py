from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import ssl
import stat
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from sparkle.builders import WorkspaceManager
from sparkle.external_worker import ExternalWorkerClient
from sparkle.secrets import SecretNotFoundError, SecretResolver
from sparkle.storage import SQLiteStore, utc_now
from sparkle.worker_executor import (
    BubblewrapExecutor,
    FixedUnittestExecutor,
    WorkerExecutionError,
    WorkerJob,
    WorkerSourceFile,
    default_worker_python,
)


class WorkerServiceError(RuntimeError):
    status_code = 400
    code = "invalid_request"


class WorkerAuthenticationError(WorkerServiceError):
    status_code = 401
    code = "unauthorized"


class WorkerConflictError(WorkerServiceError):
    status_code = 409
    code = "job_conflict"


class WorkerPayloadError(WorkerServiceError):
    status_code = 413
    code = "payload_too_large"


class WorkerUnavailableError(WorkerServiceError):
    status_code = 503
    code = "worker_unavailable"


class WorkerNotFoundError(WorkerServiceError):
    status_code = 404
    code = "not_found"


def _configured_bool(
    values: Mapping[str, str], name: str, default: bool,
) -> bool:
    raw = values.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _configured_int(
    values: Mapping[str, str],
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    try:
        value = int(values.get(name, default))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be from {minimum} to {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    host: str = "127.0.0.1"
    port: int = 8770
    worker_id: str = "sparkle-worker"
    state_dir: Path = Path("var/worker_environment")
    signing_key_refs: tuple[str, ...] = ("SPARKLE_WORKER_SIGNING_KEY",)
    signing_key_file: Path | None = None
    executor_mode: str = "bubblewrap"
    bubblewrap_binary: str = ""
    python_binary: str = default_worker_python()
    allow_unsafe_process_executor: bool = False
    max_body_bytes: int = 8_000_000
    max_concurrency: int = 1
    replay_ttl_seconds: int = 86_400
    max_replay_entries: int = 10_000
    tls_certificate_file: Path | None = None
    tls_private_key_file: Path | None = None
    trusted_tls_termination: bool = False

    @classmethod
    def load(cls, environ: Mapping[str, str] | None = None) -> "WorkerConfig":
        values = dict(os.environ if environ is None else environ)
        state_dir = Path(values.get(
            "SPARKLE_WORKER_STATE_DIR", "var/worker_environment",
        )).expanduser().resolve()
        key_file = values.get("SPARKLE_WORKER_SIGNING_KEY_FILE", "").strip()
        cert_file = values.get("SPARKLE_WORKER_TLS_CERT_FILE", "").strip()
        private_key_file = values.get("SPARKLE_WORKER_TLS_KEY_FILE", "").strip()
        config = cls(
            host=values.get("SPARKLE_WORKER_HOST", "127.0.0.1").strip(),
            port=_configured_int(
                values, "SPARKLE_WORKER_PORT", 8770, minimum=1, maximum=65_535,
            ),
            worker_id=values.get(
                "SPARKLE_WORKER_ID", "sparkle-worker",
            ).strip(),
            state_dir=state_dir,
            signing_key_file=Path(key_file).expanduser().resolve() if key_file else None,
            executor_mode=values.get(
                "SPARKLE_WORKER_EXECUTOR", "bubblewrap",
            ).strip().lower(),
            bubblewrap_binary=values.get("SPARKLE_WORKER_BWRAP", "").strip(),
            python_binary=values.get(
                "SPARKLE_WORKER_PYTHON", default_worker_python(),
            ).strip(),
            allow_unsafe_process_executor=_configured_bool(
                values, "SPARKLE_WORKER_ALLOW_UNSAFE_PROCESS_EXECUTOR", False,
            ),
            max_body_bytes=_configured_int(
                values, "SPARKLE_WORKER_MAX_BODY_BYTES", 8_000_000,
                minimum=1_000_000, maximum=20_000_000,
            ),
            max_concurrency=_configured_int(
                values, "SPARKLE_WORKER_MAX_CONCURRENCY", 1,
                minimum=1, maximum=32,
            ),
            replay_ttl_seconds=_configured_int(
                values, "SPARKLE_WORKER_REPLAY_TTL_SECONDS", 86_400,
                minimum=300, maximum=604_800,
            ),
            max_replay_entries=_configured_int(
                values, "SPARKLE_WORKER_MAX_REPLAY_ENTRIES", 10_000,
                minimum=100, maximum=1_000_000,
            ),
            tls_certificate_file=(
                Path(cert_file).expanduser().resolve() if cert_file else None
            ),
            tls_private_key_file=(
                Path(private_key_file).expanduser().resolve()
                if private_key_file else None
            ),
            trusted_tls_termination=_configured_bool(
                values, "SPARKLE_WORKER_TRUSTED_TLS_TERMINATION", False,
            ),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.host:
            raise ValueError("Worker host cannot be empty")
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{1,127}", self.worker_id):
            raise ValueError("Worker ID must be a 2-128 character safe identifier")
        if self.executor_mode not in {"bubblewrap", "process"}:
            raise ValueError("Worker executor must be bubblewrap or process")
        if self.executor_mode == "process" and not self.allow_unsafe_process_executor:
            raise ValueError(
                "Process executor requires SPARKLE_WORKER_ALLOW_UNSAFE_PROCESS_EXECUTOR=true"
            )
        if bool(self.tls_certificate_file) != bool(self.tls_private_key_file):
            raise ValueError("Worker TLS certificate and private key must be configured together")
        if not self._is_loopback() and not (
            self.direct_tls or self.trusted_tls_termination
        ):
            raise ValueError(
                "Non-loopback worker binding requires direct TLS or trusted TLS termination"
            )

    def _is_loopback(self) -> bool:
        if self.host.lower() == "localhost":
            return True
        try:
            return ipaddress.ip_address(self.host).is_loopback
        except ValueError:
            return False

    @property
    def direct_tls(self) -> bool:
        return bool(self.tls_certificate_file and self.tls_private_key_file)


def resolve_worker_signing_key(
    config: WorkerConfig,
    resolver: SecretResolver | None = None,
) -> bytes:
    if config.signing_key_file is not None:
        path = config.signing_key_file
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError as exc:
            raise SecretNotFoundError("Worker signing-key file is unreadable") from exc
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("Worker signing-key file must be a regular non-symlink file")
            if metadata.st_mode & 0o077:
                raise ValueError(
                    "Worker signing-key file permissions must deny group/other access"
                )
            if not 32 <= metadata.st_size <= 4_096:
                raise ValueError("Worker signing-key file must contain 32-4096 bytes")
            key = os.read(descriptor, 4_097).strip()
        finally:
            os.close(descriptor)
    else:
        key = (resolver or SecretResolver()).first(config.signing_key_refs).encode("utf-8")
    if not 32 <= len(key) <= 4_096:
        raise ValueError("Worker signing key must contain 32-4096 bytes")
    return key


class WorkerRequestValidator:
    REQUEST_FIELDS = {
        "protocol_version", "job_id", "operation", "project_name", "limits", "files",
    }
    LIMIT_FIELDS = {
        "timeout_seconds", "max_output_chars", "requested_network_isolation",
        "requested_filesystem_isolation", "requested_ephemeral",
    }
    FILE_FIELDS = {"path", "sha256", "content_base64"}

    def __init__(
        self,
        signing_key: bytes,
        *,
        max_body_bytes: int = 8_000_000,
        clock: Callable[[], float] | None = None,
    ):
        self.signing_key = signing_key
        self.max_body_bytes = max_body_bytes
        self.clock = clock or time.time

    @staticmethod
    def _header(headers: Mapping[str, str], name: str) -> str:
        lowered = name.lower()
        for key, value in headers.items():
            if key.lower() == lowered and isinstance(value, str):
                return value
        return ""

    def _authenticate(self, headers: Mapping[str, str], body: bytes) -> None:
        if self._header(headers, "X-SPARKLE-Worker-Protocol") != "1":
            raise WorkerAuthenticationError("Worker request authentication failed")
        timestamp = self._header(headers, "X-SPARKLE-Worker-Timestamp")
        signature = self._header(headers, "X-SPARKLE-Worker-Signature")
        try:
            issued_at = int(timestamp)
        except ValueError as exc:
            raise WorkerAuthenticationError("Worker request authentication failed") from exc
        if abs(self.clock() - issued_at) > ExternalWorkerClient.MAX_CLOCK_SKEW_SECONDS:
            raise WorkerAuthenticationError("Worker request authentication failed")
        expected = ExternalWorkerClient._signature(self.signing_key, timestamp, body)
        if not hmac.compare_digest(signature, expected):
            raise WorkerAuthenticationError("Worker request authentication failed")

    @staticmethod
    def _validate_path(raw_path: str) -> PurePosixPath:
        if not isinstance(raw_path, str) or not raw_path or len(raw_path) > 240:
            raise WorkerServiceError("Worker source path is invalid")
        if "\\" in raw_path or raw_path.startswith("/"):
            raise WorkerServiceError("Worker source path is invalid")
        path = PurePosixPath(raw_path)
        if path.as_posix() != raw_path or any(part in {"", ".", ".."} for part in path.parts):
            raise WorkerServiceError("Worker source path is invalid")
        lowered = [part.lower() for part in path.parts]
        if any(
            part.startswith(".") or "secret" in part or "credential" in part
            or part in ExternalWorkerClient._SENSITIVE_PARTS
            for part in lowered
        ) or path.suffix.lower() in ExternalWorkerClient._SENSITIVE_SUFFIXES:
            raise WorkerServiceError("Worker source path is not accepted")
        return path

    def validate(self, headers: Mapping[str, str], body: bytes) -> WorkerJob:
        if not body or len(body) > self.max_body_bytes:
            raise WorkerPayloadError("Worker request body exceeds its bound")
        self._authenticate(headers, body)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkerServiceError("Worker request body is invalid") from exc
        if not isinstance(payload, dict) or set(payload) != self.REQUEST_FIELDS:
            raise WorkerServiceError("Worker request schema is invalid")
        job_id = payload["job_id"]
        project_name = payload["project_name"]
        if (
            payload["protocol_version"] != ExternalWorkerClient.PROTOCOL
            or payload["operation"] != ExternalWorkerClient.OPERATION
            or not isinstance(job_id, str)
            or not re.fullmatch(r"SPK-WRK-[A-F0-9]{32}", job_id)
            or not isinstance(project_name, str)
            or not WorkspaceManager.NAME_PATTERN.fullmatch(project_name)
        ):
            raise WorkerServiceError("Worker request identity is invalid")
        limits = payload["limits"]
        if not isinstance(limits, dict) or set(limits) != self.LIMIT_FIELDS:
            raise WorkerServiceError("Worker request limits are invalid")
        timeout_seconds = limits["timeout_seconds"]
        max_output_chars = limits["max_output_chars"]
        if (
            isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int)
            or not 1 <= timeout_seconds <= 60
            or isinstance(max_output_chars, bool) or not isinstance(max_output_chars, int)
            or not 1 <= max_output_chars <= ExternalWorkerClient.MAX_OUTPUT_CHARS
            or any(
                limits[name] is not True
                for name in (
                    "requested_network_isolation",
                    "requested_filesystem_isolation",
                    "requested_ephemeral",
                )
            )
        ):
            raise WorkerServiceError("Worker request limits are invalid")
        files = payload["files"]
        if not isinstance(files, list) or not 1 <= len(files) <= ExternalWorkerClient.MAX_FILES:
            raise WorkerServiceError("Worker source file count is invalid")
        accepted: list[WorkerSourceFile] = []
        seen: set[str] = set()
        total_bytes = 0
        test_files = 0
        for item in files:
            if not isinstance(item, dict) or set(item) != self.FILE_FIELDS:
                raise WorkerServiceError("Worker source file schema is invalid")
            path = self._validate_path(item["path"])
            raw_path = path.as_posix()
            if raw_path in seen:
                raise WorkerServiceError("Worker source paths must be unique")
            seen.add(raw_path)
            digest = item["sha256"]
            encoded = item["content_base64"]
            if (
                not isinstance(digest, str)
                or not re.fullmatch(r"[a-f0-9]{64}", digest)
                or not isinstance(encoded, str)
            ):
                raise WorkerServiceError("Worker source encoding is invalid")
            try:
                content = base64.b64decode(encoded, validate=True)
                content.decode("utf-8")
            except (ValueError, UnicodeDecodeError) as exc:
                raise WorkerServiceError("Worker source encoding is invalid") from exc
            if len(content) > ExternalWorkerClient.MAX_FILE_BYTES:
                raise WorkerPayloadError("Worker source file exceeds its bound")
            calculated = hashlib.sha256(content).hexdigest()
            if not hmac.compare_digest(digest, calculated):
                raise WorkerServiceError("Worker source digest is invalid")
            if self.signing_key in content:
                raise WorkerServiceError("Worker source contains a configured secret")
            total_bytes += len(content)
            if total_bytes > ExternalWorkerClient.MAX_TOTAL_BYTES:
                raise WorkerPayloadError("Worker source bundle exceeds its bound")
            if (
                path.parts[0] == "tests"
                and path.name.startswith("test")
                and path.suffix == ".py"
            ):
                test_files += 1
            accepted.append(WorkerSourceFile(raw_path, content, digest))
        if test_files == 0:
            raise WorkerServiceError("Worker source requires tests/test*.py")
        return WorkerJob(
            job_id=job_id,
            project_name=project_name,
            timeout_seconds=timeout_seconds,
            max_output_chars=max_output_chars,
            files=tuple(accepted),
            request_hash=hashlib.sha256(body).hexdigest(),
        )


class WorkerJobStore(SQLiteStore):
    def __init__(
        self,
        path: Path,
        *,
        ttl_seconds: int = 86_400,
        max_entries: int = 10_000,
        clock: Callable[[], float] | None = None,
    ):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.clock = clock or time.time
        super().__init__(path)
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS worker_jobs (
                    job_id TEXT PRIMARY KEY,
                    request_hash TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('running','complete')),
                    response_body BLOB,
                    created_at TEXT NOT NULL,
                    updated_epoch REAL NOT NULL
                )
            """)

    def _prune(self, connection, now: float) -> None:
        connection.execute(
            "DELETE FROM worker_jobs WHERE updated_epoch < ?", (now - self.ttl_seconds,),
        )
        count = connection.execute("SELECT COUNT(*) AS count FROM worker_jobs").fetchone()[
            "count"
        ]
        excess = max(0, int(count) - self.max_entries + 1)
        if excess:
            connection.execute("""
                DELETE FROM worker_jobs WHERE job_id IN (
                    SELECT job_id FROM worker_jobs WHERE state='complete'
                    ORDER BY updated_epoch ASC LIMIT ?
                )
            """, (excess,))

    def claim(self, job: WorkerJob) -> tuple[str, bytes | None]:
        now = float(self.clock())
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._prune(connection, now)
            row = connection.execute(
                "SELECT * FROM worker_jobs WHERE job_id=?", (job.job_id,),
            ).fetchone()
            if row is not None:
                if not hmac.compare_digest(row["request_hash"], job.request_hash):
                    raise WorkerConflictError("Worker job identity conflicts with prior input")
                if row["state"] == "complete" and row["response_body"] is not None:
                    return "replay", bytes(row["response_body"])
                raise WorkerConflictError("Worker job is already running")
            connection.execute("""
                INSERT INTO worker_jobs(
                    job_id, request_hash, state, response_body, created_at, updated_epoch
                ) VALUES(?,?, 'running', NULL, ?, ?)
            """, (job.job_id, job.request_hash, utc_now(), now))
        return "new", None

    def complete(self, job: WorkerJob, response_body: bytes) -> None:
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE worker_jobs SET state='complete', response_body=?, updated_epoch=?
                WHERE job_id=? AND request_hash=? AND state='running'
            """, (response_body, float(self.clock()), job.job_id, job.request_hash))
        if cursor.rowcount != 1:
            raise WorkerConflictError("Worker job claim was lost")

    def release(self, job: WorkerJob) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM worker_jobs WHERE job_id=? AND request_hash=? AND state='running'",
                (job.job_id, job.request_hash),
            )

    def status(self) -> dict[str, int]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT state, COUNT(*) AS count FROM worker_jobs GROUP BY state"
            ).fetchall()
        counts = {row["state"]: int(row["count"]) for row in rows}
        return {
            "running": counts.get("running", 0),
            "complete": counts.get("complete", 0),
            "max_entries": self.max_entries,
            "ttl_seconds": self.ttl_seconds,
        }


@dataclass(frozen=True, slots=True)
class WorkerHTTPResponse:
    status: int
    body: bytes
    headers: dict[str, str]


class ExternalWorkerService:
    def __init__(
        self,
        config: WorkerConfig,
        *,
        secret_resolver: SecretResolver | None = None,
        signing_key: bytes | None = None,
        executor: FixedUnittestExecutor | None = None,
        store: WorkerJobStore | None = None,
        clock: Callable[[], float] | None = None,
    ):
        self.config = config
        self.clock = clock or time.time
        self.signing_key = signing_key or resolve_worker_signing_key(
            config, secret_resolver,
        )
        if not 32 <= len(self.signing_key) <= 4_096:
            raise ValueError("Worker signing key must contain 32-4096 bytes")
        self.validator = WorkerRequestValidator(
            self.signing_key,
            max_body_bytes=config.max_body_bytes,
            clock=self.clock,
        )
        if executor is not None:
            self.executor = executor
        elif config.executor_mode == "bubblewrap":
            self.executor = BubblewrapExecutor(
                bubblewrap_binary=config.bubblewrap_binary or None,
                python_binary=config.python_binary,
            )
        else:
            self.executor = FixedUnittestExecutor(
                python_binary=config.python_binary,
                allow_unsafe_process=config.allow_unsafe_process_executor,
            )
        config.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        config.state_dir.chmod(0o700)
        self.store = store or WorkerJobStore(
            config.state_dir / "worker_jobs.sqlite3",
            ttl_seconds=config.replay_ttl_seconds,
            max_entries=config.max_replay_entries,
            clock=self.clock,
        )
        self.capacity = threading.BoundedSemaphore(config.max_concurrency)

    def status(self) -> dict[str, Any]:
        executor = self.executor.status()
        transport = (
            "direct_tls" if self.config.direct_tls else
            "trusted_tls_termination" if self.config.trusted_tls_termination else
            "loopback_only"
        )
        return {
            "service": "SPARKLE external test worker",
            "version": "0.20.0-alpha.1",
            "protocol": ExternalWorkerClient.PROTOCOL,
            "operation": ExternalWorkerClient.OPERATION,
            "ready": bool(executor["available"]),
            "worker_id": self.config.worker_id,
            "signing_key_configured": True,
            "credentials_exposed": False,
            "transport_security": transport,
            "direct_tls": self.config.direct_tls,
            "max_body_bytes": self.config.max_body_bytes,
            "max_concurrency": self.config.max_concurrency,
            "executor": executor,
            "replay_store": self.store.status(),
        }

    def _signed_response(self, body: bytes) -> WorkerHTTPResponse:
        timestamp = str(int(self.clock()))
        return WorkerHTTPResponse(200, body, {
            "Content-Type": "application/json; charset=utf-8",
            "X-SPARKLE-Worker-Protocol": "1",
            "X-SPARKLE-Worker-Timestamp": timestamp,
            "X-SPARKLE-Worker-Signature": ExternalWorkerClient._signature(
                self.signing_key, timestamp, body,
            ),
        })

    def handle_job(
        self, headers: Mapping[str, str], body: bytes,
    ) -> WorkerHTTPResponse:
        if not self.capacity.acquire(blocking=False):
            raise WorkerUnavailableError("Worker concurrency limit reached")
        job: WorkerJob | None = None
        claimed = False
        try:
            job = self.validator.validate(headers, body)
            claim_state, replay_body = self.store.claim(job)
            if claim_state == "replay":
                return self._signed_response(replay_body or b"")
            claimed = True
            if not self.executor.status()["available"]:
                raise WorkerUnavailableError("Worker executor isolation is unavailable")
            try:
                result = self.executor.execute(job, worker_id=self.config.worker_id)
            except WorkerExecutionError as exc:
                raise WorkerUnavailableError("Worker execution failed safely") from exc
            output = result.output
            try:
                secret_text = self.signing_key.decode("utf-8")
            except UnicodeDecodeError:
                secret_text = ""
            if secret_text:
                output = output.replace(secret_text, "[REDACTED]")
            response_value = {
                "protocol_version": ExternalWorkerClient.PROTOCOL,
                "job_id": job.job_id,
                "status": result.status,
                "returncode": result.returncode,
                "timed_out": result.timed_out,
                "output": output[: job.max_output_chars],
                "duration_ms": result.duration_ms,
                "sandbox": result.sandbox,
            }
            response_body = ExternalWorkerClient._canonical_json(response_value)
            if len(response_body) > ExternalWorkerClient.MAX_RESPONSE_BYTES:
                raise WorkerUnavailableError("Worker response exceeded its bound")
            self.store.complete(job, response_body)
            claimed = False
            return self._signed_response(response_body)
        finally:
            if claimed and job is not None:
                self.store.release(job)
            self.capacity.release()


class WorkerHandler(BaseHTTPRequestHandler):
    service: ExternalWorkerService
    server_version = "SPARKLE-Worker/0.20"

    def log_message(self, format: str, *args: object) -> None:
        # Do not serialize client identity, headers, queries, or source bodies.
        safe_path = self.path.split("?", 1)[0]
        if safe_path not in {"/health", "/v1/jobs"}:
            safe_path = "/[unknown]"
        print(f"worker - {self.command} {safe_path}")

    def _send(
        self,
        status: int,
        body: bytes,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for name, value in (headers or {}).items():
            if name.lower() != "content-type":
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _error(self, error: WorkerServiceError) -> None:
        body = json.dumps(
            {"ok": False, "error": error.code}, separators=(",", ":"),
        ).encode("utf-8")
        self._send(error.status_code, body)

    def do_GET(self) -> None:
        if self.path != "/health":
            return self._error(WorkerNotFoundError("Unknown worker route"))
        status = self.service.status()
        body = json.dumps(
            {"ok": status["ready"], "status": status},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self._send(200 if status["ready"] else 503, body)

    def do_POST(self) -> None:
        if self.path != "/v1/jobs":
            return self._error(WorkerNotFoundError("Unknown worker route"))
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
            if length <= 0:
                raise WorkerServiceError("Worker request body is required")
            if length > self.service.config.max_body_bytes:
                raise WorkerPayloadError("Worker request exceeds its bound")
            body = self.rfile.read(length)
            if len(body) != length:
                raise WorkerServiceError("Worker request body is incomplete")
            response = self.service.handle_job(dict(self.headers.items()), body)
            self._send(response.status, response.body, response.headers)
        except WorkerServiceError as exc:
            self._error(exc)
        except Exception:
            self._error(WorkerUnavailableError("Worker internal failure"))


def build_server(
    service: ExternalWorkerService,
) -> ThreadingHTTPServer:
    handler = type("ConfiguredWorkerHandler", (WorkerHandler,), {"service": service})
    server = ThreadingHTTPServer((service.config.host, service.config.port), handler)
    if service.config.direct_tls:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(
            certfile=str(service.config.tls_certificate_file),
            keyfile=str(service.config.tls_private_key_file),
        )
        server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def serve_worker(service: ExternalWorkerService) -> None:
    server = build_server(service)
    scheme = "https" if service.config.direct_tls else "http"
    print(f"SPARKLE worker: {scheme}://{service.config.host}:{service.config.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sparkle-worker", description="SPARKLE external fixed-test worker",
    )
    parser.add_argument(
        "--check", action="store_true", help="Validate configuration and isolation preflight",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = WorkerConfig.load()
    service = ExternalWorkerService(config)
    if args.check:
        value = service.status()
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0 if value["ready"] else 2
    serve_worker(service)
    return 0


def entrypoint(argv: list[str] | None = None) -> int:
    try:
        return main(argv)
    except (ValueError, SecretNotFoundError, WorkerServiceError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(entrypoint())
