"""Closed, source-free aggregate counts for Boolean output source context."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .conditions import ConditionResult
from .models import InventoryResult, SourceSnapshot
from .output_context import (OUTPUT_CONTEXT_CONSTANTS, COUNT_MAPS, COVERAGE_KEYS,
    MAX_OUTPUT_CONTEXT_BYTES, MAX_OUTPUT_CONTEXT_JSON_BYTES, MAX_OUTPUT_CONTEXT_RECORDS,
    BooleanOutputContextResult, _partial, validate_output_context)
from .references import ReferenceResult
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult

MAX_REPORT_BYTES = 4096
CONSTANTS = {**OUTPUT_CONTEXT_CONSTANTS, 'policy_version': 2,
    'report_kind': 'l5x_output_context_review_summary', 'exporter_version': 'output-context-summary-1',
    'sharing_status': 'aggregate_sync_allowed'}


class OutputContextSummaryError(ValueError):
    """Publication rejection containing no source content."""


def _invalid() -> None:
    raise OutputContextSummaryError('Output context summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != expected:
        _invalid()


def validate_output_context_summary(summary: dict[str, Any]) -> None:
    """Authenticate fixed vocabularies, exact partitions and resource capacity."""
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
    outputs, addresses, reads, rungs = (c[key] for key in
        ('outputs_total', 'addresses_total', 'condition_reads_total', 'rung_contexts_total'))
    exact = c['targets_by_status']['exact_address']
    accepted, rejected = c['accepted_operands_by_role'], c['rejected_operands_by_role']
    accepted_count, rejected_count = sum(accepted.values()), sum(rejected.values())
    hints, unqualified = sum(c['hints_by_category'].values()), sum(c['unqualified_hints_by_category'].values())
    if (outputs + addresses + reads + rungs > MAX_OUTPUT_CONTEXT_RECORDS
            or max(c['source_rungs'], c['source_instructions'], c['source_operands'],
                   c['source_expression_uses'], c['source_condition_nodes'], c['source_outputs']) > MAX_OUTPUT_CONTEXT_RECORDS
            or outputs != c['source_outputs'] or outputs > c['source_instructions']
            or c['source_condition_nodes'] < c['source_rungs'] - c['unparsed_rungs']
            or outputs != sum(c['outputs_by_opcode'].values())
            or any(outputs != sum(c[key].values()) for key in
                   ('targets_by_status', 'contexts_by_status', 'guard_statuses', 'actions_by_status'))
            or c['output_rungs'] != rungs or rungs > min(outputs, c['source_rungs'] - c['unparsed_rungs'])
            or bool(rungs) != bool(outputs) or c['unparsed_rungs'] > c['source_rungs']
            or addresses > exact or bool(addresses) != bool(exact)
            or sum(c['endpoint_kinds'].values()) != addresses
            or sum(c['address_profiles'].values()) != addresses
            or c['addresses_without_readers'] != c['address_profiles']['write_only']
            or c['addresses_with_multiple_coils'] > min(addresses, exact - addresses)
            or accepted['write'] < exact
            or c['actions_by_status']['recognized'] > c['source_operands']
            or accepted_count + rejected_count > c['source_operands']
            or c['accepted_expression_uses'] + c['rejected_expression_uses'] > c['source_expression_uses']
            or c['noncoil_writers_total'] != accepted['write'] + accepted['read_write'] - exact
            or c['addresses_with_noncoil_writers'] > min(addresses, c['noncoil_writers_total'])
            or bool(c['addresses_with_noncoil_writers']) != bool(c['noncoil_writers_total'])
            or c['addresses_with_unknown_roles'] > min(addresses, accepted['unknown'])
            or bool(c['addresses_with_unknown_roles']) != bool(accepted['unknown'])
            or c['addresses_with_namespace_uses'] > min(addresses, rejected_count + c['rejected_expression_uses'])
            or bool(c['addresses_with_namespace_uses']) != bool(rejected_count + c['rejected_expression_uses'])
            or c['address_profiles']['read_and_write'] > accepted['read'] + accepted['read_write'] + c['accepted_expression_uses']
            or bool(c['address_profiles']['read_and_write']) != bool(accepted['read'] + accepted['read_write'] + c['accepted_expression_uses'])
            or reads != sum(c['condition_read_kinds'].values())
            or reads != sum(c['condition_read_statuses'].values())
            or reads > accepted['read'] + accepted['read_write'] + rejected['read'] + rejected['read_write']
            or c['condition_read_statuses']['accepted'] > accepted['read'] + accepted['read_write']
            or c['condition_read_kinds']['ons_storage'] > accepted['read_write'] + rejected['read_write']
            or c['condition_read_kinds']['predicate'] > accepted['read'] + rejected['read']
            or (not addresses and (accepted_count + rejected_count + c['accepted_expression_uses'] + c['rejected_expression_uses'] + reads))
            or c['rungs_with_hints'] > min(rungs, hints) or bool(c['rungs_with_hints']) != bool(hints)
            or c['rungs_with_unqualified_hints'] > min(rungs, unqualified)
            or bool(c['rungs_with_unqualified_hints']) != bool(unqualified)
            or any(c['hints_by_category'][key] + c['unqualified_hints_by_category'][key] > rungs
                   for key in c['hints_by_category'])
            or c['outputs_with_branches'] > outputs or c['outputs_with_stateful_conditions'] > outputs
            or c['contexts_by_status']['stateful'] > c['outputs_with_stateful_conditions']
            or c['contexts_by_status']['opaque'] > c['guard_statuses']['opaque']
            or c['contexts_by_status']['binding_gaps'] > c['guard_statuses']['binding_gaps']
            or c['contexts_by_status']['modeled'] + c['contexts_by_status']['stateful'] > c['guard_statuses']['modeled']
            or c['guard_statuses']['opaque'] - c['contexts_by_status']['opaque'] > c['contexts_by_status']['namespace_gap']
            or c['guard_statuses']['binding_gaps'] - c['contexts_by_status']['binding_gaps'] > c['contexts_by_status']['namespace_gap']
            or c['targets_by_status']['signature_unresolved'] > c['actions_by_status']['unresolved']
            or exact + c['targets_by_status']['identity_gap'] + c['targets_by_status']['unbound'] > c['actions_by_status']['recognized']
            or c['actions_by_status']['unresolved'] > c['targets_by_status']['signature_unresolved'] + c['targets_by_status']['namespace_gap']):
        _invalid()
    # Each retained source ID carries a 64-character digest. Count conservative
    # mandatory ID links; this rejects impossible aggregate capacities without
    # publishing identifiers or assuming actual runtime relationships.
    minimum_bytes = 64 * (5 * outputs + 2 * addresses + 3 * reads + rungs
        + accepted_count + rejected_count + c['accepted_expression_uses'] + c['rejected_expression_uses']
        + c['noncoil_writers_total'] + outputs + exact + hints + unqualified)
    if minimum_bytes > min(MAX_OUTPUT_CONTEXT_BYTES, MAX_OUTPUT_CONTEXT_JSON_BYTES):
        _invalid()
    if summary['status'] != ('partial' if _partial(c) else 'complete'):
        _invalid()


def build_output_context_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, result: BooleanOutputContextResult,
        revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_output_context(snapshot, inventory, references, access, calculations,
                                rung_analysis, relationships, conditions, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
            'tool_revision': dict(revision) if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        render_output_context_summary(summary)
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_output_context_summary(summary: dict[str, Any]) -> str:
    validate_output_context_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
