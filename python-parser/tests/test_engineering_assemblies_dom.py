"""Development-only navigation checks for wholly invented assembly evidence."""
from __future__ import annotations

from copy import deepcopy
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
from test_signal_candidates_workflow import captured, options
from test_signal_patterns_dom import SELECT

FIXTURES = Path(__file__).resolve().parents[2] / 'public/fixtures/synthetic'


@lru_cache(maxsize=4)
def review(name: str = 'signal_candidates_demo.L5X', *, historical: bool = False) -> dict:
    parts = captured((FIXTURES / name).read_bytes())
    return build_review_data(*parts[:4], **options(parts),
                            include_engineering_assemblies=not historical)


@unittest.skipUnless(_NODE, 'Node is optional development tooling for DOM checks.')
class EngineeringAssembliesDomTests(unittest.TestCase):
    def run_ui(self, checks: str, data: dict | None = None) -> None:
        payload = review() if data is None else data
        page = ParsedPage(render_review_html(payload))
        line = "const data = JSON.parse(document.getElementById('review-data').textContent);"
        script = page.scripts[1][1].replace(line, line + """
        globalThis.assemblyTestData=data;
        globalThis.assemblyBefore=JSON.stringify(data);
        """, 1)
        result = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': payload, 'script': script,
            'checks': SELECT + checks + "assert.equal(JSON.stringify(assemblyTestData),assemblyBefore);"}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_group_pagination_search_and_multirung_filter(self) -> None:
        self.run_ui(r"""
        navigate('assemblies');
        assert.equal(rows(tableNamed('Cross-rung source groups')).length,50);
        const next=content.querySelectorAll('button').find(n=>n.attributes['aria-label']==='Next page: Cross-rung source groups');
        assert.ok(next);next.click();assert.ok(rows(tableNamed('Cross-rung source groups')).length>0);
        choose('Filter Cross-rung groups','multi_rung');
        assert.ok(rows(tableNamed('Cross-rung source groups')).every(r=>Number(r.childNodes[3].textContent.replaceAll(',',''))>1));
        choose('Filter Cross-rung groups','all');
        const search=document.getElementById('review-search');search.value='Pump_Command';search.events.input();
        const found=rows(tableNamed('Cross-rung source groups'));assert.ok(found.length>0);
        assert.ok(found.some(r=>r.childNodes[0].textContent.includes('Pump_Command')));
        """)

    def test_output_guard_links_preserve_branch_and_source_evidence(self) -> None:
        self.run_ui(r"""
        navigate('assemblies');
        const search=document.getElementById('review-search');search.value='Pump_Command';search.events.input();
        rows(tableNamed('Cross-rung source groups')).find(r=>r.childNodes[0].textContent.includes('Pump_Command')).querySelector('button').click();
        assert.ok(content.textContent.includes('no active edit or execution order is selected'));
        assert.ok(content.textContent.includes('does not establish equipment identity'));
        const memberships=rows(tableNamed('Cross-rung group memberships'));
        assert.ok(memberships.some(r=>r.textContent.includes('Output guard: xio'))||memberships.some(r=>r.textContent.toLowerCase().includes('output guard: xio')));
        const open=memberships.flatMap(r=>r.querySelectorAll('button')).find(b=>b.textContent==='Output guard and source fields');
        assert.ok(open);open.click();assert.ok(heading.textContent.includes('Pump_Command'));
        assert.ok(tableNamed('Output upstream condition operands').textContent.includes('XIO'));
        """)

    def test_repeated_contacts_and_member_identity_remain_separate(self) -> None:
        self.run_ui(r"""
        navigate('assemblies');
        const search=document.getElementById('review-search');search.value='Repeated';search.events.input();
        rows(tableNamed('Cross-rung source groups')).find(r=>r.childNodes[0].textContent.includes('Repeated')).querySelector('button').click();
        const guardRows=rows(tableNamed('Cross-rung group memberships')).filter(r=>r.childNodes[1].textContent.toLowerCase().startsWith('output guard:'));
        assert.equal(guardRows.length,2);
        assert.ok(tableNamed('Cross-rung related addresses').textContent.includes('Alarm_Input'));
        """)

    def test_historical_report_has_no_new_navigation(self) -> None:
        self.run_ui(r"""
        assert.ok(!document.querySelectorAll('.nav-button').some(b=>b.dataset.view==='assemblies'));
        navigate('signalcontext');assert.ok(content.textContent.includes('Signal'));
        """, review(historical=True))

    def test_pid_calculation_and_file_dossiers_join_the_same_exact_address(self) -> None:
        self.run_ui(r"""
        function selectGroup(name){
          navigate('assemblies');const search=document.getElementById('review-search');search.value=name;search.events.input();
          const row=rows(tableNamed('Cross-rung source groups')).find(r=>r.childNodes[0].textContent===name);
          assert.ok(row,name);row.querySelector('button').click();
        }
        selectGroup('Scaled');
        const source=tableNamed('Cross-rung group memberships').textContent;
        assert.ok(source.includes('PID slot:'));assert.ok(source.includes('calculation output'));assert.ok(source.includes('file write'));
        assert.ok(source.includes('Use of PID slot address'));assert.ok(!source.includes('PID member use'));
        assert.ok(source.includes('Base access role unknown'));assert.ok(source.includes('selector or array span'));
        assert.ok(tableNamed('Cross-rung related addresses').textContent.includes('Sensor'));
        let buttons=tableNamed('Cross-rung group memberships').querySelectorAll('button');
        buttons.find(b=>b.textContent==='PID slots, members and master evidence').click();
        assert.ok(heading.textContent.includes('PID'));assert.ok(content.textContent.toLowerCase().includes('master'));
        selectGroup('Scaled');buttons=tableNamed('Cross-rung group memberships').querySelectorAll('button');
        buttons.find(b=>b.textContent.startsWith('MUL')).click();assert.ok(heading.textContent.includes('MUL'));
        selectGroup('Scaled');buttons=tableNamed('Cross-rung group memberships').querySelectorAll('button');
        buttons.find(b=>b.textContent.startsWith('AVE')).click();assert.ok(heading.textContent.includes('AVE'));
        """, review('engineering_assemblies_demo.L5X'))

    def test_sequence_state_and_alternate_edits_keep_original_context(self) -> None:
        self.run_ui(r"""
        navigate('assemblies');choose('Filter Cross-rung groups','sfc_context');
        const pump=rows(tableNamed('Cross-rung source groups')).find(r=>r.childNodes[0].textContent==='Pump');
        assert.ok(pump);pump.querySelector('button').click();
        assert.ok(content.textContent.includes('competing writers'));assert.ok(content.textContent.includes('opaque guard'));
        const rungs=rows(tableNamed('Cross-rung group source rungs'));assert.ok(rungs.length>=4);
        tableNamed('Cross-rung group memberships').querySelectorAll('button').find(b=>b.textContent==='Transition reference and step context').click();
        assert.ok(content.textContent.includes('Pump'));assert.ok(content.textContent.toLowerCase().includes('transition'));
        navigate('assemblies');choose('Filter Cross-rung groups','stateful_objects');
        rows(tableNamed('Cross-rung source groups')).find(r=>r.childNodes[0].textContent==='Timer').querySelector('button').click();
        assert.ok(content.textContent.includes('stateful guard'));
        tableNamed('Cross-rung group memberships').querySelectorAll('button').find(b=>b.textContent==='Timer, counter or reset occurrence').click();
        assert.ok(content.textContent.toLowerCase().includes('reset'));
        navigate('assemblies');choose('Filter Cross-rung groups','stateful_objects');
        rows(tableNamed('Cross-rung source groups')).find(r=>r.childNodes[0].textContent==='Timer.DN').querySelector('button').click();
        tableNamed('Cross-rung group memberships').querySelectorAll('button').find(b=>b.textContent==='Stored-state member context').click();
        assert.ok(heading.textContent.includes('Timer.DN'));assert.ok(content.textContent.toLowerCase().includes('timer'));
        """, review('engineering_assemblies_demo.L5X'))

    def test_whole_members_and_missing_addresses_are_not_silently_merged(self) -> None:
        self.run_ui(r"""
        navigate('assemblies');
        const names=rows(tableNamed('Cross-rung source groups')).map(r=>r.childNodes[0].textContent);
        assert.ok(names.includes('Loop'));assert.ok(names.includes('Loop.SP'));
        assert.ok(names.includes('M:O.Data'));assert.ok(names.includes('M:O.Data.1'));
        assert.ok(!names.includes('Foreign'));
        const caveats=tableNamed('Assembly source caveats').textContent;
        assert.ok(caveats.includes('missing address'));assert.ok(caveats.includes('ineligible occurrence'));
        assert.ok(caveats.includes('communication semantics unmodeled'));
        """, review('engineering_assemblies_demo.L5X'))

    def test_source_text_stays_inert_in_group_search_and_details(self) -> None:
        data = deepcopy(review('engineering_assemblies_demo.L5X'))
        entity = next(e for e in data['inventory']['entities'] if e['name'] == 'Scaled')
        entity['name'] = '<img src=x onerror=alert(1)>'
        self.run_ui(r"""
        navigate('assemblies');
        const row=rows(tableNamed('Cross-rung source groups')).find(r=>r.childNodes[0].textContent.includes('<img src=x'));
        assert.ok(row);row.querySelector('button').click();assert.ok(heading.textContent.includes('<img src=x'));
        assert.equal(content.querySelectorAll('img').length,0);assert.equal(heading.querySelectorAll('img').length,0);
        """, data)

    def test_signal_expression_memberships_open_the_exact_calculation_reference(self) -> None:
        source = (FIXTURES / 'engineering_assemblies_demo.L5X').read_bytes()
        extra = (b'<Rung Number="11"><Text>GRT(Scaled,0)OTE(Pump);</Text></Rung>'
                 b'<Rung Number="12"><Text>CPT(Demand,Scaled+Scaled);</Text></Rung>')
        source = source.replace(b'</RLLContent>', extra + b'</RLLContent>', 1)
        parts = captured(source)
        data = build_review_data(*parts[:4], **options(parts), include_engineering_assemblies=True)
        self.run_ui(r"""
        navigate('assemblies');const search=document.getElementById('review-search');search.value='Scaled';search.events.input();
        rows(tableNamed('Cross-rung source groups')).find(r=>r.childNodes[0].textContent==='Scaled').querySelector('button').click();
        const expressions=rows(tableNamed('Cross-rung group memberships')).filter(r=>r.childNodes[0].textContent==='Boolean signals'&&r.childNodes[1].textContent==='expression read');
        assert.equal(expressions.length,2);
        expressions[1].querySelectorAll('button').find(b=>b.textContent==='Expression reference').click();
        assert.ok(heading.textContent.includes('CPT'));assert.ok(content.textContent.includes('Scaled'));
        """, data)

    def test_truncated_group_is_visible_and_does_not_claim_absence(self) -> None:
        data = deepcopy(review())
        group = data['engineering_assemblies']['groups'][0]
        group['scan_status'] = 'truncated'
        self.run_ui(r"""
        navigate('assemblies');choose('Filter Cross-rung groups','truncated');
        const selected=rows(tableNamed('Cross-rung source groups'));assert.equal(selected.length,1);
        assert.ok(selected[0].textContent.includes('Incomplete grouping scan'));selected[0].querySelector('button').click();
        assert.ok(content.textContent.includes('an absent link does not establish absence'));
        """, data)

    def test_selected_related_address_display_has_explicit_bounds(self) -> None:
        data = deepcopy(review('engineering_assemblies_demo.L5X'))
        assembly = data['engineering_assemblies']
        group = assembly['groups'][0]
        membership = next(m for m in assembly['memberships'] if m['id'] in group['membership_ids'])
        for number in range(510):
            duplicate = dict(membership, id=f'ui-bound-{number}',
                             related_address_id=f'other-ui-address-{number}')
            assembly['memberships'].append(duplicate)
            group['membership_ids'].append(duplicate['id'])
        self.run_ui(r"""
        navigate('assemblies');rows(tableNamed('Cross-rung source groups'))[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Related-address display truncated'));
        assert.ok(content.textContent.includes('500 links'));
        assert.equal(rows(tableNamed('Cross-rung related addresses')).length,50);
        """, data)


if __name__ == '__main__':
    unittest.main()
