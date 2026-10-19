"""Closed aggregates expose modeled ONS state structure without source values."""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from plc_workbench.condition_summary import (
    ConditionSummaryError, build_condition_summary, render_condition_summary,
    validate_condition_summary,
)
from test_condition_summary import summary
from test_stateful_conditions import stateful_capture
from test_relationships import tag


def stateful_summary(texts=('ONS(A)OTE(B);',), **kwargs):
    return build_condition_summary(*stateful_capture(texts, **kwargs))


class StatefulConditionSummaryTests(unittest.TestCase):
    def test_stateful_population_is_closed_and_condition_scope_can_be_complete(self) -> None:
        report = stateful_summary()
        c = report['coverage']
        self.assertEqual(report['schema_version'], 3)
        self.assertEqual(report['analyzer_version'], 'condition-analysis-3')
        self.assertEqual(report['exporter_version'], 'condition-summary-3')
        self.assertEqual(c['stateful_opcodes'], {'ONS': 1})
        self.assertEqual(c['node_kinds']['stateful_transfer'], 1)
        self.assertEqual(c['binding_gap_stateful'], 0)
        self.assertEqual(c['outputs_with_stateful_conditions'], 1)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['execution_analysis'], 'not_implemented')
        self.assertLessEqual(len(render_condition_summary(report)), 4096)

    def test_state_storage_gaps_are_partial_even_without_coils(self) -> None:
        report = stateful_summary(('ONS(Missing);',))
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['coverage']['outputs_with_stateful_conditions'], 0)
        self.assertEqual(report['coverage']['binding_gap_stateful'], 1)
        self.assertEqual(report['coverage']['binding_gap_predicates'], 0)
        report = stateful_summary(('ONS(S:FS)OTE(A);',))
        self.assertEqual(report['coverage']['guard_statuses']['binding_gaps'], 1)
        validate_condition_summary(report)

    def test_mixed_instruction_partition_and_ons_signature_failures_conserve(self) -> None:
        report = stateful_summary(('XIC(A)ONS(B)MOV(A,C)OTE(D)ONS(B,C)Mystery(A)OTL(C);',))
        c = report['coverage']
        self.assertEqual(c['source_instructions'], 7)
        self.assertEqual(c['node_kinds']['stateful_transfer'], 1)
        self.assertEqual(c['node_kinds']['pass_through'], 1)
        self.assertEqual(c['opaque_reasons'], {'signature_unresolved': 1, 'unsupported_condition_behavior': 1})
        self.assertEqual(c['outputs_with_stateful_conditions'], 2)
        self.assertEqual(c['guard_statuses'], {'modeled': 1, 'binding_gaps': 0, 'opaque': 1})

    def test_empty_unparsed_and_nonstateful_sources_have_zero_state_counts(self) -> None:
        for texts in ((';',), ('XIC(A',), ('MOV(A,B)OTE(C);',), ('[ONS(),]OTE(A);',)):
            with self.subTest(texts=texts):
                report = stateful_summary(texts)
                self.assertEqual(report['coverage']['stateful_opcodes'], {'ONS': 0})
                self.assertEqual(report['coverage']['outputs_with_stateful_conditions'], 0)
                validate_condition_summary(report)
        validate_condition_summary(stateful_summary(texts=(), rung_xml=''))

    def test_new_counts_cannot_publish_text_nonintegers_or_impossible_populations(self) -> None:
        mutations = (
            lambda r: r['coverage']['stateful_opcodes'].update(OSR=0),
            lambda r: r['coverage']['stateful_opcodes'].update(ONS=0),
            lambda r: r['coverage']['node_kinds'].update(stateful_transfer=0),
            lambda r: r['coverage'].update(binding_gap_stateful=2),
            lambda r: r['coverage'].update(binding_gap_stateful=True),
            lambda r: r['coverage'].update(binding_gap_stateful=1.0),
            lambda r: r['coverage'].update(outputs_with_stateful_conditions=2),
            lambda r: r['coverage'].update(outputs_with_stateful_conditions=-1),
            lambda r: r['coverage'].update(outputs_with_stateful_conditions=10**13),
            lambda r: r['coverage'].update(stateful_storage='PrivateStorage'),
            lambda r: r['coverage'].pop('binding_gap_stateful'),
            lambda r: r['coverage'].pop('outputs_with_stateful_conditions'),
            lambda r: r.update(status='partial'),
        )
        base = stateful_summary()
        for mutate in mutations:
            candidate = deepcopy(base)
            mutate(candidate)
            with self.subTest(mutate=mutate), self.assertRaises(ConditionSummaryError):
                render_condition_summary(candidate)

    def test_stateful_output_requires_a_stateful_node_and_gap_requires_a_cause(self) -> None:
        base = stateful_summary(('OTE(A);',))
        for mutate in (lambda c: c.update(outputs_with_stateful_conditions=1),
                       lambda c: c.update(binding_gap_stateful=1),
                       lambda c: c['guard_statuses'].update(modeled=0, binding_gaps=1)):
            report = deepcopy(base)
            mutate(report['coverage'])
            with self.subTest(mutate=mutate), self.assertRaises(ConditionSummaryError):
                validate_condition_summary(report)

    def test_legacy_summaries_keep_old_fields_and_versions_cannot_be_disguised(self) -> None:
        for version in (1, 2):
            old = summary(('ONS(A)OTE(B);',), schema_version=version)
            before = render_condition_summary(old)
            self.assertNotIn('stateful_opcodes', old['coverage'])
            self.assertNotIn('binding_gap_stateful', old['coverage'])
            self.assertNotIn('outputs_with_stateful_conditions', old['coverage'])
            self.assertEqual(old['coverage']['node_kinds']['opaque_transfer'], 1)
            self.assertEqual(before, render_condition_summary(summary(('ONS(A)OTE(B);',), schema_version=version)))
            forged = deepcopy(old)
            forged.update(schema_version=3, analyzer_version='condition-analysis-3', exporter_version='condition-summary-3')
            with self.assertRaises(ConditionSummaryError):
                validate_condition_summary(forged)
            forged = stateful_summary()
            forged.update(schema_version=version, analyzer_version=f'condition-analysis-{version}',
                          exporter_version=f'condition-summary-{version}')
            with self.assertRaises(ConditionSummaryError):
                validate_condition_summary(forged)

    def test_storage_only_gap_guards_must_retain_stateful_marker_population(self) -> None:
        report = stateful_summary(('ONS(Missing)OTE(A)OTL(B);',))
        self.assertEqual(report['coverage']['guard_statuses']['binding_gaps'], 2)
        self.assertEqual(report['coverage']['outputs_with_stateful_conditions'], 2)
        report['coverage']['outputs_with_stateful_conditions'] = 1
        with self.assertRaises(ConditionSummaryError):
            validate_condition_summary(report)

    def test_no_source_storage_names_identifiers_or_read_values_are_published(self) -> None:
        report = stateful_summary(('ONS(InventedStorage)OTE(InventedOutput);',),
                                  tags=tag('InventedStorage') + tag('InventedOutput'))
        rendered = render_condition_summary(report)
        for text in ('InventedStorage', 'InventedOutput', 'operand_id', 'condition_node_',
                     'storage_before', 'storage_after', 'has_stateful'):
            self.assertNotIn(text, rendered)

    def test_stateful_payload_forgery_is_rejected_before_publication(self) -> None:
        inputs = list(stateful_capture())
        inputs[-1] = deepcopy(inputs[-1])
        inputs[-1].outputs[0]['has_stateful'] = False
        with self.assertRaises(ConditionSummaryError):
            build_condition_summary(*inputs)

    def test_new_summary_remains_independently_byte_bounded(self) -> None:
        report = stateful_summary()
        with patch('plc_workbench.condition_summary.MAX_REPORT_BYTES', 1), self.assertRaises(ConditionSummaryError):
            render_condition_summary(report)


if __name__ == '__main__':
    unittest.main()
