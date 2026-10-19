"""Invented source navigation for supplemental addresses and MSG context."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import subprocess
import unittest

from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from plc_workbench.source_reuse import source_reuse_scope
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_review_html import ParsedPage
from test_signal_candidates_workflow import captured, options
from test_signal_patterns_dom import SELECT

SOURCE = Path(__file__).resolve().parents[2] / 'public/fixtures/synthetic/residual_source_demo.L5X'


@lru_cache(maxsize=2)
def review(*, historical: bool = False) -> dict:
    with source_reuse_scope():
        parts = captured(SOURCE.read_bytes())
        return build_review_data(*parts[:4], **options(parts), include_engineering_assemblies=True,
            engineering_assemblies_schema_version=1 if historical else 2,
            include_communication_context=not historical)


@unittest.skipUnless(_NODE, 'Node is optional development tooling for DOM checks.')
class ResidualSourceDomTests(unittest.TestCase):
    def run_ui(self, checks: str, payload: dict | None = None) -> None:
        data = review() if payload is None else payload
        page = ParsedPage(render_review_html(data))
        marker = "const data = JSON.parse(document.getElementById('review-data').textContent);"
        script = page.scripts[1][1].replace(marker, marker +
            'globalThis.savedData=data;globalThis.before=JSON.stringify(data);', 1)
        result = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': data, 'script': script, 'checks': SELECT + checks +
            'assert.equal(JSON.stringify(savedData),before);'}), text=True,
            encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_supplemental_file_and_sequence_anchors_open_without_legacy_links(self) -> None:
        self.run_ui(r"""
        for(const [name,evidence] of [['AverageOnly','AVE'],['SequenceOnly','Transition reference']]){
          navigate('assemblies');const search=document.getElementById('review-search');search.value=name;search.events.input();
          rows(tableNamed('Cross-rung source groups')).find(r=>r.childNodes[0].textContent===name).querySelector('button').click();
          assert.ok(heading.textContent.includes(name));assert.ok(content.textContent.includes('Supplemental exact address'));
          assert.ok(!content.querySelectorAll('button').some(b=>b.textContent==='All captured uses of this exact address'));
          assert.ok(rows(tableNamed('Cross-rung group memberships')).every(r=>r.childNodes[2].querySelector('button')));
          tableNamed('Cross-rung group memberships').querySelectorAll('button').find(b=>b.textContent.startsWith(evidence)).click();
          assert.ok(content.textContent.length>0);
        }
        """)

    def test_msg_alias_repeats_parameters_remote_collision_and_source_navigation(self) -> None:
        self.run_ui(r"""
        navigate('communication');assert.equal(rows(tableNamed('Communication occurrences')).length,6);
        const row=rows(tableNamed('Communication occurrences')).find(r=>r.textContent.includes('MessageAlias'));
        row.querySelector('button').click();
        assert.ok(content.textContent.includes('invented-peer-route'));assert.ok(content.textContent.includes('Outgoing'));
        const endpoints=rows(tableNamed('Communication local endpoint candidates'));
        assert.equal(endpoints.length,1);assert.ok(endpoints[0].textContent.includes('LocalAlias'));
        assert.ok(endpoints[0].textContent.includes('Incoming'));assert.ok(endpoints[0].textContent.includes('[2]'));
        assert.ok(!endpoints[0].textContent.includes('Outgoing'));
        endpoints[0].querySelector('button').click();assert.ok(heading.textContent.includes('Incoming'));
        navigate('ladder');rows(tableNamed('Ladder rungs')).find(r=>r.childNodes[0].textContent==='Rung 1').querySelector('button').click();
        assert.equal(rows(tableNamed('Rung MSG occurrences')).length,2);
        """)

    def test_gap_filter_and_multiple_representations_remain_distinct(self) -> None:
        self.run_ui(r"""
        navigate('communication');choose('Filter Communication context','gaps');
        const selected=rows(tableNamed('Communication occurrences'));assert.equal(selected.length,3);
        assert.ok(selected.some(r=>r.textContent.includes('NoParameters')));
        selected.find(r=>r.textContent.includes('AmbiguousMessage')).querySelector('button').click();
        const tables=content.querySelectorAll('table').filter(t=>t.querySelector('caption')?.textContent==='Communication local endpoint candidates');
        assert.equal(tables.length,2);assert.ok(content.textContent.includes('no effective configuration is selected'));
        assert.ok(tables.some(t=>t.textContent.includes('Incoming')));assert.ok(tables.some(t=>t.textContent.includes('Outgoing')));
        """)

    def test_produced_consumed_metadata_links_to_source_declaration(self) -> None:
        self.run_ui(r"""
        navigate('communication');const records=rows(tableNamed('Produced and consumed metadata'));
        assert.equal(records.length,2);assert.ok(records.some(r=>r.textContent.includes('invented-map')));
        records.find(r=>r.textContent.includes('ConsumedValue')).querySelector('button').click();
        assert.ok(heading.textContent.includes('ConsumedValue'));assert.ok(tableNamed('Object communication metadata').textContent.includes('invented-remote-tag'));
        """)

    def test_residual_inventory_retains_opaque_rules_and_missing_body(self) -> None:
        self.run_ui(r"""
        navigate('residuals');assert.ok(content.textContent.includes('Parser investigation'));
        assert.ok(tableNamed('Residual routine bodies').textContent.includes('MissingBody'));
        choose('Filter Unresolved analysis','catalogue');const selected=rows(tableNamed('Unresolved instruction analysis'));
        const mystery=selected.find(r=>r.textContent.includes('MYSTERY'));assert.ok(mystery);
        mystery.querySelector('button').click();assert.ok(content.textContent.includes('MYSTERY'));
        navigate('residuals');const search=document.getElementById('review-search');search.value='MSG';search.events.input();
        assert.equal(rows(tableNamed('Unresolved instruction analysis')).length,6);
        assert.ok(tableNamed('Unresolved instruction analysis').textContent.includes('MSG stored parameters'));
        """)

    def test_historical_report_keeps_previous_navigation(self) -> None:
        self.run_ui(r"""
        assert.ok(!document.querySelectorAll('.nav-button').some(b=>['communication','residuals'].includes(b.dataset.view)));
        navigate('assemblies');assert.ok(tableNamed('Assembly source caveats').textContent.includes('missing address'));
        """, review(historical=True))

    def test_authored_fields_and_supplemental_names_stay_inert(self) -> None:
        data = deepcopy(review())
        parameter = data['communication_context']['parameters'][0]
        parameter['attributes']['ConnectionPath'] = '<img src=x onerror=alert(1)>'
        data['communication_context']['tag_connections'][0]['direct_text'] = '<svg onload=alert(1)>'
        next(e for e in data['inventory']['entities'] if e['name'] == 'SequenceOnly')['name'] = '<script>alert(1)</script>'
        self.run_ui(r"""
        navigate('communication');assert.ok(tableNamed('Produced and consumed metadata').textContent.includes('<svg'));
        assert.equal(content.querySelectorAll('svg').length,0);
        rows(tableNamed('Communication occurrences')).find(r=>r.textContent.includes('MessageAlias')).querySelector('button').click();
        assert.ok(content.textContent.includes('<img src=x'));assert.equal(content.querySelectorAll('img').length,0);
        navigate('assemblies');rows(tableNamed('Cross-rung source groups')).find(r=>r.textContent.includes('<script>')).querySelector('button').click();
        assert.ok(heading.textContent.includes('<script>'));assert.equal(heading.querySelectorAll('script').length,0);
        """, data)


if __name__ == '__main__':
    unittest.main()
