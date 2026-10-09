"""Stage 1: count actual XML structure without exposing attribute values or text.

Standalone auxiliary helper; it does not import the application or the l5x package.
Root and nested counts cover the full input, not a sample.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
import tempfile
from typing import BinaryIO
from xml.parsers import expat

MAX_DEPTH = 128
MAX_SHAPES = 50_000
CHUNK_SIZE = 64 * 1024


class StructureError(ValueError):
    """A safe diagnostic that does not include source content."""


@dataclass
class XMLPathSummary:
    name: str
    attributes: dict[str, int] = field(default_factory=dict)
    children: dict[str, XMLPathSummary] = field(default_factory=dict)
    occurrences: int = 0
    text_occurrences: int = 0
    cdata_occurrences: int = 0


def _local_name(expanded_name: str) -> str:
    # Expat supplies namespace URI + "}" + local name when a namespace is used.
    return expanded_name.rsplit("}", 1)[-1]


def parse_structure(source: BinaryIO) -> XMLPathSummary:
    """Read XML without retaining its text or attribute values.

    Each parent has at most one child of each local element name. Attributes and
    child structures from repeated occurrences are combined in first-seen order.
    Counts preserve multiplicity at each XML path; individual record associations
    are intentionally not retained.
    """
    root: XMLPathSummary | None = None
    stack: list[XMLPathSummary] = []
    text_seen: list[bool] = []
    cdata_seen: list[bool] = []
    # Private parser-only bookkeeping detects namespace collisions. Never exported.
    element_names: dict[tuple[int, str], str] = {}
    attribute_names: dict[tuple[int, str], str] = {}
    shape_count = 0

    def start_element(expanded_name: str, attributes: dict[str, str]) -> None:
        nonlocal root, shape_count
        if len(stack) >= MAX_DEPTH:
            raise StructureError(f"XML exceeds the maximum depth of {MAX_DEPTH}.")
        name = _local_name(expanded_name)
        parent_id = id(stack[-1]) if stack else 0
        key = (parent_id, name)
        previous = element_names.setdefault(key, expanded_name)
        if previous != expanded_name:
            raise StructureError("Element names collide after removing namespaces.")

        if not stack:
            if root is not None:
                raise StructureError("XML must contain exactly one root element.")
            node = root = XMLPathSummary(name)
            shape_count += 1
        else:
            parent = stack[-1]
            if name not in parent.children:
                parent.children[name] = XMLPathSummary(name)
                shape_count += 1
            node = parent.children[name]
        if shape_count > MAX_SHAPES:
            raise StructureError(f"XML exceeds the limit of {MAX_SHAPES} unique paths.")

        node.occurrences += 1
        # Iterate names only. Attribute values are deliberately never copied.
        for expanded_attribute in attributes:
            attribute = _local_name(expanded_attribute)
            attribute_key = (id(node), attribute)
            previous_attribute = attribute_names.setdefault(
                attribute_key, expanded_attribute
            )
            if previous_attribute != expanded_attribute:
                raise StructureError("Attribute names collide after removing namespaces.")
            node.attributes[attribute] = node.attributes.get(attribute, 0) + 1
        stack.append(node)
        text_seen.append(False)
        cdata_seen.append(False)

    def end_element(_name: str) -> None:
        stack.pop()
        text_seen.pop()
        cdata_seen.pop()

    def start_cdata() -> None:
        if stack:
            if not cdata_seen[-1]:
                stack[-1].cdata_occurrences += 1
                cdata_seen[-1] = True

    def character_data(text: str) -> None:
        if stack and not text_seen[-1] and text.strip():
            stack[-1].text_occurrences += 1
            text_seen[-1] = True

    def reject_declaration(*_arguments: object) -> None:
        raise StructureError("DTD and entity declarations are not allowed.")

    def reject_external_entity(*_arguments: object) -> int:
        raise StructureError("External entities are not allowed.")

    parser = expat.ParserCreate(namespace_separator="}")
    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    parser.StartCdataSectionHandler = start_cdata
    parser.CharacterDataHandler = character_data
    parser.StartDoctypeDeclHandler = reject_declaration
    parser.EntityDeclHandler = reject_declaration
    parser.ExternalEntityRefHandler = reject_external_entity
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    # Character data is counted by presence only. No handler stores its contents.
    # Comments and processing instructions are ignored.
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
    if root is None:
        raise StructureError("XML has no root element.")
    return root


def build_summary(root: XMLPathSummary) -> dict[str, object]:
    """Count the complete source, grouped by XML path and by element name.

    Attribute counts mean presence on source elements, not distinct values.
    Text counts mean elements with non-whitespace direct text, including CDATA.
    """
    totals = {
        "element_occurrences": 0,
        "attribute_occurrences": 0,
        "distinct_element_paths": 0,
        "elements_with_text": 0,
        "elements_with_cdata": 0,
        "max_depth": 0,
    }
    element_counts: dict[str, int] = {}
    attribute_counts: dict[str, int] = {}

    def visit(node: XMLPathSummary, depth: int) -> dict[str, object]:
        totals["element_occurrences"] += node.occurrences
        totals["attribute_occurrences"] += sum(node.attributes.values())
        totals["distinct_element_paths"] += 1
        totals["elements_with_text"] += node.text_occurrences
        totals["elements_with_cdata"] += node.cdata_occurrences
        totals["max_depth"] = max(totals["max_depth"], depth)
        element_counts[node.name] = element_counts.get(node.name, 0) + node.occurrences
        for name, count in node.attributes.items():
            attribute_counts[name] = attribute_counts.get(name, 0) + count
        return {
            "element": node.name,
            "count": node.occurrences,
            "attributes": {
                name: {"count": count} for name, count in node.attributes.items()
            },
            "elements_with_text": node.text_occurrences,
            "elements_with_cdata": node.cdata_occurrences,
            "children": [visit(child, depth + 1) for child in node.children.values()],
        }

    nested = visit(root, 1)
    return {
        "schema_version": 1,
        "count_scope": "complete_input",
        "aggregation": "repeated_elements_grouped_by_xml_path",
        "namespaces": "prefixes_and_uris_removed",
        "totals": totals,
        "counts_by_element_name": element_counts,
        "counts_by_attribute_name": attribute_counts,
        "root": nested,
    }


def _write_atomic(output: Path, rendered: str) -> None:
    """Replace one output after its sanitized content has been fully written."""
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n",
            prefix=".xml-structure-counts-", suffix=".tmp",
            dir=output.parent, delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(rendered)
        os.replace(temporary, output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def create_summary(source: Path, output: Path) -> Path:
    """Read the source once and atomically publish a value-free count report."""
    source = source.resolve()
    output = output.resolve()
    if source == output or (
        source.exists() and output.exists() and source.samefile(output)
    ):
        raise StructureError("Input and output must be different files.")
    with source.open("rb") as stream:
        report = build_summary(parse_structure(stream))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    _write_atomic(output, rendered)
    return output


def main() -> int:
    # File location: <repository>/tools/l5x_inspect/summarize_xml.py
    default_output = (
        Path(__file__).resolve().parents[2] / "public" / "xml-structure-counts.json"
    )
    parser = argparse.ArgumentParser(
        description=(
            "Count XML elements and attributes in the complete input and write "
            "a nested JSON summary without source values or text."
        ),
        epilog=(
            "Stage 1 only. Counts expose document size. Element/attribute names "
            "remain visible; no dummy L5X or full XML skeleton is generated yet."
        ),
    )
    parser.add_argument("file", type=Path, help="local XML/L5X input; read only")
    parser.add_argument(
        "-o", "--output", type=Path, default=default_output,
        help="JSON output (default: repository public/xml-structure-counts.json)",
    )
    args = parser.parse_args()
    try:
        output = create_summary(args.file, args.output)
    except StructureError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"File operation failed: {error.strerror or 'I/O error'}.", file=sys.stderr)
        return 1
    print(f"Wrote structure counts: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
