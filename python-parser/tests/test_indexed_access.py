"""Invented indirect operands retain uncertainty and every index-read use."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.indexed_access import (
    IndexedAccessError, analyze_indexed_access, render_indexed_access_json, validate_indexed_access,
)
from test_binding_context import capture as capture_context
from test_rack_candidates import tag, controller, program


def capture(texts=('MOV(A,B[C]);',), *, tags=None, **kwargs):
    tags = tags if tags is not None else ''.join(tag(n) for n in ('A', 'B', 'C', 'D', 'T'))
    parts = capture_context(texts, tags=tags, modules='', **kwargs)
    return (*parts, analyze_indexed_access(*parts))


class IndexedAccessTests(unittest.TestCase):
    def test_direct_write_keeps_old_gap_and_adds_symbolic_root_and_index_read(self):
        parts = capture()
        prior = [deepcopy(p.to_dict()) for p in parts[1:-1]]
        result = parts[-1]
        use = result.uses[0]
        self.assertEqual((result.status, use['kind'], use['role'], use['disposition']),
                         ('partial', 'operand', 'write', 'symbolic'))
        self.assertEqual(use['source_id'], parts[3].operands[1]['id'])
        names = {entity.id: entity.name for entity in parts[1].entities}
        self.assertEqual(names[use['root_binding']['target_id']], 'B')
        self.assertEqual(names[use['index_reads'][0]['binding']['target_id']], 'C')
        self.assertEqual(parts[-2].coverage['gaps_by_category']['non_static_array_index'], 1)
        self.assertIsNone(parts[3].operands[1]['target_id'])
        self.assertFalse(any(address['target_id'] == use['root_binding']['target_id'] for address in parts[-4].addresses))
        self.assertEqual(result.coverage['root_bound_uses'], 1)
        self.assertEqual(result.coverage['bound_index_reads'], 1)
        self.assertEqual(result.exact_element_analysis, 'not_implemented')
        validate_indexed_access(*parts)
        self.assertEqual(prior, [p.to_dict() for p in parts[1:-1]])

    def test_arithmetic_and_repeated_references_preserve_offsets_and_occurrences(self):
        raw = 'B[(C+C)*D-2]'
        parts = capture((f'MOV(A,{raw});',))
        use = parts[-1].uses[0]
        reads = use['index_reads']
        self.assertEqual([raw[r['start']:r['end']] for r in reads], ['C', 'C', 'D'])
        self.assertEqual(len({r['id'] for r in reads}), 3)
        self.assertEqual(reads[0]['binding'], reads[1]['binding'])
        self.assertEqual(use['selectors'], [{'start': 2, 'end': len(raw)-1,
                                           'group_index': 0, 'dimension_index': 0, 'dynamic': True}])
        self.assertEqual(parts[-1].coverage['index_read_occurrences'], 3)

    def test_multiple_dimensions_members_and_static_selectors_stay_in_order(self):
        raw = 'B[1,C].Member[D+1,2][C].3'
        use = capture((f'MOV(A,{raw});',))[-1].uses[0]
        self.assertEqual([raw[s['start']:s['end']] for s in use['selectors']], ['1', 'C', 'D+1', '2', 'C'])
        self.assertEqual([s['group_index'] for s in use['selectors']], [0, 0, 1, 1, 2])
        self.assertEqual([s['dimension_index'] for s in use['selectors']], [0, 1, 0, 1, 0])
        self.assertEqual([r['selector_index'] for r in use['index_reads']], [1, 2, 4])

    def test_reads_and_read_write_targets_retain_separate_roles(self):
        result = capture(('XIC(A[C])MVM(A[C],1,B[C])ONS(D[C]);',))[-1]
        self.assertEqual([u['role'] for u in result.uses], ['read', 'read', 'read_write', 'read_write'])
        self.assertEqual(result.coverage['uses_by_role']['read'], 2)
        self.assertEqual(result.coverage['uses_by_role']['read_write'], 2)

    def test_constant_arithmetic_is_not_folded_and_static_addresses_are_not_admitted(self):
        parts = capture(('MOV(A,B[1+2])MOV(A,B[3])MOV(A,B[01]);',))
        use = parts[-1].uses[0]
        self.assertEqual(len(parts[-1].uses), 1)
        self.assertEqual(use['index_reads'], [])
        self.assertEqual(parts[-1].coverage['dynamic_selectors'], 1)
        self.assertEqual(use['root_binding']['suffix'], '')
        self.assertNotIn('[0]', render_indexed_access_json(parts[-1]))
        self.assertNotIn('evaluated', render_indexed_access_json(parts[-1]))

    def test_missing_root_and_index_bindings_do_not_invent_exact_targets(self):
        result = capture(('MOV(A,Missing[Absent+Absent]);',))[-1]
        use = result.uses[0]
        self.assertEqual(use['root_binding']['status'], 'unresolved')
        self.assertIsNone(use['root_binding']['target_id'])
        self.assertEqual([r['binding']['status'] for r in use['index_reads']], ['unresolved', 'unresolved'])
        self.assertEqual(result.coverage['root_bound_uses'], 0)
        self.assertEqual(result.coverage['bound_index_reads'], 0)

    def test_alias_chains_cycles_and_invalid_composition_remain_distinct(self):
        tags = ''.join(tag(n) for n in ('A', 'B', 'C'))
        tags += tag('Good', 'B.Member') + tag('Bad', 'B.1') + tag('Cycle', 'Other') + tag('Other', 'Cycle')
        tags += tag('IndexAlias', 'C.Field') + tag('IndexBad', 'C.2')
        result = capture(('MOV(A,Good[IndexAlias])MOV(A,Bad[C])MOV(A,Cycle[C])MOV(A,B[IndexBad.Member]);',), tags=tags)[-1]
        first, second, third, fourth = result.uses
        self.assertEqual(first['root_binding']['status'], 'root_bound')
        self.assertEqual(first['root_binding']['suffix'], '.Member')
        self.assertEqual(first['index_reads'][0]['binding']['suffix'], '.Field')
        self.assertEqual(second['root_binding']['status'], 'invalid_expanded_suffix')
        self.assertIsNone(second['root_binding']['target_id'])
        self.assertEqual(third['root_binding']['status'], 'alias_cycle')
        self.assertEqual(fourth['index_reads'][0]['binding']['status'], 'invalid_expanded_suffix')
        self.assertIsNone(fourth['index_reads'][0]['binding']['target_id'])

    def test_dynamic_alias_targets_and_cpt_leaves_are_explicit_unsupported_populations(self):
        tags = ''.join(tag(n) for n in ('A', 'B', 'C')) + tag('Indirect', 'B[C]')
        result = capture(('MOV(A,Indirect)CPT(A,B[C]+B[C])Unknown(B[C]);',), tags=tags)[-1]
        self.assertEqual([u['disposition'] for u in result.uses],
                         ['alias_target_dynamic', 'unknown_role', 'expression_dynamic', 'expression_dynamic', 'alias_target_dynamic'])
        self.assertEqual(result.coverage['uses_by_kind'], {'alias': 1, 'expression': 2, 'operand': 2})
        self.assertEqual(result.coverage['symbolic_uses'], 0)
        self.assertEqual(result.coverage['index_read_occurrences'], 0)
        self.assertTrue(all(u['root_binding'] is None for u in result.uses))

    def test_unknown_role_and_nondata_do_not_gain_read_or_write_semantics(self):
        result = capture(('Unknown(B[C])JMP(B[C])MOV(A,B[C],D);',))[-1]
        self.assertEqual([u['role'] for u in result.uses], ['unknown', 'non_data', 'unknown'])
        self.assertEqual({u['disposition'] for u in result.uses}, {'unknown_role'})
        self.assertEqual(result.coverage['symbolic_uses'], 0)

    def test_malformed_unsupported_and_program_qualified_forms_are_not_partially_parsed(self):
        cases = ('B[C+]', 'B[C[D]]', 'B[SIN(C)]', 'B[C].1.Member', 'Program:P.B[C]',
                 'B[C].Member trailing', 'B[-1]', 'B[C**2]', 'B[C AND D]')
        for raw in cases:
            with self.subTest(raw=raw):
                use = capture((f'MOV(A,{raw});',))[-1].uses[0]
                self.assertEqual(use['disposition'], 'unsupported_grammar')
                self.assertEqual(use['selectors'], [])
                self.assertEqual(use['index_reads'], [])
                self.assertIsNone(use['root_binding'])

    def test_empty_and_static_sources_have_complete_empty_companion(self):
        for texts in ((), (';',), ('XIC(A',), ('MOV(A,B[1])CPT(A,B[2]+1);',),
                      ('MOV("B[C]",A)Unknown("B[C]");',)):
            with self.subTest(texts=texts):
                result = capture(texts)[-1]
                self.assertEqual(result.uses, [])
                self.assertEqual(result.status, 'complete')

    def test_alias_expansion_limit_is_not_reported_as_a_syntax_error(self):
        parts = capture(('MOV(A,Alias[C]);',), tags=tag('A')+tag('B')+tag('C')+tag('Alias','B.LongMember'))
        with patch('plc_workbench.indexed_access.MAX_ADDRESS_CHARS',10):
            use = analyze_indexed_access(*parts[:-1]).uses[0]
        self.assertEqual(use['disposition'], 'symbolic')
        self.assertEqual(use['root_binding']['status'], 'unsupported_address')
        self.assertEqual(use['root_binding']['reason'], 'expanded_suffix_limit')
        self.assertIsNone(use['root_binding']['target_id'])
        self.assertEqual(len(use['index_reads']),1)

    def test_program_shadowing_and_alias_declaration_scope_resolve_independently(self):
        from plc_workbench.source import snapshot_from_bytes, analyze_snapshot
        from plc_workbench.references import analyze_references
        from plc_workbench.calculations import analyze_calculations
        from plc_workbench.access import analyze_access
        from plc_workbench.rung_analysis import analyze_rungs
        from plc_workbench.relationships import analyze_relationships
        from plc_workbench.conditions import analyze_conditions
        from plc_workbench.binding_context import analyze_binding_context
        body = controller('', tags=tag('Root')+tag('Index')+tag('Alias','Root.Member'),
                          extra=program('MOV(1,Root[Index])MOV(1,Alias[Index]);', tag('Root')+tag('Index')))
        s = snapshot_from_bytes(('<RSLogix5000Content>'+body+'</RSLogix5000Content>').encode())
        i = analyze_snapshot(s); r = analyze_references(i); c = analyze_calculations(s,i,r)
        a = analyze_access(i,r,schema_version=4,snapshot=s,calculations=c)
        ru = analyze_rungs(s,i,r,a,c); rel = analyze_relationships(s,i,r,a,c,ru)
        co = analyze_conditions(s,i,r,a,c,ru,rel,schema_version=2)
        bc = analyze_binding_context(s,i,r,a,c,ru,rel,co)
        uses = analyze_indexed_access(s,i,r,a,c,ru,rel,co,bc).uses
        entities = {e.id:e for e in i.entities}
        direct, alias = uses
        self.assertNotEqual(direct['root_binding']['target_id'], alias['root_binding']['target_id'])
        self.assertEqual(entities[entities[direct['root_binding']['target_id']].scope_id].kind, 'program')
        self.assertEqual(entities[entities[alias['root_binding']['target_id']].scope_id].kind, 'controller')
        self.assertEqual(direct['index_reads'][0]['binding']['target_id'], alias['index_reads'][0]['binding']['target_id'])

    def test_ambiguous_index_and_root_do_not_pick_a_declaration(self):
        result = capture(('MOV(A,B[C]);',), tags=tag('A')+tag('B')+tag('B')+tag('C')+tag('C'))[-1]
        self.assertEqual(result.uses[0]['root_binding']['status'], 'ambiguous')
        self.assertEqual(result.uses[0]['index_reads'][0]['binding']['status'], 'ambiguous')

    def test_bounded_shapes_are_explicit_and_do_not_fallback_to_partial_reads(self):
        parts = capture(('MOV(A,B[(C+D)]);',))
        for constant, value in (('MAX_ADDRESS_CHARS', 3), ('MAX_TOKENS', 3), ('MAX_SELECTORS', 0), ('MAX_DEPTH', 0)):
            with self.subTest(constant=constant), patch('plc_workbench.indexed_access.'+constant, value):
                use = analyze_indexed_access(*parts[:-1]).uses[0]
                self.assertEqual(use['disposition'], 'resource_limit')
                self.assertEqual(use['index_reads'], [])
        for constant in ('MAX_RECORDS', 'MAX_EVIDENCE_IDS', 'MAX_INDEXED_BYTES'):
            with self.subTest(constant=constant), patch('plc_workbench.indexed_access.'+constant, 1), self.assertRaises(IndexedAccessError):
                analyze_indexed_access(*parts[:-1])

    def test_canonical_mutations_and_foreign_snapshot_are_rejected(self):
        parts = capture(('MOV(A,B[C+C]);',))
        mutations = (
            lambda r:r.uses[0].update(role='read'), lambda r:r.uses[0].update(disposition='unknown_role'),
            lambda r:r.uses[0]['selectors'][0].update(start=0), lambda r:r.uses[0]['index_reads'].reverse(),
            lambda r:r.uses[0]['index_reads'][0]['binding'].update(target_id=None),
            lambda r:r.coverage.update(bound_index_reads=0),
            lambda r:r.uses[0]['root_binding'].update(suffix='[0]'),
        )
        for mutate in mutations:
            result = deepcopy(parts[-1]); mutate(result)
            with self.assertRaises(IndexedAccessError): validate_indexed_access(*parts[:-1],result)
        with self.assertRaises(IndexedAccessError):
            validate_indexed_access(*parts[:-1],replace(parts[-1],schema_version=True))
        with self.assertRaises(IndexedAccessError):
            validate_indexed_access(*parts[:-1],capture(('MOV(A,B[D]);',))[-1])

    def test_forged_prerequisite_is_rejected_before_new_derivation(self):
        parts = capture()
        forged = list(deepcopy(parts[:-1]))
        forged[-1].gaps[0]['category'] = 'private_forgery'
        with patch('plc_workbench.indexed_access._derive') as derive, self.assertRaises(IndexedAccessError) as raised:
            analyze_indexed_access(*forged)
        derive.assert_not_called()
        self.assertNotIn('private_forgery',str(raised.exception))

    def test_native_renderer_exact_boundary_and_source_free_failures(self):
        result = capture()[-1]
        rendered = render_indexed_access_json(result)
        self.assertEqual(json.loads(rendered),result.to_dict())
        with patch('plc_workbench.indexed_access.MAX_INDEXED_BYTES',len(rendered)):
            self.assertEqual(render_indexed_access_json(result),rendered)
        with patch('plc_workbench.indexed_access.MAX_INDEXED_BYTES',len(rendered)-1), self.assertRaises(IndexedAccessError):
            render_indexed_access_json(result)
        class Hostile(list):
            def __iter__(self): raise AssertionError('Foreign hook invoked')
        cyclic=[];cyclic.append(cyclic)
        for bad in (Hostile(),cyclic,{'private':object()}):
            with self.assertRaises(IndexedAccessError): render_indexed_access_json(replace(result,uses=bad))


if __name__ == '__main__': unittest.main()
