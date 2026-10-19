"""AOI declaration-owned evidence and first-field root context, without effects.

The two symbol indexes are alternative views of the same occurrences, never
additive access counts. An empty index means no observed supported access, not
an unused parameter. Routine ownership does not establish invocation order.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
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
MAX_CONTEXT_BYTES_V2 = 16 * 1024 * 1024
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
CONTEXT_CONSTANTS_V2 = {**CONTEXT_CONSTANTS, 'schema_version': 2,
    'analyzer_version': 'aoi-body-context-2', 'parameter_mapping': 'named_member_associations_only'}
MEMBER_STATUSES = frozenset({'matched_parameter', 'declaration_unavailable',
    'unsupported_context', 'protected', 'unsupported_instance', 'unsupported_member',
    'missing_parameter', 'ambiguous_parameter', 'unsupported_parameter', 'alias_unresolved'})
SIGNATURE_STATUSES = frozenset({'available', 'declaration_unavailable', 'unsupported_context',
    'protected', 'ambiguous_parameters', 'unsupported_metadata'})
CALL_SHAPE_STATUSES = frozenset({'missing_instance_field', 'empty_fields',
    'signature_unavailable', 'no_required_parameters', 'required_field_count_equal',
    'fewer_than_required_fields', 'more_than_required_fields'})
COUNT_MAPS_V2 = {**COUNT_MAPS, 'members_by_status': MEMBER_STATUSES,
    'members_by_kind': frozenset({'operand', 'expression'}),
    'matched_members_by_usage': frozenset({'input', 'output'}),
    'matched_members_by_role': OPERAND_ROLES_V4,
    'signatures_by_status': SIGNATURE_STATUSES,
    'calls_by_field_shape': frozenset({'zero_fields', 'one_field', 'multiple_fields'}),
    'calls_by_signature_observation': CALL_SHAPE_STATUSES}
COVERAGE_KEYS_V2 = COVERAGE_KEYS | frozenset(COUNT_MAPS_V2) | {
    'member_contexts_total', 'matched_member_contexts', 'matched_parameters',
    'matched_instance_roots', 'signature_required_parameters', 'signature_optional_parameters',
    'signature_system_parameters', 'signature_unclassified_parameters',
    'call_argument_fields', 'call_trailing_fields', 'call_empty_fields',
}
_V2_FIELDS = frozenset({'member_contexts', 'parameter_signatures', 'call_shapes'})
_SYSTEM_PARAMETERS = frozenset({'enablein', 'enableout'})
_V2_PROTECTION_MARKERS = _PROTECTION_MARKERS | {'IsEncrypted'}
MAX_ASSOCIATION_LINKS = 250_000


class AoiBodyContextError(ValueError):
    """Source-free canonical or resource validation failure."""


def _invalid() -> None:
    raise AoiBodyContextError('AOI body context does not match its source evidence.')


def _limit() -> None:
    raise AoiBodyContextError('AOI body context exceeds its evidence limits.')


def _context_byte_limit(schema_version: int) -> int:
    return MAX_CONTEXT_BYTES_V2 if schema_version == 2 else MAX_CONTEXT_BYTES


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
    member_contexts: list[dict[str, Any]] = field(default_factory=list)
    parameter_signatures: list[dict[str, Any]] = field(default_factory=list)
    call_shapes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        render_aoi_body_context_json(self)
        return deepcopy(_project_data(self))


def coverage_status(c: dict[str, Any], schema_version: int = 1) -> str:
    """Ownership/first-field completeness, not body semantics or call validity.

    Existing unknown roles and unresolved body operands are counted unchanged;
    they do not erase otherwise complete declaration ownership evidence.
    """
    incomplete = (c['definitions_with_body_gaps'] or c['symbols_with_context_gaps']
        or c['routines_total'] != c['routines_by_body_status']['supported_rll']
        or c['calls_total'] != c['calls_by_instance_status']['bound_root_context']
        or c['calls_total'] != c['instance_datatype_status']['matching_type_name']
        or c['calls_total'] != c['instance_address_shape']['root'] + c['instance_address_shape']['static_element'])
    if schema_version == 2:
        incomplete |= (c['member_contexts_total'] != c['members_by_status']['matched_parameter']
            or c['definitions_total'] != c['signatures_by_status']['available']
            or c['calls_total'] != sum(c['calls_by_signature_observation'][key] for key in
                ('no_required_parameters', 'required_field_count_equal')))
    return 'partial' if incomplete else 'complete'


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, access: AccessResult,
            custom: CustomInstructionContextResult, *, schema_version: int = 1) -> AoiBodyContextResult:
    byte_limit = _context_byte_limit(schema_version)
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
        if records > MAX_RECORDS or retained > byte_limit:
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


def _with_parameter_members(snapshot: SourceSnapshot, inventory: InventoryResult,
                            references: ReferenceResult, access: AccessResult,
                            custom: CustomInstructionContextResult,
                            base: AoiBodyContextResult) -> AoiBodyContextResult:
    """Associate named members only; call field counts do not assign positions.

    The candidate population is root-bound explicit uses whose resolved root's
    declared datatype names an AOI in that root's controller. Unsupported and
    missing roots remain in upstream binding coverage, not guessed into this set.
    """
    # This temporary base has schema1's fields, but belongs to a schema2 build.
    # Charge it against the selected build budget rather than schema1's limit.
    retained = len(_render_context_json(_project_data(base), MAX_CONTEXT_BYTES_V2))
    records = len(base.declarations) + len(base.routines) + len(base.symbols) + len(base.calls)
    links = pending_link_bytes = 0

    def reserve_links(amount: int) -> None:
        nonlocal links, pending_link_bytes
        # Reserve before copying alias chains or collecting signature links.
        if (links + amount > MAX_ASSOCIATION_LINKS
                or retained + pending_link_bytes + amount * 96 > MAX_CONTEXT_BYTES_V2):
            _limit()
        links += amount
        pending_link_bytes += amount * 96

    def retain(rows: list[dict[str, Any]], row: dict[str, Any]) -> None:
        nonlocal records, retained, pending_link_bytes
        records += 1
        retained += len(json.dumps(row, ensure_ascii=True, separators=(',', ':'))) + 1
        if records > MAX_RECORDS or retained > MAX_CONTEXT_BYTES_V2:
            _limit()
        # This row now pays for its links in full. Release its construction
        # reservation without releasing earlier rows or the total link count.
        pending_link_bytes = 0
        rows.append(row)

    nodes = _read_nodes(snapshot.data)
    namespace = _namespace(nodes[0].expanded_name)
    supported, protected, by_locator = [], [], {}
    for index, node in enumerate(nodes):
        supported.append(_namespace(node.expanded_name) == namespace
            and all('}' not in key for key in node.expanded_attributes)
            and (node.parent is None or supported[node.parent]))
        protected.append(bool(_V2_PROTECTION_MARKERS.intersection(node.attributes))
            or node.name in {'EncodedData', 'EncryptedContent', 'EncryptedAOIContent', 'EncryptionInfo'}
            or (node.parent is not None and protected[node.parent]))
        by_locator[node.locator] = index
    subtree_supported, subtree_protected = list(supported), list(protected)
    for index in reversed(range(len(nodes))):
        parent = nodes[index].parent
        if parent is not None:
            subtree_supported[parent] &= subtree_supported[index]
            subtree_protected[parent] |= subtree_protected[index]
    entities = {entity.id: entity for entity in inventory.entities}
    controllers, owners = {}, {}
    for entity in inventory.entities:
        controllers[entity.id] = entity.id if entity.kind == 'controller' else controllers.get(entity.parent_id)
        owners[entity.id] = entity.id if entity.kind == 'aoi' else owners.get(entity.parent_id)
    declarations = {row['source_id']: row for row in custom.declarations}
    declaration_index: dict[tuple[str, str], list[str]] = defaultdict(list)
    for declaration in custom.declarations:
        entity = entities[declaration['source_id']]
        name = _name(entity.name)
        if name is not None and declaration['controller_id'] is not None:
            declaration_index[declaration['controller_id'], name].append(entity.id)
    symbols: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for entity in inventory.entities:
        if entity.kind in {'aoi_parameter', 'aoi_local_tag'} and _name(entity.name) is not None:
            symbols[owners[entity.id], _name(entity.name)].append(entity)

    def qualified(identifier: str) -> bool:
        return supported[by_locator[entities[identifier].locator]]

    def protected_entity(identifier: str) -> bool:
        return protected[by_locator[entities[identifier].locator]]

    def declaration_status(identifier: str) -> str:
        row = declarations[identifier]
        index = by_locator[entities[identifier].locator]
        if row['status'] == 'unsupported_context' or not subtree_supported[index]:
            return 'unsupported_context'
        if row['status'] != 'unique_candidate':
            return 'declaration_unavailable'
        if subtree_protected[index] or row['encoded_region_ids'] or row['protection_marker'] != 'none_observed':
            return 'protected'
        return 'available'

    c = deepcopy(base.coverage)
    for key, vocabulary in COUNT_MAPS_V2.items():
        if key not in COUNT_MAPS:
            c[key] = dict.fromkeys(sorted(vocabulary), 0)
    c.update(dict.fromkeys(sorted(COVERAGE_KEYS_V2 - COVERAGE_KEYS - COUNT_MAPS_V2.keys()), 0))
    signatures, call_shapes, members = [], [], []
    signatures_by_id = {}
    for declaration in custom.declarations:
        identifier = declaration['source_id']
        status = declaration_status(identifier)
        groups = {key: [] for key in ('required', 'optional', 'system', 'unclassified')}
        ambiguous = any(len(symbols[identifier, name]) > 1 for p in declaration['parameters']
                        if (name := _name(entities[p['source_id']].name)) is not None)
        if status == 'available' and ambiguous:
            status = 'ambiguous_parameters'
        for parameter in declaration['parameters']:
            entity = entities[parameter['source_id']]
            name = _name(entity.name)
            group = 'unclassified'
            if status == 'available' and name is not None:
                if name in _SYSTEM_PARAMETERS:
                    group = 'system'
                elif (parameter['usage'] in {'input', 'output', 'inout'}
                      and parameter['required'] in {'true', 'false'}
                      and parameter['visible'] in {'true', 'false'}
                      and (parameter['required'] != 'true' or parameter['visible'] == 'true')
                      and (parameter['usage'] != 'inout' or parameter['required'] == 'true')):
                    group = 'required' if parameter['required'] == 'true' else 'optional'
            reserve_links(1)
            groups[group].append(entity.id)
            c[f'signature_{group}_parameters'] += 1
        if status == 'available' and groups['unclassified']:
            status = 'unsupported_metadata'
        row = {'declaration_id': identifier, 'status': status,
               **{f'{key}_parameter_ids': value for key, value in groups.items()}}
        retain(signatures, row)
        signatures_by_id[identifier] = row
        c['signatures_by_status'][status] += 1
    source_instructions = {instruction.id: instruction for rung in inventory.rungs for instruction in rung.instructions}
    source_rungs = {rung.id: rung for rung in inventory.rungs}
    for call in base.calls:
        arguments = source_instructions[call['instruction_id']].arguments
        count, empty = len(arguments), sum(not value.strip() for value in arguments)
        trailing = max(0, count - 1)
        signature = signatures_by_id.get(call['declaration_id'])
        rung_index = by_locator[source_rungs[call['rung_id']].locator]
        available = (signature and signature['status'] == 'available'
                     and subtree_supported[rung_index] and not subtree_protected[rung_index])
        required = len(signature['required_parameter_ids']) if available else None
        status = ('missing_instance_field' if not count else 'empty_fields' if empty else
                  'signature_unavailable' if required is None else
                  'fewer_than_required_fields' if trailing < required else
                  'more_than_required_fields' if trailing > required else
                  'no_required_parameters' if required == 0 else 'required_field_count_equal')
        row = {'instruction_id': call['instruction_id'], 'declaration_id': call['declaration_id'],
               'argument_count': count, 'trailing_field_count': trailing, 'empty_field_count': empty,
               'required_parameter_count': required, 'status': status}
        retain(call_shapes, row)
        c['calls_by_field_shape']['zero_fields' if not count else 'one_field' if count == 1 else 'multiple_fields'] += 1
        c['calls_by_signature_observation'][status] += 1
        c['call_argument_fields'] += count
        c['call_trailing_fields'] += trailing
        c['call_empty_fields'] += empty

    aliases = {row['source_id']: row for row in references.aliases}
    matched_parameters, matched_roots = set(), set()
    for kind, population in (('operand', access.operands), ('expression', access.expression_uses)):
        for use in population:
            if use['binding_status'] != 'root_bound' or not use['suffix']:
                continue
            target = entities[use['target_id']]
            dtype = _name(target.attributes.get('DataType'))
            candidates = declaration_index.get((controllers[target.id], dtype), ())
            if not candidates:
                continue
            declaration_id = candidates[0] if len(candidates) == 1 else None
            parameter_id, parameter_alias = None, None
            status = 'declaration_unavailable' if declaration_id is None else declaration_status(declaration_id)
            rung = source_rungs[use['rung_id']]
            linked = (use['symbol_id'], target.id, *use.get('alias_chain', ()))
            index = by_locator[rung.locator]
            if not subtree_supported[index] or any(not qualified(item) for item in linked):
                status = 'unsupported_context'
            elif subtree_protected[index] or any(protected_entity(item) for item in linked):
                status = 'protected'
            elif status == 'available':
                suffix = use['suffix']
                name = _name(suffix[1:]) if suffix.startswith('.') else None
                if (target.kind not in {'tag', 'aoi_local_tag'}
                        or target.attributes.get('Dimensions') not in {None, '', '0'}):
                    status = 'unsupported_instance'
                elif name is None:
                    status = 'unsupported_member'
                else:
                    matches = symbols.get((declaration_id, name), ())
                    if len(matches) != 1:
                        status = 'ambiguous_parameter' if matches else 'missing_parameter'
                    elif matches[0].kind != 'aoi_parameter' or name in _SYSTEM_PARAMETERS or matches[0].attributes.get('Usage') not in {'Input', 'Output'}:
                        status = 'unsupported_parameter'
                    else:
                        parameter = matches[0]
                        parameter_alias = aliases.get(parameter.id)
                        alias_links = (() if parameter_alias is None else
                                       (parameter_alias['target_id'], *parameter_alias['alias_chain']))
                        if any(item is not None and not qualified(item) for item in alias_links):
                            status = 'unsupported_context'
                        elif any(item is not None and protected_entity(item) for item in alias_links):
                            status = 'protected'
                        elif parameter_alias is not None and parameter_alias['status'] != 'root_bound':
                            status = 'alias_unresolved'
                        else:
                            status, parameter_id = 'matched_parameter', parameter.id
            # Alias evidence is retained only for an established parameter link.
            parameter_alias = parameter_alias if parameter_id is not None else None
            reserve_links(len(use.get('alias_chain', ())) + (len(parameter_alias['alias_chain']) if parameter_alias else 0) + 5)
            row = {'use_id': use['id'], 'use_kind': kind, 'instruction_id': use['instruction_id'],
                   'rung_id': use['rung_id'], 'role': use['role'], 'status': status,
                   'symbol_id': use['symbol_id'], 'target_id': target.id,
                   'alias_chain': list(use.get('alias_chain', ())), 'suffix': use['suffix'],
                   'declaration_id': declaration_id, 'declaration_candidate_count': len(candidates),
                   'parameter_id': parameter_id,
                   'parameter_alias_target_id': parameter_alias['target_id'] if parameter_alias else None,
                   'parameter_alias_chain': list(parameter_alias['alias_chain']) if parameter_alias else [],
                   'parameter_alias_suffix': parameter_alias['suffix'] if parameter_alias else None}
            retain(members, row)
            c['members_by_status'][status] += 1
            c['members_by_kind'][kind] += 1
            if parameter_id is not None:
                c['matched_members_by_usage'][entities[parameter_id].attributes['Usage'].lower()] += 1
                c['matched_members_by_role'][use['role']] += 1
                matched_parameters.add(parameter_id)
                matched_roots.add(target.id)
    c.update(member_contexts_total=len(members), matched_member_contexts=c['members_by_status']['matched_parameter'],
             matched_parameters=len(matched_parameters), matched_instance_roots=len(matched_roots))
    return AoiBodyContextResult(**{**vars(base), **CONTEXT_CONSTANTS_V2,
        'status': coverage_status(c, 2), 'coverage': c, 'member_contexts': members,
        'parameter_signatures': signatures, 'call_shapes': call_shapes})


def analyze_aoi_body_context(snapshot: SourceSnapshot, inventory: InventoryResult,
                             references: ReferenceResult, access: AccessResult,
                             calculations: CalculationResult, rung_analysis: RungAnalysisResult,
                             relationships: RelationshipResult, conditions: ConditionResult,
                             binding_context: BindingContextResult,
                             custom_instruction_context: CustomInstructionContextResult, *,
                             schema_version: int = 1) -> AoiBodyContextResult:
    try:
        if type(schema_version) is not int or schema_version not in {1, 2}:
            _invalid()
        validate_custom_instruction_context(snapshot, inventory, references, access, calculations,
            rung_analysis, relationships, conditions, binding_context, custom_instruction_context)
        result = _derive(snapshot, inventory, access, custom_instruction_context, schema_version=schema_version)
        if schema_version == 2:
            result = _with_parameter_members(snapshot, inventory, references, access, custom_instruction_context, result)
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
            rung_analysis, relationships, conditions, binding_context, custom_instruction_context,
            schema_version=result.schema_version)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except AoiBodyContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def _project_data(result: AoiBodyContextResult) -> dict[str, Any]:
    if (type(result) is not AoiBodyContextResult or vars(result).keys() != set(AoiBodyContextResult.__dataclass_fields__)
            or type(result.schema_version) is not int or result.schema_version not in {1, 2}):
        _invalid()
    if result.schema_version == 1:
        if any(type(getattr(result, key)) is not list or getattr(result, key) for key in _V2_FIELDS):
            _invalid()
        return {key: value for key, value in vars(result).items() if key not in _V2_FIELDS}
    return vars(result)


def render_aoi_body_context_json(result: AoiBodyContextResult) -> str:
    """Bound native containers before serialization; authentication is separate."""
    payload = _project_data(result)
    return _render_context_json(payload, _context_byte_limit(result.schema_version))


def _render_context_json(payload: dict[str, Any], byte_limit: int) -> str:
    try:
        remaining, records = byte_limit, 0
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
            if size + 1 > byte_limit:
                _limit()
            output.write(chunk)
        return output.getvalue() + '\n'
    except AoiBodyContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
