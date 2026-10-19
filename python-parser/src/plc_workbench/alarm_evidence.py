"""Bounded stored alarm declarations and XML, without effective alarm behavior.

The recognized envelopes follow 1756-RM014D (September 2025), pages 131-139
and 180-190. Attributes and text remain lexical source facts. Definitions are
not instantiated; relative inputs, severity, messages and commands are not run.
IDs identify one captured snapshot and do not persist across changed exports.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from io import StringIO
import json
from typing import Any

from .models import InventoryResult, SourceSnapshot
from .source import MAX_ELEMENTS, _entity_id, _read_nodes
from .tag_data import OWNER_KINDS, TagDataResult, _namespace, _strict_match, validate_tag_data

MAX_ALARM_EVIDENCE_RECORDS = 50_000
MAX_ALARM_EVIDENCE_LINKS = 100_000
MAX_ALARM_XML_VISITS = MAX_ELEMENTS
MAX_ALARM_EVIDENCE_BYTES = 8 * 1024 * 1024
MAX_ALARM_EVIDENCE_JSON_BYTES = 8 * 1024 * 1024
ROW_GROUPS = ('declarations', 'containers', 'elements')
DECLARED_TYPES = frozenset({'ALARM_ANALOG', 'ALARM_DIGITAL'})
QUALIFICATIONS = frozenset({'qualified', 'source_gap'})
CONTAINER_KINDS = frozenset({'alarm_conditions', 'alarm_definitions', 'alarm_data', 'orphan'})
_ELEMENT_NAMES = {
    'AlarmConditions': 'alarm_conditions', 'AlarmCondition': 'alarm_condition',
    'AlarmDefinitions': 'alarm_definitions', 'DataTypeAlarmDefinition': 'data_type_alarm_definition',
    'MemberAlarmDefinition': 'member_alarm_definition', 'AlarmConfig': 'alarm_config',
    'AlarmAnalogParameters': 'alarm_analog_parameters', 'AlarmDigitalParameters': 'alarm_digital_parameters',
    'Messages': 'messages', 'Message': 'message', 'Text': 'text',
    'AlarmClass': 'alarm_class', 'HMIGroup': 'hmi_group',
    'HMICommand': 'hmi_command', 'HMICmd': 'hmi_command',
}
ELEMENT_KINDS = frozenset(_ELEMENT_NAMES.values()) | {'unknown'}
GAP_CODES = frozenset({'namespace_gap', 'unsupported_placement', 'unknown_element',
    'missing_identity', 'unexpected_children', 'unexpected_direct_text', 'duplicate_sibling', 'ancestor_gap'})
COUNT_MAPS = {
    'declarations_by_kind': OWNER_KINDS, 'declarations_by_type': DECLARED_TYPES,
    'declarations_by_qualification': QUALIFICATIONS,
    'containers_by_kind': CONTAINER_KINDS, 'containers_by_qualification': QUALIFICATIONS,
    'elements_by_kind': ELEMENT_KINDS, 'elements_by_qualification': QUALIFICATIONS,
    'gaps_by_code': GAP_CODES,
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | frozenset({
    'source_xml_elements', 'source_entities', 'source_data_contents',
    'declarations_total', 'containers_total', 'elements_total', 'records_with_gaps',
    'gap_links_total', 'content_links_total', 'container_links_total',
    'declarations_with_data', 'declarations_with_containers', 'direct_text_bytes',
    'attribute_pairs', 'duplicate_groups', 'duplicate_records',
})
ALARM_EVIDENCE_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'alarm-evidence-1',
    'analysis_scope': 'explicit_alarm_declaration_source_evidence',
    'execution_analysis': 'not_implemented', 'value_analysis': 'not_implemented',
    'effective_value_selection': 'not_implemented', 'definition_expansion': 'not_implemented',
    'relative_input_binding': 'not_implemented', 'severity_analysis': 'not_implemented',
    'shutdown_analysis': 'not_implemented', 'engineering_review': 'unreviewed',
}
# Only alarm-specific anchors are recognized outside an already captured tree.
# Generic Messages/Message/Text elsewhere must not become alarm evidence.
_ANCHORS = frozenset(_ELEMENT_NAMES) - {'Messages', 'Message', 'Text'}
_NAMED = frozenset({'AlarmCondition', 'DataTypeAlarmDefinition', 'MemberAlarmDefinition'})
_LEAVES = frozenset({'Text', 'AlarmClass', 'HMIGroup', 'HMICommand', 'HMICmd',
                     'AlarmAnalogParameters', 'AlarmDigitalParameters'})
_CHILDREN = {
    'AlarmConditions': {'AlarmCondition'}, 'AlarmDefinitions': {'DataTypeAlarmDefinition'},
    'DataTypeAlarmDefinition': {'MemberAlarmDefinition'},
    'AlarmCondition': {'AlarmConfig'}, 'MemberAlarmDefinition': {'AlarmConfig'},
    'Data': {'AlarmAnalogParameters', 'AlarmDigitalParameters', 'AlarmConfig'},
    'AlarmConfig': {'Messages', 'AlarmClass', 'HMIGroup', 'HMICommand', 'HMICmd'},
    'Messages': {'Message'}, 'Message': {'Text'},
}


class AlarmEvidenceError(ValueError):
    """Fixed source-free capture or validation rejection."""


def _invalid() -> None:
    raise AlarmEvidenceError('Alarm evidence is inconsistent or exceeds its limits.') from None


@dataclass(frozen=True)
class AlarmEvidenceResult:
    snapshot: dict[str, str | int]
    status: str
    declarations: list[dict[str, Any]]
    containers: list[dict[str, Any]]
    elements: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'alarm-evidence-1'
    analysis_scope: str = 'explicit_alarm_declaration_source_evidence'
    execution_analysis: str = 'not_implemented'
    value_analysis: str = 'not_implemented'
    effective_value_selection: str = 'not_implemented'
    definition_expansion: str = 'not_implemented'
    relative_input_binding: str = 'not_implemented'
    severity_analysis: str = 'not_implemented'
    shutdown_analysis: str = 'not_implemented'
    engineering_review: str = 'unreviewed'

    def to_dict(self) -> dict[str, Any]:
        render_alarm_evidence_json(self)
        return deepcopy(vars(self))


def _capture(snapshot: SourceSnapshot, inventory: InventoryResult,
             tag_data: TagDataResult) -> AlarmEvidenceResult:
    nodes = _read_nodes(snapshot.data)
    if len(nodes) > MAX_ALARM_XML_VISITS:
        _invalid()
    namespace = _namespace(nodes[0].expanded_name)
    entities = {row.locator: row for row in inventory.entities}
    source_contents = {row['source_id']: row['content_ids'] for row in tag_data.owners}
    declarations: list[dict[str, Any]] = []
    containers: list[dict[str, Any]] = []
    elements: list[dict[str, Any]] = []
    declared: dict[str, dict[str, Any]] = {}
    qualified: dict[int, bool] = {}
    nearest: dict[int, Any] = {}
    selected: dict[int, int] = {}
    rows: dict[int, dict[str, Any]] = {}
    duplicate_groups: dict[tuple[Any, ...], list[int]] = defaultdict(list)
    retained_bytes = 4096
    retained_records = retained_links = 0

    def retain(row: dict[str, Any]) -> None:
        nonlocal retained_bytes, retained_records
        retained_records += 1
        retained_bytes += len(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if retained_records > MAX_ALARM_EVIDENCE_RECORDS or retained_bytes > MAX_ALARM_EVIDENCE_BYTES:
            _invalid()

    def link(target: list[str], identifier: str) -> None:
        nonlocal retained_bytes, retained_links
        retained_links += 1
        retained_bytes += len(identifier.encode('utf-8')) + 8
        if retained_links > MAX_ALARM_EVIDENCE_LINKS or retained_bytes > MAX_ALARM_EVIDENCE_BYTES:
            _invalid()
        target.append(identifier)

    for index, node in enumerate(nodes):
        qualified[index] = (_namespace(node.expanded_name) == namespace
            and all('}' not in key for key in node.expanded_attributes)
            and (node.parent is None or qualified[node.parent]))
        entity = entities.get(node.locator)
        parent_owner = nearest.get(node.parent)
        nearest[index] = entity if entity is not None else parent_owner
        if entity is not None and entity.kind in OWNER_KINDS and entity.attributes.get('DataType') in DECLARED_TYPES:
            gaps = [] if qualified[index] else ['namespace_gap']
            if not entity.name or not entity.name.strip():
                gaps.append('missing_identity')
            declaration = {
                'id': _entity_id(snapshot.id, 'alarm_declaration', node.locator),
                'source_id': entity.id, 'kind': entity.kind,
                'declared_type': entity.attributes['DataType'],
                'qualification': 'source_gap' if gaps else 'qualified', 'gap_codes': sorted(gaps),
                'content_ids': [], 'container_ids': [],
            }
            retain(declaration)
            for identifier in source_contents.get(entity.id, []):
                link(declaration['content_ids'], identifier)
            declarations.append(declaration)
            declared[entity.id] = declaration
        root_index = selected.get(node.parent)
        alarm_data = node.name == 'Data' and node.attributes.get('Format') == 'Alarm'
        if root_index is None and node.name not in _ANCHORS and not alarm_data:
            continue
        gaps: list[str] = []
        if not qualified[index]:
            gaps.append('namespace_gap')
        if root_index is None:
            kind = ('alarm_data' if alarm_data else 'alarm_conditions' if node.name == 'AlarmConditions'
                    else 'alarm_definitions' if node.name == 'AlarmDefinitions' else 'orphan')
            direct_owner = entities.get(nodes[node.parent].locator) if node.parent is not None else None
            placement = (kind == 'alarm_conditions' and direct_owner is not None and direct_owner.kind == 'tag'
                or kind == 'alarm_definitions' and direct_owner is not None and direct_owner.kind == 'controller'
                or kind == 'alarm_data' and direct_owner is not None and direct_owner.kind in OWNER_KINDS
                    and direct_owner.attributes.get('DataType') in DECLARED_TYPES)
            if not placement:
                gaps.append('unsupported_placement')
            if direct_owner is not None and (not direct_owner.name or not direct_owner.name.strip()):
                gaps.append('missing_identity')
            identifier = _entity_id(snapshot.id, 'alarm_container', node.locator)
            row = {'id': identifier, 'owner_id': parent_owner.id if parent_owner is not None else None,
                'parent_id': None, 'locator': node.locator, 'xml_name': node.name,
                'xml_namespace': _namespace(node.expanded_name), 'attributes': dict(node.expanded_attributes),
                'direct_text': node.text, 'kind': kind, 'qualification': 'qualified', 'gap_codes': gaps}
            root_index = index
            containers.append(row)
            if row['owner_id'] in declared:
                link(declared[row['owner_id']]['container_ids'], identifier)
        else:
            root = rows[root_index]
            kind = _ELEMENT_NAMES.get(node.name, 'unknown')
            if kind == 'unknown':
                gaps.append('unknown_element')
            if node.name not in _CHILDREN.get(nodes[node.parent].name, set()):
                gaps.append('unsupported_placement')
            if node.name in {'AlarmAnalogParameters', 'AlarmDigitalParameters'}:
                expected = 'ALARM_ANALOG' if node.name == 'AlarmAnalogParameters' else 'ALARM_DIGITAL'
                owner = nearest.get(root_index)
                if owner is None or owner.attributes.get('DataType') != expected:
                    gaps.append('unsupported_placement')
            row = {'id': _entity_id(snapshot.id, 'alarm_element', node.locator),
                'container_id': root['id'], 'owner_id': root['owner_id'],
                'parent_id': rows[node.parent]['id'], 'locator': node.locator, 'ordinal': node.ordinal,
                'xml_name': node.name, 'xml_namespace': _namespace(node.expanded_name),
                'attributes': dict(node.expanded_attributes), 'direct_text': node.text,
                'kind': kind, 'qualification': 'qualified', 'gap_codes': gaps}
            elements.append(row)
        root_node = nodes[root_index]
        root_owner = nearest.get(root_index)
        # RM014D explicitly supplies Type for analog and tag-based messages.
        # Do not infer that a digital alarm's single message requires Type.
        typed_message = (root_node.name in {'AlarmConditions', 'AlarmCondition', 'AlarmDefinitions',
            'DataTypeAlarmDefinition', 'MemberAlarmDefinition'}
            or rows.get(root_index, row)['kind'] == 'alarm_data' and root_owner is not None
                and root_owner.attributes.get('DataType') == 'ALARM_ANALOG')
        identity = ('Name' if node.name in _NAMED else 'Type' if node.name == 'Message' and typed_message
                    else 'Lang' if node.name == 'Text' else None)
        if identity is not None and not node.expanded_attributes.get(identity, '').strip():
            gaps.append('missing_identity')
        if node.name in _LEAVES and node.children:
            gaps.append('unexpected_children')
        if node.name not in {'Text', 'AlarmClass', 'HMIGroup', 'HMICommand', 'HMICmd'} and node.text.strip():
            gaps.append('unexpected_direct_text')
        # Repeated identities remain separate; no representation wins. Unknown
        # sibling structures are preserved without inventing identity rules.
        if node.name in _ELEMENT_NAMES or alarm_data:
            discriminator = ('Name', node.expanded_attributes.get('Name')) if node.name in _NAMED else (
                ('Type', node.expanded_attributes.get('Type')) if node.name == 'Message' else
                ('Lang', node.expanded_attributes.get('Lang')) if node.name == 'Text' else
                ('Format', node.expanded_attributes.get('Format')) if alarm_data else None)
            duplicate_groups[(node.parent, node.expanded_name, discriminator)].append(index)
        rows[index] = row
        selected[index] = root_index
        retain(row)

    repeated = [indices for indices in duplicate_groups.values() if len(indices) > 1]
    for indices in repeated:
        for index in indices:
            rows[index]['gap_codes'].append('duplicate_sibling')
    # Source order puts parents before children. Duplicate/unknown parent gaps
    # therefore quarantine every descendant, even a familiar child spelling.
    for index, row in rows.items():
        parent = rows.get(nodes[index].parent)
        if parent is not None and parent['gap_codes']:
            row['gap_codes'].append('ancestor_gap')
        row['gap_codes'] = sorted(set(row['gap_codes']))
        row['qualification'] = 'source_gap' if row['gap_codes'] else 'qualified'

    c = {key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()}
    c.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
    c.update(source_xml_elements=len(nodes), source_entities=len(inventory.entities),
        source_data_contents=len(tag_data.contents), declarations_total=len(declarations),
        containers_total=len(containers), elements_total=len(elements),
        duplicate_groups=len(repeated), duplicate_records=sum(map(len, repeated)))
    for group, records in (('declarations', declarations), ('containers', containers), ('elements', elements)):
        for row in records:
            c[f'{group}_by_kind'][row['kind']] += 1
            c[f'{group}_by_qualification'][row['qualification']] += 1
            c['records_with_gaps'] += int(bool(row['gap_codes']))
            c['gap_links_total'] += len(row['gap_codes'])
            for code in row['gap_codes']:
                c['gaps_by_code'][code] += 1
            if group == 'declarations':
                c['declarations_by_type'][row['declared_type']] += 1
                for field, count in (('content_ids', 'content_links_total'), ('container_ids', 'container_links_total')):
                    c[count] += len(row[field])
                c['declarations_with_data'] += int(bool(row['content_ids']))
                c['declarations_with_containers'] += int(bool(row['container_ids']))
            else:
                c['direct_text_bytes'] += len(row['direct_text'].encode('utf-8'))
                c['attribute_pairs'] += len(row['attributes'])
    # Account new flags and qualified labels added after the first retention
    # pass before returning. The final pretty-JSON cap also includes wrappers.
    if retained_bytes + c['gap_links_total'] * 40 + retained_records * 16 > MAX_ALARM_EVIDENCE_BYTES:
        _invalid()
    return AlarmEvidenceResult(dict(inventory.snapshot), 'partial' if c['records_with_gaps'] else 'complete',
                               declarations, containers, elements, c)


def analyze_alarm_evidence(snapshot: SourceSnapshot, inventory: InventoryResult,
                           tag_data: TagDataResult) -> AlarmEvidenceResult:
    """Authenticate source and stored-data links before capturing alarm XML."""
    try:
        validate_tag_data(snapshot, inventory, tag_data)
        result = _capture(snapshot, inventory, tag_data)
        render_alarm_evidence_json(result)
        return result
    except AlarmEvidenceError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_alarm_evidence(snapshot: SourceSnapshot, inventory: InventoryResult,
                            tag_data: TagDataResult, result: AlarmEvidenceResult) -> None:
    """Replay captured evidence; reject caller edits before publishing counts."""
    try:
        valid = type(result) is AlarmEvidenceResult and _strict_match(
            analyze_alarm_evidence(snapshot, inventory, tag_data), result)
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        valid = False
    if not valid:
        _invalid()


def render_alarm_evidence_json(result: AlarmEvidenceResult) -> str:
    """Bounded private rendering; source authentication is a separate boundary."""
    if type(result) is not AlarmEvidenceResult or vars(result).keys() != set(AlarmEvidenceResult.__dataclass_fields__):
        _invalid()
    try:
        exhausted = object()
        stack = [iter((vars(result),))]
        budget = MAX_ALARM_EVIDENCE_JSON_BYTES
        while stack:
            item = next(stack[-1], exhausted)
            if item is exhausted:
                stack.pop()
                continue
            budget -= 1
            if len(stack) > 12 or budget < 0:
                _invalid()
            if type(item) is dict:
                if any(type(key) is not str for key in item):
                    _invalid()
                budget -= sum(len(key.encode('utf-8')) for key in item)
                stack.append(iter(item.values()))
            elif type(item) is list:
                if len(item) > max(MAX_ALARM_EVIDENCE_RECORDS, MAX_ALARM_EVIDENCE_LINKS):
                    _invalid()
                stack.append(iter(item))
            elif type(item) is str:
                budget -= len(item.encode('utf-8'))
            elif type(item) not in {int, type(None)}:
                _invalid()
            if budget < 0:
                _invalid()
        output = StringIO()
        size = 1
        for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, indent=2).iterencode(vars(result)):
            size += len(chunk.encode('utf-8'))
            if size > MAX_ALARM_EVIDENCE_JSON_BYTES:
                _invalid()
            output.write(chunk)
        output.write('\n')
        return output.getvalue()
    except AlarmEvidenceError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
