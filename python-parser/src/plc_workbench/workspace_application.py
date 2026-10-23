"""Read-only application declarations, configured routes and raw register evidence.

This projection deliberately separates declaration kind, controller data direction,
datatype, logic access and documented channel profiles. A floating point value is
not physical analogue I/O, and configured module routes are not verified cabling.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import re
from typing import Any
from types import SimpleNamespace

from .source import _read_nodes
from .stateful_objects import _declaration
from .workspace_field_io import FieldIOIndex
from .workspace_io_comments import collect_io_annotations, select_description
from .workspace_paging import page_size
from .workspace_variables import _member_key

MAX_REGISTERS = 100_000
MAX_INDEX_BYTES = 96 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_DETAIL = 500
MAX_TEXT = 4096
_IMPORT_REFERENCE = 'https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm014_-en-p.pdf'
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*', re.ASCII)
_INDEX = re.compile(r'\[\s*[0-9]+(?:\s*,\s*[0-9]+)*\s*\]', re.ASCII)
_DIRECTION = {'module_input_tag': 'input', 'module_output_tag': 'output',
              'module_config_tag': 'configuration'}
_ROOTS = frozenset({'tag', 'aoi_parameter', 'aoi_local_tag', *_DIRECTION})
_LIMITATIONS = (
    'Hardware routes describe configured module parent relationships and ports, not verified physical cabling or installed equipment.',
    'Registers are captured declarations and statically addressed members. Array dimensions do not create uncaptured elements; indirect indexes and opaque payloads remain unresolved.',
    'Datatype, declaration kind, controller data direction, external access and explicit logic access are separate facts. REAL or SINT data does not establish a field channel.',
    'Captured export values are not live readings or guaranteed initialization values. Repeated Data, DefaultData and L5K representations are retained without selecting an effective value.',
    'Read/write sites are explicit static uses, not runtime order or reaching assignments. Copy ranges, AOI side effects and dynamic addresses are not expanded into invented member uses.',
    'Documented channel profiles require exact qualified identity and member evidence; configuration, electrical modes and field wiring still require confirmation.',
)


class ApplicationError(ValueError):
    """A bounded, source-free projection or selection failure."""


def _invalid() -> None:
    raise ApplicationError('Saved application evidence is inconsistent or exceeds its limits.') from None


def _page(rows: list, page: int, size: int) -> dict:
    pages = max(1, (len(rows) + size - 1) // size)
    selected = min(page, pages)
    return {'items': rows[(selected - 1) * size:selected * size], 'page': selected,
            'pages': pages, 'page_size': size, 'total': len(rows)}


def _text(value: Any, limit: int = MAX_TEXT) -> Any:
    return value[:limit] if isinstance(value, str) else value


def _bounded(row: Any, limit: int = MAX_TEXT) -> Any:
    """Shorten presentation text only; canonical IDs and addresses stay intact."""
    if isinstance(row, dict):
        result = {}
        for key, value in row.items():
            if isinstance(value, str) and len(value) > limit and key not in {
                    'id', 'address', 'suffix', 'parent_suffix', 'alias_for', 'alias_target'} and not key.endswith('_id'):
                result[key], result[key + '_truncated'] = value[:limit], True
            else:
                result[key] = _bounded(value, limit)
        return result
    if isinstance(row, list):
        return [_bounded(item, limit) for item in row]
    return row


def validate_query(query: dict) -> dict:
    if type(query) is not dict:
        raise ApplicationError('Choose a captured run and available application filters.')
    result = {}
    for key in ('run_id', 'module_id', 'register_id', 'query', 'datatype'):
        value = query.get(key, '')
        if (type(value) is not str or len(value) > 256 or key == 'run_id' and not value
                or any(ord(char) < 32 or ord(char) == 127 for char in value)):
            raise ApplicationError('Choose a captured run and bounded application filters.')
        result[key] = value
    for key, choices in (
            ('direction', {'', 'input', 'output', 'configuration', 'internal'}),
            ('declaration_kind', {'', 'base', 'alias', 'produced', 'consumed', 'module_input',
                                  'module_output', 'module_configuration', 'aoi_parameter', 'aoi_local', 'unknown'}),
            ('member_kind', {'', 'declaration', 'container', 'scalar', 'bit'}),
            ('logic_role', {'', 'read', 'write', 'read_write', 'unknown', 'unused'})):
        value = query.get(key, '')
        if type(value) is not str or value not in choices:
            raise ApplicationError('Choose an available application filter.')
        result[key] = value
    for key in ('page', 'module_page', 'use_page'):
        value = query.get(key, 1)
        if type(value) not in {str, int} or not re.fullmatch(r'[1-9][0-9]{0,5}', str(value)):
            raise ApplicationError('Choose a positive bounded application page.')
        result[key] = int(value)
    try:
        result['page_size'] = page_size(query, 50, error=ApplicationError)
    except ValueError:
        raise ApplicationError('Choose one of the available application page sizes.') from None
    return result


def unavailable(size: int = 50) -> dict:
    return {'available': False, 'snapshot_id': None,
            'notice': 'Saved application evidence is missing or could not be verified. Original source remains available.',
            'modules': _page([], 1, size), 'registers': _page([], 1, size),
            'selected_module': None, 'selected_register': None,
            'coverage': {}, 'limitations': list(_LIMITATIONS)}


class ApplicationIndex:
    """Projection backed only by the workspace's authenticated immutable evidence."""

    def __init__(self, field_io: FieldIOIndex) -> None:
        if type(field_io) is not FieldIOIndex:
            _invalid()
        self.io, self.base = field_io, field_io.base
        self.modules: dict[str, dict] = {}
        self.registers: dict[str, dict] = {}
        self._keys: dict[tuple[str, str], str] = {}
        self._by_owner: dict[str, list[str]] = defaultdict(list)
        self._values: dict[str, list] = defaultdict(list)
        self._uses: dict[str, list] = defaultdict(list)
        self._aliases: dict[str, list] = defaultdict(list)
        self._annotations: dict[str, list] = defaultdict(list)
        self._children: dict[str, list] = defaultdict(list)
        self._communications: dict[str, list] = defaultdict(list)
        self._definitions: dict[tuple, list] = defaultdict(list)
        self._controllers: dict[str, str | None] = {}
        self._declared_members: dict[tuple, dict] = {}
        self.annotation_texts: dict[str, str] = dict(field_io.annotation_texts)
        self._unresolved: list[dict] = []
        self._search: dict[str, str] = {}
        self._budget = 0
        self._gaps: Counter = Counter()
        try:
            self._build()
        except ApplicationError:
            raise
        except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
            _invalid()

    def _retain(self, value: Any) -> None:
        self._budget += len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self._budget > MAX_INDEX_BYTES:
            _invalid()

    def _kind(self, entity: Any) -> str:
        if entity.kind in _DIRECTION:
            return 'module_' + _DIRECTION[entity.kind]
        if entity.kind == 'aoi_parameter':
            return 'aoi_parameter'
        if entity.kind == 'aoi_local_tag':
            return 'aoi_local'
        return {'Alias': 'alias', 'Produced': 'produced', 'Consumed': 'consumed', 'Base': 'base', None: 'base'}.get(
            entity.attributes.get('TagType'), 'unknown')

    def _add(self, owner_id: str, suffix: str, member_kind: str = 'scalar') -> dict:
        key = owner_id, _member_key(suffix)
        if key in self._keys:
            row = self.registers[self._keys[key]]
            if member_kind == 'container' and suffix:
                row['member_kind'] = 'container'
            return row
        if len(self.registers) >= MAX_REGISTERS or len(suffix) > 4096:
            _invalid()
        owner = self.base._entities[owner_id]
        name = self.base._resolver.name(owner) or owner.name
        scope = self.base._entities.get(owner.scope_id)
        identifier = 'application_register_' + hashlib.sha256((owner_id + '\0' + key[1]).encode()).hexdigest()
        module_id = self.io._root_module.get(owner_id)
        row = {'id': identifier, 'source_id': owner_id, 'root_id': owner_id, 'module_id': module_id,
               'name': name, 'address': (name or '(unnamed declaration)') + suffix, 'suffix': suffix,
               'parent_register_id': None, 'path': self.base._path(owner_id),
               'scope': {'id': owner.scope_id, 'name': scope.name if scope else None,
                         'path': self.base._path(owner.scope_id)},
               'declaration_kind': self._kind(owner), 'io_direction': _DIRECTION.get(owner.kind, 'internal'),
               'member_kind': member_kind if suffix else 'declaration',
               'datatype': owner.attributes.get('DataType') if not suffix else None,
               'radix': owner.attributes.get('Radix') if not suffix else None,
               'external_access': owner.attributes.get('ExternalAccess'),
               'alias_target': owner.attributes.get('AliasFor') if not suffix else None,
               'description': owner.description if not suffix else None,
               'dimensions': owner.attributes.get('Dimensions') if not suffix else None,
               'logic_access': {'roles': [], 'uses_total': 0}, 'aliases_total': 0,
               'logical_meaning': {'status': 'unknown', 'basis': 'not_decoded'},
               'transport': {'status': 'unknown', 'basis': 'configured_relationship_only' if module_id else 'not_established'},
               'physical': {'field_type': None, 'channel': None, 'status': 'unknown', 'reference': None},
               'states': {'declaration': 'extracted',
                          'source_qualification': 'resolved' if self.base._entity_ok.get(owner_id) else 'unknown',
                          'datatype': 'extracted' if not suffix and owner.attributes.get('DataType') else 'unknown',
                          'radix': 'extracted' if not suffix and owner.attributes.get('Radix') else 'unknown',
                          'direction': 'extracted' if module_id else 'unknown', 'physical': 'unknown'},
               'provenance': {'source_id': owner_id, 'locator': owner.locator,
                              'name_basis': self.base._resolver.names.get(owner_id, {}).get('name_origin'),
                              'datatype_source_ids': [owner_id] if not suffix and owner.attributes.get('DataType') else [],
                              'radix_source_ids': [owner_id] if not suffix and owner.attributes.get('Radix') else []}}
        self.registers[identifier] = row
        self._keys[key] = identifier
        self._by_owner[owner_id].append(identifier)
        return row

    def _hardware(self) -> None:
        entities = self.base._entities
        names: dict[tuple, list] = defaultdict(list)
        for entity in entities.values():
            self._children[entity.parent_id].append(entity)
            if entity.kind == 'module' and entity.name:
                names[entity.scope_id, entity.name.casefold()].append(entity)
        for identifier, original in self.io.modules.items():
            entity = entities[identifier]
            parent_name = entity.attributes.get('ParentModule')
            candidates = names.get((entity.scope_id, (parent_name or '').casefold()), [])
            parent = candidates[0] if len(candidates) == 1 else None
            own_ports = self.io.ports[identifier]
            root = (parent is entity and not any(
                port['upstream'] in {'true', '1'} for port in own_ports))
            parent_port = entity.attributes.get('ParentModPortId')
            matches = [port for port in self.io.ports.get(parent.id if parent else '', [])
                       if port['port_id'] == parent_port and parent_port is not None]
            status = ('source_unqualified' if not original['qualified'] else
                      'root' if root else 'parent_not_declared' if not parent_name else
                      'parent_ambiguous' if len(candidates) > 1 else
                      'parent_missing' if parent is None else
                      'parent_unqualified' if not self.base._entity_ok.get(parent.id) else
                      'parent_port_missing' if not matches else
                      'parent_port_ambiguous' if len(matches) > 1 else
                      'parent_port_unqualified' if not matches[0]['qualified'] else 'resolved')
            attachment = {'status': status, 'parent_port_id': parent_port,
                          'parent_port_source_id': matches[0]['id'] if len(matches) == 1 else None,
                          'parent_port_type': matches[0]['type'] if len(matches) == 1 else None,
                          'parent_port_address': matches[0]['address'] if len(matches) == 1 else None}
            connections = []
            for child in self._children[identifier]:
                if child.kind not in {'module_connection', 'module_rack_connection'}:
                    continue
                roots = [root for root in self.io.roots[identifier]
                         if entities[root['id']].parent_id == child.id]
                connections.append({'id': child.id, 'source_id': child.id, 'name': child.name,
                    'attributes': dict(child.attributes), 'qualified': bool(self.base._entity_ok.get(child.id)),
                    'attribute_help': {'RPI': {'meaning': 'Requested packet interval for this module connection, in microseconds.',
                                               'units': 'microseconds', 'status': 'vendor_documented', 'reference': _IMPORT_REFERENCE},
                                       'ConnectionPath': {'meaning': 'Configured communication path to the target module.',
                                                          'status': 'vendor_documented', 'reference': _IMPORT_REFERENCE},
                                       'InputTagSuffix': {'meaning': 'Configured suffix for the input tag of this module connection.',
                                                          'status': 'vendor_documented', 'reference': _IMPORT_REFERENCE},
                                       'OutputTagSuffix': {'meaning': 'Configured suffix for the output tag of this module connection.',
                                                           'status': 'vendor_documented', 'reference': _IMPORT_REFERENCE}},
                    'input_root_ids': [row['id'] for row in roots if row['direction'] == 'input'],
                    'output_root_ids': [row['id'] for row in roots if row['direction'] == 'output']})
            row = {'id': identifier, 'source_id': identifier, 'name': original['name'],
                   'description': original['description'], 'controller': original['controller'],
                   'catalog_number': original['catalog_number'], 'vendor': original['vendor'],
                   'module_role': original['module_role'], 'catalog_reference': original['catalog_reference'],
                   'catalog_description': original['catalog_description'],
                   'parent_name': parent_name, 'parent_id': parent.id if parent and not root else None,
                   'attachment': attachment, 'ports': own_ports, 'connections': connections,
                   'qualified': original['qualified'], 'attributes': dict(entity.attributes),
                   'states': {'identity': 'extracted', 'catalog': 'vendor_documented' if original['catalog_reference'] else 'unknown',
                              'attachment': 'resolved' if status == 'resolved' else 'extracted' if status == 'root' else 'unknown'},
                   'provenance': {'source_id': identifier, 'locator': entity.locator}}
            self.modules[identifier] = row
        for row in self.modules.values():
            trail, seen, current, status = [], set(), row, 'root'
            while current is not None:
                if current['id'] in seen:
                    status = 'cycle'
                    break
                if len(trail) >= 160:
                    status = 'depth_limit'
                    break
                seen.add(current['id'])
                trail.append({'id': current['id'], 'name': current['name']})
                status = current['attachment']['status']
                if status != 'resolved':
                    break
                current = self.modules.get(current['parent_id'])
            row['route'] = {'status': 'resolved_to_root' if status == 'root' else status,
                            'module_ids': [item['id'] for item in reversed(trail)],
                            'modules': list(reversed(trail))}
            self._retain(row)

    def _containers(self) -> None:
        evidence = getattr(self.base, '_data_evidence', None)
        if evidence is None:
            return
        paths: dict[str, str | None] = {row['id']: '' if row['format_kind'] == 'decorated' else None
                                       for row in evidence.contents}
        qualified = {row['id']: bool(self.base._entity_ok.get(row['owner_id']) and
                     row['xml_namespace'] == self.base._namespace and not row['direct_text'].strip()
                     and not any('}' in key for key in row['attributes'])) for row in evidence.contents}
        for element in evidence.elements:
            attrs, parent, path = element['attributes'], paths.get(element['parent_id']), None
            if parent is not None:
                if element['xml_name'] in {'Structure', 'Array', 'DataValue'}:
                    path = parent
                elif element['xml_name'] in {'StructureMember', 'ArrayMember', 'DataValueMember'} and _NAME.fullmatch(attrs.get('Name', '')):
                    path = parent + '.' + attrs['Name']
                elif element['xml_name'] == 'Element' and _INDEX.fullmatch(attrs.get('Index', '')):
                    path = parent + attrs['Index']
            paths[element['id']] = path
            okay = bool(qualified.get(element['parent_id']) and element['xml_namespace'] == self.base._namespace
                        and element['kind'] not in {'unmodeled', 'opaque'} and not element['direct_text'].strip()
                        and not any('}' in key for key in attrs))
            qualified[element['id']] = okay
            if path is None or not okay:
                self._gaps['unmodeled_or_unqualified_data_elements'] += 1
                continue
            if element['owner_id'] not in self.base._entities or self.base._entities[element['owner_id']].kind not in _ROOTS:
                continue
            container = element['kind'] in {'structure', 'structure_member', 'array', 'array_member'}
            row = self._add(element['owner_id'], path, 'container' if container else 'scalar')
            ambiguous = self._path_ambiguous(element['owner_id'], path, element['content_id'])
            if container and ambiguous:
                row['states']['member'] = 'unknown'
            if attrs.get('Dimensions'):
                row['dimensions'] = attrs['Dimensions']
            if container and attrs.get('DataType') and not ambiguous:
                candidates = self.base._types.get((element['owner_id'], _member_key(path)), set())
                if len(candidates) == 1:
                    row['datatype'] = next(iter(candidates))
                    row['states']['datatype'] = 'extracted'
                    row['provenance']['datatype_source_ids'] = [element['id']]
                elif len(candidates) > 1:
                    row['datatype'] = None
                    row['states']['datatype'] = 'unknown'
            row['provenance'].setdefault('content_ids', [])
            if element['content_id'] not in row['provenance']['content_ids']:
                row['provenance']['content_ids'].append(element['content_id'])
        self._gaps.update({f'tag_data_{code}': count for code, count in
                          Counter(row['code'] for row in evidence.issues).items()})

    def _use(self, row: dict, reference: dict, role: str, *, expression: bool = False) -> None:
        instruction = self.base._instructions[reference['instruction_id']]
        rung = self.base._rungs[reference['rung_id']]
        formula = instruction.arguments[1] if instruction.opcode.upper() == 'CPT' and len(instruction.arguments) == 2 else None
        operand = formula[reference['start']:reference['end']] if expression and formula is not None else reference.get('raw_text') or row['address']
        value = {'id': reference['id'], 'instruction_id': instruction.id, 'rung_id': rung.id,
                 'rung_number': rung.number, 'opcode': instruction.opcode, 'role': role,
                 'operand': operand,
                 'path': self.base._path(rung.parent_id), 'exact_instruction': (rung.text or '')[instruction.start:instruction.end],
                 'expression': formula,
                 'destination': instruction.arguments[0] if instruction.opcode.upper() == 'CPT' and len(instruction.arguments) == 2 else None,
                 'basis': 'parsed_expression_reference' if expression else 'explicit_instruction_operand',
                 'source_id': rung.id}
        self._uses[row['id']].append(value)
        self._retain(value)

    def _references(self) -> None:
        roles = {row['id']: row['role'] for row in self.base._access.operands} if self.base._access else {}
        expressions = {row['id'] for row in self.base._access.operands
                       if row.get('binding_status') == 'parsed_expression'} if self.base._access else set()
        for reference in self.base._references.operands:
            if reference['status'] != 'root_bound' or not self.base._qualified(reference, reference['rung_id']):
                if reference['status'] not in {'literal', 'placeholder', 'non_data'} and reference['id'] not in expressions:
                    self._gaps['unresolved_or_unqualified_reference_operands'] += 1
                    if len(self._unresolved) < MAX_DETAIL:
                        self._unresolved.append({'source_id': reference['rung_id'], 'rung_id': reference['rung_id'],
                            'instruction_id': reference['instruction_id'], 'operand': reference['raw_text'],
                            'status': reference['status'], 'reason': reference.get('reason')})
                continue
            if self.base._entities[reference['target_id']].kind not in _ROOTS:
                continue
            suffix = reference['suffix']
            row = self._add(reference['target_id'], suffix, 'bit' if re.search(r'\.[0-9]+$', suffix) else 'scalar')
            self._use(row, reference, roles.get(reference['id'], 'unknown'))
            for alias_id in reference.get('alias_chain', []):
                alias = self._add(alias_id, '')
                self._use(alias, reference, roles.get(reference['id'], 'unknown'))
        if self.base._access:
            for reference in self.base._access.expression_uses:
                if reference['binding_status'] != 'root_bound' or not self.base._qualified(reference, reference['rung_id']):
                    self._gaps['unresolved_expression_references'] += 1
                    continue
                if self.base._entities[reference['target_id']].kind not in _ROOTS:
                    continue
                row = self._add(reference['target_id'], reference['suffix'])
                self._use(row, reference, reference['role'], expression=True)
                for alias_id in reference.get('alias_chain', []):
                    self._use(self._add(alias_id, ''), reference, reference['role'], expression=True)
        for alias in self.base._references.aliases:
            declaration = self._add(alias['source_id'], '')
            declaration['alias_binding'] = {'status': alias['status'], 'target_id': alias.get('target_id'),
                                             'suffix': alias.get('suffix'), 'alias_chain': alias.get('alias_chain', [])}
            if alias['status'] != 'root_bound' or not all(self.base._entity_ok.get(value) for value in
                    [alias['source_id'], alias.get('target_id'), *alias.get('alias_chain', [])]):
                self._gaps['unresolved_alias_declarations'] += 1
                continue
            target = self._add(alias['target_id'], alias['suffix'])
            declaration['alias_binding']['register_id'] = target['id']
            declaration['module_id'] = target['module_id']
            declaration['io_direction'] = target['io_direction']
            declaration['states']['direction'] = 'resolved' if target['module_id'] else 'unknown'
            if target['module_id']:
                declaration['transport']['basis'] = 'qualified_alias_to_configured_module'
            entity = self.base._entities[alias['source_id']]
            self._aliases[target['id']].append({'id': entity.id, 'source_id': entity.id, 'name': entity.name,
                'alias_for': entity.attributes.get('AliasFor'), 'scope_id': entity.scope_id,
                'status': 'resolved', 'suffix': alias['suffix'], 'register_id': declaration['id']})

    def _descriptions(self) -> None:
        owners = {entity.id for entity in self.base._entities.values() if entity.kind in _ROOTS}
        notes = collect_io_annotations(self.base._source, self.base._captured,
                                       self.base._entity_ok, owner_ids=owners)
        for (owner_id, suffix), annotations in notes.items():
            row = self._add(owner_id, suffix)
            self._annotations[row['id']].extend(annotations)
            self.annotation_texts.update({note['id']: note['text'] for note in annotations})
        for row in list(self.registers.values()):
            if row['root_id'] not in owners:
                continue
            exact = self._annotations[row['id']]
            candidates = [dict(note, description_scope=note.get('description_scope') or ('exact_member_comment' if row['suffix'] else
                               'exact_alias_description' if row['declaration_kind'] == 'alias' else
                               'backing_description')) for note in exact]
            if row['suffix']:
                root_id = self._keys[row['root_id'], '']
                candidates.extend(dict(note, description_scope='backing_description')
                                  for note in self._annotations[root_id])
            selection = select_description(candidates)
            row['description_selection'] = selection
            preferred = selection['preferred_annotation_id']
            if preferred:
                row['description'] = next(note['text'] for note in candidates if note['id'] == preferred)
            self._annotations[row['id']] = candidates

    def _source_details(self) -> None:
        """Retain communication and datatype declarations without decoding payloads."""
        owners = {entity.locator: entity for entity in self.base._entities.values()
                  if entity.kind in {'tag', 'data_type'}}
        nodes = _read_nodes(self.base._source)
        for node in nodes:
            owner = owners.get(node.locator)
            if owner is None or not self.base._entity_ok.get(owner.id):
                continue
            if owner.kind == 'data_type':
                members = []
                for child_index in node.children:
                    container = nodes[child_index]
                    if container.name != 'Members' or container.expanded_name.rpartition('}')[0] != node.expanded_name.rpartition('}')[0]:
                        continue
                    for member_index in container.children:
                        member = nodes[member_index]
                        valid = (member.name == 'Member' and _NAME.fullmatch(member.attributes.get('Name', ''))
                                 and member.expanded_name.rpartition('}')[0] == node.expanded_name.rpartition('}')[0]
                                 and not any('}' in key for key in member.expanded_attributes)
                                 and not any('}' in key for key in container.expanded_attributes))
                        value = {'name': member.attributes.get('Name'), 'source_id': owner.id, 'locator': member.locator,
                                 'attributes': dict(member.expanded_attributes), 'status': 'extracted' if valid else 'unknown'}
                        annotations = []
                        if valid:
                            for description_index in member.children:
                                description = nodes[description_index]
                                if (description.name != 'Description' or description.expanded_name.rpartition('}')[0] != node.expanded_name.rpartition('}')[0]
                                        or any('}' in key for key in description.expanded_attributes)):
                                    continue
                                texts = ([nodes[index] for index in description.children]
                                         if description.children and not description.text.strip() else [description])
                                for text_node in texts:
                                    if (text_node.children or not text_node.text.strip()
                                            or text_node.name not in {'Description', 'LocalizedDescription'}
                                            or text_node.expanded_name.rpartition('}')[0] != node.expanded_name.rpartition('}')[0]
                                            or any('}' in key for key in text_node.expanded_attributes)):
                                        continue
                                    annotation_id = 'io_annotation_' + hashlib.sha256(
                                        f'{self.base._captured.snapshot["id"]}\0{text_node.locator}\0datatype_member_description'.encode()).hexdigest()
                                    annotation = {'id': annotation_id, 'owner_id': owner.id, 'owner_name': owner.name,
                                        'source_id': owner.id, 'locator': text_node.locator,
                                        'kind': 'datatype_member_description', 'language': text_node.attributes.get('Lang'),
                                        'text': text_node.text, 'description_scope': 'declared_member_description'}
                                    annotations.append(annotation)
                                    self.annotation_texts[annotation_id] = text_node.text
                        value['source_annotations'] = annotations
                        value['description'] = annotations[0]['text'] if annotations else None
                        members.append(value)
                        self._retain(value)
                duplicates = Counter((row['name'] or '').casefold() for row in members)
                for row in members:
                    if duplicates[(row['name'] or '').casefold()] > 1:
                        row['status'] = 'unknown'
                self._definitions[owner.scope_id, (owner.name or '').casefold()].append({
                    'source_id': owner.id, 'name': owner.name, 'members': members,
                    'members_total': len(members), 'members_truncated': False})
                continue
            for index in node.children:
                child = nodes[index]
                if child.name not in {'ProduceInfo', 'ConsumeInfo'}:
                    continue
                okay = (child.expanded_name.rsplit('}', 1)[0] if '}' in child.expanded_name else None) == self.base._namespace
                okay = okay and not any('}' in key for key in child.expanded_attributes)
                value = {'kind': child.name, 'source_id': owner.id, 'locator': child.locator,
                         'attributes': dict(child.expanded_attributes), 'status': 'extracted' if okay else 'unknown',
                         'child_elements': len(child.children), 'direct_text': child.text,
                         'interpretation': 'captured_attributes_only'}
                self._communications[owner.id].append(value)
                self._retain(value)
                if not okay or child.children or child.text.strip():
                    self._gaps['unmodeled_communication_details'] += 1

    def _controller(self, owner: Any) -> str | None:
        if owner.id in self._controllers:
            return self._controllers[owner.id]
        scope = self.base._entities.get(owner.scope_id)
        for _ in range(160):
            if scope is None or scope.kind == 'controller':
                self._controllers[owner.id] = scope.id if scope else None
                return self._controllers[owner.id]
            scope = self.base._entities.get(scope.scope_id)
        return None

    def _declaration_members(self) -> None:
        """List qualified UDT members; never unroll uncaptured array elements."""
        roots = [entity for entity in self.base._entities.values() if entity.kind in _ROOTS
                 and self.base._entity_ok.get(entity.id) and entity.attributes.get('TagType') != 'Alias']
        expanded: set[tuple[str, str, str]] = set()
        work = 0

        def expand(owner: Any, prefix: str, datatype: str, trail: tuple[str, ...]) -> None:
            nonlocal work
            identity = owner.id, _member_key(prefix), datatype.casefold()
            if identity in expanded:
                return
            expanded.add(identity)
            definitions = self._definitions.get((self._controller(owner), datatype.casefold()), [])
            if len(definitions) != 1:
                if len(definitions) > 1:
                    self._gaps['ambiguous_datatype_definitions'] += 1
                return
            if datatype.casefold() in trail or len(trail) >= 16:
                self._gaps['recursive_or_deep_datatype_definitions'] += 1
                return
            definition = definitions[0]
            parent = self._add(owner.id, prefix, 'container')
            parent['datatype_definition_source_id'] = definition['source_id']
            for member in definition['members']:
                work += 1
                if work > MAX_REGISTERS * 4:
                    _invalid()
                if member['status'] != 'extracted':
                    self._gaps['unresolved_datatype_members'] += 1
                    continue
                attrs = member['attributes']
                suffix = prefix + '.' + member['name']
                dimensions = attrs.get('Dimension', attrs.get('Dimensions', '0'))
                nested = self._definitions.get((self._controller(owner), attrs.get('DataType', '').casefold()))
                row = self._add(owner.id, suffix, 'container' if nested or dimensions not in {'', '0'} else 'scalar')
                if row['dimensions'] is None:
                    row['dimensions'] = dimensions
                self._declared_members[owner.id, _member_key(suffix)] = member
                existing_notes = {note['id'] for note in self._annotations[row['id']]}
                self._annotations[row['id']].extend(note for note in member.get('source_annotations', [])
                                                     if note['id'] not in existing_notes)
                if dimensions in {'', '0'} and attrs.get('DataType'):
                    expand(owner, suffix, attrs['DataType'], (*trail, datatype.casefold()))

        for owner in roots:
            dtype = owner.attributes.get('DataType')
            if not dtype:
                continue
            if owner.attributes.get('Dimensions', '') in {'', '0'}:
                expand(owner, '', dtype, ())
            else:
                for identifier in list(self._by_owner[owner.id]):
                    row = self.registers[identifier]
                    match = re.match(r'\[[^\]]+\]', row['suffix'])
                    if match and _declaration(owner, match.group())[1] == 'static_in_bounds':
                        expand(owner, match.group(), dtype, ())
            # Expand only array indexes that actually occur in captured members
            # or explicit references, never every possible declared element.
            for _ in range(16):
                added = False
                for identifier in list(self._by_owner[owner.id]):
                    row = self.registers[identifier]
                    for match in re.finditer(r'\[[^\]]+\]', row['suffix']):
                        prefix = row['suffix'][:match.start()]
                        member = self._declared_members.get((owner.id, _member_key(prefix)))
                        if member is None:
                            continue
                        attrs = dict(member['attributes'])
                        attrs['Dimensions'] = attrs.get('Dimension', attrs.get('Dimensions', '0'))
                        if _declaration(SimpleNamespace(attributes=attrs), match.group())[1] != 'static_in_bounds':
                            continue
                        instance = row['suffix'][:match.end()]
                        structured = self._definitions.get((self._controller(owner), attrs.get('DataType', '').casefold()))
                        target = self._add(owner.id, instance, 'container' if structured else 'scalar')
                        self._declared_members[owner.id, _member_key(instance)] = dict(member, selection='static_array_element')
                        existing_notes = {note['id'] for note in self._annotations[target['id']]}
                        self._annotations[target['id']].extend(note for note in member.get('source_annotations', [])
                                                               if note['id'] not in existing_notes)
                        if target.get('datatype_definition_source_id'):
                            continue
                        before = len(self.registers)
                        expand(owner, instance, attrs.get('DataType', ''), ())
                        added = added or len(self.registers) > before
                if not added:
                    break

    def _metadata(self) -> None:
        for row in self.registers.values():
            owner = self.base._entities[row['root_id']]
            member = self._declared_members.get((owner.id, _member_key(row['suffix'])))
            attrs = member['attributes'] if member else owner.attributes if not row['suffix'] else {}
            basis = ('static_declared_member_array_element' if member and member.get('selection') == 'static_array_element'
                     else 'datatype_member_declaration' if member else 'root_declaration')
            source_id = member['source_id'] if member else owner.id
            if (row['suffix'] and not attrs and self.base._entity_ok.get(owner.id)
                    and _declaration(owner, row['suffix'])[1] == 'static_in_bounds'):
                attrs, basis = owner.attributes, 'static_root_array_element'
            if row['suffix'] and not attrs:
                match = re.fullmatch(r'(.+)(\[[^\]]+\])', row['suffix'])
                array_member = self._declared_members.get((owner.id, _member_key(match[1]))) if match else None
                if array_member:
                    array_attrs = dict(array_member['attributes'])
                    array_attrs['Dimensions'] = array_attrs.get('Dimension', array_attrs.get('Dimensions', '0'))
                    if _declaration(SimpleNamespace(attributes=array_attrs), match[2])[1] == 'static_in_bounds':
                        attrs, basis, source_id = array_attrs, 'static_declared_member_array_element', array_member['source_id']
            if member:
                row['declaration_member'] = member
                row['states'].setdefault('member', 'resolved')
                if attrs.get('ExternalAccess') is not None:
                    row['external_access'] = attrs['ExternalAccess']
            dimensions = attrs.get('Dimension', attrs.get('Dimensions'))
            if dimensions is not None and basis not in {'static_root_array_element', 'static_declared_member_array_element'}:
                row['declared_dimensions'] = dimensions
                if row['dimensions'] is not None and row['dimensions'] != dimensions:
                    row.setdefault('metadata_conflicts', {})['dimensions'] = {'declared': dimensions,
                        'captured': row['dimensions'], 'declaration_source_id': source_id, 'declaration_basis': basis}
                    row['dimensions'], row['states']['dimensions'] = None, 'unknown'
                else:
                    row['dimensions'], row['states']['dimensions'] = dimensions, 'extracted'
            for field, attribute in (('datatype', 'DataType'), ('radix', 'Radix')):
                declared, captured = attrs.get(attribute), row[field]
                row['declared_' + field] = declared
                if declared and captured and declared.casefold() != captured.casefold():
                    row.setdefault('metadata_conflicts', {})[field] = {'declared': declared, 'captured': captured,
                        'declaration_source_id': source_id, 'declaration_basis': basis}
                    row[field], row['states'][field] = None, 'unknown'
                    self._gaps['declaration_' + field + '_conflicts'] += 1
                elif declared and not captured and row['states'][field] == 'unknown':
                    # A known conflict in captured evidence must not be erased by a fallback.
                    values = self._values[row['id']]
                    if (any(value.get('metadata_status') == 'conflict' for value in values)
                            or len({value[field] for value in values if value.get(field)}) > 1):
                        continue
                    row[field] = declared
                    row['states'][field] = 'extracted' if not row['suffix'] else 'resolved'
                    row['provenance'][field + '_source_ids'] = [source_id]
                    row['provenance'][field + '_basis'] = basis

    def _value_records(self, owner_id: str, suffix: str, values: list[dict]) -> list[dict]:
        records = []
        for value in values:
            ambiguous = self._path_ambiguous(owner_id, suffix, value['content_id'])
            records.append(dict(value, ambiguous=ambiguous))
        return records

    def _path_ambiguous(self, owner_id: str, suffix: str, content_id: str) -> bool:
        key = _member_key(suffix)
        return any(gap == '' or key == gap or key.startswith(gap + '.') or key.startswith(gap + '[')
                   for gap in self.base._ambiguous.get((owner_id, content_id), set()))

    def _build(self) -> None:
        self._hardware()
        for entity in self.base._entities.values():
            if entity.kind in _ROOTS:
                self._add(entity.id, '')
        self._source_details()
        self._containers()
        for (owner_id, suffix), values in self.base._values.items():
            if self.base._entities[owner_id].kind not in _ROOTS:
                continue
            row = self._add(owner_id, values[0]['path'])
            values = self._value_records(owner_id, values[0]['path'], values)
            self._values[row['id']].extend(values)
            self._retain(values)
            qualified = ([] if any(value['ambiguous'] for value in values) else
                         [value for value in values if value['status'] == 'qualified'])
            for field in ('datatype', 'radix'):
                choices = {value[field] for value in qualified if value.get(field)}
                if len(choices) == 1:
                    row[field] = next(iter(choices))
                    inherited = any(value.get(field + '_basis') in {'array_parent', 'immediate_array'} or
                                    str(value.get(field + '_basis', '')).startswith('inherited') for value in qualified)
                    row['states'][field] = 'resolved' if inherited else 'extracted'
                    row['provenance'][field + '_source_ids'] = sorted({
                        value.get(field + '_source_id') or value['element_id'] for value in qualified if value.get(field)})
                elif len(choices) > 1:
                    row[field], row['states'][field] = None, 'unknown'
                    self._gaps['conflicting_' + field] += 1
            row['states']['member'] = ('resolved' if qualified and all(value['status'] == 'qualified' and not value['ambiguous'] for value in values)
                                       else 'unknown')
        self._references()
        self._declaration_members()
        self._descriptions()
        self._metadata()
        for address in self.io.addresses.values():
            row = self._add(address['root_id'], address['suffix'])
            if address['channel'] is not None:
                row['physical'] = {'field_type': address['field_type'], 'channel': address['channel'],
                                   'status': 'vendor_documented', 'reference': address['point_reference'],
                                   'basis': address['point_basis'], 'configuration_status': address['configuration_status']}
                row['states']['physical'] = 'vendor_documented'
            # Field-I/O candidates include qualified alias and module fallbacks;
            # combine them with UDT member descriptions without losing priority.
            candidates = list(self._annotations[row['id']])
            for note in (address.get('description_selection') or {}).get('candidates', []):
                candidates.append(dict(note, text=self.annotation_texts.get(note['id'], note.get('text', ''))))
            selection = select_description(candidates, text_lookup=self.annotation_texts)
            row['description_selection'] = selection
            preferred = selection['preferred_annotation_id']
            row['description'] = self.annotation_texts.get(preferred) if preferred else row['description']
            deduplicated = {note['id']: note for note in candidates}
            self._annotations[row['id']] = list(deduplicated.values())
        for row in self.registers.values():
            target = self.registers.get(row.get('alias_binding', {}).get('register_id'))
            if target is not None:
                for field in ('datatype', 'radix'):
                    if row[field] is not None and target[field] is not None and row[field].casefold() != target[field].casefold():
                        row.setdefault('metadata_conflicts', {})[field] = {'declared': row[field], 'target': target[field],
                            'target_register_id': target['id'], 'declaration_basis': 'alias_target_conflict'}
                        row[field], row['states'][field] = None, 'unknown'
                    elif row[field] is None and target[field] is not None and not row.get('metadata_conflicts', {}).get(field):
                        row[field] = target[field]
                        row['states'][field] = 'resolved'
                        row['provenance'][field + '_source_ids'] = target['provenance'].get(field + '_source_ids', [])
            suffix = row['suffix']
            if suffix:
                parent = re.sub(r'(?:\.[^.\[]+|\[[^\]]*\])$', '', suffix)
                row['parent_register_id'] = self._keys.get((row['root_id'], _member_key(parent)))
            row['logic_access'] = {'roles': sorted({use['role'] for use in self._uses[row['id']]}),
                                   'uses_total': len(self._uses[row['id']])}
            row['aliases_total'] = len(self._aliases[row['id']])
            if row['declaration_kind'] in {'produced', 'consumed'}:
                row['transport'] = {'label': row['declaration_kind'].capitalize() + ' tag',
                                    'status': 'extracted', 'basis': 'tag_type_declaration'}
            elif row['module_id'] and self.base._entity_ok.get(row['root_id']) and self.modules[row['module_id']]['qualified']:
                row['transport'] = {'label': 'Configured module ' + row['io_direction'] + ' payload',
                                    'status': 'resolved', 'basis': 'qualified_module_root_or_alias_binding'}
            search = ' '.join(str(value or '') for value in (row['address'], row['description'], row['path'],
                    row['datatype'], row['alias_target'], *[alias['name'] for alias in self._aliases[row['id']]])).casefold()
            self._search[row['id']] = search
            self._retain(row)
            self._retain(search)
        self._coverage()

    def _coverage(self) -> None:
        base = self.base
        role_counts = Counter(row.opcode.upper() for row in base._instructions.values())
        operand_gaps = Counter(row['status'] for row in base._references.operands)
        data = getattr(base, '_data_evidence', None)
        self.coverage = {'modules_total': len(self.modules), 'registers_total': len(self.registers),
            'registers_by_declaration_kind': dict(Counter(row['declaration_kind'] for row in self.registers.values())),
            'registers_by_direction': dict(Counter(row['io_direction'] for row in self.registers.values())),
            'registers_by_member_kind': dict(Counter(row['member_kind'] for row in self.registers.values())),
            'registers_by_datatype': dict(Counter(row['datatype'] or 'unknown' for row in self.registers.values())),
            'routes_by_status': dict(Counter(row['route']['status'] for row in self.modules.values())),
            'source_declarations': sum(row['member_kind'] == 'declaration' for row in self.registers.values()),
            'raw_payload_members': sum(bool(row['module_id'] and row['suffix']) for row in self.registers.values()),
            'vendor_documented_channels': sum(row['physical']['status'] == 'vendor_documented' for row in self.registers.values()),
            'vendor_decoded_payloads': 0, 'captured_values': sum(len(values) for values in self._values.values()),
            'representations_total': sum(len(values) for values in base._contents.values()),
            'representations_by_format': dict(Counter(row['format_kind'] for values in base._contents.values() for row in values)),
            'reference_operands_by_status': dict(operand_gaps),
            'copy_range_instructions_not_expanded': sum(role_counts[opcode] for opcode in ('COP', 'CPS', 'FLL')),
            'instructions_with_unknown_access': sum(row.get('status') != 'classified' for row in base._access.instructions) if base._access else len(base._instructions),
            'source_inventory_coverage': base._captured.coverage,
            'export_attributes': base._captured.export_attributes,
            'communication_details': sum(len(rows) for rows in self._communications.values()),
            'datatype_definitions': sum(len(rows) for rows in self._definitions.values()),
            'datatype_declared_members': len(self._declared_members),
            'unresolved_reference_examples': self._unresolved,
            'unresolved_reference_examples_truncated': self._gaps['unresolved_or_unqualified_reference_operands'] > len(self._unresolved),
            'routine_types': base._captured.routine_types,
            'encoded_regions': sum(entity.kind == 'encoded_region' for entity in base._entities.values()),
            'inventory_diagnostics': dict(Counter(row.code for row in base._captured.diagnostics)),
            'aoi_calls_not_expanded': sum(role_counts[entity.name.upper()] for entity in base._entities.values()
                                          if entity.kind == 'aoi' and entity.name),
            'tag_data_coverage': data.coverage if data else {},
            'gaps': dict(self._gaps), 'has_tag_data': base._has_data, 'has_instruction_access': base._has_access,
            'totals_scope': 'captured_and_statically_associated_records_not_all_runtime_memory'}
        self._retain(self.coverage)

    def _detail(self, row: dict, query: dict) -> dict:
        owner = self.base._entities[row['root_id']]
        values = self._values[row['id']]
        contents = self.base._contents[row['root_id']]
        definitions = self._definitions.get((self._controller(owner), (row['datatype'] or row.get('declared_datatype') or '').casefold()), [])
        definition = definitions[0] if len(definitions) == 1 else None
        if definition:
            definition = dict(definition, members=definition['members'][:MAX_DETAIL],
                              members_truncated=definition['members_total'] > MAX_DETAIL)
        result = dict(row, attributes=dict(owner.attributes),
                      datatype_definition=definition,
                      communications=self._communications[row['root_id']][:MAX_DETAIL],
                      communications_total=len(self._communications[row['root_id']]),
                      communications_truncated=len(self._communications[row['root_id']]) > MAX_DETAIL,
                      uses=_page(self._uses[row['id']], query['use_page'], query['page_size']),
                      values=values[:MAX_DETAIL], values_total=len(values), values_truncated=len(values) > MAX_DETAIL,
                      representations=contents[:MAX_DETAIL], representations_total=len(contents),
                      representations_truncated=len(contents) > MAX_DETAIL,
                      aliases=self._aliases[row['id']][:MAX_DETAIL],
                      aliases_truncated=len(self._aliases[row['id']]) > MAX_DETAIL,
                      source_annotations=self._annotations[row['id']][:MAX_DETAIL],
                      source_annotations_total=len(self._annotations[row['id']]),
                      source_annotations_truncated=len(self._annotations[row['id']]) > MAX_DETAIL)
        return _bounded(result)

    def view(self, query: dict) -> dict:
        query = validate_query(query)
        module_id, register_id = query['module_id'], query['register_id']
        if module_id and module_id not in self.modules:
            raise ApplicationError('Choose a module captured in this run.')
        if register_id and register_id not in self.registers:
            raise ApplicationError('Choose a register captured in this run.')
        if register_id and module_id and self.registers[register_id]['module_id'] != module_id:
            raise ApplicationError('Choose a register belonging to this configured module.')
        rows = [row for row in self.registers.values()
                if (not module_id or row['module_id'] == module_id)
                and (not query['direction'] or row['io_direction'] == query['direction'])
                and (not query['declaration_kind'] or row['declaration_kind'] == query['declaration_kind'])
                and (not query['member_kind'] or row['member_kind'] == query['member_kind'])
                and (not query['datatype'] or (row['datatype'] or '').casefold() == query['datatype'].casefold())
                and (not query['query'] or query['query'].casefold() in self._search[row['id']])
                and (not query['logic_role'] or query['logic_role'] in row['logic_access']['roles']
                     or query['logic_role'] == 'unused' and not row['logic_access']['uses_total'])]
        rows.sort(key=lambda row: (row['scope']['path'].casefold(), row['address'].casefold(), row['id']))
        modules = sorted(self.modules.values(), key=lambda row: ((row['controller']['name'] or '').casefold(),
                                                                 (row['name'] or '').casefold(), row['id']))
        if query['query']:
            matched_modules = {row['module_id'] for row in rows}
            modules = [row for row in modules if row['id'] in matched_modules or query['query'].casefold() in
                       ' '.join(str(row[key] or '') for key in ('name', 'description', 'catalog_number')).casefold()]
        selected = self.registers.get(register_id)
        module = self.modules.get(module_id or (selected['module_id'] if selected else None))
        result = {'available': True, 'snapshot_id': self.base._captured.snapshot['id'],
            'notice': 'Configured hardware and captured application registers, with source facts and unresolved relationships kept separate.',
            'modules': _page(modules, query['module_page'], query['page_size']),
            'registers': _page(rows, query['page'], query['page_size']),
            'selected_module': module, 'selected_register': self._detail(selected, query) if selected else None,
            'coverage': self.coverage, 'limitations': list(_LIMITATIONS)}
        result = _bounded(result)
        if len(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) > MAX_RESPONSE_BYTES:
            _invalid()
        return deepcopy(result)
