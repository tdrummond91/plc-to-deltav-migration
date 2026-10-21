"""Collect source-bound prose for an English reading layer, never PLC code.

The immutable snapshot remains authoritative. XML locations distinguish repeated
notes; exact text may share one translation cache entry without merging evidence.
"""
from __future__ import annotations

from collections import Counter
import hashlib
from typing import Any

from .source import SourceError, _read_nodes, snapshot_from_bytes


_PROSE = {'Description', 'Comment', 'LocalizedDescription', 'LocalizedComment'}
_DATA = {'Data', 'DefaultData', 'DataValue', 'DataValueMember', 'Structure',
         'StructureMember', 'Array', 'ArrayMember', 'EncodedData', 'EncryptedData'}
_LOCALIZED = {'LocalizedDescription', 'LocalizedComment', 'LocalizedText'}


def collect_annotations(snapshot_bytes: bytes, inventory: dict, sfc: dict | None = None,
                        conditions: dict | None = None) -> dict[str, Any]:
    """Return bounded prose occurrences tied to the supplied exact snapshot.

    Names, attributes, stored data and executable text are never translation
    inputs. Nested/localized note fragments stay independent so no concatenated
    wording or invented ownership is introduced.
    """
    snapshot = snapshot_from_bytes(snapshot_bytes)
    identity = {'id': snapshot.id, 'sha256': snapshot.sha256, 'size_bytes': snapshot.size_bytes}
    if not isinstance(inventory, dict) or inventory.get('snapshot') != identity:
        raise SourceError('Translation annotations and inventory must use the same source snapshot.')
    nodes = _read_nodes(snapshot_bytes)
    root_namespace = nodes[0].expanded_name.rpartition('}')[0]
    records = [*inventory.get('entities', []), *inventory.get('rungs', [])]
    if sfc is not None:
        if sfc.get('snapshot') != identity:
            raise SourceError('Translation annotations and sequence evidence disagree.')
        records.extend(sfc.get('elements', []))
    owners = {r['locator']: r['id'] for r in records
              if isinstance(r, dict) and isinstance(r.get('locator'), str) and isinstance(r.get('id'), str)}
    owner_by_index: dict[int, str] = {}
    qualified: dict[int, bool] = {}
    excluded_data: dict[int, bool] = {}
    prose_context: dict[int, str | None] = {}
    entries: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    namespace_gaps = 0
    st_lines = 0

    def retain(original: str, locator: str, kind: str, owner: str | None) -> None:
        if not original.strip():
            return
        digest = hashlib.sha256(f'{snapshot.id}\0{locator}\0{kind}'.encode()).hexdigest()
        entry = {'id': f'annotation_{digest}', 'locator': locator, 'kind': kind, 'original': original}
        if owner:
            entry['owner_id'] = owner
        entries.append(entry)
        counts[kind] += 1

    for index, node in enumerate(nodes):
        parent = nodes[node.parent] if node.parent is not None else None
        qualified[index] = (node.expanded_name.rpartition('}')[0] == root_namespace
                            and (node.parent is None or qualified[node.parent]))
        excluded_data[index] = node.name in _DATA or excluded_data.get(node.parent, False)
        owner = owners.get(node.locator) or owner_by_index.get(node.parent)
        if owner:
            owner_by_index[index] = owner
        context = prose_context.get(node.parent)
        kind = None
        if node.name in _PROSE and not excluded_data[index]:
            # Localized text must be inside an explicit annotation envelope.
            if node.name not in _LOCALIZED or context:
                kind = 'description' if 'Description' in node.name else 'comment'
        elif node.name == 'TextBox' and not excluded_data[index]:
            kind = 'text_box'
        elif node.name in {'Text', 'LocalizedText'} and context == 'text_box':
            kind = 'text_box'
        if kind:
            prose_context[index] = kind
            if not qualified[index]:
                if node.text.strip():
                    namespace_gaps += 1
            elif not excluded_data[index]:
                retain(node.text, node.locator, kind, owner)
        if node.name == 'Line' and parent is not None and parent.name == 'STContent':
            st_lines += 1

    # The existing SFC expression lexer has already distinguished comments from
    # code. Accept only terminated, unnested spans and verify their joined source
    # against the XML records before making them translation inputs.
    captured_st_comments = 0
    if conditions is not None:
        if conditions.get('snapshot') != identity or sfc is None:
            raise SourceError('Translation annotations and condition evidence disagree.')
        elements = {e['id']: e for e in sfc.get('elements', [])}
        transitions = {t['id']: t for t in conditions.get('transitions', [])}
        node_by_locator = {n.locator: n for n in nodes}
        for comment in conditions.get('comments', []):
            transition = transitions.get(comment.get('transition_id'))
            if not transition or comment.get('terminated') is not True:
                continue
            lines = [elements.get(identifier) for identifier in transition.get('line_ids', [])]
            if not lines or any(line is None for line in lines):
                continue
            xml_lines = [node_by_locator.get(line['locator']) for line in lines]
            if any(line is None for line in xml_lines):
                continue
            original = '\n'.join(line.text for line in xml_lines)
            start, end = comment.get('start'), comment.get('end')
            raw = comment.get('raw_text')
            if (original != transition.get('raw_text') or type(start) is not int or type(end) is not int
                    or not 0 <= start < end <= len(original) or original[start:end] != raw):
                continue
            if not isinstance(raw, str) or raw[:2] not in {'//', '(*', '/*'}:
                continue
            if raw[:2] != '//' and (raw[-2:] not in {'*)', '*/'} or any(p in raw[2:-2] for p in ('(*', '/*'))):
                continue
            locator = f"{xml_lines[0].locator}#comment-{start}-{end}"
            retain(raw, locator, 'structured_text_comment', transition.get('transition_id'))
            captured_st_comments += 1

    limitations = [
        'Names, tag addresses, code, saved values and attribute text remain exactly as exported.',
        'English wording is a reading aid; source evidence and engineering classifications are unchanged.',
    ]
    if st_lines:
        limitations.append('Structured-text code stays in its original form. Only separately captured, '
                           'terminated SFC transition comments are eligible; other embedded comments remain original.')
    if namespace_gaps:
        limitations.append('Notes under an unsupported XML namespace remain original and are excluded from translation.')
    return {
        'snapshot_id': snapshot.id,
        'entries': entries,
        'coverage': {'annotations': len(entries), 'unique_texts': len({e['original'] for e in entries}),
                     'by_kind': dict(sorted(counts.items())), 'namespace_exclusions': namespace_gaps,
                     'structured_text_lines': st_lines, 'captured_structured_text_comments': captured_st_comments},
        'limitations': limitations,
    }
