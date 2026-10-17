"""Closed source-free counts for source-declared execution context."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .conditions import ConditionResult
from .execution_context import (COUNT_MAPS, COVERAGE_KEYS, EXECUTION_CONTEXT_CONSTANTS,
    MAX_EVIDENCE_IDS, MAX_EXECUTION_CONTEXT_BYTES, MAX_EXECUTION_CONTEXT_JSON_BYTES,
    MAX_EXECUTION_CONTEXT_RECORDS, ROW_GROUPS, ExecutionContextResult, _partial,
    validate_execution_context)
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult

MAX_REPORT_BYTES = 8 * 1024
CONSTANTS = {**EXECUTION_CONTEXT_CONSTANTS, 'policy_version': 2,
    'report_kind': 'l5x_execution_context_review_summary',
    'exporter_version': 'execution-context-summary-1', 'sharing_status': 'aggregate_sync_allowed'}


class ExecutionContextSummaryError(ValueError):
    """Fixed source-free publication rejection."""


def _invalid() -> None:
    raise ExecutionContextSummaryError('Execution context summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != expected:
        _invalid()


def validate_execution_context_summary(summary: dict[str, Any]) -> None:
    """Enforce closed vocabularies, exact partitions and bounded capacities."""
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
    tasks, programs, schedules, designations, calls, controls, routines = (c[f'{key}_total'] for key in ROW_GROUPS)
    events = c['event_info_total']
    occurrences = calls + controls
    unique_schedules = c['schedules_by_status']['unique_candidate']
    unique_designations = c['designations_by_status']['unique_candidate']
    unique_calls = c['calls_by_status']['unique_candidate']
    unique_labels = c['label_targets_by_status']['unique_candidate']
    label_occurrences = c['controls_by_opcode']['JMP'] + c['controls_by_opcode']['LBL']
    candidates = sum(c[key] for key in ('schedule_candidate_links', 'designation_candidate_links',
        'call_candidate_links', 'label_candidate_links', 'other_edit_candidate_links'))
    expected_links = (candidates + schedules + unique_schedules + designations
        + unique_calls + calls + unique_designations + controls)
    records = tasks + programs + schedules + designations + calls + controls + routines + events
    minimum_bytes = 64 * (records + expected_links)
    if (any(c[f'{group}_total'] != c[source] for group, source in (
                ('tasks', 'source_tasks'), ('programs', 'source_programs'),
                ('schedules', 'source_schedules'), ('routine_contexts', 'source_routines')))
            or max(c[key] for key in ('source_tasks', 'source_programs', 'source_schedules',
                'source_routines', 'source_rungs', 'source_instructions', 'source_condition_nodes',
                'source_operands', 'source_expression_uses')) > MAX_EXECUTION_CONTEXT_RECORDS
            or c['source_tasks'] + c['source_programs'] + c['source_schedules'] + c['source_routines'] > MAX_EXECUTION_CONTEXT_RECORDS
            or records > MAX_EXECUTION_CONTEXT_RECORDS
            or c['unparsed_rungs'] > c['source_rungs']
            or c['source_condition_nodes'] < c['source_rungs'] - c['unparsed_rungs'] + occurrences
            or occurrences > c['source_instructions']
            or occurrences and c['source_rungs'] == c['unparsed_rungs']
            or occurrences and not routines
            or calls != c['source_control_opcodes']['JSR']
            or any(c['controls_by_opcode'][key] != c['source_control_opcodes'][key] for key in c['controls_by_opcode'])
            or designations != 2 * programs
            or c['designations_by_kind']['main'] != programs or c['designations_by_kind']['fault'] != programs
            or any(sum(c[key].values()) != count for key, count in (
                ('tasks_by_qualification', tasks), ('programs_by_qualification', programs),
                ('routines_by_qualification', routines), ('event_info_by_qualification', events),
                ('schedules_by_status', schedules), ('designations_by_status', designations),
                ('calls_by_status', calls), ('controls_by_opcode', controls),
                ('label_targets_by_status', controls), ('guards_by_quality', occurrences),
                ('arguments_by_shape', occurrences), ('routines_by_body_status', routines)))
            or (schedules or events) and not tasks
            or c['programs_missing_type'] > programs or c['main_designation_gaps'] > programs
            or c['main_designation_gaps'] > designations - unique_designations
            or unique_designations < programs - c['main_designation_gaps']
            or c['main_designation_gaps'] < programs - unique_designations
            or c['programs_with_schedules'] > min(programs, unique_schedules)
            or bool(c['programs_with_schedules']) != bool(unique_schedules)
            or c['routines_with_incoming_calls'] > min(routines, unique_calls)
            or bool(c['routines_with_incoming_calls']) != bool(unique_calls)
            or c['routines_with_outgoing_calls'] > min(routines, calls)
            or bool(c['routines_with_outgoing_calls']) != bool(calls)
            or c['routines_with_controls'] > min(routines, controls)
            or bool(c['routines_with_controls']) != bool(controls)
            or c['routines_with_designations'] > min(routines, unique_designations)
            or bool(c['routines_with_designations']) != bool(unique_designations)
            or c['routines_in_lexical_cycles'] > min(routines, calls)
            or c['label_targets_by_status']['not_applicable'] != controls - label_occurrences
            or unique_labels > label_occurrences
            or c['schedule_candidate_links'] > schedules * programs
            or c['designation_candidate_links'] > designations * routines
            or c['call_candidate_links'] > calls * routines
            or c['label_candidate_links'] > label_occurrences * c['controls_by_opcode']['LBL']
            or c['other_edit_candidate_links'] > label_occurrences * c['controls_by_opcode']['LBL']
            or c['guards_with_branches'] > occurrences
            or c['guards_with_stateful_conditions'] > occurrences
            or c['guards_by_quality']['stateful'] > c['guards_with_stateful_conditions']
            or c['guards_with_namespace_gaps'] != c['guards_by_quality']['namespace_gap']
            or c['argument_fields'] > c['source_operands']
            or c['argument_fields'] < occurrences - c['arguments_by_shape']['no_fields']
            or bool(c['argument_fields']) != bool(occurrences - c['arguments_by_shape']['no_fields'])
            or c['empty_argument_fields'] > c['argument_fields']
            or c['empty_argument_fields'] < c['arguments_by_shape']['empty_fields']
            or bool(c['empty_argument_fields']) != bool(c['arguments_by_shape']['empty_fields'])
            or c['evidence_links'] != expected_links
            or records + expected_links + c['argument_fields'] + c['empty_argument_fields'] > MAX_EVIDENCE_IDS
            or minimum_bytes > min(MAX_EXECUTION_CONTEXT_BYTES, MAX_EXECUTION_CONTEXT_JSON_BYTES)):
        _invalid()
    for key, counts, unique, capacity in (
            ('schedule_candidate_links', c['schedules_by_status'], unique_schedules, programs),
            ('designation_candidate_links', c['designations_by_status'], unique_designations, routines),
            ('call_candidate_links', c['calls_by_status'], unique_calls, routines),
            ('label_candidate_links', c['label_targets_by_status'], unique_labels, c['controls_by_opcode']['LBL'])):
        minimum = unique + 2 * counts['ambiguous_candidate']
        maximum = unique + capacity * (counts['ambiguous_candidate'] + counts['namespace_gap'])
        if not minimum <= c[key] <= maximum:
            _invalid()
    if summary['status'] != ('partial' if _partial(c) else 'complete'):
        _invalid()


def build_execution_context_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, result: ExecutionContextResult,
        revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_execution_context(snapshot, inventory, references, access, calculations,
                                   rung_analysis, relationships, conditions, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
            'tool_revision': dict(revision) if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        render_execution_context_summary(summary)
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_execution_context_summary(summary: dict[str, Any]) -> str:
    validate_execution_context_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
