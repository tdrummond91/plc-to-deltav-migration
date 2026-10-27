"""Small, source-free diagnostics for authenticated workspace projections.

Only fixed stage/reason identifiers and bounded integer measurements cross the
API boundary. Never retain exception objects, messages, filenames or source
snippets here; they can contain proprietary engineering information.
"""
from __future__ import annotations

from typing import Any

_STAGES = frozenset({'evidence', 'source', 'inventory', 'references', 'calculations',
    'access', 'tag_data', 'variable_index', 'field_io', 'field_signals', 'io_annotations'})
_REASONS = {
    'invalid_evidence': 'Saved evidence did not pass the workspace consistency checks.',
    'projection_failed': 'The workspace could not build this view from the saved evidence.',
    'source_bytes_limit': 'The saved source exceeds the workspace source-size limit.',
    'artifact_bytes_limit': 'A saved analysis artifact exceeds the workspace loading limit.',
    'artifact_unavailable': 'A required saved analysis artifact is missing or could not be loaded.',
    'index_bytes_limit': 'The saved evidence exceeds this view\'s retained-data limit.',
    'address_count_limit': 'The saved evidence exceeds the field-address count limit.',
    'signal_count_limit': 'The saved evidence exceeds the field-signal count limit.',
    'annotation_count_limit': 'The saved evidence exceeds the I/O annotation count limit.',
    'annotation_chars_limit': 'The saved evidence exceeds the I/O annotation text limit.',
}
_MAX_MEASUREMENT = 2 ** 63 - 1


def diagnostic(stage: Any, code: Any, actual: Any = None, limit: Any = None) -> dict:
    """Return only recognized identifiers and safe integer measurements."""
    if (type(stage) is not str or stage not in _STAGES
            or type(code) is not str or code not in _REASONS):
        return {'stage': 'evidence', 'reason': 'invalid_evidence'}
    result: dict[str, str | int] = {'stage': stage, 'reason': code}
    for key, value in (('actual', actual), ('limit', limit)):
        if type(value) is int and 0 <= value <= _MAX_MEASUREMENT:
            result[key] = value
    return result


def evidence_notice(value: Any) -> str:
    """Explain a sanitized diagnostic without interpolating arbitrary strings."""
    if type(value) is not dict:
        value = {}
    clean = diagnostic(value.get('stage'), value.get('reason'),
                       value.get('actual'), value.get('limit'))
    reason = clean['reason']
    text = _REASONS[reason]
    if 'actual' in clean and 'limit' in clean:
        text += f" Measured {clean['actual']:,}; limit {clean['limit']:,}."
    if reason == 'index_bytes_limit':
        text += ' Index construction stopped at this limit; the complete index may require more space.'
    if reason.endswith('_limit'):
        text += ' This workspace view needs a capacity fix to load the evidence.'
    return f"{text} [{clean['stage']}/{reason}]"
