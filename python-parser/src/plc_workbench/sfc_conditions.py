"""Bounded, source-linked SFC transition expressions; never controller execution.

Each captured transition remains visible, including unsupported text and XML
shapes. AST offsets index the joined Line text in XML order (one inserted LF
between Lines), not serialized XML bytes. Bindings prove scoped declaration
identity only, not member existence, type correctness or runtime truth.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from io import StringIO
import hashlib
import json
import re
from typing import Any

from .models import InventoryResult, SourceSnapshot
from .references import (ReferenceResult, _Resolver, _ADDRESS, MAX_ADDRESS_LENGTH,
                         _strict_record_match, validate_references)
from .sfc_structure import SfcStructureResult, validate_sfc_structure
from .source import _read_nodes, analyze_snapshot
from .tag_data import _strict_match

MAX_SFC_CONDITION_BYTES = 16 * 1024 * 1024
MAX_SFC_CONDITION_JSON_BYTES = 16 * 1024 * 1024
MAX_SFC_CONDITION_RECORDS = 250_000
MAX_EXPRESSION_CHARS = 65_536
MAX_EXPRESSION_TOKENS = 2048
MAX_EXPRESSION_DEPTH = 64
MAX_EVIDENCE_CHARS = 8_000_000
STATUSES = frozenset({'modeled', 'binding_gaps', 'unsupported'})
REASONS = frozenset({'none', 'missing_condition', 'ambiguous_condition',
    'unsupported_shape', 'namespace_gap', 'empty_expression', 'character_limit',
    'token_limit', 'depth_limit', 'invalid_token', 'invalid_expression',
    'unterminated_comment', 'nested_comment', 'unsupported_string',
    'unsupported_construct', 'unsupported_statement', 'unsupported_function',
    'instruction_call', 'dynamic_index', 'invalid_address', 'function_arity'})
BINDING_STATUSES = frozenset({'root_bound', 'unresolved', 'ambiguous', 'alias_cycle',
    'alias_depth_limit', 'unsupported_address', 'namespace_gap', 'invalid_identity'})
NODE_KINDS = frozenset({'number', 'reference', 'group', 'unary', 'binary', 'function'})
COMMENT_KINDS = frozenset({'line', 'paren_block', 'slash_block'})
METADATA_GAPS = frozenset({'missing_number', 'invalid_number', 'duplicate_number', 'out_of_order_number'})
COUNT_MAPS = {'transitions_by_status': STATUSES, 'transitions_by_reason': REASONS,
    'nodes_by_kind': NODE_KINDS, 'references_by_binding': BINDING_STATUSES,
    'comments_by_kind': COMMENT_KINDS, 'metadata_gaps': METADATA_GAPS}
COVERAGE_KEYS = frozenset({'source_routines', 'source_contents', 'source_elements',
    'source_st_lines', 'transition_st_lines', 'unprocessed_st_lines',
    'transitions_total', 'transitions_with_text', 'transitions_with_comments',
    'transitions_with_metadata_gaps', 'nodes_total', 'references_total',
    'comments_total', 'expression_chars', 'line_spans_total', *COUNT_MAPS})
SFC_CONDITION_CONSTANTS = {'schema_version': 1, 'analyzer_version': 'sfc-conditions-1',
    'analysis_scope': 'source_transition_expressions_only',
    'runtime_analysis': 'not_implemented', 'type_analysis': 'not_implemented',
    'address_identity': 'exact_expanded_spelling', 'engineering_review': 'unreviewed'}
# Logix ST precedence: official "Determine the order of execution". Equal
# priorities, including exponentiation, associate left to right. Unary minus
# binds more tightly than NOT, but less tightly than exponentiation.
_PRECEDENCE = {'OR': 1, 'XOR': 2, 'AND': 3, '&': 3, '=': 4, '<>': 4,
    '<': 5, '<=': 5, '>': 5, '>=': 5, '+': 6, '-': 6,
    '*': 7, '/': 7, 'MOD': 7, '**': 10}
FUNCTIONS = frozenset({'ABS', 'ACOS', 'ASIN', 'ATAN', 'COS', 'DEG', 'LN',
    'LOG', 'RAD', 'SIN', 'SQRT', 'TAN', 'TRUNC', 'ACS', 'ASN', 'ATN', 'SQR', 'TRN'})
_CONSTRUCTS = frozenset({'IF', 'THEN', 'ELSE', 'ELSIF', 'END_IF', 'CASE', 'OF',
    'END_CASE', 'FOR', 'TO', 'BY', 'DO', 'END_FOR', 'WHILE', 'END_WHILE',
    'REPEAT', 'UNTIL', 'END_REPEAT', 'EXIT', 'RETURN'})
_ROOT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z0-9_]+)*', re.ASCII)
_MEMBER = re.compile(r'\.(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+)', re.ASCII)
_NUMBER = re.compile(r'(?:(?:2#[01](?:_?[01])*|8#[0-7](?:_?[0-7])*|16#[0-9A-Fa-f](?:_?[0-9A-Fa-f])*)(?:[uU][lL]?|[lL])?|(?:[0-9]+\.[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?[lL]?|[0-9]+[eE][+-]?[0-9]+[lL]?|[0-9]+(?:[uU][lL]?|[lL])?)', re.ASCII)


class SfcConditionError(ValueError):
    """Source-free fatal rejection, distinct from retained expression gaps."""


def _invalid() -> None:
    raise SfcConditionError('SFC condition evidence is inconsistent or exceeds its limits.') from None


@dataclass(frozen=True)
class SfcConditionResult:
    snapshot: dict[str, str | int]
    status: str
    transitions: list[dict[str, Any]]
    nodes: list[dict[str, Any]]
    references: list[dict[str, Any]]
    comments: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'sfc-conditions-1'
    analysis_scope: str = 'source_transition_expressions_only'
    runtime_analysis: str = 'not_implemented'
    type_analysis: str = 'not_implemented'
    address_identity: str = 'exact_expanded_spelling'
    engineering_review: str = 'unreviewed'

    def to_dict(self) -> dict[str, Any]:
        render_sfc_conditions_json(self)
        return deepcopy(vars(self))


class _SyntaxGap(Exception):
    def __init__(self, reason: str, offset: int):
        self.reason, self.offset = reason, offset


def _identifier(owner: str, kind: str, ordinal: int) -> str:
    return hashlib.sha256(f'{owner}\0sfc-condition-{kind}\0{ordinal}'.encode()).hexdigest()


def _namespace(name: str) -> str | None:
    return name.rsplit('}', 1)[0] if '}' in name else None


def _partial(c: dict[str, Any]) -> bool:
    return bool(c['transitions_by_status']['binding_gaps'] or c['transitions_by_status']['unsupported']
                or c['transitions_with_metadata_gaps'] or c['unprocessed_st_lines'])


def _tokens(text: str, comments: list[dict[str, Any]]) -> list[tuple[str, str, int, int]]:
    tokens: list[tuple[str, str, int, int]] = []
    position = 0
    while position < len(text):
        char = text[position]
        if char.isspace():
            position += 1
            continue
        start = position
        prefix = text[position:position + 2]
        if prefix in {'//', '(*', '/*'}:
            kind = {'//': 'line', '(*': 'paren_block', '/*': 'slash_block'}[prefix]
            end = text.find('\n', position + 2) if prefix == '//' else text.find('*)' if prefix == '(*' else '*/', position + 2)
            terminated = prefix == '//' or end >= 0
            end = len(text) if end < 0 else end if prefix == '//' else end + 2
            comments.append({'kind': kind, 'start': start, 'end': end, 'raw_text': text[start:end], 'terminated': terminated})
            if not terminated:
                raise _SyntaxGap('unterminated_comment', start)
            if prefix != '//' and any(opener in text[start + 2:end - 2] for opener in ('(*', '/*')):
                raise _SyntaxGap('nested_comment', start)
            position = end
            continue
        if char in {'\'', '"'}:
            raise _SyntaxGap('unsupported_string', start)
        if prefix == ':=':
            raise _SyntaxGap('unsupported_statement', start)
        number = _NUMBER.match(text, position)
        if number:
            position = number.end()
            tokens.append(('number', number.group(), start, position))
        else:
            root = _ROOT.match(text, position)
            if root:
                position = root.end()
                while position < len(text):
                    member = _MEMBER.match(text, position)
                    if member:
                        position = member.end()
                    elif text[position] == '[':
                        end = text.find(']', position + 1)
                        if end < 0:
                            raise _SyntaxGap('invalid_address', position)
                        if not re.fullmatch(r'\[\s*[0-9]+(?:\s*,\s*[0-9]+)*\s*\]', text[position:end + 1], re.ASCII):
                            raise _SyntaxGap('dynamic_index', position)
                        position = end + 1
                    else:
                        break
                raw = text[start:position]
                word = raw.upper()
                if word in _CONSTRUCTS:
                    raise _SyntaxGap('unsupported_construct', start)
                kind = 'operator' if word in {'AND', 'OR', 'XOR', 'NOT', 'MOD'} else 'reference'
                if kind == 'reference' and (len(raw) > MAX_ADDRESS_LENGTH or not _ADDRESS.fullmatch(raw)):
                    raise _SyntaxGap('invalid_address', start)
                tokens.append((kind, word if kind == 'operator' else raw, start, position))
            elif prefix in {'**', '<=', '>=', '<>'}:
                position += 2
                tokens.append(('operator', prefix, start, position))
            elif char in '+-*/=<>&(),;':
                position += 1
                tokens.append(('operator', char, start, position))
            else:
                raise _SyntaxGap('invalid_token', start)
        if len(tokens) > MAX_EXPRESSION_TOKENS:
            raise _SyntaxGap('token_limit', start)
    return tokens


class _Parser:
    """Small flat AST parser; failed parses never publish a partial AST."""

    def __init__(self, text: str, tokens: list[tuple[str, str, int, int]]):
        self.text, self.tokens, self.position = text, tokens, 0
        self.nodes: list[dict[str, Any]] = []
        self.depths: list[int] = []

    def add(self, kind: str, start: int, end: int, children: list[int], operator: str | None = None) -> int:
        depth = 1 + max((self.depths[child] for child in children), default=0)
        if depth > MAX_EXPRESSION_DEPTH:
            raise _SyntaxGap('depth_limit', start)
        node = {'kind': kind, 'start': start, 'end': end, 'children': children,
                'operator': operator, 'raw_text': self.text[start:end] if kind in {'number', 'reference'} else None}
        self.nodes.append(node)
        self.depths.append(depth)
        return len(self.nodes) - 1

    def expression(self, minimum: int = 0, depth: int = 0) -> int:
        if depth >= MAX_EXPRESSION_DEPTH:
            raise _SyntaxGap('depth_limit', self.tokens[self.position][2] if self.position < len(self.tokens) else len(self.text))
        if self.position >= len(self.tokens):
            raise _SyntaxGap('invalid_expression', len(self.text))
        kind, value, start, end = self.tokens[self.position]
        self.position += 1
        if value in {'-', '+', 'NOT'}:
            operand = self.expression(8 if value == 'NOT' else 9, depth + 1)
            left = self.add('unary', start, self.nodes[operand]['end'], [operand], value)
        elif value == '(':
            child = self.expression(0, depth + 1)
            if self.position >= len(self.tokens) or self.tokens[self.position][1] != ')':
                raise _SyntaxGap('invalid_expression', start)
            end = self.tokens[self.position][3]
            self.position += 1
            left = self.add('group', start, end, [child])
        elif kind == 'number':
            left = self.add('number', start, end, [])
        elif kind == 'reference':
            if self.position < len(self.tokens) and self.tokens[self.position][1] == '(':
                function = value.upper()
                if function not in FUNCTIONS:
                    raise _SyntaxGap('instruction_call' if function == 'JSR' else 'unsupported_function', start)
                self.position += 1
                if self.position < len(self.tokens) and self.tokens[self.position][1] == ')':
                    raise _SyntaxGap('function_arity', start)
                child = self.expression(0, depth + 1)
                if self.position < len(self.tokens) and self.tokens[self.position][1] == ',':
                    raise _SyntaxGap('function_arity', start)
                if self.position >= len(self.tokens) or self.tokens[self.position][1] != ')':
                    raise _SyntaxGap('invalid_expression', start)
                end = self.tokens[self.position][3]
                self.position += 1
                left = self.add('function', start, end, [child], function)
            else:
                left = self.add('reference', start, end, [])
        else:
            raise _SyntaxGap('invalid_expression', start)
        while self.position < len(self.tokens):
            operator = self.tokens[self.position][1]
            priority = _PRECEDENCE.get(operator, -1)
            if priority < minimum:
                break
            self.position += 1
            right = self.expression(priority + 1, depth + 1)
            left = self.add('binary', self.nodes[left]['start'], self.nodes[right]['end'], [left, right], operator)
        return left


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, sfc: SfcStructureResult) -> SfcConditionResult:
    if max(len(inventory.entities), len(sfc.elements), len(sfc.contents)) > MAX_SFC_CONDITION_RECORDS:
        _invalid()
    xml_nodes = _read_nodes(snapshot.data)
    namespace = _namespace(xml_nodes[0].expanded_name)
    valid_nodes: list[bool] = []
    supported: dict[str, bool] = {}
    for node in xml_nodes:
        valid = (_namespace(node.expanded_name) == namespace
            and all('}' not in key for key in node.expanded_attributes)
            and (node.parent is None or valid_nodes[node.parent]))
        valid_nodes.append(valid)
        supported[node.locator] = valid
    entities = {row.id: row for row in inventory.entities}
    contents = {row['id']: row for row in sfc.contents}
    children: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    for element in sfc.elements:
        children[element['parent_id']].append(element)
    resolver = _Resolver(inventory)
    rows: list[dict[str, Any]] = []
    ast_nodes: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    comments: list[dict[str, Any]] = []
    c = {key: 0 for key in sorted(COVERAGE_KEYS - COUNT_MAPS.keys())}
    c.update({key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()})
    c.update(source_routines=len(sfc.routines), source_contents=len(sfc.contents), source_elements=len(sfc.elements),
             source_st_lines=sum(e['kind'] == 'st_line' for e in sfc.elements))
    transition_lines: set[str] = set()
    retained_bytes = records = 0

    def retain(row: dict[str, Any]) -> None:
        nonlocal retained_bytes, records
        records += 1
        retained_bytes += len(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if records > MAX_SFC_CONDITION_RECORDS or retained_bytes > MAX_SFC_CONDITION_BYTES:
            _invalid()

    for element in sfc.elements:
        if element['kind'] != 'transition':
            continue
        identifier = _identifier(element['id'], 'transition', 0)
        routine = entities[element['routine_id']]
        row = {'id': identifier, 'transition_id': element['id'], 'content_id': element['content_id'],
            'routine_id': element['routine_id'], 'scope_id': routine.scope_id,
            'condition_id': None, 'st_content_id': None, 'edit_kind': contents[element['content_id']]['edit_kind'],
            'line_ids': [], 'line_spans': [], 'raw_text': '', 'status': 'unsupported', 'reason': 'none',
            'error_offset': None, 'terminator_offset': None, 'root_node_id': None, 'node_ids': [], 'reference_ids': [], 'comment_ids': [],
            'metadata_gaps': []}
        descendants: list[dict[str, Any]] = []
        stack = list(reversed(children[element['id']]))
        while stack:
            descendant = stack.pop()
            descendants.append(descendant)
            stack.extend(reversed(children[descendant['id']]))
        line_rows = [child for child in descendants if child['kind'] == 'st_line']
        transition_lines.update(child['id'] for child in line_rows)
        conditions = [child for child in children[element['id']] if child['kind'] == 'condition']
        reason = 'none'
        if not conditions:
            reason = 'missing_condition'
        elif len(conditions) != 1:
            reason = 'ambiguous_condition'
        else:
            condition = conditions[0]
            row['condition_id'] = condition['id']
            st_contents = children[condition['id']]
            if len(st_contents) != 1 or st_contents[0]['kind'] != 'st_content':
                reason = 'unsupported_shape'
            else:
                st = st_contents[0]
                row['st_content_id'] = st['id']
                canonical_lines = children[st['id']]
                if (condition['direct_text'].strip() or st['direct_text'].strip()
                        or any(child['kind'] != 'st_line' or children[child['id']] for child in canonical_lines)
                        or any(child['kind'] not in {'condition', 'description'} for child in children[element['id']])
                        or element['direct_text'].strip()):
                    reason = 'unsupported_shape'
                else:
                    offset = 0
                    for line in canonical_lines:
                        row['line_ids'].append(line['id'])
                        end = offset + len(line['direct_text'])
                        row['line_spans'].append({'line_id': line['id'], 'start': offset, 'end': end})
                        offset = end + 1
                    row['raw_text'] = '\n'.join(line['direct_text'] for line in canonical_lines)
                    numbers: list[str] = []
                    metadata: set[str] = set()
                    for line in canonical_lines:
                        number = line['attributes'].get('Number')
                        if number is None:
                            metadata.add('missing_number')
                        elif not re.fullmatch(r'[0-9]+', number, re.ASCII):
                            metadata.add('invalid_number')
                        else:
                            numbers.append(number.lstrip('0') or '0')
                    if len(set(numbers)) != len(numbers):
                        metadata.add('duplicate_number')
                    if any((len(a), a) > (len(b), b) for a, b in zip(numbers, numbers[1:])):
                        metadata.add('out_of_order_number')
                    row['metadata_gaps'] = sorted(metadata)
        # Namespace provenance is required for the complete transition envelope,
        # not only the surviving token spelling or final target declaration.
        if not supported[element['locator']] or any(not supported[child['locator']] for child in descendants):
            reason = 'namespace_gap'
        text = row['raw_text']
        c['expression_chars'] += len(text)
        if c['expression_chars'] > MAX_EVIDENCE_CHARS:
            _invalid()
        local_comments: list[dict[str, Any]] = []
        parsed: _Parser | None = None
        root: int | None = None
        if reason == 'none':
            try:
                if len(text) > MAX_EXPRESSION_CHARS:
                    raise _SyntaxGap('character_limit', MAX_EXPRESSION_CHARS)
                tokens = _tokens(text, local_comments)
                if tokens and tokens[-1][1] == ';':
                    row['terminator_offset'] = tokens.pop()[2]
                if not tokens:
                    raise _SyntaxGap('empty_expression', 0)
                parsed = _Parser(text, tokens)
                root = parsed.expression()
                if parsed.position != len(tokens):
                    raise _SyntaxGap('unsupported_statement' if tokens[parsed.position][1] == ';' else 'invalid_expression', tokens[parsed.position][2])
            except _SyntaxGap as gap:
                reason, row['error_offset'] = gap.reason, gap.offset
                parsed = None
        for ordinal, comment in enumerate(local_comments):
            comment.update(id=_identifier(identifier, 'comment', ordinal), transition_id=identifier)
            row['comment_ids'].append(comment['id'])
            comments.append(comment)
            c['comments_by_kind'][comment['kind']] += 1
            retain(comment)
        row['reason'] = reason
        if parsed is not None:
            row['status'] = 'modeled'
            node_ids = [_identifier(identifier, 'node', i) for i in range(len(parsed.nodes))]
            row['node_ids'] = node_ids
            row['root_node_id'] = node_ids[root]
            for ordinal, node in enumerate(parsed.nodes):
                node = {**node, 'id': node_ids[ordinal], 'transition_id': identifier,
                        'children': [node_ids[index] for index in node['children']], 'binding_id': None}
                if node['kind'] == 'reference':
                    binding = resolver.resolve(node['raw_text'], routine.scope_id)
                    status = binding['status']
                    address = None
                    linked = [binding['symbol_id'], binding['target_id'], *binding['alias_chain']]
                    if any(link is not None and (link not in entities or not supported[entities[link].locator]) for link in linked):
                        status = 'namespace_gap'
                    elif status == 'root_bound':
                        suffix = binding['suffix']
                        if len(suffix) > MAX_ADDRESS_LENGTH or not _ADDRESS.fullmatch('A' + suffix):
                            status = 'invalid_identity'
                        else:
                            address = [binding['target_id'], suffix]
                    if status != 'root_bound':
                        row['status'] = 'binding_gaps'
                    reference = {'id': _identifier(identifier, 'reference', len(row['reference_ids'])),
                        'node_id': node['id'], 'transition_id': identifier, 'raw_text': node['raw_text'],
                        'start': node['start'], 'end': node['end'], 'binding': binding,
                        'binding_status': status, 'address_key': address}
                    row['reference_ids'].append(reference['id'])
                    node['binding_id'] = reference['id']
                    c['references_by_binding'][status] += 1
                    references.append(reference)
                    retain(reference)
                c['nodes_by_kind'][node['kind']] += 1
                ast_nodes.append(node)
                retain(node)
        c['transitions_by_status'][row['status']] += 1
        c['transitions_by_reason'][reason] += 1
        c['transitions_with_text'] += bool(text)
        c['transitions_with_comments'] += bool(row['comment_ids'])
        c['transitions_with_metadata_gaps'] += bool(row['metadata_gaps'])
        c['line_spans_total'] += len(row['line_spans'])
        for gap in row['metadata_gaps']:
            c['metadata_gaps'][gap] += 1
        rows.append(row)
        retain(row)
    c.update(transitions_total=len(rows), nodes_total=len(ast_nodes), references_total=len(references),
             comments_total=len(comments), transition_st_lines=len(transition_lines),
             unprocessed_st_lines=c['source_st_lines'] - len(transition_lines))
    return SfcConditionResult(deepcopy(inventory.snapshot), 'partial' if _partial(c) else 'complete',
                              rows, ast_nodes, references, comments, c)


def analyze_sfc_conditions(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, sfc_structure: SfcStructureResult) -> SfcConditionResult:
    try:
        if (type(snapshot) is not SourceSnapshot or type(inventory) is not InventoryResult
                or not _strict_match(analyze_snapshot(snapshot), inventory)):
            _invalid()
        validate_references(inventory, references)
        validate_sfc_structure(snapshot, inventory, sfc_structure)
        result = _derive(snapshot, inventory, sfc_structure)
        render_sfc_conditions_json(result)
        return result
    except SfcConditionError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_sfc_conditions(snapshot: SourceSnapshot, inventory: InventoryResult,
        references: ReferenceResult, sfc_structure: SfcStructureResult, result: SfcConditionResult) -> None:
    try:
        render_sfc_conditions_json(result)
        expected = analyze_sfc_conditions(snapshot, inventory, references, sfc_structure)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except SfcConditionError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_sfc_conditions_json(result: SfcConditionResult) -> str:
    try:
        if type(result) is not SfcConditionResult or vars(result).keys() != set(SfcConditionResult.__dataclass_fields__):
            _invalid()
        remaining = MAX_SFC_CONDITION_BYTES
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
                if identifier in active or len(value) > MAX_SFC_CONDITION_RECORDS:
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
        if sum(len(getattr(result, key)) for key in ('transitions', 'nodes', 'references', 'comments')) > MAX_SFC_CONDITION_RECORDS:
            _invalid()
        output, size = StringIO(), 1
        for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).iterencode(vars(result)):
            size += len(chunk.encode('utf-8'))
            if size > MAX_SFC_CONDITION_JSON_BYTES:
                _invalid()
            output.write(chunk)
        return output.getvalue() + '\n'
    except SfcConditionError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
