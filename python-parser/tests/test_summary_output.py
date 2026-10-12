"""No-clobber publication tests use invented summaries and temporary files."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.summary_output import SummaryOutputError, publish_summary


class SummaryOutputTests(unittest.TestCase):
    def test_new_utf8_json_is_published_and_temporary_file_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.L5X"
            source.write_bytes(b"invented input")
            output = root / "output folder" / "summary.json"
            rendered = '{"example": "caf\u00e9"}\n'
            publish_summary(output, rendered, input_path=source)
            self.assertEqual(output.read_bytes(), rendered.encode("utf-8"))
            self.assertEqual(source.read_bytes(), b"invented input")
            self.assertEqual(list(output.parent.iterdir()), [output])

    def test_existing_output_and_input_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            source.write_bytes(b"invented source")
            existing = root / "existing.json"
            existing.write_bytes(b"previous summary")
            for output in (source, existing):
                with self.subTest(output=output.name), self.assertRaises(SummaryOutputError):
                    publish_summary(output, "{}\n", input_path=source)
            self.assertEqual(source.read_bytes(), b"invented source")
            self.assertEqual(existing.read_bytes(), b"previous summary")
            self.assertEqual(len(list(root.iterdir())), 2)

    def test_racing_writer_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "summary.json"

            def concurrent_link(_source: Path, destination: Path) -> None:
                destination.write_bytes(b"another writer")
                raise FileExistsError("PRIVATE_SENTINEL")

            with patch("plc_workbench.summary_output.os.link", side_effect=concurrent_link):
                with self.assertRaises(SummaryOutputError) as caught:
                    publish_summary(output, "{}\n", input_path=root / "source.L5X")
            self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))
            self.assertEqual(output.read_bytes(), b"another writer")
            self.assertEqual(list(root.iterdir()), [output])

    def test_failed_flush_or_link_publishes_nothing_and_cleans_temporary_file(self) -> None:
        for failed_operation in ("os.fsync", "os.link"):
            with self.subTest(operation=failed_operation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with patch(f"plc_workbench.summary_output.{failed_operation}", side_effect=OSError("PRIVATE_SENTINEL")):
                    with self.assertRaises(SummaryOutputError) as caught:
                        publish_summary(root / "summary.json", "{}\n", input_path=root / "source.L5X")
                self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))
                self.assertEqual(list(root.iterdir()), [])

    def test_extension_and_checkout_boundary_are_checked_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(SummaryOutputError):
                publish_summary(root / "missing" / "summary.txt", "{}\n", input_path=root / "source.L5X")
            self.assertEqual(list(root.iterdir()), [])
        checkout = Path(__file__).resolve().parents[2]
        with self.assertRaises(SummaryOutputError):
            publish_summary(checkout / "public" / "summary-must-not-exist.json", "{}\n", input_path=checkout / "source.L5X")

    def test_symlink_destination_is_rejected_before_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(Path, "is_symlink", return_value=True):
                with self.assertRaises(SummaryOutputError):
                    publish_summary(root / "summary.json", "{}\n", input_path=root / "source.L5X")
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
