"""Bounded captured contact and coil patterns, without behavior inference.

The cache contains one contact index per guard, never descendant sets for every
DAG node. Work and retained links have separate budgets. A partial observation
always retains an explicit truncated marker; absence is then inconclusive.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

MAX_GUARD_PATTERN_NODES = 4096
MAX_GUARD_PATTERN_EDGES = 16384
MAX_PATTERN_VISITED_NODES = 1_000_000
MAX_PATTERN_VISITED_EDGES = 2_000_000
MAX_PATTERN_LINKS = 100_000
MAX_PATTERN_CACHE_CONTACTS = 100_000
PATTERN_COUNT_MAPS = {
    'pattern_traversals_by_status': frozenset({'complete', 'truncated'}),
    'pattern_self_contacts_by_kind': frozenset({'xic', 'xio'}),
    'pattern_timer_contacts_by_member': frozenset({'EN', 'TT', 'DN'}),
    'pattern_grouped_outputs_by_opcode': frozenset({'OTE', 'OTL', 'OTU'}),
}
PATTERN_COVERAGE_KEYS = frozenset(PATTERN_COUNT_MAPS) | frozenset({
    'pattern_unique_guards_total', 'pattern_visited_nodes', 'pattern_visited_edges',
    'pattern_outputs_with_self_contacts', 'pattern_outputs_with_timer_contacts',
    'pattern_coil_contexts_total', 'pattern_set_reset_contexts',
    'pattern_addresses_with_set_reset',
})


def add_patterns(outputs: list[dict[str, Any]], reads: list[dict[str, Any]],
        addresses: list[dict[str, Any]], condition_nodes: list[dict[str, Any]],
        stateful_objects: list[dict[str, Any]], coverage: dict[str, Any]) -> None:
    """Enrich freshly derived v1 rows in place; caller owns canonical inputs."""
    coverage.update({key: dict.fromkeys(sorted(values), 0) for key, values in PATTERN_COUNT_MAPS.items()})
    coverage.update(dict.fromkeys(sorted(PATTERN_COVERAGE_KEYS - PATTERN_COUNT_MAPS.keys()), 0))
    nodes = {row['id']: row for row in condition_nodes}
    objects = {row['id']: row for row in stateful_objects}
    timer_by_address: dict[str, list[dict[str, str]]] = defaultdict(list)
    # Inspect each existing association once, independently of reader and
    # output multiplicity. No reader-by-control Cartesian scan is needed.
    for address in addresses:
        for association in address['stateful_associations']:
            control = objects[association['object_id']]
            member = (association['member'] or '').upper()
            if (association['kind'] == 'direct_member' and association['member_status'] == 'known'
                    and association['qualification'] == 'qualified' and member in {'EN', 'TT', 'DN'}
                    and control['family'] == 'timer' and control['declaration_kind'] == 'timer'
                    and not control['type_conflict']
                    and control['bounds_status'] in {'scalar', 'static_in_bounds'}):
                timer_by_address[address['id']].append({'object_id': control['id'], 'member': member})
    reads_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for read in reads:
        if read['kind'] in {'xic', 'xio'} and read['status'] == 'exact_address':
            reads_by_node[read['condition_node_id']].append(read)
    cache: dict[str, dict[str, Any]] = {}
    cached_contacts = retained_links = 0

    def walk(guard_id: str) -> dict[str, Any]:
        nonlocal cached_contacts
        if guard_id in cache:
            return cache[guard_id]
        result: dict[str, Any] = {'traversal_status': 'complete', 'visited_nodes': 0,
            'visited_edges': 0, 'by_address': defaultdict(lambda: {'xic': [], 'xio': []}),
            'timer_contacts': []}
        queued = {guard_id}
        pending = [guard_id]
        while pending:
            if (result['visited_nodes'] >= MAX_GUARD_PATTERN_NODES
                    or coverage['pattern_visited_nodes'] >= MAX_PATTERN_VISITED_NODES):
                result['traversal_status'] = 'truncated'
                break
            identifier = pending.pop()
            node = nodes[identifier]
            result['visited_nodes'] += 1
            coverage['pattern_visited_nodes'] += 1
            for read in reads_by_node.get(identifier, ()):
                if cached_contacts >= MAX_PATTERN_CACHE_CONTACTS:
                    result['traversal_status'] = 'truncated'
                    break
                cached_contacts += 1
                result['by_address'][read['source_address_id']][read['kind']].append(read['id'])
                for timer in timer_by_address.get(read['source_address_id'], ()):
                    if cached_contacts >= MAX_PATTERN_CACHE_CONTACTS:
                        result['traversal_status'] = 'truncated'
                        break
                    cached_contacts += 1
                    result['timer_contacts'].append({'condition_read_id': read['id'], **timer})
            if result['traversal_status'] == 'truncated':
                break
            for child in node['child_ids']:
                if (result['visited_edges'] >= MAX_GUARD_PATTERN_EDGES
                        or coverage['pattern_visited_edges'] >= MAX_PATTERN_VISITED_EDGES):
                    result['traversal_status'] = 'truncated'
                    break
                result['visited_edges'] += 1
                coverage['pattern_visited_edges'] += 1
                if child not in queued:
                    # Bound queued nodes too; a wide join must not allocate an
                    # unbounded frontier before the visited-node check runs.
                    if len(queued) >= MAX_GUARD_PATTERN_NODES:
                        result['traversal_status'] = 'truncated'
                        break
                    queued.add(child)
                    pending.append(child)
            if result['traversal_status'] == 'truncated':
                break
        cache[guard_id] = result
        return result

    groups: dict[str, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    for output in outputs:
        observed = walk(output['guard_id'])
        pattern = {key: observed[key] for key in ('traversal_status', 'visited_nodes', 'visited_edges')}
        matching = observed['by_address'].get(output['target_address_id'], {})
        for key, values in (
                ('self_xic_read_ids', matching.get('xic', ())),
                ('self_xio_read_ids', matching.get('xio', ())),
                ('timer_contacts', observed['timer_contacts'])):
            available = max(0, MAX_PATTERN_LINKS - retained_links)
            selected = values[:available]
            pattern[key] = [dict(item) if isinstance(item, dict) else item for item in selected]
            retained_links += len(selected)
            if len(selected) != len(values):
                pattern['traversal_status'] = 'truncated'
        output['guard_patterns'] = pattern
        coverage['pattern_traversals_by_status'][pattern['traversal_status']] += 1
        coverage['pattern_self_contacts_by_kind']['xic'] += len(pattern['self_xic_read_ids'])
        coverage['pattern_self_contacts_by_kind']['xio'] += len(pattern['self_xio_read_ids'])
        coverage['pattern_outputs_with_self_contacts'] += int(bool(pattern['self_xic_read_ids'] or pattern['self_xio_read_ids']))
        coverage['pattern_outputs_with_timer_contacts'] += int(bool(pattern['timer_contacts']))
        for contact in pattern['timer_contacts']:
            coverage['pattern_timer_contacts_by_member'][contact['member']] += 1
        if output['target_address_id'] is not None:
            key = (output['routine_id'], output['content_locator'])
            scoped = groups[output['target_address_id']]
            if key not in scoped:
                scoped[key] = {'routine_id': key[0], 'content_locator': key[1],
                    'ote_output_ids': [], 'otl_output_ids': [], 'otu_output_ids': [], 'has_set_reset': False}
            scoped[key][f"{output['opcode'].lower()}_output_ids"].append(output['id'])
            coverage['pattern_grouped_outputs_by_opcode'][output['opcode']] += 1
    coverage['pattern_unique_guards_total'] = len(cache)
    for address in addresses:
        address['coil_contexts'] = list(groups[address['id']].values())
        for group in address['coil_contexts']:
            group['has_set_reset'] = bool(group['otl_output_ids'] and group['otu_output_ids'])
            coverage['pattern_set_reset_contexts'] += int(group['has_set_reset'])
        coverage['pattern_coil_contexts_total'] += len(address['coil_contexts'])
        coverage['pattern_addresses_with_set_reset'] += int(any(row['has_set_reset'] for row in address['coil_contexts']))
