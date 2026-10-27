"""Invented source-use facts never establish wiring, activity or spare status."""
from __future__ import annotations

from copy import deepcopy
import unittest
import re
from unittest.mock import patch

from plc_workbench.access import analyze_access
from plc_workbench.calculations import analyze_calculations
from plc_workbench.references import analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.workspace_field_io import FieldIOIndex
from plc_workbench.workspace_signal_usage import SignalUsageIndex, USAGE_STATUSES
from plc_workbench.workspace_variables import VariableIndex
from test_workspace_field_io import field_inputs, module
from test_workspace_variables import wire


def build(inputs=None, *, missing_access: bool = False) -> SignalUsageIndex:
    values = wire(inputs or field_inputs(()))
    if missing_access:
        values[3] = None
    return SignalUsageIndex(FieldIOIndex(VariableIndex(*values)))


def recapture(source: bytes):
    snapshot = snapshot_from_bytes(source)
    inventory = analyze_snapshot(snapshot)
    refs = analyze_references(inventory)
    calculations = analyze_calculations(snapshot, inventory, refs)
    access = analyze_access(inventory, refs, schema_version=4, snapshot=snapshot, calculations=calculations)
    return snapshot, inventory, refs, access, calculations, None, None


def address(index: SignalUsageIndex, name: str) -> dict:
    return next(row for row in index.io.addresses.values() if row['address'].casefold() == name.casefold())


class SignalUsageTests(unittest.TestCase):
    def test_exact_alias_reads_writes_and_read_write_roles_remain_separate(self) -> None:
        index = build(field_inputs(('XIC(InputAlias)OTE(Local:2:O.Data.0);',
                                    'XIO(Local:1:I.Data.0)ONS(InputAlias);')))
        row = address(index, 'Local:1:I.Data.0')
        before = deepcopy(index.io.addresses)
        summary = index.summary(row)
        self.assertEqual(summary['status'], 'referenced')
        self.assertEqual((summary['direct_count'], summary['direct_rung_count']), (3, 2))
        self.assertEqual(summary['roles'], {'read': 2, 'write': 0, 'read_write': 1, 'unknown': 0})
        self.assertEqual(summary['possible_count'], 0)
        self.assertTrue(summary['coverage_complete'])
        output = index.summary(address(index, 'Local:2:O.Data.0'))
        self.assertEqual(output['roles']['write'], 1)
        self.assertEqual(index.io.addresses, before)
        self.assertEqual(set(USAGE_STATUSES), {'referenced', 'possible_indirect', 'not_found', 'unknown'})

    def test_cpt_expression_member_use_is_an_exact_read(self) -> None:
        index = build(field_inputs(('CPT(InternalReal,Local:3:I.Ch0Data*2);',)))
        result = index.summary(address(index, 'Local:3:I.Ch0Data'))
        self.assertEqual(result['status'], 'referenced')
        self.assertEqual(result['direct_count'], 1)
        self.assertEqual(result['roles']['read'], 1)
        self.assertTrue(result['coverage_complete'])

    def test_no_reference_is_limited_to_complete_supported_scan_not_alias_declaration(self) -> None:
        index = build()
        result = index.summary(address(index, 'Local:1:I.Data.0'))
        self.assertEqual(result['status'], 'not_found')
        self.assertTrue(result['coverage_complete'])
        self.assertEqual(result['gap_reasons'], [])
        self.assertIn('supported captured ladder scan', result['notice'])
        self.assertIn('spare status are not established', result['notice'])

    def test_whole_word_and_member_references_resolve_without_claiming_sibling_bits(self) -> None:
        index = build(field_inputs(('MOV(Local:1:I.Data,InternalReal);',)))
        member = index.summary(address(index, 'Local:1:I.Data.0'))
        self.assertEqual(member['status'], 'referenced')
        self.assertEqual(member['direct_count'], 0)
        self.assertEqual(member['resolved_uses'][0]['reason'], 'whole_word')
        self.assertEqual(member['resolved_uses'][0]['variable'], 'Local:1:I.Data')
        self.assertEqual(index.status(address(index, 'Local:1:I.Data')), 'referenced')
        index = build(field_inputs(('XIC(Local:1:I.Data.10);',)))
        root = index.summary(address(index, 'Local:1:I.Data'))
        self.assertEqual(root['resolved_uses'][0]['reason'], 'aggregate_child')
        self.assertEqual(index.status(address(index, 'Local:1:I.Data.0')), 'not_found')

    def test_cop_cps_and_fll_ranges_do_not_claim_a_particular_channel_or_cross_roots(self) -> None:
        leaves = ''.join(f'<DataValueMember Name="Ch{i}Data" DataType="REAL" Value="0"/>' for i in range(3))
        cards = module('First', 1, 'INVENTED', data=leaves) + module('Other', 2, 'INVENTED', data=leaves)
        for opcode in ('COP', 'CPS', 'FLL'):
            text = (f'{opcode}(Local:1:I.Ch0Data,InternalReal,2);' if opcode != 'FLL'
                    else 'FLL(0,Local:1:I.Ch0Data,2);')
            with self.subTest(opcode=opcode):
                index = build(field_inputs((text,), modules=cards))
                result = index.summary(address(index, 'Local:1:I.Ch2Data'))
                self.assertEqual(result['status'], 'possible_indirect')
                self.assertEqual((result['direct_count'], result['possible_count']), (0, 1))
                self.assertEqual(result['possible_uses'][0]['reason'], 'range_unresolved')
                self.assertEqual(result['possible_uses'][0]['opcode'], opcode)
                self.assertEqual(result['possible_uses'][0]['variable'], 'Local:1:I.Ch0Data')
                other = index.summary(address(index, 'Local:2:I.Ch2Data'))
                self.assertEqual(other['possible_count'], 0)
                self.assertEqual(other['status'], 'not_found')
                if opcode != 'FLL':
                    exact = index.summary(address(index, 'Local:1:I.Ch0Data'))
                    self.assertEqual(exact['status'], 'referenced')
                    self.assertEqual(exact['possible_count'], 0)

    def test_dynamic_indices_keep_root_and_static_prefix_without_evaluating_channel(self) -> None:
        leaves = ('<ArrayMember Name="Data" DataType="REAL" Dimensions="2">'
                  '<Element Index="[0]" Value="0"/><Element Index="[1]" Value="0"/></ArrayMember>'
                  '<DataValueMember Name="Ch0Data" DataType="REAL" Value="0"/>')
        index = build(field_inputs(('MOV(Local:1:I.Data[Index],InternalReal);',),
            modules=module('ArrayCard', 1, 'INVENTED', data=leaves),
            extra_tags='<Tag Name="Index" DataType="DINT"/>'))
        for member in ('Local:1:I.Data[0]', 'Local:1:I.Data[1]'):
            result = index.summary(address(index, member))
            self.assertEqual(result['status'], 'possible_indirect')
            self.assertEqual(result['direct_count'], 0)
            self.assertEqual(result['possible_uses'][0]['reason'], 'dynamic_index')
            self.assertEqual(result['possible_uses'][0]['variable'], 'Local:1:I.Data[Index]')
        self.assertEqual(index.summary(address(index, 'Local:1:I.Ch0Data'))['possible_count'], 0)
        self.assertEqual(index.summary(address(index, 'Local:1:O.Data[0]'))['possible_count'], 0)

    def test_dynamic_cpt_leaf_retains_its_own_id_text_and_read_role(self) -> None:
        leaves = ('<ArrayMember Name="Data" DataType="REAL" Dimensions="2">'
                  '<Element Index="[0]" Value="0"/><Element Index="[1]" Value="0"/></ArrayMember>')
        index = build(field_inputs(('CPT(InternalReal,Local:1:I.Data[Index]+1);',),
            modules=module('ArrayCard', 1, 'INVENTED', data=leaves),
            extra_tags='<Tag Name="Index" DataType="DINT"/>'))
        result = index.summary(address(index, 'Local:1:I.Data[0]'))
        self.assertEqual(result['status'], 'possible_indirect')
        use = result['possible_uses'][0]
        self.assertEqual((use['variable'], use['role'], use['reason']),
                         ('Local:1:I.Data[Index]', 'read', 'dynamic_index'))
        self.assertIn(use['id'], {row['id'] for row in index.base._access.expression_uses})

    def test_dynamic_selector_explains_snapshot_external_access_and_writer_source(self) -> None:
        leaves = ('<ArrayMember Name="Data" DataType="DINT" Dimensions="4">'
                  '<Element Index="[0]" Value="0"/><Element Index="[1]" Value="0"/></ArrayMember>')
        tags = ('<Tag Name="Index" DataType="DINT" ExternalAccess="Read/Write">'
                '<Data Format="Decorated"><DataValue DataType="DINT" Value="0"/></Data></Tag>')
        index = build(field_inputs(('MOV(1,Index);', 'MOV(Local:1:I.Data[Index],InternalReal);'),
            modules=module('ArrayCard', 1, 'INVENTED', data=leaves), extra_tags=tags))
        summary = index.summary(address(index, 'Local:1:I.Data[0]'))
        self.assertEqual(summary['status'], 'possible_indirect')
        self.assertEqual(summary['resolved_count'], 0)
        use = summary['possible_uses'][0]
        self.assertIn('Index (DINT)', use['explanation'])
        self.assertIn('exported value 0 is a snapshot', use['explanation'])
        self.assertIn('external access Read/Write', use['explanation'])
        self.assertEqual(use['index_sources'][0]['rung_id'], index.base._captured.rungs[0].id)
        self.assertIn('Rung 0', use['index_sources'][0]['path'])
        self.assertEqual(summary['detail'], use['explanation'])

    def test_fixed_copy_resolves_only_selected_elements_and_keeps_exact_occurrences(self) -> None:
        leaves = ('<ArrayMember Name="Data" DataType="DINT" Dimensions="4">' +
                  ''.join(f'<Element Index="[{i}]" Value="0"/>' for i in range(4)) + '</ArrayMember>')
        index = build(field_inputs(('COP(Local:1:I.Data[1],Buffer[0],2);',),
            modules=module('ArrayCard', 1, 'INVENTED', data=leaves),
            extra_tags='<Tag Name="Buffer" DataType="DINT" Dimensions="4"/>'))
        for i, status in ((0, 'not_found'), (1, 'referenced'), (2, 'referenced'), (3, 'not_found')):
            with self.subTest(element=i):
                self.assertEqual(index.status(address(index, f'Local:1:I.Data[{i}]')), status)
        exact = index.summary(address(index, 'Local:1:I.Data[1]'))
        selected = index.summary(address(index, 'Local:1:I.Data[2]'))
        self.assertEqual((exact['direct_count'], exact['resolved_count']), (1, 0))
        self.assertEqual((selected['direct_count'], selected['resolved_count']), (0, 1))
        self.assertEqual(selected['resolved_uses'][0]['reason'], 'fixed_range')
        self.assertEqual(selected['roles']['read'], 1)
        self.assertEqual(selected['possible_count'], 0)
        self.assertTrue(selected['resolved_uses'][0]['explanation'])

    def test_dense_shared_copy_range_short_circuits_filters_but_keeps_full_selected_counts(self) -> None:
        leaves = ('<ArrayMember Name="Data" DataType="DINT" Dimensions="64">' +
                  ''.join(f'<Element Index="[{i}]" Value="0"/>' for i in range(64)) + '</ArrayMember>')
        index = build(field_inputs(('COP(Local:1:I.Data[0],Buffer[0],64);',) * 60,
            modules=module('DenseCard', 1, 'INVENTED', data=leaves),
            extra_tags='<Tag Name="Buffer" DataType="DINT" Dimensions="64"/>'))
        with patch.object(index._range_resolver, 'match', wraps=index._range_resolver.match) as match:
            for i in range(64):
                self.assertEqual(index.status(address(index, f'Local:1:I.Data[{i}]')), 'referenced')
            self.assertEqual(match.call_count, 63)
        row = address(index, 'Local:1:I.Data[1]')
        summary = index.summary(row)
        self.assertEqual((summary['resolved_count'], summary['resolved_rung_count']), (60, 60))
        self.assertEqual(len(summary['resolved_uses']), 12)
        self.assertTrue(summary['resolved_uses_truncated'])
        self.assertEqual(len(list(index.resolved_references(row))), 60)

    def test_unknown_parent_semantics_and_masked_operations_explain_parser_gap(self) -> None:
        for text in ('Mystery(Local:1:I.Data);', 'MVM(InternalReal,0,Local:1:I.Data);'):
            with self.subTest(text=text):
                index = build(field_inputs((text,)))
                result = index.summary(address(index, 'Local:1:I.Data.0'))
                self.assertEqual(result['status'], 'possible_indirect')
                self.assertEqual(result['resolved_count'], 0)
                self.assertIn('parser has not established which members', result['detail'])
                self.assertIn('Local:1:I.Data', result['detail'])

    def test_dynamic_member_and_multidimensional_literal_parts_exclude_siblings(self) -> None:
        from plc_workbench.workspace_signal_usage import _dynamic_matches
        for source, target, expected in (
                ('.Data[Index].Value', '.data[0].value', True),
                ('.Data[Index].Value', '.data[0].status', False),
                ('.Data[1,Index]', '.data[1,0]', True),
                ('.Data[01,Index]', '.data[1,0]', True),
                ('.Data[1,Index]', '.data[2,0]', False),
                ('.Data[1,Index]', '.data[1]', False),
                ('.Data[Index].Value', '.data[0]', True)):
            with self.subTest(source=source, target=target):
                self.assertEqual(_dynamic_matches(source, target), expected)

    def test_equivalent_numeric_spellings_resolve_without_changing_source_or_matching_other_indices(self) -> None:
        leaves = ('<ArrayMember Name="Data" DataType="REAL" Dimensions="11">'
                  '<Element Index="[1]" Value="0"/><Element Index="[10]" Value="0"/></ArrayMember>')
        for spelling in ('[ 1 ]', '[01]'):
            with self.subTest(spelling=spelling):
                index = build(field_inputs((f'MOV(Local:1:I.Data{spelling},InternalReal);',),
                    modules=module('ArrayCard', 1, 'INVENTED', data=leaves)))
                before = deepcopy(index.io.addresses)
                result = index.summary(address(index, 'Local:1:I.Data[1]'))
                self.assertEqual(result['status'], 'referenced')
                self.assertEqual(result['direct_count'], 0)
                self.assertEqual(result['resolved_uses'][0]['reason'], 'equivalent_static_index')
                self.assertEqual(result['resolved_uses'][0]['variable'], f'Local:1:I.Data{spelling}')
                self.assertEqual(index.status(address(index, 'Local:1:I.Data[10]')), 'not_found')
                self.assertEqual(index.io.addresses, before)
        index = build(field_inputs(('XIC(Local:1:I.Data.01);',), extra_tags=(
            '<Tag Name="FirstBit" TagType="Alias" AliasFor="Local:1:I.Data.1"/>'
            '<Tag Name="TenthBit" TagType="Alias" AliasFor="Local:1:I.Data.10"/>')))
        self.assertEqual(index.status(address(index, 'Local:1:I.Data.1')), 'referenced')
        self.assertEqual(index.status(address(index, 'Local:1:I.Data.10')), 'not_found')

    def test_missing_access_or_unsupported_roles_do_not_hide_scan_results(self) -> None:
        captured = field_inputs(('XIC(InputAlias);',))
        index = build(captured, missing_access=True)
        result = index.summary(address(index, 'Local:1:I.Data.0'))
        self.assertEqual(result['status'], 'referenced')
        self.assertEqual(result['roles']['unknown'], 1)
        self.assertIn('missing_access', result['gap_reasons'])
        self.assertEqual(index.status(address(index, 'Local:3:I.Ch0Data')), 'not_found')
        self.assertTrue(index.scan_summary()['complete'])
        self.assertEqual(index.scan_summary()['role_gap_reasons'], ['missing_access'])
        index = build(field_inputs(('Mystery(InternalReal);', 'XIC(InputAlias);')))
        self.assertEqual(index.status(address(index, 'Local:1:I.Data.0')), 'referenced')
        absent = index.summary(address(index, 'Local:3:I.Ch0Data'))
        self.assertEqual(absent['status'], 'not_found')
        self.assertFalse(absent['coverage_complete'])
        self.assertIn('unsupported_instructions', absent['gap_reasons'])
        self.assertTrue(index.scan_summary()['complete'])
        self.assertEqual(index.scan_summary()['role_gap_reasons'], ['unsupported_instructions'])

    def test_unseen_non_rll_protected_and_incomplete_routines_make_absence_unknown(self) -> None:
        source = field_inputs(())[0].data
        variants = [
            ('unsupported_routines', source.replace(b'Type="RLL"', b'Type="ST"')),
            ('unsupported_routines', source.replace(b'Type="RLL"', b'Type="SFC"')),
            ('unsupported_routines', source.replace(b'Type="RLL"', b'Type="FBD"')),
            ('protected_logic', source.replace(b'<RLLContent></RLLContent>', b'<EncodedData>Invented</EncodedData>')),
            ('incomplete_routines', source.replace(b'<RLLContent></RLLContent>', b'')),
        ]
        for reason, xml in variants:
            with self.subTest(reason=reason, source=xml[:20]):
                index = build(recapture(xml))
                self.assertEqual(len(index.base._rungs), 0)
                result = index.summary(address(index, 'Local:1:I.Data.0'))
                self.assertEqual(result['status'], 'unknown')
                self.assertIn(reason, result['gap_reasons'])

    def test_no_routines_are_unknown_but_partial_exports_report_the_captured_scan(self) -> None:
        source = field_inputs(())[0].data
        without_program = re.sub(rb'<Programs>.*?</Programs>', b'<Programs/>', source)
        index = build(recapture(without_program))
        result = index.summary(address(index, 'Local:1:I.Data.0'))
        self.assertEqual(result['status'], 'unknown')
        self.assertIn('missing_logic', result['gap_reasons'])
        for target in (b'Routine', b'Module', b'Program'):
            with self.subTest(target=target):
                partial = source.replace(b'<RSLogix5000Content>',
                    b'<RSLogix5000Content TargetType="' + target + b'" ContainsContext="true">')
                result = build(recapture(partial))
                self.assertEqual(result.status(address(result, 'Local:1:I.Data.0')), 'not_found')
                self.assertIn('partial_export', result.gap_reasons)
                self.assertTrue(result.scan_summary()['available'])
                self.assertFalse(result.scan_summary()['complete'])

    def test_unresolved_internal_name_does_not_hide_unrelated_presence_or_absence(self) -> None:
        index = build(field_inputs(('XIC(MissingInternal);', 'XIC(InputAlias);')))
        self.assertEqual(index.status(address(index, 'Local:1:I.Data.0')), 'referenced')
        self.assertEqual(index.status(address(index, 'Local:3:I.Ch0Data')), 'not_found')
        self.assertEqual(index.scan_summary(), {'rungs_total': 2, 'rungs_scanned': 2,
            'rungs_not_scanned': 0, 'available': True, 'complete': True,
            'gap_reasons': [], 'role_gap_reasons': ['unresolved_references']})

    def test_resolved_internal_dynamic_reference_is_a_scanned_address(self) -> None:
        index = build(field_inputs(('MOV(InternalArray[Index],InternalReal);',), extra_tags=(
            '<Tag Name="InternalArray" DataType="REAL" Dimensions="4"/>'
            '<Tag Name="Index" DataType="DINT"/>')))
        self.assertEqual(index.status(address(index, 'Local:1:I.Data.0')), 'not_found')
        self.assertEqual(index.scan_summary()['gap_reasons'], [])
        self.assertTrue(index.scan_summary()['complete'])
        self.assertEqual(index.scan_summary()['rungs_scanned'], 1)

    def test_unvisited_array_index_dependencies_are_a_real_scan_gap(self) -> None:
        leaves = ('<ArrayMember Name="Data" DataType="DINT" Dimensions="2">'
                  '<Element Index="[0]" Value="0"/><Element Index="[1]" Value="0"/></ArrayMember>'
                  '<DataValueMember Name="Ch0Data" DataType="DINT" Value="0"/>')
        cards = module('ArrayCard', 1, 'INVENTED', data=leaves) + module('Other', 2, 'INVENTED', data=leaves)
        tags = ('<Tag Name="FieldIndex" TagType="Alias" AliasFor="Local:2:I.Ch0Data"/>'
                '<Tag Name="Index" DataType="DINT"/>')
        for token in ('Local:2:I.Ch0Data', 'FieldIndex', 'MissingIndex', 'Index+1'):
            for operation in ('MOV({operand},InternalReal);', 'Mystery({operand});',
                              'CPT(InternalReal,{operand}+1);'):
                with self.subTest(token=token, operation=operation):
                    text = operation.format(operand=f'Local:1:I.Data[{token}]')
                    index = build(field_inputs((text,), modules=cards, extra_tags=tags))
                    self.assertEqual(index.status(address(index, 'Local:1:I.Data[0]')), 'possible_indirect')
                    self.assertEqual(index.status(address(index, 'Local:2:I.Ch0Data')), 'not_found')
                    scan = index.scan_summary()
                    self.assertEqual(scan['rungs_scanned'], 1)
                    self.assertTrue(scan['available'])
                    self.assertFalse(scan['complete'])
                    self.assertIn('unscanned_index_expressions', scan['gap_reasons'])
        for token in ('Index', 'InternalIndexAlias'):
            with self.subTest(safe_internal=token):
                index = build(field_inputs((f'MOV(Local:1:I.Data[{token}],InternalReal);',),
                    modules=cards, extra_tags=tags +
                    '<Tag Name="InternalIndexAlias" TagType="Alias" AliasFor="Index"/>'))
                self.assertTrue(index.scan_summary()['complete'])

    def test_unknown_instruction_and_arity_still_capture_exact_lexical_alias_references(self) -> None:
        captured = field_inputs(('Mystery(InputAlias);', 'Mystery(Local:1:I.Data.0);',
                                 'XIC(InputAlias,InternalReal);'))
        index = build(captured)
        summary = index.summary(address(index, 'Local:1:I.Data.0'))
        self.assertEqual(summary['status'], 'referenced')
        self.assertEqual(summary['direct_count'], 3)
        self.assertEqual(summary['roles'], {'read': 0, 'write': 0, 'read_write': 0, 'unknown': 3})
        self.assertTrue(index.scan_summary()['complete'])
        self.assertEqual(index.scan_summary()['role_gap_reasons'], ['unsupported_instructions'])
        missing = build(captured, missing_access=True)
        self.assertEqual(missing.summary(address(missing, 'Local:1:I.Data.0'))['direct_count'], 3)
        self.assertTrue(missing.scan_summary()['complete'])

    def test_extended_access_binds_counter_member_without_changing_saved_reference_records(self) -> None:
        captured = field_inputs(('CTU(InputAlias,10,0);',))
        before = deepcopy(wire(captured))
        index = build(captured)
        summary = index.summary(address(index, 'Local:1:I.Data.0'))
        self.assertEqual((summary['status'], summary['direct_count']), ('referenced', 1))
        self.assertEqual(summary['roles']['read_write'], 1)
        self.assertTrue(index.scan_summary()['complete'])
        self.assertEqual(wire(captured), before)

    def test_partial_rung_parse_and_opaque_expression_report_limits_once_without_hiding_absence(self) -> None:
        index = build(field_inputs(('XIC(InputAlias);', 'XIC(InputAlias')))
        summary = index.scan_summary()
        self.assertEqual((summary['rungs_total'], summary['rungs_scanned'], summary['rungs_not_scanned']), (2, 1, 1))
        self.assertFalse(summary['complete'])
        self.assertTrue(summary['available'])
        self.assertIn('unparsed_rungs', summary['gap_reasons'])
        self.assertEqual(index.status(address(index, 'Local:3:I.Ch0Data')), 'not_found')
        summary['gap_reasons'].clear()
        self.assertIn('unparsed_rungs', index.scan_summary()['gap_reasons'])
        index = build(field_inputs(('CPT(InternalReal,InputAlias?Other);',)))
        self.assertEqual(index.status(address(index, 'Local:1:I.Data.0')), 'not_found')
        self.assertIn('opaque_expressions', index.scan_summary()['gap_reasons'])
        self.assertFalse(index.scan_summary()['complete'])

    def test_failed_or_foreign_rungs_do_not_create_positive_evidence(self) -> None:
        for captured, reason in ((field_inputs(('XIC(InputAlias',)), 'unparsed_rungs'),
                (recapture(field_inputs(('XIC(InputAlias);',))[0].data.replace(b'<Rung ',
                    b'<Rung xmlns:x="urn:other" x:Flag="foreign" ')), 'unqualified_source')):
            with self.subTest(reason=reason):
                index = build(captured)
                result = index.summary(address(index, 'Local:1:I.Data.0'))
                self.assertEqual(result['status'], 'unknown')
                self.assertEqual(result['direct_count'], 0)
                self.assertIn(reason, result['gap_reasons'])

    def test_resolved_previews_are_bounded_detached_and_counts_remain_complete(self) -> None:
        index = build(field_inputs(('MOV(Local:1:I.Data,InternalReal);',) * 30))
        row = address(index, 'Local:1:I.Data.0')
        result = index.summary(row)
        self.assertEqual((result['resolved_count'], result['resolved_rung_count']), (30, 30))
        self.assertEqual(len(result['resolved_uses']), 12)
        self.assertTrue(result['resolved_uses_truncated'])
        self.assertEqual(result['possible_preview_limit'], 12)
        self.assertEqual([item['rung_number'] for item in result['resolved_uses']], [str(i) for i in range(12)])
        result['resolved_uses'][0]['variable'] = 'Changed'
        self.assertEqual(index.summary(row)['resolved_uses'][0]['variable'], 'Local:1:I.Data')
        with patch.object(index, 'summary', side_effect=AssertionError('summary materialized')):
            self.assertEqual(index.status(row), 'referenced')

    def test_auxiliary_limit_fails_to_uncertainty_without_losing_exact_positives(self) -> None:
        captured = field_inputs(('XIC(InputAlias);',))
        with patch('plc_workbench.workspace_signal_usage.MAX_INDEX_BYTES', 1):
            index = build(captured)
        self.assertLessEqual(index._budget, 1)
        self.assertEqual(index.status(address(index, 'Local:1:I.Data.0')), 'referenced')
        result = index.summary(address(index, 'Local:3:I.Ch0Data'))
        self.assertEqual(result['status'], 'unknown')
        self.assertIn('usage_index_limit', result['gap_reasons'])
        with self.assertRaises(ValueError):
            index.summary({'id': 'made-up', 'root_id': 'made-up', 'suffix': ''})


if __name__ == '__main__':
    unittest.main()
