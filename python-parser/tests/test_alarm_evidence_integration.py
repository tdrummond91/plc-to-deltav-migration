"""Alarm evidence is optional, canonical, private, and closed in work feedback."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import review, review_html, work_check
from plc_workbench.alarm_evidence import AlarmEvidenceError, analyze_alarm_evidence
from plc_workbench.alarm_evidence_summary import build_alarm_evidence_summary
from plc_workbench.source import capture_snapshot
from plc_workbench.source_reuse import source_reuse_scope
from plc_workbench.storage import StorageError, save_run
from plc_workbench.summary_output import publish_summary, SummaryOutputError
from plc_workbench.targeted_sample_history import sample_envelope
from plc_workbench.work_check_timing import WorkCheckTiming
from test_signal_authored_workflow import (
    captured as old_captured, options as old_options, arguments as old_arguments,
    report as old_report, maximum_width_report as old_maximum, SOURCE as OLD_SOURCE,
)
from test_review_workflow import invoke
from test_unmatched_sample_report import REVISION
from test_work_check_timing import timing_fixture

SOURCE = OLD_SOURCE.replace(b'<Tags>', b'''<Tags>
<Tag Name="StoredAlarm" DataType="ALARM_ANALOG">
<Data Format="Alarm"><AlarmAnalogParameters HHSeverity="500"/></Data>
<AlarmConditions><AlarmCondition Name="InventedCondition"><AlarmConfig>
<Messages><Message Type="Alarm"><Text Lang="en-US">PRIVATE_ALARM_SENTINEL &lt;img src=x onerror=alert(1)&gt;</Text></Message></Messages>
</AlarmConfig></AlarmCondition></AlarmConditions></Tag>''', 1)


@lru_cache(maxsize=6)
def captured(data: bytes = SOURCE) -> tuple:
    with source_reuse_scope():
        parts = old_captured(data)
        return (*parts, analyze_alarm_evidence(parts[0], parts[1], parts[5]))


def options(parts: tuple) -> dict:
    return old_options(parts) | {'alarm_evidence': parts[26]}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'alarm_evidence': parts[26]}


@lru_cache(maxsize=6)
def _report(data: bytes) -> dict:
    with source_reuse_scope():
        payload = old_report(data)
        parts = captured(data)
        payload.update(schema_version=44, workflow_version='work-check-44')
        payload['analysis']['alarm_evidence_summary'] = build_alarm_evidence_summary(
            parts[0], parts[1], parts[5], parts[26], revision=REVISION)
        if parts[26].status == 'partial':
            payload['analysis']['status'] = payload['status'] = 'partial'
        return payload


def report(data: bytes = SOURCE) -> dict:
    return deepcopy(_report(data))


def maximum_width_report() -> dict:
    """Conservative byte probe retaining the complete frozen sample envelope."""
    payload = old_maximum()
    payload.update(schema_version=44, workflow_version='work-check-44')
    summary = report()['analysis']['alarm_evidence_summary']
    def grow(value):
        if type(value) is int:
            return 10**12
        if type(value) is dict:
            return {key: grow(child) for key, child in value.items()}
        return value
    summary['coverage'] = grow(summary['coverage'])
    payload['analysis']['alarm_evidence_summary'] = summary
    return payload


class AlarmEvidenceIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = source_reuse_scope()
        self.scope.__enter__()
        self.addCleanup(self.scope.__exit__, None, None, None)

    def test_optional_review26_manifest29_preserve_previous_evidence_and_artifacts(self) -> None:
        parts = captured()
        old = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual((old['schema_version'], current['schema_version']), (25, 26))
        self.assertEqual(current['report_version'], 'engineering-review-26')
        self.assertEqual(current['alarm_evidence'], parts[26].to_dict())
        for key in old.keys() - {'schema_version', 'report_version', 'status'}:
            self.assertEqual(current[key], old[key], key)
        review.validate_review_data(*parts[:4], current, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            before = save_run(Path(folder), *parts[:2], **old_arguments(parts))
            prior = {p.name: p.read_bytes() for p in before.iterdir()}
            after = save_run(Path(folder), *parts[:2], **arguments(parts))
            manifest = json.loads((after/'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], manifest['review_schema_version']), (29, 26))
            self.assertEqual(len(manifest['artifacts']), 16)
            self.assertEqual(manifest['alarm_evidence_schema_version'], 1)
            self.assertEqual(manifest['alarm_evidence_analyzer_version'], 'alarm-evidence-1')
            self.assertNotIn('alarm-evidence.json', manifest['artifacts'])
            for name, content in prior.items():
                self.assertEqual((before/name).read_bytes(), content)
                if name not in {'manifest.json', 'review.html'}:
                    self.assertEqual((after/name).read_bytes(), content, name)

    def test_all_prerequisites_required_before_allocation(self) -> None:
        parts = captured()
        for key in old_options(parts):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                destination = Path(folder)/'unallocated'
                with self.assertRaises(review.ReviewError):
                    review.build_review_data(*parts[:4], **(options(parts) | {key: None}))
                with self.assertRaises(StorageError):
                    save_run(destination, *parts[:2], **(arguments(parts) | {key: None}))
                self.assertFalse(destination.exists())
        for change in ({'include_review': False}, {'signal_context': replace(parts[24], schema_version=2)}):
            with self.subTest(change=change.keys()), tempfile.TemporaryDirectory() as folder:
                destination = Path(folder)/'unallocated'
                with self.assertRaises(StorageError):
                    save_run(destination, *parts[:2], **(arguments(parts) | change))
                self.assertFalse(destination.exists())

    def test_canonical_forgery_rejected_before_allocation(self) -> None:
        parts = captured()
        for field in ('declarations', 'containers', 'elements'):
            self.assertTrue(getattr(parts[26], field), field)
            forged = replace(parts[26], **{field: []})
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                destination = Path(folder)/'unallocated'
                with self.assertRaises(StorageError) as error:
                    save_run(destination, *parts[:2], **(arguments(parts) | {'alarm_evidence': forged}))
                self.assertEqual(error.exception.code, 'review_validation_error')
                self.assertFalse(destination.exists())
        current = review.build_review_data(*parts[:4], **options(parts))
        current['alarm_evidence']['elements'][0]['direct_text'] = 'FORGED_PRIVATE_SENTINEL'
        with self.assertRaises(review.ReviewError) as error:
            review.validate_review_data(*parts[:4], current, **options(parts))
        self.assertNotIn('FORGED_PRIVATE_SENTINEL', str(error.exception))

    def test_version_gates_and_offline_escape(self) -> None:
        parts = captured()
        current = review.build_review_data(*parts[:4], **options(parts))
        rendered = review_html.render_review_html(current)
        self.assertIn("connect-src 'none'", rendered)
        self.assertNotIn('<img src=x onerror=alert(1)>', rendered)
        self.assertIn('\\u003cimg src=x onerror=alert(1)\\u003e', rendered)
        mutations = (
            lambda d: d.update(schema_version=25, report_version='engineering-review-25'),
            lambda d: d.update(report_version='engineering-review-25'),
            lambda d: d.update(alarm_evidence=None),
            lambda d: d['alarm_evidence'].update(schema_version=True),
            lambda d: d['alarm_evidence'].update(analyzer_version='alarm-evidence-2'),
            lambda d: d['signal_context'].update(schema_version=2, analyzer_version='signal-context-2'),
            lambda d: d.update(file_operations=None),
        )
        for mutate in mutations:
            bad = deepcopy(current)
            mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(review_html.ReviewHtmlError):
                review_html.render_review_html(bad)

    def test_versioned_budgets_preserve_old_limits_and_no_allocation(self) -> None:
        parts = captured()
        old = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual(review.MAX_REVIEW_V26_BYTES, 360*1024*1024)
        self.assertEqual(review_html._limits(26), (360*1024*1024, 392*1024*1024))
        self.assertEqual(review_html._limits(25), (352*1024*1024, 384*1024*1024))
        with patch.object(review, 'MAX_REVIEW_V26_BYTES', 1), tempfile.TemporaryDirectory() as folder:
            review.render_review_json(old)
            destination = Path(folder)/'unallocated'
            with self.assertRaises(StorageError) as error:
                save_run(destination, *parts[:2], **arguments(parts))
            self.assertEqual(error.exception.code, 'review_size_limit')
            self.assertFalse(destination.exists())
        for key in ('MAX_REVIEW_V26_PAYLOAD_BYTES', 'MAX_REVIEW_V26_HTML_BYTES'):
            with patch.object(review_html, key, 1):
                review_html.render_review_html(old)
                with self.assertRaises(review_html.ReviewHtmlSizeLimitError):
                    review_html.render_review_html(current)

    def test_cli_captures_once_and_saves_canonical_alarm_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root/'invented.L5X'
            path.write_bytes(SOURCE)
            def capture_then_replace(filename):
                snapshot = capture_snapshot(filename)
                path.write_bytes(b'changed source')
                return snapshot
            with patch('plc_workbench.source.capture_snapshot', side_effect=capture_then_replace) as capture, \
                    patch('plc_workbench.storage.save_run', wraps=save_run) as save:
                code, output, error = invoke(['review', str(path), '--workspace', str(root/'runs')])
            self.assertEqual((code, error), (3, ''))
            capture.assert_called_once_with(path)
            self.assertEqual(save.call_args.kwargs['alarm_evidence'], captured()[26])
            saved, = (root/'runs').iterdir()
            self.assertEqual((saved/'snapshot.L5X').read_bytes(), SOURCE)
            from test_engineering_assemblies_rack_workflow import captured as latest_captured, options as latest_options
            latest = latest_captured(SOURCE)
            current = review.build_review_data(*latest[:4], **latest_options(latest))
            self.assertEqual((saved/'review.html').read_bytes(), review_html.render_review_html(current).encode())

    def test_cli_failure_is_source_free_and_allocates_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root/'invented.L5X'
            path.write_bytes(SOURCE)
            with patch('plc_workbench.alarm_evidence.analyze_alarm_evidence', side_effect=AlarmEvidenceError('PRIVATE_SENTINEL')):
                code, output, error = invoke(['review', str(path), '--workspace', str(root/'failed')])
            self.assertEqual(code, 1)
            self.assertIn('Cannot analyze alarm evidence', error)
            self.assertNotIn('PRIVATE_SENTINEL', output+error)
            self.assertFalse((root/'failed').exists())

    def test_work44_requires_closed_summary_and_preserves_work43(self) -> None:
        current, old = report(), old_report(SOURCE)
        work_check.validate_work_check_report(current)
        work_check.validate_work_check_report(old)
        self.assertEqual(current['targeted_samples'], old['targeted_samples'])
        for key in old['analysis'].keys() - {'status'}:
            self.assertEqual(current['analysis'][key], old['analysis'][key], key)
        for mutate in (
            lambda p: p['analysis'].pop('alarm_evidence_summary'),
            lambda p: p['analysis'].update(alarm_evidence_summary=None),
            lambda p: p.update(schema_version=43, workflow_version='work-check-43'),
            lambda p: p['analysis']['alarm_evidence_summary'].update(source='PRIVATE'),
            lambda p: p['analysis']['alarm_evidence_summary']['tool_revision'].update(commit='b'*40),
        ):
            bad = deepcopy(current)
            mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)
        old['analysis']['alarm_evidence_summary'] = current['analysis']['alarm_evidence_summary']
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(old)

    def test_work_summary_source_counts_cannot_drift(self) -> None:
        for key in ('source_xml_elements', 'source_entities', 'source_data_contents'):
            payload = report()
            payload['analysis']['alarm_evidence_summary']['coverage'][key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)

    def test_scheduled_program_entities_are_counted_in_work44(self) -> None:
        data = SOURCE.replace(b'<Tags>', b'<Tasks><Task Name="InventedTask" Type="CONTINUOUS">'
            b'<ScheduledPrograms><ScheduledProgram Name="P"/></ScheduledPrograms></Task></Tasks><Tags>', 1)
        payload = report(data)
        baseline = report()['analysis']['execution_context_summary']['coverage']['source_schedules']
        self.assertEqual(payload['analysis']['execution_context_summary']['coverage']['source_schedules'], baseline + 1)
        self.assertEqual(payload['analysis']['alarm_evidence_summary']['coverage']['source_entities'],
                         len(captured(data)[1].entities))
        work_check.validate_work_check_report(payload)

    def test_work44_publication_budget_and_frozen_reservation(self) -> None:
        self.assertLess(len(work_check._serialize_report(maximum_width_report()).encode()), 104*1024)
        self.assertEqual(work_check._report_limit(44), 104*1024)
        self.assertEqual(work_check._report_limit(43), 104*1024)
        encoded = work_check.render_work_check_report(report())
        for marker in ('PRIVATE_ALARM_SENTINEL', 'StoredAlarm', 'InventedCondition', 'HHSeverity', 'img src=x'):
            self.assertNotIn(marker, encoded)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            publish_summary(root/'feedback.json', encoded, input_path=root/'invented.L5X')
            self.assertEqual((root/'feedback.json').read_text(), encoded)
            with self.assertRaises(SummaryOutputError):
                publish_summary(root/'oversized.json', encoded+' '*(104*1024), input_path=root/'invented.L5X')
            self.assertFalse((root/'oversized.json').exists())

    def test_work_opt_in_preserves_defaults_and_frozen_samples(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            path = root/'invented.L5X'
            path.write_bytes(SOURCE)
            common = dict(sfc_context_schema_version=2, include_execution_context=True,
                          include_signal_context=True, signal_context_schema_version=3, include_file_operations=True)
            old = work_check._analyze(root, path, root, REVISION, **common)
            current = work_check._analyze(root, path, root, REVISION, include_alarm_evidence=True, **common)
            self.assertIsNone(current['failure_code'])
            self.assertTrue(current['private_run_saved'])
            self.assertNotIn('alarm_evidence_summary', old)
            self.assertEqual(current['alarm_evidence_summary'], report()['analysis']['alarm_evidence_summary'])
            self.assertEqual(old['targeted_samples']['record'], current['targeted_samples']['record'])
            for key in old.keys()-{'status', 'targeted_samples'}:
                self.assertEqual(old[key], current[key], key)

    def test_work_failure_is_closed_and_historical_failure_code_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            path = root/'invented.L5X'
            path.write_bytes(SOURCE)
            timing = WorkCheckTiming()
            with patch.object(work_check, 'analyze_alarm_evidence', side_effect=AlarmEvidenceError('PRIVATE_SENTINEL')), \
                    patch.object(work_check, 'save_run') as save:
                result = work_check._analyze(root, path, root, REVISION, timings=timing,
                    sfc_context_schema_version=2, include_execution_context=True, include_signal_context=True,
                    signal_context_schema_version=3, include_file_operations=True, include_alarm_evidence=True)
            save.assert_not_called()
            self.assertEqual(result['failure_code'], 'alarm_evidence_error')
            self.assertIsNone(result['alarm_evidence_summary'])
            self.assertFalse(result['private_run_saved'])
            self.assertNotIn('PRIVATE_SENTINEL', json.dumps(result))
            self.assertIsNone(timing.snapshot()['phases_ms']['private_save'])
        result.pop('diagnostic_sample')
        result.pop('targeted_samples')
        payload = report()
        payload.update(analysis=result, status='failed', timings=timing_fixture(
            ('application_tests', 'helpers_tests', 'analysis_build')), targeted_samples=sample_envelope())
        work_check.validate_work_check_report(payload)
        historical = deepcopy(payload)
        historical.update(schema_version=43, workflow_version='work-check-43')
        historical['analysis'].pop('alarm_evidence_summary')
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(historical)
        payload['analysis']['alarm_evidence_summary'] = report()['analysis']['alarm_evidence_summary']
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_work_missing_prerequisites_fails_before_read(self) -> None:
        with patch.object(work_check, 'capture_snapshot') as capture:
            result = work_check._analyze(Path('.'), Path('invented.L5X'), Path('.'), REVISION,
                                         include_alarm_evidence=True)
        capture.assert_not_called()
        self.assertEqual(result['failure_code'], 'alarm_evidence_error')
        self.assertIsNone(result['alarm_evidence_summary'])


if __name__ == '__main__':
    unittest.main()
