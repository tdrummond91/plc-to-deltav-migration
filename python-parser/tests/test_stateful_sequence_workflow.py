"""Occurrence-local ONS and SFR candidates retain versioned evidence boundaries."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from functools import lru_cache
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import review, review_html, work_check
from plc_workbench.binding_context import analyze_binding_context
from plc_workbench.conditions import analyze_conditions
from plc_workbench.condition_summary import build_condition_summary
from plc_workbench.custom_instruction_context import analyze_custom_instruction_context
from plc_workbench.indexed_access import analyze_indexed_access
from plc_workbench.sfr_context import SfrContextError, analyze_sfr_context
from plc_workbench.sfr_summary import build_sfr_summary, validate_sfr_summary
from plc_workbench.storage import StorageError, save_run
from plc_workbench.summary_output import publish_summary
from plc_workbench.targeted_sample_history import sample_envelope
from test_instruction_context_workflow import (
    captured as old_captured, options as old_options, arguments as old_arguments,
    report as old_report, companion_inputs,
)
from test_binding_context_workflow import ROOT, source
from test_targeted_sample_workflow import sample_source
from test_unmatched_sample_report import REVISION


SOURCE = (ROOT / 'public/fixtures/synthetic/stateful_sequence_demo.L5X').read_bytes()


@lru_cache(maxsize=6)
def captured(data: bytes = SOURCE) -> tuple:
    parts = list(old_captured(data))
    parts[11] = analyze_conditions(*parts[:3], parts[4], parts[8], parts[9], parts[10], schema_version=3)
    parts[12] = analyze_binding_context(*parts[:3], parts[4], parts[8], parts[9], parts[10], parts[11])
    inputs = companion_inputs(parts)
    parts[13] = analyze_custom_instruction_context(*inputs)
    parts[14] = analyze_indexed_access(*inputs)
    return (*parts, analyze_sfr_context(*parts[:3], parts[4], parts[8], parts[3]))


def options(parts: tuple) -> dict:
    return old_options(parts) | {'sfr_context': parts[15]}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'sfr_context': parts[15]}


def report(data: bytes = SOURCE) -> dict:
    payload = old_report(data)
    parts = captured(data)
    payload.update(schema_version=30, workflow_version='work-check-30')
    payload['analysis']['condition_summary'] = build_condition_summary(
        *parts[:3], parts[4], parts[8], parts[9], parts[10], parts[11], revision=REVISION)
    payload['analysis']['sfr_summary'] = build_sfr_summary(
        *parts[:3], parts[4], parts[8], parts[3], parts[15], revision=REVISION)
    status = 'partial' if any(item['status'] == 'partial' for key, item in payload['analysis'].items()
                              if key.endswith('_summary')) else 'complete'
    payload['analysis']['status'] = status
    payload['status'] = 'partial' if status == 'partial' else 'passed'
    return payload


class StatefulSequenceWorkflowTests(unittest.TestCase):
    def test_review13_manifest16_preserve_prior_evidence_except_condition_semantics(self) -> None:
        previous, parts = old_captured(SOURCE), captured()
        old = review.build_review_data(*previous[:4], **old_options(previous))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual((current['schema_version'], current['conditions']['schema_version']), (13, 3))
        for key in old.keys() - {'schema_version', 'report_version', 'status', 'conditions'}:
            self.assertEqual(current[key], old[key], key)
        review.validate_review_data(*parts[:4], current, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = save_run(root, *previous[:2], **old_arguments(previous))
            old_bytes = {p.name: p.read_bytes() for p in before.iterdir()}
            after = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((after / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (16, 16))
            self.assertEqual((manifest['review_schema_version'], manifest['condition_schema_version']), (13, 3))
            self.assertEqual(manifest['sfr_context_analyzer_version'], 'sfr-context-1')
            for name, content in old_bytes.items():
                self.assertEqual((before / name).read_bytes(), content)
                if name not in {'manifest.json', 'review.html', 'boolean-conditions.json'}:
                    self.assertEqual((after / name).read_bytes(), content, name)

    def test_review_requires_canonical_sfr_and_condition3_pair(self) -> None:
        parts = captured()
        for change in ({'sfr_context': None}, {'conditions': old_captured(SOURCE)[11]}, {'indexed_access': None}):
            with self.assertRaises(review.ReviewError):
                review.build_review_data(*parts[:4], **(options(parts) | change))
        forged = deepcopy(parts[15])
        forged.coverage['calls_total'] += 1
        with self.assertRaises(review.ReviewError):
            review.build_review_data(*parts[:4], **(options(parts) | {'sfr_context': forged}))
        current = review.build_review_data(*parts[:4], **options(parts))
        current['conditions']['outputs'][0]['has_stateful'] = not current['conditions']['outputs'][0]['has_stateful']
        with self.assertRaises(review.ReviewError):
            review.validate_review_data(*parts[:4], current, **options(parts))

    def test_work30_only_condition_summary_changes_and_sampler_record_is_identical(self) -> None:
        old, current = old_report(SOURCE), report()
        work_check.validate_work_check_report(current)
        self.assertEqual(current['targeted_samples'], old['targeted_samples'])
        for key in old['analysis'].keys() - {'condition_summary', 'status'}:
            self.assertEqual(current['analysis'][key], old['analysis'][key], key)
        self.assertEqual(json.loads(work_check.render_work_check_report(current)), current)
        for mutate in (lambda p: p.update(schema_version=29, workflow_version='work-check-29'),
                       lambda p: p['analysis'].update(condition_summary=old['analysis']['condition_summary']),
                       lambda p: p['analysis'].pop('sfr_summary')):
            bad = deepcopy(current)
            mutate(bad)
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)

    def test_sfr_counts_reconcile_source_signature_and_chart_populations(self) -> None:
        for key in ('source_rungs', 'source_instructions', 'source_operands', 'source_sfc_contents', 'source_sfc_routines'):
            bad = report()
            bad['analysis']['sfr_summary']['coverage'][key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)
        bad = report(source('SFR(Missing,0);'))
        summary = bad['analysis']['sfr_summary']
        for key, value in summary['coverage'].items():
            if not key.startswith('source_'):
                summary['coverage'][key] = dict.fromkeys(value, 0) if type(value) is dict else 0
        summary['status'] = 'complete'
        validate_sfr_summary(summary)
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(bad)
        bad = report()
        bad['analysis']['sfr_summary']['tool_revision']['commit'] = 'f' * 40
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(bad)

    def test_case_variant_opcodes_share_one_withheld_population(self) -> None:
        payload = report(source('ons(A)mov(A,INDEX)sfr(Missing,0)OTE(A);'))
        work_check.validate_work_check_report(payload)
        source_counts = payload['analysis']['reference_summary']['source_summary']['instructions']['counts']
        self.assertEqual(source_counts['withheld'], 3)
        # Moving the SFR allowance to an unrelated public opcode preserves the
        # source histogram total while leaving insufficient shared capacity.
        source_counts['withheld'] -= 1
        source_counts['NOP'] = source_counts.get('NOP', 0) + 1
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_fresh_sampler_keeps_condition2_ons_slot_and_replay_never_reselects(self) -> None:
        data = sample_source(200).replace(b'MOV(A[INDEX],A);', b'XIC(A)ONS(INDEX)OTE(A);')
        data = data.replace(b'NOP();', b'MOV(A,A);')
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            path = root / 'invented.L5X'
            path.write_bytes(data)
            first = work_check._analyze(root, path, root, REVISION)
            self.assertIsNone(first['failure_code'])
            envelope = first.pop('targeted_samples')
            self.assertEqual(envelope['status'], 'selected')
            self.assertEqual(envelope['record']['cases'][3]['status'], 'included')
            self.assertEqual(first['condition_summary']['coverage']['stateful_opcodes']['ONS'], 1)
            self.assertEqual(first['condition_summary']['coverage']['node_kinds']['opaque_transfer'], 0)
            self.assertIsNone(first.pop('diagnostic_sample'))
            from test_aoi_body_workflow import report as current_report
            payload = current_report(data)
            payload.update(analysis=first, targeted_samples=envelope)
            work_check.validate_work_check_report(payload)
            path.write_bytes(source('NOP();'))
            with patch.object(work_check, 'build_targeted_samples', side_effect=AssertionError('No new disclosure.')):
                second = work_check._analyze(root, path, root, REVISION)
            self.assertEqual(second['targeted_samples'], sample_envelope('replayed', envelope['record']))

    def test_sfr_failure_is_fixed_and_new_summary_is_null_on_failure(self) -> None:
        from test_save_diagnostics import failed_report
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            path = root / 'invented.L5X'
            path.write_bytes(SOURCE)
            with patch.object(work_check, 'analyze_sfr_context', side_effect=SfrContextError('PRIVATE_FAILURE')):
                result = work_check._analyze(root, path, root, REVISION)
            self.assertEqual((result['failure_code'], result['private_run_saved']), ('sfr_context_error', False))
            self.assertIsNone(result['sfr_summary'])
            payload = failed_report(31, 'sfr_context_error')
            payload['analysis'] = {k: v for k, v in result.items() if k not in {'diagnostic_sample', 'targeted_samples'}}
            self.assertNotIn('PRIVATE_FAILURE', work_check.render_work_check_report(payload))
            self.assertIn('PRIVATE_FAILURE', (root / 'analysis.log').read_text())

    def test_current_limits_are_separate_and_failed_size_save_has_no_manifest(self) -> None:
        parts = captured()
        old = old_captured(SOURCE)
        previous = review.build_review_data(*old[:4], **old_options(old))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual(review.MAX_REVIEW_V13_BYTES, 192 * 1024 * 1024)
        self.assertEqual(review_html._limits(13), (192 * 1024 * 1024, 224 * 1024 * 1024))
        self.assertEqual(review_html._limits(12), (184 * 1024 * 1024, 216 * 1024 * 1024))
        with patch.object(review, 'MAX_REVIEW_V13_BYTES', 1):
            review.render_review_json(previous)
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(StorageError) as error:
                    save_run(Path(folder), *parts[:2], **arguments(parts))
                self.assertEqual(error.exception.code, 'review_size_limit')
                self.assertFalse(list(Path(folder).rglob('manifest.json')))
        for key in ('MAX_REVIEW_V13_PAYLOAD_BYTES', 'MAX_REVIEW_V13_HTML_BYTES'):
            with patch.object(review_html, key, 1):
                review_html.render_review_html(previous)
                with self.assertRaises(review_html.ReviewHtmlSizeLimitError):
                    review_html.render_review_html(current)
        self.assertEqual(work_check._report_limit(30), 64 * 1024)

    def test_publication_contains_closed_counts_and_no_new_source_examples(self) -> None:
        payload = report()
        encoded = json.dumps(payload['analysis']['sfr_summary'])
        self.assertNotIn('INVENTED_', encoded)
        self.assertNotIn('source_id', encoded)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'feedback.json'
            publish_summary(path, work_check.render_work_check_report(payload), input_path=Path(folder) / 'invented.L5X')
            self.assertEqual(json.loads(path.read_bytes()), payload)

    def test_html_stateful_labels_flags_and_sfr_links_remain_text_only(self) -> None:
        parts = captured()
        data = review.build_review_data(*parts[:4], **options(parts))
        rendered = review_html.render_review_html(data)
        for text in ('ONS: incoming AND NOT storage before this occurrence', 'Storage after this occurrence',
                     'Known false incoming', 'Contains stored-state condition', 'SFR content candidates',
                     'Sequence reset context', 'Step Name and numeric ID are not substituted'):
            self.assertIn(text, rendered)
        self.assertNotIn('.innerHTML', rendered)
        self.assertIn("connect-src 'none'", rendered)
        for mutate in (lambda d: d.update(sfr_context=None),
                       lambda d: d['sfr_context'].update(schema_version=True),
                       lambda d: d['conditions'].update(schema_version=2),
                       lambda d: d.update(schema_version=12, report_version='engineering-review-12')):
            bad = deepcopy(data)
            mutate(bad)
            with self.assertRaises(review_html.ReviewHtmlError):
                review_html.render_review_html(bad)


if __name__ == '__main__':
    unittest.main()
