"""Report policy compatibility uses invented data and local temporary files only."""
from __future__ import annotations

from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import summary_output, targeted_sample_history, work_check
from plc_workbench.contracts import work_reports
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from test_save_diagnostics import failed_report
from test_summary_output import SUMMARY


class WorkReportContractTests(unittest.TestCase):
    def test_all_historical_versions_keep_their_exact_cap(self) -> None:
        expected_kib = (
            [32] * 21 + [48] * 6 + [64] * 4 + [80] * 7 + [88, 96]
            + [104] * 7 + [112, 128, 128, 144, 144, 144]
        )
        self.assertEqual(len(expected_kib), 53)
        for version, kib in enumerate(expected_kib, start=1):
            with self.subTest(version=version):
                self.assertEqual(work_check._report_limit(version), kib * 1024)
        self.assertEqual(targeted_sample_history.MAX_WORK_REPORT_BYTES, 144 * 1024)
        self.assertEqual(work_reports.MAX_WORK_REPORT_BYTES, 144 * 1024)

    def test_work_check_aliases_remain_independently_patchable(self) -> None:
        # Separate same-size aliases must not accidentally become one override.
        aliases = {
            "MAX_REPORT_BYTES": range(1, 22),
            "MAX_REPORT_V22_BYTES": range(22, 28),
            "MAX_REPORT_V28_BYTES": range(28, 32),
            "MAX_REPORT_V32_BYTES": range(32, 39),
            **{f"MAX_REPORT_V{version}_BYTES": (version,) for version in range(39, 54)},
        }
        baseline = {version: work_check._report_limit(version) for version in range(1, 54)}
        for name, affected in aliases.items():
            with self.subTest(alias=name), patch.object(work_check, name, 123):
                for version in range(1, 54):
                    self.assertEqual(work_check._report_limit(version),
                                     123 if version in affected else baseline[version])

    def test_helper_unknown_versions_keep_the_base_fallback(self) -> None:
        for version in (0, -1, 54, 1000, None, "53", [], {}, True, False):
            with self.subTest(version=version):
                self.assertEqual(work_check._report_limit(version), 32 * 1024)
        # The old helper used equality membership. Strict types are enforced by
        # validators/publication, not silently added to this compatibility API.
        self.assertEqual(work_check._report_limit(53.0), 144 * 1024)

    def test_serialization_keeps_all_known_and_unknown_layouts(self) -> None:
        for version in (*range(1, 54), 0, 54, 1000, None, "53", [], True, False, 53.0):
            with self.subTest(version=version):
                payload = {"z": "caf\u00e9", "schema_version": version, "a": [1, {"b": True}]}
                compact = version in tuple(range(31, 54))
                layout = {"separators": (",", ":")} if compact else {"indent": 2}
                expected = json.dumps(payload, sort_keys=True, ensure_ascii=True, **layout) + "\n"
                self.assertEqual(work_check._serialize_report(payload), expected)
                self.assertEqual(work_reports.serialize_report(payload), expected)

    def test_expanded_publication_requires_exact_known_discriminator(self) -> None:
        class DictSubclass(dict):
            pass

        valid = {"report_kind": "l5x_work_machine_check", "schema_version": 53}
        for version in range(22, 54):
            self.assertEqual(work_reports.publication_limit_name(dict(valid, schema_version=version)),
                             work_reports.report_limit_name(version))
        invalid = [None, [], DictSubclass(valid), dict(valid, report_kind="other")]
        invalid.extend(dict(valid, schema_version=value)
                       for value in (1, 21, 54, 1000, True, False, 53.0, "53", None, [], {}))
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertIsNone(work_reports.publication_limit_name(payload))

    def test_publication_uses_runtime_alias_and_counts_raw_padding(self) -> None:
        payload = failed_report(22)
        canonical = work_check.render_work_check_report(payload)
        limit = len(canonical.encode("utf-8")) + 8
        with tempfile.TemporaryDirectory() as folder, patch.object(work_check, "MAX_REPORT_V22_BYTES", limit):
            root = Path(folder)
            padded = canonical + " " * 8
            output = root / "accepted.json"
            publish_summary(output, padded, input_path=root / "invented.L5X")
            self.assertEqual(output.read_bytes(), canonical.encode("utf-8"))
            with self.assertRaises(SummaryOutputError):
                publish_summary(root / "rejected.json", padded + " ", input_path=root / "invented.L5X")
            self.assertEqual(list(root.iterdir()), [output])

    def test_summary_fallback_is_independent_of_work_base_alias(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.object(work_check, "MAX_REPORT_BYTES", 1):
            root = Path(folder)
            output = root / "summary.json"
            publish_summary(output, SUMMARY, input_path=root / "invented.L5X")
            self.assertEqual(output.read_bytes(), SUMMARY.encode("utf-8"))
            with patch.object(summary_output, "MAX_REPORT_BYTES", len(SUMMARY.encode("utf-8")) - 1):
                with self.assertRaises(SummaryOutputError):
                    publish_summary(root / "rejected.json", SUMMARY, input_path=root / "invented.L5X")
            self.assertEqual(list(root.iterdir()), [output])

    def test_preparse_envelope_considers_every_expanded_runtime_alias(self) -> None:
        # A larger non-latest cap must reach parsing; the envelope must not
        # accidentally collapse to the latest constant or the work base cap.
        for allowed in (*work_reports.EXPANDED_LIMIT_NAMES, None):
            with self.subTest(allowed=allowed), ExitStack() as stack:
                stack.enter_context(patch.object(summary_output, "MAX_REPORT_BYTES", 1))
                stack.enter_context(patch.object(work_check, "MAX_REPORT_BYTES", 1_000_000))
                for name in work_reports.EXPANDED_LIMIT_NAMES:
                    stack.enter_context(patch.object(work_check, name, 3 if name == allowed else 1))
                decode = stack.enter_context(patch.object(summary_output.json, "loads", side_effect=ValueError))
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    with self.assertRaises(SummaryOutputError) as raised:
                        publish_summary(root / "rejected.json", "bad", input_path=root / "invented.L5X")
                    if allowed is None:
                        decode.assert_not_called()
                        self.assertEqual(str(raised.exception), "Summary exceeds its publication size limit.")
                    else:
                        decode.assert_called_once_with("bad")
                        self.assertEqual(str(raised.exception),
                                         "Only a validated summary or work-machine report can be published.")
                    self.assertEqual(list(root.iterdir()), [])

    def test_oversized_wrong_discriminators_fail_before_work_validator(self) -> None:
        for version in (21, 54, True, 53.0, "53"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                payload = {"report_kind": "l5x_work_machine_check", "schema_version": version}
                padded = json.dumps(payload) + " " * summary_output.MAX_REPORT_BYTES
                with patch.object(work_check, "render_work_check_report", side_effect=AssertionError("Must reject size first")):
                    with self.assertRaises(SummaryOutputError):
                        publish_summary(root / "rejected.json", padded, input_path=root / "invented.L5X")
                self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
