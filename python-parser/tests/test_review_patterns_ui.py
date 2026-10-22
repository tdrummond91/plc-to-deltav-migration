"""Exercise pattern review against the bundled report and invented L5X evidence."""
from __future__ import annotations

from copy import deepcopy
import re
import unittest

from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from plc_workbench.workspace_classification import _qualify_source
from plc_workbench.workspace_report import refresh_report
from plc_workbench.translation_catalog import collect_annotations
from test_access_review_ui import _NODE
from test_review import fixture
import test_review_ladder_ui as ladder_ui
from test_review_ladder_ui import captured


# Extend only this suite's DOM. Document capture listeners and focus transitions
# are needed to exercise dismissal, rather than calling application internals.
_EVENTS = r"""
const documentEvents={},windowEvents={},scheduled=new Map();let nextTimer=1;
const register=(registry,name,callback,capture=false)=>{
  (registry[name]??=[]).push({callback,capture});
};
document.addEventListener=(...args)=>register(documentEvents,...args);
window.addEventListener=(...args)=>register(windowEvents,...args);
function dispatch(registry,name,fields={}){
  const event={target:page,preventDefault(){this.defaultPrevented=true;},
    stopImmediatePropagation(){this.stopped=true;},...fields};
  for(const listener of [...(registry[name]||[])].sort((a,b)=>Number(b.capture)-Number(a.capture))){
    listener.callback(event);if(event.stopped)break;
  }
  return event;
}
global.setTimeout=(callback,delay)=>{const id=nextTimer++;scheduled.set(id,{callback,delay});return id;};
global.clearTimeout=id=>scheduled.delete(id);
function advanceTimers(delay){
  for(const [id,timer] of [...scheduled])if(timer.delay<=delay&&scheduled.has(id)){
    scheduled.delete(id);timer.callback();
  }
}
Element.prototype.focus=function(){
  const previous=document.activeElement;
  if(previous===this)return;
  document.activeElement=this;
  previous?.events.focusout?.({relatedTarget:this});
  this.events.focusin?.({relatedTarget:previous});
};
"""

_HELPERS = r"""
function selector(label){
  const result=document.getElementById('toolbar').querySelectorAll('select')
    .find(n=>n.getAttribute('aria-label')===label);
  assert.ok(result,'Missing selector '+label);return result;
}
function choose(label,value){const select=selector(label);select.value=value;select.events.change({target:select});}
function search(value){const input=document.getElementById('review-search');input.value=value;input.events.input({target:input});}
function patternRows(){return rows(tableNamed('Ladder syntax patterns'));}
function counts(){return patternRows().map(row=>Number(texts(row)[1].replaceAll(',','')));}
function openFirstPattern(){navigate('patterns');patternRows()[0].querySelector('button').click();}
function occurrenceButtons(){return tableNamed('Pattern occurrences').querySelectorAll('.pattern-rung');}
function occurrencePager(direction){
  return content.querySelectorAll('button').find(n=>n.getAttribute('aria-label')===direction+' page: Pattern occurrences');
}
function context(){return page.querySelector('.pattern-rung-context');}
function contextValues(){
  const children=context().querySelector('dl').childNodes,result={};
  for(let i=0;i<children.length;i+=2)result[children[i].textContent]=children[i+1].textContent;
  return result;
}
"""


def pattern_capture() -> tuple[bytes, dict]:
    """Different syntax shapes, with numeric count and deterministic tie cases."""
    texts = (('XIC(A)OTE(B);',) * 12 + ('XIO(A)OTE(B);',) * 2
             + ('GEQ(A,5)OTE(B);',) * 2 + ('MOV(1,B);',))
    args = fixture(texts)
    return args[0].data, build_review_data(*args)


def repeated_capture() -> tuple[bytes, dict]:
    """Two routines share rung numbers and syntax, never their source identities."""
    main = tuple(f'XIC(A)[GEQ(Pressure,{i}),NEQ(Mode,0)]OTE(B);' for i in range(12))
    other = ''.join(
        f'<Rung Number="{i}"><Text><![CDATA[XIC(A)[GEQ(Pressure,{i + 12}),NEQ(Mode,0)]OTE(B);]]></Text>'
        f'<Comment><![CDATA[Invented second routine comment {i}]]></Comment></Rung>'
        for i in range(11))
    args = fixture(main, extra_routines='<Routine Name="Other" Type="RLL"><RLLContent>'
                   + other + '</RLLContent></Routine>', comment='Invented main comment <b>literal</b>')
    return args[0].data, build_review_data(*args)


@unittest.skipUnless(_NODE, 'Node is optional developer UI tooling.')
class ReviewPatternsUiTests(unittest.TestCase):
    # Reuse the execution helper without inheriting another suite's test cases.
    run_ui = ladder_ui.ReviewLadderUiTests.run_ui

    def check_ui(self, page: str, checks: str, *, setup: str = '') -> None:
        self.run_ui(page, _HELPERS + checks, setup=_EVENTS + setup)

    def test_overview_entry_and_numeric_occurrence_sort_with_stable_ties(self):
        source, data = pattern_capture()
        self.check_ui(render_review_html(data, source=source), r"""
const nav=document.getElementById('navigation').childNodes;
assert.deepEqual(nav.slice(0,2).map(n=>n.dataset.view),['overview','patterns']);
assert.ok(content.childNodes[0].matches('.pattern-start'));
assert.ok(content.childNodes[0].textContent.includes('4 patterns'));
clickText(content,'Review patterns — most occurrences first');
assert.deepEqual(counts(),[12,2,2,1]);
const ties=patternRows().filter(row=>texts(row)[1]==='2').map(row=>texts(row)[0]);
assert.equal(new Set(ties).size,2);
choose('Sort occurrences','least');assert.deepEqual(counts(),[1,2,2,12]);
assert.deepEqual(patternRows().filter(row=>texts(row)[1]==='2').map(row=>texts(row)[0]),ties);
choose('Sort occurrences','most');assert.deepEqual(counts(),[12,2,2,1]);
assert.deepEqual(patternRows().filter(row=>texts(row)[1]==='2').map(row=>texts(row)[0]),ties);
""")

    def test_filter_search_and_back_keep_sort_and_selection(self):
        source, data = pattern_capture()
        self.check_ui(render_review_html(data, source=source), r"""
navigate('patterns');choose('Sort occurrences','least');choose('Filter Patterns','repeated');
assert.deepEqual(counts(),[2,2,12]);search('XIC');assert.deepEqual(counts(),[12]);
patternRows()[0].querySelector('button').click();
assert.ok(heading.textContent.includes('12 occurrences'));
clickText(heading,'← Back to previous view');
assert.equal(selector('Sort occurrences').value,'least');
assert.equal(selector('Filter Patterns').value,'repeated');
assert.equal(document.getElementById('review-search').value,'XIC');assert.deepEqual(counts(),[12]);
search('');assert.deepEqual(counts(),[2,2,12]);
choose('Filter Patterns','single');assert.deepEqual(counts(),[1]);
search('no such invented opcode');
assert.ok(content.textContent.includes('No records in this section'));
search('');choose('Filter Patterns','all');assert.deepEqual(counts(),[1,2,2,12]);
""")

    def test_routine_source_and_ladder_directory_use_same_paged_drawings(self):
        source, data = repeated_capture()
        self.check_ui(render_review_html(data, source=source), r"""
navigate('ladder');
let listing=tableNamed('Ladder rungs');
assert.deepEqual(listing.querySelectorAll('th').map(n=>n.textContent),['Rung','Ladder / equation']);
assert.equal(rows(listing).length,10);
assert.equal(listing.querySelectorAll('.ladder-diagram').length,10);
assert.equal(listing.querySelectorAll('.snippet').length,0);
const anchor=listing.querySelector('.pattern-rung');anchor.focus();
assert.ok(context().textContent.includes('Invented main comment'));
clickText(context(),'Open routine source');
listing=tableNamed('Ladder rungs');
assert.equal(rows(listing).length,10);
assert.ok(listing.querySelector('svg'));
const next=content.querySelectorAll('button').find(n=>n.getAttribute('aria-label')==='Next page: Ladder rungs');next.click();
assert.equal(rows(tableNamed('Ladder rungs')).length,2);
assert.deepEqual(tableNamed('Ladder rungs').querySelectorAll('.pattern-rung').map(n=>n.textContent),['Rung 10','Rung 11']);
const drawing=tableNamed('Ladder rungs').querySelector('.ladder-diagram');
assert.ok(drawing.querySelectorAll('.ladder-diagram-wire').some(n=>n.getAttribute('data-wire')==='branch-entry'));
assert.equal(drawing.querySelector('.ladder-diagram-zoom').textContent,'85%');
clickText(drawing,'Zoom in');assert.equal(drawing.querySelector('.ladder-diagram-zoom').textContent,'100%');
""")

    def test_occurrence_uses_two_columns_shared_branch_graphic_original_zoom_and_help(self):
        source, data = captured()
        self.check_ui(render_review_html(data, source=source), r"""
openFirstPattern();
const table=tableNamed('Pattern occurrences');
assert.deepEqual(table.querySelectorAll('th').map(n=>n.textContent),['Rung','Ladder / equation']);
assert.equal(rows(table)[0].childNodes.length,2);
const anchor=occurrenceButtons()[0];assert.ok(anchor.matches('.pattern-status-parsed'));
assert.ok(anchor.getAttribute('aria-description').includes('Parse status: parsed'));
const drawing=rows(table)[0].childNodes[1].querySelector('.ladder-diagram');assert.ok(drawing);
assert.ok(drawing.querySelector('svg'));
const blocks=drawing.querySelectorAll('.ladder-diagram-instruction');assert.equal(blocks.length,4);
assert.ok(blocks[1].textContent.includes('Pressure >= 90'));
assert.ok(blocks[2].textContent.includes('Mode != 0'));
assert.ok(drawing.querySelectorAll('.ladder-diagram-wire').some(n=>n.getAttribute('data-wire')==='branch-entry'));
assert.equal(drawing.querySelector('.ladder-diagram-original').querySelector('pre').textContent,input.data.inventory.rungs[0].text);
assert.equal(drawing.querySelector('.ladder-diagram-zoom').textContent,'85%');
clickText(drawing,'Zoom in');assert.equal(drawing.querySelector('.ladder-diagram-zoom').textContent,'100%');
blocks[1].events.pointerenter({target:blocks[1]});advanceTimers(1000);
const help=page.querySelector('.instruction-help-panel');assert.ok(help);
assert.ok(help.textContent.includes('Invented worked example'));
assert.ok(help.textContent.includes('Pressure'));assert.equal(requests.length,0);
navigate('overview');assert.equal(page.querySelector('.instruction-help-panel'),null);
""")

    def test_narrow_context_keeps_pointer_target_exposed_above_or_below(self):
        source, data = repeated_capture()
        self.check_ui(render_review_html(data, source=source), r"""
openFirstPattern();const anchor=occurrenceButtons()[0];
window.innerWidth=400;window.innerHeight=650;
const originalRect=Element.prototype.getBoundingClientRect;
Element.prototype.getBoundingClientRect=function(){
  if(this.matches('.pattern-rung-context'))return {width:376,height:Math.min(320,parseFloat(this.style.maxHeight)||320)};
  return originalRect.call(this);
};
anchor.getBoundingClientRect=()=>({left:20,right:90,top:100,bottom:130,width:70,height:30});
anchor.focus();assert.ok(parseFloat(context().style.top)>=140);
dispatch(documentEvents,'pointerdown',{target:page});
anchor.getBoundingClientRect=()=>({left:20,right:90,top:530,bottom:560,width:70,height:30});
anchor.events.pointerenter({});
assert.ok(parseFloat(context().style.top)+context().getBoundingClientRect().height<=520);
anchor.click();assert.equal(context(),null);assert.ok(heading.textContent.includes('Rung 0'));
""")

    def test_owner_source_link_exposes_full_member_comments_and_all_pages(self):
        notes = ''.join(f'<Comment Operand="Data.{i}">note-{i}-' + 'word ' * 120 + '-END</Comment>'
                        for i in range(12))
        args = fixture(tags='<Tag Name="Notes" DataType="DINT"><Description>'
            '<LocalizedDescription Lang="fr-FR">Description locale</LocalizedDescription>'
            '</Description><Comments>' + notes + '</Comments></Tag>')
        data = build_review_data(*args)
        source = args[0].data
        page = refresh_report(render_review_html(data, source=source).encode(), data['inventory'],
            catalog=collect_annotations(source, data['inventory']), translations={}).decode()
        overlay = re.search(r'<div id="review-language-data" hidden>(.*?)</div>', page).group(1)
        self.check_ui(page, r"""
let listing=tableNamed('Declaration source comments');
assert.equal(rows(listing).length,10);
assert.ok(listing.textContent.includes('Description locale'));
assert.ok(listing.textContent.includes('note-8-'+'word '.repeat(120)+'-END'));
const next=content.querySelectorAll('button').find(n=>n.getAttribute('aria-label')==='Next page: Declaration source comments');
next.click();listing=tableNamed('Declaration source comments');
assert.equal(rows(listing).length,3);
assert.ok(listing.textContent.includes('note-11-'+'word '.repeat(120)+'-END'));
assert.ok(listing.textContent.includes('/Comment[12]'));
""", setup="window.location={hash:'#view=objects&source='+input.data.inventory.entities.find(e=>e.name==='Notes').id};"
            + "const overlay=new Element('div');overlay.id='review-language-data';overlay.textContent=JSON.stringify("
            + overlay + ");page.append(overlay);")

    def test_ten_row_pages_keep_all_source_ids_and_repeated_numbers_in_source_order(self):
        source, data = repeated_capture()
        self.check_ui(render_review_html(data, source=source), r"""
openFirstPattern();
const expected=input.data.patterns[0].rung_ids,seen=[];
assert.equal(expected.length,23);assert.ok(occurrencePager('Previous').disabled);
for(const amount of [10,10,3]){
  assert.equal(rows(tableNamed('Pattern occurrences')).length,amount);
  const buttons=occurrenceButtons();seen.push(...buttons.map(n=>n.dataset.sourceId));
  assert.equal(content.querySelectorAll('.ladder-diagram').length,amount);
  if(seen.length<23){
    buttons[0].events.pointerenter({});assert.ok(context());
    occurrencePager('Next').click();assert.equal(context(),null);
  }
}
assert.deepEqual(seen,expected);assert.equal(new Set(seen).size,23);
assert.ok(occurrencePager('Next').disabled);
occurrencePager('Previous').click();
assert.deepEqual(occurrenceButtons().map(n=>n.dataset.sourceId),expected.slice(10,20));
const repeated=occurrenceButtons().find(n=>n.textContent==='Rung 0');assert.ok(repeated);
repeated.events.pointerenter({});assert.equal(contextValues().Routine,'Other');
assert.ok(context().textContent.includes('Invented second routine comment 0'));
repeated.click();assert.equal(context(),null);assert.ok(heading.textContent.includes('Rung 0'));
clickText(heading,'← Back to previous view');
assert.deepEqual(occurrenceButtons().map(n=>n.dataset.sourceId),expected.slice(10,20));
""")

    def test_unqualified_and_bounded_drawings_keep_complete_original_occurrences(self):
        for text, foreign in (('XIC(A)OTE(B);', True), ('XIC(A)' * 161 + ';', False)):
            source, data = captured(text, foreign_text=foreign)
            with self.subTest(foreign_namespace=foreign):
                self.check_ui(render_review_html(data, source=source), r"""
openFirstPattern();
assert.equal(occurrenceButtons().length,1);
assert.ok(content.querySelector('.ladder-diagram-fallback'));
assert.equal(content.querySelector('svg'),null);
assert.equal(content.querySelector('.ladder-diagram-original').querySelector('pre').textContent,input.data.inventory.rungs[0].text);
assert.equal(requests.length,0);
""")

    def test_context_exposes_source_comment_status_and_only_hosted_edit_link(self):
        source, data = repeated_capture()
        original = render_review_html(data, source=source)
        hosted = refresh_report(original.encode(), data['inventory'], run_id='invented-saved-run',
                                rung_qualification=_qualify_source(source, data['inventory'])[1]).decode()
        for online, page in ((False, original), (True, hosted)):
            with self.subTest(hosted=online):
                self.check_ui(page, 'const hosted=' + str(online).lower() + ';' + r"""
openFirstPattern();const anchor=occurrenceButtons()[0];anchor.events.pointerenter({});
assert.equal(anchor.getAttribute('aria-expanded'),'true');
assert.equal(context().getAttribute('role'),'dialog');
assert.deepEqual(contextValues(),{Routine:'Main',Scope:'Demo / P', 'Parse status':'parsed'});
assert.ok(context().textContent.includes('Invented main comment <b>literal</b>'));
assert.equal(context().querySelector('b'),null);
const links=context().querySelectorAll('a');assert.equal(links.length,hosted?1:0);
if(hosted){
  assert.equal(links[0].href,'/#view=rungs&source='+encodeURIComponent(anchor.dataset.sourceId));
  assert.equal(links[0].target,'_blank');assert.equal(links[0].rel,'noopener');
}
clickText(context(),'Open routine source');assert.equal(context(),null);
assert.ok(heading.textContent.includes('Main'));
""")

    def test_missing_comment_and_changed_capture_status_are_explicit(self):
        source, data = captured()
        data = deepcopy(data)
        data['inventory']['rungs'][0]['comment'] = ' \t\n '
        # Defensive display of imported/incomplete evidence must remain honest.
        for status, color in (('incomplete', 'warning'), ('error', 'error')):
            data['inventory']['rungs'][0]['parse_status'] = status
            with self.subTest(status=status):
                self.check_ui(render_review_html(data), 'const color=' + repr(color) + ';' + r"""
openFirstPattern();const anchor=occurrenceButtons()[0];
assert.ok(anchor.matches('.pattern-status-'+color));anchor.events.pointerenter({});
assert.ok(context().textContent.includes('No comment'));
assert.equal(contextValues()['Parse status'].toLowerCase(),input.data.inventory.rungs[0].parse_status);
assert.ok(content.querySelector('.ladder-diagram-fallback'));
assert.equal(content.querySelector('.ladder-diagram-original').querySelector('pre').textContent,input.data.inventory.rungs[0].text);
""")

    def test_context_keyboard_pointer_navigation_scroll_and_resize_dismissal(self):
        source, data = repeated_capture()
        self.check_ui(render_review_html(data, source=source), r"""
openFirstPattern();const anchor=occurrenceButtons()[0];anchor.focus();assert.ok(context());
anchor.events.keydown({key:'F1'});
assert.equal(document.activeElement.textContent,'Close');
const escape=dispatch(documentEvents,'keydown',{key:'Escape',target:document.activeElement});
assert.ok(escape.defaultPrevented);assert.equal(context(),null);
assert.equal(document.activeElement,anchor);assert.equal(anchor.getAttribute('aria-expanded'),'false');
advanceTimers(1000);assert.equal(context(),null);
anchor.events.pointerenter({});const box=context();assert.ok(box);
anchor.events.pointerleave({relatedTarget:box});box.events.pointerenter({});advanceTimers(1000);assert.equal(context(),box);
dispatch(documentEvents,'pointerdown',{target:box.querySelector('button')});assert.equal(context(),box);
dispatch(documentEvents,'pointerdown',{target:page});assert.equal(context(),null);
anchor.events.pointerenter({});assert.ok(context());
dispatch(documentEvents,'scroll',{target:context()});assert.ok(context());
dispatch(documentEvents,'scroll',{target:page});assert.equal(context(),null);
anchor.events.pointerenter({});dispatch(windowEvents,'resize');assert.equal(context(),null);
anchor.events.pointerenter({});assert.ok(context());navigate('objects');assert.equal(context(),null);
assert.equal(anchor.getAttribute('aria-expanded'),'false');
advanceTimers(1000);assert.equal(context(),null);
""")


if __name__ == '__main__':
    unittest.main()
