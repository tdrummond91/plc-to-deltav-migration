"""Invented ladders challenge targeted disclosure, lexical fidelity and limits."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.targeted_samples import (
    MAX_BYTES, SLOTS, TargetedSamplesError, build_targeted_samples,
    render_targeted_samples_json, validate_targeted_samples,
)
from test_binding_context import capture as capture_context


def capture(texts=('XIC(Array[Index])OTE(Result);',), *, source_rungs=400):
    """Padding contains no instructions and exposes no additional example."""
    return capture_context(tuple(texts) + (';',) * max(0, source_rungs - len(texts)))


def build(texts=('XIC(Array[Index])OTE(Result);',), **kwargs):
    return build_targeted_samples(*capture(texts, **kwargs))


class TargetedSamplesTests(unittest.TestCase):
    def test_six_first_cases_have_closed_source_free_record(self):
        texts = ('XIC(SecretArray[PrivateIndex])OTE(SecretOutput);',
                 'MOV(OtherArray[OtherIndex],Destination);', 'PrivateBlock(Instance,Argument);',
                 'XIC(Gate)ONS(Memory)OTE(Result);', 'SFR(Control,Position,9);',
                 '[LES(Value,99),XIC(Override)]OTE(Result);')
        parts = capture(texts)
        before = [deepcopy(row.to_dict()) for row in parts[1:]]
        result = build_targeted_samples(*parts)
        self.assertEqual([case['slot'] for case in result['cases']], list(SLOTS))
        self.assertEqual([case['status'] for case in result['cases']], ['included'] * 6)
        self.assertEqual(result['charged_rungs'], 6)
        self.assertEqual(result['total_reserved_rungs'], 8)
        self.assertEqual(result['samples'][2]['unlisted_opcode'], 'PrivateBlock')
        rendered = render_targeted_samples_json(result)
        for secret in ('SecretArray', 'PrivateIndex', 'SecretOutput', 'OtherArray', 'OtherIndex',
                       'Destination', 'Instance', 'Argument', 'Gate', 'Memory', 'Result', 'Position', '99'):
            self.assertNotIn(secret, rendered)
        self.assertEqual([row.to_dict() for row in parts[1:]], before)
        self.assertEqual(json.loads(rendered), result)

    def test_lexical_roots_members_dynamic_expression_and_equal_literals_are_retained(self):
        result = build(('XIC(Secret[Index+3].State.7)MOV(Secret[Index+3].State.7,Other[Index]);',))
        self.assertEqual(result['charged_rungs'], 1)
        self.assertEqual([case['sample_id'] for case in result['cases'][:2]], ['sample_1'] * 2)
        self.assertEqual(result['samples'][0]['rung_text'],
                         'XIC(ROOT_1 [ ROOT_2 + LITERAL_1 ] . MEMBER_1 . BIT_1)'
                         'MOV(ROOT_1 [ ROOT_2 + LITERAL_1 ] . MEMBER_1 . BIT_1,ROOT_3 [ ROOT_2 ]);')
        self.assertEqual(result['samples'][0]['literal_kinds'], {'LITERAL_1': 'integer'})

    def test_bit_selectors_and_decimal_literals_stay_distinct(self):
        result = build(('OddBlock(Root.7,Array[Index].12,Struct.Member.7,.7,7,7.0);',))
        self.assertEqual(result['samples'][0]['rung_text'],
                         'UNLISTED_OP_1(ROOT_1 . BIT_1,ROOT_2 [ ROOT_3 ] . BIT_2,'
                         'ROOT_4 . MEMBER_1 . BIT_1,LITERAL_1,LITERAL_2,LITERAL_3);')
        self.assertEqual(result['samples'][0]['literal_kinds'],
                         {'LITERAL_1': 'real', 'LITERAL_2': 'integer', 'LITERAL_3': 'real'})

    def test_string_escapes_radix_values_and_qualified_roots_are_scrubbed(self):
        result = build(('Novel(Local:3:I.Data.4,Program:Secret[Idx],16#AB_CD,2#101,8#17,'
                        '2.5e-3,\'private$\'text\',\'private$\'text\',"hidden""quote",?);',))
        sample = result['samples'][0]
        self.assertNotIn('Local', sample['rung_text'])
        self.assertNotIn('Program', sample['rung_text'])
        self.assertEqual(list(sample['literal_kinds'].values()), ['radix', 'radix', 'radix', 'real', 'text', 'text'])
        self.assertEqual(sample['rung_text'].count('LITERAL_5'), 2)
        self.assertIn('ROOT_1 . MEMBER_1 . BIT_1', sample['rung_text'])
        self.assertIn('ROOT_2 [ ROOT_3 ]', sample['rung_text'])
        self.assertIn(',?);', sample['rung_text'])

    def test_samples_reset_names_without_cross_rung_join_or_literal_values(self):
        result = build(('XIC(First[Idx])OTE(Output);', 'MOV(Second[Other],Output);'))
        first, second = result['samples']
        self.assertEqual(first['rung_text'], 'XIC(ROOT_1 [ ROOT_2 ])OTE(ROOT_3);')
        self.assertEqual(second['rung_text'], 'MOV(ROOT_1 [ ROOT_2 ],ROOT_3);')
        self.assertEqual(set(first), {'id', 'rung_text', 'literal_kinds', 'unlisted_opcode'})

    def test_same_rung_merges_distinct_slots_and_charges_once(self):
        result = build(('[LES(Array[Index],Other[Idx]),XIC(Override)]ONS(Memory)'
                        'SFR(Control,Step,1)Unknown(Instance)OTE(Result);',), source_rungs=150)
        self.assertEqual(result['charged_rungs'], 1)
        self.assertEqual(result['total_reserved_rungs'], 3)
        self.assertEqual({case['sample_id'] for case in result['cases']}, {'sample_1'})
        self.assertEqual({case['status'] for case in result['cases']}, {'included'})

    def test_first_unlexable_candidate_is_withheld_without_later_substitution(self):
        result = build(('Mystery(A@B);', 'Mystery(Safe);'))
        self.assertEqual(result['cases'][2]['status'], 'unsupported_lexical')
        self.assertEqual(result['samples'], [])
        for character in ('\\', '{x}', '\u03bb', '$', '#', '::'):
            with self.subTest(character=character):
                result = build((f'Mystery(A{character}B);',))
                self.assertEqual(result['cases'][2]['status'], 'unsupported_lexical')

    def test_first_oversized_candidate_is_withheld_without_later_substitution(self):
        cases = ('Mystery(' + 'Long' * 2100 + ');',
                 'Mystery(' + ','.join('A' for _ in range(70)) + ');',
                 'Mystery(A)' + 'XIC(A)' * 24 + ';',
                 '[' * 5 + 'Mystery(A)' + ',]' * 5 + ';',
                 '[' + ','.join(['Mystery(A)'] + [''] * 16) + '];',
                 'Mystery(A' + '[B' * 5 + ']' * 5 + ');')
        for text in cases:
            with self.subTest(length=len(text)):
                result = build((text, 'Mystery(Safe);'))
                self.assertEqual(result['cases'][2]['status'], 'too_large')
                self.assertEqual(result['samples'], [])

    def test_unsupported_tokens_never_leak_raw_fallback(self):
        result = build(('XIC(Array[Index])SecretBlock(A@B);', 'XIC(Later[Other]);'))
        self.assertEqual([case['status'] for case in result['cases'][:3]],
                         ['unsupported_lexical', 'included', 'unsupported_lexical'])
        self.assertEqual(result['samples'][0]['rung_text'], 'XIC(ROOT_1 [ ROOT_2 ]);')
        self.assertNotIn('SecretBlock', render_targeted_samples_json(result))

    def test_only_first_unknown_block_can_supply_one_actual_mnemonic(self):
        result = build(('FirstMystery(Secret);', 'XIC(Array[Index])OtherMystery(Other);'))
        self.assertEqual(result['cases'][0]['status'], 'unsupported_lexical')
        self.assertEqual(result['samples'][0]['unlisted_opcode'], 'FirstMystery')
        self.assertNotIn('OtherMystery', render_targeted_samples_json(result))
        result = build(('FirstMystery(Secret)OtherMystery(Other);', 'FirstMystery(Safe);'))
        self.assertEqual(result['cases'][2]['status'], 'unsupported_lexical')
        self.assertEqual(result['samples'], [])

    def test_public_unknown_family_keeps_mnemonic_without_private_clue(self):
        result = build(('CMP(A>B);', 'OddBlock(Secret);'))
        self.assertEqual(result['samples'][0]['rung_text'], 'CMP(ROOT_1 > ROOT_2);')
        self.assertIsNone(result['samples'][0]['unlisted_opcode'])
        self.assertNotIn('OddBlock', render_targeted_samples_json(result))

    def test_tiny_source_never_spends_more_than_remaining_new_budget(self):
        for total in (0, 1, 49, 50, 99, 100, 149):
            with self.subTest(total=total):
                texts = () if total == 0 else ('ONS(Memory);',)
                result = build(texts, source_rungs=total)
                self.assertEqual(result['charged_rungs'], 0)
                self.assertEqual(result['total_reserved_rungs'], 2)
                self.assertEqual(result['max_total_rungs'], total // 50)
                self.assertEqual(result['cases'][3]['status'], 'not_found' if total == 0 else 'budget_exhausted')
        result = build(('XIC(A[I]);', 'XIC(B[J]);', 'ONS(M);'), source_rungs=150)
        self.assertEqual(result['charged_rungs'], 1)
        self.assertEqual(result['cases'][0]['status'], 'included')
        self.assertEqual(result['cases'][1]['status'], 'budget_exhausted')
        self.assertEqual(result['cases'][3]['status'], 'budget_exhausted')

    def test_static_array_indices_and_empty_rungs_do_not_match_dynamic_cases(self):
        result = build(('XIC(A[1,2]);', 'XIC(B[1]);', 'NOP();'))
        self.assertEqual([case['status'] for case in result['cases'][:2]], ['not_found', 'not_found'])
        result = build(('XIC(A[1+2]);',))
        self.assertEqual(result['cases'][0]['status'], 'included')
        self.assertEqual(result['samples'][0]['rung_text'], 'XIC(ROOT_1 [ LITERAL_1 + LITERAL_2 ]);')

    def test_expression_leaves_do_not_fill_operand_only_dynamic_slots(self):
        result = build(('CPT(Destination,Array[Index]+Other[Idx]);', 'ONS(Memory);'))
        self.assertEqual([case['status'] for case in result['cases'][:2]], ['not_found', 'not_found'])
        self.assertEqual(result['charged_rungs'], 1)
        self.assertEqual(result['samples'][0]['rung_text'], 'ONS(ROOT_1);')

    def test_word_operators_are_fixed_but_similarly_spelled_tag_roots_are_scrubbed(self):
        result = build(('OddBlock(AND,OR[Index],NOT,MOD,A AND B,NOT A,A MOD B);',))
        self.assertEqual(result['samples'][0]['rung_text'],
                         'UNLISTED_OP_1(ROOT_1,ROOT_2 [ ROOT_3 ],ROOT_4,ROOT_5,'
                         'ROOT_6 AND ROOT_7,NOT ROOT_6,ROOT_6 MOD ROOT_7);')

    def test_only_recognized_comparison_and_coil_signatures_select_branch_case(self):
        for text in ('[XIC(A),XIO(B)]OTE(C);', '[LES(A),XIC(B)]OTE(C);', '[LES(A,1),XIC(B)]OTE(C,D);'):
            result = build((text,))
            self.assertEqual(result['cases'][5]['status'], 'not_found')
        result = build(('[LES(A,1),XIC(B)]OTE(C);',))
        self.assertEqual(result['cases'][5]['status'], 'included')

    def test_prerequisite_and_foreign_snapshot_forgeries_are_rejected(self):
        parts = capture()
        bad = deepcopy(parts[-1])
        bad.gaps[0]['category'] = 'other_binding_gap'
        with self.assertRaises(TargetedSamplesError):
            build_targeted_samples(*parts[:-1], bad)
        with self.assertRaises(TargetedSamplesError):
            build_targeted_samples(replace(parts[0], id='foreign'), *parts[1:])

    def test_closed_native_shape_budget_and_case_conservation(self):
        valid = build()
        mutations = (
            lambda r: r.update(secret='hidden'),
            lambda r: r.update(charged_rungs=2),
            lambda r: r.update(max_total_rungs=40),
            lambda r: r.update(total_reserved_rungs=2),
            lambda r: r.update(prior_reserved_rungs=0),
            lambda r: r.update(schema_version=True),
            lambda r: r['cases'][1].update(status='included', sample_id='sample_1'),
            lambda r: r['cases'][0].update(status='not_found', sample_id=None),
            lambda r: r['samples'][0].update(id='sample_2'),
            lambda r: r['samples'][0].update(source_id='secret'),
        )
        for mutate in mutations:
            bad = deepcopy(valid)
            mutate(bad)
            with self.assertRaises(TargetedSamplesError):
                validate_targeted_samples(bad)

    def test_public_text_rejects_original_names_values_noncanonical_labels_and_hidden_data(self):
        valid = build()
        texts = ('XIC(Secret [ ROOT_2 ])OTE(ROOT_3);', 'XIC(ROOT_1 [ 123 ])OTE(ROOT_2);',
                 'XIC(ROOT_2 [ ROOT_1 ])OTE(ROOT_3);', 'XIC(ROOT_1 [ ROOT_2 ])OTE(MEMBER_1);',
                 'XIC(ROOT_1 [ ROOT_2 ])OTE(ROOT_3); hidden', 'XIC(ROOT_1[ROOT_2])OTE(ROOT_3);',
                 'XIC(ROOT_1 [ ROOT_2 ])OTE(ROOT_3)Secret(ROOT_1);')
        for text in texts:
            with self.subTest(text=text):
                bad = deepcopy(valid)
                bad['samples'][0]['rung_text'] = text
                with self.assertRaises(TargetedSamplesError):
                    validate_targeted_samples(bad)
        bad = deepcopy(valid)
        bad['samples'][0]['literal_kinds'] = {'LITERAL_1': 'integer'}
        with self.assertRaises(TargetedSamplesError):
            validate_targeted_samples(bad)

    def test_unknown_mnemonic_is_a_single_narrow_clue_tied_to_unknown_slot(self):
        valid = build(('OddBlock(A);',))
        for unknown in ('A' * 65, 'contains space', '<script>', 'XIC', 'UNLISTED_OP_1'):
            bad = deepcopy(valid)
            bad['samples'][0]['unlisted_opcode'] = unknown
            with self.assertRaises(TargetedSamplesError):
                validate_targeted_samples(bad)
        bad = deepcopy(valid)
        bad['cases'][2].update(status='not_found', sample_id=None)
        bad['cases'][3].update(status='included', sample_id='sample_1')
        with self.assertRaises(TargetedSamplesError):
            validate_targeted_samples(bad)

    def test_adversarial_native_values_and_exact_output_byte_boundary(self):
        valid = build()
        class Hostile(dict):
            def items(self):
                raise AssertionError('Foreign hook invoked')
        with self.assertRaises(TargetedSamplesError):
            validate_targeted_samples(Hostile(valid))
        cycle = deepcopy(valid)
        cycle['samples'].append(cycle)
        with self.assertRaises(TargetedSamplesError):
            validate_targeted_samples(cycle)
        for value in (True, -1, 2 ** 100, 1.5, object()):
            bad = deepcopy(valid)
            bad['source_rungs'] = value
            with self.assertRaises(TargetedSamplesError):
                validate_targeted_samples(bad)
        encoded = render_targeted_samples_json(valid)
        self.assertLess(len(encoded.encode()), MAX_BYTES)
        with patch('plc_workbench.targeted_samples.MAX_BYTES', len(encoded.encode())):
            self.assertEqual(render_targeted_samples_json(valid), encoded)
        with patch('plc_workbench.targeted_samples.MAX_BYTES', len(encoded.encode()) - 1):
            with self.assertRaises(TargetedSamplesError):
                render_targeted_samples_json(valid)

    def test_bundle_byte_limit_withholds_case_without_later_candidate_fallback(self):
        parts = capture(('OddBlock(A,B,C,D,E,F);', 'OddBlock(A);'))
        empty = build((), source_rungs=400)
        cap = len(render_targeted_samples_json(empty).encode()) + 50
        with patch('plc_workbench.targeted_samples.MAX_BYTES', cap):
            result = build_targeted_samples(*parts)
            self.assertEqual(result['cases'][2]['status'], 'too_large')
            self.assertEqual(result['samples'], [])
            self.assertLessEqual(len(render_targeted_samples_json(result).encode()), cap)


if __name__ == '__main__':
    unittest.main()
