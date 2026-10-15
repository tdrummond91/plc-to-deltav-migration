"""Strict count-only calculation publication from invented sources."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.calculation_summary import (
    CalculationSummaryError, build_calculation_summary, render_calculation_summary,
    validate_calculation_summary,
)
from test_calculations import capture


class CalculationSummaryTests(unittest.TestCase):
    def test_counts_have_no_source_names_values_offsets_or_links_and_stay_small(self) -> None:
        inputs = capture('A + A * 123.456')
        summary = build_calculation_summary(*inputs)
        encoded = render_calculation_summary(summary)
        self.assertLess(len(encoded.encode()), 2500)
        self.assertEqual(json.loads(encoded), summary)
        self.assertEqual(summary['coverage']['nodes_total'], 5)
        self.assertEqual(summary['coverage']['reference_occurrences'], 2)
        self.assertEqual(summary['status'], 'complete')
        for private in ('123.456', 'calculation_node_', 'operand_', 'instruction_', 'sha256:',
                        'raw_text', 'target_id', 'child_ids', 'start', 'end'):
            self.assertNotIn(private, encoded)

    def test_empty_partial_unsupported_and_mixed_populations_validate(self) -> None:
        texts = ('ADD(A,B,D);', 'CPT(D,A)CPT(D,Unknown)CPT(0,1);',
                 'CPT()CPT(D,)CPT(D,A+)CPT(D,PRIVATE(A));', 'CPT(D,A + (B);')
        for text in texts:
            with self.subTest(text=text):
                summary = build_calculation_summary(*capture(text=text))
                validate_calculation_summary(summary)

    def test_closed_metadata_revision_and_counter_types_are_enforced(self) -> None:
        summary = build_calculation_summary(*capture('A'))
        for mutation in (
            lambda value: value.update(extra='private'),
            lambda value: value.update(schema_version=True),
            lambda value: value.update(numeric_analysis='complete'),
            lambda value: value['tool_revision'].update(commit='a' * 40),
            lambda value: value['coverage'].update(nodes_total=True),
            lambda value: value['coverage'].update(unknown_count=1),
            lambda value: value['coverage']['nodes_by_kind'].update(unknown=1),
            lambda value: value['coverage']['expression_errors'].update(lexical_error=-1),
        ):
            changed = deepcopy(summary)
            mutation(changed)
            with self.assertRaises(CalculationSummaryError):
                validate_calculation_summary(changed)
        for worktree in ('clean', 'modified'):
            updated = build_calculation_summary(*capture('A'), revision={'commit': 'a' * 40, 'worktree': worktree})
            validate_calculation_summary(updated)

    def test_tree_partition_and_source_capacity_forgery_is_rejected(self) -> None:
        base = build_calculation_summary(*capture('A + B * 2'))
        mutations = (
            lambda c: c.update(source_operands=1),
            lambda c: c.update(source_instructions=0),
            lambda c: c.update(source_rungs=0),
            lambda c: c.update(occurrences_total=2),
            lambda c: c['occurrences_by_signature'].update(recognized=0),
            lambda c: c['expressions_by_status'].update(unsupported=1),
            lambda c: c['expression_errors'].update(syntax_error=1),
            lambda c: c['nodes_by_kind'].update(binary=0, unary=2),
            lambda c: c.update(reference_occurrences=1),
            lambda c: c['reference_by_binding'].update(root_bound=1),
            lambda c: c.update(destination_root_bound=2),
            lambda c: c.update(expressions_with_binding_gaps=1),
        )
        for mutation in mutations:
            changed = deepcopy(base)
            mutation(changed['coverage'])
            with self.assertRaises(CalculationSummaryError):
                validate_calculation_summary(changed)

    def test_binding_gaps_and_destination_failure_force_partial_status(self) -> None:
        for inputs in (capture('A + Missing'), capture('A', destination='0'), capture('A+')):
            summary = build_calculation_summary(*inputs)
            self.assertEqual(summary['status'], 'partial')
            summary['status'] = 'complete'
            with self.assertRaises(CalculationSummaryError):
                validate_calculation_summary(summary)
        summary = build_calculation_summary(*capture('A + Missing'))
        summary['coverage']['expressions_with_binding_gaps'] = 0
        with self.assertRaises(CalculationSummaryError):
            validate_calculation_summary(summary)

    def test_impossible_unary_depth_and_parenthesis_token_counts_are_rejected(self) -> None:
        base = build_calculation_summary(*capture('A'))
        for kind, count in (('unary', 100), ('group', 300)):
            changed = deepcopy(base)
            changed['coverage']['nodes_by_kind'][kind] = count
            changed['coverage']['nodes_total'] = 1 + count
            with self.assertRaises(CalculationSummaryError):
                validate_calculation_summary(changed)
        # A broad forest can satisfy the depth/leaf bound while requiring too
        # many name/parenthesis tokens for its function nodes.
        changed = deepcopy(base)
        c = changed['coverage']
        c.update(nodes_total=300, reference_occurrences=60)
        c['reference_by_binding']['root_bound'] = 60
        c['nodes_by_kind'].update(reference=60, binary=59, function=181)
        with self.assertRaises(CalculationSummaryError):
            validate_calculation_summary(changed)

    def test_publication_rejects_private_forgeries_and_oversize_output(self) -> None:
        snapshot, inventory, references, result = capture('A')
        changed = deepcopy(result)
        changed.nodes[0]['raw_text'] = 'OTHER'
        with self.assertRaises(CalculationSummaryError):
            build_calculation_summary(snapshot, inventory, references, changed)
        summary = build_calculation_summary(snapshot, inventory, references, result)
        with patch('plc_workbench.calculation_summary.MAX_REPORT_BYTES', 10):
            with self.assertRaises(CalculationSummaryError):
                render_calculation_summary(summary)


if __name__ == '__main__':
    unittest.main()
