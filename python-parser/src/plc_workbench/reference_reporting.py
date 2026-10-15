"""Private views of snapshot-bound root bindings, with explicit limits."""

from __future__ import annotations

import json

from .models import InventoryResult
from .references import ReferenceResult
from .routine_metadata import build_routine_target_metadata
from .routine_shapes import build_routine_instruction_shapes


def render_reference_json(result: ReferenceResult) -> str:
    """Serialize private evidence; never send this payload to the public writer."""
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n"


def render_reference_text(result: ReferenceResult, *, inventory: InventoryResult | None = None) -> str:
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
        "ABS/LN/SQR slots receive lexical root/literal classification; math, domains, types and destination access are not validated.",
        "MVM data slots and SWPB source/destination slots receive lexical root/literal classification.",
        "SWPB order-mode selector slot 1 is non_data; raw text is retained and selector values are not validated.",
        "Mask widths, byte order, data types and destination access are not validated.",
        "system_flag identifies the direct S:FS instruction operand in XIC/XIO.",
        "No runtime first-scan value or execution behavior is simulated.",
        "Read/write effects and engineering purpose have not been analyzed.",
        "Expressions, dynamic addresses and uncatalogued instructions remain explicit gaps.",
        "", "Coverage:",
    ]
    lines.extend(f"  {key}: {value}" for key, value in payload["coverage"].items())
    if inventory is not None:
        shapes = build_routine_instruction_shapes(inventory)
        lines.extend([
            "", "Parsed RLL routine instruction field shapes (observations only):",
            "Parameter roles are not analyzed; first-field JSR candidates are listed separately.",
            "Second-zero buckets mean the trimmed second field is exactly ASCII 0; its meaning is unknown.",
        ])
        for opcode, group in shapes['by_opcode'].items():
            lines.append(f"  {opcode}: total={group['total']} argument_slots={group['argument_slots']} "
                         f"noncanonical_spelling={group['noncanonical_spelling']}")
            lines.extend(f"    {bucket}: {count}" for bucket, count in group['by_arity'].items())
    lines.extend(["", "Declarations:"])
    for symbol in payload["symbols"]:
        lines.extend([
            f"  {label(symbol['id'])} kind={symbol['kind']} scope={symbol['scope_id']}",
            f"    name origin: {symbol['name_origin']}; "
            f"name reason: {symbol['name_reason'] or '(none)'}",
        ])
    lines.extend(["", "Aliases:"])
    for alias in payload["aliases"]:
        lines.extend([
            f"  {label(alias['source_id'])}: {alias['raw_target']} -> {alias['status']}",
            f"    reason: {alias['reason'] or '(none)'}",
            f"    terminal root: {label(alias['target_id'])}; suffix: {alias['suffix']}",
            f"    chain: {', '.join(alias['alias_chain']) or '(none)'}",
        ])
    lines.extend(["", "Operand occurrences (argument positions start at zero):"])
    for operand in payload["operands"]:
        lines.extend([
            f"  {operand['instruction_id']} argument {operand['argument_index']}: "
            f"{operand['raw_text']} -> {operand['status']}",
            f"    reason: {operand['reason'] or '(none)'}",
            f"    rung: {operand['rung_id']}; scope: {operand['scope_id']}",
            f"    declaration: {label(operand['symbol_id'])}",
            f"    terminal root: {label(operand['target_id'])}; suffix: {operand['suffix']}",
        ])
    lines.extend([
        "", "JSR first-field routine candidates (separate routine namespace):",
        "Candidates identify program-local routine envelopes; call legality and parameter roles are not analyzed.",
        "Context uses caller identity and explicit program attributes; other_routine requires a Normal program.",
        "Phase and sequence states are not inferred from routine names.",
    ])
    for occurrence in payload['routine_targets']['occurrences']:
        lines.extend([
            f"  {occurrence['instruction_id']}: {occurrence['raw_target_name']!r} -> {occurrence['status']}",
            f"    rung: {occurrence['rung_id']}; caller: {occurrence['caller_routine_id']}; "
            f"program: {occurrence['program_id']}",
            f"    candidate count: {occurrence['candidate_count']}; "
            f"target routine: {occurrence['target_routine_id'] or '(none)'}; "
            f"context: {occurrence['target_context']}",
        ])
    if inventory is not None:
        metadata = build_routine_target_metadata(inventory, payload['routine_targets'])
        lines.extend([
            "", "Unique JSR candidate metadata (call-weighted observations only):",
            "Program Type semantics and target execution are not analyzed.",
            "Missing, empty and explicit Type attributes are distinct; language envelopes do not prove executable bodies.",
            f"  total: {metadata['total']}",
        ])
        for group in ('by_program_type', 'by_target_language', 'unclassified_context_by_program_type'):
            lines.append(f"  {group}:")
            lines.extend(f"    {bucket}: {count}" for bucket, count in metadata[group].items())
    graph = payload['routine_graph']
    entities = {entity.id: entity for entity in inventory.entities} if inventory is not None else {}

    def routine_label(entity_id: str) -> str:
        entity = entities.get(entity_id)
        return f"{entity.name!r} [{entity_id}]" if entity is not None else entity_id

    lines.extend([
        "", "Declared program-local JSR candidate graph:",
        "Edges group unique declaration candidates and retain every parsed JSR instruction ID.",
        "Execution, scheduling, call legality and parameter semantics are not analyzed.",
        "Cycles describe candidate edges only; unmodeled or partial bodies are not proven terminal routines.",
        "Main designations use raw program attributes and do not establish runtime entry or reachability.",
        "  Routine nodes:",
    ])
    for node in graph['nodes']:
        lines.append(f"    {routine_label(node['routine_id'])}; program: {routine_label(node['program_id'])}; "
                     f"language: {node['language']}; body: {node['body_status']}; rungs: {node['rung_counts']}")
    lines.append("  Grouped candidate edges:")
    for edge in graph['edges']:
        lines.extend([
            f"    {routine_label(edge['caller_routine_id'])} -> {routine_label(edge['target_routine_id'])}; "
            f"program: {routine_label(edge['program_id'])}",
            f"      instruction IDs: {', '.join(edge['instruction_ids'])}",
        ])
    lines.append(f"  Unlinked JSR instruction IDs: {', '.join(graph['unlinked_instruction_ids']) or '(none)'}")
    lines.append("  Main designations:")
    for designation in graph['main_designations']:
        target = designation['target_routine_id']
        lines.append(f"    {routine_label(designation['program_id'])}: {designation['raw_name']!r} "
                     f"-> {designation['status']}; candidates: {designation['candidate_count']}; "
                     f"target: {routine_label(target) if target is not None else '(none)'}")
    lines.append("  Candidate cyclic components:")
    if not graph['cyclic_components']:
        lines.append("    (none)")
    for component in graph['cyclic_components']:
        lines.append(f"    {', '.join(routine_label(entity_id) for entity_id in component)}")
    lines.extend(["", "Rack logical-root candidates (backing mapping not analyzed):",
                  "Candidate matches do not change declared root bindings.",
                  "candidate_names_unavailable means matching is inconclusive."])
    for candidate in payload["rack_candidates"]["candidates"]:
        lines.extend([
            f"  {candidate['source_id']}: {candidate['name'] or '(unavailable)'} "
            f"direction={candidate['direction']} scope={candidate['scope_id']}",
            f"    module: {candidate['module_id']}; connection: {candidate['connection_id']}",
            f"    name origin: {candidate['name_origin']}; reason: {candidate['reason'] or '(none)'}",
        ])
    for group, matches in payload["rack_candidates"]["matches"].items():
        lines.append(f"  Candidate lookups: {group}")
        for match in matches:
            lines.extend([
                f"    {match['source_id']}: {match['terminal_root']} -> {match['status']}",
                f"      lookup scope: {match['lookup_scope_id']}; count: {match['candidate_count']}; "
                f"candidate: {match['candidate_id'] or '(none)'}",
            ])
    lines.extend([
        "", "Repeated uses remain separate occurrences linked to the source inventory.",
        "IDs apply to this exact snapshot and are not persistent engineering-object IDs.",
        "Keep this report private. Use reference-summary for aggregate feedback.",
    ])
    return "\n".join(lines) + "\n"
