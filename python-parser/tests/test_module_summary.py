"""Module I/O publication contracts exercised with independently invented XML."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.reference_summary import (
    ReferenceSummaryError, build_reference_summary, render_reference_summary,
    validate_reference_summary,
)
from plc_workbench.references import analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.summary import SummaryError, build_summary, render_summary, validate_summary
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from plc_workbench.work_check import render_work_check_report, validate_work_check_report


ROOT = Path(__file__).resolve().parents[2]
REVISION = {'commit': 'a' * 40, 'worktree': 'clean'}


def module_inventory():
    return analyze_snapshot(snapshot_from_bytes(b'''<RSLogix5000Content>
      <Controller Name="PRIVATE_CONTROLLER"><Modules>
        <Module Name="Local" ParentModule="Local" ParentModPortId="1">
          <Ports><Port Id="1" Type="ICP" Upstream="false"/></Ports>
        </Module>
        <Module Name="PRIVATE_MODULE"><Communications>
          <ConfigTag Name="PRIVATE_MOD:C"><Data Format="L5K">[9876543.125]</Data></ConfigTag>
          <Connections><Connection Name="PRIVATE_EXPLICIT_CONNECTION">
            <InputTag Name="PRIVATE_MOD:I"/><OutputTag Name="PRIVATE_MOD:O"/>
          </Connection></Connections>
        </Communications></Module>
        <Module Name="PRIVATE_SLOT" ParentModule="Local" ParentModPortId="1">
          <Ports><Port Id="1" Address="4" Type="ICP" Upstream="true"/></Ports>
          <Communications><Connections><Connection Name="PRIVATE_DERIVED_CONNECTION">
            <InputTag/>
          </Connection></Connections></Communications>
        </Module>
        <Module Name="PRIVATE_UNAVAILABLE"><Communications><Connections>
          <Connection Name="PRIVATE_UNAVAILABLE_CONNECTION"><InputTag/></Connection>
        </Connections></Communications></Module>
      </Modules><Tags>
        <Tag Name="PRIVATE_ALIAS" TagType="Alias" AliasFor="PRIVATE_MOD:I.PRIVATE_INPUT_FIELD"/>
        <Tag Name="PRIVATE_COLON_ALIAS" TagType="Alias" AliasFor="PRIVATE_ABSENT:I.PRIVATE_FIELD"/>
        <Tag Name="PRIVATE_MISSING_ALIAS" TagType="Alias" AliasFor="PRIVATE_MISSING"/>
        <Tag Name="PRIVATE_DYNAMIC_ALIAS" TagType="Alias" AliasFor="PRIVATE_MOD:I[PRIVATE_INDEX]"/>
      </Tags><Programs><Program Name="PRIVATE_PROGRAM"><Routines>
        <Routine Name="PRIVATE_ROUTINE" Type="RLL"><RLLContent><Rung Number="0" Type="N">
          <Text>XIC(PRIVATE_ALIAS)OTE(PRIVATE_MOD:O.PRIVATE_OUTPUT_FIELD)MOV(9876543.125,PRIVATE_MOD:C.PRIVATE_CONFIG_FIELD)XIC(Local:4:I.PRIVATE_DERIVED_FIELD)XIC(PRIVATE_MISSING)XIC(PRIVATE_ABSENT:I.PRIVATE_FIELD)XIC(PRIVATE_MOD:I[PRIVATE_INDEX]);</Text>
        </Rung></RLLContent></Routine>
      </Routines></Program></Programs></Controller></RSLogix5000Content>'''))


def module_report():
    inventory = module_inventory()
    return build_reference_summary(inventory, analyze_references(inventory), revision=REVISION)


def historical(path: str):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


class ModuleSummaryTests(unittest.TestCase):
    def test_new_reports_count_module_definitions_without_exposing_evidence(self) -> None:
        inventory = module_inventory()
        report = build_reference_summary(inventory, analyze_references(inventory), revision=REVISION)
        source = report['source_summary']
        self.assertEqual((source['schema_version'], source['parser_version']), (3, 'source-inventory-2'))
        self.assertEqual((report['schema_version'], report['analyzer_version']), (4, 'source-references-3'))
        expected = {'module_ports': 2, 'module_connections': 3, 'module_input_tags': 3,
                    'module_output_tags': 1, 'module_config_tags': 1}
        self.assertEqual({key: source['counts'][key] for key in expected}, expected)
        self.assertEqual(source['counts']['total_tag_definitions'], 4)
        self.assertEqual(source['counts']['aliases'], 4)
        self.assertEqual(report['symbols']['total'], 9)
        self.assertEqual(report['module_io']['total'], 5)
        self.assertEqual(report['module_io']['named'], 4)
        self.assertEqual(report['module_io']['by_name_origin'], {
            'explicit_name': 3, 'backplane_slot': 1, 'module_name': 0, 'unavailable': 1,
        })
        self.assertEqual(report['module_io']['unavailable_by_reason']['missing_parent_module'], 1)
        self.assertEqual(sum(report['module_io']['unavailable_by_reason'].values()), 1)
        self.assertEqual(report['aliases']['by_status']['root_bound'], 1)
        self.assertEqual(report['operands']['by_status']['root_bound'], 4)
        self.assertEqual(report['operands']['by_status']['literal'], 1)
        self.assertEqual(report['status'], 'partial')
        for rendered in (render_summary(source), render_reference_summary(report)):
            for private in ('PRIVATE', '9876543.125', 'Local:4:I', inventory.snapshot['sha256'],
                            inventory.snapshot['id'], 'raw_target', 'raw_text', 'alias_chain'):
                self.assertNotIn(private, rendered)

    def test_unresolved_and_unsupported_reason_totals_reconcile_for_both_groups(self) -> None:
        report = module_report()
        for group_name in ('aliases', 'operands'):
            group = report[group_name]
            with self.subTest(group=group_name):
                self.assertEqual(group['by_reason']['unresolved']['root_not_declared'], 1)
                self.assertEqual(group['by_reason']['unresolved']['colon_root_not_declared'], 1)
                self.assertEqual(group['by_reason']['unsupported_address']['non_static_array_index'], 1)
                for status, counts in group['by_reason'].items():
                    self.assertEqual(sum(counts.values()), group['by_status'][status])
        self.assertEqual(json.loads(render_reference_summary(report)), report)

    def test_zero_module_input_has_explicit_empty_accounting(self) -> None:
        inventory = analyze_snapshot(snapshot_from_bytes(
            b'<RSLogix5000Content><Controller Name="Invented"/></RSLogix5000Content>'))
        report = build_reference_summary(inventory, analyze_references(inventory))
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['module_io']['total'], 0)
        self.assertEqual(report['module_io']['named'], 0)
        self.assertFalse(any(report['module_io']['by_name_origin'].values()))
        self.assertFalse(any(report['module_io']['unavailable_by_reason'].values()))
        for group in ('aliases', 'operands'):
            self.assertFalse(any(report[group]['by_status'].values()))
            for counts in report[group]['by_reason'].values():
                self.assertFalse(any(counts.values()))
        validate_reference_summary(report)

    def test_unavailable_module_name_prevents_false_complete_even_without_ladder(self) -> None:
        inventory = analyze_snapshot(snapshot_from_bytes(b'''<RSLogix5000Content><Controller Name="C">
          <Modules><Module Name="Unconnected"><Communications><Connections>
            <Connection Name="Process"><InputTag/></Connection>
          </Connections></Communications></Module></Modules>
          </Controller></RSLogix5000Content>'''))
        report = build_reference_summary(inventory, analyze_references(inventory))
        self.assertEqual(report['source_summary']['status'], 'complete')
        self.assertEqual(report['module_io']['by_name_origin']['unavailable'], 1)
        self.assertEqual(report['status'], 'partial')
        report['status'] = 'complete'
        with self.assertRaises(ReferenceSummaryError):
            validate_reference_summary(report)

    def test_invalid_reason_labels_counts_and_accounting_are_rejected(self) -> None:
        original = module_report()
        mutations = (
            lambda r: r['module_io'].update(PRIVATE_NAME='PRIVATE_VALUE'),
            lambda r: r['module_io']['by_name_origin'].update(PRIVATE_ORIGIN=0),
            lambda r: r['module_io']['unavailable_by_reason'].update(PRIVATE_REASON=0),
            lambda r: r['module_io'].update(total=6),
            lambda r: r['module_io'].update(named=5),
            lambda r: r['module_io']['by_name_origin'].update(explicit_name=2),
            lambda r: r['module_io']['unavailable_by_reason'].update(missing_parent_module=0),
            lambda r: r['symbols'].update(unnamed=0),
            lambda r: r['aliases']['by_reason'].update(PRIVATE_STATUS={}),
            lambda r: r['aliases']['by_reason']['unresolved'].update(PRIVATE_REASON=0),
            lambda r: r['operands']['by_reason']['unresolved'].pop('invalid_scope'),
            lambda r: r['aliases']['by_reason']['unresolved'].update(root_not_declared=0),
            lambda r: r['operands']['by_reason']['unsupported_address'].update(non_static_array_index=2),
        )
        for index, mutate in enumerate(mutations):
            report = deepcopy(original)
            mutate(report)
            with self.subTest(mutation=index), self.assertRaises(ReferenceSummaryError) as caught:
                render_reference_summary(report)
            self.assertNotIn('PRIVATE', str(caught.exception))
        for value in (True, -1, 0.5, 10**12 + 1, 'PRIVATE_COUNT'):
            report = deepcopy(original)
            report['aliases']['by_reason']['unresolved']['root_not_declared'] = value
            with self.subTest(value=value), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)

    def test_module_source_counts_reject_bad_types_and_impossible_parent_counts(self) -> None:
        original = build_summary(module_inventory())
        for value in (True, -1, 0.5, 10**12 + 1, 'PRIVATE_COUNT'):
            report = deepcopy(original)
            report['counts']['module_input_tags'] = value
            with self.subTest(value=value), self.assertRaises(SummaryError):
                validate_summary(report)
        for parent_count in ('modules', 'module_connections'):
            report = deepcopy(original)
            report['counts'][parent_count] = 0
            with self.subTest(parent=parent_count), self.assertRaises(SummaryError):
                validate_summary(report)
            nested = module_report()
            nested['source_summary']['counts'][parent_count] = 0
            with self.subTest(parent=parent_count), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(nested)

    def test_private_provenance_and_reasons_cannot_be_forged_before_aggregation(self) -> None:
        inventory = module_inventory()
        original = analyze_references(inventory)
        explicit = next(index for index, symbol in enumerate(original.symbols)
                        if symbol['kind'] == 'module_input_tag' and symbol['name'] == 'PRIVATE_MOD:I')
        unresolved = next(index for index, alias in enumerate(original.aliases)
                          if alias['reason'] == 'colon_root_not_declared')
        unsupported = next(index for index, operand in enumerate(original.operands)
                           if operand['reason'] == 'non_static_array_index')
        for group, index, field, value in (
            ('symbols', explicit, 'name', 'PRIVATE_OTHER:I'),
            ('symbols', explicit, 'name_origin', 'backplane_slot'),
            ('symbols', explicit, 'name_reason', 'missing_parent_module'),
            ('aliases', unresolved, 'reason', 'root_not_declared'),
            ('operands', unsupported, 'reason', 'malformed_address'),
        ):
            references = deepcopy(original)
            getattr(references, group)[index][field] = value
            with self.subTest(group=group, field=field), self.assertRaises(ReferenceSummaryError) as caught:
                build_reference_summary(inventory, references)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_historical_source_reference_and_work_check_reports_remain_valid(self) -> None:
        cases = (
            ('public/inspection/summary-002.json', validate_summary, render_summary),
            ('public/inspection/reference-summary-20261013T203510Z.json',
             validate_reference_summary, render_reference_summary),
            ('public/examples/reference-summary.synthetic.json',
             validate_reference_summary, render_reference_summary),
            ('public/inspection/work-check-20261013T221312Z-4c286cdf.json',
             validate_work_check_report, render_work_check_report),
            ('public/inspection/work-check-20261013T221358Z-0ad977a3.json',
             validate_work_check_report, render_work_check_report),
        )
        for relative, validate, render in cases:
            with self.subTest(report=relative):
                path = ROOT / relative
                before = path.read_bytes()
                report = json.loads(before)
                validate(report)
                self.assertEqual(json.loads(render(report)), report)
                self.assertEqual(path.read_bytes(), before)

    def test_mixed_historical_and_current_contracts_are_rejected(self) -> None:
        new = module_report()
        old = historical('public/examples/reference-summary.synthetic.json')
        for outer, nested in ((new, old['source_summary']), (old, new['source_summary'])):
            report = deepcopy(outer)
            report['source_summary'] = deepcopy(nested)
            with self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)
        for base, replacements in (
            (new, {'analyzer_version': 'source-references-1'}),
            (old, {'analyzer_version': 'source-references-2'}),
            (old, {'module_io': new['module_io']}),
        ):
            report = deepcopy(base)
            report.update(replacements)
            with self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)
        for base, replacement in ((new['source_summary'], 'source-inventory-1'),
                                  (old['source_summary'], 'source-inventory-2')):
            source = deepcopy(base)
            source['parser_version'] = replacement
            with self.assertRaises(SummaryError):
                validate_summary(source)
        legacy_source = deepcopy(old['source_summary'])
        legacy_source['counts']['module_input_tags'] = 0
        with self.assertRaises(SummaryError):
            validate_summary(legacy_source)

    def test_existing_work_check_contract_accepts_new_nested_summary(self) -> None:
        report = historical('public/inspection/work-check-20261013T221312Z-4c286cdf.json')
        report['tool_revision'] = deepcopy(REVISION)
        report['analysis']['reference_summary'] = module_report()
        report['analysis']['status'] = 'partial'
        report['status'] = 'partial'
        validate_work_check_report(report)
        self.assertEqual(json.loads(render_work_check_report(report)), report)
        self.assertEqual(report['schema_version'], 1)

    def test_publisher_independently_validates_current_source_and_reference_reports(self) -> None:
        reference = module_report()
        for original in (reference['source_summary'], reference):
            with self.subTest(kind=original['report_kind']), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                output = root / 'public/inspection/module-summary.json'
                with patch('plc_workbench.summary_output._checkout_root', return_value=root):
                    publish_summary(output, json.dumps(original), input_path=root / 'confidential/invented.L5X')
                    self.assertEqual(json.loads(output.read_text(encoding='utf-8')), original)
                    report = deepcopy(original)
                    report['source_path'] = 'PRIVATE_SOURCE.L5X'
                    rejected = root / 'public/inspection/rejected.json'
                    with self.assertRaises(SummaryOutputError) as caught:
                        publish_summary(rejected, json.dumps(report), input_path=root / 'confidential/invented.L5X')
                self.assertNotIn('PRIVATE', str(caught.exception))
                self.assertFalse(rejected.exists())
                self.assertEqual(list(output.parent.iterdir()), [output])


if __name__ == '__main__':
    unittest.main()
