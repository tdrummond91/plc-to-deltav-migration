"""Hover lifetime, independent windows and saved-source binding using invented data."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from test_workspace_ui import ASSETS, NODE

SCRIPT = (ASSETS / 'instruction-help.js').read_text(encoding='utf-8')
DOM = r"""
const assert=require('node:assert/strict');
class Element {
 constructor(tag){this.tagName=tag;this.children=[];this.events={};this.attributes={};this.style={};this.dataset={};this._text='';this.disabled=false;this.className='';this.parent=null;
 this.classList={add:name=>{this.className+=' '+name;}};}
 append(...children){for(const child of children){child.parent=this;this.children.push(child);}}
 replaceChildren(...children){for(const child of this.children)child.parent=null;this.children=[];this._text='';this.append(...children);}
 set textContent(value){this.replaceChildren();this._text=String(value);}
 get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
 setAttribute(name,value){this.attributes[name]=String(value);}
 getAttribute(name){return this.attributes[name]??null;}
 hasAttribute(name){return name in this.attributes;}
 removeAttribute(name){delete this.attributes[name];}
 addEventListener(name,fn,capture=false){(this.events[name]??=[]).push({fn,capture});}
 fire(name,options={}){const event={type:name,target:this,relatedTarget:null,prevented:false,stopped:false,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;},...options};
 for(const {fn} of [...this.events[name]||[]].sort((a,b)=>Number(b.capture)-Number(a.capture))){fn(event);if(event.stopped)break;}return event;}
 contains(node){return node===this||this.children.some(child=>child.contains(node));}
 closest(selector){if(selector==='dialog[open]'&&this.tagName==='dialog'&&this.open)return this;if(selector==='[data-source-variable]'&&this.hasAttribute('data-source-variable'))return this;return this.parent?.closest(selector)||null;}
 remove(){if(this.parent)this.parent.children=this.parent.children.filter(c=>c!==this);this.parent=null;}
 get isConnected(){return this===document.body||!!this.parent?.isConnected;}
 getClientRects(){return this.isConnected&&!this.hidden?[this.getBoundingClientRect()]:[];}
 getBoundingClientRect(){return this.rect||{top:40,left:30,right:180,bottom:100,width:500,height:Math.min(450,parseFloat(this.style.maxHeight)||450)};}
 querySelectorAll(selector){return all(this).slice(1).filter(n=>selector==='title, [title]'?(n.tagName==='title'||n.hasAttribute('title')):selector==='[data-source-variable]'?n.hasAttribute('data-source-variable'):selector.startsWith('.')?n.className.split(' ').includes(selector.slice(1)):false);}
 querySelector(selector){if(selector==='button:not(:disabled)')return all(this).find(n=>n.tagName==='button'&&!n.disabled);return this.querySelectorAll(selector)[0]||null;}
 focus(){document.activeElement=this;this.fire('focusin');}
}
const all=node=>[node,...node.children.flatMap(all)];
const document=new Element('document');document.body=new Element('body');document.documentElement=new Element('html');document.documentElement.dataset.theme='dark';document.activeElement=null;
document.createElement=tag=>new Element(tag);document.getElementById=id=>all(document.body).find(n=>n.id===id)||null;
const window=new Element('window');window.location={origin:'http://127.0.0.1:8753',search:''};window.innerWidth=1200;window.innerHeight=850;
const opened=[];window.open=(url,target,features)=>{const popup={opener:window};opened.push({url,target,features,popup});return popup;};
window.PLCInstructionHelpContent={valid:row=>!!row&&typeof row.opcode==='string'&&Array.isArray(row.arguments),render:row=>{const section=new Element('section');section.textContent=row.opcode+' '+row.arguments.join(', ');return section;}};
window.PLCVariableHelpContent={render:data=>{const section=new Element('section');section.textContent='Variable '+data.variable+' '+(data.member?.meaning||'unresolved');return section;}};
let nextTimer=0;const timers=new Map();function setTimeout(fn,ms){const id=++nextTimer;timers.set(id,{fn,ms});return id;}function clearTimeout(id){timers.delete(id);}
function tick(ms){for(const [id,item] of [...timers])if(item.ms<=ms){timers.delete(id);item.fn();}}
let observed;class MutationObserver{constructor(fn){observed=fn;}observe(){}}
const panel=()=>document.getElementById('instruction-hover-help');
const anchor=()=>{const node=new Element('g');document.body.append(node);return node;};
const instruction=(id='inst:one')=>({id,opcode:'ADD',arguments:['A','B','Output']});
const variableNode=(parent,name)=>{const token=new Element('tspan');token.setAttribute('data-source-variable',name);token.textContent=name.slice(0,8)+'…';parent.append(token);return token;};
const variableData=(variable='Delay.PRE',run='run:one',id='inst:one')=>({variable,run_id:run,instruction_id:id,available:true,historical:false,binding:{status:'root_bound'},member:{meaning:'Verified preset'},captured_values:[],writers:[],limitations:[]});
async function flush(){for(let i=0;i<12;i++)await Promise.resolve();}
"""


@unittest.skipUnless(NODE, 'Node is optional developer tooling')
class InstructionHelpUiTests(unittest.TestCase):
    def run_js(self, checks: str, setup: str = '') -> None:
        code = DOM + setup + SCRIPT + '\n(async()=>{\n' + checks
        code += "\n})().then(()=>process.stdout.write('HELP_OK\\n')).catch(error=>{console.error(error);process.exitCode=1;});"
        result = subprocess.run([NODE, '-'], input=code, capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('HELP_OK', result.stdout)

    def test_hover_can_cross_gap_into_panel_and_close_outside(self) -> None:
        self.run_js(r"""
const node=anchor();window.PLCInstructionHelp.configure({getContext:()=>({runId:'run:first'})});window.PLCInstructionHelp.attach(node,instruction());
node.fire('pointerenter');assert.equal(panel(),null);tick(240);assert.ok(panel());
node.fire('pointerleave');panel().fire('pointerenter');tick(350);assert.ok(panel());
panel().fire('pointerleave');tick(350);assert.equal(panel(),null);
node.fire('pointerenter');tick(240);document.fire('pointerdown',{target:document.body});assert.equal(panel(),null);
node.fire('pointerenter');document.fire('pointerdown',{target:document.body});tick(240);assert.equal(panel(),null);
""")

    def test_short_hover_does_not_open_and_new_hover_replaces_pending(self) -> None:
        self.run_js(r"""
const a=anchor(),b=anchor();window.PLCInstructionHelp.attach(a,instruction());window.PLCInstructionHelp.attach(b,{...instruction('inst:two'),opcode:'MUL'});
a.fire('pointerenter');a.fire('pointerleave');tick(240);assert.equal(panel(),null);
a.fire('pointerenter');b.fire('pointerenter');tick(240);assert.ok(panel().textContent.includes('MUL'));
assert.equal(a.getAttribute('aria-expanded'),'false');assert.equal(b.getAttribute('aria-expanded'),'true');
""")

    def test_ctrl_click_opens_distinct_windows_and_preserves_captured_run(self) -> None:
        self.run_js(r"""
let run='run:first',selected=0;const node=anchor(),row=instruction();
window.PLCInstructionHelp.configure({getContext:()=>({runId:run})});
node.addEventListener('click',()=>selected++);window.PLCInstructionHelp.attach(node,row);
run='run:second';row.arguments[0]='Changed';row.id='inst:changed';
node.fire('click');assert.equal(selected,1);assert.equal(opened.length,0);
for(let i=0;i<2;i++){const e=node.fire('click',{ctrlKey:true});assert.ok(e.prevented);assert.ok(e.stopped);}
assert.equal(selected,1);assert.equal(opened.length,2);
for(const item of opened){const url=new URL(item.url);assert.equal(item.target,'_blank');assert.equal(item.popup.opener,null);assert.equal(url.searchParams.get('id'),'inst:one');assert.equal(url.searchParams.get('run_id'),'run:first');assert.equal(url.searchParams.has('arguments'),false);}
assert.ok(panel().textContent.includes('A, B, Output'));assert.ok(!panel().textContent.includes('Changed'));
""")

    def test_keyboard_help_and_popout_do_not_trigger_normal_selection(self) -> None:
        self.run_js(r"""
let normal=0;const node=anchor();window.PLCInstructionHelp.attach(node,instruction(),{runId:'run:one'});node.addEventListener('keydown',()=>normal++);
const f1=node.fire('keydown',{key:'F1'});assert.ok(f1.prevented);assert.equal(normal,0);assert.equal(document.activeElement.tagName,'button');
document.fire('scroll',{target:document.body});assert.ok(panel());
document.fire('keydown',{key:'Escape'});assert.equal(panel(),null);assert.equal(document.activeElement,node);
node.fire('keydown',{key:'Enter',ctrlKey:true});assert.equal(opened.length,1);assert.equal(normal,0);
node.fire('keydown',{key:'Enter'});assert.equal(normal,1);
node.fire('click',{metaKey:true});assert.equal(opened.length,2);
""")

    def test_pointer_focus_cannot_insert_panel_before_ctrl_click_completes(self) -> None:
        self.run_js(r"""
const node=anchor();window.PLCInstructionHelp.attach(node,instruction(),{runId:'run:one'});
node.fire('pointerenter');node.fire('pointerdown');node.focus();tick(240);assert.equal(panel(),null);
document.fire('pointerup',{target:node});node.fire('click',{ctrlKey:true});assert.equal(opened.length,1);assert.ok(panel());
window.PLCInstructionHelp.close();node.fire('pointerdown');document.fire('pointercancel');node.fire('focusin');assert.ok(panel());
window.PLCInstructionHelp.close();node.fire('pointerdown');window.fire('blur');node.fire('focusin');assert.ok(panel());
""")

    def test_blocked_window_offers_user_activated_link(self) -> None:
        self.run_js(r"""
window.open=()=>null;const node=anchor();window.PLCInstructionHelp.attach(node,instruction(),{runId:'run:one'});
node.fire('click',{ctrlKey:true});assert.ok(panel().textContent.includes('blocked'));
const link=all(panel()).find(n=>n.tagName==='a');assert.equal(link.target,'_blank');assert.equal(link.rel,'noopener');assert.equal(new URL(link.href).pathname,'/instruction-help.html');
node.fire('click',{ctrlKey:true});assert.equal(all(panel()).filter(n=>n.className==='instruction-help-blocked').length,1);
""")

    def test_removal_page_scroll_and_hidden_anchors_dismiss_panel(self) -> None:
        self.run_js(r"""
const node=anchor();window.PLCInstructionHelp.attach(node,instruction(),{runId:'run:one'});
node.fire('pointerenter');tick(240);document.fire('scroll',{target:panel()});assert.ok(panel());
document.fire('scroll',{target:document.body});assert.equal(panel(),null);
node.fire('pointerenter');tick(240);node.hidden=true;observed();assert.equal(panel(),null);
node.hidden=false;node.fire('pointerenter');node.remove();observed();tick(240);assert.equal(panel(),null);
""")

    def test_native_titles_removed_and_bad_context_cannot_open_window(self) -> None:
        self.run_js(r"""
const node=anchor();node.setAttribute('title','old');const title=new Element('title'),nested=new Element('span');nested.setAttribute('title','nested');node.append(title,nested);
window.PLCInstructionHelp.attach(node,instruction(),{runId:''});window.PLCInstructionHelp.attach(node,instruction(),{runId:'later'});
assert.equal(node.getAttribute('title'),null);assert.equal(nested.getAttribute('title'),null);assert.ok(!node.children.includes(title));assert.equal(node.getAttribute('tabindex'),'0');
node.fire('click',{ctrlKey:true});assert.equal(opened.length,0);assert.equal(all(panel()).find(n=>n.textContent==='Open help window ↗').disabled,true);
""")

    def test_panel_clamps_to_small_viewport(self) -> None:
        self.run_js(r"""
const node=anchor();node.rect={top:790,left:1100,right:1190,bottom:830,width:90,height:40};window.PLCInstructionHelp.attach(node,instruction());node.fire('pointerenter');tick(240);
assert.ok(parseFloat(panel().style.left)>=12);assert.ok(parseFloat(panel().style.left)+500<=1188);assert.ok(parseFloat(panel().style.top)+450<=838);
""")

    def test_vertical_fallback_uses_available_gap_without_covering_block(self) -> None:
        self.run_js(r"""
window.innerWidth=900;const node=anchor();node.rect={top:300,left:350,right:550,bottom:400,width:200,height:100};
window.PLCInstructionHelp.attach(node,instruction());node.fire('pointerenter');tick(240);
assert.ok(parseFloat(panel().style.top)>=410);assert.ok(parseFloat(panel().style.top)+panel().getBoundingClientRect().height<=838);
assert.ok(parseFloat(panel().style.maxHeight)<450);
""")

    def test_help_inside_native_dialog_shares_its_top_layer(self) -> None:
        self.run_js(r"""
const dialog=new Element('dialog');dialog.open=true;document.body.append(dialog);const node=new Element('span');dialog.append(node);
window.PLCInstructionHelp.attach(node,instruction(),{runId:'run:historical'});node.fire('keydown',{key:'F1'});
assert.equal(panel().parent,dialog);assert.ok(dialog.contains(document.activeElement));
node.fire('click',{ctrlKey:true});assert.equal(new URL(opened[0].url).searchParams.get('run_id'),'run:historical');
dialog.remove();observed();assert.equal(panel(),null);
""")

    def test_popout_fetches_explicit_run_and_validates_response(self) -> None:
        setup = r"""
const root=new Element('main');root.id='instruction-help-window';document.body.append(root);
window.location.search='?id=inst%3Aone&run_id=run%3Aold&theme=light';const requests=[];
async function fetch(url,options){requests.push({url,options});return{ok:true,json:async()=>({source:instruction(),run_id:'run:old',kind:'instruction',historical:true,path:'Invented / Rung 0'})};}
"""
        self.run_js(r"""
await flush();assert.equal(requests.length,1);assert.ok(requests[0].url.includes('run_id=run%3Aold'));assert.equal(requests[0].options.cache,'no-store');assert.equal(requests[0].options.method,undefined);
assert.equal(document.documentElement.dataset.theme,'light');assert.ok(root.textContent.includes('Earlier analysis'));assert.ok(root.textContent.includes('ADD'));assert.ok(!all(document.body).some(n=>n.tagName==='button'&&n.textContent==='Save'));
""", setup)

    def test_popout_rejects_mismatched_source_and_retries_without_fallback(self) -> None:
        setup = r"""
const root=new Element('main');root.id='instruction-help-window';document.body.append(root);
window.location.search='?id=inst%3Aone&run_id=run%3Aold';let calls=0;
async function fetch(){calls++;return{ok:true,json:async()=>({source:instruction(),run_id:'run:wrong',kind:'instruction'})};}
"""
        self.run_js(r"""
await flush();assert.ok(root.textContent.includes('does not match'));assert.ok(!root.textContent.includes('A, B, Output'));
all(root).find(n=>n.tagName==='button').fire('click');await flush();assert.equal(calls,2);assert.equal(all(root).filter(n=>n.tagName==='button').length,1);
""", setup)

    def test_popout_missing_context_never_fetches_active_source(self) -> None:
        setup = r"""
const root=new Element('main');root.id='instruction-help-window';document.body.append(root);let calls=0;
async function fetch(){calls++;throw Error('must not fetch');}
"""
        self.run_js(r"""
await flush();assert.equal(calls,0);assert.ok(root.textContent.includes('missing its instruction'));
""", setup)

    def test_popout_timeout_offers_retry(self) -> None:
        setup = r"""
const root=new Element('main');root.id='instruction-help-window';document.body.append(root);
window.location.search='?id=inst%3Aone&run_id=run%3Aold';
function fetch(url,options){return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>{const e=new Error('aborted');e.name='AbortError';reject(e);}));}
"""
        self.run_js(r"""
tick(15000);await flush();assert.ok(root.textContent.includes('too long'));assert.ok(all(root).some(n=>n.tagName==='button'&&n.textContent==='Retry'));
""", setup)

    def test_nested_variable_hover_wins_over_parent_and_preserves_full_address(self) -> None:
        self.run_js(r"""
const node=anchor(),token=variableNode(node,'LongDelayName.PRE'),requests=[];
globalThis.fetch=async url=>{requests.push(url);return{ok:true,json:async()=>variableData('LongDelayName.PRE')};};
window.PLCInstructionHelp.attach(node,instruction(),{runId:'run:one'});
assert.equal(requests.length,0);assert.equal(token.getAttribute('tabindex'),'0');
node.fire('pointerover',{target:token});node.fire('pointerenter');tick(240);await flush();
assert.equal(requests.length,1);assert.ok(requests[0].includes('variable=LongDelayName.PRE'));
assert.equal(panel().getAttribute('aria-label'),'Variable help');assert.ok(panel().textContent.includes('LongDelayName.PRE'));
node.fire('pointerout',{target:token,relatedTarget:node});tick(240);assert.equal(panel().getAttribute('aria-label'),'Instruction help');
""")

    def test_offline_variable_hover_explains_workspace_requirement_without_requests_or_retry(self) -> None:
        self.run_js(r"""
const node=anchor(),token=variableNode(node,'Delay.PRE');let requests=0;
globalThis.fetch=async()=>{requests++;throw Error('Offline hover must not request the API');};
window.PLCInstructionHelp.attach(node,instruction());node.fire('pointerover',{target:token});tick(240);await flush();
assert.equal(requests,0);assert.ok(panel().textContent.includes('open this report through the workspace'));
assert.equal(all(panel()).some(n=>n.tagName==='button'&&n.textContent.includes('Retry')),false);
assert.equal(all(panel()).find(n=>n.textContent==='Open help window ↗').disabled,true);
node.fire('pointerout',{target:token,relatedTarget:node});tick(240);
assert.equal(panel().getAttribute('aria-label'),'Instruction help');assert.ok(panel().textContent.includes('ADD'));assert.equal(requests,0);
""")

    def test_variable_ctrl_click_and_f1_do_not_select_parent_and_keep_captured_run(self) -> None:
        self.run_js(r"""
const node=anchor(),token=variableNode(node,'Delay.PRE'),row=instruction();let selected=0,runId='run:old';
globalThis.fetch=async()=>({ok:true,json:async()=>variableData('Delay.PRE','run:old')});
window.PLCInstructionHelp.configure({getContext:()=>({runId})});
node.addEventListener('click',()=>selected++);window.PLCInstructionHelp.attach(node,row);
runId='run:new';row.id='changed';
node.fire('click',{target:token});assert.equal(selected,1);assert.equal(opened.length,0);
for(let i=0;i<2;i++)node.fire('click',{target:token,ctrlKey:true});
assert.equal(selected,1);assert.equal(opened.length,2);
opened.forEach(item=>{const url=new URL(item.url);assert.equal(url.searchParams.get('variable'),'Delay.PRE');assert.equal(url.searchParams.get('run_id'),'run:old');assert.equal(url.searchParams.get('id'),'inst:one');});
window.PLCInstructionHelp.close();node.fire('keydown',{key:'F1',target:token});await flush();
assert.equal(panel().getAttribute('aria-label'),'Variable help');assert.equal(document.activeElement.tagName,'button');
node.fire('keydown',{key:'Enter',ctrlKey:true,target:token});assert.equal(opened.length,3);
node.fire('click',{target:node,ctrlKey:true});assert.equal(new URL(opened.at(-1).url).searchParams.has('variable'),false);
""")

    def test_returning_to_active_variable_cancels_other_pending_hover(self) -> None:
        self.run_js(r"""
const node=anchor(),a=variableNode(node,'Delay.PRE'),b=variableNode(node,'Delay.ACC');
globalThis.fetch=async url=>{const q=new URL(url,window.location.origin).searchParams;return{ok:true,json:async()=>variableData(q.get('variable'))};};
window.PLCInstructionHelp.attach(node,instruction(),{runId:'run:one'});
node.fire('pointerover',{target:a});tick(240);await flush();
node.fire('pointerover',{target:b});node.fire('pointerover',{target:a});tick(240);await flush();
assert.ok(panel().textContent.includes('Delay.PRE'));assert.ok(!panel().textContent.includes('Delay.ACC'));
document.activeElement=node;node.fire('pointerleave');tick(350);assert.equal(panel(),null,'Focus on parent block must not pin a different variable');
""")

    def test_variable_stale_response_cannot_replace_new_subject_or_reopen_closed_help(self) -> None:
        self.run_js(r"""
const node=anchor(),a=variableNode(node,'Delay.PRE'),b=variableNode(node,'Delay.ACC'),pendingRequests=[];
globalThis.fetch=url=>new Promise(resolve=>pendingRequests.push({url,resolve}));
window.PLCInstructionHelp.attach(node,instruction(),{runId:'run:one'});
node.fire('pointerover',{target:a});tick(240);node.fire('pointerover',{target:b});tick(240);
pendingRequests[0].resolve({ok:true,json:async()=>variableData()});await flush();assert.ok(panel().textContent.includes('Delay.ACC'));assert.ok(!panel().textContent.includes('Verified preset'));
window.PLCInstructionHelp.close();pendingRequests[1].resolve({ok:true,json:async()=>variableData('Delay.ACC')});await flush();assert.equal(panel(),null);
""")

    def test_variable_failure_retries_and_mismatched_run_is_never_cached(self) -> None:
        self.run_js(r"""
const node=anchor(),token=variableNode(node,'Delay.PRE');let calls=0;
globalThis.fetch=async()=>({ok:true,json:async()=>variableData('Delay.PRE',++calls===1?'wrong-run':'run:one')});
window.PLCInstructionHelp.attach(node,instruction(),{runId:'run:one'});node.fire('keydown',{key:'F1',target:token});await flush();
assert.ok(panel().textContent.includes('does not match'));assert.ok(!panel().textContent.includes('Verified preset'));
all(panel()).find(n=>n.textContent==='Retry variable help').fire('click');await flush();
assert.equal(calls,2);assert.ok(panel().textContent.includes('Verified preset'));
""")

    def test_variable_load_deduplicates_is_run_bound_and_freezes_cached_evidence(self) -> None:
        self.run_js(r"""
const requests=[];globalThis.fetch=async url=>{requests.push(url);const q=new URL(url,window.location.origin).searchParams;return{ok:true,json:async()=>variableData(q.get('variable'),q.get('run_id'),q.get('instruction_id'))};};
const api=window.PLCInstructionHelp,ctx={runId:'run:one'};
const first=api.loadVariable(instruction(),'Delay.PRE',ctx),duplicate=api.loadVariable(instruction(),'Delay.PRE',ctx);
assert.equal(first,duplicate);const data=await first;assert.equal(requests.length,1);assert.ok(Object.isFrozen(data));assert.ok(Object.isFrozen(data.member));
await api.loadVariable(instruction(),'Delay.PRE',ctx);assert.equal(requests.length,1);
await api.loadVariable(instruction(),'Delay.PRE',{runId:'run:two'});assert.equal(requests.length,2);
await assert.rejects(api.loadVariable(instruction(),'Delay.PRE',{runId:''}),/captured instruction/);assert.equal(requests.length,2);
""")

    def test_variable_request_concurrency_queue_and_cache_are_bounded(self) -> None:
        self.run_js(r"""
const requests=[];globalThis.fetch=url=>new Promise(resolve=>requests.push({url,resolve}));
const api=window.PLCInstructionHelp,jobs=[];
for(let i=0;i<96;i++)jobs.push(api.loadVariable(instruction(),'Tag'+i,{runId:'run:one'}));
assert.equal(requests.length,4);await assert.rejects(api.loadVariable(instruction(),'Overflow',{runId:'run:one'}),/busy/);
for(let i=0;i<96;i++) {const request=requests[i];assert.ok(request);const q=new URL(request.url,window.location.origin).searchParams;
 request.resolve({ok:true,json:async()=>variableData(q.get('variable'))});await flush();assert.ok(requests.length<=i+5);}
await Promise.all(jobs);
globalThis.fetch=async url=>{requests.push({url});const q=new URL(url,window.location.origin).searchParams;return{ok:true,json:async()=>variableData(q.get('variable'))};};
await api.loadVariable(instruction(),'Tag96',{runId:'run:one'});assert.equal(requests.length,97);
await api.loadVariable(instruction(),'Tag0',{runId:'run:one'});assert.equal(requests.length,98,'Least recently used entry is evicted');
""")

    def test_variable_popout_fetches_only_run_bound_variable_and_uses_safe_title(self) -> None:
        setup = r"""
const root=new Element('main');root.id='instruction-help-window';document.body.append(root);
window.location.search='?id=inst%3Aone&run_id=run%3Aold&variable=Delay.PRE';const requests=[];
async function fetch(url){requests.push(url);return{ok:true,json:async()=>({...variableData('Delay.PRE','run:old'),historical:true})};}
"""
        self.run_js(r"""
await flush();assert.equal(requests.length,1);assert.ok(requests[0].startsWith('/api/variable?'));assert.ok(requests[0].includes('run_id=run%3Aold'));
assert.ok(root.textContent.includes('Earlier analysis'));assert.ok(root.textContent.includes('Delay.PRE'));assert.equal(document.title,'Delay.PRE · Variable help · PLC Workbench');
""", setup)


class InstructionHelpAssetTests(unittest.TestCase):
    def test_local_read_only_help_assets_keep_security_headers(self) -> None:
        from test_workspace import running_workspace

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with running_workspace(root / 'project.sqlite', root / 'runs') as client:
                revision = client.get('/api/state')['revision']
                for name in ('instruction-help.html', 'instruction-help.js',
                             'instruction-help.css', 'instruction-help-content.js'):
                    with self.subTest(asset=name):
                        status, data = client.request('/' + name)
                        self.assertEqual(status, 200)
                        self.assertEqual(data, (ASSETS / name).read_bytes())
                        self.assertIn("default-src 'none'", client.last_headers['content-security-policy'])
                page = client.get('/instruction-help.html').decode('utf-8')
                self.assertNotIn('workspace-token', page)
                self.assertEqual(client.get('/api/state')['revision'], revision)
