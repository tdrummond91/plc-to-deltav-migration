"""Development-only DOM checks for invented declaration-word attribution."""
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
from test_signal_authored_workflow import captured, options
from test_signal_patterns_dom import SELECT

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'public/fixtures/synthetic/signal_authored_demo.L5X').read_bytes()


@unittest.skipUnless(_NODE, 'Node is optional development tooling for DOM checks.')
class SignalAuthoredDomTests(unittest.TestCase):
    def run_ui(self, checks: str, *, truncated: bool = False) -> None:
        parts = captured(SOURCE)
        data = build_review_data(*parts[:4], **options(parts))
        if truncated:
            data['signal_context']['addresses'][0]['authored_scan_status'] = 'truncated'
        page = ParsedPage(render_review_html(data))
        result = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': data, 'script': page.scripts[1][1], 'checks': SELECT + checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_wording_filters_pagination_and_escaped_original_field(self) -> None:
        self.run_ui(r"""
        navigate('signalcontext');choose('Signal view','authored');
        assert.equal(rows(tableNamed('Signal authored wording')).length,50);
        const next=content.querySelectorAll('button').find(n=>n.attributes['aria-label']==='Next page: Signal authored wording');
        assert.ok(next);next.click();assert.equal(rows(tableNamed('Signal authored wording')).length,11);
        choose('Authored wording filter','sensor');
        const sensors=rows(tableNamed('Signal authored wording'));assert.equal(sensors.length,1);
        assert.ok(sensors[0].textContent.includes('Sensor_Enable'));
        choose('Authored wording filter','all');
        const repeated=rows(tableNamed('Signal authored wording')).find(r=>r.textContent.includes('Repeated00'));
        assert.ok(repeated);repeated.querySelector('button').click();
        const fields=rows(tableNamed('Signal authored fields'));assert.equal(fields.length,1);
        assert.ok(fields[0].textContent.includes('Root declaration context'));
        fields[0].childNodes[2].querySelector('button').click();
        assert.ok(content.textContent.includes('not an alarm classification <img src=x onerror=alert(1)>'));
        assert.equal(content.querySelectorAll('img').length,0);
        assert.equal(rows(tableNamed('Authored field operand uses')).length,2);
        """)

    def test_reader_alias_words_do_not_classify_plain_or_different_alias_output(self) -> None:
        self.run_ui(r"""
        navigate('signalcontext');choose('Signal view','outputs');
        const outputs=rows(tableNamed('Signal output guard dossiers'));
        const plain=outputs.find(r=>r.querySelector('button').textContent==='OTE · Neutral');
        assert.ok(plain);plain.querySelector('button').click();
        assert.ok(content.textContent.includes('No matching authored fields retained for this selection'));
        assert.ok(content.textContent.includes('aliases used solely by readers is excluded'));
        navigate('signalcontext');choose('Signal view','outputs');
        const alias=rows(tableNamed('Signal output guard dossiers')).find(r=>r.querySelector('button').textContent==='OTE · Valve_Command');
        assert.ok(alias);alias.querySelector('button').click();
        const fields=rows(tableNamed('Signal authored fields'));assert.equal(fields.length,2);
        assert.ok(fields.every(r=>r.textContent.includes('Valve_Command')));
        assert.ok(fields.every(r=>!r.textContent.includes('Alarm_Reader')));
        fields.find(r=>r.textContent.toLowerCase().includes('description')).childNodes[2].querySelector('button').click();
        assert.equal(rows(tableNamed('Authored field operand uses')).length,1);
        """)

    def test_source_gaps_and_truncation_are_visible_without_choosing_description(self) -> None:
        self.run_ui(r"""
        navigate('signalcontext');choose('Signal view','authored');choose('Authored wording filter','gaps');
        const gaps=rows(tableNamed('Signal authored wording'));assert.equal(gaps.length,2);
        const ambiguous=gaps.find(r=>r.textContent.includes('Ambiguous'));
        assert.ok(ambiguous);ambiguous.querySelector('button').click();
        assert.equal(rows(tableNamed('Signal authored description gaps')).length,1);
        assert.ok(content.textContent.includes('No description was selected'));
        assert.ok(content.textContent.includes('No matching authored fields retained'));
        navigate('signalcontext');choose('Signal view','authored');choose('Authored wording filter','truncated');
        assert.equal(rows(tableNamed('Signal authored wording')).length,1);
        rows(tableNamed('Signal authored wording'))[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Authored wording scan incomplete'));
        assert.ok(content.textContent.includes('an empty list cannot establish absence'));
        """, truncated=True)


if __name__ == '__main__':
    unittest.main()
