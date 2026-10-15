"""Documented PID member headers linked to captured evidence, never live values.

Catalog source: Rockwell Studio 5000 v38, PID Structure:
https://www.rockwellautomation.com/en-us/docs/studio-5000-logix-designer/38-00/contents-ditamap/instruction-set/pid-structure.html
Labels omit units, flag decoding and effective settings. DATA is only an array
header: its elements, indices, values and completeness are not interpreted.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from io import StringIO
import json
from typing import Any

from .models import InventoryResult, SourceSnapshot
from .pid import PidResult, validate_pid
from .references import ReferenceResult
from .tag_data import TagDataResult, _strict_match


def _fields(group: str, datatype: str, rows: dict[str, str]) -> dict[str, dict[str, str]]:
    return {name: {'label': label, 'group': group, 'datatype': datatype,
                   'kind': 'data_value_member'} for name, label in rows.items()}


FIELD_CATALOG = {
    **_fields('setpoint', 'REAL', {'SP': 'Setpoint'}),
    **_fields('tuning', 'REAL', {'KP': 'Proportional term', 'KI': 'Integral term',
        'KD': 'Derivative term', 'BIAS': 'Bias', 'DB': 'Deadband', 'UPD': 'Update interval'}),
    **_fields('scaling', 'REAL', {'MAXS': 'Upper engineering scale', 'MINS': 'Lower engineering scale',
        'MAXI': 'Upper PV input scale', 'MINI': 'Lower PV input scale',
        'MAXCV': 'Upper CV scale', 'MINCV': 'Lower CV scale',
        'MINTIE': 'Lower tieback scale', 'MAXTIE': 'Upper tieback scale'}),
    **_fields('limits', 'REAL', {'MAXO': 'Upper output limit', 'MINO': 'Lower output limit'}),
    **_fields('mode', 'REAL', {'SO': 'Manual output setting'}),
    **_fields('process_values', 'REAL', {'PV': 'Stored process variable', 'ERR': 'Stored error',
        'OUT': 'Stored output', 'TIE': 'Stored tieback'}),
    **_fields('alarms', 'REAL', {'PVH': 'High PV threshold', 'PVL': 'Low PV threshold',
        'DVP': 'Positive deviation threshold', 'DVN': 'Negative deviation threshold',
        'PVDB': 'PV alarm deadband', 'DVDB': 'Deviation alarm deadband'}),
    **_fields('mode', 'BOOL', {'CT': 'Cascade type flag', 'CL': 'Cascade loop flag',
        'PVT': 'PV tracking flag', 'DOE': 'Derivative basis flag', 'SWM': 'Software mode flag',
        'CA': 'Control action flag', 'MO': 'Station mode flag', 'PE': 'Equation form flag',
        'NDF': 'Derivative smoothing flag', 'NOBC': 'Bias calculation flag',
        'NOZC': 'Deadband crossing flag'}),
    **_fields('status', 'BOOL', {'EN': 'Enable flag', 'INI': 'Initialization flag',
        'SPOR': 'Setpoint range flag', 'OLL': 'Low output flag', 'OLH': 'High output flag',
        'EWD': 'Deadband status flag', 'DVNA': 'Negative deviation alarm flag',
        'DVPA': 'Positive deviation alarm flag', 'PVLA': 'Low PV alarm flag',
        'PVHA': 'High PV alarm flag'}),
    **_fields('internal', 'DINT', {'CTL': 'Packed control word'}),
    'DATA': {'label': 'Internal state array', 'group': 'internal',
             'datatype': 'REAL', 'kind': 'array_member'},
}
MEMBER_GROUPS = frozenset({*(row['group'] for row in FIELD_CATALOG.values()), 'unknown'})
MEMBER_STATUSES = frozenset({'matched', 'array_header_matched', 'unknown_name', 'name_missing',
    'qualified_attribute', 'type_missing', 'type_mismatch', 'shape_mismatch',
    'dimensions_unmodeled', 'value_missing'})
MATCHED_STATUSES = frozenset({'matched', 'array_header_matched'})
MAX_PID_MEMBER_STRUCTURES = 100_000
MAX_PID_MEMBERS = 250_000
MAX_PID_MEMBER_EVIDENCE_BYTES = 16 * 1024 * 1024
MAX_PID_MEMBER_JSON_BYTES = 16 * 1024 * 1024
PID_MEMBER_CONSTANTS = {
    'schema_version': 1, 'analyzer_version': 'pid-members-1',
    'catalog_version': 'rockwell-pid-fields-1', 'analysis_scope': 'pid_documented_member_headers',
    'member_validation': 'documented_headers_only', 'value_analysis': 'not_implemented',
    'numeric_analysis': 'not_implemented', 'effective_value_selection': 'not_implemented',
    'execution_analysis': 'not_implemented',
}
COVERAGE_KEYS = frozenset({'source_pid_partial', 'structures_total', 'distinct_backing_owners', 'members_total',
    'members_by_group', 'members_by_status', 'missing_catalog_fields', 'duplicate_catalog_fields',
    'duplicate_member_records', 'structures_with_missing', 'structures_with_duplicates',
    'structures_with_gaps'})


class PidMemberError(ValueError):
    """Source-free rejection of inconsistent or excessive member evidence."""


@dataclass(frozen=True)
class PidMemberResult:
    snapshot: dict[str, str | int]
    status: str
    structures: list[dict[str, Any]]
    members: list[dict[str, Any]]
    coverage: dict[str, Any]
    schema_version: int = 1
    analyzer_version: str = 'pid-members-1'
    catalog_version: str = 'rockwell-pid-fields-1'
    analysis_scope: str = 'pid_documented_member_headers'
    member_validation: str = 'documented_headers_only'
    value_analysis: str = 'not_implemented'
    numeric_analysis: str = 'not_implemented'
    effective_value_selection: str = 'not_implemented'
    execution_analysis: str = 'not_implemented'

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _invalid() -> None:
    raise PidMemberError('PID member evidence is inconsistent or exceeds its limits.') from None


def _ascii_upper(value: Any) -> str | None:
    return value.upper() if type(value) is str and value.isascii() else None


def _classify(element: dict[str, Any], structure_id: str) -> dict[str, Any]:
    attrs = element['attributes']
    qualified = {key.rsplit('}', 1)[-1] for key in attrs if '}' in key}
    name = _ascii_upper(attrs.get('Name'))
    field = name if name in FIELD_CATALOG and 'Name' not in qualified else None
    spec = FIELD_CATALOG.get(field)
    group = spec['group'] if spec else 'unknown'
    if qualified & {'Name', 'DataType', 'Value', 'Dimensions'}:
        status = 'qualified_attribute'
    elif not attrs.get('Name'):
        status = 'name_missing'
    elif spec is None:
        status = 'unknown_name'
    elif element['kind'] != spec['kind']:
        status = 'shape_mismatch'
    elif not attrs.get('DataType'):
        status = 'type_missing'
    elif _ascii_upper(attrs['DataType']) != spec['datatype']:
        status = 'type_mismatch'
    elif field == 'DATA':
        status = ('array_header_matched' if attrs.get('Dimensions') == '17'
                  else 'dimensions_unmodeled')
    elif 'Dimensions' in attrs:
        status = 'dimensions_unmodeled'
    elif not attrs.get('Value', '').strip():
        status = 'value_missing'
    else:
        status = 'matched'
    return {'element_id': element['id'], 'structure_id': structure_id,
            'field': field, 'group': group, 'status': status}


def _derive(snapshot: SourceSnapshot, pid: PidResult, tag_data: TagDataResult) -> PidMemberResult:
    elements = {row['id']: row for row in tag_data.elements}
    structures: list[dict[str, Any]] = []
    members: list[dict[str, Any]] = []
    seen: set[str] = set()
    owners: set[str] = set()
    coverage = dict.fromkeys(sorted(COVERAGE_KEYS), 0)
    coverage['members_by_group'] = dict.fromkeys(sorted(MEMBER_GROUPS), 0)
    coverage['members_by_status'] = dict.fromkeys(sorted(MEMBER_STATUSES), 0)
    coverage['source_pid_partial'] = int(pid.status == 'partial')
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
            if retained > MAX_PID_MEMBER_EVIDENCE_BYTES:
                _invalid()

    for occurrence in pid.occurrences:
        for candidate in occurrence['structure_candidates']:
            structure_id = candidate['structure_id']
            if structure_id in seen:
                continue
            if len(structures) >= MAX_PID_MEMBER_STRUCTURES:
                _invalid()
            seen.add(structure_id)
            owners.add(occurrence['backing_owner_id'])
            fields: Counter[str] = Counter()
            member_gap = False
            for member_id in candidate['member_ids']:
                if len(members) >= MAX_PID_MEMBERS:
                    _invalid()
                row = _classify(elements[member_id], structure_id)
                retain(row)
                members.append(row)
                coverage['members_by_group'][row['group']] += 1
                coverage['members_by_status'][row['status']] += 1
                if row['field'] is not None:
                    fields[row['field']] += 1
                member_gap |= row['status'] not in MATCHED_STATUSES
            missing = sorted(FIELD_CATALOG.keys() - fields.keys())
            duplicate = sorted(field for field, count in fields.items() if count > 1)
            row = {'structure_id': structure_id, 'content_id': candidate['content_id'],
                   'owner_id': occurrence['backing_owner_id'],
                   'member_ids': list(candidate['member_ids']),
                   'missing_fields': missing, 'duplicate_fields': duplicate}
            retain(row)
            structures.append(row)
            coverage['missing_catalog_fields'] += len(missing)
            coverage['duplicate_catalog_fields'] += len(duplicate)
            coverage['duplicate_member_records'] += sum(fields[field] for field in duplicate)
            coverage['structures_with_missing'] += bool(missing)
            coverage['structures_with_duplicates'] += bool(duplicate)
            coverage['structures_with_gaps'] += bool(missing or duplicate or member_gap)
    coverage.update(structures_total=len(structures), members_total=len(members),
                    distinct_backing_owners=len(owners))
    retain(coverage)
    partial = pid.status == 'partial' or bool(coverage['structures_with_gaps'])
    return PidMemberResult(dict(pid.snapshot), 'partial' if partial else 'complete',
                           structures, members, coverage)


def analyze_pid_members(snapshot: SourceSnapshot, inventory: InventoryResult,
                        references: ReferenceResult, tag_data: TagDataResult,
                        pid: PidResult) -> PidMemberResult:
    """Authenticate existing PID links, then classify unique direct member headers."""
    try:
        validate_pid(snapshot, inventory, references, tag_data, pid)
        result = _derive(snapshot, pid, tag_data)
        render_pid_members_json(result)
        return result
    except PidMemberError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def validate_pid_members(snapshot: SourceSnapshot, inventory: InventoryResult,
                         references: ReferenceResult, tag_data: TagDataResult,
                         pid: PidResult, result: PidMemberResult) -> None:
    try:
        valid = type(result) is PidMemberResult and _strict_match(
            analyze_pid_members(snapshot, inventory, references, tag_data, pid), result)
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        valid = False
    if not valid:
        _invalid()


def render_pid_members_json(result: PidMemberResult) -> str:
    """Bound private serialization; validate_pid_members authenticates source links."""
    if type(result) is not PidMemberResult or vars(result).keys() != set(PidMemberResult.__dataclass_fields__):
        _invalid()
    try:
        pending = [vars(result)]
        budget = MAX_PID_MEMBER_EVIDENCE_BYTES
        while pending:
            value = pending.pop()
            budget -= 1
            if type(value) is str:
                budget -= len(value.encode('utf-8'))
            elif type(value) is dict:
                if len(value) > MAX_PID_MEMBERS or any(type(key) is not str for key in value):
                    _invalid()
                pending.extend(value.keys())
                pending.extend(value.values())
            elif type(value) is list:
                if len(value) > MAX_PID_MEMBERS:
                    _invalid()
                pending.extend(value)
            elif type(value) not in (int, type(None)):
                _invalid()
            if budget < 0:
                _invalid()
        output = StringIO()
        size = 0
        for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True, indent=2,
                                      allow_nan=False).iterencode(vars(result)):
            size += len(chunk.encode('utf-8'))
            if size + 1 > MAX_PID_MEMBER_JSON_BYTES:
                _invalid()
            output.write(chunk)
        return output.getvalue() + '\n'
    except (AttributeError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()
