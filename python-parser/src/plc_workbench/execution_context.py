"""Bounded source-declared scheduling and routine-control context.

These records describe declarations and lexical candidates. They do not select
edits, expand invocation paths, simulate scheduling, or infer parameter roles.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from io import StringIO
import json
import re
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .conditions import ConditionResult, validate_conditions
from .models import InventoryResult, SourceSnapshot
from .output_context import _provenance
from .references import ReferenceResult, _Resolver, _binding, _literal, _strict_record_match
from .relationships import RelationshipResult, _identifier
from .routine_targets import ROUTINE_TARGET_STATUSES
from .rung_analysis import RungAnalysisResult
from .sfc_context import _qualified_source
from .sfc_structure import analyze_sfc_structure
from .source import _read_nodes
from .custom_instruction_context import _PROTECTION_MARKERS
from .routine_shapes import JSR_ARITY_BINS

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
EXECUTION_CONTEXT_CONSTANTS_V2 = {**EXECUTION_CONTEXT_CONSTANTS,
    'schema_version': 2, 'analyzer_version': 'execution-context-2',
    'analysis_scope': 'source_declared_execution_and_routine_boundaries'}
BOUNDARY_CONTENT_STATUSES = frozenset({'qualified_rll', 'namespace_gap', 'protected',
    'incomplete_rll', 'unsupported_context'})
CALL_BOUNDARY_STATUSES = frozenset({'associated', 'target_unavailable', 'unsupported_language',
    'missing_content', 'multiple_contents', 'namespace_gap', 'protected',
    'incomplete_content', 'unsupported_context'})
BOUNDARY_PROFILES = frozenset({'none', 'sbr_only', 'ret_only', 'sbr_and_ret', 'not_available'})
ARGUMENT_CONTEXT_STATUSES = frozenset({'routine_target', 'empty', 'literal', 'root_bound_candidate',
    'unresolved', 'ambiguous', 'alias_cycle', 'alias_depth_limit', 'unsupported_address',
    'namespace_gap', 'protected', 'unsupported_context'})
SECOND_FIELD_KINDS = frozenset({'absent', 'empty', 'exact_zero', 'other_ascii_decimal', 'other'})
ROW_GROUPS_V2 = ROW_GROUPS + ('boundary_contents', 'call_boundaries', 'argument_contexts')
COUNT_MAPS_V2 = {**COUNT_MAPS,
    'boundary_contents_by_status': BOUNDARY_CONTENT_STATUSES,
    'calls_by_boundary_status': CALL_BOUNDARY_STATUSES,
    'calls_by_boundary_profile': BOUNDARY_PROFILES,
    'argument_contexts_by_status': ARGUMENT_CONTEXT_STATUSES,
    'argument_contexts_by_opcode': frozenset({'JSR', 'SBR', 'RET'}),
    'calls_by_field_shape': frozenset(JSR_ARITY_BINS),
    'calls_by_second_field_kind': SECOND_FIELD_KINDS,
    'sbr_target_calls_by_shape': frozenset(JSR_ARITY_BINS),
    'ret_target_calls_by_shape': frozenset(JSR_ARITY_BINS)}
COVERAGE_KEYS_V2 = COVERAGE_KEYS | frozenset(COUNT_MAPS_V2) | {
    'boundary_contents_total', 'call_boundaries_total', 'argument_contexts_total',
    'boundary_rungs_total', 'boundary_parsed_rungs', 'boundary_sbr_occurrences',
    'boundary_ret_occurrences', 'unprofiled_boundary_occurrences', 'calls_with_target_content',
    'distinct_associated_contents', 'argument_candidate_symbols', 'argument_alias_links',
    'boundary_evidence_links'}
_V2_FIELDS = frozenset(ROW_GROUPS_V2) - frozenset(ROW_GROUPS)
EXECUTION_CONTEXT_CONSTANTS_V3 = {**EXECUTION_CONTEXT_CONSTANTS_V2,
    'schema_version': 3, 'analyzer_version': 'execution-context-3'}
ROW_GROUPS_V3 = ROW_GROUPS_V2 + ('sfc_declarations',)
COUNT_MAPS_V3 = {**COUNT_MAPS_V2,
    'boundary_contents_by_status': BOUNDARY_CONTENT_STATUSES | {
        'qualified_sfc', 'incomplete_sfc', 'multiple_sfc_declarations'},
    'calls_by_boundary_status': CALL_BOUNDARY_STATUSES | {'multiple_declarations'},
    'calls_by_boundary_profile': BOUNDARY_PROFILES | {'sfc_absent', 'sfc_declared'},
    'boundary_contents_by_language': frozenset({'RLL', 'SFC'}),
    'calls_by_target_language': frozenset({'RLL', 'SFC', 'other', 'unavailable'}),
    'sfc_in_attributes': frozenset({'missing', 'empty', 'text'}),
    'sfc_ret_attributes': frozenset({'missing', 'empty', 'text'})}
COVERAGE_KEYS_V3 = COVERAGE_KEYS_V2 | frozenset(COUNT_MAPS_V3) | {
    'sfc_declarations_total', 'sfc_contents_with_declarations',
    'sfc_contents_with_multiple_declarations', 'sfc_source_content_links'}
_V3_FIELDS = frozenset({'sfc_declarations'})


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
    boundary_contents: list[dict[str, Any]] = field(default_factory=list)
    call_boundaries: list[dict[str, Any]] = field(default_factory=list)
    argument_contexts: list[dict[str, Any]] = field(default_factory=list)
    sfc_declarations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        render_execution_context_json(self)
        return deepcopy(_project_data(self))


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


def _partial(c: dict[str, Any], schema_version: int = 1) -> bool:
    incomplete = bool(c['unparsed_rungs'] or c['programs_missing_type'] or c['main_designation_gaps']
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
    if schema_version >= 2:
        qualified = c['boundary_contents_by_status']['qualified_rll']
        if schema_version >= 3:
            qualified += c['boundary_contents_by_status']['qualified_sfc']
        incomplete |= (c['boundary_contents_total'] != qualified
            or c['calls_total'] != c['calls_by_boundary_status']['associated']
            or c['unprofiled_boundary_occurrences'] != 0
            or c['argument_contexts_total'] != sum(c['argument_contexts_by_status'][key]
                for key in ('routine_target', 'literal', 'root_bound_candidate')))
    return incomplete


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


def _with_boundaries(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, base: ExecutionContextResult, *, schema_version: int = 2) -> ExecutionContextResult:
    """Link source containers and lexical address candidates, never parameters."""
    retained = len(render_execution_context_json(base).encode('utf-8'))
    records = sum(len(getattr(base, key)) for key in ROW_GROUPS) + sum(len(row['event_info']) for row in base.tasks)
    links = pending = 0

    def reserve(amount: int) -> None:
        nonlocal links, pending
        if (base.coverage['evidence_links'] + links + amount > MAX_EVIDENCE_IDS
                or retained + pending + 96 * amount > MAX_EXECUTION_CONTEXT_BYTES):
            _invalid()
        links += amount
        pending += 96 * amount

    def retain(rows: list[dict[str, Any]], row: dict[str, Any]) -> None:
        nonlocal retained, records, pending
        records += 1
        retained += len(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if records > MAX_EXECUTION_CONTEXT_RECORDS or retained > MAX_EXECUTION_CONTEXT_BYTES:
            _invalid()
        pending = 0
        rows.append(row)

    nodes = _read_nodes(snapshot.data)
    by_locator = {node.locator: index for index, node in enumerate(nodes)}
    qualified, entity_ok, binding_ok = _qualified_source(snapshot, inventory)
    subtree_qualified = [qualified[node.locator] for node in nodes]
    protected = []
    for node in nodes:
        protected.append(bool((_PROTECTION_MARKERS | {'IsEncrypted'}).intersection(node.attributes))
            or node.name in {'EncodedData', 'EncryptedContent', 'EncryptedAOIContent', 'EncryptionInfo'}
            or bool(node.parent is not None and protected[node.parent]))
    subtree_protected = list(protected)
    for index in reversed(range(len(nodes))):
        parent = nodes[index].parent
        if parent is not None:
            subtree_qualified[parent] &= subtree_qualified[index]
            subtree_protected[parent] |= subtree_protected[index]
    entities = {entity.id: entity for entity in inventory.entities}
    rungs = {rung.id: rung for rung in inventory.rungs}
    rungs_by_content: dict[str, list[Any]] = defaultdict(list)
    for rung in inventory.rungs:
        parent = nodes[by_locator[rung.locator]].parent
        if parent is not None:
            rungs_by_content[nodes[parent].locator].append(rung)
    controls_by_content: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(lambda: {'SBR': [], 'RET': []})
    for row in base.control_occurrences:
        if row['opcode'] in {'SBR', 'RET'}:
            controls_by_content[row['caller_routine_id'], row['content_locator']][row['opcode']].append(row['id'])
    c = deepcopy(base.coverage)
    count_maps = COUNT_MAPS_V3 if schema_version == 3 else COUNT_MAPS_V2
    coverage_keys = COVERAGE_KEYS_V3 if schema_version == 3 else COVERAGE_KEYS_V2
    for key, vocabulary in count_maps.items():
        if key not in COUNT_MAPS:
            c[key] = dict.fromkeys(sorted(vocabulary), 0)
    c.update(dict.fromkeys(sorted(coverage_keys - COVERAGE_KEYS - count_maps.keys()), 0))
    contents, calls, arguments, declarations = [], [], [], []
    content_by_locator = {}
    routine_content_nodes = {}
    sfc_contents, sfc_declarations = {}, defaultdict(list)
    sfc_issue_contents, sfc_issue_routines = set(), set()
    if schema_version == 3:
        # Derive canonical source IDs from the same immutable snapshot. No
        # caller-supplied SFC model or live source reread enters this join.
        sfc = analyze_sfc_structure(snapshot, inventory)
        sfc_contents = {row['locator']: row for row in sfc.contents}
        element_contents = {row['id']: row['content_id'] for row in sfc.elements}
        content_ids = {row['id'] for row in sfc.contents}
        for issue in sfc.issues:
            identifier = issue['source_id']
            if identifier in element_contents:
                sfc_issue_contents.add(element_contents[identifier])
            elif identifier in content_ids:
                sfc_issue_contents.add(identifier)
            else:
                sfc_issue_routines.add(identifier)
        for row in sfc.elements:
            if row['kind'] == 'sbr_ret' and row['parent_id'] is None:
                sfc_declarations[row['content_id']].append(row)
    for routine in inventory.entities:
        owner = entities.get(routine.parent_id)
        if routine.kind != 'routine' or owner is None or owner.kind != 'program':
            continue
        node = nodes[by_locator[routine.locator]]
        content_nodes = [nodes[index] for index in node.children if nodes[index].name.endswith('Content')]
        routine_content_nodes[routine.id] = content_nodes
        language = routine.attributes.get('Type')
        routine_supported = (routine.scope_id == owner.id and language == 'RLL'
            and not node.text.strip() and all(nodes[index].name in {'Description', 'RLLContent'} for index in node.children))
        for content in content_nodes:
            is_sfc = schema_version == 3 and content.name == 'SFCContent'
            if content.name != 'RLLContent' and not is_sfc:
                continue
            sfc_source = sfc_contents.get(content.locator) if is_sfc else None
            declared = sfc_declarations[sfc_source['id']] if sfc_source is not None else []
            captured_rungs = rungs_by_content[content.locator]
            parsed = sum(rung.parse_status == 'parsed' for rung in captured_rungs)
            if not subtree_qualified[by_locator[routine.locator]] or not entity_ok(routine.id):
                status = 'namespace_gap'
            elif subtree_protected[by_locator[routine.locator]]:
                status = 'protected'
            elif is_sfc:
                if (language != 'SFC' or routine.scope_id != owner.id or sfc_source is None
                        or routine.id in sfc_issue_routines):
                    status = 'unsupported_context'
                elif sfc_source['id'] in sfc_issue_contents:
                    status = 'incomplete_sfc'
                elif len(declared) > 1:
                    status = 'multiple_sfc_declarations'
                else:
                    status = 'qualified_sfc'
            elif not routine_supported:
                status = 'unsupported_context'
            elif (content.text.strip() or any(nodes[item].name != 'Rung' for item in content.children)
                    or len(captured_rungs) != len(content.children) or parsed != len(captured_rungs)):
                status = 'incomplete_rll'
            else:
                status = 'qualified_rll'
            boundary_ids = controls_by_content[routine.id, content.locator]
            reserve(1 + len(boundary_ids['SBR']) + len(boundary_ids['RET'])
                + int(sfc_source is not None) + len(declared))
            row = {'id': _identifier('execution_content_', routine.id, content.locator),
                'routine_id': routine.id, 'content_locator': content.locator, 'status': status,
                'raw_attributes': dict(content.expanded_attributes), 'rungs_total': len(captured_rungs),
                'parsed_rungs': parsed, 'sbr_control_ids': list(boundary_ids['SBR']),
                'ret_control_ids': list(boundary_ids['RET'])}
            if schema_version == 3:
                row.update(language='SFC' if is_sfc else 'RLL',
                    source_sfc_content_id=sfc_source['id'] if sfc_source is not None else None,
                    sfc_declaration_ids=[_identifier('execution_sfc_declaration_', item['id']) for item in declared])
                c['boundary_contents_by_language'][row['language']] += 1
            retain(contents, row)
            content_by_locator[content.locator] = row
            c['boundary_contents_by_status'][status] += 1
            c['boundary_rungs_total'] += len(captured_rungs)
            c['boundary_parsed_rungs'] += parsed
            c['boundary_sbr_occurrences'] += len(boundary_ids['SBR'])
            c['boundary_ret_occurrences'] += len(boundary_ids['RET'])
            if schema_version == 3 and is_sfc:
                c['sfc_source_content_links'] += int(sfc_source is not None)
                c['sfc_contents_with_declarations'] += int(bool(declared))
                c['sfc_contents_with_multiple_declarations'] += int(len(declared) > 1)
                for item in declared:
                    reserve(2)
                    raw_attributes = dict(nodes[by_locator[item['locator']]].expanded_attributes)
                    states = {key: 'missing' if attribute not in raw_attributes else 'empty'
                        if not raw_attributes[attribute].strip() else 'text'
                        for key, attribute in (('in', 'In'), ('ret', 'Ret'))}
                    retain(declarations, {'id': _identifier('execution_sfc_declaration_', item['id']),
                        'content_id': row['id'], 'source_sfc_element_id': item['id'],
                        'source_locator': item['locator'], 'raw_attributes': raw_attributes,
                        'in_attribute_status': states['in'], 'ret_attribute_status': states['ret']})
                    for key in states:
                        c[f'sfc_{key}_attributes'][states[key]] += 1

    associated_contents = set()
    for call in base.calls:
        target = entities.get(call['target_routine_id'])
        target_contents = routine_content_nodes.get(call['target_routine_id'], [])
        content = content_by_locator.get(target_contents[0].locator) if len(target_contents) == 1 else None
        if call['status'] == 'namespace_gap':
            status = 'namespace_gap'
        elif subtree_protected[by_locator[entities[call['caller_routine_id']].locator]]:
            status = 'protected'
        elif target is None:
            status = 'target_unavailable'
        elif target.attributes.get('Type') not in ({'RLL', 'SFC'} if schema_version == 3 else {'RLL'}):
            status = 'unsupported_language'
        elif not entity_ok(target.id):
            status = 'namespace_gap'
        elif subtree_protected[by_locator[target.locator]]:
            status = 'protected'
        elif not target_contents:
            status = 'missing_content'
        elif len(target_contents) > 1:
            status = 'multiple_contents'
        elif content is None:
            status = 'unsupported_context'
        else:
            status = {'qualified_rll': 'associated', 'qualified_sfc': 'associated',
                'incomplete_rll': 'incomplete_content', 'incomplete_sfc': 'incomplete_content',
                'multiple_sfc_declarations': 'multiple_declarations'}.get(content['status'], content['status'])
        profile = 'not_available'
        if status == 'associated':
            profile = ('sbr_and_ret' if content['sbr_control_ids'] and content['ret_control_ids'] else
                'sbr_only' if content['sbr_control_ids'] else 'ret_only' if content['ret_control_ids'] else 'none')
            if schema_version == 3 and content['language'] == 'SFC':
                profile = 'sfc_declared' if content['sfc_declaration_ids'] else 'sfc_absent'
            associated_contents.add(content['id'])
        raw = call['raw_arguments']
        second = raw[1].strip() if len(raw) > 1 else None
        second_kind = ('absent' if second is None else 'empty' if not second else 'exact_zero' if second == '0'
            else 'other_ascii_decimal' if re.fullmatch('[0-9]+', second, re.ASCII) else 'other')
        shape = ('zero_fields' if not raw else 'one_field' if len(raw) == 1 else
            ('two_fields' if len(raw) == 2 else 'three_or_more') + ('_second_zero' if second == '0' else '_second_other'))
        content_id = content['id'] if content is not None else None
        reserve(1 + int(target is not None) + int(content_id is not None))
        row = {'call_id': call['id'], 'target_routine_id': call['target_routine_id'],
            'target_content_count': len(target_contents), 'target_content_id': content_id,
            'status': status, 'boundary_profile': profile, 'field_shape': shape, 'second_field_kind': second_kind}
        if schema_version == 3:
            language = 'unavailable' if target is None else target.attributes.get('Type')
            row['target_language'] = language if language in {'RLL', 'SFC', 'unavailable'} else 'other'
            c['calls_by_target_language'][row['target_language']] += 1
        retain(calls, row)
        c['calls_by_boundary_status'][status] += 1
        c['calls_by_boundary_profile'][profile] += 1
        c['calls_by_second_field_kind'][second_kind] += 1
        c['calls_by_field_shape'][shape] += 1
        c['calls_with_target_content'] += int(content_id is not None)
        if profile in {'sbr_only', 'sbr_and_ret'}:
            c['sbr_target_calls_by_shape'][shape] += 1
        if profile in {'ret_only', 'sbr_and_ret'}:
            c['ret_target_calls_by_shape'][shape] += 1

    resolver = _Resolver(inventory)
    operands = {(row['instruction_id'], row['argument_index']): row for row in references.operands}
    for occurrence in base.calls + base.control_occurrences:
        if occurrence['opcode'] not in {'JSR', 'SBR', 'RET'}:
            continue
        rung = rungs[occurrence['rung_id']]
        routine = entities[rung.parent_id]
        owner = entities.get(routine.parent_id)
        index = by_locator[rung.locator]
        for position, raw in enumerate(occurrence['raw_arguments']):
            value = raw.strip()
            binding = _binding('routine_target')
            if occurrence['opcode'] == 'JSR' and position == 0:
                pass
            elif not subtree_qualified[index]:
                binding = _binding('namespace_gap')
            elif subtree_protected[by_locator[routine.locator]]:
                binding = _binding('protected')
            elif owner is None or owner.kind != 'program' or routine.scope_id != owner.id:
                binding = _binding('unsupported_context')
            elif not value:
                binding = _binding('empty')
            elif _literal(value):
                binding = _binding('literal')
            else:
                binding = resolver.resolve(value, rung.scope_id)
                evidence = [binding['symbol_id'], binding['target_id'], *binding['alias_chain']]
                if not binding_ok(binding):
                    binding = _binding('namespace_gap')
                elif any(protected[by_locator[entities[item].locator]] for item in evidence if item is not None):
                    binding = _binding('protected')
                elif binding['status'] == 'root_bound':
                    binding['status'] = 'root_bound_candidate'
            reserve(3 + int(binding['symbol_id'] is not None) + int(binding['target_id'] is not None) + len(binding['alias_chain']))
            row = {'occurrence_id': occurrence['id'], 'instruction_id': occurrence['instruction_id'],
                'operand_id': operands[occurrence['instruction_id'], position]['id'],
                'argument_index': position, **binding}
            retain(arguments, row)
            c['argument_contexts_by_status'][binding['status']] += 1
            c['argument_contexts_by_opcode'][occurrence['opcode']] += 1
            c['argument_candidate_symbols'] += int(binding['symbol_id'] is not None)
            c['argument_alias_links'] += len(binding['alias_chain'])
    c.update(boundary_contents_total=len(contents), call_boundaries_total=len(calls),
        argument_contexts_total=len(arguments), distinct_associated_contents=len(associated_contents),
        unprofiled_boundary_occurrences=c['controls_by_opcode']['SBR'] + c['controls_by_opcode']['RET']
            - c['boundary_sbr_occurrences'] - c['boundary_ret_occurrences'], boundary_evidence_links=links)
    constants = EXECUTION_CONTEXT_CONSTANTS_V3 if schema_version == 3 else EXECUTION_CONTEXT_CONSTANTS_V2
    if schema_version == 3:
        c['sfc_declarations_total'] = len(declarations)
    return ExecutionContextResult(**{**vars(base), **constants,
        'status': 'partial' if _partial(c, schema_version) else 'complete', 'coverage': c,
        'boundary_contents': contents, 'call_boundaries': calls, 'argument_contexts': arguments,
        'sfc_declarations': declarations})


def analyze_execution_context(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, *, schema_version: int = 1) -> ExecutionContextResult:
    """Authenticate the supplied condition version and every prior input."""
    try:
        if type(schema_version) is not int or schema_version not in {1, 2, 3}:
            _invalid()
        if type(conditions) is not ConditionResult or type(conditions.schema_version) is not int or conditions.schema_version not in (3, 4, 5, 6):
            _invalid()
        validate_conditions(snapshot, inventory, references, access, calculations, rung_analysis, relationships, conditions)
        result = _derive(snapshot, inventory, references, access, conditions)
        if schema_version >= 2:
            result = _with_boundaries(snapshot, inventory, references, result, schema_version=schema_version)
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
                                             rung_analysis, relationships, conditions, schema_version=result.schema_version)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except ExecutionContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def _project_data(result: ExecutionContextResult) -> dict[str, Any]:
    if (type(result) is not ExecutionContextResult or vars(result).keys() != set(ExecutionContextResult.__dataclass_fields__)
            or type(result.schema_version) is not int or result.schema_version not in {1, 2, 3}):
        _invalid()
    if result.schema_version == 1:
        if any(type(getattr(result, key)) is not list or getattr(result, key) for key in _V2_FIELDS | _V3_FIELDS):
            _invalid()
        return {key: value for key, value in vars(result).items() if key not in _V2_FIELDS | _V3_FIELDS}
    if result.schema_version == 2:
        if type(result.sfc_declarations) is not list or result.sfc_declarations:
            _invalid()
        return {key: value for key, value in vars(result).items() if key not in _V3_FIELDS}
    return vars(result)


def render_execution_context_json(result: ExecutionContextResult) -> str:
    """Bound native containers and encoding; replay authenticates source meaning."""
    try:
        payload = _project_data(result)
        remaining, identifiers = MAX_EXECUTION_CONTEXT_BYTES, 0
        frames = [(iter((payload,)), None)]
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
        if (sum(len(getattr(result, key)) for key in (ROW_GROUPS_V3 if result.schema_version == 3 else
                ROW_GROUPS_V2 if result.schema_version == 2 else ROW_GROUPS))
                + sum(len(task['event_info']) for task in result.tasks) > MAX_EXECUTION_CONTEXT_RECORDS):
            _invalid()
        output, size = StringIO(), 1
        for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).iterencode(payload):
            size += len(chunk.encode('utf-8'))
            if size > MAX_EXECUTION_CONTEXT_JSON_BYTES:
                _invalid()
            output.write(chunk)
        return output.getvalue() + '\n'
    except ExecutionContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
