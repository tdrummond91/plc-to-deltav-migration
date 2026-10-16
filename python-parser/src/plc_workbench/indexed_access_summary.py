"""Closed, source-free populations for private symbolic indexed access."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .binding_context import BindingContextResult
from .calculations import CalculationResult
from .conditions import ConditionResult
from .indexed_access import (
    COUNT_MAPS, COVERAGE_KEYS, INDEXED_CONSTANTS, MAX_RECORDS, MAX_SELECTORS, MAX_TOKENS,
    IndexedAccessResult, validate_indexed_access,
)
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult

MAX_REPORT_BYTES = 4 * 1024
CONSTANTS = {**INDEXED_CONSTANTS, 'policy_version': 2, 'report_kind': 'l5x_indexed_access_summary',
             'exporter_version': 'indexed-access-summary-1', 'sharing_status': 'aggregate_sync_allowed'}


class IndexedAccessSummaryError(ValueError):
    """Source-free aggregate rejection."""


def _invalid() -> None:
    raise IndexedAccessSummaryError('Indexed access summary validation failed; no summary was produced.')


def _keys(value: Any, keys: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(k) is not str for k in value) or value.keys() != keys:
        _invalid()


def validate_indexed_access_summary(summary: dict[str, Any]) -> None:
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
    counts.extend(c[key] for key in COVERAGE_KEYS - COUNT_MAPS.keys())
    if any(type(v) is not int or not 0 <= v <= MAX_RECORDS for v in counts):
        _invalid()
    total, symbolic = c['uses_total'], c['symbolic_uses']
    kinds, roles, dispositions = c['uses_by_kind'], c['uses_by_role'], c['uses_by_disposition']
    roots, reads = c['root_bindings'], c['index_bindings']
    if (sum(kinds.values()) != total or sum(roles.values()) != total
            or sum(dispositions.values()) != total
            or symbolic != dispositions['symbolic']
            or symbolic > kinds['operand']
            or symbolic > roles['read'] + roles['write'] + roles['read_write']
            or kinds['operand'] > c['source_operands']
            or kinds['expression'] > c['expression_uses'] + c['source_operands']
            or kinds['alias'] > c['source_aliases']
            or dispositions['expression_dynamic'] + dispositions['expression_unsupported'] != kinds['expression']
            or dispositions['expression_unsupported'] != roles['expression_read']
            or dispositions['expression_dynamic'] > roles['read']
            or dispositions['alias_target_dynamic'] < kinds['alias']
            or kinds['alias'] > roles['unknown']
            or dispositions['unknown_role'] != roles['unknown'] + roles['non_data'] - kinds['alias']
            or sum(roots.values()) != symbolic
            or c['root_bound_uses'] != roots['root_bound']
            or sum(reads.values()) != c['index_read_occurrences']
            or c['bound_index_reads'] != reads['root_bound']
            or not symbolic <= c['dynamic_selectors'] <= c['selectors_total'] <= symbolic * MAX_SELECTORS
            or c['index_read_occurrences'] > symbolic * MAX_TOKENS
            or (not c['source_rungs'] and (c['source_instructions'] or c['source_operands'] or c['expression_uses']))
            or (not c['source_instructions'] and (c['source_operands'] or c['expression_uses']))
            or (not c['source_operands'] and c['expression_uses'])):
        _invalid()
    if type(summary['status']) is not str or summary['status'] != ('partial' if total else 'complete'):
        _invalid()


def build_indexed_access_summary(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                                 access: AccessResult, calculations: CalculationResult,
                                 rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
                                 conditions: ConditionResult, binding_context: BindingContextResult,
                                 result: IndexedAccessResult, revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_indexed_access(snapshot, inventory, references, access, calculations, rung_analysis,
                                relationships, conditions, binding_context, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
                   'tool_revision': revision if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        validate_indexed_access_summary(summary)
        summary['tool_revision'] = dict(summary['tool_revision'])
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_indexed_access_summary(summary: dict[str, Any]) -> str:
    validate_indexed_access_summary(summary)
    rendered = json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=True) + '\n'
    if len(rendered) > MAX_REPORT_BYTES:
        _invalid()
    return rendered


render_indexed_access_summary_json = render_indexed_access_summary
