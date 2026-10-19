"""Closed, source-free counts for factorized Boolean signal source context."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .conditions import ConditionResult
from .execution_context import ExecutionContextResult
from .models import InventoryResult, SourceSnapshot
from .output_context import BooleanOutputContextResult
from .references import ReferenceResult
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult
from .signal_context import (COUNT_MAPS, COVERAGE_KEYS, MAX_EVIDENCE_IDS,
    MAX_SIGNAL_CONTEXT_BYTES, MAX_SIGNAL_CONTEXT_JSON_BYTES, MAX_SIGNAL_CONTEXT_RECORDS,
    MAX_SIGNAL_CONTEXT_V2_BYTES, MAX_SIGNAL_CONTEXT_V2_JSON_BYTES,
    MAX_SIGNAL_CONTEXT_V3_BYTES, MAX_SIGNAL_CONTEXT_V3_JSON_BYTES,
    MAX_SIGNAL_CONTEXT_V4_BYTES, MAX_SIGNAL_CONTEXT_V4_JSON_BYTES,
    MAX_SIGNAL_CONTEXT_V5_BYTES, MAX_SIGNAL_CONTEXT_V5_JSON_BYTES,
    ROW_GROUPS, SIGNAL_CONTEXT_CONSTANTS, SignalContextResult, _partial, validate_signal_context,
    signal_context_constants, signal_context_count_maps, signal_context_coverage_keys)
from .signal_patterns import (MAX_GUARD_PATTERN_NODES, MAX_GUARD_PATTERN_EDGES,
    MAX_PATTERN_VISITED_NODES, MAX_PATTERN_VISITED_EDGES, MAX_PATTERN_LINKS)
from .signal_authored import (AUTHORED_ADDRESS_BYTES, AUTHORED_FIXED_BYTES, MAX_AUTHORED_FIELDS,
    MAX_AUTHORED_USE_VISITS, MAX_AUTHORED_CHARACTERS, MAX_AUTHORED_ROWS,
    MAX_AUTHORED_USE_IDS, MAX_AUTHORED_BYTES)
from .signal_dependencies import (MAX_GUARD_DEPENDENCY_NODES, MAX_GUARD_DEPENDENCY_EDGES,
    MAX_DEPENDENCY_VISITED_NODES, MAX_DEPENDENCY_VISITED_EDGES,
    MAX_DEPENDENCY_LINKS, MAX_DEPENDENCY_CACHE_READS)
from .signal_candidates import (MAX_CANDIDATE_AUTHORED_VISITS, MAX_CANDIDATE_INDEX_LINKS,
    MAX_CANDIDATE_DEPENDENCY_VISITS, MAX_CANDIDATE_PAIRS, MAX_CANDIDATE_BYTES,
    CANDIDATE_FIXED_BYTES, CANDIDATE_OUTPUT_BYTES, CANDIDATE_TARGET_BYTES, CANDIDATE_PAIR_BYTES)
from .stateful_objects import StatefulObjectResult
from .tag_data import TagDataResult

MAX_REPORT_BYTES = 8 * 1024
MAX_REPORT_V2_BYTES = 12 * 1024
MAX_REPORT_V3_BYTES = 16 * 1024
MAX_REPORT_V4_BYTES = 20 * 1024
MAX_REPORT_V5_BYTES = 24 * 1024
CONSTANTS = {**SIGNAL_CONTEXT_CONSTANTS, 'policy_version': 2,
    'report_kind': 'l5x_signal_context_review_summary', 'exporter_version': 'signal-context-summary-1',
    'sharing_status': 'aggregate_sync_allowed'}


def constants_for(version: int = 1) -> dict[str, Any]:
    if type(version) is not int or version not in {1, 2, 3, 4, 5}:
        _invalid()
    return {**CONSTANTS, **signal_context_constants(version),
        'exporter_version': f'signal-context-summary-{version}'}


class SignalContextSummaryError(ValueError):
    """Fixed source-free publication rejection."""


def _invalid() -> None:
    raise SignalContextSummaryError('Signal context summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != expected:
        _invalid()


def validate_signal_context_summary(summary: dict[str, Any]) -> None:
    _keys(summary, set(CONSTANTS) | {'status', 'tool_revision', 'coverage'})
    version = summary['schema_version']
    constants = constants_for(version)
    maps, coverage_keys = signal_context_count_maps(version), signal_context_coverage_keys(version)
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
    _keys(c, coverage_keys)
    for key, value in c.items():
        values = (value,)
        if key in maps:
            _keys(value, maps[key])
            values = value.values()
        if any(type(count) is not int or not 0 <= count <= 10**12 for count in values):
            _invalid()
    outputs, reads, addresses, rungs = (c[f'{key}_total'] for key in ROW_GROUPS)
    exact_outputs = c['targets_by_status']['exact_address']
    exact_reads = c['reads_by_status']['exact_address']
    coil_addresses = c['address_profiles']['coil_and_condition'] + c['address_profiles']['coil_only']
    read_addresses = c['address_profiles']['coil_and_condition'] + c['address_profiles']['condition_only']
    accepted_operands = sum(c['accepted_operands_by_role'].values())
    rejected_operands = sum(c['rejected_operands_by_role'].values())
    uses = accepted_operands + rejected_operands + c['accepted_expression_uses'] + c['rejected_expression_uses']
    records = outputs + reads + addresses + rungs
    # Every retained occurrence appears once in its rung and, when exact, once
    # in its address. Other source usage lists remain disjoint address groups.
    minimum_links = outputs + reads + exact_outputs + exact_reads + uses + c['noncoil_writers_total']
    if version >= 2:
        self_contacts = sum(c['pattern_self_contacts_by_kind'].values())
        timer_contacts = sum(c['pattern_timer_contacts_by_member'].values())
        groups = c['pattern_coil_contexts_total']
        paired = c['pattern_set_reset_contexts']
        grouped = c['pattern_grouped_outputs_by_opcode']
        minimum_links += exact_outputs + self_contacts + 2 * timer_contacts + 2 * groups
        if (sum(c['pattern_traversals_by_status'].values()) != outputs
                or c['pattern_unique_guards_total'] > min(outputs, c['source_condition_nodes'])
                or bool(c['pattern_unique_guards_total']) != bool(outputs)
                or c['pattern_visited_nodes'] > min(MAX_PATTERN_VISITED_NODES,
                    c['pattern_unique_guards_total'] * MAX_GUARD_PATTERN_NODES)
                or c['pattern_visited_edges'] > min(MAX_PATTERN_VISITED_EDGES,
                    c['pattern_unique_guards_total'] * MAX_GUARD_PATTERN_EDGES)
                or c['pattern_traversals_by_status']['complete'] and not c['pattern_visited_nodes']
                or (not c['pattern_traversals_by_status']['truncated']
                    and c['pattern_visited_nodes'] < c['pattern_unique_guards_total'])
                or self_contacts + timer_contacts > MAX_PATTERN_LINKS
                or any(c['pattern_self_contacts_by_kind'][kind] > exact_outputs * min(exact_reads, c['reads_by_kind'][kind])
                    for kind in ('xic', 'xio'))
                or c['pattern_outputs_with_self_contacts'] > exact_outputs
                or timer_contacts > outputs * min(exact_reads,
                    c['reads_by_kind']['xic'] + c['reads_by_kind']['xio'])
                or timer_contacts and not c['stateful_associations_by_qualification']['qualified']
                or timer_contacts and not c['stateful_associations_by_kind']['direct_member']
                or groups > exact_outputs or groups < coil_addresses
                or bool(groups) != bool(exact_outputs)
                or sum(grouped.values()) != exact_outputs
                or any(grouped[opcode] > c['outputs_by_opcode'][opcode] for opcode in grouped)
                or paired > min(groups, grouped['OTL'], grouped['OTU'])
                or c['pattern_addresses_with_set_reset'] > min(paired, coil_addresses)
                or bool(c['pattern_addresses_with_set_reset']) != bool(paired)):
            _invalid()
        for count, contacts in (('pattern_outputs_with_self_contacts', self_contacts),
                                ('pattern_outputs_with_timer_contacts', timer_contacts)):
            if c[count] > min(outputs, contacts) or bool(c[count]) != bool(contacts):
                _invalid()
    if version >= 3:
        authored_rows = c['authored_evidence_total']
        qualified_rows = c['authored_evidence_by_qualification']['qualified']
        unqualified_rows = c['authored_evidence_by_qualification']['namespace_gap']
        fields = c['authored_fields_scanned']
        sources = c['authored_sources_total']
        visits = c['authored_use_visits']
        operand_links, expression_links, gap_links = (c[key] for key in (
            'authored_operand_links', 'authored_expression_links', 'authored_description_gap_links'))
        links = operand_links + expression_links
        scans = c['authored_field_scans_by_status']
        truncated = c['authored_scans_by_status']['truncated']
        category_links = sum(c['authored_qualified_evidence_by_category'].values()) + sum(
            c['authored_unqualified_evidence_by_category'].values())
        minimum_links += authored_rows + 2 * category_links + links + gap_links
        if (sum(c['authored_scans_by_status'].values()) != addresses
                or visits > min(MAX_AUTHORED_USE_VISITS, accepted_operands + c['accepted_expression_uses'])
                or not truncated and visits != accepted_operands + c['accepted_expression_uses']
                or fields > min(MAX_AUTHORED_FIELDS, 2 * sources, 4 * visits)
                or sources > min(fields, 2 * visits) or bool(sources) != bool(fields)
                or sum(scans.values()) != fields
                or c['authored_characters_scanned'] > MAX_AUTHORED_CHARACTERS
                or not fields and c['authored_characters_scanned']
                or scans['matched'] + scans['no_match'] + scans['namespace_gap'] > c['authored_characters_scanned']
                or authored_rows > min(MAX_AUTHORED_ROWS, 4 * visits, links)
                or links + gap_links > MAX_AUTHORED_USE_IDS
                or operand_links > 4 * accepted_operands
                or expression_links > 4 * c['accepted_expression_uses']
                or bool(links) != bool(authored_rows)
                or any(sum(c[key].values()) != authored_rows for key in (
                    'authored_evidence_by_relation', 'authored_evidence_by_field', 'authored_evidence_by_qualification'))
                or c['authored_evidence_by_relation']['root_declaration'] > 2 * addresses
                or c['authored_evidence_by_relation']['alias_declaration'] > 2 * visits
                or qualified_rows > scans['matched'] * addresses
                or not truncated and scans['matched'] > qualified_rows
                or unqualified_rows > scans['namespace_gap'] * addresses
                or gap_links > min(2 * visits, (scans['ambiguous_text'] + scans['namespace_gap']) * addresses)
                or not truncated and scans['ambiguous_text'] > gap_links
                or (authored_rows or links or gap_links) and (
                    AUTHORED_FIXED_BYTES + AUTHORED_ADDRESS_BYTES * addresses
                    + 1024 * authored_rows + 64 * (links + gap_links) > MAX_AUTHORED_BYTES)):
            _invalid()
        for key, population in (
                ('authored_addresses_with_evidence', authored_rows),
                ('authored_addresses_with_description_gaps', gap_links),
                ('authored_addresses_with_unqualified_evidence', unqualified_rows)):
            if c[key] > min(addresses, population) or bool(c[key]) != bool(population):
                _invalid()
        if c['authored_addresses_with_unqualified_evidence'] > c['authored_addresses_with_evidence']:
            _invalid()
        for map_key, population in (
                ('authored_qualified_evidence_by_category', qualified_rows),
                ('authored_unqualified_evidence_by_category', unqualified_rows),
                ('authored_outputs_by_category', c['authored_outputs_with_evidence'])):
            total = sum(c[map_key].values())
            if not population <= total <= 3 * population or any(value > population for value in c[map_key].values()):
                _invalid()
        for key, row_count in (('authored_outputs_with_evidence', qualified_rows),
                ('authored_outputs_with_unqualified_evidence', unqualified_rows)):
            if c[key] > min(exact_outputs, operand_links, row_count * exact_outputs):
                _invalid()
        if any(c['authored_outputs_by_category'][category] >
                c['authored_qualified_evidence_by_category'][category] * exact_outputs
                for category in c['authored_outputs_by_category']):
            _invalid()
    if version >= 4:
        scans = c['dependency_traversals_by_status']
        guards = c['dependency_unique_guards_total']
        forward = c['dependency_read_links_total']
        reverse = c['dependency_reverse_links_total']
        cached = c['dependency_cached_read_ids']
        linked = c['dependency_outputs_with_reads']
        exact_linked = c['dependency_outputs_with_exact_reads']
        dependent = c['dependency_outputs_with_dependents']
        dependent_addresses = c['dependency_addresses_with_dependents']
        linked_exact_reads = c['dependency_reads_by_status']['exact_address']
        empty_complete = c['dependency_outputs_without_reads_complete']
        minimum_links += forward + reverse
        if (sum(scans.values()) != outputs
                or guards > min(outputs, c['source_condition_nodes'])
                or bool(guards) != bool(outputs)
                or c['dependency_visited_nodes'] > min(MAX_DEPENDENCY_VISITED_NODES,
                    guards * MAX_GUARD_DEPENDENCY_NODES)
                or c['dependency_visited_edges'] > min(MAX_DEPENDENCY_VISITED_EDGES,
                    guards * MAX_GUARD_DEPENDENCY_EDGES)
                or scans['complete'] and not c['dependency_visited_nodes']
                or not scans['truncated'] and c['dependency_visited_nodes'] < guards
                or cached > min(MAX_DEPENDENCY_CACHE_READS, reads * guards)
                or cached and not c['dependency_visited_nodes']
                or forward > cached * outputs
                or forward + reverse > MAX_DEPENDENCY_LINKS
                or sum(c['dependency_reads_by_kind'].values()) != forward
                or sum(c['dependency_reads_by_status'].values()) != forward
                or sum(c['dependency_outputs_with_reads_by_guard_quality'].values()) != linked
                or sum(c['dependency_reverse_links_by_guard_quality'].values()) != reverse
                or c['dependency_reverse_links_by_guard_quality']['namespace_gap']
                or reverse > min(linked_exact_reads, outputs * read_addresses)
                or linked > min(outputs, forward) or bool(linked) != bool(forward)
                or exact_linked > min(linked, linked_exact_reads)
                or bool(exact_linked) != bool(linked_exact_reads)
                or dependent > min(exact_linked, reverse, outputs - c['guards_by_quality']['namespace_gap'])
                or dependent < max(0, exact_linked - c['guards_by_quality']['namespace_gap'])
                or bool(dependent) != bool(reverse)
                or dependent_addresses > min(read_addresses, reverse)
                or bool(dependent_addresses) != bool(reverse)
                or reverse > dependent * dependent_addresses
                or not max(0, scans['complete'] - linked) <= empty_complete
                    <= min(scans['complete'], outputs - linked)):
            _invalid()
        for category in ('kind', 'status'):
            if any(value > c[f'reads_by_{category}'][key] * linked
                    for key, value in c[f'dependency_reads_by_{category}'].items()):
                _invalid()
        for quality, population in c['guards_by_quality'].items():
            with_reads = c['dependency_outputs_with_reads_by_guard_quality'][quality]
            reverse_count = c['dependency_reverse_links_by_guard_quality'][quality]
            if (with_reads > population or reverse_count > with_reads * read_addresses
                    or reverse_count > linked_exact_reads):
                _invalid()
    if version >= 5:
        pairs = c['candidate_pairs_total']
        pair_outputs = c['candidate_outputs_with_pairs']
        target_outputs = c['candidate_outputs_with_target_categories']
        target_links = sum(c['candidate_target_categories'].values())
        condition_links = sum(c['candidate_condition_categories'].values())
        seeds = c['candidate_pairs_by_seed']
        condition_seeded = seeds['condition_only'] + seeds['both']
        target_seeded = seeds['target_only'] + seeds['both']
        target_authored_links = sum(c['candidate_target_categories'][category]
            for category in ('alarm', 'equipment', 'sensor'))
        condition_authored_links = sum(c['candidate_condition_categories'][category]
            for category in ('alarm', 'equipment', 'sensor'))
        eligible_limit = min(exact_outputs, outputs - c['guards_by_quality']['namespace_gap'])
        visits = c['candidate_authored_link_visits']
        index_links = c['candidate_index_category_links']
        minimum_links += pairs + target_links + condition_links
        if (sum(c['candidate_scans_by_status'].values()) != outputs
                or c['candidate_scans_by_status']['truncated'] < c['dependency_traversals_by_status']['truncated']
                or visits > min(MAX_CANDIDATE_AUTHORED_VISITS, c['authored_operand_links'])
                or index_links > min(MAX_CANDIDATE_INDEX_LINKS, 3 * visits)
                or target_authored_links > index_links
                or condition_authored_links > index_links * pair_outputs
                or c['candidate_dependency_visits'] > min(MAX_CANDIDATE_DEPENDENCY_VISITS,
                    c['dependency_read_links_total'])
                or pairs > min(MAX_CANDIDATE_PAIRS, c['candidate_dependency_visits'],
                    c['dependency_reads_by_status']['exact_address'])
                or any(sum(c[key].values()) != pairs for key in (
                    'candidate_pairs_by_seed', 'candidate_pairs_by_kind', 'candidate_pairs_by_guard_quality'))
                or c['candidate_pairs_by_guard_quality']['namespace_gap']
                or pair_outputs > min(eligible_limit, pairs)
                or bool(pair_outputs) != bool(pairs)
                or pair_outputs > target_outputs + seeds['condition_only']
                or target_outputs > eligible_limit
                or not target_outputs <= target_links <= 4 * target_outputs
                or not condition_seeded <= condition_links <= 4 * condition_seeded
                or c['candidate_target_categories']['module_input']
                    + c['candidate_target_categories']['module_output'] > target_outputs
                or c['candidate_condition_categories']['module_input']
                    + c['candidate_condition_categories']['module_output'] > condition_seeded
                or target_seeded > target_outputs * exact_reads
                or pairs > pair_outputs * exact_reads
                or (pairs or target_outputs) and (CANDIDATE_FIXED_BYTES + CANDIDATE_OUTPUT_BYTES * outputs
                    + CANDIDATE_TARGET_BYTES * target_outputs + CANDIDATE_PAIR_BYTES * pairs > MAX_CANDIDATE_BYTES)):
            _invalid()
        for category, count in c['candidate_target_categories'].items():
            limit = (c['authored_outputs_by_category'][category] if category in {'alarm', 'equipment', 'sensor'}
                else c['endpoint_kinds'][category] * eligible_limit)
            if count > min(target_outputs, limit):
                _invalid()
        for category, count in c['candidate_condition_categories'].items():
            limit = (c['authored_qualified_evidence_by_category'][category] * pairs
                if category in {'alarm', 'equipment', 'sensor'} else c['endpoint_kinds'][category] * pairs)
            if count > min(condition_seeded, limit):
                _invalid()
        for kind, count in c['candidate_pairs_by_kind'].items():
            if count > c['dependency_reads_by_kind'][kind]:
                _invalid()
        for quality, count in c['candidate_pairs_by_guard_quality'].items():
            if count > c['dependency_outputs_with_reads_by_guard_quality'][quality] * exact_reads:
                _invalid()
    byte_limit = (min(MAX_SIGNAL_CONTEXT_BYTES, MAX_SIGNAL_CONTEXT_JSON_BYTES) if version == 1
        else min(MAX_SIGNAL_CONTEXT_V2_BYTES, MAX_SIGNAL_CONTEXT_V2_JSON_BYTES) if version == 2
        else min(MAX_SIGNAL_CONTEXT_V3_BYTES, MAX_SIGNAL_CONTEXT_V3_JSON_BYTES) if version == 3
        else min(MAX_SIGNAL_CONTEXT_V4_BYTES, MAX_SIGNAL_CONTEXT_V4_JSON_BYTES) if version == 4
        else min(MAX_SIGNAL_CONTEXT_V5_BYTES, MAX_SIGNAL_CONTEXT_V5_JSON_BYTES))
    if (outputs != c['source_outputs'] or rungs != c['source_rungs']
            or reads != c['source_predicate_operands'] + c['source_ons_storage_operands']
            or c['reads_by_kind']['ons_storage'] != c['source_ons_storage_operands']
            or sum(c['reads_by_kind'][key] for key in ('xic', 'xio', 'comparison')) != c['source_predicate_operands']
            or max(c[key] for key in c if key.startswith('source_')) > MAX_SIGNAL_CONTEXT_RECORDS
            or records > MAX_SIGNAL_CONTEXT_RECORDS
            or records + minimum_links + c['stateful_associations_total'] > MAX_EVIDENCE_IDS
            or 64 * (records + minimum_links) > byte_limit
            or c['unparsed_rungs'] > rungs
            or outputs > c['source_instructions'] or reads > c['source_operands']
            or c['source_condition_nodes'] < rungs - c['unparsed_rungs'] + c['source_ons_storage_operands']
            or outputs + reads and rungs == c['unparsed_rungs']
            or addresses > c['source_addresses']
            or c['source_addresses'] > c['source_operands'] + c['source_expression_uses']
            or c['source_stateful_objects'] > c['source_operands']
            or accepted_operands + rejected_operands > c['source_operands']
            or c['accepted_expression_uses'] + c['rejected_expression_uses'] > c['source_expression_uses']
            or any(sum(c[key].values()) != count for key, count in (
                ('outputs_by_opcode', outputs), ('targets_by_status', outputs), ('guards_by_quality', outputs),
                ('reads_by_kind', reads), ('reads_by_status', reads), ('endpoint_kinds', addresses),
                ('address_profiles', addresses), ('rungs_by_qualification', rungs),
                ('stateful_associations_by_kind', c['stateful_associations_total']),
                ('stateful_associations_by_qualification', c['stateful_associations_total'])))
            or coil_addresses > exact_outputs or bool(coil_addresses) != bool(exact_outputs)
            or read_addresses > exact_reads or bool(read_addresses) != bool(exact_reads)
            or exact_reads > c['accepted_operands_by_role']['read'] + c['accepted_operands_by_role']['read_write']
            or c['noncoil_writers_total'] != c['accepted_operands_by_role']['write']
                + c['accepted_operands_by_role']['read_write'] - exact_outputs
            or c['addresses_with_multiple_coils'] > min(coil_addresses, exact_outputs - coil_addresses)
            or c['addresses_with_noncoil_writers'] > min(addresses, c['noncoil_writers_total'])
            or bool(c['addresses_with_noncoil_writers']) != bool(c['noncoil_writers_total'])
            or c['addresses_with_unknown_roles'] > min(addresses, c['accepted_operands_by_role']['unknown'])
            or bool(c['addresses_with_unknown_roles']) != bool(c['accepted_operands_by_role']['unknown'])
            or c['addresses_with_rejected_uses'] > min(addresses, rejected_operands + c['rejected_expression_uses'])
            or bool(c['addresses_with_rejected_uses']) != bool(rejected_operands + c['rejected_expression_uses'])
            or c['outputs_with_branches'] > outputs or c['outputs_with_stateful_conditions'] > outputs
            or c['guards_by_quality']['stateful'] > c['outputs_with_stateful_conditions']
            or c['stateful_associations_total'] > c['source_stateful_address_uses']
            or c['stateful_associations_total'] and not c['source_stateful_objects']
            or c['stateful_associations_total'] and not addresses):
        _invalid()
    for map_key, total_key in (('hints_by_category', 'rungs_with_hints'),
                              ('unqualified_hints_by_category', 'rungs_with_unqualified_hints')):
        total = sum(c[map_key].values())
        if (c[total_key] > min(rungs, total) or bool(c[total_key]) != bool(total)
                or total > len(COUNT_MAPS[map_key]) * c[total_key]
                or any(value > c[total_key] for value in c[map_key].values())):
            _invalid()
    if any(c['hints_by_category'][key] + c['unqualified_hints_by_category'][key] > rungs
           for key in COUNT_MAPS['hints_by_category']):
        _invalid()
    if summary['status'] != ('partial' if _partial(c) else 'complete'):
        _invalid()


def build_signal_context_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, tag_data: TagDataResult, output_context: BooleanOutputContextResult,
        stateful_objects: StatefulObjectResult, execution_context: ExecutionContextResult,
        result: SignalContextResult, revision: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        validate_signal_context(snapshot, inventory, references, access, calculations, rung_analysis,
            relationships, conditions, tag_data, output_context, stateful_objects, execution_context, result)
        summary = {**constants_for(result.schema_version), 'status': result.status, 'coverage': deepcopy(result.coverage),
            'tool_revision': dict(revision) if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        render_signal_context_summary(summary)
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_signal_context_summary(summary: dict[str, Any]) -> str:
    validate_signal_context_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if len(rendered.encode('utf-8')) > (MAX_REPORT_BYTES if summary['schema_version'] == 1 else
            MAX_REPORT_V2_BYTES if summary['schema_version'] == 2 else
            MAX_REPORT_V3_BYTES if summary['schema_version'] == 3 else
            MAX_REPORT_V4_BYTES if summary['schema_version'] == 4 else MAX_REPORT_V5_BYTES):
        _invalid()
    return rendered
