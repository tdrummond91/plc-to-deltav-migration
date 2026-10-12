"""Private publication checks using entirely invented source bytes."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.models import InventoryResult, SourceSnapshot
from plc_workbench.source import snapshot_from_bytes
from plc_workbench.storage import StorageError, _assert_run_path, _write_artifact, save_run


def sample() -> tuple[SourceSnapshot, InventoryResult]:
    data = b'<RSLogix5000Content><Controller Name="Invented"/></RSLogix5000Content>'
    snapshot = snapshot_from_bytes(data)
    result = InventoryResult(
        snapshot={"id": snapshot.id, "sha256": snapshot.sha256, "size_bytes": snapshot.size_bytes},
        export_attributes={}, entities=[], rungs=[], diagnostics=[],
        counts={"controllers": 1}, routine_types={}, instruction_counts={},
        coverage={}, status="complete",
    )
    return snapshot, result


class StorageTests(unittest.TestCase):
    def test_saved_files_match_one_snapshot_and_manifest_hashes(self) -> None:
        snapshot, result = sample()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private workspace with spaces"
            source = Path(directory) / "input with spaces.L5X"
            source.write_bytes(snapshot.data)
            run = save_run(workspace, snapshot, result)
            self.assertEqual(source.read_bytes(), snapshot.data)
            self.assertEqual(run.parent, workspace.resolve())
            self.assertEqual({p.name for p in run.iterdir()}, {
                "snapshot.L5X", "inventory.json", "overview.txt", "manifest.json",
            })
            self.assertEqual((run / "snapshot.L5X").read_bytes(), snapshot.data)
            self.assertEqual(json.loads((run / "inventory.json").read_text()), result.to_dict())
            manifest = json.loads((run / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["snapshot"], result.snapshot)
            for name, details in manifest["artifacts"].items():
                saved = (run / name).read_bytes()
                self.assertEqual(details, {"sha256": hashlib.sha256(saved).hexdigest(), "size_bytes": len(saved)})
            self.assertNotIn(str(source), json.dumps(manifest))

    def test_reruns_do_not_overwrite_prior_run_or_input(self) -> None:
        snapshot, result = sample()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            first = save_run(workspace, snapshot, result)
            contents = {p.name: p.read_bytes() for p in first.iterdir()}
            second = save_run(workspace, snapshot, result)
            self.assertNotEqual(first, second)
            self.assertEqual(contents, {p.name: p.read_bytes() for p in first.iterdir()})

    def test_collision_never_reuses_an_existing_run(self) -> None:
        snapshot, result = sample()
        instant = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            existing = workspace / f"run-{instant.strftime('%Y%m%dT%H%M%S%fZ')}-collision"
            existing.mkdir()
            marker = existing / "snapshot.L5X"
            marker.write_bytes(b"existing input")
            with patch("plc_workbench.storage.datetime") as clock, patch("plc_workbench.storage.uuid4") as uuid:
                clock.now.return_value = instant
                uuid.return_value.hex = "collision"
                with self.assertRaises(StorageError):
                    save_run(workspace, snapshot, result)
            self.assertEqual(marker.read_bytes(), b"existing input")
            self.assertEqual(list(workspace.iterdir()), [existing])

    def test_failed_publication_has_no_final_manifest(self) -> None:
        snapshot, result = sample()
        with tempfile.TemporaryDirectory() as directory:
            with patch("plc_workbench.storage.os.replace", side_effect=OSError("PRIVATE NAME")):
                with self.assertRaises(StorageError) as caught:
                    save_run(Path(directory), snapshot, result)
            self.assertNotIn("PRIVATE NAME", str(caught.exception))
            runs = list(Path(directory).iterdir())
            self.assertEqual(len(runs), 1)
            self.assertFalse((runs[0] / "manifest.json").exists())
            self.assertTrue((runs[0] / ".manifest.pending").exists())

    def test_checkout_public_output_and_file_destinations_are_rejected(self) -> None:
        snapshot, result = sample()
        checkout = Path(__file__).resolve().parents[2]
        with self.assertRaises(StorageError):
            save_run(checkout / "public" / "forbidden-workspace", snapshot, result)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.L5X"
            source.write_bytes(snapshot.data)
            with self.assertRaises(StorageError):
                save_run(source, snapshot, result)
            self.assertEqual(source.read_bytes(), snapshot.data)

    def test_artifacts_cannot_escape_or_replace_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            run = workspace / "run"
            run.mkdir()
            with self.assertRaises(StorageError):
                _write_artifact(workspace, run, "../escape", b"data")
            with self.assertRaises(StorageError):
                _assert_run_path(workspace, workspace.parent / "outside")
            artifact = run / "snapshot.L5X"
            artifact.write_bytes(b"old")
            with self.assertRaises(FileExistsError):
                _write_artifact(workspace, run, artifact.name, b"new")
            self.assertEqual(artifact.read_bytes(), b"old")

    def test_symlink_run_and_artifact_escape_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            outside = workspace / "outside"
            outside.mkdir()
            run_link = workspace / "linked-run"
            try:
                run_link.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Symlink creation is unavailable on this machine.")
            with self.assertRaises(StorageError):
                _write_artifact(workspace, run_link, "snapshot.L5X", b"data")
            run = workspace / "real-run"
            run.mkdir()
            (run / "snapshot.L5X").symlink_to(outside / "private.L5X")
            with self.assertRaises(StorageError):
                _write_artifact(workspace, run, "snapshot.L5X", b"data")
            self.assertEqual(list(outside.iterdir()), [])

    def test_snapshot_mismatch_cannot_produce_a_run(self) -> None:
        snapshot, result = sample()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(StorageError):
                save_run(Path(directory), SourceSnapshot(snapshot.id, "wrong", snapshot.size_bytes, snapshot.data), result)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_noncanonical_snapshot_id_is_rejected_even_when_inventory_agrees(self) -> None:
        snapshot, result = sample()
        invalid = SourceSnapshot(
            f"l5x:{snapshot.sha256}", snapshot.sha256, snapshot.size_bytes, snapshot.data,
        )
        result.snapshot["id"] = invalid.id
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(StorageError):
                save_run(Path(directory), invalid, result)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
