"""Private, occurrence-preserving symbolic context for indirect operands.

This companion never changes existing bindings or manufactures an element by
substituting an index value. Index references are possible reads used to select
an element, not execution, bounds, loop, or initialization evidence. Complete
address envelopes are parsed before any partial evidence is retained.
"""
from __future__ import annotations

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
from .references import (
    ReferenceResult, _ADDRESS, _INDEX_TOKEN, _ROOT, _Resolver, _address,
    _index_expression, _literal, _strict_record_match,
)
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult

MAX_INDEXED_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 250_000
MAX_ADDRESS_CHARS = 4096
MAX_TOKENS = 512
MAX_SELECTORS = 64
MAX_DEPTH = 64
MAX_EVIDENCE_IDS = 1_000_000
BINDINGS = frozenset({'root_bound', 'unresolved', 'ambiguous', 'alias_cycle',
                      'alias_depth_limit', 'unsupported_address', 'invalid_expanded_suffix'})
DISPOSITIONS = frozenset({'symbolic', 'unknown_role', 'expression_dynamic', 'expression_unsupported',
                         'alias_target_dynamic', 'unsupported_grammar', 'resource_limit'})
ROLES = frozenset({'read', 'write', 'read_write', 'unknown', 'non_data', 'expression_read'})
INDEXED_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'indexed-access-1',
    'analysis_scope': 'symbolic_indexed_operands',
    'exact_element_analysis': 'not_implemented', 'range_analysis': 'not_implemented',
    'execution_analysis': 'not_implemented', 'engineering_review': 'unreviewed',
}
COUNT_MAPS = {
    'uses_by_kind': frozenset({'operand', 'expression', 'alias'}),
    'uses_by_role': ROLES, 'uses_by_disposition': DISPOSITIONS,
    'root_bindings': BINDINGS, 'index_bindings': BINDINGS,
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | {
    'source_rungs', 'source_instructions', 'source_operands', 'expression_uses', 'source_aliases',
    'uses_total', 'symbolic_uses', 'selectors_total', 'dynamic_selectors',
    'index_read_occurrences', 'root_bound_uses', 'bound_index_reads',
}
_MEMBER = re.compile(r'\.(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+)', re.ASCII)


class IndexedAccessError(ValueError):
    """Source-free canonical or resource validation failure."""


def _invalid() -> None:
    raise IndexedAccessError('Indexed access does not match its source evidence.')


def _limit() -> None:
    raise IndexedAccessError('Indexed access exceeds its evidence limits.')


class _Unsupported(ValueError):
    pass


class _TooLarge(ValueError):
    pass


@dataclass(frozen=True)
class IndexedAccessResult:
    snapshot: dict[str, str | int]
    status: str
    uses: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'indexed-access-1'
    analysis_scope: str = 'symbolic_indexed_operands'
    exact_element_analysis: str = 'not_implemented'
    range_analysis: str = 'not_implemented'
    execution_analysis: str = 'not_implemented'
    engineering_review: str = 'unreviewed'

    def to_dict(self) -> dict[str, Any]:
        render_indexed_access_json(self)
        return deepcopy(vars(self))


def _parse(raw: str) -> tuple[str, int, int, list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse the entire existing narrow grammar, retaining original offsets.

    Selectors are individual dimensions in source order. Their offsets exclude
    surrounding whitespace and delimiters; reads are individual occurrences.
    No expression is evaluated, even when all its tokens are integer literals.
    """
    if len(raw) > MAX_ADDRESS_CHARS:
        raise _TooLarge
    left = len(raw) - len(raw.lstrip())
    value = raw.strip()
    root = _ROOT.match(value)
    if root is None or value.lower().startswith('program:') or '\\' in value:
        raise _Unsupported
    cursor = root.end()
    selectors: list[dict[str, Any]] = []
    reads: list[dict[str, Any]] = []
    token_count = 1
    group = 0
    while cursor < len(value):
        if value[cursor] == '.':
            member = _MEMBER.match(value, cursor)
            if member is None:
                raise _Unsupported
            cursor = member.end()
            token_count += 1
            # A numeric bit selector is terminal in the inherited grammar.
            if member[0][1:].isdigit() and cursor != len(value):
                raise _Unsupported
        elif value[cursor] == '[':
            end = value.find(']', cursor + 1)
            if end < 0 or '[' in value[cursor + 1:end]:
                raise _Unsupported
            slot_start = cursor + 1
            slots = value[slot_start:end].split(',')
            for dimension, slot in enumerate(slots):
                expression = slot.strip()
                start = slot_start + len(slot) - len(slot.lstrip())
                stop = start + len(expression)
                if not expression:
                    raise _Unsupported
                dynamic = re.fullmatch('[0-9]+', expression) is None
                if dynamic and not _index_expression(expression):
                    raise _Unsupported
                selector_index = len(selectors)
                if selector_index >= MAX_SELECTORS:
                    raise _TooLarge
                selectors.append({'start': left + start, 'end': left + stop,
                                  'group_index': group, 'dimension_index': dimension,
                                  'dynamic': dynamic})
                position = depth = 0
                while position < len(expression):
                    token = _INDEX_TOKEN.match(expression, position)
                    if token is None:
                        raise _Unsupported
                    position = token.end()
                    token_count += 1
                    if token_count > MAX_TOKENS:
                        raise _TooLarge
                    if token['operator'] == '(':
                        depth += 1
                        if depth > MAX_DEPTH:
                            raise _TooLarge
                    elif token['operator'] == ')':
                        depth -= 1
                    if token['name'] is not None:
                        reads.append({'selector_index': selector_index,
                                      'start': left + start + token.start('name'),
                                      'end': left + start + token.end('name')})
                slot_start += len(slot) + 1
            group += 1
            cursor = end + 1
        else:
            raise _Unsupported
        if token_count > MAX_TOKENS:
            raise _TooLarge
    return root[0], left, left + root.end(), selectors, reads


def _checked_binding(resolver: _Resolver, raw: str, scope_id: str | None) -> dict[str, Any]:
    binding = resolver.resolve(raw, scope_id)
    if binding['status'] == 'root_bound' and _ADDRESS.fullmatch('R' + binding['suffix']) is None:
        # A root can resolve while alias concatenation produces a bad address.
        binding.update(status='invalid_expanded_suffix', target_id=None, reason='invalid_expanded_suffix')
    return binding


def _candidate(raw: str, reason: str | None) -> bool:
    if reason == 'non_static_array_index':
        return True  # Also retain an alias whose unsupported target caused it.
    # Unknown-role slots lack a resolver result. Malformed bracketed addresses
    # remain visible, but valid static addresses are outside this companion.
    return '[' in raw and not _literal(raw.strip()) and _address(raw)[0] is None


def _derive(inventory: InventoryResult, references: ReferenceResult, access: AccessResult,
            calculations: CalculationResult) -> IndexedAccessResult:
    if max(len(access.operands), len(access.expression_uses), len(references.aliases)) > MAX_RECORDS:
        _limit()
    coverage = {key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()}
    coverage.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
    coverage.update(source_rungs=len(inventory.rungs), source_instructions=len(access.instructions),
                    source_operands=len(access.operands), expression_uses=len(access.expression_uses),
                    source_aliases=len(references.aliases))
    resolver = _Resolver(inventory)
    source_operands = {row['id']: row for row in references.operands}
    source_nodes = {row['id']: row for row in calculations.nodes}
    uses: list[dict[str, Any]] = []
    retained_bytes = evidence_ids = 0

    def add(kind: str, row: dict[str, Any], raw: str, scope_id: str | None,
            source_id: str, role: str, reason: str | None) -> None:
        nonlocal retained_bytes, evidence_ids
        if not _candidate(raw, reason):
            return
        if len(uses) >= MAX_RECORDS:
            _limit()
        identifier = 'indexed_use_' + hashlib.sha256(f'{kind}\0{source_id}'.encode()).hexdigest()
        record = {'id': identifier, 'kind': kind, 'source_id': source_id,
                  'instruction_id': row.get('instruction_id'), 'rung_id': row.get('rung_id'),
                  'role': role, 'disposition': 'symbolic', 'root_start': None, 'root_end': None,
                  'root_binding': None, 'selectors': [], 'index_reads': []}
        if kind == 'expression':
            record['disposition'] = 'expression_unsupported' if role == 'expression_read' else 'expression_dynamic'
        elif kind == 'alias':
            record['disposition'] = 'alias_target_dynamic'
        elif role not in {'read', 'write', 'read_write'}:
            record['disposition'] = 'unknown_role'
        else:
            try:
                root, root_start, root_end, selectors, reads = _parse(raw)
                if not any(s['dynamic'] for s in selectors):
                    # A static source operand can inherit a dynamic alias target.
                    record['disposition'] = 'alias_target_dynamic' if reason == 'non_static_array_index' else 'unsupported_grammar'
                else:
                    binding = _checked_binding(resolver, root, scope_id)
                    if binding['status'] == 'root_bound':
                        try:
                            # Validate composed syntax symbolically, retaining its
                            # expressions; never invent an index value or element.
                            _parse('R' + binding['suffix'] + raw[root_end:].rstrip())
                        except _Unsupported:
                            binding.update(status='invalid_expanded_suffix', target_id=None,
                                           reason='invalid_expanded_suffix')
                        except _TooLarge:
                            binding.update(status='unsupported_address', target_id=None,
                                           reason='expanded_suffix_limit')
                    record.update(root_start=root_start, root_end=root_end, root_binding=binding,
                                  selectors=selectors)
                    for occurrence, read in enumerate(reads):
                        read_binding = _checked_binding(resolver, raw[read['start']:read['end']], scope_id)
                        read_id = 'index_read_' + hashlib.sha256(f'{identifier}\0{occurrence}'.encode()).hexdigest()
                        record['index_reads'].append({'id': read_id, **read, 'binding': read_binding})
                    coverage['symbolic_uses'] += 1
                    coverage['selectors_total'] += len(selectors)
                    coverage['dynamic_selectors'] += sum(s['dynamic'] for s in selectors)
                    coverage['index_read_occurrences'] += len(reads)
                    coverage['root_bindings'][binding['status']] += 1
                    coverage['root_bound_uses'] += int(binding['status'] == 'root_bound')
                    for read in record['index_reads']:
                        coverage['index_bindings'][read['binding']['status']] += 1
                        coverage['bound_index_reads'] += int(read['binding']['status'] == 'root_bound')
            except _TooLarge:
                record['disposition'] = 'resource_limit'
            except _Unsupported:
                record['disposition'] = 'unsupported_grammar'
        # Bound every retained population and link, not merely the outer list.
        evidence_ids += 4 + sum(len(b['alias_chain']) + 2 for b in
                                ([record['root_binding']] if record['root_binding'] else []) +
                                [r['binding'] for r in record['index_reads']]) + len(record['index_reads'])
        retained_bytes += len(json.dumps(record, ensure_ascii=True))
        if (evidence_ids > MAX_EVIDENCE_IDS or retained_bytes > MAX_INDEXED_BYTES
                or max(coverage['selectors_total'], coverage['index_read_occurrences']) > MAX_RECORDS):
            _limit()
        uses.append(record)
        coverage['uses_by_kind'][kind] += 1
        coverage['uses_by_role'][role] += 1
        coverage['uses_by_disposition'][record['disposition']] += 1

    for row in access.operands:
        source = source_operands[row['id']]
        if row['role'] == 'expression_read':
            # Parsed CPT leaves are counted independently below. Unsupported
            # expression containers stay explicit without claiming leaf reads.
            if row['binding_status'] == 'unsupported_expression' and '[' in source['raw_text']:
                add('expression', row, source['raw_text'], source['scope_id'], row['id'],
                    row['role'], 'non_static_array_index')
            continue
        add('operand', row, source['raw_text'], source['scope_id'], row['id'], row['role'], row['binding_reason'])
    for row in access.expression_uses:
        if row['binding_reason'] != 'non_static_array_index':
            continue
        source = source_operands[row['expression_operand_id']]
        add('expression', row, source_nodes[row['id']]['raw_text'], source['scope_id'], row['id'],
            row['role'], row['binding_reason'])
    for row in references.aliases:
        if row['reason'] == 'non_static_array_index':
            add('alias', row, row['raw_target'], row['scope_id'], row['source_id'], 'unknown', row['reason'])
    coverage['uses_total'] = len(uses)
    return IndexedAccessResult(deepcopy(inventory.snapshot), 'partial' if uses else 'complete', uses, coverage)


def analyze_indexed_access(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                           access: AccessResult, calculations: CalculationResult,
                           rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
                           conditions: ConditionResult, binding_context: BindingContextResult) -> IndexedAccessResult:
    try:
        validate_binding_context(snapshot, inventory, references, access, calculations, rung_analysis,
                                 relationships, conditions, binding_context)
        result = _derive(inventory, references, access, calculations)
        render_indexed_access_json(result)
        return result
    except IndexedAccessError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_indexed_access(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                            access: AccessResult, calculations: CalculationResult,
                            rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
                            conditions: ConditionResult, binding_context: BindingContextResult,
                            result: IndexedAccessResult) -> None:
    try:
        render_indexed_access_json(result)
        expected = analyze_indexed_access(snapshot, inventory, references, access, calculations,
                                          rung_analysis, relationships, conditions, binding_context)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except IndexedAccessError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_indexed_access_json(result: IndexedAccessResult) -> str:
    """Bound native values before encoding; canonical authentication is separate."""
    try:
        if type(result) is not IndexedAccessResult or vars(result).keys() != set(IndexedAccessResult.__dataclass_fields__):
            _invalid()
        payload = vars(result)
        remaining = MAX_INDEXED_BYTES
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
            if size + 1 > MAX_INDEXED_BYTES:
                _limit()
            output.write(chunk)
        return output.getvalue() + '\n'
    except IndexedAccessError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
