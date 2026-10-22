"""Exercise large invented ladder views without loading a browser or plant data."""
from __future__ import annotations

import subprocess
import unittest

from test_workspace_ui import ASSETS, NODE


SCRIPT = (ASSETS / "ladder-map.js").read_text(encoding="utf-8")
DOM = r"""
const assert = require('node:assert/strict');
class Element {
  constructor(tag) { this.tagName=tag; this.children=[]; this.events={}; this.attributes={}; this.className=''; this._text=''; this.value=''; this.disabled=false; this.hidden=false; }
  set textContent(value) { this._text=String(value); this.children=[]; }
  get textContent() { return this._text+this.children.map(child=>child.textContent).join(' '); }
  append(...children) { children.forEach(child=>{child.parent=this;this.children.push(child);}); }
  replaceChildren(...children) { this.children=[];this._text='';this.append(...children); }
  addEventListener(name,fn) { this.events[name]=fn; }
  setAttribute(name,value) { this.attributes[name]=String(value); }
  querySelectorAll(selector) { const descendants=this.children.flatMap(child=>[child,...child.querySelectorAll('*')]);return selector==='*'?descendants:descendants.filter(node=>node.tagName===selector); }
  getBoundingClientRect() { return {width:900,height:600,left:0,top:0}; }
  setPointerCapture(id) { this.pointer=id; }
  hasPointerCapture(id) { return this.pointer===id; }
  releasePointerCapture() { this.pointer=null; }
  fire(name, values={}) { if(name==='click'&&this.disabled)return;return this.events[name]?.({type:name,target:this,button:0,pointerId:1,clientX:200,clientY:200,stopPropagation(){},preventDefault(){},...values}); }
}
const document={events:{},createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),addEventListener(name,fn){this.events[name]=fn;},removeEventListener(name,fn){if(this.events[name]===fn)delete this.events[name];},fire(name,event){return this.events[name]?.({preventDefault(){},...event});}};
const window={};
const root=new Element('section');
const all=node=>[node,...node.children.flatMap(all)];
const cls=(name)=>all(root).filter(node=>(node.attributes.class||node.className||'').split(' ').includes(name));
const button=text=>all(root).find(node=>node.tagName==='button'&&node.textContent===text);
let task=0;const timers=new Map(),frames=new Map();
const setTimeout=fn=>{timers.set(++task,fn);return task;},clearTimeout=id=>timers.delete(id);
const requestAnimationFrame=fn=>{frames.set(++task,fn);return task;},cancelAnimationFrame=id=>frames.delete(id);
class ResizeObserver { observe(){} disconnect(){} }
async function flush() { for(let i=0;i<12;i++){const fs=[...frames.values()];frames.clear();fs.forEach(fn=>fn());const ts=[...timers.values()];timers.clear();await Promise.all(ts.map(fn=>fn()));await Promise.resolve();} }
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve};};
let project={active_run:'run-1',revision:1}, count=10000, accept=true;
const calls=[], inspected=[], popouts=[], connections=[], selections=[];
const rung=n=>({id:'rung-'+n,number:String(n),path:'Controller / Program / Main / Rung '+n,routine_id:'routine-1',routine_label:'Program / Main',source_order:n,comment_preview:'Invented comment '+n,opcodes:['XIC','OTE'],instruction_count:2,branch_count:0,families:['boolean'],parse_status:'complete'});
const index=(url, overrides={})=>{
 const page=Number(url.searchParams.get('page')||1),filtered=url.searchParams.get('query')||url.searchParams.get('signal_id');
 const size=filtered?1:count,start=filtered?9876:(page-1)*250;
 return {run_id:project.active_run,total:size,page,pages:Math.ceil(size/250)||1,items:Array.from({length:Math.max(0,Math.min(250,size-(page-1)*250))},(_,i)=>rung(start+i)),routines:[{id:'routine-1',label:'Main',count}],families:[{id:'boolean',label:'Boolean',count}],notice:'Captured source only.',...overrides};
};
let respond=async url=>{
 if(url.pathname.endsWith('/links'))return {run_id:project.active_run,signals:[],total:0,page:1,pages:1};
 if(url.pathname.endsWith('/detail'))return {run_id:project.active_run,id:url.searchParams.get('id'),title:'Invented rung information',description:'French/English source description',blocks:[{id:'instruction-1',opcode:'XIC',family:'boolean',identification:'known',summary:'Examine Boolean state'}],links:[{id:'aoi-1',label:'Invented AOI definition',kind:'AddOnInstructionDefinition'}],parameters:[],limitations:['Recorded source is not live flow.']};
 return index(url);
};
const options={getState:()=>project,api:async path=>{calls.push(path);return respond(new URL(path,'http://local'));},inspect:async id=>{inspected.push(id);return accept;},popout:(...args)=>popouts.push(args),connections:id=>connections.push(id),onSelection:id=>selections.push(id)};
"""


@unittest.skipUnless(NODE, "Node is optional developer tooling")
class LadderMapUiTests(unittest.TestCase):
    def run_js(self, checks: str) -> None:
        code = DOM + SCRIPT + "\n(async()=>{\n" + checks + "\n})().then(()=>process.stdout.write('MAP_OK\\n')).catch(error=>{console.error(error);process.exitCode=1;});"
        result = subprocess.run([NODE, "-"], input=code, capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MAP_OK", result.stdout)

    def test_ten_thousand_rungs_are_indexed_but_dom_and_detail_load_are_bounded(self) -> None:
        self.run_js(r"""
const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await flush();
assert.equal(calls.filter(path=>path.startsWith('/api/ladder-map?')).length,40);
assert.equal(calls.filter(path=>path.includes('/detail')).length,0);
assert.equal(cls('ladder-map-list-row').length,25);
assert.ok(cls('ladder-map-cluster').length>0&&cls('ladder-map-cluster').length<200);
assert.equal(cls('ladder-map-node').length,0);
assert.ok(all(root).length<2000);
assert.ok(cls('ladder-map-status')[0].textContent.includes('10,000 of 10,000'));
await controller.focus('rung-9876');await flush();
assert.deepEqual(inspected,['rung-9876']);
assert.ok(cls('ladder-map-node').length>0&&cls('ladder-map-node').length<=80);
const links=calls.filter(path=>path.includes('/links'));assert.ok(links.length>0);
assert.ok(new URL(links.at(-1),'http://local').searchParams.get('ids').split(',').length<=80);
const before=calls.length;project.revision=2;await controller.refresh();await flush();assert.equal(calls.length,before);
assert.ok(cls('is-selected').some(node=>node.attributes['data-rung-id']==='rung-9876'));
""")

    def test_list_paging_and_server_search_reach_beyond_first_index_page(self) -> None:
        self.run_js(r"""
const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await flush();
const page=cls('ladder-map-list-page')[0];page.value='396';page.fire('change');
assert.ok(cls('ladder-map-list-row').some(node=>node.textContent.includes('Rung 9876')));
await cls('ladder-map-list-row').find(node=>node.textContent.includes('Rung 9876')).fire('click');await flush();assert.equal(inspected.at(-1),'rung-9876');
const search=cls('ladder-map-search')[0];search.value='unusual identifier';search.fire('keydown',{key:'Enter'});await flush();
assert.ok(calls.some(path=>path.includes('query=unusual+identifier')));
assert.equal(cls('ladder-map-list-row').length,1);assert.ok(cls('ladder-map-list-row')[0].textContent.includes('9876'));
await controller.setRoutine('routine-1');await flush();assert.ok(calls.at(-1).includes('routine=routine-1')||calls.some(path=>path.includes('routine=routine-1')));
""")

    def test_cluster_tiles_use_nonoverlapping_screen_cells(self) -> None:
        self.run_js(r"""
count=271;const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await flush();
const clusters=cls('ladder-map-cluster');assert.ok(clusters.length>1);
const rects=clusters.map(node=>node.children.find(child=>child.tagName==='rect')).map(node=>Object.fromEntries(['x','y','width','height'].map(key=>[key,Number(node.attributes[key])])));
for(let i=0;i<rects.length;i++)for(let j=i+1;j<rects.length;j++){
 const a=rects[i],b=rects[j];const overlap=a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y;
 assert.equal(overlap,false,`overlapping cluster tiles ${i}, ${j}`);
}
assert.ok(clusters.every(node=>!node.textContent.includes('1 rungs')));
let stopped=false;clusters[0].fire('pointerdown',{stopPropagation(){stopped=true;}});assert.equal(stopped,true);
const before=cls('ladder-map-world')[0].attributes.transform;clusters[0].fire('click');await flush();assert.notEqual(cls('ladder-map-world')[0].attributes.transform,before);assert.ok(cls('ladder-map-node').length>0);
""")

    def test_new_run_and_new_search_ignore_old_pending_index_responses(self) -> None:
        self.run_js(r"""
const first=deferred(), second=deferred();let n=0;
respond=async url=>{if(url.pathname==='/api/ladder-map'){n++;return n===1?first.promise:second.promise;}return {run_id:project.active_run,signals:[],total:0,pages:1};};
const controller=window.PLCLadderMap.mount(root,options);const old=controller.refresh();
project={active_run:'run-2',revision:2};const newer=controller.refresh();
second.resolve({run_id:'run-2',total:1,pages:1,items:[rung(222)],routines:[],families:[]});await newer;
first.resolve({run_id:'run-1',total:999,pages:1,items:[rung(1)]});await old;await flush();
assert.equal(cls('ladder-map-list-row').length,1);assert.ok(cls('ladder-map-list-row')[0].textContent.includes('222'));
assert.ok(!cls('ladder-map-status')[0].textContent.includes('999'));
""")

    def test_declined_inspection_does_not_replace_selection_or_popout_target(self) -> None:
        self.run_js(r"""
count=20;const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await controller.focus('rung-1');await flush();
accept=false;assert.equal(await controller.focus('rung-2'),false);await flush();
button('Pop out selected source').fire('click');button('Pop out connections').fire('click');button('Pop out map').fire('click');button('Explore selected connections').fire('click');
assert.deepEqual(popouts,[['rung-1','source'],['rung-1','connections'],['rung-1','map']]);assert.deepEqual(connections,['rung-1']);assert.deepEqual(selections,['rung-1']);
""")

    def test_import_clears_snapshot_bound_filters_and_pinned_information(self) -> None:
        self.run_js(r"""
count=2;const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await controller.setRoutine('routine-1');await flush();
await controller.focus('rung-1');await flush();button('Pin information').fire('click');
project={active_run:'new-export',revision:8};await controller.refresh();await flush();
const requests=calls.filter(path=>path.startsWith('/api/ladder-map?'));const last=new URL(requests.at(-1),'http://local');
assert.equal(last.searchParams.get('run_id'),'new-export');assert.equal(last.searchParams.get('routine'),'');
assert.equal(cls('ladder-map-routine')[0].value,'');assert.ok(button('Pin information'));assert.ok(button('Pop out selected source').disabled);
const before=calls.length;await controller.refresh();await flush();assert.equal(calls.length,before);
""")

    def test_hover_cache_is_bounded_and_stale_hover_cannot_replace_current_information(self) -> None:
        self.run_js(r"""
count=2;const base=respond,waiting=deferred();respond=async url=>url.pathname.endsWith('/detail')&&url.searchParams.get('id')==='slow'?waiting.promise:base(url);
const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await flush();
const slow=new Element('button');controller.attachHover(slow,'slow');slow.fire('mouseenter');const timersBefore=[...timers.values()];timers.clear();timersBefore.forEach(fn=>fn());
const fast=new Element('button');controller.attachHover(fast,'fast');fast.fire('mouseenter');await flush();
waiting.resolve({run_id:'run-1',title:'Stale slow result',blocks:[]});await flush();assert.ok(!cls('ladder-map-detail-body')[0].textContent.includes('Stale slow'));
for(let i=0;i<81;i++){const item=new Element('button');controller.attachHover(item,'block-'+i);item.fire('mouseenter');await flush();}
const before=calls.filter(path=>path.includes('/detail')).length;const again=new Element('button');controller.attachHover(again,'block-0');again.fire('mouseenter');await flush();
assert.equal(calls.filter(path=>path.includes('/detail')).length,before+1);
""")

    def test_zoom_pan_node_drag_and_reset_are_view_only(self) -> None:
        self.run_js(r"""
count=20;const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await controller.focus('rung-1');await flush();
const canvas=cls('ladder-map-canvas')[0],world=cls('ladder-map-world')[0];const initial=world.attributes.transform;
button('Zoom in').fire('click');await flush();assert.notEqual(world.attributes.transform,initial);
const zoomed=world.attributes.transform;canvas.fire('pointerdown',{clientX:20,clientY:20});canvas.fire('pointermove',{clientX:80,clientY:70});canvas.fire('pointerup');await flush();assert.notEqual(world.attributes.transform,zoomed);
const before=inspected.length,node=cls('ladder-map-node').find(node=>node.attributes['data-rung-id']==='rung-1'),x=node.children[0].attributes.x;
node.fire('pointerdown',{clientX:100,clientY:100});canvas.fire('pointermove',{clientX:150,clientY:130});canvas.fire('pointerup');await flush();
assert.notEqual(cls('ladder-map-node').find(node=>node.attributes['data-rung-id']==='rung-1').children[0].attributes.x,x);assert.equal(inspected.length,before);
button('Reset layout').fire('click');await flush();assert.ok(calls.every(path=>path.startsWith('/api/ladder-map')));
""")

    def test_hover_is_delayed_cached_and_exposes_aoi_parameter_details(self) -> None:
        self.run_js(r"""
count=2;const base=respond;respond=async url=>url.pathname.endsWith('/detail')&&url.searchParams.get('id')==='aoi-1'?{run_id:project.active_run,id:'aoi-1',title:'Mixer AOI',description:'Invented definition',blocks:[],parameters:[{name:'Enable',attributes:{DataType:'BOOL',Usage:'Input'},description:'Enables the object'}],links:[],limitations:[]}:base(url);
const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await flush();
const node=cls('ladder-map-node')[0];node.fire('mouseenter');node.fire('mouseleave');await flush();assert.equal(calls.filter(path=>path.includes('/detail')).length,0);
node.fire('mouseenter');await flush();assert.equal(calls.filter(path=>path.includes('/detail')).length,1);assert.ok(cls('ladder-map-detail-body')[0].textContent.includes('Examine Boolean state'));
node.fire('mouseenter');await flush();assert.equal(calls.filter(path=>path.includes('/detail')).length,1);
button('Pin information').fire('click');
button('Invented AOI definition').fire('click');await flush();assert.ok(cls('ladder-map-detail-body')[0].textContent.includes('BOOL'));assert.ok(cls('ladder-map-detail-body')[0].textContent.includes('Enables the object'));
node.fire('mouseenter');await flush();assert.ok(cls('ladder-map-detail-body')[0].textContent.includes('Mixer AOI'));
const card=new Element('section');controller.attachHover(card,'instruction-9','Captured instruction');assert.equal(card.attributes.title,'Captured instruction');
controller.destroy();card.fire('mouseenter');await flush();assert.equal(root.children.length,0);
""")

    def test_signal_roles_unknown_links_and_offscreen_filter_are_explicit(self) -> None:
        self.run_js(r"""
count=2;const base=respond;respond=async url=>url.pathname.endsWith('/links')?{run_id:project.active_run,signals:[{id:'signal-1',label:'Plant_Flag',readers:['rung-1'],writers:['rung-0'],unknown:['rung-1'],outside_counts:{readers:200,writers:0,unknown:3},totals:{readers:201,writers:1,unknown:4}}],total:81,page:Number(url.searchParams.get('page')),pages:2,notice:'Recorded associations only.'}:base(url);
const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await flush();
await controller.setRoutine('routine-1');await flush();
assert.ok(cls('ladder-map-signal-row')[0].textContent.includes('outside view: 0 writers, 200 readers, 3 unknown'));
const unknown=cls('ladder-map-edge').find(node=>node.attributes.class.includes('unknown'));assert.ok(unknown);assert.equal(unknown.attributes['marker-end'],undefined);
const writer=cls('ladder-map-edge').find(node=>node.attributes.class.includes('writer'));assert.ok(writer.attributes['marker-end']);
let signalStopped=false;cls('ladder-map-signal')[0].fire('pointerdown',{stopPropagation(){signalStopped=true;}});assert.equal(signalStopped,true);
button('Next signals').fire('click');await flush();assert.ok(calls.some(path=>path.includes('/links')&&path.includes('page=2')));
button('Plant_Flag').fire('click');await flush();assert.ok(calls.some(path=>path.startsWith('/api/ladder-map?')&&path.includes('signal_id=signal-1')));
const signalRequest=new URL(calls.filter(path=>path.startsWith('/api/ladder-map?')).at(-1),'http://local');assert.equal(signalRequest.searchParams.get('routine'),'');assert.equal(signalRequest.searchParams.get('query'),'');assert.equal(signalRequest.searchParams.get('family'),'');
assert.ok(cls('ladder-map-list-row')[0].textContent.includes('9876'));button('Clear signal filter').fire('click');await flush();assert.equal(cls('ladder-map-list-row').length,2);
""")

    def test_api_failure_has_retry_and_destroy_ignores_late_results(self) -> None:
        self.run_js(r"""
count=2;const base=respond;let fail=true;respond=async url=>{if(fail&&url.pathname==='/api/ladder-map')throw new Error('Saved index unavailable');return base(url);};
const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await flush();assert.ok(!cls('ladder-map-error')[0].hidden);assert.ok(root.textContent.includes('Saved index unavailable'));
fail=false;button('Retry').fire('click');await flush();assert.equal(cls('ladder-map-list-row').length,2);
const waiting=deferred();respond=async()=>waiting.promise;project.active_run='run-2';const load=controller.refresh();controller.destroy();waiting.resolve({run_id:'run-2',total:1,pages:1,items:[rung(1)]});await load;await flush();assert.equal(root.children.length,0);
""")

    def test_old_inspection_failure_cannot_replace_new_success(self) -> None:
        self.run_js(r"""
count=3;let rejectOld;const oldFailure=new Promise((_,reject)=>rejectOld=reject);
options.inspect=id=>id==='rung-0'?oldFailure:Promise.resolve(true);
const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await flush();
const old=controller.focus('rung-0');await Promise.resolve();await controller.focus('rung-1');await flush();
rejectOld(new Error('Stale inspection failure'));await old;await flush();
assert.ok(cls('ladder-map-error')[0].hidden);button('Pop out selected source').fire('click');assert.deepEqual(popouts,[['rung-1','source']]);
""")

    def test_mismatched_run_response_is_visible_and_retryable(self) -> None:
        self.run_js(r"""
count=2;const base=respond;let stale=true;
respond=async url=>url.pathname==='/api/ladder-map'&&stale?index(url,{run_id:'old-run'}):base(url);
const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await flush();
assert.ok(!cls('ladder-map-error')[0].hidden);assert.ok(root.textContent.includes('active analysis changed'));
stale=false;button('Retry').fire('click');await flush();assert.equal(cls('ladder-map-list-row').length,2);
""")

    def test_declaration_inspection_failure_is_controlled_without_reclassifying_selection(self) -> None:
        self.run_js(r"""
count=2;const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await controller.focus('rung-1');await flush();
button('Pin information').fire('click');
button('Invented AOI definition').fire('click');await flush();
let fail=true;options.inspect=async id=>{if(fail&&id==='aoi-1')throw new Error('Source request failed');return true;};
await button('Inspect source').fire('click');await flush();assert.ok(cls('ladder-map-error')[0].textContent.includes('Source request failed'));
fail=false;button('Retry').fire('click');await flush();assert.ok(cls('ladder-map-error')[0].hidden);
button('Pop out selected source').fire('click');assert.deepEqual(popouts,[['rung-1','source']]);
""")

    def test_unpinned_preview_does_not_capture_clicks_and_toolbar_controls_pin_links(self) -> None:
        css = (ASSETS / "ladder-map.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.ladder-map-detail \{[^}]*pointer-events: none;")
        self.assertRegex(css, r"\.ladder-map-detail\.is-pinned \{[^}]*pointer-events: auto;")
        self.run_js(r"""
count=2;const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await controller.focus('rung-0');await flush();
const box=cls('ladder-map-detail')[0],toolbar=cls('ladder-map-view-controls')[0],stage=cls('ladder-map-stage')[0];
assert.ok(all(toolbar).includes(button('Pin information')));assert.ok(all(toolbar).includes(button('Close information')));assert.ok(!all(stage).includes(button('Pin information')));
assert.ok(!box.className.includes('is-pinned'));assert.ok(button('Invented AOI definition').disabled);assert.ok(box.textContent.includes('Pin information to follow its links'));
button('Pin information').fire('click');assert.ok(box.className.includes('is-pinned'));assert.equal(button('Invented AOI definition').disabled,false);
button('Unpin information').fire('click');assert.ok(!box.className.includes('is-pinned'));assert.equal(button('Invented AOI definition').disabled,true);
await controller.focus('rung-1');await flush();assert.equal(selections.at(-1),'rung-1');
button('Close information').fire('click');assert.ok(box.hidden);assert.ok(button('Pin information').disabled);
""")

    def test_pinning_inflight_hover_after_leaving_card_finishes_same_request(self) -> None:
        self.run_js(r"""
count=2;const base=respond,waiting=deferred();respond=async url=>url.pathname.endsWith('/detail')?waiting.promise:base(url);
const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await flush();
const node=cls('ladder-map-node')[0];node.fire('mouseenter');
const callbacks=[...timers.values()];timers.clear();const pendingDisplays=callbacks.map(fn=>fn());
assert.ok(cls('ladder-map-detail-body')[0].textContent.includes('Loading captured'));
node.fire('mouseleave');button('Pin information').fire('click');
waiting.resolve({run_id:'run-1',id:'rung-0',title:'Slow source loaded successfully',blocks:[],links:[{id:'aoi-1',label:'Open the captured definition'}]});
await Promise.all(pendingDisplays);await flush();
assert.equal(calls.filter(path=>path.includes('/detail')).length,1);
assert.ok(cls('ladder-map-detail-body')[0].textContent.includes('Slow source loaded successfully'));
assert.ok(!cls('ladder-map-detail-body')[0].textContent.includes('Loading captured'));
assert.ok(cls('ladder-map-detail')[0].className.includes('is-pinned'));assert.equal(button('Open the captured definition').disabled,false);
""")

    def test_connection_coverage_and_unavailable_evidence_remain_visible(self) -> None:
        self.run_js(r"""
count=2;const base=respond;let available=true;
respond=async url=>{
 if(url.pathname==='/api/ladder-map')return index(url,{connection_available:available,connection_notice:available?'Exact captured addresses only.':'Saved access evidence did not qualify.'});
 if(url.pathname.endsWith('/links'))return {run_id:project.active_run,available:true,signals:[],total:0,pages:1,coverage:{unparsed_rungs:3,unresolved_uses:17,unknown_roles:8,invalid_expanded_addresses:2,unqualified_rungs:4,unqualified_uses:6,unqualified_visible_rungs:1,unqualified_visible_uses:2,rejected_signal_count:5,calculation_reads_available:false,implicit_effects_available:false,member_overlap_available:false}};
 return base(url);
};
const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();
assert.ok(cls('ladder-map-coverage')[0].textContent.includes('Exact captured addresses only.'));await flush();
const text=cls('ladder-map-coverage')[0].textContent;
for(const expected of ['3 unparsed rungs','17 unresolved address uses','8 uses with unknown read/write roles','2 addresses without a valid expanded identity','4 source-unqualified rungs in the analysis','6 source-unqualified address uses in the analysis','1 source-unqualified visible rungs','2 source-unqualified visible address uses','5 signals omitted from this connection view','calculation expression reads','implicit instruction effects','whole structures/arrays','Missing lines do not mean'])assert.ok(text.includes(expected),expected);
const before=calls.filter(path=>path.includes('/links')).length;available=false;project.active_run='unavailable-run';await controller.refresh();await flush();
assert.equal(calls.filter(path=>path.includes('/links')).length,before);
assert.ok(cls('ladder-map-coverage')[0].textContent.includes('Connection map unavailable'));
assert.ok(cls('ladder-map-coverage')[0].textContent.includes('Saved access evidence did not qualify.'));
assert.ok(!cls('ladder-map-coverage')[0].textContent.includes('17 unresolved'));assert.equal(cls('ladder-map-list-row').length,2);
""")

    def test_close_cancels_queued_preview_and_late_results_do_not_reopen_it(self) -> None:
        self.run_js(r"""
count=2;const base=respond,waiting=deferred();let wait=false;
respond=async url=>wait&&url.pathname.endsWith('/detail')?waiting.promise:base(url);
const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await controller.focus('rung-0');await flush();
const node=cls('ladder-map-node').find(node=>node.attributes['data-rung-id']==='rung-1');
const before=calls.filter(path=>path.includes('/detail')).length;node.fire('mouseenter');button('Close information').fire('click');await flush();
assert.equal(calls.filter(path=>path.includes('/detail')).length,before);assert.ok(cls('ladder-map-detail')[0].hidden);
wait=true;node.fire('mouseenter');const callbacks=[...timers.values()];timers.clear();const pendingDisplays=callbacks.map(fn=>fn());
button('Pin information').fire('click');assert.equal(cls('ladder-map-detail-local-controls')[0].hidden,false);
button('Close panel').fire('click');waiting.resolve({run_id:'run-1',id:'rung-1',title:'Late response',blocks:[]});await Promise.all(pendingDisplays);await flush();
assert.ok(cls('ladder-map-detail')[0].hidden);assert.ok(!cls('ladder-map-detail')[0].className.includes('is-pinned'));assert.ok(button('Pin information').disabled);
""")

    def test_mouseleave_and_cancelled_second_hover_cannot_freeze_loading_preview(self) -> None:
        self.run_js(r"""
count=2;const base=respond,waiting=deferred();respond=async url=>url.pathname.endsWith('/detail')?waiting.promise:base(url);
const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await flush();
const nodes=cls('ladder-map-node');nodes[0].fire('mouseenter');const callbacks=[...timers.values()];timers.clear();const pendingDisplays=callbacks.map(fn=>fn());
nodes[0].fire('mouseleave');nodes[1].fire('mouseenter');nodes[1].fire('mouseleave');
waiting.resolve({run_id:'run-1',id:'rung-0',title:'First preview finished',blocks:[]});await Promise.all(pendingDisplays);await flush();
assert.equal(calls.filter(path=>path.includes('/detail')).length,1);assert.ok(cls('ladder-map-detail-body')[0].textContent.includes('First preview finished'));assert.ok(!cls('ladder-map-detail-body')[0].textContent.includes('Loading captured'));
""")

    def test_local_unpin_escape_pan_and_deactivation_dismiss_without_losing_index(self) -> None:
        self.run_js(r"""
count=2;const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await controller.focus('rung-0');await flush();
button('Pin information').fire('click');assert.ok(all(cls('ladder-map-detail')[0]).includes(button('Close panel')));button('Unpin panel').fire('click');
assert.equal(cls('ladder-map-detail-local-controls')[0].hidden,true);assert.ok(!cls('ladder-map-detail')[0].className.includes('is-pinned'));
button('Pin information').fire('click');document.fire('keydown',{key:'Escape'});assert.ok(cls('ladder-map-detail')[0].hidden);
await controller.focus('rung-0');await flush();button('Pin information').fire('click');cls('ladder-map-canvas')[0].fire('pointerdown');assert.ok(cls('ladder-map-detail')[0].hidden);cls('ladder-map-canvas')[0].fire('pointerup');
const node=cls('ladder-map-node')[0];node.fire('mouseenter');controller.deactivate();await flush();assert.ok(cls('ladder-map-detail')[0].hidden);
node.fire('mouseenter');await flush();assert.ok(cls('ladder-map-detail')[0].hidden);
const indexed=calls.filter(path=>path.startsWith('/api/ladder-map?')).length;await controller.refresh();await flush();assert.equal(calls.filter(path=>path.startsWith('/api/ladder-map?')).length,indexed);
node.fire('mouseenter');await flush();assert.equal(cls('ladder-map-detail')[0].hidden,false);
controller.destroy();assert.equal(document.events.keydown,undefined);
""")

    def test_deactivate_ignores_loading_details_and_escape_cancels_unopened_hover(self) -> None:
        self.run_js(r"""
count=2;const base=respond,waiting=deferred();respond=async url=>url.pathname.endsWith('/detail')?waiting.promise:base(url);
const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await flush();
const node=cls('ladder-map-node')[0];node.fire('mouseenter');document.fire('keydown',{key:'Escape'});await flush();assert.equal(calls.filter(path=>path.includes('/detail')).length,0);
node.fire('mouseenter');const callbacks=[...timers.values()];timers.clear();const displays=callbacks.map(fn=>fn());controller.deactivate();
waiting.resolve({run_id:'run-1',id:'rung-0',title:'While hidden',blocks:[]});await Promise.all(displays);await flush();assert.ok(cls('ladder-map-detail')[0].hidden);
""")

    def test_description_and_signal_name_toggles_use_captured_text_with_bounded_cards(self) -> None:
        self.run_js(r"""
count=2;const base=respond;respond=async url=>{
 if(url.pathname==='/api/ladder-map')return index(url,{items:[{...rung(0),comment_preview:'<script>Une description mixte avec un très long commentaire réel qui ne doit jamais devenir du HTML et qui continue après la troisième ligne.'},{...rung(1),comment_preview:''}]});
 if(url.pathname.endsWith('/links'))return {run_id:'run-1',signals:[{id:'flag',label:'Captured_Flag',writers:['rung-0'],readers:['rung-1'],unknown:[]}],total:1,pages:1};
 return base(url);
};
const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await flush();assert.equal(cls('ladder-map-node-comment').length,0);assert.equal(cls('ladder-map-signal-label').length,0);
const before=calls.length,descriptions=cls('ladder-map-description-toggle')[0],names=cls('ladder-map-signal-names-toggle')[0];
descriptions.checked=true;descriptions.fire('change');names.checked=true;names.fire('change');await flush();
assert.ok(cls('ladder-map-node-comment').length<=6);assert.ok(cls('ladder-map-node').some(node=>node.textContent.includes('No rung comment captured.')));
assert.ok(cls('ladder-map-node-comment').some(node=>node.textContent.includes('<script>')));assert.ok(all(root).every(node=>node.tagName!=='script'));assert.equal(cls('ladder-map-signal-label')[0].textContent,'Captured_Flag');
assert.equal(calls.length,before);descriptions.checked=false;descriptions.fire('change');names.checked=false;names.fire('change');await flush();assert.equal(cls('ladder-map-node-comment').length,0);assert.equal(cls('ladder-map-signal-label').length,0);
const help=cls('ladder-map-help')[0];for(const phrase of ['not execution order','Teal arrows','Orange dashed lines','reviewed AI','Escape','80 individual cards','320 connection lines','No rung comment'])assert.ok(root.textContent.toLowerCase().includes(phrase.toLowerCase())||help.textContent.toLowerCase().includes(phrase.toLowerCase()),phrase);
""")

    def test_leaving_during_search_preserves_query_without_reactivating_hidden_map(self) -> None:
        self.run_js(r"""
count=2;const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await flush();
const before=calls.length,search=cls('ladder-map-search')[0];search.value='late search';search.fire('input');controller.deactivate();await flush();
assert.equal(calls.length,before);assert.ok(cls('ladder-map-detail')[0].hidden);
await controller.refresh();await flush();assert.ok(calls.some(path=>path.startsWith('/api/ladder-map?')&&path.includes('query=late+search')));assert.equal(cls('ladder-map-list-row').length,1);
""")

    def test_changed_run_detail_ends_loading_with_recovery_message(self) -> None:
        self.run_js(r"""
count=2;const base=respond;respond=async url=>url.pathname.endsWith('/detail')?{run_id:'different-run',title:'Stale source',blocks:[]}:base(url);
const controller=window.PLCLadderMap.mount(root,options);await controller.refresh();await controller.focus('rung-0');await flush();
const body=cls('ladder-map-detail-body')[0];assert.ok(body.textContent.includes('analysis changed'));assert.ok(!body.textContent.includes('Loading captured'));assert.ok(button('Retry information'));
""")
