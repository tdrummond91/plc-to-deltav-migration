"""Closed public counts for private custom-instruction declaration candidates."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .binding_context import BindingContextResult
from .calculations import CalculationResult
from .conditions import ConditionResult
from .custom_instruction_context import (
    CONTEXT_CONSTANTS, COUNT_MAPS, COVERAGE_KEYS, MAX_RECORDS,
    CustomInstructionContextResult, validate_custom_instruction_context,
)
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult

MAX_REPORT_BYTES = 4 * 1024
CONSTANTS = {**CONTEXT_CONSTANTS, 'policy_version': 2, 'report_kind': 'l5x_custom_instruction_summary',
             'exporter_version': 'custom-instruction-summary-1', 'sharing_status': 'aggregate_sync_allowed'}


class CustomInstructionSummaryError(ValueError):
    """A source-free aggregate validation failure."""


def _invalid() -> None:
    raise CustomInstructionSummaryError('Custom instruction summary validation failed; no summary was produced.')


def _keys(value: Any, keys: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != keys:
        _invalid()


def validate_custom_instruction_summary(summary: dict[str, Any]) -> None:
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
    calls, definitions, parameters, routines = (
        c['unknown_family_calls'], c['definitions_total'], c['parameters_total'], c['routines_total'])
    unique = c['calls_by_status']['unique_candidate']
    called = c['unique_candidate_definitions_called']
    if (sum(c['calls_by_status'].values()) != calls
            or sum(c['definitions_by_status'].values()) != definitions
            or calls > c['source_instructions']
            or any(sum(c[f'parameter_{key}'].values()) != parameters for key in ('usage', 'required', 'visible', 'datatype'))
            or sum(c['routine_languages'].values()) != routines
            or sum(c['routine_contents'].values()) != routines
            or not called <= min(unique, c['definitions_by_status']['unique_candidate'])
            or bool(called) != bool(unique)
            or c['definitions_with_encoded_regions'] > min(definitions, c['encoded_regions_total'])
            or bool(c['definitions_with_encoded_regions']) != bool(c['encoded_regions_total'])
            or c['definitions_with_protection_markers'] > definitions
            or (not definitions and (parameters or routines or c['encoded_regions_total']))
            or (not c['source_rungs'] and (c['source_instructions'] or c['source_operands']))
            or (not c['source_instructions'] and c['source_operands'])
            or c['definitions_by_status']['ambiguous_name'] == 1
            or (c['calls_by_status']['ambiguous_declaration'] and not c['definitions_by_status']['ambiguous_name'])
            or definitions + parameters + routines + c['encoded_regions_total'] + calls > MAX_RECORDS):
        _invalid()
    # A namespace-invalid parameter makes all its metadata unavailable together.
    unsupported_parameters = {c[f'parameter_{key}']['unsupported_context']
                              for key in ('usage', 'required', 'visible', 'datatype')}
    if len(unsupported_parameters) != 1:
        _invalid()
    if c['routine_languages']['unsupported_context'] > c['routine_contents']['unsupported_context']:
        _invalid()
    incomplete = calls != unique or definitions != c['definitions_by_status']['unique_candidate']
    if type(summary['status']) is not str or summary['status'] != ('partial' if incomplete else 'complete'):
        _invalid()


def build_custom_instruction_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
                                      references: ReferenceResult, access: AccessResult,
                                      calculations: CalculationResult, rung_analysis: RungAnalysisResult,
                                      relationships: RelationshipResult, conditions: ConditionResult,
                                      binding_context: BindingContextResult,
                                      result: CustomInstructionContextResult,
                                      revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_custom_instruction_context(snapshot, inventory, references, access, calculations,
                                            rung_analysis, relationships, conditions, binding_context, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
                   'tool_revision': revision if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        validate_custom_instruction_summary(summary)
        summary['tool_revision'] = dict(summary['tool_revision'])
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_custom_instruction_summary(summary: dict[str, Any]) -> str:
    validate_custom_instruction_summary(summary)
    rendered = json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=True) + '\n'
    if len(rendered) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
