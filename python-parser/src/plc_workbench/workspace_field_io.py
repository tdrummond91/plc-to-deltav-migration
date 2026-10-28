"""Read-only module and field-address evidence from an authenticated saved run.

Catalog classification describes a declared module, not a verified installed
device. A member spelling/type alone never establishes a physical I/O point.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import re
from typing import Any

from .access import _EXTENDED_ROLES, _ROLES as _ACCESS_ROLES
from .references import _ADDRESS, _binding, _literal
from .module_catalog import CATALOG_TYPES, lookup_catalog
from .workspace_evidence import diagnostic
from .workspace_io_comments import IOCommentError, collect_io_annotations, select_description
from .workspace_sorting import natural_key
from .workspace_variables import VariableIndex, _member_key
from .workspace_rack_references import RackReferenceError, RackReferenceIndex

PAGE_SIZE = 24
USE_PAGE_SIZE = 12
MAX_ALIASES = 8
MAX_DETAIL = 24
MAX_ANNOTATIONS = 8
MAX_PREVIEW = 512
MAX_ADDRESSES = 100_000
# This shared index includes captured configuration/status members as well as
# signal candidates. A 44k-member export exceeds the former 32 MiB budget even
# with shared provenance. Allow a bounded desktop working set; these are
# serialized retained-content bytes, not a measurement of Python heap usage.
MAX_INDEX_BYTES = 128 * 1024 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_DIGITAL_MANUAL = 'https://literature.rockwellautomation.com/idc/groups/literature/documents/um/1756-um058_-en-p.pdf'
_ANALOG_MANUAL = 'https://literature.rockwellautomation.com/idc/groups/literature/documents/um/1756-um009_-en-p.pdf'
_POINT_LAYOUTS = {'1756-IB16': ('input', 'di', 16, 'DINT'),
                  '1756-OB16E': ('output', 'do', 16, 'DINT'),
                  '1756-IF8': ('input', 'ai', 8, 'REAL'),
                  '1756-OF8': ('output', 'ao', 8, 'REAL')}
FIELD_TYPE_REASONS = ('exact_vendor_catalog', 'source_unqualified', 'missing_catalog',
                      'unsupported_vendor', 'user_defined_catalog', 'unsupported_catalog')
FIELD_TYPES = ('di', 'do', 'ai', 'ao', 'mixed', 'non_field', 'unknown')
MODULE_ROLES = ('field_io', 'controller', 'communication', 'unknown')
_DIRECTIONS = {'module_input_tag': 'input', 'module_output_tag': 'output',
               'module_config_tag': 'configuration'}
_LIMITATIONS = (
    'Catalog classes describe qualified module declarations in this export; installed equipment and field wiring are not verified.',
    'Controller input/output data can contain status, echo, diagnostics, or configuration. Those members are not automatically physical points.',
    'BOOL/REAL types, tag names, and channel-like member names do not establish DI/DO/AI/AO or terminal assignments.',
    'Documented member indexes are not wiring verification. Analog configuration, enabled channels, electrical modes, scaling, and installed terminal blocks are not evaluated.',
    'Rung links show possible explicit uses, not execution order, energized outputs, live readings, or complete external use.',
    'Qualified rack references retain their actual backing source paths; remaining unresolved and dynamic references can leave uses incomplete.',
    'Grouping a card selects its module declaration. Grouping a backing tag covers all its members, not one physical channel.',
)


class FieldIOError(ValueError):
    """Fixed source-free projection or selection failure."""

    def __init__(self, message: str, *, reason: str = 'invalid_evidence',
                 actual: int | None = None, limit: int | None = None) -> None:
        super().__init__(message)
        self.diagnostic = diagnostic('field_io', reason, actual, limit)


def _invalid(reason: str = 'invalid_evidence', *, actual: int | None = None,
             limit: int | None = None) -> None:
    raise FieldIOError('Saved field I/O evidence is inconsistent or exceeds its limits.',
                       reason=reason, actual=actual, limit=limit) from None


def _page(rows: list, page: int, size: int = PAGE_SIZE) -> dict:
    pages = max(1, (len(rows) + size - 1) // size)
    page = min(page, pages)
    return {'items': rows[(page - 1) * size:page * size], 'total': len(rows),
            'page': page, 'pages': pages, 'page_size': size}


def _preview(row: dict) -> dict:
    """Only presentation strings are shortened; identities remain canonical."""
    result = {}
    for key, value in row.items():
        if isinstance(value, str) and len(value) > MAX_PREVIEW and not key.endswith('_id') and key != 'id':
            result[key], result[key + '_truncated'] = value[:MAX_PREVIEW], True
        elif isinstance(value, dict):
            result[key] = _preview(value)
        elif isinstance(value, list):
            result[key] = [_preview(item) if isinstance(item, dict) else item for item in value]
        else:
            result[key] = value
    return result


def validate_query(query: dict) -> dict:
    result = {}
    for key, limit in (('run_id', 256), ('module_id', 256), ('address_id', 256), ('query', 256)):
        value = query.get(key, '')
        if (type(value) is not str or len(value) > limit or key == 'run_id' and not value
                or any(ord(char) < 32 or ord(char) == 127 for char in value)):
            raise FieldIOError('Choose a captured run and bounded field I/O filters.')
        result[key] = value
    for key, allowed in (('field_type', {'', *FIELD_TYPES}),
                         ('direction', {'', 'input', 'output', 'configuration'})):
        value = query.get(key, '')
        if type(value) is not str or value not in allowed:
            raise FieldIOError('Choose an available field I/O filter.')
        result[key] = value
    for key in ('page', 'signal_page', 'use_page'):
        value = query.get(key, '1')
        if type(value) not in {int, str} or not re.fullmatch(r'[1-9][0-9]{0,5}', str(value)):
            raise FieldIOError('Choose a positive bounded field I/O page.')
        result[key] = int(value)
    if result['address_id'] and not result['module_id']:
        raise FieldIOError('Choose a module before selecting a field address.')
    return result


def unavailable() -> dict:
    return {'available': False,
        'notice': 'Saved field I/O evidence is missing or could not be verified. Original source remains available.',
        'snapshot_id': None, 'modules': _page([], 1), 'selected_module': None,
        'addresses': _page([], 1), 'coverage': {}, 'limitations': list(_LIMITATIONS)}


def reference_binding(base: VariableIndex, ref: dict, access: dict | None = None) -> dict:
    """Resolve source presence without inventing instruction access semantics.

    Authenticated extended access may bind a slot the older reference catalog
    did not support. Otherwise a complete lexical address in an unsupported
    instruction/arity is still a source reference, with an unknown read/write
    role. Labels, selectors, literals and known pseudo-fields remain non-data.
    All returned records are detached from the saved evidence.
    """
    instruction = base._instructions[ref['instruction_id']]
    opcode, slot, text = instruction.opcode.upper(), ref['argument_index'], ref['raw_text'].strip()
    roles = _EXTENDED_ROLES.get(opcode, _ACCESS_ROLES.get(opcode, ()))
    if (opcode in {'JMP', 'LBL'} or opcode == 'JSR' and slot == 0
            or slot < len(roles) and roles[slot] == 'non_data'):
        return dict(ref, **_binding('non_data'))
    if access and access['binding_status'] in {'root_bound', 'non_data', 'literal', 'system_flag'}:
        return dict(ref, **{key: access[key] for key in ('symbol_id', 'target_id', 'suffix')},
                    alias_chain=list(access.get('alias_chain', ref.get('alias_chain', []))),
                    status=access['binding_status'])
    if ref['status'] not in {'unsupported_instruction', 'argument_count_mismatch'}:
        return dict(ref)
    if _literal(text):
        return dict(ref, **_binding('literal'))
    # The exported system flag is not a project symbol, even when malformed
    # instruction arity prevents the historical catalog from identifying it.
    if text.upper() == 'S:FS':
        return dict(ref, **_binding('system_flag'))
    rung = base._rungs[ref['rung_id']]
    return dict(ref, **base._resolve(text, rung.scope_id))


class FieldIOIndex:
    """A bounded projection sharing the workspace's authenticated variable index."""

    def __init__(self, evidence: VariableIndex) -> None:
        if type(evidence) is not VariableIndex:
            _invalid()
        self.base = evidence
        self.modules: dict[str, dict] = {}
        self.addresses: dict[str, dict] = {}
        self.by_module: dict[str, list[str]] = defaultdict(list)
        self.roots: dict[str, list[dict]] = defaultdict(list)
        self.ports: dict[str, list[dict]] = defaultdict(list)
        self.rack_aliases: dict[str, list[dict]] = defaultdict(list)
        self._root_module: dict[str, str] = {}
        self._keys: dict[tuple[str, str], str] = {}
        self._search: dict[str, str] = {}
        self.annotation_texts: dict[str, str] = {}
        self._annotation_records: dict[tuple[str, str], dict] = {}
        self._description_candidates: dict[str, list[tuple[str, str, str]]] = {}
        self._budget = 0
        self._omitted = 0
        try:
            self._build()
        except FieldIOError:
            raise
        except RackReferenceError as exc:
            _invalid('index_bytes_limit' if exc.limit is not None else 'invalid_evidence',
                     actual=exc.actual, limit=exc.limit)
        except IOCommentError as exc:
            error = FieldIOError('Saved field I/O evidence is inconsistent or exceeds its limits.')
            error.diagnostic = diagnostic(exc.diagnostic['stage'], exc.diagnostic['reason'],
                                          exc.diagnostic.get('actual'), exc.diagnostic.get('limit'))
            raise error from None
        except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
            _invalid('projection_failed')

    def _retain(self, value: Any) -> None:
        self._budget += len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self._budget > MAX_INDEX_BYTES:
            _invalid('index_bytes_limit', actual=self._budget, limit=MAX_INDEX_BYTES)

    def _add(self, root_id: str, suffix: str) -> dict | None:
        if (root_id not in self._root_module or not self.base._entity_ok.get(root_id)
                or not isinstance(suffix, str) or len(suffix) > 4096 or not _ADDRESS.fullmatch('A' + suffix)):
            self._omitted += 1
            return None
        key = root_id, _member_key(suffix)
        if key in self._keys:
            return self.addresses[self._keys[key]]
        if len(self.addresses) >= MAX_ADDRESSES:
            _invalid('address_count_limit', actual=len(self.addresses) + 1, limit=MAX_ADDRESSES)
        entity = self.base._entities[root_id]
        name = self.base._resolver.name(entity)
        if not name or len(name) > 4096:
            self._omitted += 1
            return None
        module_id = self._root_module[root_id]
        if not self.modules[module_id]['qualified']:
            return None
        identifier = 'field_address_' + hashlib.sha256((root_id + '\0' + key[1]).encode()).hexdigest()
        row = {'id': identifier, 'root_id': root_id, 'root_name': name,
            'root_name_origin': self.base._resolver.names[root_id]['name_origin'],
            'suffix': suffix, 'address': name + suffix, 'direction': _DIRECTIONS[entity.kind],
            'field_type': 'unknown', 'point_status': 'unresolved', 'channel': None,
            'point_basis': None, 'point_reference': None, 'channel_status': 'unresolved',
            'configuration_status': 'not_evaluated',
            # Source prose is selected below from qualified annotations. Do not
            # duplicate (or charge) a transient root description on every member.
            'datatype': None, 'description': None, 'description_basis': 'backing_declaration',
            'aliases': [], 'uses': [],
            'source_annotations': [],
            'group_member_ids': [root_id], 'grouping_scope': 'backing_declaration'}
        self._retain(row)
        self.addresses[identifier] = row
        self._keys[key] = identifier
        self.by_module[module_id].append(identifier)
        return row

    def _build(self) -> None:
        base, entities = self.base, self.base._entities
        self.rack_references = RackReferenceIndex(base)
        self._budget += self.rack_references._budget
        rack_initial_budget = self.rack_references._budget
        self._retain({})
        children: dict[str, list] = defaultdict(list)
        names: dict[tuple[str | None, str], list] = defaultdict(list)
        for entity in entities.values():
            children[entity.parent_id].append(entity)
            if entity.kind == 'module' and entity.name:
                names[entity.scope_id, entity.name.lower()].append(entity)
        for entity in entities.values():
            if entity.kind != 'module':
                continue
            attrs, okay = entity.attributes, bool(base._entity_ok.get(entity.id))
            catalog = attrs.get('CatalogNumber')
            catalog_record = None
            # One first-gap reason per module keeps the census disjoint. An
            # empty user-defined override is still an authored override;
            # neither identity values nor catalog spellings are normalized.
            if not okay:
                type_reason = 'source_unqualified'
            elif not catalog or not catalog.strip():
                type_reason = 'missing_catalog'
            elif attrs.get('Vendor') != '1':
                type_reason = 'unsupported_vendor'
            elif 'UserDefinedCatalogNumber' in attrs:
                type_reason = 'user_defined_catalog'
            else:
                catalog_record = lookup_catalog(catalog, attrs.get('Vendor'))
                type_reason = 'exact_vendor_catalog' if catalog_record else 'unsupported_catalog'
            field_types = catalog_record['field_types'] if catalog_record else []
            role = catalog_record['role'] if catalog_record else 'unknown'
            field_type = (field_types[0] if len(field_types) == 1 else 'mixed' if field_types else
                          'non_field' if role in {'controller', 'communication'} else 'unknown')
            controller = entities.get(entity.scope_id)
            parent_name = attrs.get('ParentModule')
            parents = names.get((entity.scope_id, (parent_name or '').lower()), [])
            parent = parents[0] if len(parents) == 1 and base._entity_ok.get(parents[0].id) else None
            ports = [child for child in children[entity.id] if child.kind == 'module_port']
            upstream = [port for port in ports if port.attributes.get('Upstream') in {'true', '1'}]
            slot = None
            if (okay and len(upstream) == 1 and base._entity_ok.get(upstream[0].id)
                    and upstream[0].attributes.get('Type') == 'ICP'
                    and re.fullmatch(r'0|[1-9][0-9]{0,8}', upstream[0].attributes.get('Address', ''))):
                slot = upstream[0].attributes['Address']
            row = {'id': entity.id, 'name': entity.name, 'description': entity.description,
                'path': base._path(entity.id), 'controller': {'id': entity.scope_id,
                    'name': controller.name if controller else None, 'path': base._path(entity.scope_id)},
                'catalog_number': catalog, 'vendor': attrs.get('Vendor'), 'product_type': attrs.get('ProductType'),
                'parent_module_name': parent_name, 'parent_module_id': parent.id if parent else None,
                'slot': slot, 'location_status': 'declared_upstream_ICP_address' if slot is not None else 'unresolved',
                'directions': [], 'field_type': field_type,
                'field_types': field_types, 'module_role': role,
                'field_type_reason': type_reason,
                'field_type_basis': 'exact_vendor_catalog' if field_type != 'unknown' else 'unresolved',
                'catalog_description': catalog_record['description'] if catalog_record else None,
                'catalog_family': catalog_record['family'] if catalog_record else None,
                'catalog_capacity': catalog_record['capacity'] if catalog_record else {},
                'catalog_capacity_basis': catalog_record['capacity_basis'] if catalog_record else None,
                'catalog_reference': catalog_record['reference'] if catalog_record else None,
                'catalog_reference_page': catalog_record.get('reference_page') if catalog_record else None,
                'catalog_publication': catalog_record.get('publication') if catalog_record else None,
                'source_annotations': [],
                'point_count': None, 'point_count_basis': None, 'address_count': 0, 'use_count': 0,
                'rung_count': 0, 'rack_alias_count': 0, 'qualified': okay,
                'group_member_ids': [entity.id], 'grouping_scope': 'module_declaration'}
            self._retain(row)
            self.modules[entity.id] = row
            if field_type != 'unknown' and catalog in _POINT_LAYOUTS:
                row['point_count'] = _POINT_LAYOUTS[catalog][2]
                row['point_count_basis'] = ('maximum_configuration_dependent' if catalog == '1756-IF8'
                                             else 'documented_capacity')
            for port in ports:
                value = {'id': port.id, 'port_id': port.attributes.get('Id'), 'type': port.attributes.get('Type'),
                    'address': port.attributes.get('Address'), 'upstream': port.attributes.get('Upstream'),
                    'qualified': bool(base._entity_ok.get(port.id))}
                self._retain(value)
                self.ports[entity.id].append(value)
        for entity in entities.values():
            if entity.kind not in _DIRECTIONS and entity.kind not in {'module_rack_input_alias', 'module_rack_output_alias'}:
                continue
            parent = entities.get(entity.parent_id)
            module_id = parent.parent_id if parent and parent.kind in {'module_connection', 'module_rack_connection'} else entity.parent_id
            if module_id not in self.modules:
                continue
            if entity.kind in _DIRECTIONS:
                provenance = base._resolver.names[entity.id]
                self._root_module[entity.id] = module_id
                value = {'id': entity.id, 'name': provenance['name'], 'kind': entity.kind,
                    'direction': _DIRECTIONS[entity.kind], 'name_origin': provenance['name_origin'],
                    'name_reason': provenance['reason'], 'description': entity.description,
                    'datatype': entity.attributes.get('DataType'), 'qualified': bool(base._entity_ok.get(entity.id))}
                self._retain(value)
                self.roots[module_id].append(value)
                self._add(entity.id, '')
            else:
                value = {'id': entity.id, 'kind': entity.kind, 'alias_for': entity.attributes.get('AliasFor'),
                    'description': entity.description, 'status': 'backing_unresolved',
                    'qualified': bool(base._entity_ok.get(entity.id))}
                if entity.id in self.rack_references.roots:
                    rack = self.rack_references.roots[entity.id]
                    value.update(status='qualified_backing_source', backing_tag_id=rack['backing_tag_id'],
                                 backing_prefix=rack['backing_prefix'], logical_root=rack['logical_root'])
                self._retain(value)
                self.rack_aliases[module_id].append(value)
        access = {row['id']: row for row in base._access.operands} if base._access else {}
        for ref in base._references.operands:
            # Keep the legacy materialization order/spelling for persisted
            # signal bindings. Newly recovered uses are added only after all
            # previously indexed uses, aliases, values and comments below.
            if (ref['status'] != 'root_bound' or ref['target_id'] not in self._root_module
                    or not base._qualified(ref, ref['rung_id'])):
                continue
            legacy_row = self._add(ref['target_id'], ref['suffix'])
            binding = reference_binding(base, ref, access.get(ref['id']))
            if binding['status'] != 'root_bound' or binding['target_id'] not in self._root_module:
                continue
            if not base._qualified(binding, ref['rung_id']):
                continue
            row = (legacy_row if (binding['target_id'], binding['suffix']) == (ref['target_id'], ref['suffix'])
                   else self._add(binding['target_id'], binding['suffix']))
            if row is not None:
                self._use(row, ref, access.get(ref['id'], {}).get('role', 'unknown'), ref['raw_text'])
        if base._access:
            for use in base._access.expression_uses:
                if (use['binding_status'] == 'root_bound' and use['target_id'] in self._root_module
                        and base._qualified(use, use['rung_id'])):
                    row = self._add(use['target_id'], use['suffix'])
                    if row is not None:
                        self._use(row, use, use['role'], row['address'])
        io_aliases = []
        recovered_aliases = []
        for alias in base._references.aliases:
            ids = [alias['source_id'], alias.get('target_id'), *alias.get('alias_chain', [])]
            if alias['status'] != 'root_bound':
                recovered = self.rack_references.resolve(alias, alias['raw_target'], alias['scope_id'])
                if recovered and base._entity_ok.get(alias['source_id']):
                    recovered_aliases.append((alias, recovered))
            if (alias['status'] != 'root_bound' or alias['target_id'] not in self._root_module
                    or not all(base._entity_ok.get(identifier) for identifier in ids)):
                continue
            io_aliases.append(alias)
            row = self._add(alias['target_id'], alias['suffix'])
            if row is not None:
                entity = entities[alias['source_id']]
                value = _preview({'id': entity.id, 'name': entity.name, 'path': base._path(entity.id),
                                  'description': entity.description})
                self._retain(value)
                row['aliases'].append(value)
        for (owner_id, _), values in base._values.items():
            if owner_id not in self._root_module:
                continue
            for value in values:
                if value['status'] == 'qualified':
                    self._add(owner_id, value['path'])
        annotation_owners = set(self.modules) | set(self._root_module)
        annotation_owners.update(alias['source_id'] for alias in io_aliases)
        annotation_owners.update(alias['source_id'] for alias, _ in recovered_aliases)
        annotations = collect_io_annotations(base._source, base._captured, base._entity_ok,
                                             owner_ids=annotation_owners)
        by_owner: dict[str, list[tuple[str, list[dict]]]] = defaultdict(list)
        for (owner_id, suffix), notes in annotations.items():
            by_owner[owner_id].append((suffix, notes))
            if owner_id in self.modules and not suffix:
                self._annotations(self.modules[owner_id], notes, 'module')
            elif owner_id in self._root_module:
                address = self._add(owner_id, suffix)
                if address is not None:
                    self._annotations(address, notes, 'backing_declaration')
        for alias in io_aliases:
            for suffix, notes in by_owner[alias['source_id']]:
                address = self._add(alias['target_id'], alias['suffix'] + suffix)
                if address is not None:
                    self._annotations(address, notes, 'alias')
        for ref in base._references.operands:
            if ref['status'] == 'root_bound':
                continue
            binding = reference_binding(base, ref, access.get(ref['id']))
            if (binding['status'] != 'root_bound' or binding['target_id'] not in self._root_module
                    or not base._qualified(binding, ref['rung_id'])):
                continue
            row = self._add(binding['target_id'], binding['suffix'])
            if row is not None:
                self._use(row, ref, access.get(ref['id'], {}).get('role', 'unknown'), ref['raw_text'])
        # Append newly recovered rack addresses only after all legacy anchors
        # above are materialized. Their actual backing root/suffix remains the
        # stable identity; logical card/address evidence is a separate overlay.
        for alias, recovered in recovered_aliases:
            row = self._rack_address(recovered)
            if row is None:
                continue
            entity = entities[alias['source_id']]
            value = _preview({'id': entity.id, 'name': entity.name, 'path': base._path(entity.id),
                              'description': entity.description})
            self._retain(value)
            row['aliases'].append(value)
            for suffix, notes in by_owner[alias['source_id']]:
                # Member comments require their own validated logical member;
                # never blindly attach arbitrary alias comment suffixes.
                binding = dict(alias, suffix=alias['suffix'] + suffix)
                note_target = self.rack_references.resolve(binding, alias['raw_target'], alias['scope_id'])
                target = self._rack_address(note_target) if note_target else None
                if target is not None:
                    self._annotations(target, notes, 'alias')
        self._rack_recovered_uses = 0
        for ref in base._references.operands:
            rung = base._rungs[ref['rung_id']]
            if not base._rung_ok.get(rung.id):
                continue
            binding = reference_binding(base, ref, access.get(ref['id']))
            recovered = self.rack_references.resolve(binding, ref['raw_text'], rung.scope_id)
            if recovered:
                self._rack_use(ref, recovered, access.get(ref['id'], {}).get('role', 'unknown'), ref['raw_text'])
        if base._access:
            for use in base._access.expression_uses:
                rung = base._rungs[use['rung_id']]
                if not base._rung_ok.get(rung.id):
                    continue
                expression = base._reference_uses[use['expression_operand_id']]
                raw = expression['raw_text'][use['start']:use['end']]
                binding = dict(use, status=use['binding_status'], reason=use['binding_reason'])
                recovered = self.rack_references.resolve(binding, raw, rung.scope_id)
                if recovered:
                    # The authenticated calculation leaf owns the occurrence.
                    # Never substitute the whole expression or manufacture a
                    # root occurrence by searching unparsed expression text.
                    self._rack_use(use, recovered, use['role'], raw)
        self._budget += self.rack_references._budget - rack_initial_budget
        self._retain({})
        for row in self.addresses.values():
            self._select_description(row)
            values = base._values.get((row['root_id'], _member_key(row['suffix'])), [])
            types = {value['datatype'] for value in values if value['status'] == 'qualified' and value['datatype']}
            row['datatype'] = next(iter(types)) if len(types) == 1 else row.get('rack_datatype')
            self._point(row)
        for identifier, module in self.modules.items():
            self._select_description(module)
            self.by_module[identifier].sort(key=lambda key: (
                self.addresses[key]['channel'] is None, self.addresses[key]['direction'],
                self.addresses[key]['channel'] if self.addresses[key]['channel'] is not None else -1,
                natural_key(self.addresses[key]['address']), key))
            rows = [self.addresses[key] for key in self.by_module[identifier]]
            module.update(directions=sorted({row['direction'] for row in self.roots[identifier]
                                             if row['qualified'] and module['qualified']}),
                address_count=len(rows), use_count=sum(len(row['uses']) for row in rows),
                point_mapped_address_count=sum(row['channel'] is not None for row in rows),
                rung_count=len({use['rung_id'] for row in rows for use in row['uses']}),
                rack_alias_count=len(self.rack_aliases[identifier]))
            search_parts = [str(value) for value in [module['name'], module['description'], module['catalog_number'],
                module['controller']['name'], module['parent_module_name'], module['slot'], module['catalog_description']]]
            for row in rows:
                search_parts.extend([row['address'], *[str(alias.get(key) or '')
                    for alias in row['aliases'] for key in ('name', 'description')]])
                search_parts.extend(self.annotation_texts[note['id']] for note in row['source_annotations'])
            search_parts.extend(self.annotation_texts[note['id']] for note in module['source_annotations'])
            text = ' '.join(search_parts)
            self._retain(text)
            self._search[identifier] = text.casefold()
        counts = Counter(row['field_type'] for row in self.modules.values())
        reasons = Counter(row['field_type_reason'] for row in self.modules.values())
        roles = Counter(row['module_role'] for row in self.modules.values())
        self.coverage = {'modules_total': len(self.modules),
            'qualified_modules': sum(row['qualified'] for row in self.modules.values()),
            'modules_by_field_type': {kind: counts[kind] for kind in FIELD_TYPES},
            'modules_by_filter': {kind: sum(self._matches_type(row, kind) for row in self.modules.values())
                                  for kind in FIELD_TYPES},
            'modules_by_role': {role: roles[role] for role in MODULE_ROLES},
            'field_filter_counts_overlap': True,
            'modules_by_field_type_reason': {reason: reasons[reason] for reason in FIELD_TYPE_REASONS},
            'module_type_counts_scope': 'all_captured_modules',
            'addresses_total': len(self.addresses),
            'point_mapped_addresses': sum(row['channel'] is not None for row in self.addresses.values()),
            'rung_uses_total': sum(row['use_count'] for row in self.modules.values()),
            'rack_aliases_unresolved': sum(row['status'] == 'backing_unresolved'
                                          for rows in self.rack_aliases.values() for row in rows),
            'unresolved_reference_operands_in_run': sum(row['status'] in {'unresolved', 'ambiguous',
                'unsupported_address', 'alias_cycle', 'alias_depth_limit'} for row in base._references.operands),
            'omitted_addresses': self._omitted}
        self.coverage['rack_recovered_reference_uses'] = self._rack_recovered_uses
        self.coverage['rack_recovered_addresses'] = sum('rack_mapping' in row for row in self.addresses.values())

    def _rack_address(self, recovered: dict) -> dict | None:
        row = self._add(recovered['target_id'], recovered['suffix'])
        if row is not None and 'rack_mapping' not in row:
            self._retain(recovered['rack_mapping'])
            row['rack_mapping'] = recovered['rack_mapping']
            row['rack_datatype'] = recovered['datatype']
        return row

    def _rack_use(self, use: dict, recovered: dict, role: str, raw: str) -> None:
        row = self._rack_address(recovered)
        if row is None:
            return
        self._use(row, use, role, raw)
        mapping = row['rack_mapping']
        provenance = {'binding_basis': mapping['basis'],
                      'logical_address': mapping['logical_address'], 'backing_address': row['address']}
        self._retain(provenance)
        row['uses'][-1].update(provenance)
        self._rack_recovered_uses += 1

    @staticmethod
    def _matches_type(row: dict, kind: str) -> bool:
        return not kind or kind in row['field_types'] or row['field_type'] == kind

    def _annotations(self, target: dict, notes: list[dict], via: str) -> None:
        for note in notes:
            key = note['id'], via
            row = self._annotation_records.get(key)
            if row is None:
                owner = self.base._entities[note['owner_id']]
                row = _preview(dict(note, owner_name=owner.name, owner_path=self.base._path(owner.id), via=via))
                self._retain((key, row))
                self._annotation_records[key] = row
            # The row and full text are owned once; targets retain references.
            self._retain(key)
            target['source_annotations'].append(row)
            if note['id'] not in self.annotation_texts:
                self._retain(note['text'])
                self.annotation_texts[note['id']] = note['text']

    def _select_description(self, row: dict) -> None:
        """Keep exact annotations apart from explicit backing/module fallbacks."""
        candidates = []
        is_address = 'root_id' in row
        for note in row['source_annotations']:
            scope = ('exact_member_comment' if note['kind'] == 'member_comment' else
                     'exact_alias_description' if note['via'] == 'alias' and row.get('suffix') else
                     'backing_alias_description' if note['via'] == 'alias' else
                     'module_description' if note['via'] == 'module' else 'backing_description')
            candidates.append(dict(note, description_scope=scope))
        if is_address:
            root_key = self._keys.get((row['root_id'], ''))
            root = self.addresses.get(root_key) if root_key else None
            if root is not None and root is not row:
                candidates.extend(dict(note, description_scope=('backing_alias_description'
                    if note['via'] == 'alias' else 'backing_description'))
                    for note in root['source_annotations'])
            module = self.modules[row.get('rack_mapping', {}).get('module_id')
                                  or self._root_module[row['root_id']]]
            candidates.extend(dict(note, description_scope='module_description')
                              for note in module['source_annotations'])
        selection = select_description(candidates, text_lookup=self.annotation_texts)
        # Full candidate origins repeat the same annotation/owner/module
        # metadata on thousands of members. Retain their exact identities and
        # scopes, then expand only the requested page or downstream projection.
        origins = [(note['id'], note['via'], note['description_scope'])
                   for note in selection.pop('candidates')]
        self._description_candidates[row['id']] = origins
        self._retain((row['id'], origins))
        row['description_selection'] = selection
        row['description_basis'] = selection['basis']
        identifier = selection['preferred_annotation_id']
        if identifier:
            text = self.annotation_texts[identifier]
            row['description'] = text[:MAX_PREVIEW]
            row['description_truncated'] = len(text) > MAX_PREVIEW
        else:
            row['description'] = None
        self._retain(selection)
        self._retain(row['description'])

    def description_selection(self, row: dict) -> dict:
        """Return independent public provenance from compact exact references."""
        selection = deepcopy(row['description_selection'])
        selection['candidates'] = [dict(
            {key: value for key, value in self._annotation_records[identifier, via].items() if key != 'text'},
            description_scope=scope)
            for identifier, via, scope in self._description_candidates[row['id']]]
        return selection

    def _annotation_preview(self, row: dict) -> dict:
        notes = row['source_annotations']
        return dict(row, source_annotations=notes[:MAX_ANNOTATIONS], source_annotations_total=len(notes),
                    source_annotations_truncated=len(notes) > MAX_ANNOTATIONS,
                    description_selection=self.description_selection(row))

    def _point(self, row: dict) -> None:
        """Only four documented profiles; no generic datatype/channel guessing.

        UM058L tables 44/49 and p157 distinguish input state/output command
        Data bits from table48 output echo. UM009G pp130-131 distinguish I/O
        Ch0Data from input-side output echo and retain mode uncertainty.
        """
        mapping = row.get('rack_mapping', {})
        module = self.modules[mapping.get('module_id') or self._root_module[row['root_id']]]
        layout = _POINT_LAYOUTS.get(module['catalog_number'])
        if module['field_type'] == 'unknown' or layout is None:
            return
        direction, kind, count, datatype = layout
        if row['direction'] != direction:
            return
        digital = kind in {'di', 'do'}
        match = re.fullmatch(r'\.Data\.(0|[1-9][0-9]?)' if digital else r'\.Ch(0|[1-9][0-9]?)Data',
                             mapping.get('logical_suffix', row['suffix']), re.ASCII | re.IGNORECASE)
        if match is None or int(match[1]) >= count:
            return
        suffix = ((row['suffix'][:-len(mapping['logical_suffix'])] + '.Data')
                  if digital and mapping else '.Data' if digital else row['suffix'])
        key = _member_key(suffix)
        values = [value for value in self.base._values.get((row['root_id'], key), [])
                  if value['envelope'] == 'Data' and value['format'] == 'decorated']
        if len(values) != 1 or values[0]['status'] != 'qualified' or values[0]['datatype'] != datatype:
            return
        if any(gap == '' or key == gap or key.startswith(gap + '.') or key.startswith(gap + '[')
               for gap in self.base._ambiguous.get((row['root_id'], values[0]['content_id']), ())):
            return
        contents = [value for value in self.base._contents[row['root_id']]
                    if value['xml_name'] == 'Data' and value['format_kind'] == 'decorated']
        if len(contents) != 1:
            return
        row.update(field_type=kind, point_status='documented_member_layout', channel=int(match[1]),
            point_basis='exact_catalog_direction_member_and_captured_profile_type',
            point_reference=_DIGITAL_MANUAL if digital else _ANALOG_MANUAL,
            channel_status='documented_member_index_not_wiring',
            configuration_status='input_mode_unresolved' if module['catalog_number'] == '1756-IF8' else 'not_evaluated')

    def _use(self, address: dict, use: dict, role: str, variable: str) -> None:
        rung = self.base._rungs[use['rung_id']]
        instruction = self.base._instructions[use['instruction_id']]
        row = _preview({'id': use['id'], 'instruction_id': instruction.id, 'rung_id': rung.id,
            'opcode': instruction.opcode, 'role': role, 'variable': variable,
            'path': self.base._path(rung.parent_id) + ' / Rung ' + str(rung.number), 'rung_number': rung.number})
        self._retain(row)
        address['uses'].append(row)

    def view(self, query: dict) -> dict:
        selected = query['module_id']
        if selected and selected not in self.modules:
            raise FieldIOError('Choose a module captured in this run.')
        rows = [row for row in self.modules.values()
            if self._matches_type(row, query['field_type'])
            and (not query['direction'] or query['direction'] in row['directions'])
            and (not query['query'] or query['query'].casefold() in self._search[row['id']])]
        rows.sort(key=lambda row: (natural_key(row['controller']['name']), natural_key(row['name']), row['id']))
        modules = _page(rows, query['page'])
        modules['items'] = [self._annotation_preview(row) for row in modules['items']]
        detail = None
        addresses = _page([], query['signal_page'])
        if selected:
            detail = self._annotation_preview(self.modules[selected])
            for key, values in (('ports', self.ports[selected]), ('roots', self.roots[selected]),
                                ('rack_aliases', self.rack_aliases[selected])):
                detail[key] = values[:MAX_DETAIL]
                detail[key + '_total'] = len(values)
                detail[key + '_truncated'] = len(values) > MAX_DETAIL
            values = [self.addresses[key] for key in self.by_module[selected]]
            if query['address_id']:
                if query['address_id'] not in self.by_module[selected]:
                    raise FieldIOError('Choose an address captured on this module.')
                values = [self.addresses[query['address_id']]]
            addresses = _page(values, query['signal_page'])
            addresses['items'] = [dict(self._annotation_preview(row), aliases=row['aliases'][:MAX_ALIASES],
                aliases_total=len(row['aliases']), aliases_truncated=len(row['aliases']) > MAX_ALIASES,
                uses=(uses := _page(row['uses'], query['use_page'], USE_PAGE_SIZE))['items'],
                uses_total=uses['total'], use_page=uses['page'], use_pages=uses['pages'])
                for row in addresses['items']]
        limitations = list(_LIMITATIONS)
        if not self.base._has_access:
            limitations.append('Saved instruction-access evidence is absent; explicit reference roles remain unknown.')
        if not self.base._has_data:
            limitations.append('Saved tag-data evidence is absent; unused stored members are not listed.')
        result = _preview({'available': True,
            'notice': 'Module catalog classes and exact exported addresses; field wiring and installed devices require confirmation.',
            'snapshot_id': self.base._captured.snapshot['id'], 'modules': modules,
            'selected_module': detail, 'addresses': addresses, 'coverage': self.coverage, 'limitations': limitations})
        if len(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) > MAX_RESPONSE_BYTES:
            _invalid()
        return deepcopy(result)
