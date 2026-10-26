"""Derived source assemblies are opt-in, canonical and privately persisted."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import review, review_html
from plc_workbench.engineering_assemblies import build_engineering_assemblies
from plc_workbench.engineering_assemblies_summary import build_engineering_assemblies_summary
from plc_workbench.source_reuse import source_reuse_scope
from plc_workbench.storage import StorageError, save_run
from test_signal_candidates_workflow import (
    captured, options as old_options, arguments as old_arguments, SOURCE,
    report as old_report, maximum_width_report as old_maximum,
)
from test_signal_dependencies_workflow import captured as older_captured
from test_review_workflow import invoke
from test_unmatched_sample_report import REVISION


def options(parts: tuple) -> dict:
    return old_options(parts) | {"include_engineering_assemblies": True}


def arguments(parts: tuple) -> dict:
    return old_arguments(parts) | {"include_engineering_assemblies": True}


def provider_data(parts: tuple) -> dict:
    providers = old_options(parts)
    return {key: providers[key].to_dict() for key in (
        "relationships", "access", "signal_context", "pid_connections",
        "calculation_paths", "stateful_objects", "sfc_context", "file_operations",
    )}


@lru_cache(maxsize=6)
def _report(data: bytes) -> dict:
    with source_reuse_scope():
        payload = old_report(data)
        assemblies = build_engineering_assemblies(provider_data(captured(data)))
        payload.update(schema_version=47, workflow_version="work-check-47")
        payload["analysis"]["engineering_assemblies_summary"] = build_engineering_assemblies_summary(
            assemblies, tool_revision=REVISION)
        if assemblies["status"] == "partial":
            payload["analysis"]["status"] = payload["status"] = "partial"
        return payload


def report(data: bytes = SOURCE) -> dict:
    return deepcopy(_report(data))


def maximum_width_report() -> dict:
    payload = old_maximum()
    payload.update(schema_version=47, workflow_version="work-check-47")
    def grow(value):
        if type(value) is int:
            return 10**12
        if type(value) is dict:
            return {key: grow(child) for key, child in value.items()}
        return value
    payload["analysis"]["engineering_assemblies_summary"] = grow(report()["analysis"]["engineering_assemblies_summary"])
    return payload


class EngineeringAssembliesWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = source_reuse_scope()
        self.scope.__enter__()
        self.addCleanup(self.scope.__exit__, None, None, None)

    def test_opt_in_review29_manifest32_preserve_every_prior_provider_and_artifact(self) -> None:
        parts = captured()
        prior = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual((prior["schema_version"], current["schema_version"]), (28, 29))
        self.assertEqual(current["report_version"], "engineering-review-29")
        self.assertNotIn("engineering_assemblies", prior)
        self.assertEqual(current["engineering_assemblies"], build_engineering_assemblies(provider_data(parts)))
        for key in prior.keys() - {"schema_version", "report_version", "status"}:
            self.assertEqual(current[key], prior[key], key)
        review.validate_review_data(*parts[:4], current, **options(parts))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            before = save_run(root, *parts[:2], **old_arguments(parts))
            prior_bytes = {p.name: p.read_bytes() for p in before.iterdir()}
            after = save_run(root, *parts[:2], **arguments(parts))
            manifest = json.loads((after / "manifest.json").read_bytes())
            self.assertEqual((manifest["schema_version"], manifest["review_schema_version"]), (32, 29))
            self.assertEqual(len(manifest["artifacts"]), 16)
            self.assertEqual(manifest["engineering_assemblies_schema_version"], 1)
            self.assertEqual(manifest["engineering_assemblies_analyzer_version"], "engineering-assemblies-1")
            self.assertEqual(manifest["signal_context_schema_version"], 5)
            for name, value in prior_bytes.items():
                self.assertEqual((before / name).read_bytes(), value)
                if name not in {"manifest.json", "review.html"}:
                    self.assertEqual((after / name).read_bytes(), value, name)
            for name, record in manifest["artifacts"].items():
                self.assertEqual(hashlib.sha256((after / name).read_bytes()).hexdigest(), record["sha256"])

    def test_opt_in_requires_latest_complete_companions_before_allocation(self) -> None:
        parts = captured()
        for key in old_options(parts):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / "unallocated"
                with self.assertRaises(review.ReviewError):
                    review.build_review_data(*parts[:4], **(options(parts) | {key: None}))
                with self.assertRaises(StorageError):
                    save_run(destination, *parts[:2], **(arguments(parts) | {key: None}))
                self.assertFalse(destination.exists())
        for value in (1, None, "true"):
            with self.subTest(value=value), self.assertRaises(review.ReviewError):
                review.build_review_data(*parts[:4], **(old_options(parts) | {"include_engineering_assemblies": value}))
        older = older_captured()
        with self.assertRaises(review.ReviewError):
            review.build_review_data(*older[:4], **options(older))
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "unallocated"
            with self.assertRaises(StorageError):
                save_run(destination, *parts[:2], **(arguments(parts) | {"include_review": False}))
            self.assertFalse(destination.exists())

    def test_forged_assembly_and_provider_fail_canonical_replay(self) -> None:
        parts = captured()
        current = review.build_review_data(*parts[:4], **options(parts))
        for mutate in (
            lambda d: d["engineering_assemblies"].update(groups=[]),
            lambda d: d["engineering_assemblies"].update(PRIVATE_SENTINEL="PRIVATE_SENTINEL"),
            lambda d: d["engineering_assemblies"].update(schema_version=True),
            lambda d: d.update(engineering_assemblies=None),
        ):
            forged = deepcopy(current)
            mutate(forged)
            with self.subTest(mutate=mutate), self.assertRaises(review.ReviewError):
                review.validate_review_data(*parts[:4], forged, **options(parts))
        rows = deepcopy(parts[24].outputs)
        rows[0]["candidate_context"]["target_categories"] = ["PRIVATE_SENTINEL"]
        forged_signal = replace(parts[24], outputs=rows)
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "unallocated"
            with patch.object(review, "build_engineering_assemblies") as builder:
                with self.assertRaises(StorageError) as error:
                    save_run(destination, *parts[:2], **(arguments(parts) | {"signal_context": forged_signal}))
                builder.assert_not_called()
            self.assertEqual(error.exception.code, "review_validation_error")
            self.assertNotIn("PRIVATE_SENTINEL", str(error.exception))
            self.assertFalse(destination.exists())

    def test_review29_limits_do_not_change_review28(self) -> None:
        parts = captured()
        prior = review.build_review_data(*parts[:4], **old_options(parts))
        current = review.build_review_data(*parts[:4], **options(parts))
        self.assertEqual(review.MAX_REVIEW_V29_BYTES, 448 * 1024 * 1024)
        self.assertEqual(review_html._limits(29), (448 * 1024 * 1024, 480 * 1024 * 1024))
        self.assertEqual(review_html._limits(28), (384 * 1024 * 1024, 416 * 1024 * 1024))
        with patch.object(review, "MAX_REVIEW_V29_BYTES", 1), tempfile.TemporaryDirectory() as folder:
            review.render_review_json(prior)
            destination = Path(folder) / "unallocated"
            with self.assertRaises(StorageError) as error:
                save_run(destination, *parts[:2], **arguments(parts))
            self.assertEqual(error.exception.code, "review_size_limit")
            self.assertFalse(destination.exists())
        for key in ("MAX_REVIEW_V29_PAYLOAD_BYTES", "MAX_REVIEW_V29_HTML_BYTES"):
            with patch.object(review_html, key, 1):
                review_html.render_review_html(prior)
                with self.assertRaises(review_html.ReviewHtmlSizeLimitError):
                    review_html.render_review_html(current)

    def test_html_rejects_mixed_versions_and_unversioned_assembly(self) -> None:
        parts = captured()
        current = review.build_review_data(*parts[:4], **options(parts))
        for mutate in (
            lambda d: d.update(schema_version=28, report_version="engineering-review-28"),
            lambda d: d.pop("engineering_assemblies"),
            lambda d: d["engineering_assemblies"].update(schema_version=True),
            lambda d: d["engineering_assemblies"].update(analyzer_version="engineering-assemblies-2"),
            lambda d: d["signal_context"].update(schema_version=4, analyzer_version="signal-context-4"),
            lambda d: d.update(alarm_evidence=None),
            lambda d: d.update(file_operations=None),
        ):
            forged = deepcopy(current)
            mutate(forged)
            with self.subTest(mutate=mutate), self.assertRaises(review_html.ReviewHtmlError):
                review_html.render_review_html(forged)

    def test_cli_and_direct_latest_saved_bytes_are_identical(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "invented.L5X"
            path.write_bytes(SOURCE)
            code, output, error = invoke(["review", str(path), "--workspace", str(root / "runs")])
            self.assertEqual((code, error), (3, ""))
            saved, = (root / "runs").iterdir()
            manifest = json.loads((saved / "manifest.json").read_bytes())
            self.assertEqual((manifest["schema_version"], manifest["review_schema_version"]), (38, 35))
            parts = captured()
            from test_engineering_assemblies_rack_workflow import captured as current_captured, options as current_options
            current_parts = current_captured(SOURCE)
            expected = review.build_review_data(*current_parts[:4], **current_options(current_parts))
            self.assertEqual((saved / "review.html").read_bytes(), review_html.render_review_html(expected, source=current_parts[0].data).encode())

    def test_cli_exit_status_includes_assembly_truncation(self) -> None:
        from plc_workbench import engineering_assemblies
        from test_execution_context import document, program, routine, tag
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "invented.L5X"
            path.write_bytes(document(program(routines=routine(text="XIC(A)OTE(B);")),
                                      tags=tag("A") + tag("B")).encode())
            baseline = invoke(["review", str(path), "--workspace", str(root / "complete")])
            self.assertEqual((baseline[0], baseline[2]), (0, ""))
            with patch.object(engineering_assemblies, "MAX_ASSEMBLY_VISITS", 0):
                code, _, error = invoke(["review", str(path), "--workspace", str(root / "truncated")])
            self.assertEqual((code, error), (3, ""))
            saved, = (root / "truncated").iterdir()
            manifest = json.loads((saved / "manifest.json").read_bytes())
            self.assertEqual(manifest["status"], "partial")


if __name__ == "__main__":
    unittest.main()
