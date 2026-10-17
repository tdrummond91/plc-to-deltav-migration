"""Development-only source navigation for invented transition expressions.

Node is optional. This module does not belong in the work-machine allowlist.
"""
from __future__ import annotations

import json
import subprocess
import unittest

from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from plc_workbench.sfc_conditions import analyze_sfc_conditions
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_review import fixture
from test_review_html import ParsedPage
from test_stateful_object_workflow import captured, options


def transition(name: str, expression: str, number: int = 1) -> str:
    return (f'<Transition ID="{number}" Operand="{name}"><Condition><STContent>'
            f'<Line Number="0"><![CDATA[{expression}]]></Line>'
            '</STContent></Condition></Transition>')


def source(contents: str, *, tags: str = '') -> bytes:
    return fixture(sfc=contents, tags=tags)[0].data


CHECKS = r"""
function openSequence(name){
  navigate('sequenceconditions');
  const row=rows(tableNamed('Sequence transition conditions')).find(r=>r.childNodes[0].querySelector('button')?.textContent===name);
  assert.ok(row,'Missing transition: '+name);row.childNodes[0].querySelector('button').click();
}
function filterSequence(value){
  const s=document.getElementById('toolbar').querySelector('select');
  assert.ok(s);s.value=value;s.events.change();
}
function nextSequence(caption){
  const b=content.querySelectorAll('button').find(n=>n.attributes['aria-label']==='Next page: '+caption);
  assert.ok(b,'Missing next page: '+caption);b.click();
}
"""


@unittest.skipUnless(_NODE, 'Node is optional development tooling for DOM checks.')
class SfcConditionDomTests(unittest.TestCase):
    def run_ui(self, data: bytes, checks: str) -> None:
        parts = captured(data)
        conditions = analyze_sfc_conditions(*parts[:4])
        payload = build_review_data(*parts[:4], **options(parts), sfc_conditions=conditions)
        parsed = ParsedPage(render_review_html(payload))
        dom = DOM.replace('  select() {}', '  select() {}\n  scrollIntoView() {}')
        process = subprocess.run([_NODE, '-e', dom], input=json.dumps({
            'data': payload, 'script': parsed.scripts[1][1], 'checks': CHECKS + checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_grouped_expression_exposes_selected_source_and_ordered_child_nodes(self) -> None:
        self.run_ui(source('<SFCContent>' + transition('Grouping',
            'A OR NOT B AND (2 ** 3 ** 2 >= 0)') + '</SFCContent>'), r"""
        openSequence('Grouping');
        assert.ok(content.textContent.includes('Type validationNot implemented'));
        assert.ok(content.textContent.includes('Runtime evaluationNot implemented'));
        assert.ok(content.textContent.includes('No syntax rejection'));
        let selected=content.querySelectorAll('section').find(n=>n.className==='panel'&&n.textContent.includes('expression root'));
        assert.ok(selected);
        assert.ok(selected.querySelectorAll('pre').some(p=>p.textContent==='A OR NOT B AND (2 ** 3 ** 2 >= 0)'));
        const children=selected.querySelectorAll('button');
        assert.equal(children.length,2);children[1].click();
        assert.ok(content.querySelectorAll('pre').some(p=>p.textContent==='NOT B AND (2 ** 3 ** 2 >= 0)'));
        const refs=rows(tableNamed('Transition expression references'));
        assert.deepEqual(refs.map(r=>texts(r)[0]),['A','B']);
        refs[1].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Source root binding'));
        refs[1].childNodes[2].querySelector('button').click();
        assert.ok(heading.textContent.includes('B'));
        assert.ok(heading.textContent.includes('SOURCE OBJECT'));
        """)

    def test_multiline_comments_preserve_xml_order_metadata_and_literal_script_text(self) -> None:
        text = ('<Transition ID="1" Operand="Comments"><Condition><STContent>'
                '<Line Number="8"><![CDATA[A AND (* first]]></Line>'
                '<Line Number="7"><![CDATA[second *) NOT B // <script>window.sfcInjected=true</script>]]></Line>'
                '</STContent></Condition></Transition>')
        self.run_ui(source('<SFCContent>' + text + '</SFCContent>'), r"""
        navigate('sequenceconditions');filterSequence('gap');
        assert.equal(rows(tableNamed('Sequence transition conditions')).length,1);
        rows(tableNamed('Sequence transition conditions'))[0].childNodes[0].querySelector('button').click();
        const lines=rows(tableNamed('Transition source lines'));
        assert.deepEqual(lines.map(r=>texts(r)[1]),['8','7']);
        assert.ok(content.textContent.includes('out of order number'));
        const comments=rows(tableNamed('Transition expression comments'));
        assert.deepEqual(comments.map(r=>texts(r)[2]),['(* first\nsecond *)','// <script>window.sfcInjected=true</script>']);
        assert.equal(rows(tableNamed('Transition expression references')).length,2);
        assert.ok(!window.sfcInjected);
        assert.equal(content.querySelectorAll('script').length,0);
        lines[1].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('second *) NOT B // <script>window.sfcInjected=true</script>'));
        assert.ok(!window.sfcInjected);
        """)

    def test_unsupported_conditions_never_show_partial_trees_or_reference_claims(self) -> None:
        expressions = [('Dynamic', 'A AND Values[Index]'), ('Malformed', 'A AND ('),
                       ('Call', 'JSR(Main,0);'), ('Unterminated', 'A (* unfinished')]
        content = '<SFCContent>' + ''.join(transition(name, expression, i + 1)
            for i, (name, expression) in enumerate(expressions)) + '</SFCContent>'
        self.run_ui(source(content), r"""
        for(const name of ['Dynamic','Malformed','Call','Unterminated']){
          openSequence(name);
          assert.ok(content.textContent.includes('Unmodeled condition'));
          assert.ok(content.textContent.includes('Expression tree unavailable'));
          assert.ok(content.textContent.includes('Unsupported conditions publish no partial reference bindings.'));
          assert.ok(!content.querySelectorAll('table').some(t=>t.textContent.startsWith('Transition expression nodes')));
        }
        assert.ok(content.textContent.includes('Unterminated comment'));
        openSequence('Call');
        assert.ok(content.textContent.includes('instruction call'));
        assert.ok(content.textContent.includes('JSR(Main,0);'));
        """)

    def test_alias_suffix_binding_and_namespace_gap_remain_distinct(self) -> None:
        data = source('<SFCContent>' + transition('KnownAlias', 'Alias.DN AND A')
            + transition('RejectedAlias', 'Foreign.DN AND A', 2) + '</SFCContent>', tags=(
                '<Tag Name="Timer" DataType="TIMER"/>'
                '<Tag Name="Alias" TagType="Alias" AliasFor="Timer"/>'
                '<Tag Name="Foreign" TagType="Alias" AliasFor="Timer"/>'))
        # Use a different supported scope for the foreign attribute so its XML
        # expanded-name collision does not invalidate the ordinary alias too.
        data = data.replace(b'<RSLogix5000Content>', b'<RSLogix5000Content xmlns:x="urn:foreign">')
        data = data.replace(b'<Tag Name="Foreign" TagType="Alias" AliasFor="Timer"/>', b'')
        data = data.replace(b'<Controller Name="Demo">',
            b'<Controller Name="Demo"><Tags><Tag Name="Foreign" TagType="Alias" x:AliasFor="Timer"/>'
            b'<Tag Name="Timer" DataType="TIMER"/></Tags>')
        self.run_ui(data, r"""
        openSequence('KnownAlias');
        const alias=rowNamed(tableNamed('Transition expression references'),'Alias.DN');
        assert.ok(texts(alias)[1].includes('root bound'));
        assert.equal(texts(alias)[3],'.DN');
        assert.deepEqual(alias.childNodes[2].querySelectorAll('button').filter(b=>!b.attributes['aria-label']).map(b=>b.textContent),['Alias','Timer','Alias']);
        openSequence('RejectedAlias');
        const foreign=rowNamed(tableNamed('Transition expression references'),'Foreign.DN');
        assert.ok(texts(foreign)[1].includes('namespace gap'));
        assert.ok(content.textContent.includes('Reference binding gaps'));
        navigate('sequenceconditions');filterSequence('binding_gaps');
        assert.equal(rows(tableNamed('Sequence transition conditions')).length,1);
        """)

    def test_duplicate_edit_versions_remain_separate_with_inverse_source_links(self) -> None:
        self.run_ui(source('<SFCContent OnlineEditType="Original">'
            + transition('SameName', 'A') + '</SFCContent><SFCContent OnlineEditType="PendingEdits">'
            + transition('SameName', 'B') + '</SFCContent>'), r"""
        navigate('sequenceconditions');
        const versions=rows(tableNamed('Sequence transition conditions'));
        assert.equal(versions.length,2);
        assert.notEqual(texts(versions[0])[4],texts(versions[1])[4]);
        versions[1].childNodes[0].querySelector('button').click();
        assert.equal(texts(rows(tableNamed('Transition expression references'))[0])[0],'B');
        clickText(content,'SameName');
        assert.ok(heading.textContent.includes('SFC ELEMENT'));
        clickText(content,'Inspect transition expression');
        assert.ok(heading.textContent.includes('SEQUENCE CONDITION'));
        assert.equal(texts(rows(tableNamed('Transition expression references'))[0])[0],'B');
        """)

    def test_paginated_transition_list_preserves_last_condition_and_search(self) -> None:
        self.run_ui(source('<SFCContent>' + ''.join(transition(f'Transition{i}', 'A', i + 1)
            for i in range(53)) + '</SFCContent>'), r"""
        navigate('sequenceconditions');
        assert.equal(rows(tableNamed('Sequence transition conditions')).length,50);
        nextSequence('Sequence transition conditions');
        const last=rows(tableNamed('Sequence transition conditions'));
        assert.equal(last.length,3);last[2].childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('Transition52'));
        navigate('sequenceconditions');
        const search=document.getElementById('toolbar').querySelector('input');
        search.value='Transition52';search.events.input();
        assert.equal(rows(tableNamed('Sequence transition conditions')).length,1);
        """)

    def test_paginated_nodes_references_and_source_lines_keep_last_occurrence(self) -> None:
        lines = ''.join(f'<Line Number="{i}"><![CDATA[A' + (' OR' if i < 52 else '')
                        + ']]></Line>' for i in range(53))
        self.run_ui(source('<SFCContent><Transition ID="1" Operand="Repeated">'
            '<Condition><STContent>' + lines + '</STContent></Condition></Transition></SFCContent>'), r"""
        openSequence('Repeated');
        assert.equal(rows(tableNamed('Transition expression nodes')).length,50);
        nextSequence('Transition expression nodes');nextSequence('Transition expression nodes');
        const nodes=rows(tableNamed('Transition expression nodes'));
        assert.equal(nodes.length,5);
        assert.ok(texts(nodes[4])[0].includes('root'));
        nodes[4].childNodes[0].querySelector('button').click();
        assert.equal(rows(tableNamed('Transition expression references')).length,50);
        nextSequence('Transition expression references');
        const refs=rows(tableNamed('Transition expression references'));
        assert.equal(refs.length,3);
        assert.equal(texts(refs[2])[4],'260–261');
        refs[2].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('260–261'));
        assert.equal(rows(tableNamed('Transition source lines')).length,50);
        nextSequence('Transition source lines');
        const lines=rows(tableNamed('Transition source lines'));
        assert.equal(lines.length,3);assert.equal(texts(lines[2])[1],'52');
        lines[2].childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('SFC ELEMENT'));
        """)

    def test_empty_chart_keeps_capture_and_runtime_limits_visible(self) -> None:
        self.run_ui(source('<SFCContent><Step ID="1" Operand="Idle"/></SFCContent>'), r"""
        navigate('sequenceconditions');
        assert.ok(content.textContent.includes('Captured transitions0'));
        assert.ok(content.textContent.includes('No transition conditions match'));
        assert.ok(content.textContent.includes('not evaluated transitions'));
        assert.ok(content.textContent.includes('active edits or process intent'));
        """)


if __name__ == '__main__':
    unittest.main()
