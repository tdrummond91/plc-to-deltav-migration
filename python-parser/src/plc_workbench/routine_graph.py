"""Bounded static graph of declared program-local JSR routine candidates.

Edges retain parsed instruction provenance, not execution, scheduling, call
legality or parameter semantics. Missing and unmodeled bodies remain explicit
nodes rather than inferred terminal routines.
"""
from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from .models import InventoryResult

MAX_ROUTINE_GRAPH_NODES = 100_000
MAX_ROUTINE_GRAPH_EDGES = 100_000
MAX_ROUTINE_GRAPH_OCCURRENCES = 250_000
MAX_ROUTINE_GRAPH_EVIDENCE_CHARS = 8_000_000
MAX_ROUTINE_GRAPH_NAME_LENGTH = 65_536
ROUTINE_GRAPH_CONSTANTS = {
    'analysis_scope': 'declared_program_local_jsr_candidate_graph',
    'call_validation': 'not_analyzed',
    'execution': 'not_analyzed',
}
ROUTINE_GRAPH_LANGUAGES = frozenset({'RLL', 'FBD', 'SFC', 'ST', 'missing', 'other'})
ROUTINE_GRAPH_BODY_STATUSES = frozenset({
    'rll_structure_parsed', 'rll_structure_partial', 'language_unmodeled',
})
ROUTINE_GRAPH_MAIN_STATUSES = frozenset({
    'absent', 'empty', 'unsupported_name', 'missing_candidate',
    'ambiguous_candidate', 'unique_candidate',
})
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*', re.ASCII)
_PARTIAL_CODES = frozenset({
    'routine_content_missing', 'routine_content_mismatch', 'routine_content_not_analyzed',
})


class RoutineGraphError(ValueError):
    """Fatal rejection containing no source-controlled evidence."""


def _limit() -> None:
    raise RoutineGraphError('Routine graph analysis exceeds its evidence limits.')


def _cyclic_components(node_ids: list[str], edges: list[dict[str, Any]]) -> list[list[str]]:
    """Iterative Kosaraju traversal, including isolated nodes and self edges."""
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    incoming: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    self_nodes: set[str] = set()
    for edge in edges:
        caller, target = edge['caller_routine_id'], edge['target_routine_id']
        outgoing[caller].append(target)
        incoming[target].append(caller)
        if caller == target:
            self_nodes.add(caller)
    seen: set[str] = set()
    finished: list[str] = []
    for start in node_ids:
        if start in seen:
            continue
        seen.add(start)
        pending = [(start, iter(outgoing[start]))]
        while pending:
            current, neighbours = pending[-1]
            target = next(neighbours, None)
            if target is None:
                finished.append(current)
                pending.pop()
            elif target not in seen:
                seen.add(target)
                pending.append((target, iter(outgoing[target])))
    seen.clear()
    components: list[list[str]] = []
    for start in reversed(finished):
        if start in seen:
            continue
        seen.add(start)
        component: list[str] = []
        pending = [start]
        while pending:
            current = pending.pop()
            component.append(current)
            for target in incoming[current]:
                if target not in seen:
                    seen.add(target)
                    pending.append(target)
        if len(component) > 1 or start in self_nodes:
            components.append(sorted(component))
    return sorted(components)


def build_routine_graph(inventory: InventoryResult, routine_targets: dict[str, Any]) -> dict[str, Any]:
    """Group canonical candidate rows without reinterpreting their arguments.

    Program Type is not required for declaration lookup. MainRoutineName is
    kept raw, including absence versus empty, and never seeds runtime claims.
    """
    retained_characters = sum(map(len, ROUTINE_GRAPH_CONSTANTS.values()))

    def retain(value: Any) -> None:
        nonlocal retained_characters
        pending = [value]
        while pending:
            item = pending.pop()
            if type(item) is str:
                retained_characters += len(item)
                if retained_characters > MAX_ROUTINE_GRAPH_EVIDENCE_CHARS:
                    _limit()
            elif type(item) is dict:
                pending.extend(item.values())
            elif type(item) is list:
                pending.extend(item)

    if retained_characters > MAX_ROUTINE_GRAPH_EVIDENCE_CHARS:
        _limit()
    entities = {entity.id: entity for entity in inventory.entities}
    programs = [entity for entity in inventory.entities if entity.kind == 'program']
    partial_routines = {diagnostic.source_id for diagnostic in inventory.diagnostics
                        if diagnostic.code in _PARTIAL_CODES}
    rung_counts: dict[str, dict[str, int]] = defaultdict(lambda: {
        'parsed': 0, 'failed': 0, 'preserved_unsupported': 0,
    })
    for rung in inventory.rungs:
        counts = rung_counts[rung.parent_id]
        # Unknown dispositions also make a body partial; the canonical source
        # parser currently emits only these three retained rung dispositions.
        bucket = rung.parse_status if rung.parse_status in counts else 'preserved_unsupported'
        counts[bucket] += 1

    nodes: list[dict[str, Any]] = []
    node_programs: dict[str, str] = {}
    name_index: dict[tuple[str, str], list[str]] = defaultdict(list)
    for routine in inventory.entities:
        if routine.kind != 'routine':
            continue
        owner = entities.get(routine.parent_id)
        if owner is None or owner.kind != 'program' or routine.scope_id != owner.id:
            continue
        if len(nodes) >= MAX_ROUTINE_GRAPH_NODES:
            _limit()
        raw_language = routine.attributes.get('Type')
        language = (raw_language if raw_language in {'RLL', 'FBD', 'SFC', 'ST'}
                    else 'missing' if raw_language is None else 'other')
        counts = dict(rung_counts[routine.id])
        body_status = 'language_unmodeled'
        if language == 'RLL':
            partial = (routine.id in partial_routines or counts['failed']
                       or counts['preserved_unsupported'])
            body_status = 'rll_structure_partial' if partial else 'rll_structure_parsed'
        node = {'routine_id': routine.id, 'program_id': owner.id,
                'language': language, 'body_status': body_status, 'rung_counts': counts}
        retain(node)
        nodes.append(node)
        node_programs[routine.id] = owner.id
        if routine.name is not None and _NAME.fullmatch(routine.name):
            name_index[owner.id, routine.name.lower()].append(routine.id)

    main_designations: list[dict[str, Any]] = []
    for program in programs:
        raw = program.attributes.get('MainRoutineName')
        row: dict[str, Any] = {'program_id': program.id, 'raw_name': raw,
                               'status': 'absent', 'candidate_count': 0, 'target_routine_id': None}
        if raw is not None:
            if len(raw) > MAX_ROUTINE_GRAPH_NAME_LENGTH:
                _limit()
            if not raw:
                row['status'] = 'empty'
            elif not _NAME.fullmatch(raw):
                row['status'] = 'unsupported_name'
            else:
                candidates = name_index.get((program.id, raw.lower()), [])
                row['candidate_count'] = len(candidates)
                if not candidates:
                    row['status'] = 'missing_candidate'
                elif len(candidates) > 1:
                    row['status'] = 'ambiguous_candidate'
                else:
                    row['status'] = 'unique_candidate'
                    row['target_routine_id'] = candidates[0]
        retain(row)
        main_designations.append(row)

    edges_by_pair: dict[tuple[str, str, str], dict[str, Any]] = {}
    unlinked: list[str] = []
    occurrences = routine_targets['occurrences']
    if len(occurrences) > MAX_ROUTINE_GRAPH_OCCURRENCES:
        _limit()
    for occurrence in occurrences:
        instruction_id = occurrence['instruction_id']
        if occurrence['status'] != 'unique_candidate':
            retain(instruction_id)
            unlinked.append(instruction_id)
            continue
        program_id, caller, target = (occurrence['program_id'], occurrence['caller_routine_id'],
                                      occurrence['target_routine_id'])
        if (program_id is None or node_programs.get(caller) != program_id
                or node_programs.get(target) != program_id):
            raise RoutineGraphError('Routine graph candidates do not match the declared node contract.')
        pair = (program_id, caller, target)
        if pair not in edges_by_pair:
            if len(edges_by_pair) >= MAX_ROUTINE_GRAPH_EDGES:
                _limit()
            edge = {'program_id': program_id, 'caller_routine_id': caller,
                    'target_routine_id': target, 'instruction_ids': []}
            retain(edge)
            edges_by_pair[pair] = edge
        retain(instruction_id)
        edges_by_pair[pair]['instruction_ids'].append(instruction_id)
    edges = list(edges_by_pair.values())
    components = _cyclic_components(list(node_programs), edges)
    retain(components)
    return {**ROUTINE_GRAPH_CONSTANTS, 'nodes': nodes, 'edges': edges,
            'unlinked_instruction_ids': unlinked, 'main_designations': main_designations,
            'cyclic_components': components}
