"""Invented timers, counters and reset uses challenge source-only association."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access, render_access_json
from plc_workbench.calculations import analyze_calculations
from plc_workbench.conditions import analyze_conditions, render_conditions_json
from plc_workbench.references import analyze_references
from plc_workbench.relationships import analyze_relationships, render_relationships_json
from plc_workbench.rung_analysis import analyze_rungs
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.tag_data import analyze_tag_data
from plc_workbench.stateful_objects import (StatefulObjectError, analyze_stateful_objects,
    render_stateful_objects_json, validate_stateful_objects)
from test_relationships import capture as capture_relationships, tag
from test_module_io import LOCAL, module, communications


def typed_tag(name: str, datatype: str = 'TIMER', dimensions: str = '', data: str = '') -> str:
    return f'<Tag Name="{name}" TagType="Base" DataType="{datatype}" Dimensions="{dimensions}">{data}</Tag>'


def capture(texts=('XIC(A)TON(T,?,?);', 'XIC(T.DN)RES(T);'), **kwargs):
    kwargs.setdefault('tags', tag('A') + tag('B') + typed_tag('T') + typed_tag('C', 'COUNTER') + typed_tag('R', 'CONTROL'))
    args = capture_relationships(texts, **kwargs)
    conditions = analyze_conditions(*args, schema_version=3)
    tag_data = analyze_tag_data(*args[:2])
    return (*args, conditions, tag_data, analyze_stateful_objects(*args, conditions, tag_data))


def capture_xml(xml: str):
    snapshot = snapshot_from_bytes(xml.encode())
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    calculations = analyze_calculations(snapshot, inventory, references)
    access = analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
    rungs = analyze_rungs(snapshot, inventory, references, access, calculations)
    relationships = analyze_relationships(snapshot, inventory, references, access, calculations, rungs)
    args = (snapshot, inventory, references, access, calculations, rungs, relationships)
    conditions = analyze_conditions(*args, schema_version=3)
    tag_data = analyze_tag_data(snapshot, inventory)
    return (*args, conditions, tag_data, analyze_stateful_objects(*args, conditions, tag_data))


def namespace(xml: str) -> str:
    return xml.replace('<RSLogix5000Content>', '<RSLogix5000Content xmlns:x="urn:foreign-invented">')


def decorated(datatype: str = 'TIMER', value: str = '712345') -> str:
    return (f'<Data Format="Decorated"><Structure DataType="{datatype}">'
        f'<DataValueMember Name="PRE" DataType="DINT" Value="{value}"/>'
        '<DataValueMember Name="ACC" DataType="DINT" Value="17"/>'
        '</Structure></Data>')


class StatefulObjectTests(unittest.TestCase):
    def test_all_six_opcodes_keep_occurrences_and_existing_evidence(self) -> None:
        args = capture(('TON(T,?,?)TOF(T,0,0)RTO(T,1,2);', 'CTU(C,?,?)CTD(C,3,4)RES(C);'))
        before = (render_access_json(args[3]), render_relationships_json(args[6]), render_conditions_json(args[7]))
        result = args[-1]
        self.assertEqual(result.coverage['occurrences_by_opcode'], dict.fromkeys(('CTD', 'CTU', 'RES', 'RTO', 'TOF', 'TON'), 1))
        self.assertEqual(len(result.objects), 2)
        self.assertEqual([row['family'] for row in result.objects], ['timer', 'counter'])
        self.assertEqual(result.coverage['producer_occurrences'], 5)
        self.assertEqual(result.coverage['matched_reset_occurrences'], 1)
        self.assertEqual(result.coverage['objects_with_multiple_producers'], 2)
        self.assertEqual(len(result.address_uses), 2)
        self.assertEqual(sum(result.coverage['accepted_operands_by_role'].values()), 6)
        self.assertEqual(result.execution_analysis, 'not_implemented')
        validate_stateful_objects(*args)
        self.assertEqual(result.to_dict(), json.loads(render_stateful_objects_json(result)))
        self.assertEqual(before, (render_access_json(args[3]), render_relationships_json(args[6]), render_conditions_json(args[7])))

    def test_incoming_context_uses_exact_branch_dag_and_not_own_behavior(self) -> None:
        args = capture(('[XIC(A)TON(T,?,?),XIO(B)CTU(C,?,?)]RES(T);', 'TOF(T,?,?);'))
        nodes = {row['id']: row for row in args[7].nodes}
        first, second, join, tof = args[-1].occurrences
        self.assertNotEqual(first['guard_id'], second['guard_id'])
        self.assertTrue(nodes[join['guard_id']]['has_branch'])
        self.assertEqual(tof['context_status'], 'modeled')
        self.assertEqual(nodes[tof['guard_id']]['kind'], 'entry')
        self.assertTrue(args[-1].objects[0]['has_tof_reset'])

    def test_guard_gaps_stateful_and_opaque_are_explicit(self) -> None:
        result = capture(('XIC(Missing)TON(T,?,?);', 'ONS(A)CTU(C,?,?);', 'MYSTERY(A)RES(T);'))[-1]
        self.assertEqual([row['context_status'] for row in result.occurrences], ['binding_gaps', 'stateful', 'opaque'])
        self.assertEqual(result.status, 'partial')

    def test_bad_signatures_unbound_dynamic_and_invalid_expansion_are_retained(self) -> None:
        tags = typed_tag('T') + tag('A') + tag('Bit', 'T.1')
        result = capture(('TON()CTU(C,?,?)RES(Missing)RTO(T[A],?,?)TON(Bit.Member,?,?)TOF(T,bad,?);',), tags=tags)[-1]
        self.assertEqual(len(result.occurrences), 6)
        self.assertEqual([row['target_status'] for row in result.occurrences],
            ['signature_unresolved', 'unbound', 'unbound', 'unbound', 'identity_gap', 'signature_unresolved'])
        self.assertEqual(result.objects, [])
        self.assertTrue(all(row['control_address_id'] is None for row in result.occurrences))

    def test_alias_exact_suffix_static_array_and_case_never_collapse(self) -> None:
        tags = tag('A') + typed_tag('T', dimensions='2') + tag('Alias', 'T[0]')
        result = capture(('TON(Alias,?,?)RES(T[0])TON(T[00],?,?)TON(T[1],?,?)TON(T[2],?,?)TON(T[ 0 ],?,?);',
                          'XIC(T[0].DN)XIC(T[00].dn)XIC(T[1].DN);'), tags=tags)[-1]
        self.assertEqual([row['suffix'] for row in result.objects], ['[0]', '[00]', '[1]', '[2]', '[ 0 ]'])
        self.assertEqual(result.objects[0]['reset_ids'], [result.occurrences[1]['id']])
        self.assertEqual(result.coverage['bounds_by_status']['static_in_bounds'], 4)
        self.assertEqual(result.coverage['bounds_by_status']['static_out_of_bounds'], 1)
        self.assertEqual(result.coverage['members_by_status']['known'], 3)
        self.assertEqual(result.coverage['members_by_status']['unknown'], 0)

    def test_very_long_static_index_is_retained_out_of_bounds_without_integer_conversion(self) -> None:
        index = '9' * 5000
        result = capture((f'TON(T[{index}],?,?);',), tags=typed_tag('T', dimensions='2'))[-1]
        self.assertEqual(result.objects[0]['suffix'], f'[{index}]')
        self.assertEqual(result.objects[0]['bounds_status'], 'static_out_of_bounds')

    def test_nested_declared_control_member_relationships_stay_unresolved(self) -> None:
        result = capture(('TON(T.Nested,?,?)RES(T.Nested)XIC(T.Nested.DN)XIC(T.DN)TON(T.DN,?,?);',))[-1]
        self.assertEqual(len(result.objects), 2)
        self.assertTrue(all(row['declaration_kind'] == 'unresolved' for row in result.objects))
        self.assertTrue(all(row['bounds_status'] == 'unresolved' for row in result.objects))
        self.assertEqual(result.address_uses[1]['member'], 'DN')
        self.assertEqual(result.status, 'partial')

    def test_ascii_catalogue_case_does_not_merge_exact_source_identities(self) -> None:
        result = capture(('TON(T,?,?)XIC(T.DN)XIC(T.dn)XIC(T.\u0131n);',),
            tags=typed_tag('T', 'timer', data=decorated('TiMeR')))[-1]
        self.assertEqual(result.objects[0]['declaration_kind'], 'timer')
        self.assertFalse(result.objects[0]['type_conflict'])
        members = [row for row in result.address_uses if row['kind'] == 'direct_member']
        self.assertEqual([row['member'] for row in members], ['DN', 'dn'])
        self.assertNotEqual(members[0]['address_id'], members[1]['address_id'])
        self.assertTrue(all(row['member_status'] == 'known' for row in members))
        self.assertEqual(result.coverage['stored_types_by_status']['matching'], 3)

    def test_reset_only_control_timer_t_and_type_conflicting_families(self) -> None:
        tags = typed_tag('T') + typed_tag('TT', 'TIMER_T') + typed_tag('R', 'CONTROL') + tag('A')
        result = capture(('RES(R)RES(T)TON(TT,?,?)TON(T,?,?)CTU(T,?,?)TON(A,?,?)XIC(T.CU);',), tags=tags)[-1]
        by_kind = {row['declaration_kind']: row for row in result.objects}
        self.assertFalse(by_kind['control']['type_conflict'])
        self.assertEqual(by_kind['control']['family'], 'reset_only')
        self.assertEqual(result.coverage['objects_by_family']['mixed'], 1)
        self.assertEqual(result.coverage['objects_with_type_conflicts'], 2)
        self.assertEqual(result.coverage['unmatched_reset_occurrences'], 1)
        self.assertEqual(result.coverage['matched_reset_occurrences'], 1)
        self.assertEqual(result.coverage['members_by_status']['known'], 1)

    def test_whole_member_unknown_expression_and_external_writes(self) -> None:
        result = capture(('TON(T,?,?)RES(T)MOV(10,T.PRE)ADD(T.ACC,1,B)CPT(B,T.ACC+T.ACC)'
                          'XIC(T.DN)ONS(T.EN)PID(T,A,B,C,0,0,0)MOV(A,T.Odd.Member)MOV(T,B);',))[-1]
        self.assertEqual(result.coverage['accepted_expression_uses'], 2)
        self.assertEqual(result.coverage['accepted_operands_by_role']['unknown'], 1)
        self.assertEqual(result.coverage['uses_by_kind']['other_member'], 1)
        whole = next(row for row in result.address_uses if row['kind'] == 'whole_control')
        self.assertEqual(len(whole['read_operand_ids']), 1)
        self.assertEqual(len(whole['read_write_operand_ids']), 1)
        self.assertEqual(len(whole['unknown_operand_ids']), 1)
        self.assertTrue(all('producer_id' not in row and 'consumer_id' not in row for row in result.address_uses))

    def test_scope_shadowing_uses_target_identity(self) -> None:
        xml = capture(('TON(T,?,?);',))[0].data.decode()
        xml = xml.replace('<Program Name="P">', '<Program Name="P"><Tags>' + typed_tag('T') + '</Tags>')
        program = xml[xml.index('<Program Name="P">'):xml.index('</Programs>')]
        xml = xml.replace('</Programs>', program.replace('Name="P"', 'Name="Q"') + '</Programs>')
        result = capture_xml(xml)[-1]
        self.assertEqual(len(result.objects), 2)
        self.assertNotEqual(result.objects[0]['target_id'], result.objects[1]['target_id'])

    def test_namespace_alias_data_type_dimensions_and_ancestry_withhold_controls(self) -> None:
        xml = namespace(capture(('TON(Bad,?,?)RES(T);',), tags=typed_tag('T') + tag('Bad', 'T'))[0].data.decode())
        for modified in (xml.replace('AliasFor="T"', 'x:AliasFor="T"'),
                         xml.replace('DataType="TIMER"', 'x:DataType="TIMER"'),
                         xml.replace('Dimensions=""', 'x:Dimensions=""'),
                         xml.replace('<Program Name=', '<Program x:Name='),
                         xml.replace('<Text>', '<x:Text>').replace('</Text>', '</x:Text>')):
            result = capture_xml(modified)[-1]
            self.assertEqual(result.occurrences[0]['target_status'], 'namespace_gap')
            self.assertIsNone(result.occurrences[0]['control_address_id'])

    def test_namespace_member_expression_and_condition_are_quarantined(self) -> None:
        xml = namespace(capture(('TON(T,?,?);', 'XIC(Bad)RES(T)MOV(Bad,B)CPT(B,Bad+Bad);'),
            tags=typed_tag('T') + tag('B') + tag('Bad', 'T.DN'))[0].data.decode())
        result = capture_xml(xml.replace('AliasFor="T.DN"', 'x:AliasFor="T.DN"'))[-1]
        self.assertEqual(result.occurrences[1]['context_status'], 'namespace_gap')
        self.assertEqual(result.coverage['rejected_operands_by_role']['read'], 2)
        self.assertEqual(result.coverage['rejected_expression_uses'], 2)

    def test_implicit_module_parent_topology_qualification_is_preserved(self) -> None:
        modules = '<Modules>' + LOCAL + module(communications=communications('<OutputTag/>')) + '</Modules>'
        xml = namespace(capture(('TON(Local:3:O.Timer,?,?);',), modules=modules)[0].data.decode())
        self.assertEqual(capture_xml(xml)[-1].occurrences[0]['target_status'], 'exact_address')
        for modified in (xml.replace(' Address=', ' x:Address='), xml.replace('ParentModule="Local"', 'x:ParentModule="Local"')):
            self.assertEqual(capture_xml(modified)[-1].occurrences[0]['target_status'], 'namespace_gap')

    def test_stored_representations_keep_duplicates_values_and_mismatches_separate(self) -> None:
        data = decorated() + decorated('COUNTER', '923456') + '<DefaultData Format="L5K">[987654]</DefaultData>'
        args = capture(('TON(T,123,456);',), tags=typed_tag('T', data=data))
        result = args[-1]
        self.assertEqual(len(result.objects[0]['content_ids']), 3)
        self.assertEqual(len(result.stored_data), 6)
        self.assertEqual(result.coverage['stored_types_by_status'], {'matching': 3, 'mismatch': 3, 'unresolved': 0})
        private = render_stateful_objects_json(result)
        for value in ('712345', '923456', '987654'):
            self.assertNotIn(value, private)
        self.assertTrue(all(row['element_id'] in {item['id'] for item in args[8].elements} for row in result.stored_data))
        self.assertEqual(sum(result.coverage['accepted_operands_by_role'].values()), 1)
        self.assertEqual(result.status, 'partial')

    def test_data_array_spelling_and_nested_structure_paths_are_literal(self) -> None:
        data = ('<Data Format="Decorated"><Array DataType="TIMER" Dimensions="2">'
                '<Element Index="[0]"><Structure DataType="TIMER"><DataValueMember Name="ACC" Value="1"/></Structure></Element>'
                '<Element Index="[1]"><Structure DataType="TIMER"><DataValueMember Name="ACC" Value="2"/></Structure></Element>'
                '</Array></Data>')
        args = capture(('TON(T[0],?,?)TON(T[00],?,?)TON(T[1],?,?);',), tags=typed_tag('T', dimensions='2', data=data))
        first, zerozero, last = args[-1].objects
        self.assertEqual(len([row for row in args[-1].stored_data if row['object_id'] == first['id']]), 3)
        self.assertFalse(any(row['object_id'] == zerozero['id'] for row in args[-1].stored_data))
        self.assertEqual(len([row for row in args[-1].stored_data if row['object_id'] == last['id']]), 3)
        nested = '<Data Format="Decorated"><Structure DataType="Invented"><StructureMember Name="Clock" DataType="TIMER"><DataValueMember Name="PRE" Value="11"/></StructureMember></Structure></Data>'
        result = capture(('TON(T.Clock,?,?);',), tags=typed_tag('T', 'Invented', data=nested))[-1]
        self.assertEqual(len(result.stored_data), 2)
        self.assertTrue(all(row['type_status'] == 'unresolved' for row in result.stored_data))

    def test_namespaced_storage_never_becomes_qualified_member_settings(self) -> None:
        xml = namespace(capture(('TON(T,?,?);',), tags=typed_tag('T', data=decorated()))[0].data.decode())
        for modified in (xml.replace('<Structure ', '<x:Structure ').replace('</Structure>', '</x:Structure>'),
                         xml.replace('DataType="TIMER">', 'x:DataType="TIMER">'),
                         xml.replace(' Value=', ' x:Value=')):
            result = capture_xml(modified)[-1]
            self.assertGreater(result.coverage['stored_data_by_status']['namespace_gap'], 0)
            self.assertEqual(result.coverage['stored_types_by_status']['mismatch'], 0)

    def test_namespace_prior_branch_does_not_taint_sibling(self) -> None:
        xml = namespace(capture(('[XIC(Bad)TON(T,?,?),XIC(A)CTU(C,?,?)]RES(T);',),
            tags=tag('A') + typed_tag('T') + typed_tag('C', 'COUNTER') + tag('Bad', 'A'))[0].data.decode())
        result = capture_xml(xml.replace('AliasFor="A"', 'x:AliasFor="A"'))[-1]
        self.assertEqual([row['context_status'] for row in result.occurrences], ['namespace_gap', 'modeled', 'namespace_gap'])

    def test_malformed_stored_shape_is_separate_from_namespace_uncertainty(self) -> None:
        data = '<Data Format="Decorated"><Structure DataType="TIMER"><DataValueMember Name="PRE"/></Structure></Data>'
        result = capture(('TON(T,?,?);',), tags=typed_tag('T', data=data))[-1]
        self.assertEqual(result.coverage['stored_data_by_status'], {'namespace_gap': 0, 'qualified': 1, 'shape_gap': 1})
        self.assertEqual(result.stored_data[-1]['type_status'], 'unresolved')
        self.assertEqual(result.status, 'partial')

    def test_empty_unparsed_lowercase_and_complete_source_cases(self) -> None:
        self.assertEqual(capture((';',))[-1].status, 'complete')
        self.assertEqual(capture(('ton(T,?,?);',))[-1].status, 'complete')
        result = capture(('BROKEN(', 'res(R);'))[-1]
        self.assertEqual(result.coverage['unparsed_rungs'], 1)
        self.assertEqual(result.occurrences[0]['opcode'], 'RES')
        self.assertEqual(result.status, 'partial')

    def test_shared_controls_and_many_member_reads_retain_linear_evidence(self) -> None:
        texts = tuple('TON(T,?,?)RES(T)XIC(T.DN)CPT(B,T.ACC+T.ACC);' for _ in range(80))
        result = capture(texts)[-1]
        self.assertEqual(len(result.occurrences), 160)
        self.assertEqual(len(result.objects), 1)
        self.assertEqual(len(result.address_uses), 3)
        self.assertEqual(result.coverage['accepted_expression_uses'], 160)
        smaller = capture(texts[:20])[-1]
        self.assertLess(len(render_stateful_objects_json(result)), 4 * len(render_stateful_objects_json(smaller)))

    def test_canonical_validation_rejects_tampered_source_links_counts_and_prior_data(self) -> None:
        args = capture(tags=tag('A') + typed_tag('T', data=decorated()))
        for mutate in (lambda r: r.occurrences[0].update(guard_id='invented'),
                       lambda r: r.objects[0].update(type_conflict=True),
                       lambda r: r.address_uses[0]['read_write_operand_ids'].clear(),
                       lambda r: r.stored_data[0].update(type_status='mismatch'),
                       lambda r: r.coverage.update(source_rungs=True)):
            broken = deepcopy(args[-1])
            mutate(broken)
            with self.assertRaises(StatefulObjectError) as caught:
                validate_stateful_objects(*args[:-1], broken)
            self.assertNotIn('invented', str(caught.exception))
        with self.assertRaises(StatefulObjectError):
            analyze_stateful_objects(*args[:8], replace(args[8], status='invented'))
        with self.assertRaises(StatefulObjectError):
            analyze_stateful_objects(*args[:7], analyze_conditions(*args[:7], schema_version=2), args[8])

    def test_budget_limits_cycles_types_and_deterministic_serialization(self) -> None:
        args = capture()
        for constant in ('MAX_STATEFUL_OBJECT_RECORDS', 'MAX_STATEFUL_OBJECT_BYTES', 'MAX_STATEFUL_OBJECT_JSON_BYTES'):
            with patch(f'plc_workbench.stateful_objects.{constant}', 1), self.assertRaises(StatefulObjectError):
                analyze_stateful_objects(*args[:-1])
        broken = deepcopy(args[-1])
        broken.occurrences.append(broken.occurrences)
        with self.assertRaises(StatefulObjectError):
            render_stateful_objects_json(broken)
        broken = deepcopy(args[-1])
        broken.coverage['source_rungs'] = object()
        with self.assertRaises(StatefulObjectError):
            render_stateful_objects_json(broken)
        self.assertEqual(render_stateful_objects_json(args[-1]), render_stateful_objects_json(analyze_stateful_objects(*args[:-1])))


if __name__ == '__main__':
    unittest.main()
