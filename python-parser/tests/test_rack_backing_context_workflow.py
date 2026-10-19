"""Rack correspondence stays separate from base bindings and historical reports."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import review, review_html, work_check
from plc_workbench.source_reuse import source_reuse_scope
from plc_workbench.storage import StorageError, save_run
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from test_residual_diagnostics_workflow import (
    SOURCE, captured, options as old_options, arguments as old_arguments,
    report as old_report, ANALYZE_OPTIONS, old_maximum,
)
from test_unmatched_sample_report import REVISION


def options(parts: tuple) -> dict:
    return old_options(parts) | {'include_rack_backing_context': True}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'include_rack_backing_context': True}


@lru_cache(maxsize=2)
def _report(data: bytes) -> dict:
    payload = old_report(data)
    frozen = payload['targeted_samples']
    with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
        root = Path(folder).resolve()
        source = root / 'invented.L5X'
        source.write_bytes(data)
        with patch.object(work_check, 'resolve_targeted_samples', return_value=deepcopy(frozen)):
            analysis = work_check._analyze(root, source, root, REVISION, **ANALYZE_OPTIONS,
                include_residual_interpretation=True, include_control_interpretation=True,
                include_residual_diagnostics=True, include_rack_backing_context=True)
        if analysis['failure_code'] is not None:
            raise AssertionError(analysis['failure_code'])
    payload.update(schema_version=52, workflow_version='work-check-52', analysis=analysis,
                   status='partial' if analysis['status'] == 'partial' else 'passed',
                   diagnostic_sample=analysis.pop('diagnostic_sample'),
                   targeted_samples=analysis.pop('targeted_samples'))
    return payload


def report(data: bytes = SOURCE) -> dict:
    return deepcopy(_report(data))


class RackBackingContextWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        scope = source_reuse_scope()
        scope.__enter__()
        self.addCleanup(scope.__exit__, None, None, None)

    def test_saved_artifacts_preserve_prior_evidence(self) -> None:
        parts = captured()
        current = review.build_review_data(*parts[:4], **options(parts))
        prior = review.build_review_data(*parts[:4], **old_options(parts))
        self.assertEqual((prior['schema_version'], current['schema_version']), (33, 34))
        for key, value in prior.items():
            if key not in {'schema_version', 'report_version', 'status'}:
                self.assertEqual(value, current[key], key)
        self.assertEqual(current['rack_backing_context']['schema_version'], 1)
        review.validate_review_data(*parts[:4], current, **options(parts))
        forged = deepcopy(current)
        forged['rack_backing_context']['status'] = 'forged'
        with self.assertRaises(review.ReviewError):
            review.validate_review_data(*parts[:4], forged, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = save_run(root, *parts[:2], **old_arguments(parts))
            original = {p.name: p.read_bytes() for p in before.iterdir()}
            after = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((after / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], manifest['review_schema_version']), (37, 34))
            self.assertEqual(manifest['rack_backing_context_schema_version'], 1)
            self.assertEqual(len(manifest['artifacts']), 16)
            for name, record in manifest['artifacts'].items():
                raw = (after / name).read_bytes()
                self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (record['size_bytes'], record['sha256']))
            self.assertEqual(original, {p.name: p.read_bytes() for p in before.iterdir()})

    def test_flags_reject_before_allocating_private_run(self) -> None:
        parts = captured()
        for override in ({'include_rack_backing_context': 1}, {'include_residual_diagnostics': False},
                         {'include_control_interpretation': False}, {'include_review': False}):
            with self.subTest(override=override), tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'unallocated'
                with self.assertRaises(StorageError):
                    save_run(destination, *parts[:2], **(arguments(parts) | override))
                self.assertFalse(destination.exists())

    def test_public_contract_keeps_prior_summaries_and_frozen_samples(self) -> None:
        current, prior = report(), old_report()
        work_check.validate_work_check_report(current)
        for key, value in prior['analysis'].items():
            self.assertEqual(value, current['analysis'][key], key)
        self.assertEqual(current['targeted_samples'], prior['targeted_samples'])
        self.assertIsNone(current['diagnostic_sample'])
        for change in ('missing', 'wrong_revision', 'extra_field'):
            forged = deepcopy(current)
            nested = forged['analysis']['rack_backing_context_summary']
            if change == 'missing':
                del forged['analysis']['rack_backing_context_summary']
            elif change == 'wrong_revision':
                nested['tool_revision']['commit'] = 'f' * 40
            else:
                nested['private_address'] = 'invented-private-marker'
            with self.subTest(change=change), self.assertRaises(ValueError):
                work_check.validate_work_check_report(forged)
        old = deepcopy(current)
        old.update(schema_version=51, workflow_version='work-check-51')
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(old)

    def test_html_companion_and_payload_version_gates(self) -> None:
        parts = captured()
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertIn('rack_backing_context', review_html.render_review_html(current))
        for change in ('missing', 'wrong_version', 'legacy_extra'):
            forged = deepcopy(current)
            if change == 'missing':
                del forged['rack_backing_context']
            elif change == 'wrong_version':
                forged['rack_backing_context']['schema_version'] = True
            else:
                forged.update(schema_version=33, report_version='engineering-review-33')
            with self.subTest(change=change), self.assertRaises(review_html.ReviewHtmlError):
                review_html.render_review_html(forged)

    def test_caps_and_history_publication(self) -> None:
        current = report()
        def grow(value):
            if type(value) is int:
                return 10**12
            return {k: grow(v) for k, v in value.items()} if type(value) is dict else value
        wide = old_maximum()
        wide.update(schema_version=52, workflow_version='work-check-52')
        for key in ('condition_summary', 'execution_context_summary', 'rack_backing_summary',
                    'rack_backing_context_summary'):
            wide['analysis'][key] = grow(current['analysis'][key])
        self.assertLessEqual(len(json.dumps(wide, separators=(',', ':')).encode()), 144 * 1024)
        rendered = work_check.render_work_check_report(current)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'invented.L5X'
            source.write_bytes(SOURCE)
            publish_summary(root / 'current.json', rendered.ljust(144 * 1024), input_path=source)
            self.assertEqual((root / 'current.json').read_bytes(), rendered.encode())
            with self.assertRaises(SummaryOutputError):
                publish_summary(root / 'oversize.json', rendered.ljust(144 * 1024 + 1), input_path=source)
            self.assertFalse((root / 'oversize.json').exists())
        self.assertEqual(work_check._report_limit(51), 144 * 1024)
        self.assertEqual(work_check._report_limit(52), 144 * 1024)
        self.assertEqual(review_html._limits(34), (472 * 1024 * 1024, 504 * 1024 * 1024))
        parts = captured()
        with patch.object(review, 'MAX_REVIEW_V34_BYTES', 1), tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'unallocated'
            with self.assertRaises(StorageError):
                save_run(destination, *parts[:2], **arguments(parts))
            self.assertFalse(destination.exists())


    def test_nonzero_root_dispositions_reconcile_with_prior_shape_evidence(self) -> None:
        from plc_workbench.rack_backing_context_summary import validate_rack_backing_context_summary
        from test_rack_backing_context import fixture

        current = report(fixture().encode())
        work_check.validate_work_check_report(current)
        coverage = current['analysis']['rack_backing_context_summary']['coverage']
        self.assertEqual(coverage['roots_by_disposition']['associated'], 2)
        self.assertEqual(coverage['sfc_uses_by_disposition']['associated'], 2)
        changed = deepcopy(current)
        nested = changed['analysis']['rack_backing_context_summary']
        nested['status'] = 'partial'
        nested['coverage']['roots_by_disposition']['associated'] -= 1
        nested['coverage']['roots_by_disposition']['source_unqualified'] += 1
        # A standalone overlay can contain an unused failed declaration. Its
        # exact root dispositions must still agree with the prior shape model.
        validate_rack_backing_context_summary(nested)
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(changed)

        unsupported = report(fixture().replace('CatalogNumber="1756-EN2T"',
                                               'CatalogNumber="1756-ENBT"').encode())
        work_check.validate_work_check_report(unsupported)
        for disposition in ('backing_identity_gap', 'duplicate_candidate_name'):
            changed = deepcopy(unsupported)
            nested = changed['analysis']['rack_backing_context_summary']
            roots = nested['coverage']['roots_by_disposition']
            self.assertEqual(roots['family_unsupported'], 2)
            roots[disposition], roots['family_unsupported'] = 2, 0
            # These branches require a qualified EN2T Slot shape. Keeping all
            # uses unassociated cannot hide the impossible family admission.
            validate_rack_backing_context_summary(nested)
            with self.subTest(disposition=disposition), self.assertRaises(ValueError):
                work_check.validate_work_check_report(changed)


if __name__ == '__main__':
    unittest.main()
