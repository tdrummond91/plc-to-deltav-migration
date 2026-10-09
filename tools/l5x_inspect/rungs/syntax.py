"""Small neutral-text parser and structural metrics; no PLC execution semantics."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import re

MAX_TEXT = 2_000_000
MAX_DEPTH = 64
MAX_NODES = 20_000
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Publication permission list, not a complete instruction catalog.
PUBLIC_OPCODES = frozenset("""
ABS ADD AFI ALMA ALMD AND ASN ATN AVE BRK BSL BSR BTD CLR CMP CONCAT COP COS
CPS CPT CTD CTU DEG DELETE DIV DTOS DTR EQU EVENT FAL FBC FFL FFU FIND FLL
FOR FRD FSC GEQ GRT GSV INSERT IOT JMP JSR JXR LBL LEQ LES LFL LFU LIM LN
LOG LOWER MCR MEQ MID MOD MOV MSG MUL MVM NEG NEQ NOP NOT ONS OR OSF OSR
OTE OTL OTU PID RAD RES RET RTO RTOS SBR SFP SFR SIN SIZE SQI SQL SQO SQR
SRT SSV STD STOD STOR SUB SWPB TAN TND TOD TOF TON TRN UID UIE UPPER XIC XIO XOR XPY
""".split())
EXPRESSION_OPCODES = frozenset({"CMP", "CPT", "FAL", "FSC"})


class RungSyntaxError(ValueError):
    def __init__(self, code: str, offset: int):
        self.code, self.offset = code, offset
        super().__init__(f"{code} at character offset {offset}")


@dataclass(frozen=True)
class Instruction:
    opcode: str = field(repr=False)
    arguments: tuple[str, ...] = field(repr=False)


@dataclass(frozen=True)
class Sequence:
    items: tuple[Instruction | Branch, ...]


@dataclass(frozen=True)
class Branch:
    legs: tuple[Sequence, ...]


class _Parser:
    def __init__(self, text: str):
        self.text, self.pos, self.nodes = text, 0, 0

    def fail(self, code: str) -> None:
        raise RungSyntaxError(code, self.pos)

    def space(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def count_node(self) -> None:
        self.nodes += 1
        if self.nodes > MAX_NODES:
            self.fail("node_limit")

    def sequence(self, depth: int) -> Sequence:
        items = []
        while True:
            self.space()
            if self.pos == len(self.text) or self.text[self.pos] in ",];":
                return Sequence(tuple(items))
            self.count_node()
            if self.text[self.pos] == "[":
                if depth >= MAX_DEPTH:
                    self.fail("branch_depth_limit")
                self.pos += 1
                legs = [self.sequence(depth + 1)]
                while self.pos < len(self.text) and self.text[self.pos] == ",":
                    self.pos += 1
                    legs.append(self.sequence(depth + 1))
                if self.pos == len(self.text) or self.text[self.pos] != "]":
                    self.fail("unclosed_branch")
                if len(legs) < 2:
                    self.fail("branch_requires_two_legs")
                self.pos += 1
                items.append(Branch(tuple(legs)))
            else:
                match = NAME.match(self.text, self.pos)
                if not match:
                    self.fail("expected_instruction")
                opcode = match.group()
                self.pos = match.end()
                self.space()
                if self.pos == len(self.text) or self.text[self.pos] != "(":
                    self.fail("expected_argument_list")
                items.append(Instruction(opcode, self.arguments()))

    def arguments(self) -> tuple[str, ...]:
        self.pos += 1
        start = self.pos
        args: list[str] = []
        closing = [")"]
        quote: str | None = None
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if quote:
                if char == "$":
                    # Logix dollar escapes, including an escaped quote.
                    self.pos += 2
                    continue
                if char == quote:
                    if self.pos + 1 < len(self.text) and self.text[self.pos + 1] == quote:
                        self.pos += 2
                        continue
                    quote = None
                self.pos += 1
                continue
            if char in {"'", '"'}:
                quote = char
            elif char in "([{":
                closing.append({"(": ")", "[": "]", "{": "}"}[char])
                if len(closing) > MAX_DEPTH:
                    self.fail("argument_depth_limit")
            elif char in ")]}":
                if char != closing[-1]:
                    self.fail("mismatched_argument_delimiter")
                closing.pop()
                if not closing:
                    last = self.text[start:self.pos].strip()
                    if last or args:
                        args.append(last)
                    self.pos += 1
                    return tuple(args)
            elif char == "," and len(closing) == 1:
                args.append(self.text[start:self.pos].strip())
                start = self.pos + 1
            elif char == ";":
                self.fail("semicolon_inside_argument")
            self.pos += 1
        self.fail("unclosed_quote" if quote else "unclosed_argument_list")
        raise AssertionError("unreachable")


def parse_rung(text: str) -> Sequence:
    """Recognize calls and square-bracket branches; argument internals stay opaque."""
    if len(text) > MAX_TEXT:
        raise RungSyntaxError("text_limit", 0)
    parser = _Parser(text)
    result = parser.sequence(0)
    if parser.pos == len(text):
        parser.fail("missing_rung_terminator")
    if text[parser.pos] != ";":
        parser.fail("unexpected_branch_separator")
    parser.pos += 1
    parser.space()
    if parser.pos != len(text):
        parser.fail("trailing_content")
    return result


def measure(sequence: Sequence) -> dict[str, int]:
    """Instruction boxes have width 1; empty wire paths have height 1 and width 0."""
    def seq(items: Sequence, depth: int) -> dict[str, int]:
        result = {
            "instruction_calls": 0, "argument_slots": 0, "nonempty_argument_fields": 0,
            "expression_instruction_calls": 0, "branch_groups": 0, "branch_legs": 0,
            "empty_branch_legs": 0, "max_branch_depth": depth,
            "max_legs_in_group": 0, "height_lanes": 1, "width_instructions": 0,
        }
        for item in items.items:
            if isinstance(item, Instruction):
                result["instruction_calls"] += 1
                result["argument_slots"] += len(item.arguments)
                result["nonempty_argument_fields"] += sum(bool(arg) for arg in item.arguments)
                result["expression_instruction_calls"] += int(item.opcode in EXPRESSION_OPCODES)
                result["width_instructions"] += 1
            else:
                legs = [seq(leg, depth + 1) for leg in item.legs]
                result["branch_groups"] += 1
                result["branch_legs"] += len(legs)
                result["empty_branch_legs"] += sum(not leg.items for leg in item.legs)
                for key in ("instruction_calls", "argument_slots", "nonempty_argument_fields",
                            "expression_instruction_calls", "branch_groups", "branch_legs",
                            "empty_branch_legs"):
                    result[key] += sum(leg[key] for leg in legs)
                result["max_branch_depth"] = max(result["max_branch_depth"], *(leg["max_branch_depth"] for leg in legs))
                result["max_legs_in_group"] = max(result["max_legs_in_group"], len(legs), *(leg["max_legs_in_group"] for leg in legs))
                result["height_lanes"] = max(result["height_lanes"], sum(leg["height_lanes"] for leg in legs))
                result["width_instructions"] += max(leg["width_instructions"] for leg in legs)
        return result
    return seq(sequence, 0)


class OpcodeLabels:
    """Unknown names are retained privately only to assign consistent run-local labels."""
    def __init__(self) -> None:
        self._unknown: dict[str, str] = {}

    def label(self, opcode: str) -> str:
        if opcode in PUBLIC_OPCODES:
            return opcode
        if opcode not in self._unknown:
            self._unknown[opcode] = f"UNLISTED_OP_{len(self._unknown) + 1:04d}"
        return self._unknown[opcode]

    @property
    def unknown_count(self) -> int:
        return len(self._unknown)


def public_forms(sequence: Sequence, labels: OpcodeLabels) -> tuple[dict, dict, Counter]:
    """Create a value-free shape and dummy sample. Repeated whole operands share labels."""
    operands: dict[str, str] = {}
    instructions: Counter = Counter()

    def convert(items: Sequence) -> tuple[dict, dict]:
        shape_items, sample_items = [], []
        for item in items.items:
            if isinstance(item, Instruction):
                opcode = labels.label(item.opcode)
                instructions[opcode] += 1
                args = []
                for argument in item.arguments:
                    if not argument:
                        args.append("")
                    else:
                        if argument not in operands:
                            operands[argument] = f"ARG_{len(operands) + 1:03d}"
                        args.append(operands[argument])
                shape_items.append({
                    "kind": "instruction", "opcode": opcode, "argument_count": len(args),
                    "empty_argument_positions": [i for i, arg in enumerate(args) if not arg],
                })
                sample_items.append({"kind": "instruction", "opcode": opcode, "arguments": args})
            else:
                pairs = [convert(leg) for leg in item.legs]
                shape_items.append({"kind": "branch", "legs": [pair[0] for pair in pairs]})
                sample_items.append({"kind": "branch", "legs": [pair[1] for pair in pairs]})
        return (
            {"kind": "sequence", "items": shape_items},
            {"kind": "sequence", "items": sample_items},
        )
    shape, sample = convert(sequence)
    return shape, sample, instructions


def render_sample(tree: dict) -> str:
    """Render only the already-sanitized sample tree as neutral-text-shaped text."""
    def seq(node: dict) -> str:
        parts = []
        for item in node["items"]:
            if item["kind"] == "instruction":
                parts.append(f"{item['opcode']}({','.join(item['arguments'])})")
            else:
                parts.append("[" + ",".join(seq(leg) for leg in item["legs"]) + "]")
        return "".join(parts)
    return seq(tree) + ";"
