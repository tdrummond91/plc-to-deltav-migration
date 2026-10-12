"""Thin command layer for private source analysis; help performs no source I/O."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plc", description="Read-only L5X source understanding tools.")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser(
        "inspect",
        help="Inventory one captured L5X source snapshot.",
        description=(
            "Report source structure, rung syntax and gaps. All output is private "
            "and may contain source names, raw logic and source hashes. "
            "Engineering classifications are not implemented."
        ),
        epilog=(
            "Example: plc inspect example.L5X --format json. "
            "Use --rung-id with an exact ID from the same snapshot's JSON. "
            "Exit codes: 0 complete structural report, 1 failure, 2 usage, 3 partial coverage."
        ),
    )
    inspect.add_argument("file", type=Path, help="Local L5X input; never modified.")
    inspect.add_argument("--format", choices=("text", "json"), default="text", help="Stdout format (default: text).")
    inspect.add_argument("--rung-id", help="Show one exact snapshot-bound rung ID on stdout.")
    inspect.add_argument(
        "--workspace", type=Path,
        help=(
            "Explicit private directory for a NEW run; saves the captured L5X, "
            "full inventory, overview and final manifest even with --rung-id. "
            "Omit to write only stdout."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # JSON and private reports retain multilingual source text on Windows,
    # including when stdout is redirected through a legacy-codepage shell.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    # Delay analysis imports until help/usage handling has completed.
    from .reporting import ReportError, render_json, render_text
    from .source import SourceError, analyze_snapshot, capture_snapshot
    from .storage import StorageError, save_run

    try:
        snapshot = capture_snapshot(args.file)
        result = analyze_snapshot(snapshot)
        renderer = render_json if args.format == "json" else render_text
        rendered = renderer(result, args.rung_id)
        if args.workspace is not None:
            saved = save_run(args.workspace, snapshot, result)
            print(f"Saved private run: {saved}", file=sys.stderr)
        sys.stdout.write(rendered)
        return 3 if result.to_dict()["status"] == "partial" else 0
    except (SourceError, StorageError, ReportError) as exc:
        print(f"plc: {exc}", file=sys.stderr)
        return 1
    except OSError:
        print("plc: Could not read or write a local stream.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
