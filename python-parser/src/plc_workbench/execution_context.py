"""Bounded source-declared scheduling and routine-control context.

These records describe declarations and lexical candidates. They do not select
edits, expand invocation paths, simulate scheduling, or infer parameter roles.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from io import StringIO
import json
import re
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .conditions import ConditionResult, validate_conditions
from .models import InventoryResult, SourceSnapshot
from .output_context import _provenance
from .references import ReferenceResult, _strict_record_match
from .relationships import RelationshipResult, _identifier
from .routine_targets import ROUTINE_TARGET_STATUSES
from .rung_analysis import RungAnalysisResult
from .sfc_context import _qualified_source
from .source import _read_nodes

MAX_EXECUTION_CONTEXT_RECORDS = 250_000
MAX_EXECUTION_CONTEXT_BYTES = 16 * 1024 * 1024
MAX_EXECUTION_CONTEXT_JSON_BYTES = 16 * 1024 * 1024
MAX_EVIDENCE_IDS = 1_000_000
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*', re.ASCII)
CONTROL_OPCODES = frozenset({'SBR', 'RET', 'JMP', 'LBL'})
NAME_STATUSES = frozenset({'absent', 'empty', 'unsupported_name', 'missing_candidate',
    'ambiguous_candidate', 'unique_candidate', 'namespace_gap', 'unsupported_context'})
CALL_STATUSES = ROUTINE_TARGET_STATUSES | {'namespace_gap'}
LABEL_STATUSES = NAME_STATUSES | {'not_applicable', 'invalid_field_count'}
GUARD_QUALITIES = frozenset({'modeled', 'binding_gaps', 'opaque', 'stateful', 'namespace_gap'})
QUALIFICATIONS = frozenset({'qualified', 'namespace_gap'})
BODY_STATUSES = frozenset({'rll_structure_parsed', 'rll_structure_partial',
    'language_unmodeled', 'unsupported_context'})
ARGUMENT_SHAPES = frozenset({'no_fields', 'empty_fields', 'nonempty_fields'})
ROW_GROUPS = ('tasks', 'programs', 'schedules', 'designations', 'calls',
              'control_occurrences', 'routine_contexts')
COUNT_MAPS = {
    'tasks_by_qualification': QUALIFICATIONS, 'programs_by_qualification': QUALIFICATIONS,
    'routines_by_qualification': QUALIFICATIONS, 'event_info_by_qualification': QUALIFICATIONS,
    'schedules_by_status': NAME_STATUSES, 'designations_by_status': NAME_STATUSES,
    'designations_by_kind': frozenset({'main', 'fault'}), 'calls_by_status': CALL_STATUSES,
    'controls_by_opcode': CONTROL_OPCODES, 'label_targets_by_status': LABEL_STATUSES,
    'guards_by_quality': GUARD_QUALITIES, 'arguments_by_shape': ARGUMENT_SHAPES,
    'routines_by_body_status': BODY_STATUSES,
    'source_control_opcodes': CONTROL_OPCODES | {'JSR'},
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | frozenset({
    'source_tasks', 'source_programs', 'source_schedules', 'source_routines',
    'source_rungs', 'source_instructions', 'source_condition_nodes', 'source_operands',
    'source_expression_uses', 'unparsed_rungs', 'tasks_total', 'programs_total',
    'schedules_total', 'designations_total', 'calls_total', 'control_occurrences_total',
    'routine_contexts_total', 'event_info_total', 'evidence_links',
    'schedule_candidate_links', 'designation_candidate_links', 'call_candidate_links',
    'label_candidate_links', 'other_edit_candidate_links', 'programs_with_schedules',
    'routines_with_incoming_calls', 'routines_with_outgoing_calls', 'routines_with_controls',
    'routines_with_designations', 'routines_in_lexical_cycles', 'programs_missing_type',
    'main_designation_gaps', 'guards_with_branches', 'guards_with_stateful_conditions',
    'guards_with_namespace_gaps', 'argument_fields', 'empty_argument_fields',
})
EXECUTION_CONTEXT_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'execution-context-1',
    'analysis_scope': 'source_declared_execution_context',
    'execution_analysis': 'not_implemented', 'scheduling_analysis': 'not_implemented',
    'parameter_roles': 'not_analyzed', 'parameter_types': 'not_analyzed',
    'call_validation': 'not_analyzed', 'edit_selection': 'not_implemented',
    'engineering_review': 'unreviewed', 'condition_usage': 'incoming_source_dag',
}


class ExecutionContextError(ValueError):
    """Fixed source-free evidence rejection."""


def _invalid() -> None:
    raise ExecutionContextError('Execution context evidence is inconsistent or exceeds its limits.') from None


@dataclass(frozen=True)
class ExecutionContextResult:
    snapshot: dict[str, str | int]
    status: str
    tasks: list[dict[str, Any]]
    programs: list[dict[str, Any]]
    schedules: list[dict[str, Any]]
    designations: list[dict[str, Any]]
    calls: list[dict[str, Any]]
    control_occurrences: list[dict[str, Any]]
    routine_contexts: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'execution-context-1'
    analysis_scope: str = 'source_declared_execution_context'
    execution_analysis: str = 'not_implemented'
    scheduling_analysis: str = 'not_implemented'
    parameter_roles: str = 'not_analyzed'
    parameter_types: str = 'not_analyzed'
    call_validation: str = 'not_analyzed'
    edit_selection: str = 'not_implemented'
    engineering_review: str = 'unreviewed'
    condition_usage: str = 'incoming_source_dag'

    def to_dict(self) -> dict[str, Any]:
        render_execution_context_json(self)
        return deepcopy(vars(self))


class _Budget:
    def __init__(self) -> None:
        self.records = self.bytes = self.ids = 0

    def retain(self, row: dict[str, Any]) -> None:
        self.records += 1
        self.bytes += len(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self.records > MAX_EXECUTION_CONTEXT_RECORDS or self.bytes > MAX_EXECUTION_CONTEXT_BYTES:
            _invalid()

    def check_links(self, amount: int) -> None:
        if self.ids + amount > MAX_EVIDENCE_IDS or self.bytes + 96 * amount > MAX_EXECUTION_CONTEXT_BYTES:
            _invalid()

    def links(self, rows: list[str]) -> list[str]:
        # Reserve before copying a potentially quadratic candidate association.
        self.check_links(len(rows))
        self.ids += len(rows)
        self.bytes += 96 * len(rows)
        return list(rows)


def _partial(c: dict[str, Any]) -> bool:
    return bool(c['unparsed_rungs'] or c['programs_missing_type'] or c['main_designation_gaps']
        or any(c[key]['namespace_gap'] for key in ('tasks_by_qualification',
            'programs_by_qualification', 'routines_by_qualification', 'event_info_by_qualification'))
        or c['schedules_total'] != c['schedules_by_status']['unique_candidate']
        or c['calls_total'] != c['calls_by_status']['unique_candidate']
        or sum(c['designations_by_status'].values()) != c['designations_by_status']['unique_candidate']
            + c['designations_by_status']['absent']
        or c['routine_contexts_total'] != c['routines_by_body_status']['rll_structure_parsed']
        or c['control_occurrences_total'] != c['label_targets_by_status']['unique_candidate']
            + c['label_targets_by_status']['not_applicable']
        or c['calls_total'] + c['control_occurrences_total'] != c['guards_by_quality']['modeled'])


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
            access: AccessResult, conditions: ConditionResult) -> ExecutionContextResult:
    if any(len(rows) > MAX_EXECUTION_CONTEXT_RECORDS for rows in (inventory.entities,
            inventory.rungs, access.instructions, access.operands, access.expression_uses, conditions.nodes)):
        _invalid()
    budget = _Budget()
    nodes = _read_nodes(snapshot.data)
    qualified, strict_entity_ok, strict_binding_ok = _qualified_source(snapshot, inventory)
    xml = {node.locator: node for node in nodes}
    entities = {entity.id: entity for entity in inventory.entities}
    populations = {kind: [row for row in inventory.entities if row.kind == kind]
                   for kind in ('task', 'program', 'program_schedule', 'routine')}
    entity_ok = {row.id: strict_entity_ok(row.id) for row in inventory.entities}
    rung_ok, binding_ok, _ = _provenance(snapshot, inventory)
    for rung in inventory.rungs:
        rung_ok[rung.id] = rung_ok[rung.id] and qualified[rung.locator] and all(
            qualified[nodes[index].locator] for index in xml[rung.locator].children
            if nodes[index].name == 'Text')
    operands = {row['id']: row for row in access.operands}
    expression_uses: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for use in access.expression_uses:
        expression_uses[use['instruction_id']].append(use)
    condition_by_id = {row['id']: row for row in conditions.nodes}
    transfer_by_instruction = {row['instruction_id']: row for row in conditions.nodes
                               if row['kind'] == 'opaque_transfer'}
    context_ok: dict[str, bool] = {}
    for node in conditions.nodes:
        context_ok[node['id']] = (rung_ok[node['rung_id']]
            and all(context_ok[child] for child in node['child_ids'])
            and all(operands[identifier]['binding_status'] != 'root_bound'
                    or binding_ok(operands[identifier]) and strict_binding_ok(operands[identifier])
                    for identifier in node['operand_ids'])
            and all(use['binding_status'] != 'root_bound' or binding_ok(use) and strict_binding_ok(use)
                    for use in expression_uses.get(node['instruction_id'], [])))
    c = {key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()}
    c.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
    c.update(source_tasks=len(populations['task']), source_programs=len(populations['program']),
        source_schedules=len(populations['program_schedule']), source_routines=len(populations['routine']),
        source_rungs=len(inventory.rungs), source_instructions=len(access.instructions),
        source_condition_nodes=len(conditions.nodes), source_operands=len(access.operands),
        source_expression_uses=len(access.expression_uses),
        unparsed_rungs=sum(rung.parse_status != 'parsed' for rung in inventory.rungs))
    groups: dict[str, list[dict[str, Any]]] = {key: [] for key in ROW_GROUPS}
    program_index: dict[tuple[str, str], list[str]] = defaultdict(list)
    routine_index: dict[tuple[str, str], list[str]] = defaultdict(list)
    for kind, index, owner_kind in (('program', program_index, 'controller'),
                                   ('routine', routine_index, 'program')):
        for entity in populations[kind]:
            owner = entities.get(entity.parent_id)
            if (owner is not None and owner.kind == owner_kind and entity.scope_id == owner.id
                    and entity.name is not None and _NAME.fullmatch(entity.name)):
                index[owner.id, entity.name.lower()].append(entity.id)

    def retain(group: str, row: dict[str, Any]) -> None:
        budget.retain(row)
        groups[group].append(row)

    def resolve(raw: str | None, owner: str | None, index: dict[tuple[str, str], list[str]],
                okay: bool) -> tuple[str, str, list[str], str | None]:
        candidates: list[str] = []
        lexical = ('absent' if raw is None else 'empty' if raw == '' else
                   'unsupported_name' if not _NAME.fullmatch(raw) else
                   'unsupported_context' if owner is None else 'missing_candidate')
        if lexical == 'missing_candidate':
            candidates = budget.links(index.get((owner, raw.lower()), []))
            lexical = ('unique_candidate' if len(candidates) == 1 else
                       'ambiguous_candidate' if candidates else 'missing_candidate')
        status = lexical if okay and all(entity_ok[item] for item in candidates) else 'namespace_gap'
        return lexical, status, candidates, candidates[0] if status == 'unique_candidate' else None

    schedules_by_task: dict[str, list[str]] = defaultdict(list)
    schedules_by_program: dict[str, list[str]] = defaultdict(list)
    designations_by_program: dict[str, list[str]] = defaultdict(list)
    designations_by_routine: dict[str, list[str]] = defaultdict(list)
    for entity in populations['program_schedule']:
        task = entities.get(entity.parent_id)
        controller = entities.get(task.parent_id) if task is not None else None
        owner = controller.id if (task is not None and task.kind == 'task'
            and controller is not None and controller.kind == 'controller'
            and entity.scope_id == controller.id and task.scope_id == controller.id) else None
        lexical, status, candidates, target = resolve(entity.name, owner, program_index, entity_ok[entity.id])
        node = xml[entity.locator]
        identifier = _identifier('execution_schedule_', entity.id)
        row = {'id': identifier, 'schedule_id': entity.id, 'task_id': entity.parent_id,
            'controller_id': owner, 'source_locator': entity.locator,
            'container_locator': nodes[node.parent].locator if node.parent is not None else None,
            'ordinal': node.ordinal, 'raw_name': entity.name, 'raw_attributes': dict(node.expanded_attributes),
            'qualified': entity_ok[entity.id], 'lexical_status': lexical, 'status': status,
            'candidate_program_ids': candidates, 'target_program_id': target}
        retain('schedules', row)
        schedules_by_task[entity.parent_id].append(identifier)
        if target is not None:
            schedules_by_program[target].append(identifier)
        c['schedules_by_status'][status] += 1
        c['schedule_candidate_links'] += len(candidates)
    for entity in populations['program']:
        for kind, attribute in (('main', 'MainRoutineName'), ('fault', 'FaultRoutineName')):
            raw = entity.attributes.get(attribute)
            lexical, status, candidates, target = resolve(raw, entity.id, routine_index, entity_ok[entity.id])
            identifier = _identifier('execution_designation_', entity.id, kind)
            row = {'id': identifier, 'program_id': entity.id, 'kind': kind, 'attribute': attribute,
                'raw_name': raw, 'qualified': entity_ok[entity.id], 'lexical_status': lexical,
                'status': status, 'candidate_routine_ids': candidates, 'target_routine_id': target}
            retain('designations', row)
            designations_by_program[entity.id].append(identifier)
            if target is not None:
                designations_by_routine[target].append(identifier)
            c['designations_by_status'][status] += 1
            c['designations_by_kind'][kind] += 1
            c['designation_candidate_links'] += len(candidates)
            c['main_designation_gaps'] += int(kind == 'main' and status != 'unique_candidate')
    for entity in populations['task']:
        events = []
        for index in xml[entity.locator].children:
            node = nodes[index]
            if node.name != 'EventInfo':
                continue
            event = {'id': _identifier('execution_event_', snapshot.id, node.locator),
                'source_locator': node.locator, 'ordinal': node.ordinal,
                'raw_attributes': dict(node.expanded_attributes), 'qualified': qualified[node.locator]}
            budget.retain(event)
            events.append(event)
            c['event_info_by_qualification']['qualified' if event['qualified'] else 'namespace_gap'] += 1
        c['event_info_total'] += len(events)
        retain('tasks', {'id': _identifier('execution_task_', entity.id), 'task_id': entity.id,
            'controller_id': entity.parent_id, 'source_locator': entity.locator,
            'raw_attributes': dict(xml[entity.locator].expanded_attributes), 'qualified': entity_ok[entity.id],
            'schedule_ids': budget.links(schedules_by_task[entity.id]), 'event_info': events})
        c['tasks_by_qualification']['qualified' if entity_ok[entity.id] else 'namespace_gap'] += 1
    for entity in populations['program']:
        retain('programs', {'id': _identifier('execution_program_', entity.id), 'program_id': entity.id,
            'controller_id': entity.parent_id, 'source_locator': entity.locator,
            'raw_attributes': dict(xml[entity.locator].expanded_attributes), 'qualified': entity_ok[entity.id],
            'schedule_ids': budget.links(schedules_by_program[entity.id]),
            'designation_ids': budget.links(designations_by_program[entity.id])})
        c['programs_by_qualification']['qualified' if entity_ok[entity.id] else 'namespace_gap'] += 1
        c['programs_with_schedules'] += int(bool(schedules_by_program[entity.id]))
        c['programs_missing_type'] += int('Type' not in entity.attributes)

    incoming: dict[str, list[str]] = defaultdict(list)
    outgoing: dict[str, list[str]] = defaultdict(list)
    controls: dict[str, list[str]] = defaultdict(list)
    calls = {row['instruction_id']: row for row in references.routine_targets['occurrences']}
    label_index: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    routine_labels: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    occurrences = []
    for rung in inventory.rungs:
        node = xml[rung.locator]
        content = nodes[node.parent].locator if node.parent is not None else None
        for instruction in rung.instructions:
            opcode = instruction.opcode.upper() if instruction.opcode.isascii() else ''
            if opcode not in CONTROL_OPCODES | {'JSR'}:
                continue
            occurrences.append((rung, instruction, opcode, content))
            c['source_control_opcodes'][opcode] += 1
            if opcode == 'LBL' and len(instruction.arguments) == 1 and _NAME.fullmatch(instruction.arguments[0].strip()):
                key = instruction.arguments[0].strip().lower()
                label_index[rung.parent_id, content, key].append(instruction.id)
                routine_labels[rung.parent_id, key].append((content, instruction.id))
    occurrence_qualified = {instruction.id: rung_ok[rung.id] for rung, instruction, _, _ in occurrences}

    def guard(instruction_id: str) -> dict[str, Any]:
        transfer = transfer_by_instruction[instruction_id]
        node = condition_by_id[transfer['child_ids'][0]]
        status = 'opaque' if node['has_opaque'] else 'binding_gaps' if node['has_binding_gap'] else 'modeled'
        namespace_gap = not context_ok[node['id']]
        quality = ('namespace_gap' if namespace_gap else status if status != 'modeled'
                   else 'stateful' if node['has_stateful'] else 'modeled')
        c['guards_by_quality'][quality] += 1
        c['guards_with_branches'] += int(node['has_branch'])
        c['guards_with_stateful_conditions'] += int(node['has_stateful'])
        c['guards_with_namespace_gaps'] += int(namespace_gap)
        return {'guard_id': node['id'], 'guard_status': status, 'guard_quality': quality,
                'has_namespace_gap': namespace_gap, 'has_stateful': node['has_stateful'],
                'has_branch': node['has_branch']}

    for rung, instruction, opcode, content in occurrences:
        routine = entities.get(rung.parent_id)
        owner = entities.get(routine.parent_id) if routine is not None else None
        program = owner.id if owner is not None and owner.kind == 'program' else None
        raw = list(instruction.arguments)
        empty = [index for index, value in enumerate(raw) if not value.strip()]
        shape = 'no_fields' if not raw else 'empty_fields' if empty else 'nonempty_fields'
        c['arguments_by_shape'][shape] += 1
        c['argument_fields'] += len(raw)
        c['empty_argument_fields'] += len(empty)
        common = {'instruction_id': instruction.id, 'rung_id': rung.id,
            'caller_routine_id': rung.parent_id, 'program_id': program, 'opcode': opcode,
            'source_locator': rung.locator, 'content_locator': content, 'rung_ordinal': rung.ordinal,
            'source_start': instruction.start, 'source_end': instruction.end,
            'qualified': rung_ok[rung.id], 'raw_arguments': raw, 'argument_count': len(raw),
            'argument_shape': shape, 'empty_argument_indices': empty, **guard(instruction.id)}
        if opcode == 'JSR':
            source = calls[instruction.id]
            target_raw = source['raw_target_name']
            candidates = budget.links(routine_index.get((source['program_id'], target_raw.strip().lower()), [])
                if target_raw is not None and _NAME.fullmatch(target_raw.strip()) and source['program_id'] else [])
            status = source['status']
            if not rung_ok[rung.id] or any(not entity_ok[item] for item in candidates):
                status = 'namespace_gap'
            target = source['target_routine_id'] if status == 'unique_candidate' else None
            identifier = _identifier('execution_call_', instruction.id)
            retain('calls', {'id': identifier, **common, 'raw_target_name': target_raw,
                'lexical_status': source['status'], 'status': status,
                'candidate_routine_ids': candidates, 'target_routine_id': target,
                'lexical_target_context': source['target_context']})
            outgoing[rung.parent_id].append(identifier)
            if target is not None:
                incoming[target].append(identifier)
            c['calls_by_status'][status] += 1
            c['call_candidate_links'] += len(candidates)
        else:
            target_raw = raw[0] if raw else None
            lexical, candidates, other_edit = 'not_applicable', [], []
            if opcode in {'JMP', 'LBL'}:
                lexical = ('absent' if not raw else 'invalid_field_count' if len(raw) != 1
                    else 'empty' if not target_raw.strip() else 'unsupported_name'
                    if not _NAME.fullmatch(target_raw.strip()) else 'missing_candidate')
                if lexical == 'missing_candidate':
                    key = target_raw.strip().lower()
                    candidates = budget.links(label_index.get((rung.parent_id, content, key), []))
                    # Check the full possible association count before filtering.
                    peers = routine_labels.get((rung.parent_id, key), [])
                    budget.check_links(len(peers))
                    other_edit = budget.links([identifier for locator, identifier in peers if locator != content])
                    lexical = ('unique_candidate' if len(candidates) == 1 else
                        'ambiguous_candidate' if candidates else 'missing_candidate')
            status = lexical
            if opcode in {'JMP', 'LBL'} and (not rung_ok[rung.id]
                    or any(not occurrence_qualified[item] for item in candidates)):
                status = 'namespace_gap'
            identifier = _identifier('execution_control_', instruction.id)
            retain('control_occurrences', {'id': identifier, **common, 'raw_label_name': target_raw
                if opcode in {'JMP', 'LBL'} else None, 'lexical_status': lexical, 'status': status,
                'candidate_label_instruction_ids': candidates, 'other_edit_candidate_ids': other_edit,
                'target_label_instruction_id': candidates[0] if status == 'unique_candidate' else None})
            controls[rung.parent_id].append(identifier)
            c['controls_by_opcode'][opcode] += 1
            c['label_targets_by_status'][status] += 1
            c['label_candidate_links'] += len(candidates)
            c['other_edit_candidate_links'] += len(other_edit)

    graph = {row['routine_id']: row for row in references.routine_graph['nodes']}
    cyclic = {identifier for component in references.routine_graph['cyclic_components'] for identifier in component}
    for entity in populations['routine']:
        source = graph.get(entity.id)
        status = source['body_status'] if source is not None else 'unsupported_context'
        retain('routine_contexts', {'id': _identifier('execution_routine_', entity.id),
            'routine_id': entity.id, 'owner_id': entity.parent_id,
            'program_id': source['program_id'] if source is not None else None,
            'source_locator': entity.locator, 'raw_attributes': dict(xml[entity.locator].expanded_attributes),
            'qualified': entity_ok[entity.id], 'body_status': status,
            'rung_counts': dict(source['rung_counts']) if source is not None else None,
            'incoming_call_ids': budget.links(incoming[entity.id]),
            'outgoing_call_ids': budget.links(outgoing[entity.id]),
            'designation_ids': budget.links(designations_by_routine[entity.id]),
            'control_occurrence_ids': budget.links(controls[entity.id]),
            'in_lexical_call_cycle': entity.id in cyclic})
        c['routines_by_qualification']['qualified' if entity_ok[entity.id] else 'namespace_gap'] += 1
        c['routines_by_body_status'][status] += 1
        c['routines_in_lexical_cycles'] += int(entity.id in cyclic)
        for key, index in (('incoming_calls', incoming), ('outgoing_calls', outgoing),
                           ('controls', controls), ('designations', designations_by_routine)):
            c[f'routines_with_{key}'] += int(bool(index[entity.id]))
    c.update({f'{key}_total': len(rows) for key, rows in groups.items()})
    c['evidence_links'] = budget.ids
    return ExecutionContextResult(deepcopy(inventory.snapshot), 'partial' if _partial(c) else 'complete',
                                  **groups, coverage=c)


def analyze_execution_context(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult) -> ExecutionContextResult:
    """Authenticate exact conditions3 and every prior input before deriving."""
    try:
        if type(conditions) is not ConditionResult or type(conditions.schema_version) is not int or conditions.schema_version != 3:
            _invalid()
        validate_conditions(snapshot, inventory, references, access, calculations, rung_analysis, relationships, conditions)
        result = _derive(snapshot, inventory, references, access, conditions)
        render_execution_context_json(result)
        return result
    except ExecutionContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_execution_context(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, result: ExecutionContextResult) -> None:
    try:
        render_execution_context_json(result)
        expected = analyze_execution_context(snapshot, inventory, references, access, calculations,
                                             rung_analysis, relationships, conditions)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except ExecutionContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_execution_context_json(result: ExecutionContextResult) -> str:
    """Bound native containers and encoding; replay authenticates source meaning."""
    try:
        if type(result) is not ExecutionContextResult or vars(result).keys() != set(ExecutionContextResult.__dataclass_fields__):
            _invalid()
        remaining, identifiers = MAX_EXECUTION_CONTEXT_BYTES, 0
        frames = [(iter((vars(result),)), None)]
        active: set[int] = set()
        while frames:
            try:
                value = next(frames[-1][0])
            except StopIteration:
                _, identifier = frames.pop()
                if identifier is not None:
                    active.remove(identifier)
                continue
            remaining -= 1
            if len(frames) > 12:
                _invalid()
            if type(value) in (dict, list):
                identifier = id(value)
                if identifier in active or len(value) > MAX_EXECUTION_CONTEXT_RECORDS:
                    _invalid()
                active.add(identifier)
                if type(value) is dict:
                    if any(type(key) is not str for key in value):
                        _invalid()
                    remaining -= sum(len(key.encode('utf-8')) for key in value)
                    frames.append((iter(value.values()), identifier))
                else:
                    identifiers += len(value)
                    frames.append((iter(value), identifier))
            elif type(value) is str:
                remaining -= len(value.encode('utf-8'))
            elif type(value) not in (int, bool, type(None)):
                _invalid()
            if remaining < 0 or identifiers > MAX_EVIDENCE_IDS:
                _invalid()
        if (sum(len(getattr(result, key)) for key in ROW_GROUPS)
                + sum(len(task['event_info']) for task in result.tasks) > MAX_EXECUTION_CONTEXT_RECORDS):
            _invalid()
        output, size = StringIO(), 1
        for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).iterencode(vars(result)):
            size += len(chunk.encode('utf-8'))
            if size > MAX_EXECUTION_CONTEXT_JSON_BYTES:
                _invalid()
            output.write(chunk)
        return output.getvalue() + '\n'
    except ExecutionContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
