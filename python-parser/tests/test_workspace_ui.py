"""Exercise actual workspace rendering and edit-command construction.

These checks use invented source only. The small Node DOM is sufficient for
branch preservation and mutation contracts; browser appearance is checked
separately against the running local workspace.
"""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import unittest
from urllib.parse import urlsplit


ASSETS = Path(__file__).resolve().parents[1] / "src/plc_workbench/workspace_assets"
SCRIPT = (ASSETS / "workspace.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str | None]]] = []
        self.stack = []
        self.parents = {}
        self.feed((ASSETS / "index.html").read_text(encoding="utf-8"))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.elements.append((tag, attributes))
        if attributes.get('id'):
            self.parents[attributes['id']] = [item[1] for item in self.stack]
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append((tag, attributes.get('id') or tag))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                self.stack = self.stack[:index]
                break


def function(name: str) -> str:
    """Extract a top-level function from the shipped, formatted asset."""
    match = re.search(
        rf"^  (?:async )?function {name}\(.*?(?=^  (?:async )?function |^  let |^  \$|^  //|^  window\.|^  run\()",
        SCRIPT,
        flags=re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"Missing workspace function: {name}")
    return match.group()


DOM = r"""
const assert=require('node:assert/strict');
class Element {
  constructor(tag,text='') {
    this.tagName=tag; this.textContent=String(text??''); this.className='';
    this.children=[];this.events={};this.attributes={};this.dataset={};this.checked=false;
    this.value='';this.disabled=false;this.hidden=false;
    this.classList={
      contains:cls=>this.className.split(' ').includes(cls),
      toggle:(cls,on)=>{const tokens=new Set(this.className.split(' ').filter(Boolean));const add=on??!tokens.has(cls);if(add)tokens.add(cls);else tokens.delete(cls);this.className=[...tokens].join(' ');return add;},
      remove:(...names)=>{names.forEach(name=>this.classList.toggle(name,false));},
      add:(...names)=>{names.forEach(name=>this.classList.toggle(name,true));},
    };
  }
  append(...children) {for(const child of children){child.parent=this;this.children.push(child);}}
  prepend(...children) {children.forEach(child=>child.parent=this);this.children.unshift(...children);}
  replaceChildren(...children){this.children=[];this.append(...children);}
  addEventListener(name,callback){this.events[name]=callback;}
  setAttribute(name,value){this.attributes[name]=value;}
  removeAttribute(name){delete this.attributes[name];}
  remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);}
  contains(target){return target===this||this.children.some(child=>child.contains(target));}
  get childNodes(){return this.children;}
  get firstChild(){return this.children[0]||null;}
  querySelectorAll(selector){return descendants(this).filter(n=>selector.split(',').map(s=>s.trim()).some(s=>s==='.field-row'?n.className==='field-row':s==='input:checked'?n.tagName==='input'&&n.checked:n.tagName===s));}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
  closest(tag){return this.tagName===tag?this:this.parent?.closest(tag);}
  dispatchEvent(event){this.events[event.type]?.(event);}
}
const descendants=root=>root.children.flatMap(child=>[child,...descendants(child)]);
const contents=root=>[root.textContent,...root.children.map(contents)].join(' ');
const node=(tag,text,cls)=>{const n=new Element(tag,text);n.className=cls||'';return n;};
const clear=root=>root.replaceChildren();
const button=(text,callback,cls)=>{const n=node('button',text,cls);n.events.click=callback;return n;};
const field=(text,input)=>{const n=node('label',text);n.append(input);return n;};
const link=(text,id,view='ladder')=>{const n=node('a',text);n.href='/analysis#view='+view+'&source='+encodeURIComponent(id);return n;};
const input=(value='',placeholder='')=>{const n=node('input');n.value=value;n.placeholder=placeholder;return n;};
const select=(choices,value='')=>{const n=node('select');n.value=value;return n;};
const section=(root,title,description)=>{const n=node('section');n.append(node('h3',title));if(description)n.append(node('p',description));root.append(n);return n;};
const document={createTextNode:text=>node('#text',text),body:node('body')};
let $, api, window={innerWidth:1600}, renderDetail, loadObjects;
let selectedCategories=['category-pid'];
const categoryPicker=()=>({element:node('div'),values:()=>selectedCategories});
let activeGroups=[];
const groups=()=>activeGroups;
let commands=[],modalBody,saveDialog,notice='',state={project:{revision:1,active_run:'synthetic-run'},selected:new Set(['rung-a','rung-b']),source:null,dirty:false,detailSerial:0,view:'rungs'};
const statusNames={unreviewed:'Not reviewed',needs_review:'Needs review',confirmed:'Confirmed'};
let discard=()=>true;
const modal=(title,build,save)=>{modalBody=node('div');build(modalBody);saveDialog=save;};
let mutate=async command=>{commands.push(command);};
const loadRungs=async()=>{};
let openSource=async()=>{};
const notify=text=>{notice=text;};
let run=async callback=>callback();
const Event=function(type){this.type=type;};
"""


OVERLAY_SETUP = r"""
const dialog=node('dialog'),tools=node('details'),summary=node('summary','Project tools'),menuField=node('input'),outside=node('main'),inline=node('details');
tools.append(summary,menuField);inline.open=true;
$=id=>id==='dialog'?dialog:id==='project-tools'?tools:null;
dialog.open=true;let closed=0,confirms=0,confirmResult=false;
dialog.getBoundingClientRect=()=>({left:100,right:500,top:100,bottom:400});
dialog.close=()=>{closed++;dialog.open=false;dialog.events.close?.();};
summary.focus=()=>{document.activeElement=summary;};
window.confirm=()=>{confirms++;return confirmResult;};
globalThis.modalDirty=false;globalThis.modalBusy=false;globalThis.modalRevision=9;state.saving=false;
document.events={};document.addEventListener=(name,callback)=>{document.events[name]=callback;};
const fire=(name,extra={})=>dialog.events[name]?.({type:name,target:dialog,pointerId:1,button:0,isPrimary:true,clientX:20,clientY:20,detail:1,...extra});
const backdropClick=()=>{fire('pointerdown');fire('pointerup');fire('click');};
installOverlayDismissal();
"""


RUNG_LIST_DOM = r"""
const listElements=new Map();
$=id=>{if(!listElements.has(id))listElements.set(id,node('div'));return listElements.get(id);};
document.querySelectorAll=()=>[];
state={...state,listSerial:0,page:1,routine:'',saving:false};
state.project={...state.project,active_run:'synthetic-run',routines:[]};
const chip=(text,cls='')=>node('span',text,'chip '+cls);
const categoryName=id=>id;
const labelOf=item=>item.path||item.name||item.id;
const renderRungPreview=row=>node('div','Preview '+row.id);
const renderSelection=()=>{};
const pagination=()=>{};
const rungRow=(id,number)=>({id,number,path:'Invented / Routine / '+number,parse_status:'parsed'});
const rungResult=(...items)=>({items,total:items.length,page:1,page_size:50});
"""


class WorkspacePageTests(unittest.TestCase):
    def test_page_has_one_source_first_entry_and_local_assets(self) -> None:
        page = Page()
        ids = [attrs["id"] for _, attrs in page.elements if "id" in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue({"source-name", "source-count", "routine-browser", "rung-list", "rung-detail", "object-list", "group-list", "history", "reconciliation"}.issubset(ids))
        for tag, attrs in page.elements:
            for key in ("src", "href"):
                if key in attrs:
                    target = urlsplit(attrs[key] or "")
                    self.assertFalse(target.scheme or target.netloc)
                    if tag in {"script", "link"}:
                        self.assertTrue((ASSETS / target.path.lstrip("/")).is_file())
        self.assertNotIn("innerHTML", SCRIPT)
        self.assertNotIn("outerHTML", SCRIPT)
        self.assertNotIn("insertAdjacentHTML", SCRIPT)
        self.assertIn('"X-Workspace-Token": token', SCRIPT)
        self.assertIn('credentials: "same-origin"', SCRIPT)

    def test_source_values_are_not_stored_as_browser_review_data(self) -> None:
        keys = re.findall(r'''localStorage\.setItem\(\s*["']([^"']+)["']''', SCRIPT)
        self.assertCountEqual(keys, ["plc-workspace-guide-v1", "plc-workspace-theme-v1", "plc-workspace-reviewer-v1"])
        self.assertIn("No demonstration data is loaded", SCRIPT)
        self.assertIn("__WORKSPACE_TOKEN__", (ASSETS / "index.html").read_text(encoding="utf-8"))

    def test_project_controls_have_one_home_and_review_help_stays_in_header(self) -> None:
        page = Page()
        for control in ('translation-controls', 'import', 'project-changes', 'source-name'):
            self.assertIn('project-tools', page.parents[control])
        self.assertIn('header', page.parents['review-help'])
        self.assertNotIn('project-tools', page.parents['review-help'])
        self.assertIn('view-routines', page.parents['routine-browser'])
        self.assertNotIn('project-navigation', page.parents)
        self.assertNotIn('routine-tree', page.parents)

    def test_page_menu_starts_with_application_and_keeps_full_analysis_separate(self) -> None:
        html = (ASSETS / 'index.html').read_text(encoding='utf-8')
        menu = re.search(r'<select id="page-select">(.*?)</select>', html, re.DOTALL)
        self.assertIsNotNone(menu)
        values = re.findall(r'<option value="([^"]+)"', menu.group(1))
        self.assertEqual(values, ['home', 'application', 'patterns', 'field-io', 'analysis', 'routines', 'rungs',
                                  'map', 'connections', 'groups', 'objects'])
        self.assertNotIn('view-patterns', page_ids := [attrs.get('id') for _, attrs in Page().elements])
        self.assertNotIn('view-analysis', page_ids)


@unittest.skipUnless(NODE, "Node is optional developer tooling")
class WorkspaceInteractionTests(unittest.TestCase):
    def run_js(self, names: list[str], checks: str) -> None:
        if any(name in names for name in ('openSource', 'refresh', 'refreshProjectWindow')) and 'assertSourceWindowRun' not in names:
            names = ['assertSourceWindowRun', *names]
        if 'openSource' in names and 'sourceWindowAnnotation' not in names:
            names = ['sourceWindowAnnotation', *names]
        if 'renderDetail' in names and 'renderSelectedAnnotation' not in names:
            names = ['renderSelectedAnnotation', *names]
        dom = DOM
        for name in ("openSource", "loadRungs"):
            if name in names:
                dom = dom.replace(f"const {name}=async()=>{{}};", "")
                dom = dom.replace(f"let {name}=async()=>{{}};", "")
        if "loadObjects" in names:
            dom = dom.replace("renderDetail, loadObjects;", "renderDetail;")
        if 'renderDetail' in names:
            dom = dom.replace(', renderDetail', '')
        if "loadRungs" in names or "loadObjects" in names:
            dom += RUNG_LIST_DOM
        code = dom + "\n" + "\n".join(function(name) for name in names)
        code += "\n(async()=>{\n" + checks + "\n})()"
        code += ".then(()=>process.stdout.write('UI_TEST_COMPLETE\\n'))"
        code += ".catch(error=>{console.error(error);process.exitCode=1;});"
        result = subprocess.run([NODE, "-"], input=code, capture_output=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("UI_TEST_COMPLETE", result.stdout, "An asynchronous check never completed")

    def test_sticky_panel_offset_tracks_wrapped_header_height_and_releases_observer(self) -> None:
        self.run_js(['installHeaderLayout'], r"""
const header=node('header');let height=88.25,observe,resize,disconnected=false;
const writes=[];header.getBoundingClientRect=()=>({height});
document.querySelector=selector=>selector==='.topbar'?header:null;
document.documentElement={style:{setProperty:(name,value)=>writes.push([name,value])}};
window.ResizeObserver=class{constructor(callback){observe=callback;}observe(target){assert.equal(target,header);}disconnect(){disconnected=true;}};
window.addEventListener=(name,callback)=>{assert.equal(name,'resize');resize=callback;};
window.removeEventListener=(name,callback)=>{assert.equal(name,'resize');assert.equal(callback,resize);resize=null;};
const cleanup=installHeaderLayout();assert.deepEqual(writes,[['--workspace-header-height','89px']]);
observe();assert.equal(writes.length,1,'Unchanged layout should not write styles repeatedly');
height=162.5;observe();assert.deepEqual(writes.at(-1),['--workspace-header-height','163px']);
height=211;resize();assert.deepEqual(writes.at(-1),['--workspace-header-height','211px']);
height=88.25;observe();assert.deepEqual(writes.at(-1),['--workspace-header-height','89px']);
cleanup();assert.equal(disconnected,true);assert.equal(resize,null);
""")

    def test_sticky_header_measurement_has_window_resize_fallback(self) -> None:
        self.run_js(['installHeaderLayout'], r"""
let height=100,resize;const header={getBoundingClientRect:()=>({height})},values=[];
document.querySelector=()=>header;document.documentElement={style:{setProperty:(name,value)=>values.push(value)}};
window.addEventListener=(name,callback)=>{resize=callback;};window.removeEventListener=()=>{};
installHeaderLayout();assert.equal(values.at(-1),'100px');height=190;resize();assert.equal(values.at(-1),'190px');
document.querySelector=()=>null;assert.doesNotThrow(()=>installHeaderLayout()());
""")

    def test_original_table_header_tracks_page_and_nested_scroll_without_column_clones(self) -> None:
        self.run_js(['installTableHeaders'], r"""
const main=node('main'),header=node('header'),table=node('table'),head=node('thead'),wrap=node('div');
let tableTop=-100,wrapperTop=-100,wrapperBottom=500,left=-160,visible=true,frameCallback,scrollCallback,resizeCallback;
table.parentElement=wrap;wrap.parentElement=main;main.parentElement=document.body;head.parentElement=table;head.style={};
head.getBoundingClientRect=()=>({top:tableTop+(Number((head.style.transform||'').match(/-?[0-9.]+/)?.[0])||0),height:30,left});
table.getBoundingClientRect=()=>({top:tableTop,bottom:tableTop+500,left});table.getClientRects=()=>visible?[{}]:[];
wrap.getBoundingClientRect=()=>({top:wrapperTop,bottom:wrapperBottom});wrap.clientTop=0;
header.getBoundingClientRect=()=>({bottom:100});main.querySelectorAll=()=>[head];$=id=>id==='main'?main:null;
document.querySelector=()=>header;window.getComputedStyle=element=>({overflowY:element===wrap?'auto':'visible'});
document.addEventListener=(name,callback)=>{assert.equal(name,'scroll');scrollCallback=callback;};
document.removeEventListener=(name,callback)=>{assert.equal(callback,scrollCallback);scrollCallback=null;};
window.addEventListener=(name,callback)=>{resizeCallback=callback;};window.removeEventListener=()=>{};
window.requestAnimationFrame=callback=>{frameCallback=callback;return 1;};window.cancelAnimationFrame=()=>{};
const cleanup=installTableHeaders();frameCallback();assert.equal(head.style.transform,'translateY(202px)');
assert.equal(head.getBoundingClientRect().top,102);assert.equal(head.getBoundingClientRect().left,left);
left=-400;scrollCallback();frameCallback();assert.equal(head.getBoundingClientRect().left,-400);assert.equal(head.getBoundingClientRect().top,102);
wrapperTop=180;wrapperBottom=380;tableTop=-20;scrollCallback();frameCallback();assert.equal(head.getBoundingClientRect().top,180);
tableTop=-380;scrollCallback();frameCallback();assert.equal(head.getBoundingClientRect().top,90,'Heading stops at table bottom');
tableTop=240;wrapperTop=240;wrapperBottom=800;resizeCallback();frameCallback();assert.equal(head.style.transform,'');
assert.equal(head.classList.contains('workspace-table-head'),true);cleanup();assert.equal(head.classList.contains('workspace-table-head'),false);assert.equal(head.style.transform,'');
""")

    def test_table_header_stays_below_page_toolbar_and_tracks_toolbar_resize(self) -> None:
        self.run_js(['installTableHeaders'], r"""
const main=node('main'),header=node('header'),table=node('table'),head=node('thead'),view=node('section'),toolbar=node('div');
let toolbarBottom=186,toolbarVisible=true,useToolbar=true,frameCallback,resized,disconnected=false;const observed=[];
table.parentElement=main;main.parentElement=document.body;head.parentElement=table;head.style={};
table.closest=selector=>selector==='.view'&&useToolbar?view:null;view.querySelector=selector=>selector==='[data-table-toolbar]'?toolbar:null;
toolbar.getClientRects=()=>toolbarVisible?[{}]:[];toolbar.getBoundingClientRect=()=>({bottom:toolbarBottom});
head.getBoundingClientRect=()=>({top:-100+(Number((head.style.transform||'').match(/-?[0-9.]+/)?.[0])||0),height:30});
table.getBoundingClientRect=()=>({top:-100,bottom:600});table.getClientRects=()=>[{}];
header.getBoundingClientRect=()=>({bottom:100});main.querySelectorAll=()=>[head];$=id=>id==='main'?main:null;
document.querySelector=()=>header;window.getComputedStyle=()=>({overflowY:'visible'});
document.addEventListener=()=>{};document.removeEventListener=()=>{};window.addEventListener=()=>{};window.removeEventListener=()=>{};
window.requestAnimationFrame=callback=>{frameCallback=callback;return 1;};window.cancelAnimationFrame=()=>{};
window.ResizeObserver=class{constructor(callback){resized=callback;}observe(target){observed.push(target);}disconnect(){disconnected=true;}};
const cleanup=installTableHeaders();frameCallback();assert.equal(head.getBoundingClientRect().top,188);assert.ok(observed.includes(toolbar));
toolbarBottom=244;resized();frameCallback();assert.equal(head.getBoundingClientRect().top,246,'Wrapped toolbar must not cover column headings');
toolbarVisible=false;resized();frameCallback();assert.equal(head.getBoundingClientRect().top,102,'Hidden toolbar does not affect headers');
toolbarVisible=true;useToolbar=false;resized();frameCallback();assert.equal(head.getBoundingClientRect().top,102,'Other pages keep their ordinary header offset');
cleanup();assert.equal(disconnected,true);assert.equal(head.style.transform,'');
""")

    def test_page_help_keeps_access_and_instructions_out_of_the_working_view(self) -> None:
        self.run_js(['pageAccessNote', 'showPageHelp'], r"""
const panel=node('section'),heading=node('h1','Field I/O'),help=node('div','Work one field signal at a time.'),dialog=node('dialog'),opener=node('button');
help.hidden=true;help.cloneNode=()=>node('div',help.textContent);panel.querySelector=selector=>selector==='.page-heading h1'?heading:selector==='.page-help-content'?help:null;
$=id=>id==='view-field-io'?panel:id==='dialog'?dialog:null;opener.focus=()=>{document.activeElement=opener;};opener.isConnected=true;document.activeElement=opener;
const note=pageAccessNote('field-io');assert.equal(note.children[0].textContent,'Read & write');
assert.equal(note.children[1].textContent,'Page help');assert.equal(contents(note).includes('Original source evidence'),false);
note.children[1].events.click();assert.ok(contents(modalBody).includes('Original source evidence stays read-only'));
assert.ok(contents(modalBody).includes('Source references do not prove runtime activity'));assert.ok(contents(modalBody).includes('Hide empty unreferenced rows'));
assert.ok(contents(modalBody).includes('From result'));assert.equal(saveDialog,undefined);
document.activeElement=dialog;dialog.events.close();assert.equal(document.activeElement,opener);
""")

    def test_dialog_backdrop_click_is_distinct_from_padding_drag_cancel_and_keyboard_click(self) -> None:
        self.run_js(['closeModal', 'installOverlayDismissal'], OVERLAY_SETUP + r"""
fire('pointerdown',{clientX:110,clientY:110});fire('pointerup',{clientX:110,clientY:110});fire('click',{clientX:110,clientY:110});
assert.equal(closed,0,'Dialog padding is not its backdrop');
fire('pointerdown',{target:menuField,clientX:120,clientY:120});fire('pointerup');fire('click');
assert.equal(closed,0,'Dragging from dialog content onto backdrop must not dismiss');
fire('pointerdown');fire('pointerup',{clientX:120,clientY:120});fire('click');assert.equal(closed,0);
fire('pointerdown');fire('pointermove',{clientX:60});fire('pointermove');fire('pointerup');fire('click');
assert.equal(closed,0,'Dragging and returning to start must not count as click');
fire('pointerdown',{button:2});fire('pointerup');fire('click');assert.equal(closed,0);
fire('pointerdown');fire('pointercancel');fire('pointerup');fire('click');assert.equal(closed,0);
fire('pointerdown');fire('pointerup',{pointerId:2});fire('click');assert.equal(closed,0);
fire('pointerdown');fire('pointerup');fire('click',{detail:0});assert.equal(closed,0);
fire('click');assert.equal(closed,0,'A click without a completed pointer press is not dismissal');
backdropClick();assert.equal(closed,1);assert.equal(dialog.open,false);assert.equal(modalRevision,null);
assert.equal(inline.open,true);
""")

    def test_backdrop_and_native_escape_preserve_dirty_confirmation_and_inflight_guards(self) -> None:
        self.run_js(['closeModal', 'installOverlayDismissal'], OVERLAY_SETUP + r"""
modalDirty=true;backdropClick();assert.equal(confirms,1);assert.equal(closed,0);assert.equal(modalDirty,true);assert.equal(modalRevision,9);
let prevented=0;fire('cancel',{preventDefault(){prevented++;}});assert.equal(prevented,1);assert.equal(confirms,2);assert.equal(closed,0);
state.saving=true;backdropClick();fire('cancel',{preventDefault(){prevented++;}});
assert.equal(confirms,2);assert.equal(closed,0);assert.ok(notice.includes('Wait for the current operation'));
state.saving=false;modalBusy=true;backdropClick();fire('cancel',{preventDefault(){prevented++;}});
assert.equal(confirms,2);assert.equal(closed,0);assert.equal(dialog.open,true);
modalBusy=false;confirmResult=true;fire('cancel',{preventDefault(){prevented++;}});
assert.equal(confirms,3);assert.equal(closed,1);assert.equal(modalDirty,false);assert.equal(modalRevision,null);assert.equal(prevented,4);
""")

    def test_project_tools_outside_click_and_escape_leave_inline_details_and_native_dialog_alone(self) -> None:
        self.run_js(['closeModal', 'installOverlayDismissal'], OVERLAY_SETUP + r"""
dialog.open=false;tools.open=true;document.events.click({target:menuField});assert.equal(tools.open,true);
document.events.click({target:summary});assert.equal(tools.open,true);
document.events.click({target:outside});assert.equal(tools.open,false);assert.equal(inline.open,true);
tools.open=true;document.activeElement=menuField;let prevented=0;
document.events.keydown({key:'Escape',preventDefault(){prevented++;}});
assert.equal(tools.open,false);assert.equal(document.activeElement,summary);assert.equal(prevented,1);
tools.open=true;document.events.keydown({key:'Escape',defaultPrevented:true,preventDefault(){prevented++;}});assert.equal(tools.open,true);
dialog.open=true;document.events.keydown({key:'Escape',preventDefault(){prevented++;}});
document.events.click({target:dialog});assert.equal(tools.open,true);assert.equal(prevented,1);assert.equal(dialog.open,true);
dialog.open=false;document.activeElement=outside;document.events.keydown({key:'Escape',preventDefault(){prevented++;}});
assert.equal(document.activeElement,outside);assert.equal(tools.open,false);assert.equal(inline.open,true);
""")

    def test_english_rung_search_results_keep_original_disclosed_and_dirty_detail(self) -> None:
        translation = (ASSETS / "translation.js").read_text(encoding="utf-8")
        self.run_js(["loadRungs"], "document.createElement=tag=>node(tag);\n" + translation + r"""
state.dirty=true; state.source={source:{id:'selected-rung'}};
const selected=state.source;
$('rung-search').value='Valve';
api=async path=>{
  assert.equal(new URL(path,'http://localhost').searchParams.get('query'),'Valve');
  return {...rungResult({...rungRow('found',1),comment:'Fermer la vanne',
    wording:{comment:{status:'translated',text:'Close the valve'}}}),presentation_mode:'english'};
};
await loadRungs();
const root=$('rung-list');
const original=descendants(root).find(n=>n.className==='translation-original-disclosure');
assert.ok(original); assert.ok(!original.open);
assert.ok(contents(original).includes('Fermer la vanne'));
const english=descendants(root).find(n=>n.className==='translation-english');
assert.ok(contents(english).includes('Close the valve'));
assert.ok(!contents(english).includes('Fermer la vanne'));
assert.equal(state.source,selected); assert.equal(state.dirty,true);
""")

    def test_english_object_results_translate_prose_but_preserve_instruction_code(self) -> None:
        translation = (ASSETS / "translation.js").read_text(encoding="utf-8")
        self.run_js(["loadObjects"], "document.createElement=tag=>node(tag);\n" + translation + r"""
state.view='objects'; state.objectPage=1; state.dirty=true;
$('object-search').value='Pump';
api=async path=>{
  assert.equal(new URL(path,'http://localhost').searchParams.get('query'),'Pump');
  return {total:2,presentation_mode:'english',items:[
    {id:'tag',name:'P101',kind:'tag',path:'Invented / P101',description:'Pompe de transfert',
      wording:{description:{status:'translated',text:'Transfer pump'}}},
    {id:'instruction',kind:'instruction',path:'Invented / 1',description:'XIC(Marche)OTE(P101);',
      description_is_code:true,wording:{description:{status:'translated',text:'Do not substitute code'}}}
  ]};
};
await loadObjects();
const root=$('object-list');
assert.ok(contents(root).includes('Transfer pump')); assert.ok(contents(root).includes('P101'));
assert.ok(contents(root).includes('XIC(Marche)OTE(P101);'));
assert.ok(!contents(root).includes('Do not substitute code'));
assert.equal(descendants(root).filter(n=>n.className==='translation-original-disclosure').length,1);
assert.equal(state.dirty,true);
""")

    def test_translation_updates_reload_only_active_inventory_without_discarding_form(self) -> None:
        self.run_js(["translationChanged"], r"""
const loaded=[]; loadObjects=async()=>{};
run=async callback=>loaded.push(callback===loadRungs?'rungs':callback===loadObjects?'objects':'unexpected');
renderDetail=()=>{throw new Error('Translation must not rebuild engineering forms');};
state.dirty=true; state.source={source:{id:'selected-rung'}};
const selected=state.source;
state.view='rungs'; translationChanged();
state.view='objects'; translationChanged();
state.view='groups'; translationChanged();
assert.deepEqual(loaded,['rungs','objects']);
assert.equal(state.source,selected); assert.equal(state.dirty,true);
""")

    def test_series_nested_parallel_and_empty_bypass_remain_visible(self) -> None:
        self.run_js(["renderStructure"], r"""
const inst=id=>({kind:'instruction',instruction_id:id});
const seq=(...items)=>({kind:'sequence',items});
const branch=(...legs)=>({kind:'branch',legs});
const tree=seq(inst('a'),branch(seq(inst('b'),branch(seq(),seq(inst('c')))),seq(inst('d'))),inst('e'));
const instructions=new Map(['a','b','c','d','e'].map(id=>[id,{id,opcode:id.toUpperCase(),arguments:['literal <script>not markup</script>']} ]));
const selected=new Set();const root=renderStructure(tree,instructions,selected);
assert.equal(descendants(root).filter(n=>n.className==='instruction-box').length,5);
assert.equal(descendants(root).filter(n=>n.className==='branch').length,2);
assert.ok(contents(root).includes('Empty branch path'));
assert.ok(contents(root).includes('literal <script>not markup</script>'));
assert.equal(descendants(root).filter(n=>n.tagName==='script').length,0);
const checks=descendants(root).filter(n=>n.tagName==='input');checks[2].checked=true;checks[2].events.change();
assert.deepEqual([...selected],['c']);checks[2].checked=false;checks[2].events.change();assert.equal(selected.size,0);
""")

    def test_unknown_nodes_and_missing_instruction_are_explicit(self) -> None:
        self.run_js(["renderStructure"], r"""
const unknown=renderStructure({kind:'future_node'},new Map(),new Set());
assert.ok(contents(unknown).includes('Unrecognized structure node: future_node'));
const missing=renderStructure({kind:'instruction',instruction_id:'missing'},new Map(),new Set());
assert.ok(contents(missing).includes('Instruction evidence unavailable: missing'));
""")

    def test_every_argument_links_to_its_exact_operand_and_tag(self) -> None:
        self.run_js(["renderInstructions"], r"""
const root=node('div');renderInstructions(root,[{id:'i1',opcode:'MOV',arguments:['Input','Output']}],[
{id:'operand-0',instruction_id:'i1',argument_index:0,target_ids:['tag-in']},
{id:'operand-1',instruction_id:'i1',argument_index:1,target_ids:['tag-out']}]);
const links=descendants(root).filter(n=>n.tagName==='a').map(n=>n.href);
assert.ok(links.includes('/analysis#view=ladder&source=operand-0'));
assert.ok(links.includes('/analysis#view=ladder&source=operand-1'));
assert.ok(links.includes('/analysis#view=objects&source=tag-in'));
assert.ok(links.includes('/analysis#view=objects&source=tag-out'));
assert.equal(descendants(root).filter(n=>n.tagName==='li').length,2);
""")

    def test_bulk_status_preserves_each_source_categories_and_fields(self) -> None:
        self.run_js(["bulkReview"], r"""
bulkReview();const status=descendants(modalBody).find(n=>n.tagName==='select');status.value='needs_review';await saveDialog();
assert.equal(commands[0].status,'needs_review');
assert.equal(Object.hasOwn(commands[0],'fields'),false);
assert.equal(Object.hasOwn(commands[0],'category_ids'),false);
assert.deepEqual(commands[0].source_ids,['rung-a','rung-b']);
""")

    def test_bulk_explicit_empty_category_set_clears_categories_only(self) -> None:
        self.run_js(["bulkReview"], r"""
selectedCategories=[];bulkReview();descendants(modalBody).find(n=>n.tagName==='input').checked=true;await saveDialog();
assert.deepEqual(commands[0].category_ids,[]);
assert.equal(Object.hasOwn(commands[0],'fields'),false);
assert.equal(Object.hasOwn(commands[0],'status'),false);
""")

    def test_empty_bulk_change_is_rejected(self) -> None:
        self.run_js(["bulkReview"], r"""
bulkReview();await assert.rejects(saveDialog,/Choose a category replacement or status change/);assert.equal(commands.length,0);
""")

    def test_group_addition_retains_existing_and_overlapping_members(self) -> None:
        self.run_js(["groupPicker"], r"""
activeGroups=[{id:'group-a',name:'Invented loop',member_ids:['rung-a','instruction-old']}];
groupPicker(['rung-a','instruction-new']);descendants(modalBody).find(n=>n.tagName==='select').value='group-a';await saveDialog();
assert.deepEqual(commands[0],{op:'group',id:'group-a',name:'Invented loop',member_ids:['rung-a','instruction-old','instruction-new']});
""")

    def test_individual_review_saves_structured_fields_without_losing_reserved_names(self) -> None:
        self.run_js(["renderEditor", "addProperty"], r"""
const root=node('div');const savedFields=Object.fromEntries([['PV','InputTag'],['__proto__','literal property']]);
renderEditor(root,'rung-a',{category_ids:['old-category'],status:'needs_review',fields:savedFields});
const form=root.querySelector('form'), rows=form.querySelectorAll('.field-row');
rows.find(row=>row.querySelector('input').value==='Purpose').querySelector('textarea').value='Transfer permissive';
form.querySelector('select').value='confirmed';form.events.input();
await form.events.submit({preventDefault(){}});
assert.equal(commands[0].op,'review');assert.equal(commands[0].status,'confirmed');
assert.deepEqual(commands[0].source_ids,['rung-a']);
assert.equal(commands[0].fields.PV,'InputTag');assert.equal(commands[0].fields.Purpose,'Transfer permissive');
assert.equal(commands[0].fields.__proto__,'literal property');
assert.equal(Object.getPrototypeOf(commands[0].fields),null);
""")

    def test_failed_save_keeps_unsaved_editor_values_and_reenables_controls(self) -> None:
        self.run_js(["renderEditor", "addProperty"], r"""
run=async callback=>{try{return await callback();}catch{return null;}};
mutate=async()=>{throw new Error('Stale revision');};
const root=node('div');renderEditor(root,'rung-a',{fields:{Purpose:'Before'}});
const form=root.querySelector('form');const row=form.querySelectorAll('.field-row').find(row=>row.querySelector('input').value==='Purpose');
row.querySelector('textarea').value='My unsaved correction';form.events.input();
await form.events.submit({preventDefault(){}});
assert.equal(row.querySelector('textarea').value,'My unsaved correction');assert.equal(state.dirty,true);
assert.ok(form.querySelectorAll('button, input, select, textarea').every(control=>!control.disabled));
""")

    def test_parser_explanation_is_readable_with_evidence_ids_collapsed(self) -> None:
        self.run_js(["human", "familyName", "proposalReason", "missingEvidence", "renderProposal"], r"""
const root=node('div');renderProposal(root,{category:'boolean_output',basis:'structural_pattern',reason:'conditional_boolean_assign',rule_id:'internal-rule',evidence_ids:['instruction-one'],missing_evidence:['engineering_purpose_unconfirmed']},new Map([['instruction-one','OTE(OutputTag)']]));
const card=root.children[0];assert.equal(card.children[0].textContent,'Boolean outputs');
assert.ok(contents(card).includes('Condition blocks lead to one final Boolean assignment.'));
assert.ok(contents(card).includes('Engineering purpose is unconfirmed.'));
const evidenceLink=descendants(card).find(n=>n.tagName==='a');assert.equal(evidenceLink.textContent,'OTE(OutputTag)');
assert.ok(evidenceLink.href.endsWith('source=instruction-one'));
const pre=descendants(card).find(n=>n.tagName==='pre');assert.equal(pre.parent.tagName,'details');assert.notEqual(pre.parent.open,true);
""")

    def test_old_rung_form_cannot_overwrite_newer_bulk_review_after_object_view(self) -> None:
        self.run_js(["renderEditor", "addProperty", "bulkReview"], r"""
const root=node('div');renderEditor(root,'rung-a',{fields:{Purpose:'Old interpretation'}},1);
const oldForm=root.querySelector('form');
state.source={source:{id:'tag-b'}};state.project.revision=4;state.selected=new Set(['rung-a']);
let stored={status:'needs_review',fields:{Purpose:'Current interpretation'}};
mutate=async(command,revision)=>{
  const expected=revision??state.project.revision;
  if(expected!==state.project.revision)throw new Error('Stale revision');
  stored={...stored,...command};state.project.revision++;
};
run=async callback=>{try{return await callback();}catch{return null;}};
bulkReview();descendants(modalBody).find(n=>n.tagName==='select').value='confirmed';await saveDialog();
assert.equal(state.project.revision,5);assert.equal(stored.status,'confirmed');
oldForm.events.input();await oldForm.events.submit({preventDefault(){}});
assert.equal(stored.status,'confirmed');assert.equal(stored.fields.Purpose,'Current interpretation');
assert.equal(state.dirty,true);
""")

    def test_view_change_clears_hidden_forms_and_cancels_outstanding_source(self) -> None:
        self.run_js(["switchView"], r"""
const panels=new Map(['rung-detail','object-detail'].map(id=>[id,node('section','Old form')]));
$=id=>panels.get(id);document.querySelectorAll=()=>[];
loadObjects=async()=>{};
state.source={source:{id:'rung-a'}};state.detailSerial=8;
assert.equal(switchView('objects'),true);
assert.equal(state.source,null);assert.equal(state.detailSerial,9);
for(const panel of panels.values()){assert.equal(panel.children.length,1);assert.ok(contents(panel).includes('Select a source record'));assert.equal(panel.inert,false);}
""")

    def test_explicit_card_connections_win_and_page_menu_uses_new_selected_rung(self) -> None:
        self.run_js(['switchView', 'openConnections'], r"""
const panels=new Map();$=id=>{if(!panels.has(id))panels.set(id,node('section'));return panels.get(id);};
document.querySelectorAll=()=>[];run=()=>{};
const focused=[];renderConnections=()=>focused.push(state.connectionRung);
state.view='rungs';state.source={source:{id:'rung-a',instructions:[]}};state.connectionRung='previous';
openConnections('rung-b');assert.equal(state.connectionRung,'rung-b');assert.deepEqual(focused,['rung-b']);
switchView('rungs',true);state.source={source:{id:'rung-c',instructions:[]}};
switchView('connections');assert.equal(state.connectionRung,'rung-c');assert.deepEqual(focused,['rung-b','rung-c']);
discard=()=>false;openConnections('discarded');assert.equal(state.connectionRung,'rung-c');
""")

    def test_help_closes_for_accepted_navigation_but_not_a_declined_dirty_transition(self) -> None:
        self.run_js(["switchView", "openSource"], r"""
const panel=node('section');$=()=>panel;document.querySelectorAll=()=>[];
loadObjects=async()=>{};renderDetail=()=>{};let closes=0,requests=0;
window.PLCInstructionHelp={close:()=>closes++};
api=async()=>{requests++;return {run_id:'synthetic-run',source:{id:'instruction-next'}};};
discard=()=>false;
assert.equal(switchView('objects'),false);await openSource('instruction-next');
assert.equal(closes,0);assert.equal(requests,0,'The dirty guard still runs first');
discard=()=>true;
assert.equal(switchView('objects'),true);assert.equal(closes,1);
await openSource('instruction-next','object-detail');
assert.equal(closes,2);assert.equal(requests,1);assert.equal(state.source.source.id,'instruction-next');
""")

    def test_delayed_source_request_cannot_replace_new_unsaved_edits(self) -> None:
        self.run_js(["openSource"], r"""
const panel=node('section');panel.append(node('textarea','Unsaved correction'));
$=()=>panel;let resolve;
api=()=>new Promise(done=>resolve=done);let renders=0;
renderDetail=()=>renders++;
const loading=openSource('rung-next');assert.equal(panel.inert,true);assert.equal(panel.attributes['aria-busy'],'true');
state.dirty=true;resolve({run_id:'synthetic-run',source:{id:'rung-next'},revision:2});await loading;
assert.equal(renders,0);assert.ok(contents(panel).includes('Unsaved correction'));assert.equal(panel.inert,false);
assert.ok(notice.includes('unsaved changes'));
""")

    def test_out_of_order_source_responses_leave_latest_selection_visible(self) -> None:
        self.run_js(["openSource"], r"""
const panel=node('section');$=()=>panel;const pending=[];
api=()=>new Promise(resolve=>pending.push(resolve));let visible='';
renderDetail=result=>visible=result.source.id;
const first=openSource('rung-a'),second=openSource('rung-b');
pending[1]({run_id:'synthetic-run',source:{id:'rung-b'},revision:1});await second;
pending[0]({run_id:'synthetic-run',source:{id:'rung-a'},revision:1});await first;
assert.equal(visible,'rung-b');assert.equal(state.source.source.id,'rung-b');assert.equal(panel.inert,false);
""")

    def test_source_popout_pins_run_and_skips_hidden_directories(self) -> None:
        self.run_js(['openSource', 'loadRungs', 'loadObjects'], r"""
document.body.classList.add('source-popout');window.location={search:'?panel=source&run_id=synthetic-run'};
const calls=[];api=async path=>{calls.push(path);return {run_id:'synthetic-run',source:{id:'rung-specific'}};};
let visible='';renderDetail=result=>{visible=result.source.id;};
await loadRungs();await loadObjects();assert.deepEqual(calls,[]);
await openSource('rung-specific');assert.deepEqual(calls,['/api/source?id=rung-specific&run_id=synthetic-run']);assert.equal(visible,'rung-specific');
state.project={...state.project,active_run:'other-run'};
await assert.rejects(openSource('rung-specific'),/different analysis run/);assert.equal(calls.length,1);
window.location.search='?panel=source&run_id=other-run&run_id=duplicate';
await assert.rejects(openSource('rung-specific'),/invalid analysis reference/);
""")

    def test_selected_source_wording_is_requested_only_for_original_popout_owner(self) -> None:
        self.run_js(['openSource'], r"""
document.body.classList.add('source-popout');state.sourceWindowOwner='type #1';
window.location={search:'?panel=source&run_id=synthetic-run&annotation=note%20%231',hash:'#view=objects&source=type%20%231'};
const panel=node('section');$=()=>panel;const calls=[];let visible;
api=async path=>{calls.push(path);const query=new URL(path,'http://localhost').searchParams;
 return {run_id:'synthetic-run',source:{id:query.get('id')},...(query.has('annotation')
  ?{selected_annotation:{id:query.get('annotation'),owner_id:query.get('id'),text:'Selected member comment'}}:{})};};
renderDetail=result=>visible=result;
await openSource('type #1');assert.equal(calls[0],'/api/source?id=type+%231&run_id=synthetic-run&annotation=note+%231');
assert.equal(visible.selected_annotation.text,'Selected member comment');
window.location.hash='#view=objects&source=another-tag';await openSource('another-tag');
assert.equal(calls[1],'/api/source?id=another-tag&run_id=synthetic-run');assert.equal(visible.selected_annotation,undefined);
await openSource('type #1');assert.ok(calls[2].includes('&annotation=note+%231'));
document.body.classList.remove('source-popout');await openSource('type #1');assert.equal(calls[3].includes('annotation='),false);
assert.equal(state.dirty,false);assert.equal(commands.length,0);
""")

    def test_selected_wording_rejects_invalid_query_and_mismatched_response(self) -> None:
        self.run_js(['openSource'], r"""
document.body.classList.add('source-popout');state.sourceWindowOwner='type-id';
const panel=node('section');$=()=>panel;let requests=0,renders=0;
api=async()=>{requests++;return {};};renderDetail=()=>renders++;
for(const query of ['annotation=','annotation=a&annotation=b','annotation=%00','annotation='+ 'a'.repeat(257)]) {
 window.location={search:'?panel=source&run_id=synthetic-run&'+query};
 await assert.rejects(openSource('type-id'),/invalid wording reference/);
}
assert.equal(requests,0);window.location.search='?panel=source&run_id=synthetic-run&annotation=note-id';
for(const selected of [undefined,{id:'different-note',owner_id:'type-id'}, {id:'note-id',owner_id:'different-owner'}]) {
 api=async()=>({run_id:'synthetic-run',source:{id:'type-id'},selected_annotation:selected});
 await assert.rejects(openSource('type-id'),/wording does not match this source/);assert.equal(panel.inert,false);
}
assert.equal(renders,0);assert.equal(state.source,null);assert.equal(commands.length,0);
""")

    def test_selected_member_wording_renders_above_editor_with_safe_original_text(self) -> None:
        self.run_js(['renderDetail', 'renderValues'], r"""
const root=node('section'),calls=[];globalThis.chip=(text,cls)=>node('span',text,cls);
globalThis.renderEditor=(target,id)=>{target.append(node('textarea','Review '+id));};
const data={run_id:'synthetic-run',source:{id:'type-id',name:'StateRecord',kind:'data_type',attributes:{Family:'NoFamily'}},
 selected_annotation:{id:'note-id',owner_id:'type-id',owner_name:'StateRecord.Ready',owner_suffix:'.Ready',
 text:'Prêt <script>alert(1)</script>',kind:'member_description',language:'fr'}};
renderDetail(data,root);let sections=root.children.filter(item=>item.tagName==='section');
assert.ok(contents(sections[0]).includes('Selected source wording StateRecord.Ready'));
assert.ok(contents(sections[0]).includes('Prêt <script>alert(1)</script>'));
assert.equal(contents(sections[0]).includes('.Ready.Ready'),false);
assert.ok(contents(sections[1]).includes('Your engineering review'));
assert.equal(descendants(root).some(item=>item.tagName==='script'),false);
window.PLCTranslation={renderProse:(target,original,wording,mode)=>{calls.push({original,wording,mode});target.textContent=wording.text;}};
data.selected_annotation.wording={text:'Ready',status:'translated'};data.presentation_mode='english';renderDetail(data,root);
assert.equal(calls.length,1);assert.equal(calls[0].original,'Prêt <script>alert(1)</script>');assert.equal(calls[0].mode,'english');
data.selected_annotation.owner_id='wrong-owner';renderDetail(data,root);
assert.equal(contents(root).includes('Selected source wording'),false);assert.equal(commands.length,0);
""")

    def test_source_response_must_match_requested_run_id_and_current_source(self) -> None:
        self.run_js(['openSource'], r"""
const panel=node('section');$=()=>panel;let rendered=0;renderDetail=()=>rendered++;
for(const result of [{run_id:'another-run',source:{id:'rung-a'}},{run_id:'synthetic-run',source:{id:'wrong-id'}},
 {run_id:'synthetic-run',historical:true,source:{id:'rung-a'}}]) {
 api=async()=>result;await assert.rejects(openSource('rung-a'),/does not match this analysis/);assert.equal(rendered,0);assert.equal(panel.inert,false);
}
let resolve;api=()=>new Promise(done=>resolve=done);const pending=openSource('rung-a');
state.project={...state.project,active_run:'new-run'};resolve({run_id:'synthetic-run',source:{id:'rung-a'}});
await assert.rejects(pending,/does not match this analysis/);assert.equal(rendered,0);assert.equal(state.source,null);
""")

    def test_refresh_refuses_to_replace_pinned_window_with_another_run(self) -> None:
        self.run_js(['refresh'], r"""
document.body.classList.add('source-popout');window.location={search:'?panel=source&run_id=synthetic-run'};
const before=state.project;api=async()=>({active_run:'new-run',revision:2});
await assert.rejects(refresh(),/different analysis run/);assert.equal(state.project,before);
""")

    def test_deep_links_accept_only_bounded_source_identifiers_and_known_views(self) -> None:
        self.run_js(["requestedLocation"], r"""
window.location={hash:'#view=rungs&source=rung_abc'};
assert.deepEqual(requestedLocation(),{view:'rungs',source:'rung_abc'});
window.location.hash='#view=objects&source=tag_abc';assert.equal(requestedLocation().source,'tag_abc');
for(const hash of ['#main','#view=bad','#view=patterns','#view=analysis','#view=rungs&source=a&source=b','#view=rungs&extra=x','#view=groups&source=a','#view=rungs&source=%00','#view=rungs&source='+ 'a'.repeat(257),'#view=rungs&source='+ 'a'.repeat(2049)]){
  window.location.hash=hash;assert.equal(requestedLocation(),null,hash);
}
window.location.hash='';assert.deepEqual(requestedLocation(),{view:'home',source:''});
window.location.hash='#view=map&source=rung_abc';assert.deepEqual(requestedLocation(),{view:'map',source:'rung_abc'});
window.location.hash='#view=connections&source=rung_abc';assert.equal(requestedLocation().view,'connections');
window.location.hash='#view=field-io';assert.deepEqual(requestedLocation(),{view:'field-io',source:''});
window.location.hash='#view=field-io&source=module-1';assert.equal(requestedLocation(),null);
""")

    def test_popouts_use_same_origin_source_ids_and_detach_opener(self) -> None:
        self.run_js(['popupWorkspace', 'hidePoppedSource'], r"""
const opened={opener:'parent'},calls=[];
window.open=(...args)=>{calls.push(args);return opened;};
popupWorkspace('rung_abc','source');
assert.equal(calls[0][0],'/?panel=source&run_id=synthetic-run#view=rungs&source=rung_abc');
assert.equal(opened.opener,null);assert.ok(calls[0][2].includes('popup'));
popupWorkspace('aoi_abc','source');assert.ok(calls[1][0].includes('view=objects'));
popupWorkspace('rung_abc','connections');assert.ok(calls[2][0].includes('view=connections'));
popupWorkspace('','map');assert.equal(calls[3][0],'/?panel=workspace#view=map');
popupWorkspace('','source');assert.equal(calls.length,4);assert.ok(notice.includes('Select'));
popupWorkspace('x'.repeat(257),'source');popupWorkspace('rung_abc','https://unrelated.invalid');assert.equal(calls.length,4);
""")

    def test_refresh_other_window_does_not_replace_unsaved_review_without_consent(self) -> None:
        self.run_js(['refreshProjectWindow'], r"""
let fetched=0;discard=()=>false;api=async()=>{fetched++;};
state.dirty=true;state.source={source:{id:'rung-current'}};
await refreshProjectWindow();assert.equal(fetched,0);assert.equal(state.source.source.id,'rung-current');
""")

    def test_source_popout_collapses_only_the_matching_pane_and_preserves_form(self) -> None:
        self.run_js(['popupWorkspace', 'hidePoppedSource', 'setSourcePaneHidden'], r"""
const elements=new Map();$=id=>{if(!elements.has(id))elements.set(id,node('div'));return elements.get(id);};
const selected={source:{id:'rung_current'}};state.source=selected;
window.open=()=>({});
popupWorkspace('instruction_other','source');
assert.equal($('rungs-layout').classList.contains('source-collapsed'),false);
popupWorkspace('rung_current','source');
assert.equal($('rungs-layout').classList.contains('source-collapsed'),true);
assert.equal($('rungs-inspector-toggle').textContent,'Show source');
assert.equal($('rungs-inspector-toggle').attributes['aria-expanded'],'false');
assert.equal(state.source,selected);
state.dirty=true;setSourcePaneHidden('rungs',false);
assert.equal(state.dirty,true);assert.equal(state.source,selected);
assert.equal($('rungs-source-note').hidden,true);
assert.equal($('rungs-inspector-toggle').textContent,'Hide source');
popupWorkspace('rung_current','source');
assert.ok(notice.includes('Save the current review'));
assert.equal($('rungs-layout').classList.contains('source-collapsed'),false);
state.dirty=false;window.open=()=>null;popupWorkspace('rung_current','source');
assert.equal($('rungs-layout').classList.contains('source-collapsed'),false);
assert.ok(contents($('notice')).includes('Open selected view in a new tab'));
""")

    def test_navigation_restores_regular_layout_without_losing_declined_edits(self) -> None:
        self.run_js(['navigateWorkspace'], r"""
const elements=new Map();$=id=>{if(!elements.has(id))elements.set(id,node('div'));return elements.get(id);};
document.body.classList.add('workspace-popout','source-popout');
$('project-tools').open=true;
const routes=[];window.history={replaceState:(...args)=>routes.push(args[2])};
switchView=()=>false;assert.equal(navigateWorkspace('home'),false);
assert.equal(routes.length,0);assert.equal(document.body.classList.contains('source-popout'),true);
switchView=view=>{state.view=view;return true;};
assert.equal(navigateWorkspace('home'),true);
assert.equal(document.body.classList.contains('source-popout'),false);
assert.equal(document.body.classList.contains('workspace-popout'),false);
assert.equal(routes[0],'/#view=home');
assert.equal($('project-tools').open,false);
""")

    def test_source_window_access_label_follows_internal_trace_navigation(self) -> None:
        self.run_js(['switchView'], r"""
const elements=new Map();$=id=>{if(!elements.has(id))elements.set(id,node('div'));return elements.get(id);};
document.querySelectorAll=()=>[];renderConnections=()=>{};run=()=>{};
document.body.classList.add('workspace-popout','source-popout');
switchView('connections',true);assert.equal($('source-window-access').hidden,true);
switchView('rungs',true);assert.equal($('source-window-access').hidden,false);
switchView('objects',true);assert.equal($('source-window-access').hidden,false);
switchView('home',true);assert.equal($('source-window-access').hidden,true);
""")

    def test_home_has_working_page_directory_and_existing_source_summary(self) -> None:
        self.run_js(['renderHome', 'pageAccessNote', 'analysisTime', 'activeAnalysis'], r"""
const elements=new Map();$=id=>{if(!elements.has(id))elements.set(id,node('div'));return elements.get(id);};
importDialog=()=>{};state.project={active_run:'invented',revision:3,source:{name:'Invented.L5X',rung_count:9,instruction_count:20}};
const visits=[];navigateWorkspace=view=>visits.push(view);
renderHome();assert.ok(contents($('home-source')).includes('Invented.L5X'));
const links=descendants($('home-pages')).filter(n=>n.tagName==='a');
assert.equal(links.length,10);
assert.deepEqual($('home-pages').children,links);
links.forEach(link=>link.events.click({preventDefault(){}}));
assert.deepEqual(visits,['application','patterns','field-io','analysis','routines','rungs','map','connections','groups','objects']);
for(const card of [links[1],links[3]]){
  for(const modifiers of [{ctrlKey:true},{metaKey:true},{shiftKey:true},{button:1}]){
    card.events.click({...modifiers,preventDefault(){throw new Error('Keep native new-window navigation');}});
  }
  assert.equal(card.target,'_blank');assert.equal(card.rel,'noopener');
}
assert.equal(visits.length,10);
// No language override: server applies the saved preference, even before UI status loads.
assert.equal(links[1].href,'/analysis#view=patterns');assert.equal(links[1].id,'patterns-card');
assert.equal(links[2].href,'#view=field-io');assert.equal(links[2].children[0].textContent,'Field I/O');
assert.equal(links[3].href,'/analysis#view=overview');assert.equal(links[3].id,'full-analysis-card');
assert.equal(links[1].children[0].textContent,'Patterns');
assert.ok(contents(links[1]).includes('Save categorization in Rungs or Classification & groups'));
assert.ok(links[1].children[1].title.includes('do not establish equivalent behavior'));
assert.deepEqual(links.map(card=>card.children[1].textContent),
  ['Read only','Read only','Read & write','Read only','Read only','Read & write','Read & write','Read only','Read & write','Read & write']);
assert.ok(contents($('home-pages')).includes('AI, AO, DI, DO, DC, AC, PID'));
""")

    def test_analysis_identity_uses_selected_manifest_time_not_import_or_last_run(self) -> None:
        self.run_js(['analysisTime', 'activeAnalysis', 'renderAnalysisIdentity', 'analysisRunLabel'], r"""
const elements=new Map();$=id=>{if(!elements.has(id))elements.set(id,node('div'));return elements.get(id);};
const first={id:'first',source_run_id:'first',snapshot_id:'same-source',created_utc:'2026-10-25T18:30:05+00:00',imported_utc:'2026-10-26T10:00:00Z'};
const second={id:'second',source_run_id:'second',snapshot_id:'same-source',created_utc:'2026-10-26T02:10:06+00:00'};
state.project={active_run:'first',source:{name:'Invented source'},runs:[first,second]};
renderAnalysisIdentity();
assert.equal($('header-source-name').textContent,'Invented source');
assert.equal($('header-analysis-time').textContent,'Analysis run · '+analysisTime(first.created_utc));
assert.equal($('source-analysis-time').textContent,$('header-analysis-time').textContent);
assert.ok($('header-analysis-time').title.includes(first.created_utc));
assert.ok(!$('header-analysis-time').title.includes(first.imported_utc));
assert.equal($('source-run-id').textContent,'Run first');
const old=$('header-analysis-time').textContent;
state.project.active_run='second';renderAnalysisIdentity();
assert.notEqual($('header-analysis-time').textContent,old);
assert.equal($('source-run-id').textContent,'Run second');
const expected=new Intl.DateTimeFormat(undefined,{year:'numeric',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',timeZoneName:'short'}).format(new Date(second.created_utc));
assert.equal(analysisTime(second.created_utc),expected);
for(const bad of [undefined,null,{},'bad','2026-10-26','2026-10-26T10:00:00','invalidZ']) assert.equal(analysisTime(bad),'Analysis time unavailable');
assert.match(analysisRunLabel({...second,label:'second',status:'partial',newer:true}),/Newer, not loaded/);
assert.match(analysisRunLabel({...first,current:true}),/Current/);
state.project.active_run=null;renderAnalysisIdentity();
assert.equal($('header-source-name').textContent,'No source selected');
assert.equal($('source-run-id').textContent,'');
""")

    def test_saved_run_discovery_preserves_edits_and_rejects_stale_responses(self) -> None:
        self.run_js(['refreshSavedRuns', 'analysisRunLabel', 'analysisTime'], r"""
const elements=new Map();$=id=>{if(!elements.has(id))elements.set(id,node('div'));return elements.get(id);};
state.project={active_run:'first',revision:7};state.dirty=true;state.source={source:{id:'editing'}};
const original=state.project,source=state.source;
api=async path=>{assert.equal(path,'/api/runs');return {active_run:'first',items:[{newer:true,label:'second',created_utc:'2026-10-26T10:00:00Z'}]};};
await refreshSavedRuns();
assert.equal(state.project,original);assert.equal(state.source,source);assert.equal(state.dirty,true);
assert.equal($('new-analysis').hidden,false);assert.equal($('new-analysis').dataset.action,'choose');
assert.match($('source-run-availability').textContent,/1 newer saved analysis/);
api=async()=>({active_run:'second',items:[]});await refreshSavedRuns();
assert.equal($('new-analysis').dataset.action,'refresh');assert.equal(state.project,original);
let release;api=()=>new Promise(resolve=>{release=resolve;});const pending=refreshSavedRuns();
state.project={active_run:'second',revision:8};
$('source-run-availability').textContent='Current';release({active_run:'first',items:[{newer:true}]});
await pending;assert.equal($('source-run-availability').textContent,'Current');
api=async()=>({active_run:'second',items:[]});await refreshSavedRuns();assert.equal($('new-analysis').hidden,true);
api=async()=>{throw new Error('offline');};await refreshSavedRuns();
assert.match($('source-run-availability').textContent,/Could not check saved runs/);
""")

    def test_analysis_windows_preserve_unsaved_form_and_recover_blocked_popups(self) -> None:
        self.run_js(['navigateWorkspace', 'openFullAnalysis'], r"""
const elements=new Map();$=id=>{if(!elements.has(id))elements.set(id,node('div'));return elements.get(id);};
const calls=[],opened={opener:'workspace'};window.open=(...args)=>{calls.push(args);return opened;};
discard=()=>{throw new Error('Opening evidence must not discard a review');};
switchView=()=>{throw new Error('Opening evidence must not navigate the editor');};
const selected={source:{id:'rung-current'}};state.source=selected;state.dirty=true;state.view='rungs';
for(const [page,report] of [['patterns','patterns'],['analysis','overview']]){
  $('page-select').value=page;
  assert.equal(navigateWorkspace(page),true);
  assert.deepEqual(calls.at(-1),['/analysis#view='+report,'_blank','popup,width=1400,height=900']);
  assert.equal(opened.opener,null);assert.equal($('page-select').value,'rungs');
  assert.equal(state.source,selected);assert.equal(state.dirty,true);assert.equal(state.view,'rungs');
}
window.open=()=>null;
for(const [page,report,activeView] of [['patterns','patterns','guide'],['analysis','overview','changes']]){
  state.view=activeView;$('notice').replaceChildren();$('page-select').value=page;
  assert.equal(navigateWorkspace(page),false);assert.equal($('page-select').value,'');
  const fallback=$('notice').children[0];
  assert.equal(fallback.href,'/analysis#view='+report);
  assert.equal(fallback.target,'_blank');assert.equal(fallback.rel,'noopener');
  assert.ok(fallback.textContent.includes(page==='patterns'?'Patterns':'full source analysis'));
  assert.ok(notice.includes('blocked'));assert.equal(state.source,selected);assert.equal(state.dirty,true);
  assert.equal(state.view,activeView);
}
""")

    def test_field_io_view_refreshes_and_invalidates_background_requests_on_exit(self) -> None:
        self.run_js(['switchView'], r"""
const elements=new Map();$=id=>{if(!elements.has(id))elements.set(id,node('div'));return elements.get(id);};
document.querySelectorAll=()=>[];let refreshes=0,exits=0;
fieldIOBrowser={refresh:()=>refreshes++,deactivate:()=>exits++};state.view='home';
assert.equal(switchView('field-io'),true);assert.equal(refreshes,1);assert.equal($('page-select').value,'field-io');
assert.equal(switchView('home'),true);assert.equal(exits,1);assert.equal(state.view,'home');
""")

    def test_application_navigation_initializes_run_and_reactivates_after_exit(self) -> None:
        self.run_js(['switchView'], r"""
const elements=new Map();$=id=>{if(!elements.has(id))elements.set(id,node('div'));return elements.get(id);};
document.querySelectorAll=()=>[];let updates=0,exits=0;
applicationBrowser={update:value=>{updates++;assert.equal(value,state.project);},deactivate:()=>exits++};
state.view='home';
assert.equal(switchView('application'),true);assert.equal(updates,1);
assert.equal($('page-select').value,'application');
assert.equal(switchView('home'),true);assert.equal(exits,1);
assert.equal(switchView('application'),true);assert.equal(updates,2);
""")

    def test_changed_analysis_clears_unavailable_routine_filter(self) -> None:
        self.run_js(['renderRoutines'], r"""
const picker=node('select');$=()=>picker;
state.routine='old-routine';state.page=8;
state.project.routines=[{id:'new-routine',path:'Program / New',count:4}];
renderRoutines();assert.equal(state.routine,'');assert.equal(state.page,1);assert.equal(picker.value,'');
state.routine='new-routine';renderRoutines();assert.equal(picker.value,'new-routine');
""")

    def test_routine_review_navigation_clears_filters_and_opens_requested_rung(self) -> None:
        self.run_js(['openRoutineRungs'], r"""
const elements=new Map();$=id=>{if(!elements.has(id))elements.set(id,node('div'));return elements.get(id);};
['rung-search','rung-family-filter','category-filter','status-filter'].forEach(id=>$(id).value='old');
let views=[],sources=[],routes=[];switchView=(view,skip)=>views.push([view,skip]);
openSource=async(...args)=>sources.push(args);setSourcePaneHidden=()=>{};
window.history={replaceState:(_a,_b,url)=>routes.push(url)};
discard=()=>false;assert.equal(await openRoutineRungs('routine-new','rung-new'),false);assert.equal(views.length,0);
discard=()=>true;assert.equal(await openRoutineRungs('routine-new','rung-new'),true);
assert.equal(state.routine,'routine-new');assert.equal(state.page,1);
assert.deepEqual(views,[['rungs',true]]);assert.deepEqual(sources,[['rung-new','rung-detail',true]]);
assert.equal(routes[0],'/#view=rungs&source=rung-new');
assert.equal($('category-filter').value,'');assert.equal($('rung-routine-filter').value,'routine-new');
""")

    def test_family_filter_keeps_choice_and_existing_inventory_constraints(self) -> None:
        self.run_js(['loadRungs'], r"""
state.source={source:{id:'keep'}};state.routine='routine-a';
$('rung-family-filter').value='calculation';$('category-filter').value='reviewed';
$('status-filter').value='confirmed';$('rung-search').value='pressure';
api=async path=>{
  const query=new URL(path,'http://localhost').searchParams;
  assert.equal(query.get('family'),'calculation');assert.equal(query.get('routine'),'routine-a');
  assert.equal(query.get('category'),'reviewed');assert.equal(query.get('status'),'confirmed');
  assert.equal(query.get('query'),'pressure');
  return {...rungResult(),families:[{id:'calculation',label:'Calculations',count:3}]};
};
await loadRungs();assert.equal($('rung-family-filter').value,'calculation');
assert.ok(contents($('rung-family-filter')).includes('Calculations'));
assert.equal(state.source.source.id,'keep');
""")

    def test_changed_analysis_clears_unavailable_family_before_showing_results(self) -> None:
        self.run_js(['loadRungs'], r"""
state.source={source:{id:'keep'}};state.dirty=true;state.page=5;
$('rung-family-filter').value='calculation';const queries=[];
api=async path=>{
  const query=new URL(path,'http://localhost').searchParams;queries.push(query);
  return {...rungResult(...(query.get('family')?[]:[rungRow('new-source',2)])),
    families:[{id:'boolean_condition',label:'Boolean conditions',count:1}]};
};
await loadRungs();assert.equal(queries.length,2);
assert.equal(queries[0].get('family'),'calculation');assert.equal(queries[1].get('family'),'');
assert.equal(queries[1].get('page'),'1');assert.equal($('rung-family-filter').value,'');
assert.ok(contents($('rung-list')).includes('Rung 2'));
assert.equal(state.dirty,true);assert.equal(state.source.source.id,'keep');
""")

    def test_refresh_preserves_edits_or_navigation_started_while_request_pending(self) -> None:
        self.run_js(['refreshProjectWindow'], r"""
for (const change of ['edit','navigate']) {
  const oldProject={active_run:'old',revision:1};
  const oldSource={source:{id:'old-rung'}};
  state={...state,project:oldProject,source:oldSource,dirty:false,view:'map',saving:false};
  let resolve;api=()=>new Promise(done=>resolve=done);
  const pending=refreshProjectWindow();
  if(change==='edit')state.dirty=true;
  else {state.detailSerial++;state.source={source:{id:'later-rung'}};}
  resolve({active_run:'new',revision:2});await pending;
  assert.equal(state.project,oldProject);
  assert.equal(state.source.source.id,change==='edit'?'old-rung':'later-rung');
  assert.equal(state.dirty,change==='edit');
  assert.ok(notice.includes('kept'));
}
""")

    def test_map_deep_link_focuses_map_without_loading_hidden_rung_editor(self) -> None:
        self.run_js(['openLocation'], r"""
requestedLocation=()=>({view:'map',source:'rung-map'});switchView=()=>true;
const focused=[];ladderMap={focus:async id=>focused.push(id)};
openSource=async()=>{throw Error('hidden editor must not load');};
await openLocation(true);assert.deepEqual(focused,['rung-map']);
""")

    def test_initial_inventory_opens_first_rung_in_an_untouched_pane(self) -> None:
        self.run_js(["loadRungs", "openSource"], r"""
const calls=[],visible=[];
run=async()=>{};
api=async url=>{
  calls.push(url);
  return url.startsWith('/api/rungs?')?rungResult(rungRow('first',1),rungRow('second',2))
    :{run_id:'synthetic-run',source:{id:'first'},revision:1};
};
renderDetail=(result,panel)=>{visible.push(result.source.id);panel.append(node('div','Visible '+result.source.id));};
await loadRungs();
assert.deepEqual(visible,['first']);assert.equal(state.source.source.id,'first');
assert.equal(calls.filter(url=>url.startsWith('/api/source')).length,1);
assert.equal($('rung-detail').inert,false);
assert.ok(contents($('rung-list')).includes('Open rung') && contents($('rung-list')).includes('Connections'));
""")

    def test_manual_rung_click_wins_over_an_outstanding_inventory_response(self) -> None:
        self.run_js(["loadRungs", "openSource"], r"""
state.source={source:{id:'previous'}};
const items=rungResult(rungRow('first',1),rungRow('chosen',2));
api=async()=>items;await loadRungs();
const choice=descendants($('rung-list')).filter(n=>n.tagName==='button'&&n.textContent==='Open rung')[1];
state.source=null;
let resolveList,resolveSource;const sourceRequests=[];
api=url=>url.startsWith('/api/rungs?')?new Promise(done=>resolveList=done)
  :new Promise(done=>{sourceRequests.push(url);resolveSource=done;});
let manual,visible='';
run=async callback=>{if(callback===loadRungs)return;manual=callback();return manual;};
renderDetail=result=>{visible=result.source.id;};
const loading=loadRungs();choice.events.click();
resolveList(items);await loading;
assert.deepEqual(sourceRequests,['/api/source?id=chosen&run_id=synthetic-run']);
resolveSource({run_id:'synthetic-run',source:{id:'chosen'},revision:1});await manual;
assert.equal(visible,'chosen');assert.equal(state.source.source.id,'chosen');
""")

    def test_deep_link_selection_wins_when_inventory_returns_first(self) -> None:
        self.run_js(["loadRungs", "openSource", "switchView", "requestedLocation", "openLocation"], r"""
window.location={hash:'#view=rungs&source=linked-rung'};
let resolveList,resolveSource;const requests=[],tasks=[];
api=url=>{
  requests.push(url);
  return url.startsWith('/api/rungs?')?new Promise(done=>resolveList=done)
    :new Promise(done=>resolveSource=done);
};
run=async callback=>{
  if(callback===loadRungs&&state.source)return;
  const task=callback();tasks.push(task);return task;
};
let visible='';renderDetail=result=>{visible=result.source.id;};
const opening=openLocation(true);
resolveList(rungResult(rungRow('first',1)));await tasks[0];
assert.deepEqual(requests.filter(url=>url.startsWith('/api/source')),['/api/source?id=linked-rung&run_id=synthetic-run']);
resolveSource({run_id:'synthetic-run',source:{id:'linked-rung'},revision:1});await opening;
assert.equal(visible,'linked-rung');assert.equal(state.source.source.id,'linked-rung');
""")

    def test_inventory_started_during_manual_source_load_does_not_steal_selection(self) -> None:
        self.run_js(["loadRungs", "openSource"], r"""
let resolveList,resolveChosen;const sourceRequests=[];
run=async()=>{};let visible='';renderDetail=result=>{visible=result.source.id;};
api=url=>{
  if(url.startsWith('/api/rungs?'))return new Promise(done=>resolveList=done);
  sourceRequests.push(url);
  if(url.includes('id=chosen&'))return new Promise(done=>resolveChosen=done);
  return Promise.resolve({run_id:'synthetic-run',source:{id:'first'},revision:1});
};
const chosen=openSource('chosen');
const refreshing=loadRungs();
resolveList(rungResult(rungRow('first',1),rungRow('chosen',2)));await refreshing;
assert.deepEqual(sourceRequests,['/api/source?id=chosen&run_id=synthetic-run']);
resolveChosen({run_id:'synthetic-run',source:{id:'chosen'},revision:1});await chosen;
assert.equal(visible,'chosen');assert.equal(state.source.source.id,'chosen');
""")

    def test_unsaved_form_or_in_progress_save_prevents_filter_auto_selection(self) -> None:
        self.run_js(["loadRungs", "openSource"], r"""
run=async()=>{};let rendered=0;renderDetail=()=>rendered++;
for(const locked of ['dirty','saving']) {
  state.source=null;state.dirty=false;state.saving=false;
  const panel=$('rung-detail');panel.replaceChildren(node('textarea','Keep my edits'));
  let resolve;const sourceRequests=[];
  api=url=>{
    if(url.startsWith('/api/source'))sourceRequests.push(url);
    return new Promise(done=>resolve=done);
  };
  $('rung-search').value='new filter';const loading=loadRungs();
  state[locked]=true;
  resolve(rungResult(rungRow('filtered',9)));await loading;
  assert.deepEqual(sourceRequests,[]);assert.equal(rendered,0);
  assert.ok(contents(panel).includes('Keep my edits'));
  assert.ok(contents($('rung-list')).includes('Rung 9'));
}
""")

    def test_late_inventory_after_view_switch_cannot_reopen_hidden_rung(self) -> None:
        self.run_js(["loadRungs", "openSource", "switchView"], r"""
let resolveList;const sourceRequests=[];
api=url=>{
  if(url.startsWith('/api/source'))sourceRequests.push(url);
  return new Promise(done=>resolveList=done);
};
loadObjects=async()=>{};
$('rung-list').append(node('p','Earlier list'));
const loading=loadRungs();switchView('objects');
resolveList(rungResult(rungRow('late-rung',1)));await loading;
assert.equal(state.view,'objects');assert.equal(state.source,null);
assert.deepEqual(sourceRequests,[]);
assert.ok(contents($('rung-list')).includes('Earlier list'));
assert.ok(contents($('rung-detail')).includes('Select a source record'));
""")

    def test_newest_filter_result_alone_can_choose_an_initial_rung(self) -> None:
        self.run_js(["loadRungs", "openSource"], r"""
const pending=[],sourceRequests=[];run=async()=>{};
api=url=>url.startsWith('/api/rungs?')?new Promise(resolve=>pending.push(resolve))
  :(sourceRequests.push(url),Promise.resolve({run_id:'synthetic-run',source:{id:'new-result'},revision:1}));
let visible='';renderDetail=result=>{visible=result.source.id;};
const old=loadRungs();$('rung-search').value='changed';const current=loadRungs();
pending[1](rungResult(rungRow('new-result',2)));await current;
pending[0](rungResult(rungRow('old-result',1)));await old;
assert.deepEqual(sourceRequests,['/api/source?id=new-result&run_id=synthetic-run']);assert.equal(visible,'new-result');
assert.ok(contents($('rung-list')).includes('Rung 2'));
assert.equal(contents($('rung-list')).includes('Rung 1'),false);
""")


if __name__ == "__main__":
    unittest.main()
