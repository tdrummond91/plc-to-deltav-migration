"""One immutable, small request for informative, value-free ladder examples.

Selection uses authenticated private evidence. Publication retains whole-rung
instruction/branch structure and lexical equality inside each sample, never
cross-rung identifiers. This module performs no filesystem or network IO.
"""
from __future__ import annotations

from collections import defaultdict
import json
import re
from typing import Any

from .access import AccessResult
from .binding_context import BindingContextResult, validate_binding_context
from .calculations import CalculationResult
from .conditions import ConditionResult
from .ladder.syntax import (Branch, Instruction, NAME, PUBLIC_OPCODES, RungSyntaxError,
                            Sequence, measure, parse_rung)
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult

REQUEST_ID = 'rung-cases-1'
MAX_BYTES = 16 * 1024
MAX_RAW_TEXT = 8192
MAX_SAMPLE_TEXT = 2048
MAX_INSTRUCTIONS = 24
MAX_DEPTH = 4
MAX_BRANCH_LEGS = 16
MAX_TOKENS = 128
MAX_SAMPLES = 6
SLOTS = ('dynamic_index_1', 'dynamic_index_2', 'unknown_block_1',
         'opaque_ons_1', 'opaque_sfr_1', 'branched_output_1')
STATUSES = frozenset({'included', 'not_found', 'too_large', 'unsupported_lexical', 'budget_exhausted'})
KINDS = frozenset({'integer', 'real', 'radix', 'text'})
_FIELDS = frozenset({'schema_version', 'request_id', 'budget_scope', 'source_rungs',
                     'prior_reserved_rungs', 'max_total_rungs', 'charged_rungs',
                     'total_reserved_rungs', 'cases', 'samples'})
_SAMPLE_FIELDS = frozenset({'id', 'rung_text', 'literal_kinds', 'unlisted_opcode'})
_ROOT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z0-9_]+)*', re.ASCII)
_NUMBER = re.compile(r'(?:2#[01](?:_?[01])*|8#[0-7](?:_?[0-7])*|16#[0-9A-Fa-f](?:_?[0-9A-Fa-f])*'
                     r'|(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)', re.ASCII)
_PLACEHOLDER = re.compile(r'(ROOT|MEMBER|BIT|LITERAL)_([1-9][0-9]*)', re.ASCII)
_OPERATORS = ('**', '<=', '>=', '<>', '!=', '==', '+', '-', '*', '/', '%', '^', '=', '<', '>', '&', '|', '!', '~', '?')
_WORD_OPERATORS = frozenset({'AND', 'OR', 'XOR', 'NOT', 'MOD'})
# Freeze the current family partition for this immutable request. A familiar
# public mnemonic can still have an unknown family (for example CMP).
_FAMILY_OPCODES = frozenset('''XIC XIO EQU NEQ LES LEQ GRT GEQ LIM OTE OTL OTU ONS OSR OSF
ADD SUB MUL DIV ABS LN SQR CPT AVE FAL TON TOF RTO RES CTU CTD MOV MVM SWPB CLR COP CPS
MSG GSV SSV SFR SQO JMP LBL JSR SBR RET PID ALMA ALMD ASO'''.split())
_COMPARISONS = {'EQU': 2, 'NEQ': 2, 'LES': 2, 'LEQ': 2, 'GRT': 2, 'GEQ': 2, 'LIM': 3}


class TargetedSamplesError(ValueError):
    """Source-free rejection of a sample record or its source evidence."""


class _Withhold(Exception):
    def __init__(self, status: str):
        self.status = status


def _invalid() -> None:
    raise TargetedSamplesError('Targeted sample evidence is invalid.')


def _withhold(status: str = 'unsupported_lexical') -> None:
    raise _Withhold(status)


def _string_end(text: str, start: int) -> int:
    quote, pos = text[start], start + 1
    while pos < len(text):
        if text[pos] == '$':
            pos += 2
        elif text[pos] == quote:
            if pos + 1 < len(text) and text[pos + 1] == quote:
                pos += 2
            else:
                return pos + 1
        else:
            pos += 1
    _withhold()
    raise AssertionError('unreachable')


def _tokens(text: str, *, public: bool, kinds: dict[str, str]) -> list[tuple[str, str]]:
    """Consume every character; punctuation, strings and numbers never fall back."""
    result: list[tuple[str, str]] = []
    pos = 0
    closing: list[str] = []
    member = False
    while pos < len(text):
        char = text[pos]
        if char in ' \t\r\n':
            pos += 1
            continue
        if len(result) >= MAX_TOKENS:
            _withhold('too_large')
        if char in "'\"":
            if public or member:
                _withhold()
            end = _string_end(text, pos)
            result.append(('LITERAL:text', text[pos:end]))
        elif member and char.isascii() and char.isdigit():
            match = re.match(r'[0-9]+', text[pos:], re.ASCII)
            assert match is not None
            end = pos + len(match.group())
            if public:
                _withhold()
            result.append(('BIT', text[pos:end]))
        elif char.isascii() and (char.isdigit() or char == '.' and pos + 1 < len(text) and text[pos + 1].isdigit()
                                and not (result and (result[-1][0] in {'ROOT', 'MEMBER', 'BIT'} or result[-1] == ('fixed', ']')))):
            if public or member:
                _withhold()
            match = _NUMBER.match(text, pos)
            if match is None:
                _withhold()
            end = match.end()
            value = match.group()
            kind = 'radix' if '#' in value else 'real' if any(c in value for c in '.eE') else 'integer'
            result.append((f'LITERAL:{kind}', value))
        elif (match := _ROOT.match(text, pos)) is not None:
            value, end = match.group(), match.end()
            if member:
                if ':' in value:
                    _withhold()
                kind = 'MEMBER'
            else:
                kind = 'ROOT'
                # Operator words are fixed only in an operator position. An
                # identically spelled standalone tag or array root is scrubbed.
                remaining = text[end:].lstrip(' \t\r\n')
                after_value = bool(result and (result[-1][0] != 'fixed' or result[-1][1] in {')', ']'}))
                if value in _WORD_OPERATORS and remaining and remaining[0] not in '[.,)]':
                    if value == 'NOT' and not after_value or value != 'NOT' and after_value:
                        kind = 'fixed'
            if public and kind != 'fixed':
                placeholder = _PLACEHOLDER.fullmatch(value)
                if placeholder is None:
                    _withhold()
                label_kind = placeholder[1]
                if member and label_kind not in {'MEMBER', 'BIT'} or not member and label_kind not in {'ROOT', 'LITERAL'}:
                    _withhold()
                kind = label_kind
                if kind == 'LITERAL':
                    if value not in kinds:
                        _withhold()
                    kind = f'LITERAL:{kinds[value]}'
            result.append((kind, value))
        elif char in '([.,)]':
            end = pos + 1
            if member:
                _withhold()
            if char in '([':
                if len(closing) >= MAX_DEPTH:
                    _withhold('too_large')
                closing.append(')' if char == '(' else ']')
            elif char in ')]':
                if not closing or closing.pop() != char:
                    _withhold()
            result.append(('fixed', char))
            member = char == '.'
            pos = end
            continue
        else:
            operator = next((op for op in _OPERATORS if text.startswith(op, pos)), None)
            if operator is None or member:
                _withhold()
            result.append(('fixed', operator))
            end = pos + len(operator)
        member = False
        pos = end
    if member or closing:
        _withhold()
    return result


def _shape(tree: Sequence, unknown: str | None) -> tuple[Any, ...]:
    return tuple(('instruction', item.opcode if item.opcode in PUBLIC_OPCODES else 'UNLISTED_OP_1',
                  len(item.arguments), tuple(not arg.strip() for arg in item.arguments))
                 if isinstance(item, Instruction) else ('branch', tuple(_shape(leg, unknown) for leg in item.legs))
                 for item in tree.items)


def _convert(text: str, *, public: bool = False, supplied_kinds: dict[str, str] | None = None,
             supplied_unknown: str | None = None) -> tuple[str, dict[str, str], str | None, dict[str, Any]]:
    if len(text) > (MAX_SAMPLE_TEXT if public else MAX_RAW_TEXT):
        _withhold('too_large')
    tree = parse_rung(text)
    metrics = measure(tree)
    if metrics['instruction_calls'] > MAX_INSTRUCTIONS or metrics['max_branch_depth'] > MAX_DEPTH or metrics['branch_legs'] > MAX_BRANCH_LEGS:
        _withhold('too_large')
    labels: dict[str, dict[str, str]] = {key: {} for key in ('ROOT', 'MEMBER', 'BIT', 'LITERAL')}
    literal_kinds: dict[str, str] = {}
    unknown: str | None = None
    token_count = 1  # final semicolon
    traces: list[tuple[tuple[str, str], ...]] = []
    opcodes: list[tuple[str, int]] = []
    dynamic_uses = 0

    def argument(raw: str) -> str:
        nonlocal token_count, dynamic_uses
        tokens = _tokens(raw, public=public, kinds=supplied_kinds or {})
        token_count += len(tokens)
        if token_count > MAX_TOKENS:
            _withhold('too_large')
        rendered: list[str] = []
        trace: list[tuple[str, str]] = []
        dynamic = False
        bracket: list[list[tuple[str, str]]] = []
        for kind, value in tokens:
            if kind == 'fixed':
                label = value
            else:
                label_kind = kind.split(':')[0]
                mapping = labels[label_kind]
                if value not in mapping:
                    mapping[value] = f'{label_kind}_{len(mapping) + 1}'
                label = mapping[value]
                if public and label != value:
                    _withhold()
                if label_kind == 'LITERAL':
                    literal_kinds[label] = kind.split(':')[1]
            if value == '[' and kind == 'fixed':
                bracket.append([])
            elif value == ']' and kind == 'fixed':
                content = bracket.pop()
                # Plain integer dimensions remain static. Every other index
                # shape is potentially dynamic, including a constant formula.
                static = bool(content) and all(k == 'LITERAL:integer' if n % 2 == 0 else (k, v) == ('fixed', ',')
                                               for n, (k, v) in enumerate(content)) and len(content) % 2 == 1
                dynamic |= not static
            elif bracket:
                bracket[-1].append((kind, value))
            rendered.append(label)
            trace.append((kind, label))
        dynamic_uses += int(dynamic)
        traces.append(tuple(trace))
        return ' '.join(rendered)

    def sequence(items: Sequence) -> str:
        nonlocal token_count, unknown
        rendered = []
        for item in items.items:
            if isinstance(item, Branch):
                token_count += 2 + len(item.legs) - 1
                rendered.append('[' + ','.join(sequence(leg) for leg in item.legs) + ']')
                continue
            opcode = item.opcode
            if public and opcode == 'UNLISTED_OP_1':
                if supplied_unknown is None:
                    _withhold()
                unknown = supplied_unknown
            elif opcode not in PUBLIC_OPCODES:
                if public or opcode == 'UNLISTED_OP_1' or NAME.fullmatch(opcode) is None or len(opcode) > 64 or unknown is not None and unknown != opcode:
                    _withhold()
                unknown = opcode
                opcode = 'UNLISTED_OP_1'
            opcodes.append((opcode if opcode != 'UNLISTED_OP_1' else unknown or '', len(item.arguments)))
            token_count += 3 + max(0, len(item.arguments) - 1)
            rendered.append(opcode + '(' + ','.join(argument(raw) for raw in item.arguments) + ')')
        return ''.join(rendered)

    result = sequence(tree) + ';'
    if token_count > MAX_TOKENS or len(result) > MAX_SAMPLE_TEXT:
        _withhold('too_large')
    if public:
        if result != text or literal_kinds != supplied_kinds or unknown != supplied_unknown:
            _withhold()
    else:
        # Reparse the actual public bytes. Both structural and lexical traces
        # must survive; whitespace and opaque value spelling are the only loss.
        _, _, _, checked = _convert(result, public=True, supplied_kinds=literal_kinds, supplied_unknown=unknown)
        if _shape(tree, unknown) != _shape(parse_rung(result), unknown) or checked['trace'] != traces:
            _withhold()
    evidence = {'trace': traces, 'opcodes': opcodes, 'dynamic_uses': dynamic_uses,
                'branched': bool(metrics['branch_groups'])}
    return result, literal_kinds, unknown, evidence


def _native(record: Any) -> None:
    """Bound native containers before any membership, encoding or iteration hook."""
    stack, seen, count, characters = [(record, 0)], set(), 0, 0
    while stack:
        value, depth = stack.pop()
        count += 1
        if count > 4000 or depth > 8:
            _invalid()
        kind = type(value)
        if kind in (dict, list):
            if id(value) in seen or len(value) > 256:
                _invalid()
            seen.add(id(value))
            if kind is dict:
                for key, child in value.items():
                    if type(key) is not str or len(key) > 64:
                        _invalid()
                    characters += len(key)
                    stack.append((child, depth + 1))
            else:
                stack.extend((child, depth + 1) for child in value)
        elif kind is str:
            if len(value) > MAX_SAMPLE_TEXT:
                _invalid()
            characters += len(value)
        elif kind is int:
            if not 0 <= value <= 2_147_483_647:
                _invalid()
        elif value is not None:
            _invalid()
        if characters > MAX_BYTES:
            _invalid()


def validate_targeted_samples(record: dict[str, Any]) -> None:
    """Validate public shape, scrubbing, case eligibility and budget conservation.

    The independent immutable-history guard supplies provenance on later runs;
    this validator cannot authenticate an arbitrary record against absent L5X.
    """
    try:
        _native(record)
        if type(record) is not dict or record.keys() != _FIELDS:
            _invalid()
        if record['schema_version'] != 1 or record['request_id'] != REQUEST_ID or record['budget_scope'] != 'new_informative_examples' or record['prior_reserved_rungs'] != 2:
            _invalid()
        for key in ('schema_version', 'source_rungs', 'prior_reserved_rungs', 'max_total_rungs', 'charged_rungs', 'total_reserved_rungs'):
            if type(record[key]) is not int:
                _invalid()
        cases, samples = record['cases'], record['samples']
        if type(cases) is not list or len(cases) != len(SLOTS) or type(samples) is not list or len(samples) > MAX_SAMPLES:
            _invalid()
        maximum = min(40, record['source_rungs'] // 50)
        if record['max_total_rungs'] != maximum or record['charged_rungs'] != len(samples) or record['total_reserved_rungs'] != 2 + len(samples) or len(samples) > max(0, maximum - 2):
            _invalid()
        by_id, unknowns = {}, set()
        for index, sample in enumerate(samples, 1):
            if type(sample) is not dict or sample.keys() != _SAMPLE_FIELDS or sample['id'] != f'sample_{index}':
                _invalid()
            if type(sample['rung_text']) is not str or type(sample['literal_kinds']) is not dict:
                _invalid()
            if any(value not in KINDS for value in sample['literal_kinds'].values()):
                _invalid()
            unknown = sample['unlisted_opcode']
            if unknown is not None:
                if type(unknown) is not str or len(unknown) > 64 or NAME.fullmatch(unknown) is None or unknown in PUBLIC_OPCODES or unknown == 'UNLISTED_OP_1':
                    _invalid()
                unknowns.add(unknown)
            _, _, _, evidence = _convert(sample['rung_text'], public=True,
                                         supplied_kinds=sample['literal_kinds'], supplied_unknown=unknown)
            by_id[sample['id']] = evidence
        if len(unknowns) > 1 or sum(sample['unlisted_opcode'] is not None for sample in samples) > 1:
            _invalid()
        referenced: list[str] = []
        dynamic_counts: dict[str, int] = defaultdict(int)
        for slot, case in zip(SLOTS, cases):
            if type(case) is not dict or case.keys() != {'slot', 'status', 'sample_id'} or case['slot'] != slot or case['status'] not in STATUSES:
                _invalid()
            identifier = case['sample_id']
            if case['status'] != 'included':
                if identifier is not None:
                    _invalid()
                continue
            if type(identifier) is not str or identifier not in by_id:
                _invalid()
            if identifier not in referenced:
                referenced.append(identifier)
            evidence = by_id[identifier]
            opcodes = evidence['opcodes']
            if slot.startswith('dynamic_index_'):
                dynamic_counts[identifier] += 1
                if evidence['dynamic_uses'] < dynamic_counts[identifier]:
                    _invalid()
            elif slot == 'unknown_block_1' and not any(op not in _FAMILY_OPCODES for op, _ in opcodes):
                _invalid()
            elif slot == 'opaque_ons_1' and not any(op == 'ONS' for op, _ in opcodes):
                _invalid()
            elif slot == 'opaque_sfr_1' and not any(op == 'SFR' for op, _ in opcodes):
                _invalid()
            elif slot == 'branched_output_1' and not (evidence['branched'] and any(_COMPARISONS.get(op) == arity for op, arity in opcodes)
                                                     and any(op in {'OTE', 'OTL', 'OTU'} and arity == 1 for op, arity in opcodes)):
                _invalid()
        if referenced != list(by_id):
            _invalid()
        if unknowns:
            clue = next(sample['id'] for sample in samples if sample['unlisted_opcode'] is not None)
            if cases[2]['status'] != 'included' or cases[2]['sample_id'] != clue:
                _invalid()
        if len(_encode(record).encode('utf-8')) > MAX_BYTES:
            _invalid()
    except TargetedSamplesError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError, _Withhold):
        _invalid()


def _encode(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(',', ':')) + '\n'


def render_targeted_samples_json(record: dict[str, Any]) -> str:
    validate_targeted_samples(record)
    return _encode(record)


render_targeted_samples = render_targeted_samples_json


def build_targeted_samples(snapshot: SourceSnapshot, inventory: InventoryResult, references: ReferenceResult,
                           access: AccessResult, calculations: CalculationResult, rung_analysis: RungAnalysisResult,
                           relationships: RelationshipResult, conditions: ConditionResult,
                           binding_context: BindingContextResult) -> dict[str, Any]:
    """Select first occurrences once; a withheld candidate never advances the scan."""
    try:
        validate_binding_context(snapshot, inventory, references, access, calculations,
                                 rung_analysis, relationships, conditions, binding_context)
        # This frozen request targets ordinary known-role operand slots only.
        # CPT reference leaves remain a separate population and cannot fill it.
        eligible = {row['source_id'] for row in binding_context.gaps
                    if row['kind'] == 'operand' and row['category'] == 'non_static_array_index'}
        use_order: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
        for row in access.operands:
            if row['id'] in eligible:
                use_order[row['instruction_id']].append((row['argument_index'], -1, row['id']))
        unknown_blocks = {row['id'] for row in rung_analysis.blocks if row['family'] == 'unknown'}
        opaque = {row['instruction_id'] for row in conditions.nodes if row['kind'] == 'opaque_transfer'}
        instruction_opcodes = {row['id']: row['opcode'] for row in access.instructions}
        comparison_rungs = {row['rung_id'] for row in conditions.nodes if row['kind'] == 'predicate'
                            and instruction_opcodes[row['instruction_id']] in _COMPARISONS}
        output_rungs = {row['rung_id'] for row in conditions.outputs if row['action'] != 'unresolved'}
        branched = {row['id'] for row in rung_analysis.rungs if row['structure'] == 'branched'}
        branched_outputs = comparison_rungs & output_rungs & branched
        selected: dict[str, Any] = {}
        selected_unknown: str | None = None
        dynamic_count = 0
        for rung in inventory.rungs:
            for instruction in rung.instructions:
                for _ in sorted(use_order.get(instruction.id, [])):
                    dynamic_count += 1
                    if dynamic_count <= 2:
                        selected[f'dynamic_index_{dynamic_count}'] = rung
                if instruction.id in unknown_blocks:
                    if 'unknown_block_1' not in selected:
                        selected['unknown_block_1'] = rung
                        selected_unknown = instruction.opcode if instruction.opcode not in PUBLIC_OPCODES else None
                if instruction.id in opaque and instruction.opcode.upper() in {'ONS', 'SFR'}:
                    selected.setdefault(f'opaque_{instruction.opcode.lower()}_1', rung)
            if rung.id in branched_outputs:
                selected.setdefault('branched_output_1', rung)
        maximum = min(40, len(inventory.rungs) // 50)
        result = {'schema_version': 1, 'request_id': REQUEST_ID, 'budget_scope': 'new_informative_examples',
                  'source_rungs': len(inventory.rungs), 'prior_reserved_rungs': 2, 'max_total_rungs': maximum,
                  'charged_rungs': 0, 'total_reserved_rungs': 2, 'cases': [], 'samples': []}
        attempted: dict[str, tuple[str, str | None]] = {}
        for slot in SLOTS:
            rung = selected.get(slot)
            status, sample_id = 'not_found', None
            if rung is not None:
                if rung.id in attempted:
                    status, sample_id = attempted[rung.id]
                elif len(result['samples']) >= max(0, maximum - 2):
                    status = 'budget_exhausted'
                else:
                    try:
                        if rung.text is None:
                            _withhold()
                        text, kinds, unknown, _ = _convert(rung.text)
                        if unknown is not None and (unknown != selected_unknown or rung.id != selected['unknown_block_1'].id):
                            _withhold()
                        sample_id = f"sample_{len(result['samples']) + 1}"
                        sample = {'id': sample_id, 'rung_text': text,
                                  'literal_kinds': kinds, 'unlisted_opcode': unknown}
                        # Reserve the longest case fields before retaining any
                        # new sample. Later statuses cannot push the bundle over
                        # its byte cap or cause a partial/raw fallback.
                        preview = {**result, 'samples': [*result['samples'], sample],
                                   'charged_rungs': len(result['samples']) + 1,
                                   'total_reserved_rungs': len(result['samples']) + 3,
                                   'cases': [{'slot': name, 'status': 'unsupported_lexical',
                                              'sample_id': 'sample_6'} for name in SLOTS]}
                        if len(_encode(preview).encode('utf-8')) > MAX_BYTES:
                            sample_id = None
                            _withhold('too_large')
                        result['samples'].append(sample)
                        status = 'included'
                    except _Withhold as exc:
                        status = exc.status
                    except RungSyntaxError:
                        status = 'unsupported_lexical'
                attempted[rung.id] = status, sample_id
            result['cases'].append({'slot': slot, 'status': status, 'sample_id': sample_id})
        result['charged_rungs'] = len(result['samples'])
        result['total_reserved_rungs'] = 2 + result['charged_rungs']
        validate_targeted_samples(result)
        return result
    except TargetedSamplesError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
