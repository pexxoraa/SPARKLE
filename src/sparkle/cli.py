from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from sparkle.api import serve
from sparkle.contracts import Message, ModelRequest
from sparkle.model import ModelError
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
    scaffold = sub.add_parser("scaffold", help="Create a bounded application workspace")
    scaffold.add_argument("manifest")
    scaffold.add_argument("--approve", action="store_true")
    scaffold.add_argument("--overwrite", action="store_true")
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
        source_id = system.knowledge_ingestor.ingest(path, title=args.title)
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
            _print({"ok": True, "runs": system.automation_runner.run_due()})
            return 0
        if not 1 <= args.interval <= 3600:
            raise ValueError("Watch interval must be from 1 to 3600 seconds")
        try:
            while True:
                runs = system.automation_runner.run_due()
                if runs:
                    _print({"ok": True, "runs": runs})
                time.sleep(args.interval)
        except KeyboardInterrupt:
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
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ModelError, ValueError, KeyError, TypeError, ToolError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
