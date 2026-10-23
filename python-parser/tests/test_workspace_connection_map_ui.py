"""Production connection-map interactions against real synthetic index views."""
from __future__ import annotations

import json
import subprocess
import unittest

from test_relationships import capture
from test_workspace_connections import build
from test_workspace_ui import ASSETS, DOM, NODE


SCRIPT = (ASSETS / 'connections.js').read_text(encoding='utf-8')
MAP_DOM = r"""
const makeElement=tag=>{const n=node(tag);n.style={};n.isConnected=true;n.clientWidth=1200;return n;};
document.createElement=makeElement;
document.createElementNS=(namespace,tag)=>{const n=makeElement(tag);n.namespaceURI=namespace;return n;};
const requestAnimationFrame=callback=>callback();
const all=root=>[root,...descendants(root)];
const css=(root,name)=>all(root).filter(n=>(n.className||n.attributes.class||'').split(' ').includes(name));
const findButton=(root,text)=>all(root).find(n=>n.tagName==='button'&&n.textContent===text);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const clone=value=>JSON.parse(JSON.stringify(value));
const selectOf=(root,label)=>all(root).find(n=>n.tagName==='label'&&n.textContent===label).children.find(n=>n.tagName==='select');
const click=async node=>{assert.ok(node,'Expected actionable control');assert.equal(node.disabled,false);node.events.click();await flush();};
const changeSelect=async(node,value)=>{node.value=value;node.events.change();await flush();};
const defer=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
"""


def fixture() -> dict:
    inputs = capture(('MOV(A,B)ADD(B,1,B);', *('XIC(B)OTE(C);' for _ in range(9)), 'MOV(C,B);'))
    index = build(inputs)
    focus = inputs[1].rungs[0].id
    neighbor = inputs[1].rungs[1].id
    view = index.view(focus)
    signal = next(row['id'] for row in view['signals'] if row['label'] == 'B')
    return {'all': view, 'focused': index.view(focus, signal_id=signal),
            'page2': index.view(focus, signal_id=signal, endpoint_page=2),
            'neighbor': index.view(neighbor), 'signal_id': signal, 'focus_id': focus,
            'neighbor_id': neighbor}


@unittest.skipUnless(NODE, 'Node is optional developer tooling')
class WorkspaceConnectionMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = fixture()

    def run_js(self, checks: str, payload: object = None) -> None:
        code = DOM + MAP_DOM + SCRIPT + '\nconst data=' + json.dumps(self.data if payload is None else payload) + ';\n'
        code += '\n(async()=>{\n' + checks + '\n})().catch(error=>{console.error(error);process.exitCode=1;});'
        result = subprocess.run([NODE, '-'], input=code, capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_signal_expansion_sends_actual_api_key_and_clears_back_to_all(self) -> None:
        self.run_js(r"""
const calls=[];
const root=window.PLCConnections.render({rungId:data.focus_id,
  load:async query=>{calls.push({...query});return clone(query.signal_id?data.focused:data.all);},openRung:()=>{}});
await flush();
assert.equal(root.attributes['aria-busy'],'false');
assert.equal(css(root,'connection-focus').length,1);
assert.ok(css(root,'connection-wire').length);
await click(findButton(root,'B'));
assert.equal(calls.at(-1).signal_id,data.signal_id);
assert.equal(Object.hasOwn(calls.at(-1),'signal'),false,'HTTP API expects signal_id');
assert.ok(findButton(root,'Show all signals'));
assert.equal(css(root,'connection-rung').filter(n=>n.dataset.rungId!==data.all.signals.find(s=>s.label==='B').writers[0].id).length,8);
await click(findButton(root,'Show all signals'));
assert.equal(calls.at(-1).signal_id,'');
assert.equal(findButton(root,'Show all signals'),undefined);
""")

    def test_graph_page_sizes_preserve_focus_direction_and_expanded_signal(self) -> None:
        self.run_js(r"""
const calls=[];
const root=window.PLCConnections.render({rungId:data.focus_id,
  load:async query=>{calls.push({...query});return clone(query.signal_id?data.focused:data.all);},openRung:()=>{}});
await flush();await changeSelect(selectOf(root,'Connections'),'outputs');
await changeSelect(selectOf(root,'Signals per page'),'50');
assert.equal(calls.at(-1).page_size,50);assert.equal(calls.at(-1).page,1);assert.equal(calls.at(-1).direction,'outputs');
await click(findButton(root,'B'));await changeSelect(selectOf(root,'Connected rungs per page'),'25');
assert.equal(calls.at(-1).signal_id,data.signal_id);assert.equal(calls.at(-1).id,data.focus_id);
assert.equal(calls.at(-1).endpoint_page_size,25);assert.equal(calls.at(-1).endpoint_page,1);
""")

    def test_neighbor_refocus_back_and_open_focused_rung_preserve_navigation(self) -> None:
        self.run_js(r"""
const calls=[],focuses=[],opened=[];
const root=window.PLCConnections.render({rungId:data.focus_id,onFocus:id=>focuses.push(id),openRung:id=>opened.push(id),
  load:async query=>{calls.push({...query});return clone(query.id===data.neighbor_id?data.neighbor:query.signal_id?data.focused:data.all);}});
await flush();
await click(findButton(root,'B'));
await click(css(root,'connection-rung').find(n=>n.dataset.rungId===data.neighbor_id));
assert.equal(calls.at(-1).id,data.neighbor_id);
assert.equal(calls.at(-1).signal_id,'');
assert.deepEqual(focuses,[data.neighbor_id]);
await click(findButton(root,'Open focused rung'));
assert.deepEqual(opened,[data.neighbor_id]);
await click(all(root).find(n=>n.tagName==='button'&&n.textContent.includes('Back in trace')));
assert.equal(calls.at(-1).id,data.focus_id);
assert.equal(calls.at(-1).signal_id,data.signal_id,'Back restores expanded signal');
assert.equal(focuses.at(-1),data.focus_id);
assert.equal(all(root).find(n=>n.tagName==='button'&&n.textContent.includes('Back in trace')).disabled,true);
""")

    def test_scope_direction_and_endpoint_paging_reset_only_expected_filters(self) -> None:
        self.run_js(r"""
const calls=[];
const root=window.PLCConnections.render({rungId:data.focus_id,openRung:()=>{},
  load:async query=>{calls.push({...query});return clone(query.signal_id?(query.endpoint_page===2?data.page2:data.focused):data.all);}});
await flush();
await click(findButton(root,'B'));
await click(findButton(root,'Next connected rungs'));
assert.equal(calls.at(-1).endpoint_page,2);
assert.equal(calls.at(-1).signal_id,data.signal_id);
assert.equal(findButton(root,'Next connected rungs').disabled,true);
assert.ok(contents(root).includes('No writers on this page'));
assert.equal(contents(root).includes('No other explicit writer rung recorded'),false);
await changeSelect(selectOf(root,'Scope'),'routine');
assert.equal(calls.at(-1).scope,'routine');
assert.equal(calls.at(-1).endpoint_page,1);
assert.equal(calls.at(-1).signal_id,'');
await changeSelect(selectOf(root,'Connections'),'outputs');
assert.equal(calls.at(-1).direction,'outputs');
assert.equal(calls.at(-1).scope,'routine');
""")

    def test_unknown_role_is_visible_without_directed_signal_line(self) -> None:
        inputs = capture(('PID(A,B,C,D,0,0,0);', 'OTE(A);'))
        payload = build(inputs).view(inputs[1].rungs[0].id)
        self.run_js(r"""
const root=window.PLCConnections.render({rungId:data.focus.id,load:async()=>clone(data),openRung:()=>{}});
await flush();
assert.equal(css(root,'connection-signal').length,0);
assert.equal(css(root,'connection-wire').length,0);
assert.equal(css(root,'connection-focus').length,1);
assert.ok(contents(root).includes('input/output role is unresolved'));
assert.ok(contents(root).includes('unknown roles: 7'));
assert.equal(contents(root).includes('No exact-address connections are recorded'),false);
assert.equal(css(root,'connection-signal-detail').length,4);
""", payload)

    def test_unavailable_then_retry_and_transport_failure_never_claim_no_connections(self) -> None:
        self.run_js(r"""
let calls=0;
const root=window.PLCConnections.render({rungId:data.focus_id,openRung:()=>{},load:async()=>{
  calls++;if(calls===1)return {available:false,notice:'Saved evidence unavailable; original source remains.'};
  if(calls===2)throw new Error('PRIVATE_EXCEPTION');return clone(data.all);
}});
await flush();
assert.ok(contents(root).includes('Saved evidence unavailable'));
assert.equal(css(root,'connection-canvas').length,0);
assert.equal(contents(root).includes('No exact-address connections'),false);
await click(findButton(root,'Retry'));
assert.ok(contents(root).includes('could not load'));
assert.equal(contents(root).includes('PRIVATE_EXCEPTION'),false);
assert.equal(root.attributes['aria-busy'],'false');
await click(findButton(root,'Retry'));
assert.equal(css(root,'connection-focus').length,1);
""")

    def test_source_labels_are_text_and_ids_do_not_become_markup(self) -> None:
        self.run_js(r"""
const payload=clone(data.all),hostile='<img src=x onerror=alert(1)> & <script>bad()</script>';
payload.focus.path=hostile;
payload.signals[0].label=hostile;payload.signals[0].target_path=hostile;
payload.signals[1].readers[0].path=hostile;
const root=window.PLCConnections.render({rungId:data.focus_id,openRung:()=>{},load:async()=>payload});
await flush();
assert.ok(contents(root).includes(hostile));
assert.equal(all(root).some(n=>['img','script'].includes(n.tagName)),false);
assert.equal(all(root).some(n=>Object.hasOwn(n.attributes,'onclick')),false);
""")

    def test_counts_use_actual_totals_and_legacy_calculation_gap_is_visible(self) -> None:
        self.run_js(r"""
const payload=clone(data.focused),same=payload.signals[0].same_rung;
same.reads=101;same.writes=52;same.unknown=7;
same.read_use_ids=['preview'];same.write_use_ids=['preview'];same.unknown_use_ids=[];
payload.coverage.calculation_reads_available=false;
const root=window.PLCConnections.render({rungId:data.focus_id,openRung:()=>{},load:async()=>payload});
await flush();
assert.ok(contents(root).includes('101 read uses'));
assert.ok(contents(root).includes('52 write uses'));
assert.ok(contents(root).includes('7 uses with an unknown role'));
assert.ok(contents(root).includes('no calculation-expression input connections'));
""")

    def test_late_responses_and_errors_cannot_replace_newer_focus(self) -> None:
        self.run_js(r"""
let calls=0;const old=defer(),latest=defer();
const root=window.PLCConnections.render({rungId:data.focus_id,openRung:()=>{},load:query=>{
 calls++;if(calls===1)return Promise.resolve(clone(data.all));return calls===2?old.promise:latest.promise;
}});
await flush();
const scope=selectOf(root,'Scope'),direction=selectOf(root,'Connections');
scope.value='routine';scope.events.change();
assert.equal(css(root,'connection-canvas').length,0,'Pending load clears stale controls');
direction.value='inputs';direction.events.change();
const newest=clone(data.focused);newest.focus.path='NEWEST RESULT';latest.resolve(newest);await flush();
assert.ok(contents(root).includes('NEWEST RESULT'));
old.reject(new Error('OLD FAILURE'));await flush();
assert.ok(contents(root).includes('NEWEST RESULT'));
assert.equal(contents(root).includes('could not load'),false);
assert.equal(root.attributes['aria-busy'],'false');
""")

    def test_zoom_and_fit_change_canvas_scale_without_new_data_requests(self) -> None:
        self.run_js(r"""
let calls=0;
const root=window.PLCConnections.render({rungId:data.focus_id,openRung:()=>{},load:async()=>{calls++;return clone(data.all);}});
await flush();
const canvas=css(root,'connection-canvas')[0];
await click(findButton(root,'100%'));
assert.equal(canvas.style.transform,'scale(1)');
await click(findButton(root,'Zoom out'));
assert.equal(canvas.style.transform,'scale(0.85)');
await click(findButton(root,'Fit width'));
assert.ok(Number(canvas.style.transform.match(/[\d.]+/)[0])<1);
assert.equal(calls,1);
""")

    def test_late_success_does_not_restore_superseded_selection(self) -> None:
        self.run_js(r"""
let calls=0;const old=defer(),latest=defer();
const root=window.PLCConnections.render({rungId:data.focus_id,openRung:()=>{},load:query=>{
 calls++;if(calls===1)return Promise.resolve(clone(data.all));return calls===2?old.promise:latest.promise;
}});
await flush();
const scope=selectOf(root,'Scope'),direction=selectOf(root,'Connections');
scope.value='routine';scope.events.change();
direction.value='inputs';direction.events.change();
const newest=clone(data.focused);newest.focus.path='LATEST SCOPE';latest.resolve(newest);await flush();
const stale=clone(data.all);stale.focus.path='STALE SCOPE';old.resolve(stale);await flush();
assert.ok(contents(root).includes('LATEST SCOPE'));
assert.equal(contents(root).includes('STALE SCOPE'),false);
assert.equal(selectOf(root,'Scope').value,'routine');
assert.equal(selectOf(root,'Connections').value,'inputs');
""")

    def test_direction_filter_draws_only_selected_side_of_read_write_signal(self) -> None:
        inputs = capture(('ONS(A);', 'OTE(A);', 'XIC(A)OTE(B);'))
        index = build(inputs)
        focus = inputs[1].rungs[0].id
        payload = {'focus_id': focus, 'views': {
            direction: index.view(focus, direction=direction)
            for direction in ('both', 'inputs', 'outputs')
        }}
        self.run_js(r"""
for(const view of Object.values(data.views)) {
  assert.equal(view.signals.length,1);
  assert.equal(view.signals[0].input,true);
  assert.equal(view.signals[0].output,true,'Backend retains full source roles under direction filters');
}
const calls=[];
const root=window.PLCConnections.render({rungId:data.focus_id,openRung:()=>{},load:async query=>{
  calls.push({...query});return clone(data.views[query.direction]);
}});
await flush();
assert.equal(css(root,'connection-signal').length,2);
assert.ok(css(root,'connection-wire').some(n=>n.attributes.class.includes('input')));
assert.ok(css(root,'connection-wire').some(n=>n.attributes.class.includes('output')));
await changeSelect(selectOf(root,'Connections'),'inputs');
assert.equal(calls.at(-1).direction,'inputs');
assert.equal(css(root,'connection-signal').length,1);
assert.equal(css(root,'connection-signal')[0].style.left,'310px');
assert.ok(css(root,'connection-wire').length);
assert.equal(css(root,'connection-wire').some(n=>n.attributes.class.includes('output')),false);
await changeSelect(selectOf(root,'Connections'),'outputs');
assert.equal(calls.at(-1).direction,'outputs');
assert.equal(css(root,'connection-signal').length,1);
assert.equal(css(root,'connection-signal')[0].style.left,'960px');
assert.ok(css(root,'connection-wire').length);
assert.equal(css(root,'connection-wire').some(n=>n.attributes.class.includes('input')),false);
""", payload)

    def test_unavailable_and_transport_error_offer_choose_rung_recovery(self) -> None:
        self.run_js(r"""
for(const fails of [false,true]) {
  let chosen=0;
  const root=window.PLCConnections.render({rungId:data.focus_id,openRung:()=>{},
    chooseRung:()=>{chosen++;},load:async()=>{
      if(fails)throw new Error('unavailable transport');
      return {available:false,notice:'Saved connection evidence is unavailable.'};
    }});
  await flush();
  assert.ok(findButton(root,'Retry'));
  await click(findButton(root,'Choose another rung'));
  assert.equal(chosen,1);
  assert.equal(css(root,'connection-canvas').length,0);
}
""")

    def test_unknown_focus_keeps_known_writer_and_reader_navigable_without_arrows(self) -> None:
        inputs = capture(('PID(A,B,C,D,0,0,0);', 'OTE(A);', 'XIC(A)OTE(B);'))
        index = build(inputs)
        focus, writer, reader = [rung.id for rung in inputs[1].rungs]
        view = index.view(focus)
        signal = next(row['id'] for row in view['signals'] if row['label'] == 'A')
        payload = {'view': view, 'filtered': index.view(focus, signal_id=signal),
                   'writer': index.view(writer), 'reader': index.view(reader),
                   'focus_id': focus, 'writer_id': writer, 'reader_id': reader, 'signal_id': signal}
        self.run_js(r"""
const calls=[],focuses=[];
const root=window.PLCConnections.render({rungId:data.focus_id,openRung:()=>{},onFocus:id=>focuses.push(id),
  load:async query=>{calls.push({...query});return clone(query.id===data.writer_id?data.writer:
    query.id===data.reader_id?data.reader:query.signal_id?data.filtered:data.view);}});
await flush();
assert.equal(css(root,'connection-wire').length,0);
let item=css(root,'connection-signal-detail').find(n=>n.children[0].textContent.startsWith('A '));
assert.ok(item.open,'Unknown-role details are expanded');
let known=css(item,'connection-evidence-endpoint');
assert.equal(known.length,2);
assert.ok(known.some(n=>n.textContent.startsWith('Writer ')));
assert.ok(known.some(n=>n.textContent.startsWith('Reader ')));
await click(findButton(item,'Focus this signal'));
assert.equal(calls.at(-1).signal_id,data.signal_id);
assert.equal(css(root,'connection-wire').length,0,'Signal focus must not invent the unknown rung role');
item=css(root,'connection-signal-detail')[0];
await click(css(item,'connection-evidence-endpoint').find(n=>n.textContent.startsWith('Writer ')));
assert.equal(calls.at(-1).id,data.writer_id);
assert.equal(focuses.at(-1),data.writer_id);
await click(all(root).find(n=>n.tagName==='button'&&n.textContent.includes('Back in trace')));
assert.equal(calls.at(-1).id,data.focus_id);
assert.equal(calls.at(-1).signal_id,data.signal_id);
await click(css(root,'connection-evidence-endpoint').find(n=>n.textContent.startsWith('Reader ')));
assert.equal(calls.at(-1).id,data.reader_id);
assert.equal(focuses.at(-1),data.reader_id);
""", payload)

    def test_competing_writer_of_output_remains_reachable_in_signal_details(self) -> None:
        inputs = capture(('OTE(A);', 'OTL(A);', 'XIC(A)OTE(B);'))
        index = build(inputs)
        focus, writer = [rung.id for rung in inputs[1].rungs[:2]]
        payload = {'view': index.view(focus), 'writer': index.view(writer),
                   'focus_id': focus, 'writer_id': writer}
        self.run_js(r"""
const calls=[];
assert.equal(data.view.signals[0].output,true);
assert.equal(data.view.signals[0].input,false);
assert.equal(data.view.signals[0].counts.multiple_writers,true);
const root=window.PLCConnections.render({rungId:data.focus_id,openRung:()=>{},load:async query=>{
  calls.push({...query});return clone(query.id===data.writer_id?data.writer:data.view);
}});
await flush();
assert.ok(css(root,'connection-wire').length);
assert.equal(css(root,'connection-wire').some(n=>n.attributes.class.includes('input')),false);
assert.equal(css(root,'connection-rung').some(n=>n.dataset.rungId===data.writer_id),false,
  'Competing writer has no false input-side diagram edge');
const competing=css(root,'connection-evidence-endpoint').find(n=>n.textContent.startsWith('Writer '));
assert.ok(competing,'Competing writer must remain discoverable in signal details');
await click(competing);
assert.equal(calls.at(-1).id,data.writer_id);
""", payload)


if __name__ == '__main__':
    unittest.main()
