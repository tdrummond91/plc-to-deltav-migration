"""Read-only application navigation keeps evidence dimensions and run identity explicit."""
from __future__ import annotations

import json
import subprocess
import unittest

from test_workspace_field_signals_ui import DOM
from test_workspace_ui import ASSETS, NODE


SCRIPT = (ASSETS / 'application-map.js').read_text(encoding='utf-8')
FIXTURE = r"""
const moduleRow=(id='module-1',changes={})=>({id,name:id==='module-1'?'InventedAdapter':'InventedController',controller:{id:'controller-1',name:'InventedController'},
 catalog_number:'Generic Ethernet Module',vendor:'Invented',description:'Remote adapter',parent_name:'InventedController',parent_id:'controller-1',
 attachment:{status:'qualified',parent_port_id:'2',parent_port_type:'Ethernet',parent_port_address:'192.0.2.10'},
 route:{status:'qualified',module_ids:['controller-1',id],modules:[{id:'controller-1',name:'InventedController'},{id,name:'InventedAdapter'}]},
 ports:[{Id:'1',Type:'Ethernet',Address:'192.0.2.20',Upstream:'true'}],connections:[{id:'connection-1',attributes:{Name:'Input',RPI:'20000',InputSize:'32',Path:'Invented route'}}],...changes});
const registerRow=(id='register-1',changes={})=>({id,source_id:'source-root',root_id:'source-root',module_id:'module-1',name:'Data[2]',address:'InventedAdapter:I.Data[2]',suffix:'.Data[2]',
 parent_register_id:'register-array',path:'Controller / InventedAdapter:I / Data[2]',scope:{id:'scope-1',name:'Controller'},declaration_kind:'module_input',io_direction:'input',
 member_kind:'scalar',datatype:'SINT',radix:'Decimal',external_access:'Read/Write',alias_target:null,description:'Diagnostic status byte',logic_access:{roles:['read'],uses_total:1},
 physical:{field_type:'unknown',channel:null,status:'unresolved'},states:{datatype:'declared'},provenance:{datatype:{basis:'inherited_from_array',parent_path:'.Data'}},
 description_selection:{preferred_annotation_id:'preferred-note',basis:'exact_member',status:'review_required',conflict:true},
 source_annotations:[{id:'preferred-note',kind:'member_comment',text:'Diagnostic status byte',owner_id:'source-root'},{id:'alternate-note',kind:'alias_description',text:'Remote status',owner_id:'alias-1'}],
 aliases:[{id:'alias-1',name:'RemoteStatus',alias_for:'InventedAdapter:I.Data[2]',status:'qualified'}],aliases_total:1,
 values:[{value:'0',datatype:'SINT',radix:'Decimal'}],representations:[{format:'Decorated'}],...changes});
let applicationModules=[moduleRow()],applicationRows=[registerRow()],appCalls=[],appOpened=[];
function appResult(path){const q=new URL(path,'http://localhost').searchParams,size=Number(q.get('page_size')||50);
 const selected=applicationRows.find(row=>row.id===q.get('register_id'));
 return {available:true,run_id:project.active_run,snapshot_id:'snapshot-1',modules:page(applicationModules,size),registers:page(applicationRows,size),
 selected_module:applicationModules.find(row=>row.id===q.get('module_id'))||null,
 selected_register:selected?{...selected,uses:page([{instruction_id:'instruction-1',rung_id:'rung-1',opcode:'CPT',role:'read',operand:'InventedAdapter:I.Data[2]',
 exact_instruction:'CPT(Result,InventedAdapter:I.Data[2] * 0.5)',expression:'InventedAdapter:I.Data[2] * 0.5',rung_number:7,path:'Program / Main / Rung 7'}],size)}:null,
 coverage:{declared_tags:8,registers:16,routine_languages:{RLL:2,ST:1},unresolved:{physical_mapping:16}},limitations:['Configured connections do not prove physical wiring.']};}
let appResponse=async path=>appResult(path);
const appOptions={getState:()=>project,api:async path=>{appCalls.push(path);return appResponse(path);},onSource:id=>appOpened.push({kind:'source',id}),onRung:id=>appOpened.push({kind:'rung',id})};
"""


@unittest.skipUnless(NODE, 'Node is optional developer tooling')
class ApplicationUiTests(unittest.TestCase):
    def run_js(self, checks: str) -> None:
        code = DOM + FIXTURE + SCRIPT + '\n(async()=>{\n' + checks + '\n})()'
        code += ".then(()=>process.stdout.write('APPLICATION_TEST_COMPLETE\\n'))"
        code += '.catch(error=>{console.error(error);process.exitCode=1;});'
        completed = subprocess.run([NODE, '-'], input=code, capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('APPLICATION_TEST_COMPLETE', completed.stdout)

    def test_hardware_routes_preserve_ports_connections_and_source_navigation(self) -> None:
        self.run_js(r"""
const controller=window.PLCApplicationMap.mount(root,appOptions);await controller.update(project);
assert.equal(writes.length,0);await findButton(root,'InventedAdapter').fire('click');
assert.ok(root.textContent.includes('Parent port address 192.0.2.10'));assert.ok(root.textContent.includes('InputSize 32'));
assert.ok(root.textContent.includes('Byte sizes and assembly instances do not establish a physical channel count'));
const routes=byClass(root,'application-route-node');assert.equal(routes.length,2);
await findButton(root,'Open module source').fire('click');assert.deepEqual(appOpened,[{kind:'source',id:'module-1'}]);
await routes[0].fire('click');assert.equal(new URL(appCalls.at(-1),'http://localhost').searchParams.get('module_id'),'controller-1');
assert.equal(writes.length,0);
""")

    def test_register_details_separate_raw_numeric_storage_and_physical_classification(self) -> None:
        self.run_js(r"""
const controller=window.PLCApplicationMap.mount(root,appOptions);await controller.update(project);await findButton(root,'Registers & data').fire('click');
assert.ok(byClass(root,'application-table')[0].textContent.includes('SINT scalar input read Unresolved unresolved'));
await findButton(root,'InventedAdapter:I.Data[2]').fire('click');
const detail=byClass(root,'application-register-detail')[0];
for(const label of ['Declared datatype','Declaration kind','Data direction','Logic access','Logical meaning','Physical classification','Transport','External access'])assert.ok(detail.textContent.includes(label),label);
assert.ok(detail.textContent.includes('inherited_from_array'));assert.ok(detail.textContent.includes('Conflicting source wording is preserved'));
assert.ok(detail.textContent.includes('CPT(Result,InventedAdapter:I.Data[2] * 0.5)'));
await findButton(root,'Open source').fire('click');await findButton(root,'Open rung 7').fire('click');
assert.deepEqual(appOpened,[{kind:'source',id:'source-root'},{kind:'rung',id:'rung-1'}]);
await findButton(root,'Inspect containing register / array').fire('click');assert.equal(new URL(appCalls.at(-1),'http://localhost').searchParams.get('register_id'),'register-array');
assert.equal(writes.length,0);
""")

    def test_page_sizes_and_filters_preserve_module_scope_but_reset_page(self) -> None:
        self.run_js(r"""
const controller=window.PLCApplicationMap.mount(root,appOptions);await controller.update(project);await findButton(root,'InventedAdapter').fire('click');await findButton(root,'Inspect this module’s registers').fire('click');
const size=byClass(root,'application-page-size')[0];assert.deepEqual(size.children.map(option=>option.value),['10','50','100','200','500']);
const datatype=byClass(root,'application-datatype')[0],direction=byClass(root,'application-direction')[0],role=byClass(root,'application-role')[0];
datatype.value='SINT';direction.value='input';role.value='read';size.value='200';await size.fire('change');
const request=new URL(appCalls.at(-1),'http://localhost').searchParams;
assert.equal(request.get('module_id'),'module-1');assert.equal(request.get('datatype'),'SINT');assert.equal(request.get('direction'),'input');assert.equal(request.get('logic_role'),'read');assert.equal(request.get('page'),'1');assert.equal(request.get('page_size'),'200');
await findButton(root,'Clear filters').fire('click');const cleared=new URL(appCalls.at(-1),'http://localhost').searchParams;
assert.equal(cleared.get('module_id'),'');assert.equal(cleared.get('datatype'),'');assert.equal(writes.length,0);
""")

    def test_old_run_response_and_source_buttons_cannot_escape_to_current_run(self) -> None:
        self.run_js(r"""
const controller=window.PLCApplicationMap.mount(root,appOptions);await controller.update(project);await findButton(root,'Registers & data').fire('click');await findButton(root,'InventedAdapter:I.Data[2]').fire('click');
const stale=findButton(root,'Open source'),pending=deferred();appResponse=()=>pending.promise;const refresh=controller.refresh();
project={...project,active_run:'run-2'};await stale.fire('click');assert.equal(appOpened.length,0);
appResponse=async path=>({...appResult(path),registers:page([registerRow('new-register',{address:'CurrentRunOnly'})])});await controller.update(project);
pending.resolve({ ...appResult('/api/application?run_id=run-1'),run_id:'run-1'});await refresh;
assert.ok(root.textContent.includes('CurrentRunOnly'));assert.equal(root.textContent.includes('Diagnostic status byte CPT'),false);assert.equal(appOpened.length,0);
""")

    def test_stale_or_oversized_payload_is_rejected_without_source_actions(self) -> None:
        self.run_js(r"""
appResponse=async path=>({...appResult(path),run_id:'wrong-run'});
const controller=window.PLCApplicationMap.mount(root,appOptions);await controller.update(project);assert.ok(root.textContent.includes('did not match the requested analysis'));
appResponse=async path=>({...appResult(path),registers:page(Array.from({length:51},()=>registerRow()))});await controller.refresh();
assert.ok(root.textContent.includes('page bounds'));assert.equal(byClass(root,'application-register-name').length,0);assert.equal(writes.length,0);
""")

    def test_coverage_and_unavailable_runs_keep_uncertainty_visible(self) -> None:
        self.run_js(r"""
const controller=window.PLCApplicationMap.mount(root,appOptions);await controller.update(project);await findButton(root,'Coverage').fire('click');
assert.ok(root.textContent.includes('RLL 2 ST 1'));assert.ok(root.textContent.includes('physical mapping 16'));
assert.ok(root.textContent.includes('Configured connections do not prove physical wiring.'));
appResponse=async()=>({available:false,run_id:'run-1',notice:'Snapshot missing'});await controller.refresh();assert.ok(root.textContent.includes('Snapshot missing'));
controller.destroy();assert.equal(root.children.length,0);assert.equal(writes.length,0);
""")

    def test_capacity_failure_is_visible_as_a_display_error_not_empty_source(self) -> None:
        self.run_js(r"""
appResponse=async()=>({available:false,run_id:'run-1',reason:'application_capacity',notice:'The saved analysis is still present. Re-running unchanged analysis will not resolve this display limit.'});
const controller=window.PLCApplicationMap.mount(root,appOptions);await controller.update(project);
assert.ok(root.textContent.includes('Application map display limit'));assert.ok(root.textContent.includes('saved analysis is still present'));
assert.ok(byClass(root,'application-status')[0].className.includes('is-error'));
assert.equal(root.textContent.includes('No records match'),false);assert.equal(writes.length,0);
""")

    def test_source_wording_is_literal_and_description_candidates_are_retained(self) -> None:
        self.run_js(r"""
applicationRows=[registerRow('register-1',{description:'<img src=x onerror=alert(1)>',source_annotations:[{id:'note',text:'<script>bad()</script>',owner_id:'source-root'}]})];
const controller=window.PLCApplicationMap.mount(root,appOptions);await controller.update(project);await findButton(root,'Registers & data').fire('click');await findButton(root,'InventedAdapter:I.Data[2]').fire('click');
assert.ok(root.textContent.includes('<script>bad()</script>'));assert.equal(all(root).some(node=>node.tagName==='script'||node.tagName==='img'),false);assert.equal(writes.length,0);
""")

    def test_reactivation_reloads_after_inflight_page_was_discarded(self) -> None:
        self.run_js(r"""
const controller=window.PLCApplicationMap.mount(root,appOptions);await controller.update(project);const pending=deferred();appResponse=()=>pending.promise;const abandoned=controller.refresh();controller.deactivate();
appResponse=async path=>({...appResult(path),modules:page([moduleRow('updated',{name:'Updated adapter'})])});await controller.update(project);
pending.resolve(appResult('/api/application'));await abandoned;assert.ok(root.textContent.includes('Updated adapter'));assert.equal(byClass(root,'application-module-name').length,1);
""")

    def test_real_backend_projection_keeps_type_origin_and_cpt_links_visible(self) -> None:
        from plc_workbench.workspace_application import ApplicationIndex
        from test_workspace_field_io import build

        index = ApplicationIndex(build())
        target = next(row for row in index.registers.values() if row['address'] == 'InternalReal')
        payload = index.view({'run_id': 'run-1', 'register_id': target['id']})
        payload['run_id'] = 'run-1'
        self.run_js('appResponse=async()=>(' + json.dumps(payload) + ');\n' + r"""
const controller=window.PLCApplicationMap.mount(root,appOptions);await controller.update(project);await findButton(root,'Registers & data').fire('click');
const detail=byClass(root,'application-register-detail')[0];assert.ok(detail);assert.ok(detail.textContent.includes('Declared datatype REAL Evidence: extracted'));
assert.ok(detail.textContent.includes('source ids'));assert.ok(detail.textContent.includes('Calculation destination InternalReal'));
assert.ok(detail.textContent.includes('Local:3:I.Ch0Data+1'));assert.ok(detail.textContent.includes('Declaration attributes'));
const rung=byClass(root,'application-uses')[0].children.flatMap(all).find(node=>node.tagName==='button'&&node.textContent.startsWith('Open rung'));
await rung.fire('click');assert.equal(appOpened[0].kind,'rung');assert.ok(appOpened[0].id.startsWith('rung_'));assert.equal(writes.length,0);
""")

    def test_conflicting_metadata_and_unknown_transport_remain_explicit(self) -> None:
        self.run_js(r"""
applicationRows=[registerRow('register-1',{datatype:null,declared_datatype:'SINT',metadata_conflicts:{datatype:{declared:'SINT',captured:['INT'],declaration_source_id:'source-root'}},
 transport:{status:'unknown',basis:'configured_relationship_only'},logical_meaning:{status:'unknown',basis:'not_decoded'},
 attributes:{TagType:'Consumed'},communications:[{attributes:{Producer:'InventedProducer',RemoteTag:'InventedRemote',RPI:'20'}}],
 datatype_definition:{name:'InventedUDT',source_id:'datatype-1',members:[{name:'Status',attributes:{DataType:'SINT'},status:'extracted'}]}})];
const controller=window.PLCApplicationMap.mount(root,appOptions);await controller.update(project);await findButton(root,'Registers & data').fire('click');await findButton(root,'InventedAdapter:I.Data[2]').fire('click');
assert.ok(root.textContent.includes('Source metadata conflict'));assert.ok(root.textContent.includes('Conflicting source metadata'));
assert.ok(root.textContent.includes('Declared datatype SINT Evidence: source conflict'));assert.ok(root.textContent.includes('Transport Unresolved Evidence: unknown'));
assert.ok(root.textContent.includes('InventedProducer'));assert.ok(root.textContent.includes('Datatype definition · InventedUDT'));
assert.equal(root.textContent.includes('[object Object]'),false);assert.equal(writes.length,0);
""")


if __name__ == '__main__':
    unittest.main()
