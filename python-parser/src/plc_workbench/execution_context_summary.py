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
    COUNT_MAPS_V2, COVERAGE_KEYS_V2, EXECUTION_CONTEXT_CONSTANTS_V2,
    COUNT_MAPS_V3, COVERAGE_KEYS_V3, EXECUTION_CONTEXT_CONSTANTS_V3,
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
CONSTANTS_V2 = {**CONSTANTS, **EXECUTION_CONTEXT_CONSTANTS_V2,
    'exporter_version': 'execution-context-summary-2'}
CONSTANTS_V3 = {**CONSTANTS, **EXECUTION_CONTEXT_CONSTANTS_V3,
    'exporter_version': 'execution-context-summary-3'}


class ExecutionContextSummaryError(ValueError):
    """Fixed source-free publication rejection."""


def _invalid() -> None:
    raise ExecutionContextSummaryError('Execution context summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != expected:
        _invalid()


def validate_execution_context_summary(summary: dict[str, Any]) -> None:
    """Enforce closed vocabularies, exact partitions and bounded capacities."""
    if type(summary) is not dict or type(summary.get('schema_version')) is not int or summary['schema_version'] not in {1, 2, 3}:
        _invalid()
    version = summary['schema_version']
    constants = CONSTANTS_V3 if version == 3 else CONSTANTS_V2 if version == 2 else CONSTANTS
    count_maps = COUNT_MAPS_V3 if version == 3 else COUNT_MAPS_V2 if version == 2 else COUNT_MAPS
    _keys(summary, set(constants) | {'status', 'tool_revision', 'coverage'})
    for key, value in constants.items():
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
    _keys(c, COVERAGE_KEYS_V3 if version == 3 else COVERAGE_KEYS_V2 if version == 2 else COVERAGE_KEYS)
    for key, value in c.items():
        values = (value,)
        if key in count_maps:
            _keys(value, count_maps[key])
            values = value.values()
        if any(type(count) is not int or not 0 <= count <= (MAX_EVIDENCE_IDS if version >= 2 else 10**12) for count in values):
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
    if version >= 2:
        _validate_boundaries(c, records, version)
    if summary['status'] != ('partial' if _partial(c, version) else 'complete'):
        _invalid()


def _validate_boundaries(c: dict[str, Any], base_records: int, version: int = 2) -> None:
    contents, calls, fields = (c[key] for key in ('boundary_contents_total', 'call_boundaries_total', 'argument_contexts_total'))
    statuses, profiles = c['calls_by_boundary_status'], c['calls_by_boundary_profile']
    field_statuses, by_opcode = c['argument_contexts_by_status'], c['argument_contexts_by_opcode']
    shapes, second = c['calls_by_field_shape'], c['calls_by_second_field_kind']
    associated = statuses['associated']
    sbr_calls, ret_calls = profiles['sbr_only'] + profiles['sbr_and_ret'], profiles['ret_only'] + profiles['sbr_and_ret']
    source_sbr, source_ret = c['controls_by_opcode']['SBR'], c['controls_by_opcode']['RET']
    two = shapes['two_fields_second_zero'] + shapes['two_fields_second_other']
    larger = shapes['three_or_more_second_zero'] + shapes['three_or_more_second_other']
    minimum_jsr_fields = shapes['one_field'] + 2 * two + 3 * larger
    root_bound = field_statuses['root_bound_candidate']
    candidate_capacity = sum(field_statuses[key] for key in
        ('root_bound_candidate', 'alias_cycle', 'alias_depth_limit', 'unsupported_address', 'unresolved', 'ambiguous'))
    links = (contents + c['boundary_sbr_occurrences'] + c['boundary_ret_occurrences']
        + calls + c['calls_by_status']['unique_candidate'] + c['calls_with_target_content']
        + 3 * fields + c['argument_candidate_symbols'] + root_bound + c['argument_alias_links'])
    records = base_records + contents + calls + fields
    qualified_contents = c['boundary_contents_by_status']['qualified_rll']
    if version == 3:
        qualified_contents += c['boundary_contents_by_status']['qualified_sfc']
        records += c['sfc_declarations_total']
        links += c['sfc_source_content_links'] + 3 * c['sfc_declarations_total']
        _validate_sfc_boundaries(c)
    if (calls != c['calls_total']
            or any(sum(c[key].values()) != total for key, total in (
                ('boundary_contents_by_status', contents), ('calls_by_boundary_status', calls),
                ('calls_by_boundary_profile', calls), ('calls_by_field_shape', calls),
                ('calls_by_second_field_kind', calls), ('argument_contexts_by_status', fields),
                ('argument_contexts_by_opcode', fields), ('sbr_target_calls_by_shape', sbr_calls),
                ('ret_target_calls_by_shape', ret_calls)))
            or profiles['not_available'] != calls - associated
            or associated > c['calls_with_target_content']
            or c['calls_with_target_content'] > 0 and contents == 0
            or c['calls_with_target_content'] > c['calls_by_status']['unique_candidate']
            or statuses['target_unavailable'] > calls - c['calls_by_status']['unique_candidate']
            or c['distinct_associated_contents'] > min(associated, qualified_contents)
            or bool(c['distinct_associated_contents']) != bool(associated)
            or c['boundary_sbr_occurrences'] > source_sbr or c['boundary_ret_occurrences'] > source_ret
            or c['unprofiled_boundary_occurrences'] != source_sbr + source_ret
                - c['boundary_sbr_occurrences'] - c['boundary_ret_occurrences']
            or c['boundary_parsed_rungs'] > c['boundary_rungs_total']
            or c['boundary_rungs_total'] > c['source_rungs']
            or c['boundary_rungs_total'] - c['boundary_parsed_rungs'] > c['unparsed_rungs']
            or contents > 0 and (c['programs_total'] == 0 or c['routine_contexts_total'] == 0)
            or contents == 0 and (c['boundary_rungs_total'] or c['boundary_sbr_occurrences'] or c['boundary_ret_occurrences'])
            or c['boundary_sbr_occurrences'] + c['boundary_ret_occurrences'] > 0 and c['boundary_parsed_rungs'] == 0
            or sbr_calls > 0 and c['boundary_sbr_occurrences'] == 0
            or ret_calls > 0 and c['boundary_ret_occurrences'] == 0
            or any(c[key][shape] > shapes[shape] for key in ('sbr_target_calls_by_shape', 'ret_target_calls_by_shape') for shape in shapes)
            or c['sbr_target_calls_by_shape']['zero_fields'] or c['ret_target_calls_by_shape']['zero_fields']
            or second['absent'] != shapes['zero_fields'] + shapes['one_field']
            or second['exact_zero'] != shapes['two_fields_second_zero'] + shapes['three_or_more_second_zero']
            or second['empty'] > c['empty_argument_fields']
            or field_statuses['routine_target'] != calls - shapes['zero_fields']
            or by_opcode['JSR'] < minimum_jsr_fields
            or larger == 0 and by_opcode['JSR'] != minimum_jsr_fields
            or any(by_opcode[opcode] > 0 and c['source_control_opcodes'][opcode] == 0 for opcode in by_opcode)
            or fields > c['argument_fields']
            or c['controls_by_opcode']['JMP'] + c['controls_by_opcode']['LBL'] == 0 and fields != c['argument_fields']
            or field_statuses['empty'] > c['empty_argument_fields']
            or not root_bound <= c['argument_candidate_symbols'] <= candidate_capacity
            or not field_statuses['alias_cycle'] + 64 * field_statuses['alias_depth_limit'] <= c['argument_alias_links'] <= 64 * c['argument_candidate_symbols']
            or c['boundary_evidence_links'] != links
            or records > MAX_EXECUTION_CONTEXT_RECORDS
            or records + c['evidence_links'] + links + c['argument_fields'] + c['empty_argument_fields'] > MAX_EVIDENCE_IDS
            or 64 * (records + c['evidence_links'] + links) > min(MAX_EXECUTION_CONTEXT_BYTES, MAX_EXECUTION_CONTEXT_JSON_BYTES)):
        _invalid()


def _validate_sfc_boundaries(c: dict[str, Any]) -> None:
    languages, targets = c['boundary_contents_by_language'], c['calls_by_target_language']
    statuses, profiles = c['boundary_contents_by_status'], c['calls_by_boundary_profile']
    sfc, declarations = languages['SFC'], c['sfc_declarations_total']
    populated, multiple = c['sfc_contents_with_declarations'], c['sfc_contents_with_multiple_declarations']
    sfc_calls = profiles['sfc_absent'] + profiles['sfc_declared']
    rll_calls = sum(profiles[key] for key in ('none', 'sbr_only', 'ret_only', 'sbr_and_ret'))
    if (sum(languages.values()) != c['boundary_contents_total']
            or sum(targets.values()) != c['calls_total']
            or any(sum(c[key].values()) != declarations for key in ('sfc_in_attributes', 'sfc_ret_attributes'))
            or statuses['qualified_rll'] + statuses['incomplete_rll'] > languages['RLL']
            or statuses['qualified_sfc'] + statuses['incomplete_sfc'] + statuses['multiple_sfc_declarations'] > sfc
            or not 0 <= multiple <= populated <= min(sfc, declarations)
            or declarations < populated + multiple
            or bool(populated) != bool(declarations)
            or multiple == 0 and declarations != populated
            or statuses['multiple_sfc_declarations'] > multiple
            or populated > c['sfc_source_content_links'] or c['sfc_source_content_links'] > sfc
            or statuses['qualified_sfc'] > c['sfc_source_content_links'] - multiple
            or c['distinct_associated_contents'] < sum(bool(value) for key, value in profiles.items() if key != 'not_available')
            or statuses['qualified_sfc'] < sum(bool(profiles[key]) for key in ('sfc_absent', 'sfc_declared'))
            or statuses['qualified_rll'] < sum(bool(profiles[key]) for key in ('none', 'sbr_only', 'ret_only', 'sbr_and_ret'))
            or sfc_calls > targets['SFC'] or rll_calls > targets['RLL']
            or sfc_calls > 0 and statuses['qualified_sfc'] == 0
            or rll_calls > 0 and statuses['qualified_rll'] == 0
            or profiles['sfc_declared'] > 0 and populated == multiple
            or profiles['sfc_absent'] > 0 and populated == sfc
            or c['calls_by_boundary_status']['multiple_declarations'] > targets['SFC']
            or c['calls_by_boundary_status']['multiple_declarations'] > 0 and statuses['multiple_sfc_declarations'] == 0
            or c['calls_by_boundary_status']['unsupported_language'] > targets['other']
            or targets['unavailable'] != c['calls_total'] - c['calls_by_status']['unique_candidate']):
        _invalid()


def build_execution_context_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, result: ExecutionContextResult,
        revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_execution_context(snapshot, inventory, references, access, calculations,
                                   rung_analysis, relationships, conditions, result)
        constants = CONSTANTS_V3 if result.schema_version == 3 else CONSTANTS_V2 if result.schema_version == 2 else CONSTANTS
        summary = {**constants, 'status': result.status, 'coverage': deepcopy(result.coverage),
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
