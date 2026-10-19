"""Closed signal3 publication counts preserve authored-source boundaries."""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from plc_workbench.signal_context_summary import (SignalContextSummaryError,
    build_signal_context_summary, render_signal_context_summary, validate_signal_context_summary)
from test_signal_authored import capture, described, tag


class SignalAuthoredSummaryTests(unittest.TestCase):
    def test_summary_is_closed_counts_without_source_words_or_identifiers(self) -> None:
        args = capture(('XIC(Secret_Pump)OTE(Secret_Pump);',), tags=described('Secret_Pump', 'warning transmitter'))
        summary = build_signal_context_summary(*args)
        rendered = render_signal_context_summary(summary)
        self.assertEqual(summary['schema_version'], 3)
        self.assertEqual(summary['coverage']['authored_outputs_with_evidence'], 1)
        self.assertLess(len(rendered.encode()), 16384)
        for text in ('Secret_Pump', 'warning', 'transmitter', 'entity_id', 'operand_ids', 'terms'):
            self.assertNotIn(text, rendered)
        for texts in ((';',), ('BROKEN(',), ('OTE(Missing);',), ('XIC(A);',)):
            validate_signal_context_summary(build_signal_context_summary(*capture(texts)))

    def test_impossible_counts_unknown_keys_and_types_are_rejected(self) -> None:
        good = build_signal_context_summary(*capture(('XIC(Pump)OTE(Pump);',), tags=described('Pump', 'alarm')))
        mutations = (
            lambda c: c['authored_scans_by_status'].update(complete=100),
            lambda c: c['authored_evidence_by_field'].update(secret=1),
            lambda c: c.update(authored_sources_total=0),
            lambda c: c.update(authored_fields_scanned=True),
            lambda c: c.update(authored_fields_scanned=100_001),
            lambda c: c.update(authored_characters_scanned=0),
            lambda c: c.update(authored_use_visits=0),
            lambda c: c.update(authored_evidence_total=0),
            lambda c: c.update(authored_operand_links=0),
            lambda c: c.update(authored_expression_links=1),
            lambda c: c.update(authored_description_gap_links=1),
            lambda c: c.update(authored_addresses_with_evidence=0),
            lambda c: c.update(authored_addresses_with_description_gaps=1),
            lambda c: c.update(authored_outputs_with_evidence=2),
            lambda c: c.update(authored_outputs_with_unqualified_evidence=1),
            lambda c: c['authored_outputs_by_category'].update(sensor=1),
            lambda c: c['authored_qualified_evidence_by_category'].update(alarm=0),
        )
        for mutate in mutations:
            broken = deepcopy(good)
            mutate(broken['coverage'])
            with self.subTest(mutate=mutate), self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(broken)

    def test_reader_alias_counts_are_not_promoted_to_output_categories(self) -> None:
        summary = build_signal_context_summary(*capture(('XIC(Pump_Alarm)OTE(D);',),
            tags=tag('D') + tag('Pump_Alarm', 'D')))
        c = summary['coverage']
        self.assertEqual(c['authored_qualified_evidence_by_category']['alarm'], 1)
        self.assertEqual(c['authored_outputs_by_category']['alarm'], 0)
        self.assertEqual(c['authored_outputs_with_evidence'], 0)
        validate_signal_context_summary(summary)

    def test_ambiguity_and_truncation_are_partial_without_invented_matches(self) -> None:
        tags = tag('A').replace('/>', '><Description>alarm</Description><Description>sensor</Description></Tag>')
        summary = build_signal_context_summary(*capture(('OTE(A);',), tags=tags))
        self.assertEqual(summary['coverage']['authored_description_gap_links'], 1)
        self.assertEqual(summary['coverage']['authored_evidence_total'], 0)
        self.assertEqual(summary['status'], 'partial')
        with patch('plc_workbench.signal_authored.MAX_AUTHORED_USE_IDS', 1):
            summary = build_signal_context_summary(*capture(('XIC(Pump)OTE(Pump);',), tags=tag('Pump')))
        validate_signal_context_summary(summary)
        summary['status'] = 'complete'
        with self.assertRaises(SignalContextSummaryError):
            validate_signal_context_summary(summary)

    def test_version_three_caps_and_prior_version_constants_remain_separate(self) -> None:
        summary = build_signal_context_summary(*capture(('OTE(Pump);',), tags=tag('Pump')))
        for cap in ('MAX_SIGNAL_CONTEXT_V3_BYTES', 'MAX_SIGNAL_CONTEXT_V3_JSON_BYTES'):
            with patch(f'plc_workbench.signal_context_summary.{cap}', 1), self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(summary)
        with patch('plc_workbench.signal_context_summary.MAX_REPORT_V3_BYTES', 1), self.assertRaises(SignalContextSummaryError):
            render_signal_context_summary(summary)

    def test_one_use_cannot_introduce_more_than_root_and_immediate_symbol(self) -> None:
        summary = build_signal_context_summary(*capture(('OTE(Pump);',), tags=tag('Pump')))
        c = summary['coverage']
        c['authored_sources_total'] = 4
        c['authored_fields_scanned'] = 4
        c['authored_field_scans_by_status']['absent'] = 3
        with self.assertRaises(SignalContextSummaryError):
            validate_signal_context_summary(summary)


if __name__ == '__main__':
    unittest.main()
