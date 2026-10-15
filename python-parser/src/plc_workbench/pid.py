"""Bounded PID occurrence and stored-structure evidence, without loop semantics.

Slot names describe the seven exported instruction arguments. They do not prove
execution, reads/writes, types, approved loop identity, cascade behavior, current
values or effective initialization. Stored representations and duplicate members
remain separate canonical source links; no representation or member wins.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from io import StringIO
import json
from typing import Any

from .models import InventoryResult, SourceSnapshot
from .references import OPERAND_STATUSES, ReferenceResult, validate_references
from .source import _read_nodes
from .tag_data import TagDataResult, _namespace, _strict_match, validate_tag_data

MAX_PID_OCCURRENCES = 250_000
MAX_PID_OPERANDS = 250_000
MAX_PID_EVIDENCE_BYTES = 16 * 1024 * 1024
MAX_PID_JSON_BYTES = 16 * 1024 * 1024
SLOT_NAMES = ('pid_structure', 'process_variable', 'tieback', 'control_variable',
              'master_loop', 'inhold_bit', 'inhold_value')
SLOT_KINDS = frozenset((*SLOT_NAMES, 'unknown'))
SIGNATURE_STATUSES = frozenset({'recognized', 'argument_count_mismatch', 'empty_argument'})
STORAGE_STATUSES = frozenset({
    'signature_unresolved', 'first_operand_unbound', 'owner_not_captured',
    'owner_namespace_unsupported', 'binding_namespace_unsupported',
    'suffix_not_empty', 'declaration_not_pid',
    'dimensions_unmodeled', 'no_data', 'no_decorated_data', 'no_pid_structure', 'linked',
})
PID_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'pid-evidence-1',
    'analysis_scope': 'pid_occurrence_evidence', 'semantic_analysis': 'not_implemented',
    'execution_analysis': 'not_implemented', 'initialization_analysis': 'not_implemented',
    'member_validation': 'not_implemented', 'effective_value_selection': 'not_implemented',
    'numeric_analysis': 'not_implemented',
}
COVERAGE_KEYS = frozenset({
    'source_rungs', 'unparsed_rungs', 'source_instructions', 'source_operands',
    'occurrences_total', 'occurrences_by_signature', 'operands_total', 'operands_by_slot',
    'operands_by_binding', 'storage_by_status', 'distinct_backing_owners',
    'backing_owners_with_data', 'backing_owners_without_data', 'backing_owners_with_opaque_only',
    'representation_occurrences', 'decorated_representation_occurrences',
    'structure_occurrences', 'direct_member_occurrences', 'occurrences_with_backing_owner',
    'occurrences_with_data', 'occurrences_without_data', 'occurrences_with_opaque_only',
    'occurrences_with_multiple_representations', 'occurrences_with_multiple_structures',
})
_MEMBER_KINDS = frozenset({'data_value_member', 'structure_member', 'array_member'})
_SAFE_KINDS = frozenset({'structure', 'array', 'element', *_MEMBER_KINDS})


class PidError(ValueError):
    """Fixed source-free rejection of inconsistent or excessive PID evidence."""


@dataclass(frozen=True)
class PidResult:
    snapshot: dict[str, str | int]
    status: str
    occurrences: list[dict[str, Any]]
    operands: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'pid-evidence-1'
    analysis_scope: str = 'pid_occurrence_evidence'
    semantic_analysis: str = 'not_implemented'
    execution_analysis: str = 'not_implemented'
    initialization_analysis: str = 'not_implemented'
    member_validation: str = 'not_implemented'
    effective_value_selection: str = 'not_implemented'
    numeric_analysis: str = 'not_implemented'

    def to_dict(self) -> dict[str, Any]:
        """Return private source links; authenticate before copying caller records."""
        return asdict(self)


def _invalid() -> None:
    raise PidError('PID evidence is inconsistent or exceeds its limits.') from None


def _ascii_pid(value: Any) -> bool:
    return type(value) is str and value.isascii() and value.upper() == 'PID'


def _check_limits(inventory: InventoryResult, references: ReferenceResult) -> None:
    if (type(inventory) is not InventoryResult or type(references) is not ReferenceResult
            or type(inventory.rungs) is not list or type(references.operands) is not list
            or len(references.operands) > MAX_PID_OPERANDS):
        _invalid()
    instructions = operands = 0
    for rung in inventory.rungs:
        if rung.parse_status == 'parsed':
            instructions += len(rung.instructions)
            operands += sum(len(instruction.arguments) for instruction in rung.instructions)
            if instructions > MAX_PID_OCCURRENCES or operands > MAX_PID_OPERANDS:
                _invalid()


def _derive_pid(snapshot: SourceSnapshot, inventory: InventoryResult,
                references: ReferenceResult, tag_data: TagDataResult) -> PidResult:
    nodes = _read_nodes(snapshot.data)
    root_namespace = _namespace(nodes[0].expanded_name)
    nodes_by_locator = {node.locator: node for node in nodes}
    # The reference contract intentionally retains legacy local-name bindings.
    # PID association additionally checks only the paths actually used by that
    # binding, so a foreign alias/scope cannot acquire ordinary PID semantics.
    binding_provenance: dict[str, bool] = {}
    for node in nodes:
        binding_provenance[node.locator] = (
            _namespace(node.expanded_name) == root_namespace
            and not any('}' in key and key.rsplit('}', 1)[-1] in {'Name', 'TagType', 'AliasFor'}
                        for key in node.expanded_attributes)
            and (node.parent is None or binding_provenance[nodes[node.parent].locator]))
    entities = {entity.id: entity for entity in inventory.entities}
    owners = {owner['source_id']: owner for owner in tag_data.owners}
    contents = {row['id']: row for row in tag_data.contents}
    children: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for element in tag_data.elements:
        children[element['parent_id']].append(element)
    # Canonical elements are preorder, so descendants are classified before
    # parents here. This bounds work even with repeated calls to one owner.
    safe: dict[str, bool] = {}
    for element in reversed(tag_data.elements):
        attribute_names = {key.rsplit('}', 1)[-1] for key in element['attributes']}
        structural_conflict = (
            element['kind'] in {'structure', 'structure_member', 'array', 'array_member'}
            and 'Value' in attribute_names
            or element['kind'] in {'structure', 'structure_member'}
            and 'Dimensions' in attribute_names)
        safe[element['id']] = (element['kind'] in _SAFE_KINDS
                               and element['xml_namespace'] == root_namespace
                               and not element['direct_text'].strip()
                               and not structural_conflict
                               and all(safe[child['id']] for child in children[element['id']]))
    owner_evidence: dict[str, dict[str, Any]] = {}
    retained = 0

    def retain(row: Any) -> None:
        nonlocal retained
        pending = [row]
        while pending:
            value = pending.pop()
            retained += 1
            if type(value) is str:
                retained += len(value.encode('utf-8'))
            elif type(value) is dict:
                pending.extend(value.keys())
                pending.extend(value.values())
            elif type(value) is list:
                pending.extend(value)
            if retained > MAX_PID_EVIDENCE_BYTES:
                _invalid()

    def owner_links(owner_id: str) -> dict[str, Any]:
        if owner_id in owner_evidence:
            return owner_evidence[owner_id]
        owner = owners[owner_id]
        node = nodes_by_locator[entities[owner_id].locator]
        namespace_supported = _namespace(node.expanded_name) == root_namespace
        content_ids = list(owner['content_ids'])
        decorated = [content_id for content_id in content_ids if namespace_supported
                     and contents[content_id]['xml_namespace'] == root_namespace
                     and contents[content_id]['format_kind'] == 'decorated']
        candidates = []
        for content_id in decorated:
            if contents[content_id]['direct_text'].strip():
                continue
            for element in children[content_id]:
                if (element['kind'] == 'structure' and safe[element['id']]
                        and _ascii_pid(element['attributes'].get('DataType'))
                        and all(member['kind'] in _MEMBER_KINDS
                                for member in children[element['id']])):
                    candidates.append({'content_id': content_id, 'structure_id': element['id'],
                                       'member_ids': [member['id'] for member in children[element['id']]]})
        evidence = {'namespace_supported': namespace_supported, 'attributes': node.expanded_attributes,
                    'content_ids': content_ids, 'decorated_content_ids': decorated,
                    'structure_candidates': candidates}
        owner_evidence[owner_id] = evidence
        return evidence

    occurrences: list[dict[str, Any]] = []
    operands: list[dict[str, Any]] = []
    coverage: dict[str, Any] = dict.fromkeys(sorted(COVERAGE_KEYS), 0)
    coverage.update(occurrences_by_signature=dict.fromkeys(sorted(SIGNATURE_STATUSES), 0),
                    operands_by_slot=dict.fromkeys(sorted(SLOT_KINDS), 0),
                    operands_by_binding=dict.fromkeys(sorted(OPERAND_STATUSES), 0),
                    storage_by_status=dict.fromkeys(sorted(STORAGE_STATUSES), 0))
    source_operands = iter(references.operands)
    backing_owners: set[str] = set()
    for rung in inventory.rungs:
        if rung.parse_status != 'parsed':
            coverage['unparsed_rungs'] += 1
            continue
        rung_node = nodes_by_locator[rung.locator]
        rung_binding_supported = (binding_provenance[rung.locator]
                                  and all(binding_provenance[nodes[index].locator]
                                          for index in rung_node.children
                                          if nodes[index].name == 'Text'))
        for instruction in rung.instructions:
            coverage['source_instructions'] += 1
            bound = [next(source_operands) for _ in instruction.arguments]
            if not _ascii_pid(instruction.opcode):
                continue
            signature = ('argument_count_mismatch' if len(instruction.arguments) != 7 else
                         'empty_argument' if any(not arg.strip() for arg in instruction.arguments)
                         else 'recognized')
            occurrence = {'id': instruction.id, 'rung_id': rung.id,
                          'signature_status': signature, 'operand_ids': [],
                          'storage_status': 'signature_unresolved', 'backing_owner_id': None,
                          'content_ids': [], 'decorated_content_ids': [], 'structure_candidates': []}
            for index, reference in enumerate(bound):
                slot = SLOT_NAMES[index] if signature == 'recognized' else 'unknown'
                operand = {'id': reference['id'], 'instruction_id': instruction.id,
                           'rung_id': rung.id, 'argument_index': index, 'slot': slot,
                           'binding_status': reference['status']}
                retain(operand)
                operands.append(operand)
                occurrence['operand_ids'].append(reference['id'])
                coverage['operands_by_slot'][slot] += 1
                coverage['operands_by_binding'][reference['status']] += 1
            if signature == 'recognized':
                first = bound[0]
                if first['status'] != 'root_bound':
                    status = 'first_operand_unbound'
                elif first['target_id'] not in owners:
                    status = 'owner_not_captured'
                else:
                    owner_id = first['target_id']
                    backing_owners.add(owner_id)
                    evidence = owner_links(owner_id)
                    occurrence['backing_owner_id'] = owner_id
                    occurrence['content_ids'] = list(evidence['content_ids'])
                    occurrence['decorated_content_ids'] = list(evidence['decorated_content_ids'])
                    attrs = evidence['attributes']
                    if not evidence['namespace_supported']:
                        status = 'owner_namespace_unsupported'
                    elif (not rung_binding_supported or not all(
                            binding_provenance[entities[source_id].locator]
                            for source_id in [first['symbol_id'], *first['alias_chain'], owner_id])):
                        status = 'binding_namespace_unsupported'
                    elif first['suffix']:
                        status = 'suffix_not_empty'
                    elif not _ascii_pid(attrs.get('DataType')):
                        status = 'declaration_not_pid'
                    elif any(key.rsplit('}', 1)[-1] == 'Dimensions' for key in attrs):
                        status = 'dimensions_unmodeled'
                    elif not evidence['content_ids']:
                        status = 'no_data'
                    elif not evidence['decorated_content_ids']:
                        status = 'no_decorated_data'
                    elif not evidence['structure_candidates']:
                        status = 'no_pid_structure'
                    else:
                        status = 'linked'
                        occurrence['structure_candidates'] = [
                            {**candidate, 'member_ids': list(candidate['member_ids'])}
                            for candidate in evidence['structure_candidates']]
                occurrence['storage_status'] = status
            retain(occurrence)
            occurrences.append(occurrence)
            coverage['occurrences_by_signature'][signature] += 1
            coverage['storage_by_status'][occurrence['storage_status']] += 1
            has_owner = occurrence['backing_owner_id'] is not None
            has_data = bool(occurrence['content_ids'])
            has_decorated = bool(occurrence['decorated_content_ids'])
            for key, present in (
                ('occurrences_with_backing_owner', has_owner),
                ('occurrences_with_data', has_owner and has_data),
                ('occurrences_without_data', has_owner and not has_data),
                ('occurrences_with_opaque_only', has_data and not has_decorated),
                ('occurrences_with_multiple_representations', len(occurrence['content_ids']) > 1),
                ('occurrences_with_multiple_structures', len(occurrence['structure_candidates']) > 1),
            ):
                coverage[key] += int(present)
            coverage['representation_occurrences'] += len(occurrence['content_ids'])
            coverage['decorated_representation_occurrences'] += len(occurrence['decorated_content_ids'])
            coverage['structure_occurrences'] += len(occurrence['structure_candidates'])
            coverage['direct_member_occurrences'] += sum(
                len(candidate['member_ids']) for candidate in occurrence['structure_candidates'])
    coverage.update(source_rungs=len(inventory.rungs), source_operands=len(references.operands),
                    occurrences_total=len(occurrences), operands_total=len(operands),
                    distinct_backing_owners=len(backing_owners))
    for owner_id in backing_owners:
        evidence = owner_evidence[owner_id]
        coverage['backing_owners_with_data' if evidence['content_ids'] else
                 'backing_owners_without_data'] += 1
        coverage['backing_owners_with_opaque_only'] += int(
            bool(evidence['content_ids']) and not evidence['decorated_content_ids'])
    retain(coverage)
    partial = bool(coverage['unparsed_rungs'] or coverage['storage_by_status']['linked'] != len(occurrences))
    return PidResult(dict(inventory.snapshot), 'partial' if partial else 'complete',
                     occurrences, operands, coverage)


def analyze_pid(snapshot: SourceSnapshot, inventory: InventoryResult,
                references: ReferenceResult, tag_data: TagDataResult) -> PidResult:
    """Authenticate all source layers before deriving bounded occurrence links."""
    try:
        _check_limits(inventory, references)
        validate_tag_data(snapshot, inventory, tag_data)
        validate_references(inventory, references)
        result = _derive_pid(snapshot, inventory, references, tag_data)
        render_pid_json(result)
        return result
    except PidError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError, StopIteration):
        _invalid()


def validate_pid(snapshot: SourceSnapshot, inventory: InventoryResult,
                 references: ReferenceResult, tag_data: TagDataResult, result: PidResult) -> None:
    """Replay canonical records before copying or serializing caller evidence."""
    try:
        valid = type(result) is PidResult and _strict_match(
            analyze_pid(snapshot, inventory, references, tag_data), result)
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        valid = False
    if not valid:
        _invalid()


def render_pid_json(result: PidResult) -> str:
    """Bound private serialization; source authentication is validate_pid."""
    if type(result) is not PidResult or vars(result).keys() != set(PidResult.__dataclass_fields__):
        _invalid()
    try:
        exhausted = object()
        stack = [iter((vars(result),))]
        budget = MAX_PID_EVIDENCE_BYTES
        while stack:
            value = next(stack[-1], exhausted)
            if value is exhausted:
                stack.pop()
                continue
            budget -= 1
            if len(stack) > 12 or budget < 0:
                _invalid()
            if type(value) is dict:
                if any(type(key) is not str for key in value):
                    _invalid()
                budget -= sum(len(key.encode('utf-8')) for key in value)
                stack.append(iter(value.values()))
            elif type(value) is list:
                if len(value) > max(MAX_PID_OCCURRENCES, MAX_PID_OPERANDS):
                    _invalid()
                stack.append(iter(value))
            elif type(value) is str:
                budget -= len(value.encode('utf-8'))
            elif type(value) not in {int, type(None)}:
                _invalid()
            if budget < 0:
                _invalid()
        output = StringIO()
        size = 1
        for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, indent=2).iterencode(vars(result)):
            size += len(chunk.encode('utf-8'))
            if size > MAX_PID_JSON_BYTES:
                _invalid()
            output.write(chunk)
        output.write('\n')
        return output.getvalue()
    except PidError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
