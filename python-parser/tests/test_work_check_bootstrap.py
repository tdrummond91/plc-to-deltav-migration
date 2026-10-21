"""Exercise the Bash bootstrap against disposable local Git repositories."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


def available_bash() -> str | None:
    if os.name == "nt":
        candidates = [Path("C:/Program Files/Git/bin/bash.exe")]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "Programs/Git/bin/bash.exe")
        return next((str(candidate) for candidate in candidates if candidate.is_file()), None)
    return shutil.which("bash")


class WorkCheckBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bash = available_bash()
        cls.git = shutil.which("git")
        if cls.bash is None or cls.git is None:
            raise unittest.SkipTest("Bash and Git are required for bootstrap boundary tests.")
        cls.bootstrap = Path(__file__).resolve().parents[2] / "run-work-check.sh"

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="plc bootstrap test ")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.remote = self.base / "remote.git"
        self.seed = self.base / "seed checkout"
        self.worker = self.base / "worker checkout"
        self.bin = self.base / "fake commands"
        self.bin.mkdir()
        self.seed.mkdir()
        self.arguments_log = self.base / "uv arguments.bin"
        self.head_log = self.base / "uv observed head.txt"
        self.git_log = self.base / "git invocations.txt"
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.env.update({
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "WORK_CHECK_REAL_GIT": Path(self.git).as_posix(),
            "WORK_CHECK_CAPTURE_ARGS": self.arguments_log.as_posix(),
            "WORK_CHECK_CAPTURE_HEAD": self.head_log.as_posix(),
            "WORK_CHECK_CAPTURE_GIT": self.git_log.as_posix(),
            "WORK_CHECK_BIN": self.bin.as_posix(),
            "PATH": str(self.bin) + os.pathsep + self.env.get("PATH", ""),
        })
        self._git("init", "--bare", str(self.remote), cwd=self.base)
        self._git("init", "-b", "feat/bootstrap-pc")
        self._git("config", "user.name", "Synthetic Tester")
        self._git("config", "user.email", "synthetic@example.invalid")
        self._git("config", "commit.gpgsign", "false")
        self._git("config", "core.autocrlf", "false")
        shutil.copyfile(self.bootstrap, self.seed / "run-work-check.sh")
        shutil.copyfile(self.bootstrap.parent / ".gitattributes", self.seed / ".gitattributes")
        (self.seed / ".gitignore").write_text("confidential/\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "test: create synthetic bootstrap checkout")
        self._git("remote", "add", "origin", str(self.remote))
        self._git("push", "-u", "origin", "feat/bootstrap-pc")
        self._git("clone", "--branch", "feat/bootstrap-pc", str(self.remote), str(self.worker), cwd=self.base)
        self._write_executable("git", """#!/usr/bin/env bash
printf '%s\\n' "$1" >> "$WORK_CHECK_CAPTURE_GIT"
exec "$WORK_CHECK_REAL_GIT" "$@"
""")
        self._write_executable("uv", """#!/usr/bin/env bash
printf '%s\\0' "$@" > "$WORK_CHECK_CAPTURE_ARGS"
git rev-parse HEAD > "$WORK_CHECK_CAPTURE_HEAD"
""")

    def _write_executable(self, name: str, contents: str) -> None:
        target = self.bin / name
        target.write_text(contents, encoding="utf-8", newline="\n")
        target.chmod(0o755)

    def _git(self, *arguments: str, cwd: Path | None = None) -> str:
        result = subprocess.run(
            [self.git, *arguments], cwd=cwd or self.seed, env=self.env,
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        if result.returncode:
            self.fail(f"Synthetic Git setup failed: {result.stderr}")
        return result.stdout.strip()

    def _run(self, *arguments: str) -> subprocess.CompletedProcess:
        # Git for Windows prepends its own executable directories at startup.
        # Install the command recorder after startup, before sourcing the same
        # bootstrap entry point; exec uv still replaces this shell normally.
        setup = ('if command -v cygpath >/dev/null; then '
                 'WORK_CHECK_BIN="$(cygpath -u "$WORK_CHECK_BIN")"; fi; '
                 'export PATH="$WORK_CHECK_BIN:$PATH"; source "$@"')
        return subprocess.run(
            [self.bash, "--noprofile", "--norc", "-c", setup, "work-check-test",
             str(self.worker / "run-work-check.sh"), *arguments],
            cwd=self.base, env=self.env, capture_output=True, text=True,
            encoding="utf-8", timeout=30,
        )

    def _commands(self) -> list[str]:
        return self.git_log.read_text(encoding="utf-8").splitlines() if self.git_log.exists() else []

    def test_windows_autocrlf_checkout_keeps_launcher_executable_by_bash(self) -> None:
        windows_checkout = self.base / "windows checkout"
        self._git("-c", "core.autocrlf=true", "clone", "--branch", "feat/bootstrap-pc",
                  str(self.remote), str(windows_checkout), cwd=self.base)
        self.assertNotIn(b"\r\n", (windows_checkout / "run-work-check.sh").read_bytes())
        self.worker = windows_checkout
        result = self._run("invented.L5X")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.arguments_log.exists())

    @unittest.skipUnless(os.name == "nt", "Windows paths are case-insensitive by default.")
    def test_windows_checkout_path_case_does_not_reject_the_same_directory(self) -> None:
        self.worker = self.worker.with_name(self.worker.name.upper())
        result = self._run("invented.L5X")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.arguments_log.exists())
        self.assertTrue(set(self._commands()) <= {"rev-parse", "status", "symbolic-ref"})

    def test_launcher_copied_below_checkout_root_stops_before_uv(self) -> None:
        nested = self.worker / "copied scripts"
        nested.mkdir()
        shutil.copyfile(self.bootstrap, nested / "run-work-check.sh")
        self.worker = nested
        result = self._run("invented.L5X")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("original repository checkout", result.stderr)
        self.assertFalse(self.arguments_log.exists())
        self.assertEqual(self._commands(), ["rev-parse"])

    def test_uses_local_checkout_without_pulling_and_preserves_argument_boundaries(self) -> None:
        old_head = self._git("rev-parse", "HEAD", cwd=self.worker)
        (self.seed / "remote-update.txt").write_text("synthetic remote change\n", encoding="utf-8")
        self._git("add", "remote-update.txt")
        self._git("commit", "-m", "test: advance synthetic remote")
        self._git("push", "origin", "feat/bootstrap-pc")
        remote_head = self._git("rev-parse", "HEAD")
        self.assertNotEqual(old_head, remote_head)

        result = self._run("--debug", "folder with spaces/invented unit.L5X", "literal-dollar-$value")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.head_log.read_text(encoding="utf-8").strip(), old_head)
        self.assertEqual(self._git("rev-parse", "HEAD", cwd=self.worker), old_head)
        arguments = self.arguments_log.read_bytes().decode("utf-8").split("\0")[:-1]
        self.assertEqual(arguments, [
            "run", "--project", "python-parser", "--locked", "python", "-B", "-m",
            "plc_workbench.work_check", "--open-workspace", "--debug", "folder with spaces/invented unit.L5X", "literal-dollar-$value",
        ])
        self.assertTrue(set(self._commands()) <= {"rev-parse", "status", "symbolic-ref"})

    def test_local_changes_stop_before_uv(self) -> None:
        self._git("switch", "-c", "main", cwd=self.worker)
        (self.worker / "local-notes.txt").write_text("synthetic local work", encoding="utf-8")
        result = self._run("invented.L5X")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("local changes", result.stderr)
        self.assertFalse(self.arguments_log.exists())
        self.assertNotIn("pull", self._commands())
        self.assertEqual((self.worker / "local-notes.txt").read_text(encoding="utf-8"), "synthetic local work")

    def test_different_upstream_does_not_block_local_analysis(self) -> None:
        self._git("branch", "wrong-upstream-pc")
        self._git("push", "origin", "wrong-upstream-pc")
        self._git("fetch", "origin", cwd=self.worker)
        self._git("branch", "--set-upstream-to=origin/wrong-upstream-pc", cwd=self.worker)
        result = self._run("invented.L5X")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.arguments_log.exists())
        self.assertTrue(set(self._commands()) <= {"rev-parse", "status", "symbolic-ref"})

    def test_missing_upstream_does_not_block_local_analysis(self) -> None:
        self._git("branch", "--unset-upstream", cwd=self.worker)
        result = self._run("invented.L5X")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.arguments_log.exists())
        self.assertTrue(set(self._commands()) <= {"rev-parse", "status", "symbolic-ref"})

    def test_main_and_other_named_branches_run_without_git_mutations(self) -> None:
        for branch in ("main", "feature-other-machine"):
            with self.subTest(branch=branch):
                self._git("switch", "-c", branch, cwd=self.worker)
                before = self._git("rev-parse", "HEAD", cwd=self.worker)
                result = self._run("invented.L5X")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(self.arguments_log.exists())
                self.assertEqual(self._git("rev-parse", "HEAD", cwd=self.worker), before)
                self.assertEqual(self._git("symbolic-ref", "--short", "HEAD", cwd=self.worker), branch)
                self.assertEqual(self._git("status", "--porcelain", cwd=self.worker), "")
                self.assertTrue(set(self._commands()) <= {"rev-parse", "status", "symbolic-ref"})

    def test_detached_head_stops_before_uv(self) -> None:
        self._git("switch", "--detach", cwd=self.worker)
        result = self._run("invented.L5X")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("detached HEAD", result.stderr)
        self.assertFalse(self.arguments_log.exists())
        self.assertNotIn("pull", self._commands())

    def test_unreachable_origin_does_not_block_local_analysis(self) -> None:
        self._git("remote", "set-url", "origin", str(self.base / "missing-remote.git"), cwd=self.worker)
        result = self._run("invented.L5X")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(set(self._commands()) <= {"rev-parse", "status", "symbolic-ref"})
        self.assertTrue(self.arguments_log.exists())


if __name__ == "__main__":
    unittest.main()
