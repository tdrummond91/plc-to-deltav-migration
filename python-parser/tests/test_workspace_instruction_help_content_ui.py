"""Read-only instruction help uses captured arguments and independent examples."""
from __future__ import annotations

import json
import subprocess
import unittest

from test_workspace_ui import ASSETS, NODE


SCRIPTS = '\n'.join((ASSETS / name).read_text(encoding='utf-8') for name in
                    ('source-colors.js', 'rung-explanation.js', 'instruction-help-content.js'))
DOM = r"""
const assert=require('node:assert/strict');
class Element {
  constructor(tag){this.tagName=tag;this.children=[];this.attributes={};this.className='';this._text='';}
  set textContent(text){this._text=String(text);this.children=[];}
  get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
  set innerHTML(value){throw new Error('Instruction help must not use HTML injection');}
  append(...children){this.children.push(...children);}
  setAttribute(name,value){this.attributes[name]=String(value);}
  getAttribute(name){return this.attributes[name]??null;}
}
const document={createElement:tag=>new Element(tag)},window={};
const all=root=>[root,...root.children.flatMap(all)];
const cls=(root,name)=>all(root).filter(item=>(item.attributes.class||item.className).split(' ').includes(name));
const example=root=>cls(root,'instruction-help-example')[0]?.textContent||'';
const captured=root=>all(cls(root,'instruction-help-arguments')[0]).filter(item=>item.tagName==='code').map(item=>item.textContent);
"""


@unittest.skipUnless(NODE, 'Node is optional developer tooling')
class InstructionHelpContentTests(unittest.TestCase):
    def run_js(self, checks: str, data: object = None) -> None:
        code = DOM + SCRIPTS + '\nconst data=' + json.dumps(data) + ';\n' + checks
        result = subprocess.run([NODE, '-'], input=code, capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_supported_shape_has_a_named_independent_example_and_complete_arguments(self):
        arities = {**dict.fromkeys(['XIC', 'XIO', 'OTE', 'OTL', 'OTU', 'CLR', 'ONS', 'RES'], 1),
                   **dict.fromkeys(['EQU', 'NEQ', 'LES', 'LEQ', 'GRT', 'GEQ', 'MOV', 'CPT', 'ABS', 'LN', 'SQR', 'OSR', 'OSF'], 2),
                   **dict.fromkeys(['ADD', 'SUB', 'MUL', 'DIV', 'TON', 'TOF', 'RTO', 'CTU', 'CTD'], 3), 'PID': 7}
        self.run_js(r"""
for(const [opcode,arity] of Object.entries(data)){
  const instruction={opcode,arguments:Array.from({length:arity},(_,i)=>'CapturedOnly_'+i)};
  const before=JSON.stringify(instruction),root=window.PLCInstructionHelpContent.render(instruction);
  assert.equal(window.PLCInstructionHelpContent.valid(instruction),true);
  assert.ok(root.children[0].textContent.startsWith(opcode+' — '));
  assert.equal(root.children[0].textContent.includes('Unresolved'),false);
  assert.deepEqual(captured(root),instruction.arguments);assert.equal(JSON.stringify(instruction),before);
  assert.ok(root.textContent.includes(window.PLCRungExplanation.summary(instruction)));
  const worked=example(root);assert.ok(worked.includes('Invented worked example'));
  assert.ok(worked.includes('independent of your captured source'));assert.ok(worked.includes('Input / initial state:'));
  assert.ok(worked.includes('Operation:'));assert.ok(worked.includes('Result:'));
  assert.equal(worked.includes('CapturedOnly_'),false);
  assert.equal(all(root).some(item=>['button','input','textarea','select','script'].includes(item.tagName)),false);
  assert.equal(all(root).some(item=>Object.hasOwn(item.attributes,'title')),false);
}
""", arities)

    def test_comparison_and_arithmetic_examples_do_not_evaluate_captured_operands(self):
        self.run_js(r"""
const render=(opcode,args)=>window.PLCInstructionHelpContent.render({opcode,arguments:args});
const geq=render('GEQ',['PrivatePressure','PrivateLimit']);
assert.ok(example(geq).includes('90 >= 90'));assert.ok(example(geq).includes('outgoing path are TRUE'));
assert.ok(example(render('GRT',['A','B'])).includes('outgoing path are FALSE'));
assert.ok(example(render('SUB',['A','B','D'])).includes('12 - 3'));assert.ok(example(render('SUB',['A','B','D'])).includes('Write 9'));
assert.ok(example(render('CPT',['D','SECRET(A)'])).includes('(6 + 4) / 2 = 10 / 2'));
assert.equal(example(geq).includes('PrivatePressure'),false);
assert.ok(geq.textContent.includes('Numeric conversion and precision'));
""")

    def test_timers_distinguish_on_off_and_retained_state_with_execution_assumptions(self):
        self.run_js(r"""
const help=opcode=>window.PLCInstructionHelpContent.render({opcode,arguments:['CapturedTimer','1','0']});
const ton=help('TON'),tof=help('TOF'),rto=help('RTO');
for(const root of [ton,tof,rto]){
  assert.ok(example(root).includes('standard Logix TIMER'));assert.ok(example(root).includes('normal repeated execution'));
  assert.ok(example(root).includes('no pauses, resets, or other writers'));
}
assert.ok(example(ton).includes('A later FALSE execution clears ACC to 0 and DN to FALSE'));
assert.ok(example(tof).includes('prior TRUE execution'));assert.ok(example(tof).includes('DN stays TRUE during the delay and becomes FALSE'));
assert.ok(example(rto).includes('ACC remains 300 ms during FALSE'));assert.ok(example(rto).includes('another 700 ms'));
assert.ok(rto.textContent.includes('FALSE does not clear the accumulator'));
""")

    def test_edges_distinguish_scans_path_pulses_and_output_bit_pulses(self):
        self.run_js(r"""
const help=(opcode,count)=>window.PLCInstructionHelpContent.render({opcode,arguments:Array(count).fill('Captured')});
const ctu=help('CTU',3),ctd=help('CTD',3),ons=help('ONS',1),osr=help('OSR',2),osf=help('OSF',2);
for(const root of [ctu,ctd,ons,osr,osf])assert.ok(example(root).includes('Startup/prescan behavior is excluded'));
assert.ok(example(ctu).includes('ACC becomes 3'));assert.ok(example(ctu).includes('Staying TRUE on later executions adds no further count'));
assert.ok(example(ctd).includes('ACC becomes 2'));assert.ok(ctd.textContent.includes('rising transition, not a falling transition'));
assert.ok(example(ons).includes('ONS outgoing path is TRUE'));assert.ok(ons.textContent.includes('not a separate pulse-output operand'));
assert.ok(example(osr).includes('Output bit is TRUE on the first execution, then FALSE'));
assert.ok(example(osf).includes('first FALSE execution'));assert.ok(osf.textContent.includes('outgoing path conditions remain FALSE'));
""")

    def test_reset_and_pid_examples_do_not_infer_source_structure_or_control_output(self):
        self.run_js(r"""
const reset=window.PLCInstructionHelpContent.render({opcode:'RES',arguments:['UnknownStructure']});
assert.ok(example(reset).includes('invented TIMER'));assert.ok(example(reset).includes('PRE remains 1000 ms'));
assert.ok(reset.textContent.includes('not a whole-object clear'));assert.ok(reset.textContent.includes('captured target type is not inferred'));
const pid=window.PLCInstructionHelpContent.render({opcode:'PID',arguments:['Loop','PV','Tie','CV','Master','Hold','HeldValue']});
assert.ok(example(pid).includes('Conceptual example only'));assert.ok(example(pid).includes('PV = 45 and setpoint = 50'));
assert.ok(example(pid).includes('No CV value or direction is predicted'));
assert.equal(example(pid).includes('CV ='),false);
assert.ok(pid.textContent.includes('master-loop, hold, modes, scaling'));
""")

    def test_unknown_wrong_arity_and_blank_operands_have_no_worked_result_or_roles(self):
        self.run_js(r"""
for(const instruction of [{opcode:'CustomWidget',arguments:['First','Last']},{opcode:'OTE',arguments:['First','Last']},
 {opcode:'XIC',arguments:[' '.repeat(300)]},{opcode:'constructor',arguments:[]}]){
  assert.equal(window.PLCInstructionHelpContent.valid(instruction),true);
  const root=window.PLCInstructionHelpContent.render(instruction);
  assert.ok(root.children[0].textContent.includes('Unresolved'));assert.equal(example(root),'');
  assert.ok(root.textContent.includes('No worked result or input/output roles are inferred'));
  assert.deepEqual(captured(root),instruction.arguments);
}
""")

    def test_malformed_oversized_and_sparse_records_are_rejected_without_partial_help(self):
        self.run_js(r"""
for(const instruction of [null,[],{},'XIC(A)',{opcode:' ',arguments:[]},{opcode:'x'.repeat(81),arguments:[]},
 {opcode:'XIC',arguments:['x'.repeat(4097)]},{opcode:'XIC',arguments:new Array(1)},
 {opcode:'XIC',arguments:[null]},{opcode:'Custom',arguments:Array(33).fill('A')},
 {opcode:'Custom',arguments:Array(32).fill('x'.repeat(4096))}]){
  assert.equal(window.PLCInstructionHelpContent.valid(instruction),false);
  const root=window.PLCInstructionHelpContent.render(instruction);assert.equal(example(root),'');
  assert.ok(root.textContent.includes('effects remain unresolved'));assert.equal(cls(root,'instruction-help-arguments').length,0);
}
""")

    def test_colored_arguments_are_safe_exact_text_and_large_records_bound_dom_size(self):
        self.run_js(r"""
const instruction={opcode:'CPT',arguments:['<img src=x onerror=alert(1)>','A + B / 2']};
let root=window.PLCInstructionHelpContent.render(instruction);assert.deepEqual(captured(root),instruction.arguments);
assert.ok(cls(root,'source-variable').length>0);assert.ok(cls(root,'source-operator').length>0);
assert.equal(all(root).some(item=>['img','script','iframe'].includes(item.tagName)),false);
delete window.PLCSourceColors;root=window.PLCInstructionHelpContent.render(instruction);assert.deepEqual(captured(root),instruction.arguments);
const large={opcode:'Custom',arguments:Array(16).fill('+'.repeat(4000))};
assert.equal(window.PLCInstructionHelpContent.valid(large),true);root=window.PLCInstructionHelpContent.render(large);
assert.deepEqual(captured(root),large.arguments);assert.ok(all(root).length<100);
""")

    def test_stateful_reference_links_use_verified_rockwell_pages_without_source_values(self):
        self.run_js(r"""
for(const [opcode,arity] of [['TON',3],['TOF',3],['RTO',3],['CTU',3],['CTD',3],['ONS',1],['OSR',2],['OSF',2],['RES',1],['PID',7]]){
  const root=window.PLCInstructionHelpContent.render({opcode,arguments:Array(arity).fill('SourcePrivateValue')});
  const link=all(root).find(item=>item.tagName==='a');assert.ok(link);
  const url=new URL(link.href);assert.equal(url.hostname,'www.rockwellautomation.com');assert.equal(url.search,'');assert.equal(url.hash,'');
  assert.ok(url.pathname.includes('/37-00/contents-ditamap/instruction-set/'));
  assert.equal(link.href.includes('SourcePrivateValue'),false);assert.equal(link.rel,'noopener noreferrer');
}
""")


if __name__ == '__main__':
    unittest.main()
