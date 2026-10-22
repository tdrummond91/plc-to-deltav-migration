"""Plain-language source rules preserve path scope and unresolved effects."""
from __future__ import annotations

from dataclasses import asdict
import json
import subprocess
import unittest

from test_calculations import capture
from test_workspace_ui import ASSETS, DOM, NODE


SCRIPT = (ASSETS / 'rung-explanation.js').read_text(encoding='utf-8')
EXPLANATION_DOM = r"""
document.createElement=tag=>node(tag);
const all=root=>[root,...descendants(root)];
const css=(root,name)=>all(root).filter(n=>n.className.split(' ').includes(name));
const render=(data,options={})=>window.PLCRungExplanation.render(data.source,
  {sourceQualified:true,operands:data.operands,calculations:data.calculations,...options});
"""


def source(text: str) -> dict:
    _, inventory, references, calculations = capture(text=text)
    return {'source': asdict(inventory.rungs[0]), 'operands': references.operands,
            'calculations': calculations.to_dict()}


@unittest.skipUnless(NODE, 'Node is optional developer tooling')
class WorkspaceRungExplanationTests(unittest.TestCase):
    def run_js(self, checks: str, payload: object) -> None:
        code = DOM + EXPLANATION_DOM + SCRIPT + '\nconst data=' + json.dumps(payload) + ';\n' + checks
        result = subprocess.run([NODE, '-'], input=code, capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_alarm_like_comparison_names_inputs_condition_and_output_without_equipment_inference(self):
        self.run_js(r"""
const root=render(data),inputs=css(root,'rung-explanation-inputs')[0],outputs=css(root,'rung-explanation-outputs')[0];
assert.ok(contents(inputs).includes('Pressure'));
assert.ok(contents(inputs).includes('90'));
assert.ok(contents(root).includes('Pressure is greater than 90'));
assert.ok(contents(outputs).includes('Warning'));
assert.ok(contents(outputs).includes('TRUE when the rung-entry condition is TRUE AND (Pressure is greater than 90); FALSE otherwise'));
assert.ok(contents(outputs).includes('when this instruction is evaluated'));
assert.equal(contents(outputs).includes('shutdown'),false);
assert.equal(contents(outputs).includes('priority'),false);
assert.equal(/[¬∧∨]/u.test(contents(root)),false);
assert.equal(css(root,'rung-explanation-step').length,2);
""", source('GRT(Pressure,90)OTE(Warning);'))

    def test_nested_condition_branches_keep_parentheses_and_path_scope(self):
        self.run_js(r"""
const root=render(data),outputs=css(root,'rung-explanation-outputs')[0];
assert.equal(css(root,'rung-explanation-branch').length,2);
assert.equal(css(root,'rung-explanation-path').length,4);
assert.ok(contents(root).includes('Inhibit is FALSE'));
assert.ok(contents(root).includes('Main path / Path 2 / Path 2'));
assert.ok(contents(outputs).includes('AND'));
assert.ok(contents(outputs).includes('OR'));
assert.ok(contents(outputs).includes('((Enable is TRUE) AND (A is TRUE)) OR'));
assert.ok(contents(outputs).includes('TRUE when the rung-entry condition is TRUE AND ('));
""", source('XIC(Enable)[XIC(A),XIO(Inhibit)[XIC(B),XIC(C)]]OTE(Output);'))

    def test_parallel_actions_do_not_become_one_expression_and_each_output_keeps_its_path(self):
        self.run_js(r"""
const root=render(data),outputs=css(root,'rung-explanation-outputs')[0];
const rows=all(outputs).filter(n=>n.tagName==='tr').slice(1);
assert.equal(rows.length,3);
assert.ok(contents(rows[0]).includes('Left'));
assert.ok(contents(rows[0]).includes('Main path / Path 1'));
assert.ok(contents(rows[0]).includes('A is TRUE'));
assert.equal(contents(rows[0]).includes('B is TRUE'),false);
assert.ok(contents(rows[1]).includes('Right'));
assert.ok(contents(rows[1]).includes('Main path / Path 2'));
assert.ok(contents(rows[1]).includes('B is TRUE'));
assert.ok(contents(rows[2]).includes('Tail'));
assert.equal(contents(rows[2]).includes('TRUE when the rung-entry condition is TRUE AND ('),false);
assert.ok(contents(root).includes('A single Boolean expression would omit their effects'));
""", source('[XIC(A)OTE(Left),XIC(B)OTE(Right)]OTE(Tail);'))

    def test_empty_bypass_is_not_removed_from_condition_summary(self):
        self.run_js(r"""
const root=render(data),outputs=css(root,'rung-explanation-outputs')[0];
assert.ok(contents(root).includes('Empty path: passes the incoming condition through unchanged'));
assert.equal(contents(outputs).includes('TRUE when the rung-entry condition is TRUE AND (A is TRUE)'),false);
assert.ok(contents(outputs).includes('incoming path result: TRUE or FALSE'));
""", source('[XIC(A),]OTE(Output);'))

    def test_latches_timers_and_pid_keep_state_and_unresolved_semantics_explicit(self):
        self.run_js(r"""
const roots=data.map(item=>render(item));
assert.ok(contents(roots[0]).includes('When this path is FALSE, this instruction leaves the stored bit unchanged'));
assert.ok(contents(roots[1]).includes('On-delay timer uses stored state Timer'));
assert.ok(contents(roots[1]).includes('Timing, count changes, and downstream member values are not evaluated'));
const timerOutput=css(roots[1],'rung-explanation-outputs')[0];
assert.equal(contents(timerOutput).includes('TRUE when the rung-entry condition is TRUE AND (Timer.DN is TRUE)'),false);
assert.ok(contents(roots[2]).includes('PID instruction is present with seven captured parameters'));
assert.ok(contents(roots[2]).includes('No explicit outputs are identified'));
assert.equal(css(roots[2],'rung-explanation-state').length,1);
""", [source('XIC(A)OTL(Latched);'), source('TON(Timer,100,0)XIC(Timer.DN)OTE(Output);'),
       source('PID(Loop,PV,Tieback,CV,InHold,HoldValue,Master);')])

    def test_opaque_or_wrong_arity_blocks_cannot_invent_input_output_roles(self):
        self.run_js(r"""
for(const item of data) {
  const root=render(item);
  assert.equal(css(root,'rung-explanation-unknown').length,1);
  assert.ok(contents(root).includes('No explicit inputs are identified'));
  assert.ok(contents(root).includes('No explicit outputs are identified'));
  assert.ok(contents(root).includes('Keep its arguments and source position'));
}
""", [source('CustomValve(First,Last);'), source('OTE(First,Last);')])

    def test_calculation_summary_uses_original_expression_and_explains_unavailable_syntax(self):
        self.run_js(r"""
const root=render(data),outputs=css(root,'rung-explanation-outputs')[0];
assert.ok(contents(outputs).includes('D'));
assert.ok(contents(root).includes('evaluate the captured expression ((A+B)/C)'));
assert.ok(contents(root).includes('Saved expression syntax is parsed'));
const absent=render(data,{calculations:{}});
assert.ok(contents(absent).includes('Expression syntax is unavailable or unsupported'));
""", source('CPT(D,(A+B)/C);'))

    def test_unqualified_incomplete_and_large_source_fall_back_without_partial_claims(self):
        self.run_js(r"""
const variants=[()=>render(data,{sourceQualified:false}),()=>render(data,{sourceQualified:undefined})];
const missing=structuredClone(data);missing.source.structure.items.pop();variants.push(()=>render(missing));
const repeated=structuredClone(data);repeated.source.structure.items.push(repeated.source.structure.items[0]);variants.push(()=>render(repeated));
const deep=structuredClone(data);for(let i=0;i<55;i++)deep.source.structure={kind:'sequence',items:[deep.source.structure]};variants.push(()=>render(deep));
const huge=structuredClone(data);huge.source.instructions=Array.from({length:181},(_,i)=>({...data.source.instructions[0],id:'new-'+i}));variants.push(()=>render(huge));
for(const variant of variants) {
  const root=variant();assert.equal(css(root,'rung-explanation-fallback').length,1);
  assert.equal(css(root,'rung-explanation-step').length,0);
  assert.ok(contents(root).includes(data.source.text));
  assert.equal(all(root).filter(n=>n.tagName==='details')[0].open,true);
}
""", source('XIC(A)OTE(B);'))

    def test_source_text_is_safe_text_and_duplicate_binding_is_not_claimed_linked(self):
        self.run_js(r"""
const original=data.operands.find(item=>item.instruction_id===data.source.instructions[0].id);
data.operands.push({...original});
const root=render(data);
assert.ok(contents(css(root,'rung-explanation-inputs')[0]).includes('reference binding unavailable'));
data.source.instructions[0].arguments[0]='<img src=x onerror=alert(1)>';
const unsafe=render(data);
assert.ok(contents(unsafe).includes('<img src=x onerror=alert(1)>'));
assert.equal(all(unsafe).some(item=>item.tagName==='img'),false);
""", source('XIC(A)OTE(B);'))

    def test_pure_instruction_summaries_name_comparison_calculation_and_boolean_effects(self):
        self.run_js(r"""
document.createElement=()=>{throw new Error('A summary must not need DOM construction');};
const summaries=data.map(instruction=>window.PLCRungExplanation.summary(instruction));
assert.ok(summaries[0].includes('GEQ'));assert.ok(summaries[0].includes('Pressure is greater than or equal to 90'));
assert.ok(summaries[0].includes('Inputs / values: Pressure, 90'));
assert.ok(summaries[1].includes('ValveClosed is FALSE'));
assert.ok(summaries[2].includes('Warning follows this instruction\'s incoming path result: TRUE or FALSE'));
assert.ok(summaries[2].includes('Outputs / stored state: Warning'));
assert.equal(summaries[2].includes('shutdown'),false);
assert.ok(summaries[3].includes('subtract Offset from Input'));assert.ok(summaries[3].includes('write the result to Output'));
assert.ok(summaries[4].includes('evaluate the captured expression ((A+B)/C)'));
summaries.forEach(text=>assert.ok(text.length<=1200));
""", [{'opcode': 'GEQ', 'arguments': ['Pressure', '90']},
       {'opcode': 'XIO', 'arguments': ['ValveClosed']},
       {'opcode': 'OTE', 'arguments': ['Warning']},
       {'opcode': 'SUB', 'arguments': ['Input', 'Offset', 'Output']},
       {'opcode': 'CPT', 'arguments': ['Result', '(A+B)/C']}])

    def test_instruction_summaries_keep_stateful_and_unknown_effects_explicit(self):
        self.run_js(r"""
const summary=window.PLCRungExplanation.summary;
const latch=summary({opcode:'OTL',arguments:['Hold']});
assert.ok(latch.includes('leaves the stored bit unchanged'));
const timer=summary({opcode:'TON',arguments:['Timer','100','0']});
assert.ok(timer.includes('uses stored state Timer'));assert.ok(timer.includes('execution history'));
assert.ok(timer.includes('not evaluated here'));
const pid=summary({opcode:'PID',arguments:['Loop','PV','Tieback','CV','InHold','HoldValue','Master']});
assert.ok(pid.includes('require separate review'));assert.equal(pid.includes('Outputs / stored state:'),false);
for(const instruction of [{opcode:'Custom_Block',arguments:['First','Last']},{opcode:'OTE',arguments:['First','Last']}]){
  const text=summary(instruction);assert.ok(text.includes('Unknown instruction effects'));
  assert.ok(text.includes('No input/output roles are inferred'));
  assert.equal(text.includes('Inputs / values:'),false);assert.equal(text.includes('Outputs / stored state:'),false);
}
""", None)

    def test_instruction_summary_rejects_malformed_records_and_bounds_previews_without_mutation(self):
        self.run_js(r"""
const summary=window.PLCRungExplanation.summary;
for(const instruction of [null,{},'XIC(A)',{opcode:' ',arguments:[]},{opcode:'x'.repeat(81),arguments:[]},
 {opcode:'XIC',arguments:'A'},{opcode:'XIC',arguments:[null]},{opcode:'XIC',arguments:new Array(1)},
 {opcode:'XIC',arguments:['x'.repeat(4097)]},{opcode:'XIC',arguments:Array(33).fill('A')},
 {opcode:'Custom',arguments:Array(32).fill('x'.repeat(4096))}]){
  const text=summary(instruction);assert.ok(text.includes('Instruction details unavailable'));assert.ok(text.length<200);
}
const instruction={opcode:'CPT',arguments:['Output','x'.repeat(4096)],id:'synthetic'};
const before=JSON.stringify(instruction),text=summary(instruction);
assert.equal(JSON.stringify(instruction),before);assert.ok(text.length<=1200);
assert.ok(text.includes('Argument previews shortened'));assert.ok(text.includes('...'));
assert.equal(summary({opcode:'XIC',arguments:['<script>literal source</script>']}).includes('<script>literal source</script>'),true);
""", None)

    def test_summary_shortening_does_not_turn_blank_operands_into_known_effects(self):
        self.run_js(r"""
const summary=window.PLCRungExplanation.summary;
for(const opcode of ['XIC','OTE']){
  for(const argument of [' '.repeat(121),' \t\n'.repeat(300)]){
    const instruction={opcode,arguments:[argument]},before=JSON.stringify(instruction);
    const text=summary(instruction);
    assert.ok(text.includes('Unknown instruction effects'));
    assert.ok(text.includes('No input/output roles are inferred'));
    assert.equal(text.includes('Inputs / values:'),false);
    assert.equal(text.includes('Outputs / stored state:'),false);
    assert.equal(JSON.stringify(instruction),before);
  }
}
""", None)


if __name__ == '__main__':
    unittest.main()
