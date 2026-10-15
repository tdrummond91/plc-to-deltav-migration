"""Bounded possible explicit RLL operand access, independent of execution.

Roles do not prove an instruction executes, an operand is type-correct, a member
exists, or two suffixes overlap. Version 3 adds explicit, separately attributed
root resolution for selected slots without changing historical references.
Version 4 consumes authenticated calculation2 evidence, preserving source slots
and expression reference occurrences as distinct possible-access records.
Implicit effects and dependencies are outside this deliberately narrow catalog.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from io import StringIO
import json
import re
from typing import Any

from .calculations import CalculationResult, validate_calculations
from .models import InventoryResult, SourceSnapshot
from .references import (
    ALIAS_STATUSES, MAX_EXPANDED_EVIDENCE_CHARS, MAX_OPERANDS, ReferenceResult, _Resolver, _binding, _literal,
    _strict_record_match, validate_references,
)

MAX_INSTRUCTIONS = 250_000
MAX_ACCESS_BYTES = 32 * 1024 * 1024
MAX_EXPRESSION_USES = 250_000
INSTRUCTION_STATUSES = frozenset({
    'classified', 'unsupported_instruction', 'argument_count_mismatch', 'empty_argument',
    'unsupported_operand_form',
})
OPERAND_ROLES = frozenset({'read', 'write', 'read_write', 'non_data', 'unknown'})
OPERAND_ROLES_V4 = OPERAND_ROLES | {'expression_read'}
EXPRESSION_STATUSES = frozenset({'parsed', 'unsupported'})
INDEXED_ROLES = frozenset({'read', 'write', 'read_write', 'unknown'})
ACCESS2_CONSTANTS = {
    'schema_version': 2,
    'analyzer_version': 'instruction-access-2',
    'analysis_scope': 'explicit_rll_operand_roles',
    'execution_analysis': 'not_implemented',
    'member_validation': 'not_implemented',
    'implicit_effects': 'not_analyzed',
    'initialization_analysis': 'not_implemented',
    'range_analysis': 'not_implemented',
}
ACCESS_CONSTANTS = {
    **ACCESS2_CONSTANTS, 'schema_version': 3, 'analyzer_version': 'instruction-access-3',
}
ACCESS4_CONSTANTS = {
    **ACCESS_CONSTANTS, 'schema_version': 4, 'analyzer_version': 'instruction-access-4',
}
COVERAGE_KEYS_V2 = frozenset({
    'instructions_total', 'instructions_by_status', 'operands_total', 'operands_by_role',
    'bound_by_role', 'linked_operands', 'unlinked_operands', 'indexed_roots',
    'source_rungs', 'unparsed_rungs', 'access_gap_operands',
    'timer_instructions', 'timer_pseudo_operands_by_kind',
})
COVERAGE_KEYS = COVERAGE_KEYS_V2 | frozenset({
    'extended_instructions', 'counter_pseudo_operands_by_kind',
    'counter_invalid_forms', 'extended_bound_operands',
})
COVERAGE_KEYS_V4 = COVERAGE_KEYS | frozenset({
    'calculation_instructions', 'expression_containers_by_status', 'expression_uses_total',
    'expression_uses_by_binding', 'expression_indexed_roots', 'expressions_with_binding_gaps',
})
EXTENDED_FAMILIES = frozenset({
    'counter', 'message', 'system_get', 'system_set', 'sfc_reset_step', 'sfc_reset_initial',
})

# These spellings already have reference contracts. Retention is not an explicit
# read for OTL/OTU. MVM conservatively reads the whole destination because its
# unmasked bits are retained; masks and individual bits are never evaluated.
# RES records a possible write to selected fields, not a whole-object clear.
# COP/CPS slots do not expand copied ranges or claim overlap/synchronization.
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
    **dict.fromkeys(('TON', 'TOF', 'RTO'), ('read_write', 'non_data', 'non_data')),
    'RES': ('write',),
    **dict.fromkeys(('COP', 'CPS'), ('read', 'write', 'read')),
}
_TIMER_OPCODES = frozenset({'TON', 'TOF', 'RTO'})
_COUNTER_OPCODES = frozenset({'CTU', 'CTD'})
_EXTENDED_ROLES = {
    **dict.fromkeys(('CTU', 'CTD'), ('read_write', 'non_data', 'non_data')),
    'MSG': ('read_write',),
    'GSV': ('non_data', 'non_data', 'non_data', 'write'),
    'SSV': ('non_data', 'non_data', 'non_data', 'read'),
    'SFR': ('non_data', 'write'),
}
_EXTENDED_FAMILY = {
    'CTU': 'counter', 'CTD': 'counter', 'MSG': 'message',
    'GSV': 'system_get', 'SSV': 'system_set', 'SFR': 'sfc_reset_step',
}
TIMER_PSEUDO_KINDS = frozenset({'placeholder', 'integer_literal'})
# Lexical exported pseudo-fields only: no value conversion, width/range check,
# initialization model, or runtime reads. Decimal underscores are not admitted;
# radix underscores have the same digit-separated grammar as references._NUMBER.
_INTEGER_IMMEDIATE = re.compile(
    r'[+-]?(?:[0-9]+|2#[01](?:_?[01])*|8#[0-7](?:_?[0-7])*'
    r'|16#[0-9A-Fa-f](?:_?[0-9A-Fa-f])*)', re.ASCII,
)
_REASONS = {
    'classified': 'catalogued_slot',
    'unsupported_instruction': 'instruction_not_supported',
    'argument_count_mismatch': 'argument_count_mismatch',
    'empty_argument': 'empty_argument',
    'unsupported_operand_form': 'unsupported_operand_form',
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
    schema_version: int = 3
    analyzer_version: str = 'instruction-access-3'
    analysis_scope: str = 'explicit_rll_operand_roles'
    execution_analysis: str = 'not_implemented'
    member_validation: str = 'not_implemented'
    implicit_effects: str = 'not_analyzed'
    initialization_analysis: str = 'not_implemented'
    range_analysis: str = 'not_implemented'
    expression_uses: list[dict[str, Any]] = field(default_factory=list)
    expression_roots: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return private source-linked evidence; this is not a public report."""
        render_access_json(self)
        data = _project_data(self)
        # Preflight admits only native containers, so this cannot invoke a
        # caller's deepcopy hooks. Keep historical field order as well as data.
        return deepcopy(data)


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


def _timer_pseudo_kind(raw: str) -> str | None:
    value = raw.strip()
    if value == '?':
        return 'placeholder'
    return 'integer_literal' if _INTEGER_IMMEDIATE.fullmatch(value) else None


def _derive_access(inventory: InventoryResult, references: ReferenceResult,
                   schema_version: int, calculations: CalculationResult | None = None) -> AccessResult:
    """Consume authenticated references in their canonical occurrence order."""
    instructions: list[dict[str, Any]] = []
    operands: list[dict[str, Any]] = []
    roots: dict[str, dict[str, Any]] = {}
    instruction_counts = dict.fromkeys(sorted(INSTRUCTION_STATUSES), 0)
    role_vocabulary = OPERAND_ROLES_V4 if schema_version == 4 else OPERAND_ROLES
    role_counts = dict.fromkeys(sorted(role_vocabulary), 0)
    bound_counts = dict.fromkeys(sorted(role_vocabulary), 0)
    timer_pseudo_counts = dict.fromkeys(sorted(TIMER_PSEUDO_KINDS), 0)
    counter_pseudo_counts = dict.fromkeys(sorted(TIMER_PSEUDO_KINDS), 0)
    extended_counts = dict.fromkeys(sorted(EXTENDED_FAMILIES), 0)
    counter_invalid_forms = extended_bound = 0
    expanded_characters = 0
    retained_bytes = 0
    expression_uses: list[dict[str, Any]] = []
    expression_roots: dict[str, dict[str, Any]] = {}
    expression_counts = dict.fromkeys(sorted(EXPRESSION_STATUSES), 0)
    expression_bindings = dict.fromkeys(sorted(ALIAS_STATUSES), 0)
    expression_gaps = 0
    calculation_by_id = {row['id']: row for row in calculations.occurrences} if calculations else {}
    nodes_by_id = {row['id']: row for row in calculations.nodes} if calculations else {}

    def charge_record(record: dict[str, Any]) -> None:
        nonlocal retained_bytes
        if schema_version == 4:
            retained_bytes += len(json.dumps(record, ensure_ascii=True))
            if retained_bytes > MAX_ACCESS_BYTES:
                _limit()

    def charge_binding(binding: dict[str, Any]) -> None:
        nonlocal expanded_characters
        if schema_version >= 3:
            expanded_characters += len(binding['suffix']) + sum(map(len, binding['alias_chain']))
            if expanded_characters > MAX_EXPANDED_EVIDENCE_CHARS:
                _limit()
    resolver: _Resolver | None = None
    source_operands = iter(references.operands)
    unparsed_rungs = access_gaps = timer_instructions = 0
    for rung in inventory.rungs:
        if rung.parse_status != 'parsed':
            unparsed_rungs += 1
            continue
        for instruction in rung.instructions:
            opcode = instruction.opcode
            normalized_opcode = opcode.upper() if opcode.isascii() else None
            extended = schema_version >= 3 and normalized_opcode in _EXTENDED_ROLES
            calculation = schema_version == 4 and normalized_opcode == 'CPT'
            slots = (('write', 'expression_read') if calculation else
                     (_EXTENDED_ROLES if extended else _ROLES).get(normalized_opcode))
            empty_slots = [index for index, arg in enumerate(instruction.arguments)
                           if not arg.strip() and not (extended and normalized_opcode in {'GSV', 'SSV'}
                                                       and index == 1)]
            status = ('unsupported_instruction' if slots is None else
                      'argument_count_mismatch' if len(instruction.arguments) != len(slots) else
                      'empty_argument' if empty_slots else
                      'classified')
            counter = extended and normalized_opcode in _COUNTER_OPCODES
            if status == 'classified' and (normalized_opcode in _TIMER_OPCODES or counter):
                kinds = [_timer_pseudo_kind(raw) for raw in instruction.arguments[1:]]
                if any(kind is None for kind in kinds):
                    status = 'unsupported_operand_form'
                    counter_invalid_forms += int(counter)
                else:
                    timer_instructions += int(not counter)
                    for kind in kinds:
                        (counter_pseudo_counts if counter else timer_pseudo_counts)[kind] += 1
            initial_step = (extended and normalized_opcode == 'SFR' and status == 'classified'
                            and instruction.arguments[1].strip() == '0')
            if extended and status == 'classified':
                extended_counts['sfc_reset_initial' if initial_step else _EXTENDED_FAMILY[normalized_opcode]] += 1
            occurrence = calculation_by_id[instruction.id] if calculation else None
            if calculation and status == 'classified':
                expression_counts[occurrence['syntax_status']] += 1
            instruction_counts[status] += 1
            operand_ids: list[str] = []
            for index, raw in enumerate(instruction.arguments):
                reference = next(source_operands)
                role = slots[index] if status == 'classified' else 'unknown'
                if initial_step and index == 1:
                    role = 'non_data'
                reason = ('timer_pseudo_operand' if status == 'classified'
                          and normalized_opcode in _TIMER_OPCODES and index in {1, 2}
                          else _REASONS[status])
                binding = reference
                origin = 'source_references'
                if extended and status == 'classified':
                    if role == 'non_data':
                        binding = _binding('non_data')
                        origin = 'access_non_data'
                        if counter and index in {1, 2}:
                            reason = 'counter_pseudo_operand'
                        elif initial_step and index == 1:
                            reason = 'sfc_initial_step_sentinel'
                    else:
                        origin = 'access_resolver'
                        value = raw.strip()
                        if _literal(value):
                            binding = _binding('literal')
                        else:
                            if resolver is None:
                                resolver = _Resolver(inventory)
                            binding = resolver.resolve(value, rung.scope_id)
                        extended_bound += int(binding['status'] == 'root_bound')
                if role == 'expression_read':
                    disposition = occurrence['syntax_status']
                    binding = _binding(f'{disposition}_expression')
                    origin = 'calculation_expression'
                # V4 shares the retained expansion allowance across source
                # operands and expression leaves; v2 keeps its frozen behavior.
                charge_binding(binding)
                operand = {
                    'id': reference['id'], 'instruction_id': instruction.id,
                    'rung_id': rung.id, 'argument_index': index,
                    'role': role, 'reason': reason,
                    'binding_status': binding['status'],
                    'symbol_id': binding['symbol_id'], 'target_id': binding['target_id'],
                    'suffix': binding['suffix'],
                }
                if schema_version >= 3:
                    operand.update(binding_origin=origin, source_reference_status=reference['status'],
                                   binding_reason=binding['reason'], alias_chain=list(binding['alias_chain']))
                charge_record(operand)
                operands.append(operand)
                operand_ids.append(operand['id'])
                role_counts[role] += 1
                if binding['status'] == 'root_bound':
                    bound_counts[role] += 1
                    if role in INDEXED_ROLES:
                        target_id = binding['target_id']
                        if target_id not in roots:
                            roots[target_id] = {'target_id': target_id, **{
                                f'{item}_operand_ids': [] for item in sorted(INDEXED_ROLES)
                            }}
                        roots[target_id][f'{role}_operand_ids'].append(operand['id'])
                if (role == 'read' and binding['status'] not in
                        {'root_bound', 'literal', 'system_flag'} or
                        role in {'write', 'read_write'} and binding['status'] != 'root_bound'):
                    access_gaps += 1
            if calculation and status == 'classified' and occurrence['syntax_status'] == 'parsed':
                leaves = sorted((nodes_by_id[identifier] for identifier in occurrence['node_ids']
                                 if nodes_by_id[identifier]['kind'] == 'reference'), key=lambda node: node['start'])
                gaps = False
                for node in leaves:
                    if len(expression_uses) >= MAX_EXPRESSION_USES:
                        _limit()
                    binding = node['binding']
                    charge_binding(binding)
                    use = {
                        'id': node['id'], 'expression_operand_id': occurrence['expression_operand_id'],
                        'instruction_id': instruction.id, 'rung_id': rung.id,
                        'start': node['start'], 'end': node['end'], 'role': 'read',
                        'binding_status': binding['status'], 'binding_reason': binding['reason'],
                        'symbol_id': binding['symbol_id'], 'target_id': binding['target_id'],
                        'suffix': binding['suffix'], 'alias_chain': list(binding['alias_chain']),
                    }
                    charge_record(use)
                    expression_uses.append(use)
                    expression_bindings[binding['status']] += 1
                    if binding['status'] == 'root_bound':
                        target = binding['target_id']
                        expression_roots.setdefault(target, {'target_id': target, 'read_use_ids': []})['read_use_ids'].append(use['id'])
                    else:
                        gaps = True
                expression_gaps += int(gaps)
            instruction_record = {
                'id': instruction.id, 'rung_id': rung.id, 'opcode': opcode,
                'status': status, 'operand_ids': operand_ids,
            }
            charge_record(instruction_record)
            instructions.append(instruction_record)
    linked = sum(bound_counts[role] for role in INDEXED_ROLES)
    coverage = {
        'instructions_total': len(instructions), 'instructions_by_status': instruction_counts,
        'operands_total': len(operands), 'operands_by_role': role_counts,
        'bound_by_role': bound_counts, 'linked_operands': linked,
        'unlinked_operands': len(operands) - linked, 'indexed_roots': len(roots),
        'source_rungs': len(inventory.rungs), 'unparsed_rungs': unparsed_rungs,
        'access_gap_operands': access_gaps,
        'timer_instructions': timer_instructions,
        'timer_pseudo_operands_by_kind': timer_pseudo_counts,
    }
    if schema_version >= 3:
        coverage.update(extended_instructions=extended_counts,
                        counter_pseudo_operands_by_kind=counter_pseudo_counts,
                        counter_invalid_forms=counter_invalid_forms,
                        extended_bound_operands=extended_bound)
    if schema_version == 4:
        coverage.update(calculation_instructions=sum(expression_counts.values()),
                        expression_containers_by_status=expression_counts,
                        expression_uses_total=len(expression_uses), expression_uses_by_binding=expression_bindings,
                        expression_indexed_roots=len(expression_roots), expressions_with_binding_gaps=expression_gaps)
    partial = bool(unparsed_rungs or access_gaps or any(
        count for key, count in instruction_counts.items() if key != 'classified')
        or expression_counts['unsupported'] or expression_gaps)
    return AccessResult(dict(inventory.snapshot), 'partial' if partial else 'complete',
                        instructions, operands, list(roots.values()), coverage,
                        schema_version=schema_version, analyzer_version=f'instruction-access-{schema_version}',
                        expression_uses=expression_uses, expression_roots=list(expression_roots.values()))


def analyze_access(inventory: InventoryResult, references: ReferenceResult, *,
                   schema_version: int = 3, snapshot: SourceSnapshot | None = None,
                   calculations: CalculationResult | None = None) -> AccessResult:
    """Classify possible explicit operand roles against canonical references.

    Versions 2/3 retain their caller-authenticated inventory contract. Version 4
    requires a snapshot and canonical calculation2 companion, replaying both
    before deriving expression reads. This layer does no source IO.
    """
    try:
        if type(schema_version) is not int or schema_version not in {2, 3, 4}:
            _invalid()
        _check_limits(inventory, references)
        validate_references(inventory, references)
        if schema_version == 4:
            if (type(snapshot) is not SourceSnapshot or type(calculations) is not CalculationResult
                    or type(calculations.schema_version) is not int or calculations.schema_version != 2):
                _invalid()
            validate_calculations(snapshot, inventory, references, calculations)
        elif snapshot is not None or calculations is not None:
            _invalid()
        result = _derive_access(inventory, references, schema_version, calculations)
        render_access_json(result)
        return result
    except AccessError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, StopIteration):
        _invalid()


def validate_access(inventory: InventoryResult, references: ReferenceResult,
                    result: AccessResult, *, snapshot: SourceSnapshot | None = None,
                    calculations: CalculationResult | None = None) -> None:
    """Reject every deviation from canonical access, without copying a candidate."""
    try:
        if type(result) is not AccessResult:
            _invalid()
        expected = analyze_access(inventory, references, schema_version=result.schema_version,
                                  snapshot=snapshot, calculations=calculations)
        valid = (type(result) is AccessResult
                 and _strict_record_match(vars(expected), vars(result)))
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError):
        valid = False
    if not valid:
        _invalid()


def _project_data(result: AccessResult) -> dict[str, Any]:
    """Keep v2/v3 wire contracts frozen without silently discarding evidence."""
    if type(result) is not AccessResult:
        _invalid()
    data = vars(result)
    if (data.keys() != set(AccessResult.__dataclass_fields__)
            or type(result.schema_version) is not int or result.schema_version not in {2, 3, 4}):
        _invalid()
    if result.schema_version < 4:
        for name in ('expression_uses', 'expression_roots'):
            if type(data[name]) is not list or len(data[name]) != 0:
                _invalid()
        return {key: value for key, value in data.items() if key not in {'expression_uses', 'expression_roots'}}
    return data


def render_access_json(result: AccessResult) -> str:
    """Render bounded private JSON; source-bound validation is validate_access.

    Preflight only plain built-ins, fixed nesting depth and bounded content before
    JSON encoding. This also rejects cycles and custom objects without invoking
    their equality, deepcopy, iteration or serialization hooks.
    """
    if type(result) is not AccessResult:
        _invalid()
    try:
        data = _project_data(result)
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
