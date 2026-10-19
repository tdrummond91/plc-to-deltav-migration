"""Bounded snapshot-bound Data/DefaultData evidence, without value interpretation.

Parsed XML attributes and direct text are preserved, not byte-exact XML syntax.
The snapshot retains CDATA, escaping and comments. Formats and repeated records
stay separate: this reader never chooses effective values or validates members.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, fields, is_dataclass
import hashlib
from io import StringIO
import json
from typing import Any

from .models import InventoryResult, SourceSnapshot
from .source import MAX_SOURCE_BYTES, _entity_id, _read_nodes, analyze_snapshot

MAX_TAG_DATA_OWNERS = 100_000
MAX_TAG_DATA_CONTENTS = 100_000
MAX_TAG_DATA_ELEMENTS = 250_000
MAX_TAG_DATA_ISSUES = 500_000
MAX_TAG_DATA_EVIDENCE_BYTES = 32 * 1024 * 1024
MAX_TAG_DATA_JSON_BYTES = 64 * 1024 * 1024
OWNER_KINDS = frozenset({'tag', 'aoi_parameter', 'aoi_local_tag',
                         'module_input_tag', 'module_output_tag', 'module_config_tag'})
ENVELOPE_KINDS = frozenset({'Data', 'DefaultData'})
FORMAT_KINDS = frozenset({'decorated', 'string', 'l5k', 'raw', 'missing', 'other'})
ELEMENT_KINDS = frozenset({'data_value', 'structure', 'array', 'data_value_member',
                           'structure_member', 'array_member', 'element', 'opaque', 'unmodeled'})
DUPLICATE_KINDS = frozenset({'content', 'member', 'element', 'root'})
ISSUE_CODES = frozenset({'format_unsupported', 'namespace_unmodeled', 'shape_unmodeled',
                         'unexpected_direct_text', 'content_empty', 'duplicate_content',
                         'duplicate_member', 'duplicate_element', 'duplicate_root'})
TAG_DATA_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'tag-data-1',
    'analysis_scope': 'tag_data_evidence', 'value_analysis': 'not_implemented',
    'effective_value_selection': 'not_implemented', 'member_validation': 'not_implemented',
}
COVERAGE_KEYS = frozenset({
    'owners_total', 'owners_by_kind', 'owners_with_data', 'owners_without_data',
    'contents_total', 'contents_by_envelope', 'contents_by_format',
    'elements_total', 'elements_by_kind', 'duplicate_groups', 'duplicate_records',
    'issues_total', 'issues_by_code', 'source_xml_elements', 'direct_text_bytes',
    'attribute_pairs', 'contents_with_text', 'elements_with_text',
})
_ROOT_KINDS = frozenset({'data_value', 'structure', 'array'})
_MEMBER_KINDS = frozenset({'data_value_member', 'structure_member', 'array_member'})
_KINDS = {'DataValue': 'data_value', 'Structure': 'structure', 'Array': 'array',
          'DataValueMember': 'data_value_member', 'StructureMember': 'structure_member',
          'ArrayMember': 'array_member', 'Element': 'element'}


class TagDataError(ValueError):
    """Fixed source-free rejection of inconsistent or excessive evidence."""


@dataclass(frozen=True)
class TagDataResult:
    snapshot: dict[str, str | int]
    status: str
    owners: list[dict[str, Any]]
    contents: list[dict[str, Any]]
    elements: list[dict[str, Any]]
    issues: list[dict[str, str]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'tag-data-1'
    analysis_scope: str = 'tag_data_evidence'
    value_analysis: str = 'not_implemented'
    effective_value_selection: str = 'not_implemented'
    member_validation: str = 'not_implemented'

    def to_dict(self) -> dict[str, Any]:
        """Return private evidence, including stored values; never publish."""
        return asdict(self)


def _fail() -> None:
    raise TagDataError('Tag-data evidence is inconsistent or exceeds its limits.') from None


def _strict_match(expected: Any, actual: Any) -> bool:
    """Follow only canonical bounded containers, never copy an untrusted tree."""
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


def _namespace(name: str) -> str | None:
    return name.rsplit('}', 1)[0] if '}' in name else None


def _format(attributes: dict[str, str]) -> str:
    value = attributes.get('Format')
    return ({'Decorated': 'decorated', 'String': 'string', 'L5K': 'l5k', 'Raw': 'raw'}.get(value)
            or ('missing' if value is None else 'other'))


def _element_kind(node: Any, parent_kind: str | None, root_namespace: str | None) -> str:
    """Recognize small lexical shapes, not a Logix schema or valid member path."""
    if _namespace(node.expanded_name) != root_namespace:
        return 'unmodeled'
    kind = _KINDS.get(node.name, 'unmodeled')
    parents = {
        'data_value': {None}, 'structure': {None, 'element'}, 'array': {None, 'element'},
        'data_value_member': {'structure', 'structure_member'},
        'structure_member': {'structure', 'structure_member'},
        'array_member': {'structure', 'structure_member'},
        'element': {'array', 'array_member'},
    }
    if parent_kind not in parents.get(kind, set()):
        return 'unmodeled'
    attributes = node.expanded_attributes
    if kind in _MEMBER_KINDS and not attributes.get('Name'):
        return 'unmodeled'
    if kind in {'data_value', 'data_value_member'} and ('Value' not in attributes or node.children):
        return 'unmodeled'
    if kind == 'element' and (not attributes.get('Index')
                              or ('Value' in attributes and bool(node.children))
                              or ('Value' not in attributes and len(node.children) != 1)):
        return 'unmodeled'
    return kind


def analyze_tag_data(snapshot: SourceSnapshot, inventory: InventoryResult) -> TagDataResult:
    """Authenticate the complete inventory and capture eligible direct envelopes."""
    try:
        if (type(snapshot) is not SourceSnapshot or type(inventory) is not InventoryResult
                or vars(snapshot).keys() != set(SourceSnapshot.__dataclass_fields__)
                or type(snapshot.data) is not bytes or len(snapshot.data) > MAX_SOURCE_BYTES
                or type(snapshot.size_bytes) is not int or snapshot.size_bytes != len(snapshot.data)
                or type(snapshot.sha256) is not str or type(snapshot.id) is not str
                or snapshot.sha256 != hashlib.sha256(snapshot.data).hexdigest()
                or snapshot.id != f'sha256:{snapshot.sha256}'):
            _fail()
        if not _strict_match(analyze_snapshot(snapshot), inventory):
            _fail()
        result = _capture(snapshot, inventory)
        render_tag_data_json(result)
        return result
    except TagDataError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _fail()


def _capture(snapshot: SourceSnapshot, inventory: InventoryResult) -> TagDataResult:
    nodes = _read_nodes(snapshot.data)
    root_namespace = _namespace(nodes[0].expanded_name)
    by_locator = {node.locator: node for node in nodes}
    owners: list[dict[str, Any]] = []
    contents: list[dict[str, Any]] = []
    elements: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    groups: dict[str, dict[Any, list[dict[str, Any]]]] = {
        kind: defaultdict(list) for kind in DUPLICATE_KINDS}
    retained = 0

    def retain(row: Any) -> None:
        nonlocal retained
        pending = [row]
        while pending:
            value = pending.pop()
            if type(value) is str:
                retained += len(value.encode('utf-8'))
            elif type(value) is dict:
                pending.extend(value.keys())
                pending.extend(value.values())
            elif type(value) is list:
                pending.extend(value)
            if retained > MAX_TAG_DATA_EVIDENCE_BYTES:
                _fail()

    def issue(code: str, row: dict[str, Any], content_id: str) -> None:
        if len(issues) >= MAX_TAG_DATA_ISSUES:
            _fail()
        record = {'code': code, 'source_id': row['id'],
                  'owner_id': row['owner_id'], 'content_id': content_id}
        retain(record)
        issues.append(record)

    for owner in inventory.entities:
        if owner.kind not in OWNER_KINDS:
            continue
        if len(owners) >= MAX_TAG_DATA_OWNERS:
            _fail()
        owner_node = by_locator[owner.locator]
        owner_row = {'source_id': owner.id, 'kind': owner.kind, 'content_ids': []}
        owners.append(owner_row)
        for index in owner_node.children:
            node = nodes[index]
            if node.name not in ENVELOPE_KINDS:
                continue
            if len(contents) >= MAX_TAG_DATA_CONTENTS:
                _fail()
            content_id = _entity_id(snapshot.id, 'tag_data_content', node.locator)
            content = {'id': content_id, 'owner_id': owner.id, 'xml_name': node.name,
                       'xml_namespace': _namespace(node.expanded_name), 'locator': node.locator,
                       'attributes': dict(node.expanded_attributes), 'direct_text': node.text,
                       'format_kind': _format(node.expanded_attributes)}
            owner_row['content_ids'].append(content_id)
            contents.append(content)
            retain(content)
            # Namespace is part of a representation's identity; unfamiliar
            # names cannot collapse into an ordinary Data/Format declaration.
            groups['content'][(owner.id, node.expanded_name, node.expanded_attributes.get('Format'))].append(content)
            namespace_supported = (content['xml_namespace'] == root_namespace
                                   and _namespace(owner_node.expanded_name) == root_namespace)
            if not namespace_supported:
                issue('namespace_unmodeled', content, content_id)
            decorated = namespace_supported and content['format_kind'] == 'decorated'
            if content['format_kind'] not in {'decorated', 'string'}:
                issue('format_unsupported', content, content_id)
            if decorated and not node.children:
                issue('content_empty', content, content_id)
            if decorated and node.text.strip():
                issue('unexpected_direct_text', content, content_id)
            context: dict[int, tuple[str, str | None]] = {}
            pending = list(reversed(node.children))
            while pending:
                child_index = pending.pop()
                child = nodes[child_index]
                if len(elements) >= MAX_TAG_DATA_ELEMENTS:
                    _fail()
                parent_id, parent_kind = context.get(child.parent, (content_id, None))
                kind = (_element_kind(child, parent_kind, root_namespace) if decorated else
                        'unmodeled' if namespace_supported and content['format_kind'] == 'string' else 'opaque')
                element_id = _entity_id(snapshot.id, 'tag_data_element', child.locator)
                element = {'id': element_id, 'owner_id': owner.id, 'content_id': content_id,
                           'parent_id': parent_id, 'xml_name': child.name,
                           'xml_namespace': _namespace(child.expanded_name), 'ordinal': child.ordinal,
                           'kind': kind, 'attributes': dict(child.expanded_attributes), 'direct_text': child.text}
                context[child_index] = (element_id, kind)
                elements.append(element)
                retain(element)
                if kind == 'unmodeled':
                    issue('shape_unmodeled', element, content_id)
                if decorated and child.text.strip():
                    issue('unexpected_direct_text', element, content_id)
                if kind in _ROOT_KINDS and parent_id == content_id:
                    groups['root'][content_id].append(element)
                if kind in _MEMBER_KINDS:
                    groups['member'][(content_id, parent_id, child.expanded_attributes['Name'])].append(element)
                if kind == 'element':
                    groups['element'][(content_id, parent_id, child.expanded_attributes['Index'])].append(element)
                pending.extend(reversed(child.children))
        retain(owner_row)
    duplicate_groups = dict.fromkeys(sorted(DUPLICATE_KINDS), 0)
    duplicate_records = dict.fromkeys(sorted(DUPLICATE_KINDS), 0)
    for kind in sorted(DUPLICATE_KINDS):
        for members in groups[kind].values():
            if len(members) < 2:
                continue
            duplicate_groups[kind] += 1
            duplicate_records[kind] += len(members)
            for row in members:
                issue(f'duplicate_{kind}', row, row['id'] if kind == 'content' else row['content_id'])

    def tally(rows: list[dict[str, Any]], key: str, vocabulary: frozenset[str]) -> dict[str, int]:
        counts = dict.fromkeys(sorted(vocabulary), 0)
        for row in rows:
            counts[row[key]] += 1
        return counts

    records = [*contents, *elements]
    with_data = sum(bool(row['content_ids']) for row in owners)
    coverage = {
        'owners_total': len(owners), 'owners_by_kind': tally(owners, 'kind', OWNER_KINDS),
        'owners_with_data': with_data, 'owners_without_data': len(owners) - with_data,
        'contents_total': len(contents), 'contents_by_envelope': tally(contents, 'xml_name', ENVELOPE_KINDS),
        'contents_by_format': tally(contents, 'format_kind', FORMAT_KINDS),
        'elements_total': len(elements), 'elements_by_kind': tally(elements, 'kind', ELEMENT_KINDS),
        'duplicate_groups': duplicate_groups, 'duplicate_records': duplicate_records,
        'issues_total': len(issues), 'issues_by_code': tally(issues, 'code', ISSUE_CODES),
        'source_xml_elements': len(nodes),
        'direct_text_bytes': sum(len(row['direct_text'].encode('utf-8')) for row in records),
        'attribute_pairs': sum(len(row['attributes']) for row in records),
        'contents_with_text': sum(bool(row['direct_text']) for row in contents),
        'elements_with_text': sum(bool(row['direct_text']) for row in elements),
    }
    retain(coverage)
    return TagDataResult(dict(inventory.snapshot), 'partial' if issues else 'complete',
                         owners, contents, elements, issues, coverage)


def validate_tag_data(snapshot: SourceSnapshot, inventory: InventoryResult, result: TagDataResult) -> None:
    """Replay source-bound evidence before copying/serializing caller records."""
    try:
        valid = type(result) is TagDataResult and _strict_match(analyze_tag_data(snapshot, inventory), result)
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        valid = False
    if not valid:
        _fail()


def render_tag_data_json(result: TagDataResult) -> str:
    """Render bounded private JSON; canonical validation requires snapshot/inventory."""
    if type(result) is not TagDataResult or vars(result).keys() != set(TagDataResult.__dataclass_fields__):
        _fail()
    try:
        exhausted = object()
        stack = [iter((vars(result),))]
        budget = MAX_TAG_DATA_JSON_BYTES
        while stack:
            value = next(stack[-1], exhausted)
            if value is exhausted:
                stack.pop()
                continue
            budget -= 1
            if len(stack) > 12 or budget < 0:
                _fail()
            if type(value) is dict:
                if any(type(key) is not str for key in value):
                    _fail()
                budget -= sum(len(key.encode('utf-8')) for key in value)
                stack.append(iter(value.values()))
            elif type(value) is list:
                if len(value) > max(MAX_TAG_DATA_OWNERS, MAX_TAG_DATA_CONTENTS,
                                    MAX_TAG_DATA_ELEMENTS, MAX_TAG_DATA_ISSUES):
                    _fail()
                stack.append(iter(value))
            elif type(value) is str:
                budget -= len(value.encode('utf-8'))
            elif type(value) not in {int, type(None)}:
                _fail()
            if budget < 0:
                _fail()
        output = StringIO()
        size = 1
        for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, indent=2).iterencode(vars(result)):
            size += len(chunk.encode('utf-8'))
            if size > MAX_TAG_DATA_JSON_BYTES:
                _fail()
            output.write(chunk)
        output.write('\n')
        return output.getvalue()
    except TagDataError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _fail()
