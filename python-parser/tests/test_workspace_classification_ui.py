"""Exercise classification navigation and edit contracts using invented evidence."""
from __future__ import annotations

import subprocess
import unittest

from test_workspace_ui import ASSETS, NODE, Page, function


SCRIPT = (ASSETS / "classification.js").read_text(encoding="utf-8")
DOM = r"""
const assert = require('node:assert/strict');
class Element {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.events = {}; this.attributes = {};
    this.className = ''; this.value = ''; this.disabled = false; this.hidden = false;
    this.checked = false; this._text = '';
  }
  set textContent(text) {this._text = String(text); this.children = [];}
  get textContent() {return this._text + this.children.map(item => item.textContent).join(' ');}
  append(...nodes) {nodes.forEach(node => {node.parent = this; this.children.push(node);});}
  replaceChildren(...nodes) {this.children = []; this._text = ''; this.append(...nodes);}
  addEventListener(name, callback) {this.events[name] = callback;}
  setAttribute(name, value) {this.attributes[name] = value;}
  removeAttribute(name) {delete this.attributes[name];}
  fire(name) {return this.events[name]?.({type:name});}
}
const document = {createElement: tag => new Element(tag)};
const window = {};
const all = root => [root, ...root.children.flatMap(all)];
const byClass = (root, cls) => all(root).filter(node => node.className.split(' ').includes(cls));
const findButton = (root, text) => all(root).find(node => node.tagName === 'button' && node.textContent === text);
const openEvidence = async () => {const details=byClass(root,'classification-evidence')[0];details.open=true;await details.fire('toggle');};
const root = new Element('section');
const categories = [
  {id: 'dc', label:'DC — discrete calculation', description:'A true/false result.'},
  {id: 'ac', label:'AC — analogue calculation', description:'A floating point result.'},
  {id: 'platform', label:'Controller/platform implementation', description:'Implementation context; retain any required behavior.'},
];
const result = (changes = {}) => ({
  items: [{id:'proposal-1', name:'Invented_Flag', category_ids:['dc'], member_ids:['tag-one','rung-one'],
    rung_ids:['rung-one'], anchor_id:'rung-one', reason:'Boolean result is written by this logic.',
    basis:'A declared BOOL destination links these uses.', limitations:['Runtime behavior still needs review.'],
    parameters:[{name:'Preset', value:'250', source_id:'tag-one'}], migration_hint:'Preserve the Boolean behavior.',
    effective_migration_status:'unreviewed', effective_category_ids:['dc']}],
  total:1, page:1, page_size:50, pages:1, categories, coverage:{},
  limitations:['A source association is not an approved module.'], run_id:'invented-run', ...changes,
});
const calls = [], opened = [], adopted = [], edited = [];
let response = async () => result(), project = {active_run:'invented-run', revision:7};
const options = {
  getState: () => project,
  api: async path => {calls.push(path); return response(path);},
  openSource: (...args) => opened.push(args),
  adopt: async (...args) => adopted.push(args),
  editGroup: id => edited.push(id),
  reportLink: (text,id) => {const a = new Element('a'); a.textContent = text; a.href = '/analysis?language=english#source='+encodeURIComponent(id); return a;},
};
const deferred = () => {let resolve; const promise = new Promise(done => resolve=done); return {promise,resolve};};
"""


class ClassificationPageTests(unittest.TestCase):
    def test_browser_precedes_saved_groups_and_uses_local_assets(self) -> None:
        elements = Page().elements
        ids = [attrs.get("id") for _, attrs in elements]
        self.assertLess(ids.index("classification-browser"), ids.index("group-list"))
        scripts = [attrs.get("src") for tag, attrs in elements if tag == "script"]
        self.assertLess(scripts.index("/classification.js"), scripts.index("/workspace.js"))
        self.assertIn("/classification.css", [attrs.get("href") for tag, attrs in elements if tag == "link"])


@unittest.skipUnless(NODE, "Node is optional developer tooling")
class ClassificationUiTests(unittest.TestCase):
    def run_js(self, checks: str, extra: str = "") -> None:
        code = DOM + SCRIPT + extra + "\n(async () => {\n" + checks + "\n})()"
        code += ".then(() => process.stdout.write('CLASSIFICATION_TEST_COMPLETE\\n'))"
        code += ".catch(error => {console.error(error); process.exitCode = 1;});"
        completed = subprocess.run([NODE, "-"], input=code, capture_output=True, encoding="utf-8", timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("CLASSIFICATION_TEST_COMPLETE", completed.stdout)

    def test_source_linked_proposals_are_visible_without_creating_groups(self) -> None:
        self.run_js(r"""
const controller = window.PLCClassification.mount(root, options); await controller.refresh();
assert.equal(calls.length, 1); assert.equal(adopted.length, 0);
assert.ok(root.textContent.includes('DC — discrete calculation'));
assert.ok(root.textContent.includes('Boolean result is written'));
await openEvidence();
assert.ok(root.textContent.includes('Runtime behavior still needs review'));
assert.ok(root.textContent.includes('250'));
assert.ok(root.textContent.includes('2 linked source records · 1 rungs'));
await findButton(root,'Inspect source').fire('click');
await findButton(root,'Open source').fire('click');
assert.deepEqual(opened,[['rung-one','rung'],['tag-one','object']]);
assert.ok(all(root).find(node => node.tagName === 'a').href.includes('language=english'));
assert.equal(byClass(root,'classification-migration-filter')[0].value,'');
assert.ok(root.textContent.includes('Unknown and uncertain items stay visible'));
""")

    def test_group_page_size_preserves_filter_and_resets_first_page(self) -> None:
        self.run_js(r"""
const controller=window.PLCClassification.mount(root,options);await controller.refresh();
const category=byClass(root,'classification-category-filter')[0];category.value='dc';await category.fire('change');
assert.equal(new URL(calls[0],'http://local').searchParams.get('page_size'),'50');
const size=all(root).find(n=>n.attributes['aria-label']==='Groups per page');size.value='200';await size.fire('change');
const query=new URL(calls.at(-1),'http://local').searchParams;
assert.equal(query.get('category'),'dc');assert.equal(query.get('page'),'1');assert.equal(query.get('page_size'),'200');
assert.deepEqual(adopted,[]);assert.deepEqual(edited,[]);
""")

    def test_category_migration_query_and_pagination_reach_backend(self) -> None:
        self.run_js(r"""
response = async () => result({page:1,pages:2,total:26});
const controller = window.PLCClassification.mount(root,options); await controller.refresh();
const category = byClass(root,'classification-category-filter')[0], migration = byClass(root,'classification-migration-filter')[0];
category.value = 'ac'; await category.fire('change');
assert.equal(new URL(calls.at(-1),'http://localhost').searchParams.get('category'),'ac');
assert.ok(byClass(root,'classification-filter-description')[0].textContent.includes('floating point'));
migration.value = 'in_scope'; await migration.fire('change');
const search = byClass(root,'classification-search')[0]; search.value = 'Loop & value/?';
await findButton(root,'Next →').fire('click');
const query = new URL(calls.at(-1),'http://localhost').searchParams;
assert.equal(query.get('migration'),'in_scope'); assert.equal(query.get('query'),'Loop & value/?');
assert.equal(query.get('page'),'2');
await findButton(root,'Clear filters').fire('click');
const cleared = new URL(calls.at(-1),'http://localhost').searchParams;
assert.equal(cleared.get('page'),'1'); assert.equal(cleared.get('query'),''); assert.equal(cleared.get('category'),''); assert.equal(cleared.get('migration'),'');
""")

    def test_adoption_is_explicit_and_saved_group_opens_without_duplicate(self) -> None:
        self.run_js(r"""
const controller = window.PLCClassification.mount(root,options); await controller.refresh();
await findButton(root,'Adopt & edit group').fire('click');
assert.equal(adopted.length,1); assert.equal(adopted[0][0].id,'proposal-1'); assert.equal(adopted[0][1],'invented-run');
response = async () => {const data=result();data.items[0].saved_group_id='saved-1'; return data;};
await controller.refresh(); await findButton(root,'Edit saved group').fire('click');
assert.deepEqual(edited,['saved-1']); assert.equal(adopted.length,1);
""")

    def test_effective_categories_and_stale_decision_are_shown(self) -> None:
        self.run_js(r"""
response = async () => {const data=result(); Object.assign(data.items[0],{effective_category_ids:['ac','dc'],effective_migration_status:'investigate',needs_revalidation:true});return data;};
const controller=window.PLCClassification.mount(root,options);await controller.refresh();
const card=byClass(root,'classification-card')[0];
assert.ok(card.textContent.includes('AC — analogue calculation'));
assert.ok(card.textContent.includes('DC — discrete calculation'));
assert.ok(card.textContent.includes('Investigate before deciding'));
assert.ok(card.textContent.includes('Source evidence changed'));
assert.ok(card.textContent.includes('remains in scope'));
""")

    def test_group_fields_preserve_custom_categories_and_save_multi_function_decisions(self) -> None:
        self.run_js(r"""
const editor=window.PLCClassification.groupFields({function_categories:['dc','custom'],migration_status:'replace',migration_note:'Existing reason',needs_revalidation:true},categories);
assert.ok(editor.element.textContent.includes('true/false'));
assert.ok(editor.element.textContent.includes('floating point'));
assert.ok(editor.element.textContent.includes('source evidence changed'));
const checks=all(editor.element).filter(node=>node.tagName==='input');
assert.equal(checks[0].checked,true); assert.equal(checks[3].checked,true);
checks[1].checked=true;await checks[1].fire('change');
byClass(editor.element,'classification-migration-edit')[0].value='exclude';
byClass(editor.element,'classification-note-edit')[0].value='  Controller diagnostics handled elsewhere.  ';
assert.deepEqual(editor.values(),{function_categories:['dc','custom','ac'],migration_status:'exclude',migration_note:'Controller diagnostics handled elsewhere.'});
assert.ok(editor.element.textContent.includes('source evidence and saved review stay available'));
""")

    def test_untrusted_source_fields_are_rendered_as_text(self) -> None:
        self.run_js(r"""
response=async()=>{const data=result();Object.assign(data.items[0],{name:'<img src=x onerror=alert(1)>',reason:'<script>unsafe()</script>',parameters:[{name:'<svg>',value:'<b>unsafe</b>'}]});return data;};
const controller=window.PLCClassification.mount(root,options);await controller.refresh();
await openEvidence();
assert.ok(root.textContent.includes('<script>unsafe()</script>'));
assert.ok(root.textContent.includes('<b>unsafe</b>'));
assert.equal(all(root).some(node=>['script','img','svg','b'].includes(node.tagName)),false);
""")

    def test_stale_response_does_not_replace_new_filters(self) -> None:
        self.run_js(r"""
const pending=deferred();let count=0;
response=async()=>++count===1?pending.promise:result({items:[],total:0});
const controller=window.PLCClassification.mount(root,options);const first=controller.refresh();
await controller.refresh();pending.resolve(result());await first;
assert.equal(byClass(root,'classification-card').length,0);
assert.ok(root.textContent.includes('No detected groups match'));
assert.equal(root.attributes['aria-busy'],undefined);
""")

    def test_large_group_builds_source_links_lazily_and_pages_every_member(self) -> None:
        self.run_js(r"""
response=async()=>{
  const data=result(),item=data.items[0];
  item.member_ids=Array.from({length:1000},(_,i)=>'source-'+i);
  item.rung_ids=item.member_ids.slice(0,300);item.anchor_id='source-0';
  item.source_labels=Object.fromEntries(item.member_ids.map((id,i)=>[id,'Invented / Routine / rung '+i]));
  item.migration_hint='platform_detail';return data;
};
const controller=window.PLCClassification.mount(root,options);await controller.refresh();
assert.equal(byClass(root,'classification-source-links').length,0);
assert.ok(all(root).length<100);
assert.ok(root.textContent.includes('controller-specific implementation details'));
await openEvidence();
let links=byClass(root,'classification-source-links')[0];
assert.equal(links.children.length,50);
assert.equal(links.children[0].textContent,'Invented / Routine / rung 0');
assert.equal(findButton(root,'← Previous source links').disabled,true);
for(let page=1;page<20;page++)await findButton(root,'Next source links →').fire('click');
assert.equal(links.children.length,50);assert.equal(links.children[49].textContent,'Invented / Routine / rung 999');
assert.equal(findButton(root,'Next source links →').disabled,true);
await links.children[49].fire('click');assert.deepEqual(opened.at(-1),['source-999','object']);
const details=byClass(root,'classification-evidence')[0];details.open=false;await details.fire('toggle');details.open=true;await details.fire('toggle');
assert.equal(byClass(root,'classification-source-links').length,1);
assert.ok(all(root).length<200);
""")

    def test_coverage_distinguishes_linked_rungs_from_fully_identified_functions(self) -> None:
        self.run_js(r"""
response=async()=>result({coverage:{source_rungs:4606,represented_rungs:4500,unrepresented_rungs:106,truncated:true}});
const controller=window.PLCClassification.mount(root,options);await controller.refresh();
const text=byClass(root,'classification-coverage')[0].textContent;
assert.ok(text.includes('4,500 of 4,606'));assert.ok(text.includes('does not mean every function is classified'));
assert.ok(text.includes('106 rungs still have no proposal'));assert.ok(text.includes('coverage is partial'));
""")

    def test_failed_requests_have_retry_and_no_old_actions(self) -> None:
        self.run_js(r"""
const controller=window.PLCClassification.mount(root,options);await controller.refresh();
response=async()=>{throw new Error('Saved snapshot unavailable.');};await controller.refresh();
assert.equal(byClass(root,'classification-card').length,0);
assert.ok(root.textContent.includes('Saved snapshot unavailable.'));
response=async()=>result();await findButton(root,'Retry classifications').fire('click');
assert.equal(byClass(root,'classification-card').length,1);
""")

    def test_no_active_run_makes_no_classification_request(self) -> None:
        self.run_js(r"""
project={active_run:null};const controller=window.PLCClassification.mount(root,options);await controller.refresh();
assert.equal(calls.length,0);assert.ok(root.textContent.includes('Choose an analysis run'));
""")

    def test_workspace_editor_sends_explicit_function_and_migration_fields(self) -> None:
        setup = r"""
const node=(tag,text,cls)=>{const n=new Element(tag);if(text!==undefined&&text!==null)n.textContent=text;n.className=cls||'';return n;};
const input=(value,placeholder)=>{const n=node('input');n.value=value;n.placeholder=placeholder;return n;};
const field=(text,input)=>{const n=node('label',text);n.append(input);return n;};
const clear=n=>n.replaceChildren();const button=(text,click)=>{const n=node('button',text);n.addEventListener('click',click);return n;};
const discard=()=>true;let saved,modalBody,command,modalDirty=false;
const state={project:{classification_categories:categories}};
const modal=(title,build,save)=>{modalBody=node('div');build(modalBody);saved=save;};
const mutate=async value=>{command=value;};const notify=()=>{};
""" + "const select=(items,value)=>{const element=node('select');element.value=value;return element;};\n" + function("pageSizeControl") + function("groupEditor")
        self.run_js(r"""
groupEditor({id:'saved-1',name:'Test group',member_ids:['tag-one'],function_categories:['dc'],migration_status:'retain',migration_note:'Preserve function',proposal_id:'proposal-1'});
await saved();assert.equal(command.op,'group');assert.equal(command.id,'saved-1');
assert.deepEqual(command.member_ids,['tag-one']);assert.deepEqual(command.function_categories,['dc']);
assert.equal(command.migration_status,'retain');assert.equal(command.migration_note,'Preserve function');
assert.equal(Object.hasOwn(command,'proposal_id'),false);
""", setup)

    def test_subset_decision_explains_why_the_original_proposal_remains(self) -> None:
        self.run_js(r"""
response=async()=>{const data=result();Object.assign(data.items[0],{migration_scope_limited:true,saved_member_count:1,effective_migration_status:'investigate',saved_group_id:'subset'});return data;};
const controller=window.PLCClassification.mount(root,options);await controller.refresh();
assert.ok(root.textContent.includes('saved group contains 1 source records'));
assert.ok(root.textContent.includes('decision apply to the saved members only'));
assert.ok(root.textContent.includes('larger proposal remains in scope'));
""")


if __name__ == "__main__":
    unittest.main()
