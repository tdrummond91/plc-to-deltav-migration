"""Invented source candidates keep exact uses, uncertainty and bounded joins."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from plc_workbench.signal_candidates import CANDIDATE_COVERAGE_KEYS
from plc_workbench.signal_context import (SignalContextError, analyze_signal_context,
    render_signal_context_json, signal_context_constants, validate_signal_context)
from test_signal_context import capture as base_capture, capture_xml as base_capture_xml, namespace, tag
from test_signal_authored import described

MODULES = ('<Modules><Module Name="M"><Communications><Connections><Connection Name="C">'
    '<InputTag Name="M:I"/><OutputTag Name="M:O"/></Connection></Connections></Communications></Module></Modules>')


def capture(*args, **kwargs):
    parts = base_capture(*args, **kwargs)
    return (*parts[:-1], analyze_signal_context(*parts[:-1], schema_version=5))


def capture_xml(xml: str):
    parts = base_capture_xml(xml)
    return (*parts[:-1], analyze_signal_context(*parts[:-1], schema_version=5))


def context(output):
    return output['candidate_context']


class SignalCandidateTests(unittest.TestCase):
    def test_signal_four_projection_and_default_are_byte_identical(self) -> None:
        args = base_capture(('XIC(Alarm)OTL(Pump);', 'XIO(Pump)OTU(Pump);'),
            tags=tag('Alarm') + tag('Pump'))
        old = analyze_signal_context(*args[:-1], schema_version=4)
        new = analyze_signal_context(*args[:-1], schema_version=5)
        reduced = deepcopy(new)
        for output in reduced.outputs:
            del output['candidate_context']
        for key in CANDIDATE_COVERAGE_KEYS:
            del reduced.coverage[key]
        reduced = replace(reduced, **signal_context_constants(4))
        self.assertEqual(render_signal_context_json(reduced), render_signal_context_json(old))
        self.assertEqual(analyze_signal_context(*args[:-1]).schema_version, 1)
        validate_signal_context(*args[:-1], new)

    def test_condition_target_and_both_seed_combinations_keep_occurrences(self) -> None:
        result = capture(('XIC(Alarm)OTE(D);', 'XIC(A)OTE(Pump);', 'XIC(Alarm)OTE(Pump);'),
            tags=tag('Alarm') + tag('Pump') + tag('A') + tag('D'))[-1]
        self.assertEqual(result.coverage['candidate_pairs_by_seed'],
            {'both': 1, 'condition_only': 1, 'target_only': 1})
        self.assertEqual([context(row)['target_categories'] for row in result.outputs],
            [[], ['equipment'], ['equipment']])
        self.assertEqual([context(row)['conditions'][0]['categories'] for row in result.outputs],
            [['alarm'], [], ['alarm']])

    def test_reader_alias_does_not_label_writer_and_writer_alias_does_not_label_reader(self) -> None:
        for text, target, source in (('XIC(Alarm)OTE(D);', [], ['alarm']),
                ('XIC(D)OTE(Alarm);', ['alarm'], [])):
            with self.subTest(text=text):
                result = capture((text,), tags=tag('D') + tag('Alarm', 'D'))[-1]
                selected = context(result.outputs[0])
                self.assertEqual(selected['target_categories'], target)
                self.assertEqual(selected['conditions'][0]['categories'], source)

    def test_root_wording_stays_root_context_and_no_neighbor_or_expression_leak(self) -> None:
        result = capture(('XIC(A.Left)OTE(A.Right);', 'CPT(D,A.Left)XIC(B)OTE(D);'),
            tags=described('A', 'alarm sensor') + tag('B') + tag('D'))[-1]
        self.assertEqual(context(result.outputs[0])['target_categories'], ['alarm', 'sensor'])
        self.assertEqual(context(result.outputs[0])['conditions'][0]['categories'], ['alarm', 'sensor'])
        self.assertEqual(context(result.outputs[1])['conditions'], [])
        self.assertTrue(all(row['scope'] == 'declaration_root_context'
            for address in result.addresses for row in address['authored_evidence']))

    def test_repeated_shared_and_branch_contacts_keep_original_membership(self) -> None:
        result = capture(('XIC(A)[XIC(B)OTE(Pump),XIO(C)OTE(Valve)]OTE(Pump)XIC(D);',
                          'XIC(A)XIO(A)EQU(A,A)OTE(Pump);'),
            tags=''.join(tag(name) for name in ('A', 'B', 'C', 'D', 'Pump', 'Valve')))[-1]
        first, second, join, repeated = result.outputs
        for output in result.outputs:
            self.assertEqual([row['condition_read_id'] for row in context(output)['conditions']],
                output['guard_dependencies']['condition_read_ids'])
        self.assertEqual([len(context(row)['conditions']) for row in (first, second, join, repeated)], [2, 2, 3, 4])
        self.assertEqual(len({row['condition_read_id'] for row in context(repeated)['conditions']}), 4)
        self.assertTrue(join['has_branch'])

    def test_module_endpoints_seed_both_sides_without_physical_pairing(self) -> None:
        result = capture(('XIC(M:I.Data.0)OTE(M:O.Data.1);',), modules=MODULES)[-1]
        selected = context(result.outputs[0])
        self.assertEqual(selected['target_categories'], ['module_output'])
        self.assertEqual(selected['conditions'][0]['categories'], ['module_input'])
        self.assertEqual(result.physical_mapping, 'not_implemented')
        self.assertEqual(result.shutdown_analysis, 'not_implemented')

    def test_empty_no_match_literal_flag_and_unbound_reads_remain_distinct(self) -> None:
        result = capture(('OTE(Pump);', 'XIC(A)OTE(D);', 'EQU(1,2)XIC(S:FS)XIC(Missing)OTE(Pump);'),
            tags=tag('A') + tag('D') + tag('Pump'))[-1]
        self.assertEqual([context(row)['conditions'] for row in result.outputs], [[], [], []])
        self.assertEqual(result.coverage['candidate_outputs_with_target_categories'], 2)
        self.assertEqual(result.coverage['candidate_scans_by_status'], {'complete': 3, 'truncated': 0})
        self.assertEqual(result.outputs[2]['guard_quality'], 'binding_gaps')

    def test_missing_signature_and_namespace_targets_are_excluded(self) -> None:
        for text in ('XIC(Alarm)OTE(Missing);', 'XIC(Alarm)OTE(A,D);'):
            result = capture((text,), tags=tag('Alarm') + tag('A') + tag('D'))[-1]
            self.assertTrue(all(not context(row)['conditions'] and not context(row)['target_categories']
                for row in result.outputs))
        xml = namespace(base_capture(('XIC(Alarm)OTE(Pump);',), tags=tag('Alarm') + tag('Pump'))[0].data.decode())
        xml = xml.replace('Name="Pump" TagType=', 'Name="Pump" x:Marker="foreign" TagType=')
        result = capture_xml(xml)[-1]
        self.assertEqual(result.outputs[0]['target_status'], 'namespace_gap')
        self.assertEqual(context(result.outputs[0])['conditions'], [])

    def test_namespace_contaminated_guard_does_not_promote_qualified_sibling(self) -> None:
        xml = namespace(base_capture(('[XIC(Alarm),XIC(B)]OTE(Pump);',),
            tags=tag('Alarm') + tag('B') + tag('Pump'))[0].data.decode())
        xml = xml.replace('Name="B" TagType=', 'Name="B" x:Marker="foreign" TagType=')
        result = capture_xml(xml)[-1]
        self.assertEqual(result.outputs[0]['guard_quality'], 'namespace_gap')
        self.assertEqual(context(result.outputs[0])['conditions'], [])

    def test_ambiguous_and_namespace_descriptions_stay_existing_gaps(self) -> None:
        for fragment in ('<Description>alarm</Description><Description>sensor</Description>',
                '<x:Description>alarm</x:Description>'):
            xml = namespace(base_capture(('XIC(A)OTE(D);',), tags=tag('A') + tag('D'))[0].data.decode())
            xml = xml.replace(tag('A'), tag('A').replace('/>', f'>{fragment}</Tag>'))
            result = capture_xml(xml)[-1]
            self.assertEqual(context(result.outputs[0])['conditions'], [])
            self.assertEqual(context(result.outputs[0])['scan_status'], 'complete')
            self.assertEqual(result.status, 'partial')

    def test_opaque_stateful_comparison_and_set_reset_remain_typed_associations(self) -> None:
        result = capture(('XIC(Alarm)MYSTERY(A)OTE(Pump);', 'EQU(A,1)ONS(B)OTL(Pump);', 'XIO(A)OTU(Pump);'),
            tags=''.join(tag(name) for name in ('Alarm', 'A', 'B', 'Pump')))[-1]
        self.assertEqual(result.coverage['candidate_pairs_by_guard_quality']['opaque'], 1)
        self.assertEqual(result.coverage['candidate_pairs_by_guard_quality']['stateful'], 2)
        self.assertEqual(result.coverage['candidate_pairs_by_kind']['comparison'], 1)
        self.assertEqual(result.coverage['candidate_pairs_by_kind']['ons_storage'], 1)
        self.assertEqual([row['opcode'] for row in result.outputs], ['OTE', 'OTL', 'OTU'])

    def test_source_edits_keep_separate_candidate_occurrences(self) -> None:
        xml = base_capture(('XIC(Alarm)OTE(Pump);',), tags=tag('Alarm') + tag('Pump'))[0].data.decode()
        start, end = xml.index('<RLLContent>'), xml.index('</RLLContent>') + len('</RLLContent>')
        body = xml[start:end]
        xml = xml[:start] + body.replace('<RLLContent>', '<RLLContent Type="Original">') + body.replace(
            '<RLLContent>', '<RLLContent Type="Pending">') + xml[end:]
        result = capture_xml(xml)[-1]
        self.assertEqual(result.coverage['candidate_pairs_total'], 2)
        self.assertNotEqual(result.outputs[0]['content_locator'], result.outputs[1]['content_locator'])
        self.assertNotEqual(context(result.outputs[0])['conditions'], context(result.outputs[1])['conditions'])

    def test_dependency_and_authored_truncation_propagate_even_with_empty_prefix(self) -> None:
        args = base_capture(('XIC(Alarm)OTE(Pump);',), tags=tag('Alarm') + tag('Pump'))
        for module, cap in (('signal_dependencies', 'MAX_DEPENDENCY_LINKS'),
                ('signal_authored', 'MAX_AUTHORED_USE_VISITS')):
            with self.subTest(cap=cap), patch(f'plc_workbench.{module}.{cap}', 0):
                result = analyze_signal_context(*args[:-1], schema_version=5)
                self.assertEqual(context(result.outputs[0])['scan_status'], 'truncated')
                validate_signal_context(*args[:-1], result)

    def test_each_join_and_retention_limit_is_explicit_and_replayable(self) -> None:
        args = base_capture(('XIC(Alarm)OTE(Pump);', 'XIO(Alarm)OTE(Pump);'),
            tags=tag('Alarm') + tag('Pump'))
        for cap in ('MAX_CANDIDATE_AUTHORED_VISITS', 'MAX_CANDIDATE_INDEX_LINKS',
                'MAX_CANDIDATE_DEPENDENCY_VISITS', 'MAX_CANDIDATE_PAIRS', 'MAX_CANDIDATE_BYTES'):
            with self.subTest(cap=cap), patch(f'plc_workbench.signal_candidates.{cap}', 0):
                first = analyze_signal_context(*args[:-1], schema_version=5)
                second = analyze_signal_context(*args[:-1], schema_version=5)
                self.assertEqual(render_signal_context_json(first), render_signal_context_json(second))
                self.assertEqual(first.coverage['candidate_scans_by_status']['truncated'], 2)
                self.assertEqual(first.status, 'partial')
                validate_signal_context(*args[:-1], first)

    def test_pair_budget_preserves_atomic_occurrences_and_target_context(self) -> None:
        args = base_capture(('XIC(A)XIO(A)OTE(Pump);',), tags=tag('A') + tag('Pump'))
        with patch('plc_workbench.signal_candidates.MAX_CANDIDATE_PAIRS', 1):
            result = analyze_signal_context(*args[:-1], schema_version=5)
            self.assertEqual(context(result.outputs[0])['target_categories'], ['equipment'])
            self.assertEqual(len(context(result.outputs[0])['conditions']), 1)
            self.assertEqual(context(result.outputs[0])['scan_status'], 'truncated')
            validate_signal_context(*args[:-1], result)

    def test_tampering_and_versioned_caps_are_rejected_source_free(self) -> None:
        args = capture(('XIC(Alarm)OTE(Pump);',), tags=tag('Alarm') + tag('Pump'))
        for mutate in (lambda r: context(r.outputs[0])['conditions'].clear(),
                lambda r: context(r.outputs[0])['target_categories'].append('PRIVATE'),
                lambda r: context(r.outputs[0]).update(scan_status='PRIVATE'),
                lambda r: r.coverage.update(candidate_pairs_total=True)):
            broken = deepcopy(args[-1])
            mutate(broken)
            with self.assertRaises(SignalContextError) as caught:
                validate_signal_context(*args[:-1], broken)
            self.assertNotIn('PRIVATE', str(caught.exception))
        for cap in ('MAX_SIGNAL_CONTEXT_V5_BYTES', 'MAX_SIGNAL_CONTEXT_V5_JSON_BYTES'):
            with patch(f'plc_workbench.signal_context.{cap}', 1), self.assertRaises(SignalContextError):
                render_signal_context_json(args[-1])
        for version in (True, 0, 6, '5'):
            with self.subTest(version=version), self.assertRaises(SignalContextError):
                analyze_signal_context(*args[:-1], schema_version=version)


if __name__ == '__main__':
    unittest.main()
