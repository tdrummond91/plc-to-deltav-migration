"""PID review publication uses invented captured bytes and temporary files only."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import work_check
from plc_workbench.pid import PidError, analyze_pid
from plc_workbench.pid_summary import PidSummaryError, validate_pid_summary
from plc_workbench.review import ReviewError, build_review_data, render_review_json, validate_review_data
from plc_workbench.review_html import ReviewHtmlError, render_review_html
from plc_workbench.storage import StorageError, _write_artifact, save_run
from plc_workbench.tag_data import analyze_tag_data

from test_access_workflow import COMPLETE, evidence
from test_review_html import ParsedPage
from test_review_workflow import invoke
from test_unmatched_sample_report import REVISION, report


ROOT = Path(__file__).resolve().parents[2]
WORK15_REPORT = ROOT / 'public/inspection/work-check-20261015T110923Z-e950612e.json'
DATA = COMPLETE.replace(b'<Tag Name="A" TagType="Base"/>', b'''<Tag Name="A" TagType="Base" DataType="PID">
<Data Format="Decorated"><Structure DataType="PID">
<DataValueMember Name="SP" DataType="REAL" Value="937291"/>
</Structure></Data></Tag>''').replace(b'XIC(A)OTE(A);', b'PID(A,1,0,A,0,0,0);')


def captured(data: bytes = DATA):
    snapshot, inventory, references, sfc, access = evidence(data)
    tag_data = analyze_tag_data(snapshot, inventory)
    pid = analyze_pid(snapshot, inventory, references, tag_data)
    return snapshot, inventory, references, sfc, access, tag_data, pid


def arguments(parts: tuple) -> dict:
    return dict(references=parts[2], sfc_structure=parts[3], include_review=True,
                access=parts[4], tag_data=parts[5], pid=parts[6])


class PidReviewStorageTests(unittest.TestCase):
    def test_review4_manifest7_preserve_all_legacy_optional_paths_and_hash_eleven_artifacts(self) -> None:
        parts = captured()
        snapshot, inventory, references, sfc, access, tag_data, pid = parts
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            variants = ({}, {'references': references}, {'references': references, 'sfc_structure': sfc},
                        {'references': references, 'sfc_structure': sfc, 'include_review': True},
                        {'references': references, 'sfc_structure': sfc, 'include_review': True, 'access': access},
                        {'references': references, 'sfc_structure': sfc, 'include_review': True,
                         'access': access, 'tag_data': tag_data})
            previous = []
            for version, kwargs in enumerate(variants, 1):
                saved = save_run(workspace, snapshot, inventory, **kwargs)
                files = {path.name: path.read_bytes() for path in saved.iterdir()}
                manifest = json.loads(files['manifest.json'])
                self.assertEqual(manifest['schema_version'], version)
                self.assertNotIn('pid.json', files)
                self.assertFalse(any(key.startswith('pid_') for key in manifest))
                if version >= 4:
                    self.assertEqual(manifest['review_schema_version'], version - 3)
                    payload = json.loads(ParsedPage(files['review.html'].decode()).scripts[0][1])
                    self.assertNotIn('pid', payload)
                previous.append((saved, files))
            sfc_only = save_run(workspace, snapshot, inventory, sfc_structure=sfc)
            self.assertEqual(json.loads((sfc_only / 'manifest.json').read_bytes())['artifact_kind'],
                             'source_sfc_structure_run')
            saved = save_run(workspace, snapshot, inventory, **arguments(parts))
            manifest = json.loads((saved / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], manifest['artifact_kind']),
                             (7, 'source_reference_sfc_access_tag_data_pid_review_run'))
            self.assertEqual((manifest['review_schema_version'], manifest['review_version']),
                             (4, 'engineering-review-4'))
            self.assertEqual((manifest['pid_schema_version'], manifest['pid_analyzer_version']),
                             (1, 'pid-evidence-1'))
            self.assertEqual(len(manifest['artifacts']), 11)
            private = json.loads((saved / 'pid.json').read_bytes())
            self.assertEqual(private, pid.to_dict())
            payload = json.loads(ParsedPage((saved / 'review.html').read_text(encoding='utf-8')).scripts[0][1])
            self.assertEqual(payload['pid'], private)
            legacy = build_review_data(snapshot, inventory, references, sfc, access=access, tag_data=tag_data)
            for key in ('inventory', 'references', 'sfc', 'access', 'tag_data', 'patterns', 'findings', 'statistics'):
                self.assertEqual(payload[key], legacy[key])
            validate_review_data(snapshot, inventory, references, sfc, payload,
                                 access=access, tag_data=tag_data, pid=pid)
            for name, details in manifest['artifacts'].items():
                content = (saved / name).read_bytes()
                self.assertEqual(details, {'sha256': hashlib.sha256(content).hexdigest(), 'size_bytes': len(content)})
            for prior, files in previous:
                self.assertEqual({path.name: path.read_bytes() for path in prior.iterdir()}, files)

    def test_dependencies_foreign_and_forged_pid_fail_before_copy_or_workspace_allocation(self) -> None:
        parts = captured()
        full = arguments(parts)
        foreign = captured(DATA.replace(b'937291', b'937292'))[-1]
        forged = deepcopy(parts[-1])
        forged.occurrences[0]['storage_status'] = 'no_data'
        cycle = deepcopy(parts[-1])
        cycle.coverage['private_extra'] = cycle.coverage
        variants = [dict(pid=parts[-1]), dict(full, include_review=False), dict(full, tag_data=None),
                    dict(full, access=None), dict(full, references=None), dict(full, sfc_structure=None),
                    dict(full, pid=foreign), dict(full, pid=forged), dict(full, pid=cycle),
                    dict(full, pid=replace(parts[-1], schema_version=True))]
        with tempfile.TemporaryDirectory() as directory:
            for index, kwargs in enumerate(variants):
                workspace = Path(directory) / str(index)
                with self.subTest(index=index), self.assertRaises(StorageError):
                    save_run(workspace, *parts[:2], **kwargs)
                self.assertFalse(workspace.exists())
        payload = build_review_data(*parts[:4], access=parts[4], tag_data=parts[5], pid=parts[6])
        payload['pid']['occurrences'][0]['backing_owner_id'] = None
        with self.assertRaises(ReviewError):
            validate_review_data(*parts[:4], payload, access=parts[4], tag_data=parts[5], pid=parts[6])

    def test_html_version_pairs_and_required_or_forbidden_companions_are_strict(self) -> None:
        parts = captured()
        kwargs = ({}, {'access': parts[4]}, {'access': parts[4], 'tag_data': parts[5]},
                  {'access': parts[4], 'tag_data': parts[5], 'pid': parts[6]})
        for version, options in enumerate(kwargs, 1):
            original = build_review_data(*parts[:4], **options)
            mutations = [lambda p: p.update(schema_version=True),
                         lambda p: p.update(report_version='engineering-review-0')]
            for companion, minimum in (('access', 2), ('tag_data', 3), ('pid', 4)):
                if version >= minimum:
                    mutations.append(lambda p, key=companion: p.pop(key))
                    mutations.append(lambda p, key=companion: p.update({key: None}))
                else:
                    mutations.append(lambda p, key=companion: p.update({key: {}}))
            for mutate in mutations:
                candidate = deepcopy(original)
                mutate(candidate)
                with self.subTest(version=version, mutate=mutate), self.assertRaises(ReviewHtmlError):
                    render_review_html(candidate)

    def test_review4_uses_existing_v3_budgets_with_exact_payload_boundary(self) -> None:
        parts = captured()
        kwargs = dict(access=parts[4], tag_data=parts[5], pid=parts[6])
        data = build_review_data(*parts[:4], **kwargs)
        exact = len(render_review_json(data).encode('utf-8'))
        with patch('plc_workbench.review.MAX_REVIEW_BYTES', 1):
            with patch('plc_workbench.review.MAX_REVIEW_V3_BYTES', exact):
                self.assertEqual(build_review_data(*parts[:4], **kwargs), data)
            with patch('plc_workbench.review.MAX_REVIEW_V3_BYTES', exact - 1), self.assertRaises(ReviewError):
                build_review_data(*parts[:4], **kwargs)
        with patch('plc_workbench.review_html.MAX_REVIEW_HTML_BYTES', 1), \
                patch('plc_workbench.review_html.MAX_REVIEW_PAYLOAD_BYTES', 1):
            self.assertIn('review-data', render_review_html(data))
        with tempfile.TemporaryDirectory() as directory:
            for index, limit in enumerate(('review.MAX_REVIEW_V3_BYTES', 'review_html.MAX_REVIEW_V3_PAYLOAD_BYTES',
                                          'review_html.MAX_REVIEW_V3_HTML_BYTES')):
                workspace = Path(directory) / str(index)
                with self.subTest(limit=limit), patch(f'plc_workbench.{limit}', 1), self.assertRaises(StorageError):
                    save_run(workspace, *parts[:2], **arguments(parts))
                self.assertFalse(workspace.exists())

    def test_pid_render_failure_precedes_allocation_and_write_failure_never_finalizes(self) -> None:
        parts = captured()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / 'not-created'
            with patch('plc_workbench.pid.render_pid_json', side_effect=PidError('PRIVATE_FAILURE')):
                with self.assertRaises(StorageError) as raised:
                    save_run(workspace, *parts[:2], **arguments(parts))
            self.assertNotIn('PRIVATE_FAILURE', str(raised.exception))
            self.assertFalse(workspace.exists())

            def fail(destination, run_dir, name, data):
                if name == 'pid.json':
                    raise OSError('PRIVATE_DISK_DETAIL')
                return _write_artifact(destination, run_dir, name, data)

            with patch('plc_workbench.storage._write_artifact', side_effect=fail), self.assertRaises(StorageError):
                save_run(workspace, *parts[:2], **arguments(parts))
            saved, = workspace.iterdir()
            self.assertFalse((saved / 'manifest.json').exists())

    def test_cli_captures_once_includes_pid_and_sanitizes_pid_failure(self) -> None:
        from plc_workbench.source import capture_snapshot
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'invented.L5X'
            source.write_bytes(DATA)

            def capture_then_replace(path):
                snapshot = capture_snapshot(path)
                source.write_bytes(b'changed live input')
                return snapshot

            workspace = Path(directory) / 'runs'
            with patch('plc_workbench.source.capture_snapshot', side_effect=capture_then_replace) as capture, \
                    patch('plc_workbench.pid.analyze_pid', wraps=analyze_pid) as analyze:
                code, output, error = invoke(['review', str(source), '--workspace', str(workspace)])
            capture.assert_called_once_with(source)
            self.assertGreaterEqual(analyze.call_count, 1)
            self.assertTrue(all(call.args[0].data == DATA for call in analyze.call_args_list))
            self.assertEqual((code, error), (3, ''))
            saved, = workspace.iterdir()
            self.assertIn(str(saved / 'review.html'), output)
            self.assertEqual((saved / 'snapshot.L5X').read_bytes(), DATA)
            self.assertEqual(json.loads((saved / 'pid.json').read_bytes()), captured()[-1].to_dict())
            source.write_bytes(DATA)
            with patch('plc_workbench.pid.analyze_pid', side_effect=PidError('PRIVATE_FAILURE')):
                code, output, error = invoke(['review', str(source), '--workspace', str(Path(directory) / 'failed')])
            self.assertEqual((code, output), (1, ''))
            self.assertNotIn('PRIVATE_FAILURE', error)
            self.assertFalse((Path(directory) / 'failed').exists())


class PidWorkReportTests(unittest.TestCase):
    def test_work16_count_only_summary_and_frozen_work15(self) -> None:
        payload = report(DATA)
        self.assertEqual((payload['schema_version'], payload['workflow_version']), (17, 'work-check-17'))
        self.assertEqual(payload['analysis']['pid_summary']['schema_version'], 1)
        rendered = work_check.render_work_check_report(payload)
        self.assertEqual(json.loads(rendered), payload)
        self.assertLess(len(rendered.encode()), 32 * 1024)
        for private in ('PRIVATE_', '937291', 'snapshot', 'instruction_id', 'owner_id', 'content_id', 'raw_text'):
            self.assertNotIn(private, rendered)
        before = WORK15_REPORT.read_bytes()
        historical = json.loads(before)
        self.assertEqual((historical['schema_version'], historical['workflow_version']), (15, 'work-check-15'))
        self.assertEqual(json.loads(work_check.render_work_check_report(historical)), historical)
        for mutate in (lambda p: p.update(schema_version=16, workflow_version='work-check-16'),
                       lambda p: p['analysis'].update(pid_summary=payload['analysis']['pid_summary']),
                       lambda p: p['analysis'].update(pid_summary=None)):
            changed = deepcopy(historical)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                work_check.validate_work_check_report(changed)
        self.assertEqual(WORK15_REPORT.read_bytes(), before)

    def test_summary_presence_revision_versions_and_closed_keys(self) -> None:
        for mutate in (lambda p: p['analysis'].pop('pid_summary'),
                       lambda p: p['analysis'].update(pid_summary=None),
                       lambda p: p['analysis']['pid_summary']['tool_revision'].update(commit='b' * 40),
                       lambda p: p['analysis']['pid_summary'].update(schema_version=True),
                       lambda p: p['analysis']['pid_summary'].update(schema_version=2),
                       lambda p: p['analysis']['pid_summary'].update(private='PRIVATE'),
                       lambda p: p['analysis'].update(private='PRIVATE'),
                       lambda p: p['analysis']['tag_data_summary'].update(schema_version=2),
                       lambda p: p['analysis']['access_summary'].update(schema_version=1)):
            candidate = report(DATA)
            mutate(candidate)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)

    def test_internally_valid_source_counts_and_pid_population_reconcile(self) -> None:
        for key in ('source_rungs', 'source_instructions', 'source_operands'):
            candidate = report(DATA)
            candidate['analysis']['pid_summary']['coverage'][key] += 1
            validate_pid_summary(candidate['analysis']['pid_summary'])
            with self.subTest(key=key), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        candidate = report(DATA)
        absent = report(COMPLETE)['analysis']['pid_summary']
        absent['coverage'].update({key: candidate['analysis']['pid_summary']['coverage'][key]
                                  for key in ('source_rungs', 'source_instructions', 'source_operands')})
        validate_pid_summary(absent)
        candidate['analysis']['pid_summary'] = absent
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)
        one_pid = DATA.replace(b'PID(A,1,0,A,0,0,0);', b'PID(A,1,0,A,0,0,0)COP(A,1,0,A,0,0,0);')
        two_pid = one_pid.replace(b'COP(', b'PID(')
        candidate = report(one_pid)
        candidate['analysis']['pid_summary'] = report(two_pid)['analysis']['pid_summary']
        validate_pid_summary(candidate['analysis']['pid_summary'])
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)
        work_check.validate_work_check_report(report(DATA.replace(b'PID(', b'pid(')))
        work_check.validate_work_check_report(report(COMPLETE))

    def test_failure_and_not_run_null_summaries_and_pid_error_are_versioned(self) -> None:
        original = report(DATA)
        for state in ('failed', 'not_run'):
            candidate = deepcopy(original)
            candidate['analysis'] = {'status': state, 'failure_code': 'pid_error' if state == 'failed' else None,
                'private_run_saved': False, 'reference_summary': None, 'sfc_structure_summary': None,
                'access_summary': None, 'tag_data_summary': None, 'pid_summary': None, 'pid_member_summary': None}
            candidate.update(status='failed', diagnostic_sample=None)
            if state == 'not_run':
                candidate['tests']['application'] = work_check.unavailable_result('not_run')
            work_check.validate_work_check_report(candidate)
            candidate['analysis']['pid_summary'] = original['analysis']['pid_summary']
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        candidate = deepcopy(original)
        candidate.update(schema_version=15, workflow_version='work-check-15', status='failed', diagnostic_sample=None)
        candidate['analysis'] = {'status': 'failed', 'failure_code': 'pid_error', 'private_run_saved': False,
            'reference_summary': None, 'sfc_structure_summary': None, 'access_summary': None, 'tag_data_summary': None}
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)

    def test_pid_links_cannot_exceed_captured_tag_data_capacities(self) -> None:
        original = report(DATA)['analysis']['pid_summary']
        without_data = DATA.replace(b'<Data Format="Decorated"><Structure DataType="PID">\n'
            b'<DataValueMember Name="SP" DataType="REAL" Value="937291"/>\n'
            b'</Structure></Data>', b'')
        candidate = report(without_data)
        self.assertEqual(candidate['analysis']['tag_data_summary']['coverage']['contents_total'], 0)
        candidate['analysis']['pid_summary'] = original
        validate_pid_summary(original)
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)
        for mutate in (
            lambda c: c.update(representation_occurrences=2, occurrences_with_multiple_representations=1),
            lambda c: c.update(representation_occurrences=2, decorated_representation_occurrences=2,
                               occurrences_with_multiple_representations=1),
            lambda c: c.update(structure_occurrences=2, occurrences_with_multiple_structures=1),
            lambda c: c.update(direct_member_occurrences=2),
        ):
            candidate = report(DATA)
            mutate(candidate['analysis']['pid_summary']['coverage'])
            validate_pid_summary(candidate['analysis']['pid_summary'])
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        repeated = DATA.replace(b'PID(A,1,0,A,0,0,0);', b'PID(A,1,0,A,0,0,0)PID(A,1,0,A,0,0,0);')
        candidate = report(repeated)
        self.assertEqual(candidate['analysis']['pid_summary']['coverage']['representation_occurrences'], 2)
        self.assertEqual(candidate['analysis']['tag_data_summary']['coverage']['contents_total'], 1)
        work_check.validate_work_check_report(candidate)

    def test_runner_passes_captured_pid_once_and_sanitizes_analysis_and_summary_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(DATA)
            with patch.object(work_check, 'capture_snapshot', wraps=work_check.capture_snapshot) as capture, \
                    patch.object(work_check, 'analyze_pid', wraps=analyze_pid) as analyze, \
                    patch.object(work_check, 'save_run') as save:
                outcome = work_check._analyze(root, source, root, REVISION)
            capture.assert_called_once_with(source)
            analyze.assert_called_once()
            self.assertEqual(save.call_args.args[1].data, DATA)
            self.assertEqual(save.call_args.kwargs['pid'].to_dict(), captured()[-1].to_dict())
            self.assertIsNotNone(outcome['pid_summary'])
            for target, error, expected, saved in (
                ('analyze_pid', PidError('PRIVATE_FAILURE'), 'pid_error', False),
                ('build_pid_summary', PidSummaryError('PRIVATE_FAILURE'), 'summary_error', True),
            ):
                with patch.object(work_check, target, side_effect=error), patch.object(work_check, 'save_run'):
                    outcome = work_check._analyze(root, source, root, REVISION)
                self.assertEqual((outcome['failure_code'], outcome['private_run_saved']), (expected, saved))
                for key in ('reference_summary', 'sfc_structure_summary', 'access_summary', 'tag_data_summary', 'pid_summary', 'pid_member_summary'):
                    self.assertIsNone(outcome[key])
                self.assertNotIn('PRIVATE_FAILURE', json.dumps(outcome))
                self.assertIn('PRIVATE_FAILURE', (root / 'analysis.log').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
