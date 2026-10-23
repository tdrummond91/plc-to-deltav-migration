"""Shared, source-qualified ladder drawings in standalone and saved reports."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from plc_workbench.project_store import ProjectError
from plc_workbench.access import analyze_access
from plc_workbench.references import analyze_references
from plc_workbench.review import build_review_data
from plc_workbench.review_html import ReviewHtmlError, render_review_html
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.storage import save_run
from plc_workbench.workspace_classification import _qualify_source
from plc_workbench.workspace_report import refresh_report
from test_access_review_ui import _DOM, _NODE
from test_review import fixture
from test_review_html import ParsedPage


SHARED = Path(__file__).parents[1] / 'src/plc_workbench/workspace_assets'


def captured(text: str = 'XIC(A)[GEQ(Pressure,90),NEQ(Mode,0)]OTE(B);',
             *, foreign_text: bool = False) -> tuple[bytes, dict]:
    args = fixture((text,))
    if foreign_text:
        raw = args[0].data.replace(b'<Text>', b'<Text xmlns="urn:invented-extension">')
        snapshot = snapshot_from_bytes(raw)
        inventory = analyze_snapshot(snapshot)
        args = (snapshot, inventory, analyze_references(inventory),
                analyze_sfc_structure(snapshot, inventory))
    return args[0].data, build_review_data(*args)


def display_context(page: ParsedPage) -> dict:
    match = re.search(r'const REVIEW_LADDER = Object.freeze\(([^\n]+)\);', page.scripts[1][1])
    return json.loads(match.group(1))


class ReviewLadderAssetsTests(unittest.TestCase):
    def test_same_shared_renderer_is_embedded_without_external_assets_or_payload_changes(self):
        source, data = captured()
        page = ParsedPage(render_review_html(data, source=source))
        ordinary = ParsedPage(render_review_html(data))
        self.assertEqual(page.scripts[0], ordinary.scripts[0])
        self.assertEqual(len(page.scripts), 2)
        for name in ('source-colors.js', 'rung-explanation.js', 'instruction-help-content.js',
                     'variable-help-content.js', 'instruction-help.js', 'ladder-diagram.js'):
            self.assertIn((SHARED / name).read_text(encoding='utf-8'), page.scripts[1][1])
        for name in ('source-colors.css', 'ladder-diagram.css', 'instruction-help.css'):
            self.assertIn((SHARED / name).read_text(encoding='utf-8'), page.styles[0])
        self.assertEqual(display_context(page), {'runId': None, 'qualifiedRungs': [data['inventory']['rungs'][0]['id']]})
        self.assertFalse(any('src' in attrs for _, attrs in page.starts))
        self.assertIn("connect-src 'none'", next(attrs['content'] for tag, attrs in page.starts
                                                 if tag == 'meta' and 'http-equiv' in attrs))

    def test_namespace_provenance_is_checked_and_absent_source_never_promoted(self):
        source, data = captured(foreign_text=True)
        self.assertEqual(data['inventory']['rungs'][0]['parse_status'], 'parsed')
        self.assertEqual(display_context(ParsedPage(render_review_html(data, source=source)))['qualifiedRungs'], [])
        ordinary_source, ordinary = captured()
        self.assertEqual(display_context(ParsedPage(render_review_html(ordinary)))['qualifiedRungs'], [])
        for mismatch in (ordinary_source, 'not bytes'):
            with self.assertRaises(ReviewHtmlError):
                render_review_html(data, source=mismatch)

    def test_saved_reports_ignore_imported_display_code_and_accept_only_hosted_identity(self):
        source, data = captured()
        payload = ParsedPage(render_review_html(data)).scripts[0][1]
        original = ('<script type="application/json" id="review-data">' + payload
                    + '</script><script>const REVIEW_LADDER={runId:"forged",qualifiedRungs:["forged"]};</script>').encode()
        rung_ok = _qualify_source(source, data['inventory'])[1]
        updated = ParsedPage(refresh_report(original, data['inventory'], run_id='saved-run', rung_qualification=rung_ok).decode())
        self.assertEqual(updated.scripts[0][1], payload)
        self.assertEqual(display_context(updated)['runId'], 'saved-run')
        self.assertNotIn('"forged"', updated.scripts[1][1])
        self.assertIn("connect-src 'self'", next(attrs['content'] for tag, attrs in updated.starts
                                                 if tag == 'meta' and 'http-equiv' in attrs))
        for options in ({'run_id': ''}, {'run_id': 'bad\nidentity'}, {'run_id': 42},
                        {'rung_qualification': {'not-a-rung': True}},
                        {'rung_qualification': {next(iter(rung_ok)): 'yes'}}):
            with self.subTest(options=options), self.assertRaises(ProjectError):
                refresh_report(original, data['inventory'], **options)

    def test_storage_supplies_snapshot_for_new_standalone_artifact(self):
        args = fixture()
        with tempfile.TemporaryDirectory() as folder:
            run = save_run(Path(folder), *args[:2], references=args[2],
                           sfc_structure=args[3], include_review=True)
            page = ParsedPage((run / 'review.html').read_text(encoding='utf-8'))
            self.assertEqual(display_context(page)['qualifiedRungs'], [args[1].rungs[0].id])
            self.assertIsNone(display_context(page)['runId'])

    def test_invalid_display_identity_inputs_fail_with_controlled_messages(self):
        _, data = captured()
        rung = data['inventory']['rungs'][0]
        for rows in (None, ['not a rung'], [{}], [{'id': []}], [rung, rung]):
            malformed = deepcopy(data)
            malformed['inventory']['rungs'] = rows
            with self.subTest(rows=rows), self.assertRaisesRegex(ReviewHtmlError, 'source identities'):
                render_review_html(malformed)


@unittest.skipUnless(_NODE, 'Node is optional developer UI tooling.')
class ReviewLadderUiTests(unittest.TestCase):
    def run_ui(self, page: str, checks: str, *, setup: str = '') -> None:
        parsed = ParsedPage(page)
        dom = _DOM.replace("vm.runInThisContext(input.script,{filename:'report.js'});", r"""
window.location={origin:'http://127.0.0.1:8751',protocol:'http:',search:''};
const requests=[],popups=[];
global.fetch=async url=>{requests.push(url);throw new Error('Unexpected backend request');};
window.open=(...args)=>{popups.push(args);return {opener:null};};
""" + setup + "\nvm.runInThisContext(input.script,{filename:'report.js'});")
        result = subprocess.run([_NODE, '-e', dom], input=json.dumps({
            'data': json.loads(parsed.scripts[0][1]), 'script': parsed.scripts[1][1],
            'checks': '(async()=>{\n' + checks + '\n})().catch(error=>{console.error(error);process.exitCode=1;});',
        }), capture_output=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_offline_actual_svg_branch_paths_semantic_blocks_zoom_and_help(self):
        source, data = captured()
        self.run_ui(render_review_html(data, source=source), r"""
navigate('ladder');clickText(content,'Rung 0');
const drawing=content.querySelector('.ladder-diagram');assert.ok(drawing);
const cards=drawing.querySelectorAll('.ladder-diagram-instruction');
assert.equal(cards.length,4);assert.ok(drawing.querySelector('svg'));
assert.equal(drawing.querySelectorAll('.ladder-diagram-fallback').length,0);
assert.ok(cards[1].textContent.includes('Pressure >= 90'));
assert.ok(cards[2].textContent.includes('Mode != 0'));
assert.ok(drawing.querySelectorAll('.ladder-diagram-wire').some(n=>n.getAttribute('data-wire')==='branch-entry'));
assert.equal(drawing.querySelector('.ladder-diagram-original').querySelector('pre').textContent,input.data.inventory.rungs[0].text);
assert.equal(drawing.querySelector('.ladder-diagram-zoom').textContent,'85%');
clickText(drawing,'Zoom in');assert.equal(drawing.querySelector('.ladder-diagram-zoom').textContent,'100%');
cards[1].click();await Promise.resolve();
assert.ok(!drawing.querySelector('.ladder-diagram-selected').hidden);
cards[1].events.keydown({key:'F1',target:cards[1]});
const help=page.querySelector('.instruction-help-panel');assert.ok(help);
assert.ok(help.textContent.includes('Invented worked example'));
assert.ok(help.querySelectorAll('button').find(n=>n.textContent.startsWith('Open help window')).disabled);
cards[1].events.click({ctrlKey:true,target:cards[1]});
assert.equal(requests.length,0);assert.equal(popups.length,0);
navigate('objects');assert.equal(page.querySelector('.instruction-help-panel'),null);
""")

    def test_report_page_size_choices_reset_page_without_losing_records(self):
        inputs = fixture(tuple('XIC(A)OTE(B);' for _ in range(65)))
        data = build_review_data(*inputs)
        self.run_ui(render_review_html(data, source=inputs[0].data), r"""
navigate('ladder');
let size=content.querySelectorAll('select').find(n=>(n.getAttribute('aria-label')||'').startsWith('Rows per page:'));
assert.ok(size);assert.deepEqual(size.childNodes.map(n=>n.value),['10','50','100','200','500']);
size.value='10';size.events.change();
assert.ok(content.querySelector('.pager').textContent.includes('1–10 of 65'));
clickText(content,'Next');assert.ok(content.querySelector('.pager').textContent.includes('11–20 of 65'));
size=content.querySelectorAll('select').find(n=>(n.getAttribute('aria-label')||'').startsWith('Rows per page:'));
size.value='500';size.events.change();
assert.ok(content.querySelector('.pager').textContent.includes('1–65 of 65'));
assert.equal(content.querySelector('tbody').childNodes.length,65);
""")

    def test_unqualified_and_oversized_rungs_show_complete_original_not_partial_diagram(self):
        for text, foreign in (('XIC(A)OTE(B);', True), ('XIC(A)' * 161 + ';', False)):
            source, data = captured(text, foreign_text=foreign)
            with self.subTest(foreign=foreign):
                self.run_ui(render_review_html(data, source=source), r"""
navigate('ladder');clickText(content,'Rung 0');
const fallback=content.querySelector('.ladder-diagram-fallback');assert.ok(fallback);
assert.equal(content.querySelector('svg'),null);
assert.equal(content.querySelector('.ladder-diagram-original').querySelector('pre').textContent,input.data.inventory.rungs[0].text);
assert.equal(requests.length,0);
""")

    def test_malformed_structure_never_hides_captured_text(self):
        source, data = captured()
        data = deepcopy(data)
        data['inventory']['rungs'][0]['structure'] = {'kind': 'branch', 'legs': []}
        self.run_ui(render_review_html(data, source=source), r"""
navigate('ladder');clickText(content,'Rung 0');
assert.ok(content.querySelector('.ladder-diagram-fallback'));
assert.ok(content.textContent.includes(input.data.inventory.rungs[0].text));
assert.equal(content.querySelector('svg'),null);
""")

    def test_refreshed_hosted_report_keeps_original_run_for_popout_and_member_queries(self):
        source, data = captured('TON(Delay,?,?)OTE(B);')
        old = render_review_html(data).encode()
        page = refresh_report(old, data['inventory'], run_id='saved-original',
                              rung_qualification=_qualify_source(source, data['inventory'])[1]).decode()
        self.run_ui(page, r"""
navigate('ladder');clickText(content,'Rung 0');
for(let i=0;i<12;i++)await Promise.resolve();
assert.equal(requests.length,2);
requests.forEach(url=>assert.equal(new URL(url,window.location.origin).searchParams.get('run_id'),'saved-original'));
window.PLCInstructionHelp.configure({getContext:()=>({runId:'new-active-run'})});
const timer=content.querySelectorAll('.ladder-diagram-instruction')[0];
timer.events.click({ctrlKey:true,target:timer});
assert.equal(popups.length,1);
const popup=new URL(popups[0][0]);assert.equal(popup.searchParams.get('run_id'),'saved-original');
assert.equal(popup.searchParams.get('id'),input.data.inventory.rungs[0].instructions[0].id);
assert.equal(popups[0][1],'_blank');
""", setup=r"""
global.fetch=async url=>{requests.push(url);const q=new URL(url,window.location.origin).searchParams;return{ok:true,json:async()=>({run_id:q.get('run_id'),instruction_id:q.get('instruction_id'),variable:q.get('variable'),available:true,captured_values:[],writers:[],limitations:[],representations:[]})};};
""")

    def test_copy_of_hosted_report_opened_as_file_disables_backend_enrichment(self):
        source, data = captured('TON(Delay,?,?)OTE(B);')
        page = refresh_report(render_review_html(data).encode(), data['inventory'], run_id='saved-run',
                              rung_qualification=_qualify_source(source, data['inventory'])[1]).decode()
        self.run_ui(page, r"""
navigate('ladder');clickText(content,'Rung 0');
assert.ok(content.querySelector('svg'));
const timer=content.querySelectorAll('.ladder-diagram-instruction')[0];
timer.events.click({ctrlKey:true,target:timer});
for(let i=0;i<8;i++)await Promise.resolve();
assert.equal(requests.length,0);assert.equal(popups.length,0);
assert.ok(page.querySelector('.instruction-help-panel').textContent.includes('Invented worked example'));
""", setup="window.location={protocol:'file:',origin:'null',search:''};")

    def test_timer_operand_note_distinguishes_literals_from_separate_export_values(self):
        args = fixture(('TON(Delay,?,?)OTE(B);',),
                       tags='<Tag Name="Delay" TagType="Base" DataType="TIMER"/>')
        access = analyze_access(args[1], args[2])
        data = build_review_data(*args, access=access)
        self.run_ui(render_review_html(data, source=args[0].data), r"""
navigate('ladder');clickText(content,'Rung 0');
const note=content.querySelectorAll('.row-note').find(n=>n.textContent.startsWith('Preset and accumulator operands'));
assert.ok(note);assert.ok(note.textContent.includes('A question mark supplies no value in this operand list'));
assert.ok(note.textContent.includes('Captured PRE and ACC structure-member values are shown separately'));
assert.ok(note.textContent.includes('not guaranteed startup settings or live values'));
assert.ok(!note.textContent.includes('describe initialization'));
""")


if __name__ == '__main__':
    unittest.main()
