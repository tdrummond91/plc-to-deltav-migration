"""Invented evidence verifies conservative, source-linked classification groups."""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from plc_workbench.workspace_classification import CATEGORY_DEFINITIONS, build_classification


class Evidence:
    def __init__(self) -> None:
        self.inventory = {'snapshot': {'id': 'invented-snapshot'}, 'entities': [], 'rungs': []}
        self.analysis = {'snapshot': self.inventory['snapshot'], 'blocks': [], 'candidates': []}
        self.report = {'access': {'operands': [], 'expression_uses': []},
            'tag_data': {'contents': [], 'elements': []},
            'pid': {'occurrences': []}, 'stateful_objects': {'objects': []},
            'relationships': {'addresses': []}, 'engineering_assemblies': {'memberships': []}}

    def entity(self, name: str, datatype: str = 'BOOL', kind: str = 'tag', **attributes) -> str:
        self.inventory['entities'].append({'id': name, 'name': name, 'kind': kind,
            'parent_id': None, 'attributes': {'DataType': datatype, **attributes}})
        return name

    def instruction(self, rung: str, opcode: str, uses: list[tuple[str, str, str]], family: str = '') -> str:
        rows = [row for row in self.inventory['rungs'] if row['id'] == rung]
        if not rows:
            rows = [{'id': rung, 'number': rung, 'parse_status': 'parsed', 'instructions': []}]
            self.inventory['rungs'].extend(rows)
        identifier = f'{rung}-i{len(rows[0]["instructions"])}'
        rows[0]['instructions'].append({'id': identifier, 'opcode': opcode, 'arguments': []})
        self.analysis['blocks'].append({'id': identifier, 'rung_id': rung, 'opcode': opcode, 'family': family})
        for index, (owner, suffix, role) in enumerate(uses):
            self.report['access']['operands'].append({'id': f'{identifier}-o{index}',
                'instruction_id': identifier, 'rung_id': rung, 'target_id': owner,
                'suffix': suffix, 'role': role, 'binding_status': 'root_bound'})
        return identifier

    def data(self, owner: str, members: list[tuple[str, str, str]]) -> None:
        number = len(self.report['tag_data']['contents'])
        content = f'content-{number}'
        self.report['tag_data']['contents'].append({'id': content, 'format_kind': 'decorated',
            'xml_namespace': None, 'attributes': {'Format': 'Decorated'}, 'direct_text': ''})
        self.report['tag_data']['elements'].append({'id': content + '-root', 'owner_id': owner,
            'parent_id': content, 'kind': 'structure', 'xml_namespace': None, 'direct_text': '',
            'attributes': {'DataType': 'InventedStructure'}})
        for index, (name, datatype, value) in enumerate(members):
            self.report['tag_data']['elements'].append({'id': f'{content}-{index}',
                'owner_id': owner, 'parent_id': content + '-root', 'kind': 'data_value_member',
                'xml_namespace': None, 'direct_text': '',
                'attributes': {'Name': name, 'DataType': datatype, 'Value': value}})

    def result(self) -> dict:
        # Focused projection fixtures supply already qualified canonical IDs.
        # Real XML qualification is covered separately below through the parser.
        qualification = ({row['id']: True for row in self.inventory['entities']},
                         {row['id']: True for row in self.inventory['rungs']}, None)
        with patch('plc_workbench.workspace_classification._qualify_source', return_value=qualification):
            return build_classification(self.inventory, self.analysis, self.report, source=b'')


def address(result: dict, owner: str, suffix: str = '') -> dict:
    return next(row for row in result['groups'] if row['anchor_id'] == owner and row['address_suffix'] == suffix)


class ClassificationTests(unittest.TestCase):
    def test_discrete_and_analogue_definitions_and_internal_types(self) -> None:
        definitions = {row['id']: row for row in CATEGORY_DEFINITIONS}
        self.assertIn('discrete calculation', definitions['dc']['label'])
        self.assertIn('analogue calculation', definitions['ac']['label'])
        ev = Evidence()
        ev.entity('Input')
        ev.entity('BooleanResult')
        ev.entity('FloatResult', 'REAL')
        ev.entity('IntegerResult', 'DINT')
        ev.instruction('r1', 'XIC', [('Input', '', 'read')], 'boolean_condition')
        ev.instruction('r1', 'OTE', [('BooleanResult', '', 'write')], 'boolean_output')
        ev.instruction('r2', 'ADD', [('FloatResult', '', 'write')], 'calculation')
        ev.instruction('r3', 'ADD', [('IntegerResult', '', 'write')], 'calculation')
        result = ev.result()
        self.assertEqual(address(result, 'BooleanResult')['category_ids'], ['dc'])
        self.assertEqual(address(result, 'FloatResult')['category_ids'], ['ac'])
        self.assertEqual(address(result, 'IntegerResult')['category_ids'], ['calculation'])
        self.assertFalse({'ai', 'ao', 'di', 'do'} & {category for row in result['groups'] for category in row['category_ids']})

    def test_typed_member_qualification_and_duplicate_ambiguity(self) -> None:
        ev = Evidence()
        ev.entity('Values', 'InventedStructure')
        ev.data('Values', [('Float', 'LREAL', '2.5'), ('Integer', 'DINT', '3')])
        for suffix in ('.Float', '.Integer', '.Unknown'):
            ev.instruction(suffix, 'CPT', [('Values', suffix, 'write')], 'calculation')
        result = ev.result()
        self.assertIn('ac', address(result, 'Values', '.Float')['category_ids'])
        self.assertIn('calculation', address(result, 'Values', '.Integer')['category_ids'])
        self.assertIn('calculation', address(result, 'Values', '.Unknown')['category_ids'])
        ev.data('Values', [('Float', 'LREAL', '2.5')])
        self.assertNotIn('ac', address(ev.result(), 'Values', '.Float')['category_ids'])

    def test_io_requires_direction_data_role_and_unique_type(self) -> None:
        ev = Evidence()
        for owner, kind, datatype in [('AI', 'module_input_tag', 'REAL'),
                                      ('AO', 'module_output_tag', 'REAL'),
                                      ('DI', 'module_input_tag', 'BOOL'),
                                      ('DO', 'module_output_tag', 'BOOL')]:
            ev.entity(owner, 'ModuleType', kind)
            ev.data(owner, [('Data', datatype, '0'), ('Fault', 'BOOL', '0'), ('Ready', 'BOOL', '1')])
            for name in ('Data', 'Fault', 'Ready'):
                ev.instruction(owner + name, 'MOV', [(owner, '.' + name, 'read')], 'data_transfer')
        result = ev.result()
        for owner in ('AI', 'AO', 'DI', 'DO'):
            self.assertIn(owner.lower(), address(result, owner, '.Data')['category_ids'])
            for name in ('.Fault', '.Ready'):
                categories = address(result, owner, name)['category_ids']
                self.assertFalse({'ai', 'ao', 'di', 'do'} & set(categories))
                self.assertIn('io_input' if owner in {'AI', 'DI'} else 'io_output', categories)

    def test_packed_integer_data_and_arbitrary_float_are_not_analogue_io(self) -> None:
        ev = Evidence()
        ev.entity('Module', 'ModuleType', 'module_input_tag')
        ev.data('Module', [('Data', 'DINT', '1'), ('TemperatureAlarm', 'REAL', '1.5')])
        for suffix in ('.Data', '.Data.0', '.TemperatureAlarm'):
            ev.instruction(suffix, 'MOV', [('Module', suffix, 'read')], 'data_transfer')
        for row in ev.result()['groups']:
            self.assertFalse({'ai', 'di'} & set(row['category_ids']))

    def test_shared_pid_owner_and_assembly_merge_all_writer_rungs(self) -> None:
        ev = Evidence()
        ev.entity('Loop', 'PID')
        ev.data('Loop', [('SP', 'REAL', '12.5'), ('KP', 'REAL', '1.2')])
        ids = [ev.instruction(f'r{i}', 'PID', [('Loop', '', 'read_write')], 'pid_control') for i in (1, 2)]
        for instruction in ids:
            ev.report['pid']['occurrences'].append({'id': instruction, 'rung_id': instruction.split('-')[0],
                'backing_owner_id': 'Loop', 'operand_ids': [instruction + '-o0'], 'storage_status': 'linked'})
        ev.report['relationships']['addresses'] = [{'id': 'address-loop', 'target_id': 'Loop', 'suffix': ''}]
        ev.report['engineering_assemblies']['memberships'] = [{'group_id': 'address-loop', 'instruction_id': ids[0],
            'rung_id': 'r1', 'context_flags': ['competing_writers']}]
        result = ev.result()
        matches = [row for row in result['groups'] if row['anchor_id'] == 'Loop' and not row['address_suffix']]
        self.assertEqual(len(matches), 1)
        group = matches[0]
        self.assertEqual(set(group['rung_ids']), {'r1', 'r2'})
        self.assertTrue(set(ids).issubset(group['member_ids']))
        self.assertEqual({row['name']: row['value'] for row in group['parameters'] if row.get('evidence_id')}, {'.SP': '12.5', '.KP': '1.2'})
        self.assertTrue(any('Multiple source writers' in note for note in group['limitations']))
        self.assertEqual(len({row['id'] for row in result['groups']}), len(result['groups']))

    def test_nested_timers_remain_separate_and_have_consumer_rungs(self) -> None:
        ev = Evidence()
        ev.entity('UnitState', 'StateStructure')
        for suffix in ('.FirstTimer', '.SecondTimer'):
            producer = ev.instruction(suffix, 'TON', [('UnitState', suffix, 'read_write')], 'timer_counter')
            consumer = ev.instruction(suffix + 'Read', 'XIC', [('UnitState', suffix + '.DN', 'read')], 'boolean_condition')
            ev.report['stateful_objects']['objects'].append({'target_id': 'UnitState', 'suffix': suffix,
                'family': 'timer', 'producer_ids': [producer], 'reset_ids': [], 'type_conflict': False})
        result = ev.result()
        for suffix in ('.FirstTimer', '.SecondTimer'):
            group = address(result, 'UnitState', suffix)
            self.assertIn('timer', group['category_ids'])
            self.assertEqual(set(group['rung_ids']), {suffix, suffix + 'Read'})
        self.assertNotEqual(address(result, 'UnitState', '.FirstTimer')['id'], address(result, 'UnitState', '.SecondTimer')['id'])

    def test_multifunction_same_destination_and_latches_keep_limits(self) -> None:
        ev = Evidence()
        ev.entity('Result', 'BOOL')
        ev.instruction('one', 'OTL', [('Result', '', 'write')], 'boolean_output')
        ev.instruction('two', 'MOV', [('Result', '', 'write')], 'data_transfer')
        group = address(ev.result(), 'Result')
        self.assertEqual(set(group['category_ids']), {'dc', 'data_transfer'})
        self.assertTrue(any('Latched' in note for note in group['limitations']))

    def test_platform_logic_is_investigate_and_never_excluded(self) -> None:
        ev = Evidence()
        ev.entity('ModuleConfig', 'Config', 'module_config_tag')
        ev.entity('FaultStatus', 'DINT')
        ev.instruction('r1', 'GSV', [('FaultStatus', '', 'write')], 'communication_system')
        ev.instruction('r2', 'JMP', [], 'control_flow')
        result = ev.result()
        status = address(result, 'FaultStatus')
        self.assertEqual(set(status['category_ids']), {'communication', 'platform'})
        self.assertEqual(status['migration_hint'], 'investigate')
        self.assertEqual(address(result, 'ModuleConfig')['migration_hint'], 'investigate')
        self.assertTrue(any(row['anchor_id'] == 'r2' and 'platform' in row['category_ids'] for row in result['groups']))
        self.assertTrue(all(row['migration_hint'] in {'retain', 'investigate'} for row in result['groups']))

    def test_unknown_blocks_and_wording_are_explicit_unconfirmed_candidates(self) -> None:
        ev = Evidence()
        block = ev.instruction('r1', 'InventedCustomBlock', [], 'unknown')
        ev.analysis['candidates'].append({'rung_id': 'r1', 'basis': 'text_hint', 'category': 'alarm', 'evidence_ids': ['r1']})
        group = address(ev.result(), 'r1')
        self.assertEqual(set(group['category_ids']), {'alarm', 'unknown'})
        self.assertIn(block, group['member_ids'])
        self.assertTrue(any('do not establish alarm consequence' in text for text in group['limitations']))

    def test_linked_input_does_not_hide_alarm_or_unknown_instruction_function(self) -> None:
        ev = Evidence()
        ev.entity('Input')
        alarm = ev.instruction('alarm', 'ALMD', [('Input', '', 'read')], 'alarm')
        unknown = ev.instruction('mystery', 'Mystery', [('Input', '', 'unknown')], 'unknown')
        result = ev.result()
        alarm_group = address(result, 'alarm')
        self.assertIn('alarm', alarm_group['category_ids'])
        self.assertIn(alarm, alarm_group['member_ids'])
        self.assertIn(unknown, address(result, 'mystery')['member_ids'])

    def test_counter_fallback_is_not_mislabeled_timer(self) -> None:
        ev = Evidence()
        instruction = ev.instruction('r1', 'CTU', [], 'timer_counter')
        ev.analysis['candidates'].append({'rung_id': 'r1', 'category': 'timer_counter',
            'basis': 'instruction_signature', 'evidence_ids': [instruction]})
        self.assertEqual(address(ev.result(), 'r1')['category_ids'], ['counter'])

    def test_aoi_parameters_expose_declaration_fields_and_source_links(self) -> None:
        ev = Evidence()
        ev.entity('Custom', '', 'aoi')
        ev.entity('Setpoint', 'REAL', 'aoi_parameter', Usage='Input', Required='true')
        ev.inventory['entities'][-1]['parent_id'] = 'Custom'
        group = address(ev.result(), 'Custom')
        parameters = {row['name']: row for row in group['parameters']}
        self.assertEqual(parameters['Setpoint.Usage']['value'], 'Input')
        self.assertEqual(parameters['Setpoint.DataType']['source_id'], 'Setpoint')
        self.assertIn('Setpoint', group['member_ids'])

    def test_snapshot_guard_immutability_and_deterministic_group_identity(self) -> None:
        ev = Evidence()
        ev.entity('Result', 'REAL')
        ev.instruction('r1', 'CPT', [('Result', '', 'write')], 'calculation')
        original = deepcopy((ev.inventory, ev.analysis, ev.report))
        first = ev.result()
        self.assertEqual(first, ev.result())
        self.assertEqual(original, (ev.inventory, ev.analysis, ev.report))
        ev.report['access']['snapshot'] = {'id': 'different-snapshot'}
        with self.assertRaisesRegex(ValueError, 'snapshot'):
            ev.result()

    def test_limits_are_explicit_and_do_not_mutate_source(self) -> None:
        ev = Evidence()
        ev.entity('Settings', 'Structure')
        ev.data('Settings', [('One', 'REAL', '1'), ('Two', 'REAL', '2'), ('Three', 'REAL', '3')])
        ev.entity('Other', 'REAL')
        ev.instruction('r1', 'CPT', [('Other', '', 'write')], 'calculation')
        with patch('plc_workbench.workspace_classification.MAX_GROUPS', 1), patch('plc_workbench.workspace_classification.MAX_PARAMETERS_PER_GROUP', 2):
            result = ev.result()
        self.assertEqual(len(result['groups']), 1)
        self.assertTrue(result['coverage']['truncated'])
        self.assertEqual(len(result['groups'][0]['parameters']), 2)
        self.assertTrue(any('truncated' in text for text in result['groups'][0]['limitations']))
        self.assertEqual(len(ev.report['tag_data']['elements']), 4)

    def test_real_saved_evidence_shapes(self) -> None:
        from plc_workbench.access import analyze_access
        from plc_workbench.calculations import analyze_calculations
        from plc_workbench.references import analyze_references
        from plc_workbench.rung_analysis import analyze_rungs
        from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
        from plc_workbench.tag_data import analyze_tag_data
        snapshot = snapshot_from_bytes(b'''<RSLogix5000Content><Controller Name="Invented"><Tags>
          <Tag Name="AnalogResult" TagType="Base" DataType="REAL"/>
          <Tag Name="BooleanResult" TagType="Base" DataType="BOOL"/>
          </Tags><Programs><Program Name="P"><Routines><Routine Name="R" Type="RLL"><RLLContent>
          <Rung Number="0" Type="N"><Text>CPT(AnalogResult,1+2);</Text></Rung>
          <Rung Number="1" Type="N"><Text>OTE(BooleanResult);</Text></Rung>
          </RLLContent></Routine></Routines></Program></Programs></Controller></RSLogix5000Content>''')
        inventory = analyze_snapshot(snapshot)
        references = analyze_references(inventory)
        calculations = analyze_calculations(snapshot, inventory, references)
        access = analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
        analysis = analyze_rungs(snapshot, inventory, references, access, calculations)
        result = build_classification(inventory.to_dict(), analysis.to_dict(),
            {'access': access.to_dict(), 'tag_data': analyze_tag_data(snapshot, inventory).to_dict()}, source=snapshot.data)
        names = {row['name']: row for row in result['groups']}
        self.assertIn('ac', names['AnalogResult']['category_ids'])
        self.assertIn('dc', names['BooleanResult']['category_ids'])
        self.assertEqual(result['coverage']['represented_rungs'], 2)

    def test_foreign_owners_aliases_scopes_and_data_never_prove_analogue_types(self) -> None:
        from plc_workbench.access import analyze_access
        from plc_workbench.calculations import analyze_calculations
        from plc_workbench.references import analyze_references
        from plc_workbench.rung_analysis import analyze_rungs
        from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
        from plc_workbench.tag_data import analyze_tag_data
        cases = [
            ('<Tag Name="Out" DataType="Custom"><Data Format="Decorated"><Structure DataType="Custom"><StructureMember Name="Nested" DataType="First"><DataValueMember Name="Value" DataType="REAL" Value="2"/></StructureMember><StructureMember Name="Nested" DataType="Second"/></Structure></Data></Tag>', 'Out.Nested.Value', 'Program', 'Text'),
            ('<Tag Name="Out" DataType="Custom"><Data Format="Decorated"><Structure DataType="Custom"><DataValueMember Name="Value" DataType="REAL" Value="2"/></Structure><Structure DataType="Custom"/></Data></Tag>', 'Out.Value', 'Program', 'Text'),
            ('<Tag Name="Out" DataType="Custom"><Data Format="Decorated"><Structure DataType="Custom"><DataValueMember Name="Value" DataType="REAL" Value="2"/></Structure></Data><Data Format="Decorated"><Structure DataType="Custom"/></Data></Tag>', 'Out.Value', 'Program', 'Text'),
            ('<x:Tag Name="Out" DataType="REAL"/>', 'Out', 'Program', 'Text'),
            ('<Tag Name="Out" x:DataType="REAL"/>', 'Out', 'Program', 'Text'),
            ('<Tag Name="Out" DataType="REAL"/><Tag Name="Alias" TagType="Alias" x:AliasFor="Out"/>', 'Alias', 'Program', 'Text'),
            ('<Tag Name="Out" DataType="REAL"/>', 'Out', 'x:Program', 'Text'),
            ('<Tag Name="Out" DataType="REAL"/>', 'Out', 'Program', 'x:Text'),
            ('<Tag Name="Out" DataType="Custom"><x:Data Format="Decorated"><x:Structure DataType="Custom"><x:DataValueMember Name="Value" DataType="REAL" Value="2"/></x:Structure></x:Data></Tag>', 'Out.Value', 'Program', 'Text'),
        ]
        for tags, destination, program, text in cases:
            with self.subTest(tags=tags, program=program, text=text):
                xml = f'<RSLogix5000Content xmlns:x="urn:unsupported"><Controller Name="Invented"><Tags>{tags}</Tags><Programs><{program} Name="P"><Routines><Routine Name="R" Type="RLL"><RLLContent><Rung Number="0" Type="N"><{text}>CPT({destination},1+2);</{text}></Rung></RLLContent></Routine></Routines></{program}></Programs></Controller></RSLogix5000Content>'
                snapshot = snapshot_from_bytes(xml.encode())
                inventory = analyze_snapshot(snapshot)
                references = analyze_references(inventory)
                calculations = analyze_calculations(snapshot, inventory, references)
                access = analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
                analysis = analyze_rungs(snapshot, inventory, references, access, calculations)
                report = {'access': access.to_dict(), 'tag_data': analyze_tag_data(snapshot, inventory).to_dict()}
                result = build_classification(inventory.to_dict(), analysis.to_dict(), report, source=snapshot.data)
                self.assertNotIn('ac', {cat for group in result['groups'] for cat in group['category_ids']})
                self.assertEqual(result['coverage']['represented_rungs'], 1)
                self.assertTrue(any(group['limitations'] for group in result['groups']))
                with self.assertRaisesRegex(ValueError, 'snapshot'):
                    build_classification(inventory.to_dict(), analysis.to_dict(), report, source=b'<different/>')

    def test_pid_namespace_rejection_keeps_instruction_separate_from_owner(self) -> None:
        ev = Evidence()
        ev.entity('Loop', 'REAL')
        instruction = ev.instruction('r1', 'PID', [('Loop', '', 'read_write')], 'pid_control')
        ev.report['pid']['occurrences'].append({'id': instruction, 'rung_id': 'r1',
            'backing_owner_id': 'Loop', 'operand_ids': [instruction + '-o0'],
            'storage_status': 'binding_namespace_unsupported'})
        result = ev.result()
        group = address(result, instruction)
        self.assertIn('pid', group['category_ids'])
        self.assertNotIn('Loop', group['member_ids'])
        self.assertTrue(any('association is unresolved' in note for note in group['limitations']))


if __name__ == '__main__':
    unittest.main()
