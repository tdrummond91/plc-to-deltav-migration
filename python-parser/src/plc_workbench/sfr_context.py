"""Bounded SFR declaration and chart-step candidates, never execution effects.

Routine names use the program-local namespace. Named step operands share only
exact resolved root/suffix identity; this does not validate a member or type.
Every exported chart edit remains separate and no active revision is selected.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from io import StringIO
from itertools import chain
import json
import re
from typing import Any

from .access import AccessResult, validate_access
from .calculations import CalculationResult, validate_calculations
from .models import InventoryResult, SourceSnapshot
from .references import (
    MAX_ADDRESS_LENGTH, ReferenceResult, _ADDRESS, _Resolver, _binding, _literal,
    _strict_record_match,
)
from .sfc_structure import SfcStructureResult, validate_sfc_structure
from .source import _read_nodes

MAX_CONTEXT_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 250_000
MAX_NAME_LENGTH = 64
SIGNATURE_STATUSES = frozenset({'classified', 'argument_count_mismatch', 'empty_argument'})
ROUTINE_STATUSES = frozenset({'not_analyzed', 'unsupported_context', 'unsupported_name',
    'missing_candidate', 'ambiguous_candidate', 'unique_candidate'})
CHART_STATUSES = frozenset({'not_analyzed', 'not_sfc', 'protected', 'missing_content',
                          'available', 'unsupported_context'})
SELECTOR_KINDS = frozenset({'not_analyzed', 'named', 'initial'})
MATCH_STATUSES = frozenset({'unique_candidate', 'missing_candidate', 'ambiguous_candidate',
                          'selector_unresolved', 'unsupported_context', 'incomplete_context'})
STEP_BINDINGS = frozenset({'root_bound', 'unresolved', 'ambiguous', 'alias_cycle',
    'alias_depth_limit', 'unsupported_address', 'missing_operand', 'empty_operand',
    'unsupported_context', 'invalid_identity', 'literal'})
INITIAL_KINDS = frozenset({'true', 'false', 'missing', 'other'})
CONTEXT_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'sfr-context-1',
    'analysis_scope': 'declared_sfr_target_context', 'execution': 'not_analyzed',
    'reset_effects': 'not_analyzed', 'edit_selection': 'not_analyzed',
    'member_validation': 'not_analyzed',
}
COUNT_MAPS = {
    'calls_by_signature': SIGNATURE_STATUSES, 'calls_by_routine_status': ROUTINE_STATUSES,
    'calls_by_chart_status': CHART_STATUSES, 'calls_by_selector_kind': SELECTOR_KINDS,
    'content_matches_by_status': MATCH_STATUSES, 'steps_by_binding': STEP_BINDINGS,
    'initial_markers_by_kind': INITIAL_KINDS,
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | {
    'source_rungs', 'source_instructions', 'source_operands', 'source_sfc_routines',
    'source_sfc_contents', 'source_sfc_steps', 'calls_total', 'steps_total',
    'content_matches_total', 'matched_calls', 'fully_matched_calls', 'multiple_content_calls',
}
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z', re.ASCII)
_PROTECTION_MARKERS = frozenset({'Protected', 'IsProtected', 'SourceProtected', 'SourceKey',
                                'SourceKeyName', 'ProtectionType', 'Encrypted', 'EncryptionInfo'})


class SfrContextError(ValueError):
    """A source-free rejection of inconsistent or excessive evidence."""


def _invalid() -> None:
    raise SfrContextError('SFR context does not match its source evidence.')


def _limit() -> None:
    raise SfrContextError('SFR context exceeds its evidence limits.')


@dataclass(frozen=True)
class SfrContextResult:
    snapshot: dict[str, str | int]
    status: str
    calls: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'sfr-context-1'
    analysis_scope: str = 'declared_sfr_target_context'
    execution: str = 'not_analyzed'
    reset_effects: str = 'not_analyzed'
    edit_selection: str = 'not_analyzed'
    member_validation: str = 'not_analyzed'

    def to_dict(self) -> dict[str, Any]:
        render_sfr_context_json(self)
        return deepcopy(vars(self))


def _namespace(name: str) -> str | None:
    return name.rsplit('}', 1)[0] if '}' in name else None


def _name(value: str | None) -> str | None:
    if value is None or len(value) > MAX_NAME_LENGTH or _NAME.fullmatch(value) is None:
        return None
    return value.lower()


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, access: AccessResult,
            sfc_structure: SfcStructureResult) -> SfrContextResult:
    if max(len(inventory.entities), len(inventory.rungs), len(access.instructions),
           len(access.operands), len(sfc_structure.elements)) > MAX_RECORDS:
        _limit()
    nodes = _read_nodes(snapshot.data)
    root_namespace = _namespace(nodes[0].expanded_name)
    supported: dict[str, bool] = {}
    node_supported: list[bool] = []
    rung_locators = {row.locator for row in inventory.rungs}
    nearest_rung: list[str | None] = []
    unsupported_rungs: set[str] = set()
    for node in nodes:
        valid = (_namespace(node.expanded_name) == root_namespace
                 and all('}' not in key for key in node.expanded_attributes)
                 and (node.parent is None or node_supported[node.parent]))
        node_supported.append(valid)
        supported[node.locator] = valid
        rung_locator = (node.locator if node.locator in rung_locators else
                        nearest_rung[node.parent] if node.parent is not None else None)
        nearest_rung.append(rung_locator)
        if not valid and rung_locator is not None:
            unsupported_rungs.add(rung_locator)
    entities = {row.id: row for row in inventory.entities}
    instruction_access = {row['id']: row for row in access.instructions}
    operand_access = {row['id']: row for row in access.operands}
    chart_by_id = {row['routine_id']: row for row in sfc_structure.routines}
    contents_by_routine: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for content in sfc_structure.contents:
        contents_by_routine[content['routine_id']].append(content)
    # Namespace-invalid descendants remain an explicit gap for the whole
    # content; filtering them out could make an apparent unique match.
    unsupported_contents = {
        row['content_id'] for row in sfc_structure.elements if not supported[row['locator']]
    }
    incomplete_contents = {row['content_id'] for row in sfc_structure.elements if row['kind'] == 'unmodeled'}
    names: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for entity in inventory.entities:
        owner = entities.get(entity.parent_id)
        name = _name(entity.name)
        if (entity.kind == 'routine' and owner is not None and owner.kind == 'program'
                and entity.scope_id == owner.id and name is not None):
            # Keep collisions before language/namespace filtering.
            names[owner.id, name].append(entity)
    resolver = _Resolver(inventory)
    retained = records = 0

    def charge(row: Any) -> None:
        nonlocal retained, records
        records += 1
        retained += len(json.dumps(row, ensure_ascii=True, separators=(',', ':'))) + 1
        if records > MAX_RECORDS or retained > MAX_CONTEXT_BYTES:
            _limit()

    def binding(raw: str | None, scope_id: str | None, context_valid: bool) -> dict[str, Any]:
        if not context_valid:
            return _binding('unsupported_context')
        if raw is None:
            return _binding('missing_operand')
        value = raw.strip()
        if not value:
            return _binding('empty_operand')
        if _literal(value):
            return _binding('literal')
        result = resolver.resolve(value, scope_id)
        if result['status'] == 'root_bound':
            linked = [result['symbol_id'], result['target_id'], *result['alias_chain']]
            if any(identifier not in entities or not supported[entities[identifier].locator]
                   for identifier in linked):
                return _binding('unsupported_context')
            suffix = result['suffix']
            if len(suffix) > MAX_ADDRESS_LENGTH or _ADDRESS.fullmatch('A' + suffix) is None:
                return _binding('invalid_identity')
        return result

    steps: list[dict[str, Any]] = []
    named_steps: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    initial_steps: dict[str, list[str]] = defaultdict(list)
    named_incomplete: set[str] = set()
    initial_incomplete: set[str] = set()
    for element in sfc_structure.elements:
        if element['kind'] != 'step':
            continue
        routine = entities[element['routine_id']]
        result = binding(element['attributes'].get('Operand'), routine.scope_id,
                         supported[element['locator']])
        raw_initial = element['attributes'].get('InitialStep')
        initial = (raw_initial if raw_initial in {'true', 'false'} else
                   'missing' if raw_initial is None else 'other')
        row = {'element_id': element['id'], 'content_id': element['content_id'],
               'routine_id': element['routine_id'], 'binding_status': result['status'],
               'symbol_id': result['symbol_id'], 'target_id': result['target_id'],
               'suffix': result['suffix'], 'alias_chain': list(result['alias_chain']),
               'initial_kind': initial}
        charge(row)
        steps.append(row)
        if result['status'] == 'root_bound':
            named_steps[row['content_id'], row['target_id'], row['suffix']].append(row['element_id'])
        else:
            named_incomplete.add(row['content_id'])
        if initial == 'true':
            initial_steps[row['content_id']].append(row['element_id'])
        elif initial in {'missing', 'other'}:
            # No documented missing-marker default is applied to source XML.
            initial_incomplete.add(row['content_id'])

    calls: list[dict[str, Any]] = []
    for rung in inventory.rungs:
        if rung.parse_status != 'parsed':
            continue
        caller = entities.get(rung.parent_id)
        program = entities.get(caller.parent_id) if caller is not None else None
        valid_context = (caller is not None and caller.kind == 'routine'
                         and caller.attributes.get('Type') == 'RLL'
                         and program is not None and program.kind == 'program'
                         and caller.scope_id == program.id and rung.scope_id == program.id
                         and supported[rung.locator] and supported[caller.locator]
                         and supported[program.locator] and rung.locator not in unsupported_rungs)
        for instruction in rung.instructions:
            if not instruction.opcode.isascii() or instruction.opcode.upper() != 'SFR':
                continue
            use = instruction_access[instruction.id]
            signature = use['status']
            if signature not in SIGNATURE_STATUSES:
                _invalid()
            row: dict[str, Any] = {
                'instruction_id': instruction.id, 'rung_id': rung.id,
                'caller_routine_id': rung.parent_id,
                'program_id': program.id if valid_context else None,
                'target_operand_id': use['operand_ids'][1] if len(use['operand_ids']) > 1 else None,
                'signature_status': signature, 'routine_status': 'not_analyzed',
                'routine_candidate_count': 0, 'target_routine_id': None,
                'chart_status': 'not_analyzed', 'selector_kind': 'not_analyzed',
                'selector_binding_status': 'not_analyzed', 'content_matches': [],
            }
            target = None
            selector = None
            if signature == 'classified':
                is_initial = instruction.arguments[1].strip() == '0'
                row['selector_kind'] = 'initial' if is_initial else 'named'
                selector = (None if is_initial else
                            binding(instruction.arguments[1], rung.scope_id, bool(valid_context)))
                row['selector_binding_status'] = 'initial' if is_initial else selector['status']
                # Existing possible-write evidence remains unchanged and its
                # exact identity must agree before adding contextual links.
                previous = operand_access[row['target_operand_id']]
                if selector is not None and selector['status'] == 'root_bound':
                    if (previous['binding_status'] != 'root_bound'
                            or any(previous[key] != selector[key]
                                   for key in ('symbol_id', 'target_id', 'suffix', 'alias_chain'))):
                        _invalid()
                name = _name(instruction.arguments[0].strip())
                if not valid_context:
                    row['routine_status'] = 'unsupported_context'
                elif name is None:
                    row['routine_status'] = 'unsupported_name'
                else:
                    candidates = names.get((program.id, name), [])
                    row['routine_candidate_count'] = len(candidates)
                    row['routine_status'] = ('missing_candidate' if not candidates else
                                             'ambiguous_candidate' if len(candidates) > 1 else
                                             'unique_candidate')
                    if len(candidates) == 1:
                        target = candidates[0]
                        row['target_routine_id'] = target.id
            if target is not None:
                chart = chart_by_id.get(target.id)
                contents = contents_by_routine[target.id]
                row['chart_status'] = (
                    'unsupported_context' if not supported[target.locator] else
                    'not_sfc' if target.attributes.get('Type') != 'SFC' else
                    # Presence is a conservative metadata boundary, not an
                    # assertion that a particular source key is usable.
                    'protected' if chart['protection_markers']
                    or _PROTECTION_MARKERS.intersection(target.attributes) else
                    'unsupported_context' if chart['unmodeled_children'] or chart['direct_text'].strip() else
                    'missing_content' if not contents else 'available')
                if row['chart_status'] == 'available':
                    for content in contents:
                        candidate_ids: list[str] = []
                        if row['selector_kind'] == 'initial':
                            candidate_ids = initial_steps[content['id']]
                            incomplete = content['id'] in initial_incomplete
                        elif selector['status'] == 'root_bound':
                            candidate_ids = named_steps[content['id'], selector['target_id'], selector['suffix']]
                            incomplete = content['id'] in named_incomplete
                        else:
                            incomplete = False
                        status = (
                            'unsupported_context' if not supported[content['locator']]
                            or content['id'] in unsupported_contents else
                            'selector_unresolved' if selector is not None and selector['status'] != 'root_bound' else
                            'incomplete_context' if incomplete or content['id'] in incomplete_contents
                            or content['direct_text'].strip() else
                            'missing_candidate' if not candidate_ids else
                            'ambiguous_candidate' if len(candidate_ids) > 1 else 'unique_candidate')
                        match = {'content_id': content['id'], 'edit_kind': content['edit_kind'],
                                 'status': status, 'candidate_count': len(candidate_ids),
                                 'candidate_step_ids': list(candidate_ids),
                                 'target_step_id': candidate_ids[0] if status == 'unique_candidate' else None}
                        charge(match)
                        row['content_matches'].append(match)
            # Matches were already incrementally charged. Charge their array
            # shell with the call, avoiding a large intermediate serialization.
            charge({**row, 'content_matches': []})
            calls.append(row)

    coverage: dict[str, Any] = {key: dict.fromkeys(sorted(values), 0)
                              for key, values in COUNT_MAPS.items()}
    coverage.update(source_rungs=len(inventory.rungs), source_instructions=len(access.instructions),
                    source_operands=len(access.operands), source_sfc_routines=len(sfc_structure.routines),
                    source_sfc_contents=len(sfc_structure.contents), source_sfc_steps=len(steps),
                    calls_total=len(calls), steps_total=len(steps), content_matches_total=0,
                    matched_calls=0, fully_matched_calls=0, multiple_content_calls=0)
    for row in calls:
        for field, count in (('signature_status', 'calls_by_signature'),
                             ('routine_status', 'calls_by_routine_status'),
                             ('chart_status', 'calls_by_chart_status'),
                             ('selector_kind', 'calls_by_selector_kind')):
            coverage[count][row[field]] += 1
        matches = row['content_matches']
        coverage['content_matches_total'] += len(matches)
        for match in matches:
            coverage['content_matches_by_status'][match['status']] += 1
        resolved = sum(match['status'] == 'unique_candidate' for match in matches)
        coverage['matched_calls'] += int(bool(resolved))
        coverage['fully_matched_calls'] += int(bool(matches) and resolved == len(matches))
        coverage['multiple_content_calls'] += int(len(matches) > 1)
    for row in steps:
        coverage['steps_by_binding'][row['binding_status']] += 1
        coverage['initial_markers_by_kind'][row['initial_kind']] += 1
    complete = (coverage['fully_matched_calls'] == len(calls)
                and coverage['steps_by_binding']['root_bound'] == len(steps)
                and coverage['initial_markers_by_kind']['other'] == 0)
    return SfrContextResult(dict(inventory.snapshot), 'complete' if complete else 'partial',
                            calls, steps, coverage)


def analyze_sfr_context(snapshot: SourceSnapshot, inventory: InventoryResult,
                        references: ReferenceResult, access: AccessResult,
                        calculations: CalculationResult,
                        sfc_structure: SfcStructureResult) -> SfrContextResult:
    """Authenticate supplied companions and derive only bounded target context."""
    try:
        validate_calculations(snapshot, inventory, references, calculations)
        if type(access) is not AccessResult or type(access.schema_version) is not int or access.schema_version not in {3, 4}:
            _invalid()
        if access.schema_version == 4:
            validate_access(inventory, references, access, snapshot=snapshot, calculations=calculations)
        else:
            validate_access(inventory, references, access)
        validate_sfc_structure(snapshot, inventory, sfc_structure)
        result = _derive(snapshot, inventory, access, sfc_structure)
        render_sfr_context_json(result)
        return result
    except SfrContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_sfr_context(snapshot: SourceSnapshot, inventory: InventoryResult,
                         references: ReferenceResult, access: AccessResult,
                         calculations: CalculationResult, sfc_structure: SfcStructureResult,
                         result: SfrContextResult) -> None:
    try:
        expected = analyze_sfr_context(snapshot, inventory, references, access, calculations, sfc_structure)
        if type(result) is not SfrContextResult or not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except SfrContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_sfr_context_json(result: SfrContextResult) -> str:
    """Render private linked evidence with bounded native-container traversal."""
    try:
        if type(result) is not SfrContextResult or vars(result).keys() != set(SfrContextResult.__dataclass_fields__):
            _invalid()
        payload = vars(result)
        stack: list[tuple[Any, int | None]] = [(iter((payload,)), None)]
        active: set[int] = set()
        remaining = MAX_CONTEXT_BYTES
        while stack:
            try:
                value = next(stack[-1][0])
            except StopIteration:
                _, identifier = stack.pop()
                if identifier is not None:
                    active.remove(identifier)
                continue
            remaining -= 1
            if type(value) is str:
                remaining -= len(value)
            elif type(value) in {dict, list}:
                if len(value) > MAX_RECORDS or id(value) in active or len(stack) > 12:
                    _limit()
                if type(value) is dict and any(type(key) is not str for key in value):
                    _invalid()
                active.add(id(value))
                values = chain(value.keys(), value.values()) if type(value) is dict else value
                stack.append((iter(values), id(value)))
            elif type(value) not in {int, bool, type(None)}:
                _invalid()
            if remaining < 0:
                _limit()
        output, size = StringIO(), 0
        for chunk in json.JSONEncoder(ensure_ascii=True, sort_keys=True, indent=2).iterencode(payload):
            size += len(chunk)
            if size + 1 > MAX_CONTEXT_BYTES:
                _limit()
            output.write(chunk)
        return output.getvalue() + '\n'
    except SfrContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
