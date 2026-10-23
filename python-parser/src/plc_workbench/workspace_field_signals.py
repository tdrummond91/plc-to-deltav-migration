"""Bounded channel-address projection and optional, one-hop logic suggestions.

Rows are captured module members, never a module's advertised capacity expanded
into invented wired points. Related rungs share an explicit address; neither
execution, scaling, alarm consequence nor package membership is inferred.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import re
from typing import Any

from .rung_analysis import _FAMILIES
from .workspace_connections import ConnectionIndex
from .workspace_field_io import FieldIOIndex, _page, _preview
from .workspace_variables import _member_key
from .workspace_paging import page_size

PAGE_SIZE = 24
DETAIL_PAGE_SIZE = 12
MAX_PREVIEW_ITEMS = 8
MAX_SIGNALS = 100_000
MAX_INDEX_BYTES = 24 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_DIRECT_EXPANSION = 32
MAX_BRIDGES = 128
MAX_BRIDGE_FANOUT = 64
MAX_RELATED = 256
MAX_RELATED_PATHS = 4
MAX_SAVED_SEARCH_CHARS = 8 * 1024 * 1024
FIELD_TYPES = ('di', 'do', 'ai', 'ao')
_DIRECTION_TYPES = {'input': ('di', 'ai'), 'output': ('do', 'ao')}
# These spellings are review candidates only. This does not add a device profile
# or assign a physical channel number to an unverified member layout.
_CANDIDATE_MEMBER = re.compile(
    r'(?:\.Data\.(?:0|[1-9][0-9]{0,3})|\.Ch(?:0|[1-9][0-9]{0,3})Data'
    r'|\.Ch(?:0|[1-9][0-9]{0,3})\.Data|\.Data\[(?:0|[1-9][0-9]{0,3})\]'
    r'|\.Channel\[(?:0|[1-9][0-9]{0,3})\]\.Data)', re.ASCII | re.IGNORECASE)
_LIMITATIONS = (
    'Rows identify captured module addresses, not verified field wiring or installed devices.',
    'Review-mapping candidates retain unknown type and channel; catalog or qualified channel datatype/direction can suggest a field category to review.',
    'No rows are invented from catalog capacity. Missing rows can mean absent member evidence or an unsupported member layout.',
    'Exact member aliases share one source identity. Whole-word, array-range, dynamic-index and implicit instruction effects are not expanded.',
    'Related rungs are optional one-hop shared-address candidates. They do not prove dataflow, execution order, scaling, shutdown behavior or package membership.',
)


class FieldSignalError(ValueError):
    """Source-free invalid projection or query error."""


def _invalid() -> None:
    raise FieldSignalError('Saved field signal evidence is inconsistent or exceeds its limits.') from None


def validate_query(query: dict) -> dict:
    if type(query) is not dict:
        raise FieldSignalError('Choose valid field signal filters.')
    result: dict[str, Any] = {}
    for key, limit in (('run_id', 256), ('signal_id', 256), ('module_id', 256), ('query', 256)):
        value = query.get(key, '')
        if (type(value) is not str or len(value) > limit or key == 'run_id' and not value
                or any(ord(char) < 32 or ord(char) == 127 for char in value)):
            raise FieldSignalError('Choose a captured run and bounded field signal filters.')
        result[key] = value
    for key, default, allowed in (('section', 'all', {'all', 'signals', 'candidates'}),
                                  ('field_type', '', {'', 'unknown', *FIELD_TYPES})):
        value = query.get(key, default)
        if type(value) is not str or value not in allowed:
            raise FieldSignalError('Choose an available field signal filter.')
        result[key] = value
    for key in ('page', 'use_page', 'related_page', 'rung_page'):
        value = query.get(key, '1')
        if type(value) not in {int, str} or not re.fullmatch(r'[1-9][0-9]{0,5}', str(value)):
            raise FieldSignalError('Choose a positive bounded field signal page.')
        result[key] = int(value)
    result['page_size'] = page_size(query, PAGE_SIZE, error=FieldSignalError)
    result['detail_page_size'] = page_size(query, DETAIL_PAGE_SIZE, key='detail_page_size', error=FieldSignalError)
    return result


def unavailable(size: int = PAGE_SIZE) -> dict:
    return {'available': False, 'snapshot_id': None, 'signals': _page([], 1, size),
            'selected_signal': None, 'coverage': {}, 'limitations': list(_LIMITATIONS),
            'notice': 'Saved field signal evidence could not be verified. Original source remains available.'}


class FieldSignalIndex:
    """Share authenticated field/variable evidence; never rerun analysis on reads."""

    def __init__(self, field_io: FieldIOIndex, connections: ConnectionIndex | None = None) -> None:
        if type(field_io) is not FieldIOIndex or connections is not None and type(connections) is not ConnectionIndex:
            _invalid()
        self.field_io = field_io
        self.base = field_io.base
        self.snapshot_id = self.base._captured.snapshot['id']
        self.connections = connections
        self.signals: dict[str, dict] = {}
        self._search: dict[str, str] = {}
        self._direct: dict[str, dict[str, list[dict]]] = {}
        self._uses: dict[str, list[dict]] = {}
        self._budget = 0
        try:
            if connections is not None:
                # ConnectionIndex authenticates companions, but is not itself
                # tied to this source index until both captured sets match.
                if connections._rungs != self.base._rungs or connections._entities != self.base._entities:
                    _invalid()
                connections.qualify_map(self.base._entity_ok, self.base._rung_ok)
            self._build()
        except FieldSignalError:
            raise
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError, RecursionError):
            _invalid()

    def _retain(self, value: Any) -> None:
        self._budget += len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self._budget > MAX_INDEX_BYTES:
            _invalid()

    def _candidate(self, row: dict, module: dict) -> list[str] | None:
        if (row['direction'] not in _DIRECTION_TYPES or not row['suffix']
                or module['module_role'] in {'controller', 'communication'}
                or _CANDIDATE_MEMBER.fullmatch(row['suffix']) is None):
            return None
        suggested = [kind for kind in module['field_types'] if kind in _DIRECTION_TYPES[row['direction']]]
        if module['module_role'] == 'field_io' and not suggested:
            return None  # Opposite-direction data on a known card can be echo/status.
        return suggested

    def _build(self) -> None:
        excluded = Counter()
        for address in self.field_io.addresses.values():
            module_id = self.field_io._root_module[address['root_id']]
            module = self.field_io.modules[module_id]
            documented = address['point_status'] == 'documented_member_layout'
            candidates = [] if documented else self._candidate(address, module)
            if candidates is None:
                excluded['non_signal_addresses'] += 1
                continue
            if len(self.signals) >= MAX_SIGNALS:
                _invalid()
            metadata = self._source_metadata(address)
            hinted = self._analogue_hint(address, candidates or []) if not documented else address['field_type']
            if not documented and hinted != 'unknown':
                candidates = [hinted]
            status = 'documented_member_layout' if documented else 'review_mapping'
            row = {key: address[key] for key in ('id', 'root_id', 'suffix', 'address', 'direction',
                'field_type', 'channel', 'datatype', 'description', 'description_basis',
                'point_basis', 'point_reference', 'channel_status', 'configuration_status')}
            row['description_selection'] = address.get('description_selection', {})
            row['logical_signal'] = {
                'kind': 'numeric' if address['datatype'] in {'REAL', 'LREAL'} else
                        'boolean' if address['datatype'] == 'BOOL' else 'unresolved',
                'direction': address['direction'],
                'basis': 'captured_datatype_and_module_direction',
                'physical_layout_documented': documented,
            }
            row.update(module_id=module_id, source_qualified=True, mapping_status=status,
                mapping_reason=('exact_catalog_direction_member_and_captured_profile_type' if documented
                    else 'qualified_floating_channel_requires_review' if hinted != 'unknown'
                    else 'captured_member_layout_requires_review' if candidates
                    else 'captured_member_and_catalog_require_review'), candidate_field_types=candidates,
                aliases=address['aliases'][:MAX_PREVIEW_ITEMS], aliases_total=len(address['aliases']),
                aliases_truncated=len(address['aliases']) > MAX_PREVIEW_ITEMS,
                source_annotations=address['source_annotations'][:MAX_PREVIEW_ITEMS],
                source_annotations_total=len(address['source_annotations']),
                source_annotations_truncated=len(address['source_annotations']) > MAX_PREVIEW_ITEMS,
                use_count=len(address['uses']), rung_count=len({use['rung_id'] for use in address['uses']}))
            alias_name = metadata['name'] if metadata['tag_type'] == 'Alias' else None
            row.update(source_metadata=metadata, suggested_target_name=alias_name or address['address'],
                target_name_basis='alias' if alias_name else 'base_address', suggested_field_type=hinted,
                suggested_type_basis='documented_member_layout' if documented else
                    'qualified_floating_channel_and_direction' if hinted != 'unknown' else 'catalog_direction_candidate')
            source_metadata = {key: row[key] for key in ('root_id', 'module_id', 'direction', 'field_type',
                'candidate_field_types', 'mapping_status', 'channel', 'datatype', 'point_basis')}
            source_metadata.update(snapshot_id=self.snapshot_id, suffix=_member_key(row['suffix']),
                                   catalog=module['catalog_number'], vendor=module['vendor'])
            signature = hashlib.sha256(json.dumps(source_metadata, sort_keys=True,
                ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()
            row['binding'] = {'snapshot_id': self.snapshot_id, 'root_id': row['root_id'],
                'suffix': row['suffix'], 'address_id': row['id'], 'evidence_signature': signature}
            row['hardware'] = self._hardware(module)
            self._retain(row)
            self.signals[row['id']] = row
            direct: dict[str, list[dict]] = defaultdict(list)
            for use in address['uses']:
                direct[use['rung_id']].append(use)
                self._retain((use['rung_id'], use['id']))
            self._direct[row['id']] = dict(direct)
            self._uses[row['id']] = sorted(address['uses'], key=lambda use: (
                self.base._order[use['rung_id']], self.base._instructions[use['instruction_id']].start, use['id']))
            parts = [row['address'], row['description'] or '', module['name'] or '',
                     module['catalog_number'] or '', module['description'] or '']
            parts.extend(str(alias.get(key) or '') for alias in address['aliases'] for key in ('name', 'description'))
            parts.extend(self.field_io.annotation_texts[note['id']] for note in address['source_annotations'])
            self._search[row['id']] = ' '.join(parts).casefold()
            self._retain(self._search[row['id']])
        self._ordered = sorted(self.signals, key=lambda identifier: (
            self.signals[identifier]['hardware']['controller']['path'] or '',
            self.signals[identifier]['hardware']['path'], self.signals[identifier]['direction'],
            self.signals[identifier]['channel'] is None, self.signals[identifier]['channel'] or 0,
            self.signals[identifier]['address'].casefold(), identifier))
        counts = Counter(row['field_type'] for row in self.signals.values()
                         if row['mapping_status'] == 'documented_member_layout')
        candidate_counts = Counter(kind for row in self.signals.values() if row['mapping_status'] == 'review_mapping'
                                   for kind in (row['candidate_field_types'] or ['unknown']))
        self.coverage = {'signals_total': len(self.signals), 'documented_total': sum(counts.values()),
            'candidates_total': sum(row['mapping_status'] == 'review_mapping' for row in self.signals.values()),
            'documented_by_field_type': {kind: counts[kind] for kind in FIELD_TYPES},
            'candidates_by_field_type': {kind: candidate_counts[kind] for kind in (*FIELD_TYPES, 'unknown')},
            'candidates_without_type_hint': candidate_counts['unknown'],
            'filter_counts': {kind: sum(row['field_type'] == kind or kind in row['candidate_field_types']
                                      for row in self.signals.values()) for kind in (*FIELD_TYPES, 'unknown')},
            'candidate_filter_counts_may_overlap': True,
            'excluded_addresses': excluded['non_signal_addresses'],
            'captured_addresses_total': len(self.field_io.addresses),
            'related_connections_available': self.connections is not None,
            'capacity_expansion': False, 'implicit_effects_available': False, 'member_overlap_available': False}

    def _source_metadata(self, row: dict) -> dict:
        """Keep authored alias settings beside the exact backing channel settings."""
        root = self.base._entities[row['root_id']]
        alias = self.base._entities[row['aliases'][0]['id']] if row['aliases'] else None
        selected = alias or root
        values = self.base._values.get((root.id, _member_key(row['suffix'])), [])
        qualified = [value for value in values if value['status'] == 'qualified'
                     and value['envelope'] == 'Data' and value['format'] == 'decorated']
        radices = {value['radix'] for value in qualified if value.get('radix')}
        return {'source_id': selected.id, 'name': selected.name or row['root_name'],
            'base_name': row['root_name'], 'tag_type': selected.attributes.get('TagType') or ('Alias' if alias else 'Base'),
            'alias_for': selected.attributes.get('AliasFor') if alias else None,
            'data_type': row['datatype'] or selected.attributes.get('DataType'),
            'radix': next(iter(radices)) if len(radices) == 1 else selected.attributes.get('Radix'),
            'external_access': selected.attributes.get('ExternalAccess', root.attributes.get('ExternalAccess'))}

    def _analogue_hint(self, row: dict, catalog_hints: list[str]) -> str:
        """A typed input/output channel can suggest analogue without a card profile.

        Keep the physical mapping unreviewed. A floating internal tag, status,
        configuration or output echo cannot enter this channel-only projection.
        """
        kind = {'input': 'ai', 'output': 'ao'}.get(row['direction'])
        if not kind or catalog_hints and kind not in catalog_hints:
            return 'unknown'
        if not re.fullmatch(r'\.Ch(?:0|[1-9][0-9]{0,3})(?:Data|\.Data)|\.Channel\[(?:0|[1-9][0-9]{0,3})\]\.Data',
                            row['suffix'], re.ASCII | re.IGNORECASE):
            return 'unknown'
        contents = [value for value in self.base._contents.get(row['root_id'], [])
                    if value['xml_name'] == 'Data' and value['format_kind'] == 'decorated']
        if len(contents) != 1:
            return 'unknown'
        key = _member_key(row['suffix'])
        values = [value for value in self.base._values.get((row['root_id'], key), [])
                  if value['envelope'] == 'Data' and value['format'] == 'decorated']
        if len(values) != 1 or values[0]['status'] != 'qualified':
            return 'unknown'
        value = values[0]
        if any(gap == '' or key == gap or key.startswith(gap + '.') or key.startswith(gap + '[')
               for gap in self.base._ambiguous.get((row['root_id'], value['content_id']), ())):
            return 'unknown'
        floating = value['datatype'] in {'REAL', 'LREAL'}
        radix_only = not value['datatype'] and value.get('radix') == 'Float'
        if not (floating or radix_only) or value.get('radix') not in {None, 'Float'}:
            return 'unknown'
        return kind

    @staticmethod
    def _hardware(module: dict) -> dict:
        return {key: module[key] for key in ('id', 'name', 'path', 'description', 'catalog_number',
            'vendor', 'controller', 'parent_module_id', 'parent_module_name', 'slot', 'location_status',
            'catalog_description', 'catalog_family', 'catalog_capacity', 'catalog_capacity_basis',
            'catalog_reference', 'catalog_reference_page', 'catalog_publication', 'field_type_reason')}

    def anchor(self, signal_id: str) -> dict:
        if type(signal_id) is not str or signal_id not in self.signals:
            raise FieldSignalError('Choose a field signal captured in this run.')
        return deepcopy(self.signals[signal_id]['binding'])

    def _rung(self, rung_id: str) -> dict:
        rung = self.base._rungs[rung_id]
        routine = self.base._entities.get(rung.parent_id)
        scope = self.base._entities.get(rung.scope_id)
        families = sorted({_FAMILIES.get(item.opcode.upper(), 'unknown') for item in rung.instructions})
        roles = []
        for family, role in (('calculation', 'scaling'), ('alarm', 'alarm'), ('pid_control', 'logic'),
                             ('boolean_output', 'logic'), ('timer_counter', 'logic'), ('data_transfer', 'reference')):
            if family in families and role not in roles:
                roles.append(role)
        return {'id': rung.id, 'rung_id': rung.id, 'number': rung.number, 'routine_id': rung.parent_id,
            'routine': routine.name if routine else None, 'scope_id': rung.scope_id,
            'scope': scope.name if scope else None, 'path': self.base._path(rung.parent_id) + ' / Rung ' + str(rung.number),
            'parse_status': rung.parse_status, 'source_qualified': bool(self.base._rung_ok.get(rung.id)),
            'function_families': families, 'candidate_role': roles[0] if roles else 'reference',
            'candidate_roles': roles or ['reference'], 'role_basis': 'captured_opcode_family_only',
            'role_notice': 'Suggested review role only; a calculation is not necessarily scaling and alarm consequence is unknown.'}

    def _related(self, signal_id: str, page: int, size: int = DETAIL_PAGE_SIZE) -> dict:
        direct_ids = sorted(self._direct[signal_id], key=self.base._order.__getitem__)
        traversal = {'direct_rungs_total': len(direct_ids), 'direct_rungs_examined': 0,
            'bridges_examined': 0, 'high_fanout_bridges_skipped': 0, 'omitted_endpoint_visits': 0,
            'truncated': False, 'max_direct_rungs': MAX_DIRECT_EXPANSION, 'max_bridges': MAX_BRIDGES,
            'max_bridge_fanout': MAX_BRIDGE_FANOUT, 'max_related_rungs': MAX_RELATED,
            'hop_count': 1, 'paths_per_rung_limit': MAX_RELATED_PATHS}
        result = {'available': self.connections is not None, **_page([], page, size),
                  'traversal': traversal, 'association_basis': 'one_hop_shared_exact_address',
                  'total_is_lower_bound': False}
        if self.connections is None:
            return result
        index = self.connections
        direct = set(direct_ids)
        chosen = self.signals[signal_id]
        chosen_key = chosen['root_id'], _member_key(chosen['suffix'])
        related: dict[str, dict] = {}
        examined: set[tuple[str, str]] = set()
        stop = False
        for from_id in direct_ids[:MAX_DIRECT_EXPANSION]:
            traversal['direct_rungs_examined'] += 1
            for bridge_id in index._map_rung_signals.get(from_id, []):
                bridge = index._signals[bridge_id]
                if (bridge['target_id'], _member_key(bridge['suffix'])) == chosen_key:
                    continue
                # One bridge per source rung remains explicit evidence of the
                # proposed two-edge association; do not invent transitive flow.
                key = from_id, bridge_id
                if key in examined:
                    continue
                if len(examined) >= MAX_BRIDGES:
                    traversal['truncated'] = stop = True
                    break
                examined.add(key)
                buckets = index._map_buckets[bridge_id]
                endpoint_count = sum(len(values) for values in buckets.values())
                if endpoint_count > MAX_BRIDGE_FANOUT:
                    traversal['high_fanout_bridges_skipped'] += 1
                    traversal['omitted_endpoint_visits'] += endpoint_count
                    traversal['truncated'] = True
                    continue
                endpoints = sorted(set().union(*buckets.values()) - direct, key=self.base._order.__getitem__)
                for rung_id in endpoints:
                    if rung_id not in related:
                        if len(related) >= MAX_RELATED:
                            traversal['truncated'] = stop = True
                            break
                        related[rung_id] = {**self._rung(rung_id), 'association_reason': 'shared_address_with_direct_use_rung',
                            'associations': [], 'associations_truncated': False}
                    row = related[rung_id]
                    if len(row['associations']) >= MAX_RELATED_PATHS:
                        row['associations_truncated'] = True
                        continue
                    row['associations'].append({'from_rung_id': from_id,
                        'connection_signal_id': bridge_id, 'target_id': bridge['target_id'],
                        'suffix': bridge['suffix'], 'address': bridge['label'],
                        'from_roles': [role for role, members in buckets.items() if from_id in members],
                        'related_roles': [role for role, members in buckets.items() if rung_id in members]})
                if stop:
                    break
            if stop:
                break
        traversal['bridges_examined'] = len(examined)
        traversal['truncated'] |= len(direct_ids) > traversal['direct_rungs_examined']
        rows = sorted(related.values(), key=lambda row: self.base._order[row['id']])
        return {**result, **_page(rows, page, size),
                'total_is_lower_bound': traversal['truncated']}

    def detail(self, signal_id: str, query: dict) -> dict:
        query = validate_query(query)
        self.anchor(signal_id)
        row = self.signals[signal_id]
        direct = self._direct[signal_id]
        rung_ids = sorted(direct, key=self.base._order.__getitem__)
        page = _page(rung_ids, query.get('rung_page', 1), query['detail_page_size'])
        page['items'] = [{**self._rung(identifier), 'association_reason': 'direct_exact_address_use',
            'use_count': len(direct[identifier]),
            'instruction_ids': list(dict.fromkeys(use['instruction_id'] for use in direct[identifier]))[:MAX_PREVIEW_ITEMS],
            'instruction_ids_truncated': len({use['instruction_id'] for use in direct[identifier]}) > MAX_PREVIEW_ITEMS}
            for identifier in page['items']]
        return {**deepcopy(row), 'direct_uses': _page(self._uses[signal_id], query.get('use_page', 1), query['detail_page_size']),
                'direct_rungs': page, 'related_rungs': self._related(signal_id, query.get('related_page', 1), query['detail_page_size']),
                'grouping_scope': 'exact_module_member', 'automatic_membership': False}

    def view(self, query: dict, *, extra_search: dict[str, str] | None = None) -> dict:
        query = validate_query(query)
        if extra_search is not None and (type(extra_search) is not dict or len(extra_search) > MAX_SIGNALS
                or any(type(key) is not str or type(value) is not str or len(key) > 256 or len(value) > 32768
                       for key, value in extra_search.items())
                or sum(len(key) + len(value) for key, value in extra_search.items()) > MAX_SAVED_SEARCH_CHARS):
            raise FieldSignalError('Saved field signal search metadata exceeds its limits.')
        extras = extra_search or {}
        needle = query['query'].casefold()
        if query['module_id'] and query['module_id'] not in self.field_io.modules:
            raise FieldSignalError('Choose a module captured in this run.')
        rows = []
        for identifier in self._ordered:
            row = self.signals[identifier]
            documented = row['mapping_status'] == 'documented_member_layout'
            if (query['section'] == 'signals' and not documented or query['section'] == 'candidates' and documented
                    or query['module_id'] and query['module_id'] != row['module_id']
                    or query['field_type'] and query['field_type'] != row['field_type']
                    and query['field_type'] not in row['candidate_field_types']
                    or needle and needle not in self._search[identifier] and needle not in extras.get(identifier, '').casefold()):
                continue
            rows.append(row)
        controllers = {}
        for row in rows:
            controller = row['hardware']['controller']
            identifier = controller['id'] or controller['name'] or 'unassigned'
            entry = controllers.setdefault(identifier, {'controller_id': identifier, 'controller_name': controller['name'], 'total': 0})
            entry['total'] += 1
        result = {'available': True, 'snapshot_id': self.snapshot_id, 'signals': _page(rows, query['page'], query['page_size']),
            'controller_counts': list(controllers.values()),
            'selected_signal': self.detail(query['signal_id'], query) if query['signal_id'] else None,
            'coverage': self.coverage, 'limitations': list(_LIMITATIONS),
            'notice': 'Captured channel addresses and mapping candidates. Select a row to review its source, related logic and saved migration decisions.'}
        result = _preview(result)
        # Display limits must never alter the exact identity submitted when a
        # reviewer saves a signal. The address label may remain a preview.
        for item in [*result['signals']['items'], *([result['selected_signal']] if result['selected_signal'] else [])]:
            item['binding'] = self.anchor(item['id'])
            item['suffix'] = self.signals[item['id']]['suffix']
        if len(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) > MAX_RESPONSE_BYTES:
            raise FieldSignalError('This field I/O view exceeds the display limit. Choose fewer signals or candidate rungs per page, or narrow the filters.')
        return deepcopy(result)
