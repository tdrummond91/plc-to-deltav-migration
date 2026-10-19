"""Source-linked file/array operations without expanding or executing ranges.

Documented operand roles supplement the frozen access catalogue. A bound start
is not an accessed range; pseudo-fields and exported data are never selected as
effective runtime values. FAL expressions use the existing bounded syntax subset.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from io import StringIO
import json
import re
from typing import Any

from .access import AccessResult, _timer_pseudo_kind
from .calculations import CalculationResult, FUNCTIONS, NODE_KINDS, _Parser, _Unsupported as ExpressionUnsupported
from .conditions import ConditionResult, validate_conditions
from .indexed_access import _parse as parse_index, _Unsupported as IndexUnsupported, _TooLarge as IndexTooLarge
from .models import InventoryResult, SourceSnapshot
from .output_context import _provenance
from .references import ReferenceResult, _ADDRESS, _Resolver, _literal, _strict_record_match
from .relationships import RelationshipResult, _identifier
from .rung_analysis import RungAnalysisResult
from .sfc_context import _qualified_source
from .source import _read_nodes
from .stateful_objects import _controls, _data_paths, _declaration, _index_control, _member
from .tag_data import TagDataResult, validate_tag_data

MAX_FILE_OPERATION_RECORDS = 250_000
MAX_FILE_OPERATION_BYTES = 8 * 1024 * 1024
MAX_FILE_OPERATION_JSON_BYTES = MAX_FILE_OPERATION_BYTES
OPCODES = frozenset({'COP', 'CPS', 'AVE', 'FAL', 'SQO'})
ROW_GROUPS = ('occurrences', 'slots', 'expression_nodes', 'index_uses', 'controls', 'stored_data')
SIGNATURES = frozenset({'recognized', 'argument_count_mismatch', 'empty_argument'})
QUALIFICATIONS = frozenset({'qualified', 'namespace_gap'})
CONTEXTS = frozenset({'modeled', 'binding_gaps', 'opaque', 'stateful', 'namespace_gap'})
SLOT_ROLES = frozenset({'read', 'write', 'read_write', 'non_data', 'expression_read', 'unknown'})
SLOT_STATUSES = frozenset({'exact_address', 'symbolic_address', 'literal', 'non_data', 'parsed_expression',
    'unsupported_expression', 'unbound', 'invalid_identity', 'namespace_gap', 'signature_unresolved', 'unsupported_form'})
SELECTORS = frozenset({'not_selector', 'placeholder', 'integer_literal', 'dimension', 'all', 'inc', 'numeric_mode', 'invalid'})
EXPRESSION_STATUSES = frozenset({'not_applicable', 'parsed', 'unsupported', 'signature_unresolved', 'namespace_gap'})
ADDRESS_STATUSES = frozenset({'exact_address', 'symbolic_address', 'literal', 'unbound', 'invalid_identity', 'namespace_gap'})
INDEX_STATUSES = frozenset({'parsed', 'unsupported_grammar', 'resource_limit', 'alias_target_dynamic', 'namespace_gap'})
SPAN_KINDS = frozenset({'destination_element_copy', 'dimension_average', 'expression_iteration', 'masked_sequence'})
COUNT_MAPS = {
    'occurrences_by_opcode': OPCODES, 'signatures': SIGNATURES, 'qualifications': QUALIFICATIONS,
    'contexts': CONTEXTS, 'slots_by_role': SLOT_ROLES, 'slots_by_status': SLOT_STATUSES,
    'selectors_by_kind': SELECTORS, 'expressions_by_status': EXPRESSION_STATUSES,
    'expression_nodes_by_kind': NODE_KINDS, 'expression_references_by_status': ADDRESS_STATUSES,
    'index_uses_by_status': INDEX_STATUSES, 'index_roots_by_status': ADDRESS_STATUSES,
    'index_reads_by_status': ADDRESS_STATUSES, 'span_kinds': SPAN_KINDS,
    'controls_by_declaration': frozenset({'control', 'timer', 'counter', 'other', 'unresolved'}),
    'controls_by_bounds': frozenset({'scalar', 'static_in_bounds', 'static_out_of_bounds', 'unresolved'}),
    'stored_data_by_status': frozenset({'qualified', 'namespace_gap', 'shape_gap'}),
    'stored_data_by_kind': frozenset({'control', 'member'}),
    'stored_types_by_status': frozenset({'matching', 'mismatch', 'unresolved'}),
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | frozenset({
    'source_rungs', 'source_instructions', 'source_operands', 'source_expression_uses',
    'source_condition_nodes', 'source_data_elements', 'source_selected_operands', 'source_selected_instructions',
    'source_fal_instructions', 'unparsed_rungs', 'occurrences_total', 'slots_total', 'expression_nodes_total',
    'index_uses_total', 'controls_total', 'stored_data_total', 'pseudo_operands_total',
    'expression_references_total', 'index_read_occurrences', 'selectors_total',
    'newly_classified_instructions', 'newly_classified_slots', 'content_links_total', 'controls_with_data',
})
FILE_OPERATION_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'file-operations-1',
    'analysis_scope': 'file_array_source_operations', 'address_identity': 'exact_expanded_spelling',
    'execution_analysis': 'not_implemented', 'range_expansion': 'not_implemented',
    'numeric_analysis': 'not_implemented', 'effective_value_selection': 'not_implemented',
    'condition_usage': 'incoming_source_context_not_write_guard', 'engineering_review': 'unreviewed',
}
# Import/export neutral text, rather than operand-table presentation order.
_SLOTS = {
    'COP': (('source', 'read'), ('destination', 'write'), ('length', 'read')),
    'CPS': (('source', 'read'), ('destination', 'write'), ('length', 'read')),
    'AVE': (('array', 'read'), ('dimension', 'non_data'), ('destination', 'write'),
            ('control', 'read_write'), ('pseudo_length', 'non_data'), ('pseudo_position', 'non_data')),
    'FAL': (('control', 'read_write'), ('pseudo_length', 'non_data'), ('pseudo_position', 'non_data'),
            ('mode', 'non_data'), ('destination', 'write'), ('expression', 'expression_read')),
    'SQO': (('array', 'read'), ('mask', 'read'), ('destination', 'read_write'),
            ('control', 'read_write'), ('pseudo_length', 'non_data'), ('pseudo_position', 'non_data')),
}
_SPANS = {'COP': 'destination_element_copy', 'CPS': 'destination_element_copy',
    'AVE': 'dimension_average', 'FAL': 'expression_iteration', 'SQO': 'masked_sequence'}


class FileOperationError(ValueError):
    """Source-free evidence rejection."""


def _invalid() -> None:
    raise FileOperationError('File operation evidence is inconsistent or exceeds its limits.') from None


@dataclass(frozen=True)
class FileOperationResult:
    snapshot: dict[str, str | int]
    status: str
    occurrences: list[dict[str, Any]]
    slots: list[dict[str, Any]]
    expression_nodes: list[dict[str, Any]]
    index_uses: list[dict[str, Any]]
    controls: list[dict[str, Any]]
    stored_data: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'file-operations-1'
    analysis_scope: str = 'file_array_source_operations'
    address_identity: str = 'exact_expanded_spelling'
    execution_analysis: str = 'not_implemented'
    range_expansion: str = 'not_implemented'
    numeric_analysis: str = 'not_implemented'
    effective_value_selection: str = 'not_implemented'
    condition_usage: str = 'incoming_source_context_not_write_guard'
    engineering_review: str = 'unreviewed'

    def to_dict(self) -> dict[str, Any]:
        render_file_operations_json(self)
        return deepcopy(vars(self))


class _Budget:
    def __init__(self) -> None:
        self.records = self.bytes = 0

    def add(self, row: dict[str, Any]) -> None:
        self.records += 1
        self.bytes += len(json.dumps(row, ensure_ascii=True).encode('ascii'))
        if self.records > MAX_FILE_OPERATION_RECORDS or self.bytes > MAX_FILE_OPERATION_BYTES:
            _invalid()


def _partial(c: dict[str, Any]) -> bool:
    return bool(c['unparsed_rungs'] or c['signatures']['recognized'] != c['occurrences_total']
        or c['qualifications']['namespace_gap'] or c['contexts']['modeled'] != c['occurrences_total']
        or any(c['slots_by_status'][key] for key in ('unsupported_expression', 'unbound', 'invalid_identity',
            'namespace_gap', 'signature_unresolved', 'unsupported_form'))
        or any(c['expression_references_by_status'][key] for key in ('unbound', 'invalid_identity', 'namespace_gap'))
        or c['index_uses_by_status']['parsed'] != c['index_uses_total']
        or any(c[key][status] for key in ('index_reads_by_status', 'index_roots_by_status')
            for status in ('unbound', 'invalid_identity', 'namespace_gap'))
        or c['controls_by_declaration']['control'] != c['controls_total']
        or c['controls_by_bounds']['unresolved'] or c['controls_by_bounds']['static_out_of_bounds']
        or c['stored_data_by_status']['namespace_gap'] or c['stored_data_by_status']['shape_gap']
        or c['stored_types_by_status']['mismatch'])


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
        access: AccessResult, conditions: ConditionResult, tag_data: TagDataResult) -> FileOperationResult:
    budget = _Budget()
    c = {key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()}
    c.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
    c.update(source_rungs=len(inventory.rungs), source_instructions=len(access.instructions),
        source_operands=len(access.operands), source_expression_uses=len(access.expression_uses),
        source_condition_nodes=len(conditions.nodes), source_data_elements=len(tag_data.elements),
        unparsed_rungs=sum(row.parse_status != 'parsed' for row in inventory.rungs))
    if any(c[key] > MAX_FILE_OPERATION_RECORDS for key in c if key.startswith('source_')):
        _invalid()
    supported, entity_ok, chain_ok = _qualified_source(snapshot, inventory)
    rung_ok, rung_binding_ok, _ = _provenance(snapshot, inventory)
    source_nodes = _read_nodes(snapshot.data)
    xml = {row.locator: row for row in source_nodes}
    source_operands = {(row['instruction_id'], row['argument_index']): row for row in references.operands}
    access_operands = {row['id']: row for row in access.operands}
    access_instructions = {row['id']: row for row in access.instructions}
    nodes = {row['id']: row for row in conditions.nodes}
    instruction_nodes = {row['instruction_id']: row for row in conditions.nodes if row['instruction_id'] is not None}
    entities = {row.id: row for row in inventory.entities}
    resolver = _Resolver(inventory)
    occurrences, slots, expression_nodes, index_uses, controls, stored_data = [], [], [], [], [], []
    by_control: dict[str, dict[str, Any]] = {}
    qualified_rungs = {}
    for rung in inventory.rungs:
        pending = [index for index in xml[rung.locator].children if source_nodes[index].name == 'Text']
        qualified = rung_ok[rung.id] and supported[rung.locator]
        while pending:
            child = source_nodes[pending.pop()]
            qualified = qualified and supported[child.locator]
            pending.extend(child.children)
        qualified_rungs[rung.id] = qualified
    context_ok: dict[str, bool] = {}
    expression_uses = defaultdict(list)
    for row in access.expression_uses:
        expression_uses[row['instruction_id']].append(row)
    for node in conditions.nodes:
        context_ok[node['id']] = (qualified_rungs[node['rung_id']]
            and all(context_ok[child] for child in node['child_ids'])
            and all(access_operands[item]['binding_status'] != 'root_bound'
                or rung_binding_ok(access_operands[item]) and chain_ok(access_operands[item]) for item in node['operand_ids'])
            and all(row['binding_status'] != 'root_bound' or rung_binding_ok(row) and chain_ok(row)
                for row in expression_uses[node['instruction_id']]))

    def resolve(raw: str, rung: Any) -> tuple[str, dict[str, Any], str | None]:
        binding = resolver.resolve(raw, rung.scope_id)
        status = 'literal' if _literal(raw.strip()) else 'unbound'
        address = None
        if binding['status'] == 'root_bound':
            if not chain_ok(binding) or not rung_binding_ok({'rung_id': rung.id, **binding}):
                status = 'namespace_gap'
            elif _ADDRESS.fullmatch('R' + binding['suffix']) is None:
                status = 'invalid_identity'
            else:
                status = 'exact_address'
                address = _identifier('relationship_address_', str(inventory.snapshot['id']),
                    binding['target_id'], binding['suffix'])
        if not qualified_rungs[rung.id]:
            status, address = 'namespace_gap', None
        return status, binding, address

    def index(raw: str, rung: Any, source_id: str, kind: str, role: str, binding: dict[str, Any]) -> str | None:
        if binding.get('reason') != 'non_static_array_index' and '[' not in raw:
            return None
        if _ADDRESS.fullmatch(raw.strip()):
            if binding.get('reason') != 'non_static_array_index':
                return None
            disposition = 'alias_target_dynamic'
        else:
            disposition = 'unsupported_grammar'
        record = {'id': _identifier('file_index', source_id), 'source_id': source_id,
            'source_kind': kind, 'rung_id': rung.id, 'role': role, 'status': disposition,
            'root_start': None, 'root_end': None, 'root_binding': None, 'root_status': None,
            'selectors': [], 'index_reads': []}
        try:
            root, start, end, selectors, reads = parse_index(raw)
            if any(row['dynamic'] for row in selectors):
                root_status, root_binding, _ = resolve(root, rung)
                if root_status == 'exact_address':
                    parse_index('R' + root_binding['suffix'] + raw[end:].rstrip())
                record.update(status='namespace_gap' if root_status == 'namespace_gap' else 'parsed',
                    root_start=start, root_end=end, root_binding=root_binding, root_status=root_status,
                    selectors=selectors)
                for number, read in enumerate(reads):
                    status, found, _ = resolve(raw[read['start']:read['end']], rung)
                    record['index_reads'].append({'id': _identifier('file_index_read', source_id, str(number)),
                        **read, 'binding': found, 'status': status})
        except IndexTooLarge:
            record.update(status='resource_limit', root_binding=None, root_status=None, selectors=[], index_reads=[])
        except IndexUnsupported:
            record.update(status='unsupported_grammar', root_binding=None, root_status=None, selectors=[], index_reads=[])
        if record['root_status'] is not None:
            c['index_roots_by_status'][record['root_status']] += 1
        c['index_uses_by_status'][record['status']] += 1
        c['selectors_total'] += len(record['selectors'])
        c['index_read_occurrences'] += len(record['index_reads'])
        for read in record['index_reads']:
            c['index_reads_by_status'][read['status']] += 1
        budget.add(record)
        index_uses.append(record)
        return 'symbolic_address' if record['status'] == 'parsed' and record['root_status'] == 'exact_address' else None

    for rung in inventory.rungs:
        if rung.parse_status != 'parsed':
            continue
        source_node = xml[rung.locator]
        content = source_nodes[source_node.parent] if source_node.parent is not None else None
        for instruction in rung.instructions:
            opcode = instruction.opcode.upper() if instruction.opcode.isascii() else instruction.opcode
            if opcode not in OPCODES:
                continue
            signature = ('argument_count_mismatch' if len(instruction.arguments) != len(_SLOTS[opcode]) else
                'empty_argument' if any(not arg.strip() for arg in instruction.arguments) else 'recognized')
            qualified = qualified_rungs[rung.id]
            node = instruction_nodes[instruction.id]
            guard = nodes[node['child_ids'][0]]
            context = ('namespace_gap' if not context_ok[guard['id']] else 'opaque' if guard['has_opaque'] else
                'binding_gaps' if guard['has_binding_gap'] else 'stateful' if guard['has_stateful'] else 'modeled')
            row = {'id': instruction.id, 'rung_id': rung.id, 'opcode': opcode, 'signature_status': signature,
                'qualification': 'qualified' if qualified else 'namespace_gap', 'slot_ids': [],
                'guard_id': guard['id'], 'context_status': context, 'expression_status': 'not_applicable',
                'error_code': None, 'error_offset': None, 'expression_root_id': None, 'expression_node_ids': [],
                'control_slot_id': None, 'destination_slot_id': None, 'span_kind': _SPANS[opcode],
                'routine_id': rung.parent_id, 'content_locator': content.locator if content else None,
                'content_attributes': dict(content.expanded_attributes) if content else {}, 'rung_locator': rung.locator}
            local_slots = []
            for position, raw in enumerate(instruction.arguments):
                source = source_operands[(instruction.id, position)]
                kind, role = _SLOTS[opcode][position] if signature == 'recognized' else ('unknown', 'unknown')
                slot = {'id': source['id'], 'instruction_id': instruction.id, 'rung_id': rung.id,
                    'position': position, 'raw_text': raw, 'kind': kind, 'role': role,
                    'status': 'signature_unresolved', 'binding': None, 'address_id': None,
                    'selector_kind': 'not_selector'}
                if kind.startswith('pseudo_'):
                    slot['selector_kind'] = _timer_pseudo_kind(raw) or 'invalid'
                    slot['status'] = 'non_data' if slot['selector_kind'] != 'invalid' else 'unsupported_form'
                    c['pseudo_operands_total'] += 1
                elif kind == 'dimension':
                    slot['selector_kind'] = 'dimension' if raw.strip() in {'0', '1', '2'} else 'invalid'
                    slot['status'] = 'non_data' if slot['selector_kind'] != 'invalid' else 'unsupported_form'
                elif kind == 'mode':
                    value = raw.strip()
                    slot['selector_kind'] = value.lower() if value.isascii() and value.upper() in {'ALL', 'INC'} else (
                        'numeric_mode' if re.fullmatch(r'[0-9]{1,10}', value) and 1 <= int(value) <= 2147483647 else 'invalid')
                    slot['status'] = 'non_data' if slot['selector_kind'] != 'invalid' else 'unsupported_form'
                elif kind == 'expression':
                    slot['status'] = 'unsupported_expression'
                elif role != 'unknown':
                    status, binding, address = resolve(raw, rung)
                    symbolic = index(raw, rung, slot['id'], 'slot', role, binding)
                    slot.update(status=symbolic or status, binding=binding, address_id=address)
                    if kind in {'source', 'array', 'destination', 'control'} and status == 'literal':
                        slot['status'] = 'unsupported_form'
                if not qualified:
                    slot.update(status='namespace_gap', address_id=None)
                if kind == 'control':
                    row['control_slot_id'] = slot['id']
                if kind == 'destination':
                    row['destination_slot_id'] = slot['id']
                row['slot_ids'].append(slot['id'])
                local_slots.append(slot)
            if opcode == 'FAL':
                row['expression_status'] = 'signature_unresolved' if signature != 'recognized' else 'namespace_gap' if not qualified else 'unsupported'
                if signature == 'recognized' and qualified:
                    expression = local_slots[5]
                    try:
                        parser = _Parser(expression['raw_text'], instruction.id, str(snapshot.id), FUNCTIONS)
                        root = parser.parse()
                    except ExpressionUnsupported as error:
                        row.update(error_code=error.code, error_offset=error.offset)
                    else:
                        for parsed in parser.nodes:
                            parsed.update(status=None, address_id=None)
                            if parsed['kind'] == 'reference':
                                status, binding, address = resolve(parsed['raw_text'], rung)
                                symbolic = index(parsed['raw_text'], rung, parsed['id'], 'expression', 'read', binding)
                                parsed.update(status=symbolic or status, binding=binding, address_id=address)
                                c['expression_references_by_status'][parsed['status']] += 1
                            budget.add(parsed)
                            c['expression_nodes_by_kind'][parsed['kind']] += 1
                            expression_nodes.append(parsed)
                        row.update(expression_status='parsed', expression_root_id=root,
                            expression_node_ids=[parsed['id'] for parsed in parser.nodes])
                        expression['status'] = 'parsed_expression'
            for slot in local_slots:
                if slot['kind'] == 'control' and slot['status'] == 'exact_address':
                    binding, address = slot['binding'], slot['address_id']
                    if address not in by_control:
                        declaration, bounds = _declaration(entities[binding['target_id']], binding['suffix'])
                        by_control[address] = {'id': address, 'target_id': binding['target_id'], 'suffix': binding['suffix'],
                            'occurrence_ids': [], 'declaration_kind': declaration, 'bounds_status': bounds,
                            'owner_id': None, 'content_ids': []}
                    by_control[address]['occurrence_ids'].append(instruction.id)
                c['slots_by_role'][slot['role']] += 1
                c['slots_by_status'][slot['status']] += 1
                c['selectors_by_kind'][slot['selector_kind']] += 1
                c['newly_classified_slots'] += int(slot['role'] != 'unknown' and access_operands[slot['id']]['role'] == 'unknown')
                budget.add(slot)
                slots.append(slot)
            c['source_selected_operands'] += len(instruction.arguments)
            c['source_fal_instructions'] += int(opcode == 'FAL')
            c['newly_classified_instructions'] += int(signature == 'recognized' and access_instructions[instruction.id]['status'] != 'classified')
            for key, value in (('occurrences_by_opcode', opcode), ('signatures', signature),
                    ('qualifications', row['qualification']), ('contexts', context),
                    ('expressions_by_status', row['expression_status']), ('span_kinds', row['span_kind'])):
                c[key][value] += 1
            budget.add(row)
            occurrences.append(row)
    owners = {row['source_id']: row for row in tag_data.owners}
    control_targets: dict[str, Any] = {}
    for control in by_control.values():
        owner = owners.get(control['target_id'])
        if owner:
            control.update(owner_id=owner['source_id'], content_ids=list(owner['content_ids']))
        c['controls_by_declaration'][control['declaration_kind']] += 1
        c['controls_by_bounds'][control['bounds_status']] += 1
        c['content_links_total'] += len(control['content_ids'])
        c['controls_with_data'] += bool(control['content_ids'])
        _index_control(control_targets, control)
        budget.add(control)
        controls.append(control)
    for element, path, status, structure in _data_paths(snapshot, tag_data):
        if path is None:
            continue
        for control in _controls(control_targets, element['owner_id'], path):
            relation = _member(control['suffix'], path)
            if relation is None:
                continue
            kind, member = relation
            expected = entities[control['target_id']].attributes.get('DataType', '')
            type_status = 'unresolved'
            if status == 'qualified' and control['bounds_status'] != 'unresolved' and expected and structure and structure[0] == control['suffix']:
                type_status = 'matching' if structure[1].upper() == expected.upper() else 'mismatch'
            link = {'control_id': control['id'], 'element_id': element['id'], 'member': member,
                'kind': 'control' if kind == 'whole_control' else 'member', 'status': status, 'type_status': type_status}
            budget.add(link)
            stored_data.append(link)
            c['stored_data_by_status'][status] += 1
            c['stored_data_by_kind'][link['kind']] += 1
            c['stored_types_by_status'][type_status] += 1
    c.update({f'{key}_total': len(value) for key, value in zip(ROW_GROUPS,
        (occurrences, slots, expression_nodes, index_uses, controls, stored_data))})
    c.update(source_selected_instructions=len(occurrences),
        expression_references_total=c['expression_nodes_by_kind']['reference'])
    return FileOperationResult(deepcopy(inventory.snapshot), 'partial' if _partial(c) else 'complete',
        occurrences, slots, expression_nodes, index_uses, controls, stored_data, c)


def analyze_file_operations(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, tag_data: TagDataResult) -> FileOperationResult:
    try:
        if type(conditions) is not ConditionResult or conditions.schema_version not in (3, 4, 5, 6):
            _invalid()
        validate_conditions(snapshot, inventory, references, access, calculations, rung_analysis, relationships, conditions)
        validate_tag_data(snapshot, inventory, tag_data)
        result = _derive(snapshot, inventory, references, access, conditions, tag_data)
        render_file_operations_json(result)
        return result
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_file_operations(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, tag_data: TagDataResult, result: FileOperationResult) -> None:
    try:
        render_file_operations_json(result)
        expected = analyze_file_operations(snapshot, inventory, references, access,
            calculations, rung_analysis, relationships, conditions, tag_data)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_file_operations_json(result: FileOperationResult) -> str:
    if type(result) is not FileOperationResult or vars(result).keys() != set(FileOperationResult.__dataclass_fields__):
        _invalid()
    for key, value in FILE_OPERATION_CONSTANTS.items():
        if type(getattr(result, key)) is not type(value) or getattr(result, key) != value:
            _invalid()
    if type(result.status) is not str or result.status not in {'complete', 'partial'}:
        _invalid()
    try:
        remaining = MAX_FILE_OPERATION_JSON_BYTES
        active = set()
        frames = [(iter((vars(result),)), None)]
        while frames:
            try:
                value = next(frames[-1][0])
            except StopIteration:
                _, identifier = frames.pop()
                if identifier is not None:
                    active.remove(identifier)
                continue
            remaining -= 1
            if type(value) is str:
                remaining -= len(value.encode('utf-8'))
            elif type(value) in {list, dict}:
                if id(value) in active or len(frames) > 32:
                    _invalid()
                if type(value) is dict and any(type(key) is not str for key in value):
                    _invalid()
                active.add(id(value))
                iterator = iter(value) if type(value) is list else iter(item for pair in value.items() for item in pair)
                frames.append((iterator, id(value)))
            elif value is not None and type(value) not in {int, bool}:
                _invalid()
            if remaining < 0:
                _invalid()
        output = StringIO()
        size = 0
        for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, separators=(',', ':')).iterencode(vars(result)):
            size += len(chunk.encode('utf-8'))
            if size + 1 > MAX_FILE_OPERATION_JSON_BYTES:
                _invalid()
            output.write(chunk)
        return output.getvalue() + '\n'
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
