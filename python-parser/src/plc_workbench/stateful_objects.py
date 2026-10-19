"""Source relationships for timers, counters and resets, without simulation.

Controls and member uses retain literal expanded spelling. Stored representations
remain separate evidence: neither pseudo-operands nor Data records select an
effective preset, accumulator, elapsed time or reset state.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from io import StringIO
import json
import re
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .conditions import ConditionResult, validate_conditions
from .models import InventoryResult, SourceSnapshot
from .output_context import _provenance
from .references import MAX_ADDRESS_LENGTH, ReferenceResult, _strict_record_match
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult
from .tag_data import TagDataResult, _namespace, validate_tag_data
from .source import _read_nodes

MAX_STATEFUL_OBJECT_RECORDS = 250_000
MAX_STATEFUL_OBJECT_BYTES = 16 * 1024 * 1024
MAX_STATEFUL_OBJECT_JSON_BYTES = 16 * 1024 * 1024
OPCODES = frozenset({'TON', 'TOF', 'RTO', 'CTU', 'CTD', 'RES'})
TIMER_OPCODES = frozenset({'TON', 'TOF', 'RTO'})
COUNTER_OPCODES = frozenset({'CTU', 'CTD'})
ROLES = frozenset({'read', 'write', 'read_write', 'unknown'})
MEMBERS = {'timer': frozenset({'PRE', 'ACC', 'EN', 'TT', 'DN'}),
           'counter': frozenset({'PRE', 'ACC', 'CU', 'CD', 'DN', 'OV', 'UN'})}
MEMBERS['mixed'] = MEMBERS['timer'] | MEMBERS['counter']
COUNT_MAPS = {
    'occurrences_by_opcode': OPCODES,
    'targets_by_status': frozenset({'exact_address', 'identity_gap', 'unbound', 'signature_unresolved', 'namespace_gap'}),
    'contexts_by_status': frozenset({'modeled', 'binding_gaps', 'opaque', 'stateful', 'namespace_gap'}),
    'objects_by_family': frozenset({'timer', 'counter', 'mixed', 'reset_only'}),
    'declarations_by_kind': frozenset({'timer', 'counter', 'control', 'other', 'unresolved'}),
    'bounds_by_status': frozenset({'scalar', 'static_in_bounds', 'static_out_of_bounds', 'unresolved'}),
    'uses_by_kind': frozenset({'whole_control', 'direct_member', 'other_member'}),
    'members_by_status': frozenset({'whole_control', 'known', 'unknown'}),
    'accepted_operands_by_role': ROLES, 'rejected_operands_by_role': ROLES,
    'stored_data_by_kind': frozenset({'control', 'member'}),
    'stored_data_by_status': frozenset({'qualified', 'namespace_gap', 'shape_gap'}),
    'stored_types_by_status': frozenset({'matching', 'mismatch', 'unresolved'}),
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | frozenset({
    'source_rungs', 'source_instructions', 'source_operands', 'source_expression_uses',
    'source_data_elements', 'unparsed_rungs', 'occurrences_total', 'occurrence_rungs',
    'objects_total', 'address_uses_total', 'stored_data_total', 'accepted_expression_uses',
    'rejected_expression_uses', 'objects_with_multiple_producers', 'objects_with_resets',
    'objects_with_matched_resets', 'unmatched_reset_occurrences', 'matched_reset_occurrences',
    'objects_with_type_conflicts', 'objects_with_tof_resets', 'objects_with_data',
    'objects_without_data', 'content_links_total', 'producer_occurrences', 'reset_occurrences',
})
STATEFUL_OBJECT_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'stateful-objects-1',
    'analysis_scope': 'timer_counter_reset_source_relationships',
    'address_identity': 'exact_expanded_spelling', 'execution_analysis': 'not_implemented',
    'effective_value_selection': 'not_implemented', 'engineering_review': 'unreviewed',
    'condition_usage': 'incoming_source_dag_not_runtime_enable',
}


class StatefulObjectError(ValueError):
    """Fixed source-free rejection of inconsistent or excessive evidence."""


def _invalid() -> None:
    raise StatefulObjectError('Stateful object evidence is inconsistent or exceeds its limits.') from None


@dataclass(frozen=True)
class StatefulObjectResult:
    snapshot: dict[str, str | int]
    status: str
    occurrences: list[dict[str, Any]]
    objects: list[dict[str, Any]]
    address_uses: list[dict[str, Any]]
    stored_data: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'stateful-objects-1'
    analysis_scope: str = 'timer_counter_reset_source_relationships'
    address_identity: str = 'exact_expanded_spelling'
    execution_analysis: str = 'not_implemented'
    effective_value_selection: str = 'not_implemented'
    engineering_review: str = 'unreviewed'
    condition_usage: str = 'incoming_source_dag_not_runtime_enable'

    def to_dict(self) -> dict[str, Any]:
        render_stateful_objects_json(self)
        return deepcopy(vars(self))


class _Budget:
    def __init__(self) -> None:
        self.records = self.bytes = 0

    def retain(self, row: dict[str, Any]) -> None:
        self.records += 1
        self.bytes += len(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self.records > MAX_STATEFUL_OBJECT_RECORDS or self.bytes > MAX_STATEFUL_OBJECT_BYTES:
            _invalid()


def _partial(c: dict[str, Any]) -> bool:
    return bool(c['unparsed_rungs'] or c['occurrences_total'] != c['targets_by_status']['exact_address']
        or c['occurrences_total'] != c['contexts_by_status']['modeled']
        or c['objects_by_family']['mixed'] or c['objects_with_type_conflicts']
        or c['declarations_by_kind']['unresolved'] or c['bounds_by_status']['unresolved']
        or c['bounds_by_status']['static_out_of_bounds'] or c['unmatched_reset_occurrences']
        or c['members_by_status']['unknown'] or sum(c['rejected_operands_by_role'].values())
        or c['rejected_expression_uses'] or c['accepted_operands_by_role']['unknown']
        or c['stored_data_by_status']['namespace_gap'] or c['stored_data_by_status']['shape_gap']
        or c['stored_types_by_status']['mismatch'])


def _declaration(entity: Any, suffix: str) -> tuple[str, str]:
    """Check only the root declaration and one literal array selection.

    A nested member stays unresolved; root TIMER does not prove a nested
    TIMER.ACC operand is another timer. Literal spelling is never normalized
    for identity, including [0], [00] and whitespace within brackets.
    """
    datatype = _catalog(entity.attributes.get('DataType', ''))
    kind = {'TIMER': 'timer', 'TIMER_T': 'timer', 'COUNTER': 'counter', 'CONTROL': 'control'}.get(datatype, 'other' if datatype else 'unresolved')
    raw_dimensions = entity.attributes.get('Dimensions', '')
    if not suffix:
        return kind, 'scalar' if raw_dimensions in {'', '0'} else 'unresolved'
    index = re.fullmatch(r'\[\s*([0-9]+(?:\s*,\s*[0-9]+)*)\s*\]', suffix)
    dimensions = re.fullmatch(r'\s*[0-9]+(?:\s*[, ]\s*[0-9]+)*\s*', raw_dimensions)
    if index and dimensions:
        values = [value.lstrip('0') or '0' for value in re.split(r'\s*,\s*', index.group(1))]
        sizes = [value.lstrip('0') or '0' for value in re.split(r'[, ]+', raw_dimensions.strip())]
        # Decimal text comparison avoids Python's integer-string limit and
        # never turns a lexical address into an effective runtime value.
        okay = len(values) == len(sizes) and all((len(value), value) < (len(size), size) for value, size in zip(values, sizes))
        return kind, 'static_in_bounds' if okay else 'static_out_of_bounds'
    return 'unresolved', 'unresolved'


def _catalog(value: str) -> str:
    """ASCII catalogue lookup only; source identity and spelling stay literal."""
    return value.upper() if value.isascii() else value


def _member(control_suffix: str, use_suffix: str) -> tuple[str, str | None] | None:
    if use_suffix == control_suffix:
        return 'whole_control', None
    if use_suffix.startswith(control_suffix + '.'):
        member = use_suffix[len(control_suffix) + 1:]
        return ('direct_member' if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', member) else 'other_member'), member
    return None


def _data_paths(snapshot: SourceSnapshot, tag_data: TagDataResult):
    """Index lexical decorated paths, retaining duplicates and qualification.

    Whole representations remain owner links even when no decorated path can
    be understood. Foreign elements may retain a lexical path but are marked
    unqualified. Namespaced attributes never substitute for normal attributes.
    """
    namespace = _namespace(_read_nodes(snapshot.data)[0].expanded_name)
    paths: dict[str, str | None] = {}
    namespace_ok: dict[str, bool] = {}
    shape_ok: dict[str, bool] = {}
    structure_types: dict[str, tuple[str, str] | None] = {}
    for content in tag_data.contents:
        paths[content['id']] = '' if content['format_kind'] == 'decorated' else None
        namespace_ok[content['id']] = content['xml_namespace'] == namespace and not any('}' in key for key in content['attributes'])
        shape_ok[content['id']] = not content['direct_text'].strip()
        structure_types[content['id']] = None
    for element in tag_data.elements:
        parent = paths[element['parent_id']]
        name, attrs = element['xml_name'], element['attributes']
        path = None
        if parent is not None:
            if name in {'Structure', 'Array', 'DataValue'}:
                path = parent
            elif name in {'StructureMember', 'ArrayMember', 'DataValueMember'} and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', attrs.get('Name', '')):
                path = parent + '.' + attrs['Name']
            elif name == 'Element' and re.fullmatch(r'\[\s*[0-9]+(?:\s*,\s*[0-9]+)*\s*\]', attrs.get('Index', '')):
                path = parent + attrs['Index']
        if path is not None and len(path) > MAX_ADDRESS_LENGTH:
            path = None
        paths[element['id']] = path
        namespace_ok[element['id']] = (namespace_ok[element['parent_id']] and element['xml_namespace'] == namespace
            and not any('}' in key for key in attrs))
        shape_ok[element['id']] = (shape_ok[element['parent_id']] and element['kind'] not in {'unmodeled', 'opaque'}
            and not element['direct_text'].strip())
        structure_type = structure_types[element['parent_id']]
        if path is not None and name in {'Structure', 'StructureMember'}:
            structure_type = (path, attrs.get('DataType', ''))
        structure_types[element['id']] = structure_type
        status = 'namespace_gap' if not namespace_ok[element['id']] else 'shape_gap' if not shape_ok[element['id']] else 'qualified'
        yield element, path, status, structure_type


def _index_control(index: dict[str, Any], control: dict[str, Any]) -> None:
    current = index.setdefault(control['target_id'], {})
    for part in control['suffix'].split('.') if control['suffix'] else ():
        current = current.setdefault(part, {})
    current[None] = control


def _controls(index: dict[str, Any], target: str, suffix: str):
    """Visit exact dot-prefix controls in linear suffix length, not root scans."""
    current = index.get(target, {})
    if None in current:
        yield current[None]
    for part in suffix.split('.') if suffix else ():
        current = current.get(part, {})
        if not current:
            return
        if None in current:
            yield current[None]


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, access: AccessResult,
            relationships: RelationshipResult, conditions: ConditionResult, tag_data: TagDataResult) -> StatefulObjectResult:
    if any(len(rows) > MAX_STATEFUL_OBJECT_RECORDS for rows in (inventory.rungs, inventory.entities,
            access.instructions, access.operands, access.expression_uses, conditions.nodes, tag_data.elements)):
        _invalid()
    budget = _Budget()
    rung_ok, binding_ok, _ = _provenance(snapshot, inventory)
    operands = {row['id']: row for row in access.operands}
    expression_uses = {row['id']: row for row in access.expression_uses}
    entities = {row.id: row for row in inventory.entities}
    source_instructions = {row.id: row for rung in inventory.rungs for row in rung.instructions}
    address_by_use = {identifier: row for row in relationships.addresses for role in ROLES for identifier in row[f'{role}_operand_ids']}
    identity_gaps = {row['id'] for row in relationships.identity_gaps}
    expression_by_instruction: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for use in access.expression_uses:
        expression_by_instruction[use['instruction_id']].append(use)
    nodes = {row['id']: row for row in conditions.nodes}
    instruction_nodes = {row['instruction_id']: row for row in conditions.nodes if row['instruction_id'] is not None}
    context_ok = {}
    for node in conditions.nodes:
        context_ok[node['id']] = (rung_ok[node['rung_id']] and all(context_ok[child] for child in node['child_ids'])
            and all(operands[identifier]['binding_status'] != 'root_bound' or binding_ok(operands[identifier]) for identifier in node['operand_ids'])
            and all(use['binding_status'] != 'root_bound' or binding_ok(use) for use in expression_by_instruction.get(node['instruction_id'], [])))
    c = {key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()}
    c.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
    c.update(source_rungs=len(inventory.rungs), source_instructions=len(access.instructions), source_operands=len(access.operands),
        source_expression_uses=len(access.expression_uses), source_data_elements=len(tag_data.elements),
        unparsed_rungs=sum(row.parse_status != 'parsed' for row in inventory.rungs))
    occurrences, objects, address_uses, stored_data = [], [], [], []
    by_address: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for instruction in access.instructions:
        opcode = source_instructions[instruction['id']].opcode.upper()
        if opcode not in OPCODES:
            continue
        operand = operands.get(instruction['operand_ids'][0]) if instruction['operand_ids'] else None
        target = address_by_use.get(operand['id']) if operand is not None else None
        status = ('signature_unresolved' if instruction['status'] != 'classified' else 'exact_address' if target
                  else 'identity_gap' if operand and operand['id'] in identity_gaps else 'unbound')
        if not rung_ok[instruction['rung_id']] or operand and operand['binding_status'] == 'root_bound' and not binding_ok(operand):
            status = 'namespace_gap'
        node = instruction_nodes[instruction['id']]
        guard = nodes[node['child_ids'][0]]
        context = ('namespace_gap' if not context_ok[guard['id']] else 'opaque' if guard['has_opaque']
            else 'binding_gaps' if guard['has_binding_gap'] else 'stateful' if guard['has_stateful'] else 'modeled')
        row = {'id': instruction['id'], 'rung_id': instruction['rung_id'], 'opcode': opcode,
            'control_operand_id': operand['id'] if operand else None,
            'control_address_id': target['id'] if status == 'exact_address' else None,
            'target_status': status, 'guard_id': guard['id'], 'context_status': context}
        budget.retain(row)
        occurrences.append(row)
        if row['control_address_id'] is not None:
            by_address[row['control_address_id']].append(row)
        c['occurrences_by_opcode'][opcode] += 1
        c['targets_by_status'][status] += 1
        c['contexts_by_status'][context] += 1
    owners = {row['source_id']: row for row in tag_data.owners}
    object_index: dict[str, Any] = {}
    for address in relationships.addresses:
        if address['id'] not in by_address:
            continue
        rows = by_address[address['id']]
        opcodes = {row['opcode'] for row in rows}
        timer, counter = bool(opcodes & TIMER_OPCODES), bool(opcodes & COUNTER_OPCODES)
        family = 'mixed' if timer and counter else 'timer' if timer else 'counter' if counter else 'reset_only'
        declaration, bounds = _declaration(entities[address['target_id']], address['suffix'])
        conflict = (declaration != 'unresolved' and
            (timer and declaration != 'timer' or counter and declaration != 'counter'
             or family == 'reset_only' and declaration not in {'timer', 'counter', 'control'}))
        owner = owners.get(address['target_id'])
        row = {'id': address['id'], 'target_id': address['target_id'], 'suffix': address['suffix'],
            'producer_ids': [item['id'] for item in rows if item['opcode'] != 'RES'],
            'reset_ids': [item['id'] for item in rows if item['opcode'] == 'RES'],
            'family': family, 'declaration_kind': declaration, 'type_conflict': bool(conflict), 'bounds_status': bounds,
            'owner_id': owner['source_id'] if owner else None, 'content_ids': list(owner['content_ids']) if owner else [],
            'has_tof_reset': 'TOF' in opcodes and 'RES' in opcodes}
        budget.retain(row)
        objects.append(row)
        _index_control(object_index, row)
        c['objects_by_family'][family] += 1
        c['declarations_by_kind'][declaration] += 1
        c['bounds_by_status'][bounds] += 1
        c['objects_with_multiple_producers'] += int(len(row['producer_ids']) > 1)
        c['objects_with_resets'] += int(bool(row['reset_ids']))
        c['objects_with_matched_resets'] += int(bool(row['reset_ids']) and bool(row['producer_ids']))
        c['matched_reset_occurrences' if row['producer_ids'] else 'unmatched_reset_occurrences'] += len(row['reset_ids'])
        c['objects_with_type_conflicts'] += int(row['type_conflict'])
        c['objects_with_tof_resets'] += int(row['has_tof_reset'])
        c['objects_with_data' if row['content_ids'] else 'objects_without_data'] += 1
        c['content_links_total'] += len(row['content_ids'])
        c['producer_occurrences'] += len(row['producer_ids'])
        c['reset_occurrences'] += len(row['reset_ids'])
    for address in relationships.addresses:
        for control in _controls(object_index, address['target_id'], address['suffix']):
            relation = _member(control['suffix'], address['suffix'])
            if relation is None:
                continue
            kind, member = relation
            known = MEMBERS.get(control['family'], MEMBERS.get(control['declaration_kind'], frozenset()))
            member_status = 'whole_control' if member is None else 'known' if _catalog(member) in known else 'unknown'
            row = {'object_id': control['id'], 'address_id': address['id'], 'kind': kind, 'member': member,
                'member_status': member_status, 'rejected_operand_ids': [], 'expression_use_ids': [], 'rejected_expression_use_ids': []}
            for role in sorted(ROLES):
                accepted = []
                for identifier in address[f'{role}_operand_ids']:
                    okay = binding_ok(operands[identifier])
                    (accepted if okay else row['rejected_operand_ids']).append(identifier)
                    c['accepted_operands_by_role' if okay else 'rejected_operands_by_role'][role] += 1
                row[f'{role}_operand_ids'] = accepted
            for identifier in address['expression_use_ids']:
                okay = binding_ok(expression_uses[identifier])
                row['expression_use_ids' if okay else 'rejected_expression_use_ids'].append(identifier)
                c['accepted_expression_uses' if okay else 'rejected_expression_uses'] += 1
            budget.retain(row)
            address_uses.append(row)
            c['uses_by_kind'][kind] += 1
            c['members_by_status'][member_status] += 1
    for element, path, status, structure_type in _data_paths(snapshot, tag_data):
        if path is None:
            continue
        for control in _controls(object_index, element['owner_id'], path):
            relation = _member(control['suffix'], path)
            if relation is None:
                continue
            kind, member = relation
            expected_type = entities[control['target_id']].attributes.get('DataType', '')
            type_status = 'unresolved'
            if (status == 'qualified' and control['bounds_status'] != 'unresolved' and expected_type
                    and structure_type is not None and structure_type[0] == control['suffix'] and structure_type[1]):
                type_status = 'matching' if _catalog(structure_type[1]) == _catalog(expected_type) else 'mismatch'
            row = {'object_id': control['id'], 'element_id': element['id'],
                'kind': 'control' if kind == 'whole_control' else 'member', 'member': member,
                'status': status, 'type_status': type_status}
            budget.retain(row)
            stored_data.append(row)
            c['stored_data_by_kind'][row['kind']] += 1
            c['stored_data_by_status'][row['status']] += 1
            c['stored_types_by_status'][type_status] += 1
    c.update(occurrences_total=len(occurrences), occurrence_rungs=len({row['rung_id'] for row in occurrences}),
        objects_total=len(objects), address_uses_total=len(address_uses), stored_data_total=len(stored_data))
    return StatefulObjectResult(deepcopy(inventory.snapshot), 'partial' if _partial(c) else 'complete',
        occurrences, objects, address_uses, stored_data, c)


def analyze_stateful_objects(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, tag_data: TagDataResult) -> StatefulObjectResult:
    try:
        if type(conditions) is not ConditionResult or conditions.schema_version not in (3, 4, 5, 6):
            _invalid()
        validate_conditions(snapshot, inventory, references, access, calculations, rung_analysis, relationships, conditions)
        validate_tag_data(snapshot, inventory, tag_data)
        result = _derive(snapshot, inventory, access, relationships, conditions, tag_data)
        render_stateful_objects_json(result)
        return result
    except StatefulObjectError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_stateful_objects(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, tag_data: TagDataResult, result: StatefulObjectResult) -> None:
    try:
        render_stateful_objects_json(result)
        expected = analyze_stateful_objects(snapshot, inventory, references, access, calculations,
            rung_analysis, relationships, conditions, tag_data)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except StatefulObjectError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_stateful_objects_json(result: StatefulObjectResult) -> str:
    try:
        if type(result) is not StatefulObjectResult or vars(result).keys() != set(StatefulObjectResult.__dataclass_fields__):
            _invalid()
        remaining = MAX_STATEFUL_OBJECT_BYTES
        frames = [(iter((vars(result),)), None)]
        active = set()
        while frames:
            try:
                value = next(frames[-1][0])
            except StopIteration:
                _, identifier = frames.pop()
                if identifier is not None:
                    active.remove(identifier)
                continue
            remaining -= 1
            if len(frames) > 12:
                _invalid()
            if type(value) in (dict, list):
                identifier = id(value)
                if identifier in active or len(value) > MAX_STATEFUL_OBJECT_RECORDS:
                    _invalid()
                active.add(identifier)
                if type(value) is dict:
                    if any(type(key) is not str for key in value):
                        _invalid()
                    remaining -= sum(len(key.encode('utf-8')) for key in value)
                    frames.append((iter(value.values()), identifier))
                else:
                    frames.append((iter(value), identifier))
            elif type(value) is str:
                remaining -= len(value.encode('utf-8'))
            elif type(value) not in (int, bool, type(None)):
                _invalid()
            if remaining < 0:
                _invalid()
        if sum(len(getattr(result, key)) for key in ('occurrences', 'objects', 'address_uses', 'stored_data')) > MAX_STATEFUL_OBJECT_RECORDS:
            _invalid()
        output, size = StringIO(), 1
        for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).iterencode(vars(result)):
            size += len(chunk.encode('utf-8'))
            if size > MAX_STATEFUL_OBJECT_JSON_BYTES:
                _invalid()
            output.write(chunk)
        return output.getvalue() + '\n'
    except StatefulObjectError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
