"""Closed source-free counts for SFC transition-expression evidence."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .sfc_structure import SfcStructureResult
from .sfc_conditions import (SFC_CONDITION_CONSTANTS, COUNT_MAPS, COVERAGE_KEYS,
    MAX_SFC_CONDITION_BYTES, MAX_SFC_CONDITION_JSON_BYTES, MAX_SFC_CONDITION_RECORDS,
    MAX_EXPRESSION_CHARS, MAX_EXPRESSION_TOKENS, MAX_EVIDENCE_CHARS,
    SfcConditionResult, _partial, validate_sfc_conditions)

MAX_REPORT_BYTES = 4096
CONSTANTS = {**SFC_CONDITION_CONSTANTS, 'policy_version': 2,
    'report_kind': 'l5x_sfc_condition_review_summary', 'exporter_version': 'sfc-condition-summary-1',
    'sharing_status': 'aggregate_sync_allowed'}


class SfcConditionSummaryError(ValueError):
    """Fixed rejection without source-bearing details."""


def _invalid() -> None:
    raise SfcConditionSummaryError('SFC condition summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != expected:
        _invalid()


def validate_sfc_condition_summary(summary: dict[str, Any]) -> None:
    _keys(summary, set(CONSTANTS) | {'status', 'tool_revision', 'coverage'})
    for key, value in CONSTANTS.items():
        if type(summary[key]) is not type(value) or summary[key] != value:
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
    c = summary['coverage']
    _keys(c, COVERAGE_KEYS)
    for key, value in c.items():
        values = [value]
        if key in COUNT_MAPS:
            _keys(value, COUNT_MAPS[key])
            values = value.values()
        if any(type(count) is not int or not 0 <= count <= 10**12 for count in values):
            _invalid()
    transitions, nodes, references, comments = (c[key] for key in
        ('transitions_total', 'nodes_total', 'references_total', 'comments_total'))
    modeled = c['transitions_by_status']['modeled'] + c['transitions_by_status']['binding_gaps']
    unsupported = c['transitions_by_status']['unsupported']
    kinds = c['nodes_by_kind']
    unresolved = references - c['references_by_binding']['root_bound']
    metadata = sum(c['metadata_gaps'].values())
    if (transitions + nodes + references + comments > MAX_SFC_CONDITION_RECORDS
            or max(c['source_routines'], c['source_contents'], c['source_elements']) > MAX_SFC_CONDITION_RECORDS
            or transitions > c['source_elements'] or c['source_st_lines'] > c['source_elements']
            or c['transition_st_lines'] + c['unprocessed_st_lines'] != c['source_st_lines']
            or c['line_spans_total'] > c['transition_st_lines']
            or any(sum(c[key].values()) != transitions for key in ('transitions_by_status', 'transitions_by_reason'))
            or c['transitions_by_reason']['none'] != modeled
            or any(c[key] > transitions for key in ('transitions_with_text', 'transitions_with_comments', 'transitions_with_metadata_gaps'))
            or c['transitions_with_text'] > c['line_spans_total']
            or modeled > c['transitions_with_text']
            or sum(kinds.values()) != nodes or kinds['reference'] != references
            or sum(c['references_by_binding'].values()) != references
            or sum(c['comments_by_kind'].values()) != comments
            or bool(nodes) != bool(modeled) or nodes < modeled or nodes > modeled * MAX_EXPRESSION_TOKENS
            or kinds['binary'] + modeled != kinds['number'] + references
            or bool(unresolved) != bool(c['transitions_by_status']['binding_gaps'])
            or unresolved < c['transitions_by_status']['binding_gaps']
            or bool(comments) != bool(c['transitions_with_comments'])
            or comments < c['transitions_with_comments']
            or bool(metadata) != bool(c['transitions_with_metadata_gaps'])
            or any(count > c['transitions_with_metadata_gaps'] for count in c['metadata_gaps'].values())
            or metadata < c['transitions_with_metadata_gaps']
            or c['expression_chars'] > MAX_EVIDENCE_CHARS
            or c['expression_chars'] < c['transitions_with_text']
            or bool(c['expression_chars']) != bool(c['transitions_with_text'])
            or c['expression_chars'] < c['transitions_by_reason']['character_limit'] * (MAX_EXPRESSION_CHARS + 1)
            or not transitions and (c['transition_st_lines'] or c['line_spans_total'] or metadata)
            or transitions and not c['source_contents']
            or c['source_contents'] and not c['source_routines']
            or c['source_elements'] and not c['source_contents']
            or unsupported and not transitions):
        _invalid()
    minimum_bytes = 64 * (4 * transitions + 3 * nodes + 4 * references + 2 * comments + 2 * c['line_spans_total'])
    if minimum_bytes > min(MAX_SFC_CONDITION_BYTES, MAX_SFC_CONDITION_JSON_BYTES):
        _invalid()
    if summary['status'] != ('partial' if _partial(c) else 'complete'):
        _invalid()


def build_sfc_condition_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, sfc_structure: SfcStructureResult, result: SfcConditionResult,
        revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_sfc_conditions(snapshot, inventory, references, sfc_structure, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
                   'tool_revision': dict(revision) if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        render_sfc_condition_summary(summary)
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_sfc_condition_summary(summary: dict[str, Any]) -> str:
    validate_sfc_condition_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
