"""Development-only file-operation navigation with invented source and Node.

Subprocess fixtures stay outside the work-machine test allowlist.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest

from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_file_operation_workflow import captured, options
from test_review import fixture
from test_review_html import ParsedPage

ROOT = Path(__file__).resolve().parents[2]
SELECT = r"""
function chooseFile(value){
  const s=document.getElementById('toolbar').querySelector('select');
  assert.ok(s);s.value=value;s.events.change();
}
"""


@unittest.skipUnless(_NODE, 'Node is optional development tooling for DOM checks.')
class FileOperationDomTests(unittest.TestCase):
    def run_ui(self, source: bytes, checks: str) -> None:
        parts = captured(source)
        data = build_review_data(*parts[:4], **options(parts))
        parsed = ParsedPage(render_review_html(data))
        result = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': data, 'script': parsed.scripts[1][1], 'checks': SELECT + checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_paging_symbolic_indices_roles_expression_and_source_navigation(self) -> None:
        source = (ROOT/'public/fixtures/synthetic/file_operations_demo.L5X').read_bytes()
        self.run_ui(source, r"""
        navigate('fileoperations');
        assert.equal(rows(tableNamed('File operation occurrences')).length,50);
        const next=content.querySelectorAll('button').find(b=>b.attributes['aria-label']==='Next page: File operation occurrences');
        assert.ok(next);next.click();
        assert.equal(rows(tableNamed('File operation occurrences')).length,15);
        chooseFile('FAL');
        assert.equal(rows(tableNamed('File operation occurrences')).length,3);
        rows(tableNamed('File operation occurrences'))[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('FAL'));
        const slots=rows(tableNamed('File operation slots'));
        assert.equal(slots.length,6);
        assert.ok(slots[4].textContent.includes('Destination[ArithmeticControl.POS]'));
        assert.ok(slots[4].textContent.includes('symbolic address'));
        assert.ok(slots[5].textContent.includes('expression read'));
        assert.ok(content.textContent.includes('ArithmeticControl.POS'));
        assert.ok(content.textContent.includes('Symbolic index selectors'));
        assert.ok(rows(tableNamed('File arithmetic expression nodes')).length>0);
        slots[4].querySelector('button').click();
        assert.ok(heading.textContent.includes('Rung 3'));
        assert.ok(content.textContent.includes('Selected operand'));
        assert.ok(tableNamed('Rung file operations'));
        navigate('fileoperations');chooseFile('SQO');
        assert.equal(rows(tableNamed('File operation occurrences')).length,2);
        rows(tableNamed('File operation occurrences'))[0].querySelector('button').click();
        assert.ok(rows(tableNamed('File operation slots'))[2].textContent.includes('read write'));
        assert.ok(content.textContent.includes('other destination bits are retained'));
        assert.ok(content.textContent.includes('Original'));
        assert.ok(content.textContent.includes('Control declaration and stored representations'));
        navigate('fileoperations');chooseFile('FAL');
        rows(tableNamed('File operation occurrences'))[2].querySelector('button').click();
        assert.ok(content.textContent.includes('unsupported function'));
        assert.ok(content.textContent.includes('No parsed expression nodes'));
        """)

    def test_control_gaps_are_searchable_and_namespace_rejections_do_not_link(self) -> None:
        source = fixture((
            'FAL(Timer,?,?,ALL,B,1);',
            'FAL(Controls[99],?,?,ALL,B,1);',
            'FAL(Control,?,?,ALL,B,1);',
            'COP(A,Foreign,2);',
        ), tags=(
            '<Tag Name="Timer" DataType="TIMER"/>'
            '<Tag Name="Controls" DataType="CONTROL" Dimensions="2"/>'
            '<Tag Name="Control" DataType="CONTROL"/>'
            '<Tag Name="Foreign" TagType="Alias" AliasFor="B"/>'))[0].data
        source = source.replace(b'<RSLogix5000Content>', b'<RSLogix5000Content xmlns:x="urn:foreign">')
        source = source.replace(b'AliasFor="B"', b'x:AliasFor="B"')
        self.run_ui(source, r"""
        navigate('fileoperations');chooseFile('gaps');
        const selected=rows(tableNamed('File operation occurrences'));
        assert.equal(selected.length,3);
        assert.ok(selected[0].textContent.includes('Rung 0'));
        assert.ok(selected[1].textContent.includes('Rung 1'));
        assert.ok(selected[2].textContent.includes('Rung 3'));
        selected[2].querySelector('button').click();
        const destination=rows(tableNamed('File operation slots'))[1];
        assert.ok(destination.childNodes[3].textContent.includes('namespace gap'));
        assert.equal(destination.childNodes[3].querySelectorAll('button').length,0);
        """)


if __name__ == '__main__':
    unittest.main()
