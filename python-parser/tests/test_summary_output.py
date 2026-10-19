"""No-clobber publication tests use invented summaries and temporary files."""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy
import json
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.summary import build_summary, render_summary
from plc_workbench.summary_output import SummaryOutputError, publish_summary

SUMMARY = render_summary(build_summary(analyze_snapshot(snapshot_from_bytes(
    b'<RSLogix5000Content><Controller Name="Invented"/></RSLogix5000Content>'))))


class SummaryOutputTests(unittest.TestCase):
    def test_new_utf8_json_is_published_and_temporary_file_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.L5X"
            source.write_bytes(b"invented input")
            output = root / "output folder" / "summary.json"
            rendered = SUMMARY
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
                    publish_summary(output, SUMMARY, input_path=source)
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
                    publish_summary(output, SUMMARY, input_path=root / "source.L5X")
            self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))
            self.assertEqual(output.read_bytes(), b"another writer")
            self.assertEqual(list(root.iterdir()), [output])

    def test_failed_flush_or_link_publishes_nothing_and_cleans_temporary_file(self) -> None:
        for failed_operation in ("os.fsync", "os.link"):
            with self.subTest(operation=failed_operation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with patch(f"plc_workbench.summary_output.{failed_operation}", side_effect=OSError("PRIVATE_SENTINEL")):
                    with self.assertRaises(SummaryOutputError) as caught:
                        publish_summary(root / "summary.json", SUMMARY, input_path=root / "source.L5X")
                self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))
                self.assertEqual(list(root.iterdir()), [])

    def test_extension_and_checkout_boundary_are_checked_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(SummaryOutputError):
                publish_summary(root / "missing" / "summary.txt", SUMMARY, input_path=root / "source.L5X")
            self.assertEqual(list(root.iterdir()), [])
        checkout = Path(__file__).resolve().parents[2]
        with self.assertRaises(SummaryOutputError):
            publish_summary(checkout / "public" / "summary-must-not-exist.json", SUMMARY, input_path=checkout / "source.L5X")

    def test_valid_aggregate_can_be_saved_directly_in_synced_inspection_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            output = root / 'public/inspection/summary.json'
            with patch('plc_workbench.summary_output._checkout_root', return_value=root):
                publish_summary(output, SUMMARY, input_path=root / 'confidential/input.L5X')
            self.assertEqual(output.read_text(encoding='utf-8'), SUMMARY)

    def test_arbitrary_data_and_oversized_reports_cannot_use_summary_publication(self) -> None:
        for rendered in ('{"PRIVATE_TAG":"PRIVATE_VALUE"}', SUMMARY + ' ' * 32768):
            with self.subTest(rendered=rendered[:20]), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                output = root / 'public/inspection/summary.json'
                with patch('plc_workbench.summary_output._checkout_root', return_value=root):
                    with self.assertRaises(SummaryOutputError) as caught:
                        publish_summary(output, rendered, input_path=root / 'confidential/input.L5X')
                self.assertNotIn('PRIVATE', str(caught.exception))
                self.assertFalse(output.exists())
                self.assertEqual(list(root.iterdir()), [])

    def test_symlink_destination_is_rejected_before_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(Path, "is_symlink", return_value=True):
                with self.assertRaises(SummaryOutputError):
                    publish_summary(root / "summary.json", SUMMARY, input_path=root / "source.L5X")
            self.assertEqual(list(root.iterdir()), [])

    def test_sfc_count_only_dispatch_revalidates_and_publishes_canonical_json(self) -> None:
        from test_sfc_summary import fixture_summary
        from plc_workbench.sfc_summary import render_sfc_summary

        summary = fixture_summary()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'sfc-summary.json'
            publish_summary(output, json.dumps(summary), input_path=root / 'source.L5X')
            self.assertEqual(output.read_text(encoding='utf-8'), render_sfc_summary(summary))
            forged = deepcopy(summary)
            forged['PRIVATE_VALUES'] = ['PRIVATE_TAG']
            with self.assertRaises(SummaryOutputError):
                publish_summary(root / 'rejected.json', json.dumps(forged), input_path=root / 'source.L5X')
            self.assertFalse((root / 'rejected.json').exists())


if __name__ == "__main__":
    unittest.main()
