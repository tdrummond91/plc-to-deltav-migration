"""The current interpretation bundle is opt-in and preserves historical replay."""
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
from test_r3_context_workflow import (
    options as old_options, arguments as old_arguments, report as old_report,
    maximum_width_report as old_maximum, ANALYZE_OPTIONS,
)
from test_signal_candidates_workflow import captured as old_captured
from test_unmatched_sample_report import REVISION

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'public/fixtures/synthetic/residual_interpretation_demo.L5X').read_bytes()


@lru_cache(maxsize=6)
def captured(data: bytes = SOURCE) -> tuple:
    with source_reuse_scope():
        parts = list(old_captured(data))
        base = (*parts[:3], parts[4], parts[8], parts[9], parts[10])
        parts[11] = work_check.analyze_conditions(*base, schema_version=4)
        common = (*base, parts[11])
        parts[12] = work_check.analyze_binding_context(*common)
        companions = (*common, parts[12])
        parts[13] = work_check.analyze_custom_instruction_context(*companions)
        parts[14] = work_check.analyze_indexed_access(*companions)
        parts[16] = work_check.analyze_aoi_body_context(*companions, parts[13], schema_version=2)
        parts[17] = work_check.analyze_pid_connections(*common, parts[5], parts[6], parts[7])
        parts[18] = work_check.analyze_calculation_paths(*common)
        parts[19] = work_check.analyze_output_context(*common)
        parts[20] = work_check.analyze_stateful_objects(*common, parts[5])
        parts[23] = work_check.analyze_execution_context(*common)
        parts[24] = work_check.analyze_signal_context(
            *common, parts[5], parts[19], parts[20], parts[23], schema_version=5)
        parts[25] = work_check.analyze_file_operations(*common, parts[5])
        return tuple(parts)


def options(parts: tuple) -> dict:
    return old_options(parts) | {'include_residual_interpretation': True}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'include_residual_interpretation': True}


@lru_cache(maxsize=2)
def _report(data: bytes) -> dict:
    payload = old_report(data)
    frozen = payload['targeted_samples']
    with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
        root = Path(folder).resolve()
        source = root / 'invented.L5X'
        source.write_bytes(data)
        with patch.object(work_check, 'resolve_targeted_samples', return_value=deepcopy(frozen)):
            analysis = work_check._analyze(root, source, root, REVISION,
                **ANALYZE_OPTIONS, include_residual_interpretation=True)
        if analysis['failure_code'] is not None:
            raise AssertionError(analysis['failure_code'])
    payload.update(schema_version=49, workflow_version='work-check-49', analysis=analysis,
                   status='partial' if analysis['status'] == 'partial' else 'passed',
                   diagnostic_sample=analysis.pop('diagnostic_sample'),
                   targeted_samples=analysis.pop('targeted_samples'))
    return payload


def report(data: bytes = SOURCE) -> dict:
    return deepcopy(_report(data))


def maximum_width_report() -> dict:
    payload = old_maximum()
    payload.update(schema_version=49, workflow_version='work-check-49')
    def grow(value):
        if type(value) is int:
            return 10**12
        return {key: grow(child) for key, child in value.items()} if type(value) is dict else value
    for key in ('condition_summary', 'aoi_body_summary', 'communication_context_summary'):
        payload['analysis'][key] = grow(report()['analysis'][key])
    return payload


class ResidualInterpretationWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        scope = source_reuse_scope()
        scope.__enter__()
        self.addCleanup(scope.__exit__, None, None, None)

    def test_saved_artifacts_replay_and_historical_bundle(self) -> None:
        parts, prior_parts = captured(), old_captured(SOURCE)
        prior = review.build_review_data(*prior_parts[:4], **old_options(prior_parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual((prior['schema_version'], current['schema_version']), (30, 31))
        self.assertEqual((current['conditions']['schema_version'],
                          current['aoi_body_context']['schema_version'],
                          current['communication_context']['schema_version']), (4, 2, 2))
        self.assertLess(current['conditions']['coverage']['node_kinds']['opaque_transfer'],
                        prior['conditions']['coverage']['node_kinds']['opaque_transfer'])
        review.validate_review_data(*parts[:4], current, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = save_run(root, *prior_parts[:2], **old_arguments(prior_parts))
            originals = {path.name: path.read_bytes() for path in before.iterdir()}
            after = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((after / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], manifest['review_schema_version']), (34, 31))
            self.assertEqual(len(manifest['artifacts']), 16)
            for name, record in manifest['artifacts'].items():
                self.assertEqual(hashlib.sha256((after / name).read_bytes()).hexdigest(), record['sha256'])
            self.assertEqual(originals, {path.name: path.read_bytes() for path in before.iterdir()})

    def test_incompatible_versions_fail_before_allocating_private_run(self) -> None:
        parts = captured()
        for override in ({'include_residual_interpretation': False},
                         {'include_residual_interpretation': 1},
                         {'include_communication_context': False},
                         {'conditions': old_captured(SOURCE)[11]},
                         {'aoi_body_context': old_captured(SOURCE)[16]}):
            with self.subTest(override=tuple(override)), tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'unallocated'
                with self.assertRaises(StorageError):
                    save_run(destination, *parts[:2], **(arguments(parts) | override))
                self.assertFalse(destination.exists())

    def test_html_and_canonical_replay_reject_mixed_versions(self) -> None:
        parts = captured()
        current = review.build_review_data(*parts[:4], **options(parts))
        for mutate in (lambda d: d.update(schema_version=30, report_version='engineering-review-30'),
                       lambda d: d['conditions'].update(schema_version=3),
                       lambda d: d['aoi_body_context'].update(schema_version=1),
                       lambda d: d['communication_context'].update(schema_version=1)):
            forged = deepcopy(current)
            mutate(forged)
            with self.subTest(mutate=mutate):
                with self.assertRaises(review.ReviewError):
                    review.validate_review_data(*parts[:4], forged, **options(parts))
                with self.assertRaises(review_html.ReviewHtmlError):
                    review_html.render_review_html(forged)

    def test_current_report_reconciles_and_keeps_samples_frozen(self) -> None:
        current, prior = report(), old_report(SOURCE)
        work_check.validate_work_check_report(current)
        self.assertEqual(current['targeted_samples'], prior['targeted_samples'])
        self.assertEqual(current['diagnostic_sample'], None)
        for key in ('reference_summary', 'access_summary', 'calculation_summary',
                    'pid_summary', 'rung_analysis_summary', 'relationship_summary'):
            self.assertEqual(current['analysis'][key], prior['analysis'][key])
        for key in ('condition_summary', 'aoi_body_summary', 'communication_context_summary'):
            forged = deepcopy(current)
            forged['analysis'][key] = prior['analysis'][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                work_check.validate_work_check_report(forged)

    def test_limits_and_public_width_preserve_historical_caps(self) -> None:
        wide = json.dumps(maximum_width_report(), ensure_ascii=True, separators=(',', ':')).encode('utf-8')
        self.assertLessEqual(len(wide), work_check._report_limit(49))
        self.assertEqual(work_check._report_limit(48), 112 * 1024)
        self.assertEqual(work_check._report_limit(49), 128 * 1024)
        self.assertEqual(review_html._limits(30), (456 * 1024 * 1024, 488 * 1024 * 1024))
        self.assertEqual(review_html._limits(31), (464 * 1024 * 1024, 496 * 1024 * 1024))
        parts = captured()
        with patch.object(review, 'MAX_REVIEW_V31_BYTES', 1), tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'unallocated'
            with self.assertRaises(StorageError):
                save_run(destination, *parts[:2], **arguments(parts))
            self.assertFalse(destination.exists())

    def test_publication_accepts_current_cap_and_retains_historical_cap(self) -> None:
        current = work_check.render_work_check_report(report())
        previous = work_check.render_work_check_report(old_report(SOURCE))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'invented.L5X'
            source.write_bytes(SOURCE)
            output = root / 'current.json'
            publish_summary(output, current.ljust(128 * 1024), input_path=source)
            self.assertEqual(output.read_bytes(), current.encode('utf-8'))
            for name, rendered in (
                ('current-too-large.json', current.ljust(128 * 1024 + 1)),
                ('previous-too-large.json', previous.ljust(112 * 1024 + 1)),
            ):
                with self.subTest(name=name), self.assertRaises(SummaryOutputError):
                    publish_summary(root / name, rendered, input_path=source)
                self.assertFalse((root / name).exists())
            self.assertEqual(sorted(path.name for path in root.iterdir()),
                             ['current.json', 'invented.L5X'])


if __name__ == '__main__':
    unittest.main()
