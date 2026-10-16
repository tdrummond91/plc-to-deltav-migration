"""Local boolean-condition evidence stays private; only closed counts cross publication."""
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
from plc_workbench.conditions import ConditionError, analyze_conditions, render_conditions_json
from plc_workbench.condition_summary import build_condition_summary, validate_condition_summary
from plc_workbench.review import ReviewError, build_review_data, validate_review_data
from plc_workbench.review_html import ReviewHtmlError, render_review_html
from plc_workbench.storage import StorageError, _write_artifact, save_run
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from test_access_workflow import ROOT, ladder
from test_cpt_access_workflow import report as access_report
from test_relationship_workflow import (arguments as old_arguments, captured as old_captured,
                                        options as old_options, report as old_report)
from test_review_workflow import invoke
from test_unmatched_sample_report import REVISION

SOURCE = ladder('XIC(A)[XIO(A),EQU(A,937291)]OTE(A)OTL(A)OTU(A);')


def captured(data: bytes = SOURCE, *, schema_version: int = 1) -> tuple:
    parts = old_captured(data)
    return (*parts, analyze_conditions(*parts[:3], parts[4], parts[8], parts[9], parts[10],
                                      schema_version=schema_version))


def options(parts: tuple) -> dict:
    return old_options(parts) | {'conditions': parts[11]}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'conditions': parts[11]}


def report(data: bytes = SOURCE, *, schema_version: int = 24) -> dict:
    payload = old_report(data)
    parts = captured(data, schema_version=2 if schema_version >= 26 else 1)
    summary = build_condition_summary(*parts[:3], parts[4], parts[8], parts[9], parts[10], parts[11], revision=REVISION)
    payload.update(schema_version=schema_version, workflow_version=f'work-check-{schema_version}')
    payload['analysis']['condition_summary'] = summary
    if summary['status'] == 'partial':
        payload['analysis']['status'] = payload['status'] = 'partial'
    return payload


class ConditionWorkflowTests(unittest.TestCase):
    def test_review9_and_manifest12_hash_sixteen_artifacts_and_preserve_older_evidence(self) -> None:
        parts = captured()
        data = build_review_data(*parts[:4], **options(parts))
        self.assertEqual((data['schema_version'], data['report_version']), (9, 'engineering-review-9'))
        self.assertEqual(data['conditions'], parts[-1].to_dict())
        validate_review_data(*parts[:4], data, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            previous = save_run(Path(folder), *parts[:2], **old_arguments(parts))
            previous_bytes = {path.name: path.read_bytes() for path in previous.iterdir()}
            saved = save_run(Path(folder), *parts[:2], **arguments(parts))
            manifest = json.loads((saved / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (12, 16))
            self.assertEqual((manifest['review_schema_version'], manifest['review_version']), (9, 'engineering-review-9'))
            self.assertEqual((manifest['condition_schema_version'], manifest['condition_analyzer_version']),
                             (1, 'condition-analysis-1'))
            self.assertEqual((saved / 'boolean-conditions.json').read_bytes(), render_conditions_json(parts[-1]).encode())
            for name, details in manifest['artifacts'].items():
                value = (saved / name).read_bytes()
                self.assertEqual(details, {'size_bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()})
                if name not in {'boolean-conditions.json', 'review.html'}:
                    self.assertEqual(value, previous_bytes[name])
            self.assertEqual(previous_bytes, {path.name: path.read_bytes() for path in previous.iterdir()})

    def test_forged_foreign_missing_and_old_companions_fail_before_allocation(self) -> None:
        parts = captured()
        forged = deepcopy(parts[-1])
        forged.coverage['source_rungs'] += 1
        foreign = captured(SOURCE.replace(b'937291', b'937292'))[-1]
        boolean_version = deepcopy(parts[-1])
        object.__setattr__(boolean_version, 'schema_version', True)
        cases = [dict(options(parts), **{key: None}) for key in old_options(parts)]
        cases.extend(dict(options(parts), conditions=value) for value in (forged, foreign, boolean_version))
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
        payload['conditions']['coverage']['source_rungs'] += 1
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
                    save_run(workspace, *parts[:2], **dict(arguments(parts), conditions=forged))
            self.assertFalse(workspace.exists())

    def test_versions_and_optional_html_companion_are_strict(self) -> None:
        parts = captured()
        current = build_review_data(*parts[:4], **options(parts))
        self.assertIn('review-data', render_review_html(current))
        for mutate in (lambda p: p.pop('conditions'), lambda p: p.update(conditions=None),
                       lambda p: p.update(schema_version=8, report_version='engineering-review-8'),
                       lambda p: p.update(schema_version=9, report_version='engineering-review-8')):
            bad = deepcopy(current)
            mutate(bad)
            with self.assertRaises(ReviewHtmlError):
                render_review_html(bad)
        kwargs = old_options(parts)
        for version in range(1, 9):
            selected = {key: kwargs[key] for key in tuple(kwargs)[:version - 1]}
            if version < 7 and 'access' in selected:
                selected['access'] = analyze_access(*parts[1:3], schema_version=3)
            legacy = build_review_data(*parts[:4], **selected)
            self.assertEqual(legacy['schema_version'], version)
            render_review_html(legacy)
            legacy['conditions'] = {}
            with self.assertRaises(ReviewHtmlError):
                render_review_html(legacy)

    def test_render_and_size_failure_allocate_nothing_write_failure_never_finalizes(self) -> None:
        parts = captured()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            workspace = root / 'render'
            with patch('plc_workbench.conditions.render_conditions_json',
                       side_effect=ConditionError('PRIVATE_FAILURE')), self.assertRaises(StorageError) as raised:
                save_run(workspace, *parts[:2], **arguments(parts))
            self.assertNotIn('PRIVATE_FAILURE', str(raised.exception))
            self.assertFalse(workspace.exists())
            for index, name in enumerate(('review.MAX_REVIEW_V9_BYTES', 'review_html.MAX_REVIEW_V9_PAYLOAD_BYTES',
                                          'review_html.MAX_REVIEW_V9_HTML_BYTES')):
                workspace = root / str(index)
                with patch(f'plc_workbench.{name}', 1), self.assertRaises(StorageError):
                    save_run(workspace, *parts[:2], **arguments(parts))
                self.assertFalse(workspace.exists())

            def fail(destination, run_dir, name, data):
                if name == 'boolean-conditions.json':
                    raise OSError('PRIVATE_DISK_DETAIL')
                return _write_artifact(destination, run_dir, name, data)

            workspace = root / 'write'
            with patch('plc_workbench.storage._write_artifact', side_effect=fail), self.assertRaises(StorageError):
                save_run(workspace, *parts[:2], **arguments(parts))
            saved, = workspace.iterdir()
            self.assertFalse((saved / 'manifest.json').exists())

    def test_cli_and_runner_save_identical_conditions_and_fixed_safe_failures(self) -> None:
        parts = captured(schema_version=2)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(SOURCE)
            code, output, error = invoke(['review', str(source), '--workspace', str(root / 'runs')])
            self.assertEqual((code, error), (0, ''))
            saved, = (root / 'runs').iterdir()
            self.assertIn(str(saved / 'review.html'), output)
            self.assertEqual(json.loads((saved / 'boolean-conditions.json').read_bytes()), parts[-1].to_dict())
            with patch.object(work_check, 'save_run', return_value=root / 'saved') as save:
                outcome = work_check._analyze(root, source, root, REVISION)
            self.assertIsNone(outcome['failure_code'])
            self.assertEqual(save.call_args.kwargs['conditions'].to_dict(), parts[-1].to_dict())
            outcome.pop('diagnostic_sample')
            # Current reports add context without changing this frozen layer.
            outcome.pop('binding_context_summary')
            self.assertEqual(outcome, report(schema_version=26)['analysis'])
            with patch('plc_workbench.conditions.analyze_conditions', side_effect=ConditionError('PRIVATE_FAILURE')):
                code, output, error = invoke(['review', str(source), '--workspace', str(root / 'failed')])
            self.assertEqual((code, output), (1, ''))
            self.assertNotIn('PRIVATE_FAILURE', error)
            self.assertFalse((root / 'failed').exists())
            with patch.object(work_check, 'analyze_conditions', side_effect=ConditionError('PRIVATE_FAILURE')):
                failure = work_check._analyze(root, source, root, REVISION)
            self.assertEqual((failure['failure_code'], failure['private_run_saved']), ('condition_error', False))
            self.assertTrue(all(value is None for key, value in failure.items() if key.endswith('_summary')))
            self.assertNotIn('PRIVATE_FAILURE', json.dumps(failure))
            self.assertIn('PRIVATE_FAILURE', (root / 'analysis.log').read_text())


class ConditionWorkReportTests(unittest.TestCase):
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
        for target, donor in (('XIC(A)OTE(A);', 'XIO(A)OTE(A);'),
                              ('OTE(A);', 'OTL(A);'),
                              ('XIC(A)ote(A);', 'XIO(A)OTL(A);'),
                              ('[XIC(A),]OTE(A);', 'XIC(A)OTE(A);'),
                              ('XIC(MISSING)OTE(A);', 'XIC(A)OTE(MISSING);'),
                              ('OTE(A);', 'OTE(A,A);'),
                              ('XIC(A)OTE(A);', 'MOV(A,A);')):
            bad = report(ladder(target))
            summary = report(ladder(donor))['analysis']['condition_summary']
            validate_condition_summary(summary)
            bad['analysis']['condition_summary'] = summary
            with self.subTest(target=target, donor=donor), self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)

    def test_branched_instruction_bounds_admit_empty_and_mixed_source_shapes(self) -> None:
        for text in (';', '[,];', '[MOV(A,A),];', 'MOV(A,A);', '[XIC(A),]MOV(A,A);',
                     'xic(A)ote(A);', 'XIC(A,A)OTE(A,A);', 'XIC(MISSING)OTE(MISSING);',
                     'XIC(S:FS)OTE(A);', 'OTE(1);'):
            with self.subTest(text=text):
                work_check.validate_work_check_report(report(ladder(text)))
        data = ladder('MOV(A,A);').replace(b'</RLLContent>',
            b'<Rung Number="908" Type="N"><Text>[,];</Text></Rung>'
            b'<Rung Number="909" Type="N"><Text>[MOV(A,A),];</Text></Rung></RLLContent>')
        work_check.validate_work_check_report(report(data))

    def test_parser_analysis_and_publication_require_no_external_processes(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(SOURCE)
            with patch('subprocess.Popen', side_effect=AssertionError('No external processes.')):
                payload = report()
                code, _, error = invoke(['review', str(source), '--workspace', str(root / 'review')])
                self.assertEqual((code, error), (0, ''))
                result = work_check._analyze(root, source, root, REVISION)
                self.assertIsNone(result['failure_code'])
                publish_summary(root / 'public.json', work_check.render_work_check_report(payload),
                                input_path=source)

    def test_closed_versions_and_failure_codes(self) -> None:
        previous, current = old_report(SOURCE), report()
        for bad in (dict(current, schema_version=23, workflow_version='work-check-23'),
                    dict(previous, schema_version=24, workflow_version='work-check-24')):
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)
        for mutate in (lambda p: p['analysis'].update(condition_summary=None),
                       lambda p: p['analysis']['condition_summary']['tool_revision'].update(commit='b' * 40),
                       lambda p: p['analysis']['condition_summary'].update(schema_version=True),
                       lambda p: p['analysis']['condition_summary'].update(private='PRIVATE')):
            bad = deepcopy(current)
            mutate(bad)
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)
        for state in ('failed', 'not_run'):
            failed = deepcopy(current)
            failed['analysis'] = {'status': state, 'failure_code': 'condition_error' if state == 'failed' else None,
                'private_run_saved': False, **{key: None for key in current['analysis'] if key.endswith('_summary')}}
            failed.update(status='failed', diagnostic_sample=None)
            if state == 'not_run':
                failed['tests']['application'] = work_check.unavailable_result('not_run')
            work_check.validate_work_check_report(failed)
            failed['analysis']['condition_summary'] = current['analysis']['condition_summary']
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(failed)
        failed = deepcopy(previous)
        failed['analysis'] = {'status': 'failed', 'failure_code': 'condition_error', 'private_run_saved': False,
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
                                            rendered.replace('"condition-analysis-1"', '"PRIVATE"'))):
                destination = root / f'rejected-{index}.json'
                with self.assertRaises(SummaryOutputError):
                    publish_summary(destination, value, input_path=root / 'source.L5X')
                self.assertFalse(destination.exists())


class ConditionTransferWorkflowTests(unittest.TestCase):
    """New transfers use a separate contract without rewriting older evidence."""

    SOURCE = ladder('XIC(A)[MOV(A,A),ADD(A,1,A)]OTE(A)CPT(A,A+1)ONS(A)OTL(A);')

    def test_review10_manifest13_keep_sixteen_artifacts_and_prior_companions(self) -> None:
        previous_parts = captured(self.SOURCE)
        parts = captured(self.SOURCE, schema_version=2)
        data = build_review_data(*parts[:4], **options(parts))
        self.assertEqual((data['schema_version'], data['report_version']), (10, 'engineering-review-10'))
        self.assertEqual(data['conditions']['schema_version'], 2)
        self.assertEqual(data['conditions']['coverage']['node_kinds']['pass_through'], 3)
        self.assertEqual(data['conditions']['coverage']['nodes_total'], previous_parts[-1].coverage['nodes_total'])
        validate_review_data(*parts[:4], data, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            previous = save_run(root, *previous_parts[:2], **arguments(previous_parts))
            before = {path.name: path.read_bytes() for path in previous.iterdir()}
            current = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((current / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (13, 16))
            self.assertEqual((manifest['review_schema_version'], manifest['review_version']), (10, 'engineering-review-10'))
            self.assertEqual((manifest['condition_schema_version'], manifest['condition_analyzer_version']),
                             (2, 'condition-analysis-2'))
            self.assertEqual((current / 'boolean-conditions.json').read_bytes(), render_conditions_json(parts[-1]).encode())
            for name, details in manifest['artifacts'].items():
                value = (current / name).read_bytes()
                self.assertEqual(details, {'size_bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()})
                if name not in {'boolean-conditions.json', 'review.html'}:
                    self.assertEqual(value, before[name])
            self.assertEqual(before, {path.name: path.read_bytes() for path in previous.iterdir()})

    def test_wrong_version_or_mutated_transfer_cannot_allocate_storage(self) -> None:
        parts = captured(self.SOURCE, schema_version=2)
        for version in (1, 3, True, 2.0):
            forged = deepcopy(parts[-1])
            object.__setattr__(forged, 'schema_version', version)
            with self.subTest(version=version), tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'unallocated'
                with self.assertRaises(StorageError):
                    save_run(destination, *parts[:2], **dict(arguments(parts), conditions=forged))
                self.assertFalse(destination.exists())
        forged = deepcopy(parts[-1])
        transfer = next(node for node in forged.nodes if node['kind'] == 'pass_through')
        transfer['child_ids'] = []
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'unallocated'
            with self.assertRaises(StorageError):
                save_run(destination, *parts[:2], **dict(arguments(parts), conditions=forged))
            self.assertFalse(destination.exists())

    def test_review10_limit_is_independent_of_frozen_review9(self) -> None:
        from plc_workbench import review
        old_parts, parts = captured(self.SOURCE), captured(self.SOURCE, schema_version=2)
        previous = build_review_data(*old_parts[:4], **options(old_parts))
        current = build_review_data(*parts[:4], **options(parts))
        self.assertEqual(review.MAX_REVIEW_V10_BYTES, 160 * 1024 * 1024)
        for restricted, accepted, rejected in (('MAX_REVIEW_V10_BYTES', previous, current),
                                              ('MAX_REVIEW_V9_BYTES', current, previous)):
            with patch.object(review, restricted, 1):
                review.render_review_json(accepted)
                with self.assertRaises(review.ReviewSizeLimitError):
                    review.render_review_json(rejected)
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'unallocated'
            with patch.object(review, 'MAX_REVIEW_V10_BYTES', 1), self.assertRaises(StorageError) as caught:
                save_run(destination, *parts[:2], **arguments(parts))
            self.assertEqual(caught.exception.code, 'review_size_limit')
            self.assertFalse(destination.exists())

    def test_work26_explicitly_requires_condition2_and_older_versions_require_condition1(self) -> None:
        current = report(self.SOURCE, schema_version=26)
        old24 = report(self.SOURCE)
        old25 = report(self.SOURCE, schema_version=25)
        for payload in (current, old24, old25):
            self.assertEqual(json.loads(work_check.render_work_check_report(payload)), payload)
        for original, donor in ((current, old24), (old24, current), (old25, current)):
            bad = deepcopy(original)
            bad['analysis']['condition_summary'] = donor['analysis']['condition_summary']
            with self.assertRaises(work_check.WorkCheckError):
                work_check.validate_work_check_report(bad)
        for key in old24['analysis']:
            if key not in {'condition_summary', 'status'}:
                self.assertEqual(current['analysis'][key], old24['analysis'][key])

    def test_pass_opcodes_share_withheld_allowance_with_predicates_and_coils(self) -> None:
        for target, donor in (('MOV(A,A)XIC(A)OTE(A);', 'ABS(A,A)XIC(A)OTE(A);'),
                              ('mov(A,A)XIC(A)OTE(A);', 'MOV(A,A)xio(A)OTE(A);'),
                              ('mov(A,A)XIC(A)OTE(A);', 'MOV(A,A)XIC(A)otl(A);')):
            bad = report(ladder(target), schema_version=26)
            summary = report(ladder(donor), schema_version=26)['analysis']['condition_summary']
            validate_condition_summary(summary)
            bad['analysis']['condition_summary'] = summary
            with self.subTest(target=target, donor=donor), self.assertRaises(work_check.WorkCheckError):
                work_check.validate_work_check_report(bad)
        # One withheld case variant may legitimately cover one recognized pass.
        work_check.validate_work_check_report(report(ladder('mov(A,A)XIC(A)OTE(A);'), schema_version=26))

    def test_work26_publication_is_aggregate_only_and_uses_bounded_larger_envelope(self) -> None:
        payload = report(self.SOURCE, schema_version=26)
        rendered = work_check.render_work_check_report(payload)
        self.assertIn('passthrough_opcodes', rendered)
        for private in ('child_ids', 'instruction_id', 'target_id', 'operand_ids', 'snapshot', 'A+1'):
            self.assertNotIn(private, rendered)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch('subprocess.Popen', side_effect=AssertionError('No external processes.')):
                padded = rendered + ' ' * max(0, 33 * 1024 - len(rendered))
                publish_summary(root / 'accepted.json', padded, input_path=root / 'source.L5X')
            self.assertEqual((root / 'accepted.json').read_bytes(), rendered.encode())
            with self.assertRaises(SummaryOutputError):
                publish_summary(root / 'oversized.json', rendered + ' ' * (49 * 1024), input_path=root / 'source.L5X')
            self.assertFalse((root / 'oversized.json').exists())


if __name__ == '__main__':
    unittest.main()
