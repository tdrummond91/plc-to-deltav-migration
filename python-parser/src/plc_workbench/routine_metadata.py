"""Observe declared metadata of unique JSR candidates without interpreting it.

Counts are call-weighted: a routine called twice contributes twice. Missing,
empty and explicit program Type attributes remain distinguishable. A language
envelope does not establish executable content or whether a call is legal.
"""
from __future__ import annotations

from typing import Any

from .models import InventoryResult
from .routine_targets import ROUTINE_TARGET_CONTEXTS

MAX_COUNT = 10**12
ROUTINE_METADATA_CONSTANTS = {
    'analysis_scope': 'parsed_rll_unique_jsr_candidate_metadata',
    'program_type_semantics': 'not_analyzed',
    'target_execution': 'not_analyzed',
}
PROGRAM_TYPE_BUCKETS = (
    'absent', 'empty', 'explicit_normal', 'explicit_equipment_phase',
    'explicit_sequence', 'other_explicit',
)
TARGET_LANGUAGE_BUCKETS = ('RLL', 'FBD', 'SFC', 'ST', 'missing', 'other')
_PROGRAM_TYPES = {
    'Normal': 'explicit_normal', 'EquipmentPhase': 'explicit_equipment_phase',
    'Sequence': 'explicit_sequence',
}


class RoutineMetadataError(ValueError):
    """A fixed rejection which never includes source-controlled details."""


def _invalid() -> None:
    raise RoutineMetadataError('Routine target metadata validation failed.')


def _keys(value: Any, expected: set[str]) -> None:
    if type(value) is not dict or value.keys() != expected:
        _invalid()


def _count(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= MAX_COUNT:
        _invalid()
    return value


def build_routine_target_metadata(
    inventory: InventoryResult, routine_targets: dict[str, Any],
) -> dict[str, Any]:
    """Join already canonical private candidates to declared entity metadata.

    This does not mutate source or reference records and never retains names,
    attribute strings, IDs or per-call rows. Canonical reference validation is
    the caller's responsibility; broken join evidence fails closed here too.
    """
    profile = {
        **ROUTINE_METADATA_CONSTANTS, 'total': 0,
        'by_program_type': dict.fromkeys(PROGRAM_TYPE_BUCKETS, 0),
        'by_target_language': dict.fromkeys(TARGET_LANGUAGE_BUCKETS, 0),
        'unclassified_context_by_program_type': dict.fromkeys(PROGRAM_TYPE_BUCKETS, 0),
    }
    try:
        entities = {entity.id: entity for entity in inventory.entities}
        occurrences = routine_targets['occurrences']
        if type(occurrences) is not list:
            _invalid()
        for row in occurrences:
            if type(row) is not dict:
                _invalid()
            if row['status'] != 'unique_candidate':
                continue
            program_id, target_id = row['program_id'], row['target_routine_id']
            if type(program_id) is not str or type(target_id) is not str:
                _invalid()
            program, target = entities.get(program_id), entities.get(target_id)
            if (program is None or program.kind != 'program' or target is None
                    or target.kind != 'routine' or target.parent_id != program.id
                    or target.scope_id != program.id):
                _invalid()
            if 'Type' not in program.attributes:
                program_type = 'absent'
            else:
                raw_type = program.attributes['Type']
                if type(raw_type) is not str:
                    _invalid()
                program_type = 'empty' if raw_type == '' else _PROGRAM_TYPES.get(raw_type, 'other_explicit')
            if 'Type' not in target.attributes:
                language = 'missing'
            else:
                raw_language = target.attributes['Type']
                if type(raw_language) is not str:
                    _invalid()
                language = raw_language if raw_language in TARGET_LANGUAGE_BUCKETS[:4] else 'other'
            context = row['target_context']
            if type(context) is not str or context not in ROUTINE_TARGET_CONTEXTS:
                _invalid()
            if context == 'not_analyzed' and program_type == 'explicit_normal':
                _invalid()
            profile['total'] += 1
            profile['by_program_type'][program_type] += 1
            profile['by_target_language'][language] += 1
            if context == 'not_analyzed':
                profile['unclassified_context_by_program_type'][program_type] += 1
        _count(profile['total'])
        return profile
    except (KeyError, TypeError, AttributeError):
        _invalid()


def validate_routine_target_metadata(
    value: Any, *, routine_targets: dict[str, Any], source_summary: dict[str, Any],
) -> None:
    """Validate closed counters against previously validated public aggregates.

    Repeated calls prohibit using declaration counts as an upper bound for a
    language bucket. Each positive bucket must nevertheless have at least one
    matching source envelope. Private canonical reanalysis proves each join.
    """
    try:
        _keys(value, set(ROUTINE_METADATA_CONSTANTS) | {
            'total', 'by_program_type', 'by_target_language',
            'unclassified_context_by_program_type',
        })
        for key, fixed in ROUTINE_METADATA_CONSTANTS.items():
            if type(value[key]) is not str or value[key] != fixed:
                _invalid()
        total = _count(value['total'])
        program_types = value['by_program_type']
        languages = value['by_target_language']
        unknown = value['unclassified_context_by_program_type']
        _keys(program_types, set(PROGRAM_TYPE_BUCKETS))
        _keys(languages, set(TARGET_LANGUAGE_BUCKETS))
        _keys(unknown, set(PROGRAM_TYPE_BUCKETS))
        for group in (program_types, languages, unknown):
            for count in group.values():
                _count(count)
        unique = _count(routine_targets['by_status']['unique_candidate'])
        unclassified = _count(routine_targets['unique_by_target_context']['not_analyzed'])
        other_routine = _count(routine_targets['unique_by_target_context']['other_routine'])
        current_routine = _count(routine_targets['unique_by_target_context']['current_routine'])
        distinct = _count(routine_targets['distinct_targets'])
        if (total != unique or sum(program_types.values()) != total
                or sum(languages.values()) != total or sum(unknown.values()) != unclassified
                or unknown['explicit_normal'] != 0
                or other_routine > program_types['explicit_normal']
                or current_routine > languages['RLL']
                or any(unknown[bucket] > program_types[bucket] for bucket in PROGRAM_TYPE_BUCKETS)):
            _invalid()
        source_languages = source_summary['routine_types']
        distinct_capacity = 0
        for language in TARGET_LANGUAGE_BUCKETS:
            if language == 'other':
                declarations = _count(source_languages['withheld']) + _count(source_languages['Sequence'])
            else:
                declarations = _count(source_languages[language])
            if languages[language] > 0 and declarations == 0:
                _invalid()
            distinct_capacity += min(languages[language], declarations)
        if distinct > distinct_capacity:
            _invalid()
    except (KeyError, TypeError, AttributeError):
        _invalid()
