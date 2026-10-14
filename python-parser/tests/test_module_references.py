"""Invented module I/O declarations exercise controller-scope root bindings."""
from __future__ import annotations

from copy import deepcopy
import unittest

from plc_workbench.reference_reporting import render_reference_text
from plc_workbench.references import ReferenceError, analyze_references, validate_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def routine(text: str) -> str:
    return ('<Routines><Routine Name="Main" Type="RLL"><RLLContent>'
            f'<Rung Number="0" Type="N"><Text><![CDATA[{text}]]></Text></Rung>'
            '</RLLContent></Routine></Routines>')


def program(text: str, tags: str = '', name: str = 'P') -> str:
    return f'<Program Name="{name}"><Tags>{tags}</Tags>{routine(text)}</Program>'


def module(inputs: str = '<InputTag Name="Remote:I"/>',
           outputs: str = '<OutputTag Name="Remote:O"/>',
           config: str = '<ConfigTag Name="Remote:C"/>') -> str:
    return ('<Modules><Module Name="Remote"><Communications>' + config +
            '<Connections><Connection Name="Data">' + inputs + outputs +
            '</Connection></Connections></Communications></Module></Modules>')


def inventory(body: str):
    return analyze_snapshot(snapshot_from_bytes((
        '<RSLogix5000Content><Controller Name="Demo">' + body +
        '</Controller></RSLogix5000Content>').encode()))


class ModuleReferenceTests(unittest.TestCase):
    def test_derived_io_names_bind_without_mutating_unnamed_source_records(self) -> None:
        modules = '''<Modules>
          <Module Name="Local" ParentModule="Local" ParentModPortId="1">
            <Ports><Port Id="1" Type="ICP" Address="0" Upstream="false"/></Ports>
          </Module>
          <Module Name="Card" ParentModule="Local" ParentModPortId="1">
            <Ports><Port Id="1" Type="ICP" Address="3" Upstream="true"/></Ports>
            <Communications><ConfigTag ConfigSize="4"/><Connections>
              <Connection Name="Data"><InputTag/><OutputTag/></Connection>
            </Connections></Communications>
          </Module></Modules>'''
        source = inventory(modules + '<Tags><Tag Name="InputAlias" TagType="Alias" '
                           'AliasFor="Local:3:I.Data.0"/></Tags><Programs>' +
                           program('XIC(InputAlias)MOV(Local:3:I.Data,Local:3:O.Data)'
                                   'XIC(Local:3:C.Setting);') + '</Programs>')
        before = source.to_dict()
        result = analyze_references(source)
        io = [row for row in result.symbols if row['kind'].startswith('module_')]
        self.assertEqual({row['name'] for row in io}, {'Local:3:I', 'Local:3:O', 'Local:3:C'})
        self.assertTrue(all(row['name_origin'] == 'backplane_slot' for row in io))
        self.assertTrue(all(row['name_reason'] is None for row in io))
        self.assertTrue(all(row['status'] == 'root_bound' for row in result.operands))
        self.assertTrue(all('Name' not in row['attributes'] for row in io))
        self.assertEqual(source.to_dict(), before)
        self.assertTrue(all(row.name is None for row in source.entities
                            if row.kind.startswith('module_') and row.kind.endswith('_tag')))
        self.assertEqual(result.status, 'complete')

    def test_unavailable_io_name_has_fixed_reason_and_remains_unnamed(self) -> None:
        source = inventory(module(inputs='<InputTag/>', outputs='', config='') +
                           '<Programs>' + program('XIC(Remote:I);') + '</Programs>')
        result = analyze_references(source)
        self.assertIsNone(result.symbols[0]['name'])
        self.assertEqual(result.symbols[0]['name_origin'], 'unavailable')
        self.assertEqual(result.symbols[0]['name_reason'], 'missing_parent_module')
        self.assertEqual(result.coverage['unnamed_symbols'], 1)
        self.assertEqual(result.operands[0]['status'], 'unresolved')
        self.assertEqual(result.operands[0]['reason'], 'colon_root_not_declared')
        self.assertEqual(result.status, 'partial')

    def test_all_module_io_kinds_are_controller_symbols_and_bind_aliases(self) -> None:
        source = inventory(module() + '<Tags><Tag Name="Alias" TagType="Alias" '
                           'AliasFor="Remote:I.Data.0"/></Tags><Programs>' +
                           program('XIC(Alias)MOV(Remote:I.Data,Remote:O.Data)XIC(Remote:C.Setting);') +
                           '</Programs>')
        result = analyze_references(source)
        io = [row for row in result.symbols if row['kind'].startswith('module_')]
        self.assertEqual({row['kind'] for row in io}, {
            'module_input_tag', 'module_output_tag', 'module_config_tag'})
        controller = next(row for row in source.entities if row.kind == 'controller')
        self.assertTrue(all(row['scope_id'] == controller.id for row in io))
        self.assertTrue(all(row['name_origin'] == 'explicit_name' for row in io))
        self.assertTrue(all(row['name_reason'] is None for row in io))
        self.assertTrue(all(row['status'] == 'root_bound' for row in result.operands))
        input_symbol = next(row for row in io if row['kind'] == 'module_input_tag')
        self.assertEqual(result.aliases[0]['target_id'], input_symbol['id'])
        self.assertEqual(result.aliases[0]['suffix'], '.Data.0')
        self.assertEqual(result.operands[0]['target_id'], input_symbol['id'])
        self.assertEqual(result.schema_version, 4)
        self.assertEqual(result.analyzer_version, 'source-references-7')
        self.assertEqual(result.status, 'complete')

    def test_tag_module_collision_is_ambiguous_and_program_tag_still_shadows(self) -> None:
        source = inventory(module() + '<Tags><Tag Name="REMOTE:I"/></Tags><Programs>' +
                           program('XIC(Remote:I);', name='ControllerUse') +
                           program('XIC(Remote:I);', '<Tag Name="Remote:I"/>', 'LocalUse') +
                           '</Programs>')
        result = analyze_references(source)
        self.assertEqual(result.operands[0]['status'], 'ambiguous')
        self.assertIsNone(result.operands[0]['reason'])
        self.assertEqual(result.operands[1]['status'], 'root_bound')
        symbol = next(row for row in result.symbols
                      if row['id'] == result.operands[1]['target_id'])
        self.assertEqual(symbol['kind'], 'tag')
        self.assertEqual(symbol['scope_id'], result.operands[1]['scope_id'])
        self.assertEqual(result.coverage['ambiguous_symbol_groups'], 1)

    def test_aoi_does_not_inherit_controller_module_symbols(self) -> None:
        source = inventory(module() + '<AddOnInstructionDefinitions>'
                           '<AddOnInstructionDefinition Name="AOI">' +
                           routine('XIC(Remote:I);') +
                           '</AddOnInstructionDefinition></AddOnInstructionDefinitions>')
        result = analyze_references(source)
        self.assertEqual(result.operands[0]['status'], 'unresolved')
        self.assertEqual(result.operands[0]['reason'], 'colon_root_not_declared')

    def test_module_symbols_never_fall_back_to_another_controller(self) -> None:
        raw = ('<RSLogix5000Content><Controller Name="One">' + module() +
               '</Controller><Controller Name="Two"><Programs>' +
               program('XIC(Remote:I);') + '</Programs></Controller></RSLogix5000Content>')
        result = analyze_references(analyze_snapshot(snapshot_from_bytes(raw.encode())))
        self.assertEqual(result.operands[0]['status'], 'unresolved')
        self.assertEqual(result.operands[0]['reason'], 'colon_root_not_declared')

    def test_module_raw_alias_attributes_remain_evidence_without_creating_aliases(self) -> None:
        source = inventory(module(inputs='<InputTag Name="Remote:I" TagType="Alias" '
                                  'AliasFor="Missing" InventedMetadata="retained"/>') +
                           '<Programs>' + program('XIC(Remote:I);') + '</Programs>')
        result = analyze_references(source)
        self.assertEqual(result.aliases, [])
        self.assertEqual(result.operands[0]['status'], 'root_bound')
        symbol = next(row for row in result.symbols if row['kind'] == 'module_input_tag')
        self.assertEqual(symbol['attributes'], {
            'Name': 'Remote:I', 'TagType': 'Alias', 'AliasFor': 'Missing',
            'InventedMetadata': 'retained'})
        self.assertEqual(symbol['name_origin'], 'explicit_name')

    def test_duplicate_io_names_remain_ambiguous(self) -> None:
        source = inventory(module(inputs='<InputTag Name="Remote:I"/><InputTag Name="remote:i"/>') +
                           '<Programs>' + program('XIC(Remote:I);') + '</Programs>')
        result = analyze_references(source)
        self.assertEqual(result.operands[0]['status'], 'ambiguous')
        self.assertEqual(result.coverage['ambiguous_symbol_groups'], 1)
        self.assertEqual(len({row['id'] for row in result.symbols}), 4)

    def test_canonical_validation_rejects_forged_io_name_and_provenance(self) -> None:
        source = inventory(module())
        result = analyze_references(source)
        for key, value in [('name', 'Forged:I'), ('name_origin', 'backplane_slot'),
                           ('name_reason', 'missing_parent_module')]:
            with self.subTest(field=key):
                changed = deepcopy(result)
                changed.symbols[0][key] = value
                with self.assertRaises(ReferenceError):
                    validate_references(source, changed)

    def test_private_text_exposes_name_provenance_and_failure_reasons(self) -> None:
        source = inventory(module() + '<Programs>' + program('XIC(Unknown:I);') + '</Programs>')
        text = render_reference_text(analyze_references(source))
        self.assertIn('name origin: explicit_name', text)
        self.assertIn('reason: colon_root_not_declared', text)
        self.assertIn('Remote:I', text)


if __name__ == '__main__':
    unittest.main()
