"""Reviewer navigation and feedback instructions against the shipped HTML payload."""
from __future__ import annotations

import json
import subprocess
import unittest

from plc_workbench.review_html import render_review_html
from test_access_review_ui import _DOM, _NODE
from test_review_html import ParsedPage, review_data


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI checks.')
class ReviewGuideUiTests(unittest.TestCase):
    def run_ui(self, checks: str, *, debug: bool = False) -> None:
        parsed = ParsedPage(render_review_html(review_data(), debug=debug))
        result = subprocess.run(
            [_NODE, '-e', _DOM],
            input=json.dumps({'data': json.loads(parsed.scripts[0][1]),
                              'script': parsed.scripts[1][1], 'checks': checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_guide_entry_explains_review_and_human_responses_without_development_narrative(self) -> None:
        self.run_ui(r"""
        assert.ok(!content.textContent.includes('Developer diagnostics'));
        clickText(content,'Open Review guide');
        assert.ok(heading.textContent.includes('Review guide'));
        for(const text of ['What this review is for','Checked','Needs correction','Evidence missing',
          'Not applicable','does not save review decisions','What to check by subject',
          'Write feedback that can be acted on','Terms used in the report']) {
          assert.ok(content.textContent.includes(text),text);
        }
        assert.ok(!/ChatGPT|Codex|OpenAI|artificial intelligence|sampled rungs|sample budget|frozen samples/i.test(content.textContent));
        assert.ok(content.textContent.includes('Analog input, analog output'));
        assert.ok(document.getElementById('navigation').childNodes.find(n=>n.dataset.view==='guide').attributes['aria-current']==='page');
        assert.equal(content.querySelectorAll('form').length,0);
        """)

    def test_subject_links_only_offer_available_views_in_legacy_reports(self) -> None:
        self.run_ui(r"""
        navigate('guide');
        assert.equal(content.querySelectorAll('details').filter(n=>n.className==='guide-topic').length,10);
        assert.ok(!content.querySelectorAll('button').some(n=>n.textContent==='Open PID evidence'));
        assert.ok(content.textContent.includes('runtime-dependent value'));
        clickText(content,'Open Objects');
        assert.ok(heading.textContent.includes('Objects & references'));
        navigate('guide');clickText(content,'Open Ladder');
        assert.ok(heading.textContent.includes('Ladder source'));
        """)

    def test_selected_record_feedback_keeps_identity_and_returns_to_exact_detail(self) -> None:
        self.run_ui(r"""
        navigate('ladder');clickText(content,'Rung 0');
        const previousHeading=heading.textContent;
        clickText(heading,'Prepare review feedback');
        const template=document.getElementById('review-feedback-template');
        assert.ok(template.readOnly);
        assert.ok(template.value.includes(input.data.snapshot.sha256));
        assert.ok(template.value.includes('Record ID: '+input.data.inventory.rungs[0].id));
        assert.ok(template.value.includes('Object / routine / rung: Rung 0'));
        assert.ok(template.value.includes('Supporting evidence:'));
        assert.ok(template.value.includes('Expected result or unanswered question:'));
        const original=template.value;
        clickText(content,'Select feedback template');
        assert.equal(document.activeElement,template);
        assert.equal(template.value,original);
        clickText(content,'Return to the selected record');
        assert.equal(heading.textContent,previousHeading);
        navigate('guide');
        assert.ok(document.getElementById('review-feedback-template').value.includes('Record ID: [copy'));
        """)

    def test_feedback_captures_default_sfc_content_without_leaking_it_to_declaration(self) -> None:
        self.run_ui(r"""
        navigate('sfc');clickText(content,'Sequence');
        clickText(heading,'Prepare review feedback');
        let template=document.getElementById('review-feedback-template');
        assert.ok(template.value.includes('Content ID: '+input.data.sfc.contents[0].id));
        clickText(content,'Return to the selected record');
        clickText(content,'Sequence');
        clickText(heading,'Prepare review feedback');
        template=document.getElementById('review-feedback-template');
        assert.ok(!template.value.includes('Content ID:'));
        assert.ok(template.value.includes('Record ID: '+input.data.sfc.routines[0].routine_id));
        """)

    def test_debug_report_shows_diagnostics_without_changing_reviewer_instructions(self) -> None:
        self.run_ui(r"""
        assert.ok(content.textContent.includes('Developer diagnostics'));
        assert.ok(content.textContent.includes(input.data.report_version));
        navigate('guide');
        assert.ok(content.textContent.includes('Supporting evidence'));
        assert.ok(!content.textContent.includes('Developer diagnostics'));
        """, debug=True)


if __name__ == '__main__':
    unittest.main()
