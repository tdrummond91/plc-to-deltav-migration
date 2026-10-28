"""Verify equation presentation against invented, actually parsed L5X evidence."""
from __future__ import annotations

from dataclasses import asdict
import json
import subprocess
import unittest

from test_calculations import capture
from test_workspace_ui import ASSETS, DOM, NODE, Page, function
from test_workspace_rung_flow_ui import FLOW_DOM
from test_workspace_rung_explanation_ui import SCRIPT as EXPLANATION_SCRIPT


MATH_FUNCTIONS = ["mathNode", "mathAtom", "mathFence", "mathExpression", "instructionEquation"]
RUNG_FUNCTIONS = [*MATH_FUNCTIONS, "renderEquationTree", "renderStructure", "loadRungRenderer",
                  "renderRungRenderer", "renderRungLogic"]
MATH_DOM = r"""
document.createElement=tag=>node(tag);
document.createElementNS=(namespace,tag)=>{const result=node(tag);result.namespaceURI=namespace;return result;};
Element.prototype.getAttribute=function(name){return name==='class'?this.attributes[name]??this.className:this.attributes[name]??null;};
Element.prototype.focus=function(){document.activeElement=this;};
const exactText=root=>root.textContent+root.children.map(exactText).join('');
const tags=(root,tag)=>[root,...descendants(root)].filter(n=>n.tagName===tag);
const hasClass=(element,name)=>(element.attributes.class||element.className||'').split(' ').includes(name);
const argumentTexts=root=>tags(root,'mrow').filter(n=>hasClass(n,'equation-source-argument')).map(exactText);
const variableColors=(root,text)=>[root,...descendants(root)].filter(n=>hasClass(n,'source-variable')&&exactText(n)===text).map(n=>n.attributes.class.match(/\bsource-var-\d\b/)[0]);
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
            code += FLOW_DOM
            # Exercise shipped dependencies in the HTML's real deferred order,
            # including fresh source popouts, rather than injecting a test order.
            scripts = [attrs['src'] for tag, attrs in Page().elements if tag == 'script']
            required = {'/source-colors.js', '/rung-flow.js', '/rung-explanation.js', '/ladder-diagram.js'}
            self.assertTrue(required.issubset(scripts))
            for asset in scripts:
                if asset in required:
                    self.assertLess(scripts.index(asset), scripts.index('/workspace.js'))
                    code += (ASSETS / asset.lstrip('/')).read_text(encoding='utf-8')
        else:
            code += (ASSETS / "source-colors.js").read_text(encoding="utf-8") + EXPLANATION_SCRIPT
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
for (const [opcode,operator] of [['EQU','=='],['NEQ','!='],['LES','<'],['LEQ','≤'],['GRT','>'],['GEQ','≥']]) {
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
  assert.deepEqual(argumentTexts(rendered.math),args);
  assert.equal(tags(rendered.math,'mo').some(n=>exactText(n)==='←'),false);
  assert.equal(rendered.math.attributes['aria-label'],opcode+'('+args.join(', ')+')');
}
for (const item of data) {
  const rendered=equation(item);
  assert.equal(rendered.fallback,true);
  assert.ok(rendered.label.includes('Original expression'));
  assert.deepEqual(argumentTexts(rendered.math),item.source.instructions[0].arguments);
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
  assert.deepEqual(argumentTexts(result.math),args);
  assert.equal(tags(result.math,'mo').some(n=>['←','⇒'].includes(exactText(n))),false);
}
for(const opcode of ['XIC','XIO','OTE','OTL','OTU']) {
  const result=make(opcode,['Bit','Unexpected']);
  assert.equal(result.label,'Instruction');
  assert.deepEqual(argumentTexts(result.math),['Bit','Unexpected']);
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
  assert.deepEqual(argumentTexts(rendered.math),damaged.source.instructions[0].arguments);
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
assert.deepEqual(argumentTexts(math),source.instructions[0].arguments);
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
assert.deepEqual(tabs.map(exactText),['Logic summary','Full ladder','Equations','Branch structure','Original text']);
assert.deepEqual(panels.map(p=>p.hidden),[true,false,true,true,true]);
assert.deepEqual(tabs.map(t=>t.attributes['aria-selected']),['false','true','false','false','false']);
assert.deepEqual(tabs.map(t=>t.tabIndex),[-1,0,-1,-1,-1]);
for(let i=0;i<5;i++) {
  assert.equal(tabs[i].attributes['aria-controls'],panels[i].id);
  assert.equal(panels[i].attributes['aria-labelledby'],tabs[i].id);
}
assert.equal(css(panels[0],'rung-explanation-step').length,data.source.instructions.length);
assert.ok(exactText(panels[0]).includes('Inputs & constants'));
assert.ok(exactText(panels[0]).includes('Logic paths'));
assert.ok(exactText(panels[0]).includes('Outputs & stored state'));
assert.equal(tags(panels[1],'g').filter(n=>hasClass(n,'ladder-diagram-instruction')).length,data.source.instructions.length);
assert.ok(tags(panels[1],'svg').length);
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
        self.run_js([*RUNG_FUNCTIONS, "renderInstructions", "renderSelectedAnnotation", "renderDetail"], r"""
let editorCall;
globalThis.renderEditor=(root,id,review,revision)=>{editorCall={id,review,revision};root.append(node('button','Save review'));};
const root=node('div');const review={status:'confirmed'};
renderDetail({source:data.source,calculations:data,source_qualified:true,review,revision:9},root);
const panels=descendants(root).filter(n=>n.attributes.role==='tabpanel');
assert.equal(css(panels[0],'rung-explanation-step').length,data.source.instructions.length);
assert.ok(exactText(panels[0]).includes('Saved expression syntax is parsed'));
assert.ok(tags(panels[1],'svg').length);
assert.equal(tags(panels[2],'mfrac').length,1);
assert.equal(editorCall.id,data.source.id);
assert.equal(editorCall.review,review);
assert.equal(editorCall.revision,9);
assert.ok(exactText(root).includes('Save review'));
assert.equal(tags(root,'pre').find(n=>n.textContent===data.source.text).textContent,data.source.text);
""", parsed("A/B"))

    def test_fresh_copy_rung_source_keeps_comment_ladder_and_review_controls(self) -> None:
        self.run_js([*RUNG_FUNCTIONS, "renderInstructions", "renderSelectedAnnotation", "renderDetail"], r"""
globalThis.translations={show:(root,data)=>root.append(node('p',data.source.comment))};
globalThis.renderEditor=(root,id)=>{assert.equal(id,data.source.id);root.append(node('input','Saved decision'));};
const source={...data.source,comment:'Invented registers copied into an engineering buffer.'};
const root=node('div');renderDetail({source,calculations:data,source_qualified:true,review:{},revision:4},root);
const panels=descendants(root).filter(n=>n.attributes.role==='tabpanel');
assert.equal(panels.length,5);assert.ok(tags(panels[1],'svg').length);
assert.ok(contents(root).includes(source.comment));assert.ok(contents(root).includes('Your engineering review'));
assert.equal(tags(panels[4],'pre')[0].textContent,source.text);
assert.ok(tags(panels[1],'g').some(n=>n.attributes['data-instruction-id']===source.instructions[0].id));
""", parsed(text="COP(Local:3:I.Data[0],Buffer[0],4);"))

    def test_missing_summary_asset_reloads_once_without_blanking_the_ladder(self) -> None:
        self.run_js(RUNG_FUNCTIONS, r"""
const original=window.PLCRungExplanation,loaded=[];delete window.PLCRungExplanation;
document.head=node('head');document.head.append=script=>{loaded.push(script);};
const root=node('div');renderRungLogic(root,data.source,data,{sourceQualified:true});
const panels=descendants(root).filter(n=>n.attributes.role==='tabpanel');
assert.equal(loaded.length,1);assert.equal(loaded[0].src,'/rung-explanation.js');
assert.ok(contents(panels[0]).includes('Loading logic summary'));
assert.ok(tags(panels[1],'svg').length);assert.equal(tags(panels[4],'pre')[0].textContent,data.source.text);
window.PLCRungExplanation=original;loaded[0].onload();await Promise.resolve();await Promise.resolve();
assert.ok(css(panels[0],'rung-explanation-step').length);assert.equal(tags(panels[0],'button').length,0);
assert.equal(loaded.length,1);
""", parsed(text="COP(Local:3:I.Data[0],Buffer[0],4);"))

    def test_failed_local_asset_retry_keeps_the_editor_draft_and_other_views(self) -> None:
        self.run_js([*RUNG_FUNCTIONS, "renderInstructions", "renderSelectedAnnotation", "renderDetail"], r"""
const original=window.PLCLadderDiagram,loaded=[];delete window.PLCLadderDiagram;
document.head=node('head');document.head.append=script=>{loaded.push(script);};
const draft=node('input');draft.value='Retained engineering correction';
globalThis.renderEditor=root=>root.append(draft);
const root=node('div');renderDetail({source:data.source,calculations:data,source_qualified:true,review:{},revision:4},root);
const panels=descendants(root).filter(n=>n.attributes.role==='tabpanel');
assert.equal(loaded.length,1);assert.equal(loaded[0].src,'/ladder-diagram.js');
loaded[0].onerror();await Promise.resolve();await Promise.resolve();
assert.ok(contents(panels[1]).includes('stop and reopen the workspace'));
assert.equal(tags(panels[1],'pre')[0].textContent,data.source.text);
assert.ok(css(panels[0],'rung-explanation-step').length);assert.equal(tags(panels[4],'pre')[0].textContent,data.source.text);
const retry=tags(panels[1],'button').find(n=>n.textContent==='Retry display');assert.equal(retry.disabled,false);
const pending=retry.events.click();assert.equal(retry.disabled,true);assert.equal(loaded.length,2);
await retry.events.click();assert.equal(loaded.length,2,'Repeated clicks cannot start duplicate loads');
window.PLCLadderDiagram=original;loaded[1].onload();await pending;
assert.ok(tags(panels[1],'svg').length);assert.equal(contents(panels[1]).includes('could not be loaded'),false);
assert.ok(tags(panels[1],'button').some(n=>n.textContent==='Select individual instructions to group'));
assert.ok(descendants(root).includes(draft));assert.equal(draft.value,'Retained engineering correction');
""", parsed(text="COP(Local:3:I.Data[0],Buffer[0],4);"))

    def test_renderer_exception_is_contained_and_manual_retry_does_not_reload_source(self) -> None:
        self.run_js(RUNG_FUNCTIONS, r"""
const original=window.PLCRungExplanation;
window.PLCRungExplanation={render:()=>{throw new Error('Invented renderer failure');}};
document.head=node('head');document.head.append=()=>assert.fail('An initialized renderer should not reload its script');
const root=node('div');assert.doesNotThrow(()=>renderRungLogic(root,data.source,data,{sourceQualified:true}));
const panels=descendants(root).filter(n=>n.attributes.role==='tabpanel');
assert.ok(contents(panels[0]).includes('temporarily unavailable'));assert.ok(tags(panels[1],'svg').length);
assert.equal(contents(root).includes('Invented renderer failure'),false);
window.PLCRungExplanation=original;
await tags(panels[0],'button').find(n=>n.textContent==='Retry display').events.click();
assert.ok(css(panels[0],'rung-explanation-step').length);assert.ok(tags(panels[1],'svg').length);
""", parsed(text="COP(Local:3:I.Data[0],Buffer[0],4);"))

    def test_late_renderer_retry_for_previous_source_cannot_replace_current_rung_or_draft(self) -> None:
        self.run_js([*RUNG_FUNCTIONS, "renderInstructions", "renderSelectedAnnotation", "renderDetail"], r"""
const original=window.PLCLadderDiagram,loaded=[],drafts=[];delete window.PLCLadderDiagram;
document.head=node('head');document.head.append=script=>loaded.push(script);
globalThis.renderEditor=(root,id)=>{const draft=node('input');draft.dataset.source=id;drafts.push(draft);root.append(draft);};
const root=node('div');
renderDetail({source:data[0].source,calculations:data[0],source_qualified:true,review:{},revision:4},root);
const previousPanels=descendants(root).filter(n=>n.attributes.role==='tabpanel');
assert.equal(loaded.length,1);assert.ok(contents(previousPanels[1]).includes('Loading ladder drawing'));
renderDetail({source:data[1].source,calculations:data[1],source_qualified:true,review:{},revision:4},root);
assert.equal(loaded.length,2);
window.PLCLadderDiagram=original;loaded[1].onload();await Promise.resolve();await Promise.resolve();
const currentPanels=descendants(root).filter(n=>n.attributes.role==='tabpanel');
assert.ok(tags(currentPanels[1],'svg').length);assert.equal(tags(currentPanels[4],'pre')[0].textContent,data[1].source.text);
drafts[1].value='Keep this newer rung correction';state.dirty=true;
const visibleNodes=descendants(root),visibleText=contents(root);
loaded[0].onload();await Promise.resolve();await Promise.resolve();
assert.ok(tags(previousPanels[1],'svg').length,'The previous request really completed');
assert.deepEqual(descendants(root),visibleNodes,'A late display update remains in the detached previous source');
assert.equal(contents(root),visibleText);assert.equal(drafts[1].value,'Keep this newer rung correction');
assert.ok(descendants(root).includes(drafts[1]));assert.equal(descendants(root).includes(drafts[0]),false);
assert.equal(state.dirty,true);assert.equal(tags(currentPanels[4],'pre')[0].textContent,data[1].source.text);
""", [parsed(text="COP(Local:3:I.Data[0],Buffer[0],4);"),
        parsed(text="XIC(Enable)OTE(Ready);")])

    def test_asset_loader_is_bounded_and_rejects_missing_exports_or_unknown_assets(self) -> None:
        self.run_js(["loadRungRenderer"], r"""
const loaded=[],timers=[],cleared=[];
const savedSetTimeout=globalThis.setTimeout,savedClearTimeout=globalThis.clearTimeout;
globalThis.setTimeout=(callback,delay)=>{assert.equal(delay,10000);timers.push(callback);return timers.length;};
globalThis.clearTimeout=id=>cleared.push(id);
document.head=node('head');document.head.append=script=>loaded.push(script);
await assert.rejects(loadRungRenderer('https://untrusted.invalid/file.js'),/Unknown/);assert.equal(loaded.length,0);
await assert.rejects(loadRungRenderer('__proto__'),/Unknown/);assert.equal(loaded.length,0);
delete window.PLCRungExplanation;
const missing=loadRungRenderer('PLCRungExplanation');loaded[0].onload();
await assert.rejects(missing,/did not initialize/);assert.deepEqual(cleared,[1]);
const timed=loadRungRenderer('PLCLadderDiagram');timers[1]();
await assert.rejects(timed,/timed out/);assert.deepEqual(cleared,[1,2]);
loaded[1].onerror();assert.deepEqual(cleared,[1,2],'Late callbacks cannot settle a completed load twice');
globalThis.setTimeout=savedSetTimeout;globalThis.clearTimeout=savedClearTimeout;
""")

    def test_variable_identity_colors_are_shared_across_equations_flow_branches_and_list(self) -> None:
        self.run_js([*RUNG_FUNCTIONS, "renderInstructions"], r"""
const root=node('div');renderRungLogic(root,data.source,data,{sourceQualified:true});
const list=node('div');renderInstructions(list,data.source.instructions,[]);
const panels=descendants(root).filter(n=>n.attributes.role==='tabpanel');
for(const text of ['Flow.PV','Sum','Result','Device.Ready']) {
  const colors=[...variableColors(panels[1],text),...variableColors(panels[2],text),
    ...variableColors(panels[3],text),...variableColors(list,text)];
  assert.ok(colors.length>=4,text+' appears in each source view');
  assert.equal(new Set(colors).size,1,text+' retains one presentation color');
}
assert.notEqual(variableColors(panels[2],'Flow.PV')[0],variableColors(panels[2],'Sum')[0]);
const fraction=tags(panels[2],'mfrac')[0];
assert.ok(hasClass(fraction,'source-operator'));
for(const operand of ['Sum','Flow.PV']) assert.ok(variableColors(fraction,operand).length);
assert.ok(tags(panels[2],'mo').filter(n=>['←','+'].includes(exactText(n))).every(n=>hasClass(n,'source-operator')));
assert.ok(tags(panels[2],'mo').filter(n=>['(',')',','].includes(exactText(n))).every(n=>!hasClass(n,'source-operator')));
assert.ok([root,...descendants(root)].some(n=>exactText(n)==='2.5'&&hasClass(n,'source-literal')));
assert.ok(tags(panels[2],'mi').some(n=>exactText(n)==='SET'&&hasClass(n,'source-operator')&&!hasClass(n,'source-variable')));
assert.equal(tags(panels[4],'pre')[0].textContent,data.source.text);
assert.equal(tags(panels[3],'input').length,data.source.instructions.length);
""", parsed(text="ADD(Flow.PV,2.5,Sum)[CPT(Result,(Sum+Flow.PV)/3),MOV(Result,Flow.PV)]XIC(Device.Ready)OTL(Device.Ready);"))

    def test_functions_literals_and_indexed_source_keep_exact_math_text(self) -> None:
        self.run_js(MATH_FUNCTIONS, r"""
const first=equation(data[0]),indexed=equation(data[1]);
assert.ok(tags(first.math,'msqrt').every(n=>hasClass(n,'source-operator')));
assert.ok(tags(first.math,'mi').some(n=>exactText(n)==='LN'&&hasClass(n,'source-operator')&&!hasClass(n,'source-variable')));
assert.ok(tags(first.math,'mn').some(n=>exactText(n)==='2'&&hasClass(n,'source-literal')));
assert.equal(variableColors(first.math,'Flow.PV').length,1);
const reference=tags(indexed.math,'mi').find(n=>exactText(n)==='Arr[Index + 1]');
assert.ok(reference&&hasClass(reference,'source-variable'));
assert.equal(tags(indexed.math,'mi').some(n=>exactText(n)==='Index'),false);
assert.equal(indexed.math.attributes['aria-label'],'CPT(D, Arr[Index + 1] + 16#FF)');
assert.ok(tags(indexed.math,'mn').some(n=>exactText(n)==='16#FF'&&hasClass(n,'source-literal')));
""", [parsed("SQRT(Flow.PV)+LN(Count)+2"), parsed("Arr[Index + 1] + 16#FF")])

    def test_fallback_argument_colors_preserve_all_text_and_do_not_create_markup(self) -> None:
        self.run_js(MATH_FUNCTIONS, r"""
const instruction={id:'invented',opcode:'Custom_Block',arguments:[' Flow.PV + 2 ','Flow.PV','"<b>source only</b>"']};
const rendered=instructionEquation(instruction,null,new Map());
assert.equal(exactText(rendered.math),'Custom_Block( Flow.PV + 2 ,Flow.PV,"<b>source only</b>")');
assert.deepEqual(argumentTexts(rendered.math),instruction.arguments);
assert.ok(tags(rendered.math,'mi').some(n=>exactText(n)==='Custom_Block'&&hasClass(n,'source-operator')));
assert.equal(new Set(variableColors(rendered.math,'Flow.PV')).size,1);
assert.equal(variableColors(rendered.math,'Flow.PV').length,2);
assert.ok(tags(rendered.math,'mtext').some(n=>exactText(n)==='+'&&hasClass(n,'source-operator')));
assert.ok(tags(rendered.math,'mtext').some(n=>exactText(n)==='2'&&hasClass(n,'source-literal')));
assert.equal(tags(rendered.math,'b').length,0);
assert.equal(rendered.math.attributes['aria-label'],'Custom_Block('+instruction.arguments.join(', ')+')');
assert.ok(tags(rendered.math,'mtext').every(n=>n.namespaceURI==='http://www.w3.org/1998/Math/MathML'));
""")

    def test_help_attaches_to_instruction_content_without_native_titles_or_review_control_targets(self) -> None:
        self.run_js([*RUNG_FUNCTIONS, "renderInstructions"], r"""
const attached=[];window.PLCInstructionHelp={attach:(anchor,instruction,context)=>attached.push({anchor,instruction,context}),close:()=>{}};
const root=node('div');renderRungLogic(root,data.source,data,{sourceQualified:true});
const list=node('div'),context={runId:'saved-list-run'};renderInstructions(list,data.source.instructions,[],context);
const panels=descendants(root).filter(n=>n.attributes.role==='tabpanel');
const math=tags(panels[2],'math');
for(let index=0;index<data.source.instructions.length;index++) {
  const instruction=data.source.instructions[index],help=window.PLCRungExplanation.summary(instruction);
  assert.ok(help.length>instruction.opcode.length);
  assert.equal(math[index].attributes['aria-description'],help);
  assert.equal(math[index].attributes['aria-label'],instruction.opcode+'('+instruction.arguments.join(', ')+')');
  const targets=attached.filter(item=>item.instruction===instruction && !hasClass(item.anchor,'ladder-diagram-instruction')).map(item=>item.anchor);
  assert.equal(targets.length,4+instruction.arguments.length,'Equations, branch and list header/arguments get help');
  const listTargets=attached.filter(item=>item.instruction===instruction&&item.context===context);
  assert.equal(listTargets.length,1+instruction.arguments.length,'Each argument keeps its explicit saved-run identity');
  targets.forEach(anchor=>{
    assert.equal(anchor.attributes['aria-description'],help);
    assert.equal([anchor,...descendants(anchor)].some(n=>['a','input','label','button'].includes(n.tagName)),false,
      'Help must not intercept review checkboxes or evidence links');
  });
}
for(const surface of [root,list]) for(const item of [surface,...descendants(surface)]) {
  assert.equal(Boolean(item.title),false,'No competing native tooltip');
  assert.equal(item.attributes.title,undefined,'MathML also uses the shared help');
}
const branchChecks=tags(panels[3],'input');
assert.equal(branchChecks.length,data.source.instructions.length);
assert.ok(branchChecks.every(input=>typeof input.events.change==='function'),'Review selection remains wired');
const unknown=data.source.instructions[1];
assert.ok(/unresolved|unsupported|not inferred|unknown|not recognized/i.test(window.PLCRungExplanation.summary(unknown)));
assert.equal(tags(panels[4],'pre')[0].textContent,data.source.text);
""", parsed(text="GEQ(Measured,Limit)Custom_Block(Measured,Output)OTE(Output);"))

    def test_reconciliation_help_keeps_historical_run_through_nested_branches(self) -> None:
        self.run_js(["renderStructure", "rebindDialog"], r"""
const attached=[],pending=[];
state.project.active_run='current-analysis';
window.PLCInstructionHelp={attach:(anchor,instruction,context)=>attached.push({anchor,instruction,
  runId:context?.runId??state.project.active_run})};
globalThis.debounce=()=>()=>{};
run=action=>{const result=action();pending.push(result);return result;};
const historical={...data.source,comment:null,description:null};
api=async path=>{
  const query=new URL(path,'http://local').searchParams;
  assert.equal(query.get('run_id'),'historical-analysis');assert.equal(query.get('id'),historical.id);
  return {run_id:'historical-analysis',source:historical,path:'Invented historical source'};
};
rebindDialog({run_id:'historical-analysis',source_id:historical.id,review:{}});
await Promise.all(pending);
assert.equal(attached.length,historical.instructions.length);
attached.forEach((item,index)=>{
  assert.equal(item.runId,'historical-analysis');assert.equal(item.instruction,historical.instructions[index]);
});
const historicalScroll=tags(modalBody,'div').find(n=>hasClass(n,'structure-scroll'));
assert.equal(tags(historicalScroll,'a').length,0);assert.equal(tags(historicalScroll,'input').length,0);
renderStructure(data.source.structure,new Map(data.source.instructions.map(instruction=>[instruction.id,instruction])),new Set());
assert.ok(attached.slice(historical.instructions.length).every(item=>item.runId==='current-analysis'),
  'Current source views continue using their configured current context');
""", parsed(text="XIC(Start)[GEQ(Value,Limit),XIO(Hold)]OTE(Result);"))

    def test_shared_reading_guide_explains_colors_without_adding_review_decisions(self) -> None:
        self.run_js(["renderGuide"], r"""
const root=node('div');$=id=>{assert.equal(id,'guide-content');return root;};
globalThis.localStorage={getItem:()=>null};
globalThis.importDialog=()=>{};globalThis.categoryManager=()=>{};
globalThis.switchView=()=>{};
renderGuide();
assert.ok(exactText(root).includes('Six variable colors repeat'));
assert.ok(exactText(root).includes('Colors do not indicate live values, input/output roles, alarm severity or execution state'));
assert.ok(exactText(root).includes('unsupported blocks keep their effects unresolved'));
assert.equal(tags(root,'input').length,8);
assert.equal(commands.length,0);
""")


if __name__ == "__main__":
    unittest.main()
