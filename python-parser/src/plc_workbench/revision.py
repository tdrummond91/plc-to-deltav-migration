"""Bounded local code provenance, containing no paths, branch names or remotes."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess


_CODE_PATHS = ("python-parser/src", "python-parser/pyproject.toml", "python-parser/uv.lock")
_GIT_TIMEOUT_SECONDS = 2


def _checkout_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists() and (parent / "python-parser").is_dir():
            return parent
    return None


def _git(checkout: Path, *arguments: str) -> bytes:
    # Ignore inherited GIT_DIR/WORK_TREE/config injection and avoid optional
    # locks or fsmonitor hooks. Only local built-in Git reads are requested.
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    environment.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
    process = subprocess.run(
        [
            "git", "--no-optional-locks", "-c", "core.fsmonitor=false",
            "-C", str(checkout), *arguments,
        ],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True, timeout=_GIT_TIMEOUT_SECONDS, env=environment,
    )
    return process.stdout


def collect_revision() -> dict[str, str | None]:
    """Return unavailable provenance unless this actual checkout is verified.

    Git status is scoped to application sources and dependency/build metadata.
    Staged, unstaged and untracked source changes count; documentation, fixtures
    and private inputs do not. No network command is issued.
    """
    unavailable: dict[str, str | None] = {"commit": None, "worktree": "unavailable"}
    try:
        checkout = _checkout_root()
        if checkout is None:
            return unavailable
        toplevel = _git(checkout, "rev-parse", "--show-toplevel").decode("utf-8").strip()
        if not toplevel or Path(toplevel).resolve() != checkout:
            return unavailable
        commit = _git(checkout, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip()
        if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            return unavailable
        status = _git(
            checkout, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *_CODE_PATHS,
        )
        final_commit = _git(checkout, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip()
        if final_commit != commit:
            return unavailable
        return {"commit": commit, "worktree": "modified" if status else "clean"}
    except (OSError, RuntimeError, UnicodeError, subprocess.SubprocessError):
        return unavailable
