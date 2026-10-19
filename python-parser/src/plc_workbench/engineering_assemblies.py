"""Bounded, exact-address source assemblies across existing qualified providers.

These are indexes of source occurrences, not inferred equipment or executable
dataflow. Provider IDs retain the original rung, edit, alias and branch evidence.
Only canonical provider dictionaries produced by the review pipeline are inputs.
No source files, subprocesses, network or transitive path expansion are used.
"""
from __future__ import annotations

from collections import defaultdict
import json
from typing import Any, Iterator

from .references import MAX_ADDRESS_LENGTH, _ADDRESS
from .relationships import _identifier
from .rack_backing_context import CONTEXT_CONSTANTS as RACK_CONSTANTS, _id as _rack_id

MAX_ENGINEERING_ASSEMBLIES_BYTES = 64 * 1024 * 1024
MAX_ASSEMBLY_MEMBERSHIPS = 100_000
MAX_ASSEMBLY_GROUPS = 20_000
MAX_ASSEMBLY_VISITS = 500_000
FIXED_BYTES = 32_768
GROUP_BYTES = 1024
PROVIDERS = frozenset({'signal_context', 'pid_connections', 'calculation_paths',
    'stateful_objects', 'sfc_context', 'file_operations'})
RELATIONS = frozenset({'read', 'write', 'read_write', 'unknown', 'expression_read',
    'boolean_output', 'boolean_condition', 'guard_condition', 'pid_slot', 'pid_address_use',
    'calculation_input', 'calculation_output', 'stateful_control', 'stateful_member',
    'sfc_reference', 'file_read', 'file_write', 'file_read_write', 'file_unknown'})
FLAGS = frozenset({'binding_gap', 'namespace_gap', 'opaque_guard', 'stateful_guard',
    'unknown_role', 'competing_writers', 'branched', 'source_truncated',
    'pid_control_gap', 'pid_master_gap', 'stateful_type_gap', 'selector_or_array_span',
    'communication_control_only', 'alarm_wording', 'equipment_wording', 'sensor_wording',
    'module_input', 'module_output'})
GAP_REASONS = frozenset({'provider_partial', 'provider_missing', 'binding_or_namespace',
    'missing_address', 'ineligible_occurrence', 'unqualified_membership', 'unknown_role',
    'source_truncated', 'dynamic_address', 'communication_semantics_unmodeled',
    'unsupported_member', 'context_gap'})
EXCLUSION_REASONS = GAP_REASONS - {'provider_partial', 'provider_missing',
    'source_truncated', 'communication_semantics_unmodeled', 'unknown_role', 'context_gap'}
COUNT_MAPS = {'memberships_by_provider': PROVIDERS, 'memberships_by_relation': RELATIONS,
    'memberships_by_flag': FLAGS, 'groups_by_flag': FLAGS,
    'excluded_by_provider': PROVIDERS, 'excluded_by_reason': EXCLUSION_REASONS,
    'providers_by_status': frozenset({'complete', 'partial', 'missing'})}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | frozenset({'groups_total', 'memberships_total',
    'multirung_groups', 'multiprovider_groups', 'groups_with_boundary_flags',
    'source_gap_buckets', 'source_gap_counts', 'excluded_total',
    'visited_rows', 'visited_links', 'retained_bytes'})
ASSEMBLY_CONSTANTS = {'schema_version': 1, 'analyzer_version': 'engineering-assemblies-1',
    'analysis_scope': 'qualified_exact_address_source_assemblies',
    'engineering_review': 'unreviewed', 'execution_analysis': 'not_implemented',
    'equipment_identity': 'not_inferred', 'shutdown_analysis': 'not_implemented'}
ASSEMBLY_CONSTANTS_V2 = {**ASSEMBLY_CONSTANTS, 'schema_version': 2,
    'analyzer_version': 'engineering-assemblies-2'}
COVERAGE_KEYS_V2 = COVERAGE_KEYS | {'supplemental_addresses_total', 'excluded_by_provider_reason'}
ASSEMBLY_CONSTANTS_V3 = {**ASSEMBLY_CONSTANTS, 'schema_version': 3,
    'analyzer_version': 'engineering-assemblies-3'}
RACK_RELATIONS = frozenset({'read', 'write', 'read_write', 'unknown', 'boolean_condition',
    'boolean_output', 'guard_condition', 'sfc_reference'})
NON_ADDRESS_KINDS = frozenset({'literal', 'system_flag'})
COUNT_MAPS_V3 = {**COUNT_MAPS, 'rack_memberships_by_relation': RACK_RELATIONS,
    'known_non_address_guard_inputs_by_kind': NON_ADDRESS_KINDS}
COVERAGE_KEYS_V3 = COVERAGE_KEYS_V2 | {'rack_memberships_total',
    'rack_memberships_by_relation', 'known_non_address_guard_inputs_by_kind'}
_ROLES = ('read', 'write', 'read_write', 'unknown')
_CATEGORIES = {'alarm': 'alarm_wording', 'equipment': 'equipment_wording',
    'sensor': 'sensor_wording', 'module_input': 'module_input', 'module_output': 'module_output'}


class EngineeringAssembliesError(ValueError):
    """Fixed source-free error for invalid or oversized canonical projections."""


def _invalid() -> None:
    raise EngineeringAssembliesError('Engineering assembly evidence is inconsistent or exceeds its limits.') from None


def _encoded(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode('utf-8'))


class _Builder:
    def __init__(self, data: dict[str, Any], schema_version: int) -> None:
        self.data = data
        self.schema_version = schema_version
        self.coverage = {key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()}
        self.coverage.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
        if schema_version >= 2:
            self.coverage['supplemental_addresses_total'] = 0
            self.coverage['excluded_by_provider_reason'] = {provider:
                dict.fromkeys(sorted(EXCLUSION_REASONS), 0) for provider in sorted(PROVIDERS)}
        if schema_version == 3:
            self.coverage['rack_memberships_total'] = 0
            self.coverage['rack_memberships_by_relation'] = dict.fromkeys(sorted(RACK_RELATIONS), 0)
            self.coverage['known_non_address_guard_inputs_by_kind'] = dict.fromkeys(sorted(NON_ADDRESS_KINDS), 0)
        self.bytes = FIXED_BYTES
        self.halted = False
        self.source_truncated = False
        self.groups: dict[str, dict[str, Any]] = {}
        self.memberships: list[dict[str, Any]] = []
        self.gaps: dict[tuple[str, str], int] = defaultdict(int)
        self.group_rungs: dict[str, set[str]] = defaultdict(set)
        self.group_providers: dict[str, set[str]] = defaultdict(set)
        self.group_flags: dict[str, set[str]] = defaultdict(set)
        self.group_writers: dict[str, set[str]] = defaultdict(set)
        self.addresses: dict[str, dict[str, Any]] = {}
        self.relationship_ids: set[str] = set()
        self.supplemental_addresses: list[dict[str, Any]] = []
        self.use_addresses: dict[str, str] = {}
        self.operands: dict[str, dict[str, Any]] = {}
        self.instructions: dict[str, dict[str, Any]] = {}
        self.rack_uses: dict[tuple[str, str], tuple[dict[str, Any], dict[str, str]]] = {}

    def visit(self, link: bool = False) -> bool:
        if self.halted:
            return False
        if self.coverage['visited_rows'] + self.coverage['visited_links'] >= MAX_ASSEMBLY_VISITS:
            self.halted = True
            return False
        self.coverage['visited_links' if link else 'visited_rows'] += 1
        return True

    def rows(self, provider: str, field: str) -> Iterator[dict[str, Any]]:
        for row in (self.data.get(provider) or {}).get(field, ()):
            if not self.visit():
                break
            yield row

    def links(self, row: dict[str, Any], field: str) -> Iterator[str]:
        for identifier in row.get(field, ()):
            if not self.visit(link=True):
                break
            yield identifier

    def gap(self, provider: str, reason: str, count: int = 1, *, exclude: bool = False) -> None:
        if count:
            self.gaps[provider, reason] += count
        if exclude:
            self.coverage['excluded_total'] += count
            self.coverage['excluded_by_provider'][provider] += count
            self.coverage['excluded_by_reason'][reason] += count
            if self.schema_version >= 2:
                self.coverage['excluded_by_provider_reason'][provider][reason] += count

    def identity(self, provider: str, target: Any, suffix: Any) -> dict[str, str]:
        """Accept a static spelling and shared snapshot from replayed evidence."""
        snapshot = self.data.get('relationships', {}).get('snapshot', {}).get('id')
        provider_snapshot = self.data.get(provider, {}).get('snapshot', {}).get('id')
        if (type(snapshot) is not str or not snapshot or len(snapshot) > MAX_ADDRESS_LENGTH
                or provider_snapshot != snapshot or type(provider_snapshot) is not str
                or type(target) is not str or not target or len(target) > MAX_ADDRESS_LENGTH
                or type(suffix) is not str or len(suffix) > MAX_ADDRESS_LENGTH
                or suffix and suffix[0] not in '.['
                or _ADDRESS.fullmatch('R' + suffix) is None):
            _invalid()
        identifier = _identifier('relationship_address_', snapshot, target, suffix)
        result = {'id': identifier, 'target_id': target, 'suffix': suffix}
        prior = self.addresses.get(identifier)
        if prior is not None and any(prior.get(key) != value for key, value in result.items()):
            _invalid()
        return result

    def sfc_identity(self, row: dict[str, Any]) -> dict[str, str]:
        result = self.identity('sfc_context', row['target_id'], row['suffix'])
        snapshot = self.data['sfc_context']['snapshot']['id']
        if (row['id'] != _identifier('sfc_context_address_', snapshot, result['target_id'], result['suffix'])
                or row['relationship_address_id'] != (result['id'] if result['id'] in self.relationship_ids else None)):
            _invalid()
        return result

    def file_identity(self, row: dict[str, Any]) -> dict[str, str]:
        binding = row['binding']
        if type(binding) is not dict or binding.get('status') != 'root_bound':
            _invalid()
        result = self.identity('file_operations', binding['target_id'], binding['suffix'])
        if row['address_id'] != result['id']:
            _invalid()
        return result

    def quality(self, row: dict[str, Any], key: str) -> set[str]:
        result: set[str] = set()
        value = row.get(key)
        flag = {'namespace_gap': 'namespace_gap', 'opaque': 'opaque_guard',
            'binding_gaps': 'binding_gap', 'stateful': 'stateful_guard',
            'unavailable': 'binding_gap'}.get(value)
        if flag:
            result.add(flag)
        if row.get('has_branch') or row.get('branch_depth', 0):
            result.add('branched')
        return result

    def emit(self, address: str | None, provider: str, relation: str, source_id: str,
            instruction_id: str | None = None, rung_id: str | None = None,
            related_address: str | None = None, flags: set[str] | None = None,
            *, writer: bool = False, supplemental: dict[str, str] | None = None,
            rack_source_use_ids: tuple[str, ...] = ()) -> None:
        if self.halted:
            return
        new_address = address not in self.addresses
        if ((new_address and supplemental is None)
                or related_address is not None and related_address not in self.addresses):
            self.gap(provider, 'missing_address', exclude=True)
            return
        flags = set(flags or ())
        operand = self.operands.get(source_id, {})
        instruction_id = instruction_id or operand.get('instruction_id')
        rung_id = rung_id or operand.get('rung_id') or self.instructions.get(instruction_id, {}).get('rung_id')
        if relation in {'unknown', 'file_unknown'} or operand.get('role') == 'unknown':
            flags.add('unknown_role')
        if self.instructions.get(instruction_id, {}).get('opcode', '').upper() == 'MSG':
            flags.add('communication_control_only')
        row = {'id': f'assembly_membership_{len(self.memberships)}', 'group_id': address,
            'provider': provider, 'relation': relation, 'source_id': source_id,
            'instruction_id': instruction_id, 'rung_id': rung_id,
            'related_address_id': related_address, 'context_flags': sorted(flags)}
        if self.schema_version == 3:
            row['rack_source_use_ids'] = sorted(set(rack_source_use_ids))
            if len(row['rack_source_use_ids']) > 2 or rack_source_use_ids and relation not in RACK_RELATIONS:
                _invalid()
        # Reserve the exact row and membership-ID list entry before appending.
        # A rung ID is retained once per group, so charge it on first insertion.
        # Sixteen bytes exceed the array commas/new entries; the fixed group
        # reserve already covers every closed provider/flag list and field name.
        size = _encoded(row) + _encoded(row['id']) + 16
        if rung_id is not None and rung_id not in self.group_rungs[address]:
            size += _encoded(rung_id)
        new_group = address not in self.groups
        if new_group:
            size += GROUP_BYTES + 2 * _encoded(address)
        if new_address:
            # Reserve both the retained record and indexed ID before either the
            # supplemental identity or its first membership is appended.
            size += _encoded(supplemental) + _encoded(address) + 16
        if (len(self.memberships) >= MAX_ASSEMBLY_MEMBERSHIPS
                or new_group and len(self.groups) >= MAX_ASSEMBLY_GROUPS
                or self.bytes + size > MAX_ENGINEERING_ASSEMBLIES_BYTES):
            self.halted = True
            return
        self.bytes += size
        if new_address:
            self.addresses[address] = supplemental
            self.supplemental_addresses.append(supplemental)
        if new_group:
            self.groups[address] = {'id': address, 'address_id': address,
                'membership_ids': [], 'rung_ids': [], 'providers': [],
                'boundary_flags': [], 'scan_status': 'complete'}
        self.groups[address]['membership_ids'].append(row['id'])
        if rung_id is not None:
            self.group_rungs[address].add(rung_id)
        self.group_providers[address].add(provider)
        self.group_flags[address].update(flags)
        if writer and instruction_id is not None:
            self.group_writers[address].add(instruction_id)
        self.memberships.append(row)
        if rack_source_use_ids:
            self.coverage['rack_memberships_total'] += 1
            self.coverage['rack_memberships_by_relation'][relation] += 1
        self.coverage['memberships_by_provider'][provider] += 1
        self.coverage['memberships_by_relation'][relation] += 1
        for flag in flags:
            self.coverage['memberships_by_flag'][flag] += 1

    def qualified_uses(self, provider: str, row: dict[str, Any], address: str,
            relation: str | None = None, flags: set[str] | None = None,
            related_address: str | None = None) -> None:
        for role in _ROLES:
            for identifier in self.links(row, f'{role}_operand_ids'):
                self.emit(address, provider, relation or role, identifier, flags=flags,
                    related_address=related_address, writer=role in {'write', 'read_write'})
        for identifier in self.links(row, 'expression_use_ids'):
            self.emit(address, provider, relation or 'expression_read', identifier,
                flags=flags, related_address=related_address)

    def index(self) -> None:
        for row in self.rows('access', 'instructions'):
            self.instructions[row['id']] = row
        for field in ('operands', 'expression_uses'):
            for row in self.rows('access', field):
                self.operands[row['id']] = row
        for row in self.rows('relationships', 'addresses'):
            self.addresses[row['id']] = row
            if self.schema_version >= 2:
                self.relationship_ids.add(row['id'])
            for field in (*(f'{role}_operand_ids' for role in _ROLES), 'expression_use_ids'):
                for identifier in self.links(row, field):
                    prior = self.use_addresses.get(identifier)
                    if prior is not None and prior != row['id']:
                        _invalid()
                    self.use_addresses[identifier] = row['id']

    def index_rack(self) -> None:
        """Join occurrence proofs, never substitute every use of a rack root.

        The review pipeline replays the rack provider against its source. These
        checks additionally bind its proof IDs to the exact canonical consumer
        rows. Every index is populated through the shared visit budget.
        """
        provider = 'rack_backing_context'
        source = self.data[provider]
        for key, expected in RACK_CONSTANTS.items():
            if type(source.get(key)) is not type(expected) or source[key] != expected:
                _invalid()
        snapshot = self.data['relationships']['snapshot']
        for name in (provider, 'access', 'signal_context', 'sfc_context'):
            if self.data[name].get('snapshot') != snapshot:
                _invalid()
        reads, outputs, references = {}, {}, {}
        for row in self.rows('signal_context', 'condition_reads'):
            if row['id'] in reads:
                _invalid()
            reads[row['id']] = row
        for row in self.rows('signal_context', 'outputs'):
            identifier = row['target_operand_id']
            if identifier in outputs:
                _invalid()
            outputs[identifier] = row
        for row in self.rows('sfc_context', 'references'):
            identifier = row['condition_reference_id']
            if identifier in references:
                _invalid()
            references[identifier] = row
        roots, addresses = {}, {}
        for row in self.rows(provider, 'roots'):
            if row['id'] in roots or row['id'] != _rack_id('root', row['candidate_id']):
                _invalid()
            roots[row['id']] = row
        for row in self.rows(provider, 'addresses'):
            if row['id'] in addresses or row['id'] != _rack_id('address', row['candidate_id'], row['suffix']):
                _invalid()
            root = roots.get(row['root_id'])
            if root is None or root['candidate_id'] != row['candidate_id']:
                _invalid()
            identity = None
            if row['disposition'] == 'associated':
                if (root['disposition'] != 'associated' or type(root['slot']) is not str
                        or not root['slot'].isascii() or not root['slot'].isdigit()
                        or root['backing_suffix'] != f".Slot[{root['slot']}]"
                        or row['direction'] != root['direction']
                        or row['backing_tag_id'] != root['backing_tag_id']
                        or row['backing_suffix'] != root['backing_suffix'] + row['suffix']):
                    _invalid()
                identity = self.identity(provider, row['backing_tag_id'], row['backing_suffix'])
            addresses[row['id']] = (row, identity)
        seen: set[str] = set()
        for row in self.rows(provider, 'uses'):
            kind, identifier = row['kind'], row['source_id']
            if (kind not in {'rll', 'sfc'} or row['id'] in seen
                    or row['id'] != _rack_id('use', kind, identifier)):
                _invalid()
            seen.add(row['id'])
            if row['disposition'] != 'associated':
                continue
            address, identity = addresses.get(row['address_id'], ({}, None))
            if identity is None or row['candidate_id'] != address['candidate_id']:
                _invalid()
            if kind == 'rll':
                operand = self.operands.get(identifier, {})
                if (operand.get('binding_status') != 'unresolved'
                        or operand.get('binding_reason') != 'colon_root_not_declared'
                        or operand.get('role') != row['role'] or row['role'] not in {'read', 'write', 'read_write'}
                        or operand.get('suffix') != address['suffix']):
                    _invalid()
                read, output = reads.get(identifier), outputs.get(identifier)
                predicate = read['condition_node_id'] if read is not None and read['kind'] != 'ons_storage' else None
                if (row['predicate_node_id'] != predicate
                        or row['output_id'] != (output['condition_output_id'] if output is not None else None)):
                    _invalid()
                for consumer in (read, output):
                    if consumer is not None and (consumer['rung_id'] != operand['rung_id']
                            or consumer['instruction_id'] != operand['instruction_id']):
                        _invalid()
                if (read is not None and read['status'] not in {'unbound', 'identity_gap'}
                        or output is not None and output['target_status'] not in {'unbound', 'identity_gap'}):
                    _invalid()
                prior = self.use_addresses.get(identifier)
                if prior is not None:
                    _invalid()
            else:
                reference = references.get(identifier, {})
                if (reference.get('status') != 'binding_gap' or reference.get('binding_status') != 'unresolved'
                        or row['role'] != 'read' or row['predicate_node_id'] is not None or row['output_id'] is not None):
                    _invalid()
            self.rack_uses[kind, identifier] = (row, identity)

    def rack_identity(self, kind: str, identifier: str) -> tuple[dict[str, str] | None, tuple[str, ...]]:
        proof = self.rack_uses.get((kind, identifier))
        return (proof[1], (proof[0]['id'],)) if proof is not None else (None, ())

    def signal(self) -> None:
        provider = 'signal_context'
        reads = {}
        read_identities = {}
        for row in self.rows(provider, 'condition_reads'):
            reads[row['id']] = row
            supplemental, proof = self.rack_identity('rll', row['id']) if (
                self.schema_version == 3 and row['kind'] != 'ons_storage') else (None, ())
            if row['status'] == 'exact_address':
                read_identities[row['id']] = (row['source_address_id'], ())
                self.emit(row['source_address_id'], provider, 'boolean_condition', row['id'],
                    row['instruction_id'], row['rung_id'],
                    flags={'stateful_guard'} if row['kind'] == 'ons_storage' else set())
            elif supplemental is not None:
                read_identities[row['id']] = (supplemental['id'], proof)
                self.emit(supplemental['id'], provider, 'boolean_condition', row['id'],
                    row['instruction_id'], row['rung_id'], supplemental=supplemental,
                    rack_source_use_ids=proof)
            elif row['status'] not in {'literal', 'system_flag'}:
                self.gap(provider, 'binding_or_namespace', exclude=True)
        for row in self.rows(provider, 'addresses'):
            self.qualified_uses(provider, row, row['id'])
            rejected = len(row.get('rejected_operand_ids', ())) + len(row.get('rejected_expression_use_ids', ()))
            self.gap(provider, 'unqualified_membership', rejected, exclude=True)
        if self.schema_version == 3:
            for (kind, source_id), (use, identity) in self.rack_uses.items():
                if not self.visit():
                    break
                if kind == 'rll':
                    self.emit(identity['id'], provider, use['role'], source_id,
                        writer=use['role'] in {'write', 'read_write'}, supplemental=identity,
                        rack_source_use_ids=(use['id'],))
        for row in self.rows(provider, 'outputs'):
            supplemental, proof = self.rack_identity('rll', row['target_operand_id']) if self.schema_version == 3 else (None, ())
            target = supplemental['id'] if supplemental is not None else row['target_address_id']
            if (row['target_status'] != 'exact_address' and supplemental is None
                    or row['guard_quality'] == 'namespace_gap' or row['has_namespace_gap']):
                self.gap(provider, 'binding_or_namespace', exclude=True)
                continue
            flags = self.quality(row, 'guard_quality')
            dependency = row.get('guard_dependencies', {})
            candidate = row.get('candidate_context', {})
            if (dependency.get('traversal_status') == 'truncated'
                    or candidate.get('scan_status') == 'truncated'):
                flags.add('source_truncated')
                self.source_truncated = True
                self.gap(provider, 'source_truncated')
            flags.update(_CATEGORIES[value] for value in candidate.get('target_categories', ()))
            self.emit(target, provider, 'boolean_output', row['id'],
                row['instruction_id'], row['rung_id'], flags=flags, writer=True,
                supplemental=supplemental, rack_source_use_ids=proof)
            categories = {}
            for match in candidate.get('conditions', ()):
                if not self.visit(link=True):
                    break
                categories[match['condition_read_id']] = {_CATEGORIES[value] for value in match['categories']}
            for identifier in self.links(dependency, 'condition_read_ids'):
                read = reads.get(identifier)
                if self.schema_version == 3 and read is not None and read['status'] in NON_ADDRESS_KINDS:
                    self.coverage['known_non_address_guard_inputs_by_kind'][read['status']] += 1
                    continue
                resolved = read_identities.get(identifier)
                if read is None or resolved is None:
                    self.gap(provider, 'binding_or_namespace', exclude=True)
                    continue
                self.emit(target, provider, 'guard_condition', identifier,
                    row['instruction_id'], row['rung_id'], resolved[0],
                    flags | categories.get(identifier, set()), rack_source_use_ids=proof + resolved[1])

    def pid(self) -> None:
        provider = 'pid_connections'
        occurrences = {}
        for row in self.rows(provider, 'occurrences'):
            flags = set()
            if row['control_status'] != 'linked':
                flags.add('pid_control_gap')
            if row['master']['status'] not in {'literal', 'single_occurrence'} or row['master']['self_reference']:
                flags.add('pid_master_gap')
            occurrences[row['id']] = (row, flags)
        for row in self.rows(provider, 'slots'):
            source, flags = occurrences.get(row['instruction_id'], ({}, set()))
            if row['status'] == 'exact_address':
                self.emit(row['address_id'], provider, 'pid_slot', row['id'],
                    row['instruction_id'], source.get('rung_id'), flags=flags)
            elif row['status'] != 'literal':
                self.gap(provider, 'binding_or_namespace', exclude=True)
        for row in self.rows(provider, 'addresses'):
            if row['kind'] not in {'direct_member', 'whole_owner', 'slot_address'}:
                self.gap(provider, 'unsupported_member', exclude=True)
                continue
            self.qualified_uses(provider, row, row['id'], 'pid_address_use')
            rejected = len(row.get('namespace_gap_operand_ids', ())) + len(row.get('namespace_gap_expression_use_ids', ()))
            self.gap(provider, 'unqualified_membership', rejected, exclude=True)

    def calculation(self) -> None:
        provider = 'calculation_paths'
        for row in self.rows(provider, 'occurrences'):
            if row['status'] != 'eligible':
                self.gap(provider, 'ineligible_occurrence', exclude=True)
                continue
            flags = self.quality(row, 'condition_quality')
            self.emit(row['destination_address_id'], provider, 'calculation_output', row['id'],
                row['id'], row['rung_id'], flags=flags, writer=True)
            for field in ('input_operand_ids', 'expression_use_ids'):
                for identifier in self.links(row, field):
                    operand = self.operands.get(identifier, {})
                    if operand.get('binding_status') in {'literal', 'parsed_expression'}:
                        continue
                    self.emit(self.use_addresses.get(identifier), provider, 'calculation_input', identifier,
                        row['id'], row['rung_id'], flags=flags)

    def stateful(self) -> None:
        provider = 'stateful_objects'
        objects = {row['id']: row for row in self.rows(provider, 'objects')}
        for row in self.rows(provider, 'occurrences'):
            if row['target_status'] != 'exact_address' or row['context_status'] == 'namespace_gap':
                self.gap(provider, 'binding_or_namespace', exclude=True)
                continue
            flags = self.quality(row, 'context_status') | {'stateful_guard'}
            obj = objects.get(row['control_address_id'], {})
            if (obj.get('type_conflict') or obj.get('declaration_kind') == 'unresolved'
                    or obj.get('bounds_status') in {'unresolved', 'static_out_of_bounds'}):
                flags.add('stateful_type_gap')
            self.emit(row['control_address_id'], provider, 'stateful_control', row['id'],
                row['id'], row['rung_id'], flags=flags, writer=True)
        for row in self.rows(provider, 'address_uses'):
            flags = {'stateful_guard'}
            obj = objects.get(row['object_id'], {})
            if (obj.get('type_conflict') or obj.get('declaration_kind') == 'unresolved'
                    or obj.get('bounds_status') in {'unresolved', 'static_out_of_bounds'}):
                flags.add('stateful_type_gap')
            if row['member_status'] == 'unknown':
                self.gap(provider, 'unsupported_member', exclude=True)
                continue
            self.qualified_uses(provider, row, row['address_id'], 'stateful_member', flags, row['object_id'])
            rejected = len(row.get('rejected_operand_ids', ())) + len(row.get('rejected_expression_use_ids', ()))
            self.gap(provider, 'unqualified_membership', rejected, exclude=True)

    def sfc(self) -> None:
        provider = 'sfc_context'
        addresses = {}
        for row in self.rows(provider, 'addresses'):
            addresses[row['id']] = row
            address = row['relationship_address_id']
            if self.schema_version >= 2:
                self.sfc_identity(row)
            if address is not None:
                self.qualified_uses(provider, row, address)
            rejected = sum(len(value) for value in row.get('unqualified_operand_ids_by_role', {}).values())
            rejected += len(row.get('unqualified_expression_use_ids', ()))
            self.gap(provider, 'unqualified_membership', rejected, exclude=True)
        for row in self.rows(provider, 'references'):
            if row['status'] != 'exact_address':
                supplemental, proof = self.rack_identity('sfc', row['condition_reference_id']) if self.schema_version == 3 else (None, ())
                if supplemental is not None:
                    self.emit(supplemental['id'], provider, 'sfc_reference', row['id'],
                        supplemental=supplemental, rack_source_use_ids=proof)
                    continue
                self.gap(provider, 'binding_or_namespace', exclude=True)
                continue
            address_row = addresses.get(row['address_id'], {})
            if self.schema_version >= 2:
                if row['binding_status'] != 'root_bound':
                    _invalid()
                supplemental = self.sfc_identity(address_row)
                self.emit(supplemental['id'], provider, 'sfc_reference', row['id'], supplemental=supplemental)
            else:
                self.emit(address_row.get('relationship_address_id'), provider, 'sfc_reference', row['id'])

    def file(self) -> None:
        provider = 'file_operations'
        occurrences = {row['id']: row for row in self.rows(provider, 'occurrences')}
        for row in self.rows(provider, 'slots'):
            source = occurrences.get(row['instruction_id'], {})
            if row['status'] != 'exact_address' or source.get('qualification') != 'qualified':
                if row['status'] not in {'literal', 'non_data', 'parsed_expression'}:
                    reason = 'dynamic_address' if row['status'] == 'symbolic_address' else 'binding_or_namespace'
                    self.gap(provider, reason, exclude=True)
                continue
            supplemental = self.file_identity(row) if self.schema_version >= 2 else None
            flags = self.quality(source, 'context_status') | {'selector_or_array_span'}
            self.emit(row['address_id'], provider, f"file_{row['role']}", row['id'],
                row['instruction_id'], row['rung_id'], flags=flags,
                writer=row['role'] in {'write', 'read_write'}, supplemental=supplemental)
        for row in self.rows(provider, 'expression_nodes'):
            if row['kind'] != 'reference':
                continue
            if row['status'] == 'exact_address':
                source = occurrences.get(row['instruction_id'], {})
                if self.schema_version >= 2 and source.get('qualification') != 'qualified':
                    self.gap(provider, 'binding_or_namespace', exclude=True)
                    continue
                supplemental = self.file_identity(row) if self.schema_version >= 2 else None
                self.emit(row['address_id'], provider, 'file_read', row['id'],
                    row['instruction_id'], source.get('rung_id'),
                    flags=self.quality(source, 'context_status') | {'selector_or_array_span'},
                    supplemental=supplemental)
            else:
                self.gap(provider, 'dynamic_address' if row['status'] == 'symbolic_address'
                    else 'binding_or_namespace', exclude=True)

    def finish(self) -> dict[str, Any]:
        c = self.coverage
        truncated = self.halted or self.source_truncated
        for identifier, group in self.groups.items():
            flags = self.group_flags[identifier]
            if len(self.group_writers[identifier]) > 1:
                flags.add('competing_writers')
            if truncated:
                flags.add('source_truncated')
            group.update(rung_ids=sorted(self.group_rungs[identifier]),
                providers=sorted(self.group_providers[identifier]), boundary_flags=sorted(flags),
                scan_status='truncated' if truncated else 'complete')
            c['multirung_groups'] += int(len(group['rung_ids']) > 1)
            c['multiprovider_groups'] += int(len(group['providers']) > 1)
            c['groups_with_boundary_flags'] += int(bool(flags))
            for flag in flags:
                c['groups_by_flag'][flag] += 1
        c.update(groups_total=len(self.groups), memberships_total=len(self.memberships),
            source_gap_buckets=len(self.gaps), source_gap_counts=sum(self.gaps.values()), retained_bytes=self.bytes)
        constants = {1: ASSEMBLY_CONSTANTS, 2: ASSEMBLY_CONSTANTS_V2, 3: ASSEMBLY_CONSTANTS_V3}[self.schema_version]
        if self.schema_version >= 2:
            c['supplemental_addresses_total'] = len(self.supplemental_addresses)
        result = {**constants, 'status': 'partial' if self.gaps or truncated
            or c['groups_with_boundary_flags'] else 'complete',
            'scan_status': 'truncated' if truncated else 'complete',
            'groups': list(self.groups.values()), 'memberships': self.memberships,
            'source_gaps': [{'provider': provider, 'reason': reason, 'count': count}
                for (provider, reason), count in sorted(self.gaps.items())], 'coverage': c,
            'budget': {'max_bytes': MAX_ENGINEERING_ASSEMBLIES_BYTES,
                'max_memberships': MAX_ASSEMBLY_MEMBERSHIPS, 'max_groups': MAX_ASSEMBLY_GROUPS,
                'max_visits': MAX_ASSEMBLY_VISITS, 'retained_bytes': self.bytes,
                'visited_rows': c['visited_rows'], 'visited_links': c['visited_links']}}
        if self.schema_version >= 2:
            result['supplemental_addresses'] = self.supplemental_addresses
        if _encoded(result) > min(self.bytes, MAX_ENGINEERING_ASSEMBLIES_BYTES):
            _invalid()
        return result


def build_engineering_assemblies(data: dict[str, Any], *, schema_version: int = 1) -> dict[str, Any]:
    """Index qualified canonical evidence without changing any provider payload."""
    try:
        if type(schema_version) is not int or schema_version not in {1, 2, 3}:
            _invalid()
        builder = _Builder(data, schema_version)
        for provider in sorted(PROVIDERS):
            source = data.get(provider)
            status = source.get('status', 'partial') if source is not None else 'missing'
            builder.coverage['providers_by_status'][status] += 1
            if status != 'complete':
                builder.gap(provider, 'provider_missing' if status == 'missing' else 'provider_partial')
        builder.index()
        if schema_version == 3:
            builder.index_rack()
        builder.signal()
        builder.pid()
        builder.calculation()
        builder.stateful()
        builder.sfc()
        builder.file()
        # MSG's control structure is inspectable, but its transport/remote data
        # semantics are not implemented by these providers. Do not imply otherwise.
        for row in builder.instructions.values():
            if not builder.visit():
                break
            if row.get('opcode', '').upper() == 'MSG':
                builder.gap('signal_context', 'communication_semantics_unmodeled')
        return builder.finish()
    except EngineeringAssembliesError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError, RecursionError):
        _invalid()
