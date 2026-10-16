"""Exact-address evidence stays private; only closed counts cross publication."""
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
from plc_workbench.relationships import RelationshipError, analyze_relationships, render_relationships_json
from plc_workbench.relationship_summary import build_relationship_summary, validate_relationship_summary
from plc_workbench.review import ReviewError, build_review_data, validate_review_data
from plc_workbench.review_html import ReviewHtmlError, render_review_html
from plc_workbench.storage import StorageError, _write_artifact, save_run
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from test_access_workflow import ROOT, ladder
from test_cpt_access_workflow import report as access_report
from test_rung_analysis_workflow import (arguments as old_arguments, captured as old_captured,
                                        options as old_options, report as old_report)
from test_review_workflow import invoke
from test_unmatched_sample_report import REVISION

SOURCE = ladder('ADD(A,937291,A)CPT(A,A+A);')


def captured(data: bytes = SOURCE) -> tuple:
    parts = old_captured(data)
    return (*parts, analyze_relationships(*parts[:3], parts[4], parts[8], parts[9]))


def options(parts: tuple) -> dict:
    return old_options(parts) | {'relationships': parts[10]}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'relationships': parts[10]}


def report(data: bytes = SOURCE) -> dict:
    payload = old_report(data)
    parts = captured(data)
    summary = build_relationship_summary(*parts[:3], parts[4], parts[8], parts[9], parts[10], revision=REVISION)
    payload.update(schema_version=23, workflow_version='work-check-23')
    payload['analysis']['relationship_summary'] = summary
    if summary['status'] == 'partial':
        payload['analysis']['status'] = payload['status'] = 'partial'
    return payload


class RelationshipWorkflowTests(unittest.TestCase):
    def test_review8_and_manifest11_hash_fifteen_artifacts_and_preserve_older_evidence(self) -> None:
        parts = captured()
        data = build_review_data(*parts[:4], **options(parts))
        self.assertEqual((data['schema_version'], data['report_version']), (8, 'engineering-review-8'))
        self.assertEqual(data['relationships'], parts[-1].to_dict())
        validate_review_data(*parts[:4], data, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            previous = save_run(Path(folder), *parts[:2], **old_arguments(parts))
            previous_bytes = {path.name: path.read_bytes() for path in previous.iterdir()}
            saved = save_run(Path(folder), *parts[:2], **arguments(parts))
            manifest = json.loads((saved / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (11, 15))
            self.assertEqual((manifest['review_schema_version'], manifest['review_version']), (8, 'engineering-review-8'))
            self.assertEqual((manifest['relationship_schema_version'], manifest['relationship_analyzer_version']),
                             (1, 'relationship-analysis-1'))
            self.assertEqual((saved / 'relationships.json').read_bytes(), render_relationships_json(parts[-1]).encode())
            for name, details in manifest['artifacts'].items():
                value = (saved / name).read_bytes()
                self.assertEqual(details, {'size_bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()})
                if name not in {'relationships.json', 'review.html'}:
                    self.assertEqual(value, previous_bytes[name])
            self.assertEqual(previous_bytes, {path.name: path.read_bytes() for path in previous.iterdir()})

    def test_forged_foreign_missing_and_old_companions_fail_before_allocation(self) -> None:
        parts = captured()
        forged = deepcopy(parts[-1])
        forged.coverage['source_rungs'] += 1
        foreign = captured(SOURCE.replace(b'A+A', b'A-A'))[-1]
        boolean_version = deepcopy(parts[-1])
        object.__setattr__(boolean_version, 'schema_version', True)
        cases = [dict(options(parts), **{key: None}) for key in old_options(parts)]
        cases.extend(dict(options(parts), relationships=value) for value in (forged, foreign, boolean_version))
        cases.append(dict(options(parts), access=analyze_access(*parts[1:3], schema_version=3)))
        for kwargs in cases:
            with self.subTest(keys=kwargs.keys()), self.assertRaises(ReviewError):
                build_review_data(*parts[:4], **kwargs)
            with tempfile.TemporaryDirectory() as folder:
                workspace = Path(folder) / 'absent'
                with self.assertRaises(StorageError):
                    save_run(workspace, *parts[:2], **(old_arguments(parts) | kwargs))
                self.assertFalse(workspace.exists())
        payload = build_review_data(*parts[:4], **options(parts))
        payload['relationships']['coverage']['source_rungs'] += 1
        with self.assertRaises(ReviewError):
            validate_review_data(*parts[:4], payload, **options(parts))

    def test_foreign_objects_are_rejected_without_calling_serialization_hooks(self) -> None:
        parts = captured()

        class HookDict(dict):
            def items(self):
                raise AssertionError('A caller hook must never run.')

        forged = deepcopy(parts[-1])
        object.__setattr__(forged, 'coverage', HookDict(forged.coverage))
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder) / 'absent'
            with patch.object(type(forged), 'to_dict', side_effect=AssertionError('Do not serialize foreign evidence.')):
                with self.assertRaises(StorageError):
                    save_run(workspace, *parts[:2], **dict(arguments(parts), relationships=forged))
            self.assertFalse(workspace.exists())

    def test_versions_and_optional_html_companion_are_strict(self) -> None:
        parts = captured()
        current = build_review_data(*parts[:4], **options(parts))
        self.assertIn('review-data', render_review_html(current))
        for mutate in (lambda p: p.pop('relationships'), lambda p: p.update(relationships=None),
                       lambda p: p.update(schema_version=7, report_version='engineering-review-7'),
                       lambda p: p.update(schema_version=8, report_version='engineering-review-7')):
            bad = deepcopy(current)
            mutate(bad)
            with self.assertRaises(ReviewHtmlError):
                render_review_html(bad)
        kwargs = old_options(parts)
        for version in range(1, 8):
            selected = {key: kwargs[key] for key in tuple(kwargs)[:version - 1]}
            if version < 7 and 'access' in selected:
                selected['access'] = analyze_access(*parts[1:3], schema_version=3)
            legacy = build_review_data(*parts[:4], **selected)
            self.assertEqual(legacy['schema_version'], version)
            render_review_html(legacy)
            legacy['relationships'] = {}
            with self.assertRaises(ReviewHtmlError):
                render_review_html(legacy)

    def test_render_and_size_failure_allocate_nothing_write_failure_never_finalizes(self) -> None:
        parts = captured()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            workspace = root / 'render'
            with patch('plc_workbench.relationships.render_relationships_json',
                       side_effect=RelationshipError('PRIVATE_FAILURE')), self.assertRaises(StorageError) as raised:
                save_run(workspace, *parts[:2], **arguments(parts))
            self.assertNotIn('PRIVATE_FAILURE', str(raised.exception))
            self.assertFalse(workspace.exists())
            for index, name in enumerate(('review.MAX_REVIEW_V3_BYTES', 'review_html.MAX_REVIEW_V3_PAYLOAD_BYTES',
                                          'review_html.MAX_REVIEW_V3_HTML_BYTES')):
                workspace = root / str(index)
                with patch(f'plc_workbench.{name}', 1), self.assertRaises(StorageError):
                    save_run(workspace, *parts[:2], **arguments(parts))
                self.assertFalse(workspace.exists())

            def fail(destination, run_dir, name, data):
                if name == 'relationships.json':
                    raise OSError('PRIVATE_DISK_DETAIL')
                return _write_artifact(destination, run_dir, name, data)

            workspace = root / 'write'
            with patch('plc_workbench.storage._write_artifact', side_effect=fail), self.assertRaises(StorageError):
                save_run(workspace, *parts[:2], **arguments(parts))
            saved, = workspace.iterdir()
            self.assertFalse((saved / 'manifest.json').exists())

    def test_cli_and_runner_save_identical_relationships_and_fixed_safe_failures(self) -> None:
        parts = captured()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(SOURCE)
            code, output, error = invoke(['review', str(source), '--workspace', str(root / 'runs')])
            self.assertEqual((code, error), (3, ''))
            saved, = (root / 'runs').iterdir()
            self.assertIn(str(saved / 'review.html'), output)
            self.assertEqual(json.loads((saved / 'relationships.json').read_bytes()), parts[-1].to_dict())
            with patch.object(work_check, 'save_run', return_value=root / 'saved') as save:
                outcome = work_check._analyze(root, source, root, REVISION)
            self.assertIsNone(outcome['failure_code'])
            self.assertEqual(save.call_args.kwargs['relationships'].to_dict(), parts[-1].to_dict())
            outcome.pop('diagnostic_sample')
            outcome.pop('targeted_samples', None)
            self.assertIsNotNone(outcome.pop('custom_instruction_summary'))
            self.assertIsNotNone(outcome.pop('indexed_access_summary'))
            self.assertIsNotNone(outcome.pop('condition_summary'))
            self.assertIsNotNone(outcome.pop('binding_context_summary'))
            self.assertEqual(outcome, report()['analysis'])
            with patch('plc_workbench.relationships.analyze_relationships', side_effect=RelationshipError('PRIVATE_FAILURE')):
                code, output, error = invoke(['review', str(source), '--workspace', str(root / 'failed')])
            self.assertEqual((code, output), (1, ''))
            self.assertNotIn('PRIVATE_FAILURE', error)
            self.assertFalse((root / 'failed').exists())
            with patch.object(work_check, 'analyze_relationships', side_effect=RelationshipError('PRIVATE_FAILURE')):
                failure = work_check._analyze(root, source, root, REVISION)
            self.assertEqual((failure['failure_code'], failure['private_run_saved']), ('relationship_error', False))
            self.assertTrue(all(value is None for key, value in failure.items() if key.endswith('_summary')))
            self.assertNotIn('PRIVATE_FAILURE', json.dumps(failure))
            self.assertIn('PRIVATE_FAILURE', (root / 'analysis.log').read_text())


class RelationshipWorkReportTests(unittest.TestCase):
    def test_aggregate_only_publication_and_history_including_next_current_report(self) -> None:
        payload = report()
        rendered = work_check.render_work_check_report(payload)
        self.assertEqual(json.loads(rendered), payload)
        for private in ('raw_text', 'instruction_id', 'target_id', 'snapshot', '937291', 'A+A'):
            self.assertNotIn(private, rendered)
        paths = list((ROOT / 'public/inspection').glob('work-check-*.json'))
        with tempfile.TemporaryDirectory() as folder:
            returned = Path(folder) / 'work-check-current.json'
            returned.write_text(rendered)
            for path in (*paths, returned):
                before = path.read_bytes()
                historical = json.loads(before)
                self.assertEqual(json.loads(work_check.render_work_check_report(historical)), historical)
                self.assertEqual(path.read_bytes(), before)
            from test_rung_analysis_workflow import RungAnalysisWorkReportTests
            local = Path(folder) / 'public/inspection'
            local.mkdir(parents=True)
            (local / returned.name).write_text(rendered)
            with patch('test_rung_analysis_workflow.ROOT', Path(folder)):
                RungAnalysisWorkReportTests().test_current_summary_is_aggregate_only_and_historical_reports_are_unchanged()

    def test_valid_foreign_aggregate_populations_cannot_contradict_existing_evidence(self) -> None:
        for target, donor in (('MOV(A,A);', 'MOV(1,A);'),
                              ('CPT(A,A);', 'CPT(A,A+A);'),
                              ('MOV(A,A);', 'MOV(MISSING,A);'),
                              ('ADD(A,A,A);', 'MOV(A,A)CLR(A);'),
                              ('[MOV(A,A)ADD(A,A,A),];', 'MOV(A,A)ADD(A,A,A);'),
                              ('MOV(A,A);', '[MOV(A,A),];'),
                              ('[MOV(A,A),];', 'MOV(A,A);'),
                              ('MOV(A,A);', ';')):
            bad = report(ladder(target))
            summary = report(ladder(donor))['analysis']['relationship_summary']
            validate_relationship_summary(summary)
            bad['analysis']['relationship_summary'] = summary
            with self.subTest(target=target, donor=donor), self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)

    def test_branched_instruction_bounds_admit_empty_and_mixed_source_shapes(self) -> None:
        for text in (';', '[,];', '[MOV(A,A),];', 'MOV(A,A);', '[XIC(A),]MOV(A,A);'):
            with self.subTest(text=text):
                work_check.validate_work_check_report(report(ladder(text)))
        data = ladder('MOV(A,A);').replace(b'</RLLContent>',
            b'<Rung Number="908" Type="N"><Text>[,];</Text></Rung>'
            b'<Rung Number="909" Type="N"><Text>[MOV(A,A),];</Text></Rung></RLLContent>')
        work_check.validate_work_check_report(report(data))

    def test_closed_versions_and_failure_codes(self) -> None:
        previous, current = old_report(SOURCE), report()
        for bad in (dict(current, schema_version=22, workflow_version='work-check-22'),
                    dict(previous, schema_version=23, workflow_version='work-check-23')):
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)
        for mutate in (lambda p: p['analysis'].update(relationship_summary=None),
                       lambda p: p['analysis']['relationship_summary']['tool_revision'].update(commit='b' * 40),
                       lambda p: p['analysis']['relationship_summary'].update(schema_version=True),
                       lambda p: p['analysis']['relationship_summary'].update(private='PRIVATE')):
            bad = deepcopy(current)
            mutate(bad)
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)
        for state in ('failed', 'not_run'):
            failed = deepcopy(current)
            failed['analysis'] = {'status': state, 'failure_code': 'relationship_error' if state == 'failed' else None,
                'private_run_saved': False, **{key: None for key in current['analysis'] if key.endswith('_summary')}}
            failed.update(status='failed', diagnostic_sample=None)
            if state == 'not_run':
                failed['tests']['application'] = work_check.unavailable_result('not_run')
            work_check.validate_work_check_report(failed)
            failed['analysis']['relationship_summary'] = current['analysis']['relationship_summary']
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(failed)
        failed = deepcopy(previous)
        failed['analysis'] = {'status': 'failed', 'failure_code': 'relationship_error', 'private_run_saved': False,
            **{key: None for key in previous['analysis'] if key.endswith('_summary')}}
        failed.update(status='failed', diagnostic_sample=None)
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(failed)

    def test_versioned_caps_and_real_publication_boundary(self) -> None:
        current, previous, legacy = report(), old_report(SOURCE), access_report(SOURCE)
        rendered = work_check.render_work_check_report(current)
        size = len(rendered.encode())
        with patch.object(work_check, 'MAX_REPORT_BYTES', 1), patch.object(work_check, 'MAX_REPORT_V22_BYTES', size):
            for accepted in (current, previous):
                work_check.validate_work_check_report(accepted)
                work_check.render_work_check_report(accepted)
            with self.assertRaises(work_check.WorkCheckError):
                work_check.validate_work_check_report(legacy)
        with patch.object(work_check, 'MAX_REPORT_V22_BYTES', size - 1):
            with self.assertRaises(work_check.WorkCheckError):
                work_check.render_work_check_report(current)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            padded = rendered + ' ' * max(0, 33 * 1024 - len(rendered))
            publish_summary(root / 'accepted.json', padded, input_path=root / 'source.L5X')
            self.assertEqual((root / 'accepted.json').read_bytes(), rendered.encode())
            old = work_check.render_work_check_report(legacy)
            for index, value in enumerate((old + ' ' * max(0, 33 * 1024 - len(old)),
                                            rendered + ' ' * (49 * 1024),
                                            rendered.replace('"relationship-analysis-1"', '"PRIVATE"'))):
                destination = root / f'rejected-{index}.json'
                with self.assertRaises(SummaryOutputError):
                    publish_summary(destination, value, input_path=root / 'source.L5X')
                self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
