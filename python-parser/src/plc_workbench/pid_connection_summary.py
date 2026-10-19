"""Closed public counts for PID source connections, without names or values."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .conditions import ConditionResult
from .models import InventoryResult, SourceSnapshot
from .pid import PidResult
from .pid_connections import (COUNT_MAPS, COVERAGE_KEYS, MAX_PID_CONNECTION_BYTES,
    MAX_PID_CONNECTION_JSON_BYTES, MAX_PID_CONNECTION_RECORDS, PID_CONNECTION_CONSTANTS,
    PID_CONNECTION_CONSTANTS_V2,
    PidConnectionResult, _partial, validate_pid_connections)
from .pid_members import PidMemberResult
from .references import ReferenceResult
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult
from .tag_data import TagDataResult

MAX_REPORT_BYTES = 4096
CONSTANTS = {**PID_CONNECTION_CONSTANTS, 'policy_version': 2,
    'report_kind': 'l5x_pid_connection_review_summary',
    'exporter_version': 'pid-connection-summary-1', 'sharing_status': 'aggregate_sync_allowed'}
CONSTANTS_V2 = {**CONSTANTS, **PID_CONNECTION_CONSTANTS_V2,
                'exporter_version': 'pid-connection-summary-2'}


class PidConnectionSummaryError(ValueError):
    """Publication rejection with no source content."""


def _invalid() -> None:
    raise PidConnectionSummaryError('PID connection summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != expected:
        _invalid()


def validate_pid_connection_summary(summary: dict[str, Any]) -> None:
    """Enforce closed vocabulary, disjoint partitions and conservative capacities."""
    _keys(summary, set(CONSTANTS) | {'status', 'tool_revision', 'coverage'})
    if type(summary['schema_version']) is not int or summary['schema_version'] not in (1, 2):
        _invalid()
    constants = CONSTANTS_V2 if summary['schema_version'] == 2 else CONSTANTS
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
    _keys(c, COVERAGE_KEYS)
    for key, value in c.items():
        values = [value]
        if key in COUNT_MAPS:
            _keys(value, COUNT_MAPS[key])
            values = value.values()
        if any(type(count) is not int or not 0 <= count <= 10**12 for count in values):
            _invalid()
    occurrences, slots, addresses = (c[key] for key in ('occurrences_total', 'slots_total', 'addresses_total'))
    slot_status = c['slots_by_status']
    controls, masters = c['control_by_status'], c['masters_by_status']
    kinds, roles, groups = (c[key] for key in ('address_kinds', 'address_links_by_role', 'member_addresses_by_group'))
    candidate_occurrences = masters['single_occurrence'] + masters['multiple_occurrences']
    links = c['master_candidate_links']
    context = c['occurrences_with_condition_context']
    recognized_slots = slots - slot_status['signature_unresolved']
    malformed = masters['signature_unresolved']
    master_slot_statuses = {'literal', 'binding_gap', 'identity_gap', 'namespace_gap'}
    exact_masters = sum(count for key, count in masters.items()
                        if key not in master_slot_statuses | {'signature_unresolved'})
    exact_controls = sum(controls[key] for key in ('linked', 'owner_not_pid', 'owner_dimensions_unmodeled'))
    if (occurrences + slots + addresses > MAX_PID_CONNECTION_RECORDS
            or c['source_pid_partial'] not in (0, 1) or c['source_members_partial'] not in (0, 1)
            or sum(slot_status.values()) != slots or sum(controls.values()) != occurrences
            or sum(masters.values()) != occurrences or sum(kinds.values()) != addresses
            or recognized_slots != 7 * (occurrences - malformed)
            or malformed > controls['unavailable']
            or (not occurrences and (slots or addresses))
            or (not malformed and slot_status['signature_unresolved'])
            or any(masters[key] > slot_status[key] for key in master_slot_statuses)
            or exact_masters + exact_controls > slot_status['exact_address']
            or masters['namespace_gap'] + controls['namespace_gap'] > slot_status['namespace_gap']
            or not masters['single_occurrence'] + 2 * masters['multiple_occurrences'] <= links
            or links > masters['single_occurrence'] + masters['multiple_occurrences'] * controls['linked']
            or (candidate_occurrences and not controls['linked'])
            or c['master_self_references'] > min(candidate_occurrences, controls['linked'])
            or context + c['occurrences_without_condition_context'] != occurrences
            or c['incoming_condition_links'] != context
            or sum(groups.values()) != kinds['direct_member'] + kinds['unknown_member']
            or groups['unknown'] != kinds['unknown_member']
            or (not controls['linked'] and addresses != kinds['slot_address'])
            or kinds['whole_owner'] > controls['linked']
            or kinds['slot_address'] > slot_status['exact_address']
            or addresses > sum(roles.values())
            or slot_status['exact_address'] > sum(roles[role] for role in ('read', 'write', 'read_write', 'unknown'))
            or (slot_status['exact_address'] and not addresses)):
        _invalid()
    # Every retained canonical ID has at least a 64-character source digest.
    # This lower bound rejects impossible count payloads without copying names.
    minimum_bytes = 64 * (2 * occurrences + 2 * slots + addresses + sum(roles.values())
                          + links + c['incoming_condition_links'])
    if minimum_bytes > min(MAX_PID_CONNECTION_BYTES, MAX_PID_CONNECTION_JSON_BYTES):
        _invalid()
    if summary['status'] != ('partial' if _partial(c) else 'complete'):
        _invalid()


def build_pid_connection_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, tag_data: TagDataResult, pid: PidResult,
        pid_members: PidMemberResult, result: PidConnectionResult,
        revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_pid_connections(snapshot, inventory, references, access, calculations,
            rung_analysis, relationships, conditions, tag_data, pid, pid_members, result)
        constants = CONSTANTS_V2 if result.schema_version == 2 else CONSTANTS
        summary = {**constants, 'status': result.status, 'coverage': deepcopy(result.coverage),
                   'tool_revision': dict(revision) if revision is not None else
                   {'commit': None, 'worktree': 'unavailable'}}
        render_pid_connection_summary(summary)
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_pid_connection_summary(summary: dict[str, Any]) -> str:
    validate_pid_connection_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
