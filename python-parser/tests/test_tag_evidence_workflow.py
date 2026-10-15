"""Tag Data publication boundaries use invented bytes and temporary files."""
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
from plc_workbench.storage import StorageError, _write_artifact, save_run
from plc_workbench.tag_data import TagDataError, analyze_tag_data
from plc_workbench.tag_data_summary import TagDataSummaryError, validate_tag_data_summary

from test_access_workflow import COMPLETE, evidence
from test_review_html import ParsedPage
from test_review_workflow import invoke
from test_unmatched_sample_report import REVISION, report


ROOT = Path(__file__).resolve().parents[2]
WORK14_REPORT = ROOT / 'public/inspection/work-check-20261015T094840Z-c2673e7a.json'
DATA = COMPLETE.replace(b'<Tag Name="A" TagType="Base"/>', b'''<Tag Name="A" TagType="Base">
<Data Format="Decorated"><Structure DataType="PRIVATE_TYPE">
<DataValueMember Name="PRIVATE_MEMBER" DataType="DINT" Value="937291"/>
</Structure></Data></Tag>''')
OPAQUE = DATA.replace(b'Format="Decorated"', b'Format="PRIVATE_FORMAT"')


def captured(data: bytes = DATA):
    snapshot, inventory, references, sfc, access = evidence(data)
    tag_data = analyze_tag_data(snapshot, inventory)
    return snapshot, inventory, references, sfc, access, tag_data


class TagEvidenceStorageTests(unittest.TestCase):
    def test_manifest6_hashes_review3_and_legacy_optional_paths_are_preserved(self) -> None:
        snapshot, inventory, references, sfc, access, tag_data = captured()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            variants = ({}, {'references': references}, {'references': references, 'sfc_structure': sfc},
                        {'references': references, 'sfc_structure': sfc, 'include_review': True},
                        {'references': references, 'sfc_structure': sfc, 'include_review': True, 'access': access})
            previous = []
            for version, arguments in enumerate(variants, 1):
                saved = save_run(workspace, snapshot, inventory, **arguments)
                contents = {path.name: path.read_bytes() for path in saved.iterdir()}
                manifest = json.loads(contents['manifest.json'])
                self.assertEqual(manifest['schema_version'], version)
                self.assertNotIn('tag-data.json', contents)
                self.assertFalse(any(key.startswith('tag_data_') for key in manifest))
                if version >= 4:
                    self.assertEqual(manifest['review_schema_version'], version - 3)
                previous.append((saved, contents))
            saved = save_run(workspace, snapshot, inventory, references=references,
                             sfc_structure=sfc, include_review=True, access=access, tag_data=tag_data)
            manifest = json.loads((saved / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], manifest['artifact_kind']),
                             (6, 'source_reference_sfc_access_tag_data_review_run'))
            self.assertEqual((manifest['review_schema_version'], manifest['review_version']),
                             (3, 'engineering-review-3'))
            self.assertEqual((manifest['tag_data_schema_version'], manifest['tag_data_analyzer_version']),
                             (1, 'tag-data-1'))
            self.assertEqual(len(manifest['artifacts']), 10)
            private = json.loads((saved / 'tag-data.json').read_bytes())
            self.assertEqual(private, tag_data.to_dict())
            payload = json.loads(ParsedPage((saved / 'review.html').read_text(encoding='utf-8')).scripts[0][1])
            self.assertEqual(payload['tag_data'], private)
            for name, details in manifest['artifacts'].items():
                content = (saved / name).read_bytes()
                self.assertEqual(details, {'sha256': hashlib.sha256(content).hexdigest(), 'size_bytes': len(content)})
            for prior, contents in previous:
                self.assertEqual({path.name: path.read_bytes() for path in prior.iterdir()}, contents)

    def test_dependencies_and_foreign_or_forged_evidence_fail_before_workspace_creation(self) -> None:
        snapshot, inventory, references, sfc, access, tag_data = captured()
        full = dict(references=references, sfc_structure=sfc, include_review=True, access=access)
        wrong = captured(DATA.replace(b'937291', b'937292'))[-1]
        forged = deepcopy(tag_data)
        forged.elements[-1]['attributes']['Value'] = 'PRIVATE_FORGED'
        variants = [dict(tag_data=tag_data), dict(references=references, tag_data=tag_data),
                    dict(full, include_review=False, tag_data=tag_data), dict(full, access=None, tag_data=tag_data),
                    dict(full, tag_data=wrong), dict(full, tag_data=forged),
                    dict(full, tag_data=replace(tag_data, schema_version=True))]
        with tempfile.TemporaryDirectory() as directory:
            for index, arguments in enumerate(variants):
                workspace = Path(directory) / str(index)
                with self.subTest(index=index), self.assertRaises(StorageError):
                    save_run(workspace, snapshot, inventory, **arguments)
                self.assertFalse(workspace.exists())

    def test_render_failure_is_private_and_precedes_all_writes(self) -> None:
        snapshot, inventory, references, sfc, access, tag_data = captured()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / 'not-created'
            with patch('plc_workbench.tag_data.render_tag_data_json', side_effect=TagDataError('PRIVATE_VALUE')):
                with self.assertRaises(StorageError) as raised:
                    save_run(workspace, snapshot, inventory, references=references, sfc_structure=sfc,
                             include_review=True, access=access, tag_data=tag_data)
            self.assertNotIn('PRIVATE_VALUE', str(raised.exception))
            self.assertFalse(workspace.exists())

    def test_review3_payload_and_html_budget_failures_allocate_no_workspace(self) -> None:
        snapshot, inventory, references, sfc, access, tag_data = captured()
        with tempfile.TemporaryDirectory() as directory:
            for index, limit in enumerate(('review.MAX_REVIEW_V3_BYTES',
                                          'review_html.MAX_REVIEW_V3_PAYLOAD_BYTES',
                                          'review_html.MAX_REVIEW_V3_HTML_BYTES')):
                workspace = Path(directory) / str(index)
                with self.subTest(limit=limit), patch(f'plc_workbench.{limit}', 1), self.assertRaises(StorageError):
                    save_run(workspace, snapshot, inventory, references=references, sfc_structure=sfc,
                             include_review=True, access=access, tag_data=tag_data)
                self.assertFalse(workspace.exists())

    def test_tag_data_write_failure_never_finalizes_manifest(self) -> None:
        snapshot, inventory, references, sfc, access, tag_data = captured()

        def fail(workspace, run_dir, name, data):
            if name == 'tag-data.json':
                raise OSError('PRIVATE_DISK_DETAIL')
            return _write_artifact(workspace, run_dir, name, data)

        with tempfile.TemporaryDirectory() as directory:
            with patch('plc_workbench.storage._write_artifact', side_effect=fail):
                with self.assertRaises(StorageError):
                    save_run(Path(directory), snapshot, inventory, references=references, sfc_structure=sfc,
                             include_review=True, access=access, tag_data=tag_data)
            saved, = Path(directory).iterdir()
            self.assertFalse((saved / 'manifest.json').exists())

    def test_cli_captures_once_and_reports_safe_tag_failure(self) -> None:
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
                    patch('plc_workbench.tag_data.analyze_tag_data', wraps=analyze_tag_data) as analyze:
                code, output, error = invoke(['review', str(source), '--workspace', str(workspace)])
            capture.assert_called_once_with(source)
            self.assertTrue(analyze.called)
            # PID and report validation replay the captured evidence. None of
            # those checks recaptures the changed live file.
            self.assertTrue(all(call.args[0].data == DATA for call in analyze.call_args_list))
            self.assertEqual((code, error), (0, ''))
            saved, = workspace.iterdir()
            self.assertIn(str(saved / 'review.html'), output)
            self.assertEqual((saved / 'snapshot.L5X').read_bytes(), DATA)
            self.assertEqual(json.loads((saved / 'tag-data.json').read_bytes()), captured()[-1].to_dict())
            source.write_bytes(DATA)
            with patch('plc_workbench.tag_data.analyze_tag_data', side_effect=TagDataError('PRIVATE_FAILURE')):
                code, output, error = invoke(['review', str(source), '--workspace', str(Path(directory) / 'failed')])
            self.assertEqual((code, output), (1, ''))
            self.assertNotIn('PRIVATE_FAILURE', error)
            self.assertFalse((Path(directory) / 'failed').exists())

    def test_cli_tag_issue_makes_otherwise_complete_run_partial(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'invented.L5X'
            source.write_bytes(OPAQUE)
            workspace = Path(directory) / 'runs'
            code, _, error = invoke(['review', str(source), '--workspace', str(workspace)])
            self.assertEqual((code, error), (3, ''))
            saved, = workspace.iterdir()
            for name in ('inventory.json', 'references.json', 'sfc-structure.json', 'access.json'):
                self.assertEqual(json.loads((saved / name).read_bytes())['status'], 'complete')
            self.assertEqual(json.loads((saved / 'tag-data.json').read_bytes())['status'], 'partial')
            self.assertEqual(json.loads((saved / 'manifest.json').read_bytes())['status'], 'partial')


class TagEvidenceWorkTests(unittest.TestCase):
    def test_current_work_summary_is_count_only_and_version14_is_frozen(self) -> None:
        payload = report(DATA)
        self.assertEqual((payload['schema_version'], payload['workflow_version']), (17, 'work-check-17'))
        summary = payload['analysis']['tag_data_summary']
        self.assertEqual(summary['schema_version'], 1)
        rendered = work_check.render_work_check_report(payload)
        self.assertEqual(json.loads(rendered), payload)
        self.assertLess(len(rendered.encode()), 32 * 1024)
        for private in ('PRIVATE_', '937291', 'source_id', 'owner_id', '"direct_text":', '"attributes":', 'snapshot'):
            self.assertNotIn(private, rendered)
        before = WORK14_REPORT.read_bytes()
        historical = json.loads(before)
        self.assertEqual((historical['schema_version'], historical['workflow_version']), (14, 'work-check-14'))
        self.assertEqual(json.loads(work_check.render_work_check_report(historical)), historical)
        for mutation in (
            lambda p: p.update(schema_version=15, workflow_version='work-check-15'),
            lambda p: p['analysis'].update(tag_data_summary=summary),
            lambda p: p['analysis'].update(tag_data_summary=None),
        ):
            changed = deepcopy(historical)
            mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                work_check.validate_work_check_report(changed)
        self.assertEqual(WORK14_REPORT.read_bytes(), before)

    def test_summary_presence_revision_and_closed_metadata(self) -> None:
        for mutation in (
            lambda p: p['analysis'].pop('tag_data_summary'),
            lambda p: p['analysis'].update(tag_data_summary=None),
            lambda p: p['analysis']['tag_data_summary']['tool_revision'].update(commit='b' * 40),
            lambda p: p['analysis']['tag_data_summary'].update(schema_version=2),
            lambda p: p['analysis']['tag_data_summary'].update(format='PRIVATE_FORMAT'),
        ):
            changed = report(DATA)
            mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                work_check.validate_work_check_report(changed)

    def test_internally_valid_owner_counts_and_xml_counts_must_match_source(self) -> None:
        for mutation in (
            lambda c: c.update(owners_total=c['owners_total'] + 1, owners_without_data=c['owners_without_data'] + 1,
                               owners_by_kind={**c['owners_by_kind'], 'tag': c['owners_by_kind']['tag'] + 1}),
            lambda c: c['owners_by_kind'].update(tag=0, aoi_local_tag=1),
            lambda c: c.update(source_xml_elements=c['source_xml_elements'] + 1),
        ):
            changed = report(DATA)
            summary = changed['analysis']['tag_data_summary']
            mutation(summary['coverage'])
            validate_tag_data_summary(summary)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                work_check.validate_work_check_report(changed)

    def test_all_six_owner_kinds_reconcile_including_unnamed_declarations(self) -> None:
        data = COMPLETE.replace(b'</Controller>', b'''<AddOnInstructionDefinitions>
<AddOnInstructionDefinition Name="PRIVATE_AOI"><Parameters><Parameter DataType="DINT"/>
</Parameters><LocalTags><LocalTag Name="PRIVATE_LOCAL"/></LocalTags>
</AddOnInstructionDefinition></AddOnInstructionDefinitions><Modules><Module Name="PRIVATE_MODULE">
<Communications><ConfigTag/><Connections><Connection><InputTag/><OutputTag/></Connection>
</Connections></Communications></Module></Modules></Controller>''')
        payload = report(data)
        coverage = payload['analysis']['tag_data_summary']['coverage']
        self.assertEqual(coverage['owners_by_kind'], {'tag': 1, 'aoi_parameter': 1,
            'aoi_local_tag': 1, 'module_input_tag': 1, 'module_output_tag': 1, 'module_config_tag': 1})
        self.assertEqual((coverage['owners_total'], coverage['owners_without_data']), (6, 6))
        work_check.validate_work_check_report(payload)

    def test_no_data_is_complete_and_tag_issue_status_is_combined(self) -> None:
        absent = report(COMPLETE)
        self.assertEqual(absent['analysis']['tag_data_summary']['status'], 'complete')
        self.assertEqual(absent['analysis']['tag_data_summary']['coverage']['owners_without_data'], 1)
        self.assertEqual(absent['status'], 'passed')
        payload = report(OPAQUE)
        for key in ('reference_summary', 'sfc_structure_summary', 'access_summary'):
            self.assertEqual(payload['analysis'][key]['status'], 'complete')
        self.assertEqual(payload['analysis']['tag_data_summary']['status'], 'partial')
        self.assertEqual((payload['analysis']['status'], payload['status']), ('partial', 'partial'))
        work_check.validate_work_check_report(payload)
        payload['analysis']['status'] = 'complete'
        payload['status'] = 'passed'
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_new_failure_code_and_null_summary_rules_are_versioned(self) -> None:
        original = report(DATA)
        for status in ('failed', 'not_run'):
            payload = deepcopy(original)
            payload['analysis'] = {'status': status, 'failure_code': 'tag_data_error' if status == 'failed' else None,
                'private_run_saved': False, 'reference_summary': None, 'sfc_structure_summary': None,
                'access_summary': None, 'tag_data_summary': None, 'pid_summary': None, 'pid_member_summary': None}
            payload.update(status='failed', diagnostic_sample=None)
            if status == 'not_run':
                payload['tests']['application'] = work_check.unavailable_result('not_run')
            work_check.validate_work_check_report(payload)
            payload['analysis']['tag_data_summary'] = original['analysis']['tag_data_summary']
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)
        payload.update(schema_version=14, workflow_version='work-check-14')
        payload['analysis'] = {'status': 'failed', 'failure_code': 'tag_data_error', 'private_run_saved': False,
            'reference_summary': None, 'sfc_structure_summary': None, 'access_summary': None}
        payload['tests'] = original['tests']
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_runner_passes_captured_evidence_once_and_sanitizes_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(DATA)
            with patch.object(work_check, 'capture_snapshot', wraps=work_check.capture_snapshot) as capture, \
                    patch.object(work_check, 'analyze_tag_data', wraps=analyze_tag_data) as analyze, \
                    patch.object(work_check, 'save_run') as save:
                outcome = work_check._analyze(root, source, root, REVISION)
            capture.assert_called_once_with(source)
            analyze.assert_called_once()
            self.assertEqual(save.call_args.args[1].data, DATA)
            self.assertEqual(save.call_args.kwargs['tag_data'].to_dict(), captured()[-1].to_dict())
            self.assertIsNotNone(outcome['tag_data_summary'])
            for target, error, expected, saved in (
                ('analyze_tag_data', TagDataError('PRIVATE_FAILURE'), 'tag_data_error', False),
                ('build_tag_data_summary', TagDataSummaryError('PRIVATE_FAILURE'), 'summary_error', True),
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
