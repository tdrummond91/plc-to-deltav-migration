"""Source relationships around parsed SFC references, never chart execution.

Exact expanded addresses are interned once. RLL evidence is namespace-qualified
per occurrence; chart-step links are declaration/member candidates. Lexical gap
hints remain explicitly unbound and cannot become address relationships.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from functools import cache
from io import StringIO
import json
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .models import InventoryResult, SourceSnapshot
from .output_context import _provenance
from .references import ReferenceResult, _Resolver, _address, _strict_record_match
from .relationships import RelationshipResult, _identifier, validate_relationships
from .rung_analysis import RungAnalysisResult
from .sfc_conditions import SfcConditionResult, validate_sfc_conditions
from .sfc_structure import SfcStructureResult
from .sfr_context import SfrContextResult, validate_sfr_context
from .source import _read_nodes
from .tag_data import _namespace

MAX_SFC_CONTEXT_BYTES = 16 * 1024 * 1024
MAX_SFC_CONTEXT_JSON_BYTES = 16 * 1024 * 1024
MAX_SFC_CONTEXT_RECORDS = 250_000
MAX_EVIDENCE_IDS = 1_000_000
ROLES = frozenset({'read', 'write', 'read_write', 'unknown'})
COUNT_MAPS = {
    'references_by_status': frozenset({'exact_address', 'binding_gap', 'namespace_gap'}),
    'accepted_operands_by_role': ROLES, 'rejected_operands_by_role': ROLES,
    'step_links_by_evidence': frozenset({'bound_identity', 'lexical_hint'}),
    'step_links_by_relation': frozenset({'same_content', 'other_edit', 'peer_chart'}),
    'step_links_by_match': frozenset({'exact', 'base_member'}),
    'gaps_by_kind': frozenset({'root_missing', 'alias_chain_gap', 'other'}),
    'gaps_by_lexical_kind': frozenset({'boolean_word', 'other'}),
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | frozenset({
    'source_transitions', 'source_references', 'source_steps', 'source_rll_addresses',
    'source_operands', 'source_expression_uses', 'references_total', 'addresses_total',
    'step_links_total', 'gaps_total', 'references_with_step_links',
    'references_with_multiple_steps', 'addresses_with_rll_evidence',
    'addresses_with_rll_readers', 'addresses_with_rll_writers',
    'addresses_with_unknown_roles', 'addresses_with_rejected_uses',
    'accepted_expression_uses', 'rejected_expression_uses',
    'unqualified_step_links', 'outside_scope_declarations',
    'unqualified_outside_scope_declarations', 'gaps_with_outside_declarations',
    'gaps_with_lexical_steps', 'source_unparsed_transitions',
})
SFC_CONTEXT_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'sfc-context-1',
    'analysis_scope': 'sfc_reference_source_relationships',
    'address_identity': 'exact_expanded_spelling', 'execution_analysis': 'not_implemented',
    'type_analysis': 'not_implemented', 'overlap_analysis': 'not_implemented',
    'edit_selection': 'not_implemented', 'engineering_review': 'unreviewed',
}


class SfcContextError(ValueError):
    """Source-free rejection for inconsistent or excessive evidence."""


def _invalid() -> None:
    raise SfcContextError('SFC context evidence is inconsistent or exceeds its limits.') from None


@dataclass(frozen=True)
class SfcContextResult:
    snapshot: dict[str, str | int]
    status: str
    references: list[dict[str, Any]]
    addresses: list[dict[str, Any]]
    step_links: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'sfc-context-1'
    analysis_scope: str = 'sfc_reference_source_relationships'
    address_identity: str = 'exact_expanded_spelling'
    execution_analysis: str = 'not_implemented'
    type_analysis: str = 'not_implemented'
    overlap_analysis: str = 'not_implemented'
    edit_selection: str = 'not_implemented'
    engineering_review: str = 'unreviewed'

    def to_dict(self) -> dict[str, Any]:
        render_sfc_context_json(self)
        return deepcopy(vars(self))


class _Budget:
    def __init__(self) -> None:
        self.records = self.bytes = self.ids = 0

    def retain(self, row: dict[str, Any]) -> None:
        self.records += 1
        self.bytes += len(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self.records > MAX_SFC_CONTEXT_RECORDS or self.bytes > MAX_SFC_CONTEXT_BYTES:
            _invalid()

    def link(self, amount: int = 1) -> None:
        self.ids += amount
        # Reserve space as associations accumulate, before a large address or
        # gap can finish construction. This is deliberately conservative.
        self.bytes += 96 * amount
        if self.ids > MAX_EVIDENCE_IDS or self.bytes > MAX_SFC_CONTEXT_BYTES:
            _invalid()


def _qualified_source(snapshot: SourceSnapshot, inventory: InventoryResult):
    """Qualify non-rung binding chains, including implicit I/O name ancestry.

The existing RLL provenance helper is reused for RLL occurrences. This matching
non-rung qualifier also rejects namespaced attributes on SFC/source entities;
it does not manufacture a rung to authenticate a chart binding.
"""
    nodes = _read_nodes(snapshot.data)
    namespace = _namespace(nodes[0].expanded_name)
    supported: dict[str, bool] = {}
    for node in nodes:
        supported[node.locator] = (_namespace(node.expanded_name) == namespace
            and all('}' not in key for key in node.expanded_attributes)
            and (node.parent is None or supported[nodes[node.parent].locator]))
    entities = {row.id: row for row in inventory.entities}
    modules: dict[tuple[str | None, str], list[Any]] = defaultdict(list)
    ports: dict[str, list[Any]] = defaultdict(list)
    for row in inventory.entities:
        if row.kind == 'module' and row.name:
            modules[row.scope_id, row.name.lower()].append(row)
        elif row.kind == 'module_port':
            ports[row.parent_id].append(row)

    @cache
    def entity_ok(identifier: str) -> bool:
        entity = entities.get(identifier)
        if entity is None or not supported[entity.locator]:
            return False
        if entity.kind not in {'module_input_tag', 'module_output_tag', 'module_config_tag'} or entity.name is not None:
            return True
        current = entities.get(entity.parent_id)
        if current is not None and current.kind == 'module_connection':
            current = entities.get(current.parent_id)
        seen: set[str] = set()
        for _ in range(64):
            if current is None or current.kind != 'module' or not supported[current.locator]:
                return False
            if any(not supported[row.locator] for row in ports[current.id]) or current.id in seen:
                return False
            seen.add(current.id)
            parent_name = current.attributes.get('ParentModule')
            if parent_name is None and current.name and current.name.lower() == 'local':
                parent_name = current.name
            parents = modules.get((current.scope_id, (parent_name or '').lower()), [])
            if len(parents) != 1:
                return False
            parent = parents[0]
            if parent.id == current.id:
                return True
            current = parent
        return False

    def binding_ok(binding: dict[str, Any]) -> bool:
        return all(entity_ok(identifier) for identifier in
            [binding['symbol_id'], *binding['alias_chain'], binding['target_id']] if identifier is not None)

    return supported, entity_ok, binding_ok


def _partial(c: dict[str, Any]) -> bool:
    return bool(c['gaps_total'] or c['source_unparsed_transitions']
        or sum(c['rejected_operands_by_role'].values()) or c['rejected_expression_uses']
        or c['accepted_operands_by_role']['unknown'] or c['unqualified_step_links'])


def _match(reference_suffix: str, step_suffix: str) -> str | None:
    if reference_suffix == step_suffix:
        return 'exact'
    # A literal member delimiter is required: .X never matches .XY, and a
    # whole array never implies an indexed element or equivalent index spelling.
    return 'base_member' if reference_suffix.startswith(step_suffix + '.') else None


def _suffix_candidates(suffix: str) -> list[str]:
    """Only exact spelling and prefixes ending immediately before a dot.

    Lookup work depends on bounded address length, not the number of unrelated
    steps sharing the same root. Array brackets are deliberately not cut.
    """
    return [suffix, *(suffix[:offset] for offset, char in enumerate(suffix) if char == '.')]


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, access: AccessResult,
        relationships: RelationshipResult, sfc_structure: SfcStructureResult,
        sfr_context: SfrContextResult, sfc_conditions: SfcConditionResult) -> SfcContextResult:
    populations = (inventory.entities, inventory.rungs, access.operands, access.expression_uses,
                   relationships.addresses, sfc_structure.elements, sfr_context.steps,
                   sfc_conditions.transitions, sfc_conditions.references)
    if any(len(rows) > MAX_SFC_CONTEXT_RECORDS for rows in populations):
        _invalid()
    budget = _Budget()
    supported, entity_ok, binding_ok = _qualified_source(snapshot, inventory)
    _, rung_binding_ok, _ = _provenance(snapshot, inventory)
    entities = {row.id: row for row in inventory.entities}
    elements = {row['id']: row for row in sfc_structure.elements}
    transitions = {row['id']: row for row in sfc_conditions.transitions}
    operands = {row['id']: row for row in access.operands}
    expressions = {row['id']: row for row in access.expression_uses}
    rll_addresses = {(row['target_id'], row['suffix']): row for row in relationships.addresses}
    resolver = _Resolver(inventory)
    names: dict[str, list[Any]] = defaultdict(list)
    for (_, name), group in resolver.index.items():
        names[name].extend(group)
    # Index by bound target or lexical root. Only same-scope lexical hints are
    # considered; outside-scope declarations have their own explicit category.
    bound_steps: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    lexical_steps: dict[tuple[str | None, str, str], list[dict[str, Any]]] = defaultdict(list)
    step_order = {step['element_id']: ordinal for ordinal, step in enumerate(sfr_context.steps)}
    step_qualified: dict[str, bool] = {}
    for step in sfr_context.steps:
        element = elements[step['element_id']]
        routine = entities[step['routine_id']]
        okay = supported[element['locator']] and binding_ok(step)
        step_qualified[step['element_id']] = okay
        if step['binding_status'] == 'root_bound' and okay:
            bound_steps[step['target_id'], step['suffix']].append(step)
        raw = element['attributes'].get('Operand', '')
        parsed, _ = _address(raw.strip())
        if parsed is not None:
            lexical_steps[routine.scope_id, parsed[0].lower(), parsed[1]].append({**step, 'lexical_suffix': parsed[1]})
    c = {key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()}
    c.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
    c.update(source_transitions=len(sfc_conditions.transitions), source_references=len(sfc_conditions.references),
             source_steps=len(sfr_context.steps), source_rll_addresses=len(relationships.addresses),
             source_operands=len(access.operands), source_expression_uses=len(access.expression_uses),
             source_unparsed_transitions=sfc_conditions.coverage['transitions_by_status']['unsupported'])
    references, addresses, step_links, gaps = [], {}, [], []

    def link_step(reference: dict[str, Any], step: dict[str, Any], evidence: str, match: str) -> str:
        identifier = _identifier('sfc_context_step_', reference['id'], step['element_id'], evidence)
        relation = ('same_content' if reference['content_id'] == step['content_id'] else
                    'other_edit' if reference['routine_id'] == step['routine_id'] else 'peer_chart')
        row = {'id': identifier, 'reference_id': reference['id'], 'step_element_id': step['element_id'],
               'step_content_id': step['content_id'], 'step_routine_id': step['routine_id'],
               'relation': relation, 'evidence': evidence, 'match_kind': match,
               'step_binding_status': step['binding_status'],
               'namespace_qualified': step_qualified[step['element_id']]}
        budget.retain(row)
        budget.link()
        step_links.append(row)
        reference['step_link_ids'].append(identifier)
        c['step_links_by_evidence'][evidence] += 1
        c['step_links_by_relation'][relation] += 1
        c['step_links_by_match'][match] += 1
        c['unqualified_step_links'] += not row['namespace_qualified']
        return identifier

    for source in sfc_conditions.references:
        transition = transitions[source['transition_id']]
        status = ('namespace_gap' if source['binding_status'] == 'namespace_gap'
                  or not binding_ok(source['binding']) else
                  'exact_address' if source['binding_status'] == 'root_bound' else 'binding_gap')
        row = {'id': _identifier('sfc_context_reference_', source['id']),
               'condition_reference_id': source['id'], 'transition_id': source['transition_id'],
               'content_id': transition['content_id'], 'routine_id': transition['routine_id'],
               'scope_id': transition['scope_id'], 'edit_kind': transition['edit_kind'],
               'address_id': None, 'status': status, 'binding_status': source['binding_status'],
               'step_link_ids': [], 'gap_id': None}
        if status == 'exact_address':
            key = tuple(source['address_key'])
            if key not in addresses:
                prior = rll_addresses.get(key)
                address = {'id': _identifier('sfc_context_address_', inventory.snapshot['id'], *key),
                           'target_id': key[0], 'suffix': key[1], 'condition_reference_ids': [],
                           'relationship_address_id': prior['id'] if prior else None,
                           **{f'{role}_operand_ids': [] for role in sorted(ROLES)},
                           'unqualified_operand_ids_by_role': {role: [] for role in sorted(ROLES)},
                           'expression_use_ids': [], 'unqualified_expression_use_ids': []}
                if prior is not None:
                    for role in sorted(ROLES):
                        for identifier in prior[f'{role}_operand_ids']:
                            accepted = rung_binding_ok(operands[identifier])
                            bucket = address[f'{role}_operand_ids'] if accepted else address['unqualified_operand_ids_by_role'][role]
                            budget.link()
                            bucket.append(identifier)
                            c['accepted_operands_by_role' if accepted else 'rejected_operands_by_role'][role] += 1
                    for identifier in prior['expression_use_ids']:
                        accepted = rung_binding_ok(expressions[identifier])
                        budget.link()
                        address['expression_use_ids' if accepted else 'unqualified_expression_use_ids'].append(identifier)
                        c['accepted_expression_uses' if accepted else 'rejected_expression_uses'] += 1
                addresses[key] = address
            address = addresses[key]
            row['address_id'] = address['id']
            budget.link()
            address['condition_reference_ids'].append(source['id'])
            candidates = [step for suffix in _suffix_candidates(key[1])
                          for step in bound_steps.get((key[0], suffix), [])]
            candidates.sort(key=lambda step: step_order[step['element_id']])
            for step in candidates:
                match = _match(key[1], step['suffix'])
                if match is not None:
                    link_step(row, step, 'bound_identity', match)
        else:
            binding = source['binding']
            kind = ('alias_chain_gap' if binding['status'] != 'root_bound' and binding['alias_chain'] else 'root_missing'
                    if binding['status'] == 'unresolved' and binding['symbol_id'] is None
                    and binding['reason'] in {'root_not_declared', 'colon_root_not_declared'} else 'other')
            lexical = 'boolean_word' if source['raw_text'].upper() in {'TRUE', 'FALSE'} else 'other'
            parsed, _ = _address(source['raw_text'])
            lookup_scope = transition['scope_id']
            if binding['alias_chain']:
                alias = entities[binding['alias_chain'][-1]]
                parsed, _ = _address(alias.attributes.get('AliasFor', ''))
                lookup_scope = alias.scope_id
            root = parsed[0] if parsed else None
            gap = {'id': _identifier('sfc_context_gap_', source['id']), 'reference_id': row['id'],
                   'kind': kind, 'lexical_kind': lexical, 'lookup_scope_id': lookup_scope,
                   'root_text': root, 'outside_scope_entity_ids': [],
                   'unqualified_outside_scope_entity_ids': [], 'lexical_step_link_ids': []}
            row['gap_id'] = gap['id']
            scope = entities.get(lookup_scope)
            eligible = {lookup_scope}
            if scope is not None and scope.kind == 'program':
                eligible.add(scope.scope_id)
            if root is not None:
                for declaration in names.get(root.lower(), []):
                    if declaration.scope_id not in eligible:
                        accepted = entity_ok(declaration.id)
                        bucket = 'outside_scope_entity_ids' if accepted else 'unqualified_outside_scope_entity_ids'
                        budget.link()
                        gap[bucket].append(declaration.id)
                        c['outside_scope_declarations' if accepted else 'unqualified_outside_scope_declarations'] += 1
            # Use the original condition spelling, never the unresolved final
            # alias target, for visible step-operand lexical hints.
            original, _ = _address(source['raw_text'])
            if original is not None:
                candidates = [step for suffix in _suffix_candidates(original[1])
                              for step in lexical_steps.get((transition['scope_id'], original[0].lower(), suffix), [])]
                candidates.sort(key=lambda step: step_order[step['element_id']])
                for step in candidates:
                    match = _match(original[1], step['lexical_suffix'])
                    if match is not None:
                        identifier = link_step(row, step, 'lexical_hint', match)
                        budget.link()
                        gap['lexical_step_link_ids'].append(identifier)
            c['gaps_by_kind'][kind] += 1
            c['gaps_by_lexical_kind'][lexical] += 1
            c['gaps_with_outside_declarations'] += bool(gap['outside_scope_entity_ids'] or gap['unqualified_outside_scope_entity_ids'])
            c['gaps_with_lexical_steps'] += bool(gap['lexical_step_link_ids'])
            budget.retain(gap)
            gaps.append(gap)
        c['references_by_status'][status] += 1
        c['references_with_step_links'] += bool(row['step_link_ids'])
        c['references_with_multiple_steps'] += len(row['step_link_ids']) > 1
        budget.retain(row)
        references.append(row)
    for address in addresses.values():
        readers = bool(address['read_operand_ids'] or address['read_write_operand_ids'] or address['expression_use_ids'])
        writers = bool(address['write_operand_ids'] or address['read_write_operand_ids'])
        unknown = bool(address['unknown_operand_ids'])
        c['addresses_with_rll_evidence'] += readers or writers or unknown
        c['addresses_with_rll_readers'] += readers
        c['addresses_with_rll_writers'] += writers
        c['addresses_with_unknown_roles'] += unknown
        c['addresses_with_rejected_uses'] += bool(address['unqualified_expression_use_ids'] or any(address['unqualified_operand_ids_by_role'].values()))
        budget.retain(address)
    c.update(references_total=len(references), addresses_total=len(addresses), step_links_total=len(step_links), gaps_total=len(gaps))
    return SfcContextResult(deepcopy(inventory.snapshot), 'partial' if _partial(c) else 'complete',
                            references, list(addresses.values()), step_links, gaps, c)


def analyze_sfc_context(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        sfc_structure: SfcStructureResult, sfr_context: SfrContextResult,
        sfc_conditions: SfcConditionResult) -> SfcContextResult:
    try:
        validate_relationships(snapshot, inventory, references, access, calculations, rung_analysis, relationships)
        validate_sfr_context(snapshot, inventory, references, access, calculations, sfc_structure, sfr_context)
        validate_sfc_conditions(snapshot, inventory, references, sfc_structure, sfc_conditions)
        result = _derive(snapshot, inventory, access, relationships, sfc_structure, sfr_context, sfc_conditions)
        render_sfc_context_json(result)
        return result
    except SfcContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_sfc_context(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        sfc_structure: SfcStructureResult, sfr_context: SfrContextResult,
        sfc_conditions: SfcConditionResult, result: SfcContextResult) -> None:
    try:
        render_sfc_context_json(result)
        expected = analyze_sfc_context(snapshot, inventory, references, access, calculations,
            rung_analysis, relationships, sfc_structure, sfr_context, sfc_conditions)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except SfcContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_sfc_context_json(result: SfcContextResult) -> str:
    try:
        if type(result) is not SfcContextResult or vars(result).keys() != set(SfcContextResult.__dataclass_fields__):
            _invalid()
        remaining, identifiers = MAX_SFC_CONTEXT_BYTES, 0
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
            remaining -= 1
            if len(frames) > 12:
                _invalid()
            if type(value) in (dict, list):
                identifier = id(value)
                if identifier in active or len(value) > MAX_SFC_CONTEXT_RECORDS:
                    _invalid()
                active.add(identifier)
                if type(value) is dict:
                    if any(type(key) is not str for key in value):
                        _invalid()
                    remaining -= sum(len(key.encode('utf-8')) for key in value)
                    frames.append((iter(value.values()), identifier))
                else:
                    identifiers += len(value)
                    frames.append((iter(value), identifier))
            elif type(value) is str:
                remaining -= len(value.encode('utf-8'))
            elif type(value) not in (int, bool, type(None)):
                _invalid()
            if remaining < 0 or identifiers > MAX_EVIDENCE_IDS:
                _invalid()
        if sum(len(getattr(result, key)) for key in ('references', 'addresses', 'step_links', 'gaps')) > MAX_SFC_CONTEXT_RECORDS:
            _invalid()
        output, size = StringIO(), 1
        for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).iterencode(vars(result)):
            size += len(chunk.encode('utf-8'))
            if size > MAX_SFC_CONTEXT_JSON_BYTES:
                _invalid()
            output.write(chunk)
        return output.getvalue() + '\n'
    except SfcContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
