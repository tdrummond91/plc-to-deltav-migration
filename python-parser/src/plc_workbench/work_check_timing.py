"""Bounded monotonic workflow durations, with no source-bearing metadata.

The snapshot covers run_check entry through the end of analysis, excluding the
uv bootstrap and subsequent rendering, publication and local Git commit.
Durations are floored to milliseconds. Nonoverlapping phase intervals therefore
sum to no more than the elapsed total without a rounding allowance.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from time import perf_counter_ns
from typing import Any, Callable, Iterator

MAX_TIMING_MS = 31 * 24 * 60 * 60 * 1000
PHASES = (
    "application_tests", "helpers_tests", "analysis_build", "private_save",
    "summary_build", "sample_replay",
)


class WorkCheckTimingError(ValueError):
    """Fixed rejection for unsupported or inconsistent duration data."""


def _invalid() -> None:
    raise WorkCheckTimingError("Work-check timing data is invalid.") from None


def validate_timings(value: Any) -> None:
    if (type(value) is not dict or value.keys() != {"schema_version", "total_ms", "phases_ms"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or type(value["total_ms"]) is not int or not 0 <= value["total_ms"] <= MAX_TIMING_MS
            or type(value["phases_ms"]) is not dict or value["phases_ms"].keys() != set(PHASES)):
        _invalid()
    durations = value["phases_ms"].values()
    if (any(item is not None and (type(item) is not int or not 0 <= item <= MAX_TIMING_MS)
            for item in durations)
            or sum(item for item in durations if item is not None) > value["total_ms"]):
        _invalid()


class WorkCheckTiming:
    """Record each attempted phase once, including exceptions leaving a phase."""

    def __init__(self, *, clock: Callable[[], int] | None = None,
                 announce: Callable[[str, int], None] | None = None) -> None:
        self._clock = perf_counter_ns if clock is None else clock
        self._announce = announce
        self._started = self._clock()
        self._active: str | None = None
        self._durations: dict[str, int | None] = dict.fromkeys(PHASES)
        self._snapshot: dict[str, Any] | None = None

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        if (type(name) is not str or name not in self._durations or self._active is not None
                or self._snapshot is not None or self._durations[name] is not None):
            _invalid()
        self._active = name
        started = self._clock()
        try:
            yield
        finally:
            elapsed = (self._clock() - started) // 1_000_000
            self._active = None
            if not 0 <= elapsed <= MAX_TIMING_MS:
                _invalid()
            self._durations[name] = elapsed
            if self._announce is not None:
                self._announce(name, elapsed)

    def snapshot(self) -> dict[str, Any]:
        if self._active is not None:
            _invalid()
        if self._snapshot is None:
            self._snapshot = {"schema_version": 1,
                              "total_ms": (self._clock() - self._started) // 1_000_000,
                              "phases_ms": dict(self._durations)}
            validate_timings(self._snapshot)
        return deepcopy(self._snapshot)
