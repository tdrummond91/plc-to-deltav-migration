"""Rendered navigation for source boundaries, AOI proofs and generic selectors."""
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
from test_control_interpretation_workflow import SOURCE, captured, options
from test_residual_interpretation_workflow import captured as legacy_captured, options as legacy_options
from test_review_html import ParsedPage


@lru_cache(maxsize=4)
def page(data: bytes = SOURCE, *, legacy: bool = False) -> tuple[dict, str]:
    with source_reuse_scope():
        parts = legacy_captured(data) if legacy else captured(data)
        model = build_review_data(*parts[:4], **(legacy_options(parts) if legacy else options(parts)))
        return model, ParsedPage(render_review_html(model)).scripts[1][1]


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI behavior checks.')
class ControlInterpretationUiTests(unittest.TestCase):
    def run_ui(self, checks: str, *, data: bytes = SOURCE, legacy: bool = False) -> None:
        model, script = page(data, legacy=legacy)
        result = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': model, 'script': script, 'checks': checks}), text=True, encoding='utf-8',
            capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_call_boundary_and_field_links_reuse_existing_source_dossiers(self):
        self.run_ui(r"""
        navigate('executioncontext');
        assert.equal(rows(tableNamed('Execution routine calls')).length,2);
        rows(tableNamed('Execution routine calls'))[1].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Associationassociated'));
        assert.ok(content.textContent.includes('Boundary populationsbr and ret'));
        assert.ok(content.textContent.includes('Second field spellingother'));
        const fields=tableNamed('Execution lexical field candidates');
        assert.deepEqual(rows(fields).map(r=>texts(r)[1]),['routine target','root bound candidate','root bound candidate']);
        assert.ok(texts(rows(fields)[1])[0].includes('2: Raw'));
        assert.ok(content.textContent.includes('do not validate an RLL calling convention'));
        const boundaries=tableNamed('Exact content SBR and RET occurrences');
        assert.equal(rows(boundaries).length,2);
        rows(boundaries)[0].childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('SBR boundary'));
        assert.equal(rows(tableNamed('Execution lexical field candidates')).length,1);
        assert.equal(rows(tableNamed('Exact content SBR and RET occurrences')).length,2);
        clickText(tableNamed('Execution lexical field candidates'),'Raw');
        assert.ok(heading.textContent.includes('Raw'));
        navigate('executioncontext');clickText(tableNamed('Execution routine bodies'),'Sub');
        assert.equal(rows(tableNamed('Routine incoming calls')).length,2);
        assert.equal(rows(tableNamed('Exact content SBR and RET occurrences')).length,2);
        assert.ok(!content.textContent.includes('undefined'));
        """)

    def test_generic_service_identity_and_selector_source_values(self):
        self.run_ui(r"""
        navigate('communication');
        assert.ok(tableNamed('Generic service populations').textContent.includes('get attribute single'));
        assert.ok(tableNamed('Generic service populations').textContent.includes('unavailable'));
        clickText(tableNamed('Communication occurrences'),'MSG · GenericMessage');
        assert.ok(content.textContent.includes('Generic service identityget attribute single'));
        assert.ok(content.textContent.includes('Selector encoding completenessall selectors parsed'));
        const selectors=tableNamed('Generic message selectors');
        assert.equal(rows(selectors).length,4);
        assert.deepEqual(texts(rowNamed(selectors,'ServiceCode')),['ServiceCode','16#000e','parsed','14']);
        assert.deepEqual(texts(rowNamed(selectors,'TargetObject')),['TargetObject','1','parsed','1']);
        assert.ok(content.textContent.includes('do not establish target support'));
        assert.ok(content.textContent.includes('Configured directionservice dependent'));
        assert.ok(!content.textContent.includes('Generic services, runtime changes'));
        """)

    def test_aoi_proof_has_source_links_and_routine_transfers_stay_opaque(self):
        self.run_ui(r"""
        navigate('transfers');
        assert.ok(tableNamed('AOI condition proof dispositions').textContent.includes('modeled'));
        clickText(tableNamed('Instruction condition transfers'),'InventedScale');
        assert.ok(content.textContent.includes('Proof dispositionmodeled'));
        assert.ok(content.textContent.includes('supported operations do not write EnableIn or EnableOut'));
        assert.ok(content.textContent.includes('does not pair positional parameters'));
        for(const name of ['InventedScale','Converter','Logic','EnableOut'])assert.ok(content.querySelectorAll('button').some(b=>b.textContent===name));
        navigate('transfers');clickText(tableNamed('Instruction condition transfers'),'JSR');
        assert.ok(content.textContent.includes('Outgoing condition behavior remains unmodeled'));
        assert.ok(!content.textContent.includes('AOI outgoing-condition evidence'));
        """)

    def test_failed_aoi_proof_explains_first_blocking_check(self):
        data = SOURCE.replace(b'MOV(InputValue,OutputValue);', b'MOV(InputValue,EnableOut);')
        self.run_ui(r"""
        navigate('transfers');clickText(tableNamed('Instruction condition transfers'),'InventedScale');
        assert.ok(content.textContent.includes('Proof dispositionexplicit override'));
        assert.ok(content.textContent.includes('first blocking check'));
        assert.ok(content.textContent.includes('outgoing condition remains opaque'));
        """, data=data)

    def test_gsv_signature_disposition_explains_existing_syntax_boundary(self):
        data = SOURCE.replace(b'JSR(Sub,0)JSR(Sub,Raw,Command);',
            b'GSV(WallClockTime,,CurrentValue,Raw)GSV(WallClockTime,,CurrentValue,?);')
        self.run_ui(r"""
        navigate('transfers');
        assert.ok(tableNamed('GSV signature dispositions').textContent.includes('destination syntax'));
        const gsv=rows(tableNamed('Instruction condition transfers')).filter(r=>texts(r)[0]==='GSV');
        assert.equal(gsv.length,2);gsv[1].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Signature dispositiondestination syntax'));
        assert.ok(content.textContent.includes('destination field does not have a supported address spelling'));
        assert.ok(content.textContent.includes('does not identify an object/attribute catalogue match'));
        assert.ok(content.textContent.includes('Outgoing condition behavior remains unmodeled'));
        """, data=data)

    def test_pid2_preserves_incoming_condition_and_documented_transfer_text(self):
        self.run_ui(r"""
        navigate('pid');rows(tableNamed('PID instruction occurrences'))[0].childNodes[0].querySelector('button').click();
        assert.equal(rows(tableNamed('PID incoming conditions')).length,1);
        assert.ok(content.textContent.includes('normal-execution PID rule preserves the incoming rung condition'));
        assert.ok(!content.textContent.includes('outgoing PID condition behavior remains unmodeled'));
        rows(tableNamed('PID incoming conditions'))[0].childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('INSTRUCTION CONDITION TRANSFER'));
        assert.ok(content.textContent.includes('Selected condition'));
        """)

    def test_prior_bundle_keeps_legacy_views_without_new_rows(self):
        self.run_ui(r"""
        navigate('executioncontext');rows(tableNamed('Execution routine calls'))[0].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Captured arguments and parameter unknowns'));
        assert.ok(!content.textContent.includes('Execution lexical field candidates'));
        assert.ok(!content.textContent.includes('Call to exact source content'));
        navigate('communication');clickText(tableNamed('Communication occurrences'),'MSG · GenericMessage');
        assert.ok(content.textContent.includes('Generic services, runtime changes'));
        assert.ok(!content.textContent.includes('Generic message selectors'));
        navigate('transfers');clickText(tableNamed('Instruction condition transfers'),'InventedScale');
        assert.ok(!content.textContent.includes('AOI outgoing-condition evidence'));
        navigate('pid');rows(tableNamed('PID instruction occurrences'))[0].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Outgoing PID condition behavior remains unmodeled in this saved view'));
        assert.ok(!content.textContent.includes('undefined'));
        """, legacy=True)


if __name__ == '__main__':
    unittest.main()
