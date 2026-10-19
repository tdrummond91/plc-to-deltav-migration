"""Relationship publication contains only fixed counts and coherent totals."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.relationship_summary import (
    RelationshipSummaryError, build_relationship_summary, render_relationship_summary,
    validate_relationship_summary,
)
from test_relationships import capture, tag


def summary(texts=('MOV(A,B)ADD(B,1,C);',), **kwargs):
    return build_relationship_summary(*capture(texts, **kwargs))


class RelationshipSummaryTests(unittest.TestCase):
    def test_fixed_aggregate_is_bounded_deterministic_and_source_free(self) -> None:
        report = summary()
        rendered = render_relationship_summary(report)
        self.assertLessEqual(len(rendered), 6144)
        self.assertEqual(json.loads(rendered), report)
        self.assertEqual(rendered, render_relationship_summary(deepcopy(report)))
        self.assertEqual(report['coverage']['local_links_total'], 1)
        self.assertEqual(report['status'], 'complete')
        private = render_relationship_summary(summary(('MOV(SecretPlantTag,1);',), tags=tag('SecretPlantTag')))
        for word in ('SecretPlantTag', 'target_id', 'rung_id', 'MOV', 'relationship_address_'):
            self.assertNotIn(word, private)

    def test_empty_unparsed_branched_and_unknown_cases_are_valid(self) -> None:
        for texts in ((';',), ('[,];',), ('XIC(A',), ('Mystery(A);',), ('[XIC(A),]OTE(B);',),
                      ('CPT(A,1+2);',), ('MOV(1,2);',), ('PID(A,B,C,D,0,0,0);',)):
            with self.subTest(texts=texts):
                validate_relationship_summary(summary(texts))

    def test_invalid_composed_suffix_rejection_counts_are_consistent(self) -> None:
        report = summary(('MOV(Bit.Member,B)CPT(B,Bit.Member+B);',), tags=tag('A') + tag('B') + tag('Bit', 'A.1'))
        self.assertEqual(report['coverage']['identity_gaps_total'], 2)
        self.assertEqual(report['status'], 'partial')
        validate_relationship_summary(report)

    def test_closed_keys_native_types_and_constants_reject_leaks(self) -> None:
        mutations = (
            lambda r: r.update(private='text'),
            lambda r: r['coverage'].update(source='text'),
            lambda r: r['coverage']['pattern_skips'].update(private=0),
            lambda r: r['coverage'].update(source_rungs=True),
            lambda r: r['coverage'].update(source_rungs=1.0),
            lambda r: r['coverage'].update(source_rungs=-1),
            lambda r: r['coverage'].update(source_rungs=10**13),
            lambda r: r.update(schema_version=True),
            lambda r: r.update(overlap_analysis='complete'),
            lambda r: r.update(engineering_review='approved'),
            lambda r: r.update(status='approved'),
        )
        for mutate in mutations:
            candidate = summary()
            mutate(candidate)
            with self.subTest(mutation=mutate), self.assertRaises(RelationshipSummaryError):
                render_relationship_summary(candidate)

    def test_population_contradictions_are_rejected(self) -> None:
        mutations = (
            lambda c: c.update(source_rungs=2),
            lambda c: c.update(source_instructions=3),
            lambda c: c.update(source_operands=0),
            lambda c: c.update(expression_uses=1),
            lambda c: c.update(addresses_total=4),
            lambda c: c.update(identity_gaps_total=1),
            lambda c: c.update(indexed_expression_uses=1),
            lambda c: c.update(rejected_expression_uses=1),
            lambda c: c.update(cross_rung_addresses=1),
            lambda c: c.update(multiple_writer_addresses=2),
            lambda c: c.update(local_links_total=2),
            lambda c: c.update(local_link_rungs=0),
            lambda c: c.update(eligible_instructions=1, barrier_instructions=1),
            lambda c: c.update(patterns_total=0),
            lambda c: c.update(patterned_rungs=0),
            lambda c: c.update(skipped_rungs=1),
            lambda c: c.update(access_gap_operands=9),
            lambda c: c.update(unknown_role_operands=9),
            lambda c: c['address_profiles'].update(read_only=0),
            lambda c: c['local_link_kinds'].update(expression=1),
            lambda c: c['pattern_skips'].update(unparsed=1),
        )
        base = summary()
        for mutate in mutations:
            candidate = deepcopy(base)
            mutate(candidate['coverage'])
            with self.subTest(mutation=mutate), self.assertRaises(RelationshipSummaryError):
                validate_relationship_summary(candidate)
        candidate = deepcopy(base)
        candidate['status'] = 'partial'
        with self.assertRaises(RelationshipSummaryError):
            validate_relationship_summary(candidate)

    def test_revision_is_validated_and_copied(self) -> None:
        inputs = capture()
        revision = {'commit': 'a' * 40, 'worktree': 'clean'}
        report = build_relationship_summary(*inputs, revision=revision)
        revision['commit'] = 'b' * 40
        self.assertEqual(report['tool_revision']['commit'], 'a' * 40)
        for rev in ({'commit': None, 'worktree': 'clean'}, {'commit': 'a' * 40, 'worktree': 'unavailable'},
                    {'commit': '../secret', 'worktree': 'modified'}, {'commit': None, 'worktree': 'unknown'}):
            candidate = deepcopy(report)
            candidate['tool_revision'] = rev
            with self.subTest(revision=rev), self.assertRaises(RelationshipSummaryError):
                validate_relationship_summary(candidate)

    def test_forged_private_result_cannot_publish_plausible_counts(self) -> None:
        inputs = capture()
        result = replace(inputs[-1], local_links=[])
        with self.assertRaises(RelationshipSummaryError):
            build_relationship_summary(*inputs[:-1], result)

    def test_render_size_limit_remains_independent(self) -> None:
        report = summary()
        with patch('plc_workbench.relationship_summary.MAX_REPORT_BYTES', 1), self.assertRaises(RelationshipSummaryError):
            render_relationship_summary(report)


if __name__ == '__main__':
    unittest.main()
