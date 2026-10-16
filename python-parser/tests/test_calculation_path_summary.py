"""Closed, name-free publication counts for isolated calculation regions."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.calculation_path_summary import (CalculationPathSummaryError,
    build_calculation_path_summary, render_calculation_path_summary, validate_calculation_path_summary)
from test_calculation_paths import capture, capture_xml
from test_relationships import tag


class CalculationPathSummaryTests(unittest.TestCase):
    def test_canonical_summary_is_closed_bounded_and_contains_no_source(self) -> None:
        args = capture(('MOV(932871,B)[MOV(B,C)CPT(D,C+C),CLR(B)ADD(B,1,C)];',))
        summary = build_calculation_path_summary(*args, revision={'commit': 'a' * 40, 'worktree': 'clean'})
        text = render_calculation_path_summary(summary)
        self.assertLess(len(text.encode()), 4096)
        self.assertEqual(json.loads(text), summary)
        self.assertNotIn('932871', text)
        self.assertNotIn('instruction_', text)
        self.assertNotIn('rung_', text.replace('rung_entry', '').replace('rung_end', ''))
        self.assertEqual(summary['coverage']['links_total'], 3)
        self.assertEqual(summary['coverage'], args[-1].coverage)
        self.assertEqual(summary['exporter_version'], 'calculation-path-summary-1')

    def test_valid_edge_cases_preserve_gap_and_condition_partition(self) -> None:
        for text in (';', 'XIC(A);', 'BROKEN(', 'MOV(A);', 'CPT(A,ATAN2(B,C));',
                     'MOV(A[B],C);', 'XIC(Missing)MOV(A,B);',
                     'ONS(D)CLR(A);', 'MYSTERY(A)MOV(A,B)MOV(B,C);', 'CLR(A);', 'CPT(A,1+2);',
                     'MOV(A,B)[,]MOV(B,C);'):
            with self.subTest(text=text):
                args = capture((text,))
                summary = build_calculation_path_summary(*args)
                validate_calculation_path_summary(summary)
                self.assertEqual(summary['status'], args[-1].status)
        xml = capture(('MOV(A,B)MOV(B,C);',), tags=tag('A') + tag('B') + tag('C', 'B'))[0].data.decode()
        xml = xml.replace('<RSLogix5000Content>', '<RSLogix5000Content xmlns:x="urn:foreign">')
        args = capture_xml(xml.replace('AliasFor="B"', 'x:AliasFor="B"'))
        validate_calculation_path_summary(build_calculation_path_summary(*args))

    def test_rejects_foreign_keys_boolean_counts_revision_and_constants(self) -> None:
        good = build_calculation_path_summary(*capture())
        for mutate in (lambda s: s.update(source_name='private'),
                       lambda s: s['coverage']['blocks_by_opcode'].update(SECRET=1),
                       lambda s: s['coverage'].update(source_rungs=True),
                       lambda s: s['coverage'].update(source_rungs=-1),
                       lambda s: s['tool_revision'].update(commit='private'),
                       lambda s: s.update(schema_version=True),
                       lambda s: s.update(status='partial')):
            bad = deepcopy(good)
            mutate(bad)
            with self.subTest(bad=bad), self.assertRaises(CalculationPathSummaryError):
                validate_calculation_path_summary(bad)

    def test_exact_partitions_and_region_membership_counts_are_enforced(self) -> None:
        good = build_calculation_path_summary(*capture())
        fields = ('occurrences_total', 'regions_total', 'region_blocks_total', 'source_instructions',
                  'input_operands_total', 'selected_rungs', 'links_total')
        for field in fields:
            bad = deepcopy(good)
            bad['coverage'][field] += 1
            with self.subTest(field=field), self.assertRaises(CalculationPathSummaryError):
                validate_calculation_path_summary(bad)
        for group, key in (('blocks_by_opcode', 'MOV'), ('blocks_by_status', 'eligible'),
                           ('condition_quality', 'modeled'), ('region_starts', 'branch_entry'),
                           ('region_ends', 'branch_end'), ('links_by_kind', 'expression')):
            bad = deepcopy(good)
            bad['coverage'][group][key] += 1
            with self.subTest(group=group), self.assertRaises(CalculationPathSummaryError):
                validate_calculation_path_summary(bad)

    def test_rejects_linked_read_and_region_capacity_forgeries(self) -> None:
        good = build_calculation_path_summary(*capture(('MOV(A,B)CPT(C,B+B);',)))
        for mutate in (lambda c: c.update(eligible_expression_uses=1),
                       lambda c: c.update(linked_blocks=2),
                       lambda c: c.update(linked_regions=2),
                       lambda c: c.update(eligible_read_inputs=c['address_input_operands'] + 1),
                       lambda c: c.update(branched_regions=1),
                       lambda c: c.update(expression_input_operands=0, unresolved_input_operands=1),
                       lambda c: c.update(overlap_invalidations=c['blocks_by_status']['eligible'] + 1)):
            bad = deepcopy(good)
            mutate(bad['coverage'])
            with self.subTest(bad=bad), self.assertRaises(CalculationPathSummaryError):
                validate_calculation_path_summary(bad)

    def test_gap_blocks_are_isolated_and_barrier_subsets_are_enforced(self) -> None:
        good = build_calculation_path_summary(*capture(('MOV(A)MOV(A,B);',)))
        for mutate in (lambda c: c['region_ends'].update(block_gap=0, rung_end=2),
                       lambda c: c['barriers_by_reason'].update(access_not_classified=0, other_instruction=1),
                       lambda c: c['condition_quality'].update(modeled=0, unavailable=2),
                       lambda c: c.update(regions_total=1, region_starts={'barrier': 0, 'branch_entry': 0, 'branch_join': 0, 'rung_entry': 1},
                                          region_ends={'barrier': 0, 'block_gap': 1, 'branch_end': 0, 'branch_fork': 0, 'rung_end': 0}, linked_regions=1)):
            bad = deepcopy(good)
            mutate(bad['coverage'])
            with self.subTest(bad=bad), self.assertRaises(CalculationPathSummaryError):
                validate_calculation_path_summary(bad)

    def test_replay_authentication_and_public_byte_limit(self) -> None:
        args = capture()
        bad = deepcopy(args[-1])
        bad.occurrences[0]['destination_operand_id'] = 'invented'
        with self.assertRaises(CalculationPathSummaryError) as caught:
            build_calculation_path_summary(*args[:-1], bad)
        self.assertNotIn('invented', str(caught.exception))
        good = build_calculation_path_summary(*args)
        with patch('plc_workbench.calculation_path_summary.MAX_REPORT_BYTES', 20), self.assertRaises(CalculationPathSummaryError):
            render_calculation_path_summary(good)
        with patch('plc_workbench.calculation_path_summary.MAX_CALCULATION_PATH_BYTES', 20), self.assertRaises(CalculationPathSummaryError):
            validate_calculation_path_summary(good)


if __name__ == '__main__':
    unittest.main()
