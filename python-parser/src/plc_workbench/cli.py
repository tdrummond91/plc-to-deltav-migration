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
    summarize = commands.add_parser(
        "summarize",
        help="Generate a bounded aggregate summary for repository sync.",
        description=(
            "Capture and analyze one local L5X, then emit only the approved summary "
            "schema. These aggregates are approved for this project's repository sync. "
            "No raw source identifiers, paths or logic belong in this summary."
        ),
        epilog=(
            "Example: plc summarize example.L5X --output public/inspection/summary.json. "
            "Omit --output for JSON on stdout. Shell redirection is outside path checks. "
            "Exit codes: 0 complete structural report, 1 failure, 2 usage, 3 partial coverage."
        ),
    )
    summarize.add_argument("file", type=Path, help="Local L5X input; never modified.")
    summarize.add_argument(
        "--output", type=Path,
        help="NEW .json destination; existing files and symlinks are never overwritten.",
    )
    return parser


def _summarize(args: argparse.Namespace) -> int:
    from .revision import collect_revision
    from .source import SourceError, analyze_snapshot, capture_snapshot
    from .summary import SummaryError, build_summary, render_summary
    from .summary_output import SummaryOutputError, publish_summary

    try:
        snapshot = capture_snapshot(args.file)
        result = analyze_snapshot(snapshot)
        summary = build_summary(result, revision=collect_revision())
        rendered = render_summary(summary)
        partial = result.status == "partial"
        if args.output is None:
            sys.stdout.write(rendered)
        else:
            publish_summary(args.output, rendered, input_path=args.file)
            notice = (
                "Saved aggregate summary; status: partial."
                if partial else
                "Saved aggregate summary; status: complete."
            )
            print(notice, file=sys.stderr)
        return 3 if partial else 0
    except SourceError:
        # The source reader is also used by private inspection, whose error
        # context may include operating-system diagnostics. The shareable
        # summary boundary must not reflect any of that source context.
        print("plc: Cannot read or analyze source; no summary was produced.", file=sys.stderr)
        return 1
    except (SummaryError, SummaryOutputError) as exc:
        print(f"plc: {exc}", file=sys.stderr)
        return 1
    except OSError:
        print("plc: Could not read or write a local stream.", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # JSON and private reports retain multilingual source text on Windows,
    # including when stdout is redirected through a legacy-codepage shell.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if args.command == "summarize":
        return _summarize(args)
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
