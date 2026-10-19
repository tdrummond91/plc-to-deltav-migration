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
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.coverage = {key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()}
        self.coverage.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
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
        self.use_addresses: dict[str, str] = {}
        self.operands: dict[str, dict[str, Any]] = {}
        self.instructions: dict[str, dict[str, Any]] = {}

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
            *, writer: bool = False) -> None:
        if self.halted:
            return
        if address not in self.addresses or related_address is not None and related_address not in self.addresses:
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
        if (len(self.memberships) >= MAX_ASSEMBLY_MEMBERSHIPS
                or new_group and len(self.groups) >= MAX_ASSEMBLY_GROUPS
                or self.bytes + size > MAX_ENGINEERING_ASSEMBLIES_BYTES):
            self.halted = True
            return
        self.bytes += size
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
            for field in (*(f'{role}_operand_ids' for role in _ROLES), 'expression_use_ids'):
                for identifier in self.links(row, field):
                    prior = self.use_addresses.get(identifier)
                    if prior is not None and prior != row['id']:
                        _invalid()
                    self.use_addresses[identifier] = row['id']

    def signal(self) -> None:
        provider = 'signal_context'
        reads = {}
        for row in self.rows(provider, 'condition_reads'):
            reads[row['id']] = row
            if row['status'] == 'exact_address':
                self.emit(row['source_address_id'], provider, 'boolean_condition', row['id'],
                    row['instruction_id'], row['rung_id'],
                    flags={'stateful_guard'} if row['kind'] == 'ons_storage' else set())
            elif row['status'] not in {'literal', 'system_flag'}:
                self.gap(provider, 'binding_or_namespace', exclude=True)
        for row in self.rows(provider, 'addresses'):
            self.qualified_uses(provider, row, row['id'])
            rejected = len(row.get('rejected_operand_ids', ())) + len(row.get('rejected_expression_use_ids', ()))
            self.gap(provider, 'unqualified_membership', rejected, exclude=True)
        for row in self.rows(provider, 'outputs'):
            if row['target_status'] != 'exact_address' or row['guard_quality'] == 'namespace_gap' or row['has_namespace_gap']:
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
            self.emit(row['target_address_id'], provider, 'boolean_output', row['id'],
                row['instruction_id'], row['rung_id'], flags=flags, writer=True)
            categories = {}
            for match in candidate.get('conditions', ()):
                if not self.visit(link=True):
                    break
                categories[match['condition_read_id']] = {_CATEGORIES[value] for value in match['categories']}
            for identifier in self.links(dependency, 'condition_read_ids'):
                read = reads.get(identifier)
                if read is None or read['status'] != 'exact_address':
                    self.gap(provider, 'binding_or_namespace', exclude=True)
                    continue
                self.emit(row['target_address_id'], provider, 'guard_condition', identifier,
                    row['instruction_id'], row['rung_id'], read['source_address_id'],
                    flags | categories.get(identifier, set()))

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
            if address is not None:
                self.qualified_uses(provider, row, address)
            rejected = sum(len(value) for value in row.get('unqualified_operand_ids_by_role', {}).values())
            rejected += len(row.get('unqualified_expression_use_ids', ()))
            self.gap(provider, 'unqualified_membership', rejected, exclude=True)
        for row in self.rows(provider, 'references'):
            if row['status'] != 'exact_address':
                self.gap(provider, 'binding_or_namespace', exclude=True)
                continue
            address = addresses.get(row['address_id'], {}).get('relationship_address_id')
            self.emit(address, provider, 'sfc_reference', row['id'])

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
            flags = self.quality(source, 'context_status') | {'selector_or_array_span'}
            self.emit(row['address_id'], provider, f"file_{row['role']}", row['id'],
                row['instruction_id'], row['rung_id'], flags=flags,
                writer=row['role'] in {'write', 'read_write'})
        for row in self.rows(provider, 'expression_nodes'):
            if row['kind'] != 'reference':
                continue
            if row['status'] == 'exact_address':
                source = occurrences.get(row['instruction_id'], {})
                self.emit(row['address_id'], provider, 'file_read', row['id'],
                    row['instruction_id'], source.get('rung_id'),
                    flags=self.quality(source, 'context_status') | {'selector_or_array_span'})
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
        result = {**ASSEMBLY_CONSTANTS, 'status': 'partial' if self.gaps or truncated
            or c['groups_with_boundary_flags'] else 'complete',
            'scan_status': 'truncated' if truncated else 'complete',
            'groups': list(self.groups.values()), 'memberships': self.memberships,
            'source_gaps': [{'provider': provider, 'reason': reason, 'count': count}
                for (provider, reason), count in sorted(self.gaps.items())], 'coverage': c,
            'budget': {'max_bytes': MAX_ENGINEERING_ASSEMBLIES_BYTES,
                'max_memberships': MAX_ASSEMBLY_MEMBERSHIPS, 'max_groups': MAX_ASSEMBLY_GROUPS,
                'max_visits': MAX_ASSEMBLY_VISITS, 'retained_bytes': self.bytes,
                'visited_rows': c['visited_rows'], 'visited_links': c['visited_links']}}
        if _encoded(result) > min(self.bytes, MAX_ENGINEERING_ASSEMBLIES_BYTES):
            _invalid()
        return result


def build_engineering_assemblies(data: dict[str, Any]) -> dict[str, Any]:
    """Index qualified canonical evidence without changing any provider payload."""
    try:
        builder = _Builder(data)
        for provider in sorted(PROVIDERS):
            source = data.get(provider)
            status = source.get('status', 'partial') if source is not None else 'missing'
            builder.coverage['providers_by_status'][status] += 1
            if status != 'complete':
                builder.gap(provider, 'provider_missing' if status == 'missing' else 'provider_partial')
        builder.index()
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
