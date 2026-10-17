"""Closed, source-free counts for factorized Boolean signal source context."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .conditions import ConditionResult
from .execution_context import ExecutionContextResult
from .models import InventoryResult, SourceSnapshot
from .output_context import BooleanOutputContextResult
from .references import ReferenceResult
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult
from .signal_context import (COUNT_MAPS, COVERAGE_KEYS, MAX_EVIDENCE_IDS,
    MAX_SIGNAL_CONTEXT_BYTES, MAX_SIGNAL_CONTEXT_JSON_BYTES, MAX_SIGNAL_CONTEXT_RECORDS,
    ROW_GROUPS, SIGNAL_CONTEXT_CONSTANTS, SignalContextResult, _partial, validate_signal_context)
from .stateful_objects import StatefulObjectResult
from .tag_data import TagDataResult

MAX_REPORT_BYTES = 8 * 1024
CONSTANTS = {**SIGNAL_CONTEXT_CONSTANTS, 'policy_version': 2,
    'report_kind': 'l5x_signal_context_review_summary', 'exporter_version': 'signal-context-summary-1',
    'sharing_status': 'aggregate_sync_allowed'}


class SignalContextSummaryError(ValueError):
    """Fixed source-free publication rejection."""


def _invalid() -> None:
    raise SignalContextSummaryError('Signal context summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != expected:
        _invalid()


def validate_signal_context_summary(summary: dict[str, Any]) -> None:
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
        values = (value,)
        if key in COUNT_MAPS:
            _keys(value, COUNT_MAPS[key])
            values = value.values()
        if any(type(count) is not int or not 0 <= count <= 10**12 for count in values):
            _invalid()
    outputs, reads, addresses, rungs = (c[f'{key}_total'] for key in ROW_GROUPS)
    exact_outputs = c['targets_by_status']['exact_address']
    exact_reads = c['reads_by_status']['exact_address']
    coil_addresses = c['address_profiles']['coil_and_condition'] + c['address_profiles']['coil_only']
    read_addresses = c['address_profiles']['coil_and_condition'] + c['address_profiles']['condition_only']
    accepted_operands = sum(c['accepted_operands_by_role'].values())
    rejected_operands = sum(c['rejected_operands_by_role'].values())
    uses = accepted_operands + rejected_operands + c['accepted_expression_uses'] + c['rejected_expression_uses']
    records = outputs + reads + addresses + rungs
    # Every retained occurrence appears once in its rung and, when exact, once
    # in its address. Other source usage lists remain disjoint address groups.
    minimum_links = outputs + reads + exact_outputs + exact_reads + uses + c['noncoil_writers_total']
    if (outputs != c['source_outputs'] or rungs != c['source_rungs']
            or reads != c['source_predicate_operands'] + c['source_ons_storage_operands']
            or c['reads_by_kind']['ons_storage'] != c['source_ons_storage_operands']
            or sum(c['reads_by_kind'][key] for key in ('xic', 'xio', 'comparison')) != c['source_predicate_operands']
            or max(c[key] for key in c if key.startswith('source_')) > MAX_SIGNAL_CONTEXT_RECORDS
            or records > MAX_SIGNAL_CONTEXT_RECORDS
            or records + minimum_links + c['stateful_associations_total'] > MAX_EVIDENCE_IDS
            or 64 * (records + minimum_links) > min(MAX_SIGNAL_CONTEXT_BYTES, MAX_SIGNAL_CONTEXT_JSON_BYTES)
            or c['unparsed_rungs'] > rungs
            or outputs > c['source_instructions'] or reads > c['source_operands']
            or c['source_condition_nodes'] < rungs - c['unparsed_rungs'] + c['source_ons_storage_operands']
            or outputs + reads and rungs == c['unparsed_rungs']
            or addresses > c['source_addresses']
            or c['source_addresses'] > c['source_operands'] + c['source_expression_uses']
            or c['source_stateful_objects'] > c['source_operands']
            or accepted_operands + rejected_operands > c['source_operands']
            or c['accepted_expression_uses'] + c['rejected_expression_uses'] > c['source_expression_uses']
            or any(sum(c[key].values()) != count for key, count in (
                ('outputs_by_opcode', outputs), ('targets_by_status', outputs), ('guards_by_quality', outputs),
                ('reads_by_kind', reads), ('reads_by_status', reads), ('endpoint_kinds', addresses),
                ('address_profiles', addresses), ('rungs_by_qualification', rungs),
                ('stateful_associations_by_kind', c['stateful_associations_total']),
                ('stateful_associations_by_qualification', c['stateful_associations_total'])))
            or coil_addresses > exact_outputs or bool(coil_addresses) != bool(exact_outputs)
            or read_addresses > exact_reads or bool(read_addresses) != bool(exact_reads)
            or exact_reads > c['accepted_operands_by_role']['read'] + c['accepted_operands_by_role']['read_write']
            or c['noncoil_writers_total'] != c['accepted_operands_by_role']['write']
                + c['accepted_operands_by_role']['read_write'] - exact_outputs
            or c['addresses_with_multiple_coils'] > min(coil_addresses, exact_outputs - coil_addresses)
            or c['addresses_with_noncoil_writers'] > min(addresses, c['noncoil_writers_total'])
            or bool(c['addresses_with_noncoil_writers']) != bool(c['noncoil_writers_total'])
            or c['addresses_with_unknown_roles'] > min(addresses, c['accepted_operands_by_role']['unknown'])
            or bool(c['addresses_with_unknown_roles']) != bool(c['accepted_operands_by_role']['unknown'])
            or c['addresses_with_rejected_uses'] > min(addresses, rejected_operands + c['rejected_expression_uses'])
            or bool(c['addresses_with_rejected_uses']) != bool(rejected_operands + c['rejected_expression_uses'])
            or c['outputs_with_branches'] > outputs or c['outputs_with_stateful_conditions'] > outputs
            or c['guards_by_quality']['stateful'] > c['outputs_with_stateful_conditions']
            or c['stateful_associations_total'] > c['source_stateful_address_uses']
            or c['stateful_associations_total'] and not c['source_stateful_objects']
            or c['stateful_associations_total'] and not addresses):
        _invalid()
    for map_key, total_key in (('hints_by_category', 'rungs_with_hints'),
                              ('unqualified_hints_by_category', 'rungs_with_unqualified_hints')):
        total = sum(c[map_key].values())
        if (c[total_key] > min(rungs, total) or bool(c[total_key]) != bool(total)
                or total > len(COUNT_MAPS[map_key]) * c[total_key]
                or any(value > c[total_key] for value in c[map_key].values())):
            _invalid()
    if any(c['hints_by_category'][key] + c['unqualified_hints_by_category'][key] > rungs
           for key in COUNT_MAPS['hints_by_category']):
        _invalid()
    if summary['status'] != ('partial' if _partial(c) else 'complete'):
        _invalid()


def build_signal_context_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, tag_data: TagDataResult, output_context: BooleanOutputContextResult,
        stateful_objects: StatefulObjectResult, execution_context: ExecutionContextResult,
        result: SignalContextResult, revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_signal_context(snapshot, inventory, references, access, calculations, rung_analysis,
            relationships, conditions, tag_data, output_context, stateful_objects, execution_context, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
            'tool_revision': dict(revision) if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        render_signal_context_summary(summary)
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_signal_context_summary(summary: dict[str, Any]) -> str:
    validate_signal_context_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
