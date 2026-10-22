"""Verify equation presentation against invented, actually parsed L5X evidence."""
from __future__ import annotations

from dataclasses import asdict
import json
import subprocess
import unittest

from test_calculations import capture
from test_workspace_ui import DOM, NODE, function
from test_workspace_rung_flow_ui import FLOW_DOM, SCRIPT as FLOW_SCRIPT
from test_workspace_rung_explanation_ui import SCRIPT as EXPLANATION_SCRIPT


MATH_FUNCTIONS = ["mathNode", "mathAtom", "mathFence", "mathExpression", "instructionEquation"]
RUNG_FUNCTIONS = [*MATH_FUNCTIONS, "renderEquationTree", "renderStructure", "renderRungLogic"]
MATH_DOM = r"""
document.createElementNS=(namespace,tag)=>{const result=node(tag);result.namespaceURI=namespace;return result;};
Element.prototype.focus=function(){document.activeElement=this;};
const exactText=root=>root.textContent+root.children.map(exactText).join('');
const tags=(root,tag)=>[root,...descendants(root)].filter(n=>n.tagName===tag);
const nodeMap=data=>new Map(data.nodes.map(n=>[n.id,n]));
const equation=data=>instructionEquation(data.source.instructions[0],data.occurrences[0],nodeMap(data));
"""


def parsed(expression: str = "A + 1", *, text: str | None = None) -> dict:
    """Use the production parser, rather than hand-inventing its AST contract."""
    _, inventory, _, calculations = capture(expression, text=text)
    return {"source": asdict(inventory.rungs[0]), "occurrences": calculations.occurrences,
            "nodes": calculations.nodes, "status": calculations.status}


@unittest.skipUnless(NODE, "Node is optional developer tooling")
class WorkspaceEquationTests(unittest.TestCase):
    def run_js(self, names: list[str], checks: str, payload: object = None) -> None:
        dom = DOM.replace("renderDetail, ", "") if "renderDetail" in names else DOM
        code = dom + MATH_DOM
        if "renderRungLogic" in names:
            code += FLOW_DOM + FLOW_SCRIPT + EXPLANATION_SCRIPT
        code += "\n" + "\n".join(function(name) for name in names)
        code += "\nconst data=" + json.dumps(payload) + ";\n"
        code += "\n(async()=>{\n" + checks + "\n})().catch(error=>{console.error(error);process.exitCode=1;});"
        result = subprocess.run([NODE, "-"], input=code, capture_output=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cpt_fraction_and_power_precedence_follow_parsed_source(self) -> None:
        self.run_js(MATH_FUNCTIONS, r"""
for (const item of data) {
  const rendered=equation(item);
  assert.equal(rendered.fallback,false);
  assert.equal(rendered.math.namespaceURI,'http://www.w3.org/1998/Math/MathML');
  const assignment=rendered.math.children[0];
  assert.equal(exactText(assignment.children[0]),'D');
  assert.equal(exactText(assignment.children[1]),'←');
}
const fraction=tags(equation(data[0]).math,'mfrac')[0];
assert.ok(exactText(fraction.children[0]).includes('(A+B)'));
assert.equal(exactText(fraction.children[1]),'C');
const signed=equation(data[1]).math.children[0].children[2];
assert.equal(signed.tagName,'mrow');
assert.equal(exactText(signed.children[0]),'−');
assert.equal(signed.children[1].tagName,'msup');
assert.equal(exactText(signed.children[1].children[0]),'A');
const signedBase=tags(equation(data[2]).math,'msup')[0];
assert.equal(exactText(signedBase.children[0]),'(−A)');
assert.equal(exactText(signedBase.children[1]),'B');
const powers=tags(equation(data[3]).math,'msup');
assert.equal(powers.length,2);
assert.equal(exactText(powers[0].children[1]),'C');
assert.equal(powers[0].children[0].tagName,'mrow');
assert.equal(exactText(powers[0].children[0].children[0]),'(');
assert.equal(powers[0].children[0].children[1],powers[1]);
assert.equal(exactText(powers[1].children[0]),'A');
assert.equal(exactText(powers[1].children[1]),'B');
""", [parsed(expression) for expression in ("(A+B)/C", "-A**B", "(-A)**B", "A**B**C")])

    def test_grouping_opaque_addresses_and_bitwise_words_remain_visible(self) -> None:
        self.run_js(MATH_FUNCTIONS, r"""
const grouped=equation(data[0]);
assert.ok(exactText(grouped.math).includes('(B−C)'));
assert.equal(tags(grouped.math,'mo').filter(n=>exactText(n)==='−').length,2);
const indexed=equation(data[1]);
const address=tags(indexed.math,'mi').find(n=>exactText(n)==='Arr[Index + 1]');
assert.ok(address);
assert.equal(address.attributes.mathvariant,'normal');
assert.equal(tags(indexed.math,'mi').filter(n=>exactText(n)==='Index').length,0);
const bitwise=equation(data[2]);
assert.deepEqual(tags(bitwise.math,'mo').map(exactText).filter(t=>['NOT','AND','XOR','OR'].includes(t)),['NOT','AND','XOR','OR']);
assert.equal(tags(bitwise.math,'mo').some(n=>['∧','∨','¬'].includes(exactText(n))),false);
""", [parsed(expression) for expression in ("A-(B-C)", "Arr[Index + 1] * A", "NOT A AND B XOR C OR D")])

    def test_instruction_arithmetic_destination_order_and_comparisons(self) -> None:
        self.run_js(MATH_FUNCTIONS, r"""
const make=(opcode,args)=>instructionEquation({id:'i',opcode,arguments:args},null,new Map());
for (const [opcode,operator] of [['ADD','+'],['SUB','−'],['MUL','×']]) {
  const rendered=make(opcode,['Source_A','Source_B','Destination']);
  assert.equal(exactText(rendered.math),'Destination←Source_A'+operator+'Source_B');
  assert.equal(rendered.label,'Calculation');
}
const division=make('DIV',['Source_A','Source_B','Destination']);
assert.equal(exactText(division.math.children[0].children[0]),'Destination');
const fraction=tags(division.math,'mfrac')[0];
assert.equal(exactText(fraction.children[0]),'Source_A');
assert.equal(exactText(fraction.children[1]),'Source_B');
for (const [opcode,operator] of [['EQU','='],['NEQ','≠'],['LES','<'],['LEQ','≤'],['GRT','>'],['GEQ','≥']]) {
  const rendered=make(opcode,['A','B']);
  assert.equal(exactText(rendered.math),'A'+operator+'B');
  assert.equal(rendered.label,'Comparison');
  assert.equal(tags(rendered.math,'mo').some(n=>exactText(n)==='←'),false);
}
assert.equal(exactText(make('MOV',['Input','Output']).math),'Output←Input');
assert.equal(exactText(make('CLR',['Output']).math),'Output←0');
""")

    def test_roots_absolute_value_and_logarithms_in_instructions_and_cpt(self) -> None:
        self.run_js(MATH_FUNCTIONS, r"""
for (const item of data) {
  for (const source of [item.direct,item.cpt]) {
    const rendered=equation(source);
    assert.equal(rendered.label,'Calculation');
    assert.equal(rendered.fallback,false);
    const assignment=rendered.math.children[0];
    assert.equal(exactText(assignment.children[0]),'D');
    assert.equal(exactText(assignment.children[1]),'←');
    const value=assignment.children[2];
    if (['SQR','SQRT'].includes(item.opcode)) {
      assert.equal(value.tagName,'msqrt');
      assert.equal(value.children.length,1);
      assert.equal(exactText(value.children[0]),'A');
      assert.equal(tags(rendered.math,'msup').length,0);
    } else if (item.opcode==='ABS') {
      assert.equal(exactText(value),'|A|');
      assert.equal(exactText(value.children[0]),'|');
      assert.equal(exactText(value.children[2]),'|');
    } else {
      assert.equal(exactText(value),'LN(A)');
      assert.equal(exactText(value.children[0]),'LN');
      assert.equal(exactText(value.children[1]),'(A)');
    }
  }
}
""", [{"opcode": opcode, "direct": parsed(text=f"{opcode}(A,D);"),
         "cpt": parsed(f"{opcode}(A)")} for opcode in ("SQR", "SQRT", "ABS", "LN")])

    def test_unsupported_instructions_bad_arity_and_cpt_retain_original_arguments(self) -> None:
        self.run_js(MATH_FUNCTIONS, r"""
for (const [opcode,args] of [
  ['Unknown_Block',[' A ','1','Output']],
  ['LIM',['Low','Value','High']], ['ADD',['A','D']], ['DIV',['A','','D']],
  ['MOV',['A','B','C']], ['CLR',[]]]) {
  const rendered=instructionEquation({id:'i',opcode,arguments:args},null,new Map());
  assert.equal(rendered.label,'Instruction');
  assert.deepEqual(tags(rendered.math,'mtext').map(exactText),args);
  assert.equal(tags(rendered.math,'mo').some(n=>exactText(n)==='←'),false);
  assert.equal(rendered.math.attributes['aria-label'],opcode+'('+args.join(', ')+')');
}
for (const item of data) {
  const rendered=equation(item);
  assert.equal(rendered.fallback,true);
  assert.ok(rendered.label.includes('Original expression'));
  assert.deepEqual(tags(rendered.math,'mtext').map(exactText),item.source.instructions[0].arguments);
  assert.equal(tags(rendered.math,'mfrac').length,0);
}
""", [parsed("A + PRIVATE_FUNCTION(B)"), parsed("A /"), parsed(text="CPT(D,A,B);")])

    def test_boolean_conditions_and_stateful_outputs_express_local_enable_semantics(self) -> None:
        self.run_js(MATH_FUNCTIONS, r"""
const make=(opcode,args)=>instructionEquation({id:'i',opcode,arguments:args},null,new Map());
for(const [opcode,expected,label] of [
  ['XIC','Incoming condition AND (Device.Ready is TRUE)','true'],['XIO','Incoming condition AND (Device.Ready is FALSE)','false'],
  ['OTE','Device.Ready←Incoming condition','incoming condition'],
  ['OTL','IF incoming condition is TRUE, SET(Device.Ready)','Latch'],['OTU','IF incoming condition is TRUE, RESET(Device.Ready)','Unlatch'],
]) {
  const result=make(opcode,['Device.Ready']);
  assert.equal(exactText(result.math),expected);
  assert.ok(result.label.includes(label));
  assert.equal(result.math.attributes['aria-label'],opcode+'(Device.Ready)');
}
for(const [opcode,label] of [['TON','On-delay timer'],['TOF','Off-delay timer'],
  ['RTO','Retentive timer'],['ONS','One-shot storage'],['CTU','Count up']]) {
  const args=['Stored_State','250','0'],result=make(opcode,args);
  assert.equal(result.label,label);
  assert.deepEqual(tags(result.math,'mtext').map(exactText),args);
  assert.equal(tags(result.math,'mo').some(n=>['←','⇒'].includes(exactText(n))),false);
}
for(const opcode of ['XIC','XIO','OTE','OTL','OTU']) {
  const result=make(opcode,['Bit','Unexpected']);
  assert.equal(result.label,'Instruction');
  assert.deepEqual(tags(result.math,'mtext').map(exactText),['Bit','Unexpected']);
}
""")

    def test_invalid_cyclic_and_foreign_ast_fall_back_without_partial_equation(self) -> None:
        self.run_js(MATH_FUNCTIONS, r"""
const mutations=[
  item=>{item.nodes=[];},
  item=>{item.nodes.find(n=>n.id===item.occurrences[0].root_node_id).child_ids[0]=item.occurrences[0].root_node_id;},
  item=>{item.nodes.find(n=>n.kind==='reference').instruction_id='other-instruction';},
  item=>{item.nodes.find(n=>n.id===item.occurrences[0].root_node_id).operator='UNSUPPORTED';},
  item=>{item.nodes.find(n=>n.id===item.occurrences[0].root_node_id).child_ids.pop();},
  item=>{item.nodes.find(n=>n.kind==='reference').kind='future-node';}
];
for (const mutate of mutations) {
  const damaged=JSON.parse(JSON.stringify(data));mutate(damaged);
  const rendered=equation(damaged);
  assert.equal(rendered.fallback,true);
  assert.deepEqual(tags(rendered.math,'mtext').map(exactText),damaged.source.instructions[0].arguments);
  assert.equal(tags(rendered.math,'mo').some(n=>exactText(n)==='←'),false);
  assert.equal(tags(rendered.math,'mfrac').length,0);
}
""", parsed("A / B"))

    def test_markup_like_source_is_text_in_math_and_original_source(self) -> None:
        self.run_js(RUNG_FUNCTIONS, r"""
const source={id:'r',text:'Unknown(<img src=x onerror=alert(1)>,"<script>bad</script>");',
instructions:[{id:'i',opcode:'Unknown',arguments:['<img src=x onerror=alert(1)>','"<script>bad</script>"']}],
structure:{kind:'sequence',items:[{kind:'instruction',instruction_id:'i'}]}};
const root=node('div');renderRungLogic(root,source,{},{sourceQualified:true});
const math=tags(root,'math')[0];
assert.deepEqual(tags(math,'mtext').map(exactText),source.instructions[0].arguments);
assert.equal(tags(root,'pre').find(n=>n.textContent===source.text).textContent,source.text);
assert.equal(tags(root,'script').length+tags(root,'img').length,0);
assert.equal(descendants(root).some(n=>'onerror' in n.attributes),false);
""")

    def test_parallel_paths_empty_legs_and_evidence_are_not_combined(self) -> None:
        self.run_js(RUNG_FUNCTIONS, r"""
const root=node('div');renderRungLogic(root,data.source,data);
const panel=descendants(root).filter(n=>n.attributes.role==='tabpanel')[2];
const paths=descendants(panel).filter(n=>n.className==='equation-path');
assert.equal(paths.length,3);
assert.ok(exactText(paths[0]).includes('Path 1'));
assert.ok(exactText(paths[0]).includes('D←A+B'));
assert.equal(tags(paths[1],'math').length,0);
assert.ok(exactText(paths[1]).includes('Empty branch path'));
assert.ok(exactText(paths[2]).includes('D←B−C'));
assert.equal(tags(panel,'math').length,data.source.instructions.length);
const evidence=tags(panel,'a').map(n=>n.href);
for(const instruction of data.source.instructions)
  assert.ok(evidence.includes('/analysis#view=ladder&source='+instruction.id));
""", parsed(text="[ADD(A,B,D),,SUB(B,C,D)]MOV(D,A);"))

    def test_default_summary_connected_flow_original_text_and_accessible_keyboard_tabs(self) -> None:
        self.run_js(RUNG_FUNCTIONS, r"""
const root=node('div');renderRungLogic(root,data.source,data,{sourceQualified:true});
const tabs=descendants(root).filter(n=>n.attributes.role==='tab');
const panels=descendants(root).filter(n=>n.attributes.role==='tabpanel');
assert.deepEqual(tabs.map(exactText),['Logic summary','Rung flow','Equations','Branch structure','Original text']);
assert.deepEqual(panels.map(p=>p.hidden),[false,true,true,true,true]);
assert.deepEqual(tabs.map(t=>t.attributes['aria-selected']),['true','false','false','false','false']);
assert.deepEqual(tabs.map(t=>t.tabIndex),[0,-1,-1,-1,-1]);
for(let i=0;i<5;i++) {
  assert.equal(tabs[i].attributes['aria-controls'],panels[i].id);
  assert.equal(panels[i].attributes['aria-labelledby'],tabs[i].id);
}
assert.equal(css(panels[0],'rung-explanation-step').length,data.source.instructions.length);
assert.ok(exactText(panels[0]).includes('Inputs & constants'));
assert.ok(exactText(panels[0]).includes('Logic paths'));
assert.ok(exactText(panels[0]).includes('Outputs & stored state'));
assert.equal(css(panels[1],'rung-flow-card').length,data.source.instructions.length);
assert.equal(tags(panels[1],'mfrac').length,1);
const raw=tags(panels[4],'pre')[0];assert.equal(raw.textContent,data.source.text);
tabs[4].events.click();assert.deepEqual(panels.map(p=>p.hidden),[true,true,true,true,false]);
let prevented=0;
const press=(i,key)=>tabs[i].events.keydown({key,preventDefault(){prevented++;}});
press(4,'ArrowRight');assert.equal(document.activeElement,tabs[0]);
press(0,'ArrowLeft');assert.equal(document.activeElement,tabs[4]);
press(4,'Home');assert.equal(document.activeElement,tabs[0]);
press(0,'End');assert.equal(document.activeElement,tabs[4]);
press(4,'Enter');assert.equal(prevented,4);
assert.equal(raw.textContent,data.source.text);
const select=tags(panels[1],'button').find(n=>exactText(n)==='Select individual instructions to group');
select.events.click();assert.deepEqual(panels.map(p=>p.hidden),[true,true,true,false,true]);
""", parsed(text="  CPT(D, (A + B) / C);\n"))

    def test_missing_structure_and_unavailable_ast_explain_original_source_fallback(self) -> None:
        self.run_js(RUNG_FUNCTIONS, r"""
const source={...data.source,structure:null};const root=node('div');
renderRungLogic(root,source,{status:'unavailable'},{sourceQualified:true});
const panel=descendants(root).find(n=>n.attributes.role==='tabpanel');
assert.ok(exactText(root).includes('could not be verified'));
assert.ok(exactText(panel).includes('Complete parsed instruction and branch structure is unavailable'));
assert.equal(tags(panel,'math').length,0);
assert.equal(tags(panel,'pre')[0].textContent,source.text);
""", parsed())

    def test_source_detail_passes_calculations_to_equations_and_keeps_review_editor(self) -> None:
        self.run_js([*RUNG_FUNCTIONS, "renderInstructions", "renderDetail"], r"""
let editorCall;
globalThis.renderEditor=(root,id,review,revision)=>{editorCall={id,review,revision};root.append(node('button','Save review'));};
const root=node('div');const review={status:'confirmed'};
renderDetail({source:data.source,calculations:data,source_qualified:true,review,revision:9},root);
const panels=descendants(root).filter(n=>n.attributes.role==='tabpanel');
assert.equal(css(panels[0],'rung-explanation-step').length,data.source.instructions.length);
assert.ok(exactText(panels[0]).includes('Saved expression syntax is parsed'));
assert.equal(tags(panels[1],'mfrac').length,1);
assert.equal(tags(panels[2],'mfrac').length,1);
assert.equal(editorCall.id,data.source.id);
assert.equal(editorCall.review,review);
assert.equal(editorCall.revision,9);
assert.ok(exactText(root).includes('Save review'));
assert.equal(tags(root,'pre').find(n=>n.textContent===data.source.text).textContent,data.source.text);
""", parsed("A/B"))

    def test_rung_list_preview_typesets_available_expressions_and_explains_remaining_paths(self) -> None:
        self.run_js([*MATH_FUNCTIONS, "renderRungPreview"], r"""
const preview={preview:{instructions:data.source.instructions.slice(0,2),
  instruction_count:data.source.instructions.length,branch_count:2,calculations:data}};
const root=renderRungPreview(preview);
assert.equal(tags(root,'math').length,2);
assert.equal(tags(root,'mfrac').length,1);
assert.ok(exactText(root).includes('Incoming condition AND (Ready is TRUE)'));
assert.ok(exactText(root).includes('1 more instruction'));
assert.ok(exactText(root).includes('2 parallel branches'));
assert.ok(exactText(root).includes('open flow to follow paths'));
assert.equal(exactText(root).includes(data.source.text),false);
const unavailable=renderRungPreview({});
assert.equal(tags(unavailable,'math').length,0);
assert.ok(exactText(unavailable).includes('complete text'));
""", parsed(text="XIC(Ready)CPT(D,(A+B)/C)OTE(Output);"))


if __name__ == "__main__":
    unittest.main()
