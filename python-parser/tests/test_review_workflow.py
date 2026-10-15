"""Private review publication and CLI boundaries use invented data only."""
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
from plc_workbench.references import analyze_references
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.source import SourceError, capture_snapshot
from plc_workbench.storage import StorageError, save_run
from test_sfc_structure import fixture


def sample():
    snapshot, inventory = fixture('''<SFCContent><Step ID="1" Operand="PRIVATE_STEP"/>
      <TextBox ID="2"><Text>PRIVATE_NOTE</Text></TextBox>
      <Attachment FromID="2" ToID="1"/></SFCContent>''', extra='''
      <Routine Name="PRIVATE_MAIN" Type="RLL"><RLLContent><Rung Number="0">
      <Text>XIC(PRIVATE_MISSING)OTE(PRIVATE_OUT);</Text></Rung></RLLContent></Routine>''')
    return snapshot, inventory, analyze_references(inventory), analyze_sfc_structure(snapshot, inventory)


def invoke(args: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = main(args)
        except SystemExit as exc:
            code = int(exc.code)
    return code, out.getvalue(), err.getvalue()


class ReviewWorkflowTests(unittest.TestCase):
    def test_review_requires_all_evidence_before_allocating_workspace(self) -> None:
        snapshot, inventory, references, sfc = sample()
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'not-created'
            for kwargs in ({}, {'references': references}, {'sfc_structure': sfc}):
                with self.subTest(kwargs=list(kwargs)), self.assertRaises(StorageError):
                    save_run(destination, snapshot, inventory, include_review=True, **kwargs)
                self.assertFalse(destination.exists())
            with self.assertRaises(StorageError):
                save_run(destination, snapshot, inventory, references=references,
                         sfc_structure=sfc, include_review=1)

    def test_review_manifest_hashes_and_prior_runs_are_preserved(self) -> None:
        snapshot, inventory, references, sfc = sample()
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            prior = save_run(workspace, snapshot, inventory, references=references, sfc_structure=sfc)
            prior_bytes = {p.name: p.read_bytes() for p in prior.iterdir()}
            saved = save_run(workspace, snapshot, inventory, references=references,
                             sfc_structure=sfc, include_review=True)
            manifest = json.loads((saved / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], manifest['artifact_kind']),
                             (4, 'source_reference_sfc_review_run'))
            self.assertEqual((manifest['review_schema_version'], manifest['review_version']),
                             (1, 'engineering-review-1'))
            self.assertEqual(len(manifest['artifacts']), 8)
            html = (saved / 'review.html').read_text(encoding='utf-8')
            self.assertIn('PRIVATE_NOTE', html)
            self.assertIn('PRIVATE_MISSING', html)
            for name, details in manifest['artifacts'].items():
                data = (saved / name).read_bytes()
                self.assertEqual(details, {'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data)})
            self.assertEqual({p.name: p.read_bytes() for p in prior.iterdir()}, prior_bytes)
            self.assertEqual(json.loads(prior_bytes['manifest.json'])['schema_version'], 3)
            self.assertEqual((saved / 'snapshot.L5X').read_bytes(), snapshot.data)

    def test_review_generation_failure_is_source_free_and_allocates_no_run(self) -> None:
        from plc_workbench.review_html import ReviewHtmlError
        snapshot, inventory, references, sfc = sample()
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'not-created'
            with patch('plc_workbench.review_html.render_review_html',
                       side_effect=ReviewHtmlError('PRIVATE_TEXT')):
                with self.assertRaises(StorageError) as raised:
                    save_run(destination, snapshot, inventory, references=references,
                             sfc_structure=sfc, include_review=True)
            self.assertNotIn('PRIVATE_TEXT', str(raised.exception))
            self.assertFalse(destination.exists())

    def test_review_write_failure_cannot_publish_final_manifest(self) -> None:
        import plc_workbench.storage as storage
        snapshot, inventory, references, sfc = sample()
        original = storage._write_artifact

        def fail_review(workspace, run_dir, name, data):
            if name == 'review.html':
                raise OSError('PRIVATE_DISK_DETAIL')
            return original(workspace, run_dir, name, data)

        with tempfile.TemporaryDirectory() as folder:
            with patch.object(storage, '_write_artifact', side_effect=fail_review):
                with self.assertRaises(StorageError) as raised:
                    save_run(Path(folder), snapshot, inventory, references=references,
                             sfc_structure=sfc, include_review=True)
            self.assertNotIn('PRIVATE_DISK_DETAIL', str(raised.exception))
            saved, = Path(folder).iterdir()
            self.assertFalse((saved / 'manifest.json').exists())
            self.assertEqual((saved / 'snapshot.L5X').read_bytes(), snapshot.data)

    def test_cli_help_usage_and_safe_source_failure(self) -> None:
        with patch('plc_workbench.source.capture_snapshot', side_effect=AssertionError('no I/O')):
            self.assertEqual(invoke(['review', '--help'])[0], 0)
            self.assertEqual(invoke(['review', 'input.L5X'])[0], 2)
        with patch('plc_workbench.source.capture_snapshot', side_effect=SourceError('PRIVATE_INPUT')):
            code, out, err = invoke(['review', 'PRIVATE_INPUT.L5X', '--workspace', 'destination'])
        self.assertEqual((code, out), (1, ''))
        self.assertNotIn('PRIVATE_INPUT', err)

    def test_cli_capture_once_uses_frozen_bytes_and_prints_report_location(self) -> None:
        snapshot, _, _, _ = sample()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'invented.L5X'
            source.write_bytes(snapshot.data)

            def changed_after_capture(path):
                captured = capture_snapshot(path)
                source.write_bytes(b'changed live input')
                return captured

            with patch('plc_workbench.source.capture_snapshot', side_effect=changed_after_capture) as capture:
                code, out, err = invoke(['review', str(source), '--workspace', str(root / 'runs')])
            capture.assert_called_once_with(source)
            self.assertEqual((code, err), (3, ''))
            saved, = (root / 'runs').iterdir()
            self.assertIn(str(saved / 'review.html'), out)
            self.assertNotIn('PRIVATE_NOTE', out)
            self.assertEqual((saved / 'snapshot.L5X').read_bytes(), snapshot.data)
            self.assertIn('PRIVATE_NOTE', (saved / 'review.html').read_text(encoding='utf-8'))
            access = json.loads((saved / 'access.json').read_bytes())
            self.assertEqual(access['snapshot']['id'], snapshot.id)
            self.assertEqual(access['snapshot']['sha256'], snapshot.sha256)
            self.assertEqual(json.loads((saved / 'manifest.json').read_bytes())['schema_version'], 12)


if __name__ == '__main__':
    unittest.main()
