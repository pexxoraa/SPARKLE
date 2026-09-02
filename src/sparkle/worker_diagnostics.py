from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from typing import Any

from sparkle.worker_executor import BubblewrapExecutor


AVAILABLE = "AVAILABLE"
UNAVAILABLE = "UNAVAILABLE"
NOT_VERIFIED = "NOT_VERIFIED"


class WorkerIsolationDiagnostic:
    """Report host primitives without requiring worker credentials."""

    SCHEMA = "SPARKLE-WORKER-HOST-DIAGNOSTIC/1"

    def __init__(
        self,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        executable_finder: Callable[[str], str | None] | None = None,
        bubblewrap_factory: Callable[[], BubblewrapExecutor] | None = None,
    ):
        self.runner = runner or subprocess.run
        self.executable_finder = executable_finder or shutil.which
        self.bubblewrap_factory = bubblewrap_factory or BubblewrapExecutor

    @staticmethod
    def _bounded(value: object) -> str:
        text = str(value or "").strip().replace("\x00", "")
        return text[:512]

    def _command_probe(
        self,
        *,
        label: str,
        command: list[str] | None,
    ) -> dict[str, Any]:
        if not command:
            return {
                "state": UNAVAILABLE,
                "command": label,
                "exit_code": None,
                "stdout": "",
                "stderr": "required executable is unavailable",
            }
        try:
            completed = self.runner(
                command,
                env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return {
                "state": NOT_VERIFIED,
                "command": label,
                "exit_code": None,
                "stdout": "",
                "stderr": type(exc).__name__,
            }
        return {
            "state": AVAILABLE if completed.returncode == 0 else UNAVAILABLE,
            "command": label,
            "exit_code": int(completed.returncode),
            "stdout": self._bounded(completed.stdout),
            "stderr": self._bounded(completed.stderr),
        }

    def _namespace_probe(self, namespace: str) -> dict[str, Any]:
        unshare = self.executable_finder("unshare")
        true_binary = self.executable_finder("true")
        flags = ["--user", "--map-root-user"]
        if namespace != "user":
            flags.append(f"--{namespace}")
        command = [unshare, *flags, "--", true_binary] if unshare and true_binary else None
        return self._command_probe(
            label=f"unshare {' '.join(flags)} -- true",
            command=command,
        )

    def _no_new_privileges_probe(self) -> dict[str, Any]:
        code = (
            "import ctypes,sys;libc=ctypes.CDLL(None,use_errno=True);"
            "r=libc.prctl(38,1,0,0,0);g=libc.prctl(39,0,0,0,0);"
            "print('enabled' if r==0 and g==1 else 'unavailable');"
            "sys.exit(0 if r==0 and g==1 else 1)"
        )
        return self._command_probe(
            label="prctl(PR_SET_NO_NEW_PRIVS)",
            command=[sys.executable, "-I", "-c", code] if os.name == "posix" else None,
        )

    def run(self) -> dict[str, Any]:
        namespace_results = {
            name: self._namespace_probe(name)
            for name in ("user", "mount", "net")
        }
        no_new_privileges = self._no_new_privileges_probe()
        try:
            isolation = self.bubblewrap_factory().status()
        except Exception as exc:  # diagnostic boundary must remain content-free
            isolation = {
                "available": False,
                "filesystem_isolation": False,
                "network_isolation": False,
                "failure_type": type(exc).__name__,
                "canaries": {},
            }
        bwrap_path = self.executable_finder("bwrap")
        bwrap_available = bool(isolation.get("available"))
        filesystem_available = bool(isolation.get("filesystem_isolation"))
        network_available = bool(isolation.get("network_isolation"))
        checks = {
            "user_namespace": namespace_results["user"],
            "mount_namespace": namespace_results["mount"],
            "network_namespace": namespace_results["net"],
            "no_new_privileges": no_new_privileges,
            "bubblewrap": {
                "state": AVAILABLE if bwrap_available else UNAVAILABLE,
                "executable_present": bool(bwrap_path),
                "preflight_passed": bwrap_available,
                "failure_type": isolation.get("failure_type"),
            },
            "filesystem_isolation": {
                "state": AVAILABLE if filesystem_available else UNAVAILABLE,
                "verified_by": "bubblewrap_executable_preflight",
            },
            "network_isolation": {
                "state": AVAILABLE if network_available else UNAVAILABLE,
                "verified_by": "bubblewrap_executable_preflight",
            },
        }
        return {
            "schema": self.SCHEMA,
            "platform": sys.platform,
            "architecture": os.uname().machine if hasattr(os, "uname") else "unknown",
            "checks": checks,
            "canaries": dict(isolation.get("canaries", {})),
            "software_platform_ready": True,
            "isolation_preflight_passed": bwrap_available,
            "level_3_status": "BLOCKED",
            "level_3_verified": False,
            "deployment_started": False,
        }
