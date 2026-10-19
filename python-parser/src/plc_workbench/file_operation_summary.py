"""Closed aggregate counts for file/array source operations."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .file_operations import (COUNT_MAPS, COVERAGE_KEYS, FILE_OPERATION_CONSTANTS,
    MAX_FILE_OPERATION_RECORDS, ROW_GROUPS, FileOperationResult, _partial, validate_file_operations)

MAX_REPORT_BYTES = 8 * 1024
MAX_FILE_OPERATION_SUMMARY_BYTES = MAX_REPORT_BYTES
CONSTANTS = {**FILE_OPERATION_CONSTANTS, 'policy_version': 2,
    'report_kind': 'l5x_file_operation_review_summary', 'exporter_version': 'file-operation-summary-1',
    'sharing_status': 'aggregate_sync_allowed'}
FILE_OPERATION_SUMMARY_CONSTANTS = CONSTANTS


class FileOperationSummaryError(ValueError):
    """Fixed source-free publication rejection."""


def _invalid() -> None:
    raise FileOperationSummaryError('File operation summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != expected:
        _invalid()


def validate_file_operation_summary(summary: dict[str, Any]) -> None:
    _keys(summary, set(CONSTANTS) | {'status', 'coverage', 'tool_revision'})
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
    operations, slots = c['occurrences_total'], c['slots_total']
    nodes, indices, controls, stored = (c[f'{key}_total'] for key in ROW_GROUPS[2:])
    selected = c['occurrences_by_opcode']
    new_operations = selected['AVE'] + selected['FAL'] + selected['SQO']
    recognized = c['signatures']['recognized']
    bad = operations - recognized
    expected_slots = 3 * (selected['COP'] + selected['CPS']) + 6 * new_operations
    copies = selected['COP'] + selected['CPS']
    exact_roles = {'read': 2 * copies + selected['AVE'] + 2 * selected['SQO'],
        'write': copies + selected['AVE'] + selected['FAL'],
        'read_write': selected['AVE'] + selected['FAL'] + 2 * selected['SQO'],
        'non_data': 3 * selected['AVE'] + 3 * selected['FAL'] + 2 * selected['SQO'],
        'expression_read': selected['FAL'], 'unknown': 0}
    expression_references = c['expression_references_total']
    partitions = (
        ('occurrences_by_opcode', operations), ('signatures', operations), ('qualifications', operations),
        ('contexts', operations), ('span_kinds', operations), ('expressions_by_status', operations),
        ('slots_by_role', slots), ('slots_by_status', slots), ('selectors_by_kind', slots),
        ('expression_nodes_by_kind', nodes), ('expression_references_by_status', expression_references),
        ('index_uses_by_status', indices), ('index_reads_by_status', c['index_read_occurrences']),
        ('controls_by_declaration', controls), ('controls_by_bounds', controls),
        ('stored_data_by_status', stored), ('stored_data_by_kind', stored), ('stored_types_by_status', stored),
    )
    if (any(sum(c[key].values()) != total for key, total in partitions)
            or any(c[key] > MAX_FILE_OPERATION_RECORDS for key in c if key.startswith('source_'))
            or sum(c[f'{key}_total'] for key in ROW_GROUPS) > MAX_FILE_OPERATION_RECORDS
            or c['unparsed_rungs'] > c['source_rungs']
            or operations != c['source_selected_instructions'] or slots != c['source_selected_operands']
            or operations > c['source_instructions'] or slots > c['source_operands']
            or operations and c['source_rungs'] == c['unparsed_rungs']
            or c['source_fal_instructions'] != selected['FAL']
            or slots < max(0, expected_slots - 6 * bad)
            or not bad and slots != expected_slots
            or not bad and c['slots_by_role'] != exact_roles
            or not bad and c['pseudo_operands_total'] != 2 * new_operations
            or not bad and c['newly_classified_instructions'] != new_operations
            or c['expressions_by_status']['not_applicable'] != operations - selected['FAL']
            or c['slots_by_role']['expression_read'] > selected['FAL']
            or c['slots_by_status']['parsed_expression'] != c['expressions_by_status']['parsed']
            or c['slots_by_status']['unsupported_expression'] != c['expressions_by_status']['unsupported']
            or expression_references != c['expression_nodes_by_kind']['reference']
            or expression_references > nodes
            or nodes and not c['expressions_by_status']['parsed']
            or c['expressions_by_status']['parsed'] > nodes
            or nodes > 512 * c['expressions_by_status']['parsed']
            or controls > new_operations or controls > c['slots_by_status']['exact_address']
            or c['pseudo_operands_total'] > 2 * new_operations
            or c['pseudo_operands_total'] % 2
            or c['pseudo_operands_total'] > c['slots_by_role']['non_data']
            or c['newly_classified_instructions'] > min(recognized, new_operations)
            or c['newly_classified_slots'] != 6 * c['newly_classified_instructions']
            or c['newly_classified_slots'] > slots - c['slots_by_role']['unknown']
            or c['controls_with_data'] > controls
            or c['controls_with_data'] > c['content_links_total']
            or bool(c['controls_with_data']) != bool(c['content_links_total'])
            or stored and not c['controls_with_data']
            or stored > c['source_data_elements'] * controls
            or indices > slots + expression_references
            or c['selectors_total'] < c['index_uses_by_status']['parsed']
            or sum(c['index_roots_by_status'].values()) != c['index_uses_by_status']['parsed'] + c['index_uses_by_status']['namespace_gap']
            or c['index_read_occurrences'] and not indices
            or c['selectors_total'] > 64 * indices
            or c['index_read_occurrences'] > 512 * indices):
        _invalid()
    if summary['status'] != ('partial' if _partial(c) else 'complete'):
        _invalid()


def build_file_operation_summary(snapshot, inventory, references, access, calculations,
        rung_analysis, relationships, conditions, tag_data, result: FileOperationResult,
        revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_file_operations(snapshot, inventory, references, access, calculations,
            rung_analysis, relationships, conditions, tag_data, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
            'tool_revision': dict(revision) if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        render_file_operation_summary(summary)
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_file_operation_summary(summary: dict[str, Any]) -> str:
    validate_file_operation_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
