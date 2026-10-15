"""Closed counts for documented PID member headers; never names, values or links."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .models import InventoryResult, SourceSnapshot
from .pid import PidResult
from .pid_members import (
    COVERAGE_KEYS, FIELD_CATALOG, MATCHED_STATUSES, MAX_PID_MEMBERS,
    MAX_PID_MEMBER_EVIDENCE_BYTES, MAX_PID_MEMBER_JSON_BYTES, MAX_PID_MEMBER_STRUCTURES,
    MEMBER_GROUPS, MEMBER_STATUSES, PID_MEMBER_CONSTANTS, PidMemberResult, validate_pid_members,
)
from .references import ReferenceResult
from .tag_data import TagDataResult

MAX_REPORT_BYTES = 4096
CONSTANTS = {**PID_MEMBER_CONSTANTS, 'policy_version': 2,
             'report_kind': 'l5x_pid_member_review_summary',
             'exporter_version': 'pid-member-summary-1', 'sharing_status': 'aggregate_sync_allowed'}


class PidMemberSummaryError(ValueError):
    """Publication rejection with no private source content."""


def _invalid() -> None:
    raise PidMemberSummaryError('PID member summary validation failed; no summary was produced.') from None


def _keys(value: Any, keys: set[str] | frozenset[str]) -> None:
    if (type(value) is not dict or any(type(key) is not str for key in value)
            or value.keys() != keys):
        _invalid()


def _count(value: Any) -> None:
    if type(value) is not int or not 0 <= value <= 10**12:
        _invalid()


def validate_pid_member_summary(summary: dict[str, Any]) -> None:
    """Check closed vocabulary, partitions and capacities independent of source."""
    _keys(summary, set(CONSTANTS) | {'status', 'tool_revision', 'coverage'})
    for key, fixed in CONSTANTS.items():
        if type(summary[key]) is not type(fixed) or summary[key] != fixed:
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
    partitions = {'members_by_group': MEMBER_GROUPS, 'members_by_status': MEMBER_STATUSES}
    for key, value in c.items():
        if key in partitions:
            _keys(value, partitions[key])
            for count in value.values():
                _count(count)
        else:
            _count(value)
    structures, members, owners = c['structures_total'], c['members_total'], c['distinct_backing_owners']
    groups, statuses = c['members_by_group'], c['members_by_status']
    missing, duplicate = c['missing_catalog_fields'], c['duplicate_catalog_fields']
    missing_structures, duplicate_structures, gaps = (c[key] for key in (
        'structures_with_missing', 'structures_with_duplicates', 'structures_with_gaps'))
    duplicate_records = c['duplicate_member_records']
    unmatched = sum(count for status, count in statuses.items() if status not in MATCHED_STATUSES)
    known = members - groups['unknown']
    catalog_size = len(FIELD_CATALOG)
    known_distinct = catalog_size * structures - missing
    if (structures > MAX_PID_MEMBER_STRUCTURES or members > MAX_PID_MEMBERS
            or owners > structures or bool(owners) != bool(structures)
            or (members and not structures) or c['source_pid_partial'] not in (0, 1)
            or sum(groups.values()) != members or sum(statuses.values()) != members
            or not 0 <= missing_structures <= gaps <= structures
            or not 0 <= duplicate_structures <= gaps
            or not missing_structures <= missing <= catalog_size * missing_structures
            or not duplicate_structures <= duplicate <= catalog_size * duplicate_structures
            or bool(missing_structures) != bool(missing)
            or bool(duplicate_structures) != bool(duplicate)
            or bool(duplicate) != bool(duplicate_records)
            or duplicate_records < 2 * duplicate or duplicate_records > known
            or known_distinct < 0 or known_distinct > known
            or duplicate > known_distinct
            or known != known_distinct + duplicate_records - duplicate
            or gaps > missing_structures + duplicate_structures + unmatched
            or (unmatched and not gaps)
            or statuses['unknown_name'] + statuses['name_missing'] > groups['unknown']
            or groups['unknown'] > statuses['unknown_name'] + statuses['name_missing'] + statuses['qualified_attribute']
            or statuses['array_header_matched'] > groups['internal']):
        _invalid()
    # A complete catalog cannot be redistributed into arbitrary groups. Extra
    # records may repeat known fields, but cannot create additional unique ones.
    duplicate_extras = duplicate_records - duplicate
    for group in MEMBER_GROUPS - {'unknown'}:
        capacity = sum(spec['group'] == group for spec in FIELD_CATALOG.values()) * structures
        if not max(0, capacity - missing) <= groups[group] <= capacity + duplicate_extras:
            _invalid()
    if (statuses['array_header_matched'] > structures + duplicate_extras
            or statuses['matched'] > (catalog_size - 1) * structures + duplicate_extras):
        _invalid()
    minimum_bytes = 64 * (3 * structures + 3 * members)
    if minimum_bytes > min(MAX_PID_MEMBER_EVIDENCE_BYTES, MAX_PID_MEMBER_JSON_BYTES):
        _invalid()
    partial = bool(c['source_pid_partial'] or gaps)
    if summary['status'] != ('partial' if partial else 'complete'):
        _invalid()


def build_pid_member_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
                             references: ReferenceResult, tag_data: TagDataResult,
                             pid: PidResult, result: PidMemberResult,
                             revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_pid_members(snapshot, inventory, references, tag_data, pid, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
                   'tool_revision': dict(revision) if revision is not None else
                   {'commit': None, 'worktree': 'unavailable'}}
        validate_pid_member_summary(summary)
        render_pid_member_summary(summary)
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_pid_member_summary(summary: dict[str, Any]) -> str:
    validate_pid_member_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
