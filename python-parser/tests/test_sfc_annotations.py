"""Invented annotation evidence stays separate from flow and descriptions."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.sfc_structure import (
    SfcStructureError, analyze_sfc_structure, render_sfc_text, validate_sfc_structure,
)
from plc_workbench.storage import save_run
from test_sfc_structure import fixture


def analyze(body: str):
    snapshot, inventory = fixture(body)
    return analyze_sfc_structure(snapshot, inventory)


def chars(value) -> int:
    if type(value) is str:
        return len(value)
    if type(value) is dict:
        return sum(chars(key) + chars(item) for key, item in value.items())
    if type(value) is list:
        return sum(map(chars, value))
    return 0


class SfcAnnotationTests(unittest.TestCase):
    def test_direct_and_child_cdata_remain_exact_opaque_text(self) -> None:
        result = analyze('''<SFCContent><TextBox ID="1"><![CDATA[  PRIVATE <raw>\n ]]></TextBox>
          <TextBox ID="2"><Text><![CDATA[ PRIVATE child & <text> ]]></Text></TextBox></SFCContent>''')
        self.assertEqual(result.status, 'complete')
        self.assertEqual([row['kind'] for row in result.elements],
                         ['text_box', 'text_box', 'text_box_text'])
        self.assertEqual([row['direct_text'] for row in result.elements],
                         ['  PRIVATE <raw>\n ', '', ' PRIVATE child & <text> '])
        self.assertEqual(result.annotations, [])
        self.assertEqual((result.schema_version, result.analyzer_version), (2, 'sfc-structure-2'))

    def test_wrong_parent_text_and_nested_markup_stay_unmodeled(self) -> None:
        result = analyze('''<SFCContent><Step ID="1"><Text>PRIVATE_WRONG</Text></Step>
          <TextBox ID="2"><Text>before<Bold>nested</Bold>after<Text>other</Text>
          <Description>unknown description context</Description></Text></TextBox></SFCContent>''')
        unknown = [row for row in result.elements if row['kind'] == 'unmodeled']
        self.assertEqual([row['xml_name'] for row in unknown], ['Text', 'Bold', 'Text', 'Description'])
        text = next(row for row in result.elements if row['kind'] == 'text_box_text')
        self.assertEqual(text['direct_text'], 'beforeafter\n          ')
        self.assertEqual([row['direct_text'] for row in unknown],
                         ['PRIVATE_WRONG', 'nested', 'other', 'unknown description context'])
        self.assertEqual(sum(issue['code'] == 'element_unmodeled' for issue in result.issues), 4)

    def test_attachment_direction_action_targets_and_flow_are_independent(self) -> None:
        result = analyze('''<SFCContent><TextBox ID="0001"><Text>PRIVATE_NOTE</Text></TextBox>
          <Step ID="2" Operand="PRIVATE_STEP"><Action ID="3" Operand="PRIVATE_ACTION"/></Step>
          <Transition ID="4"/><DirectedLink FromID="2" ToID="4"/>
          <Attachment FromID="1" ToID="0003"/><Attachment FromID="0001" ToID="2"/>
          <Attachment FromID="2" ToID="1"/><Attachment FromID="1" ToID="1"/>
          <DirectedLink FromID="1" ToID="3"/></SFCContent>''')
        self.assertEqual([(a['from_status'], a['to_status']) for a in result.annotations],
                         [('resolved', 'resolved'), ('resolved', 'resolved'),
                          ('unsupported_kind', 'unsupported_kind'), ('resolved', 'unsupported_kind')])
        self.assertEqual([(a['from_status'], a['to_status']) for a in result.links],
                         [('resolved', 'resolved'), ('unsupported_kind', 'unsupported_kind')])
        action = next(row for row in result.elements if row['kind'] == 'action')
        self.assertEqual(result.annotations[0]['to_element_id'], action['id'])
        self.assertEqual(sum(i['code'] == 'annotation_endpoint_unresolved' for i in result.issues), 3)
        self.assertEqual(sum(i['code'] == 'link_endpoint_unresolved' for i in result.issues), 2)

    def test_attachment_endpoint_failures_use_full_id_index_without_fallback(self) -> None:
        result = analyze('''<SFCContent><TextBox ID="1"/><Vendor ID="01"/><Step ID="2"/>
          <Vendor ID="3"/><Attachment FromID="1" ToID="2"/><Attachment ToID="999"/>
          <Attachment FromID="-1" ToID="3"/><Attachment FromID=" 1" ToID="4294967296"/>
          </SFCContent>''')
        self.assertEqual([(a['from_status'], a['to_status']) for a in result.annotations],
                         [('ambiguous_target', 'resolved'), ('missing_attribute', 'missing_target'),
                          ('invalid_id', 'unsupported_kind'), ('invalid_id', 'invalid_id')])
        self.assertIsNone(result.annotations[0]['from_element_id'])
        self.assertEqual(sum(i['code'] == 'block_id_duplicate' for i in result.issues), 2)
        self.assertEqual(sum(i['code'] == 'annotation_endpoint_unresolved' for i in result.issues), 7)

    def test_content_edit_namespaces_do_not_cross_resolve_or_select_versions(self) -> None:
        result = analyze('''<SFCContent OnlineEditType="Original"><TextBox ID="1"/><Step ID="2"/>
          <Attachment FromID="1" ToID="2"/></SFCContent>
          <SFCContent OnlineEditType="PendingEdits"><TextBox ID="1"/>
          <Attachment FromID="1" ToID="2"/></SFCContent>''')
        self.assertEqual([a['to_status'] for a in result.annotations], ['resolved', 'missing_target'])
        self.assertNotEqual(result.annotations[0]['from_element_id'], result.annotations[1]['from_element_id'])
        self.assertNotIn('block_id_duplicate', {i['code'] for i in result.issues})

    def test_annotation_capture_does_not_change_inventory_st_flow_or_ids(self) -> None:
        body = '''<SFCContent><TextBox ID="1"><Text>PRIVATE_NOTE</Text></TextBox>
          <Step ID="2"><Action ID="3"><Body><STContent><Line Number="0">PRIVATE := 42;</Line></STContent></Body></Action></Step>
          <Transition ID="4"/><DirectedLink FromID="2" ToID="4"/>
          <Attachment FromID="1" ToID="3"/></SFCContent>'''
        snapshot, inventory = fixture(body)
        before = inventory.to_dict()
        result = analyze_sfc_structure(snapshot, inventory)
        self.assertEqual(inventory.to_dict(), before)
        self.assertEqual(len(result.links), 1)
        self.assertEqual(len(result.annotations), 1)
        self.assertEqual(result.links[0]['from_status'], 'resolved')
        line = next(row for row in result.elements if row['kind'] == 'st_line')
        self.assertEqual(line['direct_text'], 'PRIVATE := 42;')
        self.assertEqual(sum(row['block_id_status'] == 'valid' for row in result.elements), 4)
        self.assertEqual(result.elements, analyze_sfc_structure(snapshot, inventory).elements)

    def test_annotation_limit_and_exact_all_key_value_character_budget(self) -> None:
        body = '<SFCContent><TextBox ID="1"/><Step ID="2"/><Attachment FromID="1" ToID="2"/></SFCContent>'
        with patch('plc_workbench.sfc_structure.MAX_SFC_ANNOTATIONS', 0):
            with self.assertRaises(SfcStructureError) as caught:
                analyze(body)
            self.assertNotIn('TextBox', str(caught.exception))
        result = analyze(body)
        exact = chars(result.to_dict())
        with patch('plc_workbench.sfc_structure.MAX_SFC_EVIDENCE_CHARS', exact):
            self.assertEqual(analyze(body), result)
        with patch('plc_workbench.sfc_structure.MAX_SFC_EVIDENCE_CHARS', exact - 1):
            with self.assertRaises(SfcStructureError):
                analyze(body)

    def test_canonical_annotation_tampering_and_cycles_are_rejected(self) -> None:
        snapshot, inventory = fixture('<SFCContent><TextBox ID="1"/><Step ID="2"/><Attachment FromID="1" ToID="2"/></SFCContent>')
        result = analyze_sfc_structure(snapshot, inventory)
        bad = deepcopy(result.annotations)
        bad[0]['to_element_id'] = bad[0]['from_element_id']
        cyclic: list = []
        cyclic.append(cyclic)
        for changed in (replace(result, annotations=bad), replace(result, annotations=[]),
                        replace(result, annotations=cyclic), replace(result, schema_version=True)):
            with self.subTest(changed=type(changed.annotations)), self.assertRaises(SfcStructureError):
                validate_sfc_structure(snapshot, inventory, changed)

    def test_private_text_and_saved_artifacts_include_separate_annotations(self) -> None:
        snapshot, inventory = fixture('''<SFCContent><TextBox ID="1" Name="PRIVATE_LABEL"><Text>PRIVATE_NOTE</Text></TextBox>
          <Step ID="2" Operand="PRIVATE_STEP"/><Attachment FromID="1" ToID="2"/></SFCContent>''')
        result = analyze_sfc_structure(snapshot, inventory)
        rendered = render_sfc_text(result, inventory=inventory)
        self.assertIn('Annotation attachments (separate from control flow):', rendered)
        self.assertIn('no automatic description assignment', rendered)
        self.assertIn('PRIVATE_NOTE', rendered)
        self.assertIn('PRIVATE_STEP', rendered)
        self.assertIn('PRIVATE_LABEL', rendered)
        with tempfile.TemporaryDirectory() as directory:
            run = save_run(Path(directory), snapshot, inventory, sfc_structure=result)
            self.assertEqual(json.loads((run / 'sfc-structure.json').read_text()), result.to_dict())
            self.assertEqual((run / 'sfc-structure.txt').read_text(), rendered)
            manifest = json.loads((run / 'manifest.json').read_text())
            self.assertEqual(manifest['sfc_schema_version'], 2)
            for name, details in manifest['artifacts'].items():
                data = (run / name).read_bytes()
                self.assertEqual(details, {'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data)})

    def test_repeated_attachments_do_not_repeat_large_endpoint_payloads(self) -> None:
        note = 'PRIVATE_NOTE_' + 'N' * 5_000
        label = 'PRIVATE_LABEL_' + 'L' * 5_000
        operand = 'PRIVATE_OPERAND_' + 'O' * 5_000

        def rendered(attachments: int) -> str:
            result = analyze(f'<SFCContent><TextBox ID="1" Label="{label}">'
                             f'<Text>{note}</Text></TextBox><Step ID="2" Operand="{operand}"/>'
                             + '<Attachment FromID="1" ToID="2"/>' * attachments
                             + '</SFCContent>')
            return render_sfc_text(result)

        single = rendered(1)
        repeated = rendered(500)
        for payload in (note, label, operand):
            self.assertEqual(repeated.count(payload), 1)
        self.assertEqual(repeated.count('      Annotation:'), 500)
        self.assertIn('Element descriptors (attributes and raw text shown once):', repeated)
        self.assertIn('Endpoint IDs refer to the element descriptors above.', repeated)
        annotation_section = repeated.split('    Annotation attachments', 1)[1]
        self.assertNotIn(note, annotation_section)
        self.assertNotIn(label, annotation_section)
        self.assertNotIn(operand, annotation_section)
        # Additional attachments contribute only fixed-size ID/type/attribute
        # records. They cannot multiply 15K endpoint text/attribute payloads.
        self.assertLess(len(repeated) - len(single), 1_000 * 499)


if __name__ == '__main__':
    unittest.main()
