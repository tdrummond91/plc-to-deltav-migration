"""Rung evidence integration uses invented sources and local temporary files only."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import work_check
from plc_workbench.access import analyze_access
from plc_workbench.rung_analysis import RungAnalysisError, analyze_rungs, render_rung_analysis_json
from plc_workbench.rung_analysis_summary import build_rung_summary, validate_rung_summary
from plc_workbench.review import ReviewError, build_review_data, validate_review_data
from plc_workbench.review_html import ReviewHtmlError, render_review_html
from plc_workbench.storage import StorageError, _write_artifact, save_run
from test_access_workflow import ROOT, ladder
from test_calculation_workflow import arguments as old_arguments, options as old_options
from test_cpt_access_workflow import captured as old_captured, report as old_report
from test_review_workflow import invoke
from test_unmatched_sample_report import REVISION

SOURCE = ladder('XIC(A)[OTE(A),CPT(A,A+A)]PRIVATE_BLOCK(A);')


def captured(data: bytes = SOURCE):
    parts = old_captured(data)
    return (*parts, analyze_rungs(*parts[:3], parts[4], parts[8]))


def options(parts: tuple) -> dict:
    return old_options(parts) | {'rung_analysis': parts[9]}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'rung_analysis': parts[9]}


def report(data: bytes = SOURCE) -> dict:
    payload = old_report(data)
    parts = captured(data)
    summary = build_rung_summary(*parts[:3], parts[4], parts[8], parts[9], revision=REVISION)
    payload.update(schema_version=22, workflow_version='work-check-22')
    payload['analysis']['rung_analysis_summary'] = summary
    if summary['status'] == 'partial':
        payload['analysis']['status'] = payload['status'] = 'partial'
    return payload


class RungAnalysisWorkflowTests(unittest.TestCase):
    def test_review7_and_manifest10_save_fourteen_hashed_artifacts(self) -> None:
        parts = captured()
        payload = build_review_data(*parts[:4], **options(parts))
        self.assertEqual((payload['schema_version'], payload['report_version']), (7, 'engineering-review-7'))
        self.assertEqual(payload['rung_analysis'], parts[-1].to_dict())
        self.assertEqual(payload['semantic_analysis'], 'structural_and_candidate_evidence')
        validate_review_data(*parts[:4], payload, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            previous = save_run(Path(folder), *parts[:2], **old_arguments(parts))
            previous_bytes = {path.name: path.read_bytes() for path in previous.iterdir()}
            saved = save_run(Path(folder), *parts[:2], **arguments(parts))
            manifest = json.loads((saved / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (10, 14))
            self.assertEqual((manifest['review_schema_version'], manifest['review_version']), (7, 'engineering-review-7'))
            self.assertEqual((manifest['rung_analysis_schema_version'], manifest['rung_analysis_analyzer_version']),
                             (1, 'rung-analysis-1'))
            self.assertEqual((saved / 'rung-analysis.json').read_bytes(), render_rung_analysis_json(parts[-1]).encode())
            for name, details in manifest['artifacts'].items():
                data = (saved / name).read_bytes()
                self.assertEqual(details, {'size_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
                if name not in {'rung-analysis.json', 'review.html'}:
                    self.assertEqual(data, previous_bytes[name])
            self.assertEqual(previous_bytes, {path.name: path.read_bytes() for path in previous.iterdir()})

    def test_missing_forged_foreign_and_older_companions_fail_before_allocation(self) -> None:
        parts = captured()
        forged = deepcopy(parts[-1])
        forged.coverage['source_rungs'] += 1
        foreign = captured(SOURCE.replace(b'A+A', b'A-A'))[-1]
        wrongs = [dict(options(parts), **{key: None}) for key in old_options(parts)]
        wrongs.extend((dict(options(parts), rung_analysis=forged),
                       dict(options(parts), rung_analysis=foreign),
                       dict(options(parts), access=analyze_access(*parts[1:3], schema_version=3))))
        for kwargs in wrongs:
            with self.subTest(keys=kwargs.keys()), self.assertRaises(ReviewError):
                build_review_data(*parts[:4], **kwargs)
            with tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder) / 'absent'
                with self.assertRaises(StorageError):
                    save_run(workspace, *parts[:2], **(old_arguments(parts) | kwargs))
                self.assertFalse(workspace.exists())
        payload = build_review_data(*parts[:4], **options(parts))
        payload['rung_analysis']['coverage']['source_rungs'] += 1
        with self.assertRaises(ReviewError):
            validate_review_data(*parts[:4], payload, **options(parts))

    def test_html_version_and_companion_presence_are_strict(self) -> None:
        parts = captured()
        current = build_review_data(*parts[:4], **options(parts))
        self.assertIn('review-data', render_review_html(current))
        for mutate in (lambda p: p.pop('rung_analysis'), lambda p: p.update(rung_analysis=None),
                       lambda p: p.update(schema_version=6, report_version='engineering-review-6'),
                       lambda p: p.update(schema_version=7, report_version='engineering-review-6')):
            bad = deepcopy(current)
            mutate(bad)
            with self.assertRaises(ReviewHtmlError):
                render_review_html(bad)
        kwargs = old_options(parts)
        kwargs['access'] = analyze_access(*parts[1:3], schema_version=3)
        for version in range(1, 7):
            legacy = build_review_data(*parts[:4], **{key: kwargs[key] for key in tuple(kwargs)[:version - 1]})
            self.assertNotIn('rung_analysis', legacy)
            render_review_html(legacy)
            legacy['rung_analysis'] = {}
            with self.assertRaises(ReviewHtmlError):
                render_review_html(legacy)

    def test_render_failure_allocates_nothing_and_write_failure_never_finalizes(self) -> None:
        parts = captured()
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder) / 'absent'
            with patch('plc_workbench.rung_analysis.render_rung_analysis_json',
                       side_effect=RungAnalysisError('PRIVATE_FAILURE')):
                with self.assertRaises(StorageError) as raised:
                    save_run(workspace, *parts[:2], **arguments(parts))
            self.assertNotIn('PRIVATE_FAILURE', str(raised.exception))
            self.assertFalse(workspace.exists())

            def fail(destination, run_dir, name, data):
                if name == 'rung-analysis.json':
                    raise OSError('PRIVATE_DISK_DETAIL')
                return _write_artifact(destination, run_dir, name, data)

            with patch('plc_workbench.storage._write_artifact', side_effect=fail), self.assertRaises(StorageError):
                save_run(workspace, *parts[:2], **arguments(parts))
            saved, = workspace.iterdir()
            self.assertFalse((saved / 'manifest.json').exists())

    def test_review7_keeps_bounded_json_and_html_before_workspace_allocation(self) -> None:
        parts = captured()
        with tempfile.TemporaryDirectory() as folder:
            for index, name in enumerate(('review.MAX_REVIEW_V3_BYTES',
                                          'review_html.MAX_REVIEW_V3_PAYLOAD_BYTES',
                                          'review_html.MAX_REVIEW_V3_HTML_BYTES')):
                workspace = Path(folder) / str(index)
                with self.subTest(limit=name), patch(f'plc_workbench.{name}', 1), self.assertRaises(StorageError):
                    save_run(workspace, *parts[:2], **arguments(parts))
                self.assertFalse(workspace.exists())

    def test_cli_and_runner_use_same_snapshot_and_save_current_rung_evidence(self) -> None:
        parts = captured()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(SOURCE)
            code, output, error = invoke(['review', str(source), '--workspace', str(root / 'runs')])
            self.assertEqual((code, error), (3, ''))
            saved, = (root / 'runs').iterdir()
            self.assertIn(str(saved / 'review.html'), output)
            self.assertEqual(json.loads((saved / 'rung-analysis.json').read_bytes()), parts[-1].to_dict())
            with patch.object(work_check, 'save_run', return_value=root / 'saved') as save:
                outcome = work_check._analyze(root, source, root, REVISION)
            self.assertIsNone(outcome['failure_code'])
            self.assertEqual(save.call_args.kwargs['rung_analysis'].to_dict(), parts[-1].to_dict())
            outcome.pop('diagnostic_sample')
            self.assertIsNotNone(outcome.pop('relationship_summary'))
            self.assertIsNotNone(outcome.pop('condition_summary'))
            self.assertEqual(outcome, report()['analysis'])
            with patch('plc_workbench.rung_analysis.analyze_rungs', side_effect=RungAnalysisError('PRIVATE_FAILURE')):
                code, output, error = invoke(['review', str(source), '--workspace', str(root / 'failed')])
            self.assertEqual((code, output), (1, ''))
            self.assertNotIn('PRIVATE_FAILURE', error)
            self.assertFalse((root / 'failed').exists())

    def test_runner_failure_is_local_and_all_summary_fields_remain_null(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(SOURCE)
            with patch.object(work_check, 'analyze_rungs', side_effect=RungAnalysisError('PRIVATE_FAILURE')):
                outcome = work_check._analyze(root, source, root, REVISION)
            self.assertEqual((outcome['failure_code'], outcome['private_run_saved']), ('rung_analysis_error', False))
            self.assertTrue(all(value is None for key, value in outcome.items() if key.endswith('_summary')))
            self.assertNotIn('PRIVATE_FAILURE', json.dumps(outcome))
            self.assertIn('PRIVATE_FAILURE', (root / 'analysis.log').read_text())


class RungAnalysisWorkReportTests(unittest.TestCase):
    def test_current_summary_is_aggregate_only_and_historical_reports_are_unchanged(self) -> None:
        payload = report()
        work_check.validate_work_check_report(payload)
        self.assertEqual((payload['schema_version'], payload['workflow_version']), (22, 'work-check-22'))
        rendered = work_check.render_work_check_report(payload)
        self.assertEqual(json.loads(rendered), payload)
        for private in ('PRIVATE_', 'raw_text', 'instruction_id', 'target_id', 'snapshot', 'A+A'):
            self.assertNotIn(private, rendered)
        for path in (ROOT / 'public/inspection').glob('work-check-*.json'):
            before = path.read_bytes()
            historical = json.loads(before)
            self.assertLessEqual(historical['schema_version'], work_check._CONSTANTS['schema_version'])
            self.assertEqual(json.loads(work_check.render_work_check_report(historical)), historical)
            self.assertEqual(path.read_bytes(), before)

    def test_history_scan_accepts_returned_current_report_on_next_run(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inspection = root / 'public' / 'inspection'
            inspection.mkdir(parents=True)
            before = {}
            for name, payload in (('historical', old_report(SOURCE)), ('returned', report())):
                path = inspection / f'work-check-{name}.json'
                before[path] = work_check.render_work_check_report(payload).encode('utf-8')
                path.write_bytes(before[path])
            with patch(f'{__name__}.ROOT', root):
                self.test_current_summary_is_aggregate_only_and_historical_reports_are_unchanged()
            self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_old_envelope_cannot_gain_rung_summary_and_current_cannot_lose_it(self) -> None:
        previous, current = old_report(SOURCE), report()
        for bad in (dict(current, schema_version=21, workflow_version='work-check-21'),
                    dict(previous, schema_version=22, workflow_version='work-check-22')):
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)
        for mutate in (lambda p: p['analysis'].update(rung_analysis_summary=None),
                       lambda p: p['analysis']['rung_analysis_summary']['tool_revision'].update(commit='b' * 40),
                       lambda p: p['analysis']['rung_analysis_summary'].update(schema_version=True),
                       lambda p: p['analysis']['rung_analysis_summary'].update(private='PRIVATE')):
            bad = deepcopy(current)
            mutate(bad)
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)

    def test_source_and_access_counts_reject_valid_but_foreign_rung_summaries(self) -> None:
        for target, donor in (('CPT(A,A);', 'CPT(A,A+A);'),
                              ('MOV(A,A);', 'MOV(MISSING,A);'),
                              ('MOV(A,A);', 'PRIVATE_BLOCK(A,A);'),
                              ('XIC(A)OTE(A);', '[XIC(A),]OTE(A);'),
                              ('[XIC(A),]OTE(A);', '[XIC(A),,]OTE(A);'),
                              ('[XIC(A),]OTE(A);', 'XIC(A)[,]OTE(A);'),
                              ('PID(A,,A,A,A,A,A);', 'PID(A,A,A,A,A,A,A);'),
                              ('MOV(A,A);', 'MOV(A,A)MOV(A,A);')):
            bad = report(ladder(target))
            bad['analysis']['rung_analysis_summary'] = report(ladder(donor))['analysis']['rung_analysis_summary']
            validate_rung_summary(bad['analysis']['rung_analysis_summary'])
            with self.subTest(target=target, donor=donor), self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)

    def test_versioned_limits_apply_to_validation_and_rendering(self) -> None:
        current, legacy = report(), old_report(SOURCE)
        current_bytes = len(work_check.render_work_check_report(current).encode())
        with patch.object(work_check, 'MAX_REPORT_BYTES', 1), \
                patch.object(work_check, 'MAX_REPORT_V22_BYTES', current_bytes):
            work_check.validate_work_check_report(current)
            work_check.render_work_check_report(current)
            for action in (work_check.validate_work_check_report, work_check.render_work_check_report):
                with self.assertRaises(work_check.WorkCheckError):
                    action(legacy)
        with patch.object(work_check, 'MAX_REPORT_V22_BYTES', current_bytes - 1):
            for action in (work_check.validate_work_check_report, work_check.render_work_check_report):
                with self.assertRaises(work_check.WorkCheckError):
                    action(current)

    def test_publication_allows_larger_work22_only_after_canonical_validation(self) -> None:
        from plc_workbench.summary_output import SummaryOutputError, publish_summary
        current = work_check.render_work_check_report(report())
        legacy = work_check.render_work_check_report(old_report(SOURCE))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            # Whitespace cannot widen a legacy contract, while the new fixed
            # count map can cross32KiB and still publish canonical bytes.
            padded_current = current + ' ' * (33 * 1024 - len(current))
            publish_summary(root / 'current.json', padded_current, input_path=root / 'source.L5X')
            self.assertEqual((root / 'current.json').read_bytes(), current.encode())
            for index, bad in enumerate((legacy + ' ' * (33 * 1024 - len(legacy)),
                                         current + ' ' * (49 * 1024),
                                         current.replace('"rung-analysis-1"', '"PRIVATE"'))):
                destination = root / f'bad-{index}.json'
                with self.assertRaises(SummaryOutputError):
                    publish_summary(destination, bad, input_path=root / 'source.L5X')
                self.assertFalse(destination.exists())

    def test_failure_and_not_run_null_summary_and_versioned_failure_code(self) -> None:
        original = report()
        for state in ('failed', 'not_run'):
            current = deepcopy(original)
            current['analysis'] = {'status': state, 'failure_code': 'rung_analysis_error' if state == 'failed' else None,
                'private_run_saved': False, **{key: None for key in original['analysis'] if key.endswith('_summary')}}
            current.update(status='failed', diagnostic_sample=None)
            if state == 'not_run':
                current['tests']['application'] = work_check.unavailable_result('not_run')
            work_check.validate_work_check_report(current)
            current['analysis']['rung_analysis_summary'] = original['analysis']['rung_analysis_summary']
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(current)
        old = deepcopy(original)
        old.update(schema_version=21, workflow_version='work-check-21', status='failed', diagnostic_sample=None)
        old['analysis'] = {'status': 'failed', 'failure_code': 'rung_analysis_error', 'private_run_saved': False,
            **{key: None for key in original['analysis'] if key.endswith('_summary') and key != 'rung_analysis_summary'}}
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(old)


if __name__ == '__main__':
    unittest.main()
