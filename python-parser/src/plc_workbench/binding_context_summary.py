"""Closed counts for private unresolved-use and logical rack context."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .binding_context import (
    CONTEXT_CONSTANTS, COUNT_MAPS, COVERAGE_KEYS, MAX_RECORDS,
    BindingContextResult, validate_binding_context,
)
from .access import AccessResult
from .calculations import CalculationResult
from .conditions import ConditionResult
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult

MAX_REPORT_BYTES = 4 * 1024
CONSTANTS = {**CONTEXT_CONSTANTS, 'policy_version': 2, 'report_kind': 'l5x_binding_context_summary',
             'exporter_version': 'binding-context-summary-1', 'sharing_status': 'aggregate_sync_allowed'}


class BindingContextSummaryError(ValueError):
    """Source-free aggregate validation failure."""


def _invalid() -> None:
    raise BindingContextSummaryError('Binding context summary validation failed; no summary was produced.')


def _keys(value: Any, keys: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(k) is not str for k in value) or value.keys() != keys:
        _invalid()


def validate_binding_context_summary(summary: dict[str, Any]) -> None:
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
        if type(revision['commit']) is not str or re.fullmatch('[0-9a-f]{40}', revision['commit']) is None:
            _invalid()
    else:
        _invalid()
    c = summary['coverage']
    _keys(c, COVERAGE_KEYS)
    counts = []
    for key, vocabulary in COUNT_MAPS.items():
        _keys(c[key], vocabulary)
        counts.extend(c[key].values())
    counts.extend(c[k] for k in COVERAGE_KEYS - COUNT_MAPS.keys())
    if any(type(v) is not int or not 0 <= v <= MAX_RECORDS for v in counts):
        _invalid()
    total, addresses, uses = c['gap_uses_total'], c['candidate_addresses'], c['candidate_address_uses']
    operand = c['operand_binding_gaps'] + c['operand_identity_gaps']
    expression = c['expression_binding_gaps'] + c['expression_identity_gaps']
    predicates, outputs = c['predicate_gap_uses'], c['output_gap_occurrences']
    categories = c['gaps_by_category']
    profiles, roles = c['candidate_address_profiles'], c['gaps_by_role']
    if (total != operand + expression
            or c['gaps_by_kind'] != {'operand': operand, 'expression': expression}
            or sum(c['gaps_by_role'].values()) != total or sum(categories.values()) != total
            or operand > c['source_operands'] or expression > c['expression_uses']
            or predicates > c['gaps_by_role']['read'] or predicates > operand
            or outputs > c['gaps_by_role']['write'] or predicates + outputs > operand
            or c['predicate_gap_occurrences'] > min(predicates, c['source_instructions'])
            or bool(c['predicate_gap_occurrences']) != bool(predicates)
            or outputs > c['source_instructions']
            or sum(c['predicate_gap_categories'].values()) != predicates
            or c['predicate_gap_categories']['non_address_value'] != 0
            or sum(c['output_gap_categories'].values()) != outputs
            or any(c['predicate_gap_categories'][k] + c['output_gap_categories'][k] > n for k, n in categories.items())
            or uses != categories['rack_unique_candidate']
            or uses > operand  # Only existing source-operand matches are admitted.
            or not 0 <= c['candidate_roots'] <= addresses <= uses
            or bool(addresses) != bool(uses) or bool(c['candidate_roots']) != bool(addresses)
            or sum(c['candidate_address_directions'].values()) != addresses
            or sum(c['candidate_address_profiles'].values()) != addresses
            or profiles['read_only'] + profiles['read_and_write'] > roles['read'] - expression + roles['read_write']
            or profiles['write_only'] + profiles['read_and_write'] > roles['write'] + roles['read_write']
            or addresses + max(0, profiles['read_and_write'] - roles['read_write']) > uses
            or categories['invalid_expanded_suffix'] != c['operand_identity_gaps'] + c['expression_identity_gaps']
            or categories['non_address_value'] > c['gaps_by_role']['write'] + c['gaps_by_role']['read_write']
            or (not c['source_rungs'] and (c['source_instructions'] or c['source_operands'] or c['expression_uses']))
            or (not c['source_instructions'] and (c['source_operands'] or c['expression_uses']))
            or (not c['source_operands'] and c['expression_uses'])):
        _invalid()
    if type(summary['status']) is not str or summary['status'] != ('partial' if total else 'complete'):
        _invalid()


def build_binding_context_summary(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                                  access: AccessResult, calculations: CalculationResult,
                                  rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
                                  conditions: ConditionResult, result: BindingContextResult,
                                  revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_binding_context(snapshot, inventory, references, access, calculations, rung_analysis,
                                 relationships, conditions, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
                   'tool_revision': revision if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        validate_binding_context_summary(summary)
        summary['tool_revision'] = dict(summary['tool_revision'])
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_binding_context_summary(summary: dict[str, Any]) -> str:
    validate_binding_context_summary(summary)
    rendered = json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=True) + '\n'
    if len(rendered) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
