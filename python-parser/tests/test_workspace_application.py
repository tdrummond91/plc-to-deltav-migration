"""Invented L5X variants keep raw payloads, source facts and semantics apart."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from plc_workbench.workspace_application import ApplicationError, ApplicationIndex, validate_query
from plc_workbench.workspace_field_io import FieldIOIndex
from plc_workbench.workspace_variables import VariableIndex
from test_workspace_connections import multi_routine
from test_workspace_field_io import field_inputs, module
from test_workspace_variables import program, wire


def build(captured=None) -> ApplicationIndex:
    return ApplicationIndex(FieldIOIndex(VariableIndex(*wire(captured or field_inputs()))))


def register(index: ApplicationIndex, address: str, scope: str | None = None) -> dict:
    return next(row for row in index.registers.values()
                if row['address'] == address and (scope is None or row['scope']['name'] == scope))


def detail(index: ApplicationIndex, address: str, scope: str | None = None, **query) -> dict:
    return index.view({'run_id': 'invented-run', 'register_id': register(index, address, scope)['id'],
                       **query})['selected_register']


def payload() -> str:
    return ('<Data Format="L5K"><![CDATA[[[0,1,2],0]]]></Data>'
            '<Data Format="Decorated"><Structure DataType="InventedRaw">'
            '<ArrayMember Name="Data" DataType="SINT" Dimensions="3" Radix="Decimal">'
            '<Element Index="[0]" Value="0"/><Element Index="[1]" Value="1"/>'
            '<Element Index="[2]" Value="2"/></ArrayMember>'
            '<DataValueMember Name="ConnectionFaulted" DataType="BOOL" Value="0"/>'
            '<DataValueMember Name="DeviceStatus" DataType="DINT" Value="0"/>'
            '</Structure></Data>')


def raw_inputs():
    card = module('OpaqueDevice', 7, 'INVENTED', data='')
    card = card.replace('<InputTag><Data Format="Decorated"><Structure DataType="InventedModule"></Structure></Data></InputTag>',
                        '<InputTag ExternalAccess="Read/Write">' + payload() + '</InputTag>')
    return field_inputs(('MOV(Local:7:I.Data[1],InternalReal);',), modules=card)


class ApplicationEvidenceTests(unittest.TestCase):
    def test_raw_bytes_containment_and_diagnostics_remain_visible_without_physical_guess(self) -> None:
        index = build(raw_inputs())
        byte = register(index, 'Local:7:I.Data[1]')
        array = register(index, 'Local:7:I.Data')
        self.assertEqual((byte['datatype'], byte['radix'], byte['states']['datatype']), ('SINT', 'Decimal', 'resolved'))
        self.assertEqual(byte['parent_register_id'], array['id'])
        self.assertEqual((array['member_kind'], array['dimensions']), ('container', '3'))
        self.assertEqual(byte['external_access'], 'Read/Write')
        self.assertEqual(byte['logic_access']['roles'], ['read'])
        self.assertEqual(byte['physical']['status'], 'unknown')
        self.assertIsNone(byte['physical']['field_type'])
        self.assertEqual(register(index, 'Local:7:I.ConnectionFaulted')['datatype'], 'BOOL')
        self.assertEqual(register(index, 'Local:7:I.DeviceStatus')['datatype'], 'DINT')
        self.assertEqual({row['format_kind'] for row in detail(index, byte['address'])['representations']}, {'l5k', 'decorated'})

    def test_repeated_representations_do_not_duplicate_registers_or_select_effective_value(self) -> None:
        # Reuse the ordinary analyzer pipeline, not hand-built inventory objects.
        from test_workspace_variables import inputs
        data = payload() + payload()
        index = build(inputs(('MOV(Bytes.Data[1],Out);',),
                            '<Tag Name="Bytes" TagType="Base">' + data + '</Tag><Tag Name="Out" DataType="DINT"/>'))
        rows = [row for row in index.registers.values() if row['address'] == 'Bytes.Data[1]']
        self.assertEqual(len(rows), 1)
        selected = detail(index, 'Bytes.Data[1]')
        self.assertEqual(selected['values_total'], 2)
        self.assertEqual(selected['representations_total'], 4)
        self.assertNotIn('effective_value', selected)
        self.assertNotIn('initial_value', selected)

    def test_all_controller_directions_and_base_alias_produced_consumed_are_independent(self) -> None:
        tags = ('<Tag Name="Consumer" TagType="Consumed" DataType="REAL" ExternalAccess="Read Only">'
                '<ConsumeInfo Producer="RemoteController" RemoteTag="Published" RPI="20"/></Tag>'
                '<Tag Name="Producer" TagType="Produced" DataType="REAL">'
                '<ProduceInfo ProduceCount="3"/></Tag>'
                '<Tag Name="Internal" TagType="Base" DataType="REAL" ExternalAccess="None"/>')
        index = build(field_inputs(('MOV(Consumer,Producer);',), extra_tags=tags))
        consumer = detail(index, 'Consumer')
        self.assertEqual((consumer['declaration_kind'], consumer['io_direction'], consumer['external_access']),
                         ('consumed', 'internal', 'Read Only'))
        self.assertEqual(consumer['communications'][0]['attributes']['RPI'], '20')
        self.assertEqual(consumer['communications'][0]['status'], 'extracted')
        self.assertEqual(consumer['logic_access']['roles'], ['read'])
        self.assertEqual(detail(index, 'Producer')['logic_access']['roles'], ['write'])
        self.assertEqual(register(index, 'Internal')['physical']['status'], 'unknown')
        kinds = {row['declaration_kind'] for row in index.registers.values()}
        self.assertTrue({'module_input', 'module_output', 'module_configuration', 'alias', 'base', 'produced', 'consumed'} <= kinds)

    def test_alias_is_declaration_not_assignment_and_scope_shadowing_is_preserved(self) -> None:
        tags = ('<Tag Name="Value" DataType="DINT"/><Tag Name="A" TagType="Alias" AliasFor="Value"/>')
        programs = (program('One', ('MOV(A,Value);',), '<Tag Name="Value" DataType="REAL"/>')
                    + program('Two', ('MOV(1,Value);',), '<Tag Name="Value" DataType="DINT"/>'))
        index = build(multi_routine(programs, tags))
        alias = detail(index, 'A')
        global_value = register(index, 'Value', 'C')
        self.assertEqual(alias['alias_binding']['register_id'], global_value['id'])
        self.assertEqual(alias['alias_target'], 'Value')
        self.assertEqual(alias['logic_access']['roles'], ['read'])
        self.assertEqual(global_value['logic_access']['roles'], ['read'])
        self.assertEqual(register(index, 'Value', 'One')['datatype'], 'REAL')
        self.assertEqual(register(index, 'Value', 'One')['logic_access']['roles'], ['write'])
        self.assertNotEqual(register(index, 'Value', 'One')['id'], register(index, 'Value', 'Two')['id'])

    def test_cpt_sources_and_destination_link_exact_expression_without_execution_claim(self) -> None:
        index = build()
        source = detail(index, 'Local:3:I.Ch0Data')
        use = next(use for use in source['uses']['items'] if use['opcode'] == 'CPT')
        self.assertEqual(use['role'], 'read')
        self.assertEqual(use['expression'], 'Local:3:I.Ch0Data+1')
        self.assertEqual(use['destination'], 'InternalReal')
        self.assertEqual(use['exact_instruction'], 'CPT(InternalReal,Local:3:I.Ch0Data+1)')
        destination = detail(index, 'InternalReal')
        self.assertTrue(any(use['opcode'] == 'CPT' and use['role'] == 'write' for use in destination['uses']['items']))
        self.assertEqual(index.coverage['gaps'].get('unresolved_or_unqualified_reference_operands', 0), 0)
        self.assertNotIn('execution_order', use)

    def test_cpt_expression_alias_spelling_stays_original(self) -> None:
        tags = ('<Tag Name="Value" DataType="REAL"/><Tag Name="Output" DataType="REAL"/>'
                '<Tag Name="Alias" TagType="Alias" AliasFor="Value"/>')
        index = build(multi_routine(program('P', ('CPT(Output,Alias+1);',)), tags))
        row = detail(index, 'Value')
        self.assertEqual(row['uses']['items'][0]['operand'], 'Alias')
        self.assertEqual(row['uses']['items'][0]['expression'], 'Alias+1')

    def test_parent_attachment_is_parent_port_not_child_upstream_port(self) -> None:
        bridge = module('Bridge', 2, '1756-EN2T').replace('</Ports>', '<Port Id="2" Type="Ethernet" Address="192.0.2.10" Upstream="false"/></Ports>')
        remote = module('Remote', 3, 'INVENTED').replace('ParentModule="Local" ParentModPortId="1"', 'ParentModule="Bridge" ParentModPortId="2"')
        index = build(field_inputs(modules=bridge + remote))
        selected = next(row for row in index.modules.values() if row['name'] == 'Remote')
        self.assertEqual(selected['attachment']['parent_port_type'], 'Ethernet')
        self.assertEqual(selected['attachment']['parent_port_address'], '192.0.2.10')
        self.assertEqual(selected['ports'][0]['type'], 'ICP')
        self.assertEqual([row['name'] for row in selected['route']['modules']], ['Local', 'Bridge', 'Remote'])
        self.assertEqual(selected['route']['status'], 'resolved_to_root')

    def test_missing_duplicate_port_and_module_cycles_are_explained(self) -> None:
        for extra, expected in (
                (module('A', 1, 'INVENTED').replace('ParentModPortId="1"', 'ParentModPortId="9"'), 'parent_port_missing'),
                (module('A', 1, 'INVENTED').replace('ParentModule="Local"', 'ParentModule="Missing"'), 'parent_missing'),
                (module('A', 1, 'INVENTED').replace('ParentModule="Local"', 'ParentModule="B"') +
                 module('B', 2, 'INVENTED').replace('ParentModule="Local"', 'ParentModule="A"'), 'cycle')):
            with self.subTest(expected=expected):
                index = build(field_inputs(modules=extra))
                row = next(row for row in index.modules.values() if row['name'] == 'A')
                self.assertEqual(row['route']['status'], expected)

    def test_connection_attrs_preserve_rpi_paths_suffixes_sizes(self) -> None:
        card = module('Remote', 1, 'INVENTED').replace('<Connection Name="Data">',
            '<Connection Name="Data" RPI="20000" ConnectionPath="2 192.0.2.20" InputSize="24" OutputSize="8" InputTagSuffix="InPayload" OutputTagSuffix="OutPayload">')
        index = build(field_inputs(modules=card))
        row = next(row for row in index.modules.values() if row['name'] == 'Remote')['connections'][0]
        self.assertEqual(row['attributes']['RPI'], '20000')
        self.assertEqual(row['attributes']['InputSize'], '24')
        self.assertEqual(row['attributes']['ConnectionPath'], '2 192.0.2.20')
        self.assertEqual(row['attribute_help']['RPI']['units'], 'microseconds')
        self.assertTrue(row['input_root_ids'])

    def test_documented_profiles_are_separate_from_generic_real_members_and_status(self) -> None:
        index = build()
        self.assertEqual(register(index, 'Local:3:I.Ch0Data')['physical']['field_type'], 'ai')
        for address in ('InternalReal', 'Local:5:I.Ch0Data', 'Local:2:I.Data.0', 'Local:1:I.Fault.0'):
            with self.subTest(address=address):
                self.assertEqual(register(index, address)['physical']['status'], 'unknown')
        self.assertEqual(index.coverage['vendor_decoded_payloads'], 0)

    def test_dynamic_copy_aoi_and_unsupported_coverage_is_not_declared_complete(self) -> None:
        tags = '<Tag Name="Bytes" DataType="SINT" Dimensions="3"/><Tag Name="Offset" DataType="DINT"/><Tag Name="Out" DataType="REAL"/>'
        extra = ('<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="Custom">'
                 '<Parameters><Parameter Name="In" DataType="REAL" Usage="Input"/></Parameters>'
                 '<LocalTags><LocalTag Name="Memory" DataType="REAL"/></LocalTags>'
                 '<EncodedData>invented protected payload</EncodedData></AddOnInstructionDefinition></AddOnInstructionDefinitions>')
        index = build(multi_routine(program('Main', ('MOV(Bytes[Offset],Out);', 'COP(Bytes[0],Out,2);', 'Custom(Out);')), tags, extra))
        self.assertGreater(index.coverage['gaps']['unresolved_or_unqualified_reference_operands'], 0)
        self.assertEqual(index.coverage['copy_range_instructions_not_expanded'], 1)
        self.assertEqual(index.coverage['aoi_calls_not_expanded'], 1)
        self.assertIn('captured_and_statically', index.coverage['totals_scope'])
        self.assertEqual(register(index, 'Memory')['declaration_kind'], 'aoi_local')
        self.assertEqual(register(index, 'In')['declaration_kind'], 'aoi_parameter')
        self.assertFalse(any(row['address'] == 'Bytes[Offset]' for row in index.registers.values()))

    def test_description_precedence_conflicts_and_scope_are_preserved(self) -> None:
        tags = ('<Tag Name="Record" DataType="InventedRecord"><Description>Container description</Description>'
                '<Comments><Comment Operand="Value">Member description</Comment>'
                '<Comment Operand="Value">Conflicting description</Comment></Comments>'
                '<Data Format="Decorated"><Structure DataType="InventedRecord">'
                '<DataValueMember Name="Value" DataType="REAL" Value="1.0"/></Structure></Data></Tag>')
        index = build(multi_routine(program('Main', ('MOV(Record.Value,Record.Value);',)), tags))
        row = detail(index, 'Record.Value')
        self.assertEqual(row['description'], 'Member description')
        self.assertEqual(row['description_selection']['basis'], 'exact_member_comment')
        self.assertTrue(row['description_selection']['conflict'])
        self.assertEqual(row['description_selection']['candidate_count'], 3)
        self.assertTrue(all(note['owner_id'] == row['source_id'] for note in row['source_annotations']))

    def test_foreign_namespaces_do_not_create_qualified_members_or_alias_bindings(self) -> None:
        card = module('Foreign', 1, '1756-IF8', extra='xmlns:x="urn:invented" x:Marker="present"')
        index = build(field_inputs(modules=card))
        root = next(row for row in index.registers.values() if row['module_id'] and row['io_direction'] == 'input')
        self.assertEqual(root['states']['source_qualification'], 'unknown')
        self.assertEqual(root['physical']['status'], 'unknown')
        self.assertEqual(next(row for row in index.modules.values() if row['name'] == 'Foreign')['route']['status'], 'source_unqualified')

    def test_inherited_metadata_conflicts_remain_unresolved(self) -> None:
        data = ('<Data Format="Decorated"><Array DataType="SINT" Dimensions="2" Radix="Decimal">'
                '<Element Index="[0]" DataType="REAL" Radix="Float" Value="1"/>'
                '<Element Index="[1]" Value="2"/></Array></Data>')
        tags = '<Tag Name="Payload" DataType="SINT" Dimensions="2">' + data + '</Tag>'
        index = build(multi_routine(program('P', ('MOV(Payload[0],Payload[1]);',)), tags))
        self.assertIsNone(register(index, 'Payload[0]')['datatype'])
        self.assertEqual(register(index, 'Payload[0]')['states']['member'], 'unknown')
        self.assertEqual(register(index, 'Payload[1]')['datatype'], 'SINT')
        self.assertEqual(detail(index, 'Payload[0]')['values'][0]['metadata_status'], 'conflict')

    def test_page_sizes_filters_and_source_identity_are_stable(self) -> None:
        tags = ''.join(f'<Tag Name="Value{i}" DataType="REAL"/>' for i in range(225))
        index = build(multi_routine(program('P', ('MOV(Value0,Value1);',)), tags))
        first = index.view({'run_id': 'r', 'page_size': 100})
        second = index.view({'run_id': 'r', 'page_size': 100, 'page': 2})
        self.assertEqual(first['registers']['total'], 225)
        self.assertEqual(len(first['registers']['items']), 100)
        self.assertFalse({row['id'] for row in first['registers']['items']} & {row['id'] for row in second['registers']['items']})
        unused = index.view({'run_id': 'r', 'logic_role': 'unused', 'datatype': 'real', 'page_size': 500})
        self.assertEqual(unused['registers']['total'], 223)
        self.assertTrue(all(row['source_id'].startswith('tag_') for row in first['registers']['items']))
        first['registers']['items'][0]['address'] = 'changed'
        self.assertNotEqual(index.view({'run_id': 'r', 'page_size': 100})['registers']['items'][0]['address'], 'changed')

    def test_use_pagination_and_unknown_selection_validation(self) -> None:
        tags = '<Tag Name="A" DataType="REAL"/><Tag Name="B" DataType="REAL"/>'
        index = build(multi_routine(program('P', tuple('MOV(A,B);' for _ in range(26))), tags))
        selected = detail(index, 'A', page_size=10, use_page=2)
        self.assertEqual((selected['uses']['total'], selected['uses']['page'], len(selected['uses']['items'])), (26, 2, 10))
        for query in ({'register_id': 'missing'}, {'module_id': 'missing'}):
            with self.assertRaises(ApplicationError):
                index.view({'run_id': 'r', **query})

    def test_bad_filters_and_oversized_response_fail_closed(self) -> None:
        for query in ({'run_id': ''}, {'run_id': 'r', 'page_size': 11}, {'run_id': 'r', 'page_size': True},
                      {'run_id': 'r', 'page': 0}, {'run_id': 'r', 'direction': 'di'},
                      {'run_id': 'r', 'logic_role': 'live'}, {'run_id': 'r', 'query': '\n'}):
            with self.subTest(query=query), self.assertRaises(ApplicationError):
                validate_query(query)
        index = build()
        with patch('plc_workbench.workspace_application.MAX_RESPONSE_BYTES', 10), self.assertRaises(ApplicationError):
            index.view({'run_id': 'r'})
        with patch('plc_workbench.workspace_application.MAX_REGISTERS', 1), self.assertRaises(ApplicationError):
            build()

    def test_source_evidence_is_never_mutated_by_projection(self) -> None:
        io = FieldIOIndex(VariableIndex(*wire(field_inputs())))
        before = json.dumps({'modules': io.modules, 'addresses': io.addresses, 'values': list(io.base._values.items())}, sort_keys=True)
        index = ApplicationIndex(io)
        index.view({'run_id': 'r'})
        after = json.dumps({'modules': io.modules, 'addresses': io.addresses, 'values': list(io.base._values.items())}, sort_keys=True)
        self.assertEqual(before, after)

    def test_ambiguous_members_and_ancestors_are_never_reported_resolved(self) -> None:
        for data in (
                '<Structure DataType="Thing"><DataValueMember Name="Speed" DataType="REAL" Value="1"/>'
                '<DataValueMember Name="Speed" DataType="REAL" Value="2"/></Structure>',
                '<Structure DataType="Thing"><StructureMember Name="Nested" DataType="Thing">'
                '<DataValueMember Name="Speed" DataType="REAL" Value="1"/></StructureMember>'
                '<StructureMember Name="Nested" DataType="Thing">'
                '<DataValueMember Name="Speed" DataType="REAL" Value="2"/></StructureMember></Structure>'):
            with self.subTest(data=data):
                tags = '<Tag Name="T"><Data Format="Decorated">' + data + '</Data></Tag>'
                index = build(multi_routine(program('P', ()), tags))
                suffix = '.Nested.Speed' if 'Nested' in data else '.Speed'
                row = detail(index, 'T' + suffix)
                self.assertEqual(row['states']['member'], 'unknown')
                self.assertTrue(all(value['ambiguous'] for value in row['values']))
                self.assertIsNone(row['datatype'])

    def test_declared_and_captured_datatype_conflict_is_explicit(self) -> None:
        tags = ('<Tag Name="T" DataType="DINT"><Data Format="Decorated">'
                '<DataValue DataType="REAL" Radix="Float" Value="1.0"/></Data></Tag>')
        row = detail(build(multi_routine(program('P', ()), tags)), 'T')
        self.assertIsNone(row['datatype'])
        self.assertEqual(row['declared_datatype'], 'DINT')
        self.assertEqual(row['metadata_conflicts']['datatype']['captured'], 'REAL')
        self.assertEqual(row['values'][0]['datatype'], 'REAL')

    def test_static_root_array_inherits_only_in_bounds_declaration(self) -> None:
        tags = '<Tag Name="T" DataType="REAL" Dimensions="3" Radix="Float"/><Tag Name="O" DataType="REAL"/>'
        index = build(multi_routine(program('P', ('MOV(T[1],O);', 'MOV(T[9],O);')), tags))
        self.assertEqual(register(index, 'T[1]')['datatype'], 'REAL')
        self.assertEqual(register(index, 'T[1]')['provenance']['datatype_basis'], 'static_root_array_element')
        self.assertIsNone(register(index, 'T[9]')['datatype'])
        self.assertFalse(any(row['address'] == 'T[0]' for row in index.registers.values()))

    def test_udt_members_and_nested_array_declarations_without_values(self) -> None:
        definitions = ('<DataTypes><DataType Name="Inner"><Members>'
                       '<Member Name="Speed" DataType="REAL" Dimension="0" ExternalAccess="Read Only"/>'
                       '</Members></DataType><DataType Name="Outer"><Members>'
                       '<Member Name="Bytes" DataType="SINT" Dimension="8"/>'
                       '<Member Name="Child" DataType="Inner" Dimension="3"/>'
                       '</Members></DataType></DataTypes>')
        tags = '<Tag Name="T" DataType="Outer"/><Tag Name="O" DataType="REAL"/>'
        index = build(multi_routine(program('P', ('MOV(T.Child[1].Speed,O);', 'MOV(T.Bytes[2],O);')), tags, definitions))
        self.assertEqual(register(index, 'T.Child[1].Speed')['datatype'], 'REAL')
        self.assertEqual(register(index, 'T.Child[1].Speed')['external_access'], 'Read Only')
        self.assertEqual(register(index, 'T.Bytes[2]')['datatype'], 'SINT')
        self.assertEqual(register(index, 'T.Bytes[2]')['member_kind'], 'scalar')
        self.assertIsNone(register(index, 'T.Bytes[2]')['dimensions'])
        self.assertEqual(register(index, 'T.Bytes')['dimensions'], '8')
        self.assertFalse(any(row['address'] == 'T.Child[0]' for row in index.registers.values()))
        self.assertEqual(detail(index, 'T')['datatype_definition']['members_total'], 2)
        self.assertEqual(detail(index, 'T.Child[1].Speed')['values_total'], 0)
        self.assertTrue(register(index, 'T.Child[1].Speed')['declaration_member']['source_id'].startswith('data_type_'))

    def test_unknown_kind_and_timer_placeholders_are_not_misclassified(self) -> None:
        tags = '<Tag Name="T" DataType="TIMER"/><Tag Name="Odd" TagType="Invented" DataType="REAL"/>'
        index = build(multi_routine(program('P', ('TON(T,?,?);',)), tags))
        self.assertEqual(register(index, 'Odd')['declaration_kind'], 'unknown')
        self.assertEqual(index.coverage['gaps'].get('unresolved_or_unqualified_reference_operands', 0), 0)
        self.assertEqual(index.view({'run_id': 'r', 'declaration_kind': 'unknown'})['registers']['total'], 1)

    def test_full_description_lookup_retains_translation_cache_identity(self) -> None:
        description = 'A long invented description. ' * 100
        tags = '<Tag Name="T" DataType="DINT"><Description>' + description + '</Description></Tag>'
        index = build(multi_routine(program('P', ()), tags))
        row = register(index, 'T')
        self.assertEqual(index.annotation_texts[row['description_selection']['preferred_annotation_id']], description)

    def test_udt_description_is_qualified_fallback_and_dimensions_conflict_is_visible(self) -> None:
        definitions = ('<DataTypes><DataType Name="Container"><Members>'
                       '<Member Name="Bytes" DataType="SINT" Dimension="8"><Description>'
                       '<![CDATA[Invented received-byte payload]]></Description></Member>'
                       '</Members></DataType></DataTypes>')
        tags = ('<Tag Name="T" DataType="Container"><Description>Generic declaration</Description>'
                '<Data Format="Decorated"><Structure DataType="Container">'
                '<ArrayMember Name="Bytes" DataType="SINT" Dimensions="4">'
                '<Element Index="[1]" Value="2"/></ArrayMember></Structure></Data></Tag>')
        index = build(multi_routine(program('P', ()), tags, definitions))
        row = detail(index, 'T.Bytes')
        self.assertEqual(row['description'], 'Invented received-byte payload')
        self.assertEqual(row['description_selection']['basis'], 'declared_member_description')
        self.assertIsNone(row['dimensions'])
        self.assertEqual(row['metadata_conflicts']['dimensions']['captured'], '4')
        self.assertEqual(row['metadata_conflicts']['dimensions']['declared'], '8')
        self.assertEqual(detail(index, 'T')['datatype_definition']['members'][0]['description'], 'Invented received-byte payload')
        self.assertEqual(register(index, 'T.Bytes[1]')['member_kind'], 'scalar')
        exact = tags.replace('<Data Format="Decorated">',
                             '<Comments><Comment Operand="Bytes">Exact byte-array note</Comment></Comments><Data Format="Decorated">')
        exact_index = build(multi_routine(program('P', ()), exact, definitions))
        exact_row = detail(exact_index, 'T.Bytes')
        self.assertEqual(exact_row['description'], 'Exact byte-array note')
        self.assertEqual(exact_row['description_selection']['basis'], 'exact_member_comment')
        declared_note = next(note for note in exact_row['source_annotations'] if note['kind'] == 'datatype_member_description')
        self.assertTrue(declared_note['source_id'].startswith('data_type_'))
        self.assertIn('/Members[1]/Member[1]/Description[1]', declared_note['locator'])

    def test_module_payload_uses_udt_description_before_module_fallback(self) -> None:
        definition = ('<DataTypes><DataType Name="RawPayload"><Members>'
                      '<Member Name="Byte" DataType="SINT" Dimension="0">'
                      '<Description>Declared payload byte</Description></Member></Members></DataType></DataTypes>')
        card = module('Generic', 1, 'INVENTED', data='<DataValueMember Name="Byte" DataType="SINT" Value="0"/>')
        card = card.replace('<InputTag>', '<InputTag DataType="RawPayload">').replace('DataType="InventedModule"', 'DataType="RawPayload"')
        local = '<Module Name="Local" ParentModule="Local" ParentModPortId="1"><Ports><Port Id="1" Type="ICP" Address="0" Upstream="false"/></Ports></Module>'
        index = build(multi_routine(program('P', ()), '', definition + '<Modules>' + local + card + '</Modules>'))
        row = detail(index, 'Local:1:I.Byte')
        self.assertEqual(row['description'], 'Declared payload byte')
        self.assertEqual(row['description_selection']['basis'], 'declared_member_description')


if __name__ == '__main__':
    unittest.main()
