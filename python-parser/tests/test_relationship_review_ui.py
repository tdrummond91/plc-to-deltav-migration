"""Exercise relationship dossiers with invented evidence in the optional Node DOM."""
from __future__ import annotations

import json
import subprocess
import unittest

from plc_workbench.access import analyze_access
from plc_workbench.calculations import analyze_calculations
from plc_workbench.pid import analyze_pid
from plc_workbench.pid_members import analyze_pid_members
from plc_workbench.relationships import analyze_relationships
from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from plc_workbench.rung_analysis import analyze_rungs
from plc_workbench.tag_data import analyze_tag_data
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_review import fixture
from test_review_html import ParsedPage


def review(texts: tuple[str, ...] = (
    'MOV(A,Temp)CPT(B,Temp+Temp);',
    'MOV(A.Member,Temp)ADD(Temp,2,B);',
    'MOV(A.member,Temp)ADD(Temp,2,B);',
    'PID(Loop,A,0,B,Master,0,0);',
    'MSG(Control);',
    'XIC(InputOnly);',
    'OTE(OutputOnly);',
    'MOV(Bad.Child,B)CPT(B,Bad.Child+1);',
), *, legacy: bool = False, tags: str = '') -> dict:
    args = fixture(texts, tags=(
        '<Tag Name="Temp" TagType="Base" DataType="REAL"/>'
        '<Tag Name="Loop" TagType="Base" DataType="PID"/>'
        '<Tag Name="Master" TagType="Base" DataType="PID"/>'
        '<Tag Name="Control" TagType="Base" DataType="MESSAGE"/>'
        '<Tag Name="InputOnly" TagType="Base" DataType="BOOL"/>'
        '<Tag Name="OutputOnly" TagType="Base" DataType="BOOL"/>'
        '<Tag Name="Bad" TagType="Alias" AliasFor="A.0"/>' + tags))
    calculations = analyze_calculations(*args[:3])
    access = analyze_access(args[1], args[2], schema_version=4,
                            snapshot=args[0], calculations=calculations)
    tag_data = analyze_tag_data(*args[:2])
    pid = analyze_pid(*args[:3], tag_data)
    members = analyze_pid_members(*args[:3], tag_data, pid)
    rungs = analyze_rungs(*args[:3], access, calculations)
    relationships = analyze_relationships(*args[:3], access, calculations, rungs)
    return build_review_data(*args, access=access, tag_data=tag_data, pid=pid,
                             pid_members=members, calculations=calculations,
                             rung_analysis=rungs,
                             **({} if legacy else {'relationships': relationships}))


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI behavior checks.')
class RelationshipReviewUiTests(unittest.TestCase):
    def run_ui(self, data: dict, checks: str, *, count_search_characters: bool = False) -> None:
        parsed = ParsedPage(render_review_html(data))
        dom = DOM
        if count_search_characters:
            invocation = "vm.runInThisContext(input.script,{filename:'report.js'});"
            dom = dom.replace(invocation, """
let indexedCharacters=0;
const originalLower=String.prototype.toLocaleLowerCase;
String.prototype.toLocaleLowerCase=function(...args){indexedCharacters+=this.length;return originalLower.apply(this,args);};
""" + invocation + "\nString.prototype.toLocaleLowerCase=originalLower;", 1)
        process = subprocess.run([_NODE, '-e', dom], input=json.dumps({
            'data': data, 'script': parsed.scripts[1][1], 'checks': checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_exact_spelling_counts_and_source_navigation(self) -> None:
        self.run_ui(review(), r"""
        navigate('engineering');clickText(content,'Explore address relationships');
        let table=tableNamed('Exact address groups');
        const names=rows(table).map(r=>r.childNodes[0].querySelector('button').textContent);
        assert.ok(names.includes('A.Member'));assert.ok(names.includes('A.member'));
        const temp=rows(table).find(r=>r.childNodes[0].querySelector('button').textContent==='Temp');
        assert.deepEqual(texts(temp).slice(2),['2','3','0','0','2','3']);
        temp.childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('Temp'));
        assert.equal(rows(tableNamed('Exact address read occurrences')).length,2);
        assert.equal(rows(tableNamed('Exact address write occurrences')).length,3);
        const expression=tableNamed('Exact address expression reads');
        assert.deepEqual(rows(expression).map(r=>texts(r)[1]),['[0, 4)','[5, 9)']);
        assert.equal(rows(tableNamed('Exact address rungs')).length,3);
        rows(expression)[1].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Selected expression read'));
        assert.ok(content.textContent.includes('[5, 9)'));
        const selected=content.querySelectorAll('section').find(s=>s.textContent.startsWith('Selected expression read'));
        clickText(selected,'Address: Temp');assert.ok(heading.textContent.includes('EXACT ADDRESS EVIDENCE'));
        clickText(content,'Open root access and other suffixes');
        assert.equal(rows(tableNamed('Root exact address groups')).length,1);
        assert.ok(content.textContent.includes('Root access combines all suffixes'));
        """)

    def test_unknown_roles_and_stateful_access_are_not_invented_readers(self) -> None:
        self.run_ui(review(), r"""
        navigate('relationships');
        let table=tableNamed('Exact address groups');
        const loop=rows(table).find(r=>r.childNodes[0].querySelector('button').textContent==='Loop');
        assert.deepEqual(texts(loop).slice(1),['Unknown roles only','0','0','0','1','0','1']);
        loop.childNodes[0].querySelector('button').click();
        assert.equal(rows(tableNamed('Exact address unknown occurrences')).length,1);
        assert.ok(content.textContent.includes('not counted as an explicit reader or writer'));
        navigate('relationships');
        const control=rows(tableNamed('Exact address groups')).find(r=>r.childNodes[0].querySelector('button').textContent==='Control');
        assert.deepEqual(texts(control).slice(1),['Captured reads and writes','0','0','1','0','0','1']);
        control.childNodes[0].querySelector('button').click();
        assert.equal(rows(tableNamed('Exact address read_write occurrences')).length,1);
        assert.ok(content.textContent.includes('do not establish dead or uninitialized logic'));
        """)

    def test_index_spelling_variants_remain_distinct_from_root_access(self) -> None:
        self.run_ui(review(('XIC(A[1])XIC(A[01])XIC(A[ 1 ])XIC(A.1);',)), r"""
        navigate('access');
        rows(tableNamed('Root access groups'))[0].childNodes[2].querySelector('button').click();
        const exact=tableNamed('Root exact address groups');
        assert.deepEqual(rows(exact).map(r=>r.childNodes[0].querySelector('button').textContent),['A[1]','A[01]','A[ 1 ]','A.1']);
        assert.equal(rows(tableNamed('Root access occurrences')).length,4);
        rows(exact)[1].querySelector('button').click();
        assert.ok(heading.textContent.includes('A[01]'));
        assert.equal(rows(tableNamed('Exact address read occurrences')).length,1);
        assert.ok(content.textContent.includes('does not validate members or prove whether two addresses overlap'));
        """)

    def test_long_shared_root_is_bounded_in_labels_and_search_with_full_source_link(self) -> None:
        name = 'Root' + 'N' * 59_996
        suffix = '.' + 'Member' * 60
        texts = tuple(f'MOV(B,LongAlias[{i}])ADD(LongAlias[{i}],1,B);' for i in range(200))
        data = review(texts + (f'XIC(LongAlias{suffix});',), tags=(
            f'<Tag Name="{name}" TagType="Base" DataType="DINT"/>'
            f'<Tag Name="LongAlias" TagType="Alias" AliasFor="{name}"/>'))
        self.run_ui(data, r"""
        // Both address rows and local-link rows previously copied the complete
        // 60,000-character root name, exceeding 24 million search characters.
        assert.ok(indexedCharacters<2000000,'Search index amplification: '+indexedCharacters);
        navigate('relationships');
        assert.ok(content.textContent.includes('search text use shortened previews'));
        let table=tableNamed('Exact address groups');
        assert.equal(rows(table).length,50);
        for(const row of rows(table))assert.ok(row.childNodes[0].querySelector('button').textContent.length<=280);
        content.querySelectorAll('button').find(n=>n.attributes['aria-label']==='Next page: Exact address groups').click();
        assert.equal(rows(tableNamed('Exact address groups')).length,50);
        let search=document.getElementById('review-search');search.value='[199]';search.events.input();
        assert.equal(rows(tableNamed('Exact address groups')).length,1);
        rows(tableNamed('Exact address groups'))[0].querySelector('button').click();
        assert.ok(heading.textContent.length<500);
        const links=content.querySelectorAll('button');
        const declaration=links.find(n=>n.textContent.startsWith('Root'));
        declaration.click();
        assert.ok(heading.textContent.includes('Root'+'N'.repeat(59996)));
        navigate('relationships');
        search=document.getElementById('review-search');search.value='Member';search.events.input();
        const long=rows(tableNamed('Exact address groups'))[0];
        assert.ok(long.childNodes[0].querySelector('button').textContent.length<=280);
        long.querySelector('button').click();
        assert.ok(content.textContent.includes('.'+'Member'.repeat(60)));
        navigate('relationships');
        let mode=document.getElementById('toolbar').querySelectorAll('select')[1];mode.value='links';mode.events.change();
        search=document.getElementById('review-search');search.value='[199]';search.events.input();
        const local=tableNamed('Local calculation links');assert.equal(rows(local).length,1);
        assert.ok(rows(local)[0].childNodes[2].textContent.length<=280);
        """, count_search_characters=True)

    def test_profiles_search_and_pagination_restore_on_back(self) -> None:
        data = review(tuple(f'XIC(A.Member{i});' for i in range(53)) + ('OTE(B);',))
        self.run_ui(data, r"""
        navigate('relationships');
        let toolbar=document.getElementById('toolbar');
        let profile=toolbar.querySelectorAll('select')[0];profile.value='read_only';profile.events.change();
        assert.equal(rows(tableNamed('Exact address groups')).length,50);
        content.querySelectorAll('button').find(n=>n.attributes['aria-label']==='Next page: Exact address groups').click();
        assert.equal(rows(tableNamed('Exact address groups')).length,3);
        rows(tableNamed('Exact address groups'))[0].querySelector('button').click();
        heading.querySelector('button').click();
        assert.equal(rows(tableNamed('Exact address groups')).length,3);
        let search=document.getElementById('review-search');search.value='Member52';search.events.input();
        assert.equal(rows(tableNamed('Exact address groups')).length,1);
        assert.ok(tableNamed('Exact address groups').textContent.includes('A.Member52'));
        search.value='No captured explicit writer';search.events.input();
        assert.equal(rows(tableNamed('Exact address groups')).length,50);
        search.value='No captured explicit reader';search.events.input();
        assert.ok(content.textContent.includes('No exact addresses match'));
        profile=document.getElementById('toolbar').querySelectorAll('select')[0];profile.value='write_only';profile.events.change();
        assert.equal(rows(tableNamed('Exact address groups')).length,1);
        """)

    def test_local_reuse_keeps_repeated_expression_reads_and_barriers(self) -> None:
        self.run_ui(review(('MOV(A,Temp)CPT(B,Temp+Temp);',
                            'MOV(A,Temp)XIC(A)ADD(Temp,2,B);',
                            '[MOV(A,Temp),]ADD(Temp,2,B);')), r"""
        navigate('relationships');
        let mode=document.getElementById('toolbar').querySelectorAll('select')[1];mode.value='links';mode.events.change();
        const links=tableNamed('Local calculation links');
        assert.equal(rows(links).length,2);
        assert.deepEqual(rows(links).map(r=>texts(r)[4]),['Expression read occurrence','Expression read occurrence']);
        assert.ok(content.textContent.includes('does not prove execution, value flow or scan order'));
        rows(links)[1].childNodes[3].querySelector('button').click();
        assert.ok(content.textContent.includes('Selected expression read'));
        navigate('ladder');clickText(content,'Rung 0');
        assert.equal(rows(tableNamed('Rung local calculation links')).length,2);
        clickText(tableNamed('Engineering result operands'),'Address: Temp');
        assert.ok(heading.textContent.includes('EXACT ADDRESS EVIDENCE'));
        """)

    def test_operand_reuse_patterns_keep_literal_and_variable_differences(self) -> None:
        self.run_ui(review(('MOV(A,Temp)ADD(Temp,2,B);',
                            'MOV(B,Temp)ADD(Temp,2,A);',
                            'MOV(B,Temp)ADD(B,2,A);',
                            'MOV(A,Temp)ADD(Temp,3,B);',
                            'MYSTERY(A);')), r"""
        navigate('relationships');
        let mode=document.getElementById('toolbar').querySelectorAll('select')[1];mode.value='patterns';mode.events.change();
        const patterns=tableNamed('Operand-reuse patterns');
        assert.equal(rows(patterns).length,3);
        assert.deepEqual(rows(patterns).map(r=>texts(r)[1]),['2','1','1']);
        assert.equal(rows(tableNamed('Skipped operand-reuse rungs')).length,1);
        assert.ok(content.textContent.includes('do not establish behavioral equivalence'));
        rows(patterns)[0].querySelector('button').click();
        assert.equal(rows(tableNamed('Ladder rungs')).length,2);
        clickText(content,'Rung 1');
        assert.ok(content.textContent.includes('Open operand-reuse pattern (2 rungs)'));
        """)

    def test_alias_composition_gaps_remain_distinct_and_link_to_source(self) -> None:
        self.run_ui(review(), r"""
        navigate('relationships');
        assert.ok(!tableNamed('Exact address groups').textContent.includes('A.0.Child'));
        let mode=document.getElementById('toolbar').querySelectorAll('select')[1];mode.value='gaps';mode.events.change();
        const gaps=tableNamed('Address identity gaps');assert.equal(rows(gaps).length,2);
        assert.deepEqual(rows(gaps).map(r=>texts(r)[1]),['Operand','Expression reference']);
        rows(gaps)[1].querySelector('button').click();
        assert.ok(content.textContent.includes('Expanded suffix cannot form an address'));
        assert.ok(content.textContent.includes('Selected expression read'));
        """)

    def test_pid_slot_and_cpt_destination_link_without_assigning_pid_access(self) -> None:
        self.run_ui(review(), r"""
        navigate('pid');rows(tableNamed('PID instruction occurrences'))[0].querySelector('button').click();
        const slots=tableNamed('PID operand functions');
        const loop=rows(slots)[0].childNodes[3].querySelectorAll('button');
        loop[loop.length-1].click();
        assert.ok(heading.textContent.includes('EXACT ADDRESS EVIDENCE'));
        assert.ok(content.textContent.includes('Unknown roles only'));
        navigate('calculations');rows(tableNamed('Calculation occurrences'))[0].querySelector('button').click();
        const destination=content.querySelectorAll('section').find(s=>s.textContent.startsWith('Destination operand'));
        const buttons=destination.querySelectorAll('button');buttons[buttons.length-1].click();
        assert.ok(heading.textContent.includes('EXACT ADDRESS EVIDENCEB'));
        """)

    def test_legacy_report_has_no_relationship_view(self) -> None:
        self.run_ui(review(legacy=True), r"""
        assert.ok(!document.getElementById('navigation').childNodes.some(n=>n.dataset.view==='relationships'));
        navigate('engineering');
        assert.ok(!content.textContent.includes('Explore address relationships'));
        navigate('access');rows(tableNamed('Root access groups'))[0].querySelector('button').click();
        assert.ok(!content.textContent.includes('Exact expanded addresses'));
        """)
