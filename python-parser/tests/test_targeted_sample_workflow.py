"""Current sampling is separate from unchanged private analysis and summaries."""
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

from plc_workbench import work_check
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from plc_workbench.targeted_sample_history import sample_envelope
from plc_workbench.targeted_samples import build_targeted_samples
from test_binding_context_workflow import captured, report as old_report, source
from test_unmatched_sample_report import REVISION


def sample_source(count: int = 150, *, reverse: bool = False) -> bytes:
    body = source('MOV(A[INDEX],A);')
    padding = ''.join(f'<Rung Number="{i}"><Text>NOP();</Text></Rung>' for i in range(1, count)).encode()
    return body.replace(b'<RLLContent>', b'<RLLContent>' + padding) if reverse else body.replace(
        b'</RLLContent>', padding + b'</RLLContent>')


@lru_cache(maxsize=8)
def _record(count: int = 150) -> dict:
    parts = captured(sample_source(count))
    return build_targeted_samples(*parts[:3], parts[4], parts[8], parts[9], parts[10], parts[11], parts[12])


def record(count: int = 150) -> dict:
    return deepcopy(_record(count))


@lru_cache(maxsize=8)
def _report(count: int = 150) -> dict:
    payload = old_report(sample_source(count))
    payload.update(schema_version=28, workflow_version='work-check-28', diagnostic_sample=None,
                   targeted_samples=sample_envelope('selected', record(count)))
    return payload


def report(count: int = 150) -> dict:
    return deepcopy(_report(count))


class TargetedSampleWorkflowTests(unittest.TestCase):
    def test_work28_round_trip_preserves_eleven_summaries_and_freezes_old_versions(self) -> None:
        current, previous = report(), old_report(sample_source())
        self.assertEqual(current['analysis'], previous['analysis'])
        self.assertEqual(json.loads(work_check.render_work_check_report(current)), current)
        work_check.validate_work_check_report(previous)
        for payload in (dict(current, schema_version=27, workflow_version='work-check-27'),
                        dict(previous, schema_version=28, workflow_version='work-check-28')):
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)

    def test_selected_population_is_current_replay_is_explicitly_historical(self) -> None:
        payload = report()
        payload['targeted_samples'] = sample_envelope('selected', record(151))
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)
        payload['targeted_samples']['status'] = 'replayed'
        work_check.validate_work_check_report(payload)

    def test_envelope_is_closed_and_current_raw_sampler_cannot_rotate(self) -> None:
        changes = [lambda p: p['targeted_samples'].update(private='SECRET'),
                   lambda p: p['targeted_samples'].update(status='fresh'),
                   lambda p: p['targeted_samples'].update(reason='SECRET'),
                   lambda p: p['targeted_samples'].update(schema_version=True),
                   lambda p: p.update(targeted_samples=sample_envelope()),
                   lambda p: p.update(diagnostic_sample={'kind': 'direct_malformed_operand',
                                                        'opcode': 'MOV', 'argument_index': 0, 'raw_text': 'SECRET?'})]
        for change in changes:
            payload = report()
            change(payload)
            with self.subTest(change=change), self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)

    def test_selected_case_claims_cannot_contradict_current_aggregate_populations(self) -> None:
        payload = report()
        # Two claimed dynamic occurrences cannot fit the single observed gap.
        claimed = record()
        claimed['cases'][1].update(status='budget_exhausted', sample_id=None)
        payload['targeted_samples'] = sample_envelope('selected', claimed)
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)
        payload['targeted_samples']['status'] = 'replayed'
        work_check.validate_work_check_report(payload)

    def test_expression_dynamic_gaps_do_not_require_ordinary_operand_slots(self) -> None:
        data = sample_source(200).replace(b'MOV(A[INDEX],A);', b'CPT(A,A[INDEX]+A[INDEX])ONS(A);')
        parts = captured(data)
        selected = build_targeted_samples(*parts[:3], parts[4], parts[8], parts[9], parts[10], parts[11], parts[12])
        payload = old_report(data)
        payload.update(schema_version=28, workflow_version='work-check-28', diagnostic_sample=None,
                       targeted_samples=sample_envelope('selected', selected))
        counts = payload['analysis']['binding_context_summary']['coverage']
        self.assertEqual((counts['gaps_by_category']['non_static_array_index'], counts['expression_binding_gaps']), (2, 2))
        self.assertEqual([case['status'] for case in selected['cases'][:2]], ['not_found', 'not_found'])
        self.assertEqual(selected['cases'][3]['status'], 'included')
        work_check.validate_work_check_report(payload)

    def test_unavailable_samples_do_not_change_normal_analysis_status(self) -> None:
        for reason in ('history_error', 'selection_error'):
            payload = report()
            payload['targeted_samples'] = sample_envelope('unavailable', reason=reason)
            work_check.validate_work_check_report(payload)
            self.assertEqual(payload['analysis'], report()['analysis'])

    def test_failed_analysis_and_tests_require_not_run_without_record(self) -> None:
        from test_save_diagnostics import failed_report
        payload = failed_report(27)
        payload.update(schema_version=28, workflow_version='work-check-28', targeted_samples=sample_envelope())
        work_check.validate_work_check_report(payload)
        for status in ('selected', 'replayed', 'unavailable'):
            bad = deepcopy(payload)
            bad['targeted_samples'] = sample_envelope(status, record() if status != 'unavailable' else None)
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)
        payload['analysis'].update(status='not_run', failure_code=None)
        payload['tests']['application'] = work_check.unavailable_result('not_run')
        work_check.validate_work_check_report(payload)

    def test_publication_uses_current64k_only_and_keeps_legacy_limits(self) -> None:
        self.assertEqual(work_check.MAX_REPORT_V28_BYTES, 64 * 1024)
        self.assertEqual(work_check.MAX_REPORT_V22_BYTES, 48 * 1024)
        current, previous = report(), old_report(sample_source())
        with patch.object(work_check, 'MAX_REPORT_V28_BYTES', 1):
            work_check.render_work_check_report(previous)
            with self.assertRaises(ValueError):
                work_check.render_work_check_report(current)
        with patch.object(work_check, 'MAX_REPORT_V22_BYTES', 1):
            work_check.render_work_check_report(current)
            with self.assertRaises(ValueError):
                work_check.render_work_check_report(previous)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            rendered = work_check.render_work_check_report(current)
            publish_summary(root / 'current.json', rendered, input_path=root / 'invented.L5X')
            self.assertEqual(json.loads((root / 'current.json').read_bytes()), current)
            for value, limit in ((current, 64 * 1024), (previous, 48 * 1024)):
                padded = json.dumps(value)
                padded += ' ' * (limit + 1 - len(padded))
                with self.assertRaises(SummaryOutputError):
                    publish_summary(root / 'oversized.json', padded, input_path=root / 'invented.L5X')
            self.assertFalse((root / 'oversized.json').exists())

    def test_analyze_selects_after_private_save_then_replays_after_source_change(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            path = root / 'invented.L5X'
            path.write_bytes(sample_source())
            with patch.object(work_check, 'build_diagnostic_sample', side_effect=AssertionError('Legacy sampler must not run.')):
                first = work_check._analyze(root, path, root, REVISION)
                self.assertIsNone(first['failure_code'])
                self.assertEqual(first['targeted_samples']['status'], 'selected')
                path.write_bytes(sample_source(151, reverse=True))
                with patch.object(work_check, 'build_targeted_samples', side_effect=AssertionError('Do not resample.')):
                    second = work_check._analyze(root, path, root, REVISION)
            self.assertEqual(second['targeted_samples']['status'], 'replayed')
            self.assertEqual(second['targeted_samples']['record'], first['targeted_samples']['record'])
            self.assertEqual(second['binding_context_summary']['coverage']['source_rungs'], 151)
            self.assertEqual(len(list((root / 'confidential/workspaces/work-check').iterdir())), 2)
            self.assertIsNone(second['diagnostic_sample'])

    def test_sampling_failure_preserves_saved_run_and_all_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            path = root / 'invented.L5X'
            path.write_bytes(sample_source())
            with patch.object(work_check, 'build_targeted_samples', side_effect=ValueError('PRIVATE_FAILURE')):
                result = work_check._analyze(root, path, root, REVISION)
            self.assertIsNone(result['failure_code'])
            self.assertTrue(result['private_run_saved'])
            self.assertEqual(result['targeted_samples'], sample_envelope('unavailable', reason='selection_error'))
            self.assertNotIn('PRIVATE_FAILURE', json.dumps(result))
            result.pop('diagnostic_sample')
            result.pop('targeted_samples')
            result.pop('custom_instruction_summary')
            result.pop('indexed_access_summary')
            result.pop('sfr_summary')
            result.pop('aoi_body_summary')
            result.pop('pid_connection_summary')
            result.pop('calculation_path_summary')
            result.pop('output_context_summary')
            self.assertEqual(result.pop('condition_summary')['schema_version'], 3)
            self.assertEqual(result, {k: v for k, v in report()['analysis'].items() if k != 'condition_summary'})

    def test_publication_failure_keeps_reservation_and_retry_does_not_rotate(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            path = root / 'invented.L5X'
            path.write_bytes(sample_source())
            results = report()['tests']['application']
            with patch.object(work_check, '_branch', return_value='feat/test-pc'), \
                    patch.object(work_check, '_git', return_value=REVISION['commit']) as git, \
                    patch.object(work_check, '_check_pinned'), \
                    patch.object(work_check, '_source_path', return_value=path), \
                    patch.object(work_check, '_private_logs', return_value=root), \
                    patch.object(work_check, '_run_suite', return_value=results), \
                    patch('plc_workbench.summary_output.publish_summary', side_effect=SummaryOutputError('Publication failed.')):
                with self.assertRaises(SummaryOutputError):
                    work_check.run_check(root, None)
                reservation = root / 'confidential/work-check-samples/rung-cases-1.json'
                before = reservation.read_bytes()
                path.write_bytes(sample_source(151, reverse=True))
                with patch.object(work_check, 'build_targeted_samples', side_effect=AssertionError('Do not rotate.')):
                    with self.assertRaises(SummaryOutputError):
                        work_check.run_check(root, None)
                self.assertEqual(reservation.read_bytes(), before)
                self.assertTrue(all(call.args[1:] == ('rev-parse', 'HEAD') for call in git.call_args_list))
                self.assertFalse((root / 'public').exists())


if __name__ == '__main__':
    unittest.main()
