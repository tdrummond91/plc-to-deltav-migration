"""Viewport-loaded full ladders and adjustable pages preserve source and selections."""
from __future__ import annotations

import subprocess
import unittest

from test_workspace_ui import DOM, NODE, RUNG_LIST_DOM, function


@unittest.skipUnless(NODE, 'Node is optional developer UI tooling')
class WorkspacePagingUiTests(unittest.TestCase):
    def run_js(self, names: list[str], checks: str, setup: str = '') -> None:
        dom = DOM
        for name in ('loadRungs', 'openSource', 'loadObjects'):
            if name in names:
                if name == 'loadObjects':
                    dom = dom.replace(', loadObjects;', ';')
                else:
                    dom = dom.replace(f'const {name}=async()=>{{}};', '').replace(f'let {name}=async()=>{{}};', '')
        code = dom + setup + '\n' + '\n'.join(function(name) for name in names)
        code += '\n(async()=>{\n' + checks + '\n})().catch(error=>{console.error(error);process.exitCode=1;});'
        result = subprocess.run([NODE, '-'], input=code, encoding='utf-8', capture_output=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_full_ladder_waits_for_viewport_preserves_every_instruction_and_bounds_concurrency(self):
        self.run_js(['pumpRungPreviews', 'renderRungPreview'], r"""
state={...state,project:{active_run:'run-a',project_path:'project-a'},listSerial:1,view:'rungs',rungPreviewQueue:[],rungPreviewLoading:0};
const requests=[],renders=[],pending=[];let observer;
$=()=>node('div');
window.IntersectionObserver=class{constructor(callback){this.callback=callback;observer=this;}observe(){}unobserve(){}};
window.PLCLadderDiagram={render:(source,options)=>{renders.push({source,options});return node('div','Full '+source.id);}};
api=url=>{requests.push(new URL(url,'http://local'));return new Promise(resolve=>pending.push(resolve));};
const previews=Array.from({length:8},(_,i)=>renderRungPreview({id:'rung-'+i,preview:{instructions:[{id:'truncated'}]}}));
const tick=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
await tick();assert.equal(requests.length,0);
observer.callback(previews.map(target=>({target,isIntersecting:true})));await tick();
assert.equal(requests.length,3);assert.equal(state.rungPreviewLoading,3);
const source={id:'rung-0',instructions:Array.from({length:40},(_,i)=>({id:'i-'+i})),structure:{kind:'branch',legs:[]}};
pending[0]({source,run_id:'run-a',source_qualified:true});await tick();
assert.equal(requests.length,4);assert.equal(renders.length,1);assert.equal(renders[0].source,source);
assert.equal(renders[0].source.instructions.length,40);assert.equal(renders[0].options.sourceQualified,true);
assert.deepEqual(renders[0].options.helpContext,{runId:'run-a'});
assert.ok(requests.every(url=>url.searchParams.get('run_id')==='run-a'));
state.listSerial++;state.rungPreviewQueue=[];
for(let i=1;i<pending.length;i++)pending[i]({source:{id:'rung-'+i},run_id:'run-a',source_qualified:true});
await tick();assert.equal(renders.length,1);assert.equal(requests.length,4);assert.equal(state.rungPreviewLoading,0);
""")

    def test_lazy_ladder_mismatched_source_can_be_retried_without_changing_review(self):
        self.run_js(['pumpRungPreviews', 'renderRungPreview'], r"""
state={...state,project:{active_run:'run-a',project_path:'project-a'},listSerial:1,view:'rungs',rungPreviewQueue:[],rungPreviewLoading:0,dirty:true};
let count=0;const renders=[];
window.PLCLadderDiagram={render:(source,options)=>{renders.push(options);return node('div','Complete ladder');}};
api=async()=>{count++;return {run_id:count===1?'other-run':'run-a',source:{id:'rung-a'},source_qualified:false};};
const preview=renderRungPreview({id:'rung-a'}),tick=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
descendants(preview).find(n=>n.textContent==='Load full ladder').events.click();await tick();
assert.equal(renders.length,0);assert.ok(contents(preview).includes('source changed'));
descendants(preview).find(n=>n.textContent==='Retry ladder').events.click();await tick();
assert.equal(renders.length,1);assert.equal(renders[0].sourceQualified,false);assert.equal(state.dirty,true);
""")

    def test_rung_page_size_resets_page_preserves_filters_and_off_page_selection(self):
        setup = RUNG_LIST_DOM.replace('const pagination=()=>{};', '')
        self.run_js(['pageSizeControl', 'pagination', 'loadRungs'], r"""
state.page=3;state.rungPageSize=50;state.source={source:{id:'keep'}};
state.selected=new Set(['off-page']);$('rung-search').value='Valve';$('category-filter').value='di';
let request;
api=async url=>{request=new URL(url,'http://local');return {items:[rungRow('visible',1)],total:600,page:state.page,page_size:state.rungPageSize};};
await loadRungs();const picker=descendants($('rung-pagination')).find(n=>n.tagName==='select');
picker.value='200';await picker.events.change();await Promise.resolve();
assert.equal(request.searchParams.get('page'),'1');assert.equal(request.searchParams.get('page_size'),'200');
assert.equal(request.searchParams.get('query'),'Valve');assert.equal(request.searchParams.get('category'),'di');
assert.ok(state.selected.has('off-page'));assert.equal(state.source.source.id,'keep');
const heading=descendants($('rung-list')).find(n=>n.className==='rung-card-heading');
assert.deepEqual(heading.children.map(n=>n.className),['rung-card-number','rung-card-hierarchy','rung-card-tools']);
assert.equal(heading.children[2].children.at(-1).textContent,'Open rung');
""", setup)
