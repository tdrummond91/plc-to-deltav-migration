"""Invented module layouts exercise inferred names without plant data."""
from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch

from plc_workbench.module_io import (
    MODULE_IO_KINDS, NAME_ORIGINS, NAME_REASONS, ModuleIOError, derive_module_io_names,
)
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def port(number: str = '1', kind: str = 'ICP', address: str = '3',
         upstream: str = 'true') -> str:
    return f'<Port Id="{number}" Type="{kind}" Address="{address}" Upstream="{upstream}"/>'


def module(name: str = 'Card', parent: str = 'Local', parent_port: str = '1',
           ports: str | None = None, communications: str = '', extra: str = '') -> str:
    ports = port() if ports is None else ports
    return (f'<Module Name="{name}" ParentModule="{parent}" ParentModPortId="{parent_port}" {extra}>'
            f'<Ports>{ports}</Ports><Communications>{communications}</Communications></Module>')


def connection(tags: str = '<InputTag/>', name: str = 'Data', extra: str = '') -> str:
    return f'<Connection Name="{name}" {extra}>{tags}</Connection>'


def communications(tags: str = '<InputTag/>', extra: str = '') -> str:
    return '<Connections>' + connection(tags, extra=extra) + '</Connections>'


LOCAL = module('Local', 'Local', ports=port(address='0', upstream='false'))
BRIDGE = module('Bridge', ports=port(address='2') + port('2', 'Ethernet', '192.0.2.1', 'false'))
REMOTE = module('Remote', 'Bridge', '2',
                port('1', 'Ethernet', '192.0.2.2') + port('2', 'ICP', '0', 'false'))


def inventory(modules: str, *, other_controller: str = ''):
    return analyze_snapshot(snapshot_from_bytes((
        '<RSLogix5000Content><Controller Name="Invented"><Modules>' + modules +
        '</Modules></Controller>' + other_controller + '</RSLogix5000Content>'
    ).encode()))


def rows(modules: str):
    return list(derive_module_io_names(inventory(modules)).values())


class ModuleIONamingTests(unittest.TestCase):
    def test_local_slot_input_output_and_config_names(self) -> None:
        result = rows(LOCAL + module(communications='<ConfigTag/>' +
                                    communications('<InputTag/><OutputTag/>')))
        self.assertEqual(result, [
            {'name': 'Local:3:C', 'name_origin': 'backplane_slot', 'reason': None},
            {'name': 'Local:3:I', 'name_origin': 'backplane_slot', 'reason': None},
            {'name': 'Local:3:O', 'name_origin': 'backplane_slot', 'reason': None},
        ])

    def test_remote_slot_and_direct_ethernet_have_distinct_origins(self) -> None:
        result = rows(LOCAL + BRIDGE + REMOTE +
                      module('RemoteCard', 'Remote', '2', communications=communications()) +
                      module('Direct', 'Bridge', '2', port(kind='Ethernet', address='192.0.2.10'),
                             '<ConfigTag/>' + communications('<InputTag/><OutputTag/>')))
        self.assertEqual([item['name'] for item in result],
                         ['Remote:3:I', 'Direct:C', 'Direct:I', 'Direct:O'])
        self.assertEqual([item['name_origin'] for item in result],
                         ['backplane_slot', 'module_name', 'module_name', 'module_name'])

    def test_explicit_name_does_not_require_topology_but_must_be_a_whole_root(self) -> None:
        for name, expected in [('Known:4:I', None), ('Known:I.Member', 'invalid_explicit_name'),
                               ('Known', 'invalid_explicit_name'), ('', 'invalid_explicit_name'),
                               ('Known:4:I[1]', 'invalid_explicit_name'),
                               ('pROGRAM:I', 'invalid_explicit_name')]:
            with self.subTest(name=name):
                result = rows(module(parent='Absent', communications=communications(
                    f'<InputTag Name="{name}"/>')))[0]
                self.assertEqual(result['reason'], expected)
                self.assertEqual(result['name_origin'], 'explicit_name' if expected is None else 'unavailable')

    def test_suffixes_are_connection_specific_and_malformed_values_never_default(self) -> None:
        result = rows(LOCAL + module(communications='<Connections>' +
                      connection('<InputTag/><OutputTag/>', 'One',
                                 'InputTagSuffix="I2_Extra" OutputTagSuffix="O3"') +
                      connection('<InputTag/>', 'Two', 'InputTagSuffix="I4"') + '</Connections>'))
        self.assertEqual([item['name'] for item in result], ['Local:3:I2_Extra', 'Local:3:O3', 'Local:3:I4'])
        for bad in ['', ':I', 'O', 'I.Data', 'I[0]', ' I', 'i']:
            with self.subTest(bad=bad):
                self.assertEqual(rows(LOCAL + module(communications=communications(
                    extra=f'InputTagSuffix="{bad}"')))[0]['reason'], 'invalid_suffix')

    def test_duplicate_derived_names_are_retained_for_resolver_ambiguity(self) -> None:
        result = rows(LOCAL + module(communications='<Connections>' + connection(name='One') +
                                   connection(name='Two') + '</Connections>') +
                      module('OtherCard', communications=communications()))
        self.assertEqual([item['name'] for item in result], ['Local:3:I'] * 3)

    def test_duplicate_module_context_is_not_selected_by_source_order(self) -> None:
        result = rows(LOCAL + module(communications=communications()) + module('cARD'))
        self.assertEqual(result[0]['reason'], 'ambiguous_module_context')
        result = rows(LOCAL + LOCAL + module(communications=communications()))
        self.assertEqual(result[0]['reason'], 'ambiguous_parent_module')

    def test_reserved_qualified_namespace_cannot_be_a_derived_root(self) -> None:
        result = rows(LOCAL + BRIDGE + module('Program', 'Bridge', '2',
                                             port(kind='Ethernet', address='192.0.2.10'),
                                             communications()))
        self.assertEqual(result[0]['reason'], 'invalid_module_name')

    def test_duplicate_connection_names_or_ids_are_unavailable(self) -> None:
        for first, second in [(connection(name='One'), connection(name='oNE')),
                              (connection(name='One', extra='Id="1"'),
                               connection(name='Two', extra='Id="1"'))]:
            result = rows(LOCAL + module(communications='<Connections>' + first + second + '</Connections>'))
            self.assertEqual([item['reason'] for item in result], ['ambiguous_connection_context'] * 2)

    def test_upstream_ambiguity_duplicates_and_invalid_flags_are_unavailable(self) -> None:
        for ports, expected in [(port(upstream='false'), 'missing_upstream_port'),
                                (port() + port('2'), 'ambiguous_upstream_port'),
                                (port() + port(upstream='false'), 'invalid_upstream_port'),
                                (port(upstream='maybe'), 'invalid_upstream_port'),
                                (port(number='-1'), 'invalid_upstream_port')]:
            with self.subTest(expected=expected):
                self.assertEqual(rows(LOCAL + module(ports=ports, communications=communications()))[0]['reason'],
                                 expected)

    def test_missing_and_duplicate_parent_ports(self) -> None:
        for root, expected in [(module('Local', 'Local', ports=''), 'missing_parent_port'),
                               (LOCAL.replace('</Ports>', port(upstream='false') + '</Ports>'),
                                'ambiguous_parent_port')]:
            self.assertEqual(rows(root + module(communications=communications()))[0]['reason'], expected)

    def test_unsupported_and_mismatched_bus_types_do_not_guess_slot_names(self) -> None:
        for parent_type, child_type, expected in [('ICP', 'Ethernet', 'port_type_mismatch'),
                                                 ('ControlNet', 'ControlNet', 'unsupported_port_type')]:
            root = module('Local', 'Local', ports=port(kind=parent_type, upstream='false'))
            self.assertEqual(rows(root + module(ports=port(kind=child_type),
                                               communications=communications()))[0]['reason'], expected)

    def test_slots_are_exact_canonical_unsigned_decimal(self) -> None:
        for slot in ['03', '-1', '+3', '3.0', '3:2', '']:
            self.assertEqual(rows(LOCAL + module(ports=port(address=slot),
                                               communications=communications()))[0]['reason'], 'invalid_slot')

    def test_missing_parent_and_separate_controller_are_not_cross_bound(self) -> None:
        source = inventory(module(communications=communications()),
                           other_controller='<Controller Name="Other"><Modules>' + LOCAL +
                           '</Modules></Controller>')
        self.assertEqual(list(derive_module_io_names(source).values())[0]['reason'], 'missing_parent_module')

    def test_incomplete_ancestor_chain_remains_unavailable(self) -> None:
        result = rows(REMOTE + module('RemoteCard', 'Remote', '2', communications=communications()))
        self.assertEqual(result[0]['reason'], 'missing_parent_module')

    def test_local_root_can_omit_parent_name_but_arbitrary_roots_cannot(self) -> None:
        root = LOCAL.replace(' ParentModule="Local"', '')
        self.assertEqual(rows(root + module(communications=communications()))[0]['name'], 'Local:3:I')
        root = module('Unknown', 'Unknown', ports=port(upstream='false')).replace(' ParentModule="Unknown"', '')
        self.assertEqual(rows(root + module(parent='Unknown', communications=communications()))[0]['reason'],
                         'missing_parent_module')

    def test_topology_cycle_and_depth_are_explicit(self) -> None:
        both = port() + port('2', upstream='false')
        cycle = module('A', 'B', '2', both, communications()) + module('B', 'A', '2', both)
        self.assertEqual(rows(cycle)[0]['reason'], 'topology_cycle')
        with patch('plc_workbench.module_io.MAX_TOPOLOGY_DEPTH', 1):
            self.assertEqual(rows(LOCAL + module(communications=communications()))[0]['reason'],
                             'topology_depth_limit')
        self.assertEqual(rows(module('Self', 'Self', ports=port(upstream='false'),
                                     communications=communications()))[0]['reason'], 'topology_cycle')

    def test_parent_id_spelling_alias_never_hides_conflict(self) -> None:
        child = module(communications=communications()).replace('ParentModPortId=', 'ParentModPortID=')
        self.assertEqual(rows(LOCAL + child)[0]['name'], 'Local:3:I')
        conflict = module(communications=communications(), extra='ParentModPortID="2"')
        self.assertEqual(rows(LOCAL + conflict)[0]['reason'], 'ambiguous_parent_port')

    def test_malformed_private_contexts_do_not_bind(self) -> None:
        source = inventory(LOCAL + module(communications=communications()))
        io = next(entity for entity in source.entities if entity.kind == 'module_input_tag')
        for changes, expected in [({'parent_id': None}, 'missing_connection_context'),
                                  ({'scope_id': 'absent'}, 'missing_module_context')]:
            altered = replace(source, entities=[replace(entity, **changes) if entity.id == io.id else entity
                                                for entity in source.entities])
            self.assertEqual(derive_module_io_names(altered)[io.id]['reason'], expected)

    def test_values_and_datatypes_have_no_effect_and_source_is_unchanged(self) -> None:
        base = LOCAL + module(communications=communications())
        secret = base.replace('<InputTag/>', '<InputTag DataType="PRIVATE_SENTINEL">'
                              '<Data><Value>PRIVATE_SENTINEL</Value></Data></InputTag>')
        source = inventory(secret)
        before = source.to_dict()
        first = derive_module_io_names(source)
        second = derive_module_io_names(source)
        self.assertEqual(list(first.values()), rows(base))
        self.assertEqual(first, second)
        self.assertEqual(source.to_dict(), before)
        self.assertNotIn('PRIVATE_SENTINEL', str(first))
        for row in first.values():
            self.assertEqual(set(row), {'name', 'name_origin', 'reason'})
            self.assertIn(row['name_origin'], NAME_ORIGINS)
            self.assertTrue(row['reason'] is None or row['reason'] in NAME_REASONS)
        self.assertEqual(set(first), {entity.id for entity in source.entities if entity.kind in MODULE_IO_KINDS})

    def test_name_lengths_and_repeated_prefix_expansion_are_bounded(self) -> None:
        with patch('plc_workbench.module_io.MAX_IO_NAME_LENGTH', 8):
            explicit = rows(module(communications=communications('<InputTag Name="LongName:I"/>')))
            self.assertEqual(explicit[0]['reason'], 'name_length_limit')
            derived = rows(LOCAL + module(communications=communications()))
            self.assertEqual(derived[0]['reason'], 'name_length_limit')
        source = inventory(LOCAL + module(communications=communications('<InputTag/>' * 3)))
        self.assertEqual(len(derive_module_io_names(source)), 3)
        with patch('plc_workbench.module_io.MAX_EXPANDED_NAME_CHARS', 26):
            with self.assertRaises(ModuleIOError):
                derive_module_io_names(source)
            from plc_workbench.references import ReferenceError, analyze_references
            with self.assertRaises(ReferenceError):
                analyze_references(source)


if __name__ == '__main__':
    unittest.main()
