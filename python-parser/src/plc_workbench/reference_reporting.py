"""Private views of snapshot-bound root bindings, with explicit limits."""

from __future__ import annotations

import json

from .references import ReferenceResult


def render_reference_json(result: ReferenceResult) -> str:
    """Serialize private evidence; never send this payload to the public writer."""
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n"


def render_reference_text(result: ReferenceResult) -> str:
    payload = result.to_dict()
    symbols = {item["id"]: item for item in payload["symbols"]}

    def label(symbol_id: str | None) -> str:
        if symbol_id is None:
            return "(unbound)"
        symbol = symbols.get(symbol_id)
        return f"{symbol['name']} [{symbol_id}]" if symbol else symbol_id

    lines = [
        "PRIVATE L5X tag and alias references",
        f"Status: {payload['status']}",
        f"Snapshot: {payload['snapshot']['id']}",
        f"Analyzer: {payload['analyzer_version']}",
        "Scope: declared root bindings in catalogued ladder operands.",
        "root_bound identifies a declaration; members, array bounds and access are not validated.",
        "Read/write effects and engineering purpose have not been analyzed.",
        "Expressions, dynamic addresses and uncatalogued instructions remain explicit gaps.",
        "", "Coverage:",
    ]
    lines.extend(f"  {key}: {value}" for key, value in payload["coverage"].items())
    lines.extend(["", "Declarations:"])
    for symbol in payload["symbols"]:
        lines.append(f"  {label(symbol['id'])} kind={symbol['kind']} scope={symbol['scope_id']}")
    lines.extend(["", "Aliases:"])
    for alias in payload["aliases"]:
        lines.extend([
            f"  {label(alias['source_id'])}: {alias['raw_target']} -> {alias['status']}",
            f"    terminal root: {label(alias['target_id'])}; suffix: {alias['suffix']}",
            f"    chain: {', '.join(alias['alias_chain']) or '(none)'}",
        ])
    lines.extend(["", "Operand occurrences (argument positions start at zero):"])
    for operand in payload["operands"]:
        lines.extend([
            f"  {operand['instruction_id']} argument {operand['argument_index']}: "
            f"{operand['raw_text']} -> {operand['status']}",
            f"    rung: {operand['rung_id']}; scope: {operand['scope_id']}",
            f"    declaration: {label(operand['symbol_id'])}",
            f"    terminal root: {label(operand['target_id'])}; suffix: {operand['suffix']}",
        ])
    lines.extend([
        "", "Repeated uses remain separate occurrences linked to the source inventory.",
        "IDs apply to this exact snapshot and are not persistent engineering-object IDs.",
        "Keep this report private. Use reference-summary for aggregate feedback.",
    ])
    return "\n".join(lines) + "\n"
