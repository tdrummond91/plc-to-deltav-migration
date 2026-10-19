"""Bounded direct guard-read membership, not a runtime dependency equation.

Each unique incoming condition DAG is scanned once. Occurrence IDs preserve
comparisons, stored-state reads, repeated contacts and alternative paths. The
reverse index links qualified exact reads to individual output occurrences;
it neither joins writers nor expands transitive address paths.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

MAX_GUARD_DEPENDENCY_NODES = 4096
MAX_GUARD_DEPENDENCY_EDGES = 16384
MAX_DEPENDENCY_VISITED_NODES = 1_000_000
MAX_DEPENDENCY_VISITED_EDGES = 2_000_000
MAX_DEPENDENCY_LINKS = 100_000
MAX_DEPENDENCY_CACHE_READS = 100_000
DEPENDENCY_COUNT_MAPS = {
    'dependency_traversals_by_status': frozenset({'complete', 'truncated'}),
    'dependency_reads_by_kind': frozenset({'xic', 'xio', 'comparison', 'ons_storage'}),
    'dependency_reads_by_status': frozenset({'exact_address', 'identity_gap', 'unbound',
        'literal', 'system_flag', 'namespace_gap'}),
    'dependency_outputs_with_reads_by_guard_quality': frozenset({'modeled', 'binding_gaps',
        'opaque', 'stateful', 'namespace_gap'}),
    'dependency_reverse_links_by_guard_quality': frozenset({'modeled', 'binding_gaps',
        'opaque', 'stateful', 'namespace_gap'}),
}
DEPENDENCY_COVERAGE_KEYS = frozenset(DEPENDENCY_COUNT_MAPS) | frozenset({
    'dependency_unique_guards_total', 'dependency_visited_nodes', 'dependency_visited_edges',
    'dependency_cached_read_ids', 'dependency_read_links_total', 'dependency_reverse_links_total',
    'dependency_outputs_with_reads', 'dependency_outputs_with_exact_reads',
    'dependency_outputs_with_dependents', 'dependency_addresses_with_dependents',
    'dependency_outputs_without_reads_complete',
})


def add_dependencies(outputs: list[dict[str, Any]], reads: list[dict[str, Any]],
        addresses: list[dict[str, Any]], condition_nodes: list[dict[str, Any]],
        coverage: dict[str, Any]) -> None:
    """Enrich freshly authenticated signal rows; callers own source validation.

Truncation of any output makes reverse-index absence inconclusive everywhere:
an unvisited condition could refer to any address. No second reverse scan may
silently turn the retained subset into a complete result.
"""
    coverage.update({key: dict.fromkeys(sorted(values), 0)
        for key, values in DEPENDENCY_COUNT_MAPS.items()})
    coverage.update(dict.fromkeys(sorted(DEPENDENCY_COVERAGE_KEYS - DEPENDENCY_COUNT_MAPS.keys()), 0))
    nodes = {row['id']: row for row in condition_nodes}
    reads_by_id = {row['id']: row for row in reads}
    reads_by_node: dict[str, list[str]] = defaultdict(list)
    for read in reads:
        reads_by_node[read['condition_node_id']].append(read['id'])
    addresses_by_id = {row['id']: row for row in addresses}
    for address in addresses:
        address['dependent_output_ids'] = []
    cache: dict[str, dict[str, Any]] = {}
    retained_links = 0

    def walk(guard_id: str) -> dict[str, Any]:
        if guard_id in cache:
            return cache[guard_id]
        result: dict[str, Any] = {'traversal_status': 'complete', 'visited_nodes': 0,
            'visited_edges': 0, 'condition_read_ids': []}
        queued, pending = {guard_id}, [guard_id]
        while pending:
            if (result['visited_nodes'] >= MAX_GUARD_DEPENDENCY_NODES
                    or coverage['dependency_visited_nodes'] >= MAX_DEPENDENCY_VISITED_NODES):
                result['traversal_status'] = 'truncated'
                break
            identifier = pending.pop()
            node = nodes[identifier]
            result['visited_nodes'] += 1
            coverage['dependency_visited_nodes'] += 1
            for read_id in reads_by_node.get(identifier, ()):
                if coverage['dependency_cached_read_ids'] >= MAX_DEPENDENCY_CACHE_READS:
                    result['traversal_status'] = 'truncated'
                    break
                result['condition_read_ids'].append(read_id)
                coverage['dependency_cached_read_ids'] += 1
            if result['traversal_status'] == 'truncated':
                break
            for child_id in node['child_ids']:
                if (result['visited_edges'] >= MAX_GUARD_DEPENDENCY_EDGES
                        or coverage['dependency_visited_edges'] >= MAX_DEPENDENCY_VISITED_EDGES):
                    result['traversal_status'] = 'truncated'
                    break
                result['visited_edges'] += 1
                coverage['dependency_visited_edges'] += 1
                if child_id not in queued:
                    if len(queued) >= MAX_GUARD_DEPENDENCY_NODES:
                        result['traversal_status'] = 'truncated'
                        break
                    queued.add(child_id)
                    pending.append(child_id)
            if result['traversal_status'] == 'truncated':
                break
        cache[guard_id] = result
        return result

    for output in outputs:
        observed = walk(output['guard_id'])
        dependency = {key: observed[key] for key in ('traversal_status', 'visited_nodes', 'visited_edges')}
        dependency['condition_read_ids'] = []
        reverse_addresses: set[str] = set()
        exact_reads = 0
        for read_id in observed['condition_read_ids']:
            read = reads_by_id[read_id]
            address_id = read['source_address_id']
            reverse = (read['status'] == 'exact_address'
                and output['guard_quality'] != 'namespace_gap'
                and not output['has_namespace_gap'] and address_id not in reverse_addresses)
            # A forward read and its first reverse address link are atomic.
            # Repeated contact occurrences stay distinct in the forward list,
            # while one output appears once per reverse address dossier.
            cost = 1 + int(reverse)
            if retained_links + cost > MAX_DEPENDENCY_LINKS:
                dependency['traversal_status'] = 'truncated'
                break
            retained_links += cost
            dependency['condition_read_ids'].append(read_id)
            coverage['dependency_reads_by_kind'][read['kind']] += 1
            coverage['dependency_reads_by_status'][read['status']] += 1
            exact_reads += int(read['status'] == 'exact_address')
            if reverse:
                addresses_by_id[address_id]['dependent_output_ids'].append(output['id'])
                reverse_addresses.add(address_id)
                coverage['dependency_reverse_links_by_guard_quality'][output['guard_quality']] += 1
        output['guard_dependencies'] = dependency
        retained_reads = len(dependency['condition_read_ids'])
        coverage['dependency_traversals_by_status'][dependency['traversal_status']] += 1
        coverage['dependency_read_links_total'] += retained_reads
        coverage['dependency_reverse_links_total'] += len(reverse_addresses)
        coverage['dependency_outputs_with_reads'] += int(bool(retained_reads))
        coverage['dependency_outputs_with_exact_reads'] += int(bool(exact_reads))
        coverage['dependency_outputs_with_dependents'] += int(bool(reverse_addresses))
        coverage['dependency_outputs_without_reads_complete'] += int(
            not retained_reads and dependency['traversal_status'] == 'complete')
        if retained_reads:
            coverage['dependency_outputs_with_reads_by_guard_quality'][output['guard_quality']] += 1
    coverage['dependency_unique_guards_total'] = len(cache)
    coverage['dependency_addresses_with_dependents'] = sum(
        bool(row['dependent_output_ids']) for row in addresses)
