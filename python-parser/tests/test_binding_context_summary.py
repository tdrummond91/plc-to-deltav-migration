"""Only closed binding-context populations may cross the feedback boundary."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.binding_context_summary import (
    BindingContextSummaryError, build_binding_context_summary,
    render_binding_context_summary, validate_binding_context_summary,
)
from test_binding_context import capture
from test_rack_candidates import tag


def summary(*args, **kwargs):
    return build_binding_context_summary(*capture(*args, **kwargs))


class BindingContextSummaryTests(unittest.TestCase):
    def test_closed_small_source_free_report_and_distinct_slot_counts(self):
        value = summary(('EQU(Input,Output)OTE(Output);',))
        text = render_binding_context_summary(value)
        self.assertLessEqual(len(text),4096)
        self.assertEqual(json.loads(text),value)
        self.assertEqual(text,render_binding_context_summary(deepcopy(value)))
        self.assertEqual(value['coverage']['predicate_gap_uses'],2)
        self.assertEqual(value['coverage']['predicate_gap_occurrences'],1)
        for private in ('Local:3','Input','Output','snapshot','source_id'):
            self.assertNotIn(private,text)
        self.assertNotRegex(text,r'(?:candidate_address_|operand_)[0-9a-f]{64}')

    def test_all_edge_populations_validate(self):
        for texts in ((),(';',),('XIC(A',),('XIC(Input[Index]);',),('OTE(123);',),
                      ('CPT(Missing,Input+Input)MSG(Input);',),('XIC(Missing)OTE(Output);',),
                      ('XIC(Input)XIC(Output)OTE(Output);',)):
            with self.subTest(texts=texts): validate_binding_context_summary(summary(texts))
        validate_binding_context_summary(summary(('XIC(Bit.Member)CPT(A,Bit.Member+1);',),tags=tag('A')+tag('Bit','A.1')))
        validate_binding_context_summary(summary(('XIC(Bit.Member);',),tags=tag('Bit','Local:3:I.1')))

    def test_closed_keys_constants_and_native_count_types(self):
        base = summary()
        mutations = (
            lambda r:r.update(private='secret'), lambda r:r.update(schema_version=True),
            lambda r:r.update(backing_mapping='verified'), lambda r:r.update(engineering_review='approved'),
            lambda r:r['coverage'].update(private='secret'),
            lambda r:r['coverage']['gaps_by_category'].update(PrivateRoot=0),
            lambda r:r['coverage'].update(gap_uses_total=True),
            lambda r:r['coverage'].update(gap_uses_total=2.0),
            lambda r:r['coverage'].update(gap_uses_total=-1),
            lambda r:r['coverage'].update(source_operands=250001),
            lambda r:r.update(status='complete'),
            lambda r:r['tool_revision'].update(commit='PrivateRevision'),
        )
        for mutate in mutations:
            value=deepcopy(base);mutate(value)
            with self.assertRaises(BindingContextSummaryError):render_binding_context_summary(value)

    def test_conservation_and_candidate_bounds_reject_inconsistent_counts(self):
        base=summary()
        mutations=(
            lambda c:c.update(gap_uses_total=1), lambda c:c.update(operand_binding_gaps=0),
            lambda c:c.update(predicate_gap_uses=2), lambda c:c.update(predicate_gap_occurrences=0),
            lambda c:c.update(output_gap_occurrences=2), lambda c:c.update(candidate_addresses=3),
            lambda c:c.update(candidate_roots=0), lambda c:c.update(candidate_address_uses=0),
            lambda c:c.update(source_operands=0), lambda c:c.update(source_instructions=0),
            lambda c:c.update(source_rungs=0), lambda c:c['gaps_by_kind'].update(expression=1),
            lambda c:c['gaps_by_role'].update(read=0),
            lambda c:c['predicate_gap_categories'].update(rack_unique_candidate=0),
            lambda c:c['output_gap_categories'].update(rack_unique_candidate=0),
            lambda c:c['candidate_address_profiles'].update(read_only=0),
            lambda c:c['candidate_address_directions'].update(input=0),
            lambda c:c['gaps_by_category'].update(rack_unique_candidate=1,invalid_expanded_suffix=1),
        )
        for mutate in mutations:
            value=deepcopy(base);mutate(value['coverage'])
            with self.assertRaises(BindingContextSummaryError):validate_binding_context_summary(value)

    def test_category_subpopulations_cannot_move_to_a_different_gap(self):
        value=summary(('XIC(Input)OTE(Missing);',))
        c=value['coverage'];c['predicate_gap_categories'].update(rack_unique_candidate=0,undeclared_root=1)
        with self.assertRaises(BindingContextSummaryError):validate_binding_context_summary(value)

    def test_logical_profiles_require_corresponding_read_and_write_uses(self):
        for text, profile in (('XIC(Input);','write_only'),('OTE(Output);','read_only')):
            value=summary((text,))
            value['coverage']['candidate_address_profiles']={
                'read_only':int(profile=='read_only'),'write_only':int(profile=='write_only'),'read_and_write':0}
            with self.assertRaises(BindingContextSummaryError):validate_binding_context_summary(value)
        # Each mixed group needs either a read-write use or separate read/write uses.
        value=summary(('XIC(Input)OTE(Output);',))
        value['coverage']['candidate_address_profiles']={'read_only':0,'write_only':0,'read_and_write':2}
        with self.assertRaises(BindingContextSummaryError):validate_binding_context_summary(value)

    def test_literal_write_gap_cannot_be_swapped_into_predicate_counts(self):
        value=summary(('XIC(Missing)OTE(123);',))
        value['coverage']['predicate_gap_categories'].update(undeclared_root=0,non_address_value=1)
        value['coverage']['output_gap_categories'].update(undeclared_root=1,non_address_value=0)
        with self.assertRaises(BindingContextSummaryError):validate_binding_context_summary(value)

    def test_expression_read_cannot_support_a_candidate_address_profile(self):
        value=summary(('OTE(Output)CPT(A,Missing+1);',),tags=tag('Output','Local:3:O.Data')+tag('A'))
        value['coverage']['candidate_address_profiles'].update(write_only=0,read_only=1)
        with self.assertRaises(BindingContextSummaryError):validate_binding_context_summary(value)

    def test_canonical_build_rejects_forgery_before_publishing(self):
        parts=capture();bad=deepcopy(parts[-1]);bad.gaps[0]['category']='rack_no_match'
        with self.assertRaises(BindingContextSummaryError):build_binding_context_summary(*parts[:-1],bad)
        with self.assertRaises(BindingContextSummaryError):build_binding_context_summary(*parts[:-1],replace(parts[-1],schema_version=True))

    def test_revision_is_copied_and_boundary_is_exact(self):
        revision={'commit':'a'*40,'worktree':'clean'}
        value=build_binding_context_summary(*capture(),revision=revision)
        revision['commit']='b'*40
        self.assertEqual(value['tool_revision']['commit'],'a'*40)
        text=render_binding_context_summary(value)
        with patch('plc_workbench.binding_context_summary.MAX_REPORT_BYTES',len(text)):
            self.assertEqual(render_binding_context_summary(value),text)
        with patch('plc_workbench.binding_context_summary.MAX_REPORT_BYTES',len(text)-1),self.assertRaises(BindingContextSummaryError):
            render_binding_context_summary(value)


if __name__ == '__main__':unittest.main()
