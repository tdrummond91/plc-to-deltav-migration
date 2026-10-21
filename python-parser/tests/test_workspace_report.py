"""Saved pre-navigation reports remain useful without source re-analysis."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from plc_workbench.project_store import ProjectError, ProjectStore
from plc_workbench.review_html import render_review_html
from plc_workbench.workspace_report import read_report_data, refresh_report
from test_review_html import ParsedPage, review_data
from test_review_links import _LINK_SETUP
from test_cpt_access_review_ui import DOM
from test_access_review_ui import _NODE


class WorkspaceReportTests(unittest.TestCase):
    def setUp(self):
        self.data = review_data()
        self.payload = ParsedPage(render_review_html(self.data)).scripts[0][1]
        self.legacy = (f'<html><script type="application/json" id="review-data">{self.payload}</script>'
                       '<script>window.IMPORTED_EXECUTABLE_MARKER=true;</script></html>').encode()

    def test_refresh_preserves_evidence_and_replaces_old_executable_presentation(self):
        original = bytes(self.legacy)
        refreshed = refresh_report(self.legacy, self.data['inventory'])
        parsed = ParsedPage(refreshed.decode())
        self.assertEqual(json.loads(parsed.scripts[0][1]), json.loads(self.payload))
        self.assertNotIn('IMPORTED_EXECUTABLE_MARKER', refreshed.decode())
        self.assertIn('WORKSPACE_REVIEW = true', parsed.scripts[1][1])
        self.assertIn('hashchange', parsed.scripts[1][1])
        self.assertEqual(original, self.legacy)

    def test_read_saved_payload_is_source_bound_and_ignores_executable_html(self):
        original = bytes(self.legacy)
        data = read_report_data(self.legacy, self.data['inventory'])
        self.assertEqual(data, json.loads(self.payload))
        self.assertEqual(data['sfc'], json.loads(self.payload)['sfc'])
        self.assertEqual(self.legacy, original)
        changed = deepcopy(self.data['inventory'])
        changed['rungs'][0]['comment'] = 'Different source wording'
        for html, inventory in ((self.legacy, changed), (self.legacy + self.legacy, self.data['inventory']),
                                (b'<script id="review-data">{}</script>', self.data['inventory'])):
            with self.assertRaises(ProjectError):
                read_report_data(html, inventory)

    def test_disagreeing_source_or_multiple_payloads_fail(self):
        changed = deepcopy(self.data['inventory'])
        changed['rungs'][0]['text'] = 'NOP();'
        with self.assertRaises(ProjectError):
            refresh_report(self.legacy, changed)
        with self.assertRaises(ProjectError):
            refresh_report(self.legacy + self.legacy, self.data['inventory'])
        with self.assertRaises(ProjectError):
            refresh_report(b'<html>No saved evidence</html>', self.data['inventory'])

    def test_debug_saved_source_also_becomes_a_normal_evidence_view(self):
        refreshed = refresh_report(render_review_html(self.data, debug=True).encode(), self.data['inventory'])
        parsed = ParsedPage(refreshed.decode())
        self.assertEqual(json.loads(parsed.scripts[0][1]), json.loads(self.payload))

    def test_malformed_optional_provider_returns_a_controlled_error(self):
        data = json.loads(self.payload)
        data['pid'] = []
        malformed = ('<script type="application/json" id="review-data">'
                     + json.dumps(data) + '</script>').encode()
        with self.assertRaises(ProjectError):
            refresh_report(malformed, self.data['inventory'])
        with self.assertRaises(ProjectError):
            read_report_data(malformed, self.data['inventory'])

    def test_current_complete_saved_analysis_imports_without_reanalysis(self):
        from plc_workbench.source_reuse import source_reuse_scope
        from plc_workbench.storage import save_run
        from test_engineering_assemblies_rack_workflow import SOURCE, captured, arguments

        with source_reuse_scope(), tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            parts = captured(SOURCE)
            run = save_run(root / 'runs', *parts[:2], **arguments(parts))
            manifest = json.loads((run / 'manifest.json').read_bytes())
            self.assertEqual(manifest['schema_version'], 38)
            with ProjectStore(root / 'project.sqlite') as project:
                project.import_run(run)
                original = project.artifact('review.html')
                rendered = refresh_report(original, project.inventory())
                payload = json.loads(ParsedPage(rendered.decode()).scripts[0][1])
                self.assertEqual(payload['schema_version'], 35)
                self.assertEqual(payload['engineering_assemblies']['schema_version'], 3)
                self.assertEqual(payload['inventory']['rungs'], project.inventory()['rungs'])
                self.assertEqual(payload['inventory']['entities'], project.inventory()['entities'])
                self.assertEqual(project.artifact('review.html'), original)

    @unittest.skipUnless(_NODE, 'Node is optional development UI tooling.')
    def test_legacy_report_now_opens_requested_rung_and_workspace_link(self):
        parsed = ParsedPage(refresh_report(self.legacy, self.data['inventory']).decode())
        rung_id = self.data['inventory']['rungs'][0]['id']
        dom = DOM.replace("vm.runInThisContext(input.script,{filename:'report.js'});",
                          _LINK_SETUP + "\nvm.runInThisContext(input.script,{filename:'report.js'});")
        result = subprocess.run([_NODE, '-e', dom], input=json.dumps({
            'data': json.loads(parsed.scripts[0][1]), 'script': parsed.scripts[1][1],
            'fragment': f'#view=ladder&source={rung_id}',
            'checks': "assert.ok(heading.textContent.includes('Rung 0'));"
                      "assert.ok(heading.textContent.includes('Return to editable workspace'));"
                      "assert.ok(!heading.textContent.includes('Prepare review feedback'));"
                      "assert.ok(content.textContent.includes('XIC(A)OTE(Missing);'));",
        }), text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
