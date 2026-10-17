"""Exercise engineering discovery with invented rungs in the optional Node DOM."""
from __future__ import annotations

import json
import subprocess
import unittest

from plc_workbench.access import analyze_access
from plc_workbench.calculations import analyze_calculations
from plc_workbench.pid import analyze_pid
from plc_workbench.pid_members import analyze_pid_members
from plc_workbench.references import analyze_references
from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from plc_workbench.rung_analysis import analyze_rungs
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.tag_data import analyze_tag_data
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_review import fixture
from test_review_html import ParsedPage


def review(texts: tuple[str, ...] = (
    'XIC(A)OTE(B);',
    '[XIC(A),]OTE(B);',
    'XIC(A)MYSTERY(B)OTE(B);',
    'MYSTERY(A);',
    ';',
    'XIC(A',
    'CPT(B,A+A);',
    'XIC(A);',
), *, comment: str = '', legacy: bool = False, tags: str = '', rung_metadata: bool = True,
           ambiguous_comment: bool = False) -> dict:
    args = fixture(texts, comment=comment, tags=tags)
    if not rung_metadata or ambiguous_comment:
        raw = args[0].data
        if not rung_metadata:
            raw = raw.replace(b'<Rung Number="0" Type="N">', b'<Rung>')
        if ambiguous_comment:
            raw = raw.replace(b'</Comment>', b'</Comment><Comment>Another source comment</Comment>', 1)
        snapshot = snapshot_from_bytes(raw)
        inventory = analyze_snapshot(snapshot)
        args = snapshot, inventory, analyze_references(inventory), analyze_sfc_structure(snapshot, inventory)
    calculations = analyze_calculations(*args[:3])
    access = analyze_access(args[1], args[2], schema_version=4,
                            snapshot=args[0], calculations=calculations)
    tag_data = analyze_tag_data(*args[:2])
    pid = analyze_pid(*args[:3], tag_data)
    members = analyze_pid_members(*args[:3], tag_data, pid)
    analysis = analyze_rungs(*args[:3], access, calculations)
    return build_review_data(*args, access=access, tag_data=tag_data, pid=pid,
                             pid_members=members, calculations=calculations,
                             **({} if legacy else {'rung_analysis': analysis}))


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI behavior checks.')
class RungAnalysisReviewUiTests(unittest.TestCase):
    def run_ui(self, data: dict, checks: str) -> None:
        parsed = ParsedPage(render_review_html(data))
        process = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': data, 'script': parsed.scripts[1][1], 'checks': checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_every_rung_is_accounted_for_once_with_distinct_evidence_groups(self) -> None:
        self.run_ui(review(), r"""
        assert.ok(content.textContent.includes('Automated analysis in progress'));
        clickText(content,'Explore engineering analysisFollow function families, branch structure and uncertainty before reviewing individual instructions.→');
        let table=tableNamed('Engineering rung analysis');
        assert.equal(rows(table).length,8);
        assert.equal(texts(rows(table)[0])[1].split('Boolean outputs').length-1,1);
        assert.equal(new Set(rows(table).map(r=>r.childNodes[0].querySelector('button').textContent)).size,8);
        assert.ok(content.textContent.includes('8 rungs accounted for once'));
        const select=document.getElementById('toolbar').querySelectorAll('select')[0];
        for(const [key,count] of [['identified',4],['partial',1],['unclassified',3]]){
          select.value=key;select.events.change();
          assert.equal(rows(tableNamed('Engineering rung analysis')).length,count,key);
        }
        assert.ok(content.textContent.includes('Includes empty rungs and unavailable syntax'));
        """)

    def test_family_filters_keep_partial_unknown_blocks_in_context(self) -> None:
        self.run_ui(review(), r"""
        navigate('engineering');
        const toolbar=document.getElementById('toolbar');
        const family=toolbar.querySelectorAll('select').find(n=>n.attributes['aria-label']==='Function family');
        family.value='boolean_output';family.events.change();
        assert.equal(rows(tableNamed('Engineering rung analysis')).length,3);
        const partial=rows(tableNamed('Engineering rung analysis')).find(r=>r.textContent.includes('Rung 2'));
        assert.ok(partial.textContent.includes('Boolean outputs'));
        assert.ok(partial.textContent.includes('Possible / partial functions'));
        assert.ok(partial.textContent.includes('1 base-catalogue block gaps'));
        partial.childNodes[0].querySelector('button').click();
        const blocks=tableNamed('Rung ordered block functions');
        assert.deepEqual(rows(blocks).map(r=>r.childNodes[0].querySelector('button').textContent),['XIC','MYSTERY','OTE']);
        assert.ok(rows(blocks)[1].textContent.includes('unknown'));
        assert.ok(content.textContent.includes('Unresolved block functions (1)'));
        assert.ok(content.textContent.includes('Condition blocks lead to one final Boolean assignment.')===false);
        """)

    def test_branch_outline_preserves_source_order_empty_bypass_and_links(self) -> None:
        self.run_ui(review(('[XIC(A),[XIO(A),]]OTE(B);',)), r"""
        navigate('engineering');rows(tableNamed('Engineering rung analysis'))[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Multiple branch paths'));
        assert.ok(content.textContent.includes('Empty branch legs1'));
        const outline=tableNamed('Rung branch outline');
        const text=rows(outline).map(r=>texts(r)[0]);
        assert.deepEqual(text,['Series','Branch · 2 alternatives','Path 1','XIC','Path 2','Branch · 2 alternatives','Path 1','XIO','Path 2 · empty / bypass','OTE']);
        clickText(outline,'XIO');assert.ok(content.textContent.includes('Selected instructionXIO'));
        assert.ok(content.textContent.includes('A final lexical instruction is not necessarily a definite physical output.'));
        """)

    def test_internal_boolean_result_is_distinct_from_module_io(self) -> None:
        self.run_ui(review(('XIC(A)OTE(B);',)), r"""
        navigate('engineering');
        const families=content.querySelectorAll('button').filter(n=>n.className==='engineering-family');
        for(const label of ['I/O inputs','I/O outputs','Possible sensors']){
          const b=families.find(n=>n.childNodes[0].textContent===label);
          assert.equal(b.childNodes[1].textContent,'0');assert.equal(b.childNodes[2].textContent,'No candidates found');
        }
        assert.ok(content.textContent.includes('Zero candidates do not establish absence.'));
        rows(tableNamed('Engineering rung analysis'))[0].querySelector('button').click();
        assert.ok(content.textContent.includes('One bound result address'));
        assert.equal(rows(tableNamed('Engineering result operands')).length,1);
        assert.ok(tableNamed('Engineering result operands').textContent.includes('B'));
        assert.ok(tableNamed('Rung function candidates').textContent.includes('Engineering purpose is unconfirmed.'));
        assert.ok(tableNamed('Rung function candidates').textContent.includes('boolean_assign'));
        """)

    def test_text_hints_and_comments_are_visible_escaped_and_searchable(self) -> None:
        self.run_ui(review(('XIC(A)OTE(B);',), comment='Possible pump alarm <img src=x> & sensor'), r"""
        navigate('engineering');
        const table=tableNamed('Engineering rung analysis');
        assert.ok(table.textContent.includes('Possible equipmentText hint only'));
        assert.ok(table.textContent.includes('Possible alarmsText hint only'));
        assert.ok(table.textContent.includes('Possible sensorsText hint only'));
        const search=document.getElementById('review-search');search.value='pump';search.events.input();
        assert.equal(rows(tableNamed('Engineering rung analysis')).length,1);
        rows(tableNamed('Engineering rung analysis'))[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Possible pump alarm <img src=x> & sensor'));
        assert.equal(content.querySelectorAll('img').length,0);
        assert.ok(tableNamed('Rung function candidates').textContent.includes('A name or comment alone does not establish behavior.'));
        assert.ok(tableNamed('Rung function candidates').textContent.includes('unreviewed'));
        """)

    def test_structure_gap_filters_and_pagination_keep_selection(self) -> None:
        self.run_ui(review(tuple('XIC(A)OTE(B);' for _ in range(51))+('XIC(A);','[XIC(A),]OTE(B);')), r"""
        navigate('engineering');
        assert.equal(rows(tableNamed('Engineering rung analysis')).length,50);
        content.querySelectorAll('button').find(n=>n.attributes['aria-label']==='Next page: Engineering rung analysis').click();
        assert.equal(rows(tableNamed('Engineering rung analysis')).length,3);
        const shape=document.getElementById('toolbar').querySelectorAll('select').find(n=>n.attributes['aria-label']==='Structure / gaps');
        shape.value='no_result';shape.events.change();
        assert.equal(rows(tableNamed('Engineering rung analysis')).length,1);
        assert.ok(tableNamed('Engineering rung analysis').textContent.includes('Rung 51'));
        assert.ok(content.textContent.includes('not proof of dead or unreachable logic'));
        shape.value='bypass';shape.events.change();
        assert.equal(rows(tableNamed('Engineering rung analysis')).length,1);
        assert.ok(tableNamed('Engineering rung analysis').textContent.includes('Rung 52'));
        shape.value='comment';shape.events.change();
        assert.equal(rows(tableNamed('Engineering rung analysis')).length,50);
        """)

    def test_expression_reads_repeat_and_unsupported_calculation_stays_partial(self) -> None:
        self.run_ui(review(('CPT(B,A+A);','CPT(B,ATAN2(A,A));')), r"""
        navigate('engineering');
        const rungRows=rows(tableNamed('Engineering rung analysis'));
        assert.ok(rungRows[1].textContent.includes('Possible / partial functions'));
        assert.ok(rungRows[1].textContent.includes('Unsupported calculation expression'));
        rungRows[0].querySelector('button').click();
        assert.equal(rows(tableNamed('Engineering expression reads')).length,2);
        assert.equal(rows(tableNamed('Engineering result operands')).length,1);
        clickText(tableNamed('Engineering expression reads'),'A');
        assert.ok(content.textContent.includes('Selected expression read'));
        """)

    def test_missing_metadata_filters_preserve_source_navigation(self) -> None:
        self.run_ui(review(('XIC(A)OTE(B);','OTE(B);'), rung_metadata=False), r"""
        navigate('engineering');
        const shape=document.getElementById('toolbar').querySelectorAll('select').find(n=>n.attributes['aria-label']==='Structure / gaps');
        shape.value='metadata';shape.events.change();
        const table=tableNamed('Engineering rung analysis');assert.equal(rows(table).length,1);
        assert.ok(table.textContent.includes('Missing number, type'));
        assert.ok(rows(table)[0].querySelector('button').textContent.startsWith('Unnumbered rung · position '));
        rows(table)[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('Unnumbered rung · position '));
        assert.ok(content.textContent.includes('Missing rung identifiersnumber, type'));
        assert.equal(rows(tableNamed('Rung ordered block functions')).length,2);
        navigate('ladder');
        assert.ok(rows(tableNamed('Ladder rungs'))[0].querySelector('button').textContent.startsWith('Unnumbered rung · position '));
        """)

    def test_mnemonic_only_and_pid_keep_links_to_their_original_evidence(self) -> None:
        self.run_ui(review(('JSR(Main,0);','PID(A,A,0,B,0,A,0);')), r"""
        navigate('engineering');
        const table=tableNamed('Engineering rung analysis');
        assert.ok(rows(table)[0].textContent.includes('Program control flowMnemonic only'));
        assert.ok(rows(table)[1].textContent.includes('7 base-catalogue operand role gaps'));
        assert.ok(content.textContent.includes('Instruction roles or signatures recognized; purpose remains unconfirmed'));
        rows(table)[1].querySelector('button').click();
        const candidates=tableNamed('Rung function candidates');
        assert.ok(candidates.textContent.includes('PID / control'));
        clickText(candidates,'PID · A');
        assert.ok(heading.textContent.includes('PID'));
        assert.ok(tableNamed('PID operand functions'));
        """)

    def test_legacy_reports_do_not_invent_engineering_analysis(self) -> None:
        self.run_ui(review(legacy=True), r"""
        assert.ok(!document.getElementById('navigation').childNodes.some(n=>n.dataset.view==='engineering'));
        assert.ok(!content.textContent.includes('Automated analysis in progress'));
        navigate('ladder');clickText(content,'Rung 0');
        assert.ok(!content.textContent.includes('Ordered block functions'));
        assert.ok(!content.textContent.includes('Rung function candidates'));
        """)

    def test_declared_pid_type_is_a_separate_weak_candidate(self) -> None:
        self.run_ui(review(('MOV(Loop.SP,B);',), tags='<Tag Name="Loop" TagType="Base" DataType="PID"/>'), r"""
        navigate('engineering');
        const table=tableNamed('Engineering rung analysis');
        assert.ok(table.textContent.includes('PID / controlDeclared type evidence'));
        rows(table)[0].querySelector('button').click();
        const candidates=tableNamed('Rung function candidates');
        assert.ok(candidates.textContent.includes('PID execution has not been established.'));
        assert.ok(candidates.textContent.includes('pid_declared_structure'));
        assert.ok(content.textContent.includes('it does not establish a PID execution'));
        assert.ok(!content.textContent.includes('PID evidence on this rung'));
        """)

    def test_ambiguous_comment_is_not_absent_and_zero_is_a_real_rung_number(self) -> None:
        self.run_ui(review(('XIC(A)OTE(B);',), comment='First source comment', ambiguous_comment=True), r"""
        navigate('engineering');
        const first=rows(tableNamed('Engineering rung analysis'))[0];
        assert.ok(first.querySelector('button').textContent.startsWith('Rung 0 · '));
        assert.ok(first.textContent.includes('Comment is ambiguous; see source findings.'));
        assert.ok(!first.textContent.includes('No comment captured.'));
        first.querySelector('button').click();
        assert.ok(heading.textContent.includes('Rung 0 · '));
        assert.ok(content.textContent.includes('Commentambiguous'));
        """)

    def test_unparsed_structure_does_not_assert_no_branches_or_bypass(self) -> None:
        self.run_ui(review(('XIC(A',)), r"""
        navigate('engineering');
        assert.ok(tableNamed('Engineering rung analysis').textContent.includes('Rung structure could not be parsed'));
        assert.ok(!tableNamed('Engineering rung analysis').textContent.includes('No capture/binding gaps in this view'));
        rows(tableNamed('Engineering rung analysis'))[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Branches / legsUnavailable: rung not parsed'));
        assert.ok(content.textContent.includes('Empty branch legsUnavailable: rung not parsed'));
        assert.ok(content.textContent.includes('A path bypasses all blocksUnavailable: rung not parsed'));
        assert.ok(!content.textContent.includes('A path bypasses all blocksNo'));
        assert.ok(!content.querySelectorAll('table').some(t=>t.childNodes.some(c=>c.tagName==='CAPTION'&&c.textContent==='Rung branch outline')));
        """)

    def test_search_accepts_the_displayed_rung_label_and_source_position(self) -> None:
        self.run_ui(review(('XIC(A)OTE(B);','OTE(B);'), rung_metadata=False), r"""
        navigate('engineering');
        const search=document.getElementById('review-search');search.value='Rung 1';search.events.input();
        const table=tableNamed('Engineering rung analysis');assert.equal(rows(table).length,1);
        assert.ok(rows(table)[0].querySelector('button').textContent.startsWith('Rung 1 · '));
        search.value='Unnumbered rung · position';search.events.input();
        const missing=tableNamed('Engineering rung analysis');assert.equal(rows(missing).length,1);
        assert.ok(rows(missing)[0].querySelector('button').textContent.startsWith('Unnumbered rung · position '));
        """)


if __name__ == '__main__':
    unittest.main()
