"""Invented source ladders exercise bounded cross-rung signal navigation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.execution_context import analyze_execution_context
from plc_workbench.signal_context import (SignalContextError, analyze_signal_context,
    render_signal_context_json, validate_signal_context)
from plc_workbench.stateful_objects import analyze_stateful_objects
from plc_workbench.tag_data import analyze_tag_data
from test_output_context import capture as output_capture, capture_xml as output_capture_xml, namespace
from test_relationships import tag
from test_stateful_objects import typed_tag


def finish(base):
    tag_data = analyze_tag_data(base[0], base[1])
    stateful = analyze_stateful_objects(*base[:8], tag_data)
    execution = analyze_execution_context(*base[:8])
    args = (*base[:8], tag_data, base[8], stateful, execution)
    return (*args, analyze_signal_context(*args))


def capture(texts=('XIC(A)OTE(D);',), **kwargs):
    return finish(output_capture(texts, **kwargs))


def capture_xml(xml: str):
    return finish(output_capture_xml(xml))


def ancestors(conditions, guard: str) -> set[str]:
    nodes = {row['id']: row for row in conditions.nodes}
    seen: set[str] = set()
    pending = [guard]
    while pending:
        identifier = pending.pop()
        if identifier not in seen:
            seen.add(identifier)
            pending.extend(nodes[identifier]['child_ids'])
    return seen


class SignalContextTests(unittest.TestCase):
    def test_external_input_and_cross_rung_guard_navigation_are_complete(self) -> None:
        args = capture(('XIC(A)OTE(B);', 'XIO(B)OTE(C);', 'MOV(A,D)XIC(C)OTE(D);'))
        result = args[-1]
        self.assertEqual(result.coverage['condition_reads_total'], 3)
        self.assertEqual(result.coverage['source_predicate_operands'], 3)
        self.assertEqual(result.coverage['address_profiles'], {'coil_and_condition': 2, 'coil_only': 1, 'condition_only': 1})
        first, second, third = result.outputs
        self.assertEqual(result.condition_reads[1]['source_address_id'], first['target_address_id'])
        self.assertEqual(result.condition_reads[2]['source_address_id'], second['target_address_id'])
        self.assertEqual(result.condition_reads[1]['kind'], 'xio')
        self.assertIn(result.condition_reads[2]['condition_node_id'], ancestors(args[7], third['guard_id']))
        self.assertEqual(result.coverage['noncoil_writers_total'], 1)
        self.assertTrue(all('dependencies' not in row and 'output_ids' not in row for row in result.condition_reads))
        self.assertEqual(result.to_dict(), json.loads(render_signal_context_json(result)))
        validate_signal_context(*args)

    def test_parallel_guard_ancestors_do_not_mix_siblings_or_expand_pairs(self) -> None:
        args = capture(('[XIC(A)OTE(B),XIO(C)OTE(D)]OTE(A);',))
        left, right, join = args[-1].outputs
        one, two = args[-1].condition_reads
        self.assertIn(one['condition_node_id'], ancestors(args[7], left['guard_id']))
        self.assertNotIn(two['condition_node_id'], ancestors(args[7], left['guard_id']))
        self.assertNotIn(one['condition_node_id'], ancestors(args[7], right['guard_id']))
        self.assertIn(two['condition_node_id'], ancestors(args[7], join['guard_id']))
        self.assertTrue(join['has_branch'])
        self.assertEqual(len(args[-1].condition_reads), 2)

    def test_comparison_slots_constants_and_ons_storage_are_typed(self) -> None:
        result = capture(('EQU(A,1)LES(B,C)LIM(0,D,10)ONS(A)OTE(D);',))[-1]
        self.assertEqual(result.coverage['reads_by_kind'], {'comparison': 7, 'ons_storage': 1, 'xic': 0, 'xio': 0})
        self.assertEqual(result.coverage['reads_by_status']['literal'], 3)
        self.assertEqual(result.coverage['source_ons_storage_operands'], 1)
        self.assertEqual(result.outputs[0]['guard_quality'], 'stateful')
        self.assertTrue(all(row['source_address_id'] is None for row in result.condition_reads if row['status'] == 'literal'))

    def test_aliases_exact_member_spelling_and_all_target_uses_survive(self) -> None:
        tags = tag('A') + tag('B') + tag('Alias', 'B.X')
        result = capture(('OTE(Alias)OTL(B.X)OTU(B.x)XIC(B.X)XIO(B.x);',
                          'MOV(A,B.X)CPT(A,B.X+B.X)PID(B.X,A,B,A,0,0,0);'), tags=tags)[-1]
        self.assertEqual(len(result.addresses), 2)
        self.assertEqual(result.outputs[0]['target_address_id'], result.outputs[1]['target_address_id'])
        self.assertNotEqual(result.outputs[0]['target_address_id'], result.outputs[2]['target_address_id'])
        address = result.addresses[0]
        self.assertEqual(len(address['output_ids']), 2)
        self.assertEqual(len(address['expression_use_ids']), 2)
        self.assertEqual(len(address['noncoil_writer_operand_ids']), 1)
        self.assertEqual(len(address['unknown_operand_ids']), 1)
        self.assertEqual(result.status, 'partial')

    def test_timer_member_is_association_not_boolean_transfer(self) -> None:
        args = capture(('XIC(A)XIO(B)TON(T,?,?);', 'XIC(T.DN)OTE(D);', 'RES(T);'),
            tags=tag('A') + tag('B') + tag('D') + typed_tag('T'))
        result = args[-1]
        timer_read = result.condition_reads[-1]
        address = next(row for row in result.addresses if row['id'] == timer_read['source_address_id'])
        self.assertEqual(address['stateful_associations'], [{'object_id': args[10].objects[0]['id'],
            'kind': 'direct_member', 'member': 'DN', 'member_status': 'known', 'qualification': 'qualified'}])
        self.assertEqual(address['output_ids'], [])
        self.assertEqual(result.stateful_usage, 'source_association_not_boolean_transfer')
        self.assertEqual(result.coverage['stateful_associations_total'], 1)

    def test_module_endpoints_are_declared_without_command_feedback_assignment(self) -> None:
        modules = ('<Modules><Module Name="M"><Communications><Connections><Connection Name="C">'
            '<InputTag Name="M:I"/><OutputTag Name="M:O"/></Connection></Connections></Communications></Module></Modules>')
        result = capture(('XIC(M:I.Data.0)OTE(M:O.Data.1);',), modules=modules)[-1]
        self.assertEqual(result.coverage['endpoint_kinds']['module_input'], 1)
        self.assertEqual(result.coverage['endpoint_kinds']['module_output'], 1)
        self.assertTrue(all('engineering_role' not in row for row in result.addresses))

    def test_edit_containers_and_source_routine_provenance_stay_separate(self) -> None:
        xml = output_capture(('XIC(A)OTE(D);',))[0].data.decode()
        original = '<RLLContent Type="Original"><Rung Number="0"><Text>XIC(A)OTE(D);</Text></Rung></RLLContent>'
        pending = '<RLLContent Type="Pending"><Rung Number="0"><Text>XIO(A)OTE(D);</Text></Rung></RLLContent>'
        start, end = xml.index('<RLLContent>'), xml.index('</RLLContent>') + len('</RLLContent>')
        result = capture_xml(xml[:start] + original + pending + xml[end:])[-1]
        self.assertEqual([row['content_attributes'] for row in result.rung_contexts], [{'Type': 'Original'}, {'Type': 'Pending'}])
        self.assertNotEqual(result.outputs[0]['content_locator'], result.outputs[1]['content_locator'])
        self.assertEqual(result.outputs[0]['routine_id'], result.outputs[1]['routine_id'])
        self.assertEqual(result.outputs[0]['target_address_id'], result.outputs[1]['target_address_id'])
        self.assertEqual(result.edit_selection, 'not_implemented')

    def test_strict_namespace_ancestry_and_guard_contamination_are_explicit(self) -> None:
        xml = namespace(output_capture(('XIC(A)OTE(D);',))[0].data.decode())
        for old, new in (('<Routine ', '<Routine x:Marker="foreign" '),
                         ('<RLLContent>', '<RLLContent x:Marker="foreign">')):
            result = capture_xml(xml.replace(old, new))[-1]
            self.assertEqual(result.outputs[0]['target_status'], 'namespace_gap')
            self.assertEqual(result.condition_reads[0]['status'], 'namespace_gap')
            self.assertEqual(result.addresses, [])
        result = capture_xml(xml.replace('Name="A" TagType=', 'Name="A" x:Marker="foreign" TagType='))[-1]
        self.assertEqual(result.outputs[0]['target_status'], 'exact_address')
        self.assertEqual(result.outputs[0]['guard_quality'], 'namespace_gap')
        self.assertEqual(result.condition_reads[0]['status'], 'namespace_gap')
        self.assertIsNone(result.condition_reads[0]['source_address_id'])

    def test_hints_stay_rung_wide_and_foreign_text_is_quarantined(self) -> None:
        rungs = ('<Rung><Comment>pump alarm</Comment><Text>[XIC(A)OTE(B),XIO(A)OTE(D)];</Text></Rung>'
                 '<Rung><Comment>sensor pump</Comment><Text>XIC(A);</Text></Rung>')
        args = capture(rung_xml=rungs)
        self.assertEqual(args[-1].coverage['rungs_with_hints'], 2)
        self.assertTrue(all('candidate_ids_by_category' not in row for row in args[-1].outputs))
        self.assertEqual(len(args[-1].rung_contexts[0]['output_ids']), 2)
        self.assertEqual(args[-1].rung_contexts[1]['output_ids'], [])
        xml = namespace(args[0].data.decode()).replace('<Comment>', '<Comment x:Marker="foreign">')
        result = capture_xml(xml)[-1]
        self.assertEqual(result.coverage['rungs_with_hints'], 0)
        self.assertEqual(result.coverage['rungs_with_unqualified_hints'], 2)

    def test_binding_gaps_unparsed_and_no_downstream_coils_are_evidence(self) -> None:
        result = capture(('XIC(Missing)OTE(D);', 'XIC(A[B]);', 'BROKEN(', 'XIC(A);'))[-1]
        self.assertEqual(result.coverage['unparsed_rungs'], 1)
        self.assertEqual(result.coverage['reads_by_status']['unbound'], 2)
        self.assertEqual(result.coverage['condition_reads_total'], 3)
        self.assertEqual(len(result.rung_contexts), 4)
        self.assertEqual(result.status, 'partial')

    def test_canonical_replay_authenticates_all_companions_and_links(self) -> None:
        args = capture(('XIC(A)OTE(D);',))
        before = [deepcopy(vars(row)) for row in args[8:12]]
        validate_signal_context(*args)
        self.assertEqual(before, [vars(row) for row in args[8:12]])
        for index, field in ((9, 'outputs'), (10, 'objects'), (11, 'routine_contexts')):
            changed = list(args[:-1])
            changed[index] = replace(changed[index], status='private-marker')
            with self.subTest(index=index), self.assertRaises(SignalContextError) as caught:
                analyze_signal_context(*changed)
            self.assertNotIn('private-marker', str(caught.exception))
        for mutate in (lambda r: r.condition_reads[0].update(kind='xio'),
                       lambda r: r.outputs[0].update(guard_id='private-marker'),
                       lambda r: r.addresses[0]['read_operand_ids'].clear(),
                       lambda r: r.rung_contexts[0].update(content_locator='private-marker'),
                       lambda r: r.coverage.update(source_predicate_operands=True)):
            broken = deepcopy(args[-1])
            mutate(broken)
            with self.assertRaises(SignalContextError):
                validate_signal_context(*args[:-1], broken)

    def test_factorization_stays_linear_with_repeated_branches_and_coils(self) -> None:
        small = capture((''.join('[XIC(A),XIO(B)]' for _ in range(10)) + 'OTE(C)OTL(D);',))[-1]
        large = capture((''.join('[XIC(A),XIO(B)]' for _ in range(40)) + 'OTE(C)OTL(D);',))[-1]
        self.assertEqual(len(large.condition_reads), 80)
        self.assertEqual(len(large.outputs), 2)
        self.assertLess(len(render_signal_context_json(large)), 4 * len(render_signal_context_json(small)))

    def test_incremental_and_render_bounds_and_determinism(self) -> None:
        args = capture()
        for name in ('MAX_SIGNAL_CONTEXT_RECORDS', 'MAX_SIGNAL_CONTEXT_BYTES',
                     'MAX_SIGNAL_CONTEXT_JSON_BYTES', 'MAX_EVIDENCE_IDS'):
            with patch(f'plc_workbench.signal_context.{name}', 1), self.assertRaises(SignalContextError):
                analyze_signal_context(*args[:-1])
        cyclic = deepcopy(args[-1])
        cyclic.addresses.append(cyclic.addresses)
        with self.assertRaises(SignalContextError):
            render_signal_context_json(cyclic)
        self.assertEqual(render_signal_context_json(args[-1]), render_signal_context_json(analyze_signal_context(*args[:-1])))


if __name__ == '__main__':
    unittest.main()
