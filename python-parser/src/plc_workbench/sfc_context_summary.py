"""Closed counts for SFC source relationships; no names, IDs or source text."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .rack_candidates import RACK_MATCH_STATUSES
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult
from .sfc_conditions import SfcConditionResult
from .sfc_structure import SfcStructureResult
from .sfr_context import SfrContextResult
from .sfc_context import (COUNT_MAPS, COVERAGE_KEYS, SFC_CONTEXT_CONSTANTS,
    MAX_EVIDENCE_IDS, MAX_SFC_CONTEXT_BYTES, MAX_SFC_CONTEXT_JSON_BYTES,
    MAX_SFC_CONTEXT_RECORDS, SfcContextResult, _partial, validate_sfc_context)

MAX_REPORT_BYTES = 4096
MAX_REPORT_V2_BYTES = 5 * 1024
CONSTANTS = {**SFC_CONTEXT_CONSTANTS, 'policy_version': 2,
    'report_kind': 'l5x_sfc_context_review_summary', 'exporter_version': 'sfc-context-summary-1',
    'sharing_status': 'aggregate_sync_allowed'}
V2_CONSTANTS = {**CONSTANTS, 'schema_version': 2, 'exporter_version': 'sfc-context-summary-2'}
GAP_REASONS = frozenset({'none', 'other', 'root_not_declared', 'colon_root_not_declared',
    'invalid_scope', 'aoi_alias_target_not_local', 'empty_address', 'address_length_limit',
    'program_qualified_address', 'backslash_qualified_address', 'non_static_array_index',
    'malformed_address', 'expanded_suffix_limit'})
GAP_MAPS = {'binding_reasons': GAP_REASONS,
    'alias_rack_matches': frozenset(RACK_MATCH_STATUSES) | {'not_applicable', 'no_record'},
    'unique_rack_match_directions': frozenset({'input', 'output'})}
GAP_KEYS = frozenset(GAP_MAPS) | {'alias_gap_references', 'distinct_terminal_aliases',
    'distinct_unique_rack_candidates'}


class SfcContextSummaryError(ValueError):
    """Fixed source-free rejection."""


def _invalid() -> None:
    raise SfcContextSummaryError('SFC context summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != expected:
        _invalid()


def validate_sfc_context_summary(summary: dict[str, Any]) -> None:
    if type(summary) is not dict or type(summary.get('schema_version')) is not int:
        _invalid()
    version = summary['schema_version']
    constants = {1: CONSTANTS, 2: V2_CONSTANTS}.get(version)
    if constants is None:
        _invalid()
    _keys(summary, set(constants) | {'status', 'tool_revision', 'coverage'}
          | ({'gap_diagnostics'} if version == 2 else set()))
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
    refs, addresses, links, gaps = (c[key] for key in ('references_total', 'addresses_total', 'step_links_total', 'gaps_total'))
    exact = c['references_by_status']['exact_address']
    accepted, rejected = c['accepted_operands_by_role'], c['rejected_operands_by_role']
    accepted_uses = sum(accepted.values()) + c['accepted_expression_uses']
    rejected_uses = sum(rejected.values()) + c['rejected_expression_uses']
    bound, lexical = (c['step_links_by_evidence'][key] for key in ('bound_identity', 'lexical_hint'))
    outside = c['outside_scope_declarations'] + c['unqualified_outside_scope_declarations']
    associated_ids = exact + links + lexical + outside + accepted_uses + rejected_uses
    minimum_bytes = 64 * (9 * refs + 2 * addresses + 5 * links + 2 * gaps + associated_ids)
    if (refs != c['source_references'] or sum(c['references_by_status'].values()) != refs
            or gaps != refs - exact or addresses > exact or bool(addresses) != bool(exact)
            or refs + addresses + links + gaps > MAX_SFC_CONTEXT_RECORDS
            or max(c[key] for key in ('source_transitions', 'source_references', 'source_steps',
                   'source_rll_addresses', 'source_operands', 'source_expression_uses')) > MAX_SFC_CONTEXT_RECORDS
            or c['source_unparsed_transitions'] > c['source_transitions']
            or refs and c['source_transitions'] == c['source_unparsed_transitions']
            or sum(c['gaps_by_kind'].values()) != gaps or sum(c['gaps_by_lexical_kind'].values()) != gaps
            or any(sum(c[key].values()) != links for key in
                   ('step_links_by_evidence', 'step_links_by_relation', 'step_links_by_match'))
            or links > refs * c['source_steps'] or bound > exact * c['source_steps']
            or lexical > gaps * c['source_steps'] or c['unqualified_step_links'] > lexical
            or c['references_with_step_links'] > refs
            or c['references_with_multiple_steps'] > c['references_with_step_links']
            or links < c['references_with_step_links'] + c['references_with_multiple_steps']
            or bool(links) != bool(c['references_with_step_links'])
            or c['references_with_step_links'] and links > c['references_with_step_links'] * c['source_steps']
            or c['gaps_with_lexical_steps'] > min(gaps, lexical)
            or bool(lexical) != bool(c['gaps_with_lexical_steps'])
            or c['gaps_with_outside_declarations'] > min(gaps, outside)
            or bool(outside) != bool(c['gaps_with_outside_declarations'])
            or sum(accepted.values()) + sum(rejected.values()) > c['source_operands']
            or c['accepted_expression_uses'] + c['rejected_expression_uses'] > c['source_expression_uses']
            or c['addresses_with_rll_evidence'] > min(addresses, accepted_uses, c['source_rll_addresses'])
            or bool(accepted_uses) != bool(c['addresses_with_rll_evidence'])
            or c['addresses_with_rejected_uses'] > min(addresses, rejected_uses, c['source_rll_addresses'])
            or bool(rejected_uses) != bool(c['addresses_with_rejected_uses'])
            or c['addresses_with_rll_readers'] > min(c['addresses_with_rll_evidence'], accepted['read'] + accepted['read_write'] + c['accepted_expression_uses'])
            or bool(c['addresses_with_rll_readers']) != bool(accepted['read'] + accepted['read_write'] + c['accepted_expression_uses'])
            or c['addresses_with_rll_writers'] > min(c['addresses_with_rll_evidence'], accepted['write'] + accepted['read_write'])
            or bool(c['addresses_with_rll_writers']) != bool(accepted['write'] + accepted['read_write'])
            or c['addresses_with_unknown_roles'] > min(c['addresses_with_rll_evidence'], accepted['unknown'])
            or bool(c['addresses_with_unknown_roles']) != bool(accepted['unknown'])
            or c['addresses_with_rll_evidence'] > c['addresses_with_rll_readers'] + c['addresses_with_rll_writers'] + c['addresses_with_unknown_roles']
            or associated_ids > MAX_EVIDENCE_IDS
            or minimum_bytes > min(MAX_SFC_CONTEXT_BYTES, MAX_SFC_CONTEXT_JSON_BYTES)):
        _invalid()
    if summary['status'] != ('partial' if _partial(c) else 'complete'):
        _invalid()
    if version == 2:
        d = summary['gap_diagnostics']
        _keys(d, GAP_KEYS)
        for key, value in d.items():
            if key in GAP_MAPS:
                _keys(value, GAP_MAPS[key])
                counts = value.values()
            else:
                counts = (value,)
            if any(type(count) is not int or not 0 <= count <= 10**12 for count in counts):
                _invalid()
        aliases = d['alias_gap_references']
        terminal = d['distinct_terminal_aliases']
        matches = d['alias_rack_matches']
        unique = matches['unique_candidate']
        candidates = d['distinct_unique_rack_candidates']
        eligible = aliases - matches['not_applicable']
        if (sum(d['binding_reasons'].values()) != gaps
                or aliases != c['gaps_by_kind']['alias_chain_gap']
                or sum(matches.values()) != aliases
                or terminal > aliases or bool(terminal) != bool(aliases)
                or eligible > d['binding_reasons']['colon_root_not_declared']
                or sum(d['unique_rack_match_directions'].values()) != unique
                or candidates > min(unique, terminal) or bool(candidates) != bool(unique)):
            _invalid()


def _gap_diagnostics(references: ReferenceResult, conditions: SfcConditionResult,
                     result: SfcContextResult) -> dict[str, Any]:
    """Count existing alias/rack hints without interpreting or exporting addresses.

    Reference analysis already compares every alias declaration with rack roots.
    Reuse its original-alias match only when the failing root and lookup scope
    agree. A candidate remains unbound; no target/member mapping is inferred.
    These reuse the rack model's lexical hints, not the qualified RLL-address
    namespace. Module/port namespace provenance is not requalified here.
    """
    d = {key: dict.fromkeys(sorted(values), 0) for key, values in GAP_MAPS.items()}
    d.update(dict.fromkeys(sorted(GAP_KEYS - GAP_MAPS.keys()), 0))
    sources = {row['id']: row for row in conditions.references}
    contexts = {row['id']: row for row in result.references}
    matches = {row['source_id']: row for row in references.rack_candidates['matches']['aliases']}
    candidates = {row['source_id']: row for row in references.rack_candidates['candidates']}
    terminal_aliases: set[str] = set()
    unique_candidates: set[str] = set()
    for gap in result.gaps:
        source = sources[contexts[gap['reference_id']]['condition_reference_id']]
        binding = source['binding']
        reason = binding['reason']
        bucket = 'none' if reason is None else reason if reason in GAP_REASONS else 'other'
        d['binding_reasons'][bucket] += 1
        if gap['kind'] != 'alias_chain_gap':
            continue
        d['alias_gap_references'] += 1
        terminal_aliases.add(binding['alias_chain'][-1])
        status = 'not_applicable'
        if source['binding_status'] == 'unresolved' and reason == 'colon_root_not_declared':
            match = matches.get(binding['symbol_id'])
            status = 'no_record'
            if (match is not None and match['terminal_root'] == gap['root_text']
                    and match['lookup_scope_id'] == gap['lookup_scope_id']):
                status = match['status']
                if status == 'unique_candidate':
                    candidate = candidates[match['candidate_id']]
                    d['unique_rack_match_directions'][candidate['direction']] += 1
                    unique_candidates.add(candidate['source_id'])
        d['alias_rack_matches'][status] += 1
    d['distinct_terminal_aliases'] = len(terminal_aliases)
    d['distinct_unique_rack_candidates'] = len(unique_candidates)
    return d


def build_sfc_context_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        sfc_structure: SfcStructureResult, sfr_context: SfrContextResult,
        sfc_conditions: SfcConditionResult, result: SfcContextResult,
        revision: dict[str, Any] | None = None, *, schema_version: int = 1) -> dict[str, Any]:
    try:
        if type(schema_version) is not int or schema_version not in (1, 2):
            _invalid()
        validate_sfc_context(snapshot, inventory, references, access, calculations,
            rung_analysis, relationships, sfc_structure, sfr_context, sfc_conditions, result)
        summary = {**(CONSTANTS if schema_version == 1 else V2_CONSTANTS),
            'status': result.status, 'coverage': deepcopy(result.coverage),
            'tool_revision': dict(revision) if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        if schema_version == 2:
            summary['gap_diagnostics'] = _gap_diagnostics(references, sfc_conditions, result)
        render_sfc_context_summary(summary)
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_sfc_context_summary(summary: dict[str, Any]) -> str:
    validate_sfc_context_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    limit = MAX_REPORT_BYTES if summary['schema_version'] == 1 else MAX_REPORT_V2_BYTES
    if len(rendered.encode('utf-8')) > limit:
        _invalid()
    return rendered
