"""CPT source slots and authenticated expression reads stay distinct."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import AccessError, analyze_access, render_access_json, validate_access
from plc_workbench.access_summary import build_access_summary, render_access_summary
from plc_workbench.calculations import analyze_calculations
from test_calculations import capture, tag


BASELINE_TEXT = 'TON(A,?,0)CTU(A,?,0)MSG(A)GSV(TASK,,Status,A)SFR(R,A)CPT(D,A+A*B);'


def evidence(expression: str = 'A + A * B', **kwargs):
    snapshot, inventory, references, calculations = capture(expression, **kwargs)
    result = analyze_access(inventory, references, schema_version=4,
                            snapshot=snapshot, calculations=calculations)
    return snapshot, inventory, references, calculations, result


class CptAccessTests(unittest.TestCase):
    def test_reference_occurrences_preserve_order_identity_and_separate_root_indices(self) -> None:
        snapshot, inventory, references, calculations, result = evidence(' B + (A + B) * A ', destination='A')
        self.assertEqual(result.status, 'complete')
        self.assertEqual([row['role'] for row in result.operands], ['write', 'expression_read'])
        container = result.operands[1]
        self.assertEqual((container['binding_status'], container['binding_origin'], container['source_reference_status']),
                         ('parsed_expression', 'calculation_expression', 'unsupported_expression'))
        self.assertEqual((container['symbol_id'], container['target_id'], container['suffix'], container['alias_chain']),
                         (None, None, '', []))
        nodes = {row['id']: row for row in calculations.nodes}
        self.assertEqual([nodes[row['id']]['raw_text'] for row in result.expression_uses], ['B', 'A', 'B', 'A'])
        self.assertEqual(len({row['id'] for row in result.expression_uses}), 4)
        self.assertEqual([row['start'] for row in result.expression_uses],
                         sorted(row['start'] for row in result.expression_uses))
        for use in result.expression_uses:
            node = nodes[use['id']]
            self.assertEqual((use['start'], use['end']), (node['start'], node['end']))
            self.assertEqual(use['expression_operand_id'], container['id'])
            self.assertEqual(use['role'], 'read')
            self.assertNotIn('raw_text', use)
        self.assertEqual(result.coverage['operands_total'], 2)
        self.assertEqual(result.coverage['expression_uses_total'], 4)
        self.assertEqual(result.coverage['linked_operands'], 1)
        self.assertEqual(result.coverage['bound_by_role']['read'], 0)
        self.assertEqual(result.coverage['bound_by_role']['expression_read'], 0)
        self.assertEqual(result.roots[0]['write_operand_ids'], [result.operands[0]['id']])
        self.assertEqual(result.roots[0]['read_operand_ids'], [])
        self.assertEqual([len(root['read_use_ids']) for root in result.expression_roots], [2, 2])
        validate_access(inventory, references, result, snapshot=snapshot, calculations=calculations)

    def test_constant_expression_has_container_but_no_reference_reads(self) -> None:
        _, _, _, _, result = evidence('1 + SQR(4)')
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.expression_uses, [])
        self.assertEqual(result.expression_roots, [])
        self.assertEqual(result.coverage['calculation_instructions'], 1)
        self.assertEqual(result.coverage['expression_containers_by_status'], {'parsed': 1, 'unsupported': 0})

    def test_aliases_use_authenticated_suffixes_and_do_not_share_mutable_lists(self) -> None:
        _, _, _, calculations, result = evidence('Alias.Member + Alias.Member',
            tags=tag('A') + tag('D') + tag('Alias', 'A[1]'))
        for use in result.expression_uses:
            self.assertEqual(use['suffix'], '[1].Member')
            self.assertNotEqual(use['symbol_id'], use['target_id'])
            self.assertEqual(use['alias_chain'], [use['symbol_id']])
            node = next(row for row in calculations.nodes if row['id'] == use['id'])
            self.assertIsNot(use['alias_chain'], node['binding']['alias_chain'])
        result.expression_uses[0]['alias_chain'].clear()
        self.assertEqual(len(result.expression_uses[1]['alias_chain']), 1)

    def test_lexical_scope_shadowing_remains_the_calculation_resolvers_result(self) -> None:
        _, _, _, calculations, result = evidence('Alias + A', local=tag('A') + tag('Alias', 'A'))
        self.assertEqual(len(result.expression_roots), 1)
        self.assertEqual(result.expression_uses[0]['target_id'], result.expression_uses[1]['target_id'])
        expected = [node['binding'] for node in calculations.nodes if node['kind'] == 'reference']
        self.assertEqual([row['target_id'] for row in result.expression_uses], [row['target_id'] for row in expected])

    def test_dynamic_and_unresolved_leaves_remain_separate_read_gaps(self) -> None:
        _, _, _, _, result = evidence(text='CPT(D,Arr[Index] + Missing + A)CPT(D,Missing);')
        self.assertEqual([use['binding_status'] for use in result.expression_uses],
                         ['unsupported_address', 'unresolved', 'root_bound', 'unresolved'])
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.coverage['expressions_with_binding_gaps'], 2)
        self.assertEqual(result.coverage['access_gap_operands'], 0)
        self.assertEqual(result.coverage['expression_indexed_roots'], 1)

    def test_bad_syntax_keeps_known_destination_write_without_partial_expression_reads(self) -> None:
        for expression in ('A +', 'A + UnknownFunction(B)', 'ATAN2(A,B)', 'A @ B'):
            with self.subTest(expression=expression):
                _, _, _, _, result = evidence(expression)
                self.assertEqual(result.instructions[0]['status'], 'classified')
                self.assertEqual(result.status, 'partial')
                self.assertEqual([row['role'] for row in result.operands], ['write', 'expression_read'])
                self.assertEqual(result.operands[1]['binding_status'], 'unsupported_expression')
                self.assertEqual(result.expression_uses, [])
                self.assertEqual(result.coverage['expression_containers_by_status'], {'parsed': 0, 'unsupported': 1})

    def test_invalid_signatures_remain_all_unknown_and_have_no_expression_container(self) -> None:
        for text, status in (('CPT(D);', 'argument_count_mismatch'), ('CPT(D,A,B);', 'argument_count_mismatch'),
                             ('CPT(,A);', 'empty_argument'), ('CPT(D,);', 'empty_argument'),
                             ('CPT();', 'argument_count_mismatch')):
            with self.subTest(text=text):
                _, _, _, _, result = evidence(text=text)
                self.assertEqual(result.instructions[0]['status'], status)
                self.assertTrue(all(row['role'] == 'unknown' for row in result.operands))
                self.assertEqual(result.coverage['calculation_instructions'], 0)
                self.assertEqual(result.expression_uses, [])

    def test_unbound_destination_is_source_slot_gap_independent_of_parsed_reads(self) -> None:
        _, _, _, _, result = evidence('A', destination='Missing')
        self.assertEqual(result.coverage['access_gap_operands'], 1)
        self.assertEqual(result.coverage['expressions_with_binding_gaps'], 0)
        self.assertEqual(result.status, 'partial')

    def test_companions_are_required_pinned_and_source_authenticated(self) -> None:
        snapshot, inventory, references, calculations = capture()
        for kwargs in ({}, {'snapshot': snapshot}, {'calculations': calculations},
                       {'snapshot': snapshot, 'calculations': analyze_calculations(snapshot, inventory, references, schema_version=1)},
                       {'snapshot': replace(snapshot, data=snapshot.data + b' '), 'calculations': calculations}):
            with self.subTest(kwargs=list(kwargs)), self.assertRaises(AccessError):
                analyze_access(inventory, references, schema_version=4, **kwargs)
        mutations = (
            lambda c: c.nodes[0].update(id='forged'),
            lambda c: c.nodes[0]['binding'].update(target_id='forged'),
            lambda c: c.occurrences[0].update(expression_operand_id='forged'),
            lambda c: c.nodes.reverse(),
        )
        for mutate in mutations:
            candidate = deepcopy(calculations)
            mutate(candidate)
            with self.subTest(mutation=mutate), self.assertRaises(AccessError):
                analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=candidate)

    def test_canonical_validation_rejects_leaf_and_index_forgery(self) -> None:
        snapshot, inventory, references, calculations, result = evidence()
        mutations = (
            lambda a: a.expression_uses.reverse(),
            lambda a: a.expression_uses[0].update(start=999),
            lambda a: a.expression_uses[0].update(role='write'),
            lambda a: a.expression_uses[0].update(expression_operand_id='forged'),
            lambda a: a.expression_roots[0]['read_use_ids'].reverse(),
            lambda a: a.roots[0]['read_operand_ids'].append(a.expression_uses[0]['id']),
            lambda a: a.operands[1].update(binding_status='root_bound', target_id=a.operands[0]['target_id']),
        )
        for mutate in mutations:
            candidate = deepcopy(result)
            mutate(candidate)
            with self.subTest(mutation=mutate), self.assertRaises(AccessError):
                validate_access(inventory, references, candidate, snapshot=snapshot, calculations=calculations)

    def test_independent_use_count_and_shared_retained_expansion_are_bounded(self) -> None:
        snapshot, inventory, references, calculations = capture('Alias.Member + Alias.Member',
            tags=tag('A') + tag('D') + tag('Alias', 'A[1]'))
        for limit, value in (('MAX_EXPRESSION_USES', 1), ('MAX_EXPANDED_EVIDENCE_CHARS', 1), ('MAX_ACCESS_BYTES', 500)):
            with self.subTest(limit=limit), patch('plc_workbench.access.' + limit, value), self.assertRaises(AccessError):
                analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)

    def test_source_and_leaf_binding_expansions_share_one_budget_before_copying(self) -> None:
        snapshot, inventory, references, calculations = capture('Alias', destination='Alias',
            tags=tag('A') + tag('Alias', 'A[1]'))
        leaf = next(row for row in calculations.nodes if row['kind'] == 'reference')['binding']
        one_binding = len(leaf['suffix']) + sum(map(len, leaf['alias_chain']))
        with patch('plc_workbench.access.MAX_EXPANDED_EVIDENCE_CHARS', one_binding), self.assertRaises(AccessError):
            analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
        with patch('plc_workbench.access.MAX_EXPANDED_EVIDENCE_CHARS', 2 * one_binding):
            result = analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
        self.assertEqual(len(result.expression_uses), 1)

    def test_legacy_bytes_and_default_api_remain_frozen(self) -> None:
        _, inventory, references, _ = capture(text=BASELINE_TEXT)
        hashes = {
            2: ('434408e6e36b7e1e88ca8371f4cb28e50cb45ff966e4c58329b4a3e9c0b35abf',
                '157a28daf8344183be006d1998addc943dedf2fcfd58e1ae5ee8f7172cd7b990'),
            3: ('79c897cada1f97b098d80b5ad6d3d4191e7e6998fab40b10dafcdc7a25c7a3b6',
                '67924aa8276c4bca9089c543ee14c1fc144b963183e1971f7526a05bd4867250'),
        }
        for version, expected in hashes.items():
            result = analyze_access(inventory, references, schema_version=version)
            encoded = render_access_json(result)
            summary = render_access_summary(build_access_summary(inventory, references, result))
            self.assertEqual(tuple(hashlib.sha256(text.encode()).hexdigest() for text in (encoded, summary)), expected)
            self.assertEqual(json.loads(encoded), result.to_dict())
            self.assertNotIn('expression_uses', result.to_dict())
            self.assertNotIn('expression_roots', result.to_dict())
        self.assertEqual(analyze_access(inventory, references).schema_version, 3)

    def test_serialization_rejects_hidden_legacy_fields_and_custom_hooks(self) -> None:
        _, inventory, references, _ = capture()
        class Hostile:
            def __deepcopy__(self, memo):
                raise AssertionError('deepcopy hook must not run')
            def __eq__(self, other):
                raise AssertionError('equality hook must not run')
            def __iter__(self):
                raise AssertionError('iteration hook must not run')
        for version in (2, 3, 4):
            if version == 4:
                result = evidence()[-1]
            else:
                result = analyze_access(inventory, references, schema_version=version)
            for value in ([{'unexpected': 1}], Hostile()):
                candidate = replace(result, expression_uses=value)
                if version == 4 and type(value) is list:
                    candidate = replace(result, expression_uses=[{'unexpected': Hostile()}])
                for serializer in (render_access_json, lambda row: row.to_dict()):
                    with self.subTest(version=version, value=type(value), serializer=serializer), self.assertRaises(AccessError):
                        serializer(candidate)


if __name__ == '__main__':
    unittest.main()
