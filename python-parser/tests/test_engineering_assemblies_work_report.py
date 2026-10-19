"""Assembly feedback is closed aggregate evidence; work1-46 remain frozen."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import work_check
from plc_workbench.source_reuse import source_reuse_scope
from plc_workbench.summary_output import publish_summary, SummaryOutputError
from plc_workbench.targeted_sample_history import sample_envelope
from plc_workbench.work_check_tests import unavailable_result
from plc_workbench.work_check_timing import WorkCheckTiming
from test_engineering_assemblies_workflow import report, maximum_width_report, SOURCE
from test_signal_candidates_workflow import report as legacy_report
from test_work_check_timing import timing_fixture
from test_unmatched_sample_report import REVISION


class EngineeringAssembliesWorkReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = source_reuse_scope()
        self.scope.__enter__()
        self.addCleanup(self.scope.__exit__, None, None, None)

    def test_explicit_opt_in_preserves_prior_summaries_and_frozen_samples(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            source = root / "invented.L5X"
            source.write_bytes(SOURCE)
            common = dict(sfc_context_schema_version=2, include_execution_context=True,
                          include_signal_context=True, include_file_operations=True,
                          signal_context_schema_version=5, include_alarm_evidence=True)
            old = work_check._analyze(root, source, root, REVISION, **common)
            current = work_check._analyze(root, source, root, REVISION,
                include_engineering_assemblies=True, **common)
            self.assertNotIn("engineering_assemblies_summary", old)
            for result in (old, current):
                self.assertIsNone(result["failure_code"])
                self.assertTrue(result["private_run_saved"])
            self.assertEqual(current["engineering_assemblies_summary"]["schema_version"], 1)
            self.assertEqual(current["engineering_assemblies_summary"], report()["analysis"]["engineering_assemblies_summary"])
            self.assertEqual(old["targeted_samples"]["record"], current["targeted_samples"]["record"])
            self.assertEqual(current["targeted_samples"]["status"], "replayed")
            for key in old.keys() - {"status", "targeted_samples"}:
                self.assertEqual(old[key], current[key], key)

    def test_work47_requires_assembly1_while_work46_keeps_previous_contract(self) -> None:
        current, old = report(), legacy_report(SOURCE)
        work_check.validate_work_check_report(current)
        work_check.validate_work_check_report(old)
        self.assertEqual(current["targeted_samples"], old["targeted_samples"])
        for key in old["analysis"].keys() - {"status"}:
            self.assertEqual(current["analysis"][key], old["analysis"][key], key)
        for mutate in (
            lambda p: p["analysis"].pop("engineering_assemblies_summary"),
            lambda p: p["analysis"].update(engineering_assemblies_summary=None),
            lambda p: p.update(schema_version=46, workflow_version="work-check-46"),
            lambda p: p["analysis"]["engineering_assemblies_summary"].update(source="PRIVATE"),
            lambda p: p["analysis"]["engineering_assemblies_summary"]["tool_revision"].update(commit="b"*40),
            lambda p: p["analysis"]["engineering_assemblies_summary"].update(schema_version=True),
            lambda p: p["analysis"].update(signal_context_summary=None),
        ):
            candidate = deepcopy(current)
            mutate(candidate)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)

    def test_outer_cap_reserves_frozen_envelope_and_rejects_private_fields(self) -> None:
        maximum = len(work_check._serialize_report(maximum_width_report()).encode())
        self.assertLessEqual(maximum, work_check.MAX_REPORT_V47_BYTES)
        self.assertEqual(maximum, 103810)
        self.assertEqual(work_check._report_limit(47), 104 * 1024)
        for version in (41, 42, 43, 44, 45, 46):
            self.assertEqual(work_check._report_limit(version), 104 * 1024)
        encoded = work_check.render_work_check_report(report())
        for marker in ("InventedCompactSignal", "PRIVATE_SENTINEL", "PRIVATE_ALARM_SENTINEL",
                       "PRIVATE_AUTHORED_SENTINEL", "Delay.DN", '"condition_read_id":', '"address_id":',
                       '"instruction_id":', '"membership_ids":', '"rung_ids":'):
            self.assertNotIn(marker, encoded)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            destination = root / "feedback.json"
            publish_summary(destination, encoded, input_path=root / "invented.L5X")
            self.assertEqual(destination.read_text(), encoded)
            for payload in (report(), legacy_report(SOURCE)):
                oversized = work_check._serialize_report(payload) + " " * work_check._report_limit(payload["schema_version"])
                with self.assertRaises(SummaryOutputError):
                    publish_summary(root / "rejected.json", oversized, input_path=root / "invented.L5X")
                self.assertFalse((root / "rejected.json").exists())

    def test_assembly_failure_stops_before_save_and_keeps_closed_failure_shape(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            source = root / "invented.L5X"
            source.write_bytes(SOURCE)
            timing = WorkCheckTiming()
            with patch.object(work_check, "build_engineering_assemblies", side_effect=ValueError("PRIVATE")), \
                    patch.object(work_check, "save_run") as save:
                result = work_check._analyze(root, source, root, REVISION, timings=timing,
                    sfc_context_schema_version=2, include_execution_context=True,
                    include_signal_context=True, include_file_operations=True,
                    signal_context_schema_version=5, include_alarm_evidence=True,
                    include_engineering_assemblies=True)
            save.assert_not_called()
            self.assertEqual(result["failure_code"], "engineering_assemblies_error")
            self.assertFalse(result["private_run_saved"])
            self.assertNotIn("PRIVATE", json.dumps(result))
            self.assertIsNone(timing.snapshot()["phases_ms"]["private_save"])
        result.pop("diagnostic_sample")
        result.pop("targeted_samples")
        payload = report()
        payload.update(analysis=result, status="failed", timings=timing_fixture(
            ("application_tests", "helpers_tests", "analysis_build")), targeted_samples=sample_envelope())
        work_check.validate_work_check_report(payload)
        self.assertIsNone(result["engineering_assemblies_summary"])
        payload["analysis"]["engineering_assemblies_summary"] = report()["analysis"]["engineering_assemblies_summary"]
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_not_run_requires_null_assembly(self) -> None:
        payload = report()
        for key in payload["analysis"]:
            payload["analysis"][key] = None
        payload["analysis"].update(status="not_run", private_run_saved=False)
        payload.update(status="failed", targeted_samples=sample_envelope(),
                       timings=timing_fixture(("application_tests", "helpers_tests")))
        payload["tests"]["application"] = unavailable_result("runner_error")
        work_check.validate_work_check_report(payload)
        payload["analysis"]["engineering_assemblies_summary"] = report()["analysis"]["engineering_assemblies_summary"]
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_missing_prerequisites_fail_before_any_source_read(self) -> None:
        common = dict(include_execution_context=True, include_signal_context=True,
                      include_file_operations=True, include_alarm_evidence=True,
                      signal_context_schema_version=5, include_engineering_assemblies=True)
        for key, value in (("include_execution_context", False), ("include_signal_context", False),
                           ("include_file_operations", False), ("include_alarm_evidence", False),
                           ("signal_context_schema_version", 4), ("include_engineering_assemblies", 1)):
            with self.subTest(key=key), patch.object(work_check, "capture_snapshot") as capture:
                result = work_check._analyze(Path("."), Path("invented.L5X"), Path("."), REVISION,
                                             **(common | {key: value}))
            capture.assert_not_called()
            self.assertEqual(result["failure_code"], "engineering_assemblies_error")
            self.assertFalse(result["private_run_saved"])
            self.assertIsNone(result["engineering_assemblies_summary"])


if __name__ == "__main__":
    unittest.main()
