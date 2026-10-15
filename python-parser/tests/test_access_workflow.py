"""Access publication and work envelopes use invented bytes and temporary files."""
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
from plc_workbench.access import AccessError, analyze_access
from plc_workbench.access_summary import validate_access_summary
from plc_workbench.references import analyze_references
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.storage import StorageError, _write_artifact, save_run

from test_review_workflow import invoke
from test_unmatched_sample_report import REVISION, SOURCE, report


ROOT = Path(__file__).resolve().parents[2]
COMPLETE = SOURCE.replace(b'MysteryRack:7:I.Data[2].3', b'A')


def evidence(data: bytes = COMPLETE):
    snapshot = snapshot_from_bytes(data)
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    return snapshot, inventory, references, analyze_sfc_structure(snapshot, inventory), analyze_access(inventory, references)


class AccessStorageTests(unittest.TestCase):
    def test_manifest5_hashes_review2_and_earlier_runs_are_preserved(self) -> None:
        snapshot, inventory, references, sfc, access = evidence()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            previous = []
            variants = ({}, {'references': references}, {'references': references, 'sfc_structure': sfc},
                        {'references': references, 'sfc_structure': sfc, 'include_review': True})
            for version, arguments in enumerate(variants, 1):
                run = save_run(workspace, snapshot, inventory, **arguments)
                contents = {path.name: path.read_bytes() for path in run.iterdir()}
                manifest = json.loads(contents['manifest.json'])
                self.assertEqual(manifest['schema_version'], version)
                self.assertNotIn('access.json', contents)
                self.assertFalse(any(key.startswith('access_') for key in manifest))
                if version == 4:
                    self.assertEqual((manifest['review_schema_version'], manifest['review_version']),
                                     (1, 'engineering-review-1'))
                previous.append((run, contents))
            run = save_run(workspace, snapshot, inventory, references=references,
                           sfc_structure=sfc, include_review=True, access=access)
            manifest = json.loads((run / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], manifest['artifact_kind']),
                             (5, 'source_reference_sfc_access_review_run'))
            self.assertEqual((manifest['review_schema_version'], manifest['review_version']),
                             (2, 'engineering-review-2'))
            self.assertEqual((manifest['access_schema_version'], manifest['access_analyzer_version']),
                             (1, 'instruction-access-1'))
            self.assertEqual(manifest['status'], 'complete')
            self.assertEqual(len(manifest['artifacts']), 9)
            self.assertEqual(json.loads((run / 'access.json').read_bytes()), access.to_dict())
            for name, details in manifest['artifacts'].items():
                content = (run / name).read_bytes()
                self.assertEqual(details, {'sha256': hashlib.sha256(content).hexdigest(), 'size_bytes': len(content)})
            for prior, contents in previous:
                self.assertEqual({path.name: path.read_bytes() for path in prior.iterdir()}, contents)

    def test_missing_evidence_wrong_snapshot_and_tampered_result_create_no_workspace(self) -> None:
        snapshot, inventory, references, sfc, access = evidence()
        wrong = evidence(COMPLETE.replace(b'OTE(A)', b'OTL(A)'))[-1]
        variants = [dict(access=access), dict(references=references, access=access),
                    dict(references=references, sfc_structure=sfc, access=access),
                    dict(references=references, include_review=True, access=access),
                    dict(references=references, sfc_structure=sfc, include_review=True, access=wrong),
                    dict(references=references, sfc_structure=sfc, include_review=True,
                         access=replace(access, status='partial'))]
        with tempfile.TemporaryDirectory() as directory:
            for index, arguments in enumerate(variants):
                workspace = Path(directory) / str(index)
                with self.subTest(index=index), self.assertRaises(StorageError):
                    save_run(workspace, snapshot, inventory, **arguments)
                self.assertFalse(workspace.exists())

    def test_rendering_failure_precedes_all_writes(self) -> None:
        snapshot, inventory, references, sfc, access = evidence()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / 'not-created'
            with patch('plc_workbench.access.render_access_json', side_effect=AccessError('PRIVATE_VALUE')):
                with self.assertRaises(StorageError) as raised:
                    save_run(workspace, snapshot, inventory, references=references,
                             sfc_structure=sfc, include_review=True, access=access)
            self.assertNotIn('PRIVATE_VALUE', str(raised.exception))
            self.assertFalse(workspace.exists())

    def test_access_write_failure_cannot_finalize_manifest(self) -> None:
        snapshot, inventory, references, sfc, access = evidence()

        def fail(workspace, run_dir, name, data):
            if name == 'access.json':
                raise OSError('PRIVATE_DISK_DETAIL')
            return _write_artifact(workspace, run_dir, name, data)

        with tempfile.TemporaryDirectory() as directory:
            with patch('plc_workbench.storage._write_artifact', side_effect=fail):
                with self.assertRaises(StorageError):
                    save_run(Path(directory), snapshot, inventory, references=references,
                             sfc_structure=sfc, include_review=True, access=access)
            run, = Path(directory).iterdir()
            self.assertFalse((run / 'manifest.json').exists())

    def test_cli_partial_access_is_included_in_exit_status_and_saved_manifest(self) -> None:
        # A literal output binds structurally, but is an access-role gap.
        data = COMPLETE.replace(b'OTE(A)', b'OTE(1)')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'invented.L5X'
            source.write_bytes(data)
            workspace = Path(directory) / 'runs'
            code, output, error = invoke(['review', str(source), '--workspace', str(workspace)])
            self.assertEqual((code, error), (3, ''))
            run, = workspace.iterdir()
            self.assertIn(str(run / 'review.html'), output)
            self.assertEqual(json.loads((run / 'references.json').read_bytes())['status'], 'complete')
            self.assertEqual(json.loads((run / 'access.json').read_bytes())['status'], 'partial')
            self.assertEqual(json.loads((run / 'manifest.json').read_bytes())['status'], 'partial')


class AccessWorkReportTests(unittest.TestCase):
    def test_work13_closed_summary_and_historical_work12_remain_separate(self) -> None:
        payload = report(COMPLETE)
        self.assertEqual((payload['schema_version'], payload['workflow_version']), (13, 'work-check-13'))
        self.assertEqual(payload['analysis']['access_summary']['schema_version'], 1)
        rendered = work_check.render_work_check_report(payload)
        for private in ('PRIVATE_', 'snapshot', 'terminal_root', 'instruction_id', 'raw_text'):
            self.assertNotIn(private, rendered)
        self.assertEqual(json.loads(rendered), payload)
        older = ROOT / 'public/inspection/work-check-20261015T041710Z-a3c2dc50.json'
        before = older.read_bytes()
        historical = json.loads(before)
        self.assertEqual(historical['schema_version'], 12)
        self.assertEqual(json.loads(work_check.render_work_check_report(historical)), historical)
        historical['analysis']['access_summary'] = payload['analysis']['access_summary']
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(historical)
        self.assertEqual(older.read_bytes(), before)

    def test_summary_presence_and_revision_must_match(self) -> None:
        original = report(COMPLETE)
        for mutation in (
            lambda p: p['analysis'].pop('access_summary'),
            lambda p: p['analysis'].update(access_summary=None),
            lambda p: p['analysis']['access_summary']['tool_revision'].update(commit='b' * 40),
            lambda p: p['analysis']['access_summary'].update(raw_text='PRIVATE_VALUE'),
        ):
            changed = deepcopy(original)
            mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                work_check.validate_work_check_report(changed)

    def test_valid_access_counts_must_reconcile_to_reference_populations(self) -> None:
        original = report(COMPLETE)
        variants = (
            COMPLETE.replace(b'XIC(A)', b'NOP()XIC(A)'),
            COMPLETE.replace(b'XIC(A)', b'EQU(A,A)'),
            COMPLETE.replace(b'</RLLContent>', b'<Rung Number="908"><Text>NOP();</Text></Rung></RLLContent>'),
        )
        for data in variants:
            changed = deepcopy(original)
            changed['analysis']['access_summary'] = report(data)['analysis']['access_summary']
            changed['analysis']['status'] = changed['analysis']['access_summary']['status']
            changed['status'] = 'partial' if changed['analysis']['status'] == 'partial' else 'passed'
            validate_access_summary(changed['analysis']['access_summary'])
            with self.subTest(data=data), self.assertRaises(ValueError):
                work_check.validate_work_check_report(changed)
        changed = deepcopy(original)
        changed['analysis']['access_summary']['coverage']['indexed_roots'] = 2
        validate_access_summary(changed['analysis']['access_summary'])
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(changed)

    def test_linked_and_unparsed_counts_reconcile_even_when_summary_is_valid(self) -> None:
        changed = report(COMPLETE)
        coverage = changed['analysis']['access_summary']['coverage']
        coverage['bound_by_role']['read'] -= 1
        coverage['linked_operands'] -= 1
        coverage['unlinked_operands'] += 1
        validate_access_summary(changed['analysis']['access_summary'])
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(changed)
        two_rungs = COMPLETE.replace(b'</RLLContent>',
            b'<Rung Number="908"><Text>XIC(A);</Text></Rung></RLLContent>')
        changed = report(two_rungs)
        changed['analysis']['access_summary']['coverage']['unparsed_rungs'] = 1
        changed['analysis']['access_summary']['status'] = 'partial'
        changed['analysis']['status'] = changed['status'] = 'partial'
        validate_access_summary(changed['analysis']['access_summary'])
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(changed)

    def test_classified_and_non_data_are_subsets_of_reference_catalogue(self) -> None:
        changed = report(COMPLETE.replace(b'XIC(A)OTE(A);', b'PRIVATE_OP(1);'))
        summary = changed['analysis']['access_summary']
        summary['status'] = 'complete'
        summary['coverage']['instructions_by_status'].update(classified=1, unsupported_instruction=0)
        summary['coverage']['operands_by_role'].update(unknown=0, read=1)
        validate_access_summary(summary)
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(changed)
        changed = report(COMPLETE.replace(b'XIC(A)', b'XIC(1)'))
        summary = changed['analysis']['access_summary']
        summary['coverage']['operands_by_role'].update(read=0, non_data=1)
        validate_access_summary(summary)
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(changed)

    def test_access_partial_controls_analysis_and_work_status(self) -> None:
        payload = report(COMPLETE.replace(b'OTE(A)', b'OTE(1)'))
        self.assertEqual(payload['analysis']['reference_summary']['status'], 'complete')
        self.assertEqual(payload['analysis']['sfc_structure_summary']['status'], 'complete')
        self.assertEqual(payload['analysis']['access_summary']['status'], 'partial')
        self.assertEqual((payload['analysis']['status'], payload['status']), ('partial', 'partial'))
        work_check.validate_work_check_report(payload)
        payload['analysis']['status'] = 'complete'
        payload['status'] = 'passed'
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_access_failure_and_not_run_require_null_summaries(self) -> None:
        original = report(COMPLETE)
        for status in ('failed', 'not_run'):
            payload = deepcopy(original)
            payload['analysis'] = {'status': status, 'failure_code': 'access_error' if status == 'failed' else None,
                'private_run_saved': False, 'reference_summary': None, 'sfc_structure_summary': None, 'access_summary': None}
            payload['status'] = 'failed'
            if status == 'not_run':
                payload['tests']['application'] = work_check.unavailable_result('not_run')
            work_check.validate_work_check_report(payload)
            payload['analysis']['access_summary'] = original['analysis']['access_summary']
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)
        payload = deepcopy(original)
        payload.update(schema_version=12, workflow_version='work-check-12', status='failed')
        payload['analysis'] = {'status': 'failed', 'failure_code': 'access_error', 'private_run_saved': False,
                               'reference_summary': None, 'sfc_structure_summary': None}
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_analyze_captures_once_passes_access_and_sanitizes_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(COMPLETE)
            with patch.object(work_check, 'capture_snapshot', wraps=work_check.capture_snapshot) as capture, \
                    patch.object(work_check, 'analyze_access', wraps=analyze_access) as analyze, \
                    patch.object(work_check, 'save_run') as save:
                result = work_check._analyze(root, source, root, REVISION)
            capture.assert_called_once_with(source)
            analyze.assert_called_once()
            self.assertEqual(save.call_args.kwargs['access'].to_dict(), analyze_access(*analyze.call_args.args).to_dict())
            self.assertEqual(result['access_summary']['status'], 'complete')
            self.assertEqual(save.call_args.args[1].data, COMPLETE)
            with patch.object(work_check, 'analyze_access', side_effect=AccessError('PRIVATE_ERROR')):
                result = work_check._analyze(root, source, root, REVISION)
            self.assertEqual(result['failure_code'], 'access_error')
            self.assertFalse(result['private_run_saved'])
            self.assertIsNone(result['access_summary'])
            self.assertNotIn('PRIVATE_ERROR', json.dumps(result))
            self.assertIn('PRIVATE_ERROR', (root / 'analysis.log').read_text(encoding='utf-8'))

    def test_summary_failure_after_save_exposes_no_partial_summary(self) -> None:
        from plc_workbench.access_summary import AccessSummaryError
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(COMPLETE)
            with patch.object(work_check, 'save_run', return_value=root / 'saved-run'), \
                    patch.object(work_check, 'build_access_summary', side_effect=AccessSummaryError('PRIVATE_SUMMARY')):
                result = work_check._analyze(root, source, root, REVISION)
            self.assertEqual((result['status'], result['failure_code'], result['private_run_saved']),
                             ('failed', 'summary_error', True))
            self.assertTrue(all(result[key] is None for key in
                ('reference_summary', 'sfc_structure_summary', 'access_summary', 'diagnostic_sample')))
            result.pop('diagnostic_sample')
            payload = report(COMPLETE)
            payload.update(analysis=result, status='failed')
            self.assertNotIn('PRIVATE_SUMMARY', work_check.render_work_check_report(payload))


if __name__ == '__main__':
    unittest.main()
