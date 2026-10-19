"""Invented module declarations exercise exact XML contexts and raw evidence."""
from __future__ import annotations

import unittest

from plc_workbench.models import InventoryResult
from plc_workbench.source import SourceError, analyze_snapshot, snapshot_from_bytes


def inventory(body: str, namespace: str = '') -> InventoryResult:
    xml = (f'<RSLogix5000Content{namespace}><Controller Name="Demo">{body}'
           '</Controller></RSLogix5000Content>')
    return analyze_snapshot(snapshot_from_bytes(xml.encode()))


MODULE = '''<Modules><Module Name="Remote" ParentModule="Local" ParentModPortId="1">
  <Ports><Port Id="1" Address="192.0.2.10" Type="Ethernet" Upstream="true"/>
    <Port Id="2" Address="3" Type="ICP" Upstream="false"/></Ports>
  <Communications>
    <ConfigTag ConfigSize="4" TagType="Alias" AliasFor="Uninterpreted">
      <Description>Invented configuration</Description>
      <Data Format="Decorated"><Structure DataType="Demo:C"><DataValueMember
        Name="Setting" DataType="DINT" Value="8"/></Structure></Data>
    </ConfigTag>
    <Connections>
      <Connection Name="Process" RPI="20000" Type="Input" InputTagSuffix="I2">
        <InputTag ExternalAccess="Read Only"><Data Format="L5K">[0]</Data></InputTag>
        <OutputTag Name="ExplicitEvidence" DataType="Demo:O"/>
      </Connection>
      <Connection Name="Diagnostics"><InputTag TagType="Alias"/></Connection>
    </Connections>
  </Communications>
</Module></Modules>'''


class ModuleSourceTests(unittest.TestCase):
    def test_module_records_have_exact_parent_scope_and_raw_attributes(self) -> None:
        result = inventory(MODULE)
        controller = next(e for e in result.entities if e.kind == 'controller')
        module = next(e for e in result.entities if e.kind == 'module')
        by_id = {e.id: e for e in result.entities}
        children = [e for e in result.entities if e.kind.startswith('module_')]
        self.assertEqual(len(children), 8)
        for entity in children:
            self.assertEqual(entity.scope_id, controller.id)
            if entity.kind in {'module_input_tag', 'module_output_tag'}:
                connection = by_id[entity.parent_id]
                self.assertEqual(connection.kind, 'module_connection')
                self.assertEqual(connection.parent_id, module.id)
            else:
                self.assertEqual(entity.parent_id, module.id)
        ports = [e for e in children if e.kind == 'module_port']
        self.assertEqual(ports[0].attributes, {
            'Id': '1', 'Address': '192.0.2.10', 'Type': 'Ethernet', 'Upstream': 'true',
        })
        self.assertIsNone(ports[0].name)
        config = next(e for e in children if e.kind == 'module_config_tag')
        self.assertEqual(config.description, 'Invented configuration')
        self.assertEqual(config.attributes['AliasFor'], 'Uninterpreted')
        self.assertIsNone(config.name)
        output = next(e for e in children if e.kind == 'module_output_tag')
        self.assertEqual(output.name, 'ExplicitEvidence')
        self.assertEqual(output.attributes['Name'], 'ExplicitEvidence')
        for entity in children:
            if entity.name is None:
                self.assertNotIn('Name', entity.attributes)
        self.assertFalse(result.diagnostics)
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.schema_version, 3)
        self.assertEqual(result.parser_version, 'source-inventory-3')

    def test_module_counts_are_separate_from_tag_and_alias_counts(self) -> None:
        result = inventory(MODULE + '<Tags><Tag Name="Bit" TagType="Base"/>'
                           '<Tag Name="Alias" TagType="Alias" AliasFor="Bit"/></Tags>')
        expected = {
            'modules': 1, 'module_ports': 2, 'module_connections': 2,
            'module_input_tags': 2, 'module_output_tags': 1, 'module_config_tags': 1,
            'controller_tags': 2, 'total_tag_definitions': 2, 'aliases': 1,
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(result.counts[key], value)
        empty = inventory('')
        for key in expected:
            self.assertEqual(empty.counts[key], 0)

    def test_data_is_preserved_as_unmodeled_xml_not_added_as_declarations(self) -> None:
        result = inventory(MODULE)
        paths = {row['path'] for row in result.coverage['unmodeled_xml_paths']}
        prefix = '/RSLogix5000Content/Controller/Modules/Module/Communications'
        self.assertIn(prefix + '/ConfigTag/Data/Structure/DataValueMember', paths)
        self.assertIn(prefix + '/Connections/Connection/InputTag/Data', paths)
        self.assertFalse(any(e.name == 'Setting' for e in result.entities))

    def test_connections_warn_on_missing_name_but_unnamed_ports_and_io_do_not(self) -> None:
        result = inventory('<Modules><Module Name="M"><Ports><Port/></Ports>'
                           '<Communications><ConfigTag/><Connections><Connection>'
                           '<InputTag/><OutputTag/></Connection></Connections>'
                           '</Communications></Module></Modules>')
        connection = next(e for e in result.entities if e.kind == 'module_connection')
        self.assertEqual(len(result.diagnostics), 1)
        self.assertEqual(result.diagnostics[0].code, 'entity_name_missing')
        self.assertEqual(result.diagnostics[0].source_id, connection.id)
        self.assertEqual(result.status, 'partial')

    def test_module_lookalikes_require_every_supported_parent_role(self) -> None:
        result = inventory('''<VendorExtension>
          <Modules><Module Name="Fake"><Ports><Port/></Ports><Communications>
            <ConfigTag/><Connections><Connection Name="Fake"><InputTag/><OutputTag/>
            </Connection></Connections></Communications></Module></Modules>
          </VendorExtension><Modules><Module Name="Real">
            <Port/><InputTag/><OutputTag/><ConfigTag/><Connection Name="Wrong"/>
            <Vendor><Ports><Port/></Ports><Communications><ConfigTag/><Connections>
              <Connection Name="Wrong"><InputTag/><OutputTag/></Connection>
            </Connections></Communications></Vendor>
            <ExtendedProperties><public><PL><Connection Name="VendorMetadata">
              <InputTag/><OutputTag/>
            </Connection></PL></public></ExtendedProperties>
            <Communications><InputTag/><Connections><PLConnection Name="Vendor">
              <InputTag/><OutputTag/></PLConnection><Connection Name="Ordinary">
              <ConfigTag/><Ports><Port/></Ports>
            </Connection></Connections></Communications>
          </Module></Modules>''')
        self.assertEqual(result.counts['modules'], 1)
        self.assertEqual(result.counts['module_connections'], 1)
        for kind in ('module_ports', 'module_input_tags', 'module_output_tags',
                     'module_config_tags'):
            self.assertEqual(result.counts[kind], 0)
        self.assertIn('declaration_context_not_analyzed',
                      {d.code for d in result.diagnostics})
        self.assertEqual(result.status, 'partial')

    def test_rack_declarations_are_captured_without_claiming_ordinary_io_or_backing(self) -> None:
        result = inventory('''<Modules><Module Name="Rack"><Communications><Connections>
          <RackConnection Name="RackConnection"><InAliasTag AliasFor="Rack:I"/>
            <OutAliasTag AliasFor="Rack:O"/><InputTag/><OutputTag/>
            <Connection Name="Nested"><InputTag/></Connection></RackConnection>
          </Connections></Communications></Module></Modules>''')
        self.assertEqual(result.counts['module_connections'], 0)
        self.assertEqual(result.counts['module_input_tags'], 0)
        self.assertEqual(result.counts['module_output_tags'], 0)
        self.assertEqual(result.counts['module_rack_connections'], 1)
        self.assertEqual(result.counts['module_rack_input_aliases'], 1)
        self.assertEqual(result.counts['module_rack_output_aliases'], 1)
        findings = [d for d in result.diagnostics
                    if d.code == 'module_rack_backing_not_analyzed']
        self.assertEqual(len(findings), 1)
        connection = next(e for e in result.entities if e.kind == 'module_rack_connection')
        self.assertEqual(findings[0].source_id, connection.id)
        paths = {row['path'] for row in result.coverage['unmodeled_xml_paths']}
        for name in ('RackConnection', 'InAliasTag', 'OutAliasTag'):
            self.assertFalse(any(path.endswith('/' + name) for path in paths))
        for name in ('InputTag', 'OutputTag', 'Connection'):
            self.assertTrue(any(path.endswith('/' + name) for path in paths))
        self.assertEqual(result.status, 'partial')

    def test_namespaced_declarations_retain_the_same_roles(self) -> None:
        ordinary = inventory(MODULE)
        namespaced = inventory(MODULE, ' xmlns="urn:invented-l5x"')
        self.assertEqual(ordinary.counts, namespaced.counts)
        self.assertEqual([e.kind for e in ordinary.entities],
                         [e.kind for e in namespaced.entities])
        self.assertFalse(namespaced.diagnostics)
        with self.assertRaises(SourceError):
            inventory('<Modules><Module Name="M"><Ports xmlns:a="one" xmlns:b="two">'
                      '<a:Port/><b:Port/></Ports></Module></Modules>')

    def test_duplicate_module_io_positions_get_deterministic_distinct_ids(self) -> None:
        body = MODULE.replace('<Connections>', '<Connections><Connection Name="Process">'
                              '<InputTag/><InputTag/></Connection>')
        first = inventory(body)
        second = inventory(body)
        self.assertEqual(first, second)
        ids = [e.id for e in first.entities]
        self.assertEqual(len(ids), len(set(ids)))
        inputs = [e for e in first.entities if e.kind == 'module_input_tag']
        self.assertEqual(inputs[0].parent_id, inputs[1].parent_id)
        self.assertNotEqual(inputs[0].id, inputs[1].id)
        self.assertNotEqual(inputs[0].locator, inputs[1].locator)


if __name__ == '__main__':
    unittest.main()
