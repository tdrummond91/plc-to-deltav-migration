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
        self.feed((ASSETS / "index.html").read_text(encoding="utf-8"))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append((tag, dict(attrs)))


def function(name: str) -> str:
    """Extract a top-level function from the shipped, formatted asset."""
    match = re.search(
        rf"^  (?:async )?function {name}\(.*?(?=^  (?:async )?function |^  let |^  \$|^  //|^  run\()",
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
  }
  append(...children) {for(const child of children){child.parent=this;this.children.push(child);}}
  prepend(...children) {children.forEach(child=>child.parent=this);this.children.unshift(...children);}
  replaceChildren(...children){this.children=[];this.append(...children);}
  addEventListener(name,callback){this.events[name]=callback;}
  setAttribute(name,value){this.attributes[name]=value;}
  removeAttribute(name){delete this.attributes[name];}
  remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);}
  get childNodes(){return this.children;}
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
const document={createTextNode:text=>node('#text',text)};
let $, api, window={innerWidth:1600}, renderDetail, loadObjects;
let selectedCategories=['category-pid'];
const categoryPicker=()=>({element:node('div'),values:()=>selectedCategories});
let activeGroups=[];
const groups=()=>activeGroups;
let commands=[],modalBody,saveDialog,notice='',state={project:{revision:1},selected:new Set(['rung-a','rung-b']),source:null,dirty:false,detailSerial:0,view:'rungs'};
const statusNames={unreviewed:'Not reviewed',needs_review:'Needs review',confirmed:'Confirmed'};
const discard=()=>true;
const modal=(title,build,save)=>{modalBody=node('div');build(modalBody);saveDialog=save;};
let mutate=async command=>{commands.push(command);};
const loadRungs=async()=>{};
const openSource=async()=>{};
const notify=text=>{notice=text;};
let run=async callback=>callback();
const Event=function(type){this.type=type;};
"""


class WorkspacePageTests(unittest.TestCase):
    def test_page_has_one_source_first_entry_and_local_assets(self) -> None:
        page = Page()
        ids = [attrs["id"] for _, attrs in page.elements if "id" in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue({"source-name", "source-count", "routine-tree", "rung-list", "rung-detail", "object-list", "group-list", "history", "reconciliation"}.issubset(ids))
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
        keys = re.findall(r'localStorage\.setItem\(\s*"([^"]+)"', SCRIPT)
        self.assertCountEqual(keys, ["plc-workspace-guide-v1", "plc-workspace-theme-v1", "plc-workspace-reviewer-v1"])
        self.assertIn("No demonstration data is loaded", SCRIPT)
        self.assertIn("__WORKSPACE_TOKEN__", (ASSETS / "index.html").read_text(encoding="utf-8"))


@unittest.skipUnless(NODE, "Node is optional developer tooling")
class WorkspaceInteractionTests(unittest.TestCase):
    def run_js(self, names: list[str], checks: str) -> None:
        dom = DOM.replace("const openSource=async()=>{};", "") if "openSource" in names else DOM
        code = dom + "\n" + "\n".join(function(name) for name in names)
        code += "\n(async()=>{\n" + checks + "\n})().catch(error=>{console.error(error);process.exitCode=1;});"
        result = subprocess.run([NODE, "-"], input=code, capture_output=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

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

    def test_delayed_source_request_cannot_replace_new_unsaved_edits(self) -> None:
        self.run_js(["openSource"], r"""
const panel=node('section');panel.append(node('textarea','Unsaved correction'));
$=()=>panel;let resolve;
api=()=>new Promise(done=>resolve=done);let renders=0;
renderDetail=()=>renders++;
const loading=openSource('rung-next');assert.equal(panel.inert,true);assert.equal(panel.attributes['aria-busy'],'true');
state.dirty=true;resolve({source:{id:'rung-next'},revision:2});await loading;
assert.equal(renders,0);assert.ok(contents(panel).includes('Unsaved correction'));assert.equal(panel.inert,false);
assert.ok(notice.includes('unsaved changes'));
""")

    def test_out_of_order_source_responses_leave_latest_selection_visible(self) -> None:
        self.run_js(["openSource"], r"""
const panel=node('section');$=()=>panel;const pending=[];
api=()=>new Promise(resolve=>pending.push(resolve));let visible='';
renderDetail=result=>visible=result.source.id;
const first=openSource('rung-a'),second=openSource('rung-b');
pending[1]({source:{id:'rung-b'},revision:1});await second;
pending[0]({source:{id:'rung-a'},revision:1});await first;
assert.equal(visible,'rung-b');assert.equal(state.source.source.id,'rung-b');assert.equal(panel.inert,false);
""")

    def test_deep_links_accept_only_bounded_source_identifiers_and_known_views(self) -> None:
        self.run_js(["requestedLocation"], r"""
window.location={hash:'#view=rungs&source=rung_abc'};
assert.deepEqual(requestedLocation(),{view:'rungs',source:'rung_abc'});
window.location.hash='#view=objects&source=tag_abc';assert.equal(requestedLocation().source,'tag_abc');
for(const hash of ['#main','#view=bad','#view=rungs&source=a&source=b','#view=rungs&extra=x','#view=groups&source=a','#view=rungs&source=%00','#view=rungs&source='+ 'a'.repeat(257),'#view=rungs&source='+ 'a'.repeat(2049)]){
  window.location.hash=hash;assert.equal(requestedLocation(),null,hash);
}
window.location.hash='';assert.deepEqual(requestedLocation(),{view:'rungs',source:''});
""")


if __name__ == "__main__":
    unittest.main()
