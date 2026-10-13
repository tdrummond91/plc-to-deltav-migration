"""Publish a validated aggregate summary without clobbering any file."""

from __future__ import annotations

import os
import json
from pathlib import Path
import tempfile

from .summary import MAX_REPORT_BYTES, render_summary


class SummaryOutputError(ValueError):
    """A fixed safe publication failure, without source or destination paths."""


def _checkout_root() -> Path | None:
    # The output boundary follows the installed source checkout, never cwd.
    # Packaged installations have no checkout and use the explicit destination.
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists() and (parent / "python-parser").is_dir():
            return parent
    return None


def _destination_path(output: Path, input_path: Path) -> Path:
    expanded = output.expanduser()
    if expanded.suffix.lower() != ".json":
        raise SummaryOutputError("Summary output must use a .json extension.")
    if expanded.is_symlink() or expanded.exists():
        raise SummaryOutputError("Summary output already exists; choose a new file.")
    destination = expanded.resolve()
    if destination == input_path.expanduser().resolve():
        raise SummaryOutputError("Summary output cannot replace its input.")
    checkout = _checkout_root()
    if checkout is not None and destination.is_relative_to(checkout):
        allowed = (checkout / "confidential", checkout / "public" / "inspection")
        if not any(destination.is_relative_to(folder) for folder in allowed):
            raise SummaryOutputError("Summary output inside this checkout must be beneath public/inspection/ or confidential/.")
    return destination


def publish_summary(output: Path, rendered: str, *, input_path: Path) -> None:
    """Publish UTF-8 bytes with an atomic no-clobber hard link.

    The temporary file and destination share a directory/filesystem. An
    unsupported hard-link operation fails closed; no rename/overwrite fallback
    weakens the no-clobber guarantee. As with private workspaces, this is a
    local single-owner destination, not a hostile filesystem security boundary.
    """
    temporary: Path | None = None
    try:
        # This entry point can write into the synced tree. Validate independently
        # of the CLI and serialize canonical output rather than copying arbitrary
        # caller text (including duplicate JSON keys or hidden extra fields).
        if len(rendered.encode('utf-8')) > MAX_REPORT_BYTES:
            raise SummaryOutputError('Summary exceeds its publication size limit.')
        try:
            payload = json.loads(rendered)
            # Dispatch only known closed publication contracts. Callers cannot
            # provide their own validator or bypass validation for private data.
            if isinstance(payload, dict) and payload.get('report_kind') == 'l5x_reference_review_summary':
                from .reference_summary import render_reference_summary
                rendered = render_reference_summary(payload)
            elif isinstance(payload, dict) and payload.get('report_kind') == 'l5x_work_machine_check':
                from .work_check import render_work_check_report
                rendered = render_work_check_report(payload)
            else:
                rendered = render_summary(payload)
        except (ValueError, TypeError, RecursionError) as exc:
            raise SummaryOutputError('Only a validated aggregate summary can be published.') from exc
        destination = _destination_path(output, input_path)
        parent = destination.parent
        parent.mkdir(parents=True, exist_ok=True)
        if parent.resolve() != parent:
            raise SummaryOutputError("Summary destination changed during publication.")
        descriptor, filename = tempfile.mkstemp(prefix=".plc-summary-", suffix=".pending", dir=parent)
        temporary = Path(filename)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(rendered.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        if parent.resolve() != parent or destination.is_symlink():
            raise SummaryOutputError("Summary destination changed during publication.")
        # os.link is atomic and refuses an existing destination, including one
        # created by another writer after our preliminary checks.
        os.link(temporary, destination)
    except FileExistsError as exc:
        raise SummaryOutputError("Summary output already exists; choose a new file.") from exc
    except (OSError, RuntimeError, UnicodeError) as exc:
        raise SummaryOutputError(
            "Could not publish summary. Check destination access, free space and hard-link support; no output was published."
        ) from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                # Cleanup failure does not invalidate an already linked,
                # complete result. A .pending file is never a published report.
                pass
