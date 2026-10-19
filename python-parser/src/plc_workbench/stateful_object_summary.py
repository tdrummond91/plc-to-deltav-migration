"""Closed, source-free counts for timer, counter and reset relationships."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .conditions import ConditionResult
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult
from .tag_data import TagDataResult
from .stateful_objects import (STATEFUL_OBJECT_CONSTANTS, COUNT_MAPS, COVERAGE_KEYS,
    MAX_STATEFUL_OBJECT_BYTES, MAX_STATEFUL_OBJECT_JSON_BYTES, MAX_STATEFUL_OBJECT_RECORDS,
    StatefulObjectResult, _partial, validate_stateful_objects)

MAX_REPORT_BYTES = 4096
CONSTANTS = {**STATEFUL_OBJECT_CONSTANTS, 'policy_version': 2,
    'report_kind': 'l5x_stateful_object_review_summary', 'exporter_version': 'stateful-object-summary-1',
    'sharing_status': 'aggregate_sync_allowed'}


class StatefulObjectSummaryError(ValueError):
    """Publication rejection containing no source content."""


def _invalid() -> None:
    raise StatefulObjectSummaryError('Stateful object summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != expected:
        _invalid()


def validate_stateful_object_summary(summary: dict[str, Any]) -> None:
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
    occurrences, objects, uses, stored = (c[key] for key in
        ('occurrences_total', 'objects_total', 'address_uses_total', 'stored_data_total'))
    producers, resets = c['producer_occurrences'], c['reset_occurrences']
    exact = c['targets_by_status']['exact_address']
    accepted, rejected = sum(c['accepted_operands_by_role'].values()), sum(c['rejected_operands_by_role'].values())
    family = c['objects_by_family']
    if (occurrences + objects + uses + stored > MAX_STATEFUL_OBJECT_RECORDS
            or max(c['source_rungs'], c['source_instructions'], c['source_operands'], c['source_expression_uses'], c['source_data_elements']) > MAX_STATEFUL_OBJECT_RECORDS
            or occurrences > c['source_instructions'] or c['unparsed_rungs'] > c['source_rungs']
            or c['occurrence_rungs'] > min(occurrences, c['source_rungs'] - c['unparsed_rungs'])
            or bool(c['occurrence_rungs']) != bool(occurrences)
            or any(sum(c[key].values()) != occurrences for key in ('occurrences_by_opcode', 'targets_by_status', 'contexts_by_status'))
            or exact != producers + resets or objects > exact or bool(objects) != bool(exact)
            or resets > c['occurrences_by_opcode']['RES']
            or producers > occurrences - c['occurrences_by_opcode']['RES']
            or any(sum(c[key].values()) != objects for key in ('objects_by_family', 'declarations_by_kind', 'bounds_by_status'))
            or producers < objects - family['reset_only'] + family['mixed']
            or family['timer'] + family['mixed'] > sum(c['occurrences_by_opcode'][key] for key in ('TON', 'TOF', 'RTO'))
            or family['counter'] + family['mixed'] > c['occurrences_by_opcode']['CTU'] + c['occurrences_by_opcode']['CTD']
            or c['objects_with_multiple_producers'] > min(objects - family['reset_only'], producers - (objects - family['reset_only']))
            or c['objects_with_multiple_producers'] < family['mixed']
            or c['matched_reset_occurrences'] + c['unmatched_reset_occurrences'] != resets
            or c['objects_with_resets'] != c['objects_with_matched_resets'] + family['reset_only']
            or c['objects_with_matched_resets'] > min(objects - family['reset_only'], c['matched_reset_occurrences'])
            or bool(c['objects_with_matched_resets']) != bool(c['matched_reset_occurrences'])
            or family['reset_only'] > c['unmatched_reset_occurrences']
            or bool(family['reset_only']) != bool(c['unmatched_reset_occurrences'])
            or c['objects_with_resets'] > min(objects, resets)
            or c['objects_with_tof_resets'] > min(c['objects_with_matched_resets'], c['occurrences_by_opcode']['TOF'])
            or c['objects_with_type_conflicts'] > objects - c['declarations_by_kind']['unresolved']
            or c['objects_with_data'] + c['objects_without_data'] != objects
            or c['objects_with_data'] > c['content_links_total']
            or bool(c['objects_with_data']) != bool(c['content_links_total'])
            or any(sum(c[key].values()) != uses for key in ('uses_by_kind', 'members_by_status'))
            or c['uses_by_kind']['whole_control'] != objects or c['members_by_status']['whole_control'] != objects
            or c['members_by_status']['known'] > c['uses_by_kind']['direct_member']
            or accepted < exact or c['accepted_operands_by_role']['read_write'] < producers
            or c['accepted_operands_by_role']['write'] < resets
            or uses > accepted + rejected + c['accepted_expression_uses'] + c['rejected_expression_uses']
            or any(sum(c[key].values()) != stored for key in ('stored_data_by_kind', 'stored_data_by_status', 'stored_types_by_status'))
            or c['stored_types_by_status']['matching'] + c['stored_types_by_status']['mismatch'] > c['stored_data_by_status']['qualified']
            or stored and (not c['objects_with_data'] or not c['source_data_elements'])
            or not objects and (uses or stored or accepted or rejected or c['accepted_expression_uses'] or c['rejected_expression_uses'])):
        _invalid()
    # All identifiers are digest-based. Count only mandatory links, not private
    # spelling lengths or an assumed writer-to-consumer Cartesian expansion.
    minimum_bytes = 64 * (3 * occurrences + exact + 2 * objects + producers + resets
        + c['content_links_total'] + 2 * uses + accepted + rejected
        + c['accepted_expression_uses'] + c['rejected_expression_uses'] + 2 * stored)
    if minimum_bytes > min(MAX_STATEFUL_OBJECT_BYTES, MAX_STATEFUL_OBJECT_JSON_BYTES):
        _invalid()
    if summary['status'] != ('partial' if _partial(c) else 'complete'):
        _invalid()


def build_stateful_object_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, tag_data: TagDataResult, result: StatefulObjectResult,
        revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_stateful_objects(snapshot, inventory, references, access, calculations,
            rung_analysis, relationships, conditions, tag_data, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
            'tool_revision': dict(revision) if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        render_stateful_object_summary(summary)
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_stateful_object_summary(summary: dict[str, Any]) -> str:
    validate_stateful_object_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
