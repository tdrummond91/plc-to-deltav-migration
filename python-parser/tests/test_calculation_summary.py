"""Strict count-only calculation publication from invented sources."""
from __future__ import annotations

from copy import deepcopy
import hashlib
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

    def test_fixed_function_counts_publish_no_unknown_function_identity(self) -> None:
        inputs = capture(text=('CPT(D,SQR(ABS(A))+SQRT(B))'
                               'CPT(D,ABS(A)+ATAN2(A,B)+PRIVATE_LATER(C))'
                               'CPT(D,PRIVATE_FIRST(A)+ATAN2(A,B));'))
        summary = build_calculation_summary(*inputs)
        self.assertEqual((summary['schema_version'], summary['analyzer_version'], summary['exporter_version']),
                         (2, 'calculation-evidence-2', 'calculation-summary-2'))
        self.assertEqual(summary['coverage']['functions_by_spelling']['SQR'], 1)
        self.assertEqual(summary['coverage']['functions_by_spelling']['SQRT'], 1)
        self.assertEqual(summary['coverage']['functions_by_spelling']['ABS'], 1)
        self.assertEqual(sum(summary['coverage']['functions_by_spelling'].values()), 3)
        self.assertEqual(summary['coverage']['unsupported_functions'], {'atan2': 1, 'other': 1})
        encoded = render_calculation_summary(summary)
        for private in ('PRIVATE_FIRST', 'PRIVATE_LATER', 'raw_text', 'error_offset', 'SQR(ABS'):
            self.assertNotIn(private, encoded)
        self.assertLess(len(encoded.encode()), 3 * 1024)

    def test_function_histogram_partitions_and_closed_vocabularies_are_enforced(self) -> None:
        base = build_calculation_summary(*capture(text='CPT(D,SQR(A))CPT(D,ATAN2(A,B));'))
        for mutate in (
            lambda c: c['functions_by_spelling'].update(SQR=0),
            lambda c: c['functions_by_spelling'].update(SQRT=1),
            lambda c: c['functions_by_spelling'].pop('SQR'),
            lambda c: c['functions_by_spelling'].update(sqr=0),
            lambda c: c['functions_by_spelling'].update(PRIVATE_NAME=0),
            lambda c: c['functions_by_spelling'].update(SQR=True),
            lambda c: c['functions_by_spelling'].update(SQR=-1),
            lambda c: c['unsupported_functions'].update(atan2=0),
            lambda c: c['unsupported_functions'].update(other=1),
            lambda c: c['unsupported_functions'].update(ATAN2=0),
            lambda c: c['unsupported_functions'].update(private_name=0),
            lambda c: c['unsupported_functions'].update(atan2=True),
            lambda c: c['unsupported_functions'].pop('other'),
        ):
            changed = deepcopy(base)
            mutate(changed['coverage'])
            with self.assertRaises(CalculationSummaryError):
                validate_calculation_summary(changed)

    def test_frozen_schema_one_summary_replays_exact_bytes_and_rejects_new_fields(self) -> None:
        text = 'CPT(D,SQRT(A)+ABS(-B))CPT(D,SQR(A))CPT(D,ATAN2(A,B));'
        summary = build_calculation_summary(*capture(text=text, schema_version=1))
        encoded = render_calculation_summary(summary)
        self.assertEqual(hashlib.sha256(encoded.encode()).hexdigest(),
                         '6beba81055151c5bb097a9ba713c4380b3049ca09be028434e71ce57e5002697')
        self.assertEqual((summary['schema_version'], summary['analyzer_version'], summary['exporter_version']),
                         (1, 'calculation-evidence-1', 'calculation-summary-1'))
        current = build_calculation_summary(*capture(text=text))
        for key in ('functions_by_spelling', 'unsupported_functions'):
            changed = deepcopy(summary)
            changed['coverage'][key] = current['coverage'][key]
            with self.assertRaises(CalculationSummaryError):
                validate_calculation_summary(changed)
        for base, replacement in ((summary, current), (current, summary)):
            for field in ('schema_version', 'analyzer_version', 'exporter_version'):
                changed = deepcopy(base)
                changed[field] = replacement[field]
                with self.assertRaises(CalculationSummaryError):
                    validate_calculation_summary(changed)

    def test_summary_version_rejects_noninteger_and_unknown_versions(self) -> None:
        summary = build_calculation_summary(*capture('A'))
        for version in (True, False, 0, 3, 1.0, '1', None):
            changed = deepcopy(summary)
            changed['schema_version'] = version
            with self.subTest(version=version), self.assertRaises(CalculationSummaryError):
                validate_calculation_summary(changed)


if __name__ == '__main__':
    unittest.main()
