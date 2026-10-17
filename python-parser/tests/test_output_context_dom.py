"""Development-only output context DOM checks using invented source and Node.

This subprocess module is intentionally outside the work-machine test allowlist.
"""
from __future__ import annotations

import json
import subprocess
import unittest

from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_output_context_workflow import captured, options
from test_review import fixture
from test_review_html import ParsedPage


@unittest.skipUnless(_NODE, 'Node is optional development tooling for DOM checks.')
class OutputContextDomTests(unittest.TestCase):
    def run_ui(self, source: bytes, checks: str) -> None:
        parts = captured(source)
        data = build_review_data(*parts[:4], **options(parts))
        parsed = ParsedPage(render_review_html(data))
        process = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': data, 'script': parsed.scripts[1][1], 'checks': checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_qualified_targets_and_actual_condition_edges_keep_repeated_reads_and_self_feedback(self) -> None:
        source = fixture((
            'OTE(A);', '[XIC(A)OTE(B),XIC(C)OTE(D)]OTE(C);',
            'XIC(A)XIC(A)OTE(A);', 'ONS(A)OTE(B);', 'CPT(B,A+A);',
            'XIC(A)MOV(1,A);', 'XIC(A)XIC(Alias)OTE(B);', 'OTE(Alias);',
        ), tags='<Tag Name="C" DataType="BOOL"/><Tag Name="D" DataType="BOOL"/>'
                '<Tag Name="Alias" TagType="Alias" AliasFor="A"/>',
           comment='Alarm <script>window.outputInjected=true</script>')[0].data
        source = source.replace(b'<RSLogix5000Content>', b'<RSLogix5000Content xmlns:x="urn:foreign">')
        source = source.replace(b'AliasFor="A"', b'x:AliasFor="A"')
        self.run_ui(source, r"""
        navigate('conditions');
        assert.ok(heading.textContent.includes('Boolean output context'));
        const occurrences=rows(tableNamed('Boolean output occurrences'));
        const unresolved=occurrences.find(r=>r.textContent.includes('OTE')&&r.textContent.includes('Alias'));
        assert.ok(unresolved);
        assert.ok(!unresolved.childNodes[1].querySelectorAll('button').some(b=>b.textContent.startsWith('Address:')));
        assert.ok(unresolved.childNodes[1].textContent.includes('No accepted target address'));
        occurrences[0].childNodes[1].querySelector('button').click();
        assert.ok(heading.textContent.includes('BOOLEAN OUTPUT ADDRESS CONTEXT'));
        assert.equal(rows(tableNamed('Qualified condition reads of output target')).length,6);
        const consumers=rows(tableNamed('Outputs with matching condition ancestry'));
        assert.equal(consumers.length,4);
        assert.deepEqual(consumers.map(r=>r.childNodes[0].textContent),['OTE · B','OTE · C','OTE · A','OTE · B']);
        assert.ok(consumers[3].textContent.includes('stored-state'));
        assert.equal(rows(tableNamed('Accepted expression readers')).length,2);
        assert.equal(rows(tableNamed('Unqualified condition-read occurrences')).length,1);
        consumers[2].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Incoming condition evidence'));
        assert.ok(content.textContent.includes('Authored wording on this rung'));
        assert.ok(!globalThis.outputInjected);
        tableNamed('Authored wording on this rung').querySelector('button').click();
        assert.ok(heading.textContent.includes('Rung 2'));
        assert.ok(content.textContent.includes('Alarm <script>window.outputInjected=true</script>'));
        assert.ok(!globalThis.outputInjected);
        navigate('conditions');
        const gap=rows(tableNamed('Boolean output occurrences')).find(r=>r.childNodes[0].textContent==='OTE · Alias');
        gap.childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Target uses remain unresolved'));
        assert.ok(!content.querySelectorAll('button').some(b=>b.textContent==='Address: A'));
        clickText(content,'Alias · argument 1');
        assert.ok(heading.textContent.includes('Rung 7'));
        assert.ok(content.textContent.includes('Selected operand'));
        assert.ok(content.textContent.includes('OTE(Alias);'));
        """)

    def test_shared_ancestor_reaches_both_branches_and_opaque_context_keeps_source_links(self) -> None:
        source = fixture(('OTE(A);', 'XIC(A)[OTE(B),OTE(C)];',
                          'XIC(A)XIC(A)ONS(A)MYSTERY(A)PID(A,B,C,D,0,0,0)OTE(D);'), tags=(
            '<Tag Name="C" DataType="BOOL"/><Tag Name="D" DataType="BOOL"/>'))[0].data
        self.run_ui(source, r"""
        navigate('conditions');
        rows(tableNamed('Boolean output occurrences'))[0].childNodes[1].querySelector('button').click();
        const reads=rows(tableNamed('Qualified condition reads of output target'));
        assert.deepEqual(reads.map(r=>r.childNodes[1].textContent),[
          'Predicate operand read','Predicate operand read','Predicate operand read','ONS stored-state read']);
        const consumers=rows(tableNamed('Outputs with matching condition ancestry'));
        assert.deepEqual(consumers.map(r=>r.childNodes[0].textContent),['OTE · B','OTE · C','OTE · D']);
        assert.ok(consumers[2].textContent.includes('Contains unknown transfer'));
        assert.ok(consumers[2].textContent.includes('Includes stored-state context'));
        assert.equal(rows(tableNamed('Uses with unknown operand roles')).length,1);
        assert.equal(rows(tableNamed('Other captured writer operands')).length,1);
        reads[3].childNodes[2].querySelector('button').click();
        assert.ok(heading.textContent.includes('Rung 2'));
        assert.ok(content.textContent.includes('Selected instruction'));
        """)

    def test_authored_hints_belong_to_whole_rung_and_do_not_leak_to_same_target(self) -> None:
        source = fixture(('[OTE(A),OTE(B)];', 'OTE(A);'))[0].data
        source = source.replace(b'<Comment><![CDATA[]]></Comment>',
                                b'<Comment><![CDATA[alarm pump sensor]]></Comment>', 1)
        self.run_ui(source, r"""
        navigate('conditions');
        const outputs=rows(tableNamed('Boolean output occurrences'));
        assert.equal(outputs[0].childNodes[4].textContent,'alarm · equipment · sensor');
        assert.equal(outputs[1].childNodes[4].textContent,outputs[0].childNodes[4].textContent);
        assert.equal(outputs[2].childNodes[4].textContent,'None captured');
        outputs[1].childNodes[0].querySelector('button').click();
        assert.equal(rows(tableNamed('Authored wording on this rung')).length,3);
        assert.ok(content.textContent.includes('belong to the entire rung'));
        navigate('conditions');
        rows(tableNamed('Boolean output occurrences'))[2].childNodes[0].querySelector('button').click();
        assert.ok(!content.textContent.includes('Authored wording on this rung'));
        """)

    def test_consumer_and_occurrence_pages_are_bounded(self) -> None:
        source = fixture(('OTE(A);',) + ('XIC(A)OTE(B);',) * 52)[0].data
        self.run_ui(source, r"""
        navigate('conditions');
        assert.equal(rows(tableNamed('Boolean output occurrences')).length,50);
        content.querySelectorAll('button').find(b=>b.attributes['aria-label']==='Next page: Boolean output occurrences').click();
        assert.equal(rows(tableNamed('Boolean output occurrences')).length,3);
        navigate('conditions');
        rows(tableNamed('Boolean output occurrences'))[0].childNodes[1].querySelector('button').click();
        assert.equal(rows(tableNamed('Outputs with matching condition ancestry')).length,50);
        content.querySelectorAll('button').find(b=>b.attributes['aria-label']==='Next page: Outputs with matching condition ancestry').click();
        assert.equal(rows(tableNamed('Outputs with matching condition ancestry')).length,2);
        assert.equal(rows(tableNamed('Qualified condition reads of output target')).length,50);
        content.querySelectorAll('button').find(b=>b.attributes['aria-label']==='Next page: Qualified condition reads of output target').click();
        const last=rows(tableNamed('Qualified condition reads of output target'));
        assert.equal(last.length,2);
        last[1].childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('Rung 52'));
        assert.ok(content.textContent.includes('Selected operand'));
        """)

    def test_target_pages_preserve_last_address_navigation(self) -> None:
        source = fixture(tuple(f'OTE(T{i});' for i in range(53)), tags=''.join(
            f'<Tag Name="T{i}" DataType="BOOL"/>' for i in range(53)))[0].data
        self.run_ui(source, r"""
        navigate('conditions');
        const view=document.getElementById('toolbar').querySelectorAll('select').find(s=>s.attributes['aria-label']==='Output view');
        view.value='targets';view.events.change();
        assert.equal(rows(tableNamed('Boolean output target addresses')).length,50);
        content.querySelectorAll('button').find(b=>b.attributes['aria-label']==='Next page: Boolean output target addresses').click();
        const last=rows(tableNamed('Boolean output target addresses'));
        assert.equal(last.length,3);
        assert.equal(last[2].childNodes[0].textContent,'T52');
        last[2].childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('BOOLEAN OUTPUT ADDRESS CONTEXT'));
        assert.ok(heading.textContent.includes('T52'));
        assert.equal(rows(tableNamed('Coils sharing a qualified target'))[0].childNodes[0].textContent,'OTE · T52');
        """)


if __name__ == '__main__':
    unittest.main()
