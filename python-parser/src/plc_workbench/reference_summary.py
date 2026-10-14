"""Closed, count-only publication boundary for private source root bindings.

No names, source identities, addresses, per-occurrence relationships, or alias
chains cross this boundary. The nested source summary is the only code-revision
record. Root binding does not establish member validity or instruction effects.
"""
from __future__ import annotations

from collections import Counter
import json
from typing import Any, TYPE_CHECKING

from .models import InventoryResult
from .module_io import MODULE_IO_KINDS, NAME_ORIGINS, NAME_REASONS
from .references import (
    ALIAS_STATUSES, OPERAND_STATUSES, UNRESOLVED_REASONS, UNSUPPORTED_ADDRESS_REASONS,
    ReferenceError, _address, validate_references,
)
from .summary import SummaryError, build_summary, validate_summary

if TYPE_CHECKING:
    from .references import ReferenceResult

MAX_REPORT_BYTES = 32 * 1024
MAX_COUNT = 10**12
LEGACY_SYMBOL_KINDS = frozenset({'tag', 'aoi_local_tag', 'aoi_parameter'})
SYMBOL_KINDS = LEGACY_SYMBOL_KINDS | frozenset(MODULE_IO_KINDS)
REASONS_BY_STATUS = {'unresolved': frozenset(UNRESOLVED_REASONS),
                     'unsupported_address': frozenset(UNSUPPORTED_ADDRESS_REASONS)}
COMPLETE_OPERAND_STATUSES = frozenset({'root_bound', 'literal', 'non_data'})
MALFORMED_ADDRESS_SHAPES = frozenset({
    'alias_target_failure', 'leading_hash_static_address', 'leading_hash_other',
    'contains_brackets', 'contains_colon', 'contains_dot', 'other_form',
})
LEGACY_CONSTANTS = {
    'schema_version': 1,
    'policy_version': 2,
    'report_kind': 'l5x_reference_review_summary',
    'exporter_version': 'reference-summary-1',
    'analyzer_version': 'source-references-1',
    'analysis_scope': 'scoped_root_bindings',
    'semantic_analysis': 'not_implemented',
    'effect_analysis': 'not_implemented',
    'member_validation': 'not_implemented',
    'sharing_status': 'aggregate_sync_allowed',
}
V2_CONSTANTS = LEGACY_CONSTANTS | {
    'schema_version': 2,
    'exporter_version': 'reference-summary-2',
    'analyzer_version': 'source-references-2',
}
V3_CONSTANTS = V2_CONSTANTS | {
    'schema_version': 3,
    'exporter_version': 'reference-summary-3',
}
CONSTANTS = V3_CONSTANTS | {
    'schema_version': 4,
    'exporter_version': 'reference-summary-4',
    'analyzer_version': 'source-references-3',
}
_CORE_CONSTANTS = {key: V2_CONSTANTS[key] for key in (
    'schema_version', 'analyzer_version', 'analysis_scope', 'semantic_analysis',
    'effect_analysis', 'member_validation',
)}
# Private record layout stays at v2; timer slot recognition changes the analyzer.
_CORE_CONSTANTS['analyzer_version'] = CONSTANTS['analyzer_version']
_COVERAGE_KEYS = frozenset({'rungs_total', 'rungs_analyzed', 'instructions_total',
                            'instructions_catalogued'})
_CORE_COVERAGE_KEYS = _COVERAGE_KEYS | {
    'source_status', 'operands_total', 'ambiguous_symbol_groups', 'unnamed_symbols',
}
_SYMBOL_KEYS = frozenset({'id', 'name', 'scope_id', 'kind', 'attributes',
                         'name_origin', 'name_reason'})
_ALIAS_KEYS = frozenset({'source_id', 'scope_id', 'raw_target', 'status', 'symbol_id',
                        'target_id', 'suffix', 'alias_chain', 'reason'})
_OPERAND_KEYS = frozenset({'id', 'instruction_id', 'rung_id', 'scope_id', 'argument_index',
                          'raw_text', 'status', 'symbol_id', 'target_id', 'suffix', 'alias_chain', 'reason'})


class ReferenceSummaryError(ValueError):
    """Publication rejection without source-controlled details."""


def _invalid() -> None:
    raise ReferenceSummaryError('Reference summary validation failed; no summary was produced.')


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or value.keys() != expected:
        _invalid()


def _count(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= MAX_COUNT:
        _invalid()
    return value


def _counts(value: Any, expected: set[str] | frozenset[str]) -> None:
    _keys(value, expected)
    for count in value.values():
        _count(count)


def _constants(value: dict[str, Any], expected: dict[str, Any]) -> None:
    for key, fixed in expected.items():
        if type(value[key]) is not type(fixed) or value[key] != fixed:
            _invalid()


def _records(value: Any, keys: frozenset[str]) -> list[dict[str, Any]]:
    if type(value) is not list:
        _invalid()
    for record in value:
        _keys(record, keys)
    return value


def _status_counts(records: list[dict[str, Any]], allowed: frozenset[str]) -> dict[str, int]:
    counts = dict.fromkeys(sorted(allowed), 0)
    for record in records:
        status = record['status']
        if type(status) is not str or status not in allowed:
            _invalid()
        counts[status] += 1
    return counts


def _is_alias(entity: Any) -> bool:
    return (entity.kind == 'tag' and entity.attributes.get('TagType') == 'Alias'
            or (entity.kind in {'aoi_parameter', 'aoi_local_tag'}
                and 'AliasFor' in entity.attributes))


def _reason_counts(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts = {status: dict.fromkeys(sorted(allowed), 0) for status, allowed in REASONS_BY_STATUS.items()}
    for record in records:
        status, reason = record['status'], record['reason']
        if status in counts:
            if type(reason) is not str or reason not in counts[status]:
                _invalid()
            counts[status][reason] += 1
        elif reason is not None:
            _invalid()
    return counts


def _malformed_address_shapes(operands: list[dict[str, Any]]) -> dict[str, int]:
    """Partition verified malformed operand occurrences into closed observations.

    Precedence is alias failure, leading hash, brackets, colon, dot, other.
    An alias failure describes its target, not the caller's spelling. A single
    leading hash is tested against the existing address recognizer after removal;
    that observation neither admits the prefix nor binds the resulting address.
    No strings, lengths, distinct identities or per-occurrence links are emitted.
    """
    counts = dict.fromkeys(sorted(MALFORMED_ADDRESS_SHAPES), 0)
    for operand in operands:
        if operand['status'] != 'unsupported_address' or operand['reason'] != 'malformed_address':
            continue
        value = operand['raw_text'].strip()
        if operand['alias_chain']:
            shape = 'alias_target_failure'
        elif value.startswith('#'):
            parsed, _ = _address(value[1:])
            shape = 'leading_hash_static_address' if parsed is not None else 'leading_hash_other'
        elif '[' in value or ']' in value:
            shape = 'contains_brackets'
        elif ':' in value:
            shape = 'contains_colon'
        elif '.' in value:
            shape = 'contains_dot'
        else:
            shape = 'other_form'
        counts[shape] += 1
    return counts


def _module_io_counts(symbols: list[dict[str, Any]]) -> dict[str, Any]:
    origins = dict.fromkeys(sorted(NAME_ORIGINS), 0)
    reasons = dict.fromkeys(sorted(NAME_REASONS), 0)
    for symbol in symbols:
        if symbol['kind'] not in MODULE_IO_KINDS:
            continue
        origin, reason = symbol['name_origin'], symbol['name_reason']
        if type(origin) is not str or origin not in origins:
            _invalid()
        origins[origin] += 1
        if origin == 'unavailable':
            if type(reason) is not str or reason not in reasons or symbol['name'] is not None:
                _invalid()
            reasons[reason] += 1
        elif reason is not None or type(symbol['name']) is not str or not symbol['name']:
            _invalid()
    total = sum(origins.values())
    return {'total': total, 'named': total - origins['unavailable'],
            'by_name_origin': origins, 'unavailable_by_reason': reasons}


def build_reference_summary(
    inventory: InventoryResult,
    references: ReferenceResult,
    *,
    revision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconstruct aggregates only after reconciling the paired private evidence.

    The snapshot and occurrence checks happen in memory and never enter the
    report. They prevent accidentally combining results from different exports
    or publishing counts from an incomplete reference-record collection.
    """
    try:
        # Reanalyze the already captured inventory to verify target IDs and
        # chains as well as aggregate accounting. This never reopens the L5X.
        validate_references(inventory, references)
        core = references.to_dict()
        _keys(core, set(_CORE_CONSTANTS) | {
            'snapshot', 'symbols', 'aliases', 'operands', 'coverage', 'status',
        })
        _constants(core, _CORE_CONSTANTS)
        if type(core['snapshot']) is not dict or core['snapshot'] != inventory.snapshot:
            _invalid()
        source_summary = build_summary(inventory, revision=revision)
        coverage = core['coverage']
        _keys(coverage, _CORE_COVERAGE_KEYS)
        if coverage['source_status'] != inventory.status:
            _invalid()
        for key in _CORE_COVERAGE_KEYS - {'source_status'}:
            _count(coverage[key])

        symbols = _records(core['symbols'], _SYMBOL_KEYS)
        aliases = _records(core['aliases'], _ALIAS_KEYS)
        operands = _records(core['operands'], _OPERAND_KEYS)
        entities = {entity.id: entity for entity in inventory.entities if entity.kind in SYMBOL_KINDS}
        if len(symbols) != len(entities):
            _invalid()
        seen_symbols: set[str] = set()
        kinds: Counter[str] = Counter()
        for symbol in symbols:
            identifier = symbol['id']
            kind = symbol['kind']
            if (type(identifier) is not str or identifier in seen_symbols
                    or type(kind) is not str or kind not in SYMBOL_KINDS):
                _invalid()
            entity = entities.get(identifier)
            if (entity is None or kind != entity.kind
                    or (kind not in MODULE_IO_KINDS and symbol['name'] != entity.name)
                    or symbol['scope_id'] != entity.scope_id):
                _invalid()
            seen_symbols.add(identifier)
            kinds[kind] += 1

        expected_aliases = {entity.id for entity in entities.values() if _is_alias(entity)}
        seen_aliases: set[str] = set()
        for alias in aliases:
            identifier = alias['source_id']
            if (type(identifier) is not str or identifier not in expected_aliases
                    or identifier in seen_aliases
                    or alias['scope_id'] != entities[identifier].scope_id):
                _invalid()
            seen_aliases.add(identifier)
        if seen_aliases != expected_aliases:
            _invalid()

        instructions = {
            instruction.id: (rung, instruction)
            for rung in inventory.rungs if rung.parse_status == 'parsed'
            for instruction in rung.instructions
        }
        seen_operands: set[tuple[str, int]] = set()
        seen_operand_ids: set[str] = set()
        for operand in operands:
            identifier = operand['id']
            instruction_id = operand['instruction_id']
            index = operand['argument_index']
            if (type(identifier) is not str or not identifier or identifier in seen_operand_ids
                    or type(instruction_id) is not str or instruction_id not in instructions
                    or type(index) is not int or index < 0):
                _invalid()
            rung, instruction = instructions[instruction_id]
            pair = (instruction_id, index)
            if (index >= len(instruction.arguments) or pair in seen_operands
                    or operand['rung_id'] != rung.id or operand['scope_id'] != rung.scope_id
                    or operand['raw_text'] != instruction.arguments[index]):
                _invalid()
            seen_operands.add(pair)
            seen_operand_ids.add(identifier)
        if (len(operands) != sum(len(instruction.arguments) for _, instruction in instructions.values())
                or coverage['operands_total'] != len(operands)):
            _invalid()

        summary = dict(CONSTANTS) | {
            'status': core['status'],
            'source_summary': source_summary,
            'symbols': {
                'total': len(symbols),
                'by_kind': {kind: kinds[kind] for kind in sorted(SYMBOL_KINDS)},
                'unnamed': coverage['unnamed_symbols'],
                'ambiguous_groups': coverage['ambiguous_symbol_groups'],
            },
            'aliases': {'total': len(aliases), 'by_status': _status_counts(aliases, ALIAS_STATUSES),
                        'by_reason': _reason_counts(aliases)},
            'operands': {'total': len(operands), 'by_status': _status_counts(operands, OPERAND_STATUSES),
                         'by_reason': _reason_counts(operands),
                         'malformed_address_shapes': _malformed_address_shapes(operands)},
            'module_io': _module_io_counts(symbols),
            'coverage': {key: coverage[key] for key in sorted(_COVERAGE_KEYS)},
        }
        validate_reference_summary(summary)
        return summary
    except (ReferenceError, SummaryError, KeyError, TypeError, AttributeError, IndexError):
        _invalid()


def validate_reference_summary(summary: dict[str, Any]) -> None:
    """Validate every field and all aggregate relationships at publication time."""
    try:
        _validate(summary)
    except (SummaryError, KeyError, TypeError, AttributeError, IndexError):
        _invalid()


def _validate(summary: dict[str, Any]) -> None:
    if type(summary) is not dict:
        _invalid()
    version = summary.get('schema_version')
    if type(version) is not int or version not in {1, 2, 3, 4}:
        _invalid()
    legacy = version == 1
    _keys(summary, set(CONSTANTS) | {'status', 'source_summary', 'symbols', 'aliases', 'operands', 'coverage'}
          | (set() if legacy else {'module_io'}))
    _constants(summary, {1: LEGACY_CONSTANTS, 2: V2_CONSTANTS, 3: V3_CONSTANTS, 4: CONSTANTS}[version])
    if type(summary['status']) is not str or summary['status'] not in {'complete', 'partial'}:
        _invalid()
    source = summary['source_summary']
    validate_summary(source)
    if source['schema_version'] != (2 if legacy else 3):
        _invalid()
    source_counts = source['counts']
    symbols = summary['symbols']
    _keys(symbols, {'total', 'by_kind', 'unnamed', 'ambiguous_groups'})
    for key in ('total', 'unnamed', 'ambiguous_groups'):
        _count(symbols[key])
    _counts(symbols['by_kind'], LEGACY_SYMBOL_KINDS if legacy else SYMBOL_KINDS)
    expected_kinds = {
        'tag': source_counts['total_tag_definitions'],
        'aoi_local_tag': source_counts['aoi_local_tags'],
        'aoi_parameter': source_counts['aoi_parameters'],
    }
    if not legacy:
        expected_kinds.update({kind: source_counts[f'{kind}s'] for kind in MODULE_IO_KINDS})
    if (symbols['by_kind'] != expected_kinds or sum(symbols['by_kind'].values()) != symbols['total']
            or symbols['unnamed'] > symbols['total']
            or 2 * symbols['ambiguous_groups'] > symbols['total'] - symbols['unnamed']):
        _invalid()
    for name, allowed in (('aliases', ALIAS_STATUSES), ('operands', OPERAND_STATUSES)):
        group = summary[name]
        has_shapes = version in {3, 4} and name == 'operands'
        _keys(group, {'total', 'by_status'} | (set() if legacy else {'by_reason'})
              | ({'malformed_address_shapes'} if has_shapes else set()))
        _count(group['total'])
        _counts(group['by_status'], allowed)
        if sum(group['by_status'].values()) != group['total']:
            _invalid()
        if not legacy:
            _keys(group['by_reason'], set(REASONS_BY_STATUS))
            for status, reasons in REASONS_BY_STATUS.items():
                _counts(group['by_reason'][status], reasons)
                if sum(group['by_reason'][status].values()) != group['by_status'][status]:
                    _invalid()
        if has_shapes:
            shapes = group['malformed_address_shapes']
            _counts(shapes, MALFORMED_ADDRESS_SHAPES)
            if sum(shapes.values()) != group['by_reason']['unsupported_address']['malformed_address']:
                _invalid()
            if shapes['alias_target_failure'] and not summary['aliases']['by_reason']['unsupported_address']['malformed_address']:
                _invalid()
    if not legacy:
        module_io = summary['module_io']
        _keys(module_io, {'total', 'named', 'by_name_origin', 'unavailable_by_reason'})
        _count(module_io['total'])
        _count(module_io['named'])
        _counts(module_io['by_name_origin'], frozenset(NAME_ORIGINS))
        _counts(module_io['unavailable_by_reason'], frozenset(NAME_REASONS))
        unavailable = module_io['by_name_origin']['unavailable']
        if (module_io['total'] != sum(symbols['by_kind'][kind] for kind in MODULE_IO_KINDS)
                or sum(module_io['by_name_origin'].values()) != module_io['total']
                or module_io['named'] + unavailable != module_io['total']
                or sum(module_io['unavailable_by_reason'].values()) != unavailable
                or unavailable > symbols['unnamed']):
            _invalid()
    aliases = summary['aliases']
    operands = summary['operands']
    if not (source_counts['aliases'] <= aliases['total']
            <= source_counts['aliases'] + source_counts['aoi_parameters'] + source_counts['aoi_local_tags']):
        _invalid()
    if aliases['total'] > symbols['total']:
        _invalid()
    coverage = summary['coverage']
    _counts(coverage, _COVERAGE_KEYS)
    if (coverage['rungs_total'] != source_counts['rungs']
            or coverage['rungs_analyzed'] != source['coverage']['rungs']['parsed']
            or coverage['instructions_total'] != source_counts['instructions']
            or coverage['instructions_catalogued'] > coverage['instructions_total']
            or operands['total'] != source['ladder_metrics']['totals']['argument_slots']):
        _invalid()
    incomplete = (
        source['status'] != 'complete'
        or coverage['instructions_catalogued'] != coverage['instructions_total']
        or symbols['unnamed'] or symbols['ambiguous_groups']
        or any(count for state, count in aliases['by_status'].items() if state != 'root_bound')
        or any(count for state, count in operands['by_status'].items() if state not in COMPLETE_OPERAND_STATUSES)
    )
    if summary['status'] == 'complete' and incomplete:
        _invalid()


def render_reference_summary(summary: dict[str, Any]) -> str:
    """Serialize deterministic JSON containing only validated public aggregates."""
    validate_reference_summary(summary)
    rendered = json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        raise ReferenceSummaryError('Reference summary exceeds its publication size limit; no summary was produced.')
    return rendered
