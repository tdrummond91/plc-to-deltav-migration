"""Closed count-only publication boundary for PID occurrence evidence."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .models import InventoryResult, SourceSnapshot
from .pid import (
    COVERAGE_KEYS, MAX_PID_EVIDENCE_BYTES, MAX_PID_JSON_BYTES, MAX_PID_OCCURRENCES,
    MAX_PID_OPERANDS, PID_CONSTANTS, SIGNATURE_STATUSES, SLOT_KINDS, SLOT_NAMES,
    STORAGE_STATUSES, PidResult, validate_pid,
)
from .references import OPERAND_STATUSES, ReferenceResult
from .source import MAX_ELEMENTS
from .tag_data import MAX_TAG_DATA_CONTENTS, MAX_TAG_DATA_ELEMENTS, MAX_TAG_DATA_OWNERS, TagDataResult

MAX_COUNT = 10**12
MAX_REPORT_BYTES = 8 * 1024
CONSTANTS = {
    **PID_CONSTANTS, 'policy_version': 2, 'report_kind': 'l5x_pid_review_summary',
    'exporter_version': 'pid-summary-1', 'sharing_status': 'aggregate_sync_allowed',
}


class PidSummaryError(ValueError):
    """Publication rejection containing no private names, values or links."""


def _invalid() -> None:
    raise PidSummaryError('PID summary validation failed; no summary was produced.') from None


def _keys(value: Any, keys: set[str] | frozenset[str]) -> None:
    if (type(value) is not dict or any(type(key) is not str for key in value)
            or value.keys() != keys):
        _invalid()


def _count(value: Any) -> None:
    if type(value) is not int or not 0 <= value <= MAX_COUNT:
        _invalid()


def validate_pid_summary(summary: dict[str, Any]) -> None:
    """Validate fixed metadata, partitions and observable evidence capacities."""
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
    mappings = {'occurrences_by_signature': SIGNATURE_STATUSES, 'operands_by_slot': SLOT_KINDS,
                'operands_by_binding': OPERAND_STATUSES, 'storage_by_status': STORAGE_STATUSES}
    for key, value in c.items():
        if key in mappings:
            _keys(value, mappings[key])
            for count in value.values():
                _count(count)
        else:
            _count(value)
    total, operands = c['occurrences_total'], c['operands_total']
    signatures, slots, bindings, storage = (c[key] for key in (
        'occurrences_by_signature', 'operands_by_slot', 'operands_by_binding', 'storage_by_status'))
    for count, partition in ((total, signatures), (total, storage),
                             (operands, slots), (operands, bindings)):
        if count != sum(partition.values()):
            _invalid()
    recognized = signatures['recognized']
    if (not 0 <= c['unparsed_rungs'] <= c['source_rungs'] <= MAX_ELEMENTS
            or not total <= c['source_instructions'] <= MAX_PID_OCCURRENCES
            or not operands <= c['source_operands'] <= MAX_PID_OPERANDS
            or (c['source_instructions'] and c['source_rungs'] == c['unparsed_rungs'])
            or (c['source_operands'] and not c['source_instructions'])
            or any(slots[slot] != recognized for slot in SLOT_NAMES)
            or slots['unknown'] < 7 * signatures['empty_argument']
            or (not signatures['argument_count_mismatch']
                and slots['unknown'] != 7 * signatures['empty_argument'])
            or bindings['argument_count_mismatch'] != slots['unknown'] - 7 * signatures['empty_argument']
            or (signatures['argument_count_mismatch'] == 1 and bindings['argument_count_mismatch'] == 7)
            or not signatures['empty_argument'] <= bindings['empty'] <= 7 * signatures['empty_argument']
            or bindings['non_data'] or bindings['system_flag'] or bindings['unsupported_instruction']
            or storage['signature_unresolved'] != total - recognized):
        _invalid()
    owner_occurrences = c['occurrences_with_backing_owner']
    owners = c['distinct_backing_owners']
    with_data, without_data, opaque = (c[key] for key in (
        'occurrences_with_data', 'occurrences_without_data', 'occurrences_with_opaque_only'))
    owner_data, owner_without, owner_opaque = (c[key] for key in (
        'backing_owners_with_data', 'backing_owners_without_data', 'backing_owners_with_opaque_only'))
    if (owner_occurrences != total - storage['signature_unresolved']
            - storage['first_operand_unbound'] - storage['owner_not_captured']
            or owners > min(owner_occurrences, MAX_TAG_DATA_OWNERS)
            or bool(owners) != bool(owner_occurrences)
            or owner_data + owner_without != owners
            or with_data + without_data != owner_occurrences
            or owner_data > with_data or owner_without > without_data
            or owner_opaque > min(owner_data, opaque)
            or opaque > with_data
            or bool(owner_data) != bool(with_data)
            or bool(owner_without) != bool(without_data)
            or bool(owner_opaque) != bool(opaque)
            or bindings['root_bound'] < owner_occurrences + storage['owner_not_captured']):
        _invalid()
    representations, decorated, structures, members = (c[key] for key in (
        'representation_occurrences', 'decorated_representation_occurrences',
        'structure_occurrences', 'direct_member_occurrences'))
    multiple_representations = c['occurrences_with_multiple_representations']
    multiple_structures = c['occurrences_with_multiple_structures']
    linked = storage['linked']
    if (representations < with_data + multiple_representations
            or representations > with_data * MAX_TAG_DATA_CONTENTS
            or decorated > representations
            or decorated < with_data - opaque
            or decorated > (with_data - opaque) * MAX_TAG_DATA_CONTENTS
            or opaque > representations - decorated
            or multiple_representations > with_data
            or (not multiple_representations and representations != with_data)
            or multiple_structures > linked
            or structures < linked + multiple_structures
            or structures > linked * MAX_TAG_DATA_ELEMENTS
            or members > linked * MAX_TAG_DATA_ELEMENTS
            or (not multiple_structures and structures != linked)
            or linked > with_data - opaque
            or (structures and not decorated)
            or storage['no_data'] > without_data
            or storage['no_decorated_data'] > opaque
            or storage['no_pid_structure'] + linked > with_data - opaque
            or storage['owner_namespace_unsupported'] > without_data + opaque):
        _invalid()
    # Every linked identifier has at least a 64-byte digest. This conservative
    # lower bound catches aggregate claims that cannot fit either private limit,
    # even without exposing IDs or trusting source-controlled string lengths.
    minimum_bytes = 64 * (2 * total + 4 * operands + owner_occurrences + representations
                          + decorated + 2 * structures + members)
    if minimum_bytes > min(MAX_PID_EVIDENCE_BYTES, MAX_PID_JSON_BYTES):
        _invalid()
    partial = bool(c['unparsed_rungs'] or linked != total)
    if summary['status'] != ('partial' if partial else 'complete'):
        _invalid()


def build_pid_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
                      references: ReferenceResult, tag_data: TagDataResult, result: PidResult,
                      revision: dict[str, Any] | None = None) -> dict[str, Any]:
    """Replay private evidence before copying only its closed aggregate counts."""
    try:
        validate_pid(snapshot, inventory, references, tag_data, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
                   'tool_revision': revision if revision is not None else
                   {'commit': None, 'worktree': 'unavailable'}}
        validate_pid_summary(summary)
        summary['tool_revision'] = dict(summary['tool_revision'])
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_pid_summary(summary: dict[str, Any]) -> str:
    validate_pid_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
