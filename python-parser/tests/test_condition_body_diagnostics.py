"""Invented metadata and rejected-instance forms for the condition6 boundary."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch

from plc_workbench.conditions import (
    AOI_BODY_GAP_REASONS, GSV_INSTANCE_GAP_FORMS, MAX_RECORDS, ConditionError,
    analyze_conditions, render_conditions_json, validate_conditions,
)
from plc_workbench.condition_summary import (
    MAX_REPORT_V4_BYTES, ConditionSummaryError, build_condition_summary,
    render_condition_summary, validate_condition_summary,
)
from test_aoi_condition_identity import capture as capture5, proofs, xml
from test_custom_instruction_context import routine


def capture(source=None, **kwargs):
    inputs = capture5(source, **kwargs)[:-1]
    return *inputs, analyze_conditions(*inputs, schema_version=6)


def metadata_source(**kwargs):
    return xml(**kwargs).replace(b'<Parameters>', b'<RevisionNote>invented</RevisionNote>'
        b'<AdditionalHelpText>invented</AdditionalHelpText><Parameters>', 1)


class ConditionBodyDiagnosticTests(unittest.TestCase):
    def test_unique_leaf_metadata_admits_only_the_preexisting_complete_body_proof(self):
        source = metadata_source().replace(b'<RLLContent>', b'<Description>invented</Description><RLLContent>', 1)
        inputs = capture(source)
        proof = proofs(inputs[-1])[0]
        self.assertEqual(proof['aoi_identity_status'], 'modeled')
        self.assertIsNone(proof['aoi_body_gap_reason'])
        self.assertEqual((proof['aoi_checked_instructions'], proof['aoi_checked_writes']), (2, 2))
        self.assertEqual(inputs[-1].outputs[-1]['guard_status'], 'modeled')
        validate_conditions(*inputs)
        report = build_condition_summary(*inputs)
        self.assertEqual(sum(report['coverage']['aoi_body_gap_reasons'].values()), 0)
        rendered = render_condition_summary(report)
        for private in ('invented', 'RevisionNote', 'AdditionalHelpText', 'Widget', 'Instance'):
            self.assertNotIn(private, rendered)
        for body, status in (('MOV(Input,EnableOut);', 'explicit_override'),
                             ('MOV(Input,Missing);', 'write_unqualified'),
                             ('Widget(Local);', 'instruction_unsupported')):
            with self.subTest(body=body):
                outer = [p for p in proofs(capture(metadata_source(body=body))[-1]) if p['aoi_instance_id']]
                self.assertEqual(outer[0]['aoi_identity_status'], status)
                self.assertIsNone(outer[0]['aoi_body_gap_reason'])

    def test_metadata_duplicates_attributes_nested_content_namespaces_and_protection_fail_closed(self):
        source = metadata_source()
        for new, status, gap in (
            (b'<RevisionNote/><RevisionNote>', 'body_unqualified', 'metadata_shape'),
            (b'<RevisionNote Other="value">', 'body_unqualified', 'metadata_shape'),
            (b'<RevisionNote><Unknown/>', 'body_unqualified', 'metadata_shape'),
            (b'<RevisionNote xmlns="urn:foreign">', 'source_unqualified', None),
            (b'<RevisionNote Protected="false">', 'protected', None),
        ):
            with self.subTest(new=new):
                inputs = capture(source.replace(b'<RevisionNote>', new, 1))
                proof = proofs(inputs[-1])[0]
                self.assertEqual((proof['aoi_identity_status'], proof['aoi_body_gap_reason']), (status, gap))
                validate_condition_summary(build_condition_summary(*inputs))
        self.assertEqual(proofs(capture(source.replace(b'<RSLogix5000Content>',
            b'<RSLogix5000Content xmlns="urn:logix">'))[-1])[0]['aoi_identity_status'], 'modeled')

    def test_each_body_gap_has_one_fixed_first_failure_and_no_source_text(self):
        source = xml()
        body_routine = routine('MOV(Input,Output)CPT(Local,Input+Input);', 'Logic').encode()
        mutations = {
            'definition_content': (b'<Parameters>', b'<Unknown/><Parameters>'),
            'metadata_shape': (b'<Parameters>', b'<Description/><Description/><Parameters>'),
            'container_cardinality': (b'<Routines>', b'<Routines/><Routines>'),
            'scan_enabled': (b'Name="Widget" ', b'Name="Widget" ExecutePrescan="true" '),
            'scan_flag_syntax': (b'Name="Widget" ', b'Name="Widget" ExecutePrescan="0" '),
            'container_content': (b'<LocalTags>', b'<LocalTags><Unknown/>'),
            'routine_count': (body_routine, b''),
            'routine_identity': (b'Name="Logic"', b'Name="Other"'),
            'routine_content': (b'<RLLContent>', b'<Unknown/><RLLContent>'),
            'content_shape': (b'<RLLContent>', b'<RLLContent><Unknown/>'),
            'rung_count': (b'<Rung Number="0" Type="N"><Text><![CDATA[MOV(Input,Output)CPT(Local,Input+Input);]]></Text></Rung>', b''),
            'rung_parse': (b'MOV(Input,Output)', b'MOV(Input,Output'),
            'rung_type': (b'Type="N"', b'Type="I"'),
            'rung_content': (b'<Text>', b'<Unknown/><Text>'),
        }
        self.assertEqual(set(mutations), AOI_BODY_GAP_REASONS)
        for reason, (old, new) in mutations.items():
            with self.subTest(reason=reason):
                self.assertIn(old, source)
                inputs = capture(source.replace(old, new, 1))
                proof = proofs(inputs[-1])[0]
                self.assertEqual((proof['aoi_identity_status'], proof['aoi_body_gap_reason']),
                                 ('body_unqualified', reason))
                self.assertEqual(inputs[-1].coverage['aoi_body_gap_reasons'][reason], 1)
                self.assertEqual(sum(inputs[-1].coverage['aoi_body_gap_reasons'].values()), 1)
                validate_condition_summary(build_condition_summary(*inputs))
        # Source order and simultaneous failures cannot produce multiple counts.
        inputs = capture(source.replace(b'<Parameters>', b'<Unknown/><Parameters>', 1)
                         .replace(b'Name="Logic"', b'Name="Other"'))
        self.assertEqual(proofs(inputs[-1])[0]['aoi_body_gap_reason'], 'definition_content')

    def test_repeated_calls_count_occurrences_and_cache_definition_without_expansion(self):
        inputs = capture(xml(calls='Widget(Instance)' * 7 + 'OTE(Coil);')
                         .replace(b'<Parameters>', b'<Unknown/><Parameters>', 1))
        self.assertEqual(inputs[-1].coverage['aoi_body_gap_reasons']['definition_content'], 7)
        self.assertEqual(len({p['aoi_declaration_id'] for p in proofs(inputs[-1])}), 1)
        validate_conditions(*inputs)

    def test_gsv_rejected_instance_forms_are_lexical_and_never_admit_new_signatures(self):
        cases = {'zero_literal': '0', 'other_integer': '-2', 'question_mark': '?',
                 'quoted': '"invented"', 'program_qualified': 'Program:Invented', 'other': '1.5'}
        self.assertEqual(set(cases), GSV_INSTANCE_GAP_FORMS)
        for form, instance in cases.items():
            with self.subTest(form=form):
                inputs = capture(calls=f'GSV(WallClockTime,{instance},DateTime,Coil)OTE(Coil);')
                row = next(r for r in inputs[-1].nodes if 'gsv_signature_status' in r)
                self.assertEqual((row['kind'], row['gsv_signature_status'], row['gsv_instance_gap_form']),
                                 ('opaque_transfer', 'instance_syntax', form))
                self.assertEqual(inputs[-1].coverage['gsv_instance_gap_forms'][form], 1)
                validate_conditions(*inputs)
                validate_condition_summary(build_condition_summary(*inputs))
        # Exact decimal spelling only: these are not silently normalized to 0.
        for instance in ('00', '+0', '-0', '1' * 100):
            inputs = capture(calls=f'GSV(WallClockTime,{instance},DateTime,Coil);')
            self.assertEqual(inputs[-1].coverage['gsv_instance_gap_forms']['other_integer'], 1)

    def test_gsv_prior_signature_gates_and_accepted_instances_have_no_gap_form(self):
        cases = ('GSV(WallClockTime,,DateTime,Coil)', 'GSV(Program,THIS,LastScanTime,Coil)',
                 'GSV(WallClockTime.0,0,DateTime,Coil)', 'GSV(WallClockTime,0)',
                 'GSV(,0,DateTime,Coil)', 'GSV(WallClockTime,,DateTime,1)')
        for block in cases:
            with self.subTest(block=block):
                inputs = capture(calls=block + ';')
                row = next(r for r in inputs[-1].nodes if 'gsv_signature_status' in r)
                self.assertIsNone(row['gsv_instance_gap_form'])
                self.assertEqual(sum(inputs[-1].coverage['gsv_instance_gap_forms'].values()), 0)
                validate_condition_summary(build_condition_summary(*inputs))
        source = xml(calls='GSV(WallClockTime,0,DateTime,Coil);').replace(
            b'<Program Name="Main"', b'<Program xmlns:v="urn:foreign" v:Other="value" Name="Main"')
        inputs = capture(source)
        row = next(r for r in inputs[-1].nodes if 'gsv_signature_status' in r)
        self.assertEqual(row['gsv_signature_status'], 'namespace')
        self.assertIsNone(row['gsv_instance_gap_form'])

    def test_replay_and_public_conservation_reject_forged_details_open_keys_and_versions(self):
        inputs = capture(xml(calls='Widget(Instance)GSV(WallClockTime,0,DateTime,Coil);')
                         .replace(b'<Parameters>', b'<Unknown/><Parameters>', 1))
        for field, value in (('aoi_body_gap_reason', 'rung_type'), ('gsv_instance_gap_form', 'quoted')):
            changed = deepcopy(inputs[-1])
            next(row for row in changed.nodes if field in row)[field] = value
            with self.subTest(field=field), self.assertRaises(ConditionError):
                validate_conditions(*inputs[:-1], changed)
        for version in range(1, 6):
            with self.subTest(version=version), self.assertRaises(ConditionError):
                validate_conditions(*inputs[:-1], replace(inputs[-1], schema_version=version,
                                                         analyzer_version=f'condition-analysis-{version}'))
        report = build_condition_summary(*inputs)
        for name, key in (('aoi_body_gap_reasons', 'definition_content'),
                          ('gsv_instance_gap_forms', 'zero_literal')):
            for target, value in ((key, 0), (key, True), ('invented_source', 0)):
                changed = deepcopy(report)
                changed['coverage'][name][target] = value
                with self.subTest(name=name, target=target, value=value), self.assertRaises(ConditionSummaryError):
                    validate_condition_summary(changed)

    def test_new_fields_are_budgeted_and_maximum_width_remains_within_eight_kib(self):
        inputs = capture(metadata_source(calls='Widget(Instance)GSV(WallClockTime,0,DateTime,Coil);'))
        rendered = render_conditions_json(inputs[-1])
        with patch('plc_workbench.conditions.MAX_CONDITION_BYTES', len(rendered)):
            self.assertEqual(render_conditions_json(analyze_conditions(*inputs[:-1], schema_version=6)), rendered)
        with patch('plc_workbench.conditions.MAX_CONDITION_BYTES', len(rendered) - 1):
            with self.assertRaises(ConditionError): analyze_conditions(*inputs[:-1], schema_version=6)
        for key in ('MAX_RECORDS', 'MAX_EVIDENCE_IDS'):
            with patch(f'plc_workbench.conditions.{key}', 1), self.assertRaises(ConditionError):
                analyze_conditions(*inputs[:-1], schema_version=6)
        report = build_condition_summary(*inputs)
        with patch('plc_workbench.condition_summary.MAX_REPORT_V4_BYTES', 1), self.assertRaises(ConditionSummaryError):
            render_condition_summary(report)
        widest = deepcopy(report)
        widest['status'] = 'complete'
        widest['tool_revision'] = {'commit': 'f' * 40, 'worktree': 'modified'}
        for key, value in widest['coverage'].items():
            widest['coverage'][key] = ({name: MAX_RECORDS for name in value} if isinstance(value, dict)
                                      else 2_000_000 if key == 'branch_legs' else MAX_RECORDS)
        self.assertEqual(len(json.dumps(widest, sort_keys=True, indent=1) + '\n'), 7842)
        self.assertLessEqual(7842, MAX_REPORT_V4_BYTES)

    def test_condition5_payloads_are_frozen_including_metadata_rejection_and_zero_instance(self):
        inputs = capture5(metadata_source(calls='Widget(Instance)GSV(WallClockTime,0,DateTime,Coil)OTE(Coil);'))
        rendered = render_conditions_json(inputs[-1]), render_condition_summary(build_condition_summary(*inputs))
        self.assertEqual(tuple(hashlib.sha256(value.encode()).hexdigest() for value in rendered),
                         ('1fdb19d273c49188de3949bf41efdd4a1d28e0d16d524ba95561cb26589f6c97',
                          '3f633438ad6f9d4be435ab9cd2c34727ce6dbaa9820e874e00f7a0086d01b8c5'))
        self.assertEqual(analyze_conditions(*inputs[:-1]).schema_version, 1)
        self.assertNotIn('aoi_body_gap_reasons', inputs[-1].coverage)


if __name__ == '__main__':
    unittest.main()
