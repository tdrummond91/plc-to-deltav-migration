"""Invented stored-data evidence tests; no live values or schema inference."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.tag_data import (
    ELEMENT_KINDS, TagDataError, analyze_tag_data, render_tag_data_json, validate_tag_data,
)
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def source(body: str = '', namespace: str = ''):
    xml = (f'<RSLogix5000Content{namespace}><Controller Name="Invented">{body}'
           '</Controller></RSLogix5000Content>')
    snapshot = snapshot_from_bytes(xml.encode())
    return snapshot, analyze_snapshot(snapshot)


def capture(body: str = '', namespace: str = ''):
    snapshot, inventory = source(body, namespace)
    return snapshot, inventory, analyze_tag_data(snapshot, inventory)


def tags(data: str, name: str = 'SecretTag') -> str:
    return f'<Tags><Tag Name="{name}" TagType="Base" DataType="Unknown">{data}</Tag></Tags>'


SCALAR = '<Data Format="Decorated"><DataValue DataType="DINT" Value="0009"/></Data>'
SHAPES = '''<Data Format="Decorated"><Structure DataType="InventedType">
 <DataValueMember Name="Scalar" DataType="REAL" Value="-1.00e+2"/>
 <StructureMember Name="Nested"><DataValueMember Name="Empty" Value=""/></StructureMember>
 <ArrayMember Name="Members"><Element Index="[00]" Value="16#FFFF"/>
  <Element Index="[1]"><Structure><DataValueMember Name="Value" Value="false"/></Structure></Element>
  <Element Index="[2]"><Array><Element Index="[0]" Value="-0"/></Array></Element>
 </ArrayMember></Structure></Data>'''


class TagDataTests(unittest.TestCase):
    def test_empty_and_missing_data_are_complete_observations(self) -> None:
        for body, owners in (('', 0), (tags(''), 1)):
            with self.subTest(body=body):
                snapshot, inventory, result = capture(body)
                self.assertEqual(result.status, 'complete')
                self.assertEqual(result.coverage['owners_without_data'], owners)
                self.assertEqual(result.coverage['contents_total'], 0)
                self.assertEqual(result.issues, [])
                validate_tag_data(snapshot, inventory, result)
        self.assertEqual(capture(tags(''))[2].owners[0]['content_ids'], [])

    def test_all_decorated_shapes_preserve_lexical_values_and_parent_links(self) -> None:
        snapshot, inventory, result = capture(tags(SHAPES + SCALAR))
        self.assertEqual(result.status, 'partial')  # Same-format envelopes remain ambiguous.
        self.assertEqual(set(row['kind'] for row in result.elements), ELEMENT_KINDS - {'opaque', 'unmodeled'})
        self.assertEqual(result.coverage['duplicate_groups']['content'], 1)
        self.assertEqual({row['attributes'].get('Value') for row in result.elements
                          if 'Value' in row['attributes']}, {'-1.00e+2', '', '16#FFFF', 'false', '-0', '0009'})
        by_id = {row['id']: row for row in result.elements}
        content_ids = {row['id'] for row in result.contents}
        for row in result.elements:
            self.assertNotIn('locator', row)
            self.assertNotIn('children', row)
            self.assertEqual(row['owner_id'], result.owners[0]['source_id'])
            self.assertIn(row['content_id'], content_ids)
            self.assertTrue(row['parent_id'] in by_id or row['parent_id'] in content_ids)
        validate_tag_data(snapshot, inventory, result)
        with self.assertRaises(FrozenInstanceError):
            result.status = 'complete'

    def test_parsed_text_and_all_formats_are_retained_without_winner(self) -> None:
        text = '"private" & <unparsed> $00'
        body = tags('<Data Format="String"><![CDATA[' + text + ']]></Data>'
                    '<Data Format="L5K">[001, 16#FF]<Vendor Text="unchanged"/></Data>'
                    '<Data Format="Raw"><Byte Value="01"/></Data>'
                    '<Data><Opaque/></Data><DefaultData Format="Vendor">opaque</DefaultData>')
        _, _, result = capture(body)
        self.assertEqual(len(result.contents), 5)
        self.assertEqual(result.contents[0]['direct_text'], text)
        self.assertEqual([row['format_kind'] for row in result.contents],
                         ['string', 'l5k', 'raw', 'missing', 'other'])
        self.assertEqual(result.coverage['issues_by_code']['format_unsupported'], 4)
        self.assertTrue(all(row['kind'] == 'opaque' for row in result.elements))
        self.assertEqual(result.coverage['duplicate_records']['content'], 0)
        self.assertEqual(result.owners[0]['content_ids'], [row['id'] for row in result.contents])
        self.assertNotIn('effective_value', result.to_dict())

    def test_all_owner_kinds_match_canonical_entities_including_unnamed(self) -> None:
        body = tags(SCALAR) + '''<Programs><Program Name="P"><Tags><Tag Name="SecretTag"
          TagType="Alias" AliasFor="Other"><DefaultData Format="String">local</DefaultData></Tag>
          </Tags></Program></Programs><AddOnInstructionDefinitions><AddOnInstructionDefinition Name="A">
          <Parameters><Parameter Name="Param"><DefaultData Format="Decorated"><DataValue Value="7"/>
          </DefaultData></Parameter><Parameter/></Parameters><LocalTags><LocalTag Name="Local">
          <DefaultData Format="String">authored</DefaultData></LocalTag></LocalTags>
          </AddOnInstructionDefinition></AddOnInstructionDefinitions><Modules><Module Name="M">
          <Communications><ConfigTag><Data Format="String">config</Data></ConfigTag><Connections>
          <Connection Name="C"><InputTag><Data Format="String">input</Data></InputTag>
          <OutputTag/></Connection></Connections></Communications></Module></Modules>'''
        _, inventory, result = capture(body)
        self.assertEqual(result.coverage['owners_by_kind'], {
            'tag': 2, 'aoi_parameter': 2, 'aoi_local_tag': 1,
            'module_input_tag': 1, 'module_output_tag': 1, 'module_config_tag': 1,
        })
        self.assertEqual(result.coverage['owners_without_data'], 2)
        expected = {e.id for e in inventory.entities if e.kind in result.coverage['owners_by_kind']}
        self.assertEqual({row['source_id'] for row in result.owners}, expected)
        self.assertEqual(len(set(row['owner_id'] for row in result.contents)), 6)

    def test_exact_context_excludes_vendor_owners_and_indirect_envelopes(self) -> None:
        body = tags('<Vendor>' + SCALAR + '</Vendor><Data Format="Decorated"><Vendor>'
                    '<Structure><DataValueMember Name="A" Value="1"/></Structure></Vendor></Data>')
        body += '<Vendor><Tags><Tag Name="Hidden">' + SCALAR + '</Tag></Tags></Vendor>'
        _, _, result = capture(body)
        self.assertEqual(result.coverage['owners_total'], 1)
        self.assertEqual(result.coverage['contents_total'], 1)
        self.assertEqual([row['kind'] for row in result.elements], ['unmodeled'] * 3)
        self.assertEqual(result.coverage['issues_by_code']['shape_unmodeled'], 3)

    def test_invalid_shapes_do_not_promote_descendants(self) -> None:
        cases = [
            '<DataValue/>', '<DataValue Value="1"><Structure/></DataValue>',
            '<DataValueMember Name="WrongParent" Value="1"/>',
            '<Structure><DataValueMember Value="1"/></Structure>',
            '<Structure><StructureMember Name=""><DataValueMember Name="X" Value="1"/></StructureMember></Structure>',
            '<Array><Element Value="1"/></Array>',
            '<Array><Element Index="" Value="1"/></Array>',
            '<Array><Element Index="[0]"/></Array>',
            '<Array><Element Index="[0]" Value="1"><Structure/></Element></Array>',
            '<Array><Element Index="[0]"><Structure/><Array/></Element></Array>',
            '<Array><Element Index="[0]"><Structure/><Structure/></Element></Array>',
        ]
        for fragment in cases:
            with self.subTest(fragment=fragment):
                _, _, result = capture(tags(f'<Data Format="Decorated">{fragment}</Data>'))
                self.assertEqual(result.status, 'partial')
                self.assertGreater(result.coverage['elements_by_kind']['unmodeled'], 0)
                by_id = {row['id']: row for row in result.elements}
                for row in result.elements:
                    parent = by_id.get(row['parent_id'])
                    if parent and parent['kind'] == 'unmodeled':
                        self.assertEqual(row['kind'], 'unmodeled')

    def test_empty_and_mixed_text_have_specific_issues(self) -> None:
        _, _, result = capture(tags('<Data Format="Decorated"/><Data Format="String"/>'))
        self.assertEqual(result.coverage['issues_by_code']['content_empty'], 1)
        self.assertEqual(result.coverage['contents_with_text'], 0)
        _, _, result = capture(tags('<Data Format="Decorated">before<Structure>inside'
                                   '<DataValueMember Name="A" Value="1"/>after</Structure>end</Data>'))
        self.assertEqual(result.contents[0]['direct_text'], 'beforeend')
        self.assertEqual(result.elements[0]['direct_text'], 'insideafter')
        self.assertEqual(result.coverage['issues_by_code']['unexpected_direct_text'], 2)
        _, _, result = capture(tags('<Data Format="String"><DataValue Value="1"/></Data>'))
        self.assertEqual(result.elements[0]['kind'], 'unmodeled')

    def test_duplicate_observations_are_separate_and_spelling_sensitive(self) -> None:
        data = ('<Data Format="Decorated"><Structure>'
                '<DataValueMember Name="A" Value="1"/><DataValueMember Name="A" Value="2"/>'
                '<DataValueMember Name="a" Value="3"/><ArrayMember Name="Items">'
                '<Element Index="[0]" Value="1"/><Element Index="[0]" Value="2"/>'
                '<Element Index="[00]" Value="3"/></ArrayMember></Structure>'
                '<DataValue Value="4"/></Data>')
        _, _, result = capture(tags(data + SCALAR + '<DefaultData Format="Decorated"><DataValue Value="5"/></DefaultData>'))
        self.assertEqual(result.coverage['duplicate_groups'], {'content': 1, 'member': 1, 'element': 1, 'root': 1})
        self.assertEqual(result.coverage['duplicate_records'], dict.fromkeys(('content', 'member', 'element', 'root'), 2))
        self.assertEqual(len(result.contents), 3)
        self.assertEqual(len(set(row['id'] for row in result.elements)), len(result.elements))

    def test_coherent_root_namespace_is_supported_and_foreign_shapes_are_not(self) -> None:
        _, _, coherent = capture(tags(SCALAR), ' xmlns="urn:coherent"')
        self.assertEqual(coherent.status, 'complete')
        self.assertEqual(coherent.contents[0]['xml_namespace'], 'urn:coherent')
        _, _, foreign = capture(tags('<x:Data Format="Decorated"><DataValue Value="1"/></x:Data>'),
                                ' xmlns:x="urn:foreign"')
        self.assertEqual(foreign.contents[0]['xml_name'], 'Data')
        self.assertEqual(foreign.contents[0]['xml_namespace'], 'urn:foreign')
        self.assertEqual(foreign.elements[0]['kind'], 'opaque')
        self.assertEqual(foreign.coverage['issues_by_code']['namespace_unmodeled'], 1)
        _, _, child = capture(tags('<Data Format="Decorated"><x:Structure>'
                                  '<DataValueMember Name="A" Value="1"/></x:Structure></Data>'),
                              ' xmlns:x="urn:foreign"')
        self.assertEqual([row['kind'] for row in child.elements], ['unmodeled', 'unmodeled'])

    def test_foreign_owner_and_attributes_cannot_supply_ordinary_semantics(self) -> None:
        _, _, owner = capture('<Tags><x:Tag Name="A">' + SCALAR + '</x:Tag></Tags>',
                              ' xmlns:x="urn:foreign"')
        self.assertEqual(owner.coverage['owners_total'], 1)
        self.assertEqual(owner.elements[0]['kind'], 'opaque')
        _, _, attrs = capture(tags('<Data Format="Decorated"><DataValue x:Value="1"/></Data>'),
                              ' xmlns:x="urn:foreign"')
        self.assertEqual(attrs.elements[0]['attributes'], {'urn:foreign}Value': '1'})
        self.assertEqual(attrs.elements[0]['kind'], 'unmodeled')
        _, _, format_attr = capture(tags('<Data x:Format="Decorated"><DataValue Value="1"/></Data>'),
                                    ' xmlns:x="urn:foreign"')
        self.assertEqual(format_attr.contents[0]['format_kind'], 'missing')
        self.assertEqual(format_attr.elements[0]['kind'], 'opaque')

    def test_ids_are_snapshot_bound_and_locations_are_reconstructable(self) -> None:
        snapshot, inventory, result = capture(tags(SHAPES))
        before = inventory.to_dict()
        self.assertEqual(result.to_dict(), analyze_tag_data(snapshot, inventory).to_dict())
        by_id = {row['id']: row for row in result.elements}
        content_locations = {row['id']: row['locator'] for row in result.contents}
        for row in result.elements:
            location, current = '', row
            while current:
                location = f"/{current['xml_name']}[{current['ordinal']}]" + location
                parent = current['parent_id']
                if parent in content_locations:
                    location = content_locations[parent] + location
                    break
                current = by_id[parent]
            self.assertIn('/Data[1]/Structure[1]', location)
        self.assertEqual(inventory.to_dict(), before)
        changed = capture(tags(SHAPES, 'Different'))[2]
        self.assertFalse({r['id'] for r in result.elements} & {r['id'] for r in changed.elements})
        self.assertEqual(json.loads(render_tag_data_json(result)), result.to_dict())

    def test_inventory_snapshot_and_result_forgeries_are_source_free(self) -> None:
        snapshot, inventory, result = capture(tags(SCALAR))
        inventory_changes = [replace(inventory, status='partial'), deepcopy(inventory), deepcopy(inventory)]
        inventory_changes[1].counts['controller_tags'] = True
        inventory_changes[2].entities.append(inventory_changes[2].entities[0])
        for forged in inventory_changes:
            with self.subTest(forged='inventory'), self.assertRaisesRegex(TagDataError, '^Tag-data evidence is inconsistent or exceeds its limits\\.$'):
                analyze_tag_data(snapshot, forged)
        forged_snapshot = replace(snapshot, size_bytes=True)
        with self.assertRaises(TagDataError):
            analyze_tag_data(forged_snapshot, inventory)
        for mutate in (
            lambda r: r.contents[0]['attributes'].update(Format='L5K'),
            lambda r: r.elements[0].update(parent_id=r.elements[0]['id']),
            lambda r: r.coverage.update(owners_total=True),
            lambda r: r.elements[0].update(extra='source-secret'),
            lambda r: r.contents.append(r.contents),
            lambda r: r.__dict__.update(extra='source-secret'),
        ):
            forged = deepcopy(result)
            mutate(forged)
            with self.assertRaisesRegex(TagDataError, '^Tag-data evidence is inconsistent or exceeds its limits\\.$'):
                validate_tag_data(snapshot, inventory, forged)
        with self.assertRaises(TagDataError):
            validate_tag_data(snapshot, inventory, result.to_dict())

    def test_unsafe_or_malformed_xml_fails_without_source_echo(self) -> None:
        _, inventory = source()
        for xml in ('<!DOCTYPE RSLogix5000Content [<!ENTITY secret SYSTEM "file:///private-secret">]>'
                    '<RSLogix5000Content>&secret;</RSLogix5000Content>',
                    '<RSLogix5000Content><private-secret>'):
            with self.assertRaisesRegex(TagDataError, '^Tag-data evidence is inconsistent or exceeds its limits\\.$'):
                analyze_tag_data(snapshot_from_bytes(xml.encode()), inventory)

    def test_aggregate_record_and_byte_limits_fail_closed(self) -> None:
        snapshot, inventory = source(tags(SCALAR + SCALAR))
        for constant, limit in (
            ('MAX_TAG_DATA_OWNERS', 0), ('MAX_TAG_DATA_CONTENTS', 1),
            ('MAX_TAG_DATA_ELEMENTS', 1), ('MAX_TAG_DATA_ISSUES', 1),
            ('MAX_TAG_DATA_EVIDENCE_BYTES', 100), ('MAX_TAG_DATA_JSON_BYTES', 100),
        ):
            with self.subTest(constant=constant), patch(f'plc_workbench.tag_data.{constant}', limit):
                with self.assertRaises(TagDataError):
                    analyze_tag_data(snapshot, inventory)
        # Long namespaces are charged for each retained occurrence, not merely
        # once at the tiny xmlns source declaration.
        namespace = 'urn:' + 'a' * 1000
        ns_snapshot, ns_inventory = source(tags('<Data Format="Decorated"><Array>' +
                                               '<Element Index="[0]" Value="1"/>' * 10 + '</Array></Data>'),
                                          f' xmlns="{namespace}"')
        with patch('plc_workbench.tag_data.MAX_TAG_DATA_EVIDENCE_BYTES', 10_000):
            with self.assertRaises(TagDataError):
                analyze_tag_data(ns_snapshot, ns_inventory)

    def test_render_rejects_cycles_boolean_and_unknown_objects_without_copying(self) -> None:
        result = capture(tags(SCALAR))[2]
        for mutate in (lambda r: r.contents.append(r.contents),
                       lambda r: r.coverage.update(owners_total=True),
                       lambda r: r.contents[0].update(direct_text=object())):
            forged = deepcopy(result)
            mutate(forged)
            with self.assertRaises(TagDataError):
                render_tag_data_json(forged)
        with patch('plc_workbench.tag_data.MAX_TAG_DATA_JSON_BYTES', 100):
            with self.assertRaises(TagDataError):
                render_tag_data_json(result)


if __name__ == '__main__':
    unittest.main()
