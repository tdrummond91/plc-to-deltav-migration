"""Source-qualified field-member usage, separate from wiring and runtime state.

Exact operand references are borrowed from FieldIOIndex. Parent/child, copied
range and dynamic-index references are navigation candidates only: a shared
declaration never proves that a particular channel is covered or energized.
"""
from __future__ import annotations

from bisect import bisect_left
from collections import Counter, defaultdict
from copy import deepcopy
import json
import re
from typing import Any, Iterator

from .references import _ADDRESS
from .workspace_field_io import FieldIOIndex, _preview, reference_binding
from .workspace_variables import _child, _member_key

USAGE_STATUSES = ('referenced', 'possible_indirect', 'not_found', 'unknown')
MAX_POSSIBLE_USES = 12
MAX_INDEX_BYTES = 32 * 1024 * 1024
_ROLES = ('read', 'write', 'read_write', 'unknown')
_PART = re.compile(r'\.[^.\[]+|\[[^\]]*\]')
_SAFE_BINDINGS = {'root_bound', 'literal', 'non_data', 'system_flag', 'parsed_expression'}
_NOTICES = {
    'referenced': 'Exact references occur in the captured ladder logic. References do not establish runtime activity, reachability or field wiring.',
    'possible_indirect': 'No exact reference was found. Equivalent numeric spelling, a parent, child, copied range or dynamic index may involve this member; particular channel coverage is not established.',
    'not_found': 'No reference was found in the supported captured ladder scan. External uses, runtime activity, field wiring and spare status are not established.',
    'unknown': 'No usable ladder reference scan is available, or the indirect-reference index reached its limit. This does not establish that the member is unused.',
}


class _UsageLimit(ValueError):
    pass


def _parents(suffix: str) -> Iterator[str]:
    """Visit exact ancestor boundaries, including the declaration root."""
    for match in _PART.finditer(suffix):
        yield suffix[:match.start()]


def _usage_key(suffix: str) -> str:
    """Normalize numeric spelling for association only, never source identity."""
    key = _member_key(suffix)
    key = re.sub(r'\[\s*([0-9]+(?:\s*,\s*[0-9]+)*)\s*\]',
                 lambda match: '[' + ','.join(value.strip().lstrip('0') or '0'
                                               for value in match[1].split(',')) + ']', key)
    return re.sub(r'\.([0-9]+)(?=\.|\[|$)', lambda match: '.' + (match[1].lstrip('0') or '0'), key)


class SignalUsageIndex:
    """Index only qualified uses; inexpensive status queries do not build rows."""

    def __init__(self, field_io: FieldIOIndex) -> None:
        if type(field_io) is not FieldIOIndex:
            raise ValueError('Choose authenticated field evidence for source usage.')
        self.io, self.base = field_io, field_io.base
        self._budget = 0
        self._limited = False
        self._uses: dict[str, dict] = {}
        self._exact: dict[str, dict[str, list[str]]] = defaultdict(dict)
        self._keys: dict[str, list[str]] = {}
        self._ranges: dict[str, list[str]] = defaultdict(list)
        self._dynamic: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        self.gap_reasons = self._coverage_gaps()
        try:
            self._build()
        except _UsageLimit:
            # The auxiliary index is optional. Never lose known exact positives
            # or turn incomplete absence into a confident no-reference result.
            self._limited = True
            self.gap_reasons = sorted(set(self.gap_reasons) | {'usage_index_limit'})
            self._uses.clear()
            self._exact.clear()
            self._keys.clear()
            self._ranges.clear()
            self._dynamic.clear()
            self._budget = 0

    def scan_summary(self) -> dict:
        """Report analysis-wide scan limits separately from access-role gaps."""
        gaps = sorted(set(self._scan_gaps) | ({'usage_index_limit'} if self._limited else set()))
        return {'rungs_total': self._rungs_total, 'rungs_scanned': self._rungs_scanned,
                'rungs_not_scanned': self._rungs_total - self._rungs_scanned,
                'available': self._scan_available and not self._limited,
                'complete': not gaps, 'gap_reasons': gaps,
                'role_gap_reasons': list(self._role_gaps)}

    def _retain(self, value: Any) -> None:
        self._budget += len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self._budget > MAX_INDEX_BYTES:
            raise _UsageLimit()

    def _index_dependency_gap(self, variable: str, rung_id: str) -> bool:
        """Disclose index contents omitted by the root-only dynamic scan.

        A single qualified internal variable is known not to be a field root.
        An alias can still resolve to a field address. Compound or unresolved
        index expressions remain a scan gap until their own source occurrences
        are indexed; never turn their omitted dependencies into absence proof.
        """
        rung = self.base._rungs[rung_id]
        for match in re.finditer(r'\[([^\[\]]*)\]', variable):
            for raw in match[1].split(','):
                token = raw.strip()
                if re.fullmatch(r'[0-9]+', token):
                    continue
                if not _ADDRESS.fullmatch(token):
                    return True
                binding = self.base._resolve(token, rung.scope_id)
                if (binding['status'] != 'root_bound'
                        or not self.base._qualified(binding, rung_id)
                        or binding['target_id'] in self.io._root_module):
                    return True
        return False

    def _coverage_gaps(self) -> list[str]:
        base = self.base
        inventory = base._captured
        reasons, role_reasons = set(), set()
        self._rungs_total = len(inventory.rungs)
        self._rungs_scanned = sum(row.parse_status == 'parsed' and bool(base._rung_ok.get(row.id))
                                  for row in inventory.rungs)
        if not any(row.kind == 'routine' for row in inventory.entities):
            reasons.add('missing_logic')
        target = inventory.export_attributes.get('TargetType')
        if ((target is not None and target.casefold() != 'controller')
                or not any(row.kind == 'controller' for row in inventory.entities)):
            reasons.add('partial_export')
        if not base._has_access:
            role_reasons.add('missing_access')
        if any(row.parse_status != 'parsed' for row in inventory.rungs):
            reasons.add('unparsed_rungs')
        if any(row.kind == 'routine' and row.attributes.get('Type') != 'RLL' for row in inventory.entities):
            reasons.add('unsupported_routines')
        if any(row.kind == 'encoded_region' for row in inventory.entities):
            reasons.add('protected_logic')
        if inventory.coverage.get('routines', {}).get('failed', 0):
            reasons.add('incomplete_routines')
        if (any(not base._rung_ok.get(row.id) for row in inventory.rungs)
                or any(row.kind in {'routine', 'aoi_definition', 'program'} and not base._entity_ok.get(row.id)
                       for row in inventory.entities)):
            reasons.add('unqualified_source')
        access = {row['id']: row for row in base._access.operands} if base._access else {}
        if base._access:
            if any(row['status'] != 'classified' for row in base._access.instructions):
                role_reasons.add('unsupported_instructions')
        for ref in base._references.operands:
            slot = access.get(ref['id'])
            if slot and slot['binding_status'] == 'parsed_expression':
                continue
            binding = reference_binding(base, ref, slot)
            if binding['status'] == 'unsupported_expression':
                reasons.add('opaque_expressions')
            elif binding['status'] not in _SAFE_BINDINGS:
                rung = base._rungs[ref['rung_id']]
                dynamic = base._resolve(ref['raw_text'].strip(), rung.scope_id)
                if (dynamic.get('reason') == 'non_static_array_index'
                        and self._index_dependency_gap(ref['raw_text'], rung.id)):
                    reasons.add('unscanned_index_expressions')
                if (dynamic.get('reason') != 'non_static_array_index'
                        or not base._qualified(dynamic, rung.id)):
                    # A scanned address with an undeclared/ambiguous name is
                    # a binding diagnostic, not an unread rung or expression.
                    (role_reasons if _ADDRESS.fullmatch(ref['raw_text'].strip())
                     else reasons).add('unresolved_references')
        if base._access:
            for use in base._access.expression_uses:
                if use['binding_status'] in _SAFE_BINDINGS:
                    continue
                expression = base._reference_uses[use['expression_operand_id']]
                rung = base._rungs[use['rung_id']]
                binding = base._resolve(expression['raw_text'][use['start']:use['end']], rung.scope_id)
                if (binding.get('reason') == 'non_static_array_index'
                        and self._index_dependency_gap(expression['raw_text'][use['start']:use['end']], rung.id)):
                    reasons.add('unscanned_index_expressions')
                if (binding.get('reason') != 'non_static_array_index'
                        or not base._qualified(binding, rung.id)):
                    (role_reasons if _ADDRESS.fullmatch(expression['raw_text'][use['start']:use['end']])
                     else reasons).add('unresolved_references')
        # A captured, qualified empty RLL routine is a valid zero-reference
        # scan. Missing/protected/failed routine bodies are not empty ladders.
        empty_rll = (not inventory.rungs and any(row.kind == 'routine'
            and row.attributes.get('Type') == 'RLL' and base._entity_ok.get(row.id)
            for row in inventory.entities) and not reasons.intersection(
                {'missing_logic', 'protected_logic', 'incomplete_routines', 'unqualified_source'}))
        self._scan_available = bool(self._rungs_scanned or empty_rll)
        self._scan_gaps, self._role_gaps = sorted(reasons), sorted(role_reasons)
        return sorted(reasons | role_reasons)

    def _build(self) -> None:
        for address in self.io.addresses.values():
            uses = address['uses']
            if not uses:
                continue
            root, suffix = address['root_id'], _usage_key(address['suffix'])
            ids = [use['id'] for use in uses]
            self._retain((root, suffix, ids))
            self._exact[root].setdefault(suffix, []).extend(ids)
            self._uses.update((use['id'], use) for use in uses)
        for root, suffixes in self._exact.items():
            keys = sorted(suffixes)
            self._retain((root, keys))
            self._keys[root] = keys

        access = {row['id']: row for row in self.base._access.operands} if self.base._access else {}
        def candidates():
            yield from self.base._references.operands
            # CPT leaves retain their own source-node IDs and offsets. Resolve
            # dynamic leaves individually, not their containing expression.
            if self.base._access:
                for use in self.base._access.expression_uses:
                    if use['binding_status'] == 'root_bound':
                        continue
                    expression = self.base._reference_uses[use['expression_operand_id']]
                    yield {'id': use['id'], 'instruction_id': use['instruction_id'],
                           'rung_id': use['rung_id'], 'argument_index': -1,
                           'raw_text': expression['raw_text'][use['start']:use['end']],
                           'status': use['binding_status'], 'role': use['role']}

        for ref in candidates():
            if ref['id'] in self.base._reference_uses:
                ref = reference_binding(self.base, ref, access.get(ref['id']))
                if ref['status'] in {'non_data', 'literal', 'system_flag', 'unsupported_expression'}:
                    continue
            instruction = self.base._instructions[ref['instruction_id']]
            opcode = instruction.opcode.upper()
            slot = ref['argument_index']
            is_range = ((opcode in {'COP', 'CPS'} and slot in {0, 1})
                        or (opcode == 'FLL' and slot == 1)) and len(instruction.arguments) == 3
            # Dynamic references require the existing resolver's root-only
            # qualification. A named FLL destination is an exact lexical use;
            # its affected range and read/write semantics stay unevaluated.
            possible_dynamic = '[' in ref['raw_text'] and ref['status'] != 'root_bound'
            if not (is_range or possible_dynamic):
                continue
            rung = self.base._rungs[ref['rung_id']]
            binding = self.base._resolve(ref['raw_text'].strip(), rung.scope_id)
            if (binding.get('target_id') not in self.io._root_module
                    or not self.base._qualified(binding, rung.id)):
                continue
            dynamic = (binding['status'] == 'unsupported_address'
                       and binding.get('reason') == 'non_static_array_index')
            if binding['status'] != 'root_bound' and not dynamic:
                continue
            root = binding['target_id']
            if ref['id'] not in self._uses:
                role = access.get(ref['id'], {}).get('role', ref.get('role', 'unknown'))
                value = {'id': ref['id'], 'rung_id': rung.id, 'instruction_id': instruction.id,
                    'opcode': instruction.opcode, 'role': role if role in _ROLES else 'unknown',
                    'variable': ref['raw_text'], 'path': self.base._path(rung.parent_id) + ' / Rung ' + str(rung.number),
                    'rung_number': rung.number}
                self._retain(value)
                self._uses[ref['id']] = value
            if is_range:
                self._retain((root, ref['id'], 'range_unresolved'))
                self._ranges[root].append(ref['id'])
            if dynamic:
                # Only the static prefix is known. Never evaluate the index or
                # assume a matching physical channel or runtime index value.
                first_dynamic = next(match for match in re.finditer(r'\[([^\]]*)\]', binding['suffix'])
                    if not re.fullmatch(r'\s*[0-9]+(?:\s*,\s*[0-9]+)*\s*', match[1]))
                prefix = _usage_key(binding['suffix'][:first_dynamic.start()])
                self._retain((root, prefix, ref['id'], 'dynamic_index'))
                self._dynamic[root][prefix].append(ref['id'])

    def _address(self, address: dict) -> dict:
        canonical = self.io.addresses.get(address.get('id')) if type(address) is dict else None
        if (canonical is None or address.get('root_id') != canonical['root_id']
                or address.get('suffix') != canonical['suffix']):
            raise ValueError('Choose a field address from this authenticated source.')
        return canonical

    def _possible(self, address: dict) -> Iterator[tuple[str, str]]:
        root, key = address['root_id'], _usage_key(address['suffix'])
        for identifier in self._ranges.get(root, ()):
            yield identifier, 'range_unresolved'
        for prefix, identifiers in self._dynamic.get(root, {}).items():
            if key == prefix or _child(prefix, key) or _child(key, prefix):
                for identifier in identifiers:
                    yield identifier, 'dynamic_index'
        exact = self._exact.get(root, {})
        for identifier in exact.get(key, ()):
            yield identifier, 'equivalent_static_index'
        for parent in _parents(key):
            for identifier in exact.get(parent, ()):
                yield identifier, 'aggregate_parent'
        keys = self._keys.get(root, [])
        for prefix in (key + '.', key + '['):
            start = bisect_left(keys, prefix)
            for index in range(start, len(keys)):
                suffix = keys[index]
                if not suffix.startswith(prefix):
                    break
                for identifier in exact[suffix]:
                    yield identifier, 'aggregate_child'

    def status(self, address: dict) -> str:
        address = self._address(address)
        if address['uses']:
            return 'referenced'
        if not self._limited and next(self._possible(address), None) is not None:
            return 'possible_indirect'
        return 'unknown' if self._limited or not self._scan_available else 'not_found'

    def summary(self, address: dict) -> dict:
        address = self._address(address)
        direct = address['uses']
        direct_ids = {use['id'] for use in direct}
        roles = Counter(use['role'] if use['role'] in _ROLES else 'unknown' for use in direct)
        possible = {}
        if not self._limited:
            for identifier, reason in self._possible(address):
                if identifier not in direct_ids:
                    possible.setdefault(identifier, reason)
        ordered = sorted(possible, key=lambda identifier: (
            self.base._order[self._uses[identifier]['rung_id']],
            self.base._instructions[self._uses[identifier]['instruction_id']].start, identifier))
        status = self.status(address)
        result = {'status': status, 'direct_count': len(direct),
            'direct_rung_count': len({use['rung_id'] for use in direct}),
            'roles': {role: roles[role] for role in _ROLES}, 'possible_count': len(possible),
            'possible_rung_count': len({self._uses[identifier]['rung_id'] for identifier in possible}),
            # Legacy per-row coverage includes role/name diagnostics. The
            # page-level reference_scan.complete describes reference scanning.
            'coverage_complete': not self.gap_reasons, 'gap_reasons': list(self.gap_reasons),
            'notice': _NOTICES[status],
            'possible_uses': [_preview(dict(self._uses[identifier], reason=possible[identifier]))
                              for identifier in ordered[:MAX_POSSIBLE_USES]],
            'possible_uses_truncated': len(ordered) > MAX_POSSIBLE_USES,
            'possible_preview_limit': MAX_POSSIBLE_USES}
        return deepcopy(result)
