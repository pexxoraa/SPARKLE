from __future__ import annotations

import argparse
import json

from sparkle.interaction import InteractionSessionError
from sparkle.system import SparkleSystem


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sparkle-interaction", description="SPARKLE operator interaction sessions")
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("mode", choices=["browser", "computer"])
    start.add_argument("--ttl-seconds", type=int, default=900)
    start.add_argument("--host", action="append", default=[])
    start.add_argument("--action", action="append", default=[])
    inspect = sub.add_parser("inspect")
    inspect.add_argument("session_id")
    history = sub.add_parser("history")
    history.add_argument("session_id")
    browse = sub.add_parser("browse")
    browse.add_argument("session_id")
    browse.add_argument("url")
    browse.add_argument("--expected-revision", type=int, required=True)
    browse.add_argument("--timeout-seconds", type=int, default=15)
    browse.add_argument("--max-text-chars", type=int, default=20_000)
    action = sub.add_parser("action")
    action.add_argument("session_id")
    action.add_argument("kind", choices=["screenshot", "click", "type_text", "key"])
    action.add_argument("--x", type=int)
    action.add_argument("--y", type=int)
    action.add_argument("--text")
    action.add_argument("--key")
    action.add_argument("--expected-revision", type=int, required=True)
    close = sub.add_parser("close")
    close.add_argument("session_id")
    close.add_argument("--expected-revision", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = SparkleSystem().interactions
    if args.command == "start":
        _print(service.start_session(args.mode, ttl_seconds=args.ttl_seconds, allowed_hosts=args.host, allowed_actions=args.action))
    elif args.command == "inspect":
        _print(service.session(args.session_id))
    elif args.command == "history":
        _print({"history": service.history(args.session_id)})
    elif args.command == "browse":
        _print(service.browse_session(args.session_id, args.url, expected_revision=args.expected_revision,
                                      timeout_seconds=args.timeout_seconds, max_text_chars=args.max_text_chars))
    elif args.command == "action":
        payload = {"kind": args.kind}
        for field in ("x", "y", "text", "key"):
            value = getattr(args, field)
            if value is not None:
                payload[field] = value
        _print(service.perform_session(args.session_id, payload, expected_revision=args.expected_revision))
    elif args.command == "close":
        _print(service.close_session(args.session_id, expected_revision=args.expected_revision))
    return 0


def entrypoint() -> None:
    try:
        raise SystemExit(main())
    except (InteractionSessionError, ValueError, RuntimeError) as exc:
        _print({"ok": False, "error": str(exc)})
        raise SystemExit(2) from exc


if __name__ == "__main__":
    entrypoint()
