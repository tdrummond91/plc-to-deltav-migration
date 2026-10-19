"""Execution context stays private and preserves historical review artifacts."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import review, review_html
from plc_workbench.execution_context import ExecutionContextError, analyze_execution_context
from plc_workbench.execution_context_summary import build_execution_context_summary
from plc_workbench.sfc_context_summary import build_sfc_context_summary
from plc_workbench.source import capture_snapshot
from plc_workbench.source_reuse import source_reuse_scope
from plc_workbench.storage import StorageError, save_run
from test_sfc_context_workflow import (
    captured as old_captured, options as old_options, arguments as old_arguments,
    report as old_report, context_inputs as sfc_context_inputs,
)
from test_binding_context_workflow import ROOT, source
from test_review_workflow import invoke
from test_unmatched_sample_report import REVISION
from test_work_check_timing import timing_fixture, maximum_width_report as old_maximum

SOURCE = (ROOT / 'public/fixtures/synthetic/execution_context_demo.L5X').read_bytes()


def context_inputs(parts: tuple) -> tuple:
    return (*parts[:3], parts[4], parts[8], parts[9], parts[10], parts[11])


@lru_cache(maxsize=6)
def captured(data: bytes = SOURCE) -> tuple:
    with source_reuse_scope():
        parts = old_captured(data)
        return (*parts, analyze_execution_context(*context_inputs(parts)))


def options(parts: tuple) -> dict:
    return old_options(parts) | {'execution_context': parts[23]}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'execution_context': parts[23]}


@lru_cache(maxsize=6)
def _report(data: bytes) -> dict:
    with source_reuse_scope():
        payload = old_report(data)
        parts = captured(data)
        payload.update(schema_version=39, workflow_version='work-check-39', timings=timing_fixture())
        payload['analysis']['sfc_context_summary'] = build_sfc_context_summary(
            *sfc_context_inputs(parts), parts[22], revision=REVISION, schema_version=2)
        payload['analysis']['execution_context_summary'] = build_execution_context_summary(
            *context_inputs(parts), parts[23], revision=REVISION)
        if parts[23].status == 'partial':
            payload['analysis']['status'] = payload['status'] = 'partial'
        return payload


def report(data: bytes = SOURCE) -> dict:
    return deepcopy(_report(data))


def maximum_width_report() -> dict:
    """Conservative byte probe; simultaneous maxima need not be feasible."""
    payload = old_maximum()
    payload.update(schema_version=39, workflow_version='work-check-39')
    def grow(value):
        if type(value) is int:
            return 10**12
        if type(value) is dict:
            return {key: grow(child) for key, child in value.items()}
        return value
    payload['analysis']['execution_context_summary'] = grow(report()['analysis']['execution_context_summary'])
    return payload


class ExecutionContextWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = source_reuse_scope()
        self.scope.__enter__()
        self.addCleanup(self.scope.__exit__, None, None, None)

    def test_review21_manifest24_preserve_old_evidence_and_sixteen_artifacts(self) -> None:
        parts = captured()
        old = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual((current['schema_version'], current['report_version']), (21, 'engineering-review-21'))
        self.assertEqual(current['execution_context'], parts[23].to_dict())
        for key in old.keys() - {'schema_version', 'report_version', 'status'}:
            self.assertEqual(current[key], old[key], key)
        review.validate_review_data(*parts[:4], current, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = save_run(root, *parts[:2], **old_arguments(parts))
            prior = {p.name: p.read_bytes() for p in before.iterdir()}
            after = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((after / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (24, 16))
            self.assertEqual(manifest['review_schema_version'], 21)
            self.assertEqual(manifest['execution_context_analyzer_version'], 'execution-context-1')
            self.assertNotIn('execution-context.json', manifest['artifacts'])
            for name, content in prior.items():
                self.assertEqual((before / name).read_bytes(), content)
                if name not in {'manifest.json', 'review.html'}:
                    self.assertEqual((after / name).read_bytes(), content, name)

    def test_complete_preceding_chain_is_required_before_allocation(self) -> None:
        parts = captured(source('NOP();'))
        for key in old_options(parts):
            with self.subTest(key=key):
                with self.assertRaises(review.ReviewError):
                    review.build_review_data(*parts[:4], **(options(parts) | {key: None}))
                with tempfile.TemporaryDirectory() as folder:
                    destination = Path(folder) / 'unallocated'
                    with self.assertRaises(StorageError):
                        save_run(destination, *parts[:2], **(arguments(parts) | {key: None}))
                    self.assertFalse(destination.exists())
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'unallocated'
            with self.assertRaises(StorageError):
                save_run(destination, *parts[:2], **(arguments(parts) | {'include_review': False}))
            self.assertFalse(destination.exists())

    def test_forged_companion_and_review_are_canonically_rejected(self) -> None:
        parts = captured()
        for field in ('tasks', 'programs', 'schedules', 'designations', 'calls',
                      'control_occurrences', 'routine_contexts'):
            self.assertTrue(getattr(parts[23], field), field)
            forged = replace(parts[23], **{field: []})
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'unallocated'
                with self.assertRaises(StorageError) as error:
                    save_run(destination, *parts[:2], **(arguments(parts) | {'execution_context': forged}))
                self.assertEqual(error.exception.code, 'review_validation_error')
                self.assertFalse(destination.exists())
        current = review.build_review_data(*parts[:4], **options(parts))
        current['execution_context']['calls'][0]['raw_target_name'] = 'FORGED_PRIVATE_SENTINEL'
        with self.assertRaises(review.ReviewError) as error:
            review.validate_review_data(*parts[:4], current, **options(parts))
        self.assertNotIn('FORGED_PRIVATE_SENTINEL', str(error.exception))

    def test_review21_limits_preserve_review20_and_prevent_allocation(self) -> None:
        parts = captured(source('NOP();'))
        old = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual(review.MAX_REVIEW_V21_BYTES, 296 * 1024 * 1024)
        self.assertEqual(review_html._limits(21), (296 * 1024 * 1024, 328 * 1024 * 1024))
        self.assertEqual(review_html._limits(20), (280 * 1024 * 1024, 312 * 1024 * 1024))
        with patch.object(review, 'MAX_REVIEW_V21_BYTES', 1), tempfile.TemporaryDirectory() as folder:
            review.render_review_json(old)
            destination = Path(folder) / 'unallocated'
            with self.assertRaises(StorageError) as error:
                save_run(destination, *parts[:2], **arguments(parts))
            self.assertEqual(error.exception.code, 'review_size_limit')
            self.assertFalse(destination.exists())
        for key in ('MAX_REVIEW_V21_PAYLOAD_BYTES', 'MAX_REVIEW_V21_HTML_BYTES'):
            with patch.object(review_html, key, 1):
                review_html.render_review_html(old)
                with self.assertRaises(review_html.ReviewHtmlSizeLimitError):
                    review_html.render_review_html(current)

    def test_html_is_offline_escaped_paginated_and_has_closed_version_gates(self) -> None:
        parts = captured()
        current = review.build_review_data(*parts[:4], **options(parts))
        rendered = review_html.render_review_html(current)
        for text in ('PAGE_SIZE = 50', 'Execution context', 'Execution routine calls',
                     'Execution control boundaries', "connect-src 'none'", 'textContent'):
            self.assertIn(text, rendered)
        self.assertNotIn('.innerHTML', rendered)
        self.assertNotIn('<img src=x onerror=alert(1)>', rendered)
        self.assertIn('\\u003cimg src=x onerror=alert(1)\\u003e', rendered)
        for mutate in (lambda d: d.update(execution_context=None),
                       lambda d: d['execution_context'].update(schema_version=True),
                       lambda d: d['execution_context'].update(analyzer_version='execution-context-2'),
                       lambda d: d.update(sfc_context=None),
                       lambda d: d.update(schema_version=20, report_version='engineering-review-20')):
            bad = deepcopy(current)
            mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(review_html.ReviewHtmlError):
                review_html.render_review_html(bad)
        old = review.build_review_data(*parts[:4], **old_options(parts))
        old['execution_context'] = current['execution_context']
        with self.assertRaises(review_html.ReviewHtmlError):
            review_html.render_review_html(old)

    def test_cli_captures_once_saves_latest_and_retains_partial_status(self) -> None:
        data = source('XIC(A)JSR(Missing,0);')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'invented.L5X'
            path.write_bytes(data)
            def capture_then_replace(filename):
                captured_source = capture_snapshot(filename)
                path.write_bytes(b'changed live source')
                return captured_source
            with patch('plc_workbench.source.capture_snapshot', side_effect=capture_then_replace) as capture, \
                    patch('plc_workbench.storage.save_run', wraps=save_run) as save:
                code, output, error = invoke(['review', str(path), '--workspace', str(root / 'runs')])
            capture.assert_called_once_with(path)
            save.assert_called_once()
            self.assertEqual(save.call_args.args[1].data, data)
            self.assertEqual(save.call_args.kwargs['execution_context'], captured(data)[23])
            self.assertEqual((code, error), (3, ''))
            saved, = (root / 'runs').iterdir()
            self.assertEqual((saved / 'snapshot.L5X').read_bytes(), data)
            manifest = json.loads((saved / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], manifest['status']), (24, 'partial'))
            expected = review.build_review_data(*captured(data)[:4], **options(captured(data)))
            self.assertEqual((saved / 'review.html').read_bytes(), review_html.render_review_html(expected).encode())

    def test_cli_execution_failure_is_source_free_and_allocates_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'invented.L5X'
            path.write_bytes(source('NOP();'))
            with patch('plc_workbench.execution_context.analyze_execution_context',
                       side_effect=ExecutionContextError('PRIVATE_SENTINEL')):
                code, output, error = invoke(['review', str(path), '--workspace', str(root / 'failed')])
            self.assertEqual(code, 1)
            self.assertIn('Cannot analyze execution context', error)
            self.assertNotIn('PRIVATE_SENTINEL', output + error)
            self.assertFalse((root / 'failed').exists())

    def test_invented_fixture_exercises_pagination_and_unresolved_context(self) -> None:
        context = captured()[23]
        self.assertGreater(len(context.calls), 50)
        self.assertEqual(context.status, 'partial')
        self.assertTrue(any(row['has_stateful'] for row in context.calls))
        self.assertTrue(any(row['has_branch'] for row in context.calls))
        self.assertTrue(any(not row['qualified'] for row in context.tasks))
        self.assertTrue(any(row['raw_attributes'].get('Rate') == '010.00' for row in context.tasks))
        self.assertEqual({row['opcode'] for row in context.control_occurrences}, {'SBR', 'RET', 'JMP', 'LBL'})


if __name__ == '__main__':
    unittest.main()
