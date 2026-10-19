"""Invented source assemblies preserve exact occurrence evidence and boundaries."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from plc_workbench.engineering_assemblies import (EngineeringAssembliesError,
    FLAGS, GROUP_BYTES, MAX_ENGINEERING_ASSEMBLIES_BYTES, PROVIDERS, build_engineering_assemblies)
from plc_workbench.relationships import _identifier
from plc_workbench.references import MAX_ADDRESS_LENGTH
from test_signal_candidates_workflow import captured, options

SOURCE = Path(__file__).resolve().parents[2] / 'public/fixtures/synthetic/engineering_assemblies_demo.L5X'


@lru_cache(maxsize=8)
def provider_data(source: bytes | None = None) -> dict:
    parts = captured(SOURCE.read_bytes() if source is None else source)
    return {key: value.to_dict() for key, value in options(parts).items()
        if key in PROVIDERS | {'access', 'relationships'}}


def empty() -> dict:
    return {key: {'status': 'complete'} for key in PROVIDERS | {'access', 'relationships'}}


def rows(result: dict, relation: str) -> list[dict]:
    return [row for row in result['memberships'] if row['relation'] == relation]


def supplemental_data() -> dict:
    """Invented static provider rows with no legacy relationship address."""
    data = empty()
    for provider in ('relationships', 'sfc_context', 'file_operations'):
        data[provider]['snapshot'] = {'id': 'synthetic-snapshot'}
    addresses, references = [], []
    for index, suffix in enumerate(('', '.Flag', '[01].Flag', '[1].Flag', '.Flag')):
        address = _identifier('sfc_context_address_', 'synthetic-snapshot', 'PRIVATE_TARGET', suffix)
        if all(row['id'] != address for row in addresses):
            addresses.append({'id': address, 'target_id': 'PRIVATE_TARGET', 'suffix': suffix,
                'relationship_address_id': None})
        references.append({'id': f'sfc_reference_{index}', 'address_id': address,
            'status': 'exact_address', 'binding_status': 'root_bound'})
    references.append({'id': 'sfc_gap', 'status': 'binding_gap'})
    data['sfc_context'].update(addresses=addresses, references=references)
    data['file_operations']['occurrences'] = [{'id': 'file_instruction', 'rung_id': 'file_rung',
        'qualification': 'qualified', 'context_status': 'modeled'}]
    slots = []
    for index, suffix in enumerate(('.Flag', '.FileOnly')):
        slots.append({'id': f'file_slot_{index}', 'instruction_id': 'file_instruction', 'rung_id': 'file_rung',
            'status': 'exact_address', 'role': 'read',
            'address_id': _identifier('relationship_address_', 'synthetic-snapshot', 'PRIVATE_TARGET', suffix),
            'binding': {'status': 'root_bound', 'target_id': 'PRIVATE_TARGET', 'suffix': suffix}})
    slots.append({'id': 'file_dynamic', 'instruction_id': 'file_instruction', 'status': 'symbolic_address'})
    data['file_operations']['slots'] = slots
    return data


class EngineeringAssembliesTests(unittest.TestCase):
    def test_schema2_accepts_canonical_alias_suffix_at_inclusive_length_limit(self) -> None:
        half = MAX_ADDRESS_LENGTH // 2 - 1
        aliases = (b'<Tag Name="AliasA" TagType="Alias" AliasFor="Pump.' + b'A' * half
            + b'"/><Tag Name="AliasB" TagType="Alias" AliasFor="AliasA.' + b'B' * half + b'"/>')
        source = SOURCE.read_bytes().replace(b'<Tag Name="Permit"', aliases + b'<Tag Name="Permit"', 1)
        source = source.replace(b'Pump AND State.X', b'AliasB AND State.X')
        data = provider_data(source)
        exact = next(row for row in data['sfc_context']['addresses'] if len(row['suffix']) == MAX_ADDRESS_LENGTH)
        self.assertIsNone(exact['relationship_address_id'])
        result = build_engineering_assemblies(data, schema_version=2)
        supplemental = next(row for row in result['supplemental_addresses'] if row['suffix'] == exact['suffix'])
        self.assertEqual(supplemental['target_id'], exact['target_id'])
        self.assertTrue(any(row['group_id'] == supplemental['id'] for row in rows(result, 'sfc_reference')))
        self.assertEqual(result['scan_status'], 'complete')

    def test_schema2_canonical_sfc_and_fal_only_addresses_join_without_changing_providers(self) -> None:
        source = SOURCE.read_bytes().replace(b'Pump AND State.X',
            b'Control.DN AND Counter.DN AND MissingName').replace(
                b'AVE(Samples[0],0,Scaled,Control,?,?);',
                b'FAL(Control,?,?,ALL,Scaled,Counter.ACC+Samples[Index]);')
        data = provider_data(source)
        before = deepcopy(data)
        legacy = build_engineering_assemblies(data)
        current = build_engineering_assemblies(data, schema_version=2)
        self.assertEqual(data, before)
        self.assertEqual(legacy['coverage']['excluded_by_reason']['missing_address'], 4)
        self.assertEqual(current['coverage']['excluded_by_reason']['missing_address'], 0)
        self.assertEqual(current['coverage']['supplemental_addresses_total'], 4)
        self.assertEqual(current['coverage']['memberships_by_provider']['sfc_context'], 2)
        self.assertEqual(current['coverage']['memberships_by_provider']['file_operations'], 3)
        self.assertEqual(current['coverage']['excluded_by_provider_reason']['sfc_context']['binding_or_namespace'], 1)
        self.assertEqual(current['coverage']['excluded_by_provider_reason']['file_operations']['dynamic_address'], 1)
        self.assertFalse({row['id'] for row in current['supplemental_addresses']}
            & {row['id'] for row in data['relationships']['addresses']})
        for provider in PROVIDERS - {'sfc_context', 'file_operations'}:
            old_rows = [{key: value for key, value in row.items() if key != 'id'}
                for row in legacy['memberships'] if row['provider'] == provider]
            new_rows = [{key: value for key, value in row.items() if key != 'id'}
                for row in current['memberships'] if row['provider'] == provider]
            self.assertEqual(old_rows, new_rows)

    def test_schema2_supplements_only_qualified_static_provider_identities(self) -> None:
        data = supplemental_data()
        before = deepcopy(data)
        legacy = build_engineering_assemblies(data)
        result = build_engineering_assemblies(data, schema_version=2)
        self.assertEqual(data, before)
        self.assertEqual(legacy, build_engineering_assemblies(data, schema_version=1))
        self.assertNotIn('supplemental_addresses', legacy)
        self.assertEqual(legacy['coverage']['excluded_by_reason']['missing_address'], 7)
        self.assertEqual(result['analyzer_version'], 'engineering-assemblies-2')
        self.assertEqual(result['coverage']['supplemental_addresses_total'], 5)
        self.assertEqual(result['coverage']['memberships_by_provider']['sfc_context'], 5)
        self.assertEqual(result['coverage']['memberships_by_provider']['file_operations'], 2)
        self.assertEqual(result['coverage']['excluded_by_reason']['missing_address'], 0)
        self.assertEqual(result['coverage']['excluded_total'], 2)
        self.assertEqual(result['coverage']['excluded_by_provider_reason']['sfc_context']['binding_or_namespace'], 1)
        self.assertEqual(result['coverage']['excluded_by_provider_reason']['file_operations']['dynamic_address'], 1)
        self.assertEqual(result['coverage']['multiprovider_groups'], 1)
        self.assertEqual({row['suffix'] for row in result['supplemental_addresses']},
            {'', '.Flag', '[01].Flag', '[1].Flag', '.FileOnly'})
        for row in result['supplemental_addresses']:
            self.assertEqual(set(row), {'id', 'target_id', 'suffix'})
            self.assertEqual(row['id'], _identifier('relationship_address_', 'synthetic-snapshot', row['target_id'], row['suffix']))
        self.assertEqual(result, build_engineering_assemblies(data, schema_version=2))

    def test_schema2_rejects_tampered_identity_snapshot_and_binding_without_disclosure(self) -> None:
        mutations = (
            lambda data: data['file_operations']['snapshot'].update(id='PRIVATE_OTHER_SNAPSHOT'),
            lambda data: data['sfc_context']['snapshot'].update(id='PRIVATE_OTHER_SNAPSHOT'),
            lambda data: data['sfc_context']['addresses'][0].update(relationship_address_id='PRIVATE_FORGED'),
            lambda data: data['sfc_context']['addresses'][0].update(id='PRIVATE_FORGED'),
            lambda data: data['sfc_context']['addresses'][0].update(suffix='PRIVATE_ROOT'),
            lambda data: data['sfc_context']['references'][0].update(binding_status='namespace_gap'),
            lambda data: data['file_operations']['slots'][0].update(address_id='PRIVATE_FORGED'),
            lambda data: data['file_operations']['slots'][0]['binding'].update(status='unresolved'),
            lambda data: data['file_operations']['slots'][0]['binding'].update(suffix='[PRIVATE_DYNAMIC]'),
            lambda data: data['file_operations']['slots'][0]['binding'].update(suffix=True),
        )
        for index, mutate in enumerate(mutations):
            data = supplemental_data()
            mutate(data)
            with self.subTest(index=index), self.assertRaises(EngineeringAssembliesError) as error:
                build_engineering_assemblies(data, schema_version=2)
            self.assertNotIn('PRIVATE', str(error.exception))
        for version in (True, '2', 0, 3, None):
            with self.subTest(version=version), self.assertRaises(EngineeringAssembliesError):
                build_engineering_assemblies(empty(), schema_version=version)

    def test_schema2_reserves_supplemental_rows_atomically_with_membership(self) -> None:
        data = supplemental_data()
        result = build_engineering_assemblies(data, schema_version=2)
        for limit, value in (('MAX_ASSEMBLY_MEMBERSHIPS', 1), ('MAX_ASSEMBLY_GROUPS', 1),
                ('MAX_ASSEMBLY_VISITS', 6), ('MAX_ENGINEERING_ASSEMBLIES_BYTES', result['budget']['retained_bytes'] - 1)):
            with self.subTest(limit=limit), patch('plc_workbench.engineering_assemblies.' + limit, value):
                bounded = build_engineering_assemblies(data, schema_version=2)
                self.assertEqual(bounded['scan_status'], 'truncated')
                self.assertEqual({row['id'] for row in bounded['supplemental_addresses']},
                    {row['id'] for row in bounded['groups']})
                self.assertLessEqual(bounded['coverage']['visited_rows'] + bounded['coverage']['visited_links'],
                    bounded['budget']['max_visits'])
                self.assertLessEqual(bounded['budget']['retained_bytes'], bounded['budget']['max_bytes'])
                self.assertLess(len(json.dumps(bounded).encode()), bounded['budget']['retained_bytes'])

    def test_schema2_supplemental_record_bytes_are_charged_before_admission(self) -> None:
        data = supplemental_data()
        data['sfc_context'].update(addresses=[], references=[])
        data['file_operations']['slots'] = [data['file_operations']['slots'][0]]
        slot = data['file_operations']['slots'][0]
        suffix = '.' + 'A' * 60_000
        slot['binding']['suffix'] = suffix
        slot['address_id'] = _identifier('relationship_address_', 'synthetic-snapshot', 'PRIVATE_TARGET', suffix)
        with patch('plc_workbench.engineering_assemblies.MAX_ENGINEERING_ASSEMBLIES_BYTES', 40_000):
            result = build_engineering_assemblies(data, schema_version=2)
        self.assertEqual(result['scan_status'], 'truncated')
        self.assertEqual(result['groups'], [])
        self.assertEqual(result['memberships'], [])
        self.assertEqual(result['supplemental_addresses'], [])
        self.assertLessEqual(result['budget']['retained_bytes'], 40_000)

    def test_schema2_projection_needs_no_process_filesystem_or_network(self) -> None:
        data = supplemental_data()
        with patch('builtins.open', side_effect=AssertionError('file access')), \
                patch('subprocess.Popen', side_effect=AssertionError('process')), \
                patch('socket.socket', side_effect=AssertionError('network')):
            self.assertEqual(len(build_engineering_assemblies(data, schema_version=2)['supplemental_addresses']), 5)

    def test_schema2_file_expressions_require_qualified_occurrence_and_static_binding(self) -> None:
        data = supplemental_data()
        node = deepcopy(data['file_operations']['slots'][1])
        node.update(id='file_expression', kind='reference')
        data['file_operations'].update(slots=[], expression_nodes=[node])
        result = build_engineering_assemblies(data, schema_version=2)
        self.assertEqual([row['source_id'] for row in rows(result, 'file_read')], ['file_expression'])
        data['file_operations']['occurrences'][0]['qualification'] = 'namespace_gap'
        result = build_engineering_assemblies(data, schema_version=2)
        self.assertFalse(rows(result, 'file_read'))
        self.assertEqual(result['coverage']['excluded_by_provider_reason']['file_operations']['binding_or_namespace'], 1)

    def test_real_provider_projection_is_pure_deterministic_and_closed(self) -> None:
        data = provider_data()
        before = deepcopy(data)
        result = build_engineering_assemblies(data)
        self.assertEqual(data, before)
        self.assertEqual(result, build_engineering_assemblies(data))
        self.assertEqual(set(result['coverage']['memberships_by_provider']), PROVIDERS)
        self.assertTrue(all(result['coverage']['memberships_by_provider'].values()))
        self.assertEqual(result['scan_status'], 'complete')
        self.assertLess(len(json.dumps(result).encode()), result['budget']['retained_bytes'])
        self.assertLess(result['budget']['retained_bytes'], MAX_ENGINEERING_ASSEMBLIES_BYTES)
        self.assertEqual(result['execution_analysis'], 'not_implemented')
        self.assertEqual(result['equipment_identity'], 'not_inferred')

    def test_shared_addresses_have_multirung_and_multiple_provider_context(self) -> None:
        result = build_engineering_assemblies(provider_data())
        self.assertGreaterEqual(result['coverage']['multirung_groups'], 6)
        self.assertGreaterEqual(result['coverage']['multiprovider_groups'], 6)
        self.assertTrue(any({'pid_connections', 'calculation_paths', 'file_operations'} <= set(row['providers'])
            for row in result['groups']))
        self.assertTrue(any('competing_writers' in row['boundary_flags'] for row in result['groups']))
        identifiers = {row['id'] for row in result['memberships']}
        self.assertEqual(sum(len(row['membership_ids']) for row in result['groups']), len(identifiers))

    def test_repeated_contacts_keep_occurrences_and_original_output_instruction(self) -> None:
        data = provider_data()
        result = build_engineering_assemblies(data)
        pairs = rows(result, 'guard_condition')
        outputs = {row['instruction_id']: row for row in data['signal_context']['outputs']}
        reads = {row['id']: row for row in data['signal_context']['condition_reads']}
        for pair in pairs:
            output, read = outputs[pair['instruction_id']], reads[pair['source_id']]
            self.assertEqual(pair['group_id'], output['target_address_id'])
            self.assertEqual(pair['related_address_id'], read['source_address_id'])
            self.assertIn(pair['source_id'], output['guard_dependencies']['condition_read_ids'])
        first = data['signal_context']['outputs'][0]
        first_pairs = [row for row in pairs if row['instruction_id'] == first['instruction_id']]
        self.assertEqual(len(first_pairs), 3)
        self.assertEqual(len({row['source_id'] for row in first_pairs}), 3)
        self.assertEqual(len({row['related_address_id'] for row in first_pairs}), 2)

    def test_reader_alias_wording_does_not_label_output_as_alarm(self) -> None:
        result = build_engineering_assemblies(provider_data())
        self.assertEqual(sum('alarm_wording' in row['context_flags'] for row in rows(result, 'guard_condition')), 2)
        self.assertFalse(any('alarm_wording' in row['context_flags'] for row in rows(result, 'boolean_output')))

    def test_root_member_and_module_bit_identities_stay_separate(self) -> None:
        data = provider_data()
        result = build_engineering_assemblies(data)
        addresses = {row['id']: row for row in data['relationships']['addresses']}
        by_target: dict[str, set[str]] = {}
        for group in result['groups']:
            address = addresses[group['id']]
            by_target.setdefault(address['target_id'], set()).add(address['suffix'])
        self.assertTrue(any({'', '.DN'} <= value for value in by_target.values()))
        self.assertTrue(any({'.Data', '.Data.1'} <= value for value in by_target.values()))

    def test_namespace_gap_guard_never_produces_direct_pairs(self) -> None:
        data = provider_data()
        result = build_engineering_assemblies(data)
        gaps = {row['instruction_id'] for row in data['signal_context']['outputs']
            if row['has_namespace_gap']}
        self.assertTrue(gaps)
        self.assertFalse(any(row['instruction_id'] in gaps for row in result['memberships']
            if row['relation'] in {'boolean_output', 'guard_condition'}))
        self.assertGreater(result['coverage']['excluded_by_reason']['binding_or_namespace'], 0)

    def test_qualified_use_lists_not_relationship_identity_authorize_membership(self) -> None:
        data = empty()
        data['relationships']['addresses'] = [{'id': 'A', 'target_id': 'decl', 'suffix': '',
            'read_operand_ids': ['rejected']}]
        data['access']['operands'] = [{'id': 'rejected', 'instruction_id': 'I', 'rung_id': 'R'}]
        data['signal_context']['addresses'] = [{'id': 'A', 'read_operand_ids': [],
            'rejected_operand_ids': ['rejected']}]
        result = build_engineering_assemblies(data)
        self.assertEqual(result['groups'], [])
        self.assertEqual(result['coverage']['excluded_by_reason']['unqualified_membership'], 1)

    def test_pid_slots_and_members_retain_base_unknown_roles_and_master_gap(self) -> None:
        result = build_engineering_assemblies(provider_data())
        self.assertEqual(len(rows(result, 'pid_slot')), 4)
        self.assertTrue(any('unknown_role' in row['context_flags'] for row in rows(result, 'pid_slot')))
        self.assertTrue(all('pid_master_gap' in row['context_flags'] for row in rows(result, 'pid_slot')))
        self.assertTrue(rows(result, 'pid_address_use'))

    def test_only_eligible_calculations_join_and_branches_remain_flagged(self) -> None:
        data = provider_data()
        result = build_engineering_assemblies(data)
        eligible = {row['id'] for row in data['calculation_paths']['occurrences'] if row['status'] == 'eligible'}
        linked = {row['instruction_id'] for row in result['memberships'] if row['provider'] == 'calculation_paths'}
        self.assertEqual(linked, eligible)
        self.assertTrue(any('branched' in row['context_flags'] for row in rows(result, 'calculation_output')))
        self.assertEqual(result['coverage']['excluded_by_reason']['ineligible_occurrence'], 1)

    def test_sfc_provider_ids_map_to_relationship_address_not_themselves(self) -> None:
        data = provider_data()
        result = build_engineering_assemblies(data)
        addresses = {row['id']: row for row in data['sfc_context']['addresses']}
        references = {row['id']: row for row in data['sfc_context']['references']}
        self.assertEqual(len(rows(result, 'sfc_reference')), 2)
        for row in rows(result, 'sfc_reference'):
            address = addresses[references[row['source_id']]['address_id']]
            self.assertEqual(row['group_id'], address['relationship_address_id'])
            self.assertNotEqual(row['group_id'], address['id'])
            self.assertIsNone(row['rung_id'])
            self.assertIsNone(row['instruction_id'])

    def test_missing_sfc_and_file_relationship_addresses_stay_auditable(self) -> None:
        data = deepcopy(provider_data())
        data['sfc_context']['addresses'][0]['relationship_address_id'] = None
        result = build_engineering_assemblies(data)
        self.assertEqual(len(rows(result, 'sfc_reference')), 1)
        self.assertTrue(any(row['provider'] == 'sfc_context' and row['reason'] == 'missing_address'
            for row in result['source_gaps']))
        self.assertTrue(any(row['provider'] == 'file_operations' and row['reason'] == 'missing_address'
            for row in result['source_gaps']))

    def test_stateful_resets_members_and_unknown_boundaries_are_retained(self) -> None:
        result = build_engineering_assemblies(provider_data())
        self.assertEqual(len(rows(result, 'stateful_control')), 2)
        self.assertEqual(len(rows(result, 'stateful_member')), 3)
        self.assertTrue(all(row['related_address_id'] is not None for row in rows(result, 'stateful_member')))
        self.assertTrue(all('stateful_guard' in row['context_flags'] for row in rows(result, 'stateful_control')))
        self.assertTrue(any('opaque_guard' in row['context_flags'] for row in rows(result, 'guard_condition')))

    def test_pending_edit_occurrences_keep_distinct_rung_and_source_ids(self) -> None:
        data = provider_data()
        result = build_engineering_assemblies(data)
        outputs = data['signal_context']['outputs']
        self.assertEqual(len(rows(result, 'boolean_output')), len(outputs) - 1)
        last = outputs[-1]
        self.assertTrue(any(row['rung_id'] == last['rung_id'] and row['source_id'] == last['id']
            for row in rows(result, 'boolean_output')))
        self.assertNotEqual(outputs[0]['rung_id'], last['rung_id'])

    def test_stateful_out_of_bounds_and_missing_type_are_known_gaps(self) -> None:
        original = SOURCE.read_bytes()
        variants = (
            original.replace(b'<Tag Name="Timer" DataType="TIMER"/>', b'<Tag Name="Timer" DataType="TIMER" Dimensions="2"/>')
                .replace(b'TON(Timer,', b'TON(Timer[2],').replace(b'RES(Timer)', b'RES(Timer[2])')
                .replace(b'XIC(Timer.DN)', b'XIC(Timer[2].DN)'),
            original.replace(b'<Tag Name="Timer" DataType="TIMER"/>', b'<Tag Name="Timer"/>'))
        for source in variants:
            result = build_engineering_assemblies(provider_data(source))
            with self.subTest(source=source[:50]):
                self.assertTrue(rows(result, 'stateful_control'))
                self.assertTrue(all('stateful_type_gap' in row['context_flags']
                    for row in result['memberships'] if row['provider'] == 'stateful_objects'))

    def test_dynamic_file_slot_is_excluded_without_resolving_symbolic_address(self) -> None:
        source = SOURCE.read_bytes().replace(b'AVE(Samples[0],0,Scaled,Control,?,?);',
            b'FAL(Control,?,?,ALL,Scaled,Sensor+Sensor);')
        parsed = provider_data(source)
        projected = build_engineering_assemblies(parsed)
        expression_ids = {row['id'] for row in parsed['file_operations']['expression_nodes']
            if row['kind'] == 'reference'}
        self.assertEqual(len(expression_ids), 2)
        self.assertEqual({row['source_id'] for row in rows(projected, 'file_read')}, expression_ids)
        data = deepcopy(provider_data())
        slot = data['file_operations']['slots'][2]
        slot['status'] = 'symbolic_address'
        result = build_engineering_assemblies(data)
        self.assertEqual(result['coverage']['excluded_by_reason']['dynamic_address'], 1)
        self.assertFalse(any(row['source_id'] == slot['id'] for row in result['memberships']
            if row['provider'] == 'file_operations'))

    def test_communication_boundary_is_explicit_even_without_signal_membership(self) -> None:
        result = build_engineering_assemblies(provider_data())
        self.assertIn({'provider': 'signal_context', 'reason': 'communication_semantics_unmodeled', 'count': 1}, result['source_gaps'])

    def test_membership_group_visit_and_byte_limits_are_reserved_before_append(self) -> None:
        metadata = {'id': '', 'address_id': '', 'membership_ids': [], 'rung_ids': [],
            'providers': sorted(PROVIDERS), 'boundary_flags': sorted(FLAGS), 'scan_status': 'truncated'}
        self.assertLess(len(json.dumps(metadata, separators=(',', ':'))), GROUP_BYTES)
        data = empty()
        identifiers = [f'operand_{index:03d}' for index in range(10)]
        data['access']['operands'] = [{'id': identifier, 'instruction_id': f'I{index:03d}',
            'rung_id': f'rung_{index:03d}', 'role': 'read'} for index, identifier in enumerate(identifiers)]
        data['relationships']['addresses'] = [{'id': 'A', 'read_operand_ids': identifiers}]
        data['signal_context']['addresses'] = [{'id': 'A', 'read_operand_ids': identifiers}]
        unique = build_engineering_assemblies(data)
        for row in data['access']['operands']:
            row['rung_id'] = 'rung_000'
        shared = build_engineering_assemblies(data)
        self.assertEqual(unique['budget']['retained_bytes'] - shared['budget']['retained_bytes'],
            9 * len(json.dumps('rung_000')))
        for result in (unique, shared):
            self.assertLess(len(json.dumps(result).encode()), result['budget']['retained_bytes'])
        for limit, value in (('MAX_ASSEMBLY_MEMBERSHIPS', 1), ('MAX_ASSEMBLY_GROUPS', 1),
                ('MAX_ASSEMBLY_VISITS', 1), ('MAX_ENGINEERING_ASSEMBLIES_BYTES', 33_000)):
            with self.subTest(limit=limit), patch('plc_workbench.engineering_assemblies.' + limit, value):
                result = build_engineering_assemblies(provider_data())
                self.assertEqual(result['scan_status'], 'truncated')
                self.assertTrue(all(row['scan_status'] == 'truncated' for row in result['groups']))
                self.assertLessEqual(result['budget']['retained_bytes'], result['budget']['max_bytes'])
                self.assertLessEqual(len(result['memberships']), result['budget']['max_memberships'])
                self.assertLessEqual(len(result['groups']), result['budget']['max_groups'])
                self.assertLessEqual(result['budget']['visited_rows'] + result['budget']['visited_links'], result['budget']['max_visits'])

    def test_upstream_dependency_truncation_propagates_to_all_assembly_groups(self) -> None:
        for context, field in (('guard_dependencies', 'traversal_status'), ('candidate_context', 'scan_status')):
            data = deepcopy(provider_data())
            data['signal_context']['outputs'][0][context][field] = 'truncated'
            result = build_engineering_assemblies(data)
            with self.subTest(context=context):
                self.assertEqual(result['scan_status'], 'truncated')
                self.assertTrue(all('source_truncated' in row['boundary_flags'] for row in result['groups']))

    def test_identity_collision_is_rejected_without_disclosing_input(self) -> None:
        data = empty()
        data['relationships']['addresses'] = [
            {'id': 'PRIVATE_A', 'read_operand_ids': ['same']},
            {'id': 'PRIVATE_B', 'read_operand_ids': ['same']}]
        with self.assertRaises(EngineeringAssembliesError) as error:
            build_engineering_assemblies(data)
        self.assertNotIn('PRIVATE', str(error.exception))

    def test_missing_providers_and_empty_complete_data_have_distinct_statuses(self) -> None:
        self.assertEqual(build_engineering_assemblies(empty())['status'], 'complete')
        missing = build_engineering_assemblies({})
        self.assertEqual(missing['status'], 'partial')
        self.assertEqual(missing['coverage']['providers_by_status']['missing'], 6)
        self.assertEqual(len(missing['source_gaps']), 6)

    def test_no_process_filesystem_or_network_calls_are_needed_for_projection(self) -> None:
        data = provider_data()
        with patch('builtins.open', side_effect=AssertionError('file access')), \
                patch('subprocess.Popen', side_effect=AssertionError('process')), \
                patch('socket.socket', side_effect=AssertionError('network')):
            self.assertTrue(build_engineering_assemblies(data)['groups'])


if __name__ == '__main__':
    unittest.main()
