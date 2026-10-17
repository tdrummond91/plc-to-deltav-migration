"""Closed workflow timings use invented source and deterministic clocks."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from functools import lru_cache
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import work_check
from plc_workbench.sfc_context_summary import build_sfc_context_summary
from plc_workbench.source import SourceError
from plc_workbench.storage import StorageError
from plc_workbench.summary_output import publish_summary
from plc_workbench.work_check_timing import (
    MAX_TIMING_MS, PHASES, WorkCheckTiming, WorkCheckTimingError, validate_timings,
)
from test_binding_context_workflow import source
from test_sfc_context_workflow import (
    captured, context_inputs, report as old_report, maximum_width_report as old_maximum,
)
from test_unmatched_sample_report import REVISION

SOURCE = source('XIC(A)OTE(A);')


class Clock:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> int:
        return self.value


def timing_fixture(attempted: tuple[str, ...] = PHASES) -> dict:
    return {'schema_version': 1, 'total_ms': len(attempted),
            'phases_ms': {name: 1 if name in attempted else None for name in PHASES}}


@lru_cache(maxsize=1)
def _report() -> dict:
    payload = old_report(SOURCE)
    parts = captured(SOURCE)
    payload.update(schema_version=38, workflow_version='work-check-38', timings=timing_fixture())
    payload['analysis']['sfc_context_summary'] = build_sfc_context_summary(
        *context_inputs(parts), parts[22], revision=REVISION, schema_version=2)
    return payload


def report() -> dict:
    return deepcopy(_report())


def maximum_width_report() -> dict:
    payload = old_maximum()
    payload.update(schema_version=38, workflow_version='work-check-38',
                   timings={'schema_version': 1, 'total_ms': MAX_TIMING_MS,
                            'phases_ms': dict.fromkeys(PHASES, MAX_TIMING_MS)})
    def grow(value):
        if type(value) is int:
            return 10**12
        if type(value) is dict:
            return {key: grow(child) for key, child in value.items()}
        return value
    payload['analysis']['sfc_context_summary'] = grow(report()['analysis']['sfc_context_summary'])
    return payload


class WorkCheckTimingTests(unittest.TestCase):
    def test_monotonic_intervals_floor_milliseconds_and_leave_unattempted_null(self) -> None:
        clock = Clock()
        timing = WorkCheckTiming(clock=clock)
        clock.value = 700_000
        with timing.phase('application_tests'):
            clock.value = 2_500_000
        clock.value = 3_100_000
        with timing.phase('helpers_tests'):
            clock.value = 3_900_000
        clock.value = 5_200_000
        result = timing.snapshot()
        self.assertEqual(result['total_ms'], 5)
        self.assertEqual(result['phases_ms'], dict.fromkeys(PHASES) | {
            'application_tests': 1, 'helpers_tests': 0})
        validate_timings(result)
        clock.value = 100_000_000
        result['phases_ms']['application_tests'] = 90
        self.assertEqual(timing.snapshot()['total_ms'], 5)
        self.assertEqual(timing.snapshot()['phases_ms']['application_tests'], 1)

    def test_failed_attempt_retains_duration_and_original_exception(self) -> None:
        clock = Clock()
        timing = WorkCheckTiming(clock=clock)
        failure = RuntimeError('PRIVATE_FAILURE')
        with self.assertRaises(RuntimeError) as caught:
            with timing.phase('analysis_build'):
                clock.value = 4_900_000
                raise failure
        self.assertIs(caught.exception, failure)
        result = timing.snapshot()
        self.assertEqual(result['phases_ms']['analysis_build'], 4)
        self.assertIsNone(result['phases_ms']['private_save'])
        self.assertNotIn('PRIVATE_FAILURE', json.dumps(result))

    def test_phase_identity_overlap_duplicates_and_post_snapshot_attempts_are_rejected(self) -> None:
        clock = Clock()
        timing = WorkCheckTiming(clock=clock)
        with self.assertRaises(WorkCheckTimingError):
            with timing.phase('PRIVATE_NEW_PHASE'):
                pass
        with timing.phase('application_tests'):
            with self.assertRaises(WorkCheckTimingError):
                timing.snapshot()
            with self.assertRaises(WorkCheckTimingError):
                with timing.phase('helpers_tests'):
                    pass
        with self.assertRaises(WorkCheckTimingError):
            with timing.phase('application_tests'):
                pass
        timing.snapshot()
        with self.assertRaises(WorkCheckTimingError):
            with timing.phase('helpers_tests'):
                pass

    def test_closed_numeric_contract_rejects_non_native_numbers_bounds_and_extra_keys(self) -> None:
        for mutate in (
            lambda p: p.update(schema_version=True),
            lambda p: p.update(total_ms=True),
            lambda p: p.update(total_ms=-1),
            lambda p: p.update(total_ms=1.0),
            lambda p: p.update(total_ms=MAX_TIMING_MS + 1),
            lambda p: p.update(total_ms=5),
            lambda p: p.update(source='PRIVATE'),
            lambda p: p['phases_ms'].update(application_tests=False),
            lambda p: p['phases_ms'].update(application_tests=-1),
            lambda p: p['phases_ms'].update(application_tests=0.1),
            lambda p: p['phases_ms'].update(application_tests=MAX_TIMING_MS + 1),
            lambda p: p['phases_ms'].update(PRIVATE=0),
            lambda p: p['phases_ms'].pop('sample_replay'),
        ):
            candidate = timing_fixture()
            mutate(candidate)
            with self.subTest(mutate=mutate), self.assertRaises(WorkCheckTimingError):
                validate_timings(candidate)

    def test_work38_requires_timing_and_summary2_while_historical_work37_stays_closed(self) -> None:
        current, old = report(), old_report(SOURCE)
        work_check.validate_work_check_report(current)
        work_check.validate_work_check_report(old)
        for mutate in (
            lambda p: p.pop('timings'),
            lambda p: p.update(timings=None),
            lambda p: p['analysis'].update(sfc_context_summary=old['analysis']['sfc_context_summary']),
            lambda p: p.update(schema_version=37, workflow_version='work-check-37'),
            lambda p: p['timings']['phases_ms'].update(sample_replay=None),
            lambda p: p['timings']['phases_ms'].update(application_tests=None),
        ):
            candidate = report()
            mutate(candidate)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        for key in old['analysis'].keys() - {'sfc_context_summary'}:
            self.assertEqual(current['analysis'][key], old['analysis'][key])
        self.assertEqual(current['targeted_samples'], old['targeted_samples'])
        self.assertEqual(current['analysis']['sfc_context_summary']['coverage'],
                         old['analysis']['sfc_context_summary']['coverage'])

    def test_failed_and_not_run_phase_presence_is_consistent(self) -> None:
        from test_save_diagnostics import failed_report
        payload = failed_report(38, 'read_error')
        payload['timings'] = timing_fixture(PHASES[:3])
        work_check.validate_work_check_report(payload)
        for phases in (PHASES[:2], PHASES[:3] + ('summary_build',), PHASES[:5]):
            candidate = deepcopy(payload)
            candidate['timings'] = timing_fixture(phases)
            with self.subTest(phases=phases), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        payload['analysis'].update(status='not_run', failure_code=None)
        payload['tests']['application']['status'] = 'failed'
        payload['tests']['application']['counts']['failures'] = 1
        payload['tests']['application']['failed_test_ids'] = ['invented.Case.test_failure']
        payload['timings'] = timing_fixture(PHASES[:2])
        work_check.validate_work_check_report(payload)
        payload['timings'] = timing_fixture(PHASES[:3])
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_timed_analysis_preserves_default_contract_and_frozen_sample_replay(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            path = root / 'invented.L5X'
            path.write_bytes(SOURCE)
            clock = Clock()
            timing = WorkCheckTiming(clock=clock)
            with patch.object(work_check, 'save_run', return_value=root / 'saved'):
                first = work_check._analyze(root, path, root, REVISION)
                second = work_check._analyze(root, path, root, REVISION, timings=timing)
            self.assertIsNone(second['failure_code'])
            self.assertEqual(second['sfc_context_summary']['schema_version'], 1)
            self.assertEqual(first.pop('targeted_samples')['record'], second.pop('targeted_samples')['record'])
            self.assertEqual(first, second)
            self.assertEqual(timing.snapshot()['phases_ms'], dict.fromkeys(PHASES, 0) | {
                'application_tests': None, 'helpers_tests': None})

    def test_analysis_failures_keep_attempted_duration_and_do_not_start_later_phases(self) -> None:
        for target, error, code, attempted in (
            ('capture_snapshot', SourceError('PRIVATE'), 'read_error', PHASES[2:3]),
            ('save_run', StorageError('PRIVATE'), 'save_error', PHASES[2:4]),
            ('build_reference_summary', ValueError('PRIVATE'), 'summary_error', PHASES[2:5]),
        ):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
                root = Path(folder).resolve()
                path = root / 'invented.L5X'
                path.write_bytes(SOURCE)
                clock = Clock()
                timing = WorkCheckTiming(clock=clock)
                def fail(*args, **kwargs):
                    clock.value += 3_000_000
                    raise error
                with patch.object(work_check, 'save_run', return_value=root / 'saved'), \
                        patch.object(work_check, target, side_effect=fail):
                    result = work_check._analyze(root, path, root, REVISION, timings=timing)
                self.assertEqual(result['failure_code'], code)
                phases = timing.snapshot()['phases_ms']
                self.assertEqual({name for name, value in phases.items() if value is not None}, set(attempted))
                self.assertEqual(phases[attempted[-1]], 3)
                self.assertNotIn('PRIVATE', json.dumps(result))

    def test_progress_is_visible_and_closed_stdout_cannot_replace_a_failure(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            work_check._phase_elapsed('analysis_build', 1234)
        self.assertEqual(output.getvalue(), 'Analysis build: 1.234 s elapsed.\n')
        failure = RuntimeError('PRIVATE')
        timing = WorkCheckTiming(clock=Clock(), announce=work_check._phase_elapsed)
        with patch.object(work_check, 'print', side_effect=BrokenPipeError), self.assertRaises(RuntimeError) as caught:
            with timing.phase('analysis_build'):
                raise failure
        self.assertIs(caught.exception, failure)
        self.assertEqual(timing.snapshot()['phases_ms']['analysis_build'], 0)

    def test_publication_retains_80k_cap_and_maximum_width_has_room(self) -> None:
        maximum = maximum_width_report()
        self.assertLess(len(work_check._serialize_report(maximum).encode()), 80 * 1024)
        self.assertEqual(work_check._report_limit(38), 80 * 1024)
        encoded = work_check.render_work_check_report(report())
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            publish_summary(root / 'feedback.json', encoded, input_path=root / 'invented.L5X')
            self.assertEqual((root / 'feedback.json').read_text(), encoded)


if __name__ == '__main__':
    unittest.main()
