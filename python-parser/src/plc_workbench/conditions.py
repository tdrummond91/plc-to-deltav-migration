"""Bounded, source-relative Boolean conditions for selected normal-scan coils.

The graph preserves evaluation entry, instruction occurrences, branch leg order,
and opaque transfers. It neither simulates a scan nor establishes physical I/O,
alarm purpose, member types, initialization, or process behavior.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
from io import StringIO
from itertools import chain
import json
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult, _strict_record_match
from .relationships import RelationshipResult, validate_relationships
from .rung_analysis import RungAnalysisResult

MAX_CONDITION_BYTES = 32 * 1024 * 1024
MAX_RECORDS = 250_000
MAX_EVIDENCE_IDS = 2_000_000
PREDICATE_OPCODES = frozenset('XIC XIO EQU NEQ LES LEQ GRT GEQ LIM'.split())
OUTPUT_ACTIONS = {'OTE': 'assign_condition', 'OTL': 'set_if_true', 'OTU': 'clear_if_true'}
# Instruction-specific normal-scan LD execution tables, cited in
# CONDITION_TRANSFER_REVIEW.md. Operand access alone is never sufficient to
# admit an opcode. Stateful effects and faults are outside this transfer model.
PASSTHROUGH_OPCODES = frozenset('ABS ADD CLR COP CPS CPT CTU DIV LN MOV MUL OSF RES RTO SQR SUB TON'.split())
CONDITION_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'condition-analysis-1',
    'analysis_scope': 'local_rung_boolean_conditions', 'execution_analysis': 'not_implemented',
    'engineering_review': 'unreviewed', 'evaluation_scope': 'normal_scan_only',
}
COUNT_MAPS = {
    'node_kinds': frozenset({'entry', 'predicate', 'all', 'any', 'opaque_transfer'}),
    'output_opcodes': frozenset(OUTPUT_ACTIONS), 'predicate_opcodes': PREDICATE_OPCODES,
    'guard_statuses': frozenset({'modeled', 'binding_gaps', 'opaque'}),
    'action_statuses': frozenset({'recognized', 'unresolved'}),
    'target_statuses': frozenset({'exact_address', 'identity_gap', 'unbound', 'signature_unresolved'}),
    'rung_statuses': frozenset({'parsed', 'unparsed'}),
    'opaque_reasons': frozenset({'unsupported_condition_behavior', 'signature_unresolved'}),
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | {
    'source_rungs', 'source_instructions', 'source_operands', 'expression_uses',
    'nodes_total', 'outputs_total', 'rungs_with_outputs', 'output_addresses',
    'branch_joins', 'branch_legs', 'binding_gap_predicates', 'outputs_with_branches',
}


def condition_constants(schema_version: int) -> dict[str, Any]:
    if type(schema_version) is not int or schema_version not in (1, 2):
        _invalid()
    return {**CONDITION_CONSTANTS, 'schema_version': schema_version,
            'analyzer_version': f'condition-analysis-{schema_version}'}


def count_maps(schema_version: int) -> dict[str, frozenset[str]]:
    condition_constants(schema_version)
    if schema_version == 1:
        return dict(COUNT_MAPS)
    return {**COUNT_MAPS, 'node_kinds': COUNT_MAPS['node_kinds'] | {'pass_through'},
            'passthrough_opcodes': PASSTHROUGH_OPCODES}


def coverage_keys(schema_version: int) -> frozenset[str]:
    return frozenset(COVERAGE_KEYS | count_maps(schema_version).keys())


class ConditionError(ValueError):
    """Source-free validation or resource rejection."""


def _invalid() -> None:
    raise ConditionError('Condition evidence does not match the source evidence.')


def _limit() -> None:
    raise ConditionError('Condition evidence exceeds its evidence limits.')


@dataclass(frozen=True)
class ConditionResult:
    snapshot: dict[str, str | int]
    status: str
    nodes: list[dict[str, Any]]
    outputs: list[dict[str, Any]]
    rungs: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'condition-analysis-1'
    analysis_scope: str = 'local_rung_boolean_conditions'
    execution_analysis: str = 'not_implemented'
    engineering_review: str = 'unreviewed'
    evaluation_scope: str = 'normal_scan_only'

    def to_dict(self) -> dict[str, Any]:
        render_conditions_json(self)
        return deepcopy(vars(self))


class _Budget:
    def __init__(self) -> None:
        self.bytes = self.ids = 0

    def record(self, record: dict[str, Any]) -> None:
        self.bytes += len(json.dumps(record, ensure_ascii=True, separators=(',', ':'))) + 1
        self.ids += sum(len(value) if type(value) is list else int(value is not None)
                        for key, value in record.items()
                        if key == 'id' or key.endswith('_id') or key.endswith('_ids'))
        if self.bytes > MAX_CONDITION_BYTES or self.ids > MAX_EVIDENCE_IDS:
            _limit()


def _identifier(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode('utf-8'))
        digest.update(b'\0')
    return prefix + digest.hexdigest()


def _derive(inventory: InventoryResult, access: AccessResult,
            relationships: RelationshipResult, *, schema_version: int = 1) -> ConditionResult:
    constants = condition_constants(schema_version)
    if max(len(inventory.rungs), len(access.instructions), len(access.operands),
           len(access.expression_uses)) > MAX_RECORDS:
        _limit()
    instructions = {row['id']: row for row in access.instructions}
    operands = {row['id']: row for row in access.operands}
    source_instructions = {row.id: row for rung in inventory.rungs for row in rung.instructions}
    addresses = {identifier: address['id'] for address in relationships.addresses
                 for role in ('read', 'write', 'read_write', 'unknown')
                 for identifier in address[f'{role}_operand_ids']}
    identity_gaps = {row['id'] for row in relationships.identity_gaps if row['kind'] == 'operand'}
    maps = count_maps(schema_version)
    coverage = {key: dict.fromkeys(sorted(vocabulary), 0) for key, vocabulary in maps.items()}
    coverage.update(dict.fromkeys(sorted(coverage_keys(schema_version) - maps.keys()), 0))
    coverage.update(source_rungs=len(inventory.rungs), source_instructions=len(access.instructions),
                    source_operands=len(access.operands), expression_uses=len(access.expression_uses))
    nodes: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    rungs: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    target_addresses: set[str] = set()
    budget = _Budget()

    def node(rung_id: str, kind: str, child_ids: list[str], *, instruction_id: str | None = None,
             operand_ids: list[str] | None = None, reason: str | None = None,
             binding_gap: bool = False) -> str:
        if len(nodes) >= MAX_RECORDS:
            _limit()
        identifier = _identifier('condition_node_', inventory.snapshot['id'], rung_id, str(len(nodes)), kind)
        row = {'id': identifier, 'rung_id': rung_id, 'kind': kind, 'instruction_id': instruction_id,
               'child_ids': child_ids, 'operand_ids': list(operand_ids or []), 'reason': reason,
               'has_opaque': kind == 'opaque_transfer' or any(by_id[c]['has_opaque'] for c in child_ids),
               'has_binding_gap': binding_gap or any(by_id[c]['has_binding_gap'] for c in child_ids),
               'has_branch': kind == 'any' or any(by_id[c]['has_branch'] for c in child_ids)}
        budget.record(row)
        nodes.append(row)
        by_id[identifier] = row
        coverage['node_kinds'][kind] += 1
        if kind == 'opaque_transfer':
            coverage['opaque_reasons'][reason] += 1
        if kind == 'any':
            coverage['branch_joins'] += 1
            coverage['branch_legs'] += len(child_ids)
        return identifier

    def instruction(rung_id: str, instruction_id: str, incoming: str, output_ids: list[str]) -> str:
        record = instructions[instruction_id]
        opcode = source_instructions[instruction_id].opcode.upper()
        operand_ids = record['operand_ids']
        classified = record['status'] == 'classified'
        if opcode in PREDICATE_OPCODES and classified:
            gap = any(identifier not in addresses and operands[identifier]['binding_status'] not in {'literal', 'system_flag'}
                      for identifier in operand_ids)
            predicate = node(rung_id, 'predicate', [], instruction_id=instruction_id,
                             operand_ids=operand_ids, binding_gap=gap)
            coverage['predicate_opcodes'][opcode] += 1
            coverage['binding_gap_predicates'] += int(gap)
            return node(rung_id, 'all', [incoming, predicate])
        if opcode in OUTPUT_ACTIONS:
            if len(outputs) >= MAX_RECORDS:
                _limit()
            target = operand_ids[0] if classified else None
            address = addresses.get(target)
            target_status = ('signature_unresolved' if not classified else 'exact_address' if address
                             else 'identity_gap' if target in identity_gaps else 'unbound')
            guard = by_id[incoming]
            guard_status = 'opaque' if guard['has_opaque'] else 'binding_gaps' if guard['has_binding_gap'] else 'modeled'
            identifier = _identifier('condition_output_', inventory.snapshot['id'], instruction_id)
            row = {'id': identifier, 'instruction_id': instruction_id, 'rung_id': rung_id,
                   'opcode': opcode, 'action': OUTPUT_ACTIONS[opcode] if classified else 'unresolved',
                   'guard_id': incoming, 'guard_status': guard_status, 'target_operand_id': target,
                   'target_address_id': address, 'target_status': target_status}
            budget.record(row)
            outputs.append(row)
            output_ids.append(identifier)
            coverage['output_opcodes'][opcode] += 1
            coverage['guard_statuses'][guard_status] += 1
            coverage['action_statuses']['recognized' if classified else 'unresolved'] += 1
            coverage['target_statuses'][target_status] += 1
            # Count guards containing a completed ANY join, not every coil
            # located inside a branch leg before that leg rejoins its peers.
            coverage['outputs_with_branches'] += int(guard['has_branch'])
            if address:
                target_addresses.add(address)
            # These three catalogued normal-scan coil instructions pass the
            # incoming condition through. Their destination actions differ.
            if classified:
                return incoming
        if schema_version == 2 and opcode in PASSTHROUGH_OPCODES and classified:
            coverage['passthrough_opcodes'][opcode] += 1
            # Keep the occurrence even though the Boolean transfer is identity.
            # Data binding gaps do not change that documented transfer. These
            # slots still retain their independent access/binding evidence.
            return node(rung_id, 'pass_through', [incoming], instruction_id=instruction_id,
                        operand_ids=operand_ids, reason='documented_normal_scan_passthrough')
        reason = ('signature_unresolved' if opcode in PREDICATE_OPCODES or opcode in OUTPUT_ACTIONS
                  or (schema_version == 2 and opcode in PASSTHROUGH_OPCODES)
                  else 'unsupported_condition_behavior')
        return node(rung_id, 'opaque_transfer', [incoming], instruction_id=instruction_id,
                    operand_ids=operand_ids, reason=reason)

    for rung in inventory.rungs:
        parsed = rung.parse_status == 'parsed'
        output_ids: list[str] = []
        entry = node(rung.id, 'entry', []) if parsed else None
        exit_id = entry
        if parsed:
            # Explicit continuations avoid recursive calls, expanded Boolean
            # formulas, descendant lists, and repeated prefix copying.
            stack: list[tuple[Any, ...]] = [('visit', rung.structure, entry)]
            values: list[str] = []
            while stack:
                task = stack.pop()
                event = task[0]
                if event == 'visit':
                    tree, incoming = task[1:]
                    if tree['kind'] == 'instruction':
                        values.append(instruction(rung.id, tree['instruction_id'], incoming, output_ids))
                    elif tree['kind'] == 'sequence':
                        stack.append(('sequence', tree['items'], 0, incoming))
                    else:
                        legs = tree['legs']
                        stack.append(('join', len(legs)))
                        stack.extend(('visit', leg, incoming) for leg in reversed(legs))
                elif event == 'sequence':
                    items, index, incoming = task[1:]
                    if index == len(items):
                        values.append(incoming)
                    else:
                        stack.append(('next', items, index + 1))
                        stack.append(('visit', items[index], incoming))
                elif event == 'next':
                    stack.append(('sequence', task[1], task[2], values.pop()))
                else:
                    count = task[1]
                    children = values[-count:] if count else []
                    if count:
                        del values[-count:]
                    values.append(node(rung.id, 'any', children))
            exit_id = values.pop()
        row = {'id': rung.id, 'status': 'parsed' if parsed else 'unparsed',
               'entry_id': entry, 'exit_id': exit_id, 'output_ids': output_ids}
        budget.record(row)
        rungs.append(row)
        coverage['rung_statuses'][row['status']] += 1
        coverage['rungs_with_outputs'] += int(bool(output_ids))
    coverage.update(nodes_total=len(nodes), outputs_total=len(outputs), output_addresses=len(target_addresses))
    partial = bool(coverage['rung_statuses']['unparsed'] or coverage['node_kinds']['opaque_transfer']
                   or coverage['binding_gap_predicates']
                   or len(outputs) != coverage['target_statuses']['exact_address'])
    return ConditionResult(deepcopy(inventory.snapshot), 'partial' if partial else 'complete',
                           nodes, outputs, rungs, coverage, **constants)


def analyze_conditions(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                       access: AccessResult, calculations: CalculationResult,
                       rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
                       *, schema_version: int = 1) -> ConditionResult:
    """Authenticate every prior companion before deriving bounded conditions."""
    try:
        validate_relationships(snapshot, inventory, references, access, calculations, rung_analysis, relationships)
        result = _derive(inventory, access, relationships, schema_version=schema_version)
        render_conditions_json(result)
        return result
    except ConditionError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_conditions(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                        access: AccessResult, calculations: CalculationResult,
                        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
                        result: ConditionResult) -> None:
    try:
        if type(result) is not ConditionResult:
            _invalid()
        render_conditions_json(result)
        expected = analyze_conditions(snapshot, inventory, references, access, calculations, rung_analysis,
                                      relationships, schema_version=result.schema_version)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except ConditionError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_conditions_json(result: ConditionResult) -> str:
    """Serialize only bounded native containers; authentication is separate."""
    try:
        if type(result) is not ConditionResult or vars(result).keys() != set(ConditionResult.__dataclass_fields__):
            _invalid()
        payload = vars(result)
        remaining = MAX_CONDITION_BYTES
        frames: list[tuple[Any, int | None]] = [(iter((payload,)), None)]
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
            if type(value) is str:
                remaining -= len(value)
            elif type(value) in {dict, list}:
                if len(value) > MAX_RECORDS or id(value) in active or len(frames) > 12:
                    _limit()
                if type(value) is dict and any(type(key) is not str for key in value):
                    _invalid()
                active.add(id(value))
                children = chain(value.keys(), value.values()) if type(value) is dict else value
                frames.append((iter(children), id(value)))
            elif type(value) not in {int, bool, type(None)}:
                _invalid()
            if remaining < 0:
                _limit()
        output, size = StringIO(), 0
        for chunk in json.JSONEncoder(ensure_ascii=True, sort_keys=True, indent=2).iterencode(payload):
            size += len(chunk)
            if size + 1 > MAX_CONDITION_BYTES:
                _limit()
            output.write(chunk)
        return output.getvalue() + '\n'
    except ConditionError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
