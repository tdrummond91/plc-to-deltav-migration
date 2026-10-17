"""Development-only timer/counter source navigation checks with invented input.

Node is optional and this module is not in the work-machine test allowlist.
"""
from __future__ import annotations

import json
import subprocess
import unittest

from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_review import fixture
from test_review_html import ParsedPage
from test_stateful_object_workflow import captured, options


def timer_tag(name: str = 'Timer', contents: str = '', datatype: str = 'TIMER') -> str:
    return f'<Tag Name="{name}" DataType="{datatype}">{contents}</Tag>'


def saved(value: str, datatype: str = 'TIMER') -> str:
    return (f'<Data Format="Decorated"><Structure DataType="{datatype}">'
            f'<DataValueMember Name="PRE" DataType="DINT" Value="{value}"/>'
            '</Structure></Data>')


SELECT = r"""
function selectTimer(label,value){
  const s=document.getElementById('toolbar').querySelectorAll('select').find(n=>n.attributes['aria-label']===label);
  assert.ok(s,'Missing select: '+label);s.value=value;s.events.change();
}
function nextTimerPage(caption){
  const b=content.querySelectorAll('button').find(n=>n.attributes['aria-label']==='Next page: '+caption);
  assert.ok(b,'Missing next page: '+caption);b.click();
}
"""


@unittest.skipUnless(_NODE, 'Node is optional development tooling for DOM checks.')
class StatefulObjectDomTests(unittest.TestCase):
    def run_ui(self, source: bytes, checks: str) -> None:
        parts = captured(source)
        data = build_review_data(*parts[:4], **options(parts))
        parsed = ParsedPage(render_review_html(data))
        process = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': data, 'script': parsed.scripts[1][1], 'checks': SELECT + checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_alias_controls_keep_pseudo_arguments_and_member_reader_source_links(self) -> None:
        source = fixture((
            'XIC(A)TON(Timer,17,0);', 'XIC(B)RES(Alias);',
            'XIC(Timer.DN)OTE(A);', 'CPT(B,Timer.ACC+Timer.ACC);',
            'XIC(Timer.dn)OTE(A);',
        ), tags=timer_tag() + '<Tag Name="Alias" TagType="Alias" AliasFor="Timer"/>')[0].data
        self.run_ui(source, r"""
        navigate('statefulobjects');
        assert.ok(content.textContent.includes('Captured timer and counter relationships'));
        assert.ok(!content.textContent.includes('ONS uses state at this occurrence'));
        assert.equal(rows(tableNamed('Timer and counter control groups')).length,1);
        rowNamed(tableNamed('Timer and counter control groups'),'Timer').querySelector('button').click();
        assert.equal(rows(tableNamed('Timer and counter producer occurrences')).length,1);
        assert.equal(rows(tableNamed('Reset occurrences for this control')).length,1);
        const members=tableNamed('Timer and counter member uses');
        assert.deepEqual(texts(rowNamed(members,'Timer.DN')).slice(2),['1 / 0 / 0 / 0','0','0']);
        assert.ok(texts(rowNamed(members,'Timer.dn'))[1].endsWith('known'));
        assert.equal(texts(rowNamed(members,'Timer.dn'))[2],'1 / 0 / 0 / 0');
        assert.equal(texts(rowNamed(members,'Timer.ACC'))[3],'2');
        rowNamed(members,'Timer.DN').querySelector('button').click();
        rows(tableNamed('Timer and counter read operands'))[0].childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('Rung 2'));
        assert.ok(content.textContent.includes('Selected operand'));
        navigate('statefulobjects');
        selectTimer('Timer and counter view','occurrences');
        rows(tableNamed('Timer and counter instruction occurrences'))[0].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('not interpreted as per-scan input values'));
        const args=rows(tableNamed('Timer and counter captured arguments'));
        assert.equal(args.length,3);
        assert.ok(args[1].textContent.includes('17'));
        assert.ok(content.textContent.includes('Incoming source condition'));
        """)

    def test_control_reset_and_tof_cooccurrence_do_not_claim_invalidity_or_ons_behavior(self) -> None:
        source = fixture(('TOF(Timer,?,?);', 'RES(Timer);', 'RES(Control);',
                          'TON(Number,?,?);', 'TON(Modern,?,?);'), tags=(
            timer_tag() + timer_tag('Control', datatype='CONTROL')
            + timer_tag('Number', datatype='DINT') + timer_tag('Modern', datatype='TIMER_T')))[0].data
        self.run_ui(source, r"""
        navigate('statefulobjects');
        const groups=tableNamed('Timer and counter control groups');
        assert.ok(rowNamed(groups,'Timer').textContent.includes('TOF and RES'));
        assert.ok(!rowNamed(groups,'Control').textContent.includes('Declaration conflicts'));
        assert.ok(rowNamed(groups,'Number').textContent.includes('Declaration conflicts'));
        assert.ok(!rowNamed(groups,'Modern').textContent.includes('Declaration conflicts'));
        assert.ok(rowNamed(groups,'Modern').textContent.includes('TIMER_T'));
        rowNamed(groups,'Control').querySelector('button').click();
        assert.ok(content.textContent.includes('A CONTROL reset may be valid'));
        assert.ok(content.textContent.includes('No timer or counter producer occurrences observed'));
        assert.ok(!content.textContent.includes('Change the opcode or evidence filter'));
        assert.ok(!content.textContent.includes('ONS uses state at this occurrence'));
        navigate('statefulobjects');
        rowNamed(tableNamed('Timer and counter control groups'),'Modern').querySelector('button').click();
        assert.ok(content.textContent.includes('No reset occurrences observed for this exact control'));
        """)

    def test_incoming_conditions_preserve_siblings_join_and_ons_state(self) -> None:
        source = fixture(('[XIC(A)TON(First,?,?),XIC(B)TON(Second,?,?)]RES(First);',
                          'ONS(A)RTO(First,?,?);'),
            tags=timer_tag('First') + timer_tag('Second'))[0].data
        self.run_ui(source, r"""
        navigate('statefulobjects');
        selectTimer('Timer and counter view','occurrences');
        rows(tableNamed('Timer and counter instruction occurrences'))[0].childNodes[0].querySelector('button').click();
        let graph=rows(tableNamed('Timer and counter incoming condition'));
        assert.deepEqual(graph.filter(r=>r.childNodes[1].textContent.includes('Test XIC')).map(r=>r.childNodes[1].querySelector('.cell-sub').textContent),['A']);
        navigate('statefulobjects');
        selectTimer('Timer and counter view','occurrences');
        rows(tableNamed('Timer and counter instruction occurrences'))[1].childNodes[0].querySelector('button').click();
        graph=rows(tableNamed('Timer and counter incoming condition'));
        assert.deepEqual(graph.filter(r=>r.childNodes[1].textContent.includes('Test XIC')).map(r=>r.childNodes[1].querySelector('.cell-sub').textContent),['B']);
        navigate('statefulobjects');
        selectTimer('Timer and counter view','occurrences');
        rows(tableNamed('Timer and counter instruction occurrences'))[2].childNodes[0].querySelector('button').click();
        graph=rows(tableNamed('Timer and counter incoming condition'));
        assert.deepEqual(graph.filter(r=>r.childNodes[1].textContent.includes('Test XIC')).map(r=>r.childNodes[1].querySelector('.cell-sub').textContent),['A','B']);
        assert.ok(graph.some(r=>r.textContent.includes('Any branch input may hold')));
        navigate('statefulobjects');
        selectTimer('Timer and counter view','occurrences');
        rows(tableNamed('Timer and counter instruction occurrences'))[3].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Contains stored-state condition'));
        assert.ok(tableNamed('Timer and counter incoming condition').textContent.includes('ONS: incoming AND NOT storage'));
        """)

    def test_duplicate_and_mismatched_stored_values_remain_separate_and_safe_to_open(self) -> None:
        source = fixture(('TON(Timer,?,?);',), tags=timer_tag(contents=(
            saved('17') + saved('99', 'COUNTER')
            + saved('&lt;script&gt;window.timerInjected=true&lt;/script&gt;'))))[0].data
        self.run_ui(source, r"""
        navigate('statefulobjects');
        selectTimer('Timer and counter evidence','gaps');
        rowNamed(tableNamed('Timer and counter control groups'),'Timer').querySelector('button').click();
        const savedRows=rows(tableNamed('Timer and counter stored evidence'));
        assert.equal(savedRows.length,6);
        assert.deepEqual(savedRows.filter(r=>r.childNodes[2].textContent!=='No scalar value on this element').map(r=>r.childNodes[2].textContent),['17','99','<script>window.timerInjected=true</script>']);
        assert.ok(savedRows[3].textContent.includes('stored type mismatch'));
        assert.equal(rows(tableNamed('Timer and counter data representations')).length,3);
        savedRows[5].childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('STORED DATA ELEMENT'));
        assert.ok(content.textContent.includes('<script>window.timerInjected=true</script>'));
        assert.ok(!window.timerInjected);
        """)

    def test_namespace_rejected_member_reads_and_controls_remain_source_only(self) -> None:
        source = fixture(('TON(Timer,?,?);', 'XIC(RejectedDone)OTE(A);', 'RES(RejectedControl);'),
            tags=timer_tag() + '<Tag Name="RejectedDone" TagType="Alias" AliasFor="Timer.DN"/>'
                '<Tag Name="RejectedControl" TagType="Alias" AliasFor="Timer"/>')[0].data
        source = source.replace(b'<RSLogix5000Content>', b'<RSLogix5000Content xmlns:x="urn:foreign">')
        source = source.replace(b'AliasFor=', b'x:AliasFor=')
        self.run_ui(source, r"""
        navigate('statefulobjects');
        selectTimer('Timer and counter evidence','gaps');
        rowNamed(tableNamed('Timer and counter control groups'),'Timer').querySelector('button').click();
        const member=rowNamed(tableNamed('Timer and counter member uses'),'Timer.DN');
        assert.deepEqual(texts(member).slice(2),['0 / 0 / 0 / 0','0','1']);
        member.querySelector('button').click();
        assert.equal(rows(tableNamed('Timer and counter namespace operand gaps')).length,1);
        rows(tableNamed('Timer and counter namespace operand gaps'))[0].childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('Rung 1'));
        navigate('statefulobjects');
        selectTimer('Timer and counter view','occurrences');
        const occurrence=rows(tableNamed('Timer and counter instruction occurrences')).find(r=>r.childNodes[0].textContent==='RES · RejectedControl');
        assert.ok(occurrence);
        assert.ok(occurrence.childNodes[1].textContent.includes('No qualified control address'));
        occurrence.childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Control association unresolved'));
        assert.ok(!content.textContent.includes('Qualified control identity'));
        """)

    def test_raw_capture_issues_are_visible_even_without_a_qualified_member_path(self) -> None:
        foreign = ('<DefaultData Format="Decorated" xmlns:x="urn:foreign"><Structure DataType="TIMER">'
                   '<DataValueMember x:Name="PRE" DataType="DINT" Value="41"/>'
                   '</Structure></DefaultData>')
        source = fixture(('TON(Duplicate,?,?);', 'TON(Foreign,?,?);'), tags=(
            timer_tag('Duplicate', saved('17') + saved('18'))
            + timer_tag('Foreign', foreign)))[0].data
        source = source.replace(b'<RSLogix5000Content>', b'<RSLogix5000Content xmlns:x="urn:foreign">')
        self.run_ui(source, r"""
        navigate('statefulobjects');
        selectTimer('Timer and counter evidence','gaps');
        const groups=tableNamed('Timer and counter control groups');
        assert.equal(rows(groups).length,2);
        assert.ok(rowNamed(groups,'Duplicate').textContent.includes('Stored data capture issues'));
        assert.ok(rowNamed(groups,'Foreign').textContent.includes('Stored data capture issues'));
        rowNamed(groups,'Foreign').querySelector('button').click();
        const reps=rows(tableNamed('Timer and counter data representations'));
        assert.equal(reps.length,1);
        assert.equal(reps[0].childNodes[3].textContent,'1');
        reps[0].childNodes[1].querySelector('button').click();
        assert.ok(heading.textContent.includes('STORED TAG DATA'));
        assert.equal(rows(tableNamed('Stored data capture issues')).length,1);
        assert.ok(content.textContent.includes('41'));
        """)

    def test_group_and_occurrence_pagination_keep_last_source_navigation(self) -> None:
        source = fixture(tuple(f'TON(Timer{i},?,?);' for i in range(53)), tags=''.join(
            timer_tag(f'Timer{i}') for i in range(53)))[0].data
        self.run_ui(source, r"""
        navigate('statefulobjects');
        assert.equal(rows(tableNamed('Timer and counter control groups')).length,50);
        nextTimerPage('Timer and counter control groups');
        const groups=rows(tableNamed('Timer and counter control groups'));
        assert.equal(groups.length,3);
        groups[2].querySelector('button').click();
        assert.ok(heading.textContent.includes('Timer52'));
        navigate('statefulobjects');
        selectTimer('Timer and counter view','occurrences');
        assert.equal(rows(tableNamed('Timer and counter instruction occurrences')).length,50);
        nextTimerPage('Timer and counter instruction occurrences');
        const last=rows(tableNamed('Timer and counter instruction occurrences'));
        assert.equal(last.length,3);
        last[2].childNodes[3].querySelector('button').click();
        assert.ok(heading.textContent.includes('Rung 52'));
        """)

    def test_member_and_stored_evidence_pagination_keep_last_value_and_operand(self) -> None:
        members = ''.join(f'<DataValueMember Name="Extra{i}" DataType="DINT" Value="{i}"/>'
                          for i in range(53))
        source = fixture(('TON(Timer,?,?);',) + tuple(f'MOV(Timer.Extra{i},A);' for i in range(53)),
            tags=timer_tag(contents=f'<Data Format="Decorated"><Structure DataType="TIMER">{members}</Structure></Data>'))[0].data
        self.run_ui(source, r"""
        navigate('statefulobjects');
        rowNamed(tableNamed('Timer and counter control groups'),'Timer').querySelector('button').click();
        assert.equal(rows(tableNamed('Timer and counter member uses')).length,50);
        nextTimerPage('Timer and counter member uses');
        assert.equal(rows(tableNamed('Timer and counter member uses')).length,4);
        const last=rowNamed(tableNamed('Timer and counter member uses'),'Timer.Extra52');
        last.querySelector('button').click();
        rows(tableNamed('Timer and counter read operands'))[0].childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('Rung 53'));
        navigate('statefulobjects');
        rowNamed(tableNamed('Timer and counter control groups'),'Timer').querySelector('button').click();
        assert.equal(rows(tableNamed('Timer and counter stored evidence')).length,50);
        nextTimerPage('Timer and counter stored evidence');
        const stored=rows(tableNamed('Timer and counter stored evidence'));
        assert.equal(stored.length,4);
        assert.equal(stored[3].childNodes[2].textContent,'52');
        stored[3].childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('Extra52'));
        assert.ok(heading.textContent.includes('STORED DATA ELEMENT'));
        """)


if __name__ == '__main__':
    unittest.main()
