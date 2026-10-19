"""Development-only navigation of explicit alarm evidence from invented XML."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest

from plc_workbench.alarm_evidence import analyze_alarm_evidence
from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_review_html import ParsedPage
from test_signal_authored_workflow import captured, options
from test_signal_patterns_dom import SELECT

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(_NODE, 'Node is optional development tooling for DOM checks.')
class AlarmEvidenceDomTests(unittest.TestCase):
    def run_ui(self, checks: str, *, empty: bool = False) -> None:
        source = (b'<RSLogix5000Content><Controller Name="Empty"/></RSLogix5000Content>'
                  if empty else (ROOT / 'public/fixtures/synthetic/alarm_evidence_demo.L5X').read_bytes())
        parts = captured(source)
        alarm = analyze_alarm_evidence(parts[0], parts[1], parts[5])
        data = build_review_data(*parts[:4], **options(parts), alarm_evidence=alarm)
        page = ParsedPage(render_review_html(data))
        result = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': data, 'script': page.scripts[1][1], 'checks': SELECT + checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_filters_pagination_and_literal_message_navigation(self) -> None:
        self.run_ui(r"""
        navigate('alarmevidence');
        assert.equal(rows(tableNamed('Alarm source records')).length,50);
        const next=content.querySelectorAll('button').find(n=>n.attributes['aria-label']==='Next page: Alarm source records');
        assert.ok(next);next.click();assert.ok(rows(tableNamed('Alarm source records')).length>0);
        choose('Filter Alarm source evidence','conditions');
        assert.ok(rows(tableNamed('Alarm source records')).every(r=>r.textContent.includes('AlarmCondition')));
        choose('Filter Alarm source evidence','messages');
        const query=document.getElementById('review-search');query.value='<img';query.events.input();
        const messages=rows(tableNamed('Alarm source records'));assert.ok(messages.length>0);
        messages[0].querySelector('button').click();
        assert.ok(content.textContent.includes('<img'));assert.equal(content.querySelectorAll('img').length,0);
        assert.ok(content.textContent.includes('Direct source text'));
        const parent=content.querySelectorAll('button').find(n=>n.textContent.startsWith('Message'));
        assert.ok(parent);parent.click();assert.ok(tableNamed('Child alarm source records'));
        """)

    def test_source_gaps_templates_and_declaration_links(self) -> None:
        self.run_ui(r"""
        navigate('alarmevidence');choose('Filter Alarm source evidence','gaps');
        const gaps=rows(tableNamed('Alarm source records'));assert.ok(gaps.length>0);
        assert.ok(gaps.every(r=>r.textContent.includes('source gap')));
        gaps[0].querySelector('button').click();assert.ok(content.textContent.includes('Source gaps'));
        navigate('alarmevidence');choose('Filter Alarm source evidence','definitions');
        assert.ok(rows(tableNamed('Alarm source records')).length>0);
        assert.ok(rows(tableNamed('Alarm source records')).some(r=>r.textContent.includes('0012.50')));
        assert.ok(content.textContent.includes('template expansion'));
        choose('Filter Alarm source evidence','settings');
        const query=document.getElementById('review-search');query.value='HMICommand';query.events.input();
        assert.ok(rows(tableNamed('Alarm source records')).some(r=>r.textContent.includes('HMICommand')));
        navigate('alarmevidence');choose('Filter Alarm source evidence','declarations');
        const declaration=rows(tableNamed('Alarm source records'))[0];assert.ok(declaration);
        declaration.querySelector('button').click();assert.ok(content.textContent.includes('Stored representations'));
        const owner=content.querySelectorAll('button').find(n=>!['Back','Previous','Next'].includes(n.textContent));
        assert.ok(owner);owner.click();assert.ok(heading.textContent.includes('SOURCE OBJECT'));
        assert.ok(tableNamed('Object alarm evidence'));
        """)

    def test_empty_population_does_not_claim_no_alarms(self) -> None:
        self.run_ui(r"""
        navigate('alarmevidence');
        assert.ok(content.textContent.includes('zero count does not rule out'));
        assert.ok(content.textContent.includes('No matching alarm source evidence'));
        assert.ok(content.textContent.includes('Typed declarations'));
        """, empty=True)


if __name__ == '__main__':
    unittest.main()
