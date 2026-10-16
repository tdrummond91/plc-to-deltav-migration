"""Closed public counts for private SFR declaration and chart-step candidates."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .sfc_structure import SfcStructureResult
from .sfr_context import (
    CONTEXT_CONSTANTS, COUNT_MAPS, COVERAGE_KEYS, MAX_RECORDS, SfrContextResult,
    validate_sfr_context,
)

MAX_REPORT_BYTES = 4 * 1024
CONSTANTS = {**CONTEXT_CONSTANTS, 'policy_version': 2, 'report_kind': 'l5x_sfr_context_summary',
             'exporter_version': 'sfr-summary-1', 'sharing_status': 'aggregate_sync_allowed'}


class SfrSummaryError(ValueError):
    """A source-free aggregate validation failure."""


def _invalid() -> None:
    raise SfrSummaryError('SFR summary validation failed; no summary was produced.')


def _keys(value: Any, keys: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != keys:
        _invalid()


def validate_sfr_summary(summary: dict[str, Any]) -> None:
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
    if any(type(value) is not int or not 0 <= value <= MAX_RECORDS for value in counts):
        _invalid()
    calls, steps, matches = c['calls_total'], c['steps_total'], c['content_matches_total']
    signature, routine, chart, selector, matching = (c['calls_by_signature'], c['calls_by_routine_status'],
        c['calls_by_chart_status'], c['calls_by_selector_kind'], c['content_matches_by_status'])
    classified, available, unique = signature['classified'], chart['available'], matching['unique_candidate']
    if (any(sum(c[key].values()) != calls for key in (
            'calls_by_signature', 'calls_by_routine_status', 'calls_by_chart_status', 'calls_by_selector_kind'))
            or sum(matching.values()) != matches
            or sum(c['steps_by_binding'].values()) != steps
            or sum(c['initial_markers_by_kind'].values()) != steps
            or c['source_sfc_steps'] != steps
            or calls > c['source_instructions']
            or classified * 2 > c['source_operands']
            or selector['named'] + selector['initial'] != classified
            or selector['not_analyzed'] != calls - classified
            or routine['not_analyzed'] != calls - classified
            or chart['not_analyzed'] != calls - routine['unique_candidate']
            or not c['fully_matched_calls'] <= c['matched_calls'] <= min(available, unique)
            or bool(c['matched_calls']) != bool(unique)
            or not c['multiple_content_calls'] <= available
            or matches < available + c['multiple_content_calls']
            or (not c['multiple_content_calls'] and matches != available)
            or (available and not c['source_sfc_routines'])
            or matches > available * c['source_sfc_contents']
            or (steps and not c['source_sfc_contents'])
            or (c['source_sfc_contents'] and not c['source_sfc_routines'])
            or (c['multiple_content_calls'] and c['source_sfc_contents'] < 2)
            or matching['selector_unresolved'] > selector['named'] * c['source_sfc_contents']
            or (unique and not steps)
            or (matching['ambiguous_candidate'] and steps < 2)
            or (not c['source_rungs'] and (c['source_instructions'] or c['source_operands']))
            or (not c['source_instructions'] and c['source_operands'])
            or calls + steps + matches > MAX_RECORDS):
        _invalid()
    # Every call that is not fully matched consumes at least one nonunique
    # content match; each fully matched call needs at least one unique match.
    if (available - c['fully_matched_calls'] > matches - unique
            or c['fully_matched_calls'] > unique
            or c['matched_calls'] - c['fully_matched_calls'] > c['multiple_content_calls']):
        _invalid()
    complete = (c['fully_matched_calls'] == calls and c['steps_by_binding']['root_bound'] == steps
                and c['initial_markers_by_kind']['other'] == 0)
    if type(summary['status']) is not str or summary['status'] != ('complete' if complete else 'partial'):
        _invalid()


def build_sfr_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
                      references: ReferenceResult, access: AccessResult,
                      calculations: CalculationResult, sfc_structure: SfcStructureResult,
                      result: SfrContextResult, revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_sfr_context(snapshot, inventory, references, access, calculations, sfc_structure, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
                   'tool_revision': revision if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        validate_sfr_summary(summary)
        summary['tool_revision'] = dict(summary['tool_revision'])
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_sfr_summary(summary: dict[str, Any]) -> str:
    validate_sfr_summary(summary)
    rendered = json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=True) + '\n'
    if len(rendered) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
