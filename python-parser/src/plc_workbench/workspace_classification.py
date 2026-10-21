"""Read-only, snapshot-bound review groups from already validated evidence.

Groups are proposals, not DeltaV module boundaries. In particular an address can
have several writers and a rung can contribute to several groups. This module
never edits the source, runs the PLC, or decides that platform logic is disposable.
The caller must authenticate the saved report before passing it here.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from bisect import bisect_left
from copy import deepcopy
import hashlib
import re
from typing import Any


CATEGORY_DEFINITIONS = tuple({'id': key, 'label': label, 'description': description}
    for key, label, description in (
        ('ai', 'AI — analogue input candidate', 'Input module data with a captured floating-point data leaf; physical channel and scaling need review.'),
        ('ao', 'AO — analogue output candidate', 'Output module data with a captured floating-point data leaf; physical channel and scaling need review.'),
        ('di', 'DI — discrete input candidate', 'Input module data with a captured Boolean data leaf; physical channel assignment needs review.'),
        ('do', 'DO — discrete output candidate', 'Output module data with a captured Boolean data leaf; physical channel assignment needs review.'),
        ('dc', 'DC — discrete calculation', 'Logic computes or stores a true/false result, including separately identified latch behavior.'),
        ('ac', 'AC — analogue calculation', 'A calculation writes a result proved to be REAL or LREAL in the captured source.'),
        ('pid', 'PID control', 'Explicit PID instruction or PID declaration; may require several DeltaV classes.'),
        ('alarm', 'Alarm candidate', 'Alarm instruction, declared alarm object, or explicitly qualified wording hint; shutdown consequence is not inferred.'),
        ('timer', 'Timer', 'Timer control object or instruction; nested timers remain separate source objects.'),
        ('counter', 'Counter', 'Counter control object or instruction; counting and reset behavior need mapping.'),
        ('sequence', 'Sequence or control flow', 'Sequence, jump, call, or related source control flow requiring engineering interpretation.'),
        ('equipment', 'Equipment candidate', 'Equipment wording is a candidate, not proof of a physical device.'),
        ('sensor', 'Sensor candidate', 'Sensor wording is a candidate, not proof of a physical instrument.'),
        ('communication', 'Communication and system access', 'MSG, GSV, SSV or related communications; consumed results may affect the process.'),
        ('data_transfer', 'Data transfer', 'Copies, moves, clears or other data transfer operations.'),
        ('io_input', 'Input module — channel unresolved', 'Explicit input module direction; actual signal, channel role or value type remains unresolved.'),
        ('io_output', 'Output module — channel unresolved', 'Explicit output module direction; actual signal, channel role or value type remains unresolved.'),
        ('calculation', 'Calculation — result type unresolved', 'A calculation is present but a floating-point result has not been proved.'),
        ('condition', 'Conditions and comparisons', 'Boolean contacts or comparisons used as conditions; not a standalone output by themselves.'),
        ('structured', 'Structured object and parameters', 'A source structure or AOI declaration with linked captured parameters.'),
        ('platform', 'Allen-Bradley platform detail', 'Platform/configuration evidence retained for review; exclusion is never automatic.'),
        ('unknown', 'Unclassified / needs investigation', 'Insufficient evidence for a more specific function category.'),
    ))
_CATEGORY_IDS = frozenset(row['id'] for row in CATEGORY_DEFINITIONS)
MAX_GROUPS = 20_000
MAX_MEMBERSHIPS = 100_000
MAX_PARAMETERS = 100_000
MAX_PARAMETERS_PER_GROUP = 128
MAX_TEXT = 8192
_FLOATS = {'REAL', 'LREAL'}
_SCALARS = _FLOATS | {'BOOL', 'SINT', 'INT', 'DINT', 'LINT', 'USINT', 'UINT', 'UDINT', 'ULINT', 'STRING'}
_MATH = set('ADD SUB MUL DIV MOD ABS LN LOG SQR SQRT SIN COS TAN ASN ACS ATN XPY CPT AVE FAL'.split())
_BOOLEAN_OUTPUT = {'OTE', 'OTL', 'OTU', 'ONS', 'OSR', 'OSF'}
_FAMILY = {'pid_control': 'pid', 'boolean_output': 'dc', 'timer_counter': 'timer',
    'data_transfer': 'data_transfer', 'communication_system': 'communication',
    'sequence_control': 'sequence', 'control_flow': 'sequence', 'alarm': 'alarm',
    'equipment': 'equipment', 'sensor': 'sensor', 'io_input': 'io_input',
    'io_output': 'io_output', 'calculation': 'calculation', 'miscellaneous': 'unknown',
    'boolean_condition': 'condition'}
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
_INDEX = re.compile(r'\[\s*[0-9]+(?:\s*,\s*[0-9]+)*\s*\]')
# These are source data-field shapes, not a hardware catalogue or channel proof.
_DATA_LEAF = re.compile(r'(?:\.Data(?:\[[0-9]+\])?|\.Ch[0-9]+Data|\.Ch[0-9]+\.Data)', re.I)


def _snapshot(data: dict[str, Any]) -> str | None:
    return data.get('snapshot', {}).get('id')


def _id(snapshot: str, key: str) -> str:
    return 'classification:' + hashlib.sha256(f'{snapshot}|{key}'.encode()).hexdigest()


def _qualify_source(source: bytes, inventory: dict) -> tuple[dict, dict, str | None]:
    """Check XML provenance; legacy local-name bindings alone are insufficient."""
    from .source import _read_nodes, snapshot_from_bytes
    from .tag_data import _namespace
    if snapshot_from_bytes(source).id != _snapshot(inventory):
        raise ValueError('Classification source does not match the saved snapshot.')
    nodes = _read_nodes(source)
    namespace = _namespace(nodes[0].expanded_name)
    qualified = {}
    by_locator = {node.locator: node for node in nodes}
    for node in nodes:
        qualified[node.locator] = (
            _namespace(node.expanded_name) == namespace
            and not any('}' in key for key in node.expanded_attributes)
            and (node.parent is None or qualified[nodes[node.parent].locator]))
    entities = {row['id']: qualified.get(row.get('locator'), False)
                for row in inventory.get('entities', [])}
    rungs = {}
    for row in inventory.get('rungs', []):
        node = by_locator.get(row.get('locator'))
        rungs[row['id']] = bool(node and qualified[node.locator] and all(
            qualified[nodes[index].locator] for index in node.children if nodes[index].name == 'Text'))
    return entities, rungs, namespace


class _Builder:
    def __init__(self, inventory: dict, analysis: dict, report: dict, source: bytes) -> None:
        self.snapshot = _snapshot(inventory)
        if not self.snapshot or _snapshot(analysis) not in {None, self.snapshot}:
            raise ValueError('Classification evidence does not match the source snapshot.')
        for value in report.values():
            if isinstance(value, dict) and 'snapshot' in value and _snapshot(value) != self.snapshot:
                raise ValueError('Classification evidence does not match the source snapshot.')
        self.inventory, self.analysis, self.report = inventory, analysis, report
        self.entity_ok, self.rung_ok, self.namespace = _qualify_source(source, inventory)
        self.entities = {row['id']: row for row in inventory.get('entities', [])}
        self.children: dict[str, list[dict]] = defaultdict(list)
        for row in self.entities.values():
            self.children[row.get('parent_id')].append(row)
        self.rungs = {row['id']: row for row in inventory.get('rungs', [])}
        self.instructions: dict[str, dict] = {}
        self.instruction_rungs: dict[str, str] = {}
        for rung in self.rungs.values():
            for instruction in rung.get('instructions', []):
                self.instructions[instruction['id']] = instruction
                self.instruction_rungs[instruction['id']] = rung['id']
        self.canonical = self.entities.keys() | self.rungs.keys() | self.instructions.keys()
        self.groups: dict[str, dict] = {}
        self.member_sets: dict[str, set[str]] = defaultdict(set)
        self.rung_sets: dict[str, set[str]] = defaultdict(set)
        self.memberships = self.parameter_count = self.merged = 0
        self.truncated = False
        self.covered_instructions: set[str] = set()
        self.parameters: dict[str, list[dict]] = defaultdict(list)
        self.parameters_total: Counter = Counter()
        self.types: dict[tuple[str, str], list[str]] = defaultdict(list)
        self.ambiguous_paths: dict[str, set[str]] = defaultdict(set)
        self.types_by_id: dict[str, str] = {}
        self.operands = {row['id']: row for row in report.get('access', {}).get('operands', [])}
        self.addresses = {row['id']: row for row in report.get('relationships', {}).get('addresses', [])}
        self.addresses.update({row['id']: row for row in report.get('engineering_assemblies', {}).get('supplemental_addresses', [])})
        self.access_uses = list(self.operands.values()) + report.get('access', {}).get('expression_uses', [])
        self.uses: dict[tuple[str, str], list[dict]] = defaultdict(list)
        self.owner_uses: dict[str, list[dict]] = defaultdict(list)
        for row in self.access_uses:
            if self.qualified_use(row):
                self.uses[row['target_id'], row.get('suffix') or ''].append(row)
                self.owner_uses[row['target_id']].append(row)
        self.owner_suffixes: dict[str, list[str]] = defaultdict(list)
        for owner, suffix in self.uses:
            self.owner_suffixes[owner].append(suffix)
        for values in self.owner_suffixes.values():
            values.sort()
        self._data()

    def qualified_use(self, row: dict) -> bool:
        targets = [row.get('target_id'), row.get('symbol_id', row.get('target_id')),
                   *row.get('alias_chain', [])]
        return (row.get('binding_status') == 'root_bound'
                and self.rung_ok.get(row.get('rung_id'), False)
                and all(self.entity_ok.get(identifier, False) for identifier in targets))

    def _data(self) -> None:
        """Retain uniquely typed decorated paths and bounded captured values.

        Duplicate representations are deliberately not selected as effective
        values. Parameter rows identify each stored occurrence independently.
        """
        data = self.report.get('tag_data', {})
        paths: dict[str, str | None] = {}
        namespaces: dict[str, str | None] = {}
        content_ids = set()
        occurrences: Counter = Counter()
        for row in data.get('contents', []):
            okay = (row.get('format_kind') == 'decorated' and row.get('xml_namespace') == self.namespace
                    and not any('}' in key for key in row.get('attributes', {}))
                    and not row.get('direct_text', '').strip())
            paths[row['id']] = '' if okay else None
            namespaces[row['id']] = row.get('xml_namespace')
            content_ids.add(row['id'])
            if row.get('format_kind') == 'decorated' and not okay:
                self.ambiguous_paths[row.get('owner_id')].add('')
        parents = {row.get('parent_id') for row in data.get('elements', [])}
        for row in data.get('elements', []):
            attrs = row.get('attributes', {})
            parent = paths.get(row.get('parent_id'))
            path = None
            okay = (parent is not None and row.get('kind') not in {'unmodeled', 'opaque'}
                    and row.get('xml_namespace') == namespaces.get(row.get('parent_id'))
                    and not any('}' in key for key in attrs) and not row.get('direct_text', '').strip())
            if row.get('kind') in {'structure', 'structure_member', 'array', 'array_member'} and 'Value' in attrs:
                okay = False
            if okay:
                if row.get('kind') in {'structure', 'array', 'data_value'}:
                    path = parent
                elif row.get('kind') in {'structure_member', 'array_member', 'data_value_member'} and _NAME.fullmatch(attrs.get('Name', '')):
                    path = parent + '.' + attrs['Name']
                elif row.get('kind') == 'element' and _INDEX.fullmatch(attrs.get('Index', '')):
                    path = parent + attrs['Index']
            if path is not None and len(path) > MAX_TEXT:
                path = None
            paths[row['id']] = path
            namespaces[row['id']] = namespaces.get(row.get('parent_id'))
            owner = row.get('owner_id')
            if path is None or not self.entity_ok.get(owner, False):
                if self.entity_ok.get(owner, False) and namespaces.get(row.get('parent_id')) == self.namespace:
                    # An unsupported alternative can conceal a duplicate path.
                    # Preserve source evidence but do not select a type from it.
                    self.ambiguous_paths[owner].add('')
                continue
            if row.get('parent_id') in content_ids or row.get('kind') in {
                    'structure_member', 'array_member', 'data_value_member', 'element'}:
                occurrences[owner, path] += 1
                if occurrences[owner, path] > 1:
                    self.ambiguous_paths[owner].add(path)
            dtype = attrs.get('DataType', '')
            if row.get('kind') == 'element' and not dtype:
                dtype = self.types_by_id.get(row.get('parent_id'), '')
            self.types_by_id[row['id']] = dtype
            if dtype and row.get('kind') in {'data_value', 'data_value_member', 'element'} and row['id'] not in parents:
                self.types[owner, path].append(dtype.upper())
            if 'Value' in attrs:
                self.parameters_total[owner] += 1
                if len(self.parameters[owner]) < MAX_PARAMETERS_PER_GROUP:
                    value = attrs['Value']
                    self.parameters[owner].append({'name': path or '(whole value)',
                        'value': value[:MAX_TEXT], 'datatype': dtype or 'unresolved',
                        'source_id': owner, 'evidence_id': row['id'],
                        'value_truncated': len(value) > MAX_TEXT,
                        'basis': 'Captured export value; not a live or selected effective setting.'})

    def datatype(self, owner: str, suffix: str) -> str | None:
        if not self.entity_ok.get(owner, False):
            return None
        entity = self.entities.get(owner, {})
        attrs = entity.get('attributes', {})
        if not suffix and not attrs.get('Dimensions'):
            dtype = attrs.get('DataType', '').upper()
            if dtype in _SCALARS:
                return dtype
        ambiguous = self.ambiguous_paths[owner]
        if ('' in ambiguous or suffix in ambiguous
                or any(suffix[:match.start()] in ambiguous for match in re.finditer(r'[.\[]', suffix))):
            return None
        types = self.types.get((owner, suffix), [])
        return types[0] if len(types) == 1 else None

    def group(self, owner: str, suffix: str = '', *, rung: bool = False) -> dict | None:
        if owner not in self.canonical:
            return None
        key = ('rung:' if rung else 'address:') + owner + '|' + suffix
        if key in self.groups:
            self.merged += 1
            return self.groups[key]
        if len(self.groups) >= MAX_GROUPS:
            self.truncated = True
            return None
        source = self.entities.get(owner) or self.rungs.get(owner) or self.instructions.get(owner, {})
        name = (f"Rung {source.get('number') or source.get('ordinal') or owner} — remaining functions"
                if rung else str(source.get('name') or source.get('opcode') or source.get('kind') or owner) + suffix)
        group = {'id': _id(self.snapshot, key), 'name': name[:MAX_TEXT], 'anchor_id': owner,
            'address_suffix': suffix, 'category_ids': [], 'member_ids': [], 'rung_ids': [],
            'reason': '', 'basis': '', 'limitations': [], 'parameters': [],
            'migration_hint': 'retain', 'proposal_kind': 'rung_function' if rung else 'source_object'}
        self.groups[key] = group
        self.link(group, owner)
        return group

    def link(self, group: dict | None, *identifiers: str) -> None:
        if group is None:
            return
        key = group['id']
        for identifier in identifiers:
            if identifier not in self.canonical or identifier in self.member_sets[key]:
                continue
            if self.memberships >= MAX_MEMBERSHIPS:
                self.truncated = True
                self.note(group, 'Membership display limit reached; original source records remain available.')
                return
            self.member_sets[key].add(identifier)
            group['member_ids'].append(identifier)
            self.memberships += 1
            rung_id = identifier if identifier in self.rungs else self.instruction_rungs.get(identifier)
            if rung_id and rung_id not in self.rung_sets[key]:
                self.rung_sets[key].add(rung_id)
                group['rung_ids'].append(rung_id)
            if identifier in self.instructions:
                self.covered_instructions.add(identifier)

    @staticmethod
    def note(group: dict | None, text: str) -> None:
        if group is not None and text not in group['limitations']:
            group['limitations'].append(text)

    def classify(self, group: dict | None, categories: list[str], reason: str, basis: str) -> None:
        if group is None:
            return
        for category in categories:
            if category in _CATEGORY_IDS and category not in group['category_ids']:
                group['category_ids'].append(category)
        for field, text in (('reason', reason), ('basis', basis)):
            if text and text not in group[field]:
                group[field] += (' ' if group[field] else '') + text
        if any(category in {'unknown', 'communication', 'platform'} for category in categories):
            group['migration_hint'] = 'investigate'

    def attach_uses(self, group: dict | None, owner: str, suffix: str, *, descendants: bool = False) -> None:
        if group is None:
            return
        rows = self.owner_uses[owner] if descendants and not suffix else self.uses[owner, suffix]
        if descendants and suffix:
            rows = list(rows)
            values = self.owner_suffixes[owner]
            for prefix in (suffix + '.', suffix + '['):
                position = bisect_left(values, prefix)
                while position < len(values) and values[position].startswith(prefix):
                    rows.extend(self.uses[owner, values[position]])
                    position += 1
        writers = set()
        for use in rows:
            if self.memberships >= MAX_MEMBERSHIPS:
                self.truncated = True
                self.note(group, 'Membership display limit reached; original source records remain available.')
                break
            used_suffix = use.get('suffix') or ''
            if descendants and suffix and not (used_suffix == suffix or used_suffix.startswith(suffix + '.') or used_suffix.startswith(suffix + '[')):
                continue
            self.link(group, use.get('instruction_id'), use.get('rung_id'))
            if use.get('role') in {'write', 'read_write'}:
                writers.add(use.get('instruction_id'))
        if len(writers) > 1:
            self.note(group, 'Multiple source writers are linked; execution order and effective writer are not resolved.')

    def add_parameters(self, group: dict | None, owner: str, suffix: str = '') -> None:
        if group is None:
            return
        existing = {row.get('evidence_id') for row in group['parameters']}
        rows = [row for row in self.parameters[owner]
                if row['evidence_id'] not in existing and (not suffix or row['name'] == suffix
                    or row['name'].startswith(suffix + '.') or row['name'].startswith(suffix + '['))]
        room = max(0, min(MAX_PARAMETERS - self.parameter_count, MAX_PARAMETERS_PER_GROUP - len(group['parameters'])))
        group['parameters'].extend(deepcopy(rows[:room]))
        self.parameter_count += len(rows[:room])
        if self.parameters_total[owner] > len(self.parameters[owner]) or len(rows) > room:
            self.truncated = True
            self.note(group, 'Captured parameter display is truncated; inspect the original source for remaining settings.')
        if group['parameters']:
            self.note(group, 'Captured settings may contain duplicate representations; no live or effective value is selected.')

    def declaration_parameters(self, group: dict | None, owner: str, prefix: str = 'Declaration') -> None:
        if group is None:
            return
        attrs = self.entities[owner].get('attributes', {})
        fields = ('DataType', 'Dimensions', 'Usage', 'TagType', 'AliasFor', 'Radix',
                  'Required', 'Visible', 'Constant', 'ExternalAccess', 'Default',
                  'CatalogNumber', 'Vendor', 'ProductType', 'ProductCode')
        for field in fields:
            if field not in attrs:
                continue
            if self.parameter_count >= MAX_PARAMETERS or len(group['parameters']) >= MAX_PARAMETERS_PER_GROUP:
                self.truncated = True
                self.note(group, 'Captured parameter display is truncated; inspect the original source for remaining settings.')
                break
            value = attrs[field]
            group['parameters'].append({'name': f'{prefix}.{field}', 'value': value[:MAX_TEXT],
                'datatype': 'source attribute', 'source_id': owner,
                'value_truncated': len(value) > MAX_TEXT, 'basis': 'Authored declaration attribute; not a runtime value.'})
            self.parameter_count += 1

    def declarations(self) -> None:
        for owner, entity in self.entities.items():
            if not self.entity_ok.get(owner, False):
                group = self.group(owner)
                self.classify(group, ['unknown'], 'Source declaration has unsupported XML qualification.',
                              'Original declaration retained without inferred type or address semantics.')
                self.note(group, 'An extension namespace or attribute prevents a reliable source association.')
                continue
            attrs = entity.get('attributes', {})
            dtype = attrs.get('DataType', '').upper()
            kind = entity.get('kind')
            cats = []
            if dtype == 'PID':
                cats = ['pid', 'structured']
            elif dtype == 'TIMER':
                cats = ['timer', 'structured']
            elif dtype == 'COUNTER':
                cats = ['counter', 'structured']
            elif dtype in {'ALARM_ANALOG', 'ALARM_DIGITAL'}:
                cats = ['alarm', 'structured']
            elif kind in {'aoi', 'data_type'} or (kind in {'tag', 'aoi_local_tag', 'aoi_parameter'} and dtype and dtype not in _SCALARS):
                cats = ['structured']
            elif kind == 'module_input_tag':
                cats = ['io_input']
            elif kind == 'module_output_tag':
                cats = ['io_output']
            elif kind in {'module_config_tag', 'module', 'module_connection', 'module_port', 'module_rack_connection'}:
                cats = ['platform']
            if not cats:
                continue
            group = self.group(owner)
            self.classify(group, cats, 'Explicit source declaration and captured settings.', 'Source declaration; proposed grouping, not a DeltaV class assignment.')
            self.attach_uses(group, owner, '', descendants=True)
            self.add_parameters(group, owner)
            self.declaration_parameters(group, owner)
            if kind in {'aoi', 'data_type'}:
                for child in self.children[owner]:
                    if child.get('kind') in {'aoi_parameter', 'aoi_local_tag'}:
                        self.link(group, child['id'])
                        self.add_parameters(group, child['id'])
                        self.declaration_parameters(group, child['id'], child.get('name') or child['id'])
            if cats == ['platform']:
                self.note(group, 'Platform-specific source can affect faults, timing, communications or process decisions. Review before exclusion.')

    def control_objects(self) -> None:
        for occurrence in self.report.get('pid', {}).get('occurrences', []):
            owner = occurrence.get('backing_owner_id')
            instruction = occurrence.get('id')
            # PID provider may retain a root while explicitly rejecting a member
            # suffix. Resolve that exact suffix from its bound control operand.
            first = self.operands.get(next(iter(occurrence.get('operand_ids', [])), None), {})
            suffix = first.get('suffix') or ''
            qualified = (self.qualified_use(first) and owner == first.get('target_id')
                         and occurrence.get('storage_status') not in {
                             'owner_namespace_unsupported', 'binding_namespace_unsupported', 'signature_unresolved'})
            owner = owner if qualified else instruction
            if not qualified:
                suffix = ''
            group = self.group(owner, suffix)
            self.classify(group, ['pid'], 'Explicit PID instruction and its source control object.', 'PID occurrence evidence.')
            self.link(group, instruction, occurrence.get('rung_id'))
            self.attach_uses(group, owner, suffix, descendants=True)
            self.add_parameters(group, owner, suffix)
            self.note(group, 'PID, input scaling, output handling and cascade paths may map to several DeltaV classes.')
            if not qualified:
                self.note(group, 'Control-address association is unresolved; the instruction is retained separately from any apparent source owner.')
            if occurrence.get('storage_status') not in {'linked', 'no_data', 'no_decorated_data', 'no_pid_structure'}:
                self.note(group, 'PID control storage or type qualification has gaps; inspect the original operands.')
        for obj in self.report.get('stateful_objects', {}).get('objects', []):
            owner, suffix = obj.get('target_id'), obj.get('suffix') or ''
            if not self.entity_ok.get(owner, False):
                continue
            group = self.group(owner, suffix)
            family = obj.get('family')
            cats = ['timer', 'counter'] if family == 'mixed' else [family] if family in {'timer', 'counter'} else ['timer' if obj.get('declaration_kind') == 'timer' else 'counter' if obj.get('declaration_kind') == 'counter' else 'unknown']
            self.classify(group, cats, 'Shared stateful control address, including producers and resets.', 'Stateful object evidence.')
            self.link(group, *(obj.get('producer_ids', []) + obj.get('reset_ids', [])))
            self.attach_uses(group, owner, suffix, descendants=True)
            self.add_parameters(group, owner, suffix)
            self.note(group, 'Each timer/counter remains a separate object; a rung may require more than one target class.')
            if obj.get('type_conflict'):
                self.note(group, 'Instruction family conflicts with the captured declaration type.')

    def address_groups(self) -> None:
        """Classify actual output destinations and exact shared data addresses."""
        # Validated access also covers older saved reports without assemblies.
        for (owner, suffix), uses in self.uses.items():
            entity = self.entities[owner]
            cats: list[str] = []
            dtype = self.datatype(owner, suffix)
            kinds = {'module_input_tag': ('io_input', 'ai', 'di'), 'module_output_tag': ('io_output', 'ao', 'do')}
            direction = kinds.get(entity.get('kind'))
            typed_data = bool(direction and _DATA_LEAF.fullmatch(suffix) and dtype in _FLOATS | {'BOOL'})
            if direction:
                cats.append(direction[1] if typed_data and dtype in _FLOATS else direction[2] if typed_data else direction[0])
            for use in uses:
                if use.get('role') not in {'write', 'read_write'}:
                    continue
                opcode = self.instructions.get(use.get('instruction_id'), {}).get('opcode', '').upper()
                if opcode in _BOOLEAN_OUTPUT:
                    cats.append('dc')
                elif opcode in _MATH:
                    cats.append('ac' if dtype in _FLOATS else 'calculation')
                elif opcode in {'MOV', 'MVM', 'CLR', 'COP', 'CPS', 'SWPB'}:
                    cats.append('data_transfer')
                elif opcode in {'GSV', 'SSV', 'MSG'}:
                    cats.append('communication')
                    if opcode in {'GSV', 'SSV'}:
                        cats.append('platform')
            # Read-only scalar addresses are still discoverable, but aren't
            # invented sensor/AI/DI objects just because their type is numeric.
            group = self.group(owner, suffix)
            self.classify(group, cats, 'Exact source address with linked uses across rungs.', 'Bound source operands and captured declaration/data types.')
            self.attach_uses(group, owner, suffix)
            self.add_parameters(group, owner, suffix)
            if direction:
                self.note(group, 'Module direction is explicit. Hardware channel, wiring, scaling and physical signal identity are not confirmed.')
                if not typed_data:
                    self.note(group, 'The member is not a uniquely typed supported data leaf; status/configuration bits are not promoted to physical I/O.')
            if 'calculation' in cats:
                self.note(group, 'Calculation result is not proved floating point; integer and unresolved member results are not AC.')
            if any(self.instructions.get(use.get('instruction_id'), {}).get('opcode', '').upper() in {'OTL', 'OTU', 'ONS', 'OSR', 'OSF'} for use in uses):
                self.note(group, 'Latched or edge-storage behavior requires explicit mapping; this is not a stateless Boolean equation.')

        memberships = self.report.get('engineering_assemblies', {}).get('memberships', [])
        for row in memberships:
            address = self.addresses.get(row.get('group_id'))
            if not address or not self.entity_ok.get(address.get('target_id'), False) or not self.rung_ok.get(row.get('rung_id'), False):
                continue
            group = self.group(address.get('target_id'), address.get('suffix') or '')
            self.link(group, row.get('instruction_id'), row.get('rung_id'))
            self.classify(group, [], 'Qualified source assembly links are included.', 'Exact-address assembly evidence; no equipment identity inferred.')
            if 'competing_writers' in row.get('context_flags', []):
                self.note(group, 'Multiple source writers are linked; execution order and effective writer are not resolved.')

    def rung_fallbacks(self) -> None:
        candidates: dict[str, list[dict]] = defaultdict(list)
        for row in self.analysis.get('candidates', []):
            candidates[row.get('rung_id')].append(row)
        blocks = {row['id']: row for row in self.analysis.get('blocks', [])}
        represented: dict[str, set[str]] = defaultdict(set)
        for group in self.groups.values():
            for identifier in group['member_ids']:
                if identifier in self.instructions:
                    represented[identifier].update(group['category_ids'])

        def block_category(identifier: str) -> str:
            if not self.rung_ok.get(self.instruction_rungs.get(identifier), False):
                return 'unknown'
            block = blocks.get(identifier, {})
            opcode = self.instructions.get(identifier, {}).get('opcode', '').upper()
            if opcode in {'CTU', 'CTD'}:
                return 'counter'
            return _FAMILY.get(block.get('family'), 'unknown')

        def has_function(identifier: str) -> bool:
            category = block_category(identifier)
            acceptable = {'ac', 'calculation'} if category == 'calculation' else {category}
            # Linking an operand is not the same as representing its function.
            # An unknown instruction must remain visible for investigation.
            return category != 'unknown' and bool(acceptable & represented[identifier])

        for rung_id, rung in self.rungs.items():
            remaining = [row['id'] for row in rung.get('instructions', []) if not has_function(row['id'])]
            remaining_set = set(remaining)
            hints = [row for row in candidates[rung_id] if row.get('basis') == 'text_hint']
            if not remaining and not hints and rung.get('instructions'):
                continue
            group = self.group(rung_id, rung=True)
            categories = []
            for identifier in remaining:
                block = blocks.get(identifier, {})
                categories.append(block_category(identifier))
                if block.get('opcode', '').upper() in {'GSV', 'SSV', 'JMP', 'LBL', 'JSR', 'SBR', 'RET'}:
                    categories.append('platform')
            for row in candidates[rung_id]:
                if row.get('basis') == 'text_hint' or set(row.get('evidence_ids', [])) & remaining_set:
                    category = _FAMILY.get(row.get('category'), 'unknown')
                    # The broader timer_counter provider also describes CTU/CTD.
                    if row.get('category') == 'timer_counter' and not any(block_category(identifier) == 'timer' for identifier in remaining):
                        continue
                    categories.append(category)
            self.classify(group, categories or ['unknown'], 'Rung functions that are not fully represented by a source object group.', 'Existing rung candidates and instruction families; multi-function classifications retained.')
            self.link(group, *remaining)
            if hints:
                self.note(group, 'Name/comment hints identify review candidates only; they do not establish alarm consequence, equipment or sensor identity.')
            if not self.rung_ok.get(rung_id, False):
                self.note(group, 'Unsupported XML qualification: instruction meaning and source associations require investigation.')
            if rung.get('parse_status') != 'parsed':
                self.note(group, 'Rung parsing is incomplete; original source remains the authority.')

    def result(self) -> dict:
        self.declarations()
        self.control_objects()
        self.address_groups()
        self.rung_fallbacks()
        groups = list(self.groups.values())
        for group in groups:
            if not group['category_ids']:
                group['category_ids'] = ['unknown']
                group['migration_hint'] = 'investigate'
            elif len(group['category_ids']) > 1 and 'unknown' in group['category_ids']:
                # Unknown is retained: a known function does not erase gaps.
                self.note(group, 'Some linked functions remain unclassified alongside the identified categories.')
            group['category_ids'].sort()
        by_category = Counter(category for group in groups for category in group['category_ids'])
        represented = set().union(*(set(group['rung_ids']) for group in groups)) if groups else set()
        limits = ['Groups are review proposals, not confirmed DeltaV modules or execution-equivalent replacements.',
            'Original source, classifications and review decisions are unchanged; platform evidence is retained.',
            'Physical channels, shutdown consequences, alarm ranking and effective runtime settings require engineering confirmation.',
            'Only uniquely captured member types are used; absent, duplicated or unsupported member paths remain unresolved.']
        if self.truncated:
            limits.append('Display limits were reached. Counts and grouped memberships are partial; all original source remains available.')
        return {'snapshot_id': self.snapshot, 'categories': deepcopy(list(CATEGORY_DEFINITIONS)),
            'groups': groups, 'coverage': {'groups': len(groups), 'memberships': self.memberships,
                'parameters': self.parameter_count, 'groups_by_category': dict(by_category),
                'source_rungs': len(self.rungs), 'represented_rungs': len(represented),
                'unrepresented_rungs': len(self.rungs) - len(represented),
                'source_entities': len(self.entities), 'source_instructions': len(self.instructions),
                'merged_anchor_contributions': self.merged, 'truncated': self.truncated},
            'limitations': limits}


def build_classification(inventory: dict, analysis: dict, report: dict, *, source: bytes) -> dict:
    """Project authenticated saved evidence without modifying any input record."""
    return _Builder(inventory, analysis, report, source).result()
