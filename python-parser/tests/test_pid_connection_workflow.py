"""PID connection publication and review boundaries use invented source only."""
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
from plc_workbench.pid_connections import PidConnectionError, analyze_pid_connections
from plc_workbench.pid_connection_summary import (
    PidConnectionSummaryError, build_pid_connection_summary, validate_pid_connection_summary,
)
from plc_workbench.storage import StorageError, save_run
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from test_aoi_body_workflow import (
    captured as old_captured, options as old_options, arguments as old_arguments,
    report as old_report,
)
from test_binding_context_workflow import ROOT, source
from test_unmatched_sample_report import REVISION

SOURCE = (ROOT / 'public/fixtures/synthetic/pid_connections_demo.L5X').read_bytes()


def connection_inputs(parts: tuple) -> tuple:
    return (*parts[:3], parts[4], parts[8], parts[9], parts[10], parts[11], parts[5], parts[6], parts[7])


@lru_cache(maxsize=6)
def captured(data: bytes = SOURCE) -> tuple:
    parts = old_captured(data)
    return (*parts, analyze_pid_connections(*connection_inputs(parts)))


def options(parts: tuple) -> dict:
    return old_options(parts) | {'pid_connections': parts[17]}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'pid_connections': parts[17]}


@lru_cache(maxsize=6)
def _report(data: bytes) -> dict:
    payload = old_report(data)
    parts = captured(data)
    payload.update(schema_version=32, workflow_version='work-check-32')
    payload['analysis']['pid_connection_summary'] = build_pid_connection_summary(
        *connection_inputs(parts), parts[17], revision=REVISION)
    if parts[17].status == 'partial':
        payload['analysis']['status'] = payload['status'] = 'partial'
    return payload


def report(data: bytes = SOURCE) -> dict:
    return deepcopy(_report(data))


def maximum_width_report() -> dict:
    """Conservative byte probe, not a claim that simultaneous maxima are valid."""
    from plc_workbench.ladder.syntax import PUBLIC_OPCODES
    from plc_workbench.summary import DIAGNOSTIC_CODES, MAX_COUNT
    from plc_workbench.targeted_samples import MAX_BYTES

    def grow(value, maximum=MAX_COUNT):
        if type(value) is int:
            return maximum
        if type(value) is dict:
            return {key: grow(child, maximum) for key, child in value.items()}
        if type(value) is list:
            return [grow(child, maximum) for child in value]
        return value

    maximum = grow(report())
    maximum['schema_version'] = 32
    for key in ('aoi_body_summary', 'sfr_summary', 'custom_instruction_summary',
                'indexed_access_summary', 'binding_context_summary', 'pid_connection_summary'):
        maximum['analysis'][key] = grow(maximum['analysis'][key], 250_000)
    source_counts = maximum['analysis']['reference_summary']['source_summary']
    source_counts['instructions']['counts'].update(dict.fromkeys(PUBLIC_OPCODES, 250_000))
    source_counts['diagnostics']['by_code'].update(dict.fromkeys(DIAGNOSTIC_CODES, MAX_COUNT))
    maximum['targeted_samples']['record'] = 'x' * MAX_BYTES
    return maximum


class PidConnectionWorkflowTests(unittest.TestCase):
    def test_review15_manifest18_preserve_previous_evidence_and_sixteen_artifacts(self) -> None:
        parts = captured()
        old = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual((current['schema_version'], current['report_version']), (15, 'engineering-review-15'))
        for key in old.keys() - {'schema_version', 'report_version', 'status'}:
            self.assertEqual(current[key], old[key], key)
        review.validate_review_data(*parts[:4], current, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = save_run(root, *parts[:2], **old_arguments(parts))
            old_bytes = {p.name: p.read_bytes() for p in before.iterdir()}
            after = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((after / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (18, 16))
            self.assertEqual(manifest['review_schema_version'], 15)
            self.assertEqual(manifest['pid_connections_analyzer_version'], 'pid-connections-1')
            self.assertNotIn('pid-connections.json', manifest['artifacts'])
            for name, content in old_bytes.items():
                self.assertEqual((before / name).read_bytes(), content)
                if name not in {'manifest.json', 'review.html'}:
                    self.assertEqual((after / name).read_bytes(), content, name)

    def test_review_and_storage_reject_incomplete_or_forged_companion_before_allocation(self) -> None:
        parts = captured()
        for key in ('aoi_body_context', 'pid_members', 'relationships', 'conditions', 'access'):
            with self.subTest(key=key), self.assertRaises(review.ReviewError):
                review.build_review_data(*parts[:4], **(options(parts) | {key: None}))
        for field in ('occurrences', 'slots', 'addresses'):
            forged = replace(parts[17], **{field: []})
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'unallocated'
                with self.assertRaises(StorageError):
                    save_run(destination, *parts[:2], **(arguments(parts) | {'pid_connections': forged}))
                self.assertFalse(destination.exists())
        current = review.build_review_data(*parts[:4], **options(parts))
        current['pid_connections']['coverage']['master_self_references'] += 1
        with self.assertRaises(review.ReviewError):
            review.validate_review_data(*parts[:4], current, **options(parts))

    def test_work32_preserves_all_previous_summary_and_sample_bytes(self) -> None:
        old, current = old_report(SOURCE), report()
        work_check.validate_work_check_report(current)
        self.assertEqual(current['targeted_samples'], old['targeted_samples'])
        for key in old['analysis'].keys() - {'status'}:
            self.assertEqual(current['analysis'][key], old['analysis'][key], key)
        self.assertEqual(json.loads(work_check.render_work_check_report(current)), current)
        for path in (ROOT / 'public/inspection').glob('work-check-*.json'):
            before = path.read_bytes()
            historical = json.loads(before)
            self.assertLessEqual(historical['schema_version'], work_check._CONSTANTS['schema_version'])
            self.assertEqual(json.loads(work_check.render_work_check_report(historical)), historical)
            self.assertEqual(path.read_bytes(), before)
        self.assertEqual(work_check.render_work_check_report(old), json.dumps(
            old, separators=(',', ':'), sort_keys=True, ensure_ascii=True) + '\n')

    def test_public_presence_revision_versions_and_source_status_are_closed(self) -> None:
        for mutate in (
            lambda p: p['analysis'].pop('pid_connection_summary'),
            lambda p: p['analysis'].update(pid_connection_summary=None),
            lambda p: p['analysis']['pid_connection_summary']['tool_revision'].update(commit='f' * 40),
            lambda p: p['analysis']['pid_connection_summary'].update(schema_version=True),
            lambda p: p['analysis']['pid_connection_summary'].update(private='PRIVATE'),
            lambda p: p['analysis']['pid_connection_summary']['coverage'].update(source_pid_partial=0),
            lambda p: p.update(schema_version=31, workflow_version='work-check-31'),
        ):
            candidate = report()
            mutate(candidate)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)

    def test_cross_summary_counts_reject_valid_but_foreign_populations(self) -> None:
        candidate = report()
        candidate['analysis']['pid_connection_summary'] = report(source('NOP();'))['analysis']['pid_connection_summary']
        validate_pid_connection_summary(candidate['analysis']['pid_connection_summary'])
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)
        # Keep each standalone summary valid while moving accepted occurrences
        # beyond the source's role capacity, or beyond its condition population.
        for role in ('read', 'write', 'read_write', 'unknown', 'expression_read'):
            candidate = report()
            c = candidate['analysis']['pid_connection_summary']['coverage']
            rel = candidate['analysis']['relationship_summary']['coverage']
            capacity = rel['indexed_expression_uses'] if role == 'expression_read' else rel['indexed_operands_by_role'][role]
            c['address_links_by_role'][role] = capacity + 1
            validate_pid_connection_summary(candidate['analysis']['pid_connection_summary'])
            with self.subTest(role=role), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        for role, capacity in (('namespace_gap_operand', sum(rel['indexed_operands_by_role'].values())),
                               ('namespace_gap_expression', rel['indexed_expression_uses'])):
            candidate = report()
            candidate['analysis']['pid_connection_summary']['coverage']['address_links_by_role'][role] = capacity + 1
            validate_pid_connection_summary(candidate['analysis']['pid_connection_summary'])
            with self.subTest(role=role), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)

    def test_runner_captures_connections_once_and_replays_frozen_sample_request(self) -> None:
        from plc_workbench.targeted_sample_history import sample_envelope
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            path = root / 'invented.L5X'
            path.write_bytes(SOURCE)
            with patch.object(work_check, 'capture_snapshot', wraps=work_check.capture_snapshot) as capture, \
                    patch.object(work_check, 'analyze_pid_connections', wraps=analyze_pid_connections) as analyze, \
                    patch.object(work_check, 'save_run', return_value=root / 'saved') as save:
                first = work_check._analyze(root, path, root, REVISION)
            self.assertIsNone(first['failure_code'])
            capture.assert_called_once_with(path)
            analyze.assert_called_once()
            self.assertEqual(save.call_args.kwargs['pid_connections'], captured()[17])
            envelope = first.pop('targeted_samples')
            first.pop('diagnostic_sample')
            payload = report()
            payload.update(schema_version=36, workflow_version='work-check-36', analysis=first, targeted_samples=envelope)
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
                ('analyze_pid_connections', PidConnectionError('PRIVATE_SENTINEL'), 'pid_connection_error', False),
                ('build_pid_connection_summary', PidConnectionSummaryError('PRIVATE_SENTINEL'), 'summary_error', True),
            ):
                with patch.object(work_check, target, side_effect=error), patch.object(work_check, 'save_run', return_value=root):
                    result = work_check._analyze(root, path, root, REVISION)
                self.assertEqual((result['failure_code'], result['private_run_saved']), (code, saved))
                self.assertTrue(all(value is None for key, value in result.items() if key.endswith('_summary')))
                payload = failed_report(36, code)
                payload['analysis'] = {k: v for k, v in result.items() if k not in {'diagnostic_sample', 'targeted_samples'}}
                self.assertNotIn('PRIVATE_SENTINEL', work_check.render_work_check_report(payload))
                self.assertIn('PRIVATE_SENTINEL', (root / 'analysis.log').read_text())
                payload.update(schema_version=31, workflow_version='work-check-31')
                with self.assertRaises(ValueError):
                    work_check.validate_work_check_report(payload)

    def test_review15_limits_do_not_change_review14_or_allocate_failed_run(self) -> None:
        parts = captured()
        old = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual(review.MAX_REVIEW_V15_BYTES, 208 * 1024 * 1024)
        self.assertEqual(review_html._limits(15), (208 * 1024 * 1024, 240 * 1024 * 1024))
        self.assertEqual(review_html._limits(14), (200 * 1024 * 1024, 232 * 1024 * 1024))
        with patch.object(review, 'MAX_REVIEW_V15_BYTES', 1), tempfile.TemporaryDirectory() as folder:
            review.render_review_json(old)
            with self.assertRaises(StorageError) as error:
                save_run(Path(folder), *parts[:2], **arguments(parts))
            self.assertEqual(error.exception.code, 'review_size_limit')
            self.assertFalse(list(Path(folder).rglob('manifest.json')))
        for key in ('MAX_REVIEW_V15_PAYLOAD_BYTES', 'MAX_REVIEW_V15_HTML_BYTES'):
            with patch.object(review_html, key, 1):
                review_html.render_review_html(old)
                with self.assertRaises(review_html.ReviewHtmlSizeLimitError):
                    review_html.render_review_html(current)

    def test_work32_cap_covers_full_schema_width_and_full_frozen_request(self) -> None:
        maximum = maximum_width_report()
        size = len(work_check._serialize_report(maximum).encode())
        self.assertGreater(size, work_check.MAX_REPORT_V28_BYTES)
        self.assertLess(size, work_check.MAX_REPORT_V32_BYTES)
        self.assertEqual(work_check._report_limit(31), 64 * 1024)
        self.assertEqual(work_check._report_limit(32), 80 * 1024)
        work_check._report_size(maximum)
        with patch.object(work_check, 'MAX_REPORT_V32_BYTES', size - 1):
            with self.assertRaises(work_check.WorkCheckError):
                work_check._report_size(maximum)

    def test_publication_accepts_only_counts_and_uses_compact_work32_bytes(self) -> None:
        payload = report()
        encoded = work_check.render_work_check_report(payload)
        self.assertEqual(encoded, json.dumps(payload, separators=(',', ':'), sort_keys=True, ensure_ascii=True) + '\n')
        for token in ('DemoLoop', '"instruction_id"', '"owner_id"', '"address_id"', '"incoming_condition_ids"'):
            self.assertNotIn(token, json.dumps(payload['analysis']['pid_connection_summary']))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'feedback.json'
            publish_summary(path, encoded, input_path=Path(folder) / 'invented.L5X')
            self.assertEqual(path.read_text(), encoded)

    def test_publication_raw_input_cap_is_80k_only_for_work32(self) -> None:
        current = work_check.render_work_check_report(report())
        previous = work_check.render_work_check_report(old_report(SOURCE))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'feedback.json'
            padded = current + ' ' * (80 * 1024 - len(current.encode()))
            publish_summary(path, padded, input_path=root / 'invented.L5X')
            self.assertEqual(path.read_text(), current)
            for payload in (padded + ' ', previous + ' ' * (64 * 1024 + 1 - len(previous.encode()))):
                rejected = root / 'rejected.json'
                with self.assertRaises(SummaryOutputError):
                    publish_summary(rejected, payload, input_path=root / 'invented.L5X')
                self.assertFalse(rejected.exists())

    def test_html_has_one_pid_navigation_with_paginated_source_connection_details(self) -> None:
        parts = captured()
        current = review.build_review_data(*parts[:4], **options(parts))
        rendered = review_html.render_review_html(current)
        for text in ('Slot connections and observed usage', 'Member connections by function',
                     'Explicit master operand candidates', 'Incoming condition evidence',
                     'Observed source connections', 'Namespace gaps in operand uses', 'PAGE_SIZE = 50'):
            self.assertIn(text, rendered)
        self.assertEqual(rendered.count("labels.pid='PID evidence'"), 1)
        self.assertNotIn('.innerHTML', rendered)
        self.assertIn("connect-src 'none'", rendered)
        for mutate in (lambda d: d.update(pid_connections=None),
                       lambda d: d['pid_connections'].update(schema_version=True),
                       lambda d: d['sfr_context'].update(schema_version=1),
                       lambda d: d.update(schema_version=14, report_version='engineering-review-14')):
            bad = deepcopy(current)
            mutate(bad)
            with self.assertRaises(review_html.ReviewHtmlError):
                review_html.render_review_html(bad)


if __name__ == '__main__':
    unittest.main()
