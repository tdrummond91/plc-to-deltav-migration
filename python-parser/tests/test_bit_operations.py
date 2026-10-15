"""Bounded MVM/SWPB roles from invented inputs and unchanged public history."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from plc_workbench import work_check
from plc_workbench.diagnostic_sample import (
    DiagnosticSampleError, build_diagnostic_sample, validate_diagnostic_sample,
)
from plc_workbench.reference_reporting import render_reference_json, render_reference_text
from plc_workbench.reference_summary import (
    ReferenceSummaryError, build_reference_summary, render_reference_summary,
    validate_reference_summary,
)
from plc_workbench.references import (
    ReferenceError, _swpb_order_mode, analyze_references, validate_references,
)
from plc_workbench.summary import build_summary
from test_diagnostic_sample import colon_sample, sample
from test_references import inventory, named, program, tag
from test_unmatched_sample_report import REVISION, SOURCE, report


ROOT = Path(__file__).resolve().parents[2]
PREVIOUS_REPORT = ROOT / 'public/inspection/work-check-20261014T195120Z-0b07d834.json'


def report_source(text: str) -> bytes:
    return SOURCE.replace(b'XIC(MysteryRack:7:I.Data[2].3)OTE(A);', text.encode('ascii'))


class BitOperationTests(unittest.TestCase):
    def test_mvm_binds_all_data_slots_with_literals_aliases_and_suffixes(self) -> None:
        source = inventory(tag('Base') + tag('Mask') + tag('Destination')
                           + tag('Alias', 'Base.Member[2]'),
                           program('MVM(Alias.7,Mask[9],Destination.Member)'
                                   'MVM(Base,16#FF,Destination)MVM(1,2#10,42);'))
        result = analyze_references(source)
        self.assertEqual([row['status'] for row in result.operands],
                         ['root_bound'] * 4 + ['literal', 'root_bound'] + ['literal'] * 3)
        alias, mask, destination = result.operands[:3]
        self.assertEqual((alias['symbol_id'], alias['target_id']),
                         (named(result, 'Alias')['id'], named(result, 'Base')['id']))
        self.assertEqual((alias['suffix'], alias['alias_chain']),
                         ('.Member[2].7', [named(result, 'Alias')['id']]))
        self.assertEqual((mask['target_id'], mask['suffix']), (named(result, 'Mask')['id'], '[9]'))
        self.assertEqual(destination['suffix'], '.Member')
        self.assertEqual(result.coverage['instructions_catalogued'], 3)
        self.assertEqual(result.status, 'complete')
        # Lexical literals, including a destination literal, do not establish
        # legal execution, mask width, data type or destination access.
        self.assertEqual((result.schema_version, result.analyzer_version), (6, 'source-references-9'))
        for field in ('member_validation', 'semantic_analysis', 'effect_analysis'):
            self.assertEqual(getattr(result, field), 'not_implemented')
        validate_references(source, result)

    def test_swpb_selector_is_non_data_for_every_nonempty_spelling(self) -> None:
        modes = ('Selector', 'Alias.7', '0', '16#FF', 'Unknown:7:I.Data', 'Mode?',
                 'Mode + 1', 'Array[Index]', 'UNKNOWN_MODE', "'text'")
        text = ''.join(f'SWPB(Source[2],{mode},Destination.7)' for mode in modes) + ';'
        source = inventory(tag('Source') + tag('Destination') + tag('Selector')
                           + tag('Alias', 'Source.Member'), program(text))
        rung = source.rungs[0]
        first = replace(rung.instructions[0], arguments=(' Source[2] ', ' Selector ', ' Destination.7 '))
        source = replace(source, rungs=[replace(rung, instructions=[first, *rung.instructions[1:]])])
        before = deepcopy(source.to_dict())
        result = analyze_references(source)
        self.assertEqual([row['status'] for row in result.operands],
                         ['root_bound', 'non_data', 'root_bound'] * len(modes))
        self.assertEqual([row['raw_text'] for row in result.operands[1::3]], [' Selector ', *modes[1:]])
        for row in result.operands[1::3]:
            self.assertEqual((row['symbol_id'], row['target_id'], row['reason']), (None, None, None))
            self.assertEqual((row['suffix'], row['alias_chain']), ('', []))
        self.assertEqual(result.rack_candidates['matches']['direct_operands'], [])
        self.assertEqual(result.coverage['instructions_catalogued'], len(modes))
        self.assertEqual(result.status, 'complete')
        self.assertEqual(source.to_dict(), before)
        text = render_reference_text(result)
        self.assertIn('SWPB order-mode selector slot 1 is non_data', text)
        self.assertIn('raw text is retained and selector values are not validated.', text)
        self.assertIn('Mask widths, byte order, data types and destination access are not validated.', text)
        self.assertEqual(json.loads(render_reference_json(result)), result.to_dict())

    def test_arity_and_empty_slots_precede_roles_and_ascii_case_keeps_evidence(self) -> None:
        source = inventory(tag('Source') + tag('Mask') + tag('Destination'), program(
            'mVm(sOURCE,mASK,dESTINATION)sWpB(sOURCE,mode?,dESTINATION)'
            'SWPB(Source,)SWPB(Source,mode?,Destination,0)'
            'SWPB(Source,,Destination)MVM(,Mask,Destination);'))
        result = analyze_references(source)
        self.assertEqual([row['status'] for row in result.operands], [
            'root_bound', 'root_bound', 'root_bound', 'root_bound', 'non_data', 'root_bound',
            *(['argument_count_mismatch'] * 6), 'root_bound', 'empty', 'root_bound',
            'empty', 'root_bound', 'root_bound',
        ])
        self.assertEqual(result.coverage['instructions_catalogued'], 4)
        self.assertEqual(result.status, 'partial')
        self.assertEqual([instruction.opcode for instruction in source.rungs[0].instructions[:2]],
                         ['mVm', 'sWpB'])
        self.assertTrue(_swpb_order_mode('sWpB', 1))
        for opcode, index in (('SWPB', True), ('SWPB', 1.0), ('SWPB', 0), ('SWPB', 2),
                              ('SWPB', '1'), ('\u017fWPB', 1), ('SWP\u212a', 1), ('MVM', 1), (None, 1)):
            with self.subTest(opcode=opcode, index=index):
                self.assertFalse(_swpb_order_mode(opcode, index))

    def test_other_roles_occurrence_ids_and_source_inventory_stay_unchanged(self) -> None:
        source = inventory(tag('A'), program(
            'MVM(A,1,A)SWPB(42,Mode,A)MOV(1,A)ABS(1,A)ADD(A,1,A)'
            'TON(A,?,?)XIC(S:FS)JMP(Label?)CPT(A,Value + 1)PRIVATE_UNKNOWN(A);'))
        before = deepcopy(source.to_dict())
        result = analyze_references(source)
        self.assertEqual([row['status'] for row in result.operands], [
            'root_bound', 'literal', 'root_bound', 'literal', 'non_data', 'root_bound',
            'literal', 'root_bound', 'literal', 'root_bound', 'root_bound', 'literal', 'root_bound',
            'root_bound', 'non_data', 'non_data', 'system_flag', 'non_data',
            'root_bound', 'unsupported_expression', 'unsupported_instruction',
        ])
        self.assertEqual(len({row['id'] for row in result.operands}), len(result.operands))
        for row in result.operands:
            occurrence = f"{source.snapshot['id']}\0{row['instruction_id']}\0{row['argument_index']}"
            self.assertEqual(row['id'], 'operand_' + hashlib.sha256(occurrence.encode()).hexdigest())
            self.assertEqual((row['rung_id'], row['scope_id']), (source.rungs[0].id, source.rungs[0].scope_id))
        validate_references(source, result)
        self.assertEqual(source.to_dict(), before)

    def test_canonical_reanalysis_rejects_forged_selector_bindings_and_old_analyzer(self) -> None:
        source = inventory(tag('A') + tag('Mode'), program('SWPB(A,Mode,A)MVM(A,1,A);'))
        original = analyze_references(source)
        for fields in ({'status': 'root_bound', 'symbol_id': named(original, 'Mode')['id'],
                        'target_id': named(original, 'Mode')['id']},
                       {'status': 'literal'}, {'status': 'unsupported_address', 'reason': 'malformed_address'},
                       {'raw_text': 'Other?'}, {'argument_index': True}, {'suffix': '.Invented'},
                       {'alias_chain': [named(original, 'A')['id']]}):
            changed = deepcopy(original)
            changed.operands[1].update(fields)
            with self.subTest(fields=fields), self.assertRaises(ReferenceError):
                validate_references(source, changed)
        for changed in (replace(original, analyzer_version='source-references-6'),
                        replace(original, schema_version=5)):
            with self.assertRaises(ReferenceError):
                validate_references(source, changed)
            with self.assertRaises(ReferenceSummaryError):
                build_reference_summary(source, changed)

    def test_public_counts_and_work_report_use_current_pair_without_private_text(self) -> None:
        source = inventory(tag('PrivateSource') + tag('PrivateMask') + tag('PrivateDestination'), program(
            'MVM(PrivateSource,PrivateMask,PrivateDestination)MVM(73281,16#FF,PrivateDestination)'
            'SWPB(PrivateSource,PrivateMode?,PrivateDestination);'))
        before = deepcopy(source.to_dict())
        nested = build_reference_summary(source, analyze_references(source), revision=REVISION)
        self.assertEqual((nested['schema_version'], nested['exporter_version'], nested['analyzer_version']),
                         (12, 'reference-summary-12', 'source-references-9'))
        self.assertEqual(nested['source_summary'], build_summary(source, revision=REVISION))
        self.assertEqual((source.schema_version, source.parser_version), (3, 'source-inventory-3'))
        self.assertEqual(nested['source_summary']['schema_version'], 4)
        self.assertEqual(nested['source_summary']['instructions']['counts'], {'MVM': 2, 'SWPB': 1, 'withheld': 0})
        self.assertEqual(nested['operands']['total'], 9)
        self.assertEqual({key: count for key, count in nested['operands']['by_status'].items() if count},
                         {'root_bound': 6, 'literal': 2, 'non_data': 1})
        self.assertEqual(nested['coverage']['instructions_catalogued'], 3)
        rendered = render_reference_summary(nested)
        self.assertEqual(json.loads(rendered), nested)
        for private in ('Private', '73281', '16#FF', 'raw_text', 'symbol_id', 'target_id', 'scope_id',
                        source.snapshot['id'], source.snapshot['sha256']):
            self.assertNotIn(private, rendered)
        payload = report(report_source('MVM(A,1,A)SWPB(A,UnknownMode,A);'))
        self.assertEqual((payload['schema_version'], payload['workflow_version']), (15, 'work-check-15'))
        self.assertEqual(payload['analysis']['reference_summary']['schema_version'], 12)
        self.assertEqual(payload['status'], 'passed')
        self.assertIsNone(payload['diagnostic_sample'])
        self.assertEqual(json.loads(work_check.render_work_check_report(payload)), payload)
        self.assertEqual(source.to_dict(), before)

    def test_both_sample_kinds_reject_selector_before_address_parsing_with_other_gaps(self) -> None:
        cases = (
            ('SWPB(A,Mode?,A)XIC(Gap?);', sample('Mode?', opcode='SWPB', argument_index=1)),
            ('SWPB(A,Unknown:I,A)XIC(Gap:I);', colon_sample('Unknown:I', opcode='SWPB', argument_index=1)),
        )
        for text, selector_sample in cases:
            with self.subTest(kind=selector_sample['kind']):
                with patch('plc_workbench.diagnostic_sample._address') as address:
                    with self.assertRaises(DiagnosticSampleError):
                        validate_diagnostic_sample(selector_sample)
                    address.assert_not_called()
                payload = report(report_source(text))
                self.assertIsNotNone(payload['diagnostic_sample'])
                self.assertEqual(payload['diagnostic_sample']['opcode'], 'XIC')
                work_check.validate_work_check_report(payload)
                payload['diagnostic_sample'] = selector_sample
                with self.assertRaises(ValueError):
                    work_check.validate_work_check_report(payload)

    def test_canonical_sample_selection_skips_modes_and_preserves_malformed_data(self) -> None:
        cases = (
            ('SWPB(A,Mode?,A)SWPB(Source?,Unknown:I,Destination?);',
             sample('Source?', opcode='SWPB', argument_index=0)),
            ('SWPB(A,Unknown:I,A)MVM(MaskRack:I,1,A);',
             colon_sample('MaskRack:I', opcode='MVM', argument_index=0)),
            ('SWPB(A,Mode?,Destination?);', sample('Destination?', opcode='SWPB', argument_index=2)),
            ('MVM(A,Mask?,A);', sample('Mask?', opcode='MVM', argument_index=1)),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                source = inventory(tag('A'), program(text))
                references = analyze_references(source)
                source_before, references_before = source.to_dict(), references.to_dict()
                for _ in range(2):
                    self.assertEqual(build_diagnostic_sample(source, references), expected)
                validate_diagnostic_sample(expected)
                self.assertEqual(source.to_dict(), source_before)
                self.assertEqual(references.to_dict(), references_before)

    def test_actual_previous_report_remains_exactly_readable_and_version_mixes_fail(self) -> None:
        before = PREVIOUS_REPORT.read_bytes()
        previous = json.loads(before)
        historical = previous['analysis']['reference_summary']
        self.assertEqual((previous['schema_version'], previous['workflow_version']), (5, 'work-check-5'))
        self.assertEqual((historical['schema_version'], historical['exporter_version'], historical['analyzer_version']),
                         (7, 'reference-summary-7', 'source-references-6'))
        self.assertEqual(json.loads(work_check.render_work_check_report(previous)), previous)
        self.assertEqual(json.loads(render_reference_summary(historical)), historical)
        current = report(report_source('MVM(A,1,A)SWPB(A,UnknownMode,A);'))
        self.assertEqual(current['analysis']['reference_summary'].keys(),
                         historical.keys() | {'routine_instruction_shapes', 'routine_targets', 'routine_target_metadata', 'routine_graph'})
        for base, constants in ((previous, {'schema_version': 6, 'workflow_version': 'work-check-6'}),
                                (current, {'schema_version': 5, 'workflow_version': 'work-check-5'})):
            changed = deepcopy(base)
            changed.update(constants)
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(changed)
        for field, value in (('schema_version', 8), ('exporter_version', 'reference-summary-8'),
                             ('analyzer_version', 'source-references-7')):
            changed = deepcopy(historical)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(changed)
        self.assertEqual(PREVIOUS_REPORT.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
