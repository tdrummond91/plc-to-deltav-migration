"""Derived binding context is private, canonical, and separate from bindings."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import work_check
from plc_workbench.binding_context import BindingContextError, analyze_binding_context
from plc_workbench.binding_context_summary import build_binding_context_summary, validate_binding_context_summary
from plc_workbench.review import ReviewError, build_review_data, validate_review_data
from plc_workbench.review_html import ReviewHtmlError, render_review_html
from plc_workbench.storage import StorageError, save_run
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from test_condition_workflow import (
    ROOT, arguments as old_arguments, captured as old_captured,
    options as old_options, report as old_report,
)
from test_rack_candidates import LOCAL, card, controller, tag
from test_review_workflow import invoke
from test_unmatched_sample_report import REVISION


def source(text: str = 'XIC(IN)OTE(OUT)MOV(A[INDEX],A)CPT(A,MISSING+1);',
           *, modules: str | None = None) -> bytes:
    tags = tag('A') + tag('INDEX') + tag('IN', 'Local:3:I.Data.0') + tag('OUT', 'Local:3:O.Data.1')
    body = controller(LOCAL + card() if modules is None else modules, text, tags)
    return f'<RSLogix5000Content>{body}</RSLogix5000Content>'.encode()


SOURCE = source()


def captured(data: bytes = SOURCE) -> tuple:
    parts = old_captured(data, schema_version=2)
    context = analyze_binding_context(*parts[:3], parts[4], parts[8], parts[9], parts[10], parts[11])
    return (*parts, context)


def options(parts: tuple) -> dict:
    return old_options(parts) | {'binding_context': parts[12]}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'binding_context': parts[12]}


def report(data: bytes = SOURCE) -> dict:
    payload = old_report(data, schema_version=26)
    parts = captured(data)
    summary = build_binding_context_summary(
        *parts[:3], parts[4], parts[8], parts[9], parts[10], parts[11], parts[12], revision=REVISION)
    payload.update(schema_version=27, workflow_version='work-check-27')
    payload['analysis']['binding_context_summary'] = summary
    if summary['status'] == 'partial':
        payload['analysis']['status'] = payload['status'] = 'partial'
    return payload


class BindingContextWorkflowTests(unittest.TestCase):
    def test_review11_manifest14_embed_context_without_an_extra_artifact(self) -> None:
        parts = captured()
        data = build_review_data(*parts[:4], **options(parts))
        self.assertEqual((data['schema_version'], data['report_version']), (11, 'engineering-review-11'))
        self.assertEqual(data['binding_context'], parts[-1].to_dict())
        validate_review_data(*parts[:4], data, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            previous = save_run(root, *parts[:2], **old_arguments(parts))
            before = {path.name: path.read_bytes() for path in previous.iterdir()}
            current = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((current / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (14, 16))
            self.assertEqual((manifest['review_schema_version'], manifest['review_version']), (11, 'engineering-review-11'))
            self.assertEqual((manifest['binding_context_schema_version'], manifest['binding_context_analyzer_version']),
                             (1, 'binding-context-1'))
            self.assertEqual((current / 'review.html').read_bytes(), render_review_html(data).encode())
            self.assertFalse((current / 'binding-context.json').exists())
            for name, details in manifest['artifacts'].items():
                value = (current / name).read_bytes()
                self.assertEqual(details, {'size_bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()})
                if name != 'review.html':
                    self.assertEqual(value, before[name])
            self.assertEqual(before, {path.name: path.read_bytes() for path in previous.iterdir()})

    def test_missing_old_foreign_and_mutated_companions_fail_before_allocation(self) -> None:
        parts = captured()
        forged = deepcopy(parts[-1])
        forged.coverage['source_rungs'] += 1
        foreign = captured(SOURCE.replace(b'MISSING+1', b'MISSING+2'))[-1]
        boolean = deepcopy(parts[-1])
        object.__setattr__(boolean, 'schema_version', True)
        cases = [dict(options(parts), **{key: None}) for key in old_options(parts)]
        cases.extend(dict(options(parts), binding_context=value) for value in (forged, foreign, boolean))
        legacy_conditions = old_captured(SOURCE, schema_version=1)[11]
        cases.append(dict(options(parts), conditions=legacy_conditions))
        for kwargs in cases:
            with self.subTest(keys=tuple(kwargs)), self.assertRaises(ReviewError):
                build_review_data(*parts[:4], **kwargs)
            with tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'absent'
                with self.assertRaises(StorageError):
                    save_run(destination, *parts[:2], **(old_arguments(parts) | kwargs))
                self.assertFalse(destination.exists())
        data = build_review_data(*parts[:4], **options(parts))
        data['binding_context']['coverage']['source_operands'] += 1
        with self.assertRaises(ReviewError):
            validate_review_data(*parts[:4], data, **options(parts))

    def test_foreign_container_hooks_are_not_called_or_serialized(self) -> None:
        parts = captured()

        class HookDict(dict):
            def items(self):
                raise AssertionError('Caller hooks must never run.')

        forged = deepcopy(parts[-1])
        object.__setattr__(forged, 'coverage', HookDict(forged.coverage))
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'absent'
            with patch.object(type(forged), 'to_dict', side_effect=AssertionError('Do not serialize foreign evidence.')):
                with self.assertRaises(StorageError):
                    save_run(destination, *parts[:2], **dict(arguments(parts), binding_context=forged))
            self.assertFalse(destination.exists())

    def test_versioned_review_budget_and_html_companion_are_closed(self) -> None:
        from plc_workbench import review
        parts = captured()
        current = build_review_data(*parts[:4], **options(parts))
        previous = build_review_data(*parts[:4], **old_options(parts))
        self.assertEqual(review.MAX_REVIEW_V11_BYTES, 168 * 1024 * 1024)
        for restricted, accepted, rejected in (('MAX_REVIEW_V11_BYTES', previous, current),
                                              ('MAX_REVIEW_V10_BYTES', current, previous)):
            with patch.object(review, restricted, 1):
                review.render_review_json(accepted)
                with self.assertRaises(review.ReviewSizeLimitError):
                    review.render_review_json(rejected)
        for mutate in (lambda p: p.pop('binding_context'), lambda p: p.update(binding_context=None),
                       lambda p: p.update(schema_version=10, report_version='engineering-review-10')):
            bad = deepcopy(current)
            mutate(bad)
            with self.assertRaises(ReviewHtmlError):
                render_review_html(bad)
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'absent'
            with patch.object(review, 'MAX_REVIEW_V11_BYTES', 1), self.assertRaises(StorageError) as caught:
                save_run(destination, *parts[:2], **arguments(parts))
            self.assertEqual(caught.exception.code, 'review_size_limit')
            self.assertFalse(destination.exists())

    def test_cli_and_work_runner_use_the_same_context_without_external_processes(self) -> None:
        parts = captured()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            input_path = root / 'invented.L5X'
            input_path.write_bytes(SOURCE)
            with patch('subprocess.Popen', side_effect=AssertionError('No external processes.')):
                code, output, error = invoke(['review', str(input_path), '--workspace', str(root / 'runs')])
                self.assertEqual((code, error), (3, ''))
                saved, = (root / 'runs').iterdir()
                self.assertIn(str(saved / 'review.html'), output)
                from test_output_context_workflow import captured as latest_captured, options as latest_options
                latest = latest_captured(SOURCE)
                data = build_review_data(*latest[:4], **latest_options(latest))
                self.assertEqual((saved / 'review.html').read_bytes(), render_review_html(data).encode())
                with patch.object(work_check, 'save_run', return_value=root / 'saved') as save:
                    outcome = work_check._analyze(root, input_path, root, REVISION)
                self.assertIsNone(outcome['failure_code'])
                self.assertEqual(save.call_args.kwargs['binding_context'].to_dict(), parts[-1].to_dict())
                outcome.pop('diagnostic_sample')
                outcome.pop('targeted_samples', None)
                outcome.pop('custom_instruction_summary')
                outcome.pop('indexed_access_summary')
                outcome.pop('sfr_summary')
                outcome.pop('aoi_body_summary')
                outcome.pop('pid_connection_summary')
                outcome.pop('calculation_path_summary')
                outcome.pop('output_context_summary')
                self.assertEqual(outcome.pop('condition_summary')['schema_version'], 3)
                self.assertEqual(outcome, {k: v for k, v in report()['analysis'].items() if k != 'condition_summary'})

    def test_context_failures_are_fixed_and_do_not_publish_private_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            input_path = root / 'invented.L5X'
            input_path.write_bytes(SOURCE)
            with patch('plc_workbench.binding_context.analyze_binding_context', side_effect=BindingContextError('PRIVATE_FAILURE')):
                code, output, error = invoke(['review', str(input_path), '--workspace', str(root / 'failed')])
            self.assertEqual((code, output), (1, ''))
            self.assertNotIn('PRIVATE_FAILURE', error)
            self.assertFalse((root / 'failed').exists())
            with patch.object(work_check, 'analyze_binding_context', side_effect=BindingContextError('PRIVATE_FAILURE')):
                failure = work_check._analyze(root, input_path, root, REVISION)
            self.assertEqual((failure['failure_code'], failure['private_run_saved']), ('binding_context_error', False))
            self.assertTrue(all(value is None for key, value in failure.items() if key.endswith('_summary')))
            self.assertNotIn('PRIVATE_FAILURE', json.dumps(failure))
            self.assertIn('PRIVATE_FAILURE', (root / 'analysis.log').read_text())


class BindingContextWorkReportTests(unittest.TestCase):
    def test_work27_requires_context_and_preserves_all_ten_earlier_summaries(self) -> None:
        current, previous = report(), old_report(SOURCE, schema_version=26)
        for key, value in previous['analysis'].items():
            self.assertEqual(current['analysis'][key], value)
        self.assertEqual(json.loads(work_check.render_work_check_report(current)), current)
        for bad in (dict(current, schema_version=26, workflow_version='work-check-26'),
                    dict(previous, schema_version=27, workflow_version='work-check-27')):
            with self.assertRaises(work_check.WorkCheckError):
                work_check.validate_work_check_report(bad)
        for mutate in (lambda p: p['analysis'].update(binding_context_summary=None),
                       lambda p: p['analysis']['binding_context_summary']['tool_revision'].update(commit='b' * 40),
                       lambda p: p['analysis']['binding_context_summary'].update(schema_version=True),
                       lambda p: p['analysis']['binding_context_summary'].update(private='PRIVATE')):
            bad = deepcopy(current)
            mutate(bad)
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)

    def test_context_failure_code_and_null_summary_are_version_specific(self) -> None:
        from test_save_diagnostics import failed_report
        work_check.validate_work_check_report(failed_report(27, 'binding_context_error'))
        for version in range(1, 27):
            with self.subTest(version=version), self.assertRaises(work_check.WorkCheckError):
                work_check.validate_work_check_report(failed_report(version, 'binding_context_error'))
        bad = failed_report(27, 'binding_context_error')
        bad['analysis']['binding_context_summary'] = report()['analysis']['binding_context_summary']
        with self.assertRaises(work_check.WorkCheckError):
            work_check.validate_work_check_report(bad)

    def test_foreign_context_populations_cannot_contradict_authenticated_companions(self) -> None:
        for target, donor in ((source('XIC(A)OTE(A);'), SOURCE),
                              (source('XIC(A[INDEX])OTE(A);'), source('XIC(IN)OTE(A);')),
                              (source('XIC(A[INDEX])OTE(A);'), source('XIC(IN.Member)OTE(A);')),
                              (source('XIC(IN)OTE(A);'), source('XIC(A)OTE(OUT);'))):
            bad = report(target)
            summary = report(donor)['analysis']['binding_context_summary']
            validate_binding_context_summary(summary)
            bad['analysis']['binding_context_summary'] = summary
            with self.subTest(target=target[-100:], donor=donor[-100:]), self.assertRaises(work_check.WorkCheckError):
                work_check.validate_work_check_report(bad)

    def test_publication_is_count_only_bounded_and_history_is_unchanged(self) -> None:
        current = report()
        rendered = work_check.render_work_check_report(current)
        for private in ('candidate_id', 'source_id', 'alias_chain', 'terminal_root', 'snapshot', 'Local:3:I', 'MISSING+1'):
            self.assertNotIn(private, rendered)
        for path in (ROOT / 'public/inspection').glob('work-check-*.json'):
            before = path.read_bytes()
            payload = json.loads(before)
            self.assertEqual(json.loads(work_check.render_work_check_report(payload)), payload)
            self.assertEqual(path.read_bytes(), before)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch('subprocess.Popen', side_effect=AssertionError('No external processes.')):
                padded = rendered + ' ' * max(0, 33 * 1024 - len(rendered))
                publish_summary(root / 'accepted.json', padded, input_path=root / 'source.L5X')
            self.assertEqual((root / 'accepted.json').read_bytes(), rendered.encode())
            with self.assertRaises(SummaryOutputError):
                publish_summary(root / 'oversized.json', rendered + ' ' * (49 * 1024), input_path=root / 'source.L5X')
            self.assertFalse((root / 'oversized.json').exists())

    def test_candidate_direction_requires_a_declared_root_but_allows_many_members(self) -> None:
        modules = LOCAL + card(children='<InAliasTag/>')
        current = report(source('XIC(IN)OTE(A);', modules=modules))
        directions = current['analysis']['binding_context_summary']['coverage']['candidate_address_directions']
        self.assertEqual(directions, {'input': 1, 'output': 0})
        bad = deepcopy(current)
        summary = bad['analysis']['binding_context_summary']
        summary['coverage']['candidate_address_directions'].update(input=0, output=1)
        validate_binding_context_summary(summary)
        with self.assertRaises(work_check.WorkCheckError):
            work_check.validate_work_check_report(bad)
        multiple = report(source('XIC(Local:3:I.Data.0)XIC(Local:3:I.Data.1)OTE(A);', modules=modules))
        self.assertEqual(multiple['analysis']['binding_context_summary']['coverage']['candidate_address_directions']['input'], 2)
        self.assertEqual(multiple['analysis']['reference_summary']['rack_candidates']['declarations']['by_direction']['input'], 1)
        work_check.validate_work_check_report(multiple)


if __name__ == '__main__':
    unittest.main()
