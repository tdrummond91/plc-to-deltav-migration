"""Synthetic workflow tests: no plant files, real checkout writes or network."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import work_check
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.references import analyze_references
from plc_workbench.reference_summary import build_reference_summary


COMMIT = "a" * 40
NEW_COMMIT = "b" * 40
BRANCH = "feat/check-example-pc"
RUN_ID = "20261013T120000Z-1234abcd"
SOURCE = b'<RSLogix5000Content><Controller Name="Toy"><Programs><Program Name="P"><Routines><Routine Name="R" Type="RLL"><RLLContent><Rung Number="0"><Text>NOP();</Text></Rung></RLLContent></Routine></Routines></Program></Programs></Controller></RSLogix5000Content>'


def test_result(status: str = "passed") -> dict:
    failed = status == "failed"
    return {
        "schema_version": 1, "status": status,
        "counts": {"tests_run": 3, "failures": int(failed), "errors": 0, "skipped": 0,
                   "expected_failures": 0, "unexpected_successes": 0},
        "failed_test_ids": ["test_demo.Demo.test_example"] if failed else [],
        "failure_ids_omitted": 0,
    }


def reference_summary() -> dict:
    inventory = analyze_snapshot(snapshot_from_bytes(SOURCE))
    return build_reference_summary(inventory, analyze_references(inventory), revision={"commit": COMMIT, "worktree": "clean"})


def report() -> dict:
    summary = reference_summary()
    return {
        "schema_version": 1, "report_kind": "l5x_work_machine_check", "workflow_version": "work-check-1",
        "run_id": RUN_ID, "tool_revision": {"commit": COMMIT, "worktree": "clean"},
        "tests": {"application": test_result(), "helpers": test_result()},
        "analysis": {"status": summary["status"], "failure_code": None, "private_run_saved": True, "reference_summary": summary},
        "status": "passed" if summary["status"] == "complete" else "partial",
    }


class ReportTests(unittest.TestCase):
    def test_round_trip_and_closed_schema(self) -> None:
        payload = report()
        self.assertEqual(json.loads(work_check.render_work_check_report(payload)), payload)
        payload["source_path"] = "SECRET"
        with self.assertRaises(ValueError):
            work_check.render_work_check_report(payload)

    def test_rejects_false_success_and_mismatched_revision(self) -> None:
        payload = report()
        payload["tests"]["application"] = test_result("failed")
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)
        payload = report()
        payload["tool_revision"]["commit"] = NEW_COMMIT
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_rejects_unapproved_analysis_text(self) -> None:
        payload = report()
        payload["status"] = "failed"
        payload["analysis"] = {"status": "failed", "failure_code": "private exception value", "private_run_saved": False, "reference_summary": None}
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_failed_tests_require_no_analysis(self) -> None:
        payload = report()
        payload["tests"]["application"] = test_result("failed")
        payload["status"] = "failed"
        payload["analysis"] = {"status": "not_run", "failure_code": None, "private_run_saved": False, "reference_summary": None}
        work_check.validate_work_check_report(payload)
        payload["analysis"]["private_run_saved"] = True
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_rejects_bool_version_and_extra_nested_test_data(self) -> None:
        for mutate in (lambda value: value.update(schema_version=True),
                       lambda value: value["tests"]["application"].update(traceback="SECRET")):
            payload = report()
            mutate(payload)
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)

    def test_analysis_failure_can_record_previously_saved_private_run(self) -> None:
        payload = report()
        payload["analysis"] = {"status": "failed", "failure_code": "summary_error", "private_run_saved": True, "reference_summary": None}
        payload["status"] = "failed"
        work_check.validate_work_check_report(payload)
        payload["analysis"]["failure_code"] = "read_error"
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_publisher_accepts_report_and_preserves_existing_output(self) -> None:
        from plc_workbench.summary_output import SummaryOutputError, publish_summary
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "report.json"
            rendered = work_check.render_work_check_report(report())
            publish_summary(destination, rendered, input_path=Path(folder) / "toy.L5X")
            self.assertEqual(destination.read_text(encoding="utf-8"), rendered)
            with self.assertRaises(SummaryOutputError):
                publish_summary(destination, rendered, input_path=Path(folder) / "toy.L5X")
            self.assertEqual(destination.read_text(encoding="utf-8"), rendered)

    def test_publisher_rejects_private_fields_before_creating_output(self) -> None:
        from plc_workbench.summary_output import SummaryOutputError, publish_summary
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "new-directory" / "report.json"
            payload = report()
            payload["private_source"] = "SECRET"
            with self.assertRaises(SummaryOutputError):
                publish_summary(destination, json.dumps(payload), input_path=Path(folder) / "toy.L5X")
            self.assertFalse(destination.exists())
            self.assertFalse(destination.parent.exists())


class DiagnosticReportTests(unittest.TestCase):
    def test_returned_schema3_timer_sample_remains_readable_unchanged(self) -> None:
        path = Path(__file__).resolve().parents[2] / "public/inspection/work-check-20261014T075024Z-a11d87b8.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["analysis"]["reference_summary"]["schema_version"], 3)
        self.assertEqual(payload["diagnostic_sample"], {
            "kind": "direct_malformed_operand", "opcode": "TON", "argument_index": 1, "raw_text": "?",
        })
        self.assertEqual(json.loads(work_check.render_work_check_report(payload)), payload)

    def test_current_analysis_excludes_timer_placeholders_from_sample(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / "toy.L5X"
            source.write_bytes(SOURCE.replace(b"NOP();", b"TON(ToyTimer,?,?);"))
            result = work_check._analyze(root, source, root, {"commit": COMMIT, "worktree": "clean"})
            self.assertIsNone(result["diagnostic_sample"])
            nested = result["reference_summary"]
            self.assertEqual(nested["schema_version"], 12)
            self.assertEqual(nested["analyzer_version"], "source-references-9")
            self.assertEqual(nested["operands"]["by_status"]["non_data"], 2)
            self.assertEqual(nested["operands"]["by_reason"]["unsupported_address"]["malformed_address"], 0)

    def sample_report(self, reference_version: int = 12) -> dict:
        from plc_workbench.diagnostic_sample import build_diagnostic_sample
        inventory = analyze_snapshot(snapshot_from_bytes(SOURCE.replace(b"NOP();", b"TON(ToyTimer,Preset?,?);")))
        references = analyze_references(inventory)
        nested = build_reference_summary(inventory, references, revision={"commit": COMMIT, "worktree": "clean"})
        if reference_version < 12:
            del nested['routine_graph']
        if reference_version < 11:
            del nested['routine_target_metadata']
        if reference_version < 10:
            del nested['routine_targets']
        if reference_version < 9:
            del nested['routine_instruction_shapes']
        if reference_version in (3, 4, 5):
            self.assertEqual(nested['operands']['by_status'].pop('system_flag'), 0)
        if reference_version in (3, 4, 5, 6, 7, 8, 9, 10, 11):
            nested.update(schema_version=reference_version,
                          exporter_version=f"reference-summary-{reference_version}",
                          analyzer_version=f"source-references-{7 if reference_version == 9 else 8 if reference_version in (10, 11) else reference_version - 1}")
        if reference_version in (3, 4):
            del nested["rack_candidates"]
            source = nested["source_summary"]
            source.update(schema_version=3, exporter_version="aggregate-summary-3",
                          parser_version="source-inventory-2")
            for key in ("module_rack_connections", "module_rack_input_aliases", "module_rack_output_aliases"):
                del source["counts"][key]
        elif reference_version not in (5, 6, 7, 8, 9, 10, 11, 12):
            raise ValueError("Unsupported diagnostic fixture version.")
        payload = report()
        payload.update(schema_version=2, workflow_version="work-check-2", status="partial",
                       diagnostic_sample=build_diagnostic_sample(inventory, references))
        payload["analysis"].update(status="partial", reference_summary=nested)
        return payload

    def test_v2_sample_round_trips_through_publication(self) -> None:
        from plc_workbench.summary_output import publish_summary
        payload = self.sample_report()
        self.assertEqual(payload["diagnostic_sample"]["raw_text"], "Preset?")
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.json"
            publish_summary(output, work_check.render_work_check_report(payload), input_path=Path(folder) / "toy.L5X")
            self.assertEqual(json.loads(output.read_text()), payload)

    def test_current_and_schema4_reject_recognized_timer_samples_but_schema3_preserves_them(self) -> None:
        for version in (3, 4, 5, 6, 7, 8, 9, 10, 11, 12):
            for raw in ("?", " ? "):
                for index in (1, 2):
                    payload = self.sample_report(version)
                    payload["diagnostic_sample"].update(raw_text=raw, argument_index=index)
                    with self.subTest(version=version, raw=raw, index=index):
                        if version == 3:
                            # This vocabulary was legitimately malformed under analyzer 2.
                            work_check.validate_work_check_report(payload)
                        else:
                            with self.assertRaises(ValueError):
                                work_check.validate_work_check_report(payload)

    def test_v1_and_v2_null_sample_are_supported_without_rewriting_history(self) -> None:
        legacy = report()
        self.assertEqual(json.loads(work_check.render_work_check_report(legacy)), legacy)
        current = dict(legacy, schema_version=2, workflow_version="work-check-2", diagnostic_sample=None)
        self.assertEqual(json.loads(work_check.render_work_check_report(current)), current)

    def test_version_hybrids_and_extra_sample_fields_are_rejected(self) -> None:
        for mutate in (lambda p: p.pop("diagnostic_sample"),
                       lambda p: p.update(schema_version=1),
                       lambda p: p.update(workflow_version="work-check-1"),
                       lambda p: p["diagnostic_sample"].update(rung="PRIVATE_RUNG")):
            payload = self.sample_report()
            mutate(payload)
            with self.assertRaises(ValueError):
                work_check.render_work_check_report(payload)

    def test_failure_reports_require_null_sample(self) -> None:
        payload = self.sample_report()
        payload["tests"]["application"] = test_result("failed")
        payload["analysis"] = {"status": "not_run", "failure_code": None,
                               "private_run_saved": False, "reference_summary": None}
        payload["status"] = "failed"
        with self.assertRaises(ValueError):
            work_check.render_work_check_report(payload)
        payload["diagnostic_sample"] = None
        work_check.validate_work_check_report(payload)

    def test_sample_requires_matching_observed_instruction_and_malformed_population(self) -> None:
        payload = self.sample_report()
        payload["diagnostic_sample"]["opcode"] = "RTO"
        with self.assertRaises(ValueError):
            work_check.render_work_check_report(payload)
        payload = self.sample_report()
        payload["analysis"] = report()["analysis"]
        payload["status"] = report()["status"]
        with self.assertRaises(ValueError):
            work_check.render_work_check_report(payload)

    def test_analysis_uses_captured_records_for_single_actual_operand(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / "toy.L5X"
            source.write_bytes(SOURCE.replace(b"NOP();", b"TON(ToyTimer,Preset?,?);"))
            with patch.object(work_check, "capture_snapshot", wraps=work_check.capture_snapshot) as capture:
                result = work_check._analyze(root, source, root, {"commit": COMMIT, "worktree": "clean"})
            capture.assert_called_once_with(source)
            self.assertEqual(result["diagnostic_sample"], {
                "kind": "direct_malformed_operand", "opcode": "TON", "argument_index": 1, "raw_text": "Preset?",
            })
            self.assertNotIn("ToyTimer", json.dumps(result))


class SourceAndAnalysisTests(unittest.TestCase):
    def test_config_cannot_escape_git_directory(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with patch.object(work_check, "_git", side_effect=["public/settings.json", str(root / ".git")]):
                with self.assertRaises(work_check.WorkCheckError):
                    work_check._config_path(root)

    def test_explicit_and_remembered_paths(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / "confidential" / "plc-code" / "toy.L5X"
            source.parent.mkdir(parents=True)
            source.write_bytes(SOURCE)
            config = root / "local-config.json"
            with patch.object(work_check, "_config_path", return_value=config):
                self.assertEqual(work_check._source_path(root, "toy.L5X"), source)
                work_check._remember_source(root, source)
                self.assertEqual(work_check._source_path(root, None), source)
                config.write_text('{"schema_version":1,"source":"relative.L5X"}', encoding="utf-8")
                with self.assertRaisesRegex(work_check.WorkCheckError, "No usable saved source"):
                    work_check._source_path(root, None)

    def test_missing_source_is_fixed_error(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(work_check.WorkCheckError) as raised:
                work_check._source_path(Path(folder), "PRIVATE_FILE.L5X")
            self.assertNotIn("PRIVATE_FILE", str(raised.exception))

    def test_analysis_captures_once_and_saves_same_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / "toy.L5X"
            source.write_bytes(SOURCE)
            with patch.object(work_check, "capture_snapshot", wraps=work_check.capture_snapshot) as capture, \
                    patch.object(work_check, "save_run") as save:
                outcome = work_check._analyze(root, source, root, {"commit": COMMIT, "worktree": "clean"})
            capture.assert_called_once_with(source)
            self.assertIn(outcome["status"], ("complete", "partial"))
            self.assertTrue(outcome["private_run_saved"])
            self.assertEqual(save.call_args.args[1].data, SOURCE)
            self.assertEqual(save.call_args.args[2].snapshot["id"], save.call_args.args[1].id)

    def test_raw_analysis_exception_is_only_in_private_log(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with patch.object(work_check, "capture_snapshot", side_effect=OSError("SECRET_SOURCE_VALUE")):
                outcome = work_check._analyze(root, root / "toy.L5X", root, {"commit": COMMIT, "worktree": "clean"})
            self.assertEqual(outcome["failure_code"], "read_error")
            self.assertNotIn("SECRET_SOURCE_VALUE", json.dumps(outcome))
            self.assertIn("SECRET_SOURCE_VALUE", (root / "analysis.log").read_text(encoding="utf-8"))

    def test_log_write_failure_does_not_discard_analysis_failure(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with patch.object(work_check, "capture_snapshot", side_effect=OSError("PRIVATE_READ_ERROR")), \
                    patch.object(Path, "open", side_effect=OSError("disk full")):
                outcome = work_check._analyze(root, root / "toy.L5X", root, {"commit": COMMIT, "worktree": "clean"})
            self.assertEqual(outcome["failure_code"], "read_error")
            self.assertEqual(outcome["status"], "failed")


class SuiteTests(unittest.TestCase):
    def _run(self, root: Path, payload: dict, code: int = 0) -> dict:
        def completed(*args, **kwargs):
            (root / "application-tests.json").write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.CompletedProcess(args[0], code)
        with patch.object(work_check.subprocess, "run", side_effect=completed):
            return work_check._run_suite(root, root, "application")

    def test_passed_and_failed_results_have_expected_exit(self) -> None:
        for status, code in (("passed", 0), ("failed", 1)):
            with tempfile.TemporaryDirectory() as folder:
                payload = test_result(status)
                self.assertEqual(self._run(Path(folder), payload, code), payload)

    def test_malformed_result_and_wrong_exit_become_runner_error(self) -> None:
        for payload, code in ((dict(test_result(), private_value="SECRET"), 0), (test_result(), 1)):
            with tempfile.TemporaryDirectory() as folder:
                outcome = self._run(Path(folder), payload, code)
                self.assertEqual(outcome["status"], "runner_error")
                self.assertIsNone(outcome["counts"])
                self.assertNotIn("SECRET", json.dumps(outcome))


class GitAndWorkflowTests(unittest.TestCase):
    def test_raw_git_output_preserves_exact_report_whitespace(self) -> None:
        contents = b'  {"synthetic": true}\n\n'
        with patch.object(work_check.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=contents)):
            self.assertEqual(work_check._git(Path("."), "show", ":report.json", raw=True), contents.decode("utf-8"))
            self.assertEqual(work_check._git(Path("."), "show", ":report.json"), contents.decode("utf-8").strip())

    def test_git_preserves_ssh_auth_but_removes_repository_overrides(self) -> None:
        with patch.dict(os.environ, {"GIT_SSH_COMMAND": "ssh -i local-test-key", "GIT_INDEX_FILE": "unrelated-index"}), \
                patch.object(work_check.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=b"")) as run:
            work_check._git(Path("."), "status")
        environment = run.call_args.kwargs["env"]
        self.assertEqual(environment["GIT_SSH_COMMAND"], "ssh -i local-test-key")
        self.assertNotIn("GIT_INDEX_FILE", environment)

    def test_git_failure_records_raw_error_only_in_private_log(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            error = subprocess.CalledProcessError(1, ["git", "status"], stderr=b"PRIVATE_GIT_DIAGNOSTIC")
            with patch.object(work_check.subprocess, "run", side_effect=error):
                with self.assertRaises(work_check.WorkCheckError) as raised:
                    work_check._git(root, "status", logs=root)
            self.assertIn("Git status failed", str(raised.exception))
            self.assertNotIn("PRIVATE_GIT_DIAGNOSTIC", str(raised.exception))
            self.assertIn("PRIVATE_GIT_DIAGNOSTIC", (root / "git.log").read_text(encoding="utf-8"))

    def test_pinning_rejects_changed_head_and_unrelated_changes(self) -> None:
        for head, status in ((NEW_COMMIT, ""), (COMMIT, "?? unrelated.txt\0"), (COMMIT, "M  tracked.txt\0")):
            with patch.object(work_check, "_branch", return_value=BRANCH), \
                    patch.object(work_check, "_git", side_effect=[head, status]):
                with self.assertRaises(work_check.WorkCheckError):
                    work_check._check_pinned(Path("."), BRANCH, COMMIT)

    def test_report_pin_accepts_only_its_new_untracked_or_staged_file(self) -> None:
        path = f"public/inspection/work-check-{RUN_ID}.json"
        for status in (f"?? {path}\0", f"A  {path}\0"):
            with self.subTest(status=status), patch.object(work_check, "_branch", return_value="main"), \
                    patch.object(work_check, "_git", side_effect=[COMMIT, status]):
                work_check._check_pinned(Path("."), "main", COMMIT, report_path=path)
        for status in ("", f"AM {path}\0", f" M {path}\0", "?? another.json\0",
                       f"A  {path}\0M  unrelated.txt\0", f"?? {path}\0 M unrelated.txt\0"):
            with self.subTest(status=status), patch.object(work_check, "_branch", return_value="main"), \
                    patch.object(work_check, "_git", side_effect=[COMMIT, status]):
                with self.assertRaises(work_check.WorkCheckError):
                    work_check._check_pinned(Path("."), "main", COMMIT, report_path=path)

    def test_any_named_branch_is_accepted_without_reading_upstream(self) -> None:
        for branch in ("main", "master", "feature", BRANCH):
            with self.subTest(branch=branch), patch.object(work_check, "_git", return_value=branch) as git:
                self.assertEqual(work_check._branch(Path(".")), branch)
            git.assert_called_once_with(Path("."), "symbolic-ref", "--quiet", "--short", "HEAD")

    def test_detached_head_failure_prevents_source_reads_and_analysis(self) -> None:
        with patch.object(work_check, "_git", side_effect=work_check.WorkCheckError("Git symbolic-ref failed")), \
                patch.object(work_check, "_source_path") as source, \
                patch.object(work_check, "_run_suite") as tests, \
                patch.object(work_check, "_analyze") as analysis:
            with self.assertRaises(work_check.WorkCheckError):
                work_check.run_check(Path("."), "toy.L5X")
        source.assert_not_called()
        tests.assert_not_called()
        analysis.assert_not_called()

    def test_pinning_rejects_a_changed_named_branch(self) -> None:
        with patch.object(work_check, "_branch", return_value="another-branch"):
            with self.assertRaisesRegex(work_check.WorkCheckError, "branch or commit changed"):
                work_check._check_pinned(Path("."), "main", COMMIT)

    def _workflow(self, root: Path, suite_results: list[dict], *, pin_failure: bool = False,
                  commit_parent: str = COMMIT, extra_commit_path: bool = False):
        source = root / "toy.L5X"
        source.write_bytes(SOURCE)
        calls: list[tuple[str, ...]] = []
        published: list[dict] = []
        saved_report: str | None = None
        saved_rendered: str | None = None
        committed = False
        def git(checkout, *args, **kwargs):
            nonlocal committed
            calls.append(args)
            self.assertIn(args[0], {"rev-parse", "status", "symbolic-ref", "add", "commit", "diff-tree", "show"})
            if args == ("rev-parse", "HEAD"):
                return NEW_COMMIT if committed else COMMIT
            if args == ("rev-parse", "HEAD^"):
                return commit_parent
            if args[0] == "commit":
                committed = True
            if args[0] == "diff-tree":
                return f"{saved_report}\nunrelated.txt" if extra_commit_path else saved_report
            if args[0] == "show":
                self.assertTrue(kwargs.get("raw"))
                return saved_rendered
            return ""

        def publish(path, rendered, **kwargs):
            nonlocal saved_report, saved_rendered
            self.assertEqual(path.parent, root / "public" / "inspection")
            saved_report = path.relative_to(root).as_posix()
            saved_rendered = rendered
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(rendered.encode("utf-8"))
            published.append(json.loads(rendered))

        with ExitStack() as stack:
            stack.enter_context(patch.object(work_check, "_git", side_effect=git))
            stack.enter_context(patch.object(work_check, "_branch", return_value=BRANCH))
            pin = stack.enter_context(patch.object(work_check, "_check_pinned"))
            if pin_failure:
                pin.side_effect = [None, work_check.WorkCheckError("changed during tests")]
            stack.enter_context(patch.object(work_check, "_remember_source"))
            stack.enter_context(patch.object(work_check, "_run_suite", side_effect=suite_results))
            from plc_workbench.sfc_structure import analyze_sfc_structure
            from plc_workbench.sfc_summary import build_sfc_summary
            from plc_workbench.access import analyze_access
            from plc_workbench.access_summary import build_access_summary
            snapshot = snapshot_from_bytes(SOURCE)
            inventory = analyze_snapshot(snapshot)
            analysis_payload = report()["analysis"]
            analysis_payload["sfc_structure_summary"] = build_sfc_summary(
                snapshot, inventory, analyze_sfc_structure(snapshot, inventory),
                revision={"commit": COMMIT, "worktree": "clean"})
            references = analyze_references(inventory)
            analysis_payload["access_summary"] = build_access_summary(
                inventory, references, analyze_access(inventory, references),
                revision={"commit": COMMIT, "worktree": "clean"})
            from plc_workbench.tag_data import analyze_tag_data
            from plc_workbench.tag_data_summary import build_tag_data_summary
            from plc_workbench.pid import analyze_pid
            from plc_workbench.pid_summary import build_pid_summary
            from plc_workbench.pid_members import analyze_pid_members
            from plc_workbench.pid_member_summary import build_pid_member_summary
            tag_data = analyze_tag_data(snapshot, inventory)
            analysis_payload["tag_data_summary"] = build_tag_data_summary(
                snapshot, inventory, tag_data,
                revision={"commit": COMMIT, "worktree": "clean"})
            pid = analyze_pid(snapshot, inventory, references, tag_data)
            analysis_payload["pid_summary"] = build_pid_summary(
                snapshot, inventory, references, tag_data, pid,
                revision={"commit": COMMIT, "worktree": "clean"})
            analysis_payload["pid_member_summary"] = build_pid_member_summary(
                snapshot, inventory, references, tag_data, pid,
                analyze_pid_members(snapshot, inventory, references, tag_data, pid),
                revision={"commit": COMMIT, "worktree": "clean"})
            analysis = stack.enter_context(patch.object(work_check, "_analyze", return_value=analysis_payload))
            stack.enter_context(patch("plc_workbench.summary_output.publish_summary", side_effect=publish))
            stack.enter_context(redirect_stdout(io.StringIO()))
            try:
                outcome = work_check.run_check(root, str(source))
            except work_check.WorkCheckError as exc:
                outcome = exc
        return outcome, calls, published, analysis

    def test_failed_suite_commits_only_local_report_without_analysis_or_remote_access(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            outcome, calls, published, analysis = self._workflow(Path(folder).resolve(), [test_result("failed"), test_result()])
        self.assertEqual(outcome, 1)
        analysis.assert_not_called()
        self.assertEqual(published[0]["tests"]["helpers"]["status"], "passed")
        self.assertEqual(published[0]["analysis"]["status"], "not_run")
        self.assertEqual(sum(call[0] == "commit" for call in calls), 1)
        self.assertFalse(any(call[0] in {"fetch", "pull", "push", "reset", "stash"} for call in calls))

    def test_success_commits_only_valid_report_without_remote_access(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            outcome, calls, published, analysis = self._workflow(Path(folder).resolve(), [test_result(), test_result()])
        self.assertEqual(outcome, 0)
        analysis.assert_called_once()
        work_check.validate_work_check_report(published[0])
        added, = [call for call in calls if call[0] == "add"]
        committed, = [call for call in calls if call[0] == "commit"]
        self.assertEqual(added[1], "--")
        self.assertEqual(len(added), 3)
        self.assertTrue(added[2].startswith("public/inspection/work-check-"))
        self.assertIn("--only", committed)
        self.assertEqual(committed[committed.index("--") + 1:], (added[2],))
        self.assertFalse(any(call[0] in {"fetch", "pull", "push"} for call in calls))

    def test_changed_code_prevents_publication_and_commit(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            outcome, calls, published, analysis = self._workflow(Path(folder).resolve(), [test_result(), test_result()], pin_failure=True)
        self.assertIsInstance(outcome, work_check.WorkCheckError)
        self.assertEqual(published, [])
        self.assertFalse(any(call[0] in {"add", "commit", "push"} for call in calls))

    def test_unexpected_commit_parent_or_paths_are_flagged_without_remote_access(self) -> None:
        for options in ({"commit_parent": NEW_COMMIT}, {"extra_commit_path": True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as folder:
                outcome, calls, published, _ = self._workflow(
                    Path(folder).resolve(), [test_result(), test_result()], **options)
            self.assertIsInstance(outcome, work_check.WorkCheckError)
            self.assertIn("Commit history changed unexpectedly", str(outcome))
            self.assertEqual(len(published), 1)
            self.assertEqual(sum(call[0] == "commit" for call in calls), 1)
            self.assertFalse(any(call[0] in {"fetch", "pull", "push", "reset"} for call in calls))


class LocalReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.git = shutil.which("git")
        if self.git is None:
            self.skipTest("Git is required for local repository integration")
        temporary = tempfile.TemporaryDirectory(prefix="plc-local-report-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.checkout = self.base / "checkout"
        self.remote = self.base / "remote.git"
        self.checkout.mkdir()
        self.environment = {key: value for key, value in os.environ.items()
                            if not key.upper().startswith("GIT_")}
        self.environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                                GIT_TERMINAL_PROMPT="0")
        self.command("init", "-b", "main")
        self.command("config", "user.name", "Synthetic Test")
        self.command("config", "user.email", "synthetic@example.invalid")
        self.command("config", "commit.gpgsign", "false")
        (self.checkout / ".gitignore").write_text("confidential/\npublic/inspection/local/\n", encoding="utf-8")
        (self.checkout / "tracked.txt").write_text("Initial synthetic file\n", encoding="utf-8")
        self.command("add", ".gitignore", "tracked.txt")
        self.command("commit", "-m", "Synthetic local report fixture")
        self.command("clone", "--bare", str(self.checkout), str(self.remote))
        self.command("remote", "add", "origin", str(self.remote))
        self.command("fetch", "origin")
        self.command("branch", "--set-upstream-to", "origin/main")
        self.remote_head = self.command("rev-parse", "HEAD", root=self.remote)
        self.command("remote", "set-url", "origin", str(self.base / "missing-origin.git"))
        self.source = self.checkout / "confidential" / "plc-code" / "toy.L5X"
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(SOURCE)
        self.runtime_commands: list[tuple[str, ...]] = []

    def command(self, *args: str, root: Path | None = None) -> str:
        return subprocess.run([self.git, "-C", str(root or self.checkout), *args], env=self.environment,
                              check=True, capture_output=True, text=True, timeout=30).stdout.strip()

    def run_check(self, *, suite_status: str = "passed", remembered: bool = False, before_git=None) -> tuple[int, str]:
        real_git = work_check._git

        def checked_git(root: Path, *args: str, **kwargs) -> str:
            self.runtime_commands.append(args)
            self.assertIn(args[0], {"rev-parse", "status", "symbolic-ref", "add", "commit", "diff-tree", "show"},
                          "Remote access and unrelated Git mutations are forbidden")
            if before_git is not None:
                before_git(args)
            return real_git(root, *args, **kwargs)

        output = io.StringIO()
        self.run_output = output
        with patch.dict(os.environ, self.environment, clear=True), \
                patch.object(work_check, "_git", side_effect=checked_git), \
                patch.object(work_check, "_run_suite", side_effect=[test_result(suite_status), test_result()]), \
                redirect_stdout(output):
            code = work_check.run_check(self.checkout, None if remembered else str(self.source))
        return code, output.getvalue()

    def assert_remote_and_source_unchanged(self) -> None:
        self.assertEqual(self.command("rev-parse", "HEAD", root=self.remote), self.remote_head)
        self.assertEqual(self.source.read_bytes(), SOURCE)
        self.assertFalse(any(command[0] in {"fetch", "pull", "push"} for command in self.runtime_commands))

    def test_repeated_local_runs_on_main_create_report_only_commits_with_unreachable_origin(self) -> None:
        seen_reports: dict[Path, bytes] = {}
        for suite_status in ("passed", "failed", "passed"):
            with self.subTest(suite_status=suite_status):
                before = self.command("rev-parse", "HEAD")
                code, output = self.run_check(suite_status=suite_status, remembered=bool(seen_reports))
                self.assertEqual(code, 0 if suite_status == "passed" else 1)
                self.assertEqual(self.command("symbolic-ref", "--short", "HEAD"), "main")
                self.assertNotEqual(self.command("rev-parse", "HEAD"), before)
                self.assertEqual(self.command("rev-parse", "HEAD^"), before)
                self.assertEqual(self.command("rev-list", "--count", f"{before}..HEAD"), "1")
                self.assertEqual(self.command("status", "--porcelain"), "")
                reports = set((self.checkout / "public" / "inspection").glob("work-check-*.json"))
                new_reports = reports - seen_reports.keys()
                self.assertEqual(len(new_reports), 1)
                for path, contents in seen_reports.items():
                    self.assertEqual(path.read_bytes(), contents)
                new_report = new_reports.pop()
                relative = new_report.relative_to(self.checkout).as_posix()
                self.assertEqual(self.command("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"), relative)
                saved = json.loads(new_report.read_text(encoding="utf-8"))
                seen_reports[new_report] = new_report.read_bytes()
                work_check.validate_work_check_report(saved)
                self.assertEqual(saved["tool_revision"]["commit"], before)
                self.assertEqual(saved["tests"]["application"]["status"], suite_status)
                self.assertIn("locally", output)
                self.assert_remote_and_source_unchanged()

    def assert_failed_commit_preserves_report(self, before_git=None) -> None:
        before = self.command("rev-parse", "HEAD")
        with self.assertRaises(work_check.WorkCheckError):
            self.run_check(before_git=before_git)
        self.assertEqual(self.command("rev-parse", "HEAD"), before)
        report_path, = (self.checkout / "public" / "inspection").glob("work-check-*.json")
        saved = json.loads(report_path.read_text(encoding="utf-8"))
        work_check.validate_work_check_report(saved)
        self.assertEqual(saved["tool_revision"]["commit"], before)
        self.assertEqual(self.command("diff", "--cached", "--name-only"), report_path.relative_to(self.checkout).as_posix())
        self.assertEqual(sum(command[0] == "commit" for command in self.runtime_commands), 1)
        self.assert_remote_and_source_unchanged()

    def test_missing_git_identity_preserves_uncommitted_report_without_remote_access(self) -> None:
        self.command("config", "--unset", "user.name")
        self.command("config", "--unset", "user.email")
        self.command("config", "user.useConfigOnly", "true")
        self.assert_failed_commit_preserves_report()

    def test_commit_failure_preserves_uncommitted_report_without_remote_access(self) -> None:
        def fail_commit(args: tuple[str, ...]) -> None:
            if args[0] == "commit":
                raise work_check.WorkCheckError("Synthetic commit failure")
        self.assert_failed_commit_preserves_report(fail_commit)

    def test_inflight_unstaged_edit_stops_before_report_commit(self) -> None:
        before = self.command("rev-parse", "HEAD")
        def edit_before_add(args: tuple[str, ...]) -> None:
            if args[0] == "add":
                (self.checkout / "tracked.txt").write_text("Unrelated unstaged edit\n", encoding="utf-8")
        with self.assertRaises(work_check.WorkCheckError):
            self.run_check(before_git=edit_before_add)
        self.assertEqual(self.command("rev-parse", "HEAD"), before)
        self.assertIn(" M tracked.txt", self.command("status", "--porcelain").splitlines())
        self.assertFalse(any(command[0] == "commit" for command in self.runtime_commands))
        self.assert_remote_and_source_unchanged()

    def test_report_only_commit_excludes_edit_staged_at_commit_boundary(self) -> None:
        before = self.command("rev-parse", "HEAD")
        def stage_before_commit(args: tuple[str, ...]) -> None:
            if args[0] == "commit":
                self.assertIn("--only", args)
                (self.checkout / "tracked.txt").write_text("Unrelated staged edit\n", encoding="utf-8")
                self.command("add", "tracked.txt")
        with self.assertRaises(work_check.WorkCheckError):
            self.run_check(before_git=stage_before_commit)
        self.assertEqual(self.command("rev-parse", "HEAD^"), before)
        report_path, = (self.checkout / "public" / "inspection").glob("work-check-*.json")
        self.assertEqual(self.command("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"),
                         report_path.relative_to(self.checkout).as_posix())
        self.assertEqual(self.command("diff", "--cached", "--name-only"), "tracked.txt")
        self.assertEqual((self.checkout / "tracked.txt").read_text(encoding="utf-8"), "Unrelated staged edit\n")
        self.assert_remote_and_source_unchanged()

    def change_report_contents(self, relative_path: str) -> None:
        path = self.checkout / relative_path
        altered = json.loads(path.read_text(encoding="utf-8"))
        altered["private_note"] = "PRIVATE_SENTINEL"
        path.write_text(json.dumps(altered), encoding="utf-8")

    def test_report_content_change_before_add_prevents_commit_and_success(self) -> None:
        before = self.command("rev-parse", "HEAD")
        def alter_before_add(args: tuple[str, ...]) -> None:
            if args[0] == "add":
                self.change_report_contents(args[-1])
        with self.assertRaises(work_check.WorkCheckError) as raised:
            self.run_check(before_git=alter_before_add)
        self.assertEqual(self.command("rev-parse", "HEAD"), before)
        self.assertFalse(any(command[0] == "commit" for command in self.runtime_commands))
        report_path, = (self.checkout / "public" / "inspection").glob("work-check-*.json")
        self.assertIn("PRIVATE_SENTINEL", report_path.read_text(encoding="utf-8"))
        self.assertNotIn("PRIVATE_SENTINEL", str(raised.exception))
        self.assertNotIn("Committed work-machine report", self.run_output.getvalue())
        self.assert_remote_and_source_unchanged()

    def test_report_content_change_at_commit_is_flagged_without_history_rollback(self) -> None:
        before = self.command("rev-parse", "HEAD")
        def alter_at_commit(args: tuple[str, ...]) -> None:
            if args[0] == "commit":
                self.change_report_contents(args[-1])
        with self.assertRaises(work_check.WorkCheckError) as raised:
            self.run_check(before_git=alter_at_commit)
        self.assertEqual(self.command("rev-parse", "HEAD^"), before)
        report_path, = (self.checkout / "public" / "inspection").glob("work-check-*.json")
        relative = report_path.relative_to(self.checkout).as_posix()
        self.assertIn("PRIVATE_SENTINEL", self.command("show", f"HEAD:{relative}"))
        self.assertNotIn("PRIVATE_SENTINEL", str(raised.exception))
        self.assertNotIn("Committed work-machine report", self.run_output.getvalue())
        self.assertFalse(any(command[0] in {"reset", "revert"} for command in self.runtime_commands))
        self.assert_remote_and_source_unchanged()

    def test_git_filter_cannot_substitute_unvalidated_staged_report_contents(self) -> None:
        filter_path = self.checkout / ".git" / "synthetic-filter.py"
        filter_path.write_text(
            "import json, sys\n"
            "value = json.load(sys.stdin)\n"
            "value['private_note'] = 'PRIVATE_SENTINEL'\n"
            "json.dump(value, sys.stdout)\n", encoding="utf-8")
        self.command("config", "filter.synthetic.clean", f'"{Path(sys.executable).as_posix()}" "{filter_path.as_posix()}"')
        self.command("config", "filter.synthetic.required", "true")
        (self.checkout / ".git" / "info" / "attributes").write_text(
            "public/inspection/work-check-*.json filter=synthetic\n", encoding="utf-8")
        before = self.command("rev-parse", "HEAD")
        with self.assertRaises(work_check.WorkCheckError) as raised:
            self.run_check()
        self.assertEqual(self.command("rev-parse", "HEAD"), before)
        self.assertFalse(any(command[0] == "commit" for command in self.runtime_commands))
        report_path, = (self.checkout / "public" / "inspection").glob("work-check-*.json")
        relative = report_path.relative_to(self.checkout).as_posix()
        self.assertIn("PRIVATE_SENTINEL", self.command("show", f":{relative}"))
        original = json.loads(report_path.read_text(encoding="utf-8"))
        work_check.validate_work_check_report(original)
        self.assertNotIn("PRIVATE_SENTINEL", str(raised.exception))
        self.assertNotIn("Committed work-machine report", self.run_output.getvalue())
        self.assert_remote_and_source_unchanged()


if __name__ == "__main__":
    unittest.main()
