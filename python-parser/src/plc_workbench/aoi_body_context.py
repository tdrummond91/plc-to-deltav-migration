"""AOI declaration-owned evidence and first-field root context, without effects.

The two symbol indexes are alternative views of the same occurrences, never
additive access counts. An empty index means no observed supported access, not
an unused parameter. Routine ownership does not establish invocation order.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from io import StringIO
from itertools import chain
import json
from typing import Any

from .access import AccessResult, INSTRUCTION_STATUSES, OPERAND_ROLES_V4
from .binding_context import BindingContextResult
from .calculations import CalculationResult
from .conditions import ConditionResult
from .custom_instruction_context import (
    CustomInstructionContextResult, _name, _namespace, _PROTECTION_MARKERS,
    validate_custom_instruction_context,
)
from .models import InventoryResult, SourceSnapshot
from .references import (
    OPERAND_STATUSES, ReferenceResult, _ADDRESS, _Resolver, _binding, _literal,
    _strict_record_match,
)
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult
from .source import _read_nodes

MAX_CONTEXT_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 250_000
BODY_STATUSES = frozenset({'supported_rll', 'unsupported_context', 'protected',
    'unsupported_language', 'missing_or_multiple_content', 'incomplete_rll'})
INSTANCE_STATUSES = frozenset({'bound_root_context', 'missing_operand', 'unbound',
    'literal', 'unsupported_context', 'declaration_unavailable'})
DATATYPE_STATUSES = frozenset({'matching_type_name', 'different_type_name', 'missing',
    'member_deferred', 'unsupported_context', 'not_analyzed'})
ADDRESS_SHAPES = frozenset({'root', 'unindexed_array', 'static_element', 'member',
    'unsupported', 'literal', 'missing', 'not_analyzed'})
BODY_BINDINGS = OPERAND_STATUSES | {'parsed_expression', 'unsupported_expression'}
CONTEXT_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'aoi-body-context-1',
    'analysis_scope': 'declared_aoi_body_and_instance_context',
    'execution': 'not_analyzed', 'call_validation': 'not_analyzed',
    'parameter_mapping': 'not_analyzed', 'member_validation': 'not_analyzed',
}
COUNT_MAPS = {
    'body_rungs_by_parse_status': frozenset({'parsed', 'failed', 'preserved_unsupported', 'excluded'}),
    'body_instructions_by_access_status': INSTRUCTION_STATUSES,
    'body_operands_by_role': OPERAND_ROLES_V4,
    'body_operands_by_binding': BODY_BINDINGS,
    'routines_by_body_status': BODY_STATUSES,
    'calls_by_instance_status': INSTANCE_STATUSES,
    'instance_datatype_status': DATATYPE_STATUSES,
    'instance_address_shape': ADDRESS_SHAPES,
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | {
    'source_rungs', 'source_instructions', 'source_operands', 'source_expression_uses',
    'definitions_total', 'routines_total', 'parameters_total', 'local_tags_total',
    'body_rungs_total', 'body_instructions_total', 'body_operands_total',
    'body_expression_uses_total', 'body_symbol_operand_uses', 'body_symbol_expression_uses',
    'calls_total', 'definitions_with_body_gaps', 'symbols_with_context_gaps',
}


class AoiBodyContextError(ValueError):
    """Source-free canonical or resource validation failure."""


def _invalid() -> None:
    raise AoiBodyContextError('AOI body context does not match its source evidence.')


def _limit() -> None:
    raise AoiBodyContextError('AOI body context exceeds its evidence limits.')


@dataclass(frozen=True)
class AoiBodyContextResult:
    snapshot: dict[str, str | int]
    status: str
    declarations: list[dict[str, Any]]
    routines: list[dict[str, Any]]
    symbols: list[dict[str, Any]]
    calls: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'aoi-body-context-1'
    analysis_scope: str = 'declared_aoi_body_and_instance_context'
    execution: str = 'not_analyzed'
    call_validation: str = 'not_analyzed'
    parameter_mapping: str = 'not_analyzed'
    member_validation: str = 'not_analyzed'

    def to_dict(self) -> dict[str, Any]:
        render_aoi_body_context_json(self)
        return deepcopy(vars(self))


def coverage_status(c: dict[str, Any]) -> str:
    """Ownership/first-field completeness, not body semantics or call validity.

    Existing unknown roles and unresolved body operands are counted unchanged;
    they do not erase otherwise complete declaration ownership evidence.
    """
    incomplete = (c['definitions_with_body_gaps'] or c['symbols_with_context_gaps']
        or c['routines_total'] != c['routines_by_body_status']['supported_rll']
        or c['calls_total'] != c['calls_by_instance_status']['bound_root_context']
        or c['calls_total'] != c['instance_datatype_status']['matching_type_name']
        or c['calls_total'] != c['instance_address_shape']['root'] + c['instance_address_shape']['static_element'])
    return 'partial' if incomplete else 'complete'


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, access: AccessResult,
            custom: CustomInstructionContextResult) -> AoiBodyContextResult:
    if max(len(inventory.entities), len(inventory.rungs), len(access.instructions),
           len(access.operands), len(access.expression_uses)) > MAX_RECORDS:
        _limit()
    nodes = _read_nodes(snapshot.data)
    namespace = _namespace(nodes[0].expanded_name)
    supported: list[bool] = []
    subtree_supported: list[bool] = []
    protected: list[bool] = []
    by_locator = {}
    for index, node in enumerate(nodes):
        valid = (_namespace(node.expanded_name) == namespace
                 and all('}' not in key for key in node.expanded_attributes)
                 and (node.parent is None or supported[node.parent]))
        supported.append(valid)
        subtree_supported.append(valid)
        protected.append(bool(_PROTECTION_MARKERS.intersection(node.attributes))
                         or node.name in {'EncodedData', 'EncryptedContent'}
                         or bool(node.parent is not None and protected[node.parent]))
        by_locator[node.locator] = index
    for index in reversed(range(len(nodes))):
        if nodes[index].parent is not None and not subtree_supported[index]:
            subtree_supported[nodes[index].parent] = False
    subtree_protected = list(protected)
    for index in reversed(range(len(nodes))):
        if nodes[index].parent is not None and subtree_protected[index]:
            subtree_protected[nodes[index].parent] = True
    entities = {entity.id: entity for entity in inventory.entities}
    owners = {}
    for entity in inventory.entities:
        owners[entity.id] = entity.id if entity.kind == 'aoi' else owners.get(entity.parent_id)
    rungs_by_routine: dict[str, list[Any]] = defaultdict(list)
    for rung in inventory.rungs:
        rungs_by_routine[rung.parent_id].append(rung)
    operands_by_rung: dict[str, list[Any]] = defaultdict(list)
    expressions_by_rung: dict[str, list[Any]] = defaultdict(list)
    for row in access.operands:
        operands_by_rung[row['rung_id']].append(row)
    for row in access.expression_uses:
        expressions_by_rung[row['rung_id']].append(row)
    access_by_id = {row['id']: row for row in access.instructions}
    incomplete_routines = {d.source_id for d in inventory.diagnostics
                           if d.code == 'routine_content_not_analyzed'}
    c = {key: dict.fromkeys(sorted(vocabulary), 0) for key, vocabulary in COUNT_MAPS.items()}
    c.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
    c.update(source_rungs=len(inventory.rungs), source_instructions=len(access.instructions),
             source_operands=len(access.operands), source_expression_uses=len(access.expression_uses))
    declarations, routines, symbols, calls = [], [], [], []
    symbols_by_declaration: dict[str, list[Any]] = defaultdict(list)
    symbols_by_id = {}
    direct_operands: dict[str, list[str]] = defaultdict(list)
    resolved_operands: dict[str, list[str]] = defaultdict(list)
    direct_expressions: dict[str, list[str]] = defaultdict(list)
    resolved_expressions: dict[str, list[str]] = defaultdict(list)
    body_operands, body_expressions = [], []
    retained = records = 0

    def charge(row: Any) -> None:
        nonlocal retained, records
        records += 1
        retained += len(json.dumps(row, ensure_ascii=True, separators=(',', ':'))) + 1
        if records > MAX_RECORDS or retained > MAX_CONTEXT_BYTES:
            _limit()

    for entity in inventory.entities:
        if entity.kind not in {'aoi_parameter', 'aoi_local_tag'} or owners[entity.id] is None:
            continue
        row = {'source_id': entity.id, 'declaration_id': owners[entity.id], 'kind': entity.kind,
               'context_status': 'supported' if supported[by_locator[entity.locator]] else 'unsupported_context',
               'direct_operand_ids': [], 'resolved_operand_ids': [],
               'direct_expression_use_ids': [], 'resolved_expression_use_ids': []}
        symbols.append(row)
        symbols_by_declaration[owners[entity.id]].append(row)
        symbols_by_id[entity.id] = row
        c['parameters_total' if entity.kind == 'aoi_parameter' else 'local_tags_total'] += 1
        c['symbols_with_context_gaps'] += row['context_status'] != 'supported'
    for declaration in custom.declarations:
        identifier = declaration['source_id']
        owned = symbols_by_declaration[identifier]
        row = {'declaration_id': identifier, 'status': declaration['status'],
               'routine_ids': [],
               'parameter_ids': [item['source_id'] for item in owned if item['kind'] == 'aoi_parameter'],
               'local_tag_ids': [item['source_id'] for item in owned if item['kind'] == 'aoi_local_tag']}
        gaps = (declaration['status'] != 'unique_candidate' or not declaration['routines']
                or bool(declaration['encoded_region_ids']) or declaration['protection_marker'] != 'none_observed')
        for body in declaration['routines']:
            routine = entities[body['source_id']]
            index = by_locator[routine.locator]
            owned_rungs = rungs_by_routine[routine.id]
            if not subtree_supported[index] or declaration['status'] == 'unsupported_context':
                status = 'unsupported_context'
            elif subtree_protected[index] or declaration['protection_marker'] != 'none_observed':
                status = 'protected'
            elif body['language'] != 'rll':
                status = 'unsupported_language'
            elif body['content'] != 'rll':
                status = 'missing_or_multiple_content'
            elif (any(item.parse_status != 'parsed' for item in owned_rungs)
                    or routine.id in incomplete_routines):
                status = 'incomplete_rll'
            else:
                status = 'supported_rll'
            instructions = [item for rung in owned_rungs for item in rung.instructions]
            operands = [item for rung in owned_rungs for item in operands_by_rung[rung.id]]
            expressions = [item for rung in owned_rungs for item in expressions_by_rung[rung.id]]
            record = {'routine_id': routine.id, 'declaration_id': identifier, 'body_status': status,
                      'rung_ids': [item.id for item in owned_rungs],
                      'instruction_ids': [item.id for item in instructions],
                      'operand_ids': [item['id'] for item in operands],
                      'expression_use_ids': [item['id'] for item in expressions]}
            charge(record)
            routines.append(record)
            row['routine_ids'].append(routine.id)
            gaps |= status != 'supported_rll'
            c['routines_by_body_status'][status] += 1
            for rung in owned_rungs:
                c['body_rungs_by_parse_status'][rung.parse_status] += 1
            for instruction in instructions:
                c['body_instructions_by_access_status'][access_by_id[instruction.id]['status']] += 1
            for operand in operands:
                c['body_operands_by_role'][operand['role']] += 1
                c['body_operands_by_binding'][operand['binding_status']] += 1
            body_operands.extend(operands)
            body_expressions.extend(expressions)
        charge(row)
        declarations.append(row)
        c['definitions_with_body_gaps'] += bool(gaps)
    # Restrict both indexes to declaration-owned body occurrences. External
    # calls, same-spelling controller tags, and dynamic index reads do not join.
    owners_by_rung = {rung.id: owners.get(rung.parent_id) for rung in inventory.rungs}
    supported_routines = {row['routine_id'] for row in routines if row['body_status'] == 'supported_rll'}
    supported_rungs = {rung.id for rung in inventory.rungs if rung.parent_id in supported_routines}
    for population, direct, resolved, count in (
        (body_operands, direct_operands, resolved_operands, 'body_symbol_operand_uses'),
        (body_expressions, direct_expressions, resolved_expressions, 'body_symbol_expression_uses'),
    ):
        for use in population:
            if use['rung_id'] not in supported_rungs:
                continue
            linked = [use['symbol_id'], use['target_id'], *use.get('alias_chain', [])]
            if any(item is not None and not supported[by_locator[entities[item].locator]] for item in linked):
                continue
            owner = owners_by_rung[use['rung_id']]
            matched = False
            for key, index in (('symbol_id', direct), ('target_id', resolved)):
                symbol = symbols_by_id.get(use[key])
                if symbol is not None and symbol['declaration_id'] == owner and symbol['context_status'] == 'supported':
                    index[use[key]].append(use['id'])
                    matched = True
            c[count] += matched
    for symbol in symbols:
        identifier = symbol['source_id']
        symbol.update(direct_operand_ids=direct_operands[identifier], resolved_operand_ids=resolved_operands[identifier],
                      direct_expression_use_ids=direct_expressions[identifier], resolved_expression_use_ids=resolved_expressions[identifier])
        charge(symbol)
    source_rungs = {rung.id: rung for rung in inventory.rungs}
    source_instructions = {instruction.id: instruction for rung in inventory.rungs for instruction in rung.instructions}
    resolver = _Resolver(inventory)
    for call in custom.calls:
        instruction = source_instructions[call['instruction_id']]
        rung = source_rungs[call['rung_id']]
        operand_ids = access_by_id[instruction.id]['operand_ids']
        binding = _binding('not_analyzed')
        status, shape, datatype = 'declaration_unavailable', 'not_analyzed', 'not_analyzed'
        if call['status'] == 'unique_candidate':
            if not subtree_supported[by_locator[rung.locator]]:
                status, binding = 'unsupported_context', _binding('unsupported_context')
            elif not instruction.arguments or not instruction.arguments[0].strip():
                status, shape, binding = 'missing_operand', 'missing', _binding('missing_operand')
            elif _literal(instruction.arguments[0].strip()):
                status, shape, binding = 'literal', 'literal', _binding('literal')
            else:
                binding = resolver.resolve(instruction.arguments[0], rung.scope_id)
                status, shape = 'unbound', 'unsupported'
                linked = [binding['symbol_id'], binding['target_id'], *binding['alias_chain']]
                if any(item is not None and not supported[by_locator[entities[item].locator]] for item in linked):
                    status, binding, datatype = 'unsupported_context', _binding('unsupported_context'), 'unsupported_context'
                elif binding['status'] == 'root_bound':
                    status = 'bound_root_context'
                    suffix = binding['suffix']
                    target = entities[binding['target_id']]
                    dimensions = target.attributes.get('Dimensions')
                    if _ADDRESS.fullmatch('A' + suffix) is None:
                        shape = 'unsupported'
                    elif '.' in suffix:
                        shape, datatype = 'member', 'member_deferred'
                    else:
                        shape = 'static_element' if suffix else 'unindexed_array' if dimensions not in {None, '', '0'} else 'root'
                        declared_type = _name(target.attributes.get('DataType'))
                        definition_name = _name(entities[call['declaration_id']].name)
                        datatype = ('missing' if declared_type is None else 'matching_type_name'
                                    if declared_type == definition_name else 'different_type_name')
        record = {'instruction_id': instruction.id, 'rung_id': rung.id,
                  'declaration_id': call['declaration_id'], 'declaration_status': call['status'],
                  'first_operand_id': operand_ids[0] if operand_ids else None,
                  'instance_status': status, 'binding_status': binding['status'],
                  'symbol_id': binding['symbol_id'], 'target_id': binding['target_id'],
                  'alias_chain': list(binding['alias_chain']), 'datatype_status': datatype, 'address_shape': shape}
        charge(record)
        calls.append(record)
        c['calls_by_instance_status'][status] += 1
        c['instance_datatype_status'][datatype] += 1
        c['instance_address_shape'][shape] += 1
    c.update(definitions_total=len(declarations), routines_total=len(routines),
             body_rungs_total=sum(len(row['rung_ids']) for row in routines),
             body_instructions_total=sum(len(row['instruction_ids']) for row in routines),
             body_operands_total=len(body_operands), body_expression_uses_total=len(body_expressions), calls_total=len(calls))
    return AoiBodyContextResult(deepcopy(inventory.snapshot), coverage_status(c), declarations, routines, symbols, calls, c)


def analyze_aoi_body_context(snapshot: SourceSnapshot, inventory: InventoryResult,
                             references: ReferenceResult, access: AccessResult,
                             calculations: CalculationResult, rung_analysis: RungAnalysisResult,
                             relationships: RelationshipResult, conditions: ConditionResult,
                             binding_context: BindingContextResult,
                             custom_instruction_context: CustomInstructionContextResult) -> AoiBodyContextResult:
    try:
        validate_custom_instruction_context(snapshot, inventory, references, access, calculations,
            rung_analysis, relationships, conditions, binding_context, custom_instruction_context)
        result = _derive(snapshot, inventory, access, custom_instruction_context)
        render_aoi_body_context_json(result)
        return result
    except AoiBodyContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_aoi_body_context(snapshot: SourceSnapshot, inventory: InventoryResult,
                              references: ReferenceResult, access: AccessResult,
                              calculations: CalculationResult, rung_analysis: RungAnalysisResult,
                              relationships: RelationshipResult, conditions: ConditionResult,
                              binding_context: BindingContextResult,
                              custom_instruction_context: CustomInstructionContextResult,
                              result: AoiBodyContextResult) -> None:
    try:
        render_aoi_body_context_json(result)
        expected = analyze_aoi_body_context(snapshot, inventory, references, access, calculations,
            rung_analysis, relationships, conditions, binding_context, custom_instruction_context)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except AoiBodyContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_aoi_body_context_json(result: AoiBodyContextResult) -> str:
    """Bound native containers before serialization; authentication is separate."""
    try:
        if type(result) is not AoiBodyContextResult or vars(result).keys() != set(AoiBodyContextResult.__dataclass_fields__):
            _invalid()
        payload, remaining, records = vars(result), MAX_CONTEXT_BYTES, 0
        stack = [(iter((payload,)), None)]
        active = set()
        while stack:
            try:
                value = next(stack[-1][0])
            except StopIteration:
                _, identifier = stack.pop()
                if identifier is not None:
                    active.remove(identifier)
                continue
            remaining -= 1
            if type(value) is str:
                remaining -= len(value)
            elif type(value) in {dict, list}:
                if len(value) > MAX_RECORDS or id(value) in active or len(stack) > 12:
                    _limit()
                if type(value) is dict:
                    records += 1
                    if any(type(key) is not str for key in value):
                        _invalid()
                if records > MAX_RECORDS:
                    _limit()
                active.add(id(value))
                stack.append((iter(chain(value.keys(), value.values()) if type(value) is dict else value), id(value)))
            elif type(value) not in {int, bool, type(None)}:
                _invalid()
            if remaining < 0:
                _limit()
        output, size = StringIO(), 0
        for chunk in json.JSONEncoder(ensure_ascii=True, sort_keys=True, indent=2).iterencode(payload):
            size += len(chunk)
            if size + 1 > MAX_CONTEXT_BYTES:
                _limit()
            output.write(chunk)
        return output.getvalue() + '\n'
    except AoiBodyContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
