"""One explicitly authorized real operand for a narrowly scoped parser diagnosis.

This is separate from the count-only reference summary. The sample contains
one direct malformed operand, or a direct unresolved colon operand without a
rack candidate, plus its standard opcode and zero-based slot. It never includes
a rung, source location, adjacent operands or an alias target.
Selection follows the existing canonical operand order; repeated runs neither
rotate examples nor truncate or replace source text. No file or network IO.
"""
from __future__ import annotations

from typing import Any

from .ladder.syntax import Instruction, RungSyntaxError, parse_rung
from .models import InventoryResult
from .references import (
    ReferenceResult, _ARITIES, _address, _literal, _swpb_order_mode, validate_references,
)


MAX_OPERAND_CHARS = 128
MALFORMED_SAMPLE_KIND = "direct_malformed_operand"
UNMATCHED_COLON_SAMPLE_KIND = "direct_unmatched_colon_operand"
SAMPLE_KINDS = frozenset({MALFORMED_SAMPLE_KIND, UNMATCHED_COLON_SAMPLE_KIND})
_KEYS = frozenset({"kind", "opcode", "argument_index", "raw_text"})


class DiagnosticSampleError(ValueError):
    """Fixed validation failure without echoing source-controlled text."""


def _invalid() -> None:
    raise DiagnosticSampleError("Invalid single-operand diagnostic sample.")


def validate_diagnostic_sample(value: Any) -> None:
    """Validate the closed lexical form; report/evidence validators check context."""
    if value is None:
        return
    if type(value) is not dict or value.keys() != _KEYS:
        _invalid()
    if type(value["kind"]) is not str or value["kind"] not in SAMPLE_KINDS:
        _invalid()
    opcode, index, raw = value["opcode"], value["argument_index"], value["raw_text"]
    if (type(opcode) is not str or opcode not in _ARITIES or opcode in {"JMP", "LBL"}
            or type(index) is not int or not 0 <= index < _ARITIES[opcode]
            or opcode == "CPT" and index == 1 or _swpb_order_mode(opcode, index)):
        _invalid()
    if type(raw) is not str or not 1 <= len(raw) <= MAX_OPERAND_CHARS or not raw.isprintable():
        _invalid()
    parsed, reason = _address(raw)
    if _literal(raw.strip()):
        _invalid()
    if value["kind"] == MALFORMED_SAMPLE_KIND:
        if parsed is not None or reason != "malformed_address":
            _invalid()
    elif parsed is None or ":" not in parsed[0]:
        _invalid()
    # Malformed addresses may contain nested syntax or array commas. Reuse the
    # grammar to distinguish one operand from injected slots or whole rungs.
    try:
        tree = parse_rung(f"XIC({raw});")
    except RungSyntaxError:
        _invalid()
    if (len(tree.items) != 1 or type(tree.items[0]) is not Instruction
            or tree.items[0].opcode != "XIC" or tree.items[0].arguments != (raw.strip(),)):
        _invalid()


def build_diagnostic_sample(inventory: InventoryResult, references: ReferenceResult) -> dict[str, Any] | None:
    """Prefer malformed evidence, then an unmatched direct colon-root operand.

    Canonical validation covers the private rack comparisons before they can
    authorize fallback. Both passes retain source occurrence order, and neither
    pass rotates, shortens or substitutes an operand.
    """
    validate_references(inventory, references)
    opcodes = {instruction.id: instruction.opcode.upper()
               for rung in inventory.rungs for instruction in rung.instructions}
    for operand in references.operands:
        if (operand["status"] != "unsupported_address" or operand["reason"] != "malformed_address"
                or operand["alias_chain"]):
            continue
        sample = {"kind": MALFORMED_SAMPLE_KIND, "opcode": opcodes[operand["instruction_id"]],
                  "argument_index": operand["argument_index"], "raw_text": operand["raw_text"]}
        try:
            validate_diagnostic_sample(sample)
        except DiagnosticSampleError:
            # Overlong or nonprintable real operands remain counted in the
            # aggregate. They do not become shortened or substituted samples.
            continue
        return sample
    unmatched = {row["source_id"]
                 for row in references.rack_candidates["matches"]["direct_operands"]
                 if row["status"] == "no_candidate_match"}
    for operand in references.operands:
        if (operand["id"] not in unmatched or operand["status"] != "unresolved"
                or operand["reason"] != "colon_root_not_declared" or operand["alias_chain"]):
            continue
        sample = {"kind": UNMATCHED_COLON_SAMPLE_KIND, "opcode": opcodes[operand["instruction_id"]],
                  "argument_index": operand["argument_index"], "raw_text": operand["raw_text"]}
        try:
            validate_diagnostic_sample(sample)
        except DiagnosticSampleError:
            continue
        return sample
    return None
