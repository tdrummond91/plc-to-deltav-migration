"""Real local Git exercises, invented reports, and a mocked Codex boundary."""
from __future__ import annotations

from contextlib import redirect_stdout
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import listener

REPOSITORY = Path(__file__).resolve().parents[3]
BRANCH = "feat/listener-test-pc"
REPORT_PATH = "public/inspection/work-check-synthetic.json"


def report(run_id: str = "20261013T120000Z-1234abcd") -> dict:
    result = {"schema_version": 1, "status": "failed", "counts": {
        "tests_run": 1, "failures": 1, "errors": 0, "skipped": 0,
        "expected_failures": 0, "unexpected_successes": 0},
        "failed_test_ids": ["test_synthetic.Check.test_example"], "failure_ids_omitted": 0}
    return {"schema_version": 1, "report_kind": "l5x_work_machine_check", "workflow_version": "work-check-1",
            "run_id": run_id, "tool_revision": {"commit": "a" * 40, "worktree": "clean"},
            "tests": {"application": result, "helpers": result},
            "analysis": {"status": "not_run", "failure_code": None, "private_run_saved": False,
                         "reference_summary": None}, "status": "failed"}


def result(status: str = "waiting_for_report") -> dict:
    return {"status": status, "summary": "Reviewed synthetic report.", "next_step": "Run the next work check.",
            "question": None if status == "waiting_for_report" else "Which bounded step should follow?", "commit": None}


class ListenerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.primary = self.root / "primary"
        self.checkout = self.root / "dedicated"
        self.remote = self.root / "remote.git"
        self.directory = self.root / "state"
        self.directory.mkdir()
        self.git = shutil.which("git")
        if self.git is None:
            self.skipTest("Git is required for local repository integration tests")
        self.command("init", "--bare", str(self.remote))
        self.command("init", "-b", BRANCH, str(self.primary))
        self.command("-C", str(self.primary), "config", "user.name", "Synthetic Test")
        self.command("-C", str(self.primary), "config", "user.email", "synthetic@example.invalid")
        shutil.copytree(REPOSITORY / "python-parser" / "src" / "plc_workbench",
                        self.primary / "python-parser" / "src" / "plc_workbench",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.commit("Synthetic validator fixture")
        self.command("-C", str(self.primary), "remote", "add", "origin", str(self.remote))
        self.command("-C", str(self.primary), "push", "-u", "origin", BRANCH)
        self.command("clone", "--branch", BRANCH, str(self.remote), str(self.checkout))
        self.config = {"repository": str(self.primary), "checkout": str(self.checkout), "branch": BRANCH,
                       "git": self.git, "codex": sys.executable}
        self.state = listener.initialize(self.directory, self.config)

    def command(self, *args: str) -> str:
        process = subprocess.run([self.git or "git", *args], check=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, env={key: value for key, value in os.environ.items()
                                                             if key.upper() not in listener._GIT_ENV})
        return process.stdout.decode("utf-8").strip()

    def commit(self, message: str, root: Path | None = None) -> None:
        root = root or self.primary
        self.command("-C", str(root), "add", ".")
        self.command("-C", str(root), "-c", "user.name=Synthetic Test", "-c",
                     "user.email=synthetic@example.invalid", "commit", "-m", message)

    def publish(self, payload: dict | str | None = None) -> None:
        destination = self.primary / REPORT_PATH
        destination.parent.mkdir(parents=True, exist_ok=True)
        value = report() if payload is None else payload
        destination.write_text(json.dumps(value) if isinstance(value, dict) else value, encoding="utf-8")
        self.commit("Return invented work report")
        self.command("-C", str(self.primary), "push")

    def run_poll(self, outcome: dict | None = None) -> tuple[dict, object]:
        with patch.object(listener, "_agent", return_value=outcome or result()) as agent:
            self.state = listener.poll(self.directory, self.config, self.state)
        return self.state, agent

    def test_new_report_once_code_push_ignored_and_changed_blob_once(self) -> None:
        self.publish()
        state, agent = self.run_poll()
        self.assertEqual(state["status"], "waiting_for_report")
        self.assertEqual(len(state["processed_reports"]), 1)
        agent.assert_called_once()
        state, agent = self.run_poll()
        agent.assert_not_called()
        (self.primary / "code.txt").write_text("Invented code-only change", encoding="utf-8")
        self.commit("Synthetic code change")
        self.command("-C", str(self.primary), "push")
        state, agent = self.run_poll()
        agent.assert_not_called()
        self.publish(report("20261013T120001Z-1234abcd"))
        state, agent = self.run_poll()
        agent.assert_called_once()
        self.assertEqual(len(state["processed_reports"]), 2)
        self.publish(report())
        state, agent = self.run_poll()
        agent.assert_not_called()

    def test_initialization_baselines_existing_validated_reports(self) -> None:
        self.publish()
        self.command("-C", str(self.checkout), "pull", "--ff-only")
        other = self.root / "other-state"
        other.mkdir()
        state = listener.initialize(other, dict(self.config))
        self.assertEqual(len(state["processed_reports"]), 1)
        with patch.object(listener, "_agent") as agent:
            listener.poll(other, self.config, state)
        agent.assert_not_called()

    def test_initial_report_runs_once_while_other_existing_reports_are_baselined(self) -> None:
        self.publish()
        older_path = "public/inspection/work-check-older-synthetic.json"
        (self.primary / older_path).write_text(json.dumps(report("20261013T110000Z-1234abcd")), encoding="utf-8")
        self.commit("Another existing invented report")
        self.command("-C", str(self.primary), "push")
        self.command("-C", str(self.checkout), "pull", "--ff-only")
        other = self.root / "initial-report-state"
        other.mkdir()
        state = listener.initialize(other, dict(self.config), initial_report=REPORT_PATH)
        self.assertEqual([item["path"] for item in state["processed_reports"]], [older_path])
        with patch.object(listener, "_agent", return_value=result()) as agent:
            state = listener.poll(other, self.config, state)
            self.assertEqual([item["path"] for item in agent.call_args.args[1]["reports"]], [REPORT_PATH])
            state = listener.poll(other, self.config, state)
        agent.assert_called_once()
        self.assertEqual(len(state["processed_reports"]), 2)

    def test_initial_report_must_exist_as_a_validated_tracked_report(self) -> None:
        other = self.root / "missing-report-state"
        other.mkdir()
        with self.assertRaisesRegex(listener.ListenerError, "initial_report_not_found"):
            listener.initialize(other, dict(self.config), initial_report=REPORT_PATH)
        self.assertFalse((other / "config.json").exists())
        self.assertFalse((other / "state.json").exists())

    def test_malformed_report_pauses_without_launching_worker(self) -> None:
        self.publish('{"private_source": "DO_NOT_PUBLISH"}')
        state, agent = self.run_poll()
        self.assertEqual((state["status"], state["reason"]), ("needs_attention", "report_validation_failed"))
        self.assertTrue(state["paused"])
        self.assertNotIn("DO_NOT_PUBLISH", json.dumps(state))
        agent.assert_not_called()
        self.run_poll()[1].assert_not_called()

    def test_oversized_report_rejected_before_validator(self) -> None:
        self.publish(" " * (listener.MAX_REPORT_BYTES + 1))
        state, agent = self.run_poll()
        self.assertEqual(state["reason"], "report_size_limit")
        agent.assert_not_called()

    def test_git_symlink_blob_is_rejected_without_reading_target(self) -> None:
        # Write a Git symlink entry without needing Windows symlink privileges.
        path = self.primary / REPORT_PATH
        path.parent.mkdir(parents=True)
        blob = subprocess.run([self.git, "-C", str(self.primary), "hash-object", "-w", "--stdin"],
                              input=b"never-open-this-private-target", check=True, stdout=subprocess.PIPE).stdout.decode().strip()
        self.command("-C", str(self.primary), "update-index", "--add", "--cacheinfo", f"120000,{blob},{REPORT_PATH}")
        self.command("-C", str(self.primary), "commit", "-m", "Synthetic symlink report")
        self.command("-C", str(self.primary), "checkout", "--", REPORT_PATH)
        self.command("-C", str(self.primary), "push")
        state, agent = self.run_poll()
        self.assertEqual(state["reason"], "report_path_or_mode_invalid")
        agent.assert_not_called()

    def test_primary_dirty_defers_and_preserves_contents(self) -> None:
        self.publish()
        content = self.primary / "local-edit.txt"
        content.write_text("Preserve me", encoding="utf-8")
        state, agent = self.run_poll()
        self.assertEqual((state["status"], state["reason"]), ("deferred", "primary_dirty"))
        self.assertFalse(state["paused"])
        self.assertEqual(content.read_text(encoding="utf-8"), "Preserve me")
        agent.assert_not_called()

    def test_primary_unpushed_commit_defers(self) -> None:
        self.publish()
        (self.primary / "local.txt").write_text("Unpushed work", encoding="utf-8")
        self.commit("Local work")
        state, agent = self.run_poll()
        self.assertEqual(state["reason"], "primary_ahead_or_diverged")
        self.assertEqual(state["status"], "deferred")
        agent.assert_not_called()

    def test_dedicated_divergence_halts_and_preserves_commit(self) -> None:
        (self.checkout / "local.txt").write_text("Preserve this commit", encoding="utf-8")
        self.commit("Unpushed dedicated work", self.checkout)
        head = self.command("-C", str(self.checkout), "rev-parse", "HEAD")
        self.publish()
        state, agent = self.run_poll()
        self.assertEqual(state["reason"], "checkout_ahead_or_diverged")
        self.assertTrue(state["paused"])
        self.assertEqual(self.command("-C", str(self.checkout), "rev-parse", "HEAD"), head)
        agent.assert_not_called()

    def test_claim_is_durable_before_worker_and_failure_is_not_retried(self) -> None:
        self.publish()
        def fail(config: dict, event: dict, run: Path) -> dict:
            persisted = listener._read_json(self.directory / "state.json")
            self.assertEqual(persisted["status"], "running")
            self.assertEqual(persisted["pending"], event)
            raise listener.ListenerError("worker_failed")
        with patch.object(listener, "_agent", side_effect=fail) as agent:
            self.state = listener.poll(self.directory, self.config, self.state)
        agent.assert_called_once()
        self.assertEqual(self.state["reason"], "worker_failed")
        self.assertEqual(self.state["processed_reports"], [])
        self.assertIsNotNone(self.state["pending"])
        self.run_poll()[1].assert_not_called()

    def test_abandoned_running_state_halts_without_retry(self) -> None:
        self.state.update(status="running", pending={"report_commit": "a" * 40})
        state, agent = self.run_poll()
        self.assertEqual(state["reason"], "interrupted_worker")
        self.assertTrue(state["paused"])
        agent.assert_not_called()

    def test_success_with_dirty_or_unpushed_worker_output_does_not_complete(self) -> None:
        self.publish()
        def leave_dirty(config: dict, event: dict, run: Path) -> dict:
            (self.checkout / "unfinished.txt").write_text("Keep work", encoding="utf-8")
            return result()
        with patch.object(listener, "_agent", side_effect=leave_dirty):
            state = listener.poll(self.directory, self.config, self.state)
        self.assertEqual(state["reason"], "checkout_dirty")
        self.assertEqual(state["processed_reports"], [])
        self.assertTrue((self.checkout / "unfinished.txt").exists())

    def test_success_with_unpushed_worker_commit_does_not_complete(self) -> None:
        self.publish()
        def leave_commit(config: dict, event: dict, run: Path) -> dict:
            (self.checkout / "work.txt").write_text("Unpushed work", encoding="utf-8")
            self.commit("Worker commit", self.checkout)
            return result()
        with patch.object(listener, "_agent", side_effect=leave_commit):
            state = listener.poll(self.directory, self.config, self.state)
        self.assertEqual(state["reason"], "worker_changes_not_synchronized")
        self.assertEqual(state["processed_reports"], [])

    def test_valid_pushed_worker_commit_completes_the_claim(self) -> None:
        self.publish()
        def push_commit(config: dict, event: dict, run: Path) -> dict:
            (self.checkout / "work.txt").write_text("Invented worker improvement", encoding="utf-8")
            self.commit("Synthetic worker improvement", self.checkout)
            self.command("-C", str(self.checkout), "push")
            return {**result(), "commit": self.command("-C", str(self.checkout), "rev-parse", "HEAD")}
        with patch.object(listener, "_agent", side_effect=push_commit):
            state = listener.poll(self.directory, self.config, self.state)
        self.assertEqual(state["status"], "waiting_for_report")
        self.assertIsNone(state["pending"])
        self.assertEqual(len(state["processed_reports"]), 1)
        self.assertEqual(state["last_result"]["commit"], self.command("-C", str(self.checkout), "rev-parse", "HEAD"))

    def test_worker_cannot_omit_commit_when_it_advanced_the_branch(self) -> None:
        self.publish()
        def omit_commit(config: dict, event: dict, run: Path) -> dict:
            (self.checkout / "work.txt").write_text("Invented worker improvement", encoding="utf-8")
            self.commit("Synthetic worker improvement", self.checkout)
            self.command("-C", str(self.checkout), "push")
            return result()
        with patch.object(listener, "_agent", side_effect=omit_commit):
            state = listener.poll(self.directory, self.config, self.state)
        self.assertEqual(state["reason"], "worker_commit_missing")
        self.assertTrue(state["paused"])
        self.assertEqual(state["processed_reports"], [])

    def test_synchronized_rewritten_history_does_not_complete_claim(self) -> None:
        self.publish()
        def rewrite(config: dict, event: dict, run: Path) -> dict:
            # All refs here are independently invented temporary repositories.
            # Keep the same tree, but deliberately replace its ancestry to test
            # the listener's check even when the local and remote tips agree.
            tree = self.command("-C", str(self.checkout), "rev-parse", "HEAD^{tree}")
            replacement = self.command("-C", str(self.checkout), "-c", "user.name=Synthetic Test", "-c",
                                       "user.email=synthetic@example.invalid", "commit-tree", tree,
                                       "-m", "Synthetic independent root")
            self.command("-C", str(self.checkout), "push", "origin", f"{replacement}:refs/heads/synthetic-rewritten-root")
            self.command("-C", str(self.remote), "update-ref", f"refs/heads/{BRANCH}", replacement)
            self.command("-C", str(self.checkout), "update-ref", f"refs/heads/{BRANCH}", replacement)
            return {**result(), "commit": replacement}
        with patch.object(listener, "_agent", side_effect=rewrite):
            state = listener.poll(self.directory, self.config, self.state)
        self.assertEqual(state["reason"], "worker_history_rewritten")
        self.assertTrue(state["paused"])
        self.assertEqual(state["processed_reports"], [])

    def test_needs_input_marks_report_processed_and_pauses(self) -> None:
        self.publish()
        state, agent = self.run_poll(result("needs_input"))
        self.assertEqual(state["status"], "needs_input")
        self.assertTrue(state["paused"])
        self.assertIsNotNone(state["last_result"]["question"])
        self.assertEqual(len(state["processed_reports"]), 1)
        self.run_poll()[1].assert_not_called()

    def test_lock_prevents_overlapping_polls_and_control_changes(self) -> None:
        with listener.lock(self.directory):
            with self.assertRaises(listener.Busy):
                with listener.lock(self.directory):
                    self.fail("Second holder acquired an active lock")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = listener.main(["--state-dir", str(self.directory), "pause", "--reason", "manual"])
            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "busy")
        self.assertFalse(listener._read_json(self.directory / "state.json")["paused"])

    def test_pause_resume_and_status_preserve_report_history(self) -> None:
        self.publish()
        self.run_poll(result("phase_complete"))
        with redirect_stdout(io.StringIO()):
            listener.main(["--state-dir", str(self.directory), "pause", "--reason", "Review checkpoint"])
            listener.main(["--state-dir", str(self.directory), "resume"])
        state = listener._read_json(self.directory / "state.json")
        self.assertFalse(state["paused"])
        self.assertEqual(state["status"], "idle")
        self.assertEqual(len(state["processed_reports"]), 1)


class WorkerBoundaryTests(unittest.TestCase):
    def test_invalid_local_state_fails_closed_without_worker(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "state.json").write_text('{"schema_version": true}', encoding="utf-8")
            with patch.object(listener, "_agent") as agent, redirect_stdout(io.StringIO()) as output:
                code = listener.main(["--state-dir", str(root), "status"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output.getvalue())["reason"], "local_state_invalid")
            agent.assert_not_called()

    def test_invalid_local_config_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config.json").write_text('{"repository": "incomplete"}', encoding="utf-8")
            with patch.object(listener, "_agent") as agent, redirect_stdout(io.StringIO()) as output:
                code = listener.main(["--state-dir", str(root), "poll"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output.getvalue())["reason"], "local_state_invalid")
            agent.assert_not_called()

    def test_direct_native_launch_strips_api_keys_and_records_local_logs(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "PROMPT.txt").write_text("Read the approved scope.", encoding="utf-8")
            (root / "result.schema.json").write_text("{}", encoding="utf-8")
            run = root / "run"
            run.mkdir()
            def launch(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
                self.assertEqual(command[0], "native-codex.exe")
                self.assertIn("--no-daemon", command)
                self.assertNotIn("--approve-for-me", command)
                self.assertNotIn("-c", command)
                self.assertNotIn("--sandbox", command)
                self.assertNotIn("shell", kwargs)
                self.assertNotIn("OPENAI_API_KEY", kwargs["env"])
                self.assertNotIn("CODEX_API_KEY", kwargs["env"])
                self.assertNotIn("CODEX_THREAD_ID", kwargs["env"])
                self.assertNotIn("GIT_DIR", kwargs["env"])
                if os.name == "nt":
                    self.assertEqual(kwargs["creationflags"], subprocess.CREATE_NO_WINDOW)
                self.assertIn(b"Listener event", kwargs["input"])
                (run / "result.json").write_text(json.dumps(result()), encoding="utf-8")
                return subprocess.CompletedProcess(command, 0)
            with patch.object(listener, "__file__", str(root / "listener.py")), \
                    patch.dict(os.environ, {"OPENAI_API_KEY": "must-not-forward", "CODEX_API_KEY": "also-remove",
                                            "CODEX_THREAD_ID": "parent-thread", "GIT_DIR": "wrong-checkout"}), \
                    patch.object(listener.subprocess, "run", side_effect=launch):
                value = listener._agent({"codex": "native-codex.exe", "checkout": "dedicated"}, {"reports": []}, run)
            self.assertEqual(value, result())
            self.assertTrue((run / "stdout.jsonl").exists())
            self.assertTrue((run / "stderr.log").exists())

    def test_worker_result_rejects_unknown_fields_and_missing_questions(self) -> None:
        for value in ({**result(), "extra": "not-allowed"}, {**result(), "status": []},
                      {**result("needs_input"), "question": None},
                      {**result("phase_complete"), "question": None},
                      {**result(), "question": "This would incorrectly suppress a question"},
                      {**result(), "commit": "not-a-commit"}, {**result(), "summary": ""}):
            with self.subTest(value=value), self.assertRaises(listener.ListenerError):
                listener._validate_result(value)


if __name__ == "__main__":
    unittest.main()
