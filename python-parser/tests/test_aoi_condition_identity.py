"""Invented complete AOIs prove only a narrowly bounded default EnableOut rule."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch

from plc_workbench.conditions import (
    AOI_BODY_OPCODES, AOI_IDENTITY_STATUSES, GSV_SIGNATURE_STATUSES, ConditionError, MAX_RECORDS,
    analyze_conditions, render_conditions_json, validate_conditions,
)
from plc_workbench.condition_summary import (
    ConditionSummaryError, MAX_REPORT_V4_BYTES, build_condition_summary,
    render_condition_summary, validate_condition_summary,
)
from plc_workbench.source import SourceError
from test_aoi_body_context import document
from test_custom_instruction_context import routine
from test_output_conditions import capture_xml, current, LEGACY_TEXTS


PARAMETERS = (
    '<Parameter Name="EnableIn" DataType="BOOL" Usage="Input" Required="false" Visible="false"/>'
    '<Parameter Name="EnableOut" DataType="BOOL" Usage="Output" Required="false" Visible="false"/>'
    '<Parameter Name="Input" DataType="DINT" Usage="Input" Required="false" Visible="false"/>'
    '<Parameter Name="Output" DataType="DINT" Usage="Output" Required="false" Visible="false"/>'
)


def xml(**kwargs):
    values = {'body': 'MOV(Input,Output)CPT(Local,Input+Input);', 'parameters': PARAMETERS,
              'calls': 'Widget(Instance)OTE(Coil);', 'tags': '<Tag Name="Coil" DataType="BOOL"/>'}
    values.update(kwargs)
    return ('<RSLogix5000Content>' + document(**values) + '</RSLogix5000Content>').encode()


def capture(source=None, **kwargs):
    inputs = capture_xml(xml(**kwargs) if source is None else source)[:-1]
    return *inputs, analyze_conditions(*inputs, schema_version=5)


def proofs(result):
    return [row for row in result.nodes if 'aoi_identity_status' in row]


class AoiConditionIdentityTests(unittest.TestCase):
    def assert_status(self, status, source=None, **kwargs):
        inputs = capture(source, **kwargs)
        calls = proofs(inputs[-1])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['aoi_identity_status'], status)
        self.assertEqual(calls[0]['kind'], 'pass_through' if status == 'modeled' else 'opaque_transfer')
        self.assertEqual(inputs[-1].coverage['aoi_identity_statuses'][status], 1)
        self.assertEqual(inputs[-1].outputs[-1]['guard_status'], 'modeled' if status == 'modeled' else 'opaque')
        validate_condition_summary(build_condition_summary(*inputs))
        return inputs

    def test_scalar_arithmetic_body_retains_call_and_private_proof(self):
        inputs = self.assert_status('modeled')
        result = inputs[-1]
        proof = proofs(result)[0]
        self.assertEqual((proof['aoi_checked_instructions'], proof['aoi_checked_writes']), (2, 2))
        self.assertTrue(all(proof[key] for key in ('aoi_declaration_id', 'aoi_instance_id',
                                                 'aoi_logic_id', 'aoi_enableout_id')))
        self.assertEqual(len(proof['child_ids']), 1)
        self.assertEqual(result.coverage['passthrough_opcodes']['custom'], 1)
        self.assertEqual(result.coverage['opaque_opcodes']['withheld'], 0)
        report = build_condition_summary(*inputs)
        self.assertEqual(set(report['coverage']['aoi_identity_statuses']), AOI_IDENTITY_STATUSES)
        rendered = render_condition_summary(report)
        for source in ('Widget', 'Instance', 'Input+Input', 'aoi_declaration_id', 'condition_node_'):
            self.assertNotIn(source, rendered)
        validate_conditions(*inputs)

    def test_each_allowed_arithmetic_write_is_own_scalar_and_scoped(self):
        blocks = {'ABS': 'ABS(Input,Output)', 'ADD': 'ADD(Input,1,Output)', 'CLR': 'CLR(Output)',
                  'CPT': 'CPT(Output,Input+1)', 'DIV': 'DIV(Input,1,Output)', 'LN': 'LN(Input,Output)',
                  'MOV': 'MOV(Input,Output)', 'MUL': 'MUL(Input,1,Output)', 'SQR': 'SQR(Input,Output)',
                  'SUB': 'SUB(Input,1,Output)'}
        self.assertEqual(set(blocks), AOI_BODY_OPCODES)
        for opcode, block in blocks.items():
            with self.subTest(opcode=opcode):
                self.assert_status('modeled', body=block + ';')
        # A same-named controller tag cannot redirect a bound AOI local write.
        self.assert_status('modeled', tags='<Tag Name="Output" DataType="Widget"/>'
                           '<Tag Name="Coil" DataType="BOOL"/>')

    def test_enableout_override_and_enablein_write_never_propagate(self):
        for body in ('MOV(1,EnableOut);', 'OTE(EnableOut);', 'CPT(EnableOut,Input);'):
            with self.subTest(body=body):
                self.assert_status('explicit_override', body=body)
        self.assert_status('write_unqualified', body='MOV(1,EnableIn);')

    def test_unbound_alias_array_member_and_foreign_reads_or_writes_fail_closed(self):
        for body in ('MOV(Input,Missing);', 'MOV(Input,Output.0);', 'MOV(Input,Local[0]);',
                     'MOV(Missing,Output);', 'CPT(Output,Input+Missing);', 'MOV(Input);'):
            with self.subTest(body=body):
                self.assert_status('instruction_unsupported' if body == 'MOV(Input);' else 'write_unqualified', body=body)
        for local in ('<LocalTag Name="Local" DataType="DINT" Dimensions="2"/>',
                      '<LocalTag Name="Local" DataType="Unknown"/>',
                      '<LocalTag Name="Local" DataType="DINT" AliasFor="Output"/>'):
            with self.subTest(local=local):
                self.assert_status('parameter_unqualified', locals=local)

    def test_predicates_nested_calls_state_and_bulk_operations_are_not_admitted_by_roles(self):
        for body in ('XIC(Input)MOV(Input,Output);', 'COP(Input,Output,1);', 'JSR(R,0);',
                     'SBR(Input);', 'RET();', 'SFR(R,S);', 'Widget(Local);', 'TON(Local,?,?);'):
            with self.subTest(body=body):
                result = capture(body=body)[-1]
                outer = [p for p in proofs(result) if p['aoi_instance_id']]
                self.assertEqual(outer[0]['aoi_identity_status'], 'instruction_unsupported')
                self.assertEqual(result.outputs[-1]['guard_status'], 'opaque')

    def test_definition_uniqueness_instance_type_shape_alias_and_call_arity(self):
        source = xml()
        definition = source[source.index(b'<AddOnInstructionDefinition '):source.index(b'</AddOnInstructionDefinition>') + len(b'</AddOnInstructionDefinition>')]
        self.assert_status('definition_unavailable', source.replace(b'</AddOnInstructionDefinitions>', definition + b'</AddOnInstructionDefinitions>'))
        # The source parser rejects sibling expanded-name collisions before any
        # provider can select the ordinary declaration over its foreign twin.
        with self.assertRaises(SourceError):
            capture(source.replace(b'</AddOnInstructionDefinitions>',
                    definition.replace(b'<AddOnInstructionDefinition ', b'<AddOnInstructionDefinition xmlns="urn:foreign" ')
                    + b'</AddOnInstructionDefinitions>'))
        self.assert_status('definition_unavailable', source.replace(b'<Tags>',
                           b'<DataTypes><DataType Name="Widget"/></DataTypes><Tags>', 1))
        self.assert_status('parameter_unqualified', source.replace(b'<Tags>',
                           b'<DataTypes><DataType Name="DINT"/></DataTypes><Tags>', 1))
        self.assert_status('definition_unavailable', source.replace(b'Widget(Instance)', b'Absent(Instance)'))
        for old, new in ((b'DataType="Widget"', b'DataType="Other"'),
                         (b'DataType="Widget"', b'DataType="Widget" Dimensions="2"'),
                         (b'DataType="Widget"', b'DataType="Widget" AliasFor="Other"')):
            with self.subTest(new=new):
                self.assert_status('instance_unqualified', source.replace(old, new))
        for call in ('Widget()', 'Widget(Instance,Input)', 'Widget(Instance.Output)', 'Widget(Instance[0])'):
            with self.subTest(call=call):
                self.assert_status('call_unqualified', calls=call + 'OTE(Coil);')
        self.assert_status('instance_unqualified', calls='Widget(Missing)OTE(Coil);')
        # Unicode lowercase lookalikes must not bind an ASCII type spelling.
        kelvin_source = source.replace(b'Widget', b'KWidget')
        self.assert_status('definition_unavailable', kelvin_source.replace(
            b'<AddOnInstructionDefinition Name="KWidget"', '<AddOnInstructionDefinition Name="\u212aWidget"'.encode()))
        self.assert_status('instance_unqualified', kelvin_source.replace(
            b'DataType="KWidget"', 'DataType="\u212aWidget"'.encode()))

    def test_enable_parameter_signature_and_unique_scalar_symbols_required(self):
        mutations = (
            PARAMETERS.replace('Name="EnableOut"', 'Name="Other"'),
            PARAMETERS.replace('Name="EnableOut" DataType="BOOL"', 'Name="EnableOut" DataType="DINT"'),
            PARAMETERS.replace('Usage="Output"', 'Usage="InOut"', 1),
            PARAMETERS.replace('Required="false"', 'Required="true"', 1),
            PARAMETERS.replace('Visible="false"', 'Visible="true"', 1),
            PARAMETERS + '<Parameter Name="INPUT" DataType="DINT" Usage="Input" Required="false" Visible="false"/>',
            PARAMETERS.replace('Name="Input"', 'Name="Input" AliasFor="Local"'),
        )
        for parameters in mutations:
            with self.subTest(parameters=parameters):
                self.assert_status('parameter_unqualified', parameters=parameters)
        self.assert_status('parameter_unqualified', locals='<LocalTag Name="EnableOut" DataType="BOOL"/>')
        self.assert_status('parameter_unqualified', parameters=PARAMETERS.replace('DataType="DINT"', 'DataType="LINT"'))
        self.assert_status('modeled', locals='<LocalTag Name="Local" DataType="LINT"/>')

    def test_namespace_protection_and_complete_body_envelopes_are_required(self):
        source = xml()
        for old, new in (
            (b'<AddOnInstructionDefinition ', b'<AddOnInstructionDefinition xmlns:v="urn:foreign" v:Other="x" '),
            (b'<LocalTags>', b'<LocalTags xmlns="urn:foreign">'),
            (b'<Text>', b'<Text xmlns="urn:foreign">'),
        ):
            with self.subTest(new=new):
                self.assert_status('source_unqualified', source.replace(old, new))
        self.assert_status('modeled', source.replace(b'<RSLogix5000Content>', b'<RSLogix5000Content xmlns="urn:logix">'))
        self.assert_status('protected', definition_attributes='Protected="true"')
        self.assert_status('protected', definition_attributes='Protected="false"')
        self.assert_status('protected', source.replace(b'<LocalTags>', b'<LocalTags IsEncrypted="false">'))
        for attributes in ('SourceKey="key"', 'ExecuteEnableInFalse="true"', 'ExecutePrescan="true"'):
            with self.subTest(attributes=attributes):
                self.assert_status('protected' if attributes.startswith('SourceKey') else 'body_unqualified',
                                   definition_attributes=attributes)
        for extra in (routine('MOV(Input,Output);', 'Logic'), routine('MOV(Input,Output);', 'EnableInFalse')):
            self.assert_status('body_unqualified', extra_routines=extra)
        for old, new in ((b'Name="Logic" Type="RLL"', b'Name="Logic" Type="ST"'),
                         (b'<RLLContent>', b'<RLLContent><Unknown/>'),
                         (b'<Text>', b'<Text><Unknown/>'),
                         (b'MOV(Input,Output)', b'MOV(Input,Output'),
                         (b'</Routines></AddOnInstructionDefinition>', b'</Routines><Unknown/></AddOnInstructionDefinition>')):
            with self.subTest(new=new):
                self.assert_status('body_unqualified', source.replace(old, new, 1))

    def test_repeated_calls_overlap_guards_without_expanding_private_body(self):
        inputs = capture(calls='[Widget(Instance),Widget(Instance)]Widget(Instance)OTE(Coil);')
        result = inputs[-1]
        self.assertEqual(len(proofs(result)), 3)
        self.assertEqual(result.coverage['aoi_identity_statuses']['modeled'], 3)
        self.assertTrue(all(p['aoi_checked_instructions'] == 2 for p in proofs(result)))
        self.assertEqual(len({p['aoi_logic_id'] for p in proofs(result)}), 1)
        self.assertEqual(result.outputs[-1]['guard_status'], 'modeled')
        validate_condition_summary(build_condition_summary(*inputs))

    def test_custom_partition_and_builtin_control_flow_are_independent(self):
        inputs = capture(calls='Widget(Instance)Absent(Instance)SBR(Input)JSR(R,0)RET()SFR(R,S)OTE(Coil);')
        result = inputs[-1]
        self.assertEqual(result.coverage['aoi_identity_statuses']['modeled'], 1)
        self.assertEqual(result.coverage['aoi_identity_statuses']['definition_unavailable'], 1)
        self.assertEqual(result.coverage['opaque_opcodes']['withheld'], 1)
        self.assertEqual(result.coverage['opaque_guard_opcodes']['withheld'], 1)
        self.assertEqual({opcode: result.coverage['opaque_opcodes'][opcode] for opcode in ('SBR', 'JSR', 'RET', 'SFR')},
                         {'SBR': 1, 'JSR': 1, 'RET': 1, 'SFR': 1})
        report = build_condition_summary(*inputs)
        report['coverage']['aoi_identity_statuses']['definition_unavailable'] = 0
        with self.assertRaises(ConditionSummaryError):
            validate_condition_summary(report)

    def test_replay_rejects_forged_proofs_and_closed_summary_populations(self):
        inputs = capture()
        for key, value in (('aoi_identity_status', 'explicit_override'), ('aoi_checked_writes', 0),
                           ('aoi_logic_id', None), ('aoi_instance_id', 'private-forgery')):
            changed = deepcopy(inputs[-1])
            proofs(changed)[0][key] = value
            with self.subTest(key=key), self.assertRaises(ConditionError):
                validate_conditions(*inputs[:-1], changed)
        for version in (1, 2, 3, 4):
            with self.subTest(version=version), self.assertRaises(ConditionError):
                validate_conditions(*inputs[:-1], replace(inputs[-1], schema_version=version,
                                                         analyzer_version=f'condition-analysis-{version}'))
        report = build_condition_summary(*inputs)
        for key, value in (('modeled', 0), ('explicit_override', 1), ('PrivateName', 0), ('modeled', True)):
            changed = deepcopy(report)
            changed['coverage']['aoi_identity_statuses'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ConditionSummaryError):
                validate_condition_summary(changed)

    def test_caps_cover_private_proofs_and_maximum_public_integer_widths(self):
        inputs = capture()
        for limit in ('MAX_CONDITION_BYTES', 'MAX_RECORDS', 'MAX_EVIDENCE_IDS'):
            with self.subTest(limit=limit), patch(f'plc_workbench.conditions.{limit}', 1):
                with self.assertRaises(ConditionError):
                    analyze_conditions(*inputs[:-1], schema_version=5)
        rendered = render_conditions_json(inputs[-1])
        with patch('plc_workbench.conditions.MAX_CONDITION_BYTES', len(rendered)):
            self.assertEqual(render_conditions_json(analyze_conditions(*inputs[:-1], schema_version=5)), rendered)
        with patch('plc_workbench.conditions.MAX_CONDITION_BYTES', len(rendered) - 1):
            with self.assertRaises(ConditionError):
                analyze_conditions(*inputs[:-1], schema_version=5)
        rows = inputs[-1].nodes + inputs[-1].outputs + inputs[-1].rungs
        identifiers = sum(len(value) if type(value) is list else int(value is not None)
                          for row in rows for key, value in row.items()
                          if key == 'id' or key.endswith('_id') or key.endswith('_ids'))
        with patch('plc_workbench.conditions.MAX_EVIDENCE_IDS', identifiers):
            analyze_conditions(*inputs[:-1], schema_version=5)
        with patch('plc_workbench.conditions.MAX_EVIDENCE_IDS', identifiers - 1):
            with self.assertRaises(ConditionError):
                analyze_conditions(*inputs[:-1], schema_version=5)
        report = build_condition_summary(*inputs)
        with patch('plc_workbench.condition_summary.MAX_REPORT_V4_BYTES', 1):
            with self.assertRaises(ConditionSummaryError):
                render_condition_summary(report)
        widest = deepcopy(report)
        widest['tool_revision'] = {'commit': 'f' * 40, 'worktree': 'modified'}
        for key, value in widest['coverage'].items():
            widest['coverage'][key] = ({name: MAX_RECORDS for name in value} if isinstance(value, dict)
                                      else 2_000_000 if key == 'branch_legs' else MAX_RECORDS)
        self.assertLessEqual(len(json.dumps(widest, sort_keys=True, indent=1) + '\n'), MAX_REPORT_V4_BYTES)

    def test_gsv_diagnostic_explains_existing_signature_rules_without_expansion(self):
        cases = {
            'modeled': 'GSV(WallClockTime,,DateTime,Coil)',
            'argument_count': 'GSV(WallClockTime,Coil)',
            'empty_field': 'GSV(,,DateTime,Coil)',
            'class_token': 'GSV(WallClockTime.0,,DateTime,Coil)',
            'instance_syntax': 'GSV(WallClockTime,1,DateTime,Coil)',
            'attribute_token': 'GSV(WallClockTime,,DateTime.0,Coil)',
            'destination_syntax': 'GSV(WallClockTime,,DateTime,1)',
        }
        self.assertEqual(set(cases) | {'namespace'}, GSV_SIGNATURE_STATUSES)
        for status, block in cases.items():
            with self.subTest(status=status):
                inputs = capture(calls=block + 'OTE(Coil);')
                result = inputs[-1]
                self.assertEqual(result.coverage['gsv_signature_statuses'][status], 1)
                rows = [row for row in result.nodes if 'gsv_signature_status' in row]
                self.assertEqual(rows[0]['gsv_signature_status'], status)
                self.assertEqual(rows[0]['kind'], 'pass_through' if status == 'modeled' else 'opaque_transfer')
                validate_condition_summary(build_condition_summary(*inputs))
        inputs = capture(xml(calls=cases['modeled'] + 'OTE(Coil);').replace(
            b'<Program Name="Main"', b'<Program xmlns:v="urn:foreign" v:Meaning="other" Name="Main"'))
        self.assertEqual(inputs[-1].coverage['gsv_signature_statuses']['namespace'], 1)
        report = build_condition_summary(*inputs)
        report['coverage']['gsv_signature_statuses']['namespace'] = 0
        with self.assertRaises(ConditionSummaryError):
            validate_condition_summary(report)
        good = capture(calls=cases['modeled'] + 'OTE(Coil);')
        forged = deepcopy(good[-1])
        next(row for row in forged.nodes if 'gsv_signature_status' in row)['gsv_signature_status'] = 'class_token'
        with self.assertRaises(ConditionError):
            validate_conditions(*good[:-1], forged)

    def test_condition4_payloads_remain_frozen_and_default_stays_one(self):
        inputs = current(LEGACY_TEXTS)
        rendered = render_conditions_json(inputs[-1]), render_condition_summary(build_condition_summary(*inputs))
        self.assertEqual(tuple(hashlib.sha256(value.encode()).hexdigest() for value in rendered),
                         ('ac608e61105926a2f2e2dc49a79a632bda1f720ff012fe06df47062d4a4fc67c',
                          '2f44ab885fedeb931dc1ea16b2a929e88bbf06a4b4a94fe5202c31876b3ed323'))
        self.assertEqual(analyze_conditions(*inputs[:-1]).schema_version, 1)
        self.assertNotIn('aoi_identity_statuses', inputs[-1].coverage)


if __name__ == '__main__':
    unittest.main()
