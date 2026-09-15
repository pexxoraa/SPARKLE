from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import time
from pathlib import Path

from sparkle.browser_runtime import DefaultInteractionService, run_browser_acceptance
from sparkle.interaction import InteractionSessionError


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _write_new_artifact(
    path: str, value: dict[str, object]
) -> tuple[Path, str]:
    target = Path(os.path.abspath(Path(path).expanduser()))
    if not target.parent.is_dir():
        raise ValueError("Browser acceptance artifact parent does not exist")
    encoded = (
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(target, flags, 0o600)
    except OSError as exc:
        raise ValueError(
            "Browser acceptance artifact must be a new regular file"
        ) from exc
    identity: tuple[int, int] | None = None
    try:
        with os.fdopen(descriptor, "wb") as output:
            metadata = os.fstat(output.fileno())
            identity = (metadata.st_dev, metadata.st_ino)
            owner_matches = (
                not hasattr(os, "geteuid") or metadata.st_uid == os.geteuid()
            )
            if (
                not stat.S_ISREG(metadata.st_mode)
                or not owner_matches
                or metadata.st_nlink != 1
            ):
                raise ValueError(
                    "Browser acceptance artifact must be an owner-only regular file"
                )
            if os.name == "posix":
                os.fchmod(output.fileno(), 0o600)
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        try:
            current = target.lstat()
            if identity == (current.st_dev, current.st_ino):
                target.unlink()
        except OSError:
            pass
        raise
    return target, hashlib.sha256(encoded).hexdigest()


def _read_artifact(path: str) -> tuple[Path, bytes, dict[str, object]]:
    target = Path(os.path.abspath(Path(path).expanduser()))
    try:
        before = target.lstat()
        if stat.S_ISLNK(before.st_mode):
            raise ValueError(
                "Browser acceptance artifact must be an owner-only regular file"
            )
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(target, flags)
        with os.fdopen(descriptor, "rb") as source:
            metadata = os.fstat(source.fileno())
            owner_matches = (
                not hasattr(os, "geteuid") or metadata.st_uid == os.geteuid()
            )
            if (
                not stat.S_ISREG(metadata.st_mode)
                or not owner_matches
                or metadata.st_mode & 0o077
                or not 1 <= metadata.st_size <= 65_536
                or (before.st_dev, before.st_ino)
                != (metadata.st_dev, metadata.st_ino)
            ):
                raise ValueError(
                    "Browser acceptance artifact must be an owner-only regular file"
                )
            raw = source.read(65_537)
    except ValueError:
        raise
    except OSError as exc:
        raise ValueError("Browser acceptance artifact is unavailable") from exc
    try:
        decoded = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Browser acceptance artifact is invalid") from exc
    if not isinstance(decoded, dict):
        raise ValueError("Browser acceptance artifact must be a JSON object")
    return target, raw, decoded


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sparkle-interaction",
        description="SPARKLE operator interaction sessions",
    )
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
    action.add_argument(
        "kind", choices=["screenshot", "click", "type_text", "key"]
    )
    action.add_argument("--x", type=int)
    action.add_argument("--y", type=int)
    action.add_argument("--text")
    action.add_argument("--key")
    action.add_argument("--expected-revision", type=int, required=True)
    close = sub.add_parser("close")
    close.add_argument("session_id")
    close.add_argument("--expected-revision", type=int, required=True)
    accept = sub.add_parser("accept-browser")
    accept.add_argument("--output", required=True)
    record = sub.add_parser("record-browser-acceptance")
    record.add_argument("artifact")
    record.add_argument("--operator", required=True)
    record.add_argument("--ttl-hours", type=int, default=720)
    sub.add_parser("browser-acceptance-status")
    revoke = sub.add_parser("revoke-browser-acceptance")
    revoke.add_argument("record_id")
    revoke.add_argument("--operator", required=True)
    revoke.add_argument("--reason", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # The operator CLI enables SPARKLE's concrete safe HTTPS browser. GUI
    # computer control remains disabled unless a host-specific adapter is
    # explicitly supplied by an embedding/runtime integration.
    service = DefaultInteractionService()
    if args.command == "start":
        _print(
            service.start_session(
                args.mode,
                ttl_seconds=args.ttl_seconds,
                allowed_hosts=args.host,
                allowed_actions=args.action,
            )
        )
    elif args.command == "inspect":
        _print(service.session(args.session_id))
    elif args.command == "history":
        _print({"history": service.history(args.session_id)})
    elif args.command == "browse":
        _print(
            service.browse_session(
                args.session_id,
                args.url,
                expected_revision=args.expected_revision,
                timeout_seconds=args.timeout_seconds,
                max_text_chars=args.max_text_chars,
            )
        )
    elif args.command == "action":
        payload = {"kind": args.kind}
        for field in ("x", "y", "text", "key"):
            value = getattr(args, field)
            if value is not None:
                payload[field] = value
        _print(
            service.perform_session(
                args.session_id,
                payload,
                expected_revision=args.expected_revision,
            )
        )
    elif args.command == "close":
        _print(
            service.close_session(
                args.session_id,
                expected_revision=args.expected_revision,
            )
        )
    elif args.command == "accept-browser":
        evidence = run_browser_acceptance(service.browser)
        target, artifact_sha256 = _write_new_artifact(args.output, evidence)
        _print(
            {
                **evidence,
                "artifact_path": str(target),
                "artifact_sha256": artifact_sha256,
            }
        )
        return 0 if evidence["passed"] is True else 2
    elif args.command == "record-browser-acceptance":
        if not 1 <= args.ttl_hours <= 2_160:
            raise ValueError("Browser acceptance TTL must be 1-2160 hours")
        target, raw, evidence = _read_artifact(args.artifact)
        _print(
            service.record_browser_acceptance(
                evidence,
                artifact_sha256=hashlib.sha256(raw).hexdigest(),
                artifact_ref=str(target),
                operator=args.operator,
                expires_at=time.time() + args.ttl_hours * 3_600,
            )
        )
    elif args.command == "browser-acceptance-status":
        _print(service.browser_acceptance())
    elif args.command == "revoke-browser-acceptance":
        _print(
            service.revoke_browser_acceptance(
                args.record_id,
                operator=args.operator,
                reason=args.reason,
            )
        )
    return 0


def entrypoint() -> None:
    try:
        raise SystemExit(main())
    except (InteractionSessionError, ValueError, RuntimeError) as exc:
        _print({"ok": False, "error": str(exc)})
        raise SystemExit(2) from exc


if __name__ == "__main__":
    entrypoint()
