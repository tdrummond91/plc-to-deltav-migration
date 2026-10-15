"""Closed, count-only SFC structure publication contract.

The private structure reader preserves XML evidence. This boundary reconstructs
only approved totals; names, IDs, attributes, links and ST text remain private.
Structure counts describe the export, not execution or sequence semantics.
"""
from __future__ import annotations

from collections import Counter
import json
import re
from typing import Any

from .models import InventoryResult, SourceSnapshot
from .sfc_structure import (
    SfcStructureResult, SFC_ELEMENT_KINDS, SFC_EDIT_KINDS,
    SFC_BLOCK_ID_STATUSES, SFC_ENDPOINT_STATUSES, SFC_ISSUE_CODES,
    SFC_ELEMENT_KINDS_V1, SFC_ISSUE_CODES_V1,
    SFC_OPAQUE_TEXT_KINDS, SFC_OPAQUE_TEXT_KINDS_V1,
    MAX_SFC_ELEMENTS, MAX_SFC_CONTENTS, MAX_SFC_LINKS, MAX_SFC_EVIDENCE_CHARS,
    MAX_SFC_ANNOTATIONS,
    validate_sfc_structure,
)
from .summary import MAX_COUNT, MAX_REPORT_BYTES

CONSTANTS_V1 = {
    'schema_version': 1,
    'policy_version': 2,
    'report_kind': 'l5x_sfc_structure_review_summary',
    'exporter_version': 'sfc-structure-summary-1',
    'analyzer_version': 'sfc-structure-1',
    'analysis_scope': 'sfc_structure_only',
    'semantic_analysis': 'not_implemented',
    'sharing_status': 'aggregate_sync_allowed',
}
CONSTANTS = CONSTANTS_V1 | {
    'schema_version': 2,
    'exporter_version': 'sfc-structure-summary-2',
    'analyzer_version': 'sfc-structure-2',
}


class SfcSummaryError(ValueError):
    """Fixed source-free publication failure."""


def _invalid() -> None:
    raise SfcSummaryError('SFC summary validation failed; no shareable candidate was produced.')


def _keys(value: Any, keys: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or value.keys() != keys:
        _invalid()


def _count(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= MAX_COUNT:
        _invalid()
    return value


def _counts(value: Any, keys: set[str] | frozenset[str]) -> None:
    _keys(value, keys)
    for count in value.values():
        _count(count)


def _partition(group: Any, vocabulary: frozenset[str]) -> None:
    _keys(group, {'total', 'by_kind'})
    _count(group['total'])
    _counts(group['by_kind'], vocabulary)
    if sum(group['by_kind'].values()) != group['total']:
        _invalid()


def _tally(rows: list[dict[str, Any]], field: str, vocabulary: frozenset[str]) -> dict[str, int]:
    observed = Counter(row[field] for row in rows)
    if not observed.keys() <= vocabulary:
        _invalid()
    return {key: observed[key] for key in sorted(vocabulary)}


def build_sfc_summary(
    snapshot: SourceSnapshot, inventory: InventoryResult, result: SfcStructureResult,
    *, revision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconstruct counts only after canonical private-evidence validation."""
    try:
        if (type(inventory) is not InventoryResult or type(inventory.schema_version) is not int
                or inventory.schema_version != 3 or inventory.parser_version != 'source-inventory-3'
                or inventory.analysis_scope != 'source_structure_only'
                or inventory.semantic_analysis != 'not_implemented'):
            _invalid()
        validate_sfc_structure(snapshot, inventory, result)
        blocks = [row for row in result.elements if row['block_id_status'] is not None]
        block_ids = Counter((row['content_id'], row['canonical_id']) for row in blocks
                            if row['block_id_status'] == 'valid')
        duplicates = [count for count in block_ids.values() if count > 1]
        endpoints = Counter(link[field] for link in result.links for field in ('from_status', 'to_status'))
        issue_counts = _tally(result.issues, 'code', SFC_ISSUE_CODES)
        resolved = sum(link['from_status'] == link['to_status'] == 'resolved' for link in result.links)
        annotations = [row for row in result.annotations
                       if row['from_status'] == row['to_status'] == 'resolved']
        annotation_endpoints = Counter(row[field] for row in result.annotations
                                       for field in ('from_status', 'to_status'))
        text_boxes = [row for row in result.elements if row['kind'] == 'text_box']
        text_children = [row for row in result.elements if row['kind'] == 'text_box_text']
        text_parents = {row['parent_id'] for row in text_children}
        text_shapes: Counter[str] = Counter()
        for row in text_boxes:
            direct = bool(row['direct_text'].strip())
            child = row['id'] in text_parents
            text_shapes['mixed' if direct and child else 'direct_only' if direct else
                        'child_only' if child else 'empty'] += 1
        with_content = sum(bool(row['content_ids']) for row in result.routines)
        summary = dict(CONSTANTS) | {
            'tool_revision': dict(revision) if revision is not None else {'commit': None, 'worktree': 'unavailable'},
            'source_sfc_routines': sum(entity.kind == 'routine' and entity.attributes.get('Type') == 'SFC'
                                       for entity in inventory.entities),
            'status': result.status,
            'counts': {
                'routines': {'total': len(result.routines), 'with_content': with_content,
                             'without_content': len(result.routines) - with_content,
                             'with_unmodeled_content': sum(bool(row['unmodeled_children'] or row['direct_text'].strip())
                                                          for row in result.routines),
                             'with_protection': sum(bool(row['protection_markers']) for row in result.routines)},
                'contents': {'total': len(result.contents),
                             'by_edit_kind': _tally(result.contents, 'edit_kind', SFC_EDIT_KINDS)},
                'elements': {'total': len(result.elements),
                             'by_kind': _tally(result.elements, 'kind', SFC_ELEMENT_KINDS)},
                'blocks': {'total': len(blocks),
                           'by_id_status': _tally(blocks, 'block_id_status', SFC_BLOCK_ID_STATUSES),
                           'duplicate_groups': len(duplicates), 'duplicate_members': sum(duplicates)},
                'links': {'total': len(result.links),
                          'by_status': {'resolved': resolved, 'unresolved': len(result.links) - resolved}},
                'link_endpoints': {'total': 2 * len(result.links),
                                   'by_status': {key: endpoints[key] for key in sorted(SFC_ENDPOINT_STATUSES)}},
                'annotations': {
                    'total': len(result.annotations),
                    'by_status': {'resolved': len(annotations),
                                  'unresolved': len(result.annotations) - len(annotations)},
                    'distinct_text_boxes': len({row['from_element_id'] for row in annotations}),
                    'distinct_targets': len({row['to_element_id'] for row in annotations}),
                },
                'annotation_endpoints': {
                    'total': 2 * len(result.annotations),
                    'by_status': {key: annotation_endpoints[key] for key in sorted(SFC_ENDPOINT_STATUSES)},
                },
                'annotation_text': {
                    'text_boxes': len(text_boxes),
                    'by_shape': {key: text_shapes[key]
                                 for key in ('empty', 'direct_only', 'child_only', 'mixed')},
                    'child_elements': len(text_children),
                    'total_characters': sum(len(row['direct_text']) for row in text_boxes + text_children),
                },
                'structured_text': {'lines': sum(row['kind'] == 'st_line' for row in result.elements),
                                    'total_characters': sum(len(row['direct_text']) for row in result.elements
                                                            if row['kind'] == 'st_line')},
                'issues': {'total': len(result.issues), 'by_code': issue_counts},
            },
        }
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        _invalid()
    validate_sfc_summary(summary)
    return summary


def validate_sfc_summary(summary: dict[str, Any]) -> None:
    """Reject unknown fields, raw strings and inconsistent aggregate evidence."""
    _keys(summary, set(CONSTANTS) | {'tool_revision', 'source_sfc_routines', 'status', 'counts'})
    if type(summary['schema_version']) is not int or summary['schema_version'] not in (1, 2):
        _invalid()
    current = summary['schema_version'] == 2
    constants = CONSTANTS if current else CONSTANTS_V1
    element_kinds = SFC_ELEMENT_KINDS if current else SFC_ELEMENT_KINDS_V1
    issue_codes = SFC_ISSUE_CODES if current else SFC_ISSUE_CODES_V1
    opaque_kinds = SFC_OPAQUE_TEXT_KINDS if current else SFC_OPAQUE_TEXT_KINDS_V1
    # The old summary treated unknown elements as opaque, too.
    opaque_kinds = opaque_kinds | {'unmodeled'}
    for key, expected in constants.items():
        if type(summary[key]) is not type(expected) or summary[key] != expected:
            _invalid()
    if summary['status'] not in ('complete', 'partial'):
        _invalid()
    revision = summary['tool_revision']
    _keys(revision, {'commit', 'worktree'})
    if revision['worktree'] == 'unavailable':
        if revision['commit'] is not None:
            _invalid()
    elif revision['worktree'] in ('clean', 'modified'):
        if type(revision['commit']) is not str or re.fullmatch(r'[0-9a-f]{40}', revision['commit']) is None:
            _invalid()
    else:
        _invalid()
    _count(summary['source_sfc_routines'])
    counts = summary['counts']
    count_keys = {'routines', 'contents', 'elements', 'blocks', 'links', 'link_endpoints', 'structured_text', 'issues'}
    if current:
        count_keys |= {'annotations', 'annotation_endpoints', 'annotation_text'}
    _keys(counts, count_keys)
    routines = counts['routines']
    _counts(routines, {'total', 'with_content', 'without_content', 'with_protection', 'with_unmodeled_content'})
    contents = counts['contents']
    _keys(contents, {'total', 'by_edit_kind'})
    _count(contents['total'])
    _counts(contents['by_edit_kind'], SFC_EDIT_KINDS)
    _partition(counts['elements'], element_kinds)
    blocks = counts['blocks']
    _keys(blocks, {'total', 'by_id_status', 'duplicate_groups', 'duplicate_members'})
    for key in ('total', 'duplicate_groups', 'duplicate_members'):
        _count(blocks[key])
    _counts(blocks['by_id_status'], SFC_BLOCK_ID_STATUSES)
    for name, vocabulary in (('links', frozenset({'resolved', 'unresolved'})),
                             ('link_endpoints', SFC_ENDPOINT_STATUSES)):
        _keys(counts[name], {'total', 'by_status'})
        _count(counts[name]['total'])
        _counts(counts[name]['by_status'], vocabulary)
        if sum(counts[name]['by_status'].values()) != counts[name]['total']:
            _invalid()
    _counts(counts['structured_text'], {'lines', 'total_characters'})
    issues = counts['issues']
    _keys(issues, {'total', 'by_code'})
    _count(issues['total'])
    _counts(issues['by_code'], issue_codes)
    if (routines['total'] != summary['source_sfc_routines']
            or routines['with_content'] + routines['without_content'] != routines['total']
            or routines['with_protection'] > routines['total']
            or routines['with_unmodeled_content'] > routines['total']
            or sum(contents['by_edit_kind'].values()) != contents['total']
            or contents['total'] < routines['with_content']
            or bool(contents['total']) != bool(routines['with_content'])
            or sum(blocks['by_id_status'].values()) != blocks['total']
            or blocks['total'] > counts['elements']['total']
            or not 2 * blocks['duplicate_groups'] <= blocks['duplicate_members'] <= blocks['by_id_status']['valid']
            or bool(blocks['duplicate_groups']) != bool(blocks['duplicate_members'])
            or counts['links']['total'] != counts['elements']['by_kind']['directed_link']
            or counts['link_endpoints']['total'] != 2 * counts['links']['total']
            or counts['structured_text']['lines'] != counts['elements']['by_kind']['st_line']
            or not counts['structured_text']['lines'] and counts['structured_text']['total_characters']
            or sum(issues['by_code'].values()) != issues['total']
            or (summary['status'] == 'partial') != bool(issues['total'])):
        _invalid()
    if not contents['total'] and counts['elements']['total']:
        _invalid()
    if (contents['total'] > MAX_SFC_CONTENTS or counts['elements']['total'] > MAX_SFC_ELEMENTS
            or counts['links']['total'] > MAX_SFC_LINKS
            or counts['structured_text']['total_characters'] > MAX_SFC_EVIDENCE_CHARS):
        _invalid()
    resolved = counts['link_endpoints']['by_status']['resolved']
    resolved_links = counts['links']['by_status']['resolved']
    unresolved_links = counts['links']['by_status']['unresolved']
    if not 2 * resolved_links <= resolved <= 2 * resolved_links + unresolved_links:
        _invalid()
    if resolved and blocks['by_id_status']['valid'] <= blocks['duplicate_members']:
        _invalid()
    endpoints = counts['link_endpoints']['by_status']
    kinds = counts['elements']['by_kind']
    flow_blocks = sum(kinds[key] for key in ('step', 'transition', 'branch', 'leg', 'sbr_ret', 'stop'))
    if (blocks['total'] < flow_blocks + kinds['action'] + kinds['text_box']
            or resolved and not flow_blocks
            or endpoints['ambiguous_target'] and not blocks['duplicate_groups']
            or endpoints['unsupported_kind'] and (blocks['total'] <= flow_blocks
                                                  or blocks['by_id_status']['valid'] <= blocks['duplicate_members'])):
        _invalid()
    by_code = issues['by_code']
    exact_issues = {
        'content_missing': routines['without_content'],
        'protection_present': routines['with_protection'],
        'routine_content_unmodeled': routines['with_unmodeled_content'],
        'edit_kind_unmodeled': contents['by_edit_kind']['empty'] + contents['by_edit_kind']['other'],
        'element_unmodeled': kinds['unmodeled'],
        'block_id_missing': blocks['by_id_status']['missing'],
        'block_id_invalid': blocks['by_id_status']['invalid'],
        'block_id_duplicate': blocks['duplicate_members'],
        'link_endpoint_unresolved': counts['link_endpoints']['total'] - resolved,
    }
    if current:
        _validate_annotations(counts, flow_blocks)
        exact_issues['annotation_endpoint_unresolved'] = (
            counts['annotation_endpoints']['total']
            - counts['annotation_endpoints']['by_status']['resolved']
        )
    text_issue_capacity = contents['total'] + sum(count for kind, count in kinds.items()
                                                  if kind not in opaque_kinds)
    if (any(by_code[key] != value for key, value in exact_issues.items())
            or by_code['unexpected_direct_text'] > text_issue_capacity):
        _invalid()


def _validate_annotations(counts: dict[str, Any], flow_blocks: int) -> None:
    """Check feasible count-only annotation evidence without publishing ID pairs."""
    annotations = counts['annotations']
    _keys(annotations, {'total', 'by_status', 'distinct_text_boxes', 'distinct_targets'})
    for key in ('total', 'distinct_text_boxes', 'distinct_targets'):
        _count(annotations[key])
    _counts(annotations['by_status'], {'resolved', 'unresolved'})
    endpoints = counts['annotation_endpoints']
    _keys(endpoints, {'total', 'by_status'})
    _count(endpoints['total'])
    _counts(endpoints['by_status'], SFC_ENDPOINT_STATUSES)
    resolved = annotations['by_status']['resolved']
    unresolved = annotations['by_status']['unresolved']
    endpoint_resolved = endpoints['by_status']['resolved']
    blocks = counts['blocks']
    unique_valid = blocks['by_id_status']['valid'] - blocks['duplicate_members']
    kinds = counts['elements']['by_kind']
    target_blocks = flow_blocks + kinds['action']
    text_boxes = annotations['distinct_text_boxes']
    targets = annotations['distinct_targets']
    text = counts['annotation_text']
    _keys(text, {'text_boxes', 'by_shape', 'child_elements', 'total_characters'})
    for key in ('text_boxes', 'child_elements', 'total_characters'):
        _count(text[key])
    _counts(text['by_shape'], {'empty', 'direct_only', 'child_only', 'mixed'})
    child_shapes = text['by_shape']['child_only'] + text['by_shape']['mixed']
    direct_shapes = text['by_shape']['direct_only'] + text['by_shape']['mixed']
    if (resolved + unresolved != annotations['total']
            or annotations['total'] != kinds['attachment']
            or annotations['total'] > MAX_SFC_ANNOTATIONS
            or endpoints['total'] != 2 * annotations['total']
            or sum(endpoints['by_status'].values()) != endpoints['total']
            or not 2 * resolved <= endpoint_resolved <= 2 * resolved + unresolved
            or bool(text_boxes) != bool(resolved) or bool(targets) != bool(resolved)
            or text_boxes > min(resolved, kinds['text_box'])
            or targets > min(resolved, target_blocks)
            or text_boxes + targets > unique_valid
            or endpoint_resolved and not unique_valid
            or endpoint_resolved and not (kinds['text_box'] or target_blocks)
            or endpoint_resolved > annotations['total'] and not (kinds['text_box'] and target_blocks)
            or endpoints['by_status']['ambiguous_target'] and not blocks['duplicate_groups']
            or endpoints['by_status']['unsupported_kind'] and not unique_valid):
        _invalid()
    if (text['text_boxes'] != kinds['text_box']
            or sum(text['by_shape'].values()) != text['text_boxes']
            or text['child_elements'] != kinds['text_box_text']
            or child_shapes > text['child_elements']
            or bool(child_shapes) != bool(text['child_elements'])
            or direct_shapes > text['total_characters']
            or not text['text_boxes'] and text['total_characters']
            or text['total_characters'] > MAX_SFC_EVIDENCE_CHARS):
        _invalid()


def render_sfc_summary(summary: dict[str, Any]) -> str:
    """Serialize only a closed, bounded publication candidate."""
    validate_sfc_summary(summary)
    rendered = json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        raise SfcSummaryError('SFC summary exceeds its publication size limit; no candidate was produced.')
    return rendered
