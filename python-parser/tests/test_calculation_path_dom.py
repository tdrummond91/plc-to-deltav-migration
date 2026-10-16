"""Development-only DOM regression using invented source and optional Node.

This subprocess test is intentionally excluded from the work-machine allowlist.
"""
from __future__ import annotations

import json
import subprocess
import unittest

from plc_workbench.review import build_review_data
from plc_workbench.review_html import render_review_html
from test_access_review_ui import _NODE
from test_calculation_path_workflow import captured, options
from test_cpt_access_review_ui import DOM
from test_review import fixture
from test_review_html import ParsedPage


@unittest.skipUnless(_NODE, 'Node is optional development tooling for DOM checks.')
class CalculationPathDomTests(unittest.TestCase):
    def test_namespace_gap_destination_keeps_source_without_accepted_address_link(self) -> None:
        source = fixture(('MOV(A,Alias)MOV(A,B);',), tags=(
            '<Tag Name="Alias" TagType="Alias" AliasFor="B"/>'))[0].data
        source = source.replace(b'<RSLogix5000Content>',
                                b'<RSLogix5000Content xmlns:x="urn:foreign">')
        source = source.replace(b'AliasFor="B"', b'x:AliasFor="B"')
        parts = captured(source)
        data = build_review_data(*parts[:4], **options(parts))
        parsed = ParsedPage(render_review_html(data))
        checks = r"""
        const [gap,accepted]=input.data.calculation_paths.occurrences;
        assert.equal(gap.gap_reason,'namespace_gap');
        assert.equal(gap.destination_address_id,null);
        const original=input.data.relationships.addresses.find(a=>
          a.write_operand_ids.includes(gap.destination_operand_id));
        assert.ok(original,'Original relationship evidence must still exist.');
        assert.equal(accepted.destination_address_id,original.id);

        navigate('calculationpaths');
        const list=rows(tableNamed('Calculation block occurrences'));
        assert.ok(list[0].childNodes[2].textContent.includes('No accepted destination address'));
        assert.equal(list[0].childNodes[2].querySelectorAll('button').length,0);
        assert.equal(list[1].childNodes[2].textContent,'Address: B');
        list[0].childNodes[0].querySelector('button').click();
        const destination=content.querySelectorAll('section').find(s=>
          s.textContent.startsWith('Destination operand'));
        assert.ok(destination.textContent.includes('No accepted destination address'));
        assert.equal(destination.querySelectorAll('button').length,1);
        clickText(destination,'Alias · argument 2');
        assert.ok(heading.textContent.includes('Rung 0'));
        assert.ok(content.textContent.includes('Selected operand'));
        assert.ok(content.textContent.includes('MOV(A,Alias)MOV(A,B);'));

        navigate('calculationpaths');
        rows(tableNamed('Calculation block occurrences'))[1].childNodes[0].querySelector('button').click();
        const acceptedDestination=content.querySelectorAll('section').find(s=>
          s.textContent.startsWith('Destination operand'));
        clickText(acceptedDestination,'Address: B');
        assert.ok(heading.textContent.includes('EXACT ADDRESS EVIDENCE'));
        assert.ok(content.textContent.includes(accepted.destination_address_id));
        """
        result = subprocess.run([_NODE, '-e', DOM], input=json.dumps({
            'data': data, 'script': parsed.scripts[1][1], 'checks': checks}),
            text=True, encoding='utf-8', capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
