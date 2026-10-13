"""Conservative, snapshot-bound root bindings for private L5X source evidence.

A root binding does not validate a member, an array bound, a data type, or an
instruction's effects. Unknown operand roles and expressions remain explicit
gaps. This module does no IO and never changes the source inventory.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import hashlib
import re
from typing import Any

from .models import EntityRecord, InventoryResult

MAX_OPERANDS = 250_000
MAX_ALIAS_DEPTH = 64
MAX_ADDRESS_LENGTH = 65_536
MAX_EXPANDED_EVIDENCE_CHARS = 8_000_000

OPERAND_STATUSES = frozenset({
    'root_bound', 'unresolved', 'ambiguous', 'alias_cycle', 'alias_depth_limit',
    'unsupported_address', 'unsupported_expression', 'literal', 'non_data',
    'unsupported_instruction', 'argument_count_mismatch', 'empty',
})
ALIAS_STATUSES = frozenset({
    'root_bound', 'unresolved', 'ambiguous', 'alias_cycle', 'alias_depth_limit',
    'unsupported_address',
})

# These are operand-role contracts, not instruction execution models. Keeping
# the initial list small avoids turning labels, class names or opaque AOI slots
# into plausible-looking tag references. "address" also admits literal values.
_ARITIES = {
    'XIC': 1, 'XIO': 1, 'OTE': 1, 'OTL': 1, 'OTU': 1, 'ONS': 1,
    'MOV': 2, 'ADD': 3, 'SUB': 3, 'MUL': 3, 'DIV': 3,
    'EQU': 2, 'NEQ': 2, 'LES': 2, 'LEQ': 2, 'GRT': 2, 'GEQ': 2,
    'LIM': 3, 'CLR': 1, 'CPT': 2, 'JMP': 1, 'LBL': 1,
    'TON': 3, 'TOF': 3, 'RTO': 3, 'OSF': 2, 'OSR': 2, 'RES': 1,
    'COP': 3, 'CPS': 3, 'PID': 7,
}
_SYMBOL_KINDS = frozenset({'tag', 'aoi_parameter', 'aoi_local_tag'})
_ATTRIBUTES = frozenset({
    'Name', 'TagType', 'DataType', 'Dimensions', 'AliasFor', 'Usage',
    'ExternalAccess', 'Required', 'Visible',
})
_ROOT_TEXT = r'[A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z0-9_]+)*'
_ROOT = re.compile(_ROOT_TEXT)
_ADDRESS = re.compile(
    rf'(?P<root>{_ROOT_TEXT})(?P<suffix>'
    r'(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\s*[0-9]+(?:\s*,\s*[0-9]+)*\s*\])*'
    r'(?:\.[0-9]+)?)', re.ASCII,
)
_NUMBER = re.compile(
    r'[+-]?(?:(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?'
    r'|2#[01](?:_?[01])*|8#[0-7](?:_?[0-7])*'
    r'|16#[0-9A-Fa-f](?:_?[0-9A-Fa-f])*)', re.ASCII,
)
_STRINGS = tuple(re.compile(rf'{quote}(?:[^{quote}$]|\$.|{quote}{quote})*{quote}', re.DOTALL)
                 for quote in ("'", '"'))


class ReferenceError(ValueError):
    """Fatal analysis error whose message never includes source evidence."""


@dataclass(frozen=True)
class ReferenceResult:
    snapshot: dict[str, str | int]
    symbols: list[dict[str, Any]]
    aliases: list[dict[str, Any]]
    operands: list[dict[str, Any]]
    coverage: dict[str, str | int]
    status: str
    schema_version: int = 1
    analyzer_version: str = 'source-references-1'
    analysis_scope: str = 'scoped_root_bindings'
    semantic_analysis: str = 'not_implemented'
    effect_analysis: str = 'not_implemented'
    member_validation: str = 'not_implemented'

    def to_dict(self) -> dict[str, Any]:
        """Return private records, including names and operands; never publish."""
        return asdict(self)


def _is_alias(entity: EntityRecord) -> bool:
    return (entity.attributes.get('TagType') == 'Alias'
            or entity.kind in {'aoi_parameter', 'aoi_local_tag'}
            and 'AliasFor' in entity.attributes)


def _address(raw: str) -> tuple[str, str] | None:
    value = raw.strip()
    if len(value) > MAX_ADDRESS_LENGTH or value.lower().startswith('program:'):
        return None
    match = _ADDRESS.fullmatch(value)
    return (match['root'], match['suffix']) if match else None


def _literal(raw: str) -> bool:
    return bool(_NUMBER.fullmatch(raw) or any(pattern.fullmatch(raw) for pattern in _STRINGS))


def _binding(status: str, symbol_id: str | None = None,
             target_id: str | None = None, suffix: str = '',
             alias_chain: list[str] | None = None) -> dict[str, Any]:
    return {'status': status, 'symbol_id': symbol_id, 'target_id': target_id,
            'suffix': suffix, 'alias_chain': list(alias_chain or [])}


class _Resolver:
    def __init__(self, inventory: InventoryResult):
        self.entities = {entity.id: entity for entity in inventory.entities}
        self.symbols = [entity for entity in inventory.entities if entity.kind in _SYMBOL_KINDS]
        self.index: dict[tuple[str, str], list[EntityRecord]] = defaultdict(list)
        self.unnamed = 0
        for symbol in self.symbols:
            if (not symbol.name or not _ROOT.fullmatch(symbol.name)
                    or symbol.name.lower().startswith('program:')):
                self.unnamed += 1
                continue
            if symbol.scope_id is not None:
                self.index[symbol.scope_id, symbol.name.lower()].append(symbol)
        self.ambiguous = sum(len(group) > 1 for group in self.index.values())

    def lookup(self, name: str, scope_id: str | None,
               aoi_local_only: bool = False) -> tuple[str, EntityRecord | None]:
        scope = self.entities.get(scope_id) if scope_id else None
        if scope is None or scope.kind not in {'program', 'controller', 'aoi'}:
            return 'unresolved', None
        scopes = [scope.id]
        # AOIs are isolated templates. A program may only fall back to its own
        # controller, never to another program or an unrelated controller.
        if scope.kind == 'program':
            controller = self.entities.get(scope.scope_id)
            if controller is not None and controller.kind == 'controller':
                scopes.append(controller.id)
        for candidate_scope in scopes:
            matches = self.index.get((candidate_scope, name.lower()), [])
            if matches:
                # A colliding declaration is ambiguous before kind filtering;
                # an invalid AOI duplicate must not appear uniquely resolvable.
                if len(matches) != 1:
                    return 'ambiguous', None
                if aoi_local_only and matches[0].kind != 'aoi_local_tag':
                    return 'unresolved', None
                return 'root_bound', matches[0]
        return 'unresolved', None

    def resolve(self, raw: str, scope_id: str | None, *,
                chain: list[str] | None = None, aoi_local_only: bool = False) -> dict[str, Any]:
        chain = list(chain or [])
        parsed = _address(raw)
        if parsed is None:
            return _binding('unsupported_address', alias_chain=chain)
        root, suffix = parsed
        status, symbol = self.lookup(root, scope_id, aoi_local_only)
        if symbol is None:
            return _binding(status, suffix=suffix, alias_chain=chain)
        first_id = symbol.id
        seen = set(chain)
        while _is_alias(symbol):
            if symbol.id in seen:
                return _binding('alias_cycle', first_id, suffix=suffix, alias_chain=chain)
            if len(chain) >= MAX_ALIAS_DEPTH:
                return _binding('alias_depth_limit', first_id, suffix=suffix, alias_chain=chain)
            chain.append(symbol.id)
            seen.add(symbol.id)
            parsed = _address(symbol.attributes.get('AliasFor', ''))
            if parsed is None:
                return _binding('unsupported_address', first_id, suffix=suffix, alias_chain=chain)
            root, next_suffix = parsed
            if len(next_suffix) + len(suffix) > MAX_ADDRESS_LENGTH:
                return _binding('unsupported_address', first_id, suffix=suffix, alias_chain=chain)
            suffix = next_suffix + suffix
            # The alias target is resolved in the declaration's own scope,
            # regardless of the program that referenced the alias.
            status, symbol = self.lookup(root, symbol.scope_id,
                                         symbol.kind == 'aoi_parameter')
            if symbol is None:
                return _binding(status, first_id, suffix=suffix, alias_chain=chain)
        return _binding('root_bound', first_id, symbol.id, suffix, chain)


def analyze_references(inventory: InventoryResult) -> ReferenceResult:
    """Bind explicit catalogued operand roots to snapshot declaration IDs.

    All occurrence records remain separate. Alias suffixes are evidence strings
    assembled in target-to-caller order, not validated addresses. Root binding
    deliberately does not prove that an instruction accepts the given value.
    """
    if inventory.parser_version != 'source-inventory-1' or inventory.schema_version != 1:
        raise ReferenceError('Unsupported source inventory version.')
    operand_total = sum(len(instruction.arguments) for rung in inventory.rungs
                        if rung.parse_status == 'parsed' for instruction in rung.instructions)
    if operand_total > MAX_OPERANDS:
        raise ReferenceError('Reference analysis exceeds the operand limit.')
    resolver = _Resolver(inventory)
    symbols = [
        {'id': entity.id, 'name': entity.name, 'scope_id': entity.scope_id,
         'kind': entity.kind,
         'attributes': {key: value for key, value in entity.attributes.items() if key in _ATTRIBUTES}}
        for entity in resolver.symbols
    ]
    expanded_characters = 0

    def account_expansion(binding: dict[str, Any]) -> None:
        nonlocal expanded_characters
        # Bound retained evidence across the entire result, not just each
        # traversal: many callers may expand the same long alias chain.
        expanded_characters += len(binding['suffix']) + sum(map(len, binding['alias_chain']))
        if expanded_characters > MAX_EXPANDED_EVIDENCE_CHARS:
            raise ReferenceError('Reference analysis exceeds the expanded-evidence limit.')

    aliases: list[dict[str, Any]] = []
    for entity in resolver.symbols:
        if _is_alias(entity):
            binding = resolver.resolve(entity.attributes.get('AliasFor', ''), entity.scope_id,
                                       chain=[entity.id], aoi_local_only=entity.kind == 'aoi_parameter')
            account_expansion(binding)
            aliases.append({'source_id': entity.id, 'scope_id': entity.scope_id,
                            'raw_target': entity.attributes.get('AliasFor', ''), **binding})
    operands: list[dict[str, Any]] = []
    instructions_total = instructions_catalogued = rungs_analyzed = 0
    for rung in inventory.rungs:
        if rung.parse_status != 'parsed':
            continue
        rungs_analyzed += 1
        for instruction in rung.instructions:
            instructions_total += 1
            arity = _ARITIES.get(instruction.opcode.upper())
            valid_arity = arity is not None and len(instruction.arguments) == arity
            instructions_catalogued += int(valid_arity)
            for index, raw in enumerate(instruction.arguments):
                value = raw.strip()
                if arity is None:
                    binding = _binding('unsupported_instruction')
                elif not valid_arity:
                    binding = _binding('argument_count_mismatch')
                elif not value:
                    binding = _binding('empty')
                elif instruction.opcode.upper() in {'JMP', 'LBL'}:
                    binding = _binding('non_data')
                elif instruction.opcode.upper() == 'CPT' and index == 1:
                    binding = _binding('unsupported_expression')
                elif _literal(value):
                    binding = _binding('literal')
                else:
                    binding = resolver.resolve(value, rung.scope_id)
                account_expansion(binding)
                occurrence = f"{inventory.snapshot['id']}\0{instruction.id}\0{index}"
                operand_id = 'operand_' + hashlib.sha256(occurrence.encode('utf-8')).hexdigest()
                operands.append({
                    'id': operand_id, 'instruction_id': instruction.id, 'rung_id': rung.id,
                    'scope_id': rung.scope_id, 'argument_index': index, 'raw_text': raw,
                    **binding,
                })
    coverage: dict[str, str | int] = {
        'source_status': inventory.status, 'rungs_total': len(inventory.rungs),
        'rungs_analyzed': rungs_analyzed, 'instructions_total': instructions_total,
        'instructions_catalogued': instructions_catalogued, 'operands_total': len(operands),
        'ambiguous_symbol_groups': resolver.ambiguous, 'unnamed_symbols': resolver.unnamed,
    }
    partial = (inventory.status != 'complete' or resolver.ambiguous or resolver.unnamed
               or instructions_catalogued != instructions_total
               or any(row['status'] != 'root_bound' for row in aliases)
               or any(row['status'] not in {'root_bound', 'literal', 'non_data'} for row in operands))
    return ReferenceResult(dict(inventory.snapshot), symbols, aliases, operands,
                           coverage, 'partial' if partial else 'complete')


def _strict_record_match(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    """Compare only the canonical tree's bounded shape, without coercion.

    Traversal follows expected containers, so a malformed or cyclic candidate
    cannot add recursive work. Exact built-in types avoid custom equality or
    mapping methods and keep bool distinct from int. No candidate serialization
    or dataclass deep-copy occurs before the shape is checked.
    """
    pending: list[tuple[Any, Any]] = [(expected, actual)]
    while pending:
        expected_value, actual_value = pending.pop()
        value_type = type(expected_value)
        if type(actual_value) is not value_type:
            return False
        if value_type is dict:
            if len(expected_value) != len(actual_value):
                return False
            if (any(type(key) is not str for key in actual_value)
                    or expected_value.keys() != actual_value.keys()):
                return False
            pending.extend((value, actual_value[key]) for key, value in expected_value.items())
        elif value_type is list:
            if len(expected_value) != len(actual_value):
                return False
            pending.extend(zip(expected_value, actual_value))
        elif value_type not in {str, int, bool, type(None)} or expected_value != actual_value:
            return False
    return True


def validate_references(inventory: InventoryResult, references: ReferenceResult) -> None:
    """Verify derived records against canonical analysis of captured inventory.

    This does not reread XML or source files. Reanalysis uses the analyzer's
    existing resource budgets and catches changes to every field, including
    source links, alias evidence, statuses, metadata and coverage. Persisting or
    publishing code should call this before using caller-supplied records.
    """
    try:
        valid = (type(references) is ReferenceResult
                 and _strict_record_match(vars(analyze_references(inventory)), vars(references)))
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError):
        valid = False
    if not valid:
        raise ReferenceError('Reference records do not match the source inventory.') from None
