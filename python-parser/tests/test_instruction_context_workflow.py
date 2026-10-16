"""Private context companions preserve earlier evidence and public boundaries."""
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

from plc_workbench import review, review_html, work_check
from plc_workbench.custom_instruction_context import analyze_custom_instruction_context
from plc_workbench.custom_instruction_summary import build_custom_instruction_summary
from plc_workbench.indexed_access import analyze_indexed_access
from plc_workbench.indexed_access_summary import build_indexed_access_summary
from plc_workbench.storage import StorageError, save_run
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from plc_workbench.targeted_sample_history import sample_envelope
from test_binding_context_workflow import (
    captured as old_captured, options as old_options, arguments as old_arguments,
    report as old_report, source,
)
from test_targeted_sample_workflow import record
from test_unmatched_sample_report import REVISION


SOURCE = source('INVENTED_CUSTOM(A)MOV(A[INDEX+7],A);').replace(
    b'</Controller>', b'''<AddOnInstructionDefinitions>
    <AddOnInstructionDefinition Name="INVENTED_CUSTOM"><Parameters>
    <Parameter Name="INVENTED_PARAMETER" DataType="DINT" Usage="Input" Required="true"/>
    </Parameters><Routines><Routine Name="INVENTED_LOGIC" Type="RLL"><RLLContent>
    <Rung Number="0"><Text>NOP();</Text></Rung></RLLContent></Routine></Routines>
    </AddOnInstructionDefinition></AddOnInstructionDefinitions></Controller>''')


def companion_inputs(parts: tuple) -> tuple:
    return (*parts[:3], parts[4], parts[8], parts[9], parts[10], parts[11], parts[12])


@lru_cache(maxsize=4)
def captured(data: bytes = SOURCE) -> tuple:
    parts = old_captured(data)
    inputs = companion_inputs(parts)
    return (*parts, analyze_custom_instruction_context(*inputs), analyze_indexed_access(*inputs))


def options(parts: tuple) -> dict:
    return old_options(parts) | {'custom_instruction_context': parts[13], 'indexed_access': parts[14]}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'custom_instruction_context': parts[13], 'indexed_access': parts[14]}


def report(data: bytes = SOURCE) -> dict:
    payload = old_report(data)
    parts = captured(data)
    inputs = companion_inputs(parts)
    payload.update(schema_version=29, workflow_version='work-check-29', diagnostic_sample=None,
                   targeted_samples=sample_envelope('replayed', record()))
    payload['analysis'].update(
        custom_instruction_summary=build_custom_instruction_summary(*inputs, parts[13], revision=REVISION),
        indexed_access_summary=build_indexed_access_summary(*inputs, parts[14], revision=REVISION))
    if 'partial' in (parts[13].status, parts[14].status):
        payload['analysis']['status'] = payload['status'] = 'partial'
    return payload


class InstructionContextWorkflowTests(unittest.TestCase):
    def test_review12_manifest15_add_context_without_changing_other_artifacts(self) -> None:
        parts = captured()
        previous = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual(current['schema_version'], 12)
        self.assertEqual(current['custom_instruction_context'], parts[13].to_dict())
        self.assertEqual(current['indexed_access'], parts[14].to_dict())
        for key in previous.keys() - {'schema_version', 'report_version', 'status'}:
            self.assertEqual(current[key], previous[key], key)
        review.validate_review_data(*parts[:4], current, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = save_run(root, *parts[:2], **old_arguments(parts))
            before = {p.name: p.read_bytes() for p in old.iterdir()}
            new = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((new / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (15, 16))
            self.assertEqual((manifest['review_schema_version'], manifest['review_version']), (12, 'engineering-review-12'))
            for name in ('custom_instruction_context', 'indexed_access'):
                self.assertEqual(manifest[name + '_schema_version'], 1)
                self.assertEqual(manifest[name + '_analyzer_version'], current[name]['analyzer_version'])
            for name, content in before.items():
                self.assertEqual((old / name).read_bytes(), content)
                if name not in {'manifest.json', 'review.json', 'review.html'}:
                    self.assertEqual((new / name).read_bytes(), content, name)

    def test_review_requires_both_canonical_companions_and_binding_context(self) -> None:
        parts = captured()
        for key in ('custom_instruction_context', 'indexed_access', 'binding_context'):
            args = options(parts)
            args[key] = None
            with self.subTest(missing=key), self.assertRaises(review.ReviewError):
                review.build_review_data(*parts[:4], **args)
        for index, key in ((13, 'custom_instruction_context'), (14, 'indexed_access')):
            forged = deepcopy(parts[index])
            forged.coverage['source_operands'] += 1
            with self.assertRaises(review.ReviewError):
                review.build_review_data(*parts[:4], **(options(parts) | {key: forged}))
        current = review.build_review_data(*parts[:4], **options(parts))
        current['indexed_access']['uses'][0]['role'] = 'read_write'
        with self.assertRaises(review.ReviewError):
            review.validate_review_data(*parts[:4], current, **options(parts))

    def test_new_limits_are_versioned_and_save_fails_before_manifest(self) -> None:
        parts = captured()
        old = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual(review.MAX_REVIEW_V12_BYTES, 184 * 1024 * 1024)
        self.assertEqual(review_html._limits(12), (184 * 1024 * 1024, 216 * 1024 * 1024))
        self.assertEqual(review_html._limits(11), (168 * 1024 * 1024, 200 * 1024 * 1024))
        with patch.object(review, 'MAX_REVIEW_V12_BYTES', 1):
            review.render_review_json(old)
            with self.assertRaises(review.ReviewSizeLimitError):
                review.render_review_json(current)
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(StorageError) as caught:
                    save_run(Path(folder), *parts[:2], **arguments(parts))
                self.assertEqual(caught.exception.code, 'review_size_limit')
                self.assertEqual(list(Path(folder).rglob('manifest.json')), [])
        for constant in ('MAX_REVIEW_V12_PAYLOAD_BYTES', 'MAX_REVIEW_V12_HTML_BYTES'):
            with patch.object(review_html, constant, 1):
                review_html.render_review_html(old)
                with self.assertRaises(review_html.ReviewHtmlSizeLimitError):
                    review_html.render_review_html(current)

    def test_work29_preserves_eleven_summaries_and_replays_historical_record(self) -> None:
        payload, previous = report(), old_report(SOURCE)
        work_check.validate_work_check_report(payload)
        for key in previous['analysis']:
            self.assertEqual(payload['analysis'][key], previous['analysis'][key], key)
        self.assertEqual(payload['targeted_samples']['record'], record())
        self.assertNotEqual(payload['targeted_samples']['record']['source_rungs'],
                            payload['analysis']['indexed_access_summary']['coverage']['source_rungs'])
        self.assertEqual(json.loads(work_check.render_work_check_report(payload)), payload)
        for older in (27, 28):
            bad = deepcopy(payload)
            bad.update(schema_version=older, workflow_version=f'work-check-{older}')
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(bad)

    def test_public_counts_reconcile_across_companions_and_reject_extra_source_fields(self) -> None:
        for name in ('custom_instruction_summary', 'indexed_access_summary'):
            for change in (
                lambda s: s['coverage'].__setitem__('source_rungs', s['coverage']['source_rungs'] + 1),
                lambda s: s['coverage'].__setitem__('source_operands', s['coverage']['source_operands'] + 1),
                lambda s: s['tool_revision'].update(commit='f' * 40),
                lambda s: s.update(source_name='INVENTED_PRIVATE'),
            ):
                bad = report()
                change(bad['analysis'][name])
                with self.subTest(name=name), self.assertRaises(ValueError):
                    work_check.validate_work_check_report(bad)
        bad = report()
        counts = bad['analysis']['custom_instruction_summary']['coverage']
        counts['unknown_family_calls'] += 1
        counts['calls_by_status']['unique_candidate'] += 1
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(bad)
        bad = report()
        bad['analysis']['indexed_access_summary']['coverage']['source_aliases'] += 1
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(bad)
        encoded = json.dumps(report()['analysis'])
        for text in ('INVENTED_CUSTOM', 'INVENTED_PARAMETER', 'INVENTED_LOGIC', 'A[INDEX+7]'):
            self.assertNotIn(text, encoded)

    def test_failure_envelopes_require_null_new_summaries(self) -> None:
        from test_save_diagnostics import failed_report
        for code in ('custom_instruction_context_error', 'indexed_access_error'):
            payload = failed_report(27)
            payload.update(schema_version=29, workflow_version='work-check-29', targeted_samples=sample_envelope())
            payload['analysis'].update(failure_code=code, custom_instruction_summary=None, indexed_access_summary=None)
            work_check.validate_work_check_report(payload)
            payload['analysis']['indexed_access_summary'] = report()['analysis']['indexed_access_summary']
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)

    def test_public_counts_cannot_omit_known_dynamic_gaps_or_parameter_declarations(self) -> None:
        from plc_workbench.indexed_access_summary import validate_indexed_access_summary
        from plc_workbench.custom_instruction_summary import validate_custom_instruction_summary
        payload = report()
        summary = payload['analysis']['indexed_access_summary']
        for key, value in summary['coverage'].items():
            if key.startswith('source_') or key == 'expression_uses':
                continue
            summary['coverage'][key] = dict.fromkeys(value, 0) if type(value) is dict else 0
        summary['status'] = 'complete'
        validate_indexed_access_summary(summary)
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)
        payload = report()
        summary = payload['analysis']['custom_instruction_summary']
        summary['coverage']['parameters_total'] = 0
        for key in ('parameter_usage', 'parameter_required', 'parameter_visible', 'parameter_datatype'):
            summary['coverage'][key] = dict.fromkeys(summary['coverage'][key], 0)
        validate_custom_instruction_summary(summary)
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_analysis_saves_new_companions_without_resampling(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            path = root / 'invented.L5X'
            path.write_bytes(SOURCE)
            reservation = root / 'confidential/work-check-samples/rung-cases-1.json'
            reservation.parent.mkdir(parents=True)
            reservation.write_text(json.dumps(record()), encoding='utf-8')
            with patch.object(work_check, 'build_targeted_samples', side_effect=AssertionError('No new examples.')):
                result = work_check._analyze(root, path, root, REVISION)
            self.assertIsNone(result['failure_code'])
            self.assertTrue(result['private_run_saved'])
            self.assertEqual(result.pop('targeted_samples'), sample_envelope('replayed', record()))
            self.assertIsNone(result.pop('diagnostic_sample'))
            from test_pid_connection_workflow import report as latest_report
            self.assertEqual(result, latest_report(SOURCE)['analysis'])

    def test_publication_retains_64k_cap_and_does_not_accept_private_context(self) -> None:
        current = report()
        self.assertEqual(work_check._report_limit(29), 64 * 1024)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            path = root / 'feedback.json'
            publish_summary(path, work_check.render_work_check_report(current), input_path=root / 'invented.L5X')
            self.assertEqual(json.loads(path.read_bytes()), current)
            with self.assertRaises(SummaryOutputError):
                publish_summary(root / 'oversized.json', json.dumps(current) + ' ' * 65536, input_path=root / 'invented.L5X')
            private = captured()[14].to_dict()
            with self.assertRaises(SummaryOutputError):
                publish_summary(root / 'private.json', json.dumps(private), input_path=root / 'invented.L5X')

    def test_html_context_shapes_and_safe_static_navigation(self) -> None:
        parts = captured()
        data = review.build_review_data(*parts[:4], **options(parts))
        rendered = review_html.render_review_html(data)
        for label in ('Instruction & index context', 'Symbolic index read occurrences',
                      'Custom parameter declarations', 'Custom routine declarations',
                      'Inspect symbolic index context', 'Custom instruction occurrences'):
            self.assertIn(label, rendered)
        self.assertIn("connect-src 'none'", rendered)
        self.assertNotIn('.innerHTML', rendered)
        for key in ('custom_instruction_context', 'indexed_access'):
            bad = deepcopy(data)
            bad[key]['schema_version'] = True
            with self.assertRaises(review_html.ReviewHtmlError):
                review_html.render_review_html(bad)
        previous = review.build_review_data(*parts[:4], **old_options(parts))
        previous['indexed_access'] = data['indexed_access']
        with self.assertRaises(review_html.ReviewHtmlError):
            review_html.render_review_html(previous)


if __name__ == '__main__':
    unittest.main()
