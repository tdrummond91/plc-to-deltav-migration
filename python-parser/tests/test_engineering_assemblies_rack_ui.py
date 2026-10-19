"""Development-only navigation of invented rack and direct source groups."""
from copy import deepcopy
from functools import lru_cache
import unittest

from plc_workbench.review import build_review_data
from plc_workbench.source_reuse import source_reuse_scope
from test_access_review_ui import _NODE
import test_engineering_assemblies_dom as assembly_dom
from test_rack_backing_context import fixture
from test_rack_backing_context_workflow import captured, options


@lru_cache(maxsize=2)
def report(bad_alias: bool = False) -> dict:
    source = fixture(tags='<Tag Name="Command" DataType="BOOL"/>'
                         '<Tag Name="Other" DataType="BOOL"/>', rungs=(
        'XIC(ProbeAlias)OTE(Command);',
        'XIC(Remote:I.Slot[3].Data.0)OTE(Other);',
        'XIC(Command)OTE(Remote:3:O.Data.0);',
        'GRT(5,1)OTE(Command);',
        'GSV(WallClockTime,?,DateTime,Command);',
    ))
    if bad_alias:
        source = source.replace('Name="ProbeAlias"', 'DataType="REAL" Name="ProbeAlias"')
    with source_reuse_scope():
        parts = captured(source.encode())
        return build_review_data(*parts[:4], **(options(parts) |
            {'engineering_assemblies_schema_version': 3}))


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI checks.')
class EngineeringAssembliesRackUiTests(unittest.TestCase):
    run_ui = assembly_dom.EngineeringAssembliesDomTests.run_ui

    def test_rack_occurrence_opens_joined_direct_and_sfc_source_group(self) -> None:
        self.run_ui(r"""
        navigate('rackbacking');
        assert.ok(content.textContent.includes('Qualified occurrences join cross-rung source groups'));
        rows(tableNamed('Rack source addresses')).find(r=>texts(r)[0].includes('Remote:3:I')).querySelector('button').click();
        const links=rows(tableNamed('Rack cross-rung groups'));
        assert.ok(links.length>=2);
        links.find(r=>r.textContent.includes('Slot[3].Data.0')).querySelector('button').click();
        const memberships=tableNamed('Cross-rung group memberships');
        assert.ok(memberships.textContent.includes('Transition reference and step context'));
        assert.ok(memberships.textContent.includes('Rack qualification: ProbeAlias'));
        assert.ok(rows(tableNamed('Cross-rung group source rungs')).length>=2);
        clickText(memberships,'Rack qualification: ProbeAlias');
        assert.ok(heading.textContent.includes('RACK SOURCE OCCURRENCE'));
        assert.ok(content.textContent.includes('Original predicate with binding gap'));
        """, report())

    def test_reverse_guard_navigation_reaches_target_with_original_gap_and_proof(self) -> None:
        self.run_ui(r"""
        navigate('assemblies');
        const search=document.getElementById('review-search');search.value='Command';search.events.input();
        rows(tableNamed('Cross-rung source groups')).find(r=>texts(r)[0]==='Command').querySelector('button').click();
        const reverse=rows(tableNamed('Cross-rung related addresses')).find(r=>r.textContent.includes('Output whose guard reads this address'));
        assert.ok(reverse);assert.ok(reverse.textContent.includes('Slot[3].Data.0'));
        assert.equal(texts(reverse)[2],'Guard input');
        assert.ok(texts(reverse)[3].startsWith('Output guard:'));
        reverse.childNodes[0].querySelector('button').click();
        const guard=rows(tableNamed('Cross-rung group memberships')).find(r=>texts(r)[1].startsWith('Output guard:'));
        assert.ok(guard.textContent.includes('Command'));
        clickText(guard,'Output guard and source fields');
        assert.ok(content.textContent.includes('unbound'));
        """, report())

    def test_known_values_are_explained_and_failed_alias_does_not_link(self) -> None:
        self.run_ui(r"""
        navigate('assemblies');assert.ok(content.textContent.includes('Literal guard inputs2'));
        assert.ok(content.textContent.includes('not counted as binding failures'));
        navigate('rackbacking');
        choose('Rack evidence','uses');choose('Filter Rack source addresses','gaps');
        const rejected=rows(tableNamed('Rack source occurrences'));assert.ok(rejected.length>0);
        rejected[0].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('alias metadata unqualified'));
        assert.ok(content.textContent.includes('No qualified membership retained'));
        assert.ok(!content.querySelectorAll('button').some(b=>b.textContent==='Command'));
        """, report(True))

    def test_reverse_link_display_remains_bounded(self) -> None:
        data = deepcopy(report())
        assembly = data['engineering_assemblies']
        anchor = next(m['related_address_id'] for m in assembly['memberships']
                      if m['relation'] == 'guard_condition' and m['related_address_id'])
        original = next(m for m in assembly['memberships'] if m['related_address_id'] == anchor)
        for index in range(510):
            assembly['memberships'].append(dict(original, id=f'ui-reverse-{index}',
                group_id=f'ui-other-{index}', instruction_id=None))
        self.run_ui(r"""
        navigate('assemblies');
        const m=assemblyTestData.engineering_assemblies.memberships.find(m=>m.relation==='guard_condition'&&m.related_address_id);
        const address=assemblyTestData.engineering_assemblies.groups.find(g=>g.id===m.related_address_id);
        const groups=assemblyTestData.engineering_assemblies.groups;
        rows(tableNamed('Cross-rung source groups'))[groups.indexOf(address)].querySelector('button').click();
        assert.ok(content.textContent.includes('Related-address display truncated'));
        assert.equal(rows(tableNamed('Cross-rung related addresses')).length,50);
        """, data)

    def test_gsv_question_mark_followup_identifies_external_evidence(self) -> None:
        self.run_ui(r"""
        navigate('residuals');const search=document.getElementById('review-search');
        search.value='GSV';search.events.input();
        const gsv=rows(tableNamed('Unresolved instruction analysis')).find(r=>texts(r)[0].startsWith('GSV '));
        assert.ok(gsv);assert.ok(gsv.textContent.includes('captured GSV instance is ?'));
        assert.ok(gsv.textContent.includes('vendor or controlled-exporter evidence'));
        assert.ok(!gsv.textContent.includes('rule or explicit control-flow treatment is still needed'));
        """, report())


if __name__ == '__main__':
    unittest.main()
