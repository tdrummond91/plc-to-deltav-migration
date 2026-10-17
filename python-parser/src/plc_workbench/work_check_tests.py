"""Run audited parser tests and emit a bounded result without traceback content.

The caller redirects the ordinary unittest stream to a private log. Only this
module's closed result contract is eligible for inclusion in a shared report.
Work-machine runs import only the explicit module allowlists below. New test
modules require review before joining this scope. Listener/host, Bash/bootstrap,
Git/work-check automation, revision integration and CLI tests that invoke Git
metadata collection are development-only. Ordinary full unittest discovery is
unchanged. Each selected suite runs in a fresh process because the test
directories use top-level module names.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, TextIO
import unittest


MAX_RESULT_BYTES = 8192
MAX_FAILED_IDS = 20
MAX_ID_LENGTH = 160
_MAX_COUNT = 1_000_000_000
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+", re.ASCII)
_FALLBACK_ID = "unittest.loader._FailedTest"
_COUNT_KEYS = frozenset({
    "tests_run", "failures", "errors", "skipped", "expected_failures", "unexpected_successes",
})
_RESULT_KEYS = frozenset({
    "schema_version", "status", "counts", "failed_test_ids", "failure_ids_omitted",
})
# Audited for subprocess/network fixtures: these cases use invented inputs,
# memory buffers or temporary local files. The summary modules also exercise
# pure work-check report validation; they never execute that workflow.
WORK_MACHINE_MODULES = {
    "application": (
        "test_address_shape_summary", "test_cli", "test_diagnostic_sample", "test_module_io",
        "test_module_references", "test_module_source", "test_module_summary",
        "test_rack_candidates", "test_rack_source", "test_rack_summary",
        "test_reference_summary", "test_references", "test_source", "test_source_reuse", "test_storage",
        "test_summary", "test_summary_output", "test_timer_placeholders",
        "test_unmatched_sample_report",
        "test_system_flags", "test_system_flag_summary", "test_system_flag_report",
        "test_math_references", "test_math_summary", "test_math_report",
        "test_bit_operations",
        "test_routine_shapes", "test_routine_targets", "test_routine_metadata", "test_routine_graph", "test_sfc_structure", "test_sfc_summary",
        "test_sfc_cli", "test_sfc_storage", "test_sfc_work_report",
        "test_sfc_annotations", "test_sfc_annotation_summary",
        "test_review", "test_review_html", "test_review_workflow",
        "test_access", "test_access_summary", "test_access_workflow",
        "test_access_extended", "test_access_summary_extended", "test_access_extended_workflow",
        "test_tag_data", "test_tag_data_summary", "test_tag_evidence_workflow",
        "test_pid", "test_pid_summary", "test_pid_workflow",
        "test_pid_members", "test_pid_member_summary", "test_pid_member_workflow",
        "test_pid_connections", "test_pid_connection_summary", "test_pid_connection_workflow",
        "test_calculation_paths", "test_calculation_path_summary", "test_calculation_path_workflow",
        "test_output_context", "test_output_context_summary", "test_output_context_workflow",
        "test_stateful_objects", "test_stateful_object_summary", "test_stateful_object_workflow",
        "test_sfc_conditions", "test_sfc_condition_summary", "test_sfc_condition_workflow",
        "test_sfc_context", "test_sfc_context_summary", "test_sfc_context_workflow", "test_work_check_timing",
        "test_calculations", "test_calculation_summary", "test_calculation_workflow",
        "test_cpt_access", "test_cpt_access_summary", "test_cpt_access_workflow",
        "test_rung_analysis", "test_rung_analysis_summary", "test_rung_analysis_workflow",
        "test_relationships", "test_relationship_summary", "test_relationship_workflow",
        "test_conditions", "test_condition_summary", "test_condition_workflow",
        "test_save_diagnostics", "test_review_save_failures",
        "test_binding_context", "test_binding_context_summary", "test_binding_context_workflow",
        "test_targeted_samples", "test_targeted_sample_history", "test_targeted_sample_workflow",
        "test_custom_instruction_context", "test_custom_instruction_summary",
        "test_indexed_access", "test_indexed_access_summary", "test_instruction_context_workflow",
        "test_stateful_conditions", "test_stateful_condition_summary",
        "test_sfr_context", "test_sfr_summary", "test_stateful_sequence_workflow",
        "test_aoi_body_context", "test_aoi_body_summary", "test_aoi_body_workflow",
    ),
    "helpers": (
        "test_minimize_l5x", "test_profile_values", "test_review_regressions",
        "test_rung_inventory", "test_rung_syntax", "test_summarize_xml", "test_write_skeleton",
    ),
}


def _count(value: object) -> bool:
    return type(value) is int and 0 <= value <= _MAX_COUNT


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and len(value) <= MAX_ID_LENGTH and _IDENTIFIER.fullmatch(value) is not None


def validate_test_result(payload: object, *, allow_unavailable: bool = False) -> None:
    """Reject extra fields, free text and inconsistent pass/fail accounting."""
    invalid = "Invalid structured test result."
    if not isinstance(payload, dict) or payload.keys() != _RESULT_KEYS:
        raise ValueError(invalid)
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ValueError(invalid)
    status = payload["status"]
    if not isinstance(status, str):
        raise ValueError(invalid)
    identifiers = payload["failed_test_ids"]
    omitted = payload["failure_ids_omitted"]
    if (not isinstance(identifiers, list) or len(identifiers) > MAX_FAILED_IDS
            or any(not _valid_id(value) for value in identifiers)
            or len(set(identifiers)) != len(identifiers) or not _count(omitted)):
        raise ValueError(invalid)
    if status in {"runner_error", "not_run"}:
        if not allow_unavailable or payload["counts"] is not None or identifiers or omitted:
            raise ValueError(invalid)
        return
    if status not in {"passed", "failed"}:
        raise ValueError(invalid)
    counts = payload["counts"]
    if not isinstance(counts, dict) or counts.keys() != _COUNT_KEYS or any(not _count(v) for v in counts.values()):
        raise ValueError(invalid)
    failures = counts["failures"] + counts["errors"] + counts["unexpected_successes"]
    if status == "passed":
        if failures or identifiers or omitted:
            raise ValueError(invalid)
    elif failures == 0 or not identifiers or len(identifiers) + omitted > failures:
        raise ValueError(invalid)
    if omitted and len(identifiers) != MAX_FAILED_IDS:
        raise ValueError(invalid)
    # Subtests are events, not separate tests: failures, errors and even skipped
    # events can outnumber tests_run. Do not subtract them to invent pass counts.


def unavailable_result(status: str) -> dict[str, Any]:
    """Construct an explicit result for a suite which did not complete."""
    if status not in {"runner_error", "not_run"}:
        raise ValueError("Invalid unavailable test status.")
    return {
        "schema_version": 1, "status": status, "counts": None,
        "failed_test_ids": [], "failure_ids_omitted": 0,
    }


def render_test_result(payload: object, *, allow_unavailable: bool = False) -> str:
    validate_test_result(payload, allow_unavailable=allow_unavailable)
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if len(rendered.encode("utf-8")) > MAX_RESULT_BYTES:
        raise ValueError("Structured test result exceeds its size limit.")
    return rendered


def _base_test_id(test: unittest.TestCase) -> str:
    """Use a case's code identity, never an overridable id or subtest repr."""
    case_type = type(test)
    method = getattr(test, "_testMethodName", None)
    if not isinstance(method, str) or not any(method in base.__dict__ for base in case_type.__mro__):
        return _FALLBACK_ID
    identifier = f"{case_type.__module__}.{case_type.__qualname__}.{method}"
    return identifier if _valid_id(identifier) else _FALLBACK_ID


class StructuredTestResult(unittest.TextTestResult):
    """Capture only parent case identities for failed unittest events."""

    def __init__(self, stream: TextIO, descriptions: bool, verbosity: int) -> None:
        super().__init__(stream, descriptions, verbosity)
        self.failed_case_ids: list[str] = []
        self._seen_failed_ids: set[str] = set()
        self.failure_ids_omitted = 0

    def _record_failure(self, test: unittest.TestCase) -> None:
        identifier = _base_test_id(test)
        if identifier in self._seen_failed_ids:
            return
        self._seen_failed_ids.add(identifier)
        if len(self.failed_case_ids) < MAX_FAILED_IDS:
            self.failed_case_ids.append(identifier)
        else:
            self.failure_ids_omitted += 1

    def addFailure(self, test: unittest.TestCase, err: tuple) -> None:
        self._record_failure(test)
        super().addFailure(test, err)

    def addError(self, test: unittest.TestCase, err: tuple) -> None:
        self._record_failure(test)
        super().addError(test, err)

    def addUnexpectedSuccess(self, test: unittest.TestCase) -> None:
        self._record_failure(test)
        super().addUnexpectedSuccess(test)

    def addSubTest(self, test: unittest.TestCase, subtest: unittest.TestCase, err: tuple | None) -> None:
        if err is not None:
            self._record_failure(test)
        super().addSubTest(test, subtest, err)

    def as_payload(self) -> dict[str, Any]:
        payload = {
            "schema_version": 1,
            "status": "passed" if self.wasSuccessful() else "failed",
            "counts": {
                "tests_run": self.testsRun,
                "failures": len(self.failures),
                "errors": len(self.errors),
                "skipped": len(self.skipped),
                "expected_failures": len(self.expectedFailures),
                "unexpected_successes": len(self.unexpectedSuccesses),
            },
            "failed_test_ids": list(self.failed_case_ids),
            "failure_ids_omitted": self.failure_ids_omitted,
        }
        validate_test_result(payload)
        return payload


def run_suite(suite: unittest.TestSuite, *, stream: TextIO) -> dict[str, Any]:
    """Execute an already-discovered suite; stream is for private diagnostics."""
    result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=StructuredTestResult).run(suite)
    return result.as_payload()


def _checkout_root() -> Path:
    location = Path(__file__).resolve()
    for parent in location.parents:
        if parent / "python-parser" / "src" / "plc_workbench" / "work_check_tests.py" == location:
            return parent
    raise ValueError("Test execution requires a source checkout.")


def _load_work_machine_suite(root: Path, name: str) -> unittest.TestSuite:
    """Load exact reviewed modules, without discovering or importing others."""
    directory = root / ("python-parser/tests" if name == "application" else "tools/l5x_inspect/tests")
    loader = unittest.TestLoader()
    selected = unittest.TestSuite()
    original_path = list(sys.path)
    sys.path.insert(0, str(directory))
    try:
        for module_name in WORK_MACHINE_MODULES[name]:
            module_path = directory / f"{module_name}.py"
            if not module_path.is_file():
                raise ValueError("A selected test module is missing.")
            cached = sys.modules.get(module_name)
            if cached is not None and Path(getattr(cached, "__file__", "")).resolve() != module_path.resolve():
                raise ValueError("A selected test module was loaded from another directory.")
            tests = loader.loadTestsFromName(module_name)
            if tests.countTestCases() == 0:
                raise ValueError("A selected test module contains no tests.")
            selected.addTests(tests)
    finally:
        sys.path[:] = original_path
    if selected.countTestCases() == 0:
        raise ValueError("No parser tests were selected.")
    return selected


def _publish_result(output: Path, payload: object) -> None:
    """Atomically create a new result, never overwrite a prior run."""
    encoded = render_test_result(payload).encode("utf-8")
    temporary: Path | None = None
    destination = output.expanduser()
    if destination.suffix.lower() != ".json" or destination.exists() or destination.is_symlink():
        raise ValueError("Test result requires a new JSON output file.")
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor, filename = tempfile.mkstemp(prefix=".plc-tests-", suffix=".pending", dir=destination.parent)
        temporary = Path(filename)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, destination)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run audited local parser tests with bounded JSON results.")
    parser.add_argument("--suite", choices=("application", "helpers"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        root = _checkout_root()
        suite = _load_work_machine_suite(root, arguments.suite)
        if suite.countTestCases() == 0:
            raise ValueError("No parser tests were selected.")
        payload = run_suite(suite, stream=sys.stderr)
        _publish_result(arguments.output, payload)
    except (OSError, ValueError, RuntimeError, ImportError):
        print("Could not complete the structured test run; inspect the private log.", file=sys.stderr)
        return 2
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
