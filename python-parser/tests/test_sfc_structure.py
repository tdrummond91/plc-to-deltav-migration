"""SFC structure evidence uses invented XML only, never plant exports."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.sfc_structure import (
    SfcStructureError, analyze_sfc_structure, render_sfc_json, render_sfc_text,
    validate_sfc_structure,
)
from plc_workbench.source import analyze_snapshot, capture_snapshot, snapshot_from_bytes


def fixture(body: str = '<SFCContent/>', extra: str = '', aoi: str = ''):
    data = (f'<RSLogix5000Content><Controller Name="PRIVATE_CONTROLLER">'
            f'<Programs><Program Name="PRIVATE_PROGRAM"><Routines>'
            f'<Routine Name="PRIVATE_CHART" Type="SFC">{body}</Routine>{extra}'
            f'</Routines></Program></Programs>{aoi}</Controller></RSLogix5000Content>').encode()
    snapshot = snapshot_from_bytes(data)
    return snapshot, analyze_snapshot(snapshot)


def analyze(body: str = '<SFCContent/>', **kwargs):
    snapshot, inventory = fixture(body, **kwargs)
    return analyze_sfc_structure(snapshot, inventory)


class SfcStructureTests(unittest.TestCase):
    def test_empty_chart_complete_without_changing_existing_inventory(self) -> None:
        snapshot, inventory = fixture()
        prior = inventory.to_dict()
        result = analyze_sfc_structure(snapshot, inventory)
        self.assertEqual(result.status, 'complete')
        self.assertEqual(len(result.routines), 1)
        self.assertEqual(len(result.contents), 1)
        self.assertEqual(result.elements, [])
        self.assertEqual(result.semantic_analysis, 'not_implemented')
        self.assertEqual(inventory.to_dict(), prior)
        validate_sfc_structure(snapshot, inventory, result)

    def test_no_sfc_and_familiar_names_in_extensions_are_not_declarations(self) -> None:
        data = b'<RSLogix5000Content><Controller Name="C"><Vendor><Routines><Routine Type="SFC"><SFCContent><Step ID="1"/></SFCContent></Routine></Routines></Vendor></Controller></RSLogix5000Content>'
        snapshot = snapshot_from_bytes(data)
        result = analyze_sfc_structure(snapshot, analyze_snapshot(snapshot))
        self.assertEqual(result.status, 'complete')
        self.assertEqual((result.routines, result.contents, result.elements), ([], [], []))

    def test_flow_ids_links_and_opaque_st_action_condition_are_retained(self) -> None:
        result = analyze('''<SFCContent Custom="PRIVATE_META">
          <Step ID="0001" Operand="PRIVATE_STEP"><ActionList><Action ID="3" Operand="PRIVATE_ACTION"><Body><STContent><Line Number="0">PRIVATE_OUTPUT := 42;</Line></STContent></Body></Action></ActionList><Preset>PRIVATE_PRESET</Preset></Step>
          <Transition ID="2"><Condition><STContent><Line Number="0">PRIVATE_SIGNAL &gt; 3</Line></STContent></Condition></Transition>
          <DirectedLink FromID="1" ToID="0002"/>
        </SFCContent>''')
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.links[0]['from_status'], 'resolved')
        self.assertEqual(result.links[0]['to_status'], 'resolved')
        step = next(e for e in result.elements if e['kind'] == 'step')
        self.assertEqual(step['canonical_id'], '1')
        self.assertEqual(step['attributes']['ID'], '0001')
        self.assertIsNone(step['parent_id'])
        line = next(e for e in result.elements if e['direct_text'] == 'PRIVATE_OUTPUT := 42;')
        self.assertEqual(line['kind'], 'st_line')
        self.assertEqual(result.contents[0]['attributes']['Custom'], 'PRIVATE_META')

    def test_multiple_edit_contents_keep_ids_and_link_namespaces_separate(self) -> None:
        result = analyze('''<SFCContent OnlineEditType="Original"><Step ID="1"/><Transition ID="2"/><DirectedLink FromID="1" ToID="2"/></SFCContent>
          <SFCContent OnlineEditType="PendingEdits"><Step ID="1"/><DirectedLink FromID="1" ToID="2"/></SFCContent>
          <SFCContent OnlineEditType="TestEdits"/>''')
        self.assertEqual([c['edit_kind'] for c in result.contents], ['Original', 'PendingEdits', 'TestEdits'])
        self.assertEqual(result.links[0]['to_status'], 'resolved')
        self.assertEqual(result.links[1]['to_status'], 'missing_target')
        self.assertNotEqual(result.links[0]['from_element_id'], result.links[1]['from_element_id'])
        self.assertNotIn('block_id_duplicate', {i['code'] for i in result.issues})

    def test_duplicate_normalized_ids_and_unknown_records_never_choose_target(self) -> None:
        result = analyze('<SFCContent><Step ID="1"/><Transition ID="01"/><Vendor ID="2"/><DirectedLink FromID="1" ToID="2"/></SFCContent>')
        self.assertEqual(result.links[0]['from_status'], 'ambiguous_target')
        self.assertEqual(result.links[0]['to_status'], 'unsupported_kind')
        self.assertIsNone(result.links[0]['from_element_id'])
        self.assertEqual(sum(i['code'] == 'block_id_duplicate' for i in result.issues), 2)

    def test_uint32_ids_lexical_normalization_and_endpoint_rejections(self) -> None:
        result = analyze('''<SFCContent><Step ID="4294967295"/><Step ID="4294967296"/>
          <Step ID="-1"/><Step ID=" 1"/><Step ID="١"/><Step/>
          <DirectedLink FromID="0004294967295" ToID="4294967296"/>
          <DirectedLink ToID="999"/></SFCContent>''')
        self.assertEqual([e['block_id_status'] for e in result.elements[:6]],
                         ['valid', 'invalid', 'invalid', 'invalid', 'invalid', 'missing'])
        self.assertEqual(result.links[0]['from_status'], 'resolved')
        self.assertEqual(result.links[0]['to_status'], 'invalid_id')
        self.assertEqual(result.links[1]['from_status'], 'missing_attribute')
        self.assertEqual(result.links[1]['to_status'], 'missing_target')

    def test_branch_legs_flow_kinds_and_nonflow_targets(self) -> None:
        result = analyze('''<SFCContent><Branch ID="1"><Leg ID="2"/></Branch><SbrRet ID="3"/><Stop ID="4"/>
          <Step ID="5"><Action ID="6"/></Step><TextBox ID="7"/>
          <DirectedLink FromID="2" ToID="3"/><DirectedLink FromID="6" ToID="7"/></SFCContent>''')
        self.assertEqual(result.links[0]['from_status'], 'resolved')
        self.assertEqual(result.links[0]['to_status'], 'resolved')
        self.assertEqual(result.links[1]['from_status'], 'unsupported_kind')
        self.assertEqual(result.links[1]['to_status'], 'unsupported_kind')

    def test_unmodeled_context_all_text_preserved_and_partial(self) -> None:
        result = analyze('<SFCContent>PRIVATE_CONTENT<Step ID="1">PRIVATE_STEP_TEXT<Transition ID="2"/><Vendor PRIVATE="X">PRIVATE_UNKNOWN</Vendor></Step></SFCContent>')
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.contents[0]['direct_text'], 'PRIVATE_CONTENT')
        self.assertEqual([e['kind'] for e in result.elements], ['step', 'unmodeled', 'unmodeled'])
        self.assertEqual(result.elements[-1]['direct_text'], 'PRIVATE_UNKNOWN')
        self.assertEqual(result.elements[-1]['attributes'], {'PRIVATE': 'X'})
        self.assertIn('unexpected_direct_text', {i['code'] for i in result.issues})

    def test_unmodeled_routine_siblings_and_text_are_one_explicit_gap(self) -> None:
        result = analyze('PRIVATE_ROUTINE_TEXT<SFCContent/><Vendor><Payload>PRIVATE_VENDOR</Payload></Vendor><Other/>')
        self.assertEqual(result.status, 'partial')
        routine = result.routines[0]
        self.assertEqual([m['xml_name'] for m in routine['unmodeled_children']], ['Vendor', 'Other'])
        self.assertEqual(routine['direct_text'], 'PRIVATE_ROUTINE_TEXT')
        self.assertEqual([i['code'] for i in result.issues], ['routine_content_unmodeled'])
        self.assertNotIn('PRIVATE_VENDOR', render_sfc_json(result))
        self.assertEqual(result.elements, [])
        self.assertEqual(analyze('<Description>PRIVATE_DESCRIPTION</Description><EncryptionInfo/><SFCContent/>').status,
                         'complete')

    def test_protection_missing_body_and_unknown_edit_types_are_explicit(self) -> None:
        result = analyze('<EncryptedContent PRIVATE="X"/>')
        self.assertEqual({i['code'] for i in result.issues}, {'protection_present', 'content_missing'})
        self.assertEqual(result.routines[0]['protection_markers'][0]['xml_name'], 'EncryptedContent')
        result = analyze('<SFCContent OnlineEditType=""/><SFCContent OnlineEditType="PRIVATE_UNKNOWN"/>')
        self.assertEqual([c['edit_kind'] for c in result.contents], ['empty', 'other'])
        self.assertEqual(result.status, 'partial')

    def test_aoi_chart_kept_as_structural_evidence_without_runtime_inference(self) -> None:
        aoi = '<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="PRIVATE_AOI"><Routines><Routine Name="Logic" Type="SFC"><SFCContent/></Routine></Routines></AddOnInstructionDefinition></AddOnInstructionDefinitions>'
        snapshot, inventory = fixture(aoi=aoi)
        result = analyze_sfc_structure(snapshot, inventory)
        self.assertEqual(len(result.routines), 2)
        self.assertEqual(result.status, 'complete')
        aoi_entity = next(e for e in inventory.entities if e.kind == 'aoi')
        self.assertEqual(result.routines[1]['scope_id'], aoi_entity.id)

    def test_snapshot_pair_and_canonical_declaration_tampering_rejected(self) -> None:
        snapshot, inventory = fixture()
        for changed_snapshot in (replace(snapshot, sha256='0' * 64), replace(snapshot, size_bytes=True)):
            with self.assertRaises(SfcStructureError):
                analyze_sfc_structure(changed_snapshot, inventory)
        with self.assertRaises(SfcStructureError):
            analyze_sfc_structure(snapshot, replace(inventory, entities=inventory.entities[:-1]))
        entity = inventory.entities[-1]
        altered = replace(entity, attributes={**entity.attributes, 'Type': 'RLL'})
        with self.assertRaises(SfcStructureError):
            analyze_sfc_structure(snapshot, replace(inventory, entities=[*inventory.entities[:-1], altered]))

    def test_canonical_replay_rejects_status_id_and_bool_number_alterations(self) -> None:
        snapshot, inventory = fixture('<SFCContent><Step ID="1"/></SFCContent>')
        result = analyze_sfc_structure(snapshot, inventory)
        changed_elements = deepcopy(result.elements)
        changed_elements[0]['canonical_id'] = '2'
        for changed in (replace(result, schema_version=True), replace(result, status='partial'),
                        replace(result, elements=changed_elements)):
            with self.assertRaises(SfcStructureError):
                validate_sfc_structure(snapshot, inventory, changed)

    def test_cyclic_and_wrong_type_candidates_fail_before_deep_copy(self) -> None:
        snapshot, inventory = fixture()
        result = analyze_sfc_structure(snapshot, inventory)
        cyclic: list = []
        cyclic.append(cyclic)
        for changed in (replace(result, routines=cyclic), replace(result, contents={'bad': 'shape'})):
            with self.assertRaises(SfcStructureError):
                validate_sfc_structure(snapshot, inventory, changed)

    def test_bounds_elements_contents_links_chars_ids_fixed_safe_errors(self) -> None:
        cases = [
            ('MAX_SFC_ELEMENTS', 0, '<SFCContent><Step ID="1"/></SFCContent>'),
            ('MAX_SFC_CONTENTS', 0, '<SFCContent/>'),
            ('MAX_SFC_LINKS', 0, '<SFCContent><DirectedLink/></SFCContent>'),
            ('MAX_SFC_EVIDENCE_CHARS', 0, '<SFCContent/>'),
            ('MAX_SFC_ID_LENGTH', 1, '<SFCContent><Step ID="PRIVATE_SECRET"/></SFCContent>'),
        ]
        for constant, limit, body in cases:
            with self.subTest(constant=constant), patch(f'plc_workbench.sfc_structure.{constant}', limit):
                with self.assertRaises(SfcStructureError) as captured:
                    analyze(body)
                self.assertNotIn('PRIVATE_SECRET', str(captured.exception))

    def test_evidence_budget_counts_source_attribute_keys_and_exact_full_result(self) -> None:
        with patch('plc_workbench.sfc_structure.MAX_SFC_EVIDENCE_CHARS', 2000):
            with self.assertRaises(SfcStructureError):
                analyze(f'<SFCContent {"A" * 3000}="X"/>')

        def retained_characters(value) -> int:
            if type(value) is str:
                return len(value)
            if type(value) is dict:
                return sum(retained_characters(key) + retained_characters(item)
                           for key, item in value.items())
            if type(value) is list:
                return sum(map(retained_characters, value))
            return 0

        for body in ('<SFCContent><Step ID="1"/></SFCContent>', '<SFCContent/><Vendor/>'):
            with self.subTest(body=body):
                result = analyze(body)
                exact = retained_characters(result.to_dict())
                with patch('plc_workbench.sfc_structure.MAX_SFC_EVIDENCE_CHARS', exact):
                    self.assertEqual(analyze(body), result)
                with patch('plc_workbench.sfc_structure.MAX_SFC_EVIDENCE_CHARS', exact - 1):
                    with self.assertRaises(SfcStructureError):
                        analyze(body)

    def test_saved_snapshot_bytes_survive_live_file_replacement_and_private_rendering(self) -> None:
        snapshot, inventory = fixture('<SFCContent><Step ID="1" Operand="PRIVATE_STEP"/></SFCContent>')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'invented.L5X'
            path.write_bytes(snapshot.data)
            captured = capture_snapshot(path)
            path.write_bytes(b'PRIVATE_REPLACEMENT')
            result = analyze_sfc_structure(captured, inventory)
        self.assertEqual(result.status, 'complete')
        self.assertIn('PRIVATE_STEP', render_sfc_text(result, inventory=inventory))
        self.assertEqual(json.loads(render_sfc_json(result)), result.to_dict())


if __name__ == '__main__':
    unittest.main()
