"""Dependency feedback remains aggregate-only with frozen historical contracts."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import work_check
from plc_workbench.signal_context import SignalContextError
from plc_workbench.source_reuse import source_reuse_scope
from plc_workbench.summary_output import publish_summary, SummaryOutputError
from plc_workbench.targeted_sample_history import sample_envelope
from plc_workbench.work_check_tests import unavailable_result
from plc_workbench.work_check_timing import WorkCheckTiming
from test_signal_dependencies_workflow import report, maximum_width_report, SOURCE
from test_alarm_evidence_integration import report as legacy_report
from test_work_check_timing import timing_fixture
from test_unmatched_sample_report import REVISION


class SignalDependenciesWorkReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = source_reuse_scope()
        self.scope.__enter__()
        self.addCleanup(self.scope.__exit__, None, None, None)

    def test_explicit_opt_in_preserves_prior_summaries_and_frozen_samples(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(SOURCE)
            common = dict(sfc_context_schema_version=2, include_execution_context=True,
                          include_signal_context=True, include_file_operations=True)
            default = work_check._analyze(root, source, root, REVISION, **common)
            old = work_check._analyze(root, source, root, REVISION,
                signal_context_schema_version=3, include_alarm_evidence=True, **common)
            current = work_check._analyze(root, source, root, REVISION,
                signal_context_schema_version=4, include_alarm_evidence=True, **common)
            self.assertEqual(default['signal_context_summary']['schema_version'], 1)
            for result in (default, old, current):
                self.assertIsNone(result['failure_code'])
                self.assertTrue(result['private_run_saved'])
            self.assertEqual(current['signal_context_summary']['schema_version'], 4)
            self.assertEqual(default['targeted_samples']['record'], current['targeted_samples']['record'])
            self.assertEqual(old['targeted_samples'], current['targeted_samples'])
            for key in old.keys() - {'signal_context_summary', 'status'}:
                self.assertEqual(old[key], current[key], key)

    def test_work45_requires_signal4_while_work44_retains_signal3(self) -> None:
        current, old = report(), legacy_report(SOURCE)
        work_check.validate_work_check_report(current)
        work_check.validate_work_check_report(old)
        self.assertEqual(current['targeted_samples'], old['targeted_samples'])
        for key in old['analysis'].keys() - {'signal_context_summary', 'status'}:
            self.assertEqual(current['analysis'][key], old['analysis'][key], key)
        for mutate in (
            lambda p: p['analysis'].update(signal_context_summary=old['analysis']['signal_context_summary']),
            lambda p: p['analysis'].update(signal_context_summary=None),
            lambda p: p.update(schema_version=44, workflow_version='work-check-44'),
            lambda p: p['analysis']['signal_context_summary'].update(source='PRIVATE'),
            lambda p: p['analysis']['signal_context_summary']['tool_revision'].update(commit='b'*40),
            lambda p: p['analysis'].pop('alarm_evidence_summary'),
            lambda p: p['analysis'].update(file_operation_summary=None),
        ):
            candidate = deepcopy(current)
            mutate(candidate)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        old['analysis']['signal_context_summary'] = current['analysis']['signal_context_summary']
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(old)

    def test_outer_cap_and_full_frozen_envelope_reservation(self) -> None:
        self.assertLess(len(work_check._serialize_report(maximum_width_report()).encode()), 104 * 1024)
        for version in (41, 42, 43, 44, 45):
            self.assertEqual(work_check._report_limit(version), 104 * 1024)
        encoded = work_check.render_work_check_report(report())
        for marker in ('InventedCompactSignal', 'PRIVATE_SENTINEL', 'PRIVATE_ALARM_SENTINEL',
                       'PRIVATE_AUTHORED_SENTINEL', 'Delay.DN', 'condition_read_ids', 'dependent_output_ids'):
            self.assertNotIn(marker, encoded)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            destination = root / 'feedback.json'
            publish_summary(destination, encoded, input_path=root / 'invented.L5X')
            self.assertEqual(destination.read_text(), encoded)
            for payload in (report(), legacy_report(SOURCE)):
                oversized = work_check._serialize_report(payload) + ' ' * (104 * 1024)
                with self.assertRaises(SummaryOutputError):
                    publish_summary(root / 'rejected.json', oversized, input_path=root / 'invented.L5X')
                self.assertFalse((root / 'rejected.json').exists())

    def test_signal4_failure_stops_before_save_and_preserves_closed_failure_shape(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(SOURCE)
            timing = WorkCheckTiming()
            with patch.object(work_check, 'analyze_signal_context',
                    side_effect=SignalContextError('PRIVATE')) as analyze, patch.object(work_check, 'save_run') as save:
                result = work_check._analyze(root, source, root, REVISION, timings=timing,
                    sfc_context_schema_version=2, include_execution_context=True,
                    include_signal_context=True, include_file_operations=True,
                    signal_context_schema_version=4, include_alarm_evidence=True)
            save.assert_not_called()
            self.assertEqual(analyze.call_args.kwargs['schema_version'], 4)
            self.assertEqual(result['failure_code'], 'signal_context_error')
            self.assertFalse(result['private_run_saved'])
            self.assertNotIn('PRIVATE', json.dumps(result))
            self.assertIsNone(timing.snapshot()['phases_ms']['private_save'])
        result.pop('diagnostic_sample')
        result.pop('targeted_samples')
        payload = report()
        payload.update(analysis=result, status='failed', timings=timing_fixture(
            ('application_tests', 'helpers_tests', 'analysis_build')), targeted_samples=sample_envelope())
        work_check.validate_work_check_report(payload)
        for key in ('signal_context_summary', 'file_operation_summary', 'alarm_evidence_summary'):
            self.assertIsNone(result[key])
            candidate = deepcopy(payload)
            candidate['analysis'][key] = report()['analysis'][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)

    def test_not_run_retains_null_companions(self) -> None:
        payload = report()
        for key in payload['analysis']:
            payload['analysis'][key] = None
        payload['analysis'].update(status='not_run', private_run_saved=False)
        payload.update(status='failed', targeted_samples=sample_envelope(),
                       timings=timing_fixture(('application_tests', 'helpers_tests')))
        payload['tests']['application'] = unavailable_result('runner_error')
        work_check.validate_work_check_report(payload)
        for key in ('signal_context_summary', 'file_operation_summary', 'alarm_evidence_summary'):
            candidate = deepcopy(payload)
            candidate['analysis'][key] = report()['analysis'][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)

    def test_signal4_missing_prerequisites_fails_before_source_read(self) -> None:
        common = dict(include_execution_context=True, include_signal_context=True,
                      include_file_operations=True, include_alarm_evidence=True,
                      signal_context_schema_version=4)
        for key in ('include_execution_context', 'include_file_operations', 'include_alarm_evidence'):
            with self.subTest(key=key), patch.object(work_check, 'capture_snapshot') as capture:
                result = work_check._analyze(Path('.'), Path('invented.L5X'), Path('.'), REVISION,
                                             **(common | {key: False}))
            capture.assert_not_called()
            self.assertIn(result['failure_code'], {'signal_context_error', 'alarm_evidence_error'})
            self.assertFalse(result['private_run_saved'])
            self.assertIsNone(result['signal_context_summary'])


if __name__ == '__main__':
    unittest.main()
