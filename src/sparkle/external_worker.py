from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
import urllib.request
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sparkle.builders import WorkspaceManager
from sparkle.config import data_root
from sparkle.secrets import SecretNotFoundError, SecretResolver
from sparkle.storage import SQLiteStore, utc_now


class ExternalWorkerError(RuntimeError):
    """A safe external-worker boundary failure."""


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects so signed source is never forwarded to another origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class ExternalWorkerClient(SQLiteStore):
    """Submits one fixed test operation to an explicitly configured HTTPS worker."""

    PROTOCOL = "SPARKLE-WORKER/1"
    OPERATION = "python_unittest"
    MAX_FILES = 500
    MAX_TOTAL_BYTES = 5_000_000
    MAX_FILE_BYTES = 500_000
    MAX_OUTPUT_CHARS = 12_000
    MAX_RESPONSE_BYTES = 100_000
    MAX_CLOCK_SKEW_SECONDS = 300
    _RESPONSE_FIELDS = {
        "protocol_version", "job_id", "status", "returncode", "timed_out",
        "output", "duration_ms", "sandbox",
    }
    _SANDBOX_FIELDS = {
        "worker_id", "filesystem_isolation", "network_isolation", "ephemeral",
        "resource_limits",
    }
    _SENSITIVE_PARTS = {
        ".git", ".ssh", ".env", "secrets", "credentials", "id_rsa", "id_ed25519",
    }
    _SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
    _SECRET_PATTERN = re.compile(
        r"(?i)\b(authorization|api[_-]?key|token|secret)(\s*[:=]\s*|\s+)([^\s,;]+)"
    )
    _BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[^\s,;]+")

    def __init__(
        self,
        root: Path | None = None,
        path: Path | None = None,
        *,
        enabled: bool = False,
        endpoint: str = "",
        secret_refs: tuple[str, ...] = ("SPARKLE_WORKER_SIGNING_KEY",),
        request_timeout_seconds: int = 15,
        job_timeout_seconds: int = 10,
        max_payload_bytes: int = 8_000_000,
        secret_resolver: SecretResolver | None = None,
        opener: Callable[..., Any] | None = None,
        clock: Callable[[], float] | None = None,
        job_id_factory: Callable[[], str] | None = None,
    ):
        if not 1 <= request_timeout_seconds <= 120:
            raise ValueError("External worker request timeout must be from 1 to 120 seconds")
        if not 1 <= job_timeout_seconds <= 60:
            raise ValueError("External worker job timeout must be from 1 to 60 seconds")
        if not 1_000_000 <= max_payload_bytes <= 20_000_000:
            raise ValueError("External worker payload limit must be from 1000000 to 20000000 bytes")
        if not secret_refs or not all(isinstance(item, str) and item for item in secret_refs):
            raise ValueError("External worker secret references must be non-empty names")
        self.root = (root or data_root() / "applications").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.enabled = enabled
        self.endpoint = endpoint.strip()
        self.secret_refs = secret_refs
        self.request_timeout_seconds = request_timeout_seconds
        self.job_timeout_seconds = job_timeout_seconds
        self.max_payload_bytes = max_payload_bytes
        self.secret_resolver = secret_resolver or SecretResolver()
        self.opener = opener or urllib.request.build_opener(_NoRedirectHandler()).open
        self.clock = clock or time.time
        self.job_id_factory = job_id_factory or (
            lambda: f"SPK-WRK-{uuid.uuid4().hex.upper()}"
        )
        super().__init__(path or data_root() / "data_environment" / "external_worker_runs.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS external_worker_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL UNIQUE,
                    project_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    returncode INTEGER,
                    timed_out INTEGER NOT NULL,
                    output TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    file_count INTEGER NOT NULL,
                    total_bytes INTEGER NOT NULL,
                    response_verified INTEGER NOT NULL,
                    isolation_verified INTEGER NOT NULL,
                    sandbox_json TEXT NOT NULL,
                    error_type TEXT,
                    created_at TEXT NOT NULL
                )
            """)

    def _endpoint_is_valid(self) -> bool:
        try:
            parsed = urlparse(self.endpoint)
            return bool(
                parsed.scheme == "https"
                and parsed.hostname
                and not parsed.username
                and not parsed.password
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            return False

    def _validated_endpoint(self) -> str:
        if not self.endpoint:
            raise ExternalWorkerError("External worker endpoint is not configured")
        if not self._endpoint_is_valid():
            raise ExternalWorkerError(
                "External worker endpoint must be HTTPS without credentials, query, or fragment"
            )
        return self.endpoint

    def status(self) -> dict[str, Any]:
        secret_status = self.secret_resolver.status(self.secret_refs)
        endpoint_valid = self._endpoint_is_valid()
        signing_key_configured = any(secret_status.values())
        return {
            "enabled": self.enabled,
            "protocol": self.PROTOCOL,
            "operation": self.OPERATION,
            "endpoint_configured": bool(self.endpoint),
            "endpoint_https_valid": endpoint_valid,
            "signing_key_configured": signing_key_configured,
            "configured": self.enabled and endpoint_valid and signing_key_configured,
            "https_required": True,
            "explicit_approval_required": True,
            "agent_tool_registered": False,
            "max_files": self.MAX_FILES,
            "max_total_bytes": self.MAX_TOTAL_BYTES,
            "max_payload_bytes": self.max_payload_bytes,
            "live_worker_verified": False,
            "isolation_verified": False,
            "credentials_exposed": False,
        }

    def _project_root(self, project_name: str) -> Path:
        if not WorkspaceManager.NAME_PATTERN.fullmatch(project_name):
            raise ValueError("Project name must be a 2-64 character lowercase identifier")
        project = self.root / project_name
        if project.is_symlink():
            raise ValueError("External worker submission rejects every symlink")
        resolved = project.resolve()
        if resolved.parent != self.root or not resolved.is_dir():
            raise ValueError(f"Application workspace does not exist: {project_name}")
        return resolved

    @classmethod
    def _validate_source_path(cls, relative: Path) -> None:
        if len(relative.as_posix()) > 240:
            raise ValueError("External worker source path exceeds 240 characters")
        lowered = [part.lower() for part in relative.parts]
        if any(
            part.startswith(".")
            or part in cls._SENSITIVE_PARTS
            or "secret" in part
            or "credential" in part
            for part in lowered
        ):
            raise ValueError("External worker submission rejects hidden or sensitive paths")
        if relative.suffix.lower() in cls._SENSITIVE_SUFFIXES:
            raise ValueError("External worker submission rejects credential-file suffixes")

    def _source_bundle(
        self, project: Path, *, forbidden_values: tuple[bytes, ...] = (),
    ) -> tuple[list[dict[str, str]], int, int]:
        files: list[dict[str, str]] = []
        total_bytes = 0
        test_files = 0
        for current, directories, names in os.walk(project, followlinks=False):
            directories.sort()
            names.sort()
            current_path = Path(current)
            for name in [*directories, *names]:
                if (current_path / name).is_symlink():
                    raise ValueError("External worker submission rejects every symlink")
            for name in names:
                candidate = current_path / name
                if not candidate.is_file():
                    raise ValueError("External worker submission requires regular files")
                relative = candidate.relative_to(project)
                self._validate_source_path(relative)
                content = candidate.read_bytes()
                if len(content) > self.MAX_FILE_BYTES:
                    raise ValueError(
                        f"External worker source file exceeds {self.MAX_FILE_BYTES} bytes"
                    )
                try:
                    content.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise ValueError("External worker submission accepts UTF-8 source files only") from exc
                if any(value and value in content for value in forbidden_values):
                    raise ValueError("External worker submission contains a configured secret value")
                total_bytes += len(content)
                if len(files) + 1 > self.MAX_FILES or total_bytes > self.MAX_TOTAL_BYTES:
                    raise ValueError("Workspace exceeds external worker submission bounds")
                relative_text = relative.as_posix()
                if (
                    relative.parts[0] == "tests"
                    and relative.name.startswith("test")
                    and relative.suffix == ".py"
                ):
                    test_files += 1
                files.append({
                    "path": relative_text,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "content_base64": base64.b64encode(content).decode("ascii"),
                })
        if test_files == 0:
            raise ValueError("Workspace requires at least one tests/test*.py file")
        return files, total_bytes, test_files

    @staticmethod
    def _canonical_json(value: dict[str, Any]) -> bytes:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")

    @staticmethod
    def _signature(key: bytes, timestamp: str, body: bytes) -> str:
        digest = hmac.new(key, timestamp.encode("ascii") + b"." + body, hashlib.sha256)
        return f"sha256={digest.hexdigest()}"

    @classmethod
    def _safe_output(cls, value: str) -> str:
        sanitized = cls._BEARER_PATTERN.sub("Bearer [REDACTED]", value)
        sanitized = cls._SECRET_PATTERN.sub(r"\1\2[REDACTED]", sanitized)
        return sanitized.strip()[: cls.MAX_OUTPUT_CHARS]

    def _response_header(self, response: Any, name: str) -> str:
        value = response.headers.get(name) if getattr(response, "headers", None) else None
        if not isinstance(value, str) or not value:
            raise ExternalWorkerError("External worker response authentication is missing")
        return value

    def _validate_response(
        self, response: Any, body: bytes, *, key: bytes, expected_job_id: str,
    ) -> dict[str, Any]:
        status_code = response.getcode() if hasattr(response, "getcode") else None
        if status_code != 200:
            raise ExternalWorkerError("External worker response status code is invalid")
        content_type = (
            response.headers.get("Content-Type", "")
            if getattr(response, "headers", None) else ""
        ).split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ExternalWorkerError("External worker response Content-Type is invalid")
        protocol_header = self._response_header(response, "X-SPARKLE-Worker-Protocol")
        if protocol_header != "1":
            raise ExternalWorkerError("External worker response protocol header is invalid")
        timestamp = self._response_header(response, "X-SPARKLE-Worker-Timestamp")
        signature = self._response_header(response, "X-SPARKLE-Worker-Signature")
        try:
            response_time = int(timestamp)
        except ValueError as exc:
            raise ExternalWorkerError("External worker response timestamp is invalid") from exc
        if abs(self.clock() - response_time) > self.MAX_CLOCK_SKEW_SECONDS:
            raise ExternalWorkerError("External worker response timestamp is stale")
        expected_signature = self._signature(key, timestamp, body)
        if not hmac.compare_digest(signature, expected_signature):
            raise ExternalWorkerError("External worker response signature is invalid")
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExternalWorkerError("External worker response is not valid UTF-8 JSON") from exc
        if not isinstance(value, dict) or set(value) != self._RESPONSE_FIELDS:
            raise ExternalWorkerError("External worker response schema is invalid")
        if value["protocol_version"] != self.PROTOCOL or value["job_id"] != expected_job_id:
            raise ExternalWorkerError("External worker response identity is invalid")
        if value["status"] not in {"passed", "failed"}:
            raise ExternalWorkerError("External worker response status is invalid")
        returncode = value["returncode"]
        timed_out = value["timed_out"]
        duration_ms = value["duration_ms"]
        output = value["output"]
        sandbox = value["sandbox"]
        if (
            isinstance(returncode, bool) or not isinstance(returncode, int)
            or not -255 <= returncode <= 255
            or not isinstance(timed_out, bool)
            or isinstance(duration_ms, bool) or not isinstance(duration_ms, (int, float))
            or not 0 <= duration_ms <= 3_600_000
            or not isinstance(output, str)
            or not isinstance(sandbox, dict) or set(sandbox) != self._SANDBOX_FIELDS
        ):
            raise ExternalWorkerError("External worker response value types are invalid")
        if len(output) > self.MAX_RESPONSE_BYTES:
            raise ExternalWorkerError("External worker response output exceeds its bound")
        if not isinstance(sandbox["worker_id"], str) or not 1 <= len(sandbox["worker_id"]) <= 128:
            raise ExternalWorkerError("External worker sandbox identity is invalid")
        if not all(
            isinstance(sandbox[name], bool)
            for name in self._SANDBOX_FIELDS - {"worker_id"}
        ):
            raise ExternalWorkerError("External worker sandbox claims are invalid")
        passed = returncode == 0 and not timed_out
        if (value["status"] == "passed") != passed:
            raise ExternalWorkerError("External worker response status is inconsistent")
        value["output"] = self._safe_output(output)
        value["duration_ms"] = round(float(duration_ms), 2)
        return value

    def _record(
        self,
        *,
        job_id: str,
        project_name: str,
        status: str,
        returncode: int | None,
        timed_out: bool,
        output: str,
        duration_ms: float,
        file_count: int,
        total_bytes: int,
        response_verified: bool,
        sandbox: dict[str, Any] | None,
        error_type: str | None,
    ) -> tuple[int, str]:
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO external_worker_runs(
                    job_id, project_name, status, returncode, timed_out, output,
                    duration_ms, file_count, total_bytes, response_verified,
                    isolation_verified, sandbox_json, error_type, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                job_id, project_name, status, returncode, int(timed_out), output,
                duration_ms, file_count, total_bytes, int(response_verified), 0,
                json.dumps(sandbox or {}, sort_keys=True, separators=(",", ":")),
                error_type, now,
            ))
        return int(cursor.lastrowid), now

    def run_directory(
        self,
        project_name: str,
        workspace: Path,
        *,
        approved: bool,
        timeout_seconds: int | None = None,
        max_output_chars: int | None = None,
    ) -> dict[str, Any]:
        """Internal operator boundary for evaluator-owned, non-production bundles."""
        if approved is not True:
            raise ExternalWorkerError("External runtime evaluation requires explicit approval")
        if not WorkspaceManager.NAME_PATTERN.fullmatch(project_name):
            raise ValueError("Project name must be a 2-64 character lowercase identifier")
        if workspace.is_symlink():
            raise ValueError("External worker submission rejects every symlink")
        resolved = workspace.resolve()
        if not resolved.is_dir():
            raise ValueError("External runtime evaluation workspace does not exist")
        timeout = self.job_timeout_seconds if timeout_seconds is None else timeout_seconds
        output_limit = self.MAX_OUTPUT_CHARS if max_output_chars is None else max_output_chars
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 60:
            raise ValueError("External runtime evaluation timeout is invalid")
        if not isinstance(output_limit, int) or isinstance(output_limit, bool) or not 100 <= output_limit <= self.MAX_OUTPUT_CHARS:
            raise ValueError("External runtime evaluation output limit is invalid")
        return self._run(
            project_name,
            resolved,
            timeout_seconds=timeout,
            max_output_chars=output_limit,
        )

    def run(self, project_name: str) -> dict[str, Any]:
        return self._run(project_name, self._project_root(project_name))

    def _run(
        self,
        project_name: str,
        project: Path,
        *,
        timeout_seconds: int | None = None,
        max_output_chars: int | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise ExternalWorkerError(
                "External workspace worker is disabled; enable it only after deploying and validating a dedicated worker"
            )
        endpoint = self._validated_endpoint()
        try:
            signing_key = self.secret_resolver.first(self.secret_refs).encode("utf-8")
        except SecretNotFoundError as exc:
            raise ExternalWorkerError("External worker signing key is not configured") from exc
        if len(signing_key) < 32:
            raise ExternalWorkerError("External worker signing key must contain at least 32 bytes")
        files, total_bytes, test_files = self._source_bundle(
            project, forbidden_values=(signing_key,),
        )
        job_id = self.job_id_factory()
        if not re.fullmatch(r"SPK-WRK-[A-F0-9]{32}", job_id):
            raise ExternalWorkerError("External worker job identifier is invalid")
        payload = {
            "protocol_version": self.PROTOCOL,
            "job_id": job_id,
            "operation": self.OPERATION,
            "project_name": project_name,
            "limits": {
                "timeout_seconds": timeout_seconds or self.job_timeout_seconds,
                "max_output_chars": max_output_chars or self.MAX_OUTPUT_CHARS,
                "requested_network_isolation": True,
                "requested_filesystem_isolation": True,
                "requested_ephemeral": True,
            },
            "files": files,
        }
        body = self._canonical_json(payload)
        if len(body) > self.max_payload_bytes:
            raise ValueError("External worker request exceeds the serialized payload bound")
        timestamp = str(int(self.clock()))
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-SPARKLE-Worker-Protocol": "1",
                "X-SPARKLE-Worker-Timestamp": timestamp,
                "X-SPARKLE-Worker-Signature": self._signature(signing_key, timestamp, body),
            },
            method="POST",
        )
        started = time.monotonic()
        try:
            with self.opener(request, timeout=self.request_timeout_seconds) as response:
                response_body = response.read(self.MAX_RESPONSE_BYTES + 1)
                if len(response_body) > self.MAX_RESPONSE_BYTES:
                    raise ExternalWorkerError("External worker response exceeds its size bound")
                value = self._validate_response(
                    response, response_body, key=signing_key, expected_job_id=job_id,
                )
        except ExternalWorkerError as exc:
            self._record(
                job_id=job_id, project_name=project_name, status="error",
                returncode=None, timed_out=False, output="", duration_ms=round(
                    (time.monotonic() - started) * 1000, 2,
                ), file_count=len(files), total_bytes=total_bytes,
                response_verified=False, sandbox=None, error_type=type(exc).__name__,
            )
            raise
        except Exception as exc:
            self._record(
                job_id=job_id, project_name=project_name, status="error",
                returncode=None, timed_out=False, output="", duration_ms=round(
                    (time.monotonic() - started) * 1000, 2,
                ), file_count=len(files), total_bytes=total_bytes,
                response_verified=False, sandbox=None, error_type=type(exc).__name__,
            )
            raise ExternalWorkerError(
                f"External worker transport failed ({type(exc).__name__})"
            ) from exc
        run_id, created_at = self._record(
            job_id=job_id, project_name=project_name, status=value["status"],
            returncode=value["returncode"], timed_out=value["timed_out"],
            output=value["output"], duration_ms=value["duration_ms"],
            file_count=len(files), total_bytes=total_bytes,
            response_verified=True, sandbox=value["sandbox"], error_type=None,
        )
        return {
            "external_test_run_id": run_id,
            "job_id": job_id,
            "project_name": project_name,
            "status": value["status"],
            "framework": self.OPERATION,
            "test_files": test_files,
            "returncode": value["returncode"],
            "timed_out": value["timed_out"],
            "output": value["output"],
            "duration_ms": value["duration_ms"],
            "file_count": len(files),
            "total_bytes": total_bytes,
            "response_verified": True,
            "sandbox_claims": value["sandbox"],
            "isolation_verified": False,
            "created_at": created_at,
        }

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM external_worker_runs ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [self._public(row) for row in rows]

    @staticmethod
    def _public(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "external_test_run_id": row["id"],
            "job_id": row["job_id"],
            "project_name": row["project_name"],
            "status": row["status"],
            "framework": ExternalWorkerClient.OPERATION,
            "returncode": row["returncode"],
            "timed_out": bool(row["timed_out"]),
            "output": row["output"],
            "duration_ms": row["duration_ms"],
            "file_count": row["file_count"],
            "total_bytes": row["total_bytes"],
            "response_verified": bool(row["response_verified"]),
            "sandbox_claims": json.loads(row["sandbox_json"]),
            "isolation_verified": bool(row["isolation_verified"]),
            "error_type": row["error_type"],
            "created_at": row["created_at"],
        }
