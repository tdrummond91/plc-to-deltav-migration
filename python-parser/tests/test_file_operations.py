"""Invented file/array operations exercise roles, provenance and bounded evidence."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import render_access_json
from plc_workbench.conditions import analyze_conditions, render_conditions_json
from plc_workbench.file_operations import (FileOperationError, analyze_file_operations,
    render_file_operations_json, validate_file_operations)
from plc_workbench.stateful_objects import _member
from plc_workbench.tag_data import analyze_tag_data
from test_relationships import capture as capture_relationships, tag
from test_stateful_objects import capture_xml as stateful_xml, typed_tag, namespace
from test_module_io import LOCAL, module, communications

DATA = ('<Data Format="Decorated"><Structure DataType="CONTROL">'
    '<DataValueMember Name="LEN" DataType="DINT" Value="5"/>'
    '<DataValueMember Name="POS" DataType="DINT" Value="1"/>'
    '<DataValueMember Name="DN" DataType="BOOL" Value="0"/></Structure></Data>')
TAGS = (typed_tag('A', 'DINT', '8') + typed_tag('B', 'DINT', '8') + typed_tag('D', 'DINT')
    + typed_tag('R', 'CONTROL', data=DATA) + typed_tag('I', 'DINT') + tag('Gate'))
TEXTS = ('COP(A[0],B[0],3);', 'CPS(A[1],B[0],2);', 'AVE(A[0],0,D,R,?,?);',
    'FAL(R,?,?,ALL,B[R.POS],A[R.POS]+1);', 'SQO(A[0],16#FFFF,D,R,?,?);')


def capture(texts=TEXTS, **kwargs):
    kwargs.setdefault('tags', TAGS)
    args = capture_relationships(texts, **kwargs)
    args = (*args, analyze_conditions(*args, schema_version=3), analyze_tag_data(*args[:2]))
    return (*args, analyze_file_operations(*args))


def capture_xml(xml: str):
    args = stateful_xml(xml)[:-1]
    return (*args, analyze_file_operations(*args))


class FileOperationTests(unittest.TestCase):
    def test_five_opcodes_roles_and_preceding_evidence_unchanged(self) -> None:
        args = capture()
        before = render_access_json(args[3]), render_conditions_json(args[7])
        result = analyze_file_operations(*args[:-1])
        self.assertEqual(result.coverage['occurrences_by_opcode'], dict.fromkeys(('AVE', 'COP', 'CPS', 'FAL', 'SQO'), 1))
        self.assertEqual(result.coverage['slots_total'], 24)
        self.assertEqual(result.coverage['newly_classified_instructions'], 3)
        self.assertEqual(result.coverage['newly_classified_slots'], 18)
        self.assertEqual(result.coverage['pseudo_operands_total'], 6)
        self.assertEqual(result.coverage['controls_total'], 1)
        existing_addresses = {r['id'] for r in args[6].addresses}
        self.assertTrue(all(s['address_id'] in existing_addresses for s in result.slots[:6]
            if s['status'] == 'exact_address'))
        sqo = [s for s in result.slots if s['instruction_id'] == result.occurrences[-1]['id']]
        self.assertEqual([s['role'] for s in sqo], ['read', 'read', 'read_write', 'read_write', 'non_data', 'non_data'])
        self.assertEqual(before, (render_access_json(args[3]), render_conditions_json(args[7])))
        validate_file_operations(*args)
        self.assertEqual(json.loads(render_file_operations_json(result)), result.to_dict())

    def test_fal_neutral_order_and_symbolic_occurrence_reads(self) -> None:
        result = capture(('FAL(R,?,?,INC,B[R.POS],A[R.POS]+A[R.POS]);',))[-1]
        row = result.occurrences[0]
        self.assertEqual(row['destination_slot_id'], result.slots[4]['id'])
        self.assertEqual(result.slots[4]['status'], 'symbolic_address')
        self.assertIsNone(result.slots[4]['address_id'])
        self.assertEqual(result.slots[5]['status'], 'parsed_expression')
        self.assertEqual(result.coverage['expression_references_total'], 2)
        self.assertEqual(result.coverage['index_read_occurrences'], 3)
        self.assertEqual(result.coverage['index_uses_total'], 3)
        self.assertEqual(len({r['id'] for r in result.index_uses}), 3)

    def test_pseudo_fields_and_selectors_are_not_runtime_reads(self) -> None:
        result = capture(('AVE(A[0],2,D,R,16#10,-1);', 'FAL(R,?,?,2147483647,D,1);'))[-1]
        non_data = [s for s in result.slots if s['role'] == 'non_data']
        self.assertEqual([s['selector_kind'] for s in non_data],
            ['dimension', 'integer_literal', 'integer_literal', 'placeholder', 'placeholder', 'numeric_mode'])
        self.assertTrue(all(s['binding'] is None for s in non_data))
        self.assertEqual(result.coverage['pseudo_operands_total'], 4)

    def test_invalid_selector_forms_keep_valid_slot_roles(self) -> None:
        result = capture(('AVE(A[0],3,D,R,B,?);', 'FAL(R,?,?,2147483648,D,1);', 'FAL(R,?,?,0,D,1);'))[-1]
        self.assertEqual(result.coverage['slots_by_status']['unsupported_form'], 4)
        self.assertEqual(result.coverage['signatures']['recognized'], 3)
        self.assertEqual(result.status, 'partial')

    def test_bad_signatures_never_assign_plausible_slots(self) -> None:
        result = capture(('COP(A,B)AVE(A,0,D,R,?,)FAL(R)SQO();',))[-1]
        self.assertEqual(len(result.occurrences), 4)
        self.assertTrue(all(s['role'] == 'unknown' for s in result.slots))
        self.assertTrue(all(s['status'] == 'signature_unresolved' for s in result.slots))
        self.assertEqual(result.expression_nodes, [])
        self.assertEqual(result.controls, [])
        self.assertEqual(result.coverage['newly_classified_instructions'], 0)

    def test_unsupported_fal_expression_is_all_or_nothing(self) -> None:
        for expression in ('A[0]+ATAN2(D,D)', 'A[0]+', '+'.join(['1'] * 300)):
            with self.subTest(expression=expression[:30]):
                result = capture((f'FAL(R,?,?,ALL,D,{expression});',))[-1]
                self.assertEqual(result.occurrences[0]['expression_status'], 'unsupported')
                self.assertEqual(result.expression_nodes, [])
                self.assertEqual(result.index_uses, [])
                self.assertEqual(result.status, 'partial')

    def test_literals_cannot_masquerade_as_array_or_destination(self) -> None:
        result = capture(('COP(12,13,2);', 'AVE(17,0,18,19,?,?);', 'SQO(20,16#FF,21,22,?,?);'))[-1]
        self.assertEqual(result.coverage['slots_by_status']['unsupported_form'], 8)
        self.assertEqual(result.controls, [])
        self.assertEqual(result.slots[-5]['status'], 'literal')

    def test_alias_identity_and_invalid_expanded_suffix(self) -> None:
        tags = TAGS + tag('Alias', 'B[0]') + tag('Bit', 'B.1')
        result = capture(('COP(A[0],Alias,1)COP(A[0],B[0],1)COP(A[0],B[00],1)COP(A[0],Bit.Member,1);',), tags=tags)[-1]
        destinations = [s for s in result.slots if s['kind'] == 'destination']
        self.assertEqual(destinations[0]['address_id'], destinations[1]['address_id'])
        self.assertNotEqual(destinations[1]['address_id'], destinations[2]['address_id'])
        self.assertEqual(destinations[3]['status'], 'invalid_identity')

    def test_dynamic_gap_details_do_not_invent_exact_elements(self) -> None:
        tags = TAGS + tag('Alias', 'B[I]')
        result = capture(('COP(A[0],B[Missing+I],1)COP(A[0],Missing[I],1)COP(A[0],Alias,1);',), tags=tags)[-1]
        self.assertEqual(result.coverage['index_reads_by_status']['unbound'], 1)
        self.assertEqual(result.coverage['index_roots_by_status']['unbound'], 1)
        self.assertEqual(result.coverage['index_uses_by_status']['alias_target_dynamic'], 1)
        self.assertTrue(all(s['address_id'] is None for s in result.slots if s['kind'] == 'destination'))
        self.assertEqual(result.status, 'partial')

    def test_incoming_branch_guards_preserve_unknown_and_stateful_context(self) -> None:
        result = capture(('[XIC(Gate)COP(A,B,1),ONS(Gate)CPS(A,B,1)]AVE(A,0,D,R,?,?);',
            'Mystery(Gate)FAL(R,?,?,ALL,D,1);', 'XIC(Missing)SQO(A,1,D,R,?,?);'))[-1]
        self.assertEqual([r['context_status'] for r in result.occurrences], ['modeled', 'stateful', 'stateful', 'opaque', 'binding_gaps'])
        self.assertEqual(result.occurrences[0]['span_kind'], 'destination_element_copy')

    def test_namespace_ancestry_and_text_attributes_quarantine_occurrences(self) -> None:
        original = capture(('AVE(A[0],0,D,R,?,?);',))[0].data.decode()
        for xml in (namespace(original).replace('<RLLContent>', '<RLLContent x:Type="foreign">'),
                    namespace(original).replace('<Text>', '<Text x:format="foreign">')):
            result = capture_xml(xml)[-1]
            self.assertEqual(result.coverage['qualifications']['namespace_gap'], 1)
            self.assertEqual(result.controls, [])
            self.assertTrue(all(s['status'] == 'namespace_gap' and s['address_id'] is None for s in result.slots))

    def test_foreign_alias_and_implicit_module_dependencies_are_unqualified(self) -> None:
        args = capture(('COP(A[0],Alias,1);',), tags=TAGS + tag('Alias', 'B[0]'))
        xml = namespace(args[0].data.decode()).replace('Name="Alias"', 'Name="Alias" x:Type="foreign"')
        self.assertEqual(capture_xml(xml)[-1].slots[1]['status'], 'namespace_gap')
        args = capture(('COP(Local:3:I.Data,B[0],1);',),
            modules='<Modules>' + LOCAL + module(communications=communications()) + '</Modules>')
        xml = namespace(args[0].data.decode()).replace('Address="3"', 'Address="3" x:Topology="foreign"')
        self.assertEqual(capture_xml(xml)[-1].slots[0]['status'], 'namespace_gap')

    def test_control_data_retains_duplicates_formats_and_type_gaps(self) -> None:
        tags = TAGS.replace(DATA, DATA + DATA + '<Data Format="L5K">[5,1,0]</Data>')
        result = capture(('AVE(A,0,D,R,?,?)SQO(A,1,D,R,?,?);',), tags=tags)[-1]
        self.assertEqual(len(result.controls[0]['content_ids']), 3)
        self.assertEqual(len(result.stored_data), 8)
        self.assertEqual(result.coverage['controls_with_data'], 1)
        bad = capture(('AVE(A,0,D,R,?,?);',), tags=TAGS.replace('Structure DataType="CONTROL"', 'Structure DataType="TIMER"'))[-1]
        self.assertEqual(bad.coverage['stored_types_by_status']['mismatch'], 4)
        self.assertEqual(bad.status, 'partial')

    def test_nested_control_members_and_array_bounds_remain_distinct(self) -> None:
        tags = TAGS.replace('Name="R" TagType="Base" DataType="CONTROL" Dimensions=""',
            'Name="R" TagType="Base" DataType="CONTROL" Dimensions="2"')
        result = capture(('AVE(A,0,D,R[0],?,?)AVE(A,0,D,R[2],?,?)AVE(A,0,D,R.Member,?,?);',), tags=tags)[-1]
        self.assertEqual([r['bounds_status'] for r in result.controls], ['static_in_bounds', 'static_out_of_bounds', 'unresolved'])
        self.assertEqual(result.controls[-1]['declaration_kind'], 'unresolved')

    def test_control_array_data_matching_scales_with_relevant_paths(self) -> None:
        size = 24
        elements = ''.join(f'<Element Index="[{i}]"><Structure DataType="CONTROL">'
            '<DataValueMember Name="LEN" DataType="DINT" Value="8"/>'
            '<DataValueMember Name="POS" DataType="DINT" Value="0"/></Structure></Element>' for i in range(size))
        data = f'<Data Format="Decorated"><Array DataType="CONTROL" Dimensions="{size}">{elements}</Array></Data>'
        tags = TAGS.replace(typed_tag('R', 'CONTROL', data=DATA), typed_tag('R', 'CONTROL', str(size), data))
        with patch('plc_workbench.file_operations._member', wraps=_member) as matches:
            result = capture(tuple(f'AVE(A,0,D,R[{i}],?,?);' for i in range(size)), tags=tags)[-1]
        self.assertEqual(len(result.controls), size)
        self.assertEqual(result.coverage['controls_with_data'], size)
        self.assertLessEqual(matches.call_count, 5 * size)

    def test_index_resource_limit_is_an_explicit_source_gap(self) -> None:
        # The ordinary address grammar admits a long identifier, while the
        # separate symbolic parser imposes its smaller evidence budget.
        result = capture(('COP(A[0],B[' + 'I' * 4100 + '],1);',))[-1]
        self.assertEqual(result.coverage['index_uses_by_status']['resource_limit'], 1)
        self.assertIsNone(result.slots[1]['address_id'])
        self.assertEqual(result.status, 'partial')

    def test_resource_limits_and_custom_containers_are_rejected(self) -> None:
        args = capture()
        with patch('plc_workbench.file_operations.MAX_FILE_OPERATION_BYTES', 64):
            with self.assertRaises(FileOperationError):
                analyze_file_operations(*args[:-1])
        result = replace(args[-1], slots=[])
        result.slots.append(result.slots)
        with self.assertRaises(FileOperationError):
            render_file_operations_json(result)
        class Evil(list):
            def __iter__(self):
                raise AssertionError('custom iterator was invoked')
        with self.assertRaises(FileOperationError):
            render_file_operations_json(replace(args[-1], slots=Evil()))

    def test_mutated_result_and_upstream_are_rejected_source_free(self) -> None:
        args = capture()
        result = deepcopy(args[-1])
        result.slots[0]['role'] = 'write'
        with self.assertRaisesRegex(FileOperationError, '^File operation evidence'):
            validate_file_operations(*args[:-1], result)
        broken = deepcopy(args[3])
        broken.operands[0]['role'] = 'write'
        with self.assertRaises(FileOperationError):
            analyze_file_operations(*args[:3], broken, *args[4:-1])

    def test_nonselected_source_is_complete_empty_companion(self) -> None:
        result = capture(('MOV(D,D);',))[-1]
        self.assertEqual(result.occurrences, [])
        self.assertEqual(result.status, 'complete')


if __name__ == '__main__':
    unittest.main()
