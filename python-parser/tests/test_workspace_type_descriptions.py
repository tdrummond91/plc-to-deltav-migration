"""Invented UDT wording follows qualified member paths without unrolling data."""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from plc_workbench.workspace_application import ApplicationIndex
from plc_workbench.workspace_field_signals import FieldSignalIndex
from plc_workbench.workspace_type_descriptions import DeclaredMemberDescriptions, LOOKUP_REASONS
from plc_workbench.workspace_variables import VariableIndex
from test_workspace_application import detail as application_detail
from test_workspace_field_io import build as field_io, field_inputs, module
from test_workspace_field_signals import find, query
from test_workspace_signal_context import BOOLEAN, STATUS
from test_workspace_signal_usage import recapture
from test_workspace_variables import wire


def member(name: str, datatype: str = 'REAL', description: str = 'Invented member wording', extra: str = '') -> str:
    return f'<Member Name="{name}" DataType="{datatype}" {extra}><Description>{description}</Description></Member>'


def definition(name: str, body: str) -> str:
    return f'<DataType Name="{name}"><Members>{body}</Members></DataType>'


def with_types(inputs, definitions: str):
    return recapture(inputs[0].data.replace(b'</Controller>',
        ('<DataTypes>' + definitions + '</DataTypes></Controller>').encode()))


def inspect(index: DeclaredMemberDescriptions, name: str, suffix: str) -> dict:
    root = next(entity for entity in index.base._entities.values() if entity.name == name)
    return index.inspect(root.id, suffix)


class TypeDescriptionTests(unittest.TestCase):
    def test_module_structure_member_description_has_type_owner_and_shared_annotation_id(self) -> None:
        definitions = definition('InventedModule', member('Ch0Data'))
        field = field_io(with_types(field_inputs(('MOV(Local:3:I.Ch0Data,InternalReal);',)), definitions))
        before = deepcopy(field.base._captured)
        signal = find(FieldSignalIndex(field), 'Local:3:I.Ch0Data')
        self.assertEqual(signal['description'], 'Invented member wording')
        origin = signal['description_origin']
        self.assertEqual((origin['kind'], origin['basis'], origin['specific']),
                         ('type_member', 'declared_member_description', True))
        self.assertEqual((origin['owner_name'], origin['owner_suffix']), ('InventedModule.Ch0Data', '.Ch0Data'))
        self.assertEqual(field.base._entities[origin['owner_id']].kind, 'data_type')
        self.assertTrue(origin['owner_path'].endswith(' / Ch0Data'))
        app = ApplicationIndex(field)
        note = next(note for note in application_detail(app, 'Local:3:I.Ch0Data')['source_annotations']
                    if note['kind'] == 'datatype_member_description')
        self.assertEqual(note['id'], origin['annotation_id'])
        self.assertEqual(field.base._captured, before)

    def test_array_rank_bounds_nested_types_and_recursion_do_not_expand_members(self) -> None:
        schemas = definition('Outer', member('Items', 'Inner', extra='Dimension="2,3"'))
        schemas += definition('Inner', member('Value') + member('Next', 'Inner'))
        tags = '<Tag Name="Record" DataType="Outer"/><Tag Name="RootArray" DataType="Outer" Dimensions="4"/>'
        base = VariableIndex(*wire(with_types(field_inputs((), extra_tags=tags), schemas)))
        index = DeclaredMemberDescriptions(base)
        result = inspect(index, 'Record', '.Items[1,2].Value')
        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['facts']['array_rank'], 2)
        self.assertEqual(result['facts']['member_depth'], 2)
        self.assertEqual(result['annotations'][0]['owner_name'], 'Inner.Value')
        self.assertEqual(inspect(index, 'RootArray', '[3].Items[0,1].Value')['status'], 'available')
        for suffix in ('.Items[2,0].Value', '.Items[0].Value', '.Items.Value', '.Items[Index,0].Value', '.Items[0,1,2].Value'):
            with self.subTest(suffix=suffix):
                self.assertEqual(inspect(index, 'Record', suffix)['status'], 'unsupported_path')
        self.assertEqual(inspect(index, 'RootArray', '[4].Items[0,1].Value')['status'], 'unsupported_path')
        # Recursive types do not unroll; only a bounded, explicitly requested path is walked.
        self.assertEqual(inspect(index, 'Record', '.Items[0,0]' + '.Next' * 40 + '.Value')['status'], 'unsupported_path')
        before = (deepcopy(index._definitions), index._budget)
        for number in range(300):
            inspect(index, 'RootArray', f'[{number % 4}].Items[0,1].Value')
        self.assertEqual((index._definitions, index._budget), before)

    def test_multilingual_notes_remain_alternatives_and_same_language_conflicts_visible(self) -> None:
        texts = '<LocalizedDescription Lang="fr">Pression inventee</LocalizedDescription><LocalizedDescription Lang="en">Invented pressure</LocalizedDescription>'
        for extra, conflict in (('', False), ('<LocalizedDescription Lang="fr">Autre texte</LocalizedDescription>', True)):
            with self.subTest(conflict=conflict):
                field = field_io(with_types(field_inputs(()), definition('InventedModule', member('Ch0Data', description=texts + extra))))
                row = find(FieldSignalIndex(field), 'Local:3:I.Ch0Data')
                notes = [note for note in row['source_annotations'] if note['kind'] == 'datatype_member_description']
                self.assertEqual([note['language'] for note in notes[:2]], ['fr', 'en'])
                self.assertEqual(row['description_selection']['conflict'], conflict)
                self.assertEqual(row['description_origin']['kind'], 'type_member')
                self.assertEqual(field.member_descriptions.lookup_reason(row['root_id'], row['suffix']),
                                 'conflict' if conflict else 'available')

    def test_exact_instance_comment_and_alias_outrank_type_template(self) -> None:
        card = module('Analog', 3, '1756-IF8').replace('<InputTag>', '<InputTag><Comments>'
            '<Comment Operand="Ch0Data">Invented instance comment</Comment></Comments>')
        alias = '<Tag Name="Specific" TagType="Alias" AliasFor="Local:3:I.Ch0Data"><Description>Invented alias text</Description></Tag>'
        for comments, expected in ((False, 'alias'), (True, 'channel')):
            actual = card if comments else module('Analog', 3, '1756-IF8')
            row = find(FieldSignalIndex(field_io(with_types(field_inputs((), modules=actual, extra_tags=alias),
                definition('InventedModule', member('Ch0Data'))))), 'Local:3:I.Ch0Data')
            self.assertEqual(row['description_origin']['kind'], expected)
            self.assertTrue(any(note['kind'] == 'datatype_member_description' for note in row['source_annotations']))

    def test_described_udt_result_supplies_input_context_with_separate_type_owner(self) -> None:
        inputs = field_inputs((BOOLEAN.replace('OTE(Status)', 'OTE(Status.Ready)'),),
            extra_tags='<Tag Name="Status" DataType="StateRecord"/>')
        field = field_io(with_types(inputs, definition('StateRecord', member('Ready', 'BOOL', 'Invented readiness result'))))
        row = find(FieldSignalIndex(field), 'Local:1:I.Data.1')
        context = row['use_context']
        self.assertEqual(context['description'], 'Invented readiness result')
        self.assertEqual(context['result_name'], 'Status.Ready')
        self.assertEqual(context['description_basis'], 'declared_member_description')
        self.assertEqual(context['description_owner_name'], 'StateRecord.Ready')
        self.assertEqual(context['description_owner_suffix'], '.Ready')
        self.assertNotEqual(context['description_source_id'], context['result_id'])
        self.assertEqual(field.base._entities[context['description_source_id']].kind, 'data_type')

    def test_conflicting_duplicate_or_foreign_definitions_do_not_select_a_template(self) -> None:
        valid = definition('InventedModule', member('Ch0Data'))
        variants = (valid + valid,
            definition('InventedModule', member('Ch0Data') + member('ch0data', description='Other')),
            valid.replace('<Member ', '<Member xmlns:x="urn:foreign" x:Bad="true" '),
            valid.replace('<Members>', '<Members xmlns="urn:foreign">'),
            valid.replace('<DataType ', '<DataType Protected="true" '),
            valid.replace('DataType="REAL"', 'DataType="REAL" Dimension="2" Dimensions="3"'))
        for schema in variants:
            with self.subTest(schema=schema[:70]):
                field = field_io(with_types(field_inputs(()), schema))
                row = find(FieldSignalIndex(field), 'Local:3:I.Ch0Data')
                self.assertEqual(row['description_origin']['kind'], 'module')
                self.assertEqual(field.member_descriptions.lookup_reason(row['root_id'], row['suffix']), 'conflict')

    def test_captured_conflicts_foreign_shapes_and_duplicate_representations_are_rejected(self) -> None:
        schema = definition('InventedModule', member('Ch0Data'))
        leaf = '<DataValueMember Name="Ch0Data" DataType="DINT" Value="0"/>'
        cards = (module('Analog', 3, 'INVENTED', data=leaf),
            module('Analog', 3, 'INVENTED').replace('<Structure ', '<Structure xmlns:x="urn:foreign" x:Bad="true" '),
            module('Analog', 3, 'INVENTED').replace('</InputTag>', '<Data Format="Decorated"><Structure DataType="InventedModule"/></Data></InputTag>'))
        for card in cards:
            with self.subTest(card=card[:60]):
                inputs = with_types(field_inputs(('MOV(Local:3:I.Ch0Data,InternalReal);',), modules=card), schema)
                row = find(FieldSignalIndex(field_io(inputs)), 'Local:3:I.Ch0Data')
                self.assertEqual(row['description_origin']['kind'], 'module')
        tags = '<Tag Name="Record" DataType="Outer"><Data Format="Decorated"><Structure DataType="Other"/></Data></Tag>'
        index = DeclaredMemberDescriptions(VariableIndex(*wire(with_types(field_inputs((), extra_tags=tags), definition('Outer', member('Value'))))))
        self.assertEqual(inspect(index, 'Record', '.Value')['status'], 'conflict')

    def test_array_elements_inherit_member_wording_without_becoming_whole_root_wording(self) -> None:
        schema = definition('InventedModule', member('Data', 'DINT', 'Invented register template', 'Dimension="8"'))
        data = '<ArrayMember Name="Data" DataType="DINT" Dimensions="8"><Element Index="[4]" Value="0"/></ArrayMember>'
        field = field_io(with_types(field_inputs(('MOV(Local:8:I.Data[4],InternalReal);',),
            modules=module('Register', 8, 'INVENTED', data=data)), schema))
        row = find(FieldSignalIndex(field), 'Local:8:I.Data[4]')
        self.assertEqual(row['description'], 'Invented register template')
        self.assertEqual(row['description_origin']['owner_suffix'], '.Data')
        self.assertEqual(field.member_descriptions.lookup_reason(row['root_id'], '.Data[8]'), 'unsupported_path')
        self.assertEqual(field.member_descriptions.lookup_reason(row['root_id'], '.Data[04]'), 'available')
        self.assertEqual(field.member_descriptions.lookup_reason(row['root_id'], '.Data[4].1'), 'unsupported_path')

    def test_logical_rack_alias_uses_canonical_udt_ancestry_without_false_bit_inheritance(self) -> None:
        from test_rack_backing_context import fixture
        from test_workspace_rack_references import index as rack_index
        text = fixture(rungs=('MOV(Remote:3:I.Data,Stored);',), tags='<Tag Name="Stored" DataType="DINT"/>', sfc='')
        # Use the independently invented rack fixture's actual native layout names.
        field = rack_index(text)
        root = next(row for row in field.addresses.values() if row.get('rack_mapping') and row['direction'] == 'input')
        root_type = next(iter(field.base._types[root['root_id'], '']))
        slot_type = next(iter(field.base._types[root['root_id'], '.slot[3]']))
        schemas = definition(root_type, member('Slot', slot_type, extra='Dimension="17"'))
        schemas += definition(slot_type, member('Data', 'DINT', 'Invented rack word'))
        text = text.replace('</Controller>', '<DataTypes>' + schemas + '</DataTypes></Controller>')
        field = rack_index(text)
        word = next(row for row in field.addresses.values() if row.get('rack_mapping') and row['suffix'].endswith('.Data'))
        status = field.member_descriptions.lookup_reason(word['root_id'], word['suffix'])
        self.assertEqual(status, 'available')
        self.assertEqual(word['description'], 'Invented rack word')
        self.assertEqual(field.member_descriptions.lookup_reason(word['root_id'], word['suffix'] + '.0'), 'unsupported_path')

    def test_numeric_equivalent_indices_cannot_bypass_captured_type_conflicts(self) -> None:
        schemas = definition('RecordType', member('Values', 'REAL', extra='Dimension="2"'))
        data = '<Data Format="Decorated"><Structure DataType="RecordType"><ArrayMember Name="Values" DataType="REAL" Dimensions="2">'
        data += '<Element Index="[1]" DataType="DINT" Value="0"/></ArrayMember></Structure></Data>'
        inputs = field_inputs((), extra_tags='<Tag Name="Record" DataType="RecordType">' + data + '</Tag>')
        index = DeclaredMemberDescriptions(VariableIndex(*wire(with_types(inputs, schemas))))
        for suffix in ('.Values[1]', '.values[01]', '.Values[ 1 ]'):
            self.assertEqual(inspect(index, 'Record', suffix)['status'], 'conflict')

    def test_result_alias_inherits_target_member_template_but_own_description_wins(self) -> None:
        tags = '<Tag Name="Status" DataType="StateRecord"/><Tag Name="ReadyAlias" TagType="Alias" AliasFor="Status.Ready"/>'
        schema = definition('StateRecord', member('Ready', 'BOOL', 'Invented type readiness'))
        for described in (False, True):
            actual = tags.replace('AliasFor="Status.Ready"/>', 'AliasFor="Status.Ready"><Description>Specific alias result</Description></Tag>') if described else tags
            field = field_io(with_types(field_inputs((BOOLEAN.replace('Status', 'ReadyAlias'),), extra_tags=actual), schema))
            context = find(FieldSignalIndex(field), 'Local:1:I.Data.1')['use_context']
            self.assertEqual(context['description'], 'Specific alias result' if described else 'Invented type readiness')
            self.assertEqual(context['result_name'], 'ReadyAlias')
            self.assertEqual(context['description_basis'], 'exact_alias_description' if described else 'declared_member_description')

    def test_foreign_description_is_ignored_and_huge_arrays_keep_one_template(self) -> None:
        schema = definition('RecordType', member('Values', 'REAL', extra='Dimension="2000000000"'))
        inputs = field_inputs((), extra_tags='<Tag Name="Record" DataType="RecordType"/>')
        index = DeclaredMemberDescriptions(VariableIndex(*wire(with_types(inputs, schema))))
        self.assertEqual(inspect(index, 'Record', '.Values[1999999999]')['status'], 'available')
        self.assertEqual(index._member_count, 1)
        self.assertLess(index._budget, 2048)
        foreign = schema.replace('<Description>', '<Description xmlns="urn:foreign">')
        index = DeclaredMemberDescriptions(VariableIndex(*wire(with_types(inputs, foreign))))
        self.assertEqual(inspect(index, 'Record', '.Values[1]')['status'], 'no_description')

    def test_diagnostic_enum_and_capacity_are_source_free_and_reads_do_not_retain_paths(self) -> None:
        schemas = definition('RecordType', member('Known') + member('Blank', description=''))
        inputs = with_types(field_inputs((), extra_tags='<Tag Name="Record" DataType="RecordType"/>'), schemas)
        index = DeclaredMemberDescriptions(VariableIndex(*wire(inputs)))
        root = next(entity.id for entity in index.base._entities.values() if entity.name == 'Record')
        self.assertEqual(index.lookup_reason(root, '.Known'), 'available')
        self.assertEqual(index.lookup_reason(root, '.Blank'), 'no_description')
        self.assertEqual(index.lookup_reason(root, '.Missing'), 'member_not_declared')
        self.assertEqual(index.lookup_reason(root, '.Known.Nested'), 'no_type_definition')
        result = index.diagnostic(root, '.Known')
        self.assertEqual(set(result), {'status', 'root_type_declared', 'captured_layout', 'path_static',
                                      'member_depth', 'array_rank', 'description_count'})
        self.assertIn(result['status'], LOOKUP_REASONS)
        self.assertTrue(all(type(value) in {int, bool} for key, value in result.items() if key != 'status'))
        original = index.inspect(root, '.Known')
        changed = index.inspect(root, '.Known')
        changed['annotations'][0]['text'] = 'Changed'
        self.assertEqual(index.inspect(root, '.Known'), original)
        with patch('plc_workbench.workspace_type_descriptions.MAX_METADATA_BYTES', 1):
            bounded = DeclaredMemberDescriptions(index.base)
        self.assertFalse(bounded.available)
        self.assertEqual(bounded.lookup_reason(root, '.Known'), 'capacity')
        self.assertEqual((bounded._definitions, bounded._layouts, bounded._budget), ({}, {}, 0))

    def test_nearest_containing_comments_are_inherited_but_not_specific_or_name_prefix_matches(self) -> None:
        card = module('Input', 1, '1756-IB16').replace('<InputTag>', '<InputTag><Comments>'
            '<Comment Operand="Data">Invented input word</Comment><Comment Operand="Data.2">Exact bit</Comment>'
            '<Comment Operand="Data10">Other member</Comment></Comments>')
        field = field_io(field_inputs(('XIC(Local:1:I.Data.1)XIC(Local:1:I.Data.2)XIC(Local:1:I.Data10.1);',), modules=card))
        index = FieldSignalIndex(field)
        row = find(index, 'Local:1:I.Data.1')
        self.assertEqual(row['description'], 'Invented input word')
        self.assertEqual(row['description_origin']['kind'], 'containing_member')
        self.assertEqual(row['description_origin']['owner_name'], 'Local:1:I')
        self.assertFalse(row['description_origin']['specific'])
        self.assertEqual(row['description_origin']['owner_suffix'], '.data')
        self.assertEqual(find(index, 'Local:1:I.Data.2')['description_origin']['kind'], 'channel')
        other = next(row for row in field.addresses.values() if row['address'] == 'Local:1:I.Data10.1')
        self.assertEqual(other['description'], 'Other member')
        self.assertFalse(any(field.annotation_texts[note['id']] == 'Invented input word' for note in other['source_annotations']))

    def test_inherited_parent_comments_do_not_hide_result_context_or_prevent_empty_filter(self) -> None:
        comments = '<Comments><Comment Operand="Data">Generic parent wording</Comment></Comments>'
        card = module('Input', 1, '1756-IB16').replace('<InputTag>', '<InputTag>' + comments)
        inputs = field_inputs((BOOLEAN,), modules=card, extra_tags=STATUS)
        index = FieldSignalIndex(field_io(inputs))
        row = find(index, 'Local:1:I.Data.1')
        self.assertEqual(row['description_origin']['kind'], 'containing_member')
        self.assertEqual(row['use_context']['description'], 'Invented two-limit permissive')
        data = '<ArrayMember Name="Data" DataType="DINT" Dimensions="2"><Element Index="[0]" Value="0"/></ArrayMember>'
        card = module('Array', 8, 'INVENTED', data=data).replace('<InputTag>', '<InputTag>' + comments)
        index = FieldSignalIndex(field_io(field_inputs((), modules=card)))
        empty = find(index, 'Local:8:I.Data[0]')
        self.assertEqual(empty['description_origin']['kind'], 'containing_member')
        self.assertNotIn(empty['id'], {row['id'] for row in index.view(query(hide_empty=1))['signals']['items']})


if __name__ == '__main__':
    unittest.main()
