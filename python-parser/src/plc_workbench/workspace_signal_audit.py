"""Closed, count-only audit of the cached Field I/O view.

Only fixed keys, booleans and counts leave this boundary. Never serialize source
identifiers, prose, addresses, values, filenames or instruction sequences here.
This describes captured RLL references, not live wiring or equipment activity.
"""
from __future__ import annotations

from .workspace_field_signals import FieldSignalIndex
from .workspace_signal_context import description_origin

_USAGE = ('referenced', 'possible_indirect', 'not_found', 'unknown')
_ORIGINS = ('channel', 'alias', 'type_member', 'containing_member', 'backing', 'module', 'missing')
_TYPES = ('ai', 'ao', 'di', 'do', 'unknown')
_MEMBER_REASONS = ('available', 'no_description', 'no_type_definition', 'member_not_declared',
                   'conflict', 'unsupported_path', 'capacity')
_SCOPES = ('exact_member_comment', 'exact_alias_description', 'declared_member_description',
           'containing_member_comment', 'backing_description', 'backing_alias_description', 'module_description')
_CASES = ('used_missing', 'used_inherited', 'unreferenced_missing', 'unreferenced_inherited',
          'type_member_inherited', 'result_context')
_GAPS = ('missing_logic', 'partial_export', 'missing_access', 'unparsed_rungs',
         'unsupported_routines', 'protected_logic', 'incomplete_routines',
         'unqualified_source', 'unsupported_instructions', 'opaque_expressions',
         'unscanned_index_expressions', 'unresolved_references', 'usage_index_limit')


def build_audit(index: FieldSignalIndex) -> dict:
    """Count every signal, independent of paging, text search or view filters."""
    if type(index) is not FieldSignalIndex:
        raise ValueError('An authenticated field signal index is required.')
    by_usage = {kind: 0 for kind in _USAGE}
    by_origin = {kind: {origin: 0 for origin in _ORIGINS} for kind in _USAGE}
    by_type = {kind: {field_type: 0 for field_type in _TYPES} for kind in _USAGE}
    contexts = {kind: 0 for kind in _USAGE}
    member_reasons = {kind: 0 for kind in _MEMBER_REASONS}
    candidate_scopes = {kind: 0 for kind in _SCOPES}
    cases = {kind: {'present': False} for kind in _CASES}
    truncated_candidates = 0
    empty = recovered_signals = recovered_occurrences = conflicts = 0
    for identifier in index._ordered:
        signal = index.signals[identifier]
        address = index.field_io.addresses[identifier]
        usage = index.usage.status(address)
        origin = description_origin(index.field_io, address)
        reason = index.field_io.member_descriptions.lookup_reason(address['root_id'], address['suffix'])
        member_reasons[reason] += 1
        scopes = {kind: 0 for kind in _SCOPES}
        for _, _, scope in index.field_io._description_candidates[identifier]:
            scopes[scope] += 1
        for scope, count in scopes.items():
            candidate_scopes[scope] += int(count > 0)
        selection = address['description_selection']
        truncated_candidates += int(selection['candidates_truncated'])
        has_context = identifier in index.context._signals
        inherited = origin['kind'] in {'containing_member', 'backing', 'module'}
        buckets = {'used_missing': usage == 'referenced' and origin['kind'] == 'missing' and not has_context,
            'used_inherited': usage == 'referenced' and inherited and not has_context,
            'unreferenced_missing': usage == 'not_found' and origin['kind'] == 'missing',
            'unreferenced_inherited': usage == 'not_found' and inherited,
            'type_member_inherited': origin['kind'] == 'type_member', 'result_context': has_context}
        for bucket, matches in buckets.items():
            if matches and not cases[bucket]['present']:
                member = index.field_io.member_descriptions.diagnostic(address['root_id'], address['suffix'])
                # These are anonymous fact profiles, not source excerpts. No
                # identifiers, XML, prose, values or rung patterns leave here.
                cases[bucket] = {'present': True,
                    'usage_flags': {kind: usage == kind for kind in _USAGE},
                    'origin_flags': {kind: origin['kind'] == kind for kind in _ORIGINS},
                    'specific_description': origin['specific'], 'conflicting_description': origin['conflict'],
                    'result_context': has_context, 'alias_count': len(address['aliases']),
                    'direct_reference_count': len(address['uses']),
                    'direct_rung_count': len({use['rung_id'] for use in address['uses']}),
                    'candidate_count': selection['candidate_count'],
                    'candidate_list_truncated': selection['candidates_truncated'],
                    'retained_candidate_scope_counts': dict(scopes),
                    'member_lookup_flags': {kind: reason == kind for kind in _MEMBER_REASONS},
                    'member_facts': {key: member[key] for key in ('root_type_declared', 'captured_layout',
                        'path_static', 'member_depth', 'array_rank', 'description_count')}}
        by_usage[usage] += 1
        by_origin[usage][origin['kind']] += 1
        by_type[usage][signal['field_type']] += 1
        contexts[usage] += int(identifier in index.context._signals)
        conflicts += int(origin['conflict'])
        empty += int(not signal['informative'])
        if signal.get('rack_mapping'):
            recovered_signals += 1
            recovered_occurrences += len(address['uses'])
    scan = index.usage.scan_summary()
    gaps = set(scan['gap_reasons']) | set(scan['role_gap_reasons'])
    return {'schema_version': 2,
        'inventory': {'field_signal_addresses': len(index.signals),
            'captured_addresses': len(index.field_io.addresses),
            'excluded_non_signal_addresses': index.coverage['excluded_addresses']},
        'usage_counts': by_usage,
        'description_origins_by_usage': by_origin,
        'field_types_by_usage': by_type,
        'described_result_contexts_by_usage': contexts,
        'description_conflicts': conflicts,
        'description_diagnostics': {'member_lookup_counts': member_reasons,
            'signals_with_retained_candidate_scope': candidate_scopes,
            'signals_with_truncated_candidate_list': truncated_candidates,
            'anonymous_cases': cases},
        'empty_unreferenced_signals_before_saved_review_protection': empty,
        'rack_source_correspondence': {'signals': recovered_signals,
            'source_occurrences_on_mapped_signals': recovered_occurrences,
            'recovered_addresses': index.field_io.coverage['rack_recovered_addresses'],
            'recovered_reference_occurrences': index.field_io.coverage['rack_recovered_reference_uses']},
        'scan': {'rungs_total': scan['rungs_total'], 'rungs_scanned': scan['rungs_scanned'],
            'rungs_not_scanned': scan['rungs_not_scanned'], 'available': scan['available'],
            'complete': scan['complete'], 'result_context_available': index.context.available,
            'known_gap_flags': {key: key in gaps for key in _GAPS},
            'other_gap_count': len(gaps - set(_GAPS))}}
