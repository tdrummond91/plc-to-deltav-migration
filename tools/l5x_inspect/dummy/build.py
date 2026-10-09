"""Create a minimized structural fixture and a traceable coverage report."""
from __future__ import annotations

from collections import Counter
import hashlib
from io import BytesIO
import json
from pathlib import Path
from typing import BinaryIO
from xml.sax.saxutils import escape, quoteattr

from rungs.inventory import inventory_stream
from summarize_xml import StructureError, _write_atomic, build_summary, parse_structure
from .model import Node, sanitized_tree
from .selection import select_nodes


def serialize(nodes: list[Node], keep: set[int]) -> tuple[str, list[dict]]:
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<!-- Synthetic structural example; not validated for controller import. -->']
    links: list[dict] = []

    def emit(index: int, parent_locator: str, ordinal: int, depth: int) -> None:
        node = nodes[index]
        locator = f"{parent_locator}/{node.name}[{ordinal}]"
        links.append({"dummy_locator": locator, "source_locator": node.locator,
                      "variant_id": node.variant})
        indent = "  " * depth
        attrs = "".join(f" {key}={quoteattr(value)}" for key, value in node.attributes.items())
        children = [i for i in node.children if i in keep]
        opening = f"{indent}<{node.name}{attrs}>"
        text = node.text
        if node.cdata:
            value = "<![CDATA[" + text.replace("]]>", "]]]]><![CDATA[>") + "]]>"
        else:
            value = escape(text)
        if not children:
            lines.append(opening + value + f"</{node.name}>")
            return
        lines.append(opening)
        if value:
            lines.append(f"{indent}  {value}")
        ordinals: Counter = Counter()
        for child in children:
            ordinals[nodes[child].name] += 1
            emit(child, locator, ordinals[nodes[child].name], depth + 1)
        lines.append(f"{indent}</{node.name}>")
    emit(0, "", 1, 0)
    return "\n".join(lines) + "\n", links


def build_fixture(source: BinaryIO, per_variant: int = 5, top: int = 5, seed: int = 0) -> tuple[str, dict]:
    if not 1 <= per_variant <= 20 or not 1 <= top <= 20:
        raise StructureError("Sampling limits must be between 1 and 20.")
    source.seek(0)
    rung_report = inventory_stream(source, top=top)
    if rung_report["status"] != "complete" or rung_report["coverage"]["metadata_findings"]:
        raise StructureError("Resolve partial rung coverage or metadata findings before generating a fixture.")
    source.seek(0)
    nodes, counts = sanitized_tree(source, rung_report, seed=seed)
    keep, selection = select_nodes(nodes, rung_report, per_variant)
    xml, links = serialize(nodes, keep)
    paths: dict[str, dict] = {}
    attr_actions: Counter = Counter()
    text_actions: Counter = Counter()
    retained_rungs: list[str] = []
    for index, node in enumerate(nodes):
        kept = index in keep
        row = paths.setdefault(node.path, {
            "path": node.path, "source_elements": 0, "retained_elements": 0, "omitted_elements": 0,
            "source_attributes": 0, "retained_attributes": 0, "omitted_attributes": 0,
            "source_text_values": 0, "retained_text_values": 0, "omitted_text_values": 0,
            "retained_attribute_actions": {}, "retained_text_actions": {},
        })
        state = "retained" if kept else "omitted"
        row["source_elements"] += 1
        row[f"{state}_elements"] += 1
        row["source_attributes"] += len(node.attributes)
        row[f"{state}_attributes"] += len(node.attributes)
        has_text = node.source_text or node.cdata
        row["source_text_values"] += int(has_text)
        row[f"{state}_text_values"] += int(has_text)
        if kept:
            for name, action in node.attribute_actions.items():
                action_counts = row["retained_attribute_actions"].setdefault(name, {})
                action_counts[action] = action_counts.get(action, 0) + 1
                attr_actions[action] += 1
            if has_text:
                row["retained_text_actions"][node.text_action] = row["retained_text_actions"].get(node.text_action, 0) + 1
                text_actions[node.text_action] += 1
            if node.path.endswith("/RLLContent/Rung"):
                retained_rungs.append(node.locator)
    actual = build_summary(parse_structure(BytesIO(xml.encode("utf-8"))))
    expected_attributes = sum(len(nodes[i].attributes) for i in keep)
    if (actual["totals"]["element_occurrences"] != len(keep)
            or actual["totals"]["attribute_occurrences"] != expected_attributes
            or actual["totals"]["distinct_element_paths"] != len(paths)
            or selection["local_variants"] != selection["retained_local_variants"]):
        raise StructureError("Fixture output structure/coverage verification failed.")
    selected = set(retained_rungs)
    rung_records = [r for r in rung_report["rungs"] if r["locator"] in selected]
    report = {
        "schema_version": 2, "stage": "minimized_fixture", "policy_version": 2, "seed": seed,
        "status": "structural_fixture_verified",
        "output_sha256": hashlib.sha256(xml.encode("utf-8")).hexdigest(),
        "source_totals": rung_report["source_totals"],
        "output_totals": actual["totals"],
        "coverage": {
            "source_elements": len(nodes), "retained_elements": len(keep),
            "omitted_elements": len(nodes) - len(keep), "source_paths": len(paths),
            "retained_paths": actual["totals"]["distinct_element_paths"],
            "source_ladder_rungs": len(rung_report["rungs"]), "retained_ladder_rungs": len(rung_records),
            "retained_ladder_shapes": len({r["pattern_id"] for r in rung_records}),
            "source_ladder_shapes": len(rung_report["patterns"]),
            "comments_ignored": counts.get("comments_ignored", 0),
            "processing_instructions_ignored": counts.get("processing_instructions_ignored", 0),
        },
        "selection": selection,
        "attribute_actions": dict(attr_actions), "text_actions": dict(text_actions),
        "unsupported_content": {
            action: count for action, count in text_actions.items()
            if action in {"opaque_payload_replaced", "structured_text_replaced", "mixed_text_replaced"}
        },
        "policies": {
            "sampling": "First N occurrences of each local variant per retained parent, plus first occurrence of every global local variant, ranked rungs and instruction representatives; ancestors included. Complete selected rung subtrees bypass the quota.",
            "variant": "XML path, attribute names/categories, approved technical values or masked datatype identity, collapsed ordered child-name runs, text/CDATAness and text action. Not complete subtree equivalence.",
            "ladder": "Retained rung subtrees are complete; whole operands replaced using Stage 4. Number/approved Type retained.",
            "identifiers": "Exact whole identifier/reference strings share dummy IDs in this run; no scope/member/reference resolution. Ladder ARG IDs are separate per rung.",
            "numbers": "Invented small values; dates fixed to 2000-01-01. Only approved technical literals and numeric rung Number are retained.",
            "datatypes": "Stage 3 approved types retained; other names consistently masked. Not all unknown names are user-defined.",
            "payloads": "Non-ladder serialized text and ST text replaced by explicit placeholders. Not translated or interpreted.",
            "mappings": "Public source/dummy ordinal XML locators only. Private string replacement dictionaries exist only in process memory.",
            "publication": "XML then report; files independently atomic. Compare output_sha256 before using a pair after any write error.",
        },
        "limitations": [
            "Structural fixture only; controller import and execution semantics are not validated.",
            "Sampled SFC graphs, task references, tag/member links, array dimensions/indices and serialized payloads are not repaired for semantic coherence.",
            "Lexical replacement preserves broad value categories, not every source formatting rule.",
            "Equal shapes do not imply equal behavior. Ordinal locators apply only to this export ordering.",
            "Namespace URIs, original comments/PIs and CDATA segmentation are not retained.",
            "Original XML element and attribute names remain present, as in the reviewed skeleton.",
        ],
        "rungs": rung_records, "paths": list(paths.values()), "occurrence_map": links,
    }
    return xml, report


def create_fixture(source: Path, output_dir: Path, per_variant: int = 5,
                   top: int = 5, seed: int = 0) -> dict:
    source, output_dir = source.resolve(), output_dir.resolve()
    xml_path = output_dir / "controller_demo.L5X"
    report_path = output_dir / "minimized-report.json"
    for output in (xml_path, report_path):
        if source == output.resolve() or (
            source.exists() and output.exists() and source.samefile(output)
        ):
            raise StructureError("Input and output must be different files.")
    if xml_path.exists() and report_path.exists() and xml_path.samefile(report_path):
        raise StructureError("XML and report outputs must be different files.")
    with source.open("rb") as stream:
        xml, report = build_fixture(stream, per_variant, top, seed)
    _write_atomic(xml_path, xml)
    _write_atomic(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report
