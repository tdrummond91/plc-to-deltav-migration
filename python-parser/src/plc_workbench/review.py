"""Private, snapshot-bound evidence for the offline engineering review report.

Patterns compare exact ordered syntax only. Findings expose existing gaps; they
do not infer equipment, dependencies, instruction effects, or engineering intent.
This module performs no filesystem, process, or network operations.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import fields, is_dataclass
import hashlib
import io
import json
from typing import Any

from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult, analyze_references
from .sfc_structure import SfcStructureResult, analyze_sfc_structure
from .source import analyze_snapshot

MAX_REVIEW_BYTES = 64 * 1024 * 1024
MAX_REVIEW_FINDINGS = 500_000
MAX_REVIEW_PATTERNS = 100_000
_BOUND = frozenset({'root_bound', 'literal', 'non_data', 'system_flag'})


class ReviewError(ValueError):
    """A fixed-message error that never exposes private evidence or OS details."""


def _fail() -> None:
    raise ReviewError('Engineering review evidence is inconsistent or exceeds its limits.') from None


def _strict_equal(expected: Any, actual: Any) -> bool:
    """Walk only the canonical tree, rejecting extra fields, cycles and coercion."""
    pending = [(expected, actual)]
    while pending:
        wanted, got = pending.pop()
        kind = type(wanted)
        if type(got) is not kind:
            return False
        if is_dataclass(wanted):
            if vars(wanted).keys() != vars(got).keys():
                return False
            pending.extend((getattr(wanted, field.name), getattr(got, field.name))
                           for field in fields(wanted))
        elif kind is dict:
            if (len(wanted) != len(got) or any(type(key) is not str for key in got)
                    or wanted.keys() != got.keys()):
                return False
            pending.extend((value, got[key]) for key, value in wanted.items())
        elif kind in {list, tuple}:
            if len(wanted) != len(got):
                return False
            pending.extend(zip(wanted, got))
        elif kind not in {str, int, bool, type(None)} or wanted != got:
            return False
    return True


def _json_native(value: Any) -> Any:
    if type(value) is dict:
        return {key: _json_native(item) for key, item in value.items()}
    if type(value) in {list, tuple}:
        return [_json_native(item) for item in value]
    return value


def _bounded_json(data: dict[str, Any], *, retain: bool = True) -> str:
    """Count UTF-8 bytes without retaining millions of small encoder chunks."""
    rendered = io.StringIO() if retain else None
    total = 0
    for chunk in json.JSONEncoder(ensure_ascii=False, separators=(',', ':'),
                                  allow_nan=False).iterencode(data):
        total += len(chunk.encode('utf-8'))
        if total > MAX_REVIEW_BYTES:
            _fail()
        if rendered is not None:
            rendered.write(chunk)
    return rendered.getvalue() if rendered is not None else ''


def _identifier(snapshot_id: str, kind: str, identity: str) -> str:
    digest = hashlib.sha256(f'{snapshot_id}\0{kind}\0{identity}'.encode('utf-8')).hexdigest()
    return f'review_{kind}_{digest}'


def _patterns(inventory: InventoryResult) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for rung in inventory.rungs:
        if rung.parse_status != 'parsed':
            continue
        instructions = {row.id: row for row in rung.instructions}

        def shape(node: dict[str, Any]) -> list[Any]:
            if node['kind'] == 'instruction':
                row = instructions[node['instruction_id']]
                return ['instruction', row.opcode, len(row.arguments)]
            children = node['legs'] if node['kind'] == 'branch' else node['items']
            return [node['kind'], [shape(child) for child in children]]

        signature = json.dumps(shape(rung.structure), ensure_ascii=False, separators=(',', ':'))
        if signature not in groups:
            if len(groups) >= MAX_REVIEW_PATTERNS:
                _fail()
            opcodes = Counter((row.opcode, len(row.arguments)) for row in rung.instructions)
            groups[signature] = {
                'id': _identifier(str(inventory.snapshot['id']), 'pattern', signature),
                'shape': signature,
                'opcode_summary': [{'opcode': opcode, 'arity': arity, 'count': count}
                                   for (opcode, arity), count in sorted(opcodes.items())],
                'rung_ids': [], 'count': 0,
            }
        groups[signature]['rung_ids'].append(rung.id)
        groups[signature]['count'] += 1
    return list(groups.values())


def _findings(inventory: InventoryResult, references: ReferenceResult,
              sfc: SfcStructureResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    locators = {row.id: row.locator for row in (*inventory.entities, *inventory.rungs)}

    def add(origin: str, code: str, severity: str, source_id: str | None,
            related: list[str | None], message: str, *, locator: str | None = None) -> None:
        if len(rows) >= MAX_REVIEW_FINDINGS:
            _fail()
        rows.append({
            'id': _identifier(str(inventory.snapshot['id']), 'finding', str(len(rows))),
            'origin': origin, 'code': code, 'severity': severity,
            'source_id': source_id,
            'locator': locator if locator is not None else locators.get(source_id),
            'related_ids': list(dict.fromkeys(value for value in related
                                             if value is not None and value != source_id)),
            'message': message,
        })

    for row in inventory.diagnostics:
        add('source', row.code, row.severity, row.source_id, [], row.message, locator=row.locator)
    for row in references.operands:
        if row['status'] not in _BOUND:
            add('operand', row['status'], 'warning', row['id'],
                [row['instruction_id'], row['rung_id'], row['scope_id']],
                f"Operand binding status: {row['status']}. Consult the retained source evidence.")
    for rung in inventory.rungs:
        for row in rung.instructions:
            if not row.arguments:
                add('operand', 'no_operand_evidence', 'info', row.id, [rung.id, rung.scope_id],
                    'This instruction has no operand binding rows; its effects are not analyzed.')
    for row in references.aliases:
        if row['status'] != 'root_bound':
            add('alias', row['status'], 'warning', row['source_id'],
                [row['scope_id'], *row['alias_chain']],
                f"Alias binding status: {row['status']}. Consult the retained source evidence.")
    for row in references.routine_targets['occurrences']:
        if row['status'] != 'unique_candidate':
            add('routine_target', row['status'], 'warning', row['instruction_id'],
                [row['rung_id'], row['caller_routine_id'], row['program_id']],
                f"Routine declaration candidate status: {row['status']}. Call validity is not analyzed.")
        elif row['target_context'] == 'not_analyzed':
            add('routine_target', 'target_context_not_analyzed', 'info', row['instruction_id'],
                [row['rung_id'], row['caller_routine_id'], row['program_id'], row['target_routine_id']],
                'A unique routine declaration candidate exists; its call context remains unanalyzed.')
    for row in sfc.issues:
        add('sfc', row['code'], 'warning', row['source_id'], [],
            f"SFC structural capture issue: {row['code']}. Consult the retained source evidence.")
    return rows


def build_review_data(snapshot: SourceSnapshot, inventory: InventoryResult,
                      references: ReferenceResult,
                      sfc_structure: SfcStructureResult) -> dict[str, Any]:
    """Build a bounded PRIVATE report using only the captured immutable bytes.

    All inputs are checked by canonical replay before any caller-supplied tree
    is copied or serialized. IDs remain scoped to this exact snapshot, including
    pattern and finding IDs; they are not persistent correction identifiers.
    """
    try:
        if (type(snapshot) is not SourceSnapshot or type(inventory) is not InventoryResult
                or type(references) is not ReferenceResult
                or type(sfc_structure) is not SfcStructureResult
                or type(snapshot.data) is not bytes or type(snapshot.size_bytes) is not int
                or type(snapshot.id) is not str or type(snapshot.sha256) is not str):
            _fail()
        canonical_inventory = analyze_snapshot(snapshot)
        if not _strict_equal(canonical_inventory, inventory):
            _fail()
        canonical_references = analyze_references(canonical_inventory)
        if not _strict_equal(canonical_references, references):
            _fail()
        canonical_sfc = analyze_sfc_structure(snapshot, canonical_inventory)
        if not _strict_equal(canonical_sfc, sfc_structure):
            _fail()
        patterns = _patterns(canonical_inventory)
        findings = _findings(canonical_inventory, canonical_references, canonical_sfc)
        data = {
            'schema_version': 1, 'report_version': 'engineering-review-1',
            'snapshot': dict(canonical_inventory.snapshot),
            'status': 'complete' if all(item.status == 'complete' for item in
                                      (canonical_inventory, canonical_references, canonical_sfc)) else 'partial',
            'analysis_scope': 'source_evidence_review',
            'semantic_analysis': 'not_implemented', 'effect_analysis': 'not_implemented',
            'inventory': _json_native(canonical_inventory.to_dict()),
            'references': canonical_references.to_dict(), 'sfc': canonical_sfc.to_dict(),
            'patterns': patterns, 'findings': findings,
            'statistics': {
                'entities': len(inventory.entities), 'rungs': len(inventory.rungs),
                'parsed_rungs': sum(rung.parse_status == 'parsed' for rung in inventory.rungs),
                'pattern_groups': len(patterns),
                'repeated_pattern_groups': sum(row['count'] > 1 for row in patterns),
                'findings': len(findings), 'symbols': len(references.symbols),
                'operands': len(references.operands), 'sfc_elements': len(sfc_structure.elements),
                'sfc_links': len(sfc_structure.links), 'sfc_annotations': len(sfc_structure.annotations),
            },
        }
        _bounded_json(data, retain=False)
        return data
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _fail()


def validate_review_data(snapshot: SourceSnapshot, inventory: InventoryResult,
                         references: ReferenceResult, sfc_structure: SfcStructureResult,
                         data: dict[str, Any]) -> None:
    """Compare every candidate field against bounded canonical captured evidence."""
    try:
        if _strict_equal(build_review_data(snapshot, inventory, references, sfc_structure), data):
            return
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        pass
    _fail()


def render_review_json(data: dict[str, Any]) -> str:
    """Serialize PRIVATE data; persistence callers must validate it first."""
    try:
        return _bounded_json(data)
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _fail()
