"""Explain unresolved uses without promoting rack candidates to bound symbols.

This derived index is embedded in the private review. Source strings, alias
chains and module metadata remain in their existing authenticated companions.
Candidate logical addresses inhabit a separate namespace from exact addresses.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from io import StringIO
from itertools import chain
import json
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .conditions import ConditionResult, validate_conditions
from .models import InventoryResult, SourceSnapshot
from .references import MAX_ADDRESS_LENGTH, ReferenceResult, _ADDRESS, _strict_record_match
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult

MAX_CONTEXT_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 250_000
CATEGORIES = frozenset({
    'rack_unique_candidate', 'rack_suffix_invalid', 'rack_ambiguous_candidate',
    'rack_names_unavailable', 'rack_outside_scope', 'rack_no_match', 'rack_context_unavailable',
    'non_static_array_index', 'unsupported_address', 'undeclared_root', 'unresolved_scope',
    'alias_cycle', 'alias_depth_limit', 'ambiguous_root', 'invalid_expanded_suffix',
    'non_address_value', 'other_binding_gap',
})
CONTEXT_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'binding-context-1',
    'analysis_scope': 'unresolved_access_and_condition_context',
    'backing_mapping': 'not_analyzed', 'member_validation': 'not_implemented',
    'engineering_review': 'unreviewed',
}
COUNT_MAPS = {
    'gaps_by_kind': frozenset({'operand', 'expression'}),
    'gaps_by_role': frozenset({'read', 'write', 'read_write'}),
    'gaps_by_category': CATEGORIES, 'predicate_gap_categories': CATEGORIES,
    'output_gap_categories': CATEGORIES,
    'candidate_address_directions': frozenset({'input', 'output'}),
    'candidate_address_profiles': frozenset({'read_only', 'write_only', 'read_and_write'}),
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | {
    'source_rungs', 'source_instructions', 'source_operands', 'expression_uses',
    'operand_binding_gaps', 'operand_identity_gaps', 'expression_binding_gaps',
    'expression_identity_gaps', 'gap_uses_total', 'predicate_gap_uses',
    'predicate_gap_occurrences', 'output_gap_occurrences', 'candidate_addresses',
    'candidate_address_uses', 'candidate_roots',
}


class BindingContextError(ValueError):
    """Source-free context validation or resource rejection."""


def _invalid() -> None:
    raise BindingContextError('Binding context does not match its source evidence.')


def _limit() -> None:
    raise BindingContextError('Binding context exceeds its evidence limits.')


@dataclass(frozen=True)
class BindingContextResult:
    snapshot: dict[str, str | int]
    status: str
    gaps: list[dict[str, Any]]
    logical_addresses: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'binding-context-1'
    analysis_scope: str = 'unresolved_access_and_condition_context'
    backing_mapping: str = 'not_analyzed'
    member_validation: str = 'not_implemented'
    engineering_review: str = 'unreviewed'

    def to_dict(self) -> dict[str, Any]:
        render_binding_context_json(self)
        return deepcopy(vars(self))


def _derive(inventory: InventoryResult, references: ReferenceResult, access: AccessResult,
            relationships: RelationshipResult, conditions: ConditionResult) -> BindingContextResult:
    if max(len(access.operands), len(access.expression_uses), len(conditions.nodes)) > MAX_RECORDS:
        _limit()
    c = {key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()}
    c.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
    c.update(source_rungs=len(inventory.rungs), source_instructions=len(access.instructions),
             source_operands=len(access.operands), expression_uses=len(access.expression_uses))
    identities = {(r['kind'], r['id']) for r in relationships.identity_gaps}
    matches = {r['source_id']: r for group in ('direct_operands', 'alias_operands')
               for r in references.rack_candidates['matches'][group]}
    candidates = {r['source_id']: r for r in references.rack_candidates['candidates']}
    predicates = {operand: n['id'] for n in conditions.nodes if n['kind'] == 'predicate'
                  for operand in n['operand_ids']}
    outputs = {o['target_operand_id']: o['id'] for o in conditions.outputs
               if o['target_operand_id'] is not None and o['target_status'] != 'exact_address'}
    gaps: list[dict[str, Any]] = []
    addresses: dict[tuple[str, str], dict[str, Any]] = {}
    roles: dict[str, set[str]] = defaultdict(set)
    predicate_ids: set[str] = set()
    roots: set[str] = set()
    retained_bytes = 0

    def charge(record: Any) -> None:
        nonlocal retained_bytes
        retained_bytes += len(json.dumps(record, ensure_ascii=True, separators=(',', ':'))) + 1
        if retained_bytes > MAX_CONTEXT_BYTES:
            _limit()

    def category(row: dict[str, Any], kind: str, identity_gap: bool) -> tuple[str, str | None]:
        if identity_gap:
            return 'invalid_expanded_suffix', None
        status, reason = row['binding_status'], row.get('binding_reason')
        if status == 'unresolved' and reason == 'colon_root_not_declared':
            match = matches.get(row['id']) if kind == 'operand' else None
            if match is None:
                return 'rack_context_unavailable', None
            if match['status'] == 'unique_candidate':
                suffix = row['suffix']
                valid = len(suffix) <= MAX_ADDRESS_LENGTH and _ADDRESS.fullmatch('A' + suffix) is not None
                return ('rack_unique_candidate' if valid else 'rack_suffix_invalid'), match['candidate_id']
            return {
                'ambiguous_candidate': 'rack_ambiguous_candidate',
                'candidate_names_unavailable': 'rack_names_unavailable',
                'outside_visible_scope': 'rack_outside_scope',
                'no_candidate_match': 'rack_no_match',
            }[match['status']], None
        if status == 'unsupported_address':
            return ('non_static_array_index' if reason == 'non_static_array_index' else 'unsupported_address'), None
        if status == 'unresolved':
            return ('undeclared_root' if reason == 'root_not_declared' else 'unresolved_scope'), None
        return {
            'alias_cycle': 'alias_cycle', 'alias_depth_limit': 'alias_depth_limit',
            'ambiguous': 'ambiguous_root', 'literal': 'non_address_value',
            'system_flag': 'non_address_value',
        }.get(status, 'other_binding_gap'), None

    for kind, records in (('operand', access.operands), ('expression', access.expression_uses)):
        for row in records:
            role, status = row['role'], row['binding_status']
            if role not in {'read', 'write', 'read_write'}:
                continue
            binding_gap = (status != 'root_bound' if kind == 'expression' or role != 'read'
                           else status not in {'root_bound', 'literal', 'system_flag'})
            identity_gap = (kind, row['id']) in identities
            if not binding_gap and not identity_gap:
                continue
            if len(gaps) >= MAX_RECORDS:
                _limit()
            label, candidate = category(row, kind, identity_gap)
            address_id = None
            if label == 'rack_unique_candidate':
                key = (candidate, row['suffix'])
                if key not in addresses:
                    if len(addresses) >= MAX_RECORDS:
                        _limit()
                    digest = hashlib.sha256('\0'.join((inventory.snapshot['id'], *key)).encode()).hexdigest()
                    address = {'id': 'candidate_address_' + digest, 'candidate_id': candidate,
                               'suffix': row['suffix'], 'operand_ids': [], 'expression_use_ids': [],
                               'profile': 'read_only'}
                    charge(address)
                    addresses[key] = address
                    roots.add(candidate)
                    c['candidate_address_directions'][candidates[candidate]['direction']] += 1
                address = addresses[key]
                address_id = address['id']
                charge(row['id'])
                address['operand_ids' if kind == 'operand' else 'expression_use_ids'].append(row['id'])
                roles[address_id].add(role)
                c['candidate_address_uses'] += 1
            predicate_id = predicates.get(row['id']) if kind == 'operand' else None
            output_id = outputs.get(row['id']) if kind == 'operand' else None
            gap = {'source_id': row['id'], 'kind': kind, 'category': label,
                   'candidate_id': candidate, 'candidate_address_id': address_id,
                   'predicate_node_id': predicate_id, 'output_id': output_id}
            charge(gap)
            gaps.append(gap)
            c['gaps_by_kind'][kind] += 1
            c['gaps_by_role'][role] += 1
            c['gaps_by_category'][label] += 1
            c[f'{kind}_binding_gaps'] += int(binding_gap)
            c[f'{kind}_identity_gaps'] += int(identity_gap)
            if predicate_id:
                predicate_ids.add(predicate_id)
                c['predicate_gap_uses'] += 1
                c['predicate_gap_categories'][label] += 1
            if output_id:
                c['output_gap_occurrences'] += 1
                c['output_gap_categories'][label] += 1
    for row in addresses.values():
        profile = roles[row['id']]
        read, write = bool(profile & {'read', 'read_write'}), bool(profile & {'write', 'read_write'})
        row['profile'] = 'read_and_write' if read and write else 'read_only' if read else 'write_only'
        c['candidate_address_profiles'][row['profile']] += 1
    c.update(gap_uses_total=len(gaps), predicate_gap_occurrences=len(predicate_ids),
             candidate_roots=len(roots), candidate_addresses=len(addresses))
    return BindingContextResult(deepcopy(inventory.snapshot), 'partial' if gaps else 'complete',
                                gaps, list(addresses.values()), c)


def analyze_binding_context(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                            access: AccessResult, calculations: CalculationResult,
                            rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
                            conditions: ConditionResult) -> BindingContextResult:
    try:
        validate_conditions(snapshot, inventory, references, access, calculations, rung_analysis,
                            relationships, conditions)
        if conditions.schema_version != 2 or access.schema_version != 4:
            _invalid()
        result = _derive(inventory, references, access, relationships, conditions)
        render_binding_context_json(result)
        return result
    except BindingContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_binding_context(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                             access: AccessResult, calculations: CalculationResult,
                             rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
                             conditions: ConditionResult, result: BindingContextResult) -> None:
    try:
        render_binding_context_json(result)
        expected = analyze_binding_context(snapshot, inventory, references, access, calculations,
                                           rung_analysis, relationships, conditions)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except BindingContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_binding_context_json(result: BindingContextResult) -> str:
    """Bound native values before encoding; canonical authentication is separate."""
    try:
        if type(result) is not BindingContextResult or vars(result).keys() != set(BindingContextResult.__dataclass_fields__):
            _invalid()
        payload = vars(result)
        remaining = MAX_CONTEXT_BYTES
        stack: list[tuple[Any, int | None]] = [(iter((payload,)), None)]
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
                if type(value) is dict and any(type(k) is not str for k in value):
                    _invalid()
                active.add(id(value))
                stack.append((iter(chain(value.keys(), value.values()) if type(value) is dict else value), id(value)))
            elif type(value) not in {int, bool, type(None)}:
                _invalid()
            if remaining < 0:
                _limit()
        output, size = StringIO(), 0
        for chunk in json.JSONEncoder(ensure_ascii=True, sort_keys=True, indent=2).iterencode(payload):
            size += len(chunk)
            if size + 1 > MAX_CONTEXT_BYTES:
                _limit()
            output.write(chunk)
        return output.getvalue() + '\n'
    except BindingContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
