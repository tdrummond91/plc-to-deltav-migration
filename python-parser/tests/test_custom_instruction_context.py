"""Invented AOI declarations exercise candidate identity without semantic claims."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access
from plc_workbench.binding_context import analyze_binding_context
from plc_workbench.calculations import analyze_calculations
from plc_workbench.conditions import analyze_conditions
from plc_workbench.custom_instruction_context import (
    CustomInstructionContextError, analyze_custom_instruction_context,
    render_custom_instruction_context_json, validate_custom_instruction_context,
)
from plc_workbench.references import analyze_references
from plc_workbench.relationships import analyze_relationships
from plc_workbench.rung_analysis import analyze_rungs
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def routine(text='InventedAOI(A);', name='Run'):
    return (f'<Routine Name="{name}" Type="RLL"><RLLContent><Rung Number="0" Type="N">'
            f'<Text><![CDATA[{text}]]></Text></Rung></RLLContent></Routine>')


def definition(name='InventedAOI', children=None, attributes=''):
    if children is None:
        children = ('<Parameters><Parameter Name="Argument" Usage="Input" Required="true" '
                    'Visible="false" DataType="DINT"/></Parameters><Routines>'
                    + routine('XIC(A)OTE(B);', 'Logic') + '</Routines>')
    return f'<AddOnInstructionDefinition Name="{name}" {attributes}>{children}</AddOnInstructionDefinition>'


def controller(definitions=None, text='InventedAOI(A);', name='InventedController'):
    definitions = definition() if definitions is None else definitions
    return (f'<Controller Name="{name}"><AddOnInstructionDefinitions>{definitions}</AddOnInstructionDefinitions>'
            '<Programs><Program Name="InventedProgram"><Routines>' + routine(text)
            + '</Routines></Program></Programs></Controller>')


def capture(body=None, root_attributes=''):
    body = controller() if body is None else body
    snapshot = snapshot_from_bytes((f'<RSLogix5000Content {root_attributes}>' + body + '</RSLogix5000Content>').encode())
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    calculations = analyze_calculations(snapshot, inventory, references)
    access = analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
    rungs = analyze_rungs(snapshot, inventory, references, access, calculations)
    relationships = analyze_relationships(snapshot, inventory, references, access, calculations, rungs)
    conditions = analyze_conditions(snapshot, inventory, references, access, calculations, rungs,
                                    relationships, schema_version=2)
    binding = analyze_binding_context(snapshot, inventory, references, access, calculations, rungs,
                                      relationships, conditions)
    parts = (snapshot, inventory, references, access, calculations, rungs, relationships, conditions, binding)
    return (*parts, analyze_custom_instruction_context(*parts))


class CustomInstructionContextTests(unittest.TestCase):
    def test_unique_candidate_links_existing_evidence_without_changing_roles(self):
        parts = capture()
        result = parts[-1]
        before = [deepcopy(part.to_dict()) for part in parts[1:-1]]
        declaration, call = result.declarations[0], result.calls[0]
        self.assertEqual(call['status'], 'unique_candidate')
        self.assertEqual(call['declaration_id'], declaration['source_id'])
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.coverage['unknown_family_calls'], 1)
        self.assertEqual(result.coverage['parameter_usage']['input'], 1)
        self.assertEqual(result.coverage['routine_languages']['rll'], 1)
        self.assertEqual(result.coverage['routine_contents']['rll'], 1)
        by_id = {entity.id: entity for entity in parts[1].entities}
        self.assertEqual(by_id[declaration['parameters'][0]['source_id']].kind, 'aoi_parameter')
        self.assertEqual(by_id[declaration['routines'][0]['source_id']].kind, 'routine')
        self.assertEqual(parts[5].coverage['block_families']['unknown'], 1)
        self.assertEqual(next(row for row in parts[3].instructions if row['id'] == call['instruction_id'])['status'], 'unsupported_instruction')
        self.assertEqual((result.effects, result.parameter_roles, result.call_validation), ('not_analyzed',) * 3)
        validate_custom_instruction_context(*parts)
        self.assertEqual(before, [part.to_dict() for part in parts[1:-1]])
        rendered = render_custom_instruction_context_json(result)
        for raw in ('InventedAOI', 'InventedController', 'Argument', 'XIC(A)', 'DataType'):
            self.assertNotIn(raw, rendered)

    def test_matching_is_ascii_case_insensitive_and_occurrence_preserving(self):
        result = capture(controller(text='inventedaoi(A)INVENTEDAOI(A)InventedAOI(B);'))[-1]
        self.assertEqual([row['status'] for row in result.calls], ['unique_candidate'] * 3)
        self.assertEqual(len({row['instruction_id'] for row in result.calls}), 3)
        self.assertEqual(result.coverage['unique_candidate_definitions_called'], 1)

    def test_same_name_in_different_controllers_never_crosses_scope(self):
        result = capture(controller(name='One') + controller(name='Two') +
                         controller(definitions='', name='Three'))[-1]
        self.assertEqual([row['status'] for row in result.calls],
                         ['unique_candidate', 'unique_candidate', 'missing_declaration'])
        self.assertNotEqual(result.calls[0]['declaration_id'], result.calls[1]['declaration_id'])
        self.assertEqual(result.coverage['unique_candidate_definitions_called'], 2)

    def test_duplicate_and_case_colliding_declarations_are_ambiguous(self):
        for name in ('InventedAOI', 'inventedaoi'):
            with self.subTest(name=name):
                result = capture(controller(definition() + definition(name)))[-1]
                self.assertEqual([row['status'] for row in result.declarations], ['ambiguous_name'] * 2)
                self.assertEqual(result.calls[0]['status'], 'ambiguous_declaration')
                self.assertIsNone(result.calls[0]['declaration_id'])
                self.assertEqual(result.status, 'partial')

    def test_invalid_names_do_not_use_unicode_or_trimmed_matching(self):
        for name in (' InventedAOI', 'InventedAOI ', 'Invented-AOI', 'İnventedAOI', '', 'A' * 65):
            with self.subTest(name=name):
                result = capture(controller(definition(name)))[-1]
                self.assertEqual(result.declarations[0]['status'], 'invalid_name')
                self.assertEqual(result.calls[0]['status'], 'missing_declaration')
        result = capture(controller(definition().replace(' Name="InventedAOI"', '', 1)))[-1]
        self.assertEqual(result.declarations[0]['status'], 'invalid_name')

    def test_missing_definition_and_partial_export_do_not_invent_candidates(self):
        result = capture(controller(definitions=''))[-1]
        self.assertEqual(result.calls[0]['status'], 'missing_declaration')
        self.assertEqual(result.declarations, [])
        # A bare declaration in an unsupported export envelope stays in snapshot evidence.
        result = capture(definition() + controller(definitions=''))[-1]
        self.assertEqual(result.declarations, [])
        self.assertEqual(result.calls[0]['status'], 'missing_declaration')
        self.assertEqual(capture(definition())[-1].calls, [])

    def test_declared_parameter_metadata_is_not_positional_call_validation(self):
        parameters = ('<Parameters><Parameter Name="One" Usage="Input" Required="true" Visible="false" DataType="DINT"/>'
                      '<Parameter Name="Two" Usage="Output" Required="false" Visible="true"/>'
                      '<Parameter Name="Three" Usage="InOut" Required="TRUE" Visible=""/>'
                      '<Parameter Name="Four" Usage="Mystery"/><Parameter Name="Five"/></Parameters>')
        result = capture(controller(definition(children=parameters), text='InventedAOI();'))[-1]
        self.assertEqual(result.calls[0]['status'], 'unique_candidate')
        self.assertEqual([row['usage'] for row in result.declarations[0]['parameters']],
                         ['input', 'output', 'inout', 'other', 'missing'])
        self.assertEqual(result.coverage['parameter_required'],
                         {'true': 1, 'false': 1, 'other': 1, 'missing': 2, 'unsupported_context': 0})
        self.assertEqual(result.coverage['parameter_datatype']['missing'], 4)
        self.assertEqual(result.call_validation, 'not_analyzed')

    def test_body_language_availability_and_protection_are_separate_source_facts(self):
        bodies = ('<Routines><Routine Name="A" Type="ST"><STContent><Line>Private ST body</Line></STContent></Routine>'
                  '<Routine Name="B" Type="FBD"><FBDContent/></Routine><Routine Name="C" Type="SFC"><SFCContent/></Routine>'
                  '<Routine Name="D"/><Routine Name="E" Type="Unlisted"><OtherContent/></Routine>'
                  '<Routine Name="F" Type="ST"><STContent/><ExtraContent/></Routine></Routines>'
                  '<EncodedData>Private encoded bytes</EncodedData>')
        result = capture(controller(definition(children=bodies, attributes='SourceKey="PrivateSecret"')))[-1]
        c = result.coverage
        self.assertEqual(c['routine_languages'],
                         {'rll': 0, 'st': 2, 'fbd': 1, 'sfc': 1, 'missing': 1, 'other': 1, 'unsupported_context': 0})
        self.assertEqual(c['routine_contents']['multiple'], 1)
        self.assertEqual(c['routine_contents']['missing'], 1)
        self.assertEqual(c['definitions_with_encoded_regions'], 1)
        self.assertEqual(c['encoded_regions_total'], 1)
        self.assertEqual(c['definitions_with_protection_markers'], 1)
        for secret in ('Private ST body', 'Private encoded bytes', 'PrivateSecret'):
            self.assertNotIn(secret, render_custom_instruction_context_json(result))
        self.assertEqual(result.calls[0]['status'], 'unique_candidate')

    def test_unknown_family_is_not_unknown_access_and_known_builtins_stay_out(self):
        result = capture(controller(definition('MOV'), text='MOV(A,B)MISSING(A)SBR(A)NOP();'))[-1]
        self.assertEqual(len(result.calls), 2)  # NOP is not in the frozen family catalog.
        self.assertEqual(result.coverage['calls_by_status']['missing_declaration'], 2)
        self.assertEqual(result.coverage['definitions_total'], 1)

    def test_calls_inside_aoi_bodies_use_their_owning_controller(self):
        defs = definition(children='<Routines>' + routine('OtherAOI(A);', 'Logic') + '</Routines>') + definition('OtherAOI', '')
        result = capture(controller(defs))[-1]
        self.assertEqual(result.coverage['calls_by_status']['unique_candidate'], 2)
        self.assertEqual(result.coverage['unique_candidate_definitions_called'], 2)

    def test_common_root_namespace_is_supported(self):
        result = capture(root_attributes='xmlns="urn:invented-source"')[-1]
        self.assertEqual(result.calls[0]['status'], 'unique_candidate')

    def test_extension_declaration_namespace_cannot_look_like_an_exact_match(self):
        defs = definition().replace('<AddOnInstructionDefinition ', '<ext:AddOnInstructionDefinition ')
        defs = defs.replace('</AddOnInstructionDefinition>', '</ext:AddOnInstructionDefinition>')
        result = capture(controller(defs), 'xmlns:ext="urn:extension"')[-1]
        self.assertEqual(result.declarations[0]['status'], 'unsupported_context')
        self.assertEqual(result.calls[0]['status'], 'unsupported_context')
        self.assertIsNone(result.calls[0]['declaration_id'])
        self.assertEqual(result.coverage['parameter_usage']['unsupported_context'], 1)

    def test_namespaced_name_or_usage_attributes_are_not_treated_as_logix_attributes(self):
        for old, new in (('Name="InventedAOI"', 'ext:Name="InventedAOI"'),
                         ('Usage="Input"', 'ext:Usage="Input"')):
            result = capture(controller(definition().replace(old, new)), 'xmlns:ext="urn:extension"')[-1]
            if old.startswith('Name'):
                self.assertEqual(result.calls[0]['status'], 'unsupported_context')
            else:
                self.assertEqual(result.calls[0]['status'], 'unique_candidate')
                self.assertEqual(result.declarations[0]['parameters'][0]['usage'], 'unsupported_context')

    def test_extension_text_and_routine_type_make_calls_unsupported(self):
        base = controller(definitions=definition(children=''))
        for mutated in (base.replace('<Text>', '<ext:Text>').replace('</Text>', '</ext:Text>'),
                        base.replace('Type="RLL"', 'ext:Type="RLL"')):
            result = capture(mutated, 'xmlns:ext="urn:extension"')[-1]
            self.assertEqual(result.calls[0]['status'], 'unsupported_context')

    def test_same_name_with_unmodeled_namespace_attributes_blocks_unique_match(self):
        definitions = definition(attributes='SourceKey="Private"') + definition(attributes='ext:Marker="Private"')
        result = capture(controller(definitions), 'xmlns:ext="urn:extension"')[-1]
        self.assertEqual(result.calls[0]['status'], 'unsupported_context')
        self.assertIsNone(result.calls[0]['declaration_id'])
        self.assertEqual([row['status'] for row in result.declarations], ['unsupported_context'] * 2)
        # A marker already observed in the canonical namespace remains a source fact.
        self.assertEqual(result.coverage['definitions_with_protection_markers'], 1)

    def test_extension_body_is_unavailable_without_destroying_declaration_candidate(self):
        defs = definition(children='<Routines><Routine Name="Body" Type="ST"><ext:STContent/></Routine></Routines>')
        result = capture(controller(defs), 'xmlns:ext="urn:extension"')[-1]
        self.assertEqual(result.calls[0]['status'], 'unique_candidate')
        self.assertEqual(result.coverage['routine_languages']['st'], 1)
        self.assertEqual(result.coverage['routine_contents']['unsupported_context'], 1)

    def test_canonical_result_and_prerequisite_forgery_are_rejected(self):
        parts = capture()
        mutations = (
            lambda result: result.calls[0].update(status='missing_declaration', declaration_id=None),
            lambda result: result.declarations[0]['parameters'][0].update(usage='output'),
            lambda result: result.declarations[0]['routines'].clear(),
            lambda result: result.coverage.update(unknown_family_calls=2),
        )
        for mutate in mutations:
            value = deepcopy(parts[-1]); mutate(value)
            with self.assertRaises(CustomInstructionContextError):
                validate_custom_instruction_context(*parts[:-1], value)
        for value in (replace(parts[-1], schema_version=True), replace(parts[-1], effects='validated')):
            with self.assertRaises(CustomInstructionContextError):
                validate_custom_instruction_context(*parts[:-1], value)
        forged = list(deepcopy(parts[:-1])); forged[-1].coverage['source_rungs'] = 87654
        with patch('plc_workbench.custom_instruction_context._derive') as derive:
            with self.assertRaises(CustomInstructionContextError): analyze_custom_instruction_context(*forged)
            derive.assert_not_called()
        foreign = capture(controller(text='InventedAOI(B);'))[-1]
        with self.assertRaises(CustomInstructionContextError):
            validate_custom_instruction_context(*parts[:-1], foreign)

    def test_native_renderer_rejects_hooks_cycles_and_exact_byte_boundary(self):
        result = capture()[-1]
        text = render_custom_instruction_context_json(result)
        self.assertEqual(json.loads(text), result.to_dict())
        with patch('plc_workbench.custom_instruction_context.MAX_CONTEXT_BYTES', len(text)):
            self.assertEqual(render_custom_instruction_context_json(result), text)
        with patch('plc_workbench.custom_instruction_context.MAX_CONTEXT_BYTES', len(text) - 1):
            with self.assertRaises(CustomInstructionContextError): render_custom_instruction_context_json(result)
        class Hostile(list):
            def __iter__(self): raise AssertionError('Foreign hook called')
        cycle = []; cycle.append(cycle)
        for value in (Hostile(), cycle, {'secret': object()}):
            with self.assertRaises(CustomInstructionContextError):
                render_custom_instruction_context_json(replace(result, calls=value))

    def test_derivation_limits_fail_with_source_free_errors(self):
        parts = capture()
        for constant in ('MAX_RECORDS', 'MAX_CONTEXT_BYTES'):
            with patch('plc_workbench.custom_instruction_context.' + constant, 1):
                with self.assertRaises(CustomInstructionContextError) as raised:
                    analyze_custom_instruction_context(*parts[:-1])
                self.assertNotIn('Invented', str(raised.exception))

    def test_metadata_record_budget_applies_before_aggregate_row_retention(self):
        from plc_workbench.custom_instruction_context import _derive
        parts = capture(controller(definition(children='<Parameters>' +
                         ''.join(f'<Parameter Name="P{i}"/>' for i in range(6)) + '</Parameters>'),
                         text='InventedAOI(A)' * 6 + ';'))
        # Call the authenticated derivation with a smaller aggregate record budget.
        # It charges parameters separately, even though they live in one declaration.
        bound = len(parts[1].entities)
        self.assertLess(bound, 6 + 1 + 6)  # Parameters, declaration and call occurrences.
        with patch('plc_workbench.custom_instruction_context.MAX_RECORDS', bound):
            with self.assertRaises(CustomInstructionContextError): _derive(parts[0], parts[1], parts[3], parts[5])

    def test_unsupported_large_call_name_does_not_become_a_missing_definition(self):
        result = capture(controller(definition('A' * 65, ''), text='A' * 65 + '(A);'))[-1]
        self.assertEqual(result.declarations[0]['status'], 'invalid_name')
        self.assertEqual(result.calls[0]['status'], 'unsupported_context')

    def test_repeated_calls_do_not_duplicate_definition_or_body_evidence(self):
        result = capture(controller(text='InventedAOI(A)' * 120 + ';'))[-1]
        self.assertEqual(len(result.calls), 120)
        self.assertEqual(len(result.declarations), 1)
        self.assertEqual(result.coverage['parameters_total'], 1)
        self.assertLess(len(render_custom_instruction_context_json(result)), 100_000)


if __name__ == '__main__': unittest.main()
