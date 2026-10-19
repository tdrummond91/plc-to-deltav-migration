"""CPT syntax, scope and rejection tests using invented source only."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import tracemalloc
import unittest
from unittest.mock import patch

from plc_workbench.calculations import (
    FUNCTIONS, FUNCTIONS_V1, CalculationError, analyze_calculations, render_calculation_json, validate_calculations,
)
from plc_workbench.references import analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def tag(name: str, alias: str | None = None) -> str:
    return (f'<Tag Name="{name}" TagType="Base" DataType="REAL"/>' if alias is None else
            f'<Tag Name="{name}" TagType="Alias" AliasFor="{alias}"/>')


def program(text: str, tags: str = '', name: str = 'P') -> str:
    return (f'<Program Name="{name}"><Tags>{tags}</Tags><Routines><Routine Name="R" Type="RLL">'
            f'<RLLContent><Rung Number="0" Type="N"><Text><![CDATA[{text}]]></Text></Rung>'
            '</RLLContent></Routine></Routines></Program>')


def capture_xml(xml: str, *, schema_version: int = 2):
    snapshot = snapshot_from_bytes(xml.encode())
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    result = analyze_calculations(snapshot, inventory, references, schema_version=schema_version)
    return snapshot, inventory, references, result


def capture(expression: str = 'A + 1', destination: str = 'D', *, text: str | None = None,
            tags: str | None = None, local: str = '', schema_version: int = 2):
    declarations = ''.join(tag(name) for name in ('A', 'B', 'C', 'D', 'Index', 'Arr')) if tags is None else tags
    xml = ('<RSLogix5000Content><Controller Name="Invented"><Tags>' + declarations + '</Tags><Programs>'
           + program(text if text is not None else f'CPT({destination},{expression});', local)
           + '</Programs></Controller></RSLogix5000Content>')
    return capture_xml(xml, schema_version=schema_version)


def tree(result, occurrence: int = 0):
    by_id = {row['id']: row for row in result.nodes}

    def visit(identifier):
        node = by_id[identifier]
        if node['kind'] in {'literal', 'reference'}:
            return node['raw_text']
        return (node['operator'] or node['kind'], *(visit(child) for child in node['child_ids']))

    return visit(result.occurrences[occurrence]['root_node_id'])


class CalculationTests(unittest.TestCase):
    def test_repeated_leaves_spans_ids_and_original_layers_are_preserved(self) -> None:
        inputs = capture('  A + A * 2  ')
        snapshot, inventory, references, result = inputs
        original_inventory, original_references = inventory.to_dict(), references.to_dict()
        self.assertEqual(result.status, 'complete')
        self.assertEqual(tree(result), ('+', 'A', ('*', 'A', '2')))
        occurrence = result.occurrences[0]
        self.assertEqual(occurrence['id'], inventory.rungs[0].instructions[0].id)
        self.assertEqual(occurrence['expression_operand_id'], references.operands[1]['id'])
        self.assertEqual(references.operands[1]['status'], 'unsupported_expression')
        leaves = [node for node in result.nodes if node['kind'] == 'reference']
        self.assertEqual([node['raw_text'] for node in leaves], ['A', 'A'])
        self.assertNotEqual(leaves[0]['id'], leaves[1]['id'])
        self.assertEqual(leaves[0]['binding']['target_id'], leaves[1]['binding']['target_id'])
        self.assertEqual(result.coverage['reference_occurrences'], 2)
        source_expression = references.operands[1]['raw_text']
        for node in result.nodes:
            if node['raw_text'] is not None:
                self.assertEqual(source_expression[node['start']:node['end']], node['raw_text'])
        validate_calculations(*inputs)
        self.assertEqual(json.loads(render_calculation_json(result)), result.to_dict())
        self.assertEqual(result.to_dict(), analyze_calculations(snapshot, inventory, references).to_dict())
        self.assertEqual(inventory.to_dict(), original_inventory)
        self.assertEqual(references.to_dict(), original_references)

    def test_documented_precedence_left_associative_power_and_unary_negation(self) -> None:
        examples = {
            'A**B**C': ('**', ('**', 'A', 'B'), 'C'),
            '-A**B': ('-', ('**', 'A', 'B')),
            '(-A)**B': ('**', ('group', ('-', 'A')), 'B'),
            'A-B-C': ('-', ('-', 'A', 'B'), 'C'),
            'A + B * C MOD 2': ('+', 'A', ('MOD', ('*', 'B', 'C'), '2')),
            'NOT A AND B XOR C OR D': ('OR', ('XOR', ('AND', ('NOT', 'A'), 'B'), 'C'), 'D'),
            'A / B / C': ('/', ('/', 'A', 'B'), 'C'),
            'SQRT(A + B) * ABS(-C)': ('*', ('SQRT', ('+', 'A', 'B')), ('ABS', ('-', 'C'))),
            'A**(-2)': ('**', 'A', ('group', ('-', '2'))),
        }
        for expression, expected in examples.items():
            with self.subTest(expression=expression):
                result = capture(expression)[-1]
                self.assertEqual(result.status, 'complete')
                self.assertEqual(tree(result), expected)

    def test_every_verified_unary_function_and_ascii_case_is_retained(self) -> None:
        for function in FUNCTIONS:
            with self.subTest(function=function):
                result = capture(f'{function.lower()}(A)')[-1]
                self.assertEqual(result.status, 'complete')
                self.assertEqual(tree(result), (function, 'A'))
        result = capture(text='cPt(D,a mOd 2);')[-1]
        self.assertEqual(tree(result), ('MOD', 'a', '2'))

    def test_unknown_functions_and_unsupported_lexemes_have_no_partial_bindings(self) -> None:
        for expression, code in (
            ('A + PRIVATE_FUNCTION(B)', 'unsupported_function'),
            ('ATAN2(A,B)', 'unsupported_function'),
            ('A + "invented_secret"', 'lexical_error'),
            ('A % 2', 'lexical_error'), ('A ^ 2', 'lexical_error'),
            ('A + π', 'lexical_error'), ('A\u00a0+B', 'lexical_error'),
            ('A +', 'syntax_error'), ('ABS(A,B)', 'syntax_error'),
            ('A B', 'syntax_error'), ('A(1)', 'unsupported_function'),
            ('+A', 'syntax_error'), ('A ** * B', 'syntax_error'),
            ('A**-B**C', 'syntax_error'), ('A**NOT B', 'syntax_error'),
            ('B + Arr[1+]', 'syntax_error'), ('B + Arr[foo@@bar]', 'syntax_error'),
            ('B + Arr[]', 'syntax_error'),
        ):
            with self.subTest(expression=expression):
                result = capture(expression)[-1]
                self.assertEqual(result.status, 'partial')
                self.assertEqual(result.nodes, [])
                self.assertEqual(result.coverage['reference_occurrences'], 0)
                self.assertEqual(result.occurrences[0]['syntax_status'], 'unsupported')
                self.assertEqual(result.occurrences[0]['error_code'], code)
                self.assertIsNone(result.occurrences[0]['root_node_id'])
                self.assertEqual(result.occurrences[0]['node_ids'], [])

    def test_legacy_and_modern_function_spellings_keep_distinct_nodes_and_counts(self) -> None:
        pairs = {'ACS': 'ACOS', 'ASN': 'ASIN', 'ATN': 'ATAN', 'FRD': 'BCD_TO',
                 'SQR': 'SQRT', 'TOD': 'TO_BCD', 'TRN': 'TRUNC'}
        self.assertEqual(FUNCTIONS - FUNCTIONS_V1, pairs.keys())
        self.assertEqual(len(FUNCTIONS), 22)
        for legacy, modern in pairs.items():
            expression = f'{legacy.title()}({modern.lower()}(A)) + {legacy.lower()}(B)'
            with self.subTest(legacy=legacy, modern=modern):
                inputs = capture(expression)
                result = inputs[-1]
                self.assertEqual(tree(result), ('+', (legacy, (modern, 'A')), (legacy, 'B')))
                self.assertEqual(result.coverage['functions_by_spelling'][legacy], 2)
                self.assertEqual(result.coverage['functions_by_spelling'][modern], 1)
                self.assertEqual(sum(result.coverage['functions_by_spelling'].values()), 3)
                self.assertEqual(result.coverage['nodes_by_kind']['function'], 3)
                self.assertEqual(result.coverage['unsupported_functions'], {'atan2': 0, 'other': 0})
                validate_calculations(*inputs)
        # Function names without parentheses remain ordinary reference leaves.
        result = capture('SQR + SQRT', tags=tag('SQR') + tag('SQRT') + tag('D'))[-1]
        self.assertEqual(result.coverage['reference_occurrences'], 2)
        self.assertEqual(sum(result.coverage['functions_by_spelling'].values()), 0)

    def test_every_function_rejects_wrong_arity_without_partial_function_counts(self) -> None:
        for function in FUNCTIONS:
            for argument in ('', 'A,B'):
                with self.subTest(function=function, argument=argument):
                    result = capture(f'ABS(A) + {function}({argument})')[-1]
                    self.assertEqual(result.occurrences[0]['error_code'], 'syntax_error')
                    self.assertEqual(result.nodes, [])
                    self.assertEqual(sum(result.coverage['functions_by_spelling'].values()), 0)
                    self.assertEqual(sum(result.coverage['unsupported_functions'].values()), 0)

    def test_only_first_rejected_function_is_counted_and_unknown_names_are_pooled(self) -> None:
        cases = (
            ('ABS(A) + aTaN2(A,B) + PRIVATE_FUNCTION(C)', 'unsupported_function', 'atan2'),
            ('ABS(A) + PRIVATE_FUNCTION(B) + ATAN2(A,C)', 'unsupported_function', 'other'),
            ('A.ATAN2(B)', 'unsupported_function', 'other'),
            ('ATAN2[0](A)', 'unsupported_function', 'other'),
            ('ATAN2_PRIVATE(A)', 'unsupported_function', 'other'),
            ('ATAN2(A,B) + π', 'lexical_error', None),
            ('ATAN2(ABS(A), B)', 'unsupported_function', 'atan2'),
        )
        for expression, error, bucket in cases:
            with self.subTest(expression=expression):
                result = capture(expression)[-1]
                self.assertEqual(result.occurrences[0]['error_code'], error)
                self.assertEqual(result.nodes, [])
                self.assertEqual(sum(result.coverage['functions_by_spelling'].values()), 0)
                self.assertEqual(result.coverage['unsupported_functions'],
                                 {name: int(name == bucket) for name in ('atan2', 'other')})

    def test_schema_one_replay_is_byte_stable_and_catalogs_cannot_cross_contaminate(self) -> None:
        text = 'CPT(D,SQRT(A)+ABS(-B))CPT(D,SQR(A))CPT(D,ATAN2(A,B));'
        inputs = capture(text=text, schema_version=1)
        old = inputs[-1]
        # Captured from the schema 1 implementation before its catalog changed.
        self.assertEqual(hashlib.sha256(render_calculation_json(old).encode()).hexdigest(),
                         'f50fcd86c774c0d48827900dee7f68bd8c90ec10c2aba682efd779c94d5461ed')
        self.assertEqual((old.schema_version, old.analyzer_version), (1, 'calculation-evidence-1'))
        self.assertEqual(old.coverage['expressions_by_status']['parsed'], 1)
        for version in (2, 1, 2, 1):
            current = analyze_calculations(*inputs[:3], schema_version=version)
            self.assertEqual(current.coverage['expressions_by_status']['parsed'], 1 if version == 1 else 2)
            validate_calculations(*inputs[:3], current)
            if version == 1:
                self.assertEqual(render_calculation_json(current), render_calculation_json(old))
        self.assertNotIn('functions_by_spelling', old.coverage)
        self.assertNotIn('unsupported_functions', old.coverage)
        current = analyze_calculations(*inputs[:3])
        for name in ('functions_by_spelling', 'unsupported_functions'):
            changed = deepcopy(old)
            changed.coverage[name] = current.coverage[name]
            with self.assertRaises(CalculationError):
                validate_calculations(*inputs[:3], changed)

    def test_schema_selection_and_function_counters_are_authenticated(self) -> None:
        snapshot, inventory, references, result = capture('SQR(A)')
        for version in (True, False, 0, 3, 1.0, '1', None):
            with self.subTest(version=version), self.assertRaises(CalculationError):
                analyze_calculations(snapshot, inventory, references, schema_version=version)
            with self.subTest(result_version=version), self.assertRaises(CalculationError):
                validate_calculations(snapshot, inventory, references, replace(result, schema_version=version))
        changed = deepcopy(result)
        changed.coverage['functions_by_spelling'].update(SQR=0, SQRT=1)
        with self.assertRaises(CalculationError):
            validate_calculations(snapshot, inventory, references, changed)
        with self.assertRaises(CalculationError):
            validate_calculations(snapshot, inventory, references,
                                  replace(result, schema_version=1, analyzer_version='calculation-evidence-1'))

    def test_dynamic_index_is_one_unsupported_address_leaf_without_index_dependency(self) -> None:
        *_, result = capture('Arr[Index+1] + Arr[2].Value + A')
        leaves = [node for node in result.nodes if node['kind'] == 'reference']
        self.assertEqual([node['raw_text'] for node in leaves], ['Arr[Index+1]', 'Arr[2].Value', 'A'])
        self.assertEqual([node['binding']['status'] for node in leaves],
                         ['unsupported_address', 'root_bound', 'root_bound'])
        self.assertEqual(leaves[0]['binding']['reason'], 'non_static_array_index')
        self.assertEqual(result.coverage['expressions_with_binding_gaps'], 1)
        self.assertEqual(result.status, 'partial')

    def test_literal_spelling_preserved_without_numeric_or_domain_evaluation(self) -> None:
        expression = '16#F_F + 2#10 + 8#17 + 1e-3 + .50 + LN(-1) + 1 / 0'
        result = capture(expression)[-1]
        self.assertEqual(result.status, 'complete')
        literals = [node['raw_text'] for node in result.nodes if node['kind'] == 'literal']
        self.assertEqual(literals, ['16#F_F', '2#10', '8#17', '1e-3', '.50', '1', '1', '0'])
        self.assertTrue(all(node['binding'] is None for node in result.nodes if node['kind'] == 'literal'))
        self.assertEqual(result.numeric_analysis, 'not_implemented')
        for expression in ('16#GG', '2#102', '1e+', '1.2.3', '1_000'):
            with self.subTest(expression=expression):
                self.assertEqual(capture(expression)[-1].occurrences[0]['syntax_status'], 'unsupported')

    def test_signature_failures_and_non_root_destinations_remain_partial(self) -> None:
        *_, result = capture(text='CPT()CPT(D)CPT(D,A,B)CPT(,A)CPT(D,)CPT(0,A)CPT(Missing,A);')
        self.assertEqual(result.coverage['occurrences_total'], 7)
        self.assertEqual(result.coverage['occurrences_by_signature'],
                         {'recognized': 2, 'argument_count_mismatch': 3, 'empty_argument': 2})
        self.assertEqual(result.coverage['expressions_by_status'],
                         {'parsed': 2, 'unsupported': 0, 'signature_unresolved': 5})
        self.assertEqual(result.coverage['destination_root_bound'], 0)
        self.assertEqual(result.status, 'partial')
        self.assertIsNone(result.occurrences[0]['destination_operand_id'])
        self.assertIsNotNone(result.occurrences[3]['destination_operand_id'])
        self.assertTrue(all(not row['node_ids'] for row in result.occurrences[:5]))

    def test_program_shadowing_and_alias_declaration_scope_are_reused(self) -> None:
        tags = tag('A') + tag('D') + tag('Alias', 'A.Member[2]')
        *_, result = capture('A + Alias.7', tags=tags, local=tag('A'))
        leaves = [node for node in result.nodes if node['kind'] == 'reference']
        self.assertNotEqual(leaves[0]['binding']['target_id'], leaves[1]['binding']['target_id'])
        self.assertEqual(leaves[1]['binding']['suffix'], '.Member[2].7')
        self.assertEqual(len(leaves[1]['binding']['alias_chain']), 1)
        self.assertEqual(result.status, 'complete')

    def test_cycles_ambiguity_missing_and_unsupported_qualified_addresses_are_gaps(self) -> None:
        tags = tag('D') + tag('A', 'B') + tag('B', 'A') + tag('Duplicate') + tag('DUPLICATE')
        *_, result = capture('A + Duplicate + Missing + Program:Other.Tag', tags=tags)
        leaves = [node for node in result.nodes if node['kind'] == 'reference']
        self.assertEqual([node['binding']['status'] for node in leaves],
                         ['alias_cycle', 'ambiguous', 'unresolved', 'unsupported_address'])
        self.assertEqual(leaves[-1]['binding']['reason'], 'program_qualified_address')
        self.assertEqual(result.coverage['expressions_with_binding_gaps'], 1)

    def test_aoi_scope_isolated_from_controller_and_alias_targets_must_be_local(self) -> None:
        xml = ('<RSLogix5000Content><Controller Name="C"><Tags>' + tag('Outside') + '</Tags>'
               '<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="AOI">'
               '<Parameters><Parameter Name="P" DataType="REAL" Usage="Input" AliasFor="Q"/>'
               '<Parameter Name="Q" DataType="REAL" Usage="Input"/></Parameters>'
               '<LocalTags><LocalTag Name="Dest" DataType="REAL"/></LocalTags>'
               '<Routines><Routine Name="Logic" Type="RLL"><RLLContent><Rung Number="0"><Text>'
               '<![CDATA[CPT(Dest,P + Outside);]]></Text></Rung></RLLContent></Routine></Routines>'
               '</AddOnInstructionDefinition></AddOnInstructionDefinitions></Controller></RSLogix5000Content>')
        result = capture_xml(xml)[-1]
        leaves = [node for node in result.nodes if node['kind'] == 'reference']
        self.assertEqual([node['binding']['reason'] for node in leaves],
                         ['aoi_alias_target_not_local', 'root_not_declared'])

    def test_no_cpt_and_unparsed_rungs_are_not_fabricated_occurrences(self) -> None:
        self.assertEqual(capture(text='ADD(A,B,D);')[-1].status, 'complete')
        result = capture(text='CPT(D,A + (B);')[-1]
        self.assertEqual(result.coverage['unparsed_rungs'], 1)
        self.assertEqual(result.occurrences, [])
        self.assertEqual(result.nodes, [])
        self.assertEqual(result.status, 'partial')

    def test_length_token_depth_limits_preserve_occurrences_without_partial_nodes(self) -> None:
        for expression, code in (
            ('A' + ' ' * 4096 + '+1', 'length_limit'),
            ('A+' * 256 + 'A', 'token_limit'),
            ('(' * 65 + 'A' + ')' * 65, None),
            ('-' * 65 + 'A', 'depth_limit'),
            ('A+' * 64 + 'A', 'depth_limit'),
        ):
            with self.subTest(code=code, expression_length=len(expression)):
                result = capture(expression)[-1]
                # The outer ladder grammar itself rejects nesting beyond 64.
                if code is None:
                    self.assertEqual(result.coverage['unparsed_rungs'], 1)
                else:
                    self.assertEqual(result.occurrences[0]['error_code'], code)
                self.assertEqual(result.nodes, [])

    def test_total_source_limits_include_non_cpt_instructions_and_operands(self) -> None:
        snapshot, inventory, references, _ = capture(text='ADD(A,B,D)ADD(A,B,D);')
        for name, limit in (('MAX_CALCULATION_INSTRUCTIONS', 1), ('MAX_OPERANDS', 5)):
            with self.subTest(name=name), patch(f'plc_workbench.calculations.{name}', limit):
                with self.assertRaises(CalculationError):
                    analyze_calculations(snapshot, inventory, references)
        snapshot, inventory, references, _ = capture('A+B')
        for name, limit in (('MAX_CALCULATION_NODES', 2), ('MAX_CALCULATION_BYTES', 500)):
            with self.subTest(name=name), patch(f'plc_workbench.calculations.{name}', limit):
                with self.assertRaises(CalculationError):
                    analyze_calculations(snapshot, inventory, references)

    def test_snapshot_inventory_references_and_every_result_link_are_authenticated(self) -> None:
        inputs = capture('A + A')
        snapshot, inventory, references, result = inputs
        for changed_snapshot in (replace(snapshot, id='forged'), replace(snapshot, size_bytes=True),
                                 replace(snapshot, sha256='0' * 64)):
            with self.assertRaises(CalculationError):
                analyze_calculations(changed_snapshot, inventory, references)
        changed_inventory = deepcopy(inventory)
        changed_inventory.rungs[0].instructions[0] = replace(changed_inventory.rungs[0].instructions[0], opcode='ADD')
        with self.assertRaises(CalculationError):
            analyze_calculations(snapshot, changed_inventory, references)
        changed_references = deepcopy(references)
        changed_references.operands[0]['target_id'] = None
        with self.assertRaises(CalculationError):
            analyze_calculations(snapshot, inventory, changed_references)
        alterations = [
            lambda value: value.nodes[0].update(start=True),
            lambda value: value.nodes[0].update(raw_text='InventedDifferent'),
            lambda value: value.nodes[0]['binding'].update(target_id=None),
            lambda value: value.nodes[-1]['child_ids'].reverse(),
            lambda value: value.occurrences[0].update(root_node_id=None),
            lambda value: value.coverage.update(nodes_total=0),
            lambda value: value.occurrences.append(value.occurrences[0]),
        ]
        for alteration in alterations:
            changed = deepcopy(result)
            alteration(changed)
            with self.assertRaises(CalculationError):
                validate_calculations(snapshot, inventory, references, changed)
        validate_calculations(*inputs)

    def test_bounded_renderer_rejects_custom_objects_and_cycles(self) -> None:
        result = capture('A')[-1]
        changed = deepcopy(result)
        changed.nodes[0]['binding'] = object()
        with self.assertRaises(CalculationError):
            render_calculation_json(changed)
        changed = deepcopy(result)
        changed.nodes[0]['child_ids'].append(changed.nodes[0]['child_ids'])
        with patch('plc_workbench.calculations.MAX_CALCULATION_BYTES', 2000):
            with self.assertRaises(CalculationError):
                render_calculation_json(changed)

    def test_cyclic_fanout_is_rejected_without_allocating_a_wide_queue(self) -> None:
        changed = deepcopy(capture('A')[-1])
        cycle = []
        cycle.extend([cycle] * 1000)
        changed.coverage['cycle'] = cycle
        tracemalloc.start()
        try:
            with patch('plc_workbench.calculations.MAX_CALCULATION_BYTES', 2000):
                with self.assertRaises(CalculationError):
                    render_calculation_json(changed)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 100_000)


if __name__ == '__main__':
    unittest.main()
