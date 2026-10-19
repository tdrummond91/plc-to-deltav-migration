"""Development-only checks for exact residual cohorts and SFR evidence joins."""
from __future__ import annotations

from functools import lru_cache
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


@lru_cache(maxsize=1)
def report() -> dict:
    source = SOURCE.replace(
        b'<Rung Number="10" Type="N">',
        b'<Rung Number="11" Type="N"><Text>SFR(Chart,Step)SFR(Chart,Permit);</Text></Rung>'
        b'<Rung><Text>MOV(Raw,Outgoing[Raw]);</Text></Rung>'
        b'<Rung Number="10" Type="N">',
    ).replace(b'SequenceOnly AND Step.X', b'SequenceOnly AND MissingPermit')
    with source_reuse_scope():
        parts = captured(source)
        return build_review_data(*parts[:4], **options(parts))


SELECT = r"""
function cohort(name){
 navigate('residuals');
 const row=rows(tableNamed('Residual source populations')).find(r=>texts(r)[0]===name);
 assert.ok(row,name);const count=Number(texts(row)[1]);row.querySelector('button').click();return count;
}
function filter(label){return document.getElementById('toolbar').querySelectorAll('select').find(s=>s.attributes['aria-label']===label);}
"""


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI checks.')
class ResidualNavigationUiTests(unittest.TestCase):
    def run_ui(self, checks: str, data: dict | None = None) -> None:
        data = report() if data is None else data
        script = ParsedPage(render_review_html(data)).scripts[1][1]
        marker = "const data = JSON.parse(document.getElementById('review-data').textContent);"
        script = script.replace(marker, marker +
                                'globalThis.savedData=data;globalThis.savedBefore=JSON.stringify(data);', 1)
        result = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': data, 'script': script, 'checks': SELECT + checks +
            'assert.equal(JSON.stringify(savedData),savedBefore);'}), text=True,
            encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_sfr_targets_join_residuals_without_erasing_opaque_behavior(self) -> None:
        self.run_ui(r"""
        navigate('engineering');
        const coverage=rows(tableNamed('Engineering additional evidence coverage')).find(r=>texts(r)[0]==='Sequence reset target context');
        assert.deepEqual(texts(coverage),['Sequence reset target context','2','1','Captured in this report']);
        navigate('residuals');const search=document.getElementById('review-search');search.value='SFR';search.events.input();
        const resets=rows(tableNamed('Unresolved instruction analysis'));assert.equal(resets.length,2);
        for(const row of resets){
          assert.ok(row.textContent.includes('Outgoing condition unmodeled'));
          assert.ok(row.textContent.includes('captured reset fields and candidate dispositions explain available source context'));
          assert.ok(row.textContent.includes('Opaque condition transfer remains unresolved'));
          assert.ok(!row.textContent.includes('No additional provider record'));
        }
        const matched=resets.find(r=>r.textContent.includes('matched exported contents: 1 / 1'));
        assert.ok(matched);assert.ok(!matched.textContent.includes('Specialized context has gaps'));
        clickText(matched,'Sequence reset target context');
        assert.ok(tableNamed('SFR content candidates').textContent.includes('unique candidate'));
        heading.querySelector('.back').click();
        const missing=rows(tableNamed('Unresolved instruction analysis')).find(r=>r.textContent.includes('matched exported contents: 0 / 1'));
        assert.ok(missing.textContent.includes('Specialized context has gaps'));
        clickText(missing,'Sequence reset target context');
        assert.ok(tableNamed('SFR content candidates').textContent.includes('missing candidate'));
        """)

    def test_rung_cohorts_open_exact_filters_and_detail_back_retains_selection(self) -> None:
        self.run_ui(r"""
        for(const [name,value] of [['Rungs without a known local result','no_result'],['Rungs without a clear comment','comment'],['Rungs with missing identifiers','metadata']]){
          const expected=cohort(name);assert.ok(expected>0);assert.equal(filter('Structure / gaps').value,value);
          assert.equal(rows(tableNamed('Engineering rung analysis')).length,expected);
          rows(tableNamed('Engineering rung analysis'))[0].childNodes[0].querySelector('button').click();
          heading.querySelector('.back').click();assert.equal(filter('Structure / gaps').value,value);
          assert.equal(rows(tableNamed('Engineering rung analysis')).length,expected);
        }
        """)

    def test_address_transition_and_index_cohorts_match_their_counts(self) -> None:
        self.run_ui(r"""
        for(const [name,value] of [['Read-only exact addresses','read_only'],['Write-only exact addresses','write_only']]){
          const expected=cohort(name);assert.ok(expected>0);
          assert.equal(filter('Filter Address relationships').value,value);
          assert.equal(rows(tableNamed('Exact address groups')).length,expected);
        }
        const transitions=cohort('Sequence transition gaps');assert.equal(transitions,1);
        assert.equal(filter('Filter Sequence conditions').value,'gap');
        assert.equal(rows(tableNamed('Sequence transition conditions')).length,transitions);
        const indexes=cohort('Indexed source occurrences');assert.equal(indexes,1);
        assert.equal(filter('Filter Instruction & index context').value,'indexed');
        assert.equal(rows(tableNamed('Indexed source occurrences')).length,indexes);
        assert.ok(!content.querySelectorAll('caption').some(c=>c.textContent==='Custom instruction occurrences'));
        filter('Filter Instruction & index context').value='all';filter('Filter Instruction & index context').events.change();
        assert.ok(tableNamed('Custom instruction occurrences'));
        """)

    def test_historical_report_without_sfr_keeps_navigation(self) -> None:
        from test_residual_source_dom import review
        self.run_ui(r"""
        navigate('engineering');
        assert.ok(!rows(tableNamed('Engineering additional evidence coverage')).some(r=>texts(r)[0]==='Sequence reset target context'));
        const count=cohort('Rungs without a clear comment');
        assert.equal(filter('Structure / gaps').value,'comment');
        assert.equal(rows(tableNamed('Engineering rung analysis')).length,count);
        """, review())

    def test_supported_aoi_body_is_accounted_for_without_hiding_missing_rll(self) -> None:
        self.run_ui(r"""
        navigate('residuals');
        const bodies=rows(tableNamed('Residual routine bodies'));
        assert.equal(bodies.length,1);assert.ok(bodies[0].textContent.includes('MissingBody'));
        assert.ok(!bodies[0].textContent.includes('Logic'));
        """)

    def test_protected_and_incomplete_aoi_bodies_keep_precise_questions(self) -> None:
        for source, status in [
            (SOURCE.replace(b'<AddOnInstructionDefinition Name=', b'<AddOnInstructionDefinition Protected="false" Name=', 1), 'protected'),
            (SOURCE.replace(b'<Routines><Routine Name="Logic" Type="RLL"><RLLContent>',
                            b'<Routines><Routine Name="Logic" Type="ST"><RLLContent>', 1), 'unsupported_language'),
        ]:
            with self.subTest(status=status), source_reuse_scope():
                parts = captured(source)
                data = build_review_data(*parts[:4], **options(parts))
                self.assertEqual(data['aoi_body_context']['routines'][0]['body_status'], status)
                self.run_ui(r"""
                navigate('residuals');const bodies=rows(tableNamed('Residual routine bodies'));
                assert.ok(bodies.some(r=>r.textContent.includes('MissingBody')));
                const logic=bodies.find(r=>r.textContent.includes('Logic'));assert.ok(logic);
                clickText(logic,'Inspect AOI body');assert.ok(heading.textContent.includes('Logic'));
                """ + f'assert.ok(content.textContent.includes({json.dumps(status.replace("_", " "))}));', data)

    def test_gsv_question_mark_retains_exact_signature_uncertainty(self) -> None:
        source = SOURCE.replace(b'<Text>JSR(Sub,0)', b'<Text>GSV(WALLCLOCKTIME,?,LocalDateTime,Raw)JSR(Sub,0)')
        with source_reuse_scope():
            parts = captured(source)
            data = build_review_data(*parts[:4], **options(parts))
        self.run_ui(r"""
        navigate('transfers');const search=document.getElementById('review-search');search.value='GSV';search.events.input();
        rows(tableNamed('Instruction condition transfers'))[0].querySelector('button').click();
        assert.ok(content.textContent.includes('The captured instance field is ?'));
        assert.ok(content.textContent.includes('do not establish it as an unused-instance equivalent'));
        assert.ok(content.textContent.includes('outgoing condition stays opaque'));
        assert.ok(!content.textContent.includes('source invalid'));
        """, data)


if __name__ == '__main__':
    unittest.main()
