"""Stage 1 tests use in-memory XML and mocked output writes only."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

# Permit direct execution and unittest discovery from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from summarize_xml import (  # noqa: E402
    MAX_DEPTH, StructureError, build_summary, create_summary, parse_structure,
)


def report_for(xml: str) -> dict[str, object]:
    return build_summary(parse_structure(BytesIO(xml.encode("utf-8"))))


class StructureSummaryTests(unittest.TestCase):
    def test_complete_totals_and_nested_counts(self) -> None:
        result = report_for(
            '<Root Name="SECRET"><Tags>'
            '<Tag Name="A"><Data Value="1"/></Tag>'
            '<Tag Name="B" Type="X"><Data Value="2"/></Tag>'
            '</Tags><Other><Data Value="3"/></Other></Root>'
        )
        self.assertEqual(result["count_scope"], "complete_input")
        self.assertEqual(result["totals"], {
            "element_occurrences": 8, "attribute_occurrences": 7,
            "distinct_element_paths": 6, "elements_with_text": 0,
            "elements_with_cdata": 0, "max_depth": 4,
        })
        self.assertEqual(result["counts_by_element_name"]["Data"], 3)
        self.assertEqual(result["counts_by_attribute_name"]["Name"], 3)
        tag = result["root"]["children"][0]["children"][0]
        self.assertEqual(tag["count"], 2)
        self.assertEqual(tag["attributes"], {
            "Name": {"count": 2}, "Type": {"count": 1},
        })
        self.assertEqual(tag["children"][0]["count"], 2)
        other = result["root"]["children"][1]
        self.assertEqual(other["children"][0]["count"], 1)

    def test_repeated_nesting_keeps_full_source_count(self) -> None:
        result = report_for(
            "<Root><Tags>" + '<Tag Name="SECRET"><Data/></Tag>' * 700
            + "</Tags></Root>"
        )
        tag = result["root"]["children"][0]["children"][0]
        self.assertEqual(tag["count"], 700)
        self.assertEqual(tag["children"][0]["count"], 700)
        self.assertEqual(len(result["root"]["children"][0]["children"]), 1)
        self.assertEqual(result["totals"]["element_occurrences"], 1402)

    def test_attribute_counts_are_presence_not_unique_values(self) -> None:
        result = report_for('<Root><Tag Name="same"/><Tag Name="same"/><Tag/></Root>')
        tag = result["root"]["children"][0]
        self.assertEqual(tag["count"], 3)
        self.assertEqual(tag["attributes"]["Name"]["count"], 2)

    def test_values_comments_processing_instructions_never_enter_json(self) -> None:
        result = report_for(
            '<?xml version="1.0"?><?private SECRET_PI?>'
            '<Root Name="SECRET_NAME"><!--SECRET_COMMENT-->'
            '<Description>SECRET_DESCRIPTION</Description>'
            '<Text><![CDATA[SECRET_LOGIC <PRIVATE_FAKE_XML/>]]></Text>'
            '</Root>'
        )
        serialized = json.dumps(result)
        self.assertNotIn("SECRET", serialized)
        self.assertNotIn("PRIVATE_FAKE_XML", serialized)
        self.assertNotIn("source_path", serialized)
        self.assertNotIn("source_hash", serialized)

    def test_text_and_cdata_count_once_per_source_element(self) -> None:
        result = report_for(
            '<Root><Text>one<![CDATA[two]]><![CDATA[]]></Text>'
            '<Text><![CDATA[]]></Text><Text>  </Text></Root>'
        )
        text = result["root"]["children"][0]
        self.assertEqual(text["count"], 3)
        self.assertEqual(text["elements_with_text"], 1)
        self.assertEqual(text["elements_with_cdata"], 2)

    def test_chunk_boundaries_do_not_duplicate_text_counts(self) -> None:
        class TinyChunks(BytesIO):
            def read(self, size: int = -1) -> bytes:
                return super().read(2 if size < 0 else min(size, 2))
        stream = TinyChunks("<Root><Text>Québec test</Text></Root>".encode())
        result = build_summary(parse_structure(stream))
        self.assertEqual(result["totals"]["elements_with_text"], 1)

    def test_same_element_at_different_paths_is_separate(self) -> None:
        result = report_for(
            '<Root><Left><Tag Name="A"/></Left>'
            '<Right><Tag AliasFor="B"/><Tag AliasFor="C"/></Right></Root>'
        )
        left, right = result["root"]["children"]
        self.assertEqual(left["children"][0]["count"], 1)
        self.assertEqual(right["children"][0]["count"], 2)
        self.assertEqual(result["counts_by_element_name"]["Tag"], 3)

    def test_first_seen_child_order_is_retained(self) -> None:
        result = report_for("<Root><Z/><A/><Z/></Root>")
        self.assertEqual([c["element"] for c in result["root"]["children"]], ["Z", "A"])

    def test_empty_document_is_rejected(self) -> None:
        with self.assertRaises(StructureError):
            report_for("")

    def test_namespace_uris_are_not_exported(self) -> None:
        result = report_for(
            '<private:Root xmlns:private="urn:SECRET_URI" private:Name="SECRET">'
            '<private:Child/></private:Root>'
        )
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertEqual(result["root"]["element"], "Root")
        self.assertEqual(result["totals"]["attribute_occurrences"], 1)

    def test_namespace_element_collisions_are_rejected(self) -> None:
        with self.assertRaises(StructureError):
            report_for('<Root xmlns:a="urn:a" xmlns:b="urn:b"><a:Tag/><b:Tag/></Root>')

    def test_namespace_attribute_collisions_are_rejected(self) -> None:
        with self.assertRaises(StructureError):
            report_for('<Root xmlns:a="urn:a" xmlns:b="urn:b" a:Name="1" b:Name="2"/>')

    def test_dtd_and_entities_are_rejected(self) -> None:
        for source in (
            '<!DOCTYPE Root [<!ENTITY x "SECRET">]><Root>&x;</Root>',
            '<!DOCTYPE Root SYSTEM "file:///SECRET"><Root/>',
        ):
            with self.subTest(source=source):
                with self.assertRaises(StructureError):
                    report_for(source)

    def test_parse_error_does_not_echo_source(self) -> None:
        with self.assertRaises(StructureError) as caught:
            report_for("<Root><SECRET_BAD_ELEMENT></Root>")
        self.assertNotIn("SECRET", str(caught.exception))
        self.assertIn("line", str(caught.exception))

    def test_excessive_depth_is_rejected(self) -> None:
        with self.assertRaises(StructureError):
            report_for("<Node>" * (MAX_DEPTH + 1) + "</Node>" * (MAX_DEPTH + 1))

    def test_distinct_path_limit_is_enforced(self) -> None:
        with patch("summarize_xml.MAX_SHAPES", 2):
            with self.assertRaises(StructureError):
                report_for("<Root><First/><Second/></Root>")

    def test_pipeline_prepares_json_without_real_writes(self) -> None:
        with patch("pathlib.Path.open", return_value=BytesIO(b"<Root><Tag/><Tag/></Root>")):
            with patch("summarize_xml._write_atomic") as publish:
                output = create_summary(Path("invented.L5X"), Path("invented.json"))
        publish.assert_called_once()
        self.assertEqual(publish.call_args.args[0], output)
        self.assertEqual(
            json.loads(publish.call_args.args[1])["counts_by_element_name"]["Tag"], 2
        )

    def test_malformed_input_does_not_publish(self) -> None:
        with patch("pathlib.Path.open", return_value=BytesIO(b"<Root><BAD></Root>")):
            with patch("summarize_xml._write_atomic") as publish:
                with self.assertRaises(StructureError):
                    create_summary(Path("invented.L5X"), Path("invented.json"))
        publish.assert_not_called()

    def test_source_cannot_be_overwritten(self) -> None:
        with patch("summarize_xml._write_atomic") as publish:
            with self.assertRaises(StructureError):
                create_summary(Path(__file__), Path(__file__))
        publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
