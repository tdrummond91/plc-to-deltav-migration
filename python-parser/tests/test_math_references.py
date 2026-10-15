"""Unary-math root evidence from invented sources, without runtime evaluation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest

from plc_workbench.reference_reporting import render_reference_json, render_reference_text
from plc_workbench.references import ReferenceError, analyze_references, validate_references
from test_references import inventory, named, program, tag


OPCODES = ('ABS', 'LN', 'SQR')


class MathReferenceTests(unittest.TestCase):
    def test_all_three_instructions_bind_both_roots_and_accept_source_literals(self) -> None:
        text = ''.join(f'{opcode}(Source,Destination){opcode}(-1,Destination)' for opcode in OPCODES) + ';'
        source = inventory(tag('Source') + tag('Destination'), program(text))
        result = analyze_references(source)
        self.assertEqual([row['status'] for row in result.operands],
                         ['root_bound', 'root_bound', 'literal', 'root_bound'] * 3)
        self.assertEqual(result.coverage['instructions_total'], 6)
        self.assertEqual(result.coverage['instructions_catalogued'], 6)
        self.assertEqual(result.coverage['operands_total'], 12)
        self.assertEqual(len({row['id'] for row in result.operands}), 12)
        for row in result.operands:
            if row['status'] == 'root_bound':
                expected = named(result, row['raw_text'])['id']
                self.assertEqual((row['symbol_id'], row['target_id']), (expected, expected))
        # Negative LN/SQR input and these synthetic DINT declarations do not
        # trigger domain or data-type analysis in this root-reference stage.
        self.assertEqual(result.status, 'complete')
        self.assertEqual((result.schema_version, result.analyzer_version), (6, 'source-references-9'))
        for field in ('semantic_analysis', 'effect_analysis', 'member_validation'):
            self.assertEqual(getattr(result, field), 'not_implemented')
        validate_references(source, result)

    def test_existing_lexical_literal_policy_also_applies_to_destination_slots(self) -> None:
        literals = ('0', '-2', '+.5', '1e-3', '2#10', '8#17', '16#FF', "'text'", '"text"')
        for opcode in OPCODES:
            for literal in literals:
                with self.subTest(opcode=opcode, literal=literal):
                    source = inventory(programs=program(f'{opcode}({literal},{literal});'))
                    result = analyze_references(source)
                    self.assertEqual([row['status'] for row in result.operands], ['literal', 'literal'])
                    for row in result.operands:
                        self.assertIsNone(row['symbol_id'])
                        self.assertIsNone(row['target_id'])
                        self.assertIsNone(row['reason'])
                        self.assertEqual((row['suffix'], row['alias_chain']), ('', []))
                    self.assertEqual(result.status, 'complete')

    def test_alias_scope_suffix_raw_evidence_and_occurrence_links_are_preserved(self) -> None:
        tags = tag('Base') + tag('Signal') + tag('Destination') + tag('Alias', 'Base.Member[2]')
        local = tag('Signal') + tag('Base')
        source = inventory(tags, program('ABS(Alias.7,Destination)'
                                        'LN(Signal[9],Destination)SQR(Alias,Signal);', local))
        rung = source.rungs[0]
        first = replace(rung.instructions[0], arguments=('  aLIAS.7  ', ' Destination '))
        source = replace(source, rungs=[replace(rung, instructions=[first, *rung.instructions[1:]])])
        result = analyze_references(source)
        alias_operand, destination, local_operand, _, second_alias, second_local = result.operands
        self.assertEqual(alias_operand['raw_text'], '  aLIAS.7  ')
        self.assertEqual(destination['raw_text'], ' Destination ')
        self.assertEqual(alias_operand['target_id'], result.symbols[0]['id'])
        self.assertEqual(alias_operand['suffix'], '.Member[2].7')
        self.assertEqual(alias_operand['alias_chain'], [named(result, 'Alias')['id']])
        self.assertEqual(second_alias['suffix'], '.Member[2]')
        local_id = named(result, 'Signal', rung.scope_id)['id']
        self.assertEqual(local_operand['target_id'], local_id)
        self.assertEqual(local_operand['suffix'], '[9]')
        self.assertEqual(second_local['target_id'], local_id)
        self.assertEqual({row['id'] for row in result.symbols},
                         {row.id for row in source.entities if row.kind == 'tag'})
        for row in result.operands:
            occurrence = f"{source.snapshot['id']}\0{row['instruction_id']}\0{row['argument_index']}"
            self.assertEqual(row['id'], 'operand_' + hashlib.sha256(occurrence.encode()).hexdigest())
            self.assertEqual(row['rung_id'], rung.id)
            self.assertEqual(row['scope_id'], rung.scope_id)
        validate_references(source, result)

    def test_mixed_case_opcodes_and_tags_keep_the_same_contract(self) -> None:
        source = inventory(tag('Source') + tag('Destination'),
                           program('aBs(sOURCE,dESTINATION)lN(Source,Destination)sQr(SOURCE,DESTINATION);'))
        result = analyze_references(source)
        self.assertEqual(result.coverage['instructions_catalogued'], 3)
        self.assertEqual([row['status'] for row in result.operands], ['root_bound'] * 6)
        self.assertEqual([instruction.opcode for instruction in source.rungs[0].instructions],
                         ['aBs', 'lN', 'sQr'])
        self.assertEqual([row['raw_text'] for row in result.operands],
                         ['sOURCE', 'dESTINATION', 'Source', 'Destination', 'SOURCE', 'DESTINATION'])
        validate_references(source, result)

    def test_wrong_arity_empty_expressions_and_dynamic_indices_stay_explicit_gaps(self) -> None:
        tags = tag('Source') + tag('Destination') + tag('Index')
        for opcode in OPCODES:
            for arguments in ('Source', 'Source,Destination,0', ''):
                with self.subTest(opcode=opcode, arguments=arguments):
                    result = analyze_references(inventory(tags, program(f'{opcode}({arguments});')))
                    self.assertEqual(result.coverage['instructions_catalogued'], 0)
                    self.assertTrue(all(row['status'] == 'argument_count_mismatch' for row in result.operands))
                    self.assertEqual(result.status, 'partial')
            result = analyze_references(inventory(tags, program(
                f'{opcode}(,Destination){opcode}(Source,)'
                f'{opcode}(Source + 1,Destination){opcode}(Source,Destination + 1)'
                f'{opcode}(Source[Index],Destination){opcode}(Source,Destination[Index]);')))
            self.assertEqual([row['status'] for row in result.operands], [
                'empty', 'root_bound', 'root_bound', 'empty',
                'unsupported_address', 'root_bound', 'root_bound', 'unsupported_address',
                'unsupported_address', 'root_bound', 'root_bound', 'unsupported_address',
            ])
            self.assertEqual([result.operands[index]['reason'] for index in (4, 7, 8, 11)],
                             ['malformed_address', 'malformed_address',
                              'non_static_array_index', 'non_static_array_index'])
            self.assertEqual(result.status, 'partial')

    def test_unselected_opcodes_and_existing_special_roles_keep_their_rules(self) -> None:
        text = ('SQRT(Source,Destination)LOG(Source,Destination)PRIVATE_MATH(Source,Destination)'
                'ADD(Source,1,Destination)MOV(1,Destination)CPT(Destination,Source + 1)'
                'TON(Source,?,?)XIC(S:FS)JMP(Label);')
        result = analyze_references(inventory(tag('Source') + tag('Destination'), program(text)))
        self.assertEqual([row['status'] for row in result.operands], [
            *(['unsupported_instruction'] * 6), 'root_bound', 'literal', 'root_bound',
            'literal', 'root_bound', 'root_bound', 'unsupported_expression',
            'root_bound', 'non_data', 'non_data', 'system_flag', 'non_data',
        ])
        self.assertEqual(result.coverage['instructions_catalogued'], 6)
        self.assertEqual(result.status, 'partial')

    def test_canonical_private_records_reject_alterations_without_mutating_source(self) -> None:
        source = inventory(tag('Source') + tag('Destination'), program('ABS(Source,Destination)LN(-1,0)SQR(4,Destination);'))
        before = source.to_dict()
        result = analyze_references(source)
        text = render_reference_text(result)
        self.assertIn('ABS/LN/SQR slots receive lexical root/literal classification', text)
        self.assertIn('math, domains, types and destination access are not validated.', text)
        self.assertIn('Source -> root_bound', text)
        self.assertIn('-1 -> literal', text)
        self.assertEqual(json.loads(render_reference_json(result)), result.to_dict())
        self.assertEqual(source.to_dict(), before)
        for fields in ({'status': 'literal'}, {'raw_text': 'Other'}, {'argument_index': False},
                       {'target_id': None}, {'suffix': '.Invented'}, {'instruction_id': 'forged'}):
            changed = deepcopy(result)
            changed.operands[0].update(fields)
            with self.subTest(fields=fields), self.assertRaises(ReferenceError):
                validate_references(source, changed)
        for schema, analyzer in ((4, 'source-references-5'), (4, 'source-references-6'), (3, 'source-references-6'),
                                 (5, 'source-references-6')):
            with self.subTest(schema=schema, analyzer=analyzer), self.assertRaises(ReferenceError):
                validate_references(source, replace(result, schema_version=schema, analyzer_version=analyzer))
        validate_references(source, result)
        self.assertEqual(source.to_dict(), before)


if __name__ == '__main__':
    unittest.main()
