"""Assemblies2 and communication1 share a canonical, bounded release gate."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import review, review_html, work_check
from plc_workbench.communication_context import analyze_communication_context
from plc_workbench.communication_context_summary import build_communication_context_summary
from plc_workbench.engineering_assemblies import build_engineering_assemblies
from plc_workbench.engineering_assemblies_summary import build_engineering_assemblies_summary
from plc_workbench.source_reuse import source_reuse_scope
from plc_workbench.storage import StorageError, save_run
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from plc_workbench.targeted_sample_history import sample_envelope
from plc_workbench.work_check_tests import unavailable_result
from plc_workbench.work_check_timing import WorkCheckTiming
from test_engineering_assemblies_workflow import (
    arguments as old_arguments, options as old_options, provider_data,
    report as old_report, maximum_width_report as old_maximum,
)
from test_signal_candidates_workflow import captured
from test_unmatched_sample_report import REVISION
from test_work_check_timing import timing_fixture
from test_review_workflow import invoke
from test_execution_context import document, program, routine

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "public/fixtures/synthetic/residual_source_demo.L5X").read_bytes()
BUNDLE = {"engineering_assemblies_schema_version": 2, "include_communication_context": True}
ANALYZE_OPTIONS = dict(sfc_context_schema_version=2, include_execution_context=True,
    include_signal_context=True, include_file_operations=True, signal_context_schema_version=5,
    include_alarm_evidence=True, include_engineering_assemblies=True, **BUNDLE)


def options(parts: tuple) -> dict:
    return old_options(parts) | BUNDLE


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | BUNDLE


def communication(parts: tuple):
    providers = old_options(parts)
    return analyze_communication_context(*parts[:3], providers["access"], providers["tag_data"],
                                         calculations=providers["calculations"])


@lru_cache(maxsize=2)
def _report(data: bytes) -> dict:
    with source_reuse_scope():
        parts = captured(data)
        providers = old_options(parts)
        payload = old_report(data)
        payload.update(schema_version=48, workflow_version="work-check-48")
        assemblies = build_engineering_assemblies(provider_data(parts), schema_version=2)
        payload["analysis"]["engineering_assemblies_summary"] = build_engineering_assemblies_summary(
            assemblies, tool_revision=REVISION)
        companion = communication(parts)
        payload["analysis"]["communication_context_summary"] = build_communication_context_summary(
            *parts[:3], providers["access"], providers["tag_data"], companion,
            revision=REVISION, calculations=providers["calculations"])
        if "partial" in (assemblies["status"], companion.status):
            payload["analysis"]["status"] = payload["status"] = "partial"
        return payload


def report(data: bytes = SOURCE) -> dict:
    return deepcopy(_report(data))


def maximum_width_report() -> dict:
    payload = old_maximum()
    payload.update(schema_version=48, workflow_version="work-check-48")
    def grow(value):
        if type(value) is int:
            return 10**12
        if type(value) is dict:
            return {key: grow(child) for key, child in value.items()}
        return value
    for key in ("engineering_assemblies_summary", "communication_context_summary"):
        payload["analysis"][key] = grow(report()["analysis"][key])
    return payload


class R3ContextWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = source_reuse_scope()
        self.scope.__enter__()
        self.addCleanup(self.scope.__exit__, None, None, None)

    def test_bundle_gate_preserves_default_review29_and_sixteen_artifacts(self) -> None:
        parts = captured(SOURCE)
        prior = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual((prior["schema_version"], current["schema_version"]), (29, 30))
        self.assertNotIn("communication_context", prior)
        self.assertEqual(current["communication_context"], communication(parts).to_dict())
        self.assertEqual(current["engineering_assemblies"]["schema_version"], 2)
        for key in prior.keys() - {"schema_version", "report_version", "status", "engineering_assemblies"}:
            self.assertEqual(current[key], prior[key], key)
        review.validate_review_data(*parts[:4], current, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = save_run(root, *parts[:2], **old_arguments(parts))
            original = {path.name: path.read_bytes() for path in before.iterdir()}
            after = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((after / "manifest.json").read_bytes())
            self.assertEqual((manifest["schema_version"], manifest["review_schema_version"]), (33, 30))
            self.assertEqual((manifest["engineering_assemblies_schema_version"],
                              manifest["communication_context_schema_version"]), (2, 1))
            self.assertEqual(manifest["communication_context_analyzer_version"], "communication-context-1")
            self.assertEqual(len(manifest["artifacts"]), 16)
            self.assertEqual(set(original), {path.name for path in after.iterdir()})
            for name, content in original.items():
                self.assertEqual((before / name).read_bytes(), content)
                if name not in {"manifest.json", "review.html"}:
                    self.assertEqual((after / name).read_bytes(), content, name)
            for name, record in manifest["artifacts"].items():
                self.assertEqual(hashlib.sha256((after / name).read_bytes()).hexdigest(), record["sha256"])

    def test_bundle_requires_all_providers_before_allocating_a_run(self) -> None:
        parts = captured(SOURCE)
        bad_options = [{key: None} for key in old_options(parts)]
        bad_options += [{"engineering_assemblies_schema_version": value} for value in (True, None, 0, 1, 3)]
        bad_options += [{"include_communication_context": value} for value in (None, 1, "true", False)]
        bad_options += [{"include_engineering_assemblies": False}]
        for override in bad_options:
            with self.subTest(override=override), tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / "unallocated"
                with self.assertRaises(review.ReviewError):
                    review.build_review_data(*parts[:4], **(options(parts) | override))
                with self.assertRaises(StorageError):
                    save_run(destination, *parts[:2], **(arguments(parts) | override))
                self.assertFalse(destination.exists())

    def test_canonical_replay_rejects_companion_and_provider_tampering(self) -> None:
        parts = captured(SOURCE)
        current = review.build_review_data(*parts[:4], **options(parts))
        for mutate in (
            lambda d: d.update(communication_context=None),
            lambda d: d["communication_context"].update(schema_version=True),
            lambda d: d["communication_context"].update(PRIVATE_SENTINEL="PRIVATE_SENTINEL"),
            lambda d: d["communication_context"].update(occurrences=[]),
            lambda d: d["engineering_assemblies"].update(supplemental_addresses=[]),
            lambda d: d["engineering_assemblies"].update(schema_version=1),
        ):
            forged = deepcopy(current)
            mutate(forged)
            with self.subTest(mutate=mutate), self.assertRaises(review.ReviewError):
                review.validate_review_data(*parts[:4], forged, **options(parts))
        providers = old_options(parts)
        forged = replace(providers["access"], status="partial" if providers["access"].status == "complete" else "complete")
        with patch.object(review, "analyze_communication_context") as analyzer:
            with self.assertRaises(review.ReviewError):
                review.build_review_data(*parts[:4], **(options(parts) | {"access": forged}))
            analyzer.assert_not_called()

    def test_html_rejects_mixed_missing_null_and_unversioned_companions(self) -> None:
        parts = captured(SOURCE)
        current = review.build_review_data(*parts[:4], **options(parts))
        for mutate in (
            lambda d: d.update(schema_version=29, report_version="engineering-review-29"),
            lambda d: d.pop("communication_context"),
            lambda d: d.update(communication_context=None),
            lambda d: d["communication_context"].update(schema_version=True),
            lambda d: d["communication_context"].update(analyzer_version="communication-context-2"),
            lambda d: d["engineering_assemblies"].update(schema_version=1, analyzer_version="engineering-assemblies-1"),
            lambda d: d.update(alarm_evidence=None),
            lambda d: d.update(file_operations=None),
        ):
            forged = deepcopy(current)
            mutate(forged)
            with self.subTest(mutate=mutate), self.assertRaises(review_html.ReviewHtmlError):
                review_html.render_review_html(forged)

    def test_versioned_limits_preserve_review29_and_stop_before_allocation(self) -> None:
        parts = captured(SOURCE)
        prior = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual(review.MAX_REVIEW_V30_BYTES, 456 * 1024 * 1024)
        self.assertEqual(review_html._limits(30), (456 * 1024 * 1024, 488 * 1024 * 1024))
        self.assertEqual(review_html._limits(29), (448 * 1024 * 1024, 480 * 1024 * 1024))
        with patch.object(review, "MAX_REVIEW_V30_BYTES", 1), tempfile.TemporaryDirectory() as folder:
            review.render_review_json(prior)
            destination = Path(folder) / "unallocated"
            with self.assertRaises(StorageError) as error:
                save_run(destination, *parts[:2], **arguments(parts))
            self.assertEqual(error.exception.code, "review_size_limit")
            self.assertFalse(destination.exists())
        for key in ("MAX_REVIEW_V30_PAYLOAD_BYTES", "MAX_REVIEW_V30_HTML_BYTES"):
            with patch.object(review_html, key, 1):
                review_html.render_review_html(prior)
                with self.assertRaises(review_html.ReviewHtmlSizeLimitError):
                    review_html.render_review_html(current)

    def test_communication_only_gap_propagates_through_review_manifest_cli_and_work(self) -> None:
        from test_communication_context import tag
        source_bytes = document(program(routines=routine(text=";")), tags=tag(
            "Produced", body="<ProduceInfo><Unknown/></ProduceInfo>")).encode("utf-8")
        parts = captured(source_bytes)
        prior = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual(prior["status"], "complete")
        self.assertEqual(current["communication_context"]["status"], "partial")
        self.assertEqual(current["status"], "partial")
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            source = root / "invented.L5X"
            source.write_bytes(source_bytes)
            code, _, error = invoke(["review", str(source), "--workspace", str(root / "runs")])
            self.assertEqual((code, error), (3, ""))
            saved, = (root / "runs").iterdir()
            manifest = json.loads((saved / "manifest.json").read_bytes())
            self.assertEqual(manifest["status"], "partial")
            analysis = work_check._analyze(root, source, root, REVISION, **ANALYZE_OPTIONS)
            self.assertEqual(analysis["status"], "partial")
            self.assertIsNone(analysis["failure_code"])
            self.assertTrue(analysis["private_run_saved"])
            self.assertEqual(analysis["communication_context_summary"],
                             report(source_bytes)["analysis"]["communication_context_summary"])
        payload = report(source_bytes)
        work_check.validate_work_check_report(payload)
        payload["analysis"]["status"] = "complete"
        payload["status"] = "passed"
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_work48_preserves_prior_summaries_and_frozen_sample_reservation(self) -> None:
        current, old = report(), old_report(SOURCE)
        work_check.validate_work_check_report(current)
        work_check.validate_work_check_report(old)
        self.assertEqual(current["targeted_samples"], old["targeted_samples"])
        for key in old["analysis"].keys() - {"status", "engineering_assemblies_summary"}:
            self.assertEqual(current["analysis"][key], old["analysis"][key], key)
        for mutate in (
            lambda p: p["analysis"].pop("communication_context_summary"),
            lambda p: p["analysis"].update(communication_context_summary=None),
            lambda p: p.update(schema_version=47, workflow_version="work-check-47"),
            lambda p: p["analysis"]["communication_context_summary"].update(source="PRIVATE"),
            lambda p: p["analysis"]["communication_context_summary"]["tool_revision"].update(commit="b" * 40),
            lambda p: p["analysis"]["communication_context_summary"].update(schema_version=True),
            lambda p: p["analysis"]["communication_context_summary"]["coverage"].update(source_rungs=10**12),
            lambda p: p["analysis"].update(engineering_assemblies_summary=old["analysis"]["engineering_assemblies_summary"]),
        ):
            forged = deepcopy(current)
            mutate(forged)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                work_check.validate_work_check_report(forged)

    def test_closed_failure_and_not_run_require_null_new_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder).resolve()
            source = root / "invented.L5X"
            source.write_bytes(SOURCE)
            timing = WorkCheckTiming()
            with patch.object(work_check, "analyze_communication_context", side_effect=ValueError("PRIVATE")), \
                    patch.object(work_check, "save_run") as save:
                result = work_check._analyze(root, source, root, REVISION, timings=timing, **ANALYZE_OPTIONS)
            save.assert_not_called()
            self.assertEqual(result["failure_code"], "communication_context_error")
            self.assertNotIn("PRIVATE", json.dumps(result))
            self.assertFalse(result["private_run_saved"])
            self.assertIsNone(timing.snapshot()["phases_ms"]["private_save"])
        result.pop("diagnostic_sample")
        result.pop("targeted_samples")
        failed = report()
        failed.update(analysis=result, status="failed", timings=timing_fixture(
            ("application_tests", "helpers_tests", "analysis_build")), targeted_samples=sample_envelope())
        work_check.validate_work_check_report(failed)
        not_run = deepcopy(failed)
        not_run["analysis"].update(status="not_run", failure_code=None)
        not_run["tests"]["application"] = unavailable_result("runner_error")
        not_run["timings"] = timing_fixture(("application_tests", "helpers_tests"))
        work_check.validate_work_check_report(not_run)
        for payload in (failed, not_run):
            for key in ("engineering_assemblies_summary", "communication_context_summary"):
                forged = deepcopy(payload)
                forged["analysis"][key] = report()["analysis"][key]
                with self.subTest(status=payload["analysis"]["status"], key=key), self.assertRaises(ValueError):
                    work_check.validate_work_check_report(forged)

    def test_work_bundle_gate_fails_before_reading_the_source(self) -> None:
        for override in ({"engineering_assemblies_schema_version": True},
                         {"engineering_assemblies_schema_version": 1},
                         {"include_communication_context": None},
                         {"include_communication_context": False},
                         {"include_engineering_assemblies": False},
                         {"include_file_operations": False}):
            with self.subTest(override=override), patch.object(work_check, "capture_snapshot") as capture:
                result = work_check._analyze(Path("."), Path("invented.L5X"), Path("."), REVISION,
                                             **(ANALYZE_OPTIONS | override))
            capture.assert_not_called()
            self.assertIn(result["failure_code"], ("communication_context_error", "engineering_assemblies_error"))
            self.assertFalse(result["private_run_saved"])

    def test_maximum_envelope_and_publication_preserve_historical_caps(self) -> None:
        maximum = len(work_check._serialize_report(maximum_width_report()).encode("utf-8"))
        self.assertEqual(maximum, 107787)
        self.assertLessEqual(maximum, work_check.MAX_REPORT_V48_BYTES)
        self.assertEqual(work_check._report_limit(48), 112 * 1024)
        self.assertEqual(work_check._report_limit(47), 104 * 1024)
        encoded = work_check.render_work_check_report(report())
        for marker in ("PRIVATE_", '"endpoint_id":', '"instruction_id":', '"supplemental_addresses":',
                       '"LocalElement": "', '"ConnectionPath": "'):
            self.assertNotIn(marker, encoded)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            destination = root / "feedback.json"
            publish_summary(destination, encoded, input_path=root / "invented.L5X")
            self.assertEqual(destination.read_text(encoding="utf-8"), encoded)
            for payload in (report(), old_report(SOURCE)):
                oversized = work_check._serialize_report(payload) + " " * work_check._report_limit(payload["schema_version"])
                with self.assertRaises(SummaryOutputError):
                    publish_summary(root / "rejected.json", oversized, input_path=root / "invented.L5X")
                self.assertFalse((root / "rejected.json").exists())

    def test_committed_reports_remain_read_only_and_valid(self) -> None:
        paths = sorted((ROOT / "public/inspection").glob("work-check-*.json"))
        self.assertGreaterEqual(len(paths), 55)
        for path in paths:
            original = path.read_bytes()
            with self.subTest(report=path.name):
                work_check.validate_work_check_report(json.loads(original))
                self.assertEqual(path.read_bytes(), original)

    def test_historical_report_validation_accepts_future_feedback(self) -> None:
        paths = sorted((ROOT / "public/inspection").glob("work-check-*.json"))
        with tempfile.TemporaryDirectory() as folder:
            later = Path(folder) / "work-check-future.json"
            later.write_text(work_check.render_work_check_report(report()), encoding="utf-8", newline=chr(10))
            with patch.object(Path, "glob", return_value=iter([*paths, later])):
                self.test_committed_reports_remain_read_only_and_valid()


if __name__ == "__main__":
    unittest.main()
