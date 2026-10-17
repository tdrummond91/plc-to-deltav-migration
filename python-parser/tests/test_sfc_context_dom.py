"""Development-only navigation of invented sequence relationship evidence."""
from __future__ import annotations

from functools import lru_cache
import json
import subprocess
import unittest

from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_review_html import ParsedPage
from test_sfc_condition_dom import CHECKS, source, transition
from test_sfc_context import fixture as context_fixture
from test_sfc_context_workflow import SOURCE, captured, options
from test_module_io import LOCAL, communications, module


@lru_cache(maxsize=6)
def payload(data: bytes) -> dict:
    parts = captured(data)
    return build_review_data(*parts[:4], **options(parts))


CONTEXT_CHECKS = r"""
function openContext(name,reference){
  navigate('sequenceconditions');
  const search=document.getElementById('toolbar').querySelector('input');
  search.value=name;search.events.input();
  const condition=rows(tableNamed('Sequence transition conditions')).find(r=>r.childNodes[0].querySelector('button')?.textContent===name);
  assert.ok(condition,'Missing transition: '+name);condition.childNodes[0].querySelector('button').click();
  const row=rowNamed(tableNamed('Transition reference relationships'),reference);
  assert.ok(row,'Missing context reference: '+reference);
  row.childNodes[0].querySelector('button').click();
  assert.ok(heading.textContent.includes('SEQUENCE REFERENCE CONTEXT'));
}
function panelNamed(name){
  const result=content.querySelectorAll('section').find(n=>n.className==='panel'&&n.childNodes[0]?.textContent===name);
  assert.ok(result,'Missing panel: '+name);return result;
}
"""


@unittest.skipUnless(_NODE, 'Node is optional development tooling for DOM checks.')
class SfcContextDomTests(unittest.TestCase):
    def run_ui(self, checks: str, data: bytes = SOURCE) -> None:
        review = payload(data)
        parsed = ParsedPage(render_review_html(review))
        dom = DOM.replace('  select() {}', '  select() {}\n  scrollIntoView() {}')
        process = subprocess.run([_NODE, '-e', dom], input=json.dumps({
            'data': review, 'script': parsed.scripts[1][1],
            'checks': CHECKS + CONTEXT_CHECKS + checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_reference_address_and_alias_writer_navigation_excludes_foreign_text(self) -> None:
        self.run_ui(r"""
        openContext('SharedStepMember','StepA.X');
        assert.ok(content.textContent.includes('Context qualificationexact address'));
        const counts=panelNamed('Qualified exact address uses').textContent;
        assert.ok(counts.includes('Distinct captured writer instructions2'),counts);
        assert.equal(rows(tableNamed('Qualified ladder writers')).length,2);
        assert.equal(rows(tableNamed('Qualified ladder readers')).length,1);
        assert.equal(rows(tableNamed('Excluded sequence address uses')).length,1);
        const writer=rows(tableNamed('Qualified ladder writers')).find(r=>r.textContent.includes('StepAlias.X'));
        assert.ok(writer);writer.childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('Rung 5'));
        openContext('SharedStepMember','StepA.X');
        const sourcePanel=panelNamed('Reference source');
        sourcePanel.querySelectorAll('button').find(b=>b.textContent==='StepA.X').click();
        assert.ok(heading.textContent.includes('SEQUENCE EXACT ADDRESS'));
        assert.equal(rows(tableNamed('Qualified ladder writers')).length,2);
        clickText(content,'Open original RLL relationship evidence');
        assert.ok(heading.textContent.includes('EXACT ADDRESS'));
        """)

    def test_bound_candidates_preserve_edits_peers_aliases_and_local_shadow(self) -> None:
        self.run_ui(r"""
        openContext('SharedStepMember','StepA.X');
        const candidates=rows(tableNamed('Sequence step candidates'));
        assert.equal(candidates.length,4);
        assert.deepEqual(candidates.map(r=>texts(r)[1]),['same content','same content','other edit','peer chart']);
        assert.ok(candidates.every(r=>texts(r)[2].includes('bound identity')));
        assert.ok(candidates.every(r=>texts(r)[2].includes('base member')));
        assert.ok(candidates.every(r=>!texts(r)[0].includes('OtherProgram')));
        candidates[2].childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('SFC ELEMENT'));
        clickText(content,'Open parent SFC content');
        assert.ok(content.textContent.includes('PendingEdits')||content.textContent.includes('Pending edits'));
        openContext('WholeStep','StepA');
        assert.ok(rows(tableNamed('Sequence step candidates')).every(r=>texts(r)[2].includes('exact')));
        openContext('LocalShadow','StepA.X');
        const local=rows(tableNamed('Sequence step candidates'));
        assert.equal(local.length,1);assert.ok(texts(local[0])[0].includes('OtherProgram'));
        assert.ok(content.textContent.includes('No qualified explicit RLL writer captured'));
        """)

    def test_suffix_boundaries_do_not_merge_distinct_index_or_root_spellings(self) -> None:
        self.run_ui(r"""
        openContext('ExactArrayMember','Steps[0].X');
        assert.equal(rows(tableNamed('Sequence step candidates')).length,1);
        assert.ok(content.textContent.includes('Exact suffix[0].X'));
        openContext('DifferentArraySpelling','Steps[00].X');
        assert.ok(content.textContent.includes('No step candidates captured'));
        assert.ok(content.textContent.includes('Exact suffix[00].X'));
        openContext('PrefixCollision','StepAB.X');
        const candidates=rows(tableNamed('Sequence step candidates'));
        assert.equal(candidates.length,1);assert.equal(texts(candidates[0])[3],'StepAB');
        openContext('DescendantMember','StepA.Nested.X');
        assert.equal(rows(tableNamed('Sequence step candidates')).length,4);
        assert.ok(content.textContent.includes('No qualified explicit RLL writer captured'));
        assert.ok(content.textContent.includes('does not establish an uninitialized value or dead logic'));
        """)

    def test_lexical_hints_and_missing_alias_target_never_become_qualified_addresses(self) -> None:
        self.run_ui(r"""
        openContext('DiagramNameOnly','DiagramOnly.X');
        assert.ok(content.textContent.includes('Context qualificationbinding gap'));
        assert.ok(content.textContent.includes('Lookup rootDiagramOnly'));
        const candidate=rows(tableNamed('Sequence step candidates'))[0];
        assert.ok(texts(candidate)[2].includes('lexical hint'));
        assert.ok(!content.textContent.includes('Qualified exact address uses'));
        openContext('MissingAliasTarget','BrokenAlias.X');
        assert.ok(content.textContent.includes('Diagnosticalias chain gap'));
        assert.ok(content.textContent.includes('Lookup rootAbsentTarget'));
        assert.ok(tableNamed('Same-name declarations outside lookup scope').textContent.includes('AbsentTarget'));
        assert.ok(!content.textContent.includes('Qualified exact address uses'));
        openContext('IdentifierSpellings','TRUE');
        assert.ok(content.textContent.includes('Lexical categoryboolean word'));
        assert.ok(content.textContent.includes('lexical observations only'));
        assert.ok(!content.textContent.includes('Qualified exact address uses'));
        """)

    def test_namespace_gap_and_unqualified_outside_scope_candidate_remain_visible(self) -> None:
        data = SOURCE.replace(b'<Tag Name="PeerOnly" DataType="BOOL"/>',
                              b'<Tag Name="PeerOnly" DataType="BOOL" x:Marker="foreign"/>')
        self.run_ui(r"""
        openContext('ForeignDeclaration','Foreign.X');
        assert.ok(content.textContent.includes('Context qualificationnamespace gap'));
        assert.ok(!content.textContent.includes('Qualified exact address uses'));
        openContext('OutsideScopeName','PeerOnly');
        const candidate=rows(tableNamed('Unqualified same-name declarations outside lookup scope'))[0];
        assert.ok(candidate.textContent.includes('PeerOnly'));
        candidate.querySelector('button').click();
        assert.ok(heading.textContent.includes('SOURCE OBJECT'));
        assert.ok(content.textContent.includes('urn:deliberate-foreign')||content.textContent.includes('PeerOnly'));
        """, data)

    def test_shared_references_paginate_and_keep_last_peer_transition_navigable(self) -> None:
        self.run_ui(r"""
        openContext('SharedStepMember','StepA.X');
        assert.equal(rows(tableNamed('Sequence address references')).length,50);
        nextSequence('Sequence address references');
        const last=rows(tableNamed('Sequence address references'));
        assert.ok(last.length>0&&last.length<50);
        assert.equal(texts(last[last.length-1])[1],'PeerCondition');
        last[last.length-1].childNodes[1].querySelector('button').click();
        assert.ok(heading.textContent.includes('PeerCondition'));
        const ref=rows(tableNamed('Transition reference relationships'))[0];
        ref.childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('SEQUENCE REFERENCE CONTEXT'));
        assert.ok(content.textContent.includes('Content versionabsent'));
        navigate('sequenceconditions');filterSequence('context_gap');
        const gaps=rows(tableNamed('Sequence transition conditions'));
        assert.equal(gaps.length,6);
        assert.ok(gaps.every(r=>!texts(r)[0].includes('SharedStepMember')));
        """)

    def test_inferred_module_namespace_gap_is_included_in_unresolved_filter(self) -> None:
        modules = LOCAL + module(communications=communications('<InputTag/>'))
        modules = modules.replace('<Port Id="1" Type="ICP" Address="3" Upstream="true"/>',
            '<Port Id="1" Type="ICP" Address="3" Upstream="true" x:Marker="foreign"/>')
        data = context_fixture(text='Local:3:I.Data', modules=modules).encode()
        parts = captured(data)
        self.assertEqual(parts[21].transitions[0]['status'], 'modeled')
        self.assertEqual(parts[22].references[0]['status'], 'namespace_gap')
        self.run_ui(r"""
        navigate('sequenceconditions');filterSequence('gap');
        const conditions=rows(tableNamed('Sequence transition conditions'));
        assert.equal(conditions.length,1);
        assert.ok(conditions[0].textContent.includes('Reference relationship diagnostic'));
        conditions[0].childNodes[0].querySelector('button').click();
        const reference=rows(tableNamed('Transition reference relationships'))[0];
        assert.ok(texts(reference)[1].includes('namespace gap'));
        reference.childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Original root bindingroot bound'));
        assert.ok(!content.textContent.includes('Qualified exact address uses'));
        """, data)

    def test_direct_chart_connections_and_attached_authored_note_are_followable(self) -> None:
        self.run_ui(r"""
        openSequence('SharedStepMember');
        const links=rows(tableNamed('Structural links'));
        assert.equal(links.length,2);
        links[1].childNodes[2].querySelector('button').click();
        assert.ok(heading.textContent.includes('SFC ELEMENT'));
        assert.ok(content.textContent.includes('Steps[0]'));
        openSequence('SharedStepMember');
        const notes=rows(tableNamed('Annotation attachments'));
        assert.equal(notes.length,1);notes[0].childNodes[1].querySelector('button').click();
        assert.ok(heading.textContent.includes('SFC ELEMENT'));
        assert.ok(content.textContent.includes('Invented note: compare the two possible writers before migration.'));
        """)

    def test_expression_reader_navigation_literal_script_and_empty_conditions(self) -> None:
        self.run_ui(r"""
        openContext('TimerMember','StepA.T');
        assert.equal(rows(tableNamed('Qualified ladder expression readers')).length,1);
        rows(tableNamed('Qualified ladder expression readers'))[0].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Selected expression read'));
        openSequence('CommentEvidence');
        assert.ok(content.textContent.includes('// <script>window.contextFixtureLeak=true</script>'));
        assert.equal(content.querySelectorAll('script').length,0);assert.ok(!window.contextFixtureLeak);
        rows(tableNamed('Transition reference relationships'))[0].childNodes[0].querySelector('button').click();
        assert.ok(!window.contextFixtureLeak);
        """)
        self.run_ui(r"""
        openSequence('LiteralOnly');
        assert.ok(content.textContent.includes('No reference leaves captured'));
        assert.ok(content.textContent.includes('Direct chart connections'));
        assert.ok(!content.textContent.includes('No qualified explicit RLL writer captured'));
        """, source('<SFCContent>' + transition('LiteralOnly', '1 = 1') + '</SFCContent>'))


if __name__ == '__main__':
    unittest.main()
