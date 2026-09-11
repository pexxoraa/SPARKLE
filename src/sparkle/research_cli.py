from __future__ import annotations

import argparse
import json

from sparkle.research import ResearchService, ResearchWorkflowError
from sparkle.system import SparkleSystem


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _json_arg(value: str) -> dict[str, object]:
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("JSON argument must be an object")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sparkle-research", description="SPARKLE persistent research workflows")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    inspect = sub.add_parser("inspect"); inspect.add_argument("name")
    create = sub.add_parser("create"); create.add_argument("definition"); create.add_argument("--approve", action="store_true")
    transition = sub.add_parser("transition"); transition.add_argument("name"); transition.add_argument("status", choices=sorted(ResearchService.STATUS)); transition.add_argument("--expected-revision", type=int, required=True); transition.add_argument("--approve", action="store_true")
    evidence = sub.add_parser("evidence-add"); evidence.add_argument("name"); evidence.add_argument("citation"); evidence.add_argument("--source-quality", choices=sorted(ResearchService.QUALITY), default="unknown"); evidence.add_argument("--quality-rationale", default="Not independently assessed"); evidence.add_argument("--approve", action="store_true")
    claim = sub.add_parser("claim-add"); claim.add_argument("name"); claim.add_argument("claim"); claim.add_argument("--approve", action="store_true")
    report = sub.add_parser("report"); report.add_argument("name")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = SparkleSystem().research
    if args.command == "list": _print({"projects": service.list()})
    elif args.command == "inspect": _print(service.inspect(args.name, include_archived=True))
    elif args.command == "report": _print(service.report(args.name))
    else:
        if not args.approve: raise ValueError("Explicit operator approval required")
        if args.command == "create": _print(service.create(_json_arg(args.definition), actor="cli"))
        elif args.command == "transition": _print(service.transition(args.name,args.status,expected_revision=args.expected_revision,actor="cli"))
        elif args.command == "evidence-add": _print(service.add_evidence(args.name,_json_arg(args.citation),source_quality=args.source_quality,quality_rationale=args.quality_rationale,actor="cli"))
        elif args.command == "claim-add": _print(service.add_claim(args.name,_json_arg(args.claim),actor="cli"))
    return 0


def entrypoint() -> None:
    try: raise SystemExit(main())
    except (ResearchWorkflowError, ValueError, OSError, json.JSONDecodeError) as exc:
        _print({"ok":False,"error":str(exc)}); raise SystemExit(2) from exc

if __name__ == "__main__": entrypoint()
