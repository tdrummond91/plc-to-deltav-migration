"""Source-qualified field-member usage, separate from wiring and runtime state.

Exact operand references are borrowed from FieldIOIndex. Static relationships
are resolved separately; dynamic selectors retain their actual source evidence.
Source use does not assert that an instruction executes or a wire is energized.
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
from .workspace_usage_ranges import UsageRangeResolver

USAGE_STATUSES = ('referenced', 'possible_indirect', 'not_found', 'unknown')
MAX_POSSIBLE_USES = 12
MAX_INDEX_BYTES = 32 * 1024 * 1024
_ROLES = ('read', 'write', 'read_write', 'unknown')
_PART = re.compile(r'\.[^.\[]+|\[[^\]]*\]')
_SAFE_BINDINGS = {'root_bound', 'literal', 'non_data', 'system_flag', 'parsed_expression'}
_WORD_OPERATIONS = {'MOV', 'MOVE', 'ADD', 'SUB', 'MUL', 'DIV', 'MOD',
                    'EQU', 'NEQ', 'LES', 'LEQ', 'GRT', 'GEQ', 'LIM',
                    'AND', 'OR', 'XOR', 'NOT', 'CLR', 'NEG', 'ABS', 'CPT'}
_INTEGER_BITS = {'SINT': 8, 'INT': 16, 'DINT': 32, 'LINT': 64}
_NOTICES = {
    'referenced': 'Direct or statically resolved references occur in the captured ladder logic. References do not establish runtime activity, reachability or field wiring.',
    'possible_indirect': 'A related source operand was found. Its explanation identifies the selector or missing layout needed to determine this member\'s access.',
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


def _dynamic_matches(suffix: str, candidate: str) -> bool:
    """Keep literal indices and member names on both sides of a selector."""
    left, right = _PART.findall(_usage_key(suffix)), _PART.findall(candidate)
    for source, target in zip(left, right):
        if source.startswith('[') and target.startswith('['):
            dimensions, selected = source[1:-1].split(','), target[1:-1].split(',')
            if len(dimensions) != len(selected):
                return False
            for value, index in zip(dimensions, selected):
                if (value.strip().isdigit()
                        and (value.strip().lstrip('0') or '0') != (index.strip().lstrip('0') or '0')):
                    return False
        elif source != target:
            return False
    return True


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
        self._range_details: dict[str, dict] = {}
        self._dynamic_details: dict[str, dict] = {}
        self._dynamic: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        self.gap_reasons = self._coverage_gaps()
        try:
            self._range_resolver = UsageRangeResolver(self.base)
            self._budget += self._range_resolver._budget
            self._retain({})
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
            self._range_details.clear()
            self._dynamic_details.clear()
            self._dynamic.clear()
            self._range_resolver = None
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
                descriptor = self._range_resolver.resolve(ref, binding)
                self._retain((root, ref['id'], descriptor))
                self._ranges[root].append(ref['id'])
                self._range_details[ref['id']] = descriptor
            if dynamic:
                # Only the static prefix is known. Never evaluate the index or
                # assume a matching physical channel or runtime index value.
                first_dynamic = next(match for match in re.finditer(r'\[([^\]]*)\]', binding['suffix'])
                    if not re.fullmatch(r'\s*[0-9]+(?:\s*,\s*[0-9]+)*\s*', match[1]))
                prefix = _usage_key(binding['suffix'][:first_dynamic.start()])
                self._retain((root, prefix, ref['id'], 'dynamic_index'))
                self._dynamic[root][prefix].append(ref['id'])
                detail = self._index_detail(ref['raw_text'], rung.id)
                detail['suffix'] = binding['suffix']
                self._retain(detail)
                self._dynamic_details[ref['id']] = detail

    def _index_detail(self, variable: str, rung_id: str) -> dict:
        """Explain selection without mistaking exported values for constants."""
        rung = self.base._rungs[rung_id]
        explanations, sources, source_count = [], [], 0
        tokens = list(dict.fromkeys(token.strip() for match in re.finditer(r'\[([^\[\]]*)\]', variable)
                     for token in match[1].split(',') if not re.fullmatch(r'\s*[0-9]+\s*', token)))
        for token in tokens[:4]:
            binding = self.base._resolve(token, rung.scope_id) if _ADDRESS.fullmatch(token) else {}
            if not binding or not self.base._qualified(binding, rung_id):
                explanations.append(f'Index expression {token} must be evaluated at execution; its value has not been statically resolved.')
                continue
            owner = self.base._entities[binding['target_id']]
            key = _usage_key(binding['suffix'])
            dtype = self._range_resolver.scalar_type(owner.id, binding['suffix'])
            label = token + (f' ({dtype})' if dtype else '')
            values = [value for value in self.base._values.get((owner.id, _member_key(binding['suffix'])), ())
                      if value['envelope'] == 'Data' and value['status'] == 'qualified'
                      and value['value_present'] and not self.base._ambiguous.get((owner.id, value['content_id']))]
            if len(values) == 1:
                label += f'; exported value {str(values[0]["value"])[:80]} is a snapshot'
            external = owner.attributes.get('ExternalAccess')
            if external:
                label += f'; external access {external}'
            writers = []
            for use in self.base._writers.get(owner.id, ()):
                used_key = _usage_key(use['suffix'])
                instruction = self.base._instructions[use['instruction_id']]
                if (used_key == key or _child(used_key, key) or _child(key, used_key)
                        or use['uncertain'] or instruction.opcode.upper() in {'COP', 'CPS', 'FLL'}):
                    writers.append(use)
            if writers:
                label += f'; {len(writers)} captured write or unclassified access occurrence(s)'
                source_count += len(writers)
                for writer in writers[:3]:
                    target = self.base._rungs[writer['rung_id']]
                    instruction = self.base._instructions[writer['instruction_id']]
                    sources.append({'variable': token, 'instruction_id': instruction.id, 'rung_id': target.id,
                        'opcode': instruction.opcode, 'role': writer['role'],
                        'path': self.base._path(target.parent_id) + ' / Rung ' + str(target.number)})
            else:
                label += '; no captured ladder writer'
            explanations.append(label + '. A stored value alone does not fix the selected element for every execution.')
        return {'explanation': 'The source uses ' + variable + '. ' + ' '.join(explanations),
                'index_sources': sources, 'index_sources_total': source_count,
                'index_sources_truncated': len(tokens) > 4 or source_count > len(sources)}

    def _address(self, address: dict) -> dict:
        canonical = self.io.addresses.get(address.get('id')) if type(address) is dict else None
        if (canonical is None or address.get('root_id') != canonical['root_id']
                or address.get('suffix') != canonical['suffix']):
            raise ValueError('Choose a field address from this authenticated source.')
        return canonical

    def _related(self, address: dict) -> Iterator[tuple[str, str, bool, str]]:
        """Yield actual relationships with proof separated from target selection."""
        root, key = address['root_id'], _usage_key(address['suffix'])
        range_ids = self._range_details
        for identifier in self._ranges.get(root, ()):
            match = self._range_resolver.match(self._range_details[identifier], address)
            if match['status'] != 'excluded':
                explanation = match['explanation']
                if identifier in self._dynamic_details:
                    explanation = self._dynamic_details[identifier]['explanation'] + ' ' + explanation
                yield identifier, ('fixed_range' if match['status'] == 'included' else 'range_unresolved'), \
                    match['status'] == 'included', explanation
        for prefix, identifiers in self._dynamic.get(root, {}).items():
            if key == prefix or _child(prefix, key) or _child(key, prefix):
                for identifier in identifiers:
                    if (identifier not in range_ids
                            and _dynamic_matches(self._dynamic_details[identifier]['suffix'], key)):
                        yield identifier, 'dynamic_index', False, self._dynamic_details[identifier]['explanation']
        exact = self._exact.get(root, {})
        for identifier in exact.get(key, ()):
            yield identifier, 'equivalent_static_index', True, \
                f'{self._uses[identifier]["variable"]} names this same address; numeric index spelling is equivalent.'
        for parent in _parents(key):
            for identifier in exact.get(parent, ()):
                if identifier in range_ids:
                    continue
                use = self._uses[identifier]
                dtype = self._range_resolver.scalar_type(root, parent)
                bit = key[len(parent):]
                proven = (bool(re.fullmatch(r'\.[0-9]+', bit)) and dtype in _INTEGER_BITS
                          and int(bit[1:]) < _INTEGER_BITS[dtype] and use['role'] in {'read', 'write', 'read_write'}
                          and use['opcode'].upper() in _WORD_OPERATIONS)
                explanation = (f'{use["opcode"]} references the full {dtype} word {use["variable"]}; this address is bit {bit[1:]} of that word.'
                    if proven else f'{use["opcode"]} names containing operand {use["variable"]}. The parser has not established which members this instruction accesses.')
                yield identifier, 'whole_word' if proven else 'aggregate_parent', proven, explanation
        keys = self._keys.get(root, [])
        for prefix in (key + '.', key + '['):
            start = bisect_left(keys, prefix)
            for index in range(start, len(keys)):
                suffix = keys[index]
                if not suffix.startswith(prefix):
                    break
                for identifier in exact[suffix]:
                    yield identifier, 'aggregate_child', True, \
                        f'This containing address is used through member {self._uses[identifier]["variable"]}. This does not mean every member is used.'

    def _associations(self, address: dict) -> tuple[dict, dict]:
        direct_ids = {use['id'] for use in address['uses']}
        resolved, pending = {}, {}
        if not self._limited:
            for identifier, reason, proven, explanation in self._related(address):
                if identifier in direct_ids:
                    continue
                record = {'reason': reason, 'explanation': explanation}
                if proven:
                    resolved.setdefault(identifier, record)
                    pending.pop(identifier, None)
                elif identifier not in resolved:
                    pending.setdefault(identifier, record)
        return resolved, pending

    def resolved_references(self, address: dict) -> Iterator[dict]:
        """All proven occurrences for selected-signal paging, never just previews."""
        address = self._address(address)
        resolved, _ = self._associations(address)
        for identifier, relation in resolved.items():
            yield dict(self._uses[identifier], **relation)

    def status(self, address: dict) -> str:
        address = self._address(address)
        if address['uses']:
            return 'referenced'
        pending = False
        if not self._limited:
            for _, _, proven, _ in self._related(address):
                if proven:
                    return 'referenced'
                pending = True
        if pending:
            return 'possible_indirect'
        return 'unknown' if self._limited or not self._scan_available else 'not_found'

    def summary(self, address: dict) -> dict:
        address = self._address(address)
        direct = address['uses']
        roles = Counter(use['role'] if use['role'] in _ROLES else 'unknown' for use in direct)
        resolved, possible = self._associations(address)
        def resolved_role(identifier: str) -> str:
            return (self._range_details[identifier]['role'] if identifier in resolved
                    and resolved[identifier]['reason'] == 'fixed_range' else self._uses[identifier]['role'])
        roles.update(resolved_role(identifier) for identifier in resolved)
        def ordered(records: dict) -> list[str]:
            return sorted(records, key=lambda identifier: (
                self.base._order[self._uses[identifier]['rung_id']],
                self.base._instructions[self._uses[identifier]['instruction_id']].start, identifier))
        def previews(records: dict) -> list[dict]:
            return [_preview(dict(self._uses[identifier], **records[identifier], role=resolved_role(identifier),
                       **{key: value for key, value in self._dynamic_details.get(identifier, {}).items()
                          if key.startswith('index_sources')}))
                    for identifier in ordered(records)[:MAX_POSSIBLE_USES]]
        status = ('referenced' if direct or resolved else 'possible_indirect' if possible
                  else 'unknown' if self._limited or not self._scan_available else 'not_found')
        result = {'status': status, 'direct_count': len(direct),
            'direct_rung_count': len({use['rung_id'] for use in direct}),
            'roles': {role: roles[role] for role in _ROLES}, 'possible_count': len(possible),
            'possible_rung_count': len({self._uses[identifier]['rung_id'] for identifier in possible}),
            # Legacy per-row coverage includes role/name diagnostics. The
            # page-level reference_scan.complete describes reference scanning.
            'coverage_complete': not self.gap_reasons, 'gap_reasons': list(self.gap_reasons),
            'notice': _NOTICES[status],
            'detail': next(iter(possible.values()))['explanation'] if possible and not (direct or resolved) else '',
            'resolved_count': len(resolved),
            'resolved_rung_count': len({self._uses[identifier]['rung_id'] for identifier in resolved}),
            'resolved_uses': previews(resolved),
            'resolved_uses_truncated': len(resolved) > MAX_POSSIBLE_USES,
            'possible_uses': previews(possible),
            'possible_uses_truncated': len(possible) > MAX_POSSIBLE_USES,
            'possible_preview_limit': MAX_POSSIBLE_USES}
        return deepcopy(_preview(result))
