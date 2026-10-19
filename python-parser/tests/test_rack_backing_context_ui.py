"""Development-only navigation for source rack correspondences, not live I/O."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
import subprocess
import unittest

from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from plc_workbench.source_reuse import source_reuse_scope
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_rack_backing_context import fixture
from test_rack_backing_context_workflow import captured, options
from test_residual_diagnostics_workflow import options as previous_options
from test_review_html import ParsedPage


@lru_cache(maxsize=3)
def report(source: str | None = None, historical: bool = False) -> dict:
    with source_reuse_scope():
        parts = captured((fixture() if source is None else source).encode())
        return build_review_data(*parts[:4], **(previous_options(parts) if historical else options(parts)))


SELECT = r"""
function choose(label,value){
 const select=document.getElementById('toolbar').querySelectorAll('select').find(s=>s.attributes['aria-label']===label);
 assert.ok(select,label);select.value=value;select.events.change();
}
"""


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI checks.')
class RackBackingContextUiTests(unittest.TestCase):
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

    def test_address_and_root_dossiers_link_each_captured_evidence_layer(self) -> None:
        self.run_ui(r"""
        navigate('rackbacking');assert.equal(rows(tableNamed('Rack source addresses')).length,2);
        assert.ok(content.textContent.includes('Source occurrences5'));
        assert.ok(content.textContent.includes('original bindings, condition gaps and exact-address groups remain unchanged'));
        const inputRow=rows(tableNamed('Rack source addresses')).find(r=>r.textContent.includes('Remote:3:I'));
        assert.ok(inputRow.textContent.includes('Remote:I.Slot[3].Data.0'));assert.ok(!inputRow.textContent.includes('unnamed'));inputRow.childNodes[0].querySelector('button').click();
        assert.equal(rows(tableNamed('Rack address occurrences')).length,4);
        clickText(content,'Inspect rack declaration evidence');
        const proof=rows(tableNamed('Rack declaration source evidence'));
        for(const label of ['Rack declaration','Rack connection','Adapter','Backing declaration','Captured data representation','Slot array','Selected array element','Selected slot structure','Data member','Fault member'])assert.ok(proof.some(r=>texts(r)[0]===label),label);
        proof.find(r=>texts(r)[0]==='Data member').childNodes[1].querySelector('button').click();
        assert.ok(heading.textContent.includes('Data'));assert.ok(!content.textContent.includes('undefined'));
        navigate('rackbacking');choose('Rack evidence','roots');assert.equal(rows(tableNamed('Rack source declarations')).length,2);
        const rootSearch=document.getElementById('review-search');rootSearch.value='Remote:I.Slot';rootSearch.events.input();
        assert.equal(rows(tableNamed('Rack source declarations')).length,1);rootSearch.value='';rootSearch.events.input();
        choose('Rack evidence','uses');assert.equal(rows(tableNamed('Rack source occurrences')).length,5);
        """)

    def test_original_binding_and_sfc_gaps_link_to_separate_occurrence_proofs(self) -> None:
        self.run_ui(r"""
        navigate('bindingcontext');assert.equal(rows(tableNamed('Binding gap occurrences')).length,3);
        rows(tableNamed('Binding gap occurrences'))[0].childNodes[0].querySelector('button').click();
        clickText(content,'Inspect rack source occurrence: associated');
        assert.ok(heading.textContent.includes('RACK SOURCE OCCURRENCE'));
        assert.ok(content.textContent.includes('Original predicate with binding gap'));
        clickText(content,'Explain binding gap');assert.ok(heading.textContent.includes('BINDING GAP CONTEXT'));
        navigate('rackbacking');choose('Rack evidence','uses');
        const transition=rows(tableNamed('Rack source occurrences')).find(r=>texts(r)[1]==='sfc / read');
        assert.ok(transition);transition.childNodes[4].querySelector('button').click();
        assert.ok(heading.textContent.includes('SEQUENCE REFERENCE CONTEXT'));
        assert.ok(content.textContent.includes('Original root bindingunresolved'));
        clickText(content,'Inspect rack source occurrence: associated');
        assert.ok(heading.textContent.includes('RACK SOURCE OCCURRENCE'));
        navigate('engineering');
        assert.ok(rows(tableNamed('Engineering additional evidence coverage')).some(r=>texts(r)[0]==='Rack source addresses'));
        navigate('residuals');assert.ok(tableNamed('Unresolved instruction analysis').textContent.includes('Rack source address'));
        assert.ok(tableNamed('Unresolved instruction analysis').textContent.includes('Binding evidence incomplete'));
        """)

    def test_bad_alias_remains_a_use_gap_even_when_address_and_root_are_supported(self) -> None:
        source = fixture().replace('Name="ProbeAlias"', 'DataType="REAL" Name="ProbeAlias"')
        data = report(source)
        rejected = sum(u['disposition'] != 'associated' for u in data['rack_backing_context']['uses'])
        self.assertGreater(rejected, 0)
        self.run_ui(r"""
        navigate('residuals');
        const cohort=rows(tableNamed('Residual source populations')).find(r=>texts(r)[0]==='Rack source occurrences with gaps');
        const expected=Number(texts(cohort)[1]);assert.ok(expected>0);cohort.querySelector('button').click();
        const uses=rows(tableNamed('Rack source occurrences'));assert.equal(uses.length,expected);
        assert.ok(uses.every(r=>r.textContent.includes('alias metadata unqualified')));
        uses[0].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('alias metadata unqualified'));
        clickText(content,'Inspect address correspondence');
        assert.ok(content.textContent.includes('Dispositionassociated'));
        assert.ok(tableNamed('Rack address occurrences').textContent.includes('alias metadata unqualified'));
        """, data)

    def test_unsupported_suffix_has_no_fabricated_destination_and_search_intersects_filter(self) -> None:
        data = report(fixture(rungs=('XIC(Remote:3:I.Data.32);',), sfc=''))
        self.run_ui(r"""
        navigate('rackbacking');choose('Filter Rack source addresses','gaps');
        const addresses=rows(tableNamed('Rack source addresses'));assert.equal(addresses.length,1);
        assert.ok(addresses[0].textContent.includes('bit out of range'));assert.ok(addresses[0].textContent.includes('No qualified destination'));
        const search=document.getElementById('review-search');search.value='does-not-exist';search.events.input();
        assert.ok(content.textContent.includes('No records in this section'));
        search.value='Data.32';search.events.input();assert.equal(rows(tableNamed('Rack source addresses')).length,1);
        rows(tableNamed('Rack source addresses'))[0].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Adapter source addressNo qualified destination'));
        """, data)

    def test_historical_report_does_not_invent_projection(self) -> None:
        self.run_ui(r"""
        assert.ok(!document.querySelectorAll('.nav-button').some(b=>b.dataset.view==='rackbacking'));
        navigate('bindingcontext');assert.equal(rows(tableNamed('Binding gap occurrences')).length,3);
        rows(tableNamed('Binding gap occurrences'))[0].childNodes[0].querySelector('button').click();
        assert.ok(!content.textContent.includes('Inspect rack source occurrence'));
        """, report(historical=True))

    def test_candidate_names_remain_inert_text(self) -> None:
        data = deepcopy(report())
        data['references']['rack_candidates']['candidates'][0]['name'] = '<img src=x onerror=alert(1)>'
        self.run_ui(r"""
        navigate('rackbacking');assert.ok(content.textContent.includes('<img src=x'));
        assert.equal(content.querySelectorAll('img').length,0);
        rows(tableNamed('Rack source addresses'))[0].childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('<img src=x'));assert.equal(heading.querySelectorAll('img').length,0);
        """, data)


if __name__ == '__main__':
    unittest.main()
