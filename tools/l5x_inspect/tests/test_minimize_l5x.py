from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dummy.build import build_fixture, create_fixture
from rungs.inventory import inventory_stream
from summarize_xml import StructureError

PREFIX = '<RSLogix5000Content><Controller Name="SECRET_CONTROLLER">'
SUFFIX = '</Controller></RSLogix5000Content>'


def document(body: str) -> bytes:
    return (PREFIX + body + SUFFIX).encode()


def rung(text: str, number: int = 0) -> str:
    return f'<Rung Number="{number}" Type="N"><Text><![CDATA[{text}]]></Text></Rung>'


def routine(body: str, name: str = "SECRET_ROUTINE") -> str:
    return f'<Programs><Program Name="SECRET_PROGRAM"><Routines><Routine Name="{name}" Type="RLL"><RLLContent>{body}</RLLContent></Routine></Routines></Program></Programs>'


def create(body: str, **kwargs) -> tuple[str, dict]:
    return build_fixture(BytesIO(document(body)), **kwargs)


class MinimizedFixtureTests(unittest.TestCase):
    def test_values_removed_and_technical_values_retained(self):
        xml, report = create('<Tags><Tag Name="SECRET_TAG" TagType="Base" DataType="BOOL"><Description><![CDATA[SECRET_DESCRIPTION]]></Description><Data Format="Decorated"><DataValue DataType="BOOL" Value="987654"/></Data></Tag></Tags>')
        public = xml + json.dumps(report)
        for secret in ("SECRET_CONTROLLER", "SECRET_TAG", "SECRET_DESCRIPTION", "987654"):
            self.assertNotIn(secret, public)
        root = ET.fromstring(xml)
        self.assertEqual(root.find(".//Tag").get("DataType"), "BOOL")
        self.assertEqual(root.find(".//Tag").get("TagType"), "Base")
        self.assertIn(root.find(".//DataValue").get("Value"), {"0", "1"})

    def test_whole_identifiers_share_labels(self):
        xml, _ = create('<Tags><Tag Name="SECRET_SAME"/><Tag Name="SECRET_ALIAS" AliasFor="SECRET_SAME"/></Tags>')
        tags = ET.fromstring(xml).findall(".//Tag")
        self.assertEqual(tags[0].get("Name"), tags[1].get("AliasFor"))

    def test_unknown_datatypes_masked_consistently_and_represented(self):
        xml, report = create('<Tags><Tag Name="A" DataType="PRIVATE_UDT"/><Tag Name="B" DataType="PRIVATE_UDT"/><Tag Name="C" DataType="PRIVATE_OTHER"/></Tags>', per_variant=1)
        types = {t.get("DataType") for t in ET.fromstring(xml).findall(".//Tag")}
        self.assertEqual(len(types), 2)
        self.assertTrue(all(value.startswith("DUMMY_TYPE_") for value in types))
        self.assertNotIn("PRIVATE_UDT", xml + json.dumps(report))

    def test_rare_late_variant_preserved(self):
        body = '<Items>' + '<Item A="ordinary"/>' * 20 + '<Item A="ordinary" Rare="SECRET_VALUE"><Late/></Item></Items>'
        xml, report = create(body, per_variant=2)
        root = ET.fromstring(xml)
        self.assertEqual(len(root.findall(".//Item")), 3)
        self.assertIsNotNone(root.find(".//Late"))
        self.assertEqual(report["coverage"]["retained_paths"], report["coverage"]["source_paths"])

    def test_per_variant_limit_and_count_accounting(self):
        xml, report = create('<Items>' + '<Item A="ordinary"/>' * 20 + '</Items>', per_variant=3)
        self.assertEqual(len(ET.fromstring(xml).findall(".//Item")), 3)
        for row in report["paths"]:
            for kind in ("elements", "attributes", "text_values"):
                self.assertEqual(row[f"source_{kind}"], row[f"retained_{kind}"] + row[f"omitted_{kind}"])
        self.assertEqual(report["coverage"]["omitted_elements"], 17)

    def test_consecutive_runs_keep_original_order(self):
        xml, _ = create('<Items>' + '<A/>' * 10 + '<B/>' + '<A/>' * 10 + '</Items>', per_variant=1)
        self.assertEqual([e.tag for e in ET.fromstring(xml).find(".//Items")], ["A", "B", "A"])

    def test_ranked_tall_and_wide_rungs_preserved(self):
        body = rung("XIC(SECRET_A)OTE(SECRET_B);", 0) * 10
        body += rung("[XIC(A),XIC(B),XIC(C),XIC(D)]OTE(E);", 10)
        body += rung("XIC(A)XIC(B)XIC(C)XIC(D)OTE(E);", 11)
        xml, report = create(routine(body), per_variant=1, top=1)
        numbers = {e.get("Number") for e in ET.fromstring(xml).findall(".//Rung")}
        self.assertTrue({"10", "11"}.issubset(numbers))
        inv = inventory_stream(BytesIO(xml.encode()))
        self.assertEqual(inv["maxima_for_parsed_rungs"]["height_lanes"], 4)
        self.assertEqual(inv["maxima_for_parsed_rungs"]["width_instructions"], 5)
        self.assertNotIn("SECRET_A", xml + json.dumps(report))

    def test_unlisted_opcode_is_masked_and_forced_into_sample(self):
        body = rung("XIC(A)OTE(B);") * 10 + rung("SECRET_AOI(SECRET_OPERAND,123456);", 30)
        xml, report = create(routine(body), per_variant=1, top=1)
        self.assertIn("UNLISTED_OP_0001(", xml)
        self.assertNotIn("SECRET_AOI", xml + json.dumps(report))
        self.assertNotIn("SECRET_OPERAND", xml)
        self.assertNotIn("123456", xml)
        self.assertIn("UNLISTED_OP_0001", report["selection"]["instruction_labels_represented"])

    def test_selected_rungs_keep_all_children(self):
        xml, _ = create(routine('<Rung Number="7" Type="N"><Comment><![CDATA[SECRET_COMMENT]]></Comment><Text><![CDATA[XIC(A)OTE(B);]]></Text></Rung>'))
        self.assertIsNotNone(ET.fromstring(xml).find(".//Rung/Comment"))
        self.assertNotIn("SECRET_COMMENT", xml)
        self.assertIn('Number="7"', xml)
        self.assertIn('Type="N"', xml)

    def test_rung_metric_equivalence_for_selected_records(self):
        body = rung("XIC(a)[XIC(b),[XIO(c),XIC(d)]XIC(e)]OTE(f);", 5)
        xml, report = create(routine(body))
        actual = inventory_stream(BytesIO(xml.encode()))
        self.assertEqual(actual["rungs"][0]["metrics"], report["rungs"][0]["metrics"])

    def test_aliases_in_separate_rungs_do_not_claim_global_identity(self):
        xml, report = create(routine(rung("XIC(A)OTE(B);") + rung("XIC(C)OTE(D);", 1)))
        texts = [t.text for t in ET.fromstring(xml).findall(".//Rung/Text")]
        self.assertEqual(texts[0], texts[1])
        self.assertIn("separate per rung", report["policies"]["identifiers"])

    def test_payload_and_st_text_are_explicitly_replaced(self):
        xml, report = create('<Tags><Tag><Data Format="L5K"><![CDATA[SECRET_PAYLOAD]]></Data></Tag></Tags><Routine Type="SFC"><SFCContent><Transition><Condition><STContent><Line Number="1"><![CDATA[SECRET_EXPRESSION]]></Line></STContent></Condition></Transition></SFCContent></Routine>')
        self.assertIn("DUMMY_SERIALIZED_DATA", xml)
        self.assertIn("DUMMY_ST_TEXT", xml)
        self.assertNotIn("SECRET_PAYLOAD", xml + json.dumps(report))
        self.assertNotIn("SECRET_EXPRESSION", xml)
        self.assertEqual(report["unsupported_content"]["opaque_payload_replaced"], 1)
        self.assertEqual(report["unsupported_content"]["structured_text_replaced"], 1)

    def test_mixed_content_replacement_is_reported(self):
        xml, report = create('<Extra>SECRET_BEFORE<Inner/>SECRET_AFTER</Extra>')
        self.assertNotIn("SECRET_BEFORE", xml)
        self.assertEqual(report["unsupported_content"]["mixed_text_replaced"], 1)

    def test_empty_cdata_is_preserved(self):
        xml, report = create('<Description><![CDATA[]]></Description>')
        self.assertIn("<![CDATA[]]>", xml)
        self.assertEqual(report["text_actions"]["empty_preserved"], 1)

    def test_comments_pis_and_namespace_uri_not_exported(self):
        xml, report = create('<!--SECRET_COMMENT--><?private SECRET_PI?><x:Extra xmlns:x="SECRET_URI" x:Attr="SECRET_ATTR"/>')
        self.assertNotIn("SECRET", xml + json.dumps(report))
        self.assertEqual(report["coverage"]["comments_ignored"], 1)
        self.assertEqual(report["coverage"]["processing_instructions_ignored"], 1)

    def test_ordinal_source_output_mapping(self):
        xml, report = create('<Items>' + '<Item/>' * 10 + '<Item Rare="true"/>' + '</Items>', per_variant=1)
        links = report["occurrence_map"]
        rare = next(r for r in links if r["source_locator"].endswith("/Item[11]"))
        self.assertTrue(rare["dummy_locator"].endswith("/Item[2]"))
        self.assertEqual(len(links), report["coverage"]["retained_elements"])
        self.assertEqual(len({r["dummy_locator"] for r in links}), len(links))

    def test_reproducible_seed_and_generated_output_hash(self):
        body = '<Value Number="837263" Enabled="true">438234</Value>'
        first, report = create(body, seed=7)
        second, _ = create(body, seed=7)
        self.assertEqual(first, second)
        self.assertEqual(report["output_sha256"], sha256(first.encode()).hexdigest())

    def test_bad_rung_or_metadata_blocks_publication(self):
        for body in (rung("BROKEN"), '<Rung><Text><![CDATA[XIC(A);]]></Text></Rung>'):
            with self.subTest(body=body), self.assertRaises(StructureError):
                create(routine(body))

    def test_malformed_xml_dtd_and_namespace_collision_rejected(self):
        for raw in (b"<broken>", b'<!DOCTYPE X [<!ENTITY a "SECRET">]><X>&a;</X>',
                    b'<Root xmlns:a="a" xmlns:b="b"><a:X/><b:X/></Root>'):
            with self.subTest(raw=raw), self.assertRaises(StructureError):
                build_fixture(BytesIO(raw))

    def test_sampling_bounds(self):
        for number in (0, -1, 21):
            with self.subTest(number=number), self.assertRaises(StructureError):
                create("<Item/>", per_variant=number)

    def test_successful_publication_is_mocked(self):
        with patch("pathlib.Path.open", return_value=BytesIO(document("<Items><Item/></Items>"))), \
             patch("dummy.build._write_atomic") as write:
            report = create_fixture(Path("invented-input.L5X"), Path("invented-output"))
        self.assertEqual(write.call_count, 2)
        self.assertEqual(report["status"], "structural_fixture_verified")

    def test_fatal_input_does_not_publish(self):
        with patch("pathlib.Path.open", return_value=BytesIO(b"<broken>")), \
             patch("dummy.build._write_atomic") as write:
            with self.assertRaises(StructureError):
                create_fixture(Path("invented-input.L5X"), Path("invented-output"))
        write.assert_not_called()

    def test_source_output_path_collision_rejected(self):
        with self.assertRaises(StructureError):
            create_fixture(Path("invented-output/controller_demo.L5X"), Path("invented-output"))

    def test_program_and_aoi_rungs_both_represented(self):
        body = routine(rung("XIC(A)OTE(B);"))
        body += '<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="SECRET_AOI"><Routines><Routine Type="RLL"><RLLContent>' + rung("XIO(C)OTU(D);") + '</RLLContent></Routine></Routines></AddOnInstructionDefinition></AddOnInstructionDefinitions>'
        xml, report = create(body, per_variant=1)
        self.assertEqual(report["coverage"]["retained_ladder_rungs"], 2)
        self.assertIsNotNone(ET.fromstring(xml).find(".//AddOnInstructionDefinition/Routines/Routine/RLLContent/Rung"))


if __name__ == "__main__":
    unittest.main()
