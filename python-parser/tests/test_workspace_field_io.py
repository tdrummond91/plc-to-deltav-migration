"""Invented catalog/address evidence never substitutes datatype for wiring proof."""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from plc_workbench.workspace_field_io import CATALOG_TYPES, FieldIOError, FieldIOIndex, validate_query
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
    def test_exact_catalog_module_classes_and_source_topology(self) -> None:
        index = build()
        self.assertEqual(len(CATALOG_TYPES), 39)
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
        for setting, value in (('MAX_INDEX_BYTES', 10), ('MAX_ADDRESSES', 0)):
            with self.subTest(setting=setting), patch('plc_workbench.workspace_field_io.' + setting, value):
                with self.assertRaisesRegex(FieldIOError, '^Saved field I/O evidence is inconsistent or exceeds its limits.$'):
                    FieldIOIndex(evidence)
        for values in ({'run_id': ''}, {'page': True}, {'page': '0'}, {'query': 'x' * 257},
                       {'field_type': 'BOOL'}, {'direction': 'di'}, {'address_id': 'invented'}):
            with self.subTest(values=values), self.assertRaises(FieldIOError):
                query(**values)
        index = FieldIOIndex(evidence)
        with patch('plc_workbench.workspace_field_io.MAX_RESPONSE_BYTES', 10), self.assertRaises(FieldIOError):
            index.view(query())

    def test_forged_evidence_is_rejected_before_projection(self) -> None:
        values = wire(field_inputs())
        values[1]['entities'][1]['attributes']['CatalogNumber'] = 'PRIVATE_FORGERY'
        with self.assertRaises(VariableError):
            FieldIOIndex(VariableIndex(*values))


if __name__ == '__main__':
    unittest.main()
