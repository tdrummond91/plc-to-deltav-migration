"""Exercise CPT access navigation using invented snapshots and an optional DOM."""
from __future__ import annotations

import json
import subprocess
import unittest

from plc_workbench.access import analyze_access
from plc_workbench.calculations import analyze_calculations
from plc_workbench.pid import analyze_pid
from plc_workbench.pid_members import analyze_pid_members
from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from plc_workbench.tag_data import analyze_tag_data
from test_access_review_ui import _DOM, _NODE
from test_review import fixture
from test_review_html import ParsedPage


# Calculation grouping uses inline indentation; the shared tiny DOM otherwise
# already implements the APIs these tests need. It remains development tooling.
DOM = _DOM.replace('this.dataset={};', 'this.dataset={};this.style={};')


def review(texts: tuple[str, ...] = (
    'CPT(A,A+A)CPT(B,Alias.Member+Alias.Member);',
    'CPT(Constant,2+3);',
    'CPT(B,ATAN2(A,A))CPT(B,Missing+1);',
    'CPT(B,A<1);',
), *, schema_version: int = 4) -> dict:
    args = fixture(texts, tags=(
        '<Tag Name="OnlyExpression" TagType="Base" DataType="DINT"/>'
        '<Tag Name="AliasMiddle" TagType="Alias" AliasFor="OnlyExpression[2]"/>'
        '<Tag Name="Alias" TagType="Alias" AliasFor="AliasMiddle"/>'
        '<Tag Name="Constant" TagType="Base" DataType="DINT"/>'))
    calculations = analyze_calculations(*args[:3])
    access = analyze_access(args[1], args[2], schema_version=schema_version,
                            **({'snapshot': args[0], 'calculations': calculations}
                               if schema_version >= 4 else {}))
    tag_data = analyze_tag_data(*args[:2])
    pid = analyze_pid(*args[:3], tag_data)
    members = analyze_pid_members(*args[:3], tag_data, pid)
    return build_review_data(*args, access=access, tag_data=tag_data, pid=pid,
                             pid_members=members, calculations=calculations)


@unittest.skipUnless(_NODE, 'Node is optional development tooling for UI behavior checks.')
class CptAccessReviewUiTests(unittest.TestCase):
    def run_ui(self, data: dict, checks: str) -> None:
        parsed = ParsedPage(render_review_html(data))
        process = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': data, 'script': parsed.scripts[1][1], 'checks': checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_separate_leaf_counts_expression_only_roots_and_same_root_write(self) -> None:
        self.run_ui(review(), r"""
        navigate('access');
        const roots=tableNamed('Root access groups');
        assert.deepEqual(texts(rowNamed(roots,'A')).slice(2),['0','1','0','0','2']);
        const only=rowNamed(roots,'OnlyExpression');
        assert.deepEqual(texts(only).slice(2),['0','0','0','0','2']);
        assert.deepEqual(texts(rowNamed(roots,'Constant')).slice(2),['0','1','0','0','0']);
        assert.ok(content.textContent.includes('Expression reference read occurrences'));
        only.childNodes[6].querySelector('button').click();
        assert.ok(!content.querySelectorAll('table').some(t=>t.textContent.includes('Root access occurrences')));
        const leaves=tableNamed('Root expression read occurrences');
        assert.equal(rows(leaves).length,2);
        assert.deepEqual(rows(leaves).map(r=>texts(r)[1]),['[0, 12)','[13, 25)']);
        assert.deepEqual(rows(leaves).map(r=>texts(r)[5]),['[2].Member','[2].Member']);
        rows(leaves)[1].childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('Selected expression read'));
        const selection=content.querySelectorAll('section').find(n=>n.textContent.startsWith('Selected expression read'));
        assert.ok(selection.textContent.includes('[13, 25)'));
        assert.ok(selection.textContent.includes('Alias.Member'));
        assert.ok(selection.textContent.includes('Calculation node ID'));
        assert.ok(selection.querySelectorAll('button').some(n=>n.textContent.startsWith('Rung 0')));
        navigate('objects');clickText(tableNamed('Source objects'),'A');
        clickText(content,'Inspect root access occurrences');
        assert.equal(rows(tableNamed('Root access occurrences')).length,1);
        assert.equal(texts(rows(tableNamed('Root access occurrences'))[0])[1],'write');
        assert.equal(rows(tableNamed('Root expression read occurrences')).length,2);
        """)

    def test_alias_declaration_and_intermediate_alias_reverse_use_links(self) -> None:
        self.run_ui(review(), r"""
        for(const name of ['Alias','AliasMiddle','OnlyExpression']){
          navigate('objects');clickText(tableNamed('Source objects'),name);
          const leaves=tableNamed('Object expression read occurrences');
          assert.equal(rows(leaves).length,2,name);
          const roots=rows(leaves)[0].childNodes[4].querySelectorAll('button').map(n=>n.textContent);
          assert.ok(roots.includes('Alias'));assert.ok(roots.includes('AliasMiddle'));
          assert.ok(roots.includes('OnlyExpression'));
        }
        """)

    def test_unsupported_containers_and_unresolved_leaves_have_distinct_gaps(self) -> None:
        self.run_ui(review(), r"""
        navigate('access');
        const unsupported=tableNamed('Unsupported expression accesses');
        assert.equal(rows(unsupported).length,2);
        assert.deepEqual(rows(unsupported).map(r=>texts(r)[0]),['ATAN2(A,A)','A<1']);
        const unbound=tableNamed('Unresolved expression reads');
        assert.deepEqual(rows(unbound).map(r=>texts(r)[0]),['Missing']);
        assert.ok(!content.querySelectorAll('table').some(t=>t.childNodes.some(c=>c.tagName==='CAPTION'&&c.textContent==='Unresolved operand accesses')));
        const escaped=rowNamed(unsupported,'A<1');
        escaped.childNodes[0].querySelector('button').click();
        assert.ok(content.textContent.includes('A<1'));
        assert.ok(content.textContent.includes('Expression parsing gap'));
        assert.ok(!content.querySelectorAll('table').some(t=>t.childNodes.some(c=>c.tagName==='CAPTION'&&c.textContent==='Calculation expression references')));
        """)

    def test_container_navigation_preserves_original_reference_finding(self) -> None:
        self.run_ui(review(), r"""
        navigate('ladder');clickText(content,'Rung 0');
        const original=rowNamed(tableNamed('Rung operand bindings'),'A+A');
        assert.ok(texts(original)[2].includes('unsupported expression'));
        assert.equal(texts(original)[4],'expression read');
        const container=rowNamed(tableNamed('Rung instruction access bindings'),'A+A');
        assert.equal(texts(container)[2],'expression read');
        assert.ok(texts(container)[3].includes('parsed expression'));
        assert.ok(!texts(container)[4].includes('No root'));
        clickText(container,'Open expression');
        assert.ok(heading.textContent.includes('CPT'));
        assert.equal(rows(tableNamed('Calculation expression references')).length,2);
        navigate('findings');
        const finding=rows(tableNamed('Review findings')).find(r=>r.textContent.includes('A+A'));
        assert.ok(finding);finding.querySelectorAll('button')[0].click();
        assert.ok(content.textContent.includes('This finding retains the original reference status.'));
        assert.ok(tableNamed('Finding instruction access binding').textContent.includes('parsed expression'));
        """)

    def test_constant_expression_and_paged_repeated_reads(self) -> None:
        self.run_ui(review(('CPT(Constant,2+3);',)), r"""
        navigate('ladder');clickText(content,'Rung 0');
        clickText(tableNamed('Rung instruction access bindings'),'Open expression');
        assert.ok(content.textContent.includes('No reference leaves in this parsed expression'));
        """)
        self.run_ui(review(('CPT(B,' + '+'.join(['Alias.Member'] * 51) + ');',)), r"""
        navigate('objects');clickText(tableNamed('Source objects'),'Alias');
        assert.equal(rows(tableNamed('Object expression read occurrences')).length,50);
        content.querySelectorAll('button').find(n=>n.attributes['aria-label']==='Next page: Object expression read occurrences').click();
        const last=tableNamed('Object expression read occurrences');assert.equal(rows(last).length,1);
        assert.equal(texts(rows(last)[0])[1],'[650, 662)');
        clickText(last,'Alias.Member');
        const selection=content.querySelectorAll('section').find(n=>n.textContent.startsWith('Selected expression read'));
        assert.ok(selection.textContent.includes('[650, 662)'));
        """)

    def test_legacy_access_has_no_expression_read_column_or_new_root_claim(self) -> None:
        for version in (2, 3):
            with self.subTest(version=version):
                self.run_ui(review(('XIC(A)CPT(B,Alias.Member);',), schema_version=version), r"""
                navigate('access');
                const roots=tableNamed('Root access groups');
                assert.equal(rows(roots)[0].childNodes.length,6);
                assert.ok(!rows(roots).some(r=>texts(r)[0]==='OnlyExpression'));
                assert.ok(!content.textContent.includes('Parsed expression containers'));
                navigate('objects');clickText(tableNamed('Source objects'),'Alias');
                assert.ok(content.textContent.includes('Calculation occurrences'));
                assert.ok(!content.textContent.includes('Expression read occurrences'));
                """)


if __name__ == '__main__':
    unittest.main()
