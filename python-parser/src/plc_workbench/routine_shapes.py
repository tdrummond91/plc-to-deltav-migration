"""Count parsed RLL routine-instruction fields without interpreting their roles.

Only closed counters leave this module. Names, argument values, identities and
per-occurrence links remain in the private source inventory. The second-field
zero buckets describe exact trimmed spelling, not an input count or call validity.
"""
from __future__ import annotations

from typing import Any

from .models import InventoryResult

MAX_COUNT = 10**12
ROUTINE_OPCODES = ('JSR', 'SBR', 'RET')
SHAPE_CONSTANTS = {
    'analysis_scope': 'parsed_rll_routine_instruction_fields',
    'parameter_roles': 'not_analyzed',
    'target_resolution': 'not_analyzed',
}
JSR_ARITY_BINS = (
    'zero_fields', 'one_field', 'two_fields_second_zero', 'two_fields_second_other',
    'three_or_more_second_zero', 'three_or_more_second_other',
)
OTHER_ARITY_BINS = ('zero_fields', 'one_field', 'two_fields', 'three_or_more')


class RoutineShapeError(ValueError):
    """Rejection whose fixed message contains no source-controlled details."""


def _invalid() -> None:
    raise RoutineShapeError('Routine instruction shape validation failed.')


def _count(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= MAX_COUNT:
        _invalid()
    return value


def _keys(value: Any, expected: set[str]) -> None:
    if type(value) is not dict or value.keys() != expected:
        _invalid()


def build_routine_instruction_shapes(inventory: InventoryResult) -> dict[str, Any]:
    """Observe successful RLL parser records; never bind or reinterpret a field."""
    groups = {
        opcode: {
            'total': 0, 'argument_slots': 0, 'noncanonical_spelling': 0,
            'by_arity': dict.fromkeys(JSR_ARITY_BINS if opcode == 'JSR' else OTHER_ARITY_BINS, 0),
        }
        for opcode in ROUTINE_OPCODES
    }
    for rung in inventory.rungs:
        if rung.parse_status != 'parsed':
            continue
        for instruction in rung.instructions:
            # Keep normalization ASCII-only; this is the parser's opcode grammar.
            opcode = instruction.opcode.upper() if instruction.opcode.isascii() else ''
            if opcode not in groups:
                continue
            group = groups[opcode]
            arity = len(instruction.arguments)
            if arity == 0:
                bucket = 'zero_fields'
            elif arity == 1:
                bucket = 'one_field'
            elif opcode == 'JSR':
                size = 'two_fields' if arity == 2 else 'three_or_more'
                spelling = 'zero' if instruction.arguments[1].strip() == '0' else 'other'
                bucket = f'{size}_second_{spelling}'
            else:
                bucket = 'two_fields' if arity == 2 else 'three_or_more'
            group['total'] += 1
            group['argument_slots'] += arity
            group['noncanonical_spelling'] += int(instruction.opcode != opcode)
            group['by_arity'][bucket] += 1
    return {**SHAPE_CONSTANTS, 'by_opcode': groups}


def validate_routine_instruction_shapes(
    value: Any, *, source_summary: dict[str, Any], instructions_catalogued: int,
    operands_total: int, unsupported_instruction_slots: int,
) -> None:
    """Check the closed shape and reconcile its limits with validated aggregates.

    Public counts bound these observations; canonical private reanalysis proves
    their source provenance. The withheld opcode bucket supplies only a shared
    upper bound for noncanonical spellings, never a new public opcode label.
    """
    _keys(value, set(SHAPE_CONSTANTS) | {'by_opcode'})
    for key, fixed in SHAPE_CONSTANTS.items():
        if type(value[key]) is not str or value[key] != fixed:
            _invalid()
    groups = value['by_opcode']
    _keys(groups, set(ROUTINE_OPCODES))
    try:
        source_total = _count(source_summary['counts']['instructions'])
        source_opcodes = source_summary['instructions']['counts']
        if type(source_opcodes) is not dict:
            _invalid()
        withheld = _count(source_opcodes['withheld'])
    except (KeyError, TypeError):
        _invalid()
    catalogued = _count(instructions_catalogued)
    operands = _count(operands_total)
    unsupported_slots = _count(unsupported_instruction_slots)
    total = slots = noncanonical = 0
    for opcode in ROUTINE_OPCODES:
        group = groups[opcode]
        _keys(group, {'total', 'argument_slots', 'noncanonical_spelling', 'by_arity'})
        group_total = _count(group['total'])
        group_slots = _count(group['argument_slots'])
        spelling_count = _count(group['noncanonical_spelling'])
        bins = group['by_arity']
        expected = JSR_ARITY_BINS if opcode == 'JSR' else OTHER_ARITY_BINS
        _keys(bins, set(expected))
        for count in bins.values():
            _count(count)
        two = sum(bins[key] for key in expected if key.startswith('two_fields'))
        larger = sum(bins[key] for key in expected if key.startswith('three_or_more'))
        minimum_slots = bins['one_field'] + 2 * two + 3 * larger
        if (group_total != sum(bins.values()) or spelling_count > group_total
                or group_slots < minimum_slots
                or (larger == 0 and group_slots != minimum_slots)
                or group_total != _count(source_opcodes.get(opcode, 0)) + spelling_count):
            _invalid()
        total += group_total
        slots += group_slots
        noncanonical += spelling_count
    if (catalogued > source_total or total > source_total - catalogued
            or noncanonical > withheld or slots > operands or slots > unsupported_slots):
        _invalid()
