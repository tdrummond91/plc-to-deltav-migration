"""Closed, source-free coverage for bounded engineering source assemblies."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .engineering_assemblies import (ASSEMBLY_CONSTANTS, COUNT_MAPS, COVERAGE_KEYS,
    FIXED_BYTES, GAP_REASONS, GROUP_BYTES, MAX_ASSEMBLY_GROUPS,
    MAX_ASSEMBLY_MEMBERSHIPS, MAX_ASSEMBLY_VISITS, MAX_ENGINEERING_ASSEMBLIES_BYTES,
    PROVIDERS)

MAX_REPORT_BYTES = 8 * 1024
CONSTANTS = {**ASSEMBLY_CONSTANTS, 'policy_version': 2,
    'report_kind': 'l5x_engineering_assemblies_review_summary',
    'exporter_version': 'engineering-assemblies-summary-1',
    'sharing_status': 'aggregate_sync_allowed'}


class EngineeringAssembliesSummaryError(ValueError):
    """Fixed source-free rejection of malformed aggregate publication."""


def _invalid() -> None:
    raise EngineeringAssembliesSummaryError('Engineering assembly summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != expected:
        _invalid()


def validate_engineering_assemblies_summary(summary: dict[str, Any]) -> None:
    """Reject open vocabulary, bool counts, impossible partitions and budgets."""
    _keys(summary, set(CONSTANTS) | {'status', 'scan_status', 'coverage', 'tool_revision'})
    for key, value in CONSTANTS.items():
        if type(summary[key]) is not type(value) or summary[key] != value:
            _invalid()
    if type(summary['status']) is not str or summary['status'] not in {'complete', 'partial'}:
        _invalid()
    if type(summary['scan_status']) is not str or summary['scan_status'] not in {'complete', 'truncated'}:
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
        if any(type(item) is not int or not 0 <= item <= 10**12 for item in values):
            _invalid()
    groups, members = c['groups_total'], c['memberships_total']
    flagged, flags, member_flags = c['groups_with_boundary_flags'], c['groups_by_flag'], c['memberships_by_flag']
    if (groups > MAX_ASSEMBLY_GROUPS or members > MAX_ASSEMBLY_MEMBERSHIPS
            or groups > members or bool(groups) != bool(members)
            or sum(c['memberships_by_provider'].values()) != members
            or sum(c['memberships_by_relation'].values()) != members
            or sum(c['excluded_by_provider'].values()) != c['excluded_total']
            or sum(c['excluded_by_reason'].values()) != c['excluded_total']
            or sum(c['providers_by_status'].values()) != len(PROVIDERS)
            or c['visited_rows'] + c['visited_links'] > MAX_ASSEMBLY_VISITS
            or members > c['visited_rows'] + c['visited_links']
            or not FIXED_BYTES + groups * GROUP_BYTES + members * 16 <= c['retained_bytes'] <= MAX_ENGINEERING_ASSEMBLIES_BYTES
            or any(c[key] > min(groups, members // 2) for key in ('multirung_groups', 'multiprovider_groups'))
            or flagged > groups or flagged > sum(flags.values())
            or any(value > flagged for value in flags.values())
            or any(value > members for value in member_flags.values())
            or any(flags[key] > member_flags[key] for key in flags if key not in {'competing_writers', 'source_truncated'})
            or member_flags['competing_writers'] != 0
            or flags['competing_writers'] > members // 2
            or c['source_gap_buckets'] > len(PROVIDERS) * len(GAP_REASONS)
            or c['source_gap_counts'] < max(c['source_gap_buckets'], c['excluded_total'])
            or bool(c['source_gap_buckets']) != bool(c['source_gap_counts'])
            or c['source_gap_counts'] < c['providers_by_status']['partial'] + c['providers_by_status']['missing']):
        _invalid()
    relation, provider = c['memberships_by_relation'], c['memberships_by_provider']
    exclusive = {'pid_connections': ('pid_slot', 'pid_address_use'),
        'calculation_paths': ('calculation_input', 'calculation_output'),
        'stateful_objects': ('stateful_control', 'stateful_member'),
        'file_operations': ('file_read', 'file_write', 'file_read_write', 'file_unknown')}
    if any(sum(relation[key] for key in keys) != provider[name] for name, keys in exclusive.items()):
        _invalid()
    if (sum(relation[key] for key in ('boolean_output', 'boolean_condition', 'guard_condition')) > provider['signal_context']
            or relation['sfc_reference'] > provider['sfc_context']
            or member_flags['selector_or_array_span'] != provider['file_operations']
            or member_flags['stateful_guard'] < provider['stateful_objects']
            or member_flags['unknown_role'] < relation['unknown'] + relation['file_unknown']):
        _invalid()
    truncated = summary['scan_status'] == 'truncated'
    if flags['source_truncated'] != (groups if truncated else 0) or member_flags['source_truncated'] and not truncated:
        _invalid()
    partial = bool(c['source_gap_counts'] or flagged or truncated)
    if summary['status'] != ('partial' if partial else 'complete'):
        _invalid()
    if len(json.dumps(summary, ensure_ascii=True, separators=(',', ':')).encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()


def build_engineering_assemblies_summary(result: dict[str, Any],
        tool_revision: dict[str, Any] | None = None) -> dict[str, Any]:
    """Publish fixed counts only; evidence, labels and source IDs never cross."""
    try:
        for key, expected in ASSEMBLY_CONSTANTS.items():
            if type(result[key]) is not type(expected) or result[key] != expected:
                _invalid()
        summary = {**CONSTANTS, 'status': result['status'], 'scan_status': result['scan_status'],
            'coverage': deepcopy(result['coverage']),
            'tool_revision': deepcopy(tool_revision if tool_revision is not None
                else {'commit': None, 'worktree': 'unavailable'})}
        validate_engineering_assemblies_summary(summary)
        return summary
    except EngineeringAssembliesSummaryError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, RecursionError, OverflowError):
        _invalid()


def render_engineering_assemblies_summary(summary: dict[str, Any]) -> str:
    validate_engineering_assemblies_summary(summary)
    result = json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=True) + '\n'
    if len(result.encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()
    return result
