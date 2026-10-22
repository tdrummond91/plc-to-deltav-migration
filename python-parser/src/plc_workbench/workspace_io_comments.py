"""Source-bound module/channel prose, without changing saved inventory contracts.

L5X member comments live under Comments/Comment with a relative Operand;
they are not the owning tag's direct Description. Keep every annotation and
language separately so conflicting comments never become one invented value.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import re

from .models import InventoryResult
from .source import _read_nodes, snapshot_from_bytes

MAX_ANNOTATIONS = 25_000
MAX_ANNOTATION_CHARS = 4_000_000
_OWNERS = {'module', 'module_input_tag', 'module_output_tag', 'module_config_tag',
           'tag', 'aoi_local_tag', 'aoi_parameter'}
_PART = r'(?:\.[A-Za-z_][A-Za-z0-9_]*|\.(?:0|[1-9][0-9]*)|\[(?:0|[1-9][0-9]*)(?:,(?:0|[1-9][0-9]*))*\])'
_SUFFIX = re.compile(_PART + '+', re.ASCII)


class IOCommentError(ValueError):
    """Fixed, source-free error for annotation evidence failures."""


def _invalid() -> None:
    raise IOCommentError('Saved I/O annotation evidence is inconsistent or exceeds its limits.')


def _member(operand: str | None) -> str | None:
    if not operand or len(operand) > 4096:
        return None
    # Rockwell exports relative operands; accept their leading-dot spelling and
    # explicit member spellings without changing array indexes or leading zeros.
    suffix = operand if operand.startswith(('.', '[')) else '.' + operand
    if not _SUFFIX.fullmatch(suffix):
        return None
    return re.sub(r'\.[A-Za-z_][A-Za-z0-9_]*', lambda match: match.group().lower(), suffix)


def collect_io_annotations(source: bytes, inventory: InventoryResult,
                           qualified: dict[str, bool], *,
                           owner_ids: set[str] | frozenset[str] | None = None
                           ) -> dict[tuple[str, str], list[dict]]:
    """Join only exact declaration locations in the authenticated snapshot.

    The caller authenticates the inventory. This reader independently checks
    snapshot identity, supported XML ancestry and annotation structure; source
    extensions, Data content and dynamic operands do not create channel notes.
    An optional owner filter is applied before retaining or budgeting prose;
    excluded internal tags cannot exhaust a field-I/O annotation budget.
    """
    snapshot = snapshot_from_bytes(source)
    if inventory.snapshot != {'id': snapshot.id, 'sha256': snapshot.sha256,
                              'size_bytes': snapshot.size_bytes}:
        _invalid()
    nodes = _read_nodes(source)
    namespace = nodes[0].expanded_name.rpartition('}')[0]
    okay: list[bool] = []
    locations: dict[str, int] = {}
    for node in nodes:
        okay.append(node.expanded_name.rpartition('}')[0] == namespace
                    and not any('}' in key for key in node.expanded_attributes)
                    and (node.parent is None or okay[node.parent]))
        locations[node.locator] = len(okay) - 1
    result: dict[tuple[str, str], list[dict]] = defaultdict(list)
    count = chars = 0

    def retain(owner_id: str, suffix: str, index: int, kind: str,
               language: str | None = None) -> None:
        nonlocal count, chars
        node = nodes[index]
        if not okay[index] or node.children or not node.text.strip():
            return
        count += 1
        chars += len(node.text)
        if count > MAX_ANNOTATIONS or chars > MAX_ANNOTATION_CHARS:
            _invalid()
        identifier = hashlib.sha256(f'{snapshot.id}\0{node.locator}\0{kind}'.encode()).hexdigest()
        result[owner_id, suffix].append({
            'id': 'io_annotation_' + identifier, 'owner_id': owner_id, 'suffix': suffix,
            'kind': kind, 'language': language, 'locator': node.locator, 'text': node.text,
        })

    def prose(owner_id: str, suffix: str, index: int, kind: str, localized: str) -> None:
        node = nodes[index]
        if not okay[index]:
            return
        if not node.children:
            retain(owner_id, suffix, index, kind)
        elif not node.text.strip() and all(nodes[i].name == localized for i in node.children):
            for child in node.children:
                retain(owner_id, suffix, child, kind, nodes[child].attributes.get('Lang'))

    for owner in inventory.entities:
        if owner_ids is not None and owner.id not in owner_ids:
            continue
        index = locations.get(owner.locator)
        if owner.kind not in _OWNERS or not qualified.get(owner.id) or index is None or not okay[index]:
            continue
        for child in nodes[index].children:
            node = nodes[child]
            if node.name == 'Description':
                prose(owner.id, '', child, 'source_description', 'LocalizedDescription')
            elif node.name == 'Comments' and okay[child]:
                for comment in node.children:
                    entry = nodes[comment]
                    suffix = _member(entry.attributes.get('Operand'))
                    if entry.name == 'Comment' and suffix is not None:
                        prose(owner.id, suffix, comment, 'member_comment', 'LocalizedComment')
    return dict(result)
