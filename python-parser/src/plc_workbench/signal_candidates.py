"""Explainable direct source associations selected by wording or I/O roots.

This rule combines existing qualified evidence, not inferred engineering roles.
An association retains the original condition occurrence and coil guard; it
does not claim that the condition causes a shutdown or identifies equipment.
"""
from __future__ import annotations

from typing import Any

CANDIDATE_RULE_ID = 'qualified-direct-signal-context-1'
CANDIDATE_CATEGORIES = frozenset({'alarm', 'equipment', 'sensor', 'module_input', 'module_output'})
MAX_CANDIDATE_AUTHORED_VISITS = 250_000
MAX_CANDIDATE_INDEX_LINKS = 100_000
MAX_CANDIDATE_DEPENDENCY_VISITS = 100_000
MAX_CANDIDATE_PAIRS = 50_000
MAX_CANDIDATE_BYTES = 8 * 1024 * 1024
CANDIDATE_FIXED_BYTES = 4096
CANDIDATE_OUTPUT_BYTES = 256
CANDIDATE_TARGET_BYTES = 128
CANDIDATE_PAIR_BYTES = 384
CANDIDATE_COUNT_MAPS = {
    'candidate_scans_by_status': frozenset({'complete', 'truncated'}),
    'candidate_target_categories': CANDIDATE_CATEGORIES,
    'candidate_condition_categories': CANDIDATE_CATEGORIES,
    'candidate_pairs_by_seed': frozenset({'condition_only', 'target_only', 'both'}),
    'candidate_pairs_by_kind': frozenset({'xic', 'xio', 'comparison', 'ons_storage'}),
    'candidate_pairs_by_guard_quality': frozenset({'modeled', 'binding_gaps', 'opaque', 'stateful', 'namespace_gap'}),
}
CANDIDATE_COVERAGE_KEYS = frozenset(CANDIDATE_COUNT_MAPS) | frozenset({
    'candidate_outputs_with_pairs', 'candidate_outputs_with_target_categories',
    'candidate_pairs_total', 'candidate_authored_link_visits',
    'candidate_dependency_visits', 'candidate_index_category_links',
})


def add_candidates(outputs: list[dict[str, Any]], reads: list[dict[str, Any]],
        addresses: list[dict[str, Any]], coverage: dict[str, Any]) -> None:
    """Apply the fixed rule to authenticated signal4 rows without source reads.

The authored index is keyed by address AND operand, preventing an alias used by
a reader from labeling a writer. Index truncation conservatively marks eligible
outputs incomplete. Per-output dependency and relevant address scan statuses
also propagate, even when the retained prefix has no matching category.
"""
    coverage.update({key: dict.fromkeys(sorted(values), 0)
        for key, values in CANDIDATE_COUNT_MAPS.items()})
    coverage.update(dict.fromkeys(sorted(CANDIDATE_COVERAGE_KEYS - CANDIDATE_COUNT_MAPS.keys()), 0))
    address_by_id = {row['id']: row for row in addresses}
    read_by_id = {row['id']: row for row in reads}
    authored: dict[tuple[str, str], set[str]] = {}
    index_truncated = False
    for address in addresses:
        for evidence in address['authored_evidence']:
            if evidence['qualification'] != 'qualified':
                continue
            for operand_id in evidence['operand_ids']:
                if coverage['candidate_authored_link_visits'] >= MAX_CANDIDATE_AUTHORED_VISITS:
                    index_truncated = True
                    break
                coverage['candidate_authored_link_visits'] += 1
                key = (address['id'], operand_id)
                additions = set(evidence['categories']) - authored.get(key, set())
                if coverage['candidate_index_category_links'] + len(additions) > MAX_CANDIDATE_INDEX_LINKS:
                    index_truncated = True
                    break
                authored.setdefault(key, set()).update(additions)
                coverage['candidate_index_category_links'] += len(additions)
            if index_truncated:
                break
        if index_truncated:
            break

    retained_bytes = CANDIDATE_FIXED_BYTES + CANDIDATE_OUTPUT_BYTES * len(outputs)
    retention_halted = retained_bytes > MAX_CANDIDATE_BYTES
    work_halted = False

    def categories(address: dict[str, Any], operand_id: str) -> list[str]:
        selected = set(authored.get((address['id'], operand_id), ()))
        if address['endpoint_kind'] in {'module_input', 'module_output'}:
            selected.add(address['endpoint_kind'])
        return sorted(selected)

    for output in outputs:
        dependency = output['guard_dependencies']
        context: dict[str, Any] = {'scan_status': dependency['traversal_status'],
            'target_categories': [], 'conditions': []}
        output['candidate_context'] = context
        eligible = (output['target_status'] == 'exact_address'
            and output['guard_quality'] != 'namespace_gap' and not output['has_namespace_gap'])
        if eligible:
            target = address_by_id[output['target_address_id']]
            if index_truncated or target['authored_scan_status'] == 'truncated' or retention_halted or work_halted:
                context['scan_status'] = 'truncated'
            target_categories = categories(target, output['target_operand_id'])
            if target_categories and not retention_halted:
                if retained_bytes + CANDIDATE_TARGET_BYTES > MAX_CANDIDATE_BYTES:
                    retention_halted = True
                    context['scan_status'] = 'truncated'
                else:
                    retained_bytes += CANDIDATE_TARGET_BYTES
                    context['target_categories'] = target_categories
                    coverage['candidate_outputs_with_target_categories'] += 1
                    for category in target_categories:
                        coverage['candidate_target_categories'][category] += 1
            for read_id in dependency['condition_read_ids']:
                if retention_halted or work_halted:
                    context['scan_status'] = 'truncated'
                    break
                if coverage['candidate_dependency_visits'] >= MAX_CANDIDATE_DEPENDENCY_VISITS:
                    work_halted = True
                    context['scan_status'] = 'truncated'
                    break
                coverage['candidate_dependency_visits'] += 1
                read = read_by_id[read_id]
                if read['status'] != 'exact_address':
                    continue
                address = address_by_id[read['source_address_id']]
                if address['authored_scan_status'] == 'truncated':
                    context['scan_status'] = 'truncated'
                read_categories = categories(address, read_id)
                if not read_categories and not context['target_categories']:
                    continue
                if (coverage['candidate_pairs_total'] >= MAX_CANDIDATE_PAIRS
                        or retained_bytes + CANDIDATE_PAIR_BYTES > MAX_CANDIDATE_BYTES):
                    retention_halted = True
                    context['scan_status'] = 'truncated'
                    break
                retained_bytes += CANDIDATE_PAIR_BYTES
                context['conditions'].append({'condition_read_id': read_id, 'categories': read_categories})
                coverage['candidate_pairs_total'] += 1
                seed = ('both' if read_categories and context['target_categories'] else
                    'condition_only' if read_categories else 'target_only')
                coverage['candidate_pairs_by_seed'][seed] += 1
                coverage['candidate_pairs_by_kind'][read['kind']] += 1
                coverage['candidate_pairs_by_guard_quality'][output['guard_quality']] += 1
                for category in read_categories:
                    coverage['candidate_condition_categories'][category] += 1
        coverage['candidate_outputs_with_pairs'] += int(bool(context['conditions']))
        coverage['candidate_scans_by_status'][context['scan_status']] += 1
