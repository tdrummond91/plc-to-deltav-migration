"""Signal pattern feedback stays aggregate-only and preserves historical contracts."""
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
from plc_workbench.signal_context_summary import validate_signal_context_summary
from plc_workbench.source_reuse import source_reuse_scope
from plc_workbench.summary_output import publish_summary, SummaryOutputError
from plc_workbench.work_check_timing import WorkCheckTiming
from test_signal_patterns_workflow import report, maximum_width_report, SOURCE
from test_file_operation_workflow import report as legacy_report
from test_work_check_timing import timing_fixture
from test_unmatched_sample_report import REVISION


class SignalPatternsWorkReportTests(unittest.TestCase):
    def test_timer_patterns_require_eligible_stateful_source_populations(self) -> None:
        counter_only = SOURCE.replace(b'TIMER', b'COUNTER').replace(b'TON(Delay', b'CTU(Delay')
        counter_declaration = SOURCE.replace(b'TIMER', b'COUNTER')
        counter_family = SOURCE.replace(b'TON(Delay', b'CTU(Delay')
        outside_bounds = SOURCE.replace(b'Name="Delay" DataType="TIMER"',
                                        b'Name="Delay" DataType="TIMER" Dimensions="1"')
        outside_bounds = outside_bounds.replace(b'TON(Delay,', b'TON(Delay[1],').replace(
            b'XIC(Delay.DN)', b'XIC(Delay[1].DN)')
        for name, data, missing in (
            ('counter_only', counter_only, ('objects_by_family', 'timer')),
            ('counter_declaration', counter_declaration, ('declarations_by_kind', 'timer')),
            ('counter_family', counter_family, ('objects_by_family', 'timer')),
            ('outside_bounds', outside_bounds, ('bounds_by_status', 'scalar')),
        ):
            with self.subTest(source=name):
                payload = report(data)
                work_check.validate_work_check_report(payload)
                stateful = payload['analysis']['stateful_object_summary']['coverage']
                self.assertEqual(stateful[missing[0]][missing[1]], 0)
                if name == 'outside_bounds':
                    self.assertEqual(stateful['bounds_by_status']['static_in_bounds'], 0)
                summary = payload['analysis']['signal_context_summary']
                counts = summary['coverage']
                self.assertEqual(sum(counts['pattern_timer_contacts_by_member'].values()), 0)
                counts['pattern_timer_contacts_by_member']['DN'] = 1
                counts['pattern_outputs_with_timer_contacts'] = 1
                # Counts are locally feasible; only the other source summary
                # exposes the missing timer/type/bounds evidence.
                validate_signal_context_summary(summary)
                with self.assertRaises(ValueError):
                    work_check.validate_work_check_report(payload)

    def test_explicit_analysis_defaults_to_signal1_and_latest_opt_in_changes_only_signal(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()), source_reuse_scope():
            root = Path(folder).resolve()
            source = root/'invented.L5X'
            source.write_bytes(SOURCE)
            common = dict(sfc_context_schema_version=2, include_execution_context=True,
                          include_signal_context=True, include_file_operations=True)
            old = work_check._analyze(root, source, root, REVISION, **common)
            current = work_check._analyze(root, source, root, REVISION,
                                          signal_context_schema_version=2, **common)
            self.assertIsNone(old['failure_code'])
            self.assertIsNone(current['failure_code'])
            self.assertTrue(old['private_run_saved'])
            self.assertTrue(current['private_run_saved'])
            self.assertEqual(old['signal_context_summary']['schema_version'], 1)
            self.assertEqual(current['signal_context_summary']['schema_version'], 2)
            self.assertEqual(old['targeted_samples']['record'], current['targeted_samples']['record'])
            self.assertEqual((old['targeted_samples']['status'], current['targeted_samples']['status']),
                             ('selected', 'replayed'))
            for key in old.keys() - {'signal_context_summary', 'status', 'targeted_samples'}:
                self.assertEqual(old[key], current[key], key)

    def test_work42_requires_signal2_while_work41_retains_signal1(self) -> None:
        current, old = report(), legacy_report(SOURCE)
        work_check.validate_work_check_report(current)
        work_check.validate_work_check_report(old)
        self.assertEqual(current['targeted_samples'], old['targeted_samples'])
        for key in old['analysis'].keys() - {'signal_context_summary', 'status'}:
            self.assertEqual(current['analysis'][key], old['analysis'][key], key)
        for mutate in (
            lambda p: p['analysis'].update(signal_context_summary=old['analysis']['signal_context_summary']),
            lambda p: p['analysis'].update(signal_context_summary=None),
            lambda p: p.update(schema_version=41, workflow_version='work-check-41'),
            lambda p: p['analysis']['signal_context_summary'].update(source='PRIVATE'),
            lambda p: p['analysis']['signal_context_summary']['tool_revision'].update(commit='b'*40),
        ):
            candidate = deepcopy(current)
            mutate(candidate)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        old['analysis']['signal_context_summary'] = current['analysis']['signal_context_summary']
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(old)

    def test_outer_cap_and_full_frozen_envelope_reservation(self) -> None:
        self.assertLess(len(work_check._serialize_report(maximum_width_report()).encode()), 104*1024)
        self.assertEqual(work_check._report_limit(42), 104*1024)
        self.assertEqual(work_check._report_limit(41), 104*1024)
        self.assertEqual(work_check._report_limit(40), 96*1024)
        encoded = work_check.render_work_check_report(report())
        for marker in ('InventedCompactSignal', 'PRIVATE_SENTINEL', 'Delay.DN'):
            self.assertNotIn(marker, encoded)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            destination = root / 'feedback.json'
            publish_summary(destination, encoded, input_path=root/'invented.L5X')
            self.assertEqual(destination.read_text(), encoded)
            for payload in (report(), legacy_report(SOURCE)):
                oversized = work_check._serialize_report(payload) + ' '*(104*1024)
                with self.assertRaises(SummaryOutputError):
                    publish_summary(root/'rejected.json', oversized, input_path=root/'invented.L5X')
                self.assertFalse((root/'rejected.json').exists())

    def test_signal2_failure_stops_before_save_and_preserves_closed_failure_shape(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            source = root/'invented.L5X'
            source.write_bytes(SOURCE)
            timing = WorkCheckTiming()
            with source_reuse_scope(), patch.object(work_check, 'analyze_signal_context',
                    side_effect=SignalContextError('PRIVATE')) as analyze, patch.object(work_check, 'save_run') as save:
                result = work_check._analyze(root, source, root, REVISION, timings=timing,
                                            sfc_context_schema_version=2, include_execution_context=True,
                                            include_signal_context=True, include_file_operations=True,
                                            signal_context_schema_version=2)
            save.assert_not_called()
            self.assertEqual(analyze.call_args.kwargs['schema_version'], 2)
            self.assertEqual(result['failure_code'], 'signal_context_error')
            self.assertIsNone(result['signal_context_summary'])
            self.assertIsNone(result['file_operation_summary'])
            self.assertFalse(result['private_run_saved'])
            self.assertNotIn('PRIVATE', json.dumps(result))
            self.assertIsNone(timing.snapshot()['phases_ms']['private_save'])
        payload = report()
        result.pop('diagnostic_sample')
        result.pop('targeted_samples')
        payload.update(analysis=result, status='failed', timings=timing_fixture(
            ('application_tests','helpers_tests','analysis_build')))
        from plc_workbench.targeted_sample_history import sample_envelope
        payload['targeted_samples'] = sample_envelope()
        work_check.validate_work_check_report(payload)
        payload['analysis']['signal_context_summary'] = report()['analysis']['signal_context_summary']
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)


if __name__ == '__main__':
    unittest.main()
