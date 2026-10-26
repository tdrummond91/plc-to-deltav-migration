"""Authored signal attribution is private, versioned and canonically replayed."""
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
from plc_workbench.signal_context import analyze_signal_context
from plc_workbench.signal_context_summary import build_signal_context_summary
from plc_workbench.source_reuse import source_reuse_scope
from plc_workbench.storage import StorageError, save_run
from test_signal_patterns_workflow import (
    captured as old_captured, options, arguments, SOURCE as PATTERN_SOURCE,
    report as old_report, maximum_width_report as old_maximum,
)
from test_signal_context_workflow import context_inputs
from test_review_workflow import invoke
from test_unmatched_sample_report import REVISION

SOURCE = PATTERN_SOURCE.replace(b'<Tag Name="Out" DataType="BOOL"/>',
    b'<Tag Name="Out" DataType="BOOL"><Description>Invented pump alarm '
    b'PRIVATE_AUTHORED_SENTINEL</Description></Tag>')


@lru_cache(maxsize=6)
def captured(data: bytes = SOURCE) -> tuple:
    with source_reuse_scope():
        parts = old_captured(data)
        signal = analyze_signal_context(*context_inputs(parts), schema_version=3)
        return (*parts[:24], signal, *parts[25:])


@lru_cache(maxsize=6)
def _report(data: bytes) -> dict:
    with source_reuse_scope():
        payload = old_report(data)
        parts = captured(data)
        payload.update(schema_version=43, workflow_version='work-check-43')
        payload['analysis']['signal_context_summary'] = build_signal_context_summary(
            *context_inputs(parts), parts[24], revision=REVISION)
        if parts[24].status == 'partial':
            payload['analysis']['status'] = payload['status'] = 'partial'
        return payload


def report(data: bytes = SOURCE) -> dict:
    return deepcopy(_report(data))


def maximum_width_report() -> dict:
    """Reserve wide counts alongside the complete unchanged sample envelope."""
    payload = old_maximum()
    payload.update(schema_version=43, workflow_version='work-check-43')

    def grow(value):
        if type(value) is int:
            return 10**12
        if type(value) is dict:
            return {key: grow(child) for key, child in value.items()}
        return value

    payload['analysis']['signal_context_summary'] = grow(report()['analysis']['signal_context_summary'])
    return payload


class SignalAuthoredWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = source_reuse_scope()
        self.scope.__enter__()
        self.addCleanup(self.scope.__exit__, None, None, None)

    def test_review25_manifest28_preserve_preceding_evidence_and_artifacts(self) -> None:
        parts, prior_parts = captured(), old_captured(SOURCE)
        old = review.build_review_data(*prior_parts[:4], **options(prior_parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual((current['schema_version'], current['report_version']), (25, 'engineering-review-25'))
        self.assertEqual(current['signal_context'], parts[24].to_dict())
        for key in old.keys() - {'schema_version', 'report_version', 'status', 'signal_context'}:
            self.assertEqual(current[key], old[key], key)
        review.validate_review_data(*parts[:4], current, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = save_run(root, *prior_parts[:2], **arguments(prior_parts))
            prior_bytes = {p.name: p.read_bytes() for p in before.iterdir()}
            after = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((after / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (28, 16))
            self.assertEqual(manifest['review_schema_version'], 25)
            self.assertEqual(manifest['signal_context_schema_version'], 3)
            self.assertEqual(manifest['signal_context_analyzer_version'], 'signal-context-3')
            for name, content in prior_bytes.items():
                self.assertEqual((before / name).read_bytes(), content)
                if name not in {'manifest.json', 'review.html'}:
                    self.assertEqual((after / name).read_bytes(), content, name)

    def test_signal3_requires_all_companions_before_allocating_private_run(self) -> None:
        parts = captured()
        for key in options(parts):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(review.ReviewError):
                    review.build_review_data(*parts[:4], **(options(parts) | {key: None}))
                destination = Path(folder) / 'unallocated'
                with self.assertRaises(StorageError):
                    save_run(destination, *parts[:2], **(arguments(parts) | {key: None}))
                self.assertFalse(destination.exists())

    def test_forged_authored_evidence_fails_replay_before_allocation(self) -> None:
        parts = captured()
        addresses = deepcopy(parts[24].addresses)
        row = next(row for row in addresses if row['authored_evidence'])
        row['authored_evidence'][0]['entity_id'] = 'FORGED_PRIVATE_SENTINEL'
        forged = replace(parts[24], addresses=addresses)
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'unallocated'
            with self.assertRaises(StorageError) as error:
                save_run(destination, *parts[:2], **(arguments(parts) | {'signal_context': forged}))
            self.assertEqual(error.exception.code, 'review_validation_error')
            self.assertNotIn('FORGED_PRIVATE_SENTINEL', str(error.exception))
            self.assertFalse(destination.exists())
        current = review.build_review_data(*parts[:4], **options(parts))
        current['signal_context']['addresses'] = addresses
        with self.assertRaises(review.ReviewError):
            review.validate_review_data(*parts[:4], current, **options(parts))

    def test_versioned_limits_leave_review24_unchanged(self) -> None:
        parts, prior_parts = captured(), old_captured(SOURCE)
        current = review.build_review_data(*parts[:4], **options(parts))
        old = review.build_review_data(*prior_parts[:4], **options(prior_parts))
        self.assertEqual(review.MAX_REVIEW_V25_BYTES, 352 * 1024 * 1024)
        self.assertEqual(review_html._limits(25), (352 * 1024 * 1024, 384 * 1024 * 1024))
        self.assertEqual(review_html._limits(24), (344 * 1024 * 1024, 376 * 1024 * 1024))
        with patch.object(review, 'MAX_REVIEW_V25_BYTES', 1), tempfile.TemporaryDirectory() as folder:
            review.render_review_json(old)
            destination = Path(folder) / 'unallocated'
            with self.assertRaises(StorageError) as error:
                save_run(destination, *parts[:2], **arguments(parts))
            self.assertEqual(error.exception.code, 'review_size_limit')
            self.assertFalse(destination.exists())
        for key in ('MAX_REVIEW_V25_PAYLOAD_BYTES', 'MAX_REVIEW_V25_HTML_BYTES'):
            with patch.object(review_html, key, 1):
                review_html.render_review_html(old)
                with self.assertRaises(review_html.ReviewHtmlSizeLimitError):
                    review_html.render_review_html(current)

    def test_html_rejects_mixed_companion_versions(self) -> None:
        parts = captured()
        current = review.build_review_data(*parts[:4], **options(parts))
        for mutate in (
            lambda d: d.update(schema_version=24, report_version='engineering-review-24'),
            lambda d: d.update(file_operations=None),
            lambda d: d['signal_context'].update(schema_version=True),
            lambda d: d['signal_context'].update(analyzer_version='signal-context-2'),
            lambda d: d.update(signal_context=old_captured(SOURCE)[24].to_dict()),
        ):
            bad = deepcopy(current)
            mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(review_html.ReviewHtmlError):
                review_html.render_review_html(bad)

    def test_cli_and_direct_latest_review_bytes_match(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'invented.L5X'
            path.write_bytes(SOURCE)
            code, output, error = invoke(['review', str(path), '--workspace', str(root / 'runs')])
            self.assertEqual((code, error), (3, ''))
            saved, = (root / 'runs').iterdir()
            manifest = json.loads((saved / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], manifest['review_schema_version']), (38, 35))
            from test_engineering_assemblies_workflow import captured as latest_captured, options as latest_options
            parts = latest_captured(SOURCE)
            from test_engineering_assemblies_rack_workflow import captured as current_captured, options as current_options
            current_parts = current_captured(SOURCE)
            expected = review.build_review_data(*current_parts[:4], **current_options(current_parts))
            self.assertEqual((saved / 'review.html').read_bytes(), review_html.render_review_html(expected, source=current_parts[0].data).encode())


if __name__ == '__main__':
    unittest.main()
