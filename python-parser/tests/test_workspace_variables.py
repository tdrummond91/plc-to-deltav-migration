"""Invented variable provenance, captured representations, and possible writers."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import json
import unittest
from unittest.mock import patch

from plc_workbench.tag_data import analyze_tag_data
from plc_workbench.workspace_variables import VariableError, VariableIndex, MAX_VALUES, MAX_WRITERS
from test_workspace_connections import multi_routine, routine


def decorated(preset: str = '2500', accumulator: str = '42', datatype: str = 'TIMER', envelope: str = 'Data') -> str:
    return (f'<{envelope} Format="Decorated"><Structure DataType="{datatype}">'
            f'<DataValueMember Name="PRE" DataType="DINT" Value="{preset}"/>'
            f'<DataValueMember Name="ACC" DataType="DINT" Value="{accumulator}"/>'
            f'</Structure></{envelope}>')


def tag(name: str = 'T', data: str | None = None, datatype: str = 'TIMER', extra: str = '') -> str:
    return (f'<Tag Name="{name}" TagType="Base" DataType="{datatype}" {extra}>'
            '<Description>Invented control description</Description>'
            + (decorated(datatype=datatype) if data is None else data) + '</Tag>')


def program(name: str, texts: tuple[str, ...], local: str = '') -> str:
    rungs = ''.join(f'<Rung Number="{i}" Type="N"><Text><![CDATA[{text}]]></Text></Rung>'
                    for i, text in enumerate(texts))
    return (f'<Program Name="{name}"><Tags>{local}</Tags><Routines><Routine Name="R" Type="RLL">'
            f'<RLLContent>{rungs}</RLLContent></Routine></Routines></Program>')


def inputs(texts: tuple[str, ...] = ('TON(T,?,?);',), declarations: str | None = None, programs: str | None = None):
    return multi_routine(programs if programs is not None else program('P', texts),
                         tag() if declarations is None else declarations)


def wire(captured) -> list:
    snapshot, inventory, references, access, calculations, _, _ = captured
    data = analyze_tag_data(snapshot, inventory)
    return [snapshot.data, *[json.loads(json.dumps(asdict(value)))
            for value in (inventory, references, access, data, calculations)]]


def inspect(captured, variable: str, rung: int = 0, instruction: int = 0) -> dict:
    return VariableIndex(*wire(captured)).view(captured[1].rungs[rung].instructions[instruction].id, variable)


class WorkspaceVariableTests(unittest.TestCase):
    def test_invalid_companions_identify_the_failed_stage_without_source_text(self) -> None:
        original = wire(inputs())
        for position, stage in ((1, 'inventory'), (2, 'references'), (3, 'access'),
                                (4, 'tag_data'), (5, 'calculations')):
            modified = deepcopy(original)
            modified[position]['analyzer_version' if position != 1 else 'parser_version'] = 'PRIVATE_SOURCE'
            with self.subTest(stage=stage), self.assertRaises(VariableError) as failure:
                VariableIndex(*modified)
            self.assertEqual(failure.exception.diagnostic['stage'], stage)
            self.assertNotIn('PRIVATE_SOURCE', str(failure.exception.diagnostic))

    def test_variable_capacity_is_measured_and_separate_from_invalid_evidence(self) -> None:
        captured = wire(inputs())
        with patch('plc_workbench.workspace_variables.MAX_INDEX_BYTES', 1), \
                self.assertRaises(VariableError) as failure:
            VariableIndex(*captured)
        detail = failure.exception.diagnostic
        self.assertEqual((detail['stage'], detail['reason'], detail['limit']),
                         ('variable_index', 'index_bytes_limit', 1))
        self.assertGreater(detail['actual'], detail['limit'])

    def test_timer_placeholders_resolve_saved_members_and_keep_other_formats(self) -> None:
        captured = inputs(('TON(T,?,?);', 'MOV(500,T.PRE);', 'RES(T);', 'CPT(T.PRE,400+100);', 'Custom(T);'),
                          tag(data='<Data Format="L5K">[0,2500,42]</Data>' + decorated()))
        view = inspect(captured, 'T.PRE')
        self.assertTrue(view['available'])
        self.assertEqual(view['display_value'], {'value': '2500', 'datatype': 'DINT', 'units': 'ms',
                                                 'envelope': 'Data', 'basis': 'Decorated Data export'})
        self.assertIn('target duration', view['member']['meaning'])
        self.assertIn('rockwellautomation.com', view['member']['reference'])
        self.assertEqual(view['declaration']['scope_kind'], 'controller')
        self.assertEqual(view['declaration']['description'], 'Invented control description')
        self.assertEqual([row['format'] for row in view['representations']], ['l5k', 'decorated'])
        self.assertEqual([(row['opcode'], row['role'], row['relation']) for row in view['writers']], [
            ('TON', 'read_write', 'whole_control'), ('MOV', 'write', 'exact_address'),
            ('RES', 'write', 'whole_control'), ('CPT', 'write', 'exact_address'),
            ('Custom', 'unknown', 'possible_overlap')])
        self.assertNotIn('rung_text', view['writers'][0])
        self.assertEqual(inspect(captured, 'T.ACC')['display_value']['value'], '42')

    def test_local_shadow_and_alias_declaration_scope_do_not_cross_programs(self) -> None:
        declarations = tag(data=decorated('100')) + ('<Tag Name="Alias" TagType="Alias" AliasFor="T.PRE" '
            'ExternalAccess="Read/Write"><Description>Invented alias description</Description></Tag>')
        programs = program('One', ('TON(T,?,?)MOV(1,T.PRE)MOV(Alias,T.ACC);',), tag(data=decorated('200')))
        programs += program('Two', ('MOV(2,T.PRE);',), tag(data=decorated('300')))
        captured = inputs(declarations=declarations, programs=programs)
        local = inspect(captured, 'T.PRE')
        alias = inspect(captured, 'Alias', instruction=2)
        self.assertEqual(local['display_value']['value'], '200')
        self.assertEqual(local['declaration']['scope_name'], 'One')
        self.assertFalse(any('Two' in row['path'] for row in local['writers']))
        self.assertEqual(alias['display_value']['value'], '100')
        self.assertEqual(alias['declaration']['scope_kind'], 'controller')
        self.assertEqual(alias['binding']['suffix'], '.PRE')
        self.assertEqual(len(alias['binding']['alias_chain']), 1)
        self.assertEqual(alias['source_declaration']['name'], 'Alias')
        self.assertEqual(alias['source_declaration']['alias_for'], 'T.PRE')
        self.assertEqual(alias['source_declaration']['description'], 'Invented alias description')
        self.assertEqual(alias['source_declaration']['external_access'], 'Read/Write')
        self.assertIsNone(local['source_declaration'])

    def test_duplicate_decorated_values_and_ancestors_withhold_display(self) -> None:
        for data in (decorated('100') + decorated('200'),
                     '<Data Format="Decorated"><Structure DataType="TIMER">'
                     '<DataValueMember Name="PRE" Value="100"/><DataValueMember Name="PRE" Value="100"/>'
                     '</Structure></Data>',
                     '<Data Format="Decorated"><Structure DataType="TIMER"><DataValueMember Name="PRE" Value="1"/>'
                     '</Structure><Structure DataType="TIMER"><DataValueMember Name="ACC" Value="2"/></Structure></Data>',
                     decorated().replace('</Data>', '<Unknown><DataValueMember Name="PRE" Value="9"/></Unknown></Data>')):
            with self.subTest(data=data):
                view = inspect(inputs(declarations=tag(data=data)), 'T.PRE')
                self.assertIsNone(view['display_value'])
                self.assertGreater(view['captured_values_total'], 0)
        view = inspect(inputs(declarations=tag(data=decorated('100') + decorated('200', envelope='DefaultData'))), 'T.PRE')
        self.assertEqual(view['display_value']['value'], '100')
        self.assertEqual({row['envelope'] for row in view['captured_values']}, {'Data', 'DefaultData'})

    def test_default_only_missing_and_opaque_data_supply_no_inline_value(self) -> None:
        for data in ('', '<Data Format="L5K">[0,25,0]</Data>', decorated(envelope='DefaultData')):
            with self.subTest(data=data):
                view = inspect(inputs(declarations=tag(data=data)), 'T.PRE')
                self.assertTrue(view['available'])
                self.assertIsNone(view['display_value'])

    def test_malformed_shapes_foreign_attributes_and_types_stay_unqualified(self) -> None:
        for data in ('<Data Format="Decorated"><Structure DataType="TIMER">text'
                     '<DataValueMember Name="PRE" Value="1"/></Structure></Data>',
                     '<Data Format="Decorated" xmlns:x="urn:private"><Structure DataType="TIMER">'
                     '<DataValueMember Name="PRE" x:Value="1"/></Structure></Data>',
                     decorated(datatype='COUNTER'),
                     decorated().replace('DataType="DINT"', 'DataType="BOOL"')):
            with self.subTest(data=data):
                view = inspect(inputs(declarations=tag(data=data)), 'T.PRE')
                self.assertIsNone(view['display_value'])
        foreign = '<Tag xmlns:x="urn:extension" Name="T" DataType="TIMER" x:flag="1">' + decorated() + '</Tag>'
        self.assertFalse(inspect(inputs(declarations=foreign), 'T.PRE')['available'])

    def test_counter_and_timer_t_units_are_distinguished(self) -> None:
        counter = inspect(inputs(('CTU(T,?,?);',), tag(datatype='COUNTER')), 'T.PRE')
        timer_t = inspect(inputs(declarations=tag(datatype='TIMER_T')), 'T.ACC')
        self.assertEqual(counter['member']['units'], 'counts')
        self.assertEqual(counter['display_value']['units'], 'counts')
        self.assertIsNone(timer_t['member']['units'])

    def test_member_case_variants_join_without_changing_index_spelling(self) -> None:
        captured = inputs(('MOV(t.pre,T.ACC);', 'MOV(5,T.PRE);', 'MOV(6,t.pre);'))
        view = inspect(captured, 't.pre')
        self.assertEqual(view['display_value']['value'], '2500')
        self.assertEqual(view['binding']['suffix'], '.pre')
        self.assertEqual(view['captured_values'][0]['path'], '.PRE')
        self.assertEqual([row['instruction_text'] for row in view['writers']], ['MOV(5,T.PRE)', 'MOV(6,t.pre)'])
        mixed = decorated().replace('</Structure>', '<DataValueMember Name="pre" DataType="DINT" Value="33"/></Structure>')
        ambiguous = inspect(inputs(declarations=tag(data=mixed)), 'T.PRE')
        self.assertIsNone(ambiguous['display_value'])
        self.assertEqual(ambiguous['captured_values_total'], 2)
        self.assertTrue(all(row['ambiguous'] for row in ambiguous['captured_values']))

    def test_generic_nested_udt_member_uses_saved_type_not_name_guess(self) -> None:
        data = ('<Data Format="Decorated"><Structure DataType="MyUDT"><StructureMember Name="Clock" DataType="TIMER">'
                '<DataValueMember Name="PRE" DataType="DINT" Value="999"/></StructureMember>'
                '<DataValueMember Name="PRE" DataType="REAL" Value="1.25"/></Structure></Data>')
        captured = inputs(('MOV(T.Clock.PRE,T.PRE);',), tag(datatype='MyUDT', data=data))
        nested = inspect(captured, 'T.Clock.PRE')
        unknown = inspect(captured, 'T.PRE')
        self.assertIn('target duration', nested['member']['meaning'])
        self.assertEqual(nested['member']['type_basis'], 'captured_decorated_structure')
        self.assertEqual(nested['display_value']['value'], '999')
        self.assertIsNone(unknown['member']['meaning'])
        self.assertIsNone(unknown['member']['units'])
        self.assertEqual(unknown['display_value']['value'], '1.25')

    def test_dynamic_index_has_root_only_and_possible_writer_evidence(self) -> None:
        data = ('<Data Format="Decorated"><Array DataType="DINT"><Element Index="[0]" Value="12"/>'
                '<Element Index="[00]" Value="15"/></Array></Data>')
        captured = inputs(('MOV(T[I],I);', 'MOV(5,T[I]);', 'MOV(T[0],I);'),
                          tag(data=data, datatype='DINT', extra='Dimensions="2"') + tag('I', data='', datatype='DINT'))
        dynamic = inspect(captured, 'T[I]')
        static = inspect(captured, 'T[0]', rung=2)
        self.assertEqual(dynamic['binding']['status'], 'unsupported_address')
        self.assertEqual(dynamic['binding']['basis'], 'root_only_dynamic_index')
        self.assertEqual(dynamic['captured_values'], [])
        self.assertEqual(static['display_value']['value'], '12')
        self.assertEqual(static['writers'][0]['relation'], 'possible_overlap')

    def test_scalar_array_elements_inherit_exact_immediate_type_and_radix(self) -> None:
        for data, variable, dtype, extra in (
            ('<Array DataType="SINT" Radix="Decimal" Dimensions="2"><Element Index="[1]" Value="-12"/></Array>',
             'T[1]', 'SINT', 'Dimensions="2"'),
            ('<Structure DataType="Packet"><ArrayMember Name="Bytes" DataType="SINT" Radix="Hex" Dimensions="2,3">'
             '<Element Index="[1,2]" Value="16#12"/></ArrayMember></Structure>', 'T.Bytes[1,2]', 'Packet', ''),
            ('<Array DataType="Packet" Dimensions="2"><Element Index="[0]"><Structure DataType="Packet">'
             '<ArrayMember Name="Bytes" DataType="SINT" Radix="Decimal" Dimensions="2">'
             '<Element Index="[1]" Value="12"/></ArrayMember></Structure></Element></Array>',
             'T[0].Bytes[1]', 'Packet', 'Dimensions="2"'),
        ):
            with self.subTest(variable=variable):
                captured = inputs((f'MOV({variable},Sink);',),
                    tag(data=f'<Data Format="Decorated">{data}</Data>', datatype=dtype, extra=extra))
                view = inspect(captured, variable)
                value = view['captured_values'][0]
                parent = next(row for row in analyze_tag_data(captured[0], captured[1]).elements
                              if row['id'] == value['datatype_source_id'])
                self.assertEqual((value['datatype'], value['datatype_basis']), ('SINT', 'immediate_array'))
                self.assertEqual(value['radix_source_id'], parent['id'])
                self.assertEqual(value['radix'], parent['attributes']['Radix'])
                self.assertIn(parent['xml_name'], {'Array', 'ArrayMember'})
                self.assertEqual(value['metadata_status'], 'qualified')
                self.assertIsNone(value['declared_datatype'])
                self.assertEqual(view['display_value']['datatype'], 'SINT')
                self.assertNotIn('DataType', next(row for row in analyze_tag_data(captured[0], captured[1]).elements
                                                if row['id'] == value['element_id'])['attributes'])

    def test_array_element_conflicts_are_explicit_and_withhold_single_value(self) -> None:
        for attrs in ('DataType="DINT"', 'Radix="Hex"', 'DataType="DINT" Radix="Hex"'):
            with self.subTest(attrs=attrs):
                data = ('<Data Format="Decorated"><Array DataType="SINT" Radix="Decimal">'
                        f'<Element Index="[0]" Value="12" {attrs}/></Array></Data>')
                view = inspect(inputs(('MOV(T[0],Sink);',), tag(data=data, datatype='SINT', extra='Dimensions="1"')), 'T[0]')
                value = view['captured_values'][0]
                self.assertIsNone(view['display_value'])
                self.assertEqual((value['metadata_status'], value['status']), ('conflict', 'metadata_conflict'))
                self.assertEqual(value['parent_datatype'], 'SINT')
                if 'DataType' in attrs:
                    self.assertIsNone(value['datatype'])
                    self.assertEqual(value['declared_datatype'], 'DINT')
                    self.assertEqual(value['datatype_basis'], 'conflict_with_array')
                if 'Radix' in attrs:
                    self.assertIsNone(value['radix'])
                    self.assertEqual(value['declared_radix'], 'Hex')

    def test_array_inheritance_does_not_cross_representations_or_unsupported_shape(self) -> None:
        def array(dtype: str, value: str, envelope: str = 'Data', extra: str = '') -> str:
            return (f'<{envelope} Format="Decorated"><Array DataType="{dtype}" Radix="Decimal" {extra}>'
                    f'<Element Index="[0]" Value="{value}"/></Array></{envelope}>')
        data = '<Data Format="L5K">[99]</Data>' + array('SINT', '12') + array('DINT', '42', 'DefaultData')
        view = inspect(inputs(('MOV(T[0],Sink);',), tag(data=data, datatype='SINT', extra='Dimensions="1"')), 'T[0]')
        self.assertEqual(view['display_value']['datatype'], 'SINT')
        self.assertEqual([(row['envelope'], row['datatype']) for row in view['captured_values']],
                         [('Data', 'SINT'), ('DefaultData', 'DINT')])
        for data in (array('SINT', '12') + array('SINT', '12'),
                     array('SINT', '12', extra='xmlns:x="urn:foreign" x:Flag="1"'),
                     array('SINT', '12').replace('<Array ', '<Array xmlns="urn:foreign" ')):
            with self.subTest(data=data):
                result = inspect(inputs(('MOV(T[0],Sink);',), tag(data=data, datatype='SINT', extra='Dimensions="1"')), 'T[0]')
                self.assertIsNone(result['display_value'])
                if 'foreign' in data:
                    self.assertIsNone(result['captured_values'][0]['datatype'])
                    self.assertIsNone(result['captured_values'][0]['array_source_id'])
        structured = ('<Data Format="Decorated"><Array DataType="Packet" Radix="Decimal">'
                      '<Element Index="[0]"><Structure DataType="Packet"><DataValueMember Name="Byte" DataType="SINT" '
                      'Value="12"/></Structure></Element></Array></Data>')
        result = inspect(inputs(('MOV(T[0],Sink);',), tag(data=structured, datatype='Packet', extra='Dimensions="1"')), 'T[0]')
        self.assertIsNone(result['captured_values'][0]['datatype'])
        self.assertIsNone(result['display_value'])

    def test_actual_cpt_leaves_and_unknown_instruction_arguments_are_eligible(self) -> None:
        captured = inputs(('CPT(T.PRE,T.ACC+4);', 'Custom(T.PRE);'))
        self.assertEqual(inspect(captured, 'T.ACC')['display_value']['value'], '42')
        self.assertEqual(inspect(captured, 'T.PRE', rung=1)['display_value']['value'], '2500')
        with self.assertRaises(VariableError):
            inspect(captured, 'T.DN')

    def test_derived_timer_members_require_valid_supported_signature(self) -> None:
        for text in ('TON(T,?,Other);', 'TON(T,?);', 'Custom(T,?,?);'):
            with self.subTest(text=text), self.assertRaises(VariableError):
                inspect(inputs((text,)), 'T.PRE')
        self.assertFalse(inspect(inputs(), '?')['available'])

    def test_canonical_replay_rejects_wrong_snapshot_and_forged_optional_evidence(self) -> None:
        valid = wire(inputs())
        for index, mutate in (
            (1, lambda value: value['entities'][-1]['attributes'].update(DataType='COUNTER')),
            (2, lambda value: value['operands'][0].update(target_id='foreign')),
            (3, lambda value: value['operands'][0].update(role='write')),
            (4, lambda value: value['elements'][1]['attributes'].update(Value='secret-forgery')),
            (4, lambda value: value['coverage'].update(contents_total=True)),
        ):
            forged = deepcopy(valid)
            mutate(forged[index])
            with self.subTest(index=index), self.assertRaisesRegex(VariableError, '^Saved variable evidence is inconsistent or exceeds its limits\\.$'):
                VariableIndex(*forged)
        forged = deepcopy(valid)
        forged[0] += b' '
        with self.assertRaises(VariableError):
            VariableIndex(*forged)

    def test_response_counts_and_string_previews_are_bounded_and_copied(self) -> None:
        captured = inputs(('TON(T,?,?);', 'MOV(' + '1' * 6000 + ',T.PRE);',
                           *('MOV(1,T.PRE);' for _ in range(MAX_WRITERS + 3))),
                          tag(data=decorated('x' * 6000) * (MAX_VALUES + 2)))
        index = VariableIndex(*wire(captured))
        identifier = captured[1].rungs[0].instructions[0].id
        view = index.view(identifier, 'T.PRE')
        self.assertEqual(view['captured_values_total'], MAX_VALUES + 2)
        self.assertTrue(view['captured_values_truncated'])
        self.assertTrue(view['writers_truncated'])
        self.assertEqual(len(view['writers']), MAX_WRITERS)
        self.assertTrue(view['captured_values'][0]['value_truncated'])
        self.assertTrue(view['writers'][1]['instruction_text_truncated'])
        self.assertEqual(len(view['writers'][1]['instruction_text']), 4096)
        self.assertIsNone(view['display_value'])
        view['captured_values'][0]['value'] = 'mutated'
        self.assertNotEqual(index.view(identifier, 'T.PRE')['captured_values'][0]['value'], 'mutated')
        with patch('plc_workbench.workspace_variables.MAX_INDEX_BYTES', 1), self.assertRaises(VariableError):
            VariableIndex(*wire(inputs()))


if __name__ == '__main__':
    unittest.main()
