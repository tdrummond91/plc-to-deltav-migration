"""Signal context stays private and preserves historical review artifacts."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import review, review_html
from plc_workbench.signal_context import SignalContextError, analyze_signal_context
from plc_workbench.signal_context_summary import build_signal_context_summary
from plc_workbench.source import capture_snapshot
from plc_workbench.source_reuse import source_reuse_scope
from plc_workbench.storage import StorageError, save_run
from test_execution_context_workflow import (
    captured as old_captured, options as old_options, arguments as old_arguments,
    report as old_report, maximum_width_report as old_maximum,
)
from test_binding_context_workflow import ROOT, source
from test_review_workflow import invoke
from test_unmatched_sample_report import REVISION

DEMO_SOURCE = (ROOT / 'public/fixtures/synthetic/signal_context_demo.L5X').read_bytes()
# Keep canonical-replay tests compact; the larger demo is reserved for paging QA.
SOURCE = b'''<RSLogix5000Content><Controller Name="InventedCompactSignal">
<Description>Invented &lt;img src=x onerror=alert(1)&gt;</Description>
<Tags><Tag Name="A" DataType="BOOL"/><Tag Name="B" DataType="BOOL"/>
<Tag Name="Out" DataType="BOOL"/><Tag Name="Edge" DataType="BOOL"/>
<Tag Name="Value" DataType="REAL"/><Tag Name="Delay" DataType="TIMER"/></Tags>
<Tasks><Task Name="Task" Type="CONTINUOUS"><ScheduledPrograms><ScheduledProgram Name="P"/></ScheduledPrograms></Task></Tasks>
<Programs><Program Name="P" Type="Normal" MainRoutineName="Main"><Routines><Routine Name="Main" Type="RLL">
<RLLContent OnlineEditType="Original"><Rung Number="0" Type="N"><Comment>Invented pump alarm sensor</Comment><Text><![CDATA[XIC(A)[XIO(B)OTE(Out),GRT(Value,12.5)OTL(Out)];]]></Text></Rung>
<Rung Number="1" Type="N"><Text><![CDATA[XIC(A)ONS(Edge)OTU(Out);]]></Text></Rung>
<Rung Number="2" Type="N"><Text><![CDATA[XIC(A)TON(Delay,?,?);]]></Text></Rung>
<Rung Number="3" Type="N"><Text><![CDATA[XIC(Delay.DN)OTE(B)MOV(1,Out);]]></Text></Rung>
</RLLContent><RLLContent OnlineEditType="Pending"><Rung Number="0" Type="N"><Text><![CDATA[XIC(Out)OTE(A);]]></Text></Rung></RLLContent>
</Routine></Routines></Program></Programs></Controller></RSLogix5000Content>'''



def context_inputs(parts: tuple) -> tuple:
    return (*parts[:3], parts[4], parts[8], parts[9], parts[10], parts[11],
            parts[5], parts[19], parts[20], parts[23])


@lru_cache(maxsize=6)
def captured(data: bytes = SOURCE) -> tuple:
    with source_reuse_scope():
        parts = old_captured(data)
        return (*parts, analyze_signal_context(*context_inputs(parts)))


def options(parts: tuple) -> dict:
    return old_options(parts) | {'signal_context': parts[24]}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {'signal_context': parts[24]}


@lru_cache(maxsize=6)
def _report(data: bytes) -> dict:
    with source_reuse_scope():
        payload = old_report(data)
        parts = captured(data)
        payload.update(schema_version=40, workflow_version='work-check-40')
        payload['analysis']['signal_context_summary'] = build_signal_context_summary(
            *context_inputs(parts), parts[24], revision=REVISION)
        if parts[24].status == 'partial':
            payload['analysis']['status'] = payload['status'] = 'partial'
        return payload


def report(data: bytes = SOURCE) -> dict:
    return deepcopy(_report(data))


def maximum_width_report() -> dict:
    """Conservative byte probe; simultaneous maxima need not be feasible."""
    payload = old_maximum()
    payload.update(schema_version=40, workflow_version='work-check-40')
    def grow(value):
        if type(value) is int:
            return 10**12
        if type(value) is dict:
            return {key: grow(child) for key, child in value.items()}
        return value
    payload['analysis']['signal_context_summary'] = grow(report()['analysis']['signal_context_summary'])
    return payload


class SignalContextWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = source_reuse_scope()
        self.scope.__enter__()
        self.addCleanup(self.scope.__exit__, None, None, None)

    def test_review22_manifest25_preserve_old_evidence_and_sixteen_artifacts(self) -> None:
        parts = captured()
        old = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual((current['schema_version'], current['report_version']), (22, 'engineering-review-22'))
        self.assertEqual(current['signal_context'], parts[24].to_dict())
        for key in old.keys() - {'schema_version', 'report_version', 'status'}:
            self.assertEqual(current[key], old[key], key)
        review.validate_review_data(*parts[:4], current, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = save_run(root, *parts[:2], **old_arguments(parts))
            prior = {p.name: p.read_bytes() for p in before.iterdir()}
            after = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((after / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (25, 16))
            self.assertEqual(manifest['review_schema_version'], 22)
            self.assertEqual(manifest['signal_context_analyzer_version'], 'signal-context-1')
            self.assertNotIn('signal-context.json', manifest['artifacts'])
            for name, content in prior.items():
                self.assertEqual((before / name).read_bytes(), content)
                if name not in {'manifest.json', 'review.html'}:
                    self.assertEqual((after / name).read_bytes(), content, name)

    def test_complete_preceding_chain_is_required_before_allocation(self) -> None:
        parts = captured(source('NOP();'))
        for key in old_options(parts):
            with self.subTest(key=key):
                with self.assertRaises(review.ReviewError):
                    review.build_review_data(*parts[:4], **(options(parts) | {key: None}))
                with tempfile.TemporaryDirectory() as folder:
                    destination = Path(folder) / 'unallocated'
                    with self.assertRaises(StorageError):
                        save_run(destination, *parts[:2], **(arguments(parts) | {key: None}))
                    self.assertFalse(destination.exists())
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'unallocated'
            with self.assertRaises(StorageError):
                save_run(destination, *parts[:2], **(arguments(parts) | {'include_review': False}))
            self.assertFalse(destination.exists())

    def test_forged_companion_and_review_are_canonically_rejected(self) -> None:
        parts = captured()
        for field in ('outputs', 'addresses', 'condition_reads', 'rung_contexts'):
            self.assertTrue(getattr(parts[24], field), field)
            forged = replace(parts[24], **{field: []})
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'unallocated'
                with self.assertRaises(StorageError) as error:
                    save_run(destination, *parts[:2], **(arguments(parts) | {'signal_context': forged}))
                self.assertEqual(error.exception.code, 'review_validation_error')
                self.assertFalse(destination.exists())
        current = review.build_review_data(*parts[:4], **options(parts))
        current['signal_context']['outputs'][0]['opcode'] = 'FORGED_PRIVATE_SENTINEL'
        with self.assertRaises(review.ReviewError) as error:
            review.validate_review_data(*parts[:4], current, **options(parts))
        self.assertNotIn('FORGED_PRIVATE_SENTINEL', str(error.exception))

    def test_review22_limits_preserve_review21_and_prevent_allocation(self) -> None:
        parts = captured(source('NOP();'))
        old = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual(review.MAX_REVIEW_V22_BYTES, 328 * 1024 * 1024)
        self.assertEqual(review_html._limits(22), (328 * 1024 * 1024, 360 * 1024 * 1024))
        self.assertEqual(review_html._limits(21), (296 * 1024 * 1024, 328 * 1024 * 1024))
        with patch.object(review, 'MAX_REVIEW_V22_BYTES', 1), tempfile.TemporaryDirectory() as folder:
            review.render_review_json(old)
            destination = Path(folder) / 'unallocated'
            with self.assertRaises(StorageError) as error:
                save_run(destination, *parts[:2], **arguments(parts))
            self.assertEqual(error.exception.code, 'review_size_limit')
            self.assertFalse(destination.exists())
        for key in ('MAX_REVIEW_V22_PAYLOAD_BYTES', 'MAX_REVIEW_V22_HTML_BYTES'):
            with patch.object(review_html, key, 1):
                review_html.render_review_html(old)
                with self.assertRaises(review_html.ReviewHtmlSizeLimitError):
                    review_html.render_review_html(current)

    def test_html_is_offline_escaped_paginated_and_has_closed_version_gates(self) -> None:
        parts = captured()
        current = review.build_review_data(*parts[:4], **options(parts))
        rendered = review_html.render_review_html(current)
        for text in ('PAGE_SIZE = 50', 'Signal relationships', 'Signal output guard dossiers',
                     'Relationship traversal truncated', "connect-src 'none'", 'textContent'):
            self.assertIn(text, rendered)
        self.assertNotIn('.innerHTML', rendered)
        self.assertNotIn('<img src=x onerror=alert(1)>', rendered)
        self.assertIn('\\u003cimg src=x onerror=alert(1)\\u003e', rendered)
        for mutate in (lambda d: d.update(signal_context=None),
                       lambda d: d['signal_context'].update(schema_version=True),
                       lambda d: d['signal_context'].update(analyzer_version='signal-context-2'),
                       lambda d: d.update(execution_context=None),
                       lambda d: d.update(schema_version=21, report_version='engineering-review-21')):
            bad = deepcopy(current)
            mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(review_html.ReviewHtmlError):
                review_html.render_review_html(bad)
        old = review.build_review_data(*parts[:4], **old_options(parts))
        old['signal_context'] = current['signal_context']
        with self.assertRaises(review_html.ReviewHtmlError):
            review_html.render_review_html(old)

    def test_cli_captures_once_saves_latest_and_retains_partial_status(self) -> None:
        data = source('XIC(A)JSR(Missing,0);')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'invented.L5X'
            path.write_bytes(data)
            def capture_then_replace(filename):
                captured_source = capture_snapshot(filename)
                path.write_bytes(b'changed live source')
                return captured_source
            with patch('plc_workbench.source.capture_snapshot', side_effect=capture_then_replace) as capture, \
                    patch('plc_workbench.storage.save_run', wraps=save_run) as save:
                code, output, error = invoke(['review', str(path), '--workspace', str(root / 'runs')])
            capture.assert_called_once_with(path)
            save.assert_called_once()
            self.assertEqual(save.call_args.args[1].data, data)
            from test_signal_candidates_workflow import captured as latest_captured
            self.assertEqual(save.call_args.kwargs['signal_context'], latest_captured(data)[24])
            self.assertEqual((code, error), (3, ''))
            saved, = (root / 'runs').iterdir()
            self.assertEqual((saved / 'snapshot.L5X').read_bytes(), data)
            manifest = json.loads((saved / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], manifest['status']), (38, 'partial'))
            from test_engineering_assemblies_workflow import captured as latest_captured, options as latest_options
            from test_engineering_assemblies_rack_workflow import captured as current_captured, options as current_options
            current_parts = current_captured(data)
            expected = review.build_review_data(*current_parts[:4], **current_options(current_parts))
            self.assertEqual((saved / 'review.html').read_bytes(), review_html.render_review_html(expected).encode())

    def test_cli_signal_failure_is_source_free_and_allocates_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'invented.L5X'
            path.write_bytes(source('NOP();'))
            with patch('plc_workbench.signal_context.analyze_signal_context',
                       side_effect=SignalContextError('PRIVATE_SENTINEL')):
                code, output, error = invoke(['review', str(path), '--workspace', str(root / 'failed')])
            self.assertEqual(code, 1)
            self.assertIn('Cannot analyze signal context', error)
            self.assertNotIn('PRIVATE_SENTINEL', output + error)
            self.assertFalse((root / 'failed').exists())

    def test_invented_fixture_exercises_pagination_and_unresolved_context(self) -> None:
        context = captured(DEMO_SOURCE)[24]
        self.assertGreater(len(context.outputs), 50)
        self.assertGreater(len(context.addresses), 50)
        self.assertEqual(context.status, 'partial')
        self.assertTrue(any(row['has_stateful'] for row in context.outputs))
        self.assertTrue(any(row['stateful_associations'] for row in context.addresses))
        self.assertTrue(any(row['noncoil_writer_operand_ids'] for row in context.addresses))
        self.assertEqual({row['opcode'] for row in context.outputs}, {'OTE', 'OTL', 'OTU'})
        self.assertTrue({'xic', 'xio', 'comparison', 'ons_storage'} <= {row['kind'] for row in context.condition_reads})
        self.assertTrue({'literal', 'unbound'} <= {row['status'] for row in context.condition_reads})
        self.assertEqual({row['content_attributes']['OnlineEditType'] for row in context.rung_contexts}, {'Original', 'Pending'})


if __name__ == '__main__':
    unittest.main()
