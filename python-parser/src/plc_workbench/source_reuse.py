"""Bounded private source templates retained only within one analysis invocation.

This is an optimization, not a validation boundary. Callers validate identities
before lookup and include every applicable parser limit in their policy key.
The budget bounds retained graphs, not transient copies or total process memory.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import is_dataclass
import hashlib
import sys
from typing import Callable, Iterator, Literal, TypeVar

MAX_REUSE_BYTES = 128 * 1024 * 1024
# Covers the scope object, ContextVar token and fixed bookkeeping containers.
_SCOPE_RESERVE_BYTES = 4096
_T = TypeVar('_T')
_Kind = Literal['xml', 'inventory']


def _graph_size(value: object, limit: int) -> int | None:
    """Size retained Python graphs without recursion; unknown types fail closed."""
    total = _SCOPE_RESERVE_BYTES
    pending = [value]
    seen: set[int] = set()
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        total += sys.getsizeof(item)
        if total > limit:
            return None
        if type(item) in (dict, Counter):
            pending.extend(item.keys())
            pending.extend(item.values())
            if type(item) is not dict and hasattr(item, '__dict__'):
                pending.append(vars(item))
        elif type(item) in (list, tuple, set, frozenset):
            pending.extend(item)
        elif is_dataclass(item) and not isinstance(item, type):
            # Current source records have dictionaries; an unfamiliar slotted
            # record may retain fields outside vars(), so decline to retain it.
            if any('__slots__' in cls.__dict__ for cls in type(item).__mro__):
                return None
            pending.append(vars(item))
        elif type(item) not in (str, bytes, int, float, bool, type(None)):
            return None
    return total


class _SourceReuse:
    __slots__ = ('max_bytes', 'data', 'entries', 'rejected')

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        self.data: bytes | None = None
        self.entries: dict[_Kind, tuple[tuple, object]] = {}
        # At most two small digest/policy markers. They suppress repeated sizing
        # of successful but oversized results, never computation or validation.
        self.rejected: dict[_Kind, tuple[bytes, tuple]] = {}

    def clear(self) -> None:
        self.data = None
        self.entries.clear()
        self.rejected.clear()

    def size(self, data: bytes | None, entries: dict, rejected: dict) -> int | None:
        return _graph_size((data, entries, rejected), self.max_bytes)

    def remember_rejection(self, kind: _Kind, data: bytes, policy: tuple) -> None:
        rejected = {**self.rejected, kind: (hashlib.sha256(data).digest(), policy)}
        if self.size(self.data, self.entries, rejected) is not None:
            self.rejected = rejected

    def reuse(self, kind: _Kind, data: bytes, policy: tuple,
              build: Callable[[], _T], clone: Callable[[_T], _T]) -> _T:
        if self.max_bytes < _SCOPE_RESERVE_BYTES:
            return build()
        # One source is pinned only after an entry is admitted. A second source
        # is analyzed normally and cannot displace the first source's templates.
        if self.data is not None and self.data != data:
            return build()
        entry = self.entries.get(kind)
        if entry is not None and entry[0] == policy:
            return clone(entry[1])
        result = build()  # Exceptions are never cached or marked as oversized.
        marker = self.rejected.get(kind)
        if marker is not None and marker == (hashlib.sha256(data).digest(), policy):
            return result
        rejected = {key: value for key, value in self.rejected.items() if key != kind}
        entries = {**self.entries, kind: (policy, result)}
        if self.size(data, entries, rejected) is None:
            if kind == 'inventory':
                entries.pop('xml', None)
            if self.size(data, entries, rejected) is None:
                self.remember_rejection(kind, data, policy)
                return result
        # A miss returns the original result; only its private copy is retained.
        # Recheck the actual copy because deepcopy can change container sizes.
        entries[kind] = (policy, clone(result))
        if self.size(data, entries, rejected) is None:
            if kind == 'inventory':
                entries.pop('xml', None)
            if self.size(data, entries, rejected) is None:
                self.remember_rejection(kind, data, policy)
                return result
        self.data, self.entries, self.rejected = data, entries, rejected
        return result


_ACTIVE: ContextVar[_SourceReuse | None] = ContextVar('source_reuse', default=None)


@contextmanager
def source_reuse_scope(*, max_bytes: int = MAX_REUSE_BYTES) -> Iterator[None]:
    """Reuse one exact source within this scope; zero disables retention.

    Each nested scope is independent and restores its parent on exit. Mutable
    templates are not exposed by this API and are cleared even after failures.
    """
    if type(max_bytes) is not int or not 0 <= max_bytes <= MAX_REUSE_BYTES:
        raise ValueError('Source reuse budget must be an integer from 0 to 128 MiB.')
    state = _SourceReuse(max_bytes)
    token = _ACTIVE.set(state)
    try:
        yield
    finally:
        state.clear()
        _ACTIVE.reset(token)


def _reuse_source(kind: _Kind, data: bytes, policy: tuple,
                  build: Callable[[], _T], clone: Callable[[_T], _T]) -> _T:
    # Only native immutable bytes have trustworthy value equality. Preserve the
    # original compute path for subclasses and buffer callers without pinning
    # mutable storage or allowing overloaded equality to match another source.
    if type(data) is not bytes:
        return build()
    state = _ACTIVE.get()
    if state is None:
        return build()
    return state.reuse(kind, data, policy, build, clone)
