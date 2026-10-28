"""Bounded fixed copy/fill footprints from qualified scalar storage evidence.

COP/CPS copy bytes; Length counts destination elements, not source elements.
FLL likewise sizes its destination footprint from destination element bytes.
Only SINT/INT/DINT/REAL scalars and one-dimensional arrays are modeled here.
No UDT offsets, BOOL packing, controller-specific clipping, or live values are
inferred. A request crossing a member boundary remains unresolved because these
instructions can continue into the enclosing base tag.

Rockwell instruction references:
https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-01/contents-ditamap/instruction-set/array-file-misc-instructions/copy-synchronous-copy-file--cps-.html
https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/array-file-misc-instructions/file-fill-fll.html
"""
from __future__ import annotations

import json
import re
from typing import Any

from .references import _NUMBER
from .workspace_variables import VariableIndex, _child, _member_key
from .workspace_rack_references import RackReferenceIndex

MAX_LAYOUTS = 100_000
MAX_LAYOUT_BYTES = 16 * 1024 * 1024
_WIDTHS = {'SINT': 1, 'INT': 2, 'DINT': 4, 'REAL': 4}
_INTEGER_TYPES = frozenset({'SINT', 'INT', 'DINT'})
_EXPLANATIONS = {
    'unsupported_instruction': 'This instruction or operand does not have a supported fixed copy/fill range.',
    'unqualified_operand': 'The operand could not be bound to one qualified source declaration.',
    'variable_length': 'Length is not a supported nonnegative integer literal. A saved tag value does not establish its runtime length.',
    'missing_layout': 'A qualified scalar datatype or array layout is missing for an operand.',
    'ambiguous_layout': 'Conflicting or duplicate captured datatype/layout evidence prevents a single byte range.',
    'unsupported_layout': 'The captured storage type or dimensions are not modeled: structures, packed BOOLs and multidimensional arrays need additional layout support.',
    'array_element_required': 'An explicit array element is needed to establish the starting byte.',
    'invalid_index': 'The literal starting index is outside the captured array dimensions.',
    'member_boundary': 'The requested bytes extend beyond a known scalar or member array. The enclosing structure layout is needed; the range has not been clipped.',
    'metadata_limit': 'The bounded datatype/layout index reached its capacity.',
    'fixed_range': 'The immediate length and qualified scalar layouts establish this byte range.',
    'different_root': 'This address belongs to a different source declaration.',
    'outside_range': 'This address is outside the proven fixed byte range.',
    'containing_object': 'Only part of this containing object is covered by the fixed range.',
    'unmodeled_member': 'This member spelling cannot be placed inside the proven scalar/array storage layout.',
    'zero_length': 'The literal length is zero, so the fixed range covers no additional bytes.',
}


def _key(suffix: str) -> str:
    value = _member_key(suffix)
    value = re.sub(r'\[\s*([0-9]+(?:\s*,\s*[0-9]+)*)\s*\]',
        lambda match: '[' + ','.join(str(int(part)) for part in match[1].split(',')) + ']', value)
    return re.sub(r'\.([0-9]+)(?=\.|\[|$)', lambda match: '.' + str(int(match[1])), value)


def _integer(text: str) -> int | None:
    text = text.strip()
    if len(text) > 64:
        return None
    if re.fullmatch(r'\+?[0-9]+', text):
        value = int(text)
    else:
        match = re.fullmatch(r'\+?(2#[01](?:_?[01])*|8#[0-7](?:_?[0-7])*|16#[0-9a-fA-F](?:_?[0-9a-fA-F])*)', text)
        if not match:
            return None
        radix, digits = text.lstrip('+').split('#')
        value = int(digits.replace('_', ''), int(radix))
    return value if value <= 2_147_483_647 else None


class _LayoutLimit(ValueError):
    pass


class UsageRangeResolver:
    """Build metadata once; descriptors and matches are detached, uncached data."""

    def __init__(self, base: VariableIndex, rack_references: RackReferenceIndex | None = None) -> None:
        if (type(base) is not VariableIndex or rack_references is not None
                and (type(rack_references) is not RackReferenceIndex or rack_references.base is not base)):
            raise ValueError('Choose authenticated variable evidence for fixed ranges.')
        self.base = base
        self._resolve = rack_references.binding if rack_references is not None else base._resolve
        self._layouts: dict[tuple[str, str], dict] = {}
        self._blocked: dict[tuple[str, str], str] = {}
        self._budget = 0
        self._limited = False
        try:
            self._build()
        except _LayoutLimit:
            self._layouts.clear()
            self._blocked.clear()
            self._budget = 0
            self._limited = True

    def _charge(self, value: Any) -> None:
        self._budget += len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self._budget > MAX_LAYOUT_BYTES or len(self._layouts) + len(self._blocked) >= MAX_LAYOUTS:
            raise _LayoutLimit()

    def _block(self, key: tuple[str, str], reason: str) -> None:
        if key not in self._blocked:
            self._charge((key, reason))
            self._blocked[key] = reason
            self._layouts.pop(key, None)

    def _add(self, root: str, suffix: str, datatype: str | None, dimensions: str | None,
             source_id: str, *, array: bool = False) -> None:
        key = root, _key(suffix)
        if key in self._blocked:
            return
        datatype = (datatype or '').upper()
        if datatype not in _WIDTHS:
            if datatype:
                self._block(key, 'ambiguous_layout' if key in self._layouts else 'unsupported_layout')
            return  # A UDT root does not invalidate modeled child array paths.
        dimension = str(dimensions or '').strip()
        if not array and dimension in {'', '0'}:
            count, kind = 1, 'scalar'
        elif re.fullmatch(r'[0-9]{1,10}', dimension) and 0 < int(dimension) <= 2_147_483_647:
            count, kind = int(dimension), 'array'
        else:
            self._block(key, 'unsupported_layout')
            return
        row = {'datatype': datatype, 'element_bytes': _WIDTHS[datatype], 'count': count,
               'kind': kind, 'source_id': source_id}
        previous = self._layouts.get(key)
        if previous is not None:
            if any(previous[name] != row[name] for name in ('datatype', 'element_bytes', 'count', 'kind')):
                self._block(key, 'ambiguous_layout')
            return
        self._charge((key, row))
        self._layouts[key] = row

    def _array_path(self, row: dict, elements: dict, contents: dict) -> tuple[str | None, bool]:
        """Qualify array declarations even when no scalar values were exported."""
        pieces, okay, current = [], True, row
        for _ in range(160):
            attrs, name = current['attributes'], current['xml_name']
            okay &= (current['xml_namespace'] == self.base._namespace
                and current['kind'] not in {'unmodeled', 'opaque'} and not current['direct_text'].strip()
                and not any('}' in key for key in attrs)
                and not (current['kind'] in {'structure', 'structure_member', 'array', 'array_member'}
                         and 'Value' in attrs))
            if name in {'StructureMember', 'ArrayMember', 'DataValueMember'}:
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', attrs.get('Name', '')):
                    return None, False
                pieces.append('.' + attrs['Name'])
            elif name == 'Element':
                if not re.fullmatch(r'\[\s*[0-9]+(?:\s*,\s*[0-9]+)*\s*\]', attrs.get('Index', '')):
                    return None, False
                pieces.append(attrs['Index'])
            elif name not in {'Structure', 'Array', 'DataValue'}:
                return None, False
            parent = current['parent_id']
            if parent in contents:
                content = contents[parent]
                okay &= (content['owner_id'] == row['owner_id'] and content['id'] == row['content_id']
                    and content['xml_name'] == 'Data' and content['format_kind'] == 'decorated'
                    and content['xml_namespace'] == self.base._namespace and not content['direct_text'].strip()
                    and not any('}' in key for key in content['attributes']))
                path = ''.join(reversed(pieces))
                return (_key(path), bool(okay)) if len(path) <= 4096 else (None, False)
            current = elements.get(parent)
            if current is None or current['owner_id'] != row['owner_id'] or current['content_id'] != row['content_id']:
                return None, False
        return None, False

    def _build(self) -> None:
        base = self.base
        # Declaration types/dimensions are static layout facts. Saved Value
        # attributes are deliberately never read by this resolver.
        for entity in base._entities.values():
            if base._entity_ok.get(entity.id) and entity.kind in {'tag', 'aoi_parameter', 'aoi_local_tag'}:
                self._add(entity.id, '', entity.attributes.get('DataType'), entity.attributes.get('Dimensions'), entity.id)
        elements = {row['id']: row for row in base._data_evidence.elements} if base._data_evidence else {}
        contents = {row['id']: row for row in base._data_evidence.contents} if base._data_evidence else {}
        data_counts = {owner: sum(item['xml_name'] == 'Data' and item['format_kind'] == 'decorated'
                                  for item in rows) for owner, rows in base._contents.items()}
        for row in elements.values():
            if row['kind'] not in {'array', 'array_member'} or not base._entity_ok.get(row['owner_id']):
                continue
            content = contents[row['content_id']]
            if content['xml_name'] != 'Data' or content['format_kind'] != 'decorated':
                continue
            path, okay = self._array_path(row, elements, contents)
            if path is None:
                continue
            ambiguous = base._ambiguous.get((row['owner_id'], row['content_id']), set())
            if (not okay or data_counts.get(row['owner_id']) != 1
                    or any(not item or _key(item) == path or _child(_key(item), path) for item in ambiguous)):
                self._block((row['owner_id'], path), 'ambiguous_layout')
            else:
                self._add(row['owner_id'], path, row['attributes'].get('DataType'),
                          row['attributes'].get('Dimensions'), row['id'], array=True)
        for (root, _), values in base._values.items():
            if not base._entity_ok.get(root):
                continue
            for value in values:
                if value['envelope'] != 'Data' or value['format'] != 'decorated':
                    continue
                path = _key(value['path'])
                array_id = value.get('array_source_id')
                parent = elements.get(array_id) if array_id else None
                source_element = elements.get(value['element_id'])
                if parent is None and source_element and source_element['xml_name'] == 'Element':
                    candidate = elements.get(source_element['parent_id'])
                    if candidate and candidate['kind'] in {'array', 'array_member'}:
                        parent = candidate
                if parent is not None:
                    match = re.fullmatch(r'(.*)\[[^\]]*\]', path)
                    if match is None:
                        continue
                    container = match[1]
                else:
                    container = path
                key = root, container
                ambiguous = base._ambiguous.get((root, value['content_id']), set())
                if (data_counts.get(root) != 1 or value['status'] != 'qualified'
                        or any(not item or _key(item) == path or _child(_key(item), path)
                               for item in ambiguous)):
                    self._block(key, 'ambiguous_layout')
                    continue
                if parent is not None:
                    self._add(root, container, parent['attributes'].get('DataType'),
                              parent['attributes'].get('Dimensions'), parent['id'], array=True)
                elif re.search(r'\[[^\]]*\]$', path):
                    # Scalar-looking Elements without a qualified immediate
                    # array never supply independent element storage layouts.
                    self._block(key, 'unsupported_layout')
                else:
                    self._add(root, path, value.get('datatype'), None, value['element_id'])

    def _location(self, root: str, suffix: str) -> tuple[dict | None, str]:
        if self._limited:
            return None, 'metadata_limit'
        key = _key(suffix)
        direct = self._layouts.get((root, key))
        if (root, key) in self._blocked:
            return None, self._blocked[root, key]
        if direct is not None:
            if direct['kind'] == 'array':
                return None, 'array_element_required'
            return dict(direct, container_suffix=key, offset=0, capacity=direct['element_bytes']), 'fixed_range'
        match = re.fullmatch(r'(.*)\[([0-9]+)\]', key)
        if match:
            container, index = match[1], int(match[2])
            if (root, container) in self._blocked:
                return None, self._blocked[root, container]
            layout = self._layouts.get((root, container))
            if layout and layout['kind'] == 'array':
                if index >= layout['count']:
                    return None, 'invalid_index'
                return dict(layout, container_suffix=container,
                    offset=index * layout['element_bytes'], capacity=layout['count'] * layout['element_bytes']), 'fixed_range'
        return None, 'missing_layout'

    def scalar_type(self, root_id: str, suffix: str) -> str | None:
        location, _ = self._location(root_id, suffix)
        return location['datatype'] if location is not None else None

    def resolve(self, ref: dict, binding: dict) -> dict:
        descriptor = {'status': 'unresolved', 'reason': 'unsupported_instruction',
            'explanation': _EXPLANATIONS['unsupported_instruction'], 'root_id': binding.get('target_id'),
            'role': 'unknown', 'container_suffix': None, 'start_byte': None, 'end_byte': None,
            'element_bytes': None, 'datatype': None, 'length': None, 'byte_count': None}

        def fail(reason: str, operand: str | None = None) -> dict:
            label = operand or ref.get('raw_text', 'Selected operand')
            return dict(descriptor, reason=reason, explanation=f'{label}: {_EXPLANATIONS[reason]}')

        canonical = self.base._reference_uses.get(ref.get('id'))
        if canonical is None:
            return fail('unsupported_instruction')
        instruction = self.base._instructions[canonical['instruction_id']]
        opcode, slot = instruction.opcode.upper(), canonical['argument_index']
        if (len(instruction.arguments) != 3 or opcode not in {'COP', 'CPS', 'FLL'}
                or slot not in {0, 1}):
            return fail('unsupported_instruction')
        descriptor['role'] = 'read' if slot == 0 else 'write'
        length = _integer(instruction.arguments[2])
        if length is None:
            return fail('variable_length', 'Length=' + instruction.arguments[2].strip())
        descriptor['length'] = length
        rung = self.base._rungs[canonical['rung_id']]
        operands = {}
        for position in ((0, 1) if opcode in {'COP', 'CPS'} else (1,)):
            resolved = self._resolve(instruction.arguments[position].strip(), rung.scope_id)
            if resolved['status'] != 'root_bound' or not self.base._qualified(resolved, rung.id):
                return fail('unqualified_operand', instruction.arguments[position].strip())
            if position == slot and (resolved['target_id'] != binding.get('target_id')
                    or _key(resolved['suffix']) != _key(binding.get('suffix', ''))):
                return fail('unqualified_operand')
            location, reason = self._location(resolved['target_id'], resolved['suffix'])
            if location is None:
                return fail(reason, instruction.arguments[position].strip())
            operands[position] = location
        source_location = None
        if opcode == 'FLL' and not _NUMBER.fullmatch(instruction.arguments[0].strip()):
            source = self._resolve(instruction.arguments[0].strip(), rung.scope_id)
            if source['status'] != 'root_bound' or not self.base._qualified(source, rung.id):
                return fail('unqualified_operand', instruction.arguments[0].strip())
            if slot == 0 and (source['target_id'] != binding.get('target_id')
                    or _key(source['suffix']) != _key(binding.get('suffix', ''))):
                return fail('unqualified_operand')
            source_location, reason = self._location(source['target_id'], source['suffix'])
            if source_location is None:
                return fail(reason, instruction.arguments[0].strip())
        if opcode == 'FLL' and slot == 0 and source_location is None:
            return fail('unqualified_operand')
        byte_count = length * operands[1]['element_bytes']
        descriptor['byte_count'] = byte_count
        for position, row in operands.items():
            if row['offset'] + byte_count > row['capacity']:
                return fail('member_boundary', instruction.arguments[position].strip())
        selected = source_location if opcode == 'FLL' and slot == 0 else operands[slot]
        if opcode == 'FLL' and slot == 0:
            # Fill repeatedly uses one source value; Length describes the
            # destination, never that many adjacent source elements.
            byte_count = selected['element_bytes'] if length else 0
            descriptor['byte_count'] = byte_count
        descriptor.update(status='resolved', reason='fixed_range', container_suffix=selected['container_suffix'],
            start_byte=selected['offset'], end_byte=selected['offset'] + byte_count,
            element_bytes=selected['element_bytes'], datatype=selected['datatype'])
        root_name = self.base._resolver.name(self.base._entities[descriptor['root_id']])
        name = root_name + selected['container_suffix']
        if byte_count == 0:
            explanation = f'{opcode} Length=0 covers no additional elements of {name}.'
        else:
            first = selected['offset'] // selected['element_bytes']
            last = (selected['offset'] + byte_count - 1) // selected['element_bytes']
            count = last - first + 1
            address_range = (f'{name}[{first}]' + (f' through {name}[{last}]' if last != first else '')
                             if selected['kind'] == 'array' else name)
            partial = '; last element partly covered' if byte_count % selected['element_bytes'] else ''
            verb = 'reads' if descriptor['role'] == 'read' else 'writes'
            explanation = (f'{opcode} {verb} {address_range} when executed '
                f'({count} element{"s" if count != 1 else ""}, {byte_count} bytes{partial}). ')
        length_detail = (f'One source value supplies Length={length} destination elements; '
                         if opcode == 'FLL' and slot == 0 else
                         f"Length={length} x {operands[1]['element_bytes']} destination bytes; ")
        descriptor['explanation'] = explanation + length_detail + (
            f"byte offsets {descriptor['start_byte']} to {descriptor['end_byte']} (end excluded).")
        return descriptor

    def match(self, descriptor: dict, address: dict) -> dict:
        def result(status: str, reason: str) -> dict:
            explanation = (descriptor['explanation'] if reason == 'fixed_range' else _EXPLANATIONS[reason])
            return {'status': status, 'reason': reason, 'explanation': explanation}

        if address.get('root_id') != descriptor.get('root_id'):
            return result('excluded', 'different_root')
        if descriptor['status'] != 'resolved':
            return {'status': 'unresolved', 'reason': descriptor['reason'], 'explanation': descriptor['explanation']}
        if descriptor['byte_count'] == 0:
            return result('excluded', 'zero_length')
        key, container = _key(address['suffix']), descriptor['container_suffix']
        layout = self._layouts.get((address['root_id'], container))
        if not layout:
            return result('unresolved', 'missing_layout')
        if _child(key, container):
            return result('unresolved', 'containing_object')
        tail = key[len(container):] if key.startswith(container) else None
        if layout['kind'] == 'array':
            match = re.fullmatch(r'\[([0-9]+)\](?:\.([0-9]+))?', tail or '')
            if not match:
                return result('unresolved', 'containing_object') if key == container else result(
                    'unresolved' if _child(container, key) else 'excluded',
                    'unmodeled_member' if _child(container, key) else 'outside_range')
            index, bit = int(match[1]), int(match[2]) if match[2] is not None else None
            if index >= layout['count']:
                return result('excluded', 'outside_range')
            start = index * layout['element_bytes']
        else:
            match = re.fullmatch(r'(?:\.([0-9]+))?', tail or '') if tail is not None else None
            if not match:
                return result('unresolved' if _child(container, key) else 'excluded',
                    'unmodeled_member' if _child(container, key) else 'outside_range')
            bit = int(match[1]) if match[1] is not None else None
            start = 0
        width = layout['element_bytes']
        if bit is not None:
            if layout['datatype'] not in _INTEGER_TYPES or bit >= 8 * width:
                return result('unresolved', 'unmodeled_member')
            start, width = start + bit // 8, 1
        included = start < descriptor['end_byte'] and descriptor['start_byte'] < start + width
        return result('included' if included else 'excluded', 'fixed_range' if included else 'outside_range')
