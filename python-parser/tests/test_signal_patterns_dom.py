"""Development-only report navigation using invented Boolean patterns and Node."""
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
from test_signal_patterns_workflow import captured, options

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'public/fixtures/synthetic/signal_patterns_demo.L5X').read_bytes()
SELECT = r"""
function choose(label,value){
  const s=document.getElementById('toolbar').querySelectorAll('select').find(n=>n.attributes['aria-label']===label);
  assert.ok(s,label);s.value=value;s.events.change();
}
"""


@unittest.skipUnless(_NODE, 'Node is optional development tooling for DOM checks.')
class SignalPatternsDomTests(unittest.TestCase):
    def run_ui(self, checks: str, *, truncated: bool = False) -> None:
        parts = captured(SOURCE)
        data = build_review_data(*parts[:4], **options(parts))
        if truncated:
            # Exercise the rendered state independently of the analyzer budget.
            data['signal_context']['outputs'][0]['guard_patterns']['traversal_status'] = 'truncated'
        page = ParsedPage(render_review_html(data))
        result = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': data, 'script': page.scripts[1][1], 'checks': SELECT + checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_patterns_pagination_self_contact_and_source_navigation(self) -> None:
        self.run_ui(r"""
        navigate('signalcontext');choose('Signal view','patterns');
        assert.equal(rows(tableNamed('Signal contact pattern findings')).length,50);
        const next=content.querySelectorAll('button').find(n=>n.attributes['aria-label']==='Next page: Signal contact pattern findings');
        assert.ok(next);next.click();
        assert.equal(rows(tableNamed('Signal contact pattern findings')).length,10);
        choose('Pattern evidence','selfxio');
        const selected=rows(tableNamed('Signal contact pattern findings'));
        assert.equal(selected.length,1);
        selected[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('Command'));
        assert.ok(content.textContent.includes('No qualified XIC self contacts retained'));
        const contacts=rows(tableNamed('Self XIO contact evidence'));
        assert.equal(contacts.length,1);assert.ok(contacts[0].textContent.includes('XIO contact'));
        assert.ok(content.textContent.includes('does not establish a seal-in circuit'));
        contacts[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('Rung 4'));
        assert.ok(content.textContent.includes('Selected operand'));
        assert.equal(content.querySelectorAll('img').length,0);
        """)

    def test_timer_bypass_and_set_reset_edit_groups_keep_evidence_separate(self) -> None:
        self.run_ui(r"""
        navigate('signalcontext');choose('Signal view','patterns');choose('Pattern evidence','timer');
        const timed=rows(tableNamed('Signal contact pattern findings'));
        assert.equal(timed.length,2);timed[0].querySelector('button').click();
        const contacts=rows(tableNamed('Timer contacts in output guard'));
        assert.equal(contacts.length,1);assert.ok(contacts[0].textContent.includes('DN'));
        assert.ok(content.textContent.includes('Bypass'));
        assert.ok(content.textContent.includes('does not determine timing'));
        contacts[0].childNodes[3].querySelector('button').click();
        assert.ok(heading.textContent.includes('Delay'));
        assert.ok(content.textContent.includes('Reset occurrences for this control'));
        navigate('signalcontext');choose('Signal view','setreset');
        const pairs=rows(tableNamed('Same-content set reset addresses'));
        assert.equal(pairs.length,1);assert.ok(pairs[0].textContent.includes('Latched'));
        pairs[0].querySelector('button').click();
        assert.equal(rows(tableNamed('Signal coil source groups')).length,1);
        assert.equal(rows(tableNamed('Selected content coil writers')).length,3);
        assert.ok(content.textContent.includes('Both OTL and OTU captured'));
        navigate('signalcontext');choose('Signal view','addresses');
        const split=rows(tableNamed('Exact signal address dossiers')).find(r=>r.textContent.includes('AcrossEdits'));
        assert.ok(split);split.querySelector('button').click();
        const groups=rows(tableNamed('Signal coil source groups'));
        assert.equal(groups.length,2);
        assert.ok(groups.every(r=>r.textContent.includes('No same-content pair')));
        assert.equal(rows(tableNamed('Selected content coil writers')).length,1);
        groups[1].querySelector('button').click();
        assert.ok(content.textContent.includes('Pending'));
        assert.ok(rows(tableNamed('Selected content coil writers'))[0].textContent.includes('OTU'));
        """)

    def test_truncated_pattern_scan_is_filterable_and_explicit(self) -> None:
        self.run_ui(r"""
        navigate('signalcontext');choose('Signal view','patterns');choose('Pattern evidence','truncated');
        const findings=rows(tableNamed('Signal contact pattern findings'));
        assert.equal(findings.length,1);assert.ok(findings[0].textContent.includes('Pattern scan truncated'));
        findings[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Pattern evidence is incomplete'));
        assert.ok(content.textContent.includes('empty lists cannot establish that a contact is absent'));
        """, truncated=True)


if __name__ == '__main__':
    unittest.main()
