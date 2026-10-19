"""Count-only investigation of captured rack/adapter data; never a binding rule.

All source models are replayed. XML is used only to qualify already modeled
entities and their ancestors, not to extract additional configuration values.
Each rack declaration receives one first-gap/observed-shape disposition.
"""
from __future__ import annotations

from collections import defaultdict
import json
import re
from typing import Any, Callable

from .models import InventoryResult, SourceSnapshot
from .module_io import MAX_TOPOLOGY_DEPTH, derive_module_io_names
from .references import ReferenceResult, validate_references
from .source import MAX_ELEMENTS, _read_nodes
from .tag_data import TagDataResult, validate_tag_data

MAX_REPORT_BYTES = 4096
MAX_REPORT_BYTES_V2 = 8192
MAX_COUNT = MAX_ELEMENTS
FAMILIES = frozenset({'rockwell_1794_acn15', 'other', 'missing_identity', 'unavailable_context'})
DISPOSITIONS = frozenset({
    'source_unqualified', 'adapter_missing', 'adapter_ambiguous', 'candidate_unavailable',
    'backing_tag_missing', 'backing_tag_ambiguous', 'backing_tag_unqualified',
    'backing_name_unavailable', 'representation_missing', 'representation_unsupported',
    'representation_ambiguous', 'shape_unsupported', 'data_member_missing',
    'data_member_ambiguous', 'data_array_unsupported', 'slot_missing', 'slot_ambiguous',
    'slot_shape_observed_mapping_unchecked',
})
_EARLY = frozenset({'source_unqualified', 'adapter_missing', 'adapter_ambiguous', 'candidate_unavailable'})
COVERAGE_KEYS = frozenset({'rack_connections', 'rack_declarations', 'declarations_by_direction',
                           'candidate_names', 'adapter_families', 'candidate_dispositions',
                           'observed_shape_by_family'})
CONSTANTS = {
    'schema_version': 1, 'policy_version': 2, 'report_kind': 'l5x_rack_backing_investigation_summary',
    'exporter_version': 'rack-backing-summary-1', 'analysis_scope': 'captured_rack_adapter_shape',
    'sharing_status': 'aggregate_sync_allowed', 'backing_mapping': 'not_analyzed',
    'communication_format': 'not_captured', 'profile_interpretation': 'not_implemented',
    'effective_value_selection': 'not_implemented', 'member_validation': 'not_implemented',
}
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*', re.ASCII)
_DECIMAL = re.compile(r'[0-9]+', re.ASCII)
_INDEX = re.compile(r'\[([0-9]+)\]', re.ASCII)
_MODULE_TYPE = re.compile(r'AB:(1756|1794|1734|1738)_[A-Za-z0-9_]{1,64}:([ICOS]):[0-9]{1,3}', re.ASCII)
_SCALAR_TYPES = frozenset({'BOOL', 'SINT', 'INT', 'DINT'})
_CATALOG_GROUPS = {
    'rockwell_1756_ethernet': frozenset({'1756-ENET', '1756-ENBT', '1756-EN2T', '1756-EN2F',
                                       '1756-EN2TR', '1756-EN3TR'}),
    'rockwell_1756_controlnet': frozenset({'1756-CNB', '1756-CNBR', '1756-CN2', '1756-CN2R'}),
    'rockwell_1794_flex': frozenset({'1794-ACN15', '1794-ACNR15', '1794-AENT', '1794-AENTR'}),
    'rockwell_1734_point': frozenset({'1734-AENT', '1734-AENTR'}),
    'rockwell_1738_armorpoint': frozenset({'1738-AENT', '1738-AENTR'}),
}
_CATALOG_FAMILIES = {catalog: f"rockwell_{catalog.lower().replace('-', '_')}"
                     for catalogs in _CATALOG_GROUPS.values() for catalog in catalogs}
V2_FAMILIES = frozenset(_CATALOG_FAMILIES.values()) | {'other', 'missing_identity', 'unavailable_context'}
_PRE_REPRESENTATION = _EARLY | {'backing_tag_missing', 'backing_tag_ambiguous',
                               'backing_tag_unqualified', 'backing_name_unavailable'}
V2_DISPOSITIONS = _PRE_REPRESENTATION | {
    'representation_missing', 'representation_unsupported', 'representation_ambiguous',
    'shape_unsupported', 'layout_unrecognized', 'layout_ambiguous', 'array_unsupported',
    'slot_missing', 'slot_ambiguous', 'slot_shape_unsupported',
    'data_array_shape_observed_mapping_unchecked', 'slot_array_shape_observed_mapping_unchecked',
}
V2_REPRESENTATIONS = frozenset({'unavailable_context', 'missing', 'single_decorated',
                              'decorated_with_l5k', 'decorated_with_other', 'multiple_decorated',
                              'l5k_only', 'other_only', 'mixed_without_decorated'})
V2_TYPE_FAMILIES = frozenset({'ab_1756', 'ab_1794', 'ab_1734', 'ab_1738', 'other',
                            'missing', 'unavailable_context'})
V2_MEMBERS = frozenset({'data', 'slot', 'slot_status_bits', 'fault', 'other'})
V2_LAYOUTS = frozenset({'data_array', 'slot_array'})
V2_HEADERS = frozenset({'unavailable_context', 'unrecognized_type', 'identity_unavailable',
                        'direction_mismatch', 'series_mismatch', 'series_direction_consistent'})
V2_SLOT_HEADER_FIELDS = frozenset({
    'not_examined', 'slot_missing_or_ambiguous', 'structure_unqualified', 'fields_unqualified',
    'qualified_header_fields_present', 'unrecognized_header_fields_present',
    'mismatched_header_fields_present',
})
V2_COVERAGE_KEYS = COVERAGE_KEYS | {'dispositions_by_direction', 'representation_census',
                                   'root_type_families', 'header_contexts', 'top_level_members',
                                   'observed_shape_by_layout_family', 'root_header_consistency',
                                   'observed_shape_by_header_consistency', 'slot_header_field_shapes'}
V2_CONSTANTS = CONSTANTS | {
    'schema_version': 2, 'exporter_version': 'rack-backing-summary-2',
    'analysis_scope': 'captured_rack_layout_evidence',
    'representation_usage': 'unique_decorated_source_shape', 'layout_usage': 'source_shape_not_binding',
    'header_comparison': 'catalog_series_and_direction_only',
}


class RackBackingSummaryError(ValueError):
    """Fixed failure containing no source-controlled evidence."""


def _invalid() -> None:
    raise RackBackingSummaryError('Rack backing summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != expected:
        _invalid()


def validate_rack_backing_summary(summary: dict[str, Any]) -> None:
    """Validate the closed publication vocabulary and count conservation."""
    if type(summary) is dict and type(summary.get('schema_version')) is int and summary['schema_version'] == 2:
        _validate_v2(summary)
        return
    _keys(summary, set(CONSTANTS) | {'status', 'coverage', 'tool_revision'})
    for key, value in CONSTANTS.items():
        if type(summary[key]) is not type(value) or summary[key] != value:
            _invalid()
    revision = summary['tool_revision']
    _keys(revision, {'commit', 'worktree'})
    if type(revision['worktree']) is not str:
        _invalid()
    if revision['worktree'] == 'unavailable':
        if revision['commit'] is not None:
            _invalid()
    elif revision['worktree'] in {'clean', 'modified'}:
        if type(revision['commit']) is not str or re.fullmatch(r'[0-9a-f]{40}', revision['commit']) is None:
            _invalid()
    else:
        _invalid()
    c = summary['coverage']
    _keys(c, COVERAGE_KEYS)
    maps = {'declarations_by_direction': {'input', 'output'},
            'candidate_names': {'available', 'unavailable'},
            'adapter_families': FAMILIES, 'candidate_dispositions': DISPOSITIONS,
            'observed_shape_by_family': FAMILIES}
    for key, value in c.items():
        if key in maps:
            _keys(value, maps[key])
            values = value.values()
        else:
            values = (value,)
        if any(type(count) is not int or not 0 <= count <= MAX_COUNT for count in values):
            _invalid()
    total = c['rack_declarations']
    if any(sum(c[key].values()) != total for key in maps if key != 'observed_shape_by_family'):
        _invalid()
    d = c['candidate_dispositions']
    if (total and not c['rack_connections']
            or c['rack_connections'] + total > MAX_ELEMENTS
            or c['adapter_families']['unavailable_context'] != sum(d[key] for key in _EARLY)
            or sum(d[key] for key in {'adapter_missing', 'adapter_ambiguous', 'candidate_unavailable'})
               > c['candidate_names']['unavailable']
            or sum(d[key] for key in DISPOSITIONS - _EARLY) > c['candidate_names']['available']
            or sum(c['observed_shape_by_family'].values()) != d['slot_shape_observed_mapping_unchecked']
            or c['observed_shape_by_family']['unavailable_context'] != 0
            or any(c['observed_shape_by_family'][key] > c['adapter_families'][key] for key in FAMILIES)
            or type(summary['status']) is not str
            or summary['status'] != ('partial' if c['rack_connections'] or total else 'complete')):
        _invalid()


def render_rack_backing_summary(summary: dict[str, Any]) -> str:
    validate_rack_backing_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=True, sort_keys=True, separators=(',', ':')) + '\n'
    limit = MAX_REPORT_BYTES_V2 if summary['schema_version'] == 2 else MAX_REPORT_BYTES
    if len(rendered.encode('utf-8')) > limit:
        _invalid()
    return rendered


def _validate_v2(summary: dict[str, Any]) -> None:
    _keys(summary, set(V2_CONSTANTS) | {'status', 'coverage', 'tool_revision'})
    for key, value in V2_CONSTANTS.items():
        if type(summary[key]) is not type(value) or summary[key] != value:
            _invalid()
    revision = summary['tool_revision']
    _keys(revision, {'commit', 'worktree'})
    if type(revision['worktree']) is not str:
        _invalid()
    if revision['worktree'] == 'unavailable':
        if revision['commit'] is not None:
            _invalid()
    elif revision['worktree'] in {'clean', 'modified'}:
        if type(revision['commit']) is not str or re.fullmatch(r'[0-9a-f]{40}', revision['commit']) is None:
            _invalid()
    else:
        _invalid()
    c = summary['coverage']
    _keys(c, V2_COVERAGE_KEYS)

    def count(value: Any) -> None:
        if type(value) is not int or not 0 <= value <= MAX_COUNT:
            _invalid()

    def counts(value: Any, keys: set[str] | frozenset[str]) -> None:
        _keys(value, keys)
        for number in value.values():
            count(number)

    for key in ('rack_connections', 'rack_declarations', 'header_contexts'):
        count(c[key])
    for key, keys in (
        ('declarations_by_direction', {'input', 'output'}), ('candidate_names', {'available', 'unavailable'}),
        ('adapter_families', V2_FAMILIES), ('observed_shape_by_family', V2_FAMILIES),
        ('candidate_dispositions', V2_DISPOSITIONS), ('root_type_families', V2_TYPE_FAMILIES),
        ('top_level_members', V2_MEMBERS),
        ('root_header_consistency', V2_HEADERS), ('observed_shape_by_header_consistency', V2_HEADERS),
        ('slot_header_field_shapes', V2_SLOT_HEADER_FIELDS),
    ):
        counts(c[key], keys)
    for key, outer, inner in (
        ('dispositions_by_direction', {'input', 'output'}, V2_DISPOSITIONS),
        ('representation_census', {'input', 'output'}, V2_REPRESENTATIONS),
        ('observed_shape_by_layout_family', V2_LAYOUTS, V2_FAMILIES),
    ):
        _keys(c[key], outer)
        for row in c[key].values():
            counts(row, inner)
    total, d = c['rack_declarations'], c['candidate_dispositions']
    def header_capacity(families: dict[str, int], *, matching: bool) -> int:
        # Marginals cannot identify individual headers, but they bound feasible
        # series matches/mismatches without assuming the same context was seen.
        recognized = sum(c['root_type_families'][f'ab_{series}'] for series in ('1756', '1794', '1734', '1738'))
        capacity = 0
        for series in ('1756', '1794', '1734', '1738'):
            products = sum(families[family] for catalog, family in _CATALOG_FAMILIES.items()
                           if catalog.startswith(f'{series}-'))
            roots = c['root_type_families'][f'ab_{series}']
            capacity += min(products, roots if matching else recognized - roots)
        return capacity

    if (total and not c['rack_connections'] or c['rack_connections'] + total > MAX_ELEMENTS
            or any(sum(c[key].values()) != total for key in ('declarations_by_direction', 'candidate_names',
                   'adapter_families', 'candidate_dispositions', 'root_type_families', 'root_header_consistency',
                   'slot_header_field_shapes'))
            or c['adapter_families']['unavailable_context'] != sum(d[key] for key in _EARLY)
            or sum(d[key] for key in {'adapter_missing', 'adapter_ambiguous', 'candidate_unavailable'})
               > c['candidate_names']['unavailable']
            or sum(d[key] for key in V2_DISPOSITIONS - _EARLY) > c['candidate_names']['available']
            or c['header_contexts'] != total - c['root_type_families']['unavailable_context']
            or c['header_contexts'] != total - c['root_header_consistency']['unavailable_context']
            or c['header_contexts'] != sum(d[key] for key in {'layout_unrecognized', 'layout_ambiguous',
                   'array_unsupported', 'slot_missing', 'slot_ambiguous', 'slot_shape_unsupported'} | {
                   f'{layout}_shape_observed_mapping_unchecked' for layout in V2_LAYOUTS})
            or c['root_header_consistency']['unrecognized_type']
               != c['root_type_families']['other'] + c['root_type_families']['missing']
            or c['root_header_consistency']['identity_unavailable']
               > c['adapter_families']['other'] + c['adapter_families']['missing_identity']
            or c['root_header_consistency']['series_mismatch'] + c['root_header_consistency']['series_direction_consistent']
               > sum(c['adapter_families'][key] for key in _CATALOG_FAMILIES.values())
            or c['root_header_consistency']['series_direction_consistent'] > header_capacity(c['adapter_families'], matching=True)
            or c['root_header_consistency']['series_mismatch'] > header_capacity(c['adapter_families'], matching=False)
            or any(value > c['header_contexts'] for value in c['top_level_members'].values())
            or type(summary['status']) is not str
            or summary['status'] != ('partial' if total or c['rack_connections'] else 'complete')):
        _invalid()
    for direction in ('input', 'output'):
        by_direction = c['dispositions_by_direction'][direction]
        census = c['representation_census'][direction]
        if (sum(by_direction.values()) != c['declarations_by_direction'][direction]
                or sum(census.values()) != c['declarations_by_direction'][direction]
                or census['unavailable_context'] != sum(by_direction[key] for key in _PRE_REPRESENTATION)
                or census['missing'] != by_direction['representation_missing']
                or census['multiple_decorated'] != by_direction['representation_ambiguous']
                or sum(census[key] for key in {'l5k_only', 'other_only', 'mixed_without_decorated'})
                   != by_direction['representation_unsupported']):
            _invalid()
    if any(sum(c['dispositions_by_direction'][direction][key] for direction in ('input', 'output')) != d[key]
           for key in V2_DISPOSITIONS):
        _invalid()
    observed = c['observed_shape_by_family']
    joints = c['observed_shape_by_layout_family']
    headers = c['observed_shape_by_header_consistency']
    slot_fields = c['slot_header_field_shapes']
    if (observed['unavailable_context'] != 0
            or any(sum(joints[layout].values()) != d[f'{layout}_shape_observed_mapping_unchecked'] for layout in V2_LAYOUTS)
            or any(sum(joints[layout][family] for layout in V2_LAYOUTS) != observed[family] for family in V2_FAMILIES)
            or any(observed[key] > c['adapter_families'][key] for key in V2_FAMILIES)
            or sum(observed.values()) > c['header_contexts']
            or sum(c['observed_shape_by_header_consistency'].values()) != sum(observed.values())
            or c['observed_shape_by_header_consistency']['unavailable_context'] != 0
            or any(c['observed_shape_by_header_consistency'][key] > c['root_header_consistency'][key]
                   for key in V2_HEADERS)
            or headers['series_mismatch'] + headers['series_direction_consistent']
               > sum(observed[key] for key in _CATALOG_FAMILIES.values())
            or headers['identity_unavailable'] > observed['other'] + observed['missing_identity']
            or headers['series_direction_consistent'] > header_capacity(observed, matching=True)
            or headers['series_mismatch'] > header_capacity(observed, matching=False)
            or headers['unrecognized_type'] + headers['direction_mismatch']
               > d['data_array_shape_observed_mapping_unchecked']
            or d['data_array_shape_observed_mapping_unchecked'] > c['top_level_members']['data']
            or d['slot_array_shape_observed_mapping_unchecked'] > c['top_level_members']['slot']):
        _invalid()
    if (total - slot_fields['not_examined'] > min(c['top_level_members']['slot'], c['header_contexts'])
            or slot_fields['qualified_header_fields_present'] != d['slot_array_shape_observed_mapping_unchecked']
            or slot_fields['mismatched_header_fields_present'] > d['slot_shape_unsupported']
            or sum(slot_fields[key] for key in {'unrecognized_header_fields_present',
                   'mismatched_header_fields_present', 'structure_unqualified', 'fields_unqualified'})
               > d['array_unsupported'] + d['slot_shape_unsupported']
            or slot_fields['slot_missing_or_ambiguous'] > d['array_unsupported'] + d['slot_missing'] + d['slot_ambiguous']
            or total - slot_fields['not_examined'] > sum(d[key] for key in {
                   'array_unsupported', 'slot_missing', 'slot_ambiguous', 'slot_shape_unsupported',
                   'slot_array_shape_observed_mapping_unchecked'})):
        _invalid()


def _namespace(name: str) -> str | None:
    return name.rsplit('}', 1)[0] if '}' in name else None


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
            tag_data: TagDataResult, *, schema_version: int = 1,
            evidence_sink: Callable[[dict[str, Any], str, str, dict[str, Any]], None] | None = None) -> dict[str, Any]:
    nodes = _read_nodes(snapshot.data)
    root_namespace = _namespace(nodes[0].expanded_name)
    by_locator = {node.locator: index for index, node in enumerate(nodes)}
    qualified: list[bool] = []
    protected: list[bool] = []
    markers = {'Protected', 'IsProtected', 'SourceProtected', 'SourceKey', 'SourceKeyName',
               'ProtectionType', 'Encrypted', 'EncryptionInfo', 'IsEncrypted'}
    for node in nodes:
        marked = (node.name in {'EncodedData', 'EncryptedContent', 'EncryptedAOIContent', 'EncryptionInfo'}
                  or bool(markers.intersection(node.attributes)))
        qualified.append(_namespace(node.expanded_name) == root_namespace
                         and all('}' not in key for key in node.expanded_attributes)
                         and not marked
                         and (node.parent is None or qualified[node.parent]))
        protected.append(marked)
    for index in range(len(nodes) - 1, -1, -1):
        parent = nodes[index].parent
        if parent is not None and protected[index]:
            protected[parent] = True
    entities = {row.id: row for row in inventory.entities}
    source_ok = {row.id: qualified[by_locator[row.locator]] and not protected[by_locator[row.locator]]
                 for row in inventory.entities}
    modules: dict[tuple[str | None, str], list[Any]] = defaultdict(list)
    ports: dict[str | None, list[Any]] = defaultdict(list)
    tags: dict[tuple[str | None, str], list[Any]] = defaultdict(list)
    connection_names: dict[tuple[str | None, str], int] = defaultdict(int)
    connection_ids: dict[tuple[str | None, str], int] = defaultdict(int)
    for row in inventory.entities:
        if row.kind == 'module' and row.name and _NAME.fullmatch(row.name):
            modules[(row.scope_id, row.name.lower())].append(row)
        elif row.kind == 'module_port':
            ports[row.parent_id].append(row)
        elif row.kind == 'module_connection':
            if row.name is not None:
                connection_names[(row.parent_id, row.name.lower())] += 1
            if 'Id' in row.attributes:
                connection_ids[(row.parent_id, row.attributes['Id'])] += 1
        elif row.kind in {'module_input_tag', 'module_output_tag'}:
            connection = entities.get(row.parent_id)
            if connection is not None and connection.kind == 'module_connection':
                tags[(connection.parent_id, row.kind)].append(row)
    # Cache each module's qualification across its topology ancestors. Walks
    # have the same fixed depth ceiling as naming, and retain only IDs/booleans.
    topology_ok: dict[str, bool] = {}

    def topology_qualified(module_id: str) -> bool:
        trail: list[str] = []
        current = entities[module_id]
        result = False
        for _ in range(MAX_TOPOLOGY_DEPTH):
            if current.id in topology_ok:
                result = topology_ok[current.id]
                break
            if current.id in trail:
                break
            trail.append(current.id)
            if not source_ok[current.id] or any(not source_ok[port.id] for port in ports[current.id]):
                break
            parent_name = current.attributes.get('ParentModule', current.name if current.name == 'Local' else '')
            if not _NAME.fullmatch(parent_name):
                break
            parents = modules.get((current.scope_id, parent_name.lower()), [])
            if len(parents) != 1:
                break
            if parents[0].id == current.id:
                result = current.name is not None and current.name.lower() == 'local'
                break
            current = parents[0]
        for identifier in trail:
            topology_ok[identifier] = result
        return result

    names = derive_module_io_names(inventory)
    contents: dict[str, list[dict[str, Any]]] = defaultdict(list)
    children: dict[str, list[dict[str, Any]]] = defaultdict(list)
    content_issues: dict[str, set[str]] = defaultdict(set)
    for row in tag_data.contents:
        contents[row['owner_id']].append(row)
    for row in tag_data.elements:
        children[row['parent_id']].append(row)
    for row in tag_data.issues:
        content_issues[row['content_id']].add(row['code'])
    # A backing representation can be shared by many cards. Analyze its roots,
    # Data member and indexes once; never copy its rows into per-card records.
    shape_cache: dict[str, tuple[str | None, dict[str, list[Any]] | None]] = {}

    def representation(owner_id: str) -> tuple[str | None, dict[str, list[Any]] | None]:
        if owner_id in shape_cache:
            return shape_cache[owner_id]
        rows = contents.get(owner_id, [])
        outcome: tuple[str | None, dict[str, list[Any]] | None]
        if not rows:
            outcome = ('representation_missing', None)
        elif len(rows) != 1:
            outcome = ('representation_ambiguous', None)
        else:
            content = rows[0]
            roots = children.get(content['id'], [])
            issues = content_issues.get(content['id'], set())
            if content['format_kind'] != 'decorated' or content['xml_namespace'] != root_namespace:
                outcome = ('representation_unsupported', None)
            elif (any('}' in key for key in content['attributes'])
                  or issues - {'duplicate_member', 'duplicate_element'}
                  or len(roots) != 1 or roots[0]['kind'] != 'structure'
                  or any('}' in key for key in roots[0]['attributes'])):
                outcome = ('shape_unsupported', None)
            else:
                members = [row for row in children.get(roots[0]['id'], [])
                           if row['attributes'].get('Name', '').lower() == 'data']
                if not members:
                    outcome = ('data_member_missing', None)
                elif len(members) != 1:
                    outcome = ('data_member_ambiguous', None)
                else:
                    member = members[0]
                    attrs = member['attributes']
                    dimension = attrs.get('Dimensions', '')
                    if (member['kind'] != 'array_member' or attrs.get('DataType') != 'DINT'
                            or any('}' in key for key in attrs)
                            or not _DECIMAL.fullmatch(dimension) or len(dimension) > 6
                            or not 1 <= int(dimension) <= MAX_ELEMENTS):
                        outcome = ('data_array_unsupported', None)
                    else:
                        indexes: dict[str, list[Any]] = defaultdict(list)
                        valid = True
                        for element in children.get(member['id'], []):
                            match = _INDEX.fullmatch(element['attributes'].get('Index', ''))
                            index = (match[1].lstrip('0') or '0') if match else None
                            if (element['kind'] != 'element' or index is None or len(index) > 6
                                    or int(index) >= int(dimension)
                                    or any('}' in key for key in element['attributes'])
                                    or 'Value' not in element['attributes']
                                    or children.get(element['id'])):
                                valid = False
                                break
                            indexes[index].append(element)
                        outcome = (None, indexes) if valid else ('data_array_unsupported', None)
        shape_cache[owner_id] = outcome
        return outcome

    v2_shapes: dict[str, dict[str, Any]] = {}

    def representation_v2(owner_id: str) -> dict[str, Any]:
        if owner_id in v2_shapes:
            return v2_shapes[owner_id]
        rows = contents.get(owner_id, [])
        decorated = [row for row in rows if row['format_kind'] == 'decorated']
        formats = {row['format_kind'] for row in rows}
        census = ('missing' if not rows else 'multiple_decorated' if len(decorated) > 1 else
                  'single_decorated' if len(rows) == 1 and decorated else
                  'decorated_with_l5k' if decorated and formats <= {'decorated', 'l5k'} else
                  'decorated_with_other' if decorated else 'l5k_only' if formats == {'l5k'} else
                  'other_only' if len(formats) == 1 else 'mixed_without_decorated')
        value: dict[str, Any] = {'census': census, 'root_type_family': 'unavailable_context',
                                 'members': set(), 'layout': None, 'indexes': {},
                                 'gap': None, 'slot_shapes': {}, 'type_series': None, 'type_direction': None,
                                 'slot_diagnostics': None}
        v2_shapes[owner_id] = value
        if not rows:
            value['gap'] = 'representation_missing'
            return value
        if not decorated:
            value['gap'] = 'representation_unsupported'
            return value
        if len(decorated) != 1:
            value['gap'] = 'representation_ambiguous'
            return value
        content = decorated[0]
        roots = children.get(content['id'], [])
        issues = content_issues.get(content['id'], set())
        if (content['xml_namespace'] != root_namespace or any('}' in key for key in content['attributes'])
                or issues - {'duplicate_member', 'duplicate_element'}
                or len(roots) != 1 or roots[0]['kind'] != 'structure'
                or any('}' in key for key in roots[0]['attributes'])):
            value['gap'] = 'shape_unsupported'
            return value
        root = roots[0]
        value['content_id'], value['root_element_id'] = content['id'], root['id']
        data_type = root['attributes'].get('DataType', '')
        type_match = _MODULE_TYPE.fullmatch(data_type)
        value['root_type_family'] = f'ab_{type_match[1]}' if type_match else 'other' if data_type else 'missing'
        if type_match:
            value['type_series'], value['type_direction'] = type_match[1], type_match[2]
        members: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in children.get(root['id'], []):
            name = row['attributes'].get('Name', '').lower()
            members[name].append(row)
            value['members'].add({'data': 'data', 'slot': 'slot', 'slotstatusbits': 'slot_status_bits',
                                  'fault': 'fault'}.get(name, 'other'))
        available = [name for name in ('data', 'slot') if name in members]
        if not available:
            value['gap'] = 'layout_unrecognized'
            return value
        if len(available) != 1 or len(members[available[0]]) != 1:
            value['gap'] = 'layout_ambiguous'
            return value
        member = members[available[0]][0]
        value['array_element_id'] = member['id']
        value['layout'] = f'{available[0]}_array'
        attrs = member['attributes']
        dimension = attrs.get('Dimensions', '')
        member_type = attrs.get('DataType', '')
        if (member['kind'] != 'array_member' or any('}' in key for key in attrs)
                or not _DECIMAL.fullmatch(dimension) or len(dimension) > 6
                or not 1 <= int(dimension) <= MAX_ELEMENTS
                or (value['layout'] == 'data_array' and member_type not in _SCALAR_TYPES)):
            value['gap'] = 'array_unsupported'
            return value
        array_type = _MODULE_TYPE.fullmatch(member_type)
        if value['layout'] == 'slot_array' and array_type is None:
            # Keep the strict native-shape outcome, while inspecting qualified
            # structure fields separately from an unrecognized type spelling.
            value['gap'] = 'array_unsupported'
        indexes: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for element in children.get(member['id'], []):
            match = _INDEX.fullmatch(element['attributes'].get('Index', ''))
            index = (match[1].lstrip('0') or '0') if match else None
            if (element['kind'] != 'element' or index is None or len(index) > 6
                    or int(index) >= int(dimension) or any('}' in key for key in element['attributes'])):
                value['gap'] = 'array_unsupported'
                return value
            indexes[index].append(element)
        value['indexes'] = indexes
        if value['layout'] == 'slot_array':
            value['slot_diagnostics'] = {}
        for index, elements in indexes.items():
            if len(elements) != 1:
                value['slot_shapes'][index] = 'slot_ambiguous'
                if value['slot_diagnostics'] is not None:
                    value['slot_diagnostics'][index] = 'slot_missing_or_ambiguous'
                continue
            element = elements[0]
            nested = children.get(element['id'], [])
            if value['layout'] == 'data_array':
                good = 'Value' in element['attributes'] and not nested
            else:
                expected_direction = 'I' if entities[owner_id].kind == 'module_input_tag' else 'O'
                structure_ok = (len(nested) == 1 and nested[0]['kind'] == 'structure'
                                and not any('}' in key for key in nested[0]['attributes']))
                fields_ok = header_ok = False
                diagnostic = 'structure_unqualified'
                if structure_ok:
                    element_type = _MODULE_TYPE.fullmatch(nested[0]['attributes'].get('DataType', ''))
                    header_recognized = type_match is not None and array_type is not None and element_type is not None
                    header_ok = (header_recognized and nested[0]['attributes'].get('DataType') == member_type
                                 and array_type[1] == type_match[1]
                                 and array_type[2] == type_match[2] == expected_direction)
                    fields: dict[str, list[dict[str, Any]]] = defaultdict(list)
                    for field in children.get(nested[0]['id'], []):
                        fields[field['attributes'].get('Name', '').lower()].append(field)
                    required = {'data', 'fault'} if entities[owner_id].kind == 'module_input_tag' else {'data'}
                    fields_ok = all(len(fields.get(name, [])) == 1
                                    and fields[name][0]['kind'] == 'data_value_member'
                                    and fields[name][0]['attributes'].get('DataType') == 'DINT'
                                    and not any('}' in key for key in fields[name][0]['attributes'])
                                    and not children.get(fields[name][0]['id']) for name in required)
                    diagnostic = ('fields_unqualified' if not fields_ok else
                                  'qualified_header_fields_present' if header_ok else
                                  'unrecognized_header_fields_present' if not header_recognized else
                                  'mismatched_header_fields_present')
                value['slot_diagnostics'][index] = diagnostic
                good = structure_ok and fields_ok and header_ok
            value['slot_shapes'][index] = (f"{value['layout']}_shape_observed_mapping_unchecked"
                                            if good else 'slot_shape_unsupported')
        return value

    families = V2_FAMILIES if schema_version == 2 else FAMILIES
    dispositions = V2_DISPOSITIONS if schema_version == 2 else DISPOSITIONS
    c = {'rack_connections': inventory.counts['module_rack_connections'],
         'rack_declarations': 0, 'declarations_by_direction': {'input': 0, 'output': 0},
         'candidate_names': {'available': 0, 'unavailable': 0},
         'adapter_families': dict.fromkeys(sorted(families), 0),
         'observed_shape_by_family': dict.fromkeys(sorted(families), 0),
         'candidate_dispositions': dict.fromkeys(sorted(dispositions), 0)}
    if schema_version == 2:
        c.update(dispositions_by_direction={direction: dict.fromkeys(sorted(V2_DISPOSITIONS), 0)
                                            for direction in ('input', 'output')},
                 representation_census={direction: dict.fromkeys(sorted(V2_REPRESENTATIONS), 0)
                                        for direction in ('input', 'output')},
                 root_type_families=dict.fromkeys(sorted(V2_TYPE_FAMILIES), 0),
                 header_contexts=0, top_level_members=dict.fromkeys(sorted(V2_MEMBERS), 0),
                 root_header_consistency=dict.fromkeys(sorted(V2_HEADERS), 0),
                 observed_shape_by_header_consistency=dict.fromkeys(sorted(V2_HEADERS), 0),
                 slot_header_field_shapes=dict.fromkeys(sorted(V2_SLOT_HEADER_FIELDS), 0),
                 observed_shape_by_layout_family={layout: dict.fromkeys(sorted(V2_FAMILIES), 0)
                                                 for layout in sorted(V2_LAYOUTS)})

    def classify(candidate: dict[str, Any], metadata: dict[str, Any]) -> tuple[str, str]:
        unavailable = 'unavailable_context'
        module = entities.get(candidate['module_id'])
        if module is None or not all(source_ok.get(candidate[key], False)
                                     for key in ('source_id', 'connection_id', 'module_id')):
            return 'source_unqualified', unavailable
        parent_name = module.attributes.get('ParentModule', '')
        if parent_name and not _NAME.fullmatch(parent_name):
            return 'source_unqualified', unavailable
        parents = modules.get((module.scope_id, parent_name.lower()), [])
        if not parents:
            return 'adapter_missing', unavailable
        if len(parents) != 1:
            return 'adapter_ambiguous', unavailable
        adapter = parents[0]
        if not source_ok[adapter.id]:
            return 'source_unqualified', unavailable
        if candidate['name'] is None:
            return 'candidate_unavailable', unavailable
        if not topology_qualified(module.id):
            return 'source_unqualified', unavailable
        vendor, catalog = (adapter.attributes.get(key) for key in ('Vendor', 'CatalogNumber'))
        family = ('missing_identity' if not vendor or not catalog else
                  'rockwell_1794_acn15' if vendor == '1' and catalog == '1794-ACN15' else 'other')
        if schema_version == 2:
            family = ('missing_identity' if not vendor or not catalog else
                      _CATALOG_FAMILIES.get(catalog, 'other') if vendor == '1'
                      and 'UserDefinedCatalogNumber' not in adapter.attributes else 'other')
        kind, suffix = ('module_input_tag', 'I') if candidate['direction'] == 'input' else ('module_output_tag', 'O')
        possible = tags.get((adapter.id, kind), [])
        if not possible:
            return 'backing_tag_missing', family
        if len(possible) != 1:
            return 'backing_tag_ambiguous', family
        tag = possible[0]
        if not source_ok[tag.id] or not source_ok[tag.parent_id]:
            return 'backing_tag_unqualified', family
        connection = entities[tag.parent_id]
        if ((connection.name is not None
             and connection_names[(adapter.id, connection.name.lower())] != 1)
                or ('Id' in connection.attributes
                    and connection_ids[(adapter.id, connection.attributes['Id'])] != 1)):
            return 'backing_tag_ambiguous', family
        expected = f'{adapter.name}:{suffix}'
        actual = names[tag.id]['name']
        if actual is None or actual.lower() != expected.lower():
            return 'backing_name_unavailable', family
        if schema_version == 2:
            shape = representation_v2(tag.id)
            metadata.update(census=shape['census'], root_type_family=shape['root_type_family'],
                            members=shape['members'], layout=shape['layout'])
            slot = candidate['name'].rsplit(':', 2)[1].lstrip('0') or '0'
            if evidence_sink is not None:
                # Private callers receive references into authenticated source
                # rows, not copied values or any additional XML extraction.
                selected = shape['indexes'].get(slot, [])
                metadata['evidence'] = {
                    'adapter_id': adapter.id, 'backing_tag_id': tag.id,
                    'backing_name': actual, 'slot': slot,
                    'content_id': shape.get('content_id'),
                    'root_element_id': shape.get('root_element_id'),
                    'array_element_id': shape.get('array_element_id'),
                    'selected_element': selected[0] if len(selected) == 1 else None,
                }
            if shape['slot_diagnostics'] is not None:
                metadata['slot_header_field_shape'] = shape['slot_diagnostics'].get(slot, 'slot_missing_or_ambiguous')
            if shape['root_type_family'] != 'unavailable_context':
                metadata['header_consistency'] = (
                    'unrecognized_type' if shape['type_series'] is None else
                    'direction_mismatch' if shape['type_direction'] != suffix else
                    'identity_unavailable' if family in {'other', 'missing_identity'} else
                    'series_mismatch' if catalog.split('-', 1)[0] != shape['type_series'] else
                    'series_direction_consistent')
            if shape['gap'] is not None:
                return shape['gap'], family
            return shape['slot_shapes'].get(slot, 'slot_missing'), family
        gap, indexes = representation(tag.id)
        if gap is not None:
            return gap, family
        slot = candidate['name'].rsplit(':', 2)[1].lstrip('0') or '0'
        assert indexes is not None
        matches = indexes.get(slot, [])
        if not matches:
            return 'slot_missing', family
        if len(matches) != 1:
            return 'slot_ambiguous', family
        return 'slot_shape_observed_mapping_unchecked', family

    for candidate in references.rack_candidates['candidates']:
        c['rack_declarations'] += 1
        c['declarations_by_direction'][candidate['direction']] += 1
        c['candidate_names']['available' if candidate['name'] is not None else 'unavailable'] += 1
        metadata: dict[str, Any] = {'census': 'unavailable_context', 'root_type_family': 'unavailable_context',
                                    'members': set(), 'layout': None, 'header_consistency': 'unavailable_context',
                                    'slot_header_field_shape': 'not_examined'}
        disposition, family = classify(candidate, metadata)
        if evidence_sink is not None:
            evidence_sink(candidate, disposition, family, metadata)
        c['candidate_dispositions'][disposition] += 1
        c['adapter_families'][family] += 1
        if disposition == 'slot_shape_observed_mapping_unchecked':
            c['observed_shape_by_family'][family] += 1
        if schema_version == 2:
            c['dispositions_by_direction'][candidate['direction']][disposition] += 1
            c['representation_census'][candidate['direction']][metadata['census']] += 1
            c['root_type_families'][metadata['root_type_family']] += 1
            c['root_header_consistency'][metadata['header_consistency']] += 1
            c['slot_header_field_shapes'][metadata['slot_header_field_shape']] += 1
            if metadata['root_type_family'] != 'unavailable_context':
                c['header_contexts'] += 1
                for member in metadata['members']:
                    c['top_level_members'][member] += 1
            if disposition in {f'{layout}_shape_observed_mapping_unchecked' for layout in V2_LAYOUTS}:
                c['observed_shape_by_family'][family] += 1
                c['observed_shape_by_layout_family'][metadata['layout']][family] += 1
                c['observed_shape_by_header_consistency'][metadata['header_consistency']] += 1
    return c


def build_rack_backing_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
                               references: ReferenceResult, tag_data: TagDataResult, *,
                               tool_revision: dict[str, Any] | None = None,
                               schema_version: int = 1) -> dict[str, Any]:
    """Authenticate captured evidence and publish only fixed investigation counts."""
    try:
        if type(schema_version) is not int or schema_version not in {1, 2}:
            _invalid()
        validate_tag_data(snapshot, inventory, tag_data)
        validate_references(inventory, references)
        coverage = _derive(snapshot, inventory, references, tag_data, schema_version=schema_version)
        summary = (V2_CONSTANTS if schema_version == 2 else CONSTANTS) | {
            'status': 'partial' if coverage['rack_connections'] or coverage['rack_declarations'] else 'complete',
            'coverage': coverage,
            'tool_revision': dict(tool_revision) if tool_revision is not None else {'commit': None, 'worktree': 'unavailable'},
        }
        render_rack_backing_summary(summary)
        return summary
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, RecursionError, OverflowError):
        _invalid()
