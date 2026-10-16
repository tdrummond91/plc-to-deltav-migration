"""Closed AOI aggregate reports reject source leakage and inconsistent counts."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.aoi_body_summary import (
    AoiBodySummaryError, build_aoi_body_summary, render_aoi_body_summary,
    validate_aoi_body_summary,
)
from test_aoi_body_context import capture, document


def summary(*args, **kwargs):
    return build_aoi_body_summary(*capture(*args, **kwargs))


class AoiBodySummaryTests(unittest.TestCase):
    def test_small_closed_deterministic_counts_expose_no_source_identifiers(self):
        value = summary()
        text = render_aoi_body_summary(value)
        self.assertEqual(json.loads(text), value)
        self.assertEqual(text, render_aoi_body_summary(deepcopy(value)))
        self.assertLessEqual(len(text), 4096)
        for private in ('Widget', 'Instance', 'Input', 'snapshot', 'source_id', 'instruction_id', 'declaration_id'):
            self.assertNotIn(private, text)
        self.assertEqual(value['coverage']['body_symbol_operand_uses'], 4)

    def test_missing_literal_member_alias_and_namespace_populations_validate(self):
        cases = (document(calls='Widget();'), document(calls='Widget(3);'),
                 document(calls='Mystery(Instance);'), document(calls='Widget(Instance.Member);'),
                 document(calls='Widget(Instance[2]);'), document(calls='Widget(Unknown);'),
                 document(definition_attributes='Protected="true"'),
                 document(body='Widget(Local);'), '<Controller Name="Empty"/>')
        for xml in cases:
            with self.subTest(xml=xml): validate_aoi_body_summary(summary(xml))
        xml = document().replace('Name="Instance"', 'x:Name="Instance"')
        validate_aoi_body_summary(summary(xml, 'xmlns:x="urn:extension"'))

    def test_closed_keys_types_and_constants_reject_private_extensions(self):
        base = summary()
        mutations = (
            lambda x: x.update(private_name='secret'),
            lambda x: x.update(schema_version=True),
            lambda x: x.update(execution='modeled'),
            lambda x: x.update(call_validation='validated'),
            lambda x: x['coverage'].update(Widget=1),
            lambda x: x['coverage']['instance_address_shape'].update(Instance=0),
            lambda x: x['coverage'].update(calls_total=True),
            lambda x: x['coverage'].update(calls_total=1.0),
            lambda x: x['coverage'].update(source_rungs=-1),
            lambda x: x['coverage'].update(source_rungs=250001),
            lambda x: x.update(status='partial'),
            lambda x: x['tool_revision'].update(commit='private'),
        )
        for mutate in mutations:
            value = deepcopy(base); mutate(value)
            with self.assertRaises(AoiBodySummaryError): render_aoi_body_summary(value)

    def test_population_conservation_and_subset_bounds_are_enforced(self):
        base = summary()
        mutations = (
            lambda c: c.update(body_rungs_total=2),
            lambda c: c.update(body_instructions_total=2),
            lambda c: c.update(body_operands_total=4),
            lambda c: c.update(source_rungs=0),
            lambda c: c.update(source_instructions=0),
            lambda c: c.update(source_operands=0),
            lambda c: c.update(source_expression_uses=0),
            lambda c: c.update(body_symbol_operand_uses=6),
            lambda c: c.update(body_symbol_expression_uses=3),
            lambda c: c.update(definitions_total=0),
            lambda c: c.update(definitions_with_body_gaps=2),
            lambda c: c.update(symbols_with_context_gaps=5),
            lambda c: c.update(routines_total=0),
            lambda c: c['body_operands_by_role'].update(read=99),
            lambda c: c['body_operands_by_binding'].update(root_bound=99),
            lambda c: c['instance_address_shape'].update(root=0, literal=1),
            lambda c: c['instance_datatype_status'].update(matching_type_name=0, member_deferred=1),
        )
        for mutate in mutations:
            value = deepcopy(base); mutate(value['coverage'])
            with self.assertRaises(AoiBodySummaryError): validate_aoi_body_summary(value)

    def test_source_authentication_is_required_before_summary_publication(self):
        parts = capture()
        bad = deepcopy(parts[-1]); bad.coverage['body_symbol_operand_uses'] = 3
        with self.assertRaises(AoiBodySummaryError): build_aoi_body_summary(*parts[:-1], bad)
        bad = deepcopy(parts[-2]); bad.calls.clear()
        with self.assertRaises(AoiBodySummaryError): build_aoi_body_summary(*parts[:-2], bad, parts[-1])

    def test_revision_copy_and_render_size_cap(self):
        revision = {'commit': 'a' * 40, 'worktree': 'clean'}
        result = build_aoi_body_summary(*capture(), revision=revision)
        revision['commit'] = 'b' * 40
        self.assertEqual(result['tool_revision']['commit'], 'a' * 40)
        with patch('plc_workbench.aoi_body_summary.MAX_REPORT_BYTES', 100):
            with self.assertRaises(AoiBodySummaryError): render_aoi_body_summary(result)


if __name__ == '__main__':
    unittest.main()
