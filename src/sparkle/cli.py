from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from sparkle.api import serve
from sparkle.contracts import Message, ModelRequest
from sparkle.model import ModelError
from sparkle.external_worker import ExternalWorkerError
from sparkle.secrets import SecretNotFoundError
from sparkle.system import SparkleSystem
from sparkle.tooling import ToolError


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sparkle", description="SPARKLE personal AI system")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show component and secret-presence status")
    serve_parser = sub.add_parser("serve", help="Start the API and dashboard")
    serve_parser.add_argument("--host")
    serve_parser.add_argument("--port", type=int)
    chat = sub.add_parser("chat", help="Run a text request")
    chat.add_argument("message")
    chat.add_argument("--agent")
    chat.add_argument("--multi", action="store_true")
    smoke = sub.add_parser("smoke-test", help="Verify configuration or make a safe live provider call")
    smoke.add_argument("--live", action="store_true")
    memory = sub.add_parser("remember", help="Store an explicit durable memory")
    memory.add_argument("category")
    memory.add_argument("key")
    memory.add_argument("value")
    knowledge = sub.add_parser("ingest", help="Ingest a UTF-8 text or Markdown file")
    knowledge.add_argument("path")
    knowledge.add_argument("--title")
    knowledge.add_argument(
        "--monitor-key",
        help="Track later revisions under a safe 1-64 character research key",
    )
    agent_install = sub.add_parser("agent-install", help="Install a generated agent manifest")
    agent_install.add_argument("manifest")
    agent_install.add_argument("--approve", action="store_true")
    agent_install.add_argument("--replace", action="store_true")
    agent_remove = sub.add_parser("agent-remove", help="Remove a generated agent")
    agent_remove.add_argument("name")
    agent_remove.add_argument("--approve", action="store_true")
    automation_run = sub.add_parser("automations-run", help="Execute due automations")
    automation_run.add_argument("--watch", action="store_true")
    automation_run.add_argument("--interval", type=float, default=60.0)
    automation_run.add_argument("--lease-seconds", type=int, default=3_600)
    scaffold = sub.add_parser("scaffold", help="Create a bounded application workspace")
    scaffold.add_argument("manifest")
    scaffold.add_argument("--approve", action="store_true")
    scaffold.add_argument("--overwrite", action="store_true")
    verify_workspace = sub.add_parser(
        "verify-workspace", help="Run bounded static checks in an application workspace",
    )
    verify_workspace.add_argument("manifest")
    verify_workspace.add_argument("--approve", action="store_true")
    test_workspace = sub.add_parser(
        "test-workspace", help="Run the fixed opt-in Python unittest command",
    )
    test_workspace.add_argument("project_name")
    test_workspace.add_argument("--approve", action="store_true")
    external_test = sub.add_parser(
        "test-workspace-external",
        help="Submit a workspace to the configured signed HTTPS test worker",
    )
    external_test.add_argument("project_name")
    external_test.add_argument("--approve", action="store_true")
    package_workspace = sub.add_parser(
        "package-workspace", help="Create a deterministic application ZIP artifact",
    )
    package_workspace.add_argument("project_name")
    package_workspace.add_argument("--approve", action="store_true")
    deployment = sub.add_parser(
        "record-deployment", help="Record an immutable unverified deployment event",
    )
    deployment.add_argument("artifact_id", type=int)
    deployment.add_argument("environment_name")
    deployment.add_argument("target_kind")
    deployment.add_argument("reported_outcome")
    deployment.add_argument("--approve", action="store_true")
    return parser


def _load_manifest(path: str) -> dict[str, object]:
    source = Path(path).resolve()
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Manifest root must be a JSON object")
    return value


def live_smoke(system: SparkleSystem) -> int:
    adapter = system.model_router.select("general")
    health = adapter.health()
    if not health.get("configured"):
        _print({"ok": False, "stage": "credential_presence", "provider": health, "secret_value_exposed": False})
        return 2
    started = time.monotonic()
    try:
        response = adapter.complete(ModelRequest(
            messages=[Message(role="user", content="Reply with exactly SPARKLE_LIVE_OK")],
            system="This is a provider connectivity smoke test. Follow the user's exact output instruction.",
            max_output_tokens=64, thinking=False, temperature=0,
        ))
    except ModelError as exc:
        _print({
            "ok": False, "stage": "live_request", "provider": health,
            "error": str(exc), "retryable": exc.retryable, "secret_value_exposed": False,
        })
        return 1
    exact = response.text.strip() == "SPARKLE_LIVE_OK"
    _print({
        "ok": exact, "stage": "live_request", "provider": response.provider, "model": response.model,
        "finish_reason": response.finish_reason, "exact_response_match": exact,
        "provider_request_id": response.provider_request_id,
        "usage": response.usage, "duration_ms": round((time.monotonic() - started) * 1000, 2),
        "secret_value_exposed": False,
    })
    return 0 if exact else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    system = SparkleSystem()
    if args.command == "status":
        _print(system.status())
        return 0
    if args.command == "serve":
        serve(system, args.host or system.config.host, args.port or system.config.port)
        return 0
    if args.command == "chat":
        result = system.orchestrator.run_multi(args.message) if args.multi else system.orchestrator.run(args.message, agent_name=args.agent)
        _print(result.to_dict())
        return 0
    if args.command == "smoke-test":
        if args.live:
            return live_smoke(system)
        _print({"ok": True, "models": system.models.list(), "live_call_executed": False})
        return 0
    if args.command == "remember":
        memory_id = system.memory.remember(args.category, args.key, args.value, metadata={"source": "cli"})
        _print({"ok": True, "memory_id": memory_id})
        return 0
    if args.command == "ingest":
        path = Path(args.path).resolve()
        source_id = system.knowledge_ingestor.ingest(
            path, title=args.title, monitor_key=args.monitor_key,
        )
        _print({"ok": True, "source_id": source_id})
        return 0
    if args.command == "agent-install":
        manifest = _load_manifest(args.manifest)
        manifest["approved"] = bool(args.approve)
        manifest["replace"] = bool(args.replace)
        result = system.tools.execute(
            "agent_install", manifest, allowed={"agent_install"},
        )
        _print({"ok": True, "agent": result})
        return 0
    if args.command == "agent-remove":
        if not args.approve:
            raise ValueError("Agent removal requires --approve")
        _print({"ok": True, "removed": system.agents.remove(args.name)})
        return 0
    if args.command == "automations-run":
        if not args.watch:
            _print({
                "ok": True,
                "runs": system.automation_runner.run_due(
                    lease_seconds=args.lease_seconds,
                ),
            })
            return 0
        from sparkle.automation_service import AutomationService, run_with_signals

        service = AutomationService(
            system.automations,
            system.automation_runner,
            interval_seconds=args.interval,
            lease_seconds=args.lease_seconds,
        )
        _print({"ok": True, "service_run": run_with_signals(service)})
        return 0
    if args.command == "scaffold":
        manifest = _load_manifest(args.manifest)
        manifest["approved"] = bool(args.approve)
        manifest["overwrite"] = bool(args.overwrite)
        result = system.tools.execute(
            "workspace_scaffold", manifest, allowed={"workspace_scaffold"},
        )
        _print({"ok": True, "build": result})
        return 0
    if args.command == "verify-workspace":
        manifest = _load_manifest(args.manifest)
        manifest["approved"] = bool(args.approve)
        result = system.tools.execute(
            "workspace_verify", manifest, allowed={"workspace_verify"},
        )
        _print({"ok": result["status"] == "passed", "verification": result})
        return 0 if result["status"] == "passed" else 1
    if args.command == "test-workspace":
        result = system.tools.execute(
            "workspace_test",
            {"project_name": args.project_name, "approved": bool(args.approve)},
            allowed={"workspace_test"},
        )
        _print({"ok": result["status"] == "passed", "test_run": result})
        return 0 if result["status"] == "passed" else 1
    if args.command == "test-workspace-external":
        result = system.external_worker_tool.run({
            "project_name": args.project_name,
            "approved": bool(args.approve),
        })
        _print({"ok": result["status"] == "passed", "external_test_run": result})
        return 0 if result["status"] == "passed" else 1
    if args.command == "package-workspace":
        result = system.tools.execute(
            "workspace_package",
            {"project_name": args.project_name, "approved": bool(args.approve)},
            allowed={"workspace_package"},
        )
        _print({"ok": True, "artifact": result})
        return 0
    if args.command == "record-deployment":
        if not args.approve:
            raise ValueError("Deployment recording requires --approve")
        result = system.artifacts.record_deployment(
            args.artifact_id,
            args.environment_name,
            args.target_kind,
            args.reported_outcome,
        )
        _print({"ok": True, "deployment": result})
        return 0
    return 2


def entrypoint(argv: list[str] | None = None) -> int:
    try:
        return main(argv)
    except (
        ModelError,
        ExternalWorkerError,
        SecretNotFoundError,
        ValueError,
        KeyError,
        TypeError,
        ToolError,
        FileExistsError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(entrypoint())
