"""Closed signal feedback uses invented inputs and local files only."""
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
from test_signal_context_workflow import report, maximum_width_report, SOURCE
from test_execution_context_workflow import report as legacy_report
from test_work_check_timing import timing_fixture
from test_unmatched_sample_report import REVISION


class SignalContextWorkReportTests(unittest.TestCase):
    def test_work40_requires_new_closed_summary_and_preserves_work39(self) -> None:
        current, old = report(), legacy_report(SOURCE)
        work_check.validate_work_check_report(current)
        work_check.validate_work_check_report(old)
        for mutate in (
            lambda p: p['analysis'].pop('signal_context_summary'),
            lambda p: p['analysis'].update(signal_context_summary=None),
            lambda p: p.update(schema_version=39, workflow_version='work-check-39'),
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

    def test_shared_source_counts_cannot_drift(self) -> None:
        for key in ('source_addresses', 'source_outputs', 'source_stateful_objects',
                    'source_stateful_address_uses', 'source_routines', 'source_rungs',
                    'source_instructions', 'source_condition_nodes', 'source_operands',
                    'source_expression_uses', 'source_predicate_operands',
                    'source_ons_storage_operands', 'unparsed_rungs'):
            payload = report()
            payload['analysis']['signal_context_summary']['coverage'][key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)

    def test_locally_feasible_predicate_kinds_still_match_captured_opcodes(self) -> None:
        payload = report()
        summary = payload['analysis']['signal_context_summary']
        kinds = summary['coverage']['reads_by_kind']
        self.assertGreater(kinds['xic'], 0)
        kinds['xic'] -= 1
        kinds['xio'] += 1
        # Total slots and all local partitions still agree. The outer report
        # must reconcile the instruction kinds against the captured conditions.
        validate_signal_context_summary(summary)
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_new_cap_publication_and_full_frozen_envelope_reservation(self) -> None:
        self.assertLess(len(work_check._serialize_report(maximum_width_report()).encode()), 96*1024)
        self.assertEqual(work_check._report_limit(40), 96*1024)
        self.assertEqual(work_check._report_limit(39), 88*1024)
        encoded = work_check.render_work_check_report(report())
        for marker in ('InventedSignalDemo', 'PRIVATE_SENTINEL', 'SensorPV'):
            self.assertNotIn(marker, encoded)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            destination = root / 'feedback.json'
            publish_summary(destination, encoded, input_path=root/'invented.L5X')
            self.assertEqual(destination.read_text(), encoded)
            for payload, limit in ((report(),96*1024),(legacy_report(SOURCE),88*1024)):
                oversized = work_check._serialize_report(payload) + ' '*limit
                with self.assertRaises(SummaryOutputError):
                    publish_summary(root/'rejected.json', oversized, input_path=root/'invented.L5X')
                self.assertFalse((root/'rejected.json').exists())

    def test_signal_failure_stops_before_save_and_keeps_error_private(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            source = root/'invented.L5X'
            source.write_bytes(SOURCE)
            timing = WorkCheckTiming()
            with source_reuse_scope(), patch.object(work_check, 'analyze_signal_context',
                    side_effect=SignalContextError('PRIVATE')), patch.object(work_check, 'save_run') as save:
                result = work_check._analyze(root, source, root, REVISION, timings=timing,
                                            sfc_context_schema_version=2, include_execution_context=True,
                                            include_signal_context=True)
            save.assert_not_called()
            self.assertEqual(result['failure_code'], 'signal_context_error')
            self.assertIsNone(result['signal_context_summary'])
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
