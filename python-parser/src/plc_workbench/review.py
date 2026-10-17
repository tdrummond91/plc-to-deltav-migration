"""Private, snapshot-bound evidence for the offline engineering review report.

Patterns compare exact ordered syntax. Findings expose existing gaps; the
optional rung companion adds explicit, unreviewed structure and purpose
candidates without asserting execution, dependencies, or confirmed intent.
This module performs no filesystem, process, or network operations.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import fields, is_dataclass
import hashlib
import io
import json
from typing import Any

from .access import AccessResult, analyze_access
from .models import InventoryResult, SourceSnapshot
from .pid import PidResult, analyze_pid
from .pid_members import PidMemberResult, analyze_pid_members
from .pid_connections import PidConnectionResult, analyze_pid_connections
from .calculations import CalculationResult, analyze_calculations
from .calculation_paths import CalculationPathResult, analyze_calculation_paths
from .output_context import BooleanOutputContextResult, analyze_output_context
from .stateful_objects import StatefulObjectResult, analyze_stateful_objects
from .rung_analysis import RungAnalysisResult, analyze_rungs
from .relationships import RelationshipResult, analyze_relationships
from .conditions import ConditionResult, analyze_conditions
from .binding_context import BindingContextResult, analyze_binding_context
from .custom_instruction_context import CustomInstructionContextResult, analyze_custom_instruction_context
from .indexed_access import IndexedAccessResult, analyze_indexed_access
from .sfr_context import SfrContextResult, analyze_sfr_context
from .aoi_body_context import AoiBodyContextResult, analyze_aoi_body_context
from .references import ReferenceResult, analyze_references
from .sfc_structure import SfcStructureResult, analyze_sfc_structure
from .source import analyze_snapshot
from .tag_data import TagDataResult, analyze_tag_data

MAX_REVIEW_BYTES = 64 * 1024 * 1024
# Review3/4/5 combine the established evidence with bounded companion payloads.
# Historical review1/2 retain their original ceiling.
MAX_REVIEW_V3_BYTES = 128 * 1024 * 1024
# Review9 adds a separately bounded 32 MiB condition companion. Reserve that
# allowance alongside the established report; review1-8 keep their old limits.
MAX_REVIEW_V9_BYTES = 160 * 1024 * 1024
# Review10 changes transfer semantics without increasing the companion budget.
MAX_REVIEW_V10_BYTES = 160 * 1024 * 1024
MAX_REVIEW_V11_BYTES = 168 * 1024 * 1024
MAX_REVIEW_V12_BYTES = 184 * 1024 * 1024
MAX_REVIEW_V13_BYTES = 192 * 1024 * 1024
MAX_REVIEW_V14_BYTES = 200 * 1024 * 1024
MAX_REVIEW_V15_BYTES = 208 * 1024 * 1024
MAX_REVIEW_V16_BYTES = 216 * 1024 * 1024
MAX_REVIEW_V17_BYTES = 232 * 1024 * 1024
MAX_REVIEW_V18_BYTES = 248 * 1024 * 1024
MAX_REVIEW_FINDINGS = 500_000
MAX_REVIEW_PATTERNS = 100_000
_BOUND = frozenset({'root_bound', 'literal', 'non_data', 'system_flag'})


class ReviewError(ValueError):
    """A fixed-message error that never exposes private evidence or OS details."""


class ReviewSizeLimitError(ReviewError):
    """A report exceeded its versioned combined UTF-8 payload budget."""


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
    version = (data.get('schema_version'), data.get('report_version'))
    limit = (MAX_REVIEW_V18_BYTES if version == (18, 'engineering-review-18') else
             MAX_REVIEW_V17_BYTES if version == (17, 'engineering-review-17') else
             MAX_REVIEW_V16_BYTES if version == (16, 'engineering-review-16') else
             MAX_REVIEW_V15_BYTES if version == (15, 'engineering-review-15') else
             MAX_REVIEW_V14_BYTES if version == (14, 'engineering-review-14') else
             MAX_REVIEW_V13_BYTES if version == (13, 'engineering-review-13') else
             MAX_REVIEW_V12_BYTES if version == (12, 'engineering-review-12') else
             MAX_REVIEW_V11_BYTES if version == (11, 'engineering-review-11') else
             MAX_REVIEW_V10_BYTES if version == (10, 'engineering-review-10') else
             MAX_REVIEW_V9_BYTES if version == (9, 'engineering-review-9') else
             MAX_REVIEW_V3_BYTES if version
             in ((3, 'engineering-review-3'), (4, 'engineering-review-4'),
                 (5, 'engineering-review-5'), (6, 'engineering-review-6'),
                 (7, 'engineering-review-7'), (8, 'engineering-review-8')) else MAX_REVIEW_BYTES)
    total = 0
    for chunk in json.JSONEncoder(ensure_ascii=False, separators=(',', ':'),
                                  allow_nan=False).iterencode(data):
        total += len(chunk.encode('utf-8'))
        if total > limit:
            raise ReviewSizeLimitError('Engineering review exceeds the report size limit.')
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
                      sfc_structure: SfcStructureResult,
                      *, access: AccessResult | None = None,
                      tag_data: TagDataResult | None = None,
                      pid: PidResult | None = None,
                      pid_members: PidMemberResult | None = None,
                      calculations: CalculationResult | None = None,
                      rung_analysis: RungAnalysisResult | None = None,
                      relationships: RelationshipResult | None = None,
                      conditions: ConditionResult | None = None,
                      binding_context: BindingContextResult | None = None,
                      custom_instruction_context: CustomInstructionContextResult | None = None,
                      indexed_access: IndexedAccessResult | None = None,
                      sfr_context: SfrContextResult | None = None,
                      aoi_body_context: AoiBodyContextResult | None = None,
                      pid_connections: PidConnectionResult | None = None,
                      calculation_paths: CalculationPathResult | None = None,
                      output_context: BooleanOutputContextResult | None = None,
                      stateful_objects: StatefulObjectResult | None = None) -> dict[str, Any]:
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
        if tag_data is not None and access is None:
            _fail()
        if pid is not None and (tag_data is None or access is None):
            _fail()
        if pid_members is not None and (pid is None or tag_data is None or access is None):
            _fail()
        if calculations is not None and (pid_members is None or pid is None or tag_data is None or access is None):
            _fail()
        if rung_analysis is not None and (calculations is None or pid_members is None or pid is None
                                         or tag_data is None or access is None):
            _fail()
        if relationships is not None:
            for companion, expected_type, version in (
                    (relationships, RelationshipResult, 1), (rung_analysis, RungAnalysisResult, 1),
                    (access, AccessResult, 4), (calculations, CalculationResult, 2)):
                if (type(companion) is not expected_type or type(companion.schema_version) is not int
                        or companion.schema_version != version):
                    _fail()
        if conditions is not None:
            if (type(conditions) is not ConditionResult or type(conditions.schema_version) is not int
                    or conditions.schema_version not in (1, 2, 3) or type(relationships) is not RelationshipResult):
                _fail()
        if binding_context is not None:
            if (type(binding_context) is not BindingContextResult or type(binding_context.schema_version) is not int
                    or binding_context.schema_version != 1 or type(conditions) is not ConditionResult
                    or conditions.schema_version not in (2, 3)):
                _fail()
        if custom_instruction_context is not None or indexed_access is not None:
            if (type(custom_instruction_context) is not CustomInstructionContextResult
                    or type(indexed_access) is not IndexedAccessResult or binding_context is None):
                _fail()
        if sfr_context is not None or (conditions is not None and conditions.schema_version == 3):
            if (type(sfr_context) is not SfrContextResult or custom_instruction_context is None
                    or indexed_access is None or conditions is None or conditions.schema_version != 3):
                _fail()
        if aoi_body_context is not None or (sfr_context is not None and sfr_context.schema_version == 2):
            if (type(aoi_body_context) is not AoiBodyContextResult or sfr_context is None
                    or sfr_context.schema_version != 2):
                _fail()
        if pid_connections is not None and (aoi_body_context is None or pid_members is None):
            _fail()
        if calculation_paths is not None and pid_connections is None:
            _fail()
        if output_context is not None and calculation_paths is None:
            _fail()
        if stateful_objects is not None and (output_context is None or tag_data is None):
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
        canonical_calculations = None
        if calculations is not None:
            # Replay the captured grammar before using its leaves for access4.
            # Review6 still accepts the frozen calculation1/access2 or 3 paths.
            if type(calculations) is not CalculationResult:
                _fail()
            canonical_calculations = analyze_calculations(
                snapshot, canonical_inventory, canonical_references,
                schema_version=calculations.schema_version)
            if not _strict_equal(canonical_calculations, calculations):
                _fail()
        canonical_access = None
        if access is not None:
            # The nested version freezes the operand catalogue and binding
            # overlay. Older evidence must not acquire roles during review.
            if type(access) is not AccessResult:
                _fail()
            access_inputs = ({'snapshot': snapshot, 'calculations': canonical_calculations}
                             if access.schema_version == 4 else {})
            canonical_access = analyze_access(canonical_inventory, canonical_references,
                                              schema_version=access.schema_version, **access_inputs)
            if not _strict_equal(canonical_access, access):
                _fail()
        canonical_tag_data = None
        if tag_data is not None:
            canonical_tag_data = analyze_tag_data(snapshot, canonical_inventory)
            if not _strict_equal(canonical_tag_data, tag_data):
                _fail()
        canonical_pid = None
        if pid is not None:
            canonical_pid = analyze_pid(snapshot, canonical_inventory, canonical_references, canonical_tag_data)
            if not _strict_equal(canonical_pid, pid):
                _fail()
        canonical_pid_members = None
        if pid_members is not None:
            canonical_pid_members = analyze_pid_members(
                snapshot, canonical_inventory, canonical_references, canonical_tag_data, canonical_pid)
            if not _strict_equal(canonical_pid_members, pid_members):
                _fail()
        canonical_rungs = None
        if rung_analysis is not None:
            if type(rung_analysis) is not RungAnalysisResult:
                _fail()
            canonical_rungs = analyze_rungs(snapshot, canonical_inventory, canonical_references,
                                           canonical_access, canonical_calculations)
            if not _strict_equal(canonical_rungs, rung_analysis):
                _fail()
        canonical_relationships = None
        if relationships is not None:
            canonical_relationships = analyze_relationships(
                snapshot, canonical_inventory, canonical_references, canonical_access,
                canonical_calculations, canonical_rungs)
            if not _strict_equal(canonical_relationships, relationships):
                _fail()
        canonical_conditions = None
        if conditions is not None:
            canonical_conditions = analyze_conditions(
                snapshot, canonical_inventory, canonical_references, canonical_access,
                canonical_calculations, canonical_rungs, canonical_relationships,
                schema_version=conditions.schema_version)
            if not _strict_equal(canonical_conditions, conditions):
                _fail()
        canonical_binding_context = None
        if binding_context is not None:
            canonical_binding_context = analyze_binding_context(
                snapshot, canonical_inventory, canonical_references, canonical_access,
                canonical_calculations, canonical_rungs, canonical_relationships, canonical_conditions)
            if not _strict_equal(canonical_binding_context, binding_context):
                _fail()
        canonical_custom_context = canonical_indexed_access = None
        if custom_instruction_context is not None:
            companion_inputs = (snapshot, canonical_inventory, canonical_references, canonical_access,
                                canonical_calculations, canonical_rungs, canonical_relationships,
                                canonical_conditions, canonical_binding_context)
            canonical_custom_context = analyze_custom_instruction_context(*companion_inputs)
            canonical_indexed_access = analyze_indexed_access(*companion_inputs)
            if (not _strict_equal(canonical_custom_context, custom_instruction_context)
                    or not _strict_equal(canonical_indexed_access, indexed_access)):
                _fail()
        canonical_sfr_context = None
        if sfr_context is not None:
            canonical_sfr_context = analyze_sfr_context(
                snapshot, canonical_inventory, canonical_references, canonical_access,
                canonical_calculations, canonical_sfc, schema_version=sfr_context.schema_version)
            if not _strict_equal(canonical_sfr_context, sfr_context):
                _fail()
        canonical_aoi_body = None
        if aoi_body_context is not None:
            canonical_aoi_body = analyze_aoi_body_context(*companion_inputs, canonical_custom_context)
            if not _strict_equal(canonical_aoi_body, aoi_body_context):
                _fail()
        canonical_pid_connections = None
        if pid_connections is not None:
            canonical_pid_connections = analyze_pid_connections(
                snapshot, canonical_inventory, canonical_references, canonical_access,
                canonical_calculations, canonical_rungs, canonical_relationships,
                canonical_conditions, canonical_tag_data, canonical_pid, canonical_pid_members)
            if not _strict_equal(canonical_pid_connections, pid_connections):
                _fail()
        canonical_calculation_paths = None
        if calculation_paths is not None:
            canonical_calculation_paths = analyze_calculation_paths(
                snapshot, canonical_inventory, canonical_references, canonical_access,
                canonical_calculations, canonical_rungs, canonical_relationships, canonical_conditions)
            if not _strict_equal(canonical_calculation_paths, calculation_paths):
                _fail()
        canonical_output_context = None
        if output_context is not None:
            canonical_output_context = analyze_output_context(
                snapshot, canonical_inventory, canonical_references, canonical_access,
                canonical_calculations, canonical_rungs, canonical_relationships, canonical_conditions)
            if not _strict_equal(canonical_output_context, output_context):
                _fail()
        canonical_stateful_objects = None
        if stateful_objects is not None:
            canonical_stateful_objects = analyze_stateful_objects(
                snapshot, canonical_inventory, canonical_references, canonical_access,
                canonical_calculations, canonical_rungs, canonical_relationships, canonical_conditions,
                canonical_tag_data)
            if not _strict_equal(canonical_stateful_objects, stateful_objects):
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
        if canonical_access is not None:
            data.update({
                'schema_version': 2, 'report_version': 'engineering-review-2',
                'analysis_scope': 'source_evidence_with_operand_access',
                'access': canonical_access.to_dict(),
            })
            if canonical_access.status == 'partial':
                data['status'] = 'partial'
        if canonical_tag_data is not None:
            data.update({
                'schema_version': 3, 'report_version': 'engineering-review-3',
                'analysis_scope': 'source_evidence_with_operand_access_and_tag_data',
                'tag_data': canonical_tag_data.to_dict(),
            })
            if canonical_tag_data.status == 'partial':
                data['status'] = 'partial'
        if canonical_pid is not None:
            data.update({
                'schema_version': 4, 'report_version': 'engineering-review-4',
                'analysis_scope': 'source_evidence_with_operand_access_tag_data_and_pid',
                'pid': canonical_pid.to_dict(),
            })
            if canonical_pid.status == 'partial':
                data['status'] = 'partial'
        if canonical_pid_members is not None:
            data.update({
                'schema_version': 5, 'report_version': 'engineering-review-5',
                'analysis_scope': 'source_evidence_with_operand_access_tag_data_pid_and_member_headers',
                'pid_members': canonical_pid_members.to_dict(),
            })
            if canonical_pid_members.status == 'partial':
                data['status'] = 'partial'
        if canonical_calculations is not None:
            data.update({
                'schema_version': 6, 'report_version': 'engineering-review-6',
                'analysis_scope': 'source_evidence_with_operand_access_tag_data_pid_member_headers_and_calculations',
                'calculations': canonical_calculations.to_dict(),
            })
            if canonical_calculations.status == 'partial':
                data['status'] = 'partial'
        if canonical_rungs is not None:
            data.update({
                'schema_version': 7, 'report_version': 'engineering-review-7',
                'analysis_scope': 'source_evidence_with_rung_structure_and_purpose_candidates',
                'semantic_analysis': 'structural_and_candidate_evidence',
                'rung_analysis': canonical_rungs.to_dict(),
            })
            if canonical_rungs.status == 'partial':
                data['status'] = 'partial'
        if canonical_relationships is not None:
            data.update({
                'schema_version': 8, 'report_version': 'engineering-review-8',
                'analysis_scope': 'source_evidence_with_rung_candidates_and_exact_address_relationships',
                'relationships': canonical_relationships.to_dict(),
            })
            if canonical_relationships.status == 'partial':
                data['status'] = 'partial'
        if canonical_conditions is not None:
            review_version = 9 if canonical_conditions.schema_version == 1 else 10
            data.update({
                'schema_version': review_version, 'report_version': f'engineering-review-{review_version}',
                'analysis_scope': 'source_evidence_with_exact_addresses_and_local_boolean_conditions',
                'conditions': canonical_conditions.to_dict(),
            })
            if canonical_conditions.status == 'partial':
                data['status'] = 'partial'
        if canonical_binding_context is not None:
            data.update({
                'schema_version': 11, 'report_version': 'engineering-review-11',
                'binding_context': canonical_binding_context.to_dict(),
            })
            if canonical_binding_context.status == 'partial':
                data['status'] = 'partial'
        if canonical_custom_context is not None:
            data.update({
                'schema_version': 12, 'report_version': 'engineering-review-12',
                'custom_instruction_context': canonical_custom_context.to_dict(),
                'indexed_access': canonical_indexed_access.to_dict(),
            })
            if 'partial' in (canonical_custom_context.status, canonical_indexed_access.status):
                data['status'] = 'partial'
        if canonical_sfr_context is not None:
            data.update({'schema_version': 13, 'report_version': 'engineering-review-13',
                         'sfr_context': canonical_sfr_context.to_dict()})
            if canonical_sfr_context.status == 'partial':
                data['status'] = 'partial'
        if canonical_aoi_body is not None:
            data.update({'schema_version': 14, 'report_version': 'engineering-review-14',
                         'aoi_body_context': canonical_aoi_body.to_dict()})
            if canonical_aoi_body.status == 'partial':
                data['status'] = 'partial'
        if canonical_pid_connections is not None:
            data.update({'schema_version': 15, 'report_version': 'engineering-review-15',
                         'pid_connections': canonical_pid_connections.to_dict()})
            if canonical_pid_connections.status == 'partial':
                data['status'] = 'partial'
        if canonical_calculation_paths is not None:
            data.update({'schema_version': 16, 'report_version': 'engineering-review-16',
                         'calculation_paths': canonical_calculation_paths.to_dict()})
            if canonical_calculation_paths.status == 'partial':
                data['status'] = 'partial'
        if canonical_output_context is not None:
            data.update({'schema_version': 17, 'report_version': 'engineering-review-17',
                         'output_context': canonical_output_context.to_dict()})
            if canonical_output_context.status == 'partial':
                data['status'] = 'partial'
        if canonical_stateful_objects is not None:
            data.update({'schema_version': 18, 'report_version': 'engineering-review-18',
                         'stateful_objects': canonical_stateful_objects.to_dict()})
            if canonical_stateful_objects.status == 'partial':
                data['status'] = 'partial'
        _bounded_json(data, retain=False)
        return data
    except ReviewSizeLimitError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _fail()


def validate_review_data(snapshot: SourceSnapshot, inventory: InventoryResult,
                         references: ReferenceResult, sfc_structure: SfcStructureResult,
                         data: dict[str, Any], *, access: AccessResult | None = None,
                         tag_data: TagDataResult | None = None,
                         pid: PidResult | None = None,
                         pid_members: PidMemberResult | None = None,
                         calculations: CalculationResult | None = None,
                         rung_analysis: RungAnalysisResult | None = None,
                         relationships: RelationshipResult | None = None,
                         conditions: ConditionResult | None = None,
                         binding_context: BindingContextResult | None = None,
                         custom_instruction_context: CustomInstructionContextResult | None = None,
                         indexed_access: IndexedAccessResult | None = None,
                         sfr_context: SfrContextResult | None = None,
                         aoi_body_context: AoiBodyContextResult | None = None,
                         pid_connections: PidConnectionResult | None = None,
                         calculation_paths: CalculationPathResult | None = None,
                         output_context: BooleanOutputContextResult | None = None,
                         stateful_objects: StatefulObjectResult | None = None) -> None:
    """Compare every candidate field against bounded canonical captured evidence."""
    try:
        if _strict_equal(build_review_data(snapshot, inventory, references, sfc_structure,
                                          access=access, tag_data=tag_data, pid=pid,
                                          pid_members=pid_members, calculations=calculations,
                                          rung_analysis=rung_analysis, relationships=relationships,
                                          conditions=conditions, binding_context=binding_context,
                                          custom_instruction_context=custom_instruction_context,
                                          indexed_access=indexed_access, sfr_context=sfr_context,
                                          aoi_body_context=aoi_body_context,
                                          pid_connections=pid_connections,
                                          calculation_paths=calculation_paths,
                                          output_context=output_context, stateful_objects=stateful_objects), data):
            return
    except ReviewSizeLimitError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        pass
    _fail()


def render_review_json(data: dict[str, Any]) -> str:
    """Serialize PRIVATE data; persistence callers must validate it first."""
    try:
        return _bounded_json(data)
    except ReviewSizeLimitError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _fail()
