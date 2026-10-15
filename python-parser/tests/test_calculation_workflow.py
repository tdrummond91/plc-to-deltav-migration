"""Additive CPT review and sharing contracts from invented snapshots only."""
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
from plc_workbench.calculations import CalculationError, analyze_calculations
from plc_workbench.calculation_summary import CalculationSummaryError, validate_calculation_summary
from plc_workbench.review import ReviewError, build_review_data, render_review_json, validate_review_data
from plc_workbench.review_html import ReviewHtmlError, render_review_html
from plc_workbench.storage import StorageError, _write_artifact, save_run

from test_pid_member_workflow import DATA as PID_DATA, ROOT, arguments as member_arguments, captured as member_captured
from test_review_html import ParsedPage
from test_review_workflow import invoke
from test_unmatched_sample_report import REVISION, report


DATA = PID_DATA.replace(b'PID(A,1,0,A,0,0,0);', b'CPT(A.SP,A.SP+937291);')


def captured(data: bytes = DATA):
    parts = member_captured(data)
    return (*parts, analyze_calculations(*parts[:3]))


def arguments(parts: tuple) -> dict:
    return member_arguments(parts) | {'calculations': parts[8]}


def options(parts: tuple) -> dict:
    return {key: arguments(parts)[key] for key in ('access', 'tag_data', 'pid', 'pid_members', 'calculations')}


class CalculationReviewStorageTests(unittest.TestCase):
    def test_review6_manifest9_hash_thirteen_artifacts_and_preserve_all_old_companions(self) -> None:
        parts = captured()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            old = save_run(workspace, *parts[:2], **member_arguments(parts))
            old_files = {path.name: path.read_bytes() for path in old.iterdir()}
            old_manifest = json.loads(old_files['manifest.json'])
            self.assertEqual((old_manifest['schema_version'], old_manifest['review_schema_version']), (8, 5))
            self.assertNotIn('calculations.json', old_files)
            self.assertFalse(any(key.startswith('calculation_') for key in old_manifest))
            old_payload = json.loads(ParsedPage(old_files['review.html'].decode()).scripts[0][1])
            self.assertNotIn('calculations', old_payload)
            saved = save_run(workspace, *parts[:2], **arguments(parts))
            manifest = json.loads((saved / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], manifest['artifact_kind']),
                             (9, 'source_reference_sfc_access_tag_data_pid_member_calculation_review_run'))
            self.assertEqual((manifest['review_schema_version'], manifest['review_version']), (6, 'engineering-review-6'))
            self.assertEqual((manifest['calculation_schema_version'], manifest['calculation_analyzer_version']),
                             (1, 'calculation-evidence-1'))
            self.assertEqual(len(manifest['artifacts']), 13)
            private = json.loads((saved / 'calculations.json').read_bytes())
            self.assertEqual(private, parts[8].to_dict())
            payload = json.loads(ParsedPage((saved / 'review.html').read_text(encoding='utf-8')).scripts[0][1])
            self.assertEqual(payload['calculations'], private)
            for key in old_payload.keys() - {'schema_version', 'report_version', 'analysis_scope', 'status'}:
                self.assertEqual(payload[key], old_payload[key])
            validate_review_data(*parts[:4], payload, **options(parts))
            for name, details in manifest['artifacts'].items():
                content = (saved / name).read_bytes()
                self.assertEqual(details, {'sha256': hashlib.sha256(content).hexdigest(), 'size_bytes': len(content)})
                if name in old_files and name != 'review.html':
                    self.assertEqual(content, old_files[name])
            self.assertEqual({path.name: path.read_bytes() for path in old.iterdir()}, old_files)

    def test_dependencies_foreign_forged_and_cyclic_calculations_fail_before_allocation(self) -> None:
        parts = captured()
        full = arguments(parts)
        foreign = captured(DATA.replace(b'937291', b'937292'))[-1]
        forged = deepcopy(parts[-1])
        forged.coverage['nodes_total'] += 1
        cycle = deepcopy(parts[-1])
        cycle.coverage['private_extra'] = cycle.coverage
        variants = [dict(calculations=parts[-1]), dict(full, include_review=False), dict(full, pid_members=None),
                    dict(full, pid=None), dict(full, tag_data=None), dict(full, access=None),
                    dict(full, references=None), dict(full, sfc_structure=None), dict(full, calculations=foreign),
                    dict(full, calculations=forged), dict(full, calculations=cycle),
                    dict(full, calculations=replace(parts[-1], schema_version=True))]
        with tempfile.TemporaryDirectory() as directory:
            for index, kwargs in enumerate(variants):
                workspace = Path(directory) / str(index)
                with self.subTest(index=index), self.assertRaises(StorageError):
                    save_run(workspace, *parts[:2], **kwargs)
                self.assertFalse(workspace.exists())
        payload = build_review_data(*parts[:4], **options(parts))
        payload['calculations']['coverage']['nodes_total'] += 1
        with self.assertRaises(ReviewError):
            validate_review_data(*parts[:4], payload, **options(parts))

    def test_html_all_version_pairs_and_companion_presence_are_strict(self) -> None:
        parts = captured()
        all_options = options(parts)
        for version in range(1, 7):
            kwargs = {key: all_options[key] for key in tuple(all_options)[:version - 1]}
            original = build_review_data(*parts[:4], **kwargs)
            mutations = [lambda p: p.update(schema_version=True),
                         lambda p: p.update(report_version='engineering-review-0')]
            for companion, minimum in (('access', 2), ('tag_data', 3), ('pid', 4),
                                       ('pid_members', 5), ('calculations', 6)):
                if version >= minimum:
                    mutations.extend((lambda p, key=companion: p.pop(key),
                                      lambda p, key=companion: p.update({key: None})))
                else:
                    mutations.append(lambda p, key=companion: p.update({key: {}}))
            for mutate in mutations:
                candidate = deepcopy(original)
                mutate(candidate)
                with self.subTest(version=version, mutate=mutate), self.assertRaises(ReviewHtmlError):
                    render_review_html(candidate)

    def test_review6_retains_budgets_and_rejects_before_allocating(self) -> None:
        parts = captured()
        data = build_review_data(*parts[:4], **options(parts))
        exact = len(render_review_json(data).encode('utf-8'))
        with patch('plc_workbench.review.MAX_REVIEW_BYTES', 1):
            with patch('plc_workbench.review.MAX_REVIEW_V3_BYTES', exact):
                self.assertEqual(build_review_data(*parts[:4], **options(parts)), data)
            with patch('plc_workbench.review.MAX_REVIEW_V3_BYTES', exact - 1), self.assertRaises(ReviewError):
                build_review_data(*parts[:4], **options(parts))
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

    def test_render_failure_precedes_allocation_and_write_failure_never_finalizes(self) -> None:
        parts = captured()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / 'not-created'
            with patch('plc_workbench.calculations.render_calculation_json', side_effect=CalculationError('PRIVATE_FAILURE')):
                with self.assertRaises(StorageError) as raised:
                    save_run(workspace, *parts[:2], **arguments(parts))
            self.assertNotIn('PRIVATE_FAILURE', str(raised.exception))
            self.assertFalse(workspace.exists())

            def fail(destination, run_dir, name, data):
                if name == 'calculations.json':
                    raise OSError('PRIVATE_DISK_DETAIL')
                return _write_artifact(destination, run_dir, name, data)

            with patch('plc_workbench.storage._write_artifact', side_effect=fail), self.assertRaises(StorageError):
                save_run(workspace, *parts[:2], **arguments(parts))
            saved, = workspace.iterdir()
            self.assertFalse((saved / 'manifest.json').exists())

    def test_cli_captures_once_and_sanitizes_calculation_failure(self) -> None:
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
                    patch('plc_workbench.calculations.analyze_calculations', wraps=analyze_calculations) as analyze:
                code, output, error = invoke(['review', str(source), '--workspace', str(workspace)])
            capture.assert_called_once_with(source)
            analyze.assert_called_once()
            self.assertEqual((code, error), (3, ''))
            saved, = workspace.iterdir()
            self.assertIn(str(saved / 'review.html'), output)
            self.assertEqual((saved / 'snapshot.L5X').read_bytes(), DATA)
            self.assertEqual(json.loads((saved / 'calculations.json').read_bytes()), captured()[-1].to_dict())
            source.write_bytes(DATA)
            with patch('plc_workbench.calculations.analyze_calculations', side_effect=CalculationError('PRIVATE_FAILURE')):
                code, output, error = invoke(['review', str(source), '--workspace', str(Path(directory) / 'failed')])
            self.assertEqual((code, output), (1, ''))
            self.assertNotIn('PRIVATE_FAILURE', error)
            self.assertFalse((Path(directory) / 'failed').exists())


class CalculationWorkReportTests(unittest.TestCase):
    def test_latest_return_has_room_for_a_count_only_calculation_summary(self) -> None:
        # Sizing uses invented expression nodes scaled to the returned CPT
        # population. This does not assert the unseen source syntax is parsed.
        returned = json.loads((ROOT / 'public/inspection/work-check-20261015T140634Z-ec36ce0b.json').read_bytes())
        summary = report(DATA)['analysis']['calculation_summary']
        reference = returned['analysis']['reference_summary']
        population = reference['source_summary']['instructions']['counts']['CPT']
        for key, value in summary['coverage'].items():
            if isinstance(value, dict):
                summary['coverage'][key] = {name: count * population for name, count in value.items()}
            else:
                summary['coverage'][key] *= population
        summary['coverage'].update(
            source_rungs=reference['coverage']['rungs_total'],
            unparsed_rungs=reference['coverage']['rungs_total'] - reference['coverage']['rungs_analyzed'],
            source_instructions=reference['coverage']['instructions_total'],
            source_operands=reference['operands']['total'])
        summary['tool_revision'] = deepcopy(returned['tool_revision'])
        validate_calculation_summary(summary)
        returned.update(schema_version=18, workflow_version='work-check-18')
        returned['analysis']['calculation_summary'] = summary
        rendered = work_check.render_work_check_report(returned)
        self.assertLess(len(rendered.encode('utf-8')), work_check.MAX_REPORT_BYTES)

    def test_work18_is_count_only_and_all_historical_reports_remain_frozen(self) -> None:
        payload = report(DATA)
        self.assertEqual((payload['schema_version'], payload['workflow_version']), (18, 'work-check-18'))
        self.assertEqual(payload['analysis']['calculation_summary']['schema_version'], 1)
        rendered = work_check.render_work_check_report(payload)
        self.assertEqual(json.loads(rendered), payload)
        self.assertLess(len(rendered.encode()), 32 * 1024)
        for private in ('PRIVATE_', '937291', 'snapshot', 'instruction_id', 'owner_id', 'raw_text'):
            self.assertNotIn(private, rendered)
        paths = [path for path in (ROOT / 'public/inspection').glob('work-check-*.json')
                 if json.loads(path.read_bytes())['schema_version'] <= 17]
        self.assertTrue(paths)
        for path in paths:
            before = path.read_bytes()
            historical = json.loads(before)
            self.assertLessEqual(historical['schema_version'], 17)
            self.assertEqual(json.loads(work_check.render_work_check_report(historical)), historical)
            for mutate in (lambda p: p.update(schema_version=18, workflow_version='work-check-18'),
                           lambda p: p['analysis'].update(calculation_summary=payload['analysis']['calculation_summary']),
                           lambda p: p['analysis'].update(calculation_summary=None)):
                changed = deepcopy(historical)
                mutate(changed)
                with self.subTest(path=path.name, mutate=mutate), self.assertRaises(ValueError):
                    work_check.validate_work_check_report(changed)
            self.assertEqual(path.read_bytes(), before)

    def test_summary_presence_revision_versions_and_closed_keys(self) -> None:
        for mutate in (lambda p: p['analysis'].pop('calculation_summary'),
                       lambda p: p['analysis'].update(calculation_summary=None),
                       lambda p: p['analysis']['calculation_summary']['tool_revision'].update(commit='b' * 40),
                       lambda p: p['analysis']['calculation_summary'].update(schema_version=True),
                       lambda p: p['analysis']['calculation_summary'].update(schema_version=2),
                       lambda p: p['analysis']['calculation_summary'].update(private='PRIVATE'),
                       lambda p: p['analysis'].update(private='PRIVATE')):
            candidate = report(DATA)
            mutate(candidate)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)

    def test_source_counts_and_cpt_population_cannot_be_transplanted(self) -> None:
        empty = DATA.replace(b'CPT(A.SP,A.SP+937291);', b'XIC(A)OTE(A);')
        second = DATA.replace(b'CPT(A.SP,A.SP+937291);', b'CPT(A.SP,A.SP+937291)CPT(A.SP,1);')
        for target, donor in ((DATA, empty), (empty, DATA), (DATA, second)):
            candidate = report(target)
            candidate['analysis']['calculation_summary'] = report(donor)['analysis']['calculation_summary']
            validate_calculation_summary(candidate['analysis']['calculation_summary'])
            with self.subTest(target=target == empty, donor=donor == second), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        # Legacy operands remain entire expression strings. Additional lexical
        # leaves may exceed legacy operand counts without becoming new operands.
        repeats = DATA.replace(b'A.SP+937291', b'+'.join([b'A.SP'] * 12))
        candidate = report(repeats)
        coverage = candidate['analysis']['calculation_summary']['coverage']
        self.assertGreater(coverage['reference_occurrences'], candidate['analysis']['reference_summary']['operands']['total'])
        work_check.validate_work_check_report(candidate)
        lowercase = report(DATA.replace(b'CPT(', b'cpt('))
        work_check.validate_work_check_report(lowercase)
        self.assertEqual(lowercase['analysis']['calculation_summary']['coverage']['occurrences_total'], 1)

    def test_source_totals_and_opcode_counts_are_checked_independently(self) -> None:
        for field in ('source_rungs', 'source_instructions', 'source_operands'):
            candidate = report(DATA)
            candidate['analysis']['calculation_summary']['coverage'][field] += 1
            validate_calculation_summary(candidate['analysis']['calculation_summary'])
            with self.subTest(field=field), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        # Equal instruction and operand totals cannot mask a missing CPT.
        other = DATA.replace(b'CPT(A.SP,A.SP+937291);', b'MOV(A.SP,A.SP);')
        candidate = report(other)
        candidate['analysis']['calculation_summary'] = report(DATA)['analysis']['calculation_summary']
        validate_calculation_summary(candidate['analysis']['calculation_summary'])
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)

    def test_status_and_recognized_destination_root_capacity_are_reconciled(self) -> None:
        candidate = report(DATA)
        candidate['analysis']['status'] = 'complete'
        candidate['status'] = 'passed'
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)
        unbound = DATA.replace(b'CPT(A.SP,A.SP+937291);', b'CPT(MISSING,937291);')
        candidate = report(unbound)
        donor = report(DATA.replace(b'CPT(A.SP,A.SP+937291);', b'CPT(A.SP,937291);'))
        candidate['analysis']['calculation_summary'] = donor['analysis']['calculation_summary']
        validate_calculation_summary(candidate['analysis']['calculation_summary'])
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)

    def test_failure_and_not_run_require_null_summaries_and_error_is_versioned(self) -> None:
        original = report(DATA)
        for state in ('failed', 'not_run'):
            candidate = deepcopy(original)
            candidate['analysis'] = {'status': state, 'failure_code': 'calculation_error' if state == 'failed' else None,
                'private_run_saved': False, **{key: None for key in original['analysis'] if key.endswith('_summary')}}
            candidate.update(status='failed', diagnostic_sample=None)
            if state == 'not_run':
                candidate['tests']['application'] = work_check.unavailable_result('not_run')
            work_check.validate_work_check_report(candidate)
            candidate['analysis']['calculation_summary'] = original['analysis']['calculation_summary']
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        candidate = deepcopy(original)
        candidate.update(schema_version=17, workflow_version='work-check-17', status='failed', diagnostic_sample=None)
        candidate['analysis'] = {'status': 'failed', 'failure_code': 'calculation_error', 'private_run_saved': False,
            **{key: None for key in original['analysis'] if key.endswith('_summary') and key != 'calculation_summary'}}
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)

    def test_runner_captures_calculations_once_and_sanitizes_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(DATA)
            with patch.object(work_check, 'capture_snapshot', wraps=work_check.capture_snapshot) as capture, \
                    patch.object(work_check, 'analyze_calculations', wraps=analyze_calculations) as analyze, \
                    patch.object(work_check, 'save_run') as save:
                outcome = work_check._analyze(root, source, root, REVISION)
            capture.assert_called_once_with(source)
            analyze.assert_called_once()
            self.assertEqual(save.call_args.args[1].data, DATA)
            self.assertEqual(save.call_args.kwargs['calculations'].to_dict(), captured()[-1].to_dict())
            self.assertIsNotNone(outcome['calculation_summary'])
            for target, error, expected, saved in (
                ('analyze_calculations', CalculationError('PRIVATE_FAILURE'), 'calculation_error', False),
                ('build_calculation_summary', CalculationSummaryError('PRIVATE_FAILURE'), 'summary_error', True),
            ):
                with patch.object(work_check, target, side_effect=error), patch.object(work_check, 'save_run'):
                    outcome = work_check._analyze(root, source, root, REVISION)
                self.assertEqual((outcome['failure_code'], outcome['private_run_saved']), (expected, saved))
                for key in ('reference_summary', 'sfc_structure_summary', 'access_summary',
                            'tag_data_summary', 'pid_summary', 'pid_member_summary', 'calculation_summary'):
                    self.assertIsNone(outcome[key])
                self.assertNotIn('PRIVATE_FAILURE', json.dumps(outcome))
                self.assertIn('PRIVATE_FAILURE', (root / 'analysis.log').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
