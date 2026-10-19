"""Invented rack proofs join source assemblies without changing old providers."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
import unittest
from unittest.mock import patch

from plc_workbench.engineering_assemblies import (
    EngineeringAssembliesError, build_engineering_assemblies)
from plc_workbench.rack_backing_context import _id as rack_id
from plc_workbench.relationships import _identifier
from plc_workbench.source_reuse import source_reuse_scope
from test_engineering_assemblies import provider_data, rows
from test_rack_backing_context import capture, fixture


def assembly_fixture(*, rungs: tuple[str, ...] | None = None, sfc: str | None = None) -> str:
    """Independent paths exercise aliases, direct backing and both guard ends."""
    return fixture(tags='<Tag Name="Permit" DataType="BOOL"/><Tag Name="Dest" DataType="BOOL"/>',
        rungs=rungs if rungs is not None else (
            'XIC(ProbeAlias)OTE(Dest);',
            'XIC(Remote:I.Slot[3].Data.0)OTE(Dest);',
            'XIC(Permit)OTE(Remote:3:O.Data.0);',
            'XIC(Remote:3:I.Data.0)OTE(Remote:3:O.Data.0);',
            'EQU(1,2)XIC(S:FS)OTE(Dest);',
            'XIC(Remote:I.Slot[3].Data.0)OTE(Remote:O.Slot[3].Data.0);'),
        sfc=sfc if sfc is not None else 'ProbeAlias OR Remote:I.Slot[3].Data.0 OR Remote:3:I.Data.0')


@lru_cache(maxsize=16)
def _captured(source: str) -> dict:
    with source_reuse_scope():
        data = deepcopy(provider_data(source.encode()))
        data['rack_backing_context'] = capture(source)[-1].to_dict()
        return data


def rack_data(source: str | None = None) -> dict:
    return deepcopy(_captured(assembly_fixture() if source is None else source))


class EngineeringAssembliesRackTests(unittest.TestCase):
    def test_exact_backing_groups_join_direct_alias_cross_rung_and_sfc_sources(self) -> None:
        data = rack_data()
        before = deepcopy(data)
        old = build_engineering_assemblies(data, schema_version=2)
        result = build_engineering_assemblies(data, schema_version=3)
        self.assertEqual(data, before)
        self.assertEqual(result, build_engineering_assemblies(data, schema_version=3))
        self.assertEqual(result['analyzer_version'], 'engineering-assemblies-3')
        self.assertEqual(result['coverage']['excluded_by_reason']['binding_or_namespace'], 0)
        self.assertGreater(old['coverage']['excluded_by_reason']['binding_or_namespace'], 0)
        root = next(row for row in data['rack_backing_context']['roots'] if row['direction'] == 'input')
        address_id = _identifier('relationship_address_', data['relationships']['snapshot']['id'],
            root['backing_tag_id'], '.Slot[3].Data.0')
        group = next(row for row in result['groups'] if row['id'] == address_id)
        self.assertEqual(group['providers'], ['sfc_context', 'signal_context'])
        self.assertEqual(len(group['rung_ids']), 4)
        self.assertNotIn(address_id, {row['id'] for row in result['supplemental_addresses']})
        members = [row for row in result['memberships'] if row['group_id'] == address_id]
        self.assertTrue(any(row['rack_source_use_ids'] for row in members))
        self.assertTrue(any(not row['rack_source_use_ids'] for row in members))
        self.assertEqual(len([row for row in members if row['relation'] == 'sfc_reference']), 3)
        self.assertEqual(result['coverage']['rack_memberships_by_relation'], {
            'read': 2, 'write': 2, 'read_write': 0, 'unknown': 0,
            'boolean_condition': 2, 'boolean_output': 2, 'guard_condition': 3, 'sfc_reference': 2})
        self.assertEqual(result['coverage']['known_non_address_guard_inputs_by_kind'],
            {'literal': 2, 'system_flag': 1})
        self.assertEqual(result['execution_analysis'], 'not_implemented')
        self.assertEqual(result['equipment_identity'], 'not_inferred')

    def test_rack_target_recovers_exact_read_and_both_rack_ends_keep_both_proofs(self) -> None:
        data = rack_data()
        result = build_engineering_assemblies(data, schema_version=3)
        outputs = data['signal_context']['outputs']
        target_only = next(row for row in outputs if row['target_status'] == 'unbound'
            and not row['has_binding_gap'])
        pair = next(row for row in rows(result, 'guard_condition')
            if row['instruction_id'] == target_only['instruction_id'])
        self.assertEqual(len(pair['rack_source_use_ids']), 1)
        self.assertIsNotNone(pair['related_address_id'])
        both = [row for row in rows(result, 'guard_condition') if len(row['rack_source_use_ids']) == 2]
        self.assertEqual(len(both), 1)
        self.assertEqual(both[0]['rack_source_use_ids'], sorted(both[0]['rack_source_use_ids']))
        known = {row['id']: row for row in data['rack_backing_context']['uses']}
        self.assertEqual({known[key]['role'] for key in both[0]['rack_source_use_ids']}, {'read', 'write'})

    def test_backing_only_addresses_are_supplemented_once_and_reverse_ids_are_retained(self) -> None:
        data = rack_data(assembly_fixture(rungs=('XIC(ProbeAlias)OTE(Remote:3:O.Data.0);',), sfc='ProbeAlias'))
        result = build_engineering_assemblies(data, schema_version=3)
        self.assertEqual(result['coverage']['supplemental_addresses_total'], 2)
        self.assertEqual(len({row['id'] for row in result['supplemental_addresses']}), 2)
        source_ids = {row['id'] for row in data['signal_context']['condition_reads']}
        self.assertTrue(source_ids <= {row['source_id'] for row in result['memberships']})
        self.assertTrue(all(set(row) == {'id', 'target_id', 'suffix'} for row in result['supplemental_addresses']))
        self.assertEqual(result['coverage']['rack_memberships_total'], 6)

    def test_exact_spelling_never_coalesces_case_or_zero_padded_bit_suffixes(self) -> None:
        data = rack_data(assembly_fixture(rungs=('XIC(Remote:3:I.Data.0);',
            'XIC(Remote:3:I.Data.00);', 'XIC(Remote:3:I.data.0);'), sfc=''))
        result = build_engineering_assemblies(data, schema_version=3)
        self.assertEqual({row['suffix'] for row in result['supplemental_addresses']},
            {'.Slot[3].Data.0', '.Slot[3].Data.00', '.Slot[3].data.0'})
        self.assertEqual(len(result['groups']), 3)

    def test_unsupported_suffix_namespace_and_missing_root_remain_exclusions(self) -> None:
        base = assembly_fixture(rungs=('XIC(Remote:3:I.Data.32)OTE(Dest);',), sfc='Remote:3:I.Data.32')
        variants = (base,
            assembly_fixture().replace('<RLLContent>', '<RLLContent xmlns="urn:foreign">'),
            assembly_fixture().replace('CatalogNumber="1756-EN2T"', 'CatalogNumber="Unknown"'))
        for source in variants:
            with self.subTest(source=source[-80:]):
                data = rack_data(source)
                result = build_engineering_assemblies(data, schema_version=3)
                self.assertGreater(result['coverage']['excluded_by_reason']['binding_or_namespace'], 0)
                accepted = {row['id'] for row in data['rack_backing_context']['uses'] if row['disposition'] == 'associated'}
                self.assertTrue(all(set(row['rack_source_use_ids']) <= accepted for row in result['memberships']))
        result = build_engineering_assemblies(rack_data(base), schema_version=3)
        self.assertEqual(result['coverage']['rack_memberships_total'], 0)

    def test_non_address_conditions_are_counted_once_per_accepted_output_dependency(self) -> None:
        source = assembly_fixture(rungs=('EQU(1,2)XIC(S:FS)[OTE(Dest),OTE(Remote:3:O.Data.0)];',), sfc='')
        data = rack_data(source)
        old = build_engineering_assemblies(data, schema_version=2)
        result = build_engineering_assemblies(data, schema_version=3)
        self.assertEqual(result['coverage']['known_non_address_guard_inputs_by_kind'], {'literal': 4, 'system_flag': 2})
        self.assertEqual(result['coverage']['excluded_by_reason']['binding_or_namespace'], 0)
        self.assertGreater(old['coverage']['excluded_by_reason']['binding_or_namespace'], 0)
        self.assertFalse(rows(result, 'guard_condition'))

    def test_opaque_guard_keeps_qualified_address_and_its_boundary(self) -> None:
        source = assembly_fixture(rungs=('PrivateOpaque()XIC(ProbeAlias)OTE(Dest);',), sfc='')
        result = build_engineering_assemblies(rack_data(source), schema_version=3)
        guards = rows(result, 'guard_condition')
        self.assertEqual(len(guards), 1)
        self.assertIn('opaque_guard', guards[0]['context_flags'])
        self.assertEqual(len(guards[0]['rack_source_use_ids']), 1)

    def test_snapshot_consumer_source_and_correspondence_tampering_fail_closed(self) -> None:
        def first_use(data):
            return next(row for row in data['rack_backing_context']['uses'] if row['kind'] == 'rll')
        mutations = (
            lambda d: d['rack_backing_context']['snapshot'].update(id='PRIVATE_OTHER'),
            lambda d: d['signal_context']['snapshot'].update(id='PRIVATE_OTHER'),
            lambda d: d['rack_backing_context'].update(schema_version=True),
            lambda d: first_use(d).update(id='PRIVATE_FORGED'),
            lambda d: first_use(d).update(predicate_node_id='PRIVATE_FORGED'),
            lambda d: first_use(d).update(output_id='PRIVATE_FORGED'),
            lambda d: first_use(d).update(role='write'),
            lambda d: first_use(d).update(candidate_id='PRIVATE_FORGED'),
            lambda d: d['rack_backing_context']['addresses'][0].update(backing_suffix='.Slot[4].Data.0'),
            lambda d: d['rack_backing_context']['addresses'][0].update(backing_tag_id='PRIVATE_FORGED'),
            lambda d: d['rack_backing_context']['uses'].append(deepcopy(first_use(d))),
            lambda d: d['signal_context']['condition_reads'][0].update(instruction_id='PRIVATE_FORGED'),
            lambda d: d['signal_context']['condition_reads'][0].update(status='namespace_gap'),
            lambda d: d['sfc_context']['references'][0].update(status='namespace_gap'),
        )
        for index, mutate in enumerate(mutations):
            data = rack_data()
            mutate(data)
            with self.subTest(index=index), self.assertRaises(EngineeringAssembliesError) as error:
                build_engineering_assemblies(data, schema_version=3)
            self.assertNotIn('PRIVATE', str(error.exception))

    def test_matching_proof_hash_cannot_redirect_a_source_to_another_consumer(self) -> None:
        data = rack_data()
        use = next(row for row in data['rack_backing_context']['uses'] if row['kind'] == 'rll')
        exact = next(row for row in data['signal_context']['condition_reads'] if row['status'] == 'exact_address')
        use.update(source_id=exact['id'], id=rack_id('use', 'rll', exact['id']), predicate_node_id=exact['condition_node_id'])
        with self.assertRaises(EngineeringAssembliesError):
            build_engineering_assemblies(data, schema_version=3)

    def test_limits_stop_indexing_and_reserve_new_memberships_atomically(self) -> None:
        data = rack_data()
        result = build_engineering_assemblies(data, schema_version=3)
        for name, limit in (('MAX_ASSEMBLY_VISITS', 1), ('MAX_ASSEMBLY_VISITS', 38),
                ('MAX_ASSEMBLY_VISITS', 80), ('MAX_ASSEMBLY_MEMBERSHIPS', 1),
                ('MAX_ASSEMBLY_GROUPS', 1), ('MAX_ENGINEERING_ASSEMBLIES_BYTES', 34000),
                ('MAX_ENGINEERING_ASSEMBLIES_BYTES', result['budget']['retained_bytes'] - 1)):
            with self.subTest(name=name, limit=limit), patch('plc_workbench.engineering_assemblies.' + name, limit):
                limited = build_engineering_assemblies(data, schema_version=3)
                self.assertEqual(limited['scan_status'], 'truncated')
                self.assertLessEqual(limited['coverage']['visited_rows'] + limited['coverage']['visited_links'],
                    limited['budget']['max_visits'])
                self.assertLessEqual(limited['budget']['retained_bytes'], limited['budget']['max_bytes'])
                self.assertTrue({row['id'] for row in limited['supplemental_addresses']}
                    <= {row['id'] for row in limited['groups']})
                self.assertLess(len(json.dumps(limited).encode()), limited['budget']['retained_bytes'])
                self.assertEqual(limited['coverage']['rack_memberships_total'],
                    sum(bool(row['rack_source_use_ids']) for row in limited['memberships']))

    def test_all_overlay_indexes_consume_visits_instead_of_preallocating(self) -> None:
        data = rack_data()
        # Invalid late records must not be touched after the visit budget halts.
        data['rack_backing_context']['roots'] += [None] * 100
        with patch('plc_workbench.engineering_assemblies.MAX_ASSEMBLY_VISITS', 1):
            result = build_engineering_assemblies(data, schema_version=3)
        self.assertEqual(result['coverage']['visited_rows'], 1)
        self.assertEqual(result['groups'], [])

    def test_historical_versions_ignore_new_overlay_and_replay_exactly(self) -> None:
        data = rack_data()
        old = deepcopy(data)
        del old['rack_backing_context']
        for version in (1, 2):
            with self.subTest(version=version):
                expected = build_engineering_assemblies(old, schema_version=version)
                self.assertEqual(build_engineering_assemblies(data, schema_version=version), expected)
                self.assertTrue(all('rack_source_use_ids' not in row for row in expected['memberships']))
                self.assertNotIn('rack_memberships_total', expected['coverage'])
        with self.assertRaises(EngineeringAssembliesError):
            build_engineering_assemblies(old, schema_version=3)

    def test_projection_needs_no_filesystem_process_or_network(self) -> None:
        data = rack_data()
        with patch('builtins.open', side_effect=AssertionError('file access')), \
                patch('subprocess.Popen', side_effect=AssertionError('process')), \
                patch('socket.socket', side_effect=AssertionError('network')):
            result = build_engineering_assemblies(data, schema_version=3)
        self.assertGreater(result['coverage']['rack_memberships_total'], 0)


if __name__ == '__main__':
    unittest.main()
