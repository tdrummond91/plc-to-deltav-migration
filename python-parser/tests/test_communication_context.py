"""Invented MSG and tag connection evidence, never live controller data."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access
from plc_workbench.calculations import analyze_calculations
from plc_workbench.communication_context import (
    CommunicationContextError, analyze_communication_context,
    render_communication_context_json, validate_communication_context,
)
from plc_workbench.references import analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.tag_data import analyze_tag_data


def tag(name: str, datatype: str = 'DINT', body: str = '', attributes: str = '') -> str:
    return f'<Tag Name="{name}" DataType="{datatype}" {attributes}>{body}</Tag>'


def message(attributes: str = 'LocalElement="LocalValue" RemoteElement="RemoteSecret"',
            body: str = '') -> str:
    return f'<Data Format="Message"><MessageParameters {attributes}>{body}</MessageParameters></Data>'


def program(text: str, tags: str = '', name: str = 'P') -> str:
    return (f'<Program Name="{name}"><Tags>{tags}</Tags><Routines><Routine Name="R" Type="RLL">'
            f'<RLLContent><Rung Number="0"><Text><![CDATA[{text}]]></Text></Rung></RLLContent>'
            '</Routine></Routines></Program>')


def capture(text: str = 'MSG(Control);', tags: str | None = None, local_tags: str = '',
            extra_programs: str = '', namespace: str = '', extra_controllers: str = '',
            extra_body: str = '', schema_version: int = 1):
    if tags is None:
        tags = tag('Control', 'MESSAGE', message()) + tag('LocalValue')
    source = (f'<RSLogix5000Content{namespace}><Controller Name="C"><Tags>{tags}</Tags>{extra_body}<Programs>'
              + program(text, local_tags) + extra_programs + '</Programs></Controller>'
              + extra_controllers + '</RSLogix5000Content>')
    snapshot = snapshot_from_bytes(source.encode('utf-8'))
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    access = analyze_access(inventory, references)
    tag_data = analyze_tag_data(snapshot, inventory)
    result = analyze_communication_context(snapshot, inventory, references, access, tag_data, schema_version=schema_version)
    return snapshot, inventory, references, access, tag_data, result


class CommunicationContextTests(unittest.TestCase):
    def test_direct_configuration_links_control_parameter_and_local_candidate_only(self):
        parts = capture()
        result = parts[-1]
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.occurrences[0]['status'], 'linked')
        owner = result.owners[0]
        parameter = result.parameters[0]
        endpoint = result.endpoints[0]
        self.assertEqual(result.occurrences[0]['owner_id'], owner['source_id'])
        self.assertEqual(owner['parameter_ids'], [parameter['source_id']])
        self.assertEqual(parameter['source_id'], parts[-2].elements[0]['id'])
        self.assertEqual(parameter['content_id'], parts[-2].contents[0]['id'])
        self.assertEqual(parameter['attributes']['RemoteElement'], 'RemoteSecret')
        self.assertEqual(endpoint['field'], 'LocalElement')
        self.assertEqual(endpoint['status'], 'root_candidate')
        self.assertEqual(endpoint['binding']['target_id'], next(e.id for e in parts[1].entities if e.name == 'LocalValue'))
        self.assertEqual(result.remote_binding, 'not_performed')
        validate_communication_context(*parts)

    def test_providers_stay_unchanged_and_access4_replays(self):
        parts = capture('MSG(Control)CPT(LocalValue,LocalValue+1);')
        before = [p.to_dict() for p in parts[1:-1]]
        validate_communication_context(*parts)
        self.assertEqual(before, [p.to_dict() for p in parts[1:-1]])
        snapshot, inventory, references, _, tag_data, expected = parts
        calculations = analyze_calculations(snapshot, inventory, references)
        access = analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
        actual = analyze_communication_context(snapshot, inventory, references, access, tag_data, calculations=calculations)
        self.assertEqual(actual.to_dict(), expected.to_dict())
        with self.assertRaises(CommunicationContextError):
            analyze_communication_context(snapshot, inventory, references, access, tag_data)

    def test_repeated_calls_and_multiple_envelopes_parameters_remain_separate(self):
        data = message('LocalElement="LocalValue" DestinationTag="LocalValue"') + message('LocalElement="LocalValue"')
        parts = capture('MSG(Control)MSG(Control);', tag('Control', 'MESSAGE', data) + tag('LocalValue'))
        result = parts[-1]
        self.assertEqual(len(result.occurrences), 2)
        self.assertEqual(len(result.parameters), 2)
        self.assertEqual(len(result.endpoints), 3)
        self.assertEqual(len({row['source_id'] for row in result.parameters}), 2)
        self.assertEqual([row['status'] for row in result.occurrences], ['multiple_representations'] * 2)
        self.assertEqual(result.coverage['owners_with_multiple_contents'], 1)
        self.assertEqual(result.coverage['owners_with_multiple_parameters'], 1)
        self.assertEqual(result.coverage['endpoints_by_field'], {'DestinationTag': 1, 'LocalElement': 2})
        self.assertEqual(result.occurrences[0]['parameter_ids'], result.occurrences[1]['parameter_ids'])
        direct = '<Data Format="Message"><MessageParameters/><MessageParameters/></Data>'
        same = capture(tags=tag('Control', 'MESSAGE', direct))[-1]
        self.assertEqual(same.coverage['contents_total'], 1)
        self.assertEqual(same.coverage['parameter_records'], 2)
        self.assertEqual(same.occurrences[0]['status'], 'multiple_representations')

    def test_local_resolution_uses_control_owner_scope_not_calling_program(self):
        tags = tag('Control', 'MESSAGE', message('LocalElement="Alias.Member[01]"'))
        tags += tag('Alias', attributes='TagType="Alias" AliasFor="LocalValue"') + tag('LocalValue')
        parts = capture(tags=tags, local_tags=tag('LocalValue'))
        endpoint = parts[-1].endpoints[0]
        controller_value = next(e for e in parts[1].entities if e.name == 'LocalValue' and e.scope_id == parts[1].entities[0].id)
        self.assertEqual(endpoint['binding']['target_id'], controller_value.id)
        self.assertEqual(endpoint['binding']['suffix'], '.Member[01]')
        self.assertEqual(len(endpoint['binding']['alias_chain']), 1)
        self.assertEqual(endpoint['status'], 'root_candidate')

    def test_program_local_control_and_alias_shadow_controller_declarations(self):
        tags = tag('Control', 'MESSAGE', message('LocalElement="Value"')) + tag('Value')
        local = tag('Control', 'MESSAGE', message('LocalElement="Value"')) + tag('Value')
        local += tag('ControlAlias', attributes='TagType="Alias" AliasFor="Control"')
        parts = capture('MSG(ControlAlias);', tags, local)
        program_scope = next(e.id for e in parts[1].entities if e.kind == 'program')
        occurrence = parts[-1].occurrences[0]
        control = next(e for e in parts[1].entities if e.name == 'Control' and e.scope_id == program_scope)
        self.assertEqual(occurrence['owner_id'], control.id)
        endpoint = next(r for r in parts[-1].endpoints if r['owner_id'] == control.id)
        self.assertEqual(endpoint['scope_id'], program_scope)
        target = next(e for e in parts[1].entities if e.id == endpoint['binding']['target_id'])
        self.assertEqual(target.scope_id, program_scope)

    def test_control_signature_type_array_member_and_binding_gaps(self):
        tags = tag('Control', 'MESSAGE', message()) + tag('LocalValue')
        tags += tag('Wrong', 'DINT', message()) + tag('Array', 'MESSAGE', message(), 'Dimensions="2"')
        result = capture('MSG(Control.EN)MSG(Control[0])MSG(Array)MSG(Control[Index])'
                         'MSG(Wrong)MSG(Missing)MSG(Control,Wrong)MSG();', tags)[-1]
        self.assertEqual([r['status'] for r in result.occurrences], [
            'control_member_unsupported', 'control_array_unsupported', 'control_array_unsupported',
            'control_binding_gap', 'control_type_unconfirmed', 'control_binding_gap', 'signature_gap', 'signature_gap'])
        self.assertTrue(all(not row['parameter_ids'] for row in result.occurrences))
        self.assertEqual({r['status'] for r in result.parameters}, {'supported', 'type_gap', 'array_gap'})

    def test_missing_configuration_does_not_infer_values_from_decorated_representation(self):
        result = capture(tags=tag('Control', 'MESSAGE', '<Data Format="Decorated"><Structure DataType="MESSAGE"/></Data>'))[-1]
        self.assertEqual(result.occurrences[0]['status'], 'missing_parameters')
        self.assertEqual(result.parameters, [])
        self.assertEqual(result.endpoints, [])

    def test_ambiguous_control_declarations_and_alias_members_do_not_select_parameters(self):
        data = tag('Control', 'MESSAGE', message())
        result = capture(tags=data + data + tag('LocalValue'))[-1]
        self.assertEqual(result.occurrences[0]['status'], 'control_binding_gap')
        self.assertIsNone(result.occurrences[0]['owner_id'])
        self.assertEqual(len(result.parameters), 2)
        tags = data + tag('Alias', attributes='TagType="Alias" AliasFor="Control.EN"')
        result = capture('MSG(Alias);', tags)[-1]
        self.assertEqual(result.occurrences[0]['status'], 'control_member_unsupported')
        self.assertEqual(result.occurrences[0]['parameter_ids'], [])

    def test_alias_declaration_data_cannot_become_an_independent_configuration_owner(self):
        tags = tag('Control', 'MESSAGE', message()) + tag('LocalValue')
        tags += tag('Alias', 'MESSAGE', message(), 'TagType="Alias" AliasFor="Control"')
        result = capture('MSG(Alias);', tags)[-1]
        self.assertEqual(result.occurrences[0]['status'], 'linked')
        self.assertEqual([row['status'] for row in result.parameters], ['supported', 'type_gap'])
        self.assertEqual([row['status'] for row in result.endpoints], ['root_candidate', 'unsupported_context'])

    def test_shadowed_message_type_and_nonbase_owners_are_type_gaps(self):
        for definitions in ('<DataTypes><DataType Name="MESSAGE"/></DataTypes>',
                            '<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="Message"/></AddOnInstructionDefinitions>'):
            result = capture(extra_body=definitions)[-1]
            self.assertEqual(result.occurrences[0]['status'], 'control_type_unconfirmed')
            self.assertEqual(result.parameters[0]['status'], 'type_gap')
            self.assertEqual(result.endpoints[0]['status'], 'unsupported_context')
        result = capture(tags=tag('Control', 'MESSAGE', message(), 'TagType="Produced"'))[-1]
        self.assertEqual(result.occurrences[0]['status'], 'control_type_unconfirmed')

    def test_unrelated_controller_type_declaration_cannot_shadow_control_owner(self):
        extra = '<Controller Name="Other"><DataTypes><DataType Name="MESSAGE"/></DataTypes></Controller>'
        self.assertEqual(capture(extra_controllers=extra)[-1].occurrences[0]['status'], 'linked')

    def test_wrong_envelopes_and_nested_parameters_retained_without_candidates(self):
        cases = ('<Data Format="Decorated"><MessageParameters LocalElement="LocalValue"/></Data>',
                 '<DefaultData Format="Message"><MessageParameters LocalElement="LocalValue"/></DefaultData>',
                 '<Data Format="Message"><Wrapper><MessageParameters LocalElement="LocalValue"/></Wrapper></Data>',
                 '<Data Format="Message">unexpected<MessageParameters LocalElement="LocalValue"/></Data>',
                 '<Data Format="Message"><MessageParameters LocalElement="LocalValue"/><VendorConfig/></Data>',
                 message('LocalElement="LocalValue"', '<Extension/>'),
                 message('LocalElement="LocalValue"', 'unexpected'))
        for data in cases:
            with self.subTest(data=data):
                result = capture(tags=tag('Control', 'MESSAGE', data) + tag('LocalValue'))[-1]
                self.assertEqual(result.parameters[0]['status'], 'unsupported_shape')
                self.assertEqual(result.occurrences[0]['status'], 'unsupported_parameters')
                self.assertEqual(result.endpoints[0]['status'], 'unsupported_context')
                self.assertIsNone(result.endpoints[0]['binding']['target_id'])

    def test_root_namespace_supported_and_foreign_names_attributes_not_promoted(self):
        self.assertEqual(capture(namespace=' xmlns="urn:logix"')[-1].status, 'complete')
        cases = ('<Data Format="Message"><v:MessageParameters LocalElement="LocalValue"/></Data>',
                 '<v:Data Format="Message"><MessageParameters LocalElement="LocalValue"/></v:Data>',
                 '<Data Format="Message"><MessageParameters v:LocalElement="LocalValue"/></Data>')
        for data in cases:
            result = capture(tags=tag('Control', 'MESSAGE', data) + tag('LocalValue'), namespace=' xmlns:v="urn:vendor"')[-1]
            self.assertEqual(result.parameters[0]['status'], 'unsupported_context')
            self.assertEqual(result.occurrences[0]['status'], 'unsupported_parameters')
            self.assertTrue(all(e['status'] == 'unsupported_context' for e in result.endpoints))
        self.assertEqual(result.endpoints, [])
        self.assertEqual(result.parameters[0]['attributes'], {'urn:vendor}LocalElement': 'LocalValue'})

    def test_foreign_target_and_alias_context_never_become_root_candidates(self):
        tags = '<v:Tag Name="LocalValue" DataType="DINT"/>'
        result = capture(tags=tags, local_tags=tag('Control', 'MESSAGE', message()),
                         namespace=' xmlns:v="urn:vendor"')[-1]
        self.assertEqual(result.endpoints[0]['status'], 'unsupported_context')
        tags += '<v:Tag Name="Alias" TagType="Alias" AliasFor="LocalValue"/>'
        result = capture(tags=tags, local_tags=tag('Control', 'MESSAGE', message('LocalElement="Alias"')),
                         namespace=' xmlns:v="urn:vendor"')[-1]
        self.assertEqual(result.endpoints[0]['status'], 'unsupported_context')

    def test_qualified_dynamic_ambiguous_missing_cycle_and_composed_invalid_local_paths(self):
        cases = (
            ('Program:P.LocalValue', 'qualified_unsupported', 'program_qualified_address', ''),
            ('\\Remote\\Value', 'qualified_unsupported', 'backslash_qualified_address', ''),
            ('LocalValue[Index]', 'binding_gap', 'non_static_array_index', ''),
            ('Missing', 'binding_gap', 'root_not_declared', ''),
            ('LocalValue', 'binding_gap', None, tag('LocalValue')),
            ('Cycle', 'binding_gap', None, tag('Cycle', attributes='TagType="Alias" AliasFor="Cycle"')),
            ('Bit.Member', 'invalid_expanded_suffix', None, tag('Bit', attributes='TagType="Alias" AliasFor="LocalValue.1"')),
        )
        for raw, expected, reason, more in cases:
            with self.subTest(raw=raw):
                tags = tag('Control', 'MESSAGE', message(f'LocalElement="{raw}"')) + tag('LocalValue') + more
                endpoint = capture(tags=tags)[-1].endpoints[0]
                self.assertEqual(endpoint['status'], expected)
                self.assertEqual(endpoint['binding']['reason'], reason)

    def test_remote_fields_stay_authored_even_when_a_local_declaration_matches(self):
        data = message('RemoteElement="LocalValue" ConnectionPath="LocalValue" MessageType="SecretProtocol" Vendor="Unchanged"')
        result = capture(tags=tag('Control', 'MESSAGE', data) + tag('LocalValue'))[-1]
        self.assertEqual(result.endpoints, [])
        self.assertEqual(result.parameters[0]['attributes'], {
            'RemoteElement': 'LocalValue', 'ConnectionPath': 'LocalValue',
            'MessageType': 'SecretProtocol', 'Vendor': 'Unchanged'})
        self.assertEqual(result.coverage['parameter_fields']['RemoteElement'], 1)
        self.assertEqual(result.coverage['parameter_fields']['ConnectionPath'], 1)

    def test_direct_produce_consume_metadata_retains_repeats_and_no_peer_binding(self):
        tags = tag('Produced', body='<ProduceInfo Consumers="2"/><ProduceInfo Consumers="3"/>')
        tags += tag('Consumed', body='<ConsumeInfo Producer="PrivatePeer" RemoteTag="SecretRemote"/>')
        tags += tag('Nested', body='<Vendor><ProduceInfo Consumers="9"/></Vendor>')
        result = capture(';', tags)[-1]
        self.assertEqual(result.coverage['tag_connections_by_kind'], {'ConsumeInfo': 1, 'ProduceInfo': 2})
        self.assertEqual(result.coverage['tags_with_connections'], 2)
        self.assertEqual(len({r['id'] for r in result.tag_connections}), 3)
        self.assertEqual(result.tag_connections[-1]['attributes']['Producer'], 'PrivatePeer')
        self.assertEqual(result.endpoints, [])
        self.assertTrue(all(r['status'] == 'source_metadata' for r in result.tag_connections))

    def test_tag_connections_with_unknown_namespace_or_children_remain_gaps(self):
        tags = tag('Produced', body='<v:ProduceInfo/><ConsumeInfo><Extension/></ConsumeInfo>')
        result = capture(';', tags, namespace=' xmlns:v="urn:vendor"')[-1]
        self.assertEqual([r['status'] for r in result.tag_connections], ['unsupported_context', 'unsupported_shape'])
        self.assertEqual(result.tag_connections[1]['child_elements'], 1)
        for kind in ('ProduceInfo', 'ConsumeInfo'):
            tags = tag('Connection', body=f'<{kind}>unexpected</{kind}>')
            result = capture(';', tags)[-1]
            self.assertEqual(result.tag_connections[0]['status'], 'unsupported_shape')
            self.assertEqual(result.tag_connections[0]['direct_text'], 'unexpected')
            self.assertEqual(result.status, 'partial')

    def test_control_rung_namespace_is_a_gap_even_with_canonical_lexical_binding(self):
        parts = capture()
        for source_name in ('Rung', 'Text'):
            xml = parts[0].data.decode('utf-8').replace(f'<{source_name}', f'<v:{source_name}').replace(f'</{source_name}>', f'</v:{source_name}>')
            xml = xml.replace('<RSLogix5000Content>', '<RSLogix5000Content xmlns:v="urn:vendor">')
            snapshot = snapshot_from_bytes(xml.encode('utf-8'))
            inventory = analyze_snapshot(snapshot)
            references = analyze_references(inventory)
            access = analyze_access(inventory, references)
            result = analyze_communication_context(snapshot, inventory, references, access, analyze_tag_data(snapshot, inventory))
            self.assertEqual(access.operands[0]['binding_status'], 'root_bound')
            self.assertEqual(result.occurrences[0]['status'], 'unsupported_context')
            self.assertEqual(result.occurrences[0]['parameter_ids'], [])

    def test_module_io_control_is_a_type_gap_and_nonowner_type_member_is_excluded(self):
        extra = ('<Modules><Module Name="M"><Communications><Connections><Connection Name="C">'
                 '<InputTag Name="M:I" DataType="MESSAGE"/></Connection></Connections></Communications></Module></Modules>'
                 '<DataTypes><DataType Name="Holder"><Members><Member Name="StoredMessage" DataType="MESSAGE"/>'
                 '</Members></DataType></DataTypes>')
        result = capture('MSG(M:I);', tags='', extra_body=extra)[-1]
        self.assertEqual(result.occurrences[0]['status'], 'control_type_unconfirmed')
        self.assertEqual(len(result.owners), 1)

    def test_multiple_controllers_and_other_programs_cannot_supply_local_candidates(self):
        tags = tag('Control', 'MESSAGE', message('LocalElement="OtherValue"'))
        extra = '<Controller Name="Other"><Tags>' + tag('OtherValue') + '</Tags></Controller>'
        result = capture(tags=tags, extra_programs=program(';', tag('OtherValue'), 'Q'), extra_controllers=extra)[-1]
        self.assertEqual(result.endpoints[0]['status'], 'binding_gap')
        self.assertIsNone(result.endpoints[0]['binding']['target_id'])

    def test_tampered_providers_are_rejected_before_derivation(self):
        parts = capture()
        for index, mutate in (
            (1, lambda p: p.entities[-1].attributes.update(Name='PrivateForgery')),
            (2, lambda p: p.symbols[0]['attributes'].update(DataType='PrivateForgery')),
            (3, lambda p: p.operands[0].update(target_id='PrivateForgery')),
            (4, lambda p: p.elements[0]['attributes'].update(LocalElement='PrivateForgery')),
        ):
            provided = list(deepcopy(parts[:-1])); mutate(provided[index])
            with patch('plc_workbench.communication_context._derive') as derive, self.assertRaises(CommunicationContextError) as raised:
                analyze_communication_context(*provided)
            derive.assert_not_called()
            self.assertNotIn('PrivateForgery', str(raised.exception))

    def test_tampered_result_reordered_records_and_foreign_snapshot_are_rejected(self):
        parts = capture('MSG(Control)MSG(Control);')
        mutations = (
            lambda r: r.occurrences.reverse(),
            lambda r: r.parameters[0]['attributes'].update(MessageType='PrivateForgery'),
            lambda r: r.endpoints[0]['binding'].update(target_id='PrivateForgery'),
            lambda r: r.owners[0]['content_ids'].clear(),
            lambda r: r.coverage.update(msg_occurrences=0),
        )
        for mutate in mutations:
            result = deepcopy(parts[-1]); mutate(result)
            with self.assertRaises(CommunicationContextError): validate_communication_context(*parts[:-1], result)
        with self.assertRaises(CommunicationContextError):
            validate_communication_context(*parts[:-1], replace(parts[-1], schema_version=True))
        with self.assertRaises(CommunicationContextError):
            validate_communication_context(*parts[:-1], capture('MSG(Control);')[-1])

    def test_private_renderer_plain_values_cycles_exact_limits_and_utf8(self):
        parts = capture(tags=tag('Control', 'MESSAGE', message('RemoteElement="caf&#233;"')))
        result = parts[-1]
        rendered = render_communication_context_json(result)
        self.assertEqual(json.loads(rendered), result.to_dict())
        self.assertEqual(len(rendered.encode('utf-8')), len(rendered))
        with patch('plc_workbench.communication_context.MAX_CONTEXT_BYTES', len(rendered)):
            self.assertEqual(render_communication_context_json(result), rendered)
        with patch('plc_workbench.communication_context.MAX_CONTEXT_BYTES', len(rendered) - 1), self.assertRaises(CommunicationContextError):
            render_communication_context_json(result)
        with patch('plc_workbench.communication_context.MAX_RECORDS', 0), self.assertRaises(CommunicationContextError):
            analyze_communication_context(*parts[:-1])
        class Hostile(list):
            def __iter__(self): raise AssertionError('Foreign hook invoked')
        cyclic = []; cyclic.append(cyclic)
        for bad in (Hostile(), cyclic, {'secret': object()}):
            with self.assertRaises(CommunicationContextError):
                render_communication_context_json(replace(result, endpoints=bad))

    def test_derivation_enforces_cumulative_rows_and_evidence_budget(self):
        parts = capture('MSG(Control)' * 10 + ';')
        with patch('plc_workbench.communication_context.MAX_RECORDS', 10), self.assertRaises(CommunicationContextError):
            analyze_communication_context(*parts[:-1])
        with patch('plc_workbench.communication_context.MAX_CONTEXT_BYTES', 100), self.assertRaises(CommunicationContextError):
            analyze_communication_context(*parts[:-1])
        with self.assertRaises(CommunicationContextError):
            analyze_communication_context(replace(parts[0], sha256='0' * 64), *parts[1:-1])

    def test_empty_and_unparsed_inputs_do_not_invent_msg_occurrences(self):
        for text in (';', 'MSG(Control', 'Unknown(Control);'):
            result = capture(text, tags='')[-1]
            self.assertEqual(result.occurrences, [])
            self.assertEqual(result.status, 'complete')


class CommunicationInterpretationTests(unittest.TestCase):
    def test_every_documented_message_type_uses_an_exact_catalogue_entry(self):
        families = (
            ('Block Transfer', 'block_transfer'), ('CIP Data Table', 'cip_data_table'),
            ('PLC2 Unprotected', 'plc2_unprotected'), ('PLC3 Typed', 'plc3_typed'),
            ('PLC3 Word Range', 'plc3_word_range'), ('PLC5 Typed', 'plc5_typed'),
            ('PLC5 Word Range', 'plc5_word_range'), ('SERCOS IDN', 'sercos_idn'), ('SLC Typed', 'slc_typed'),
        )
        catalogue = [(f'{name} {word}', family, direction) for name, family in families
                     for word, direction in (('Read', 'read'), ('Write', 'write'))]
        catalogue += [('CIP Generic', 'cip_generic', 'service_dependent'),
                      ('Unconfigured', 'unconfigured', 'unconfigured'),
                      ('Module Reconfigure', 'module_reconfigure', 'reconfigure')]
        tags = tag('LocalValue')
        for index, (name, _, _) in enumerate(catalogue):
            tags += tag(f'Control{index}', 'MESSAGE', message(
                f'MessageType="{name}" CommTypeCode="0" LocalElement="LocalValue" RemoteElement="RemoteSecret"'))
        parts = capture(''.join(f'MSG(Control{i})' for i in range(len(catalogue))) + ';', tags, schema_version=2)
        result = parts[-1]
        for row, (_, family, direction) in zip(result.parameters, catalogue):
            self.assertEqual(row['interpretation']['message_type_status'], 'catalogued')
            self.assertEqual(row['interpretation']['family'], family)
            self.assertEqual(row['interpretation']['direction'], direction)
        self.assertEqual(result.coverage['parameter_directions']['read'], 9)
        self.assertEqual(result.coverage['parameter_directions']['write'], 9)
        self.assertEqual(result.coverage['linked_parameter_records'], 21)
        validate_communication_context(*parts)

    def test_unknown_empty_missing_and_substring_types_never_gain_direction(self):
        values = (None, '', ' ', 'cip data table read', 'CIP Data Table Read ', 'Secret Read',
                  'CIP Generic Read', 'SLC, Typed WriteUnconfigured')
        for value in values:
            with self.subTest(value=value):
                attributes = 'LocalElement="LocalValue"' + ('' if value is None else f' MessageType="{value}"')
                result = capture(tags=tag('Control', 'MESSAGE', message(attributes)) + tag('LocalValue'), schema_version=2)[-1]
                item = result.parameters[0]['interpretation']
                expected = 'missing' if value is None else 'empty' if not value.strip() else 'unknown'
                self.assertEqual(item['message_type_status'], expected)
                self.assertEqual(item['family'], 'unknown')
                self.assertEqual(item['direction'], 'unknown')
                self.assertEqual(result.endpoints[0]['authored_role'], 'unclassified')
                self.assertEqual(result.occurrences[0]['authored_direction'], 'unknown')

    def test_communication_methods_distinguish_missing_invalid_and_unknown(self):
        cases = [(str(i), value) for i, value in enumerate(
            ('cip', 'dh_plus', 'cip_source_id', 'block_transfer_remote_io', 'block_transfer_controlnet'))]
        cases += [(None, 'missing'), ('', 'invalid'), ('0 ', 'invalid'), ('00', 'invalid'),
                  ('-1', 'invalid'), ('1.0', 'invalid'), ('0x0', 'invalid'), ('\u0661', 'invalid'),
                  ('PrivateCode', 'invalid'), ('5', 'unknown'), ('9' * 5000, 'unknown')]
        for value, expected in cases:
            with self.subTest(value=value[:30] if value else value):
                attributes = '' if value is None else f'CommTypeCode="{value}"'
                result = capture(tags=tag('Control', 'MESSAGE', message(attributes)), schema_version=2)[-1]
                self.assertEqual(result.parameters[0]['interpretation']['communication_method'], expected)

    def test_endpoint_authored_roles_are_separate_from_binding_and_runtime(self):
        for message_type, expected in (('CIP Data Table Read', 'local_destination'),
                                       ('CIP Data Table Write', 'local_source'),
                                       ('CIP Generic', 'service_dependent'),
                                       ('Module Reconfigure', 'unclassified'),
                                       ('Unconfigured', 'unconfigured')):
            result = capture(tags=tag('Control', 'MESSAGE', message(
                f'MessageType="{message_type}" LocalElement="Missing" DestinationTag="LocalValue"'))
                + tag('LocalValue'), schema_version=2)[-1]
            endpoints = {r['field']: r for r in result.endpoints}
            self.assertEqual(endpoints['LocalElement']['status'], 'binding_gap')
            self.assertEqual(endpoints['LocalElement']['authored_role'], expected)
            self.assertEqual(endpoints['DestinationTag']['authored_role'],
                             'unconfigured' if message_type == 'Unconfigured' else 'authored_destination')
            self.assertEqual(result.runtime_behavior, 'not_analyzed')
            self.assertEqual(result.remote_binding, 'not_performed')
            self.assertEqual(result.effective_configuration, 'not_selected')
        # The field's source meaning can be qualified even when its target
        # declaration has a foreign attribute. It is still no runtime role
        # or valid local endpoint: retain the independent binding disposition.
        qualified_field = capture(tags=tag('Control', 'MESSAGE', message(
            'MessageType="CIP Data Table Write" LocalElement="LocalValue"'))
            + tag('LocalValue', attributes='xmlns:x="urn:foreign" x:Meaning="other"'), schema_version=2)[-1]
        self.assertEqual(qualified_field.parameters[0]['status'], 'supported')
        self.assertEqual(qualified_field.endpoints[0]['status'], 'unsupported_context')
        self.assertEqual(qualified_field.endpoints[0]['authored_role'], 'local_source')

    def test_missing_empty_fields_are_distinct_without_inventing_transfer_requirements(self):
        result = capture(tags=tag('Control', 'MESSAGE', message(
            'MessageType="Block Transfer Read" LocalElement=" " DestinationTag="" ConnectionPath=""')),
            schema_version=2)[-1]
        shapes = result.parameters[0]['interpretation']['field_shapes']
        self.assertEqual(shapes, {'LocalElement': 'empty', 'DestinationTag': 'empty',
                                  'ConnectionPath': 'empty', 'RemoteElement': 'missing'})
        self.assertEqual([r['authored_role'] for r in result.endpoints], ['field_gap', 'field_gap'])
        self.assertEqual(result.coverage['endpoint_authored_roles']['field_gap'], 2)

    def test_generic_services_paths_and_remote_values_do_not_define_direction(self):
        for service in ('4C', '4D', '0E', '10', 'SecretService'):
            result = capture(tags=tag('Control', 'MESSAGE', message(
                f'MessageType="CIP Generic" ServiceCode="{service}" ConnectionPath="LocalValue" '
                'RemoteElement="LocalValue" LocalElement="LocalValue"')) + tag('LocalValue'), schema_version=2)[-1]
            self.assertEqual(result.parameters[0]['interpretation']['direction'], 'service_dependent')
            self.assertEqual(len(result.endpoints), 1)
            self.assertEqual(result.endpoints[0]['field'], 'LocalElement')

    def test_duplicates_are_individual_records_and_never_select_a_call_configuration(self):
        read = message('MessageType="CIP Data Table Read" LocalElement="LocalValue"')
        write = message('MessageType="CIP Data Table Write" LocalElement="LocalValue"')
        parts = capture('MSG(Control)MSG(Control);', tag('Control', 'MESSAGE', read + write)
                        + tag('Uncalled', 'MESSAGE', read) + tag('LocalValue'), schema_version=2)
        result = parts[-1]
        self.assertEqual(result.coverage['parameter_directions']['read'], 2)
        self.assertEqual(result.coverage['parameter_directions']['write'], 1)
        self.assertEqual(result.coverage['occurrence_directions']['unavailable'], 2)
        self.assertEqual(result.coverage['owners_total'], 2)
        self.assertEqual(result.coverage['owners_referenced_by_occurrences'], 1)
        self.assertEqual(result.coverage['parameter_records_referenced_by_occurrences'], 2)
        self.assertEqual(result.coverage['linked_parameter_records'], 0)
        self.assertEqual(result.effective_configuration, 'not_selected')
        validate_communication_context(*parts)

    def test_repeated_calls_count_one_linked_owner_and_one_parameter_record(self):
        parts = capture('MSG(Control)MSG(Control);', tag('Control', 'MESSAGE', message(
            'MessageType="SLC Typed Write"')) + tag('Uncalled', 'MESSAGE', message()), schema_version=2)
        c = parts[-1].coverage
        self.assertEqual(c['msg_occurrences'], 2)
        self.assertEqual(c['parameter_records'], 2)
        self.assertEqual(c['occurrence_directions']['write'], 2)
        for key in ('owners_referenced_by_occurrences', 'parameter_records_referenced_by_occurrences',
                    'owners_with_linked_occurrences', 'linked_parameter_records'):
            self.assertEqual(c[key], 1)
        validate_communication_context(*parts)

    def test_unsupported_namespace_envelope_and_owner_never_get_interpretations(self):
        attrs = 'MessageType="CIP Data Table Read" CommTypeCode="0" LocalElement="LocalValue"'
        fixtures = (
            tag('Control', 'MESSAGE', message(attrs, '<Foreign/>')),
            tag('Control', 'DINT', message(attrs)),
            tag('Control', 'MESSAGE', message(attrs + ' x:Extra="1"')),
            tag('Control', 'MESSAGE', f'<DefaultData Format="Message"><MessageParameters {attrs}/></DefaultData>'),
        )
        for tags in fixtures:
            with self.subTest(tags=tags):
                parts = capture(tags=tags + tag('LocalValue'), namespace=' xmlns:x="urn:foreign"', schema_version=2)
                item = parts[-1].parameters[0]['interpretation']
                self.assertEqual({item[k] for k in ('message_type_status', 'family', 'direction', 'communication_method')},
                                 {'unsupported_context'})
                self.assertEqual(set(item['field_shapes'].values()), {'unsupported_context'})
                self.assertEqual(parts[-1].endpoints[0]['authored_role'], 'unsupported_context')
                self.assertEqual(parts[-1].occurrences[0]['authored_direction'], 'unavailable')
                validate_communication_context(*parts)
        supported = capture(tags=tag('Control', 'MESSAGE', message(attrs)) + tag('LocalValue'),
                            namespace=' xmlns="urn:root"', schema_version=2)[-1]
        self.assertEqual(supported.parameters[0]['interpretation']['direction'], 'read')

    def test_versioned_replay_rejects_forged_interpretations_and_invalid_versions(self):
        parts = capture(schema_version=2)
        mutations = (
            lambda r: r.parameters[0]['interpretation'].update(direction='read'),
            lambda r: r.endpoints[0].update(authored_role='local_source'),
            lambda r: r.occurrences[0].update(authored_direction='read'),
            lambda r: r.coverage.update(linked_parameter_records=0),
        )
        for mutate in mutations:
            result = deepcopy(parts[-1]); mutate(result)
            with self.assertRaises(CommunicationContextError): validate_communication_context(*parts[:-1], result)
        for version in (True, 0, 4, '2'):
            with self.assertRaises(CommunicationContextError):
                analyze_communication_context(*parts[:-1], schema_version=version)
        with self.assertRaises(CommunicationContextError):
            validate_communication_context(*parts[:-1], replace(parts[-1], schema_version=1))

    def test_schema2_resource_limits_include_interpretations(self):
        parts = capture('MSG(Control)' * 10 + ';', schema_version=2)
        rendered = render_communication_context_json(parts[-1])
        with patch('plc_workbench.communication_context.MAX_CONTEXT_BYTES', len(rendered)):
            self.assertEqual(render_communication_context_json(parts[-1]), rendered)
        with patch('plc_workbench.communication_context.MAX_CONTEXT_BYTES', len(rendered) - 1), self.assertRaises(CommunicationContextError):
            render_communication_context_json(parts[-1])
        with patch('plc_workbench.communication_context.MAX_RECORDS', 10), self.assertRaises(CommunicationContextError):
            analyze_communication_context(*parts[:-1], schema_version=2)
        with patch('plc_workbench.communication_context.MAX_CONTEXT_BYTES', 100), self.assertRaises(CommunicationContextError):
            analyze_communication_context(*parts[:-1], schema_version=2)

    def test_default_schema1_bytes_match_the_prior_released_fixture(self):
        # Captured from 31cc08b's renderer using this same invented fixture.
        parts = capture()
        rendered = render_communication_context_json(parts[-1])
        self.assertEqual(hashlib.sha256(rendered.encode()).hexdigest(),
                         '6b8e20d3948fda5494c8ec49bc7bdb2ca82a35cab2fff6a83f6673e4425c3cea')
        self.assertEqual(rendered, render_communication_context_json(
            analyze_communication_context(*parts[:-1], schema_version=1)))
        self.assertNotIn('interpretation', parts[-1].parameters[0])
        self.assertNotIn('authored_role', parts[-1].endpoints[0])


GENERIC_ATTRIBUTES = ('MessageType="CIP Generic" CommTypeCode="0" ServiceCode="16#0e" '
                      'ObjectType="16#F" TargetObject="39" AttributeNumber="16#1" '
                      'LocalElement="LocalValue" DestinationTag="LocalValue"')


def generic_message(**changes: str | None) -> str:
    attributes = {'MessageType': 'CIP Generic', 'CommTypeCode': '0', 'ServiceCode': '16#0e',
                  'ObjectType': '16#F', 'TargetObject': '39', 'AttributeNumber': '16#1',
                  'LocalElement': 'LocalValue', 'DestinationTag': 'LocalValue'}
    attributes.update(changes)
    return message(' '.join(f'{name}="{value}"' for name, value in attributes.items() if value is not None))


class GenericServiceInterpretationTests(unittest.TestCase):
    def test_documented_ids_and_unknown_ids_preserve_direction_and_endpoint_roles(self):
        cases = {'16#1': 'get_attributes_all', '16#000E': 'get_attribute_single',
                 '16#10': 'set_attribute_single', '16#0': 'unknown_service',
                 '16#5': 'unknown_service', '16#4b': 'unknown_service', '16#7fff': 'unknown_service'}
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                parts = capture(tags=tag('Control', 'MESSAGE', generic_message(ServiceCode=raw))
                                + tag('LocalValue'), schema_version=3)
                result = parts[-1]
                generic = result.parameters[0]['interpretation']['generic']
                self.assertEqual(generic['service'], expected)
                self.assertEqual(generic['selector_values']['ServiceCode'], int(raw[3:], 16))
                self.assertEqual(generic['completeness'], 'all_selectors_parsed')
                self.assertEqual(result.parameters[0]['interpretation']['direction'], 'service_dependent')
                self.assertEqual(result.occurrences[0]['authored_direction'], 'service_dependent')
                self.assertEqual(result.occurrences[0]['generic_service'], expected)
                self.assertEqual({row['field']: row['authored_role'] for row in result.endpoints},
                                 {'LocalElement': 'service_dependent', 'DestinationTag': 'authored_destination'})
                self.assertEqual(result.remote_binding, 'not_performed')
                self.assertEqual(result.runtime_behavior, 'not_analyzed')
                validate_communication_context(*parts)

    def test_each_hex_selector_requires_explicit_ascii_encoding_and_own_range(self):
        common = [(None, 'missing'), ('', 'empty'), (' ', 'empty'), ('14', 'unsupported_encoding'),
                  ('0x0e', 'unsupported_encoding'), ('#16e', 'unsupported_encoding'),
                  ('16#', 'unsupported_encoding'), ('16#0_E', 'unsupported_encoding'),
                  ('16#-1', 'unsupported_encoding'), ('16#e ', 'unsupported_encoding'),
                  (' 16#e', 'unsupported_encoding'), ('１６#e', 'unsupported_encoding'),
                  ('16#é', 'unsupported_encoding'), ('16#0', 'parsed'), ('16#000e', 'parsed')]
        for field in ('ServiceCode', 'ObjectType', 'AttributeNumber'):
            boundary = [('16#ffff', 'parsed'), ('16#10000', 'out_of_range')] if field == 'AttributeNumber' else [
                ('16#7fff', 'parsed'), ('16#8000', 'out_of_range')]
            for raw, expected in common + boundary:
                with self.subTest(field=field, raw=raw):
                    result = capture(tags=tag('Control', 'MESSAGE', generic_message(**{field: raw}))
                                     + tag('LocalValue'), schema_version=3)[-1]
                    generic = result.parameters[0]['interpretation']['generic']
                    self.assertEqual(generic['selector_statuses'][field], expected)
                    self.assertEqual(generic['selector_values'][field], int(raw[3:], 16) if expected == 'parsed' else None)
                    self.assertEqual(generic['completeness'], 'all_selectors_parsed' if expected == 'parsed' else 'selector_gaps')

    def test_target_object_requires_canonical_ascii_decimal_and_bounded_conversion(self):
        cases = [(None, 'missing'), ('', 'empty'), (' ', 'empty'), ('0', 'parsed'), ('32767', 'parsed'),
                 ('32768', 'out_of_range'), ('999999999', 'out_of_range'), ('01', 'unsupported_encoding'),
                 ('+1', 'unsupported_encoding'), ('-1', 'unsupported_encoding'), ('1.0', 'unsupported_encoding'),
                 ('1_0', 'unsupported_encoding'), (' 1', 'unsupported_encoding'), ('1 ', 'unsupported_encoding'),
                 ('١', 'unsupported_encoding'), ('16#1', 'unsupported_encoding')]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                result = capture(tags=tag('Control', 'MESSAGE', generic_message(TargetObject=raw))
                                 + tag('LocalValue'), schema_version=3)[-1]
                generic = result.parameters[0]['interpretation']['generic']
                self.assertEqual(generic['selector_statuses']['TargetObject'], expected)
                self.assertEqual(generic['selector_values']['TargetObject'], int(raw) if expected == 'parsed' else None)
        for field, raw, status, value in (('ServiceCode', '16#' + 'F' * 10000, 'out_of_range', None),
                                         ('ServiceCode', '16#' + '0' * 10000 + 'E', 'parsed', 14),
                                         ('TargetObject', '9' * 10000, 'out_of_range', None)):
            with self.subTest(field=field, length=len(raw)):
                result = capture(tags=tag('Control', 'MESSAGE', generic_message(**{field: raw}))
                                 + tag('LocalValue'), schema_version=3)[-1]
                generic = result.parameters[0]['interpretation']['generic']
                self.assertEqual((generic['selector_statuses'][field], generic['selector_values'][field]), (status, value))

    def test_source_qualification_and_exact_generic_type_precede_service_decoding(self):
        supported = generic_message()
        for body, attrs in ((supported.replace('<MessageParameters ', '<x:MessageParameters ').replace('</MessageParameters>', '</x:MessageParameters>'), ''),
                            (supported.replace('ServiceCode=', 'x:ServiceCode='), ''),
                            (supported.replace('</Data>', '<Other/></Data>'), ''),
                            (supported, ' Dimensions="2"')):
            with self.subTest(body=body, attrs=attrs):
                parts = capture(tags=tag('Control', 'MESSAGE', body, attrs) + tag('LocalValue'),
                                namespace=' xmlns:x="urn:foreign"', schema_version=3)
                generic = parts[-1].parameters[0]['interpretation']['generic']
                self.assertEqual(generic['service'], 'unsupported_context')
                self.assertEqual(set(generic['selector_statuses'].values()), {'unsupported_context'})
                self.assertEqual(set(generic['selector_values'].values()), {None})
                self.assertEqual(parts[-1].occurrences[0]['generic_service'], 'unavailable')
                validate_communication_context(*parts)
        for name in ('CIP Data Table Read', 'cip generic', 'CIP Generic ', None):
            with self.subTest(name=name):
                result = capture(tags=tag('Control', 'MESSAGE', generic_message(MessageType=name))
                                 + tag('LocalValue'), schema_version=3)[-1]
                generic = result.parameters[0]['interpretation']['generic']
                self.assertEqual(generic['service'], 'not_applicable')
                self.assertEqual(set(generic['selector_statuses'].values()), {'not_applicable'})
        result = capture(tags=tag('Control', 'MESSAGE', generic_message()) + tag('LocalValue'),
                         namespace=' xmlns="urn:root"', schema_version=3)[-1]
        self.assertEqual(result.parameters[0]['interpretation']['generic']['service'], 'get_attribute_single')

    def test_repeated_calls_uncalled_records_and_duplicate_configurations_stay_distinct(self):
        tags = (tag('Control', 'MESSAGE', generic_message())
                + tag('Uncalled', 'MESSAGE', generic_message(ServiceCode='16#10'))
                + tag('Ordinary', 'MESSAGE', generic_message(MessageType='CIP Data Table Read')) + tag('LocalValue'))
        parts = capture('MSG(Control)MSG(Control)MSG(Control)MSG(Ordinary);', tags, schema_version=3)
        c = parts[-1].coverage
        self.assertEqual(c['generic_parameter_services']['get_attribute_single'], 1)
        self.assertEqual(c['generic_parameter_services']['set_attribute_single'], 1)
        self.assertEqual(c['generic_linked_parameter_services']['get_attribute_single'], 1)
        self.assertEqual(c['generic_linked_parameter_services']['set_attribute_single'], 0)
        self.assertEqual(c['generic_linked_occurrence_services']['get_attribute_single'], 3)
        self.assertEqual(c['generic_linked_occurrence_services']['not_applicable'], 1)
        validate_communication_context(*parts)
        parts = capture('MSG(Control)MSG(Control);', tag('Control', 'MESSAGE',
                        generic_message() + generic_message(ServiceCode='16#10')) + tag('LocalValue'), schema_version=3)
        self.assertEqual([r['generic_service'] for r in parts[-1].occurrences], ['unavailable', 'unavailable'])
        self.assertEqual(sum(parts[-1].coverage['generic_linked_parameter_services'].values()), 0)
        self.assertEqual(parts[-1].coverage['generic_parameter_services']['get_attribute_single'], 1)
        self.assertEqual(parts[-1].coverage['generic_parameter_services']['set_attribute_single'], 1)
        validate_communication_context(*parts)

    def test_replay_rejects_forged_services_selectors_and_linked_counts(self):
        parts = capture(tags=tag('Control', 'MESSAGE', generic_message()) + tag('LocalValue'), schema_version=3)
        for mutate in (
                lambda r: r.parameters[0]['interpretation']['generic'].update(service='set_attribute_single'),
                lambda r: r.parameters[0]['interpretation']['generic']['selector_values'].update(ObjectType=31),
                lambda r: r.parameters[0]['interpretation']['generic']['selector_statuses'].update(TargetObject='missing'),
                lambda r: r.parameters[0]['interpretation']['generic'].update(completeness='selector_gaps'),
                lambda r: r.occurrences[0].update(generic_service='unknown_service'),
                lambda r: r.coverage['generic_linked_parameter_services'].update(get_attribute_single=0)):
            forged = deepcopy(parts[-1]); mutate(forged)
            with self.subTest(mutate=mutate), self.assertRaises(CommunicationContextError):
                validate_communication_context(*parts[:-1], forged)
        with self.assertRaises(CommunicationContextError):
            validate_communication_context(*parts[:-1], replace(parts[-1], schema_version=2,
                                                                analyzer_version='communication-context-2'))

    def test_schema3_budget_charges_interpretations_and_exact_final_bytes(self):
        parts = capture(tags=tag('Control', 'MESSAGE', generic_message()) + tag('LocalValue'), schema_version=3)
        rendered = render_communication_context_json(parts[-1])
        with patch('plc_workbench.communication_context.MAX_CONTEXT_BYTES', len(rendered)):
            self.assertEqual(render_communication_context_json(parts[-1]), rendered)
        with patch('plc_workbench.communication_context.MAX_CONTEXT_BYTES', len(rendered) - 1), self.assertRaises(CommunicationContextError):
            render_communication_context_json(parts[-1])
        for key, limit in (('MAX_CONTEXT_BYTES', 100), ('MAX_RECORDS', 1)):
            with self.subTest(key=key), patch('plc_workbench.communication_context.' + key, limit), self.assertRaises(CommunicationContextError):
                analyze_communication_context(*parts[:-1], schema_version=3)

    def test_schema2_bytes_and_vocabulary_remain_frozen(self):
        tags = tag('Control', 'MESSAGE', message(GENERIC_ATTRIBUTES)) + tag('LocalValue')
        parts = capture(tags=tags, schema_version=2)
        self.assertEqual(hashlib.sha256(render_communication_context_json(parts[-1]).encode()).hexdigest(),
                         '21c4b7ab96a668c11af17d075d1da97532ceb65e550b763fca8ce18884263ae0')
        self.assertNotIn('generic', parts[-1].parameters[0]['interpretation'])
        self.assertNotIn('generic_service', parts[-1].occurrences[0])
        validate_communication_context(*parts)
        current = capture(tags=tags, schema_version=3)[-1]
        self.assertEqual(current.coverage['occurrence_directions'], parts[-1].coverage['occurrence_directions'])
        self.assertEqual(current.coverage['endpoint_authored_roles'], parts[-1].coverage['endpoint_authored_roles'])


if __name__ == '__main__':
    unittest.main()
