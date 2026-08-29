from __future__ import annotations

import argparse
import json
import os
import signal
import stat
import sys
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - the supervised service targets POSIX
    fcntl = None

from sparkle.automation import AutomationRunner, AutomationStore
from sparkle.config import data_root


class AutomationServiceError(RuntimeError):
    """A safe supervised-automation lifecycle failure."""


class AutomationServiceLock:
    """A persistent no-follow flock that prevents concurrent local schedulers."""

    def __init__(self, path: Path | None = None):
        self.path = path or data_root() / "data_environment" / "automation-service.lock"
        self._descriptor: int | None = None

    def acquire(self) -> None:
        if self._descriptor is not None:
            raise AutomationServiceError("Automation service lock is already held")
        if fcntl is None:
            raise AutomationServiceError(
                "The supervised automation service requires POSIX file locking"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(self.path, flags, 0o600)
        except OSError as exc:
            raise AutomationServiceError("Automation service lock is unavailable") from exc
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise AutomationServiceError("Automation service lock must be a regular file")
            os.fchmod(descriptor, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise AutomationServiceError(
                    "Another automation service instance already holds the lock"
                ) from exc
        except Exception:
            os.close(descriptor)
            raise
        self._descriptor = descriptor

    def release(self) -> None:
        if self._descriptor is None:
            return
        descriptor, self._descriptor = self._descriptor, None
        try:
            if fcntl is not None:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)

    @contextmanager
    def held(self) -> Iterator[None]:
        self.acquire()
        try:
            yield
        finally:
            self.release()


class AutomationService:
    """Runs the existing automation engine with locking, recovery, and health state."""

    def __init__(
        self,
        store: AutomationStore,
        runner: AutomationRunner,
        *,
        interval_seconds: float = 60,
        lease_seconds: int = 3_600,
        lock: AutomationServiceLock | None = None,
        instance_id: str | None = None,
        clock: Any | None = None,
        stop_event: threading.Event | None = None,
    ):
        if isinstance(interval_seconds, bool) or not isinstance(
            interval_seconds, (int, float)
        ) or not 1 <= float(interval_seconds) <= 3_600:
            raise ValueError("Automation service interval must be from 1 to 3600 seconds")
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or not (
            30 <= lease_seconds <= 86_400
        ):
            raise ValueError("Automation service lease must be from 30 to 86400 seconds")
        identity = instance_id or uuid.uuid4().hex
        if (
            not isinstance(identity, str)
            or not 16 <= len(identity) <= 128
            or not identity.isalnum()
        ):
            raise ValueError("Automation service instance ID is invalid")
        self.store = store
        self.runner = runner
        self.interval_seconds = float(interval_seconds)
        self.lease_seconds = lease_seconds
        self.lock = lock or AutomationServiceLock()
        self.instance_id = identity
        self.clock = clock or (lambda: datetime.now(UTC))
        self.stop_event = stop_event or threading.Event()
        self._started = False

    def _now(self) -> datetime:
        value = self.clock()
        if not isinstance(value, datetime):
            raise AutomationServiceError("Automation service clock returned an invalid value")
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value

    def request_stop(self) -> None:
        self.stop_event.set()
        if self._started:
            try:
                self.store.service_heartbeat(
                    self.instance_id, state="draining", now=self._now().isoformat(),
                )
            except Exception:
                pass

    def run(self, *, max_cycles: int | None = None) -> dict[str, Any]:
        if max_cycles is not None and (
            isinstance(max_cycles, bool) or not isinstance(max_cycles, int) or max_cycles < 1
        ):
            raise ValueError("Automation service max_cycles must be a positive integer")
        completed_cycles = 0
        total_runs = 0
        recovered = 0
        last_error_type: str | None = None
        terminal_state = "stopped"
        with self.lock.held():
            started = self._now()
            recovered = self.store.recover_stale_claims(started.isoformat())
            self.store.service_start(
                self.instance_id,
                interval_seconds=self.interval_seconds,
                lease_seconds=self.lease_seconds,
                recovered_claims=recovered,
                now=started.isoformat(),
            )
            self._started = True
            try:
                while not self.stop_event.is_set():
                    cycle_time = self._now()
                    cycle_recovered = self.store.recover_stale_claims(
                        cycle_time.isoformat()
                    )
                    recovered += cycle_recovered
                    self.store.service_heartbeat(
                        self.instance_id,
                        recovered_claims=cycle_recovered,
                        now=cycle_time.isoformat(),
                    )
                    try:
                        runs = self.runner.run_due(
                            cycle_time,
                            claim_token=self.instance_id,
                            lease_seconds=self.lease_seconds,
                        )
                    except Exception as exc:
                        last_error_type = type(exc).__name__[:128]
                        self.store.service_heartbeat(
                            self.instance_id,
                            state="degraded",
                            cycle_completed=True,
                            last_error_type=last_error_type,
                            now=self._now().isoformat(),
                        )
                    else:
                        total_runs += len(runs)
                        last_error_type = None
                        self.store.service_heartbeat(
                            self.instance_id,
                            state="running",
                            cycle_completed=True,
                            now=self._now().isoformat(),
                        )
                    completed_cycles += 1
                    if max_cycles is not None and completed_cycles >= max_cycles:
                        break
                    self.stop_event.wait(self.interval_seconds)
            except BaseException as exc:
                terminal_state = "error"
                last_error_type = type(exc).__name__[:128]
                raise
            finally:
                self._started = False
                self.store.service_stop(
                    self.instance_id,
                    state=terminal_state,
                    last_error_type=last_error_type,
                    now=self._now().isoformat(),
                )
        return {
            "state": terminal_state,
            "cycles": completed_cycles,
            "runs": total_runs,
            "recovered_claims": recovered,
            "last_error_type": last_error_type,
            "credentials_exposed": False,
        }


def run_with_signals(
    service: AutomationService, *, max_cycles: int | None = None,
) -> dict[str, Any]:
    previous: dict[int, Any] = {}

    def stop_handler(_signum: int, _frame: Any) -> None:
        # Signal handlers perform no I/O; normal service control flow persists
        # the terminal state after the bounded active operation returns.
        service.stop_event.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, stop_handler)
    try:
        return service.run(max_cycles=max_cycles)
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sparkle-automations",
        description="Supervised SPARKLE automation service",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run one supervised cycle")
    mode.add_argument("--status", action="store_true", help="Read persisted service status")
    mode.add_argument(
        "--healthcheck", action="store_true", help="Require a fresh healthy service heartbeat",
    )
    mode.add_argument("--check", action="store_true", help="Check state and lock readiness")
    parser.add_argument(
        "--interval",
        type=float,
        default=float(os.environ.get("SPARKLE_AUTOMATION_INTERVAL_SECONDS", "60")),
    )
    parser.add_argument(
        "--lease-seconds",
        type=int,
        default=int(os.environ.get("SPARKLE_AUTOMATION_LEASE_SECONDS", "3600")),
    )
    return parser


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    store = AutomationStore()
    if args.status or args.healthcheck:
        status = store.service_status()
        _print({"ok": not args.healthcheck or status["healthy"], "service": status})
        return 0 if not args.healthcheck or status["healthy"] else 2
    if args.check:
        status = store.service_status()
        lock = AutomationServiceLock()
        lock_available = False
        try:
            lock.acquire()
            lock_available = True
        except AutomationServiceError:
            lock_available = False
        finally:
            lock.release()
        ready = bool(status["healthy"] or lock_available)
        _print({
            "ok": ready,
            "ready": ready,
            "lock_available": lock_available,
            "service": status,
            "credentials_exposed": False,
        })
        return 0 if ready else 2

    from sparkle.system import SparkleSystem

    system = SparkleSystem()
    service = AutomationService(
        system.automations,
        system.automation_runner,
        interval_seconds=args.interval,
        lease_seconds=args.lease_seconds,
    )
    result = run_with_signals(service, max_cycles=1 if args.once else None)
    ok = result["state"] == "stopped" and result["last_error_type"] is None
    _print({"ok": ok, "service_run": result})
    return 0 if ok else 1


def entrypoint(argv: list[str] | None = None) -> int:
    try:
        return main(argv)
    except (AutomationServiceError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(entrypoint())
