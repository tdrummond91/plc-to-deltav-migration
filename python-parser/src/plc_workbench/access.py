"""Bounded possible explicit RLL operand access, independent of execution.

Roles do not prove an instruction executes, an operand is type-correct, a member
exists, or two suffixes overlap. Only existing canonical root bindings are used.
Implicit effects and dependencies are outside this deliberately narrow catalog.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from io import StringIO
import json
from typing import Any

from .models import InventoryResult
from .references import (
    MAX_OPERANDS, ReferenceResult, _strict_record_match, validate_references,
)

MAX_INSTRUCTIONS = 250_000
MAX_ACCESS_BYTES = 32 * 1024 * 1024
INSTRUCTION_STATUSES = frozenset({
    'classified', 'unsupported_instruction', 'argument_count_mismatch', 'empty_argument',
})
OPERAND_ROLES = frozenset({'read', 'write', 'read_write', 'non_data', 'unknown'})
INDEXED_ROLES = frozenset({'read', 'write', 'read_write', 'unknown'})
ACCESS_CONSTANTS = {
    'schema_version': 1,
    'analyzer_version': 'instruction-access-1',
    'analysis_scope': 'explicit_rll_operand_roles',
    'execution_analysis': 'not_implemented',
    'member_validation': 'not_implemented',
    'implicit_effects': 'not_analyzed',
}
COVERAGE_KEYS = frozenset({
    'instructions_total', 'instructions_by_status', 'operands_total', 'operands_by_role',
    'bound_by_role', 'linked_operands', 'unlinked_operands', 'indexed_roots',
    'source_rungs', 'unparsed_rungs', 'access_gap_operands',
})

# These spellings already have reference contracts. Retention is not an explicit
# read for OTL/OTU. MVM conservatively reads the whole destination because its
# unmasked bits are retained; masks and individual bits are never evaluated.
_ROLES = {
    **dict.fromkeys(('XIC', 'XIO'), ('read',)),
    **dict.fromkeys(('OTE', 'OTL', 'OTU', 'CLR'), ('write',)),
    'ONS': ('read_write',),
    **dict.fromkeys(('OSR', 'OSF'), ('read_write', 'write')),
    'MOV': ('read', 'write'),
    'MVM': ('read', 'read', 'read_write'),
    'SWPB': ('read', 'non_data', 'write'),
    **dict.fromkeys(('ADD', 'SUB', 'MUL', 'DIV'), ('read', 'read', 'write')),
    **dict.fromkeys(('ABS', 'LN', 'SQR'), ('read', 'write')),
    **dict.fromkeys(('EQU', 'NEQ', 'LES', 'LEQ', 'GRT', 'GEQ'), ('read', 'read')),
    'LIM': ('read', 'read', 'read'),
    **dict.fromkeys(('JMP', 'LBL'), ('non_data',)),
}
_REASONS = {
    'classified': 'catalogued_slot',
    'unsupported_instruction': 'instruction_not_supported',
    'argument_count_mismatch': 'argument_count_mismatch',
    'empty_argument': 'empty_argument',
}


class AccessError(ValueError):
    """Analysis rejection containing no source-controlled evidence."""


@dataclass(frozen=True)
class AccessResult:
    snapshot: dict[str, str | int]
    status: str
    instructions: list[dict[str, Any]]
    operands: list[dict[str, Any]]
    roots: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'instruction-access-1'
    analysis_scope: str = 'explicit_rll_operand_roles'
    execution_analysis: str = 'not_implemented'
    member_validation: str = 'not_implemented'
    implicit_effects: str = 'not_analyzed'

    def to_dict(self) -> dict[str, Any]:
        """Return private source-linked evidence; this is not a public report."""
        return asdict(self)


def _invalid() -> None:
    raise AccessError('Access records do not match the source evidence.')


def _limit() -> None:
    raise AccessError('Access analysis exceeds its evidence limits.')


def _check_limits(inventory: InventoryResult, references: ReferenceResult) -> None:
    if type(inventory) is not InventoryResult or type(references) is not ReferenceResult:
        _invalid()
    if type(references.operands) is not list:
        _invalid()
    if len(references.operands) > MAX_OPERANDS:
        _limit()
    instruction_total = operand_total = 0
    for rung in inventory.rungs:
        if rung.parse_status == 'parsed':
            instruction_total += len(rung.instructions)
            if instruction_total > MAX_INSTRUCTIONS:
                _limit()
            for instruction in rung.instructions:
                operand_total += len(instruction.arguments)
                if operand_total > MAX_OPERANDS:
                    _limit()


def _derive_access(inventory: InventoryResult, references: ReferenceResult) -> AccessResult:
    """Consume authenticated references in their canonical occurrence order."""
    instructions: list[dict[str, Any]] = []
    operands: list[dict[str, Any]] = []
    roots: dict[str, dict[str, Any]] = {}
    instruction_counts = dict.fromkeys(sorted(INSTRUCTION_STATUSES), 0)
    role_counts = dict.fromkeys(sorted(OPERAND_ROLES), 0)
    bound_counts = dict.fromkeys(sorted(OPERAND_ROLES), 0)
    source_operands = iter(references.operands)
    unparsed_rungs = access_gaps = 0
    for rung in inventory.rungs:
        if rung.parse_status != 'parsed':
            unparsed_rungs += 1
            continue
        for instruction in rung.instructions:
            opcode = instruction.opcode
            slots = _ROLES.get(opcode.upper()) if opcode.isascii() else None
            status = ('unsupported_instruction' if slots is None else
                      'argument_count_mismatch' if len(instruction.arguments) != len(slots) else
                      'empty_argument' if any(not arg.strip() for arg in instruction.arguments) else
                      'classified')
            instruction_counts[status] += 1
            operand_ids: list[str] = []
            for index, _ in enumerate(instruction.arguments):
                reference = next(source_operands)
                role = slots[index] if status == 'classified' else 'unknown'
                operand = {
                    'id': reference['id'], 'instruction_id': instruction.id,
                    'rung_id': rung.id, 'argument_index': index,
                    'role': role, 'reason': _REASONS[status],
                    'binding_status': reference['status'],
                    'symbol_id': reference['symbol_id'], 'target_id': reference['target_id'],
                    'suffix': reference['suffix'],
                }
                operands.append(operand)
                operand_ids.append(operand['id'])
                role_counts[role] += 1
                if reference['status'] == 'root_bound':
                    bound_counts[role] += 1
                    if role in INDEXED_ROLES:
                        target_id = reference['target_id']
                        if target_id not in roots:
                            roots[target_id] = {'target_id': target_id, **{
                                f'{item}_operand_ids': [] for item in sorted(INDEXED_ROLES)
                            }}
                        roots[target_id][f'{role}_operand_ids'].append(operand['id'])
                if (role == 'read' and reference['status'] not in
                        {'root_bound', 'literal', 'system_flag'} or
                        role in {'write', 'read_write'} and reference['status'] != 'root_bound'):
                    access_gaps += 1
            instructions.append({
                'id': instruction.id, 'rung_id': rung.id, 'opcode': opcode,
                'status': status, 'operand_ids': operand_ids,
            })
    linked = sum(bound_counts[role] for role in INDEXED_ROLES)
    coverage = {
        'instructions_total': len(instructions), 'instructions_by_status': instruction_counts,
        'operands_total': len(operands), 'operands_by_role': role_counts,
        'bound_by_role': bound_counts, 'linked_operands': linked,
        'unlinked_operands': len(operands) - linked, 'indexed_roots': len(roots),
        'source_rungs': len(inventory.rungs), 'unparsed_rungs': unparsed_rungs,
        'access_gap_operands': access_gaps,
    }
    partial = bool(unparsed_rungs or access_gaps or any(
        count for key, count in instruction_counts.items() if key != 'classified'))
    return AccessResult(dict(inventory.snapshot), 'partial' if partial else 'complete',
                        instructions, operands, list(roots.values()), coverage)


def analyze_access(inventory: InventoryResult, references: ReferenceResult) -> AccessResult:
    """Classify possible explicit operand roles against canonical references.

    The caller authenticates inventory against its byte snapshot. This layer
    authenticates references against that inventory and does no source IO.
    """
    try:
        _check_limits(inventory, references)
        validate_references(inventory, references)
        result = _derive_access(inventory, references)
        render_access_json(result)
        return result
    except AccessError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, StopIteration):
        _invalid()


def validate_access(inventory: InventoryResult, references: ReferenceResult,
                    result: AccessResult) -> None:
    """Reject every deviation from canonical access, without copying a candidate."""
    try:
        expected = analyze_access(inventory, references)
        valid = (type(result) is AccessResult
                 and _strict_record_match(vars(expected), vars(result)))
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError):
        valid = False
    if not valid:
        _invalid()


def render_access_json(result: AccessResult) -> str:
    """Render bounded private JSON; source-bound validation is validate_access.

    Preflight only plain built-ins, fixed nesting depth and bounded content before
    JSON encoding. This also rejects cycles and custom objects without invoking
    their equality, deepcopy, iteration or serialization hooks.
    """
    if type(result) is not AccessResult:
        _invalid()
    try:
        data = vars(result)
        if data.keys() != set(AccessResult.__dataclass_fields__):
            _invalid()
        stack = [iter((data,))]
        exhausted = object()
        budget = MAX_ACCESS_BYTES
        while stack:
            item = next(stack[-1], exhausted)
            if item is exhausted:
                stack.pop()
                continue
            budget -= 1
            if budget < 0 or len(stack) > 12:
                _limit()
            if type(item) is dict:
                if any(type(key) is not str for key in item):
                    _invalid()
                budget -= sum(len(key) for key in item)
                stack.append(iter(item.values()))
            elif type(item) is list:
                if len(item) > max(MAX_OPERANDS, MAX_INSTRUCTIONS):
                    _limit()
                stack.append(iter(item))
            elif type(item) is str:
                budget -= len(item)
            elif type(item) not in {int, type(None)}:
                _invalid()
            if budget < 0:
                _limit()
        output = StringIO()
        size = 0
        for chunk in json.JSONEncoder(ensure_ascii=True, sort_keys=True, indent=2).iterencode(data):
            size += len(chunk)  # ensure_ascii makes character and UTF-8 byte counts equal.
            if size + 1 > MAX_ACCESS_BYTES:
                _limit()
            output.write(chunk)
        output.write('\n')
        return output.getvalue()
    except AccessError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
