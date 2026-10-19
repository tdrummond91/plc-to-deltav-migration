"""Invented SFC declarations join calls without claiming parameter transfers."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch

from plc_workbench import execution_context as execution
from plc_workbench.execution_context_summary import (
    ExecutionContextSummaryError, build_execution_context_summary,
    render_execution_context_summary, validate_execution_context_summary,
)
from plc_workbench.sfc_structure import analyze_sfc_structure
from test_execution_context import capture_xml, document, program, routine
from test_routine_boundaries import capture_v2


def source(body='', *, calls='JSR(Chart,0);', target=None, extra=''):
    target = routine('Chart', language='SFC', content=f'<SFCContent>{body}</SFCContent>') if target is None else target
    return document(program(routines=routine(text=calls) + target) + extra)


def capture_v3(xml=None):
    parts = capture_xml(source() if xml is None else xml)
    return (*parts[:-1], execution.analyze_execution_context(*parts[:-1], schema_version=3))


class SfcRoutineBoundaryTests(unittest.TestCase):
    def test_schema2_private_and_public_bytes_remain_frozen(self):
        parts = capture_v2()
        for text, size, digest in (
            (execution.render_execution_context_json(parts[-1]), 14843,
             'fdc5cb75a085d2e894ab6f299d40cd1928406484845355a5afed6a3e8f225802'),
            (render_execution_context_summary(build_execution_context_summary(*parts)), 6432,
             '80feff112de4bf307cc8820e6dbd9fe6928811fb89585b2459123f8aac16c4a0'),
        ):
            self.assertEqual(len(text.encode()), size)
            self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), digest)
        self.assertNotIn('sfc_declarations', parts[-1].to_dict())
        with self.assertRaises(execution.ExecutionContextError):
            execution.render_execution_context_json(replace(parts[-1], sfc_declarations=[{}]))

    def test_absent_declared_interface_is_qualified_without_runtime_or_call_validation(self):
        parts = capture_v3(source('<Step ID="0" Name="First"/>'))
        result = parts[-1]
        row = result.call_boundaries[0]
        self.assertEqual((row['status'], row['boundary_profile'], row['target_language']),
                         ('associated', 'sfc_absent', 'SFC'))
        target = next(r for r in result.boundary_contents if r['id'] == row['target_content_id'])
        self.assertEqual(target['status'], 'qualified_sfc')
        self.assertEqual(target['sfc_declaration_ids'], [])
        self.assertEqual(result.coverage['calls_by_boundary_status']['unsupported_language'], 0)
        self.assertEqual(result.coverage['boundary_contents_by_language'], {'RLL': 1, 'SFC': 1})
        self.assertEqual(result.call_validation, 'not_analyzed')
        self.assertEqual(result.execution_analysis, 'not_implemented')
        self.assertEqual(result.parameter_roles, 'not_analyzed')
        self.assertEqual(result.status, 'partial')  # SFC execution is still unmodeled.
        execution.validate_execution_context(*parts)
        validate_execution_context_summary(build_execution_context_summary(*parts))

    def test_repeated_calls_share_one_exact_declaration_and_existing_sfc_source_ids(self):
        parts = capture_v3(source('<SbrRet ID="7" In="17, Root[2]" Ret=""/>',
                                  calls='JSR(Chart,0)JSR(Chart,2,17,29);'))
        result = parts[-1]
        self.assertEqual(len(result.sfc_declarations), 1)
        self.assertEqual({r['boundary_profile'] for r in result.call_boundaries}, {'sfc_declared'})
        self.assertEqual(len({r['target_content_id'] for r in result.call_boundaries}), 1)
        declaration = result.sfc_declarations[0]
        self.assertEqual(declaration['raw_attributes']['In'], '17, Root[2]')
        self.assertEqual((declaration['in_attribute_status'], declaration['ret_attribute_status']), ('text', 'empty'))
        sfc = analyze_sfc_structure(parts[0], parts[1])
        self.assertEqual(declaration['source_sfc_element_id'], sfc.elements[0]['id'])
        content = next(r for r in result.boundary_contents if r['language'] == 'SFC')
        self.assertEqual(content['source_sfc_content_id'], sfc.contents[0]['id'])
        self.assertEqual(content['sfc_declaration_ids'], [declaration['id']])
        self.assertEqual(result.coverage['distinct_associated_contents'], 1)
        self.assertFalse(any('parameter_index' in r or 'input_count' in r for r in result.argument_contexts))
        validate_execution_context_summary(build_execution_context_summary(*parts))

    def test_attribute_absence_empty_and_nonempty_spellings_do_not_validate_lists(self):
        for attrs, states in (('', ('missing', 'missing')), ('In=" " Ret="x,,y"', ('empty', 'text')),
                              ('In="Root[Dynamic]" Ret=""', ('text', 'empty'))):
            with self.subTest(attrs=attrs):
                parts = capture_v3(source(f'<SbrRet ID="0" {attrs}/>'))
                row = parts[-1].sfc_declarations[0]
                self.assertEqual((row['in_attribute_status'], row['ret_attribute_status']), states)
                self.assertEqual(parts[-1].call_boundaries[0]['status'], 'associated')
                validate_execution_context_summary(build_execution_context_summary(*parts))

    def test_multiple_declarations_are_not_selected_or_duplicated_per_call(self):
        parts = capture_v3(source('<SbrRet ID="0"/><SbrRet ID="1"/>', calls='JSR(Chart,0)' * 3 + ';'))
        result = parts[-1]
        self.assertEqual(len(result.sfc_declarations), 2)
        self.assertEqual({r['status'] for r in result.call_boundaries}, {'multiple_declarations'})
        self.assertEqual({r['boundary_profile'] for r in result.call_boundaries}, {'not_available'})
        self.assertEqual(result.coverage['sfc_contents_with_multiple_declarations'], 1)
        self.assertEqual(result.coverage['distinct_associated_contents'], 0)
        validate_execution_context_summary(build_execution_context_summary(*parts))

    def test_missing_multiple_mismatched_and_incomplete_content_dispositions(self):
        variants = (
            ('', 'missing_content'),
            ('<SFCContent/><SFCContent/>', 'multiple_contents'),
            ('<SFCContent/><STContent/>', 'multiple_contents'),
            ('<RLLContent/>', 'unsupported_context'),
            ('<SFCContent><Unexpected/></SFCContent>', 'incomplete_content'),
            ('<SFCContent><SbrRet/></SFCContent>', 'incomplete_content'),
            ('<SFCContent><SbrRet ID="0"/><Step ID="0"/></SFCContent>', 'incomplete_content'),
            ('<SFCContent><Step ID="0"><SbrRet ID="1"/></Step></SFCContent>', 'incomplete_content'),
            ('<SFCContent>unparsed text</SFCContent>', 'incomplete_content'),
            ('<SFCContent OnlineEditType="unknown"/>', 'incomplete_content'),
            ('<Unexpected/><SFCContent/>', 'unsupported_context'),
        )
        for content, expected in variants:
            with self.subTest(content=content):
                parts = capture_v3(source(target=routine('Chart', language='SFC', content=content)))
                self.assertEqual(parts[-1].call_boundaries[0]['status'], expected)
                self.assertEqual(parts[-1].call_boundaries[0]['boundary_profile'], 'not_available')
                validate_execution_context_summary(build_execution_context_summary(*parts))

    def test_foreign_namespaces_and_protection_block_entire_content(self):
        for body, expected in (
            ('<SbrRet xmlns="urn:foreign" ID="0"/>', 'namespace_gap'),
            ('<Step ID="0" x:Marker="foreign"/>', 'namespace_gap'),
            ('<SbrRet ID="0" x:In="A"/>', 'namespace_gap'),
            ('<SbrRet ID="0" Protected="false"/>', 'protected'),
            ('<EncodedData/>', 'protected'),
        ):
            with self.subTest(body=body):
                xml = source(body).replace('<RSLogix5000Content ', '<RSLogix5000Content xmlns:x="urn:foreign" ')
                parts = capture_v3(xml)
                self.assertEqual(parts[-1].call_boundaries[0]['status'], expected)
                validate_execution_context_summary(build_execution_context_summary(*parts))

    def test_scope_ambiguity_and_edits_do_not_select_a_target(self):
        for target, status in (
            (routine('Chart', language='SFC', content='<SFCContent/>') * 2, 'target_unavailable'),
            (routine('Chart', language='ST', content='<STContent/>'), 'unsupported_language'),
            (routine('Chart', language='SFC', content='<SFCContent OnlineEditType="Original"/><SFCContent OnlineEditType="TestEdits"/>'), 'multiple_contents'),
        ):
            parts = capture_v3(source(target=target))
            self.assertEqual(parts[-1].call_boundaries[0]['status'], status)
            validate_execution_context_summary(build_execution_context_summary(*parts))
        first = program('P', routine(text='JSR(Chart,0);') + routine('Chart', language='SFC', content='<SFCContent/>'))
        second = program('Q', routine(text='JSR(Chart,0);') + routine('Chart', language='SFC', content='<SFCContent><SbrRet ID="0"/></SFCContent>'))
        parts = capture_v3(document(first + second))
        self.assertEqual([r['boundary_profile'] for r in parts[-1].call_boundaries], ['sfc_absent', 'sfc_declared'])
        self.assertEqual(parts[-1].coverage['distinct_associated_contents'], 2)
        validate_execution_context_summary(build_execution_context_summary(*parts))

    def test_uncalled_and_aoi_owned_declarations_do_not_acquire_call_profiles(self):
        aoi = ('<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="Widget"><Routines>'
               + routine('Logic', language='SFC', content='<SFCContent><SbrRet ID="0"/></SFCContent>')
               + '</Routines></AddOnInstructionDefinition></AddOnInstructionDefinitions>')
        xml = source('<SbrRet ID="0"/>', calls='NOP();').replace('</Controller>', aoi + '</Controller>')
        parts = capture_v3(xml)
        self.assertEqual(len(parts[-1].sfc_declarations), 1)
        self.assertEqual(parts[-1].call_boundaries, [])
        self.assertEqual(parts[-1].coverage['distinct_associated_contents'], 0)
        validate_execution_context_summary(build_execution_context_summary(*parts))

    def test_replay_rejects_forged_declarations_source_ids_dispositions_and_counts(self):
        parts = capture_v3(source('<SbrRet ID="0" In="A" Ret=""/>'))
        for mutate in (
            lambda r: r.sfc_declarations[0]['raw_attributes'].update(In='B'),
            lambda r: r.sfc_declarations[0].update(source_sfc_element_id='invented'),
            lambda r: r.sfc_declarations[0].update(in_attribute_status='empty'),
            lambda r: r.call_boundaries[0].update(boundary_profile='sfc_absent'),
            lambda r: r.boundary_contents[-1]['sfc_declaration_ids'].clear(),
            lambda r: r.coverage.update(sfc_source_content_links=0),
        ):
            bad = deepcopy(parts[-1]); mutate(bad)
            with self.assertRaises(execution.ExecutionContextError):
                execution.validate_execution_context(*parts[:-1], bad)

    def test_public_counts_reject_impossible_partitions_and_links(self):
        base = build_execution_context_summary(*capture_v3(source('<SbrRet ID="0"/>')))
        for mutate in (
            lambda c: c['boundary_contents_by_language'].update(SFC=0),
            lambda c: c['calls_by_target_language'].update(SFC=0, RLL=1),
            lambda c: c['sfc_in_attributes'].update(missing=0),
            lambda c: c.update(sfc_contents_with_multiple_declarations=1),
            lambda c: c.update(sfc_contents_with_declarations=0),
            lambda c: c.update(sfc_source_content_links=0),
            lambda c: c.update(boundary_evidence_links=c['boundary_evidence_links'] - 1),
        ):
            bad = deepcopy(base); mutate(bad['coverage'])
            with self.assertRaises(ExecutionContextSummaryError): validate_execution_context_summary(bad)

    def test_public_maximum_count_width_fits_unchanged_eight_kib_limit(self):
        summary = build_execution_context_summary(*capture_v3())
        # Every coverage count is bounded by 250k records or by the 64-byte
        # minimum charged per evidence record/link within the 16 MiB limit.
        maximum = execution.MAX_EXECUTION_CONTEXT_BYTES // 64
        def grow(value):
            return maximum if type(value) is int else {key: grow(child) for key, child in value.items()}
        summary['coverage'] = grow(summary['coverage'])
        summary['tool_revision'] = {'commit': 'a' * 40, 'worktree': 'modified'}
        summary['status'] = 'complete'
        self.assertEqual(len((json.dumps(summary, sort_keys=True, indent=2) + '\n').encode()), 8136)

    def test_multiple_declarations_cannot_be_reported_as_qualified_content(self):
        summary = build_execution_context_summary(*capture_v3(source(
            '<SbrRet ID="0"/><SbrRet ID="1"/>', calls='NOP();')))
        c = summary['coverage']
        c['boundary_contents_by_status'].update(multiple_sfc_declarations=0, qualified_sfc=1)
        summary['status'] = 'partial' if execution._partial(c, 3) else 'complete'
        with self.assertRaises(ExecutionContextSummaryError): validate_execution_context_summary(summary)

    def test_mutually_exclusive_associated_profiles_require_distinct_contents(self):
        target = routine('Chart', language='SFC', content='<SFCContent><SbrRet ID="0"/></SFCContent>')
        target += routine('Other', language='SFC', content='<SFCContent/>')
        summary = build_execution_context_summary(*capture_v3(source(
            calls='JSR(Chart,0)JSR(Other,0);', target=target)))
        self.assertEqual(summary['coverage']['distinct_associated_contents'], 2)
        too_few = deepcopy(summary)
        too_few['coverage']['distinct_associated_contents'] = 1
        with self.assertRaises(ExecutionContextSummaryError): validate_execution_context_summary(too_few)
        summary['coverage']['boundary_contents_by_status'].update(qualified_sfc=1, incomplete_sfc=1)
        with self.assertRaises(ExecutionContextSummaryError): validate_execution_context_summary(summary)

    def test_private_link_record_and_exact_byte_limits_are_enforced(self):
        parts = capture_v3(source('<SbrRet ID="0"/>', calls='JSR(Chart,0)' * 8 + ';'))
        rendered = execution.render_execution_context_json(parts[-1])
        with patch.object(execution, 'MAX_EXECUTION_CONTEXT_JSON_BYTES', len(rendered.encode())):
            self.assertEqual(execution.render_execution_context_json(parts[-1]), rendered)
        with patch.object(execution, 'MAX_EXECUTION_CONTEXT_JSON_BYTES', len(rendered.encode()) - 1):
            with self.assertRaises(execution.ExecutionContextError): execution.validate_execution_context(*parts)
        base = execution.analyze_execution_context(*parts[:-1])
        for name, limit in (('MAX_EVIDENCE_IDS', base.coverage['evidence_links']),
                            ('MAX_EXECUTION_CONTEXT_RECORDS', sum(len(getattr(base, group)) for group in execution.ROW_GROUPS)),
                            ('MAX_EXECUTION_CONTEXT_BYTES', len(execution.render_execution_context_json(base).encode()) + 95)):
            with self.subTest(name=name), patch.object(execution, name, limit):
                with self.assertRaises(execution.ExecutionContextError):
                    execution._with_boundaries(parts[0], parts[1], parts[2], base, schema_version=3)

    def test_signal_context_replays_execution3_instead_of_schema1(self):
        from test_signal_context import capture_xml as signal_capture
        from plc_workbench.signal_context import analyze_signal_context, SignalContextError
        parts = signal_capture(source('<SbrRet ID="0"/>'))
        execution3 = execution.analyze_execution_context(*parts[:8], schema_version=3)
        args = (*parts[:11], execution3)
        analyze_signal_context(*args)
        bad = deepcopy(execution3); bad.sfc_declarations[0].update(ret_attribute_status='text')
        with self.assertRaises(SignalContextError): analyze_signal_context(*args[:-1], bad)


if __name__ == '__main__':
    unittest.main()
