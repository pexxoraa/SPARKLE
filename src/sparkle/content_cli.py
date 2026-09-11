from __future__ import annotations

import argparse
import json
from pathlib import Path

from sparkle.content_workflow import ContentWorkflowError, ContentWorkflowService


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _load(path: str) -> dict[str, object]:
    value = json.loads(Path(path).resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Manifest must contain a JSON object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sparkle-content", description="SPARKLE persistent content workflows")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list").add_argument("--query", default="")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("name")
    history = sub.add_parser("history")
    history.add_argument("name")
    templates = sub.add_parser("templates")
    templates.add_argument("--include-archived", action="store_true")
    template = sub.add_parser("template-save")
    template.add_argument("manifest")
    template.add_argument("--expected-revision", type=int, default=0)
    template.add_argument("--approve", action="store_true")
    create = sub.add_parser("create")
    create.add_argument("manifest")
    create.add_argument("--approve", action="store_true")
    update = sub.add_parser("update")
    update.add_argument("name")
    update.add_argument("changes")
    update.add_argument("--expected-revision", type=int, required=True)
    update.add_argument("--approve", action="store_true")
    transform = sub.add_parser("transform")
    transform.add_argument("name")
    transform.add_argument("manifest")
    transform.add_argument("--expected-revision", type=int, required=True)
    transform.add_argument("--approve", action="store_true")
    transition = sub.add_parser("transition")
    transition.add_argument("name")
    transition.add_argument("status", choices=sorted(ContentWorkflowService.STATUSES))
    transition.add_argument("--expected-revision", type=int, required=True)
    transition.add_argument("--approve", action="store_true")
    export = sub.add_parser("export")
    export.add_argument("name")
    export.add_argument("format", choices=sorted(ContentWorkflowService.EXPORTS))
    export.add_argument("--expected-revision", type=int, required=True)
    export.add_argument("--approve", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = ContentWorkflowService()
    if args.command == "list":
        _print({"items": service.search(args.query)})
    elif args.command == "inspect":
        _print(service.get(args.name, include_archived=True))
    elif args.command == "history":
        _print({"history": service.history(args.name)})
    elif args.command == "templates":
        _print({"templates": service.templates(include_archived=args.include_archived)})
    else:
        if not args.approve:
            raise ValueError("Explicit operator approval required")
        if args.command == "template-save":
            _print(service.save_template(_load(args.manifest), expected_revision=args.expected_revision, operator="cli"))
        elif args.command == "create":
            _print(service.create(_load(args.manifest), operator="cli"))
        elif args.command == "update":
            _print(service.update(args.name, _load(args.changes), expected_revision=args.expected_revision, operator="cli"))
        elif args.command == "transform":
            _print(service.transform(args.name, _load(args.manifest), expected_revision=args.expected_revision, operator="cli"))
        elif args.command == "transition":
            _print(service.transition(args.name, args.status, expected_revision=args.expected_revision, operator="cli"))
        elif args.command == "export":
            _print(service.export(args.name, args.format, expected_revision=args.expected_revision))
    return 0


def entrypoint() -> None:
    try:
        raise SystemExit(main())
    except (ContentWorkflowError, ValueError, OSError, json.JSONDecodeError) as exc:
        _print({"ok": False, "error": str(exc)})
        raise SystemExit(2) from exc


if __name__ == "__main__":
    entrypoint()
