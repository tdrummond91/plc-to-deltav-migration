"""Value profiling tests use only invented, in-memory source XML."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from summarize_xml import StructureError  # noqa: E402
from profile_values import create_profile, lexical_kind, profile_stream  # noqa: E402


def profile(xml: str) -> dict:
    return profile_stream(BytesIO(xml.encode("utf-8")))


def row(report: dict, path: str) -> dict:
    return next(item for item in report["paths"] if item["path"] == path)


class ValueProfileTests(unittest.TestCase):
    def test_occurrences_uniques_and_missing_attributes(self) -> None:
        report = profile('<Root><Tag Name="same"/><Tag Name="same"/><Tag Name="other"/><Tag/></Root>')
        entry = row(report, "/Root/Tag")["attributes"]["Name"]
        self.assertEqual(entry["occurrences"], 3)
        self.assertEqual(entry["unique_value_count"], 2)
        self.assertEqual(entry["missing_on_elements"], 1)
        self.assertEqual(entry["withheld_occurrences"], 3)
        self.assertEqual(entry["technical_value_counts"], {})
        self.assertEqual(report["coverage"]["attribute_occurrences_profiled"], 3)

    def test_same_name_at_different_paths_is_independent(self) -> None:
        report = profile('<Root><Left Name="a"/><Right Name="a"/><Right Name="b"/></Root>')
        self.assertEqual(row(report, "/Root/Left")["attributes"]["Name"]["unique_value_count"], 1)
        self.assertEqual(row(report, "/Root/Right")["attributes"]["Name"]["unique_value_count"], 2)

    def test_literal_types_do_not_infer_plc_type(self) -> None:
        report = profile('<Root><DataValue DataType="BOOL" Value="0"/></Root>')
        value = row(report, "/Root/DataValue")["attributes"]["Value"]
        self.assertEqual(value["lexical_type_counts"], {"integer_literal": 1})
        self.assertEqual(value["declared_datatypes_on_same_element"], {"BOOL": 1})
        self.assertEqual(value["technical_value_counts"], {})

    def test_no_inherited_datatype_claim(self) -> None:
        report = profile('<Root><Array DataType="BOOL"><Element Value="0"/></Array></Root>')
        value = row(report, "/Root/Array/Element")["attributes"]["Value"]
        self.assertEqual(value["declared_datatypes_on_same_element"], {})

    def test_technical_types_allowed_custom_types_withheld(self) -> None:
        report = profile(
            '<Root><Tag DataType="DINT"/><Tag DataType="DINT"/>'
            '<Tag DataType="PRIVATE_UDT"/><Tag DataType="PRIVATE_UDT"/></Root>'
        )
        entry = row(report, "/Root/Tag")["attributes"]["DataType"]
        self.assertEqual(entry["technical_value_counts"], {"DINT": 2})
        self.assertEqual(entry["withheld_occurrences"], 2)
        self.assertEqual(entry["withheld_unique_value_count"], 1)
        self.assertNotIn("PRIVATE_UDT", json.dumps(report))

    def test_known_literal_is_not_published_in_a_name_field(self) -> None:
        report = profile('<Root><Tag Name="DINT"/></Root>')
        entry = row(report, "/Root/Tag")["attributes"]["Name"]
        self.assertEqual(entry["technical_value_counts"], {})
        self.assertEqual(entry["withheld_unique_value_count"], 1)
        self.assertNotIn('"DINT"', json.dumps(report))

    def test_arbitrary_values_dates_comments_and_logic_do_not_leak(self) -> None:
        report = profile(
            '<?PRIVATE target?><Root Name="PRIVATE_NAME" ExportDate="2099-12-31">'
            '<!--PRIVATE_COMMENT--><Description>PRIVATE_DESCRIPTION</Description>'
            '<RLLContent><Rung><Text><![CDATA[XIC(PRIVATE_TAG)OTE(PRIVATE_OUTPUT);]]></Text>'
            '</Rung></RLLContent><Data Format="PRIVATE_FORMAT">PRIVATE_PAYLOAD</Data>'
            '<DataValue DataType="PRIVATE_TYPE" Value="PRIVATE_VALUE"/></Root>'
        )
        serialized = json.dumps(report)
        for secret in ("PRIVATE", "2099-12-31", "XIC(", "OTE("):
            self.assertNotIn(secret, serialized)
        self.assertEqual(report["coverage"]["comments_ignored"], 1)
        self.assertEqual(report["coverage"]["processing_instructions_ignored"], 1)
        description = row(report, "/Root/Description")["text"]
        self.assertEqual(description["examples_origin"], "invented_not_source_samples")
        self.assertEqual(len(description["synthetic_examples"]), 3)

    def test_direct_text_cdata_and_whitespace_counts(self) -> None:
        report = profile('<Root>  <Text><![CDATA[]]></Text><Text>  </Text><Text>a<![CDATA[b]]></Text></Root>')
        self.assertIsNone(row(report, "/Root")["text"])
        text = row(report, "/Root/Text")["text"]
        self.assertEqual(text["occurrences"], 2)
        self.assertEqual(text["unique_value_count"], 2)
        self.assertEqual(text["lexical_type_counts"], {"empty": 1, "identifier_like": 1})

    def test_mixed_text_is_direct_not_descendant_text(self) -> None:
        report = profile('<Root>A<Child>B</Child>C</Root>')
        self.assertEqual(row(report, "/Root")["text"]["occurrences"], 1)
        self.assertEqual(row(report, "/Root/Child")["text"]["occurrences"], 1)
        self.assertEqual(report["coverage"]["text_values_profiled"], 2)

    def test_repeated_private_values_are_only_a_heuristic(self) -> None:
        report = profile('<Root>' + '<Tag Name="PRIVATE_A"/><Tag Name="PRIVATE_B"/>' * 3 + '</Root>')
        entry = row(report, "/Root/Tag")["attributes"]["Name"]
        self.assertTrue(entry["repeated_small_value_set"])
        self.assertEqual(entry["technical_value_counts"], {})
        self.assertNotIn("PRIVATE", json.dumps(report))

    def test_routine_types_and_gap_are_located_without_names(self) -> None:
        report = profile(
            '<Root><Programs><Program Name="PRIVATE_PROGRAM"><Routines>'
            '<Routine Name="PRIVATE_NORMAL" Type="RLL"><RLLContent/></Routine>'
            '<Routine Name="PRIVATE_EMPTY" Type="RLL"/>'
            '<Routine Name="PRIVATE_SFC" Type="SFC"><SFCContent><Transition>'
            '<Condition><STContent><Line Number="0">PRIVATE_ST</Line></STContent></Condition>'
            '</Transition></SFCContent></Routine>'
            '</Routines></Program></Programs></Root>'
        )
        coverage = report["routine_coverage"]
        self.assertEqual(coverage["count"], 3)
        self.assertEqual(coverage["type_counts"], {"RLL": 2, "SFC": 1})
        self.assertEqual(coverage["issue_counts"], {"no_recognized_content": 1})
        records = coverage["records"]
        self.assertEqual(records[1]["locator"], "/Root[1]/Programs[1]/Program[1]/Routines[1]/Routine[2]")
        self.assertEqual(records[1]["content_counts"], {})
        self.assertEqual(records[2]["content_counts"], {"SFCContent": 1})
        self.assertNotIn("PRIVATE", json.dumps(report))

    def test_routine_mismatch_multiple_and_protection_are_findings(self) -> None:
        report = profile(
            '<Root><Routine Type="RLL"><STContent/><STContent/><EncryptedContent/></Routine></Root>'
        )
        record = report["routine_coverage"]["records"][0]
        self.assertEqual(record["issues"], [
            "multiple_content_blocks", "type_content_mismatch", "protection_marker_present",
        ])

    def test_missing_and_unknown_routine_types_are_not_exported(self) -> None:
        report = profile('<Root><Routine/><Routine Type="PRIVATE_ROUTINE_KIND"/></Root>')
        self.assertEqual(report["routine_coverage"]["type_counts"], {"<missing>": 1, "<withheld>": 1})
        self.assertNotIn("PRIVATE", json.dumps(report))

    def test_format_counts_are_context_specific(self) -> None:
        report = profile('<Root><Data Format="Decorated"/><Data Format="PRIVATE"/><Other Format="Decorated"/></Root>')
        data = row(report, "/Root/Data")["attributes"]["Format"]
        other = row(report, "/Root/Other")["attributes"]["Format"]
        self.assertEqual(data["technical_value_counts"], {"Decorated": 1})
        self.assertEqual(data["withheld_occurrences"], 1)
        self.assertEqual(other["technical_value_counts"], {})


    def test_documented_special_data_formats_are_counted(self) -> None:
        report = profile(
            '<Root><Data Format="Message"/><Data Format="String"/>'
            '<Data Format="Alarm"/><Data Format="HMIBC"/></Root>'
        )
        self.assertEqual(
            row(report, "/Root/Data")["attributes"]["Format"]["technical_value_counts"],
            {"Message": 1, "String": 1, "Alarm": 1, "HMIBC": 1},
        )

    def test_lexical_kinds(self) -> None:
        examples = {
            "": "empty", "  ": "empty", "false": "boolean_literal",
            "True": "boolean_literal", "0": "integer_literal", "-25": "integer_literal",
            "16#00_AF": "radix_integer_literal", "2#0110": "radix_integer_literal",
            "2#29": "string", "0.5": "real_literal", "-1E+3": "real_literal",
            "2000-01-01": "date_like", "Thu Oct 08 13:40:00 2026": "date_like",
            "A_Name": "identifier_like", "texte abrégé": "string",
        }
        for value, expected in examples.items():
            with self.subTest(value=value):
                self.assertEqual(lexical_kind(value), expected)

    def test_namespaces_omitted_and_collisions_rejected(self) -> None:
        report = profile('<x:Root xmlns:x="urn:PRIVATE" x:Name="PRIVATE_VALUE"/>')
        self.assertEqual(report["paths"][0]["path"], "/Root")
        self.assertNotIn("PRIVATE", json.dumps(report))
        with self.assertRaises(StructureError):
            profile('<Root xmlns:a="urn:a" xmlns:b="urn:b"><a:X/><b:X/></Root>')

    def test_empty_and_malformed_input_errors_omit_payloads(self) -> None:
        for value in ("", "<Root><PRIVATE></Root>"):
            with self.subTest(value=value):
                with self.assertRaises(StructureError) as caught:
                    profile(value)
                self.assertNotIn("PRIVATE", str(caught.exception))

    def test_dtd_is_rejected(self) -> None:
        with self.assertRaises(StructureError):
            profile('<!DOCTYPE Root [<!ENTITY x "PRIVATE">]><Root>&x;</Root>')

    def test_memory_limits_stop_without_source_values(self) -> None:
        with patch("profile_values.MAX_DIRECT_TEXT", 3):
            with self.assertRaises(StructureError):
                profile("<Root>PRIVATE_LONG_TEXT</Root>")
        with patch("profile_values.MAX_UNIQUE_VALUES", 1):
            with self.assertRaises(StructureError):
                profile('<Root A="PRIVATE_ONE" B="PRIVATE_TWO"/>')

    def test_pipeline_writes_json_only_after_success(self) -> None:
        with patch("pathlib.Path.open", return_value=BytesIO(b'<Root Name="PRIVATE"/>')):
            with patch("profile_values._write_atomic") as publish:
                report = create_profile(Path("invented.L5X"), Path("invented.json"))
        publish.assert_called_once()
        self.assertEqual(json.loads(publish.call_args.args[1]), report)
        self.assertNotIn("PRIVATE", publish.call_args.args[1])

    def test_failure_does_not_publish(self) -> None:
        with patch("pathlib.Path.open", return_value=BytesIO(b'<Root><PRIVATE></Root>')):
            with patch("profile_values._write_atomic") as publish:
                with self.assertRaises(StructureError):
                    create_profile(Path("invented.L5X"), Path("invented.json"))
        publish.assert_not_called()

    def test_same_file_is_rejected(self) -> None:
        with patch("profile_values._write_atomic") as publish:
            with self.assertRaises(StructureError):
                create_profile(Path(__file__), Path(__file__))
        publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
