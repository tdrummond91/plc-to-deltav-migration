"""Boolean output context publication and review boundaries use invented source only."""
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
from plc_workbench.output_context import OutputContextError, analyze_output_context
from plc_workbench.output_context_summary import (
    OutputContextSummaryError, build_output_context_summary, validate_output_context_summary,
)
from plc_workbench.storage import StorageError, save_run
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from test_calculation_path_workflow import (
    captured as old_captured, options as old_options, arguments as old_arguments,
    report as old_report, maximum_width_report as old_maximum,
)
from test_binding_context_workflow import ROOT, source
from test_unmatched_sample_report import REVISION

SOURCE = (ROOT / 'public/fixtures/synthetic/output_context_demo.L5X').read_bytes()


def context_inputs(parts: tuple) -> tuple:
    return (*parts[:3], parts[4], parts[8], parts[9], parts[10], parts[11])


@lru_cache(maxsize=6)
def captured(data: bytes = SOURCE) -> tuple:
    parts = old_captured(data)
    return (*parts, analyze_output_context(*context_inputs(parts)))


def options(parts: tuple) -> dict:
    return old_options(parts) | {'output_context': parts[19]}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'output_context': parts[19]}


@lru_cache(maxsize=6)
def _report(data: bytes) -> dict:
    payload = old_report(data)
    parts = captured(data)
    payload.update(schema_version=34, workflow_version='work-check-34')
    payload['analysis']['output_context_summary'] = build_output_context_summary(
        *context_inputs(parts), parts[19], revision=REVISION)
    if parts[19].status == 'partial':
        payload['analysis']['status'] = payload['status'] = 'partial'
    return payload


def report(data: bytes = SOURCE) -> dict:
    return deepcopy(_report(data))


def maximum_width_report() -> dict:
    """Conservative byte probe; simultaneous maxima need not be feasible."""
    payload = old_maximum()
    payload.update(schema_version=34, workflow_version='work-check-34')
    summary = deepcopy(report()['analysis']['output_context_summary'])
    def grow(value):
        if type(value) is int:
            return 250_000
        if type(value) is dict:
            return {key: grow(child) for key, child in value.items()}
        return value
    payload['analysis']['output_context_summary'] = grow(summary)
    return payload


class OutputContextWorkflowTests(unittest.TestCase):
    def test_review17_manifest20_preserve_old_evidence_and_sixteen_artifacts(self) -> None:
        parts = captured()
        old = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual((current['schema_version'], current['report_version']), (17, 'engineering-review-17'))
        for key in old.keys() - {'schema_version', 'report_version', 'status'}:
            self.assertEqual(current[key], old[key], key)
        review.validate_review_data(*parts[:4], current, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = save_run(root, *parts[:2], **old_arguments(parts))
            prior = {p.name: p.read_bytes() for p in before.iterdir()}
            after = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((after / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (20, 16))
            self.assertEqual(manifest['review_schema_version'], 17)
            self.assertEqual(manifest['output_context_analyzer_version'], 'output-context-1')
            self.assertNotIn('output-context.json', manifest['artifacts'])
            for name, content in prior.items():
                self.assertEqual((before / name).read_bytes(), content)
                if name not in {'manifest.json', 'review.html'}:
                    self.assertEqual((after / name).read_bytes(), content, name)

    def test_incomplete_or_forged_companion_rejected_before_allocation(self) -> None:
        parts = captured()
        for key in ('calculation_paths', 'conditions', 'relationships', 'access'):
            with self.subTest(key=key), self.assertRaises(review.ReviewError):
                review.build_review_data(*parts[:4], **(options(parts) | {key: None}))
        for field in ('outputs', 'addresses', 'condition_reads', 'rung_contexts'):
            forged = replace(parts[19], **{field: []})
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                root = Path(folder) / 'unallocated'
                with self.assertRaises(StorageError):
                    save_run(root, *parts[:2], **(arguments(parts) | {'output_context': forged}))
                self.assertFalse(root.exists())
        current = review.build_review_data(*parts[:4], **options(parts))
        current['output_context']['coverage']['outputs_total'] += 1
        with self.assertRaises(review.ReviewError):
            review.validate_review_data(*parts[:4], current, **options(parts))

    def test_work34_preserves_previous_summaries_and_frozen_sample_bytes(self) -> None:
        old, current = old_report(SOURCE), report()
        work_check.validate_work_check_report(current)
        self.assertEqual(current['targeted_samples'], old['targeted_samples'])
        for key in old['analysis'].keys() - {'status'}:
            self.assertEqual(current['analysis'][key], old['analysis'][key], key)
        self.assertEqual(json.loads(work_check.render_work_check_report(current)), current)
        for path in (ROOT / 'public/inspection').glob('work-check-*.json'):
            before = path.read_bytes()
            historical = json.loads(before)
            self.assertLessEqual(historical['schema_version'], 33)
            self.assertEqual(json.loads(work_check.render_work_check_report(historical)), historical)
            self.assertEqual(path.read_bytes(), before)
        self.assertEqual(work_check.render_work_check_report(old), json.dumps(
            old, separators=(',', ':'), sort_keys=True, ensure_ascii=True) + '\n')

    def test_public_presence_revision_versions_and_source_populations_are_closed(self) -> None:
        for mutate in (
            lambda p: p['analysis'].pop('output_context_summary'),
            lambda p: p['analysis'].update(output_context_summary=None),
            lambda p: p['analysis']['output_context_summary']['tool_revision'].update(commit='f' * 40),
            lambda p: p['analysis']['output_context_summary'].update(schema_version=True),
            lambda p: p['analysis']['output_context_summary'].update(private='PRIVATE'),
            lambda p: p.update(schema_version=33, workflow_version='work-check-33'),
        ):
            candidate = report()
            mutate(candidate)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        candidate = report()
        candidate['analysis']['output_context_summary'] = report(source('NOP();'))['analysis']['output_context_summary']
        validate_output_context_summary(candidate['analysis']['output_context_summary'])
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)

    def test_balanced_foreign_counts_cannot_replace_source_evidence(self) -> None:
        # Each mutation remains a valid standalone aggregate but contradicts
        # the captured condition or rung summary in the same work report.
        for field in ('opcode', 'hint', 'condition_population', 'source_population'):
            candidate = report(source('OTE(A);'))
            counts = candidate['analysis']['output_context_summary']['coverage']
            if field == 'opcode':
                counts['outputs_by_opcode'].update(OTE=0, OTL=1)
            elif field == 'hint':
                counts['hints_by_category']['alarm'] = 1
                counts['rungs_with_hints'] = 1
            elif field == 'condition_population':
                counts['source_condition_nodes'] += 1
            else:
                counts['source_instructions'] += 1
            validate_output_context_summary(candidate['analysis']['output_context_summary'])
            with self.subTest(field=field), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)

    def test_runner_captures_once_and_replays_without_resampling(self) -> None:
        from plc_workbench.targeted_sample_history import sample_envelope
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            path = root / 'invented.L5X'
            path.write_bytes(SOURCE)
            with patch.object(work_check, 'capture_snapshot', wraps=work_check.capture_snapshot) as capture, \
                    patch.object(work_check, 'analyze_output_context', wraps=analyze_output_context) as analyze, \
                    patch.object(work_check, 'save_run', return_value=root / 'saved') as save:
                first = work_check._analyze(root, path, root, REVISION)
            self.assertIsNone(first['failure_code'])
            capture.assert_called_once_with(path)
            analyze.assert_called_once()
            self.assertEqual(save.call_args.kwargs['output_context'], captured()[19])
            envelope = first.pop('targeted_samples')
            first.pop('diagnostic_sample')
            payload = report()
            payload.update(analysis=first, targeted_samples=envelope)
            work_check.validate_work_check_report(payload)
            path.write_bytes(source('NOP();'))
            with patch.object(work_check, 'build_targeted_samples', side_effect=AssertionError('No new disclosure.')), \
                    patch.object(work_check, 'save_run', return_value=root / 'saved'):
                second = work_check._analyze(root, path, root, REVISION)
            self.assertEqual(second['targeted_samples'], sample_envelope('replayed', envelope['record']))

    def test_failures_use_fixed_codes_null_summaries_and_private_logs(self) -> None:
        from test_save_diagnostics import failed_report
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            path = root / 'invented.L5X'
            path.write_bytes(SOURCE)
            for target, error, code, saved in (
                ('analyze_output_context', OutputContextError('PRIVATE_SENTINEL'), 'output_context_error', False),
                ('build_output_context_summary', OutputContextSummaryError('PRIVATE_SENTINEL'), 'summary_error', True),
            ):
                with patch.object(work_check, target, side_effect=error), patch.object(work_check, 'save_run', return_value=root):
                    result = work_check._analyze(root, path, root, REVISION)
                self.assertEqual((result['failure_code'], result['private_run_saved']), (code, saved))
                self.assertTrue(all(value is None for key, value in result.items() if key.endswith('_summary')))
                payload = failed_report(34, code)
                payload['analysis'] = {k: v for k, v in result.items() if k not in {'diagnostic_sample', 'targeted_samples'}}
                self.assertNotIn('PRIVATE_SENTINEL', work_check.render_work_check_report(payload))
                self.assertIn('PRIVATE_SENTINEL', (root / 'analysis.log').read_text())
                payload.update(schema_version=33, workflow_version='work-check-33')
                with self.assertRaises(ValueError):
                    work_check.validate_work_check_report(payload)

    def test_cli_uses_one_captured_snapshot_and_sanitizes_context_failure(self) -> None:
        from plc_workbench.source import capture_snapshot
        from test_review_workflow import invoke
        data = source('XIC(A)OTE(A);')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'invented.L5X'
            path.write_bytes(data)
            def capture_then_replace(filename):
                snapshot = capture_snapshot(filename)
                path.write_bytes(b'changed live source')
                return snapshot
            with patch('plc_workbench.source.capture_snapshot', side_effect=capture_then_replace) as capture, \
                    patch('plc_workbench.storage.save_run', wraps=save_run) as save:
                code, output, error = invoke(['review', str(path), '--workspace', str(root / 'runs')])
            capture.assert_called_once_with(path)
            save.assert_called_once()
            self.assertEqual(save.call_args.args[1].data, data)
            self.assertEqual(save.call_args.kwargs['output_context'], captured(data)[19])
            self.assertEqual((code, error), (3, ''))
            saved, = (root / 'runs').iterdir()
            self.assertEqual((saved / 'snapshot.L5X').read_bytes(), data)
            expected = review.build_review_data(*captured(data)[:4], **options(captured(data)))
            self.assertEqual((saved / 'review.html').read_bytes(), review_html.render_review_html(expected).encode())
            path.write_bytes(data)
            with patch('plc_workbench.output_context.analyze_output_context', side_effect=OutputContextError('PRIVATE_SENTINEL')):
                code, output, error = invoke(['review', str(path), '--workspace', str(root / 'failed')])
            self.assertEqual(code, 1)
            self.assertIn('Cannot analyze Boolean output context', error)
            self.assertNotIn('PRIVATE_SENTINEL', output + error)
            self.assertFalse((root / 'failed').exists())

    def test_review17_limits_preserve_review16_and_prevent_allocation(self) -> None:
        parts = captured()
        old = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual(review.MAX_REVIEW_V17_BYTES, 232 * 1024 * 1024)
        self.assertEqual(review_html._limits(17), (232 * 1024 * 1024, 264 * 1024 * 1024))
        self.assertEqual(review_html._limits(16), (216 * 1024 * 1024, 248 * 1024 * 1024))
        with patch.object(review, 'MAX_REVIEW_V17_BYTES', 1), tempfile.TemporaryDirectory() as folder:
            review.render_review_json(old)
            destination = Path(folder) / 'unallocated'
            with self.assertRaises(StorageError) as error:
                save_run(destination, *parts[:2], **arguments(parts))
            self.assertEqual(error.exception.code, 'review_size_limit')
            self.assertFalse(destination.exists())
        for key in ('MAX_REVIEW_V17_PAYLOAD_BYTES', 'MAX_REVIEW_V17_HTML_BYTES'):
            with patch.object(review_html, key, 1):
                review_html.render_review_html(old)
                with self.assertRaises(review_html.ReviewHtmlSizeLimitError):
                    review_html.render_review_html(current)

    def test_work34_conservative_width_fits_unchanged_80k_envelope(self) -> None:
        maximum = maximum_width_report()
        size = len(work_check._serialize_report(maximum).encode())
        self.assertLess(size, work_check.MAX_REPORT_V32_BYTES)
        self.assertEqual(work_check._report_limit(31), 64 * 1024)
        self.assertEqual(work_check._report_limit(32), 80 * 1024)
        self.assertEqual(work_check._report_limit(34), 80 * 1024)
        work_check._report_size(maximum)
        with patch.object(work_check, 'MAX_REPORT_V32_BYTES', size - 1):
            with self.assertRaises(work_check.WorkCheckError):
                work_check._report_size(maximum)

    def test_publication_accepts_closed_counts_and_applies_raw_input_cap(self) -> None:
        payload = report()
        encoded = work_check.render_work_check_report(payload)
        self.assertEqual(encoded, json.dumps(payload, separators=(',', ':'), sort_keys=True, ensure_ascii=True) + '\n')
        for token in ('"instruction_id"', '"rung_id"', '"address_id"', '"incoming_condition_id"', '"raw_text"'):
            self.assertNotIn(token, json.dumps(payload['analysis']['output_context_summary']))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'feedback.json'
            padded = encoded + ' ' * (80 * 1024 - len(encoded.encode()))
            publish_summary(path, padded, input_path=root / 'invented.L5X')
            self.assertEqual(path.read_text(), encoded)
            with self.assertRaises(SummaryOutputError):
                publish_summary(root / 'rejected.json', padded + ' ', input_path=root / 'invented.L5X')
            self.assertFalse((root / 'rejected.json').exists())

    def test_html_uses_safe_paginated_evidence_and_closed_version_gates(self) -> None:
        parts = captured()
        current = review.build_review_data(*parts[:4], **options(parts))
        rendered = review_html.render_review_html(current)
        for text in ('Boolean output context', 'Outputs whose captured condition context reads this address', 'Incoming condition evidence',
                     'Other captured writer operands', 'Authored wording on this rung', 'PAGE_SIZE = 50'):
            self.assertIn(text, rendered)
        self.assertNotIn('.innerHTML', rendered)
        self.assertIn('PRIVATE · OFFLINE', rendered)
        self.assertNotIn('PRIVATE Â· OFFLINE', rendered)
        self.assertIn("connect-src 'none'", rendered)
        for mutate in (lambda d: d.update(output_context=None),
                       lambda d: d['output_context'].update(schema_version=True),
                       lambda d: d['pid_connections'].update(schema_version=2),
                       lambda d: d.update(schema_version=16, report_version='engineering-review-16')):
            bad = deepcopy(current)
            mutate(bad)
            with self.assertRaises(review_html.ReviewHtmlError):
                review_html.render_review_html(bad)


if __name__ == '__main__':
    unittest.main()
