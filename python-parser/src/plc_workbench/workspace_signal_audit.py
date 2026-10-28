"""Closed, count-only audit of the cached Field I/O view.

Only fixed keys, booleans and counts leave this boundary. Never serialize source
identifiers, prose, addresses, values, filenames or instruction sequences here.
This describes captured RLL references, not live wiring or equipment activity.
"""
from __future__ import annotations

from .workspace_field_signals import FieldSignalIndex
from .workspace_signal_context import description_origin

_USAGE = ('referenced', 'possible_indirect', 'not_found', 'unknown')
_ORIGINS = ('channel', 'alias', 'backing', 'module', 'missing')
_TYPES = ('ai', 'ao', 'di', 'do', 'unknown')
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
    empty = recovered_signals = recovered_occurrences = conflicts = 0
    for identifier, signal in index.signals.items():
        address = index.field_io.addresses[identifier]
        usage = index.usage.status(address)
        origin = description_origin(index.field_io, address)
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
    return {'schema_version': 1,
        'inventory': {'field_signal_addresses': len(index.signals),
            'captured_addresses': len(index.field_io.addresses),
            'excluded_non_signal_addresses': index.coverage['excluded_addresses']},
        'usage_counts': by_usage,
        'description_origins_by_usage': by_origin,
        'field_types_by_usage': by_type,
        'described_result_contexts_by_usage': contexts,
        'description_conflicts': conflicts,
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
