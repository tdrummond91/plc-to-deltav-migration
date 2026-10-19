"""Alarm evidence publication exposes closed counts, never stored settings."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.alarm_evidence_summary import (
    CONSTANTS, AlarmEvidenceSummaryError, build_alarm_evidence_summary,
    render_alarm_evidence_summary, validate_alarm_evidence_summary,
)
from test_alarm_evidence import CONDITIONS, DATA, DEFINITIONS, capture, tag


class AlarmEvidenceSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.args = capture(tag(DATA + CONDITIONS) + DEFINITIONS)
        cls.summary = build_alarm_evidence_summary(*cls.args)

    def test_closed_counts_roundtrip_and_no_source_leakage(self) -> None:
        summary = self.summary
        self.assertEqual(set(summary), set(CONSTANTS) | {'status', 'coverage', 'tool_revision'})
        rendered = render_alarm_evidence_summary(summary)
        self.assertEqual(json.loads(rendered), summary)
        self.assertLess(len(rendered.encode('utf-8')), 8192)
        for secret in ('PrivateCondition', 'PrivateType', 'PrivateDefinition', 'PrivateClass',
                       'PrivateGroup', 'PrivateCommand', '0007', '0099', '0012', '.PV',
                       '<img', self.args[0].sha256, self.args[-1].containers[0]['id']):
            self.assertNotIn(secret, rendered)
        self.assertEqual(rendered, render_alarm_evidence_summary(deepcopy(summary)))

    def test_equal_lexical_shapes_have_equal_summary_despite_private_spelling(self) -> None:
        first = build_alarm_evidence_summary(*capture(tag(DATA, name='SecretA')))
        second = build_alarm_evidence_summary(*capture(tag(DATA.replace('0007', '0099'), name='SecretB')))
        self.assertEqual(first, second)

    def test_empty_and_unused_declarations_have_complete_status(self) -> None:
        for body in ('', tag()):
            with self.subTest(body=body):
                summary = build_alarm_evidence_summary(*capture(body))
                self.assertEqual(summary['status'], 'complete')
                self.assertEqual(summary['coverage']['records_with_gaps'], 0)
                validate_alarm_evidence_summary(summary)

    def test_partial_status_and_gap_partitions_reconcile(self) -> None:
        summary = build_alarm_evidence_summary(*capture(tag(CONDITIONS + CONDITIONS)))
        c = summary['coverage']
        self.assertEqual(summary['status'], 'partial')
        self.assertEqual(c['gap_links_total'], sum(c['gaps_by_code'].values()))
        self.assertEqual(c['duplicate_records'], c['gaps_by_code']['duplicate_sibling'])
        changed = {**summary, 'status': 'complete'}
        with self.assertRaises(AlarmEvidenceSummaryError):
            validate_alarm_evidence_summary(changed)

    def test_changed_partitions_capacities_and_boolean_counts_are_rejected(self) -> None:
        mutations = [('declarations_total', 999), ('containers_total', 0), ('elements_total', True),
            ('source_xml_elements', 1), ('source_entities', 0), ('source_data_contents', 0),
            ('records_with_gaps', 1), ('content_links_total', 1000), ('container_links_total', 1000),
            ('declarations_with_data', 0), ('declarations_with_containers', 0),
            ('duplicate_groups', 1), ('duplicate_records', 1), ('gap_links_total', 1),
            ('attribute_pairs', 2_000_001), ('direct_text_bytes', 8 * 1024 * 1024 + 1)]
        for key, value in mutations:
            with self.subTest(key=key):
                summary = deepcopy(self.summary)
                summary['coverage'][key] = value
                with self.assertRaises(AlarmEvidenceSummaryError):
                    validate_alarm_evidence_summary(summary)

    def test_extra_source_fields_open_keys_wrong_constants_and_revisions_fail(self) -> None:
        changes = [{'raw_text': 'secret'}, {'schema_version': True}, {'analyzer_version': 'secret'},
                   {'tool_revision': {'commit': 'secret', 'worktree': 'clean'}},
                   {'tool_revision': {'commit': 'a' * 40, 'worktree': 'unavailable'}},
                   {'status': 'partial'}]
        for update in changes:
            with self.subTest(update=update):
                summary = {**deepcopy(self.summary), **update}
                with self.assertRaises(AlarmEvidenceSummaryError):
                    validate_alarm_evidence_summary(summary)
        for field in ('gaps_by_code', 'elements_by_kind', 'declarations_by_type'):
            summary = deepcopy(self.summary)
            summary['coverage'][field]['PRIVATE'] = 0
            with self.assertRaises(AlarmEvidenceSummaryError):
                validate_alarm_evidence_summary(summary)

    def test_valid_revision_is_copied_and_summary_does_not_alias_private_counts(self) -> None:
        revision = {'commit': 'a' * 40, 'worktree': 'modified'}
        summary = build_alarm_evidence_summary(*self.args, revision=revision)
        revision['commit'] = 'b' * 40
        self.assertEqual(summary['tool_revision']['commit'], 'a' * 40)
        summary['coverage']['containers_by_kind']['alarm_data'] = 999
        self.assertEqual(self.args[-1].coverage['containers_by_kind']['alarm_data'], 1)

    def test_forged_private_results_never_publish(self) -> None:
        result = deepcopy(self.args[-1])
        result.elements[0]['attributes']['PrivateSetting'] = 'secret'
        with self.assertRaises(AlarmEvidenceSummaryError):
            build_alarm_evidence_summary(*self.args[:3], result)

    def test_duplicate_unknown_and_foreign_shapes_still_validate_as_closed_counts(self) -> None:
        bodies = [tag(CONDITIONS + CONDITIONS), tag(DATA.replace('<AlarmConfig>', '<AlarmConfig x:Flag="secret">')),
                  tag(CONDITIONS.replace('<AlarmConfig>', '<AlarmConfig><Vendor/>')),
                  '<Vendor>' + CONDITIONS + '</Vendor>']
        for body in bodies:
            with self.subTest(body=body):
                summary = build_alarm_evidence_summary(*capture(body, ' xmlns:x="urn:private"'))
                validate_alarm_evidence_summary(summary)
                self.assertEqual(summary['status'], 'partial')

    def test_zero_container_capacity_cannot_hide_text_or_attributes(self) -> None:
        base = build_alarm_evidence_summary(*capture(tag()))
        for key in ('direct_text_bytes', 'attribute_pairs'):
            summary = deepcopy(base)
            summary['coverage'][key] = 1
            with self.assertRaises(AlarmEvidenceSummaryError):
                validate_alarm_evidence_summary(summary)

    def test_public_byte_cap_is_enforced(self) -> None:
        with patch('plc_workbench.alarm_evidence_summary.MAX_REPORT_BYTES', 20):
            with self.assertRaises(AlarmEvidenceSummaryError):
                render_alarm_evidence_summary(self.summary)


if __name__ == '__main__':
    unittest.main()
