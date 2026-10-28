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
 closest(selectors){const tags=selectors.split(',').map(value=>value.trim().toLowerCase());for(let item=this;item;item=item.parent){if(tags.includes(item.tagName.toLowerCase()))return item;}return null;}
 getBoundingClientRect(){return {left:600,top:200,bottom:230,width:380,height:220};}
 focus(){document.activeElement=this;this.events.focus?.({target:this});}
 click(){return this.fire('click');}
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
const usageEvidence=(status='referenced',changes={})=>({status,direct_count:status==='referenced'?3:0,direct_rung_count:status==='referenced'?2:0,
 roles:{read:status==='referenced'?3:0,write:0,read_write:0,unknown:0},possible_count:status==='possible_indirect'?2:0,
 possible_rung_count:status==='possible_indirect'?1:0,coverage_complete:status!=='unknown',gap_reasons:[],possible_uses:[],
 possible_preview_limit:12,possible_uses_truncated:false,notice:'Captured source references only.',...changes});
const scanEvidence=(changes={})=>({rungs_total:100,rungs_scanned:100,rungs_not_scanned:0,complete:true,available:true,gap_reasons:[],role_gap_reasons:[],...changes});
let project={project_path:'invented.sqlite',active_run:'run-1',revision:1,signals:[],groups:[]},rows=[sourceRow()],calls=[],writes=[],opened=[];
const savedSignal=(changes={})=>({id:'signal-1',binding:binding(),target_name:'LS_001',description:'Engineering words',field_type:'di',active:true,needs_revalidation:false,...changes});
const group=(changes={})=>({id:'group-1',name:'Existing package',member_ids:['existing-rung'],signal_ids:['other-signal'],member_roles:{'existing-rung':'alarm'},migration_status:'unreviewed',...changes});
function result(path){const query=new URL(path,'http://localhost').searchParams;
 const detailSize=Number(query.get('detail_page_size')||10);
 const live=rows.map(row=>({...row,saved_signal:project.signals.find(item=>item.binding.address_id===row.id&&item.binding.run_id===project.active_run)||null}));
 const row=live.find(row=>row.id===query.get('signal_id'));
 return {available:true,run_id:project.active_run,revision:project.revision,snapshot_id:'snapshot-1',presentation_mode:'original',signals:page(live,Number(query.get('page_size')||50)),coverage:{reference_scan:scanEvidence()},limitations:['No physical wiring is inferred.'],
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
    def test_compact_toolbar_groups_controls_and_preserves_page_help_action(self) -> None:
        self.run_js(r"""
let helpClicks=0;const heading=new Element('div'),help=new Element('button');heading.className='page-heading';
help.textContent='Page help';help.addEventListener('click',()=>helpClicks++);heading.append(help);
root.parentElement={querySelector:selector=>selector==='.page-heading'?heading:null};
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const toolbar=byClass(root,'field-signals-toolbar')[0],top=byClass(root,'field-signals-toolbar-top')[0];
assert.equal(toolbar.attributes['data-table-toolbar'],'');assert.equal(top.contains(heading),true);
for(const cls of ['field-signals-status','field-signals-reference-scan','field-signals-controller-tools'])assert.ok(top.contains(byClass(root,cls)[0]));
assert.equal(toolbar.contains(byClass(root,'field-signals-filters')[0]),true);await help.fire('click');assert.equal(helpClicks,1);
const chip=byClass(root,'field-signals-hide-chip')[0],checkbox=byClass(root,'field-signals-hide-empty')[0];
assert.ok(chip.children[0]===checkbox);assert.equal(chip.textContent.trim(),'Hide empty rows');assert.equal(checkbox.attributes['aria-label'],'Hide empty unreferenced rows');
assert.ok(chip.title.includes('Saved signals remain visible'));assert.equal(checkbox.checked,false);
const scan=byClass(root,'field-signals-reference-scan')[0];scan.open=true;document.events.pointerdown({target:scan.children[1]});assert.equal(scan.open,true);
document.events.pointerdown({target:root});assert.equal(scan.open,false);scan.open=true;
document.events.keydown({key:'Escape',target:scan,preventDefault(){}});assert.equal(scan.open,false);assert.equal(writes.length,0);
""")

    def test_footer_is_independent_of_split_layout_and_tracks_clearance_and_activation(self) -> None:
        self.run_js(r"""
const observed=[];let resized;window.ResizeObserver=class{constructor(callback){resized=callback;}observe(target){observed.push(target);}};
root.getClientRects=()=>[{}];root.style.setProperty=(name,value)=>{root.style[name]=value;};
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const footer=byClass(root,'field-signals-footer')[0],toolbar=byClass(root,'field-signals-toolbar')[0],layout=byClass(root,'field-signals-layout')[0];
assert.equal(layout.contains(footer),false);assert.ok(root.children.at(-1)===footer);assert.equal(footer.hidden,false);
assert.ok(observed.includes(footer)&&observed.includes(toolbar));
toolbar.getBoundingClientRect=()=>({height:86.2});footer.getBoundingClientRect=()=>({height:41.1});resized();
assert.equal(root.style['--field-signals-toolbar-height'],'87px');assert.equal(root.style['--field-signals-footer-height'],'42px');
await controller.openSignal('address-1');await edit('field-signals-target-name','Keep through footer layout');assert.equal(footer.hidden,false);
controller.deactivate();assert.equal(footer.hidden,true);await controller.refresh();assert.equal(footer.hidden,false);
assert.equal(byClass(root,'field-signals-target-name')[0].value,'Keep through footer layout');
rows=[];await controller.refresh();assert.equal(footer.hidden,false);
response=async path=>({...result(path),available:false});await controller.refresh();assert.equal(footer.hidden,false);
const waiting=deferred();response=()=>waiting.promise;const loading=controller.refresh();assert.equal(footer.hidden,false);
waiting.resolve(result('/api/field-signals'));await loading;assert.equal(controller.hasUnsavedChanges(),true);assert.equal(writes.length,0);
""")

    def test_editor_height_fits_actual_top_to_footer_and_scroll_updates_are_coalesced(self) -> None:
        self.run_js(r"""
const writesToStyle=[];let frame,frames=0,resized;
window.innerHeight=960;window.requestAnimationFrame=callback=>{frame=callback;return ++frames;};
window.ResizeObserver=class{constructor(callback){resized=callback;}observe(){}};
window.getComputedStyle=()=>({top:'221px'});root.getClientRects=()=>[{}];
root.style.setProperty=(name,value)=>{root.style[name]=value;writesToStyle.push([name,value]);};
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();frame();
const toolbar=byClass(root,'field-signals-toolbar')[0],footer=byClass(root,'field-signals-footer')[0],editor=byClass(root,'field-signals-detail')[0];
let top=251.42,toolbarBottom=213,footerHeight=37;
toolbar.getBoundingClientRect=()=>({height:103,bottom:toolbarBottom});footer.getBoundingClientRect=()=>({height:footerHeight});
editor.getBoundingClientRect=()=>({top});await controller.openSignal('address-1');frame();
assert.equal(root.style['--field-signals-editor-height'],'663px');
assert.ok(top+parseFloat(root.style['--field-signals-editor-height'])<window.innerHeight-footerHeight,'Natural top must not put editor behind footer');
top=221;const beforeFrames=frames;document.events.scroll();document.events.scroll();document.events.scroll();assert.equal(frames,beforeFrames+1);frame();
assert.equal(root.style['--field-signals-editor-height'],'694px');const beforeWrites=writesToStyle.length;resized();frame();
assert.equal(writesToStyle.length,beforeWrites,'An unchanged observation must not rewrite layout styles');
window.innerWidth=900;window.innerHeight=700;top=250;toolbarBottom=242;footerHeight=68;resized();frame();
assert.equal(root.style['--field-signals-editor-height'],'374px');assert.ok(top+374<700-footerHeight);
assert.equal(writes.length,0);
""")

    def test_row_selection_opens_editor_and_close_restores_full_width_without_losing_drafts(self) -> None:
        self.run_js(r"""
rows.push(sourceRow('address-2'));
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const layout=byClass(root,'field-signals-layout')[0],editor=byClass(root,'field-signals-detail')[0];
let entries=byClass(root,'field-signals-row');assert.equal(entries.length,2);
assert.equal(editor.hidden,true);assert.equal(layout.className,'field-signals-layout');
assert.equal(root.textContent.includes('Choose an individual signal'),false);
await entries[0].fire('click',{target:entries[0].children[2]});
assert.equal(editor.hidden,false);assert.ok(layout.className.includes('has-selection'));
assert.ok(entries[0].className.includes('is-current'));assert.equal(entries[0].attributes['aria-current'],'true');
assert.equal(byClass(root,'field-signals-open')[0].attributes['aria-expanded'],'true');
await edit('field-signals-target-name','Retained signal name');
await findButton(root,'Close').fire('click');assert.equal(editor.hidden,true);
assert.equal(layout.className,'field-signals-layout');assert.equal(entries[0].attributes['aria-current'],undefined);
assert.equal(document.activeElement,entries[0]);assert.equal(controller.hasUnsavedChanges(),true);
await entries[1].fire('click',{target:entries[1].children[4]});
assert.ok(entries[1].className.includes('is-current'));assert.equal(entries[0].className.includes('is-current'),false);
await entries[0].fire('click',{target:entries[0].children[2]});
assert.equal(byClass(root,'field-signals-target-name')[0].value,'Retained signal name');assert.equal(writes.length,0);
await controller.refresh();entries=byClass(root,'field-signals-row');assert.equal(entries[0].attributes['aria-current'],'true');
""")

    def test_row_keyboard_selection_leaves_links_and_hardware_actions_independent(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{description_origin:{kind:'channel',specific:true,owner_id:'module-root',owner_name:'Local:3:I',owner_suffix:'.Data.0'}})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const entry=byClass(root,'field-signals-row')[0],editor=byClass(root,'field-signals-detail')[0];
assert.equal(entry.attributes.tabindex,'0');let prevented=false;
await entry.fire('keydown',{key:'Enter',preventDefault(){prevented=true;}});
assert.equal(prevented,true);assert.equal(editor.hidden,false);await findButton(root,'Close').fire('click');
prevented=false;await entry.fire('keydown',{key:' ',preventDefault(){prevented=true;}});
assert.equal(prevented,true);await findButton(root,'Close').fire('click');
const before=calls.length,info=byClass(root,'field-signals-hardware-info')[0];
await entry.fire('click',{target:info.children[0]});
await entry.fire('keydown',{target:info,key:'Enter'});
const link=byClass(root,'field-signals-description-origin')[0].children[0];
await entry.fire('click',{target:link});assert.equal(calls.length,before);assert.equal(editor.hidden,true);
await info.fire('pointerenter');assert.equal(byClass(document.body,'field-signals-hardware-popover').length,1);assert.equal(editor.hidden,true);
window.getSelection=()=>({toString:()=> 'selected description'});await entry.fire('click',{target:entry.children[2]});
assert.equal(calls.length,before);assert.equal(editor.hidden,true);assert.equal(writes.length,0);
""")

    def test_closing_loading_editor_cannot_be_undone_by_late_response(self) -> None:
        self.run_js(r"""
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const waiting=deferred(),answer=result('/api/field-signals?signal_id=address-1');response=()=>waiting.promise;
const loading=controller.openSignal('address-1');assert.equal(byClass(root,'field-signals-detail')[0].hidden,false);
await findButton(root,'Close').fire('click');waiting.resolve(answer);await loading;
assert.equal(byClass(root,'field-signals-detail')[0].hidden,true);assert.equal(byClass(root,'field-signals-layout')[0].className,'field-signals-layout');
assert.equal(byClass(root,'field-signals-target-name').length,0);assert.equal(writes.length,0);
""")

    def test_stale_open_response_does_not_steal_focus_from_current_signal_edit(self) -> None:
        self.run_js(r"""
rows.push(sourceRow('address-2'));const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
for(const opener of ['row','usage','public']) {
 const waiting=deferred(),answer=result('/api/field-signals?signal_id=address-1');
 response=path=>new URL(path,'http://localhost').searchParams.get('signal_id')==='address-1'?waiting.promise:Promise.resolve(result(path));
 const first=opener==='row'?byClass(root,'field-signals-row')[0].fire('click'):
   opener==='usage'?byClass(root,'field-signals-usage-open')[0].fire('click'):controller.openSignal('address-1');
 await controller.openSignal('address-2');const name=byClass(root,'field-signals-target-name')[0];
 name.focus();await edit('field-signals-target-name','Current '+opener+' draft');
 waiting.resolve(answer);await first;
 assert.equal(document.activeElement,name,'Stale '+opener+' response stole editing focus');
 assert.equal(name.value,'Current '+opener+' draft');assert.equal(byClass(root,'field-signals-row')[1].attributes['aria-current'],'true');
 await findButton(root,'Close').fire('click');
}
assert.equal(controller.hasUnsavedChanges(),true);assert.equal(writes.length,0);
""")

    def test_escape_closes_editor_retains_draft_and_prioritizes_hardware_popup(self) -> None:
        self.run_js(r"""
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
await edit('field-signals-target-name','Keep after Escape');const editor=byClass(root,'field-signals-detail')[0];
const type=byClass(root,'field-signals-reviewed-type')[0];
document.events.keydown({key:'Escape',target:type,preventDefault(){}});assert.equal(editor.hidden,false,'Native select keeps its Escape');
const info=byClass(root,'field-signals-hardware-info')[0];await info.fire('pointerenter');
document.events.keydown({key:'Escape',target:info,preventDefault(){}});
assert.equal(byClass(document.body,'field-signals-hardware-popover').length,0);assert.equal(editor.hidden,false);
const name=byClass(root,'field-signals-target-name')[0];name.focus();let prevented=false;
document.events.keydown({key:'Escape',target:name,preventDefault(){prevented=true;}});
assert.equal(prevented,true);assert.equal(editor.hidden,true);assert.equal(controller.hasUnsavedChanges(),true);
assert.equal(document.activeElement,byClass(root,'field-signals-row')[0]);
await controller.openSignal('address-1');assert.equal(byClass(root,'field-signals-target-name')[0].value,'Keep after Escape');assert.equal(writes.length,0);
""")

    def test_failed_loading_does_not_claim_filters_have_no_matches(self) -> None:
        self.run_js(r"""
response=async path=>({...result(path),available:false,signals:page([]),notice:'Limit reached [field_io/index_bytes_limit]'});
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
assert.ok(root.textContent.includes('Limit reached [field_io/index_bytes_limit]'));
assert.ok(root.textContent.includes('This does not mean the analysis has no I/O'));
assert.equal(root.textContent.includes('No individual signals match'),false);
assert.equal(writes.length,0);
response=async path=>result(path);await controller.refresh();
assert.ok(root.textContent.includes('LevelSwitch'));
assert.equal(root.textContent.includes('The field signal list could not be loaded'),false);
""")

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
assert.ok(table.textContent.includes('Field type / channel Source alias / address Source description Logic usage DeltaV name Package status Info'));
assert.ok(table.textContent.includes('LevelSwitch'));assert.ok(table.textContent.includes('Local:3:I.Data.0'));assert.ok(table.textContent.includes('Niveau haut'));
assert.ok(table.textContent.includes('Input AI type candidate'));assert.equal(table.textContent.includes('1756-IB16'),false);assert.equal(table.textContent.includes('Local rack'),false);
assert.equal(byClass(root,'field-signals-controller').length,1);assert.ok(byClass(root,'field-signals-controller')[0].textContent.includes('Invented controller'));
assert.equal(writes.length,0);assert.equal(controller.hasUnsavedChanges(),false);
""")

    def test_logic_usage_statuses_are_separate_from_physical_mapping(self) -> None:
        self.run_js(r"""
rows=['referenced','possible_indirect','not_found','unknown'].map((status,index)=>sourceRow('address-'+(index+1),{
 field_type:'unknown',mapping_status:'review_mapping',candidate_field_types:['di'],usage:usageEvidence(status)}));
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const cells=byClass(root,'field-signals-usage-cell');assert.equal(cells.length,4);
assert.ok(cells[0].textContent.includes('Used in logic 3 exact references · 2 rungs'));
assert.ok(cells[1].textContent.startsWith('Indirect reference'));assert.ok(cells[1].textContent.includes('2 indirect references · 1 rung'));
assert.ok(cells[2].textContent.includes('No references found Within scanned source'));
assert.ok(cells[3].textContent.includes('Not checked Reference scan unavailable'));
assert.equal(byClass(root,'field-signals-table')[0].textContent.match(/Input DI type candidate/g).length,4);
assert.equal(byClass(root,'field-signals-table')[0].textContent.includes('Mapping unresolved'),false);
assert.equal(root.textContent.includes('Source references do not prove runtime activity'),false,'General instructions belong in Page help');
assert.equal(/\binactive\b|\bspare\b|\blive\b/i.test(cells.map(item=>item.textContent).join(' ')),false);
assert.equal(writes.length,0);
rows=[sourceRow('address-1',{usage:usageEvidence('referenced',{direct_count:1,direct_rung_count:1})}),
 sourceRow('address-2',{usage:usageEvidence('possible_indirect',{possible_count:1,possible_rung_count:1})})];
await controller.refresh();const singular=byClass(root,'field-signals-usage-cell');
assert.ok(singular[0].textContent.includes('1 exact reference · 1 rung'));assert.equal(singular[0].textContent.includes('1 exact references'),false);
assert.ok(singular[1].textContent.includes('1 indirect reference · 1 rung'));assert.equal(singular[1].textContent.includes('1 indirect references'),false);
await controller.openSignal('address-1');assert.ok(byClass(root,'field-signals-usage-count')[0].textContent.includes('1 exact reference · 1 rung'));
""")

    def test_missing_usage_and_blank_description_are_explicit_even_with_translation(self) -> None:
        self.run_js(r"""
let translated=0;window.PLCTranslation={renderProse(target,original){translated++;target.textContent=original;}};
rows=[sourceRow('address-1',{description:'   ',source_annotations:[],usage:undefined})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
assert.equal(byClass(root,'field-signals-wording-preview')[0].textContent,'No source description captured');
assert.ok(byClass(root,'field-signals-usage-cell')[0].textContent.includes('Not checked'));
assert.equal(byClass(root,'field-signals-usage-cell')[0].textContent.includes('No references found'),false);
await controller.openSignal('address-1');assert.ok(byClass(root,'field-signals-source')[0].textContent.includes('No source description captured'));
assert.equal(translated,0);assert.equal(writes.length,0);assert.equal(controller.hasUnsavedChanges(),false);
""")

    def test_usage_filter_is_global_resets_page_and_preserves_other_filters_and_drafts(self) -> None:
        self.run_js(r"""
response=async path=>{const answer=result(path),q=new URL(path,'http://localhost').searchParams;
 return {...answer,signals:{...answer.signals,page:Number(q.get('page')||1),pages:3,total:150}};};
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
await edit('field-signals-target-name','My usage-filter draft');await findButton(root,'Next signals').fire('click');
assert.equal(new URL(calls.at(-1),'http://localhost').searchParams.get('page'),'2');
await edit('field-signals-type','di','change');
const filter=byClass(root,'field-signals-usage-filter')[0];assert.deepEqual(filter.children.map(item=>item.value),['','referenced','possible_indirect','not_found','unknown']);
for(const value of ['referenced','possible_indirect','not_found','unknown','']){
 await edit('field-signals-usage-filter',value,'change');const q=new URL(calls.at(-1),'http://localhost').searchParams;
 assert.equal(q.get('usage'),value);assert.equal(q.get('page'),'1');assert.equal(q.get('field_type'),'di');assert.equal(q.get('run_id'),'run-1');}
await edit('field-signals-usage-filter','referenced','change');await edit('field-signals-query','Pump');
await byClass(root,'field-signals-filters')[0].fire('submit');await edit('field-signals-page-size','100','change');
const q=new URL(calls.at(-1),'http://localhost').searchParams;
assert.equal(q.get('usage'),'referenced');assert.equal(q.get('query'),'Pump');assert.equal(q.get('page_size'),'100');
assert.equal(byClass(root,'field-signals-target-name')[0].value,'My usage-filter draft');assert.equal(controller.hasUnsavedChanges(),true);assert.equal(writes.length,0);
""")

    def test_clickable_usage_opens_exact_and_possible_links_with_one_scan_summary(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{usage:usageEvidence('referenced',{coverage_complete:false,gap_reasons:['unsupported_routines','opaque_expressions','missing_logic','partial_export'],
 possible_count:2,possible_rung_count:2,possible_uses:[{id:'possible-1',rung_id:'maybe-rung',instruction_id:'maybe-inst',opcode:'COP',role:'write',variable:'Local:3:I.Data',
 path:'Program / Routine / Maybe',reason:'range_unresolved'},
 {id:'possible-2',rung_id:'index-rung',instruction_id:'index-inst',opcode:'MOV',role:'read',variable:'Local:3:I.Data[ 1 ]',reason:'equivalent_static_index'}]})})];
response=async path=>{const answer=result(path);answer.coverage.reference_scan=scanEvidence({complete:false,rungs_scanned:99,rungs_not_scanned:1,
 gap_reasons:['unsupported_routines','partial_export','opaque_expressions','unscanned_index_expressions'],role_gap_reasons:['unsupported_instructions']});
 if(answer.selected_signal)answer.selected_signal.direct_uses=page([
 {id:'use-1',rung_id:'rung-1',instruction_id:'inst/a?#',opcode:'XIC',role:'read',variable:'InputAlias',path:'Program / Routine / Exact'}],10);return answer;};
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
await byClass(root,'field-signals-usage-open')[0].fire('click');const summary=byClass(root,'field-signals-usage-summary')[0];
assert.ok(summary.textContent.includes('Exact source references'));assert.ok(summary.textContent.includes('References needing target resolution'));
const scan=byClass(root,'field-signals-reference-scan')[0];assert.equal(byClass(root,'field-signals-reference-scan').length,1);
assert.ok(scan.textContent.includes('99 / 100 rungs scanned; 1 not scanned'));assert.ok(scan.textContent.includes('source omissions'));
assert.ok(scan.textContent.includes('Some routine languages are unsupported'));assert.ok(scan.textContent.includes('Some expressions were not analyzed'));
assert.ok(scan.textContent.includes('References inside some array index expressions have not been scanned'));
assert.ok(scan.textContent.includes('Source is a partial controller export'));assert.ok(scan.textContent.includes('Instruction and name details'));
assert.ok(scan.textContent.includes('No references found applies to the scanned source.'));
assert.equal(root.textContent.split('Some routine languages are unsupported').length-1,1);
assert.equal(summary.textContent.includes('Coverage incomplete'),false);assert.equal(summary.textContent.includes('Source is a partial controller export'),false);
assert.ok(byClass(root,'field-signals-usage-cell')[0].textContent.startsWith('Used in logic'));assert.equal(byClass(root,'field-signals-usage-cell')[0].textContent.includes('incomplete'),false);
await findButton(summary,'View reference scan scope').fire('click');assert.equal(scan.open,true);assert.equal(document.activeElement,scan);
assert.ok(summary.textContent.includes('Equivalent numeric array index spelling'));
assert.ok(summary.textContent.includes('The copy or fill range has not been resolved to individual members'));assert.ok(summary.textContent.includes('Read: 3'));
assert.equal(findLink(summary,'Open instruction source').href,'/?panel=source&run_id=run-1#view=rungs&source=inst%2Fa%3F%23');
assert.ok(all(summary).some(item=>item.tagName==='a'&&item.href==='/?panel=source&run_id=run-1#view=rungs&source=maybe-inst'));
assert.ok(all(summary).some(item=>item.tagName==='a'&&item.href==='/?panel=source&run_id=run-1#view=rungs&source=maybe-rung'));
const link=findLink(summary,'Open instruction source');project={...project,active_run:'run-2'};let prevented=false;
await link.fire('click',{preventDefault(){prevented=true;}});assert.equal(prevented,true);assert.equal(writes.length,0);
""")

    def test_name_and_instruction_gaps_do_not_contaminate_reference_findings(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{usage:usageEvidence('referenced',{coverage_complete:false,gap_reasons:['unresolved_references','unsupported_instructions']})}),
 sourceRow('address-2',{usage:usageEvidence('not_found',{coverage_complete:false,gap_reasons:['unresolved_references','unsupported_instructions']})})];
response=async path=>{const answer=result(path);answer.coverage.reference_scan=scanEvidence({role_gap_reasons:['unresolved_references','unsupported_instructions']});return answer;};
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const scan=byClass(root,'field-signals-reference-scan')[0],table=byClass(root,'field-signals-table')[0];
assert.equal(scan.children[0].textContent,'Scan 100 / 100');assert.ok(scan.children[0].title.includes('100 / 100 rungs scanned · complete'));
assert.ok(scan.textContent.includes('Instruction and name details'));assert.ok(scan.textContent.includes('Some source names could not be resolved'));
assert.equal(scan.textContent.includes('Source outside the scan'),false);assert.equal(scan.textContent.includes('Some source is outside'),false);
assert.equal(table.textContent.includes('incomplete'),false);assert.equal(table.textContent.includes('Some source names'),false);
assert.ok(byClass(root,'field-signals-usage-cell')[0].textContent.startsWith('Used in logic'));
assert.ok(byClass(root,'field-signals-usage-cell')[1].textContent.startsWith('No references found'));
scan.open=true;await edit('field-signals-usage-filter','referenced','change');assert.equal(scan.open,true);
assert.equal(byClass(root,'field-signals-reference-scan').length,1);assert.equal(writes.length,0);
""")

    def test_unavailable_reference_scan_is_reported_once_and_not_as_unused(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{usage:undefined}),sourceRow('address-2',{usage:{status:'unexpected'}})];
response=async path=>{const answer=result(path);answer.coverage.reference_scan=scanEvidence({available:false,complete:false,rungs_scanned:0,rungs_not_scanned:100,gap_reasons:['protected_logic']});return answer;};
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
const scan=byClass(root,'field-signals-reference-scan')[0];assert.equal(byClass(root,'field-signals-reference-scan').length,1);
assert.ok(scan.textContent.includes('0 / 100 rungs scanned; 100 not scanned'));assert.ok(scan.textContent.includes('Some logic is protected'));
assert.equal(root.textContent.split('Reference scan unavailable. Addresses without reference evidence are shown as Not checked.').length-1,1);
assert.equal(root.textContent.split('Some logic is protected').length-1,1);
assert.ok(byClass(root,'field-signals-usage-cell').every(cell=>cell.textContent.includes('Not checked')&&!cell.textContent.includes('No references found')));
assert.equal(byClass(root,'field-signals-usage-summary')[0].textContent.includes('Some logic is protected'),false);
response=async path=>{const answer=result(path);answer.coverage={};return answer;};await controller.refresh();
assert.ok(scan.textContent.includes('Scan details unavailable'));assert.equal(scan.textContent.includes('0 / 0'),false);assert.equal(writes.length,0);
""")

    def test_unclassified_channel_types_preserve_known_input_output_direction(self) -> None:
        self.run_js(r"""
rows=['input','output','unknown'].map((direction,index)=>sourceRow('address-'+(index+1),{
 direction,field_type:'unknown',candidate_field_types:[],mapping_status:'review_mapping'}));
rows.push(sourceRow('address-4',{field_type:'ao',direction:'output'}));
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();const table=byClass(root,'field-signals-table')[0];
assert.ok(table.textContent.includes('Input Channel type not classified'));assert.ok(table.textContent.includes('Output Channel type not classified'));
assert.ok(table.textContent.includes('Unclassified Channel type not classified'));assert.ok(table.textContent.includes('AO Source-mapped'));
assert.equal(table.textContent.includes('Mapping unresolved'),false);assert.equal(writes.length,0);
""")

    def test_possible_usage_preview_is_bounded_and_never_presented_as_exact(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{usage:usageEvidence('possible_indirect',{possible_count:20,possible_rung_count:20,possible_uses_truncated:true,
 possible_uses:Array.from({length:20},(_,i)=>({id:'use-'+i,instruction_id:'inst-'+i,rung_id:'rung-'+i,opcode:'MOV',role:'read',variable:'Data[Index]',reason:'dynamic_index'}))})})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
const summary=byClass(root,'field-signals-usage-summary')[0];assert.equal(byClass(summary,'field-signals-usage-reference').length,12);
assert.ok(summary.textContent.includes('Showing 12 of 20 indirect references'));assert.ok(summary.textContent.includes('A variable index selects the member; its value is determined at runtime'));
assert.equal(summary.textContent.includes('Exact source references'),false);assert.equal(writes.length,0);
""")

    def test_resolved_parent_reference_is_used_and_shows_concrete_evidence(self) -> None:
        self.run_js(r"""
const explanation='MOV reads Local:3:I.Data, which contains the bit Local:3:I.Data.0.';
rows=[sourceRow('address-1',{usage:usageEvidence('referenced',{direct_count:0,direct_rung_count:0,resolved_count:1,resolved_rung_count:1,
 roles:{read:1,write:0,read_write:0,unknown:0},resolved_uses:[{id:'resolved-1',rung_id:'parent-rung',instruction_id:'parent/inst?',opcode:'MOV',role:'read',
 variable:'Local:3:I.Data',reason:'aggregate_parent',explanation}]})})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const cell=byClass(root,'field-signals-usage-cell')[0];assert.ok(cell.textContent.includes('Used in logic 1 resolved reference · 1 rung'));
assert.equal(cell.textContent.includes('0 exact'),false);assert.equal(cell.textContent.includes('Indirect reference'),false);
await byClass(root,'field-signals-usage-open')[0].fire('click');const summary=byClass(root,'field-signals-usage-summary')[0];
assert.ok(summary.textContent.includes('Resolved source references'));assert.ok(summary.textContent.includes(explanation));
assert.ok(summary.textContent.includes('Read: 1'));assert.equal(summary.textContent.includes('References needing target resolution'),false);
assert.equal(byClass(summary,'field-signals-reference-explanation')[0].textContent,explanation);
const link=findLink(summary,'Open instruction source');assert.equal(link.href,'/?panel=source&run_id=run-1#view=rungs&source=parent%2Finst%3F');
project={...project,active_run:'run-2'};let prevented=false;await link.fire('click',{preventDefault(){prevented=true;}});
assert.equal(prevented,true);assert.equal(writes.length,0);
""")

    def test_resolved_previews_are_bounded_and_do_not_sum_overlapping_rung_counts(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{usage:usageEvidence('referenced',{direct_count:3,direct_rung_count:2,resolved_count:20,resolved_rung_count:4,
 resolved_uses_truncated:true,roles:{read:23,write:0,read_write:0,unknown:0},
 resolved_uses:Array.from({length:20},(_,i)=>({id:'resolved-'+i,rung_id:'rung-'+i,instruction_id:'instruction-'+i,opcode:'COP',role:'read',
 variable:'Local:3:I.Data[0]',reason:'range_resolved',explanation:'COP covers this element within the captured 4-element range.'}))})})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
const summary=byClass(root,'field-signals-usage-summary')[0],count=byClass(root,'field-signals-usage-count')[0].textContent;
assert.equal(count,'3 exact references · 2 rungs; 20 resolved references · 4 rungs');assert.equal(count.includes('6 rungs'),false);
assert.equal(byClass(summary,'field-signals-usage-reference').length,12);assert.ok(summary.textContent.includes('Showing 12 of 20 resolved references'));
assert.ok(summary.textContent.includes('Read: 23'));assert.equal(summary.textContent.includes('References needing target resolution'),false);
assert.equal(writes.length,0);
""")

    def test_indirect_references_show_specific_reason_as_plain_text(self) -> None:
        self.run_js(r"""
const short='Index Selection is chosen at runtime.',explanation='MOV uses Data[Selection]; Selection is an internal DINT with a runtime value. <img src=x onerror=alert(1)>';
rows=[sourceRow('address-1',{usage:usageEvidence('possible_indirect',{detail:short,possible_count:1,possible_rung_count:1,
 possible_uses:[{id:'runtime-use',rung_id:'index-rung',instruction_id:'index-inst',opcode:'MOV',role:'read',variable:'Data[Selection]',reason:'dynamic_index',explanation}]})})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const cell=byClass(root,'field-signals-usage-cell')[0];assert.ok(cell.textContent.startsWith('Indirect reference'));
assert.equal(byClass(cell,'field-signals-usage-detail')[0].textContent,short);assert.ok(cell.textContent.includes('1 indirect reference · 1 rung'));
assert.equal(byClass(cell,'field-signals-usage-detail')[0].title,short);
assert.equal(root.textContent.includes('Possible indirect use'),false);
await controller.openSignal('address-1');const summary=byClass(root,'field-signals-usage-summary')[0];
assert.ok(summary.textContent.includes('References needing target resolution'));
const description=byClass(summary,'field-signals-reference-explanation')[0];assert.equal(description.textContent,explanation);assert.equal(description.children.length,0);
assert.equal(summary.textContent.includes('A variable index selects the member'),false);assert.equal(summary.textContent.includes('may include'),false);
assert.ok(all(summary).some(item=>item.tagName==='a'&&item.href==='/?panel=source&run_id=run-1#view=rungs&source=index-inst'));
await edit('field-signals-target-name','Preserved through resolution filter');await edit('field-signals-usage-filter','possible_indirect','change');
assert.equal(new URL(calls.at(-1),'http://localhost').searchParams.get('usage'),'possible_indirect');
assert.equal(byClass(root,'field-signals-target-name')[0].value,'Preserved through resolution filter');assert.equal(writes.length,0);
""")

    def test_index_sources_are_compact_deduplicated_and_guarded(self) -> None:
        self.run_js(r"""
const indexSource=index=>({variable:index===0?'Selection <img src=x>':'Selection'+index,instruction_id:index===1?'':'writer/'+index+'?',
 rung_id:'writer-rung-'+index,opcode:index===0?'MOV <script>':'ADD',role:index===1?'unknown':index===2?'read_write':'write',path:'Main / Routine / Rung '+index});
rows=[sourceRow('address-1',{usage:usageEvidence('possible_indirect',{detail:'Selection is written by captured logic.',possible_count:2,possible_rung_count:2,
 possible_uses:[{id:'dynamic-1',rung_id:'use-1',instruction_id:'inst-1',opcode:'MOV',role:'read',variable:'Data[Selection]',explanation:'Selection is an externally writable DINT.',
 index_sources:[0,1,2,3].map(indexSource)},
 {id:'dynamic-2',rung_id:'use-2',instruction_id:'inst-2',opcode:'MOV',role:'read',variable:'Data[Selection2]',explanation:'Selection2 is assigned in ladder logic.',
 index_sources:[0,4,5,6,7].map(indexSource)}]})})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
const sources=byClass(root,'field-signals-index-sources')[0],links=all(sources).filter(item=>item.tagName==='a');
assert.equal(byClass(root,'field-signals-index-sources').length,1);assert.equal(links.length,3);
assert.ok(sources.textContent.includes('Showing 3 of 8 index source references in these previews.'));
assert.equal(links[0].textContent,'Index Selection <img src=x> written by MOV <script> · Main / Routine / Rung 0');
assert.equal(links[0].children.length,0);assert.equal(links[0].href,'/?panel=source&run_id=run-1#view=rungs&source=writer%2F0%3F');
assert.equal(links[1].textContent,'Index Selection1 accessed by ADD · Main / Routine / Rung 1');
assert.equal(links[1].href,'/?panel=source&run_id=run-1#view=rungs&source=writer-rung-1');assert.ok(links[2].textContent.includes('written by ADD'));
project={...project,active_run:'run-2'};let prevented=false;await links[0].fire('click',{preventDefault(){prevented=true;}});assert.equal(prevented,true);
assert.equal(writes.length,0);
""")

    def test_index_source_preview_limits_are_explicit(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{usage:usageEvidence('possible_indirect',{possible_count:1,possible_rung_count:1,
 possible_uses:[{id:'dynamic-1',rung_id:'use-1',opcode:'MOV',role:'read',variable:'Data[Selection]',explanation:'Selection has additional writer references.',
 index_sources_truncated:true,index_sources:[{variable:'Selection',rung_id:'writer-rung',opcode:'ADD',role:'write',path:'Main / Routine / Rung 1'}]}]})})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
const sources=byClass(root,'field-signals-index-sources')[0];assert.ok(sources.textContent.includes('Showing 1 of 1 index source reference in these previews. Additional index sources are outside this preview.'));
assert.equal(all(sources).filter(item=>item.tagName==='a').length,1);assert.equal(writes.length,0);
""")

    def test_exact_reference_paging_retains_signal_drafts(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{usage:usageEvidence('referenced',{direct_count:11,direct_rung_count:11})})];
response=async path=>{const answer=result(path),q=new URL(path,'http://localhost').searchParams,p=Number(q.get('use_page')||1);
 if(answer.selected_signal)answer.selected_signal.direct_uses=page([{id:'u'+p,instruction_id:'i'+p,rung_id:'r'+p,opcode:'XIC',role:'read'}],10,{page:p,pages:2,total:11});return answer;};
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
await edit('field-signals-target-name','Preserved draft');await findButton(root,'Next exact references').fire('click');
assert.equal(new URL(calls.at(-1),'http://localhost').searchParams.get('use_page'),'2');
assert.equal(findLink(byClass(root,'field-signals-usage-summary')[0],'Open instruction source').href,'/?panel=source&run_id=run-1#view=rungs&source=i2');
assert.equal(byClass(root,'field-signals-target-name')[0].value,'Preserved draft');assert.equal(controller.hasUnsavedChanges(),true);assert.equal(writes.length,0);
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
assert.ok(table.textContent.includes('Input Numeric input type candidate'));assert.equal(table.textContent.includes('AI Source-mapped'),false);
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

    def test_page_size_is_in_footer_and_empty_row_filter_is_reversible_without_losing_drafts(self) -> None:
        self.run_js(r"""
response=async path=>{const answer=result(path),hidden=new URL(path,'http://localhost').searchParams.get('hide_empty')==='1';
 answer.filtering={hide_empty:hidden,total_before_hide:7,hidden_empty_count:hidden?5:0,preserved_empty_count:hidden?1:0,informative_count:1};return answer;};
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
const selector=byClass(root,'field-signals-page-size')[0],footer=byClass(root,'field-signals-footer')[0],filters=byClass(root,'field-signals-filters')[0];
assert.equal(footer.contains(selector),true);assert.equal(filters.contains(selector),false);assert.ok(footer.textContent.includes('Signals per page'));
assert.ok(footer.children.at(-1)===findButton(footer,'Download I/O audit'));
assert.equal(byClass(footer,'field-signals-footer-middle')[0].contains(byClass(root,'field-signals-filter-summary')[0]),true);
await edit('field-signals-target-name','Keep my review');const checkbox=byClass(root,'field-signals-hide-empty')[0];assert.equal(checkbox.checked,false);
checkbox.checked=true;await checkbox.fire('change');let q=new URL(calls.at(-1),'http://localhost').searchParams;
assert.equal(q.get('hide_empty'),'1');assert.equal(q.get('page'),'1');assert.ok(footer.textContent.includes('5 empty unreferenced rows hidden; 1 saved row retained'));
await edit('field-signals-page-size','100','change');q=new URL(calls.at(-1),'http://localhost').searchParams;assert.equal(q.get('hide_empty'),'1');assert.equal(q.get('page_size'),'100');
checkbox.checked=false;await checkbox.fire('change');assert.equal(new URL(calls.at(-1),'http://localhost').searchParams.get('hide_empty'),'0');
assert.equal(byClass(root,'field-signals-filter-summary')[0].hidden,true);assert.equal(byClass(root,'field-signals-target-name')[0].value,'Keep my review');assert.equal(writes.length,0);
""")

    def test_count_audit_download_is_run_bound_and_does_not_change_review(self) -> None:
        self.run_js(r"""
const exported={run_id:'run-1',revision:7,audit:{schema_version:1,inventory:{signals:7},usage:{referenced:4,not_found:3}}},blobs=[],downloads=[];
URL.createObjectURL=blob=>{blobs.push(blob);return 'blob:local-audit';};URL.revokeObjectURL=()=>{};
const originalClick=Element.prototype.click;Element.prototype.click=function(){if(this.tagName==='a'&&this.download)downloads.push({href:this.href,download:this.download});return originalClick.call(this);};
response=async path=>path.startsWith('/api/field-signals-audit?')?exported:result(path);
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
await edit('field-signals-target-name','Unsaved review');await findButton(root,'Download I/O audit').fire('click');
assert.equal(calls.at(-1),'/api/field-signals-audit?run_id=run-1');assert.deepEqual(downloads,[{href:'blob:local-audit',download:'field-io-audit.json'}]);
assert.equal(blobs[0].type,'application/json');const payload=JSON.parse(await blobs[0].text());assert.deepEqual(payload,exported.audit);
const countOnly=value=>{if(value&&typeof value==='object')Object.values(value).forEach(countOnly);else assert.ok(typeof value==='number'||typeof value==='boolean');};countOnly(payload);
assert.ok(!(await blobs[0].text()).includes('run-1'));assert.ok(!('revision' in payload));
exported.audit={schema_version:2,inventory:{signals:7},description_origins:{type_member:3,containing_member:2}};
await findButton(root,'Download I/O audit').fire('click');assert.equal(blobs.length,2);
const current=JSON.parse(await blobs[1].text());assert.deepEqual(current,exported.audit);countOnly(current);assert.ok(!('run_id' in current));
exported.audit={schema_version:3,derived_context_kinds:{result_description:4,rung_comment:2}};
await findButton(root,'Download I/O audit').fire('click');assert.equal(blobs.length,3);
const newest=JSON.parse(await blobs[2].text());assert.deepEqual(newest,exported.audit);countOnly(newest);
exported.audit={schema_version:4};await findButton(root,'Download I/O audit').fire('click');
assert.equal(blobs.length,3);assert.ok(root.textContent.includes('This I/O audit format is unavailable'));
assert.equal(byClass(root,'field-signals-target-name')[0].value,'Unsaved review');assert.equal(controller.hasUnsavedChanges(),true);assert.equal(writes.length,0);
""")

    def test_count_audit_wrong_or_changed_run_cannot_download(self) -> None:
        self.run_js(r"""
let downloads=0;URL.createObjectURL=()=>{downloads++;return 'blob:unexpected';};
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
response=async path=>path.startsWith('/api/field-signals-audit?')?{run_id:'wrong-run'}:result(path);
await findButton(root,'Download I/O audit').fire('click');assert.equal(downloads,0);assert.ok(root.textContent.includes('The audit does not match this analysis'));
const pending=deferred();response=path=>path.startsWith('/api/field-signals-audit?')?pending.promise:Promise.resolve(result(path));
const loading=findButton(root,'Download I/O audit').fire('click');project={...project,active_run:'run-2'};await controller.refresh();
pending.resolve({run_id:'run-1'});await loading;assert.equal(downloads,0);assert.equal(writes.length,0);
""")

    def test_unique_result_context_is_labeled_linked_and_keeps_original_wording(self) -> None:
        self.run_js(r"""
let callsToTranslate=[];window.PLCTranslation={renderProse(target,original,wording){callsToTranslate.push({original,wording});target.textContent=original;}};
rows=[sourceRow('address-1',{description:'Remote adapter',source_annotations:[{text:'Remote adapter'}],
 description_origin:{kind:'module',specific:false,label:'Inherited module description'},
 use_context:{description:'High level shutdown input',result_name:'HighLevelTrip',result_id:'result/tag?',rung_id:'result-rung',wording:{description:{status:'translated',text:'High level shutdown input'}}}})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const cell=byClass(root,'field-signals-source-description')[0];assert.ok(cell.textContent.includes('High level shutdown input'));assert.equal(cell.textContent.includes('Remote adapter'),false);
const link=findLink(cell,'From result HighLevelTrip');assert.ok(link);assert.equal(link.href,'/?panel=source&run_id=run-1#view=objects&source=result%2Ftag%3F');
assert.equal(callsToTranslate[0].wording.status,'translated');await controller.openSignal('address-1');
const source=byClass(root,'field-signals-source')[0];assert.ok(source.textContent.includes('Remote adapter'));assert.ok(source.textContent.includes('Inherited module description'));
assert.ok(byClass(root,'field-signals-use-context')[0].textContent.includes('From result HighLevelTrip'));
assert.equal(findLink(byClass(root,'field-signals-use-context')[0],'Open result rung').href,'/?panel=source&run_id=run-1#view=rungs&source=result-rung');
project={...project,active_run:'other-run'};let prevented=false;await link.fire('click',{preventDefault(){prevented=true;}});assert.equal(prevented,true);assert.equal(writes.length,0);
""")

    def test_specific_channel_wording_wins_and_generic_fallback_is_marked(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{description_origin:{kind:'channel',specific:true,label:'Channel comment'},use_context:{description:'Result fallback',result_name:'ResultTag',result_id:'tag-id'}}),
 sourceRow('address-2',{description:'Ethernet remote adapter',source_annotations:[{text:'Ethernet remote adapter'}],description_origin:{kind:'module',specific:false,label:'Inherited module description'}})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();const descriptions=byClass(root,'field-signals-source-description');
assert.ok(descriptions[0].textContent.includes('Niveau haut'));assert.equal(descriptions[0].textContent.includes('Result fallback'),false);
assert.ok(descriptions[1].textContent.includes('Ethernet remote adapter Inherited from module (owner name not captured)'));assert.equal(writes.length,0);
""")

    def test_rung_comment_context_links_the_rung_owner_in_cell_and_editor(self) -> None:
        self.run_js(r"""
const context={description:'Calculated status for the inlet',description_kind:'rung_comment',description_basis:'rung_comment',
 description_owner_name:'Rung 0',description_source_id:'rung #0',description_annotation_id:null,rung_id:'rung #0',rung_number:0,
 path:'Invented controller / Main / Status / Rung 0',result_id:'status-tag',result_name:'InletStatus'};
rows=[sourceRow('address-1',{description_origin:{kind:'missing',specific:false},use_context:context})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const cell=byClass(root,'field-signals-source-description')[0],link=findLink(cell,'From Rung 0 comment');
assert.ok(link);assert.equal(link.href,'/?panel=source&run_id=run-1#view=rungs&source=rung%20%230');assert.equal(link.title,context.path);
assert.ok(findLink(cell,'Result InletStatus'));assert.equal(findLink(cell,'From result InletStatus'),undefined);
await controller.openSignal('address-1');const editor=byClass(root,'field-signals-use-context')[0];
assert.equal(findLink(editor,'From Rung 0 comment').href,link.href);assert.equal(findLink(editor,'Open result rung'),undefined);
assert.ok(editor.textContent.includes(context.description));assert.equal(writes.length,0);
project={...project,active_run:'run-2'};let prevented=false;await link.fire('click',{preventDefault(){prevented=true;}});assert.equal(prevented,true);
""")

    def test_every_description_identifies_its_direct_or_inherited_owner(self) -> None:
        self.run_js(r"""
const cases=[
 {kind:'module',specific:false,owner_id:'module #1',owner_name:'RemoteAdapter',label:'Inherited from module RemoteAdapter'},
 {kind:'backing',specific:false,owner_id:'backing-tag',owner_name:'Rack:I',label:'Inherited from backing tag Rack:I'},
 {kind:'backing',basis:'backing_alias_description',specific:false,owner_id:'backing-alias',owner_name:'RackAlias',label:'Inherited from backing alias RackAlias'},
 {kind:'alias',specific:true,owner_id:'alias-id',owner_name:'HighLevel',label:'From alias HighLevel'},
 {kind:'channel',specific:true,owner_id:'input-tag',owner_name:'Rack:I',owner_suffix:'.Data.4',label:'From member Rack:I.Data.4'},
 {kind:'containing_member',specific:false,owner_id:'containing-tag',owner_name:'Rack:I',owner_suffix:'.Data',label:'Inherited from member Rack:I.Data'},
 {kind:'type_member',specific:true,owner_id:'type-id',owner_name:'InputType.Ch0Data',owner_suffix:'.Ch0Data',label:'Inherited from data type InputType.Ch0Data'},
];
rows=cases.map((origin,index)=>sourceRow('address-'+index,{description_origin:origin}));
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();const cells=byClass(root,'field-signals-source-description');
cases.forEach((origin,index)=>{const provenance=byClass(cells[index],'field-signals-description-origin');assert.equal(provenance.length,1);
 const link=findLink(provenance[0],origin.label);assert.ok(link,origin.label);
 assert.equal(link.href,'/?panel=source&run_id=run-1#view=objects&source='+encodeURIComponent(origin.owner_id));
 assert.equal(link.children.length,0);assert.equal(link.target,'_blank');});
const old=findLink(cells[0],cases[0].label);project={...project,active_run:'new-run'};let prevented=false;
await old.fire('click',{preventDefault(){prevented=true;}});assert.equal(prevented,true);assert.equal(writes.length,0);
""")

    def test_context_scope_limit_is_explained_without_hiding_captured_wording(self) -> None:
        self.run_js(r"""
const context={description:'Captured status context',description_kind:'rung_comment',description_owner_name:'Rung 2',
 description_source_id:'rung-2',rung_id:'rung-2',path:'Main / Status / Rung 2',scope_complete:false,
 notice:'Context from the single matched rung. Additional source is outside the completed scan.'};
rows=[sourceRow('address-1',{description_origin:{kind:'missing',specific:false},use_context:context}),
 sourceRow('address-2',{description_origin:{kind:'missing',specific:false},use_context:{...context,scope_complete:true}})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const cell=byClass(root,'field-signals-source-description')[0],provenance=byClass(cell,'field-signals-description-origin')[0];
assert.ok(cell.textContent.includes(context.description));assert.equal(provenance.title,context.notice);
assert.equal(findLink(provenance,'From Rung 2 comment').title,context.path);
await controller.openSignal('address-1');const panel=byClass(root,'field-signals-use-context')[0];
assert.ok(panel.textContent.includes('Context from the matched rung; additional unscanned source may contain other uses.'));
assert.ok(panel.textContent.includes(context.description));await findButton(panel,'View reference scan scope').fire('click');
assert.equal(byClass(root,'field-signals-reference-scan')[0].open,true);
await controller.openSignal('address-2');assert.equal(byClass(root,'field-signals-use-context')[0].textContent.includes('additional unscanned source'),false);
assert.equal(writes.length,0);
""")

    def test_member_suffix_uses_selected_annotation_and_missing_text_has_no_fake_owner(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{description_selection:{preferred_annotation_id:'chosen'},
 source_annotations:[{id:'wrong',text:'Wrong owner',owner_name:'Other',suffix:'.Data.9'},
 {id:'chosen',text:'Correct member comment',owner_name:'Rack:I',suffix:'.Data.4'}],
 description_origin:{kind:'channel',specific:true,annotation_id:'chosen',owner_id:'root-tag',owner_name:'Rack:I'}}),
 sourceRow('address-2',{description:'',source_annotations:[],description_origin:{kind:'missing',specific:false,owner_id:null,owner_name:null}}),
 sourceRow('address-3',{description_origin:{kind:'module',specific:false,owner_name:'<img src=x>',owner_id:null}})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();const cells=byClass(root,'field-signals-source-description');
assert.ok(findLink(cells[0],'From member Rack:I.Data.4'));assert.equal(cells[0].textContent.includes('Other'),false);
assert.equal(cells[1].textContent,'No source description captured');assert.equal(byClass(cells[1],'field-signals-description-origin').length,0);
const missingOwner=byClass(cells[2],'field-signals-description-origin')[0];assert.equal(missingOwner.textContent,'Inherited from module <img src=x>');
assert.equal(all(missingOwner).some(item=>item.tagName==='a'),false);assert.equal(all(missingOwner).some(item=>item.tagName==='img'),false);
assert.equal(writes.length,0);
""")

    def test_result_context_names_and_links_its_actual_description_owner(self) -> None:
        self.run_js(r"""
const common={description:'Ready for operation',result_name:'Status.Ready',result_id:'status-tag',
 description_basis:'declared_member_description',description_source_id:'type #1',description_annotation_id:'member #1',
 description_owner_name:'StateRecord.Ready',description_owner_suffix:'.Ready'};
rows=[sourceRow('address-1',{description_origin:{kind:'missing',specific:false},use_context:common}),
 sourceRow('address-2',{description_origin:{kind:'missing',specific:false},use_context:{...common,description_source_id:'status-tag'}}),
 sourceRow('address-3',{description_origin:{kind:'missing',specific:false},use_context:{...common,
 description_owner_name:'<img src=x>',description_owner_suffix:'.Ready'}})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();
const cells=byClass(root,'field-signals-source-description'),first=byClass(cells[0],'field-signals-description-origin')[0];
assert.ok(findLink(first,'From result Status.Ready'));
const owner=findLink(first,'Inherited from data type StateRecord.Ready');assert.ok(owner);
assert.equal(owner.href,'/?panel=source&run_id=run-1&annotation=member%20%231#view=objects&source=type%20%231');assert.equal(owner.target,'_blank');
assert.equal(findLink(first,'From result Status.Ready').href,'/?panel=source&run_id=run-1#view=objects&source=status-tag');
assert.equal(first.textContent.includes('.Ready.Ready'),false);
assert.equal(all(byClass(cells[1],'field-signals-description-origin')[0]).filter(item=>item.tagName==='a').length,1);
assert.equal(findLink(cells[1],'From result Status.Ready').href,'/?panel=source&run_id=run-1&annotation=member%20%231#view=objects&source=status-tag');
assert.ok(findLink(cells[2],'Inherited from data type <img src=x>.Ready'));assert.equal(all(cells[2]).some(item=>item.tagName==='img'),false);
project={...project,active_run:'run-2'};let prevented=false;await owner.fire('auxclick',{preventDefault(){prevented=true;}});
assert.equal(prevented,true);assert.equal(writes.length,0);
""")

    def test_result_description_is_explicitly_derived_and_footer_controls_keep_drafts(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{description_origin:{kind:'module',specific:false,owner_id:'module',owner_name:'Remote'},
 use_context:{description:'Tank high-level trip',result_name:'TankTrip',result_id:'trip-tag'}})];
response=async path=>{const answer=result(path),query=new URL(path,'http://localhost').searchParams;
 answer.signals={...answer.signals,page:Number(query.get('page')||1),pages:3,total:150};return answer;};
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
const footer=byClass(root,'field-signals-footer')[0],directory=byClass(root,'field-signals-directory')[0];
assert.ok(root.children.at(-1)===footer);assert.equal(directory.contains(footer),false);assert.equal(byClass(root,'field-signals-layout')[0].contains(footer),false);
assert.equal(footer.attributes['aria-label'],'Field I/O pagination and audit');
const provenance=byClass(byClass(root,'field-signals-source-description')[0],'field-signals-description-origin')[0];
assert.ok(provenance.textContent.includes('Derived context'));assert.ok(findLink(provenance,'From result TankTrip'));
await edit('field-signals-target-name','Keep this correction');await findButton(footer,'Next signals').fire('click');
assert.equal(new URL(calls.at(-1),'http://localhost').searchParams.get('page'),'2');assert.equal(byClass(root,'field-signals-footer')[0],footer);
assert.ok(footer.textContent.includes('page 2 of 3'));await findButton(footer,'Previous signals').fire('click');
assert.equal(new URL(calls.at(-1),'http://localhost').searchParams.get('page'),'1');
assert.equal(byClass(root,'field-signals-target-name')[0].value,'Keep this correction');assert.equal(controller.hasUnsavedChanges(),true);assert.equal(writes.length,0);
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
assert.equal(findLink(aliases,'Alias 0').href,'/?panel=source&run_id=run-1#view=objects&source=alias-0');assert.equal(findLink(aliases,'Alias 8'),undefined);
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
assert.equal(findLink(member,'Open rung source').href,'/?panel=source&run_id=run-1#view=rungs&source=existing-rung');
await byClass(root,'field-signals-hardware-info')[0].fire('pointerenter');const popover=byClass(document.body,'field-signals-hardware-popover')[0];
assert.equal(findLink(popover,'Open module source').href,'/?panel=source&run_id=run-1#view=objects&source=module%23one');
assert.equal(findLink(popover,'Open controller source').href,'/?panel=source&run_id=run-1#view=objects&source=controller%26one');
""")

    def test_source_note_links_encode_owner_identity_and_block_stale_project(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{source_annotations:[{id:'derived-note',owner_id:'owner #1&x=y',kind:'member_comment',text:'Text'}],source_annotations_truncated:true})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
const link=findLink(root,'Open complete source wording');assert.equal(link.href,'/?panel=source&run_id=run-1&annotation=derived-note#view=objects&source='+encodeURIComponent('owner #1&x=y'));assert.equal(link.target,'_blank');assert.equal(link.rel,'noopener');
assert.equal(findLink(root,'Browse all source comments').href,'/#view=objects');
let prevented=false;project={...project,project_path:'other.sqlite'};link.events.click({preventDefault(){prevented=true;}});assert.equal(prevented,true);assert.equal(opened.length,0);
""")

    def test_origin_and_candidate_links_select_exact_member_wording(self) -> None:
        self.run_js(r"""
rows=[sourceRow('address-1',{description:'Specific member wording',
 description_origin:{kind:'type_member',specific:true,annotation_id:'member &1',owner_id:'data-type',owner_name:'StateRecord.Ready'},
 description_selection:{preferred_annotation_id:'member &1',basis:'declared_member_description',status:'selected',candidate_count:1,
 candidates:[{id:'member &1',owner_id:'data-type',owner_name:'StateRecord.Ready',kind:'member_description'}]}})];
const controller=window.PLCFieldSignals.mount(root,options);await controller.refresh();await controller.openSignal('address-1');
const expected='/?panel=source&run_id=run-1&annotation=member%20%261#view=objects&source=data-type';
assert.equal(findLink(root,'Inherited from data type StateRecord.Ready').href,expected);
assert.equal(findLink(root,'Open candidate source').href,expected);assert.equal(writes.length,0);
""")
