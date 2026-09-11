from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sparkle.data_analysis import DataAnalysisService


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _json_object(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Recipe root must be a JSON object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sparkle-data", description="SPARKLE bounded data-analysis workflows")
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest", help="Import or revise a bounded CSV/JSON dataset")
    ingest.add_argument("name")
    ingest.add_argument("path")
    ingest.add_argument("--format", choices=("csv", "json"))
    ingest.add_argument("--title")
    ingest.add_argument("--expected-revision", type=int, default=0)
    ingest.add_argument("--approve", action="store_true")
    listing = sub.add_parser("list", help="List imported datasets")
    listing.add_argument("--include-archived", action="store_true")
    inspect = sub.add_parser("inspect", help="Inspect schema and bounded sample rows")
    inspect.add_argument("name")
    inspect.add_argument("--sample", type=int, default=20)
    inspect.add_argument("--include-archived", action="store_true")
    analyze = sub.add_parser("analyze", help="Run and persist a deterministic analysis recipe")
    analyze.add_argument("name")
    analyze.add_argument("recipe")
    analyze.add_argument("--approve", action="store_true")
    history = sub.add_parser("history", help="List reproducible analysis artifacts")
    history.add_argument("name")
    history.add_argument("--limit", type=int, default=20)
    archive = sub.add_parser("archive", help="Archive a dataset with optimistic revision control")
    archive.add_argument("name")
    archive.add_argument("--expected-revision", type=int, required=True)
    archive.add_argument("--approve", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = DataAnalysisService()
    if args.command == "ingest":
        if not args.approve:
            raise ValueError("Dataset ingestion requires --approve")
        path = Path(args.path).expanduser().resolve()
        source_format = args.format or path.suffix.lower().lstrip(".")
        _print(service.ingest(
            args.name, path.read_text(encoding="utf-8"), source_format=source_format,
            title=args.title, expected_revision=args.expected_revision, operator="cli",
        ))
        return 0
    if args.command == "list":
        _print({"datasets": service.datasets(include_archived=args.include_archived)})
        return 0
    if args.command == "inspect":
        _print(service.inspect(args.name, sample=args.sample, include_archived=args.include_archived))
        return 0
    if args.command == "analyze":
        if not args.approve:
            raise ValueError("Persisted analysis requires --approve")
        _print(service.analyze(args.name, _json_object(args.recipe), persist=True, operator="cli"))
        return 0
    if args.command == "history":
        _print({"analyses": service.history(args.name, limit=args.limit)})
        return 0
    if args.command == "archive":
        if not args.approve:
            raise ValueError("Dataset archival requires --approve")
        _print(service.archive(args.name, expected_revision=args.expected_revision, operator="cli"))
        return 0
    raise AssertionError("unreachable")


def entrypoint() -> None:
    raise SystemExit(main())
