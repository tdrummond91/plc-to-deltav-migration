"""Invented catalog/address evidence never substitutes datatype for wiring proof."""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from plc_workbench.workspace_field_io import CATALOG_TYPES, FIELD_TYPE_REASONS, FieldIOError, FieldIOIndex, validate_query
from plc_workbench.workspace_io_comments import MAX_DESCRIPTION_CANDIDATES
from plc_workbench.workspace_variables import VariableError, VariableIndex
from test_workspace_connections import multi_routine
from test_workspace_variables import program, wire


def module(name: str, slot: int, catalog: str, vendor: str = '1', extra: str = '', data: str | None = None) -> str:
    leaves = ('<DataValueMember Name="Data" DataType="DINT" Value="0"/>'
              '<DataValueMember Name="Fault" DataType="DINT" Value="0"/>'
              '<DataValueMember Name="Ch0Data" DataType="REAL" Value="0.0"/>') if data is None else data
    content = f'<Data Format="Decorated"><Structure DataType="InventedModule">{leaves}</Structure></Data>'
    return (f'<Module Name="{name}" CatalogNumber="{catalog}" Vendor="{vendor}" '
            f'ParentModule="Local" ParentModPortId="1" {extra}>'
            f'<Description>Invented {name} module</Description><Ports><Port Id="1" Type="ICP" Address="{slot}" Upstream="true"/></Ports>'
            '<Communications><ConfigTag/><Connections><Connection Name="Data">'
            f'<InputTag>{content}</InputTag><OutputTag>{content}</OutputTag>'
            '</Connection></Connections></Communications></Module>')


def field_inputs(texts: tuple[str, ...] | None = None, *, modules: str | None = None,
                 local_tags: str = '', extra_tags: str = ''):
    if modules is None:
        modules = ''.join(module(name, slot, catalog) for name, slot, catalog in (
            ('DiscreteIn', 1, '1756-IB16'), ('DiscreteOut', 2, '1756-OB16E'),
            ('AnalogIn', 3, '1756-IF8'), ('AnalogOut', 4, '1756-OF8'), ('Unlisted', 5, 'INVENTED')))
    if texts is None:
        texts = ('XIC(InputAlias)OTE(Local:2:O.Data.0);',
                 'MOV(Local:3:I.Ch0Data,Local:4:O.Ch0Data);',
                 'XIC(Local:2:I.Data.0)XIC(Local:1:I.Fault.0);',
                 'MOV(Local:5:I.Ch0Data,InternalReal);',
                 'CPT(InternalReal,Local:3:I.Ch0Data+1);')
    tags = ('<Tag Name="InputAlias" TagType="Alias" AliasFor="Local:1:I.Data.0">'
            '<Description>Invented field alias description</Description></Tag>'
            '<Tag Name="InternalReal" DataType="REAL"/><Tag Name="InternalBool" DataType="BOOL"/>') + extra_tags
    local = ('<Module Name="Local" ParentModule="Local" ParentModPortId="1">'
             '<Ports><Port Id="1" Type="ICP" Address="0" Upstream="false"/></Ports></Module>')
    return multi_routine(program('Main', texts, local_tags), tags, '<Modules>' + local + modules + '</Modules>')


def build(captured=None) -> FieldIOIndex:
    return FieldIOIndex(VariableIndex(*wire(captured or field_inputs())))


def query(**kwargs) -> dict:
    return validate_query({'run_id': 'invented-run', **kwargs})


def selected(index: FieldIOIndex, name: str) -> dict:
    identifier = next(row['id'] for row in index.modules.values() if row['name'] == name)
    return index.view(query(module_id=identifier))


def address(view: dict, suffix: str, direction: str = 'input') -> dict:
    return next(row for row in view['addresses']['items'] if row['suffix'] == suffix and row['direction'] == direction)


class WorkspaceFieldIOTests(unittest.TestCase):
    def test_compact_description_origins_expand_without_mutating_shared_annotations(self) -> None:
        comments = '<Comments><Comment Operand=".Ch0Data">Precise point description</Comment></Comments>'
        card = module('InputCard', 1, '1756-IF8').replace('<InputTag>', '<InputTag>' + comments)
        index = build(field_inputs(modules=card))
        row = next(row for row in index.addresses.values()
                   if row['address'] == 'Local:1:I.Ch0Data')
        self.assertNotIn('candidates', row['description_selection'])
        selection = index.description_selection(row)
        self.assertEqual(selection['candidate_count'], 2)
        self.assertEqual([note['description_scope'] for note in selection['candidates']],
                         ['exact_member_comment', 'module_description'])
        original = deepcopy(selection)
        selection['candidates'][0]['owner_name'] = 'Changed response'
        selection['conflicting_annotation_ids'].append('Changed response')
        self.assertEqual(index.description_selection(row), original)
        public = selected(index, 'InputCard')
        address(public, '.Ch0Data')['description_selection']['candidates'][0]['via'] = 'Changed response'
        self.assertEqual(index.description_selection(row), original)

    def test_exact_catalog_module_classes_and_source_topology(self) -> None:
        index = build()
        self.assertGreater(len(CATALOG_TYPES), 39)
        view = index.view(query())
        self.assertEqual(view['modules']['total'], 6)
        self.assertEqual({row['name']: row['field_type'] for row in view['modules']['items']}, {
            'Local': 'unknown', 'DiscreteIn': 'di', 'DiscreteOut': 'do',
            'AnalogIn': 'ai', 'AnalogOut': 'ao', 'Unlisted': 'unknown'})
        card = selected(index, 'DiscreteIn')['selected_module']
        self.assertEqual(card['slot'], '1')
        self.assertEqual(card['controller']['name'], 'C')
        self.assertEqual(card['point_count'], 16)
        self.assertIn('rockwellautomation.com', card['catalog_reference'])
        self.assertEqual(card['group_member_ids'], [card['id']])

    def test_correct_direction_and_captured_profile_are_required_for_points(self) -> None:
        index = build()
        di = address(selected(index, 'DiscreteIn'), '.Data.0')
        do = address(selected(index, 'DiscreteOut'), '.Data.0', 'output')
        ai = address(selected(index, 'AnalogIn'), '.Ch0Data')
        ao = address(selected(index, 'AnalogOut'), '.Ch0Data', 'output')
        for row, kind in ((di, 'di'), (do, 'do'), (ai, 'ai'), (ao, 'ao')):
            self.assertEqual((row['field_type'], row['channel']), (kind, 0))
            self.assertEqual(row['point_status'], 'documented_member_layout')
            self.assertIn('literature.rockwellautomation.com', row['point_reference'])
            self.assertEqual(row['group_member_ids'], [row['root_id']])
        self.assertEqual(ai['configuration_status'], 'input_mode_unresolved')
        self.assertEqual(address(selected(index, 'DiscreteOut'), '.Data.0')['field_type'], 'unknown')
        self.assertIsNone(address(selected(index, 'DiscreteIn'), '.Fault.0')['channel'])
        self.assertIsNone(address(selected(index, 'Unlisted'), '.Ch0Data')['channel'])
        self.assertEqual(di['aliases'][0]['name'], 'InputAlias')
        self.assertEqual(di['description_basis'], 'exact_alias_description')
        self.assertEqual(di['description'], 'Invented field alias description')
        self.assertEqual(di['uses'][0]['role'], 'read')
        self.assertEqual(do['uses'][0]['role'], 'write')
        self.assertEqual(ai['uses_total'], 2)  # Direct operand and CPT expression.

    def test_module_catalog_is_not_prefix_type_or_user_defined_identity_guess(self) -> None:
        variants = [('1756-IB16', '2', ''), ('1756-IB16X', '1', ''), ('1756-ib16', '1', ''),
                    ('1756-IB16', '1', 'UserDefinedCatalogNumber="1756-IB16"')]
        for catalog, vendor, extra in variants:
            with self.subTest(catalog=catalog, vendor=vendor, extra=extra):
                view = selected(build(field_inputs(modules=module('Card', 1, catalog, vendor, extra))), 'Card')
                self.assertEqual(view['selected_module']['field_type'], 'unknown')
                self.assertIsNone(address(view, '.Data.0')['channel'])

    def test_module_reasons_partition_the_full_inventory_independent_of_filters(self) -> None:
        modules = ''.join((module('Supported', 1, '1756-IF8'),
            module('NoCatalog', 2, '').replace('CatalogNumber="" ', ''),
            module('OtherVendor', 3, '1756-IF8', vendor='2'),
            module('Override', 4, '1756-IF8', extra='UserDefinedCatalogNumber=""'),
            module('Unlisted', 5, 'UNLISTED'),
            module('Foreign', 6, '1756-IF8', extra='xmlns:x="urn:extension" x:Marker="present"')))
        index = build(field_inputs(modules=modules))
        view = index.view(query(field_type='ai'))
        self.assertEqual(view['modules']['total'], 1)
        reasons = view['coverage']['modules_by_field_type_reason']
        self.assertEqual(set(reasons), set(FIELD_TYPE_REASONS))
        self.assertEqual(reasons, {'exact_vendor_catalog': 1, 'source_unqualified': 1,
            'missing_catalog': 2, 'unsupported_vendor': 1, 'user_defined_catalog': 1, 'unsupported_catalog': 1})
        self.assertEqual(sum(reasons.values()), view['coverage']['modules_total'])
        self.assertEqual(reasons['exact_vendor_catalog'], sum(count for kind, count
            in view['coverage']['modules_by_field_type'].items() if kind != 'unknown'))
        self.assertEqual(selected(index, 'Override')['selected_module']['field_type_reason'], 'user_defined_catalog')
        self.assertEqual(selected(index, 'Foreign')['selected_module']['field_type_reason'], 'source_unqualified')

    def test_reason_priority_explains_first_gap_without_normalizing_identity(self) -> None:
        variants = [
            ('', '2', 'UserDefinedCatalogNumber=""', 'missing_catalog'),
            ('   ', '1', '', 'missing_catalog'),
            ('1756-IF8', '', 'UserDefinedCatalogNumber=""', 'unsupported_vendor'),
            ('1756-IF8', '1 ', '', 'unsupported_vendor'),
            ('1756-IF8 ', '1', '', 'unsupported_catalog'),
            ('1756-IF8', '1', 'UserDefinedCatalogNumber=""', 'user_defined_catalog'),
            ('', '', 'xmlns:x="urn:extension" x:Marker="present" UserDefinedCatalogNumber=""', 'source_unqualified'),
        ]
        for catalog, vendor, extra, reason in variants:
            with self.subTest(reason=reason, catalog=catalog, vendor=vendor):
                view = selected(build(field_inputs(modules=module('Card', 1, catalog, vendor, extra))), 'Card')
                card = view['selected_module']
                self.assertEqual(card['field_type'], 'unknown')
                self.assertEqual(card['field_type_reason'], reason)
                self.assertEqual(card['catalog_number'], catalog)
                self.assertEqual(card['vendor'], vendor)

    def test_vendor_function_mixed_filters_and_non_field_context_stay_separate(self) -> None:
        catalogs = (('HartInput', '1756-IF8IH'), ('HartOutput', '1756-OF8IH'),
                    ('Mixed', '1756-IF4FXOF2F'), ('Controller', '1756-L81E'), ('Network', '1756-EN2T'))
        modules = ''.join(module(name, slot, catalog).replace(f'<Description>Invented {name} module</Description>', '')
                          for slot, (name, catalog) in enumerate(catalogs, 1))
        index = build(field_inputs(modules=modules))
        self.assertEqual(index.view(query(field_type='ai'))['modules']['total'], 2)
        self.assertEqual(index.view(query(field_type='ao'))['modules']['total'], 2)
        mixed = selected(index, 'Mixed')['selected_module']
        self.assertEqual((mixed['field_type'], mixed['field_types']), ('mixed', ['ai', 'ao']))
        self.assertEqual(mixed['catalog_capacity'], {'ai': 4, 'ao': 2})
        self.assertIsNone(mixed['description'])
        self.assertTrue(mixed['catalog_description'])
        for name, role in (('Controller', 'controller'), ('Network', 'communication')):
            row = selected(index, name)['selected_module']
            self.assertEqual((row['field_type'], row['module_role']), ('non_field', role))
            self.assertEqual(row['field_types'], [])
            self.assertEqual(row['field_type_reason'], 'exact_vendor_catalog')
        coverage = index.view(query())['coverage']
        self.assertEqual(coverage['modules_by_field_type']['mixed'], 1)
        self.assertEqual(coverage['modules_by_filter']['ai'], 2)
        self.assertEqual(coverage['modules_by_filter']['non_field'], 2)
        self.assertEqual(coverage['modules_by_role'], {'field_io': 3, 'controller': 1, 'communication': 1, 'unknown': 1})
        self.assertEqual(sum(coverage['modules_by_field_type'].values()), coverage['modules_total'])
        self.assertIsNone(address(selected(index, 'HartInput'), '.Data.0')['channel'])

    def test_authored_comments_and_alias_notes_attach_only_to_exact_module_members(self) -> None:
        card = module('Card', 1, '1756-IB16').replace('<InputTag>', '<InputTag><Comments>'
            '<Comment Operand="Data.1"><LocalizedComment Lang="fr-FR">Entree un</LocalizedComment>'
            '<LocalizedComment Lang="en-US">Input one</LocalizedComment></Comment>'
            '<Comment Operand="Data.2">Input two only</Comment></Comments>')
        aliases = ('<Tag Name="WholeInput" TagType="Alias" AliasFor="Local:1:I">'
            '<Description>Whole backing description</Description><Comments>'
            '<Comment Operand="Data.3">Alias member three only</Comment></Comments></Tag>'
            '<Tag Name="PointAlias" TagType="Alias" AliasFor="Local:1:I.Data.4">'
            '<Description>Point four only</Description></Tag>')
        index = build(field_inputs(('XIC(InputAlias);',), modules=card, extra_tags=aliases))
        view = selected(index, 'Card')
        first = address(view, '.data.1')
        self.assertEqual({note['language'] for note in first['source_annotations']}, {'fr-FR', 'en-US'})
        self.assertEqual({note['text'] for note in first['source_annotations']}, {'Entree un', 'Input one'})
        self.assertEqual(first['channel'], 1)  # Comments can expose an otherwise unused captured member.
        second = address(view, '.data.2')
        self.assertEqual([note['text'] for note in second['source_annotations']], ['Input two only'])
        third = address(view, '.data.3')
        self.assertEqual(third['source_annotations'][0]['via'], 'alias')
        self.assertEqual(third['source_annotations'][0]['owner_name'], 'WholeInput')
        fourth = address(view, '.Data.4')
        self.assertEqual([note['text'] for note in fourth['source_annotations']], ['Point four only'])
        self.assertEqual(fourth['source_annotations_total'], 1)
        self.assertFalse(any('Input two' in note['text'] for note in first['source_annotations']))
        self.assertEqual(view['selected_module']['source_annotations'][0]['via'], 'module')

    def test_annotation_preview_keeps_duplicates_and_bounds_without_borrowing_rung_prose(self) -> None:
        notes = ''.join(f'<Comment Operand="Data.5">note-{number}</Comment>' for number in range(12))
        card = module('Card', 1, '1756-IB16').replace('<InputTag>', '<InputTag><Comments>' + notes + '</Comments>')
        view = selected(build(field_inputs(('XIC(InputAlias);',), modules=card)), 'Card')
        row = address(view, '.data.5')
        self.assertEqual((len(row['source_annotations']), row['source_annotations_total'], row['source_annotations_truncated']),
                         (8, 12, True))
        self.assertTrue(all(note['kind'] == 'member_comment' for note in row['source_annotations']))

    def test_description_selection_prefers_exact_point_and_exposes_conflicts(self) -> None:
        card = module('Card', 1, '1756-IB16').replace('<InputTag>', '<InputTag>'
            '<Description>Entire input payload</Description><Comments>'
            '<Comment Operand="Data.0">Point zero authored comment</Comment>'
            '<Comment Operand="Data.1">Same text</Comment><Comment Operand="Data.1">Same text</Comment>'
            '<Comment Operand="Data.2">Point two wording A</Comment>'
            '<Comment Operand="Data.2">Point two wording B</Comment></Comments>')
        index = build(field_inputs(('XIC(InputAlias)XIC(Local:1:I.Data.3);',), modules=card))
        first = address(selected(index, 'Card'), '.Data.0')
        selection = first['description_selection']
        self.assertEqual(first['description'], 'Point zero authored comment')
        self.assertEqual(selection['basis'], 'exact_member_comment')
        self.assertEqual(selection['status'], 'review_required')  # The exact alias has different wording.
        self.assertTrue(selection['conflict'])
        self.assertEqual(selection['candidate_count'], 4)
        self.assertEqual([note['description_scope'] for note in selection['candidates']],
                         ['exact_member_comment', 'exact_alias_description', 'backing_description', 'module_description'])
        self.assertTrue(all(note.get('owner_id') and note.get('locator') for note in selection['candidates']))
        self.assertEqual(index.annotation_texts[selection['preferred_annotation_id']], first['description'])
        second = address(selected(index, 'Card'), '.data.1')
        self.assertFalse(second['description_selection']['conflict'])
        third = address(selected(index, 'Card'), '.data.2')
        self.assertEqual(third['description_selection']['conflicting_annotation_count'], 2)
        fourth = address(selected(index, 'Card'), '.Data.3')
        self.assertEqual(fourth['description'], 'Entire input payload')
        self.assertEqual(fourth['description_basis'], 'backing_description')
        self.assertEqual(fourth['source_annotations'], [])  # Fallback is not relabeled point prose.

    def test_explicit_languages_are_alternatives_but_same_language_conflicts_are_visible(self) -> None:
        for duplicate, conflict in (('', False), ('<LocalizedComment Lang="fr-FR">Autre entree</LocalizedComment>', True)):
            with self.subTest(conflict=conflict):
                card = module('Card', 1, '1756-IB16').replace('<InputTag>', '<InputTag><Comments>'
                    '<Comment Operand="Data.1"><LocalizedComment Lang="fr-FR">Entree un</LocalizedComment>'
                    '<LocalizedComment Lang="en-US">Input one</LocalizedComment>' + duplicate + '</Comment></Comments>')
                row = address(selected(build(field_inputs(('XIC(InputAlias);',), modules=card)), 'Card'), '.data.1')
                selection = row['description_selection']
                self.assertEqual(selection['conflict'], conflict)
                self.assertEqual(row['description'], 'Entree un')
                self.assertEqual(selection['candidate_count'], 3 + bool(duplicate))  # Includes explicit module fallback.
                self.assertEqual({note['language'] for note in selection['candidates'][:2]}, {'fr-FR', 'en-US'})

    def test_sint_array_types_are_consistent_between_variable_and_io_views(self) -> None:
        data = '<ArrayMember Name="Data" DataType="SINT" Radix="Decimal" Dimensions="4"><Element Index="[2]" Value="12"/></ArrayMember>'
        captured = field_inputs(('MOV(Local:1:I.Data[2],InternalReal);',), modules=module('Bytes', 1, 'INVENTED', data=data))
        index = build(captured)
        row = address(selected(index, 'Bytes'), '.Data[2]')
        self.assertEqual(row['datatype'], 'SINT')
        self.assertIsNone(row['channel'])
        value = index.base.view(captured[1].rungs[0].instructions[0].id, 'Local:1:I.Data[2]')['captured_values'][0]
        self.assertEqual((value['datatype'], value['radix']), ('SINT', 'Decimal'))
        self.assertEqual(value['datatype_basis'], 'immediate_array')

    def test_description_conflicts_use_full_text_and_keep_bounded_origin_links(self) -> None:
        prefix = 'Shared preview prose ' * 40
        notes = ''.join(f'<Comment Operand="Data.1">{prefix} distinct ending {number}</Comment>'
                        for number in range(MAX_DESCRIPTION_CANDIDATES + 2))
        card = module('Card', 1, '1756-IB16').replace('<InputTag>', '<InputTag><Comments>' + notes + '</Comments>')
        index = build(field_inputs(('XIC(InputAlias);',), modules=card))
        row = address(selected(index, 'Card'), '.data.1')
        selection = row['description_selection']
        self.assertTrue(selection['conflict'])
        self.assertTrue(selection['candidates_truncated'])
        self.assertEqual(selection['conflicting_annotation_count'], MAX_DESCRIPTION_CANDIDATES + 2)
        self.assertEqual(len(selection['candidates']), MAX_DESCRIPTION_CANDIDATES)
        self.assertEqual(selection['candidate_count'], MAX_DESCRIPTION_CANDIDATES + 3)
        self.assertEqual(len(row['description']), 512)
        self.assertTrue(row['description_truncated'])
        self.assertTrue(index.annotation_texts[selection['preferred_annotation_id']].endswith('ending 0'))
        self.assertTrue(all('text' not in note for note in selection['candidates']))

    def test_note_search_uses_full_text_and_notes_beyond_the_display_limit(self) -> None:
        notes = '<Comment Operand="Data.5">' + 'Repeated prose ' * 50 + 'UniqueTailMatch</Comment>'
        notes += ''.join(f'<Comment Operand="Data.5">Visible note {number}</Comment>' for number in range(7))
        notes += '<Comment Operand="Data.5">NinthNoteMatch</Comment>'
        card = module('Card', 1, '1756-IB16').replace('<InputTag>', '<InputTag><Comments>' + notes + '</Comments>')
        index = build(field_inputs(('XIC(InputAlias);',), modules=card))
        row = address(selected(index, 'Card'), '.data.5')
        self.assertEqual((len(row['source_annotations']), row['source_annotations_total']), (8, 9))
        self.assertTrue(row['source_annotations'][0]['text_truncated'])
        preview = ' '.join(note['text'] for note in row['source_annotations'])
        for text in ('UniqueTailMatch', 'NinthNoteMatch'):
            self.assertNotIn(text, preview)
            found = index.view(query(query=text.lower()))['modules']
            self.assertEqual(found['total'], 1)
            self.assertEqual(found['items'][0]['name'], 'Card')

    def test_unrelated_tag_comments_do_not_exhaust_field_annotation_budget(self) -> None:
        card = module('Card', 1, '1756-IB16').replace('<InputTag>', '<InputTag><Comments>'
            '<Comment Operand="Data.1">Field point one</Comment></Comments>')
        unrelated = ''.join(f'<Tag Name="Internal{number}" DataType="DINT"><Comments>'
            '<Comment Operand="Value">' + 'Internal note ' * 20 + '</Comment></Comments></Tag>'
            for number in range(100))
        unrelated += ('<Tag Name="InternalAlias" TagType="Alias" AliasFor="InternalReal">'
            '<Description>Unrelated bound alias</Description></Tag>'
            '<Tag Name="MissingAlias" TagType="Alias" AliasFor="Missing">'
            '<Description>Unresolved alias</Description></Tag>'
            '<Tag Name="ForeignAlias" TagType="Alias" AliasFor="Local:1:I.Data.2" '
            'xmlns:x="urn:foreign" x:Extra="unsupported"><Description>Unqualified alias</Description></Tag>')
        evidence = VariableIndex(*wire(field_inputs(('XIC(InputAlias);',), modules=card, extra_tags=unrelated)))
        with patch('plc_workbench.workspace_io_comments.MAX_ANNOTATIONS', 3), \
                patch('plc_workbench.workspace_io_comments.MAX_ANNOTATION_CHARS', 100):
            index = FieldIOIndex(evidence)
            view = selected(index, 'Card')
            self.assertEqual(view['selected_module']['source_annotations_total'], 1)
            self.assertEqual(address(view, '.data.1')['source_annotations'][0]['text'], 'Field point one')
            self.assertEqual(address(view, '.Data.0')['source_annotations'][0]['via'], 'alias')
            self.assertEqual(len(index.annotation_texts), 3)
        for setting, limit, reason in (('MAX_ANNOTATIONS', 2, 'annotation_count_limit'),
                                       ('MAX_ANNOTATION_CHARS', 1, 'annotation_chars_limit')):
            with self.subTest(setting=setting), patch('plc_workbench.workspace_io_comments.' + setting, limit), \
                    self.assertRaisesRegex(FieldIOError, '^Saved field I/O evidence is inconsistent or exceeds its limits.$') as caught:
                FieldIOIndex(evidence)
            self.assertEqual(caught.exception.diagnostic['stage'], 'io_annotations')
            self.assertEqual(caught.exception.diagnostic['reason'], reason)
            self.assertEqual(caught.exception.diagnostic['limit'], limit)
            self.assertGreater(caught.exception.diagnostic['actual'], limit)

    def test_wrong_missing_duplicate_or_foreign_profile_types_do_not_map_points(self) -> None:
        for data in ('', '<DataValueMember Name="Data" DataType="BOOL" Value="0"/>',
                     '<DataValueMember Name="Data" DataType="DINT" Value="0"/>' * 2,
                     '<DataValueMember xmlns="urn:extension" Name="Data" DataType="DINT" Value="0"/>'):
            with self.subTest(data=data):
                view = selected(build(field_inputs(modules=module('Card', 1, '1756-IB16', data=data))), 'Card')
                self.assertEqual(view['selected_module']['field_type'], 'di')
                self.assertIsNone(address(view, '.Data.0')['channel'])

    def test_foreign_module_and_foreign_rung_do_not_create_proven_uses(self) -> None:
        capture = field_inputs(modules=module('Card', 1, '1756-IB16', extra='xmlns:x="urn:extension" x:Marker="foreign"'))
        view = selected(build(capture), 'Card')
        self.assertFalse(view['selected_module']['qualified'])
        self.assertEqual(view['selected_module']['field_type'], 'unknown')
        self.assertEqual(view['addresses']['total'], 0)
        source_program = program('Main', ('XIC(InputAlias);',)).replace('<Text>', '<Text xmlns="urn:extension">')
        capture = multi_routine(source_program,
            '<Tag Name="InputAlias" TagType="Alias" AliasFor="Card:I.Data.0"/>',
            '<Modules>' + module('Card', 1, '1756-IB16').replace('<InputTag>', '<InputTag Name="Card:I">') + '</Modules>')
        row = address(selected(build(capture), 'Card'), '.Data.0')
        self.assertEqual(row['uses_total'], 0)

    def test_out_of_range_dynamic_and_unknown_layouts_stay_unconfirmed(self) -> None:
        texts = ('XIC(Local:1:I.Data.15)XIC(Local:1:I.Data.16)XIC(Local:1:I.Data.00);',
                 'MOV(Local:3:I.Ch8Data,InternalReal)MOV(Local:1:I.Data[InternalReal],InternalReal);')
        index = build(field_inputs(texts))
        view = selected(index, 'DiscreteIn')
        self.assertEqual(address(view, '.Data.15')['channel'], 15)
        self.assertIsNone(address(view, '.Data.16')['channel'])
        self.assertIsNone(address(view, '.Data.00')['channel'])
        self.assertFalse(any('InternalReal' in row['suffix'] for row in view['addresses']['items']))
        other = selected(build(field_inputs(modules=module('Card', 1, '1756-IB32'))), 'Card')
        self.assertEqual(other['selected_module']['field_type'], 'di')
        self.assertIsNone(address(other, '.Data.0')['channel'])

    def test_scoped_shadow_and_aliases_never_cross_module_roots(self) -> None:
        capture = field_inputs(local_tags='<Tag Name="Local:1:I" DataType="REAL"/>')
        view = selected(build(capture), 'DiscreteIn')
        # Controller alias retains its own scope; direct spelling is shadowed.
        row = address(view, '.Data.0')
        self.assertEqual([use['variable'] for use in row['uses']], ['InputAlias'])
        self.assertFalse(any(item['root_name'] in {'InternalReal', 'InternalBool'} for item in view['addresses']['items']))

    def test_rack_aliases_retained_without_guessing_backing(self) -> None:
        rack = ('<Module Name="RackCard" CatalogNumber="1756-IB16" Vendor="1"><Communications>'
                '<Connections><RackConnection><InAliasTag AliasFor="Missing:I"/>'
                '<OutAliasTag/></RackConnection></Connections></Communications></Module>')
        view = selected(build(field_inputs(modules=rack)), 'RackCard')
        self.assertEqual(view['selected_module']['rack_aliases_total'], 2)
        self.assertTrue(all(row['status'] == 'backing_unresolved' for row in view['selected_module']['rack_aliases']))
        self.assertEqual(view['addresses']['total'], 0)

    def test_paging_search_aliases_and_field_filter_are_read_only(self) -> None:
        texts = tuple('XIC(InputAlias);' for _ in range(30))
        index = build(field_inputs(texts))
        before = deepcopy(index.modules)
        self.assertEqual(index.view(query(field_type='ai'))['modules']['total'], 1)
        self.assertEqual(index.view(query(query='field alias description'))['modules']['total'], 1)
        view = selected(index, 'DiscreteIn')
        first = address(view, '.Data.0')
        self.assertEqual((len(first['uses']), first['uses_total'], first['use_pages']), (12, 30, 3))
        last = index.view(query(module_id=view['selected_module']['id'], address_id=first['id'], use_page='3'))
        self.assertEqual(len(last['addresses']['items'][0]['uses']), 6)
        self.assertEqual(index.modules, before)

    def test_module_detail_alias_and_text_previews_are_bounded_with_totals(self) -> None:
        card = module('Card', 1, '1756-IB16').replace('Invented Card module', 'x' * 2000)
        ports = ''.join(f'<Port Id="{number}" Type="ICP" Address="0" Upstream="false"/>' for number in range(2, 32))
        connections = ''.join(f'<Connection Name="Extra{number}"><InputTag Name="Card:I{number}"/></Connection>'
                              for number in range(30))
        card = card.replace('</Ports>', ports + '</Ports>').replace('</Connections>', connections + '</Connections>')
        aliases = ''.join(f'<Tag Name="Alias{number}" TagType="Alias" AliasFor="Local:1:I.Data.0"/>'
                          for number in range(12))
        view = selected(build(field_inputs(modules=card, extra_tags=aliases)), 'Card')
        detail = view['selected_module']
        self.assertEqual((len(detail['ports']), detail['ports_total'], detail['ports_truncated']), (24, 31, True))
        self.assertEqual((len(detail['roots']), detail['roots_total'], detail['roots_truncated']), (24, 33, True))
        self.assertEqual(len(detail['description']), 512)
        self.assertTrue(detail['description_truncated'])
        # Root declaration pages may precede the used address; select by stable ID.
        index = build(field_inputs(modules=card, extra_tags=aliases))
        row = next(row for row in index.addresses.values() if row['suffix'] == '.Data.0')
        page = index.view(query(module_id=detail['id'], address_id=row['id']))
        self.assertEqual((len(page['addresses']['items'][0]['aliases']),
                          page['addresses']['items'][0]['aliases_total']), (8, 13))
        self.assertTrue(page['addresses']['items'][0]['aliases_truncated'])

    def test_module_pages_cover_unused_cards_and_internal_scalars_are_not_cards(self) -> None:
        modules = ''.join(module(f'Card{number}', number, '1756-IB16') for number in range(1, 28))
        index = build(field_inputs(('XIC(InternalBool);',), modules=modules))
        first, second = index.view(query(field_type='di')), index.view(query(field_type='di', page='2'))
        self.assertEqual((first['modules']['total'], len(first['modules']['items']), len(second['modules']['items'])), (27, 24, 3))
        self.assertEqual(len({row['id'] for row in first['modules']['items'] + second['modules']['items']}), 27)
        self.assertEqual(first['coverage']['rung_uses_total'], 0)
        self.assertEqual(first['coverage']['point_mapped_addresses'], 1)  # Authored InputAlias only, not 27*16 invented points.

    def test_module_address_identity_cannot_be_borrowed_from_another_card(self) -> None:
        index = build()
        one, two = selected(index, 'DiscreteIn'), selected(index, 'DiscreteOut')
        with self.assertRaises(FieldIOError):
            index.view(query(module_id=one['selected_module']['id'], address_id=two['addresses']['items'][0]['id']))

    def test_source_free_limits_and_strict_queries(self) -> None:
        evidence = VariableIndex(*wire(field_inputs()))
        for setting, value, reason in (('MAX_INDEX_BYTES', 10, 'index_bytes_limit'),
                                       ('MAX_ADDRESSES', 0, 'address_count_limit')):
            with self.subTest(setting=setting), patch('plc_workbench.workspace_field_io.' + setting, value):
                with self.assertRaisesRegex(FieldIOError, '^Saved field I/O evidence is inconsistent or exceeds its limits.$') as caught:
                    FieldIOIndex(evidence)
                self.assertEqual(caught.exception.diagnostic['stage'], 'field_io')
                self.assertEqual(caught.exception.diagnostic['reason'], reason)
                self.assertEqual(caught.exception.diagnostic['limit'], value)
                self.assertGreater(caught.exception.diagnostic['actual'], value)
        for values in ({'run_id': ''}, {'page': True}, {'page': '0'}, {'query': 'x' * 257},
                       {'field_type': 'BOOL'}, {'direction': 'di'}, {'address_id': 'invented'}):
            with self.subTest(values=values), self.assertRaises(FieldIOError):
                query(**values)
        index = FieldIOIndex(evidence)
        with patch('plc_workbench.workspace_field_io.MAX_RESPONSE_BYTES', 10), self.assertRaises(FieldIOError):
            index.view(query())

    def test_projection_failure_diagnostic_retains_no_source_exception(self) -> None:
        evidence = VariableIndex(*wire(field_inputs()))
        with patch.object(FieldIOIndex, '_build', side_effect=KeyError('PRIVATE_SOURCE_TAG')), \
                self.assertRaises(FieldIOError) as caught:
            FieldIOIndex(evidence)
        self.assertEqual(caught.exception.diagnostic,
                         {'stage': 'field_io', 'reason': 'projection_failed'})
        self.assertNotIn('PRIVATE_SOURCE_TAG', str(caught.exception))
        with self.assertRaises(FieldIOError) as invalid:
            FieldIOIndex(None)
        self.assertEqual(invalid.exception.diagnostic,
                         {'stage': 'field_io', 'reason': 'invalid_evidence'})

    def test_forged_evidence_is_rejected_before_projection(self) -> None:
        values = wire(field_inputs())
        values[1]['entities'][1]['attributes']['CatalogNumber'] = 'PRIVATE_FORGERY'
        with self.assertRaises(VariableError):
            FieldIOIndex(VariableIndex(*values))


if __name__ == '__main__':
    unittest.main()
