"""Fixed aggregate counts for source-relative normal-scan condition evidence."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .conditions import (
    CONDITION_CONSTANTS, MAX_EVIDENCE_IDS, MAX_RECORDS,
    ConditionResult, validate_conditions,
    condition_constants, count_maps, coverage_keys,
)
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult

MAX_REPORT_BYTES = 4 * 1024
MAX_REPORT_V4_BYTES = 8 * 1024
MAX_COUNT = 10**12
CONSTANTS = {
    **CONDITION_CONSTANTS, 'policy_version': 2, 'report_kind': 'l5x_condition_summary',
    'exporter_version': 'condition-summary-1', 'sharing_status': 'aggregate_sync_allowed',
}


def summary_constants(schema_version: int) -> dict[str, Any]:
    try:
        return {**CONSTANTS, **condition_constants(schema_version),
                'exporter_version': f'condition-summary-{schema_version}'}
    except ValueError:
        _invalid()


class ConditionSummaryError(ValueError):
    """Source-free aggregate publication rejection."""


def _invalid() -> None:
    raise ConditionSummaryError('Condition summary validation failed; no summary was produced.')


def _keys(value: Any, keys: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != keys:
        _invalid()


def _count(value: Any) -> None:
    if type(value) is not int or not 0 <= value <= MAX_COUNT:
        _invalid()


def validate_condition_summary(summary: dict[str, Any]) -> None:
    """Reject nonnative values, open text fields, and inconsistent populations."""
    _keys(summary, set(CONSTANTS) | {'tool_revision', 'status', 'coverage'})
    version = summary['schema_version']
    for key, expected in summary_constants(version).items():
        if type(summary[key]) is not type(expected) or summary[key] != expected:
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
    maps, keys = count_maps(version), coverage_keys(version)
    _keys(c, keys)
    for key, vocabulary in maps.items():
        _keys(c[key], vocabulary)
        for value in c[key].values():
            _count(value)
    for key in keys - maps.keys():
        _count(c[key])
    rungs, instructions, operands, expressions = (c[k] for k in ('source_rungs', 'source_instructions', 'source_operands', 'expression_uses'))
    nodes, outputs = c['nodes_total'], c['outputs_total']
    kinds, targets, actions, guards = c['node_kinds'], c['target_statuses'], c['action_statuses'], c['guard_statuses']
    parsed, unparsed = c['rung_statuses']['parsed'], c['rung_statuses']['unparsed']
    predicates = kinds['predicate']
    opaque = kinds['opaque_transfer']
    passes = kinds.get('pass_through', 0)
    stateful = kinds.get('stateful_transfer', 0)
    stateful_gaps = c.get('binding_gap_stateful', 0)
    stateful_outputs = c.get('outputs_with_stateful_conditions', 0)
    if (max(rungs, instructions, operands, expressions, nodes, outputs) > MAX_RECORDS
            or c['branch_legs'] > MAX_EVIDENCE_IDS
            or parsed + unparsed != rungs or kinds['entry'] != parsed
            or sum(kinds.values()) != nodes
            or predicates != kinds['all'] or sum(c['predicate_opcodes'].values()) != predicates
            or kinds['any'] != c['branch_joins']
            or sum(c['opaque_reasons'].values()) != opaque
            or sum(c.get('passthrough_opcodes', {}).values()) != passes
            or sum(c.get('stateful_opcodes', {}).values()) != stateful
            or predicates + passes + stateful + opaque + actions['recognized'] != instructions
            or any(sum(c[key].values()) != outputs for key in ('output_opcodes', 'guard_statuses', 'action_statuses', 'target_statuses'))
            or actions['unresolved'] != targets['signature_unresolved']
            or actions['unresolved'] > c['opaque_reasons']['signature_unresolved']
            or c['opaque_reasons']['signature_unresolved'] > opaque
            or outputs > instructions
            or c['rungs_with_outputs'] > min(parsed, outputs)
            or bool(c['rungs_with_outputs']) != bool(outputs)
            or c['output_addresses'] > targets['exact_address']
            or bool(c['output_addresses']) != bool(targets['exact_address'])
            or c['binding_gap_predicates'] > predicates
            or stateful_gaps > stateful
            or stateful_outputs > outputs
            or (stateful_outputs and not stateful)
            or (guards['binding_gaps'] and not (c['binding_gap_predicates'] or stateful_gaps))
            or (version >= 3 and not c['binding_gap_predicates']
                and guards['binding_gaps'] > stateful_outputs)
            or (guards['opaque'] and not opaque)
            or c['outputs_with_branches'] > outputs
            or (c['outputs_with_branches'] and not c['branch_joins'])
            or c['branch_legs'] < 2 * c['branch_joins']
            or bool(c['branch_legs']) != bool(c['branch_joins'])
            or (not parsed and (instructions or nodes or c['branch_joins']))
            or (not instructions and (operands or expressions))
            or (not operands and expressions)
            or predicates + passes + stateful + actions['recognized'] > operands):
        _invalid()
    if version >= 4:
        transfers, contributors = c['opaque_opcodes'], c['opaque_guard_opcodes']
        if (sum(transfers.values()) != opaque
                or any(value > guards['opaque'] or (value and not transfers[opcode])
                       for opcode, value in contributors.items())
                or sum(contributors.values()) < guards['opaque']):
            _invalid()
    if version >= 5:
        statuses = c['aoi_identity_statuses']
        if (statuses['modeled'] != c['passthrough_opcodes']['custom']
                or sum(statuses.values()) - statuses['modeled'] != c['opaque_opcodes']['withheld']):
            _invalid()
        gsv = c['gsv_signature_statuses']
        if (gsv['modeled'] != c['passthrough_opcodes']['GSV']
                or sum(gsv.values()) - gsv['modeled'] != c['opaque_opcodes']['GSV']
                or gsv['namespace'] > c['opaque_reasons']['source_unqualified']
                or sum(gsv.values()) - gsv['modeled'] - gsv['namespace'] > c['opaque_reasons']['signature_unresolved']):
            _invalid()
    if version >= 6:
        if (sum(c['aoi_body_gap_reasons'].values()) != c['aoi_identity_statuses']['body_unqualified']
                or sum(c['gsv_instance_gap_forms'].values()) != c['gsv_signature_statuses']['instance_syntax']):
            _invalid()
    partial = bool(unparsed or opaque or c['binding_gap_predicates'] or stateful_gaps
                   or outputs != targets['exact_address'])
    if summary['status'] != ('partial' if partial else 'complete'):
        _invalid()


def build_condition_summary(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                            access: AccessResult, calculations: CalculationResult,
                            rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
                            result: ConditionResult, revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_conditions(snapshot, inventory, references, access, calculations, rung_analysis, relationships, result)
        summary = {**summary_constants(result.schema_version), 'status': result.status, 'coverage': deepcopy(result.coverage),
                   'tool_revision': revision if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        validate_condition_summary(summary)
        summary['tool_revision'] = dict(summary['tool_revision'])
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_condition_summary(summary: dict[str, Any]) -> str:
    validate_condition_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=True, sort_keys=True,
                          indent=1 if summary['schema_version'] >= 5 else 2) + '\n'
    limit = MAX_REPORT_V4_BYTES if summary['schema_version'] >= 4 else MAX_REPORT_BYTES
    if len(rendered) > limit:
        _invalid()
    return rendered
