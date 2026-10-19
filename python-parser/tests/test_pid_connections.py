"""Invented PID connections challenge exact identity and semantic boundaries."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access, render_access_json
from plc_workbench.calculations import analyze_calculations
from plc_workbench.conditions import analyze_conditions
from plc_workbench.pid_connections import (PidConnectionError, analyze_pid_connections,
    render_pid_connections_json, validate_pid_connections)
from plc_workbench.pid_members import analyze_pid_members
from plc_workbench.relationships import analyze_relationships, render_relationships_json
from plc_workbench.rung_analysis import analyze_rungs
from test_pid import capture as capture_pid, capture_xml, tag
from test_pid_members import data, full_members, scalar


def connections(inputs):
    snapshot, inventory, references, tag_data, pid = inputs
    calculations = analyze_calculations(snapshot, inventory, references)
    access = analyze_access(inventory, references, schema_version=4,
                           snapshot=snapshot, calculations=calculations)
    rung_analysis = analyze_rungs(snapshot, inventory, references, access, calculations)
    relationships = analyze_relationships(snapshot, inventory, references, access, calculations, rung_analysis)
    conditions = analyze_conditions(snapshot, inventory, references, access, calculations,
                                    rung_analysis, relationships, schema_version=3)
    members = analyze_pid_members(snapshot, inventory, references, tag_data, pid)
    args = (snapshot, inventory, references, access, calculations, rung_analysis,
            relationships, conditions, tag_data, pid, members)
    return (*args, analyze_pid_connections(*args))


def capture(text: str = 'PID(Loop,PV,0,CV,0,0,0);', tags: str | None = None, namespace: str = ''):
    if tags is None:
        tags = tag(data(full_members()))
    tags += ''.join(tag('', name, 'REAL') for name in ('PV', 'CV', 'Tie', 'Hold', 'HoldValue'))
    return connections(capture_pid(text, tags, namespace))


def by_suffix(inputs):
    suffixes = {row['id']: row['suffix'] for row in inputs[6].addresses}
    return {suffixes[row['id']]: row for row in inputs[-1].addresses}


class PidConnectionTests(unittest.TestCase):
    def test_seven_slots_link_existing_addresses_and_keep_unknown_roles(self) -> None:
        inputs = capture('MOV(PV,CV)CPT(CV,PV+PV)ONS(Hold)PID(Loop,PV,Tie,CV,0,Hold,HoldValue);')
        result = inputs[-1]
        self.assertEqual(len(result.slots), 7)
        self.assertEqual([row['id'] for row in result.slots], inputs[9].occurrences[0]['operand_ids'])
        self.assertEqual(result.coverage['slots_by_status']['exact_address'], 6)
        self.assertEqual(result.coverage['slots_by_status']['literal'], 1)
        roles = result.coverage['address_links_by_role']
        self.assertEqual(roles['unknown'], 6)
        self.assertEqual(roles['read'], 1)
        self.assertEqual(roles['write'], 2)
        self.assertEqual(roles['read_write'], 1)
        self.assertEqual(roles['expression_read'], 2)
        self.assertEqual(result.status, 'complete')
        self.assertTrue(all(row['role'] == 'unknown' for row in inputs[3].operands[-7:]))
        validate_pid_connections(*inputs)
        self.assertEqual(json.loads(render_pid_connections_json(result)), result.to_dict())

    def test_member_groups_whole_owner_and_indexed_suffixes_stay_separate(self) -> None:
        inputs = capture('MOV(PV,Loop.SP)OTE(Loop.SWM)MOV(PV,Loop.PVH)MOV(PV,Loop)'
                         'MOV(PV,Loop.DATA[0])MOV(PV,Loop.SP.Nested)MOV(PV,Loop.Unknown)'
                         'CPT(CV,Loop.SP+Loop.SP)PID(Loop,PV,0,CV,0,0,0);')
        result = inputs[-1]
        addresses = by_suffix(inputs)
        self.assertEqual(addresses['.SP']['kind'], 'direct_member')
        self.assertEqual(addresses['.SP']['group'], 'setpoint')
        self.assertEqual(addresses['.SWM']['group'], 'mode')
        self.assertEqual(addresses['.PVH']['group'], 'alarms')
        self.assertEqual(addresses['.Unknown']['kind'], 'unknown_member')
        self.assertEqual(addresses['.DATA[0]']['kind'], 'deferred_suffix')
        self.assertEqual(addresses['.SP.Nested']['kind'], 'deferred_suffix')
        self.assertEqual(len(addresses['.SP']['write_operand_ids']), 1)
        self.assertEqual(len(addresses['.SP']['expression_use_ids']), 2)
        occurrence = result.occurrences[0]
        self.assertEqual(len(occurrence['whole_owner_address_ids']), 1)
        self.assertEqual(len(occurrence['deferred_address_ids']), 2)
        self.assertEqual(occurrence['member_address_ids_by_group']['setpoint'], [addresses['.SP']['id']])
        self.assertNotIn(occurrence['whole_owner_address_ids'][0], occurrence['member_address_ids_by_group']['setpoint'])

    def test_aliases_reuse_exact_identity_without_case_or_index_normalization(self) -> None:
        tags = tag(data(full_members())) + '<Tag Name="Setpoint" TagType="Alias" AliasFor="Loop.SP"/>'
        inputs = capture('MOV(PV,Setpoint)MOV(PV,Loop.SP)MOV(PV,Loop.sp)MOV(PV,Loop.DATA[01])'
                         'MOV(PV,Loop.DATA[ 1 ])PID(Loop,PV,0,CV,0,0,0);', tags)
        addresses = by_suffix(inputs)
        self.assertEqual(len(addresses['.SP']['write_operand_ids']), 2)
        self.assertNotEqual(addresses['.SP']['id'], addresses['.sp']['id'])
        self.assertEqual(addresses['.SP']['member_ids'], addresses['.sp']['member_ids'])
        self.assertIn('.DATA[01]', addresses)
        self.assertIn('.DATA[ 1 ]', addresses)

    def test_repeated_pid_and_duplicate_representations_keep_ambiguity(self) -> None:
        tags = tag(data(scalar('SP')) + data(scalar('SP', value='777888')))
        inputs = capture('MOV(PV,Loop.SP)' + 'PID(Loop,PV,0,CV,Loop,0,0)' * 3 + ';', tags)
        result = inputs[-1]
        self.assertEqual(len(by_suffix(inputs)['.SP']['member_ids']), 2)
        self.assertEqual(result.coverage['masters_by_status']['multiple_occurrences'], 3)
        self.assertEqual(result.coverage['master_candidate_links'], 9)
        self.assertEqual(result.coverage['master_self_references'], 3)
        self.assertEqual(len({row['id'] for row in result.addresses}), len(result.addresses))
        self.assertNotIn('777888', render_pid_connections_json(result))
        self.assertEqual(result.to_dict(), analyze_pid_connections(*inputs[:-1]).to_dict())

    def test_master_owner_candidates_include_uncalled_owner_and_do_not_claim_cascade(self) -> None:
        tags = tag(data(full_members())) + tag(data(full_members()), 'Master')
        inputs = capture('PID(Loop,PV,0,CV,Master,0,0);', tags)
        master = inputs[-1].occurrences[0]['master']
        self.assertEqual(master['status'], 'missing_occurrence')
        self.assertIsNotNone(master['owner_id'])
        self.assertEqual(master['occurrence_ids'], [])
        inputs = capture('PID(Master,PV,0,CV,0,0,0)PID(Loop,PV,0,CV,Master,0,0);', tags)
        first, second = inputs[-1].occurrences
        self.assertEqual(second['master']['status'], 'single_occurrence')
        self.assertEqual(second['master']['occurrence_ids'], [first['id']])
        self.assertEqual(second['master']['self_reference'], 0)
        self.assertEqual(inputs[-1].cascade_analysis, 'not_implemented')

    def test_master_literal_missing_static_suffix_and_non_pid_are_explicit(self) -> None:
        tags = tag(data(full_members())) + tag('', 'Array', attrs=' Dimensions="2"')
        cases = {'0': 'literal', 'Missing': 'binding_gap', 'Loop.SP': 'static_suffix',
                 'Loop[0]': 'static_suffix', 'PV': 'owner_not_pid', 'Array': 'owner_dimensions_unmodeled'}
        for operand, status in cases.items():
            with self.subTest(operand=operand):
                result = capture(f'PID(Loop,PV,0,CV,{operand},0,0);', tags)[-1]
                self.assertEqual(result.occurrences[0]['master']['status'], status)

    def test_condition_ids_link_only_incoming_source_context(self) -> None:
        inputs = capture('[XIC(Hold),XIO(Tie)]PID(Loop,PV,0,CV,0,0,0);')
        result = inputs[-1]
        occurrence = result.occurrences[0]
        transfer = next(row for row in inputs[7].nodes if row['instruction_id'] == occurrence['id'])
        self.assertEqual(transfer['kind'], 'opaque_transfer')
        self.assertEqual(occurrence['incoming_condition_ids'], transfer['child_ids'][:1])
        self.assertNotIn(transfer['id'], occurrence['incoming_condition_ids'])
        self.assertEqual(result.execution_analysis, 'not_implemented')

    def test_namespace_alias_gaps_do_not_become_supported_member_accesses(self) -> None:
        tags = tag(data(full_members())) + '<Tag Name="Alias" TagType="Alias" x:AliasFor="Loop.SP"/>'
        inputs = capture('MOV(PV,Alias)CPT(CV,Alias+1)PID(Loop,PV,0,CV,0,0,0);',
                         tags, ' xmlns:x="urn:foreign"')
        address = by_suffix(inputs)['.SP']
        self.assertEqual(address['write_operand_ids'], [])
        self.assertEqual(address['expression_use_ids'], [])
        self.assertEqual(len(address['namespace_gap_operand_ids']), 1)
        self.assertEqual(len(address['namespace_gap_expression_use_ids']), 1)
        self.assertEqual(inputs[-1].status, 'partial')

    def test_qualified_scopes_and_rungs_withhold_control_and_condition_links(self) -> None:
        base = capture_pid('PID(Loop,PV,0,CV,0,0,0);', tag(data(full_members())),
                           ' xmlns:x="urn:foreign"')[0].data.decode()
        for xml in (base.replace('Name="P"', 'x:Name="P"'),
                    base.replace('<Rung ', '<x:Rung ').replace('</Rung>', '</x:Rung>'),
                    base.replace('<Text>', '<x:Text>').replace('</Text>', '</x:Text>')):
            with self.subTest(xml=xml):
                result = connections(capture_xml(xml))[-1]
                self.assertEqual(result.occurrences[0]['control_status'], 'namespace_gap')
                self.assertEqual(result.occurrences[0]['incoming_condition_ids'], [])
                self.assertEqual(result.coverage['slots_by_status']['namespace_gap'], 1)

    def test_program_scope_shadowing_does_not_join_same_named_owners(self) -> None:
        controller = tag(data(full_members()))
        base = capture_pid('MOV(PV,Loop.SP)PID(Loop,PV,0,CV,0,0,0);', controller)[0].data.decode()
        base = base.replace('<Program Name="P">', '<Program Name="P"><Tags>' + controller + '</Tags>')
        other = ('<Program Name="Q"><Routines><Routine Name="R" Type="RLL"><RLLContent>'
                 '<Rung Number="0" Type="N"><Text>MOV(0,Loop.SP);</Text></Rung>'
                 '</RLLContent></Routine></Routines></Program>')
        inputs = connections(capture_xml(base.replace('</Programs>', other + '</Programs>')))
        member = by_suffix(inputs)['.SP']
        self.assertEqual(len(member['write_operand_ids']), 1)
        self.assertEqual(member['owner_id'], inputs[-1].occurrences[0]['control_owner_id'])

    def test_malformed_signatures_and_invalid_alias_composition_preserve_gaps(self) -> None:
        result = capture('PID(Loop,PV);')[-1]
        self.assertEqual(len(result.slots), 2)
        self.assertTrue(all(row['status'] == 'signature_unresolved' for row in result.slots))
        self.assertEqual(result.occurrences[0]['master']['status'], 'signature_unresolved')
        tags = tag(data(full_members())) + '<Tag Name="Bit" TagType="Alias" AliasFor="PV.1"/>'
        result = capture('PID(Loop,Bit.Member,0,CV,0,0,0);', tags)[-1]
        self.assertEqual(result.slots[1]['status'], 'identity_gap')
        self.assertIsNone(result.slots[1]['address_id'])

    def test_no_pid_has_zero_records_and_existing_companions_are_unchanged(self) -> None:
        inputs = capture('MOV(PV,CV);')
        result = inputs[-1]
        self.assertEqual((result.occurrences, result.slots, result.addresses), ([], [], []))
        self.assertEqual(result.status, 'complete')
        inputs = capture('MOV(PV,Loop.SP)PID(Loop,PV,0,CV,0,0,0);')
        before = render_access_json(inputs[3]), render_relationships_json(inputs[6])
        analyze_pid_connections(*inputs[:-1])
        self.assertEqual(before, (render_access_json(inputs[3]), render_relationships_json(inputs[6])))

    def test_forged_links_order_bool_counts_and_companions_are_rejected(self) -> None:
        inputs = capture('MOV(PV,Loop.SP)PID(Loop,PV,0,CV,0,0,0);')
        for change in ('slot', 'member', 'condition', 'order', 'bool', 'version'):
            forged = deepcopy(inputs[-1])
            if change == 'slot':
                forged.slots[0]['address_id'] = 'PrivateSentinel'
            elif change == 'member':
                by_id = next(row for row in forged.addresses if row['field'] == 'SP')
                by_id['member_ids'] = ['PrivateSentinel']
            elif change == 'condition':
                forged.occurrences[0]['incoming_condition_ids'] = ['PrivateSentinel']
            elif change == 'order':
                forged.slots.reverse()
            elif change == 'bool':
                forged.coverage['occurrences_total'] = True
            else:
                forged = replace(forged, schema_version=True)
            with self.subTest(change=change), self.assertRaises(PidConnectionError) as caught:
                validate_pid_connections(*inputs[:-1], forged)
            self.assertNotIn('PrivateSentinel', str(caught.exception))
        for index in (2, 3, 4, 5, 6, 7, 8, 9, 10):
            forged = list(deepcopy(inputs[:-1]))
            forged[index].coverage['forged'] = 1
            with self.subTest(index=index), self.assertRaises(PidConnectionError):
                analyze_pid_connections(*forged)

    def test_limits_cycles_and_non_native_values_are_rejected(self) -> None:
        inputs = capture()
        for key in ('MAX_PID_CONNECTION_RECORDS', 'MAX_PID_CONNECTION_BYTES', 'MAX_PID_CONNECTION_JSON_BYTES'):
            with self.subTest(key=key), patch('plc_workbench.pid_connections.' + key, 1):
                with self.assertRaises(PidConnectionError):
                    analyze_pid_connections(*inputs[:-1])
        cyclic = deepcopy(inputs[-1])
        cyclic.occurrences.append(cyclic.occurrences)
        with self.assertRaises(PidConnectionError):
            render_pid_connections_json(cyclic)
        with self.assertRaises(PidConnectionError):
            render_pid_connections_json(replace(inputs[-1], coverage={'x': object()}))


if __name__ == '__main__':
    unittest.main()
