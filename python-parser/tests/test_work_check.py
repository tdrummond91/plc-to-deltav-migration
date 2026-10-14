"""Synthetic workflow tests: no plant files, real checkout writes or network."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
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

    def test_feature_branch_requires_pc_suffix_without_reading_upstream(self) -> None:
        for branch in ("main", "feature"):
            with patch.object(work_check, "_git", return_value=branch):
                with self.assertRaises(work_check.WorkCheckError):
                    work_check._branch(Path("."))
        with patch.object(work_check, "_git", return_value=BRANCH) as git:
            self.assertEqual(work_check._branch(Path(".")), BRANCH)
        git.assert_called_once_with(Path("."), "symbolic-ref", "--quiet", "--short", "HEAD")

    def _workflow(self, root: Path, suite_results: list[dict], *, pin_failure: bool = False):
        source = root / "toy.L5X"
        source.write_bytes(SOURCE)
        calls: list[tuple[str, ...]] = []
        published: list[dict] = []
        def git(checkout, *args, **kwargs):
            calls.append(args)
            self.assertIn(args[0], {"rev-parse", "status", "symbolic-ref"})
            if args == ("rev-parse", "HEAD"):
                return COMMIT
            return ""

        def publish(path, rendered, **kwargs):
            self.assertEqual(path.parent, root / "public" / "inspection" / "local")
            published.append(json.loads(rendered))

        with ExitStack() as stack:
            stack.enter_context(patch.object(work_check, "_git", side_effect=git))
            stack.enter_context(patch.object(work_check, "_branch", return_value=BRANCH))
            pin = stack.enter_context(patch.object(work_check, "_check_pinned"))
            if pin_failure:
                pin.side_effect = [None, work_check.WorkCheckError("changed during tests")]
            stack.enter_context(patch.object(work_check, "_remember_source"))
            stack.enter_context(patch.object(work_check, "_run_suite", side_effect=suite_results))
            analysis = stack.enter_context(patch.object(work_check, "_analyze", return_value=report()["analysis"]))
            stack.enter_context(patch("plc_workbench.summary_output.publish_summary", side_effect=publish))
            stack.enter_context(redirect_stdout(io.StringIO()))
            try:
                outcome = work_check.run_check(root, str(source))
            except work_check.WorkCheckError as exc:
                outcome = exc
        return outcome, calls, published, analysis

    def test_failed_suite_saves_local_report_without_analysis_or_git_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            outcome, calls, published, analysis = self._workflow(Path(folder).resolve(), [test_result("failed"), test_result()])
        self.assertEqual(outcome, 1)
        analysis.assert_not_called()
        self.assertEqual(published[0]["tests"]["helpers"]["status"], "passed")
        self.assertEqual(published[0]["analysis"]["status"], "not_run")
        self.assertFalse(any(call[0] in {"add", "commit", "fetch", "pull", "push", "reset", "stash"} for call in calls))

    def test_success_saves_valid_report_without_git_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            outcome, calls, published, analysis = self._workflow(Path(folder).resolve(), [test_result(), test_result()])
        self.assertEqual(outcome, 0)
        analysis.assert_called_once()
        work_check.validate_work_check_report(published[0])
        self.assertFalse(any(call[0] in {"add", "commit", "fetch", "pull", "push"} for call in calls))

    def test_changed_code_prevents_publication_and_commit(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            outcome, calls, published, analysis = self._workflow(Path(folder).resolve(), [test_result(), test_result()], pin_failure=True)
        self.assertIsInstance(outcome, work_check.WorkCheckError)
        self.assertEqual(published, [])
        self.assertFalse(any(call[0] in {"add", "commit", "push"} for call in calls))


class LocalReportTests(unittest.TestCase):
    def test_repeated_local_runs_preserve_git_state_with_unreachable_origin(self) -> None:
        git = shutil.which("git")
        if git is None:
            self.skipTest("Git is required for local repository integration")
        with tempfile.TemporaryDirectory(prefix="plc-local-report-") as folder:
            base = Path(folder).resolve()
            checkout = base / "checkout"
            remote = base / "remote.git"
            checkout.mkdir()
            environment = {key: value for key, value in os.environ.items()
                           if not key.upper().startswith("GIT_")}
            environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                               GIT_TERMINAL_PROMPT="0")

            def command(*args: str, root: Path = checkout) -> str:
                return subprocess.run([git, "-C", str(root), *args], env=environment,
                                      check=True, capture_output=True, text=True,
                                      timeout=30).stdout.strip()

            command("init", "-b", BRANCH)
            command("config", "user.name", "Synthetic Test")
            command("config", "user.email", "synthetic@example.invalid")
            command("config", "commit.gpgsign", "false")
            (checkout / ".gitignore").write_text("confidential/\npublic/inspection/local/\n", encoding="utf-8")
            command("add", ".gitignore")
            command("commit", "-m", "Synthetic local report fixture")
            command("clone", "--bare", str(checkout), str(remote))
            command("remote", "add", "origin", str(remote))
            command("fetch", "origin")
            command("branch", "--set-upstream-to", f"origin/{BRANCH}")
            remote_head = command("rev-parse", "HEAD", root=remote)
            command("remote", "set-url", "origin", str(base / "missing-origin.git"))
            source = checkout / "confidential" / "plc-code" / "toy.L5X"
            source.parent.mkdir(parents=True)
            source.write_bytes(SOURCE)
            real_git = work_check._git

            def checked_git(root: Path, *args: str, **kwargs) -> str:
                self.assertIn(args[0], {"rev-parse", "status", "symbolic-ref"}, "Only local Git reads are allowed")
                return real_git(root, *args, **kwargs)

            seen_reports: dict[Path, bytes] = {}
            for suite_status in ("passed", "failed", "passed"):
                with self.subTest(suite_status=suite_status):
                    before = command("rev-parse", "HEAD")
                    output = io.StringIO()
                    with patch.dict(os.environ, environment, clear=True), \
                            patch.object(work_check, "_git", side_effect=checked_git), \
                            patch.object(work_check, "_run_suite", side_effect=[test_result(suite_status), test_result()]), \
                            redirect_stdout(output):
                        code = work_check.run_check(checkout, None if seen_reports else str(source))
                    self.assertEqual(code, 0 if suite_status == "passed" else 1)
                    self.assertEqual(command("rev-parse", "HEAD"), before)
                    self.assertEqual(command("rev-parse", "HEAD", root=remote), remote_head)
                    self.assertEqual(command("status", "--porcelain"), "")
                    reports = set((checkout / "public" / "inspection" / "local").glob("work-check-*.json"))
                    new_reports = reports - seen_reports.keys()
                    self.assertEqual(len(new_reports), 1)
                    for path, contents in seen_reports.items():
                        self.assertEqual(path.read_bytes(), contents)
                    new_report = new_reports.pop()
                    saved = json.loads(new_report.read_text(encoding="utf-8"))
                    seen_reports[new_report] = new_report.read_bytes()
                    work_check.validate_work_check_report(saved)
                    self.assertEqual(saved["tool_revision"]["commit"], before)
                    self.assertEqual(saved["tests"]["application"]["status"], suite_status)
                    self.assertIn("Nothing was staged, committed or pushed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
