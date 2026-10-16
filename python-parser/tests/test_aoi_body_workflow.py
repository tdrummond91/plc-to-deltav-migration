"""AOI body/instance evidence and SFR diagnostics retain historical boundaries."""
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
from plc_workbench.aoi_body_context import AoiBodyContextError, analyze_aoi_body_context
from plc_workbench.aoi_body_summary import build_aoi_body_summary, validate_aoi_body_summary
from plc_workbench.sfr_context import analyze_sfr_context
from plc_workbench.sfr_summary import build_sfr_summary
from plc_workbench.storage import StorageError, save_run
from plc_workbench.summary_output import publish_summary
from test_stateful_sequence_workflow import (
    captured as old_captured, options as old_options, arguments as old_arguments,
    report as old_report,
)
from test_instruction_context_workflow import companion_inputs
from test_binding_context_workflow import ROOT, source
from test_unmatched_sample_report import REVISION

SOURCE = (ROOT / 'public/fixtures/synthetic/aoi_body_demo.L5X').read_bytes()


@lru_cache(maxsize=6)
def captured(data: bytes = SOURCE) -> tuple:
    parts = list(old_captured(data))
    parts[15] = analyze_sfr_context(*parts[:3], parts[4], parts[8], parts[3], schema_version=2)
    return (*parts, analyze_aoi_body_context(*companion_inputs(parts), parts[13]))


def options(parts: tuple) -> dict:
    return old_options(parts) | {'aoi_body_context': parts[16]}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'aoi_body_context': parts[16]}


def report(data: bytes = SOURCE) -> dict:
    payload = old_report(data)
    parts = captured(data)
    payload.update(schema_version=31, workflow_version='work-check-31')
    payload['analysis']['sfr_summary'] = build_sfr_summary(
        *parts[:3], parts[4], parts[8], parts[3], parts[15], revision=REVISION)
    payload['analysis']['aoi_body_summary'] = build_aoi_body_summary(
        *companion_inputs(parts), parts[13], parts[16], revision=REVISION)
    status = 'partial' if any(item['status'] == 'partial' for key, item in payload['analysis'].items()
                              if key.endswith('_summary')) else 'complete'
    payload['analysis']['status'] = status
    payload['status'] = 'partial' if status == 'partial' else 'passed'
    return payload


class AoiBodyWorkflowTests(unittest.TestCase):
    def test_review14_manifest17_keep_all_prior_analysis_and_artifact_bytes(self) -> None:
        previous, parts = old_captured(SOURCE), captured()
        old = review.build_review_data(*previous[:4], **old_options(previous))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual((current['schema_version'], current['sfr_context']['schema_version']), (14, 2))
        for key in old.keys() - {'schema_version', 'report_version', 'status', 'sfr_context'}:
            self.assertEqual(current[key], old[key], key)
        for key in ('calls', 'steps', 'status'):
            self.assertEqual(current['sfr_context'][key], old['sfr_context'][key])
        review.validate_review_data(*parts[:4], current, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = save_run(root, *previous[:2], **old_arguments(previous))
            old_bytes = {p.name: p.read_bytes() for p in before.iterdir()}
            after = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((after / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (17, 16))
            self.assertEqual(manifest['review_schema_version'], 14)
            self.assertEqual(manifest['sfr_context_analyzer_version'], 'sfr-context-2')
            self.assertEqual(manifest['aoi_body_context_analyzer_version'], 'aoi-body-context-1')
            for name, content in old_bytes.items():
                self.assertEqual((before / name).read_bytes(), content)
                if name not in {'manifest.json', 'review.html'}:
                    self.assertEqual((after / name).read_bytes(), content, name)

    def test_review_requires_canonical_aoi_and_sfr2_pair(self) -> None:
        parts = captured()
        for change in ({'sfr_context': None}, {'sfr_context': old_captured(SOURCE)[15]},
                       {'aoi_body_context': None}, {'indexed_access': None}):
            with self.subTest(change=change.keys()), self.assertRaises(review.ReviewError):
                review.build_review_data(*parts[:4], **(options(parts) | change))
        for field in ('symbols', 'calls', 'routines'):
            forged = replace(parts[16], **{field: []})
            with self.subTest(field=field), self.assertRaises(review.ReviewError):
                review.build_review_data(*parts[:4], **(options(parts) | {'aoi_body_context': forged}))
        current = review.build_review_data(*parts[:4], **options(parts))
        current['aoi_body_context']['coverage']['body_symbol_operand_uses'] += 1
        with self.assertRaises(review.ReviewError):
            review.validate_review_data(*parts[:4], current, **options(parts))

    def test_work31_only_sfr_summary_changes_and_sampler_record_is_identical(self) -> None:
        old, current = old_report(SOURCE), report()
        work_check.validate_work_check_report(current)
        self.assertEqual(current['targeted_samples'], old['targeted_samples'])
        for key in old['analysis'].keys() - {'sfr_summary', 'status'}:
            self.assertEqual(current['analysis'][key], old['analysis'][key], key)
        self.assertEqual(json.loads(work_check.render_work_check_report(current)), current)
        for mutate in (lambda p: p.update(schema_version=30, workflow_version='work-check-30'),
                       lambda p: p['analysis'].update(sfr_summary=old['analysis']['sfr_summary']),
                       lambda p: p['analysis'].pop('aoi_body_summary')):
            bad = deepcopy(current)
            mutate(bad)
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)

    def test_aoi_cross_counts_reject_omitted_declarations_and_overstated_accesses(self) -> None:
        for key in ('source_rungs', 'source_instructions', 'source_operands', 'source_expression_uses',
                    'parameters_total', 'local_tags_total', 'routines_total'):
            bad = report()
            bad['analysis']['aoi_body_summary']['coverage'][key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)
        bad = report()
        summary = bad['analysis']['aoi_body_summary']
        c = summary['coverage']
        for key in c:
            if not key.startswith('source_') and key not in {'calls_total', 'calls_by_instance_status',
                    'instance_datatype_status', 'instance_address_shape'}:
                c[key] = dict.fromkeys(c[key], 0) if type(c[key]) is dict else 0
        validate_aoi_body_summary(summary)
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(bad)
        bad = report()
        c = bad['analysis']['aoi_body_summary']['coverage']
        overflow = bad['analysis']['access_summary']['coverage']['operands_by_role']['write'] - c['body_operands_by_role']['write'] + 1
        c['body_operands_by_role']['read'] -= overflow
        c['body_operands_by_role']['write'] += overflow
        validate_aoi_body_summary(bad['analysis']['aoi_body_summary'])
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(bad)
        bad = report()
        bad['analysis']['aoi_body_summary']['tool_revision']['commit'] = 'f' * 40
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(bad)

    def test_runner_saves_current_review_and_replays_without_selecting_more(self) -> None:
        from plc_workbench.targeted_sample_history import sample_envelope
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            path = root / 'invented.L5X'
            path.write_bytes(SOURCE)
            first = work_check._analyze(root, path, root, REVISION)
            self.assertIsNone(first['failure_code'])
            envelope = first.pop('targeted_samples')
            self.assertIsNone(first.pop('diagnostic_sample'))
            payload = report()
            payload.update(schema_version=33, workflow_version='work-check-33', analysis=first, targeted_samples=envelope)
            work_check.validate_work_check_report(payload)
            path.write_bytes(source('NOP();'))
            with patch.object(work_check, 'build_targeted_samples', side_effect=AssertionError('No additional disclosure.')):
                second = work_check._analyze(root, path, root, REVISION)
            self.assertIsNone(second['failure_code'])
            self.assertEqual(second['targeted_samples'], sample_envelope('replayed', envelope['record']))

    def test_aoi_failure_uses_fixed_code_and_keeps_private_details_out_of_report(self) -> None:
        from test_save_diagnostics import failed_report
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            path = root / 'invented.L5X'
            path.write_bytes(SOURCE)
            with patch.object(work_check, 'analyze_aoi_body_context', side_effect=AoiBodyContextError('PRIVATE_FAILURE')):
                result = work_check._analyze(root, path, root, REVISION)
            self.assertEqual((result['failure_code'], result['private_run_saved']), ('aoi_body_context_error', False))
            self.assertIsNone(result['aoi_body_summary'])
            payload = failed_report(33, 'aoi_body_context_error')
            payload['analysis'] = {k: v for k, v in result.items() if k not in {'diagnostic_sample', 'targeted_samples'}}
            self.assertNotIn('PRIVATE_FAILURE', work_check.render_work_check_report(payload))
            self.assertIn('PRIVATE_FAILURE', (root / 'analysis.log').read_text())
            payload.update(schema_version=30, workflow_version='work-check-30')
            payload['analysis'].pop('aoi_body_summary')
            payload['analysis'].pop('pid_connection_summary')
            payload['analysis'].pop('calculation_path_summary')
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)

    def test_current_limits_are_separate_and_failed_save_has_no_final_manifest(self) -> None:
        parts = captured()
        old = old_captured(SOURCE)
        previous = review.build_review_data(*old[:4], **old_options(old))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual(review.MAX_REVIEW_V14_BYTES, 200 * 1024 * 1024)
        self.assertEqual(review_html._limits(14), (200 * 1024 * 1024, 232 * 1024 * 1024))
        self.assertEqual(review_html._limits(13), (192 * 1024 * 1024, 224 * 1024 * 1024))
        with patch.object(review, 'MAX_REVIEW_V14_BYTES', 1):
            review.render_review_json(previous)
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(StorageError) as error:
                    save_run(Path(folder), *parts[:2], **arguments(parts))
                self.assertEqual(error.exception.code, 'review_size_limit')
                self.assertFalse(list(Path(folder).rglob('manifest.json')))
        for key in ('MAX_REVIEW_V14_PAYLOAD_BYTES', 'MAX_REVIEW_V14_HTML_BYTES'):
            with patch.object(review_html, key, 1):
                review_html.render_review_html(previous)
                with self.assertRaises(review_html.ReviewHtmlSizeLimitError):
                    review_html.render_review_html(current)
        self.assertEqual(work_check._report_limit(31), 64 * 1024)

    def test_publication_retains_closed_counts_and_no_source_names(self) -> None:
        payload = report()
        for key in ('aoi_body_summary', 'sfr_summary'):
            encoded = json.dumps(payload['analysis'][key])
            for token in ('DemoBlend', 'States', 'SelectedChart', 'instruction_id', 'routine_id', 'declaration_id'):
                self.assertNotIn(token, encoded)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'feedback.json'
            publish_summary(path, work_check.render_work_check_report(payload), input_path=Path(folder) / 'invented.L5X')
            self.assertEqual(json.loads(path.read_bytes()), payload)

    def test_compact_work31_fits_conservative_schema_width_and_sample_budget(self) -> None:
        from plc_workbench.ladder.syntax import PUBLIC_OPCODES
        from plc_workbench.summary import DIAGNOSTIC_CODES, MAX_COUNT
        from plc_workbench.targeted_samples import MAX_BYTES
        # This is a serialization upper-bound probe, not fabricated valid
        # engineering evidence: impossible simultaneous maxima overestimate
        # each count width and include every optional closed histogram key.
        def grow(value, maximum=MAX_COUNT):
            if type(value) is int:
                return maximum
            if type(value) is dict:
                return {key: grow(child, maximum) for key, child in value.items()}
            if type(value) is list:
                return [grow(child, maximum) for child in value]
            return value
        maximum = grow(report())
        maximum['schema_version'] = 31
        for key in ('aoi_body_summary', 'sfr_summary', 'custom_instruction_summary',
                    'indexed_access_summary', 'binding_context_summary'):
            maximum['analysis'][key] = grow(maximum['analysis'][key], 250_000)
        source_counts = maximum['analysis']['reference_summary']['source_summary']
        # work31 source instruction totals equal AOI source_instructions,
        # which is bounded to 250,000; every histogram bin is no larger.
        source_counts['instructions']['counts'].update(dict.fromkeys(PUBLIC_OPCODES, 250_000))
        source_counts['diagnostics']['by_code'].update(dict.fromkeys(DIAGNOSTIC_CODES, MAX_COUNT))
        # The encoded request is already capped at16KiB. A string of that
        # length adds two extra quotes, conservatively bounding compact JSON.
        maximum['targeted_samples']['record'] = 'x' * MAX_BYTES
        encoded = work_check._serialize_report(maximum)
        self.assertLess(len(encoded.encode()), 64 * 1024)
        work_check._report_size(maximum)
        old = old_report(SOURCE)
        self.assertEqual(work_check.render_work_check_report(old), json.dumps(
            old, indent=2, sort_keys=True, ensure_ascii=True) + chr(10))
        current = report()
        self.assertEqual(work_check.render_work_check_report(current), json.dumps(
            current, separators=(',', ':'), sort_keys=True, ensure_ascii=True) + chr(10))
        with patch.object(work_check, 'MAX_REPORT_V28_BYTES', len(work_check.render_work_check_report(current)) - 1):
            with self.assertRaises(work_check.WorkCheckError):
                work_check.render_work_check_report(current)

    def test_valid_large_sample_and_maximum_permitted_independent_counts_publish(self) -> None:
        from test_targeted_samples import build
        from plc_workbench.targeted_sample_history import sample_envelope
        padding = ''.join(f'MOV({i},X{i})' for i in range(14))
        record = build(tuple(text + padding + ';' for text in (
            'XIC(A[B])', 'MOV(C[D],E)', 'PrivateBlock(F,G)',
            'XIC(H)ONS(I)OTE(J)', 'SFR(K,L,9)', '[LES(M,99),XIC(N)]OTE(O)')))
        self.assertEqual(record['charged_rungs'], 6)
        self.assertGreater(len(json.dumps(record)), 5000)
        payload = report()
        payload['targeted_samples'] = sample_envelope('replayed', record)
        counts = payload['analysis']['reference_summary']['source_summary']
        counts['counts']['trends'] = 10 ** 12
        for result in payload['tests'].values():
            result['counts']['tests_run'] = 10 ** 9
            result['counts']['skipped'] = 10 ** 9
        work_check.validate_work_check_report(payload)
        encoded = work_check.render_work_check_report(payload)
        self.assertLess(len(encoded.encode()), 64 * 1024)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'large-feedback.json'
            publish_summary(path, encoded, input_path=Path(folder) / 'invented.L5X')
            self.assertEqual(json.loads(path.read_bytes()), payload)

    def test_html_uses_paginated_safe_source_links_and_preserves_old_report_versions(self) -> None:
        parts = captured()
        data = review.build_review_data(*parts[:4], **options(parts))
        rendered = review_html.render_review_html(data)
        for text in ('First-field instance context', 'Zero observed accesses does not mean unused',
                     'Declaration-owned symbols', 'Directly named operand slots', 'Resolved-root expression leaves',
                     'Original missing result is unchanged', 'Other edits of the requested chart', 'PAGE_SIZE = 50'):
            self.assertIn(text, rendered)
        self.assertNotIn('.innerHTML', rendered)
        self.assertIn("connect-src 'none'", rendered)
        self.assertNotIn('</script><script>window', rendered)
        for mutate in (lambda d: d.update(aoi_body_context=None),
                       lambda d: d['aoi_body_context'].update(schema_version=True),
                       lambda d: d['sfr_context'].update(schema_version=1),
                       lambda d: d.update(schema_version=13, report_version='engineering-review-13')):
            bad = deepcopy(data)
            mutate(bad)
            with self.assertRaises(review_html.ReviewHtmlError):
                review_html.render_review_html(bad)


if __name__ == '__main__':
    unittest.main()
