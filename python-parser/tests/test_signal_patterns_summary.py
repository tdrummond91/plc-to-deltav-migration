"""Versioned counts-only summaries authenticate pattern intake and bounds."""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from plc_workbench.signal_context_summary import (SignalContextSummaryError,
    build_signal_context_summary, render_signal_context_summary, validate_signal_context_summary)
from test_signal_patterns import capture, tag, typed_tag


class SignalPatternSummaryTests(unittest.TestCase):
    def test_counts_only_v2_summary_and_empty_cases(self) -> None:
        args = capture(('TON(T,?,?);', 'XIC(T.DN)XIC(SecretPump)OTL(SecretPump);', 'OTU(SecretPump);'),
            tags=typed_tag('T') + tag('SecretPump'))
        summary = build_signal_context_summary(*args)
        rendered = render_signal_context_summary(summary)
        self.assertEqual(summary['schema_version'], 2)
        self.assertEqual(summary['coverage']['pattern_set_reset_contexts'], 1)
        self.assertLess(len(rendered.encode()), 12288)
        for text in ('SecretPump', 'condition_read_id', 'content_locator', 'output_context_'):
            self.assertNotIn(text, rendered)
        for texts in ((';',), ('BROKEN(',), ('XIC(A);',), ('OTE(Missing);',), ('EQU(A,1)OTE(D);',)):
            with self.subTest(texts=texts):
                validate_signal_context_summary(build_signal_context_summary(*capture(texts)))

    def test_closed_pattern_maps_and_impossible_counts_are_rejected(self) -> None:
        good = build_signal_context_summary(*capture(('XIC(D)OTL(D);', 'OTU(D);')))
        changes = (
            lambda c: c['pattern_traversals_by_status'].update(complete=100),
            lambda c: c['pattern_traversals_by_status'].update(secret=1),
            lambda c: c.update(pattern_unique_guards_total=0),
            lambda c: c.update(pattern_visited_nodes=0),
            lambda c: c.update(pattern_visited_edges=10**10),
            lambda c: c.update(pattern_outputs_with_self_contacts=0),
            lambda c: c.update(pattern_outputs_with_timer_contacts=1),
            lambda c: c.update(pattern_coil_contexts_total=0),
            lambda c: c.update(pattern_set_reset_contexts=2),
            lambda c: c.update(pattern_addresses_with_set_reset=0),
            lambda c: c['pattern_grouped_outputs_by_opcode'].update(OTE=1),
            lambda c: c['pattern_self_contacts_by_kind'].update(xio=1),
            lambda c: c['pattern_timer_contacts_by_member'].update(DN=1),
            lambda c: c.update(pattern_visited_nodes=True),
        )
        for mutate in changes:
            broken = deepcopy(good)
            mutate(broken['coverage'])
            with self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(broken)

    def test_truncation_status_is_conservative_and_caps_remain_versioned(self) -> None:
        with patch('plc_workbench.signal_patterns.MAX_PATTERN_LINKS', 0):
            summary = build_signal_context_summary(*capture(('XIC(D)OTE(D);',)))
        self.assertEqual(summary['status'], 'partial')
        validate_signal_context_summary(summary)
        broken = deepcopy(summary)
        broken['status'] = 'complete'
        with self.assertRaises(SignalContextSummaryError):
            validate_signal_context_summary(broken)
        for bound in ('MAX_SIGNAL_CONTEXT_V2_BYTES', 'MAX_SIGNAL_CONTEXT_V2_JSON_BYTES'):
            with patch(f'plc_workbench.signal_context_summary.{bound}', 1), self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(summary)
        with patch('plc_workbench.signal_context_summary.MAX_REPORT_V2_BYTES', 1), self.assertRaises(SignalContextSummaryError):
            render_signal_context_summary(summary)

    def test_self_contacts_cannot_attach_to_unbound_output_targets(self) -> None:
        summary = build_signal_context_summary(*capture(('XIC(A)OTE(Missing);',)))
        summary['coverage']['pattern_self_contacts_by_kind']['xic'] = 1
        summary['coverage']['pattern_outputs_with_self_contacts'] = 1
        with self.assertRaises(SignalContextSummaryError):
            validate_signal_context_summary(summary)

    def test_complete_traversals_visit_each_unique_guard(self) -> None:
        summary = build_signal_context_summary(*capture(('XIC(D)OTE(D);', 'XIO(D)OTE(D);')))
        summary['coverage']['pattern_visited_nodes'] = 1
        with self.assertRaises(SignalContextSummaryError):
            validate_signal_context_summary(summary)


if __name__ == '__main__':
    unittest.main()
