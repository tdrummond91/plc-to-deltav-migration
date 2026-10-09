"""Stage 2: preserve every XML element while blanking all source values."""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import os
import sys
import tempfile
from typing import BinaryIO, TextIO
from xml.parsers import expat

from summarize_xml import (
    CHUNK_SIZE, MAX_DEPTH, StructureError, build_summary, parse_structure,
)


def write_blank_xml(source: BinaryIO, output: TextIO) -> None:
    """Stream blank XML; source comments, text, PIs and namespace URIs are omitted.

    Callers must validate namespace collisions with parse_structure first.
    create_skeleton performs that preflight and validates the completed output.
    """
    # Each frame contains the local name and whether a child/CDATA was written.
    stack: list[tuple[str, bool]] = []

    def begin_content() -> None:
        if stack and not stack[-1][1]:
            output.write("\n")
            stack[-1] = (stack[-1][0], True)

    def start_element(expanded: str, attributes: dict[str, str]) -> None:
        if len(stack) >= MAX_DEPTH:
            raise StructureError(f"XML exceeds the maximum depth of {MAX_DEPTH}.")
        begin_content()
        name = expanded.rsplit("}", 1)[-1]
        blank_attributes = "".join(
            f' {attribute.rsplit("}", 1)[-1]}=""' for attribute in attributes
        )
        output.write(f'{"  " * len(stack)}<{name}{blank_attributes}>')
        stack.append((name, False))

    def end_element(_expanded: str) -> None:
        name, has_content = stack.pop()
        indent = "  " * len(stack) if has_content else ""
        output.write(f"{indent}</{name}>\n")

    def start_cdata() -> None:
        begin_content()
        output.write(f'{"  " * len(stack)}<![CDATA[]]>\n')

    def reject_declaration(*_arguments: object) -> None:
        raise StructureError("DTD and entity declarations are not allowed.")

    def reject_external_entity(*_arguments: object) -> int:
        raise StructureError("External entities are not allowed.")

    parser = expat.ParserCreate(namespace_separator="}")
    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    parser.StartCdataSectionHandler = start_cdata
    parser.StartDoctypeDeclHandler = reject_declaration
    parser.EntityDeclHandler = reject_declaration
    parser.ExternalEntityRefHandler = reject_external_entity
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    # No character-data, comment or PI handler: their source contents are discarded.
    output.write('<?xml version="1.0" encoding="utf-8"?>\n')
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


def verify_skeleton(expected: dict, actual: dict) -> None:
    """Require identical complete structure counts, except removed text."""
    if actual["totals"]["elements_with_text"] != 0:
        raise StructureError("Skeleton verification found nonblank text.")
    left, right = deepcopy(expected), deepcopy(actual)

    def clear_text_count(node: dict) -> None:
        node["elements_with_text"] = 0
        for child in node["children"]:
            clear_text_count(child)

    for report in (left, right):
        report["totals"]["elements_with_text"] = 0
        clear_text_count(report["root"])
    if left != right:
        raise StructureError("Skeleton verification found a structure/count mismatch.")


def create_skeleton(source: Path, output: Path) -> dict:
    """Preflight the source, stream sanitized XML, verify, then replace output.

    Temporary output contains only blank XML. Source is opened read-only.
    The existing output is replaced only after all parsing and checks pass.
    """
    source, output = source.resolve(), output.resolve()
    if source == output or (
        source.exists() and output.exists() and source.samefile(output)
    ):
        raise StructureError("Input and output must be different files.")

    temporary: Path | None = None
    try:
        with source.open("rb") as stream:
            expected = build_summary(parse_structure(stream))
            stream.seek(0)
            output.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n",
                prefix=".xml-skeleton-", suffix=".tmp",
                dir=output.parent, delete=False,
            ) as handle:
                temporary = Path(handle.name)
                write_blank_xml(stream, handle)

        with temporary.open("rb") as blank_stream:
            actual = build_summary(parse_structure(blank_stream))
        verify_skeleton(expected, actual)
        os.replace(temporary, output)
        return {
            "status": "verified",
            "element_occurrences": actual["totals"]["element_occurrences"],
            "attribute_occurrences": actual["totals"]["attribute_occurrences"],
            "distinct_element_paths": actual["totals"]["distinct_element_paths"],
            "elements_with_cdata": actual["totals"]["elements_with_cdata"],
            "max_depth": actual["totals"]["max_depth"],
        }
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Write a full blank XML skeleton: keep every element, attribute name, "
            "sibling order and CDATA section; remove every value and source text."
        ),
        epilog=(
            "All values, including Number, Type and DataType, are blanked. "
            "Retaining selected values belongs to the later dummy-data stage. "
            "Output is structural XML, not an importable controller project. "
            "A successful run replaces an existing output."
        ),
    )
    parser.add_argument("file", type=Path, help="original local XML/L5X; read only")
    parser.add_argument(
        "-o", "--output", type=Path,
        default=Path(__file__).resolve().parents[2] / "public" / "xml-skeleton.XML",
        help="output (default: repository public/xml-skeleton.XML)",
    )
    args = parser.parse_args()
    try:
        result = create_skeleton(args.file, args.output)
    except StructureError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"File operation failed: {error.strerror or 'I/O error'}.", file=sys.stderr)
        return 1
    print(
        f"PASS: {result['element_occurrences']} elements; "
        f"{result['attribute_occurrences']} attributes; "
        f"{result['distinct_element_paths']} paths; "
        f"{result['elements_with_cdata']} elements with CDATA; "
        f"depth {result['max_depth']}."
    )
    print(f"Skeleton: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
