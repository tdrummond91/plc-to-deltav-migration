"""Capture one L5X byte snapshot and inventory its source evidence.

This reader inventories declarations and outer ladder syntax. It does not resolve
symbols, infer instruction effects, classify equipment, or execute PLC logic.
All returned names, attributes and rung text are PRIVATE source data.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Any
from xml.parsers import expat

from .ladder.syntax import Branch, Instruction, RungSyntaxError, Sequence, measure, parse_rung
from .models import (
    Diagnostic, EntityRecord, InstructionRecord, InventoryResult, RungRecord, SourceSnapshot,
)

MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_ELEMENTS = 500_000
MAX_ATTRIBUTES = 2_000_000
MAX_DEPTH = 128
MAX_DIRECT_TEXT = 2_000_000


class SourceError(ValueError):
    """Fatal input diagnostic that never embeds raw source text."""


def snapshot_from_bytes(data: bytes) -> SourceSnapshot:
    if len(data) > MAX_SOURCE_BYTES:
        raise SourceError(f"Source exceeds the {MAX_SOURCE_BYTES}-byte limit.")
    frozen = bytes(data)
    digest = hashlib.sha256(frozen).hexdigest()
    return SourceSnapshot(f"sha256:{digest}", digest, len(frozen), frozen)


def capture_snapshot(path: Path) -> SourceSnapshot:
    """Read once with a bounded allocation; all subsequent analysis uses these bytes."""
    try:
        with path.open('rb') as stream:
            data = stream.read(MAX_SOURCE_BYTES + 1)
    except OSError as error:
        raise SourceError(f"Cannot read source: {error.strerror or 'file operation failed'}.") from None
    return snapshot_from_bytes(data)


@dataclass
class _Node:
    name: str
    attributes: dict[str, str]
    parent: int | None
    locator: str
    path: str
    ordinal: int
    children: list[int] = field(default_factory=list)
    text: str = ''
    parts: list[str] = field(default_factory=list)
    text_size: int = 0
    child_counts: Counter[str] = field(default_factory=Counter)


def _read_nodes(data: bytes) -> list[_Node]:
    """Build a bounded XML evidence tree, rejecting DTDs and lossy namespace joins."""
    nodes: list[_Node] = []
    stack: list[int] = []
    element_names: dict[str, str] = {}
    attribute_names: dict[tuple[str, str], str] = {}
    attribute_total = 0

    def start(expanded: str, attributes: dict[str, str]) -> None:
        nonlocal attribute_total
        if len(stack) >= MAX_DEPTH or len(nodes) >= MAX_ELEMENTS:
            raise SourceError('XML exceeds the depth or element limit.')
        attribute_total += len(attributes)
        if attribute_total > MAX_ATTRIBUTES:
            raise SourceError('XML exceeds the attribute limit.')
        name = expanded.rsplit('}', 1)[-1]
        parent_index = stack[-1] if stack else None
        parent = nodes[parent_index] if parent_index is not None else None
        path = f"{parent.path if parent else ''}/{name}"
        if element_names.setdefault(path, expanded) != expanded:
            raise SourceError('Element names collide after removing namespaces.')
        clean: dict[str, str] = {}
        for key, value in attributes.items():
            local = key.rsplit('}', 1)[-1]
            if attribute_names.setdefault((path, local), key) != key:
                raise SourceError('Attribute names collide after removing namespaces.')
            clean[local] = value
        if parent:
            parent.child_counts[name] += 1
            ordinal = parent.child_counts[name]
            parent.children.append(len(nodes))
        else:
            ordinal = 1
        locator = f"{parent.locator if parent else ''}/{name}[{ordinal}]"
        nodes.append(_Node(name, clean, parent_index, locator, path, ordinal))
        stack.append(len(nodes) - 1)

    def text(value: str) -> None:
        if stack:
            node = nodes[stack[-1]]
            node.text_size += len(value)
            if node.text_size > MAX_DIRECT_TEXT:
                raise SourceError('An XML element exceeds the direct-text limit.')
            node.parts.append(value)

    def end(_expanded: str) -> None:
        node = nodes[stack.pop()]
        node.text = ''.join(node.parts)
        node.parts.clear()

    def reject(*_args: object) -> None:
        raise SourceError('DTD and entity declarations are not allowed.')

    parser = expat.ParserCreate(namespace_separator='}')
    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.CharacterDataHandler = text
    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    try:
        # Feed captured bytes, never reopen or seek the live input file.
        for offset in range(0, len(data), 64 * 1024):
            parser.Parse(data[offset:offset + 64 * 1024], False)
        parser.Parse(b'', True)
    except expat.ExpatError as error:
        raise SourceError(f'Malformed XML at line {error.lineno}, column {error.offset}.') from None
    except (LookupError, ValueError) as error:
        if isinstance(error, SourceError):
            raise
        raise SourceError('Unsupported XML encoding or parser configuration.') from None
    if not nodes or nodes[0].name != 'RSLogix5000Content':
        raise SourceError('Expected an RSLogix5000Content document root.')
    return nodes


_ENTITY_KINDS = {
    'Controller': 'controller', 'Task': 'task', 'Program': 'program',
    'Routine': 'routine', 'Tag': 'tag', 'Module': 'module',
    'AddOnInstructionDefinition': 'aoi', 'DataType': 'data_type',
    'ScheduledProgram': 'program_schedule', 'Parameter': 'aoi_parameter',
    'LocalTag': 'aoi_local_tag', 'EncodedData': 'encoded_region',
}
_SCOPES = {'controller', 'program', 'aoi'}
# These envelopes are traversed by this slice. All other paths are accounted as
# generic preserved XML, not claimed invalid or interpreted. Exact bytes remain
# in the snapshot even when a dedicated source model has not been implemented.
_CONTAINER_PARENTS = {
    'Tasks': {'controller'}, 'Programs': {'controller'},
    'Routines': {'program', 'aoi'}, 'Tags': {'controller', 'program'},
    'Modules': {'controller'}, 'AddOnInstructionDefinitions': {'controller'},
    'DataTypes': {'controller'}, 'ScheduledPrograms': {'task'},
    'Parameters': {'aoi'}, 'LocalTags': {'aoi'}, 'Trends': {'controller', 'program'},
}
_DECLARATION_PARENTS = {
    'Controller': 'root', 'Task': 'Tasks', 'Program': 'Programs',
    'Routine': 'Routines', 'Tag': 'Tags', 'Module': 'Modules',
    'AddOnInstructionDefinition': 'AddOnInstructionDefinitions',
    'DataType': 'DataTypes', 'ScheduledProgram': 'ScheduledPrograms',
    'Parameter': 'Parameters', 'LocalTag': 'LocalTags',
}


def _entity_id(snapshot_id: str, kind: str, locator: str) -> str:
    digest = hashlib.sha256(f'{snapshot_id}\0{kind}\0{locator}'.encode('utf-8')).hexdigest()
    return f'{kind}_{digest}'


def analyze_snapshot(snapshot: SourceSnapshot) -> InventoryResult:
    """Return deterministic source records and scope-specific coverage accounting."""
    if (not isinstance(snapshot.data, bytes) or len(snapshot.data) > MAX_SOURCE_BYTES
            or snapshot.size_bytes != len(snapshot.data)
            or snapshot.sha256 != hashlib.sha256(snapshot.data).hexdigest()
            or snapshot.id != f'sha256:{snapshot.sha256}'):
        raise SourceError('Snapshot identity or byte size does not match its contents.')
    nodes = _read_nodes(snapshot.data)
    entities: list[EntityRecord] = []
    by_node: dict[int, EntityRecord] = {}
    diagnostics: list[Diagnostic] = []

    def ancestor(index: int, kinds: set[str] | None = None) -> EntityRecord | None:
        parent = nodes[index].parent
        while parent is not None:
            entity = by_node.get(parent)
            if entity and (kinds is None or entity.kind in kinds):
                return entity
            parent = nodes[parent].parent
        return None

    def diagnose(code: str, node: _Node, subject: str | None, message: str,
                 severity: str = 'warning') -> None:
        diagnostics.append(Diagnostic(code, severity, subject, node.locator, message))

    def direct_text(node: _Node, name: str, subject: str) -> str | None:
        matches = [nodes[i] for i in node.children if nodes[i].name == name]
        if matches and (len(matches) != 1 or matches[0].children):
            diagnose('descriptive_text_ambiguous', node, subject,
                     f'{name} has duplicate elements or nested XML; consult the captured source.')
        return matches[0].text if len(matches) == 1 and not matches[0].children else None

    generic_paths: Counter[str] = Counter()
    counts: Counter[str] = Counter({key: 0 for key in (
        'controllers', 'modules', 'tasks', 'programs', 'user_data_types',
        'aoi_definitions', 'trends', 'encoded_regions', 'controller_tags',
        'program_tags', 'other_tag_definitions', 'total_tag_definitions',
        'aoi_local_tags', 'aoi_parameters', 'aliases', 'routines', 'rungs', 'instructions',
    )})
    count_key = {
        'controller': 'controllers', 'module': 'modules', 'task': 'tasks',
        'program': 'programs', 'data_type': 'user_data_types', 'aoi': 'aoi_definitions',
        'encoded_region': 'encoded_regions', 'routine': 'routines',
        'aoi_local_tag': 'aoi_local_tags', 'aoi_parameter': 'aoi_parameters',
    }
    # Roles only propagate through supported parents. A familiar element name in
    # a vendor extension is evidence, not automatically a source declaration.
    roles: dict[int, str] = {0: 'root'}
    for index, node in enumerate(nodes):
        parent_role = roles.get(node.parent) if node.parent is not None else None
        kind = None
        if node.name == 'EncodedData':
            # Protection markers indicate unavailable evidence in any context.
            kind = 'encoded_region'
        elif parent_role is not None and _DECLARATION_PARENTS.get(node.name) == parent_role:
            kind = _ENTITY_KINDS[node.name]
        if node.name == 'Trend' and parent_role == 'Trends':
            counts['trends'] += 1
        if parent_role in _CONTAINER_PARENTS.get(node.name, set()):
            roles[index] = node.name
        elif node.name == 'RLLContent' and parent_role == 'routine':
            roles[index] = 'RLLContent'
        elif node.name == 'Rung' and parent_role == 'RLLContent':
            roles[index] = 'Rung'
        elif node.name in {'Text', 'Comment'} and parent_role == 'Rung':
            roles[index] = node.name
        elif node.name == 'Description' and node.parent in by_node:
            roles[index] = 'Description'
        if kind:
            roles[index] = kind
            parent = ancestor(index)
            scope = ancestor(index, _SCOPES)
            entity_id = _entity_id(snapshot.id, kind, node.locator)
            entity = EntityRecord(
                entity_id, kind,
                node.attributes.get('Name'), node.locator,
                parent.id if parent else None, scope.id if scope else None,
                dict(node.attributes), direct_text(node, 'Description', entity_id),
            )
            entities.append(entity)
            by_node[index] = entity
            if kind in count_key:
                counts[count_key[kind]] += 1
            if kind == 'tag':
                counts['total_tag_definitions'] += 1
                scope_kind = scope.kind if scope else None
                key = {'controller': 'controller_tags', 'program': 'program_tags'}.get(
                    scope_kind, 'other_tag_definitions')
                counts[key] += 1
                counts['aliases'] += int(node.attributes.get('TagType') == 'Alias')
            if kind == 'encoded_region':
                diagnose('encoded_content', node, entity.id,
                         'Encoded content is preserved in the snapshot and has not been analyzed.')
            elif not entity.name:
                diagnose('entity_name_missing', node, entity.id,
                         'An inventoried declaration or reference has no Name value.')
        elif index not in roles:
            generic_paths[node.path] += 1
            if node.name in _ENTITY_KINDS and node.name not in {'Parameter', 'LocalTag'}:
                diagnose('declaration_context_not_analyzed', node, None,
                         'Declaration-like XML is outside a supported source container; it was not inventoried.')

    if not counts['controllers']:
        diagnose('controller_context_missing', nodes[0], None,
                 'No controller envelope was found; this may be a partial export.')

    routine_types: Counter[str] = Counter()
    routine_status: dict[str, str] = {}
    for index, entity in by_node.items():
        if entity.kind != 'routine':
            continue
        node = nodes[index]
        language = entity.attributes.get('Type', '<missing>')
        routine_types[language] += 1
        contents = [nodes[i] for i in node.children if nodes[i].name.endswith('Content')]
        if language != 'RLL':
            routine_status[entity.id] = 'preserved_unsupported'
            diagnose('routine_language_not_analyzed', node, entity.id,
                     'The routine envelope is inventoried; its language content is not analyzed.', 'info')
        elif len(contents) != 1 or contents[0].name != 'RLLContent':
            routine_status[entity.id] = 'failed'
            code = 'routine_content_missing' if not contents else 'routine_content_mismatch'
            diagnose(code, node, entity.id,
                     'Expected exactly one RLLContent block in the RLL routine.', 'error')
        else:
            content = contents[0]
            unexpected = (node.text.strip() or content.text.strip()
                          or any(nodes[i].name not in {'Description', 'RLLContent'} for i in node.children)
                          or any(nodes[i].name != 'Rung' for i in content.children))
            routine_status[entity.id] = 'failed' if unexpected else 'parsed'
            if unexpected:
                diagnose('routine_content_not_analyzed', node, entity.id,
                         'Unexpected XML or direct text in an RLL routine prevents complete instruction coverage.', 'error')

    rungs: list[RungRecord] = []
    instruction_counts: Counter[str] = Counter()
    rung_dispositions: Counter[str] = Counter({key: 0 for key in (
        'encountered', 'parsed', 'failed', 'preserved_unsupported', 'excluded',
    )})
    for index, node in enumerate(nodes):
        if node.name != 'Rung':
            continue
        rung_dispositions['encountered'] += 1
        counts['rungs'] += 1
        parent = ancestor(index, {'routine'})
        scope = ancestor(index, _SCOPES)
        rung_id = _entity_id(snapshot.id, 'rung', node.locator)
        texts = [nodes[i] for i in node.children if nodes[i].name == 'Text']
        text = texts[0].text if len(texts) == 1 and not texts[0].children else None
        metrics: dict[str, int] = {}
        instructions: list[InstructionRecord] = []
        structure: dict[str, Any] | None = None
        parent_node = nodes[node.parent] if node.parent is not None else None
        valid_context = (roles.get(index) == 'Rung'
                         and parent_node is not None and parent_node.name == 'RLLContent'
                         and parent is not None and parent.attributes.get('Type') == 'RLL')
        if not valid_context:
            disposition = 'preserved_unsupported'
            diagnose('rung_context_not_analyzed', node, rung_id,
                     'Rung is outside a declared RLL routine content block.', 'info')
        elif node.text.strip() or any(nodes[i].name not in {'Text', 'Comment'} for i in node.children):
            disposition = 'failed'
            diagnose('rung_content_not_analyzed', node, rung_id,
                     'Unexpected XML or direct text in the rung is preserved but not analyzed.', 'error')
        elif text is None:
            disposition = 'failed'
            diagnose('rung_text_unavailable', node, rung_id,
                     'Expected exactly one Text child without nested XML.', 'error')
        else:
            try:
                tree = parse_rung(text)
            except RungSyntaxError as error:
                disposition = 'failed'
                diagnose(error.code, node, rung_id,
                         f'Outer ladder parsing failed at character offset {error.offset}.', 'error')
            else:
                disposition = 'parsed'
                metrics = measure(tree)

                def describe(sequence: Sequence) -> dict[str, Any]:
                    items: list[dict[str, Any]] = []
                    for item in sequence.items:
                        if isinstance(item, Instruction):
                            assert item.start is not None and item.end is not None
                            inst_id = _entity_id(snapshot.id, 'instruction',
                                                 f'{node.locator}/instruction[{len(instructions) + 1}]')
                            instructions.append(InstructionRecord(
                                inst_id, item.opcode, item.arguments, item.start, item.end))
                            instruction_counts[item.opcode] += 1
                            items.append({'kind': 'instruction', 'instruction_id': inst_id})
                        elif isinstance(item, Branch):
                            items.append({'kind': 'branch', 'legs': [describe(leg) for leg in item.legs]})
                    return {'kind': 'sequence', 'items': items}

                structure = describe(tree)
                counts['instructions'] += len(instructions)
        if valid_context and (not node.attributes.get('Number') or not node.attributes.get('Type')):
            diagnose('rung_metadata_missing', node, rung_id,
                     'Rung Number or Type is missing; source ordinal still identifies this record.')
        if parent and parent.id in routine_status and disposition != 'parsed':
            if routine_status[parent.id] == 'parsed':
                routine_status[parent.id] = 'failed'
        rung_dispositions[disposition] += 1
        rungs.append(RungRecord(
            rung_id, node.locator, parent.id if parent else None, scope.id if scope else None,
            node.ordinal, node.attributes.get('Number'), node.attributes.get('Type'),
            text, direct_text(node, 'Comment', rung_id), disposition, metrics, instructions, structure,
        ))

    routine_dispositions = Counter({key: 0 for key in ('parsed', 'failed', 'preserved_unsupported')})
    routine_dispositions.update(routine_status.values())
    complete_instructions = not (rung_dispositions['failed'] or rung_dispositions['preserved_unsupported']
                                 or routine_dispositions['failed'] or routine_dispositions['preserved_unsupported']
                                 or counts['encoded_regions'])
    # Completeness refers to this structural slice, never to engineering semantics.
    partial = not complete_instructions or any(d.severity in {'warning', 'error'} for d in diagnostics)
    return InventoryResult(
        snapshot={'id': snapshot.id, 'sha256': snapshot.sha256, 'size_bytes': snapshot.size_bytes},
        export_attributes=dict(nodes[0].attributes), entities=entities, rungs=rungs,
        diagnostics=diagnostics, counts=dict(counts), routine_types=dict(routine_types),
        instruction_counts=dict(instruction_counts), status='partial' if partial else 'complete',
        coverage={
            'xml_elements': len(nodes), 'routines': {'encountered': counts['routines'], **routine_dispositions},
            'rungs': dict(rung_dispositions), 'instruction_count_complete': complete_instructions,
            'instruction_count_scope': 'successfully_parsed_RLL_rungs_only',
            'unmodeled_xml_paths': [{'path': path, 'count': count} for path, count in sorted(generic_paths.items())],
            'unmodeled_xml_policy': 'Preserved in original snapshot; no dedicated interpretation in this slice.',
            'attribute_policy': 'Entity attributes retained as source facts; values and references are not validated.',
            'semantics': 'Instruction effects, references, classifications and execution behavior are not analyzed.',
        },
    )
