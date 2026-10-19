"""Exact address spelling reuse and bounded local source-order observations.

These records do not establish runtime reaching definitions, physical channels,
member overlap, type compatibility, or equivalent process behavior. They link
authenticated existing evidence without changing its binding dispositions.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from io import StringIO
from itertools import chain
import json
from typing import Any

from .access import AccessResult, INDEXED_ROLES
from .calculations import CalculationResult
from .models import InventoryResult, SourceSnapshot
from .references import (
    MAX_ADDRESS_LENGTH, MAX_EXPANDED_EVIDENCE_CHARS, ReferenceResult, _ADDRESS,
    _strict_record_match,
)
from .rung_analysis import RungAnalysisResult, validate_rung_analysis

MAX_RELATIONSHIP_BYTES = 32 * 1024 * 1024
MAX_RECORDS = 250_000
MAX_EVIDENCE_IDS = 2_000_000
ADDRESS_PROFILES = frozenset({'read_and_write', 'read_only', 'write_only', 'unknown_only'})
PATTERN_SKIPS = frozenset({'unparsed', 'empty', 'unknown_instruction', 'unknown_role',
                           'unresolved_address', 'invalid_expanded_suffix', 'unsupported_expression'})
LOCAL_BARRIERS = frozenset({'opcode_not_eligible', 'access_not_classified', 'invalid_identity',
                            'unresolved_operand', 'unsupported_expression', 'system_flag'})
LINK_KINDS = frozenset({'operand', 'expression'})
RELATIONSHIP_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'relationship-analysis-1',
    'analysis_scope': 'exact_address_reuse_and_local_order',
    'execution_analysis': 'not_implemented', 'engineering_review': 'unreviewed',
    'address_identity': 'exact_expanded_spelling', 'overlap_analysis': 'not_implemented',
}
COUNT_MAPS = {
    'indexed_operands_by_role': INDEXED_ROLES, 'rejected_operands_by_role': INDEXED_ROLES,
    'address_profiles': ADDRESS_PROFILES, 'pattern_skips': PATTERN_SKIPS,
    'local_link_kinds': LINK_KINDS, 'local_barriers': LOCAL_BARRIERS,
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | {
    'source_rungs', 'source_instructions', 'source_operands', 'expression_uses',
    'addresses_total', 'identity_gaps_total', 'indexed_expression_uses', 'rejected_expression_uses',
    'access_gap_operands', 'expression_gap_uses', 'unknown_role_operands',
    'cross_rung_addresses', 'multiple_writer_addresses', 'local_links_total', 'local_link_rungs',
    'eligible_instructions', 'barrier_instructions', 'excluded_branched_instructions',
    'patterns_total', 'patterned_rungs', 'skipped_rungs',
}
_LOCAL_OPCODES = frozenset('MOV CLR ADD SUB MUL DIV ABS LN SQR CPT'.split())


class RelationshipError(ValueError):
    """Source-free evidence validation or resource rejection."""


def _invalid() -> None:
    raise RelationshipError('Relationship evidence does not match the source evidence.')


def _limit() -> None:
    raise RelationshipError('Relationship evidence exceeds its evidence limits.')


@dataclass(frozen=True)
class RelationshipResult:
    snapshot: dict[str, str | int]
    status: str
    addresses: list[dict[str, Any]]
    identity_gaps: list[dict[str, Any]]
    local_links: list[dict[str, Any]]
    patterns: list[dict[str, Any]]
    rung_patterns: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'relationship-analysis-1'
    analysis_scope: str = 'exact_address_reuse_and_local_order'
    execution_analysis: str = 'not_implemented'
    engineering_review: str = 'unreviewed'
    address_identity: str = 'exact_expanded_spelling'
    overlap_analysis: str = 'not_implemented'

    def to_dict(self) -> dict[str, Any]:
        render_relationships_json(self)
        return deepcopy(vars(self))


class _Budget:
    """Charge incremental retained records and ID links before appending them."""

    def __init__(self) -> None:
        self.bytes = self.ids = self.suffixes = 0

    def record(self, row: dict[str, Any]) -> None:
        self.bytes += len(json.dumps(row, ensure_ascii=True, separators=(',', ':'))) + 1
        self._check()

    def identifier(self, identifier: str) -> None:
        self.ids += 1
        self.bytes += len(identifier) + 3
        self._check()

    def suffix(self, suffix: str) -> None:
        self.suffixes += len(suffix)
        self._check()

    def _check(self) -> None:
        if (self.bytes > MAX_RELATIONSHIP_BYTES or self.ids > MAX_EVIDENCE_IDS
                or self.suffixes > MAX_EXPANDED_EVIDENCE_CHARS):
            _limit()


def _identifier(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode('utf-8'))
        digest.update(b'\0')
    return prefix + digest.hexdigest()


def _derive(inventory: InventoryResult, access: AccessResult, calculations: CalculationResult,
            rung_analysis: RungAnalysisResult) -> RelationshipResult:
    if max(len(inventory.rungs), len(access.instructions), len(access.operands),
           len(access.expression_uses), len(calculations.nodes)) > MAX_RECORDS:
        _limit()
    budget = _Budget()
    instructions = {row['id']: row for row in access.instructions}
    operands = {row['id']: row for row in access.operands}
    uses_by_instruction: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for use in access.expression_uses:
        uses_by_instruction[use['instruction_id']].append(use)
    occurrences = {row['id']: row for row in calculations.occurrences}
    nodes = {row['id']: row for row in calculations.nodes}
    dossiers = {row['id']: row for row in rung_analysis.rungs}
    coverage = {key: dict.fromkeys(sorted(vocabulary), 0) for key, vocabulary in COUNT_MAPS.items()}
    coverage.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
    coverage.update(source_rungs=len(inventory.rungs), source_instructions=len(access.instructions),
                    source_operands=len(access.operands), expression_uses=len(access.expression_uses),
                    access_gap_operands=access.coverage['access_gap_operands'],
                    expression_gap_uses=len(access.expression_uses) - access.coverage['expression_uses_by_binding']['root_bound'],
                    unknown_role_operands=access.coverage['operands_by_role']['unknown'])
    addresses: dict[tuple[str, str], dict[str, Any]] = {}
    identity_gaps: list[dict[str, Any]] = []
    address_by_use: dict[str, dict[str, Any]] = {}
    rung_seen: dict[str, set[str]] = defaultdict(set)
    instruction_seen: dict[str, set[str]] = defaultdict(set)
    writers: dict[str, set[str]] = defaultdict(set)

    def index(row: dict[str, Any], kind: str) -> None:
        if row['binding_status'] != 'root_bound':
            return
        role = row['role']
        if kind == 'operand' and role not in INDEXED_ROLES:
            return
        suffix = row['suffix']
        # Alias composition may have passed each individual lexical check yet
        # produced an invalid combined suffix, e.g. a member after a bit index.
        if len(suffix) > MAX_ADDRESS_LENGTH or _ADDRESS.fullmatch('A' + suffix) is None:
            if len(identity_gaps) >= MAX_RECORDS:
                _limit()
            gap = {'id': row['id'], 'kind': kind, 'reason': 'expanded_suffix_invalid'}
            budget.identifier(row['id'])
            budget.record(gap)
            identity_gaps.append(gap)
            if kind == 'operand':
                coverage['rejected_operands_by_role'][role] += 1
            else:
                coverage['rejected_expression_uses'] += 1
            return
        key = (row['target_id'], suffix)
        if key not in addresses:
            if len(addresses) >= MAX_RECORDS:
                _limit()
            identifier = _identifier('relationship_address_', inventory.snapshot['id'], *key)
            address = {'id': identifier, 'target_id': key[0], 'suffix': suffix,
                       **{f'{r}_operand_ids': [] for r in sorted(INDEXED_ROLES)},
                       'expression_use_ids': [], 'rung_ids': [], 'instruction_ids': [], 'profile': 'unknown_only'}
            budget.suffix(suffix)
            budget.identifier(identifier)
            budget.identifier(key[0])
            budget.record(address)
            addresses[key] = address
        address = addresses[key]
        identifier = address['id']
        bucket = f'{role}_operand_ids' if kind == 'operand' else 'expression_use_ids'
        budget.identifier(row['id'])
        address[bucket].append(row['id'])
        address_by_use[row['id']] = address
        for field, seen in (('rung_id', rung_seen), ('instruction_id', instruction_seen)):
            value = row[field]
            if value not in seen[identifier]:
                budget.identifier(value)
                address[field + 's'].append(value)
                seen[identifier].add(value)
        if kind == 'operand':
            coverage['indexed_operands_by_role'][role] += 1
            if role in {'write', 'read_write'}:
                writers[identifier].add(row['instruction_id'])
        else:
            coverage['indexed_expression_uses'] += 1

    # Merge CPT leaves into source slot order rather than appending all leaves
    # after ordinary operands. First occurrence order stays deterministic.
    for rung in inventory.rungs:
        for instruction in rung.instructions:
            for identifier in instructions[instruction.id]['operand_ids']:
                operand = operands[identifier]
                if operand['role'] == 'expression_read':
                    for use in uses_by_instruction[instruction.id]:
                        index(use, 'expression')
                else:
                    index(operand, 'operand')
    for address in addresses.values():
        read = bool(address['read_operand_ids'] or address['read_write_operand_ids'] or address['expression_use_ids'])
        write = bool(address['write_operand_ids'] or address['read_write_operand_ids'])
        address['profile'] = 'read_and_write' if read and write else 'read_only' if read else 'write_only' if write else 'unknown_only'
        coverage['address_profiles'][address['profile']] += 1
        coverage['cross_rung_addresses'] += int(len(address['rung_ids']) > 1)
        coverage['multiple_writer_addresses'] += int(len(writers[address['id']]) > 1)

    local_links: list[dict[str, Any]] = []
    local_link_rungs: set[str] = set()
    for rung in inventory.rungs:
        if dossiers[rung.id]['structure'] == 'branched':
            coverage['excluded_branched_instructions'] += len(rung.instructions)
            continue
        # One remembered writer per root is deliberate: a different member or
        # whole-root write invalidates all prior exact-member observations.
        latest: dict[str, tuple[str, str, str]] = {}
        for instruction in rung.instructions:
            record = instructions[instruction.id]
            slots = [operands[identifier] for identifier in record['operand_ids']]
            uses = uses_by_instruction[instruction.id]
            reason = _local_barrier(instruction.opcode.upper(), record, slots, uses, address_by_use)
            if reason:
                coverage['barrier_instructions'] += 1
                coverage['local_barriers'][reason] += 1
                latest.clear()
                continue
            coverage['eligible_instructions'] += 1
            reads = [(row, 'operand') for row in slots if row['role'] == 'read']
            reads.extend((row, 'expression') for row in uses)
            for row, kind in reads:
                address = address_by_use.get(row['id'])
                if address is None:  # Admitted immediate literal, not an address.
                    continue
                previous = latest.get(address['target_id'])
                if previous is None or previous[0] != address['id']:
                    continue
                if len(local_links) >= MAX_RECORDS:
                    _limit()
                link = {'id': _identifier('relationship_link_', inventory.snapshot['id'], previous[2], row['id']),
                        'rung_id': rung.id, 'producer_instruction_id': previous[1],
                        'consumer_instruction_id': instruction.id, 'address_id': address['id'],
                        'write_operand_id': previous[2], 'read_id': row['id'], 'read_kind': kind}
                for value in link.values():
                    budget.identifier(value)
                budget.record(link)
                local_links.append(link)
                coverage['local_link_kinds'][kind] += 1
                local_link_rungs.add(rung.id)
            # Reads precede the write: CPT(A,A+1) can reuse an earlier A writer
            # but can never link its own destination back to its own read.
            for row in slots:
                if row['role'] == 'write':
                    address = address_by_use[row['id']]
                    latest[address['target_id']] = (address['id'], instruction.id, row['id'])

    patterns: dict[str, dict[str, Any]] = {}
    rung_patterns: list[dict[str, Any]] = []
    for rung in inventory.rungs:
        reason = _pattern_skip(rung, instructions, operands, uses_by_instruction, address_by_use)
        pattern_id = None
        if reason:
            coverage['pattern_skips'][reason] += 1
        else:
            pattern_id, variable_count = _pattern_digest(rung, instructions, operands, occurrences,
                                                          nodes, address_by_use)
            if pattern_id not in patterns:
                pattern = {'id': pattern_id, 'representative_rung_id': rung.id, 'rung_ids': [],
                           'address_variables': variable_count}
                budget.identifier(pattern_id)
                budget.identifier(rung.id)
                budget.record(pattern)
                patterns[pattern_id] = pattern
            budget.identifier(rung.id)
            patterns[pattern_id]['rung_ids'].append(rung.id)
        row = {'rung_id': rung.id, 'status': 'skipped' if reason else 'grouped',
               'pattern_id': pattern_id, 'reason': reason}
        budget.identifier(rung.id)
        if pattern_id:
            budget.identifier(pattern_id)
        budget.record(row)
        rung_patterns.append(row)
    coverage.update(addresses_total=len(addresses), identity_gaps_total=len(identity_gaps),
                    local_links_total=len(local_links), local_link_rungs=len(local_link_rungs),
                    patterns_total=len(patterns), skipped_rungs=sum(coverage['pattern_skips'].values()))
    coverage['patterned_rungs'] = len(inventory.rungs) - coverage['skipped_rungs']
    partial = bool(identity_gaps or coverage['skipped_rungs'] != coverage['pattern_skips']['empty'])
    return RelationshipResult(dict(inventory.snapshot), 'partial' if partial else 'complete',
                              list(addresses.values()), identity_gaps, local_links,
                              list(patterns.values()), rung_patterns, coverage)


def _local_barrier(opcode: str, instruction: dict[str, Any], slots: list[dict[str, Any]],
                   uses: list[dict[str, Any]], identities: dict[str, dict[str, Any]]) -> str | None:
    if opcode not in _LOCAL_OPCODES:
        return 'opcode_not_eligible'
    if instruction['status'] != 'classified':
        return 'access_not_classified'
    for row in slots:
        if row['role'] == 'expression_read':
            if row['binding_status'] != 'parsed_expression':
                return 'unsupported_expression'
            continue
        binding = row['binding_status']
        if binding == 'system_flag':
            return 'system_flag'
        if binding == 'root_bound':
            if row['id'] not in identities:
                return 'invalid_identity'
        elif row['role'] != 'read' or binding != 'literal':
            return 'unresolved_operand'
    for row in uses:
        if row['binding_status'] != 'root_bound':
            return 'unresolved_operand'
        if row['id'] not in identities:
            return 'invalid_identity'
    return None


def _pattern_skip(rung: Any, instructions: dict[str, dict[str, Any]], operands: dict[str, dict[str, Any]],
                  uses: dict[str, list[dict[str, Any]]], identities: dict[str, dict[str, Any]]) -> str | None:
    if rung.parse_status != 'parsed':
        return 'unparsed'
    if not rung.instructions:
        return 'empty'
    for instruction in rung.instructions:
        record = instructions[instruction.id]
        if record['status'] != 'classified':
            return 'unknown_instruction'
        for identifier in record['operand_ids']:
            row = operands[identifier]
            if row['role'] == 'unknown':
                return 'unknown_role'
            if row['role'] == 'expression_read':
                if row['binding_status'] != 'parsed_expression':
                    return 'unsupported_expression'
                for use in uses[instruction.id]:
                    if use['binding_status'] != 'root_bound':
                        return 'unresolved_address'
                    if use['id'] not in identities:
                        return 'invalid_expanded_suffix'
            elif row['binding_status'] == 'root_bound':
                if row['id'] not in identities:
                    return 'invalid_expanded_suffix'
            elif row['role'] == 'non_data':
                pass  # Its exact source spelling remains in the pattern.
            elif row['role'] != 'read' or row['binding_status'] not in {'literal', 'system_flag'}:
                return 'unresolved_address'
    return None


def _pattern_digest(rung: Any, instructions: dict[str, dict[str, Any]], operands: dict[str, dict[str, Any]],
                    occurrences: dict[str, dict[str, Any]], nodes: dict[str, dict[str, Any]],
                    identities: dict[str, dict[str, Any]]) -> tuple[str, int]:
    """Hash a flat unambiguous event stream; never expand all branch paths."""
    digest = hashlib.sha256(b'operand-reuse-pattern-1\0')
    variables: dict[str, int] = {}
    roots: dict[str, int] = {}
    sources = {instruction.id: instruction for instruction in rung.instructions}

    def emit(*token: Any) -> None:
        digest.update(json.dumps(token, ensure_ascii=True, separators=(',', ':')).encode('ascii'))
        digest.update(b'\n')

    def address(identifier: str) -> None:
        identity = identities[identifier]
        key = identity['id']
        if key not in variables:
            variables[key] = len(variables)
        if identity['target_id'] not in roots:
            roots[identity['target_id']] = len(roots)
        # Anonymize root names, but preserve same-root relationships and exact
        # member/index spelling. Distinct members cannot hide root overlap.
        emit('address', variables[key], roots[identity['target_id']], identity['suffix'])

    def expression(identifier: str) -> None:
        stack: list[tuple[str, bool]] = [(identifier, False)]
        while stack:
            current, closing = stack.pop()
            if closing:
                emit('expression_end')
                continue
            node = nodes[current]
            emit('expression', node['kind'], node['operator'])
            if node['kind'] == 'reference':
                address(current)
            elif node['kind'] == 'literal':
                emit('literal', node['raw_text'])
            stack.append((current, True))
            stack.extend((child, False) for child in reversed(node['child_ids']))

    stack: list[tuple[dict[str, Any], bool]] = [(rung.structure, False)]
    while stack:
        tree, closing = stack.pop()
        if closing:
            emit('structure_end')
            continue
        kind = tree['kind']
        emit('structure', kind)
        stack.append((tree, True))
        if kind == 'instruction':
            source = sources[tree['instruction_id']]
            record = instructions[source.id]
            emit('instruction', source.opcode.upper(), len(source.arguments))
            for identifier in record['operand_ids']:
                row = operands[identifier]
                emit('slot', row['role'])
                if row['role'] == 'expression_read':
                    expression(occurrences[source.id]['root_node_id'])
                elif identifier in identities:
                    address(identifier)
                else:
                    emit('spelling', row['binding_status'], source.arguments[row['argument_index']])
        else:
            children = tree['items'] if kind == 'sequence' else tree['legs']
            stack.extend((child, False) for child in reversed(children))
    return 'relationship_pattern_' + digest.hexdigest(), len(variables)


def analyze_relationships(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                          access: AccessResult, calculations: CalculationResult,
                          rung_analysis: RungAnalysisResult) -> RelationshipResult:
    """Authenticate the complete prior evidence chain before deriving links."""
    try:
        validate_rung_analysis(snapshot, inventory, references, access, calculations, rung_analysis)
        result = _derive(inventory, access, calculations, rung_analysis)
        render_relationships_json(result)
        return result
    except RelationshipError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_relationships(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                           access: AccessResult, calculations: CalculationResult,
                           rung_analysis: RungAnalysisResult, result: RelationshipResult) -> None:
    try:
        if type(result) is not RelationshipResult:
            _invalid()
        # Reject hostile native-container shapes before replay comparison.
        render_relationships_json(result)
        expected = analyze_relationships(snapshot, inventory, references, access, calculations, rung_analysis)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except RelationshipError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_relationships_json(result: RelationshipResult) -> str:
    """Bound native-only serialization; callers separately authenticate source."""
    try:
        if type(result) is not RelationshipResult or vars(result).keys() != set(RelationshipResult.__dataclass_fields__):
            _invalid()
        payload = vars(result)
        budget = MAX_RELATIONSHIP_BYTES
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
            budget -= 1
            if type(value) is str:
                budget -= len(value)
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
            if budget < 0:
                _limit()
        output, size = StringIO(), 0
        for chunk in json.JSONEncoder(ensure_ascii=True, sort_keys=True, indent=2).iterencode(payload):
            size += len(chunk)
            if size + 1 > MAX_RELATIONSHIP_BYTES:
                _limit()
            output.write(chunk)
        return output.getvalue() + '\n'
    except RelationshipError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
