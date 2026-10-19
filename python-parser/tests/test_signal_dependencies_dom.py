"""Development-only source trail behavior on wholly invented ladder graphs."""
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
from test_signal_dependencies_workflow import captured, options
from test_signal_patterns_dom import SELECT

SOURCE = (Path(__file__).resolve().parents[2] /
          'public/fixtures/synthetic/signal_dependencies_demo.L5X').read_bytes()
SELECT_TRAIL = r"""
function startTrail(name,direction){
  navigate('signalcontext');choose('Signal view','trails');
  const search=document.getElementById('review-search');search.value=name;search.events.input();
  const row=rows(tableNamed('Signal trail starting points')).find(r=>r.childNodes[0].textContent===name);
  assert.ok(row,name);row.querySelector('button').click();
  const label=direction==='upstream'?'Trace upstream writers':'Trace downstream guards';
  const action=content.querySelectorAll('button').find(n=>n.textContent===label);
  assert.ok(action,label);action.click();
}
"""


@unittest.skipUnless(_NODE, 'Node is optional development tooling for DOM checks.')
class SignalDependenciesDomTests(unittest.TestCase):
    def run_ui(self, checks: str, *, incomplete: bool = False) -> None:
        parts = captured(SOURCE)
        data = build_review_data(*parts[:4], **options(parts))
        if incomplete:
            data['signal_context']['outputs'][0]['guard_dependencies']['traversal_status'] = 'truncated'
        page = ParsedPage(render_review_html(data))
        result = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': data, 'script': page.scripts[1][1],
            'checks': SELECT + SELECT_TRAIL + checks}), text=True, encoding='utf-8',
            capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_three_rung_chain_retains_polarity_and_stops_at_other_source_contents(self) -> None:
        self.run_ui(r"""
        startTrail('Alarm_Input','downstream');
        const steps=rows(tableNamed('Signal source trail steps'));
        assert.ok(steps.some(r=>r.textContent.includes('Pump_Command')&&r.textContent.includes('XIO')),tableNamed('Signal source trail steps').textContent);
        assert.ok(steps.some(r=>r.textContent.includes('Final_Output')&&r.childNodes[0].textContent==='3'));
        assert.equal(steps.filter(r=>r.textContent.includes('Different routine or source edit')).length,2);
        assert.ok(!content.textContent.includes('Source trail limit reached'));
        startTrail('Final_Output','upstream');
        assert.ok(rows(tableNamed('Signal source trail steps')).some(r=>r.textContent.includes('Alarm_Input')));
        assert.ok(content.textContent.includes('No captured coil writer'));
        assert.equal(content.querySelectorAll('img').length,0);
        """)

    def test_shared_branch_is_not_called_a_cycle_and_true_cycle_terminates(self) -> None:
        self.run_ui(r"""
        startTrail('Sensor_Input','downstream');
        assert.ok(content.textContent.includes('Already reached through another source branch'));
        assert.ok(!content.textContent.includes('Cycle in captured source'));
        assert.ok(content.textContent.includes('Shared_Final'));
        startTrail('Cycle_A','downstream');
        assert.ok(content.textContent.includes('Cycle in captured source'));
        assert.ok(rows(tableNamed('Signal source trail steps')).length<5);
        """)

    def test_uncertain_transfers_and_competing_writers_are_visible_boundaries(self) -> None:
        self.run_ui(r"""
        for(const [name,boundary] of [
          ['Multi_Input','Competing coil writers'],['State_Input','Contains stored-state condition'],
          ['Set_Input','Set / reset state boundary'],['Gap_Input','Condition binding gaps'],
          ['Reading','Comparison operand boundary'],['Other_Write','Other writer or stored-state boundary'],
          ['Opaque_Input','Contains unknown transfer']]){
          startTrail(name,'downstream');
          assert.ok(rows(tableNamed('Signal source trail steps')).some(r=>r.textContent.includes(boundary)),name+' '+tableNamed('Signal source trail steps').textContent);
        }
        startTrail('Multi_Input','downstream');
        assert.ok(!tableNamed('Signal source trail steps').textContent.includes('Beyond_Multi'));
        """)

    def test_limits_paging_wording_filters_and_partial_reverse_index(self) -> None:
        self.run_ui(r"""
        startTrail('Deep00','downstream');
        assert.ok(content.textContent.includes('Source trail limit reached'));
        assert.ok(content.textContent.includes('Depth limit; further source not inspected'));
        assert.ok(!tableNamed('Signal source trail steps').textContent.includes('Deep09'));
        startTrail('Fan_Input','downstream');
        assert.equal(rows(tableNamed('Signal source trail steps')).length,50);
        const next=content.querySelectorAll('button').find(n=>n.attributes['aria-label']==='Next page: Signal source trail steps');
        assert.ok(next);next.click();assert.equal(rows(tableNamed('Signal source trail steps')).length,50);
        navigate('signalcontext');choose('Signal view','trails');
        const search=document.getElementById('review-search');search.value='';search.events.input();
        choose('Trail starting points','alarm');
        assert.equal(rows(tableNamed('Signal trail starting points')).length,1);
        assert.ok(tableNamed('Signal trail starting points').textContent.includes('Alarm_Input'));
        startTrail('Alarm_Input','downstream');
        assert.ok(content.textContent.includes('Dependency index is incomplete'));
        assert.ok(content.textContent.includes('empty downstream list cannot establish absence'));
        assert.ok(tableNamed('Signal source trail steps').textContent.includes('Incomplete guard dependency scan'));
        """, incomplete=True)


if __name__ == '__main__':
    unittest.main()
