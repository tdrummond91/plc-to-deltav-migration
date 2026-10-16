"""Declaration candidates for unknown-family instructions, without call semantics.

Names are compared only within the owning controller, using ASCII case folding.
The private result links existing evidence IDs; it does not duplicate AOI source,
assign operand roles, validate parameter positions, or infer instruction effects.
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

from .access import AccessResult
from .binding_context import BindingContextResult, validate_binding_context
from .calculations import CalculationResult
from .conditions import ConditionResult
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult, _strict_record_match
from .relationships import RelationshipResult
from .rung_analysis import RungAnalysisResult
from .source import _read_nodes

MAX_CONTEXT_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 250_000
MAX_NAME_LENGTH = 64
CALL_STATUSES = frozenset({'unique_candidate', 'missing_declaration',
                           'ambiguous_declaration', 'unsupported_context'})
DECLARATION_STATUSES = frozenset({'unique_candidate', 'ambiguous_name',
                                  'invalid_name', 'unsupported_context'})
USAGES = frozenset({'input', 'output', 'inout', 'missing', 'other', 'unsupported_context'})
FLAGS = frozenset({'true', 'false', 'missing', 'other', 'unsupported_context'})
DATATYPES = frozenset({'present', 'missing', 'unsupported_context'})
LANGUAGES = frozenset({'rll', 'st', 'fbd', 'sfc', 'missing', 'other', 'unsupported_context'})
CONTENTS = frozenset({'rll', 'st', 'fbd', 'sfc', 'missing', 'other',
                      'multiple', 'unsupported_context'})
CONTEXT_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'custom-instruction-context-1',
    'analysis_scope': 'inventory_declaration_candidates', 'effects': 'not_analyzed',
    'parameter_roles': 'not_analyzed', 'call_validation': 'not_analyzed',
}
COUNT_MAPS = {
    'calls_by_status': CALL_STATUSES, 'definitions_by_status': DECLARATION_STATUSES,
    'parameter_usage': USAGES, 'parameter_required': FLAGS, 'parameter_visible': FLAGS,
    'parameter_datatype': DATATYPES, 'routine_languages': LANGUAGES,
    'routine_contents': CONTENTS,
}
COVERAGE_KEYS = frozenset(COUNT_MAPS) | {
    'source_rungs', 'source_instructions', 'source_operands', 'unknown_family_calls',
    'definitions_total', 'parameters_total', 'routines_total', 'encoded_regions_total',
    'definitions_with_encoded_regions', 'definitions_with_protection_markers',
    'unique_candidate_definitions_called',
}
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z', re.ASCII)
_PROTECTION_MARKERS = frozenset({'Protected', 'IsProtected', 'SourceProtected', 'SourceKey',
                                'SourceKeyName', 'ProtectionType', 'Encrypted', 'EncryptionInfo'})


class CustomInstructionContextError(ValueError):
    """A source-free rejection of inconsistent or excessive evidence."""


def _invalid() -> None:
    raise CustomInstructionContextError('Custom instruction context does not match its source evidence.')


def _limit() -> None:
    raise CustomInstructionContextError('Custom instruction context exceeds its evidence limits.')


@dataclass(frozen=True)
class CustomInstructionContextResult:
    snapshot: dict[str, str | int]
    status: str
    calls: list[dict[str, Any]]
    declarations: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'custom-instruction-context-1'
    analysis_scope: str = 'inventory_declaration_candidates'
    effects: str = 'not_analyzed'
    parameter_roles: str = 'not_analyzed'
    call_validation: str = 'not_analyzed'

    def to_dict(self) -> dict[str, Any]:
        render_custom_instruction_context_json(self)
        return deepcopy(vars(self))


def _namespace(name: str) -> str | None:
    return name.rsplit('}', 1)[0] if '}' in name else None


def _name(value: str | None) -> str | None:
    if value is None or len(value) > MAX_NAME_LENGTH or _NAME.fullmatch(value) is None:
        return None
    return value.lower()  # The lexical check makes this ASCII folding only.


def _derive(snapshot: SourceSnapshot, inventory: InventoryResult, access: AccessResult,
            rung_analysis: RungAnalysisResult) -> CustomInstructionContextResult:
    if max(len(inventory.entities), len(inventory.rungs), len(access.instructions), len(access.operands)) > MAX_RECORDS:
        _limit()
    nodes = _read_nodes(snapshot.data)
    root_namespace = _namespace(nodes[0].expanded_name)
    by_locator = {node.locator: index for index, node in enumerate(nodes)}
    # Require every envelope in the path to share the source-root namespace.
    supported: list[bool] = []
    for node in nodes:
        supported.append(_namespace(node.expanded_name) == root_namespace
                         and all('}' not in key for key in node.expanded_attributes)
                         and (node.parent is None or supported[node.parent]))

    def context(locator: str) -> bool:
        index = by_locator[locator]
        return supported[index]

    entities = {entity.id: entity for entity in inventory.entities}
    controllers: dict[str, str | None] = {}
    owners: dict[str, str | None] = {}
    for entity in inventory.entities:  # Inventory is in parent-before-child source order.
        controllers[entity.id] = entity.id if entity.kind == 'controller' else controllers.get(entity.parent_id)
        owners[entity.id] = entity.id if entity.kind == 'aoi' else owners.get(entity.parent_id)
    children: dict[str, list[Any]] = defaultdict(list)
    for entity in inventory.entities:
        owner = owners[entity.id]
        if owner is not None and entity.id != owner:
            children[owner].append(entity)

    c = {key: dict.fromkeys(sorted(values), 0) for key, values in COUNT_MAPS.items()}
    c.update(dict.fromkeys(sorted(COVERAGE_KEYS - COUNT_MAPS.keys()), 0))
    c.update(source_rungs=len(inventory.rungs), source_instructions=len(access.instructions),
             source_operands=len(access.operands))
    declarations: list[dict[str, Any]] = []
    candidates: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    unsupported_names: set[tuple[str, str]] = set()
    retained = records = 0

    def charge(row: Any) -> None:
        nonlocal retained, records
        records += 1
        retained += len(json.dumps(row, ensure_ascii=True, separators=(',', ':'))) + 1
        if records > MAX_RECORDS or retained > MAX_CONTEXT_BYTES:
            _limit()

    def flag(attributes: dict[str, str], key: str) -> str:
        value = attributes.get(key)
        return {'true': 'true', 'false': 'false'}.get(value, 'missing' if value is None else 'other')

    for entity in inventory.entities:
        if entity.kind != 'aoi':
            continue
        controller_id, folded = controllers[entity.id], _name(entity.name)
        supported_definition = bool(controller_id and context(entity.locator)
                                    and context(entities[controller_id].locator))
        status = ('unsupported_context' if not supported_definition else
                  'invalid_name' if folded is None else 'unique_candidate')
        row = {'source_id': entity.id, 'controller_id': controller_id, 'status': status,
               'parameters': [], 'routines': [], 'encoded_region_ids': [],
               'protection_marker': 'present' if supported_definition and
               _PROTECTION_MARKERS.intersection(entity.attributes) else 'none_observed'}
        # Count IDs and nested records before retaining their aggregate container.
        for child in children[entity.id]:
            valid = supported_definition and context(child.locator)
            attributes = child.attributes
            if child.kind == 'aoi_parameter':
                usage = {'Input': 'input', 'Output': 'output', 'InOut': 'inout'}.get(
                    attributes.get('Usage'), 'missing' if 'Usage' not in attributes else 'other')
                parameter = {'source_id': child.id,
                             'usage': usage if valid else 'unsupported_context',
                             'required': flag(attributes, 'Required') if valid else 'unsupported_context',
                             'visible': flag(attributes, 'Visible') if valid else 'unsupported_context',
                             'datatype': ('present' if attributes.get('DataType') else 'missing')
                             if valid else 'unsupported_context'}
                charge(parameter)
                row['parameters'].append(parameter)
                c['parameters_total'] += 1
                for field in ('usage', 'required', 'visible', 'datatype'):
                    c[f'parameter_{field}'][parameter[field]] += 1
            elif child.kind == 'routine':
                language = {'RLL': 'rll', 'ST': 'st', 'FBD': 'fbd', 'SFC': 'sfc'}.get(
                    attributes.get('Type'), 'missing' if 'Type' not in attributes else 'other')
                node = nodes[by_locator[child.locator]]
                bodies = [nodes[i] for i in node.children if nodes[i].name.endswith('Content')]
                if not valid or any(not context(body.locator) for body in bodies):
                    content = 'unsupported_context'
                elif not bodies:
                    content = 'missing'
                elif len(bodies) != 1:
                    content = 'multiple'
                else:
                    content = {'RLLContent': 'rll', 'STContent': 'st', 'FBDContent': 'fbd',
                               'SFCContent': 'sfc'}.get(bodies[0].name, 'other')
                routine = {'source_id': child.id, 'language': language if valid else 'unsupported_context',
                           'content': content}
                charge(routine)
                row['routines'].append(routine)
                c['routines_total'] += 1
                c['routine_languages'][routine['language']] += 1
                c['routine_contents'][content] += 1
            elif child.kind == 'encoded_region':
                charge(child.id)
                row['encoded_region_ids'].append(child.id)
                c['encoded_regions_total'] += 1
        charge(row)
        declarations.append(row)
        if controller_id is not None and folded is not None:
            if status == 'unique_candidate':
                candidates[controller_id, folded].append(row)
            elif status == 'unsupported_context':
                unsupported_names.add((controller_id, folded))
        c['definitions_with_encoded_regions'] += bool(row['encoded_region_ids'])
        c['definitions_with_protection_markers'] += row['protection_marker'] == 'present'
    for key, matches in candidates.items():
        if key in unsupported_names:
            # A similarly named extension declaration is not silently ignored.
            for row in matches:
                row['status'] = 'unsupported_context'
        elif len(matches) > 1:
            for row in matches:
                row['status'] = 'ambiguous_name'
    for row in declarations:
        c['definitions_by_status'][row['status']] += 1
    c['definitions_total'] = len(declarations)

    source_rungs = {rung.id: rung for rung in inventory.rungs}
    instructions = {instruction.id: instruction for rung in inventory.rungs for instruction in rung.instructions}
    calls: list[dict[str, Any]] = []
    called: set[str] = set()
    for block in rung_analysis.blocks:
        if block['family'] != 'unknown':
            continue
        instruction = instructions[block['id']]
        rung = source_rungs[block['rung_id']]
        controller_id = controllers.get(rung.parent_id)
        folded = _name(instruction.opcode)
        key = (controller_id, folded)
        matches = candidates.get(key, [])
        rung_node = nodes[by_locator[rung.locator]]
        source_text_supported = all(context(nodes[index].locator) for index in rung_node.children
                                    if nodes[index].name == 'Text')
        if (not controller_id or folded is None or not context(rung.locator)
                or not source_text_supported or not context(entities[controller_id].locator)
                or key in unsupported_names):
            status = 'unsupported_context'
        elif len(matches) == 1:
            status = 'unique_candidate'
        elif matches:
            status = 'ambiguous_declaration'
        else:
            status = 'missing_declaration'
        declaration_id = matches[0]['source_id'] if status == 'unique_candidate' else None
        call = {'instruction_id': instruction.id, 'rung_id': rung.id, 'controller_id': controller_id,
                'status': status, 'declaration_id': declaration_id}
        charge(call)
        calls.append(call)
        c['calls_by_status'][status] += 1
        if declaration_id is not None:
            called.add(declaration_id)
    c.update(unknown_family_calls=len(calls), unique_candidate_definitions_called=len(called))
    incomplete = (len(calls) != c['calls_by_status']['unique_candidate']
                  or len(declarations) != c['definitions_by_status']['unique_candidate'])
    return CustomInstructionContextResult(deepcopy(inventory.snapshot), 'partial' if incomplete else 'complete',
                                          calls, declarations, c)


def analyze_custom_instruction_context(snapshot: SourceSnapshot, inventory: InventoryResult,
                                       references: ReferenceResult, access: AccessResult,
                                       calculations: CalculationResult, rung_analysis: RungAnalysisResult,
                                       relationships: RelationshipResult, conditions: ConditionResult,
                                       binding_context: BindingContextResult) -> CustomInstructionContextResult:
    try:
        validate_binding_context(snapshot, inventory, references, access, calculations, rung_analysis,
                                 relationships, conditions, binding_context)
        result = _derive(snapshot, inventory, access, rung_analysis)
        render_custom_instruction_context_json(result)
        return result
    except CustomInstructionContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_custom_instruction_context(snapshot: SourceSnapshot, inventory: InventoryResult,
                                        references: ReferenceResult, access: AccessResult,
                                        calculations: CalculationResult, rung_analysis: RungAnalysisResult,
                                        relationships: RelationshipResult, conditions: ConditionResult,
                                        binding_context: BindingContextResult,
                                        result: CustomInstructionContextResult) -> None:
    try:
        render_custom_instruction_context_json(result)
        expected = analyze_custom_instruction_context(snapshot, inventory, references, access, calculations,
                                                      rung_analysis, relationships, conditions, binding_context)
        if not _strict_record_match(vars(expected), vars(result)):
            _invalid()
    except CustomInstructionContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_custom_instruction_context_json(result: CustomInstructionContextResult) -> str:
    """Bound native containers before serialization; source authentication is separate."""
    try:
        if (type(result) is not CustomInstructionContextResult
                or vars(result).keys() != set(CustomInstructionContextResult.__dataclass_fields__)):
            _invalid()
        payload, remaining = vars(result), MAX_CONTEXT_BYTES
        stack: list[tuple[Any, int | None]] = [(iter((payload,)), None)]
        active: set[int] = set()
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
    except CustomInstructionContextError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
