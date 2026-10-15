"""Private, bounded capture of SFC XML structure from an immutable L5X snapshot.

Links describe XML ID references only. This slice never interprets action or
transition code, selects an edit revision, or claims controller execution.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any

from .models import EntityRecord, InventoryResult, SourceSnapshot
from .source import MAX_SOURCE_BYTES, SourceError, _entity_id, _read_nodes

MAX_SFC_ELEMENTS = 100_000
MAX_SFC_CONTENTS = 10_000
MAX_SFC_LINKS = 100_000
MAX_SFC_EVIDENCE_CHARS = 8_000_000
MAX_SFC_ID_LENGTH = 65_536
SFC_ELEMENT_KINDS = frozenset({
    'step', 'transition', 'branch', 'leg', 'sbr_ret', 'stop', 'action',
    'action_list', 'directed_link', 'text_box', 'attachment', 'preset',
    'limit_high', 'limit_low', 'body', 'condition', 'st_content', 'st_line',
    'description', 'unmodeled',
})
SFC_EDIT_KINDS = frozenset({'absent', 'empty', 'Original', 'PendingEdits', 'TestEdits', 'other'})
SFC_BLOCK_ID_STATUSES = frozenset({'missing', 'invalid', 'valid'})
SFC_ENDPOINT_STATUSES = frozenset({
    'resolved', 'missing_attribute', 'invalid_id', 'missing_target',
    'ambiguous_target', 'unsupported_kind',
})
SFC_ISSUE_CODES = frozenset({
    'content_missing', 'protection_present', 'edit_kind_unmodeled',
    'element_unmodeled', 'unexpected_direct_text', 'block_id_missing',
    'block_id_invalid', 'block_id_duplicate', 'link_endpoint_unresolved',
    'routine_content_unmodeled',
})
ELEMENT_KINDS = SFC_ELEMENT_KINDS
EDIT_KINDS = SFC_EDIT_KINDS
BLOCK_ID_STATUSES = SFC_BLOCK_ID_STATUSES
ENDPOINT_STATUSES = SFC_ENDPOINT_STATUSES
ISSUE_CODES = SFC_ISSUE_CODES
_KINDS = {
    'Step': 'step', 'Transition': 'transition', 'Branch': 'branch', 'Leg': 'leg',
    'SbrRet': 'sbr_ret', 'Stop': 'stop', 'Action': 'action', 'ActionList': 'action_list',
    'DirectedLink': 'directed_link', 'TextBox': 'text_box', 'Attachment': 'attachment',
    'Preset': 'preset', 'LimitHigh': 'limit_high', 'LimitLow': 'limit_low',
    'Body': 'body', 'Condition': 'condition', 'STContent': 'st_content',
    'Line': 'st_line', 'Description': 'description',
}
_TOP = frozenset({'Step', 'Transition', 'Branch', 'SbrRet', 'Stop', 'DirectedLink', 'TextBox', 'Attachment'})
_BLOCKS = frozenset({'step', 'transition', 'branch', 'leg', 'sbr_ret', 'stop', 'action', 'text_box'})
_FLOW = frozenset({'step', 'transition', 'branch', 'leg', 'sbr_ret', 'stop'})
_OPAQUE_TEXT = frozenset({'preset', 'limit_high', 'limit_low', 'body', 'condition', 'st_content', 'st_line', 'description'})
_PROTECTION = frozenset({'EncodedData', 'EncryptedContent', 'EncryptedSegments'})
_DECIMAL = re.compile(r'[0-9]+', re.ASCII)


class SfcStructureError(ValueError):
    """Fatal error with a fixed message that does not expose source evidence."""


@dataclass(frozen=True)
class SfcStructureResult:
    snapshot: dict[str, str | int]
    routines: list[dict[str, Any]]
    contents: list[dict[str, Any]]
    elements: list[dict[str, Any]]
    links: list[dict[str, Any]]
    issues: list[dict[str, str]]
    status: str
    schema_version: int = 1
    analyzer_version: str = 'sfc-structure-1'
    analysis_scope: str = 'sfc_structure_only'
    semantic_analysis: str = 'not_implemented'

    def to_dict(self) -> dict[str, Any]:
        """Return private evidence; callers must not publish these records."""
        return asdict(self)


def _fail() -> None:
    raise SfcStructureError('SFC structure evidence is inconsistent or exceeds its limits.')


def _canonical_id(value: str | None) -> tuple[str, str | None]:
    if value is None:
        return 'missing', None
    if len(value) > MAX_SFC_ID_LENGTH:
        _fail()
    if not _DECIMAL.fullmatch(value):
        return 'invalid', None
    canonical = value.lstrip('0') or '0'
    # Lexical comparison avoids int conversion and its huge-decimal limits.
    if len(canonical) > 10 or (len(canonical) == 10 and canonical > '4294967295'):
        return 'invalid', None
    return 'valid', canonical


def _kind(name: str, parent_kind: str | None) -> str:
    if parent_kind is None and name in _TOP:
        return _KINDS[name]
    parents = {
        'Leg': {'branch'}, 'Action': {'step', 'action_list'}, 'ActionList': {'step'},
        'Preset': {'step', 'action'}, 'LimitHigh': {'step'}, 'LimitLow': {'step'},
        'Body': {'action'}, 'Condition': {'transition'},
        'STContent': {'preset', 'limit_high', 'limit_low', 'body', 'condition'},
        'Line': {'st_content'},
    }
    if parent_kind in parents.get(name, set()):
        return _KINDS[name]
    if name == 'Description' and parent_kind not in {None, 'unmodeled', 'st_line', 'description'}:
        return 'description'
    return 'unmodeled'


def analyze_sfc_structure(snapshot: SourceSnapshot, inventory: InventoryResult) -> SfcStructureResult:
    """Capture all canonical SFC routines without rereading the live source path."""
    if type(snapshot) is not SourceSnapshot or type(inventory) is not InventoryResult:
        _fail()
    if (type(snapshot.id) is not str or type(snapshot.sha256) is not str
            or type(snapshot.data) is not bytes or len(snapshot.data) > MAX_SOURCE_BYTES
            or type(snapshot.size_bytes) is not int or snapshot.size_bytes != len(snapshot.data)
            or snapshot.sha256 != hashlib.sha256(snapshot.data).hexdigest()
            or snapshot.id != f'sha256:{snapshot.sha256}'):
        _fail()
    identity = {'id': snapshot.id, 'sha256': snapshot.sha256, 'size_bytes': snapshot.size_bytes}
    if not _strict_equal(identity, inventory.snapshot):
        _fail()
    try:
        nodes = _read_nodes(snapshot.data)
    except SourceError:
        _fail()
    # Reconstruct supported declaration ownership, not familiar names hidden in
    # arbitrary vendor wrappers. Compare every routine envelope, including RLL.
    roles: dict[int, str] = {0: 'root'}
    declarations: dict[str, tuple[int, str, str | None, str | None]] = {}
    owner_by_node: dict[int, str] = {}
    containers = {'Programs': {'controller'}, 'AddOnInstructionDefinitions': {'controller'},
                  'Routines': {'program', 'aoi'}}
    declared = {'Controller': ('root', 'controller'), 'Program': ('Programs', 'program'),
                'AddOnInstructionDefinition': ('AddOnInstructionDefinitions', 'aoi'),
                'Routine': ('Routines', 'routine')}
    for index, node in enumerate(nodes):
        parent_role = roles.get(node.parent)
        if parent_role in containers.get(node.name, set()):
            roles[index] = node.name
        rule = declared.get(node.name)
        if rule is None or parent_role != rule[0]:
            continue
        kind = rule[1]
        roles[index] = kind
        parent_index = node.parent
        while parent_index is not None and parent_index not in owner_by_node:
            parent_index = nodes[parent_index].parent
        parent_id = owner_by_node.get(parent_index)
        entity_id = _entity_id(snapshot.id, kind, node.locator)
        scope_id = parent_id
        declarations[entity_id] = (index, kind, parent_id, scope_id)
        owner_by_node[index] = entity_id
    if type(inventory.entities) is not list or any(type(e) is not EntityRecord for e in inventory.entities):
        _fail()
    relevant = [e for e in inventory.entities if e.kind in {'controller', 'program', 'aoi', 'routine'}]
    if len(relevant) != len(declarations) or len({e.id for e in relevant}) != len(relevant):
        _fail()
    for entity in relevant:
        record = declarations.get(entity.id)
        if record is None:
            _fail()
        index, kind, parent_id, scope_id = record
        node = nodes[index]
        if (entity.kind != kind or entity.locator != node.locator or entity.parent_id != parent_id
                or entity.scope_id != scope_id or entity.name != node.attributes.get('Name')
                or not _strict_equal(node.attributes, entity.attributes)):
            _fail()
    routines: list[dict[str, Any]] = []
    contents: list[dict[str, Any]] = []
    elements: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    retained = 0

    def retain(value: Any) -> None:
        nonlocal retained
        pending = [value]
        while pending:
            item = pending.pop()
            if type(item) is str:
                retained += len(item)
            elif type(item) is dict:
                pending.extend(item.keys())
                pending.extend(item.values())
            elif type(item) is list:
                pending.extend(item)
            if retained > MAX_SFC_EVIDENCE_CHARS:
                _fail()

    def issue(code: str, source_id: str) -> None:
        row = {'code': code, 'source_id': source_id}
        retain(row)
        issues.append(row)

    for entity in relevant:
        if entity.kind != 'routine' or entity.attributes.get('Type') != 'SFC':
            continue
        routine_index = declarations[entity.id][0]
        content_indices = [i for i in nodes[routine_index].children if nodes[i].name == 'SFCContent']
        markers = []
        pending = list(reversed(nodes[routine_index].children))
        while pending:
            index = pending.pop()
            node = nodes[index]
            if node.name in _PROTECTION:
                markers.append({'xml_name': node.name, 'locator': node.locator})
            pending.extend(reversed(node.children))
        unmodeled_children = [
            {'xml_name': nodes[i].name, 'locator': nodes[i].locator}
            for i in nodes[routine_index].children
            if nodes[i].name not in {'SFCContent', 'Description', 'EncryptionInfo', *_PROTECTION}
        ]
        routine_row = {'routine_id': entity.id, 'scope_id': entity.scope_id,
                       'content_ids': [], 'protection_markers': markers,
                       'unmodeled_children': unmodeled_children,
                       'direct_text': nodes[routine_index].text}
        if unmodeled_children or nodes[routine_index].text.strip():
            issue('routine_content_unmodeled', entity.id)
        if not content_indices:
            issue('content_missing', entity.id)
        if markers:
            issue('protection_present', entity.id)
        for content_index in content_indices:
            if len(contents) >= MAX_SFC_CONTENTS:
                _fail()
            content = nodes[content_index]
            content_id = _entity_id(snapshot.id, 'sfc_content', content.locator)
            routine_row['content_ids'].append(content_id)
            edit_value = content.attributes.get('OnlineEditType')
            edit_kind = ('absent' if edit_value is None else 'empty' if edit_value == '' else
                         edit_value if edit_value in {'Original', 'PendingEdits', 'TestEdits'} else 'other')
            content_row = {'id': content_id, 'routine_id': entity.id, 'locator': content.locator,
                           'attributes': dict(content.attributes), 'edit_kind': edit_kind,
                           'direct_text': content.text}
            retain(content_row)
            contents.append(content_row)
            if edit_kind in {'empty', 'other'}:
                issue('edit_kind_unmodeled', content_id)
            if content.text.strip():
                issue('unexpected_direct_text', content_id)
            block_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
            content_links: list[dict[str, Any]] = []
            pending = [(i, None, None) for i in reversed(content.children)]
            while pending:
                index, parent_id, parent_kind = pending.pop()
                node = nodes[index]
                if len(elements) >= MAX_SFC_ELEMENTS:
                    _fail()
                kind = _kind(node.name, parent_kind)
                element_id = _entity_id(snapshot.id, 'sfc_element', node.locator)
                block_status, canonical_id = (None, None)
                if kind in _BLOCKS or 'ID' in node.attributes:
                    block_status, canonical_id = _canonical_id(node.attributes.get('ID'))
                row = {'id': element_id, 'content_id': content_id, 'routine_id': entity.id,
                       'parent_id': parent_id, 'locator': node.locator, 'xml_name': node.name,
                       'kind': kind, 'attributes': dict(node.attributes), 'direct_text': node.text,
                       'block_id_status': block_status, 'canonical_id': canonical_id}
                retain(row)
                elements.append(row)
                if kind == 'unmodeled':
                    issue('element_unmodeled', element_id)
                if node.text.strip() and kind not in _OPAQUE_TEXT and kind != 'unmodeled':
                    issue('unexpected_direct_text', element_id)
                if block_status in {'missing', 'invalid'}:
                    issue(f'block_id_{block_status}', element_id)
                if canonical_id is not None:
                    block_index[canonical_id].append(row)
                if kind == 'directed_link':
                    if len(links) + len(content_links) >= MAX_SFC_LINKS:
                        _fail()
                    content_links.append(row)
                pending.extend((i, element_id, kind) for i in reversed(node.children))
            for candidates in block_index.values():
                if len(candidates) > 1:
                    for candidate in candidates:
                        issue('block_id_duplicate', candidate['id'])
            for row in content_links:
                link = {'element_id': row['id'], 'content_id': content_id}
                for side, attribute in (('from', 'FromID'), ('to', 'ToID')):
                    id_status, canonical_id = _canonical_id(row['attributes'].get(attribute))
                    candidates = block_index.get(canonical_id, [])
                    status = ('missing_attribute' if id_status == 'missing' else
                              'invalid_id' if id_status == 'invalid' else
                              'missing_target' if not candidates else
                              'ambiguous_target' if len(candidates) > 1 else
                              'unsupported_kind' if candidates[0]['kind'] not in _FLOW else 'resolved')
                    link[f'{side}_status'] = status
                    link[f'{side}_element_id'] = candidates[0]['id'] if status == 'resolved' else None
                    if status != 'resolved':
                        issue('link_endpoint_unresolved', row['id'])
                retain(link)
                links.append(link)
        retain(routine_row)
        routines.append(routine_row)
    result = SfcStructureResult(identity, routines, contents, elements, links, issues,
                                'partial' if issues else 'complete')
    # Top-level keys, snapshot identity and fixed metadata also contribute to
    # the serialized evidence budget. Child records were charged as built.
    retain({**vars(result), 'routines': [], 'contents': [], 'elements': [],
            'links': [], 'issues': []})
    return result


def _strict_equal(expected: Any, actual: Any) -> bool:
    """Walk the bounded expected shape without serializing candidate containers."""
    pending = [(expected, actual)]
    while pending:
        a, b = pending.pop()
        if type(a) is not type(b):
            return False
        if type(a) is dict:
            if len(a) != len(b) or any(type(key) is not str for key in b) or a.keys() != b.keys():
                return False
            pending.extend((a[key], b[key]) for key in a)
        elif type(a) is list:
            if len(a) != len(b):
                return False
            pending.extend(zip(a, b))
        elif type(a) not in {str, int, bool, type(None)} or a != b:
            return False
    return True


def validate_sfc_structure(snapshot: SourceSnapshot, inventory: InventoryResult,
                           result: SfcStructureResult) -> None:
    """Reject alterations by strict canonical replay over the captured bytes."""
    try:
        valid = (type(result) is SfcStructureResult
                 and _strict_equal(vars(analyze_sfc_structure(snapshot, inventory)), vars(result)))
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError):
        valid = False
    if not valid:
        _fail()


def render_sfc_json(result: SfcStructureResult) -> str:
    """Render PRIVATE source-bearing JSON."""
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + '\n'


def render_sfc_text(result: SfcStructureResult, *, inventory: InventoryResult | None = None) -> str:
    """Render PRIVATE structural evidence without selecting an active edit."""
    labels = {} if inventory is None else {e.id: e.name for e in inventory.entities}
    lines = ['PRIVATE SFC structure', f'Status: {result.status}',
             'Structure only; execution and ST semantics are not implemented.',
             'Content edit versions remain separate; no active version is selected.']
    contents = defaultdict(list)
    elements = defaultdict(list)
    links = defaultdict(list)
    for row in result.contents:
        contents[row['routine_id']].append(row)
    for row in result.elements:
        elements[row['content_id']].append(row)
    for row in result.links:
        links[row['content_id']].append(row)
    for routine in result.routines:
        routine_id = routine['routine_id']
        lines.append(f'Routine: {labels.get(routine_id) or routine_id} [{routine_id}]')
        for marker in routine['protection_markers']:
            lines.append(f'  Protection: {marker["xml_name"]} {marker["locator"]}')
        for marker in routine['unmodeled_children']:
            lines.append(f'  Unmodeled routine child: {marker["xml_name"]} {marker["locator"]}')
        if routine['direct_text'].strip():
            lines.append(f'  Unmodeled routine text: {json.dumps(routine["direct_text"], ensure_ascii=False)}')
        for content in contents[routine_id]:
            lines.append(f'  Content: {content["id"]} edit={content["edit_kind"]}')
            lines.append(f'    Attributes: {json.dumps(content["attributes"], ensure_ascii=False)}')
            if content['direct_text'].strip():
                lines.append(f'    Direct text: {json.dumps(content["direct_text"], ensure_ascii=False)}')
            for element in elements[content['id']]:
                lines.append(f'    {element["kind"]}: {element["id"]} '
                             f'ID={element["canonical_id"]} status={element["block_id_status"]}')
                lines.append(f'      Attributes: {json.dumps(element["attributes"], ensure_ascii=False)}')
                if element['direct_text'].strip():
                    lines.append(f'      Opaque/direct text: {json.dumps(element["direct_text"], ensure_ascii=False)}')
            for link in links[content['id']]:
                lines.append(f'    Link: {link["element_id"]} '
                             f'from={link["from_status"]}:{link["from_element_id"]} '
                             f'to={link["to_status"]}:{link["to_element_id"]}')
    for issue in result.issues:
        lines.append(f'Issue: {issue["code"]} [{issue["source_id"]}]')
    return '\n'.join(lines) + '\n'
