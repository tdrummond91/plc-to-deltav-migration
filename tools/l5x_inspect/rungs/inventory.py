"""Read local XML and publish only rung counts, shapes, and sanitized samples."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import BinaryIO
from xml.parsers import expat

from summarize_xml import CHUNK_SIZE, MAX_DEPTH, StructureError, _write_atomic, build_summary, parse_structure
from .syntax import MAX_TEXT, OpcodeLabels, RungSyntaxError, measure, parse_rung, public_forms, render_sample

RUNG_TYPES = frozenset({"N", "I", "D", "IR", "rR", "R", "rI", "rN", "e", "er", "d"})
SUM_METRICS = (
    "instruction_calls", "argument_slots", "nonempty_argument_fields",
    "expression_instruction_calls", "branch_groups", "branch_legs", "empty_branch_legs",
)
MAX_METRICS = ("max_branch_depth", "max_legs_in_group", "height_lanes", "width_instructions")


@dataclass
class Rung:
    record: dict
    texts: list[str] = field(default_factory=list, repr=False)
    text_nested_xml: bool = False
    text_too_long: bool = False


@dataclass
class Frame:
    name: str
    locator: str
    children: Counter = field(default_factory=Counter)
    rung: Rung | None = None
    text_parts: list[str] | None = field(default=None, repr=False)
    text_size: int = 0
    text_owner: Rung | None = None


def inventory_stream(source: BinaryIO, top: int = 5) -> dict:
    """Read one seekable local export; rung syntax errors produce explicit partial coverage."""
    if not 1 <= top <= 20:
        raise StructureError("top must be between 1 and 20.")
    original = build_summary(parse_structure(source))
    source.seek(0)
    stack: list[Frame] = []
    records: list[dict] = []
    patterns: list[dict] = []
    by_shape: dict[str, dict] = {}
    examples: dict[str, dict] = {}
    labels = OpcodeLabels()
    opcodes: Counter = Counter()
    failures: Counter = Counter()
    metadata_findings: Counter = Counter()
    sums = Counter({key: 0 for key in SUM_METRICS})
    maxima = {key: 0 for key in MAX_METRICS}
    seen_elements = 0
    seen_attributes = 0
    seen_rungs = 0
    rung_texts = 0
    ignored_rungs = 0
    parsed = 0
    empty = 0

    def fail(record: dict, code: str, offset: int | None = None) -> None:
        record.update({"status": "unparsed", "error": {"code": code}})
        if offset is not None:
            record["error"]["character_offset"] = offset
        failures[code] += 1

    def finish_rung(rung: Rung) -> None:
        nonlocal parsed, empty
        record = rung.record
        if rung.text_too_long:
            fail(record, "text_limit")
            return
        if rung.text_nested_xml:
            fail(record, "nested_xml_in_rung_text")
            return
        if len(rung.texts) != 1:
            fail(record, "missing_text" if not rung.texts else "multiple_text_elements")
            return
        try:
            tree = parse_rung(rung.texts[0])
        except RungSyntaxError as error:
            fail(record, error.code, error.offset)
            return
        metrics = measure(tree)
        shape, sample, counts = public_forms(tree, labels)
        key = json.dumps(shape, separators=(",", ":"))
        if key not in by_shape:
            pattern_id = f"pattern_{len(patterns) + 1:05d}"
            pattern = {
                "id": pattern_id, "count": 0, "metrics": metrics,
                "shape": shape, "rung_ids": [],
            }
            by_shape[key] = pattern
            patterns.append(pattern)
            examples[pattern_id] = {
                "pattern_id": pattern_id, "representative_rung_id": record["id"],
                "number": record["number"], "type": record["type"],
                "locator": record["locator"], "tree": sample,
                "neutral_text": render_sample(sample),
            }
        pattern = by_shape[key]
        pattern["count"] += 1
        pattern["rung_ids"].append(record["id"])
        record.update({"status": "parsed", "pattern_id": pattern["id"], "metrics": metrics})
        parsed += 1
        empty += int(metrics["instruction_calls"] == 0)
        opcodes.update(counts)
        for name in SUM_METRICS:
            sums[name] += metrics[name]
        for name in MAX_METRICS:
            maxima[name] = max(maxima[name], metrics[name])

    def start(expanded: str, attributes: dict[str, str]) -> None:
        nonlocal seen_elements, seen_attributes, seen_rungs, ignored_rungs, rung_texts
        if len(stack) >= MAX_DEPTH:
            raise StructureError("XML exceeds the supported depth.")
        name = expanded.rsplit("}", 1)[-1]
        parent = stack[-1] if stack else None
        if parent:
            parent.children[name] += 1
            if parent.text_owner is not None:
                parent.text_owner.text_nested_xml = True
        ordinal = parent.children[name] if parent else 1
        locator = f"{parent.locator if parent else ''}/{name}[{ordinal}]"
        frame = Frame(name, locator)
        seen_elements += 1
        seen_attributes += len(attributes)
        if name == "Rung":
            seen_rungs += 1
            if parent and parent.name == "RLLContent":
                attrs = {key.rsplit("}", 1)[-1]: value for key, value in attributes.items()}
                number, kind = attrs.get("Number"), attrs.get("Type")
                problems = []
                if number is not None and not re.fullmatch(r"[0-9]{1,20}", number):
                    number = "<withheld>"
                    problems.append("rung_number_not_numeric")
                if kind is not None and kind not in RUNG_TYPES:
                    kind = "<withheld>"
                    problems.append("rung_type_not_allowlisted")
                if number is None:
                    problems.append("rung_number_missing")
                if kind is None:
                    problems.append("rung_type_missing")
                metadata_findings.update(problems)
                record = {
                    "id": f"rung_{len(records) + 1:06d}", "locator": locator,
                    "number": number, "type": kind, "metadata_findings": problems,
                }
                records.append(record)
                frame.rung = Rung(record)
            else:
                ignored_rungs += 1
        if name == "Text" and parent and parent.rung is not None:
            frame.text_parts = []
            frame.text_owner = parent.rung
            rung_texts += 1
        stack.append(frame)

    def text(value: str) -> None:
        if stack and stack[-1].text_parts is not None:
            frame = stack[-1]
            frame.text_size += len(value)
            if frame.text_size > MAX_TEXT:
                frame.text_owner.text_too_long = True
                frame.text_parts.clear()
            elif not frame.text_owner.text_too_long:
                frame.text_parts.append(value)

    def end(_expanded: str) -> None:
        frame = stack.pop()
        if frame.text_parts is not None:
            frame.text_owner.texts.append("".join(frame.text_parts))
        if frame.rung is not None:
            finish_rung(frame.rung)

    def reject(*_args: object) -> None:
        raise StructureError("DTD and external/entity declarations are not allowed.")

    parser = expat.ParserCreate(namespace_separator="}")
    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.CharacterDataHandler = text
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

    if (seen_elements != original["totals"]["element_occurrences"]
            or seen_attributes != original["totals"]["attribute_occurrences"]
            or seen_rungs != original["counts_by_element_name"].get("Rung", 0)):
        raise StructureError("Input counts changed between preflight and rung inventory.")

    # Rank distinct shapes, so repeated copies do not crowd out diverse examples.
    # Stable sorting preserves first source occurrence when scores tie.
    rankings = {
        "tallest": [p["id"] for p in sorted(patterns, key=lambda p: p["metrics"]["height_lanes"], reverse=True)[:top]],
        "widest": [p["id"] for p in sorted(patterns, key=lambda p: p["metrics"]["width_instructions"], reverse=True)[:top]],
        "deepest": [p["id"] for p in sorted(patterns, key=lambda p: p["metrics"]["max_branch_depth"], reverse=True)[:top]],
        "most_frequent": [p["id"] for p in sorted(patterns, key=lambda p: p["count"], reverse=True)[:top]],
    }
    selected: dict[str, list[str]] = {}
    for ranking, ids in rankings.items():
        for pattern_id in ids:
            selected.setdefault(pattern_id, []).append(ranking)
    samples = [{**examples[pid], "selected_for": reasons} for pid, reasons in selected.items()]
    failed = len(records) - parsed
    if parsed + failed + ignored_rungs != seen_rungs or sum(p["count"] for p in patterns) != parsed:
        raise StructureError("Internal rung accounting mismatch.")
    return {
        "schema_version": 1, "stage": "rung_structure", "parser_version": 1,
        "status": "complete" if failed == 0 else "partial",
        "source_totals": original["totals"],
        "coverage": {
            "xml_rungs": seen_rungs, "ladder_rungs": len(records),
            "parsed_rungs": parsed, "unparsed_rungs": failed,
            "parsed_rungs_without_instructions": empty,
            "ignored_non_ladder_rungs": ignored_rungs, "rung_text_elements": rung_texts,
            "parse_error_counts": dict(failures), "metadata_findings": dict(metadata_findings),
            "distinct_shapes": len(patterns), "unlisted_opcode_labels": labels.unknown_count,
        },
        "metric_definitions": {
            "instruction_calls": "Outer ladder calls only; nested functions inside operands are opaque.",
            "branch_groups": "Square-bracket branch groups outside instruction argument lists.",
            "branch_legs": "Sum of the legs in all branch groups; not expanded end-to-end paths.",
            "max_branch_depth": "Maximum nesting of branch groups; unbranched is zero.",
            "height_lanes": "Instruction/empty sequence height 1; sequence max; branch sum of leg heights.",
            "width_instructions": "Instruction width 1; sequence sum; branch max of leg widths. Wiring width excluded.",
            "expression_instruction_calls": "CMP, CPT, FAL and FSC calls only; not a count of inner mathematical operations.",
        },
        "policies": {
            "metric_scope": "successfully_parsed_ladder_rungs_only",
            "shape_identity": "Instruction labels, arity, empty argument positions, and ordered branch topology. Operand values/reuse omitted.",
            "sample_operands": "Whole arguments replaced. Identical stripped argument text shares a placeholder within one sample only.",
            "opcode_labels": "Explicit public list; other names become run-local UNLISTED_OP labels, not assertions of custom instructions.",
            "source_identity": "Ordinal XML locators plus numeric rung Number and approved rung Type; no source filename/hash.",
            "rankings": "Top distinct shapes among parsed rungs; ties use first source occurrence.",
            "limits": "Structure parsing only; no instruction arity/type validation, execution graph, or import validity.",
        },
        "totals_for_parsed_rungs": dict(sums), "maxima_for_parsed_rungs": maxima,
        "instruction_counts": dict(opcodes), "rankings": rankings,
        "patterns": patterns, "samples": samples, "rungs": records,
    }


def create_inventory(source: Path, output: Path, top: int = 5) -> dict:
    source, output = source.resolve(), output.resolve()
    if source == output or (
        source.exists() and output.exists() and source.samefile(output)
    ):
        raise StructureError("Input and output must be different files.")
    with source.open("rb") as stream:
        report = inventory_stream(stream, top)
    _write_atomic(output, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report
