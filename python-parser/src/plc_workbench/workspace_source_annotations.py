"""One source-owned annotation for an explicitly selected source-panel link."""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from .workspace_io_comments import IOCommentError, collect_io_annotations
from .workspace_variables import VariableIndex

if TYPE_CHECKING:
    from .workspace_field_io import FieldIOIndex

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_IDENTIFIER = re.compile(r'io_annotation_[0-9a-f]{64}', re.ASCII)


class SourceAnnotationError(ValueError):
    """Fixed errors never interpolate a requested source identifier or text."""


def select_annotation(base: VariableIndex, owner_id: str, annotation_id: str,
                      field_io: FieldIOIndex | None = None) -> dict:
    if (type(annotation_id) is not str or not _IDENTIFIER.fullmatch(annotation_id)
            or type(owner_id) is not str or type(base) is not VariableIndex):
        raise SourceAnnotationError('Choose a captured source annotation.')
    owner = base._entities.get(owner_id)
    if owner is None or not base._entity_ok.get(owner_id):
        raise SourceAnnotationError('This annotation owner is not qualified in the selected analysis.')
    note = None
    if field_io is not None and field_io.base is base:
        note = field_io.member_descriptions.annotation(owner_id, annotation_id)
        if note is None:
            cached = next((row for row in field_io._annotation_records.values()
                           if row['id'] == annotation_id and row['owner_id'] == owner_id
                           and not any(row.get(key + '_truncated') for key in
                                       ('owner_name', 'owner_suffix', 'suffix', 'locator'))), None)
            if cached is not None:
                note = dict(cached, text=field_io.annotation_texts[annotation_id])
    if note is None:
        try:
            notes = collect_io_annotations(base._source, base._captured, base._entity_ok, owner_ids={owner_id})
        except IOCommentError:
            raise SourceAnnotationError('The selected source annotation could not be read within its limits.') from None
        note = next((row for rows in notes.values() for row in rows if row['id'] == annotation_id), None)
    if note is None or note['owner_id'] != owner_id:
        raise SourceAnnotationError('This annotation does not belong to this source record in the selected analysis.')
    suffix = note.get('owner_suffix', note.get('suffix', ''))
    name = note.get('owner_name') or (base._resolver.name(owner) or '') + (suffix if note['kind'] == 'datatype_member_description' else '')
    result = {'id': annotation_id, 'owner_id': owner_id, 'owner_name': name,
        'owner_suffix': suffix, 'text': note['text'], 'kind': note['kind'],
        'language': note.get('language'), 'locator': note['locator']}
    if len(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) > MAX_RESPONSE_BYTES:
        raise SourceAnnotationError('The selected annotation exceeds the source-panel display limit.')
    return result
