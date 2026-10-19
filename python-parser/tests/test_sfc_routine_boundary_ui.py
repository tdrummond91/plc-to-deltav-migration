"""Optional development-only DOM checks for SFC call-boundary evidence."""
import json
import subprocess
import unittest

from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from plc_workbench.source_reuse import source_reuse_scope
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_residual_diagnostics_workflow import SOURCE, captured, options
from test_review_html import ParsedPage


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI behavior checks.')
class SfcRoutineBoundaryUiTests(unittest.TestCase):
    def run_ui(self, declaration: bytes, checks: str):
        data = SOURCE.replace(b'JSR(Sub,0)JSR(Sub,Raw,Command);',
                              b'JSR(Sub,0)JSR(Sub,Raw,Command)JSR(Chart,0);')
        data = data.replace(b'<SFCContent>', b'<SFCContent>' + declaration)
        with source_reuse_scope():
            parts = captured(data)
            model = build_review_data(*parts[:4], **options(parts))
            script = ParsedPage(render_review_html(model)).scripts[1][1]
        result = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': model, 'script': script, 'checks': checks}), text=True,
            encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_qualified_absence_has_sfc_label_and_chart_source_navigation(self):
        self.run_ui(b'', r"""
        navigate('executioncontext');
        rows(tableNamed('Execution routine calls'))[2].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Boundary populationsfc absent'));
        assert.ok(content.textContent.includes('Exact SFC declared boundaries'));
        assert.ok(content.textContent.includes('No Subroutine/Return element is captured in this qualified SFC content.'));
        assert.ok(!content.textContent.includes('Exact RLL content boundaries'));
        assert.ok(content.textContent.includes('Subroutine/Return declarations0'));
        const source=content.querySelectorAll('button').find(b=>b.textContent.includes('Chart · SFC content'));
        assert.ok(source);source.click();
        assert.ok(heading.textContent.includes('Chart'));
        assert.ok(!content.textContent.includes('undefined'));
        """)

    def test_declared_attributes_remain_raw_and_link_to_exact_sfc_element(self):
        self.run_ui(b'<SbrRet ID="7" In="17, Raw[2]" Ret=""/>', r"""
        navigate('executioncontext');
        rows(tableNamed('Execution routine calls'))[2].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Boundary populationsfc declared'));
        const declarations=tableNamed('Exact SFC Subroutine/Return declarations');
        assert.equal(rows(declarations).length,1);
        assert.equal(texts(rows(declarations)[0])[1],'text');
        assert.equal(texts(rows(declarations)[0])[2],'empty');
        assert.ok(texts(rows(declarations)[0])[3].includes('17, Raw[2]'));
        assert.ok(content.textContent.includes('does not parse parameter lists, pair JSR fields'));
        rows(declarations)[0].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('17, Raw[2]'));
        assert.ok(!content.textContent.includes('undefined'));
        """)
