"""Bounded offline entry links select captured evidence without changing history."""
from __future__ import annotations

from functools import lru_cache
import json
import subprocess
import unittest
from urllib.parse import quote

from plc_workbench.review_html import render_review_html
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_review_html import ParsedPage, review_data
from test_rung_analysis_review_ui import review as engineering_review


_LINK_SETUP = r"""
let fragment=input.fragment;
const windowEvents={};
if(!input.omitLocation) {
  window.location={};
  Object.defineProperty(window.location,'hash',{
    get(){return fragment;},set(){throw new Error('Report must not rewrite the fragment');}
  });
}
if(!input.omitEvents)window.addEventListener=(name,callback)=>{windowEvents[name]=callback;};
if(input.omitScroll)delete window.scrollTo;
window.history={pushState(){throw new Error('Report must not rewrite browser history');},
  replaceState(){throw new Error('Report must not rewrite browser history');}};
function setFragment(value){fragment=value;windowEvents.hashchange?.({});}
"""


@lru_cache(maxsize=2)
def rendered(engineering: bool = False) -> tuple[dict, str]:
    model = engineering_review(tags=(
        '<Tag Name="Stored" DataType="DINT"><Data Format="Decorated">'
        '<DataValue DataType="DINT" Radix="Decimal" Value="3"/></Data></Tag>'
    )) if engineering else review_data()
    page = ParsedPage(render_review_html(model))
    return json.loads(page.scripts[0][1]), page.scripts[1][1]


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI behavior checks.')
class ReviewLinkTests(unittest.TestCase):
    def run_ui(self, fragment: str, checks: str, *, engineering: bool = False,
               omit_location: bool = False, omit_events: bool = False,
               omit_scroll: bool = False) -> None:
        data, script = rendered(engineering)
        invocation = "vm.runInThisContext(input.script,{filename:'report.js'});"
        dom = DOM.replace(invocation, _LINK_SETUP + '\n' + invocation)
        self.assertNotEqual(dom, DOM)
        process = subprocess.run(
            [_NODE, '-e', dom], input=json.dumps({
                'data': data, 'script': script, 'checks': checks, 'fragment': fragment,
                'omitLocation': omit_location, 'omitEvents': omit_events,
                'omitScroll': omit_scroll,
            }), text=True, encoding='utf-8', capture_output=True, timeout=30, check=False,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_direct_guide_and_available_engineering_view(self) -> None:
        self.run_ui('#view=guide', r"""
        assert.ok(heading.textContent.includes('Review guide'));
        assert.ok(content.textContent.includes('What this review is for'));
        assert.equal(fragment,'#view=guide');
        navigate('objects');
        assert.ok(heading.textContent.includes('Objects & references'));
        assert.equal(fragment,'#view=guide');
        """)
        self.run_ui('#view=engineering', r"""
        assert.ok(heading.textContent.includes('Engineering analysis'));
        assert.equal(rows(tableNamed('Engineering rung analysis')).length,8);
        """, engineering=True)

    def test_known_rung_link_keeps_back_destination_and_contextual_feedback(self) -> None:
        data, _ = rendered(True)
        source_id = data['inventory']['rungs'][0]['id']
        self.run_ui(f'#view=engineering&source={quote(source_id, safe="")}', r"""
        assert.ok(heading.textContent.includes('Rung 0'));
        assert.ok(content.textContent.includes('XIC(A)OTE(B);'));
        clickText(heading,'Prepare review feedback');
        assert.ok(document.getElementById('review-feedback-template').value.includes(input.data.inventory.rungs[0].id));
        clickText(content,'Return to the selected record');
        assert.ok(heading.textContent.includes('Rung 0'));
        clickText(heading,'\u2190 Back to previous view');
        assert.ok(heading.textContent.includes('Engineering analysis'));
        assert.equal(fragment,input.fragment);
        """, engineering=True)

    def test_captured_source_maps_are_routed_through_existing_detail_navigation(self) -> None:
        data, _ = rendered()
        cases = (
            (data['inventory']['rungs'][0]['id'], 'Rung 0'),
            (data['references']['operands'][0]['id'], 'Rung 0'),
            (data['inventory']['rungs'][0]['instructions'][0]['id'], 'Rung 0'),
            (next(row['id'] for row in data['inventory']['entities'] if row['name'] == 'A'), 'A'),
            (data['sfc']['elements'][0]['id'], 'SFC ELEMENT'),
            (data['sfc']['contents'][0]['id'], 'Sequence'),
        )
        for source_id, expected in cases:
            with self.subTest(source=source_id):
                self.run_ui(f'#view=guide&source={quote(source_id, safe="")}', f"""
                assert.ok(heading.textContent.includes({json.dumps(expected)}),heading.textContent);
                clickText(heading,'\u2190 Back to previous view');
                assert.ok(heading.textContent.includes('Review guide'));
                """)

    def test_unknown_malformed_repeated_or_oversized_links_leave_initial_overview(self) -> None:
        bad_links = (
            '', '#main', '#guide', '#view=engineering', '#view=unknown', '#view=constructor',
            '#view=toString', '#view=', '#view=guide&source=', '#view=guide&source=missing',
            '#view=guide&view=ladder', '#view=guide&source=a&source=b',
            '#view=guide&extra=value', '#view=guide&source=a=b', '#view=guide&',
            '#view=guide&%76iew=ladder', '#view=%', '#view=guide&source=%GG',
            '#view=guide&source=%C3%28', '#view=guide&source=%00',
            '#view=guide&source=' + 'x' * 2048,
            '#view=guide&source=' + '%41' * 257,
            '#view=guide%26source%3Dmissing', '#view=guide+objects',
        )
        for fragment in bad_links:
            with self.subTest(fragment=fragment[:100]):
                self.run_ui(fragment, r"""
                assert.ok(heading.textContent.includes('Review overview'),heading.textContent);
                assert.equal(fragment,input.fragment);
                """)

    def test_saved_tag_source_links_select_captured_representation_and_element(self) -> None:
        data, _ = rendered(True)
        for record, expected in ((data['tag_data']['contents'][0], 'STORED TAG DATA'),
                                 (data['tag_data']['elements'][0], 'STORED DATA ELEMENT')):
            with self.subTest(source=record['id']):
                self.run_ui(f'#view=tagdata&source={quote(record["id"], safe="")}', f"""
                assert.ok(heading.textContent.includes({json.dumps(expected)}),heading.textContent);
                clickText(heading,'\u2190 Back to previous view');
                assert.ok(heading.textContent.includes('Stored tag data'));
                """, engineering=True)

    def test_hashchange_navigates_and_ignored_anchor_keeps_current_detail_and_back(self) -> None:
        self.run_ui('#view=guide', r"""
        assert.equal(typeof windowEvents.hashchange,'function');
        setFragment('#view=ladder&source='+encodeURIComponent(input.data.inventory.rungs[0].id));
        assert.ok(heading.textContent.includes('Rung 0'));
        const detailBefore=heading.textContent, evidenceBefore=content.textContent;
        for(const ignored of ['#main','#view=missing','#view=guide&source=missing','#view=%','#view=guide&view=ladder']) {
          setFragment(ignored);
          assert.equal(heading.textContent,detailBefore);
          assert.equal(content.textContent,evidenceBefore);
        }
        clickText(heading,'\u2190 Back to previous view');
        assert.ok(heading.textContent.includes('Ladder source'));
        setFragment('#view=objects');
        assert.ok(heading.textContent.includes('Objects & references'));
        """)

    def test_missing_optional_window_apis_preserve_report_and_available_entry_links(self) -> None:
        self.run_ui('#view=guide', r"""
        assert.ok(heading.textContent.includes('Review overview'));
        navigate('guide');assert.ok(heading.textContent.includes('Review guide'));
        """, omit_location=True, omit_events=True, omit_scroll=True)
        self.run_ui('#view=guide', r"""
        assert.ok(heading.textContent.includes('Review guide'));
        navigate('ladder');clickText(content,'Rung 0');
        clickText(heading,'\u2190 Back to previous view');assert.ok(heading.textContent.includes('Ladder source'));
        """, omit_events=True, omit_scroll=True)


if __name__ == '__main__':
    unittest.main()
