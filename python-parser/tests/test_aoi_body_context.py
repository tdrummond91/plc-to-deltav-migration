"""Invented AOI bodies keep ownership, occurrences, and call evidence distinct."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from plc_workbench.aoi_body_context import (
    AoiBodyContextError, analyze_aoi_body_context, render_aoi_body_context_json,
    validate_aoi_body_context,
)
from test_custom_instruction_context import capture as old_capture, definition, routine


def document(body='XIC(Input)MOV(Input,Output)CPT(Local,Input+Input);',
             calls='Widget(Instance);', tags='', parameters=None, locals=None,
             extra_routines='', definition_attributes='', root_attributes=''):
    if parameters is None:
        parameters = ('<Parameter Name="Input" Usage="Input" Required="false" Visible="false" DataType="DINT"/>'
                      '<Parameter Name="Output" Usage="Output" Required="false" Visible="false" DataType="DINT"/>'
                      '<Parameter Name="Unobserved" Usage="Input" Required="false" Visible="false" DataType="DINT"/>')
    if locals is None:
        locals = '<LocalTag Name="Local" DataType="DINT"/>'
    children = ('<Parameters>' + parameters + '</Parameters><LocalTags>' + locals
                + '</LocalTags><Routines>' + routine(body, 'Logic') + extra_routines + '</Routines>')
    return ('<Controller Name="Invented"><Tags><Tag Name="Instance" DataType="Widget"/>' + tags + '</Tags>'
            '<AddOnInstructionDefinitions>' + definition('Widget', children, definition_attributes)
            + '</AddOnInstructionDefinitions><Programs><Program Name="Main"><Routines>'
            + routine(calls) + '</Routines></Program></Programs></Controller>')


def capture(body=None, root_attributes=''):
    parts = old_capture(document() if body is None else body, root_attributes)
    return (*parts, analyze_aoi_body_context(*parts))


def named_symbols(parts):
    names = {entity.id: entity.name for entity in parts[1].entities}
    return {names[row['source_id']]: row for row in parts[-1].symbols}


class AoiBodyContextTests(unittest.TestCase):
    def test_owned_body_subset_and_repeated_reads_preserve_ids(self):
        parts = capture()
        result = parts[-1]
        self.assertEqual(result.status, 'complete')
        c = result.coverage
        self.assertEqual((c['body_rungs_total'], c['body_instructions_total'], c['body_operands_total'],
                          c['body_expression_uses_total']), (1, 3, 5, 2))
        self.assertEqual((c['body_symbol_operand_uses'], c['body_symbol_expression_uses']), (4, 2))
        symbols = named_symbols(parts)
        self.assertEqual(len(symbols['Input']['direct_operand_ids']), 2)
        self.assertEqual(len(symbols['Input']['direct_expression_use_ids']), 2)
        self.assertEqual(symbols['Input']['direct_operand_ids'], symbols['Input']['resolved_operand_ids'])
        self.assertEqual(symbols['Unobserved']['direct_operand_ids'], [])
        self.assertEqual(symbols['Unobserved']['resolved_expression_use_ids'], [])
        self.assertEqual(len(result.routines[0]['expression_use_ids']), 2)
        self.assertEqual(result.calls[0]['datatype_status'], 'matching_type_name')
        self.assertEqual(result.calls[0]['instance_status'], 'bound_root_context')
        validate_aoi_body_context(*parts)

    def test_input_output_usage_and_hidden_flags_do_not_assign_call_slots(self):
        parts = capture(document(calls='Widget(Instance,99,Unknown,Extra);'))
        self.assertEqual(parts[-1].calls[0]['instance_status'], 'bound_root_context')
        self.assertEqual(parts[-1].call_validation, 'not_analyzed')
        self.assertEqual(parts[-1].parameter_mapping, 'not_analyzed')
        call_id = parts[-1].calls[0]['instruction_id']
        operands = [row for row in parts[3].operands if row['instruction_id'] == call_id]
        self.assertEqual([row['role'] for row in operands], ['unknown'] * 4)

    def test_companions_unchanged_and_result_contains_no_source_text(self):
        parts = capture()
        before = [deepcopy(part.to_dict()) for part in parts[1:-1]]
        validate_aoi_body_context(*parts)
        self.assertEqual(before, [part.to_dict() for part in parts[1:-1]])
        rendered = render_aoi_body_context_json(parts[-1])
        for text in ('Widget', 'Instance', 'Input', 'DINT', 'XIC(', 'Input+Input'):
            self.assertNotIn(text, rendered)

    def test_parameter_alias_indexes_direct_and_resolved_without_double_count(self):
        parameters = '<Parameter Name="Input" AliasFor="Local" Usage="Input" DataType="DINT"/>'
        parts = capture(document(body='MOV(Input,Local);', parameters=parameters))
        symbols = named_symbols(parts)
        self.assertEqual(len(symbols['Input']['direct_operand_ids']), 1)
        self.assertEqual(symbols['Input']['resolved_operand_ids'], [])
        self.assertEqual(len(symbols['Local']['resolved_operand_ids']), 2)
        self.assertEqual(parts[-1].coverage['body_symbol_operand_uses'], 2)

    def test_aoi_body_cannot_bind_same_spelling_controller_tag(self):
        parts = capture(document(body='XIC(Outside)OTE(Local);', tags='<Tag Name="Outside" DataType="BOOL"/>'))
        body_operand = next(row for row in parts[3].operands if row['id'] == parts[-1].routines[0]['operand_ids'][0])
        self.assertEqual(body_operand['binding_status'], 'unresolved')
        self.assertEqual(parts[-1].coverage['body_symbol_operand_uses'], 1)

    def test_routine_ownership_includes_prescan_without_execution_claim(self):
        parts = capture(document(extra_routines=routine('MOV(Input,Output);', 'Prescan')))
        self.assertEqual(len(parts[-1].routines), 2)
        self.assertEqual(len(parts[-1].declarations[0]['routine_ids']), 2)
        self.assertEqual(parts[-1].execution, 'not_analyzed')
        self.assertEqual(parts[-1].coverage['body_rungs_total'], 2)

    def test_protection_non_rll_missing_and_malformed_bodies_remain_partial(self):
        variants = [
            (document(definition_attributes='SourceKey="secret"'), 'protected'),
            (document().replace('Type="RLL"><RLLContent>', 'Type="ST"><RLLContent>', 1), 'unsupported_language'),
            (document().replace('<RLLContent>', '<OtherContent>', 1).replace('</RLLContent>', '</OtherContent>', 1), 'missing_or_multiple_content'),
            (document(body='XIC('), 'incomplete_rll'),
        ]
        for xml, expected in variants:
            with self.subTest(expected=expected):
                result = capture(xml)[-1]
                self.assertEqual(result.routines[0]['body_status'], expected)
                self.assertEqual(result.status, 'partial')
        xml = document().replace('<Routines>' + routine('XIC(Input)MOV(Input,Output)CPT(Local,Input+Input);', 'Logic') + '</Routines>', '')
        result = capture(xml)[-1]
        self.assertEqual(result.coverage['definitions_with_body_gaps'], 1)

    def test_namespace_context_gaps_do_not_produce_symbol_indexes(self):
        xml = document().replace('<Text><![CDATA[XIC(Input)', '<x:Text><![CDATA[XIC(Input)', 1).replace('</Text>', '</x:Text>', 1)
        parts = capture(xml, 'xmlns:x="urn:other"')
        self.assertEqual(parts[-1].routines[0]['body_status'], 'unsupported_context')
        self.assertEqual(parts[-1].coverage['body_symbol_operand_uses'], 0)
        self.assertEqual(parts[-1].status, 'partial')
        # A consistent namespace is supported; a foreign namespace attribute is not.
        self.assertEqual(capture(root_attributes='xmlns="urn:logix"')[-1].status, 'complete')
        xml = document().replace('Name="Instance"', 'x:Name="Instance"')
        self.assertEqual(capture(xml, 'xmlns:x="urn:other"')[-1].calls[0]['instance_status'], 'unsupported_context')

    def test_protected_routine_descendant_and_foreign_alias_target_are_not_indexed(self):
        xml = document().replace('<RLLContent>', '<RLLContent Protected="true">', 1)
        result = capture(xml)[-1]
        self.assertEqual(result.routines[0]['body_status'], 'protected')
        self.assertEqual(result.coverage['body_symbol_operand_uses'], 0)
        parameters = '<Parameter Name="Input" AliasFor="Local" Usage="Input"/>'
        xml = document(body='XIC(Input);', parameters=parameters,
                       locals='<LocalTag x:Name="Local" DataType="DINT"/>')
        result = capture(xml, 'xmlns:x="urn:extension"')[-1]
        self.assertEqual(result.coverage['body_symbol_operand_uses'], 0)
        self.assertEqual(result.coverage['symbols_with_context_gaps'], 1)

    def test_parameter_alias_cannot_escape_aoi_local_target_rules(self):
        parameters = ('<Parameter Name="Input" AliasFor="Other" Usage="Input"/>'
                      '<Parameter Name="Other" Usage="Input" DataType="DINT"/>')
        parts = capture(document(body='XIC(Input);', parameters=parameters))
        operand_id = parts[-1].routines[0]['operand_ids'][0]
        operand = next(row for row in parts[3].operands if row['id'] == operand_id)
        self.assertEqual(operand['binding_status'], 'unresolved')
        self.assertEqual(operand['binding_reason'], 'aoi_alias_target_not_local')
        self.assertEqual(named_symbols(parts)['Other']['resolved_operand_ids'], [])

    def test_dynamic_index_is_not_added_to_supported_body_symbol_observations(self):
        parts = capture(document(body='MOV(Local[Input],Output);'))
        symbols = named_symbols(parts)
        self.assertEqual(symbols['Input']['direct_operand_ids'], [])
        self.assertEqual(symbols['Local']['direct_operand_ids'], [])
        self.assertEqual(parts[-1].coverage['body_operands_by_binding']['unsupported_address'], 1)

    def test_first_instance_field_missing_literal_unknown_and_dynamic(self):
        for call, status, binding in (
            ('Widget();', 'missing_operand', 'missing_operand'),
            ('Widget(,A);', 'missing_operand', 'missing_operand'),
            ('Widget(1);', 'literal', 'literal'),
            ('Widget(Unknown);', 'unbound', 'unresolved'),
            ('Widget(Instance[Index]);', 'unbound', 'unsupported_address'),
        ):
            with self.subTest(call=call):
                row = capture(document(calls=call))[-1].calls[0]
                self.assertEqual((row['instance_status'], row['binding_status']), (status, binding))

    def test_instance_root_type_comparison_is_ascii_only_and_case_insensitive(self):
        self.assertEqual(capture(document(calls='widget(instance);'))[-1].calls[0]['datatype_status'], 'matching_type_name')
        for value, expected in (('widget', 'matching_type_name'), ('Other', 'different_type_name'), ('', 'missing'), ('Wİdget', 'missing')):
            xml = document().replace('DataType="Widget"', f'DataType="{value}"')
            self.assertEqual(capture(xml)[-1].calls[0]['datatype_status'], expected)

    def test_member_array_and_root_datatype_are_separate_facts(self):
        for call, dimensions, shape, dtype, status in (
            ('Widget(Instance.Member);', '', 'member', 'member_deferred', 'partial'),
            ('Widget(Instance[2]);', '4', 'static_element', 'matching_type_name', 'complete'),
            ('Widget(Instance);', '4', 'unindexed_array', 'matching_type_name', 'partial'),
            ('Widget(Instance[999]);', '4', 'static_element', 'matching_type_name', 'complete'),
        ):
            xml = document(calls=call).replace('Name="Instance" DataType="Widget"', f'Name="Instance" DataType="Widget" Dimensions="{dimensions}"')
            result = capture(xml)[-1]
            self.assertEqual((result.calls[0]['address_shape'], result.calls[0]['datatype_status'], result.status), (shape, dtype, status))
            self.assertEqual(result.call_validation, 'not_analyzed')

    def test_alias_root_resolution_preserves_chain_and_alias_cycles(self):
        tags = '<Tag Name="Alias" TagType="Alias" AliasFor="Instance"/>'
        parts = capture(document(calls='Widget(Alias);', tags=tags))
        self.assertEqual(parts[-1].calls[0]['datatype_status'], 'matching_type_name')
        self.assertEqual(len(parts[-1].calls[0]['alias_chain']), 1)
        tags = '<Tag Name="Alias" TagType="Alias" AliasFor="Cycle"/><Tag Name="Cycle" TagType="Alias" AliasFor="Alias"/>'
        self.assertEqual(capture(document(calls='Widget(Alias);', tags=tags))[-1].calls[0]['binding_status'], 'alias_cycle')

    def test_alias_depth_limit_and_expanded_suffix_are_not_instances(self):
        tags = ''.join(f'<Tag Name="A{i}" TagType="Alias" AliasFor="A{i+1}"/>' for i in range(66)) + '<Tag Name="A66" DataType="Widget"/>'
        self.assertEqual(capture(document(calls='Widget(A0);', tags=tags))[-1].calls[0]['binding_status'], 'alias_depth_limit')
        tags = '<Tag Name="Alias" TagType="Alias" AliasFor="Instance.1"/>'
        result = capture(document(calls='Widget(Alias.Member);', tags=tags))[-1]
        self.assertEqual(result.calls[0]['binding_status'], 'root_bound')
        self.assertEqual(result.calls[0]['address_shape'], 'unsupported')
        self.assertEqual(result.calls[0]['datatype_status'], 'not_analyzed')

    def test_duplicate_declarations_and_roots_remain_ambiguous(self):
        xml = document().replace('</AddOnInstructionDefinitions>', definition('Widget', '') + '</AddOnInstructionDefinitions>')
        result = capture(xml)[-1]
        self.assertEqual(result.calls[0]['instance_status'], 'declaration_unavailable')
        self.assertEqual(result.calls[0]['binding_status'], 'not_analyzed')
        result = capture(document(tags='<Tag Name="instance" DataType="Widget"/>'))[-1]
        self.assertEqual(result.calls[0]['binding_status'], 'ambiguous')

    def test_controllers_and_two_aoi_bodies_do_not_cross_join(self):
        parts = capture(document() + document().replace('Name="Invented"', 'Name="Other"'))
        result = parts[-1]
        self.assertEqual(len(result.declarations), 2)
        self.assertNotEqual(result.calls[0]['declaration_id'], result.calls[1]['declaration_id'])
        for symbol in result.symbols:
            allowed = set(next(row for row in result.routines if row['declaration_id'] == symbol['declaration_id'])['operand_ids'])
            self.assertTrue(set(symbol['direct_operand_ids']) <= allowed)

    def test_nested_aoi_call_binds_local_instance_not_same_named_controller_tag(self):
        xml = document(body='Gadget(LocalInstance);',
                       tags='<Tag Name="LocalInstance" DataType="WrongType"/>',
                       locals='<LocalTag Name="LocalInstance" DataType="Gadget"/>')
        nested = definition('Gadget', '<Routines>' + routine('MOV(1,Unknown);', 'Logic') + '</Routines>')
        xml = xml.replace('</AddOnInstructionDefinitions>', nested + '</AddOnInstructionDefinitions>')
        parts = capture(xml)
        entities = {entity.id: entity for entity in parts[1].entities}
        nested_call = next(row for row in parts[-1].calls
                           if entities[row['declaration_id']].name == 'Gadget')
        target = entities[nested_call['target_id']]
        self.assertEqual((target.name, target.kind), ('LocalInstance', 'aoi_local_tag'))
        self.assertEqual(entities[target.scope_id].name, 'Widget')
        self.assertEqual(nested_call['symbol_id'], target.id)
        self.assertEqual(nested_call['binding_status'], 'root_bound')
        self.assertEqual(nested_call['datatype_status'], 'matching_type_name')
        self.assertEqual(nested_call['address_shape'], 'root')
        # First-field context does not promote the inherited opaque call role.
        original = next(row for row in parts[3].operands if row['id'] == nested_call['first_operand_id'])
        self.assertEqual(original['role'], 'unknown')
        self.assertEqual(named_symbols(parts)['LocalInstance']['direct_operand_ids'], [])

    def test_no_definitions_is_complete_only_when_no_unknown_calls(self):
        parts = old_capture('<Controller Name="Empty"/>')
        result = analyze_aoi_body_context(*parts)
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.declarations, [])
        result = capture(document(calls='Mystery(Instance);'))[-1]
        self.assertEqual(result.calls[0]['instance_status'], 'declaration_unavailable')
        self.assertEqual(result.status, 'partial')

    def test_tampered_upstream_or_private_result_is_rejected(self):
        parts = capture()
        bad = deepcopy(parts[-1]); bad.symbols[0]['resolved_operand_ids'] = []
        with self.assertRaises(AoiBodyContextError): validate_aoi_body_context(*parts[:-1], bad)
        custom = deepcopy(parts[-2]); custom.calls[0]['declaration_id'] = None
        with self.assertRaises(AoiBodyContextError): analyze_aoi_body_context(*parts[:-2], custom)
        bad = replace(parts[-1], status='partial')
        with self.assertRaises(AoiBodyContextError): validate_aoi_body_context(*parts[:-1], bad)

    def test_cycles_oversized_and_non_native_values_are_source_free(self):
        parts = capture()
        bad = deepcopy(parts[-1]); bad.calls.append(bad.calls)
        with self.assertRaises(AoiBodyContextError): render_aoi_body_context_json(bad)
        bad = replace(parts[-1], coverage={'private': object()})
        with self.assertRaises(AoiBodyContextError): render_aoi_body_context_json(bad)
        with patch('plc_workbench.aoi_body_context.MAX_CONTEXT_BYTES', 100):
            with self.assertRaises(AoiBodyContextError): analyze_aoi_body_context(*parts[:-1])
        with patch('plc_workbench.aoi_body_context.MAX_RECORDS', 2):
            with self.assertRaises(AoiBodyContextError): analyze_aoi_body_context(*parts[:-1])


if __name__ == '__main__':
    unittest.main()
