"""Stage 3: local value profiling with restricted public values and routine coverage."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys
from typing import BinaryIO
from xml.parsers import expat

from summarize_xml import (
    CHUNK_SIZE, MAX_DEPTH, StructureError, _write_atomic, build_summary, parse_structure,
)

MAX_DIRECT_TEXT = 16 * 1024 * 1024
MAX_UNIQUE_VALUES = 1_000_000
# This is an export permission list, not a complete list of supported Logix types.
BUILTIN_TYPES = frozenset({
    "BOOL", "SINT", "INT", "DINT", "LINT", "REAL",
    "STRING", "TIMER", "COUNTER", "CONTROL", "MESSAGE", "ALARM_ANALOG", "ALARM_DIGITAL",
})
ROUTINE_CONTENT = {
    "RLL": "RLLContent", "FBD": "FBDContent", "SFC": "SFCContent",
    "ST": "STContent", "Sequence": "SEQContent",
}
CONTENT_NAMES = frozenset(ROUTINE_CONTENT.values())
PROTECTION_NAMES = frozenset({"EncodedData", "EncryptedContent", "EncryptedSegments"})
ENUM_FIELDS = {
    "TagType": frozenset({"Base", "Alias", "Produced", "Consumed"}),
    "Radix": frozenset({"Binary", "Octal", "Decimal", "Hex", "ASCII", "Ascii", "Exponential", "Float"}),
    "ExternalAccess": frozenset({"None", "Read Only", "Read/Write"}),
}
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ].*)?")
ENGLISH_DATE = re.compile(
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4}"
)
REAL = re.compile(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def technical_values(element: str, attribute: str) -> frozenset[str]:
    if attribute == "DataType":
        return BUILTIN_TYPES
    if element == "Routine" and attribute == "Type":
        return frozenset(ROUTINE_CONTENT)
    if element == "Task" and attribute == "Type":
        return frozenset({"CONTINUOUS", "PERIODIC", "EVENT", "Continuous", "Periodic", "Event"})
    if element in {"Data", "DefaultData", "ForceData"} and attribute == "Format":
        return frozenset({"L5K", "Decorated", "Message", "String", "Alarm", "HMIBC"})
    return ENUM_FIELDS.get(attribute, frozenset())


def lexical_kind(value: str) -> str:
    """Describe syntax only. This does not infer the PLC datatype or validate dates."""
    value = value.strip()
    if not value:
        return "empty"
    if value.lower() in {"true", "false"}:
        return "boolean_literal"
    if re.fullmatch(r"[+-]?\d+", value):
        return "integer_literal"
    radix = re.fullmatch(r"([+-]?)(2|8|16)#([0-9A-Fa-f_]+)", value)
    if radix:
        try:
            int(radix[3].replace("_", ""), int(radix[2]))
            return "radix_integer_literal"
        except ValueError:
            pass
    if REAL.fullmatch(value):
        return "real_literal"
    if ISO_DATE.fullmatch(value) or ENGLISH_DATE.fullmatch(value):
        return "date_like"
    if IDENTIFIER.fullmatch(value):
        return "identifier_like"
    return "string"


def field_role(path: str, attribute: str | None) -> str:
    if attribute == "DataType":
        return "datatype_name"
    if attribute in {"Name", "AliasFor", "MainRoutineName", "DestinationTag", "RemoteElement", "LocalElement"}:
        return "identifier_or_reference"
    if attribute is not None:
        return "attribute_value"
    if path.endswith("/RLLContent/Rung/Text"):
        return "ladder_text"
    if path.endswith("/STContent/Line"):
        return "structured_text"
    if path.rsplit("/", 1)[-1] in {"Description", "Comment", "RevisionNote", "AdditionalHelpText"}:
        return "free_text"
    if path.rsplit("/", 1)[-1] in {"Data", "DefaultData", "ForceData", "EncodedData"}:
        return "serialized_payload"
    return "element_text"


@dataclass
class ValueProfile:
    allowed: frozenset[str]
    count: int = 0
    # Actual source strings remain private in process memory, never in to_json().
    unique: set[str] = field(default_factory=set, repr=False)
    kinds: Counter = field(default_factory=Counter)
    approved: Counter = field(default_factory=Counter)
    declared: Counter = field(default_factory=Counter)

    def add(self, value: str, declared_type: str | None = None) -> None:
        self.count += 1
        self.unique.add(value)
        self.kinds[lexical_kind(value)] += 1
        if value in self.allowed:
            self.approved[value] += 1
        if declared_type is not None:
            key = declared_type if declared_type in BUILTIN_TYPES else "<withheld>"
            self.declared[key] += 1

    def to_json(self, role: str) -> dict:
        examples = {
            "identifier_or_reference": ["DUMMY_ID_001", "DUMMY_ID_002", "DUMMY_ID_003"],
            "datatype_name": ["DUMMY_TYPE_A", "DUMMY_TYPE_B", "DUMMY_TYPE_C"],
            "free_text": ["Description fictive A.", "Example description B.", "Example note C."],
            "ladder_text": ["DUMMY_LADDER_TEXT"],
            "structured_text": ["DUMMY_ST_TEXT"],
            "serialized_payload": ["DUMMY_SERIALIZED_DATA"],
        }.get(role)
        if examples is None:
            synthetic = {
                "empty": "", "boolean_literal": "false", "integer_literal": "123",
                "radix_integer_literal": "16#00AF", "real_literal": "12.5",
                "date_like": "2000-01-01T00:00:00", "identifier_like": "DUMMY_ID_001",
                "string": "Example text.",
            }
            examples = [synthetic[kind] for kind in self.kinds][:3]
        return {
            "occurrences": self.count,
            "unique_value_count": len(self.unique),
            "lexical_type_counts": dict(self.kinds),
            "role": role,
            "technical_enum_policy": "explicit_literal_allowlist" if self.allowed else "no_values_published",
            "technical_value_counts": dict(self.approved),
            "withheld_occurrences": self.count - sum(self.approved.values()),
            "withheld_unique_value_count": len(self.unique) - len(self.approved),
            "repeated_small_value_set": 1 < len(self.unique) <= 12 and self.count >= 3 * len(self.unique),
            "declared_datatypes_on_same_element": dict(self.declared),
            "synthetic_examples": examples,
            "examples_origin": "invented_not_source_samples",
        }


@dataclass
class PathProfile:
    count: int = 0
    attributes: dict[str, ValueProfile] = field(default_factory=dict)
    text: ValueProfile = field(default_factory=lambda: ValueProfile(frozenset()))
    with_text: int = 0
    with_cdata: int = 0


@dataclass
class Frame:
    name: str
    path: str
    locator: str
    declared_type: str | None
    direct_text: list[str] = field(default_factory=list)
    text_size: int = 0
    cdata: bool = False
    children: Counter = field(default_factory=Counter)
    routine: dict | None = None


def _flatten_counts(report: dict) -> dict:
    rows = {}
    def visit(node: dict, parent: str) -> None:
        path = f"{parent}/{node['element']}"
        rows[path] = {
            "count": node["count"],
            "attributes": {key: value["count"] for key, value in node["attributes"].items()},
            "text": node["elements_with_text"],
            "cdata": node["elements_with_cdata"],
        }
        for child in node["children"]:
            visit(child, path)
    visit(report["root"], "")
    return rows


def profile_stream(source: BinaryIO) -> dict:
    """Profile a seekable XML stream; published fields exclude arbitrary values."""
    expected = build_summary(parse_structure(source))
    source.seek(0)
    paths: dict[str, PathProfile] = {}
    stack: list[Frame] = []
    routines: list[dict] = []
    unique_total = 0
    comments = 0
    processing_instructions = 0

    def add_value(stats: ValueProfile, value: str, declared: str | None = None) -> None:
        nonlocal unique_total
        previous = len(stats.unique)
        stats.add(value, declared)
        unique_total += len(stats.unique) - previous
        if unique_total > MAX_UNIQUE_VALUES:
            raise StructureError("Value profiling exceeds the distinct-value memory limit.")

    def start(expanded: str, attributes: dict[str, str]) -> None:
        if len(stack) >= MAX_DEPTH:
            raise StructureError("XML exceeds the supported nesting depth.")
        name = expanded.rsplit("}", 1)[-1]
        attrs = {key.rsplit("}", 1)[-1]: value for key, value in attributes.items()}
        parent = stack[-1] if stack else None
        path = f"{parent.path if parent else ''}/{name}"
        if parent:
            parent.children[name] += 1
        ordinal = parent.children[name] if parent else 1
        locator = f"{parent.locator if parent else ''}/{name}[{ordinal}]"
        stats = paths.setdefault(path, PathProfile())
        stats.count += 1
        declared = attrs.get("DataType")
        for attribute, value in attrs.items():
            entry = stats.attributes.setdefault(attribute, ValueProfile(technical_values(name, attribute)))
            context_type = declared if attribute in {"Value", "ForceValue"} else None
            add_value(entry, value, context_type)
        frame = Frame(name, path, locator, declared)
        if name == "Routine":
            raw_type = attrs.get("Type")
            type_label = raw_type if raw_type in ROUTINE_CONTENT else (
                "<missing>" if raw_type is None else "<withheld>"
            )
            frame.routine = {
                "ordinal": len(routines) + 1, "locator": locator, "routine_type": type_label,
            }
            routines.append(frame.routine)
        stack.append(frame)

    def text(value: str) -> None:
        if stack:
            frame = stack[-1]
            frame.text_size += len(value)
            if frame.text_size > MAX_DIRECT_TEXT:
                raise StructureError("An element exceeds the direct-text memory limit.")
            frame.direct_text.append(value)

    def cdata() -> None:
        if stack:
            stack[-1].cdata = True

    def end(_expanded: str) -> None:
        frame = stack.pop()
        stats = paths[frame.path]
        value = "".join(frame.direct_text)
        nonblank = bool(value.strip())
        stats.with_text += int(nonblank)
        stats.with_cdata += int(frame.cdata)
        # Ignore container indentation. Empty CDATA is an explicit empty text value.
        if nonblank or frame.cdata:
            add_value(stats.text, value, frame.declared_type)
        if frame.routine is not None:
            children = dict(frame.children)
            contents = {name: count for name, count in children.items() if name in CONTENT_NAMES}
            issues = []
            kind = frame.routine["routine_type"]
            expected_content = ROUTINE_CONTENT.get(kind)
            if kind == "<missing>":
                issues.append("type_missing")
            elif kind == "<withheld>":
                issues.append("type_not_allowlisted")
            if not contents:
                issues.append("no_recognized_content")
            if sum(contents.values()) > 1:
                issues.append("multiple_content_blocks")
            if expected_content and contents and set(contents) != {expected_content}:
                issues.append("type_content_mismatch")
            if any(name in PROTECTION_NAMES for name in children):
                issues.append("protection_marker_present")
            frame.routine.update({
                "direct_child_counts": children, "content_counts": contents, "issues": issues,
            })

    def comment(_value: str) -> None:
        nonlocal comments
        comments += 1

    def pi(_target: str, _value: str) -> None:
        nonlocal processing_instructions
        processing_instructions += 1

    def reject(*_args: object) -> None:
        raise StructureError("DTD and external/entity declarations are not allowed.")

    parser = expat.ParserCreate(namespace_separator="}")
    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.CharacterDataHandler, parser.StartCdataSectionHandler = text, cdata
    parser.CommentHandler, parser.ProcessingInstructionHandler = comment, pi
    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    try:
        for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
            parser.Parse(chunk, False)
        parser.Parse(b"", True)
    except expat.ExpatError as error:
        raise StructureError(
            f"Malformed XML at line {error.lineno}, column {error.offset}."
        ) from None
    except LookupError:
        raise StructureError("Unsupported XML encoding.") from None

    observed = {
        path: {"count": item.count, "attributes": {key: val.count for key, val in item.attributes.items()},
               "text": item.with_text, "cdata": item.with_cdata}
        for path, item in paths.items()
    }
    if observed != _flatten_counts(expected):
        raise StructureError("Input structure changed between preflight and profiling.")

    routine_types = Counter(item["routine_type"] for item in routines)
    routine_issues = Counter(issue for item in routines for issue in item["issues"])
    rows = []
    for path, item in paths.items():
        attributes = {}
        for name, entry in item.attributes.items():
            attributes[name] = {
                **entry.to_json(field_role(path, name)),
                "missing_on_elements": item.count - entry.count,
            }
        rows.append({
            "path": path, "element_occurrences": item.count, "attributes": attributes,
            "text": item.text.to_json(field_role(path, None)) if item.text.count else None,
        })
    return {
        "schema_version": 1, "stage": "value_profile", "enum_policy_version": 1,
        "count_scope": "complete_input", "source_totals": expected["totals"],
        "coverage": {
            "element_paths_profiled": len(paths),
            "attribute_occurrences_profiled": expected["totals"]["attribute_occurrences"],
            "text_values_profiled": sum(item.text.count for item in paths.values()),
            "comments_ignored": comments, "processing_instructions_ignored": processing_instructions,
            "routine_records_profiled": len(routines),
            "opaque_encoded_elements": expected["counts_by_element_name"].get("EncodedData", 0),
        },
        "policies": {
            "unique_values": "exact_parsed_strings_per_field; no hashes exported",
            "text": "direct text only; indentation-only text omitted unless CDATA is present",
            "lexical_types": "syntax categories; date_like is not calendar validation",
            "declared_types": "same-element DataType only; no parent or tag resolution",
            "small_value_set": "heuristic only; never authorizes publication",
            "routine_locators": "ordinal XML paths for this input; not stable across reordered exports",
            "not_analyzed": ["ladder_instructions", "branch_metrics", "reference_resolution", "PLC_semantics"],
        },
        "routine_coverage": {
            "count": len(routines), "type_counts": dict(routine_types),
            "issue_counts": dict(routine_issues), "records": routines,
        },
        "paths": rows,
    }


def create_profile(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if source == output or (
        source.exists() and output.exists() and source.samefile(output)
    ):
        raise StructureError("Input and output must be different files.")
    with source.open("rb") as stream:
        report = profile_stream(stream)
    _write_atomic(output, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Profile XML attributes/text without publishing arbitrary source values.",
        epilog="Run on the original L5X, not the blank skeleton. All examples are invented.",
    )
    parser.add_argument("file", type=Path, help="original local XML/L5X input; read only")
    parser.add_argument(
        "-o", "--output", type=Path,
        default=Path(__file__).resolve().parents[2] / "public" / "xml-value-profile.json",
        help="JSON output (default: repository public/xml-value-profile.json)",
    )
    args = parser.parse_args()
    try:
        report = create_profile(args.file, args.output)
    except StructureError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"File operation failed: {error.strerror or 'I/O error'}.", file=sys.stderr)
        return 1
    coverage = report["coverage"]
    print(
        f"PASS: {coverage['element_paths_profiled']} paths; "
        f"{coverage['attribute_occurrences_profiled']} attribute values; "
        f"{coverage['routine_records_profiled']} routines."
    )
    print(f"Routine types: {json.dumps(report['routine_coverage']['type_counts'])}")
    print(f"Routine findings: {json.dumps(report['routine_coverage']['issue_counts'])}")
    print(f"Profile: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
