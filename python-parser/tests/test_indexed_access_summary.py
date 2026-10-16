"""Only closed integer counts cross the indexed-context sharing boundary."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.indexed_access_summary import (
    IndexedAccessSummaryError, build_indexed_access_summary,
    render_indexed_access_summary, validate_indexed_access_summary,
)
from test_indexed_access import capture
from test_rack_candidates import tag


def summary(*args, **kwargs):
    return build_indexed_access_summary(*capture(*args, **kwargs))


class IndexedAccessSummaryTests(unittest.TestCase):
    def test_closed_source_free_counts_fit_small_public_contract(self):
        value = summary(('MOV(A,B[C+C]);',))
        text = render_indexed_access_summary(value)
        self.assertEqual(json.loads(text), value)
        self.assertLessEqual(len(text),4096)
        self.assertEqual(value['coverage']['symbolic_uses'],1)
        self.assertEqual(value['coverage']['index_read_occurrences'],2)
        self.assertEqual(value['coverage']['bound_index_reads'],2)
        for forbidden in ('B[C+C]', 'snapshot', 'source_id', 'target_id', 'alias_chain', 'suffix'):
            # "invalid_expanded_suffix" is a fixed category, never source text.
            if forbidden == 'suffix':
                continue
            self.assertNotIn(forbidden,text)
        self.assertNotRegex(text,r'(?:indexed_use_|index_read_|operand_|entity_)[0-9a-f]{64}')

    def test_unsupported_and_empty_populations_validate(self):
        for texts in ((), ('MOV(A,B[1]);',), ('XIC(A',), ('MOV(A,B[1+2]);',),
                      ('MOV(A,B[C+C])MOV(A,D[C]);',), ('Unknown(B[C])JMP(B[C]);',),
                      ('CPT(A,B[C]+B[C]);',), ('CPT(A,UNKNOWN(B[C]));',),
                      ('MOV(A,Missing[Absent]);',), ('MOV(A,B[C+]);',)):
            with self.subTest(texts=texts): validate_indexed_access_summary(summary(texts))
        validate_indexed_access_summary(summary(('MOV(A,Indirect);',),
                                                tags=tag('A')+tag('B')+tag('C')+tag('Indirect','B[C]')))

    def test_public_map_keys_constants_and_native_integer_types_are_closed(self):
        base = summary()
        mutations = (
            lambda r:r.update(private='secret'), lambda r:r.update(schema_version=True),
            lambda r:r.update(exact_element_analysis='proved'),
            lambda r:r.update(range_analysis='verified'), lambda r:r.update(engineering_review='approved'),
            lambda r:r['coverage'].update(secret='private'),
            lambda r:r['coverage']['root_bindings'].update(PlantTag=0),
            lambda r:r['coverage'].update(symbolic_uses=True),
            lambda r:r['coverage'].update(symbolic_uses=1.0),
            lambda r:r['coverage'].update(symbolic_uses=-1),
            lambda r:r['coverage'].update(source_operands=250001),
            lambda r:r.update(status='complete'),
            lambda r:r['tool_revision'].update(commit='private'),
        )
        for mutate in mutations:
            value = deepcopy(base); mutate(value)
            with self.assertRaises(IndexedAccessSummaryError): render_indexed_access_summary(value)

    def test_conservation_and_index_population_bounds_reject_impossible_counts(self):
        base = summary(('MOV(A,B[C+C]);',))
        mutations = (
            lambda c:c.update(uses_total=0), lambda c:c.update(symbolic_uses=0),
            lambda c:c.update(root_bound_uses=0), lambda c:c.update(bound_index_reads=0),
            lambda c:c.update(selectors_total=0), lambda c:c.update(dynamic_selectors=0),
            lambda c:c.update(index_read_occurrences=1), lambda c:c.update(selectors_total=65),
            lambda c:c['uses_by_kind'].update(operand=0), lambda c:c['uses_by_role'].update(write=0),
            lambda c:c['uses_by_disposition'].update(symbolic=0),
            lambda c:c['root_bindings'].update(unresolved=1),
            lambda c:c['index_bindings'].update(root_bound=3),
            lambda c:c.update(source_rungs=0), lambda c:c.update(source_instructions=0),
            lambda c:c.update(source_operands=0),
        )
        for mutate in mutations:
            value = deepcopy(base); mutate(value['coverage'])
            with self.assertRaises(IndexedAccessSummaryError): validate_indexed_access_summary(value)

    def test_unknown_and_expression_categories_cannot_invent_known_access_roles(self):
        value = summary(('Unknown(B[C]);',))
        value['coverage']['uses_by_role'].update(unknown=0,write=1)
        with self.assertRaises(IndexedAccessSummaryError): validate_indexed_access_summary(value)
        value = summary(('CPT(A,B[C]);',))
        value['coverage']['uses_by_role'].update(read=0,write=1)
        with self.assertRaises(IndexedAccessSummaryError): validate_indexed_access_summary(value)
        value = summary(('CPT(A,UNKNOWN(B[C]));',))
        value['coverage']['uses_by_role'].update(expression_read=0,read=1)
        with self.assertRaises(IndexedAccessSummaryError): validate_indexed_access_summary(value)

    def test_canonical_build_rejects_forged_bindings_or_flags(self):
        parts = capture()
        result = deepcopy(parts[-1]); result.uses[0]['root_binding']['target_id'] = 'private'
        with self.assertRaises(IndexedAccessSummaryError): build_indexed_access_summary(*parts[:-1],result)
        with self.assertRaises(IndexedAccessSummaryError):
            build_indexed_access_summary(*parts[:-1],replace(parts[-1],exact_element_analysis='verified'))

    def test_revision_copy_and_exact_byte_limit(self):
        revision = {'commit':'a'*40,'worktree':'clean'}
        value = build_indexed_access_summary(*capture(),revision=revision)
        revision['commit'] = 'b'*40
        self.assertEqual(value['tool_revision']['commit'],'a'*40)
        text = render_indexed_access_summary(value)
        with patch('plc_workbench.indexed_access_summary.MAX_REPORT_BYTES',len(text)):
            self.assertEqual(render_indexed_access_summary(value),text)
        with patch('plc_workbench.indexed_access_summary.MAX_REPORT_BYTES',len(text)-1), self.assertRaises(IndexedAccessSummaryError):
            render_indexed_access_summary(value)


if __name__ == '__main__': unittest.main()
