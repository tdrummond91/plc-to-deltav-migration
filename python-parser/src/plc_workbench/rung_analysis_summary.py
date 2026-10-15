"""Closed aggregate-only publication boundary for rung analysis candidates."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .ladder.syntax import MAX_BRANCH_LEGS
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .rung_analysis import (
    COUNT_MAPS, COVERAGE_KEYS, MAX_RECORDS, RUNG_CONSTANTS, RungAnalysisResult,
    validate_rung_analysis,
)

MAX_REPORT_BYTES = 4 * 1024
MAX_COUNT = 10**12
CONSTANTS = {
    **RUNG_CONSTANTS, 'policy_version': 2, 'report_kind': 'l5x_rung_analysis_summary',
    'exporter_version': 'rung-summary-1', 'sharing_status': 'aggregate_sync_allowed',
}


class RungSummaryError(ValueError):
    """Source-free aggregate validation rejection."""


def _invalid() -> None:
    raise RungSummaryError('Rung summary validation failed; no summary was produced.')


def _keys(value: Any, keys: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(k) is not str for k in value) or value.keys() != keys:
        _invalid()


def _count(value: Any) -> None:
    if type(value) is not int or not 0 <= value <= MAX_COUNT:
        _invalid()


def validate_rung_summary(summary: dict[str, Any]) -> None:
    """Admit only fixed keys, closed count maps and coherent populations."""
    _keys(summary, set(CONSTANTS) | {'tool_revision', 'status', 'coverage'})
    for key, fixed in CONSTANTS.items():
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
    _keys(coverage, COVERAGE_KEYS)
    for key, values in COUNT_MAPS.items():
        _keys(coverage[key], values)
        for count in coverage[key].values():
            _count(count)
    for key in COVERAGE_KEYS - COUNT_MAPS.keys():
        _count(coverage[key])
    rungs, blocks = coverage['source_rungs'], coverage['source_instructions']
    operands, uses = coverage['source_operands'], coverage['expression_uses']
    candidates = coverage['candidates_total']
    if max(rungs, blocks, operands, uses, candidates) > MAX_RECORDS:
        _invalid()
    for key in ('structures', 'identification', 'comments', 'results'):
        if sum(coverage[key].values()) != rungs:
            _invalid()
    for key in ('block_identification', 'block_families'):
        if sum(coverage[key].values()) != blocks:
            _invalid()
    for key in ('candidate_categories', 'candidate_bases'):
        if sum(coverage[key].values()) != candidates:
            _invalid()
    structure, identification = coverage['structures'], coverage['identification']
    nonempty_rungs = sum(identification[key] for key in ('identified', 'partial', 'unidentified'))
    if (structure['unparsed'] != identification['unparsed']
            or structure['empty'] > identification['empty']
            or structure['series'] > nonempty_rungs
            or coverage['unknown_blocks'] != coverage['block_identification']['unknown'] + coverage['block_identification']['known_mnemonic']
            or coverage['unknown_blocks'] < identification['unidentified']
            or coverage['unknown_blocks'] > blocks - identification['identified'] - identification['partial']
            or (coverage['unknown_blocks'] and not identification['partial'] + identification['unidentified'])
            or coverage['access_gap_operands'] > operands
            or coverage['unknown_role_operands'] > operands
            or coverage['access_gap_operands'] + coverage['unknown_role_operands'] > operands
            or coverage['expression_gap_uses'] > uses
            or coverage['missing_number'] > rungs or coverage['missing_type'] > rungs
            or coverage['branches'] < structure['branched']
            or coverage['branch_legs'] < 2 * coverage['branches']
            or coverage['branch_legs'] > MAX_BRANCH_LEGS * (rungs - structure['unparsed'])
            or coverage['empty_legs'] > coverage['branch_legs']
            or (not coverage['branches'] and coverage['branch_legs'])
            or (not structure['branched'] and coverage['branches'])
            or blocks < nonempty_rungs
            or coverage['results']['no_known_result'] < identification['empty'] + structure['unparsed']
            or (not blocks and (operands or uses))
            or (not operands and uses)
            or (rungs == structure['unparsed'] + identification['empty'] and blocks)
            or candidates > 35 * rungs
            or any(count > 5 * rungs for count in coverage['candidate_categories'].values())):
        _invalid()
    partial = any(identification[s] for s in ('partial', 'unidentified', 'unparsed'))
    if summary['status'] != ('partial' if partial else 'complete'):
        _invalid()


def build_rung_summary(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                       access: AccessResult, calculations: CalculationResult, result: RungAnalysisResult,
                       revision: dict[str, Any] | None = None) -> dict[str, Any]:
    """Authenticate private records before projecting their closed count maps."""
    try:
        validate_rung_analysis(snapshot, inventory, references, access, calculations, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
                   'tool_revision': revision if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        validate_rung_summary(summary)
        summary['tool_revision'] = dict(summary['tool_revision'])
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError):
        _invalid()


def render_rung_summary(summary: dict[str, Any]) -> str:
    validate_rung_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=True, sort_keys=True, indent=2) + '\n'
    if len(rendered) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
