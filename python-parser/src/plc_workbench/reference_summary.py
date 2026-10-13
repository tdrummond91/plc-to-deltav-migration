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
from .references import ALIAS_STATUSES, OPERAND_STATUSES, ReferenceError, validate_references
from .summary import SummaryError, build_summary, validate_summary

if TYPE_CHECKING:
    from .references import ReferenceResult

MAX_REPORT_BYTES = 32 * 1024
MAX_COUNT = 10**12
SYMBOL_KINDS = frozenset({'tag', 'aoi_local_tag', 'aoi_parameter'})
COMPLETE_OPERAND_STATUSES = frozenset({'root_bound', 'literal', 'non_data'})
CONSTANTS = {
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
_CORE_CONSTANTS = {key: CONSTANTS[key] for key in (
    'schema_version', 'analyzer_version', 'analysis_scope', 'semantic_analysis',
    'effect_analysis', 'member_validation',
)}
_COVERAGE_KEYS = frozenset({'rungs_total', 'rungs_analyzed', 'instructions_total',
                            'instructions_catalogued'})
_CORE_COVERAGE_KEYS = _COVERAGE_KEYS | {
    'source_status', 'operands_total', 'ambiguous_symbol_groups', 'unnamed_symbols',
}
_SYMBOL_KEYS = frozenset({'id', 'name', 'scope_id', 'kind', 'attributes'})
_ALIAS_KEYS = frozenset({'source_id', 'scope_id', 'raw_target', 'status', 'symbol_id',
                        'target_id', 'suffix', 'alias_chain'})
_OPERAND_KEYS = frozenset({'id', 'instruction_id', 'rung_id', 'scope_id', 'argument_index',
                          'raw_text', 'status', 'symbol_id', 'target_id', 'suffix', 'alias_chain'})


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
    return (entity.attributes.get('TagType') == 'Alias'
            or (entity.kind in {'aoi_parameter', 'aoi_local_tag'}
                and 'AliasFor' in entity.attributes))


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
            if (entity is None or kind != entity.kind or symbol['name'] != entity.name
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
            'aliases': {'total': len(aliases), 'by_status': _status_counts(aliases, ALIAS_STATUSES)},
            'operands': {'total': len(operands), 'by_status': _status_counts(operands, OPERAND_STATUSES)},
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
    _keys(summary, set(CONSTANTS) | {'status', 'source_summary', 'symbols', 'aliases', 'operands', 'coverage'})
    _constants(summary, CONSTANTS)
    if type(summary['status']) is not str or summary['status'] not in {'complete', 'partial'}:
        _invalid()
    source = summary['source_summary']
    validate_summary(source)
    source_counts = source['counts']
    symbols = summary['symbols']
    _keys(symbols, {'total', 'by_kind', 'unnamed', 'ambiguous_groups'})
    for key in ('total', 'unnamed', 'ambiguous_groups'):
        _count(symbols[key])
    _counts(symbols['by_kind'], SYMBOL_KINDS)
    expected_kinds = {
        'tag': source_counts['total_tag_definitions'],
        'aoi_local_tag': source_counts['aoi_local_tags'],
        'aoi_parameter': source_counts['aoi_parameters'],
    }
    if (symbols['by_kind'] != expected_kinds or sum(symbols['by_kind'].values()) != symbols['total']
            or symbols['unnamed'] > symbols['total']
            or 2 * symbols['ambiguous_groups'] > symbols['total'] - symbols['unnamed']):
        _invalid()
    for name, allowed in (('aliases', ALIAS_STATUSES), ('operands', OPERAND_STATUSES)):
        group = summary[name]
        _keys(group, {'total', 'by_status'})
        _count(group['total'])
        _counts(group['by_status'], allowed)
        if sum(group['by_status'].values()) != group['total']:
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
