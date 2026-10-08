"""Read-only sanity checks for the independently synthetic L5X fixture.

This is not the planned application or a general ladder parser.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic"


def summarize(root: ET.Element) -> dict[str, object]:
    controllers = root.findall("Controller")
    if len(controllers) != 1:
        raise ValueError("Expected exactly one Controller.")
    controller = controllers[0]
    programs = controller.findall("Programs/Program")
    controller_tags = controller.findall("Tags/Tag")
    program_tags = [tag for p in programs for tag in p.findall("Tags/Tag")]
    routines = [r for p in programs for r in p.findall("Routines/Routine")]
    rungs = [rung for r in routines for rung in r.findall("RLLContent/Rung")]
    instruction_counts: Counter[str] = Counter()
    for rung in rungs:
        text = rung.findtext("Text")
        if text is None or not text.endswith(";"):
            raise ValueError("Each synthetic RLL rung needs terminated Text.")
        # Only for this fixture's known, unquoted neutral text.
        # Future grammar must handle strings, expressions, and unknown syntax.
        instruction_counts.update(re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\(", text))
    return {
        "counts": {
            "controllers": len(controllers),
            "modules": len(controller.findall("Modules/Module")),
            "tasks": len(controller.findall("Tasks/Task")),
            "programs": len(programs),
            "user_data_types": len(controller.findall("DataTypes/DataType")),
            "aoi_definitions": len(controller.findall(
                "AddOnInstructionDefinitions/AddOnInstructionDefinition"
            )),
            "trends": len(controller.findall("Trends/Trend")),
            "encoded_regions": len(root.findall(".//EncodedData")),
            "controller_tags": len(controller_tags),
            "program_tags": len(program_tags),
            "total_tag_definitions": len(controller_tags) + len(program_tags),
            "aliases": sum(
                t.get("TagType") == "Alias" for t in controller_tags + program_tags
            ),
            "routines": len(routines),
            "rungs": len(rungs),
            "instructions": sum(instruction_counts.values()),
        },
        "routine_types": dict(Counter(r.get("Type") for r in routines)),
        "instruction_counts": dict(instruction_counts),
        "rungs_by_routine": {
            f"{p.get('Name')}/{r.get('Name')}": len(r.findall("RLLContent/Rung"))
            for p in programs for r in p.findall("Routines/Routine")
        },
        "scheduled_programs": {
            t.get("Name"): [
                p.get("Name") for p in t.findall("ScheduledPrograms/ScheduledProgram")
            ]
            for t in controller.findall("Tasks/Task")
        },
        "tag_names_by_scope": {
            "controller": [t.get("Name") for t in controller_tags],
            **{
                f"program:{p.get('Name')}": [
                    t.get("Name") for t in p.findall("Tags/Tag")
                ] for p in programs
            },
        },
    }


def check_fixture(with_l5x: bool = False) -> list[str]:
    fixture = FIXTURE_DIR / "controller_demo.L5X"
    payload = fixture.read_bytes()
    if len(payload) > 1_000_000:
        raise ValueError("The synthetic fixture exceeds its expected size limit.")
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise ValueError("DTD and entity declarations are not part of this fixture.")
    origin = json.loads((FIXTURE_DIR / "origin.json").read_text(encoding="utf-8"))
    expected = json.loads(
        (FIXTURE_DIR / "expected_inventory.json").read_text(encoding="utf-8")
    )
    if origin.get("origin") != "independently_synthetic":
        raise ValueError("Expected a declared independently synthetic origin.")
    if hashlib.sha256(payload).hexdigest() != origin["sha256"]:
        raise ValueError("Fixture bytes differ from the origin manifest.")
    root = ET.fromstring(payload)
    if root.tag != "RSLogix5000Content":
        raise ValueError("Unexpected XML root.")
    actual = summarize(root)
    failures = [
        f"{key}: expected {expected[key]!r}; got {value!r}"
        for key, value in actual.items() if value != expected[key]
    ]
    if failures:
        return failures
    if with_l5x:
        import l5x  # Optional check using the existing project's dependency.

        project = l5x.Project(str(fixture))
        names_by_scope = expected["tag_names_by_scope"]
        if set(project.controller.tags.names) != set(names_by_scope["controller"]):
            failures.append("l5x controller tag names differ.")
        for scope, names in names_by_scope.items():
            if scope.startswith("program:"):
                name = scope.split(":", 1)[1]
                if set(project.programs[name].tags.names) != set(names):
                    failures.append(f"l5x program tag names differ: {name}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check the public synthetic L5X, its hash, and expected counts.",
        epilog="Checks the fixture only; no Studio 5000 import or runtime verification.",
    )
    parser.add_argument(
        "--with-l5x", action="store_true",
        help="also load with the installed l5x package and compare tag names",
    )
    args = parser.parse_args()
    try:
        failures = check_fixture(args.with_l5x)
    except (OSError, ValueError, ET.ParseError, ImportError, KeyError, AttributeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    suffix = " and l5x tag access" if args.with_l5x else ""
    print(f"PASS: fixture hash, XML, counts, scopes, schedules{suffix}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
