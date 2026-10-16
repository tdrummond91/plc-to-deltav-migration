"""Exercise optional condition dossiers against independently invented source."""
from __future__ import annotations

import json
import subprocess
import unittest

from plc_workbench.access import analyze_access
from plc_workbench.calculations import analyze_calculations
from plc_workbench.conditions import analyze_conditions
from plc_workbench.pid import analyze_pid
from plc_workbench.pid_members import analyze_pid_members
from plc_workbench.relationships import analyze_relationships
from plc_workbench.review import build_review_data
from plc_workbench.review_html import ReviewHtmlError, render_review_html
from plc_workbench.rung_analysis import analyze_rungs
from plc_workbench.tag_data import analyze_tag_data
from test_access_review_ui import _NODE
from test_cpt_access_review_ui import DOM
from test_review import fixture
from test_review_html import ParsedPage


def review(texts: tuple[str, ...] = (
    'XIC(A)[XIO(B),[EQU(A,1),]]OTE(Out)OTL(Latch)OTU(Latch);',
    'MYSTERY(A)OTE(Out);',
    'XIC(Missing)OTE(Out);',
    'XIC(A)OTE(Bad.Child)OTE(123)OTE(A,B);',
), *, legacy: bool = False, tags: str = '', schema_version: int = 1) -> dict:
    args = fixture(texts, tags=(
        '<Tag Name="Out" TagType="Base" DataType="BOOL"/>'
        '<Tag Name="Latch" TagType="Base" DataType="BOOL"/>'
        '<Tag Name="Bad" TagType="Alias" AliasFor="A.0"/>' + tags))
    calculations = analyze_calculations(*args[:3])
    access = analyze_access(args[1], args[2], schema_version=4,
                            snapshot=args[0], calculations=calculations)
    tag_data = analyze_tag_data(*args[:2])
    pid = analyze_pid(*args[:3], tag_data)
    members = analyze_pid_members(*args[:3], tag_data, pid)
    rungs = analyze_rungs(*args[:3], access, calculations)
    relationships = analyze_relationships(*args[:3], access, calculations, rungs)
    conditions = analyze_conditions(*args[:3], access, calculations, rungs, relationships,
                                    schema_version=schema_version)
    return build_review_data(*args, access=access, tag_data=tag_data, pid=pid,
                             pid_members=members, calculations=calculations,
                             rung_analysis=rungs, relationships=relationships,
                             **({} if legacy else {'conditions': conditions}))


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI behavior checks.')
class ConditionReviewUiTests(unittest.TestCase):
    def run_ui(self, data: dict, checks: str, *, count_search_characters: bool = False) -> None:
        parsed = ParsedPage(render_review_html(data))
        dom = DOM
        if count_search_characters:
            invocation = "vm.runInThisContext(input.script,{filename:'report.js'});"
            dom = dom.replace(invocation, """
let indexedCharacters=0;
const originalLower=String.prototype.toLocaleLowerCase;
String.prototype.toLocaleLowerCase=function(...args){indexedCharacters+=this.length;return originalLower.apply(this,args);};
""" + invocation + "\nString.prototype.toLocaleLowerCase=originalLower;", 1)
        process = subprocess.run([_NODE, '-e', dom], input=json.dumps({
            'data': data, 'script': parsed.scripts[1][1], 'checks': checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_nested_branches_empty_bypass_and_source_node_navigation(self) -> None:
        self.run_ui(review(), r"""
        navigate('engineering');clickText(content,'Explore conditional outputs');
        rows(tableNamed('Conditional output occurrences'))[0].childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('OTE · Out'));
        assert.ok(content.textContent.includes('not assumed to be true'));
        assert.ok(content.textContent.includes('writes 1 when its incoming condition is true and writes 0 when false'));
        const nodes=tableNamed('Output condition nodes');
        const meanings=rows(nodes).map(r=>texts(r)[1]);
        assert.equal(meanings.filter(t=>t.includes('Incoming rung context')).length,1);
        assert.equal(meanings.filter(t=>t.includes('Any branch input may hold')).length,2);
        const entry=rows(nodes)[0].childNodes[0].querySelector('button').textContent;
        assert.equal(entry,'C1');
        assert.ok(content.textContent.includes('including empty bypass paths'));
        const xic=rows(nodes).find(r=>texts(r)[1].includes('Test XIC'));
        xic.childNodes[0].querySelector('button').click();
        assert.equal(rows(tableNamed('Selected condition operands')).length,1);
        clickText(tableNamed('Selected condition operands'),'Address: A');
        assert.ok(heading.textContent.includes('EXACT ADDRESS EVIDENCE'));
        heading.querySelector('button').click();
        clickText(tableNamed('Selected condition operands'),'A · argument 1');
        assert.ok(heading.textContent.includes('Rung 0'));
        assert.ok(content.textContent.includes('Selected operand'));
        """)

    def test_actions_latch_pair_and_exact_address_backlinks(self) -> None:
        self.run_ui(review(), r"""
        navigate('conditions');
        const initial=rows(tableNamed('Conditional output occurrences'));
        assert.deepEqual(initial.slice(0,3).map(r=>texts(r)[2]),['Assign incoming condition','Set when true','Clear when true']);
        initial[1].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('OTL sets its target'));
        assert.ok(content.textContent.includes('false condition leaves the target unchanged'));
        clickText(content,'Address: Latch');
        const targets=tableNamed('Exact address conditional outputs');
        assert.equal(rows(targets).length,2);
        rows(targets)[1].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('OTU clears its target'));
        assert.ok(content.textContent.includes('false condition leaves the target unchanged'));
        content.querySelectorAll('button').find(b=>b.textContent.startsWith('Rung 0')).click();
        assert.equal(rows(tableNamed('Rung conditional outputs')).length,3);
        """)

    def test_output_inside_leg_keeps_only_conditions_before_its_branch_join(self) -> None:
        self.run_ui(review(('[XIC(A)OTE(Out),XIO(B)]OTE(Latch);',)), r"""
        navigate('conditions');
        assert.ok(content.textContent.includes('Guards containing a branch join1'));
        rows(tableNamed('Conditional output occurrences'))[0].querySelector('button').click();
        assert.ok(!tableNamed('Output condition nodes').textContent.includes('Any branch input'));
        heading.querySelector('button').click();
        rows(tableNamed('Conditional output occurrences'))[1].querySelector('button').click();
        assert.ok(tableNamed('Output condition nodes').textContent.includes('Any branch input'));
        """)

    def test_opaque_transfer_keeps_incoming_context_without_and_assumption(self) -> None:
        self.run_ui(review(('XIC(A)MYSTERY(B)OTE(Out);',)), r"""
        navigate('conditions');
        assert.equal(texts(rows(tableNamed('Conditional output occurrences'))[0])[3],'Contains unknown transfer');
        rows(tableNamed('Conditional output occurrences'))[0].querySelector('button').click();
        const nodes=tableNamed('Output condition nodes');
        const opaque=rows(nodes).find(r=>texts(r)[1].includes('Unknown transfer through MYSTERY'));
        assert.ok(opaque);assert.ok(texts(opaque)[1].includes('Incoming context:'));
        assert.ok(!texts(opaque)[1].includes('All of:'));
        assert.ok(content.textContent.includes('without assuming Boolean AND behavior'));
        opaque.childNodes[0].querySelector('button').click();
        assert.equal(rows(tableNamed('Selected condition inputs')).length,1);
        assert.ok(content.textContent.includes('unsupported condition behavior'));
        assert.equal(rows(tableNamed('Selected condition operands')).length,1);
        """)

    def test_unbound_guard_target_gap_and_invalid_signature_stay_separate(self) -> None:
        self.run_ui(review(), r"""
        navigate('conditions');
        let quality=document.getElementById('toolbar').querySelectorAll('select')[1];
        quality.value='binding_gaps';quality.events.change();
        assert.equal(rows(tableNamed('Conditional output occurrences')).length,1);
        assert.equal(texts(rows(tableNamed('Conditional output occurrences'))[0])[3],'Condition binding gaps');
        quality.value='all';quality.events.change();
        const bad=rows(tableNamed('Conditional output occurrences')).find(r=>texts(r)[0]==='OTE · Bad.Child');
        assert.ok(texts(bad)[1].includes('identity gap'));
        assert.ok(!bad.childNodes[1].querySelectorAll('button').some(b=>b.textContent.startsWith('Address:')));
        bad.childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Target identityidentity gap'));
        navigate('conditions');
        const literal=rows(tableNamed('Conditional output occurrences')).find(r=>texts(r)[0]==='OTE · 123');
        assert.ok(texts(literal)[1].includes('unbound'));
        const unresolved=rows(tableNamed('Conditional output occurrences')).find(r=>texts(r)[2]==='Output signature unresolved');
        assert.ok(unresolved);unresolved.childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('No target action is assigned'));
        """)

    def test_read_after_write_retains_two_distinct_predicate_occurrences(self) -> None:
        self.run_ui(review(('XIC(A)OTE(A)XIC(A)OTE(B);',)), r"""
        navigate('conditions');
        rows(tableNamed('Conditional output occurrences'))[1].childNodes[0].querySelector('button').click();
        let predicates=rows(tableNamed('Output condition nodes')).filter(r=>texts(r)[1].includes('Test XIC'));
        assert.equal(predicates.length,2);
        assert.notEqual(texts(predicates[0])[0],texts(predicates[1])[0]);
        assert.ok(content.textContent.includes('intervening writes can change later reads'));
        predicates[1].childNodes[0].querySelector('button').click();
        const source=input.data.references.operands.filter(o=>o.raw_text==='A');
        assert.equal(source.length,3);
        assert.ok(content.textContent.includes(source[2].id));
        clickText(tableNamed('Selected condition operands'),'A · argument 1');
        assert.ok(content.textContent.includes('Selected operand'));
        """)

    def test_search_opcode_quality_pagination_and_back_restore(self) -> None:
        data = review(tuple(f'XIC(A)OTE(Target{i});' for i in range(53)) + ('OTL(Latch);',),
                      tags=''.join(f'<Tag Name="Target{i}" TagType="Base" DataType="BOOL"/>' for i in range(53)))
        self.run_ui(data, r"""
        navigate('conditions');
        let opcode=document.getElementById('toolbar').querySelectorAll('select')[0];
        opcode.value='OTE';opcode.events.change();
        assert.equal(rows(tableNamed('Conditional output occurrences')).length,50);
        content.querySelectorAll('button').find(b=>b.attributes['aria-label']==='Next page: Conditional output occurrences').click();
        assert.equal(rows(tableNamed('Conditional output occurrences')).length,3);
        rows(tableNamed('Conditional output occurrences'))[0].childNodes[0].querySelector('button').click();
        heading.querySelector('button').click();
        assert.equal(rows(tableNamed('Conditional output occurrences')).length,3);
        let search=document.getElementById('review-search');search.value='Target52';search.events.input();
        assert.equal(rows(tableNamed('Conditional output occurrences')).length,1);
        search.value='';search.events.input();
        opcode=document.getElementById('toolbar').querySelectorAll('select')[0];opcode.value='OTL';opcode.events.change();
        assert.equal(rows(tableNamed('Conditional output occurrences')).length,1);
        assert.ok(tableNamed('Conditional output occurrences').textContent.includes('Latch'));
        """)

    def test_shared_graph_is_visited_once_without_formula_expansion(self) -> None:
        data = review((''.join('[XIC(A),XIO(B)]OTE(Out)' for _ in range(55)) + ';',))
        self.run_ui(data, r"""
        navigate('conditions');
        content.querySelectorAll('button').find(b=>b.attributes['aria-label']==='Next page: Conditional output occurrences').click();
        rows(tableNamed('Conditional output occurrences')).at(-1).childNodes[0].querySelector('button').click();
        const labels=[];
        while(true){
          labels.push(...rows(tableNamed('Output condition nodes')).map(r=>texts(r)[0]));
          const next=content.querySelectorAll('button').find(b=>b.attributes['aria-label']==='Next page: Output condition nodes');
          if(next.disabled)break;next.click();
        }
        assert.equal(labels.length,input.data.conditions.nodes.length);
        assert.equal(new Set(labels).size,labels.length);
        assert.ok(labels.length<400);
        assert.ok(content.textContent.length<25000);
        """)

    def test_wide_branch_input_links_are_paged_and_bounded(self) -> None:
        data = review(('[' + ','.join('XIC(A)' for _ in range(65)) + ']OTE(Out);',))
        self.run_ui(data, r"""
        navigate('conditions');rows(tableNamed('Conditional output occurrences'))[0].querySelector('button').click();
        while(!content.querySelectorAll('button').some(b=>b.textContent==='Inspect all 65 inputs')){
          content.querySelectorAll('button').find(b=>b.attributes['aria-label']==='Next page: Output condition nodes').click();
        }
        const any=rows(tableNamed('Output condition nodes')).find(r=>texts(r)[1].includes('Any branch input'));
        assert.equal(any.childNodes[1].querySelectorAll('button').length,9);
        clickText(any,'Inspect all 65 inputs');
        assert.equal(rows(tableNamed('Selected condition inputs')).length,50);
        content.querySelectorAll('button').find(b=>b.attributes['aria-label']==='Next page: Selected condition inputs').click();
        assert.equal(rows(tableNamed('Selected condition inputs')).length,15);
        rows(tableNamed('Selected condition inputs'))[0].childNodes[1].querySelector('button').click();
        assert.ok(content.textContent.includes('Selected condition'));
        """)

    def test_long_target_root_stays_bounded_in_output_labels_and_search(self) -> None:
        name = 'Root' + 'N' * 59_996
        data = review(tuple(f'XIC(A)OTE(LongAlias[{i}]);' for i in range(200)), tags=(
            f'<Tag Name="{name}" TagType="Base" DataType="DINT"/>'
            f'<Tag Name="LongAlias" TagType="Alias" AliasFor="{name}"/>'))
        self.run_ui(data, r"""
        assert.ok(indexedCharacters<2000000,'Search index amplification: '+indexedCharacters);
        navigate('conditions');
        for(const row of rows(tableNamed('Conditional output occurrences'))){
          assert.ok(texts(row)[0].length<300);assert.ok(texts(row)[1].length<300);
        }
        const search=document.getElementById('review-search');search.value='[199]';search.events.input();
        assert.equal(rows(tableNamed('Conditional output occurrences')).length,1);
        rows(tableNamed('Conditional output occurrences'))[0].querySelector('button').click();
        assert.ok(heading.textContent.length<500);
        const address=content.querySelectorAll('button').find(b=>b.textContent.startsWith('Address: Root'));address.click();
        const declaration=content.querySelectorAll('button').find(b=>b.textContent.startsWith('Root'));declaration.click();
        assert.ok(heading.textContent.includes('Root'+'N'.repeat(59996)));
        """, count_search_characters=True)

    def test_legacy_relationship_report_has_no_conditional_navigation(self) -> None:
        self.run_ui(review(legacy=True), r"""
        assert.ok(!document.getElementById('navigation').querySelectorAll('button').some(b=>b.dataset.view==='conditions'));
        navigate('engineering');assert.ok(!content.textContent.includes('Explore conditional outputs'));
        navigate('ladder');clickText(content,'Rung 0');
        assert.ok(!content.textContent.includes('Conditional coil outputs in this rung'));
        navigate('relationships');rows(tableNamed('Exact address groups'))[0].querySelector('button').click();
        assert.ok(!content.textContent.includes('Conditional coil outputs targeting this address'));
        """)

    def test_no_output_rung_has_instruction_context_and_separate_false_state_note(self) -> None:
        data = review(('XIC(A)MOV(A,B)TON(T,?,?)OSF(A,B);',), schema_version=2,
                      tags='<Tag Name="T" TagType="Base" DataType="TIMER"/>')
        self.assertEqual(data['schema_version'], 10)
        self.run_ui(data, r"""
        navigate('engineering');clickText(content,'Explore instruction conditions');
        assert.equal(rows(tableNamed('Instruction condition transfers')).length,3);
        assert.ok(content.textContent.includes('false condition can still change instruction state'));
        assert.ok(content.textContent.includes('OSF output bit is distinct'));
        const ton=rows(tableNamed('Instruction condition transfers')).find(r=>texts(r)[0]==='TON');
        assert.equal(texts(ton)[1],'Passes incoming condition');
        ton.childNodes[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('INSTRUCTION CONDITION TRANSFER'));
        assert.ok(content.textContent.includes('Incoming condition evidenceModeled condition structure'));
        assert.equal(rows(tableNamed('Instruction transfer operand access')).length,3);
        assert.ok(tableNamed('Instruction condition nodes').textContent.includes('Pass through TON'));
        content.querySelectorAll('button').find(b=>b.textContent.startsWith('Rung 0')).click();
        assert.equal(rows(tableNamed('Rung instruction condition transfers')).length,3);
        assert.ok(content.textContent.includes('No conditional outputs in this selection'));
        """)

    def test_pass_transfer_does_not_hide_data_binding_gaps_or_taint_boolean_condition(self) -> None:
        self.run_ui(review(('XIC(A)MOV(Missing,B)OTE(Out);',), schema_version=2), r"""
        navigate('conditions');
        assert.equal(texts(rows(tableNamed('Conditional output occurrences'))[0])[3],'Modeled condition structure');
        rows(tableNamed('Conditional output occurrences'))[0].querySelector('button').click();
        const pass=rows(tableNamed('Output condition nodes')).find(r=>texts(r)[1].includes('Pass through MOV'));
        pass.childNodes[0].querySelector('button').click();
        clickText(content,'Inspect instruction condition transfer');
        assert.ok(content.textContent.includes('Data binding gaps do not alter this transfer rule'));
        const missing=rows(tableNamed('Instruction transfer operand access')).find(r=>texts(r)[0]==='Missing');
        assert.ok(texts(missing)[3].includes('unresolved'));
        assert.ok(content.textContent.includes('Outgoing condition evidenceModeled condition structure'));
        """)

    def test_invalid_signature_and_unknown_ancestry_are_visible_on_no_output_rungs(self) -> None:
        self.run_ui(review(('MOV(A);','MYSTERY(B)MOV(A,B);'), schema_version=2), r"""
        navigate('transfers');
        const initial=rows(tableNamed('Instruction condition transfers'));
        assert.equal(initial.length,3);
        assert.equal(texts(initial[0])[1],'Unknown condition transfer');
        assert.equal(texts(initial[2])[1],'Passes incoming condition');
        assert.equal(texts(initial[2])[2],'Contains unknown transfer');
        initial[0].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('signature unresolved'));
        assert.ok(content.textContent.includes('Outgoing condition behavior remains unmodeled'));
        heading.querySelector('button').click();
        rows(tableNamed('Instruction condition transfers'))[2].querySelector('button').click();
        assert.ok(content.textContent.includes('Outgoing condition evidenceContains unknown transfer'));
        assert.ok(tableNamed('Instruction condition nodes').textContent.includes('Unknown transfer through MYSTERY'));
        """)

    def test_transfer_graph_preserves_reads_around_writes(self) -> None:
        self.run_ui(review(('XIC(A)MOV(B,A)XIC(A)MOV(A,B);',), schema_version=2), r"""
        navigate('transfers');
        rows(tableNamed('Instruction condition transfers'))[1].querySelector('button').click();
        const graph=rows(tableNamed('Instruction condition nodes'));
        const predicates=graph.filter(r=>texts(r)[1].includes('Test XIC'));
        assert.equal(predicates.length,2);
        assert.notEqual(texts(predicates[0])[0],texts(predicates[1])[0]);
        assert.equal(graph.filter(r=>texts(r)[1].includes('Pass through MOV')).length,2);
        predicates[1].childNodes[0].querySelector('button').click();
        assert.equal(rows(tableNamed('Selected condition operands')).length,1);
        assert.ok(content.textContent.includes(input.data.references.operands[3].id));
        """)

    def test_transfer_filters_search_pagination_and_back_restore(self) -> None:
        self.run_ui(review(tuple('MOV(A,B);' for _ in range(53)) + ('MYSTERY(B);',),
                           schema_version=2), r"""
        navigate('transfers');
        const filter=document.getElementById('toolbar').querySelector('select');
        filter.value='pass_through';filter.events.change();
        assert.equal(rows(tableNamed('Instruction condition transfers')).length,50);
        content.querySelectorAll('button').find(b=>b.attributes['aria-label']==='Next page: Instruction condition transfers').click();
        assert.equal(rows(tableNamed('Instruction condition transfers')).length,3);
        rows(tableNamed('Instruction condition transfers'))[0].querySelector('button').click();
        heading.querySelector('button').click();
        assert.equal(rows(tableNamed('Instruction condition transfers')).length,3);
        const search=document.getElementById('review-search');search.value='Rung 52';search.events.input();
        assert.equal(rows(tableNamed('Instruction condition transfers')).length,1);
        search.value='';search.events.input();
        const restored=document.getElementById('toolbar').querySelector('select');
        restored.value='opaque_transfer';restored.events.change();
        assert.equal(texts(rows(tableNamed('Instruction condition transfers'))[0])[0],'MYSTERY');
        """)

    def test_transfer_graph_visits_shared_ancestors_once(self) -> None:
        data = review((''.join('[XIC(A),XIO(B)]MOV(A,B)' for _ in range(55)) + ';',),
                      schema_version=2)
        self.run_ui(data, r"""
        navigate('transfers');
        content.querySelectorAll('button').find(b=>b.attributes['aria-label']==='Next page: Instruction condition transfers').click();
        rows(tableNamed('Instruction condition transfers')).at(-1).querySelector('button').click();
        const labels=[];
        while(true){
          labels.push(...rows(tableNamed('Instruction condition nodes')).map(r=>texts(r)[0]));
          const next=content.querySelectorAll('button').find(b=>b.attributes['aria-label']==='Next page: Instruction condition nodes');
          if(next.disabled)break;next.click();
        }
        assert.equal(labels.length,input.data.conditions.nodes.length);
        assert.equal(new Set(labels).size,labels.length);
        assert.ok(content.textContent.length<25000);
        """)

    def test_transfer_source_text_stays_inert(self) -> None:
        self.run_ui(review(('MYSTERY("<img src=x onerror=evil()>")MOV(A,B);',),
                           schema_version=2), r"""
        navigate('transfers');
        assert.ok(tableNamed('Instruction condition transfers').textContent.includes('<img src=x onerror=evil()>'));
        assert.equal(content.querySelectorAll('img').length,0);
        rows(tableNamed('Instruction condition transfers'))[0].querySelector('button').click();
        assert.ok(tableNamed('Instruction transfer operand access').textContent.includes('<img src=x onerror=evil()>'));
        assert.equal(content.querySelectorAll('img').length,0);
        """)

    def test_transfer_search_does_not_expand_long_alias_roots_per_occurrence(self) -> None:
        name = 'TransferRoot' + 'N' * 59_988
        data = review(tuple(f'MOV(A,LongAlias[{i}]);' for i in range(200)), schema_version=2,
                      tags=f'<Tag Name="{name}" TagType="Base" DataType="DINT"/>'
                           f'<Tag Name="LongAlias" TagType="Alias" AliasFor="{name}"/>')
        self.run_ui(data, r"""
        assert.ok(indexedCharacters<2000000,'Search index amplification: '+indexedCharacters);
        navigate('transfers');
        for(const row of rows(tableNamed('Instruction condition transfers'))){
          assert.ok(texts(row)[0].length<100);assert.ok(texts(row)[3].length<400);
        }
        const search=document.getElementById('review-search');search.value='[199]';search.events.input();
        assert.equal(rows(tableNamed('Instruction condition transfers')).length,1);
        assert.ok(texts(rows(tableNamed('Instruction condition transfers'))[0])[3].includes('LongAlias[199]'));
        """, count_search_characters=True)

    def test_condition_one_report_retains_opaque_mov_and_has_no_transfer_view(self) -> None:
        data = review(('MOV(A,B)OTE(Out);',))
        self.assertEqual(data['schema_version'], 9)
        self.run_ui(data, r"""
        assert.ok(!document.getElementById('navigation').querySelectorAll('button').some(b=>b.dataset.view==='transfers'));
        navigate('conditions');rows(tableNamed('Conditional output occurrences'))[0].querySelector('button').click();
        assert.ok(tableNamed('Output condition nodes').textContent.includes('Unknown transfer through MOV'));
        assert.ok(!content.textContent.includes('Pass through MOV'));
        """)

    def test_render_gate_rejects_condition_version_mismatch(self) -> None:
        for schema_version in (1, 2):
            with self.subTest(schema_version=schema_version):
                data = review(('MOV(A,B);',), schema_version=schema_version)
                data['conditions']['schema_version'] = 3 - schema_version
                with self.assertRaises(ReviewHtmlError):
                    render_review_html(data)


if __name__ == '__main__':
    unittest.main()
