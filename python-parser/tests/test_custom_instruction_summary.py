"""Public declaration-context reports contain only bounded closed counts."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.custom_instruction_summary import (
    CustomInstructionSummaryError, build_custom_instruction_summary,
    render_custom_instruction_summary, validate_custom_instruction_summary,
)
from test_custom_instruction_context import capture, controller, definition


def summary(*args, **kwargs):
    return build_custom_instruction_summary(*capture(*args, **kwargs))


class CustomInstructionSummaryTests(unittest.TestCase):
    def test_small_closed_report_never_exposes_names_source_or_identifiers(self):
        value = summary()
        text = render_custom_instruction_summary(value)
        self.assertEqual(json.loads(text), value)
        self.assertLessEqual(len(text), 4096)
        self.assertEqual(text, render_custom_instruction_summary(deepcopy(value)))
        for private in ('InventedAOI', 'InventedController', 'Argument', 'snapshot', 'source_id', 'declaration_id'):
            self.assertNotIn(private, text)
        self.assertNotRegex(text, r'(?:aoi_|instruction_|rung_)[0-9a-f]{64}')
        self.assertEqual(value['coverage']['unknown_family_calls'], 1)

    def test_missing_ambiguous_invalid_and_unsupported_populations_validate(self):
        cases = ('', controller(definitions=''), controller(definition() + definition()),
                 controller(definition('Invalid-Name')), controller(text='XIC(A)OTE(B);'),
                 controller(definition(children='')), controller(definition(children='<EncodedData>secret</EncodedData>')))
        for body in cases:
            with self.subTest(body=body): validate_custom_instruction_summary(summary(body))
        namespaced = controller(definition().replace('Name="InventedAOI"', 'x:Name="InventedAOI"'))
        validate_custom_instruction_summary(summary(namespaced, 'xmlns:x="urn:extension"'))
        colliding = controller(definition(attributes='SourceKey="Secret"') + definition(attributes='x:Marker="Secret"'))
        validate_custom_instruction_summary(summary(colliding, 'xmlns:x="urn:extension"'))

    def test_closed_keys_and_constants_prevent_private_fields(self):
        base = summary()
        mutations = (
            lambda value: value.update(raw_name='Secret'), lambda value: value.update(schema_version=True),
            lambda value: value.update(effects='analyzed'), lambda value: value.update(parameter_roles='assigned'),
            lambda value: value.update(call_validation='verified'),
            lambda value: value['coverage'].update(name='Secret'),
            lambda value: value['coverage']['calls_by_status'].update(Secret=0),
            lambda value: value['coverage'].update(unknown_family_calls=True),
            lambda value: value['coverage'].update(unknown_family_calls=1.0),
            lambda value: value['coverage'].update(unknown_family_calls=-1),
            lambda value: value['coverage'].update(source_rungs=250001),
            lambda value: value['tool_revision'].update(commit='PrivateCommit'),
            lambda value: value.update(status='partial'),
        )
        for mutate in mutations:
            value = deepcopy(base); mutate(value)
            with self.assertRaises(CustomInstructionSummaryError): render_custom_instruction_summary(value)

    def test_conservation_bounds_reject_inconsistent_public_populations(self):
        base = summary()
        mutations = (
            lambda c: c.update(unknown_family_calls=2), lambda c: c.update(definitions_total=2),
            lambda c: c.update(parameters_total=2), lambda c: c.update(routines_total=2),
            lambda c: c.update(unique_candidate_definitions_called=0),
            lambda c: c.update(unique_candidate_definitions_called=2),
            lambda c: c.update(definitions_with_encoded_regions=1),
            lambda c: c.update(encoded_regions_total=1),
            lambda c: c.update(definitions_with_protection_markers=2),
            lambda c: c.update(source_rungs=0), lambda c: c.update(source_instructions=0),
            lambda c: c['parameter_required'].update(true=0),
            lambda c: c['routine_languages'].update(rll=0),
            lambda c: c['routine_contents'].update(rll=0),
        )
        for mutate in mutations:
            value = deepcopy(base); mutate(value['coverage'])
            with self.assertRaises(CustomInstructionSummaryError): validate_custom_instruction_summary(value)

    def test_parameter_unavailable_populations_must_move_together(self):
        value = summary()
        value['coverage']['parameter_usage'].update(input=0, unsupported_context=1)
        with self.assertRaises(CustomInstructionSummaryError): validate_custom_instruction_summary(value)
        value = summary()
        value['coverage']['routine_languages'].update(rll=0, unsupported_context=1)
        with self.assertRaises(CustomInstructionSummaryError): validate_custom_instruction_summary(value)

    def test_ambiguous_call_requires_multiple_ambiguous_definitions(self):
        value = summary()
        value['coverage']['calls_by_status'].update(unique_candidate=0, ambiguous_declaration=1)
        value['coverage']['unique_candidate_definitions_called'] = 0
        value['status'] = 'partial'
        with self.assertRaises(CustomInstructionSummaryError): validate_custom_instruction_summary(value)
        value['coverage']['definitions_by_status'].update(unique_candidate=0, ambiguous_name=1)
        with self.assertRaises(CustomInstructionSummaryError): validate_custom_instruction_summary(value)

    def test_canonical_build_rejects_forged_metadata_and_semantics(self):
        parts = capture()
        bad = deepcopy(parts[-1]); bad.declarations[0]['parameters'][0]['usage'] = 'output'
        with self.assertRaises(CustomInstructionSummaryError): build_custom_instruction_summary(*parts[:-1], bad)
        with self.assertRaises(CustomInstructionSummaryError):
            build_custom_instruction_summary(*parts[:-1], replace(parts[-1], schema_version=True))

    def test_native_types_and_cyclic_values_cannot_run_foreign_hooks(self):
        class Hostile(dict):
            def keys(self): raise AssertionError('Foreign hook called')
        base = summary()
        for bad in (Hostile(), [], {'cycle': None}):
            value = deepcopy(base); value['coverage'] = bad
            if type(bad) is dict: bad['cycle'] = bad
            with self.assertRaises(CustomInstructionSummaryError): validate_custom_instruction_summary(value)

    def test_revision_is_copied_and_rendering_limit_is_exact(self):
        revision = {'commit': 'a' * 40, 'worktree': 'clean'}
        value = build_custom_instruction_summary(*capture(), revision=revision)
        revision['commit'] = 'b' * 40
        self.assertEqual(value['tool_revision']['commit'], 'a' * 40)
        text = render_custom_instruction_summary(value)
        with patch('plc_workbench.custom_instruction_summary.MAX_REPORT_BYTES', len(text)):
            self.assertEqual(render_custom_instruction_summary(value), text)
        with patch('plc_workbench.custom_instruction_summary.MAX_REPORT_BYTES', len(text) - 1):
            with self.assertRaises(CustomInstructionSummaryError): render_custom_instruction_summary(value)


if __name__ == '__main__': unittest.main()
