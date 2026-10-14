"""Publication-boundary tests using invented source, never proprietary inputs."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from plc_workbench.models import Diagnostic
from plc_workbench.source import analyze_snapshot, capture_snapshot, snapshot_from_bytes
from plc_workbench.summary import SummaryError, build_summary, render_summary, validate_summary


def inventory(secret: str = 'PRIVATE_SENTINEL', reverse: bool = False):
    rungs = [
        f'<Rung Number="915" Type="N"><Comment>{secret}_COMMENT</Comment>'
        f'<Text>XIC({secret}_TAG)[OTE({secret}_OUTPUT),{secret}_OP({secret}_VALUE)];</Text></Rung>',
        f'<Rung Number="916" Type="N"><Text>{secret}_OTHER_OP({secret}_ALIAS,7263.125);</Text></Rung>',
    ]
    if reverse:
        rungs.reverse()
    xml = (
        f'<RSLogix5000Content Owner="{secret}_OWNER" ExportDate="{secret}_DATE">'
        f'<Controller Name="{secret}_CONTROLLER"><Tags><Tag Name="{secret}_TAG" '
        f'TagType="Alias" AliasFor="{secret}_ALIAS" DataType="{secret}_TYPE">'
        f'<Description>{secret}_DESCRIPTION</Description></Tag><Tag Name="DINT"/></Tags>'
        f'<Programs><Program Name="{secret}_PROGRAM"><Routines>'
        f'<Routine Name="{secret}_ROUTINE" Type="RLL"><RLLContent>{"".join(rungs)}</RLLContent></Routine>'
        f'<Routine Name="{secret}_UNKNOWN" Type="{secret}_LANGUAGE"/>'
        '<Routine Name="NoType"/><Routine Name="LiteralSentinel" Type="&lt;missing&gt;"/>'
        '</Routines></Program></Programs>'
        f'<{secret}_ELEMENT xmlns:q="urn:{secret}_NAMESPACE"><q:Payload>{secret}_DATA</q:Payload>'
        f'</{secret}_ELEMENT></Controller></RSLogix5000Content>'
    ).encode()
    result = analyze_snapshot(snapshot_from_bytes(xml))
    result.diagnostics.append(Diagnostic(f'{secret}_CODE', f'{secret}_SEVERITY',
                                        f'{secret}_ID', f'/{secret}_LOCATOR', f'{secret}_MESSAGE'))
    return result


class SummaryTests(unittest.TestCase):
    def test_private_sentinels_and_source_identity_are_excluded(self) -> None:
        result = inventory()
        summary = build_summary(result)
        rendered = render_summary(summary)
        for forbidden in ('PRIVATE', 'SENTINEL', '7263.125', '915', '916', 'DINT',
                          result.snapshot['sha256'], result.snapshot['id']):
            self.assertNotIn(forbidden, rendered)
        self.assertEqual(summary['instructions']['counts'], {'OTE': 1, 'XIC': 1, 'withheld': 2})
        self.assertEqual(summary['routine_types']['missing'], 1)
        self.assertEqual(summary['routine_types']['withheld'], 2)
        self.assertEqual(summary['diagnostics']['by_code']['withheld'], 1)
        self.assertEqual(summary['diagnostics']['by_severity']['withheld'], 1)
        self.assertEqual(summary['status'], 'partial')
        self.assertFalse(summary['coverage']['instruction_count_complete'])
        self.assertEqual(summary['semantic_analysis'], 'not_implemented')
        self.assertEqual(summary['schema_version'], 3)
        self.assertEqual(summary['policy_version'], 2)
        self.assertEqual(summary['sharing_status'], 'aggregate_sync_allowed')
        self.assertNotIn('rungs', summary)  # no occurrence records or layout

    def test_private_renaming_and_reordering_leave_the_aggregate_identical(self) -> None:
        first = build_summary(inventory())
        changed = build_summary(inventory('OTHER_SECRET', reverse=True))
        self.assertEqual(first, changed)
        self.assertEqual(render_summary(first), render_summary(changed))

    def test_independent_fixture_counts_and_coverage(self) -> None:
        path = Path(__file__).resolve().parents[2] / 'public/fixtures/synthetic/controller_demo.L5X'
        summary = build_summary(analyze_snapshot(capture_snapshot(path)))
        self.assertEqual(summary['counts']['total_tag_definitions'], 15)
        self.assertEqual(summary['counts']['instructions'], 25)
        self.assertEqual(summary['coverage']['rungs']['parsed'], 9)
        self.assertEqual(summary['routine_types']['SFC'], 1)
        self.assertEqual(summary['status'], 'partial')
        self.assertEqual(summary['instructions']['total'], 25)

    def test_unknown_vocabulary_cannot_expand_output_keys(self) -> None:
        calls = ''.join(f'SECRET_{i}(PRIVATE);'[:-1] for i in range(10000)) + ';'
        xml = ('<RSLogix5000Content><Controller Name="C"><Programs><Program Name="P">'
               '<Routines><Routine Name="R" Type="RLL"><RLLContent><Rung Number="0" Type="N">'
               f'<Text>{calls}</Text></Rung></RLLContent></Routine></Routines>'
               '</Program></Programs></Controller></RSLogix5000Content>').encode()
        result = analyze_snapshot(snapshot_from_bytes(xml))
        summary = build_summary(result)
        self.assertEqual(summary['instructions']['counts'], {'withheld': 10000})
        self.assertLess(len(render_summary(summary).encode()), 32768)

    def test_future_versions_and_unexpected_states_fail_closed(self) -> None:
        result = inventory()
        for field, value in (('schema_version', 999), ('parser_version', 'PRIVATE_VERSION'),
                             ('analysis_scope', 'PRIVATE_SCOPE'), ('status', 'PRIVATE_STATUS')):
            with self.subTest(field=field), self.assertRaises(SummaryError):
                build_summary(replace(result, **{field: value}))

    def test_strict_counts_and_cross_field_accounting(self) -> None:
        for value in (True, -1, 2.5, float('nan'), 10**15, 'PRIVATE_VALUE'):
            result = inventory()
            result.counts['instructions'] = value
            with self.subTest(value=value), self.assertRaises(SummaryError):
                build_summary(result)
        original = build_summary(inventory())
        changes = (
            ('counts', 'rungs', 7),
            ('counts', 'routines', 9),
            ('counts', 'total_tag_definitions', 99),
            ('instructions', 'total', 20),
        )
        for group, key, value in changes:
            altered = deepcopy(original)
            altered[group][key] = value
            with self.subTest(key=key), self.assertRaises(SummaryError):
                validate_summary(altered)

    def test_renderer_rejects_added_fields_and_arbitrary_labels(self) -> None:
        for mutate in (
            lambda s: s.update(raw_source='PRIVATE_SOURCE'),
            lambda s: s['instructions']['counts'].update(PRIVATE_OPCODE=1),
            lambda s: s['diagnostics']['by_code'].update(PRIVATE_CODE=1),
            lambda s: s['coverage']['rungs'].update(PRIVATE_KEY=1),
            lambda s: s['tool_revision'].update(commit='PRIVATE_REVISION'),
            lambda s: s.update(status='PRIVATE_STATUS'),
        ):
            summary = build_summary(inventory())
            mutate(summary)
            with self.assertRaises(SummaryError) as caught:
                render_summary(summary)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_revision_is_explicit_and_only_fixed_metadata_is_accepted(self) -> None:
        revision = {'commit': 'a' * 40, 'worktree': 'modified'}
        summary = build_summary(inventory(), revision=revision)
        self.assertEqual(json.loads(render_summary(summary))['tool_revision'], revision)
        self.assertEqual(build_summary(inventory())['tool_revision'],
                         {'commit': None, 'worktree': 'unavailable'})
        for bad in ({'commit': None, 'worktree': 'clean'},
                    {'commit': 'a' * 40, 'worktree': 'unavailable'},
                    {**revision, 'branch': 'PRIVATE_BRANCH'}):
            with self.assertRaises(SummaryError):
                build_summary(inventory(), revision=bad)

    def test_measurements_outside_supported_parser_limits_are_rejected(self) -> None:
        for key, value in (('max_branch_depth', 65), ('max_legs_in_group', 20001),
                           ('height_lanes', 20001), ('width_instructions', 20001)):
            result = inventory()
            result.rungs[0].metrics[key] = value
            with self.subTest(key=key), self.assertRaises(SummaryError):
                build_summary(result)

    def test_unknown_diagnostic_severity_cannot_claim_complete_status(self) -> None:
        result = analyze_snapshot(snapshot_from_bytes(
            b'<RSLogix5000Content><Controller Name="C"/></RSLogix5000Content>'))
        self.assertEqual(result.status, 'complete')
        result.diagnostics.append(Diagnostic('PRIVATE_CODE', 'new_error', None, '/PRIVATE', 'PRIVATE_MESSAGE'))
        with self.assertRaises(SummaryError):
            build_summary(result)
        partial = build_summary(replace(result, status='partial'))
        self.assertEqual(partial['diagnostics']['by_severity']['withheld'], 1)


if __name__ == '__main__':
    unittest.main()
