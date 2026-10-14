"""Run local parser checks and analysis using the already checked-out code.

Source exports, saved engineering records and raw test output remain private.
Feedback reports include counts and at most one user-authorized mystery operand
example, committed locally for manual review and pushing.
This workflow never fetches, pulls or pushes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import traceback
from typing import Any
from uuid import uuid4

from .diagnostic_sample import (
    MALFORMED_SAMPLE_KIND, UNMATCHED_COLON_SAMPLE_KIND,
    build_diagnostic_sample, validate_diagnostic_sample,
)
from .reference_summary import build_reference_summary, validate_reference_summary
from .references import _timer_placeholder, analyze_references
from .source import analyze_snapshot, capture_snapshot
from .storage import save_run
from .work_check_tests import unavailable_result, validate_test_result

MAX_REPORT_BYTES = 32 * 1024
_LEGACY_CONSTANTS = {
    "schema_version": 1,
    "report_kind": "l5x_work_machine_check",
    "workflow_version": "work-check-1",
}
_V2_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 2, "workflow_version": "work-check-2"}
_CONSTANTS = _LEGACY_CONSTANTS | {"schema_version": 3, "workflow_version": "work-check-3"}
_FAILURE_CODES = {"read_error", "reference_error", "save_error", "summary_error", "unexpected_error"}
_GIT_REPOSITORY_OVERRIDES = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM", "GIT_IMPLICIT_WORK_TREE", "GIT_PREFIX",
    "GIT_NAMESPACE", "GIT_SHALLOW_FILE", "GIT_GRAFT_FILE", "GIT_REPLACE_REF_BASE",
})


class WorkCheckError(ValueError):
    """A fixed workflow error safe to show without raw process or source text."""


def _invalid() -> None:
    raise WorkCheckError("Work-machine report validation failed.")


def _keys(value: Any, expected: set[str]) -> None:
    if type(value) is not dict or value.keys() != expected:
        _invalid()


def validate_work_check_report(report: Any) -> None:
    """Reject unknown fields and reconcile test, analysis and overall status."""
    if type(report) is not dict or type(report.get("schema_version")) is not int:
        _invalid()
    version = report["schema_version"]
    constants = {1: _LEGACY_CONSTANTS, 2: _V2_CONSTANTS, 3: _CONSTANTS}.get(version)
    if constants is None:
        _invalid()
    extra = {"diagnostic_sample"} if version >= 2 else set()
    _keys(report, set(constants) | {"run_id", "tool_revision", "tests", "analysis", "status"} | extra)
    for key, fixed in constants.items():
        if type(report[key]) is not type(fixed) or report[key] != fixed:
            _invalid()
    if type(report["run_id"]) is not str or re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}", report["run_id"]) is None:
        _invalid()
    revision = report["tool_revision"]
    _keys(revision, {"commit", "worktree"})
    if (type(revision["commit"]) is not str or re.fullmatch(r"[0-9a-f]{40}", revision["commit"]) is None
            or revision["worktree"] != "clean"):
        _invalid()
    _keys(report["tests"], {"application", "helpers"})
    for result in report["tests"].values():
        validate_test_result(result, allow_unavailable=True)
    tests_passed = all(result["status"] == "passed" for result in report["tests"].values())
    analysis = report["analysis"]
    _keys(analysis, {"status", "failure_code", "private_run_saved", "reference_summary"})
    if type(analysis["private_run_saved"]) is not bool or type(analysis["status"]) is not str:
        _invalid()
    if analysis["status"] in ("complete", "partial"):
        if not tests_passed or analysis["failure_code"] is not None or not analysis["private_run_saved"]:
            _invalid()
        nested = analysis["reference_summary"]
        validate_reference_summary(nested)
        if version == 3 and nested["schema_version"] != 5:
            _invalid()
        if nested["status"] != analysis["status"] or nested["source_summary"]["tool_revision"] != revision:
            _invalid()
    elif analysis["status"] == "failed":
        if (not tests_passed or type(analysis["failure_code"]) is not str
                or analysis["failure_code"] not in _FAILURE_CODES or analysis["reference_summary"] is not None):
            _invalid()
        if analysis["private_run_saved"] and analysis["failure_code"] not in ("summary_error", "unexpected_error"):
            _invalid()
    elif analysis["status"] == "not_run":
        if tests_passed or analysis["failure_code"] is not None or analysis["private_run_saved"] or analysis["reference_summary"] is not None:
            _invalid()
    else:
        _invalid()
    expected = "failed" if not tests_passed or analysis["status"] == "failed" else (
        "partial" if analysis["status"] == "partial" else "passed"
    )
    if report["status"] != expected:
        _invalid()
    if version >= 2:
        sample = report["diagnostic_sample"]
        validate_diagnostic_sample(sample)
        if sample is not None:
            if analysis["status"] != "partial":
                _invalid()
            nested = analysis["reference_summary"]
            if nested["source_summary"]["instructions"]["counts"].get(sample["opcode"], 0) == 0:
                _invalid()
            if sample["kind"] == UNMATCHED_COLON_SAMPLE_KIND:
                # This fallback needs dedicated rack evidence. Historical v2
                # reports retain their original malformed-only sample contract.
                if (version != 3 or nested["schema_version"] != 5
                        or nested["rack_candidates"]["matches"]["direct_operands"]
                        ["by_status"]["no_candidate_match"] == 0):
                    _invalid()
                return
            if sample["kind"] != MALFORMED_SAMPLE_KIND:
                _invalid()
            # Keep historical samples readable under their original analyzer,
            # but a current report cannot label a recognized slot as malformed.
            if nested["schema_version"] in {4, 5} and _timer_placeholder(
                    sample["opcode"], sample["argument_index"], sample["raw_text"]):
                _invalid()
            operands = nested["operands"]
            # Samples are direct operands, never a caller hiding an alias-target
            # failure. Schemas 3 through 5 carry the required shape histogram.
            if (nested["schema_version"] not in {3, 4, 5}
                    or operands["by_reason"]["unsupported_address"]["malformed_address"]
                    <= operands["malformed_address_shapes"]["alias_target_failure"]):
                _invalid()


def render_work_check_report(report: Any) -> str:
    validate_work_check_report(report)
    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if len(rendered.encode("utf-8")) > MAX_REPORT_BYTES:
        raise WorkCheckError("Work-machine report exceeds its publication size limit.")
    return rendered


def _private_failure(path: Path, details: bytes | str | None = None) -> None:
    """Best-effort diagnostics must not prevent a count-only failure report."""
    try:
        with path.open("a", encoding="utf-8") as stream:
            traceback.print_exc(file=stream)
            if details:
                stream.write(details.decode("utf-8", errors="replace") if isinstance(details, bytes) else details)
                stream.write("\n")
    except (OSError, UnicodeError):
        pass


def _git(root: Path, *arguments: str, logs: Path | None = None, raw: bool = False) -> str:
    # Do not inherit alternate work-tree/index settings. Preserve the user's
    # normal Git configuration for local revision checks and report commits.
    environment = {key: value for key, value in os.environ.items() if key.upper() not in _GIT_REPOSITORY_OVERRIDES}
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
            timeout=180, env=environment,
        )
        output = result.stdout.decode("utf-8")
        return output if raw or "-z" in arguments else output.strip()
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        if logs is not None:
            _private_failure(logs / "git.log", getattr(exc, "stderr", None))
        action = arguments[0] if arguments and arguments[0] in {
            "status", "rev-parse", "symbolic-ref", "add", "commit", "diff-tree", "show",
        } else "operation"
        message = f"Git {action} failed; existing files and commits were preserved."
        if action == "commit":
            message += " The report remains local; nothing was pushed. Check your Git identity and commit configuration."
        if logs is not None:
            message += " See git.log in the local logs folder if available."
        raise WorkCheckError(message) from exc


def _checkout_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists() and (parent / "python-parser").is_dir():
            if Path(_git(parent, "rev-parse", "--show-toplevel")).resolve() == parent and Path.cwd().resolve() == parent:
                return parent
            break
    raise WorkCheckError("Run the work-machine launcher from its repository checkout.")


def _branch(root: Path) -> str:
    # Branch naming is a development convention, not a parser requirement.
    # symbolic-ref still rejects detached HEAD before any analysis is started.
    return _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")


def _check_pinned(root: Path, branch: str, commit: str, report_path: str | None = None) -> None:
    if _branch(root) != branch or _git(root, "rev-parse", "HEAD") != commit:
        raise WorkCheckError("The checked branch or commit changed; local results were preserved for review.")
    status = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    allowed = {""} if report_path is None else {f"?? {report_path}\0", f"A  {report_path}\0"}
    if status not in allowed:
        raise WorkCheckError("Working-tree changes were found; local results were preserved for review.")


def _config_path(root: Path) -> Path:
    value = Path(_git(root, "rev-parse", "--git-path", "plc-work-check.json"))
    destination = root / value if not value.is_absolute() else value
    git_directory = Path(_git(root, "rev-parse", "--absolute-git-dir")).resolve()
    if destination.is_symlink() or destination.resolve() != git_directory / "plc-work-check.json":
        raise WorkCheckError("Saved-source configuration must remain in this checkout's Git directory.")
    return destination.resolve()


def _check_report_file(root: Path, relative_report: str, rendered: str) -> None:
    """Do not treat an edited file at the expected path as our validated report."""
    path = root / relative_report
    try:
        if not path.is_symlink() and path.read_bytes() == rendered.encode("utf-8"):
            return
    except OSError:
        pass
    raise WorkCheckError("Report content changed or became unavailable; local results were preserved. Review before pushing.")


def _source_path(root: Path, supplied: str | None) -> Path:
    if supplied is None:
        try:
            payload = json.loads(_config_path(root).read_text(encoding="utf-8"))
            if (type(payload) is not dict or payload.keys() != {"schema_version", "source"}
                    or type(payload["schema_version"]) is not int or payload["schema_version"] != 1
                    or type(payload["source"]) is not str):
                raise ValueError
            path = Path(payload["source"])
            if not path.is_absolute():
                raise ValueError
        except (OSError, ValueError, TypeError):
            raise WorkCheckError("No usable saved source. Run the launcher with an L5X filename or path.") from None
    else:
        path = Path(supplied).expanduser()
        if not path.is_absolute():
            path = root / "confidential" / "plc-code" / path if len(path.parts) == 1 else root / path
    try:
        source = path.resolve()
        if not source.is_file() or source.suffix.lower() != ".l5x":
            raise WorkCheckError("The selected L5X file does not exist; supply its filename or path.")
        return source
    except OSError:
        raise WorkCheckError("The selected L5X file could not be accessed.") from None


def _remember_source(root: Path, source: Path) -> None:
    destination = _config_path(root)
    descriptor, name = tempfile.mkstemp(prefix=".plc-work-check-", dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"schema_version": 1, "source": str(source)}, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _private_logs(root: Path, run_id: str) -> Path:
    destination = root / "confidential" / "work-checks" / run_id
    if destination.resolve() != destination:
        raise WorkCheckError("Private output must remain in this checkout's confidential directory.")
    destination.mkdir(parents=True, exist_ok=False)
    if destination.resolve() != destination:
        raise WorkCheckError("Private output path changed during creation.")
    return destination


def _run_suite(root: Path, logs: Path, suite: str) -> dict[str, Any]:
    output = logs / f"{suite}-tests.json"
    try:
        with (logs / f"{suite}-tests.log").open("xb") as stream:
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "plc_workbench.work_check_tests", "--suite", suite, "--output", str(output)],
                cwd=root, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                check=False, timeout=1800,
            )
        if output.stat().st_size > MAX_REPORT_BYTES:
            raise ValueError
        payload = json.loads(output.read_text(encoding="utf-8"))
        validate_test_result(payload)
        if completed.returncode != (0 if payload["status"] == "passed" else 1):
            raise ValueError
        # Reconstruct the allowed result instead of forwarding subprocess JSON.
        return {
            "schema_version": 1, "status": payload["status"],
            "counts": {key: payload["counts"][key] for key in (
                "tests_run", "failures", "errors", "skipped", "expected_failures", "unexpected_successes",
            )},
            "failed_test_ids": list(payload["failed_test_ids"]),
            "failure_ids_omitted": payload["failure_ids_omitted"],
        }
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        return unavailable_result("runner_error")


def _analyze(root: Path, source: Path, logs: Path, revision: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "failed", "failure_code": "read_error", "private_run_saved": False,
                              "reference_summary": None, "diagnostic_sample": None}
    try:
        snapshot = capture_snapshot(source)
        inventory = analyze_snapshot(snapshot)
        result["failure_code"] = "reference_error"
        references = analyze_references(inventory)
        result["failure_code"] = "save_error"
        workspace = root / "confidential" / "workspaces" / "work-check"
        if workspace.resolve() != workspace:
            raise WorkCheckError("Private workspace must remain inside this checkout.")
        save_run(workspace, snapshot, inventory, references=references)
        result["private_run_saved"] = True
        result["failure_code"] = "summary_error"
        summary = build_reference_summary(inventory, references, revision=revision)
        sample = build_diagnostic_sample(inventory, references)
        result.update(status=summary["status"], failure_code=None, reference_summary=summary,
                      diagnostic_sample=sample)
    except Exception:
        # All raw exception text stays private, including OS paths and values
        # from unexpected third-party failures.
        _private_failure(logs / "analysis.log")
    return result


def run_check(root: Path, supplied_source: str | None) -> int:
    """Commit only the validated feedback report, without contacting a remote."""
    branch = _branch(root)
    commit = _git(root, "rev-parse", "HEAD")
    _check_pinned(root, branch, commit)
    source = _source_path(root, supplied_source)
    if supplied_source is not None:
        _remember_source(root, source)
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    logs = _private_logs(root, run_id)
    print(f"Selected local source: {source}", flush=True)
    print(f"Local logs: {logs}", flush=True)
    results: dict[str, Any] = {}
    for suite in ("application", "helpers"):
        print(f"Running {suite} parser tests (work-machine selection)...", flush=True)
        results[suite] = _run_suite(root, logs, suite)
        result = results[suite]
        count = result["counts"]["tests_run"] if result["counts"] is not None else 0
        print(f"{suite} tests: {result['status']} ({count} run).", flush=True)
    revision = {"commit": commit, "worktree": "clean"}
    if all(result["status"] == "passed" for result in results.values()):
        print("Analyzing source and saving private results...", flush=True)
        analysis = _analyze(root, source, logs, revision)
    else:
        analysis = {"status": "not_run", "failure_code": None, "private_run_saved": False, "reference_summary": None}
    status = "failed" if analysis["status"] in ("not_run", "failed") else (
        "partial" if analysis["status"] == "partial" else "passed"
    )
    # The bounded sample is separate from the unchanged count-only reference
    # summary and its historical analysis envelope.
    sample = analysis.pop("diagnostic_sample", None)
    report = dict(_CONSTANTS, run_id=run_id, tool_revision=revision, tests=results,
                  analysis=analysis, status=status, diagnostic_sample=sample)
    rendered = render_work_check_report(report)
    _check_pinned(root, branch, commit)
    relative_report = f"public/inspection/work-check-{run_id}.json"
    from .summary_output import publish_summary
    publish_summary(root / relative_report, rendered, input_path=source)
    print(f"Saved work-machine report locally: {relative_report}", flush=True)
    _check_pinned(root, branch, commit, relative_report)
    _check_report_file(root, relative_report, rendered)
    _git(root, "add", "--", relative_report, logs=logs)
    _check_pinned(root, branch, commit, relative_report)
    _check_report_file(root, relative_report, rendered)
    # Git filters can change the staged blob independently of the working file.
    if _git(root, "show", f":{relative_report}", logs=logs, raw=True) != rendered:
        raise WorkCheckError("Staged report content changed; local results were preserved. Review before pushing.")
    # --only limits the commit to this report even if another process stages
    # unrelated changes between the pin check and the commit command.
    _git(root, "commit", "--only", "-m", "test(workflow): record work-machine check",
         "--", relative_report, logs=logs)
    saved_commit = _git(root, "rev-parse", "HEAD")
    _check_pinned(root, branch, saved_commit)
    if (_git(root, "rev-parse", "HEAD^") != commit
            or _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD") != relative_report):
        raise WorkCheckError("Commit history changed unexpectedly; local results were preserved. Review before pushing.")
    if _git(root, "show", f"{saved_commit}:{relative_report}", logs=logs, raw=True) != rendered:
        raise WorkCheckError("Committed report content changed; local results were preserved. Review before pushing.")
    print(f"Committed work-machine report locally: {saved_commit[:12]}", flush=True)
    print("Nothing was pulled or pushed. Review the report, then run git push when ready.", flush=True)
    print(f"Check status: {status}. Raw logs and engineering records remain under confidential/.", flush=True)
    return 1 if status == "failed" else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local parser tests and analysis without automatic Git synchronization.")
    parser.add_argument("source", nargs="?", help="L5X filename under confidential/plc-code, or an explicit path. Saved locally for later runs.")
    arguments = parser.parse_args(argv)
    try:
        return run_check(_checkout_root(), arguments.source)
    except WorkCheckError as exc:
        print(str(exc), file=sys.stderr)
    except Exception:
        print("Work-machine check could not finish. Existing files and commits were preserved.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
