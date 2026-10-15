"""SFC commands at their private output and approved aggregate boundaries."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.cli import main
from plc_workbench.source import SourceError, capture_snapshot


SOURCE = (
    '<RSLogix5000Content><Controller Name="PRIVATE_CONTROLLER"><Programs>'
    '<Program Name="PRIVATE_PROGRAM"><Routines>'
    '<Routine Name="PRIVATE_SEQUENCE" Type="SFC"><SFCContent/></Routine>'
    '</Routines></Program></Programs></Controller></RSLogix5000Content>'
).encode()


def invoke(args: list[str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    # These commands are part of the process-free work-machine test allowlist.
    # Provenance is synthetic here; actual Git collection has separate tests.
    with (redirect_stdout(stdout), redirect_stderr(stderr),
          patch('plc_workbench.revision.collect_revision',
                return_value={'commit': None, 'worktree': 'unavailable'})):
        try:
            code = main(args)
        except SystemExit as exc:
            code = int(exc.code)
    return code, stdout.getvalue(), stderr.getvalue()


class SfcCliTests(unittest.TestCase):
    def test_help_and_usage_require_no_source_io(self) -> None:
        with patch('plc_workbench.source.capture_snapshot', side_effect=AssertionError('no I/O')):
            for command in ('sfc-structure', 'sfc-summary'):
                code, stdout, stderr = invoke([command, '--help'])
                self.assertEqual((code, stderr), (0, ''))
                self.assertIn('usage:', stdout)
                self.assertEqual(invoke([command])[0], 2)

    def test_private_scope_complete_capture_once_and_save_optional(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.L5X'
            source.write_bytes(SOURCE)
            with patch('plc_workbench.source.capture_snapshot', wraps=capture_snapshot) as capture:
                code, stdout, stderr = invoke(['sfc-structure', str(source), '--format', 'json'])
            capture.assert_called_once_with(source)
            self.assertEqual((code, stderr), (0, ''))
            report = json.loads(stdout)
            self.assertEqual((report['schema_version'], report['analysis_scope'], report['status']),
                             (2, 'sfc_structure_only', 'complete'))
            self.assertEqual(list(Path(directory).iterdir()), [source])
            code, text, stderr = invoke(['sfc-structure', str(source)])
            self.assertEqual((code, stderr), (0, ''))
            self.assertTrue(text.strip())
            self.assertNotEqual(text.lstrip()[0], '{')
            workspace = Path(directory) / 'private runs'
            code, _, stderr = invoke(['sfc-structure', str(source), '--workspace', str(workspace)])
            self.assertEqual(code, 0)
            self.assertIn('Saved private SFC structure run:', stderr)
            run, = workspace.iterdir()
            manifest = json.loads((run / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'partial')  # Inventory still cannot interpret SFC.
            self.assertEqual(source.read_bytes(), SOURCE)

    def test_partial_scope_and_safe_source_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.L5X'
            source.write_bytes(SOURCE.replace(b'<SFCContent/>', b''))
            code, stdout, stderr = invoke(['sfc-structure', str(source), '--format', 'json'])
            self.assertEqual((code, stderr), (3, ''))
            self.assertEqual(json.loads(stdout)['status'], 'partial')
        for command in ('sfc-structure', 'sfc-summary'):
            with patch('plc_workbench.source.capture_snapshot', side_effect=SourceError('PRIVATE_SECRET')):
                code, stdout, stderr = invoke([command, 'PRIVATE_PATH'])
            self.assertEqual((code, stdout), (1, ''))
            self.assertNotIn('PRIVATE', stderr)

    def test_private_populated_chart_uses_captured_bytes_after_input_changes(self) -> None:
        chart = (b'<SFCContent><Step ID="1" Name="PRIVATE_STEP"/>'
                 b'<Transition ID="2"><Condition><STContent>'
                 b'<Line Number="0">PRIVATE_CONDITION</Line></STContent></Condition></Transition>'
                 b'<DirectedLink FromID="1" ToID="2"/></SFCContent>')
        populated = SOURCE.replace(b'<SFCContent/>', chart)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.L5X'
            source.write_bytes(populated)

            def capture_then_change(path):
                captured = capture_snapshot(path)
                path.write_bytes(b'changed source is no longer XML')
                return captured

            workspace = Path(directory) / 'private'
            with patch('plc_workbench.source.capture_snapshot', side_effect=capture_then_change) as capture:
                code, stdout, _ = invoke(['sfc-structure', str(source), '--format', 'json',
                                         '--workspace', str(workspace)])
            capture.assert_called_once_with(source)
            self.assertEqual(code, 0)
            self.assertIn('PRIVATE_CONDITION', stdout)
            report = json.loads(stdout)
            self.assertEqual(len(report['links']), 1)
            run, = workspace.iterdir()
            self.assertEqual((run / 'snapshot.L5X').read_bytes(), populated)
            self.assertIn('PRIVATE_SEQUENCE', (run / 'sfc-structure.txt').read_text())
            self.assertEqual(json.loads((run / 'sfc-structure.json').read_text()), report)

    def test_aggregate_stdout_publication_and_no_clobber(self) -> None:
        from plc_workbench.sfc_summary import validate_sfc_summary

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'PRIVATE_INPUT.L5X'
            source.write_bytes(SOURCE)
            code, stdout, stderr = invoke(['sfc-summary', str(source)])
            self.assertEqual((code, stderr), (0, ''))
            validate_sfc_summary(json.loads(stdout))
            self.assertNotIn('PRIVATE', stdout)
            self.assertNotIn(hashlib.sha256(SOURCE).hexdigest(), stdout)
            output = Path(directory) / 'report.json'
            code, stdout, stderr = invoke(['sfc-summary', str(source), '--output', str(output)])
            self.assertEqual((code, stdout), (0, ''))
            self.assertEqual(stderr, 'Saved aggregate SFC structure summary; status: complete.\n')
            before = output.read_bytes()
            validate_sfc_summary(json.loads(before))
            self.assertEqual(invoke(['sfc-summary', str(source), '--output', str(output)])[0], 1)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(source.read_bytes(), SOURCE)

    def test_private_workspace_and_public_summary_path_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            source = checkout / 'input.L5X'
            source.write_bytes(SOURCE)
            workspace = checkout / 'public' / 'inspection' / 'private-run'
            with patch('plc_workbench.storage._checkout_root', return_value=checkout):
                code, stdout, stderr = invoke(['sfc-structure', str(source), '--workspace', str(workspace)])
            self.assertEqual((code, stdout), (1, ''))
            self.assertIn('confidential/', stderr)
            self.assertFalse(workspace.exists())
            forbidden = checkout / 'tools' / 'summary.json'
            with patch('plc_workbench.summary_output._checkout_root', return_value=checkout):
                self.assertEqual(invoke(['sfc-summary', str(source), '--output', str(forbidden)])[0], 1)
            self.assertFalse(forbidden.parent.exists())


if __name__ == '__main__':
    unittest.main()
