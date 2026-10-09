"""CLI only: inspect ladder structure without exporting source operands."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from summarize_xml import StructureError
from rungs.inventory import create_inventory


def top_count(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("top must be an integer from 1 to 20") from None
    if not 1 <= number <= 20:
        raise argparse.ArgumentTypeError("top must be an integer from 1 to 20")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventory RLL instruction/branch structure and publish sanitized shape examples.",
        epilog=(
            "Run on the original L5X, not the blank skeleton. "
            "Exit 0: complete parsing; 2: report written with unparsed rungs; 1: fatal error."
        ),
    )
    parser.add_argument("file", type=Path, help="original local XML/L5X input; read only")
    parser.add_argument(
        "-o", "--output", type=Path,
        default=Path(__file__).resolve().parents[2] / "public" / "rung-structure.json",
        help="JSON output (default: repository public/rung-structure.json)",
    )
    parser.add_argument("--top", type=top_count, default=5, help="distinct shapes per ranking, 1-20 (default: 5)")
    args = parser.parse_args()
    try:
        report = create_inventory(args.file, args.output, args.top)
    except StructureError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"File operation failed: {error.strerror or 'I/O error'}.", file=sys.stderr)
        return 1
    coverage = report["coverage"]
    label = "PASS" if report["status"] == "complete" else "PARTIAL"
    print(
        f"{label}: {coverage['parsed_rungs']}/{coverage['ladder_rungs']} ladder rungs parsed; "
        f"{coverage['unparsed_rungs']} unparsed; {coverage['distinct_shapes']} shapes."
    )
    print(
        f"Branches: {report['totals_for_parsed_rungs']['branch_groups']}; "
        f"max depth: {report['maxima_for_parsed_rungs']['max_branch_depth']}; "
        f"max height: {report['maxima_for_parsed_rungs']['height_lanes']} lanes; "
        f"max width: {report['maxima_for_parsed_rungs']['width_instructions']} instructions."
    )
    print(f"Unlisted opcode labels: {coverage['unlisted_opcode_labels']}")
    print(f"Report: {args.output}")
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
