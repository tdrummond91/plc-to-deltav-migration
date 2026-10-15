"""Unary math publication stays count-only and keeps frozen report contracts."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from plc_workbench.models import InventoryResult
from plc_workbench.reference_summary import (
    CONSTANTS, V6_CONSTANTS, V7_CONSTANTS, V8_CONSTANTS, V9_CONSTANTS, ReferenceSummaryError, build_reference_summary,
    render_reference_summary, validate_reference_summary,
)
from plc_workbench.references import analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.summary import build_summary


ROOT = Path(__file__).resolve().parents[2]
FLAG_REPORT = ROOT / 'public/inspection/work-check-20261014T191741Z-2009d02d.json'
REVISION = {'commit': 'a' * 40, 'worktree': 'modified'}
HISTORICAL_REPORT_NAMES = (
    'work-check-20261013T221312Z-4c286cdf.json',
    'work-check-20261013T221358Z-0ad977a3.json',
    'work-check-20261013T234851Z-b10d84dc.json',
    'work-check-20261014T051259Z-72d3ad4c.json',
    'work-check-20261014T072717Z-4d71aaff.json',
    'work-check-20261014T075024Z-a11d87b8.json',
    'work-check-20261014T162634Z-2a7e40fe.json',
    'work-check-20261014T175611Z-c63b79cc.json',
    'work-check-20261014T183844Z-26f5b84a.json',
    'work-check-20261014T191741Z-2009d02d.json',
)


def inventory(text: str, *, secret: str = 'PRIVATE_MATH') -> InventoryResult:
    xml = (
        f'<RSLogix5000Content Owner="{secret}_OWNER"><Controller Name="{secret}_CONTROLLER">'
        f'<Tags><Tag Name="{secret}_INPUT" TagType="Base"/>'
        f'<Tag Name="{secret}_OUTPUT" TagType="Base"/>'
        f'<Tag Name="{secret}_ALIAS" TagType="Alias" AliasFor="{secret}_INPUT.Member[2]"/>'
        '</Tags><Programs><Program Name="PRIVATE_PROGRAM"><Routines>'
        '<Routine Name="PRIVATE_ROUTINE" Type="RLL"><RLLContent>'
        f'<Rung Number="873" Type="N"><Comment>{secret}_COMMENT</Comment>'
        f'<Text><![CDATA[{text}]]></Text></Rung></RLLContent></Routine></Routines>'
        '</Program></Programs></Controller></RSLogix5000Content>'
    ).encode('utf-8')
    return analyze_snapshot(snapshot_from_bytes(xml))


def summary(source: InventoryResult) -> dict:
    return build_reference_summary(source, analyze_references(source), revision=REVISION)


class MathSummaryTests(unittest.TestCase):
    def test_unary_roots_and_literals_publish_current_counts_without_changing_source(self) -> None:
        text = ('ABS(PRIVATE_MATH_ALIAS,PRIVATE_MATH_OUTPUT.Member[7])'
                'LN(93578.125,PRIVATE_MATH_OUTPUT)SQR(-16.875,27361.25);')
        source = inventory(text)
        before = deepcopy(source.to_dict())
        source_report = build_summary(source, revision=REVISION)
        report = summary(source)
        self.assertEqual(source.to_dict(), before)
        self.assertEqual(report['source_summary'], source_report)
        self.assertEqual((source.schema_version, source.parser_version), (3, 'source-inventory-3'))
        self.assertEqual((report['schema_version'], report['exporter_version'], report['analyzer_version']),
                         (12, 'reference-summary-12', 'source-references-9'))
        self.assertEqual({key: report[key] for key in CONSTANTS}, CONSTANTS)
        self.assertEqual(report['source_summary']['schema_version'], 4)
        self.assertEqual(report['source_summary']['instructions']['counts'],
                         {'ABS': 1, 'LN': 1, 'SQR': 1, 'withheld': 0})
        self.assertEqual(report['coverage'], {'rungs_total': 1, 'rungs_analyzed': 1,
                                             'instructions_total': 3, 'instructions_catalogued': 3})
        self.assertEqual(report['operands']['total'], 6)
        self.assertEqual(report['operands']['by_status']['root_bound'], 3)
        self.assertEqual(report['operands']['by_status']['literal'], 3)
        self.assertEqual(sum(report['operands']['by_status'].values()), 6)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['aliases']['by_status']['root_bound'], 1)
        for field in ('member_validation', 'semantic_analysis', 'effect_analysis'):
            self.assertEqual(report[field], 'not_implemented')
        rendered = render_reference_summary(report)
        self.assertEqual(json.loads(rendered), report)
        for forbidden in ('PRIVATE', '93578.125', '-16.875', '27361.25', 'Member',
                          'raw_text', 'target_id', 'alias_chain', 'scope_id',
                          source.snapshot['id'], source.snapshot['sha256']):
            self.assertNotIn(forbidden, rendered)
        renamed = inventory(text.replace('PRIVATE_MATH', 'OTHER_SECRET'), secret='OTHER_SECRET')
        self.assertEqual(summary(renamed), report)

    def test_partial_unary_occurrences_reconcile_existing_status_and_reason_buckets(self) -> None:
        source = inventory('ABS(,PRIVATE_MATH_OUTPUT)LN(#PRIVATE_MATH_INPUT,PRIVATE_MATH_OUTPUT)'
                           'SQR(PRIVATE_MATH_INPUT)LN(PRIVATE_MATH_INPUT,PRIVATE_MATH_OUTPUT,9)'
                           'SQRT(PRIVATE_MATH_INPUT,PRIVATE_MATH_OUTPUT);')
        report = summary(source)
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['coverage']['instructions_total'], 5)
        self.assertEqual(report['coverage']['instructions_catalogued'], 2)
        expected = dict.fromkeys(report['operands']['by_status'], 0)
        expected.update(empty=1, root_bound=2, unsupported_address=1,
                        argument_count_mismatch=4, unsupported_instruction=2)
        self.assertEqual(report['operands']['by_status'], expected)
        self.assertEqual(report['operands']['total'], 10)
        self.assertEqual(sum(expected.values()), report['operands']['total'])
        self.assertEqual(report['source_summary']['ladder_metrics']['totals']['argument_slots'], 10)
        self.assertEqual(report['operands']['by_reason']['unsupported_address']['malformed_address'], 1)
        self.assertEqual(report['operands']['malformed_address_shapes']['leading_hash_static_address'], 1)
        self.assertEqual(json.loads(render_reference_summary(report)), report)

    def test_unary_count_and_coverage_mismatches_fail_public_validation(self) -> None:
        original = summary(inventory('ABS(93578.125,PRIVATE_MATH_OUTPUT)LN(,PRIVATE_MATH_OUTPUT);'))
        for mutate in (
            lambda r: r['operands']['by_status'].update(literal=2),
            lambda r: r['operands'].update(total=5),
            lambda r: r['coverage'].update(instructions_catalogued=3),
            lambda r: r['coverage'].update(instructions_total=3),
            lambda r: r.update(status='complete'),
            lambda r: r['operands']['by_status'].update(math_destination=0),
        ):
            report = deepcopy(original)
            mutate(report)
            with self.assertRaises(ReferenceSummaryError):
                render_reference_summary(report)

    def test_frozen_v6_keeps_flags_and_metadata_while_version_mixes_are_rejected(self) -> None:
        historical = json.loads(FLAG_REPORT.read_text(encoding='utf-8'))['analysis']['reference_summary']
        self.assertEqual({key: historical[key] for key in V6_CONSTANTS}, V6_CONSTANTS)
        self.assertEqual(historical['operands']['by_status']['system_flag'], 1)
        self.assertEqual(json.loads(render_reference_summary(historical)), historical)
        current = summary(inventory('XIC(S:FS)ABS(1,PRIVATE_MATH_OUTPUT);'))
        self.assertEqual(set(current) - {'routine_instruction_shapes', 'routine_targets', 'routine_target_metadata', 'routine_graph'}, set(historical))
        self.assertEqual(current['operands']['by_status'].keys(), historical['operands']['by_status'].keys())
        for base, field, value in (
            (historical, 'schema_version', 7),
            (historical, 'exporter_version', 'reference-summary-7'),
            (historical, 'analyzer_version', 'source-references-6'),
            (current, 'schema_version', 6),
            (current, 'exporter_version', 'reference-summary-6'),
            (current, 'analyzer_version', 'source-references-5'),
        ):
            report = deepcopy(base)
            report[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)
        for constants in (V6_CONSTANTS, V7_CONSTANTS, V8_CONSTANTS, V9_CONSTANTS, CONSTANTS):
            report = summary(inventory('ABS(1,PRIVATE_MATH_OUTPUT);'))
            report.update(constants)
            if constants['schema_version'] < 10:
                del report['routine_targets']
                del report['routine_target_metadata']
                del report['routine_graph']
            if constants['schema_version'] < 9:
                del report['routine_instruction_shapes']
            report['operands']['by_status'].update(literal=0, system_flag=1)
            with self.subTest(version=constants['schema_version']), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)

    def test_forged_private_unary_classification_and_old_analyzer_fail_canonical_reanalysis(self) -> None:
        source = inventory('ABS(93578.125,PRIVATE_MATH_OUTPUT);')
        references = analyze_references(source)
        self.assertEqual((references.schema_version, references.analyzer_version), (6, 'source-references-9'))
        forged = deepcopy(references.operands)
        forged[0].update(status='unsupported_instruction')
        for altered in (replace(references, operands=forged),
                        replace(references, analyzer_version='source-references-5'),
                        replace(references, schema_version=4)):
            with self.assertRaises(ReferenceSummaryError) as caught:
                build_reference_summary(source, altered)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_all_ten_returned_nested_reference_reports_validate_without_rewriting(self) -> None:
        versions = set()
        for name in HISTORICAL_REPORT_NAMES:
            path = ROOT / 'public/inspection' / name
            before = path.read_bytes()
            historical = json.loads(before)['analysis']['reference_summary']
            with self.subTest(path=path.name):
                self.assertIsNotNone(historical)
                validate_reference_summary(historical)
                self.assertEqual(json.loads(render_reference_summary(historical)), historical)
                self.assertEqual(path.read_bytes(), before)
                versions.add(historical['schema_version'])
        self.assertIn(6, versions)


if __name__ == '__main__':
    unittest.main()
