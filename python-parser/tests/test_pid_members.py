"""Invented PID member evidence; no source values acquire runtime meaning."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.pid import render_pid_json
from plc_workbench.pid_members import (
    FIELD_CATALOG, PidMemberError, analyze_pid_members, render_pid_members_json, validate_pid_members,
)
from plc_workbench.tag_data import render_tag_data_json
from plc_workbench.source import SourceError
from test_pid import call, capture, tag


def data(members: str) -> str:
    return f'<Data Format="Decorated"><Structure DataType="PID">{members}</Structure></Data>'


def scalar(name: str, datatype: str = 'REAL', value: str = '001.50', extra: str = '') -> str:
    return f'<DataValueMember Name="{name}" DataType="{datatype}" Value="{value}"{extra}/>'


def full_members() -> str:
    return ''.join(
        '<ArrayMember Name="DATA" DataType="REAL" Dimensions="17"/>' if name == 'DATA'
        else scalar(name, spec['datatype']) for name, spec in FIELD_CATALOG.items())


def captured(members: str, text: str | None = None, namespace: str = ''):
    inputs = capture(call() + ';' if text is None else text, tag(data(members)), namespace)
    return (*inputs, analyze_pid_members(*inputs))


class PidMemberTests(unittest.TestCase):
    def test_all_51_documented_headers_are_labeled_without_values_or_decoding(self) -> None:
        inputs = captured(full_members())
        result = inputs[-1]
        self.assertEqual(len(FIELD_CATALOG), 51)
        self.assertEqual(sum(row['datatype'] == 'BOOL' for row in FIELD_CATALOG.values()), 21)
        self.assertEqual(sum(row['datatype'] == 'DINT' for row in FIELD_CATALOG.values()), 1)
        self.assertEqual(sum(row['datatype'] == 'REAL' for row in FIELD_CATALOG.values()), 29)
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.coverage['members_by_status']['matched'], 50)
        self.assertEqual(result.coverage['members_by_status']['array_header_matched'], 1)
        self.assertEqual(result.coverage['missing_catalog_fields'], 0)
        self.assertEqual(result.structures[0]['missing_fields'], [])
        self.assertEqual({row['field'] for row in result.members}, set(FIELD_CATALOG))
        self.assertEqual(json.loads(render_pid_members_json(result)), result.to_dict())
        self.assertNotIn('001.50', render_pid_members_json(result))
        self.assertEqual(result.numeric_analysis, 'not_implemented')
        self.assertEqual(result.value_analysis, 'not_implemented')
        validate_pid_members(*inputs)

    def test_shared_owner_occurrences_deduplicate_structures_but_keep_separate_representations(self) -> None:
        document = data(scalar('SP')) + data(scalar('SP', value='999'))
        inputs = capture(call() * 4 + ';', tag(document))
        original_pid, original_tag = render_pid_json(inputs[-1]), render_tag_data_json(inputs[-2])
        result = analyze_pid_members(*inputs)
        self.assertEqual(inputs[-1].coverage['structure_occurrences'], 8)
        self.assertEqual(result.coverage['structures_total'], 2)
        self.assertEqual(result.coverage['members_total'], 2)
        self.assertEqual(result.coverage['distinct_backing_owners'], 1)
        self.assertEqual(result.coverage['duplicate_catalog_fields'], 0)
        self.assertNotEqual(result.members[0]['element_id'], result.members[1]['element_id'])
        self.assertEqual(original_pid, render_pid_json(inputs[-1]))
        self.assertEqual(original_tag, render_tag_data_json(inputs[-2]))
        self.assertEqual(result.to_dict(), analyze_pid_members(*inputs).to_dict())

    def test_duplicates_casefold_only_ascii_and_preserve_member_order_and_each_value_link(self) -> None:
        inputs = captured(scalar('SP') + scalar('sp', value='999') + scalar(' SP')
                          + scalar('S\u0420') + scalar('Unknown') + scalar('Unknown'))
        result = inputs[-1]
        self.assertEqual([row['field'] for row in result.members], ['SP', 'SP', None, None, None, None])
        self.assertEqual(result.structures[0]['duplicate_fields'], ['SP'])
        self.assertEqual(result.coverage['duplicate_member_records'], 2)
        self.assertEqual(result.coverage['duplicate_catalog_fields'], 1)
        self.assertEqual(result.coverage['missing_catalog_fields'], 50)
        self.assertEqual(result.structures[0]['member_ids'], [row['element_id'] for row in result.members])
        self.assertEqual(len(set(result.structures[0]['member_ids'])), 6)
        self.assertEqual(result.coverage['members_by_status']['unknown_name'], 4)
        self.assertEqual(result.status, 'partial')

    def test_known_name_presence_does_not_hide_type_shape_and_dimension_gaps(self) -> None:
        cases = [
            ('<DataValueMember Name="SP" Value="1"/>', 'type_missing'),
            (scalar('SP', datatype='DINT'), 'type_mismatch'),
            (scalar('SP', datatype=' REAL'), 'type_mismatch'),
            ('<StructureMember Name="SP" DataType="REAL"/>', 'shape_mismatch'),
            (scalar('SP', extra=' Dimensions="0"'), 'dimensions_unmodeled'),
            (scalar('SP', value=''), 'value_missing'),
            (scalar('SP', value='  '), 'value_missing'),
            (scalar('SP', datatype='real'), 'matched'),
        ]
        for member, status in cases:
            with self.subTest(member=member):
                result = captured(member)[-1]
                self.assertEqual(result.members[0]['field'], 'SP')
                self.assertEqual(result.members[0]['status'], status)
                self.assertNotIn('SP', result.structures[0]['missing_fields'])
                self.assertEqual(result.coverage['missing_catalog_fields'], 50)

    def test_qualified_semantic_attributes_withhold_header_claims(self) -> None:
        for attr in ('Name', 'DataType', 'Value'):
            with self.subTest(attr=attr):
                with self.assertRaises(SourceError):
                    captured(scalar('SP', extra=f' x:{attr}="conflict"'),
                             namespace=' xmlns:x="urn:invented"')
        for member in (scalar('SP').replace('DataType=', 'x:DataType='),
                       scalar('SP', extra=' x:Dimensions="0"')):
            with self.subTest(member=member):
                result = captured(member, namespace=' xmlns:x="urn:invented"')[-1]
                self.assertEqual(result.members[0]['status'], 'qualified_attribute')
                self.assertEqual(result.members[0]['field'], 'SP')
                self.assertEqual(result.members[0]['group'], 'setpoint')
        for attr in ('Name', 'Value'):
            with self.subTest(attr=attr):
                result = captured(scalar('SP').replace(f'{attr}=', f'x:{attr}='),
                                  namespace=' xmlns:x="urn:invented"')[-1]
                self.assertEqual(result.members, [])
                self.assertEqual(result.coverage['source_pid_partial'], 1)
        result = captured(scalar('SP', extra=' x:Unrelated="kept"'),
                          namespace=' xmlns:x="urn:invented"')[-1]
        self.assertEqual(result.members[0]['status'], 'matched')

    def test_array_header_never_claims_array_elements_or_numeric_values(self) -> None:
        malformed_indices = '<Element Index="[999]" Value="NaN"/><Element Index="[999]" Value="bad"/>'
        member = f'<ArrayMember Name="DATA" DataType="REAL" Dimensions="17">{malformed_indices}</ArrayMember>'
        result = captured(member)[-1]
        self.assertEqual(result.members[0]['status'], 'array_header_matched')
        self.assertEqual(result.coverage['members_total'], 1)
        for dimensions in ('', '017', '17 ', '1,17', '-17'):
            with self.subTest(dimensions=dimensions):
                result = captured(member.replace('Dimensions="17"', f'Dimensions="{dimensions}"'))[-1]
                self.assertEqual(result.members[0]['status'], 'dimensions_unmodeled')
        result = captured(scalar('SP', value='not-a-number') + scalar('CL', 'BOOL', '-123'))[-1]
        self.assertEqual([row['status'] for row in result.members], ['matched', 'matched'])

    def test_invalid_source_shapes_remain_upstream_gaps_and_do_not_become_member_claims(self) -> None:
        for member in ('<DataValueMember Name="SP" DataType="REAL"/>',
                       '<DataValueMember DataType="REAL" Value="1"/>',
                       '<x:DataValueMember Name="SP" DataType="REAL" Value="1"/>',
                       '<ArrayMember Name="DATA" DataType="REAL" Dimensions="17" Value="1"/>'):
            with self.subTest(member=member):
                inputs = captured(member, namespace=' xmlns:x="urn:invented"')
                self.assertEqual(inputs[-2].occurrences[0]['storage_status'], 'no_pid_structure')
                result = inputs[-1]
                self.assertEqual(result.coverage['source_pid_partial'], 1)
                self.assertEqual(result.members, [])
                self.assertEqual(result.structures, [])
                self.assertEqual(result.status, 'partial')

    def test_empty_structures_and_zero_pid_populations_have_distinct_coverage(self) -> None:
        result = captured('')[-1]
        self.assertEqual(result.coverage['structures_total'], 1)
        self.assertEqual(result.coverage['missing_catalog_fields'], 51)
        self.assertEqual(result.status, 'partial')
        result = captured(full_members(), text='XIC(PV);')[-1]
        self.assertEqual(result.coverage['structures_total'], 0)
        self.assertEqual(result.coverage['members_total'], 0)
        self.assertEqual(result.status, 'complete')

    def test_forged_or_cross_snapshot_evidence_is_rejected_source_free(self) -> None:
        inputs = captured(scalar('SP'))
        foreign = captured(scalar('SP', value='998877'))[-1]
        forged = deepcopy(inputs[-1])
        forged.members[0]['field'] = 'KP'
        forged_links = deepcopy(inputs[-1])
        forged_links.structures[0]['member_ids'] = []
        cycle = deepcopy(inputs[-1])
        cycle.coverage['extra'] = cycle.coverage
        for result in (foreign, forged, forged_links, cycle, replace(inputs[-1], schema_version=True)):
            with self.subTest(result_type=type(result)), self.assertRaises(PidMemberError) as caught:
                validate_pid_members(*inputs[:-1], result)
            self.assertEqual(str(caught.exception), 'PID member evidence is inconsistent or exceeds its limits.')
        forged_pid = deepcopy(inputs[-2])
        forged_pid.occurrences[0]['structure_candidates'][0]['member_ids'] = []
        with self.assertRaises(PidMemberError):
            analyze_pid_members(*inputs[:4], forged_pid)

    def test_limits_reject_before_excessive_private_payload_is_retained(self) -> None:
        inputs = captured(scalar('SP') + scalar('KP'))
        for constant, limit in (('MAX_PID_MEMBERS', 1), ('MAX_PID_MEMBER_STRUCTURES', 0),
                                ('MAX_PID_MEMBER_EVIDENCE_BYTES', 100), ('MAX_PID_MEMBER_JSON_BYTES', 100)):
            with self.subTest(constant=constant), patch('plc_workbench.pid_members.' + constant, limit):
                with self.assertRaises(PidMemberError):
                    analyze_pid_members(*inputs[:-1])
        cycle = deepcopy(inputs[-1])
        cycle.members.append(cycle.members)
        with patch('plc_workbench.pid_members.MAX_PID_MEMBER_EVIDENCE_BYTES', 1000):
            with self.assertRaises(PidMemberError):
                render_pid_members_json(cycle)


if __name__ == '__main__':
    unittest.main()
