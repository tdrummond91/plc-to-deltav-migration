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
    references = commands.add_parser(
        "references", help="Inspect private scoped tag and alias root bindings.",
        description=(
            "Bind supported ladder operands to declared roots and follow aliases. "
            "All output is private. Member validity, read/write effects and "
            "engineering classifications are not analyzed."
        ),
        epilog="Exit codes: 0 covered within scope, 1 failure, 2 usage, 3 partial coverage.",
    )
    references.add_argument("file", type=Path, help="Local L5X input; never modified.")
    references.add_argument("--format", choices=("text", "json"), default="text")
    references.add_argument(
        "--workspace", type=Path,
        help="Explicit private directory for a NEW snapshot, inventory and reference run.",
    )
    reference_summary = commands.add_parser(
        "reference-summary", help="Generate aggregate tag/alias reference feedback for sync.",
        description=(
            "Emit approved structural and root-binding counts with fixed status buckets. "
            "No names, values, source identities, operand text or individual links are included."
        ),
        epilog="Exit codes: 0 covered within scope, 1 failure, 2 usage, 3 usable partial report.",
    )
    reference_summary.add_argument("file", type=Path, help="Local L5X input; never modified.")
    reference_summary.add_argument("--output", type=Path, help="NEW .json file; never overwritten.")
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


def _references(args: argparse.Namespace) -> int:
    from .reference_reporting import render_reference_json, render_reference_text
    from .reference_summary import ReferenceSummaryError, build_reference_summary, render_reference_summary
    from .references import ReferenceError, analyze_references
    from .revision import collect_revision
    from .source import SourceError, analyze_snapshot, capture_snapshot
    from .storage import StorageError, save_run
    from .summary import SummaryError
    from .summary_output import SummaryOutputError, publish_summary

    aggregate = args.command == "reference-summary"
    try:
        snapshot = capture_snapshot(args.file)
        inventory = analyze_snapshot(snapshot)
        result = analyze_references(inventory)
        if aggregate:
            summary = build_reference_summary(inventory, result, revision=collect_revision())
            rendered = render_reference_summary(summary)
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                publish_summary(args.output, rendered, input_path=args.file)
                print(f"Saved aggregate reference summary; status: {result.status}.", file=sys.stderr)
        else:
            rendered = (render_reference_json(result) if args.format == "json"
                        else render_reference_text(result, inventory=inventory))
            if args.workspace is not None:
                saved = save_run(args.workspace, snapshot, inventory, references=result)
                print(f"Saved private reference run: {saved}", file=sys.stderr)
            sys.stdout.write(rendered)
        return 3 if result.status == "partial" else 0
    except SourceError:
        print("plc: Cannot read or analyze source; no reference report was produced.", file=sys.stderr)
        return 1
    except (ReferenceError, ReferenceSummaryError, SummaryError, SummaryOutputError, StorageError) as exc:
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
    if args.command in ("references", "reference-summary"):
        return _references(args)
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
