"""Bounded source-qualified variable inspection from immutable saved evidence.

Captured values retain their representation. Possible explicit writers are not
reaching definitions, and whole-control uses do not identify affected members.
No lookup changes source bindings or computes live or initial controller state.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult, _derive_access
from .calculations import CalculationResult, _derive as _derive_calculations
from .pid_members import FIELD_CATALOG
from .references import ReferenceResult, _Resolver, _address, _literal, _non_static_index, _ROOT, validate_references
from .source import MAX_SOURCE_BYTES, analyze_snapshot, snapshot_from_bytes
from .stateful_objects import _declaration
from .tag_data import TagDataResult, _capture, _strict_match, render_tag_data_json
from .workspace_classification import _qualify_source
from .workspace_connections import _inventory, _plain

MAX_VARIABLE = 4096
MAX_TEXT = 4096
MAX_VALUES = 24
MAX_WRITERS = 40
MAX_RESPONSE_BYTES = 256 * 1024
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_INDEX_BYTES = 64 * 1024 * 1024
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*', re.ASCII)
_INDEX = re.compile(r'\[\s*[0-9]+(?:\s*,\s*[0-9]+)*\s*\]', re.ASCII)
_TIMER_OPS = frozenset({'TON', 'TOF', 'RTO', 'CTU', 'CTD'})
_MEMBER_LABELS = {
    'TIMER': {
        'PRE': 'Preset time: the target duration compared with accumulated time, in milliseconds for a standard TIMER.',
        'ACC': 'Accumulated time, in milliseconds for a standard TIMER. Accumulation and retention depend on TON, TOF, or RTO execution; an exported value is not a live elapsed-time reading.',
        'EN': 'Enable status records the incoming condition when the timer instruction executes; the captured bit is not its current live condition.',
        'TT': 'Timing status indicates that the timer is timing. Its meaning depends on the timer instruction and its execution state.',
        'DN': 'Done status participates in the timer completion condition. TON, TOF, and RTO use or retain this state differently; an exported bit alone does not establish completion now.',
    },
    'TIMER_T': {'PRE': 'Preset time: target duration for this timer type; units are not established by this lookup.',
                'ACC': 'Accumulated time for this timer type; units and live elapsed time are not established by this lookup.'},
    'COUNTER': {
        'PRE': 'Preset count: the threshold compared with the accumulated count to determine counter done status.',
        'ACC': 'Accumulated count records counted transitions, rather than every scan. CTU and CTD execution and resets determine how it changes.',
        'CU': 'Count-up status records the count-up instruction condition used to recognize a new counting transition.',
        'CD': 'Count-down status records the count-down instruction condition used to recognize a new counting transition.',
        'DN': 'Done status indicates that the accumulated count meets or exceeds the preset count when evaluated by the counter instruction.',
        'OV': 'Overflow status records an upward counter overflow condition; the saved bit is not a current live fault reading.',
        'UN': 'Underflow status records a downward counter underflow condition; the saved bit is not a current live fault reading.',
    },
    'PID': {name: row['label'] for name, row in FIELD_CATALOG.items()},
}
_BASE_LIMITATIONS = (
    'Values are captured export evidence, not live readings, guaranteed startup values, or selected effective settings.',
    'Writers are possible explicit uses; execution order, reaching writes, copied ranges, and external writes are not established.',
    'Whole-control uses remain separate from exact member writes; their presence does not prove that this member changes.',
)


class VariableError(ValueError):
    """Fixed source-free evidence or selection failure."""


def _invalid() -> None:
    raise VariableError('Saved variable evidence is inconsistent or exceeds its limits.') from None


def validate_query(run_id: Any, instruction_id: Any, variable: Any) -> None:
    if (type(run_id) is not str or not run_id or len(run_id) > 256
            or type(instruction_id) is not str or not instruction_id or len(instruction_id) > 256
            or type(variable) is not str or not variable.strip() or len(variable) > MAX_VARIABLE
            or any(ord(char) < 32 or ord(char) == 127 for char in run_id + instruction_id + variable)):
        raise VariableError('Choose a captured run, instruction, and bounded variable spelling.')


def unavailable(notice: str) -> dict:
    return {'available': False, 'notice': notice, 'binding': None, 'declaration': None,
            'member': None, 'display_value': None, 'captured_values': [], 'captured_values_total': 0,
            'captured_values_truncated': False, 'writers': [], 'writers_total': 0,
            'writers_truncated': False, 'representations': [], 'representations_total': 0,
            'representations_truncated': False, 'limitations': list(_BASE_LIMITATIONS)}


def _upper(value: str) -> str:
    return value.upper() if value.isascii() else value


def _child(parent: str, descendant: str) -> bool:
    return descendant.startswith(parent + '.') or descendant.startswith(parent + '[')


def _member_key(suffix: str) -> str:
    """Preview association only; preserve bracket spelling and source suffixes."""
    return re.sub(r'\.[A-Za-z_][A-Za-z0-9_]*', lambda match: match.group().lower(), suffix)


class VariableIndex:
    """Authenticate once per cached run; each view joins bounded saved records."""

    def __init__(self, source: bytes, inventory: dict, references: dict,
                 access: dict | None = None, tag_data: dict | None = None,
                 calculations: dict | None = None) -> None:
        try:
            self._build(source, inventory, references, access, tag_data, calculations)
        except VariableError:
            raise
        except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
            _invalid()

    def _build(self, source: bytes, inventory: dict, references: dict,
               access: dict | None, tag_data: dict | None, calculations: dict | None) -> None:
        if type(source) is not bytes or len(source) > MAX_SOURCE_BYTES:
            _invalid()
        snapshot = snapshot_from_bytes(source)
        captured = _inventory(inventory)
        if not _strict_match(analyze_snapshot(snapshot), captured):
            _invalid()
        refs = ReferenceResult(**_plain(references))
        validate_references(captured, refs)
        # Shared, authenticated immutable records also support the field-I/O
        # projection; keep references rather than copying the saved evidence.
        self._captured, self._references = captured, refs
        self._source = source  # Shared immutable bytes for qualified authored I/O comments.
        self._resolver = _Resolver(captured)
        self._entities = {row.id: row for row in captured.entities}
        self._rungs = {row.id: row for row in captured.rungs}
        self._instructions = {item.id: item for row in captured.rungs for item in row.instructions}
        self._instruction_rung = {item.id: row for row in captured.rungs for item in row.instructions}
        self._order = {row.id: index for index, row in enumerate(captured.rungs)}
        self._entity_ok, self._rung_ok, self._namespace = _qualify_source(source, inventory)
        self._reference_uses = {row['id']: row for row in refs.operands}
        self._access_instructions: dict[str, dict] = {}
        self._expression_variables: dict[str, set[str]] = defaultdict(set)
        access_result = None
        if access is not None:
            access_result = AccessResult(**_plain(access))
            if type(access_result.schema_version) is not int or access_result.schema_version not in {2, 3, 4}:
                _invalid()
            calculation_result = None
            if access_result.schema_version == 4:
                if calculations is None:
                    _invalid()
                calculation_result = CalculationResult(**_plain(calculations))
                if (type(calculation_result.schema_version) is not int or calculation_result.schema_version != 2
                        or not _strict_match(_derive_calculations(snapshot, captured, refs, 2), calculation_result)):
                    _invalid()
                for row in calculation_result.nodes:
                    if row['kind'] == 'reference':
                        self._expression_variables[row['instruction_id']].add(row['raw_text'])
            if not _strict_match(_derive_access(captured, refs, access_result.schema_version, calculation_result), access_result):
                _invalid()
            self._access_instructions = {row['id']: row for row in access_result.instructions}
        self._has_access = access_result is not None
        self._access = access_result
        self._has_data = tag_data is not None
        self._contents: dict[str, list[dict]] = defaultdict(list)
        self._values: dict[tuple[str, str], list[dict]] = defaultdict(list)
        self._types: dict[tuple[str, str], set[str]] = defaultdict(set)
        self._ambiguous: dict[tuple[str, str], set[str]] = defaultdict(set)
        self._paths: dict[str, str] = {}
        self._budget = 0
        if tag_data is not None:
            data = TagDataResult(**_plain(tag_data))
            expected = _capture(snapshot, captured)
            render_tag_data_json(expected)
            if not _strict_match(expected, data):
                _invalid()
            self._data(data)
        self._writers: dict[str, list[dict]] = defaultdict(list)
        if access_result is not None:
            for use in access_result.operands:
                if use['role'] not in {'write', 'read_write', 'unknown'}:
                    continue
                reference = self._reference_uses[use['id']]
                rung = self._rungs[use['rung_id']]
                binding = self._resolve(reference['raw_text'].strip(), rung.scope_id)
                if not self._qualified(binding, rung.id):
                    continue
                row = {'instruction_id': use['instruction_id'], 'rung_id': rung.id,
                       'role': use['role'], 'suffix': binding['suffix'],
                       'uncertain': use['role'] == 'unknown' or binding['status'] != 'root_bound'}
                self._retain(row)
                self._writers[binding['target_id']].append(row)

    def _retain(self, row: Any) -> None:
        self._budget += len(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if self._budget > MAX_INDEX_BYTES:
            _invalid()

    def _path(self, identifier: str | None) -> str:
        if identifier in self._paths:
            return self._paths[identifier]
        names = []
        current, count = identifier, 0
        while current:
            count += 1
            if count > 160:
                _invalid()
            entity = self._entities[current]
            if entity.name:
                names.append(entity.name)
            current = entity.parent_id
        path = ' / '.join(reversed(names)) or '(unassigned source context)'
        if identifier:
            self._retain(path)
            self._paths[identifier] = path
        return path

    def _resolve(self, variable: str, scope_id: str | None) -> dict:
        binding = self._resolver.resolve(variable, scope_id)
        binding['basis'] = 'scoped_captured_declaration'
        if binding['status'] == 'root_bound' and _address('A' + binding['suffix'])[0] is None:
            binding.update(status='unsupported_address', reason='expanded_suffix_invalid',
                           basis='root_only_invalid_suffix')
        if binding['status'] == 'unsupported_address' and _non_static_index(variable):
            root = _ROOT.match(variable)
            if root:
                base = self._resolver.resolve(root.group(), scope_id)
                if base['status'] == 'root_bound':
                    base.update(status='unsupported_address', reason='non_static_array_index',
                                suffix=base['suffix'] + variable[root.end():], basis='root_only_dynamic_index')
                    return base
        return binding

    def _qualified(self, binding: dict, rung_id: str) -> bool:
        identifiers = [binding.get('symbol_id'), binding.get('target_id'), *binding.get('alias_chain', [])]
        return (self._rung_ok.get(rung_id, False) and all(identifier and self._entity_ok.get(identifier, False)
                for identifier in identifiers))

    def _data(self, data: TagDataResult) -> None:
        paths: dict[str, str | None] = {}
        qualified: dict[str, bool] = {}
        contents = {row['id']: row for row in data.contents}
        occurrences: Counter = Counter()
        children = {row['parent_id'] for row in data.elements}
        for row in data.contents:
            self._contents[row['owner_id']].append(row)
            paths[row['id']] = '' if row['format_kind'] == 'decorated' else None
            qualified[row['id']] = (self._entity_ok.get(row['owner_id'], False)
                and row['xml_namespace'] == self._namespace and not row['direct_text'].strip()
                and not any('}' in name for name in row['attributes']))
        for row in data.elements:
            parent = paths[row['parent_id']]
            attrs, path = row['attributes'], None
            if parent is not None:
                if row['xml_name'] in {'Structure', 'Array', 'DataValue'}:
                    path = parent
                elif row['xml_name'] in {'StructureMember', 'ArrayMember', 'DataValueMember'} and _NAME.fullmatch(attrs.get('Name', '')):
                    path = parent + '.' + attrs['Name']
                elif row['xml_name'] == 'Element' and _INDEX.fullmatch(attrs.get('Index', '')):
                    path = parent + attrs['Index']
            if path is not None and len(path) > MAX_VARIABLE:
                path = None
            if path is not None:
                self._retain(path)
            paths[row['id']] = path
            okay = (qualified[row['parent_id']] and row['xml_namespace'] == self._namespace
                and row['kind'] not in {'unmodeled', 'opaque'} and not row['direct_text'].strip()
                and not any('}' in name for name in attrs)
                and not (row['kind'] in {'structure', 'structure_member', 'array', 'array_member'} and 'Value' in attrs))
            qualified[row['id']] = okay
            if path is None:
                if contents[row['content_id']]['format_kind'] == 'decorated':
                    # An unfamiliar alternative may hide another authored path;
                    # keep it opaque and withhold a single-value projection.
                    self._ambiguous[row['owner_id'], row['content_id']].add('')
                continue
            content = contents[row['content_id']]
            identity = (row['owner_id'], row['content_id'])
            key = _member_key(path)
            if row['parent_id'] in contents or row['xml_name'] in {'StructureMember', 'ArrayMember', 'DataValueMember', 'Element'}:
                occurrences[identity, key] += 1
                if occurrences[identity, key] > 1:
                    self._ambiguous[identity].add(key)
            if not okay:
                self._ambiguous[identity].add(key)
            if okay and attrs.get('DataType'):
                self._types[row['owner_id'], key].add(attrs['DataType'])
            if row['xml_name'] in {'DataValue', 'DataValueMember', 'Element'}:
                record = {'element_id': row['id'], 'content_id': row['content_id'], 'owner_id': row['owner_id'],
                    'envelope': content['xml_name'], 'format': content['format_kind'], 'path': path,
                    'datatype': attrs.get('DataType'), 'radix': attrs.get('Radix'),
                    'value': attrs.get('Value'), 'value_present': 'Value' in attrs,
                    'status': 'qualified' if okay and row['id'] not in children else 'shape_or_namespace_gap',
                    'locator': content['locator'], 'ambiguous': False}
                # IDs and the content locator identify exact stored evidence;
                # no invented validated member address or default is persisted.
                self._retain(record)
                self._values[row['owner_id'], key].append(record)

    def _member(self, owner: Any, suffix: str, values: list[dict]) -> dict | None:
        if not suffix:
            return None
        match = re.search(r'\.([A-Za-z_][A-Za-z0-9_]*)$', suffix)
        name = match.group(1) if match else None
        parent = suffix[:match.start()] if match else suffix
        types = set(self._types.get((owner.id, _member_key(parent)), set()))
        root_type = owner.attributes.get('DataType', '')
        root_selected = _declaration(owner, parent)[1] in {'scalar', 'static_in_bounds'}
        if root_selected and root_type:
            types.add(root_type)
        normalized = {_upper(value) for value in types}
        dtype = next(iter(normalized)) if len(normalized) == 1 else None
        basis = 'root_declaration' if root_selected and root_type else 'captured_decorated_structure' if types else 'unresolved'
        field = _upper(name) if name else None
        meaning = _MEMBER_LABELS.get(dtype, {}).get(field)
        units = ('ms' if dtype == 'TIMER' else 'counts' if dtype == 'COUNTER' else None) if field in {'PRE', 'ACC'} else None
        member_types = {row['datatype'] for row in values if row['status'] == 'qualified' and row['datatype']}
        expected_member = ('DINT' if field in {'PRE', 'ACC'} else 'BOOL') if dtype in {'TIMER', 'COUNTER'} else None
        type_conflict = bool(expected_member and any(_upper(value) != expected_member for value in member_types))
        if type_conflict:
            meaning = units = None
        reference = ('https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/37-00/'
                     'contents-ditamap/instruction-set/timer-and-counter-instructions/'
                     + ('timer-on-delay--ton-.html' if dtype == 'TIMER' else 'count-up--ctu-.html')) if dtype in {'TIMER', 'COUNTER'} else None
        return {'name': name, 'path': suffix, 'meaning': meaning,
                'datatype': next(iter(member_types)) if len(member_types) == 1 else None,
                'type_basis': basis, 'parent_datatype': dtype, 'units': units,
                'reference': reference,
                'status': 'type_ambiguous' if type_conflict or len(normalized) > 1 else 'known' if meaning else 'unknown'}

    def view(self, instruction_id: str, variable: str) -> dict:
        if instruction_id not in self._instructions:
            raise VariableError('This instruction is not present in the selected run.')
        instruction = self._instructions[instruction_id]
        rung = self._instruction_rung[instruction_id]
        requested = variable.strip()
        actual = requested in {argument.strip() for argument in instruction.arguments}
        expression = requested in self._expression_variables.get(instruction_id, set())
        derived = False
        if (_upper(instruction.opcode) in _TIMER_OPS
                and self._access_instructions.get(instruction_id, {}).get('status') == 'classified'
                and len(instruction.arguments) == 3):
            derived = requested in {instruction.arguments[0].strip() + '.PRE', instruction.arguments[0].strip() + '.ACC'}
        if not (actual or expression or derived):
            raise VariableError('Choose a variable captured by this instruction or its supported preset/accumulator member.')
        if not self._rung_ok.get(rung.id, False):
            return unavailable('The instruction has unsupported XML provenance; variable associations are withheld.')
        if _literal(requested) or requested == '?':
            return unavailable('This captured argument is a literal or placeholder, not a declared variable.')
        binding = self._resolve(requested, rung.scope_id)
        if not self._qualified(binding, rung.id):
            result = unavailable('This variable could not be associated with one qualified scoped declaration.')
            result['binding'] = binding
            return result
        owner = self._entities[binding['target_id']]
        scope = self._entities.get(owner.scope_id)
        suffix = binding['suffix']
        key = _member_key(suffix)
        candidates = self._values.get((owner.id, key), []) if binding['status'] == 'root_bound' else []
        values = []
        display_candidates = []
        data_candidate_total = 0
        ambiguous_values = False
        for candidate in candidates:
            row = dict(candidate)
            ambiguous = self._ambiguous[owner.id, row['content_id']]
            row['ambiguous'] = any(part == key or not part or _child(part, key) for part in ambiguous)
            ambiguous_values |= row['ambiguous']
            if len(values) < MAX_VALUES:
                values.append(row)
            if row['envelope'] == 'Data':
                data_candidate_total += 1
                if (row['format'] == 'decorated' and row['status'] == 'qualified'
                        and row['value_present'] and not row['ambiguous'] and len(display_candidates) < 2):
                    display_candidates.append(row)
        member = self._member(owner, suffix, candidates)
        representations = self._contents.get(owner.id, [])
        data_contents = [row for row in representations if row['xml_name'] == 'Data' and row['format_kind'] == 'decorated']
        display = None
        if (len(data_contents) == 1 and len(display_candidates) == 1
                and data_candidate_total == 1
                and (member is None or member['status'] != 'type_ambiguous')
                and len(display_candidates[0]['value']) <= MAX_TEXT):
            row = display_candidates[0]
            display = {'value': row['value'], 'datatype': row['datatype'], 'units': member['units'] if member else None,
                       'envelope': 'Data', 'basis': 'Decorated Data export'}
        writers = []
        writer_total = 0
        for use in self._writers.get(owner.id, []):
            used = self._instructions[use['instruction_id']]
            used_key = _member_key(use['suffix'])
            relation = ('possible_overlap' if use['uncertain'] else 'exact_address' if used_key == key
                        else 'whole_control' if _child(used_key, key)
                        else 'possible_overlap' if _child(key, used_key) or _upper(used.opcode) in {'COP', 'CPS'} else None)
            if relation is None:
                continue
            writer_total += 1
            if len(writers) >= MAX_WRITERS:
                continue
            writer_rung = self._rungs[use['rung_id']]
            writers.append({'rung_id': writer_rung.id, 'instruction_id': used.id, 'opcode': used.opcode,
                'role': use['role'], 'relation': relation,
                'path': self._path(writer_rung.parent_id) + ' / Rung ' + (writer_rung.number or str(writer_rung.ordinal)),
                'rung_number': writer_rung.number,
                'instruction_text': (writer_rung.text or '')[used.start:min(used.end, used.start + MAX_TEXT)],
                'instruction_text_truncated': used.end - used.start > MAX_TEXT,
                'source_order': self._order[writer_rung.id]})
        limitations = list(_BASE_LIMITATIONS)
        limitations.append('This preview matches ASCII member names without case differences; index spelling and the original source remain unchanged.')
        if not self._has_access:
            limitations.append('Saved access evidence is absent; no writer list is available.')
        if not self._has_data:
            limitations.append('Saved tag-data evidence is absent; no stored values are supplied.')
        if binding['status'] != 'root_bound':
            limitations.append('The member/index suffix is unresolved. Only the root declaration is associated; no element value is selected.')
        if len(representations) > 1:
            limitations.append('Other Data/DefaultData representations are retained separately and have not been reconciled.')
        if ambiguous_values or len(data_contents) > 1:
            limitations.append('Repeated or structurally ambiguous decorated evidence prevents a single inline value.')
        if member and member['status'] != 'known':
            limitations.append('This member has no unambiguous documented meaning in the current type catalogue; no meaning is inferred from its name.')
        referenced = self._entities.get(binding.get('symbol_id'))
        source_declaration = None
        if referenced and referenced.id != owner.id:
            source_declaration = {'id': referenced.id, 'name': referenced.name,
                'path': self._path(referenced.id), 'description': referenced.description,
                'tag_type': referenced.attributes.get('TagType'),
                'alias_for': referenced.attributes.get('AliasFor'),
                'external_access': referenced.attributes.get('ExternalAccess')}
        result = {'available': True, 'notice': 'Captured declaration, saved representations, and possible source writers.',
            'binding': binding,
            'source_declaration': source_declaration,
            'declaration': {'id': owner.id, 'name': owner.name, 'kind': owner.kind, 'path': self._path(owner.id),
                'scope_id': owner.scope_id, 'scope_kind': scope.kind if scope else None,
                'scope_name': scope.name if scope else None, 'scope_path': self._path(owner.scope_id),
                'datatype': owner.attributes.get('DataType'), 'description': owner.description,
                'attributes': dict(owner.attributes)},
            'member': member, 'display_value': display,
            'captured_values': values, 'captured_values_total': len(candidates), 'captured_values_truncated': len(candidates) > MAX_VALUES,
            'writers': writers, 'writers_total': writer_total, 'writers_truncated': writer_total > MAX_WRITERS,
            'representations': [{'content_id': row['id'], 'envelope': row['xml_name'], 'format': row['format_kind'],
                                 'locator': row['locator'], 'status': 'captured'} for row in representations[:MAX_VALUES]],
            'representations_total': len(representations), 'representations_truncated': len(representations) > MAX_VALUES,
            'limitations': limitations}
        return self._bounded(result)

    @staticmethod
    def _bounded(result: dict) -> dict:
        # Retain source-linked previews. Full source remains available through
        # /api/source; a large value must not turn a hover into an unbounded dump.
        for row in [result['declaration'], result.get('source_declaration'), *result['captured_values'],
                    *result['writers'], *result['representations']]:
            if row is None:
                continue
            for key, value in list(row.items()):
                if type(value) is str and len(value) > MAX_TEXT:
                    row[key] = value[:MAX_TEXT]
                    row[key + '_truncated'] = True
            if 'attributes' in row:
                attrs = row['attributes']
                row['attributes'] = {key[:128]: value[:MAX_TEXT] for key, value in list(attrs.items())[:24]}
                row['attributes_truncated'] = len(attrs) > 24 or any(len(key) > 128 or len(value) > MAX_TEXT for key, value in attrs.items())
        while len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > MAX_RESPONSE_BYTES:
            field = max(('writers', 'captured_values', 'representations'), key=lambda name: len(result[name]))
            if not result[field]:
                _invalid()
            result[field].pop()
            result[field + '_truncated'] = True
        return deepcopy(result)
