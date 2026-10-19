"""Closed aggregate CPT syntax counts; no expressions, names, values or links."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .calculations import (
    CALCULATION_CONSTANTS, CALCULATION_V1_CONSTANTS, COVERAGE_KEYS, COVERAGE_V1_KEYS,
    ERROR_CODES, FUNCTIONS, UNSUPPORTED_FUNCTION_BUCKETS, MAX_CALCULATION_BYTES,
    MAX_CALCULATION_INSTRUCTIONS, MAX_CALCULATION_NODES, MAX_EXPRESSION_DEPTH, MAX_EXPRESSION_TOKENS,
    NODE_KINDS, SIGNATURE_STATUSES, SYNTAX_STATUSES, CalculationResult, validate_calculations,
)
from .models import InventoryResult, SourceSnapshot
from .references import ALIAS_STATUSES, MAX_OPERANDS, ReferenceResult
from .source import MAX_ELEMENTS

MAX_REPORT_BYTES = 3 * 1024
LEGACY_CONSTANTS = {**CALCULATION_V1_CONSTANTS, 'policy_version': 2,
                   'report_kind': 'l5x_calculation_review_summary',
                   'exporter_version': 'calculation-summary-1', 'sharing_status': 'aggregate_sync_allowed'}
CONSTANTS = {**LEGACY_CONSTANTS, **CALCULATION_CONSTANTS, 'exporter_version': 'calculation-summary-2'}


class CalculationSummaryError(ValueError):
    """Source-free rejection of unsupported aggregate evidence."""


def _invalid() -> None:
    raise CalculationSummaryError('Calculation summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if (type(value) is not dict or any(type(key) is not str for key in value)
            or value.keys() != expected):
        _invalid()


def _count(value: Any) -> None:
    if type(value) is not int or not 0 <= value <= 10**12:
        _invalid()


def validate_calculation_summary(summary: dict[str, Any]) -> None:
    """Enforce fixed partitions, source capacities and independent AST identities."""
    if type(summary) is not dict or type(summary.get('schema_version')) is not int:
        _invalid()
    version = summary['schema_version']
    if version not in {1, 2}:
        _invalid()
    constants = LEGACY_CONSTANTS if version == 1 else CONSTANTS
    _keys(summary, set(constants) | {'status', 'tool_revision', 'coverage'})
    for key, fixed in constants.items():
        if type(summary[key]) is not type(fixed) or summary[key] != fixed:
            _invalid()
    if type(summary['status']) is not str or summary['status'] not in {'complete', 'partial'}:
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
    coverage = summary['coverage']
    _keys(coverage, COVERAGE_V1_KEYS if version == 1 else COVERAGE_KEYS)
    partitions = {'occurrences_by_signature': SIGNATURE_STATUSES,
                  'expressions_by_status': SYNTAX_STATUSES, 'expression_errors': ERROR_CODES,
                  'nodes_by_kind': NODE_KINDS, 'reference_by_binding': ALIAS_STATUSES}
    if version == 2:
        partitions.update(functions_by_spelling=FUNCTIONS,
                          unsupported_functions=UNSUPPORTED_FUNCTION_BUCKETS)
    for key, value in coverage.items():
        if key in partitions:
            _keys(value, partitions[key])
            for count in value.values():
                _count(count)
        else:
            _count(value)
    c = coverage
    signatures, expressions = c['occurrences_by_signature'], c['expressions_by_status']
    total, parsed, nodes, refs = c['occurrences_total'], expressions['parsed'], c['nodes_total'], c['reference_occurrences']
    kinds = c['nodes_by_kind']
    if version == 2 and (sum(c['functions_by_spelling'].values()) != kinds['function']
                         or sum(c['unsupported_functions'].values()) != c['expression_errors']['unsupported_function']):
        _invalid()
    gaps = refs - c['reference_by_binding']['root_bound']
    recognized = signatures['recognized']
    # Each parsed expression is one tree: leaves = binary nodes + roots.
    # Group, function and unary nodes each add one parent/child edge.
    if (not 0 <= c['unparsed_rungs'] <= c['source_rungs'] <= MAX_ELEMENTS
            or not total <= c['source_instructions'] <= MAX_CALCULATION_INSTRUCTIONS
            or c['source_operands'] > MAX_OPERANDS
            or (c['source_instructions'] and c['source_rungs'] == c['unparsed_rungs'])
            or sum(signatures.values()) != total or sum(expressions.values()) != total
            or expressions['signature_unresolved'] != signatures['argument_count_mismatch'] + signatures['empty_argument']
            or parsed + expressions['unsupported'] != recognized
            or sum(c['expression_errors'].values()) != expressions['unsupported']
            or 2 * (recognized + signatures['empty_argument']) > c['source_operands']
            or not parsed <= nodes <= min(MAX_CALCULATION_NODES, parsed * MAX_EXPRESSION_TOKENS)
            or sum(kinds.values()) != nodes or kinds['reference'] != refs
            or sum(c['reference_by_binding'].values()) != refs
            or kinds['literal'] + refs != kinds['binary'] + parsed
            or nodes + kinds['group'] + 2 * kinds['function'] > parsed * MAX_EXPRESSION_TOKENS
            or nodes > MAX_EXPRESSION_DEPTH * (kinds['literal'] + refs)
            or not 0 <= c['destination_root_bound'] <= recognized
            or not 0 <= c['expressions_with_binding_gaps'] <= min(parsed, gaps)
            or bool(gaps) != bool(c['expressions_with_binding_gaps'])
            or gaps > c['expressions_with_binding_gaps'] * ((MAX_EXPRESSION_TOKENS + 1) // 2)):
        _invalid()
    # Every node retains its own digest ID and instruction link, at minimum.
    if 128 * nodes > MAX_CALCULATION_BYTES:
        _invalid()
    partial = bool(c['unparsed_rungs'] or parsed != total or c['destination_root_bound'] != total
                   or c['expressions_with_binding_gaps'])
    if summary['status'] != ('partial' if partial else 'complete'):
        _invalid()


def build_calculation_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
                              references: ReferenceResult, result: CalculationResult,
                              revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_calculations(snapshot, inventory, references, result)
        constants = LEGACY_CONSTANTS if result.schema_version == 1 else CONSTANTS
        summary = {**constants, 'status': result.status, 'coverage': deepcopy(result.coverage),
                   'tool_revision': dict(revision) if revision is not None else
                   {'commit': None, 'worktree': 'unavailable'}}
        render_calculation_summary(summary)
        return summary
    except CalculationSummaryError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_calculation_summary(summary: dict[str, Any]) -> str:
    validate_calculation_summary(summary)
    rendered = json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=True) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
