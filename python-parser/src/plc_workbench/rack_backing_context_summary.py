"""Closed, count-only publication of the independent rack association overlay."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .rack_backing_context import (CONTEXT_CONSTANTS, COUNT_MAPS, COVERAGE_KEYS,
    MAX_RECORDS, RackBackingContextResult, validate_rack_backing_context)
from .source import MAX_ELEMENTS

MAX_REPORT_BYTES = 8 * 1024
CONSTANTS = CONTEXT_CONSTANTS | {'policy_version': 2,
    'report_kind': 'l5x_rack_backing_context_summary',
    'exporter_version': 'rack-backing-context-summary-1', 'sharing_status': 'aggregate_sync_allowed'}


class RackBackingContextSummaryError(ValueError):
    """No source-controlled data is included in summary errors."""


def _invalid() -> None:
    raise RackBackingContextSummaryError('Rack backing context summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != expected:
        _invalid()


def validate_rack_backing_context_summary(summary: dict[str, Any]) -> None:
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
    for key, value in c.items():
        if key in COUNT_MAPS:
            _keys(value, COUNT_MAPS[key])
            values = value.values()
        else:
            values = (value,)
        bound = MAX_ELEMENTS if key == 'source_rack_connections' else MAX_RECORDS
        if any(type(number) is not int or not 0 <= number <= bound for number in values):
            _invalid()
    rll, sfc = c['rll_uses_by_disposition'], c['sfc_uses_by_disposition']
    roots, addresses = c['roots_total'], c['addresses_total']
    associated = rll['associated'] + sfc['associated']
    associated_addresses = c['addresses_by_disposition']['associated']
    rll_count, sfc_count = c['source_candidate_uses'], c['source_sfc_binding_gaps']
    if (roots != c['source_rack_declarations'] or sum(c['roots_by_disposition'].values()) != roots
            or sum(c['roots_by_direction'].values()) != roots
            or (roots and not c['source_rack_connections'])
            or roots + c['source_rack_connections'] > MAX_ELEMENTS
            or c['roots_by_disposition']['associated'] > sum(
                min(total, c['source_rack_connections']) for total in c['roots_by_direction'].values())
            or sum(c['addresses_by_direction'].values()) != addresses
            or sum(c['addresses_by_disposition'].values()) != addresses
            or sum(rll.values()) != rll_count or sum(sfc.values()) != sfc_count
            or c['uses_total'] != rll_count + sfc_count
            or roots + addresses + c['uses_total'] > MAX_RECORDS
            or c['rll_addresses'] != c['source_candidate_addresses']
            or not 0 <= c['source_candidate_roots'] <= min(roots, c['rll_addresses'])
            or bool(c['source_candidate_roots']) != bool(c['rll_addresses'])
            or c['rll_addresses'] > rll_count or bool(c['rll_addresses']) != bool(rll_count)
            or c['sfc_addresses'] > sfc_count
            or c['shared_addresses'] > min(c['rll_addresses'], c['sfc_addresses'])
            or addresses != c['rll_addresses'] + c['sfc_addresses'] - c['shared_addresses']
            or addresses > c['uses_total'] or (addresses and not roots)
            or rll_count > c['source_rll_gap_uses'] or sfc_count > c['source_sfc_references']
            or sum(c['associated_uses_by_role'].values()) != associated
            or c['associated_predicate_uses'] + c['associated_output_uses'] > rll['associated']
            or c['associated_predicate_uses'] > c['associated_uses_by_role']['read'] - sfc['associated']
            or c['associated_output_uses'] > c['associated_uses_by_role']['write']
            or c['associated_rll_addresses'] > min(c['rll_addresses'], associated_addresses)
            or c['associated_sfc_addresses'] > min(c['sfc_addresses'], associated_addresses)
            or associated_addresses > c['associated_rll_addresses'] + c['associated_sfc_addresses']
            or c['associated_rll_addresses'] + c['associated_sfc_addresses'] - associated_addresses > c['shared_addresses']
            or addresses - c['addresses_by_disposition']['root_gap'] and not c['roots_by_disposition']['associated']
            or addresses - associated_addresses > c['uses_total'] - associated
            or c['rll_addresses'] - c['associated_rll_addresses'] > rll_count - rll['associated']
            or c['sfc_addresses'] - c['associated_sfc_addresses'] > sfc_count - sfc['associated']
            or rll['associated'] and not c['associated_rll_addresses']
            or sfc['associated'] and not c['associated_sfc_addresses']
            or c['addresses_by_disposition']['root_gap'] and c['roots_by_disposition']['associated'] == roots
            or any(rll[key] for key in ('non_rack_gap', 'candidate_unavailable', 'candidate_ambiguous', 'outside_scope'))):
        _invalid()
    for direction, total in c['addresses_by_direction'].items():
        if total and not c['roots_by_direction'][direction]:
            _invalid()
    for status in ('root_gap', 'member_unavailable', 'bit_out_of_range'):
        if (rll[status] or sfc[status]) and not c['addresses_by_disposition'][status]:
            _invalid()
    partial = c['roots_by_disposition']['associated'] != roots or associated != c['uses_total']
    if type(summary['status']) is not str or summary['status'] != ('partial' if partial else 'complete'):
        _invalid()


def build_rack_backing_context_summary(snapshot, inventory, references, access, calculations,
        rung_analysis, relationships, conditions, binding_context, tag_data, sfc_structure,
        sfc_conditions, result: RackBackingContextResult, *,
        tool_revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_rack_backing_context(snapshot, inventory, references, access, calculations,
            rung_analysis, relationships, conditions, binding_context, tag_data, sfc_structure, sfc_conditions, result)
        summary = CONSTANTS | {'status': result.status, 'coverage': deepcopy(result.coverage),
            'tool_revision': dict(tool_revision) if tool_revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        render_rack_backing_context_summary(summary)
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_rack_backing_context_summary(summary: dict[str, Any]) -> str:
    validate_rack_backing_context_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=True, sort_keys=True, separators=(',', ':')) + '\n'
    if len(rendered) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
