"""Closed aggregate publication boundary for stored alarm declaration facts."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .alarm_evidence import (
    ALARM_EVIDENCE_CONSTANTS, COUNT_MAPS, COVERAGE_KEYS, GAP_CODES,
    MAX_ALARM_EVIDENCE_BYTES, MAX_ALARM_EVIDENCE_LINKS, MAX_ALARM_EVIDENCE_RECORDS,
    MAX_ALARM_XML_VISITS, ROW_GROUPS, AlarmEvidenceResult, validate_alarm_evidence,
)
from .models import InventoryResult, SourceSnapshot
from .source import MAX_ATTRIBUTES
from .tag_data import MAX_TAG_DATA_CONTENTS, TagDataResult

MAX_REPORT_BYTES = 8 * 1024
MAX_ALARM_EVIDENCE_SUMMARY_BYTES = MAX_REPORT_BYTES
CONSTANTS = {
    **ALARM_EVIDENCE_CONSTANTS, 'policy_version': 2,
    'report_kind': 'l5x_alarm_evidence_review_summary', 'exporter_version': 'alarm-evidence-summary-1',
    'sharing_status': 'aggregate_sync_allowed',
}
ALARM_EVIDENCE_SUMMARY_CONSTANTS = CONSTANTS


class AlarmEvidenceSummaryError(ValueError):
    """Fixed source-free publication rejection."""


def _invalid() -> None:
    raise AlarmEvidenceSummaryError('Alarm evidence summary validation failed; no summary was produced.') from None


def _keys(value: Any, expected: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != expected:
        _invalid()


def validate_alarm_evidence_summary(summary: dict[str, Any]) -> None:
    """Validate fixed vocabulary, exact count partitions and capture capacities."""
    _keys(summary, set(CONSTANTS) | {'status', 'coverage', 'tool_revision'})
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
    c = summary['coverage']
    _keys(c, COVERAGE_KEYS)
    for key, value in c.items():
        values = (value,)
        if key in COUNT_MAPS:
            _keys(value, COUNT_MAPS[key])
            values = value.values()
        if any(type(count) is not int or not 0 <= count <= 10**12 for count in values):
            _invalid()
    declarations, containers, elements = (c[f'{group}_total'] for group in ROW_GROUPS)
    records = declarations + containers + elements
    for group in ROW_GROUPS:
        if (sum(c[f'{group}_by_kind'].values()) != c[f'{group}_total']
                or sum(c[f'{group}_by_qualification'].values()) != c[f'{group}_total']):
            _invalid()
    if (sum(c['declarations_by_type'].values()) != declarations
            or records > MAX_ALARM_EVIDENCE_RECORDS
            or not 1 <= c['source_xml_elements'] <= MAX_ALARM_XML_VISITS
            or c['source_entities'] > c['source_xml_elements']
            or c['source_data_contents'] > min(MAX_TAG_DATA_CONTENTS, c['source_xml_elements'])
            or declarations > c['source_entities']
            or containers + elements + declarations > c['source_xml_elements']
            or elements and not containers):
        _invalid()
    gaps = c['gaps_by_code']
    if (c['records_with_gaps'] != sum(c[f'{group}_by_qualification']['source_gap'] for group in ROW_GROUPS)
            or c['gap_links_total'] != sum(gaps.values())
            or not c['records_with_gaps'] <= c['gap_links_total'] <= len(GAP_CODES) * c['records_with_gaps']
            or any(count > c['records_with_gaps'] for count in gaps.values())
            or gaps['unknown_element'] != c['elements_by_kind']['unknown']
            or gaps['unknown_element'] > c['elements_by_qualification']['source_gap']
            or gaps['ancestor_gap'] > containers + elements
            or gaps['unsupported_placement'] < c['containers_by_kind']['orphan']
            or gaps['duplicate_sibling'] != c['duplicate_records']
            or c['duplicate_records'] > containers + elements
            or bool(c['duplicate_groups']) != bool(c['duplicate_records'])
            or c['duplicate_records'] < 2 * c['duplicate_groups']):
        _invalid()
    if (c['content_links_total'] > c['source_data_contents']
            or c['container_links_total'] > containers
            or c['content_links_total'] + c['container_links_total'] > MAX_ALARM_EVIDENCE_LINKS
            or c['declarations_with_data'] > min(declarations, c['content_links_total'])
            or bool(c['declarations_with_data']) != bool(c['content_links_total'])
            or c['declarations_with_containers'] > min(declarations, c['container_links_total'])
            or bool(c['declarations_with_containers']) != bool(c['container_links_total'])
            or c['direct_text_bytes'] > MAX_ALARM_EVIDENCE_BYTES
            or c['attribute_pairs'] > MAX_ATTRIBUTES
            or (c['direct_text_bytes'] or c['attribute_pairs']) and not containers):
        _invalid()
    if summary['status'] != ('partial' if c['records_with_gaps'] else 'complete'):
        _invalid()


def build_alarm_evidence_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
        tag_data: TagDataResult, result: AlarmEvidenceResult,
        revision: dict[str, Any] | None = None) -> dict[str, Any]:
    """Authenticate private evidence before extracting only closed counts."""
    try:
        validate_alarm_evidence(snapshot, inventory, tag_data, result)
        summary = {**CONSTANTS, 'status': result.status, 'coverage': deepcopy(result.coverage),
            'tool_revision': dict(revision) if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        render_alarm_evidence_summary(summary)
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_alarm_evidence_summary(summary: dict[str, Any]) -> str:
    validate_alarm_evidence_summary(summary)
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
        _invalid()
    return rendered
