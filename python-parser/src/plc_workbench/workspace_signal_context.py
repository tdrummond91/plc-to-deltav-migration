"""Traceable result wording for narrowly proven, single-rung signal use.

The result's description is context for a captured read, never a replacement
source annotation or a claim about the physical equipment behind an address.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import json
from typing import TYPE_CHECKING, Any

from .workspace_field_io import FieldIOIndex
from .workspace_io_comments import IOCommentError, collect_io_annotations, select_description
from .workspace_variables import _child, _member_key

if TYPE_CHECKING:
    from .workspace_signal_usage import SignalUsageIndex

MAX_CONTEXT_BYTES = 8 * 1024 * 1024
_CONDITIONS = frozenset({'XIC', 'XIO', 'EQU', 'NEQ', 'LES', 'LEQ', 'GRT', 'GEQ', 'LIM'})
_RESULTS = frozenset({'OTE', 'MOV', 'ADD', 'SUB', 'MUL', 'DIV', 'ABS', 'LN', 'SQR', 'CPT'})
_SPECIFIC = frozenset({'exact_member_comment', 'exact_alias_description', 'declared_member_description'})
_ORIGINS = {'exact_member_comment': ('channel', 'Channel comment'),
    'exact_alias_description': ('alias', 'Signal alias description'),
    'declared_member_description': ('type_member', 'Data type member description'),
    'containing_member_comment': ('containing_member', 'Containing member comment'),
    'backing_description': ('backing', 'Backing tag description'),
    'backing_alias_description': ('backing', 'Backing alias description'),
    'module_description': ('module', 'Module description'), 'missing': ('missing', 'No signal description')}


def specific_description(address: dict) -> bool:
    selection = address['description_selection']
    return selection['basis'] in _SPECIFIC and bool((address.get('description') or '').strip())


def description_origin(field_io: FieldIOIndex, address: dict) -> dict:
    selection = address['description_selection']
    basis = selection['basis']
    kind, label = _ORIGINS.get(basis, _ORIGINS['missing'])
    preferred = selection['preferred_annotation_id']
    note = next((field_io._annotation_records[identifier, via]
                 for identifier, via, _ in field_io._description_candidates.get(address['id'], [])
                 if identifier == preferred), {})
    return {'kind': kind, 'label': label, 'basis': basis, 'specific': specific_description(address),
        'conflict': selection['conflict'], 'annotation_id': preferred,
        'owner_id': note.get('owner_id'), 'owner_name': note.get('owner_name'),
        'owner_suffix': note.get('owner_suffix', note.get('suffix')), 'owner_path': note.get('owner_path')}


class _ContextLimit(ValueError):
    pass


class SignalContextIndex:
    """Share one result context per rung; retain no expanded per-signal prose."""

    def __init__(self, field_io: FieldIOIndex, usage: SignalUsageIndex) -> None:
        self.io, self.base, self.usage = field_io, field_io.base, usage
        self._rungs: dict[str, dict] = {}
        self._signals: dict[str, str] = {}
        self._budget = 0
        self.available = True
        try:
            self._build()
        except (_ContextLimit, IOCommentError):
            self._rungs.clear()
            self._signals.clear()
            self._budget = 0
            self.available = False

    def _retain(self, value: Any) -> None:
        self._budget += len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self._budget > MAX_CONTEXT_BYTES:
            raise _ContextLimit()

    def _result(self, rung: Any, operands: list[dict], expression_uses: list[dict]) -> dict | None:
        if rung.parse_status != 'parsed' or not self.base._rung_ok.get(rung.id) or not rung.instructions:
            return None
        structure = rung.structure or {}
        items = structure.get('items', [])
        if structure.get('kind') != 'sequence' or not items or items[-1].get('kind') != 'instruction':
            return None
        output = self.base._instructions[items[-1]['instruction_id']]
        if output.opcode.upper() not in _RESULTS:
            return None
        pending = list(items[:-1])
        while pending:
            node = pending.pop()
            if node.get('kind') == 'instruction':
                if self.base._instructions[node['instruction_id']].opcode.upper() not in _CONDITIONS:
                    return None
            elif node.get('kind') == 'branch':
                legs = node.get('legs', [])
                if not legs or any(leg.get('kind') != 'sequence' or not leg.get('items') for leg in legs):
                    return None
                pending.extend(item for leg in legs for item in leg['items'])
            else:
                return None
        if any(self.base._access_instructions.get(item.id, {}).get('status') != 'classified'
               for item in rung.instructions):
            return None
        writes = [use for use in operands if use['role'] == 'write']
        if len(writes) != 1 or writes[0]['instruction_id'] != output.id:
            return None
        for use in [*operands, *expression_uses]:
            status, role = use['binding_status'], use['role']
            if role not in {'read', 'write', 'expression_read'}:
                return None
            if role == 'expression_read':
                if status != 'parsed_expression':
                    return None
            elif status == 'root_bound':
                if not self.base._qualified(use, rung.id):
                    return None
            elif not (role == 'read' and status in {'literal', 'system_flag'}):
                return None
        result = writes[0]
        if result['binding_status'] != 'root_bound':
            return None
        # Reject explicit readback/accumulation of the destination, including
        # containing-member overlap, even when the individual roles are known.
        from .workspace_signal_usage import _usage_key
        result_key = _usage_key(result['suffix'])
        for use in [*operands, *expression_uses]:
            if use['role'] == 'read' and use.get('target_id') == result['target_id']:
                key = _usage_key(use['suffix'])
                if key == result_key or _child(key, result_key) or _child(result_key, key):
                    return None
        return result

    def _build(self) -> None:
        # Context is scoped to captured RLL. Other source languages are named
        # explicitly; missing or unread RLL cannot prove this narrow single use.
        gaps = set(self.usage.scan_summary()['gap_reasons'])
        if self.base._access is None or gaps - {'unsupported_routines'}:
            return
        recovered = {use['id']: address for address in self.io.addresses.values()
                     for use in address['uses'] if use.get('binding_basis') ==
                     'qualified_rack_slot_source_correspondence'}

        def qualified_use(use: dict) -> dict:
            address = recovered.get(use['id'])
            if address is None or use['role'] != 'read' or use['binding_status'] == 'root_bound':
                return use
            # Reuse an authenticated FieldIO correspondence by occurrence ID.
            # Preserve the original access artifact, roles and source IDs.
            return dict(use, binding_status='root_bound', target_id=address['root_id'],
                        symbol_id=use.get('symbol_id') or address['root_id'], suffix=address['suffix'])

        by_rung, expressions = defaultdict(list), defaultdict(list)
        for use in self.base._access.operands:
            by_rung[use['rung_id']].append(qualified_use(use))
        for use in self.base._access.expression_uses:
            expressions[use['rung_id']].append(qualified_use(use))
        eligible, owners = {}, set()
        for rung in self.base._rungs.values():
            result = self._result(rung, by_rung[rung.id], expressions[rung.id])
            if result is not None:
                eligible[rung.id] = result
                owners.update((result['symbol_id'], result['target_id']))
        if not owners:
            return
        notes = collect_io_annotations(self.base._source, self.base._captured,
                                       self.base._entity_ok, owner_ids=owners)
        for rung_id, result in eligible.items():
            rung = self.base._rungs[rung_id]
            ref = self.base._reference_uses[result['id']]
            candidates = []
            key = _member_key(result['suffix'])
            for note in notes.get((result['target_id'], key), []):
                candidates.append(dict(note, description_scope='exact_member_comment' if key else 'declared_member_description'))
            symbol = self.base._entities[result['symbol_id']]
            if symbol.id != result['target_id'] and ref['raw_text'].strip().casefold() == (symbol.name or '').casefold():
                candidates.extend(dict(note, description_scope='exact_alias_description')
                                  for note in notes.get((symbol.id, ''), []))
            candidates.extend(self.io.member_descriptions.inspect(result['target_id'], result['suffix'])['annotations'])
            selection = select_description(candidates)
            if selection['status'] != 'selected' or selection['conflict']:
                continue
            note = next(note for note in candidates if note['id'] == selection['preferred_annotation_id'])
            opcode = self.base._instructions[result['instruction_id']].opcode.upper()
            row = {'kind': 'boolean_result' if opcode == 'OTE' else 'calculation_result',
                'description': note['text'], 'result_name': ref['raw_text'].strip(),
                'result_id': result['symbol_id'], 'result_suffix': result['suffix'],
                'description_source_id': note['owner_id'], 'description_annotation_id': note['id'],
                'description_basis': note['description_scope'],
                'description_owner_name': note.get('owner_name') or self.base._resolver.name(self.base._entities[note['owner_id']]),
                'description_owner_suffix': note.get('owner_suffix', note.get('suffix', '')),
                'rung_id': rung_id, 'instruction_id': result['instruction_id'], 'rung_number': rung.number,
                'path': self.base._path(rung.parent_id) + ' / Rung ' + str(rung.number),
                'basis': 'single_supported_rung_result',
                'notice': ('Result description from the single matched RLL use rung; it is context, not the field signal\'s source description or confirmed equipment identity.'
                    + (' Other source languages are outside this lookup.' if 'unsupported_routines' in gaps else ''))}
            self._retain((rung_id, row))
            self._rungs[rung_id] = row
        for address in self.io.addresses.values():
            if specific_description(address) or not address['uses'] or self.usage._limited:
                continue
            direct = address['uses']
            rungs = {use['rung_id'] for use in direct}
            if len(rungs) != 1 or any(use['role'] != 'read' for use in direct):
                continue
            rung_id = next(iter(rungs))
            if rung_id not in self._rungs:
                continue
            direct_ids = {use['id'] for use in direct}
            # Root/range/dynamic associations can reveal other uses even when
            # this exact spelling occurs in just one rung. Never hide those.
            if any(identifier not in direct_ids and (not proven or self.usage._uses[identifier]['rung_id'] != rung_id)
                   for identifier, _, proven, _ in self.usage._related(address)):
                continue
            self._retain((address['id'], rung_id))
            self._signals[address['id']] = rung_id

    def get(self, address_id: str) -> dict | None:
        rung_id = self._signals.get(address_id)
        return deepcopy(self._rungs[rung_id]) if rung_id else None

    def full_description(self, rung_id: str) -> str | None:
        row = self._rungs.get(rung_id)
        return row['description'] if row else None

    def matches(self, address_id: str, needle: str) -> bool:
        """Search shared full context without copying it into every signal."""
        rung_id = self._signals.get(address_id)
        row = self._rungs.get(rung_id)
        return bool(row and any(needle in row[key].casefold() for key in ('description', 'result_name', 'path')))
