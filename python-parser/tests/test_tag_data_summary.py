"""Closed public summaries expose counts, never private stored-data records."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.tag_data_summary import (
    CONSTANTS, TagDataSummaryError, build_tag_data_summary, render_tag_data_summary,
    validate_tag_data_summary,
)
from test_tag_data import SCALAR, SHAPES, capture, tags


def summary(body: str = ''):
    return build_tag_data_summary(*capture(body))


class TagDataSummaryTests(unittest.TestCase):
    def test_generated_summary_is_count_only_and_serializes_deterministically(self) -> None:
        snapshot, inventory, result = capture(tags(
            '<Data Format="String">private-value-44021</Data>'
            '<DefaultData Format="PrivateFormat"><SecretNode SecretAttr="SecretSetting"/></DefaultData>',
            'SecretOwner'))
        report = build_tag_data_summary(snapshot, inventory, result)
        self.assertEqual(set(report), set(CONSTANTS) | {'status', 'tool_revision', 'coverage'})
        self.assertEqual(report['schema_version'], 1)
        self.assertEqual(report['exporter_version'], 'tag-data-summary-1')
        self.assertEqual(report['policy_version'], 2)
        rendered = render_tag_data_summary(report)
        self.assertEqual(json.loads(rendered), report)
        self.assertEqual(rendered, render_tag_data_summary(deepcopy(report)))
        for secret in ('private-value-44021', 'PrivateFormat', 'SecretNode', 'SecretAttr',
                       'SecretSetting', 'SecretOwner', snapshot.sha256, result.owners[0]['source_id']):
            self.assertNotIn(secret, rendered)
        self.assertEqual(report['status'], 'partial')

    def test_renamed_equal_shape_evidence_has_same_public_summary(self) -> None:
        first = summary(tags('<Data Format="String">secretA</Data>', 'A'))
        second = summary(tags('<Data Format="String">secretB</Data>', 'B'))
        self.assertEqual(first, second)

    def test_complete_missing_and_partial_opaque_have_exact_status(self) -> None:
        for body in ('', tags(''), tags(SCALAR), tags('<Data Format="String"/>')):
            with self.subTest(body=body):
                report = summary(body)
                self.assertEqual(report['status'], 'complete')
                self.assertEqual(report['coverage']['issues_total'], 0)
                validate_tag_data_summary(report)
        report = summary(tags('<Data Format="L5K">[0]</Data>'))
        self.assertEqual(report['status'], 'partial')
        report['status'] = 'complete'
        with self.assertRaises(TagDataSummaryError):
            validate_tag_data_summary(report)

    def test_mixed_shapes_and_duplicates_have_valid_capacity(self) -> None:
        report = summary(tags(SHAPES + SCALAR + '<DefaultData Format="Decorated"><DataValue Value="1"/></DefaultData>'))
        validate_tag_data_summary(report)
        self.assertEqual(report['coverage']['duplicate_groups']['content'], 1)
        self.assertEqual(report['coverage']['duplicate_records']['content'], 2)
        self.assertGreater(report['coverage']['elements_by_kind']['data_value_member'], 0)

    def test_namespace_and_malformed_shape_summaries_validate(self) -> None:
        cases = [
            ('<Data Format="Decorated"><x:Structure><DataValueMember Name="A" Value="1"/></x:Structure></Data>',
             ' xmlns:x="urn:foreign"'),
            ('<x:Data Format="Decorated"/>', ' xmlns:x="urn:foreign"'),
            ('<Data x:Format="Decorated"><DataValue Value="1"/></Data>', ' xmlns:x="urn:foreign"'),
            ('<Data Format="String"><DataValue Value="1"/></Data>', ''),
            ('<Data Format="Decorated">text<Unknown>opaque</Unknown></Data>', ''),
        ]
        for data, namespace in cases:
            with self.subTest(data=data):
                report = build_tag_data_summary(*capture(tags(data), namespace))
                self.assertEqual(report['status'], 'partial')
                validate_tag_data_summary(report)

    def test_exact_keys_and_types_reject_boolean_cycles_and_leaks(self) -> None:
        valid = summary(tags(SCALAR))
        mutations = [
            lambda s: s.update(schema_version=True),
            lambda s: s.update(policy_version=False),
            lambda s: s.update(private_value='secret'),
            lambda s: s['coverage'].update(owners_total=True),
            lambda s: s['coverage']['owners_by_kind'].update(tag=True),
            lambda s: s['coverage'].update(extra=0),
            lambda s: s['coverage']['contents_by_format'].update(PrivateFormat=0),
            lambda s: s['coverage'].update(contents_total='1'),
            lambda s: s['coverage'].update(elements_total=1.0),
            lambda s: s['coverage'].update(elements_total=-1),
            lambda s: s['coverage'].update(elements_by_kind=s),
            lambda s: s['coverage'].update(owners_total=10**13),
            lambda s: s.update(status=[]),
            lambda s: s['tool_revision'].update(commit='secret'),
        ]
        for mutate in mutations:
            forged = deepcopy(valid)
            mutate(forged)
            with self.subTest(mutate=mutate), self.assertRaisesRegex(
                    TagDataSummaryError, '^Tag-data summary validation failed; no summary was produced\\.$'):
                validate_tag_data_summary(forged)

    def test_every_partition_is_checked(self) -> None:
        valid = summary(tags(SCALAR))
        for key, member in (
            ('owners_by_kind', 'tag'), ('contents_by_envelope', 'Data'),
            ('contents_by_format', 'decorated'), ('elements_by_kind', 'data_value'),
            ('issues_by_code', 'content_empty'),
        ):
            forged = deepcopy(valid)
            forged['coverage'][key][member] += 1
            with self.subTest(key=key), self.assertRaises(TagDataSummaryError):
                validate_tag_data_summary(forged)

    def test_coherent_impossible_ownership_and_xml_capacities_are_rejected(self) -> None:
        valid = summary(tags(SCALAR))
        for mutate in (
            lambda c: c.update(owners_with_data=0, owners_without_data=1),
            lambda c: c.update(owners_with_data=2, owners_without_data=0, owners_total=2,
                               owners_by_kind={**c['owners_by_kind'], 'tag': 2}),
            lambda c: c.update(source_xml_elements=c['owners_total'] + c['contents_total'] + c['elements_total'] - 1),
            lambda c: c.update(source_xml_elements=0),
            lambda c: c.update(attribute_pairs=1),
        ):
            forged = deepcopy(valid)
            mutate(forged['coverage'])
            with self.subTest(mutate=mutate), self.assertRaises(TagDataSummaryError):
                validate_tag_data_summary(forged)

    def test_coherent_duplicate_counts_cannot_exceed_record_capacity(self) -> None:
        valid = summary(tags(SCALAR + SCALAR))
        mutations = [
            lambda c: c['duplicate_groups'].update(content=2),
            lambda c: c['duplicate_groups'].update(content=0),
            lambda c: c['duplicate_records'].update(content=1),
        ]
        for mutate in mutations:
            forged = deepcopy(valid)
            mutate(forged['coverage'])
            with self.assertRaises(TagDataSummaryError):
                validate_tag_data_summary(forged)
        forged = summary(tags(SCALAR))
        coverage = forged['coverage']
        coverage['duplicate_groups']['member'] = 1
        coverage['duplicate_records']['member'] = 2
        coverage['issues_by_code']['duplicate_member'] = 2
        coverage['issues_total'] = 2
        forged['status'] = 'partial'
        with self.assertRaises(TagDataSummaryError):
            validate_tag_data_summary(forged)

    def test_known_shapes_require_decorated_and_opaque_requires_observed_gap(self) -> None:
        for kind in ('opaque', 'unmodeled'):
            report = summary(tags(SCALAR))
            coverage = report['coverage']
            coverage['elements_by_kind']['data_value'] = 0
            coverage['elements_by_kind'][kind] = 1
            with self.subTest(kind=kind), self.assertRaises(TagDataSummaryError):
                validate_tag_data_summary(report)
        report = summary(tags(SCALAR))
        report['coverage']['contents_by_format'].update(decorated=0, string=1)
        with self.assertRaises(TagDataSummaryError):
            validate_tag_data_summary(report)

    def test_unsupported_shape_and_empty_issue_counts_are_exact_or_bounded(self) -> None:
        valid = summary(tags('<Data Format="L5K">[1]</Data>'))
        valid['coverage']['issues_total'] = 0
        valid['coverage']['issues_by_code']['format_unsupported'] = 0
        valid['status'] = 'complete'
        with self.assertRaises(TagDataSummaryError):
            validate_tag_data_summary(valid)
        for code in ('content_empty', 'namespace_unmodeled'):
            forged = summary(tags(SCALAR))
            forged['status'] = 'partial'
            forged['coverage']['issues_total'] = 2
            forged['coverage']['issues_by_code'][code] = 2
            with self.assertRaises(TagDataSummaryError):
                validate_tag_data_summary(forged)

    def test_text_counts_must_fit_records_and_observed_bytes(self) -> None:
        valid = summary(tags('<Data Format="String">ab</Data>'))
        for mutate in (
            lambda c: c.update(contents_with_text=2),
            lambda c: c.update(elements_with_text=1),
            lambda c: c.update(direct_text_bytes=0),
            lambda c: c.update(contents_with_text=0),
            lambda c: c.update(direct_text_bytes=33 * 1024 * 1024),
        ):
            forged = deepcopy(valid)
            mutate(forged['coverage'])
            with self.assertRaises(TagDataSummaryError):
                validate_tag_data_summary(forged)
        forged = deepcopy(valid)
        forged['status'] = 'partial'
        forged['coverage']['issues_total'] = 1
        forged['coverage']['issues_by_code']['unexpected_direct_text'] = 1
        with self.assertRaises(TagDataSummaryError):
            validate_tag_data_summary(forged)

    def test_each_public_resource_capacity_is_enforced(self) -> None:
        report = summary(tags(SCALAR + SCALAR))
        for constant, limit in (
            ('MAX_TAG_DATA_OWNERS', 0), ('MAX_TAG_DATA_CONTENTS', 1),
            ('MAX_TAG_DATA_ELEMENTS', 1), ('MAX_TAG_DATA_ISSUES', 1),
            ('MAX_ELEMENTS', 1), ('MAX_ATTRIBUTES', 1),
        ):
            with self.subTest(constant=constant), patch(f'plc_workbench.tag_data_summary.{constant}', limit):
                with self.assertRaises(TagDataSummaryError):
                    validate_tag_data_summary(report)
        with patch('plc_workbench.tag_data_summary.MAX_REPORT_BYTES', 10):
            with self.assertRaises(TagDataSummaryError):
                render_tag_data_summary(report)

    def test_builder_authenticates_before_copying_candidate_data(self) -> None:
        snapshot, inventory, result = capture(tags(SCALAR))
        forged = deepcopy(result)
        forged.contents.append(forged.contents)
        with self.assertRaisesRegex(TagDataSummaryError, '^Tag-data summary validation failed; no summary was produced\\.$'):
            build_tag_data_summary(snapshot, inventory, forged)
        forged = deepcopy(result)
        forged.coverage['owners_total'] = True
        with self.assertRaises(TagDataSummaryError):
            build_tag_data_summary(snapshot, inventory, forged)
        other_snapshot, _, _ = capture(tags(SCALAR, 'Other'))
        with self.assertRaises(TagDataSummaryError):
            build_tag_data_summary(other_snapshot, inventory, result)

    def test_revision_has_closed_contract_and_no_aliasing(self) -> None:
        inputs = capture(tags(SCALAR))
        revision = {'commit': 'a' * 40, 'worktree': 'modified'}
        report = build_tag_data_summary(*inputs, revision=revision)
        revision['commit'] = 'b' * 40
        self.assertEqual(report['tool_revision']['commit'], 'a' * 40)
        for invalid in ({'commit': None, 'worktree': 'clean'},
                        {'commit': 'a' * 40, 'worktree': 'unavailable'},
                        {'commit': None, 'worktree': 'unavailable', 'private': 'value'},
                        {'commit': True, 'worktree': 'modified'}):
            with self.assertRaises(TagDataSummaryError):
                build_tag_data_summary(*inputs, revision=invalid)


if __name__ == '__main__':
    unittest.main()
