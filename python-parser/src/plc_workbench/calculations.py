"""Bounded CPT expression syntax and lexical roots, without executing PLC logic.

The inherited root resolver does not validate members, array indices, XML
namespace semantics, data types, execution, or effects. Dynamic array addresses
remain single unresolved leaves; their index expressions create no dependencies.
An unsupported expression retains its source link but produces no partial AST
or leaf bindings. No source is evaluated, normalized back into source, or run.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from io import StringIO
from itertools import chain
import json
import re
from typing import Any

from .models import InventoryResult, SourceSnapshot
from .references import ALIAS_STATUSES, MAX_OPERANDS, ReferenceResult, _Resolver, _address, validate_references
from .source import MAX_SOURCE_BYTES, analyze_snapshot
from .tag_data import _strict_match

MAX_EXPRESSION_CHARS = 4096
MAX_EXPRESSION_TOKENS = 512
MAX_EXPRESSION_DEPTH = 64
MAX_CALCULATION_NODES = 250_000
MAX_CALCULATION_INSTRUCTIONS = 250_000
MAX_CALCULATION_BYTES = 16 * 1024 * 1024
SIGNATURE_STATUSES = frozenset({'recognized', 'argument_count_mismatch', 'empty_argument'})
SYNTAX_STATUSES = frozenset({'parsed', 'unsupported', 'signature_unresolved'})
NODE_KINDS = frozenset({'literal', 'reference', 'unary', 'binary', 'function', 'group'})
ERROR_CODES = frozenset({'lexical_error', 'syntax_error', 'unsupported_function',
                         'length_limit', 'token_limit', 'depth_limit'})
# Schema 1's original Studio 5000 v38 spellings stay frozen for replay.
# Schema 2 also recognizes the documented pre-v36 spellings. The AST retains
# each source spelling; neither catalog proves controller/version acceptance.
FUNCTIONS_V1 = frozenset('ABS ACOS ASIN ATAN COS DEG BCD_TO LN LOG RAD SIN SQRT TAN TO_BCD TRUNC'.split())
FUNCTIONS = FUNCTIONS_V1 | frozenset('ACS ASN ATN FRD SQR TOD TRN'.split())
UNSUPPORTED_FUNCTION_BUCKETS = frozenset({'atan2', 'other'})
_PRECEDENCE = {'OR': 10, 'XOR': 20, 'AND': 30, '+': 40, '-': 40,
               '*': 50, '/': 50, 'MOD': 50, '**': 70}
_UNARY_PRECEDENCE = 60
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z0-9_]+)*', re.ASCII)
_MEMBER = re.compile(r'\.(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+)', re.ASCII)
_NUMBER = re.compile(
    r'(?:2#[01](?:_?[01])*|8#[0-7](?:_?[0-7])*|16#[0-9A-Fa-f](?:_?[0-9A-Fa-f])*'
    r'|(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)', re.ASCII)
CALCULATION_V1_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'calculation-evidence-1',
    'analysis_scope': 'cpt_expression_evidence', 'semantic_analysis': 'not_implemented',
    'execution_analysis': 'not_implemented', 'effect_analysis': 'not_implemented',
    'member_validation': 'not_implemented', 'numeric_analysis': 'not_implemented',
}
CALCULATION_CONSTANTS = {**CALCULATION_V1_CONSTANTS,
                         'schema_version': 2, 'analyzer_version': 'calculation-evidence-2'}
COVERAGE_V1_KEYS = frozenset({
    'source_rungs', 'unparsed_rungs', 'source_instructions', 'source_operands',
    'occurrences_total', 'occurrences_by_signature', 'expressions_by_status',
    'expression_errors', 'nodes_total', 'nodes_by_kind', 'reference_occurrences',
    'reference_by_binding', 'destination_root_bound', 'expressions_with_binding_gaps',
})
COVERAGE_KEYS = COVERAGE_V1_KEYS | {'functions_by_spelling', 'unsupported_functions'}


class CalculationError(ValueError):
    """Source-free rejection of inconsistent or excessive private evidence."""


@dataclass(frozen=True)
class CalculationResult:
    snapshot: dict[str, str | int]
    status: str
    occurrences: list[dict[str, Any]]
    nodes: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 2
    analyzer_version: str = 'calculation-evidence-2'
    analysis_scope: str = 'cpt_expression_evidence'
    semantic_analysis: str = 'not_implemented'
    execution_analysis: str = 'not_implemented'
    effect_analysis: str = 'not_implemented'
    member_validation: str = 'not_implemented'
    numeric_analysis: str = 'not_implemented'

    def to_dict(self) -> dict[str, Any]:
        """Private evidence only; authenticate before copying caller records."""
        return asdict(self)


def _invalid() -> None:
    raise CalculationError('Calculation evidence is inconsistent or exceeds its limits.') from None


class _Unsupported(Exception):
    def __init__(self, code: str, offset: int, function_bucket: str = 'other'):
        self.code, self.offset = code, offset
        self.function_bucket = function_bucket
        super().__init__(code)


@dataclass(frozen=True)
class _Token:
    kind: str
    text: str
    start: int
    end: int


def _tokens(text: str) -> list[_Token]:
    if len(text) > MAX_EXPRESSION_CHARS:
        raise _Unsupported('length_limit', MAX_EXPRESSION_CHARS)
    result: list[_Token] = []
    cursor = 0
    while cursor < len(text):
        if text[cursor] in ' \t\r\n':
            cursor += 1
            continue
        if len(result) >= MAX_EXPRESSION_TOKENS:
            raise _Unsupported('token_limit', cursor)
        start = cursor
        number = _NUMBER.match(text, cursor)
        name = _NAME.match(text, cursor)
        if number:
            cursor = number.end()
            kind = 'literal'
        elif name:
            cursor = name.end()
            # Keep array syntax opaque inside a single address leaf. Its
            # resolver disposition is evidence, never index evaluation.
            while cursor < len(text):
                member = _MEMBER.match(text, cursor)
                if member:
                    cursor = member.end()
                elif text[cursor] == '[':
                    depth = 1
                    cursor += 1
                    while cursor < len(text) and depth:
                        if not text[cursor].isascii():
                            raise _Unsupported('lexical_error', cursor)
                        if text[cursor] == '[':
                            depth += 1
                            if depth > MAX_EXPRESSION_DEPTH:
                                raise _Unsupported('depth_limit', cursor)
                        elif text[cursor] == ']':
                            depth -= 1
                        cursor += 1
                    if depth:
                        raise _Unsupported('syntax_error', cursor)
                else:
                    break
            value = text[start:cursor]
            kind = 'operator' if value.upper() in {'MOD', 'AND', 'XOR', 'OR', 'NOT'} else 'reference'
        elif text.startswith('**', cursor):
            cursor += 2
            kind = 'operator'
        elif text[cursor] in '+-*/':
            cursor += 1
            kind = 'operator'
        elif text[cursor] in '(),':
            cursor += 1
            kind = text[start:cursor]
        else:
            raise _Unsupported('lexical_error', cursor)
        result.append(_Token(kind, text[start:cursor], start, cursor))
    return result


class _Parser:
    def __init__(self, text: str, instruction_id: str, snapshot_id: str,
                 functions: frozenset[str]):
        self.text, self.instruction_id, self.snapshot_id = text, instruction_id, snapshot_id
        self.functions = functions
        self.tokens = _tokens(text)
        self.cursor = 0
        self.nodes: list[dict[str, Any]] = []
        self.depths: dict[str, int] = {}
        self.by_id: dict[str, dict[str, Any]] = {}

    def fail(self, code: str = 'syntax_error') -> None:
        offset = self.tokens[self.cursor].start if self.cursor < len(self.tokens) else len(self.text)
        raise _Unsupported(code, offset)

    def node(self, kind: str, start: int, end: int, operator: str | None = None,
             children: tuple[str, ...] = ()) -> str:
        depth = 1 + max((self.depths[child] for child in children), default=0)
        if depth > MAX_EXPRESSION_DEPTH:
            raise _Unsupported('depth_limit', start)
        identity = f'{self.snapshot_id}\0{self.instruction_id}\0{kind}\0{start}\0{end}'
        identifier = 'calculation_node_' + hashlib.sha256(identity.encode()).hexdigest()
        row = {'id': identifier, 'instruction_id': self.instruction_id, 'kind': kind,
               'start': start, 'end': end, 'operator': operator, 'child_ids': list(children),
               'raw_text': self.text[start:end] if kind in {'literal', 'reference'} else None,
               'binding': None}
        self.nodes.append(row)
        self.depths[identifier] = depth
        self.by_id[identifier] = row
        return identifier

    def expression(self, minimum: int = 0, depth: int = 0) -> str:
        if depth >= MAX_EXPRESSION_DEPTH:
            self.fail('depth_limit')
        if self.cursor >= len(self.tokens):
            self.fail()
        token = self.tokens[self.cursor]
        self.cursor += 1
        if token.kind == 'operator' and token.text.upper() in {'-', 'NOT'}:
            child = self.expression(_UNARY_PRECEDENCE, depth + 1)
            left = self.node('unary', token.start, self.by_id[child]['end'], token.text.upper(), (child,))
        elif token.kind == '(':
            child = self.expression(0, depth + 1)
            end = self.closing()
            left = self.node('group', token.start, end, children=(child,))
        elif token.kind in {'literal', 'reference'}:
            if (token.kind == 'reference' and self.cursor < len(self.tokens)
                    and self.tokens[self.cursor].kind == '('):
                if token.text.upper() not in self.functions:
                    # Only this exact public token receives its own bucket.
                    # Unknown/private names never become aggregate keys.
                    bucket = 'atan2' if token.text.upper() == 'ATAN2' else 'other'
                    raise _Unsupported('unsupported_function', token.start, bucket)
                self.cursor += 1
                child = self.expression(0, depth + 1)
                end = self.closing()
                left = self.node('function', token.start, end, token.text.upper(), (child,))
            else:
                # The brackets belong to an opaque address leaf, but they
                # still need the resolver's limited lexical address grammar.
                # Do not publish bindings from a malformed expression prefix.
                if token.kind == 'reference' and _address(token.text)[1] == 'malformed_address':
                    raise _Unsupported('syntax_error', token.start)
                left = self.node(token.kind, token.start, token.end)
        else:
            raise _Unsupported('syntax_error', token.start)
        while self.cursor < len(self.tokens):
            operator = self.tokens[self.cursor]
            precedence = _PRECEDENCE.get(operator.text.upper()) if operator.kind == 'operator' else None
            if precedence is None or precedence < minimum:
                break
            self.cursor += 1
            # The documented left-associative power rule and lower-precedence
            # prefix operators leave an unparenthesized signed exponent
            # outside this narrow grammar. Explicit parentheses are supported.
            if (operator.text == '**' and self.cursor < len(self.tokens)
                    and self.tokens[self.cursor].kind == 'operator'
                    and self.tokens[self.cursor].text.upper() in {'-', '+', 'NOT'}):
                self.fail()
            # Rockwell CPT documents equal precedence left-to-right, including
            # exponentiation. Python's right-associative power is not reused.
            right = self.expression(precedence + 1, depth + 1)
            left = self.node('binary', self.by_id[left]['start'], self.by_id[right]['end'],
                             operator.text.upper(), (left, right))
        return left

    def closing(self) -> int:
        if self.cursor >= len(self.tokens) or self.tokens[self.cursor].kind != ')':
            self.fail()
        end = self.tokens[self.cursor].end
        self.cursor += 1
        return end

    def parse(self) -> str:
        root = self.expression()
        if self.cursor != len(self.tokens):
            self.fail()
        return root


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult,
            references: ReferenceResult, schema_version: int) -> CalculationResult:
    constants = CALCULATION_V1_CONSTANTS if schema_version == 1 else CALCULATION_CONSTANTS
    functions = FUNCTIONS_V1 if schema_version == 1 else FUNCTIONS
    resolver = _Resolver(inventory)
    operands = {(row['instruction_id'], row['argument_index']): row for row in references.operands}
    occurrences: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    coverage: dict[str, Any] = {
        key: 0 for key in sorted(COVERAGE_V1_KEYS - {'occurrences_by_signature', 'expressions_by_status',
                                                'expression_errors', 'nodes_by_kind', 'reference_by_binding'})}
    for key, vocabulary in (('occurrences_by_signature', SIGNATURE_STATUSES),
                            ('expressions_by_status', SYNTAX_STATUSES), ('expression_errors', ERROR_CODES),
                            ('nodes_by_kind', NODE_KINDS), ('reference_by_binding', ALIAS_STATUSES)):
        coverage[key] = dict.fromkeys(sorted(vocabulary), 0)
    if schema_version == 2:
        coverage['functions_by_spelling'] = dict.fromkeys(sorted(FUNCTIONS), 0)
        coverage['unsupported_functions'] = dict.fromkeys(sorted(UNSUPPORTED_FUNCTION_BUCKETS), 0)
    retained = 0
    for rung in inventory.rungs:
        if rung.parse_status != 'parsed':
            coverage['unparsed_rungs'] += 1
            continue
        coverage['source_instructions'] += len(rung.instructions)
        for instruction in rung.instructions:
            if not instruction.opcode.isascii() or instruction.opcode.upper() != 'CPT':
                continue
            signature = ('argument_count_mismatch' if len(instruction.arguments) != 2 else
                         'empty_argument' if any(not arg.strip() for arg in instruction.arguments) else 'recognized')
            destination = operands.get((instruction.id, 0))
            expression = operands.get((instruction.id, 1))
            row = {'id': instruction.id, 'rung_id': rung.id,
                   'destination_operand_id': destination['id'] if destination else None,
                   'expression_operand_id': expression['id'] if expression else None,
                   'signature_status': signature, 'syntax_status': 'signature_unresolved',
                   'error_code': None, 'error_offset': None, 'root_node_id': None, 'node_ids': []}
            if signature == 'recognized':
                coverage['destination_root_bound'] += int(destination['status'] == 'root_bound')
                try:
                    parser = _Parser(expression['raw_text'], instruction.id, str(snapshot.id), functions)
                    root = parser.parse()
                except _Unsupported as error:
                    row.update(syntax_status='unsupported', error_code=error.code, error_offset=error.offset)
                    coverage['expression_errors'][error.code] += 1
                    if schema_version == 2 and error.code == 'unsupported_function':
                        coverage['unsupported_functions'][error.function_bucket] += 1
                else:
                    if len(nodes) + len(parser.nodes) > MAX_CALCULATION_NODES:
                        _invalid()
                    gaps = False
                    for node in parser.nodes:
                        coverage['nodes_by_kind'][node['kind']] += 1
                        if schema_version == 2 and node['kind'] == 'function':
                            coverage['functions_by_spelling'][node['operator']] += 1
                        if node['kind'] == 'reference':
                            node['binding'] = resolver.resolve(node['raw_text'], rung.scope_id)
                            disposition = node['binding']['status']
                            coverage['reference_by_binding'][disposition] += 1
                            gaps = gaps or disposition != 'root_bound'
                        retained += len(json.dumps(node, ensure_ascii=True).encode())
                        if retained > MAX_CALCULATION_BYTES:
                            _invalid()
                    coverage['expressions_with_binding_gaps'] += int(gaps)
                    row.update(syntax_status='parsed', root_node_id=root,
                               node_ids=[node['id'] for node in parser.nodes])
                    nodes.extend(parser.nodes)
            retained += len(json.dumps(row, ensure_ascii=True).encode())
            if retained > MAX_CALCULATION_BYTES:
                _invalid()
            coverage['occurrences_by_signature'][signature] += 1
            coverage['expressions_by_status'][row['syntax_status']] += 1
            occurrences.append(row)
    coverage.update(source_rungs=len(inventory.rungs), source_operands=len(references.operands),
                    occurrences_total=len(occurrences), nodes_total=len(nodes),
                    reference_occurrences=coverage['nodes_by_kind']['reference'])
    partial = bool(coverage['unparsed_rungs']
                   or coverage['expressions_by_status']['parsed'] != len(occurrences)
                   or coverage['destination_root_bound'] != len(occurrences)
                   or coverage['expressions_with_binding_gaps'])
    return CalculationResult(dict(inventory.snapshot), 'partial' if partial else 'complete',
                             occurrences, nodes, coverage, **constants)


def analyze_calculations(snapshot: SourceSnapshot, inventory: InventoryResult,
                         references: ReferenceResult, *, schema_version: int = 2) -> CalculationResult:
    """Authenticate source before analysis; schema 1 replays its frozen catalog."""
    try:
        if (type(schema_version) is not int or schema_version not in {1, 2}
                or type(snapshot) is not SourceSnapshot or type(inventory) is not InventoryResult
                or type(references) is not ReferenceResult
                or vars(snapshot).keys() != set(SourceSnapshot.__dataclass_fields__)
                or type(snapshot.data) is not bytes or len(snapshot.data) > MAX_SOURCE_BYTES
                or type(snapshot.size_bytes) is not int or snapshot.size_bytes != len(snapshot.data)
                or type(snapshot.sha256) is not str or type(snapshot.id) is not str
                or snapshot.sha256 != hashlib.sha256(snapshot.data).hexdigest()
                or snapshot.id != f'sha256:{snapshot.sha256}'
                or type(inventory.rungs) is not list or type(references.operands) is not list
                or len(references.operands) > MAX_OPERANDS):
            _invalid()
        instruction_count = operand_count = 0
        for rung in inventory.rungs:
            if rung.parse_status == 'parsed':
                instruction_count += len(rung.instructions)
                operand_count += sum(len(instruction.arguments) for instruction in rung.instructions)
                if instruction_count > MAX_CALCULATION_INSTRUCTIONS or operand_count > MAX_OPERANDS:
                    _invalid()
        if not _strict_match(analyze_snapshot(snapshot), inventory):
            _invalid()
        validate_references(inventory, references)
        result = _derive(snapshot, inventory, references, schema_version)
        render_calculation_json(result)
        return result
    except CalculationError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_calculations(snapshot: SourceSnapshot, inventory: InventoryResult,
                          references: ReferenceResult, result: CalculationResult) -> None:
    """Replay bounded canonical evidence before trusting caller-supplied records."""
    try:
        valid = type(result) is CalculationResult and _strict_match(
            analyze_calculations(snapshot, inventory, references, schema_version=result.schema_version), result)
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        valid = False
    if not valid:
        _invalid()


def render_calculation_json(result: CalculationResult) -> str:
    """Bound private serialization; validate_calculations authenticates source links."""
    if type(result) is not CalculationResult or vars(result).keys() != set(CalculationResult.__dataclass_fields__):
        _invalid()
    try:
        # Only bounded native containers reach serialization. This also rejects
        # cycles/custom objects without deep-copying an untrusted dataclass.
        budget = MAX_CALCULATION_BYTES
        payload = vars(result)
        # An iterator stack visits one child at a time. Eagerly queuing a
        # hostile cyclic/fanout container can exhaust memory before the byte
        # budget is charged. Canonical flat evidence needs fewer than 16 JSON
        # container levels, independent of the expression's AST depth.
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
                if len(value) > budget:
                    _invalid()
                budget -= len(value.encode('utf-8'))
            elif type(value) is dict:
                if any(type(key) is not str for key in value) or len(value) > MAX_CALCULATION_NODES:
                    _invalid()
                if id(value) in active or len(frames) > 16:
                    _invalid()
                active.add(id(value))
                frames.append((iter(chain(value.keys(), value.values())), id(value)))
            elif type(value) is list:
                if len(value) > max(MAX_CALCULATION_NODES, MAX_CALCULATION_INSTRUCTIONS):
                    _invalid()
                if id(value) in active or len(frames) > 16:
                    _invalid()
                active.add(id(value))
                frames.append((iter(value), id(value)))
            elif type(value) not in {int, bool, type(None)}:
                _invalid()
            if budget < 0:
                _invalid()
        buffer = StringIO()
        size = 0
        for chunk in json.JSONEncoder(indent=2, sort_keys=True, ensure_ascii=True).iterencode(payload):
            size += len(chunk.encode('utf-8'))
            if size + 1 > MAX_CALCULATION_BYTES:
                _invalid()
            buffer.write(chunk)
        return buffer.getvalue() + '\n'
    except (TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
