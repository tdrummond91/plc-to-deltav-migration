"""Development-only candidate navigation on wholly invented source evidence."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest

from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_review_html import ParsedPage
from test_signal_candidates_workflow import captured, options
from test_signal_patterns_dom import SELECT

SOURCE = (Path(__file__).resolve().parents[2] /
          'public/fixtures/synthetic/signal_candidates_demo.L5X').read_bytes()


@unittest.skipUnless(_NODE, 'Node is optional development tooling for DOM checks.')
class SignalCandidatesDomTests(unittest.TestCase):
    def run_ui(self, checks: str, *, truncated: bool = False, historical: bool = False) -> None:
        if historical:
            from test_signal_dependencies_workflow import captured as capture
        else:
            capture = captured
        parts = capture(SOURCE)
        data = build_review_data(*parts[:4], **options(parts))
        if truncated:
            data['signal_context']['outputs'][0]['candidate_context']['scan_status'] = 'truncated'
            data['signal_context']['coverage']['candidate_scans_by_status']['truncated'] += 1
        page = ParsedPage(render_review_html(data))
        result = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': data, 'script': page.scripts[1][1], 'checks': SELECT + checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_group_paging_module_seeds_and_condition_search(self) -> None:
        self.run_ui(r"""
        navigate('signalcontext');choose('Signal view','candidates');
        assert.equal(rows(tableNamed('Grouped signal source candidates')).length,50);
        const next=content.querySelectorAll('button').find(n=>n.attributes['aria-label']==='Next page: Grouped signal source candidates');
        assert.ok(next);next.click();
        assert.ok(rows(tableNamed('Grouped signal source candidates')).length>0);
        assert.ok(rows(tableNamed('Grouped signal source candidates')).length<50);
        choose('Candidate evidence','module_input');
        const io=rows(tableNamed('Grouped signal source candidates'));
        assert.equal(io.length,1);assert.ok(io[0].textContent.includes('M:O.Data.1'));
        assert.ok(io[0].textContent.includes('Module input root'));
        assert.ok(io[0].textContent.includes('Module output root'));
        choose('Candidate evidence','all');
        const search=document.getElementById('review-search');search.value='Alarm_Alias';search.events.input();
        const alias=rows(tableNamed('Grouped signal source candidates'));
        assert.equal(alias.length,1);assert.ok(alias[0].textContent.includes('OTE · Plain'));
        assert.ok(!alias[0].childNodes[1].textContent.includes('Alarm wording'));
        """)

    def test_repeated_contacts_and_alias_fields_keep_exact_source_uses(self) -> None:
        self.run_ui(r"""
        navigate('signalcontext');choose('Signal view','candidates');
        rows(tableNamed('Grouped signal source candidates')).find(r=>r.childNodes[0].textContent==='OTE · Repeated').querySelector('button').click();
        const repeated=rows(tableNamed('Output candidate condition relationships'));
        assert.equal(repeated.length,2);assert.ok(repeated.every(r=>r.textContent.includes('XIC contact')));
        repeated[0].childNodes[3].querySelector('button').click();
        assert.ok(tableNamed('Candidate condition seed fields').textContent.includes('not a shutdown classification'));
        assert.ok(tableNamed('Candidate condition seed fields').textContent.includes('<img src=x onerror=alert(1)>'));
        assert.equal(content.querySelectorAll('img').length,0);
        tableNamed('Output candidate condition relationships').querySelector('button').click();
        assert.ok(heading.textContent.includes('Rung 4'));assert.ok(content.textContent.includes('Selected operand'));
        navigate('signalcontext');choose('Signal view','candidates');
        rows(tableNamed('Grouped signal source candidates')).find(r=>r.childNodes[0].textContent==='OTE · Plain').querySelector('button').click();
        rows(tableNamed('Output candidate condition relationships'))[0].childNodes[3].querySelector('button').click();
        assert.ok(tableNamed('Candidate condition seed fields').textContent.includes('alias declaration'));
        assert.ok(content.textContent.includes('Reader-only aliases are not attributed to a target writer'));
        """)

    def test_branch_polarity_comparisons_and_state_boundaries_remain_visible(self) -> None:
        self.run_ui(r"""
        navigate('signalcontext');choose('Signal view','candidates');
        rows(tableNamed('Grouped signal source candidates')).find(r=>r.childNodes[0].textContent==='OTE · Pump_Command').querySelector('button').click();
        const pairs=rows(tableNamed('Output candidate condition relationships'));
        assert.equal(pairs.length,2);assert.ok(pairs.some(r=>r.textContent.includes('XIO contact')));
        for(const [name,label] of [['OTE · Opaque','unknown'],['OTL · State','stored-state'],['OTE · Compared','Comparison operand']]){
          navigate('signalcontext');choose('Signal view','candidates');
          const row=rows(tableNamed('Grouped signal source candidates')).find(r=>r.childNodes[0].textContent===name);
          assert.ok(row,name);row.querySelector('button').click();
          assert.ok(content.textContent.toLowerCase().includes(label.toLowerCase()),name);
        }
        assert.equal(rows(tableNamed('Output candidate condition relationships')).length,1);
        assert.ok(tableNamed('Output upstream condition operands').textContent.includes('literal'));
        """)

    def test_incomplete_scan_filter_and_notice_and_historical_menu(self) -> None:
        self.run_ui(r"""
        navigate('signalcontext');choose('Signal view','candidates');choose('Candidate evidence','truncated');
        const candidates=rows(tableNamed('Grouped signal source candidates'));
        assert.equal(candidates.length,1);assert.ok(candidates[0].textContent.includes('Incomplete candidate scan'));
        candidates[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Candidate evidence is incomplete'));
        assert.ok(content.textContent.includes('an empty list cannot establish absence'));
        """, truncated=True)
        self.run_ui(r"""
        navigate('signalcontext');
        const select=document.getElementById('toolbar').querySelectorAll('select').find(n=>n.attributes['aria-label']==='Signal view');
        assert.ok(!select.textContent.includes('Grouped source candidates'));
        choose('Signal view','outputs');assert.ok(rows(tableNamed('Signal output guard dossiers')).length);
        """, historical=True)


if __name__ == '__main__':
    unittest.main()
