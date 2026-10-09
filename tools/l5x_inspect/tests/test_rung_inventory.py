"""Invented XML and mocked filesystem writes only."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from summarize_xml import StructureError  # noqa: E402
from rungs.inventory import create_inventory, inventory_stream  # noqa: E402


def document(*texts: str) -> bytes:
    rungs = "".join(
        f'<Rung Number="{number}" Type="N"><Text><![CDATA[{text}]]></Text></Rung>'
        for number, text in enumerate(texts)
    )
    return (
        '<Root><Programs><Program Name="PRIVATE_PROGRAM"><Routines>'
        '<Routine Name="PRIVATE_ROUTINE" Type="RLL"><RLLContent>' + rungs
        + '</RLLContent></Routine></Routines></Program></Programs></Root>'
    ).encode()


def inventory(*texts: str, top: int = 5) -> dict:
    return inventory_stream(BytesIO(document(*texts)), top)


class RungInventoryTests(unittest.TestCase):
    def test_complete_counts_and_pattern_occurrence_links(self) -> None:
        result = inventory("XIC(a)OTE(b);", "XIC(x)OTE(y);", "[XIC(a),XIO(b)]OTE(c);")
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["coverage"]["parsed_rungs"], 3)
        self.assertEqual(result["coverage"]["distinct_shapes"], 2)
        self.assertEqual(result["instruction_counts"], {"XIC": 3, "OTE": 3, "XIO": 1})
        self.assertEqual(result["patterns"][0]["count"], 2)
        self.assertEqual(result["patterns"][0]["rung_ids"], ["rung_000001", "rung_000002"])
        self.assertEqual(result["rungs"][1]["pattern_id"], "pattern_00001")
        self.assertEqual(result["rungs"][1]["number"], "1")
        self.assertEqual(result["rungs"][1]["type"], "N")
        self.assertTrue(result["rungs"][1]["locator"].endswith("/Rung[2]"))

    def test_failed_rungs_are_accounted_for_and_excluded_from_totals(self) -> None:
        result = inventory("XIC(a)OTE(b);", "PRIVATE_BAD(a")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["coverage"]["parsed_rungs"], 1)
        self.assertEqual(result["coverage"]["unparsed_rungs"], 1)
        self.assertEqual(result["totals_for_parsed_rungs"]["instruction_calls"], 2)
        self.assertEqual(result["rungs"][1]["status"], "unparsed")
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_non_ladder_text_and_rungs_are_not_parsed(self) -> None:
        xml = b'<Root><SFCContent><Branch/><Text>PRIVATE</Text><Rung/></SFCContent><STContent><Line>PRIVATE</Line></STContent></Root>'
        result = inventory_stream(BytesIO(xml))
        self.assertEqual(result["coverage"]["ladder_rungs"], 0)
        self.assertEqual(result["coverage"]["ignored_non_ladder_rungs"], 1)
        self.assertEqual(result["patterns"], [])

    def test_aoi_and_program_rungs_are_both_counted(self) -> None:
        xml = b'<Root><AddOnInstructionDefinitions><AddOnInstructionDefinition><Routines><Routine><RLLContent><Rung Number="0" Type="N"><Text>NOP();</Text></Rung></RLLContent></Routine></Routines></AddOnInstructionDefinition></AddOnInstructionDefinitions><Programs><Program><Routines><Routine><RLLContent><Rung Number="0" Type="N"><Text>NOP();</Text></Rung></RLLContent></Routine></Routines></Program></Programs></Root>'
        result = inventory_stream(BytesIO(xml))
        self.assertEqual(result["coverage"]["parsed_rungs"], 2)
        self.assertNotEqual(result["rungs"][0]["locator"], result["rungs"][1]["locator"])
        self.assertEqual(result["patterns"][0]["count"], 2)

    def test_missing_multiple_and_nested_text_are_explicit(self) -> None:
        xml = b'<Root><RLLContent><Rung/><Rung><Text>NOP();</Text><Text>NOP();</Text></Rung><Rung><Text><Private>NOP();</Private></Text></Rung></RLLContent></Root>'
        result = inventory_stream(BytesIO(xml))
        self.assertEqual(result["coverage"]["parse_error_counts"], {
            "missing_text": 1, "multiple_text_elements": 1, "nested_xml_in_rung_text": 1,
        })

    def test_top_rankings_select_distinct_shapes_and_tall_wide_examples(self) -> None:
        result = inventory(
            "XIC(a)OTE(b);", "XIC(x)OTE(y);",
            "[XIC(a),XIO(b),XIC(c)]OTE(d);",
            "XIC(a)XIC(b)XIC(c)XIC(d)OTE(e);", top=1,
        )
        self.assertEqual(result["rankings"]["tallest"], ["pattern_00002"])
        self.assertEqual(result["rankings"]["widest"], ["pattern_00003"])
        self.assertEqual(result["rankings"]["most_frequent"], ["pattern_00001"])
        self.assertEqual(len(result["samples"]), 3)

    def test_ranking_ties_use_first_source_occurrence(self) -> None:
        result = inventory("XIC(a);", "XIO(b);", top=1)
        self.assertEqual(result["rankings"]["widest"], ["pattern_00001"])

    def test_unknown_opcodes_are_masked_without_preventing_structural_counts(self) -> None:
        result = inventory("PrivateMachineLogic(a,123);", "PrivateMachineLogic(b,456);", "OtherSecret(c);")
        self.assertEqual(result["coverage"]["unlisted_opcode_labels"], 2)
        self.assertEqual(result["coverage"]["parsed_rungs"], 3)
        self.assertEqual(result["instruction_counts"], {"UNLISTED_OP_0001": 2, "UNLISTED_OP_0002": 1})
        self.assertEqual(result["patterns"][0]["count"], 2)
        output = json.dumps(result)
        for value in ("PrivateMachineLogic", "OtherSecret", "PRIVATE", "123", "456"):
            self.assertNotIn(value, output)

    def test_numbers_and_approved_edit_types_are_retained_other_values_withheld(self) -> None:
        xml = b'<Root><RLLContent><Rung Number="007" Type="rN"><Text>NOP();</Text></Rung><Rung Number="PRIVATE" Type="PRIVATE"><Text>NOP();</Text></Rung></RLLContent></Root>'
        result = inventory_stream(BytesIO(xml))
        self.assertEqual(result["rungs"][0]["number"], "007")
        self.assertEqual(result["rungs"][0]["type"], "rN")
        self.assertEqual(result["rungs"][1]["number"], "<withheld>")
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_no_original_names_comments_constants_or_operand_fragments(self) -> None:
        xml = document("CPT(PRIVATE_OUT,(PRIVATE_A + 487321) / SIN(PRIVATE_B));")
        xml = xml.replace(b"<Text>", b"<Comment>PRIVATE_COMMENT</Comment><Text>")
        result = inventory_stream(BytesIO(xml))
        output = json.dumps(result)
        self.assertNotIn("PRIVATE", output)
        self.assertNotIn("487321", output)
        sample = result["samples"][0]["neutral_text"]
        self.assertEqual(sample, "CPT(ARG_001,ARG_002);")

    def test_empty_semicolon_is_parsed_blank_string_is_not(self) -> None:
        result = inventory(";", "")
        self.assertEqual(result["coverage"]["parsed_rungs_without_instructions"], 1)
        self.assertEqual(result["coverage"]["unparsed_rungs"], 1)

    def test_input_and_top_limits(self) -> None:
        for top in (0, 21):
            with self.assertRaises(StructureError):
                inventory("NOP();", top=top)
        with patch("rungs.inventory.MAX_TEXT", 3):
            result = inventory("NOP();")
        self.assertEqual(result["coverage"]["parse_error_counts"], {"text_limit": 1})

    def test_dtd_and_malformed_xml_rejected(self) -> None:
        for data in (b'<!DOCTYPE Root [<!ENTITY x "PRIVATE">]><Root/>', b"<Root><PRIVATE></Root>"):
            with self.subTest(data=data):
                with self.assertRaises(StructureError) as caught:
                    inventory_stream(BytesIO(data))
                self.assertNotIn("PRIVATE", str(caught.exception))

    def test_partial_report_is_published_without_raw_errors(self) -> None:
        with patch("pathlib.Path.open", return_value=BytesIO(document("PRIVATE_BAD"))):
            with patch("rungs.inventory._write_atomic") as publish:
                result = create_inventory(Path("invented.L5X"), Path("invented.json"))
        publish.assert_called_once()
        self.assertEqual(result["status"], "partial")
        self.assertNotIn("PRIVATE", publish.call_args.args[1])
        self.assertEqual(json.loads(publish.call_args.args[1]), result)

    def test_fatal_error_does_not_publish(self) -> None:
        with patch("pathlib.Path.open", return_value=BytesIO(b"<Root>")):
            with patch("rungs.inventory._write_atomic") as publish:
                with self.assertRaises(StructureError):
                    create_inventory(Path("invented.L5X"), Path("invented.json"))
        publish.assert_not_called()

    def test_same_file_is_rejected(self) -> None:
        with self.assertRaises(StructureError):
            create_inventory(Path(__file__), Path(__file__))


if __name__ == "__main__":
    unittest.main()
