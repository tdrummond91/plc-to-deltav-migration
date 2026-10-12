"""CLI contracts at stdout/stderr and private artifact boundaries."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.cli import main
from plc_workbench.reporting import render_text
from plc_workbench.source import analyze_snapshot, capture_snapshot, snapshot_from_bytes


SYNTHETIC = (
    '<RSLogix5000Content><Controller Name="Invented"><Programs>'
    '<Program Name="Example"><Routines><Routine Name="Main" Type="RLL">'
    '<RLLContent><Rung Number="0" Type="N"><Text>XIC(In)OTE(Out);</Text>'
    '</Rung></RLLContent></Routine></Routines></Program></Programs>'
    '</Controller></RSLogix5000Content>'
).encode()


def invoke(arguments: list[str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            code = main(arguments)
        except SystemExit as exc:
            code = int(exc.code)
    return code, stdout.getvalue(), stderr.getvalue()


class CliTests(unittest.TestCase):
    def test_help_and_usage_never_open_source_files(self) -> None:
        with patch("plc_workbench.source.capture_snapshot", side_effect=AssertionError("should not open")):
            for arguments in (["--help"], ["inspect", "--help"]):
                code, stdout, stderr = invoke(arguments)
                self.assertEqual(code, 0)
                self.assertIn("usage:", stdout)
                self.assertEqual(stderr, "")
            for arguments in ([], ["inspect"], ["inspect", "missing", "--format", "xml"]):
                code, stdout, stderr = invoke(arguments)
                self.assertEqual(code, 2)
                self.assertEqual(stdout, "")
                self.assertIn("usage:", stderr)

    def test_json_stdout_has_no_progress_and_no_implicit_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source with spaces.L5X"
            source.write_bytes(SYNTHETIC)
            code, stdout, stderr = invoke(["inspect", str(source), "--format", "json"])
            self.assertEqual(code, 0)
            self.assertEqual(stderr, "")
            report = json.loads(stdout)
            self.assertEqual(report["counts"]["rungs"], 1)
            self.assertEqual(report["instruction_counts"], {"XIC": 1, "OTE": 1})
            self.assertEqual(source.read_bytes(), SYNTHETIC)
            self.assertEqual(list(Path(directory).iterdir()), [source])

    def test_partial_report_is_printed_with_exit_three(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "partial.L5X"
            source.write_bytes(SYNTHETIC.replace(b"XIC(In)OTE(Out);", b"XIC(In)"))
            workspace = Path(directory) / "partial workspace"
            code, stdout, stderr = invoke([
                "inspect", str(source), "--format", "json", "--workspace", str(workspace),
            ])
            self.assertEqual(code, 3)
            self.assertEqual(json.loads(stdout)["status"], "partial")
            self.assertIn("Saved private run:", stderr)
            run, = workspace.iterdir()
            self.assertEqual(json.loads((run / "manifest.json").read_text())["status"], "partial")

    def test_exact_rung_selection_and_full_saved_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.L5X"
            source.write_bytes(SYNTHETIC)
            rung_id = analyze_snapshot(capture_snapshot(source)).to_dict()["rungs"][0]["id"]
            workspace = Path(directory) / "private workspace"
            code, stdout, stderr = invoke([
                "inspect", str(source), "--rung-id", rung_id,
                "--format", "json", "--workspace", str(workspace),
            ])
            self.assertEqual(code, 0)
            selected = json.loads(stdout)
            self.assertEqual(selected["rung"]["id"], rung_id)
            self.assertNotIn("rungs", selected)
            self.assertIn("Saved private run:", stderr)
            run, = workspace.iterdir()
            saved = json.loads((run / "inventory.json").read_text())
            self.assertEqual(len(saved["rungs"]), 1)
            self.assertEqual(saved["rungs"][0], selected["rung"])
            self.assertEqual(source.read_bytes(), SYNTHETIC)

    def test_invalid_rung_id_does_not_save_or_reflect_the_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.L5X"
            source.write_bytes(SYNTHETIC)
            workspace = Path(directory) / "unused"
            code, stdout, stderr = invoke([
                "inspect", str(source), "--rung-id", "PRIVATE_SECRET",
                "--workspace", str(workspace),
            ])
            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertNotIn("PRIVATE_SECRET", stderr)
            self.assertFalse(workspace.exists())

    def test_source_failure_does_not_print_raw_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "PRIVATE_PATH.L5X"
            source.write_bytes(b"<PRIVATE_RAW_TAG")
            code, stdout, stderr = invoke(["inspect", str(source)])
            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertNotIn("PRIVATE_RAW_TAG", stderr)
            self.assertNotIn("PRIVATE_PATH", stderr)

    def test_text_view_keeps_structural_and_engineering_claims_separate(self) -> None:
        result = analyze_snapshot(snapshot_from_bytes(SYNTHETIC))
        text = render_text(result)
        self.assertIn("engineering purpose has not been analyzed", text)
        self.assertIn("Structural coverage", text)
        self.assertIn("Gaps and findings", text)
        rung = result.to_dict()["rungs"][0]
        detail = render_text(result, rung["id"])
        self.assertIn("XIC(In)OTE(Out);", detail)
        self.assertIn(rung["locator"], detail)


if __name__ == "__main__":
    unittest.main()
