"""Qualified datatype-member wording without expanding UDT instances or arrays.

Descriptions remain owned by their exact datatype declaration. A lookup walks
one statically addressed source path and checks captured layout conflicts; it
never manufactures channel rows, offsets, values or source identities.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import re
from typing import Any

from .references import _ROOT
from .source import _read_nodes
from .workspace_io_comments import select_description
from .workspace_variables import VariableIndex, _member_key

MAX_METADATA_BYTES = 12 * 1024 * 1024
MAX_MEMBERS = 100_000
MAX_DEPTH = 32
LOOKUP_REASONS = ('available', 'no_description', 'no_type_definition', 'member_not_declared',
                  'conflict', 'unsupported_path', 'capacity')
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*', re.ASCII)
_TOKEN = re.compile(r'\.[A-Za-z_][A-Za-z0-9_]*|\[\s*[0-9]+(?:\s*,\s*[0-9]+)*\s*\]', re.ASCII)
_ROOT_KINDS = {'tag', 'aoi_parameter', 'aoi_local_tag', 'module_input_tag', 'module_output_tag', 'module_config_tag'}


def _dimensions(value: str | None) -> tuple[int, ...] | None:
    value = (value or '').strip()
    if value in {'', '0'}:
        return ()
    if len(value) > 64 or not re.fullmatch(r'[0-9]+(?:\s*[, ]\s*[0-9]+)*', value):
        return None
    parts = tuple(int(part) for part in re.split(r'[, ]+', value))
    return parts if 1 <= len(parts) <= 3 and all(0 < size <= 2_147_483_647 for size in parts) else None


def _prefixes(suffix: str) -> list[str]:
    return ['', *[suffix[:match.start()] for match in re.finditer(r'[.\[]', suffix) if match.start()], suffix]


def _key(suffix: str) -> str:
    return re.sub(r'\[\s*([0-9]+(?:\s*,\s*[0-9]+)*)\s*\]',
        lambda match: '[' + ','.join(part.strip().lstrip('0') or '0' for part in match[1].split(',')) + ']',
        _member_key(suffix))


class _Capacity(ValueError):
    pass


class DeclaredMemberDescriptions:
    """Shared immutable schemas, bounded metadata, and uncached path lookups."""

    def __init__(self, base: VariableIndex) -> None:
        if type(base) is not VariableIndex:
            raise ValueError('Choose authenticated variable evidence for member descriptions.')
        self.base = base
        self._definitions: dict[tuple[str | None, str], dict | None] = {}
        self._layouts: dict[tuple[str, str], tuple[str, tuple[int, ...] | None]] = {}
        self._blocked: set[tuple[str, str]] = set()
        self._value_aliases: dict[tuple[str, str], list[str]] = defaultdict(list)
        self._structure_elements: set[str] = set()
        self._budget = self._member_count = 0
        self.available = True
        try:
            self._schemas()
            if self._definitions:
                self._captured_layouts()
        except _Capacity:
            self._definitions.clear()
            self._layouts.clear()
            self._blocked.clear()
            self._value_aliases.clear()
            self._structure_elements.clear()
            self._budget = 0
            self.available = False

    def _retain(self, value: Any) -> None:
        self._budget += len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self._budget > MAX_METADATA_BYTES or self._member_count > MAX_MEMBERS:
            raise _Capacity()

    def _controller(self, owner: Any) -> str | None:
        for _ in range(160):
            if owner is None or owner.kind == 'controller':
                return owner.id if owner else None
            owner = self.base._entities.get(owner.scope_id)
        return None

    def _schemas(self) -> None:
        owners = {entity.locator: entity for entity in self.base._entities.values() if entity.kind == 'data_type'}
        if not owners:
            return
        nodes = _read_nodes(self.base._source)
        namespace = nodes[0].expanded_name.rpartition('}')[0]
        okay = []
        for node in nodes:
            okay.append(node.expanded_name.rpartition('}')[0] == namespace
                and not any('}' in key for key in node.expanded_attributes)
                and node.attributes.get('Protected', 'false').casefold() not in {'true', '1'}
                and (node.parent is None or okay[node.parent]))
        for index, node in enumerate(nodes):
            owner = owners.get(node.locator)
            if owner is None or not owner.name or not _ROOT.fullmatch(owner.name):
                continue
            key = self._controller(owner), owner.name.casefold()
            definition = None
            parent = nodes[node.parent] if node.parent is not None else None
            containers = [child for child in node.children if nodes[child].name == 'Members']
            if (self.base._entity_ok.get(owner.id) and okay[index] and parent is not None
                    and parent.name == 'DataTypes' and len(containers) == 1 and okay[containers[0]]
                    and not any(nodes[child].name == 'EncodedData' for child in node.children)):
                members: dict[str, dict | None] = {}
                for member_index in nodes[containers[0]].children:
                    member = nodes[member_index]
                    name = member.attributes.get('Name', '')
                    if not _NAME.fullmatch(name):
                        continue
                    value = None
                    if member.name == 'Member' and okay[member_index]:
                        attrs = member.attributes
                        dimensions = _dimensions(attrs.get('Dimension', attrs.get('Dimensions')))
                        if ('Dimension' in attrs and 'Dimensions' in attrs
                                and dimensions != _dimensions(attrs['Dimensions'])):
                            dimensions = None
                        datatype = attrs.get('DataType', '')
                        if datatype and _ROOT.fullmatch(datatype) and dimensions is not None:
                            notes = []
                            for description_index in member.children:
                                description = nodes[description_index]
                                if description.name != 'Description' or not okay[description_index]:
                                    continue
                                text_indexes = (description.children if description.children and not description.text.strip()
                                    and all(nodes[child].name == 'LocalizedDescription' for child in description.children)
                                    else [description_index] if not description.children else [])
                                for text_index in text_indexes:
                                    text = nodes[text_index]
                                    if not okay[text_index] or text.children or not text.text.strip():
                                        continue
                                    identifier = hashlib.sha256(f'{self.base._captured.snapshot["id"]}\0{text.locator}\0datatype_member_description'.encode()).hexdigest()
                                    notes.append({'id': 'io_annotation_' + identifier, 'owner_id': owner.id,
                                        'source_id': owner.id, 'owner_name': owner.name + '.' + name,
                                        'owner_suffix': '.' + name, 'suffix': '.' + name,
                                        'owner_path': self.base._path(owner.id) + ' / ' + name,
                                        'locator': text.locator, 'kind': 'datatype_member_description',
                                        'language': text.attributes.get('Lang'), 'text': text.text,
                                        'description_scope': 'declared_member_description'})
                            value = {'name': name, 'datatype': datatype, 'dimensions': dimensions, 'annotations': notes}
                    member_key = name.casefold()
                    members[member_key] = None if member_key in members else value
                    self._member_count += 1
                    self._retain((member_key, value))
                definition = {'owner_id': owner.id, 'members': members}
            self._definitions[key] = None if key in self._definitions else definition
            self._retain((key, owner.id))

    def _block(self, root: str, path: str) -> None:
        key = root, _key(path)
        if key not in self._blocked:
            self._retain(key)
            self._blocked.add(key)

    def _captured_layouts(self) -> None:
        data = self.base._data_evidence
        if data is None:
            return
        contents = {row['id']: row for row in data.contents if row['xml_name'] == 'Data' and row['format_kind'] == 'decorated'}
        parents = {row['parent_id'] for row in data.elements}
        counts: dict[str, int] = defaultdict(int)
        paths: dict[str, str | None] = {identifier: '' for identifier in contents}
        for content in contents.values():
            counts[content['owner_id']] += 1
            for path in self.base._ambiguous.get((content['owner_id'], content['id']), ()):
                self._block(content['owner_id'], path)
        for root, count in counts.items():
            if count != 1:
                self._block(root, '')
        for root, path in self.base._values:
            normalized = _key(path)
            if normalized != path:
                if (root, normalized) in self.base._values or self._value_aliases.get((root, normalized)):
                    self._block(root, normalized)
                self._retain((root, normalized, path))
                self._value_aliases[root, normalized].append(path)
        for row in data.elements:
            if row['content_id'] not in contents:
                continue
            parent, name, attrs = paths.get(row['parent_id']), row['xml_name'], row['attributes']
            path = None
            if parent is not None:
                if name in {'Structure', 'Array', 'DataValue'}:
                    path = parent
                elif name in {'StructureMember', 'ArrayMember', 'DataValueMember'} and _NAME.fullmatch(attrs.get('Name', '')):
                    path = parent + '.' + attrs['Name']
                elif name == 'Element' and _TOKEN.fullmatch(attrs.get('Index', '')) and attrs['Index'].startswith('['):
                    path = parent + attrs['Index']
            paths[row['id']] = path if path is None or len(path) <= 4096 else None
            if path is None or len(path) > 4096:
                self._block(row['owner_id'], parent or '')
                continue
            if name == 'Element' and row['id'] in parents:
                self._retain(row['id'])
                self._structure_elements.add(row['id'])
            if name not in {'Structure', 'StructureMember', 'Array', 'ArrayMember'}:
                continue
            datatype = attrs.get('DataType')
            if not datatype:
                continue
            dimensions = _dimensions(attrs.get('Dimensions')) if name in {'Array', 'ArrayMember'} else ()
            if name in {'Array', 'ArrayMember'} and not dimensions:
                dimensions = None
            key = row['owner_id'], _key(path)
            value = datatype.casefold(), dimensions
            if key in self._layouts and self._layouts[key] != value:
                self._block(*key)
            else:
                self._retain((key, value))
                self._layouts[key] = value

    def _matches(self, root: str, path: str, datatype: str, dimensions: tuple[int, ...]) -> bool:
        key = root, _key(path)
        if any((root, _key(prefix)) in self._blocked for prefix in _prefixes(path)):
            return False
        layout = self._layouts.get(key)
        if layout is not None and layout != (datatype.casefold(), dimensions):
            return False
        for value_path in (key[1], *self._value_aliases.get(key, ())):
            for value in self.base._values.get((root, value_path), ()):
                if value['envelope'] == 'Data' and value['format'] == 'decorated':
                    if value['element_id'] in self._structure_elements and layout is not None:
                        continue  # Its qualified Structure/Array layout is checked above.
                    if (value['status'] != 'qualified' or value.get('datatype')
                            and value['datatype'].casefold() != datatype.casefold()):
                        return False
        return True

    def inspect(self, root_id: str, suffix: str) -> dict:
        facts = {'root_type_declared': False, 'captured_layout': False, 'path_static': False,
                 'member_depth': 0, 'array_rank': 0, 'description_count': 0}
        def result(status: str, notes: list[dict] | None = None) -> dict:
            return {'status': status, 'facts': facts, 'annotations': deepcopy(notes or [])}
        if not self.available:
            return result('capacity')
        root = self.base._entities.get(root_id)
        if (root is None or root.kind not in _ROOT_KINDS or not self.base._entity_ok.get(root_id)
                or not isinstance(suffix, str) or not suffix or len(suffix) > 4096):
            return result('unsupported_path')
        tokens = list(_TOKEN.finditer(suffix))
        if ''.join(token.group() for token in tokens) != suffix or len(tokens) > MAX_DEPTH:
            return result('unsupported_path')
        facts['path_static'] = True
        dtype = root.attributes.get('DataType')
        facts['root_type_declared'] = bool(dtype)
        layout = self._layouts.get((root_id, ''))
        facts['captured_layout'] = layout is not None
        dimensions = _dimensions(root.attributes.get('Dimensions'))
        if not dtype and layout:
            dtype, dimensions = layout
        if not dtype:
            return result('no_type_definition')
        if dimensions is None or not self._matches(root_id, '', dtype, dimensions):
            return result('conflict')
        controller, prefix, selected = self._controller(root), '', None
        for token in tokens:
            part = token.group()
            if part.startswith('['):
                indexes = [int(value.strip()) for value in part[1:-1].split(',')]
                facts['array_rank'] = max(facts['array_rank'], len(indexes))
                if len(indexes) != len(dimensions) or not dimensions or any(index >= size for index, size in zip(indexes, dimensions)):
                    return result('unsupported_path')
                dimensions = ()
            else:
                if dimensions:
                    return result('unsupported_path')
                key = controller, dtype.casefold()
                if key not in self._definitions:
                    return result('no_type_definition')
                definition = self._definitions[key]
                if definition is None:
                    return result('conflict')
                if part[1:].casefold() not in definition['members']:
                    return result('member_not_declared')
                selected = definition['members'][part[1:].casefold()]
                if selected is None:
                    return result('conflict')
                dtype, dimensions = selected['datatype'], selected['dimensions']
                facts['member_depth'] += 1
            prefix += part
            if not self._matches(root_id, prefix, dtype, dimensions):
                return result('conflict')
        if selected is None:
            return result('unsupported_path')
        notes = selected['annotations']
        facts['description_count'] = len(notes)
        status = 'conflict' if select_description(notes)['conflict'] else 'available' if notes else 'no_description'
        return result(status, notes)

    def diagnostic(self, root_id: str, suffix: str) -> dict:
        result = self.inspect(root_id, suffix)
        return {'status': result['status'], **result['facts']}

    def lookup_reason(self, root_id: str, suffix: str) -> str:
        return self.inspect(root_id, suffix)['status']

    def annotation(self, owner_id: str, annotation_id: str) -> dict | None:
        """Return one exact owned note without another retained lookup table."""
        for definition in self._definitions.values():
            if definition is not None and definition['owner_id'] == owner_id:
                for member in definition['members'].values():
                    for note in member['annotations'] if member else ():
                        if note['id'] == annotation_id:
                            return deepcopy(note)
        return None
