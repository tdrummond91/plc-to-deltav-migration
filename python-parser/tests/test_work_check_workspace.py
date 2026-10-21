"""Invented-source regressions for the work-check to editor handoff."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from plc_workbench import work_check
from plc_workbench.storage import StorageError
from test_work_check import BRANCH, COMMIT, NEW_COMMIT, SOURCE, test_result


class CompletedRunCallbackTests(unittest.TestCase):
    def test_callback_receives_finalized_exact_run_after_sample_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / "invented.L5X"
            source.write_bytes(SOURCE)
            events: list[str] = []
            received: list[Path] = []
            resolve = work_check.resolve_targeted_samples

            def resolved(*args, **kwargs):
                result = resolve(*args, **kwargs)
                events.append("samples")
                return result

            def completed(path: Path) -> None:
                self.assertEqual(events, ["samples"])
                self.assertTrue((path / "manifest.json").is_file())
                self.assertTrue((path / "review.html").is_file())
                received.append(path)
                events.append("handoff")

            with patch.object(work_check, "resolve_targeted_samples", side_effect=resolved), \
                    redirect_stdout(io.StringIO()):
                outcome = work_check._analyze(
                    root, source, root, {"commit": COMMIT, "worktree": "clean"},
                    on_saved_run=completed)
            self.assertIn(outcome["status"], ("complete", "partial"))
            self.assertEqual(events, ["samples", "handoff"])
            run, = received
            self.assertEqual(run.parent, root / "confidential" / "workspaces" / "work-check")
            self.assertNotIn(str(run), json.dumps(outcome))
            self.assertNotIn("saved_run", outcome)
            self.assertNotIn("run_path", outcome)

    def test_save_and_post_save_summary_failures_never_hand_off_a_run(self) -> None:
        for stage, expected_code, saved in (("save_run", "save_error", False),
                                             ("build_reference_summary", "summary_error", True)):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                source = root / "invented.L5X"
                source.write_bytes(SOURCE)
                callback = Mock()
                error = StorageError("Invented save failure") if not saved else ValueError("Invented summary failure")
                with patch.object(work_check, stage, side_effect=error), redirect_stdout(io.StringIO()):
                    outcome = work_check._analyze(
                        root, source, root, {"commit": COMMIT, "worktree": "clean"},
                        on_saved_run=callback)
                callback.assert_not_called()
                self.assertEqual(outcome["status"], "failed")
                self.assertEqual(outcome["failure_code"], expected_code)
                self.assertEqual(outcome["private_run_saved"], saved)


class WorkspaceHandoffTests(unittest.TestCase):
    def workflow(self, root: Path, *, status: str = "partial", saved: bool = True,
                 handoffs: int = 1, suite_status: str = "passed",
                 corrupt_commit: bool = False, open_workspace: bool = True):
        """Isolate orchestration; parser callbacks are exercised with real data above."""
        source = root / "invented.L5X"
        source.write_bytes(SOURCE)
        exact_run = root / "confidential" / "workspaces" / "work-check" / "run-exact-invented"
        calls: list[tuple[str, ...]] = []
        published: list[dict] = []
        events: list[str] = []
        committed = False
        relative_report = ""
        rendered_report = ""
        analysis_result = {
            "status": status, "failure_code": "summary_error" if status == "failed" else None,
            "private_run_saved": saved, "reference_summary": None,
        }

        def analyze(*args, **kwargs):
            callback = kwargs.get("on_saved_run")
            if callback is not None:
                for unused in range(handoffs):
                    callback(exact_run)
            return deepcopy(analysis_result)

        def publish(path: Path, rendered: str, **kwargs) -> None:
            nonlocal relative_report, rendered_report
            relative_report = path.relative_to(root).as_posix()
            rendered_report = rendered
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(rendered.encode("utf-8"))
            published.append(json.loads(rendered))
            events.append("published")

        def git(checkout: Path, *args: str, **kwargs) -> str:
            nonlocal committed
            calls.append(args)
            self.assertIn(args[0], {"rev-parse", "add", "commit", "diff-tree", "show"},
                          "The work-machine path must not perform remote operations")
            if args == ("rev-parse", "HEAD"):
                return NEW_COMMIT if committed else COMMIT
            if args == ("rev-parse", "HEAD^"):
                return COMMIT
            if args[0] == "commit":
                committed = True
                events.append("committed")
            if args[0] == "diff-tree":
                return relative_report
            if args[0] == "show":
                if args[1].startswith(f"{NEW_COMMIT}:"):
                    events.append("verified")
                    return "Changed committed content" if corrupt_commit else rendered_report
                return rendered_report
            return ""

        def launch(checkout: Path, run: Path, logs: Path) -> int:
            self.assertEqual(events, ["published", "committed", "verified"])
            self.assertEqual(checkout, root)
            self.assertEqual(run, exact_run)
            events.append("opened")
            return 0

        output = io.StringIO()
        errors = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(work_check, "_git", side_effect=git))
            stack.enter_context(patch.object(work_check, "_branch", return_value=BRANCH))
            stack.enter_context(patch.object(work_check, "_check_pinned"))
            stack.enter_context(patch.object(work_check, "_remember_source"))
            stack.enter_context(patch.object(work_check, "_run_suite", side_effect=[test_result(suite_status), test_result()]))
            analyzed = stack.enter_context(patch.object(work_check, "_analyze", side_effect=analyze))
            opened = stack.enter_context(patch.object(work_check, "_open_completed_workspace", side_effect=launch))
            stack.enter_context(patch.object(work_check, "render_work_check_report", side_effect=json.dumps))
            stack.enter_context(patch("plc_workbench.summary_output.publish_summary", side_effect=publish))
            stack.enter_context(redirect_stdout(output))
            stack.enter_context(redirect_stderr(errors))
            try:
                result = work_check.run_check(root, str(source), open_workspace=open_workspace)
            except work_check.WorkCheckError as exc:
                result = exc
        return result, opened, analyzed, published, errors.getvalue(), calls

    def test_complete_and_partial_runs_open_exact_run_after_verified_commit(self) -> None:
        for status in ("complete", "partial"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                result, opened, analyzed, reports, errors, calls = self.workflow(root, status=status)
                self.assertEqual(result, 0)
                opened.assert_called_once()
                analyzed.assert_called_once()
                self.assertEqual(errors, "")
                self.assertEqual(reports[0]["status"], "passed" if status == "complete" else "partial")
                rendered = json.dumps(reports[0])
                self.assertNotIn(str(root), rendered)
                self.assertNotIn("run-exact-invented", rendered)
                self.assertFalse(any(call[0] in {"fetch", "pull", "push"} for call in calls))

    def test_failed_analysis_or_failed_suite_never_opens_an_old_run(self) -> None:
        for options in ({"status": "failed"}, {"suite_status": "failed"}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as folder:
                result, opened, analyzed, reports, errors, calls = self.workflow(Path(folder).resolve(), **options)
                self.assertEqual(result, 1)
                opened.assert_not_called()
                self.assertEqual(reports[0]["status"], "failed")
                if "suite_status" in options:
                    analyzed.assert_not_called()

    def test_absent_ambiguous_or_unsaved_handoff_never_selects_latest_run(self) -> None:
        for options in ({"handoffs": 0}, {"handoffs": 2}, {"saved": False}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as folder:
                result, opened, analyzed, reports, errors, calls = self.workflow(Path(folder).resolve(), **options)
                self.assertEqual(result, 1)
                opened.assert_not_called()
                self.assertIn("exact run", errors)
                self.assertIn("another analysis is not required", errors)

    def test_unverified_commit_prevents_editor_launch(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            result, opened, analyzed, reports, errors, calls = self.workflow(Path(folder).resolve(), corrupt_commit=True)
        self.assertIsInstance(result, work_check.WorkCheckError)
        self.assertIn("Committed report content changed", str(result))
        opened.assert_not_called()

    def test_noninteractive_run_keeps_analysis_call_shape_without_callback(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            result, opened, analyzed, reports, errors, calls = self.workflow(Path(folder).resolve(), open_workspace=False)
        self.assertEqual(result, 0)
        opened.assert_not_called()
        self.assertNotIn("on_saved_run", analyzed.call_args.kwargs)

    def test_editor_launch_receives_exact_run_and_failure_preserves_analysis(self) -> None:
        for failure in (None, 1, RuntimeError("Invented editor failure")):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                run = root / "confidential" / "workspaces" / "work-check" / "run-exact-invented"
                errors = io.StringIO()
                with patch("plc_workbench.workspace.main", return_value=failure or 0) as launch, \
                        redirect_stdout(io.StringIO()), redirect_stderr(errors):
                    if isinstance(failure, Exception):
                        launch.side_effect = failure
                    result = work_check._open_completed_workspace(root, run, root)
                launch.assert_called_once_with([
                    "--runs", str(root / "confidential" / "workspaces" / "work-check"),
                    "--import-run", str(run),
                ])
                self.assertEqual(result, 1 if failure else 0)
                if failure:
                    self.assertIn("Analysis and its feedback commit are already saved", errors.getvalue())
                    self.assertIn("You do not need to repeat the analysis", errors.getvalue())
                    self.assertNotIn("Invented editor failure", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
