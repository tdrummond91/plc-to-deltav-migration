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
    from .access import AccessResult
    from .models import SourceSnapshot
    from .pid import PidResult
    from .pid_members import PidMemberResult
    from .calculations import CalculationResult
    from .rung_analysis import RungAnalysisResult
    from .relationships import RelationshipResult
    from .conditions import ConditionResult
    from .references import ReferenceResult
    from .sfc_structure import SfcStructureResult
    from .tag_data import TagDataResult


class StorageError(ValueError):
    """Safe write error that never embeds source data or OS exception text."""

    def __init__(self, message: str, *, code: str = 'save_error') -> None:
        super().__init__(message)
        # Callers publishing feedback must admit only their versioned, closed
        # code vocabulary. Messages and causes remain private diagnostic detail.
        self.code = code


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
            raise StorageError("Workspaces inside this checkout must be beneath confidential/.", code='save_workspace_error')
    return resolved


def _assert_run_path(workspace: Path, run_dir: Path) -> None:
    if workspace.resolve() != workspace or run_dir.is_symlink():
        raise StorageError("Workspace or run path changed during publication.", code='save_workspace_error')
    if run_dir.resolve() != run_dir or run_dir.parent != workspace:
        raise StorageError("Run path must remain directly inside the resolved workspace.", code='save_workspace_error')


def _write_artifact(workspace: Path, run_dir: Path, name: str, data: bytes) -> dict[str, object]:
    _assert_run_path(workspace, run_dir)
    destination = run_dir / name
    if destination.parent != run_dir or destination.resolve() != destination:
        raise StorageError("Artifact path escaped the run directory.", code='save_workspace_error')
    # Exclusive creation protects the input and any existing run artifacts.
    with destination.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}


def save_run(
    workspace: Path, snapshot: SourceSnapshot, result: InventoryView,
    *, references: ReferenceResult | None = None,
    sfc_structure: SfcStructureResult | None = None,
    include_review: bool = False,
    access: AccessResult | None = None,
    tag_data: TagDataResult | None = None,
    pid: PidResult | None = None,
    pid_members: PidMemberResult | None = None,
    calculations: CalculationResult | None = None,
    rung_analysis: RungAnalysisResult | None = None,
    relationships: RelationshipResult | None = None,
    conditions: ConditionResult | None = None,
) -> Path:
    """Save the complete inventory, irrespective of any CLI rung selection.

    No existing run is reused or overwritten. A failure leaves an incomplete
    private run for inspection; it never marks that run complete.
    """
    try:
        if type(include_review) is not bool or (include_review and (references is None or sfc_structure is None)):
            raise StorageError("A review run requires inventory, references and SFC structure.")
        if access is not None and not include_review:
            raise StorageError("Access records require a complete engineering review run.")
        if tag_data is not None and (access is None or not include_review):
            raise StorageError("Tag Data records require an engineering review with operand access.")
        if pid is not None and (tag_data is None or access is None or not include_review):
            raise StorageError("PID records require an engineering review with operand access and Tag Data.")
        if pid_members is not None and (pid is None or tag_data is None or access is None or not include_review):
            raise StorageError("PID member records require an engineering review with PID evidence.")
        if calculations is not None and (pid_members is None or pid is None or tag_data is None or access is None or not include_review):
            raise StorageError("Calculation records require an engineering review with PID member evidence.")
        if rung_analysis is not None and (calculations is None or pid_members is None or pid is None
                                         or tag_data is None or access is None or not include_review):
            raise StorageError("Rung analysis records require a complete engineering review with calculation evidence.")
        if relationships is not None and (rung_analysis is None or not include_review):
            raise StorageError("Relationship records require a complete engineering review with rung evidence.")
        if conditions is not None and (relationships is None or not include_review):
            raise StorageError("Condition records require a complete engineering review with relationship evidence.")
        payload = result.to_dict()
        expected = {"id": snapshot.id, "sha256": snapshot.sha256, "size_bytes": snapshot.size_bytes}
        if payload["snapshot"] != expected or payload["status"] not in ("complete", "partial"):
            raise StorageError("Inventory does not match the captured source snapshot.")
        if references is not None:
            from .references import ReferenceError, validate_references
            try:
                validate_references(result, references)
            except ReferenceError as exc:
                raise StorageError("Reference records do not match the captured source inventory.") from exc
            reference_payload = references.to_dict()
            if (reference_payload["snapshot"] != expected
                    or reference_payload["status"] not in ("complete", "partial")
                    or reference_payload["coverage"]["source_status"] != payload["status"]):
                raise StorageError("References do not match the captured source inventory.")
        if sfc_structure is not None:
            from .sfc_structure import SfcStructureError, validate_sfc_structure
            try:
                validate_sfc_structure(snapshot, result, sfc_structure)
            except SfcStructureError as exc:
                raise StorageError("SFC structure does not match the captured source inventory.") from exc
            sfc_payload = sfc_structure.to_dict()
            if (sfc_payload["snapshot"] != expected
                    or sfc_payload["status"] not in ("complete", "partial")):
                raise StorageError("SFC structure does not match the captured source inventory.")
        digest = hashlib.sha256(snapshot.data).hexdigest()
        if (
            len(snapshot.data) != snapshot.size_bytes
            or digest != snapshot.sha256
            or snapshot.id != f"sha256:{digest}"
        ):
            raise StorageError("Captured source bytes do not match their identity.")
        if include_review:
            from .review import ReviewError, ReviewSizeLimitError, build_review_data
            from .review_html import ReviewHtmlError, ReviewHtmlSizeLimitError, render_review_html
            try:
                review_data = build_review_data(snapshot, result, references, sfc_structure,
                                                access=access, tag_data=tag_data, pid=pid,
                                                pid_members=pid_members, calculations=calculations,
                                                rung_analysis=rung_analysis, relationships=relationships,
                                                conditions=conditions)
                review_html = render_review_html(review_data).encode("utf-8")
            except (ReviewSizeLimitError, ReviewHtmlSizeLimitError) as exc:
                raise StorageError("Private engineering review exceeds its report size limit.", code='review_size_limit') from exc
            except ReviewError as exc:
                raise StorageError("Could not validate the private engineering review report.", code='review_validation_error') from exc
            except ReviewHtmlError as exc:
                raise StorageError("Could not render the private engineering review report.", code='review_render_error') from exc
        # Finish every validation and rendering step before allocating a run.
        contents = {
            "snapshot.L5X": snapshot.data,
            "inventory.json": render_json(result).encode("utf-8"),
            "overview.txt": render_text(result).encode("utf-8"),
        }
        if references is not None:
            from .reference_reporting import render_reference_json, render_reference_text
            contents.update({
                "references.json": render_reference_json(references).encode("utf-8"),
                "references.txt": render_reference_text(references, inventory=result).encode("utf-8"),
            })
        if sfc_structure is not None:
            from .sfc_structure import render_sfc_json, render_sfc_text
            contents.update({
                "sfc-structure.json": render_sfc_json(sfc_structure).encode("utf-8"),
                "sfc-structure.txt": render_sfc_text(sfc_structure, inventory=result).encode("utf-8"),
            })
        if include_review:
            contents["review.html"] = review_html
        if access is not None:
            from .access import AccessError, render_access_json
            try:
                access_payload = access.to_dict()
                contents["access.json"] = render_access_json(access).encode("utf-8")
            except AccessError as exc:
                raise StorageError("Could not render captured operand access records.") from exc
        if tag_data is not None:
            from .tag_data import TagDataError, render_tag_data_json
            try:
                tag_data_payload = tag_data.to_dict()
                contents["tag-data.json"] = render_tag_data_json(tag_data).encode("utf-8")
            except TagDataError as exc:
                raise StorageError("Could not render captured Tag Data records.") from exc
        if pid is not None:
            from .pid import PidError, render_pid_json
            try:
                pid_payload = pid.to_dict()
                contents["pid.json"] = render_pid_json(pid).encode("utf-8")
            except PidError as exc:
                raise StorageError("Could not render captured PID records.") from exc
        if pid_members is not None:
            from .pid_members import PidMemberError, render_pid_members_json
            try:
                pid_member_payload = pid_members.to_dict()
                contents["pid-members.json"] = render_pid_members_json(pid_members).encode("utf-8")
            except PidMemberError as exc:
                raise StorageError("Could not render captured PID member records.") from exc
        if calculations is not None:
            from .calculations import CalculationError, render_calculation_json
            try:
                calculation_payload = calculations.to_dict()
                contents["calculations.json"] = render_calculation_json(calculations).encode("utf-8")
            except CalculationError as exc:
                raise StorageError("Could not render captured calculation records.") from exc
        if rung_analysis is not None:
            from .rung_analysis import RungAnalysisError, render_rung_analysis_json
            try:
                rung_payload = rung_analysis.to_dict()
                contents["rung-analysis.json"] = render_rung_analysis_json(rung_analysis).encode("utf-8")
            except RungAnalysisError as exc:
                raise StorageError("Could not render captured rung analysis records.") from exc
        if relationships is not None:
            from .relationships import RelationshipError, render_relationships_json
            try:
                relationship_payload = relationships.to_dict()
                contents["relationships.json"] = render_relationships_json(relationships).encode("utf-8")
            except RelationshipError as exc:
                raise StorageError("Could not render captured relationship records.") from exc
        if conditions is not None:
            from .conditions import ConditionError, render_conditions_json
            try:
                condition_payload = conditions.to_dict()
                contents["boolean-conditions.json"] = render_conditions_json(conditions).encode("utf-8")
            except ConditionError as exc:
                raise StorageError("Could not render captured condition records.") from exc
        destination = _workspace_path(workspace)
        destination.mkdir(parents=True, exist_ok=True)
        if destination.resolve() != destination:
            raise StorageError("Workspace changed during creation.", code='save_workspace_error')
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
        if references is not None:
            manifest.update({
                "schema_version": 2,
                "artifact_kind": "source_reference_run",
                "status": reference_payload["status"],
                "analysis_scope": reference_payload["analysis_scope"],
                "analyzer_version": reference_payload["analyzer_version"],
                "effect_analysis": reference_payload["effect_analysis"],
                "member_validation": reference_payload["member_validation"],
            })
        if sfc_structure is not None:
            statuses = [payload["status"], sfc_payload["status"]]
            if references is not None:
                statuses.append(reference_payload["status"])
            manifest.update({
                "schema_version": 3,
                "artifact_kind": ("source_reference_sfc_structure_run" if references is not None
                                  else "source_sfc_structure_run"),
                "status": "partial" if "partial" in statuses else "complete",
                "sfc_schema_version": sfc_payload["schema_version"],
                "sfc_analyzer_version": sfc_payload["analyzer_version"],
                "sfc_analysis_scope": sfc_payload["analysis_scope"],
            })
        if include_review:
            manifest.update({
                "schema_version": 4,
                "artifact_kind": "source_reference_sfc_review_run",
                "review_schema_version": review_data["schema_version"],
                "review_version": review_data["report_version"],
            })
        if access is not None:
            manifest.update({
                "schema_version": 5,
                "artifact_kind": "source_reference_sfc_access_review_run",
                "status": "partial" if "partial" in (manifest["status"], access_payload["status"]) else "complete",
                "access_schema_version": access_payload["schema_version"],
                "access_analyzer_version": access_payload["analyzer_version"],
            })
        if tag_data is not None:
            manifest.update({
                "schema_version": 6,
                "artifact_kind": "source_reference_sfc_access_tag_data_review_run",
                "status": "partial" if "partial" in (manifest["status"], tag_data_payload["status"]) else "complete",
                "tag_data_schema_version": tag_data_payload["schema_version"],
                "tag_data_analyzer_version": tag_data_payload["analyzer_version"],
            })
        if pid is not None:
            manifest.update({
                "schema_version": 7,
                "artifact_kind": "source_reference_sfc_access_tag_data_pid_review_run",
                "status": "partial" if "partial" in (manifest["status"], pid_payload["status"]) else "complete",
                "pid_schema_version": pid_payload["schema_version"],
                "pid_analyzer_version": pid_payload["analyzer_version"],
            })
        if pid_members is not None:
            manifest.update({
                "schema_version": 8,
                "artifact_kind": "source_reference_sfc_access_tag_data_pid_member_review_run",
                "status": "partial" if "partial" in (manifest["status"], pid_member_payload["status"]) else "complete",
                "pid_member_schema_version": pid_member_payload["schema_version"],
                "pid_member_analyzer_version": pid_member_payload["analyzer_version"],
                "pid_member_catalog_version": pid_member_payload["catalog_version"],
            })
        if calculations is not None:
            manifest.update({
                "schema_version": 9,
                "artifact_kind": "source_reference_sfc_access_tag_data_pid_member_calculation_review_run",
                "status": "partial" if "partial" in (manifest["status"], calculation_payload["status"]) else "complete",
                "calculation_schema_version": calculation_payload["schema_version"],
                "calculation_analyzer_version": calculation_payload["analyzer_version"],
            })
        if rung_analysis is not None:
            manifest.update({
                "schema_version": 10,
                "artifact_kind": "source_reference_sfc_access_tag_data_pid_member_calculation_rung_review_run",
                "status": "partial" if "partial" in (manifest["status"], rung_payload["status"]) else "complete",
                "analysis_scope": review_data["analysis_scope"],
                "semantic_analysis": review_data["semantic_analysis"],
                "rung_analysis_schema_version": rung_payload["schema_version"],
                "rung_analysis_analyzer_version": rung_payload["analyzer_version"],
            })
        if relationships is not None:
            manifest.update({
                "schema_version": 11,
                "artifact_kind": "source_reference_sfc_access_tag_data_pid_member_calculation_rung_relationship_review_run",
                "status": "partial" if "partial" in (manifest["status"], relationship_payload["status"]) else "complete",
                "analysis_scope": review_data["analysis_scope"],
                "relationship_schema_version": relationship_payload["schema_version"],
                "relationship_analyzer_version": relationship_payload["analyzer_version"],
            })
        if conditions is not None:
            manifest.update({
                "schema_version": 12,
                "artifact_kind": "source_reference_sfc_access_tag_data_pid_member_calculation_rung_relationship_condition_review_run",
                "status": "partial" if "partial" in (manifest["status"], condition_payload["status"]) else "complete",
                "analysis_scope": review_data["analysis_scope"],
                "condition_schema_version": condition_payload["schema_version"],
                "condition_analyzer_version": condition_payload["analyzer_version"],
            })
        _write_artifact(
            destination, run_dir, ".manifest.pending",
            (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
        )
        _assert_run_path(destination, run_dir)
        final_manifest = run_dir / "manifest.json"
        if final_manifest.exists() or final_manifest.is_symlink():
            raise StorageError("A run manifest already exists; refusing to overwrite it.", code='save_workspace_error')
        os.replace(run_dir / ".manifest.pending", final_manifest)
        return run_dir
    except OSError as exc:
        raise StorageError("Could not save the private run. Check destination access and free space; any unfinished run has no final manifest.", code='save_io_error') from exc
    except RuntimeError as exc:
        raise StorageError("Could not save the private run. Check destination access and free space; any unfinished run has no final manifest.") from exc
