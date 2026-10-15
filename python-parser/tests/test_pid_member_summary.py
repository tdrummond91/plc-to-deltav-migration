"""PID member publication accepts only fixed count vocabularies and metadata."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.pid_member_summary import (
    CONSTANTS, PidMemberSummaryError, build_pid_member_summary,
    render_pid_member_summary, validate_pid_member_summary,
)
from test_pid import call, capture, tag
from test_pid_members import captured, data, full_members, scalar
from plc_workbench.pid_members import analyze_pid_members


class PidMemberSummaryTests(unittest.TestCase):
    def test_fixed_small_summary_contains_no_source_names_values_or_links(self) -> None:
        inputs = captured(full_members())
        summary = build_pid_member_summary(*inputs)
        rendered = render_pid_member_summary(summary)
        self.assertEqual(set(summary), set(CONSTANTS) | {'status', 'tool_revision', 'coverage'})
        self.assertEqual(json.loads(rendered), summary)
        self.assertLess(len(rendered.encode()), 3000)
        for secret in ('Loop', 'Invented', '001.50', inputs[0].sha256, inputs[-1].members[0]['element_id']):
            self.assertNotIn(secret, rendered)
        self.assertEqual(summary['status'], 'complete')
        self.assertEqual(rendered, render_pid_member_summary(deepcopy(summary)))

    def test_equal_shapes_hide_renames_and_saved_value_changes(self) -> None:
        summaries = []
        for name, value in (('SecretA', '1.500'), ('SecretB', '-999')):
            inputs = capture(call(name) + ';', tag(data(scalar('SP', value=value)), name=name))
            summaries.append(build_pid_member_summary(*inputs, analyze_pid_members(*inputs)))
        self.assertEqual(*summaries)

    def test_missing_duplicate_unknown_and_all_header_gaps_validate(self) -> None:
        for member in ('', scalar('SP'), scalar('SP') * 3, scalar('Unknown'),
                       scalar('SP', datatype='DINT'), '<StructureMember Name="SP"/>',
                       '<ArrayMember Name="DATA" DataType="REAL" Dimensions="17"/>',
                       scalar('SP', extra=' x:Dimensions="0"'),
                       '<DataValueMember Name="SP" Value="1"/>'):
            with self.subTest(member=member):
                summary = build_pid_member_summary(*captured(member, namespace=' xmlns:x="urn:test"'))
                self.assertEqual(summary['status'], 'partial')
                validate_pid_member_summary(summary)

    def test_upstream_gaps_and_empty_population_status_are_exact(self) -> None:
        for text, expected in (('XIC(PV);', 'complete'), ('PID(Missing,PV,0,CV,0,0,0);', 'partial'),
                               ('PID(Loop', 'partial')):
            summary = build_pid_member_summary(*captured(full_members(), text=text))
            self.assertEqual(summary['status'], expected)
            self.assertEqual(summary['coverage']['source_pid_partial'], int(expected == 'partial'))
            self.assertEqual(summary['coverage']['structures_with_gaps'], 0)
            summary['status'] = 'partial' if expected == 'complete' else 'complete'
            with self.assertRaises(PidMemberSummaryError):
                validate_pid_member_summary(summary)

    def test_closed_vocabulary_types_and_revision_are_strict(self) -> None:
        original = build_pid_member_summary(*captured(full_members()))
        mutations = [lambda s: s.update(private='leak'), lambda s: s.update(schema_version=True),
            lambda s: s.update(status='unknown'), lambda s: s['coverage'].update(private=1),
            lambda s: s['coverage']['members_by_group'].update(secret=0),
            lambda s: s['coverage']['members_by_status'].update(secret=0),
            lambda s: s['coverage'].update(members_total=True),
            lambda s: s['coverage'].update(members_total=-1),
            lambda s: s['coverage'].update(source_pid_partial=2),
            lambda s: s['tool_revision'].update(commit='abc'),
            lambda s: s['tool_revision'].update(worktree='clean'),
            lambda s: s['tool_revision'].update(extra='private')]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                summary = deepcopy(original)
                mutation(summary)
                with self.assertRaises(PidMemberSummaryError):
                    validate_pid_member_summary(summary)
        revision = {'commit': 'a' * 40, 'worktree': 'modified'}
        summary = build_pid_member_summary(*captured(full_members()), revision=revision)
        revision['commit'] = 'b' * 40
        self.assertEqual(summary['tool_revision']['commit'], 'a' * 40)
        validate_pid_member_summary(summary)

    def test_count_partitions_presence_duplicates_and_capacities_reject_forgery(self) -> None:
        original = build_pid_member_summary(*captured(scalar('SP') * 3 + scalar('Unknown')))
        mutations = [lambda c: c.update(structures_total=0),
            lambda c: c.update(distinct_backing_owners=2),
            lambda c: c.update(missing_catalog_fields=49),
            lambda c: c.update(duplicate_catalog_fields=2),
            lambda c: c.update(duplicate_member_records=2),
            lambda c: c.update(structures_with_missing=0),
            lambda c: c.update(structures_with_duplicates=0),
            lambda c: c.update(structures_with_gaps=0),
            lambda c: c['members_by_group'].update(unknown=0),
            lambda c: c['members_by_status'].update(matched=4)]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                summary = deepcopy(original)
                mutation(summary['coverage'])
                with self.assertRaises(PidMemberSummaryError):
                    validate_pid_member_summary(summary)
        with patch('plc_workbench.pid_member_summary.MAX_PID_MEMBER_EVIDENCE_BYTES', 100):
            with self.assertRaises(PidMemberSummaryError):
                validate_pid_member_summary(original)
        with patch('plc_workbench.pid_member_summary.MAX_REPORT_BYTES', 100):
            with self.assertRaises(PidMemberSummaryError):
                render_pid_member_summary(original)

    def test_summary_authenticates_canonical_private_records(self) -> None:
        inputs = captured(scalar('SP'))
        forged = deepcopy(inputs[-1])
        forged.members[0]['field'] = 'KI'
        with self.assertRaises(PidMemberSummaryError):
            build_pid_member_summary(*inputs[:-1], forged)
        foreign = captured(scalar('SP', value='999'))[-1]
        with self.assertRaises(PidMemberSummaryError):
            build_pid_member_summary(*inputs[:-1], foreign)

    def test_catalog_capacity_rejects_impossible_group_and_array_counts(self) -> None:
        original = build_pid_member_summary(*captured(full_members()))
        grouped = deepcopy(original)
        groups = grouped['coverage']['members_by_group']
        groups.update(dict.fromkeys(groups, 0))
        groups.update(tuning=49, internal=2)
        array = deepcopy(original)
        array['coverage']['members_by_status'].update(matched=49, array_header_matched=2)
        scalar_only = deepcopy(original)
        scalar_only['coverage']['members_by_status'].update(matched=51, array_header_matched=0)
        for forged in (grouped, array, scalar_only):
            with self.subTest(coverage=forged['coverage']), self.assertRaises(PidMemberSummaryError):
                validate_pid_member_summary(forged)
        # Multiple captured copies of DATA or a scalar field remain legitimate
        # evidence; catalog capacities include their explicit duplicate extras.
        for extra in (scalar('SP'), '<ArrayMember Name="DATA" DataType="REAL" Dimensions="17"/>'):
            validate_pid_member_summary(build_pid_member_summary(*captured(full_members() + extra)))


if __name__ == '__main__':
    unittest.main()
