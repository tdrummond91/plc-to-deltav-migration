"""Exact source-address correspondences for qualified 1756-EN2T rack aliases.

This overlay never changes the historical reference/access models. A qualified
RackConnection declaration and captured module-type Slot structure establish a
source path, not physical wiring, live configuration, values or execution.
The header grammar checks series/direction, not a product profile catalogue.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from io import StringIO
from itertools import chain
import json
import re
from typing import Any

from .access import AccessResult
from .binding_context import BindingContextResult, validate_binding_context
from .calculations import CalculationResult
from .conditions import ConditionResult
from .models import InventoryResult, SourceSnapshot
from .rack_backing_summary import _derive as _rack_shapes, _namespace, V2_DISPOSITIONS
from .references import ReferenceResult, _Resolver, _address, _ADDRESS, MAX_ADDRESS_LENGTH, _strict_record_match
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult
from .sfc_conditions import SfcConditionResult, validate_sfc_conditions
from .sfc_structure import SfcStructureResult
from .source import _read_nodes
from .tag_data import TagDataResult, validate_tag_data

MAX_CONTEXT_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 250_000
MAX_EVIDENCE_IDS = 1_000_000
ROOT_DISPOSITIONS = (V2_DISPOSITIONS - {'slot_array_shape_observed_mapping_unchecked'}) | {
    'associated', 'family_unsupported', 'backing_identity_gap', 'duplicate_candidate_name'}
ADDRESS_DISPOSITIONS = frozenset({'associated', 'root_gap', 'suffix_unsupported',
                                  'member_unavailable', 'bit_out_of_range'})
USE_DISPOSITIONS = ADDRESS_DISPOSITIONS | {'source_unqualified', 'alias_metadata_unqualified',
    'non_rack_gap', 'candidate_unavailable', 'candidate_ambiguous', 'outside_scope'}
COUNT_MAPS = {
    'roots_by_direction': frozenset({'input', 'output'}),
    'roots_by_disposition': ROOT_DISPOSITIONS,
    'addresses_by_direction': frozenset({'input', 'output'}),
    'addresses_by_disposition': ADDRESS_DISPOSITIONS,
    'rll_uses_by_disposition': USE_DISPOSITIONS,
    'sfc_uses_by_disposition': USE_DISPOSITIONS,
    'associated_uses_by_role': frozenset({'read', 'write', 'read_write'}),
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | {
    'source_rack_connections', 'source_rack_declarations', 'source_candidate_addresses',
    'source_candidate_uses', 'source_candidate_roots', 'source_rll_gap_uses',
    'source_sfc_references', 'source_sfc_binding_gaps', 'roots_total', 'addresses_total',
    'uses_total', 'rll_addresses', 'sfc_addresses', 'shared_addresses',
    'associated_predicate_uses', 'associated_output_uses', 'associated_rll_addresses',
    'associated_sfc_addresses',
}
CONTEXT_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'rack-backing-context-1',
    'analysis_scope': 'qualified_rack_source_address_correspondence',
    'binding_effect': 'independent_overlay', 'physical_mapping': 'not_proven',
    'runtime_analysis': 'not_implemented', 'effective_value_selection': 'not_implemented',
    'engineering_review': 'unreviewed',
}
_SUFFIX = re.compile(r'\.(Data|Fault)(?:\.([0-9]+))?', re.ASCII | re.IGNORECASE)
_MARKERS = frozenset({'Protected', 'IsProtected', 'SourceProtected', 'SourceKey', 'SourceKeyName',
                      'ProtectionType', 'Encrypted', 'EncryptionInfo', 'IsEncrypted'})


class RackBackingContextError(ValueError):
    """Source-free evidence rejection."""


def _invalid() -> None:
    raise RackBackingContextError('Rack backing context does not match its source evidence.') from None


def _limit() -> None:
    raise RackBackingContextError('Rack backing context exceeds its evidence limits.') from None


@dataclass(frozen=True)
class RackBackingContextResult:
    snapshot: dict[str, str | int]
    status: str
    roots: list[dict[str, Any]]
    addresses: list[dict[str, Any]]
    uses: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'rack-backing-context-1'
    analysis_scope: str = 'qualified_rack_source_address_correspondence'
    binding_effect: str = 'independent_overlay'
    physical_mapping: str = 'not_proven'
    runtime_analysis: str = 'not_implemented'
    effective_value_selection: str = 'not_implemented'
    engineering_review: str = 'unreviewed'

    def to_dict(self) -> dict[str, Any]:
        render_rack_backing_context_json(self)
        return deepcopy(vars(self))


def _id(kind: str, *parts: str) -> str:
    return 'rack_backing_' + kind + '_' + hashlib.sha256('\0'.join(parts).encode()).hexdigest()


class _Budget:
    def __init__(self) -> None:
        self.bytes = self.rows = self.links = 0

    def retain(self, row: dict[str, Any]) -> None:
        self.rows += 1
        self.links += sum(key.endswith('_id') and value is not None for key, value in row.items())
        self.bytes += len(json.dumps(row, ensure_ascii=True, separators=(',', ':'))) + 1
        if self.rows > MAX_RECORDS or self.links > MAX_EVIDENCE_IDS or self.bytes > MAX_CONTEXT_BYTES:
            _limit()


def _qualification(snapshot: SourceSnapshot, inventory: InventoryResult):
    nodes = _read_nodes(snapshot.data)
    root_namespace = _namespace(nodes[0].expanded_name)
    qualified, protected = [], []
    for node in nodes:
        marked = (node.name in {'EncodedData', 'EncryptedContent', 'EncryptedAOIContent', 'EncryptionInfo'}
                  or bool(_MARKERS.intersection(node.attributes)))
        qualified.append(not marked and _namespace(node.expanded_name) == root_namespace
                         and not any('}' in key for key in node.expanded_attributes)
                         and (node.parent is None or qualified[node.parent]))
        protected.append(marked)
    for index in range(len(nodes) - 1, -1, -1):
        parent = nodes[index].parent
        if parent is not None and protected[index]:
            protected[parent] = True
    envelopes = list(qualified)
    for index in range(len(nodes) - 1, -1, -1):
        parent = nodes[index].parent
        if parent is not None and not envelopes[index]:
            envelopes[parent] = False
    by_locator = {node.locator: envelopes[index] and not protected[index] for index, node in enumerate(nodes)}
    return by_locator, {row.id: by_locator[row.locator] for row in inventory.entities}


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
            access: AccessResult, binding_context: BindingContextResult, tag_data: TagDataResult,
            sfc_structure: SfcStructureResult, sfc_conditions: SfcConditionResult) -> RackBackingContextResult:
    if max(len(binding_context.gaps), len(sfc_conditions.references),
           len(references.rack_candidates['candidates'])) > MAX_RECORDS:
        _limit()
    budget = _Budget()
    c = {key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()}
    c.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
    c.update(source_rack_connections=inventory.counts['module_rack_connections'],
             source_rack_declarations=len(references.rack_candidates['candidates']),
             source_candidate_addresses=len(binding_context.logical_addresses),
             source_candidate_uses=binding_context.coverage['candidate_address_uses'],
             source_candidate_roots=binding_context.coverage['candidate_roots'],
             source_rll_gap_uses=len(binding_context.gaps), source_sfc_references=len(sfc_conditions.references),
             source_sfc_binding_gaps=sum(row['binding_status'] != 'root_bound' for row in sfc_conditions.references))
    entities = {row.id: row for row in inventory.entities}
    resolver = _Resolver(inventory)
    source_ok, entity_ok = _qualification(snapshot, inventory)
    elements = {row['id']: row for row in tag_data.elements}
    children: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in tag_data.elements:
        children[row['parent_id']].append(row)
    roots: dict[str, dict[str, Any]] = {}
    candidates = references.rack_candidates['candidates']
    names: dict[tuple[str | None, str], list[str]] = defaultdict(list)
    unnamed: set[str | None] = set()
    named_scopes: dict[str, set[str | None]] = defaultdict(set)
    for candidate in candidates:
        if candidate['name'] is None:
            unnamed.add(candidate['scope_id'])
        else:
            names[(candidate['scope_id'], candidate['name'].lower())].append(candidate['source_id'])
            named_scopes[candidate['name'].lower()].add(candidate['scope_id'])

    def root_evidence(candidate: dict[str, Any], disposition: str, family: str, metadata: dict[str, Any]) -> None:
        evidence = metadata.get('evidence', {})
        row = {'id': _id('root', candidate['source_id']), 'candidate_id': candidate['source_id'],
               'module_id': candidate['module_id'], 'rack_connection_id': candidate['connection_id'],
               'direction': candidate['direction'], 'disposition': disposition,
               'adapter_id': evidence.get('adapter_id'), 'backing_tag_id': None,
               'content_id': None, 'root_element_id': None, 'array_element_id': None,
               'slot_element_id': None, 'slot_structure_id': None,
               'data_member_id': None, 'fault_member_id': None, 'slot': None,
               'backing_suffix': None}
        if disposition == 'slot_array_shape_observed_mapping_unchecked':
            row['disposition'] = 'family_unsupported'
            if family == 'rockwell_1756_en2t' and metadata['header_consistency'] == 'series_direction_consistent':
                row['disposition'] = 'duplicate_candidate_name'
                if len(names[(candidate['scope_id'], candidate['name'].lower())]) == 1:
                    tag = entities[evidence['backing_tag_id']]
                    resolved = resolver.resolve(evidence['backing_name'], tag.scope_id)
                    row['disposition'] = 'backing_identity_gap'
                    if (resolved['status'] == 'root_bound' and resolved['target_id'] == tag.id
                            and resolved['symbol_id'] == tag.id and not resolved['alias_chain']
                            and resolved['suffix'] == ''):
                        selected = evidence['selected_element']
                        structure = children[selected['id']][0]
                        fields = {field['attributes'].get('Name', '').lower(): field
                                  for field in children[structure['id']]}
                        row.update(disposition='associated', backing_tag_id=tag.id,
                                   content_id=evidence['content_id'], root_element_id=evidence['root_element_id'],
                                   array_element_id=evidence['array_element_id'], slot_element_id=selected['id'],
                                   slot_structure_id=structure['id'], data_member_id=fields['data']['id'],
                                   fault_member_id=fields['fault']['id'] if candidate['direction'] == 'input' else None,
                                   slot=evidence['slot'], backing_suffix=(
                                       f".{elements[evidence['array_element_id']]['attributes']['Name']}[{evidence['slot']}]"))
        budget.retain(row)
        roots[candidate['source_id']] = row
        c['roots_by_direction'][row['direction']] += 1
        c['roots_by_disposition'][row['disposition']] += 1

    _rack_shapes(snapshot, inventory, references, tag_data, schema_version=2, evidence_sink=root_evidence)

    def suffix_evidence(root: dict[str, Any], suffix: str) -> tuple[str, str | None, str | None]:
        if root['disposition'] != 'associated':
            return 'root_gap', None, None
        backing_name = resolver.name(entities[root['backing_tag_id']])
        if backing_name is None or len(backing_name) + len(root['backing_suffix']) + len(suffix) > MAX_ADDRESS_LENGTH:
            return 'suffix_unsupported', None, None
        if not suffix:
            return 'associated', root['slot_structure_id'], elements[root['slot_structure_id']]['attributes']['DataType']
        match = _SUFFIX.fullmatch(suffix)
        if match is None:
            return 'suffix_unsupported', None, None
        field_id = root['data_member_id'] if match[1].lower() == 'data' else root['fault_member_id']
        if field_id is None:
            return 'member_unavailable', None, None
        bit = match[2]
        if bit is not None and (len(bit.lstrip('0')) > 2 or int(bit.lstrip('0') or '0') > 31):
            return 'bit_out_of_range', None, None
        return 'associated', field_id, 'BOOL' if bit is not None else 'DINT'

    def match_candidate(binding: dict[str, Any], raw_text: str, scope_id: str | None) -> tuple[str, str | None]:
        if binding['status'] != 'unresolved' or binding['reason'] != 'colon_root_not_declared':
            return 'non_rack_gap', None
        if binding['alias_chain']:
            last = entities[binding['alias_chain'][-1]]
            raw_text, scope_id = last.attributes.get('AliasFor', ''), last.scope_id
        parsed, _ = _address(raw_text)
        if parsed is None:
            return 'suffix_unsupported', None
        scope = entities.get(scope_id)
        visible = [scope_id]
        if scope is not None and scope.kind == 'program':
            visible.append(scope.scope_id)
        matches = [identifier for eligible in visible for identifier in names.get((eligible, parsed[0].lower()), [])]
        if len(matches) == 1:
            return 'associated', matches[0]
        if matches:
            return 'candidate_ambiguous', None
        if any(eligible in unnamed for eligible in visible):
            return 'candidate_unavailable', None
        return ('outside_scope' if parsed[0].lower() in named_scopes else 'candidate_unavailable'), None

    alias_checks: dict[tuple[str, str], bool] = {}

    def aliases_ok(binding: dict[str, Any], candidate_id: str) -> bool:
        for alias_id in binding['alias_chain']:
            key = (alias_id, candidate_id)
            if key not in alias_checks:
                alias = entities[alias_id]
                okay = entity_ok[alias_id] and alias.attributes.get('Dimensions', '0') == '0'
                if okay and alias.attributes.get('DataType') is not None:
                    expanded = resolver.resolve(alias.name or '', alias.scope_id)
                    _, found = match_candidate(expanded, alias.name or '', alias.scope_id)
                    status, _, data_type = suffix_evidence(roots[candidate_id], expanded['suffix'])
                    okay = found == candidate_id and status == 'associated' and alias.attributes['DataType'] == data_type
                alias_checks[key] = okay
                # Cache bounded evidence checks, never expanded alias chains.
                if len(alias_checks) > MAX_RECORDS or len(alias_checks) * 160 > MAX_CONTEXT_BYTES:
                    _limit()
            if not alias_checks[key]:
                return False
        return True

    addresses: dict[tuple[str, str], dict[str, Any]] = {}
    address_sources: dict[str, set[str]] = defaultdict(set)
    uses: list[dict[str, Any]] = []

    def add_use(kind: str, source_id: str, binding: dict[str, Any], candidate_id: str | None,
                disposition: str, qualified: bool, *, role: str = 'read',
                candidate_address_id: str | None = None, predicate_id: str | None = None,
                output_id: str | None = None) -> None:
        address = None
        if candidate_id is not None:
            suffix = binding['suffix']
            if len(suffix) > MAX_ADDRESS_LENGTH or _ADDRESS.fullmatch('A' + suffix) is None:
                disposition = 'suffix_unsupported'
            else:
                key = (candidate_id, suffix)
                if key not in addresses:
                    root = roots[candidate_id]
                    status, member_id, data_type = suffix_evidence(root, suffix)
                    address = {'id': _id('address', candidate_id, suffix), 'candidate_id': candidate_id,
                               'root_id': root['id'], 'candidate_address_id': candidate_address_id,
                               'suffix': suffix, 'direction': root['direction'], 'disposition': status,
                               'backing_tag_id': root['backing_tag_id'] if status == 'associated' else None,
                               'backing_suffix': root['backing_suffix'] + suffix if status == 'associated' else None,
                               'member_element_id': member_id, 'data_type': data_type}
                    budget.retain(address)
                    addresses[key] = address
                address = addresses[key]
                address_sources[address['id']].add(kind)
                disposition = address['disposition']
                if qualified and not aliases_ok(binding, candidate_id):
                    disposition = 'alias_metadata_unqualified'
        if not qualified:
            disposition = 'source_unqualified'
        row = {'id': _id('use', kind, source_id), 'kind': kind, 'source_id': source_id,
               'candidate_id': candidate_id, 'address_id': address['id'] if address else None,
               'disposition': disposition, 'role': role,
               'predicate_node_id': predicate_id, 'output_id': output_id}
        budget.retain(row)
        uses.append(row)
        c[f'{kind}_uses_by_disposition'][disposition] += 1
        if disposition == 'associated':
            c['associated_uses_by_role'][role] += 1
            c['associated_predicate_uses'] += predicate_id is not None
            c['associated_output_uses'] += output_id is not None

    operands = {row['id']: row for row in access.operands}
    rungs = {row.id: row for row in inventory.rungs}
    for gap in binding_context.gaps:
        if gap['category'] != 'rack_unique_candidate':
            continue
        operand = operands[gap['source_id']]
        qualified = source_ok[rungs[operand['rung_id']].locator] and all(
            entity_ok[identifier] for identifier in operand['alias_chain'])
        add_use('rll', operand['id'], operand, gap['candidate_id'], 'associated', qualified,
                role=operand['role'], candidate_address_id=gap['candidate_address_id'],
                predicate_id=gap['predicate_node_id'], output_id=gap['output_id'])

    transitions = {row['id']: row for row in sfc_conditions.transitions}
    sfc_elements = {row['id']: row for row in sfc_structure.elements}
    for reference in sfc_conditions.references:
        if reference['binding_status'] == 'root_bound':
            continue
        transition = transitions[reference['transition_id']]
        binding = reference['binding']
        disposition, candidate_id = match_candidate(binding, reference['raw_text'], transition['scope_id'])
        element = sfc_elements[transition['transition_id']]
        qualified = (reference['binding_status'] != 'namespace_gap' and source_ok[element['locator']]
                     and all(entity_ok[identifier] for identifier in binding['alias_chain']))
        add_use('sfc', reference['id'], binding, candidate_id, disposition, qualified)

    for address in addresses.values():
        sources = address_sources[address['id']]
        c['rll_addresses'] += 'rll' in sources
        c['sfc_addresses'] += 'sfc' in sources
        c['shared_addresses'] += sources == {'rll', 'sfc'}
        c['addresses_by_direction'][address['direction']] += 1
        c['addresses_by_disposition'][address['disposition']] += 1
        if address['disposition'] == 'associated':
            c['associated_rll_addresses'] += 'rll' in sources
            c['associated_sfc_addresses'] += 'sfc' in sources
    c.update(roots_total=len(roots), addresses_total=len(addresses), uses_total=len(uses))
    partial = (c['roots_by_disposition']['associated'] != c['roots_total']
               or c['rll_uses_by_disposition']['associated'] + c['sfc_uses_by_disposition']['associated'] != c['uses_total'])
    return RackBackingContextResult(deepcopy(inventory.snapshot), 'partial' if partial else 'complete',
                                    list(roots.values()), list(addresses.values()), uses, c)


def analyze_rack_backing_context(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult, conditions: ConditionResult,
        binding_context: BindingContextResult, tag_data: TagDataResult,
        sfc_structure: SfcStructureResult, sfc_conditions: SfcConditionResult) -> RackBackingContextResult:
    try:
        validate_binding_context(snapshot, inventory, references, access, calculations, rung_analysis,
                                 relationships, conditions, binding_context)
        validate_tag_data(snapshot, inventory, tag_data)
        validate_sfc_conditions(snapshot, inventory, references, sfc_structure, sfc_conditions)
        result = _derive(snapshot, inventory, references, access, binding_context, tag_data,
                         sfc_structure, sfc_conditions)
        render_rack_backing_context_json(result)
        return result
    except RackBackingContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, IndexError, RecursionError, OverflowError):
        _invalid()


def validate_rack_backing_context(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult, conditions: ConditionResult,
        binding_context: BindingContextResult, tag_data: TagDataResult,
        sfc_structure: SfcStructureResult, sfc_conditions: SfcConditionResult,
        result: RackBackingContextResult) -> None:
    try:
        render_rack_backing_context_json(result)
        expected = analyze_rack_backing_context(snapshot, inventory, references, access, calculations,
            rung_analysis, relationships, conditions, binding_context, tag_data, sfc_structure, sfc_conditions)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except RackBackingContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_rack_backing_context_json(result: RackBackingContextResult) -> str:
    """Bound native values before rendering; canonical replay is separate."""
    try:
        if type(result) is not RackBackingContextResult or vars(result).keys() != set(RackBackingContextResult.__dataclass_fields__):
            _invalid()
        if sum(len(getattr(result, key)) for key in ('roots', 'addresses', 'uses')) > MAX_RECORDS:
            _limit()
        remaining, links = MAX_CONTEXT_BYTES, 0
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
                if type(value) is dict:
                    if any(type(key) is not str for key in value):
                        _invalid()
                    links += sum(key.endswith('_id') and item is not None for key, item in value.items())
                active.add(id(value))
                stack.append((iter(chain(value.keys(), value.values()) if type(value) is dict else value), id(value)))
            elif type(value) not in {int, bool, type(None)}:
                _invalid()
            if remaining < 0 or links > MAX_EVIDENCE_IDS:
                _limit()
        output, size = StringIO(), 0
        for chunk in json.JSONEncoder(ensure_ascii=True, sort_keys=True, indent=2).iterencode(vars(result)):
            size += len(chunk)
            if size + 1 > MAX_CONTEXT_BYTES:
                _limit()
            output.write(chunk)
        return output.getvalue() + '\n'
    except RackBackingContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
