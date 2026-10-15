"""Count-only system-flag publication tests using invented in-memory source."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from plc_workbench.reference_summary import (
    LEGACY_CONSTANTS, V2_CONSTANTS, V3_CONSTANTS, V4_CONSTANTS, V5_CONSTANTS, V6_CONSTANTS, V7_CONSTANTS, V8_CONSTANTS, V9_CONSTANTS,
    ReferenceSummaryError, build_reference_summary, render_reference_summary,
    validate_reference_summary,
)
from plc_workbench.references import analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.summary import LEGACY_CONSTANTS as SOURCE_V2_CONSTANTS
from plc_workbench.summary import MODULE_COUNT_KEYS, RACK_COUNT_KEYS, V3_CONSTANTS as SOURCE_V3_CONSTANTS


ROOT = Path(__file__).resolve().parents[2]


def inventory(text: str, *, tags: str = ''):
    return analyze_snapshot(snapshot_from_bytes((
        '<RSLogix5000Content Owner="PRIVATE_OWNER"><Controller Name="PRIVATE_CONTROLLER">'
        f'<Tags>{tags}</Tags><Programs><Program Name="PRIVATE_PROGRAM"><Routines>'
        '<Routine Name="PRIVATE_ROUTINE" Type="RLL"><RLLContent>'
        '<Rung Number="742" Type="N"><Comment>PRIVATE_COMMENT</Comment>'
        f'<Text><![CDATA[{text}]]></Text></Rung></RLLContent></Routine></Routines>'
        '</Program></Programs></Controller></RSLogix5000Content>').encode('utf-8')))


def summary(source):
    return build_reference_summary(source, analyze_references(source))


def historical_report(current: dict, version: int) -> dict:
    """Represent a no-module fixture in each frozen contract's vocabulary."""
    result = deepcopy(current)
    del result['routine_targets']
    del result['routine_target_metadata']
    del result['routine_graph']
    if version < 9:
        del result['routine_instruction_shapes']
    result.update({1: LEGACY_CONSTANTS, 2: V2_CONSTANTS, 3: V3_CONSTANTS,
                   4: V4_CONSTANTS, 5: V5_CONSTANTS, 6: V6_CONSTANTS, 7: V7_CONSTANTS, 8: V8_CONSTANTS,
                   9: V9_CONSTANTS}[version])
    if version < 6:
        if result['operands']['by_status'].pop('system_flag') != 0:
            raise ValueError('Historical fixture cannot downgrade recognized system flags.')
    if version < 5:
        del result['rack_candidates']
        result['source_summary'].update(SOURCE_V3_CONSTANTS)
        for key in RACK_COUNT_KEYS:
            del result['source_summary']['counts'][key]
    if version < 3:
        del result['operands']['malformed_address_shapes']
    if version == 1:
        del result['module_io']
        for group in ('aliases', 'operands'):
            del result[group]['by_reason']
        for kind in ('module_input_tag', 'module_output_tag', 'module_config_tag'):
            del result['symbols']['by_kind'][kind]
        result['source_summary'].update(SOURCE_V2_CONSTANTS)
        for key in MODULE_COUNT_KEYS:
            del result['source_summary']['counts'][key]
    return result


class SystemFlagSummaryTests(unittest.TestCase):
    def test_only_system_flags_are_complete_without_declared_symbols_or_source_data(self) -> None:
        source = inventory('XIC(S:FS)XIO( s:fS )XIC(S:FS);')
        report = summary(source)
        self.assertEqual((report['schema_version'], report['exporter_version'], report['analyzer_version']),
                         (12, 'reference-summary-12', 'source-references-9'))
        self.assertEqual((source.schema_version, report['source_summary']['schema_version']), (3, 4))
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['operands']['total'], 3)
        self.assertEqual(report['operands']['by_status']['system_flag'], 3)
        self.assertEqual(sum(report['operands']['by_status'].values()), 3)
        self.assertFalse(any(count for status, count in report['operands']['by_status'].items()
                             if status != 'system_flag'))
        self.assertEqual(report['symbols']['total'], 0)
        self.assertFalse(any(report['symbols']['by_kind'].values()))
        self.assertEqual(report['aliases']['total'], 0)
        self.assertEqual(report['source_summary']['counts']['total_tag_definitions'], 0)
        self.assertEqual(report['coverage']['instructions_catalogued'], 3)
        self.assertFalse(any(report['operands']['malformed_address_shapes'].values()))
        self.assertFalse(any(count for group in report['operands']['by_reason'].values() for count in group.values()))
        rendered = render_reference_summary(report)
        self.assertEqual(json.loads(rendered), report)
        for forbidden in ('PRIVATE', 'S:FS', 's:fS', 'raw_text', 'target_id', 'alias_chain',
                          source.snapshot['sha256'], source.snapshot['id']):
            self.assertNotIn(forbidden, rendered)

    def test_system_flag_count_does_not_change_literal_binding_or_symbol_totals(self) -> None:
        source = inventory('XIC(S:FS)XIC(PRIVATE_TAG)MOV(93578.125,PRIVATE_TAG);',
                           tags='<Tag Name="PRIVATE_TAG" TagType="Base"/>')
        report = summary(source)
        self.assertEqual(report['operands']['by_status']['system_flag'], 1)
        self.assertEqual(report['operands']['by_status']['root_bound'], 2)
        self.assertEqual(report['operands']['by_status']['literal'], 1)
        self.assertEqual(report['operands']['total'], 4)
        self.assertEqual(report['symbols']['total'], 1)
        self.assertEqual(report['source_summary']['counts']['total_tag_definitions'], 1)
        self.assertEqual(report['status'], 'complete')
        self.assertNotIn('93578.125', render_reference_summary(report))

    def test_mixed_case_opcodes_roundtrip_without_changing_source_histogram(self) -> None:
        source = inventory('xic(s:fs)XiO(S:Fs)XIC(S:FS);')
        self.assertEqual(source.instruction_counts, {'xic': 1, 'XiO': 1, 'XIC': 1})
        report = summary(source)
        self.assertEqual(report['source_summary']['schema_version'], 4)
        self.assertEqual(report['source_summary']['instructions']['counts'], {'XIC': 1, 'withheld': 2})
        self.assertEqual(report['operands']['by_status']['system_flag'], 3)
        self.assertEqual(report['coverage']['instructions_catalogued'], 3)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(json.loads(render_reference_summary(report)), report)

    def test_alias_targets_remain_unresolved_and_keep_summary_partial(self) -> None:
        source = inventory('XIC(S:FS)XIO(PRIVATE_ALIAS);',
                           tags='<Tag Name="PRIVATE_ALIAS" TagType="Alias" AliasFor="S:FS"/>')
        report = summary(source)
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['operands']['by_status']['system_flag'], 1)
        self.assertEqual(report['operands']['by_status']['unresolved'], 1)
        self.assertEqual(report['aliases']['by_status']['unresolved'], 1)
        self.assertEqual(report['operands']['by_reason']['unresolved']['colon_root_not_declared'], 1)
        self.assertEqual(report['aliases']['by_reason']['unresolved']['colon_root_not_declared'], 1)
        self.assertNotIn('system_flag', report['aliases']['by_status'])
        report['status'] = 'complete'
        with self.assertRaises(ReferenceSummaryError):
            validate_reference_summary(report)

    def test_system_flag_counts_require_contacts_and_catalogued_instructions(self) -> None:
        no_contacts = summary(inventory('MOV(1,PRIVATE_TAG);', tags='<Tag Name="PRIVATE_TAG"/>'))
        no_contacts['operands']['by_status'].update(literal=0, system_flag=1)
        with self.assertRaises(ReferenceSummaryError):
            validate_reference_summary(no_contacts)
        too_many_for_named_and_withheld = summary(inventory('xic(S:FS)MOV(1,PRIVATE_TAG);',
                                                            tags='<Tag Name="PRIVATE_TAG"/>'))
        self.assertEqual(too_many_for_named_and_withheld['source_summary']['instructions']['counts'],
                         {'MOV': 1, 'withheld': 1})
        too_many_for_named_and_withheld['operands']['by_status'].update(literal=0, system_flag=2)
        with self.assertRaises(ReferenceSummaryError):
            validate_reference_summary(too_many_for_named_and_withheld)
        too_few_catalogued = summary(inventory('XIC(S:FS)XIO(S:FS);'))
        too_few_catalogued['coverage']['instructions_catalogued'] = 1
        too_few_catalogued['status'] = 'partial'
        with self.assertRaises(ReferenceSummaryError):
            validate_reference_summary(too_few_catalogued)

    def test_count_types_and_status_vocabulary_are_closed(self) -> None:
        original = summary(inventory('XIC(S:FS);'))
        for value in (True, False, -1, 0.5, 10**12 + 1, 'PRIVATE_COUNT'):
            report = deepcopy(original)
            report['operands']['by_status']['system_flag'] = value
            with self.subTest(value=value), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)
        for mutate in (
            lambda report: report['operands']['by_status'].pop('system_flag'),
            lambda report: report['operands']['by_status'].update(PRIVATE_STATUS=0),
            lambda report: report['aliases']['by_status'].update(system_flag=0),
            lambda report: report.update(analyzer_version='source-references-4'),
            lambda report: report.update(schema_version=True),
        ):
            report = deepcopy(original)
            mutate(report)
            with self.assertRaises(ReferenceSummaryError) as caught:
                render_reference_summary(report)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_previous_contracts_reject_even_zero_system_flag_counts(self) -> None:
        current = summary(inventory('XIC(PRIVATE_TAG);', tags='<Tag Name="PRIVATE_TAG"/>'))
        self.assertEqual(current['operands']['by_status']['system_flag'], 0)
        for version in range(1, 6):
            with self.subTest(version=version):
                historical = historical_report(current, version)
                validate_reference_summary(historical)
                self.assertEqual(json.loads(render_reference_summary(historical)), historical)
                for count in (0, 1):
                    hybrid = deepcopy(historical)
                    hybrid['operands']['by_status'].update(system_flag=count, root_bound=1 - count)
                    with self.subTest(count=count), self.assertRaises(ReferenceSummaryError):
                        validate_reference_summary(hybrid)
                hybrid = deepcopy(historical)
                hybrid.update(analyzer_version='source-references-5')
                with self.assertRaises(ReferenceSummaryError):
                    validate_reference_summary(hybrid)

    def test_frozen_v6_through_v8_keep_system_flags_and_exact_metadata(self) -> None:
        current = summary(inventory('XIC(S:FS);'))
        for version, constants in ((6, V6_CONSTANTS), (7, V7_CONSTANTS), (8, V8_CONSTANTS)):
            historical = historical_report(current, version)
            with self.subTest(version=version):
                self.assertEqual({key: historical[key] for key in constants}, constants)
                self.assertEqual(set(historical), set(current) - {'routine_instruction_shapes', 'routine_targets', 'routine_target_metadata', 'routine_graph'})
                self.assertEqual(historical['operands']['by_status'], current['operands']['by_status'])
                self.assertEqual(historical['operands']['by_status']['system_flag'], 1)
                self.assertEqual(json.loads(render_reference_summary(historical)), historical)
            for key in ('schema_version', 'exporter_version', 'analyzer_version'):
                if historical[key] == current[key]:
                    continue
                hybrid = deepcopy(historical)
                hybrid[key] = current[key]
                with self.subTest(version=version, key=key), self.assertRaises(ReferenceSummaryError):
                    validate_reference_summary(hybrid)

    def test_publisher_rejects_forged_private_system_flag_records(self) -> None:
        source = inventory('XIC(PRIVATE_TAG);', tags='<Tag Name="PRIVATE_TAG"/>')
        references = analyze_references(source)
        forged = deepcopy(references.operands)
        forged[0].update(status='system_flag', symbol_id=None, target_id=None,
                         suffix='', alias_chain=[], reason=None)
        with self.assertRaises(ReferenceSummaryError):
            build_reference_summary(source, replace(references, operands=forged))
        actual = inventory('XIC(S:FS);')
        references = analyze_references(actual)
        for key, value in (('symbol_id', 'PRIVATE_SYMBOL'), ('reason', 'PRIVATE_REASON')):
            forged = deepcopy(references.operands)
            forged[0][key] = value
            with self.subTest(key=key), self.assertRaises(ReferenceSummaryError):
                build_reference_summary(actual, replace(references, operands=forged))

    def test_committed_historical_work_report_reference_summaries_still_validate(self) -> None:
        validated = 0
        for path in sorted((ROOT / 'public/inspection').glob('work-check-*.json')):
            historical = json.loads(path.read_text(encoding='utf-8'))['analysis']['reference_summary']
            if historical is None or historical['schema_version'] >= 6:
                continue
            with self.subTest(path=path.name):
                before = deepcopy(historical)
                validate_reference_summary(historical)
                self.assertEqual(json.loads(render_reference_summary(historical)), before)
                self.assertNotIn('system_flag', historical['operands']['by_status'])
                validated += 1
        self.assertGreaterEqual(validated, 9)


if __name__ == '__main__':
    unittest.main()
