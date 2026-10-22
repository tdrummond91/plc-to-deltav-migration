"""Exact documented catalog facts do not guess field layouts or model suffixes."""
from __future__ import annotations

import json
import unittest
from urllib.parse import urlsplit

from plc_workbench.module_catalog import CATALOG_LIBRARY, CATALOG_TYPES, lookup_catalog


class ModuleCatalogTests(unittest.TestCase):
    def test_legacy_39_models_keep_their_single_field_type(self):
        old = {f'1756-{model}': kind for kind, models in (
            ('di', 'IA16 IB16 IB32 IC16 IN16 IV16 IA16I IB16I IH16I IM16I IB16D IA8D'),
            ('do', 'OA8 OB8 OB32 OC8 ON8 OA16I OB8I OB16I OH8I OW16I OX8I OA16 OB8EI OB16E OV16E OA8E OB16D OA8D'),
            ('ai', 'IF16 IF8 IF6I IR6I IT6I'), ('ao', 'OF4 OF6CI OF6VI OF8'),
        ) for model in models.split()}
        self.assertEqual(len(old), 39)
        for catalog, kind in old.items():
            with self.subTest(catalog=catalog):
                self.assertEqual(lookup_catalog(catalog, '1')['field_types'], [kind])
                self.assertEqual(CATALOG_TYPES[catalog], kind)

    def test_analog_hart_isolated_and_temperature_models_have_explicit_capacity(self):
        cases = {
            '1756-IF16H': ('ai', 16), '1756-IF16IHK': ('ai', 16),
            '1756-IF8H': ('ai', 8), '1756-IF8IH': ('ai', 8), '1756-IF8IK': ('ai', 8),
            '1756-IF6CIS': ('ai', 6), '1756-IRT8IK': ('ai', 8),
            '1756-IR12K': ('ai', 12), '1756-IT6I2': ('ai', 6), '1756-IT16K': ('ai', 16),
            '1756-OF8HK': ('ao', 8), '1756-OF8IH': ('ao', 8), '1756-OF8IK': ('ao', 8),
        }
        for catalog, (kind, count) in cases.items():
            with self.subTest(catalog=catalog):
                record = lookup_catalog(catalog, '1')
                self.assertEqual(record['role'], 'field_io')
                self.assertEqual(record['field_types'], [kind])
                self.assertEqual(record['capacity'], {kind: count})
                self.assertEqual(record['capacity_basis'], 'documented_capacity')
        for catalog, count in (('1756-IF8', 8), ('1756-IF8K', 8),
                               ('1756-IF16', 16), ('1756-IF16K', 16)):
            record = lookup_catalog(catalog, '1')
            self.assertEqual(record['capacity'], {'ai': count})
            self.assertEqual(record['capacity_basis'], 'maximum_configuration_dependent')

    def test_mixed_analog_card_retains_both_directions_without_single_type_alias(self):
        for catalog in ('1756-IF4FXOF2F', '1756-IF4FXOF2FK'):
            record = lookup_catalog(catalog, '1')
            self.assertEqual(record['field_types'], ['ai', 'ao'])
            self.assertEqual(record['capacity'], {'ai': 4, 'ao': 2})
            self.assertEqual(record['role'], 'field_io')
            self.assertNotIn(catalog, CATALOG_TYPES)

    def test_networks_and_controllers_have_no_physical_point_capacity(self):
        for role, catalogs in (
            ('communication', ('1756-EN2T', '1756-ENBT', '1756-EN2TR', '1756-EN3TR',
                               '1756-DHRIO', '1756-CNBR', '1756-DNBK', '1756-EN2TRXT')),
            ('controller', ('1756-L71', '1756-L73K', '1756-L81E', '1756-L83ES', '1756-L7SP')),
        ):
            for catalog in catalogs:
                with self.subTest(catalog=catalog):
                    record = lookup_catalog(catalog, '1')
                    self.assertEqual(record['role'], role)
                    self.assertEqual(record['field_types'], [])
                    self.assertEqual(record['capacity'], {})
                    self.assertEqual(record['capacity_basis'], 'not_applicable')
                    self.assertNotIn(catalog, CATALOG_TYPES)

    def test_flex_analog_capacities_are_channel_counts_not_transfer_word_counts(self):
        for catalog, capacity in (
            ('1794-IE8', {'ai': 8}), ('1794-IE8XT', {'ai': 8}), ('1794-IE12', {'ai': 12}),
            ('1794-OE4', {'ao': 4}), ('1794-OE4XT', {'ao': 4}), ('1794-OE12', {'ao': 12}),
            ('1794-IE4XOE2', {'ai': 4, 'ao': 2}), ('1794-IE4XOE2XT', {'ai': 4, 'ao': 2}),
            ('1794-IE8XOE4', {'ai': 8, 'ao': 4}),
        ):
            with self.subTest(catalog=catalog):
                record = lookup_catalog(catalog, '1')
                self.assertEqual(record['capacity'], capacity)
                self.assertEqual(record['field_types'], list(capacity))
                self.assertEqual(record['family'], '1794 FLEX analogue I/O')
                self.assertEqual(record['publication'], '1794-UM062B-EN-P')

    def test_unknown_vendor_case_suffix_series_and_malformed_input_stay_unknown(self):
        for model, vendor in (
            ('1756-IF8H', '2'), ('1756-IF8H', None), ('1756-IF8H', 1),
            ('1756-IF8H', '01'), ('1756-if8h', '1'), ('1756-IF8H/A', '1'),
            ('1756-IF8H ', '1'), (' 1756-IF8H', '1'), ('1756-IF8HH', '1'),
            ('1756-OF6CIK', '1'), ('1756-OF8IHXT', '1'), ('1756-L999E', '1'),
            ('AI_PID', '1'), ('<script>1756-IF8H</script>', '1'),
            ('', '1'), (None, '1'), ([], '1'), ({}, '1'),
        ):
            with self.subTest(model=model, vendor=vendor):
                self.assertIsNone(lookup_catalog(model, vendor))

    def test_records_are_bounded_json_facts_with_provenance_and_detached_results(self):
        self.assertGreater(len(CATALOG_LIBRARY), 100)
        allowed = {'configurator.rockwellautomation.com', 'literature.rockwellautomation.com'}
        for catalog in CATALOG_LIBRARY:
            record = lookup_catalog(catalog, '1')
            self.assertEqual(record['catalog_number'], catalog)
            self.assertEqual(record['vendor'], '1')
            self.assertGreater(record['reference_page'], 0)
            self.assertTrue(record['publication'].startswith(('1756-TD', '1794-UM')))
            self.assertLess(len(record['description']), 100)
            self.assertLess(len(json.dumps(record)), 1024)
            self.assertEqual(urlsplit(record['reference']).scheme, 'https')
            self.assertIn(urlsplit(record['reference']).hostname, allowed)
            self.assertEqual(set(record['field_types']), set(record['capacity']))
            self.assertTrue(all(type(count) is int and count > 0 for count in record['capacity'].values()))
            self.assertNotIn('member_layout', record)
            self.assertNotIn('terminal', record)
        record = lookup_catalog('1756-IF8H', '1')
        record['capacity']['ai'] = 999
        record['field_types'].append('do')
        record['description'] = 'Changed display only'
        self.assertEqual(lookup_catalog('1756-IF8H', '1')['capacity'], {'ai': 8})
        self.assertEqual(lookup_catalog('1756-IF8H', '1')['field_types'], ['ai'])
        with self.assertRaises(TypeError):
            CATALOG_LIBRARY['1756-IF8H']['capacity']['ai'] = 999


if __name__ == '__main__':
    unittest.main()
