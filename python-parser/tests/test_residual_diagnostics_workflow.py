"""Source diagnostics integrate with saved review and closed public contracts."""
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
from test_control_interpretation_workflow import (
    SOURCE as OLD_SOURCE, captured as old_captured, options as old_options,
    arguments as old_arguments, report as old_report,
    maximum_width_report as old_maximum, ANALYZE_OPTIONS,
)
from test_unmatched_sample_report import REVISION

SOURCE = OLD_SOURCE.replace(b'<Parameters>', b'<RevisionNote>Invented revision</RevisionNote>'
                           b'<AdditionalHelpText>Invented help</AdditionalHelpText><Parameters>', 1)


@lru_cache(maxsize=2)
def captured(data: bytes = SOURCE) -> tuple:
    with source_reuse_scope():
        parts = list(old_captured(data))
        base = (*parts[:3], parts[4], parts[8], parts[9], parts[10])
        parts[11] = work_check.analyze_conditions(*base, schema_version=6)
        common = (*base, parts[11])
        parts[12] = work_check.analyze_binding_context(*common)
        companions = (*common, parts[12])
        parts[13] = work_check.analyze_custom_instruction_context(*companions)
        parts[14] = work_check.analyze_indexed_access(*companions)
        parts[16] = work_check.analyze_aoi_body_context(*companions, parts[13], schema_version=2)
        parts[17] = work_check.analyze_pid_connections(*common, parts[5], parts[6], parts[7], schema_version=2)
        parts[18] = work_check.analyze_calculation_paths(*common)
        parts[19] = work_check.analyze_output_context(*common)
        parts[20] = work_check.analyze_stateful_objects(*common, parts[5])
        parts[23] = work_check.analyze_execution_context(*common, schema_version=3)
        parts[24] = work_check.analyze_signal_context(
            *common, parts[5], parts[19], parts[20], parts[23], schema_version=5)
        parts[25] = work_check.analyze_file_operations(*common, parts[5])
        return tuple(parts)


def options(parts: tuple) -> dict:
    return old_options(parts) | {'include_residual_diagnostics': True}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'include_residual_diagnostics': True}


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
                include_residual_diagnostics=True)
        if analysis['failure_code'] is not None:
            raise AssertionError(analysis['failure_code'])
    payload.update(schema_version=51, workflow_version='work-check-51', analysis=analysis,
                   status='partial' if analysis['status'] == 'partial' else 'passed',
                   diagnostic_sample=analysis.pop('diagnostic_sample'),
                   targeted_samples=analysis.pop('targeted_samples'))
    return payload


def report(data: bytes = SOURCE) -> dict:
    return deepcopy(_report(data))


class ResidualDiagnosticsWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        scope = source_reuse_scope()
        scope.__enter__()
        self.addCleanup(scope.__exit__, None, None, None)

    def test_saved_artifacts_and_legacy_replay(self) -> None:
        parts, before_parts = captured(), old_captured(SOURCE)
        current = review.build_review_data(*parts[:4], **options(parts))
        prior = review.build_review_data(*before_parts[:4], **old_options(before_parts))
        self.assertEqual((prior['schema_version'], current['schema_version']), (32, 33))
        self.assertEqual((current['conditions']['schema_version'], current['execution_context']['schema_version']), (6, 3))
        self.assertLess(current['conditions']['coverage']['aoi_identity_statuses']['body_unqualified'],
                        prior['conditions']['coverage']['aoi_identity_statuses']['body_unqualified'])
        review.validate_review_data(*parts[:4], current, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = save_run(root, *before_parts[:2], **old_arguments(before_parts))
            original = {p.name: p.read_bytes() for p in before.iterdir()}
            after = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((after / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], manifest['review_schema_version']), (36, 33))
            self.assertEqual(len(manifest['artifacts']), 16)
            for name, record in manifest['artifacts'].items():
                raw = (after / name).read_bytes()
                self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (record['size_bytes'], record['sha256']))
            self.assertEqual(original, {p.name: p.read_bytes() for p in before.iterdir()})

    def test_mixed_versions_and_missing_flag_fail_before_save(self) -> None:
        parts = captured()
        for override in ({'include_residual_diagnostics': False}, {'include_residual_diagnostics': 1},
                         {'include_control_interpretation': False}, {'conditions': old_captured(SOURCE)[11]},
                         {'execution_context': old_captured(SOURCE)[23]}):
            with self.subTest(override=tuple(override)), tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'unallocated'
                with self.assertRaises(StorageError):
                    save_run(destination, *parts[:2], **(arguments(parts) | override))
                self.assertFalse(destination.exists())

    def test_current_public_contract_and_frozen_evidence(self) -> None:
        current, prior = report(), old_report(SOURCE)
        work_check.validate_work_check_report(current)
        self.assertEqual(current['targeted_samples'], prior['targeted_samples'])
        self.assertIsNone(current['diagnostic_sample'])
        for key in ('condition_summary', 'execution_context_summary', 'rack_backing_summary'):
            forged = deepcopy(current)
            forged['analysis'][key] = prior['analysis'][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                work_check.validate_work_check_report(forged)
        self.assertEqual(current['analysis']['pid_connection_summary'], prior['analysis']['pid_connection_summary'])

    def test_rendered_diagnostics_and_version_gates(self) -> None:
        parts = captured()
        current = review.build_review_data(*parts[:4], **options(parts))
        rendered = review_html.render_review_html(current)
        for text in ('Remaining source qualification gaps', 'First body qualification gap', 'Unsupported instance form'):
            self.assertIn(text, rendered)
        for key, version in (('conditions', 5), ('execution_context', 2)):
            forged = deepcopy(current)
            forged[key]['schema_version'] = version
            with self.subTest(key=key), self.assertRaises(review_html.ReviewHtmlError):
                review_html.render_review_html(forged)

    def test_bounded_publication_and_private_limits(self) -> None:
        current = report()
        def grow(value):
            if type(value) is int:
                return 10**12
            return {k: grow(v) for k, v in value.items()} if type(value) is dict else value
        wide = old_maximum()
        wide.update(schema_version=51, workflow_version='work-check-51')
        for key in ('condition_summary', 'execution_context_summary', 'rack_backing_summary'):
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
        self.assertEqual(work_check._report_limit(50), 128 * 1024)
        self.assertEqual(work_check._report_limit(51), 144 * 1024)
        self.assertEqual(review_html._limits(33), review_html._limits(32))
        parts = captured()
        with patch.object(review, 'MAX_REVIEW_V33_BYTES', 1), tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'unallocated'
            with self.assertRaises(StorageError):
                save_run(destination, *parts[:2], **arguments(parts))
            self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
