"""Count-only publication from invented private SFC structure evidence."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest

from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.sfc_summary import (
    SfcSummaryError, build_sfc_summary, render_sfc_summary, validate_sfc_summary,
)
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def sfc_fixture(routines: str = '<Routine Name="PRIVATE_ROUTINE" Type="SFC"><SFCContent/></Routine>'):
    snapshot = snapshot_from_bytes((
        '<RSLogix5000Content><Controller Name="PRIVATE_CONTROLLER"><Programs>'
        f'<Program Name="PRIVATE_PROGRAM"><Routines>{routines}</Routines></Program>'
        '</Programs></Controller></RSLogix5000Content>'
    ).encode())
    inventory = analyze_snapshot(snapshot)
    result = analyze_sfc_structure(snapshot, inventory)
    return snapshot, inventory, result


def fixture_summary(routines: str | None = None):
    args = sfc_fixture() if routines is None else sfc_fixture(routines)
    return build_sfc_summary(*args)


class SfcSummaryTests(unittest.TestCase):
    def test_zero_and_empty_content_are_complete_only_for_structure(self) -> None:
        empty = fixture_summary()
        zero = fixture_summary('<Routine Name="PRIVATE_RLL" Type="RLL"><RLLContent/></Routine>')
        for summary, total in ((empty, 1), (zero, 0)):
            self.assertEqual(summary['status'], 'complete')
            self.assertEqual(summary['source_sfc_routines'], total)
            self.assertEqual(summary['counts']['routines']['total'], total)
            self.assertEqual(summary['counts']['elements']['total'], 0)
            self.assertEqual(summary['semantic_analysis'], 'not_implemented')
            validate_sfc_summary(json.loads(render_sfc_summary(summary)))

    def test_multiple_contents_count_all_revisions_and_scope_ids_per_content(self) -> None:
        summary = fixture_summary(
            '<Routine Name="PRIVATE_FLOW" Type="SFC">'
            '<SFCContent OnlineEditType="Original"><Step ID="01"/>'
            '<Transition ID="2"/><DirectedLink FromID="1" ToID="2"/></SFCContent>'
            '<SFCContent OnlineEditType="PendingEdits"><Step ID="1"/>'
            '<Stop ID="2"/><DirectedLink FromID="1" ToID="2"/></SFCContent></Routine>'
        )
        counts = summary['counts']
        self.assertEqual(counts['routines']['with_content'], 1)
        self.assertEqual(counts['contents']['total'], 2)
        self.assertEqual(counts['contents']['by_edit_kind']['Original'], 1)
        self.assertEqual(counts['contents']['by_edit_kind']['PendingEdits'], 1)
        self.assertEqual(counts['blocks']['duplicate_groups'], 0)
        self.assertEqual(counts['links']['by_status'], {'resolved': 2, 'unresolved': 0})
        self.assertEqual(summary['status'], 'complete')

    def test_privacy_and_opaque_st_text_only_yield_counts(self) -> None:
        snapshot, inventory, result = sfc_fixture(
            '<Routine Name="PRIVATE_SEQUENCE" Type="SFC"><SFCContent PRIVATE_ATTR="PRIVATE_VALUE">'
            '<Step ID="123"><Action ID="124" Name="PRIVATE_ACTION"><Body><STContent>'
            '<Line Number="0"><![CDATA[PRIVATE_TAG:=42;]]></Line><Line Number="1"/>'
            '</STContent></Body></Action></Step>'
            '<Transition ID="125"><Condition><STContent><Line>PRIVATE_CONDITION</Line>'
            '</STContent></Condition></Transition>'
            '<DirectedLink FromID="123" ToID="125"/></SFCContent></Routine>'
        )
        summary = build_sfc_summary(snapshot, inventory, result, revision={'commit': 'a' * 40, 'worktree': 'clean'})
        rendered = render_sfc_summary(summary)
        self.assertNotIn('PRIVATE', rendered)
        self.assertNotIn(snapshot.sha256, rendered)
        self.assertNotIn(result.elements[0]['id'], rendered)
        self.assertEqual(summary['counts']['structured_text'],
                         {'lines': 3, 'total_characters': len('PRIVATE_TAG:=42;PRIVATE_CONDITION')})
        self.assertEqual(summary['tool_revision'], {'commit': 'a' * 40, 'worktree': 'clean'})

    def test_duplicate_and_unresolved_evidence_issue_counts_reconcile(self) -> None:
        summary = fixture_summary(
            '<Routine Name="PRIVATE_FLOW" Type="SFC"><SFCContent OnlineEditType="PRIVATE_EDIT">'
            '<Step ID="1"/><Stop ID="01"/><Action ID="4"/><Step/><Transition ID="-1"/>'
            '<DirectedLink FromID="1" ToID="404"/><DirectedLink FromID="4"/>'
            '<PRIVATE_UNKNOWN/></SFCContent></Routine>'
            '<Routine Name="PRIVATE_MISSING" Type="SFC"><EncodedData/></Routine>'
        )
        counts = summary['counts']
        self.assertEqual(summary['status'], 'partial')
        self.assertEqual(counts['blocks']['duplicate_groups'], 1)
        self.assertEqual(counts['blocks']['duplicate_members'], 2)
        self.assertEqual(counts['link_endpoints']['by_status']['ambiguous_target'], 1)
        self.assertEqual(counts['issues']['by_code']['link_endpoint_unresolved'], 4)
        self.assertEqual(counts['routines']['without_content'], 1)
        self.assertEqual(counts['routines']['with_protection'], 1)
        self.assertNotIn('PRIVATE', render_sfc_summary(summary))

    def test_rejects_types_extra_fields_and_revision_leaks(self) -> None:
        original = fixture_summary()
        mutations = [
            lambda s: s.update(PRIVATE_FIELD='PRIVATE_VALUE'),
            lambda s: s.update(schema_version=True),
            lambda s: s['counts']['routines'].update(total=True),
            lambda s: s['counts']['routines'].update(total=-1),
            lambda s: s['counts']['contents']['by_edit_kind'].update(PRIVATE_KIND=0),
            lambda s: s['tool_revision'].update(commit='PRIVATE_COMMIT', worktree='clean'),
            lambda s: s['tool_revision'].update(commit='a' * 40, worktree='unavailable'),
        ]
        for mutation in mutations:
            altered = deepcopy(original)
            mutation(altered)
            with self.subTest(summary=altered), self.assertRaises(SfcSummaryError) as caught:
                render_sfc_summary(altered)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_rejects_count_partitions_and_false_complete_status(self) -> None:
        original = fixture_summary('<Routine Name="PRIVATE_FLOW" Type="SFC"><SFCContent>'
                                   '<Step ID="1"/><Stop ID="2"/>'
                                   '<DirectedLink FromID="1" ToID="2"/></SFCContent></Routine>')
        mutations = [
            lambda s: s.update(source_sfc_routines=2),
            lambda s: s['counts']['routines'].update(without_content=1),
            lambda s: s['counts']['contents']['by_edit_kind'].update(absent=0),
            lambda s: s['counts']['elements'].update(total=999),
            lambda s: s['counts']['blocks'].update(duplicate_groups=1),
            lambda s: s['counts']['links']['by_status'].update(resolved=0, unresolved=1),
            lambda s: s['counts']['structured_text'].update(total_characters=1),
            lambda s: s.update(status='partial'),
        ]
        for mutation in mutations:
            altered = deepcopy(original)
            mutation(altered)
            with self.subTest(summary=altered), self.assertRaises(SfcSummaryError):
                validate_sfc_summary(altered)

    def test_rejects_issue_forgery_and_unsupported_endpoint_without_valid_ids(self) -> None:
        original = fixture_summary('<Routine Name="PRIVATE_FLOW" Type="SFC"><SFCContent>'
                                   '<Step/><DirectedLink/></SFCContent></Routine>')
        altered = deepcopy(original)
        altered['counts']['issues']['by_code']['block_id_missing'] = 0
        altered['counts']['issues']['total'] -= 1
        with self.assertRaises(SfcSummaryError):
            validate_sfc_summary(altered)
        altered = deepcopy(original)
        altered['counts']['link_endpoints']['by_status'].update(missing_attribute=1, unsupported_kind=1)
        with self.assertRaises(SfcSummaryError):
            validate_sfc_summary(altered)

    def test_private_tampering_and_foreign_snapshot_cannot_build_summary(self) -> None:
        snapshot, inventory, result = sfc_fixture()
        for altered in (replace(result, status='partial'), replace(result, schema_version=True)):
            with self.subTest(result=altered), self.assertRaises(SfcSummaryError):
                build_sfc_summary(snapshot, inventory, altered)
        foreign = snapshot_from_bytes(snapshot.data.replace(b'PRIVATE_PROGRAM', b'PRIVATE_FOREIGN'))
        with self.assertRaises(SfcSummaryError):
            build_sfc_summary(foreign, inventory, result)
        with self.assertRaises(SfcSummaryError):
            build_sfc_summary(snapshot, replace(inventory, schema_version=True), result)

    def test_unsupported_endpoint_requires_possible_unique_nonflow_block(self) -> None:
        summary = fixture_summary('<Routine Name="PRIVATE_FLOW" Type="SFC"><SFCContent>'
                                  '<Step ID="1"/><DirectedLink FromID="1" ToID="1"/>'
                                  '</SFCContent></Routine>')
        # Preserve every partition and issue count while claiming a nonflow
        # endpoint in a content whose only ID-bearing block is a flow step.
        summary['status'] = 'partial'
        counts = summary['counts']
        counts['links']['by_status'].update(resolved=0, unresolved=1)
        counts['link_endpoints']['by_status'].update(resolved=1, unsupported_kind=1)
        counts['issues']['total'] = 1
        counts['issues']['by_code']['link_endpoint_unresolved'] = 1
        with self.assertRaises(SfcSummaryError):
            validate_sfc_summary(summary)

    def test_unexpected_direct_text_capacity_excludes_opaque_records(self) -> None:
        summary = fixture_summary('<Routine Name="PRIVATE_FLOW" Type="SFC"><SFCContent>'
                                  '<Step ID="1"><Action ID="2"><Body><STContent>'
                                  '<Line>PRIVATE_TEXT</Line></STContent></Body></Action></Step>'
                                  '</SFCContent></Routine>')
        # Only the content, step and action can emit this issue; opaque ST
        # records retain text without interpreting it or flagging it here.
        self.assertEqual(summary['counts']['elements']['total'], 5)
        summary['status'] = 'partial'
        summary['counts']['issues']['total'] = 4
        summary['counts']['issues']['by_code']['unexpected_direct_text'] = 4
        with self.assertRaises(SfcSummaryError):
            validate_sfc_summary(summary)

    def test_outside_content_vendor_markers_and_routine_text_are_counted(self) -> None:
        summary = fixture_summary(
            '<Routine Name="PRIVATE_VENDOR" Type="SFC"><SFCContent/>'
            '<PRIVATE_WRAPPER><Step ID="1"/></PRIVATE_WRAPPER></Routine>'
            '<Routine Name="PRIVATE_TEXT" Type="SFC">PRIVATE_TEXT<SFCContent/></Routine>'
            '<Routine Name="PRIVATE_DESC" Type="SFC"><Description>PRIVATE_DESC</Description>'
            '<EncryptionInfo/><SFCContent/></Routine>'
        )
        counts = summary['counts']
        self.assertEqual(counts['routines']['with_unmodeled_content'], 2)
        self.assertEqual(counts['issues']['by_code']['routine_content_unmodeled'], 2)
        self.assertEqual(counts['elements']['total'], 0)
        self.assertEqual(summary['status'], 'partial')
        self.assertNotIn('PRIVATE', render_sfc_summary(summary))
        for value in (1, 4):
            altered = deepcopy(summary)
            altered['counts']['routines']['with_unmodeled_content'] = value
            with self.subTest(value=value), self.assertRaises(SfcSummaryError):
                validate_sfc_summary(altered)


if __name__ == '__main__':
    unittest.main()
