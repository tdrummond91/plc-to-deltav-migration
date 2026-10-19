"""Bounded source-order calculation observations inside isolated ladder regions.

A link records an earlier exact-address write in the same source region. It is
not a reaching definition, write guard, executed path, or numerical data flow.
Forks, joins, and all non-catalogued instructions discard remembered writers.
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
from .conditions import ConditionResult, PREDICATE_OPCODES, validate_conditions
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult, _strict_record_match
from .relationships import RelationshipResult, _identifier
from .rung_analysis import RungAnalysisResult
from .source import _read_nodes
from .tag_data import _namespace

MAX_CALCULATION_PATH_RECORDS = 250_000
MAX_CALCULATION_PATH_BYTES = 8 * 1024 * 1024
MAX_CALCULATION_PATH_JSON_BYTES = 8 * 1024 * 1024
OPCODES = frozenset('MOV CLR ADD SUB MUL DIV ABS LN SQR CPT'.split())
GAP_REASONS = frozenset({'access_not_classified', 'unresolved_operand', 'invalid_identity',
    'namespace_gap', 'unsupported_expression', 'system_flag', 'condition_unavailable'})
BARRIER_REASONS = GAP_REASONS | {'other_instruction'}
CONDITION_QUALITIES = frozenset({'modeled', 'binding_gaps', 'opaque', 'stateful', 'unavailable'})
REGION_STARTS = frozenset({'rung_entry', 'branch_entry', 'branch_join', 'barrier'})
REGION_ENDS = frozenset({'rung_end', 'branch_fork', 'branch_end', 'barrier', 'block_gap'})
COUNT_MAPS = {'blocks_by_opcode': OPCODES, 'blocks_by_status': frozenset({'eligible', 'gap'}),
    'gap_reasons': GAP_REASONS, 'barriers_by_reason': BARRIER_REASONS,
    'condition_quality': CONDITION_QUALITIES, 'links_by_kind': frozenset({'operand', 'expression'}),
    'region_starts': REGION_STARTS, 'region_ends': REGION_ENDS}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | frozenset({
    'source_rungs', 'source_instructions', 'source_operands', 'source_expression_uses',
    'unparsed_rungs', 'selected_rungs', 'occurrences_total', 'regions_total', 'region_blocks_total',
    'branched_blocks', 'branched_regions', 'links_total', 'linked_blocks', 'linked_regions',
    'input_operands_total', 'literal_input_operands', 'expression_input_operands',
    'address_input_operands', 'unresolved_input_operands', 'expression_uses_total',
    'eligible_read_inputs', 'eligible_expression_uses', 'preserved_predicates',
    'barrier_instructions', 'overlap_invalidations'})
CALCULATION_PATH_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'calculation-paths-1',
    'analysis_scope': 'isolated_region_source_order', 'address_identity': 'exact_expanded_spelling',
    'execution_analysis': 'not_implemented', 'reaching_definitions': 'not_implemented',
    'numeric_analysis': 'not_implemented', 'condition_usage': 'incoming_context_not_write_guard',
}
_SEMANTIC_ATTRIBUTES = frozenset({'Name', 'TagType', 'AliasFor', 'DataType', 'Dimensions', 'Type'})


class CalculationPathError(ValueError):
    """Fixed source-free validation and resource rejection."""


def _invalid() -> None:
    raise CalculationPathError('Calculation path evidence is inconsistent or exceeds its limits.') from None


@dataclass(frozen=True)
class CalculationPathResult:
    snapshot: dict[str, str | int]
    status: str
    occurrences: list[dict[str, Any]]
    regions: list[dict[str, Any]]
    links: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'calculation-paths-1'
    analysis_scope: str = 'isolated_region_source_order'
    address_identity: str = 'exact_expanded_spelling'
    execution_analysis: str = 'not_implemented'
    reaching_definitions: str = 'not_implemented'
    numeric_analysis: str = 'not_implemented'
    condition_usage: str = 'incoming_context_not_write_guard'

    def to_dict(self) -> dict[str, Any]:
        render_calculation_paths_json(self)
        return deepcopy(vars(self))


class _Budget:
    def __init__(self) -> None:
        self.records = self.bytes = 0

    def retain(self, row: dict[str, Any]) -> None:
        self.records += 1
        self.bytes += len(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self.records > MAX_CALCULATION_PATH_RECORDS or self.bytes > MAX_CALCULATION_PATH_BYTES:
            _invalid()


def _provenance(snapshot: SourceSnapshot, inventory: InventoryResult):
    nodes = _read_nodes(snapshot.data)
    namespace = _namespace(nodes[0].expanded_name)
    supported = {}
    for node in nodes:
        supported[node.locator] = (_namespace(node.expanded_name) == namespace
            and not any('}' in key and key.rsplit('}', 1)[-1] in _SEMANTIC_ATTRIBUTES
                        for key in node.expanded_attributes)
            and (node.parent is None or supported[nodes[node.parent].locator]))
    by_locator = {node.locator: node for node in nodes}
    entities = {row.id: row for row in inventory.entities}
    rung_ok = {rung.id: supported[rung.locator] and all(
        supported[nodes[index].locator] for index in by_locator[rung.locator].children
        if nodes[index].name == 'Text') for rung in inventory.rungs}

    def binding_ok(row: dict[str, Any]) -> bool:
        return rung_ok[row['rung_id']] and all(identifier in entities
            and supported[entities[identifier].locator]
            for identifier in [row['symbol_id'], *row['alias_chain'], row['target_id']])

    return rung_ok, binding_ok


def _partial(c: dict[str, Any]) -> bool:
    return bool(c['unparsed_rungs'] or c['blocks_by_status']['gap']
                or any(c['condition_quality'][key] for key in CONDITION_QUALITIES - {'modeled'}))


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, access: AccessResult,
            relationships: RelationshipResult, conditions: ConditionResult) -> CalculationPathResult:
    if any(len(rows) > MAX_CALCULATION_PATH_RECORDS for rows in
           (inventory.rungs, access.instructions, access.operands, access.expression_uses, conditions.nodes)):
        _invalid()
    budget = _Budget()
    rung_ok, binding_ok = _provenance(snapshot, inventory)
    instructions = {row['id']: row for row in access.instructions}
    operands = {row['id']: row for row in access.operands}
    uses_by_instruction: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in access.expression_uses:
        uses_by_instruction[row['instruction_id']].append(row)
    address_by_use = {identifier: row for row in relationships.addresses
                      for role in ('read', 'write', 'read_write', 'unknown')
                      for identifier in row[f'{role}_operand_ids']}
    address_by_use.update({identifier: row for row in relationships.addresses
                           for identifier in row['expression_use_ids']})
    nodes = {row['id']: row for row in conditions.nodes}
    incoming = {row['instruction_id']: row['child_ids'][0] for row in conditions.nodes
                if row['kind'] in {'pass_through', 'opaque_transfer'} and row['instruction_id']
                and row['child_ids']}
    # Namespace-confounded prior transfers/predicates must not silently become
    # supported incoming context merely because the lexical binder found a root.
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
             source_operands=len(access.operands), source_expression_uses=len(access.expression_uses))
    occurrences, regions, links = [], [], []
    linked_blocks, linked_regions, selected_rungs = set(), set(), set()

    def reason_for(record: dict[str, Any], slots: list[dict[str, Any]],
                   uses: list[dict[str, Any]]) -> str | None:
        if record['status'] != 'classified':
            return 'access_not_classified'
        if not rung_ok[record['rung_id']]:
            return 'namespace_gap'
        for row in slots:
            if row['role'] == 'expression_read':
                if row['binding_status'] != 'parsed_expression':
                    return 'unsupported_expression'
                continue
            if row['role'] not in {'read', 'write'}:
                return 'unresolved_operand'
            if row['binding_status'] == 'system_flag':
                return 'system_flag'
            if row['binding_status'] == 'root_bound':
                if not binding_ok(row):
                    return 'namespace_gap'
                if row['id'] not in address_by_use:
                    return 'invalid_identity'
            elif row['role'] != 'read' or row['binding_status'] != 'literal':
                return 'unresolved_operand'
        for row in uses:
            if row['binding_status'] != 'root_bound':
                return 'unresolved_operand'
            if not binding_ok(row):
                return 'namespace_gap'
            if row['id'] not in address_by_use:
                return 'invalid_identity'
        return None

    for rung in inventory.rungs:
        if rung.parse_status != 'parsed':
            c['unparsed_rungs'] += 1
            continue
        latest: dict[str, tuple[str, str, str, str | None]] = {}
        active = None
        pending_start = 'rung_entry'

        def close(end: str, start: str) -> None:
            nonlocal active, pending_start
            if active is not None:
                active['end_reason'] = end
                budget.retain(active)
                regions.append(active)
                c['region_starts'][active['start_reason']] += 1
                c['region_ends'][end] += 1
                c['branched_regions'] += int(active['branch_depth'] > 0)
                active = None
            latest.clear()
            pending_start = start

        # Flat events visit each AST node once; no execution paths are expanded.
        stack = [('visit', rung.structure, 0)]
        while stack:
            event, tree, depth = stack.pop()
            if event == 'boundary':
                end, start = tree
                close(end, start)
                continue
            kind = tree['kind']
            if kind == 'sequence':
                stack.extend(('visit', item, depth) for item in reversed(tree['items']))
                continue
            if kind == 'branch':
                close('branch_fork', 'branch_entry')
                stack.append(('boundary', ('branch_end', 'branch_join'), depth))
                for leg in reversed(tree['legs']):
                    stack.append(('boundary', ('branch_end', 'branch_entry'), depth + 1))
                    stack.append(('visit', leg, depth + 1))
                continue
            identifier = tree['instruction_id']
            record = instructions[identifier]
            opcode = record['opcode'].upper()
            slots = [operands[value] for value in record['operand_ids']]
            uses = uses_by_instruction[identifier]
            reason = reason_for(record, slots, uses)
            if opcode not in OPCODES:
                if opcode in PREDICATE_OPCODES and reason is None and all(row['role'] == 'read' for row in slots):
                    c['preserved_predicates'] += 1
                    continue
                reason = reason if opcode in PREDICATE_OPCODES else 'other_instruction'
                c['barrier_instructions'] += 1
                c['barriers_by_reason'][reason] += 1
                close('barrier', 'barrier')
                continue
            context = incoming.get(identifier)
            quality = 'unavailable'
            if context is not None and context_ok[context]:
                node = nodes[context]
                quality = ('opaque' if node['has_opaque'] else 'binding_gaps' if node['has_binding_gap']
                           else 'stateful' if node['has_stateful'] else 'modeled')
            else:
                context = None
                reason = reason or ('namespace_gap' if incoming.get(identifier) else 'condition_unavailable')
            if reason:
                close('barrier', pending_start if active is None else 'barrier')
                c['barrier_instructions'] += 1
                c['barriers_by_reason'][reason] += 1
                c['gap_reasons'][reason] += 1
            if active is None:
                active = {'id': _identifier('calculation_region_', inventory.snapshot['id'], identifier),
                    'rung_id': rung.id, 'scope_id': rung.scope_id, 'branch_depth': depth,
                    'start_reason': pending_start, 'end_reason': None, 'blocks_count': 0}
            active['blocks_count'] += 1
            input_rows = [row for row in slots if row['role'] in {'read', 'expression_read'}]
            destination = next((row for row in slots if row['role'] == 'write'), None)
            destination_address = (address_by_use.get(destination['id']) if destination is not None
                and destination['binding_status'] == 'root_bound' and binding_ok(destination) else None)
            row = {'id': identifier, 'rung_id': rung.id, 'scope_id': rung.scope_id, 'opcode': opcode,
                'status': 'gap' if reason else 'eligible', 'gap_reason': reason,
                'region_id': active['id'], 'branch_depth': depth,
                'input_operand_ids': [item['id'] for item in input_rows],
                'expression_use_ids': [item['id'] for item in uses],
                'destination_operand_id': destination['id'] if destination else None,
                'destination_address_id': destination_address['id'] if destination_address else None,
                'incoming_condition_id': context, 'condition_quality': quality}
            budget.retain(row)
            occurrences.append(row)
            selected_rungs.add(rung.id)
            c['blocks_by_opcode'][opcode] += 1
            c['blocks_by_status'][row['status']] += 1
            c['condition_quality'][quality] += 1
            c['branched_blocks'] += int(depth > 0)
            c['input_operands_total'] += len(input_rows)
            c['expression_uses_total'] += len(uses)
            for item in input_rows:
                binding = item['binding_status']
                bucket = ('expression' if item['role'] == 'expression_read' else
                          'literal' if binding == 'literal' else 'address' if binding == 'root_bound'
                          and item['id'] in address_by_use and binding_ok(item) else 'unresolved')
                c[f'{bucket}_input_operands'] += 1
            if reason:
                close('block_gap', 'barrier')
                continue
            reads = [(item, 'operand') for item in input_rows if item['role'] == 'read'
                     and item['binding_status'] == 'root_bound']
            c['eligible_read_inputs'] += len(reads)
            c['eligible_expression_uses'] += len(uses)
            reads.extend((item, 'expression') for item in uses)
            for item, read_kind in reads:
                address = address_by_use[item['id']]
                previous = latest.get(address['target_id'])
                if previous is None or previous[0] != address['id']:
                    continue
                link = {'id': _identifier('calculation_path_link_', inventory.snapshot['id'], previous[2], item['id']),
                    'region_id': active['id'], 'producer_instruction_id': previous[1],
                    'consumer_instruction_id': identifier, 'address_id': address['id'],
                    'write_operand_id': previous[2], 'read_id': item['id'], 'read_kind': read_kind,
                    'producer_condition_id': previous[3], 'consumer_condition_id': context}
                budget.retain(link)
                links.append(link)
                c['links_by_kind'][read_kind] += 1
                linked_blocks.add(identifier)
                linked_regions.add(active['id'])
            # This update deliberately follows every read, including repeated
            # CPT leaves. A different exact suffix kills the whole root history.
            address = destination_address
            previous = latest.get(address['target_id'])
            c['overlap_invalidations'] += int(previous is not None and previous[0] != address['id'])
            latest[address['target_id']] = (address['id'], identifier, destination['id'], context)
        close('rung_end', 'rung_entry')
    c.update(occurrences_total=len(occurrences), regions_total=len(regions), links_total=len(links),
        region_blocks_total=sum(row['blocks_count'] for row in regions), selected_rungs=len(selected_rungs),
        linked_blocks=len(linked_blocks), linked_regions=len(linked_regions))
    return CalculationPathResult(dict(inventory.snapshot), 'partial' if _partial(c) else 'complete',
                                 occurrences, regions, links, c)


def analyze_calculation_paths(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult) -> CalculationPathResult:
    """Authenticate conditions3 and its entire prior chain before deriving links."""
    try:
        if type(conditions) is not ConditionResult or conditions.schema_version not in (3, 4, 5, 6):
            _invalid()
        validate_conditions(snapshot, inventory, references, access, calculations, rung_analysis,
                            relationships, conditions)
        result = _derive(snapshot, inventory, access, relationships, conditions)
        render_calculation_paths_json(result)
        return result
    except CalculationPathError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_calculation_paths(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, access: AccessResult, calculations: CalculationResult,
        rung_analysis: RungAnalysisResult, relationships: RelationshipResult,
        conditions: ConditionResult, result: CalculationPathResult) -> None:
    try:
        render_calculation_paths_json(result)
        expected = analyze_calculation_paths(snapshot, inventory, references, access, calculations,
                                             rung_analysis, relationships, conditions)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except CalculationPathError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_calculation_paths_json(result: CalculationPathResult) -> str:
    """Serialize bounded native containers; source authentication is separate."""
    try:
        if type(result) is not CalculationPathResult or vars(result).keys() != set(CalculationPathResult.__dataclass_fields__):
            _invalid()
        remaining = MAX_CALCULATION_PATH_BYTES
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
                if identifier in active or len(value) > MAX_CALCULATION_PATH_RECORDS:
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
            elif type(value) not in (int, type(None)):
                _invalid()
            if remaining < 0:
                _invalid()
        if sum(len(getattr(result, key)) for key in ('occurrences', 'regions', 'links')) > MAX_CALCULATION_PATH_RECORDS:
            _invalid()
        output, size = StringIO(), 1
        for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).iterencode(vars(result)):
            size += len(chunk.encode('utf-8'))
            if size > MAX_CALCULATION_PATH_JSON_BYTES:
                _invalid()
            output.write(chunk)
        return output.getvalue() + '\n'
    except CalculationPathError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
