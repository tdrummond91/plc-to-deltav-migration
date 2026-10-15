"""Closed count-only publication boundary for possible explicit RLL access."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import (
    ACCESS_CONSTANTS, ACCESS2_CONSTANTS, COVERAGE_KEYS, COVERAGE_KEYS_V2,
    EXTENDED_FAMILIES, INDEXED_ROLES, INSTRUCTION_STATUSES,
    MAX_INSTRUCTIONS, MAX_OPERANDS, OPERAND_ROLES, TIMER_PSEUDO_KINDS,
    AccessResult, validate_access,
)
from .models import InventoryResult
from .references import ReferenceResult

MAX_COUNT = 10**12
MAX_REPORT_BYTES = 32 * 1024
LEGACY_CONSTANTS = {
    'schema_version': 1,
    'analyzer_version': 'instruction-access-1',
    'analysis_scope': 'explicit_rll_operand_roles',
    'execution_analysis': 'not_implemented',
    'member_validation': 'not_implemented',
    'implicit_effects': 'not_analyzed',
    'policy_version': 2,
    'report_kind': 'l5x_access_review_summary',
    'exporter_version': 'access-summary-1',
    'sharing_status': 'aggregate_sync_allowed',
}
VERSION2_CONSTANTS = {
    **LEGACY_CONSTANTS, **ACCESS2_CONSTANTS, 'exporter_version': 'access-summary-2',
}
CONSTANTS = {
    **LEGACY_CONSTANTS, **ACCESS_CONSTANTS, 'exporter_version': 'access-summary-3',
}
# Historical work13 embeds this exact contract. Never derive its closed keys or
# status vocabulary from the current analyzer's growing timer/copy catalogue.
LEGACY_INSTRUCTION_STATUSES = frozenset({
    'classified', 'unsupported_instruction', 'argument_count_mismatch', 'empty_argument',
})
LEGACY_COVERAGE_KEYS = frozenset({
    'instructions_total', 'instructions_by_status', 'operands_total', 'operands_by_role',
    'bound_by_role', 'linked_operands', 'unlinked_operands', 'indexed_roots',
    'source_rungs', 'unparsed_rungs', 'access_gap_operands',
})


class AccessSummaryError(ValueError):
    """Publication rejection containing no source evidence."""


def _invalid() -> None:
    raise AccessSummaryError('Access summary validation failed; no summary was produced.')


def _keys(value: Any, keys: set[str] | frozenset[str]) -> None:
    if (type(value) is not dict or any(type(key) is not str for key in value)
            or value.keys() != keys):
        _invalid()


def _count(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= MAX_COUNT:
        _invalid()
    return value


def _counts(value: Any, keys: frozenset[str]) -> None:
    _keys(value, keys)
    for count in value.values():
        _count(count)


def _catalogue_capacity(instructions: int, roles: dict[str, int]) -> bool:
    """Check aggregate slot feasibility without disclosing an opcode histogram.

    Each non-data instruction is a label/jump or SWPB; each read-write
    instruction is ONS, OSR/OSF or MVM. They are disjoint. Remaining instructions
    have one to three reads, or a write with zero to two reads. These complete
    intervals make the capacity calculation constant time, including parity
    when only the non-data and read-write families are present.
    """
    reads, writes = roles['read'], roles['write']
    read_writes, selectors = roles['read_write'], roles['non_data']
    ordinary = instructions - read_writes - selectors
    if ordinary < 0:
        return False
    if ordinary == 0:
        # For s SWPBs, writes-s are OSR/OSF and (reads-s)/2 are MVM.
        lower = max(0, writes - read_writes, (2 * writes + reads - 2 * read_writes + 2) // 3)
        upper = min(selectors, writes, reads)
        lower += (reads - lower) % 2
        return lower <= upper
    # Choose the SWPB count. Other selectors are labels/jumps. For each choice,
    # ordinary instructions fill every read count between their lower/upper
    # capacities, and adjacent choices overlap, so only endpoints are needed.
    lower = max(0, writes - ordinary - read_writes)
    upper = min(selectors, writes)
    if lower > upper:
        return False
    minimum_reads = ordinary - writes + 2 * lower + max(0, writes - lower - ordinary)
    maximum_reads = (3 * ordinary - writes + 2 * upper + 2 * read_writes
                     - max(0, writes - upper - ordinary))
    return minimum_reads <= reads <= maximum_reads


def validate_access_summary(summary: dict[str, Any]) -> None:
    """Validate current v3 or frozen v1/v2 without widening old contracts."""
    if type(summary) is not dict:
        _invalid()
    version = summary.get('schema_version')
    if type(version) is not int or version not in {1, 2, 3}:
        _invalid()
    constants = {1: LEGACY_CONSTANTS, 2: VERSION2_CONSTANTS, 3: CONSTANTS}[version]
    coverage_keys = {1: LEGACY_COVERAGE_KEYS, 2: COVERAGE_KEYS_V2, 3: COVERAGE_KEYS}[version]
    instruction_statuses = LEGACY_INSTRUCTION_STATUSES if version == 1 else INSTRUCTION_STATUSES
    _keys(summary, set(constants) | {'tool_revision', 'status', 'coverage'})
    for key, fixed in constants.items():
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
        if (type(revision['commit']) is not str
                or re.fullmatch(r'[0-9a-f]{40}', revision['commit']) is None):
            _invalid()
    else:
        _invalid()
    coverage = summary['coverage']
    _keys(coverage, coverage_keys)
    groups = {'instructions_by_status', 'operands_by_role', 'bound_by_role'}
    if version >= 2:
        groups.add('timer_pseudo_operands_by_kind')
    if version == 3:
        groups.update({'extended_instructions', 'counter_pseudo_operands_by_kind'})
    for key in coverage_keys - groups:
        _count(coverage[key])
    states = coverage['instructions_by_status']
    roles, bound = coverage['operands_by_role'], coverage['bound_by_role']
    _counts(states, instruction_statuses)
    _counts(roles, OPERAND_ROLES)
    _counts(bound, OPERAND_ROLES)
    instruction_total, operand_total = coverage['instructions_total'], coverage['operands_total']
    if (sum(states.values()) != instruction_total or instruction_total > MAX_INSTRUCTIONS
            or sum(roles.values()) != operand_total or operand_total > MAX_OPERANDS
            or any(bound[role] > roles[role] for role in OPERAND_ROLES)
            or bound['non_data'] != 0):
        _invalid()
    classified = states['classified']
    known = operand_total - roles['unknown']
    invalid_instructions = instruction_total - classified
    invalid_forms = states['unsupported_operand_form'] if version >= 2 else 0
    remaining_classified, remaining_roles = classified, roles
    if version >= 2:
        timers = coverage['timer_instructions']
        pseudo = coverage['timer_pseudo_operands_by_kind']
        _counts(pseudo, TIMER_PSEUDO_KINDS)
        if (sum(pseudo.values()) != 2 * timers or timers > classified
                or timers > roles['read_write'] or 2 * timers > roles['non_data']):
            _invalid()
        remaining_classified = classified - timers
        remaining_roles = dict(roles, read_write=roles['read_write'] - timers,
                               non_data=roles['non_data'] - 2 * timers)
    extra_slots = 0
    if version == 3:
        extended = coverage['extended_instructions']
        _counts(extended, EXTENDED_FAMILIES)
        counters = extended['counter']
        counter_pseudo = coverage['counter_pseudo_operands_by_kind']
        _counts(counter_pseudo, TIMER_PSEUDO_KINDS)
        extended_roles = {
            'read': extended['system_set'],
            'write': extended['system_get'] + extended['sfc_reset_step'],
            'read_write': counters + extended['message'],
            'non_data': (2 * counters + 3 * (extended['system_get'] + extended['system_set'])
                         + extended['sfc_reset_step'] + 2 * extended['sfc_reset_initial']),
        }
        if (sum(counter_pseudo.values()) != 2 * counters
                or coverage['counter_invalid_forms'] > invalid_forms
                or any(value > remaining_roles[role] for role, value in extended_roles.items())):
            _invalid()
        # The fresh resolver binds precisely one data slot per family except
        # SFR's initial-step sentinel. Bound-role allocations must be possible
        # independently of all older catalogued slots.
        lower_bound = sum(max(0, bound[role] - (roles[role] - extended_roles[role]))
                          for role in ('read', 'write', 'read_write'))
        upper_bound = sum(min(bound[role], extended_roles[role])
                          for role in ('read', 'write', 'read_write'))
        if not lower_bound <= coverage['extended_bound_operands'] <= upper_bound:
            _invalid()
        remaining_classified -= sum(extended.values())
        remaining_roles = {role: value - extended_roles.get(role, 0)
                           for role, value in remaining_roles.items()}
        extra_slots = extended['system_get'] + extended['system_set']
    if (not classified <= known <= 3 * classified + extra_slots
            or not _catalogue_capacity(remaining_classified, remaining_roles)
            or roles['unknown'] < 3 * invalid_forms + states['empty_argument']
            or (roles['unknown'] and not invalid_instructions)
            or (not instruction_total and operand_total)):
        _invalid()
    if (not states['unsupported_instruction'] and not states['argument_count_mismatch']
            and roles['unknown'] > (4 if version == 3 else 3) * states['empty_argument'] + 3 * invalid_forms):
        _invalid()
    linked = sum(bound[role] for role in INDEXED_ROLES)
    if (coverage['linked_operands'] != linked
            or coverage['unlinked_operands'] + linked != operand_total
            or coverage['indexed_roots'] > linked
            or bool(coverage['indexed_roots']) != bool(linked)):
        _invalid()
    if (coverage['unparsed_rungs'] > coverage['source_rungs']
            or (instruction_total and coverage['unparsed_rungs'] == coverage['source_rungs'])):
        _invalid()
    unbound_writes = roles['write'] + roles['read_write'] - bound['write'] - bound['read_write']
    if not (unbound_writes <= coverage['access_gap_operands'] <=
            unbound_writes + roles['read'] - bound['read']):
        _invalid()
    partial = bool(invalid_instructions or coverage['unparsed_rungs'] or coverage['access_gap_operands'])
    if summary['status'] != ('partial' if partial else 'complete'):
        _invalid()


def build_access_summary(inventory: InventoryResult, references: ReferenceResult,
                         result: AccessResult, revision: dict[str, Any] | None = None) -> dict[str, Any]:
    """Authenticate private evidence before projecting only closed aggregate data."""
    try:
        validate_access(inventory, references, result)
        summary = {
            **(VERSION2_CONSTANTS if result.schema_version == 2 else CONSTANTS),
            'status': result.status, 'coverage': deepcopy(result.coverage),
            'tool_revision': revision if revision is not None else
                             {'commit': None, 'worktree': 'unavailable'},
        }
        validate_access_summary(summary)
        summary['tool_revision'] = dict(summary['tool_revision'])
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError):
        _invalid()


def render_access_summary(summary: dict[str, Any]) -> str:
    """Render a source-free report only after exact schema validation."""
    validate_access_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=True, sort_keys=True, indent=2) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
