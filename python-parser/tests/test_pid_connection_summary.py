"""PID public summaries admit closed counts and reject private or forged data."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.pid_connection_summary import (PidConnectionSummaryError,
    build_pid_connection_summary, render_pid_connection_summary, validate_pid_connection_summary)
from test_pid import tag
from test_pid_connections import capture
from test_pid_members import data, full_members


class PidConnectionSummaryTests(unittest.TestCase):
    def test_aggregate_summary_has_no_names_values_ids_or_source_hash(self) -> None:
        inputs = capture('MOV(PV,Loop.SP)PID(Loop,PV,0,CV,0,0,0);')
        summary = build_pid_connection_summary(*inputs)
        rendered = render_pid_connection_summary(summary)
        self.assertEqual(json.loads(rendered), summary)
        self.assertLessEqual(len(rendered.encode('utf-8')), 4096)
        self.assertEqual(summary['coverage'], inputs[-1].coverage)
        for private in ('Loop', 'PV', '001.50', inputs[0].id, inputs[-1].occurrences[0]['id']):
            self.assertNotIn(private, rendered)
        self.assertEqual(summary['tool_revision'], {'commit': None, 'worktree': 'unavailable'})
        self.assertEqual(summary['sharing_status'], 'aggregate_sync_allowed')

    def test_zero_and_partial_populations_build_without_arbitrary_minimums(self) -> None:
        for text in ('MOV(PV,CV);', 'PID(Loop,PV);', 'PID(Loop,PV,0,CV,Missing,0,0);',
                     'PID(Loop,PV,0,CV,Loop,0,0);',
                     'MOV(PV,Loop.DATA[0])PID(Loop,PV,0,CV,0,0,0);',
                     'PID(Loop,PV,0,CV,Loop,0,0)PID(Loop,PV,0,CV,0,0,0);'):
            with self.subTest(text=text):
                inputs = capture(text)
                summary = build_pid_connection_summary(*inputs)
                self.assertEqual(summary['status'], inputs[-1].status)
                validate_pid_connection_summary(summary)

    def test_master_occurrence_and_member_group_partitions_are_checked(self) -> None:
        tags = tag(data(full_members())) + tag(data(full_members()), 'Master')
        inputs = capture('PID(Master,PV,0,CV,0,0,0)PID(Loop,PV,0,CV,Master,0,0);', tags)
        original = build_pid_connection_summary(*inputs)
        changes = (
            lambda c: c.update(master_candidate_links=0),
            lambda c: c.update(master_candidate_links=2),
            lambda c: c.update(master_self_references=3),
            lambda c: c.update(incoming_condition_links=0),
            lambda c: c.update(occurrences_without_condition_context=1),
            lambda c: c['control_by_status'].update(linked=0),
            lambda c: c['member_addresses_by_group'].update(setpoint=1),
            lambda c: c['member_addresses_by_group'].update(unknown=1),
            lambda c: c['address_kinds'].update(direct_member=1),
            lambda c: c['slots_by_status'].update(exact_address=0),
        )
        for index, change in enumerate(changes):
            forged = deepcopy(original)
            change(forged['coverage'])
            with self.subTest(index=index), self.assertRaises(PidConnectionSummaryError):
                validate_pid_connection_summary(forged)

    def test_unknown_keys_boolean_counts_and_status_forgery_are_rejected(self) -> None:
        original = build_pid_connection_summary(*capture())
        changes = (
            lambda s: s.update(private='PrivateSentinel'),
            lambda s: s.update(schema_version=True),
            lambda s: s.update(status='partial'),
            lambda s: s['coverage'].update(occurrences_total=True),
            lambda s: s['coverage'].update(private=1),
            lambda s: s['coverage']['slots_by_status'].update(private=1),
            lambda s: s['coverage']['slots_by_status'].update(exact_address=-1),
            lambda s: s['coverage'].update(source_pid_partial=2),
            lambda s: s['coverage'].update(occurrences_total=10**13),
            lambda s: s['tool_revision'].update(commit='PrivateSentinel'),
        )
        for index, change in enumerate(changes):
            forged = deepcopy(original)
            change(forged)
            with self.subTest(index=index), self.assertRaises(PidConnectionSummaryError) as caught:
                render_pid_connection_summary(forged)
            self.assertNotIn('PrivateSentinel', str(caught.exception))

    def test_source_replay_precedes_public_count_copy(self) -> None:
        inputs = list(capture())
        inputs[-1].occurrences[0]['master']['operand_id'] = 'PrivateSentinel'
        with self.assertRaises(PidConnectionSummaryError) as caught:
            build_pid_connection_summary(*inputs)
        self.assertNotIn('PrivateSentinel', str(caught.exception))

    def test_master_dispositions_fit_slot_and_linked_control_populations(self) -> None:
        original = build_pid_connection_summary(*capture())
        for status in ('binding_gap', 'identity_gap', 'namespace_gap'):
            forged = deepcopy(original)
            forged['coverage']['masters_by_status']['literal'] -= 1
            forged['coverage']['masters_by_status'][status] += 1
            forged['status'] = 'partial'
            with self.subTest(status=status), self.assertRaises(PidConnectionSummaryError):
                validate_pid_connection_summary(forged)
        inputs = capture('PID(Loop,PV,0,CV,0,0,0)PID(PV,PV,0,CV,Loop,0,0);')
        forged = build_pid_connection_summary(*inputs)
        self.assertEqual(forged['coverage']['control_by_status']['linked'], 1)
        forged['coverage']['masters_by_status']['single_occurrence'] = 0
        forged['coverage']['masters_by_status']['multiple_occurrences'] = 1
        forged['coverage']['master_candidate_links'] = 2
        with self.assertRaises(PidConnectionSummaryError):
            validate_pid_connection_summary(forged)

    def test_revision_shapes_and_report_budget_are_bounded(self) -> None:
        inputs = capture()
        for revision in ({'commit': 'a' * 40, 'worktree': 'clean'},
                         {'commit': 'b' * 40, 'worktree': 'modified'}):
            self.assertEqual(build_pid_connection_summary(*inputs, revision=revision)['tool_revision'], revision)
        for revision in ({'commit': 'A' * 40, 'worktree': 'clean'},
                         {'commit': None, 'worktree': 'clean'},
                         {'commit': 'a' * 40, 'worktree': 'unavailable'},
                         {'commit': None, 'worktree': True}):
            with self.subTest(revision=revision), self.assertRaises(PidConnectionSummaryError):
                build_pid_connection_summary(*inputs, revision=revision)
        summary = build_pid_connection_summary(*inputs)
        with patch('plc_workbench.pid_connection_summary.MAX_REPORT_BYTES', 100):
            with self.assertRaises(PidConnectionSummaryError):
                render_pid_connection_summary(summary)
        for limit in ('MAX_PID_CONNECTION_RECORDS', 'MAX_PID_CONNECTION_BYTES', 'MAX_PID_CONNECTION_JSON_BYTES'):
            with self.subTest(limit=limit), patch('plc_workbench.pid_connection_summary.' + limit, 1):
                with self.assertRaises(PidConnectionSummaryError):
                    validate_pid_connection_summary(summary)


if __name__ == '__main__':
    unittest.main()
