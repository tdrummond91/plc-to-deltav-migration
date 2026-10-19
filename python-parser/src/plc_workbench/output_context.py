"""Qualified source evidence around Boolean coils, without process semantics.

Exact-address groups retain source occurrences once. The existing condition DAG
provides guard reachability; this companion never expands reader/writer pairs,
simulates execution, or assigns a rung-wide authored hint to an individual coil.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from functools import cache
from io import StringIO
import json
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .conditions import ConditionResult, validate_conditions
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult, _strict_record_match
from .relationships import RelationshipResult, _identifier
from .rung_analysis import RungAnalysisResult
from .source import _read_nodes
from .tag_data import _namespace

MAX_OUTPUT_CONTEXT_RECORDS = 250_000
MAX_OUTPUT_CONTEXT_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_CONTEXT_JSON_BYTES = 16 * 1024 * 1024
ROLES = frozenset({'read', 'write', 'read_write', 'unknown'})
HINT_CATEGORIES = frozenset({'alarm', 'equipment', 'sensor'})
TARGET_STATUSES = frozenset({'exact_address', 'identity_gap', 'unbound', 'signature_unresolved', 'namespace_gap'})
CONTEXT_STATUSES = frozenset({'modeled', 'binding_gaps', 'opaque', 'stateful', 'namespace_gap'})
ENDPOINT_KINDS = frozenset({'module_output', 'module_input', 'module_config', 'tag', 'other'})
COUNT_MAPS = {
    'outputs_by_opcode': frozenset({'OTE', 'OTL', 'OTU'}),
    'targets_by_status': TARGET_STATUSES, 'contexts_by_status': CONTEXT_STATUSES,
    'guard_statuses': frozenset({'modeled', 'binding_gaps', 'opaque'}),
    'actions_by_status': frozenset({'recognized', 'unresolved'}),
    'endpoint_kinds': ENDPOINT_KINDS, 'address_profiles': frozenset({'read_and_write', 'write_only'}),
    'accepted_operands_by_role': ROLES, 'rejected_operands_by_role': ROLES,
    'condition_read_kinds': frozenset({'predicate', 'ons_storage'}),
    'condition_read_statuses': frozenset({'accepted', 'namespace_gap'}),
    'hints_by_category': HINT_CATEGORIES, 'unqualified_hints_by_category': HINT_CATEGORIES,
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | frozenset({
    'source_rungs', 'source_instructions', 'source_operands', 'source_expression_uses',
    'source_condition_nodes', 'source_outputs', 'unparsed_rungs', 'outputs_total', 'output_rungs',
    'addresses_total', 'condition_reads_total', 'rung_contexts_total', 'accepted_expression_uses',
    'rejected_expression_uses', 'noncoil_writers_total', 'addresses_with_multiple_coils',
    'addresses_with_noncoil_writers', 'addresses_with_unknown_roles', 'addresses_without_readers',
    'addresses_with_namespace_uses', 'rungs_with_hints', 'rungs_with_unqualified_hints',
    'outputs_with_branches', 'outputs_with_stateful_conditions'})
OUTPUT_CONTEXT_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'output-context-1',
    'analysis_scope': 'boolean_output_source_context', 'address_identity': 'exact_expanded_spelling',
    'execution_analysis': 'not_implemented', 'shutdown_analysis': 'not_implemented',
    'physical_mapping': 'not_implemented', 'engineering_review': 'unreviewed',
    'hint_scope': 'rung_wide_only', 'condition_usage': 'source_dag_not_runtime_influence',
}
_SEMANTIC_ATTRIBUTES = frozenset({'Name', 'TagType', 'AliasFor', 'DataType', 'Dimensions', 'Type',
    'ParentModule', 'ParentModPortId', 'ParentModPortID', 'Id', 'Address', 'Upstream',
    'InputTagSuffix', 'OutputTagSuffix'})
_ENDPOINTS = {'module_output_tag': 'module_output', 'module_input_tag': 'module_input',
              'module_config_tag': 'module_config', 'tag': 'tag'}


class OutputContextError(ValueError):
    """Fixed source-free validation and resource rejection."""


def _invalid() -> None:
    raise OutputContextError('Output context evidence is inconsistent or exceeds its limits.') from None


@dataclass(frozen=True)
class BooleanOutputContextResult:
    snapshot: dict[str, str | int]
    status: str
    outputs: list[dict[str, Any]]
    addresses: list[dict[str, Any]]
    condition_reads: list[dict[str, Any]]
    rung_contexts: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'output-context-1'
    analysis_scope: str = 'boolean_output_source_context'
    address_identity: str = 'exact_expanded_spelling'
    execution_analysis: str = 'not_implemented'
    shutdown_analysis: str = 'not_implemented'
    physical_mapping: str = 'not_implemented'
    engineering_review: str = 'unreviewed'
    hint_scope: str = 'rung_wide_only'
    condition_usage: str = 'source_dag_not_runtime_influence'

    def to_dict(self) -> dict[str, Any]:
        render_output_context_json(self)
        return deepcopy(vars(self))


class _Budget:
    def __init__(self) -> None:
        self.records = self.bytes = 0

    def retain(self, row: dict[str, Any]) -> None:
        self.records += 1
        self.bytes += len(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self.records > MAX_OUTPUT_CONTEXT_RECORDS or self.bytes > MAX_OUTPUT_CONTEXT_BYTES:
            _invalid()


def _provenance(snapshot: SourceSnapshot, inventory: InventoryResult):
    """Qualify source ancestry, aliases and implicit module naming dependencies.

The lexical source model intentionally preserves namespace-confounded evidence.
An explicit module tag name needs its declaration ancestry. An inferred name
also needs the ports and linked parent modules used by the naming algorithm.
"""
    nodes = _read_nodes(snapshot.data)
    namespace = _namespace(nodes[0].expanded_name)
    supported: dict[str, bool] = {}
    for node in nodes:
        supported[node.locator] = (_namespace(node.expanded_name) == namespace
            and not any('}' in key and key.rsplit('}', 1)[-1] in _SEMANTIC_ATTRIBUTES
                        for key in node.expanded_attributes)
            and (node.parent is None or supported[nodes[node.parent].locator]))
    by_locator = {node.locator: node for node in nodes}
    entities = {row.id: row for row in inventory.entities}
    entity_ok = {row.id: supported[row.locator] for row in inventory.entities}
    modules: dict[tuple[str | None, str], list[Any]] = defaultdict(list)
    ports: dict[str, list[Any]] = defaultdict(list)
    for row in inventory.entities:
        if row.kind == 'module' and row.name:
            modules[(row.scope_id, row.name.lower())].append(row)
        elif row.kind == 'module_port':
            ports[row.parent_id].append(row)

    @cache
    def module_binding_ok(identifier: str) -> bool:
        io = entities[identifier]
        if io.kind not in _ENDPOINTS or io.kind == 'tag' or io.name is not None:
            return entity_ok[identifier]
        current = entities.get(io.parent_id)
        if current is not None and current.kind == 'module_connection':
            current = entities.get(current.parent_id)
        seen = set()
        for _ in range(64):
            if current is None or current.kind != 'module' or not entity_ok[current.id]:
                return False
            if any(not entity_ok[row.id] for row in ports[current.id]):
                return False
            if current.id in seen:
                return False
            seen.add(current.id)
            parent_name = current.attributes.get('ParentModule')
            if parent_name is None and current.name and current.name.lower() == 'local':
                parent_name = current.name
            parents = modules.get((current.scope_id, (parent_name or '').lower()), [])
            if len(parents) != 1:
                return False
            parent = parents[0]
            if parent.id == current.id:
                return entity_ok[identifier]
            current = parent
        return False

    rung_ok = {rung.id: supported[rung.locator] and all(
        supported[nodes[index].locator] for index in by_locator[rung.locator].children
        if nodes[index].name == 'Text') for rung in inventory.rungs}

    def binding_ok(row: dict[str, Any]) -> bool:
        return rung_ok[row['rung_id']] and all(identifier in entities
            and entity_ok[identifier] and module_binding_ok(identifier)
            for identifier in [row['symbol_id'], *row['alias_chain'], row['target_id']])

    # Description/Comment text has its own namespace provenance. Quarantine the
    # whole prior candidate if any of its authored evidence is unqualified.
    text_ok = {}
    for row in (*inventory.entities, *inventory.rungs):
        node = by_locator[row.locator]
        okay = supported[row.locator]
        stack = [index for index in node.children if nodes[index].name in {'Description', 'Comment'}]
        while stack:
            child = nodes[stack.pop()]
            okay = okay and supported[child.locator]
            stack.extend(child.children)
        text_ok[row.id] = okay
    return rung_ok, binding_ok, text_ok


def _partial(c: dict[str, Any]) -> bool:
    return bool(c['unparsed_rungs'] or c['outputs_total'] != c['targets_by_status']['exact_address']
        or c['outputs_total'] != c['contexts_by_status']['modeled']
        or c['addresses_with_namespace_uses'] or c['condition_read_statuses']['namespace_gap']
        or c['rungs_with_unqualified_hints'] or c['accepted_operands_by_role']['unknown'])


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, access: AccessResult,
            rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
            conditions: ConditionResult) -> BooleanOutputContextResult:
    if any(len(rows) > MAX_OUTPUT_CONTEXT_RECORDS for rows in
           (inventory.rungs, inventory.entities, access.instructions, access.operands,
            access.expression_uses, conditions.nodes, conditions.outputs, rung_analysis.candidates)):
        _invalid()
    budget = _Budget()
    rung_ok, binding_ok, text_ok = _provenance(snapshot, inventory)
    operands = {row['id']: row for row in access.operands}
    entities = {row.id: row for row in inventory.entities}
    uses_by_instruction: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in access.expression_uses:
        uses_by_instruction[row['instruction_id']].append(row)
    expression_uses = {row['id']: row for row in access.expression_uses}
    address_by_use = {identifier: row for row in relationships.addresses
                      for role in sorted(ROLES) for identifier in row[f'{role}_operand_ids']}
    nodes = {row['id']: row for row in conditions.nodes}
    context_ok = {}
    for node in conditions.nodes:
        context_ok[node['id']] = (rung_ok[node['rung_id']]
            and all(context_ok[child] for child in node['child_ids'])
            and all(operands[identifier]['binding_status'] != 'root_bound'
                    or binding_ok(operands[identifier]) for identifier in node['operand_ids'])
            and all(row['binding_status'] != 'root_bound' or binding_ok(row)
                    for row in uses_by_instruction.get(node['instruction_id'], [])))
    c = {key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()}
    c.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
    c.update(source_rungs=len(inventory.rungs), source_instructions=len(access.instructions),
             source_operands=len(access.operands), source_expression_uses=len(access.expression_uses),
             source_condition_nodes=len(conditions.nodes), source_outputs=len(conditions.outputs),
             unparsed_rungs=sum(row.parse_status != 'parsed' for row in inventory.rungs))
    outputs, addresses, condition_reads, rung_contexts = [], [], [], []
    outputs_by_address: dict[str, list[str]] = defaultdict(list)
    outputs_by_rung: dict[str, list[str]] = defaultdict(list)
    coil_instructions = {row['instruction_id'] for row in conditions.outputs}
    for source in conditions.outputs:
        target = operands.get(source['target_operand_id'])
        target_status = source['target_status']
        if (not rung_ok[source['rung_id']] or target is not None
                and target['binding_status'] == 'root_bound' and not binding_ok(target)):
            target_status = 'namespace_gap'
        target_address = source['target_address_id'] if target_status == 'exact_address' else None
        guard = nodes[source['guard_id']]
        namespace_gap = not context_ok[guard['id']]
        context_status = ('namespace_gap' if namespace_gap else 'opaque' if guard['has_opaque']
            else 'binding_gaps' if guard['has_binding_gap'] else 'stateful' if guard['has_stateful'] else 'modeled')
        row = {'id': _identifier('output_context_', inventory.snapshot['id'], source['instruction_id']),
            'condition_output_id': source['id'], 'instruction_id': source['instruction_id'],
            'rung_id': source['rung_id'], 'opcode': source['opcode'], 'action': source['action'],
            'target_operand_id': source['target_operand_id'], 'target_address_id': target_address,
            'target_status': target_status, 'guard_id': source['guard_id'], 'guard_status': source['guard_status'],
            'context_status': context_status, 'has_branch': guard['has_branch'], 'has_stateful': guard['has_stateful'],
            'has_opaque': guard['has_opaque'], 'has_binding_gap': guard['has_binding_gap'],
            'has_namespace_gap': namespace_gap}
        budget.retain(row)
        outputs.append(row)
        outputs_by_rung[row['rung_id']].append(row['id'])
        if target_address is not None:
            outputs_by_address[target_address].append(row['id'])
        c['outputs_by_opcode'][row['opcode']] += 1
        c['targets_by_status'][target_status] += 1
        c['contexts_by_status'][context_status] += 1
        c['guard_statuses'][row['guard_status']] += 1
        c['actions_by_status']['unresolved' if row['action'] == 'unresolved' else 'recognized'] += 1
        c['outputs_with_branches'] += int(row['has_branch'])
        c['outputs_with_stateful_conditions'] += int(row['has_stateful'])
    for source in relationships.addresses:
        if source['id'] not in outputs_by_address:
            continue
        row = {'id': source['id'], 'target_id': source['target_id'],
            'endpoint_kind': _ENDPOINTS.get(entities[source['target_id']].kind, 'other'),
            'output_ids': outputs_by_address[source['id']], 'rejected_operand_ids': [],
            'rejected_expression_use_ids': [], 'noncoil_writer_operand_ids': []}
        for role in sorted(ROLES):
            accepted = []
            for identifier in source[f'{role}_operand_ids']:
                operand = operands[identifier]
                if binding_ok(operand):
                    accepted.append(identifier)
                    if role in {'write', 'read_write'} and operand['instruction_id'] not in coil_instructions:
                        row['noncoil_writer_operand_ids'].append(identifier)
                    c['accepted_operands_by_role'][role] += 1
                else:
                    row['rejected_operand_ids'].append(identifier)
                    c['rejected_operands_by_role'][role] += 1
            row[f'{role}_operand_ids'] = accepted
        row['expression_use_ids'] = []
        for identifier in source['expression_use_ids']:
            accepted = binding_ok(expression_uses[identifier])
            row['expression_use_ids' if accepted else 'rejected_expression_use_ids'].append(identifier)
            c['accepted_expression_uses' if accepted else 'rejected_expression_uses'] += 1
        has_reader = bool(row['read_operand_ids'] or row['read_write_operand_ids'] or row['expression_use_ids'])
        row['profile'] = 'read_and_write' if has_reader else 'write_only'
        budget.retain(row)
        addresses.append(row)
        c['endpoint_kinds'][row['endpoint_kind']] += 1
        c['address_profiles'][row['profile']] += 1
        c['noncoil_writers_total'] += len(row['noncoil_writer_operand_ids'])
        c['addresses_with_multiple_coils'] += int(len(row['output_ids']) > 1)
        c['addresses_with_noncoil_writers'] += int(bool(row['noncoil_writer_operand_ids']))
        c['addresses_with_unknown_roles'] += int(bool(row['unknown_operand_ids']))
        c['addresses_without_readers'] += int(not has_reader)
        c['addresses_with_namespace_uses'] += int(bool(row['rejected_operand_ids'] or row['rejected_expression_use_ids']))
    for node in conditions.nodes:
        if node['kind'] not in {'predicate', 'stateful_transfer'}:
            continue
        for identifier in node['operand_ids']:
            source_address = address_by_use.get(identifier)
            if source_address is None or source_address['id'] not in outputs_by_address:
                continue
            operand = operands[identifier]
            if operand['role'] not in {'read', 'read_write'}:
                continue
            accepted = binding_ok(operand) and context_ok[node['id']]
            # The source operand is already unique to this node occurrence.
            # Recover rung/instruction through it rather than copying several
            # digest IDs per read. source_address_id is an accepted binding only
            # for status=accepted; rejected rows retain the association as a gap.
            row = {'id': identifier, 'condition_node_id': node['id'], 'source_address_id': source_address['id'],
                'kind': 'predicate' if node['kind'] == 'predicate' else 'ons_storage',
                'status': 'accepted' if accepted else 'namespace_gap'}
            budget.retain(row)
            condition_reads.append(row)
            c['condition_read_kinds'][row['kind']] += 1
            c['condition_read_statuses'][row['status']] += 1
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rung_analysis.candidates:
        if row['category'] in HINT_CATEGORIES and row['basis'] == 'text_hint':
            candidates[row['rung_id']].append(row)
    for rung in inventory.rungs:
        if rung.id not in outputs_by_rung:
            continue
        row = {'id': rung.id, 'output_ids': outputs_by_rung[rung.id],
            'candidate_ids_by_category': {key: [] for key in sorted(HINT_CATEGORIES)},
            'unqualified_candidate_ids_by_category': {key: [] for key in sorted(HINT_CATEGORIES)}}
        for candidate in candidates[rung.id]:
            accepted = rung_ok[rung.id] and all(text_ok.get(identifier, False) for identifier in candidate['evidence_ids'])
            key = 'candidate_ids_by_category' if accepted else 'unqualified_candidate_ids_by_category'
            row[key][candidate['category']].append(candidate['id'])
            c['hints_by_category' if accepted else 'unqualified_hints_by_category'][candidate['category']] += 1
        budget.retain(row)
        rung_contexts.append(row)
        c['rungs_with_hints'] += int(any(row['candidate_ids_by_category'].values()))
        c['rungs_with_unqualified_hints'] += int(any(row['unqualified_candidate_ids_by_category'].values()))
    c.update(outputs_total=len(outputs), output_rungs=len(outputs_by_rung), addresses_total=len(addresses),
             condition_reads_total=len(condition_reads), rung_contexts_total=len(rung_contexts))
    return BooleanOutputContextResult(deepcopy(inventory.snapshot), 'partial' if _partial(c) else 'complete',
                                      outputs, addresses, condition_reads, rung_contexts, c)


def analyze_output_context(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult) -> BooleanOutputContextResult:
    """Authenticate conditions3 and its complete prior chain, then qualify it."""
    try:
        if type(conditions) is not ConditionResult or conditions.schema_version != 3:
            _invalid()
        validate_conditions(snapshot, inventory, references, access, calculations, rung_analysis, relationships, conditions)
        result = _derive(snapshot, inventory, access, rung_analysis, relationships, conditions)
        render_output_context_json(result)
        return result
    except OutputContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_output_context(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, result: BooleanOutputContextResult) -> None:
    try:
        render_output_context_json(result)
        expected = analyze_output_context(snapshot, inventory, references, access, calculations,
                                          rung_analysis, relationships, conditions)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except OutputContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_output_context_json(result: BooleanOutputContextResult) -> str:
    """Bound native containers and serialization; source authentication is separate."""
    try:
        if type(result) is not BooleanOutputContextResult or vars(result).keys() != set(BooleanOutputContextResult.__dataclass_fields__):
            _invalid()
        remaining = MAX_OUTPUT_CONTEXT_BYTES
        frames = [(iter((vars(result),)), None)]
        active = set()
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
                if identifier in active or len(value) > MAX_OUTPUT_CONTEXT_RECORDS:
                    _invalid()
                active.add(identifier)
                if type(value) is dict:
                    if any(type(key) is not str for key in value):
                        _invalid()
                    remaining -= sum(len(key.encode('utf-8')) for key in value)
                    frames.append((iter(value.values()), identifier))
                else:
                    frames.append((iter(value), identifier))
            elif type(value) is str:
                remaining -= len(value.encode('utf-8'))
            elif type(value) not in (int, bool, type(None)):
                _invalid()
            if remaining < 0:
                _invalid()
        if sum(len(getattr(result, key)) for key in ('outputs', 'addresses', 'condition_reads', 'rung_contexts')) > MAX_OUTPUT_CONTEXT_RECORDS:
            _invalid()
        output, size = StringIO(), 1
        for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).iterencode(vars(result)):
            size += len(chunk.encode('utf-8'))
            if size > MAX_OUTPUT_CONTEXT_JSON_BYTES:
                _invalid()
            output.write(chunk)
        return output.getvalue() + '\n'
    except OutputContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
