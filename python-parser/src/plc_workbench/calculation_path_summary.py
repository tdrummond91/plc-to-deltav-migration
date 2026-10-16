"""Closed public counts for isolated calculation source-order observations."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .calculation_paths import (CALCULATION_PATH_CONSTANTS, COUNT_MAPS, COVERAGE_KEYS,
    GAP_REASONS, MAX_CALCULATION_PATH_BYTES, MAX_CALCULATION_PATH_JSON_BYTES,
    MAX_CALCULATION_PATH_RECORDS, CalculationPathResult, _partial, validate_calculation_paths)
from .calculations import CalculationResult
from .conditions import ConditionResult
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult

MAX_REPORT_BYTES = 4096
CONSTANTS = {**CALCULATION_PATH_CONSTANTS, 'policy_version': 2,
    'report_kind': 'l5x_calculation_path_review_summary',
    'exporter_version': 'calculation-path-summary-1', 'sharing_status': 'aggregate_sync_allowed'}


class CalculationPathSummaryError(ValueError):
    """Publication rejection with no source content."""


def _invalid() -> None:
    raise CalculationPathSummaryError('Calculation path summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != expected:
        _invalid()


def validate_calculation_path_summary(summary: dict[str, Any]) -> None:
    """Check closed vocabulary, exact partitions and conservative capacities."""
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
    blocks, regions, links = (c[key] for key in ('occurrences_total', 'regions_total', 'links_total'))
    eligible, gaps = (c['blocks_by_status'][key] for key in ('eligible', 'gap'))
    inputs = c['input_operands_total']
    expression_blocks = c['blocks_by_opcode']['CPT']
    # Known signatures have one destination and at most two non-expression
    # inputs. Malformed signatures retain no invented read/write roles.
    recognized = blocks - c['gap_reasons']['access_not_classified']
    if (blocks + regions + links > MAX_CALCULATION_PATH_RECORDS
            or max(c['source_rungs'], c['source_instructions'], c['source_operands'],
                   c['source_expression_uses']) > MAX_CALCULATION_PATH_RECORDS
            or eligible + gaps != blocks or sum(c['blocks_by_opcode'].values()) != blocks
            or sum(c['gap_reasons'].values()) != gaps
            or sum(c['condition_quality'].values()) != blocks
            or c['condition_quality']['unavailable'] > gaps
            or c['gap_reasons']['condition_unavailable'] > c['condition_quality']['unavailable']
            or sum(c['links_by_kind'].values()) != links
            or sum(c['region_starts'].values()) != regions or sum(c['region_ends'].values()) != regions
            or c['region_blocks_total'] != blocks or regions > blocks
            or (bool(blocks) != bool(regions))
            or c['region_ends']['block_gap'] != gaps or gaps > regions
            or c['region_starts']['rung_entry'] > c['selected_rungs']
            or c['region_ends']['rung_end'] > c['selected_rungs']
            or c['selected_rungs'] > min(blocks, c['source_rungs'] - c['unparsed_rungs'])
            or (bool(blocks) != bool(c['selected_rungs']))
            or c['unparsed_rungs'] > c['source_rungs']
            or blocks > c['source_instructions']
            or eligible + c['preserved_predicates'] + c['barrier_instructions'] != c['source_instructions']
            or sum(c['barriers_by_reason'].values()) != c['barrier_instructions']
            or any(c['gap_reasons'][key] > c['barriers_by_reason'][key] for key in GAP_REASONS)
            or c['branched_blocks'] > blocks or c['branched_regions'] > min(regions, c['branched_blocks'])
            or (bool(c['branched_blocks']) != bool(c['branched_regions']))
            or inputs != sum(c[f'{kind}_input_operands'] for kind in ('literal', 'expression', 'address', 'unresolved'))
            or inputs > min(c['source_operands'] - recognized, 2 * recognized)
            or c['expression_input_operands'] > min(expression_blocks, recognized)
            or c['expression_uses_total'] > c['source_expression_uses']
            or (not c['expression_input_operands'] and c['expression_uses_total'])
            or c['eligible_read_inputs'] > c['address_input_operands']
            or c['eligible_expression_uses'] > c['expression_uses_total']
            or c['eligible_read_inputs'] > 2 * eligible
            or (not eligible and c['eligible_expression_uses'])
            or c['links_by_kind']['operand'] > c['eligible_read_inputs']
            or c['links_by_kind']['expression'] > c['eligible_expression_uses']
            or c['linked_blocks'] > min(links, eligible)
            or c['linked_regions'] > min(c['linked_blocks'], regions - gaps)
            or (bool(links) != bool(c['linked_blocks'])) or (bool(links) != bool(c['linked_regions']))
            or c['linked_blocks'] + c['linked_regions'] > eligible
            or c['overlap_invalidations'] > eligible
            or (not eligible and c['overlap_invalidations'])):
        _invalid()
    # Every retained source ID includes at least a 64-character digest. These
    # intentionally conservative lower bounds also constrain aggregate forgeries.
    minimum_bytes = 64 * (4 * blocks + 2 * regions + 10 * links + inputs
                          + c['expression_uses_total'])
    if minimum_bytes > min(MAX_CALCULATION_PATH_BYTES, MAX_CALCULATION_PATH_JSON_BYTES):
        _invalid()
    if summary['status'] != ('partial' if _partial(c) else 'complete'):
        _invalid()


def build_calculation_path_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, result: CalculationPathResult,
        revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_calculation_paths(snapshot, inventory, references, access, calculations,
                                    rung_analysis, relationships, conditions, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
            'tool_revision': dict(revision) if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        render_calculation_path_summary(summary)
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_calculation_path_summary(summary: dict[str, Any]) -> str:
    validate_calculation_path_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
