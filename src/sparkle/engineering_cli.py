from __future__ import annotations

import argparse
import json

from sparkle.engineering import EngineeringWorkflowError
from sparkle.system import SparkleSystem


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _object(value: str) -> dict[str, object]:
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("JSON argument must be an object")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sparkle-engineering", description="SPARKLE repository engineering workflows")
    sub = parser.add_subparsers(dest="command", required=True)
    snapshot = sub.add_parser("snapshot"); snapshot.add_argument("--persist", action="store_true")
    file = sub.add_parser("file"); file.add_argument("path")
    sub.add_parser("list")
    inspect = sub.add_parser("inspect"); inspect.add_argument("name")
    readiness = sub.add_parser("readiness"); readiness.add_argument("name")
    create = sub.add_parser("create"); create.add_argument("definition"); create.add_argument("--approve", action="store_true")
    transition = sub.add_parser("transition"); transition.add_argument("name"); transition.add_argument("state"); transition.add_argument("--expected-revision", type=int, required=True); transition.add_argument("--release-notes"); transition.add_argument("--approve", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = SparkleSystem().engineering
    if args.command == "snapshot": _print(service.snapshot(persist=args.persist))
    elif args.command == "file": _print(service.inspect_file(args.path))
    elif args.command == "list": _print({"work_items":service.list_work()})
    elif args.command == "inspect": _print(service.work_item(args.name, include_archived=True))
    elif args.command == "readiness": _print(service.readiness(args.name))
    else:
        if not args.approve: raise ValueError("Explicit operator approval required")
        if args.command == "create": _print(service.create_work_item(_object(args.definition), actor="cli"))
        else: _print(service.transition(args.name,args.state,expected_revision=args.expected_revision,release_notes=args.release_notes,actor="cli"))
    return 0


def entrypoint() -> None:
    try: raise SystemExit(main())
    except (EngineeringWorkflowError, ValueError, OSError, json.JSONDecodeError) as exc:
        _print({"ok":False,"error":str(exc)}); raise SystemExit(2) from exc

if __name__ == "__main__": entrypoint()
