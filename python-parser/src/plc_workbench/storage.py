"""Append-only private inventory runs, finalized by an atomic manifest publish.

Unique directories are owned by this invocation. Consumers must ignore runs
without manifest.json; interruption can leave .manifest.pending and other files.
This is a local single-owner workspace, not a multi-user filesystem security
boundary or a complete backup/review-history system.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from .reporting import InventoryView, render_json, render_text

if TYPE_CHECKING:
    from .models import SourceSnapshot


class StorageError(ValueError):
    """Safe write error that never embeds source data or OS exception text."""


def _checkout_root() -> Path | None:
    # Anchor to installed source, not cwd: invoking from another directory must
    # not bypass this checkout's public/private boundary. Packaged apps may
    # have no checkout and rely on the explicitly chosen private destination.
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists() and (parent / "python-parser").is_dir():
            return parent
    return None


def _workspace_path(workspace: Path) -> Path:
    resolved = workspace.expanduser().resolve()
    checkout = _checkout_root()
    if checkout is not None and resolved.is_relative_to(checkout):
        private = checkout / "confidential"
        if not resolved.is_relative_to(private):
            raise StorageError("Workspaces inside this checkout must be beneath confidential/.")
    return resolved


def _assert_run_path(workspace: Path, run_dir: Path) -> None:
    if workspace.resolve() != workspace or run_dir.is_symlink():
        raise StorageError("Workspace or run path changed during publication.")
    if run_dir.resolve() != run_dir or run_dir.parent != workspace:
        raise StorageError("Run path must remain directly inside the resolved workspace.")


def _write_artifact(workspace: Path, run_dir: Path, name: str, data: bytes) -> dict[str, object]:
    _assert_run_path(workspace, run_dir)
    destination = run_dir / name
    if destination.parent != run_dir or destination.resolve() != destination:
        raise StorageError("Artifact path escaped the run directory.")
    # Exclusive creation protects the input and any existing run artifacts.
    with destination.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}


def save_run(workspace: Path, snapshot: SourceSnapshot, result: InventoryView) -> Path:
    """Save the complete inventory, irrespective of any CLI rung selection.

    No existing run is reused or overwritten. A failure leaves an incomplete
    private run for inspection; it never marks that run complete.
    """
    try:
        payload = result.to_dict()
        expected = {"id": snapshot.id, "sha256": snapshot.sha256, "size_bytes": snapshot.size_bytes}
        if payload["snapshot"] != expected or payload["status"] not in ("complete", "partial"):
            raise StorageError("Inventory does not match the captured source snapshot.")
        digest = hashlib.sha256(snapshot.data).hexdigest()
        if (
            len(snapshot.data) != snapshot.size_bytes
            or digest != snapshot.sha256
            or snapshot.id != f"sha256:{digest}"
        ):
            raise StorageError("Captured source bytes do not match their identity.")
        destination = _workspace_path(workspace)
        destination.mkdir(parents=True, exist_ok=True)
        if destination.resolve() != destination:
            raise StorageError("Workspace changed during creation.")
        created = datetime.now(timezone.utc)
        for _ in range(10):
            run_id = f"run-{created.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex}"
            run_dir = destination / run_id
            try:
                run_dir.mkdir(mode=0o700, exist_ok=False)
                break
            except FileExistsError:
                continue
        else:
            raise StorageError("Could not allocate a new run directory without a collision.")
        contents = {
            "snapshot.L5X": snapshot.data,
            "inventory.json": render_json(result).encode("utf-8"),
            "overview.txt": render_text(result).encode("utf-8"),
        }
        artifacts = {
            name: _write_artifact(destination, run_dir, name, data)
            for name, data in contents.items()
        }
        manifest = {
            "schema_version": 1,
            "artifact_kind": "source_inventory_run",
            "run_id": run_id,
            "created_utc": created.isoformat(),
            "status": payload["status"],
            "snapshot": expected,
            "parser_version": payload["parser_version"],
            "analysis_scope": payload["analysis_scope"],
            "semantic_analysis": payload["semantic_analysis"],
            "artifacts": artifacts,
        }
        _write_artifact(
            destination, run_dir, ".manifest.pending",
            (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
        )
        _assert_run_path(destination, run_dir)
        final_manifest = run_dir / "manifest.json"
        if final_manifest.exists() or final_manifest.is_symlink():
            raise StorageError("A run manifest already exists; refusing to overwrite it.")
        os.replace(run_dir / ".manifest.pending", final_manifest)
        return run_dir
    except (OSError, RuntimeError) as exc:
        raise StorageError("Could not save the private run. Check destination access and free space; any unfinished run has no final manifest.") from exc
