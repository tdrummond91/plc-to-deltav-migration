"""Stage 2 tests use invented XML and mocked filesystem publication."""
from __future__ import annotations

from contextlib import ExitStack
from io import BytesIO, StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from summarize_xml import StructureError, build_summary, parse_structure  # noqa: E402
from write_skeleton import create_skeleton, verify_skeleton, write_blank_xml  # noqa: E402


def summary(data: bytes) -> dict:
    return build_summary(parse_structure(BytesIO(data)))


def render(data: bytes) -> str:
    expected = summary(data)
    output = StringIO()
    write_blank_xml(BytesIO(data), output)
    result = output.getvalue()
    verify_skeleton(expected, summary(result.encode("utf-8")))
    return result


class SkeletonTests(unittest.TestCase):
    def test_every_repeated_element_and_order_survives(self) -> None:
        xml = b'<Root><Tag Name="one"/><Other/><Tag Name="two"/><Tag/></Root>'
        root = ET.fromstring(render(xml))
        self.assertEqual([child.tag for child in root], ["Tag", "Other", "Tag", "Tag"])
        self.assertEqual([child.attrib for child in root], [{"Name": ""}, {}, {"Name": ""}, {}])

    def test_optional_attributes_are_not_merged_across_records(self) -> None:
        root = ET.fromstring(render(b'<Root><Tag Name="A"/><Tag AliasFor="B"/></Root>'))
        self.assertEqual(root[0].attrib, {"Name": ""})
        self.assertEqual(root[1].attrib, {"AliasFor": ""})

    def test_all_source_values_are_removed(self) -> None:
        result = render(
            b'<?xml version="1.0"?><?PRIVATE instruction?>'
            b'<Root Name="PRIVATE_NAME"><!--PRIVATE_COMMENT-->'
            b'<Description>PRIVATE_DESCRIPTION</Description>'
            b'<Rung Number="123" Type="N"><Text><![CDATA[XIC(PRIVATE_TAG);]]></Text></Rung>'
            b'<Data DataType="DINT" Value="999"/><EncodedData>PRIVATE_PAYLOAD</EncodedData></Root>'
        )
        for value in ("PRIVATE", "XIC", "123", "999", "DINT"):
            self.assertNotIn(value, result)
        for element in ET.fromstring(result).iter():
            self.assertTrue(all(value == "" for value in element.attrib.values()))
            self.assertFalse((element.text or "").strip())
            self.assertFalse((element.tail or "").strip())
        self.assertIn('Number="" Type=""', result)
        self.assertIn("<![CDATA[]]>", result)

    def test_every_cdata_section_survives_in_position(self) -> None:
        result = render(b'<Root><![CDATA[first]]><Child/><![CDATA[]]><![CDATA[last]]></Root>')
        self.assertEqual(result.count("<![CDATA[]]>"), 3)
        self.assertLess(result.index("<![CDATA[]]>"), result.index("<Child>"))
        self.assertGreater(result.rindex("<![CDATA[]]>"), result.index("</Child>"))

    def test_mixed_content_and_tails_are_removed(self) -> None:
        result = render(b'<Root>BEFORE<Child>INNER</Child>AFTER</Root>')
        self.assertNotIn("BEFORE", result)
        self.assertNotIn("INNER", result)
        self.assertNotIn("AFTER", result)
        self.assertEqual(len(list(ET.fromstring(result).iter())), 2)

    def test_utf16_input_is_written_as_utf8_xml(self) -> None:
        source = '<?xml version="1.0" encoding="utf-16"?><Root Name="Québec"><Text>é</Text></Root>'
        result = render(source.encode("utf-16"))
        self.assertIn('encoding="utf-8"', result)
        self.assertNotIn("Québec", result)

    def test_large_repeated_nesting_is_not_collapsed(self) -> None:
        result = render(b"<Root>" + b'<Tag Name="same"><Data/></Tag>' * 700 + b"</Root>")
        root = ET.fromstring(result)
        self.assertEqual(len(root), 700)
        self.assertEqual(len(list(root.iter())), 1401)

    def test_namespace_names_match_stage1_without_private_uris(self) -> None:
        result = render(b'<x:Root xmlns:x="urn:PRIVATE" x:Name="secret"><x:Child/></x:Root>')
        self.assertNotIn("PRIVATE", result)
        self.assertNotIn("xmlns", result)
        self.assertEqual(ET.fromstring(result).attrib, {"Name": ""})

    def test_namespace_collisions_are_rejected_by_preflight(self) -> None:
        with self.assertRaises(StructureError):
            render(b'<Root xmlns:a="urn:a" xmlns:b="urn:b"><a:Tag/><b:Tag/></Root>')

    def test_dtds_are_rejected(self) -> None:
        with self.assertRaises(StructureError):
            render(b'<!DOCTYPE Root [<!ENTITY secret "PRIVATE">]><Root>&secret;</Root>')

    def test_verifier_rejects_lost_repetitions(self) -> None:
        with self.assertRaises(StructureError):
            verify_skeleton(summary(b"<Root><Tag/><Tag/></Root>"), summary(b"<Root><Tag/></Root>"))

    def test_verifier_rejects_lost_attribute_or_cdata(self) -> None:
        original = summary(b'<Root Name="private"><![CDATA[private]]></Root>')
        for altered in (b'<Root><![CDATA[]]></Root>', b'<Root Name=""/>'):
            with self.subTest(altered=altered):
                with self.assertRaises(StructureError):
                    verify_skeleton(original, summary(altered))

    def test_verifier_rejects_retained_text(self) -> None:
        with self.assertRaises(StructureError):
            verify_skeleton(summary(b"<Root>secret</Root>"), summary(b"<Root>secret</Root>"))

    def test_same_file_is_rejected(self) -> None:
        with self.assertRaises(StructureError):
            create_skeleton(Path(__file__), Path(__file__))

    def test_malformed_input_does_not_create_output(self) -> None:
        with patch("pathlib.Path.open", return_value=BytesIO(b"<Root>")):
            with patch("write_skeleton.tempfile.NamedTemporaryFile") as temporary:
                with self.assertRaises(StructureError):
                    create_skeleton(Path("invented.L5X"), Path("invented.XML"))
        temporary.assert_not_called()

    def test_publication_follows_validation_and_failure_cleans_up(self) -> None:
        class OpenBuffer(StringIO):
            name = "mock-skeleton.tmp"
            def close(self) -> None:
                pass

        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt):
                buffer = OpenBuffer()
                original = b'<Root><Tag Name="secret"/><Tag Name="other"/></Root>'
                def fake_open(path: Path, *_args: object, **_kwargs: object) -> BytesIO:
                    if path.name == "invented.L5X":
                        return BytesIO(original)
                    content = "<Root/>" if corrupt else buffer.getvalue()
                    return BytesIO(content.encode("utf-8"))

                with ExitStack() as context:
                    context.enter_context(patch("pathlib.Path.open", fake_open))
                    context.enter_context(patch("pathlib.Path.mkdir"))
                    context.enter_context(patch(
                        "pathlib.Path.exists", lambda path: path.name == "mock-skeleton.tmp"
                    ))
                    cleanup = context.enter_context(patch("pathlib.Path.unlink"))
                    context.enter_context(patch(
                        "write_skeleton.tempfile.NamedTemporaryFile", return_value=buffer
                    ))
                    publish = context.enter_context(patch("write_skeleton.os.replace"))
                    if corrupt:
                        with self.assertRaises(StructureError):
                            create_skeleton(Path("invented.L5X"), Path("invented.XML"))
                        publish.assert_not_called()
                    else:
                        result = create_skeleton(Path("invented.L5X"), Path("invented.XML"))
                        self.assertEqual(result["element_occurrences"], 3)
                        publish.assert_called_once()
                    cleanup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
