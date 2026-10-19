"""Reserve one immutable public-safe sample request before report publication.

Published reports travel between checkouts; the local reservation covers failed
or uncommitted publication. Neither contains source identifiers or a private
mapping. This is a bounded, single-owner filesystem workflow, not proof against
deletion of both the entire published history and the private reservation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Callable

from .targeted_samples import MAX_BYTES, REQUEST_ID, render_targeted_samples_json, validate_targeted_samples

MAX_HISTORY_FILES = 512
MAX_HISTORY_BYTES = 32 * 1024 * 1024
MAX_WORK_REPORT_BYTES = 64 * 1024


class TargetedSampleHistoryError(ValueError):
    """A fixed diagnostic safe for the public envelope."""


def _invalid() -> None:
    raise TargetedSampleHistoryError('Targeted sample history is unavailable.')


def sample_envelope(status: str = 'not_run', record: dict | None = None, *, reason: str | None = None) -> dict:
    value = {'schema_version': 1, 'status': status,
             'reason': reason or ('history_error' if status == 'unavailable' else 'none'), 'record': record}
    validate_sample_envelope(value)
    return value


def validate_sample_envelope(value: Any) -> None:
    if (type(value) is not dict or value.keys() != {'schema_version', 'status', 'reason', 'record'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or type(value['status']) is not str
            or value['status'] not in {'selected', 'replayed', 'unavailable', 'not_run'}
            or type(value['reason']) is not str):
        _invalid()
    if (value['reason'] not in {'history_error', 'selection_error'} if value['status'] == 'unavailable'
            else value['reason'] != 'none'):
        _invalid()
    if value['status'] in {'selected', 'replayed'}:
        validate_targeted_samples(value['record'])
    elif value['record'] is not None:
        _invalid()


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            _invalid()
        value[key] = item
    return value


def _safe(path: Path, *, directory: bool = False, missing: bool = False) -> bool:
    """Reject links/junctions in every existing ancestor before filesystem I/O."""
    absolute = path.absolute()
    if absolute.resolve() != absolute:
        _invalid()
    for current in (*reversed(absolute.parents), absolute):
        try:
            info = current.lstat()
        except FileNotFoundError:
            if missing:
                return False
            raise
        if (stat.S_ISLNK(info.st_mode)
                or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024)):
            _invalid()
        if current != absolute and not stat.S_ISDIR(info.st_mode):
            _invalid()
        if current == absolute and not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
            _invalid()
    return True


def _read(path: Path, limit: int) -> tuple[dict, int]:
    _safe(path)
    before = path.stat()
    if before.st_size > limit:
        _invalid()
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            _invalid()
        raw = stream.read(limit + 1)
    _safe(path)
    if len(raw) > limit:
        _invalid()
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs)
    if type(value) is not dict:
        _invalid()
    return value, len(raw)


def _history(root: Path) -> tuple[dict | None, bool]:
    from .work_check import validate_work_check_report
    directory = root / 'public' / 'inspection'
    if not _safe(directory, directory=True, missing=True):
        return None, False
    # Bound directory traversal before retaining paths; do not recurse or read
    # unrelated inspection files. A matching symlink is an error, not ignored.
    paths = []
    with os.scandir(directory) as entries:
        for entry in entries:
            if entry.name.startswith('work-check-') and entry.name.endswith('.json'):
                paths.append(Path(entry.path))
                if len(paths) > MAX_HISTORY_FILES:
                    _invalid()
    record = None
    established = False
    total_bytes = 0
    for path in sorted(paths):
        report, size = _read(path, MAX_WORK_REPORT_BYTES)
        total_bytes += size
        if total_bytes > MAX_HISTORY_BYTES:
            _invalid()
        validate_work_check_report(report)
        if report['schema_version'] < 28:
            continue
        envelope = report['targeted_samples']
        established |= envelope['status'] in {'selected', 'replayed'} or envelope['reason'] == 'history_error'
        candidate = envelope['record']
        if candidate is not None:
            if record is not None and record != candidate:
                _invalid()
            record = candidate
    _safe(directory, directory=True)
    return record, established


def _reserve(path: Path, record: dict) -> bool:
    """Return True for our new reservation; an equal atomic winner is replayed."""
    rendered = render_targeted_samples_json(record).encode('utf-8')
    parent = path.parent
    _safe(parent, directory=True, missing=True)
    parent.mkdir(parents=True, exist_ok=True)
    _safe(parent, directory=True)
    temporary = None
    try:
        descriptor, filename = tempfile.mkstemp(prefix='.rung-cases-', suffix='.pending', dir=parent)
        temporary = Path(filename)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        _safe(parent, directory=True)
        try:
            os.link(temporary, path)
            return True
        except FileExistsError:
            winner, _ = _read(path, MAX_BYTES)
            validate_targeted_samples(winner)
            if winner != record:
                _invalid()
            return False
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def resolve_targeted_samples(root: Path, builder: Callable[[], dict]) -> dict:
    """Reuse the immutable request, or reserve its only selection before release.

    History errors withhold only samples. Parser artifacts and count reports
    continue normally. No source path, source hash, or private mapping is saved.
    """
    try:
        root = root.absolute()
        _safe(root, directory=True)
        published, established = _history(root)
        reservation = root / 'confidential' / 'work-check-samples' / f'{REQUEST_ID}.json'
        private = None
        if _safe(reservation, missing=True):
            private, _ = _read(reservation, MAX_BYTES)
            validate_targeted_samples(private)
        if private is not None and published is not None and private != published:
            _invalid()
        record = private if private is not None else published
        if record is not None:
            if private is None:
                _reserve(reservation, record)
            return sample_envelope('replayed', record)
        if established:
            _invalid()
        try:
            record = builder()
            validate_targeted_samples(record)
        except Exception:
            return sample_envelope('unavailable', reason='selection_error')
        selected = _reserve(reservation, record)
        return sample_envelope('selected' if selected else 'replayed', record)
    except Exception:
        # Includes filesystem/JSON/parser failures; never emit raw text or paths.
        return sample_envelope('unavailable')
