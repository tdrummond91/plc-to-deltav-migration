"""Code provenance tests never use network access or proprietary inputs."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.revision import _git, collect_revision


class RevisionTests(unittest.TestCase):
    def test_no_checkout_or_git_failure_is_unavailable(self) -> None:
        unavailable = {"commit": None, "worktree": "unavailable"}
        with patch("plc_workbench.revision._checkout_root", return_value=None):
            self.assertEqual(collect_revision(), unavailable)
        for error in (
            FileNotFoundError("PRIVATE_PATH"),
            subprocess.TimeoutExpired("git PRIVATE_PATH", 2),
            subprocess.CalledProcessError(128, "git", stderr="PRIVATE_PATH"),
        ):
            with self.subTest(error=type(error).__name__):
                with patch("plc_workbench.revision._git", side_effect=error):
                    self.assertEqual(collect_revision(), unavailable)

    def test_wrong_git_root_malformed_head_and_changed_head_are_unavailable(self) -> None:
        root = Path(__file__).resolve().parents[2]
        unavailable = {"commit": None, "worktree": "unavailable"}
        top = str(root).encode()
        cases = (
            [str(root.parent).encode()],
            [top, b"NOT_A_COMMIT"],
            [top, b"A" * 40],
            [top, b"a" * 40, b"", b"b" * 40],
        )
        for replies in cases:
            with self.subTest(replies=len(replies)), patch("plc_workbench.revision._git", side_effect=replies):
                self.assertEqual(collect_revision(), unavailable)

    def test_git_environment_is_sanitized_and_timeout_is_bounded(self) -> None:
        root = Path(__file__).resolve().parents[2]
        completed = subprocess.CompletedProcess([], 0, stdout=b"result", stderr=b"")
        with patch.dict(os.environ, {"GIT_DIR": "PRIVATE_PATH", "GIT_WORK_TREE": "PRIVATE_PATH", "GIT_CONFIG_COUNT": "1"}):
            with patch("plc_workbench.revision.subprocess.run", return_value=completed) as run:
                self.assertEqual(_git(root, "status"), b"result")
        kwargs = run.call_args.kwargs
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG_COUNT"):
            self.assertNotIn(key, kwargs["env"])
        self.assertEqual(kwargs["timeout"], 2)
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)

    @unittest.skipUnless(shutil.which("git"), "Git is unavailable.")
    def test_real_local_head_and_scoped_modified_state_include_untracked_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "python-parser" / "src" / "example.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n", encoding="utf-8")
            (root / "python-parser" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            (root / "python-parser" / "uv.lock").write_text("version = 1\n", encoding="utf-8")
            environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
            environment.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})

            def git(*arguments: str) -> str:
                completed = subprocess.run(
                    ["git", "-c", "user.name=Synthetic Test", "-c", "user.email=synthetic@example.invalid",
                     "-c", "commit.gpgsign=false", "-c", f"core.hooksPath={os.devnull}",
                     "-C", str(root), *arguments],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=5, env=environment,
                )
                return completed.stdout.decode().strip()

            git("init", "-q")
            git("add", "python-parser")
            git("commit", "-qm", "test: establish synthetic provenance baseline")
            commit = git("rev-parse", "HEAD")
            with patch("plc_workbench.revision._checkout_root", return_value=root):
                self.assertEqual(collect_revision(), {"commit": commit, "worktree": "clean"})
                (root / "notes.md").write_text("An unrelated note.", encoding="utf-8")
                self.assertEqual(collect_revision()["worktree"], "clean")
                untracked = source.parent / "new_parser.py"
                untracked.write_text("new_value = 2\n", encoding="utf-8")
                self.assertEqual(collect_revision()["worktree"], "modified")
                untracked.unlink()
                source.write_text("value = 3\n", encoding="utf-8")
                self.assertEqual(collect_revision()["worktree"], "modified")
                source.write_text("value = 1\n", encoding="utf-8")
                lock = root / "python-parser" / "uv.lock"
                lock.write_text("version = 2\n", encoding="utf-8")
                git("add", "python-parser/uv.lock")
                self.assertEqual(collect_revision()["worktree"], "modified")


if __name__ == "__main__":
    unittest.main()
