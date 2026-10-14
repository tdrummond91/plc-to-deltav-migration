"""Closed address-shape observations from independently invented source inputs."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from xml.sax.saxutils import quoteattr

from plc_workbench.reference_summary import (
    ReferenceSummaryError, build_reference_summary, render_reference_summary,
    validate_reference_summary,
)
from plc_workbench.references import analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from plc_workbench.work_check import render_work_check_report, validate_work_check_report


REVISION = {'commit': 'a' * 40, 'worktree': 'clean'}
ZERO_SHAPES = {
    'alias_target_failure': 0, 'leading_hash_static_address': 0,
    'leading_hash_other': 0, 'contains_brackets': 0, 'contains_colon': 0,
    'contains_dot': 0, 'other_form': 0,
}


def inventory(rungs: list[str], *, aliases: tuple[tuple[str, str], ...] = (),
              secret: str = 'PRIVATE_SHAPE', value: str = '84739.125'):
    tags = '<Tag Name="A" TagType="Base"/><Tag Name="Local:2:I" TagType="Base"/>'
    tags += ''.join(
        f'<Tag Name={quoteattr(name)} TagType="Alias" AliasFor={quoteattr(target)}/>'
        for name, target in aliases
    )
    tags += (f'<Tag Name="{secret}_DATA" TagType="Base" DataType="REAL">'
             f'<Data Format="L5K"><![CDATA[{value}]]></Data></Tag>')
    rung_xml = ''.join(
        f'<Rung Number="{number + 600}" Type="N"><Comment>{secret}_COMMENT</Comment>'
        f'<Text><![CDATA[{text}]]></Text></Rung>' for number, text in enumerate(rungs)
    )
    xml = (
        f'<RSLogix5000Content Owner="{secret}_OWNER"><Controller Name="{secret}_CONTROLLER">'
        f'<Tags>{tags}</Tags><Programs><Program Name="{secret}_PROGRAM"><Routines>'
        f'<Routine Name="{secret}_ROUTINE" Type="RLL"><RLLContent>{rung_xml}</RLLContent>'
        '</Routine></Routines></Program></Programs></Controller></RSLogix5000Content>'
    ).encode()
    return analyze_snapshot(snapshot_from_bytes(xml))


def summary(source):
    return build_reference_summary(source, analyze_references(source), revision=REVISION)


def earlier_summary(current: dict, version: int) -> dict:
    """Represent this no-module invented input using the previous public contracts."""
    if version not in (1, 2, 3, 4, 5, 6, 7, 8):
        raise ValueError('Expected a historical reference version.')
    report = deepcopy(current)
    del report['routine_instruction_shapes']
    report.update(schema_version=version, exporter_version=f'reference-summary-{version}')
    report['analyzer_version'] = {
        1: 'source-references-1', 2: 'source-references-2',
        3: 'source-references-2', 4: 'source-references-3', 5: 'source-references-4',
        6: 'source-references-5', 7: 'source-references-6', 8: 'source-references-7',
    }[version]
    if version < 6 and report['operands']['by_status'].pop('system_flag') != 0:
        raise ValueError('Historical fixture cannot downgrade recognized system flags.')
    if version >= 5:
        return report
    del report['rack_candidates']
    source = report['source_summary']
    source.update(schema_version=3, exporter_version='aggregate-summary-3',
                  parser_version='source-inventory-2')
    for key in ('module_rack_connections', 'module_rack_input_aliases', 'module_rack_output_aliases'):
        del source['counts'][key]
    if version in (1, 2):
        del report['operands']['malformed_address_shapes']
    if version == 1:
        report['analyzer_version'] = 'source-references-1'
        del report['module_io']
        for group in ('aliases', 'operands'):
            del report[group]['by_reason']
        for kind in ('module_input_tag', 'module_output_tag', 'module_config_tag'):
            del report['symbols']['by_kind'][kind]
        source.update(schema_version=2, exporter_version='aggregate-summary-2',
                      parser_version='source-inventory-1')
        for key in ('module_ports', 'module_connections', 'module_input_tags',
                    'module_output_tags', 'module_config_tags'):
            del source['counts'][key]
    return report


def work_report(reference: dict) -> dict:
    suite = {
        'schema_version': 1, 'status': 'passed',
        'counts': {'tests_run': 1, 'failures': 0, 'errors': 0, 'skipped': 0,
                   'expected_failures': 0, 'unexpected_successes': 0},
        'failed_test_ids': [], 'failure_ids_omitted': 0,
    }
    return {
        'schema_version': 1, 'report_kind': 'l5x_work_machine_check',
        'workflow_version': 'work-check-1', 'run_id': '20261013T120000Z-1234abcd',
        'tool_revision': deepcopy(REVISION),
        'tests': {'application': deepcopy(suite), 'helpers': deepcopy(suite)},
        'analysis': {'status': reference['status'], 'failure_code': None,
                     'private_run_saved': True, 'reference_summary': reference},
        'status': 'passed' if reference['status'] == 'complete' else 'partial',
    }


class AddressShapeSummaryTests(unittest.TestCase):
    def test_exact_occurrence_counts_and_punctuation_precedence(self) -> None:
        source = inventory([
            'XIC(#A);', 'XIC(  #Local:2:I.Field[3].0  );', 'XIC(#Missing);',
            'XIC(##A);', 'XIC(#A[-1]);', 'XIC(#A..Field);', 'XIC(#A[Index]);',
            'XIC(A[-1]);', 'XIC(Local:2:I..Field[-1]);',
            'XIC(A::I..Field);', 'XIC(A..Field);', 'XIC(A + A);', 'XIC(A + A);',
        ])
        report = summary(source)
        self.assertEqual(report['coverage']['rungs_analyzed'], 13)
        self.assertEqual(report['operands']['malformed_address_shapes'], {
            'alias_target_failure': 0, 'leading_hash_static_address': 3,
            'leading_hash_other': 4, 'contains_brackets': 2, 'contains_colon': 1,
            'contains_dot': 1, 'other_form': 2,
        })
        self.assertEqual(report['operands']['by_reason']['unsupported_address']['malformed_address'], 13)
        self.assertEqual(report['operands']['by_status']['unsupported_address'], 13)

    def test_alias_target_failure_never_classifies_caller_spelling(self) -> None:
        source = inventory([
            'XIC(First);', 'XIC(First.Field);', 'XIC(First[2]);', 'XIC(Alias:4:I.Field);',
        ], aliases=(('First', 'Second'), ('Second', '#A'),
                    ('Alias:4:I', 'Second'), ('Unused', 'A..Field')))
        references = analyze_references(source)
        self.assertEqual([len(row['alias_chain']) for row in references.operands], [2, 2, 2, 2])
        report = build_reference_summary(source, references)
        self.assertEqual(report['operands']['malformed_address_shapes'],
                         ZERO_SHAPES | {'alias_target_failure': 4})
        self.assertEqual(report['aliases']['by_reason']['unsupported_address']['malformed_address'], 4)
        self.assertEqual(report['operands']['total'], 4)

    def test_only_final_malformed_address_operands_enter_histogram(self) -> None:
        source = inventory([
            'XIC(A[Index]);', 'XIC(Program:Demo.A);', r'XIC(\Demo.A);',
            "MOV('#PRIVATE_LITERAL..[1]',A);", 'MOV(84739.125,A);',
            'PRIVATE_UNKNOWN(#A);', 'CPT(A,#A + 1);', 'MOV( ,A);',
            'JMP(#PRIVATE_LABEL);', 'XIC(Missing);', 'XIC(#A,A);',
            'XIC(Dynamic);', 'XIC(EmptyTarget);', 'XIC(A);', f"XIC(#{'A' * 65_536});",
        ], aliases=(('Dynamic', 'A[Index]'), ('EmptyTarget', ''), ('UnusedMalformed', '#A')))
        references = analyze_references(source)
        report = build_reference_summary(source, references)
        self.assertEqual(report['coverage']['rungs_analyzed'], 15)
        self.assertEqual(report['operands']['malformed_address_shapes'], ZERO_SHAPES)
        self.assertEqual(report['operands']['by_status']['unsupported_address'], 6)
        self.assertEqual(report['operands']['by_reason']['unsupported_address']['address_length_limit'], 1)
        for state in ('unsupported_instruction', 'unsupported_expression', 'empty',
                      'non_data', 'unresolved', 'argument_count_mismatch', 'literal', 'root_bound'):
            self.assertGreater(report['operands']['by_status'][state], 0)
        self.assertEqual(report['aliases']['by_reason']['unsupported_address']['malformed_address'], 1)

    def test_single_hash_recognition_does_not_bind_or_mutate_private_evidence(self) -> None:
        source = inventory(['XIC(#A);', 'XIC(#Local:2:I.Field[3]);', 'XIC(#Missing);'])
        references = analyze_references(source)
        source_before, references_before = source.to_dict(), references.to_dict()
        report = build_reference_summary(source, references)
        self.assertEqual(report['operands']['malformed_address_shapes'],
                         ZERO_SHAPES | {'leading_hash_static_address': 3})
        for row in references.operands:
            self.assertEqual((row['status'], row['reason']), ('unsupported_address', 'malformed_address'))
            self.assertIsNone(row['symbol_id'])
            self.assertIsNone(row['target_id'])
        self.assertEqual(report['status'], 'partial')
        self.assertEqual((references.schema_version, references.analyzer_version), (4, 'source-references-7'))
        self.assertEqual(source.to_dict(), source_before)
        self.assertEqual(references.to_dict(), references_before)

    def test_empty_inventory_keeps_all_shape_buckets_zero_filled(self) -> None:
        source = analyze_snapshot(snapshot_from_bytes(
            b'<RSLogix5000Content><Controller Name="Invented"/></RSLogix5000Content>'))
        report = summary(source)
        self.assertEqual(report['operands']['malformed_address_shapes'], ZERO_SHAPES)
        self.assertEqual(report['operands']['total'], 0)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual((report['schema_version'], report['exporter_version'], report['analyzer_version']),
                         (9, 'reference-summary-9', 'source-references-7'))
        self.assertEqual(report['source_summary']['schema_version'], 4)

    def test_renaming_values_and_rung_order_do_not_reveal_private_details(self) -> None:
        reports = []
        for secret, value, reverse in (('PRIVATE_SHAPE', '84739.125', False),
                                       ('DIFFERENT_PRIVATE', '392.75', True)):
            rungs = [f'XIC(#{secret}_DATA);', f'XIC({secret}_DATA[-1]);',
                     f'XIC({secret}_DATA::I..Field);', f'XIC({secret}_DATA..Field);',
                     f'XIC({secret}_DATA + 1);', f'MOV({value},{secret}_DATA);',
                     f'XIC({secret}_ALIAS[2]);']
            source = inventory(list(reversed(rungs)) if reverse else rungs,
                               aliases=((f'{secret}_ALIAS', f'#{secret}_DATA'),),
                               secret=secret, value=value)
            rendered = render_reference_summary(summary(source))
            for private in (secret, value, source.snapshot['id'], source.snapshot['sha256'],
                            'raw_text', 'scope_id', 'alias_chain', 'target_id', 'source_path'):
                self.assertNotIn(private, rendered)
            reports.append(rendered)
        self.assertEqual(reports[0], reports[1])

    def test_unknown_missing_or_nested_shape_labels_are_rejected(self) -> None:
        original = summary(inventory(['XIC(#A);']))
        for mutate in (
            lambda r: r['operands']['malformed_address_shapes'].update(PRIVATE_ADDRESS=0),
            lambda r: r['operands']['malformed_address_shapes'].pop('other_form'),
            lambda r: r['operands'].pop('malformed_address_shapes'),
            lambda r: r['operands'].update(malformed_address_shapes=['PRIVATE_ADDRESS']),
            lambda r: r['operands']['malformed_address_shapes'].update(other_form={'PRIVATE_ADDRESS': 1}),
            lambda r: r['aliases'].update(malformed_address_shapes=deepcopy(ZERO_SHAPES)),
        ):
            report = deepcopy(original)
            mutate(report)
            with self.assertRaises(ReferenceSummaryError) as caught:
                render_reference_summary(report)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_shape_counts_require_bounded_integers_and_exact_malformed_total(self) -> None:
        original = summary(inventory(['XIC(#A);', 'XIC(A[Index]);']))
        for value in (True, False, -1, 0.5, float('nan'), 10**12 + 1, 'PRIVATE_COUNT', None, 0, 2):
            report = deepcopy(original)
            report['operands']['malformed_address_shapes']['leading_hash_static_address'] = value
            with self.subTest(value=value), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)
        self.assertEqual(sum(original['operands']['malformed_address_shapes'].values()), 1)
        self.assertEqual(original['operands']['by_status']['unsupported_address'], 2)

    def test_alias_failure_bucket_requires_an_actual_malformed_alias_count(self) -> None:
        report = summary(inventory(['XIC(#A);']))
        report['operands']['malformed_address_shapes'].update(
            leading_hash_static_address=0, alias_target_failure=1)
        with self.assertRaises(ReferenceSummaryError):
            validate_reference_summary(report)

    def test_private_shape_inputs_cannot_be_forged_before_aggregation(self) -> None:
        source = inventory(['XIC(#A);', 'XIC(A[Index]);', 'XIC(First.Field);'],
                           aliases=(('First', 'Second'), ('Second', '#A')))
        original = analyze_references(source)
        for group, index, field, value in (
            ('operands', 0, 'raw_text', '#PRIVATE_REPLACED'),
            ('operands', 0, 'alias_chain', ['PRIVATE_FORGED_ID']),
            ('operands', 1, 'reason', 'malformed_address'),
            ('operands', 2, 'alias_chain', []),
            ('aliases', 1, 'raw_target', 'PRIVATE_TARGET..Field'),
        ):
            references = deepcopy(original)
            getattr(references, group)[index][field] = value
            with self.subTest(group=group, field=field), self.assertRaises(ReferenceSummaryError) as caught:
                build_reference_summary(source, references)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_legacy_versions_validate_without_inventing_shape_evidence(self) -> None:
        current = summary(inventory(['XIC(#A);']))
        for version in (1, 2, 3, 4, 5, 6, 7, 8):
            report = earlier_summary(current, version)
            with self.subTest(version=version):
                validate_reference_summary(report)
                self.assertEqual(json.loads(render_reference_summary(report)), report)
                self.assertEqual('malformed_address_shapes' in report['operands'], version >= 3)
                self.assertEqual('rack_candidates' in report, version >= 5)
                self.assertEqual('system_flag' in report['operands']['by_status'], version >= 6)
                self.assertNotIn('routine_instruction_shapes', report)
                validate_work_check_report(work_report(report))

    def test_all_frozen_contracts_reject_even_zero_routine_shape_evidence(self) -> None:
        current = summary(inventory(['XIC(A);']))
        for version in range(1, 9):
            report = earlier_summary(current, version)
            report['routine_instruction_shapes'] = deepcopy(current['routine_instruction_shapes'])
            with self.subTest(version=version), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)

    def test_version_hybrids_and_shape_fields_on_legacy_reports_are_rejected(self) -> None:
        current = summary(inventory(['XIC(#A);']))
        for version in (1, 2):
            report = earlier_summary(current, version)
            report['operands']['malformed_address_shapes'] = deepcopy(current['operands']['malformed_address_shapes'])
            with self.subTest(version=version), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)
        for replacement in ({'schema_version': 2}, {'exporter_version': 'reference-summary-2'},
                            {'analyzer_version': 'source-references-2'}, {'schema_version': True},
                            {'source_summary': earlier_summary(current, 1)['source_summary']}):
            report = deepcopy(current)
            report.update(replacement)
            with self.subTest(replacement=replacement), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)

    def test_current_work_check_envelope_validates_nested_shape_contract(self) -> None:
        report = work_report(summary(inventory(['XIC(#A);'])))
        validate_work_check_report(report)
        self.assertEqual(json.loads(render_work_check_report(report)), report)
        self.assertEqual((report['schema_version'], report['workflow_version']), (1, 'work-check-1'))
        report['analysis']['reference_summary']['operands']['malformed_address_shapes']['PRIVATE_ADDRESS'] = 1
        with self.assertRaises(ValueError) as caught:
            render_work_check_report(report)
        self.assertNotIn('PRIVATE', str(caught.exception))

    def test_publisher_validates_shape_contract_and_never_clobbers_output(self) -> None:
        reference = summary(inventory(['XIC(#A);']))
        for original in (reference, work_report(reference)):
            with self.subTest(kind=original['report_kind']), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output = root / 'summary.json'
                publish_summary(output, json.dumps(original), input_path=root / 'invented.L5X')
                before = output.read_bytes()
                self.assertEqual(json.loads(before), original)
                with self.assertRaises(SummaryOutputError):
                    publish_summary(output, json.dumps(original), input_path=root / 'invented.L5X')
                self.assertEqual(output.read_bytes(), before)
                rejected = deepcopy(original)
                nested = (rejected if rejected['report_kind'] == 'l5x_reference_review_summary'
                          else rejected['analysis']['reference_summary'])
                nested['operands']['malformed_address_shapes']['PRIVATE_ADDRESS'] = 1
                destination = root / 'new-directory' / 'rejected.json'
                with self.assertRaises(SummaryOutputError) as caught:
                    publish_summary(destination, json.dumps(rejected), input_path=root / 'invented.L5X')
                self.assertNotIn('PRIVATE', str(caught.exception))
                self.assertFalse(destination.parent.exists())
                self.assertEqual(list(root.iterdir()), [output])


if __name__ == '__main__':
    unittest.main()
