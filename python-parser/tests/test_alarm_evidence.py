"""Invented alarm declaration facts remain distinct from operational alarms."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from plc_workbench.alarm_evidence import (
    ALARM_EVIDENCE_CONSTANTS, AlarmEvidenceError, analyze_alarm_evidence,
    render_alarm_evidence_json, validate_alarm_evidence,
)
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.tag_data import analyze_tag_data


def capture(body: str = '', namespace: str = ''):
    raw = (f'<RSLogix5000Content{namespace}><Controller Name="Invented">{body}'
           '</Controller></RSLogix5000Content>')
    snapshot = snapshot_from_bytes(raw.encode('utf-8'))
    inventory = analyze_snapshot(snapshot)
    tag_data = analyze_tag_data(snapshot, inventory)
    return snapshot, inventory, tag_data, analyze_alarm_evidence(snapshot, inventory, tag_data)


def tag(content: str = '', name: str = 'InventedAlarm', data_type: str = 'ALARM_DIGITAL') -> str:
    return f'<Tags><Tag Name="{name}" DataType="{data_type}" TagType="Base">{content}</Tag></Tags>'


CONFIG = '''<AlarmConfig><Messages><Message Type="CAM"><Text Lang="en-US"><![CDATA[
<img src=x onerror=private_command()> & lexical alarm wording
]]></Text><Text Lang="fr-FR">Texte invente</Text></Message></Messages>
<AlarmClass>PrivateClass</AlarmClass><HMIGroup>PrivateGroup</HMIGroup>
<HMICmd>PrivateCommand()</HMICmd></AlarmConfig>'''
DATA = '<Data Format="Alarm"><AlarmDigitalParameters Severity="0007" ProgAck="false"/>' + CONFIG + '</Data>'
CONDITIONS = '<AlarmConditions><AlarmCondition Name="PrivateCondition" Input=".1" Severity="0099">' + CONFIG + '</AlarmCondition></AlarmConditions>'
DEFINITIONS = ('<AlarmDefinitions><DataTypeAlarmDefinition Name="PrivateType">'
    '<MemberAlarmDefinition Name="PrivateDefinition" Input=".PV" Limit="-0.00" Severity="0012">'
    + CONFIG + '</MemberAlarmDefinition></DataTypeAlarmDefinition></AlarmDefinitions>')


class AlarmEvidenceTests(unittest.TestCase):
    def test_empty_and_unused_typed_declarations_are_complete_observations(self) -> None:
        for body, count in (('', 0), (tag(), 1)):
            with self.subTest(body=body):
                args = capture(body)
                result = args[-1]
                self.assertEqual(result.status, 'complete')
                self.assertEqual(len(result.declarations), count)
                self.assertEqual(result.containers, [])
                self.assertEqual(result.elements, [])
                validate_alarm_evidence(*args)

    def test_supported_trees_preserve_raw_facts_and_tag_data_links(self) -> None:
        snapshot, inventory, tag_data, result = capture(tag(DATA + CONDITIONS) + DEFINITIONS)
        self.assertEqual(result.status, 'complete')
        self.assertEqual({row['kind'] for row in result.containers},
                         {'alarm_data', 'alarm_conditions', 'alarm_definitions'})
        self.assertEqual(result.declarations[0]['content_ids'], tag_data.owners[0]['content_ids'])
        self.assertEqual(len(result.declarations[0]['container_ids']), 2)
        settings = next(row for row in result.elements if row['kind'] == 'alarm_digital_parameters')
        self.assertEqual(settings['attributes']['Severity'], '0007')
        definition = next(row for row in result.elements if row['kind'] == 'member_alarm_definition')
        self.assertEqual(definition['attributes']['Input'], '.PV')
        self.assertEqual(definition['attributes']['Limit'], '-0.00')
        self.assertIn('<img src=x onerror=private_command()>', render_alarm_evidence_json(result))
        self.assertEqual(tag_data.status, 'partial')  # The older generic reader does not interpret Alarm format.
        for key, value in ALARM_EVIDENCE_CONSTANTS.items():
            self.assertEqual(getattr(result, key), value)
        self.assertNotIn('effective_value', vars(result))
        validate_alarm_evidence(snapshot, inventory, tag_data, result)

    def test_provenance_ids_parent_links_locators_and_snapshot_are_replayable(self) -> None:
        args = capture(tag(DATA + CONDITIONS) + DEFINITIONS)
        snapshot, inventory, _, result = args
        ids = {row['id'] for row in [*result.containers, *result.elements]}
        self.assertEqual(len(ids), len(result.containers) + len(result.elements))
        owners = {entity.id for entity in inventory.entities}
        for row in result.elements:
            self.assertIn(row['parent_id'], ids)
            self.assertIn(row['container_id'], ids)
            self.assertIn(row['owner_id'], owners)
            self.assertTrue(row['locator'].startswith('/RSLogix5000Content[1]/Controller[1]/'))
        self.assertTrue(all(row['parent_id'] is None for row in result.containers))
        self.assertEqual(result.snapshot['id'], snapshot.id)
        self.assertEqual(render_alarm_evidence_json(result), render_alarm_evidence_json(analyze_alarm_evidence(*args[:3])))
        changed = capture(tag(DATA + CONDITIONS, name='OtherName') + DEFINITIONS)[-1]
        self.assertTrue(ids.isdisjoint(row['id'] for row in [*changed.containers, *changed.elements]))

    def test_exact_types_and_supported_owner_kinds_only(self) -> None:
        body = tag('', 'Exact', 'ALARM_ANALOG') + tag('', 'Near', 'alarm_digital')
        body += '''<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="A"><Parameters>
          <Parameter Name="P" DataType="ALARM_DIGITAL"/></Parameters><LocalTags>
          <LocalTag Name="L" DataType="ALARM_ANALOG"/></LocalTags></AddOnInstructionDefinition>
          </AddOnInstructionDefinitions><Vendor><Tag Name="Hidden" DataType="ALARM_DIGITAL"/></Vendor>'''
        result = capture(body)[-1]
        self.assertEqual(len(result.declarations), 3)
        self.assertEqual({row['kind'] for row in result.declarations}, {'tag', 'aoi_parameter', 'aoi_local_tag'})
        self.assertEqual(result.containers, [])

    def test_unused_tag_based_conditions_and_definitions_do_not_need_alarm_typed_tags(self) -> None:
        result = capture(tag(CONDITIONS, data_type='DINT') + DEFINITIONS)[-1]
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.declarations, [])
        self.assertEqual(len(result.containers), 2)
        self.assertEqual(result.coverage['elements_by_kind']['alarm_condition'], 1)
        self.assertEqual(result.coverage['elements_by_kind']['member_alarm_definition'], 1)

    def test_duplicate_envelopes_and_named_members_are_preserved_and_quarantined(self) -> None:
        duplicates = '<AlarmConditions><AlarmCondition Name="Same">' + CONFIG + '</AlarmCondition>'
        duplicates += '<AlarmCondition Name="Same">' + CONFIG + '</AlarmCondition></AlarmConditions>'
        result = capture(tag(duplicates + duplicates))[-1]
        self.assertEqual(len(result.containers), 2)
        self.assertEqual(result.coverage['duplicate_groups'], 3)
        self.assertEqual(result.coverage['duplicate_records'], 6)
        self.assertTrue(all(row['qualification'] == 'source_gap' for row in [*result.containers, *result.elements]))
        self.assertTrue(all('ancestor_gap' in row['gap_codes'] for row in result.elements))

    def test_localized_texts_are_distinct_and_duplicate_languages_are_gaps(self) -> None:
        result = capture(tag(DATA))[-1]
        self.assertEqual(result.coverage['elements_by_kind']['text'], 2)
        self.assertEqual(result.coverage['duplicate_records'], 0)
        duplicate = DATA.replace('Lang="fr-FR"', 'Lang="en-US"')
        result = capture(tag(duplicate))[-1]
        self.assertEqual(result.coverage['duplicate_records'], 2)
        self.assertEqual(result.coverage['elements_by_qualification']['source_gap'], 2)

    def test_foreign_attributes_and_ancestor_namespaces_never_qualify_children(self) -> None:
        foreign = CONDITIONS.replace('<AlarmConditions>', '<AlarmConditions x:Flag="private">')
        result = capture(tag(foreign), ' xmlns:x="urn:private"')[-1]
        self.assertEqual(result.declarations[0]['qualification'], 'qualified')
        self.assertTrue(all(row['qualification'] == 'source_gap' for row in [*result.containers, *result.elements]))
        self.assertEqual(result.containers[0]['attributes'], {'urn:private}Flag': 'private'})
        foreign = '<x:Wrapper>' + tag(CONDITIONS) + '</x:Wrapper>'
        result = capture(foreign, ' xmlns:x="urn:private"')[-1]
        self.assertEqual(result.declarations, [])
        self.assertTrue(all(row['qualification'] == 'source_gap' for row in [*result.containers, *result.elements]))

    def test_root_namespace_is_supported_but_foreign_attribute_on_declaration_is_gap(self) -> None:
        result = capture(tag(DATA), ' xmlns="urn:source"')[-1]
        self.assertEqual(result.status, 'complete')
        self.assertTrue(all(row['xml_namespace'] == 'urn:source' for row in result.elements))
        body = tag(DATA).replace('TagType="Base"', 'TagType="Base" x:Review="secret"')
        result = capture(body, ' xmlns:x="urn:foreign"')[-1]
        self.assertEqual(result.declarations[0]['gap_codes'], ['namespace_gap'])
        self.assertTrue(all(row['qualification'] == 'source_gap' for row in result.elements))

    def test_misplaced_anchors_survive_without_fabricated_ownership_or_binding(self) -> None:
        result = capture('<Vendor>' + CONDITIONS + '</Vendor><AlarmCondition Name="Orphan" Input=".1"/>'
                         + '<Messages><Message><Text>Unrelated</Text></Message></Messages>')[-1]
        self.assertEqual(len(result.containers), 2)
        self.assertEqual(result.containers[1]['kind'], 'orphan')
        self.assertTrue(all(row['qualification'] == 'source_gap' for row in result.containers))
        self.assertNotIn('Unrelated', render_alarm_evidence_json(result))
        # Nearest controller provenance is retained; it does not establish a tag owner.
        self.assertIsNotNone(result.containers[0]['owner_id'])

    def test_unknown_and_nested_text_shapes_preserve_all_descendants(self) -> None:
        body = CONDITIONS.replace(CONFIG, '<Vendor><AlarmConfig><AlarmClass>nested</AlarmClass></AlarmConfig></Vendor>'
                            '<AlarmConfig><Messages><Message><Text Lang="en"><Inner>raw</Inner></Text></Message></Messages></AlarmConfig>')
        result = capture(tag(body))[-1]
        vendor = next(row for row in result.elements if row['xml_name'] == 'Vendor')
        self.assertIn('unknown_element', vendor['gap_codes'])
        text = next(row for row in result.elements if row['kind'] == 'text')
        self.assertIn('unexpected_children', text['gap_codes'])
        for row in result.elements:
            if row['xml_name'] in {'Inner', 'AlarmClass'}:
                self.assertEqual(row['qualification'], 'source_gap')
        self.assertEqual(result.coverage['elements_by_kind']['unknown'], 2)

    def test_mismatched_parameter_kind_missing_identity_and_direct_text_are_gaps(self) -> None:
        body = tag(DATA.replace('AlarmDigitalParameters', 'AlarmAnalogParameters'))
        body += tag('<AlarmConditions>unexpected<AlarmCondition Input=".PV"/></AlarmConditions>', name='Second')
        result = capture(body)[-1]
        self.assertEqual(result.coverage['gaps_by_code']['unsupported_placement'], 1)
        self.assertEqual(result.coverage['gaps_by_code']['missing_identity'], 1)
        self.assertEqual(result.coverage['gaps_by_code']['unexpected_direct_text'], 1)

    def test_missing_owner_identity_quarantines_its_entire_tree(self) -> None:
        body = tag(DATA).replace('Name="InventedAlarm" ', '')
        result = capture(body)[-1]
        self.assertIn('missing_identity', result.declarations[0]['gap_codes'])
        self.assertIn('missing_identity', result.containers[0]['gap_codes'])
        self.assertTrue(all(row['qualification'] == 'source_gap' for row in result.elements))

    def test_missing_message_and_language_identity_remain_visible_gaps(self) -> None:
        for field, original in (('Type', 'CAM'), ('Lang', 'en-US')):
            for replacement in ('', f'{field}=""', f'{field}="  "'):
                with self.subTest(field=field, replacement=replacement):
                    body = CONDITIONS.replace(f'{field}="{original}"', replacement)
                    result = capture(tag(body))[-1]
                    self.assertEqual(result.coverage['gaps_by_code']['missing_identity'], 1)
                    selected = [row for row in result.elements if row['kind'] == ('message' if field == 'Type' else 'text')]
                    self.assertTrue(any('missing_identity' in row['gap_codes'] for row in selected))
                    if field == 'Type':
                        self.assertTrue(all(row['qualification'] == 'source_gap' for row in result.elements if row['kind'] == 'text'))

    def test_message_type_requirement_follows_documented_context(self) -> None:
        # The shared analog structure and tag-based examples identify message
        # Type; the digital single-message shape is retained without guessing
        # that the same identity is mandatory there.
        digital = DATA.replace(' Type="CAM"', '')
        self.assertEqual(capture(tag(digital))[-1].status, 'complete')
        analog = digital.replace('AlarmDigitalParameters', 'AlarmAnalogParameters')
        result = capture(tag(analog, data_type='ALARM_ANALOG'))[-1]
        self.assertEqual(result.coverage['gaps_by_code']['missing_identity'], 1)

    def test_stored_data_formats_are_linked_without_effective_selection(self) -> None:
        body = tag(DATA + '<Data Format="L5K">private lexical data</Data>'
                   '<Data Format="Decorated"><Structure DataType="ALARM_DIGITAL"/></Data>')
        *_, tag_data, result = capture(body)
        self.assertEqual(result.status, 'complete')
        self.assertEqual(len(result.declarations[0]['content_ids']), 3)
        self.assertEqual(len(result.containers), 1)
        self.assertEqual(result.coverage['content_links_total'], len(tag_data.contents))

    def test_canonical_validation_rejects_changes_and_forged_dependencies(self) -> None:
        args = capture(tag(DATA + CONDITIONS) + DEFINITIONS)
        for key, mutate in (
            ('text', lambda r: r.elements[0]['attributes'].update(Severity='999')),
            ('qualification', lambda r: r.containers[0].update(qualification='source_gap')),
            ('owner', lambda r: r.elements[0].update(owner_id=None)),
            ('coverage', lambda r: r.coverage.update(containers_total=0)),
            ('extra', lambda r: r.declarations[0].update(private_extra='secret')),
        ):
            with self.subTest(key=key):
                changed = deepcopy(args[-1])
                mutate(changed)
                with self.assertRaises(AlarmEvidenceError):
                    validate_alarm_evidence(*args[:3], changed)
        changed_data = deepcopy(args[2])
        changed_data.contents[0]['attributes']['Format'] = 'Forged'
        with self.assertRaises(AlarmEvidenceError):
            analyze_alarm_evidence(*args[:2], changed_data)
        with self.assertRaises(AlarmEvidenceError):
            analyze_alarm_evidence(replace(args[0], sha256='f' * 64), *args[1:3])

    def test_record_scan_link_retention_and_serialization_caps_are_source_free(self) -> None:
        args = capture(tag(DATA + CONDITIONS) + DEFINITIONS)
        for name, value in (('MAX_ALARM_EVIDENCE_RECORDS', 1), ('MAX_ALARM_XML_VISITS', 2),
                            ('MAX_ALARM_EVIDENCE_LINKS', 0), ('MAX_ALARM_EVIDENCE_BYTES', 4097),
                            ('MAX_ALARM_EVIDENCE_JSON_BYTES', 256)):
            with self.subTest(name=name), patch('plc_workbench.alarm_evidence.' + name, value):
                with self.assertRaisesRegex(AlarmEvidenceError, '^Alarm evidence is inconsistent or exceeds its limits\\.$'):
                    analyze_alarm_evidence(*args[:3])

    def test_json_roundtrip_copy_and_hostile_containers(self) -> None:
        args = capture(tag(DATA))
        result = args[-1]
        copied = result.to_dict()
        self.assertEqual(copied, json.loads(render_alarm_evidence_json(result)))
        copied['elements'][0]['attributes']['Severity'] = 'changed'
        self.assertEqual(result.elements[0]['attributes']['Severity'], '0007')
        circular = deepcopy(result)
        circular.elements.append(circular.elements)
        with self.assertRaises(AlarmEvidenceError):
            render_alarm_evidence_json(circular)
        poisoned = replace(result, coverage={**result.coverage, 'records_with_gaps': True})
        with self.assertRaises(AlarmEvidenceError):
            render_alarm_evidence_json(poisoned)

    def test_demo_fixture_exercises_paging_and_raw_injection(self) -> None:
        path = Path(__file__).parents[2] / 'public/fixtures/synthetic/alarm_evidence_demo.L5X'
        snapshot = snapshot_from_bytes(path.read_bytes())
        inventory = analyze_snapshot(snapshot)
        tag_data = analyze_tag_data(snapshot, inventory)
        result = analyze_alarm_evidence(snapshot, inventory, tag_data)
        self.assertGreater(len(result.declarations), 50)
        self.assertGreater(len(result.containers), 50)
        self.assertEqual(result.status, 'partial')
        self.assertGreater(result.coverage['gaps_by_code']['namespace_gap'], 0)
        self.assertGreater(result.coverage['duplicate_records'], 0)
        self.assertIn('<img src=x onerror=', render_alarm_evidence_json(result))
        validate_alarm_evidence(snapshot, inventory, tag_data, result)


if __name__ == '__main__':
    unittest.main()
