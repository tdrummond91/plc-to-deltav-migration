"""Summary command tests at real-file, stdout and publication boundaries."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.cli import main
from plc_workbench.source import capture_snapshot


SOURCE = (
    '<RSLogix5000Content Owner="PRIVATE_EXPORT_SENTINEL">'
    '<Controller Name="PRIVATE_CONTROLLER_SENTINEL"><Programs>'
    '<Program Name="PRIVATE_PROGRAM_SENTINEL"><Routines>'
    '<Routine Name="PRIVATE_ROUTINE_SENTINEL" Type="RLL"><RLLContent>'
    '<Rung Number="0" Type="N"><Comment>PRIVATE_COMMENT_SENTINEL</Comment>'
    '<Text>XIC(PRIVATE_OPERAND_SENTINEL)OTE(PRIVATE_OUTPUT_SENTINEL);</Text>'
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


class SummaryCliTests(unittest.TestCase):
    def test_summary_help_and_usage_do_not_read_input(self) -> None:
        with patch("plc_workbench.source.capture_snapshot", side_effect=AssertionError("must not read")):
            code, stdout, stderr = invoke(["summarize", "--help"])
            self.assertEqual(code, 0)
            self.assertIn("review", stdout.lower())
            self.assertEqual(stderr, "")
            for arguments in (["summarize"], ["summarize", "missing.L5X", "--rung-id", "anything"]):
                code, stdout, stderr = invoke(arguments)
                self.assertEqual(code, 2)
                self.assertEqual(stdout, "")

    def test_real_source_summary_stdout_contains_no_private_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "PRIVATE_FILENAME_SENTINEL.L5X"
            source.write_bytes(SOURCE)
            with patch("plc_workbench.revision.collect_revision", return_value={"commit": None, "worktree": "unavailable"}):
                with patch("plc_workbench.source.capture_snapshot", wraps=capture_snapshot) as capture:
                    code, stdout, stderr = invoke(["summarize", str(source)])
            capture.assert_called_once_with(source)
            self.assertEqual(code, 0)
            self.assertEqual(stderr, "")
            summary = json.loads(stdout)
            self.assertIsInstance(summary, dict)
            self.assertNotIn("PRIVATE_", stdout)
            self.assertNotIn(hashlib.sha256(SOURCE).hexdigest(), stdout)
            self.assertNotIn(str(source), stdout)
            self.assertEqual(source.read_bytes(), SOURCE)
            self.assertEqual(list(Path(directory).iterdir()), [source])

    def test_explicit_summary_publication_has_fixed_notice_without_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "PRIVATE_FILENAME_SENTINEL.L5X"
            source.write_bytes(SOURCE)
            output = Path(directory) / "PRIVATE_DESTINATION_SENTINEL.json"
            code, stdout, stderr = invoke(["summarize", str(source), "--output", str(output)])
            self.assertEqual(code, 0)
            self.assertEqual(stdout, "")
            self.assertEqual(stderr, "Saved summary candidate; status: complete. Review before sharing.\n")
            rendered = output.read_text(encoding="utf-8")
            json.loads(rendered)
            self.assertNotIn("PRIVATE_", rendered)
            self.assertNotIn(hashlib.sha256(SOURCE).hexdigest(), rendered)
            self.assertEqual(source.read_bytes(), SOURCE)

    def test_partial_summary_still_publishes_and_returns_three(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "partial.L5X"
            source.write_bytes(SOURCE.replace(b"OTE(PRIVATE_OUTPUT_SENTINEL);", b"OTE(PRIVATE_OUTPUT_SENTINEL)"))
            output = Path(directory) / "partial.json"
            code, stdout, stderr = invoke(["summarize", str(source), "--output", str(output)])
            self.assertEqual(code, 3)
            self.assertEqual(stdout, "")
            self.assertEqual(stderr, "Saved summary candidate; status: partial. Review before sharing.\n")
            self.assertIsInstance(json.loads(output.read_text(encoding="utf-8")), dict)

    def test_output_cannot_overwrite_input_or_existing_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "PRIVATE_FILENAME_SENTINEL.json"
            source.write_bytes(SOURCE)
            existing = Path(directory) / "PRIVATE_DESTINATION_SENTINEL.json"
            existing.write_bytes(b"existing report")
            for output in (source, existing):
                code, stdout, stderr = invoke(["summarize", str(source), "--output", str(output)])
                self.assertEqual(code, 1)
                self.assertEqual(stdout, "")
                self.assertNotIn("PRIVATE_", stderr)
            self.assertEqual(source.read_bytes(), SOURCE)
            self.assertEqual(existing.read_bytes(), b"existing report")

    def test_failed_source_or_publication_has_no_private_error_or_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "PRIVATE_FILENAME_SENTINEL.L5X"
            source.write_bytes(b"<PRIVATE_RAW_SENTINEL")
            output = root / "PRIVATE_OUTPUT_SENTINEL.json"
            code, stdout, stderr = invoke(["summarize", str(source), "--output", str(output)])
            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertNotIn("PRIVATE_", stderr)
            self.assertFalse(output.exists())
            source.write_bytes(SOURCE)
            with patch("plc_workbench.summary_output.os.link", side_effect=OSError("PRIVATE_LINK_ERROR")):
                code, stdout, stderr = invoke(["summarize", str(source), "--output", str(output)])
            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertNotIn("PRIVATE_", stderr)
            self.assertEqual(list(root.iterdir()), [source])

    def test_source_os_error_is_not_reflected_or_allowed_to_change_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "PRIVATE_INPUT_SENTINEL.L5X"
            source.write_bytes(SOURCE)
            existing = root / "PRIVATE_EXISTING_SENTINEL.json"
            existing.write_bytes(b"previous report")
            candidate = root / "PRIVATE_NEW_SENTINEL.json"
            for output in (existing, candidate):
                with self.subTest(existing=output == existing):
                    with patch.object(Path, "open", side_effect=OSError(5, "PRIVATE_OS_MESSAGE")):
                        code, stdout, stderr = invoke([
                            "summarize", str(source), "--output", str(output),
                        ])
                    self.assertEqual(code, 1)
                    self.assertEqual(stdout, "")
                    self.assertEqual(stderr, "plc: Cannot read or analyze source; no summary was produced.\n")
                    self.assertNotIn("PRIVATE_", stderr)
                    self.assertEqual(existing.read_bytes(), b"previous report")
                    self.assertFalse(candidate.exists())
                    self.assertEqual(source.read_bytes(), SOURCE)
                    self.assertEqual(set(root.iterdir()), {source, existing})


if __name__ == "__main__":
    unittest.main()
