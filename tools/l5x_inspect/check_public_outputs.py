"""Audit generated public files only; no confidential input or output writes."""
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sys
from xml.parsers import expat

import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--fixture-name', default='minimized_review')
args = parser.parse_args()
if sys.flags.optimize:
    parser.error("Run without -O so verification assertions are enabled.")
if args.fixture_name not in {'minimized', 'minimized_review'}:
    parser.error('Choose minimized or minimized_review under public/fixtures.')
repo = args.repo.resolve()
sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_values import BUILTIN_TYPES, _flatten_counts, field_role, lexical_kind, technical_values
from rungs.inventory import RUNG_TYPES, inventory_stream
from summarize_xml import build_summary, parse_structure

public = repo / "public"
fixture = public / "fixtures" / args.fixture_name
xml = (fixture / "controller_demo.L5X").read_bytes()
report = json.loads((fixture / "minimized-report.json").read_text(encoding="utf-8"))
source_counts = json.loads((public / "xml-structure-counts.json").read_text(encoding="utf-8"))
source_profiles = json.loads((public / "xml-value-profile.json").read_text(encoding="utf-8"))
source_rungs = json.loads((public / "rung-structure.json").read_text(encoding="utf-8"))
assert sha256(xml).hexdigest() == report["output_sha256"]
actual = build_summary(parse_structure(BytesIO(xml)))
assert actual["totals"] == report["output_totals"]
assert report["source_totals"] == source_counts["totals"] == source_rungs["source_totals"]

def scan(raw):
    records, stack = {}, []
    parser = expat.ParserCreate()
    def start(name, attrs):
        parent = stack[-1] if stack else None
        if parent:
            parent["counts"][name] += 1
        ordinal = parent["counts"][name] if parent else 1
        path = f"{parent['path'] if parent else ''}/{name}"
        locator = f"{parent['locator'] if parent else ''}/{name}[{ordinal}]"
        frame = {"path": path, "locator": locator, "name": name, "attrs": attrs,
                 "counts": Counter(), "text": [], "cdata": False}
        stack.append(frame)
        records[locator] = frame
    def text(value):
        if stack:
            stack[-1]["text"].append(value)
    def cdata():
        if stack:
            stack[-1]["cdata"] = True
    def end(_name):
        frame = stack.pop()
        frame["text"] = "".join(frame["text"])
        frame["has_value"] = bool(frame["text"].strip()) or frame["cdata"]
    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.CharacterDataHandler, parser.StartCdataSectionHandler = text, cdata
    parser.Parse(raw, True)
    return records

dummy_nodes = scan(xml)
skeleton_nodes = scan((public / "xml-skeleton.XML").read_bytes())
links = report["occurrence_map"]
assert len(links) == len(dummy_nodes)
assert len({x["dummy_locator"] for x in links}) == len(links)
assert len({x["source_locator"] for x in links}) == len(links)
source_order = {loc: i for i, loc in enumerate(skeleton_nodes)}
positions = [source_order[x['source_locator']] for x in links]
assert positions == sorted(positions), 'Retained source order changed'
source_to_dummy = {}
for link in links:
    target, source = dummy_nodes[link["dummy_locator"]], skeleton_nodes[link["source_locator"]]
    assert target["name"] == source["name"]
    assert set(target["attrs"]) == set(source["attrs"])
    source_to_dummy[link["source_locator"]] = link["dummy_locator"]
assert len({x["variant_id"] for x in links}) == report["selection"]["local_variants"] == report["selection"]["retained_local_variants"]

profiles = {row["path"]: row for row in source_profiles["paths"]}
source_rows = _flatten_counts(source_counts)
actual_rows = _flatten_counts(actual)
assert {row['path'] for row in report['paths']} == set(source_rows) == set(actual_rows)
observed_values = Counter(n["path"] for n in dummy_nodes.values() if n["has_value"])
for row in report["paths"]:
    path = row["path"]
    assert row["source_elements"] == source_rows[path]["count"]
    assert row["source_attributes"] == sum(source_rows[path]["attributes"].values())
    assert row["source_text_values"] == (profiles[path]["text"] or {}).get("occurrences", 0)
    assert row["retained_elements"] == actual_rows[path]["count"]
    assert row["retained_attributes"] == sum(actual_rows[path]["attributes"].values())
    assert row["retained_text_values"] == observed_values[path]
    for category in ("elements", "attributes", "text_values"):
        assert row[f"source_{category}"] == row[f"retained_{category}"] + row[f"omitted_{category}"]
assert sum(report["attribute_actions"].values()) == actual["totals"]["attribute_occurrences"]
assert sum(report["text_actions"].values()) == sum(observed_values.values())

bad_attributes = []
for locator, node in dummy_nodes.items():
    for name, value in node["attrs"].items():
        allowed = technical_values(node["name"], name)
        if node["path"].endswith("/RLLContent/Rung") and name == "Type":
            allowed = RUNG_TYPES
        if value == "" or value in allowed:
            continue
        if name == "DataType":
            valid = value.startswith("DUMMY_TYPE_")
        elif node["path"].endswith("/RLLContent/Rung") and name == "Number":
            valid = value.isascii() and value.isdigit()
        elif field_role(node["path"], name) == "identifier_or_reference":
            valid = value.startswith("DUMMY_ID_")
        else:
            valid = (
                value.startswith("DUMMY_ID_") or value == "Example value."
                or value == "2000-01-01T00:00:00" or value == "16#0001"
                or value in {"false", "true"}
                or lexical_kind(value) in {"integer_literal", "real_literal"}
            )
        if not valid:
            bad_attributes.append((locator, name))
assert not bad_attributes

import re
from rungs.syntax import Instruction, parse_rung
def check_operands(sequence):
    for item in sequence.items:
        if isinstance(item, Instruction):
            assert all(arg == "" or re.fullmatch(r"ARG_[0-9]{3,}", arg) for arg in item.arguments)
        else:
            for leg in item.legs:
                check_operands(leg)

text_policy_checked = 0
for node in dummy_nodes.values():
    value = node["text"].strip()
    if not value:
        continue
    role = field_role(node["path"], None)
    if role == "ladder_text":
        check_operands(parse_rung(value))
    elif role == "free_text":
        assert value in {"Example description A.", "Description fictive B.", "Example note C."}
    elif role == "serialized_payload" or node["name"] in {"EncryptedContent", "EncryptedSegments"}:
        assert value == "DUMMY_SERIALIZED_DATA"
    elif role == "structured_text":
        assert value == "(* DUMMY_ST_TEXT *)"
    elif node["counts"]:
        assert value == "Example mixed text."
    else:
        assert (
            value.startswith("DUMMY_ID_") or value == "Example value."
            or value in {"2000-01-01T00:00:00", "16#0001", "true", "false"}
            or lexical_kind(value) in {"integer_literal", "real_literal"}
        )
    text_policy_checked += 1

measured = inventory_stream(BytesIO(xml))
assert measured["status"] == "complete"
by_dummy = {r["locator"]: r for r in measured["rungs"]}
patterns = {p["id"]: p["shape"] for p in measured["patterns"]}
source_patterns = {p["id"]: p["shape"] for p in source_rungs["patterns"]}
original_rungs = {r["locator"]: r for r in source_rungs["rungs"]}
for record in report["rungs"]:
    original = original_rungs[record["locator"]]
    assert original == record
    target = by_dummy[source_to_dummy[record["locator"]]]
    assert target["metrics"] == record["metrics"]
    assert target["number"] == record["number"] and target["type"] == record["type"]
    assert patterns[target["pattern_id"]] == source_patterns[record["pattern_id"]]
assert len(by_dummy) == len(report['rungs']) == report["coverage"]["retained_ladder_rungs"]
assert len({r['locator'] for r in report['rungs']}) == len(by_dummy)
for anchor in report['selection']['mandatory_selections']:
    assert anchor['source_locator'] in source_to_dummy
retained_rung_locators = {r['locator'] for r in report['rungs']}
for loc in skeleton_nodes:
    match = re.search(r'/RLLContent\[[0-9]+\]/Rung\[[0-9]+\]', loc)
    if match and loc[:match.end()] in retained_rung_locators:
        assert loc in source_to_dummy
for sample in source_rungs["samples"]:
    assert sample["locator"] in source_to_dummy
for name in source_rungs["instruction_counts"]:
    assert measured["instruction_counts"].get(name, 0) > 0
assert measured["maxima_for_parsed_rungs"] == source_rungs["maxima_for_parsed_rungs"]

print(json.dumps({
    "status": "PASS", "xml_hash_matches": True,
    "source_output_occurrence_links_verified": len(links),
    "paths_accounted": len(report["paths"]), "variants_accounted": report["selection"]["local_variants"],
    "rung_shapes_and_metrics_verified": len(by_dummy),
    "ranked_source_samples_present": len(source_rungs["samples"]),
    "instruction_labels_present": len(measured["instruction_counts"]),
    "maxima": measured["maxima_for_parsed_rungs"],
    "output_attribute_policy_findings": len(bad_attributes),
    "nonblank_text_fields_policy_checked": text_policy_checked,
    "output_files_written": 0, "confidential_source_opened": False,
}, indent=2))
