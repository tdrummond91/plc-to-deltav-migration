"""Retained standalone inspection prototype.

Normal project use starts at ``run-work-check.sh`` or ``plc_workbench.cli``.
This older explorer keeps its original command-line interface for reference.
"""
from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path
import l5x


def show_tags(project: l5x.Project) -> None:
    # Controller-scoped tags
    for name in project.controller.tags.names:
        tag = project.controller.tags[name]
        print(f"{name}: {tag.description}")

    # Programs and their tag names
    for name in project.programs.names:
        program = project.programs[name]
        print(f"\nProgram: {name}")
        for tag_name in program.tags.names:
            print(f"  {tag_name}")


def local_name(tag: str) -> str:
    """Handle XML files with or without namespaces."""
    return tag.rsplit("}", 1)[-1]


def children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if local_name(child.tag) == name]


def child_text(element: ET.Element, name: str) -> str:
    matches = children(element, name)
    return "".join(matches[0].itertext()).strip() if matches else ""


def ladder_tokens(text: str) -> list[str]:
    """
    Keep complete instruction calls together.

    Brackets within instruction operands, such as XIC(Bits[0]),
    remain inside the instruction rather than becoming branches.
    """
    tokens: list[str] = []
    index = 0

    while index < len(text):
        character = text[index]

        if character.isspace():
            index += 1
            continue

        if character in "[],;":
            tokens.append(character)
            index += 1
            continue

        match = re.match(r"[A-Za-z_][A-Za-z0-9_]*\s*\(", text[index:])
        if not match:
            raise ValueError(
                f"Unexpected ladder text at position {index}: "
                f"{text[index : index + 60]!r}"
            )

        start = index
        index += match.end()
        depth = 1
        quote: str | None = None

        while index < len(text) and depth:
            character = text[index]

            if quote:
                # Logix strings can contain $ escape sequences.
                if character == "$" and index + 1 < len(text):
                    index += 2
                    continue
                if character == quote:
                    quote = None
            elif character in "\"'":
                quote = character
            elif character == "(":
                depth += 1
            elif character == ")":
                depth -= 1

            index += 1

        if depth:
            raise ValueError("Unclosed instruction parentheses")

        tokens.append(text[start:index])

    return tokens


def format_ladder(text: str) -> str:
    """Show branch structure; this is not a PLC execution simulator."""
    lines: list[str] = []
    branch_legs: list[int] = []

    def emit(message: str) -> None:
        lines.append(f"{'    ' * len(branch_legs)}{message}")

    for token in ladder_tokens(text):
        if token == "[":
            emit("PARALLEL BEGIN")
            branch_legs.append(1)
            emit("PATH 1")
        elif token == ",":
            if not branch_legs:
                raise ValueError("Branch separator outside a branch")
            branch_legs[-1] += 1
            emit(f"PATH {branch_legs[-1]}")
        elif token == "]":
            if not branch_legs:
                raise ValueError("Unmatched closing branch")
            branch_legs.pop()
            emit("PARALLEL END")
        elif token == ";":
            if branch_legs:
                raise ValueError("Rung ended inside an unclosed branch")
            emit("END RUNG")
        else:
            emit(token)

    if branch_legs:
        raise ValueError("Unclosed branch")

    return "\n".join(lines)


def summary(root: ET.Element) -> None:
    counts: dict[str, int] = {}

    for element in root.iter():
        name = local_name(element.tag)
        counts[name] = counts.get(name, 0) + 1

    print("EXPORT")
    for key, value in root.attrib.items():
        print(f"  {key}: {value}")

    print("\nCOMPONENT COUNTS")
    for name in (
        "Controller",
        "Module",
        "Task",
        "Program",
        "Routine",
        "Rung",
        "Tag",
        "DataType",
        "AddOnInstructionDefinition",
        "Trend",
        "EncodedData",
    ):
        print(f"  {name}: {counts.get(name, 0)}")

    print("\nROUTINES")

    def visit(element: ET.Element, scope: str = "Controller") -> None:
        name = local_name(element.tag)

        if name in ("Program", "AddOnInstructionDefinition"):
            scope = f"{name}/{element.get('Name', '?')}"

        if name == "Routine":
            rung_count = sum(local_name(item.tag) == "Rung" for item in element.iter())
            print(
                f"  {scope}/{element.get('Name', '?')} "
                f"type={element.get('Type', '?')} rungs={rung_count}"
            )
        elif name == "EncodedData":
            print(
                f"  {scope}/{element.get('Name', '?')} "
                f"[ENCODED {element.get('EncodedType', '?')}]"
            )

        for child in element:
            visit(child, scope)

    visit(root)


def show_rungs(root: ET.Element, routine_name: str) -> None:
    found = False

    def visit(element: ET.Element, scope: str = "Controller") -> None:
        nonlocal found
        name = local_name(element.tag)

        if name in ("Program", "AddOnInstructionDefinition"):
            scope = f"{name}/{element.get('Name', '?')}"

        if name == "Routine" and element.get("Name") == routine_name:
            found = True
            print(f"\n{scope}/{routine_name}")

            if element.get("Type") != "RLL":
                print("This is not a ladder routine. Use --find to inspect XML.")
                return

            for content in children(element, "RLLContent"):
                for rung in children(content, "Rung"):
                    text = child_text(rung, "Text")
                    comment = child_text(rung, "Comment")

                    print(f"\nRUNG {rung.get('Number', '?')}")
                    if comment:
                        print(f"COMMENT: {comment}")
                    print(f"RAW: {text}")

                    try:
                        print(format_ladder(text))
                    except ValueError as error:
                        print(f"Formatting unavailable: {error}")

        if (
            name == "EncodedData"
            and element.get("Name") == routine_name
            and element.get("EncodedType") == "Routine"
        ):
            found = True
            print(f"\n{scope}/{routine_name}: content is still encoded")

        for child in element:
            visit(child, scope)

    visit(root)

    if not found:
        print(f"No routine named {routine_name!r} found.")


def inspect_matches(root: ET.Element, query: str) -> None:
    """Print complete XML for named components and their descendants."""
    count = 0

    def visit(element: ET.Element, path: str = "") -> None:
        nonlocal count
        name = local_name(element.tag)
        component_name = element.get("Name")
        label = f"{name}[{component_name}]" if component_name else name
        current_path = f"{path}/{label}"

        if component_name and query.casefold() in component_name.casefold():
            count += 1
            print(f"\n{current_path}")

            if name == "EncodedData":
                print(f"Encoded content: {element.attrib}")
            else:
                print(ET.tostring(element, encoding="unicode"))

            # Its descendants are already included in the XML output.
            return

        for child in element:
            visit(child, current_path)

    visit(root)
    print(f"\nMatched components: {count}")


def main():
    parser = argparse.ArgumentParser(description="Read-only L5X inspector")
    parser.add_argument("file", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--routine", help="Display ladder rungs by routine name")
    mode.add_argument(
        "--find",
        help="Inspect components whose Name contains text",
    )
    mode.add_argument(
        "--tags", action="store_true", help="Read in L5X file to find tags"
    )
    args = parser.parse_args()

    if args.tags:
        try:
            project = l5x.Project(str(args.file))
        except OSError as error:
            parser.exit(1, f"Cannot read L5X: {error}\n")

        show_tags(project)
        return

    try:
        root = ET.parse(args.file).getroot()
    except (OSError, ET.ParseError) as error:
        parser.exit(1, f"Cannot read L5X: {error}\n")

    if args.routine:
        show_rungs(root, args.routine)
    elif args.find:
        inspect_matches(root, args.find)
    elif args.tags:
        show_tags(project)
    else:
        summary(root)


if __name__ == "__main__":
    main()
