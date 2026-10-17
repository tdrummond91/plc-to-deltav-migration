"""Invented SFC expressions only; no source filesystem or plant fixture reads."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from html import escape
import json
import unittest
from unittest.mock import patch

from plc_workbench.references import analyze_references
from plc_workbench.sfc_conditions import (FUNCTIONS, SfcConditionError,
    analyze_sfc_conditions, render_sfc_conditions_json, validate_sfc_conditions)
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def expression(text: str, number: str = '0') -> str:
    return f'<Transition ID="2"><Condition><STContent><Line Number="{number}">{escape(text)}</Line></STContent></Condition></Transition>'


def fixture(body: str | None = None, *, text: str = 'A', tags: str = '', local: str = '', extra: str = '', ns: str = ''):
    body = expression(text) if body is None else body
    data = (f'<RSLogix5000Content xmlns:x="urn:foreign" {ns}><Controller Name="C"><Tags>'
        '<Tag Name="A" DataType="BOOL"/><Tag Name="B" DataType="DINT"/>'
        '<Tag Name="CValue" DataType="REAL"/><Tag Name="Array" DataType="DINT" Dimensions="10"/>'
        f'{tags}</Tags><Programs><Program Name="P"><Tags>{local}</Tags><Routines>'
        f'<Routine Name="Chart" Type="SFC"><SFCContent>{body}</SFCContent>{extra}</Routine>'
        '</Routines></Program></Programs></Controller></RSLogix5000Content>').encode()
    snapshot = snapshot_from_bytes(data)
    inventory = analyze_snapshot(snapshot)
    return snapshot, inventory, analyze_references(inventory), analyze_sfc_structure(snapshot, inventory)


def analyze(**kwargs):
    inputs = fixture(**kwargs)
    return analyze_sfc_conditions(*inputs)


def tree(result):
    nodes = {node['id']: node for node in result.nodes}

    def descend(identifier):
        node = nodes[identifier]
        return (node['kind'], node['operator'], node['raw_text'], *(descend(child) for child in node['children']))

    return descend(result.transitions[0]['root_node_id'])


class SfcConditionTests(unittest.TestCase):
    def test_empty_and_literal_source_have_consistent_complete_evidence(self):
        empty = analyze(body='')
        self.assertEqual(empty.status, 'complete')
        self.assertEqual(empty.transitions, [])
        result = analyze(text='1')
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.nodes[0]['kind'], 'number')
        self.assertEqual(result.references, [])

    def test_snapshot_and_predecessors_are_unchanged_by_analysis_and_replay(self):
        inputs = fixture(text='A AND B > 2')
        before = deepcopy(inputs)
        result = analyze_sfc_conditions(*inputs)
        validate_sfc_conditions(*inputs, result)
        self.assertEqual(inputs, before)
        self.assertEqual(json.loads(render_sfc_conditions_json(result)), result.to_dict())

    def test_all_logix_binary_precedence_tiers(self):
        result = analyze(text='A OR B XOR A AND B = CValue < 1 + 2 * 3 ** 4')
        shaped = tree(result)
        self.assertEqual([shaped[1], shaped[4][1], shaped[4][4][1], shaped[4][4][4][1],
            shaped[4][4][4][4][1], shaped[4][4][4][4][4][1],
            shaped[4][4][4][4][4][4][1], shaped[4][4][4][4][4][4][4][1]],
            ['OR', 'XOR', 'AND', '=', '<', '+', '*', '**'])

    def test_exponent_left_association_and_distinct_unary_precedence(self):
        shaped = tree(analyze(text='-2 ** 3 ** 4'))
        self.assertEqual(shaped[1], '-')
        self.assertEqual(shaped[3][1], '**')
        self.assertEqual(shaped[3][3][1], '**')
        shaped = tree(analyze(text='NOT -2 ** 3 * 4'))
        self.assertEqual(shaped[1], '*')
        self.assertEqual(shaped[3][1], 'NOT')
        self.assertEqual(shaped[3][3][1], '-')
        self.assertEqual(shaped[3][3][3][1], '**')

    def test_group_mod_ampersand_comparisons_and_ascii_keyword_case(self):
        result = analyze(text='not (a <> B) & B MOD +2 <= CValue / -3')
        self.assertEqual(result.status, 'complete')
        self.assertEqual({n['operator'] for n in result.nodes}, {None, 'NOT', '<>', '&', 'MOD', '+', '<=', '/', '-'})
        self.assertEqual([r['raw_text'] for r in result.references], ['a', 'B', 'B', 'CValue'])

    def test_math_functions_modern_and_documented_legacy_aliases(self):
        for name in sorted(FUNCTIONS):
            with self.subTest(name=name):
                result = analyze(text=f'{name.lower()}(B + 1) > 0')
                self.assertEqual(result.status, 'complete')
                self.assertEqual(next(n for n in result.nodes if n['kind'] == 'function')['operator'], name)

    def test_numeric_radices_exponents_and_suffixes_are_lexical_not_values(self):
        for literal in ['2#10_01', '8#17', '16#Ab_Ff', '12', '12U', '12L', '12UL',
                        '16#FFUL', '0.1L', '.5', '1.', '1e-2', '1.5e+2L']:
            with self.subTest(literal=literal):
                result = analyze(text=literal)
                self.assertEqual(result.nodes[0]['raw_text'], literal)
                self.assertEqual(result.nodes[0]['kind'], 'number')
                self.assertNotIn('value', result.nodes[0])

    def test_invalid_numeric_spellings_never_become_valid_single_literals(self):
        for text in ['1e2e3', '1.2e3e4', '2#102', '8#8', '16#GG', '12LU', '1.2UL', '1e', '1__2']:
            with self.subTest(text=text):
                result = analyze(text=text)
                self.assertEqual(result.transitions[0]['status'], 'unsupported')
                self.assertEqual(result.nodes, [])

    def test_true_false_are_names_not_unverified_literal_aliases(self):
        result = analyze(text='TRUE AND FALSE', tags='<Tag Name="TRUE" DataType="BOOL"/>')
        self.assertEqual([r['binding_status'] for r in result.references], ['root_bound', 'unresolved'])
        self.assertEqual(result.coverage['nodes_by_kind']['number'], 0)

    def test_program_scope_shadowing_and_alias_declaration_scope(self):
        result = analyze(text='A AND AliasA', tags='<Tag Name="AliasA" TagType="Alias" AliasFor="A"/>',
                         local='<Tag Name="A" DataType="BOOL"/>')
        local_ref, alias_ref = result.references
        self.assertNotEqual(local_ref['binding']['target_id'], alias_ref['binding']['target_id'])
        self.assertEqual(len(alias_ref['binding']['alias_chain']), 1)

    def test_exact_static_array_suffixes_remain_distinct_without_bounds_claims(self):
        result = analyze(text='Array[0] = Array[00] AND Array[ 0 ] = Array[9000].0')
        self.assertEqual(result.status, 'complete')
        self.assertEqual([r['address_key'][1] for r in result.references], ['[0]', '[00]', '[ 0 ]', '[9000].0'])
        self.assertNotIn('bounds', render_sfc_conditions_json(result))

    def test_alias_failures_are_binding_gaps_not_discarded_ast(self):
        tags = '<Tag Name="Loop" TagType="Alias" AliasFor="Loop"/><Tag Name="Dynamic" TagType="Alias" AliasFor="Array[B]"/>'
        result = analyze(text='Loop AND Dynamic', tags=tags)
        self.assertEqual(result.transitions[0]['status'], 'binding_gaps')
        self.assertEqual([r['binding_status'] for r in result.references], ['alias_cycle', 'unsupported_address'])
        self.assertEqual(len(result.nodes), 3)

    def test_line_order_spans_and_comments_preserve_original_offsets(self):
        body = '<Transition ID="1"><Condition><STContent><Line Number="8">A // first</Line><Line Number="1">AND (* across</Line><Line Number="1">lines *) B /* third */</Line></STContent></Condition></Transition>'
        result = analyze(body=body)
        row = result.transitions[0]
        self.assertEqual(row['raw_text'], 'A // first\nAND (* across\nlines *) B /* third */')
        self.assertEqual(row['metadata_gaps'], ['duplicate_number', 'out_of_order_number'])
        for record in [*result.nodes, *result.references, *result.comments]:
            if record['raw_text'] is not None:
                self.assertEqual(row['raw_text'][record['start']:record['end']], record['raw_text'])
        self.assertEqual([c['kind'] for c in result.comments], ['line', 'paren_block', 'slash_block'])
        self.assertEqual(row['line_spans'][1]['start'], len('A // first\n'))

    def test_optional_one_terminal_semicolon_is_preserved_not_an_assignment(self):
        result = analyze(text='A; // end')
        self.assertEqual(result.transitions[0]['status'], 'modeled')
        self.assertEqual(result.transitions[0]['terminator_offset'], 1)
        self.assertEqual(result.nodes[0]['end'], 1)
        for text in ['A;;', 'A; B', 'A := B;', ';A']:
            with self.subTest(text=text):
                result = analyze(text=text)
                self.assertEqual(result.transitions[0]['status'], 'unsupported')
                self.assertEqual(result.nodes, [])

    def test_unknown_syntax_calls_and_constructs_have_closed_gaps_without_partial_ast(self):
        cases = {'A AND Array[B]': 'dynamic_index', 'A AND JSR(R,0);': 'instruction_call',
            'JSR(R,0);': 'instruction_call', 'A AND Unknown(B)': 'unsupported_function',
            'ABS()': 'function_arity', 'ABS(A,B)': 'function_arity', 'IF A THEN B': 'unsupported_construct',
            'A @ B': 'invalid_token', 'A AND': 'invalid_expression', 'A[0': 'invalid_address',
            'A + "/* not a comment */"': 'unsupported_string'}
        for text, reason in cases.items():
            with self.subTest(text=text):
                result = analyze(text=text)
                self.assertEqual(result.transitions[0]['reason'], reason)
                self.assertEqual((result.nodes, result.references), ([], []))
        self.assertEqual(analyze(text='"//"').comments, [])

    def test_nested_and_unterminated_comments_remain_source_evidence(self):
        for text, reason in [('A (* never closes', 'unterminated_comment'),
                             ('A /* (* nested *) */', 'nested_comment')]:
            result = analyze(text=text)
            self.assertEqual(result.transitions[0]['reason'], reason)
            self.assertEqual(len(result.comments), 1)
            self.assertEqual(result.nodes, [])
        self.assertFalse(analyze(text='A /*').comments[0]['terminated'])

    def test_empty_comment_only_missing_ambiguous_and_mixed_shapes(self):
        self.assertEqual(analyze(text='// only').transitions[0]['reason'], 'empty_expression')
        bodies = {'<Transition ID="1"/>': 'missing_condition',
            '<Transition ID="1"><Condition/><Condition/></Transition>': 'ambiguous_condition',
            '<Transition ID="1"><Condition>A<STContent><Line Number="0">B</Line></STContent></Condition></Transition>': 'unsupported_shape',
            '<Transition ID="1"><Condition><STContent><Line Number="0">A<Vendor>B</Vendor></Line></STContent></Condition></Transition>': 'unsupported_shape'}
        for body, reason in bodies.items():
            with self.subTest(reason=reason):
                result = analyze(body=body)
                self.assertEqual(result.transitions[0]['reason'], reason)
                self.assertEqual(result.nodes, [])

    def test_missing_invalid_and_huge_line_numbers_never_sort_or_convert_to_int(self):
        body = '<Transition ID="1"><Condition><STContent><Line>A AND</Line><Line Number="bad">B</Line></STContent></Condition></Transition>'
        self.assertEqual(analyze(body=body).transitions[0]['metadata_gaps'], ['invalid_number', 'missing_number'])
        result = analyze(body=expression('A', '9' * 5000))
        self.assertEqual(result.status, 'complete')

    def test_edit_contents_never_merge_or_select_active_revision(self):
        extra = '<SFCContent OnlineEditType="PendingEdits">' + expression('B') + '</SFCContent>'
        result = analyze(text='A', extra=extra)
        self.assertEqual([r['edit_kind'] for r in result.transitions], ['absent', 'PendingEdits'])
        self.assertNotEqual(result.transitions[0]['id'], result.transitions[1]['id'])
        self.assertNotEqual(result.transitions[0]['content_id'], result.transitions[1]['content_id'])

    def test_nontransition_sfc_lines_count_as_unprocessed(self):
        result = analyze(body=expression('A') + '<Step ID="3"><Action><Body><STContent><Line Number="0">B := 2;</Line></STContent></Body></Action></Step>')
        self.assertEqual(result.coverage['source_st_lines'], 2)
        self.assertEqual(result.coverage['transition_st_lines'], 1)
        self.assertEqual(result.coverage['unprocessed_st_lines'], 1)
        self.assertEqual(result.status, 'partial')

    def test_matching_root_namespace_supported_foreign_transition_line_rejected(self):
        self.assertEqual(analyze(ns='xmlns="urn:logix"').status, 'complete')
        body = '<Transition ID="1"><Condition><STContent><x:Line Number="0">A</x:Line></STContent></Condition></Transition>'
        result = analyze(body=body)
        self.assertEqual(result.transitions[0]['reason'], 'namespace_gap')
        self.assertEqual(result.references, [])

    def test_foreign_declaration_and_alias_attributes_cannot_create_exact_identity(self):
        for tag in ['<Tag Name="Foreign" x:DataType="BOOL"/>',
                    '<Tag Name="Foreign" TagType="Alias" x:AliasFor="A"/>']:
            result = analyze(text='Foreign', local=tag)
            self.assertEqual(result.references[0]['binding_status'], 'namespace_gap')
            self.assertIsNone(result.references[0]['address_key'])

    def test_non_ascii_keywords_and_names_are_not_normalized_into_supported_tokens(self):
        for text in ['A ſOR B', 'ΑND', 'Ａ', 'A\u200bAND B']:
            result = analyze(text=text)
            self.assertEqual(result.transitions[0]['reason'], 'invalid_token')
            self.assertEqual(result.nodes, [])

    def test_expression_token_depth_and_character_limits_are_retained_gaps(self):
        cases = [('MAX_EXPRESSION_CHARS', 2, 'A AND B', 'character_limit'),
                 ('MAX_EXPRESSION_TOKENS', 2, 'A AND B', 'token_limit'),
                 ('MAX_EXPRESSION_DEPTH', 2, '((A))', 'depth_limit'),
                 ('MAX_EXPRESSION_DEPTH', 2, 'A OR B OR A', 'depth_limit')]
        for constant, limit, text, reason in cases:
            with self.subTest(reason=reason), patch(f'plc_workbench.sfc_conditions.{constant}', limit):
                result = analyze(text=text)
                self.assertEqual(result.transitions[0]['reason'], reason)
                self.assertEqual(result.nodes, [])

    def test_aggregate_byte_record_and_character_limits_fail_closed(self):
        for constant, limit in [('MAX_EVIDENCE_CHARS', 2), ('MAX_SFC_CONDITION_BYTES', 100),
                                ('MAX_SFC_CONDITION_JSON_BYTES', 100), ('MAX_SFC_CONDITION_RECORDS', 2)]:
            with self.subTest(constant=constant), patch(f'plc_workbench.sfc_conditions.{constant}', limit):
                with self.assertRaisesRegex(SfcConditionError, '^SFC condition evidence is inconsistent or exceeds its limits.$'):
                    analyze(text='A AND B')

    def test_canonical_replay_rejects_each_collection_and_coverage_tampering(self):
        inputs = fixture(text='A // note')
        result = analyze_sfc_conditions(*inputs)
        for field in ('transitions', 'nodes', 'references', 'comments'):
            candidate = deepcopy(result)
            getattr(candidate, field)[0]['start' if field != 'transitions' else 'error_offset'] = 999
            with self.subTest(field=field), self.assertRaises(SfcConditionError):
                validate_sfc_conditions(*inputs, candidate)
        candidate = deepcopy(result)
        candidate.coverage['nodes_total'] = True
        with self.assertRaises(SfcConditionError):
            validate_sfc_conditions(*inputs, candidate)

    def test_input_snapshot_inventory_reference_and_structure_tampering_rejected(self):
        inputs = fixture()
        variants = [list(deepcopy(inputs)) for _ in range(4)]
        variants[0][0] = replace(inputs[0], sha256='0' * 64)
        variants[1][1].entities[0].attributes['Name'] = 'FORGED'
        variants[2][2].coverage['symbols'] = -1
        variants[3][3].elements[0]['direct_text'] = 'FORGED'
        for candidate in variants:
            with self.assertRaises(SfcConditionError):
                analyze_sfc_conditions(*candidate)

    def test_renderer_rejects_cycles_custom_values_and_oversized_payloads(self):
        for bad in [object(), {'cyclic': None}, 1.5]:
            result = deepcopy(analyze())
            if type(bad) is dict:
                bad['cyclic'] = bad
            result.transitions[0]['bad'] = bad
            with self.assertRaises(SfcConditionError):
                render_sfc_conditions_json(result)


if __name__ == '__main__':
    unittest.main()
