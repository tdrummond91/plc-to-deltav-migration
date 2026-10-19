"""Invented sources exercise ONS occurrence state without simulating scans."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest
from unittest.mock import patch

from plc_workbench.conditions import (
    STATEFUL_OPCODES, ConditionError, analyze_conditions, render_conditions_json,
    validate_conditions,
)
from test_conditions import PASS_EXAMPLES, capture
from test_relationships import tag


def stateful_capture(texts=('ONS(A)OTE(B);',), **kwargs):
    return capture(texts, schema_version=3, **kwargs)


def evaluate_occurrence_graph(result, *, entry: bool, predicates: list[bool],
                              storage_reads: list[bool]) -> list[bool]:
    """Independent test oracle: supplied reads are distinct occurrence values."""
    predicates_iter, storage_iter = iter(predicates), iter(storage_reads)
    values: dict[str, bool] = {}
    for n in result.nodes:
        kind = n['kind']
        if kind == 'entry':
            value = entry
        elif kind == 'predicate':
            value = next(predicates_iter)
        elif kind == 'all':
            value = all(values[c] for c in n['child_ids'])
        elif kind == 'any':
            value = any(values[c] for c in n['child_ids'])
        elif kind == 'pass_through':
            value = values[n['child_ids'][0]]
        elif kind == 'stateful_transfer':
            # Consume even when incoming is false: evaluation can clear ONS
            # storage, so a false condition is not a claim of no execution.
            before = next(storage_iter)
            value = values[n['child_ids'][0]] and not before
        else:
            raise AssertionError('Unmodeled transfers cannot be evaluated here.')
        values[n['id']] = value
    return [values[o['guard_id']] for o in result.outputs]


class StatefulConditionTests(unittest.TestCase):
    def test_ons_has_one_symbolic_node_with_storage_operand_and_no_predicted_values(self) -> None:
        inputs = stateful_capture()
        result = inputs[-1]
        self.assertEqual(STATEFUL_OPCODES, {'ONS'})
        self.assertEqual((result.schema_version, result.analyzer_version), (3, 'condition-analysis-3'))
        entry, state = result.nodes
        self.assertEqual(state['kind'], 'stateful_transfer')
        self.assertEqual(state['child_ids'], [entry['id']])
        self.assertEqual(state['operand_ids'], inputs[3].instructions[0]['operand_ids'])
        self.assertEqual(state['reason'], 'documented_normal_scan_stored_state')
        self.assertFalse(entry['has_stateful'])
        self.assertTrue(state['has_stateful'])
        self.assertFalse(state['has_opaque'])
        self.assertFalse(state['has_binding_gap'])
        self.assertEqual(result.outputs[0]['guard_id'], state['id'])
        self.assertTrue(result.outputs[0]['has_stateful'])
        self.assertEqual(result.outputs[0]['guard_status'], 'modeled')
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.execution_analysis, 'not_implemented')
        self.assertFalse(any('value' in key or 'previous_scan' in key for key in state))
        validate_conditions(*inputs)

    def test_four_normal_evaluation_cases_depend_on_current_storage(self) -> None:
        result = stateful_capture()[-1]
        # Order is incoming false/true, storage false/true. This is a local
        # instruction truth table, not a generated PLC scan trace.
        expected = {(False, False): False, (False, True): False,
                    (True, False): True, (True, True): False}
        for (incoming, storage), outgoing in expected.items():
            with self.subTest(incoming=incoming, storage=storage):
                self.assertEqual(evaluate_occurrence_graph(result, entry=incoming, predicates=[],
                                                          storage_reads=[storage]), [outgoing])

    def test_alternative_legs_keep_independent_storage_and_exact_output_prefixes(self) -> None:
        result = stateful_capture(('[ONS(A)OTE(C),XIC(C)ONS(B)OTL(D)]OTU(C);',))[-1]
        for entry, predicate, left_storage, right_storage in product((False, True), repeat=4):
            left = entry and not left_storage
            right = entry and predicate and not right_storage
            self.assertEqual(evaluate_occurrence_graph(result, entry=entry, predicates=[predicate],
                                                      storage_reads=[left_storage, right_storage]),
                             [left, right, left or right])
        self.assertEqual(result.coverage['outputs_with_stateful_conditions'], 3)
        self.assertEqual(result.coverage['outputs_with_branches'], 1)

    def test_shared_storage_and_intervening_write_keep_separate_read_occurrences(self) -> None:
        inputs = stateful_capture(('ONS(A)OTE(B)MOV(C,A)ONS(A)OTL(D);',))
        result = inputs[-1]
        nodes = [n for n in result.nodes if n['kind'] == 'stateful_transfer']
        self.assertEqual(len(nodes), 2)
        self.assertNotEqual(nodes[0]['id'], nodes[1]['id'])
        self.assertNotEqual(nodes[0]['operand_ids'], nodes[1]['operand_ids'])
        shared = next(a for a in inputs[-2].addresses
                      if all(n['operand_ids'][0] in a['read_write_operand_ids'] for n in nodes))
        self.assertEqual(len(shared['write_operand_ids']), 1)
        for entry, before_first, before_second in product((False, True), repeat=3):
            first = entry and not before_first
            self.assertEqual(evaluate_occurrence_graph(result, entry=entry, predicates=[],
                                                      storage_reads=[before_first, before_second]),
                             [first, first and not before_second])
        self.assertTrue(any(n['kind'] == 'pass_through' and n['has_stateful'] for n in result.nodes))

    def test_empty_bypass_keeps_state_dependency_without_truth_simplification(self) -> None:
        result = stateful_capture(('[ONS(A),]OTE(B);',))[-1]
        self.assertEqual([n['kind'] for n in result.nodes], ['entry', 'stateful_transfer', 'any'])
        self.assertTrue(result.nodes[-1]['has_stateful'])
        for entry, storage in product((False, True), repeat=2):
            self.assertEqual(evaluate_occurrence_graph(result, entry=entry, predicates=[],
                                                      storage_reads=[storage]), [entry])

    def test_nested_branches_and_rung_boundaries_keep_flags_local(self) -> None:
        result = stateful_capture(('[XIC(A)[ONS(B),XIO(C)],ONS(D)]OTE(C);', 'OTE(A);'))[-1]
        self.assertEqual([o['has_stateful'] for o in result.outputs], [True, False])
        by_id = {n['id']: n for n in result.nodes}
        for node in result.nodes:
            self.assertTrue(all(by_id[c]['rung_id'] == node['rung_id'] for c in node['child_ids']))
        self.assertEqual(result.coverage['stateful_opcodes'], {'ONS': 2})
        self.assertEqual(result.coverage['outputs_with_stateful_conditions'], 1)

    def test_outputs_before_and_inside_unrelated_leg_do_not_inherit_later_state(self) -> None:
        result = stateful_capture(('OTE(A)[ONS(B)OTL(C),OTE(D)]OTU(A);',))[-1]
        self.assertEqual([o['has_stateful'] for o in result.outputs], [False, True, False, True])
        self.assertEqual(result.coverage['outputs_with_stateful_conditions'], 2)

    def test_no_coil_source_still_retains_ons_transfer_and_gap_status(self) -> None:
        result = stateful_capture(('ONS(A);', 'ONS(Missing);'))[-1]
        self.assertEqual(result.outputs, [])
        self.assertEqual(result.coverage['stateful_opcodes'], {'ONS': 2})
        self.assertEqual(result.coverage['outputs_with_stateful_conditions'], 0)
        self.assertEqual(result.coverage['binding_gap_stateful'], 1)
        self.assertEqual(result.status, 'partial')

    def test_storage_requires_exact_address_even_when_access_signature_classifies(self) -> None:
        for operand in ('Missing', 'A[B]', '1', 'S:FS'):
            with self.subTest(operand=operand):
                inputs = stateful_capture((f'ONS({operand})OTE(D);',))
                self.assertEqual(inputs[3].instructions[0]['status'], 'classified')
                result = inputs[-1]
                self.assertEqual(result.coverage['binding_gap_stateful'], 1)
                self.assertEqual(result.coverage['binding_gap_predicates'], 0)
                self.assertEqual(result.outputs[0]['guard_status'], 'binding_gaps')
                self.assertTrue(result.outputs[0]['has_stateful'])
                self.assertEqual(result.status, 'partial')

    def test_alias_exact_storage_and_invalid_expansion_are_distinguished(self) -> None:
        tags = tag('A') + tag('B') + tag('Alias', 'A.Member[2]') + tag('Bit', 'A.1')
        inputs = stateful_capture(('ONS(Alias)OTE(B);', 'ONS(Bit.Member)OTE(B);'), tags=tags)
        result = inputs[-1]
        self.assertEqual([o['guard_status'] for o in result.outputs], ['modeled', 'binding_gaps'])
        self.assertEqual(result.coverage['binding_gap_stateful'], 1)
        self.assertEqual(result.coverage['binding_gap_predicates'], 0)
        # Source address identity is not BOOL/member/type validity.
        self.assertEqual(result.execution_analysis, 'not_implemented')

    def test_ambiguous_storage_declaration_is_binding_gap(self) -> None:
        result = stateful_capture(('ONS(A)OTE(B);',), tags=tag('A') + tag('A') + tag('B'))[-1]
        self.assertEqual(result.coverage['binding_gap_stateful'], 1)
        self.assertEqual(result.outputs[0]['guard_status'], 'binding_gaps')

    def test_signature_failures_remain_opaque_without_invented_storage_read(self) -> None:
        for block in ('ONS()', 'ONS(A,B)'):
            with self.subTest(block=block):
                result = stateful_capture((block + 'OTE(D);',))[-1]
                self.assertEqual(result.coverage['stateful_opcodes'], {'ONS': 0})
                self.assertEqual(result.coverage['opaque_reasons']['signature_unresolved'], 1)
                self.assertEqual(result.outputs[0]['guard_status'], 'opaque')
                self.assertFalse(result.outputs[0]['has_stateful'])

    def test_opaque_and_binding_gap_ancestry_stay_visible_alongside_state(self) -> None:
        result = stateful_capture(('Mystery(A)ONS(B)OTE(C);', 'XIC(Missing)ONS(A)OTE(C);',
                                  '[Mystery(A),ONS(Missing)]OTE(C);'))[-1]
        self.assertEqual([o['guard_status'] for o in result.outputs], ['opaque', 'binding_gaps', 'opaque'])
        self.assertTrue(all(o['has_stateful'] for o in result.outputs))
        self.assertEqual(result.coverage['binding_gap_predicates'], 1)
        self.assertEqual(result.coverage['binding_gap_stateful'], 1)
        self.assertEqual(result.coverage['outputs_with_stateful_conditions'], 3)

    def test_osf_stays_identity_and_osr_stays_explicitly_unmodeled(self) -> None:
        result = stateful_capture(('OSF(A,B)OTE(C);', 'OSR(A,B)OTE(C);', 'ons(A)OTE(C);'))[-1]
        self.assertEqual(result.coverage['passthrough_opcodes']['OSF'], 1)
        self.assertEqual(result.coverage['stateful_opcodes'], {'ONS': 1})
        self.assertEqual([o['guard_status'] for o in result.outputs], ['modeled', 'opaque', 'modeled'])
        self.assertEqual([o['has_stateful'] for o in result.outputs], [False, False, True])

    def test_all_existing_passes_still_have_their_own_occurrences(self) -> None:
        result = stateful_capture(tuple(f'ONS(D){block}OTE(C);' for block in PASS_EXAMPLES))[-1]
        self.assertEqual(result.coverage['node_kinds']['pass_through'], len(PASS_EXAMPLES))
        self.assertEqual(result.coverage['node_kinds']['stateful_transfer'], len(PASS_EXAMPLES))
        self.assertEqual(result.coverage['outputs_with_stateful_conditions'], len(PASS_EXAMPLES))
        self.assertTrue(all(n['has_stateful'] for n in result.nodes if n['kind'] == 'pass_through'))

    def test_prior_versions_keep_default_fields_and_later_node_identity(self) -> None:
        inputs = capture(('XIC(A)ONS(B)XIO(C)MOV(A,D)OTE(D);',), schema_version=2)
        before = render_conditions_json(inputs[-1])
        current = analyze_conditions(*inputs[:-1], schema_version=3)
        old = inputs[-1]
        self.assertEqual(len(current.nodes), len(old.nodes))
        for previous, changed in zip(old.nodes, current.nodes, strict=True):
            if previous['instruction_id'] == old.nodes[3]['instruction_id']:
                self.assertNotEqual(previous['id'], changed['id'])
            else:
                self.assertEqual(previous['id'], changed['id'])
        self.assertEqual(old.outputs[0]['id'], current.outputs[0]['id'])
        self.assertFalse(any('has_stateful' in n for n in old.nodes + old.outputs))
        self.assertNotIn('stateful_opcodes', old.coverage)
        self.assertEqual(before, render_conditions_json(analyze_conditions(*inputs[:-1], schema_version=2)))
        default = analyze_conditions(*inputs[:-1])
        self.assertEqual(default.schema_version, 1)
        self.assertFalse(any('has_stateful' in n for n in default.nodes + default.outputs))
        self.assertEqual(default.coverage['node_kinds']['opaque_transfer'], 2)

    def test_stateful_mutations_and_version_disguises_fail_canonical_validation(self) -> None:
        inputs = stateful_capture(('ONS(A)MOV(B,A)OTE(D);',))
        mutations = (
            lambda r: r.nodes[1].update(has_stateful=False),
            lambda r: r.nodes[0].update(has_stateful=True),
            lambda r: r.nodes[2].update(has_stateful=False),
            lambda r: r.nodes[1].update(reason='previous_scan_rising_edge'),
            lambda r: r.nodes[1].update(kind='pass_through'),
            lambda r: r.nodes[1].update(operand_ids=[]),
            lambda r: r.nodes[1].update(child_ids=[]),
            lambda r: r.outputs[0].update(has_stateful=False),
            lambda r: r.coverage.update(binding_gap_stateful=1),
            lambda r: r.coverage.update(outputs_with_stateful_conditions=0),
        )
        for mutate in mutations:
            candidate = deepcopy(inputs[-1])
            mutate(candidate)
            with self.subTest(mutate=mutate), self.assertRaises(ConditionError):
                validate_conditions(*inputs[:-1], candidate)
        with self.assertRaises(ConditionError):
            validate_conditions(*inputs[:-1], replace(inputs[-1], schema_version=2,
                                                     analyzer_version='condition-analysis-2'))

    def test_stateful_branch_products_stay_linear_and_resource_bounded(self) -> None:
        result = stateful_capture((''.join('[ONS(A),ONS(B)]' for _ in range(120)) + 'OTE(C);',))[-1]
        self.assertEqual(len(result.nodes), 361)
        self.assertEqual(sum(len(n['child_ids']) for n in result.nodes), 480)
        self.assertEqual(result.coverage['outputs_with_stateful_conditions'], 1)
        rendered = render_conditions_json(result)
        self.assertLess(len(rendered), 400_000)
        with patch('plc_workbench.conditions.MAX_CONDITION_BYTES', len(rendered) - 1), self.assertRaises(ConditionError):
            render_conditions_json(result)


if __name__ == '__main__':
    unittest.main()
