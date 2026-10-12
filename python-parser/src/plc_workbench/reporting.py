"""Private readable and JSON views over the same inventory records."""

from __future__ import annotations

import json
from typing import Any, Protocol


class InventoryView(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


class ReportError(ValueError):
    """A safe report-selection error, without reflecting the user's input."""


def _selected_payload(result: InventoryView, rung_id: str | None) -> dict[str, Any]:
    payload = result.to_dict()
    if rung_id is None:
        return payload
    matches = [rung for rung in payload["rungs"] if rung["id"] == rung_id]
    if len(matches) != 1:
        raise ReportError("Rung ID is not unique in this source snapshot or was not found.")
    rung = matches[0]
    return {
        key: payload[key]
        for key in (
            "schema_version", "parser_version", "analysis_scope",
            "semantic_analysis", "snapshot", "status",
        )
    } | {
        "rung": rung,
        "diagnostics": [
            item for item in payload["diagnostics"]
            if item["source_id"] == rung_id or item["locator"] == rung["locator"]
        ],
    }


def render_json(result: InventoryView, rung_id: str | None = None) -> str:
    """Return private data; no sanitization or public-output promise is made."""
    return json.dumps(_selected_payload(result, rung_id), indent=2, ensure_ascii=False) + "\n"


def _scalar(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _field_lines(values: dict[str, Any], indent: int = 2) -> list[str]:
    lines = []
    prefix = " " * indent
    for key, value in values.items():
        if isinstance(value, dict) and value:
            lines.append(f"{prefix}{key}:")
            lines.extend(_field_lines(value, indent + 2))
        elif isinstance(value, list) and value:
            lines.append(f"{prefix}{key}:")
            lines.extend(f"{prefix}  {_scalar(item)}" for item in value)
        else:
            lines.append(f"{prefix}{key}: {_scalar(value)}")
    return lines


def render_text(result: InventoryView, rung_id: str | None = None) -> str:
    payload = _selected_payload(result, rung_id)
    lines = [
        "PRIVATE L5X source inventory",
        f"Status: {payload['status']}",
        f"Snapshot: {payload['snapshot']['id']}",
        f"Source bytes: {payload['snapshot']['size_bytes']}",
        "Scope: source structure only; engineering purpose has not been analyzed.",
        "Instruction counts describe parsed outer syntax, not validated PLC behavior.",
        "",
    ]
    if rung_id is not None:
        rung = payload["rung"]
        lines.extend([
            f"Rung ID: {rung['id']}",
            f"Locator: {rung['locator']}",
            f"Number: {rung['number']}",
            f"Type: {rung['type']}",
            f"Parse status: {rung['parse_status']}",
            f"Scope ID: {rung['scope_id']}",
            "Text:", rung["text"] or "(no text)", "", "Instructions:",
        ])
        for instruction in rung["instructions"]:
            lines.append(
                f"  {instruction['opcode']} {json.dumps(instruction['arguments'], ensure_ascii=False)}"
                f" [{instruction['start']}:{instruction['end']}]"
            )
        if not rung["instructions"]:
            lines.append("  (none recovered)")
        if rung.get("metrics"):
            lines.extend(["", "Structural measurements:"])
            lines.extend(f"  {key}: {_scalar(value)}" for key, value in rung["metrics"].items())
    else:
        for heading, field in (
            ("Inventory counts", "counts"),
            ("Routine types", "routine_types"),
            ("Structural coverage", "coverage"),
            ("Known instruction counts", "instruction_counts"),
        ):
            lines.append(f"{heading}:")
            lines.extend(_field_lines(payload[field]))
            if not payload[field]:
                lines.append("  (none)")
            lines.append("")
    lines.extend(["", "Gaps and findings:"])
    for diagnostic in payload["diagnostics"]:
        lines.append(
            f"  [{diagnostic['severity']}] {diagnostic['code']}"
            f" at {diagnostic['locator']}: {diagnostic['message']}"
        )
    if not payload["diagnostics"]:
        lines.append("  No structural diagnostics. Engineering purpose remains unclassified.")
    lines.extend([
        "", "No tag/reference resolution, alarm consequences, PID relationships,",
        "equipment/sequence classification, PCSD or FHX generation is implemented.",
        "Keep this report and its source identifiers in an approved private location.",
    ])
    return "\n".join(lines) + "\n"
