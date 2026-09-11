from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from sparkle.system import SparkleSystem
from sparkle.voice import VoiceSessionError


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sparkle-voice", description="SPARKLE voice session lifecycle")
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--ttl-seconds", type=int, default=1800)
    start.add_argument("--language")
    start.add_argument("--voice")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("session_id")
    history = sub.add_parser("history")
    history.add_argument("session_id")
    transcribe = sub.add_parser("transcribe")
    transcribe.add_argument("session_id")
    transcribe.add_argument("path")
    transcribe.add_argument("media_type")
    transcribe.add_argument("--expected-revision", type=int, required=True)
    synth = sub.add_parser("synthesize")
    synth.add_argument("session_id")
    synth.add_argument("text")
    synth.add_argument("--expected-revision", type=int, required=True)
    close = sub.add_parser("close")
    close.add_argument("session_id")
    close.add_argument("--expected-revision", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = SparkleSystem().voice
    if args.command == "start":
        _print(service.start_session(ttl_seconds=args.ttl_seconds, language=args.language, voice=args.voice))
    elif args.command == "inspect":
        _print(service.session(args.session_id))
    elif args.command == "history":
        _print({"history": service.history(args.session_id)})
    elif args.command == "transcribe":
        audio = Path(args.path).resolve().read_bytes()
        _print(service.transcribe_session(args.session_id, audio, args.media_type, expected_revision=args.expected_revision))
    elif args.command == "synthesize":
        result = service.synthesize_session(args.session_id, args.text, expected_revision=args.expected_revision)
        public = {key: value for key, value in result.items() if key != "audio"}
        public["audio_base64"] = base64.b64encode(result["audio"]).decode("ascii")
        _print(public)
    elif args.command == "close":
        _print(service.close_session(args.session_id, expected_revision=args.expected_revision))
    return 0


def entrypoint() -> None:
    try:
        raise SystemExit(main())
    except (VoiceSessionError, ValueError, RuntimeError, OSError) as exc:
        _print({"ok": False, "error": str(exc)})
        raise SystemExit(2) from exc


if __name__ == "__main__":
    entrypoint()
