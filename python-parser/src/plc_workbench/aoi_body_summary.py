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
    AoiBodyContextResult, validate_aoi_body_context, coverage_status,
)
from .custom_instruction_context import CustomInstructionContextResult
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult

MAX_REPORT_BYTES = 4 * 1024
CONSTANTS = {**CONTEXT_CONSTANTS, 'policy_version': 2, 'report_kind': 'l5x_aoi_body_summary',
             'exporter_version': 'aoi-body-summary-1', 'sharing_status': 'aggregate_sync_allowed'}


class AoiBodySummaryError(ValueError):
    """A source-free aggregate validation failure."""


def _invalid() -> None:
    raise AoiBodySummaryError('AOI body summary validation failed; no summary was produced.')


def _keys(value: Any, keys: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != keys:
        _invalid()


def validate_aoi_body_summary(summary: dict[str, Any]) -> None:
    _keys(summary, set(CONSTANTS) | {'status', 'coverage', 'tool_revision'})
    for key, value in CONSTANTS.items():
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
    _keys(c, COVERAGE_KEYS)
    counts = []
    for key, vocabulary in COUNT_MAPS.items():
        _keys(c[key], vocabulary)
        counts.extend(c[key].values())
    counts.extend(c[key] for key in COVERAGE_KEYS - COUNT_MAPS.keys())
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
    if type(summary['status']) is not str or summary['status'] != coverage_status(c):
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
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
                   'tool_revision': revision if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        validate_aoi_body_summary(summary)
        summary['tool_revision'] = dict(summary['tool_revision'])
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_aoi_body_summary(summary: dict[str, Any]) -> str:
    validate_aoi_body_summary(summary)
    rendered = json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=True) + '\n'
    if len(rendered) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
