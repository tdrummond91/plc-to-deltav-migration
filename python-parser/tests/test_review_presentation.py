"""Distribution HTML and explicit diagnostics, using only invented source."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import cli, work_check
from plc_workbench.review import build_review_data
from plc_workbench.review_html import ReviewHtmlError, render_review_html
from plc_workbench.storage import StorageError, save_run
from test_review import fixture
from test_review_html import ParsedPage


def page_data(page: str) -> dict:
    return json.loads(ParsedPage(page).scripts[0][1])


class ReviewPresentationTests(unittest.TestCase):
    def test_distribution_omits_implementation_metadata_but_keeps_source_and_identity(self) -> None:
        marker = 'Recorded field parser_version and analyzer_version are source comments.'
        args = fixture(comment=marker)
        canonical = build_review_data(*args)
        canonical['inventory']['export_attributes'].update(
            parser_version='authored-value', rule_id='authored-rule', rule_version='authored-revision')
        original = deepcopy(canonical)
        page = render_review_html(canonical)
        data = page_data(page)
        self.assertNotIn('report_version', data)
        for provider, key in (('inventory', 'parser_version'), ('references', 'analyzer_version'),
                              ('sfc', 'analyzer_version')):
            self.assertNotIn(key, data[provider])
            expected = {k: v for k, v in canonical[provider].items() if k != key}
            self.assertEqual(data[provider], expected)
        self.assertEqual(data['snapshot'], canonical['snapshot'])
        self.assertEqual(data['schema_version'], canonical['schema_version'])
        self.assertEqual(data['inventory']['export_attributes'], canonical['inventory']['export_attributes'])
        self.assertEqual(data['inventory']['rungs'][0]['comment'], marker)
        self.assertEqual(canonical, original)
        self.assertIn('const REVIEW_DEBUG = false;', ParsedPage(page).scripts[1][1])

    def test_current_review_preserves_every_provider_record_in_distribution(self) -> None:
        from plc_workbench.source_reuse import source_reuse_scope
        from test_engineering_assemblies_rack_workflow import SOURCE, captured, options
        with source_reuse_scope():
            parts = captured(SOURCE)
            canonical = build_review_data(*parts[:4], **options(parts))
        self.assertEqual(canonical['schema_version'], 35)
        original = deepcopy(canonical)
        normal = page_data(render_review_html(canonical))
        debug = page_data(render_review_html(canonical, debug=True))
        self.assertEqual(canonical, original)
        candidates = canonical['rung_analysis']['candidates']
        self.assertTrue(candidates)
        self.assertEqual(len(normal['rung_analysis']['candidates']), len(candidates))
        for source, presented in zip(candidates, normal['rung_analysis']['candidates']):
            self.assertNotIn('rule_id', presented)
            self.assertNotIn('rule_version', presented)
            for key in ('id', 'rung_id', 'category', 'basis', 'reason', 'evidence_ids',
                        'missing_evidence', 'review_status'):
                self.assertEqual(presented[key], source[key])
        self.assertEqual(debug, canonical)
        self.assertEqual(normal.keys(), canonical.keys() - {'report_version'})
        for name, value in normal.items():
            with self.subTest(section=name):
                if isinstance(value, dict):
                    expected = {key: item for key, item in canonical[name].items()
                                if key not in {'parser_version', 'analyzer_version', 'catalog_version'}}
                    if name == 'rung_analysis':
                        expected['candidates'] = [
                            {key: item for key, item in candidate.items()
                             if key not in {'rule_id', 'rule_version'}}
                            for candidate in canonical[name]['candidates']]
                    self.assertEqual(value, expected)
                else:
                    self.assertEqual(value, canonical[name])

    def test_debug_keeps_complete_canonical_payload_and_is_explicit(self) -> None:
        canonical = build_review_data(*fixture())
        page = render_review_html(canonical, debug=True)
        self.assertEqual(page_data(page), canonical)
        self.assertIn('const REVIEW_DEBUG = true;', ParsedPage(page).scripts[1][1])
        for value in (None, 1, 'true'):
            with self.subTest(value=value), self.assertRaises(ReviewHtmlError):
                render_review_html(canonical, debug=value)

    def test_distribution_validates_canonical_header_and_size_before_projection(self) -> None:
        canonical = build_review_data(*fixture())
        invalid = dict(canonical, report_version='unsupported')
        with self.assertRaises(ReviewHtmlError):
            render_review_html(invalid)
        canonical['inventory']['parser_version'] = 'metadata' * 1000
        size = len(json.dumps(canonical, ensure_ascii=False, separators=(',', ':')).encode())
        with patch('plc_workbench.review_html.MAX_REVIEW_PAYLOAD_BYTES', size - 1):
            with self.assertRaisesRegex(ReviewHtmlError, 'size limit'):
                render_review_html(canonical)
        with patch('plc_workbench.review_html.MAX_REVIEW_PAYLOAD_BYTES', size):
            self.assertNotIn('parser_version', page_data(render_review_html(canonical))['inventory'])

    def test_saved_modes_preserve_all_engineering_companions_and_manifest_contract(self) -> None:
        snapshot, inventory, references, sfc = fixture(comment='Same captured evidence')
        with tempfile.TemporaryDirectory() as directory:
            runs = [save_run(Path(directory), snapshot, inventory, references=references,
                             sfc_structure=sfc, include_review=True, review_debug=mode)
                    for mode in (False, True)]
            self.assertNotEqual(runs[0], runs[1])
            expected = build_review_data(snapshot, inventory, references, sfc)
            self.assertEqual(page_data((runs[1] / 'review.html').read_text(encoding='utf-8')), expected)
            self.assertNotIn('report_version', page_data((runs[0] / 'review.html').read_text(encoding='utf-8')))
            for path in runs[0].iterdir():
                if path.name not in {'review.html', 'manifest.json'}:
                    self.assertEqual(path.read_bytes(), (runs[1] / path.name).read_bytes())
            manifests = [json.loads((run / 'manifest.json').read_bytes()) for run in runs]
            self.assertEqual(manifests[0].keys(), manifests[1].keys())
            self.assertEqual(manifests[0]['schema_version'], manifests[1]['schema_version'])
            self.assertEqual(manifests[0]['artifacts'].keys(), manifests[1]['artifacts'].keys())
            for run, manifest in zip(runs, manifests):
                for name, details in manifest['artifacts'].items():
                    data = (run / name).read_bytes()
                    self.assertEqual(details, {'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data)})

    def test_storage_rejects_diagnostics_without_review_before_allocating(self) -> None:
        snapshot, inventory, _, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / 'not-created'
            for value in (True, 1, None):
                with self.subTest(value=value), self.assertRaises(StorageError):
                    save_run(workspace, snapshot, inventory, review_debug=value)
                self.assertFalse(workspace.exists())

    def test_review_cli_forwards_debug_only_when_requested(self) -> None:
        snapshot, _, _, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'invented.L5X'
            source.write_bytes(snapshot.data)
            (root / 'manifest.json').write_text('{"status":"partial"}', encoding='utf-8')
            for mode in (False, True):
                argv = ['review', str(source), '--workspace', str(root)] + (['--debug'] if mode else [])
                with self.subTest(mode=mode), patch('plc_workbench.storage.save_run', return_value=root) as save, redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.main(argv), 3)
                self.assertEqual(save.call_args.kwargs.get('review_debug', False), mode)
                self.assertEqual('review_debug' in save.call_args.kwargs, mode)
                self.assertTrue(save.call_args.kwargs['include_residual_diagnostics'])

    def test_work_check_cli_accepts_debug_without_changing_default_call_shape(self) -> None:
        root = Path('invented-checkout')
        for mode in (False, True):
            with self.subTest(mode=mode), patch.object(work_check, '_checkout_root', return_value=root), patch.object(work_check, 'run_check', return_value=0) as run:
                self.assertEqual(work_check.main(['example.L5X'] + (['--debug'] if mode else [])), 0)
                run.assert_called_once_with(root, 'example.L5X', **({'review_debug': True} if mode else {}))

    def test_work_check_dispatch_keeps_analysis_scope_in_both_display_modes(self) -> None:
        class AnalysisReached(Exception):
            pass

        root = Path('invented-checkout')
        suite = {'status': 'passed', 'counts': {'tests_run': 1}}
        for mode in (False, True):
            with self.subTest(mode=mode), \
                    patch.object(work_check, '_branch', return_value='main'), \
                    patch.object(work_check, '_git', return_value='a' * 40), \
                    patch.object(work_check, '_check_pinned'), \
                    patch.object(work_check, '_source_path', return_value=root / 'input.L5X'), \
                    patch.object(work_check, '_private_logs', return_value=root / 'logs'), \
                    patch.object(work_check, '_run_suite', return_value=suite), \
                    patch.object(work_check, '_analyze', side_effect=AnalysisReached) as analyze, \
                    redirect_stdout(io.StringIO()):
                with self.assertRaises(AnalysisReached):
                    work_check.run_check(root, None, review_debug=mode)
                self.assertEqual(analyze.call_args.kwargs.get('review_debug', False), mode)
                self.assertEqual('review_debug' in analyze.call_args.kwargs, mode)
                self.assertTrue(analyze.call_args.kwargs['include_residual_diagnostics'])
                self.assertTrue(analyze.call_args.kwargs['include_rack_backing_context'])

    def test_work_check_analysis_forwards_debug_and_preserves_summary_shape(self) -> None:
        snapshot, _, _, _ = fixture()
        results = []
        with tempfile.TemporaryDirectory() as directory:
            for mode in (False, True):
                root = Path(directory).resolve() / str(mode)
                root.mkdir()
                source = root / 'invented.L5X'
                source.write_bytes(snapshot.data)
                with self.subTest(mode=mode), patch.object(work_check, 'save_run', return_value=root) as save, redirect_stdout(io.StringIO()):
                    result = work_check._analyze(root, source, root, {'commit': 'a' * 40, 'worktree': 'clean'}, review_debug=mode)
                self.assertIn(result['status'], ('complete', 'partial'))
                self.assertTrue(result['private_run_saved'])
                self.assertEqual(save.call_args.kwargs.get('review_debug', False), mode)
                self.assertEqual('review_debug' in save.call_args.kwargs, mode)
                results.append(result)
        self.assertEqual(results[0], results[1])


if __name__ == '__main__':
    unittest.main()
