"""Bounded aggregate report; never serialize private records here.

Every output key and string comes from a fixed vocabulary, except a verified
code revision supplied by the CLI. Tyler authorizes these aggregates for repo
sync: they contain no individual rung logic or process values. This policy does
not authorize other source-derived artifacts or act as a general redactor.
"""
from __future__ import annotations

from collections import Counter
import json
import re
from typing import Any

from .ladder.syntax import MAX_BRANCH_LEGS, MAX_DEPTH, MAX_NODES, PUBLIC_OPCODES
from .models import InventoryResult

MAX_REPORT_BYTES = 32 * 1024
MAX_COUNT = 10**12
COUNT_KEYS = frozenset('''controllers modules tasks programs user_data_types
    aoi_definitions trends encoded_regions controller_tags program_tags
    other_tag_definitions total_tag_definitions aoi_local_tags aoi_parameters
    aliases routines rungs instructions'''.split())
# Same publication vocabulary as the existing value-profile helper. Exact match
# only: a familiar literal in a Name/operand field never grants publication.
ROUTINE_TYPES = frozenset({'RLL', 'FBD', 'SFC', 'ST', 'Sequence'})
DIAGNOSTIC_CODES = frozenset('''encoded_content entity_name_missing
    declaration_context_not_analyzed controller_context_missing
    routine_language_not_analyzed routine_content_missing routine_content_mismatch
    routine_content_not_analyzed rung_context_not_analyzed rung_content_not_analyzed
    rung_text_unavailable rung_metadata_missing descriptive_text_ambiguous
    node_limit branch_leg_limit argument_slot_limit branch_depth_limit
    unclosed_branch branch_requires_two_legs expected_instruction
    expected_argument_list argument_depth_limit mismatched_argument_delimiter
    semicolon_inside_argument unclosed_quote unclosed_argument_list text_limit
    missing_rung_terminator unexpected_branch_separator trailing_content'''.split())
RUNG_STATES = frozenset({'parsed', 'failed', 'preserved_unsupported', 'excluded'})
ROUTINE_STATES = RUNG_STATES - {'excluded'}
SEVERITIES = frozenset({'info', 'warning', 'error'})
TOTAL_METRICS = frozenset('''instruction_calls argument_slots nonempty_argument_fields
    expression_instruction_calls branch_groups branch_legs empty_branch_legs'''.split())
MAX_METRICS = frozenset({'max_branch_depth', 'max_legs_in_group', 'height_lanes', 'width_instructions'})
CONSTANTS = {
    'schema_version': 2,
    'policy_version': 2,
    'report_kind': 'l5x_aggregate_review_summary',
    'exporter_version': 'aggregate-summary-2',
    'parser_version': 'source-inventory-1',
    'analysis_scope': 'source_structure_only',
    'semantic_analysis': 'not_implemented',
    'sharing_status': 'aggregate_sync_allowed',
}


class SummaryError(ValueError):
    """A fixed, source-free error; never interpolate rejected keys or values."""


def _invalid() -> None:
    raise SummaryError('Summary validation failed; no shareable candidate was produced.')


def _count(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= MAX_COUNT:
        _invalid()
    return value


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or value.keys() != expected:
        _invalid()


def _counts(values: Any, keys: set[str] | frozenset[str], *, sparse: bool = False) -> None:
    if sparse:
        if type(values) is not dict or not values.keys() <= keys or 'withheld' not in values:
            _invalid()
    else:
        _keys(values, keys)
    for value in values.values():
        _count(value)


def _pooled(values: dict[str, int], allowed: frozenset[str]) -> dict[str, int]:
    result: Counter[str] = Counter({'withheld': 0})
    for label, value in values.items():
        result[label if label in allowed else 'withheld'] += _count(value)
    return dict(sorted(result.items()))


def build_summary(result: InventoryResult, *, revision: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reconstruct approved aggregates, without copying a private payload.

    Only this reader's v1 contract is supported. Adding fields or changing its
    meaning requires explicitly reviewing this publication policy as well.
    """
    if (type(result.schema_version) is not int or result.schema_version != 1
            or result.parser_version != CONSTANTS['parser_version']
            or result.analysis_scope != CONSTANTS['analysis_scope']
            or result.semantic_analysis != CONSTANTS['semantic_analysis']):
        _invalid()
    try:
        counts = {key: _count(result.counts[key]) for key in sorted(COUNT_KEYS)}
        routine_types = dict.fromkeys(sorted(ROUTINE_TYPES | {'missing', 'withheld'}), 0)
        for entity in result.entities:
            if entity.kind == 'routine':
                language = entity.attributes.get('Type')
                key = 'missing' if language is None else language if language in ROUTINE_TYPES else 'withheld'
                routine_types[key] += 1

        # Do not use the private '<missing>' dictionary sentinel: a literal Type
        # with that spelling is unlisted, not a missing source attribute.
        routine_coverage = {key: _count(result.coverage['routines'][key])
                            for key in sorted(ROUTINE_STATES | {'encountered'})}
        rung_coverage = {key: _count(result.coverage['rungs'][key])
                         for key in sorted(RUNG_STATES | {'encountered'})}
        observed: Counter[str] = Counter()
        totals = dict.fromkeys(sorted(TOTAL_METRICS), 0)
        maxima = dict.fromkeys(sorted(MAX_METRICS), 0)
        for rung in result.rungs:
            if rung.parse_status not in RUNG_STATES:
                _invalid()
            observed[rung.parse_status] += 1
            if rung.parse_status == 'parsed':
                for key in totals:
                    totals[key] += _count(rung.metrics[key])
                for key in maxima:
                    maxima[key] = max(maxima[key], _count(rung.metrics[key]))
        if any(observed[key] != rung_coverage[key] for key in RUNG_STATES):
            _invalid()

        paths = result.coverage['unmodeled_xml_paths']
        by_code = Counter(d.code for d in result.diagnostics)
        by_severity = Counter(d.severity if d.severity in SEVERITIES else 'withheld'
                              for d in result.diagnostics)
        summary = dict(CONSTANTS) | {
            'tool_revision': dict(revision) if revision is not None else {'commit': None, 'worktree': 'unavailable'},
            'status': result.status,
            'counts': counts,
            'routine_types': routine_types,
            'coverage': {
                'xml_elements': _count(result.coverage['xml_elements']),
                'routines': routine_coverage,
                'rungs': rung_coverage,
                'instruction_count_complete': result.coverage['instruction_count_complete'],
                'unmodeled_xml': {'distinct_paths': len(paths),
                                 'elements': sum(_count(row['count']) for row in paths)},
            },
            'instructions': {
                'scope': 'successfully_parsed_RLL_rungs_only',
                'total': counts['instructions'],
                'counts': _pooled(result.instruction_counts, PUBLIC_OPCODES),
            },
            'ladder_metrics': {'scope': 'successfully_parsed_RLL_rungs_only',
                               'totals': totals, 'maxima': maxima},
            'diagnostics': {
                'total': len(result.diagnostics),
                'by_code': _pooled(by_code, DIAGNOSTIC_CODES),
                'by_severity': {key: by_severity[key] for key in sorted(SEVERITIES | {'withheld'})},
            },
        }
    except (KeyError, TypeError, AttributeError):
        _invalid()
    validate_summary(summary)
    return summary


def validate_summary(summary: dict[str, Any]) -> None:
    """Check the entire output boundary, including aggregate reconciliation."""
    _keys(summary, set(CONSTANTS) | {'tool_revision', 'status', 'counts', 'routine_types',
                                    'coverage', 'instructions', 'ladder_metrics', 'diagnostics'})
    for key, expected in CONSTANTS.items():
        if type(summary[key]) is not type(expected) or summary[key] != expected:
            _invalid()
    if summary['status'] not in ('complete', 'partial'):
        _invalid()
    revision = summary['tool_revision']
    _keys(revision, {'commit', 'worktree'})
    if revision['worktree'] == 'unavailable':
        if revision['commit'] is not None:
            _invalid()
    elif revision['worktree'] in ('clean', 'modified'):
        if type(revision['commit']) is not str or re.fullmatch(r'[0-9a-f]{40}', revision['commit']) is None:
            _invalid()
    else:
        _invalid()
    counts = summary['counts']
    _counts(counts, COUNT_KEYS)
    _counts(summary['routine_types'], ROUTINE_TYPES | {'missing', 'withheld'})
    coverage = summary['coverage']
    _keys(coverage, {'xml_elements', 'routines', 'rungs', 'instruction_count_complete', 'unmodeled_xml'})
    _count(coverage['xml_elements'])
    if type(coverage['instruction_count_complete']) is not bool:
        _invalid()
    for plural, states in (('routines', ROUTINE_STATES), ('rungs', RUNG_STATES)):
        group = coverage[plural]
        _counts(group, states | {'encountered'})
        if sum(group[key] for key in states) != group['encountered'] or group['encountered'] != counts[plural]:
            _invalid()
    _counts(coverage['unmodeled_xml'], {'distinct_paths', 'elements'})
    if not (coverage['unmodeled_xml']['distinct_paths'] <= coverage['unmodeled_xml']['elements'] <= coverage['xml_elements']):
        _invalid()
    if (sum(summary['routine_types'].values()) != counts['routines']
            or counts['aliases'] > counts['total_tag_definitions']
            or sum(counts[key] for key in ('controller_tags', 'program_tags', 'other_tag_definitions')) != counts['total_tag_definitions']):
        _invalid()
    instructions = summary['instructions']
    _keys(instructions, {'scope', 'total', 'counts'})
    _count(instructions['total'])
    _counts(instructions['counts'], PUBLIC_OPCODES | {'withheld'}, sparse=True)
    if (instructions['scope'] != 'successfully_parsed_RLL_rungs_only'
            or instructions['total'] != counts['instructions']
            or sum(instructions['counts'].values()) != instructions['total']):
        _invalid()
    metrics = summary['ladder_metrics']
    _keys(metrics, {'scope', 'totals', 'maxima'})
    _counts(metrics['totals'], TOTAL_METRICS)
    _counts(metrics['maxima'], MAX_METRICS)
    if metrics['scope'] != instructions['scope'] or metrics['totals']['instruction_calls'] != instructions['total']:
        _invalid()
    if (metrics['totals']['nonempty_argument_fields'] > metrics['totals']['argument_slots']
            or metrics['totals']['empty_branch_legs'] > metrics['totals']['branch_legs']
            or metrics['totals']['expression_instruction_calls'] > instructions['total']):
        _invalid()
    # A future parser may raise its limits, but this policy must not silently
    # claim v1 provenance for measurements the supported parser cannot produce.
    if (metrics['maxima']['max_branch_depth'] > MAX_DEPTH
            or metrics['maxima']['max_legs_in_group'] > MAX_BRANCH_LEGS
            or metrics['maxima']['height_lanes'] > MAX_BRANCH_LEGS
            or metrics['maxima']['width_instructions'] > MAX_NODES
            or instructions['total'] > MAX_NODES * coverage['rungs']['parsed']
            or metrics['totals']['branch_legs'] > MAX_BRANCH_LEGS * coverage['rungs']['parsed']):
        _invalid()
    if not coverage['rungs']['parsed'] and (any(metrics['totals'].values()) or any(metrics['maxima'].values())):
        _invalid()
    diagnostics = summary['diagnostics']
    _keys(diagnostics, {'total', 'by_code', 'by_severity'})
    _count(diagnostics['total'])
    _counts(diagnostics['by_code'], DIAGNOSTIC_CODES | {'withheld'}, sparse=True)
    _counts(diagnostics['by_severity'], SEVERITIES | {'withheld'})
    if any(sum(diagnostics[key].values()) != diagnostics['total'] for key in ('by_code', 'by_severity')):
        _invalid()
    incomplete = (counts['encoded_regions'] or coverage['routines']['failed']
                  or coverage['routines']['preserved_unsupported'] or coverage['rungs']['failed']
                  or coverage['rungs']['preserved_unsupported'] or coverage['rungs']['excluded'])
    if incomplete and coverage['instruction_count_complete']:
        _invalid()
    if summary['status'] == 'complete' and (not coverage['instruction_count_complete']
            or diagnostics['by_severity']['error'] or diagnostics['by_severity']['warning']
            or diagnostics['by_severity']['withheld']):
        _invalid()


def render_summary(summary: dict[str, Any]) -> str:
    """Serialize only a validated, bounded publication candidate."""
    validate_summary(summary)
    rendered = json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        raise SummaryError('Summary exceeds its publication size limit; no candidate was produced.')
    return rendered
