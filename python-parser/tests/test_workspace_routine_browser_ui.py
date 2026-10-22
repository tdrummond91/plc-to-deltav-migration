"""Lazy routine browsing and stale-response behavior against the shipped asset."""
from __future__ import annotations

import subprocess
import unittest

from test_workspace_ui import ASSETS, NODE


SCRIPT = (ASSETS / 'routine-browser.js').read_text(encoding='utf-8')
DOM = r"""
const assert=require('node:assert/strict');
class Element {
  constructor(tag) {this.tagName=tag;this.children=[];this.events={};this.attributes={};this.dataset={};this.className='';this._text='';this.value='';this.disabled=false;this.open=false;}
  set textContent(text){this._text=String(text);this.children=[];}
  get textContent(){return this._text+this.children.map(child=>child.textContent).join(' ');}
  append(...children){children.forEach(child=>{child.parent=this;this.children.push(child);});}
  replaceChildren(...children){this.children=[];this._text='';this.append(...children);}
  remove(){if(this.parent){this.parent.children=this.parent.children.filter(child=>child!==this);this.parent=null;}}
  addEventListener(name,fn){this.events[name]=fn;}
  setAttribute(name,value){this.attributes[name]=String(value);}
  fire(name,values={}){if(name==='click'&&this.disabled)return;return this.events[name]?.({type:name,target:this,...values});}
}
const document={createElement:tag=>new Element(tag)},window={};
const root=new Element('section');
const all=(node=root)=>[node,...node.children.flatMap(all)];
const cls=name=>all().filter(node=>node.className.split(' ').includes(name));
const buttons=text=>all().filter(node=>node.tagName==='button'&&node.textContent===text);
const button=text=>buttons(text)[0];
const open=entry=>{entry.open=true;entry.fire('toggle');};
const close=entry=>{entry.open=false;entry.fire('toggle');};
const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return{promise,resolve,reject};};
const routine=i=>({id:'routine-'+i,name:'Routine '+i,path:'Controller / '+(i%2?'Beta':'Alpha')+' / Routine '+i,
  program_id:i%2?'beta':'alpha',program_name:i%2?'Beta':'Alpha',program_path:'Controller / '+(i%2?'Beta':'Alpha'),
  type:i%3===0?'ST':'RLL',count:45});
let project={project_path:'project-a.sqlite',active_run:'run-1',revision:1,routines:Array.from({length:105},(_,i)=>routine(i))};
let total=45;
const rung=i=>({id:'rung-'+i,number:String(500-i),path:'Captured / Rung '+i,comment:'Original comment '+i,
  wording:{comment:{status:'ready',text:'English comment '+i}},source_qualified:true,
  instructions:[{id:'instruction-'+i,opcode:'XIC',arguments:['Input']}],
  structure:{kind:'sequence',items:[{kind:'instruction',instruction_id:'instruction-'+i}]},text:'XIC(Input);'});
const payload=(url,overrides={})=>{const page=Number(url.searchParams.get('page')||1),start=(page-1)*20;
  return {run_id:project.active_run,revision:project.revision,routine:{id:url.searchParams.get('routine'),type:'RLL'},
    page,pages:Math.max(1,Math.ceil(total/20)),page_size:20,total,
    items:Array.from({length:Math.max(0,Math.min(20,total-start))},(_,i)=>rung(start+i)),presentation_mode:'original',
    notice:'Captured source order; not live state.',...overrides};};
const calls=[],diagrams=[],reviews=[],inspections=[],links=[];
let respond=async url=>payload(url);
const options={getState:()=>project,api:async path=>{calls.push(path);return respond(new URL(path,'http://local'));},
  review:(...args)=>reviews.push(args),inspect:item=>inspections.push(item),
  reportLink:(text,id,view)=>{links.push({text,id,view});const link=new Element('a');link.textContent=text;link.href='/analysis#view='+view+'&source='+id;return link;}};
window.PLCLadderDiagram={render:(source,options)=>{const diagram=new Element('div');diagram.className='test-ladder-diagram';
  diagrams.push({source,options,diagram});diagram.textContent='Diagram '+source.id;return diagram;}};
window.PLCTranslation={renderProse:(target,text,wording,mode)=>{target.textContent=mode==='english'&&wording?.text?wording.text:text;}};
const mount=()=>{const controller=window.PLCRoutineBrowser.mount(root,options);controller.refresh();return controller;};
"""


@unittest.skipUnless(NODE, 'Node is optional developer tooling')
class WorkspaceRoutineBrowserTests(unittest.TestCase):
    def run_js(self, checks: str) -> None:
        code = DOM + SCRIPT + '\n(async()=>{\n' + checks + '\n})().catch(error=>{console.error(error);process.exitCode=1;});'
        result = subprocess.run([NODE, '-'], input=code, capture_output=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_directory_is_paged_and_does_not_fetch_until_expanded(self):
        self.run_js(r"""
const controller=mount();await flush();
assert.equal(calls.length,0);assert.equal(diagrams.length,0);
assert.equal(cls('routine-directory-entry').length,50);
assert.ok(cls('routine-directory-status')[0].textContent.includes('105 of 105'));
assert.equal(button('Previous routines').disabled,true);
button('Next routines').fire('click');
assert.equal(cls('routine-directory-entry')[0].dataset.routineId,'routine-50');
assert.equal(calls.length,0);
const jump=cls('routine-directory-page')[0];jump.value='3';jump.fire('change');
assert.equal(cls('routine-directory-entry').length,5);assert.equal(button('Next routines').disabled,true);
const current=cls('routine-directory-page')[0];current.value='99';current.fire('change');assert.equal(current.value,'3');
open(cls('routine-directory-entry')[0]);await flush();
assert.equal(calls.length,1);assert.ok(calls[0].includes('routine=routine-100'));
assert.ok(calls[0].includes('run_id=run-1'));assert.equal(diagrams.length,20);
""")

    def test_only_one_expansion_renders_and_paging_preserves_captured_order(self):
        self.run_js(r"""
mount();const first=cls('routine-directory-entry')[0],second=cls('routine-directory-entry')[1];
open(first);await flush();
assert.deepEqual(cls('routine-rung').map(card=>card.dataset.sourceId),Array.from({length:20},(_,i)=>'rung-'+i));
assert.deepEqual(cls('routine-rung-heading').map(heading=>heading.children[0].textContent),Array.from({length:20},(_,i)=>'Rung '+(500-i)));
button('Next rung page').fire('click');await flush();
assert.deepEqual(cls('routine-rung').map(card=>card.dataset.sourceId),Array.from({length:20},(_,i)=>'rung-'+(20+i)));
assert.equal(button('Previous rung page').disabled,false);
button('Next rung page').fire('click');await flush();
assert.equal(cls('routine-rung').length,5);assert.equal(button('Next rung page').disabled,true);
open(second);await flush();assert.equal(first.open,false);assert.equal(first.children[1].children.length,0);
assert.equal(second.open,true);assert.equal(cls('routine-rung').length,20);
assert.ok(new URL(calls.at(-1),'http://local').searchParams.get('routine').endsWith('-1'));
close(second);await flush();assert.equal(cls('routine-rung').length,0);
""")

    def test_program_type_and_path_filters_intersect_and_reset_without_requests(self):
        self.run_js(r"""
mount();const program=cls('routine-directory-program')[0],type=cls('routine-directory-type')[0],query=cls('routine-directory-search')[0];
program.value='beta';program.fire('change');assert.ok(cls('routine-directory-entry').every(row=>Number(row.dataset.routineId.split('-')[1])%2===1));
type.value='ST';type.fire('change');assert.ok(cls('routine-directory-entry').every(row=>Number(row.dataset.routineId.split('-')[1])%3===0));
query.value='Controller / Beta / Routine 9';query.fire('input');
assert.deepEqual(cls('routine-directory-entry').map(row=>row.dataset.routineId),['routine-9','routine-93','routine-99']);
query.value='not present';query.fire('input');assert.equal(cls('routine-directory-entry').length,0);assert.ok(root.textContent.includes('No routines match'));
button('Clear routine filters').fire('click');assert.equal(program.value,'');assert.equal(type.value,'');assert.equal(query.value,'');
assert.equal(cls('routine-directory-entry').length,50);assert.equal(calls.length,0);
""")

    def test_distinct_aoi_scopes_do_not_collapse_into_unassigned_filter(self):
        self.run_js(r"""
project.routines=['FirstWidget','SecondWidget'].map((name,i)=>({...routine(i),name:'Logic',
  program_id:'',program_name:'',program_path:'',scope_id:'aoi-'+i,scope_name:name,scope_kind:'aoi',
  scope_path:'Controller / '+name,path:'Controller / '+name+' / Logic'}));
mount();const scope=cls('routine-directory-program')[0];
assert.deepEqual(scope.children.map(option=>option.value),['','aoi-0','aoi-1']);
assert.ok(scope.children[1].textContent.includes('FirstWidget'));
assert.ok(scope.children[2].textContent.includes('SecondWidget'));
scope.value='aoi-1';scope.fire('change');
assert.deepEqual(cls('routine-directory-entry').map(entry=>entry.dataset.routineId),['routine-1']);
assert.equal(calls.length,0);
""")

    def test_collapsing_or_filtering_discards_pending_response(self):
        self.run_js(r"""
const pending=deferred();respond=async()=>pending.promise;mount();
const entry=cls('routine-directory-entry')[0];open(entry);close(entry);
pending.resolve(payload(new URL(calls[0],'http://local')));await flush();assert.equal(diagrams.length,0);
const second=deferred();respond=async()=>second.promise;open(entry);
const query=cls('routine-directory-search')[0];query.value='Routine 50';query.fire('input');
second.resolve(payload(new URL(calls[1],'http://local')));await flush();
assert.equal(diagrams.length,0);assert.equal(cls('routine-rung').length,0);assert.equal(entry.open,false);
""")

    def test_deactivate_rejects_old_response_and_refresh_reloads_pending_entry(self):
        self.run_js(r"""
const old=deferred();respond=async()=>old.promise;const controller=mount();open(cls('routine-directory-entry')[0]);
controller.deactivate();old.resolve(payload(new URL(calls[0],'http://local')));await flush();assert.equal(diagrams.length,0);
respond=async url=>payload(url);controller.refresh();await flush();assert.equal(calls.length,2);assert.equal(diagrams.length,20);
""")

    def test_run_and_project_switches_clear_expansions_and_discard_late_results(self):
        self.run_js(r"""
const pending=[];respond=async url=>{const deferredResult=deferred();pending.push({url,result:deferredResult});return deferredResult.promise;};
const controller=mount();open(cls('routine-directory-entry')[0]);
project={...project,active_run:'run-2',routines:[routine(10)]};controller.refresh();
assert.equal(cls('routine-rung').length,0);assert.equal(cls('routine-directory-entry').length,1);
pending[0].result.resolve(payload(pending[0].url,{run_id:'run-1'}));await flush();assert.equal(diagrams.length,0);
open(cls('routine-directory-entry')[0]);
project={...project,project_path:'project-b.sqlite',routines:[routine(11)]};controller.refresh();
pending[1].result.resolve(payload(pending[1].url));await flush();assert.equal(diagrams.length,0);
assert.equal(cls('routine-directory-entry')[0].dataset.routineId,'routine-11');
""")

    def test_load_failure_can_retry_and_mismatched_response_does_not_draw(self):
        self.run_js(r"""
respond=async()=>{throw new Error('Saved source unavailable');};mount();open(cls('routine-directory-entry')[0]);await flush();
assert.ok(root.textContent.includes('Saved source unavailable'));assert.equal(diagrams.length,0);
respond=async url=>payload(url,{run_id:'wrong-run'});button('Retry routine page').fire('click');await flush();
assert.ok(root.textContent.includes('source changed while this routine was loading'));assert.equal(diagrams.length,0);
respond=async url=>payload(url);button('Retry routine page').fire('click');await flush();
assert.equal(diagrams.length,20);assert.equal(button('Retry routine page'),undefined);
""")

    def test_non_ladder_notice_and_source_link_remain_available(self):
        self.run_js(r"""
total=0;respond=async url=>payload(url,{routine:{id:url.searchParams.get('routine'),type:'SFC'},available:false,notice:'This routine is SFC; inspect its original source.'});
mount();open(cls('routine-directory-entry')[0]);await flush();
assert.equal(diagrams.length,0);assert.ok(root.textContent.includes('This routine is SFC'));
assert.ok(root.textContent.includes('No captured ladder rungs'));
assert.deepEqual(links,[{text:'Open routine source ↗',id:'routine-0',view:'sfc'}]);
button('Review routine rungs').fire('click');assert.deepEqual(reviews,[['routine-0']]);
""")

    def test_translation_updates_comments_without_replacing_diagrams(self):
        self.run_js(r"""
const controller=mount();open(cls('routine-directory-entry')[0]);await flush();
const firstDiagram=cls('test-ladder-diagram')[0],firstComment=cls('routine-rung-comment')[0];
assert.equal(firstComment.textContent,'Original comment 0');const before=diagrams.length;
respond=async url=>payload(url,{presentation_mode:'english'});controller.wordingChanged();await flush();
assert.equal(cls('test-ladder-diagram')[0],firstDiagram);assert.equal(diagrams.length,before);
assert.equal(cls('routine-rung-comment')[0],firstComment);assert.equal(firstComment.textContent,'English comment 0');
const delayed=deferred();respond=async()=>delayed.promise;controller.wordingChanged();
respond=async url=>payload(url,{presentation_mode:'original'});controller.wordingChanged();await flush();
delayed.resolve(payload(new URL(calls.at(-2),'http://local'),{presentation_mode:'english'}));await flush();
assert.equal(firstComment.textContent,'Original comment 0');assert.equal(diagrams.length,before);
""")

    def test_compact_headers_put_comments_beside_rung_number_and_pass_right_side_controls_target(self):
        self.run_js(r"""
const controller=mount();open(cls('routine-directory-entry')[0]);await flush();
const headings=cls('routine-rung-heading'),comments=cls('routine-rung-comment');
headings.forEach((heading,index)=>{
  assert.equal(heading.children[0].tagName,'h2');assert.equal(comments[index].parent,heading);
  const zoom=diagrams[index].options.controlsTarget;
  assert.equal(diagrams[index].options.compact,true);assert.equal(zoom.className,'routine-rung-zoom');
  assert.equal(zoom.parent.className,'routine-rung-tools');assert.equal(zoom.parent.parent,heading);
  assert.equal(heading.children.at(-1),zoom.parent);
});
assert.ok(cls('routine-directory-help')[0].textContent.includes('Drawings start at 85%'));
const firstComment=comments[0],zoomTarget=diagrams[0].options.controlsTarget,drawCount=diagrams.length;
respond=async url=>payload(url,{presentation_mode:'english'});controller.wordingChanged();await flush();
assert.equal(firstComment.parent,headings[0]);assert.equal(firstComment.textContent,'English comment 0');
assert.equal(diagrams.length,drawCount);assert.equal(diagrams[0].options.controlsTarget,zoomTarget);
""")

    def test_repeated_translation_failures_replace_warning_and_successful_retry_keeps_diagrams(self):
        self.run_js(r"""
const controller=mount();open(cls('routine-directory-entry')[0]);await flush();
const originalDiagrams=cls('test-ladder-diagram'),originalComments=cls('routine-rung-comment');
const renderCount=diagrams.length;let failures=0;
respond=async()=>{throw new Error('Wording refresh failure '+(++failures));};
controller.wordingChanged();await flush();
assert.equal(cls('routine-page-error').length,1);assert.equal(cls('routine-page-error')[0].attributes.role,'alert');
assert.ok(root.textContent.includes('Wording refresh failure 1'));
controller.wordingChanged();await flush();
assert.equal(cls('routine-page-error').length,1);assert.equal(buttons('Retry routine page').length,1);
assert.ok(root.textContent.includes('Wording refresh failure 2'));
assert.equal(root.textContent.includes('Wording refresh failure 1'),false);
assert.equal(diagrams.length,renderCount);
assert.deepEqual(cls('test-ladder-diagram'),originalDiagrams);
respond=async url=>payload(url,{presentation_mode:'english'});
button('Retry routine page').fire('click');await flush();
assert.equal(cls('routine-page-error').length,0);assert.equal(cls('warning-panel').length,0);
assert.equal(button('Retry routine page'),undefined);
assert.equal(root.textContent.includes('Wording refresh failure'),false);
assert.equal(diagrams.length,renderCount);
cls('test-ladder-diagram').forEach((diagram,i)=>assert.equal(diagram,originalDiagrams[i]));
cls('routine-rung-comment').forEach((comment,i)=>{assert.equal(comment,originalComments[i]);assert.equal(comment.textContent,'English comment '+i);});
""")

    def test_review_and_instruction_callbacks_receive_canonical_source_and_qualification(self):
        self.run_js(r"""
respond=async url=>payload(url,{items:[{...rung(0),source_qualified:false}]});mount();open(cls('routine-directory-entry')[0]);await flush();
assert.equal(diagrams[0].options.sourceQualified,false);
button('Open rung review').fire('click');assert.deepEqual(reviews,[['routine-0','rung-0']]);
const instruction=diagrams[0].source.instructions[0];diagrams[0].options.onInstruction(instruction);assert.equal(inspections[0],instruction);
project={...project,project_path:'different-project.sqlite'};
assert.throws(()=>diagrams[0].options.onInstruction(instruction),/active analysis changed/);
""")

    def test_translation_refresh_while_page_is_loading_keeps_requested_page(self):
        self.run_js(r"""
const controller=mount();open(cls('routine-directory-entry')[0]);await flush();
const loading=deferred();respond=async()=>loading.promise;button('Next rung page').fire('click');
assert.equal(new URL(calls.at(-1),'http://local').searchParams.get('page'),'2');
respond=async url=>payload(url,{presentation_mode:'english'});controller.wordingChanged();await flush();
assert.equal(new URL(calls.at(-1),'http://local').searchParams.get('page'),'2');
assert.equal(cls('routine-rung')[0].dataset.sourceId,'rung-20');
loading.resolve(payload(new URL(calls.at(-2),'http://local')));await flush();
assert.equal(cls('routine-rung')[0].dataset.sourceId,'rung-20');
""")

    def test_returning_to_view_while_rung_page_loads_keeps_requested_page(self):
        self.run_js(r"""
const controller=mount();open(cls('routine-directory-entry')[0]);await flush();
const loading=deferred();respond=async()=>loading.promise;button('Next rung page').fire('click');
controller.deactivate();respond=async url=>payload(url);controller.refresh();await flush();
assert.equal(new URL(calls.at(-1),'http://local').searchParams.get('page'),'2');
assert.equal(cls('routine-rung')[0].dataset.sourceId,'rung-20');
loading.resolve(payload(new URL(calls.at(-2),'http://local')));await flush();
assert.equal(cls('routine-rung')[0].dataset.sourceId,'rung-20');
""")


if __name__ == '__main__':
    unittest.main()
