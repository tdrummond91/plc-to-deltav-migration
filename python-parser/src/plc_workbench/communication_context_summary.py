"""Closed, source-free counts for the private communication context companion."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from .access import AccessResult
from .calculations import CalculationResult
from .communication_context import (
    CONTEXT_CONSTANTS, CONTEXT_CONSTANTS_V2, CONTEXT_CONSTANTS_V3,
    COUNT_MAPS, COUNT_MAPS_V2, COUNT_MAPS_V3,
    COVERAGE_KEYS, COVERAGE_KEYS_V2, COVERAGE_KEYS_V3, INTERPRETED_FIELDS, MAX_RECORDS,
    GENERIC_SELECTORS, GENERIC_SERVICES, GENERIC_SELECTOR_GAPS, GENERIC_SERVICE_DISPOSITIONS,
    CommunicationContextResult, validate_communication_context,
)
from .models import InventoryResult, SourceSnapshot
from .references import ReferenceResult
from .tag_data import TagDataResult

MAX_REPORT_BYTES = 4 * 1024
MAX_REPORT_V2_BYTES = 8 * 1024
MAX_REPORT_V3_BYTES = 8 * 1024
CONSTANTS = {**CONTEXT_CONSTANTS, 'policy_version': 2,
             'report_kind': 'l5x_communication_context_summary',
             'exporter_version': 'communication-context-summary-1',
             'sharing_status': 'aggregate_sync_allowed'}
CONSTANTS_V2 = {**CONSTANTS, **CONTEXT_CONSTANTS_V2,
                'exporter_version': 'communication-context-summary-2'}
CONSTANTS_V3 = {**CONSTANTS, **CONTEXT_CONSTANTS_V3,
                'exporter_version': 'communication-context-summary-3'}


class CommunicationContextSummaryError(ValueError):
    """Source-free aggregate validation failure."""


def _invalid() -> None:
    raise CommunicationContextSummaryError('Communication context summary validation failed; no summary was produced.') from None


def _keys(value: Any, keys: set[str] | frozenset[str]) -> None:
    if type(value) is not dict or any(type(key) is not str for key in value) or value.keys() != keys:
        _invalid()


def validate_communication_context_summary(summary: dict[str, Any]) -> None:
    if type(summary) is not dict or type(summary.get('schema_version')) is not int or summary['schema_version'] not in {1, 2, 3}:
        _invalid()
    version = summary['schema_version']
    constants = CONSTANTS_V3 if version == 3 else CONSTANTS_V2 if version == 2 else CONSTANTS
    count_maps = COUNT_MAPS_V3 if version == 3 else COUNT_MAPS_V2 if version == 2 else COUNT_MAPS
    coverage_keys = COVERAGE_KEYS_V3 if version == 3 else COVERAGE_KEYS_V2 if version == 2 else COVERAGE_KEYS
    _keys(summary, set(constants) | {'status', 'coverage', 'tool_revision'})
    for key, value in constants.items():
        if type(summary[key]) is not type(value) or summary[key] != value:
            _invalid()
    revision = summary['tool_revision']
    _keys(revision, {'commit', 'worktree'})
    if type(revision['worktree']) is not str:
        _invalid()
    if revision['worktree'] == 'unavailable':
        if revision['commit'] is not None:
            _invalid()
    elif revision['worktree'] in {'clean', 'modified'}:
        if type(revision['commit']) is not str or re.fullmatch('[0-9a-f]{40}', revision['commit']) is None:
            _invalid()
    else:
        _invalid()
    c = summary['coverage']
    _keys(c, coverage_keys)
    counts: list[Any] = []
    for key, vocabulary in count_maps.items():
        _keys(c[key], vocabulary)
        counts.extend(c[key].values())
    counts.extend(c[key] for key in coverage_keys - count_maps.keys())
    if any(type(value) is not int or not 0 <= value <= MAX_RECORDS for value in counts):
        _invalid()
    owners, parameters, endpoints = c['owners_total'], c['parameter_records'], c['endpoints_total']
    connections, occurrences = c['tag_connection_records'], c['msg_occurrences']
    owner_parameters = c['owners_with_parameters']
    multiple_parameters, multiple_contents = c['owners_with_multiple_parameters'], c['owners_with_multiple_contents']
    if (sum(c['occurrences_by_status'].values()) != occurrences
            or sum(c['owners_by_status'].values()) != owners
            or sum(c['parameters_by_status'].values()) != parameters
            or sum(c['endpoints_by_status'].values()) != endpoints
            or sum(c['endpoints_by_field'].values()) != endpoints
            or sum(c['tag_connections_by_kind'].values()) != connections
            or sum(c['tag_connections_by_status'].values()) != connections
            or owners + parameters + endpoints + connections + occurrences > MAX_RECORDS
            or occurrences > c['source_instructions']
            or occurrences - c['occurrences_by_status']['signature_gap'] > c['source_operands']
            or not 0 <= multiple_parameters <= owner_parameters <= owners
            or owner_parameters + multiple_parameters > parameters
            or bool(owner_parameters) != bool(parameters)
            or multiple_contents > owners or 2 * multiple_contents > c['contents_total']
            or owner_parameters > c['contents_total']
            or bool(c['contents_total']) and not owners
            or not 0 <= c['tags_with_connections'] <= connections
            or bool(c['tags_with_connections']) != bool(connections)
            or any(value > parameters for value in c['parameter_fields'].values())
            or any(c['endpoints_by_field'][key] != c['parameter_fields'][key]
                   for key in c['endpoints_by_field'])
            or endpoints - c['endpoints_by_status']['unsupported_context'] > 2 * c['parameters_by_status']['supported']
            or (not c['source_rungs'] and (c['source_instructions'] or c['source_operands']))
            or (not c['source_instructions'] and c['source_operands'])):
        _invalid()
    linked = c['occurrences_by_status']['linked']
    repeated = c['occurrences_by_status']['multiple_representations']
    unsupported = c['occurrences_by_status']['unsupported_parameters']
    missing = c['occurrences_by_status']['missing_parameters']
    # Calls may repeat, but these mutually exclusive owner dispositions need
    # distinct owners whenever more than one disposition is observed.
    required_owners = sum(bool(count) for count in (linked, repeated, unsupported, missing))
    single_parameter_owners = int(bool(linked)) + int(bool(unsupported))
    if ((linked and not c['parameters_by_status']['supported'])
            or required_owners > c['owners_by_status']['supported']
            or single_parameter_owners > owner_parameters - multiple_parameters
            or single_parameter_owners + int(bool(missing)) > owners - multiple_contents
            or (missing and owners == owner_parameters)
            or (repeated and not (multiple_parameters or multiple_contents))
            or (unsupported and parameters == c['parameters_by_status']['supported'])
            or (c['occurrences_by_status']['control_type_unconfirmed'] and not c['owners_by_status']['type_gap'])
            or (c['occurrences_by_status']['control_array_unsupported'] and not owners)
            or (c['occurrences_by_status']['control_member_unsupported'] and not owners)):
        _invalid()
    if version >= 2:
        _validate_interpretation(c)
    if version == 3:
        _validate_generic(c)
    partial = (c['occurrences_by_status']['linked'] != occurrences
               or c['owners_by_status']['supported'] != owners
               or c['parameters_by_status']['supported'] != parameters
               or c['endpoints_by_status']['root_candidate'] != endpoints
               or c['tag_connections_by_status']['source_metadata'] != connections
               or multiple_contents or multiple_parameters)
    if type(summary['status']) is not str or summary['status'] != ('partial' if partial else 'complete'):
        _invalid()


def _validate_interpretation(c: dict[str, Any]) -> None:
    parameters = c['parameter_records']
    supported = c['parameters_by_status']['supported']
    unsupported = parameters - supported
    partition_keys = ('message_type_statuses', 'message_families', 'parameter_directions',
                      'communication_methods', *INTERPRETED_FIELDS.values())
    if any(sum(c[key].values()) != parameters or c[key]['unsupported_context'] != unsupported
           for key in partition_keys):
        _invalid()
    types, families, directions = c['message_type_statuses'], c['message_families'], c['parameter_directions']
    unknown = types['missing'] + types['empty'] + types['unknown']
    if (families['unknown'] != unknown or directions['unknown'] != unknown
            or types['catalogued'] != supported - unknown
            or not supported - types['missing'] <= c['parameter_fields']['MessageType']
               <= supported - types['missing'] + unsupported
            or directions['service_dependent'] != families['cip_generic']
            or directions['reconfigure'] != families['module_reconfigure']
            or directions['unconfigured'] != families['unconfigured']
            or directions['read'] + directions['write'] != types['catalogued']
               - families['cip_generic'] - families['module_reconfigure'] - families['unconfigured']):
        _invalid()
    for field, key in INTERPRETED_FIELDS.items():
        # Unsupported parameters can still contain fields; their authored
        # values are not promoted into shape/role interpretations.
        present = c[key]['present'] + c[key]['empty']
        if not present <= c['parameter_fields'][field] <= present + unsupported:
            _invalid()
    roles = c['endpoint_authored_roles']
    occurrence_directions = c['occurrence_directions']
    linked = c['occurrences_by_status']['linked']
    local = c['local_element_shapes']
    destination = c['destination_tag_shapes']
    # Every present local field belongs to exactly one authored direction
    # group. Infer only the unconfigured marginals left over after the fixed
    # roles; local and destination fields may coexist on the same record.
    # These bounds require a feasible partition without inventing correlations
    # between per-record fields, repeated calls or duplicate configurations.
    unconfigured_local = local['present'] - sum(roles[key] for key in (
        'local_source', 'local_destination', 'service_dependent', 'unclassified'))
    unconfigured_destination = destination['present'] - roles['authored_destination']
    if (sum(roles.values()) != c['endpoints_total']
            or roles['unsupported_context'] != c['endpoints_total']
               - sum(c[key]['present'] + c[key]['empty'] for key in ('local_element_shapes', 'destination_tag_shapes'))
            or roles['field_gap'] != local['empty'] + destination['empty']
            or roles['local_source'] > min(local['present'], directions['write'])
            or roles['local_destination'] > min(local['present'], directions['read'])
            or roles['service_dependent'] > min(local['present'], directions['service_dependent'])
            or roles['authored_destination'] > min(destination['present'], supported - directions['unconfigured'])
            or roles['unclassified'] > min(local['present'], directions['unknown'] + directions['reconfigure'])
            or not 0 <= unconfigured_local <= directions['unconfigured']
            or not 0 <= unconfigured_destination <= directions['unconfigured']
            or roles['unconfigured'] != unconfigured_local + unconfigured_destination
            or sum(occurrence_directions.values()) != c['msg_occurrences']
            or occurrence_directions['unavailable'] != c['msg_occurrences'] - linked
            or occurrence_directions['unsupported_context']
            or any(occurrence_directions[key] and not directions[key] for key in directions)):
        _invalid()
    referenced_owners = c['owners_referenced_by_occurrences']
    referenced_parameters = c['parameter_records_referenced_by_occurrences']
    linked_owners = c['owners_with_linked_occurrences']
    linked_parameters = c['linked_parameter_records']
    if (not 0 <= linked_owners <= referenced_owners <= min(c['owners_total'], c['msg_occurrences'])
            or not 0 <= linked_parameters <= referenced_parameters <= parameters
            or linked_owners != linked_parameters
            or linked_parameters > min(linked, supported)
            or bool(linked_parameters) != bool(linked)
            or referenced_parameters and not referenced_owners
            or referenced_owners > linked_owners + c['msg_occurrences'] - linked
            or referenced_parameters > linked_parameters and not (c['occurrences_by_status']['multiple_representations']
                                                                or c['occurrences_by_status']['unsupported_parameters'])):
        _invalid()


def _validate_generic(c: dict[str, Any]) -> None:
    """Conserve records, unique linked records and repeated linked calls."""
    parameters = c['parameter_records']
    supported = c['parameters_by_status']['supported']
    generic = c['message_families']['cip_generic']
    partition_keys = ('generic_parameter_services', 'generic_parameter_completeness',
                      *(key for key, _, _ in GENERIC_SELECTORS.values()))
    if any(sum(c[key].values()) != parameters
           or c[key]['unsupported_context'] != parameters - supported
           or c[key]['not_applicable'] != supported - generic for key in partition_keys):
        _invalid()
    services = c['generic_parameter_services']
    code = c['generic_service_code_statuses']
    complete = c['generic_parameter_completeness']['all_selectors_parsed']
    parsed = [c[key]['parsed'] for key, _, _ in GENERIC_SELECTORS.values()]
    if (code['parsed'] != sum(services[key] for key in (*GENERIC_SERVICES.values(), 'unknown_service'))
            or any(code[key] != services[key] for key in GENERIC_SELECTOR_GAPS)
            or not max(0, sum(parsed) - 3 * generic) <= complete <= min(parsed)
            or c['generic_parameter_completeness']['selector_gaps'] != generic - complete):
        _invalid()
    linked = c['occurrences_by_status']['linked']
    generic_calls = c['occurrence_directions']['service_dependent']
    occurrences = c['generic_linked_occurrence_services']
    unique = c['generic_linked_parameter_services']
    other_linked_parameters = c['linked_parameter_records'] - sum(unique.values())
    if (sum(occurrences.values()) != c['msg_occurrences']
            or occurrences['unavailable'] != c['msg_occurrences'] - linked
            or occurrences['not_applicable'] != linked - generic_calls
            or sum(occurrences[key] for key in GENERIC_SERVICE_DISPOSITIONS) != generic_calls
            or any(not 0 <= unique[key] <= min(services[key], occurrences[key])
                   or bool(unique[key]) != bool(occurrences[key]) for key in GENERIC_SERVICE_DISPOSITIONS)
            or not 0 <= other_linked_parameters <= min(supported - generic, linked - generic_calls)
            or bool(other_linked_parameters) != bool(linked - generic_calls)):
        _invalid()


def build_communication_context_summary(snapshot: SourceSnapshot, inventory: InventoryResult,
                                        references: ReferenceResult, access: AccessResult,
                                        tag_data: TagDataResult, result: CommunicationContextResult,
                                        revision: dict[str, Any] | None = None, *,
                                        calculations: CalculationResult | None = None) -> dict[str, Any]:
    try:
        validate_communication_context(snapshot, inventory, references, access, tag_data, result,
                                       calculations=calculations)
        constants = CONSTANTS_V3 if result.schema_version == 3 else CONSTANTS_V2 if result.schema_version == 2 else CONSTANTS
        summary = {**constants, 'status': result.status, 'coverage': deepcopy(result.coverage),
                   'tool_revision': revision if revision is not None else {'commit': None, 'worktree': 'unavailable'}}
        validate_communication_context_summary(summary)
        summary['tool_revision'] = dict(summary['tool_revision'])
        render_communication_context_summary(summary)
        return summary
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError, OverflowError):
        _invalid()


def render_communication_context_summary(summary: dict[str, Any]) -> str:
    validate_communication_context_summary(summary)
    rendered = json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=True) + '\n'
    limit = MAX_REPORT_V3_BYTES if summary['schema_version'] == 3 else MAX_REPORT_V2_BYTES if summary['schema_version'] == 2 else MAX_REPORT_BYTES
    if len(rendered) > limit:
        _invalid()
    return rendered
