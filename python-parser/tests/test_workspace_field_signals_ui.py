"""Exercise individual-signal drafts, explicit packages and bounded source navigation."""
from __future__ import annotations

import subprocess
import unittest

from test_workspace_ui import ASSETS, NODE


SCRIPT = (ASSETS / 'field-signals.js').read_text(encoding='utf-8')
DOM = r"""
const assert=require('node:assert/strict');
class Element {
 constructor(tag){this.tagName=tag;this.children=[];this.events={};this.attributes={};this.style={};this.className='';this.value='';this.disabled=false;this.hidden=false;this.checked=false;this._text='';}
 set textContent(text){this._text=String(text);this.children=[];}
 get textContent(){return this._text+this.children.map(child=>child.textContent).join(' ');}
 append(...nodes){nodes.forEach(child=>{child.parent=this;this.children.push(child);});}
 replaceChildren(...nodes){this.children=[];this._text='';this.append(...nodes);}
 addEventListener(name,callback){this.events[name]=callback;}
 setAttribute(name,value){this.attributes[name]=String(value);}
 removeAttribute(name){delete this.attributes[name];}
 remove(){if(this.parent)this.parent.children=this.parent.children.filter(child=>child!==this);}
 contains(target){return this===target||this.children.some(child=>child.contains(target));}
 getBoundingClientRect(){return {left:600,top:200,bottom:230,width:380,height:220};}
 focus(){document.activeElement=this;this.events.focus?.({target:this});}
 fire(name,extra={}){if(this.disabled)return;return this.events[name]?.({type:name,target:this,preventDefault(){},...extra});}
}
const document={events:{},body:new Element('body'),createElement:tag=>new Element(tag),addEventListener(name,callback){this.events[name]=callback;}};
const window={innerWidth:1200,innerHeight:800,events:{},addEventListener(name,callback){this.events[name]=callback;}};
const all=root=>[root,...root.children.flatMap(all)],byClass=(root,cls)=>all(root).filter(item=>item.className.split(' ').includes(cls));
const findButton=(root,text)=>all(root).find(item=>item.tagName==='button'&&item.textContent===text);
const findLink=(root,text)=>all(root).find(item=>item.tagName==='a'&&item.textContent===text);
const root=new Element('section');document.body.append(root);
const page=(items=[],size=50,changes={})=>({items,total:items.length,page:1,pages:1,page_size:size,...changes});
const binding=(id='address-1')=>({run_id:'run-1',snapshot_id:'snapshot-1',root_id:'module-root',suffix:'.Data.'+(id==='address-1'?'0':'1'),address_id:id,evidence_signature:'a'.repeat(64)});
const sourceRow=(id='address-1',changes={})=>({id,address:id==='address-1'?'Local:3:I.Data.0':'Local:3:I.Data.1',root_id:'module-root',suffix:binding(id).suffix,
 module_id:'module-1',direction:'input',field_type:'di',candidate_field_types:[],mapping_status:'documented_member_layout',mapping_reason:'exact_catalog_direction_member_and_captured_profile_type',
 aliases:[{id:'alias-'+id,name:id==='address-1'?'LevelSwitch':'SecondSwitch'}],source_annotations:[{id:'note-1',owner_id:'module-root',kind:'member_comment',text:'Niveau haut'}],
 description:'Captured source description',binding:binding(id),hardware:{name:'Rack input module',catalog_number:'1756-IB16',slot:'3',parent_module_name:'Local rack',controller:{name:'Invented controller'}},...changes});
const rung=(id='rung-1',changes={})=>({id,rung_id:id,number:3,path:'Program / Routine / '+id,candidate_role:'reference',
 association_reason:'direct_exact_address_use',role_notice:'Suggested review role only; not proof of scaling or alarm consequence.',...changes});
let project={project_path:'invented.sqlite',active_run:'run-1',revision:1,signals:[],groups:[]},rows=[sourceRow()],calls=[],writes=[],opened=[];
const savedSignal=(changes={})=>({id:'signal-1',binding:binding(),target_name:'LS_001',description:'Engineering words',field_type:'di',active:true,needs_revalidation:false,...changes});
const group=(changes={})=>({id:'group-1',name:'Existing package',member_ids:['existing-rung'],signal_ids:['other-signal'],member_roles:{'existing-rung':'alarm'},migration_status:'unreviewed',...changes});
function result(path){const query=new URL(path,'http://localhost').searchParams;
 const detailSize=Number(query.get('detail_page_size')||10);
 const live=rows.map(row=>({...row,saved_signal:project.signals.find(item=>item.binding.address_id===row.id&&item.binding.run_id===project.active_run)||null}));
 const row=live.find(row=>row.id===query.get('signal_id'));
 return {available:true,run_id:project.active_run,revision:project.revision,snapshot_id:'snapshot-1',presentation_mode:'original',signals:page(live,Number(query.get('page_size')||50)),coverage:{},limitations:['No physical wiring is inferred.'],
 selected_signal:row?{...row,direct_rungs:page([rung()],detailSize),direct_uses:page([],detailSize),related_rungs:page([rung('rung-2',{candidate_role:'scaling',association_reason:'shared_address_with_direct_use_rung',
 associations:[{address:'CalculatedValue',from_rung_id:'rung-1'}]})],detailSize)}:null};}
let response=async path=>path==='/api/state'?structuredClone(project):result(path),mutationHook=null;
const options={getState:()=>project,api:async path=>{calls.push(path);return response(path);},openSource:(...args)=>opened.push(args),
 mutate:async(command,revision)=>{writes.push({command:structuredClone(command),revision});
  if(revision!==project.revision)throw Object.assign(new Error('Revision conflict'),{status:409});
  if(command.op==='signal'){
   const old=project.signals.find(item=>item.id===command.id);
   const saved={...(old||savedSignal({id:'signal-new',binding:structuredClone(command.binding),target_name:'',description:''})),...command};delete saved.op;delete saved.confirm;
   if(command.confirm)saved.needs_revalidation=false;
   project.signals=project.signals.filter(item=>item.id!==saved.id).concat(saved);
  } else if(command.op==='group'){
   const saved={...(project.groups.find(item=>item.id===command.id)||{}),...command,id:command.id||'group-new'};delete saved.op;
   project.groups=project.groups.filter(item=>item.id!==saved.id).concat(saved);
  } else if(command.op==='signal_rebind'){
   project.signals=project.signals.map(item=>item.id===command.id?{...item,binding:structuredClone(command.binding),active:true,needs_revalidation:true}:item);
  }
  project={...project,revision:project.revision+1};if(mutationHook)await mutationHook();return structuredClone(project);
 }};
const edit=(cls,value,event='input')=>{const control=byClass(root,cls)[0];assert.ok(control,cls);control.value=value;return control.fire(event);};
const choosePackage=async(value='group-1')=>edit('field-signals-package-choice',value,'change');
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve};};
"""


@unittest.skipUnless(NODE, 'Node is optional developer tooling')
class FieldSignalsUiTests(unittest.TestCase):
    def run_js(self, checks: str) -> None:
        code = DOM + SCRIPT + '\n(async()=>{\n' + checks + '\n})()'
        code += ".then(()=>process.stdout.write('FIELD_SIGNALS_TEST_COMPLETE\\n'))"
        code += '.catch(error=>{console.error(error);process.exitCode=1;});'
        completed = subprocess.run([NODE, '-'], input=code, capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('FIELD_SIGNALS_TEST_COMPLETE', completed.stdout)

    def test_controller_sections_keep_signal_rows_and_candidates_explicit(self) -> None:
        self.run_js(r"""
rows.push(sourceRow('address-2',{field_type:'unknown',candidate_field_types:['ai'],mapping_status:'review_mapping'}));
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const table=byClass(root,'field-signals-table')[0];
assert.ok(table.textContent.includes('Physical channel Source alias / address Source description DeltaV name Package status Info'));
assert.ok(table.textContent.includes('LevelSwitch'));assert.ok(table.textContent.includes('Local:3:I.Data.0'));assert.ok(table.textContent.includes('Niveau haut'));
assert.ok(table.textContent.includes('Unresolved AI candidate'));assert.equal(table.textContent.includes('1756-IB16'),false);assert.equal(table.textContent.includes('Local rack'),false);
assert.equal(byClass(root,'field-signals-controller').length,1);assert.ok(byClass(root,'field-signals-controller')[0].textContent.includes('Invented controller'));
assert.equal(writes.length,0);assert.equal(controller.hasUnsavedChanges(),false);
""")

    def test_controller_disclosures_and_expand_all_preserve_state_after_refresh(self) -> None:
        self.run_js(r"""
rows.push(sourceRow('address-2',{hardware:{controller:{id:'controller-2',name:'Second controller'}}}));
response=async path=>({...result(path),controller_counts:[{controller_id:'Invented controller',total:60},{controller_id:'controller-2',total:12}]});
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();let panels=byClass(root,'field-signals-controller');
assert.equal(panels.length,2);assert.equal(panels.every(panel=>panel.open),true);assert.ok(panels[0].textContent.includes('1 shown · 60 matching signals'));
panels[0].open=false;await panels[0].fire('toggle');await controller.refresh();panels=byClass(root,'field-signals-controller');assert.equal(panels[0].open,false);assert.equal(panels[1].open,true);
await findButton(root,'Collapse all').fire('click');assert.equal(panels.every(panel=>!panel.open),true);
await findButton(root,'Expand all').fire('click');assert.equal(panels.every(panel=>panel.open),true);
assert.equal(writes.length,0);
""")

    def test_preferred_description_and_conflicts_do_not_follow_annotation_order(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{description:'Preferred alias description',description_selection:{preferred_annotation_id:'preferred',basis:'exact_alias_description',status:'review_required',conflict:true,candidate_count:2,candidates:[{id:'preferred',owner_id:'alias-1',kind:'description',owner_name:'AliasName'}]},
 source_annotations:[{id:'backing',text:'Broad backing description'},{id:'preferred',text:'Preferred alias description'}]})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
assert.equal(byClass(root,'field-signals-wording-preview')[0].textContent,'Preferred alias description');
assert.ok(byClass(root,'field-signals-source-description')[0].textContent.includes('Conflicting source wording'));
await controller.openSignal('address-1');assert.ok(root.textContent.includes('Description selection evidence'));assert.equal(writes.length,0);
rows=[sourceRow('address-1',{description:'Preferred module fallback',description_selection:{preferred_annotation_id:'outside-preview',basis:'module_description',status:'selected',conflict:false}})];
await controller.refresh();assert.equal(byClass(root,'field-signals-wording-preview')[0].textContent,'Preferred module fallback');
""")

    def test_numeric_payload_hint_is_not_presented_as_documented_physical_ai(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{field_type:'unknown',candidate_field_types:['ai'],mapping_status:'review_mapping',suggested_type_basis:'qualified_floating_channel_and_direction',direction:'input'})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();const table=byClass(root,'field-signals-table')[0];
assert.ok(table.textContent.includes('Unresolved Numeric input candidate'));assert.equal(table.textContent.includes('AI Source-mapped'),false);
assert.equal(writes.length,0);assert.equal(controller.hasUnsavedChanges(),false);
""")

    def test_page_size_changes_request_and_keeps_unsaved_signal_edits(self) -> None:
        self.run_js(r"""
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
assert.equal(new URL(calls[0],'http://localhost').searchParams.get('page_size'),'50');
await edit('field-signals-target-name','Retain my draft');
const selector=byClass(root,'field-signals-page-size')[0];assert.deepEqual(selector.children.map(option=>option.value),['10','50','100','200','500']);
for(const size of ['10','100','200','500']){await edit('field-signals-page-size',size,'change');const request=new URL(calls.at(-1),'http://localhost');assert.equal(request.searchParams.get('page_size'),size);assert.equal(request.searchParams.get('page'),'1');}
assert.equal(controller.hasUnsavedChanges(),true);assert.equal(byClass(root,'field-signals-target-name')[0].value,'Retain my draft');assert.equal(writes.length,0);
""")

    def test_proposed_names_are_visible_and_saved_only_explicitly_with_source_metadata(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{suggested_target_name:'XS_Example',source_metadata:{tag_type:'Alias',alias_for:'Local:3:I.Data.0',base_name:'ModuleInput',data_type:'BOOL',radix:'Decimal',external_access:'Read/Write'}})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();assert.ok(byClass(root,'field-signals-name')[0].textContent.includes('XS_Example Proposed · unreviewed'));
await controller.openSignal('address-1');assert.equal(byClass(root,'field-signals-target-name')[0].value,'XS_Example');assert.equal(controller.hasUnsavedChanges(),false);assert.equal(writes.length,0);
const facts=byClass(root,'field-signals-source-facts')[0];assert.ok(facts.textContent.includes('Tag type Alias'));assert.ok(facts.textContent.includes('Alias for Local:3:I.Data.0'));assert.ok(facts.textContent.includes('External access Read/Write'));
await findButton(root,'Save signal').fire('click');assert.equal(writes[0].command.target_name,'XS_Example');
""")

    def test_candidate_and_package_page_sizes_preserve_explicit_membership(self) -> None:
        self.run_js(r"""
project.signals=[savedSignal()];project.groups=[group({member_ids:Array.from({length:61},(_,i)=>'existing-'+i),member_roles:{},signal_ids:['signal-1']})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');await choosePackage();
assert.equal(byClass(root,'field-signals-member').length,10);await edit('field-signals-members-page-size','50','change');assert.equal(byClass(root,'field-signals-member').length,50);
const check=byClass(root,'field-signals-candidate-check')[1];check.checked=true;await check.fire('change');
await edit('field-signals-detail-page-size','100','change');const request=new URL(calls.at(-1),'http://localhost');assert.equal(request.searchParams.get('detail_page_size'),'100');assert.equal(request.searchParams.get('rung_page'),'1');assert.equal(request.searchParams.get('related_page'),'1');
assert.equal(byClass(root,'field-signals-candidate-check')[1].checked,true);assert.equal(byClass(root,'field-signals-members-page-size')[0].value,'50');
await findButton(root,'Save package').fire('click');assert.equal(writes[0].command.member_ids.length,62);assert.ok(writes[0].command.member_ids.includes('rung-2'));assert.deepEqual(writes[0].command.signal_ids,['signal-1']);
""")

    def test_saved_empty_name_is_not_overwritten_by_proposal_and_candidate_type_is_editable(self) -> None:
        self.run_js(r"""
project.signals=[savedSignal({target_name:''})];rows=[sourceRow('address-1',{suggested_target_name:'IgnoredProposal'})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');assert.equal(byClass(root,'field-signals-target-name')[0].value,'');
project.signals=[];rows.push(sourceRow('address-2',{aliases:[],suggested_target_name:'Remote:10:I.Ch1Data',field_type:'unknown',suggested_field_type:'ai',candidate_field_types:['ai'],mapping_status:'review_mapping'}));
await controller.refresh();await controller.openSignal('address-2');assert.equal(byClass(root,'field-signals-target-name')[0].value,'Remote:10:I.Ch1Data');assert.equal(byClass(root,'field-signals-reviewed-type')[0].value,'ai');assert.equal(controller.hasUnsavedChanges(),false);
""")

    def test_signal_save_uses_exact_binding_revision_and_does_not_change_source(self) -> None:
        self.run_js(r"""
const original=JSON.stringify(rows),controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
await edit('field-signals-target-name','LS_DELTA');await edit('field-signals-description','English engineering description');await edit('field-signals-reviewed-type','ai','change');
assert.equal(controller.hasUnsavedChanges(),true);assert.equal(writes.length,0);
mutationHook=()=>controller.refresh();await findButton(root,'Save signal').fire('click');
assert.deepEqual(writes[0],{revision:1,command:{op:'signal',binding:binding(),target_name:'LS_DELTA',description:'English engineering description',field_type:'ai'}});
assert.equal(JSON.stringify(rows),original);assert.equal(controller.hasUnsavedChanges(),false);assert.ok(root.textContent.includes('Signal saved'));
await edit('field-signals-target-name','LS_EDITED');await findButton(root,'Save signal').fire('click');
assert.equal(writes[1].command.id,'signal-new');assert.equal('binding' in writes[1].command,false);assert.equal(writes[1].revision,2);
""")

    def test_package_preserves_existing_members_and_signals_and_requires_explicit_candidates(self) -> None:
        self.run_js(r"""
project.signals=[savedSignal(),savedSignal({id:'other-signal',target_name:'Other',binding:binding('address-2')})];project.groups=[group()];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');await choosePackage();
const checks=byClass(root,'field-signals-candidate-check');assert.equal(checks.length,2);assert.equal(checks.every(item=>!item.checked),true);
checks[1].checked=true;await checks[1].fire('change');
const include=byClass(root,'field-signals-include-signal')[0];assert.equal(include.checked,false);include.checked=true;await include.fire('change');
assert.equal(writes.length,0);await findButton(root,'Save package').fire('click');
assert.deepEqual(writes[0],{revision:1,command:{op:'group',id:'group-1',name:'Existing package',member_ids:['existing-rung','rung-2'],
 signal_ids:['other-signal','signal-1'],member_roles:{'existing-rung':'alarm','rung-2':'scaling'}}});
assert.equal(project.groups[0].migration_status,'unreviewed');assert.equal(controller.hasUnsavedChanges(),false);
""")

    def test_explicit_member_removal_does_not_delete_other_members(self) -> None:
        self.run_js(r"""
project.signals=[savedSignal()];project.groups=[group({member_ids:['existing-rung','another-rung'],signal_ids:['signal-1'],member_roles:{'existing-rung':'alarm','another-rung':'logic'}})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');await choosePackage();
const first=byClass(root,'field-signals-member')[0],check=all(first).find(item=>item.tagName==='input');check.checked=false;await check.fire('change');
await findButton(root,'Save package').fire('click');
assert.deepEqual(writes[0].command.member_ids,['another-rung']);assert.deepEqual(writes[0].command.signal_ids,['signal-1']);assert.deepEqual(writes[0].command.member_roles,{'another-rung':'logic'});
""")

    def test_duplicate_member_controls_stay_synchronized_when_a_candidate_is_removed(self) -> None:
        self.run_js(r"""
project.signals=[savedSignal()];project.groups=[group({member_ids:['rung-1'],signal_ids:['signal-1'],member_roles:{'rung-1':'reference'}})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');await choosePackage();
assert.equal(byClass(root,'field-signals-members')[0].textContent.includes('Program / Routine / rung-1'),true);
const check=byClass(root,'field-signals-candidate-check')[0];assert.equal(check.checked,true);check.checked=false;await check.fire('change');
assert.equal(byClass(root,'field-signals-members')[0].textContent.includes('Program / Routine / rung-1'),false);
assert.equal(byClass(root,'field-signals-candidate-check')[0].checked,false);await findButton(root,'Save package').fire('click');
assert.deepEqual(writes[0].command.member_ids,[]);assert.deepEqual(writes[0].command.member_roles,{});assert.deepEqual(writes[0].command.signal_ids,['signal-1']);
""")

    def test_alias_previews_remain_bounded_with_source_links_and_no_duplicate_signal_creation(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{aliases:Array.from({length:9},(_,index)=>({id:'alias-'+index,name:'Alias '+index})),aliases_total:10,aliases_truncated:true})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
const aliases=byClass(root,'field-signals-aliases')[0];assert.equal(all(aliases).filter(item=>item.tagName==='a').length,8);
assert.ok(root.textContent.includes('10 captured aliases'));assert.ok(aliases.textContent.includes('Showing 8 of 10'));
assert.equal(findLink(aliases,'Alias 0').href,'/analysis#view=objects&source=alias-0');assert.equal(findLink(aliases,'Alias 8'),undefined);
await findButton(root,'Save signal').fire('click');assert.equal(writes[0].command.binding.address_id,'address-1');assert.equal(project.signals.length,1);
""")

    def test_new_package_does_not_reuse_an_existing_identical_name(self) -> None:
        self.run_js(r"""
project.signals=[savedSignal()];project.groups=[group({name:'New package',member_ids:[],signal_ids:[],member_roles:{}})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');await choosePackage('__new');
await edit('field-signals-package-name','New package');await findButton(root,'Save package').fire('click');
assert.equal(writes[0].command.op,'group');assert.equal('id' in writes[0].command,false);
await edit('field-signals-package-name','Renamed');await findButton(root,'Save package').fire('click');assert.equal(writes[1].command.id,'group-new');
""")

    def test_own_signal_save_advances_package_revision_without_silent_external_rebase(self) -> None:
        self.run_js(r"""
project.signals=[savedSignal()];project.groups=[group()];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');await choosePackage();
await edit('field-signals-package-name','Renamed package');await edit('field-signals-target-name','New target');
mutationHook=()=>controller.refresh();await findButton(root,'Save signal').fire('click');
assert.equal(controller.hasUnsavedChanges(),true);await findButton(root,'Save package').fire('click');
assert.deepEqual(writes.map(item=>item.revision),[1,2]);assert.equal(controller.hasUnsavedChanges(),false);
""")

    def test_conflict_preserves_values_and_explicit_rebase_merges_external_memberships(self) -> None:
        self.run_js(r"""
project.signals=[savedSignal()];project.groups=[group()];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');await choosePackage();
await edit('field-signals-target-name','My unsaved name');const check=byClass(root,'field-signals-candidate-check')[1];check.checked=true;await check.fire('change');
project={...project,revision:2,signals:[savedSignal({description:'Their revised description'})],groups:[group({member_ids:['existing-rung','external-rung'],signal_ids:['other-signal','external-signal'],
 member_roles:{'existing-rung':'alarm','external-rung':'reference'}})]};
await findButton(root,'Save package').fire('click');assert.equal(writes[0].revision,1);assert.equal(controller.hasUnsavedChanges(),true);
assert.equal(byClass(root,'field-signals-target-name')[0].value,'My unsaved name');
await findButton(root,'Review latest saved version').fire('click');assert.ok(root.textContent.includes('Their revised description'));
assert.equal(writes.length,1);await findButton(root,'Use latest revision for these edits').fire('click');
assert.equal(byClass(root,'field-signals-target-name')[0].value,'My unsaved name');assert.equal(byClass(root,'field-signals-description')[0].value,'Their revised description');
await findButton(root,'Save package').fire('click');
assert.deepEqual(writes[1].command.member_ids,['existing-rung','external-rung','rung-2']);assert.deepEqual(writes[1].command.signal_ids,['other-signal','external-signal']);
assert.equal(writes[1].revision,2);assert.equal(controller.hasUnsavedChanges(),true);
""")

    def test_unsaved_drafts_survive_row_run_changes_and_stale_save_is_blocked(self) -> None:
        self.run_js(r"""
rows.push(sourceRow('address-2'));const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
await edit('field-signals-target-name','First draft');await controller.openSignal('address-2');await edit('field-signals-target-name','Second draft');
await controller.openSignal('address-1');assert.equal(byClass(root,'field-signals-target-name')[0].value,'First draft');
const staleSave=findButton(root,'Save signal');project={...project,active_run:'run-2'};await controller.refresh();
await staleSave.fire('click');assert.equal(writes.length,0);assert.ok(root.textContent.includes('Retained from another project or analysis'));assert.ok(root.textContent.includes('First draft'));
project={...project,active_run:'run-1'};await controller.refresh();await controller.openSignal('address-2');assert.equal(byClass(root,'field-signals-target-name')[0].value,'Second draft');
assert.equal(controller.hasUnsavedChanges(),true);controller.discardDrafts();assert.equal(controller.hasUnsavedChanges(),false);
""")

    def test_delayed_old_run_and_selection_responses_cannot_replace_current_details(self) -> None:
        self.run_js(r"""
rows.push(sourceRow('address-2'));const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const pending=deferred(),old=result('/api/field-signals?signal_id=address-1');
response=path=>new URL(path,'http://localhost').searchParams.get('signal_id')==='address-1'?pending.promise:Promise.resolve(result(path));
const first=controller.openSignal('address-1');await controller.openSignal('address-2');pending.resolve(old);await first;
assert.ok(byClass(root,'field-signals-detail')[0].textContent.startsWith('SecondSwitch'));
const delayed=deferred(),oldList=result('/api/field-signals');response=()=>delayed.promise;const loading=controller.refresh();
project={...project,active_run:'run-2'};response=async path=>result(path);await controller.refresh();delayed.resolve(oldList);await loading;
assert.equal(new URL(calls.at(-1),'http://localhost').searchParams.get('run_id'),'run-2');
""")

    def test_hardware_hover_focus_outside_click_and_escape_close_without_reopening(self) -> None:
        self.run_js(r"""
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();const info=byClass(root,'field-signals-hardware-info')[0];
await info.fire('pointerenter');let panel=byClass(document.body,'field-signals-hardware-popover')[0];assert.ok(panel.textContent.includes('1756-IB16'));
assert.equal(info.attributes['aria-expanded'],'true');assert.equal(panel.attributes.role,'dialog');
document.events.pointerdown({target:panel});assert.equal(byClass(document.body,'field-signals-hardware-popover').length,1);
document.events.pointerdown({target:root});assert.equal(byClass(document.body,'field-signals-hardware-popover').length,0);
info.focus();assert.equal(byClass(document.body,'field-signals-hardware-popover').length,1);
let prevented=false;document.events.keydown({key:'Escape',preventDefault(){prevented=true;}});assert.equal(prevented,true);
assert.equal(byClass(document.body,'field-signals-hardware-popover').length,0);assert.equal(info.attributes['aria-expanded'],'false');
await info.fire('click');controller.deactivate();assert.equal(byClass(document.body,'field-signals-hardware-popover').length,0);
""")

    def test_delayed_detail_keeps_its_own_revision_instead_of_newer_global_state(self) -> None:
        self.run_js(r"""
project.signals=[savedSignal()];const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const pending=deferred(),old=result('/api/field-signals?signal_id=address-1');response=()=>pending.promise;
const loading=controller.openSignal('address-1');project={...project,revision:2,signals:[savedSignal({description:'Newer saved wording'})]};
pending.resolve(old);await loading;await edit('field-signals-target-name','My target');await findButton(root,'Save signal').fire('click');
assert.equal(writes[0].revision,1);assert.equal(project.signals[0].description,'Newer saved wording');assert.equal(controller.hasUnsavedChanges(),true);
assert.ok(root.textContent.includes('Review a newer saved version'));
""")

    def test_candidate_pages_keep_selections_and_show_bounded_search_limits(self) -> None:
        self.run_js(r"""
project.signals=[savedSignal()];project.groups=[group()];
response=async path=>{const value=result(path),q=new URL(path,'http://localhost').searchParams;if(value.selected_signal){
 value.selected_signal.direct_rungs=page([rung(q.get('rung_page')==='2'?'rung-3':'rung-1')],10,{page:Number(q.get('rung_page')||1),pages:2,total:11});
 value.selected_signal.related_rungs.total_is_lower_bound=true;value.selected_signal.related_rungs.traversal={truncated:true};}return value;};
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');await choosePackage();
const check=byClass(root,'field-signals-candidate-check')[0];check.checked=true;await check.fire('change');
const direct=byClass(root,'field-signals-candidates')[0];await findButton(direct,'Next rung candidates').fire('click');
assert.equal(new URL(calls.at(-1),'http://localhost').searchParams.get('rung_page'),'2');assert.ok(root.textContent.includes('displayed total is a minimum'));
await findButton(root,'Save package').fire('click');assert.ok(writes[0].command.member_ids.includes('rung-1'));assert.equal(writes[0].command.member_ids.includes('rung-3'),false);
""")

    def test_rebind_requires_explicit_choice_and_confirmation_then_separate_mapping_review(self) -> None:
        self.run_js(r"""
project.signals=[savedSignal({active:false,needs_revalidation:true,binding:{...binding(),run_id:'old-run',snapshot_id:'old-snapshot',address_id:'old-address'}})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
const apply=findButton(root,'Reconnect retained signal to this source');assert.equal(apply.disabled,true);
await edit('field-signals-retained-choice','signal-1','change');assert.equal(apply.disabled,true);
const check=byClass(root,'field-signals-rebind-verified')[0];check.checked=true;await check.fire('change');await apply.fire('click');
assert.deepEqual(writes[0],{revision:1,command:{op:'signal_rebind',id:'signal-1',binding:binding()}});assert.equal(project.signals[0].needs_revalidation,true);
await findButton(root,'Confirm signal mapping').fire('click');assert.equal(writes[1].command.confirm,true);assert.equal(writes[1].command.id,'signal-1');assert.equal(project.signals[0].needs_revalidation,false);
""")

    def test_invalid_pages_and_network_failure_have_retry_without_writes(self) -> None:
        self.run_js(r"""
response=async path=>({...result(path),signals:page(Array.from({length:51},()=>sourceRow()))});
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();assert.ok(root.textContent.includes('page bounds'));assert.ok(findButton(root,'Retry signals'));
response=async path=>result(path);await findButton(root,'Retry signals').fire('click');
response=async()=>{throw new Error('Local service unavailable');};await controller.openSignal('address-1');
assert.ok(root.textContent.includes('Local service unavailable'));assert.ok(findButton(root,'Retry signal details'));assert.equal(writes.length,0);
""")

    def test_projection_only_changed_signature_offers_correspondence_not_invalid_confirmation(self) -> None:
        self.run_js(r"""
project.signals=[savedSignal()];
response=async path=>{const value=result(path);if(value.selected_signal){value.selected_signal.binding={...binding(),evidence_signature:'b'.repeat(64)};
 value.selected_signal.saved_signal={...project.signals[0],needs_revalidation:true};}return value;};
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
assert.equal(findButton(root,'Confirm signal mapping').disabled,true);assert.ok(root.textContent.includes('Reconnect the retained signal'));
await edit('field-signals-retained-choice','signal-1','change');const check=byClass(root,'field-signals-rebind-verified')[0];check.checked=true;await check.fire('change');
await findButton(root,'Reconnect retained signal to this source').fire('click');
assert.equal(writes[0].command.op,'signal_rebind');assert.equal(writes[0].command.binding.evidence_signature,'b'.repeat(64));
assert.equal(findButton(root,'Confirm signal mapping').disabled,false);
""")

    def test_same_run_external_rebind_cannot_be_hidden_by_conflict_rebase(self) -> None:
        self.run_js(r"""
project.signals=[savedSignal()];const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
await edit('field-signals-description','My old-source edit');project={...project,revision:2,signals:[savedSignal({binding:binding('address-2')})]};
await findButton(root,'Save signal').fire('click');await findButton(root,'Review latest saved version').fire('click');
assert.ok(root.textContent.includes('reconnected to different source evidence'));assert.equal(findButton(root,'Use latest revision for these edits'),undefined);
assert.equal(byClass(root,'field-signals-description')[0].value,'My old-source edit');assert.equal(writes.length,1);assert.equal(writes[0].revision,1);
""")

    def test_same_snapshot_rerun_allows_confirmation_without_unnecessary_rebind(self) -> None:
        self.run_js(r"""
project={...project,active_run:'run-2',signals:[savedSignal({needs_revalidation:true})]};
response=async path=>{const value=result(path);if(value.selected_signal){value.selected_signal.binding={...binding(),run_id:'run-2'};
 value.selected_signal.saved_signal={...project.signals[0]};}return value;};
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
assert.equal(byClass(root,'field-signals-correspondence').length,0);assert.equal(findButton(root,'Confirm signal mapping').disabled,false);
await findButton(root,'Confirm signal mapping').fire('click');assert.equal(writes[0].command.op,'signal');assert.equal(writes[0].command.id,'signal-1');
assert.equal(writes[0].command.confirm,true);assert.equal('binding' in writes[0].command,false);assert.equal(project.signals[0].needs_revalidation,false);
""")

    def test_package_member_labels_and_hardware_links_preserve_captured_source_ids(self) -> None:
        self.run_js(r"""
project.signals=[savedSignal()];project.groups=[group({members:[{id:'existing-rung',kind:'rung',path:'Plant program / Scaling / Rung 9'}]})];
rows=[sourceRow('address-1',{hardware:{id:'module#one',name:'Input module',controller:{id:'controller&one',name:'Controller'},catalog_number:'1756-IB16'}})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');await choosePackage();
const member=byClass(root,'field-signals-member')[0];assert.ok(member.textContent.includes('Plant program / Scaling / Rung 9'));
assert.equal(findLink(member,'Open rung source').href,'/analysis#view=ladder&source=existing-rung');
await byClass(root,'field-signals-hardware-info')[0].fire('pointerenter');const popover=byClass(document.body,'field-signals-hardware-popover')[0];
assert.equal(findLink(popover,'Open module source').href,'/analysis#view=objects&source=module%23one');
assert.equal(findLink(popover,'Open controller source').href,'/analysis#view=objects&source=controller%26one');
""")

    def test_source_note_links_encode_owner_identity_and_block_stale_project(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{source_annotations:[{id:'derived-note',owner_id:'owner #1&x=y',kind:'member_comment',text:'Text'}],source_annotations_truncated:true})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
const link=findLink(root,'Open complete source wording');assert.equal(link.href,'/analysis#view=objects&source='+encodeURIComponent('owner #1&x=y'));assert.equal(link.target,'_blank');assert.equal(link.rel,'noopener');
assert.equal(findLink(root,'Browse all source comments').href,'/analysis#view=annotations');
let prevented=false;project={...project,project_path:'other.sqlite'};link.events.click({preventDefault(){prevented=true;}});assert.equal(prevented,true);assert.equal(opened.length,0);
""")
