"""Read and sanitize XML in memory; no source values are written."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import random
import re
from typing import BinaryIO
from xml.parsers import expat

from profile_values import MAX_DIRECT_TEXT, field_role, lexical_kind, technical_values
from rungs.inventory import RUNG_TYPES
from rungs.syntax import OpcodeLabels, parse_rung, public_forms, render_sample
from summarize_xml import CHUNK_SIZE, MAX_DEPTH, StructureError

MAX_NODES = 500_000


@dataclass
class Node:
    name: str
    path: str
    locator: str
    parent: int | None
    attributes: dict[str, str]
    attribute_actions: dict[str, str]
    attribute_classes: tuple
    children: list[int] = field(default_factory=list)
    text: str = ""
    text_action: str = "absent"
    cdata: bool = False
    source_text: bool = False
    variant: int = 0


class Replacements:
    def __init__(self, seed: int) -> None:
        self.random = random.Random(seed)
        self.identifiers: dict[str, str] = {}
        self.types: dict[str, str] = {}

    def identifier(self, raw: str, datatype: bool = False) -> str:
        mapping = self.types if datatype else self.identifiers
        if raw not in mapping:
            prefix = "DUMMY_TYPE" if datatype else "DUMMY_ID"
            mapping[raw] = f"{prefix}_{len(mapping) + 1:05d}"
        return mapping[raw]

    def literal(self, raw: str, declared: str | None) -> str:
        kind = lexical_kind(raw)
        if kind == "empty":
            return ""
        if declared == "BOOL":
            return str(self.random.randrange(2))
        if kind == "boolean_literal":
            return self.random.choice(("false", "true"))
        if kind == "integer_literal":
            return str(self.random.randint(1, 50))
        if kind == "radix_integer_literal":
            return "16#0001"
        if kind == "real_literal":
            return f"{self.random.randint(1, 50) / 10:.1f}"
        if kind == "date_like":
            return "2000-01-01T00:00:00"
        if kind == "identifier_like":
            return self.identifier(raw)
        return "Example value."

    def attribute(self, name: str, path: str, key: str, raw: str,
                  declared: str | None) -> tuple[str, str, str]:
        if raw == "":
            return "", "empty_preserved", "empty"
        allowed = technical_values(name, key)
        if name == "Rung" and path.endswith("/RLLContent/Rung") and key == "Type":
            allowed = RUNG_TYPES
        if raw in allowed:
            return raw, "technical_literal_retained", f"approved:{raw}"
        if name == "Rung" and path.endswith("/RLLContent/Rung") and key == "Number":
            if re.fullmatch(r"[0-9]{1,20}", raw):
                return raw, "rung_number_retained", "numeric_rung_number"
            return "0", "invalid_rung_number_replaced", "invalid_rung_number"
        if key == "DataType":
            value = self.identifier(raw, datatype=True)
            return value, "datatype_masked", value
        if field_role(path, key) == "identifier_or_reference":
            return self.identifier(raw), "identifier_replaced", "identifier"
        return self.literal(raw, declared if key in {"Value", "ForceValue"} else None), \
            "literal_replaced", lexical_kind(raw)


def sanitized_tree(source: BinaryIO, rung_report: dict, seed: int = 0) -> tuple[list[Node], dict]:
    """Only stack text buffers and replacement dictionaries hold original values."""
    replacements = Replacements(seed)
    labels = OpcodeLabels()
    expected_rungs = {r["locator"]: r for r in rung_report["rungs"]}
    shapes = {p["id"]: p["shape"] for p in rung_report["patterns"]}
    nodes: list[Node] = []
    stack: list[dict] = []
    counts = Counter()
    seen_rungs: set[str] = set()

    def start(expanded: str, attributes: dict[str, str]) -> None:
        if len(stack) >= MAX_DEPTH or len(nodes) >= MAX_NODES:
            raise StructureError("Input exceeds the dummy generator's depth/node limit.")
        name = expanded.rsplit("}", 1)[-1]
        attrs = {k.rsplit("}", 1)[-1]: v for k, v in attributes.items()}
        parent = stack[-1] if stack else None
        parent_node = nodes[parent["index"]] if parent else None
        if parent:
            parent["children"][name] += 1
        ordinal = parent["children"][name] if parent else 1
        path = f"{parent_node.path if parent_node else ''}/{name}"
        locator = f"{parent_node.locator if parent_node else ''}/{name}[{ordinal}]"
        clean, actions, classes = {}, {}, []
        for key, raw in attrs.items():
            value, action, category = replacements.attribute(name, path, key, raw, attrs.get("DataType"))
            clean[key], actions[key] = value, action
            classes.append((key, category))
        node = Node(name, path, locator, parent["index"] if parent else None,
                    clean, actions, tuple(sorted(classes)))
        if parent_node is not None:
            parent_node.children.append(len(nodes))
        nodes.append(node)
        stack.append({"index": len(nodes) - 1, "parts": [], "size": 0, "children": Counter(),
                      "declared": attrs.get("DataType")})
        counts["elements"] += 1
        counts["attributes"] += len(attrs)

    def text(value: str) -> None:
        if not stack:
            return
        frame = stack[-1]
        frame["size"] += len(value)
        if frame["size"] > MAX_DIRECT_TEXT:
            raise StructureError("An element exceeds the direct-text memory limit.")
        frame["parts"].append(value)

    def cdata() -> None:
        if stack:
            nodes[stack[-1]["index"]].cdata = True

    def end(_expanded: str) -> None:
        frame = stack.pop()
        node = nodes[frame["index"]]
        raw = "".join(frame["parts"])
        node.source_text = bool(raw.strip())
        counts["elements_with_text"] += int(node.source_text)
        counts["elements_with_cdata"] += int(node.cdata)
        if not node.source_text and not node.cdata:
            return
        if not node.source_text:
            node.text_action = "empty_preserved"
            return
        role = field_role(node.path, None)
        if role == "ladder_text":
            parent = nodes[node.parent]
            record = expected_rungs.get(parent.locator)
            if record is None or node.children:
                raise StructureError("Ladder content differs from the rung inventory.")
            shape, sample, _ = public_forms(parse_rung(raw), labels)
            if shape != shapes[record["pattern_id"]]:
                raise StructureError("Ladder shape differs from the rung inventory.")
            if parent.attributes.get("Number") != record["number"] or parent.attributes.get("Type") != record["type"]:
                raise StructureError("Rung metadata differs from the verified inventory.")
            seen_rungs.add(parent.locator)
            node.text = render_sample(sample)
            node.text_action = "ladder_operands_replaced"
        elif role == "serialized_payload" or node.name in {"EncryptedContent", "EncryptedSegments"}:
            node.text, node.text_action = "DUMMY_SERIALIZED_DATA", "opaque_payload_replaced"
        elif role == "structured_text":
            node.text, node.text_action = "(* DUMMY_ST_TEXT *)", "structured_text_replaced"
        elif role == "free_text":
            node.text = replacements.random.choice((
                "Example description A.", "Description fictive B.", "Example note C.",
            ))
            node.text_action = "free_text_replaced"
        elif node.children:
            node.text, node.text_action = "Example mixed text.", "mixed_text_replaced"
        else:
            node.text = replacements.literal(raw, frame["declared"])
            node.text_action = "element_text_replaced"

    def reject(*_args: object) -> None:
        raise StructureError("DTD and entity declarations are not allowed.")

    def ignored_comment(_value: str) -> None:
        counts["comments_ignored"] += 1

    def ignored_pi(_target: str, _value: str) -> None:
        counts["processing_instructions_ignored"] += 1

    parser = expat.ParserCreate(namespace_separator="}")
    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.CharacterDataHandler, parser.StartCdataSectionHandler = text, cdata
    parser.StartDoctypeDeclHandler = parser.EntityDeclHandler = parser.ExternalEntityRefHandler = reject
    parser.CommentHandler, parser.ProcessingInstructionHandler = ignored_comment, ignored_pi
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    try:
        for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
            parser.Parse(chunk, False)
        parser.Parse(b"", True)
    except expat.ExpatError as error:
        raise StructureError(f"Malformed XML at line {error.lineno}, column {error.offset}.") from None
    except LookupError:
        raise StructureError("Unsupported XML encoding.") from None
    totals = rung_report["source_totals"]
    for measured, expected in (
        ("elements", "element_occurrences"), ("attributes", "attribute_occurrences"),
        ("elements_with_text", "elements_with_text"), ("elements_with_cdata", "elements_with_cdata"),
    ):
        if counts[measured] != totals[expected]:
            raise StructureError("Input counts changed between inventory and sanitization.")
    if seen_rungs != set(expected_rungs):
        raise StructureError("Rung coverage changed between inventory and sanitization.")
    return nodes, dict(counts)
