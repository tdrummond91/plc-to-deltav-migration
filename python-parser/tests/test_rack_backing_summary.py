"""Invented rack data shapes: counts investigate backing, never remap it."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from plc_workbench import rack_backing_summary as module
from plc_workbench.rack_backing_summary import (
    DISPOSITIONS, MAX_REPORT_BYTES, RackBackingSummaryError,
    build_rack_backing_summary, render_rack_backing_summary, validate_rack_backing_summary,
)
from plc_workbench.references import analyze_references
from plc_workbench.source import SourceError, analyze_snapshot, snapshot_from_bytes
from plc_workbench.tag_data import analyze_tag_data


FIXTURE = Path(__file__).resolve().parents[2] / 'public/fixtures/synthetic/rack_io_gap_demo.L5X'
ARRAY = ('<ArrayMember Name="Data" DataType="DINT" Dimensions="8">'
         '<Element Index="[3]" Value="0"/></ArrayMember>')
DATA = f'<Data Format="Decorated"><Structure DataType="InventedRack">{ARRAY}</Structure></Data>'


def source(data: str = DATA, *, input_tag: str | None = None, catalog: str = '1794-ACN15',
           vendor: str = '1') -> str:
    # An invented XML shape, not a certified hardware configuration or import.
    text = FIXTURE.read_text(encoding='utf-8')
    text = text.replace('<Module Name="Remote"', f'<Module Vendor="{vendor}" CatalogNumber="{catalog}" Name="Remote"')
    return text.replace('<InputTag/>', input_tag if input_tag is not None else f'<InputTag>{data}</InputTag>')


def capture(text: str | None = None):
    snapshot = snapshot_from_bytes((source() if text is None else text).encode())
    inventory = analyze_snapshot(snapshot)
    return snapshot, inventory, analyze_references(inventory), analyze_tag_data(snapshot, inventory)


def summary(text: str | None = None):
    return build_rack_backing_summary(*capture(text))


def dispositions(text: str):
    return summary(text)['coverage']['candidate_dispositions']


def summary2(text: str | None = None):
    return build_rack_backing_summary(*capture(text), schema_version=2)


def slot_data(direction: str = 'I') -> str:
    # Invented values/topology around the documented CNB member/header pattern.
    status = '<DataValueMember Name="SlotStatusBits" DataType="DINT" Value="0"/>' if direction == 'I' else ''
    fault = '<DataValueMember Name="Fault" DataType="DINT" Value="0"/>' if direction == 'I' else ''
    return (f'<Data Format="Decorated"><Structure DataType="AB:1756_CNB_17SLOT:{direction}:0">'
            f'{status}<ArrayMember Name="Slot" DataType="AB:1756_CNB_SLOT:{direction}:0" Dimensions="17">'
            f'<Element Index="[3]"><Structure DataType="AB:1756_CNB_SLOT:{direction}:0">'
            f'{fault}<DataValueMember Name="Data" DataType="DINT" Value="0"/>'
            '</Structure></Element></ArrayMember></Structure></Data>')


class RackBackingSummaryTests(unittest.TestCase):
    def test_fixed_public_shape_has_no_source_data_and_preserves_inputs(self):
        parts = capture()
        before = [value.to_dict() for value in parts[1:]]
        revision = {'commit': 'a' * 40, 'worktree': 'modified'}
        result = build_rack_backing_summary(*parts, tool_revision=revision)
        revision['commit'] = 'b' * 40
        self.assertEqual(result['tool_revision']['commit'], 'a' * 40)
        c = result['coverage']
        self.assertEqual(c['rack_connections'], 1)
        self.assertEqual(c['rack_declarations'], 2)
        self.assertEqual(c['declarations_by_direction'], {'input': 1, 'output': 1})
        self.assertEqual(c['adapter_families']['rockwell_1794_acn15'], 2)
        self.assertEqual(c['candidate_dispositions']['slot_shape_observed_mapping_unchecked'], 1)
        self.assertEqual(c['candidate_dispositions']['representation_missing'], 1)
        self.assertEqual(c['observed_shape_by_family']['rockwell_1794_acn15'], 1)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['communication_format'], 'not_captured')
        self.assertEqual(result['backing_mapping'], 'not_analyzed')
        text = render_rack_backing_summary(result)
        for private in ('Remote', 'RackCard', 'InventedRack', '1794-ACN15', 'ProbeAlias',
                        'source_id', 'sha256:', 'locator', '192.0.2', 'Data[3]'):
            self.assertNotIn(private, text)
        self.assertEqual(json.loads(text), result)
        self.assertEqual(text, render_rack_backing_summary(deepcopy(result)))
        self.assertEqual(before, [value.to_dict() for value in parts[1:]])

    def test_absent_racks_unrelated_data_and_empty_rack_connection(self):
        empty = '<RSLogix5000Content><Controller Name="Invented"/></RSLogix5000Content>'
        self.assertEqual(summary(empty)['status'], 'complete')
        unrelated = empty.replace('/></RSLogix5000Content>', '><Tags><Tag Name="Other">'
                                 + DATA + '</Tag></Tags></Controller></RSLogix5000Content>')
        self.assertEqual(summary(empty), summary(unrelated))
        empty_rack = source().replace('<InAliasTag/>', '').replace('<OutAliasTag/>', '')
        result = summary(empty_rack)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['coverage']['rack_declarations'], 0)
        self.assertEqual(result['coverage']['rack_connections'], 1)

    def test_all_joint_disposition_buckets_are_reachable(self):
        # Output stays representation_missing; inspect the input-specific bin.
        cases = {
            'source_unqualified': source().replace('<Modules>', '<Modules xmlns="urn:vendor">'),
            'adapter_missing': source().replace('Name="RackCard" ParentModule="Remote"', 'Name="RackCard" ParentModule="Missing"'),
            'adapter_ambiguous': source().replace('</Modules>', '<Module Name="Remote"/></Modules>'),
            'candidate_unavailable': source().replace('<RackConnection>', '<RackConnection Name="Unexpected" >'),
            'backing_tag_missing': source(input_tag=''),
            'backing_tag_ambiguous': source(input_tag=f'<InputTag>{DATA}</InputTag><InputTag/>'),
            'backing_tag_unqualified': source(input_tag=f'<InputTag xmlns="urn:vendor">{DATA}</InputTag>'),
            'backing_name_unavailable': source(input_tag=f'<InputTag Name="Different:I">{DATA}</InputTag>'),
            'representation_missing': source(data=''),
            'representation_unsupported': source(data='<Data Format="L5K">[0]</Data>'),
            'representation_ambiguous': source(data=DATA + '<Data Format="L5K">[0]</Data>'),
            'shape_unsupported': source(data='<Data Format="Decorated"><DataValue DataType="DINT" Value="0"/></Data>'),
            'data_member_missing': source(data=DATA.replace('Name="Data"', 'Name="Different"')),
            'data_member_ambiguous': source(data=DATA.replace(ARRAY, ARRAY + ARRAY.replace('Name="Data"', 'Name="data"'))),
            'data_array_unsupported': source(data=DATA.replace('DataType="DINT"', 'DataType="INT"')),
            'slot_missing': source(data=DATA.replace('Index="[3]"', 'Index="[2]"')),
            'slot_ambiguous': source(data=DATA.replace('<Element Index="[3]" Value="0"/>',
                                                    '<Element Index="[3]" Value="0"/><Element Index="[03]" Value="1"/>')),
            'slot_shape_observed_mapping_unchecked': source(),
        }
        self.assertEqual(set(cases), DISPOSITIONS)
        for expected, xml in cases.items():
            with self.subTest(expected=expected):
                self.assertGreater(dispositions(xml)[expected], 0)

    def test_family_is_only_exact_qualified_vendor_and_catalog_identity(self):
        for vendor, catalog, expected in (
            ('1', '1794-ACN15', 'rockwell_1794_acn15'),
            ('01', '1794-ACN15', 'other'), ('2', '1794-ACN15', 'other'),
            ('1', '1794-ACN15/A', 'other'), ('1', '1794-ACNR15', 'other'),
            ('1', 'PRIVATE_VENDOR_SENTINEL', 'other'), ('', '1794-ACN15', 'missing_identity'),
            ('1', '', 'missing_identity'),
        ):
            with self.subTest(vendor=vendor, catalog=catalog):
                result = summary(source(vendor=vendor, catalog=catalog))
                self.assertEqual(result['coverage']['adapter_families'][expected], 2)
                self.assertNotIn('PRIVATE_VENDOR_SENTINEL', render_rack_backing_summary(result))

    def test_namespaces_ancestors_ports_and_protection_fail_closed(self):
        changes = (
            ('<Modules>', '<Modules xmlns="urn:other">'),
            ('<Modules>', '<Modules Protected="true">'),
            ('<Controller Name=', '<Controller Protected="false" Name='),
            ('<Module Name="Bridge"', '<Module IsEncrypted="" Name="Bridge"'),
            ('<Port ', '<Port xmlns="urn:other" '),
            ('Vendor="1"', 'xmlns:v="urn:vendor" v:Vendor="1"'),
        )
        for old, new in changes:
            with self.subTest(change=new):
                result = summary(source().replace(old, new))
                self.assertEqual(result['coverage']['candidate_dispositions']['source_unqualified'], 2)
                self.assertEqual(result['coverage']['adapter_families']['unavailable_context'], 2)
        # One coherent default namespace is supported; no namespace is privileged.
        coherent = source().replace('<RSLogix5000Content ', '<RSLogix5000Content xmlns="urn:logix" ')
        self.assertEqual(summary(coherent), summary())

    def test_duplicate_representations_shapes_and_unsupported_array_content(self):
        for data, expected in (
            (DATA + DATA, 'representation_ambiguous'),
            (DATA.replace('<Structure ', '<Structure xmlns:x="urn:v" x:Private="x" '), 'shape_unsupported'),
            (DATA.replace('<Data Format=', '<Data xmlns="urn:v" Format='), 'representation_unsupported'),
            (DATA.replace('Dimensions="8"', 'Dimensions="8,1"'), 'data_array_unsupported'),
            (DATA.replace('Dimensions="8"', 'Dimensions="0"'), 'data_array_unsupported'),
            (DATA.replace('Index="[3]"', 'Index="[8]"'), 'data_array_unsupported'),
            (DATA.replace('Index="[3]"', 'Index="[٣]"'), 'data_array_unsupported'),
            (DATA.replace('Value="0"/>', '><Structure DataType="Nested"/></Element>'), 'data_array_unsupported'),
        ):
            with self.subTest(expected=expected, data=data):
                self.assertEqual(dispositions(source(data=data))[expected], 1)

    def test_parent_lookup_is_controller_scoped_and_unrelated_tags_do_not_win(self):
        xml = source().replace('</RSLogix5000Content>',
            '<Controller Name="Other"><Modules><Module Name="Remote"/></Modules></Controller></RSLogix5000Content>')
        self.assertEqual(summary(xml), summary())
        xml = source(input_tag='').replace('<Module Name="Local"', '<Module Name="Local"')
        xml = xml.replace('<Tags>', f'<Tags><Tag Name="Remote:I">{DATA}</Tag>', 1)
        self.assertEqual(dispositions(xml)['backing_tag_missing'], 1)

    def test_parent_identity_rejects_unicode_case_collisions_at_each_topology_level(self):
        xml = source().replace('Remote', 'KRemote')
        self.assertEqual(dispositions(xml)['slot_shape_observed_mapping_unchecked'], 1)
        changed = xml.replace('Name="RackCard" ParentModule="KRemote"',
                              'Name="RackCard" ParentModule="KRemote"')
        self.assertEqual(dispositions(changed)['source_unqualified'], 2)
        ancestor = source().replace('Bridge', 'KBridge')
        changed = ancestor.replace('Name="Remote" ParentModule="KBridge"',
                                   'Name="Remote" ParentModule="KBridge"')
        self.assertEqual(dispositions(changed)['source_unqualified'], 2)

    def test_duplicate_connection_context_remains_ambiguous_with_explicit_tag_name(self):
        xml = source(input_tag=f'<InputTag Name="Remote:I">{DATA}</InputTag>')
        changed = xml.replace('<Connection Name="AdapterData">', '<Connection Name="AdapterData"/><Connection Name="AdapterData">')
        self.assertEqual(dispositions(changed)['backing_tag_ambiguous'], 2)

    def test_replay_rejects_tampered_private_models_with_fixed_error(self):
        parts = capture()
        altered_inventory = replace(parts[1], entities=[replace(e, attributes=e.attributes | {'Private': 'SECRET'})
                                                       if e.kind == 'module' else e for e in parts[1].entities])
        altered_references = deepcopy(parts[2])
        altered_references.rack_candidates['candidates'][0]['name'] = 'SECRET'
        altered_data = deepcopy(parts[3])
        altered_data.elements[-1]['attributes']['Value'] = 'SECRET'
        for index, changed in ((1, altered_inventory), (2, altered_references), (3, altered_data)):
            values = list(parts)
            values[index] = changed
            with self.subTest(index=index), self.assertRaises(RackBackingSummaryError) as error:
                build_rack_backing_summary(*values)
            self.assertNotIn('SECRET', str(error.exception))

    def test_closed_keys_types_revision_partitions_and_feasible_invariants(self):
        changes = (
            lambda r: r.update(secret='PRIVATE'), lambda r: r.update(schema_version=True),
            lambda r: r.update(backing_mapping='resolved'), lambda r: r.update(status='complete'),
            lambda r: r['coverage'].update(secret=1),
            lambda r: r['coverage']['adapter_families'].update(PRIVATE=1),
            lambda r: r['coverage'].update(rack_connections=True),
            lambda r: r['coverage'].update(rack_connections=-1),
            lambda r: r['coverage'].update(rack_connections=500001),
            lambda r: r['coverage'].update(rack_connections=0),
            lambda r: r['coverage'].update(rack_declarations=3),
            lambda r: r['tool_revision'].update(commit='PRIVATE'),
            lambda r: r['tool_revision'].update(worktree=True),
            lambda r: r['coverage']['adapter_families'].update(rockwell_1794_acn15=0, unavailable_context=2),
            lambda r: r['coverage']['candidate_names'].update(available=0, unavailable=2),
            lambda r: r['coverage']['observed_shape_by_family'].update(rockwell_1794_acn15=0),
            lambda r: r['coverage']['observed_shape_by_family'].update(rockwell_1794_acn15=0, unavailable_context=1),
            lambda r: r['coverage']['observed_shape_by_family'].update(rockwell_1794_acn15=0, other=1),
        )
        for change in changes:
            value = summary()
            change(value)
            with self.subTest(change=change), self.assertRaises(RackBackingSummaryError):
                render_rack_backing_summary(value)
        self.assertRaises(RackBackingSummaryError, validate_rack_backing_summary, [])

    def test_worst_width_and_exact_serialized_budget(self):
        result = summary()
        c = result['coverage']
        c['rack_connections'] = c['rack_declarations'] = 180000
        c['declarations_by_direction'] = {'input': 90000, 'output': 90000}
        c['candidate_names'] = {'available': 150000, 'unavailable': 30000}
        c['adapter_families'] = {'rockwell_1794_acn15': 50000, 'other': 50000,
                                'missing_identity': 40000, 'unavailable_context': 40000}
        c['candidate_dispositions'] = dict.fromkeys(sorted(DISPOSITIONS), 10000)
        c['observed_shape_by_family'] = {'rockwell_1794_acn15': 4000, 'other': 3000,
                                       'missing_identity': 3000, 'unavailable_context': 0}
        result['tool_revision'] = {'commit': 'f' * 40, 'worktree': 'modified'}
        rendered = render_rack_backing_summary(result)
        self.assertLess(len(rendered.encode()), MAX_REPORT_BYTES)
        # Even independently widening all fixed count slots fits the cap.
        width = deepcopy(result)
        for key, value in width['coverage'].items():
            width['coverage'][key] = dict.fromkeys(value, 500000) if type(value) is dict else 500000
        self.assertLess(len(json.dumps(width, sort_keys=True, separators=(',', ':')).encode()) + 1, MAX_REPORT_BYTES)
        with patch.object(module, 'MAX_REPORT_BYTES', len(rendered.encode())):
            self.assertEqual(render_rack_backing_summary(result), rendered)
        with patch.object(module, 'MAX_REPORT_BYTES', len(rendered.encode()) - 1):
            self.assertRaises(RackBackingSummaryError, render_rack_backing_summary, result)

    def test_shared_adapter_shapes_are_not_expanded_per_candidate(self):
        xml = source()
        start = xml.index('<Module Name="RackCard"')
        end = xml.index('</Module>', start) + len('</Module>')
        card = xml[start:end]
        xml = xml[:start] + ''.join(card.replace('Name="RackCard"', f'Name="Card{i}"')
                                   for i in range(200)) + xml[end:]
        result = summary(xml)
        self.assertEqual(result['coverage']['rack_connections'], 200)
        self.assertEqual(result['coverage']['rack_declarations'], 400)
        self.assertEqual(result['coverage']['candidate_dispositions']['slot_shape_observed_mapping_unchecked'], 200)


class RackBackingSummaryV2Tests(unittest.TestCase):
    def test_default_schema_and_canonical_history_are_frozen(self):
        default = summary()
        self.assertEqual(default['schema_version'], 1)
        self.assertEqual(hashlib.sha256(render_rack_backing_summary(default).encode()).hexdigest(),
                         '6436eacfff5b0ac47666effaee2c2524025590b662742bc274d3de92a66b9bb9')
        self.assertEqual(default, build_rack_backing_summary(*capture(), schema_version=1))
        for version in (True, False, 0, 3, '2', 2.0):
            with self.subTest(version=version), self.assertRaises(RackBackingSummaryError):
                build_rack_backing_summary(*capture(), schema_version=version)

    def test_slot_layout_has_direction_product_and_header_joints(self):
        xml = source(data=slot_data(), catalog='1756-CNB').replace('<OutputTag/>', f'<OutputTag>{slot_data("O")}</OutputTag>')
        parts = capture(xml)
        before = [part.to_dict() for part in parts[1:]]
        result = build_rack_backing_summary(*parts, schema_version=2)
        c = result['coverage']
        observed = 'slot_array_shape_observed_mapping_unchecked'
        self.assertEqual(c['candidate_dispositions'][observed], 2)
        self.assertEqual(c['dispositions_by_direction']['input'][observed], 1)
        self.assertEqual(c['dispositions_by_direction']['output'][observed], 1)
        self.assertEqual(c['adapter_families']['rockwell_1756_cnb'], 2)
        self.assertEqual(c['observed_shape_by_layout_family']['slot_array']['rockwell_1756_cnb'], 2)
        self.assertEqual(c['observed_shape_by_header_consistency']['series_direction_consistent'], 2)
        self.assertEqual(c['root_type_families']['ab_1756'], 2)
        self.assertEqual(c['slot_header_field_shapes']['qualified_header_fields_present'], 2)
        self.assertEqual(c['top_level_members'], {'data': 0, 'fault': 0, 'other': 0, 'slot': 2, 'slot_status_bits': 1})
        self.assertEqual(c['representation_census']['input']['single_decorated'], 1)
        self.assertEqual(result['backing_mapping'], 'not_analyzed')
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(before, [part.to_dict() for part in parts[1:]])

    def test_exact_known_products_and_vendor_override_guard(self):
        expected = {'1756-ENET', '1756-ENBT', '1756-EN2T', '1756-EN2F', '1756-EN2TR', '1756-EN3TR',
                    '1756-CNB', '1756-CNBR', '1756-CN2', '1756-CN2R', '1794-ACN15', '1794-ACNR15',
                    '1794-AENT', '1794-AENTR', '1734-AENT', '1734-AENTR', '1738-AENT', '1738-AENTR'}
        self.assertEqual(set(module._CATALOG_FAMILIES), expected)
        for catalog in expected:
            with self.subTest(catalog=catalog):
                c = summary2(source(catalog=catalog))['coverage']
                product = 'rockwell_' + catalog.lower().replace('-', '_')
                self.assertEqual(c['adapter_families'][product], 2)
                self.assertEqual(c['observed_shape_by_layout_family']['data_array'][product], 1)
        for xml in (source(vendor='01'), source(vendor='2'), source(catalog='1756-enbt'),
                    source(catalog='1756-ENBT/A'), source(catalog='PRIVATE_PRODUCT'),
                    source().replace('CatalogNumber=', 'UserDefinedCatalogNumber="" CatalogNumber=')):
            with self.subTest(xml=xml):
                self.assertEqual(summary2(xml)['coverage']['adapter_families']['other'], 2)
        self.assertEqual(summary2(source(vendor=''))['coverage']['adapter_families']['missing_identity'], 2)

    def test_representation_census_never_merges_or_chooses_effective_values(self):
        l5k, raw = '<Data Format="L5K">[PRIVATE_VALUE]</Data>', '<Data Format="Raw">PRIVATE_BYTES</Data>'
        for data, census, disposition in (
            ('', 'missing', 'representation_missing'),
            (DATA, 'single_decorated', 'data_array_shape_observed_mapping_unchecked'),
            (DATA + l5k, 'decorated_with_l5k', 'data_array_shape_observed_mapping_unchecked'),
            (DATA + l5k + raw, 'decorated_with_other', 'data_array_shape_observed_mapping_unchecked'),
            (DATA + DATA, 'multiple_decorated', 'representation_ambiguous'),
            (l5k, 'l5k_only', 'representation_unsupported'),
            (raw, 'other_only', 'representation_unsupported'),
            (l5k + raw, 'mixed_without_decorated', 'representation_unsupported'),
        ):
            with self.subTest(census=census):
                result = summary2(source(data=data))
                self.assertEqual(result['coverage']['representation_census']['input'][census], 1)
                self.assertEqual(result['coverage']['dispositions_by_direction']['input'][disposition], 1)
                self.assertEqual(result['effective_value_selection'], 'not_implemented')
                rendered = render_rack_backing_summary(result)
                self.assertNotIn('PRIVATE_', rendered)
        self.assertEqual(summary2(source(input_tag=''))['coverage']['representation_census']['input']['unavailable_context'], 1)
        # The old definition remains ambiguous for the very same source.
        self.assertEqual(dispositions(source(data=DATA + l5k))['representation_ambiguous'], 1)

    def test_all_v2_first_gap_buckets_are_exercised(self):
        cases = {
            'source_unqualified': source().replace('<Modules>', '<Modules Protected="false">'),
            'adapter_missing': source().replace('Name="RackCard" ParentModule="Remote"', 'Name="RackCard" ParentModule="Missing"'),
            'adapter_ambiguous': source().replace('</Modules>', '<Module Name="Remote"/></Modules>'),
            'candidate_unavailable': source().replace('<RackConnection>', '<RackConnection Name="Unexpected">'),
            'backing_tag_missing': source(input_tag=''),
            'backing_tag_ambiguous': source(input_tag=f'<InputTag>{DATA}</InputTag><InputTag/>'),
            'backing_tag_unqualified': source(input_tag=f'<InputTag xmlns="urn:vendor">{DATA}</InputTag>'),
            'backing_name_unavailable': source(input_tag=f'<InputTag Name="Different:I">{DATA}</InputTag>'),
            'representation_missing': source(data=''),
            'representation_unsupported': source(data='<Data Format="L5K">[0]</Data>'),
            'representation_ambiguous': source(data=DATA + DATA),
            'shape_unsupported': source(data=DATA.replace('<Structure ', '<Structure xmlns:x="urn:v" x:Other="x" ')),
            'layout_unrecognized': source(data=DATA.replace('Name="Data"', 'Name="PrivateMember"')),
            'layout_ambiguous': source(data=DATA.replace(ARRAY, ARRAY + ARRAY.replace('Name="Data"', 'Name="Slot"'))),
            'array_unsupported': source(data=DATA.replace('Dimensions="8"', 'Dimensions="8,1"')),
            'slot_missing': source(data=DATA.replace('Index="[3]"', 'Index="[2]"')),
            'slot_ambiguous': source(data=DATA.replace('<Element Index="[3]" Value="0"/>',
                                                     '<Element Index="[3]" Value="0"/><Element Index="[03]" Value="1"/>')),
            'slot_shape_unsupported': source(data=slot_data().replace('Name="Fault"', 'Name="PrivateMember"')),
            'data_array_shape_observed_mapping_unchecked': source(),
            'slot_array_shape_observed_mapping_unchecked': source(data=slot_data()),
        }
        self.assertEqual(set(cases), module.V2_DISPOSITIONS)
        for disposition, xml in cases.items():
            with self.subTest(disposition=disposition):
                self.assertGreater(summary2(xml)['coverage']['dispositions_by_direction']['input'][disposition], 0)

    def test_scalar_data_shapes_do_not_claim_element_value_or_profile_validation(self):
        for data_type in ('BOOL', 'SINT', 'INT', 'DINT'):
            result = summary2(source(data=DATA.replace('DINT', data_type).replace('Value="0"', 'Value="PRIVATE_NOT_A_NUMBER"')))
            self.assertEqual(result['coverage']['candidate_dispositions']['data_array_shape_observed_mapping_unchecked'], 1)
            self.assertEqual(result['member_validation'], 'not_implemented')
            self.assertNotIn('PRIVATE_', render_rack_backing_summary(result))
        for data_type in ('REAL', 'PRIVATE_TYPE', 'dint', 'AB:1756_CNB_SLOT:I:0'):
            with self.subTest(data_type=data_type):
                self.assertEqual(summary2(source(data=DATA.replace('DINT', data_type)))['coverage']['candidate_dispositions']['array_unsupported'], 1)

    def test_slot_required_fields_and_native_type_agreement_fail_closed(self):
        original = slot_data()
        changes = (
            original.replace('Name="Fault"', 'Name="Other"'),
            original.replace('Name="Data" DataType="DINT"', 'Name="Data" DataType="INT"'),
            original.replace('<DataValueMember Name="Data"', '<DataValueMember Name="Data" DataType="DINT" Value="1"/><DataValueMember Name="Data"'),
            original.replace('<Structure DataType="AB:1756_CNB_SLOT:I:0">', '<Structure DataType="AB:1756_DIFFERENT:I:0">'),
            original.replace('AB:1756_CNB_SLOT:I:0', 'AB:1794_OTHER:I:0'),
            original.replace('AB:1756_CNB_SLOT:I:0', 'AB:1756_CNB_SLOT:O:0'),
            original.replace('AB:1756_CNB_17SLOT:I:0', 'PRIVATE_ROOT'),
        )
        for data in changes:
            with self.subTest(data=data):
                self.assertEqual(summary2(source(data=data))['coverage']['candidate_dispositions']['slot_shape_unsupported'], 1)
        data = original.replace('Name="Slot"', 'Name="Slot" xmlns="urn:vendor"')
        self.assertEqual(summary2(source(data=data))['coverage']['candidate_dispositions']['shape_unsupported'], 1)
        # A mixed-namespace sibling spelling is rejected even before capture.
        with self.assertRaises(SourceError):
            summary2(source(data=original.replace('Name="Data"', 'Name="Data" xmlns="urn:vendor"')))

    def test_header_consistency_is_series_and_direction_only(self):
        for type_name, catalog, expected in (
            ('PRIVATE_TYPE', '1756-CNB', 'unrecognized_type'),
            ('AB:1756_CNB_17SLOT:I:0', 'PRIVATE_PRODUCT', 'identity_unavailable'),
            ('AB:1756_CNB_17SLOT:O:0', '1756-CNB', 'direction_mismatch'),
            ('AB:1794_INVENTED:I:0', '1756-CNB', 'series_mismatch'),
            ('AB:1756_INVENTED:I:0', '1756-ENBT', 'series_direction_consistent'),
        ):
            with self.subTest(expected=expected):
                result = summary2(source(data=DATA.replace('InventedRack', type_name), catalog=catalog))
                self.assertEqual(result['coverage']['root_header_consistency'][expected], 1)
                self.assertEqual(result['coverage']['observed_shape_by_header_consistency'][expected], 1)
                self.assertEqual(result['header_comparison'], 'catalog_series_and_direction_only')
                self.assertNotIn('PRIVATE_', render_rack_backing_summary(result))

    def test_unknown_slot_child_headers_retain_field_evidence_without_native_promotion(self):
        for child_type in ('AB:1756_ENBT_DI:0', 'PRIVATE_UNKNOWN_CHILD', ''):
            with self.subTest(child_type=child_type):
                data = slot_data().replace('AB:1756_CNB_SLOT:I:0', child_type)
                result = summary2(source(data=data, catalog='1756-ENBT'))
                c = result['coverage']
                self.assertEqual(c['candidate_dispositions']['array_unsupported'], 1)
                self.assertEqual(c['candidate_dispositions']['slot_array_shape_observed_mapping_unchecked'], 0)
                self.assertEqual(c['slot_header_field_shapes']['unrecognized_header_fields_present'], 1)
                self.assertEqual(c['slot_header_field_shapes']['not_examined'], 1)
                self.assertEqual(result['backing_mapping'], 'not_analyzed')
                if child_type:
                    self.assertNotIn(child_type, render_rack_backing_summary(result))
        for data in (
            slot_data().replace('AB:1756_CNB_17SLOT:I:0', 'PRIVATE_UNKNOWN_ROOT'),
            slot_data().replace('<Structure DataType="AB:1756_CNB_SLOT:I:0">', '<Structure DataType="PRIVATE_UNKNOWN_ELEMENT">'),
        ):
            result = summary2(source(data=data))
            self.assertEqual(result['coverage']['candidate_dispositions']['slot_shape_unsupported'], 1)
            self.assertEqual(result['coverage']['slot_header_field_shapes']['unrecognized_header_fields_present'], 1)

    def test_slot_field_joint_map_covers_structural_failures_and_type_disagreement(self):
        original = slot_data()
        start, end = original.index('<Element '), original.index('</Element>') + len('</Element>')
        cases = {
            'not_examined': original.replace('Dimensions="17"', 'Dimensions="17,1"'),
            'slot_missing_or_ambiguous': original.replace('Index="[3]"', 'Index="[2]"'),
            'structure_unqualified': original[:start] + '<Element Index="[3]" Value="0"/>' + original[end:],
            'fields_unqualified': original.replace('Name="Fault"', 'Name="UnknownField"'),
            'qualified_header_fields_present': original,
            'unrecognized_header_fields_present': original.replace('AB:1756_CNB_SLOT:I:0', 'UNKNOWN'),
            'mismatched_header_fields_present': original.replace('AB:1756_CNB_SLOT:I:0', 'AB:1794_INVENTED:I:0'),
        }
        self.assertEqual(set(cases), module.V2_SLOT_HEADER_FIELDS)
        for expected, data in cases.items():
            with self.subTest(expected=expected):
                counts = summary2(source(data=data))['coverage']['slot_header_field_shapes']
                self.assertEqual(counts[expected], 2 if expected == 'not_examined' else 1)
                self.assertEqual(sum(counts.values()), 2)
        # Unknown header spelling neither conceals bad fields nor prevents
        # missing/duplicate selected-slot observations in a qualified array.
        unknown = original.replace('AB:1756_CNB_SLOT:I:0', 'UNKNOWN')
        end = unknown.index('</Element>') + len('</Element>')
        duplicate = unknown[:end] + '<Element Index="[03]" Value="0"/>' + unknown[end:]
        for data, expected in ((unknown.replace('Name="Fault"', 'Name="Other"'), 'fields_unqualified'),
                               (unknown.replace('[3]', '[2]'), 'slot_missing_or_ambiguous'),
                               (duplicate, 'slot_missing_or_ambiguous')):
            result = summary2(source(data=data))
            self.assertEqual(result['coverage']['candidate_dispositions']['array_unsupported'], 1)
            self.assertEqual(result['coverage']['slot_header_field_shapes'][expected], 1)

    def test_slot_field_diagnostics_do_not_bypass_source_or_representation_qualification(self):
        data = slot_data().replace('AB:1756_CNB_SLOT:I:0', 'PRIVATE_UNKNOWN_CHILD')
        for xml in (
            source(data=data).replace('<Modules>', '<Modules Protected="false">'),
            source(data=data + data),
            source(data=data.replace('<Data Format=', '<Data xmlns="urn:foreign" Format=')),
            source(data=data.replace('Name="Slot"', 'Name="Slot" xmlns="urn:foreign"')),
        ):
            with self.subTest(xml=xml):
                c = summary2(xml)['coverage']
                self.assertEqual(c['slot_header_field_shapes']['not_examined'], 2)
                self.assertEqual(sum(c['slot_header_field_shapes'].values()), 2)

    def test_slot_field_map_rejects_open_keys_and_impossible_native_claims(self):
        for change in (
            lambda c: c['slot_header_field_shapes'].update(PRIVATE=0),
            lambda c: c['slot_header_field_shapes'].update(not_examined=True),
            lambda c: c['slot_header_field_shapes'].update(not_examined=1, qualified_header_fields_present=1),
            lambda c: c['slot_header_field_shapes'].update(not_examined=1, mismatched_header_fields_present=1),
            lambda c: c['slot_header_field_shapes'].update(not_examined=1, unrecognized_header_fields_present=1),
        ):
            result = summary2()
            change(result['coverage'])
            with self.subTest(change=change), self.assertRaises(RackBackingSummaryError):
                render_rack_backing_summary(result)
        result = summary2(source(data=slot_data()))
        result['coverage']['slot_header_field_shapes'].update(qualified_header_fields_present=0, fields_unqualified=1)
        self.assertRaises(RackBackingSummaryError, render_rack_backing_summary, result)

    def test_qualified_context_stays_controller_scoped_protected_and_ascii(self):
        baseline = source(data=slot_data(), catalog='1756-CNB')
        for xml in (
            baseline.replace('<Controller Name=', '<Controller Protected="false" Name='),
            baseline.replace('<Modules>', '<Modules Protected="true">'),
            baseline.replace('<Port ', '<Port xmlns="urn:other" '),
            baseline.replace('Remote', 'KRemote').replace('Name="RackCard" ParentModule="KRemote"', 'Name="RackCard" ParentModule="KRemote"'),
        ):
            self.assertEqual(summary2(xml)['coverage']['candidate_dispositions']['source_unqualified'], 2)
        coherent = baseline.replace('<RSLogix5000Content ', '<RSLogix5000Content xmlns="urn:logix" ')
        self.assertEqual(summary2(coherent), summary2(baseline))
        unrelated = baseline.replace('</RSLogix5000Content>', '<Controller Name="Other"><Modules><Module Name="Remote"/></Modules></Controller></RSLogix5000Content>')
        self.assertEqual(summary2(unrelated), summary2(baseline))

    def test_invalid_indexes_and_duplicate_headers_do_not_merge(self):
        for old, new, expected in (
            ('Index="[3]"', 'Index="[17]"', 'array_unsupported'),
            ('Index="[3]"', 'Index="[٣]"', 'array_unsupported'),
            ('Dimensions="17"', 'Dimensions="0000017"', 'array_unsupported'),
            ('Dimensions="17"', 'Dimensions="0"', 'array_unsupported'),
        ):
            self.assertEqual(summary2(source(data=slot_data().replace(old, new)))['coverage']['candidate_dispositions'][expected], 1)
        data = slot_data()
        start, end = data.index('<Element '), data.index('</Element>') + len('</Element>')
        duplicate = data[:end] + data[start:end].replace('[3]', '[03]') + data[end:]
        self.assertEqual(summary2(source(data=duplicate))['coverage']['candidate_dispositions']['slot_ambiguous'], 1)

    def test_v2_public_forgery_and_cross_partition_checks(self):
        changes = (
            lambda r: r.update(secret='PRIVATE'), lambda r: r.update(schema_version=True),
            lambda r: r.update(header_comparison='effective_configuration'),
            lambda r: r['coverage'].update(header_contexts=True),
            lambda r: r['coverage'].update(header_contexts=0),
            lambda r: r['coverage']['root_type_families'].update(PRIVATE=0),
            lambda r: r['coverage']['dispositions_by_direction']['output'].update(representation_missing=0),
            lambda r: r['coverage']['representation_census']['input'].update(single_decorated=0, missing=1),
            lambda r: r['coverage']['root_header_consistency'].update(unrecognized_type=0, series_direction_consistent=1),
            lambda r: r['coverage']['observed_shape_by_header_consistency'].update(unrecognized_type=0, identity_unavailable=1),
            lambda r: r['coverage']['observed_shape_by_layout_family']['data_array'].update(rockwell_1794_acn15=0, other=1),
            lambda r: r['coverage']['top_level_members'].update(data=0),
            lambda r: r['coverage']['adapter_families'].update(rockwell_1794_acn15=-1),
            lambda r: r['tool_revision'].update(commit='PRIVATE'),
        )
        for change in changes:
            value = summary2()
            change(value)
            with self.subTest(change=change), self.assertRaises(RackBackingSummaryError):
                render_rack_backing_summary(value)

    def test_v2_private_replay_rejects_tampering(self):
        parts = capture(source(data=slot_data()))
        for index in (1, 2, 3):
            values = deepcopy(list(parts))
            if index == 1:
                values[1] = replace(values[1], entities=[replace(e, attributes=e.attributes | {'Private': 'SECRET'})
                                                       if e.kind == 'module' else e for e in values[1].entities])
            elif index == 2:
                values[2].rack_candidates['candidates'][0]['name'] = 'SECRET'
            else:
                values[3].elements[-1]['attributes']['Value'] = 'SECRET'
            with self.subTest(index=index), self.assertRaises(RackBackingSummaryError) as error:
                build_rack_backing_summary(*values, schema_version=2)
            self.assertNotIn('SECRET', str(error.exception))

    def test_native_slot_and_known_identity_feasibility_cannot_be_forged(self):
        unknown = summary2(source(catalog='PRIVATE_PRODUCT'))
        c = unknown['coverage']
        c['root_type_families'].update(other=0, ab_1756=1)
        for key in ('root_header_consistency', 'observed_shape_by_header_consistency'):
            c[key].update(unrecognized_type=0, series_direction_consistent=1)
        self.assertRaises(RackBackingSummaryError, render_rack_backing_summary, unknown)
        # Shape partitions alone must not turn an arbitrary structure into a
        # native Slot header proof, even with otherwise conserved counts.
        value = summary2()
        c = value['coverage']
        old, new = 'data_array_shape_observed_mapping_unchecked', 'slot_array_shape_observed_mapping_unchecked'
        c['candidate_dispositions'].update({old: 0, new: 1})
        c['dispositions_by_direction']['input'].update({old: 0, new: 1})
        c['observed_shape_by_layout_family']['data_array']['rockwell_1794_acn15'] = 0
        c['observed_shape_by_layout_family']['slot_array']['rockwell_1794_acn15'] = 1
        c['top_level_members'].update(data=0, slot=1)
        self.assertRaises(RackBackingSummaryError, render_rack_backing_summary, value)
        for root_series, actual, forged in (
            ('1756', 'series_mismatch', 'series_direction_consistent'),
            ('1794', 'series_direction_consistent', 'series_mismatch'),
        ):
            value = summary2(source(data=DATA.replace('InventedRack', f'AB:{root_series}_INVENTED:I:0')))
            for key in ('root_header_consistency', 'observed_shape_by_header_consistency'):
                value['coverage'][key].update({actual: 0, forged: 1})
            with self.subTest(root_series=root_series), self.assertRaises(RackBackingSummaryError):
                render_rack_backing_summary(value)

    def test_absent_rack_and_empty_connections_have_distinct_status(self):
        no_rack = source().replace('<RackConnection>', '<Connection>').replace('</RackConnection>', '</Connection>')
        self.assertEqual(summary2(no_rack)['status'], 'complete')
        empty = summary2(source().replace('<InAliasTag/>', '').replace('<OutAliasTag/>', ''))
        self.assertEqual(empty['status'], 'partial')
        self.assertEqual(empty['coverage']['rack_declarations'], 0)

    def test_v2_maximum_width_and_exact_render_limit(self):
        value = summary2()
        def scale(item):
            return {key: scale(number) for key, number in item.items()} if type(item) is dict else item * 100000
        value['coverage'] = scale(value['coverage'])
        value['tool_revision'] = {'commit': 'f' * 40, 'worktree': 'modified'}
        rendered = render_rack_backing_summary(value)
        def widen(item):
            return {key: widen(number) for key, number in item.items()} if type(item) is dict else module.MAX_COUNT
        widest = deepcopy(value)
        widest['coverage'] = widen(widest['coverage'])
        width = len(json.dumps(widest, sort_keys=True, separators=(',', ':')).encode()) + 1
        self.assertLessEqual(width, module.MAX_REPORT_BYTES_V2)
        self.assertEqual(width, 6773)
        with patch.object(module, 'MAX_REPORT_BYTES_V2', len(rendered.encode())):
            self.assertEqual(render_rack_backing_summary(value), rendered)
        with patch.object(module, 'MAX_REPORT_BYTES_V2', len(rendered.encode()) - 1):
            self.assertRaises(RackBackingSummaryError, render_rack_backing_summary, value)

    def test_v2_shared_source_shapes_and_alternative_formats_do_not_expand(self):
        xml = source(data=slot_data() + '<Data Format="L5K">[0]</Data>', catalog='1756-CNB')
        start = xml.index('<Module Name="RackCard"')
        end = xml.index('</Module>', start) + len('</Module>')
        card = xml[start:end]
        xml = xml[:start] + ''.join(card.replace('Name="RackCard"', f'Name="Card{i}"') for i in range(200)) + xml[end:]
        c = summary2(xml)['coverage']
        self.assertEqual(c['rack_connections'], 200)
        self.assertEqual(c['rack_declarations'], 400)
        self.assertEqual(c['candidate_dispositions']['slot_array_shape_observed_mapping_unchecked'], 200)
        self.assertEqual(c['representation_census']['input']['decorated_with_l5k'], 200)
        self.assertEqual(c['slot_header_field_shapes']['qualified_header_fields_present'], 200)
        self.assertEqual(c['slot_header_field_shapes']['not_examined'], 200)


if __name__ == '__main__':
    unittest.main()
