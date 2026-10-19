"""Navigate invented unresolved bindings without promoting rack candidates."""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access
from plc_workbench.binding_context import analyze_binding_context
from plc_workbench.calculations import analyze_calculations
from plc_workbench.conditions import analyze_conditions
from plc_workbench.pid import analyze_pid
from plc_workbench.pid_members import analyze_pid_members
from plc_workbench.references import analyze_references
from plc_workbench.relationships import analyze_relationships
from plc_workbench.review import build_review_data
from plc_workbench.review_html import ReviewHtmlError, ReviewHtmlSizeLimitError, render_review_html
from plc_workbench.rung_analysis import analyze_rungs
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.tag_data import analyze_tag_data
from test_access_review_ui import _NODE
import test_condition_review_ui as condition_ui
from test_rack_candidates import LOCAL, card


def review(texts: tuple[str, ...] = ('XIC(AliasTwo)OTE(Local:3:O.Data.0);',), *,
           tags: str = '', modules: str | None = None, legacy: bool = False) -> dict:
    rows = ''.join(f'<Rung Number="{i}" Type="N"><Text><![CDATA[{text}]]></Text></Rung>'
                   for i, text in enumerate(texts))
    raw = ('<RSLogix5000Content><Controller Name="Invented"><Modules>'
           + (LOCAL + card() if modules is None else modules) + '</Modules><Tags>'
           '<Tag Name="A" TagType="Base" DataType="BOOL"/>'
           '<Tag Name="B" TagType="Base" DataType="BOOL"/>'
           '<Tag Name="AliasOne" TagType="Alias" AliasFor="Local:3:I.Data.0"/>'
           '<Tag Name="AliasTwo" TagType="Alias" AliasFor="AliasOne"/>' + tags + '</Tags>'
           '<Programs><Program Name="P"><Routines><Routine Name="Main" Type="RLL">'
           '<RLLContent>' + rows + '</RLLContent></Routine></Routines></Program></Programs>'
           '</Controller></RSLogix5000Content>')
    snapshot = snapshot_from_bytes(raw.encode())
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    args = snapshot, inventory, references
    calculations = analyze_calculations(*args)
    access = analyze_access(inventory, references, schema_version=4,
                            snapshot=snapshot, calculations=calculations)
    tag_data = analyze_tag_data(snapshot, inventory)
    pid = analyze_pid(*args, tag_data)
    members = analyze_pid_members(*args, tag_data, pid)
    rungs = analyze_rungs(*args, access, calculations)
    relationships = analyze_relationships(*args, access, calculations, rungs)
    conditions = analyze_conditions(*args, access, calculations, rungs, relationships,
                                    schema_version=2)
    context = analyze_binding_context(*args, access, calculations, rungs, relationships,
                                      conditions)
    return build_review_data(*args, analyze_sfc_structure(snapshot, inventory), access=access,
                             tag_data=tag_data, pid=pid, pid_members=members,
                             calculations=calculations, rung_analysis=rungs,
                             relationships=relationships, conditions=conditions,
                             **({} if legacy else {'binding_context': context}))


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI behavior checks.')
class BindingContextReviewUiTests(unittest.TestCase):
    run_ui = condition_ui.ConditionReviewUiTests.run_ui

    def test_alias_chain_candidate_module_and_connection_navigation(self) -> None:
        data = review()
        self.assertEqual(data['schema_version'], 11)
        self.run_ui(data, r"""
        navigate('engineering');clickText(content,'Explore binding gaps & context');
        assert.equal(rows(tableNamed('Binding gap occurrences')).length,2);
        assert.ok(content.textContent.includes('never join the exact-address groups'));
        rows(tableNamed('Binding gap occurrences'))[0].querySelector('button').click();
        assert.ok(heading.textContent.includes('BINDING GAP CONTEXT'));
        assert.ok(content.textContent.includes('Binding statusunresolved'));
        assert.equal(rows(tableNamed('Binding context alias chain')).length,2);
        assert.deepEqual(rows(tableNamed('Binding context alias chain')).map(r=>texts(r)[1]),['AliasTwo','AliasOne']);
        assert.ok(content.textContent.includes('Terminal rootLocal:3:I'));
        assert.ok(content.textContent.includes('Backing mappingnot analyzed'));
        assert.ok(tableNamed('Binding predicate condition nodes').textContent.includes('Test XIC'));
        clickText(content,'Open module: Card');assert.ok(heading.textContent.includes('SOURCE OBJECTCard'));
        heading.querySelector('button').click();clickText(content,'Open connection');
        assert.ok(heading.textContent.includes('module rack connection'));
        heading.querySelector('button').click();clickText(content,'Open rack alias source');
        assert.ok(heading.textContent.includes('module rack input alias'));
        """)

    def test_condition_predicate_and_output_target_links_preserve_gaps(self) -> None:
        self.run_ui(review(), r"""
        navigate('conditions');
        const output=rows(tableNamed('Conditional output occurrences'))[0];
        assert.equal(texts(output)[3],'Condition binding gaps');
        assert.ok(texts(output)[1].includes('unbound'));
        output.childNodes[0].querySelector('button').click();
        const predicate=rows(tableNamed('Output condition nodes')).find(r=>texts(r)[1].includes('Test XIC'));
        predicate.childNodes[0].querySelector('button').click();
        clickText(tableNamed('Selected condition operands'),'Explain binding gap');
        assert.ok(heading.textContent.includes('AliasTwo'));
        heading.querySelector('button').click();
        content.querySelectorAll('button').find(b=>b.textContent==='Explain binding gap').click();
        assert.ok(heading.textContent.includes('Local:3:O.Data.0'));
        assert.equal(rows(tableNamed('Binding gap conditional output')).length,1);
        assert.ok(tableNamed('Binding gap conditional output').textContent.includes('unbound'));
        """)

    def test_access_role_is_independent_of_candidate_module_direction(self) -> None:
        self.run_ui(review(('OTE(Local:3:I.Data.0);',)), r"""
        navigate('access');clickText(tableNamed('Unresolved operand accesses'),'Explain binding gap');
        assert.ok(content.textContent.includes('Operand rolewrite'));
        assert.ok(content.textContent.includes('Module directioninput'));
        clickText(content,'Candidate address: Local:3:I.Data.0');
        assert.ok(heading.textContent.includes('LOGICAL CANDIDATE ADDRESS'));
        assert.ok(content.textContent.includes('Captured use profilewrite only'));
        assert.equal(texts(rows(tableNamed('Candidate address source occurrences'))[0])[1],'operandwrite');
        """)

    def test_candidate_address_groups_do_not_merge_with_exact_addresses(self) -> None:
        data = review(('XIC(AliasTwo)XIO(Local:3:I.Data.0)OTE(Local:3:I.Data.0);',
                       'XIC(Local:3:I.Data.1)OTE(A);'))
        self.run_ui(data, r"""
        navigate('bindingcontext');
        const mode=document.getElementById('toolbar').querySelectorAll('select')[1];
        mode.value='addresses';mode.events.change();
        const groups=rows(tableNamed('Logical candidate addresses'));
        assert.equal(groups.length,2);assert.equal(texts(groups[0])[1],'read and write');
        assert.equal(texts(groups[0])[2],'3');
        groups[0].querySelector('button').click();
        assert.equal(rows(tableNamed('Candidate address source occurrences')).length,3);
        assert.ok(content.textContent.includes('Member validity, bounds, backing layout and physical channels remain unverified'));
        navigate('relationships');
        assert.ok(!tableNamed('Exact address groups').textContent.includes('Local:3:I'));
        assert.ok(tableNamed('Exact address groups').textContent.includes('A'));
        """)

    def test_ambiguous_missing_and_expression_context_do_not_select_candidate(self) -> None:
        data = review(('XIC(Local:3:I.Data.0)XIC(Local:9:I.Data.0)XIC(Missing)OTE(123);',
                       'CPT(A,AliasOne+Missing);'), modules=LOCAL + card('One') + card('Two'))
        self.run_ui(data, r"""
        navigate('bindingcontext');
        const all=rows(tableNamed('Binding gap occurrences'));
        assert.ok(all.some(r=>texts(r)[2]==='Ambiguous rack-name candidates'));
        assert.ok(all.some(r=>texts(r)[2]==='No rack-name match'));
        assert.ok(all.some(r=>texts(r)[2]==='Value is not an address'));
        assert.ok(all.some(r=>texts(r)[2]==='No existing rack-match evidence'));
        all.find(r=>texts(r)[2]==='Ambiguous rack-name candidates').querySelector('button').click();
        assert.ok(content.textContent.includes('Candidate count2'));
        assert.ok(!content.querySelectorAll('button').some(b=>b.textContent.startsWith('Candidate address:')));
        navigate('access');
        const expression=rows(tableNamed('Unresolved expression reads')).find(r=>texts(r)[0]==='AliasOne');
        clickText(expression,'Explain binding gap');
        assert.ok(content.textContent.includes('Occurrence kindexpression'));
        assert.ok(content.textContent.includes('No existing rack-match evidence'));
        assert.ok(!content.textContent.includes('Rack-name candidate context'));
        content.querySelectorAll('button').find(b=>b.textContent==='AliasOne').click();
        assert.ok(heading.textContent.includes('CALCULATION SOURCE EVIDENCE'));
        assert.ok(content.textContent.includes('Selected expression read'));
        """)

    def test_gap_and_candidate_search_filter_pagination_back_state(self) -> None:
        data = review(tuple(f'XIC(Local:3:I.Data.{i});' for i in range(53)) + ('XIC(Missing);',))
        self.run_ui(data, r"""
        navigate('bindingcontext');
        const filter=document.getElementById('toolbar').querySelectorAll('select')[0];
        filter.value='rack_unique_candidate';filter.events.change();
        assert.equal(rows(tableNamed('Binding gap occurrences')).length,50);
        content.querySelectorAll('button').find(b=>b.attributes['aria-label']==='Next page: Binding gap occurrences').click();
        assert.equal(rows(tableNamed('Binding gap occurrences')).length,3);
        rows(tableNamed('Binding gap occurrences'))[0].querySelector('button').click();
        heading.querySelector('button').click();assert.equal(rows(tableNamed('Binding gap occurrences')).length,3);
        let search=document.getElementById('review-search');search.value='Data.52';search.events.input();
        assert.equal(rows(tableNamed('Binding gap occurrences')).length,1);
        search.value='';search.events.input();
        const mode=document.getElementById('toolbar').querySelectorAll('select')[1];
        mode.value='addresses';mode.events.change();
        assert.equal(rows(tableNamed('Logical candidate addresses')).length,50);
        content.querySelectorAll('button').find(b=>b.attributes['aria-label']==='Next page: Logical candidate addresses').click();
        assert.equal(rows(tableNamed('Logical candidate addresses')).length,3);
        search=document.getElementById('review-search');search.value='Data.52';search.events.input();
        assert.equal(rows(tableNamed('Logical candidate addresses')).length,1);
        rows(tableNamed('Logical candidate addresses'))[0].querySelector('button').click();
        assert.equal(rows(tableNamed('Candidate address source occurrences')).length,1);
        """)

    def test_dossier_evidence_remains_text_and_legacy_has_no_context_links(self) -> None:
        data = review(('OTE("<img src=x>");',))
        self.run_ui(data, r"""
        navigate('bindingcontext');rows(tableNamed('Binding gap occurrences'))[0].querySelector('button').click();
        assert.ok(content.textContent.includes('<img src=x>'));
        assert.equal(content.querySelectorAll('img').length,0);
        """)
        self.run_ui(review(legacy=True), r"""
        assert.ok(!document.getElementById('navigation').querySelectorAll('button').some(b=>b.dataset.view==='bindingcontext'));
        navigate('conditions');assert.ok(!content.textContent.includes('Explain binding gap'));
        navigate('access');assert.ok(!content.textContent.includes('Explain binding gap'));
        """)

    def test_long_source_names_have_bounded_new_search_rows(self) -> None:
        name = 'Missing' + 'N' * 59_993
        data = review(tuple('XIC(LongAlias);' for _ in range(150)),
                      tags=f'<Tag Name="LongAlias" TagType="Alias" AliasFor="{name}"/>')
        self.run_ui(data, r"""
        assert.ok(indexedCharacters<2000000,'Search index amplification: '+indexedCharacters);
        navigate('bindingcontext');assert.equal(rows(tableNamed('Binding gap occurrences')).length,50);
        assert.ok(content.textContent.length<25000);
        """, count_search_characters=True)


class BindingContextHtmlGateTests(unittest.TestCase):
    def test_version_gate_rejects_missing_mismatched_and_legacy_context(self) -> None:
        data = review()
        for bad in (None, {}, {'schema_version': True, 'analyzer_version': 'binding-context-1'},
                    {'schema_version': 1, 'analyzer_version': 'wrong'}):
            with self.subTest(bad=bad):
                changed = deepcopy(data)
                changed['binding_context'] = bad
                with self.assertRaises(ReviewHtmlError):
                    render_review_html(changed)
        changed = deepcopy(data)
        changed['schema_version'], changed['report_version'] = 10, 'engineering-review-10'
        with self.assertRaises(ReviewHtmlError):
            render_review_html(changed)

    def test_review_eleven_size_caps_do_not_change_older_versions(self) -> None:
        data, legacy = review(), review(legacy=True)
        with patch('plc_workbench.review_html.MAX_REVIEW_V9_PAYLOAD_BYTES', 1):
            self.assertIn('binding-context-1', render_review_html(data))
            with self.assertRaises(ReviewHtmlSizeLimitError):
                render_review_html(legacy)
        with patch('plc_workbench.review_html.MAX_REVIEW_V11_PAYLOAD_BYTES', 1):
            with self.assertRaises(ReviewHtmlSizeLimitError):
                render_review_html(data)
            self.assertIn('engineering-review-10', render_review_html(legacy))


if __name__ == '__main__':
    unittest.main()
