"""Invented schema2 AOI member identity and lexical signature observations."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch

from plc_workbench import aoi_body_context
from plc_workbench.aoi_body_context import (
    AoiBodyContextError, analyze_aoi_body_context, render_aoi_body_context_json,
    validate_aoi_body_context,
)
from plc_workbench.aoi_body_summary import (
    AoiBodySummaryError, build_aoi_body_summary, render_aoi_body_summary,
    validate_aoi_body_summary,
)
from test_aoi_body_context import capture, document
from test_custom_instruction_context import capture as capture_custom, definition, routine


def capture_v2(xml=None, root_attributes=''):
    parts = capture_custom(document() if xml is None else xml, root_attributes)
    return (*parts, analyze_aoi_body_context(*parts, schema_version=2))


def parameter(name, usage='Input', required='false', visible='false', extra=''):
    return (f'<Parameter Name="{name}" Usage="{usage}" Required="{required}" '
            f'Visible="{visible}" DataType="DINT" {extra}/>')


class AoiParameterMemberTests(unittest.TestCase):
    def test_default_and_explicit_schema1_preserve_frozen_render_bytes(self):
        parts = capture()
        rendered = render_aoi_body_context_json(parts[-1])
        self.assertEqual(hashlib.sha256(rendered.encode()).hexdigest(),
                         '0a4e131cab89bfc3385f8a2d6168e739693e37b2f0f6cf8ab245bf265be67e27')
        self.assertEqual(rendered, render_aoi_body_context_json(analyze_aoi_body_context(*parts[:-1], schema_version=1)))
        self.assertEqual(hashlib.sha256(render_aoi_body_summary(build_aoi_body_summary(*parts)).encode()).hexdigest(),
                         'fe5c0f94d6a21c9d687e86c347652a8e3e17ad8676f65f1488edb8166f1c7bed')
        self.assertNotIn('member_contexts', parts[-1].to_dict())
        bad = replace(parts[-1], member_contexts=[{}])
        with self.assertRaises(AoiBodyContextError): render_aoi_body_context_json(bad)

    def test_exact_members_preserve_occurrence_roles_and_existing_body_links(self):
        xml = document(calls='MOV(Instance.Output,Instance.Input)CPT(Instance.Output,Instance.Input+Instance.Input)Widget(Instance);')
        parts = capture_v2(xml)
        result = parts[-1]
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.coverage['members_by_kind'], {'operand': 3, 'expression': 2})
        self.assertEqual(result.coverage['matched_parameters'], 2)
        self.assertEqual(result.coverage['matched_instance_roots'], 1)
        sources = {row['id']: row for row in parts[3].operands + parts[3].expression_uses}
        symbols = {row['source_id']: row for row in result.symbols}
        for row in result.member_contexts:
            self.assertEqual(row['role'], sources[row['use_id']]['role'])
            self.assertIn(row['parameter_id'], symbols)
            self.assertTrue(symbols[row['parameter_id']]['direct_operand_ids'])
        self.assertEqual(len({row['use_id'] for row in result.member_contexts}), 5)
        self.assertEqual(result.parameter_mapping, 'named_member_associations_only')
        self.assertEqual((result.execution, result.call_validation, result.member_validation), ('not_analyzed',) * 3)
        before = [deepcopy(item.to_dict()) for item in parts[1:-1]]
        validate_aoi_body_context(*parts)
        self.assertEqual(before, [item.to_dict() for item in parts[1:-1]])

    def test_declaration_type_members_do_not_require_a_captured_call(self):
        result = capture_v2(document(calls='MOV(Instance.Input,Instance.Output);'))[-1]
        self.assertEqual(result.calls, [])
        self.assertEqual(len(result.member_contexts), 2)
        self.assertEqual(result.coverage['matched_member_contexts'], 2)

    def test_repeated_calls_do_not_duplicate_member_or_body_observations(self):
        parts = capture_v2(document(calls='Widget(Instance)' * 120 + 'XIC(Instance.Input);'))
        result = parts[-1]
        self.assertEqual((len(result.call_shapes), len(result.parameter_signatures), len(result.member_contexts)), (120, 1, 1))
        self.assertEqual(result.coverage['calls_by_signature_observation']['no_required_parameters'], 120)
        self.assertEqual(result.coverage['body_instructions_total'], 3)
        self.assertTrue(all(row['role'] == 'unknown' for row in parts[3].operands
                            if row['instruction_id'] in {call['instruction_id'] for call in result.calls}))

    def test_scoped_types_and_program_shadowing_never_cross_join(self):
        one = document(calls='XIC(Instance.Input);')
        two = one.replace('Name="Invented"', 'Name="Other"')
        result = capture_v2(one + two)[-1]
        self.assertEqual(len({row['declaration_id'] for row in result.member_contexts}), 2)
        shadow = one.replace('<Program Name="Main">', '<Program Name="Main"><Tags><Tag Name="Instance" DataType="DINT"/></Tags>')
        self.assertEqual(capture_v2(shadow)[-1].member_contexts, [])
        self.assertEqual(capture_v2(one.replace('DataType="Widget"', 'DataType="Missing"'))[-1].member_contexts, [])

    def test_caller_aliases_and_parameter_aliases_keep_distinct_evidence(self):
        params = parameter('Input', extra='AliasFor="Local"')
        tags = ('<Tag Name="WholeAlias" TagType="Alias" AliasFor="Instance"/>'
                '<Tag Name="MemberAlias" TagType="Alias" AliasFor="Instance.Input"/>')
        result = capture_v2(document(parameters=params, tags=tags,
            calls='XIC(WholeAlias.Input)XIC(MemberAlias);'))[-1]
        self.assertEqual(len(result.member_contexts), 2)
        for row in result.member_contexts:
            self.assertEqual(row['status'], 'matched_parameter')
            self.assertEqual(row['suffix'], '.Input')
            self.assertEqual(len(row['alias_chain']), 1)
            self.assertEqual(len(row['parameter_alias_chain']), 1)
            self.assertIsNotNone(row['parameter_alias_target_id'])
            self.assertEqual(row['parameter_alias_suffix'], '')

    def test_alias_target_parameter_is_not_a_supported_local_alias(self):
        params = parameter('Input', extra='AliasFor="Output"') + parameter('Output', 'Output')
        result = capture_v2(document(parameters=params, calls='XIC(Instance.Input);'))[-1]
        self.assertEqual(result.member_contexts[0]['status'], 'alias_unresolved')
        self.assertIsNone(result.member_contexts[0]['parameter_id'])

    def test_inout_system_local_and_unknown_members_are_explicit_gaps(self):
        params = parameter('Ref', 'InOut', 'true', 'true') + parameter('EnableIn') + parameter('EnableOut', 'Output')
        result = capture_v2(document(parameters=params,
            calls='XIC(Instance.Ref)XIC(Instance.EnableIn)XIC(Instance.Local)XIC(Instance.Absent);'))[-1]
        self.assertEqual([row['status'] for row in result.member_contexts],
                         ['unsupported_parameter'] * 3 + ['missing_parameter'])
        self.assertEqual(result.coverage['signature_system_parameters'], 2)
        self.assertEqual(result.coverage['signature_required_parameters'], 1)

    def test_duplicate_parameters_or_local_collisions_stay_ambiguous(self):
        for params, locals_ in ((parameter('Input') + parameter('input'), None),
                                (parameter('Input'), '<LocalTag Name="INPUT" DataType="DINT"/>')):
            with self.subTest(params=params):
                result = capture_v2(document(parameters=params, locals=locals_, calls='XIC(Instance.Input);'))[-1]
                self.assertEqual(result.member_contexts[0]['status'], 'ambiguous_parameter')
                self.assertEqual(result.parameter_signatures[0]['status'], 'ambiguous_parameters')

    def test_duplicate_controller_aoi_declarations_are_not_selected(self):
        xml = document(calls='XIC(Instance.Input);').replace('</AddOnInstructionDefinitions>',
            definition('widget', '<Parameters>' + parameter('Input') + '</Parameters>') + '</AddOnInstructionDefinitions>')
        result = capture_v2(xml)[-1]
        row = result.member_contexts[0]
        self.assertEqual((row['status'], row['declaration_candidate_count']), ('declaration_unavailable', 2))
        self.assertIsNone(row['declaration_id'])

    def test_arrays_indices_nested_and_whole_roots_are_not_direct_scalar_members(self):
        for address, dimensions, status in (
            ('Instance.Input', '3', 'unsupported_instance'),
            ('Instance[1].Input', '3', 'unsupported_instance'),
            ('Instance[1].Input', '0', 'unsupported_member'),
            ('Instance.Input.Bit', '0', 'unsupported_member'),
            ('Instance.Input[0]', '0', 'unsupported_member'),
        ):
            with self.subTest(address=address, dimensions=dimensions):
                xml = document(calls=f'XIC({address});').replace('Name="Instance" DataType="Widget"',
                    f'Name="Instance" DataType="Widget" Dimensions="{dimensions}"')
                self.assertEqual(capture_v2(xml)[-1].member_contexts[0]['status'], status)
        self.assertEqual(capture_v2(document(calls='XIC(Instance[Index].Input);'))[-1].member_contexts, [])
        self.assertEqual(capture_v2(document(calls='XIC(Instance);'))[-1].member_contexts, [])

    def test_namespace_and_protection_on_each_dependency_block_matches(self):
        original = document(calls='XIC(Instance.Input);')
        changes = (
            ('<Controller Name="Invented">', '<Controller Name="Invented" x:Flag="x">', 'unsupported_context'),
            ('<Program Name="Main">', '<Program Name="Main" x:Flag="x">', 'unsupported_context'),
            ('Name="Instance" DataType="Widget"', 'Name="Instance" DataType="Widget" x:Flag="x"', 'unsupported_context'),
            ('<Parameter Name="Input"', '<Parameter x:Flag="x" Name="Input"', 'unsupported_context'),
            ('<LocalTag Name="Local"', '<LocalTag x:Flag="x" Name="Local"', 'unsupported_context'),
            ('<Program Name="Main">', '<Program Name="Main" Protected="true">', 'protected'),
            ('Name="Instance" DataType="Widget"', 'Name="Instance" DataType="Widget" Protected="true"', 'protected'),
            ('<Parameter Name="Input"', '<Parameter Protected="true" Name="Input"', 'protected'),
        )
        for before, after, expected in changes:
            with self.subTest(after=after):
                result = capture_v2(original.replace(before, after), 'xmlns:x="urn:foreign"')[-1]
                self.assertEqual(result.member_contexts[0]['status'], expected)
                self.assertIsNone(result.member_contexts[0]['parameter_id'])

    def test_protected_definition_and_foreign_alias_dependency_remain_gaps(self):
        result = capture_v2(document(calls='XIC(Instance.Input);', definition_attributes='Protected="true"'))[-1]
        self.assertEqual(result.member_contexts[0]['status'], 'protected')
        self.assertEqual(result.parameter_signatures[0]['status'], 'protected')
        tags = '<Tag Name="Alias" TagType="Alias" AliasFor="Instance" x:Flag="foreign"/>'
        result = capture_v2(document(calls='XIC(Alias.Input);', tags=tags), 'xmlns:x="urn:foreign"')[-1]
        self.assertEqual(result.member_contexts[0]['status'], 'unsupported_context')
        for attributes in ('IsEncrypted="true"', 'Protected="true"'):
            xml = document(calls='XIC(Instance.Input)Widget(Instance);').replace(
                '<Program Name="Main">', f'<Program Name="Main" {attributes}>')
            result = capture_v2(xml)[-1]
            self.assertEqual(result.member_contexts[0]['status'], 'protected')
            self.assertEqual(result.call_shapes[0]['status'], 'signature_unavailable')

    def test_nested_aoi_local_instance_is_distinct_from_outer_parameters(self):
        outer = document(body='XIC(Nested.Value);', calls='Widget(Instance);',
                         locals='<LocalTag Name="Nested" DataType="Gadget"/>')
        gadget = definition('Gadget', '<Parameters>' + parameter('Value') + '</Parameters>')
        outer = outer.replace('</AddOnInstructionDefinitions>', gadget + '</AddOnInstructionDefinitions>')
        parts = capture_v2(outer)
        names = {entity.id: entity.name for entity in parts[1].entities}
        row = parts[-1].member_contexts[0]
        self.assertEqual((names[row['target_id']], names[row['declaration_id']], names[row['parameter_id']]), ('Nested', 'Gadget', 'Value'))

    def test_optional_hidden_parameters_do_not_create_missing_argument_findings(self):
        result = capture_v2()[-1]
        self.assertEqual(result.parameter_signatures[0]['status'], 'available')
        self.assertEqual(result.coverage['signature_optional_parameters'], 3)
        self.assertEqual(result.call_shapes[0]['status'], 'no_required_parameters')
        self.assertEqual(result.call_shapes[0]['argument_count'], 1)

    def test_ordered_required_observations_do_not_assign_positional_roles(self):
        params = (parameter('OutFirst', 'Output', 'true', 'true') + parameter('Optional')
                  + parameter('InLater', 'Input', 'true', 'true') + parameter('Ref', 'InOut', 'true', 'true'))
        calls = ('Widget()Widget(Instance,)Widget(Instance)Widget(Instance,1,Missing,Other)'
                 'Widget(Instance,1,Missing,Other,Extra);')
        parts = capture_v2(document(parameters=params, calls=calls))
        result = parts[-1]
        names = {entity.id: entity.name for entity in parts[1].entities}
        self.assertEqual([names[item] for item in result.parameter_signatures[0]['required_parameter_ids']], ['OutFirst', 'InLater', 'Ref'])
        self.assertEqual([row['status'] for row in result.call_shapes], ['missing_instance_field', 'empty_fields',
            'fewer_than_required_fields', 'required_field_count_equal', 'more_than_required_fields'])
        self.assertEqual(result.call_validation, 'not_analyzed')
        self.assertTrue(all('parameter_id' not in row for row in result.call_shapes))
        validate_aoi_body_summary(build_aoi_body_summary(*parts))

    def test_invalid_signature_metadata_never_supplies_a_required_count(self):
        for params in (parameter('Input', required='TRUE'), parameter('Input', required='true'),
                       parameter('Ref', 'InOut'), '<Parameter Name="Input" Usage="Input"/>',
                       parameter('Bad.Name'), parameter('Input', usage='Other')):
            with self.subTest(params=params):
                result = capture_v2(document(parameters=params))[-1]
                self.assertEqual(result.parameter_signatures[0]['status'], 'unsupported_metadata')
                self.assertEqual(result.call_shapes[0]['status'], 'signature_unavailable')
                self.assertIsNone(result.call_shapes[0]['required_parameter_count'])

    def test_system_parameter_metadata_is_not_an_ordinary_required_signature(self):
        params = parameter('EnableIn', required='true', visible='true') + parameter('EnableOut', usage='Mystery')
        result = capture_v2(document(parameters=params))[-1]
        self.assertEqual(result.coverage['signature_system_parameters'], 2)
        self.assertEqual(result.call_shapes[0]['status'], 'no_required_parameters')

    def test_replay_rejects_forged_member_links_shapes_and_signatures(self):
        parts = capture_v2(document(calls='XIC(Instance.Input)Widget(Instance);'))
        for change in (
            lambda r: r.member_contexts[0].update(parameter_id=r.member_contexts[0]['target_id']),
            lambda r: r.member_contexts[0].update(role='write'),
            lambda r: r.member_contexts[0]['alias_chain'].append('invented'),
            lambda r: r.parameter_signatures[0]['optional_parameter_ids'].reverse(),
            lambda r: r.call_shapes[0].update(argument_count=2),
            lambda r: r.coverage.update(matched_parameters=True),
        ):
            bad = deepcopy(parts[-1]); change(bad)
            with self.assertRaises(AoiBodyContextError): validate_aoi_body_context(*parts[:-1], bad)
        for version in (True, 0, 3, '2'):
            with self.assertRaises(AoiBodyContextError): analyze_aoi_body_context(*parts[:-1], schema_version=version)

    def test_association_limits_reject_before_retaining_unbounded_links(self):
        parts = capture_v2(document(calls='XIC(Instance.Input);'))
        with patch('plc_workbench.aoi_body_context.MAX_ASSOCIATION_LINKS', 2):
            with self.assertRaises(AoiBodyContextError): analyze_aoi_body_context(*parts[:-1], schema_version=2)
        bad = deepcopy(parts[-1]); bad.member_contexts.append(bad.member_contexts)
        with self.assertRaises(AoiBodyContextError): render_aoi_body_context_json(bad)

    def test_schema2_has_a_separate_sixteen_mib_limit_and_prebounds_native_values(self):
        self.assertEqual(aoi_body_context.MAX_CONTEXT_BYTES, 8 * 1024 * 1024)
        self.assertEqual(aoi_body_context.MAX_CONTEXT_BYTES_V2, 16 * 1024 * 1024)
        parts = capture_v2()
        old = analyze_aoi_body_context(*parts[:-1])
        # Rendering is bounded independently of source authentication. The same
        # oversized native value crosses only the historical schema1 boundary.
        padding = {'padding': 'x' * aoi_body_context.MAX_CONTEXT_BYTES}
        with self.assertRaisesRegex(AoiBodyContextError, 'exceeds its evidence limits'):
            render_aoi_body_context_json(replace(old, snapshot=padding))
        rendered = render_aoi_body_context_json(replace(parts[-1], snapshot=padding))
        self.assertGreater(len(rendered), aoi_body_context.MAX_CONTEXT_BYTES)
        self.assertLess(len(rendered), aoi_body_context.MAX_CONTEXT_BYTES_V2)
        oversized = replace(parts[-1], snapshot={
            'padding': 'x' * aoi_body_context.MAX_CONTEXT_BYTES_V2})
        with patch('plc_workbench.aoi_body_context.json.JSONEncoder',
                   side_effect=AssertionError('serialization must not start')):
            with self.assertRaisesRegex(AoiBodyContextError, 'exceeds its evidence limits'):
                render_aoi_body_context_json(oversized)

    def test_versioned_exact_render_limits_apply_to_analysis_and_replay(self):
        parts = capture_v2(document(calls='XIC(Instance.Input)Widget(Instance);'))
        for version, constant in ((1, 'MAX_CONTEXT_BYTES'), (2, 'MAX_CONTEXT_BYTES_V2')):
            with self.subTest(version=version):
                result = analyze_aoi_body_context(*parts[:-1], schema_version=version)
                rendered = render_aoi_body_context_json(result)
                with patch(f'plc_workbench.aoi_body_context.{constant}', len(rendered)):
                    self.assertEqual(render_aoi_body_context_json(result), rendered)
                    validate_aoi_body_context(*parts[:-1], result)
                with patch(f'plc_workbench.aoi_body_context.{constant}', len(rendered) - 1):
                    for operation in (
                        lambda: render_aoi_body_context_json(result),
                        lambda: analyze_aoi_body_context(*parts[:-1], schema_version=version),
                        lambda: validate_aoi_body_context(*parts[:-1], result),
                    ):
                        with self.assertRaisesRegex(AoiBodyContextError, 'exceeds its evidence limits'):
                            operation()

    def test_schema2_derivation_and_link_reservations_use_its_own_budget(self):
        parts = capture_v2(document(calls='XIC(Instance.Input)Widget(Instance);'))
        base = analyze_aoi_body_context(*parts[:-1])
        with patch('plc_workbench.aoi_body_context.MAX_CONTEXT_BYTES', 100):
            actual = analyze_aoi_body_context(*parts[:-1], schema_version=2)
            self.assertEqual(actual, parts[-1])
            validate_aoi_body_context(*parts[:-1], actual)
            with self.assertRaises(AoiBodyContextError): analyze_aoi_body_context(*parts[:-1])
        # One parameter ID needs 96 reserved bytes before it is appended. A
        # budget for the base plus 95 bytes must stop before the final render.
        with patch('plc_workbench.aoi_body_context.MAX_CONTEXT_BYTES_V2',
                   len(render_aoi_body_context_json(base)) + 95), patch(
                       'plc_workbench.aoi_body_context._render_context_json',
                       wraps=aoi_body_context._render_context_json) as renderer:
            with self.assertRaises(AoiBodyContextError):
                analyze_aoi_body_context(*parts[:-1], schema_version=2)
            self.assertEqual(renderer.call_count, 1)
        with patch('plc_workbench.aoi_body_context.MAX_CONTEXT_BYTES_V2', 100):
            self.assertEqual(analyze_aoi_body_context(*parts[:-1]), base)
            validate_aoi_body_context(*parts[:-1], base)
            with patch('plc_workbench.aoi_body_context._render_context_json',
                       side_effect=AssertionError('derivation must stop before serialization')):
                with self.assertRaises(AoiBodyContextError):
                    analyze_aoi_body_context(*parts[:-1], schema_version=2)

    def test_completed_member_rows_replace_pending_reservations_but_keep_total_links(self):
        calls = 'MOV(Instance.Input,Instance.Output)' * 40 + 'Widget(Instance);'
        parts = capture_v2(document(calls=calls))
        result = parts[-1]
        rendered = render_aoi_body_context_json(result)
        self.assertEqual(len(result.member_contexts), 80)
        base = analyze_aoi_body_context(*parts[:-1])
        retained_bytes = len(render_aoi_body_context_json(base)) + sum(
            len(json.dumps(row, ensure_ascii=True, separators=(',', ':'))) + 1
            for rows in (result.parameter_signatures, result.call_shapes, result.member_contexts)
            for row in rows)
        self.assertLess(retained_bytes, len(rendered))
        self.assertGreater(retained_bytes + 96 * (3 + 80 * 5), len(rendered))
        # Permanently charging both each reservation and its completed row
        # exceeded this exact output-sized budget for the invented population.
        with patch('plc_workbench.aoi_body_context.MAX_CONTEXT_BYTES_V2', len(rendered)):
            actual = analyze_aoi_body_context(*parts[:-1], schema_version=2)
            self.assertEqual(render_aoi_body_context_json(actual), rendered)
            validate_aoi_body_context(*parts[:-1], actual)
        # Three declared parameter IDs and five links per member still count
        # cumulatively after each row's temporary byte reservation is released.
        with patch('plc_workbench.aoi_body_context.MAX_ASSOCIATION_LINKS', 3 + 80 * 5 - 1):
            with self.assertRaisesRegex(AoiBodyContextError, 'exceeds its evidence limits'):
                analyze_aoi_body_context(*parts[:-1], schema_version=2)

    def test_signature_link_reservations_accumulate_before_the_row_is_retained(self):
        parts = capture_v2()
        base = analyze_aoi_body_context(*parts[:-1])
        base_size = len(render_aoi_body_context_json(base))
        for reserved_bytes in (95, 191, 287):
            with self.subTest(reserved_bytes=reserved_bytes), patch(
                    'plc_workbench.aoi_body_context.MAX_CONTEXT_BYTES_V2', base_size + reserved_bytes), patch(
                    'plc_workbench.aoi_body_context.json.dumps',
                    side_effect=AssertionError('signature must be bounded before row retention')):
                with self.assertRaisesRegex(AoiBodyContextError, 'exceeds its evidence limits'):
                    aoi_body_context._with_parameter_members(
                        parts[0], parts[1], parts[2], parts[3], parts[-2], base)

    def test_releasing_pending_links_keeps_previous_rows_in_the_retention_budget(self):
        parts = capture_v2(document(calls='MOV(Instance.Input,Instance.Output)Widget(Instance);'))
        result = parts[-1]
        base = analyze_aoi_body_context(*parts[:-1])
        prior_rows = result.parameter_signatures + result.call_shapes + result.member_contexts[:1]
        retained_bytes = len(render_aoi_body_context_json(base)) + sum(
            len(json.dumps(row, ensure_ascii=True, separators=(',', ':'))) + 1 for row in prior_rows)
        # The second member's five links must be checked against every earlier
        # retained row, even though their temporary reservations were released.
        with patch('plc_workbench.aoi_body_context.MAX_CONTEXT_BYTES_V2', retained_bytes + 5 * 96 - 1):
            with self.assertRaisesRegex(AoiBodyContextError, 'exceeds its evidence limits'):
                aoi_body_context._with_parameter_members(
                    parts[0], parts[1], parts[2], parts[3], parts[-2], base)


class AoiParameterSummaryTests(unittest.TestCase):
    def test_schema2_counts_are_closed_and_contain_no_source_names(self):
        parts = capture_v2(document(calls='XIC(Instance.Input)Widget(Instance);'))
        value = build_aoi_body_summary(*parts)
        text = render_aoi_body_summary(value)
        self.assertEqual(json.loads(text), value)
        self.assertEqual(value['schema_version'], 2)
        self.assertLess(len(text), 8192)
        for source in ('Widget', 'Instance', 'source_id', 'instruction_id', 'parameter_id', 'declaration_id'):
            self.assertNotIn(source, text)
        self.assertEqual(value['coverage']['matched_member_contexts'], 1)

    def test_summary_rejects_disguised_private_data_types_and_impossible_partitions(self):
        base = build_aoi_body_summary(*capture_v2(document(calls='XIC(Instance.Input)Widget(Instance);')))
        changes = (
            lambda x: x.update(schema_version=True),
            lambda x: x.update(parameter_mapping='positional'),
            lambda x: x['coverage'].update(matched_member_contexts=True),
            lambda x: x['coverage'].update(matched_member_contexts=2),
            lambda x: x['coverage']['members_by_status'].update(private=1),
            lambda x: x['coverage']['members_by_kind'].update(expression=2),
            lambda x: x['coverage']['matched_members_by_usage'].update(output=1),
            lambda x: x['coverage'].update(matched_instance_roots=0),
            lambda x: x['coverage'].update(signature_optional_parameters=2),
            lambda x: x['coverage'].update(call_argument_fields=2),
            lambda x: x['coverage'].update(call_empty_fields=1),
            lambda x: x['coverage']['calls_by_signature_observation'].update(no_required_parameters=0, required_field_count_equal=1),
        )
        for change in changes:
            value = deepcopy(base); change(value)
            with self.assertRaises(AoiBodySummaryError): validate_aoi_body_summary(value)
        with patch('plc_workbench.aoi_body_summary.MAX_REPORT_BYTES_V2', 100):
            with self.assertRaises(AoiBodySummaryError): render_aoi_body_summary(base)

    def test_no_declarations_and_unresolved_calls_have_valid_closed_counts(self):
        for xml in ('<Controller Name="Empty"/>', document(calls='Missing(Instance);')):
            validate_aoi_body_summary(build_aoi_body_summary(*capture_v2(xml)))

    def test_root_bound_member_roles_exclude_containers_and_non_data_but_keep_unknown(self):
        base = build_aoi_body_summary(*capture_v2(document(calls='XIC(Instance.Input)Widget(Instance);')))
        for role in ('expression_read', 'non_data'):
            with self.subTest(role=role):
                value = deepcopy(base)
                value['coverage']['matched_members_by_role'].update(read=0, **{role: 1})
                with self.assertRaises(AoiBodySummaryError): validate_aoi_body_summary(value)
        pid = 'PID(' + ','.join(['Instance.Input'] * 7) + ');'
        value = build_aoi_body_summary(*capture_v2(document(calls=pid)))
        self.assertEqual(value['coverage']['matched_members_by_role']['unknown'], 7)
        validate_aoi_body_summary(value)

    def test_expression_leaf_roles_use_a_lower_bound_when_candidates_have_gaps(self):
        parts = capture_v2(document(calls='CPT(Instance.Output,Instance.Input+Instance.Absent);'))
        base = build_aoi_body_summary(*parts)
        self.assertEqual(base['coverage']['members_by_kind'], {'operand': 1, 'expression': 2})
        self.assertEqual(base['coverage']['matched_members_by_role']['read'], 1)
        self.assertEqual(base['coverage']['matched_member_contexts'], 2)
        validate_aoi_body_summary(base)
        value = deepcopy(base)
        value['coverage']['matched_members_by_role'].update(read=0, write=2)
        with self.assertRaises(AoiBodySummaryError): validate_aoi_body_summary(value)

    def test_signature_classifications_agree_with_available_and_metadata_gap_populations(self):
        base = build_aoi_body_summary(*capture_v2())
        value = deepcopy(base)
        value['coverage'].update(signature_optional_parameters=0, signature_unclassified_parameters=3)
        with self.assertRaises(AoiBodySummaryError): validate_aoi_body_summary(value)
        for status in ('unsupported_metadata', 'protected'):
            value = deepcopy(base)
            value['coverage']['signatures_by_status'].update(available=0, **{status: 1})
            value['coverage']['calls_by_signature_observation'].update(no_required_parameters=0, signature_unavailable=1)
            value['status'] = 'partial'
            with self.assertRaises(AoiBodySummaryError): validate_aoi_body_summary(value)
        value = deepcopy(base)
        value['coverage'].update(signature_optional_parameters=0, signature_system_parameters=3)
        with self.assertRaises(AoiBodySummaryError): validate_aoi_body_summary(value)

    def test_partial_signature_populations_can_mix_classified_and_unclassified_parameters(self):
        params = parameter('Input') + '<Parameter Name="Output" Usage="Output"/>'
        first = document(parameters=params, calls='XIC(Instance.Input)Widget(Instance);')
        second = document().replace('Name="Invented"', 'Name="Other"')
        value = build_aoi_body_summary(*capture_v2(first + second))
        self.assertEqual(value['coverage']['signatures_by_status']['available'], 1)
        self.assertEqual(value['coverage']['signatures_by_status']['unsupported_metadata'], 1)
        self.assertEqual(value['coverage']['signature_unclassified_parameters'], 1)
        self.assertEqual(value['coverage']['signature_optional_parameters'], 4)
        validate_aoi_body_summary(value)
        # An unavailable zero-parameter declaration does not imply at least one
        # unclassified parameter; only unsupported_metadata has that guarantee.
        protected = definition('Closed', '', 'Protected="true"')
        xml = document().replace('</AddOnInstructionDefinitions>', protected + '</AddOnInstructionDefinitions>')
        value = build_aoi_body_summary(*capture_v2(xml))
        self.assertEqual(value['coverage']['signatures_by_status']['protected'], 1)
        self.assertEqual(value['coverage']['signature_unclassified_parameters'], 0)
        validate_aoi_body_summary(value)


if __name__ == '__main__':
    unittest.main()
