from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from sparkle.system import SparkleSystem


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sparkle-level3",
        description="Inspect SPARKLE Level-3 controlled-execution state",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show Level-3, worker, and deployment-gate status")
    jobs = sub.add_parser("jobs", help="List recent controlled executions with Level-3 state")
    jobs.add_argument("--limit", type=int, default=20)
    job = sub.add_parser("job", help="Inspect one controlled execution")
    job.add_argument("execution_id")
    worker = sub.add_parser("worker-runs", help="List external worker run evidence")
    worker.add_argument("--limit", type=int, default=20)
    sub.add_parser("diagnostics", help="Summarize Level-3 failure stages without secrets")
    return parser


def _jobs(system: SparkleSystem, limit: int) -> list[dict[str, Any]]:
    records = system.controlled_executions.list(limit=max(1, min(limit, 100)))
    return [
        system.ai_system_controlled_executor.inspect(record["execution_id"])
        for record in records
    ]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    system = SparkleSystem()
    executor = system.ai_system_controlled_executor
    if args.command == "status":
        _print({
            "level3": executor.level3_status(),
            "worker": system.external_worker.status(),
            "controlled_execution_protocol": executor.PROTOCOL,
            "deployment": "FROZEN",
            "deployment_authorized": False,
        })
        return 0
    if args.command == "jobs":
        _print(_jobs(system, args.limit))
        return 0
    if args.command == "job":
        _print(executor.inspect(args.execution_id))
        return 0
    if args.command == "worker-runs":
        _print(system.external_worker.list(limit=max(1, min(args.limit, 100))))
        return 0
    if args.command == "diagnostics":
        jobs = _jobs(system, 100)
        failures: dict[str, int] = {}
        for job in jobs:
            level3 = job.get("level3") or {}
            stage = level3.get("failure_stage")
            if stage:
                failures[str(stage)] = failures.get(str(stage), 0) + 1
        _print({
            "level3": executor.level3_status(),
            "failure_stages": failures,
            "worker": system.external_worker.status(),
            "credentials_exposed": False,
            "deployment": "FROZEN",
        })
        return 0
    raise AssertionError("unreachable")


def entrypoint(argv: list[str] | None = None) -> int:
    try:
        return main(argv)
    except (ValueError, KeyError, RuntimeError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(entrypoint())
