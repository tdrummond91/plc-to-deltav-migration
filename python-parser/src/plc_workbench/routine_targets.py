"""Private, bounded candidates for the first field of parsed RLL JSRs.

Routine names occupy their own program-local namespace. A unique declaration
candidate proves neither call legality nor parameter roles, execution, language
compatibility, or the validity of a controller identifier. Routine envelopes
remain candidates even when their language bodies are not modeled.
"""
from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from .models import EntityRecord, InventoryResult

MAX_ROUTINE_TARGET_OCCURRENCES = 250_000
MAX_ROUTINE_TARGET_EVIDENCE_CHARS = 8_000_000
MAX_ROUTINE_TARGET_NAME_LENGTH = 65_536
ROUTINE_TARGET_CONSTANTS = {
    'analysis_scope': 'parsed_rll_jsr_first_field_candidates',
    'parameter_roles': 'not_analyzed',
    'call_validation': 'not_analyzed',
}
ROUTINE_TARGET_STATUSES = frozenset({
    'unique_candidate', 'missing_candidate', 'ambiguous_candidate',
    'missing_target_field', 'empty_target_field', 'unsupported_target_name',
    'unsupported_context',
})
ROUTINE_TARGET_CONTEXTS = frozenset({
    'current_routine', 'main_routine', 'fault_routine', 'other_routine', 'not_analyzed',
})
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*', re.ASCII)


class RoutineTargetError(ValueError):
    """Fatal analysis rejection containing no source-controlled details."""


def _limit() -> None:
    raise RoutineTargetError('Routine target analysis exceeds its evidence limits.')


def _attribute_name_matches(value: str, normalized_name: str) -> bool:
    """Keep declaration attributes raw and exclude Unicode case lookalikes."""
    return _NAME.fullmatch(value) is not None and value.lower() == normalized_name


def build_routine_targets(inventory: InventoryResult) -> dict[str, Any]:
    """Retain one candidate row per ASCII JSR in a successfully parsed rung.

    Missing first fields take precedence over unsupported context, which takes
    precedence over empty or unsupported names. Only the first field is read;
    its whitespace is trimmed for lookup, while declaration Names are raw.
    Caller identity and explicit program attributes supply limited context;
    only Normal programs receive the other-routine fallback. Phase/sequence
    state names and legal phase subroutines are not inferred from spelling.
    """
    entities = {entity.id: entity for entity in inventory.entities}
    index: dict[tuple[str, str], list[EntityRecord]] = defaultdict(list)
    for entity in inventory.entities:
        if entity.kind != 'routine':
            continue
        program = entities.get(entity.parent_id)
        if (program is not None and program.kind == 'program'
                and entity.scope_id == program.id and entity.name is not None
                and _NAME.fullmatch(entity.name)):
            index[program.id, entity.name.lower()].append(entity)

    rows: list[dict[str, Any]] = []
    retained_characters = sum(map(len, ROUTINE_TARGET_CONSTANTS.values()))
    for rung in inventory.rungs:
        if rung.parse_status != 'parsed':
            continue
        caller = entities.get(rung.parent_id)
        owner = entities.get(caller.parent_id) if caller is not None else None
        supported = (caller is not None and caller.kind == 'routine'
                     and caller.attributes.get('Type') == 'RLL'
                     and owner is not None and owner.kind == 'program'
                     and caller.scope_id == owner.id and rung.scope_id == owner.id)
        for instruction in rung.instructions:
            if not instruction.opcode.isascii() or instruction.opcode.upper() != 'JSR':
                continue
            if len(rows) >= MAX_ROUTINE_TARGET_OCCURRENCES:
                _limit()
            raw = instruction.arguments[0] if instruction.arguments else None
            row: dict[str, Any] = {
                'instruction_id': instruction.id, 'rung_id': rung.id,
                'caller_routine_id': rung.parent_id,
                'program_id': owner.id if supported else None,
                'raw_target_name': raw, 'status': 'missing_target_field',
                'candidate_count': 0, 'target_routine_id': None,
                'target_context': 'not_analyzed',
            }
            if raw is not None:
                if len(raw) > MAX_ROUTINE_TARGET_NAME_LENGTH:
                    _limit()
                name = raw.strip()
                if not supported:
                    row['status'] = 'unsupported_context'
                elif not name:
                    row['status'] = 'empty_target_field'
                elif not _NAME.fullmatch(name):
                    row['status'] = 'unsupported_target_name'
                else:
                    candidates = index.get((owner.id, name.lower()), [])
                    row['candidate_count'] = len(candidates)
                    if not candidates:
                        row['status'] = 'missing_candidate'
                    elif len(candidates) != 1:
                        row['status'] = 'ambiguous_candidate'
                    else:
                        target = candidates[0]
                        row['status'] = 'unique_candidate'
                        row['target_routine_id'] = target.id
                        if target.id == caller.id:
                            row['target_context'] = 'current_routine'
                        elif _attribute_name_matches(owner.attributes.get('MainRoutineName', ''), name.lower()):
                            row['target_context'] = 'main_routine'
                        elif _attribute_name_matches(owner.attributes.get('FaultRoutineName', ''), name.lower()):
                            row['target_context'] = 'fault_routine'
                        elif owner.attributes.get('Type') == 'Normal':
                            row['target_context'] = 'other_routine'
            retained_characters += sum(len(value) for value in row.values() if type(value) is str)
            if retained_characters > MAX_ROUTINE_TARGET_EVIDENCE_CHARS:
                _limit()
            rows.append(row)
    return {**ROUTINE_TARGET_CONSTANTS, 'occurrences': rows}
