"""Closed aggregate-only publication of exact-address relationship coverage."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .relationships import (
    COUNT_MAPS, COVERAGE_KEYS, MAX_RECORDS, RELATIONSHIP_CONSTANTS, RelationshipResult,
    validate_relationships,
)
from .rung_analysis import RungAnalysisResult

MAX_REPORT_BYTES = 6 * 1024
MAX_COUNT = 10**12
CONSTANTS = {
    **RELATIONSHIP_CONSTANTS, 'policy_version': 2, 'report_kind': 'l5x_relationship_summary',
    'exporter_version': 'relationship-summary-1', 'sharing_status': 'aggregate_sync_allowed',
}


class RelationshipSummaryError(ValueError):
    """Source-free aggregate publication rejection."""


def _invalid() -> None:
    raise RelationshipSummaryError('Relationship summary validation failed; no summary was produced.')


def _keys(value: Any, keys: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != keys:
        _invalid()


def _count(value: Any) -> None:
    if type(value) is not int or not 0 <= value <= MAX_COUNT:
        _invalid()


def validate_relationship_summary(summary: dict[str, Any]) -> None:
    """Validate fixed keys and feasible counts without accepting private strings."""
    _keys(summary, set(CONSTANTS) | {'tool_revision', 'status', 'coverage'})
    for key, expected in CONSTANTS.items():
        if type(summary[key]) is not type(expected) or summary[key] != expected:
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
    for key, vocabulary in COUNT_MAPS.items():
        _keys(coverage[key], vocabulary)
        for value in coverage[key].values():
            _count(value)
    for key in COVERAGE_KEYS - COUNT_MAPS.keys():
        _count(coverage[key])
    rungs = coverage['source_rungs']
    instructions = coverage['source_instructions']
    operands = coverage['source_operands']
    expressions = coverage['expression_uses']
    addresses = coverage['addresses_total']
    gaps = coverage['identity_gaps_total']
    links = coverage['local_links_total']
    patterns = coverage['patterns_total']
    grouped, skipped = coverage['patterned_rungs'], coverage['skipped_rungs']
    indexed, rejected = coverage['indexed_operands_by_role'], coverage['rejected_operands_by_role']
    indexed_expr, rejected_expr = coverage['indexed_expression_uses'], coverage['rejected_expression_uses']
    all_indexed = sum(indexed.values()) + indexed_expr
    profiles = coverage['address_profiles']
    skips = coverage['pattern_skips']
    if max(rungs, instructions, operands, expressions, addresses, gaps, links, patterns) > MAX_RECORDS:
        _invalid()
    if (sum(indexed.values()) + sum(rejected.values()) > operands
            or indexed_expr + rejected_expr + coverage['expression_gap_uses'] != expressions
            or sum(rejected.values()) + rejected_expr != gaps
            or sum(profiles.values()) != addresses
            or addresses > all_indexed or bool(addresses) != bool(all_indexed)
            or profiles['read_only'] + profiles['read_and_write'] > indexed['read'] + indexed['read_write'] + indexed_expr
            or profiles['write_only'] + profiles['read_and_write'] > indexed['write'] + indexed['read_write']
            or profiles['unknown_only'] > indexed['unknown']
            or coverage['cross_rung_addresses'] > addresses
            or coverage['multiple_writer_addresses'] > profiles['write_only'] + profiles['read_and_write']
            or 2 * coverage['multiple_writer_addresses'] > indexed['write'] + indexed['read_write']
            or 2 * coverage['cross_rung_addresses'] > all_indexed
            or (rungs < 2 and coverage['cross_rung_addresses'])
            or (instructions < 2 and coverage['multiple_writer_addresses'])
            or sum(coverage['local_link_kinds'].values()) != links
            or coverage['local_link_kinds']['operand'] > indexed['read']
            or coverage['local_link_kinds']['expression'] > indexed_expr
            or coverage['local_link_rungs'] > min(links, rungs)
            or bool(coverage['local_link_rungs']) != bool(links)
            or (links and not indexed['write'])
            or 2 * coverage['local_link_rungs'] > coverage['eligible_instructions']
            or (links and not profiles['read_and_write'])
            or sum(coverage['local_barriers'].values()) != coverage['barrier_instructions']
            or coverage['eligible_instructions'] + coverage['barrier_instructions'] + coverage['excluded_branched_instructions'] != instructions
            or sum(skips.values()) != skipped or grouped + skipped != rungs
            or patterns > grouped or bool(patterns) != bool(grouped)
            or grouped > instructions
            or skips['empty'] + skips['unparsed'] > rungs
            or bool(instructions) != bool(rungs - skips['empty'] - skips['unparsed'])
            or coverage['access_gap_operands'] + coverage['unknown_role_operands'] > operands
            or indexed['unknown'] + rejected['unknown'] > coverage['unknown_role_operands']
            or sum(indexed[role] + rejected[role] for role in ('read', 'write', 'read_write')) + coverage['access_gap_operands'] + coverage['unknown_role_operands'] > operands
            or (not instructions and (operands or expressions))
            or (not operands and expressions)
            or (gaps and not skipped)
            or (skips['invalid_expanded_suffix'] and not gaps)
            or (skips['unresolved_address'] and not coverage['access_gap_operands'] + coverage['expression_gap_uses'])
            or (skips['unknown_role'] and not coverage['unknown_role_operands'])
            or (coverage['access_gap_operands'] + coverage['expression_gap_uses'] and not skipped)):
        _invalid()
    partial = bool(gaps or skipped != skips['empty'])
    if summary['status'] != ('partial' if partial else 'complete'):
        _invalid()


def build_relationship_summary(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                               access: AccessResult, calculations: CalculationResult,
                               rung_analysis: RungAnalysisResult, result: RelationshipResult,
                               revision: dict[str, Any] | None = None) -> dict[str, Any]:
    """Authenticate private relationships before copying only fixed count maps."""
    try:
        validate_relationships(snapshot, inventory, references, access, calculations, rung_analysis, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
                   'tool_revision': revision if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        validate_relationship_summary(summary)
        summary['tool_revision'] = dict(summary['tool_revision'])
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_relationship_summary(summary: dict[str, Any]) -> str:
    validate_relationship_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=True, sort_keys=True, indent=2) + '\n'
    if len(rendered) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
