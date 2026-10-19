"""Qualified rack joins version assemblies without rewriting earlier evidence."""
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
from plc_workbench.engineering_assemblies_summary import validate_engineering_assemblies_summary
from plc_workbench.source_reuse import source_reuse_scope
from plc_workbench.storage import StorageError, save_run
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from plc_workbench.targeted_sample_history import sample_envelope
from test_rack_backing_context import fixture
from test_rack_backing_context_workflow import (
    captured, options as old_options, arguments as old_arguments,
    report as old_report, ANALYZE_OPTIONS, old_maximum,
)
from test_unmatched_sample_report import REVISION
from test_work_check_timing import timing_fixture


SOURCE = fixture().encode()
CURRENT_OPTIONS = dict(ANALYZE_OPTIONS, engineering_assemblies_schema_version=3,
    include_residual_interpretation=True, include_control_interpretation=True,
    include_residual_diagnostics=True, include_rack_backing_context=True)


def options(parts: tuple) -> dict:
    return old_options(parts) | {'engineering_assemblies_schema_version': 3}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'engineering_assemblies_schema_version': 3}


@lru_cache(maxsize=2)
def _report(data: bytes) -> dict:
    payload = old_report(data)
    frozen = payload['targeted_samples']
    with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
        root = Path(folder).resolve()
        source = root / 'invented.L5X'
        source.write_bytes(data)
        with patch.object(work_check, 'resolve_targeted_samples', return_value=deepcopy(frozen)):
            analysis = work_check._analyze(root, source, root, REVISION, **CURRENT_OPTIONS)
        if analysis['failure_code'] is not None:
            raise AssertionError(analysis['failure_code'])
    payload.update(schema_version=53, workflow_version='work-check-53', analysis=analysis,
        status='partial' if analysis['status'] == 'partial' else 'passed',
        diagnostic_sample=analysis.pop('diagnostic_sample'),
        targeted_samples=analysis.pop('targeted_samples'))
    return payload


def report(data: bytes = SOURCE) -> dict:
    return deepcopy(_report(data))


class EngineeringAssembliesRackWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        scope = source_reuse_scope()
        scope.__enter__()
        self.addCleanup(scope.__exit__, None, None, None)

    def test_review_replays_rack_before_assemblies_and_preserves_providers(self) -> None:
        parts = captured(SOURCE)
        current = review.build_review_data(*parts[:4], **options(parts))
        prior = review.build_review_data(*parts[:4], **old_options(parts))
        self.assertEqual((prior['schema_version'], current['schema_version']), (34, 35))
        self.assertEqual(current['engineering_assemblies']['schema_version'], 3)
        for key, value in prior.items():
            if key not in {'schema_version', 'report_version', 'status', 'engineering_assemblies'}:
                self.assertEqual(value, current[key], key)
        self.assertGreater(current['engineering_assemblies']['coverage']['rack_memberships_total'], 0)
        review.validate_review_data(*parts[:4], current, **options(parts))
        forged = deepcopy(current)
        membership = next(row for row in forged['engineering_assemblies']['memberships']
                          if row['rack_source_use_ids'])
        membership['rack_source_use_ids'] = []
        with self.assertRaises(review.ReviewError):
            review.validate_review_data(*parts[:4], forged, **options(parts))

    def test_save_finalizes_sixteen_verified_artifacts_with_new_versions(self) -> None:
        parts = captured(SOURCE)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = save_run(root, *parts[:2], **old_arguments(parts))
            retained = {path.name: path.read_bytes() for path in before.iterdir()}
            after = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((after / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], manifest['review_schema_version']), (38, 35))
            self.assertEqual(manifest['engineering_assemblies_schema_version'], 3)
            self.assertEqual(manifest['rack_backing_context_schema_version'], 1)
            self.assertEqual(len(manifest['artifacts']), 16)
            for name, entry in manifest['artifacts'].items():
                raw = (after / name).read_bytes()
                self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()),
                                 (entry['size_bytes'], entry['sha256']))
            self.assertEqual(retained, {path.name: path.read_bytes() for path in before.iterdir()})

    def test_v3_requires_complete_flags_before_source_or_private_allocation(self) -> None:
        parts = captured(SOURCE)
        for override in ({'include_rack_backing_context': False},
                         {'include_residual_diagnostics': False},
                         {'include_engineering_assemblies': False},
                         {'engineering_assemblies_schema_version': True},
                         {'engineering_assemblies_schema_version': 4}):
            with self.subTest(override=override), patch.object(work_check, 'capture_snapshot') as capture:
                result = work_check._analyze(Path('.'), Path('invented.L5X'), Path('.'),
                                            REVISION, **(CURRENT_OPTIONS | override))
                capture.assert_not_called()
                self.assertFalse(result['private_run_saved'])
                self.assertIsNotNone(result['failure_code'])
            with tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'unallocated'
                with self.assertRaises(StorageError):
                    save_run(destination, *parts[:2], **(arguments(parts) | override))
                self.assertFalse(destination.exists())

    def test_public_contract_preserves_other_summaries_and_frozen_samples(self) -> None:
        current, prior = report(), old_report(SOURCE)
        work_check.validate_work_check_report(current)
        work_check.validate_work_check_report(prior)
        for key, value in prior['analysis'].items():
            if key not in {'engineering_assemblies_summary', 'status'}:
                self.assertEqual(value, current['analysis'][key], key)
        self.assertEqual(current['targeted_samples'], prior['targeted_samples'])
        self.assertIsNone(current['diagnostic_sample'])
        for change in ('old_parent', 'old_child', 'boolean_version', 'private_field'):
            forged = deepcopy(current)
            if change == 'old_parent':
                forged.update(schema_version=52, workflow_version='work-check-52')
            elif change == 'old_child':
                forged['analysis']['engineering_assemblies_summary'] = prior['analysis']['engineering_assemblies_summary']
            elif change == 'boolean_version':
                forged['analysis']['engineering_assemblies_summary']['schema_version'] = True
            else:
                forged['analysis']['engineering_assemblies_summary']['source_address'] = 'PRIVATE_SENTINEL'
            with self.subTest(change=change), self.assertRaises(ValueError):
                work_check.validate_work_check_report(forged)

    def test_html_pairs_v35_only_with_assembly3_and_rack1(self) -> None:
        parts = captured(SOURCE)
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertIn('rack_source_use_ids', review_html.render_review_html(current))
        for change in ('old_parent', 'old_child', 'missing_rack', 'wrong_rack', 'wrong_analyzer'):
            forged = deepcopy(current)
            if change == 'old_parent':
                forged.update(schema_version=34, report_version='engineering-review-34')
            elif change == 'old_child':
                forged['engineering_assemblies']['schema_version'] = 2
            elif change == 'missing_rack':
                del forged['rack_backing_context']
            elif change == 'wrong_rack':
                forged['rack_backing_context']['schema_version'] = 2
            else:
                forged['engineering_assemblies']['analyzer_version'] = 'engineering-assemblies-2'
            with self.subTest(change=change), self.assertRaises(review_html.ReviewHtmlError):
                review_html.render_review_html(forged)

    def test_recovered_memberships_cannot_exceed_independent_source_counts(self) -> None:
        current = report()
        rack = current['analysis']['rack_backing_context_summary']['coverage']
        signal = current['analysis']['signal_context_summary']['coverage']
        capacities = {
            'read': rack['associated_uses_by_role']['read'],
            'write': rack['associated_uses_by_role']['write'],
            'read_write': rack['associated_uses_by_role']['read_write'],
            'boolean_condition': rack['associated_predicate_uses'],
            'boolean_output': rack['associated_output_uses'],
            'sfc_reference': rack['sfc_uses_by_disposition']['associated'],
            'guard_condition': signal['dependency_read_links_total'],
        }
        for relation, capacity in capacities.items():
            candidate = deepcopy(current)
            nested = candidate['analysis']['engineering_assemblies_summary']
            coverage = nested['coverage']
            extra = capacity + 1 - coverage['rack_memberships_by_relation'][relation]
            coverage['rack_memberships_by_relation'][relation] += extra
            coverage['rack_memberships_total'] += extra
            coverage['memberships_by_relation'][relation] += extra
            coverage['memberships_by_provider']['sfc_context' if relation == 'sfc_reference'
                                                else 'signal_context'] += extra
            coverage['memberships_total'] += extra
            coverage['visited_links'] += extra
            coverage['retained_bytes'] += extra * 512
            # Internally consistent assembly counts alone cannot prove that the
            # independent rack or guard source populations support those links.
            validate_engineering_assemblies_summary(nested)
            with self.subTest(relation=relation), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        candidate = deepcopy(current)
        nested = candidate['analysis']['engineering_assemblies_summary']
        nested['coverage']['known_non_address_guard_inputs_by_kind']['literal'] += signal['dependency_read_links_total'] + 1
        nested['coverage']['visited_links'] += signal['dependency_read_links_total'] + 1
        validate_engineering_assemblies_summary(nested)
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)

    def test_exact_guard_cannot_be_relabeled_without_a_qualified_rack_guard_source(self) -> None:
        tags = ('<Tag Name="RegularInput" DataType="BOOL"/>'
                '<Tag Name="RegularOutput" DataType="BOOL"/>'
                '<Tag Name="Accumulator" DataType="DINT"/>')
        for unrelated_rack_read in (False, True):
            rungs = ('XIC(RegularInput)OTE(RegularOutput);',)
            if unrelated_rack_read:
                rungs += ('MOV(Remote:3:I.Data,Accumulator);',)
            current = report(fixture(rungs=rungs, sfc='', tags=tags).encode())
            work_check.validate_work_check_report(current)
            rack = current['analysis']['rack_backing_context_summary']['coverage']
            self.assertEqual(rack['rll_uses_by_disposition']['associated'], int(unrelated_rack_read))
            self.assertEqual(rack['associated_predicate_uses'], 0)
            self.assertEqual(rack['associated_output_uses'], 0)
            nested = current['analysis']['engineering_assemblies_summary']
            coverage = nested['coverage']
            self.assertEqual(coverage['memberships_by_relation']['guard_condition'], 1)
            self.assertEqual(coverage['rack_memberships_by_relation']['guard_condition'], 0)
            # Relabel an existing guard without changing any membership or
            # dependency populations. The assembly alone is self-consistent.
            coverage['rack_memberships_by_relation']['guard_condition'] = 1
            coverage['rack_memberships_total'] += 1
            validate_engineering_assemblies_summary(nested)
            with self.subTest(unrelated_rack_read=unrelated_rack_read), self.assertRaises(ValueError):
                work_check.validate_work_check_report(current)

    def test_failed_assembly_stays_sanitized_and_never_saves(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(SOURCE)
            with patch.object(work_check, 'build_engineering_assemblies', side_effect=ValueError('PRIVATE_SENTINEL')), \
                    patch.object(work_check, 'save_run') as save:
                failed = work_check._analyze(root, source, root, REVISION, **CURRENT_OPTIONS)
            save.assert_not_called()
        self.assertEqual(failed['failure_code'], 'engineering_assemblies_error')
        self.assertFalse(failed['private_run_saved'])
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(failed))
        failed.pop('diagnostic_sample')
        failed.pop('targeted_samples')
        payload = report()
        payload.update(status='failed', analysis=failed, targeted_samples=sample_envelope(),
                       timings=timing_fixture(('application_tests', 'helpers_tests', 'analysis_build')))
        work_check.validate_work_check_report(payload)
        self.assertTrue(all(value is None for key, value in failed.items() if key.endswith('_summary')))

    def test_existing_size_envelope_supports_v53_and_private_caps_remain(self) -> None:
        current = report()
        def grow(value):
            if type(value) is int:
                return 10**12
            return {key: grow(item) for key, item in value.items()} if type(value) is dict else value
        wide = old_maximum()
        wide.update(schema_version=53, workflow_version='work-check-53')
        for key in ('condition_summary', 'execution_context_summary', 'rack_backing_summary',
                    'rack_backing_context_summary', 'engineering_assemblies_summary'):
            wide['analysis'][key] = grow(current['analysis'][key])
        self.assertLessEqual(len(json.dumps(wide, separators=(',', ':')).encode()), 144 * 1024)
        self.assertEqual(work_check._report_limit(53), 144 * 1024)
        self.assertEqual(review_html._limits(35), (472 * 1024 * 1024, 504 * 1024 * 1024))
        rendered = work_check.render_work_check_report(current)
        for sentinel in ('Remote:3:I', 'ProbeAlias', 'rack_source_use_ids', 'PRIVATE_SENTINEL'):
            self.assertNotIn(sentinel, rendered)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            publish_summary(root / 'valid.json', rendered.ljust(144 * 1024), input_path=root / 'invented.L5X')
            self.assertEqual((root / 'valid.json').read_bytes(), rendered.encode())
            with self.assertRaises(SummaryOutputError):
                publish_summary(root / 'large.json', rendered.ljust(144 * 1024 + 1), input_path=root / 'invented.L5X')
            self.assertFalse((root / 'large.json').exists())
        parts = captured(SOURCE)
        with patch.object(review, 'MAX_REVIEW_V35_BYTES', 1), tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'unallocated'
            with self.assertRaises(StorageError):
                save_run(destination, *parts[:2], **arguments(parts))
            self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
