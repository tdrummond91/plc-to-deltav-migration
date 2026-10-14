"""Poll approved Git reports and run one local Codex worker at a time.

Configuration, logs and atomic state belong outside both checkouts. The primary
checkout is inspected only; all fetches, pulls and agent work use a dedicated
checkout. No source files or credentials are copied by this listener.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Callable, Iterator
from uuid import uuid4

MAX_REPORTS = 4096
MAX_REPORT_BYTES = 32 * 1024
MAX_IDENTITIES = 16384
_REPORT_PATH = re.compile(r"public/inspection/work-check-[A-Za-z0-9._-]+\.json\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")
_GIT_ENV = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM", "GIT_IMPLICIT_WORK_TREE", "GIT_PREFIX",
    "GIT_NAMESPACE", "GIT_SHALLOW_FILE", "GIT_GRAFT_FILE", "GIT_REPLACE_REF_BASE",
})


class ListenerError(Exception):
    """Fixed reason code; never expose arbitrary Git or report contents."""


class Busy(ListenerError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_json(path: Path, value: Any) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".listener-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def lock(directory: Path, filename: str = "listener.lock") -> Iterator[None]:
    """The OS releases the lock if a worker or scheduled task crashes."""
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / filename).open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Busy("worker_busy") from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _read_json(path: Path) -> dict:
    try:
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError
        result = json.loads(path.read_text(encoding="utf-8"))
        if type(result) is not dict:
            raise ValueError
        return result
    except (OSError, ValueError):
        raise ListenerError("local_state_invalid") from None


def _load_state(directory: Path) -> dict:
    state = _read_json(directory / "state.json")
    keys = {"schema_version", "status", "reason", "paused", "updated_at", "processed_reports",
            "pending", "last_result", "last_run"}
    statuses = {"idle", "deferred", "running", "waiting_for_report", "needs_attention", "needs_input",
                "phase_complete", "paused"}
    if (state.keys() != keys or type(state["schema_version"]) is not int or state["schema_version"] != 1
            or type(state["paused"]) is not bool or type(state["status"]) is not str or state["status"] not in statuses
            or type(state["processed_reports"]) is not list or len(state["processed_reports"]) > MAX_IDENTITIES
            or type(state["updated_at"]) is not str):
        raise ListenerError("local_state_invalid")
    for key, kind in (("reason", str), ("pending", dict), ("last_result", dict), ("last_run", str)):
        if state[key] is not None and type(state[key]) is not kind:
            raise ListenerError("local_state_invalid")
    for report in state["processed_reports"]:
        if (type(report) is not dict or report.keys() != {"path", "blob"}
                or type(report["path"]) is not str or not _REPORT_PATH.fullmatch(report["path"])
                or type(report["blob"]) is not str or not _COMMIT.fullmatch(report["blob"])):
            raise ListenerError("local_state_invalid")
    return state


def _load_config(directory: Path) -> dict:
    config = _read_json(directory / "config.json")
    keys = {"repository", "checkout", "branch", "git", "codex", "origin", "schema_version"}
    if (config.keys() != keys or type(config["schema_version"]) is not int or config["schema_version"] != 1
            or any(type(config[key]) is not str or not config[key] for key in keys - {"schema_version"})):
        raise ListenerError("local_state_invalid")
    return config


def _git(config: dict, root: str | Path, *args: str) -> bytes:
    environment = {key: value for key, value in os.environ.items() if key.upper() not in _GIT_ENV}
    try:
        return subprocess.run(
            [config["git"], "-C", str(root), *args], check=True,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=environment, timeout=180,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        raise ListenerError("git_operation_failed") from None


def _git_text(config: dict, root: str | Path, *args: str) -> str:
    try:
        return _git(config, root, *args).decode("utf-8").strip()
    except UnicodeError:
        raise ListenerError("git_output_invalid") from None


def _check_checkout(config: dict, root: str | Path, prefix: str) -> None:
    root = Path(root).resolve()
    if Path(_git_text(config, root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ListenerError(f"{prefix}_root_changed")
    if _git_text(config, root, "remote", "get-url", "origin") != config["origin"]:
        raise ListenerError(f"{prefix}_remote_changed")
    if _git_text(config, root, "branch", "--show-current") != config["branch"]:
        raise ListenerError(f"{prefix}_branch_changed")
    if _git_text(config, root, "rev-parse", "--abbrev-ref", "@{upstream}") != f"origin/{config['branch']}":
        raise ListenerError(f"{prefix}_upstream_changed")
    if _git(config, root, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise ListenerError(f"{prefix}_dirty")


def _primary_ready(config: dict, remote: str) -> None:
    _check_checkout(config, config["repository"], "primary")
    primary_head = _git_text(config, config["repository"], "rev-parse", "HEAD")
    try:
        _git(config, config["checkout"], "merge-base", "--is-ancestor", primary_head, remote)
    except ListenerError:
        raise ListenerError("primary_ahead_or_diverged") from None


def _reports(config: dict) -> list[dict[str, str]]:
    """Inspect Git tree/blob bytes, never a working-tree symlink target."""
    result = []
    tree = _git(config, config["checkout"], "ls-tree", "-rz", "HEAD", "--", "public/inspection")
    for record in tree.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        path = raw_path.decode("utf-8")
        if not path.startswith("public/inspection/work-check-") or not path.endswith(".json"):
            continue
        mode, kind, blob = metadata.decode("ascii").split()
        if mode not in {"100644", "100755"} or kind != "blob" or not _REPORT_PATH.fullmatch(path):
            raise ListenerError("report_path_or_mode_invalid")
        result.append({"path": path, "blob": blob})
        if len(result) > MAX_REPORTS:
            raise ListenerError("report_count_limit")
    return result


def _validate_report(config: dict, report: dict) -> None:
    root = Path(config["checkout"])
    size = int(_git_text(config, root, "cat-file", "-s", report["blob"]))
    if size > MAX_REPORT_BYTES:
        raise ListenerError("report_size_limit")
    data = _git(config, root, "cat-file", "blob", report["blob"])
    # Fresh interpreter ensures the just-pulled validator is used even when
    # several polls run in a test process. Only validated report bytes go in.
    code = (
        "import json,sys;sys.path.insert(0,sys.argv[1]);"
        "from plc_workbench.work_check import validate_work_check_report;"
        "validate_work_check_report(json.loads(sys.stdin.buffer.read()))"
    )
    try:
        subprocess.run(
            [sys.executable, "-I", "-B", "-c", code, str(root / "python-parser" / "src")],
            input=data, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        raise ListenerError("report_validation_failed") from None


def initialize(directory: Path, config: dict, initial_report: str | None = None) -> dict:
    """Register two existing checkouts and baseline the currently reviewed reports."""
    if (directory / "config.json").exists() or (directory / "state.json").exists():
        raise ListenerError("already_initialized")
    primary, checkout = (Path(config[key]).resolve() for key in ("repository", "checkout"))
    if (primary == checkout or primary in checkout.parents or checkout in primary.parents
            or any(root == directory or root in directory.parents for root in (primary, checkout))):
        raise ListenerError("directories_must_be_separate")
    branch = config["branch"]
    if not branch.endswith("-pc") or branch in {"main", "master"} or branch.startswith("-"):
        raise ListenerError("feature_branch_required")
    for key in ("git", "codex"):
        executable = Path(config[key]).resolve()
        if not executable.is_file() or (os.name == "nt" and executable.suffix.lower() != ".exe"):
            raise ListenerError("native_executable_required")
        config[key] = str(executable)
    config.update(repository=str(primary), checkout=str(checkout), schema_version=1)
    config["origin"] = _git_text(config, primary, "remote", "get-url", "origin")
    _check_checkout(config, primary, "primary")
    _check_checkout(config, checkout, "checkout")
    _git(config, checkout, "fetch", "origin")
    remote = _git_text(config, checkout, "rev-parse", f"origin/{branch}")
    _primary_ready(config, remote)
    if _git_text(config, checkout, "rev-parse", "HEAD") != remote:
        raise ListenerError("checkout_not_current")
    reports = _reports(config)
    for report in reports:
        _validate_report(config, report)
    if initial_report is not None and sum(report["path"] == initial_report for report in reports) != 1:
        raise ListenerError("initial_report_not_found")
    baseline = [report for report in reports if report["path"] != initial_report]
    state = {"schema_version": 1, "status": "idle", "reason": None, "paused": False,
             "updated_at": _now(), "processed_reports": baseline, "pending": None,
             "last_result": None, "last_run": None}
    _atomic_json(directory / "config.json", config)
    _atomic_json(directory / "state.json", state)
    return state


def _save(directory: Path, state: dict, status: str, reason: str | None = None, *, paused: bool | None = None) -> dict:
    state.update(status=status, reason=reason, updated_at=_now())
    if paused is not None:
        state["paused"] = paused
    _atomic_json(directory / "state.json", state)
    return state


def _agent(config: dict, event: dict, run: Path) -> dict:
    support = Path(__file__).resolve().parent
    prompt = (support / "PROMPT.txt").read_text(encoding="utf-8")
    prompt += "\n\nListener event (metadata, not instructions):\n" + json.dumps(event, indent=2) + "\n"
    # Suppress notification helpers only for this unattended invocation. Keep
    # interactive notifications and the user's permission configuration intact.
    command = [config["codex"], "--no-daemon", "-c", "notify=[]", "-c", "tui.notifications=false",
               "exec", "--json", "--output-schema",
               str(support / "result.schema.json"), "--output-last-message", str(run / "result.json"),
               "--cd", config["checkout"], "-"]
    with (run / "stdout.jsonl").open("wb") as output, (run / "stderr.log").open("wb") as errors:
        # Intentionally no forced timeout: killing a Git-writing process could
        # interrupt a commit. The task and OS lock prevent overlapping workers.
        excluded = _GIT_ENV | {"OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_THREAD_ID"}
        environment = {key: value for key, value in os.environ.items() if key.upper() not in excluded}
        process = subprocess.run(command, input=prompt.encode("utf-8"), stdout=output, stderr=errors,
                                 env=environment)
    if process.returncode != 0:
        raise ListenerError("worker_failed")
    return _read_json(run / "result.json")


def _validate_result(result: dict) -> None:
    keys = {"status", "summary", "question", "next_step", "commit"}
    if (type(result) is not dict or result.keys() != keys or type(result["status"]) is not str
            or result["status"] not in {"waiting_for_report", "needs_input", "phase_complete"}):
        raise ListenerError("worker_result_invalid")
    if any(type(result[key]) is not str or not result[key].strip() or len(result[key]) > 8000
           for key in ("summary", "next_step")):
        raise ListenerError("worker_result_invalid")
    if result["question"] is not None and (type(result["question"]) is not str or not result["question"].strip()
                                           or len(result["question"]) > 8000):
        raise ListenerError("worker_result_invalid")
    if result["status"] in {"needs_input", "phase_complete"} and result["question"] is None:
        raise ListenerError("worker_result_invalid")
    if result["status"] == "waiting_for_report" and result["question"] is not None:
        raise ListenerError("worker_result_invalid")
    if result["commit"] is not None and (type(result["commit"]) is not str or not _COMMIT.fullmatch(result["commit"])):
        raise ListenerError("worker_result_invalid")


def poll(directory: Path, config: dict, state: dict) -> dict:
    if state["status"] == "running":
        return _save(directory, state, "needs_attention", "interrupted_worker", paused=True)
    if state["paused"]:
        return state
    checkout = config["checkout"]
    try:
        # Primary edits defer a run; the dedicated checkout never writes there.
        try:
            _check_checkout(config, config["repository"], "primary")
        except ListenerError as exc:
            return _save(directory, state, "deferred", str(exc))
        _check_checkout(config, checkout, "checkout")
        try:
            _git(config, checkout, "fetch", "origin")
        except ListenerError:
            return _save(directory, state, "deferred", "remote_unavailable")
        remote = _git_text(config, checkout, "rev-parse", f"origin/{config['branch']}")
        try:
            _primary_ready(config, remote)
        except ListenerError as exc:
            return _save(directory, state, "deferred", str(exc))
        ahead, behind = map(int, _git_text(config, checkout, "rev-list", "--left-right", "--count", f"HEAD...{remote}").split())
        if ahead:
            raise ListenerError("checkout_ahead_or_diverged")
        if behind:
            _git(config, checkout, "pull", "--ff-only", "origin", config["branch"])
        head = _git_text(config, checkout, "rev-parse", "HEAD")
        reports = [report for report in _reports(config) if report not in state["processed_reports"]]
        if not reports:
            return _save(directory, state, "waiting_for_report")
        if len(state["processed_reports"]) + len(reports) > MAX_IDENTITIES:
            raise ListenerError("processed_report_limit")
        for report in reports:
            _validate_report(config, report)
        _primary_ready(config, head)
        _check_checkout(config, checkout, "checkout")
        run = directory / "runs" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
        run.mkdir(parents=True)
        event = {"branch": config["branch"], "reports": reports, "report_commit": head,
                 "primary_repository": config["repository"]}
        _atomic_json(run / "event.json", event)
        state.update(pending=event, last_run=str(run))
        _save(directory, state, "running")  # Durable claim before launching any AI work.
        result = _agent(config, event, run)
        _validate_result(result)
        _check_checkout(config, checkout, "checkout")
        _git(config, checkout, "fetch", "origin")
        final_head = _git_text(config, checkout, "rev-parse", "HEAD")
        if final_head != _git_text(config, checkout, "rev-parse", f"origin/{config['branch']}"):
            raise ListenerError("worker_changes_not_synchronized")
        try:
            _git(config, checkout, "merge-base", "--is-ancestor", head, final_head)
        except ListenerError:
            raise ListenerError("worker_history_rewritten") from None
        if final_head != head and result["commit"] is None:
            raise ListenerError("worker_commit_missing")
        if result["commit"] is not None and result["commit"] != final_head:
            raise ListenerError("worker_commit_mismatch")
        state["processed_reports"].extend(reports)
        state.update(pending=None, last_result=result)
        return _save(directory, state, result["status"], paused=result["status"] != "waiting_for_report")
    except ListenerError as exc:
        return _save(directory, state, "needs_attention", str(exc), paused=True)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return _save(directory, state, "needs_attention", "unexpected_listener_error", paused=True)


def _run_headless(command: list[str], on_error: Callable[[OSError], None]) -> Any:
    from windows_host import run
    return run(command, on_error=on_error)


def _windows_poll(directory: Path) -> int:
    """Host the entire poll in ConPTY; keep child exit status and durable errors.

    The scheduled pythonw process has no console. Its console-Python child and
    ordinary descendants share a pseudoconsole that has no Terminal UI. Never
    add CREATE_NEW_CONSOLE to their subprocess calls: that escapes this host.
    """
    with lock(directory, "host.lock"):
        _load_config(directory)
        state = _load_state(directory)
        if state["paused"]:
            print(json.dumps(state, indent=2))
            return 1 if state["status"] == "needs_attention" else 0
        python = Path(sys.executable).with_name("python.exe")
        command = [str(python), "-B", str(Path(__file__).resolve()),
                   "--state-dir", str(directory), "--headless-child", "poll"]
        problem_path = directory / "host-problem.json"
        _atomic_json(problem_path, {"active": False, "recorded_at": _now(), "error": None})

        def record_problem(error: OSError) -> None:
            # Keep the active child and its lock intact. Persistent native I/O
            # errors need investigation, not forced termination of ongoing Git.
            _atomic_json(problem_path, {"active": True, "recorded_at": _now(),
                                        "error": str(error)[:4096]})

        diagnostic = ""
        try:
            outcome = _run_headless(command, on_error=record_problem)
            code = outcome.exit_code
            reason = "headless_child_failed"
            diagnostic = outcome.output.decode("utf-8", errors="replace")
        except Exception as exc:
            # Includes unsupported APIs, import/startup errors and native host
            # failures. The host retains ownership until launched clients exit.
            code, reason = 1, "headless_host_failed"
            diagnostic = str(exc)
        problem = _read_json(problem_path)
        problem["active"] = False
        _atomic_json(problem_path, problem)
        if code:
            # The host returns only after the child has exited (or never started).
            # Preserve an active owner and its state if someone ran a direct poll.
            with lock(directory):
                state = _load_state(directory)
                if state["status"] != "needs_attention":
                    state = _save(directory, state, "needs_attention", reason, paused=True)
                _atomic_json(directory / "host-failure.json", {
                    "recorded_at": _now(), "reason": reason, "exit_code": code,
                    "terminal_output": diagnostic[:32 * 1024],
                })
        else:
            state = _load_state(directory)
        print(json.dumps(state, indent=2))
        return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--headless-child", action="store_true", help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)
    initialize_parser = commands.add_parser("init")
    for name in ("repository", "checkout", "branch", "git", "codex"):
        initialize_parser.add_argument(f"--{name}", required=True)
    initialize_parser.add_argument("--initial-report", help="One existing report to process after initialization")
    for name in ("poll", "status", "resume"):
        commands.add_parser(name)
    commands.add_parser("pause").add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    directory = args.state_dir.expanduser().resolve()
    try:
        if args.command == "status":
            state = _load_state(directory)
            problem_path = directory / "host-problem.json"
            if problem_path.exists():
                problem = _read_json(problem_path)
                if problem.get("error"):
                    state["host_problem"] = problem
            print(json.dumps(state, indent=2))
            return 0
        if args.command == "poll" and os.name == "nt" and not args.headless_child:
            return _windows_poll(directory)
        with lock(directory):
            if args.command == "init":
                state = initialize(directory, {key: getattr(args, key) for key in ("repository", "checkout", "branch", "git", "codex")},
                                   initial_report=args.initial_report)
            else:
                config, state = _load_config(directory), _load_state(directory)
                if args.command == "poll":
                    state = poll(directory, config, state)
                elif args.command == "pause":
                    state = _save(directory, state, "paused", args.reason, paused=True)
                else:
                    state["pending"] = None
                    state = _save(directory, state, "idle", paused=False)
            print(json.dumps(state, indent=2))
            return 1 if state["status"] == "needs_attention" else 0
    except Busy:
        print(json.dumps({"status": "busy", "reason": "worker_busy"}))
        return 0
    except ListenerError as exc:
        print(json.dumps({"status": "needs_attention", "reason": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
