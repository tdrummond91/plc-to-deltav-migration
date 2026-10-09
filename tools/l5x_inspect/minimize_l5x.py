"""CLI for the first minimized, dummy-valued structural L5X fixture."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from dummy.build import create_fixture
from summarize_xml import StructureError


def sample_count(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Use an integer from 1 to 20.") from None
    if not 1 <= number <= 20:
        raise argparse.ArgumentTypeError("Use an integer from 1 to 20.")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a minimized XML/L5X example with dummy values and a coverage report.",
        epilog="Use the original local export. Output is for structural parser development; controller import is not validated.",
    )
    parser.add_argument("file", type=Path, help="Original local export, opened read-only.")
    parser.add_argument("--output-dir", type=Path,
                        default=Path(__file__).resolve().parents[2] / "public" / "fixtures" / "minimized",
                        help="Directory for controller_demo.L5X and minimized-report.json.")
    parser.add_argument("--per-variant", type=sample_count, default=5,
                        help="Examples per local XML variant under each retained parent (default: 5); mandatory coverage and full selected rungs may exceed this.")
    parser.add_argument("--top", type=sample_count, default=5,
                        help="Distinct ladder shapes per ranking (default: 5).")
    parser.add_argument("--seed", type=int, default=0,
                        help="Seed for repeatable invented values (default: 0).")
    args = parser.parse_args()
    try:
        report = create_fixture(args.file, args.output_dir, args.per_variant, args.top, args.seed)
    except StructureError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"File operation failed: {error.strerror or 'I/O error'}.", file=sys.stderr)
        return 1
    coverage = report["coverage"]
    print(
        f"PASS: {coverage['retained_elements']}/{coverage['source_elements']} elements retained; "
        f"{coverage['retained_paths']}/{coverage['source_paths']} paths; "
        f"{coverage['retained_ladder_rungs']}/{coverage['source_ladder_rungs']} ladder rungs."
    )
    print(f"Variants: {report['selection']['retained_local_variants']}/{report['selection']['local_variants']}; "
          f"instruction labels: {len(report['selection']['instruction_labels_represented'])}.")
    print(f"Payload/text replacements requiring later work: {report['unsupported_content']}")
    print(f"Fixture: {args.output_dir / 'controller_demo.L5X'}")
    print(f"Report: {args.output_dir / 'minimized-report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
