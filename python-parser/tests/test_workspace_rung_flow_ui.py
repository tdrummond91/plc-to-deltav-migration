"""Connected rung layout invariants exercised against the shipped browser asset."""
from __future__ import annotations

from dataclasses import asdict
import json
import subprocess
import unittest

from test_calculations import capture
from test_workspace_ui import ASSETS, DOM, NODE


SCRIPT = (ASSETS / "rung-flow.js").read_text(encoding="utf-8")
FLOW_DOM = r"""
const makeElement=(tag)=>{
  const result=node(tag);result.style={};
  result.classList={add:(name)=>{result.className+=(result.className?' ':'')+name;}};
  return result;
};
document.createElement=makeElement;
document.createElementNS=(namespace,tag)=>{
  const result=makeElement(tag);result.namespaceURI=namespace;return result;
};
const all=(root)=>[root,...descendants(root)];
const css=(root,name)=>all(root).filter(n=>n.className.split(' ').includes(name));
const inst=id=>({kind:'instruction',instruction_id:id});
const seq=(...items)=>({kind:'sequence',items});
const branch=(...legs)=>({kind:'branch',legs});
const source=(structure,ids)=>({structure,text:'Synthetic complete rung source;',
  instructions:ids.map(id=>({id,opcode:id.toUpperCase(),arguments:['Input','Output']}))});
const render=data=>window.PLCRungFlow.render(data);
const coords=root=>all(root).filter(n=>n.tagName==='path').map(n=>({
  values:n.attributes.d.match(/-?\d+(?:\.\d+)?/g).map(Number),kind:n.attributes['data-wire']
}));
const number=value=>Number.parseFloat(value);
const boxes=root=>css(root,'rung-flow-card').map(n=>({
  id:n.dataset.instructionId,x:number(n.style.left)-78,y:number(n.style.top)-48,
  width:number(n.style.width),height:number(n.style.height)
}));
const pointOn=(x,y,line)=>{
  const [x1,y1,x2,y2]=line.values;
  return x>=Math.min(x1,x2)&&x<=Math.max(x1,x2)
    &&y>=Math.min(y1,y2)&&y<=Math.max(y1,y2);
};
const assertGeometry=root=>{
  const cards=boxes(root),lines=coords(root);
  assert.ok(cards.length);
  assert.ok(lines.length);
  for(const card of cards){
    const middle=card.y+card.height/2;
    assert.ok(lines.some(line=>pointOn(card.x,middle,line)),card.id+' inlet disconnected');
    assert.ok(lines.some(line=>pointOn(card.x+card.width,middle,line)),card.id+' outlet disconnected');
    for(const line of lines){
      const [x1,y1,x2,y2]=line.values;
      assert.ok(x1===x2||y1===y2,'All wires are orthogonal');
      if(y1===y2&&y1>card.y&&y1<card.y+card.height)
        assert.ok(Math.max(x1,x2)<=card.x||Math.min(x1,x2)>=card.x+card.width,
          line.kind+' crosses '+card.id);
      if(x1===x2&&x1>card.x&&x1<card.x+card.width)
        assert.ok(Math.max(y1,y2)<=card.y||Math.min(y1,y2)>=card.y+card.height,
          line.kind+' crosses '+card.id);
    }
    for(const other of cards.filter(item=>item.id!==card.id))
      assert.ok(card.x+card.width<=other.x||other.x+other.width<=card.x
        ||card.y+card.height<=other.y||other.y+other.height<=card.y,
        card.id+' overlaps '+other.id);
  }
};
"""


@unittest.skipUnless(NODE, "Node is optional developer tooling")
class WorkspaceRungFlowTests(unittest.TestCase):
    def run_js(self, checks: str, payload: object = None) -> None:
        code = DOM + FLOW_DOM + SCRIPT + "\nconst data=" + json.dumps(payload)
        code += ";\n(function(){\n" + checks + "\n})();"
        result = subprocess.run(
            [NODE, "-"], input=code, capture_output=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_parsed_source_keeps_all_instructions_on_connected_paths(self) -> None:
        _, inventory, _, _ = capture(
            "A+B", text="XIC(Enable)[ADD(A,B,C),XIO(Inhibit)[TON(Timer,100,0),]]OTE(Output);",
        )
        self.run_js(r"""
const root=render(data);
assertGeometry(root);
assert.deepEqual(boxes(root).map(card=>card.id),data.instructions.map(item=>item.id));
assert.equal(coords(root).filter(line=>line.kind==='split').length,2);
assert.equal(coords(root).filter(line=>line.kind==='join').length,2);
assert.equal(coords(root).filter(line=>line.kind==='bypass').length,1);
assert.ok(contents(root).includes('Empty path'));
assert.ok(contents(root).includes('not elapsed time or live execution'));
assert.equal(css(root,'rung-flow-fallback').length,0);
""", asdict(inventory.rungs[0]))

    def test_nested_parallel_legs_have_true_split_and_join_buses(self) -> None:
        self.run_js(r"""
const tree=seq(inst('a'),branch(seq(inst('b'),branch(seq(),seq(inst('c')))),
  seq(inst('d'),inst('e'))),inst('f'));
const root=render(source(tree,['a','b','c','d','e','f']));
assertGeometry(root);
const cards=Object.fromEntries(boxes(root).map(card=>[card.id,card]));
assert.equal(cards.a.y,cards.f.y);
assert.ok(cards.d.y>cards.b.y);
assert.ok(cards.c.y<cards.d.y);
assert.ok(cards.b.x>cards.a.x);
assert.ok(cards.f.x>cards.e.x);
const lines=coords(root),splits=lines.filter(line=>line.kind==='split'),joins=lines.filter(line=>line.kind==='join');
assert.equal(splits.length,2);assert.equal(joins.length,2);
for(const line of lines.filter(line=>line.kind==='branch-entry')) {
  const [x,y]=line.values;
  assert.ok(splits.some(bus=>pointOn(x,y,bus)),'Every branch inlet meets a split bus');
}
for(const line of lines.filter(line=>line.kind==='branch-exit')) {
  const [,,x,y]=line.values;
  assert.ok(joins.some(bus=>pointOn(x,y,bus)),'Every branch outlet meets a join bus');
}
assert.equal(lines.filter(line=>line.kind==='bypass').length,1);
""")

    def test_single_sequence_and_empty_rung_keep_source_progression(self) -> None:
        self.run_js(r"""
const root=render(source(seq(inst('first'),inst('second'),inst('last')),['first','second','last']));
assertGeometry(root);
const cards=boxes(root);
assert.equal(new Set(cards.map(card=>card.y)).size,1);
assert.ok(cards[0].x<cards[1].x&&cards[1].x<cards[2].x);
assert.equal(coords(root).filter(line=>line.kind==='series').length,2);
assert.equal(coords(root).filter(line=>line.kind==='split').length,0);
const empty=render(source(seq(),[]));
assert.equal(boxes(empty).length,0);
assert.equal(coords(empty).filter(line=>line.kind==='bypass').length,1);
assert.ok(contents(empty).includes('Empty path'));
""")

    def test_opaque_and_stateful_instructions_keep_native_callback_content(self) -> None:
        self.run_js(r"""
const data=source(seq(inst('timer'),inst('opaque')),['timer','opaque']);
data.instructions[0].opcode='TON';data.instructions[1].opcode='UNKNOWN';
data.instructions[1].arguments=['<img src=x onerror=alert(1)>'];
let seen=[],clicked=null;
const root=window.PLCRungFlow.render(data,{instruction:(instruction)=>{
  seen.push(instruction.id);
  const wrapper=document.createElement('div');
  const math=document.createElementNS('http://www.w3.org/1998/Math/MathML','math');
  math.textContent=instruction.arguments[0];wrapper.append(math);return wrapper;
},onInstruction:instruction=>{clicked=instruction.id;}});
assertGeometry(root);
assert.deepEqual(seen,['timer','opaque']);
assert.equal(all(root).filter(n=>n.namespaceURI==='http://www.w3.org/1998/Math/MathML').length,2);
assert.equal(all(root).filter(n=>n.tagName==='img').length,0);
assert.ok(contents(root).includes('<img src=x onerror=alert(1)>'));
css(root,'rung-flow-inspect')[1].events.click();assert.equal(clicked,'opaque');
""")

    def test_zoom_changes_canvas_and_scroll_bounds_without_dropping_nodes(self) -> None:
        self.run_js(r"""
const root=render(source(seq(inst('a')),['a']));
const canvas=css(root,'rung-flow-canvas')[0],scaled=css(root,'rung-flow-scaled')[0];
const controls=css(root,'rung-flow-controls')[0].children;
const out=controls.find(n=>n.textContent==='Zoom out');
const into=controls.find(n=>n.textContent==='Zoom in');
const reset=controls.find(n=>n.textContent==='Reset zoom');
out.events.click();assert.equal(canvas.style.transform,'scale(0.75)');
assert.equal(number(scaled.style.width),number(canvas.style.width)*0.75);
for(let i=0;i<10;i++)out.events.click();
assert.equal(canvas.style.transform,'scale(0.25)');assert.equal(out.disabled,true);
for(let i=0;i<12;i++)into.events.click();
assert.equal(canvas.style.transform,'scale(2)');assert.equal(into.disabled,true);
reset.events.click();assert.equal(canvas.style.transform,'scale(1)');
assert.equal(css(root,'rung-flow-zoom')[0].textContent,'100%');
assert.equal(boxes(root).length,1);
""")

    def test_invalid_or_incomplete_structure_falls_back_without_partial_graph(self) -> None:
        self.run_js(r"""
for(const data of [
  source(seq(inst('a'),{kind:'future_node'}),['a']),
  source(seq(inst('missing')),['a']),
  source(seq(inst('a')),['a','unused']),
  source(seq(inst('a'),inst('a')),['a']),
  source({kind:'branch',legs:[]},[]),
  source({kind:'sequence',items:null},[]),
  source(null,[]),
]) {
  const root=render(data);
  assert.equal(css(root,'rung-flow-fallback').length,1);
  assert.equal(boxes(root).length,0);
  assert.equal(coords(root).length,0);
  assert.ok(contents(root).includes(data.text));
  assert.ok(contents(root).includes('no partial connections are shown'));
}
""")

    def test_depth_count_cycle_and_canvas_limits_are_explicit(self) -> None:
        self.run_js(r"""
let deep=inst('a');for(let i=0;i<140;i++)deep=seq(deep);
const cycle=seq();cycle.items.push(cycle);
const many=Array.from({length:181},(_,i)=>'i'+i);
const wide=Array.from({length:150},(_,i)=>'i'+i);
for(const data of [source(deep,['a']),source(cycle,[]),
  source(seq(...many.map(inst)),many),source(seq(...wide.map(inst)),wide)]) {
  const root=render(data);
  assert.equal(css(root,'rung-flow-fallback').length,1);
  assert.ok(contents(root).includes(data.text));
  assert.equal(coords(root).length,0);
  assert.equal(boxes(root).length,0);
}
""")

    def test_renderer_uses_only_local_native_dom(self) -> None:
        for unsafe in ("innerHTML", "outerHTML", "insertAdjacentHTML", "fetch(", "eval("):
            self.assertNotIn(unsafe, SCRIPT)


if __name__ == "__main__":
    unittest.main()
