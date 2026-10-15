"""Only closed, coherent normal-scan condition counts may be published."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.condition_summary import (
    ConditionSummaryError, build_condition_summary, render_condition_summary, validate_condition_summary,
)
from test_conditions import capture
from test_relationships import tag


def summary(texts=('XIC(A)OTE(B);',), **kwargs):
    return build_condition_summary(*capture(texts, **kwargs))


class ConditionSummaryTests(unittest.TestCase):
    def test_closed_counts_are_small_deterministic_and_source_free(self) -> None:
        report = summary()
        rendered = render_condition_summary(report)
        self.assertLessEqual(len(rendered), 4096)
        self.assertEqual(json.loads(rendered), report)
        self.assertEqual(rendered, render_condition_summary(deepcopy(report)))
        self.assertEqual(report['coverage']['outputs_total'], 1)
        self.assertEqual(report['status'], 'complete')
        private = render_condition_summary(summary(('XIC(SecretPlantTag)OTE(SecretPlantTag);',), tags=tag('SecretPlantTag')))
        for text in ('SecretPlantTag', 'target_address_id', 'guard_id', 'condition_node_', 'condition_output_'):
            self.assertNotIn(text, private)

    def test_edge_sources_have_consistent_summaries(self) -> None:
        for texts in ((';',), ('[,];',), ('XIC(A',), ('Unknown(A);',), ('OTE(A,B)OTE(C);',),
                      ('XIC(Missing)OTE(D);',), ('OTE(Missing);',), ('EQU(1,2)OTE(A);',),
                      ('[XIC(A)OTE(B),]OTL(C);',), ('MOV(A,B);',)):
            with self.subTest(texts=texts):
                validate_condition_summary(summary(texts))
        validate_condition_summary(summary(texts=(), rung_xml=''))

    def test_invalid_alias_composition_is_counted_not_exposed(self) -> None:
        report = summary(('XIC(Bit.Member)OTE(Bit.Member);',), tags=tag('A') + tag('Bit', 'A.1'))
        self.assertEqual(report['coverage']['binding_gap_predicates'], 1)
        self.assertEqual(report['coverage']['target_statuses']['identity_gap'], 1)
        self.assertEqual(report['status'], 'partial')

    def test_closed_keys_native_types_and_constants_reject_leaks(self) -> None:
        mutations = (
            lambda r: r.update(private='text'),
            lambda r: r['coverage'].update(source='text'),
            lambda r: r['coverage']['node_kinds'].update(private=0),
            lambda r: r['coverage'].update(source_rungs=True),
            lambda r: r['coverage'].update(source_rungs=1.0),
            lambda r: r['coverage'].update(source_rungs=-1),
            lambda r: r['coverage'].update(source_rungs=10**13),
            lambda r: r.update(schema_version=True),
            lambda r: r.update(evaluation_scope='all_scans'),
            lambda r: r.update(engineering_review='approved'),
            lambda r: r.update(status='approved'),
        )
        base = summary()
        for mutate in mutations:
            candidate = deepcopy(base)
            mutate(candidate)
            with self.subTest(mutation=mutate), self.assertRaises(ConditionSummaryError):
                render_condition_summary(candidate)

    def test_inconsistent_populations_and_impossible_flags_are_rejected(self) -> None:
        mutations = (
            lambda c: c.update(source_rungs=2),
            lambda c: c.update(source_instructions=3),
            lambda c: c.update(source_operands=0),
            lambda c: c.update(nodes_total=4),
            lambda c: c.update(outputs_total=2),
            lambda c: c.update(rungs_with_outputs=0),
            lambda c: c.update(output_addresses=0),
            lambda c: c.update(output_addresses=2),
            lambda c: c.update(branch_joins=1),
            lambda c: c.update(branch_legs=1),
            lambda c: c.update(binding_gap_predicates=2),
            lambda c: c.update(outputs_with_branches=1),
            lambda c: c['predicate_opcodes'].update(XIC=0),
            lambda c: c['output_opcodes'].update(OTL=1),
            lambda c: c['node_kinds'].update(all=0),
            lambda c: c['action_statuses'].update(unresolved=1),
            lambda c: c['target_statuses'].update(exact_address=0, signature_unresolved=1),
            lambda c: c['guard_statuses'].update(modeled=0, opaque=1),
            lambda c: c['guard_statuses'].update(modeled=0, binding_gaps=1),
        )
        base = summary()
        for mutate in mutations:
            candidate = deepcopy(base)
            mutate(candidate['coverage'])
            with self.subTest(mutation=mutate), self.assertRaises(ConditionSummaryError):
                validate_condition_summary(candidate)
        candidate = deepcopy(base)
        candidate['status'] = 'partial'
        with self.assertRaises(ConditionSummaryError):
            validate_condition_summary(candidate)

    def test_signature_and_opaque_counts_remain_separate(self) -> None:
        report = summary(('XIC(A,B)Unknown(A)OTE(C,D)OTE(A);',))
        self.assertEqual(report['coverage']['opaque_reasons'], {'signature_unresolved': 2, 'unsupported_condition_behavior': 1})
        self.assertEqual(report['coverage']['action_statuses'], {'recognized': 1, 'unresolved': 1})
        validate_condition_summary(report)

    def test_revision_is_validated_and_copied(self) -> None:
        revision = {'commit': 'a' * 40, 'worktree': 'clean'}
        report = build_condition_summary(*capture(), revision=revision)
        revision['commit'] = 'b' * 40
        self.assertEqual(report['tool_revision']['commit'], 'a' * 40)
        for value in ({'commit': None, 'worktree': 'clean'}, {'commit': 'a' * 40, 'worktree': 'unavailable'},
                      {'commit': '../Secret', 'worktree': 'modified'}, {'commit': None, 'worktree': 'unknown'}):
            candidate = deepcopy(report)
            candidate['tool_revision'] = value
            with self.subTest(value=value), self.assertRaises(ConditionSummaryError):
                validate_condition_summary(candidate)

    def test_forged_private_graph_cannot_publish_plausible_counts(self) -> None:
        inputs = capture()
        result = replace(inputs[-1], nodes=[])
        with self.assertRaises(ConditionSummaryError):
            build_condition_summary(*inputs[:-1], result)

    def test_nonnative_container_types_are_rejected_without_hooks(self) -> None:
        class Hostile(dict):
            def keys(self):
                raise AssertionError('Custom hook ran')
        report = summary()
        for field in ('coverage', 'tool_revision'):
            candidate = deepcopy(report)
            candidate[field] = Hostile(candidate[field])
            with self.subTest(field=field), self.assertRaises(ConditionSummaryError):
                validate_condition_summary(candidate)

    def test_report_byte_limit_is_independent(self) -> None:
        report = summary()
        with patch('plc_workbench.condition_summary.MAX_REPORT_BYTES', 1), self.assertRaises(ConditionSummaryError):
            render_condition_summary(report)


if __name__ == '__main__':
    unittest.main()
