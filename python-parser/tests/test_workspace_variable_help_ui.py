"""Variable evidence distinguishes captured alternatives, meaning and write sites."""
from __future__ import annotations

import subprocess
import unittest

from test_workspace_instruction_help_ui import DOM
from test_workspace_ui import ASSETS, NODE

SCRIPT = (ASSETS / 'variable-help-content.js').read_text(encoding='utf-8')


@unittest.skipUnless(NODE, 'Node is optional developer tooling')
class VariableHelpContentTests(unittest.TestCase):
    def run_js(self, checks: str) -> None:
        result = subprocess.run([NODE, '-'], input=DOM + SCRIPT + checks,
                                capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_meaning_scope_value_alternatives_and_historical_writer_links(self) -> None:
        self.run_js(r"""
const data={...variableData(),historical:true,
 declaration:{name:'Delay',path:'Controller / Program / Delay',scope_path:'Controller / Program',datatype:'TIMER',description:'Invented delay'},
 member:{path:'.PRE',datatype:'DINT',units:'ms',meaning:'Verified preset',type_basis:'Verified TIMER declaration'},
 captured_values:[{envelope:'Data',format:'decorated',path:'.PRE',datatype:'DINT',value:'2500',value_present:true,status:'captured'},
 {envelope:'DefaultData',format:'decorated',path:'.PRE',value:'1000',value_present:true,status:'captured',ambiguous:true}],
 captured_values_total:2,writers:[{instruction_id:'inst:writer',rung_id:'rung:old',path:'OldProgram / Routine / Rung 3',opcode:'MOV',role:'write',relation:'exact_address',instruction_text:'MOV(Setting,Delay.PRE)'}],writers_total:1,
 representations:[{envelope:'Data',format:'l5k',status:'opaque'}]};
const original=JSON.stringify(data),root=window.PLCVariableHelpContent.render(data);
for(const expected of ['Controller / Program','TIMER','Verified preset','ms','2500','1000','DefaultData · captured default alternative','Data · captured export value','Ambiguous evidence','do not establish the live value','Missing data']){
 if(expected!=='Missing data')assert.ok(root.textContent.includes(expected),expected);
}
assert.ok(root.textContent.includes('l5k'));assert.ok(root.textContent.includes('does not interpret it or select an effective value'));
const link=all(root).find(n=>n.tagName==='a'),url=new URL(link.href);
assert.equal(url.pathname,'/instruction-help.html');assert.equal(url.searchParams.get('id'),'inst:writer');assert.equal(url.searchParams.get('run_id'),'run:one');assert.equal(link.target,'_blank');assert.equal(link.rel,'noopener');
assert.equal(JSON.stringify(data),original);assert.equal(all(root).some(n=>['input','textarea','select'].includes(n.tagName)),false);
""")

    def test_unknown_pre_member_and_missing_values_do_not_infer_timer_or_zero(self) -> None:
        self.run_js(r"""
const root=window.PLCVariableHelpContent.render({...variableData('Custom.PRE'),available:false,member:null,declaration:{name:'Custom',datatype:'UserType'},binding:null,notice:'Member meaning unresolved'});
assert.ok(root.textContent.includes('suffix alone does not establish'));assert.ok(root.textContent.includes('Missing data does not mean zero'));
assert.ok(root.textContent.includes('does not prove that the address is never changed'));
assert.equal(root.textContent.includes('preset'),false);assert.equal(root.textContent.includes('ms'),false);
""")

    def test_hostile_text_never_becomes_markup_or_untrusted_writer_url(self) -> None:
        self.run_js(r"""
Object.defineProperty(Element.prototype,'innerHTML',{set(){throw Error('No HTML injection');}});
const hostile='<img src=x onerror=alert(1)>',root=window.PLCVariableHelpContent.render({...variableData(hostile),member:{meaning:hostile},declaration:{name:hostile,description:hostile},
captured_values:[{value:hostile,value_present:true,envelope:'Data'}],writers:[{instruction_id:'javascript:alert(1)',instruction_text:hostile,path:hostile}],limitations:[hostile]});
assert.ok(root.textContent.includes(hostile));assert.equal(all(root).some(n=>n.tagName==='img'||n.tagName==='script'),false);
const link=all(root).find(n=>n.tagName==='a');assert.equal(new URL(link.href).origin,window.location.origin);assert.equal(new URL(link.href).pathname,'/instruction-help.html');
""")

    def test_value_presence_is_explicit_and_truncation_counts_are_visible(self) -> None:
        self.run_js(r"""
const root=window.PLCVariableHelpContent.render({...variableData(),captured_values:[{envelope:'Data',value_present:false,value:'0'}],captured_values_total:9,captured_values_truncated:true,
 writers:[],writers_total:5,writers_truncated:true,representations:[{envelope:'Data',format:'raw',status:'opaque'}],representations_total:3,representations_truncated:true});
assert.ok(root.textContent.includes('Value not captured'));assert.ok(root.textContent.includes('Showing 1 of 9 captured value entries'));
assert.ok(root.textContent.includes('Showing 0 of 5 write sites'));assert.ok(root.textContent.includes('Showing 1 of 3 representations'));
""")

    def test_individual_truncated_values_and_writer_text_are_identified(self) -> None:
        self.run_js(r"""
const root=window.PLCVariableHelpContent.render({...variableData(),declaration:{description:'Short',description_truncated:true},
captured_values:[{envelope:'Data',value_present:true,value:'123…',value_truncated:true}],
writers:[{instruction_id:'inst:writer',instruction_text:'MOV(Lo…',instruction_text_truncated:true}]});
assert.ok(root.textContent.includes('not the complete captured entry'));assert.ok(root.textContent.includes('write-site preview is shortened'));
assert.ok(root.textContent.includes('description or path is shortened'));
""")

    def test_whole_structure_and_overlap_writes_do_not_claim_member_assignment(self) -> None:
        self.run_js(r"""
const root=window.PLCVariableHelpContent.render({...variableData(),writers:[
{instruction_id:'inst:timer',relation:'whole_control',role:'read_write',instruction_text:'TON(Delay,?,?)'},
{instruction_id:'inst:copy',relation:'possible_overlap',role:'write',instruction_text:'COP(Source,Delay,1)'}]});
assert.ok(root.textContent.includes("this member's effect is not established"));assert.ok(root.textContent.includes('exact member effect unresolved'));
""")

    def test_scope_and_type_evidence_use_readable_labels(self) -> None:
        self.run_js(r"""
for(const[kind,label]of[['controller','Controller-wide / global'],['program','Program'],['aoi','AOI']]){
 const root=window.PLCVariableHelpContent.render({...variableData(),declaration:{scope_kind:kind,scope_path:'Invented / Scope'},member:{type_basis:'root_declaration'}});
 assert.ok(root.textContent.includes(label+' · Invented / Scope'));assert.ok(root.textContent.includes('Scoped tag found'));
 assert.ok(root.textContent.includes('Type evidence: declared tag type'));assert.equal(root.textContent.includes('root_declaration'),false);
}
const root=window.PLCVariableHelpContent.render({...variableData(),member:{type_basis:'captured_decorated_structure'}});
assert.ok(root.textContent.includes('Type evidence: structure type in saved data'));assert.equal(root.textContent.includes('captured_decorated_structure'),false);
""")

    def test_member_reference_only_allows_official_https_domain(self) -> None:
        self.run_js(r"""
for(const reference of ['https://www.rockwellautomation.com/en-us/docs/example.html','https://rockwellautomation.com/en-us/docs/example.html']){
 const root=window.PLCVariableHelpContent.render({...variableData(),member:{reference}}),link=all(root).find(n=>n.textContent==='Member reference');
 assert.ok(link);assert.equal(link.href,reference);assert.equal(link.rel,'noopener noreferrer');
}
for(const reference of ['javascript:alert(1)','http://www.rockwellautomation.com/test','https://rockwellautomation.com.evil.invalid/test',
 'https://www.rockwellautomation.com@evil.invalid/test','https://user@www.rockwellautomation.com/test','https://www.rockwellautomation.com:444/test','not-a-url']){
 const root=window.PLCVariableHelpContent.render({...variableData(),member:{reference}});assert.equal(all(root).some(n=>n.textContent==='Member reference'),false);
}
""")
