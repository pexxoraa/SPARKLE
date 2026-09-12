from __future__ import annotations

import json
import os
import re
import signal
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sparkle.builders import WorkspaceManager
from sparkle.config import data_root
from sparkle.storage import SQLiteStore, utc_now


class DevelopmentVerifier(SQLiteStore):
    """Performs bounded static verification inside generated workspaces."""

    VALID_CHECKS = {"python_compile", "javascript_syntax", "json_parse"}
    MAX_CHECKS = 50
    MAX_FILE_BYTES = 500_000
    MAX_OUTPUT_CHARS = 8_000
    JAVASCRIPT_TIMEOUT_SECONDS = 15

    def __init__(
        self,
        root: Path | None = None,
        path: Path | None = None,
        *,
        node_binary: str | None = None,
    ):
        self.root = (root or data_root() / "applications").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        discovered_node = node_binary if node_binary is not None else shutil.which("node")
        self.node_binary = str(Path(discovered_node).resolve()) if discovered_node else None
        super().__init__(path or data_root() / "data_environment" / "verifications.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS verification_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    checks_json TEXT NOT NULL,
                    passed INTEGER NOT NULL,
                    failed INTEGER NOT NULL,
                    duration_ms REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def _project_root(self, project_name: str) -> Path:
        if not WorkspaceManager.NAME_PATTERN.fullmatch(project_name):
            raise ValueError("Project name must be a 2-64 character lowercase identifier")
        project = self.root / project_name
        if project.is_symlink():
            raise ValueError("Application workspace cannot be a symlink")
        resolved = project.resolve()
        if resolved.parent != self.root or not resolved.is_dir():
            raise ValueError(f"Application workspace does not exist: {project_name}")
        return resolved

    def _target(self, project: Path, value: str) -> tuple[Path, str]:
        relative = WorkspaceManager._validate_relative_path(value)
        candidate = project / Path(*relative.parts)
        current = candidate
        while current != project:
            if current.is_symlink():
                raise ValueError(f"Verification path contains a symlink: {value}")
            current = current.parent
        target = candidate.resolve()
        if project not in target.parents or not target.is_file():
            raise ValueError(f"Verification file is outside the project or missing: {value}")
        if target.stat().st_size > self.MAX_FILE_BYTES:
            raise ValueError(f"Verification file exceeds {self.MAX_FILE_BYTES} bytes: {value}")
        return target, relative.as_posix()

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        message = str(exc).strip() or type(exc).__name__
        return message[:DevelopmentVerifier.MAX_OUTPUT_CHARS]

    def _python_compile(self, target: Path, relative: str) -> tuple[bool, str]:
        if target.suffix.lower() != ".py":
            raise ValueError(f"python_compile requires a .py file: {relative}")
        try:
            source = target.read_text(encoding="utf-8")
            compile(source, relative, "exec", dont_inherit=True)
            return True, "Python source compiled without execution"
        except (SyntaxError, UnicodeDecodeError, ValueError, RecursionError) as exc:
            return False, self._safe_error(exc)

    def _json_parse(self, target: Path, relative: str) -> tuple[bool, str]:
        if target.suffix.lower() != ".json":
            raise ValueError(f"json_parse requires a .json file: {relative}")
        try:
            json.loads(target.read_text(encoding="utf-8"))
            return True, "JSON parsed successfully"
        except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
            return False, self._safe_error(exc)

    def _javascript_syntax(self, project: Path, relative: str) -> tuple[bool, str]:
        if Path(relative).suffix.lower() not in {".js", ".mjs", ".cjs"}:
            raise ValueError(f"javascript_syntax requires a .js, .mjs, or .cjs file: {relative}")
        if not self.node_binary:
            return False, "Node.js is unavailable in this runtime"
        environment = {
            "PATH": os.path.dirname(self.node_binary),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "NODE_OPTIONS": "--no-warnings",
        }
        try:
            completed = subprocess.run(
                [self.node_binary, "--check", "--", relative],
                cwd=project,
                env=environment,
                capture_output=True,
                text=True,
                timeout=self.JAVASCRIPT_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return False, (
                "JavaScript syntax check timed out after "
                f"{self.JAVASCRIPT_TIMEOUT_SECONDS} seconds"
            )
        except OSError as exc:
            return False, f"Node.js syntax check could not start: {type(exc).__name__}"
        output = (completed.stderr or completed.stdout or "").replace(str(project), "<workspace>")
        output = output.strip()[: self.MAX_OUTPUT_CHARS]
        if completed.returncode == 0:
            return True, "JavaScript syntax check passed"
        return False, output or f"Node.js syntax check exited {completed.returncode}"

    def verify(self, project_name: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(checks, list) or not 1 <= len(checks) <= self.MAX_CHECKS:
            raise ValueError(f"Verification requires 1-{self.MAX_CHECKS} checks")
        project = self._project_root(project_name)
        started = time.monotonic()
        results: list[dict[str, Any]] = []
        for check in checks:
            if not isinstance(check, dict):
                raise TypeError("Every verification check must be an object")
            unknown_fields = set(check) - {"type", "path"}
            if unknown_fields:
                raise ValueError(
                    f"Unsupported verification fields: {', '.join(sorted(unknown_fields))}"
                )
            check_type = check.get("type")
            raw_path = check.get("path")
            if check_type not in self.VALID_CHECKS:
                raise ValueError(f"Unsupported verification check: {check_type}")
            if not isinstance(raw_path, str):
                raise TypeError("Verification check path must be a string")
            target, relative = self._target(project, raw_path)
            if check_type == "python_compile":
                passed, output = self._python_compile(target, relative)
            elif check_type == "javascript_syntax":
                passed, output = self._javascript_syntax(project, relative)
            else:
                passed, output = self._json_parse(target, relative)
            results.append({
                "type": check_type,
                "path": relative,
                "status": "passed" if passed else "failed",
                "output": output,
            })

        passed_count = sum(result["status"] == "passed" for result in results)
        failed_count = len(results) - passed_count
        duration_ms = round((time.monotonic() - started) * 1000, 2)
        status = "passed" if failed_count == 0 else "failed"
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO verification_runs(
                    project_name, status, checks_json, passed, failed,
                    duration_ms, created_at
                ) VALUES(?,?,?,?,?,?,?)
            """, (
                project_name,
                status,
                json.dumps(results, separators=(",", ":")),
                passed_count,
                failed_count,
                duration_ms,
                now,
            ))
        return {
            "verification_id": int(cursor.lastrowid),
            "project_name": project_name,
            "status": status,
            "passed": passed_count,
            "failed": failed_count,
            "duration_ms": duration_ms,
            "checks": results,
            "created_at": now,
        }

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM verification_runs ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [self._public(row) for row in rows]

    @staticmethod
    def _public(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "verification_id": row["id"],
            "project_name": row["project_name"],
            "status": row["status"],
            "checks": json.loads(row["checks_json"]),
            "passed": row["passed"],
            "failed": row["failed"],
            "duration_ms": row["duration_ms"],
            "created_at": row["created_at"],
        }


class WorkspaceTestRunner(SQLiteStore):
    """Runs one fixed Python unittest command behind explicit opt-in controls."""

    MAX_FILES = 500
    MAX_TOTAL_BYTES = 5_000_000
    MAX_FILE_BYTES = 500_000
    MAX_OUTPUT_CHARS = 12_000
    _SECRET_PATTERN = re.compile(
        r"(?i)\b(authorization|api[_-]?key|token|secret)(\s*[:=]\s*|\s+)([^\s,;]+)"
    )
    _BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
    _ALLOWED_PARENT_ENVIRONMENT = frozenset({
        "PATH", "LANG", "LC_ALL", "LC_CTYPE", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV",
        "SPARKLE_DATA_DIR", "SPARKLE_WORKSPACE_TESTS_ENABLED",
        "SPARKLE_WORKSPACE_TEST_TIMEOUT_SECONDS",
    })

    def __init__(
        self,
        root: Path | None = None,
        path: Path | None = None,
        *,
        enabled: bool = False,
        timeout_seconds: int = 10,
        python_binary: str | None = None,
        parent_environment: Mapping[str, str] | None = None,
    ):
        if not 1 <= timeout_seconds <= 60:
            raise ValueError("Workspace test timeout must be from 1 to 60 seconds")
        self.root = (root or data_root() / "applications").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.python_binary = str(Path(python_binary or sys.executable).resolve())
        self.runner_script = Path(__file__).with_name("sandbox_runner.py").resolve()
        self.parent_environment = (
            os.environ if parent_environment is None else parent_environment
        )
        super().__init__(path or data_root() / "data_environment" / "test_runs.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS test_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    framework TEXT NOT NULL,
                    returncode INTEGER,
                    timed_out INTEGER NOT NULL,
                    output TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def status(self) -> dict[str, Any]:
        unexpected_count = self._unexpected_environment_count()
        return {
            "enabled": self.enabled,
            "framework": "python_unittest",
            "timeout_seconds": self.timeout_seconds,
            "resource_limits": os.name == "posix",
            "network_isolation": False,
            "filesystem_isolation": False,
            "sanitized_parent": unexpected_count == 0,
            "unexpected_parent_variables": unexpected_count,
            "arbitrary_commands": False,
        }

    def _unexpected_environment_count(self) -> int:
        return sum(
            1 for name, value in self.parent_environment.items()
            if value and name not in self._ALLOWED_PARENT_ENVIRONMENT
        )

    def _project_root(self, project_name: str) -> Path:
        if not WorkspaceManager.NAME_PATTERN.fullmatch(project_name):
            raise ValueError("Project name must be a 2-64 character lowercase identifier")
        project = self.root / project_name
        if project.is_symlink():
            raise ValueError("Application workspace cannot be a symlink")
        resolved = project.resolve()
        if resolved.parent != self.root or not resolved.is_dir():
            raise ValueError(f"Application workspace does not exist: {project_name}")
        return resolved

    def _inspect_workspace(self, project: Path) -> int:
        file_count = 0
        total_bytes = 0
        test_files = 0
        for current, directories, files in os.walk(project, followlinks=False):
            current_path = Path(current)
            for name in [*directories, *files]:
                candidate = current_path / name
                if candidate.is_symlink():
                    raise ValueError("Workspace tests reject every symlink")
            for name in files:
                candidate = current_path / name
                if not candidate.is_file():
                    raise ValueError("Workspace tests require regular files")
                size = candidate.stat().st_size
                if size > self.MAX_FILE_BYTES:
                    raise ValueError(
                        f"Workspace test file exceeds {self.MAX_FILE_BYTES} bytes"
                    )
                file_count += 1
                total_bytes += size
                if file_count > self.MAX_FILES or total_bytes > self.MAX_TOTAL_BYTES:
                    raise ValueError("Workspace exceeds test execution bounds")
                if (
                    project / "tests" in candidate.parents
                    and candidate.name.startswith("test")
                    and candidate.suffix == ".py"
                ):
                    test_files += 1
        if not (project / "tests").is_dir() or test_files == 0:
            raise ValueError("Workspace requires at least one tests/test*.py file")
        return test_files

    def _safe_output(self, output: str, project: Path) -> str:
        sanitized = output.replace(str(project), "<workspace>")
        sanitized = self._BEARER_PATTERN.sub("Bearer [REDACTED]", sanitized)
        sanitized = self._SECRET_PATTERN.sub(r"\1\2[REDACTED]", sanitized)
        return sanitized.strip()[: self.MAX_OUTPUT_CHARS]

    def run(self, project_name: str) -> dict[str, Any]:
        if not self.enabled:
            raise ValueError(
                "Workspace test execution is disabled; set "
                "SPARKLE_WORKSPACE_TESTS_ENABLED=true only in a dedicated disposable worker"
            )
        if os.name != "posix":
            raise ValueError("Workspace test execution requires POSIX resource limits")
        if self._unexpected_environment_count():
            raise ValueError(
                "Workspace tests require a dedicated worker process with a "
                "strictly allowlisted parent environment"
            )
        project = self._project_root(project_name)
        test_files = self._inspect_workspace(project)
        environment = {
            "PATH": str(Path(self.python_binary).parent),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "SPARKLE_TEST_SANDBOX": "1",
        }
        command = [
            self.python_binary,
            "-I",
            str(self.runner_script),
            str(project),
            str(self.timeout_seconds),
        ]
        started = time.monotonic()
        timed_out = False
        with tempfile.TemporaryFile(
            mode="w+", encoding="utf-8", errors="replace",
        ) as output_file:
            process = subprocess.Popen(
                command,
                cwd=project,
                env=environment,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                process.wait(timeout=self.timeout_seconds + 1)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            output_file.seek(0)
            output = output_file.read(self.MAX_OUTPUT_CHARS + 1)
        duration_ms = round((time.monotonic() - started) * 1000, 2)
        safe_output = self._safe_output(output or "", project)
        status = "passed" if process.returncode == 0 and not timed_out else "failed"
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO test_runs(
                    project_name, status, framework, returncode, timed_out,
                    output, duration_ms, created_at
                ) VALUES(?,?,?,?,?,?,?,?)
            """, (
                project_name,
                status,
                "python_unittest",
                process.returncode,
                int(timed_out),
                safe_output,
                duration_ms,
                now,
            ))
        return {
            "test_run_id": int(cursor.lastrowid),
            "project_name": project_name,
            "status": status,
            "framework": "python_unittest",
            "test_files": test_files,
            "returncode": process.returncode,
            "timed_out": timed_out,
            "output": safe_output,
            "duration_ms": duration_ms,
            "created_at": now,
        }

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM test_runs ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [self._public(row) for row in rows]

    @staticmethod
    def _public(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "test_run_id": row["id"],
            "project_name": row["project_name"],
            "status": row["status"],
            "framework": row["framework"],
            "returncode": row["returncode"],
            "timed_out": bool(row["timed_out"]),
            "output": row["output"],
            "duration_ms": row["duration_ms"],
            "created_at": row["created_at"],
        }