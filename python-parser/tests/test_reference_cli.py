"""Reference commands checked at private/public and saved-run boundaries."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.cli import main
from plc_workbench.reference_summary import validate_reference_summary
from plc_workbench.references import analyze_references
from plc_workbench.source import SourceError, analyze_snapshot, capture_snapshot, snapshot_from_bytes
from plc_workbench.storage import StorageError, _write_artifact, save_run
from plc_workbench.summary_output import SummaryOutputError, publish_summary


SOURCE = (
    '<RSLogix5000Content><Controller Name="PRIVATE_CONTROLLER">'
    '<Tags><Tag Name="PRIVATE_IN" TagType="Base" DataType="BOOL"/>'
    '<Tag Name="PRIVATE_OUT" TagType="Base" DataType="BOOL"/>'
    '<Tag Name="PRIVATE_ALIAS" TagType="Alias" AliasFor="PRIVATE_OUT"/></Tags>'
    '<Programs><Program Name="PRIVATE_PROGRAM"><Routines>'
    '<Routine Name="PRIVATE_ROUTINE" Type="RLL"><RLLContent>'
    '<Rung Number="0" Type="N"><Text>XIC(PRIVATE_IN)OTE(PRIVATE_ALIAS);</Text>'
    '</Rung></RLLContent></Routine></Routines></Program></Programs>'
    '</Controller></RSLogix5000Content>'
).encode()


def invoke(args: list[str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            code = main(args)
        except SystemExit as exc:
            code = int(exc.code)
    return code, stdout.getvalue(), stderr.getvalue()


class ReferenceCliTests(unittest.TestCase):
    def test_help_and_bad_usage_perform_no_source_io(self) -> None:
        with patch('plc_workbench.source.capture_snapshot', side_effect=AssertionError('no IO')):
            for command in ('references', 'reference-summary'):
                code, stdout, stderr = invoke([command, '--help'])
                self.assertEqual(code, 0)
                self.assertIn('usage:', stdout)
                self.assertEqual(stderr, '')
                self.assertEqual(invoke([command])[0], 2)

    def test_private_stdout_binds_alias_and_captures_once_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.L5X'
            source.write_bytes(SOURCE)
            with patch('plc_workbench.source.capture_snapshot', wraps=capture_snapshot) as capture:
                code, stdout, stderr = invoke(['references', str(source), '--format', 'json'])
            capture.assert_called_once_with(source)
            self.assertEqual((code, stderr), (0, ''))
            report = json.loads(stdout)
            target = next(s['id'] for s in report['symbols'] if s['name'] == 'PRIVATE_OUT')
            self.assertEqual(report['operands'][1]['target_id'], target)
            self.assertEqual(len(report['operands'][1]['alias_chain']), 1)
            self.assertEqual(list(Path(directory).iterdir()), [source])
            self.assertEqual(source.read_bytes(), SOURCE)
            code, text, _ = invoke(['references', str(source)])
            self.assertEqual(code, 0)
            self.assertIn('members, array bounds and access are not validated', text)
            self.assertIn('PRIVATE_ALIAS', text)

    def test_saved_private_run_hashes_and_reruns_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.L5X'
            source.write_bytes(SOURCE)
            workspace = Path(directory) / 'private runs'
            first_files = None
            for _ in range(2):
                code, stdout, stderr = invoke([
                    'references', str(source), '--format', 'json', '--workspace', str(workspace),
                ])
                self.assertEqual(code, 0)
                self.assertIn('Saved private reference run:', stderr)
                self.assertEqual(json.loads(stdout)['status'], 'complete')
                if first_files is None:
                    first, = workspace.iterdir()
                    first_files = {p.name: p.read_bytes() for p in first.iterdir()}
            runs = list(workspace.iterdir())
            self.assertEqual(len(runs), 2)
            self.assertEqual(first_files, {p.name: p.read_bytes() for p in first.iterdir()})
            manifest = json.loads(first_files['manifest.json'])
            self.assertEqual(manifest['schema_version'], 2)
            self.assertEqual(manifest['artifact_kind'], 'source_reference_run')
            self.assertEqual(set(manifest['artifacts']), {
                'snapshot.L5X', 'inventory.json', 'overview.txt', 'references.json', 'references.txt',
            })
            for name, details in manifest['artifacts'].items():
                saved = first_files[name]
                self.assertEqual(details['sha256'], hashlib.sha256(saved).hexdigest())
                self.assertEqual(details['size_bytes'], len(saved))
            self.assertEqual(source.read_bytes(), SOURCE)

    def test_mismatched_reference_snapshot_creates_no_run(self) -> None:
        snapshot = snapshot_from_bytes(SOURCE)
        inventory = analyze_snapshot(snapshot)
        references = replace(analyze_references(inventory), snapshot={'id': 'wrong'})
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / 'not-created'
            with self.assertRaises(StorageError):
                save_run(workspace, snapshot, inventory, references=references)
            self.assertFalse(workspace.exists())

    def test_failed_reference_artifact_never_publishes_final_manifest(self) -> None:
        snapshot = snapshot_from_bytes(SOURCE)
        inventory = analyze_snapshot(snapshot)
        references = analyze_references(inventory)

        def fail_reference(workspace, run_dir, name, data):
            if name == 'references.json':
                raise OSError('PRIVATE_FAILURE')
            return _write_artifact(workspace, run_dir, name, data)

        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            with patch('plc_workbench.storage._write_artifact', side_effect=fail_reference):
                with self.assertRaises(StorageError) as caught:
                    save_run(workspace, snapshot, inventory, references=references)
            self.assertNotIn('PRIVATE_FAILURE', str(caught.exception))
            run, = workspace.iterdir()
            self.assertFalse((run / 'manifest.json').exists())

    def test_dangling_reference_cannot_finalize_a_private_run(self) -> None:
        snapshot = snapshot_from_bytes(SOURCE)
        inventory = analyze_snapshot(snapshot)
        references = analyze_references(inventory)
        references.operands[0]['target_id'] = 'tag_PRIVATE_OTHER_SNAPSHOT'
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / 'not-created'
            with self.assertRaises(StorageError) as caught:
                save_run(workspace, snapshot, inventory, references=references)
            self.assertNotIn('PRIVATE', str(caught.exception))
            self.assertFalse(workspace.exists())

    def test_private_workspace_rejects_synced_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            source = checkout / 'PRIVATE_SOURCE.L5X'
            source.write_bytes(SOURCE)
            workspace = checkout / 'public' / 'inspection'
            with patch('plc_workbench.storage._checkout_root', return_value=checkout):
                code, stdout, stderr = invoke([
                    'references', str(source), '--workspace', str(workspace),
                ])
            self.assertEqual((code, stdout), (1, ''))
            self.assertIn('confidential/', stderr)
            self.assertFalse(workspace.exists())

    def test_public_aggregate_excludes_private_evidence_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'PRIVATE_SOURCE.L5X'
            source.write_bytes(SOURCE)
            output = Path(directory) / 'PRIVATE_OUTPUT.json'
            code, stdout, stderr = invoke(['reference-summary', str(source), '--output', str(output)])
            self.assertEqual((code, stdout), (0, ''))
            self.assertEqual(stderr, 'Saved aggregate reference summary; status: complete.\n')
            rendered = output.read_text(encoding='utf-8')
            validate_reference_summary(json.loads(rendered))
            self.assertNotIn('PRIVATE_', rendered)
            self.assertNotIn(hashlib.sha256(SOURCE).hexdigest(), rendered)
            self.assertEqual(invoke(['reference-summary', str(source), '--output', str(output)])[0], 1)
            self.assertEqual(output.read_text(encoding='utf-8'), rendered)
            self.assertEqual(source.read_bytes(), SOURCE)

    def test_source_complete_can_have_partial_reference_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.L5X'
            source.write_bytes(SOURCE.replace(b'XIC(PRIVATE_IN)', b'XIC(Unknown)'))
            output = Path(directory) / 'partial.json'
            code, stdout, stderr = invoke(['reference-summary', str(source), '--output', str(output)])
            self.assertEqual((code, stdout), (3, ''))
            self.assertIn('status: partial', stderr)
            report = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(report['source_summary']['status'], 'complete')
            self.assertEqual(report['status'], 'partial')
            self.assertEqual(report['operands']['by_status']['unresolved'], 1)

    def test_private_inventory_cannot_pass_public_dispatch(self) -> None:
        inventory = analyze_snapshot(snapshot_from_bytes(SOURCE))
        private = analyze_references(inventory).to_dict()
        private['report_kind'] = 'l5x_reference_review_summary'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'not-created' / 'private.json'
            with self.assertRaises(SummaryOutputError):
                publish_summary(output, json.dumps(private), input_path=Path(directory) / 'source.L5X')
            self.assertFalse(output.parent.exists())

    def test_summary_source_errors_never_reflect_private_exception_text(self) -> None:
        with patch('plc_workbench.source.capture_snapshot', side_effect=SourceError('PRIVATE_SECRET')):
            code, stdout, stderr = invoke(['reference-summary', 'PRIVATE_PATH'])
        self.assertEqual((code, stdout), (1, ''))
        self.assertNotIn('PRIVATE', stderr)


if __name__ == '__main__':
    unittest.main()
