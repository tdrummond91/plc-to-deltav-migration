"""Communication feedback contains fixed counts and no source-controlled values."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch

from plc_workbench.communication_context_summary import (
    CommunicationContextSummaryError, build_communication_context_summary,
    render_communication_context_summary, validate_communication_context_summary,
)
from test_communication_context import capture, message, tag


def summary(*args, **kwargs):
    return build_communication_context_summary(*capture(*args, **kwargs))


class CommunicationContextSummaryTests(unittest.TestCase):
    def test_fixed_source_free_summary_fits_budget_and_copies_revision(self):
        parts = capture()
        revision = {'commit': 'a' * 40, 'worktree': 'modified'}
        result = build_communication_context_summary(*parts, revision=revision)
        revision['commit'] = 'b' * 40
        self.assertEqual(result['tool_revision']['commit'], 'a' * 40)
        text = render_communication_context_summary(result)
        self.assertLessEqual(len(text.encode('utf-8')), 4096)
        self.assertEqual(json.loads(text), result)
        self.assertEqual(text, render_communication_context_summary(deepcopy(result)))
        for private in ('LocalValue', 'RemoteSecret', 'Control', 'snapshot', 'source_id',
                        'parameter_id', 'owner_id', 'sha256:', 'tag_data_element_', 'locator'):
            self.assertNotIn(private, text)
        scaled = deepcopy(result)
        for key, value in scaled['coverage'].items():
            if type(value) is dict:
                scaled['coverage'][key] = {k: n * 62_500 for k, n in value.items()}
            else:
                scaled['coverage'][key] *= 62_500
        self.assertLessEqual(len(render_communication_context_summary(scaled)), 4096)

    def test_missing_repeated_unsupported_and_source_metadata_counts_validate(self):
        fixtures = (
            (';', ''), ('MSG(Control);', tag('Control', 'MESSAGE')),
            ('MSG(Control)MSG(Control);', tag('Control', 'MESSAGE', message() + message())),
            ('MSG(Wrong);', tag('Wrong', body=message())),
            ('MSG(Control[Index]);', tag('Control', 'MESSAGE', message())),
            (';', tag('Produced', body='<ProduceInfo Consumers="4"/>')),
            ('MSG(Control);', tag('Control', 'MESSAGE', message('LocalElement="Program:P.Value"'))),
            ('MSG(Control);', tag('Control', 'MESSAGE', '<DefaultData Format="Message"><MessageParameters/></DefaultData>')),
        )
        for text, tags in fixtures:
            with self.subTest(text=text, tags=tags):
                validate_communication_context_summary(summary(text, tags))

    def test_closed_keys_constants_native_count_types_and_revision(self):
        base = summary()
        mutations = (
            lambda r: r.update(private='Secret'),
            lambda r: r.update(schema_version=True),
            lambda r: r.update(runtime_behavior='verified'),
            lambda r: r.update(remote_binding='verified'),
            lambda r: r['coverage'].update(private='Secret'),
            lambda r: r['coverage']['parameter_fields'].update(PrivateProtocol=1),
            lambda r: r['coverage'].update(msg_occurrences=True),
            lambda r: r['coverage'].update(msg_occurrences=1.0),
            lambda r: r['coverage'].update(msg_occurrences=-1),
            lambda r: r['coverage'].update(source_operands=250_001),
            lambda r: r.update(status='partial'),
            lambda r: r['tool_revision'].update(commit='PrivateRevision'),
        )
        for mutate in mutations:
            value = deepcopy(base); mutate(value)
            with self.assertRaises(CommunicationContextSummaryError): render_communication_context_summary(value)

    def test_count_conservation_and_presence_bounds_are_enforced(self):
        base = summary()
        mutations = (
            lambda c: c.update(msg_occurrences=0),
            lambda c: c.update(source_instructions=0),
            lambda c: c.update(source_rungs=0),
            lambda c: c.update(owners_total=0),
            lambda c: c.update(contents_total=0),
            lambda c: c.update(parameter_records=0),
            lambda c: c.update(endpoints_total=0),
            lambda c: c.update(owners_with_parameters=0),
            lambda c: c.update(owners_with_multiple_parameters=1),
            lambda c: c.update(owners_with_multiple_contents=1),
            lambda c: c['parameter_fields'].update(LocalElement=0),
            lambda c: c['parameter_fields'].update(RemoteElement=2),
            lambda c: c.update(tags_with_connections=1),
            lambda c: c['occurrences_by_status'].update(linked=0),
            lambda c: c['owners_by_status'].update(supported=0),
            lambda c: c['parameters_by_status'].update(supported=0),
            lambda c: c['endpoints_by_status'].update(root_candidate=0),
        )
        for mutate in mutations:
            value = deepcopy(base); mutate(value['coverage'])
            with self.assertRaises(CommunicationContextSummaryError): validate_communication_context_summary(value)

    def test_linked_and_repeated_occurrences_require_matching_owner_population(self):
        base = summary()
        for changes in ({'linked': 0, 'missing_parameters': 1},
                        {'linked': 0, 'multiple_representations': 1},
                        {'linked': 0, 'unsupported_parameters': 1}):
            value = deepcopy(base)
            value['coverage']['occurrences_by_status'].update(changes)
            value['status'] = 'partial'
            with self.assertRaises(CommunicationContextSummaryError): validate_communication_context_summary(value)
        value = deepcopy(base)
        value['coverage']['parameters_by_status'].update(supported=0, type_gap=1)
        value['status'] = 'partial'
        with self.assertRaises(CommunicationContextSummaryError): validate_communication_context_summary(value)

    def test_metadata_counts_need_actual_connection_population(self):
        value = summary(';', tag('Produced', body='<ProduceInfo Consumers="4"/>'))
        value['coverage']['tag_connections_by_kind']['ProduceInfo'] = 0
        with self.assertRaises(CommunicationContextSummaryError): validate_communication_context_summary(value)
        value = summary(';', tag('Produced', body='<ProduceInfo Consumers="4"/>'))
        value['coverage']['tags_with_connections'] = 0
        with self.assertRaises(CommunicationContextSummaryError): validate_communication_context_summary(value)

    def test_canonical_replay_rejects_forgery_before_publication(self):
        parts = capture()
        bad = deepcopy(parts[-1]); bad.parameters[0]['attributes']['RemoteElement'] = 'PrivateForgery'
        with self.assertRaises(CommunicationContextSummaryError) as raised:
            build_communication_context_summary(*parts[:-1], bad)
        self.assertNotIn('PrivateForgery', str(raised.exception))
        with self.assertRaises(CommunicationContextSummaryError):
            build_communication_context_summary(*parts[:-1], replace(parts[-1], schema_version=True))

    def test_exact_summary_byte_limit(self):
        value = summary()
        text = render_communication_context_summary(value)
        with patch('plc_workbench.communication_context_summary.MAX_REPORT_BYTES', len(text)):
            self.assertEqual(render_communication_context_summary(value), text)
        with patch('plc_workbench.communication_context_summary.MAX_REPORT_BYTES', len(text) - 1), self.assertRaises(CommunicationContextSummaryError):
            render_communication_context_summary(value)


class CommunicationInterpretationSummaryTests(unittest.TestCase):
    def test_schema2_is_closed_source_free_and_counts_authoring_not_runtime(self):
        value = summary(tags=tag('Control', 'MESSAGE', message(
            'MessageType="Private Read" CommTypeCode="SecretCode" ServiceCode="PrivateService" '
            'LocalElement="LocalValue" RemoteElement="RemoteSecret" ConnectionPath="PrivatePath"'))
            + tag('LocalValue'), schema_version=2)
        rendered = render_communication_context_summary(value)
        self.assertEqual(value['schema_version'], 2)
        self.assertEqual(value['protocol_decoding'], 'authored_catalogue_only')
        self.assertEqual(value['coverage']['message_type_statuses']['unknown'], 1)
        self.assertEqual(value['coverage']['communication_methods']['invalid'], 1)
        self.assertEqual(value['status'], 'complete')  # Complete source capture, not complete semantics.
        for private in ('Private Read', 'SecretCode', 'PrivateService', 'LocalValue', 'RemoteSecret', 'PrivatePath'):
            self.assertNotIn(private, rendered)
        self.assertLessEqual(len(rendered), 8192)
        self.assertEqual(json.loads(rendered), value)

    def test_schema2_interpretation_partitions_and_presence_bounds_are_enforced(self):
        base = summary(tags=tag('Control', 'MESSAGE', message(
            'MessageType="CIP Data Table Read" CommTypeCode="0" LocalElement="LocalValue"'))
            + tag('LocalValue'), schema_version=2)
        mutations = (
            lambda c: c['message_type_statuses'].update(catalogued=0),
            lambda c: c['message_families'].update(cip_data_table=0, unknown=1),
            lambda c: c['parameter_directions'].update(read=0, service_dependent=1),
            lambda c: c['communication_methods'].update(cip=0, unsupported_context=1),
            lambda c: c['local_element_shapes'].update(present=0, missing=1),
            lambda c: c['remote_element_shapes'].update(missing=0, present=1),
            lambda c: c['endpoint_authored_roles'].update(local_destination=0, local_source=1),
            lambda c: c['occurrence_directions'].update(read=0, unavailable=1),
            lambda c: c['occurrence_directions'].update(read=0, write=1),
            lambda c: c.update(owners_referenced_by_occurrences=0),
            lambda c: c.update(parameter_records_referenced_by_occurrences=0),
            lambda c: c.update(owners_with_linked_occurrences=0),
            lambda c: c.update(linked_parameter_records=0),
            lambda c: c['message_families'].update(PrivateFamily=1),
            lambda c: c['communication_methods'].update(cip=True),
        )
        for mutate in mutations:
            value = deepcopy(base); mutate(value['coverage'])
            with self.assertRaises(CommunicationContextSummaryError): validate_communication_context_summary(value)

    def test_duplicate_and_uncalled_records_preserve_different_population_denominators(self):
        read = message('MessageType="CIP Data Table Read" LocalElement="LocalValue"')
        generic = message('MessageType="CIP Generic" DestinationTag="LocalValue"')
        fixtures = (
            ('MSG(Control)MSG(Control);', tag('Control', 'MESSAGE', read) + tag('Uncalled', 'MESSAGE', generic)),
            ('MSG(Control)MSG(Control);', tag('Control', 'MESSAGE', read + generic)),
            ('MSG(Control);', tag('Control', 'MESSAGE', message('MessageType="Unconfigured" LocalElement=""'))),
            ('MSG(Control);', tag('Control', 'MESSAGE', message('MessageType="CIP Generic" x:Attr="1"'))),
            ('MSG(Control);', tag('Control', 'DINT', generic)),
            (';', ''),
        )
        for text, tags in fixtures:
            with self.subTest(tags=tags):
                value = summary(text, tags + tag('LocalValue'), namespace=' xmlns:x="urn:foreign"', schema_version=2)
                validate_communication_context_summary(value)
                render_communication_context_summary(value)

    def test_authored_roles_cannot_move_into_incompatible_direction_populations(self):
        cases = (
            ('CIP Data Table Write', 'local_source'),
            ('CIP Data Table Read', 'local_destination'),
            ('CIP Generic', 'service_dependent'),
        )
        for message_type, role in cases:
            base = summary(tags=tag('Control', 'MESSAGE', message(
                f'MessageType="{message_type}" LocalElement="LocalValue"')) + tag('LocalValue'), schema_version=2)
            forged = deepcopy(base)
            forged['coverage']['endpoint_authored_roles'].update({role: 0, 'unclassified': 1})
            with self.subTest(message_type=message_type), self.assertRaises(CommunicationContextSummaryError):
                validate_communication_context_summary(forged)
        # A single unconfigured record cannot supply two local fields, although
        # it can legitimately supply one local and one destination field.
        value = summary('MSG(Control);', tag('Control', 'MESSAGE', message(
            'MessageType="CIP Data Table Write" LocalElement="LocalValue"') + message(
            'MessageType="Unconfigured" LocalElement="LocalValue"')) + tag('LocalValue'), schema_version=2)
        value['coverage']['endpoint_authored_roles'].update(local_source=0, unconfigured=2)
        with self.assertRaises(CommunicationContextSummaryError): validate_communication_context_summary(value)
        value = summary('MSG(Control);', tag('Control', 'MESSAGE', message(
            'MessageType="CIP Data Table Write" DestinationTag="LocalValue"') + message(
            'MessageType="Unconfigured" DestinationTag="LocalValue"')) + tag('LocalValue'), schema_version=2)
        value['coverage']['endpoint_authored_roles'].update(authored_destination=2, unconfigured=0)
        with self.assertRaises(CommunicationContextSummaryError): validate_communication_context_summary(value)

    def test_message_type_presence_reconciles_supported_and_unsupported_records(self):
        base = summary(tags=tag('Control', 'MESSAGE', message(
            'MessageType="CIP Data Table Write" LocalElement="LocalValue"')) + tag('LocalValue'), schema_version=2)
        forged = deepcopy(base)
        c = forged['coverage']
        c['message_type_statuses'].update(catalogued=0, missing=1)
        c['message_families'].update(cip_data_table=0, unknown=1)
        c['parameter_directions'].update(write=0, unknown=1)
        c['occurrence_directions'].update(write=0, unknown=1)
        c['endpoint_authored_roles'].update(local_source=0, unclassified=1)
        with self.assertRaises(CommunicationContextSummaryError): validate_communication_context_summary(forged)
        forged = deepcopy(base)
        forged['coverage']['parameter_fields']['MessageType'] = 0
        with self.assertRaises(CommunicationContextSummaryError): validate_communication_context_summary(forged)
        # An unsupported record may carry a raw MessageType while a separate
        # supported record lacks it. No interpretation is assigned to that raw
        # field, and counts must not force a correlation across these records.
        mixed = summary(tags=tag('Control', 'MESSAGE', message('LocalElement="LocalValue"'))
                        + tag('Unsupported', 'DINT', message('MessageType="CIP Data Table Write"'))
                        + tag('LocalValue'), schema_version=2)
        self.assertEqual(mixed['coverage']['message_type_statuses']['missing'], 1)
        self.assertEqual(mixed['coverage']['parameter_fields']['MessageType'], 1)
        validate_communication_context_summary(mixed)

    def test_all_present_blank_missing_role_shapes_accept_independent_duplicate_records(self):
        types = ('CIP Data Table Read', 'CIP Data Table Write', 'CIP Generic',
                 'Unconfigured', 'Module Reconfigure', 'Unknown Type')
        for message_type in types:
            for local in (None, '', 'LocalValue'):
                for destination in (None, '', 'LocalValue'):
                    fields = f'MessageType="{message_type}"'
                    fields += ''.join(f' {field}="{value}"' for field, value in
                                      (('LocalElement', local), ('DestinationTag', destination)) if value is not None)
                    tags = tag('Control', 'MESSAGE', message(fields) + message(
                        'MessageType="Unconfigured" LocalElement="LocalValue" DestinationTag="LocalValue"'))
                    value = summary('MSG(Control)MSG(Control);', tags + tag('LocalValue'), schema_version=2)
                    with self.subTest(message_type=message_type, local=local, destination=destination):
                        validate_communication_context_summary(value)
                        self.assertEqual(value['coverage']['occurrence_directions']['unavailable'], 2)

    def test_all_documented_families_render_with_shape_and_role_dispositions(self):
        names = ['Block Transfer', 'CIP Data Table', 'PLC2 Unprotected', 'PLC3 Typed', 'PLC3 Word Range',
                 'PLC5 Typed', 'PLC5 Word Range', 'SERCOS IDN', 'SLC Typed']
        for kind in [f'{name} {direction}' for name in names for direction in ('Read', 'Write')] + [
                'CIP Generic', 'Unconfigured', 'Module Reconfigure']:
            value = summary(tags=tag('Control', 'MESSAGE', message(
                f'MessageType="{kind}" LocalElement="LocalValue" DestinationTag="LocalValue"'))
                + tag('LocalValue'), schema_version=2)
            validate_communication_context_summary(value)

    def test_summary2_budget_supports_maximum_width_without_weakening_summary1_cap(self):
        value = summary(schema_version=2)
        scaled = deepcopy(value)
        for key, count in scaled['coverage'].items():
            scaled['coverage'][key] = {k: n * 62_500 for k, n in count.items()} if type(count) is dict else count * 62_500
        self.assertLessEqual(len(render_communication_context_summary(scaled)), 8192)
        # Every allowed count is at most 250000, so this bounds serialized
        # field widths even though simultaneous maxima need not be feasible.
        maximum_width = deepcopy(value)
        for key, count in maximum_width['coverage'].items():
            maximum_width['coverage'][key] = {k: 250_000 for k in count} if type(count) is dict else 250_000
        maximum_width['tool_revision'] = {'commit': 'f' * 40, 'worktree': 'unavailable'}
        self.assertLessEqual(len(json.dumps(maximum_width, sort_keys=True, indent=2, ensure_ascii=True) + '\n'), 8192)
        rendered = render_communication_context_summary(value)
        with patch('plc_workbench.communication_context_summary.MAX_REPORT_V2_BYTES', len(rendered)):
            self.assertEqual(render_communication_context_summary(value), rendered)
        with patch('plc_workbench.communication_context_summary.MAX_REPORT_V2_BYTES', len(rendered) - 1), self.assertRaises(CommunicationContextSummaryError):
            render_communication_context_summary(value)
        legacy = summary()
        with patch('plc_workbench.communication_context_summary.MAX_REPORT_BYTES', 1), self.assertRaises(CommunicationContextSummaryError):
            render_communication_context_summary(legacy)

    def test_schema2_publication_replays_interpretations_and_preserves_schema1_bytes(self):
        parts = capture(schema_version=2)
        bad = deepcopy(parts[-1]); bad.parameters[0]['interpretation']['family'] = 'cip_data_table'
        with self.assertRaises(CommunicationContextSummaryError):
            build_communication_context_summary(*parts[:-1], bad)
        legacy = render_communication_context_summary(summary())
        self.assertEqual(hashlib.sha256(legacy.encode()).hexdigest(),
                         '5e05ecb9731565cd450edd6cd56d0ccd03deed06e366473793bb9e59c7689d6b')


class GenericServiceSummaryTests(unittest.TestCase):
    @staticmethod
    def _summary(**changes):
        from test_communication_context import generic_message
        return summary(tags=tag('Control', 'MESSAGE', generic_message(**changes)) + tag('LocalValue'), schema_version=3)

    def test_public_service_counts_omit_raw_and_decoded_private_selectors(self):
        value = self._summary(ServiceCode='16#4B', ObjectType='16#2A55', TargetObject='31415', AttributeNumber='16#BEEF')
        rendered = render_communication_context_summary(value)
        for private in ('16#4B', '16#2A55', '31415', '16#BEEF', '10837', '48879', 'LocalValue'):
            self.assertNotIn(private, rendered)
        self.assertEqual(value['coverage']['generic_parameter_services']['unknown_service'], 1)
        self.assertEqual(value['coverage']['generic_linked_parameter_services']['unknown_service'], 1)
        self.assertEqual(value['coverage']['generic_linked_occurrence_services']['unknown_service'], 1)
        self.assertEqual(value['coverage']['generic_parameter_completeness']['all_selectors_parsed'], 1)
        self.assertEqual(value['coverage']['parameter_directions']['service_dependent'], 1)
        self.assertEqual(value['status'], 'complete')

    def test_selector_service_completeness_and_distinct_link_conservation_reject_forgery(self):
        original = self._summary()
        changes = (
            lambda c: c['generic_parameter_services'].update(get_attribute_single=0, missing=1),
            lambda c: c['generic_service_code_statuses'].update(parsed=0, missing=1),
            lambda c: c['generic_object_type_statuses'].update(parsed=0, not_applicable=1),
            lambda c: c['generic_attribute_number_statuses'].update(parsed=0, unsupported_context=1),
            lambda c: c['generic_parameter_completeness'].update(all_selectors_parsed=0, selector_gaps=1),
            lambda c: c['generic_linked_parameter_services'].update(get_attribute_single=0),
            lambda c: c['generic_linked_parameter_services'].update(get_attribute_single=2),
            lambda c: c['generic_linked_occurrence_services'].update(get_attribute_single=0, not_applicable=1),
            lambda c: c['generic_linked_occurrence_services'].update(get_attribute_single=0, unavailable=1),
            lambda c: c['generic_linked_occurrence_services'].update(get_attribute_single=0, set_attribute_single=1),
        )
        for mutate in changes:
            forged = deepcopy(original); mutate(forged['coverage'])
            with self.subTest(mutate=mutate), self.assertRaises(CommunicationContextSummaryError):
                validate_communication_context_summary(forged)
        for key, bad in (('schema_version', True), ('schema_version', 2), ('schema_version', 4),
                         ('analyzer_version', 'communication-context-2'),
                         ('exporter_version', 'communication-context-summary-2')):
            forged = deepcopy(original); forged[key] = bad
            with self.subTest(key=key, value=bad), self.assertRaises(CommunicationContextSummaryError):
                validate_communication_context_summary(forged)

    def test_repeated_calls_uncalled_records_and_duplicates_have_feasible_marginals(self):
        from test_communication_context import generic_message
        tags = (tag('Control', 'MESSAGE', generic_message())
                + tag('Uncalled', 'MESSAGE', generic_message(ServiceCode='16#10', AttributeNumber=None))
                + tag('Ordinary', 'MESSAGE', generic_message(MessageType='CIP Data Table Read')) + tag('LocalValue'))
        value = summary('MSG(Control)MSG(Control)MSG(Ordinary);', tags, schema_version=3)
        self.assertEqual(value['coverage']['generic_parameter_services']['set_attribute_single'], 1)
        self.assertEqual(value['coverage']['generic_linked_parameter_services']['set_attribute_single'], 0)
        self.assertEqual(value['coverage']['generic_linked_occurrence_services']['get_attribute_single'], 2)
        validate_communication_context_summary(value)
        forged = deepcopy(value)
        forged['coverage']['generic_linked_parameter_services']['get_attribute_single'] = 2
        with self.assertRaises(CommunicationContextSummaryError):
            validate_communication_context_summary(forged)
        # Two generic records can split their selector gaps, so no complete
        # record is required merely because every field has a parsed member.
        split = summary('MSG(Control);', tag('Control', 'MESSAGE',
            generic_message(ObjectType=None) + generic_message(TargetObject=None)) + tag('LocalValue'), schema_version=3)
        self.assertEqual(split['coverage']['generic_parameter_completeness']['all_selectors_parsed'], 0)
        self.assertEqual(split['coverage']['generic_linked_occurrence_services']['unavailable'], 1)
        validate_communication_context_summary(split)
        forged = deepcopy(split)
        forged['coverage']['generic_parameter_completeness'].update(all_selectors_parsed=2, selector_gaps=0)
        with self.assertRaises(CommunicationContextSummaryError):
            validate_communication_context_summary(forged)

    def test_absent_invalid_unknown_and_unsupported_contexts_stay_valid_closed_populations(self):
        from test_communication_context import generic_message
        for fields in ({'ServiceCode': None}, {'ServiceCode': ''}, {'ServiceCode': '0x0E'},
                       {'ServiceCode': '16#8000'}, {'ServiceCode': '16#5'}, {'ObjectType': None},
                       {'MessageType': 'Unconfigured'}, {'MessageType': None}):
            with self.subTest(fields=fields):
                value = self._summary(**fields)
                validate_communication_context_summary(value)
                self.assertEqual(value['status'], 'complete')
        value = summary(tags=tag('Control', 'MESSAGE', generic_message().replace('ServiceCode=', 'x:ServiceCode='))
                        + tag('LocalValue'), namespace=' xmlns:x="urn:foreign"', schema_version=3)
        self.assertEqual(value['coverage']['generic_parameter_services']['unsupported_context'], 1)
        self.assertEqual(value['coverage']['generic_linked_occurrence_services']['unavailable'], 1)
        validate_communication_context_summary(value)
        empty = summary(';', '', schema_version=3)
        self.assertEqual(sum(empty['coverage']['generic_parameter_services'].values()), 0)
        validate_communication_context_summary(empty)

    def test_summary3_width_and_exact_limits_preserve_both_historical_caps(self):
        value = self._summary()
        maximum = deepcopy(value)
        for key, count in maximum['coverage'].items():
            maximum['coverage'][key] = {k: 250_000 for k in count} if type(count) is dict else 250_000
        maximum['tool_revision'] = {'commit': 'f' * 40, 'worktree': 'unavailable'}
        width = len(json.dumps(maximum, sort_keys=True, indent=2, ensure_ascii=True) + '\n')
        self.assertLessEqual(width, 8192)
        rendered = render_communication_context_summary(value)
        with patch('plc_workbench.communication_context_summary.MAX_REPORT_V3_BYTES', len(rendered)):
            self.assertEqual(render_communication_context_summary(value), rendered)
        with patch('plc_workbench.communication_context_summary.MAX_REPORT_V3_BYTES', len(rendered) - 1), self.assertRaises(CommunicationContextSummaryError):
            render_communication_context_summary(value)
        for version, constant in ((1, 'MAX_REPORT_BYTES'), (2, 'MAX_REPORT_V2_BYTES')):
            historical = summary(schema_version=version)
            with self.subTest(version=version), patch('plc_workbench.communication_context_summary.' + constant, 1):
                with self.assertRaises(CommunicationContextSummaryError):
                    render_communication_context_summary(historical)
                self.assertEqual(render_communication_context_summary(value), rendered)

    def test_schema2_bytes_and_schema3_source_replay_are_preserved(self):
        from test_communication_context import GENERIC_ATTRIBUTES, generic_message
        tags = tag('Control', 'MESSAGE', message(GENERIC_ATTRIBUTES)) + tag('LocalValue')
        historical = render_communication_context_summary(summary(tags=tags, schema_version=2))
        self.assertEqual(hashlib.sha256(historical.encode()).hexdigest(),
                         'a1e1b67f822608aa1658bffb7747e5eee8b4684609618732f01506ee2ffd2bff')
        parts = capture(tags=tag('Control', 'MESSAGE', generic_message()) + tag('LocalValue'), schema_version=3)
        forged = deepcopy(parts[-1])
        forged.parameters[0]['interpretation']['generic']['selector_values']['TargetObject'] = 7
        with self.assertRaises(CommunicationContextSummaryError):
            build_communication_context_summary(*parts[:-1], forged)


if __name__ == '__main__':
    unittest.main()
