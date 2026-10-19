"""Invented ladders exercise occurrence-preserving, bounded condition graphs."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from itertools import product
import json
import unittest
from unittest.mock import patch

from plc_workbench.conditions import (
    PASSTHROUGH_OPCODES, ConditionError, analyze_conditions, render_conditions_json, validate_conditions,
)
from plc_workbench.relationships import render_relationships_json
from test_relationships import capture as capture_relationships, tag


def capture(texts=('XIC(A)OTE(B);',), *, schema_version=1, **kwargs):
    inputs = capture_relationships(texts, **kwargs)
    return (*inputs, analyze_conditions(*inputs, schema_version=schema_version))


PASS_EXAMPLES = (
    'ABS(A,B)', 'ADD(A,1,B)', 'CLR(A)', 'COP(A,B,1)', 'CPS(A,B,1)',
    'CPT(B,A+1)', 'CTU(A,?,?)', 'DIV(A,1,B)', 'LN(A,B)', 'MOV(A,B)',
    'MUL(A,1,B)', 'OSF(A,B)', 'RES(A)', 'RTO(A,?,?)', 'SQR(A,B)',
    'SUB(A,1,B)', 'TON(A,?,?)',
)


class ConditionTransferTests(unittest.TestCase):
    def test_explicit_version_preserves_old_default_and_node_count(self) -> None:
        inputs = capture(tuple(f'{block}OTE(D);' for block in PASS_EXAMPLES))
        legacy = render_conditions_json(inputs[-1])
        self.assertEqual(legacy, render_conditions_json(analyze_conditions(*inputs[:-1], schema_version=1)))
        result = analyze_conditions(*inputs[:-1], schema_version=2)
        self.assertEqual((result.schema_version, result.analyzer_version), (2, 'condition-analysis-2'))
        self.assertEqual(len(result.nodes), len(inputs[-1].nodes))
        self.assertEqual(result.coverage['node_kinds']['pass_through'], len(PASS_EXAMPLES))
        self.assertEqual(result.coverage['node_kinds']['opaque_transfer'], 0)
        self.assertEqual(result.status, 'complete')
        self.assertEqual(set(result.coverage['passthrough_opcodes'].values()), {1})
        self.assertNotIn('passthrough_opcodes', inputs[-1].coverage)
        self.assertTrue(all(o['guard_status'] == 'opaque' for o in inputs[-1].outputs))
        validate_conditions(*inputs[:-1], result)
        self.assertEqual(legacy, render_conditions_json(inputs[-1]))

    def test_each_admitted_opcode_retains_context_and_rejects_bad_signature(self) -> None:
        self.assertEqual({b.split('(')[0] for b in PASS_EXAMPLES}, PASSTHROUGH_OPCODES)
        for block in PASS_EXAMPLES:
            with self.subTest(block=block):
                inputs = capture((f'XIC(A){block}OTE(D);',), schema_version=2)
                result = inputs[-1]
                transfer = next(n for n in result.nodes if n['kind'] == 'pass_through')
                source = inputs[3].instructions[1]
                self.assertEqual(transfer['instruction_id'], source['id'])
                self.assertEqual(transfer['operand_ids'], source['operand_ids'])
                self.assertEqual(transfer['child_ids'], [result.nodes[2]['id']])
                self.assertEqual(transfer['reason'], 'documented_normal_scan_passthrough')
                self.assertEqual(result.outputs[0]['guard_id'], transfer['id'])
                self.assertFalse(transfer['has_opaque'])
                bad = capture((f'{block[:-1]},Extra)OTE(D);',), schema_version=2)[-1]
                self.assertEqual(bad.coverage['node_kinds']['pass_through'], 0)
                self.assertEqual(bad.coverage['opaque_reasons']['signature_unresolved'], 1)
                self.assertEqual(bad.outputs[0]['guard_status'], 'opaque')

    def test_nested_passes_preserve_both_boolean_states_and_empty_bypass(self) -> None:
        result = capture(('XIC(A)[MOV(A,B)[XIO(C)TON(D,?,?),],OSF(A,B)]OTE(D);',), schema_version=2)[-1]
        predicates = [n['id'] for n in result.nodes if n['kind'] == 'predicate']
        for entry, first, second in product((False, True), repeat=3):
            outcomes = dict(zip(predicates, (first, second), strict=True))
            values = {}
            for n in result.nodes:
                kind = n['kind']
                if kind == 'entry':
                    value = entry
                elif kind == 'predicate':
                    value = outcomes[n['id']]
                elif kind == 'all':
                    value = all(values[c] for c in n['child_ids'])
                elif kind == 'any':
                    value = any(values[c] for c in n['child_ids'])
                elif kind == 'pass_through':
                    value = values[n['child_ids'][0]]
                else:
                    self.fail('Unexpected opaque transfer')
                values[n['id']] = value
            self.assertEqual(values[result.outputs[0]['guard_id']], entry and first)

    def test_noncoil_context_is_retained_without_any_output(self) -> None:
        result = capture(('XIC(A)MOV(A,B)TON(D,?,?);',), schema_version=2)[-1]
        self.assertEqual(result.outputs, [])
        self.assertEqual(result.rungs[0]['exit_id'], result.nodes[-1]['id'])
        self.assertEqual(result.coverage['node_kinds']['pass_through'], 2)

    def test_action_data_gaps_are_separate_from_boolean_guard_quality(self) -> None:
        inputs = capture(('MOV(Missing,OtherMissing)CPT(B,Missing+1)TON(Missing,?,?)OTE(D);',), schema_version=2)
        result = inputs[-1]
        self.assertTrue(any(o['binding_status'] != 'root_bound' for o in inputs[3].operands))
        self.assertEqual(result.coverage['binding_gap_predicates'], 0)
        self.assertEqual(result.outputs[0]['guard_status'], 'modeled')
        self.assertEqual(result.status, 'complete')  # condition scope only
        bad = capture(('TON(A,Missing,?)OTE(D);',), schema_version=2)[-1]
        self.assertEqual(bad.outputs[0]['guard_status'], 'opaque')

    def test_unknown_ancestry_and_later_unknown_are_not_erased(self) -> None:
        result = capture(('OTE(A)MYSTERY(A)MOV(A,B)OTE(D);',), schema_version=2)[-1]
        self.assertEqual([o['guard_status'] for o in result.outputs], ['modeled', 'opaque'])
        self.assertTrue(next(n for n in result.nodes if n['kind'] == 'pass_through')['has_opaque'])
        for block in ('ONS(A)', 'OSR(A,B)', 'TOF(A,?,?)', 'CTD(A,?,?)', 'GSV(WallClockTime,,DateTime,A)',
                      'MSG(A)', 'MVM(A,1,B)', 'SWPB(A,REVERSE,B)', 'JSR(R,0)', 'RET()', 'SBR()',
                      'SFR(R,A)', 'PID(A,B,C,D,0,0,0)', 'FAL(A,1,0,ALL,B,A+1)'):
            with self.subTest(block=block):
                candidate = capture((f'{block}OTE(D);',), schema_version=2)[-1]
                self.assertEqual(candidate.coverage['node_kinds']['pass_through'], 0)
                self.assertEqual(candidate.outputs[0]['guard_status'], 'opaque')

    def test_intervening_move_keeps_distinct_same_address_reads(self) -> None:
        result = capture(('XIC(A)MOV(B,A)XIC(A)OTE(D);',), schema_version=2)[-1]
        predicates = [n for n in result.nodes if n['kind'] == 'predicate']
        self.assertNotEqual(predicates[0]['operand_ids'], predicates[1]['operand_ids'])
        self.assertEqual([n['kind'] for n in result.nodes], ['entry', 'predicate', 'all', 'pass_through', 'predicate', 'all'])

    def test_version_and_forged_transfer_cannot_bypass_replay(self) -> None:
        inputs = capture(('MOV(A,B)OTE(D);',), schema_version=2)
        for version in (True, 0, 4, '2', 2.0):
            with self.subTest(version=version), self.assertRaises(ConditionError):
                analyze_conditions(*inputs[:-1], schema_version=version)
        for mutate in (lambda r: r.nodes[1].update(reason=None),
                       lambda r: r.nodes[1].update(child_ids=[]),
                       lambda r: r.nodes[1].update(has_binding_gap=True),
                       lambda r: r.nodes[1].update(kind='opaque_transfer'),
                       lambda r: r.coverage['passthrough_opcodes'].update(MOV=0)):
            candidate = deepcopy(inputs[-1])
            mutate(candidate)
            with self.assertRaises(ConditionError):
                validate_conditions(*inputs[:-1], candidate)
        with self.assertRaises(ConditionError):
            validate_conditions(*inputs[:-1], replace(inputs[-1], schema_version=1, analyzer_version='condition-analysis-1'))

    def test_long_branch_chains_keep_linear_space(self) -> None:
        result = capture((''.join('[MOV(A,B),TON(D,?,?)]' for _ in range(120)) + 'OTE(C);',), schema_version=2)[-1]
        self.assertEqual(len(result.nodes), 361)
        self.assertEqual(sum(len(n['child_ids']) for n in result.nodes), 480)
        self.assertLess(len(render_conditions_json(result)), 300_000)


class ConditionTests(unittest.TestCase):
    def test_series_keeps_entry_and_each_instruction_predicate(self) -> None:
        inputs = capture(('XIC(A)XIO(B)OTE(D);',))
        result = inputs[-1]
        self.assertEqual([n['kind'] for n in result.nodes], ['entry', 'predicate', 'all', 'predicate', 'all'])
        entry, first, first_all, second, second_all = result.nodes
        self.assertEqual(first_all['child_ids'], [entry['id'], first['id']])
        self.assertEqual(second_all['child_ids'], [first_all['id'], second['id']])
        self.assertNotEqual(first['instruction_id'], second['instruction_id'])
        self.assertEqual(result.outputs[0]['guard_id'], second_all['id'])
        self.assertEqual(result.outputs[0]['guard_status'], 'modeled')
        self.assertEqual(result.rungs[0]['entry_id'], entry['id'])
        self.assertEqual(result.rungs[0]['exit_id'], second_all['id'])
        self.assertEqual(result.evaluation_scope, 'normal_scan_only')
        self.assertEqual(result.status, 'complete')
        validate_conditions(*inputs)

    def test_entry_is_explicit_even_for_unguarded_output_and_empty_rung(self) -> None:
        result = capture(('OTE(A);', ';'))[-1]
        self.assertEqual([n['kind'] for n in result.nodes], ['entry', 'entry'])
        self.assertEqual(result.outputs[0]['guard_id'], result.rungs[0]['entry_id'])
        self.assertEqual(result.rungs[0]['exit_id'], result.rungs[0]['entry_id'])
        self.assertEqual(result.rungs[1]['exit_id'], result.rungs[1]['entry_id'])
        self.assertFalse(any('value' in n for n in result.nodes))

    def test_branch_joins_retain_shared_incoming_and_empty_bypass(self) -> None:
        result = capture(('XIC(A)[XIO(B),]OTE(D);',))[-1]
        by_id = {n['id']: n for n in result.nodes}
        join = next(n for n in result.nodes if n['kind'] == 'any')
        left, bypass = [by_id[x] for x in join['child_ids']]
        self.assertEqual(left['child_ids'][0], bypass['id'])
        self.assertEqual(result.outputs[0]['guard_id'], join['id'])
        self.assertEqual((result.coverage['branch_joins'], result.coverage['branch_legs']), (1, 2))
        self.assertEqual(result.coverage['outputs_with_branches'], 1)

    def test_empty_duplicate_legs_are_never_simplified(self) -> None:
        result = capture(('[,,]OTE(A);',))[-1]
        entry, join = result.nodes
        self.assertEqual(join['child_ids'], [entry['id']] * 3)
        self.assertEqual(result.outputs[0]['guard_id'], join['id'])

    def test_nested_branches_form_topological_graph_without_distributing(self) -> None:
        result = capture(('XIC(A)[XIC(B)[XIO(C),],XIC(D)]OTE(A);',))[-1]
        seen: set[str] = set()
        for row in result.nodes:
            self.assertTrue(set(row['child_ids']) <= seen)
            seen.add(row['id'])
        self.assertEqual(result.coverage['node_kinds'], {'entry': 1, 'predicate': 4, 'all': 4, 'any': 2, 'opaque_transfer': 0})
        self.assertEqual(result.coverage['branch_legs'], 4)
        self.assertEqual(len(result.nodes), 11)

    def test_outputs_inside_legs_capture_only_their_own_prefix(self) -> None:
        result = capture(('[XIC(A)OTE(B),XIO(C)OTL(D)]OTU(A);',))[-1]
        by_id = {n['id']: n for n in result.nodes}
        first, second, after = result.outputs
        self.assertEqual(by_id[first['guard_id']]['kind'], 'all')
        self.assertEqual(by_id[second['guard_id']]['kind'], 'all')
        self.assertNotEqual(first['guard_id'], second['guard_id'])
        self.assertEqual(by_id[after['guard_id']]['child_ids'], [first['guard_id'], second['guard_id']])
        self.assertEqual(result.rungs[0]['output_ids'], [o['id'] for o in result.outputs])

    def test_nested_guard_truth_tables_use_distinct_occurrence_outcomes(self) -> None:
        cases = (
            ('XIC(A)[XIC(A)[XIO(B),XIC(C)]OTE(B),XIO(A)OTL(C)]OTU(D);',
             lambda entry, p: [entry and p[0] and p[1] and (p[2] or p[3]),
                               entry and p[0] and p[4],
                               (entry and p[0] and p[1] and (p[2] or p[3])) or (entry and p[0] and p[4])]),
            ('XIC(A)[XIO(A),]OTE(D);',
             lambda entry, p: [(entry and p[0] and p[1]) or (entry and p[0])]),
        )
        for text, expected in cases:
            result = capture((text,))[-1]
            predicate_ids = [n['id'] for n in result.nodes if n['kind'] == 'predicate']
            for entry, *predicates in product((False, True), repeat=len(predicate_ids) + 1):
                # Outcomes belong to each source occurrence, even where the
                # same address is read repeatedly or written between reads.
                outcomes = dict(zip(predicate_ids, predicates, strict=True))
                values: dict[str, bool] = {}
                for node in result.nodes:
                    kind = node['kind']
                    if kind == 'entry':
                        value = entry
                    elif kind == 'predicate':
                        value = outcomes[node['id']]
                    elif kind == 'all':
                        value = all(values[c] for c in node['child_ids'])
                    elif kind == 'any':
                        value = any(values[c] for c in node['child_ids'])
                    else:
                        self.fail('Opaque transfers must not be truth-table evaluated.')
                    values[node['id']] = value
                with self.subTest(text=text, entry=entry, predicates=predicates):
                    self.assertEqual([values[o['guard_id']] for o in result.outputs], expected(entry, predicates))

    def test_coils_keep_distinct_normal_scan_actions_and_pass_condition(self) -> None:
        result = capture(('XIC(A)OTE(B)OTL(C)OTU(D);',))[-1]
        self.assertEqual([o['action'] for o in result.outputs], ['assign_condition', 'set_if_true', 'clear_if_true'])
        self.assertEqual(len({o['guard_id'] for o in result.outputs}), 1)
        self.assertEqual(result.coverage['action_statuses'], {'recognized': 3, 'unresolved': 0})
        self.assertEqual(result.coverage['output_addresses'], 3)

    def test_reads_of_same_address_separated_by_write_remain_distinct(self) -> None:
        inputs = capture(('XIC(A)OTE(A)XIC(A)OTE(B);',))
        result = inputs[-1]
        predicates = [n for n in result.nodes if n['kind'] == 'predicate']
        self.assertNotEqual(predicates[0]['operand_ids'], predicates[1]['operand_ids'])
        self.assertNotEqual(predicates[0]['id'], predicates[1]['id'])
        self.assertNotEqual(result.outputs[0]['guard_id'], result.outputs[1]['guard_id'])
        self.assertEqual(len([a for a in inputs[-2].addresses if len(a['read_operand_ids']) == 2]), 1)

    def test_all_selected_predicates_keep_source_operator_and_operand_slots(self) -> None:
        text = 'XIC(A)XIO(B)EQU(A,B)NEQ(A,B)LES(A,1)LEQ(A,1)GRT(A,1)GEQ(A,1)LIM(10,A,1)OTE(D);'
        inputs = capture((text,))
        result = inputs[-1]
        self.assertEqual(set(result.coverage['predicate_opcodes'].values()), {1})
        predicates = [n for n in result.nodes if n['kind'] == 'predicate']
        self.assertEqual(len(predicates), 9)
        self.assertEqual(len(predicates[-1]['operand_ids']), 3)
        self.assertEqual(result.coverage['binding_gap_predicates'], 0)
        self.assertFalse(any('operator' in n for n in result.nodes))

    def test_unsupported_instruction_is_transfer_not_and_unknown(self) -> None:
        result = capture(('XIC(A)Unknown(B)XIO(C)OTE(D);',))[-1]
        opaque = next(n for n in result.nodes if n['kind'] == 'opaque_transfer')
        self.assertEqual(len(opaque['child_ids']), 1)
        self.assertEqual(opaque['reason'], 'unsupported_condition_behavior')
        self.assertTrue(opaque['has_opaque'])
        self.assertEqual(result.outputs[0]['guard_status'], 'opaque')
        self.assertEqual(result.status, 'partial')

    def test_ordinary_calculations_timers_and_control_are_opaque(self) -> None:
        for block in ('MOV(A,B)', 'ADD(A,1,B)', 'CPT(A,B+1)', 'TON(T,?,?)', 'JMP(L)', 'ONS(A)', 'PID(A,B,C,D,0,0,0)'):
            with self.subTest(block=block):
                result = capture((f'{block}OTE(D);',))[-1]
                self.assertEqual(result.outputs[0]['guard_status'], 'opaque')
                self.assertEqual(result.coverage['opaque_reasons']['unsupported_condition_behavior'], 1)

    def test_invalid_predicate_and_output_signatures_are_explicit(self) -> None:
        result = capture(('XIC(A,B)OTE(C,D)OTE(A);',))[-1]
        first, second = result.outputs
        self.assertEqual(first['action'], 'unresolved')
        self.assertEqual(first['target_status'], 'signature_unresolved')
        self.assertIsNone(first['target_operand_id'])
        self.assertIsNone(first['target_address_id'])
        self.assertEqual(second['guard_status'], 'opaque')
        self.assertEqual(result.coverage['opaque_reasons']['signature_unresolved'], 2)
        self.assertEqual(result.coverage['predicate_opcodes']['XIC'], 0)

    def test_invalid_coil_records_incoming_guard_before_opaque_transfer(self) -> None:
        result = capture(('OTE(A,B)OTE(C);',))[-1]
        self.assertEqual([o['guard_status'] for o in result.outputs], ['modeled', 'opaque'])
        self.assertEqual([n['kind'] for n in result.nodes], ['entry', 'opaque_transfer'])

    def test_binding_gaps_propagate_without_guessing_predicate_truth(self) -> None:
        result = capture(('XIC(Missing)EQU(A[Missing],1)OTE(D);',))[-1]
        self.assertEqual(result.coverage['binding_gap_predicates'], 2)
        self.assertEqual(result.outputs[0]['guard_status'], 'binding_gaps')
        self.assertEqual(result.outputs[0]['action'], 'assign_condition')

    def test_literal_and_system_flag_predicates_are_not_address_gaps(self) -> None:
        result = capture(('EQU(1,2)XIC(S:FS)OTE(A);',))[-1]
        self.assertEqual(result.coverage['binding_gap_predicates'], 0)
        self.assertEqual(result.outputs[0]['guard_status'], 'modeled')

    def test_opaque_wins_over_binding_gap_and_branches_keep_both_flags(self) -> None:
        result = capture(('[XIC(Missing),Unknown(A)]OTE(B);',))[-1]
        guard = next(n for n in result.nodes if n['id'] == result.outputs[0]['guard_id'])
        self.assertTrue(guard['has_opaque'])
        self.assertTrue(guard['has_binding_gap'])
        self.assertTrue(guard['has_branch'])
        self.assertEqual(result.outputs[0]['guard_status'], 'opaque')

    def test_exact_alias_target_identity_and_invalid_composed_suffix(self) -> None:
        tags = tag('A') + tag('B') + tag('Alias', 'B.Member') + tag('Bit', 'A.1')
        inputs = capture(('XIC(Bit.Member)OTE(Bit.Member);', 'OTE(Alias)OTL(B.Member)OTU(Missing);'), tags=tags)
        before = render_relationships_json(inputs[-2])
        result = inputs[-1]
        self.assertEqual([o['target_status'] for o in result.outputs], ['identity_gap', 'exact_address', 'exact_address', 'unbound'])
        self.assertEqual(result.outputs[0]['guard_status'], 'binding_gaps')
        self.assertEqual(result.outputs[1]['target_address_id'], result.outputs[2]['target_address_id'])
        self.assertEqual(result.coverage['output_addresses'], 1)
        self.assertEqual(before, render_relationships_json(inputs[-2]))

    def test_predicate_root_binding_does_not_claim_member_type_validation(self) -> None:
        result = capture(('XIC(A.Unverified.Member[999])OTE(B.Unverified);',))[-1]
        self.assertEqual(result.outputs[0]['guard_status'], 'modeled')
        self.assertEqual(result.outputs[0]['target_status'], 'exact_address')
        self.assertEqual(result.execution_analysis, 'not_implemented')
        self.assertEqual(result.engineering_review, 'unreviewed')

    def test_unparsed_rung_has_no_invented_entry_or_output(self) -> None:
        result = capture(('XIC(A',))[-1]
        self.assertEqual(result.nodes, [])
        self.assertEqual(result.outputs, [])
        self.assertEqual(result.rungs[0]['status'], 'unparsed')
        self.assertIsNone(result.rungs[0]['entry_id'])
        self.assertIsNone(result.rungs[0]['exit_id'])
        self.assertEqual(result.status, 'partial')

    def test_rung_entry_resets_and_no_graph_edge_crosses_rungs(self) -> None:
        result = capture(('Unknown(A)OTE(B);', 'XIC(A)OTE(B);'))[-1]
        self.assertEqual([o['guard_status'] for o in result.outputs], ['opaque', 'modeled'])
        by_id = {n['id']: n for n in result.nodes}
        self.assertTrue(all(by_id[c]['rung_id'] == n['rung_id'] for n in result.nodes for c in n['child_ids']))

    def test_source_and_prior_companion_forgery_fail_before_derivation(self) -> None:
        inputs = capture()
        for index in range(1, 7):
            forged = list(deepcopy(inputs[:-1]))
            if index == 1:
                forged[index].rungs[0] = replace(forged[index].rungs[0], text='SecretSource')
            elif index == 2:
                forged[index].operands[0]['target_id'] = 'SecretSource'
            else:
                forged[index].coverage['source_rungs'] = 999
            with self.subTest(index=index), patch('plc_workbench.conditions._derive') as derive, self.assertRaises(ConditionError) as raised:
                analyze_conditions(*forged)
            derive.assert_not_called()
            self.assertNotIn('SecretSource', str(raised.exception))

    def test_graph_mutations_cannot_pass_canonical_validation(self) -> None:
        inputs = capture(('[XIC(A),XIO(B)]OTE(C)OTL(D);',))
        mutations = (
            lambda r: r.nodes.reverse(),
            lambda r: r.nodes[-1]['child_ids'].reverse(),
            lambda r: r.nodes[1].update(has_binding_gap=True),
            lambda r: r.outputs[0].update(action='clear_if_true'),
            lambda r: r.outputs[0].update(target_address_id=r.outputs[1]['target_address_id']),
            lambda r: r.rungs[0].update(exit_id=r.rungs[0]['entry_id']),
            lambda r: r.coverage.update(outputs_total=0),
        )
        for mutate in mutations:
            candidate = deepcopy(inputs[-1])
            mutate(candidate)
            with self.subTest(mutation=mutate), self.assertRaises(ConditionError):
                validate_conditions(*inputs[:-1], candidate)

    def test_snapshot_change_rekeys_graph_and_output_ids(self) -> None:
        one = capture()[-1]
        two = capture(rung_xml='<Rung Number="0" Type="N"><Text>XIC(A)OTE(B);</Text><Comment>changed</Comment></Rung>')[-1]
        self.assertNotEqual(one.nodes[0]['id'], two.nodes[0]['id'])
        self.assertNotEqual(one.outputs[0]['id'], two.outputs[0]['id'])

    def test_native_renderer_does_not_invoke_custom_container_hooks(self) -> None:
        class Hostile:
            def __deepcopy__(self, memo):
                raise AssertionError('Custom hook ran')
        class HostileList(list):
            def __iter__(self):
                raise AssertionError('Custom hook ran')
        result = capture()[-1]
        for value in (Hostile(), HostileList(), {Hostile(): 1}, [Hostile()]):
            with self.subTest(value=type(value)), self.assertRaises(ConditionError):
                render_conditions_json(replace(result, nodes=value))
        cyclic = []
        cyclic.append(cyclic)
        with self.assertRaises(ConditionError):
            render_conditions_json(replace(result, nodes=cyclic))

    def test_incremental_record_id_and_byte_limits_are_enforced(self) -> None:
        inputs = capture_relationships()
        for name in ('MAX_RECORDS', 'MAX_EVIDENCE_IDS', 'MAX_CONDITION_BYTES'):
            with self.subTest(name=name), patch('plc_workbench.conditions.' + name, 1), self.assertRaises(ConditionError):
                analyze_conditions(*inputs)
        result = analyze_conditions(*inputs)
        rendered = render_conditions_json(result)
        self.assertEqual(json.loads(rendered), result.to_dict())
        with patch('plc_workbench.conditions.MAX_CONDITION_BYTES', len(rendered) - 1), self.assertRaises(ConditionError):
            render_conditions_json(result)

    def test_long_sequence_and_branch_product_stay_linear(self) -> None:
        count = 120
        result = capture((''.join('[XIC(A),XIO(B)]' for _ in range(count)) + 'OTE(C);',))[-1]
        self.assertEqual(len(result.nodes), 1 + 5 * count)
        self.assertEqual(sum(len(n['child_ids']) for n in result.nodes), 6 * count)
        self.assertEqual(result.coverage['branch_joins'], count)
        self.assertEqual(len(result.outputs), 1)
        self.assertLess(len(render_conditions_json(result)), 500_000)


if __name__ == '__main__':
    unittest.main()
