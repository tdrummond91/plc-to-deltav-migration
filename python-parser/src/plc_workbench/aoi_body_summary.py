"""Closed public counts for declaration-owned AOI bodies and instance context."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .binding_context import BindingContextResult
from .calculations import CalculationResult
from .conditions import ConditionResult
from .aoi_body_context import (
    CONTEXT_CONSTANTS, COUNT_MAPS, COVERAGE_KEYS, MAX_RECORDS,
    CONTEXT_CONSTANTS_V2, COUNT_MAPS_V2, COVERAGE_KEYS_V2,
    AoiBodyContextResult, validate_aoi_body_context, coverage_status,
)
from .custom_instruction_context import CustomInstructionContextResult
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult

MAX_REPORT_BYTES = 4 * 1024
MAX_REPORT_BYTES_V2 = 8 * 1024
CONSTANTS = {**CONTEXT_CONSTANTS, 'policy_version': 2, 'report_kind': 'l5x_aoi_body_summary',
             'exporter_version': 'aoi-body-summary-1', 'sharing_status': 'aggregate_sync_allowed'}
CONSTANTS_V2 = {**CONSTANTS, **CONTEXT_CONSTANTS_V2, 'exporter_version': 'aoi-body-summary-2'}


class AoiBodySummaryError(ValueError):
    """A source-free aggregate validation failure."""


def _invalid() -> None:
    raise AoiBodySummaryError('AOI body summary validation failed; no summary was produced.')


def _keys(value: Any, keys: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != keys:
        _invalid()


def validate_aoi_body_summary(summary: dict[str, Any]) -> None:
    if type(summary) is not dict or type(summary.get('schema_version')) is not int or summary['schema_version'] not in {1, 2}:
        _invalid()
    version = summary['schema_version']
    constants = CONSTANTS if version == 1 else CONSTANTS_V2
    count_maps = COUNT_MAPS if version == 1 else COUNT_MAPS_V2
    coverage_keys = COVERAGE_KEYS if version == 1 else COVERAGE_KEYS_V2
    _keys(summary, set(constants) | {'status', 'coverage', 'tool_revision'})
    for key, value in constants.items():
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
        if type(revision['commit']) is not str or re.fullmatch('[0-9a-f]{40}', revision['commit']) is None:
            _invalid()
    else:
        _invalid()
    c = summary['coverage']
    _keys(c, coverage_keys)
    counts = []
    for key, vocabulary in count_maps.items():
        _keys(c[key], vocabulary)
        counts.extend(c[key].values())
    counts.extend(c[key] for key in coverage_keys - count_maps.keys())
    if any(type(value) is not int or not 0 <= value <= MAX_RECORDS for value in counts):
        _invalid()
    groups = {
        'body_rungs_by_parse_status': 'body_rungs_total',
        'body_instructions_by_access_status': 'body_instructions_total',
        'body_operands_by_role': 'body_operands_total',
        'body_operands_by_binding': 'body_operands_total',
        'routines_by_body_status': 'routines_total',
        'calls_by_instance_status': 'calls_total',
        'instance_datatype_status': 'calls_total',
        'instance_address_shape': 'calls_total',
    }
    if any(sum(c[key].values()) != c[total] for key, total in groups.items()):
        _invalid()
    if (any(c[f'body_{kind}_total'] > c[f'source_{kind}']
            for kind in ('rungs', 'instructions', 'operands', 'expression_uses'))
            or c['body_symbol_operand_uses'] > c['body_operands_total']
            or c['body_symbol_expression_uses'] > c['body_expression_uses_total']
            or c['definitions_with_body_gaps'] > c['definitions_total']
            or c['symbols_with_context_gaps'] > c['parameters_total'] + c['local_tags_total']
            or (not c['parameters_total'] + c['local_tags_total'] and
                (c['body_symbol_operand_uses'] or c['body_symbol_expression_uses']))
            or c['calls_total'] > c['source_instructions']
            or (not c['definitions_total'] and any(c[key] for key in (
                'routines_total', 'parameters_total', 'local_tags_total', 'body_rungs_total',
                'body_instructions_total', 'body_operands_total', 'body_expression_uses_total')))
            or (not c['routines_total'] and any(c[key] for key in (
                'body_rungs_total', 'body_instructions_total', 'body_operands_total', 'body_expression_uses_total')))
            or (not c['routines_total'] and c['definitions_with_body_gaps'] != c['definitions_total'])
            or (not c['source_rungs'] and c['source_instructions'])
            or (not c['source_instructions'] and (c['source_operands'] or c['source_expression_uses']))
            or (not c['body_rungs_total'] and c['body_instructions_total'])
            or (not c['body_instructions_total'] and (c['body_operands_total'] or c['body_expression_uses_total']))
            or c['definitions_total'] + c['routines_total'] + c['parameters_total']
                + c['local_tags_total'] + c['calls_total'] > MAX_RECORDS):
        _invalid()
    shape, dtype, instance = c['instance_address_shape'], c['instance_datatype_status'], c['calls_by_instance_status']
    if (shape['literal'] != instance['literal'] or shape['missing'] != instance['missing_operand']
            or dtype['member_deferred'] != shape['member']
            or sum(dtype[key] for key in ('matching_type_name', 'different_type_name', 'missing'))
                != sum(shape[key] for key in ('root', 'unindexed_array', 'static_element'))
            or sum(shape[key] for key in ('root', 'unindexed_array', 'static_element', 'member'))
                > instance['bound_root_context']
            or dtype['unsupported_context'] > instance['unsupported_context']
            or instance['declaration_unavailable'] > shape['not_analyzed']):
        _invalid()
    if version == 2:
        _validate_parameter_counts(c)
    if type(summary['status']) is not str or summary['status'] != coverage_status(c, version):
        _invalid()


def _validate_parameter_counts(c: dict[str, Any]) -> None:
    matched = c['matched_member_contexts']
    members, calls = c['member_contexts_total'], c['calls_total']
    shapes, observations = c['calls_by_field_shape'], c['calls_by_signature_observation']
    roles, signatures = c['matched_members_by_role'], c['signatures_by_status']
    if (sum(c['members_by_status'].values()) != members
            or sum(c['members_by_kind'].values()) != members
            or c['members_by_status']['matched_parameter'] != matched
            or sum(c['matched_members_by_usage'].values()) != matched
            or sum(c['matched_members_by_role'].values()) != matched
            or c['members_by_kind']['operand'] > c['source_operands']
            or c['members_by_kind']['expression'] > c['source_expression_uses']
            # Expression containers and non-data fields cannot be root-bound
            # member candidates. Unknown roles can be bound (for example PID).
            or roles['expression_read'] or roles['non_data']
            # Only expression leaves have a guaranteed read role. Some leaves
            # may be unmatched, so require the feasible lower bound, not equality.
            or roles['read'] < max(0, matched - c['members_by_kind']['operand'])
            or not c['matched_parameters'] <= min(matched, c['parameters_total'])
            or not c['matched_instance_roots'] <= matched
            or bool(matched) != bool(c['matched_parameters'])
            or bool(matched) != bool(c['matched_instance_roots'])
            or sum(c['signatures_by_status'].values()) != c['definitions_total']
            or sum(c[f'signature_{key}_parameters'] for key in ('required', 'optional', 'system', 'unclassified')) != c['parameters_total']
            or sum(shapes.values()) != calls or sum(observations.values()) != calls
            or c['call_argument_fields'] > c['source_operands']
            or c['call_argument_fields'] < shapes['one_field'] + 2 * shapes['multiple_fields']
            or c['call_trailing_fields'] != c['call_argument_fields'] - calls + shapes['zero_fields']
            or c['call_empty_fields'] > c['call_argument_fields']
            or observations['missing_instance_field'] != shapes['zero_fields']
            or observations['empty_fields'] > c['call_empty_fields']
            or bool(observations['empty_fields']) != bool(c['call_empty_fields'])
            or observations['no_required_parameters'] > shapes['one_field']
            or observations['required_field_count_equal'] > shapes['multiple_fields']
            or observations['more_than_required_fields'] > shapes['multiple_fields']
            or c['definitions_total'] * 2 + c['routines_total'] + c['parameters_total']
                + c['local_tags_total'] + calls * 2 + members > MAX_RECORDS):
        _invalid()
    if not shapes['multiple_fields'] and c['call_argument_fields'] != shapes['one_field']:
        _invalid()
    if not c['signatures_by_status']['available'] and any(observations[key] for key in (
            'no_required_parameters', 'required_field_count_equal',
            'fewer_than_required_fields', 'more_than_required_fields')):
        _invalid()
    if not c['signature_required_parameters'] and (observations['required_field_count_equal']
            or observations['fewer_than_required_fields']):
        _invalid()
    classified = sum(c[f'signature_{key}_parameters'] for key in ('required', 'optional', 'system'))
    classifiable_signatures = signatures['available'] + signatures['unsupported_metadata']
    if (c['signature_unclassified_parameters'] < signatures['unsupported_metadata']
            or (c['signature_unclassified_parameters'] and signatures['available'] == c['definitions_total'])
            or (classified and not classifiable_signatures)
            # Only the two system names can be classified, and duplicate names
            # make a signature ambiguous before any parameter classification.
            or c['signature_system_parameters'] > 2 * classifiable_signatures):
        _invalid()


def build_aoi_body_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
                           references: ReferenceResult, access: AccessResult,
                           calculations: CalculationResult, rung_analysis: RungAnalysisResult,
                           relationships: RelationshipResult, conditions: ConditionResult,
                           binding_context: BindingContextResult,
                           custom_instruction_context: CustomInstructionContextResult,
                           result: AoiBodyContextResult,
                           revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_aoi_body_context(snapshot, inventory, references, access, calculations,
                                  rung_analysis, relationships, conditions, binding_context,
                                  custom_instruction_context, result)
        constants = CONSTANTS if result.schema_version == 1 else CONSTANTS_V2
        summary = {**constants, 'status': result.status, 'coverage': deepcopy(result.coverage),
                   'tool_revision': revision if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        validate_aoi_body_summary(summary)
        summary['tool_revision'] = dict(summary['tool_revision'])
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_aoi_body_summary(summary: dict[str, Any]) -> str:
    validate_aoi_body_summary(summary)
    rendered = json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=True) + '\n'
    if len(rendered) > (MAX_REPORT_BYTES if summary['schema_version'] == 1 else MAX_REPORT_BYTES_V2):
        _invalid()
    return rendered
