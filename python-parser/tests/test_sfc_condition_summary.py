"""Closed publication boundary for invented transition-expression evidence."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.sfc_conditions import analyze_sfc_conditions
from plc_workbench.sfc_condition_summary import (SfcConditionSummaryError,
    build_sfc_condition_summary, render_sfc_condition_summary, validate_sfc_condition_summary)
from test_sfc_conditions import fixture, expression


def summary(**kwargs):
    inputs = fixture(**kwargs)
    return build_sfc_condition_summary(*inputs, analyze_sfc_conditions(*inputs))


class SfcConditionSummaryTests(unittest.TestCase):
    def test_round_trip_closed_source_free_summary(self):
        result = summary(text='A AND B > 12 // PRIVATE COMMENT')
        rendered = render_sfc_condition_summary(result)
        self.assertLess(len(rendered.encode()), 4096)
        self.assertEqual(json.loads(rendered), result)
        self.assertEqual(result['coverage']['transitions_by_status']['modeled'], 1)
        for secret in ['PRIVATE COMMENT', 'raw_text', 'line_ids', 'snapshot', 'Chart']:
            self.assertNotIn(secret, rendered)

    def test_empty_and_multiple_complete_partial_cases_are_consistent(self):
        cases = [{'body': ''}, {'text': '1'}, {'text': 'A AND B > 0'}, {'text': 'Missing'},
            {'text': 'A := B;'}, {'text': 'A // note'}, {'body': '<Transition/>'},
            {'body': expression('A', 'bad')}, {'text': 'JSR(R,0);'},
            {'text': 'A', 'extra': '<SFCContent OnlineEditType="TestEdits">' + expression('B') + '</SFCContent>'}]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                validate_sfc_condition_summary(summary(**kwargs))

    def test_revision_contract_and_no_source_extension_keys(self):
        inputs = fixture()
        result = analyze_sfc_conditions(*inputs)
        revision = {'commit': 'a' * 40, 'worktree': 'clean'}
        value = build_sfc_condition_summary(*inputs, result, revision=revision)
        self.assertEqual(value['tool_revision'], revision)
        for bad_revision in [{'commit': 'bad', 'worktree': 'clean'}, {'commit': 'a' * 40, 'worktree': 'unavailable'},
                             {'commit': None, 'worktree': 'clean'}, {'commit': None, 'worktree': 'unknown'}]:
            with self.assertRaises(SfcConditionSummaryError):
                build_sfc_condition_summary(*inputs, result, revision=bad_revision)
        for field in ['source_text', 'snapshot', 'schema_version']:
            bad = deepcopy(value)
            bad[field] = 'PRIVATE'
            with self.assertRaises(SfcConditionSummaryError):
                validate_sfc_condition_summary(bad)

    def test_boolean_negative_huge_unknown_and_fractional_counts_rejected(self):
        value = summary()
        for count in [True, -1, 10**13, 0.5, '1', None]:
            bad = deepcopy(value)
            bad['coverage']['transitions_total'] = count
            with self.subTest(count=count), self.assertRaises(SfcConditionSummaryError):
                validate_sfc_condition_summary(bad)
        bad = deepcopy(value)
        bad['coverage']['transitions_by_reason']['PRIVATE CODE'] = 1
        with self.assertRaises(SfcConditionSummaryError):
            validate_sfc_condition_summary(bad)

    def test_every_partition_and_relationship_invariant_rejects_tampering(self):
        value = summary(text='A AND B > 2 // note')
        for key in ['transitions_total', 'nodes_total', 'references_total', 'comments_total',
                    'line_spans_total', 'transition_st_lines', 'unprocessed_st_lines',
                    'transitions_with_comments', 'transitions_with_metadata_gaps', 'transitions_with_text']:
            bad = deepcopy(value)
            bad['coverage'][key] += 5
            with self.subTest(key=key), self.assertRaises(SfcConditionSummaryError):
                validate_sfc_condition_summary(bad)
        for key in ['transitions_by_status', 'transitions_by_reason', 'nodes_by_kind', 'references_by_binding',
                    'comments_by_kind', 'metadata_gaps']:
            bad = deepcopy(value)
            bad['coverage'][key][next(iter(bad['coverage'][key]))] += 1
            with self.subTest(key=key), self.assertRaises(SfcConditionSummaryError):
                validate_sfc_condition_summary(bad)

    def test_status_and_false_complete_binding_claims_rejected(self):
        value = summary(text='Missing')
        value['status'] = 'complete'
        with self.assertRaises(SfcConditionSummaryError):
            validate_sfc_condition_summary(value)
        value = summary(text='A')
        value['coverage']['references_by_binding']['root_bound'] = 0
        value['coverage']['references_by_binding']['unresolved'] = 1
        with self.assertRaises(SfcConditionSummaryError):
            validate_sfc_condition_summary(value)

    def test_source_replay_precedes_publication_and_render_budget_is_enforced(self):
        inputs = fixture()
        result = analyze_sfc_conditions(*inputs)
        result.transitions[0]['raw_text'] = 'FORGED PRIVATE'
        with self.assertRaisesRegex(SfcConditionSummaryError, '^SFC condition summary validation failed; no summary was produced.$'):
            build_sfc_condition_summary(*inputs, result)
        value = summary()
        with patch('plc_workbench.sfc_condition_summary.MAX_REPORT_BYTES', 1):
            with self.assertRaises(SfcConditionSummaryError):
                render_sfc_condition_summary(value)

    def test_return_is_detached_from_private_and_caller_revision_containers(self):
        inputs = fixture()
        result = analyze_sfc_conditions(*inputs)
        revision = {'commit': 'b' * 40, 'worktree': 'modified'}
        value = build_sfc_condition_summary(*inputs, result, revision)
        value['coverage']['transitions_by_status']['modeled'] = 999
        value['tool_revision']['commit'] = None
        self.assertEqual(result.coverage['transitions_by_status']['modeled'], 1)
        self.assertEqual(revision['commit'], 'b' * 40)


if __name__ == '__main__':
    unittest.main()
