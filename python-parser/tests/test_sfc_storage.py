"""SFC private artifacts share canonical snapshot validation and append-only runs."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.references import analyze_references
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.storage import StorageError, _write_artifact, save_run


SOURCE = (
    '<RSLogix5000Content><Controller Name="PRIVATE_CONTROLLER"><Programs>'
    '<Program Name="PRIVATE_PROGRAM"><Routines>'
    '<Routine Name="PRIVATE_SEQUENCE" Type="SFC"><SFCContent/></Routine>'
    '</Routines></Program></Programs></Controller></RSLogix5000Content>'
).encode()


def sample():
    snapshot = snapshot_from_bytes(SOURCE)
    inventory = analyze_snapshot(snapshot)
    return snapshot, inventory, analyze_sfc_structure(snapshot, inventory)


class SfcStorageTests(unittest.TestCase):
    def test_optional_artifacts_legacy_layout_and_new_manifest_hashes(self) -> None:
        snapshot, inventory, sfc = sample()
        refs = analyze_references(inventory)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.L5X'
            source.write_bytes(SOURCE)
            workspace = Path(directory) / 'workspace'
            for include_refs in (False, True):
                for include_sfc in (False, True):
                    run = save_run(workspace, snapshot, inventory,
                                   references=refs if include_refs else None,
                                   sfc_structure=sfc if include_sfc else None)
                    manifest = json.loads((run / 'manifest.json').read_text())
                    expected = {'snapshot.L5X', 'inventory.json', 'overview.txt'}
                    if include_refs:
                        expected.update({'references.json', 'references.txt'})
                    if include_sfc:
                        expected.update({'sfc-structure.json', 'sfc-structure.txt'})
                    self.assertEqual(set(manifest['artifacts']), expected)
                    self.assertEqual({p.name for p in run.iterdir()}, expected | {'manifest.json'})
                    self.assertEqual(manifest['schema_version'], 3 if include_sfc else (2 if include_refs else 1))
                    if include_sfc:
                        self.assertEqual(manifest['artifact_kind'],
                                         'source_reference_sfc_structure_run' if include_refs else 'source_sfc_structure_run')
                        self.assertEqual(manifest['sfc_schema_version'], 1)
                        self.assertEqual(manifest['sfc_analyzer_version'], 'sfc-structure-1')
                        self.assertEqual(manifest['sfc_analysis_scope'], 'sfc_structure_only')
                        self.assertEqual(manifest['status'], 'partial')
                        self.assertEqual(json.loads((run / 'sfc-structure.json').read_text()), sfc.to_dict())
                    else:
                        self.assertFalse(any(key.startswith('sfc_') for key in manifest))
                    if include_refs:
                        self.assertEqual(manifest['analysis_scope'], refs.to_dict()['analysis_scope'])
                    for name, details in manifest['artifacts'].items():
                        data = (run / name).read_bytes()
                        self.assertEqual(details, {'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data)})
            self.assertEqual(source.read_bytes(), SOURCE)

    def test_canonical_tamper_and_snapshot_mismatch_fail_before_directory_creation(self) -> None:
        snapshot, inventory, sfc = sample()
        variants = [replace(sfc, snapshot={'id': 'PRIVATE_WRONG'}),
                    replace(sfc, status='partial'), replace(sfc, routines=[])]
        with tempfile.TemporaryDirectory() as directory:
            for index, bad in enumerate(variants):
                workspace = Path(directory) / f'not-created-{index}'
                with self.assertRaises(StorageError) as caught:
                    save_run(workspace, snapshot, inventory, sfc_structure=bad)
                self.assertNotIn('PRIVATE', str(caught.exception))
                self.assertFalse(workspace.exists())
            bad_snapshot = replace(snapshot, data=snapshot.data + b' ')
            workspace = Path(directory) / 'bad-bytes'
            with self.assertRaises(StorageError):
                save_run(workspace, bad_snapshot, inventory, sfc_structure=sfc)
            self.assertFalse(workspace.exists())

    def test_failed_sfc_artifact_never_publishes_manifest(self) -> None:
        snapshot, inventory, sfc = sample()

        def fail(workspace, run_dir, name, data):
            if name == 'sfc-structure.txt':
                raise OSError('PRIVATE_FAILURE')
            return _write_artifact(workspace, run_dir, name, data)

        with tempfile.TemporaryDirectory() as directory:
            with patch('plc_workbench.storage._write_artifact', side_effect=fail):
                with self.assertRaises(StorageError) as caught:
                    save_run(Path(directory), snapshot, inventory, sfc_structure=sfc)
            self.assertNotIn('PRIVATE', str(caught.exception))
            run, = Path(directory).iterdir()
            self.assertFalse((run / 'manifest.json').exists())

    def test_combined_rerun_retains_prior_source_and_all_artifacts(self) -> None:
        snapshot, inventory, sfc = sample()
        refs = analyze_references(inventory)
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            first = save_run(workspace, snapshot, inventory, references=refs, sfc_structure=sfc)
            before = {p.name: p.read_bytes() for p in first.iterdir()}
            second = save_run(workspace, snapshot, inventory, references=refs, sfc_structure=sfc)
            self.assertNotEqual(first, second)
            self.assertEqual(before, {p.name: p.read_bytes() for p in first.iterdir()})

    def test_complete_empty_sfc_scope_and_inventory_finalize_complete_combined_run(self) -> None:
        snapshot = snapshot_from_bytes(b'<RSLogix5000Content><Controller Name="Invented"/></RSLogix5000Content>')
        inventory = analyze_snapshot(snapshot)
        sfc = analyze_sfc_structure(snapshot, inventory)
        refs = analyze_references(inventory)
        with tempfile.TemporaryDirectory() as directory:
            run = save_run(Path(directory), snapshot, inventory, references=refs, sfc_structure=sfc)
            manifest = json.loads((run / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'complete')
            self.assertEqual(sfc.to_dict()['routines'], [])


if __name__ == '__main__':
    unittest.main()
