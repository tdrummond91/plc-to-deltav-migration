"""Factorized Boolean signal source navigation, without execution inference.

Contact occurrences bind to exact addresses and existing condition DAG nodes.
Coil guards stay separate: no contact-by-coil pairs, transitive paths, edit
selection, or implicit timer/PID transfer is materialized here.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from io import StringIO
import json
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .conditions import ConditionResult, validate_conditions
from .execution_context import (ExecutionContextResult, _derive as _execution_derive,
    render_execution_context_json)
from .models import InventoryResult, SourceSnapshot
from .output_context import (BooleanOutputContextResult, _derive as _output_derive,
    _provenance, render_output_context_json)
from .references import ReferenceResult, _strict_record_match
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult
from .sfc_context import _qualified_source
from .source import _read_nodes
from .stateful_objects import (StatefulObjectResult, _derive as _stateful_derive,
    render_stateful_objects_json)
from .tag_data import TagDataResult, validate_tag_data

MAX_SIGNAL_CONTEXT_RECORDS = 250_000
MAX_SIGNAL_CONTEXT_BYTES = 32 * 1024 * 1024
MAX_SIGNAL_CONTEXT_JSON_BYTES = 32 * 1024 * 1024
MAX_EVIDENCE_IDS = 1_000_000
ROW_GROUPS = ('outputs', 'condition_reads', 'addresses', 'rung_contexts')
ROLES = frozenset({'read', 'write', 'read_write', 'unknown'})
HINT_CATEGORIES = frozenset({'alarm', 'equipment', 'sensor'})
TARGET_STATUSES = frozenset({'exact_address', 'identity_gap', 'unbound', 'signature_unresolved', 'namespace_gap'})
GUARD_QUALITIES = frozenset({'modeled', 'binding_gaps', 'opaque', 'stateful', 'namespace_gap'})
READ_STATUSES = frozenset({'exact_address', 'identity_gap', 'unbound', 'literal', 'system_flag', 'namespace_gap'})
ENDPOINT_KINDS = frozenset({'module_output', 'module_input', 'module_config', 'tag', 'other'})
COUNT_MAPS = {
    'outputs_by_opcode': frozenset({'OTE', 'OTL', 'OTU'}), 'targets_by_status': TARGET_STATUSES,
    'guards_by_quality': GUARD_QUALITIES, 'reads_by_kind': frozenset({'xic', 'xio', 'comparison', 'ons_storage'}),
    'reads_by_status': READ_STATUSES, 'endpoint_kinds': ENDPOINT_KINDS,
    'address_profiles': frozenset({'coil_and_condition', 'coil_only', 'condition_only'}),
    'accepted_operands_by_role': ROLES, 'rejected_operands_by_role': ROLES,
    'stateful_associations_by_kind': frozenset({'whole_control', 'direct_member', 'other_member'}),
    'stateful_associations_by_qualification': frozenset({'qualified', 'namespace_gap'}),
    'hints_by_category': HINT_CATEGORIES, 'unqualified_hints_by_category': HINT_CATEGORIES,
    'rungs_by_qualification': frozenset({'qualified', 'namespace_gap'}),
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | frozenset({
    'source_rungs', 'source_instructions', 'source_operands', 'source_expression_uses',
    'source_condition_nodes', 'source_predicate_operands', 'source_ons_storage_operands',
    'source_outputs', 'source_addresses', 'source_stateful_objects',
    'source_stateful_address_uses', 'source_routines', 'unparsed_rungs',
    'outputs_total', 'condition_reads_total', 'addresses_total', 'rung_contexts_total',
    'accepted_expression_uses', 'rejected_expression_uses', 'noncoil_writers_total',
    'stateful_associations_total', 'rungs_with_hints', 'rungs_with_unqualified_hints',
    'outputs_with_branches', 'outputs_with_stateful_conditions', 'addresses_with_multiple_coils',
    'addresses_with_noncoil_writers', 'addresses_with_unknown_roles', 'addresses_with_rejected_uses',
})
SIGNAL_CONTEXT_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'signal-context-1',
    'analysis_scope': 'factorized_boolean_signal_source_context',
    'address_identity': 'exact_expanded_spelling', 'condition_usage': 'source_dag_navigation',
    'execution_analysis': 'not_implemented', 'shutdown_analysis': 'not_implemented',
    'physical_mapping': 'not_implemented', 'edit_selection': 'not_implemented',
    'engineering_review': 'unreviewed', 'hint_scope': 'rung_wide_only',
    'stateful_usage': 'source_association_not_boolean_transfer',
}
_ENDPOINTS = {'module_output_tag': 'module_output', 'module_input_tag': 'module_input',
              'module_config_tag': 'module_config', 'tag': 'tag'}


class SignalContextError(ValueError):
    """Fixed source-free evidence rejection."""


def _invalid() -> None:
    raise SignalContextError('Signal context evidence is inconsistent or exceeds its limits.') from None


@dataclass(frozen=True)
class SignalContextResult:
    snapshot: dict[str, str | int]
    status: str
    outputs: list[dict[str, Any]]
    condition_reads: list[dict[str, Any]]
    addresses: list[dict[str, Any]]
    rung_contexts: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'signal-context-1'
    analysis_scope: str = 'factorized_boolean_signal_source_context'
    address_identity: str = 'exact_expanded_spelling'
    condition_usage: str = 'source_dag_navigation'
    execution_analysis: str = 'not_implemented'
    shutdown_analysis: str = 'not_implemented'
    physical_mapping: str = 'not_implemented'
    edit_selection: str = 'not_implemented'
    engineering_review: str = 'unreviewed'
    hint_scope: str = 'rung_wide_only'
    stateful_usage: str = 'source_association_not_boolean_transfer'

    def to_dict(self) -> dict[str, Any]:
        render_signal_context_json(self)
        return deepcopy(vars(self))


class _Budget:
    def __init__(self) -> None:
        self.records = self.bytes = self.ids = 0

    def retain(self, row: dict[str, Any]) -> None:
        self.records += 1
        self.bytes += len(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self.records > MAX_SIGNAL_CONTEXT_RECORDS or self.bytes > MAX_SIGNAL_CONTEXT_BYTES:
            _invalid()

    def links(self, rows: list[str]) -> list[str]:
        self.ids += len(rows)
        if self.ids > MAX_EVIDENCE_IDS or self.bytes + 64 * len(rows) > MAX_SIGNAL_CONTEXT_BYTES:
            _invalid()
        return list(rows)

    def append_link(self, rows: list[str], identifier: str) -> None:
        self.ids += 1
        self.bytes += len(identifier.encode('utf-8')) + 4
        if self.ids > MAX_EVIDENCE_IDS or self.bytes > MAX_SIGNAL_CONTEXT_BYTES:
            _invalid()
        rows.append(identifier)


def _partial(c: dict[str, Any]) -> bool:
    return bool(c['unparsed_rungs'] or c['outputs_total'] != c['targets_by_status']['exact_address']
        or c['outputs_total'] != c['guards_by_quality']['modeled']
        or any(c['reads_by_status'][key] for key in ('identity_gap', 'unbound', 'namespace_gap'))
        or c['rungs_by_qualification']['namespace_gap'] or c['addresses_with_unknown_roles']
        or c['addresses_with_rejected_uses'] or c['rungs_with_unqualified_hints']
        or c['stateful_associations_by_qualification']['namespace_gap'])


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, access: AccessResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult, conditions: ConditionResult,
        output_context: BooleanOutputContextResult, stateful_objects: StatefulObjectResult,
        execution_context: ExecutionContextResult) -> SignalContextResult:
    if any(len(rows) > MAX_SIGNAL_CONTEXT_RECORDS for rows in (inventory.rungs, inventory.entities,
            access.instructions, access.operands, access.expression_uses, conditions.nodes,
            relationships.addresses, stateful_objects.objects, stateful_objects.address_uses)):
        _invalid()
    budget = _Budget()
    qualified, _, strict_binding_ok = _qualified_source(snapshot, inventory)
    rung_ok, old_binding_ok, text_ok = _provenance(snapshot, inventory)
    nodes = _read_nodes(snapshot.data)
    xml = {node.locator: node for node in nodes}
    entities = {row.id: row for row in inventory.entities}
    text_qualification: dict[str, bool] = {}
    for owner in (*inventory.entities, *inventory.rungs):
        node = xml[owner.locator]
        okay = text_ok[owner.id] and qualified[owner.locator]
        stack = [index for index in node.children if nodes[index].name in {'Description', 'Comment'}]
        while stack:
            child = nodes[stack.pop()]
            okay = okay and qualified[child.locator]
            stack.extend(child.children)
        text_qualification[owner.id] = okay
    source_instructions = {row.id: row for rung in inventory.rungs for row in rung.instructions}
    operands = {row['id']: row for row in access.operands}
    expressions = {row['id']: row for row in access.expression_uses}
    expression_by_instruction: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in access.expression_uses:
        expression_by_instruction[row['instruction_id']].append(row)
    for rung in inventory.rungs:
        rung_ok[rung.id] = rung_ok[rung.id] and qualified[rung.locator] and all(
            qualified[nodes[index].locator] for index in xml[rung.locator].children
            if nodes[index].name == 'Text')

    def binding_ok(row: dict[str, Any]) -> bool:
        return rung_ok[row['rung_id']] and old_binding_ok(row) and strict_binding_ok(row)

    context_ok: dict[str, bool] = {}
    for row in conditions.nodes:
        context_ok[row['id']] = (rung_ok[row['rung_id']]
            and all(context_ok[identifier] for identifier in row['child_ids'])
            and all(operands[identifier]['binding_status'] != 'root_bound' or binding_ok(operands[identifier])
                    for identifier in row['operand_ids'])
            and all(use['binding_status'] != 'root_bound' or binding_ok(use)
                    for use in expression_by_instruction.get(row['instruction_id'], [])))
    condition_nodes = {row['id']: row for row in conditions.nodes}
    address_by_operand = {identifier: row['id'] for row in relationships.addresses
        for role in ROLES for identifier in row[f'{role}_operand_ids']}
    identity_gaps = {row['id'] for row in relationships.identity_gaps if row['kind'] == 'operand'}
    execution_routines = {row['routine_id']: row for row in execution_context.routine_contexts}
    c = {key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()}
    c.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
    c.update(source_rungs=len(inventory.rungs), source_instructions=len(access.instructions),
        source_operands=len(access.operands), source_expression_uses=len(access.expression_uses),
        source_condition_nodes=len(conditions.nodes), source_outputs=len(output_context.outputs),
        source_predicate_operands=sum(len(row['operand_ids']) for row in conditions.nodes if row['kind'] == 'predicate'),
        source_ons_storage_operands=sum(len(row['operand_ids']) for row in conditions.nodes if row['kind'] == 'stateful_transfer'),
        source_addresses=len(relationships.addresses), source_stateful_objects=len(stateful_objects.objects),
        source_stateful_address_uses=len(stateful_objects.address_uses),
        source_routines=len(execution_context.routine_contexts),
        unparsed_rungs=sum(row.parse_status != 'parsed' for row in inventory.rungs))
    outputs, reads, addresses, contexts = [], [], [], []
    contexts_by_rung: dict[str, dict[str, Any]] = {}
    hints: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in rung_analysis.candidates:
        if candidate['category'] in HINT_CATEGORIES and candidate['basis'] == 'text_hint':
            hints[candidate['rung_id']].append(candidate)
    for rung in inventory.rungs:
        node = xml[rung.locator]
        content = nodes[node.parent] if node.parent is not None else None
        routine = execution_routines.get(rung.parent_id)
        context = {'id': rung.id, 'routine_id': rung.parent_id,
            'program_id': routine['program_id'] if routine is not None else None,
            'content_locator': content.locator if content is not None else None,
            'content_attributes': dict(content.expanded_attributes) if content is not None else {},
            'qualified': rung_ok[rung.id],
            'execution_routine_context_id': routine['id'] if routine is not None else None,
            'output_ids': [], 'condition_read_ids': [],
            'candidate_ids_by_category': {key: [] for key in sorted(HINT_CATEGORIES)},
            'unqualified_candidate_ids_by_category': {key: [] for key in sorted(HINT_CATEGORIES)}}
        for candidate in hints[rung.id]:
            okay = rung_ok[rung.id] and all(text_qualification.get(identifier, False) for identifier in candidate['evidence_ids'])
            group = 'candidate_ids_by_category' if okay else 'unqualified_candidate_ids_by_category'
            context[group][candidate['category']].append(candidate['id'])
            c['hints_by_category' if okay else 'unqualified_hints_by_category'][candidate['category']] += 1
        budget.retain(context)
        contexts.append(context)
        contexts_by_rung[rung.id] = context
        c['rungs_by_qualification']['qualified' if context['qualified'] else 'namespace_gap'] += 1
        c['rungs_with_hints'] += int(any(context['candidate_ids_by_category'].values()))
        c['rungs_with_unqualified_hints'] += int(any(context['unqualified_candidate_ids_by_category'].values()))
    outputs_by_address: dict[str, list[str]] = defaultdict(list)
    reads_by_address: dict[str, list[str]] = defaultdict(list)
    coil_instruction_ids = {row['instruction_id'] for row in output_context.outputs}
    for source in output_context.outputs:
        context = contexts_by_rung[source['rung_id']]
        target = operands.get(source['target_operand_id'])
        target_status = source['target_status']
        if not context['qualified'] or target is not None and target['binding_status'] == 'root_bound' and not binding_ok(target):
            target_status = 'namespace_gap'
        guard = condition_nodes[source['guard_id']]
        namespace_gap = not context_ok[guard['id']]
        quality = ('namespace_gap' if namespace_gap else 'opaque' if guard['has_opaque'] else
            'binding_gaps' if guard['has_binding_gap'] else 'stateful' if guard['has_stateful'] else 'modeled')
        row = {key: source[key] for key in ('id', 'condition_output_id', 'instruction_id', 'rung_id',
            'opcode', 'action', 'target_operand_id', 'guard_id', 'has_branch', 'has_stateful', 'has_opaque', 'has_binding_gap')}
        row.update(output_context_id=source['id'], routine_id=context['routine_id'], program_id=context['program_id'],
            content_locator=context['content_locator'], target_status=target_status,
            target_address_id=source['target_address_id'] if target_status == 'exact_address' else None,
            guard_quality=quality, has_namespace_gap=namespace_gap)
        budget.retain(row)
        outputs.append(row)
        budget.append_link(context['output_ids'], row['id'])
        if row['target_address_id'] is not None:
            outputs_by_address[row['target_address_id']].append(row['id'])
        c['outputs_by_opcode'][row['opcode']] += 1
        c['targets_by_status'][target_status] += 1
        c['guards_by_quality'][quality] += 1
        c['outputs_with_branches'] += int(row['has_branch'])
        c['outputs_with_stateful_conditions'] += int(row['has_stateful'])
    for node in conditions.nodes:
        if node['kind'] not in {'predicate', 'stateful_transfer'}:
            continue
        opcode = source_instructions[node['instruction_id']].opcode.upper()
        kind = 'ons_storage' if node['kind'] == 'stateful_transfer' else opcode.lower() if opcode in {'XIC', 'XIO'} else 'comparison'
        for identifier in node['operand_ids']:
            operand = operands[identifier]
            address = address_by_operand.get(identifier)
            status = ('exact_address' if address is not None else operand['binding_status']
                if operand['binding_status'] in {'literal', 'system_flag'} else
                'identity_gap' if identifier in identity_gaps else 'unbound')
            if not context_ok[node['id']] or operand['binding_status'] == 'root_bound' and not binding_ok(operand):
                status = 'namespace_gap'
            row = {'id': identifier, 'condition_node_id': node['id'], 'instruction_id': node['instruction_id'],
                'rung_id': node['rung_id'], 'source_address_id': address if status == 'exact_address' else None,
                'status': status, 'kind': kind}
            budget.retain(row)
            reads.append(row)
            budget.append_link(contexts_by_rung[row['rung_id']]['condition_read_ids'], identifier)
            if row['source_address_id'] is not None:
                reads_by_address[row['source_address_id']].append(identifier)
            c['reads_by_kind'][kind] += 1
            c['reads_by_status'][status] += 1
    stateful_by_address: dict[str, list[dict[str, Any]]] = defaultdict(list)
    qualified_objects = set()
    for occurrence in stateful_objects.occurrences:
        operand = operands.get(occurrence['control_operand_id'])
        if occurrence['target_status'] == 'exact_address' and operand is not None and binding_ok(operand):
            qualified_objects.add(occurrence['control_address_id'])
    for source in stateful_objects.address_uses:
        stateful_by_address[source['address_id']].append(source)
    for source in relationships.addresses:
        identifier = source['id']
        if identifier not in outputs_by_address and identifier not in reads_by_address:
            continue
        row = {'id': identifier, 'target_id': source['target_id'],
            'endpoint_kind': _ENDPOINTS.get(entities[source['target_id']].kind, 'other'),
            'output_ids': budget.links(outputs_by_address[identifier]),
            'condition_read_ids': budget.links(reads_by_address[identifier]),
            'rejected_operand_ids': [], 'rejected_expression_use_ids': [],
            'noncoil_writer_operand_ids': [], 'expression_use_ids': [], 'stateful_associations': []}
        for role in sorted(ROLES):
            accepted = []
            for operand_id in source[f'{role}_operand_ids']:
                operand = operands[operand_id]
                okay = binding_ok(operand)
                (accepted if okay else row['rejected_operand_ids']).append(operand_id)
                c['accepted_operands_by_role' if okay else 'rejected_operands_by_role'][role] += 1
                if okay and role in {'write', 'read_write'} and operand['instruction_id'] not in coil_instruction_ids:
                    row['noncoil_writer_operand_ids'].append(operand_id)
            row[f'{role}_operand_ids'] = accepted
        for use_id in source['expression_use_ids']:
            okay = binding_ok(expressions[use_id])
            row['expression_use_ids' if okay else 'rejected_expression_use_ids'].append(use_id)
            c['accepted_expression_uses' if okay else 'rejected_expression_uses'] += 1
        for association in stateful_by_address[identifier]:
            item = {key: association[key] for key in ('object_id', 'kind', 'member', 'member_status')}
            item['qualification'] = 'qualified' if item['object_id'] in qualified_objects else 'namespace_gap'
            row['stateful_associations'].append(item)
            c['stateful_associations_by_kind'][item['kind']] += 1
            c['stateful_associations_by_qualification'][item['qualification']] += 1
            c['stateful_associations_total'] += 1
        row['profile'] = 'coil_and_condition' if row['output_ids'] and row['condition_read_ids'] else 'coil_only' if row['output_ids'] else 'condition_only'
        budget.retain(row)
        addresses.append(row)
        c['endpoint_kinds'][row['endpoint_kind']] += 1
        c['address_profiles'][row['profile']] += 1
        c['noncoil_writers_total'] += len(row['noncoil_writer_operand_ids'])
        c['addresses_with_multiple_coils'] += int(len(row['output_ids']) > 1)
        c['addresses_with_noncoil_writers'] += int(bool(row['noncoil_writer_operand_ids']))
        c['addresses_with_unknown_roles'] += int(bool(row['unknown_operand_ids']))
        c['addresses_with_rejected_uses'] += int(bool(row['rejected_operand_ids'] or row['rejected_expression_use_ids']))
    c.update(outputs_total=len(outputs), condition_reads_total=len(reads), addresses_total=len(addresses), rung_contexts_total=len(contexts))
    return SignalContextResult(deepcopy(inventory.snapshot), 'partial' if _partial(c) else 'complete',
        outputs, reads, addresses, contexts, c)


def analyze_signal_context(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, tag_data: TagDataResult, output_context: BooleanOutputContextResult,
        stateful_objects: StatefulObjectResult, execution_context: ExecutionContextResult) -> SignalContextResult:
    """Authenticate the common chain once and replay each companion derivation."""
    try:
        if type(conditions) is not ConditionResult or type(conditions.schema_version) is not int or conditions.schema_version != 3:
            _invalid()
        validate_conditions(snapshot, inventory, references, access, calculations, rung_analysis, relationships, conditions)
        validate_tag_data(snapshot, inventory, tag_data)
        companions = (
            (output_context, BooleanOutputContextResult, render_output_context_json,
             lambda: _output_derive(snapshot, inventory, access, rung_analysis, relationships, conditions)),
            (stateful_objects, StatefulObjectResult, render_stateful_objects_json,
             lambda: _stateful_derive(snapshot, inventory, access, relationships, conditions, tag_data)),
            (execution_context, ExecutionContextResult, render_execution_context_json,
             lambda: _execution_derive(snapshot, inventory, references, access, conditions)),
        )
        for supplied, expected_type, render, derive in companions:
            if type(supplied) is not expected_type:
                _invalid()
            render(supplied)
            if not _strict_record_match(vars(derive()), vars(supplied)):
                _invalid()
        result = _derive(snapshot, inventory, access, rung_analysis, relationships, conditions,
            output_context, stateful_objects, execution_context)
        render_signal_context_json(result)
        return result
    except SignalContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_signal_context(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, tag_data: TagDataResult, output_context: BooleanOutputContextResult,
        stateful_objects: StatefulObjectResult, execution_context: ExecutionContextResult,
        result: SignalContextResult) -> None:
    try:
        render_signal_context_json(result)
        expected = analyze_signal_context(snapshot, inventory, references, access, calculations,
            rung_analysis, relationships, conditions, tag_data, output_context, stateful_objects, execution_context)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except SignalContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_signal_context_json(result: SignalContextResult) -> str:
    """Bound native containers before encoding; replay authenticates meaning."""
    try:
        if type(result) is not SignalContextResult or vars(result).keys() != set(SignalContextResult.__dataclass_fields__):
            _invalid()
        remaining, identifiers = MAX_SIGNAL_CONTEXT_BYTES, 0
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
                if identifier in active or len(value) > MAX_SIGNAL_CONTEXT_RECORDS:
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
        if sum(len(getattr(result, key)) for key in ROW_GROUPS) > MAX_SIGNAL_CONTEXT_RECORDS:
            _invalid()
        output, size = StringIO(), 1
        for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).iterencode(vars(result)):
            size += len(chunk.encode('utf-8'))
            if size > MAX_SIGNAL_CONTEXT_JSON_BYTES:
                _invalid()
            output.write(chunk)
        return output.getvalue() + '\n'
    except SignalContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
