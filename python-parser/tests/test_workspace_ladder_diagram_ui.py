"""Conventional symbols and exact source-path geometry using invented rungs."""
from __future__ import annotations

from dataclasses import asdict
import json
import subprocess
import unittest

from test_calculations import capture
from test_workspace_ui import ASSETS, NODE


SCRIPT = (ASSETS / "ladder-diagram.js").read_text(encoding="utf-8")
DOM = r"""
const assert=require('node:assert/strict');
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.events={};this.attributes={};this.style={};this.className='';this._text='';this.hidden=false;this.disabled=false;this.clientWidth=700;}
 set textContent(text){this._text=String(text);this.children=[];}
 get textContent(){return this._text+this.children.map(child=>child.textContent).join(' ');}
 append(...children){children.forEach(child=>{child.parent=this;this.children.push(child);});}
 replaceChildren(...children){this.children=[];this._text='';this.append(...children);}
 setAttribute(name,value){this.attributes[name]=String(value);}
 addEventListener(name,fn){this.events[name]=fn;}
 fire(name,values={}){if(name==='click'&&this.disabled)return;return this.events[name]?.({type:name,target:this,preventDefault(){},...values});}
}
const document={createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag)},window={};
const all=root=>[root,...root.children.flatMap(all)];
const cls=(root,name)=>all(root).filter(node=>(node.attributes.class||node.className||'').split(' ').includes(name));
const button=(root,text)=>all(root).find(node=>node.tagName==='button'&&node.textContent===text);
const ins=id=>({kind:'instruction',instruction_id:id}),seq=(...items)=>({kind:'sequence',items}),branch=(...legs)=>({kind:'branch',legs});
const instruction=(id,opcode='XIC',args=['Invented_'+id])=>({id,opcode,arguments:args});
const source=(structure,instructions)=>({parse_status:'parsed',structure,instructions,text:instructions.map(item=>item.opcode+'('+item.arguments.join(',')+')').join('')+';'});
const render=(data,options={})=>window.PLCLadderDiagram.render(data,{sourceQualified:true,...options});
const cards=root=>cls(root,'ladder-diagram-instruction');
const wires=root=>cls(root,'ladder-diagram-wire').map(node=>({kind:node.attributes['data-wire'],v:node.attributes.d.match(/-?\d+(?:\.\d+)?/g).map(Number)}));
const boxes=root=>cards(root).map(node=>{const [x,y]=node.attributes.transform.match(/-?\d+(?:\.\d+)?/g).map(Number);return {id:node.attributes['data-instruction-id'],x,y,width:Number(node.attributes['data-width']),height:Number(node.attributes['data-height'])};});
const pointOn=(x,y,line)=>{const[a,b,c,d]=line.v;return x>=Math.min(a,c)&&x<=Math.max(a,c)&&y>=Math.min(b,d)&&y<=Math.max(b,d);};
function geometry(root){
 const bs=boxes(root),ws=wires(root);assert.ok(bs.length);assert.ok(ws.length);
 for(const box of bs){
  assert.ok(ws.some(line=>pointOn(box.x,box.y+84,line)),box.id+' inlet');
  assert.ok(ws.some(line=>pointOn(box.x+box.width,box.y+84,line)),box.id+' outlet');
  for(const line of ws){const[x1,y1,x2,y2]=line.v;assert.ok(x1===x2||y1===y2);
   if(y1===y2&&y1>box.y&&y1<box.y+box.height)assert.ok(Math.max(x1,x2)<=box.x||Math.min(x1,x2)>=box.x+box.width,line.kind+' crosses '+box.id);
   if(x1===x2&&x1>box.x&&x1<box.x+box.width)assert.ok(Math.max(y1,y2)<=box.y||Math.min(y1,y2)>=box.y+box.height,line.kind+' crosses '+box.id);
  }
  for(const other of bs.filter(item=>item.id!==box.id))assert.ok(box.x+box.width<=other.x||other.x+other.width<=box.x||box.y+box.height<=other.y||other.y+other.height<=box.y,box.id+' overlaps '+other.id);
 }
}
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return{promise,resolve,reject};};
async function tick(){for(let n=0;n<8;n++)await Promise.resolve();}
"""


@unittest.skipUnless(NODE, "Node is optional developer tooling")
class LadderDiagramUiTests(unittest.TestCase):
    def run_js(self, checks: str, data: object = None) -> None:
        code = DOM + SCRIPT + "\nconst data=" + json.dumps(data) + ";\n(async()=>{\n" + checks
        code += "\n})().then(()=>process.stdout.write('DIAGRAM_OK\\n')).catch(error=>{console.error(error);process.exitCode=1;});"
        result = subprocess.run([NODE, "-"], input=code, capture_output=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DIAGRAM_OK", result.stdout)

    def test_real_nested_source_preserves_all_blocks_joins_and_empty_bypass(self) -> None:
        _, inventory, _, _ = capture("A+B", text="XIC(Enable)[ADD(A,B,C),XIO(Inhibit)[TON(Timer,100,0),]]OTE(Output);")
        self.run_js(r"""
const root=render(data);geometry(root);
assert.deepEqual(cards(root).map(node=>node.attributes['data-instruction-id']),data.instructions.map(row=>row.id));
assert.deepEqual(cards(root).map(node=>node.attributes['data-source-position']),['1','2','3','4','5']);
assert.equal(wires(root).filter(line=>line.kind==='split').length,2);assert.equal(wires(root).filter(line=>line.kind==='join').length,2);
assert.equal(wires(root).filter(line=>line.kind==='bypass').length,1);assert.ok(root.textContent.includes('Empty bypass'));
assert.equal(cls(root,'ladder-diagram-fallback').length,0);assert.ok(root.textContent.includes(data.text));
assert.ok(root.textContent.includes('no live states'));assert.equal(all(root).filter(node=>node.attributes['marker-end']).length,0);
""", asdict(inventory.rungs[0]))

    def test_top_path_alignment_and_nested_branches_are_connected(self) -> None:
        self.run_js(r"""
const data=source(seq(ins('a'),branch(seq(ins('b'),branch(seq(),seq(ins('c')))),seq(ins('d'),ins('e'))),ins('f')),['a','b','c','d','e','f'].map(id=>instruction(id)));
const root=render(data);geometry(root);const bs=Object.fromEntries(boxes(root).map(box=>[box.id,box]));
assert.equal(bs.a.y,bs.b.y);assert.equal(bs.a.y,bs.f.y);assert.ok(bs.c.y>bs.b.y);assert.ok(bs.d.y>bs.c.y);assert.equal(bs.d.y,bs.e.y);
assert.ok(bs.b.x>bs.a.x);assert.ok(bs.f.x>bs.e.x);
const ws=wires(root),splits=ws.filter(line=>line.kind==='split'),joins=ws.filter(line=>line.kind==='join');
for(const line of ws.filter(line=>line.kind==='branch-entry'))assert.ok(splits.some(bus=>pointOn(line.v[0],line.v[1],bus)));
for(const line of ws.filter(line=>line.kind==='branch-exit'))assert.ok(joins.some(bus=>pointOn(line.v[2],line.v[3],bus)));
""")

    def test_conventional_contacts_and_coils_preserve_operand_and_latch_letters(self) -> None:
        self.run_js(r"""
const opcodes=['XIC','XIO','OTE','OTL','OTU'];const rows=opcodes.map((opcode,index)=>instruction('i'+index,opcode,['Address_'+index]));
const root=render(source(seq(...rows.map(row=>ins(row.id))),rows));geometry(root);
assert.deepEqual(cards(root).map(node=>node.attributes['data-symbol']),['contact','negated-contact','coil','latch-coil','unlatch-coil']);
assert.equal(cls(root,'ladder-diagram-negation').length,1);assert.equal(cls(root,'ladder-diagram-contact').length,4);assert.equal(cls(root,'ladder-diagram-coil').length,6);
assert.deepEqual(cls(root,'ladder-diagram-coil-letter').map(node=>node.textContent),['L','U']);
for(const row of rows)assert.ok(all(root).some(node=>node.tagName==='title'&&node.textContent===row.opcode+'('+row.arguments[0]+')'));
""")

    def test_unknown_and_arity_invalid_opcodes_keep_generic_blocks_and_complete_arguments(self) -> None:
        self.run_js(r"""
const rows=[instruction('a','XIC',[]),instruction('b','XIO',['One','Two']),instruction('c','OTL',['']),instruction('d','Mixer_AOI',['In','Out','Timer','Long parameter value','<script>literal</script>'])];
const root=render(source(seq(...rows.map(row=>ins(row.id))),rows));geometry(root);
assert.deepEqual(cards(root).map(node=>node.attributes['data-symbol']),['block','block','block','block']);assert.equal(cls(root,'ladder-diagram-negation').length,0);
await cards(root)[3].fire('click');assert.ok(cls(root,'ladder-diagram-selected')[0].textContent.includes('Long parameter value'));assert.ok(cls(root,'ladder-diagram-selected')[0].textContent.includes('<script>literal</script>'));
assert.equal(all(root).filter(node=>node.tagName==='script').length,0);assert.ok(root.textContent.includes('+ 3 more arguments'));assert.ok(root.textContent.includes("does not infer the block's effects"));
""")

    def test_qualification_and_parse_failures_show_full_original_without_partial_graph(self) -> None:
        self.run_js(r"""
const data=source(seq(ins('one')),[instruction('one')]);
for(const root of [window.PLCLadderDiagram.render(data),render(data,{sourceQualified:false}),render({...data,source_qualified:false}),render({...data,parse_status:'partial'}),render({...data,parse_status:'unparsed'})]){
 assert.equal(cls(root,'ladder-diagram-fallback').length,1);assert.equal(cards(root).length,0);assert.equal(wires(root).length,0);
 assert.ok(root.textContent.includes(data.text));assert.ok(root.textContent.includes('no partial ladder'));assert.equal(cls(root,'ladder-diagram-original')[0].open,true);
}
""")

    def test_incomplete_repeated_reordered_and_cyclic_trees_fall_back(self) -> None:
        self.run_js(r"""
const rows=[instruction('a'),instruction('b')],cycle=seq();cycle.items.push(cycle);
for(const tree of [seq(ins('a')),seq(ins('a'),ins('a')),seq(ins('b'),ins('a')),seq(ins('a'),ins('missing')),branch(),branch(ins('a')),seq({kind:'future'}),cycle]){
 const data=source(tree,rows),root=render(data);assert.equal(cls(root,'ladder-diagram-fallback').length,1);assert.equal(cards(root).length,0);assert.ok(root.textContent.includes(data.text));
}
const duplicate=source(seq(ins('a'),ins('a')),[instruction('a'),instruction('a')]);assert.equal(cls(render(duplicate),'ladder-diagram-fallback').length,1);
""")

    def test_limits_retain_complete_original_and_never_drop_excess_instructions(self) -> None:
        self.run_js(r"""
const tooMany=Array.from({length:161},(_,i)=>instruction('i'+i)),wide=Array.from({length:160},(_,i)=>instruction('w'+i,'Generic',['A','B','C']));
let deep=ins('a');for(let i=0;i<70;i++)deep=seq(deep);
const oversizedLabel=instruction('long','AOI',['x'.repeat(131073)]),oversizedArgs=instruction('slots','AOI',Array(129).fill('A'));
for(const data of [source(seq(...tooMany.map(row=>ins(row.id))),tooMany),source(seq(...wide.map(row=>ins(row.id))),wide),source(deep,[instruction('a')]),source(seq(ins('long')),[oversizedLabel]),source(seq(ins('slots')),[oversizedArgs]),source(branch(...Array.from({length:1201},()=>seq())),[])]){
 const root=render(data);assert.equal(cards(root).length,0);assert.equal(wires(root).length,0);assert.equal(cls(root,'ladder-diagram-fallback').length,1);assert.ok(root.textContent.includes(data.text));
}
""")

    def test_empty_rung_and_empty_branch_path_remain_explicit(self) -> None:
        self.run_js(r"""
const root=render(source(seq(),[]));assert.equal(cls(root,'ladder-diagram-fallback').length,0);assert.equal(cards(root).length,0);assert.equal(wires(root).filter(line=>line.kind==='bypass').length,1);
const withBypass=render(source(seq(branch(seq(),seq(ins('a'))),ins('b')),[instruction('a'),instruction('b','OTE')]));geometry(withBypass);assert.equal(wires(withBypass).filter(line=>line.kind==='bypass').length,1);
""")

    def test_pointer_keyboard_callbacks_decline_and_errors_preserve_selection(self) -> None:
        self.run_js(r"""
const seen=[];let accept=true,fail=false;
const data=source(seq(ins('a'),ins('b')),[instruction('a'),instruction('b','OTE')]);
const root=render(data,{onInstruction:async instruction=>{seen.push(instruction);if(fail)throw new Error('Source unavailable');return accept;}});
await cards(root)[0].fire('click');assert.equal(seen[0],data.instructions[0]);assert.equal(cards(root)[0].attributes['aria-pressed'],'true');
accept=false;cards(root)[1].fire('keydown',{key:'Enter'});await tick();assert.equal(seen[1],data.instructions[1]);assert.equal(cards(root)[0].attributes['aria-pressed'],'true');assert.equal(cards(root)[1].attributes['aria-pressed'],'false');
accept=true;fail=true;cards(root)[1].fire('keydown',{key:' '});await tick();assert.ok(!cls(root,'ladder-diagram-error')[0].hidden);assert.ok(root.textContent.includes('Source unavailable'));
fail=false;await button(root,'Retry instruction').fire('click');assert.equal(cards(root)[1].attributes['aria-pressed'],'true');assert.ok(cls(root,'ladder-diagram-error')[0].hidden);
""")

    def test_late_callback_failure_cannot_replace_newer_selection(self) -> None:
        self.run_js(r"""
const slow=deferred(),root=render(source(seq(ins('a'),ins('b')),[instruction('a'),instruction('b')]),{onInstruction:row=>row.id==='a'?slow.promise:Promise.resolve(true)});
const old=cards(root)[0].fire('click');await cards(root)[1].fire('click');slow.reject(new Error('Old error'));await old;
assert.ok(cls(root,'ladder-diagram-error')[0].hidden);assert.equal(cards(root)[1].attributes['aria-pressed'],'true');
""")

    def test_zoom_and_fit_change_scroll_dimensions_without_dropping_symbols(self) -> None:
        self.run_js(r"""
const rows=Array.from({length:40},(_,i)=>instruction('i'+i)),root=render(source(seq(...rows.map(row=>ins(row.id))),rows));
const canvas=cls(root,'ladder-diagram-canvas')[0],viewBox=canvas.attributes.viewBox,viewport=cls(root,'ladder-diagram-viewport')[0];
const initial=Number(canvas.attributes.width);button(root,'Zoom out').fire('click');assert.ok(Number(canvas.attributes.width)<initial);assert.equal(canvas.attributes.viewBox,viewBox);
button(root,'Reset zoom').fire('click');assert.equal(Number(canvas.attributes.width),initial);
viewport.clientWidth=380;button(root,'Fit width').fire('click');assert.ok(Number(canvas.attributes.width)<=360.0001);assert.equal(cards(root).length,40);
for(let i=0;i<20;i++)button(root,'Zoom in').fire('click');assert.equal(Number(canvas.attributes.width),initial*2);assert.ok(button(root,'Zoom in').disabled);
viewport.fire('keydown',{key:'0'});assert.equal(Number(canvas.attributes.width),initial);
""")
