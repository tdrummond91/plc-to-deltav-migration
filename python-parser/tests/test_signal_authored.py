"""Invented declaration wording stays attached to its precise source uses."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from plc_workbench.signal_authored import AUTHORED_COVERAGE_KEYS
from plc_workbench.signal_context import (SignalContextError, analyze_signal_context,
    render_signal_context_json, signal_context_constants, validate_signal_context)
from test_signal_context import capture as base_capture, capture_xml as base_capture_xml, namespace, tag


def capture(*args, **kwargs):
    parts = base_capture(*args, **kwargs)
    return (*parts[:-1], analyze_signal_context(*parts[:-1], schema_version=3))


def capture_xml(xml: str):
    parts = base_capture_xml(xml)
    return (*parts[:-1], analyze_signal_context(*parts[:-1], schema_version=3))


def described(name: str, description: str, alias: str | None = None) -> str:
    return tag(name, alias).replace('/>', f'><Description>{description}</Description></Tag>')


class SignalAuthoredTests(unittest.TestCase):
    def test_version_two_bytes_and_default_are_preserved(self) -> None:
        args = base_capture(('XIC(Pump)OTE(Pump);',), tags=described('Pump', 'Alarm sensor'))
        old = analyze_signal_context(*args[:-1], schema_version=2)
        new = analyze_signal_context(*args[:-1], schema_version=3)
        reduced = deepcopy(new)
        for address in reduced.addresses:
            for key in ('authored_evidence', 'authored_scan_status', 'authored_description_gap_ids'):
                del address[key]
        for key in AUTHORED_COVERAGE_KEYS:
            del reduced.coverage[key]
        reduced = replace(reduced, **signal_context_constants(2))
        self.assertEqual(render_signal_context_json(reduced), render_signal_context_json(old))
        self.assertEqual(analyze_signal_context(*args[:-1]).schema_version, 1)
        validate_signal_context(*args[:-1], new)

    def test_fields_categories_and_words_are_exact_but_not_engineering_classes(self) -> None:
        result = capture(('OTE(Pump_Alarm);',), tags=described('Pump_Alarm', 'trip sensor pump pump'))[-1]
        rows = result.addresses[0]['authored_evidence']
        self.assertEqual([row['field'] for row in rows], ['name', 'description'])
        self.assertEqual(rows[0]['categories'], ['alarm', 'equipment'])
        self.assertEqual(rows[1]['terms'], ['pump', 'sensor', 'trip'])
        self.assertEqual(result.coverage['authored_outputs_by_category'], {'alarm': 1, 'equipment': 1, 'sensor': 1})
        self.assertEqual(result.coverage['authored_outputs_with_evidence'], 1)
        self.assertTrue(all(row['scope'] == 'declaration_root_context' for row in rows))
        self.assertTrue(all('raw_text' not in row and 'engineering_role' not in row for row in rows))

    def test_same_root_members_retain_root_context_not_member_description(self) -> None:
        result = capture(('XIC(Pump.Start)OTE(Pump.Stop);',), tags=described('Pump', 'alarm sensor'))[-1]
        self.assertEqual(len(result.addresses), 2)
        self.assertEqual(result.coverage['authored_sources_total'], 1)
        self.assertEqual(result.coverage['authored_fields_scanned'], 2)
        self.assertEqual(result.coverage['authored_evidence_total'], 4)
        for address in result.addresses:
            self.assertEqual(len(address['authored_evidence']), 2)
            self.assertTrue(all(row['entity_id'] == address['target_id'] and row['scope'] == 'declaration_root_context'
                for row in address['authored_evidence']))
        self.assertNotEqual(result.addresses[0]['authored_evidence'][0]['operand_ids'],
            result.addresses[1]['authored_evidence'][0]['operand_ids'])

    def test_reader_alias_wording_does_not_become_an_output_hint(self) -> None:
        args = capture(('XIC(Pump_Alarm)OTE(D);',), tags=tag('D') + tag('Pump_Alarm', 'D'))
        result = args[-1]
        row = result.addresses[0]['authored_evidence'][0]
        self.assertEqual(row['relation'], 'alias_declaration')
        self.assertEqual(row['operand_ids'], [result.condition_reads[0]['id']])
        self.assertNotIn(result.outputs[0]['target_operand_id'], row['operand_ids'])
        self.assertEqual(result.coverage['authored_outputs_with_evidence'], 0)
        self.assertEqual(result.coverage['authored_qualified_evidence_by_category']['alarm'], 1)
        self.assertEqual(result.coverage['authored_outputs_by_category']['alarm'], 0)

    def test_target_alias_is_linked_but_intermediate_alias_wording_is_not_scanned(self) -> None:
        result = capture(('XIC(D)OTE(Pump_Alarm);',), tags=tag('D') + tag('Pump_Alarm', 'D'))[-1]
        self.assertEqual(result.coverage['authored_outputs_with_evidence'], 1)
        self.assertEqual(result.addresses[0]['authored_evidence'][0]['operand_ids'], [result.outputs[0]['target_operand_id']])
        middle = capture(('OTE(Head);',), tags=tag('D') + tag('Pump', 'D') + tag('Head', 'Pump'))[-1]
        self.assertEqual(middle.coverage['authored_sources_total'], 2)
        self.assertEqual(middle.addresses[0]['authored_evidence'], [])

    def test_namespace_description_and_qualified_name_remain_separate(self) -> None:
        args = base_capture(('OTE(Pump);',), tags=described('Pump', 'alarm'))
        xml = namespace(args[0].data.decode()).replace('<Description>', '<x:Description>').replace('</Description>', '</x:Description>')
        result = capture_xml(xml)[-1]
        rows = result.addresses[0]['authored_evidence']
        self.assertEqual([(row['field'], row['qualification']) for row in rows],
            [('name', 'qualified'), ('description', 'namespace_gap')])
        self.assertEqual(result.coverage['authored_outputs_by_category']['alarm'], 0)
        self.assertEqual(result.coverage['authored_outputs_by_category']['equipment'], 1)
        self.assertEqual(result.coverage['authored_outputs_with_unqualified_evidence'], 1)
        self.assertEqual(result.status, 'partial')

    def test_ambiguous_description_is_visible_without_selecting_text(self) -> None:
        for fragment in ('<Description>alarm</Description><Description>sensor</Description>',
                '<Description><Text>alarm</Text></Description>'):
            with self.subTest(fragment=fragment):
                tags = tag('Pump').replace('/>', f'>{fragment}</Tag>')
                result = capture(('OTE(Pump);',), tags=tags)[-1]
                address = result.addresses[0]
                self.assertEqual([row['field'] for row in address['authored_evidence']], ['name'])
                self.assertEqual(address['authored_description_gap_ids'], [address['target_id']])
                self.assertEqual(address['authored_scan_status'], 'complete')
                self.assertEqual(result.coverage['authored_field_scans_by_status']['ambiguous_text'], 1)
                self.assertEqual(result.coverage['authored_outputs_by_category']['alarm'], 0)
                self.assertEqual(result.status, 'partial')

    def test_unqualified_nonmatching_description_remains_a_visible_gap(self) -> None:
        args = base_capture(('OTE(A);',), tags=described('A', 'ordinary wording'))
        xml = namespace(args[0].data.decode()).replace('<Description>', '<Description x:Flag="foreign">')
        result = capture_xml(xml)[-1]
        address = result.addresses[0]
        self.assertEqual(address['authored_evidence'], [])
        self.assertEqual(address['authored_description_gap_ids'], [address['target_id']])
        self.assertEqual(address['authored_scan_status'], 'complete')
        self.assertEqual(result.coverage['authored_field_scans_by_status']['namespace_gap'], 1)
        self.assertEqual(result.status, 'partial')

    def test_whole_words_match_the_existing_catalog_without_camel_case_inference(self) -> None:
        result = capture(('OTE(Pumpkin);', 'OTE(PumpCommand);', 'OTE(A);'), tags=
            described('Pumpkin', 'alarming transmitterish') + tag('PumpCommand') + described('A', 'POMPE ALARME CAPTEUR'))[-1]
        self.assertEqual(result.coverage['authored_addresses_with_evidence'], 1)
        self.assertEqual(result.coverage['authored_outputs_by_category'], {'alarm': 1, 'equipment': 1, 'sensor': 1})

    def test_expression_uses_are_separate_and_do_not_classify_other_destinations(self) -> None:
        result = capture(('XIC(D)CPT(A,Pump+Pump);',), tags=tag('A') + tag('D') + tag('Pump', 'D'))[-1]
        row = result.addresses[0]['authored_evidence'][0]
        self.assertEqual(row['operand_ids'], [])
        self.assertEqual(len(row['expression_use_ids']), 2)
        self.assertEqual(result.coverage['authored_expression_links'], 2)
        self.assertEqual(result.coverage['authored_outputs_with_evidence'], 0)

    def test_every_local_budget_exhaustion_is_explicit_and_replayable(self) -> None:
        args = base_capture(('XIC(Pump)OTE(Pump);',), tags=described('Pump', 'alarm'))
        for budget in ('MAX_AUTHORED_FIELDS', 'MAX_AUTHORED_USE_VISITS', 'MAX_AUTHORED_CHARACTERS',
                'MAX_AUTHORED_ROWS', 'MAX_AUTHORED_USE_IDS', 'MAX_AUTHORED_BYTES'):
            with self.subTest(budget=budget), patch(f'plc_workbench.signal_authored.{budget}', 0):
                result = analyze_signal_context(*args[:-1], schema_version=3)
                self.assertEqual(result.coverage['authored_scans_by_status']['truncated'], 1)
                self.assertEqual(result.status, 'partial')
                validate_signal_context(*args[:-1], result)

    def test_partial_retained_use_list_never_claims_a_missing_writer(self) -> None:
        args = base_capture(('XIC(Pump)OTE(Pump);',), tags=tag('Pump'))
        with patch('plc_workbench.signal_authored.MAX_AUTHORED_USE_IDS', 1):
            result = analyze_signal_context(*args[:-1], schema_version=3)
            self.assertEqual(result.coverage['authored_evidence_total'], 1)
            self.assertEqual(result.addresses[0]['authored_evidence'][0]['operand_ids'], [result.condition_reads[0]['id']])
            self.assertEqual(result.coverage['authored_outputs_with_evidence'], 0)
            self.assertEqual(result.addresses[0]['authored_scan_status'], 'truncated')
            validate_signal_context(*args[:-1], result)

    def test_replay_rejects_forged_attribution_and_global_caps_still_fail_closed(self) -> None:
        args = capture(('XIC(Pump)OTE(D);',), tags=tag('Pump') + tag('D'))
        for mutate in (lambda r: r.addresses[0]['authored_evidence'][0].update(scope='member_description'),
                lambda r: r.addresses[0]['authored_evidence'][0]['operand_ids'].append(r.outputs[0]['target_operand_id']),
                lambda r: r.addresses[0]['authored_evidence'][0].update(terms=['secret']),
                lambda r: r.coverage.update(authored_fields_scanned=True)):
            broken = deepcopy(args[-1])
            mutate(broken)
            with self.assertRaises(SignalContextError):
                validate_signal_context(*args[:-1], broken)
        for cap in ('MAX_SIGNAL_CONTEXT_V3_BYTES', 'MAX_SIGNAL_CONTEXT_V3_JSON_BYTES', 'MAX_EVIDENCE_IDS'):
            with self.subTest(cap=cap), patch(f'plc_workbench.signal_context.{cap}', 1), self.assertRaises(SignalContextError):
                render_signal_context_json(args[-1])


if __name__ == '__main__':
    unittest.main()
