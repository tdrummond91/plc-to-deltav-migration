"""Closed count-only publication boundary for stored tag-data evidence."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .models import InventoryResult, SourceSnapshot
from .source import MAX_ATTRIBUTES, MAX_ELEMENTS
from .tag_data import (
    COVERAGE_KEYS, DUPLICATE_KINDS, ELEMENT_KINDS, ENVELOPE_KINDS, FORMAT_KINDS,
    ISSUE_CODES, MAX_TAG_DATA_CONTENTS, MAX_TAG_DATA_ELEMENTS, MAX_TAG_DATA_EVIDENCE_BYTES,
    MAX_TAG_DATA_ISSUES, MAX_TAG_DATA_OWNERS, OWNER_KINDS, TAG_DATA_CONSTANTS,
    TagDataResult, validate_tag_data,
)

MAX_COUNT = 10**12
MAX_REPORT_BYTES = 32 * 1024
CONSTANTS = {
    **TAG_DATA_CONSTANTS, 'policy_version': 2,
    'report_kind': 'l5x_tag_data_review_summary', 'exporter_version': 'tag-data-summary-1',
    'sharing_status': 'aggregate_sync_allowed',
}


class TagDataSummaryError(ValueError):
    """Publication rejection that contains no stored source evidence."""


def _invalid() -> None:
    raise TagDataSummaryError('Tag-data summary validation failed; no summary was produced.') from None


def _keys(value: Any, keys: set[str] | frozenset[str]) -> None:
    if (type(value) is not dict or any(type(key) is not str for key in value)
            or value.keys() != keys):
        _invalid()


def _count(value: Any) -> None:
    if type(value) is not int or not 0 <= value <= MAX_COUNT:
        _invalid()


def validate_tag_data_summary(summary: dict[str, Any]) -> None:
    """Validate closed aggregate partitions and observable capture capacities."""
    _keys(summary, set(CONSTANTS) | {'status', 'tool_revision', 'coverage'})
    for key, value in CONSTANTS.items():
        if type(summary[key]) is not type(value) or summary[key] != value:
            _invalid()
    if type(summary['status']) is not str or summary['status'] not in {'complete', 'partial'}:
        _invalid()
    revision = summary['tool_revision']
    _keys(revision, {'commit', 'worktree'})
    if type(revision['worktree']) is not str:
        _invalid()
    if revision['worktree'] == 'unavailable':
        if revision['commit'] is not None:
            _invalid()
    elif revision['worktree'] in {'clean', 'modified'}:
        if type(revision['commit']) is not str or re.fullmatch(r'[0-9a-f]{40}', revision['commit']) is None:
            _invalid()
    else:
        _invalid()
    coverage = summary['coverage']
    _keys(coverage, COVERAGE_KEYS)
    mappings = {
        'owners_by_kind': OWNER_KINDS, 'contents_by_envelope': ENVELOPE_KINDS,
        'contents_by_format': FORMAT_KINDS, 'elements_by_kind': ELEMENT_KINDS,
        'duplicate_groups': DUPLICATE_KINDS, 'duplicate_records': DUPLICATE_KINDS,
        'issues_by_code': ISSUE_CODES,
    }
    for key, value in coverage.items():
        if key in mappings:
            _keys(value, mappings[key])
            for count in value.values():
                _count(count)
        else:
            _count(value)
    owners, contents, elements = (coverage[key] for key in
                                  ('owners_total', 'contents_total', 'elements_total'))
    formats, kinds, issues = (coverage[key] for key in
                              ('contents_by_format', 'elements_by_kind', 'issues_by_code'))
    for total, partition in (
        (owners, coverage['owners_by_kind']), (contents, coverage['contents_by_envelope']),
        (contents, formats), (elements, kinds), (coverage['issues_total'], issues),
    ):
        if sum(partition.values()) != total:
            _invalid()
    if (owners > MAX_TAG_DATA_OWNERS or contents > MAX_TAG_DATA_CONTENTS
            or elements > MAX_TAG_DATA_ELEMENTS or coverage['issues_total'] > MAX_TAG_DATA_ISSUES
            or not 1 <= coverage['source_xml_elements'] <= MAX_ELEMENTS
            or owners + contents + elements > coverage['source_xml_elements']
            or coverage['owners_with_data'] + coverage['owners_without_data'] != owners
            or coverage['owners_with_data'] > contents
            or bool(coverage['owners_with_data']) != bool(contents)
            or (elements and not contents)):
        _invalid()
    if (issues['format_unsupported'] != sum(formats[key] for key in {'l5k', 'raw', 'missing', 'other'})
            or issues['namespace_unmodeled'] > contents
            or issues['shape_unmodeled'] != kinds['unmodeled']
            or issues['content_empty'] > formats['decorated']):
        _invalid()
    modeled = elements - kinds['opaque'] - kinds['unmodeled']
    if ((modeled and not formats['decorated'])
            or (kinds['unmodeled'] and not (formats['decorated'] + formats['string']))
            or (kinds['opaque'] and not (issues['format_unsupported'] + issues['namespace_unmodeled']))
            or elements < max(0, formats['decorated'] - issues['content_empty'] - issues['namespace_unmodeled'])):
        _invalid()
    capacities = {
        'content': contents,
        'member': sum(kinds[key] for key in {'data_value_member', 'structure_member', 'array_member'}),
        'element': kinds['element'],
        'root': sum(kinds[key] for key in {'data_value', 'structure', 'array'}),
    }
    for kind in DUPLICATE_KINDS:
        groups, records = coverage['duplicate_groups'][kind], coverage['duplicate_records'][kind]
        if (bool(groups) != bool(records) or records < 2 * groups or records > capacities[kind]
                or records != issues[f'duplicate_{kind}']):
            _invalid()
    if (coverage['duplicate_groups']['root'] > formats['decorated']
            or (coverage['duplicate_groups']['member'] and not (kinds['structure'] + kinds['structure_member']))
            or (coverage['duplicate_groups']['element'] and not (kinds['array'] + kinds['array_member']))):
        _invalid()
    text_records = coverage['contents_with_text'] + coverage['elements_with_text']
    if (coverage['contents_with_text'] > contents or coverage['elements_with_text'] > elements
            or coverage['direct_text_bytes'] > MAX_TAG_DATA_EVIDENCE_BYTES
            or coverage['direct_text_bytes'] < text_records
            or bool(coverage['direct_text_bytes']) != bool(text_records)
            or issues['unexpected_direct_text'] > text_records
            or issues['unexpected_direct_text'] > formats['decorated'] + elements
            or (issues['unexpected_direct_text'] and not formats['decorated'])
            or coverage['attribute_pairs'] > MAX_ATTRIBUTES
            or (coverage['attribute_pairs'] and not contents)):
        _invalid()
    # These are literal required attribute names, not valid values or types.
    minimum_attributes = (contents - formats['missing'] + kinds['data_value']
                          + 2 * kinds['data_value_member'] + kinds['structure_member']
                          + kinds['array_member'] + kinds['element'])
    if coverage['attribute_pairs'] < minimum_attributes:
        _invalid()
    if summary['status'] != ('partial' if coverage['issues_total'] else 'complete'):
        _invalid()


def build_tag_data_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
                           result: TagDataResult, revision: dict[str, Any] | None = None) -> dict[str, Any]:
    """Authenticate all private records before extracting public counts."""
    try:
        validate_tag_data(snapshot, inventory, result)
        summary = {
            **CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
            'tool_revision': revision if revision is not None else
            {'commit': None, 'worktree': 'unavailable'},
        }
        validate_tag_data_summary(summary)
        summary['tool_revision'] = dict(summary['tool_revision'])
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_tag_data_summary(summary: dict[str, Any]) -> str:
    validate_tag_data_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
