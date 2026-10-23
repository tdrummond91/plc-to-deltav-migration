"""Read-only, paged connections between captured rungs and exact addresses.

The index authenticates the saved companions once, without opening an L5X or
running the analysis pipeline. Navigation only reads the resulting index. A
signal connects possible explicit reads/writes; it is not a reaching definition,
execution timeline, whole-object/member overlap, or physical signal claim.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from typing import Any

from .access import AccessResult, _derive_access, INDEXED_ROLES
from .calculations import CalculationResult, _derive as _derive_calculations
from .models import Diagnostic, EntityRecord, InstructionRecord, InventoryResult, RungRecord, SourceSnapshot
from .references import (
    MAX_ADDRESS_LENGTH, ReferenceResult, _ADDRESS, _strict_record_match, validate_references,
)
from .relationships import RELATIONSHIP_CONSTANTS, RelationshipResult

SIGNAL_PAGE_SIZE = 12
ENDPOINT_PAGE_SIZE = 8
EVIDENCE_PREVIEW_SIZE = 40
MAX_RECORDS = 250_000
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_VIEW_BYTES = 8 * 1024 * 1024
_NOTICE = (
    'Connections show possible explicit reads and writes to the same exact '
    'address in this export. They do not establish execution order, which write '
    'reaches a read, member overlap, or physical wiring. Click another rung to '
    'follow its connections; same-rung reuse is listed separately.'
)


class ConnectionError(ValueError):
    """Fixed, source-free error suitable for a workspace unavailable panel."""


def _invalid() -> None:
    raise ConnectionError('Saved connection evidence is inconsistent or exceeds its limits.')


def _plain(value: Any, *, limit: int = MAX_ARTIFACT_BYTES) -> dict[str, Any]:
    """Bound native containers before copying or serializing saved evidence."""
    if type(value) is not dict:
        _invalid()
    pending = [(value, 0)]
    budget = limit
    seen: set[int] = set()
    while pending:
        item, depth = pending.pop()
        budget -= 1
        if budget < 0 or depth > 160:
            _invalid()
        if type(item) in {dict, list}:
            if id(item) in seen or len(item) > MAX_RECORDS:
                _invalid()
            seen.add(id(item))
            if type(item) is dict:
                if any(type(key) is not str for key in item):
                    _invalid()
                budget -= sum(len(key) for key in item)
                pending.extend((child, depth + 1) for child in item.values())
            else:
                pending.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            budget -= len(item)
        elif type(item) not in {int, bool, type(None)}:
            _invalid()
        if budget < 0:
            _invalid()
    if len(json.dumps(value, ensure_ascii=True, separators=(',', ':'))) > limit:
        _invalid()
    return deepcopy(value)


def _payload(value: Any, expected: type) -> dict[str, Any]:
    if type(value) is expected:
        value = asdict(value)
        if expected is InventoryResult:
            for rung in value['rungs']:
                for instruction in rung['instructions']:
                    instruction['arguments'] = list(instruction['arguments'])
    return _plain(value)


def _unique(rows: list[Any], key: str = 'id') -> dict[str, Any]:
    if type(rows) is not list or len(rows) > MAX_RECORDS:
        _invalid()
    result = {}
    for row in rows:
        identifier = row[key] if type(row) is dict else getattr(row, key)
        if type(identifier) is not str or not identifier or identifier in result:
            _invalid()
        result[identifier] = row
    return result


def _inventory(value: Any) -> InventoryResult:
    data = _payload(value, InventoryResult)
    if (type(data.get('schema_version')) is not int or data['schema_version'] != 3
            or data.get('parser_version') != 'source-inventory-3'
            or data.get('analysis_scope') != 'source_structure_only'
            or data.get('semantic_analysis') != 'not_implemented'):
        _invalid()
    data['entities'] = [EntityRecord(**row) for row in data['entities']]
    rungs = []
    for row in data['rungs']:
        instructions = []
        for instruction in row['instructions']:
            instruction['arguments'] = tuple(instruction['arguments'])
            instructions.append(InstructionRecord(**instruction))
        row['instructions'] = instructions
        rungs.append(RungRecord(**row))
    data['rungs'] = rungs
    data['diagnostics'] = [Diagnostic(**row) for row in data['diagnostics']]
    inventory = InventoryResult(**data)
    snapshot = inventory.snapshot
    if (set(snapshot) != {'id', 'sha256', 'size_bytes'}
            or type(snapshot['sha256']) is not str or len(snapshot['sha256']) != 64
            or any(character not in '0123456789abcdef' for character in snapshot['sha256'])
            or snapshot['id'] != f"sha256:{snapshot['sha256']}"
            or type(snapshot['size_bytes']) is not int or snapshot['size_bytes'] < 0):
        _invalid()
    entities = _unique(inventory.entities)
    _unique(inventory.rungs)
    instructions = _unique([instruction for rung in rungs for instruction in rung.instructions])
    if len(instructions) > MAX_RECORDS:
        _invalid()
    for entity in inventory.entities:
        if (entity.parent_id is not None and entity.parent_id not in entities
                or entity.scope_id is not None and entity.scope_id not in entities):
            _invalid()
    for rung in rungs:
        if (rung.parent_id is not None and rung.parent_id not in entities
                or rung.scope_id is not None and rung.scope_id not in entities
                or type(rung.ordinal) is not int or rung.ordinal < 0):
            _invalid()
        for instruction in rung.instructions:
            if (type(instruction.opcode) is not str
                    or any(type(argument) is not str for argument in instruction.arguments)
                    or type(instruction.start) is not int or type(instruction.end) is not int
                    or not 0 <= instruction.start < instruction.end <= len(rung.text or '')):
                _invalid()
    return inventory


def _address_id(snapshot_id: str, target_id: str, suffix: str) -> str:
    digest = hashlib.sha256()
    for value in (snapshot_id, target_id, suffix):
        digest.update(value.encode('utf-8'))
        digest.update(b'\0')
    return 'relationship_address_' + digest.hexdigest()


def _address_rows(inventory: InventoryResult, access: AccessResult) -> tuple[list[dict], list[dict]]:
    """Rebuild only exact membership, never relationship patterns or execution."""
    addresses: dict[tuple[str, str], dict] = {}
    gaps = []
    instructions = _unique(access.instructions)
    operands = _unique(access.operands)
    expressions: dict[str, list[dict]] = defaultdict(list)
    for use in access.expression_uses:
        expressions[use['instruction_id']].append(use)
    rung_seen: dict[str, set[str]] = defaultdict(set)
    instruction_seen: dict[str, set[str]] = defaultdict(set)

    def add(use: dict, kind: str) -> None:
        if use['binding_status'] != 'root_bound' or kind == 'operand' and use['role'] not in INDEXED_ROLES:
            return
        suffix = use['suffix']
        if len(suffix) > MAX_ADDRESS_LENGTH or _ADDRESS.fullmatch('A' + suffix) is None:
            gaps.append({'id': use['id'], 'kind': kind, 'reason': 'expanded_suffix_invalid'})
            return
        key = (use['target_id'], suffix)
        if key not in addresses:
            addresses[key] = {
                'id': _address_id(str(inventory.snapshot['id']), *key),
                'target_id': key[0], 'suffix': suffix,
                **{f'{role}_operand_ids': [] for role in sorted(INDEXED_ROLES)},
                'expression_use_ids': [], 'rung_ids': [], 'instruction_ids': [],
                'profile': 'unknown_only',
            }
        address = addresses[key]
        bucket = f"{use['role']}_operand_ids" if kind == 'operand' else 'expression_use_ids'
        address[bucket].append(use['id'])
        for field, seen in (('rung_id', rung_seen), ('instruction_id', instruction_seen)):
            if use[field] not in seen[address['id']]:
                seen[address['id']].add(use[field])
                address[field + 's'].append(use[field])

    for rung in inventory.rungs:
        for instruction in rung.instructions:
            for identifier in instructions[instruction.id]['operand_ids']:
                operand = operands[identifier]
                if operand['role'] == 'expression_read':
                    for use in expressions[instruction.id]:
                        add(use, 'expression')
                else:
                    add(operand, 'operand')
    for address in addresses.values():
        reads = bool(address['read_operand_ids'] or address['read_write_operand_ids'] or address['expression_use_ids'])
        writes = bool(address['write_operand_ids'] or address['read_write_operand_ids'])
        address['profile'] = ('read_and_write' if reads and writes else 'read_only' if reads
                              else 'write_only' if writes else 'unknown_only')
    return list(addresses.values()), gaps


class ConnectionIndex:
    """An immutable captured-use index; view calls never reanalyze the export."""

    def __init__(self, inventory: Any, references: Any, access: Any,
                 relationships: Any, calculations: Any = None) -> None:
        if any(value is None for value in (references, access, relationships)):
            raise ConnectionError('This saved run has no complete connection evidence. Analyze it again to build connections.')
        try:
            self._build(inventory, references, access, relationships, calculations)
        except ConnectionError:
            raise
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError, RecursionError):
            _invalid()

    def _build(self, inventory: Any, references: Any, access: Any,
               relationships: Any, calculations: Any) -> None:
        captured = _inventory(inventory)
        refs = ReferenceResult(**_payload(references, ReferenceResult))
        access_data = _payload(access, AccessResult)
        version = access_data.get('schema_version')
        if type(version) is not int or version not in {2, 3, 4}:
            raise ConnectionError('This saved access schema is unavailable for connection browsing. Analyze it again to update it.')
        access_result = AccessResult(**access_data)
        relationship_data = _payload(relationships, RelationshipResult)
        for key, expected in RELATIONSHIP_CONSTANTS.items():
            if type(relationship_data.get(key)) is not type(expected) or relationship_data[key] != expected:
                _invalid()
        relationship_result = RelationshipResult(**relationship_data)
        for companion in (refs, access_result, relationship_result):
            if not _strict_record_match(captured.snapshot, companion.snapshot):
                _invalid()
        # Authentication is deliberately against captured inventory. It does not
        # load source.xml or execute the full saved-run analysis pipeline.
        validate_references(captured, refs)
        calculation_result = None
        if version == 4 and calculations is None:
            raise ConnectionError('Calculation evidence is missing from this saved run. Analyze it again to build complete connections.')
        if calculations is not None:
            calculation_result = CalculationResult(**_payload(calculations, CalculationResult))
            if (type(calculation_result.schema_version) is not int
                    or calculation_result.schema_version not in {1, 2}
                    or version == 4 and calculation_result.schema_version != 2
                    or not _strict_record_match(captured.snapshot, calculation_result.snapshot)):
                _invalid()
            # _derive only parses bounded saved CPT expressions and binds their
            # leaves. SourceSnapshot.data is not used by this pure derivation.
            snapshot = SourceSnapshot(str(captured.snapshot['id']), str(captured.snapshot['sha256']),
                                      int(captured.snapshot['size_bytes']), b'')
            expected_calculations = _derive_calculations(snapshot, captured, refs, calculation_result.schema_version)
            if not _strict_record_match(vars(expected_calculations), vars(calculation_result)):
                _invalid()
        expected_access = _derive_access(captured, refs, version, calculation_result if version == 4 else None)
        if not _strict_record_match(vars(expected_access), vars(access_result)):
            _invalid()
        addresses, identity_gaps = _address_rows(captured, access_result)
        if (not _strict_record_match({'addresses': addresses, 'identity_gaps': identity_gaps},
                                    {'addresses': relationship_result.addresses,
                                     'identity_gaps': relationship_result.identity_gaps})):
            _invalid()
        self._rungs = _unique(captured.rungs)
        self._entities = _unique(captured.entities)
        self._symbol_names = {row['id']: row['name'] for row in refs.symbols}
        self._order = {rung.id: index for index, rung in enumerate(captured.rungs)}
        self._uses = {**_unique(access_result.operands), **_unique(access_result.expression_uses)}
        if len(self._uses) != len(access_result.operands) + len(access_result.expression_uses):
            _invalid()
        self._signals: dict[str, dict] = {}
        self._rung_signals: dict[str, list[str]] = defaultdict(list)
        self._endpoints = {identifier: self._rung_endpoint(rung) for identifier, rung in self._rungs.items()}
        self._rung_gaps: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        gap_ids = {row['id'] for row in identity_gaps}
        for use in self._uses.values():
            if use['id'] in gap_ids:
                self._rung_gaps[use['rung_id']]['invalid_expanded_addresses'] += 1
            elif use['binding_status'] not in {'root_bound', 'literal', 'non_data', 'system_flag', 'parsed_expression'}:
                self._rung_gaps[use['rung_id']]['unresolved_uses'] += 1
            if use['role'] == 'unknown':
                self._rung_gaps[use['rung_id']]['unknown_roles'] += 1
        for address in addresses:
            entity = self._entities.get(address['target_id'])
            if entity is None:
                _invalid()
            buckets = {
                'readers': address['read_operand_ids'] + address['read_write_operand_ids'] + address['expression_use_ids'],
                'writers': address['write_operand_ids'] + address['read_write_operand_ids'],
                'unknown_uses': address['unknown_operand_ids'],
            }
            by_rung = {}
            for name, identifiers in buckets.items():
                grouped: dict[str, list[str]] = defaultdict(list)
                for identifier in identifiers:
                    grouped[self._uses[identifier]['rung_id']].append(identifier)
                by_rung[name] = dict(sorted(grouped.items(), key=lambda row: self._order[row[0]]))
            self._signals[address['id']] = {
                'id': address['id'], 'target_id': address['target_id'], 'suffix': address['suffix'],
                'label': (self._symbol_names.get(entity.id) or entity.name or '(unnamed)') + address['suffix'],
                'target_path': self._entity_path(entity.id), 'buckets': by_rung,
                'writer_instructions': len({self._uses[identifier]['instruction_id'] for identifier in buckets['writers']}),
            }
            for rung_id in address['rung_ids']:
                self._rung_signals[rung_id].append(address['id'])
        self._coverage = {
            'source_rungs': len(captured.rungs), 'signals': len(addresses),
            'unparsed_rungs': sum(rung.parse_status != 'parsed' for rung in captured.rungs),
            'unknown_roles': sum(use['role'] == 'unknown' for use in access_result.operands),
            'unresolved_uses': sum(row.get('unresolved_uses', 0) for row in self._rung_gaps.values()),
            'invalid_expanded_addresses': len(identity_gaps),
            'access_schema_version': version, 'calculation_reads_available': version == 4,
            'implicit_effects_available': False, 'member_overlap_available': False,
        }
        self._map_qualification: tuple[dict, dict] | None = None

    def qualify_map(self, entity_ok: dict, rung_ok: dict) -> None:
        """Exclude unsupported XML associations from the visual map once/run.

        The legacy source index remains available to the original connection
        browser. The map uses a separate qualified projection: an unsupported
        source is not an unknown-role signal edge because even its target may
        be an artifact of local-name XML matching.
        """
        if (self._map_qualification is not None and self._map_qualification[0] is entity_ok
                and self._map_qualification[1] is rung_ok):
            return
        rejected = set()
        for identifier, use in self._uses.items():
            targets = [use.get('target_id'), use.get('symbol_id', use.get('target_id')),
                       *use.get('alias_chain', [])]
            if (not rung_ok.get(use.get('rung_id'), False)
                    or use.get('binding_status') == 'root_bound'
                    and not all(entity_ok.get(target, False) for target in targets)):
                rejected.add(identifier)
        self._map_buckets: dict[str, dict[str, frozenset[str]]] = {}
        self._map_rung_signals: dict[str, list[str]] = defaultdict(list)
        for identifier, signal in self._signals.items():
            buckets = {name: frozenset(rung_id for rung_id, uses in endpoints.items()
                                      if any(use not in rejected for use in uses))
                       for name, endpoints in signal['buckets'].items()}
            members = set().union(*buckets.values())
            if not members:
                continue
            self._map_buckets[identifier] = buckets
            for rung_id in members:
                self._map_rung_signals[rung_id].append(identifier)
        self._map_rejected_by_rung: dict[str, int] = defaultdict(int)
        for identifier in rejected:
            self._map_rejected_by_rung[self._uses[identifier]['rung_id']] += 1
        self._map_unqualified_rungs = frozenset(identifier for identifier in self._rungs
                                              if not rung_ok.get(identifier, False))
        self._map_coverage = {
            **self._coverage, 'signals': len(self._map_buckets), 'source_signals': len(self._signals),
            'unqualified_rungs': len(self._map_unqualified_rungs), 'unqualified_uses': len(rejected),
            'rejected_signal_count': len(self._signals) - len(self._map_buckets),
        }
        self._map_qualification = (entity_ok, rung_ok)

    def map_notice(self) -> str:
        if self._map_qualification is None:
            raise ConnectionError('Qualified source evidence is required for the ladder map.')
        extra = (' Unsupported XML source associations are omitted from connections; '
                 'the source rungs remain visible. Unsupported rung text is listed under Unidentified blocks.'
                 if self._map_coverage['unqualified_rungs'] or self._map_coverage['unqualified_uses'] else '')
        return _NOTICE + extra

    def signal_rungs(self, signal_id: str) -> frozenset[str]:
        """All exact-address users, including unknown roles, without fanout edges."""
        self.map_notice()
        if type(signal_id) is not str or signal_id not in self._map_buckets:
            raise ConnectionError('Choose a captured signal from the selected analysis.')
        return frozenset(identifier for bucket in self._map_buckets[signal_id].values()
                         for identifier in bucket)

    def map_links(self, rung_ids: list[str], *, direction: str = 'both', page: int = 1, page_size: int = 80) -> dict:
        """Bound a bipartite rung/signal view while retaining offscreen counts.

        Direction selects signals used as inputs/outputs by visible rungs. Each
        selected bus still shows every known role within the visible selection;
        it never invents a writer-to-reader ordering or Cartesian edge set.
        """
        if (type(rung_ids) is not list or len(rung_ids) > 80
                or any(type(identifier) is not str or identifier not in self._rungs for identifier in rung_ids)
                or len(set(rung_ids)) != len(rung_ids)
                or type(direction) is not str or direction not in {'both', 'inputs', 'outputs'}
                or type(page) is not int or not 1 <= page <= 1_000_000):
            raise ConnectionError('Choose at most 80 captured rungs and a valid connection page.')
        from .workspace_paging import page_size as select_size
        page_size = select_size({'page_size': page_size}, 80, graph=True, error=ConnectionError)
        notice = self.map_notice()
        visible = set(rung_ids)
        identifiers = dict.fromkeys(identifier for rung_id in rung_ids
                                    for identifier in self._map_rung_signals.get(rung_id, []))
        if direction != 'both':
            role = 'readers' if direction == 'inputs' else 'writers'
            identifiers = {identifier: None for identifier in identifiers
                           if visible.intersection(self._map_buckets[identifier][role])}
        pages = max(1, (len(identifiers) + page_size - 1) // page_size)
        page = min(page, pages)
        signals = []
        for identifier in list(identifiers)[(page - 1) * page_size:page * page_size]:
            signal = self._signals[identifier]
            row = {key: signal[key] for key in ('id', 'target_id')}
            row.update(label=signal['label'][:512], target_path=signal['target_path'][:1024],
                       outside_counts={}, totals={})
            for role, bucket in (('readers', 'readers'), ('writers', 'writers'), ('unknown', 'unknown_uses')):
                endpoints = self._map_buckets[identifier][bucket]
                row[role] = [rung_id for rung_id in rung_ids if rung_id in endpoints]
                row['totals'][role] = len(endpoints)
                row['outside_counts'][role] = len(endpoints) - len(row[role])
            signals.append(row)
        return {'available': True, 'signals': signals, 'total': len(identifiers), 'page': page,
                'pages': pages, 'page_size': page_size, 'omitted_signals': len(identifiers) - len(signals),
                'coverage': {**self._map_coverage,
                             'unqualified_visible_rungs': len(visible.intersection(self._map_unqualified_rungs)),
                             'unqualified_visible_uses': sum(self._map_rejected_by_rung.get(rung_id, 0) for rung_id in visible)},
                'notice': notice}

    def _entity_path(self, entity_id: str | None) -> str:
        names = []
        seen = set()
        while entity_id:
            if entity_id in seen or len(seen) > 160:
                _invalid()
            seen.add(entity_id)
            entity = self._entities[entity_id]
            if entity.name:
                names.append(entity.name)
            entity_id = entity.parent_id
        return ' / '.join(reversed(names)) or '(unassigned source context)'

    def _rung_endpoint(self, rung: RungRecord) -> dict:
        routine = self._entities.get(rung.parent_id)
        scope = self._entities.get(rung.scope_id)
        number = rung.number if rung.number is not None else str(rung.ordinal)
        return {'id': rung.id, 'number': number, 'routine_id': rung.parent_id,
                'routine': (routine.name if routine else None) or '(unassigned routine)',
                'program': (scope.name if scope else None) or '(unassigned scope)',
                'path': f'{self._entity_path(rung.parent_id)} / Rung {number}',
                'source_order': self._order[rung.id], 'parse_status': rung.parse_status}

    def _endpoint(self, rung_id: str, identifiers: list[str]) -> dict:
        instructions = list(dict.fromkeys(self._uses[identifier]['instruction_id'] for identifier in identifiers))
        return {**self._endpoints[rung_id], 'use_count': len(identifiers),
                'use_ids': identifiers[:EVIDENCE_PREVIEW_SIZE],
                'instruction_ids': instructions[:EVIDENCE_PREVIEW_SIZE],
                'instruction_count': len(instructions),
                'evidence_truncated': len(identifiers) > EVIDENCE_PREVIEW_SIZE or len(instructions) > EVIDENCE_PREVIEW_SIZE}

    def view(self, rung_id: str, *, scope: str = 'all', signal_id: str = '',
             direction: str = 'both', page: int = 1, endpoint_page: int = 1,
             page_size: int = SIGNAL_PAGE_SIZE, endpoint_page_size: int = ENDPOINT_PAGE_SIZE) -> dict:
        if (type(rung_id) is not str or rung_id not in self._rungs
                or type(scope) is not str or scope not in {'all', 'routine'}
                or type(direction) is not str or direction not in {'both', 'inputs', 'outputs'} or type(signal_id) is not str
                or type(page) is not int or type(endpoint_page) is not int
                or not 1 <= page <= 1_000_000 or not 1 <= endpoint_page <= 1_000_000):
            raise ConnectionError('Choose a valid rung, scope, direction, and connection page.')
        from .workspace_paging import page_size as select_size
        page_size = select_size({'page_size': page_size}, SIGNAL_PAGE_SIZE, graph=True, error=ConnectionError)
        endpoint_page_size = select_size({'page_size': endpoint_page_size}, ENDPOINT_PAGE_SIZE, graph=True, error=ConnectionError)
        identifiers = []
        for identifier in self._rung_signals.get(rung_id, []):
            buckets = self._signals[identifier]['buckets']
            if (direction == 'both' or direction == 'inputs' and rung_id in buckets['readers']
                    or direction == 'outputs' and rung_id in buckets['writers']):
                identifiers.append(identifier)
        if signal_id:
            if signal_id not in identifiers:
                raise ConnectionError('The selected signal does not belong to this rung and direction.')
            identifiers = [signal_id]
        pages = max(1, (len(identifiers) + page_size - 1) // page_size)
        page = min(page, pages)
        signals = [self._signal_view(self._signals[identifier], rung_id, scope, endpoint_page, endpoint_page_size)
                   for identifier in identifiers[(page - 1) * page_size:page * page_size]]
        result = {
            'available': True, 'focus': self._endpoints[rung_id], 'scope': scope, 'direction': direction,
            'selected_signal_id': signal_id, 'signals': signals,
            'pagination': {'page': page, 'pages': pages, 'page_size': page_size,
                           'total': len(identifiers), 'has_more': page < pages},
            'coverage': {**self._coverage, 'focus': dict(self._rung_gaps.get(rung_id, {})),
                         'focus_parse_status': self._rungs[rung_id].parse_status},
            'notice': _NOTICE,
        }
        if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > MAX_VIEW_BYTES:
            raise ConnectionError('This connection view is too large. Choose fewer signals or connected rungs per page.')
        return deepcopy(result)

    def _signal_view(self, signal: dict, rung_id: str, scope: str, endpoint_page: int,
                     endpoint_page_size: int = ENDPOINT_PAGE_SIZE) -> dict:
        groups = {}
        outside = {}
        totals = {}
        all_totals = {}
        focus_routine = self._rungs[rung_id].parent_id
        for name, by_rung in signal['buckets'].items():
            all_totals[name] = len(by_rung) - int(rung_id in by_rung)
            included = [(identifier, uses) for identifier, uses in by_rung.items() if identifier != rung_id
                        and (scope == 'all' or self._rungs[identifier].parent_id == focus_routine)]
            groups[name] = included
            totals[name] = len(included)
            outside[name] = all_totals[name] - totals[name]
        pages = max(1, max((count + endpoint_page_size - 1) // endpoint_page_size for count in totals.values()))
        endpoint_page = min(endpoint_page, pages)
        offset = (endpoint_page - 1) * endpoint_page_size
        buckets = signal['buckets']
        reads = buckets['readers'].get(rung_id, [])
        writes = buckets['writers'].get(rung_id, [])
        unknown = buckets['unknown_uses'].get(rung_id, [])
        result = {key: signal[key] for key in ('id', 'target_id', 'suffix', 'label', 'target_path')}
        result.update(
            input=bool(reads), output=bool(writes), unknown=bool(unknown),
            focus_roles=[name for name, uses in (('read', reads), ('write', writes), ('unknown', unknown)) if uses],
            counts={**all_totals, 'writer_instructions': signal['writer_instructions'],
                    'multiple_writers': signal['writer_instructions'] > 1},
            outside_counts=outside,
            same_rung={'read_use_ids': reads[:EVIDENCE_PREVIEW_SIZE], 'write_use_ids': writes[:EVIDENCE_PREVIEW_SIZE],
                       'unknown_use_ids': unknown[:EVIDENCE_PREVIEW_SIZE], 'reads': len(reads),
                       'writes': len(writes), 'unknown': len(unknown),
                       'evidence_truncated': max(len(reads), len(writes), len(unknown)) > EVIDENCE_PREVIEW_SIZE},
            endpoints={'page': endpoint_page, 'pages': pages, 'page_size': endpoint_page_size,
                       'offset': offset, 'totals': totals, 'has_more': endpoint_page < pages,
                       'bucket_has_more': {name: offset + endpoint_page_size < count for name, count in totals.items()}},
        )
        for name, rows in groups.items():
            result[name] = [self._endpoint(identifier, uses) for identifier, uses in rows[offset:offset + endpoint_page_size]]
        return result
