"""Independent expectations for source identity, coverage and exact evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.source import (
    SourceError, analyze_snapshot, capture_snapshot, snapshot_from_bytes,
)

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "public/fixtures/synthetic/controller_demo.L5X"


def analyze(body: str):
    return analyze_snapshot(snapshot_from_bytes(
        f'<RSLogix5000Content><Controller Name="Demo">{body}</Controller>'
        '</RSLogix5000Content>'.encode()
    )).to_dict()


def routine(text: str, name: str = "Main", number: str = "0") -> str:
    return (f'<Routine Name="{name}" Type="RLL"><RLLContent>'
            f'<Rung Number="{number}" Type="N"><Text><![CDATA[{text}]]></Text>'
            '</Rung></RLLContent></Routine>')


class SourceInventoryTests(unittest.TestCase):
    def test_independent_fixture_counts_and_source_links(self) -> None:
        expected = json.loads((FIXTURE.parent / "expected_inventory.json").read_text())
        result = analyze_snapshot(capture_snapshot(FIXTURE)).to_dict()
        for key, count in expected["counts"].items():
            self.assertEqual(result["counts"][key], count, key)
        self.assertEqual(result["routine_types"], expected["routine_types"])
        self.assertEqual(result["instruction_counts"], expected["instruction_counts"])
        self.assertEqual(result["coverage"]["rungs"]["parsed"], 9)
        self.assertEqual(result["coverage"]["routines"]["preserved_unsupported"], 1)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["semantic_analysis"], "not_implemented")
        entities = {row["id"]: row for row in result["entities"]}
        for rung in result["rungs"]:
            self.assertEqual(entities[rung["parent_id"]]["kind"], "routine")
            self.assertTrue(rung["locator"].startswith(entities[rung["parent_id"]]["locator"]))
            for inst in rung["instructions"]:
                fragment = rung["text"][inst["start"]:inst["end"]]
                self.assertTrue(fragment.startswith(inst["opcode"]))
                self.assertTrue(fragment.endswith(")"))

    def test_duplicate_scoped_names_and_identical_rungs_keep_identity(self) -> None:
        body = '<Programs>' + ''.join(
            f'<Program Name="P{index}"><Tags><Tag Name="Same" TagType="Base" '
            'DataType="BOOL"/></Tags><Routines>' + routine('XIC(Same);') +
            routine('XIC(Same);') + '</Routines></Program>' for index in range(2)
        ) + '</Programs>'
        result = analyze(body)
        ids = [row['id'] for row in result['entities'] + result['rungs']]
        self.assertEqual(len(ids), len(set(ids)))
        tags = [row for row in result['entities'] if row['kind'] == 'tag']
        self.assertNotEqual(tags[0]['scope_id'], tags[1]['scope_id'])
        self.assertEqual(len({r['id'] for r in result['rungs']}), 4)

    def test_snapshot_is_read_once_and_results_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source with spaces.L5X'
            before = FIXTURE.read_bytes()
            source.write_bytes(before)
            captured = capture_snapshot(source)
            self.assertEqual(source.read_bytes(), before)
            source.write_bytes(b'not XML any more')
            first = analyze_snapshot(captured).to_dict()
            second = analyze_snapshot(captured).to_dict()
            self.assertEqual(first, second)
            self.assertEqual(captured.sha256, hashlib.sha256(before).hexdigest())
            self.assertEqual(first['counts']['rungs'], 9)
            changed = snapshot_from_bytes(before + b'\n')
            self.assertNotEqual(captured.id, changed.id)

    def test_partial_export_and_opaque_unknown_content_are_visible(self) -> None:
        result = analyze('<Programs><Program Name="Only"><Routines>'
                         '<EncodedData Name="Locked" EncodedType="Routine">abc</EncodedData>'
                         '<Routine Name="Sequence" Type="SFC"><SFCContent/></Routine>'
                         '<Routine Name="Blank" Type="RLL"/>'
                         '</Routines></Program></Programs><NovelThing Custom="yes">payload</NovelThing>')
        self.assertEqual(result['counts']['encoded_regions'], 1)
        self.assertEqual(result['counts']['routines'], 2)
        codes = {r['code'] for r in result['diagnostics']}
        self.assertIn('encoded_content', codes)
        self.assertIn('routine_language_not_analyzed', codes)
        self.assertIn('routine_content_missing', codes)
        self.assertTrue(any(r['path'].endswith('/NovelThing')
                            for r in result['coverage']['unmodeled_xml_paths']))
        self.assertEqual(result['status'], 'partial')

    def test_unknown_opcode_parses_but_is_not_classified(self) -> None:
        result = analyze('<Programs><Program Name="P"><Routines>' +
                         routine('  PrivateInstruction(a, [1,2]) ;') +
                         '</Routines></Program></Programs>')
        rung = result['rungs'][0]
        self.assertEqual(rung['parse_status'], 'parsed')
        self.assertEqual(rung['instructions'][0]['opcode'], 'PrivateInstruction')
        self.assertEqual(rung['instructions'][0]['semantic_status'], 'not_analyzed')
        self.assertEqual(rung['text'][rung['instructions'][0]['start']:
                                     rung['instructions'][0]['end']],
                         'PrivateInstruction(a, [1,2])')

    def test_rung_gap_accounting_and_metadata(self) -> None:
        result = analyze('<Programs><Program Name="P"><Routines>' +
                         routine('XIC(a);') + routine('XIC(a)') +
                         '<Routine Name="MissingText" Type="RLL"><RLLContent>'
                         '<Rung Number="0" Type="N"/></RLLContent></Routine>'
                         '</Routines></Program></Programs><Other><Rung/></Other>')
        coverage = result['coverage']['rungs']
        self.assertEqual(coverage, {'encountered': 4, 'parsed': 1,
                                   'failed': 2, 'preserved_unsupported': 1, 'excluded': 0})
        self.assertEqual(result['counts']['instructions'], 1)
        self.assertEqual(result['coverage']['instruction_count_complete'], False)
        self.assertEqual(result['status'], 'partial')

    def test_nested_st_inside_sfc_does_not_count_as_an_st_routine(self) -> None:
        result = analyze('<Programs><Program Name="P"><Routines>'
                         '<Routine Name="S" Type="SFC"><SFCContent><Condition>'
                         '<STContent><Line>Example;</Line></STContent></Condition>'
                         '</SFCContent></Routine></Routines></Program></Programs>')
        self.assertEqual(result['routine_types'], {'SFC': 1})

    def test_aoi_scopes_and_tag_units_are_separate(self) -> None:
        result = analyze('<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="A">'
                         '<Parameters><Parameter Name="In" DataType="BOOL"/></Parameters>'
                         '<LocalTags><LocalTag Name="L" DataType="DINT"/></LocalTags>'
                         '<Routines>' + routine('ADD(In,1,L);') +
                         '</Routines></AddOnInstructionDefinition></AddOnInstructionDefinitions>')
        self.assertEqual(result['counts']['aoi_definitions'], 1)
        self.assertEqual(result['counts']['aoi_parameters'], 1)
        self.assertEqual(result['counts']['aoi_local_tags'], 1)
        self.assertEqual(result['counts']['total_tag_definitions'], 0)
        aoi = next(e for e in result['entities'] if e['kind'] == 'aoi')
        self.assertEqual(result['rungs'][0]['scope_id'], aoi['id'])

    def test_malformed_xml_and_entities_fail_without_source_content(self) -> None:
        for raw in (b'<PRIVATE', b'<!DOCTYPE x [<!ENTITY e "SECRET">]><x>&e;</x>',
                    b'<WrongRoot/>'):
            with self.subTest(raw=raw), self.assertRaises(SourceError) as caught:
                analyze_snapshot(snapshot_from_bytes(raw))
            self.assertNotIn('PRIVATE', str(caught.exception))
            self.assertNotIn('SECRET', str(caught.exception))

    def test_namespace_collisions_and_resource_limits(self) -> None:
        with self.assertRaises(SourceError):
            analyze('<Tags xmlns:a="one" xmlns:b="two"><a:Tag/><b:Tag/></Tags>')
        with patch('plc_workbench.source.MAX_SOURCE_BYTES', 3):
            with self.assertRaises(SourceError):
                snapshot_from_bytes(b'1234')
        with patch('plc_workbench.source.MAX_ELEMENTS', 2):
            with self.assertRaises(SourceError):
                analyze('<Extra/>')

    def test_duplicate_text_or_nested_xml_is_not_silently_parsed(self) -> None:
        result = analyze('<Programs><Program Name="P"><Routines>'
                         '<Routine Name="R" Type="RLL"><RLLContent>'
                         '<Rung Number="0" Type="N"><Text>XIC(a);</Text><Text>OTE(b);</Text></Rung>'
                         '<Rung Number="1" Type="N"><Text>XIC(<Part/>a);</Text></Rung>'
                         '</RLLContent></Routine></Routines></Program></Programs>')
        self.assertEqual(result['coverage']['rungs']['failed'], 2)
        self.assertEqual(result['counts']['instructions'], 0)

    def test_declaration_names_in_extensions_are_not_source_declarations(self) -> None:
        result = analyze('<VendorExtension><Tag Name="Fake"/>' + routine('OTE(Fake);') +
                         '</VendorExtension>')
        self.assertEqual(result['counts']['total_tag_definitions'], 0)
        self.assertEqual(result['counts']['routines'], 0)
        self.assertEqual(result['counts']['instructions'], 0)
        self.assertEqual(result['coverage']['rungs']['preserved_unsupported'], 1)
        paths = {row['path'] for row in result['coverage']['unmodeled_xml_paths']}
        self.assertIn('/RSLogix5000Content/Controller/VendorExtension/Tag', paths)
        self.assertEqual(result['status'], 'partial')

    def test_unrecognized_executable_xml_prevents_complete_instruction_counts(self) -> None:
        examples = (
            '<RLLContent><UnexpectedInstruction>opaque</UnexpectedInstruction></RLLContent>',
            '<RLLContent>opaque</RLLContent>',
            '<RLLContent/><UnexpectedInstruction/>',
            '<RLLContent><Rung Number="0" Type="N"><Text>OTE(a);</Text>'
            '<UnexpectedInstruction/></Rung></RLLContent>',
        )
        for content in examples:
            with self.subTest(content=content):
                result = analyze('<Programs><Program Name="P"><Routines>'
                                 '<Routine Name="R" Type="RLL">' + content +
                                 '</Routine></Routines></Program></Programs>')
                self.assertEqual(result['coverage']['routines']['failed'], 1)
                self.assertFalse(result['coverage']['instruction_count_complete'])
                self.assertEqual(result['status'], 'partial')

    def test_ambiguous_descriptions_and_comments_have_diagnostics(self) -> None:
        result = analyze('<Tags><Tag Name="T"><Description>one</Description>'
                         '<Description>two</Description></Tag></Tags>'
                         '<Programs><Program Name="P"><Routines>' +
                         routine('OTE(T);').replace('</Rung>',
                             '<Comment>one</Comment><Comment>two</Comment></Rung>') +
                         '</Routines></Program></Programs>')
        findings = [d for d in result['diagnostics'] if d['code'] == 'descriptive_text_ambiguous']
        self.assertEqual(len(findings), 2)
        self.assertTrue(all(d['source_id'] for d in findings))
        self.assertEqual(result['status'], 'partial')


if __name__ == '__main__':
    unittest.main()
