"""Bounded PID source connections, without execution or cascade interpretation.

Slot labels never assign access roles. Address IDs retain the relationship
companion's exact expanded spelling; root accesses never become member writes.
All stored-member and incoming-condition links point to existing evidence.
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
from .pid import PidResult
from .pid_members import FIELD_CATALOG, MEMBER_GROUPS, PidMemberResult, validate_pid_members
from .references import ReferenceResult, _strict_record_match
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult
from .source import _read_nodes
from .tag_data import TagDataResult, _namespace

MAX_PID_CONNECTION_RECORDS = 250_000
MAX_PID_CONNECTION_BYTES = 8 * 1024 * 1024
MAX_PID_CONNECTION_JSON_BYTES = 8 * 1024 * 1024
SLOT_STATUSES = frozenset({'exact_address', 'literal', 'binding_gap', 'identity_gap',
                         'namespace_gap', 'signature_unresolved'})
CONTROL_STATUSES = frozenset({'linked', 'unavailable', 'namespace_gap', 'static_suffix',
                            'owner_not_pid', 'owner_dimensions_unmodeled'})
MASTER_STATUSES = frozenset({'signature_unresolved', 'literal', 'binding_gap', 'identity_gap',
    'namespace_gap', 'static_suffix', 'owner_not_pid', 'owner_dimensions_unmodeled',
    'missing_occurrence', 'single_occurrence', 'multiple_occurrences'})
ADDRESS_KINDS = frozenset({'slot_address', 'whole_owner', 'direct_member',
                          'unknown_member', 'deferred_suffix'})
LINK_ROLES = frozenset({'read', 'write', 'read_write', 'unknown', 'expression_read',
                        'namespace_gap_operand', 'namespace_gap_expression'})
COUNT_MAPS = {'slots_by_status': SLOT_STATUSES, 'control_by_status': CONTROL_STATUSES,
              'masters_by_status': MASTER_STATUSES, 'address_kinds': ADDRESS_KINDS,
              'address_links_by_role': LINK_ROLES, 'member_addresses_by_group': MEMBER_GROUPS}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | frozenset({'source_pid_partial', 'source_members_partial',
    'occurrences_total', 'slots_total', 'addresses_total', 'master_self_references',
    'master_candidate_links', 'incoming_condition_links', 'occurrences_with_condition_context',
    'occurrences_without_condition_context'})
PID_CONNECTION_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'pid-connections-1',
    'analysis_scope': 'pid_source_connections', 'address_identity': 'exact_expanded_spelling',
    'member_association': 'direct_member_spelling_only', 'execution_analysis': 'not_implemented',
    'cascade_analysis': 'not_implemented', 'engineering_loop_identity': 'not_implemented',
    'numeric_analysis': 'not_implemented', 'effective_value_selection': 'not_implemented',
}
PID_CONNECTION_CONSTANTS_V2 = {**PID_CONNECTION_CONSTANTS,
    'schema_version': 2, 'analyzer_version': 'pid-connections-2'}
_ROLES = ('read', 'write', 'read_write', 'unknown')
_DIRECT_MEMBER = re.compile(r'\.([A-Za-z_][A-Za-z0-9_]*)', re.ASCII)
_SEMANTIC_ATTRIBUTES = frozenset({'Name', 'TagType', 'AliasFor', 'DataType', 'Dimensions', 'Type'})


class PidConnectionError(ValueError):
    """Fixed source-free validation and resource rejection."""


def _invalid() -> None:
    raise PidConnectionError('PID connection evidence is inconsistent or exceeds its limits.') from None


@dataclass(frozen=True)
class PidConnectionResult:
    snapshot: dict[str, str | int]
    status: str
    occurrences: list[dict[str, Any]]
    slots: list[dict[str, Any]]
    addresses: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'pid-connections-1'
    analysis_scope: str = 'pid_source_connections'
    address_identity: str = 'exact_expanded_spelling'
    member_association: str = 'direct_member_spelling_only'
    execution_analysis: str = 'not_implemented'
    cascade_analysis: str = 'not_implemented'
    engineering_loop_identity: str = 'not_implemented'
    numeric_analysis: str = 'not_implemented'
    effective_value_selection: str = 'not_implemented'

    def to_dict(self) -> dict[str, Any]:
        render_pid_connections_json(self)
        return deepcopy(vars(self))


class _Budget:
    def __init__(self) -> None:
        self.records = self.bytes = 0

    def retain(self, row: dict[str, Any]) -> None:
        self.records += 1
        if self.records > MAX_PID_CONNECTION_RECORDS:
            _invalid()
        self.bytes += len(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self.bytes > MAX_PID_CONNECTION_BYTES:
            _invalid()


def _provenance(snapshot: SourceSnapshot, inventory: InventoryResult):
    nodes = _read_nodes(snapshot.data)
    namespace = _namespace(nodes[0].expanded_name)
    supported: dict[str, bool] = {}
    for node in nodes:
        supported[node.locator] = (
            _namespace(node.expanded_name) == namespace
            and not any('}' in key and key.rsplit('}', 1)[-1] in _SEMANTIC_ATTRIBUTES
                        for key in node.expanded_attributes)
            and (node.parent is None or supported[nodes[node.parent].locator]))
    by_locator = {node.locator: node for node in nodes}
    entities = {row.id: row for row in inventory.entities}
    rung_ok = {}
    for rung in inventory.rungs:
        node = by_locator[rung.locator]
        rung_ok[rung.id] = supported[rung.locator] and all(
            supported[nodes[index].locator] for index in node.children if nodes[index].name == 'Text')

    def binding_ok(row: dict[str, Any]) -> bool:
        return rung_ok.get(row['rung_id'], False) and all(
            identifier in entities and supported[entities[identifier].locator]
            for identifier in [row['symbol_id'], *row['alias_chain'], row['target_id']])

    def owner_status(row: dict[str, Any]) -> str:
        if not binding_ok(row):
            return 'namespace_gap'
        if row['suffix']:
            return 'static_suffix'
        node = by_locator[entities[row['target_id']].locator]
        datatype = node.expanded_attributes.get('DataType')
        if not (type(datatype) is str and datatype.isascii() and datatype.upper() == 'PID'):
            return 'owner_not_pid'
        if any(key.rsplit('}', 1)[-1] == 'Dimensions' for key in node.expanded_attributes):
            return 'owner_dimensions_unmodeled'
        return 'linked'

    return binding_ok, owner_status, rung_ok


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, access: AccessResult,
            relationships: RelationshipResult, conditions: ConditionResult,
            pid: PidResult, pid_members: PidMemberResult, *, schema_version: int = 1) -> PidConnectionResult:
    if any(len(rows) > MAX_PID_CONNECTION_RECORDS for rows in
           (pid.occurrences, pid.operands, relationships.addresses, access.operands, access.expression_uses)):
        _invalid()
    budget = _Budget()
    binding_ok, owner_status, rung_ok = _provenance(snapshot, inventory)
    operands = {row['id']: row for row in access.operands}
    uses = {row['id']: row for row in access.expression_uses}
    address_by_operand = {identifier: row for row in relationships.addresses
                          for role in _ROLES for identifier in row[f'{role}_operand_ids']}
    controls: dict[str, tuple[str | None, str]] = {}
    owner_occurrences: dict[str, list[str]] = defaultdict(list)
    for occurrence in pid.occurrences:
        first = operands[occurrence['operand_ids'][0]] if occurrence['operand_ids'] else None
        status = 'unavailable'
        if occurrence['signature_status'] == 'recognized' and first['binding_status'] == 'root_bound':
            status = owner_status(first)
        owner = first['target_id'] if status == 'linked' else None
        controls[occurrence['id']] = (owner, status)
        if owner is not None:
            owner_occurrences[owner].append(occurrence['id'])
    incoming: dict[str, list[str]] = defaultdict(list)
    transfer_kinds = {'opaque_transfer', 'pass_through'} if schema_version == 2 else {'opaque_transfer'}
    for node in conditions.nodes:
        # The incoming evidence survives a refined outgoing transfer rule.
        # Condition4 models qualified PID occurrences as pass-through; older
        # conditions and unsupported signatures still retain opaque transfers.
        # Schema1 stays frozen, including its historical condition4 omission.
        # Both companions are authenticated before these source IDs are joined.
        if (node['kind'] in transfer_kinds and node['instruction_id'] in controls
                and node['child_ids']):
            incoming[node['instruction_id']].append(node['child_ids'][0])
    coverage = {key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()}
    coverage.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
    coverage.update(source_pid_partial=int(pid.status == 'partial'),
                    source_members_partial=int(pid_members.status == 'partial'))
    slots = []
    needed_addresses: set[str] = set()
    for source in pid.operands:
        operand = operands[source['id']]
        address = address_by_operand.get(source['id'])
        if source['slot'] == 'unknown':
            status = 'signature_unresolved'
        elif operand['binding_status'] == 'literal':
            status = 'literal'
        elif operand['binding_status'] != 'root_bound':
            status = 'binding_gap'
        elif not binding_ok(operand):
            status = 'namespace_gap'
        elif address is None:
            status = 'identity_gap'
        else:
            status = 'exact_address'
        address_id = address['id'] if status == 'exact_address' else None
        if address_id is not None:
            needed_addresses.add(address_id)
        row = {'id': source['id'], 'instruction_id': source['instruction_id'],
               'slot': source['slot'], 'status': status, 'address_id': address_id}
        budget.retain(row)
        slots.append(row)
        coverage['slots_by_status'][status] += 1
    slot_by_id = {row['id']: row for row in slots}
    member_owner = {row['structure_id']: row['owner_id'] for row in pid_members.structures}
    members: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in pid_members.members:
        if row['field'] is not None:
            members[member_owner[row['structure_id']], row['field']].append(row['element_id'])
    addresses = []
    owner_addresses: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for address in relationships.addresses:
        owner = address['target_id']
        if owner not in owner_occurrences and address['id'] not in needed_addresses:
            continue
        kind, field, group = 'slot_address', None, None
        if owner in owner_occurrences:
            direct = _DIRECT_MEMBER.fullmatch(address['suffix'])
            if not address['suffix']:
                kind = 'whole_owner'
            elif direct:
                spelling = direct[1].upper()
                if spelling in FIELD_CATALOG:
                    kind, field = 'direct_member', spelling
                    group = FIELD_CATALOG[field]['group']
                else:
                    kind, group = 'unknown_member', 'unknown'
            else:
                kind = 'deferred_suffix'
        row = {'id': address['id'], 'owner_id': owner, 'kind': kind, 'field': field, 'group': group,
               'member_ids': list(members[owner, field]) if field is not None else [],
               **{f'{role}_operand_ids': [] for role in _ROLES}, 'expression_use_ids': [],
               'namespace_gap_operand_ids': [], 'namespace_gap_expression_use_ids': []}
        for role in _ROLES:
            for identifier in address[f'{role}_operand_ids']:
                supported = binding_ok(operands[identifier])
                row[f'{role}_operand_ids' if supported else 'namespace_gap_operand_ids'].append(identifier)
                coverage['address_links_by_role'][role if supported else 'namespace_gap_operand'] += 1
        for identifier in address['expression_use_ids']:
            supported = binding_ok(uses[identifier])
            row['expression_use_ids' if supported else 'namespace_gap_expression_use_ids'].append(identifier)
            coverage['address_links_by_role']['expression_read' if supported else 'namespace_gap_expression'] += 1
        budget.retain(row)
        addresses.append(row)
        owner_addresses[owner].append(row)
        coverage['address_kinds'][kind] += 1
        if kind in {'direct_member', 'unknown_member'}:
            coverage['member_addresses_by_group'][group] += 1
    occurrences = []
    for source in pid.occurrences:
        owner, control_status = controls[source['id']]
        master = {'operand_id': None, 'status': 'signature_unresolved', 'owner_id': None,
                  'occurrence_ids': [], 'self_reference': 0}
        if source['signature_status'] == 'recognized':
            identifier = source['operand_ids'][4]
            slot = slot_by_id[identifier]
            master['operand_id'] = identifier
            master['status'] = slot['status']
            if slot['status'] == 'exact_address':
                operand = operands[identifier]
                disposition = owner_status(operand)
                if disposition == 'linked':
                    target = operand['target_id']
                    candidates = list(owner_occurrences[target])
                    master.update(owner_id=target, occurrence_ids=candidates,
                                  self_reference=int(source['id'] in candidates),
                                  status=('missing_occurrence' if not candidates else
                                          'single_occurrence' if len(candidates) == 1 else 'multiple_occurrences'))
                else:
                    master['status'] = disposition
        grouped = {group: [] for group in sorted(MEMBER_GROUPS)}
        whole, deferred, unknown = [], [], []
        for address in owner_addresses.get(owner, []):
            kind = address['kind']
            if kind == 'direct_member':
                grouped[address['group']].append(address['id'])
            elif kind == 'whole_owner':
                whole.append(address['id'])
            elif kind == 'deferred_suffix':
                deferred.append(address['id'])
            elif kind == 'unknown_member':
                unknown.append(address['id'])
                grouped['unknown'].append(address['id'])
        context = list(incoming[source['id']]) if rung_ok[source['rung_id']] else []
        row = {'id': source['id'], 'rung_id': source['rung_id'], 'slot_ids': list(source['operand_ids']),
               'control_owner_id': owner, 'control_status': control_status,
               'member_address_ids_by_group': grouped, 'whole_owner_address_ids': whole,
               'deferred_address_ids': deferred, 'unknown_member_address_ids': unknown,
               'master': master, 'incoming_condition_ids': context}
        budget.retain(row)
        occurrences.append(row)
        coverage['control_by_status'][control_status] += 1
        coverage['masters_by_status'][master['status']] += 1
        coverage['master_self_references'] += master['self_reference']
        coverage['master_candidate_links'] += len(master['occurrence_ids'])
        coverage['incoming_condition_links'] += len(context)
        coverage['occurrences_with_condition_context' if context else 'occurrences_without_condition_context'] += 1
    coverage.update(occurrences_total=len(occurrences), slots_total=len(slots), addresses_total=len(addresses))
    partial = _partial(coverage)
    constants = PID_CONNECTION_CONSTANTS_V2 if schema_version == 2 else PID_CONNECTION_CONSTANTS
    return PidConnectionResult(dict(pid.snapshot), 'partial' if partial else 'complete',
                               occurrences, slots, addresses, coverage, **constants)


def _partial(c: dict[str, Any]) -> bool:
    return bool(c['source_pid_partial'] or c['source_members_partial']
        or any(c['slots_by_status'][key] for key in SLOT_STATUSES - {'exact_address', 'literal'})
        or any(c['control_by_status'][key] for key in CONTROL_STATUSES - {'linked'})
        or any(c['masters_by_status'][key] for key in MASTER_STATUSES - {'literal', 'single_occurrence'})
        or c['master_self_references'] or c['occurrences_without_condition_context']
        or c['address_kinds']['unknown_member'] or c['address_kinds']['deferred_suffix']
        or c['address_links_by_role']['namespace_gap_operand']
        or c['address_links_by_role']['namespace_gap_expression'])


def analyze_pid_connections(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, tag_data: TagDataResult, pid: PidResult,
        pid_members: PidMemberResult, *, schema_version: int = 1) -> PidConnectionResult:
    """Authenticate both canonical chains before joining IDs conservatively."""
    try:
        if type(schema_version) is not int or schema_version not in (1, 2):
            _invalid()
        validate_conditions(snapshot, inventory, references, access, calculations, rung_analysis,
                            relationships, conditions)
        validate_pid_members(snapshot, inventory, references, tag_data, pid, pid_members)
        result = _derive(snapshot, inventory, access, relationships, conditions, pid, pid_members,
                         schema_version=schema_version)
        render_pid_connections_json(result)
        return result
    except PidConnectionError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_pid_connections(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, tag_data: TagDataResult, pid: PidResult,
        pid_members: PidMemberResult, result: PidConnectionResult) -> None:
    try:
        render_pid_connections_json(result)
        expected = analyze_pid_connections(snapshot, inventory, references, access, calculations,
            rung_analysis, relationships, conditions, tag_data, pid, pid_members,
            schema_version=result.schema_version)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except PidConnectionError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_pid_connections_json(result: PidConnectionResult) -> str:
    """Serialize bounded native containers; source authentication is separate."""
    try:
        if type(result) is not PidConnectionResult or vars(result).keys() != set(PidConnectionResult.__dataclass_fields__):
            _invalid()
        if type(result.schema_version) is not int or result.schema_version not in (1, 2):
            _invalid()
        constants = PID_CONNECTION_CONSTANTS_V2 if result.schema_version == 2 else PID_CONNECTION_CONSTANTS
        if any(type(getattr(result, key)) is not type(value) or getattr(result, key) != value
               for key, value in constants.items()):
            _invalid()
        budget = MAX_PID_CONNECTION_BYTES
        frames = [(iter((vars(result),)), None)]
        active: set[int] = set()
        while frames:
            try:
                value = next(frames[-1][0])
            except StopIteration:
                _, identifier = frames.pop()
                if identifier is not None:
                    active.remove(identifier)
                continue
            budget -= 1
            if len(frames) > 12 or budget < 0:
                _invalid()
            if type(value) in (dict, list):
                identifier = id(value)
                if identifier in active or len(value) > MAX_PID_CONNECTION_RECORDS:
                    _invalid()
                active.add(identifier)
                if type(value) is dict:
                    if any(type(key) is not str for key in value):
                        _invalid()
                    budget -= sum(len(key.encode('utf-8')) for key in value)
                    frames.append((iter(value.values()), identifier))
                else:
                    frames.append((iter(value), identifier))
            elif type(value) is str:
                budget -= len(value.encode('utf-8'))
            elif type(value) not in (int, type(None)):
                _invalid()
            if budget < 0:
                _invalid()
        if sum(len(getattr(result, key)) for key in ('occurrences', 'slots', 'addresses')) > MAX_PID_CONNECTION_RECORDS:
            _invalid()
        output = StringIO()
        size = 1
        for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, indent=2,
                                      allow_nan=False).iterencode(vars(result)):
            size += len(chunk.encode('utf-8'))
            if size > MAX_PID_CONNECTION_JSON_BYTES:
                _invalid()
            output.write(chunk)
        return output.getvalue() + '\n'
    except PidConnectionError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
