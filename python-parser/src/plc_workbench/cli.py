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
    sfc = commands.add_parser(
        "sfc-structure", help="Inspect private SFC XML structure without execution semantics.",
        description=("Capture one L5X and retain SFC elements and structural links. "
                     "All output is private. Actions, transitions and execution behavior are not interpreted."),
        epilog="Exit codes: 0 covered within SFC structure scope, 1 failure, 2 usage, 3 partial SFC structure.",
    )
    sfc.add_argument("file", type=Path, help="Local L5X input; never modified.")
    sfc.add_argument("--format", choices=("text", "json"), default="text")
    sfc.add_argument("--workspace", type=Path, help="Explicit private directory for a NEW captured source and SFC run.")
    sfc_summary = commands.add_parser(
        "sfc-summary", help="Generate count-only SFC structural feedback for sync.",
        description="Emit fixed structural counts without source identifiers, raw XML or individual links.",
        epilog="Exit codes: 0 covered within SFC structure scope, 1 failure, 2 usage, 3 partial SFC structure.",
    )
    sfc_summary.add_argument("file", type=Path, help="Local L5X input; never modified.")
    sfc_summary.add_argument("--output", type=Path, help="NEW .json file; never overwritten.")
    review = commands.add_parser(
        "review", help="Save a private offline engineering review report.",
        description=("Capture one L5X and save a searchable HTML report with source objects, "
                     "rungs, SFC structure, pattern groups and unresolved findings. "
                     "All report contents are private. Open the saved HTML in a browser."),
        epilog="Exit codes: 0 covered within scope, 1 failure, 2 usage, 3 usable partial report.",
    )
    review.add_argument("file", type=Path, help="Local L5X input; never modified.")
    review.add_argument("--workspace", type=Path, required=True,
                        help="Private directory for a NEW review run; existing runs are preserved.")
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


def _sfc(args: argparse.Namespace) -> int:
    from .revision import collect_revision
    from .sfc_structure import (
        SfcStructureError, analyze_sfc_structure,
        render_sfc_json, render_sfc_text,
    )
    from .sfc_summary import SfcSummaryError, build_sfc_summary, render_sfc_summary
    from .source import SourceError, analyze_snapshot, capture_snapshot
    from .storage import StorageError, save_run
    from .summary_output import SummaryOutputError, publish_summary

    try:
        snapshot = capture_snapshot(args.file)
        inventory = analyze_snapshot(snapshot)
        result = analyze_sfc_structure(snapshot, inventory)
        if args.command == "sfc-summary":
            summary = build_sfc_summary(snapshot, inventory, result, revision=collect_revision())
            rendered = render_sfc_summary(summary)
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                publish_summary(args.output, rendered, input_path=args.file)
                print(f"Saved aggregate SFC structure summary; status: {result.status}.", file=sys.stderr)
        else:
            rendered = (render_sfc_json(result) if args.format == "json"
                        else render_sfc_text(result, inventory=inventory))
            if args.workspace is not None:
                saved = save_run(args.workspace, snapshot, inventory, sfc_structure=result)
                print(f"Saved private SFC structure run: {saved}", file=sys.stderr)
            sys.stdout.write(rendered)
        return 3 if result.status == "partial" else 0
    except SourceError:
        print("plc: Cannot read or analyze source; no SFC structure report was produced.", file=sys.stderr)
        return 1
    except (SfcStructureError, SfcSummaryError, StorageError, SummaryOutputError) as exc:
        print(f"plc: {exc}", file=sys.stderr)
        return 1
    except OSError:
        print("plc: Could not read or write a local stream.", file=sys.stderr)
        return 1


def _review(args: argparse.Namespace) -> int:
    from .access import AccessError, analyze_access
    from .pid import PidError, analyze_pid
    from .pid_members import PidMemberError, analyze_pid_members
    from .calculations import CalculationError, analyze_calculations
    from .rung_analysis import RungAnalysisError, analyze_rungs
    from .relationships import RelationshipError, analyze_relationships
    from .conditions import ConditionError, analyze_conditions
    from .binding_context import BindingContextError, analyze_binding_context
    from .references import ReferenceError, analyze_references
    from .sfc_structure import SfcStructureError, analyze_sfc_structure
    from .source import SourceError, analyze_snapshot, capture_snapshot
    from .storage import StorageError, save_run
    from .tag_data import TagDataError, analyze_tag_data

    try:
        snapshot = capture_snapshot(args.file)
        inventory = analyze_snapshot(snapshot)
        references = analyze_references(inventory)
        sfc = analyze_sfc_structure(snapshot, inventory)
        calculations = analyze_calculations(snapshot, inventory, references)
        access = analyze_access(inventory, references, schema_version=4,
                                snapshot=snapshot, calculations=calculations)
        rung_analysis = analyze_rungs(snapshot, inventory, references, access, calculations)
        relationships = analyze_relationships(snapshot, inventory, references, access, calculations, rung_analysis)
        conditions = analyze_conditions(snapshot, inventory, references, access, calculations, rung_analysis, relationships,
                                        schema_version=2)
        binding_context = analyze_binding_context(
            snapshot, inventory, references, access, calculations, rung_analysis, relationships, conditions)
        tag_data = analyze_tag_data(snapshot, inventory)
        pid = analyze_pid(snapshot, inventory, references, tag_data)
        pid_members = analyze_pid_members(snapshot, inventory, references, tag_data, pid)
        saved = save_run(args.workspace, snapshot, inventory, references=references,
                         sfc_structure=sfc, include_review=True, access=access, tag_data=tag_data, pid=pid,
                         pid_members=pid_members, calculations=calculations, rung_analysis=rung_analysis, relationships=relationships,
                         conditions=conditions, binding_context=binding_context)
        print(f"Private review report: {saved / 'review.html'}")
        return 3 if "partial" in (inventory.status, references.status, sfc.status, access.status,
                                tag_data.status, pid.status, pid_members.status, calculations.status, rung_analysis.status,
                                relationships.status, conditions.status, binding_context.status) else 0
    except SourceError:
        print("plc: Cannot read or analyze source; no review report was produced.", file=sys.stderr)
        return 1
    except AccessError:
        print("plc: Cannot analyze operand access; no review report was produced.", file=sys.stderr)
        return 1
    except TagDataError:
        print("plc: Cannot analyze Tag Data; no review report was produced.", file=sys.stderr)
        return 1
    except PidError:
        print("plc: Cannot analyze PID evidence; no review report was produced.", file=sys.stderr)
        return 1
    except CalculationError:
        print("plc: Cannot analyze calculation evidence; no review report was produced.", file=sys.stderr)
        return 1
    except ConditionError:
        print("plc: Cannot analyze local boolean conditions; no review report was produced.", file=sys.stderr)
        return 1
    except BindingContextError:
        print("plc: Cannot analyze binding context; no review report was produced.", file=sys.stderr)
        return 1
    except RelationshipError:
        print("plc: Cannot analyze address relationships; no review report was produced.", file=sys.stderr)
        return 1
    except RungAnalysisError:
        print("plc: Cannot analyze rung structure; no review report was produced.", file=sys.stderr)
        return 1
    except PidMemberError:
        print("plc: Cannot analyze PID member headers; no review report was produced.", file=sys.stderr)
        return 1
    except (ReferenceError, SfcStructureError, StorageError) as exc:
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
    if args.command in ("sfc-structure", "sfc-summary"):
        return _sfc(args)
    if args.command == "review":
        return _review(args)
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
