"""Closed summary conservation and source privacy for invented SFC context."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.sfc_context_summary import (SfcContextSummaryError,
    build_sfc_context_summary, render_sfc_context_summary, validate_sfc_context_summary)
from test_sfc_context import capture, step, transition


class SfcContextSummaryTests(unittest.TestCase):
    def test_summary_round_trip_covers_parsed_missing_and_unsupported(self):
        for args in (capture(body=''), capture(body=step() + transition('State.X OR Missing'), rungs=('OTE(State.X);',)), capture(text='A := 1')):
            with self.subTest(status=args[-1].status):
                summary = build_sfc_context_summary(*args)
                self.assertEqual(summary, json.loads(render_sfc_context_summary(summary)))
                self.assertEqual(summary['coverage'], args[-1].coverage)

    def test_summary_contains_no_source_spelling_ids_paths_or_added_keys(self):
        summary = build_sfc_context_summary(*capture(text='UnsharedPlantName'))
        rendered = render_sfc_context_summary(summary)
        self.assertNotIn('UnsharedPlantName', rendered)
        self.assertNotIn('root_text', rendered)
        self.assertNotIn('snapshot', rendered)
        for location in (summary, summary['coverage'], summary['coverage']['gaps_by_kind']):
            location['source'] = 'DO_NOT_EXPORT'
            with self.assertRaises(SfcContextSummaryError):
                render_sfc_context_summary(summary)
            del location['source']

    def test_all_closed_counts_reject_bool_float_negative_and_excessive(self):
        summary = build_sfc_context_summary(*capture())
        for bad in (True, 1.0, -1, 10**12 + 1):
            for key in ('references_total', 'references_by_status'):
                changed = deepcopy(summary)
                if key == 'references_by_status':
                    changed['coverage'][key]['exact_address'] = bad
                else:
                    changed['coverage'][key] = bad
                with self.subTest(value=bad, key=key), self.assertRaises(SfcContextSummaryError):
                    validate_sfc_context_summary(changed)

    def test_conservation_rejects_source_mismatch_and_fabricated_associations(self):
        summary = build_sfc_context_summary(*capture(body=step() + transition('State.X OR Missing'), rungs=('OTE(State.X);',)))
        for key in ('references_total', 'source_references', 'addresses_total', 'step_links_total',
                    'gaps_total', 'gaps_with_lexical_steps', 'accepted_expression_uses',
                    'outside_scope_declarations', 'addresses_with_rll_readers', 'unqualified_step_links',
                    'references_with_multiple_steps'):
            changed = deepcopy(summary)
            changed['coverage'][key] += 100
            with self.subTest(key=key), self.assertRaises(SfcContextSummaryError):
                validate_sfc_context_summary(changed)

    def test_reference_roles_and_steps_are_conserved_independently(self):
        summary = build_sfc_context_summary(*capture(body=step() + transition('State.X'), rungs=('OTE(State.X);',)))
        for key, child in [('accepted_operands_by_role', 'write'), ('step_links_by_evidence', 'lexical_hint'),
                           ('step_links_by_relation', 'peer_chart'), ('step_links_by_match', 'exact'),
                           ('gaps_by_kind', 'root_missing')]:
            changed = deepcopy(summary)
            changed['coverage'][key][child] += 1
            with self.subTest(key=key), self.assertRaises(SfcContextSummaryError):
                validate_sfc_context_summary(changed)

    def test_revision_status_and_literal_types_are_strict(self):
        summary = build_sfc_context_summary(*capture(), revision={'commit': 'a' * 40, 'worktree': 'modified'})
        validate_sfc_context_summary(summary)
        mutations = [('schema_version', True), ('status', 'partial'), ('tool_revision', {'commit': None, 'worktree': 'clean'})]
        for key, value in mutations:
            changed = deepcopy(summary)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(SfcContextSummaryError):
                validate_sfc_context_summary(changed)

    def test_build_authenticates_context_and_output_caps_are_source_free(self):
        args = capture()
        args[-1].addresses[0]['suffix'] = '.FORGED'
        with self.assertRaises(SfcContextSummaryError):
            build_sfc_context_summary(*args)
        summary = build_sfc_context_summary(*capture())
        with patch('plc_workbench.sfc_context_summary.MAX_REPORT_BYTES', 1):
            with self.assertRaisesRegex(SfcContextSummaryError, '^SFC context summary validation failed; no summary was produced[.]$'):
                render_sfc_context_summary(summary)


if __name__ == '__main__':
    unittest.main()
