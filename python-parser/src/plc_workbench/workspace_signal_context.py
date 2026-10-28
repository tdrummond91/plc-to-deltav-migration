"""Traceable captured wording for narrowly proven, single-rung signal use.

The result's description is context for a captured read, never a replacement
source annotation or a claim about the physical equipment behind an address.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import json
from typing import TYPE_CHECKING, Any

from .references import _ROOT
from .workspace_field_io import FieldIOIndex
from .workspace_io_comments import IOCommentError, collect_io_annotations, select_description
from .workspace_variables import _child, _member_key

if TYPE_CHECKING:
    from .workspace_signal_usage import SignalUsageIndex

MAX_CONTEXT_BYTES = 8 * 1024 * 1024
CONTEXT_REASONS = ('specific_source', 'no_direct_use', 'multiple_rungs', 'nonread_use',
    'overlapping_use', 'unsupported_result', 'no_wording', 'conflicting_wording',
    'unqualified_wording', 'result_description', 'rung_comment', 'access_unavailable',
    'usage_unavailable', 'annotations_unavailable', 'capacity')
_CONDITIONS = frozenset({'XIC', 'XIO', 'EQU', 'NEQ', 'LES', 'LEQ', 'GRT', 'GEQ', 'LIM'})
_RESULTS = frozenset({'OTE', 'MOV', 'ADD', 'SUB', 'MUL', 'DIV', 'ABS', 'LN', 'SQR', 'CPT'})
_COPIES = frozenset({'COP', 'CPS'})
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
        self._rung_reasons: dict[str, str] = {}
        self._copies: dict[str, dict] = {}
        self._uncertain_roots: set[str] = set()
        self._budget = 0
        self.available = True
        self._unavailable_reason: str | None = None
        try:
            self._build()
        except (_ContextLimit, IOCommentError) as error:
            self._rungs.clear()
            self._signals.clear()
            self._rung_reasons.clear()
            self._copies.clear()
            self._uncertain_roots.clear()
            self._budget = 0
            self.available = False
            self._unavailable_reason = 'capacity' if isinstance(error, _ContextLimit) else 'annotations_unavailable'

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
        opcode = output.opcode.upper()
        if opcode not in _RESULTS | _COPIES:
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
        if opcode in _COPIES:
            resolver = self.usage._range_resolver
            if resolver is None or len(output.arguments) != 3 or expression_uses:
                return None
            source = next((use for use in operands if use['instruction_id'] == output.id
                           and use['argument_index'] == 0), None)
            if source is None or source['binding_status'] != 'root_bound':
                return None
            footprints = []
            for use in (source, result):
                ref = self.base._reference_uses[use['id']]
                binding = self.io.rack_references.binding(ref['raw_text'].strip(), rung.scope_id)
                footprint = resolver.resolve(ref, binding)
                # One destination element has one wording owner. A longer
                # array copy needs element correspondence, not the first
                # destination element's comment applied to the whole range.
                if footprint['status'] != 'resolved' or footprint['length'] != 1:
                    return None
                footprints.append(footprint)
            source_range, destination_range = footprints
            if source_range['byte_count'] % source_range['element_bytes']:
                return None  # Do not assign a whole signal to a partial word.
            if (source_range['root_id'] == destination_range['root_id']
                    and source_range['container_suffix'] == destination_range['container_suffix']
                    and source_range['start_byte'] < destination_range['end_byte']
                    and destination_range['start_byte'] < source_range['end_byte']):
                return None
            copy = {'source_use_id': source['id'], 'source_range': source_range,
                    'destination_range': destination_range}
            self._retain((rung.id, copy))
            self._copies[rung.id] = copy
        return result

    def _build(self) -> None:
        # A known captured read and its wording remain useful when another
        # routine is unread. Disclose scan gaps instead of claiming plant-wide
        # uniqueness or erasing positive evidence from qualified RLL rungs.
        scan = self.usage.scan_summary()
        gaps = set(scan['gap_reasons']) | set(scan['role_gap_reasons'])
        if self.base._access is None:
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
            if (use['binding_status'] == 'unsupported_address'
                    and use.get('binding_reason') == 'malformed_address'):
                # An unread suffix on a known root is a signal-specific gap,
                # unlike an unrelated unread routine. Do not promote context
                # for another member of that same backing root.
                raw = self.base._reference_uses[use['id']]['raw_text'].strip()
                root = _ROOT.match(raw)
                rung = self.base._rungs[use['rung_id']]
                if root and raw[root.end():root.end() + 1] in {'.', '['}:
                    binding = self.base._resolve(root[0], rung.scope_id)
                    if self.base._qualified(binding, rung.id):
                        target = binding['target_id']
                        if target not in self._uncertain_roots:
                            self._retain(target)
                            self._uncertain_roots.add(target)
        for use in self.base._access.expression_uses:
            expressions[use['rung_id']].append(qualified_use(use))
        eligible, owners = {}, set()
        for rung in self.base._rungs.values():
            result = self._result(rung, by_rung[rung.id], expressions[rung.id])
            reason = 'no_wording' if result is not None else 'unsupported_result'
            # Charge the longest diagnostic up front; later selection can
            # change the enum without silently growing retained memory.
            self._retain((rung.id, max(CONTEXT_REASONS, key=len)))
            self._rung_reasons[rung.id] = reason
            if result is not None:
                eligible[rung.id] = result
                owners.update((result['symbol_id'], result['target_id']))
        if not owners:
            return
        notes = collect_io_annotations(self.base._source, self.base._captured,
                                       self.base._entity_ok, owner_ids=owners)
        comments = None
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
            if selection['conflict']:
                self._rung_reasons[rung_id] = 'conflicting_wording'
                continue
            description_kind = 'result_description'
            if selection['status'] == 'selected':
                note = next(note for note in candidates if note['id'] == selection['preferred_annotation_id'])
                description_owner = (note.get('owner_name')
                    or self.base._resolver.name(self.base._entities[note['owner_id']]))
            else:
                if comments is None:
                    comments = self._qualified_rung_comments(set(eligible))
                if rung_id not in comments:
                    if (rung.comment or '').strip():
                        self._rung_reasons[rung_id] = 'unqualified_wording'
                    continue
                description_kind = 'rung_comment'
                description_owner = f'Rung {rung.number}'
                note = {'id': None, 'text': comments[rung_id], 'owner_id': rung_id,
                        'description_scope': 'rung_comment', 'suffix': ''}
            opcode = self.base._instructions[result['instruction_id']].opcode.upper()
            label = 'Rung comment' if description_kind == 'rung_comment' else 'Result description'
            row = {'kind': ('copy_result' if opcode in _COPIES else
                           'boolean_result' if opcode == 'OTE' else 'calculation_result'),
                'description_kind': description_kind,
                'description': note['text'], 'result_name': ref['raw_text'].strip(),
                'result_id': result['symbol_id'], 'result_suffix': result['suffix'],
                'description_source_id': note['owner_id'], 'description_annotation_id': note['id'],
                'description_basis': note['description_scope'],
                'description_owner_name': description_owner,
                'description_owner_suffix': note.get('owner_suffix', note.get('suffix', '')),
                'rung_id': rung_id, 'instruction_id': result['instruction_id'], 'rung_number': rung.number,
                'path': self.base._path(rung.parent_id) + ' / Rung ' + str(rung.number),
                'basis': ('single_fixed_copy_destination' if opcode in _COPIES
                          else 'single_supported_rung_result'),
                'scope_complete': not gaps, 'scope_gap_reasons': sorted(gaps),
                'notice': (f'{label} from the single matched RLL use rung; it is context, not the field signal\'s source description or confirmed equipment identity.'
                    + (f' {opcode} copies source bytes into one destination element; it does not perform a numeric conversion or rename the source signal.' if opcode in _COPIES else '')
                    + (' Other source languages are outside this lookup.' if 'unsupported_routines' in gaps else '')
                    + (' Additional source is outside the completed scan; this does not establish that the signal has only one use in the entire source.' if gaps else ''))}
            self._retain((rung_id, row))
            self._rungs[rung_id] = row
            self._rung_reasons[rung_id] = description_kind
        for address in self.io.addresses.values():
            if self.reason(address['id']) not in {'result_description', 'rung_comment'}:
                continue
            copy_rung, _ = self._copy_context(address)
            rung_id = copy_rung or address['uses'][0]['rung_id']
            self._retain((address['id'], rung_id))
            self._signals[address['id']] = rung_id

    def _qualified_rung_comments(self, eligible: set[str]) -> dict[str, str]:
        """Read only one plain, namespace-qualified direct Comment per rung."""
        from .source import _read_nodes
        nodes = _read_nodes(self.base._source)
        namespace = nodes[0].expanded_name.rpartition('}')[0]
        okay: list[bool] = []
        rungs = {self.base._rungs[identifier].locator: identifier for identifier in eligible}
        comments = {}
        for node in nodes:
            okay.append(node.expanded_name.rpartition('}')[0] == namespace
                and not any('}' in key for key in node.expanded_attributes)
                and node.attributes.get('Protected', '').casefold() not in {'true', '1'}
                and (node.parent is None or okay[node.parent]))
        for node in nodes:
            identifier = rungs.get(node.locator)
            if identifier is None:
                continue
            selected = [index for index in node.children if nodes[index].name == 'Comment']
            if len(selected) != 1:
                continue
            index = selected[0]
            comment = nodes[index]
            if (okay[index] and not comment.children and comment.text.strip()
                    and comment.text == self.base._rungs[identifier].comment):
                comments[identifier] = comment.text
        return comments

    def reason(self, address_id: str) -> str:
        """Return a closed diagnostic without copying source prose or names."""
        address = self.io.addresses[address_id]
        if specific_description(address):
            return 'specific_source'
        if self._unavailable_reason:
            return self._unavailable_reason
        if self.base._access is None:
            return 'access_unavailable'
        if self.usage._limited:
            return 'usage_unavailable'
        copy_rung, copy_reason = self._copy_context(address)
        if copy_rung:
            return copy_reason or self._rung_reasons.get(copy_rung, 'unsupported_result')
        direct = address['uses']
        if not direct:
            return 'no_direct_use'
        rungs = {use['rung_id'] for use in direct}
        if len(rungs) != 1:
            return 'multiple_rungs'
        if any(use['role'] != 'read' for use in direct):
            return 'nonread_use'
        rung_id = next(iter(rungs))
        if rung_id in self._copies:
            # Enable contacts are not bytes copied to the destination.
            return 'unsupported_result'
        reason = self._rung_reasons.get(rung_id, 'unsupported_result')
        if reason not in {'result_description', 'rung_comment'}:
            return reason
        if address['root_id'] in self._uncertain_roots:
            return 'overlapping_use'
        direct_ids = {use['id'] for use in direct}
        # Root/range/dynamic associations can reveal other uses even when this
        # exact spelling occurs in just one rung. Never conceal those uses.
        if any(identifier not in direct_ids and (not proven or self.usage._uses[identifier]['rung_id'] != rung_id)
               for identifier, _, proven, _ in self.usage._related(address)):
            return 'overlapping_use'
        return reason

    def _copy_context(self, address: dict) -> tuple[str | None, str | None]:
        """Find one copied source footprint, including non-operand source words.

        Query existing authenticated range evidence without expanding arrays or
        retaining prose per field signal. Every other captured or possible use
        blocks attribution to a single copy destination, even on the same rung.
        """
        if not self._copies or self.usage._limited:
            return None, None
        rung_id = None
        for identifier, _, proven, _ in self.usage._related(address):
            candidate_rung = self.usage._uses[identifier]['rung_id']
            copy = self._copies.get(candidate_rung)
            if (not proven or copy is None or identifier != copy['source_use_id']
                    or self.usage._range_resolver.match(copy['source_range'], address)['status'] != 'included'):
                continue
            if rung_id is not None and candidate_rung != rung_id:
                return rung_id, 'multiple_rungs'
            rung_id = candidate_rung
        if rung_id is None:
            return None, None
        source_id = self._copies[rung_id]['source_use_id']
        if address['root_id'] in self._uncertain_roots:
            return rung_id, 'overlapping_use'
        if any(use['id'] != source_id for use in address['uses']):
            return rung_id, 'overlapping_use'
        if any(identifier != source_id or not proven
               for identifier, _, proven, _ in self.usage._related(address)):
            return rung_id, 'overlapping_use'
        return rung_id, None

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
