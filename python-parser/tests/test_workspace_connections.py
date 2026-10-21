"""Synthetic exports exercise connection joins, fanout and evidence failures."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access
from plc_workbench.calculations import analyze_calculations
from plc_workbench.references import analyze_references
from plc_workbench.relationships import analyze_relationships
from plc_workbench.rung_analysis import analyze_rungs
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.workspace_connections import (
    ConnectionError, ConnectionIndex, ENDPOINT_PAGE_SIZE, SIGNAL_PAGE_SIZE,
)
from test_relationships import capture, tag


def build(inputs) -> ConnectionIndex:
    _, inventory, references, access, calculations, _, relationships = inputs
    return ConnectionIndex(inventory, references, access, relationships, calculations)


def wire_inputs(inputs) -> list[dict]:
    _, inventory, references, access, calculations, _, relationships = inputs
    return [json.loads(json.dumps(asdict(value)))
            for value in (inventory, references, access, relationships, calculations)]


def signal(view: dict, label: str) -> dict:
    return next(row for row in view['signals'] if row['label'] == label)


def multi_routine(programs: str, tags: str = '', extra: str = ''):
    xml = (f'<RSLogix5000Content><Controller Name="C"><Tags>{tags}</Tags>'
           f'<Programs>{programs}</Programs>{extra}</Controller></RSLogix5000Content>')
    snapshot = snapshot_from_bytes(xml.encode())
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    calculations = analyze_calculations(snapshot, inventory, references)
    access = analyze_access(inventory, references, schema_version=4,
                            snapshot=snapshot, calculations=calculations)
    rungs = analyze_rungs(snapshot, inventory, references, access, calculations)
    relationships = analyze_relationships(snapshot, inventory, references, access, calculations, rungs)
    return snapshot, inventory, references, access, calculations, rungs, relationships


def routine(name: str, text: str) -> str:
    return (f'<Routine Name="{name}" Type="RLL"><RLLContent><Rung Number="0" Type="N">'
            f'<Text><![CDATA[{text}]]></Text></Rung></RLLContent></Routine>')


class ConnectionIndexTests(unittest.TestCase):
    def test_output_fans_to_three_distinct_rungs_and_one_source_node(self) -> None:
        inputs = capture(('MOV(A,B);', 'XIC(B)OTE(C);', 'XIO(B)OTE(D);', 'EQU(B,1)OTE(T);'))
        index = build(inputs)
        view = index.view(inputs[1].rungs[0].id)
        output = signal(view, 'B')
        self.assertEqual([row['id'] for row in output['readers']], [rung.id for rung in inputs[1].rungs[1:]])
        self.assertEqual(output['counts']['readers'], 3)
        self.assertEqual(output['counts']['writer_instructions'], 1)
        self.assertTrue(output['output'])
        self.assertFalse(output['input'])
        self.assertNotIn('edges', view)
        self.assertNotIn('execution_order', view)
        self.assertEqual(output['same_rung']['writes'], 1)

    def test_reverse_lookup_uses_writer_and_scope_path(self) -> None:
        inputs = capture(('MOV(A,B);', 'XIC(B)OTE(C);'))
        row = signal(build(inputs).view(inputs[1].rungs[1].id), 'B')
        self.assertEqual([endpoint['id'] for endpoint in row['writers']], [inputs[1].rungs[0].id])
        self.assertEqual(row['writers'][0]['path'], 'Invented / P / R / Rung 0')
        self.assertEqual(row['writers'][0]['use_count'], 1)
        self.assertTrue(row['input'])

    def test_cycle_is_one_hop_and_same_rung_reuse_is_separate(self) -> None:
        inputs = capture(('MOV(A,B)ADD(B,1,B);', 'MOV(B,A);'))
        index = build(inputs)
        first = index.view(inputs[1].rungs[0].id)
        second = index.view(inputs[1].rungs[1].id)
        b = signal(first, 'B')
        self.assertEqual(b['same_rung']['reads'], 1)
        self.assertEqual(b['same_rung']['writes'], 2)
        self.assertEqual(len(b['readers']), 1)
        self.assertTrue(b['counts']['multiple_writers'])
        self.assertEqual(signal(second, 'A')['readers'][0]['id'], first['focus']['id'])

    def test_multiple_writers_are_preserved_without_claiming_last_writer(self) -> None:
        inputs = capture(('MOV(A,B);', 'CLR(B);', 'XIC(B)OTE(C);'))
        row = signal(build(inputs).view(inputs[1].rungs[2].id), 'B')
        self.assertEqual(row['counts']['writer_instructions'], 2)
        self.assertTrue(row['counts']['multiple_writers'])
        self.assertEqual(len(row['writers']), 2)
        self.assertNotIn('selected_writer', row)

    def test_alias_and_exact_suffix_join_but_members_and_root_do_not(self) -> None:
        tags = tag('A') + tag('B') + tag('Alias', 'A.Member')
        inputs = capture(('MOV(B,Alias);', 'XIC(A.Member)OTE(B);', 'XIC(A)OTE(B);',
                          'XIC(A.member)OTE(B);', 'XIC(A.Other)OTE(B);'), tags=tags)
        row = signal(build(inputs).view(inputs[1].rungs[0].id), 'A.Member')
        self.assertEqual([endpoint['id'] for endpoint in row['readers']], [inputs[1].rungs[1].id])
        self.assertEqual(row['suffix'], '.Member')
        self.assertEqual(row['target_path'], 'Invented / A')

    def test_timer_root_does_not_invent_a_done_member_connection(self) -> None:
        inputs = capture(('TON(T,?,?);', 'XIC(T.DN)OTE(B);'))
        row = signal(build(inputs).view(inputs[1].rungs[0].id), 'T')
        self.assertEqual(row['readers'], [])
        self.assertEqual(row['same_rung']['reads'], 1)
        self.assertEqual(row['same_rung']['writes'], 1)

    def test_module_io_uses_authenticated_derived_name_when_entity_is_unnamed(self) -> None:
        from test_module_io import LOCAL, communications, module
        modules = '<Modules>' + LOCAL + module(communications=communications()) + '</Modules>'
        inputs = capture(('MOV(Local:3:I.Data,A);', 'MOV(Local:3:I.Data,B);'), modules=modules)
        row = signal(build(inputs).view(inputs[1].rungs[0].id), 'Local:3:I.Data')
        self.assertEqual(row['counts']['readers'], 1)
        self.assertEqual(row['suffix'], '.Data')

    def test_preserved_orphan_rung_is_a_gap_not_an_index_wide_failure(self) -> None:
        inputs = multi_routine('', extra='<Other><Rung/></Other>')
        view = build(inputs).view(inputs[1].rungs[0].id)
        self.assertEqual(view['signals'], [])
        self.assertEqual(view['coverage']['focus_parse_status'], 'preserved_unsupported')
        self.assertEqual(view['focus']['routine'], '(unassigned routine)')

    def test_identical_scoped_tag_names_never_join(self) -> None:
        programs = ''.join(f'<Program Name="{name}"><Tags>{tag("A")}</Tags><Routines>'
                           + routine('R', text) + '</Routines></Program>'
                           for name, text in [('P', 'OTE(A);'), ('Q', 'XIC(A);')])
        inputs = multi_routine(programs)
        index = build(inputs)
        first = signal(index.view(inputs[1].rungs[0].id), 'A')
        second = signal(index.view(inputs[1].rungs[1].id), 'A')
        self.assertNotEqual(first['target_id'], second['target_id'])
        self.assertNotEqual(first['target_path'], second['target_path'])
        self.assertEqual(first['readers'], [])
        self.assertEqual(second['writers'], [])

    def test_current_routine_scope_exposes_outside_endpoint_count(self) -> None:
        programs = ('<Program Name="P"><Routines>' + routine('Writer', 'OTE(A);')
                    + routine('Reader', 'XIC(A);') + '</Routines></Program>')
        inputs = multi_routine(programs, tag('A'))
        index = build(inputs)
        focus = inputs[1].rungs[0].id
        all_row = signal(index.view(focus), 'A')
        local = signal(index.view(focus, scope='routine'), 'A')
        self.assertEqual(len(all_row['readers']), 1)
        self.assertEqual(local['readers'], [])
        self.assertEqual(local['outside_counts']['readers'], 1)
        self.assertEqual(local['counts']['readers'], 1)
        self.assertEqual(local['endpoints']['totals']['readers'], 0)

    def test_cpt_reference_occurrences_join_source_spans_and_keep_repeats(self) -> None:
        inputs = capture(('MOV(A,B);', 'CPT(C,B+B+A);'))
        index = build(inputs)
        row = signal(index.view(inputs[1].rungs[0].id), 'B')
        self.assertEqual(row['readers'][0]['use_count'], 2)
        self.assertEqual(len(set(row['readers'][0]['use_ids'])), 2)
        self.assertTrue(all(identifier.startswith('calculation_node_') for identifier in row['readers'][0]['use_ids']))

    def test_unknown_roles_are_neither_inputs_nor_outputs(self) -> None:
        inputs = capture(('PID(A,B,C,D,0,0,0);', 'OTE(A);'))
        index = build(inputs)
        focus = inputs[1].rungs[0].id
        view = index.view(focus)
        row = signal(view, 'A')
        self.assertTrue(row['unknown'])
        self.assertFalse(row['input'])
        self.assertFalse(row['output'])
        self.assertEqual(row['focus_roles'], ['unknown'])
        self.assertEqual(index.view(focus, direction='inputs')['signals'], [])
        self.assertEqual(index.view(focus, direction='outputs')['signals'], [])
        self.assertEqual(view['coverage']['focus']['unknown_roles'], 7)

    def test_unparsed_unresolved_and_invalid_alias_composition_remain_gaps(self) -> None:
        inputs = capture(('XIC(A', 'MOV(Missing,B);', 'MOV(Bit.Member,B);'),
                         tags=tag('A') + tag('B') + tag('Bit', 'A.1'))
        index = build(inputs)
        first = index.view(inputs[1].rungs[0].id)
        self.assertEqual(first['signals'], [])
        self.assertEqual(first['coverage']['unparsed_rungs'], 1)
        self.assertEqual(index.view(inputs[1].rungs[1].id)['coverage']['focus']['unresolved_uses'], 1)
        self.assertEqual(index.view(inputs[1].rungs[2].id)['coverage']['focus']['invalid_expanded_addresses'], 1)

    def test_signal_pages_and_endpoint_pages_independently_reach_all_results(self) -> None:
        names = [f'T{i}' for i in range(SIGNAL_PAGE_SIZE + 3)]
        texts = [''.join(f'OTE({name})' for name in names) + ';']
        texts += [f'XIC(T0)OTE(T1);' for _ in range(ENDPOINT_PAGE_SIZE + 3)]
        inputs = capture(tuple(texts), tags=''.join(tag(name) for name in names))
        index = build(inputs)
        focus = inputs[1].rungs[0].id
        first = index.view(focus)
        second = index.view(focus, page=2)
        self.assertEqual(first['pagination']['total'], len(names))
        self.assertEqual(len(first['signals']), SIGNAL_PAGE_SIZE)
        self.assertEqual(len(second['signals']), 3)
        row = signal(first, 'T0')
        next_endpoint = index.view(focus, signal_id=row['id'], endpoint_page=2)['signals'][0]
        self.assertEqual(len(row['readers']), ENDPOINT_PAGE_SIZE)
        self.assertEqual(len(next_endpoint['readers']), 3)
        reached = {endpoint['id'] for endpoint in row['readers'] + next_endpoint['readers']}
        self.assertEqual(reached, {rung.id for rung in inputs[1].rungs[1:]})
        self.assertFalse(next_endpoint['endpoints']['has_more'])
        self.assertEqual(next_endpoint['endpoints']['offset'], ENDPOINT_PAGE_SIZE)

    def test_json_input_and_returned_view_cannot_mutate_index(self) -> None:
        inputs = capture(('MOV(A,B);', 'XIC(B)OTE(C);'))
        wires = wire_inputs(inputs)
        index = ConnectionIndex(*wires)
        focus = inputs[1].rungs[0].id
        expected = index.view(focus)
        wires[0]['rungs'].clear()
        wires[3]['addresses'].clear()
        changed = index.view(focus)
        changed['signals'][0]['same_rung']['read_use_ids'].clear()
        changed['focus']['path'] = 'wrong'
        self.assertEqual(index.view(focus), expected)

    def test_navigation_never_replays_authentication_or_analysis(self) -> None:
        inputs = capture(('MOV(A,B);', 'XIC(B)OTE(C);'))
        index = build(inputs)
        with patch('plc_workbench.workspace_connections.validate_references', side_effect=AssertionError), \
             patch('plc_workbench.workspace_connections._derive_access', side_effect=AssertionError), \
             patch('plc_workbench.workspace_connections._derive_calculations', side_effect=AssertionError):
            for rung in inputs[1].rungs:
                self.assertTrue(index.view(rung.id)['available'])

    def test_legacy_access_without_expression_leaves_is_explicit(self) -> None:
        inputs = capture(('MOV(A,B);', 'XIC(B)OTE(C);'))
        for version in (2, 3):
            with self.subTest(version=version):
                old_access = analyze_access(inputs[1], inputs[2], schema_version=version)
                index = ConnectionIndex(inputs[1], inputs[2], old_access, inputs[-1])
                view = index.view(inputs[1].rungs[0].id)
                self.assertFalse(view['coverage']['calculation_reads_available'])
                self.assertEqual(view['coverage']['access_schema_version'], version)
                self.assertEqual(signal(view, 'B')['counts']['readers'], 1)

    def test_absent_artifacts_and_v4_missing_calculations_are_unavailable(self) -> None:
        inputs = capture()
        wires = wire_inputs(inputs)
        for index in (1, 2, 3, 4):
            values = deepcopy(wires)
            values[index] = None
            with self.subTest(index=index), self.assertRaises(ConnectionError):
                ConnectionIndex(*values)

    def test_present_legacy_calculation_companion_is_validated_even_without_leaf_edges(self) -> None:
        inputs = capture(('MOV(A,B);',))
        old_access = analyze_access(inputs[1], inputs[2], schema_version=3)
        bad_calculations = asdict(inputs[4])
        bad_calculations['snapshot']['id'] = 'foreign'
        with self.assertRaises(ConnectionError):
            ConnectionIndex(inputs[1], inputs[2], old_access, inputs[-1], bad_calculations)

    def test_mismatched_snapshots_and_unsupported_schemas_fail_closed(self) -> None:
        wires = wire_inputs(capture())
        for position in range(1, 5):
            values = deepcopy(wires)
            values[position]['snapshot']['id'] = 'private-source'
            with self.subTest(position=position), self.assertRaises(ConnectionError) as raised:
                ConnectionIndex(*values)
            self.assertNotIn('private-source', str(raised.exception))
        for field, value in [('schema_version', 1), ('schema_version', True), ('analyzer_version', 'wrong')]:
            values = deepcopy(wires)
            values[2][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ConnectionError):
                ConnectionIndex(*values)

    def test_forged_roles_and_bindings_are_rejected_even_if_membership_agrees(self) -> None:
        wires = wire_inputs(capture(('MOV(A,B);', 'XIC(B)OTE(C);')))
        values = deepcopy(wires)
        values[2]['operands'][0]['role'] = 'write'
        address = values[3]['addresses'][0]
        address['write_operand_ids'] = address['read_operand_ids']
        address['read_operand_ids'] = []
        address['profile'] = 'write_only'
        with self.assertRaises(ConnectionError):
            ConnectionIndex(*values)
        values = deepcopy(wires)
        values[1]['operands'][0]['target_id'] = values[1]['operands'][1]['target_id']
        with self.assertRaises(ConnectionError):
            ConnectionIndex(*values)

    def test_forged_address_membership_foreign_ids_and_duplicate_ids_rejected(self) -> None:
        wires = wire_inputs(capture(('MOV(A,B);', 'XIC(B)OTE(C);')))
        for mutation in ('foreign', 'duplicate', 'suffix', 'target', 'missing', 'order'):
            values = deepcopy(wires)
            address = values[3]['addresses'][0]
            if mutation == 'foreign':
                address['read_operand_ids'][0] = 'operand_private-foreign'
            elif mutation == 'duplicate':
                values[3]['addresses'].append(deepcopy(address))
            elif mutation == 'suffix':
                address['suffix'] = '.invented'
            elif mutation == 'target':
                address['target_id'] = values[3]['addresses'][1]['target_id']
            elif mutation == 'missing':
                address['read_operand_ids'].clear()
            else:
                values[3]['addresses'].reverse()
            with self.subTest(mutation=mutation), self.assertRaises(ConnectionError):
                ConnectionIndex(*values)

    def test_forged_calculation_leaf_span_binding_and_tree_are_rejected(self) -> None:
        wires = wire_inputs(capture(('CPT(C,A+B);',)))
        for mutation in ('span', 'binding', 'operator', 'use'):
            values = deepcopy(wires)
            if mutation == 'span':
                values[4]['nodes'][0]['end'] += 1
            elif mutation == 'binding':
                values[4]['nodes'][0]['binding']['target_id'] = values[4]['nodes'][1]['binding']['target_id']
            elif mutation == 'operator':
                values[4]['nodes'][-1]['operator'] = '*'
            else:
                values[2]['expression_uses'][0]['start'] += 1
            with self.subTest(mutation=mutation), self.assertRaises(ConnectionError):
                ConnectionIndex(*values)

    def test_extended_counter_roles_are_authenticated_against_catalog(self) -> None:
        inputs = capture(('CTU(T,?,?);', 'RES(T);'))
        row = signal(build(inputs).view(inputs[1].rungs[0].id), 'T')
        self.assertEqual(row['focus_roles'], ['read', 'write'])
        self.assertEqual(len(row['writers']), 1)
        wires = wire_inputs(inputs)
        wires[2]['operands'][0]['role'] = 'read'
        with self.assertRaises(ConnectionError):
            ConnectionIndex(*wires)

    def test_invalid_selection_types_are_rejected_and_page_is_bounded(self) -> None:
        inputs = capture()
        index = build(inputs)
        focus = inputs[1].rungs[0].id
        for kwargs in ({'page': True}, {'page': 0}, {'endpoint_page': -1}, {'scope': 'plant'},
                       {'direction': 'execution'}, {'signal_id': 'foreign'}, {'page': 1_000_001},
                       {'scope': []}, {'direction': {}}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ConnectionError):
                index.view(focus, **kwargs)
        with self.assertRaises(ConnectionError):
            index.view('missing')
        self.assertEqual(index.view(focus, page=999)['pagination']['page'], 1)

    def test_cyclic_and_oversized_evidence_are_rejected_without_source_echo(self) -> None:
        wires = wire_inputs(capture())
        values = deepcopy(wires)
        values[3]['coverage']['cycle'] = values[3]
        with self.assertRaises(ConnectionError):
            ConnectionIndex(*values)
        values = deepcopy(wires)
        values[3]['addresses'] *= 2
        with patch('plc_workbench.workspace_connections.MAX_RECORDS', 1), self.assertRaises(ConnectionError):
            ConnectionIndex(*values)


if __name__ == '__main__':
    unittest.main()
