"""Invented inputs challenge exact identity, ordering and pattern boundaries."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import render_access_json
from plc_workbench.relationships import (
    RelationshipError, analyze_relationships, render_relationships_json, validate_relationships,
)
from test_rung_analysis import capture as capture_rungs


def capture(texts=('MOV(A,B)ADD(B,1,C);',), **kwargs):
    inputs = capture_rungs(texts, **kwargs)
    return (*inputs, analyze_relationships(*inputs))


def tag(name: str, alias: str | None = None) -> str:
    return (f'<Tag Name="{name}" TagType="Alias" AliasFor="{alias}"/>' if alias else
            f'<Tag Name="{name}" TagType="Base" DataType="DINT"/>')


class RelationshipTests(unittest.TestCase):
    def test_exact_index_has_separate_roles_and_source_order(self) -> None:
        inputs = capture(('MOV(A,B)CPT(C,B+A+A);', 'OTE(B)ONS(D);'))
        result = inputs[-1]
        names = {e.id: e.name for e in inputs[1].entities}
        self.assertEqual([names[row['target_id']] for row in result.addresses], ['A', 'B', 'C', 'D'])
        a, b, c, d = result.addresses
        self.assertEqual((len(a['read_operand_ids']), len(a['expression_use_ids'])), (1, 2))
        self.assertEqual(b['profile'], 'read_and_write')
        self.assertEqual(c['profile'], 'write_only')
        self.assertEqual(d['profile'], 'read_and_write')
        self.assertEqual(len(b['rung_ids']), 2)
        self.assertEqual(result.coverage['cross_rung_addresses'], 1)
        self.assertEqual(result.coverage['multiple_writer_addresses'], 1)
        self.assertEqual(result.coverage['indexed_expression_uses'], 3)
        self.assertEqual(result.coverage['indexed_operands_by_role'], {'read': 1, 'write': 3, 'read_write': 1, 'unknown': 0})

    def test_alias_and_direct_spelling_share_final_identity(self) -> None:
        tags = tag('A') + tag('B') + tag('Alias', 'A.Member')
        *_, result = capture(('MOV(B,Alias)ADD(A.Member,Alias,B);',), tags=tags)
        self.assertEqual(len(result.addresses), 2)
        member = next(a for a in result.addresses if a['suffix'] == '.Member')
        self.assertEqual(len(member['read_operand_ids']), 2)
        self.assertEqual(len(member['write_operand_ids']), 1)
        self.assertEqual(len(result.local_links), 2)

    def test_suffix_case_spacing_and_leading_zeros_stay_distinct(self) -> None:
        *_, result = capture(('MOV(A.X,B)MOV(A.x,B)MOV(A[1],B)MOV(A[01],B)MOV(A[ 1 ],B);',))
        suffixes = [a['suffix'] for a in result.addresses]
        self.assertEqual(suffixes, ['.X', '', '.x', '[1]', '[01]', '[ 1 ]'])

    def test_composed_invalid_suffix_is_rejected_without_mutating_access(self) -> None:
        tags = tag('A') + tag('B') + tag('Bit', 'A.1')
        inputs = capture(('MOV(Bit.Member,B)CPT(B,Bit.Member+B);',), tags=tags)
        access, result = inputs[3], inputs[-1]
        before = render_access_json(access)
        self.assertEqual([g['kind'] for g in result.identity_gaps], ['operand', 'expression'])
        self.assertTrue(all(g['reason'] == 'expanded_suffix_invalid' for g in result.identity_gaps))
        self.assertEqual(result.coverage['rejected_operands_by_role']['read'], 1)
        self.assertEqual(result.coverage['rejected_expression_uses'], 1)
        self.assertEqual(result.coverage['pattern_skips']['invalid_expanded_suffix'], 1)
        self.assertEqual(result.local_links, [])
        self.assertEqual(before, render_access_json(access))
        self.assertTrue(any(o['binding_status'] == 'root_bound' and o['suffix'] == '.1.Member' for o in access.operands))

    def test_scope_identity_uses_final_target_not_tag_name(self) -> None:
        # Program-local A shadows controller A; aliases retain their own scope.
        from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
        from plc_workbench.references import analyze_references
        from plc_workbench.calculations import analyze_calculations
        from plc_workbench.access import analyze_access
        from plc_workbench.rung_analysis import analyze_rungs
        xml = ('<RSLogix5000Content><Controller Name="C"><Tags>' + tag('A') + '</Tags><Programs>'
               '<Program Name="P"><Tags>' + tag('A') + '</Tags><Routines><Routine Name="R" Type="RLL">'
               '<RLLContent><Rung Number="0" Type="N"><Text>OTE(A);</Text></Rung></RLLContent></Routine></Routines></Program>'
               '<Program Name="Q"><Routines><Routine Name="R" Type="RLL"><RLLContent>'
               '<Rung Number="0" Type="N"><Text>OTE(A);</Text></Rung></RLLContent></Routine></Routines></Program>'
               '</Programs></Controller></RSLogix5000Content>')
        snapshot = snapshot_from_bytes(xml.encode())
        inventory = analyze_snapshot(snapshot)
        references = analyze_references(inventory)
        calculations = analyze_calculations(snapshot, inventory, references)
        access = analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
        rung_analysis = analyze_rungs(snapshot, inventory, references, access, calculations)
        result = analyze_relationships(snapshot, inventory, references, access, calculations, rung_analysis)
        self.assertEqual(len(result.addresses), 2)
        self.assertNotEqual(result.addresses[0]['target_id'], result.addresses[1]['target_id'])
        self.assertEqual(len(result.patterns), 1)
        self.assertEqual(result.coverage['cross_rung_addresses'], 0)

    def test_bound_unknown_roles_index_but_do_not_become_reads_or_writes(self) -> None:
        *_, result = capture(('PID(A,B,C,D,0,0,0);',))
        self.assertEqual(len(result.addresses), 4)
        self.assertEqual(result.coverage['address_profiles']['unknown_only'], 4)
        self.assertEqual(result.coverage['indexed_operands_by_role']['unknown'], 4)
        self.assertEqual(result.coverage['pattern_skips']['unknown_instruction'], 1)
        self.assertEqual(result.local_links, [])

    def test_literal_non_data_and_unknown_unbound_do_not_create_addresses(self) -> None:
        *_, result = capture(('MOV(42,A)TON(T,?,?)JMP(LABEL)Mystery(B);',))
        self.assertEqual(len(result.addresses), 2)
        self.assertEqual(result.coverage['indexed_operands_by_role']['unknown'], 0)
        self.assertEqual(result.identity_gaps, [])

    def test_contiguous_local_chain_links_to_previous_exact_write(self) -> None:
        inputs = capture(('MOV(A,B)ADD(B,1,C)MUL(C,B,D);',))
        result = inputs[-1]
        instruction_ids = [i.id for i in inputs[1].rungs[0].instructions]
        self.assertEqual([(l['producer_instruction_id'], l['consumer_instruction_id']) for l in result.local_links],
                         [(instruction_ids[0], instruction_ids[1]), (instruction_ids[1], instruction_ids[2]),
                          (instruction_ids[0], instruction_ids[2])])
        self.assertEqual(result.coverage['eligible_instructions'], 3)
        self.assertEqual(result.coverage['local_link_rungs'], 1)

    def test_cpt_repeated_leaves_and_self_read_are_distinct(self) -> None:
        inputs = capture(('CPT(A,A+1)MOV(B,A)CPT(A,A+A)ADD(A,1,C);',))
        result = inputs[-1]
        ids = [i.id for i in inputs[1].rungs[0].instructions]
        self.assertEqual(len(result.local_links), 3)
        self.assertEqual([l['read_kind'] for l in result.local_links], ['expression', 'expression', 'operand'])
        self.assertEqual([l['producer_instruction_id'] for l in result.local_links], [ids[1], ids[1], ids[2]])
        self.assertNotEqual(result.local_links[0]['read_id'], result.local_links[1]['read_id'])
        self.assertTrue(all(l['producer_instruction_id'] != l['consumer_instruction_id'] for l in result.local_links))

    def test_latest_write_replaces_previous_writer(self) -> None:
        inputs = capture(('MOV(A,B)CLR(B)ADD(B,1,C);',))
        self.assertEqual(len(inputs[-1].local_links), 1)
        self.assertEqual(inputs[-1].local_links[0]['producer_instruction_id'], inputs[1].rungs[0].instructions[1].id)

    def test_member_root_and_different_member_writes_invalidate_prior_root(self) -> None:
        for text in ('MOV(B,A.Left)MOV(C,A.Right)ADD(A.Left,1,D);',
                     'MOV(B,A.Left)MOV(C,A)ADD(A.Left,1,D);',
                     'MOV(B,A)MOV(C,A.Left)ADD(A,1,D);'):
            with self.subTest(text=text):
                *_, result = capture((text,))
                self.assertEqual(result.local_links, [])

    def test_barriers_reset_whole_segment_and_later_segment_resumes(self) -> None:
        barriers = ('XIC(A)', 'COP(A,C,1)', 'JMP(L)', 'PID(A,B,C,D,0,0,0)', 'Mystery(A)',
                    'MOV(Missing,A)', 'ADD(A,1)', 'CPT(A,A+)', 'MOV(S:FS,A)')
        for barrier in barriers:
            with self.subTest(barrier=barrier):
                inputs = capture((f'MOV(A,B){barrier}ADD(B,1,C)MOV(C,D);',))
                result = inputs[-1]
                self.assertEqual(len(result.local_links), 1)
                self.assertEqual(result.local_links[0]['producer_instruction_id'], inputs[1].rungs[0].instructions[-2].id)
                self.assertEqual(result.coverage['barrier_instructions'], 1)

    def test_branches_including_bypasses_exclude_entire_rung(self) -> None:
        *_, result = capture(('MOV(A,B)[ADD(B,1,C),]MOV(C,D);', 'MOV(A,B)[,]MOV(B,C);'))
        self.assertEqual(result.local_links, [])
        self.assertEqual(result.coverage['excluded_branched_instructions'], 5)
        self.assertEqual(result.coverage['eligible_instructions'], 0)
        self.assertEqual(result.coverage['patterned_rungs'], 2)

    def test_no_links_cross_rungs_even_for_same_address(self) -> None:
        *_, result = capture(('MOV(A,B);', 'MOV(B,C);'))
        self.assertEqual(result.local_links, [])
        self.assertEqual(result.coverage['cross_rung_addresses'], 1)

    def test_patterns_preserve_repeated_addresses_but_rename_roots(self) -> None:
        *_, result = capture(('XIC(A)OTE(A);', 'XIC(B)OTE(B);', 'XIC(A)OTE(B);', 'XIC(C)OTE(D);'))
        self.assertEqual(len(result.patterns), 2)
        ids = [r['pattern_id'] for r in result.rung_patterns]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(ids[2], ids[3])
        self.assertNotEqual(ids[0], ids[2])

    def test_patterns_preserve_same_root_suffix_and_index_spelling(self) -> None:
        *_, result = capture(('XIC(A.Left)OTE(A.Right);', 'XIC(B.Left)OTE(C.Right);',
                              'XIC(A.Left)OTE(A.right);', 'XIC(A[1])OTE(B);', 'XIC(A[01])OTE(B);',
                              'XIC(B.Left)OTE(B.Right);'))
        ids = [row['pattern_id'] for row in result.rung_patterns]
        self.assertEqual(len(set(ids)), 5)
        self.assertEqual(ids[0], ids[5])

    def test_patterns_preserve_branch_order_empty_legs_and_literal_spelling(self) -> None:
        *_, result = capture(('[XIC(A),XIO(B)]OTE(C);', '[XIO(A),XIC(B)]OTE(C);',
                              '[XIC(A),]OTE(C);', '[,XIC(A)]OTE(C);', 'MOV(1,A);', 'MOV(01,B);'))
        self.assertEqual(len(result.patterns), 6)

    def test_cpt_pattern_keeps_ast_operator_function_and_repeated_address(self) -> None:
        *_, result = capture(('CPT(D,A+A);', 'CPT(C,B+B);', 'CPT(D,A+B);', 'CPT(D,A*B);',
                              'CPT(D,A+(B*C));', 'CPT(D,(A+B)*C);', 'CPT(D,ABS(A));', 'CPT(D,LN(A));',
                              'CPT(D,A+1);', 'CPT(D,A+01);'))
        ids = [row['pattern_id'] for row in result.rung_patterns]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(len(set(ids)), 9)

    def test_pattern_gaps_explicitly_partition_every_rung(self) -> None:
        *_, result = capture((';', '[,];', 'XIC(A', 'Unknown(A);', 'MOV(Missing,A);',
                              'CPT(A,B+);', 'CPT(A,Missing+1);', 'XIC(A)OTE(B);'))
        self.assertEqual(result.coverage['pattern_skips'], {'empty': 2, 'unparsed': 1, 'unknown_instruction': 1,
                          'unresolved_address': 2, 'unsupported_expression': 1, 'unknown_role': 0,
                          'invalid_expanded_suffix': 0})
        self.assertEqual((result.coverage['patterned_rungs'], result.coverage['skipped_rungs']), (1, 7))
        self.assertEqual(len(result.rung_patterns), 8)
        self.assertEqual(result.status, 'partial')

    def test_source_authentication_and_forged_companions_are_rejected(self) -> None:
        inputs = capture()
        validate_relationships(*inputs)
        for index in (1, 2, 3, 4, 5):
            forged = list(deepcopy(inputs[:-1]))
            if index == 1:
                forged[index].rungs[0] = replace(forged[index].rungs[0], text='SecretSource')
            elif index == 2:
                forged[index].operands[0]['target_id'] = 'SecretSource'
            else:
                forged[index].coverage['source_rungs'] = 999
            with self.subTest(index=index), self.assertRaises(RelationshipError) as raised:
                analyze_relationships(*forged)
            self.assertNotIn('SecretSource', str(raised.exception))
        forged = replace(inputs[-1], addresses=list(reversed(inputs[-1].addresses)))
        with self.assertRaises(RelationshipError):
            validate_relationships(*inputs[:-1], forged)

    def test_snapshot_identity_changes_address_and_link_ids(self) -> None:
        one = capture()[-1]
        two = capture(rung_xml='<Rung Number="0" Type="N"><Text>MOV(A,B)ADD(B,1,C);</Text><Comment>new</Comment></Rung>')[-1]
        self.assertNotEqual(one.addresses[0]['id'], two.addresses[0]['id'])
        self.assertNotEqual(one.local_links[0]['id'], two.local_links[0]['id'])
        self.assertEqual(one.patterns[0]['id'], two.patterns[0]['id'])

    def test_native_renderer_rejects_custom_objects_without_hooks(self) -> None:
        class Hostile:
            def __deepcopy__(self, memo):
                raise AssertionError('Custom hook ran')
        result = capture()[-1]
        for value in (Hostile(), {Hostile(): 1}, [Hostile()]):
            with self.subTest(value=type(value)), self.assertRaises(RelationshipError):
                render_relationships_json(replace(result, coverage=value))
        cyclic = []
        cyclic.append(cyclic)
        with self.assertRaises(RelationshipError):
            render_relationships_json(replace(result, addresses=cyclic))

    def test_incremental_record_id_suffix_and_byte_limits(self) -> None:
        inputs = capture_rungs(('MOV(A.Member,B)ADD(B,1,C);',))
        for name, maximum in (('MAX_RECORDS', 1), ('MAX_EVIDENCE_IDS', 1),
                              ('MAX_EXPANDED_EVIDENCE_CHARS', 1), ('MAX_RELATIONSHIP_BYTES', 1)):
            with self.subTest(name=name), patch('plc_workbench.relationships.' + name, maximum), self.assertRaises(RelationshipError):
                analyze_relationships(*inputs)
        result = analyze_relationships(*inputs)
        rendered = render_relationships_json(result)
        self.assertEqual(json.loads(rendered), result.to_dict())
        with patch('plc_workbench.relationships.MAX_RELATIONSHIP_BYTES', len(rendered) - 1), self.assertRaises(RelationshipError):
            render_relationships_json(result)

    def test_large_repeated_index_is_linear_and_does_not_build_cartesian_edges(self) -> None:
        count = 250
        *_, result = capture(tuple('MOV(A,B)ADD(B,1,C);' for _ in range(count)))
        self.assertEqual(len(result.addresses), 3)
        self.assertEqual(len(result.local_links), count)
        self.assertEqual(len(result.patterns), 1)
        self.assertEqual(len(result.patterns[0]['rung_ids']), count)
        self.assertEqual(result.coverage['cross_rung_addresses'], 3)
        self.assertEqual(result.coverage['multiple_writer_addresses'], 2)


if __name__ == '__main__':
    unittest.main()
