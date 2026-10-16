"""Closed save-stage feedback uses synthetic data and local files, never processes."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import work_check
from plc_workbench.storage import StorageError
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from test_condition_workflow import ROOT, SOURCE, report as condition_report
from test_unmatched_sample_report import REVISION


SAVE_CODES = (
    'review_size_limit', 'review_validation_error', 'review_render_error',
    'save_io_error', 'save_workspace_error',
)


def current_report() -> dict:
    from test_binding_context_workflow import report
    return report(SOURCE)


def failed_report(version: int = 25, code: str = 'save_error') -> dict:
    """Build historical envelopes without pretending failed runs have summaries."""
    fields = {
        'reference_summary': 1, 'sfc_structure_summary': 11, 'access_summary': 13,
        'tag_data_summary': 15, 'pid_summary': 16, 'pid_member_summary': 17,
        'calculation_summary': 18, 'rung_analysis_summary': 22,
        'relationship_summary': 23, 'condition_summary': 24, 'binding_context_summary': 27,
    }
    test_result = {
        'schema_version': 1, 'status': 'passed',
        'counts': {'tests_run': 1, 'failures': 0, 'errors': 0, 'skipped': 0,
                   'expected_failures': 0, 'unexpected_successes': 0},
        'failed_test_ids': [], 'failure_ids_omitted': 0,
    }
    result = {
        'schema_version': version, 'workflow_version': f'work-check-{version}',
        'report_kind': 'l5x_work_machine_check',
        'run_id': '20261015T120000Z-12345678', 'tool_revision': deepcopy(REVISION),
        'status': 'failed',
        'tests': {'application': deepcopy(test_result), 'helpers': deepcopy(test_result)},
        'analysis': {'status': 'failed', 'failure_code': code, 'private_run_saved': False,
                     **{name: None for name, introduced in fields.items() if version >= introduced}},
    }
    if version >= 2:
        result['diagnostic_sample'] = None
    return result


class SaveFailureDiagnosticsTests(unittest.TestCase):
    def analyze(self, root: Path) -> dict:
        source = root / 'invented.L5X'
        source.write_bytes(SOURCE)
        with redirect_stdout(io.StringIO()):
            return work_check._analyze(root, source, root, REVISION)

    def assert_failed(self, result: dict, code: str, *, saved: bool = False) -> None:
        self.assertEqual((result['status'], result['failure_code'], result['private_run_saved']),
                         ('failed', code, saved))
        self.assertIsNone(result['diagnostic_sample'])
        self.assertTrue(all(value is None for key, value in result.items() if key.endswith('_summary')))
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(result))
        payload = failed_report(27)
        payload['analysis'] = {key: value for key, value in result.items() if key not in ('diagnostic_sample', 'targeted_samples')}
        work_check.validate_work_check_report(payload)

    def test_each_exact_storage_code_is_safe_and_messages_stay_in_private_log(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            for code in SAVE_CODES:
                with self.subTest(code=code), patch.object(work_check, 'save_run',
                        side_effect=StorageError('PRIVATE_SENTINEL source path and raw rung', code=code)):
                    self.assert_failed(self.analyze(root), code)
            self.assertIn('PRIVATE_SENTINEL', (root / 'analysis.log').read_text())
            self.assertFalse((root / 'confidential').exists())

    def test_unknown_or_non_native_codes_never_run_hooks_or_escape_as_feedback(self) -> None:
        class HookString(str):
            def __hash__(self):
                raise AssertionError('Do not hash caller subclasses.')

        class HookObject:
            def __hash__(self):
                raise AssertionError('Do not hash caller objects.')

            def __eq__(self, other):
                raise AssertionError('Do not compare caller objects.')

            def __str__(self):
                raise AssertionError('Do not stringify a code.')

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            for code in ('PRIVATE_SENTINEL', 'review_size_limit PRIVATE_SENTINEL', None, 1, True,
                         {}, [], HookString('review_size_limit'), HookObject()):
                failure = StorageError('PRIVATE_SENTINEL')
                failure.code = code
                with patch.object(work_check, 'save_run', side_effect=failure):
                    self.assert_failed(self.analyze(root), 'save_error')
            with patch.object(work_check, 'save_run', side_effect=StorageError('review_size_limit')):
                self.assert_failed(self.analyze(root), 'save_error')
            failure = StorageError('PRIVATE_SENTINEL')
            del failure.code
            with patch.object(work_check, 'save_run', side_effect=failure):
                self.assert_failed(self.analyze(root), 'save_error')

    def test_other_exception_attributes_and_storage_subclasses_are_not_inspected(self) -> None:
        class ForeignError(ValueError):
            @property
            def code(self):
                raise AssertionError('Do not inspect foreign exceptions.')

        class StorageSubclass(StorageError):
            def __getattribute__(self, name):
                if name == 'code':
                    raise AssertionError('Do not inspect subclasses.')
                return super().__getattribute__(name)

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            for failure in (ForeignError('review_size_limit PRIVATE_SENTINEL'),
                            StorageSubclass('PRIVATE_SENTINEL', code='review_size_limit')):
                with patch.object(work_check, 'save_run', side_effect=failure):
                    self.assert_failed(self.analyze(root), 'save_error')

    def test_storage_codes_refine_only_the_save_stage(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            failure = StorageError('PRIVATE_SENTINEL', code='review_size_limit')
            with patch.object(work_check, 'analyze_conditions', side_effect=failure):
                self.assert_failed(self.analyze(root), 'condition_error')
            with patch.object(work_check, 'save_run', return_value=root / 'saved'), \
                    patch.object(work_check, 'build_reference_summary', side_effect=failure):
                self.assert_failed(self.analyze(root), 'summary_error', saved=True)

    def test_checkout_workspace_preflight_has_a_fixed_code_and_never_calls_save(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            workspace = root / 'confidential/workspaces/work-check'
            resolve = Path.resolve

            def changed(path, *args, **kwargs):
                return root / 'elsewhere' if path == workspace else resolve(path, *args, **kwargs)

            with patch.object(Path, 'resolve', changed), patch.object(work_check, 'save_run') as save:
                self.assert_failed(self.analyze(root), 'save_workspace_error')
            save.assert_not_called()

    def test_console_failure_after_save_preserves_saved_status(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with patch.object(work_check, 'save_run', return_value=root / 'saved'), \
                    patch('plc_workbench.work_check.print', create=True,
                          side_effect=BrokenPipeError('PRIVATE_SENTINEL stdout closed')):
                self.assert_failed(self.analyze(root), 'unexpected_error', saved=True)
            self.assertIn('PRIVATE_SENTINEL', (root / 'analysis.log').read_text())

    def test_successful_real_save_has_manifest_and_unchanged_summary_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with patch('subprocess.Popen', side_effect=AssertionError('No external processes.')):
                result = self.analyze(root)
                self.assertIsNone(result['failure_code'])
                self.assertTrue(result['private_run_saved'])
                saved, = (root / 'confidential/workspaces/work-check').iterdir()
                manifest = json.loads((saved / 'manifest.json').read_bytes())
                self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (14, 16))
                result.pop('diagnostic_sample')
                result.pop('targeted_samples', None)
                self.assertEqual(result, current_report()['analysis'])


class SaveFailureReportTests(unittest.TestCase):
    def test_new_codes_require_work25_or_later_older_contracts_stay_closed(self) -> None:
        for version in range(1, 28):
            work_check.validate_work_check_report(failed_report(version))
            for code in SAVE_CODES:
                payload = failed_report(version, code)
                if version >= 25:
                    self.assertEqual(json.loads(work_check.render_work_check_report(payload)), payload)
                else:
                    with self.subTest(version=version, code=code), self.assertRaises(work_check.WorkCheckError):
                        work_check.validate_work_check_report(payload)
        for version in (0, 28, True, 25.0, '25'):
            payload = failed_report()
            payload['schema_version'] = version
            with self.subTest(version=version), self.assertRaises(work_check.WorkCheckError):
                work_check.validate_work_check_report(payload)
        for workflow in ('work-check-24', 'work-check-26', None):
            payload = failed_report()
            payload['workflow_version'] = workflow
            with self.assertRaises(work_check.WorkCheckError):
                work_check.validate_work_check_report(payload)

    def test_new_save_failures_require_passed_tests_unsaved_run_and_null_summaries(self) -> None:
        for code in SAVE_CODES:
            original = failed_report(code=code)
            mutations = [lambda p: p['analysis'].update(private_run_saved=True),
                         lambda p: p['tests'].update(application=work_check.unavailable_result('not_run')),
                         lambda p: p['analysis'].update(status='not_run'),
                         lambda p: p['analysis'].update(status='complete'),
                         lambda p: p['analysis'].update(private_run_saved=0),
                         lambda p: p['analysis'].update(private_exception='PRIVATE_SENTINEL')]
            for name in tuple(original['analysis']):
                if name.endswith('_summary'):
                    mutations.append(lambda p, field=name: p['analysis'].update({field: {}}))
            for mutate in mutations:
                payload = deepcopy(original)
                mutate(payload)
                with self.subTest(code=code), self.assertRaises(work_check.WorkCheckError):
                    work_check.validate_work_check_report(payload)
        for code in ('PRIVATE_SENTINEL', 'review_size_limit\n', None, {}, [], True):
            payload = failed_report()
            payload['analysis']['failure_code'] = code
            with self.assertRaises(work_check.WorkCheckError):
                work_check.validate_work_check_report(payload)

    def test_success_contract_and_native_shapes_remain_strict(self) -> None:
        original = current_report()
        work_check.validate_work_check_report(original)
        self.assertEqual({key: value for key, value in original['analysis'].items() if key != 'binding_context_summary'},
                         condition_report(schema_version=26)['analysis'])
        for mutate in (lambda p: p['analysis'].pop('condition_summary'),
                       lambda p: p['analysis']['condition_summary'].update(schema_version=True),
                       lambda p: p['analysis']['reference_summary'].update(schema_version=11),
                       lambda p: p['analysis']['sfc_structure_summary'].update(schema_version=1),
                       lambda p: p['analysis'].update(failure_code='review_size_limit')):
            payload = deepcopy(original)
            mutate(payload)
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)

        class ForeignDict(dict):
            def keys(self):
                raise AssertionError('Caller mapping hooks must not run.')

        payload = failed_report()
        payload['analysis'] = ForeignDict(payload['analysis'])
        with self.assertRaises(work_check.WorkCheckError):
            work_check.validate_work_check_report(payload)

    def test_history_and_new_success_and_failure_reports_round_trip_unchanged(self) -> None:
        paths = tuple((ROOT / 'public/inspection').glob('work-check-*.json'))
        self.assertGreaterEqual(len(paths), 31)
        for path in paths:
            before = path.read_bytes()
            payload = json.loads(before)
            self.assertEqual(json.loads(work_check.render_work_check_report(payload)), payload)
            self.assertEqual(path.read_bytes(), before)
        for payload in (current_report(), *(failed_report(code=code) for code in SAVE_CODES)):
            self.assertEqual(json.loads(work_check.render_work_check_report(payload)), payload)

    def test_current_cap_matches_work24_without_relaxing_older_envelopes(self) -> None:
        payload = current_report()
        rendered = work_check.render_work_check_report(payload)
        size = len(rendered.encode())
        with patch.object(work_check, 'MAX_REPORT_BYTES', 1), \
                patch.object(work_check, 'MAX_REPORT_V22_BYTES', size):
            for accepted in (payload, condition_report(), failed_report(22), failed_report(23)):
                work_check.render_work_check_report(accepted)
            with self.assertRaises(work_check.WorkCheckError):
                work_check.render_work_check_report(failed_report(21))
        with patch.object(work_check, 'MAX_REPORT_V22_BYTES', size - 1):
            with self.assertRaises(work_check.WorkCheckError):
                work_check.render_work_check_report(payload)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'invented.L5X'
            padded = rendered + ' ' * max(0, 33 * 1024 - len(rendered))
            with patch('subprocess.Popen', side_effect=AssertionError('No external processes.')):
                publish_summary(root / 'current.json', padded, input_path=source)
            self.assertEqual((root / 'current.json').read_bytes(), rendered.encode())
            legacy = work_check.render_work_check_report(failed_report(21))
            for index, rejected in enumerate((legacy + ' ' * (33 * 1024),
                                               rendered + ' ' * (49 * 1024))):
                destination = root / f'rejected-{index}.json'
                with self.assertRaises(SummaryOutputError):
                    publish_summary(destination, rejected, input_path=source)
                self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
