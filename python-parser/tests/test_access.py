"""Independent synthetic evidence for bounded explicit operand access."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import (
    AccessError, analyze_access, render_access_json, validate_access,
)
from plc_workbench.references import analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def tag(name: str, target: str | None = None) -> str:
    attrs = 'TagType="Base" DataType="DINT"' if target is None else f'TagType="Alias" AliasFor="{target}"'
    return f'<Tag Name="{name}" {attrs}/>'


def program(text: str, tags: str = '', name: str = 'P') -> str:
    return (f'<Program Name="{name}"><Tags>{tags}</Tags><Routines>'
            '<Routine Name="R" Type="RLL"><RLLContent><Rung Number="0" Type="N">'
            f'<Text><![CDATA[{text}]]></Text></Rung></RLLContent></Routine>'
            '</Routines></Program>')


def source(text: str, tags: str = '', local_tags: str = '', extra_programs: str = ''):
    raw = ('<RSLogix5000Content><Controller Name="C"><Tags>' + tags +
           '</Tags><Programs>' + program(text, local_tags) + extra_programs +
           '</Programs></Controller></RSLogix5000Content>')
    return analyze_snapshot(snapshot_from_bytes(raw.encode()))


def analyze(text: str, tags: str = '', local_tags: str = ''):
    inventory = source(text, tags, local_tags)
    references = analyze_references(inventory)
    return inventory, references, analyze_access(inventory, references)


class AccessTests(unittest.TestCase):
    def test_mixed_alias_suffixes_and_local_shadow_use_existing_binding(self) -> None:
        inventory = source('XIC(Alias.3)MOV(Shared.Member,Base.Other);',
                           tag('Base') + tag('Alias', 'Base[2]') + tag('Shared'),
                           tag('Shared'), program('XIC(Shared);', name='Q'))
        references = analyze_references(inventory)
        result = analyze_access(inventory, references)
        self.assertEqual(result.status, 'complete')
        self.assertEqual([row['role'] for row in result.operands], ['read', 'read', 'write', 'read'])
        self.assertEqual(result.operands[0]['suffix'], '[2].3')
        self.assertNotEqual(result.operands[0]['symbol_id'], result.operands[0]['target_id'])
        self.assertNotEqual(result.operands[1]['target_id'], result.operands[3]['target_id'])
        for operand, reference in zip(result.operands, references.operands, strict=True):
            for key in ('id', 'instruction_id', 'rung_id', 'argument_index', 'symbol_id', 'target_id', 'suffix'):
                self.assertEqual(operand[key], reference[key])
            self.assertNotIn('raw_text', operand)
            self.assertEqual(operand['binding_status'], reference['status'])
        base = next(row for row in result.roots if row['target_id'] == result.operands[0]['target_id'])
        self.assertEqual(base['read_operand_ids'], [result.operands[0]['id']])
        self.assertEqual(base['write_operand_ids'], [result.operands[2]['id']])
        self.assertNotIn('edges', result.to_dict())
        validate_access(inventory, references, result)

    def test_mvm_retained_destination_and_one_shot_storage_are_disjoint_read_write(self) -> None:
        _, _, result = analyze('MVM(A,255,A.Member)ONS(A)OSR(A,B)OSF(A,B)OTL(A)OTU(A);',
                               tag('A') + tag('B'))
        self.assertEqual([row['role'] for row in result.operands],
                         ['read', 'read', 'read_write', 'read_write', 'read_write', 'write',
                          'read_write', 'write', 'write', 'write'])
        indexed = [identity for root in result.roots for key, ids in root.items()
                   if key.endswith('_operand_ids') for identity in ids]
        self.assertEqual(len(indexed), len(set(indexed)))
        self.assertEqual(len(indexed), 9)
        self.assertEqual(result.coverage['bound_by_role']['read_write'], 4)
        self.assertEqual(result.coverage['access_gap_operands'], 0)

    def test_catalogue_patterns_and_ascii_case_preserve_original_opcodes(self) -> None:
        patterns = [
            ('xic(A)', ['read']), ('xio(A)', ['read']), ('ote(A)', ['write']),
            ('clr(A)', ['write']), ('mov(1,A)', ['read', 'write']),
            ('swpb(A,REVERSE,B)', ['read', 'non_data', 'write']),
            *[(f'{opcode}(A,2,B)', ['read', 'read', 'write']) for opcode in ('ADD', 'SUB', 'MUL', 'DIV')],
            *[(f'{opcode}(A,B)', ['read', 'write']) for opcode in ('ABS', 'LN', 'SQR')],
            *[(f'{opcode}(A,B)', ['read', 'read']) for opcode in ('EQU', 'NEQ', 'LES', 'LEQ', 'GRT', 'GEQ')],
            ('LIM(0,A,3)', ['read', 'read', 'read']), ('JMP(Label)', ['non_data']),
            ('LBL(Label)', ['non_data']),
        ]
        for instruction, expected in patterns:
            with self.subTest(instruction=instruction):
                _, _, result = analyze(instruction + ';', tag('A') + tag('B'))
                self.assertEqual([row['role'] for row in result.operands], expected)
                self.assertEqual(result.status, 'complete')
                self.assertEqual(result.instructions[0]['opcode'], instruction.split('(')[0])
        inventory, _, _ = analyze('ONS(A);', tag('A'))
        rung = inventory.rungs[0]
        # Unicode long s would uppercase to S; it is never an admitted mnemonic.
        inventory = replace(inventory, rungs=[replace(rung, instructions=[replace(
            rung.instructions[0], opcode='ON\u017f')])])
        result = analyze_access(inventory, analyze_references(inventory))
        self.assertEqual(result.instructions[0]['status'], 'unsupported_instruction')
        self.assertEqual(result.operands[0]['role'], 'unknown')

    def test_wrong_arity_and_any_empty_slot_make_every_slot_unknown(self) -> None:
        _, _, result = analyze('MOV(A)MOV(A,)SWPB(A,,B)OSR(,B)ADD(A,B);', tag('A') + tag('B'))
        self.assertEqual([row['status'] for row in result.instructions],
                         ['argument_count_mismatch', 'empty_argument', 'empty_argument',
                          'empty_argument', 'argument_count_mismatch'])
        self.assertTrue(all(row['role'] == 'unknown' for row in result.operands))
        self.assertEqual(result.status, 'partial')
        # Reference bindings on the nonempty half of malformed signatures stay
        # visible as unknown access; no slot is promoted back into a known role.
        self.assertGreater(result.coverage['bound_by_role']['unknown'], 0)

    def test_literal_destination_is_never_write_evidence(self) -> None:
        _, _, result = analyze('XIC(S:FS)MOV(12,27)ONS(0)XIC(1)SWPB(1,UNKNOWN,A);', tag('A'))
        self.assertEqual(result.operands[0]['binding_status'], 'system_flag')
        self.assertEqual(result.operands[2]['role'], 'write')
        self.assertEqual(result.operands[2]['binding_status'], 'literal')
        self.assertIsNone(result.operands[2]['target_id'])
        self.assertEqual(result.coverage['access_gap_operands'], 2)
        self.assertEqual(result.coverage['bound_by_role']['write'], 1)
        self.assertEqual(result.status, 'partial')
        _, _, complete = analyze('XIC(s:fs)MOV(27,A)JMP(Label);', tag('A'))
        self.assertEqual(complete.status, 'complete')

    def test_unresolved_read_and_alias_cycle_are_access_gaps(self) -> None:
        _, _, result = analyze('XIC(Missing)OTE(A);', tag('A', 'B') + tag('B', 'A'))
        self.assertEqual([row['binding_status'] for row in result.operands], ['unresolved', 'alias_cycle'])
        self.assertEqual(result.coverage['access_gap_operands'], 2)
        self.assertEqual(result.roots, [])
        self.assertEqual(result.status, 'partial')

    def test_unsupported_bound_slots_remain_unknown_and_unbound_slots_are_not_guessed(self) -> None:
        _, _, result = analyze('CPT(A,B+1)PID(A,B,C,D,E,F,G)Custom(A)JSR(R)EQ(A,B);',
                               ''.join(tag(name) for name in 'ABCDEFGT'))
        self.assertTrue(all(row['role'] == 'unknown' for row in result.operands))
        self.assertEqual(result.coverage['instructions_by_status']['unsupported_instruction'], 5)
        self.assertGreater(result.coverage['bound_by_role']['unknown'], 0)
        for instruction in result.instructions[-3:]:
            ids = set(instruction['operand_ids'])
            self.assertTrue(all(row['target_id'] is None for row in result.operands if row['id'] in ids))

    def test_timer_reset_and_copy_roles_reuse_reference_occurrences(self) -> None:
        inventory, references, result = analyze(
            'ton(T,?,?)ToF(T,+100,-0)rto(T,2#1_0,-16#f_F)RES(T)'
            'COP(A[2],B[4],Length)CPS(A,B,12);',
            ''.join(tag(name) for name in ('T', 'A', 'B', 'Length')),
        )
        self.assertEqual([row['status'] for row in result.instructions], ['classified'] * 6)
        self.assertEqual([row['role'] for row in result.operands],
                         ['read_write', 'non_data', 'non_data'] * 3 +
                         ['write', 'read', 'write', 'read', 'read', 'write', 'read'])
        self.assertEqual(result.coverage['timer_instructions'], 3)
        self.assertEqual(result.coverage['timer_pseudo_operands_by_kind'],
                         {'placeholder': 2, 'integer_literal': 4})
        self.assertEqual(result.coverage['bound_by_role']['non_data'], 0)
        self.assertEqual(result.status, 'complete')
        self.assertEqual((result.schema_version, result.analyzer_version), (3, 'instruction-access-3'))
        self.assertEqual(result.initialization_analysis, 'not_implemented')
        self.assertEqual(result.range_analysis, 'not_implemented')
        for operand, reference in zip(result.operands, references.operands, strict=True):
            for key in ('id', 'symbol_id', 'target_id', 'suffix'):
                self.assertEqual(operand[key], reference[key])
            self.assertEqual(operand['binding_status'], reference['status'])
        pseudo = [row for row in result.operands if row['reason'] == 'timer_pseudo_operand']
        self.assertEqual(len(pseudo), 6)
        self.assertTrue(all(row['role'] == 'non_data' and row['target_id'] is None for row in pseudo))
        self.assertEqual(result.operands[10]['suffix'], '[2]')
        self.assertEqual(result.operands[11]['suffix'], '[4]')
        validate_access(inventory, references, result)

    def test_timer_pseudo_integer_grammar_is_lexical_and_never_a_runtime_read(self) -> None:
        values = ['0', '+0', '-0', '0123', '-999999999999999999999999999',
                  '2#1_0', '+2#0', '-8#7_0', '8#123', '16#f_F', '+16#0A', '-16#BEEF']
        for value in values:
            with self.subTest(value=value):
                _, _, result = analyze(f'TON(T, {value} , ? );', tag('T'))
                self.assertEqual(result.instructions[0]['status'], 'classified')
                self.assertEqual(result.operands[1]['role'], 'non_data')
                self.assertEqual(result.operands[1]['binding_status'], 'literal')
                self.assertEqual(result.coverage['operands_by_role']['read'], 0)
                self.assertEqual(result.coverage['timer_pseudo_operands_by_kind'],
                                 {'placeholder': 1, 'integer_literal': 1})

    def test_unsupported_timer_pseudo_form_makes_all_three_roles_unknown(self) -> None:
        values = ['A', 'A.Member', 'A[0]', 'A+1', '1.0', '1e2', '"1"', "'2'",
                  '1_000', '2#2', '8#8', '16#G', '2#_1', '2#1_', '16#F__F',
                  '١', '−1', '+?', 'TRUE']
        for opcode in ('TON', 'TOF', 'RTO'):
            for value in values:
                for index in (1, 2):
                    fields = ['T', '?', '?']
                    fields[index] = value
                    with self.subTest(opcode=opcode, value=value, index=index):
                        _, references, result = analyze(f'{opcode}({",".join(fields)});', tag('T') + tag('A'))
                        self.assertEqual(result.instructions[0]['status'], 'unsupported_operand_form')
                        self.assertEqual([row['role'] for row in result.operands], ['unknown'] * 3)
                        self.assertTrue(all(row['reason'] == 'unsupported_operand_form' for row in result.operands))
                        self.assertEqual(result.coverage['timer_instructions'], 0)
                        self.assertEqual(sum(result.coverage['timer_pseudo_operands_by_kind'].values()), 0)
                        self.assertEqual(result.status, 'partial')
                        for operand, reference in zip(result.operands, references.operands, strict=True):
                            self.assertEqual(operand['target_id'], reference['target_id'])
                        if value == 'A':
                            self.assertEqual(result.operands[index]['binding_status'], 'root_bound')
                            self.assertEqual(result.coverage['bound_by_role']['unknown'], 2)

    def test_timer_signature_failures_take_priority_and_root_failures_stay_known_gaps(self) -> None:
        for text, status in [('TON(T,?)', 'argument_count_mismatch'),
                             ('TOF(T,?,A,?)', 'argument_count_mismatch'),
                             ('RTO(T,,A)', 'empty_argument'), ('TON(,?,?)', 'empty_argument')]:
            with self.subTest(text=text):
                _, _, result = analyze(text + ';', tag('T') + tag('A'))
                self.assertEqual(result.instructions[0]['status'], status)
                self.assertTrue(all(row['role'] == 'unknown' for row in result.operands))
                self.assertEqual(result.coverage['timer_instructions'], 0)
        for root in ('Missing', '0', 'T[Index]'):
            with self.subTest(root=root):
                _, _, result = analyze(f'TON({root},?,0);', tag('T'))
                self.assertEqual(result.instructions[0]['status'], 'classified')
                self.assertEqual(result.operands[0]['role'], 'read_write')
                self.assertEqual(result.coverage['timer_instructions'], 1)
                self.assertEqual(result.coverage['access_gap_operands'], 1)
                self.assertEqual(result.roots, [])
                self.assertEqual(result.status, 'partial')

    def test_copy_length_is_read_and_literal_destinations_never_supply_write_evidence(self) -> None:
        _, _, result = analyze('COP(A[0],A[1],Length)CPS(A,A,0)RES(42)COP(1,2,3);',
                               tag('A') + tag('Length'))
        self.assertEqual([row['role'] for row in result.operands],
                         ['read', 'write', 'read', 'read', 'write', 'read',
                          'write', 'read', 'write', 'read'])
        self.assertEqual(result.operands[2]['binding_status'], 'root_bound')
        self.assertEqual(result.coverage['access_gap_operands'], 2)
        self.assertEqual(result.coverage['bound_by_role']['write'], 2)
        self.assertEqual(result.coverage['timer_instructions'], 0)
        self.assertEqual(len(result.roots), 2)
        self.assertNotIn('edges', result.to_dict())
        self.assertNotIn('ranges', result.to_dict())
        for text in ('RES()', 'RES(A,A)', 'COP(A,B)', 'CPS(A,,1)'):
            with self.subTest(text=text):
                _, _, invalid = analyze(text + ';', tag('A') + tag('B'))
                self.assertTrue(all(row['role'] == 'unknown' for row in invalid.operands))
                self.assertEqual(invalid.status, 'partial')

    def test_canonical_replay_rejects_forged_timer_kinds_roles_and_metadata(self) -> None:
        inventory, references, result = analyze('TON(T,?,0);', tag('T'))
        mutations = [
            lambda r: r.coverage['timer_pseudo_operands_by_kind'].update(placeholder=2, integer_literal=0),
            lambda r: r.coverage.update(timer_instructions=True),
            lambda r: r.coverage.update(timer_pseudo_operands_by_kind=r.coverage),
            lambda r: r.operands[1].update(reason='catalogued_slot'),
            lambda r: r.operands[2].update(role='read'),
            lambda r: vars(r).update(initialization_analysis='complete'),
            lambda r: vars(r).update(schema_version=1),
        ]
        for mutate in mutations:
            candidate = deepcopy(result)
            mutate(candidate)
            with self.subTest(mutation=mutate), self.assertRaises(AccessError):
                validate_access(inventory, references, candidate)

    def test_zero_argument_unknown_survives_and_empty_program_is_complete(self) -> None:
        _, _, result = analyze('AFI();')
        self.assertEqual(result.coverage['instructions_total'], 1)
        self.assertEqual(result.instructions[0]['operand_ids'], [])
        self.assertEqual(result.operands, [])
        self.assertEqual(result.status, 'partial')
        _, _, empty = analyze(';')
        self.assertEqual(empty.instructions, [])
        self.assertEqual(empty.status, 'complete')

    def test_unparsed_rung_marks_partial_without_inventing_instructions(self) -> None:
        _, _, result = analyze('XIC(A', tag('A'))
        self.assertEqual(result.coverage['source_rungs'], 1)
        self.assertEqual(result.coverage['unparsed_rungs'], 1)
        self.assertEqual(result.instructions, [])
        self.assertEqual(result.status, 'partial')

    def test_canonical_validation_rejects_forged_reference_and_every_access_layer(self) -> None:
        inventory, references, result = analyze('XIC(A)MOV(A,B);', tag('A') + tag('B'))
        bad_references = deepcopy(references)
        bad_references.operands[0]['target_id'] = references.operands[-1]['target_id']
        with self.assertRaises(AccessError):
            analyze_access(inventory, bad_references)
        mutations = [
            lambda r: r.snapshot.update(size_bytes=True),
            lambda r: r.instructions[0].update(opcode='PRIVATE_SENTINEL'),
            lambda r: r.operands[0].update(role='write'),
            lambda r: r.operands[0].update(argument_index=False),
            lambda r: r.operands[0].update(extra='PRIVATE_SENTINEL'),
            lambda r: r.coverage.update(extra='PRIVATE_SENTINEL'),
            lambda r: r.coverage.update(instructions_total=True),
            lambda r: r.roots[0]['read_operand_ids'].append(r.operands[-1]['id']),
            lambda r: r.instructions.append(r.instructions),
            lambda r: r.coverage.update(operands_by_role=r.coverage),
            lambda r: vars(r).update(extra='PRIVATE_SENTINEL'),
        ]
        for mutate in mutations:
            candidate = deepcopy(result)
            mutate(candidate)
            with self.subTest(mutation=mutate), self.assertRaisesRegex(AccessError, '^Access records'):
                validate_access(inventory, references, candidate)
        with self.assertRaises(AccessError):
            validate_access(inventory, references, result.to_dict())

    def test_render_is_bounded_and_rejects_cycles_types_and_extra_fields(self) -> None:
        inventory, references, result = analyze('XIC(A);', tag('A'))
        self.assertEqual(json.loads(render_access_json(result)), result.to_dict())
        with self.assertRaises(FrozenInstanceError):
            result.status = 'partial'
        for limit in ('MAX_OPERANDS', 'MAX_INSTRUCTIONS', 'MAX_ACCESS_BYTES'):
            with self.subTest(limit=limit), patch(f'plc_workbench.access.{limit}', 0):
                with self.assertRaises(AccessError):
                    analyze_access(inventory, references)
        for bad_value in (object(), True, ..., {'cycle': None}):
            candidate = deepcopy(result)
            if type(bad_value) is dict:
                bad_value['cycle'] = bad_value
            candidate.coverage['bad'] = bad_value
            with self.subTest(value=type(bad_value)), self.assertRaises(AccessError):
                render_access_json(candidate)
        with patch('plc_workbench.access.MAX_ACCESS_BYTES', 100):
            with self.assertRaises(AccessError):
                render_access_json(result)


if __name__ == '__main__':
    unittest.main()
