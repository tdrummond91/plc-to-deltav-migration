"""Execute offline access navigation against invented evidence in a tiny DOM.

Node is optional development tooling, not a parser or work-machine requirement.
These tests check rendered text, links and pagination; browser layout is reviewed
separately. The DOM implements only the APIs used by the bundled application.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest

from plc_workbench.access import analyze_access
from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from test_review import fixture
from test_review_html import ParsedPage


_NODE = shutil.which('node')
_DOM = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
class Element {
  constructor(tag) { this.tagName=tag.toUpperCase(); this.childNodes=[]; this.dataset={}; this.style={}; this.attributes={}; this.events={}; this.listeners={}; this._text=''; this.className=''; this.clientWidth=900; }
  set textContent(value) { this._text=String(value); this.childNodes=[]; }
  get textContent() { return this._text+this.childNodes.map(n=>n.textContent).join(''); }
  append(...nodes) { for(const value of nodes){if(value instanceof Element){value.parentNode=this;this.childNodes.push(value);}else {const n=new Element('#text');n.textContent=value;n.parentNode=this;this.childNodes.push(n);}} }
  replaceChildren(...nodes) { this.childNodes=[];this._text='';this.append(...nodes); }
  setAttribute(key,value) { this.attributes[key]=String(value); }
  getAttribute(key) { return this.attributes[key]??null; }
  hasAttribute(key) { return Object.hasOwn(this.attributes,key); }
  removeAttribute(key) { delete this.attributes[key]; }
  addEventListener(name,callback,capture=false) { (this.listeners[name]??=[]).push({callback,capture});this.events[name]=event=>{event={target:this,preventDefault(){},stopImmediatePropagation(){this.stopped=true;},...event};for(const item of [...this.listeners[name]].sort((a,b)=>Number(b.capture)-Number(a.capture))){item.callback(event);if(event.stopped)break;}}; }
  click() { assert.notEqual(this.disabled,true); this.events.click?.({target:this}); }
  focus() { document.activeElement=this; }
  select() {}
  matches(selector) { return selector.split(',').some(part=>{const s=part.trim();return s[0]==='.'?(this.attributes.class||this.className).split(' ').includes(s.slice(1)):s[0]==='['?this.hasAttribute(s.slice(1,-1))||(s.startsWith('[data-')&&Object.hasOwn(this.dataset,s.slice(6,-1))):this.tagName===s.toUpperCase();}); }
  querySelectorAll(selector) { return descendants(this).filter(n=>n.matches(selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  closest(selector) { return this.matches(selector)?this:this.parentNode?.closest(selector); }
  contains(node) { return node===this||descendants(this).includes(node); }
  remove() { if(this.parentNode)this.parentNode.childNodes=this.parentNode.childNodes.filter(n=>n!==this);this.parentNode=null; }
  get isConnected() { return page.contains(this); }
  getBoundingClientRect() { return {left:10,top:10,right:200,bottom:80,width:190,height:70}; }
  getClientRects() { return this.isConnected?[this.getBoundingClientRect()]:[]; }
  get classList() { return {add:(...names)=>{this.setAttribute('class',[...(this.attributes.class||this.className).split(' ').filter(Boolean),...names].join(' '));}}; }
}
function descendants(root) { return root.childNodes.flatMap(n=>[n,...descendants(n)]); }
global.Node=Element;
const page=new Element('body');
for(const id of ['review-data','page-heading','toolbar','content','main','navigation','snapshot-mini']){const n=new Element('div');n.id=id;page.append(n);}
global.document={createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),body:page,documentElement:new Element('html'),getElementById:id=>descendants(page).find(n=>n.id===id),querySelectorAll:s=>page.querySelectorAll(s),addEventListener:()=>{},activeElement:page};
global.window={scrollTo:()=>{},addEventListener:()=>{},innerWidth:1200,innerHeight:800};
global.MutationObserver=class {observe(){}};
document.getElementById('review-data').textContent=JSON.stringify(input.data);
vm.runInThisContext(input.script,{filename:'report.js'});
const content=document.getElementById('content');
const heading=document.getElementById('page-heading');
function navigate(view) { document.getElementById('navigation').childNodes.find(n=>n.dataset.view===view).click(); }
function clickText(scope,text) { const button=scope.querySelectorAll('button').find(n=>n.textContent===text);assert.ok(button,'Missing button: '+text);button.click(); }
function tableNamed(caption) { const t=content.querySelectorAll('table').find(n=>n.childNodes.some(c=>c.tagName==='CAPTION'&&c.textContent===caption));assert.ok(t,'Missing table: '+caption);return t; }
function rows(table) { return table.childNodes.find(n=>n.tagName==='TBODY').childNodes; }
function rowNamed(table,text) { const row=rows(table).find(n=>n.childNodes[0].textContent===text);assert.ok(row,'Missing row: '+text);return row; }
function texts(row) { return row.childNodes.map(n=>n.textContent); }
vm.runInThisContext(input.checks,{filename:'ui-checks.js'});
"""


def access_review(*, schema_version: int = 3, repeated: bool = False) -> dict:
    text = ('MSG(Alias.Control)GSV(Base,,Alias,Alias.Member)'
            'SSV(Base,,Alias,Alias.Member)SFR(Sequence,Alias.Step)'
            'SFR(Sequence,0)CTU(Counter,?,?)XIC(Base.Normal);')
    if repeated:
        text = ''.join('MSG(Alias.Control)' for _ in range(51)) + ';'
    args = fixture((text,), tags=(
        '<Tag Name="Base" TagType="Base" DataType="DINT"/>'
        '<Tag Name="Alias" TagType="Alias" AliasFor="Base[2]"/>'
        '<Tag Name="Counter" TagType="Base" DataType="COUNTER"/>'),
        sfc='<SFCContent><Step ID="1" Name="InventedStep"/></SFCContent>')
    access = analyze_access(args[1], args[2], schema_version=schema_version)
    return build_review_data(*args, access=access)


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI behavior checks.')
class AccessReviewUiTests(unittest.TestCase):
    def run_ui(self, data: dict, checks: str) -> None:
        parsed = ParsedPage(render_review_html(data))
        process = subprocess.run([_NODE, '-e', _DOM], input=json.dumps({
            'data': data, 'script': parsed.scripts[1][1], 'checks': checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_rung_separates_original_findings_from_new_bindings_and_selectors(self) -> None:
        self.run_ui(access_review(), r"""
        navigate('ladder');clickText(content,'Rung 0');
        assert.ok(content.textContent.includes('Original reference bindings'));
        const original=tableNamed('Rung operand bindings');
        assert.ok(texts(rowNamed(original,'Alias.Control'))[2].includes('unsupported instruction'));
        const extra=tableNamed('Rung instruction access bindings');
        const msg=rowNamed(extra,'Alias.Control');
        assert.equal(texts(msg)[2],'read write');
        assert.ok(texts(msg)[3].includes('root bound'));
        assert.equal(texts(msg)[5],'[2].Control');
        assert.deepEqual(msg.childNodes[4].querySelectorAll('button').map(n=>n.textContent),['Alias','Base']);
        const selector=rowNamed(extra,'Base');
        assert.equal(texts(selector)[2],'non data');
        assert.equal(selector.childNodes[4].querySelectorAll('button').length,0);
        assert.equal(texts(rowNamed(extra,'(blank)'))[2],'non data');
        assert.equal(texts(rowNamed(extra,'?'))[2],'initialization field');
        assert.equal(texts(rowNamed(extra,'0'))[2],'non data');
        assert.ok(!rows(extra).some(row=>texts(row)[0]==='Base.Normal'));
        clickText(msg,'Alias.Control');
        assert.ok(content.textContent.includes('original reference binding: unsupported instruction'));
        assert.ok(content.textContent.includes('instruction access binding: root bound'));
        """)

    def test_alias_and_target_backlinks_root_suffix_and_inherited_link_deduplication(self) -> None:
        self.run_ui(access_review(), r"""
        navigate('objects');clickText(tableNamed('Source objects'),'Alias');
        const alias=tableNamed('Object additional access occurrences');
        assert.deepEqual(rows(alias).map(n=>texts(n)[0]),['Alias.Control','Alias.Member','Alias.Member','Alias.Step']);
        clickText(rowNamed(alias,'Alias.Control'),'Base');
        assert.ok(heading.textContent.includes('Base'));
        const inherited=tableNamed('Object operand occurrences');
        assert.deepEqual(rows(inherited).map(n=>texts(n)[0]),['Base.Normal']);
        assert.equal(rows(tableNamed('Object additional access occurrences')).length,4);
        clickText(content,'Inspect root access occurrences');
        const root=tableNamed('Root access occurrences');
        const msg=rowNamed(root,'Alias.Control');
        assert.equal(texts(msg)[5],'[2].Control');
        assert.equal(texts(msg)[6],'Instruction access analysis');
        assert.deepEqual(msg.childNodes[4].querySelectorAll('button').map(n=>n.textContent),['Alias','Base']);
        assert.deepEqual(rowNamed(root,'Base.Normal').childNodes[4].querySelectorAll('button').map(n=>n.textContent),['Base']);
        clickText(msg,'Alias');
        assert.ok(heading.textContent.includes('Alias'));
        assert.equal(rows(tableNamed('Object additional access occurrences')).length,4);
        """)

    def test_access_coverage_and_original_finding_show_current_evidence(self) -> None:
        self.run_ui(access_review(), r"""
        navigate('access');
        for(const text of ['Classified counter instructions','Classified MSG control operands','Classified GSV instructions','Classified SSV instructions','Classified SFR target operands','Classified SFR initial-step selectors','MSG covers its control operand only; message payloads are not modeled.','SFC membership and wider reset effects are not validated.'])assert.ok(content.textContent.includes(text),text);
        navigate('findings');
        assert.ok(content.textContent.includes('Original reference findings are retained'));
        const finding=rows(tableNamed('Review findings')).find(r=>r.textContent.includes('Alias.Control'));
        assert.ok(finding);finding.querySelectorAll('button')[0].click();
        const current=tableNamed('Finding instruction access binding');
        assert.ok(texts(rowNamed(current,'Alias.Control'))[3].includes('root bound'));
        assert.ok(content.textContent.includes('This finding retains the original reference status.'));
        """)

    def test_additional_access_occurrences_keep_pagination_and_navigation(self) -> None:
        self.run_ui(access_review(repeated=True), r"""
        navigate('objects');clickText(tableNamed('Source objects'),'Alias');
        assert.equal(rows(tableNamed('Object additional access occurrences')).length,50);
        const next=content.querySelectorAll('button').find(n=>n.attributes['aria-label']==='Next page: Object additional access occurrences');
        next.click();
        assert.equal(rows(tableNamed('Object additional access occurrences')).length,1);
        clickText(tableNamed('Object additional access occurrences'),'Alias.Control');
        assert.ok(heading.textContent.includes('Rung 0'));
        assert.ok(content.textContent.includes('instruction access binding: root bound'));
        """)

    def test_legacy_access2_remains_navigable_without_overlay_metadata(self) -> None:
        self.run_ui(access_review(schema_version=2), r"""
        navigate('access');
        assert.ok(content.textContent.includes('Classified timer instructions'));
        assert.ok(!content.textContent.includes('Classified counter instructions'));
        navigate('objects');clickText(tableNamed('Source objects'),'Base');
        assert.ok(!content.textContent.includes('Additional instruction access occurrences'));
        clickText(content,'Inspect root access occurrences');
        const row=rowNamed(tableNamed('Root access occurrences'),'Base.Normal');
        assert.equal(texts(row)[5],'.Normal');
        assert.equal(texts(row)[6],'Original reference analysis');
        navigate('ladder');clickText(content,'Rung 0');
        assert.ok(content.textContent.includes('Operand bindings'));
        assert.ok(!content.textContent.includes('Instruction access bindings'));
        """)


if __name__ == '__main__':
    unittest.main()
