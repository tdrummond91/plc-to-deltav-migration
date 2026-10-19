"""Development-only operation notes keep source and Boolean gaps visible."""
from __future__ import annotations

from functools import lru_cache
import json
import subprocess
import unittest

from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from plc_workbench.source_reuse import source_reuse_scope
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_residual_diagnostics_workflow import SOURCE, captured, options
from test_review_html import ParsedPage


@lru_cache(maxsize=2)
def report(*, historical: bool = False) -> dict:
    source = SOURCE.replace(
        b'JSR(Sub,0)JSR(Sub,Raw,Command);',
        b'JSR(Sub,0)JSR(Sub,Raw,Command)JSR(MissingTarget,0)'
        b'SFR(Chart,Step)SFR(Chart,Permit)SFR(Chart,0);',
    ).replace(b'SBR(Raw)MOV(Raw,Outgoing[0]);', b'SBR(Raw)OTE(Command);')
    capture, select = captured, options
    if historical:
        from test_residual_interpretation_workflow import captured as capture, options as select
    with source_reuse_scope():
        parts = capture(source)
        return build_review_data(*parts[:4], **select(parts))


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI checks.')
class ControlOperationUiTests(unittest.TestCase):
    def run_ui(self, checks: str, *, historical: bool = False) -> None:
        data = report(historical=historical)
        script = ParsedPage(render_review_html(data)).scripts[1][1]
        marker = "const data = JSON.parse(document.getElementById('review-data').textContent);"
        script = script.replace(marker, marker +
            'globalThis.savedData=data;globalThis.savedBefore=JSON.stringify(data);', 1)
        result = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': data, 'script': script, 'checks': checks +
            'assert.equal(JSON.stringify(savedData),savedBefore);'}), text=True,
            encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_jsr_operation_preserves_missing_target_and_raw_parameter_evidence(self) -> None:
        self.run_ui(r"""
        navigate('executioncontext');
        const calls=rows(tableNamed('Execution routine calls'));
        const missing=calls.find(r=>r.textContent.includes('MissingTarget'));
        missing.querySelector('button').click();
        assert.ok(content.textContent.includes('Documented instruction operation'));
        assert.ok(content.textContent.includes('If that invocation returns normally'));
        assert.ok(content.textContent.includes('missing candidate'));
        assert.ok(content.textContent.includes('does not establish parameter mapping'));
        assert.ok(tableNamed('Execution captured arguments').textContent.includes('MissingTarget'));
        assert.ok(content.textContent.includes('Incoming condition evidence'));
        """)

    def test_sbr_and_empty_ret_keep_distinct_unresolved_control_semantics(self) -> None:
        data = report()
        self.assertEqual(data['conditions']['coverage']['opaque_guard_opcodes']['SBR'], 1)
        self.run_ui(r"""
        for(const [opcode,phrase] of [['SBR','no constant-true or pass-through condition is substituted'],['RET','A zero-field RET still represents a return']]){
          navigate('executioncontext');
          rows(tableNamed('Execution control boundaries')).find(r=>texts(r)[0].startsWith(opcode)).querySelector('button').click();
          assert.ok(content.textContent.includes(phrase));
          assert.ok(content.textContent.includes('Incoming condition evidence'));
          assert.ok(content.textContent.includes('roles and types remain unresolved'));
          if(opcode==='RET')assert.ok(content.textContent.includes('Captured fields0'));
        }
        navigate('transfers');
        const sbr=rows(tableNamed('Instruction condition transfers')).find(r=>r.textContent.includes('SBR'));
        assert.ok(sbr.textContent.includes('Unknown condition transfer'));
        """)

    def test_sfr_operation_does_not_promote_missing_or_initial_selector_evidence(self) -> None:
        self.run_ui(r"""
        navigate('sfrcontext');const resets=rows(tableNamed('SFR target contexts'));
        assert.equal(resets.length,3);
        for(let index=0;index<3;index++){
          if(index)navigate('sfrcontext');
          rows(tableNamed('SFR target contexts'))[index].querySelector('button').click();
          assert.ok(content.textContent.includes('stops and resets stored actions in that chart'));
          assert.ok(content.textContent.includes('Selector 0 denotes the initial step'));
          assert.ok(content.textContent.includes('do not establish that this occurrence executes'));
          assert.ok(content.textContent.includes('does not validate the captured signature'));
          assert.ok(tableNamed('SFR content candidates').textContent.includes(index===1?'missing candidate':'unique candidate'));
          if(index===1)assert.ok(content.textContent.includes('Missing named-target context'));
          if(index===2)assert.ok(content.textContent.includes('Selector kindinitial'));
        }
        """)

    def test_residual_followup_distinguishes_vendor_evidence_from_known_operations(self) -> None:
        self.run_ui(r"""
        navigate('residuals');const search=document.getElementById('review-search');
        const expected={JSR:'verified RLL exporter convention',SBR:'Repeating unchanged source capture cannot supply either rule',RET:'enabled RET ends the subroutine scan',SFR:'Outgoing Boolean transfer still requires applicable vendor evidence'};
        for(const [opcode,phrase] of Object.entries(expected)){
          search.value=opcode;search.events.input();
          const selected=rows(tableNamed('Unresolved instruction analysis')).filter(r=>texts(r)[0].startsWith(opcode+' '));assert.ok(selected.length,opcode);
          for(const row of selected){
            assert.ok(row.textContent.includes('Outgoing condition unmodeled'));
            assert.ok(row.textContent.includes(phrase));
            assert.ok(row.textContent.includes('Opaque condition transfer remains unresolved'));
          }
        }
        """)

    def test_historical_context_receives_operation_notes_without_schema_changes(self) -> None:
        self.assertEqual(report(historical=True)['execution_context']['schema_version'], 1)
        self.run_ui(r"""
        navigate('executioncontext');
        rows(tableNamed('Execution control boundaries')).find(r=>texts(r)[0].startsWith('RET')).querySelector('button').click();
        assert.ok(content.textContent.includes('A zero-field RET still represents a return'));
        assert.ok(content.textContent.includes('Captured fields0'));
        assert.ok(content.textContent.includes('Incoming condition evidence'));
        """, historical=True)


if __name__ == '__main__':
    unittest.main()
