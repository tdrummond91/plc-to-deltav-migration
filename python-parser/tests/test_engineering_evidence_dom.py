"""Report-only companion reconciliation preserves base semantics and source gaps."""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import subprocess
import unittest

from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_review_html import ParsedPage
from test_rung_analysis_review_ui import review as historical_review
from test_signal_dependencies_workflow import captured, options


SOURCE = Path(__file__).resolve().parents[2] / 'public/fixtures/synthetic/engineering_evidence_demo.L5X'


@lru_cache(maxsize=5)
def review(source: bytes | None = None) -> dict:
    parts = captured(SOURCE.read_bytes() if source is None else source)
    return build_review_data(*parts[:4], **options(parts))


SELECT = r"""
function choose(label,value){
 const select=document.getElementById('toolbar').querySelectorAll('select').find(n=>n.attributes['aria-label']===label);
 assert.ok(select,label);select.value=value;select.events.change();
}
function openRung(comment){
 navigate('engineering');
 const row=rows(tableNamed('Engineering rung analysis')).find(r=>r.textContent.includes(comment));
 assert.ok(row,comment);row.childNodes[0].querySelector('button').click();
}
function block(opcode){
 return rows(tableNamed('Rung ordered block functions')).find(r=>r.childNodes[0].querySelector('button').textContent===opcode);
}
"""


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI checks.')
class EngineeringEvidenceDomTests(unittest.TestCase):
    def run_ui(self, checks: str, data: dict | None = None) -> None:
        payload = review() if data is None else data
        parsed = ParsedPage(render_review_html(payload))
        # Observe the actual browser-side object, not just the Python input copy.
        data_line = "const data = JSON.parse(document.getElementById('review-data').textContent);"
        script = parsed.scripts[1][1].replace(data_line, data_line + """
        globalThis.engineeringTestData=data;
        globalThis.engineeringTestBefore=JSON.stringify({analysis:data.rung_analysis,access:data.access});
        """, 1)
        semantic_check = """
        assert.equal(JSON.stringify({analysis:engineeringTestData.rung_analysis,
          access:engineeringTestData.access}),engineeringTestBefore);
        """
        result = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': payload, 'script': script, 'checks': SELECT + checks + semantic_check}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_distinct_cohorts_and_unknown_slot_partition_keep_base_counts(self) -> None:
        self.run_ui(r"""
        navigate('engineering');
        assert.deepEqual(rows(tableNamed('Engineering additional evidence coverage')).map(texts),[
          ['PID slots / storage','2','2','Captured in this report'],
          ['Call / boundary context','5','4','Captured in this report'],
          ['File / array slots','5','5','Captured in this report'],
          ['AOI / custom context','3','1','Captured in this report']]);
        assert.deepEqual(rows(tableNamed('Engineering unknown operand context')).map(texts),[
          ['Specialized file roles','18'],['PID named slots only','7'],
          ['Execution raw fields only','8'],['AOI instance field only','2'],
          ['No additional slot context','14']]);
        const total=rows(tableNamed('Engineering unknown operand context')).reduce((n,r)=>n+Number(texts(r)[1]),0);
        assert.equal(total,49);
        assert.ok(content.textContent.includes('Base unknown blocks14'));
        assert.ok(content.textContent.includes('Instructions with additional context15'));
        assert.ok(content.textContent.includes('Rungs with additional context8'));
        assert.ok(content.textContent.includes('Base unknown blocks without additional context0'));
        const primary=document.getElementById('toolbar').querySelectorAll('select')[0];
        for(const [key,count] of [['identified',2],['partial',2],['unclassified',6]]){
          primary.value=key;primary.events.change();assert.equal(rows(tableNamed('Engineering rung analysis')).length,count,key);
        }
        """)

    def test_mixed_rung_keeps_base_roles_and_exact_provider_links(self) -> None:
        self.run_ui(r"""
        openRung('Mixed providers');
        assert.deepEqual(rows(tableNamed('Rung ordered block functions')).map(r=>r.childNodes[0].querySelector('button').textContent),['XIC','PID','AVE','JSR','Widget','OTE']);
        for(const [opcode,count] of [['PID',7],['AVE',6],['JSR',2],['Widget',1]]){
          const row=block(opcode);assert.equal(texts(row)[3].split('unknown').length-1,count,opcode);
          assert.equal(row.childNodes[4].querySelectorAll('button').length,1,opcode);
        }
        assert.ok(block('PID').textContent.includes('Opaque condition transfer remains unresolved'));
        assert.ok(block('PID').textContent.includes('member catalogue: gaps retained'));
        assert.ok(block('JSR').textContent.includes('target body: rll structure parsed'));
        assert.ok(block('Widget').textContent.includes('matching type name'));
        assert.ok(content.textContent.includes('<img src=x onerror=alert(1)>'));
        assert.equal(content.querySelectorAll('img').length,0);
        clickText(block('PID'),'PID slots / storage');assert.ok(heading.textContent.includes('PID'));
        openRung('Mixed providers');clickText(block('AVE'),'File / array slots');assert.ok(content.textContent.includes('Samples[0]'));
        openRung('Mixed providers');clickText(block('JSR'),'Call / boundary context');assert.ok(heading.textContent.includes('JSR Sub'));
        openRung('Mixed providers');clickText(block('Widget'),'AOI / custom context');assert.ok(content.textContent.includes('First-field instance context'));
        """)

    def test_malformed_namespace_and_missing_targets_never_hide_gaps(self) -> None:
        self.run_ui(r"""
        openRung('Malformed signatures');
        for(const opcode of ['PID','AVE'])assert.ok(block(opcode).textContent.includes('argument count mismatch'),opcode);
        openRung('Foreign namespace');
        assert.ok(block('AVE').textContent.includes('qualification: namespace gap'));
        assert.ok(block('AVE').textContent.includes('Source namespace gap remains'));
        assert.ok(block('AVE').textContent.includes('Captured context with gaps'));
        openRung('Missing targets');
        assert.ok(block('JSR').textContent.includes('missing candidate'));
        assert.ok(block('MissingCall').textContent.includes('missing declaration'));
        assert.ok(block('MissingCall').textContent.includes('declaration unavailable'));
        openRung('Existing target missing body');
        assert.ok(block('JSR').textContent.includes('rll structure partial'));
        assert.ok(block('JSR').textContent.includes('Captured context with gaps'));
        """)

    def test_binding_condition_and_raw_source_links_are_preserved(self) -> None:
        self.run_ui(r"""
        openRung('Unknown binding');
        assert.ok(block('XIC').textContent.includes('1 source binding gaps remain'));
        clickText(block('XIC'),'Explain binding gap');assert.ok(content.textContent.includes('MissingPermit'));
        openRung('Unknown binding');
        const copies=rows(tableNamed('Rung ordered block functions')).filter(r=>r.childNodes[0].querySelector('button').textContent==='AVE');
        assert.equal(copies.length,2);
        clickText(copies[1],'File / array slots');assert.ok(content.textContent.includes('Samples[1]'));
        openRung('Mixed providers');clickText(block('PID'),'Inspect condition transfer');
        assert.ok(content.textContent.includes('Unknown transfer'));
        openRung('Mixed providers');block('PID').childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('PID(Loop,PV,0,CV,0,0,0)'));
        """)

    def test_unindexed_aoi_array_keeps_source_shape_gap(self) -> None:
        source = SOURCE.read_bytes().replace(
            b'<Tag Name="Instance" DataType="Widget"/>',
            b'<Tag Name="Instance" DataType="Widget" Dimensions="2"/>')
        data = review(source)
        self.assertEqual(sum(c['address_shape'] == 'unindexed_array'
                             for c in data['aoi_body_context']['calls']), 2)
        self.run_ui(r"""
        navigate('engineering');
        const row=rows(tableNamed('Engineering additional evidence coverage')).find(r=>texts(r)[0]==='AOI / custom context');
        assert.deepEqual(texts(row),['AOI / custom context','3','3','Captured in this report']);
        openRung('Mixed providers');
        assert.ok(block('Widget').textContent.includes('address shape: unindexed array'));
        assert.ok(block('Widget').textContent.includes('Captured context with gaps'));
        clickText(block('Widget'),'AOI / custom context');
        assert.ok(content.textContent.includes('unindexed array'));
        """, data)

    def test_complete_pid_catalogue_accepts_matched_data_array_header(self) -> None:
        from test_pid_members import full_members
        source = SOURCE.read_bytes().replace(
            b'<DataValueMember Name="SP" DataType="REAL" Value="12"/>',
            full_members().encode('utf-8'))
        data = review(source)
        # The separate malformed PID remains partial; the valid occurrence's
        # complete member catalogue must not acquire an unrelated header gap.
        self.assertEqual(data['pid_members']['status'], 'partial')
        self.assertEqual(data['pid_members']['coverage']['structures_with_gaps'], 0)
        self.assertEqual(data['pid_members']['coverage']['members_by_status']['array_header_matched'], 1)
        self.run_ui(r"""
        navigate('engineering');
        const row=rows(tableNamed('Engineering additional evidence coverage')).find(r=>texts(r)[0]==='PID slots / storage');
        assert.deepEqual(texts(row),['PID slots / storage','2','1','Captured in this report']);
        openRung('Mixed providers');
        assert.ok(block('PID').textContent.includes('Captured context.'));
        assert.ok(block('PID').textContent.includes('member catalogue: no gap from captured members'));
        assert.ok(block('PID').textContent.includes('Opaque condition transfer remains unresolved'));
        assert.equal(texts(block('PID'))[3].split('unknown').length-1,7);
        """, data)

    def test_aoi_declaration_and_symbol_gaps_survive_supported_routine_body(self) -> None:
        cases = [
            (SOURCE.read_bytes().replace(b'</Parameters>',
             b'</Parameters><EncodedData>Invented opaque source marker</EncodedData>', 1),
             'encoded regions: 1'),
            (SOURCE.read_bytes().replace(b'<Parameter Name="Input"',
             b'<Parameter x:Marker="foreign" Name="Input"', 1),
             'symbol context gaps: 1'),
        ]
        for source, expected in cases:
            with self.subTest(expected=expected):
                data = review(source)
                self.assertEqual(data['aoi_body_context']['routines'][0]['body_status'], 'supported_rll')
                self.run_ui(r"""
                navigate('engineering');
                const row=rows(tableNamed('Engineering additional evidence coverage')).find(r=>texts(r)[0]==='AOI / custom context');
                assert.deepEqual(texts(row),['AOI / custom context','3','3','Captured in this report']);
                openRung('Mixed providers');
                assert.ok(block('Widget').textContent.includes('Captured context with gaps'));
                """ + f'assert.ok(block("Widget").textContent.includes({json.dumps(expected)}));', data)

    def test_pid_connection_gaps_survive_complete_storage_and_member_headers(self) -> None:
        from test_pid_members import full_members
        complete = SOURCE.read_bytes().replace(
            b'<DataValueMember Name="SP" DataType="REAL" Value="12"/>',
            full_members().encode('utf-8'))
        cases = [
            (complete.replace(b'PID(Loop,PV,0,CV,0,0,0)', b'PID(Loop,PV,0,CV,Loop,0,0)'),
             'master self-references: 1'),
            (complete.replace(b'<Comment>Base recognized function</Comment><Text><![CDATA[XIC(Permit)',
             b'<Comment>Base recognized function</Comment><Text><![CDATA[XIC(Loop.Unknown)'),
             'deferred / unknown member addresses: 0 / 1'),
        ]
        for source, expected in cases:
            with self.subTest(expected=expected):
                data = review(source)
                self.assertEqual(data['pid_members']['coverage']['structures_with_gaps'], 0)
                self.run_ui(r"""
                navigate('engineering');
                const row=rows(tableNamed('Engineering additional evidence coverage')).find(r=>texts(r)[0]==='PID slots / storage');
                assert.deepEqual(texts(row),['PID slots / storage','2','2','Captured in this report']);
                openRung('Mixed providers');
                assert.ok(block('PID').textContent.includes('Captured context with gaps'));
                assert.ok(block('PID').textContent.includes('member catalogue: no gap from captured members'));
                """ + f'assert.ok(block("PID").textContent.includes({json.dumps(expected)}));', data)

    def test_execution_guard_gaps_do_not_disappear_behind_parsed_target_body(self) -> None:
        self.run_ui(r"""
        openRung('Mixed providers');
        assert.ok(block('JSR').textContent.includes('target body: rll structure parsed'));
        assert.ok(block('JSR').textContent.includes('incoming condition: opaque'));
        assert.ok(block('JSR').textContent.includes('Captured context with gaps'));
        clickText(block('JSR'),'Call / boundary context');
        assert.ok(content.textContent.includes('opaque'));
        """)

    def test_provider_filter_and_search_intersect_without_changing_totals(self) -> None:
        self.run_ui(r"""
        navigate('engineering');choose('Additional evidence','available');
        assert.equal(rows(tableNamed('Engineering rung analysis')).length,8);
        choose('Additional evidence','gaps');assert.equal(rows(tableNamed('Engineering rung analysis')).length,7);
        const search=document.getElementById('review-search');search.value='Malformed signatures';search.events.input();
        assert.equal(rows(tableNamed('Engineering rung analysis')).length,1);
        assert.ok(content.textContent.includes('Instructions with additional context15'));
        search.value='';search.events.input();choose('Additional evidence','unexplained');
        assert.ok(content.textContent.includes('No rungs match these filters'));
        """)

    def test_older_payload_does_not_invent_unavailable_provider_evidence(self) -> None:
        self.run_ui(r"""
        navigate('engineering');
        const coverage=rows(tableNamed('Engineering additional evidence coverage'));
        assert.equal(coverage.filter(r=>r.textContent.includes('Unavailable in this report')).length,3);
        choose('Additional evidence','unexplained');
        assert.equal(rows(tableNamed('Engineering rung analysis')).length,2);
        rows(tableNamed('Engineering rung analysis'))[0].childNodes[0].querySelector('button').click();
        assert.ok(block('MYSTERY').textContent.includes('No additional provider record'));
        assert.ok(block('MYSTERY').textContent.includes('unknown'));
        assert.ok(content.textContent.includes('Unresolved block functions (1)'));
        """, historical_review())

    def test_no_engineering_payload_keeps_historical_report_navigation(self) -> None:
        self.run_ui(r"""
        navigate('ladder');assert.equal(rows(tableNamed('Ladder rungs')).length,8);
        assert.ok(!content.textContent.includes('Evidence across analysis views'));
        """, historical_review(legacy=True))

    def test_render_does_not_modify_base_classifications_or_roles(self) -> None:
        data = review()
        before = json.dumps({'analysis': data['rung_analysis'], 'access': data['access']}, sort_keys=True)
        self.run_ui("navigate('engineering');openRung('Additional unmapped');", data)
        self.assertEqual(before, json.dumps({'analysis': data['rung_analysis'], 'access': data['access']}, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
