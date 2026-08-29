from __future__ import annotations

import contextlib
import io
import json
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sparkle.automation import AutomationLeaseLostError, AutomationStore
from sparkle.automation_service import (
    AutomationService,
    AutomationServiceError,
    AutomationServiceLock,
    entrypoint,
)
from sparkle.config import AppConfig
from sparkle.providers.mock import DeterministicAdapter
from sparkle.registry import ModelRegistry
from sparkle.system import SparkleSystem


def test_config() -> AppConfig:
    return AppConfig("127.0.0.1", 0, 4, 5, 5, False, False)


class ImmediateEvent:
    def __init__(self):
        self.value = False

    def is_set(self):
        return self.value

    def set(self):
        self.value = True

    def wait(self, _timeout):
        return self.value


class FailingRunner:
    def run_due(self, *_args, **_kwargs):
        raise RuntimeError("bounded-cycle-failure")


class AutomationServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env_patch = patch.dict(
            os.environ, {"SPARKLE_DATA_DIR": self.temp.name}, clear=False,
        )
        self.env_patch.start()
        registry = ModelRegistry()
        registry.inject(registry.active_id, DeterministicAdapter())
        self.system = SparkleSystem(config=test_config(), model_registry=registry)
        self.now = datetime.now(UTC)

    def tearDown(self):
        self.env_patch.stop()
        self.temp.cleanup()

    def create_due(self, name: str = "Service once") -> int:
        return self.system.automations.create(
            name,
            "once",
            {"type": "agent", "prompt": "Review today", "agent": "personal"},
            next_run_at=(self.now - timedelta(minutes=1)).isoformat(),
        )

    def service(self, **overrides):
        options = {
            "interval_seconds": 1,
            "lease_seconds": 60,
            "lock": AutomationServiceLock(self.root / "service.lock"),
            "instance_id": "A" * 32,
            "clock": lambda: self.now,
            "stop_event": ImmediateEvent(),
        }
        options.update(overrides)
        return AutomationService(
            self.system.automations, self.system.automation_runner, **options,
        )

    def test_stale_claim_recovery_fences_old_runner(self):
        self.create_due()
        old = self.system.automations.claim_due(
            self.now.isoformat(), claim_token="A" * 32, lease_seconds=30,
        )[0]
        recovered_at = self.now + timedelta(seconds=31)
        self.assertEqual(
            self.system.automations.recover_stale_claims(recovered_at.isoformat()), 1,
        )
        new = self.system.automations.claim_due(
            recovered_at.isoformat(), claim_token="B" * 32, lease_seconds=30,
        )[0]
        with self.assertRaisesRegex(AutomationLeaseLostError, "expired|recovered"):
            self.system.automations.finish(
                old,
                status="success",
                attempts=1,
                started_at=self.now.isoformat(),
                result_summary="old",
                now=recovered_at,
            )
        result = self.system.automations.finish(
            new,
            status="success",
            attempts=1,
            started_at=recovered_at.isoformat(),
            result_summary="new",
            now=recovered_at,
        )
        self.assertEqual(result["status"], "success")
        runs = self.system.automations.list_runs()
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[1]["status"], "recovered")
        self.assertEqual(runs[1]["error_type"], "AutomationLeaseExpired")

    def test_service_executes_real_cycle_traces_and_stops_cleanly(self):
        self.create_due()
        service = self.service()
        result = service.run(max_cycles=1)
        self.assertEqual(result["state"], "stopped")
        self.assertEqual(result["runs"], 1)
        self.assertFalse(result["credentials_exposed"])
        status = self.system.automations.service_status(self.now)
        self.assertEqual(status["state"], "stopped")
        self.assertEqual(status["cycles"], 1)
        self.assertEqual(len(self.system.automations.list_runs()), 1)
        self.assertEqual(self.system.traces.recent()[0]["input_source"], "automation")
        self.assertEqual(stat.S_IMODE((self.root / "service.lock").stat().st_mode), 0o600)

    def test_second_instance_fails_closed_without_state_takeover(self):
        first_lock = AutomationServiceLock(self.root / "service.lock")
        first_lock.acquire()
        try:
            with self.assertRaisesRegex(AutomationServiceError, "already holds"):
                self.service(
                    lock=AutomationServiceLock(self.root / "service.lock"),
                    instance_id="B" * 32,
                ).run(max_cycles=1)
        finally:
            first_lock.release()
        self.assertEqual(
            self.system.automations.service_status(self.now)["state"],
            "never_started",
        )

    def test_cycle_failure_is_bounded_and_persisted_without_traceback(self):
        service = AutomationService(
            self.system.automations,
            FailingRunner(),
            interval_seconds=1,
            lease_seconds=60,
            lock=AutomationServiceLock(self.root / "service.lock"),
            instance_id="C" * 32,
            clock=lambda: self.now,
            stop_event=ImmediateEvent(),
        )
        result = service.run(max_cycles=1)
        self.assertEqual(result["state"], "stopped")
        self.assertEqual(result["last_error_type"], "RuntimeError")
        status = self.system.automations.service_status(self.now)
        self.assertEqual(status["last_error_type"], "RuntimeError")
        self.assertEqual(status["cycles"], 1)

    def test_pre_requested_stop_runs_no_cycle_and_status_becomes_stopped(self):
        service = self.service(stop_event=threading.Event())
        service.request_stop()
        result = service.run()
        self.assertEqual(result["cycles"], 0)
        self.assertEqual(
            self.system.automations.service_status(self.now)["state"], "stopped",
        )

    def test_service_status_detects_stale_heartbeat(self):
        self.system.automations.service_start(
            "D" * 32,
            interval_seconds=1,
            lease_seconds=30,
            recovered_claims=0,
            now=self.now.isoformat(),
        )
        status = self.system.automations.service_status(
            self.now + timedelta(seconds=31),
        )
        self.assertEqual(status["state"], "stale")
        self.assertFalse(status["healthy"])
        self.assertFalse(status["active"])

    def test_legacy_schema_migrates_claim_columns(self):
        path = self.root / "legacy.sqlite3"
        with sqlite3.connect(path) as connection:
            connection.execute("""
                CREATE TABLE automations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL, schedule TEXT, condition_json TEXT,
                    action_json TEXT NOT NULL, next_run_at TEXT, enabled INTEGER NOT NULL,
                    last_status TEXT, last_run_at TEXT, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
        store = AutomationStore(path)
        with store.connect() as connection:
            columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(automations)"
                )
            }
        self.assertIn("claim_token", columns)
        self.assertIn("claim_expires_at", columns)

    def test_service_cli_check_once_status_and_health_failure(self):
        outputs: list[dict[str, object]] = []
        for arguments in (["--check"], ["--once"], ["--status"]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(entrypoint(list(arguments)), 0)
            outputs.append(json.loads(output.getvalue()))
        self.assertTrue(outputs[0]["ready"])
        self.assertEqual(outputs[1]["service_run"]["cycles"], 1)
        self.assertEqual(outputs[2]["service"]["state"], "stopped")
        error = io.StringIO()
        with contextlib.redirect_stdout(error):
            self.assertEqual(entrypoint(["--healthcheck"]), 2)
        self.assertFalse(json.loads(error.getvalue())["ok"])

    def test_real_sigterm_drains_foreground_service(self):
        service_root = self.root / "subprocess"
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(Path.cwd() / "src"),
            "SPARKLE_DATA_DIR": str(service_root),
        }
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "sparkle.automation_service",
                "--interval",
                "1",
                "--lease-seconds",
                "60",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        try:
            deadline = time.monotonic() + 5
            store = AutomationStore(
                service_root / "data_environment" / "automations.sqlite3"
            )
            while time.monotonic() < deadline:
                if store.service_status()["active"]:
                    break
                time.sleep(0.05)
            else:
                self.fail("Automation subprocess did not publish a heartbeat")
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        self.assertEqual(process.returncode, 0, stderr)
        result = json.loads(stdout)
        self.assertTrue(result["ok"])
        self.assertEqual(result["service_run"]["state"], "stopped")
        self.assertEqual(store.service_status()["state"], "stopped")

    def test_systemd_profile_has_supervision_and_hardening(self):
        source = Path("automation_environment/sparkle-automations.service").read_text(
            encoding="utf-8",
        )
        for required in (
            "User=sparkle",
            "ExecStartPre=/opt/sparkle/.venv/bin/sparkle-automations --check",
            "Restart=on-failure",
            "TimeoutStopSec=1200s",
            "UMask=0077",
            "NoNewPrivileges=yes",
            "ProtectSystem=strict",
            "ReadWritePaths=/var/lib/sparkle",
            "CapabilityBoundingSet=",
        ):
            self.assertIn(required, source)
        self.assertNotIn("MINIMAX_API_KEY=", source)


if __name__ == "__main__":
    unittest.main()
