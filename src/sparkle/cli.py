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
    return parser


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
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ModelError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
