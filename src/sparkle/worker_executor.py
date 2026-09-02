from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from sparkle.external_worker import ExternalWorkerClient


class WorkerExecutionError(RuntimeError):
    """A safe fixed-executor failure."""


def default_worker_python() -> str:
    """Prefer the distribution Python already covered by read-only system mounts."""
    system_python = Path("/usr/bin/python3")
    return str(system_python.resolve()) if system_python.is_file() else sys.executable


@dataclass(frozen=True, slots=True)
class WorkerSourceFile:
    path: str
    content: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class WorkerJob:
    job_id: str
    project_name: str
    timeout_seconds: int
    max_output_chars: int
    files: tuple[WorkerSourceFile, ...]
    request_hash: str
    execution_context: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ExecutorResult:
    status: str
    returncode: int
    timed_out: bool
    output: str
    duration_ms: float
    sandbox: dict[str, Any]
    output_limited: bool = False


class FixedUnittestExecutor:
    """Materializes a validated bundle and runs only SPARKLE's unittest child."""

    MODE = "process"
    CANARY_NAMES = (
        "host_filesystem_read", "host_filesystem_write", "workspace_escape",
        "secret_environment", "prohibited_network", "host_process_access",
        "artifact_modification",
    )

    def __init__(
        self,
        *,
        python_binary: str | None = None,
        runner_script: Path | None = None,
        allow_unsafe_process: bool = False,
    ):
        self.python_binary = str(Path(python_binary or default_worker_python()).resolve())
        self.runner_script = (
            runner_script or Path(__file__).with_name("sandbox_runner.py")
        ).resolve()
        self.allow_unsafe_process = allow_unsafe_process

    def status(self) -> dict[str, Any]:
        available = bool(
            self.allow_unsafe_process
            and os.name == "posix"
            and Path(self.python_binary).is_file()
            and self.runner_script.is_file()
        )
        return {
            "mode": self.MODE,
            "available": available,
            "preflight_passed": available,
            "filesystem_isolation": False,
            "network_isolation": False,
            "ephemeral_workspace": True,
            "resource_limits": os.name == "posix",
            "unsafe_process_mode": True,
            "hostile_canaries_passed": False,
            "isolation_profile": None,
            "canaries": {name: False for name in self.CANARY_NAMES},
            "failure_type": None if available else "UnsafeProcessExecutorDisabled",
        }

    @staticmethod
    def _materialize(project: Path, files: tuple[WorkerSourceFile, ...]) -> None:
        project.mkdir(mode=0o700)
        for item in files:
            relative = PurePosixPath(item.path)
            target = project.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open("xb") as handle:
                handle.write(item.content)
            target.chmod(0o600)

    def _command(self, project: Path, timeout_seconds: int) -> list[str]:
        return [
            self.python_binary,
            "-I",
            str(self.runner_script),
            str(project),
            str(timeout_seconds),
        ]

    def _sandbox_claims(self, worker_id: str) -> dict[str, Any]:
        return {
            "worker_id": worker_id,
            "filesystem_isolation": False,
            "network_isolation": False,
            "ephemeral": True,
            "resource_limits": os.name == "posix",
        }

    def execute(self, job: WorkerJob, *, worker_id: str) -> ExecutorResult:
        executor_status = self.status()
        if not executor_status["available"]:
            raise WorkerExecutionError("Worker executor isolation is unavailable")
        started = time.monotonic()
        timed_out = False
        with tempfile.TemporaryDirectory(prefix="sparkle-worker-") as directory:
            project = Path(directory) / "workspace"
            self._materialize(project, job.files)
            environment = {
                "PATH": str(Path(self.python_binary).parent),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PYTHONHASHSEED": "0",
                "PYTHONDONTWRITEBYTECODE": "1",
                "SPARKLE_TEST_SANDBOX": "1",
            }
            with tempfile.TemporaryFile(
                mode="w+", encoding="utf-8", errors="replace",
            ) as output_file:
                try:
                    process = subprocess.Popen(
                        self._command(project, job.timeout_seconds),
                        cwd=project,
                        env=environment,
                        stdout=output_file,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                except OSError as exc:
                    raise WorkerExecutionError(
                        f"Fixed worker child could not start ({type(exc).__name__})"
                    ) from exc
                try:
                    process.wait(timeout=job.timeout_seconds + 2)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                output_file.seek(0)
                output = output_file.read(job.max_output_chars + 1)
        duration_ms = round((time.monotonic() - started) * 1000, 2)
        output_limited = len(output or "") > job.max_output_chars
        safe_output = ExternalWorkerClient._safe_output(output or "")[
            : job.max_output_chars
        ]
        status = "passed" if process.returncode == 0 and not timed_out else "failed"
        return ExecutorResult(
            status=status,
            returncode=max(-255, min(int(process.returncode), 255)),
            timed_out=timed_out,
            output=safe_output,
            duration_ms=duration_ms,
            sandbox=self._sandbox_claims(worker_id),
            output_limited=output_limited,
        )


class BubblewrapExecutor(FixedUnittestExecutor):
    """Runs the fixed child in a no-network, minimal-filesystem namespace."""

    MODE = "bubblewrap"
    ISOLATION_PROFILE = "SPARKLE-WORKER-BUBBLEWRAP/1"
    _SAFE_BINARY = re.compile(r"^/[A-Za-z0-9_./+-]+$")

    def __init__(
        self,
        *,
        bubblewrap_binary: str | None = None,
        python_binary: str | None = None,
        runner_script: Path | None = None,
        preflight_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ):
        super().__init__(
            python_binary=python_binary,
            runner_script=runner_script,
            allow_unsafe_process=False,
        )
        discovered = bubblewrap_binary or shutil.which("bwrap") or ""
        self.bubblewrap_binary = (
            str(Path(discovered).resolve()) if discovered else ""
        )
        self.preflight_runner = preflight_runner or subprocess.run
        self._preflight_result: bool | None = None
        self._failure_type: str | None = None
        self._canary_results = {name: False for name in self.CANARY_NAMES}

    def _runtime_mounts(self) -> list[Path]:
        roots = [
            Path("/usr"), Path("/usr/local"), Path("/bin"),
            Path("/lib"), Path("/lib64"),
        ]
        return [path for path in roots if path.exists()]

    def _base_command(self, project: Path) -> list[str]:
        if not self.bubblewrap_binary or not self._SAFE_BINARY.fullmatch(
            self.bubblewrap_binary
        ):
            raise WorkerExecutionError("Bubblewrap executable is unavailable")
        command = [
            self.bubblewrap_binary,
            "--die-with-parent",
            "--new-session",
            "--unshare-all",
            "--clearenv",
            "--proc", "/proc",
            "--dev", "/dev",
            "--tmpfs", "/tmp",
            "--dir", "/workspace",
            "--ro-bind", str(project), "/workspace",
            "--dir", "/opt",
            "--dir", "/opt/sparkle",
            "--ro-bind", str(self.runner_script), "/opt/sparkle/sandbox_runner.py",
        ]
        for root in self._runtime_mounts():
            command.extend(["--ro-bind", str(root), str(root)])
        ld_cache = Path("/etc/ld.so.cache")
        if ld_cache.is_file():
            command.extend([
                "--dir", "/etc",
                "--ro-bind", str(ld_cache), str(ld_cache),
            ])
        command.extend([
            "--chdir", "/workspace",
            "--setenv", "PATH", str(Path(self.python_binary).parent) + ":/usr/bin:/bin",
            "--setenv", "LANG", "C.UTF-8",
            "--setenv", "LC_ALL", "C.UTF-8",
            "--setenv", "PYTHONHASHSEED", "0",
            "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
            "--setenv", "SPARKLE_TEST_SANDBOX", "1",
            "--",
        ])
        return command

    def _command(self, project: Path, timeout_seconds: int) -> list[str]:
        return self._base_command(project) + [
            self.python_binary,
            "-I",
            "/opt/sparkle/sandbox_runner.py",
            "/workspace",
            str(timeout_seconds),
        ]

    def _run_preflight(self) -> bool:
        if (
            os.name != "posix"
            or not self.bubblewrap_binary
            or not Path(self.bubblewrap_binary).is_file()
            or not Path(self.python_binary).is_file()
            or not self.runner_script.is_file()
            or not self.python_binary.startswith(("/usr/", "/bin/"))
        ):
            self._failure_type = "ExecutorDependencyUnavailable"
            return False
        probe = """
import json, os, socket, sys
host_canary, other_workspace, allowed_raw, host_pid = sys.argv[1:]
allowed = set(allowed_raw.split(','))
results = {}
results['host_filesystem_read'] = not os.path.exists(host_canary) and not os.path.exists('/proc/1/root' + host_canary)
blocked_writes = True
for path in (host_canary, '/escape-canary'):
    try:
        with open(path, 'wb') as handle: handle.write(b'blocked')
    except OSError:
        pass
    else:
        blocked_writes = False
results['host_filesystem_write'] = blocked_writes
results['workspace_escape'] = not os.path.exists(other_workspace)
results['secret_environment'] = set(os.environ) <= allowed and 'SPARKLE_WORKER_SIGNING_KEY' not in os.environ
network_blocked = True
for address in (('1.1.1.1', 53), ('127.0.0.1', 1)):
    sock = socket.socket(); sock.settimeout(0.2)
    try:
        sock.connect(address)
    except OSError:
        pass
    else:
        network_blocked = False
    finally:
        sock.close()
results['prohibited_network'] = network_blocked
try:
    os.kill(int(host_pid), 0)
except OSError:
    results['host_process_access'] = True
else:
    results['host_process_access'] = False
try:
    with open('/workspace/.sparkle-artifact-canary', 'wb') as handle: handle.write(b'modified')
except OSError:
    results['artifact_modification'] = True
else:
    results['artifact_modification'] = False
print(json.dumps(results, sort_keys=True, separators=(',', ':')))
raise SystemExit(0 if all(results.values()) else 4)
"""
        with tempfile.TemporaryDirectory(prefix="sparkle-preflight-") as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir(mode=0o700)
            artifact_canary = workspace / ".sparkle-artifact-canary"
            artifact_canary.write_bytes(b"immutable")
            artifact_canary.chmod(0o400)
            canary = root / "host-canary"
            canary.write_text("must-not-be-visible", encoding="utf-8")
            other_workspace = root / "other-workspace"
            other_workspace.mkdir(mode=0o700)
            (other_workspace / "foreign-canary").write_text(
                "must-not-be-visible", encoding="utf-8",
            )
            allowed = ",".join({
                "PATH", "LANG", "LC_ALL", "PYTHONHASHSEED",
                "PYTHONDONTWRITEBYTECODE", "SPARKLE_TEST_SANDBOX",
            })
            command = self._base_command(workspace) + [
                self.python_binary, "-I", "-c", probe, str(canary),
                str(other_workspace), allowed, str(os.getpid()),
            ]
            try:
                completed = self.preflight_runner(
                    command,
                    env={"PATH": str(Path(self.bubblewrap_binary).parent)},
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                self._failure_type = type(exc).__name__
                return False
            artifact_unchanged = artifact_canary.read_bytes() == b"immutable"
        try:
            reported = json.loads(completed.stdout.strip())
        except (AttributeError, json.JSONDecodeError):
            reported = {}
        if (
            completed.returncode != 0
            or set(reported) != set(self.CANARY_NAMES)
            or not all(reported.get(name) is True for name in self.CANARY_NAMES)
            or not artifact_unchanged
        ):
            self._failure_type = "IsolationPreflightFailed"
            return False
        self._canary_results = {name: True for name in self.CANARY_NAMES}
        self._failure_type = None
        return True

    def status(self) -> dict[str, Any]:
        if self._preflight_result is None:
            self._preflight_result = self._run_preflight()
        available = bool(self._preflight_result)
        return {
            "mode": self.MODE,
            "available": available,
            "preflight_passed": available,
            "filesystem_isolation": available,
            "network_isolation": available,
            "ephemeral_workspace": True,
            "resource_limits": os.name == "posix",
            "unsafe_process_mode": False,
            "failure_type": self._failure_type,
            "hostile_canaries_passed": available,
            "isolation_profile": self.ISOLATION_PROFILE,
            "canaries": dict(self._canary_results),
        }

    def _sandbox_claims(self, worker_id: str) -> dict[str, Any]:
        available = bool(self.status()["available"])
        return {
            "worker_id": worker_id,
            "filesystem_isolation": available,
            "network_isolation": available,
            "ephemeral": True,
            "resource_limits": os.name == "posix",
        }
