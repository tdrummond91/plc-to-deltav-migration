"""Invented gaps test scope, suffix composition and candidate-only identities."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.binding_context import (
    BindingContextError, analyze_binding_context, render_binding_context_json, validate_binding_context,
)
from plc_workbench.conditions import analyze_conditions
from test_conditions import capture as capture_conditions
from test_rack_candidates import LOCAL, card, controller, program, tag


def capture(texts=('XIC(Input)OTE(Output);',), *, tags=None, modules=None, **kwargs):
    tags = tags if tags is not None else tag('Input', 'Local:3:I.Data.1') + tag('Output', 'Local:3:O.Data.2')
    modules = modules if modules is not None else '<Modules>' + LOCAL + card() + '</Modules>'
    parts = capture_conditions(texts, schema_version=2, tags=tags, modules=modules, **kwargs)
    return (*parts, analyze_binding_context(*parts))


class BindingContextTests(unittest.TestCase):
    def test_candidate_joins_each_gap_without_changing_bindings_or_conditions(self):
        parts = capture()
        snapshots = [deepcopy(x.to_dict()) for x in parts[1:-1]]
        result = parts[-1]
        self.assertEqual([r['category'] for r in result.gaps], ['rack_unique_candidate'] * 2)
        self.assertEqual([r['source_id'] for r in result.gaps], [r['id'] for r in parts[3].operands])
        self.assertTrue(result.gaps[0]['predicate_node_id'])
        self.assertIsNone(result.gaps[0]['output_id'])
        self.assertTrue(result.gaps[1]['output_id'])
        self.assertEqual(result.coverage['predicate_gap_occurrences'], 1)
        self.assertEqual(result.coverage['output_gap_occurrences'], 1)
        self.assertEqual(result.coverage['candidate_address_directions'], {'input': 1, 'output': 1})
        self.assertEqual([r['suffix'] for r in result.logical_addresses], ['.Data.1', '.Data.2'])
        self.assertEqual(parts[-2].outputs[0]['guard_status'], 'binding_gaps')
        self.assertEqual(parts[-2].outputs[0]['target_status'], 'unbound')
        self.assertEqual(parts[-3].addresses, [])
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.backing_mapping, 'not_analyzed')
        validate_binding_context(*parts)
        self.assertEqual(snapshots, [x.to_dict() for x in parts[1:-1]])

    def test_shared_candidate_suffix_groups_occurrences_and_roles_not_direction(self):
        parts = capture(('XIC(Output)OTE(Output)MOV(Output,Output)XIC(Local:3:O.Data.2);',))
        result = parts[-1]
        self.assertEqual(len(result.logical_addresses), 1)
        address = result.logical_addresses[0]
        self.assertEqual(address['profile'], 'read_and_write')
        self.assertEqual(len(address['operand_ids']), 5)
        self.assertEqual(result.coverage['gaps_by_role'], {'read': 3, 'write': 2, 'read_write': 0})
        self.assertEqual(result.coverage['candidate_address_directions'], {'input': 0, 'output': 1})
        self.assertEqual(result.coverage['candidate_roots'], 1)

    def test_alias_composition_rejects_invalid_suffix_even_with_unique_root(self):
        tags = tag('Bit', 'Local:3:I.1') + tag('Good', 'Local:3:I.Data')
        result = capture(('XIC(Bit.Member)XIC(Good[1].2);',), tags=tags)[-1]
        bad, good = result.gaps
        self.assertEqual(bad['category'], 'rack_suffix_invalid')
        self.assertIsNotNone(bad['candidate_id'])
        self.assertIsNone(bad['candidate_address_id'])
        self.assertEqual(good['category'], 'rack_unique_candidate')
        self.assertEqual(result.logical_addresses[0]['suffix'], '.Data[1].2')

    def test_exact_suffix_spelling_and_candidate_identity_remain_separate(self):
        modules = '<Modules>' + LOCAL + card('One', '3') + card('Two', '4') + '</Modules>'
        result = capture(('XIC(Local:3:I.Data[1])XIC(Local:3:I.Data[01])XIC(Local:3:I.data[1])XIC(Local:4:I.Data[1]);',), modules=modules)[-1]
        self.assertEqual(len(result.logical_addresses), 4)
        self.assertEqual(result.coverage['candidate_roots'], 2)
        self.assertEqual(len({r['id'] for r in result.logical_addresses}), 4)

    def test_ambiguous_missing_unnamed_and_outside_scope_never_group(self):
        cases = (
            (LOCAL + card(children='<InAliasTag/><InAliasTag/>'), 'rack_ambiguous_candidate'),
            (LOCAL + card(parent='Absent'), 'rack_names_unavailable'),
            (LOCAL, 'rack_no_match'),
        )
        for modules, category in cases:
            with self.subTest(category=category):
                result = capture(('XIC(Local:3:I.Data);',), modules='<Modules>'+modules+'</Modules>')[-1]
                self.assertEqual(result.gaps[0]['category'], category)
                self.assertIsNone(result.gaps[0]['candidate_id'])
                self.assertEqual(result.logical_addresses, [])

    def test_ordinary_symbol_shadows_candidate_and_never_merges_with_it(self):
        result = capture(('XIC(Local:3:I.Data)OTE(Local:3:O.Data);',), tags=tag('Local:3:I'))[-1]
        self.assertEqual(len(result.gaps), 1)
        self.assertEqual(result.coverage['candidate_address_directions'], {'input': 0, 'output': 1})

    def test_alias_lookup_uses_controller_declaration_scope(self):
        # A program's similarly named declaration cannot retarget a controller alias.
        from plc_workbench.source import snapshot_from_bytes, analyze_snapshot
        from plc_workbench.references import analyze_references
        from plc_workbench.calculations import analyze_calculations
        from plc_workbench.access import analyze_access
        from plc_workbench.rung_analysis import analyze_rungs
        from plc_workbench.relationships import analyze_relationships
        body = controller(LOCAL + card(), tags=tag('First', 'Second') + tag('Second', 'Local:3:I.Data'),
                          extra=program('XIC(First);', tag('Second')))
        # A second controller cannot see the first controller's rack roots.
        body += controller('', 'XIC(Local:3:I.Data);', name='Other')
        s = snapshot_from_bytes(('<RSLogix5000Content>'+body+'</RSLogix5000Content>').encode())
        i = analyze_snapshot(s); r = analyze_references(i); c = analyze_calculations(s,i,r)
        a = analyze_access(i,r,schema_version=4,snapshot=s,calculations=c)
        ru = analyze_rungs(s,i,r,a,c); re = analyze_relationships(s,i,r,a,c,ru)
        co = analyze_conditions(s,i,r,a,c,ru,re,schema_version=2)
        result = analyze_binding_context(s,i,r,a,c,ru,re,co)
        self.assertEqual([g['category'] for g in result.gaps], ['rack_unique_candidate','rack_outside_scope'])
        self.assertEqual(len(result.logical_addresses), 1)

    def test_dynamic_indexes_missing_roots_and_literal_targets_remain_distinct(self):
        result = capture(('XIC(Input[Index])XIC(Missing)OTE(123)TON(123,?,?);',))[-1]
        self.assertEqual([g['category'] for g in result.gaps],
                         ['non_static_array_index','undeclared_root','non_address_value','non_address_value'])
        self.assertEqual(result.coverage['predicate_gap_occurrences'], 2)
        self.assertEqual(result.coverage['output_gap_occurrences'], 1)
        self.assertEqual(result.logical_addresses, [])

    def test_expression_and_extended_access_without_original_match_stay_explicit(self):
        parts = capture(('CPT(Missing,Input+Input)MSG(Input);',))
        result = parts[-1]
        self.assertEqual([g['kind'] for g in result.gaps], ['operand','operand','expression','expression'])
        self.assertEqual([g['category'] for g in result.gaps],
                         ['undeclared_root','rack_context_unavailable','rack_context_unavailable','rack_context_unavailable'])
        self.assertEqual(result.coverage['expression_binding_gaps'], 2)
        self.assertEqual(result.coverage['operand_binding_gaps'], parts[3].coverage['access_gap_operands'])

    def test_bound_composed_identity_gaps_are_not_candidate_matches(self):
        parts = capture(('XIC(Bit.Member)CPT(A,Bit.Member+1)OTE(Bit.Member);',), tags=tag('A')+tag('Bit','A.1'))
        result = parts[-1]
        self.assertEqual(result.coverage['operand_identity_gaps'], 2)
        self.assertEqual(result.coverage['expression_identity_gaps'], 1)
        self.assertEqual(result.coverage['operand_binding_gaps'], 0)
        self.assertEqual({g['category'] for g in result.gaps}, {'invalid_expanded_suffix'})

    def test_alias_cycles_and_ambiguous_roots_are_distinct(self):
        tags = tag('A','B')+tag('B','A')+tag('Dup')+tag('Dup')
        result = capture(('XIC(A)OTE(Dup);',), tags=tags)[-1]
        self.assertEqual([g['category'] for g in result.gaps], ['alias_cycle','ambiguous_root'])

    def test_empty_and_nondata_unknown_slots_do_not_invent_binding_gaps(self):
        for texts in ((), (';',), ('XIC(A',), ('Unknown(Missing);',), ('JMP(Missing);',), ('EQU(1,2)XIC(S:FS);',)):
            with self.subTest(texts=texts):
                result = capture(texts)[-1]
                self.assertEqual(result.gaps, [])
                self.assertEqual(result.status, 'complete')

    def test_multiple_gap_slots_in_one_predicate_count_one_occurrence(self):
        result = capture(('EQU(Input,Output)OTE(Output);',))[-1]
        self.assertEqual(result.coverage['predicate_gap_uses'], 2)
        self.assertEqual(result.coverage['predicate_gap_occurrences'], 1)
        self.assertEqual(result.coverage['output_gap_occurrences'], 1)

    def test_canonical_mutations_and_foreign_snapshot_are_rejected(self):
        parts = capture()
        mutations = (
            lambda r: r.gaps.reverse(), lambda r: r.gaps[0].update(category='rack_no_match'),
            lambda r: r.gaps[0].update(candidate_id=r.gaps[1]['candidate_id']),
            lambda r: r.gaps[0].update(predicate_node_id=None),
            lambda r: r.logical_addresses[0].update(suffix='.Other'),
            lambda r: r.logical_addresses[0]['operand_ids'].clear(),
            lambda r: r.coverage.update(gap_uses_total=0),
        )
        for mutate in mutations:
            result = deepcopy(parts[-1]); mutate(result)
            with self.assertRaises(BindingContextError): validate_binding_context(*parts[:-1],result)
        with self.assertRaises(BindingContextError):
            validate_binding_context(*parts[:-1],replace(parts[-1],schema_version=True))
        foreign = capture(('XIC(Input)OTL(Output);',))[-1]
        with self.assertRaises(BindingContextError): validate_binding_context(*parts[:-1],foreign)

    def test_prerequisite_forgery_fails_before_derivation(self):
        parts = capture()
        forged = list(deepcopy(parts[:-1]))
        forged[2].rack_candidates['matches']['alias_operands'][0]['candidate_id'] = 'PrivateForgery'
        with patch('plc_workbench.binding_context._derive') as derive, self.assertRaises(BindingContextError) as raised:
            analyze_binding_context(*forged)
        derive.assert_not_called()
        self.assertNotIn('PrivateForgery',str(raised.exception))
        legacy = analyze_conditions(*parts[:-2])
        with self.assertRaises(BindingContextError): analyze_binding_context(*parts[:-2],legacy)

    def test_native_renderer_and_exact_byte_boundary(self):
        result = capture()[-1]
        rendered = render_binding_context_json(result)
        self.assertEqual(json.loads(rendered),result.to_dict())
        with patch('plc_workbench.binding_context.MAX_CONTEXT_BYTES',len(rendered)):
            self.assertEqual(render_binding_context_json(result),rendered)
        with patch('plc_workbench.binding_context.MAX_CONTEXT_BYTES',len(rendered)-1), self.assertRaises(BindingContextError):
            render_binding_context_json(result)
        class Hostile(list):
            def __iter__(self): raise AssertionError('Foreign hook invoked')
        cyclic=[];cyclic.append(cyclic)
        for bad in (Hostile(),cyclic,{'private':object()}):
            with self.assertRaises(BindingContextError): render_binding_context_json(replace(result,gaps=bad))

    def test_many_occurrences_share_one_group_without_copied_alias_chains(self):
        parts = capture(tuple('XIC(Input);' for _ in range(150)))
        result = parts[-1]
        self.assertEqual(len(result.logical_addresses),1)
        self.assertEqual(len(result.logical_addresses[0]['operand_ids']),150)
        self.assertLess(len(render_binding_context_json(result)),125_000)
        self.assertNotIn('alias_chain',render_binding_context_json(result))
        for name in ('MAX_RECORDS','MAX_CONTEXT_BYTES'):
            with patch('plc_workbench.binding_context.'+name,1), self.assertRaises(BindingContextError):
                analyze_binding_context(*parts[:-1])


if __name__ == '__main__': unittest.main()
