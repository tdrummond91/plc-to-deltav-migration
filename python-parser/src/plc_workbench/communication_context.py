"""Source-authenticated MSG configuration and authored tag connection context.

MessageParameters remain separate source records, including duplicates and
unsupported representations. Local endpoint roots are declaration candidates;
their members, transfer extent and runtime values are not validated. Schema 2
classifies authored message types without selecting an effective configuration.
Schema 3 identifies a small documented generic-service catalogue and bounded
numeric selector encodings, without validating a device's supported services.
RemoteElement and ConnectionPath are never resolved as local tags.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from io import StringIO
from itertools import chain
import json
from typing import Any

from .access import AccessResult, validate_access
from .calculations import CalculationResult
from .models import InventoryResult, SourceSnapshot
from .references import MAX_ADDRESS_LENGTH, ReferenceResult, _ADDRESS, _Resolver, _binding, _is_alias, _strict_record_match
from .source import _entity_id, _read_nodes
from .tag_data import TagDataResult, validate_tag_data

MAX_CONTEXT_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 250_000
OCCURRENCE_STATUSES = frozenset({
    'linked', 'missing_parameters', 'multiple_representations', 'unsupported_parameters',
    'control_binding_gap', 'control_member_unsupported', 'control_array_unsupported',
    'control_type_unconfirmed', 'unsupported_context', 'signature_gap',
})
OWNER_STATUSES = frozenset({'supported', 'type_gap', 'array_gap', 'unsupported_context'})
PARAMETER_STATUSES = OWNER_STATUSES | {'unsupported_shape'}
ENDPOINT_STATUSES = frozenset({'root_candidate', 'binding_gap', 'qualified_unsupported',
                               'invalid_expanded_suffix', 'unsupported_context'})
LOCAL_FIELDS = frozenset({'LocalElement', 'DestinationTag'})
PARAMETER_FIELDS = LOCAL_FIELDS | {'RemoteElement', 'ConnectionPath', 'MessageType'}
CONNECTION_KINDS = frozenset({'ProduceInfo', 'ConsumeInfo'})
CONNECTION_STATUSES = frozenset({'source_metadata', 'unsupported_context', 'unsupported_shape'})
CONTEXT_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'communication-context-1',
    'analysis_scope': 'authored_communication_context',
    'runtime_behavior': 'not_analyzed', 'protocol_decoding': 'not_implemented',
    'effective_configuration': 'not_selected', 'member_validation': 'not_implemented',
    'remote_binding': 'not_performed', 'engineering_review': 'unreviewed',
}
# Exact authored strings from 1756-RM014D-EN-P, printed pages 140-142.
# The SLC Typed Write spelling is independently explicit on printed page 375;
# the current table has a punctuation defect beside Write / Unconfigured.
# Never infer a family from a substring, a service code or a connection path.
MESSAGE_TYPES = {
    'Block Transfer Read': ('block_transfer', 'read'),
    'Block Transfer Write': ('block_transfer', 'write'),
    'CIP Data Table Read': ('cip_data_table', 'read'),
    'CIP Data Table Write': ('cip_data_table', 'write'),
    'CIP Generic': ('cip_generic', 'service_dependent'),
    'PLC2 Unprotected Read': ('plc2_unprotected', 'read'),
    'PLC2 Unprotected Write': ('plc2_unprotected', 'write'),
    'PLC3 Typed Read': ('plc3_typed', 'read'),
    'PLC3 Typed Write': ('plc3_typed', 'write'),
    'PLC3 Word Range Read': ('plc3_word_range', 'read'),
    'PLC3 Word Range Write': ('plc3_word_range', 'write'),
    'PLC5 Typed Read': ('plc5_typed', 'read'),
    'PLC5 Typed Write': ('plc5_typed', 'write'),
    'PLC5 Word Range Read': ('plc5_word_range', 'read'),
    'PLC5 Word Range Write': ('plc5_word_range', 'write'),
    'SERCOS IDN Read': ('sercos_idn', 'read'),
    'SERCOS IDN Write': ('sercos_idn', 'write'),
    'SLC Typed Read': ('slc_typed', 'read'),
    'SLC Typed Write': ('slc_typed', 'write'),
    'Unconfigured': ('unconfigured', 'unconfigured'),
    'Module Reconfigure': ('module_reconfigure', 'reconfigure'),
}
COMMUNICATION_METHODS = {
    '0': 'cip', '1': 'dh_plus', '2': 'cip_source_id',
    '3': 'block_transfer_remote_io', '4': 'block_transfer_controlnet',
}
CONTEXT_CONSTANTS_V2 = {**CONTEXT_CONSTANTS, 'schema_version': 2,
                        'analyzer_version': 'communication-context-2',
                        'protocol_decoding': 'authored_catalogue_only'}
CONTEXT_CONSTANTS_V3 = {**CONTEXT_CONSTANTS_V2, 'schema_version': 3,
                        'analyzer_version': 'communication-context-3',
                        'protocol_decoding': 'authored_catalogue_and_generic_selectors_only'}
# Current MessageParameters attribute ranges in RM014D, printed pages 141-142.
# Historical appendix examples have different limits; these are source selector
# ranges, not proof that a device implements any particular service or object.
GENERIC_SELECTORS = {
    'ServiceCode': ('generic_service_code_statuses', 16, 32767),
    'ObjectType': ('generic_object_type_statuses', 16, 32767),
    'TargetObject': ('generic_target_object_statuses', 10, 32767),
    'AttributeNumber': ('generic_attribute_number_statuses', 16, 65535),
}
GENERIC_SERVICES = {1: 'get_attributes_all', 14: 'get_attribute_single', 16: 'set_attribute_single'}
GENERIC_SELECTOR_GAPS = frozenset({'missing', 'empty', 'unsupported_encoding', 'out_of_range'})
GENERIC_SELECTOR_STATUSES = GENERIC_SELECTOR_GAPS | {'parsed', 'not_applicable', 'unsupported_context'}
GENERIC_SERVICE_DISPOSITIONS = frozenset(GENERIC_SERVICES.values()) | GENERIC_SELECTOR_GAPS | {'unknown_service'}
GENERIC_COMPLETENESS = frozenset({'all_selectors_parsed', 'selector_gaps', 'not_applicable', 'unsupported_context'})
MESSAGE_TYPE_STATUSES = frozenset({'catalogued', 'missing', 'empty', 'unknown', 'unsupported_context'})
MESSAGE_FAMILIES = frozenset(family for family, _ in MESSAGE_TYPES.values()) | {'unknown', 'unsupported_context'}
AUTHORED_DIRECTIONS = frozenset(direction for _, direction in MESSAGE_TYPES.values()) | {'unknown', 'unsupported_context'}
METHOD_DISPOSITIONS = frozenset(COMMUNICATION_METHODS.values()) | {'missing', 'invalid', 'unknown', 'unsupported_context'}
FIELD_SHAPES = frozenset({'missing', 'empty', 'present', 'unsupported_context'})
INTERPRETED_FIELDS = {'LocalElement': 'local_element_shapes', 'DestinationTag': 'destination_tag_shapes',
                      'RemoteElement': 'remote_element_shapes', 'ConnectionPath': 'connection_path_shapes'}
AUTHORED_ROLES = frozenset({'local_source', 'local_destination', 'authored_destination',
                          'service_dependent', 'unconfigured', 'unclassified', 'field_gap', 'unsupported_context'})
COUNT_MAPS = {
    'occurrences_by_status': OCCURRENCE_STATUSES, 'owners_by_status': OWNER_STATUSES,
    'parameters_by_status': PARAMETER_STATUSES, 'endpoints_by_status': ENDPOINT_STATUSES,
    'endpoints_by_field': LOCAL_FIELDS, 'parameter_fields': PARAMETER_FIELDS,
    'tag_connections_by_kind': CONNECTION_KINDS, 'tag_connections_by_status': CONNECTION_STATUSES,
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | {
    'source_rungs', 'source_instructions', 'source_operands', 'msg_occurrences',
    'owners_total', 'contents_total', 'parameter_records', 'endpoints_total',
    'tag_connection_records', 'owners_with_parameters', 'owners_with_multiple_contents',
    'owners_with_multiple_parameters', 'tags_with_connections',
}
COUNT_MAPS_V2 = {**COUNT_MAPS,
    'message_type_statuses': MESSAGE_TYPE_STATUSES,
    'message_families': MESSAGE_FAMILIES,
    'parameter_directions': AUTHORED_DIRECTIONS,
    'communication_methods': METHOD_DISPOSITIONS,
    'endpoint_authored_roles': AUTHORED_ROLES,
    'occurrence_directions': AUTHORED_DIRECTIONS | {'unavailable'},
    **{key: FIELD_SHAPES for key in INTERPRETED_FIELDS.values()},
}
COVERAGE_KEYS_V2 = COVERAGE_KEYS | frozenset(COUNT_MAPS_V2) | {
    'owners_referenced_by_occurrences', 'parameter_records_referenced_by_occurrences',
    'owners_with_linked_occurrences', 'linked_parameter_records',
}
COUNT_MAPS_V3 = {**COUNT_MAPS_V2,
    **{key: GENERIC_SELECTOR_STATUSES for key, _, _ in GENERIC_SELECTORS.values()},
    'generic_parameter_services': GENERIC_SERVICE_DISPOSITIONS | {'not_applicable', 'unsupported_context'},
    'generic_linked_parameter_services': GENERIC_SERVICE_DISPOSITIONS,
    'generic_linked_occurrence_services': GENERIC_SERVICE_DISPOSITIONS | {'not_applicable', 'unavailable'},
    'generic_parameter_completeness': GENERIC_COMPLETENESS,
}
COVERAGE_KEYS_V3 = COVERAGE_KEYS_V2 | frozenset(COUNT_MAPS_V3)


class CommunicationContextError(ValueError):
    """Source-free rejection of inconsistent or excessive evidence."""


def _invalid() -> None:
    raise CommunicationContextError('Communication context does not match its source evidence.') from None


def _limit() -> None:
    raise CommunicationContextError('Communication context exceeds its evidence limits.') from None


@dataclass(frozen=True)
class CommunicationContextResult:
    snapshot: dict[str, str | int]
    status: str
    occurrences: list[dict[str, Any]]
    owners: list[dict[str, Any]]
    parameters: list[dict[str, Any]]
    endpoints: list[dict[str, Any]]
    tag_connections: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'communication-context-1'
    analysis_scope: str = 'authored_communication_context'
    runtime_behavior: str = 'not_analyzed'
    protocol_decoding: str = 'not_implemented'
    effective_configuration: str = 'not_selected'
    member_validation: str = 'not_implemented'
    remote_binding: str = 'not_performed'
    engineering_review: str = 'unreviewed'

    def to_dict(self) -> dict[str, Any]:
        render_communication_context_json(self)
        return deepcopy(vars(self))


def _namespace(name: str) -> str | None:
    return name.rsplit('}', 1)[0] if '}' in name else None


def _interpret_parameter(row: dict[str, Any]) -> dict[str, Any]:
    """Interpret one authored record, irrespective of other representations."""
    attributes = row['attributes']
    supported = row['status'] == 'supported'
    raw_type = attributes.get('MessageType')
    type_status = ('unsupported_context' if not supported else 'missing' if raw_type is None else
                   'empty' if not raw_type.strip() else 'catalogued' if raw_type in MESSAGE_TYPES else 'unknown')
    family, direction = (MESSAGE_TYPES[raw_type] if type_status == 'catalogued' else
                         ('unsupported_context', 'unsupported_context') if not supported else ('unknown', 'unknown'))
    raw_method = attributes.get('CommTypeCode')
    # Canonical unsigned decimal only. Arbitrarily large digit strings stay
    # private and need no int conversion to be classified as unknown codes.
    method = ('unsupported_context' if not supported else 'missing' if raw_method is None else
              COMMUNICATION_METHODS[raw_method] if raw_method in COMMUNICATION_METHODS else
              'unknown' if raw_method and raw_method.isascii() and raw_method.isdecimal()
              and (raw_method == '0' or not raw_method.startswith('0')) else 'invalid')
    shapes = {field: ('unsupported_context' if not supported else 'missing' if field not in attributes else
                      'empty' if not attributes[field].strip() else 'present') for field in INTERPRETED_FIELDS}
    return {'message_type_status': type_status, 'family': family, 'direction': direction,
            'communication_method': method, 'field_shapes': shapes}


def _authored_role(interpretation: dict[str, Any], field: str) -> str:
    """An authored field role is separate from binding and runtime access."""
    shape = interpretation['field_shapes'][field]
    direction = interpretation['direction']
    if shape == 'unsupported_context':
        return 'unsupported_context'
    if shape != 'present':
        return 'field_gap'
    if direction == 'unconfigured':
        return 'unconfigured'
    if field == 'DestinationTag':
        return 'authored_destination'
    return {'read': 'local_destination', 'write': 'local_source',
            'service_dependent': 'service_dependent'}.get(direction, 'unclassified')


def _generic_selector(raw: str | None, radix: int, maximum: int) -> tuple[str, int | None]:
    """Parse only explicit ASCII hex or canonical ASCII decimal, bounded first."""
    if raw is None:
        return 'missing', None
    if not raw.strip():
        return 'empty', None
    if radix == 16:
        if not raw.startswith('16#') or len(raw) == 3 or any(ch not in '0123456789abcdefABCDEF' for ch in raw[3:]):
            return 'unsupported_encoding', None
        digits = raw[3:].lstrip('0') or '0'
        if len(digits) > 4:
            return 'out_of_range', None
    else:
        if (not raw.isascii() or not raw.isdecimal() or (raw != '0' and raw.startswith('0'))):
            return 'unsupported_encoding', None
        digits = raw
        if len(digits) > 5:
            return 'out_of_range', None
    value = int(digits, radix)
    return ('parsed', value) if value <= maximum else ('out_of_range', None)


def _interpret_generic(row: dict[str, Any]) -> dict[str, Any]:
    """Describe one configured record; selector completeness is not validity."""
    scope = ('unsupported_context' if row['status'] != 'supported' else
             'not_applicable' if row['interpretation']['family'] != 'cip_generic' else None)
    selectors = {field: (scope, None) if scope else _generic_selector(row['attributes'].get(field), radix, maximum)
                 for field, (_, radix, maximum) in GENERIC_SELECTORS.items()}
    code_status, code = selectors['ServiceCode']
    service = (GENERIC_SERVICES.get(code, 'unknown_service') if code_status == 'parsed' else code_status)
    completeness = scope or ('all_selectors_parsed' if all(status == 'parsed' for status, _ in selectors.values())
                             else 'selector_gaps')
    return {'service': service, 'selector_statuses': {key: status for key, (status, _) in selectors.items()},
            'selector_values': {key: value for key, (_, value) in selectors.items()}, 'completeness': completeness}


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
            access: AccessResult, tag_data: TagDataResult, *, schema_version: int = 1) -> CommunicationContextResult:
    """Derive only after all source companions have been authenticated."""
    if max(len(inventory.entities), len(inventory.rungs), len(access.instructions),
           len(access.operands), len(tag_data.contents), len(tag_data.elements)) > MAX_RECORDS:
        _limit()
    nodes = _read_nodes(snapshot.data)
    root_namespace = _namespace(nodes[0].expanded_name)
    by_locator = {node.locator: index for index, node in enumerate(nodes)}
    supported: list[bool] = []
    for node in nodes:
        supported.append(_namespace(node.expanded_name) == root_namespace
                         and all('}' not in key for key in node.expanded_attributes)
                         and (node.parent is None or supported[node.parent]))
    entities = {entity.id: entity for entity in inventory.entities}
    entity_context = {entity.id: supported[by_locator[entity.locator]] for entity in inventory.entities}
    controllers: dict[str, str | None] = {}
    for entity in inventory.entities:
        controllers[entity.id] = entity.id if entity.kind == 'controller' else controllers.get(entity.parent_id)
    shadowed_message_types = {controllers[entity.id] for entity in inventory.entities
                             if entity.kind in {'data_type', 'aoi'} and entity.name
                             and entity.name.isascii() and entity.name.upper() == 'MESSAGE'}
    source_elements = {_entity_id(snapshot.id, 'tag_data_element', node.locator): index
                       for index, node in enumerate(nodes) if node.name == 'MessageParameters'}
    contents = {row['id']: row for row in tag_data.contents}
    selected_parameters = [row for row in tag_data.elements if row['xml_name'] == 'MessageParameters']
    selected_contents = {row['id'] for row in tag_data.contents
                         if row['xml_name'] == 'Data' and row['attributes'].get('Format') == 'Message'}
    selected_contents.update(row['content_id'] for row in selected_parameters)
    owner_contents: dict[str, list[str]] = defaultdict(list)
    data_owner_ids = {row['source_id'] for row in tag_data.owners}
    for content in tag_data.contents:
        if content['id'] in selected_contents:
            owner_contents[content['owner_id']].append(content['id'])
    parameters_by_owner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected_parameters:
        parameters_by_owner[row['owner_id']].append(row)
    access_instructions = {row['id']: row for row in access.instructions}
    access_operands = {row['id']: row for row in access.operands}
    messages = [(rung, instruction) for rung in inventory.rungs if rung.parse_status == 'parsed'
                for instruction in rung.instructions
                if instruction.opcode.isascii() and instruction.opcode.upper() == 'MSG']
    bound_controls = {access_operands[operand_id]['target_id']
                      for _, instruction in messages
                      for operand_id in access_instructions[instruction.id]['operand_ids']}
    count_maps = COUNT_MAPS_V3 if schema_version == 3 else COUNT_MAPS_V2 if schema_version == 2 else COUNT_MAPS
    coverage_keys = COVERAGE_KEYS_V3 if schema_version == 3 else COVERAGE_KEYS_V2 if schema_version == 2 else COVERAGE_KEYS
    c = {key: dict.fromkeys(sorted(values), 0) for key, values in count_maps.items()}
    c.update(dict.fromkeys(sorted(coverage_keys - count_maps.keys()), 0))
    c.update(source_rungs=len(inventory.rungs), source_instructions=len(access.instructions),
             source_operands=len(access.operands), msg_occurrences=len(messages),
             contents_total=len(selected_contents))
    owners: list[dict[str, Any]] = []
    parameters: list[dict[str, Any]] = []
    endpoints: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []
    occurrences: list[dict[str, Any]] = []
    retained = records = 0

    def charge(row: Any) -> None:
        nonlocal retained, records
        records += 1
        retained += len(json.dumps(row, ensure_ascii=True, separators=(',', ':'))) + 1
        if records > MAX_RECORDS or retained > MAX_CONTEXT_BYTES:
            _limit()

    def owner_status(entity: Any) -> str:
        if not entity_context[entity.id]:
            return 'unsupported_context'
        if (entity.kind not in {'tag', 'aoi_local_tag'} or _is_alias(entity)
                or entity.attributes.get('TagType', 'Base') != 'Base'
                or entity.attributes.get('DataType') != 'MESSAGE'
                or controllers[entity.id] in shadowed_message_types):
            return 'type_gap'
        if entity.attributes.get('Dimensions', '') not in {'', '0'}:
            return 'array_gap'
        return 'supported'

    for entity in inventory.entities:
        if entity.id in data_owner_ids and (entity.attributes.get('DataType') == 'MESSAGE'
                                           or entity.id in owner_contents or entity.id in bound_controls):
            row = {'source_id': entity.id, 'scope_id': entity.scope_id, 'status': owner_status(entity),
                   'content_ids': list(owner_contents[entity.id]),
                   'parameter_ids': [p['id'] for p in parameters_by_owner[entity.id]]}
            charge(row)
            owners.append(row)
            c['owners_by_status'][row['status']] += 1
            c['owners_with_parameters'] += int(bool(row['parameter_ids']))
            c['owners_with_multiple_contents'] += int(len(row['content_ids']) > 1)
            c['owners_with_multiple_parameters'] += int(len(row['parameter_ids']) > 1)
        if entity.kind != 'tag':
            continue
        for child_index in nodes[by_locator[entity.locator]].children:
            node = nodes[child_index]
            if node.name not in CONNECTION_KINDS:
                continue
            status = ('unsupported_context' if not supported[child_index] else
                      'unsupported_shape' if node.children or node.text.strip() else 'source_metadata')
            row = {'id': _entity_id(snapshot.id, 'communication_tag_connection', node.locator),
                   'owner_id': entity.id, 'kind': node.name, 'locator': node.locator,
                   'xml_namespace': _namespace(node.expanded_name),
                   'attributes': dict(node.expanded_attributes), 'direct_text': node.text,
                   'child_elements': len(node.children), 'status': status}
            charge(row)
            connections.append(row)
            c['tag_connections_by_kind'][node.name] += 1
            c['tag_connections_by_status'][status] += 1
    owner_index = {row['source_id']: row for row in owners}
    resolver = _Resolver(inventory)
    for element in selected_parameters:
        entity = entities[element['owner_id']]
        content = contents[element['content_id']]
        content_node = nodes[by_locator[content['locator']]]
        node_index = source_elements[element['id']]
        node = nodes[node_index]
        status = ('unsupported_context' if not supported[node_index] else
                  'unsupported_shape' if (element['parent_id'] != content['id']
                                          or content['xml_name'] != 'Data'
                                          or content['attributes'].get('Format') != 'Message'
                                          or content_node.text.strip()
                                          or any(nodes[index].name != 'MessageParameters'
                                                 for index in content_node.children)
                                          or node.children or node.text.strip()) else
                  owner_index[entity.id]['status'])
        row = {'source_id': element['id'], 'owner_id': entity.id, 'content_id': content['id'],
               'parent_id': element['parent_id'], 'locator': node.locator,
               'xml_namespace': element['xml_namespace'], 'attributes': dict(element['attributes']),
               'direct_text': element['direct_text'], 'status': status}
        if schema_version >= 2:
            interpretation = _interpret_parameter(row)
            row['interpretation'] = interpretation
            for key, value in (('message_type_statuses', 'message_type_status'), ('message_families', 'family'),
                               ('parameter_directions', 'direction'), ('communication_methods', 'communication_method')):
                c[key][interpretation[value]] += 1
            for field, key in INTERPRETED_FIELDS.items():
                c[key][interpretation['field_shapes'][field]] += 1
            if schema_version == 3:
                generic = _interpret_generic(row)
                interpretation['generic'] = generic
                c['generic_parameter_services'][generic['service']] += 1
                c['generic_parameter_completeness'][generic['completeness']] += 1
                for field, (key, _, _) in GENERIC_SELECTORS.items():
                    c[key][generic['selector_statuses'][field]] += 1
        charge(row)
        parameters.append(row)
        c['parameters_by_status'][status] += 1
        for field in sorted(PARAMETER_FIELDS):
            if field in row['attributes']:
                c['parameter_fields'][field] += 1
        for field in sorted(LOCAL_FIELDS):
            if field not in row['attributes']:
                continue
            raw = row['attributes'][field]
            binding = resolver.resolve(raw, entity.scope_id) if status == 'supported' else _binding('unresolved', reason='invalid_scope')
            if status != 'supported':
                endpoint_status = 'unsupported_context'
            elif binding['reason'] in {'program_qualified_address', 'backslash_qualified_address'}:
                endpoint_status = 'qualified_unsupported'
            elif binding['status'] != 'root_bound':
                endpoint_status = 'binding_gap'
            elif not all(entity_context.get(identifier, False) for identifier in
                         [binding['symbol_id'], binding['target_id'], *binding['alias_chain']]):
                endpoint_status = 'unsupported_context'
            elif len(binding['suffix']) > MAX_ADDRESS_LENGTH or _ADDRESS.fullmatch('A' + binding['suffix']) is None:
                endpoint_status = 'invalid_expanded_suffix'
            else:
                endpoint_status = 'root_candidate'
            endpoint = {'parameter_id': element['id'], 'owner_id': entity.id, 'field': field,
                        'raw_text': raw, 'scope_id': entity.scope_id, 'status': endpoint_status,
                        'binding': binding}
            if schema_version >= 2:
                endpoint['authored_role'] = _authored_role(interpretation, field)
                c['endpoint_authored_roles'][endpoint['authored_role']] += 1
            charge(endpoint)
            endpoints.append(endpoint)
            c['endpoints_by_status'][endpoint_status] += 1
            c['endpoints_by_field'][field] += 1
    parameter_index = {row['source_id']: row for row in parameters}
    for rung, instruction in messages:
        access_instruction = access_instructions[instruction.id]
        operand_ids = access_instruction['operand_ids']
        operand = access_operands[operand_ids[0]] if len(operand_ids) == 1 else None
        owner_id = None
        parameter_ids: list[str] = []
        if access_instruction['status'] != 'classified' or operand is None:
            status = 'signature_gap'
        elif (not supported[by_locator[rung.locator]]
              or any(not supported[index] for index in nodes[by_locator[rung.locator]].children
                     if nodes[index].name == 'Text')):
            status = 'unsupported_context'
        elif operand['binding_status'] != 'root_bound':
            status = 'control_binding_gap'
        elif not all(entity_context.get(identifier, False) for identifier in
                     [operand['symbol_id'], operand['target_id'], *operand['alias_chain']]):
            status = 'unsupported_context'
        elif operand['suffix']:
            status = 'control_array_unsupported' if '[' in operand['suffix'] else 'control_member_unsupported'
        else:
            owner = owner_index[operand['target_id']]
            owner_id = owner['source_id']
            if owner['status'] == 'array_gap':
                status = 'control_array_unsupported'
            elif owner['status'] == 'type_gap':
                status = 'control_type_unconfirmed'
            elif owner['status'] != 'supported':
                status = 'unsupported_context'
            else:
                parameter_ids = list(owner['parameter_ids'])
                if len(owner['content_ids']) > 1 or len(parameter_ids) > 1:
                    status = 'multiple_representations'
                elif not parameter_ids:
                    status = 'missing_parameters'
                elif parameter_index[parameter_ids[0]]['status'] != 'supported':
                    status = 'unsupported_parameters'
                else:
                    status = 'linked'
        occurrence = {'instruction_id': instruction.id, 'rung_id': rung.id, 'scope_id': rung.scope_id,
                      'control_operand_id': operand['id'] if operand is not None else None,
                      'owner_id': owner_id, 'parameter_ids': parameter_ids, 'status': status}
        if schema_version >= 2:
            occurrence['authored_direction'] = (parameter_index[parameter_ids[0]]['interpretation']['direction']
                                               if status == 'linked' else 'unavailable')
            c['occurrence_directions'][occurrence['authored_direction']] += 1
            if schema_version == 3:
                occurrence['generic_service'] = (parameter_index[parameter_ids[0]]['interpretation']['generic']['service']
                                                  if status == 'linked' else 'unavailable')
                c['generic_linked_occurrence_services'][occurrence['generic_service']] += 1
        charge(occurrence)
        occurrences.append(occurrence)
        c['occurrences_by_status'][status] += 1
    c.update(owners_total=len(owners), parameter_records=len(parameters), endpoints_total=len(endpoints),
             tag_connection_records=len(connections), tags_with_connections=len({r['owner_id'] for r in connections}))
    if schema_version >= 2:
        c.update(owners_referenced_by_occurrences=len({r['owner_id'] for r in occurrences if r['owner_id'] is not None}),
                 parameter_records_referenced_by_occurrences=len({p for r in occurrences for p in r['parameter_ids']}),
                 owners_with_linked_occurrences=len({r['owner_id'] for r in occurrences if r['status'] == 'linked'}),
                 linked_parameter_records=len({p for r in occurrences if r['status'] == 'linked' for p in r['parameter_ids']}))
        if schema_version == 3:
            for identifier in {p for r in occurrences if r['status'] == 'linked' for p in r['parameter_ids']}:
                service = parameter_index[identifier]['interpretation']['generic']['service']
                if service != 'not_applicable':
                    c['generic_linked_parameter_services'][service] += 1
    partial = (any(row['status'] != 'linked' for row in occurrences)
               or any(row['status'] != 'supported' for row in owners + parameters)
               or any(row['status'] != 'root_candidate' for row in endpoints)
               or any(row['status'] != 'source_metadata' for row in connections)
               or c['owners_with_multiple_contents'] or c['owners_with_multiple_parameters'])
    return CommunicationContextResult(dict(inventory.snapshot), 'partial' if partial else 'complete',
                                      occurrences, owners, parameters, endpoints, connections, c,
                                      **(CONTEXT_CONSTANTS_V3 if schema_version == 3 else
                                         CONTEXT_CONSTANTS_V2 if schema_version == 2 else CONTEXT_CONSTANTS))


def analyze_communication_context(snapshot: SourceSnapshot, inventory: InventoryResult,
                                  references: ReferenceResult, access: AccessResult,
                                  tag_data: TagDataResult, *,
                                  calculations: CalculationResult | None = None,
                                  schema_version: int = 1) -> CommunicationContextResult:
    """Authenticate providers, then derive bounded source-only communication links."""
    try:
        if type(schema_version) is not int or schema_version not in {1, 2, 3}:
            _invalid()
        validate_tag_data(snapshot, inventory, tag_data)
        if type(access) is not AccessResult or type(access.schema_version) is not int or access.schema_version not in {3, 4}:
            _invalid()
        validate_access(inventory, references, access,
                        snapshot=snapshot if access.schema_version == 4 else None,
                        calculations=calculations)
        result = _derive(snapshot, inventory, references, access, tag_data, schema_version=schema_version)
        render_communication_context_json(result)
        return result
    except CommunicationContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_communication_context(snapshot: SourceSnapshot, inventory: InventoryResult,
                                   references: ReferenceResult, access: AccessResult,
                                   tag_data: TagDataResult, result: CommunicationContextResult, *,
                                   calculations: CalculationResult | None = None) -> None:
    try:
        render_communication_context_json(result)
        expected = analyze_communication_context(snapshot, inventory, references, access, tag_data,
                                                  calculations=calculations, schema_version=result.schema_version)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except CommunicationContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_communication_context_json(result: CommunicationContextResult) -> str:
    """Bound native values before encoding; replay authentication remains separate."""
    try:
        if type(result) is not CommunicationContextResult or vars(result).keys() != set(CommunicationContextResult.__dataclass_fields__):
            _invalid()
        remaining = MAX_CONTEXT_BYTES
        stack: list[tuple[Any, int | None]] = [(iter((vars(result),)), None)]
        active: set[int] = set()
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
                if type(value) is dict and any(type(key) is not str for key in value):
                    _invalid()
                active.add(id(value))
                stack.append((iter(chain(value.keys(), value.values()) if type(value) is dict else value), id(value)))
            elif type(value) not in {int, type(None)}:
                _invalid()
            if remaining < 0:
                _limit()
        output, size = StringIO(), 0
        for chunk in json.JSONEncoder(ensure_ascii=True, sort_keys=True, indent=2).iterencode(vars(result)):
            size += len(chunk)
            if size + 1 > MAX_CONTEXT_BYTES:
                _limit()
            output.write(chunk)
        return output.getvalue() + '\n'
    except CommunicationContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
