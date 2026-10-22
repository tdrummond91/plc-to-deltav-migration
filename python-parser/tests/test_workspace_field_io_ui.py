"""Exercise module navigation, source-only evidence and existing group handoff."""
from __future__ import annotations

import subprocess
import unittest

from test_workspace_ui import ASSETS, NODE, Page


SCRIPT = (ASSETS / 'field-io.js').read_text(encoding='utf-8')
DOM = r"""
const assert=require('node:assert/strict');
class Element {
  constructor(tag){this.tagName=tag;this.children=[];this.events={};this.attributes={};this.className='';this.value='';this.disabled=false;this.hidden=false;this.checked=false;this._text='';}
  set textContent(text){this._text=String(text);this.children=[];}
  get textContent(){return this._text+this.children.map(child=>child.textContent).join(' ');}
  append(...nodes){nodes.forEach(child=>{child.parent=this;this.children.push(child);});}
  replaceChildren(...nodes){this.children=[];this._text='';this.append(...nodes);}
  addEventListener(name,callback){this.events[name]=callback;}
  setAttribute(name,value){this.attributes[name]=String(value);}
  removeAttribute(name){delete this.attributes[name];}
  fire(name){if(this.disabled)return;return this.events[name]?.({type:name,preventDefault(){}});}
}
const document={createElement:tag=>new Element(tag)},window={};
const proseCalls=[];window.PLCTranslation={renderProse:(target,original,wording,mode)=>{
  proseCalls.push([original,wording,mode]);target.textContent=mode==='english'&&wording?.text?wording.text:original;
}};
const all=root=>[root,...root.children.flatMap(all)];
const byClass=(root,cls)=>all(root).filter(item=>item.className.split(' ').includes(cls));
const findButton=(root,text)=>all(root).find(item=>item.tagName==='button'&&item.textContent===text);
const root=new Element('section'),calls=[],opened=[],grouped=[];
let project={project_path:'invented.sqlite',active_run:'run-1',revision:1};
const moduleCard=(id='module-1',changes={})=>({id,name:id==='module-1'?'Input card':'Output card',path:'Controller / '+id,description:'Description originale',
  controller:{id:'controller-1',name:'Invented controller',path:'Controller'},catalog_number:'1756-IB16',parent_module_name:'Local rack',slot:'3',
  location_status:'captured_slot',directions:['input'],field_type:'di',field_type_basis:'exact_catalog_reference',catalog_reference:'https://literature.rockwellautomation.com/idc/groups/literature/documents/um/example.pdf',
  point_count:16,point_count_basis:'documented_capacity',point_mapped_address_count:1,address_count:1,use_count:2,rung_count:2,group_member_ids:[id],grouping_scope:'module_declaration',...changes});
const address=(changes={})=>({id:'address-1',root_id:'module-root',root_name:'Local:3:I',suffix:'.Data.0',address:'Local:3:I.Data.0',direction:'input',field_type:'di',
  point_status:'documented_member_layout',channel:0,datatype:'BOOL',description:'Limite de niveau',aliases:[{id:'alias-1',name:'LevelInput',path:'Controller / LevelInput',description:'Niveau haut'}],
  aliases_total:1,aliases_truncated:false,uses:[{id:'use-1',instruction_id:'inst-1',rung_id:'rung-1',opcode:'XIC',role:'read',variable:'LevelInput',path:'Program / Routine / Rung 3',rung_number:3}],
  uses_total:1,use_page:1,use_pages:1,group_member_ids:['module-root'],grouping_scope:'backing_declaration',...changes});
const page=(items=[],changes={})=>({items,total:items.length,page:1,pages:1,page_size:24,...changes});
const result=(changes={})=>({available:true,notice:'',run_id:project.active_run,historical:false,snapshot_id:'invented',modules:page([moduleCard()]),
  presentation_mode:'original',selected_module:null,addresses:page(),coverage:{module_type_counts_scope:'all_captured_modules',modules_by_field_type:{di:1,do:0,ai:0,ao:0,unknown:0}},limitations:['Recorded uses do not prove physical wiring.'],...changes});
const detailResult=(id='module-1',changes={})=>result({selected_module:moduleCard(id,{ports:[{id:'port-1',port_id:'1',type:'ICP',address:'3',upstream:true}],
  roots:[{id:'module-root',name:'Local:3:I',direction:'input',name_origin:'exported',datatype:'AB_Input',description:'Donnees entree'}],rack_aliases:[],ports_total:1,roots_total:1,rack_aliases_total:0}),
  addresses:page([address()]),...changes});
let response=async path=>{const query=new URL(path,'http://localhost').searchParams;return query.has('module_id')?detailResult(query.get('module_id')):result();};
const options={getState:()=>project,api:async path=>{calls.push(path);return response(path);},openSource:(...args)=>opened.push(args),addToGroup:ids=>grouped.push(ids)};
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve};};
const params=()=>new URL(calls.at(-1),'http://localhost').searchParams;
const pick=async(index=0)=>{const check=byClass(root,'field-io-module-check')[index];check.checked=true;await check.fire('change');};
"""


class FieldIOPageTests(unittest.TestCase):
    def test_local_assets_and_dedicated_page(self) -> None:
        page = Page()
        self.assertIn('view-field-io', page.parents['field-io-browser'])
        scripts = [attrs.get('src') for tag, attrs in page.elements if tag == 'script']
        self.assertLess(scripts.index('/field-io.js'), scripts.index('/workspace.js'))
        self.assertIn('/field-io.css', [attrs.get('href') for tag, attrs in page.elements if tag == 'link'])
        self.assertNotIn('innerHTML', SCRIPT)
        self.assertNotIn('/api/mutate', SCRIPT)


@unittest.skipUnless(NODE, 'Node is optional developer tooling')
class FieldIOUiTests(unittest.TestCase):
    def run_js(self, checks: str) -> None:
        code = DOM + SCRIPT + '\n(async()=>{\n' + checks + '\n})()'
        code += ".then(()=>process.stdout.write('FIELD_IO_TEST_COMPLETE\\n'))"
        code += '.catch(error=>{console.error(error);process.exitCode=1;});'
        completed = subprocess.run([NODE, '-'], input=code, capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('FIELD_IO_TEST_COMPLETE', completed.stdout)

    def test_module_cards_and_source_uses_preserve_unresolved_point_evidence(self) -> None:
        self.run_js(r"""
response=async path=>new URL(path,'http://localhost').searchParams.has('module_id')?detailResult('module-1',{addresses:page([address({field_type:'unknown',channel:null,point_status:'unresolved'})])}):result();
const controller=window.PLCFieldIO.mount(root,options);await controller.refresh();
assert.equal(calls.length,1);assert.equal(params().get('run_id'),'run-1');
assert.ok(root.textContent.includes('DI · digital input'));assert.ok(root.textContent.includes('1756-IB16'));assert.ok(root.textContent.includes('Local rack'));
await findButton(root,'Input card').fire('click');
const detail=byClass(root,'field-io-detail')[0];
assert.ok(detail.textContent.includes('Unresolved field type'));assert.ok(detail.textContent.includes('BOOL'));
assert.ok(detail.textContent.includes('Limite de niveau'));assert.ok(root.textContent.includes('selected source language'));
await findButton(root,'Open backing declaration').fire('click');
await findButton(root,'LevelInput').fire('click');
await findButton(root,'XIC · rung 3 · read').fire('click');
assert.deepEqual(opened,[['module-root','object'],['alias-1','object'],['rung-1','rung']]);
assert.equal(grouped.length,0);assert.ok(root.textContent.includes('not physical wiring'));
const reference=all(detail).find(item=>item.tagName==='a');assert.equal(reference.target,'_blank');assert.equal(reference.rel,'noopener noreferrer');
""")

    def test_filters_and_three_paged_levels_send_bounded_backend_coordinates(self) -> None:
        self.run_js(r"""
response=async path=>{const q=new URL(path,'http://localhost').searchParams;if(!q.has('module_id'))return result({modules:page([moduleCard()],{total:25,pages:2,page:Number(q.get('page'))})});
return detailResult('module-1',{addresses:page([address({uses_total:13,use_pages:2,use_page:Number(q.get('use_page')||1)})],{total:25,pages:2,page:Number(q.get('signal_page')||1)})});};
const controller=window.PLCFieldIO.mount(root,options);await controller.refresh();
const type=byClass(root,'field-io-type')[0],direction=byClass(root,'field-io-direction')[0],search=byClass(root,'field-io-search')[0];
type.value='unknown';await type.fire('change');assert.equal(params().get('field_type'),'unknown');
direction.value='output';await direction.fire('change');assert.equal(params().get('direction'),'output');
search.value='Pump & #1/?';await byClass(root,'field-io-filters')[0].fire('submit');assert.equal(params().get('query'),search.value);
await findButton(root,'Next modules').fire('click');assert.equal(params().get('page'),'2');
await findButton(root,'Input card').fire('click');assert.equal(params().get('module_id'),'module-1');assert.equal(params().get('signal_page'),'1');
await findButton(root,'Next addresses').fire('click');assert.equal(params().get('signal_page'),'2');
await findButton(root,'Next rung uses').fire('click');assert.equal(params().get('address_id'),'address-1');assert.equal(params().get('use_page'),'2');assert.equal(params().get('signal_page'),'2');
await findButton(root,'Clear filters').fire('click');assert.equal(params().get('query'),'');assert.equal(params().get('page'),'1');assert.equal(params().get('field_type'),'');
assert.ok(byClass(root,'field-io-detail')[0].textContent.includes('Choose a module'));
""")

    def test_group_action_contains_only_selected_whole_module_ids_across_pages(self) -> None:
        self.run_js(r"""
response=async path=>{const p=Number(new URL(path,'http://localhost').searchParams.get('page'));return result({modules:page([moduleCard('module-'+p)],{total:25,pages:2,page:p})});};
const controller=window.PLCFieldIO.mount(root,options);await controller.refresh();await pick();
await findButton(root,'Next modules').fire('click');await pick();
await findButton(root,'Add whole modules to group').fire('click');assert.deepEqual(grouped,[['module-1','module-2']]);
assert.ok(root.textContent.includes('2 whole modules selected'));assert.ok(root.textContent.includes('does not save individual channel selections'));
await findButton(root,'Clear module selection').fire('click');assert.equal(findButton(root,'Add whole modules to group').disabled,true);
assert.equal(byClass(root,'field-io-module-check')[0].checked,false);
""")

    def test_backing_declarations_cannot_masquerade_as_whole_module_selection(self) -> None:
        self.run_js(r"""
response=async()=>result({modules:page([moduleCard('module-1',{group_member_ids:['tag-1'],grouping_scope:'backing_declaration'})])});
const controller=window.PLCFieldIO.mount(root,options);await controller.refresh();
assert.equal(byClass(root,'field-io-module-check')[0].disabled,true);assert.equal(findButton(root,'Add whole modules to group').disabled,true);
""")

    def test_old_directory_response_cannot_replace_new_filters(self) -> None:
        self.run_js(r"""
const pending=deferred();let count=0;response=async()=>++count===1?pending.promise:result({modules:page()});
const controller=window.PLCFieldIO.mount(root,options),first=controller.refresh();
const type=byClass(root,'field-io-type')[0];type.value='ao';await type.fire('change');
pending.resolve(result());await first;
assert.equal(byClass(root,'field-io-card').length,0);assert.ok(root.textContent.includes('No module cards match'));
assert.equal(byClass(root,'field-io-directory')[0].attributes['aria-busy'],undefined);
""")

    def test_old_detail_response_cannot_replace_later_module_selection(self) -> None:
        self.run_js(r"""
const pending=deferred();response=async path=>{const q=new URL(path,'http://localhost').searchParams;
return !q.has('module_id')?result({modules:page([moduleCard(),moduleCard('module-2')])}):q.get('module_id')==='module-1'?pending.promise:detailResult('module-2');};
const controller=window.PLCFieldIO.mount(root,options);await controller.refresh();
const first=findButton(root,'Input card').fire('click');await findButton(root,'Output card').fire('click');
pending.resolve(detailResult());await first;
assert.ok(byClass(root,'field-io-detail')[0].textContent.startsWith('Output card'));
assert.equal(byClass(root,'field-io-card-open').find(item=>item.textContent==='Output card').attributes['aria-pressed'],'true');
""")

    def test_run_or_project_change_clears_selections_and_blocks_old_actions(self) -> None:
        self.run_js(r"""
const controller=window.PLCFieldIO.mount(root,options);await controller.refresh();await pick();
await findButton(root,'Input card').fire('click');const oldSource=findButton(root,'Open module source');
project={...project,active_run:'run-2'};await findButton(root,'Add whole modules to group').fire('click');
await controller.refresh();assert.equal(grouped.length,0);assert.ok(root.textContent.includes('0 whole modules selected'));
await oldSource.fire('click');assert.equal(opened.length,0);
await pick();project={...project,project_path:'another.sqlite'};await controller.refresh();
assert.equal(byClass(root,'field-io-module-check')[0].checked,false);assert.ok(root.textContent.includes('0 whole modules selected'));
""")

    def test_inflight_run_change_and_deactivation_do_not_paint_old_evidence(self) -> None:
        self.run_js(r"""
const pending=deferred();response=async()=>pending.promise;
const controller=window.PLCFieldIO.mount(root,options),first=controller.refresh();controller.deactivate();
pending.resolve(result());await first;assert.equal(byClass(root,'field-io-card').length,0);
const next=deferred();response=async()=>next.promise;const second=controller.refresh();project={...project,active_run:'run-2'};
next.resolve(result({run_id:'run-1'}));await second;assert.equal(byClass(root,'field-io-card').length,0);
response=async()=>result();await controller.refresh();assert.equal(byClass(root,'field-io-card').length,1);
""")

    def test_errors_retry_and_wrong_identity_or_oversized_pages_are_rejected(self) -> None:
        self.run_js(r"""
response=async()=>{throw new Error('connection lost');};
const controller=window.PLCFieldIO.mount(root,options);await controller.refresh();assert.ok(root.textContent.includes('connection lost'));
response=async()=>result({run_id:'wrong'});await findButton(root,'Retry module cards').fire('click');assert.ok(root.textContent.includes('does not match'));
response=async()=>result({modules:page(Array.from({length:25},()=>moduleCard()))});await findButton(root,'Retry module cards').fire('click');assert.equal(byClass(root,'field-io-card').length,0);
response=async()=>result();await findButton(root,'Retry module cards').fire('click');
response=async()=>detailResult('wrong');await findButton(root,'Input card').fire('click');assert.ok(findButton(root,'Retry module details'));
response=async()=>detailResult();await findButton(root,'Retry module details').fire('click');assert.ok(root.textContent.includes('Local:3:I.Data.0'));
""")

    def test_use_page_errors_retry_and_old_use_results_do_not_restore_closed_details(self) -> None:
        self.run_js(r"""
response=async path=>new URL(path,'http://localhost').searchParams.has('module_id')?detailResult('module-1',{addresses:page([address({uses_total:13,use_pages:2})])}):result();
const controller=window.PLCFieldIO.mount(root,options);await controller.refresh();await findButton(root,'Input card').fire('click');
response=async()=>{throw new Error('uses interrupted');};await findButton(root,'Next rung uses').fire('click');assert.ok(root.textContent.includes('uses interrupted'));
const pending=deferred();response=async()=>pending.promise;const old=findButton(root,'Retry rung uses').fire('click');
response=async()=>result();await findButton(root,'Clear filters').fire('click');
pending.resolve(detailResult('module-1',{addresses:page([address({uses_total:13,use_pages:2,use_page:2})])}));await old;
assert.ok(byClass(root,'field-io-detail')[0].textContent.includes('Choose a module'));
""")

    def test_empty_unavailable_and_unimported_sources_show_no_invented_modules(self) -> None:
        self.run_js(r"""
project={project_path:'empty.sqlite'};const controller=window.PLCFieldIO.mount(root,options);await controller.refresh();assert.equal(calls.length,0);assert.ok(root.textContent.includes('Choose an analysis'));
project.active_run='run-1';response=async()=>result({available:false,notice:'Captured module evidence is unavailable.',modules:page()});
await controller.refresh();assert.ok(root.textContent.includes('Captured module evidence is unavailable.'));assert.equal(byClass(root,'field-io-card').length,0);
""")

    def test_untrusted_text_is_literal_and_catalog_links_require_official_https_host(self) -> None:
        self.run_js(r"""
response=async path=>new URL(path,'http://localhost').searchParams.has('module_id')?detailResult('module-1',{selected_module:moduleCard('module-1',{description:'<script>bad()</script>',catalog_reference:'https://rockwellautomation.com.attacker.invalid/file',ports:[],roots:[],rack_aliases:[]})}):result({modules:page([moduleCard('module-1',{name:'<img src=x>',description:'<svg>source</svg>'})])});
const controller=window.PLCFieldIO.mount(root,options);await controller.refresh();await findButton(root,'<img src=x>').fire('click');
assert.ok(root.textContent.includes('<script>bad()</script>'));assert.equal(all(root).some(item=>['script','img','svg','a'].includes(item.tagName)),false);
assert.ok(root.textContent.includes('not physical wiring'));
""")

    def test_configuration_dependent_capacity_and_member_index_stay_qualified(self) -> None:
        self.run_js(r"""
response=async path=>new URL(path,'http://localhost').searchParams.has('module_id')?detailResult('module-1',{selected_module:moduleCard('module-1',{field_type:'ai',point_count:8,point_count_basis:'maximum_configuration_dependent',ports:[],roots:[],rack_aliases:[]}),addresses:page([address({channel:3,configuration_status:'input_mode_unresolved'})])}):result();
const controller=window.PLCFieldIO.mount(root,options);await controller.refresh();await findButton(root,'Input card').fire('click');
assert.ok(root.textContent.includes('Maximum capacity (configuration dependent)'));assert.ok(root.textContent.includes('Member channel index'));
assert.ok(root.textContent.includes('does not establish the wired channel or terminal'));
""")

    def test_type_tiles_show_full_source_module_counts_and_filter_without_wiring_claims(self) -> None:
        self.run_js(r"""
const controller=window.PLCFieldIO.mount(root,options);await controller.refresh();
const tiles=byClass(root,'field-io-type-tile');assert.equal(tiles.length,5);
assert.equal(tiles[0].textContent,'DI · digital input · 1');assert.ok(root.textContent.includes('counts describe cards, not wired points'));
await tiles[4].fire('click');assert.equal(params().get('field_type'),'unknown');assert.equal(byClass(root,'field-io-type-tile')[4].attributes['aria-pressed'],'true');
response=async()=>result({coverage:{modules_by_field_type:{di:99}}});await controller.refresh();assert.equal(byClass(root,'field-io-type-tile').length,0);
""")

    def test_selected_language_renders_cached_wording_without_resetting_module_selection(self) -> None:
        self.run_js(r"""
response=async path=>{const q=new URL(path,'http://localhost').searchParams;
if(q.has('module_id'))return detailResult('module-1',{presentation_mode:'english',addresses:page([address({wording:{description:{text:'Level limit',status:'translated',text_truncated:true}}})])});
return result({presentation_mode:'english',modules:page([moduleCard('module-1',{wording:{description:{text:'Input module wording',status:'translated'}}})])});};
const controller=window.PLCFieldIO.mount(root,options);await controller.refresh();await pick();await findButton(root,'Input card').fire('click');
assert.ok(root.textContent.includes('Input module wording'));assert.ok(root.textContent.includes('Level limit'));
assert.ok(root.textContent.includes('Description preview shortened'));
assert.ok(proseCalls.some(([original,wording,mode])=>original==='Limite de niveau'&&wording.text==='Level limit'&&mode==='english'));
await controller.refresh();assert.ok(root.textContent.includes('1 whole module selected'));assert.equal(byClass(root,'field-io-module-check')[0].checked,true);
""")

    def test_exported_upstream_false_and_zero_strings_are_not_truthy_yes(self) -> None:
        self.run_js(r"""
const values=['false','0','true','1',null,'unexpected',false,true];
response=async path=>new URL(path,'http://localhost').searchParams.has('module_id')?detailResult('module-1',{selected_module:moduleCard('module-1',{
  ports:values.map((upstream,index)=>({id:'port-'+index,port_id:String(index),type:'ICP',address:'3',upstream})),roots:[],rack_aliases:[]})}):result();
const controller=window.PLCFieldIO.mount(root,options);await controller.refresh();await findButton(root,'Input card').fire('click');
const rows=byClass(root,'field-io-source-row');
assert.deepEqual(rows.map(row=>all(row).filter(item=>item.tagName==='dd').at(-1).textContent),
 ['No','No','Yes','Yes','Not captured','Unresolved (unexpected)','No','Yes']);
""")

    def test_documented_points_lead_while_status_and_unresolved_addresses_are_collapsed(self) -> None:
        self.run_js(r"""
response=async path=>new URL(path,'http://localhost').searchParams.has('module_id')?detailResult('module-1',{addresses:page([
  address({id:'root-address',address:'Local:3:I',point_status:'unresolved',field_type:'unknown',channel:null}),address(),
  address({id:'status-address',address:'Local:3:I.Fault',point_status:'unresolved',field_type:'unknown',channel:null})])}):result();
const controller=window.PLCFieldIO.mount(root,options);await controller.refresh();await findButton(root,'Input card').fire('click');
const points=byClass(root,'field-io-points')[0],other=byClass(root,'field-io-other-addresses')[0];
assert.equal(byClass(points,'field-io-address').length,1);assert.ok(points.textContent.includes('Local:3:I.Data.0'));
assert.equal(other.tagName,'details');assert.notEqual(other.open,true);assert.equal(byClass(other,'field-io-address').length,2);
assert.ok(root.textContent.includes('1 documented field-point address on this page'));assert.ok(root.textContent.includes('paging covers both sections'));
assert.ok(root.textContent.includes('Module total: 1 matched address.'));
assert.ok(root.textContent.includes('not a count of distinct wired points'));
assert.ok(other.textContent.includes('Other captured addresses and status (2 on this page)'));
""")
