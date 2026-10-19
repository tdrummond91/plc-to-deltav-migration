"""Reviewed built-in output transfers, qualified syntax and closed diagnostics."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch

from plc_workbench.conditions import (
    ConditionError, MAX_RECORDS, OPAQUE_OPCODES, REVIEWED_PASSTHROUGH_OPCODES,
    SOURCE_SIGNATURE_OPCODES, analyze_conditions, render_conditions_json, validate_conditions,
)
from plc_workbench.condition_summary import (
    ConditionSummaryError, MAX_REPORT_V4_BYTES, build_condition_summary,
    render_condition_summary, validate_condition_summary,
)
from test_conditions import capture
from test_stateful_conditions import evaluate_occurrence_graph


EXAMPLES = (
    'MVM(A,1,B)', 'SWPB(A,REVERSE,B)', 'GSV(WallClockTime,,DateTime,A)', 'MSG(A)',
    'PID(A,B,0,C,0,0,0)', 'AVE(A,0,B,T,?,?)',
    'FAL(T,?,?,ALL,B,A+1)', 'SQO(A,1,B,T,?,?)',
)
LEGACY_TEXTS = (
    'XIC(A)[ONS(B),XIO(C)]MOV(A,B)OTE(D);',
    '[MSG(A),MVM(A,1,B),SWPB(A,REVERSE,B),GSV(WallClockTime,,DateTime,A),'
    'PID(A,B,0,C,0,0,0),AVE(A,0,B,T,?,?),FAL(T,?,?,ALL,B,A+1),SQO(A,1,B,T,?,?)]OTL(D);',
    'SFR(R,S)JSR(R,0)RET()SBR(A)DayOfWeek(A);',
)


def current(texts=('MSG(A)OTE(D);',), **kwargs):
    return capture(texts, schema_version=4, **kwargs)


def capture_xml(xml: bytes):
    from plc_workbench.access import analyze_access
    from plc_workbench.calculations import analyze_calculations
    from plc_workbench.references import analyze_references
    from plc_workbench.relationships import analyze_relationships
    from plc_workbench.rung_analysis import analyze_rungs
    from plc_workbench.source import analyze_snapshot, snapshot_from_bytes

    snapshot = snapshot_from_bytes(xml)
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    calculations = analyze_calculations(snapshot, inventory, references)
    access = analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
    rungs = analyze_rungs(snapshot, inventory, references, access, calculations)
    relationships = analyze_relationships(snapshot, inventory, references, access, calculations, rungs)
    inputs = snapshot, inventory, references, access, calculations, rungs, relationships
    return *inputs, analyze_conditions(*inputs, schema_version=4)


class ReviewedOutputConditionTests(unittest.TestCase):
    def test_each_reviewed_output_retains_occurrence_and_normal_boolean_identity(self):
        self.assertEqual({block.split('(')[0] for block in EXAMPLES}, REVIEWED_PASSTHROUGH_OPCODES)
        for block in EXAMPLES:
            with self.subTest(block=block):
                inputs = current((f'XIC(A){block}ONS(C)OTE(D);',))
                result = inputs[-1]
                self.assertEqual(result.coverage['node_kinds']['pass_through'], 1)
                self.assertEqual(result.coverage['node_kinds']['opaque_transfer'], 0)
                transfer = next(row for row in result.nodes if row['kind'] == 'pass_through')
                self.assertEqual(transfer['operand_ids'], inputs[3].instructions[1]['operand_ids'])
                self.assertEqual(transfer['instruction_id'], inputs[3].instructions[1]['id'])
                self.assertTrue(result.outputs[0]['has_stateful'])
                for entry in (False, True):
                    for predicate in (False, True):
                        for stored in (False, True):
                            self.assertEqual(evaluate_occurrence_graph(
                                result, entry=entry, predicates=[predicate], storage_reads=[stored]),
                                [entry and predicate and not stored])
                validate_conditions(*inputs)
                validate_condition_summary(build_condition_summary(*inputs))

    def test_source_only_signature_admission_does_not_rewrite_frozen_access(self):
        inputs = current(tuple(f'{block};' for block in EXAMPLES))
        unsupported = {source.opcode for rung in inputs[1].rungs for source in rung.instructions
                       if next(row for row in inputs[3].instructions if row['id'] == source.id)['status']
                       != 'classified'}
        self.assertEqual(unsupported, SOURCE_SIGNATURE_OPCODES)
        self.assertEqual(inputs[-1].coverage['node_kinds']['pass_through'], 8)
        self.assertEqual(inputs[-1].outputs, [])

    def test_missing_data_bindings_and_symbolic_indices_do_not_invent_guards(self):
        result = current(('MVM(Missing,16#FF,Buffer[Cursor+1])MSG(Other)'
                          'FAL(Control,?,?,INC,Buffer[Cursor],Missing+1)OTE(D);',))[-1]
        self.assertEqual(result.coverage['node_kinds']['pass_through'], 3)
        self.assertEqual(result.outputs[0]['guard_status'], 'modeled')
        self.assertEqual(result.coverage['binding_gap_predicates'], 0)

    def test_bad_arities_empty_fields_selectors_addresses_and_expression_stay_opaque(self):
        invalid = [block[:-1] + ',Extra)' for block in EXAMPLES]
        invalid += ['MVM(A,,B)', 'MVM(A,1,A+B)', 'MSG(1)', 'MSG(A+)',
                    'SWPB(A,PRIVATE_MODE,B)', 'SWPB(A,,B)', 'SWPB(1,WORD,B)',
                    'GSV(,,DateTime,A)', 'GSV(WallClockTime,,Bad+Attribute,A)',
                    'PID(A,B,0,1,0,0,0)', 'PID(A,B,0,C,0,,0)',
                    'AVE(A,3,B,T,?,?)', 'AVE(A,0,B,T,Missing,?)',
                    'SQO(A,1,1,T,?,?)', 'SQO(A,1,B,T,?,Bad)',
                    'FAL(T,?,?,ZERO,B,A+1)', 'FAL(T,?,?,0,B,A+1)',
                    'FAL(T,?,?,2147483648,B,A+1)', 'FAL(T,?,?,ALL,B,A+)',
                    'FAL(T,?,?,ALL,B,UnknownFunction(A))', 'FAL(T,?,A,ALL,B,1)',
                    'MVM(A,1,Buffer[Cursor+])']
        for block in invalid:
            with self.subTest(block=block):
                result = current((f'{block}OTE(D);',))[-1]
                self.assertEqual(result.coverage['node_kinds']['pass_through'], 0)
                self.assertEqual(result.coverage['opaque_reasons']['signature_unresolved'], 1)
                self.assertEqual(result.outputs[0]['guard_status'], 'opaque')

    def test_source_namespace_and_attributes_are_qualified_without_requiring_tag_binding(self):
        original = current()[0].data
        for old, new in (
            (b'<Controller ', b'<Controller xmlns:v="urn:foreign" v:Meaning="Other" '),
            (b'<RLLContent>', b'<RLLContent xmlns="urn:foreign">'),
            (b'<Text>', b'<Text xmlns="urn:foreign">'),
            (b'<Text>', b'<Text xmlns:v="urn:foreign" v:Meaning="other">'),
        ):
            with self.subTest(new=new):
                result = capture_xml(original.replace(old, new))[-1]
                self.assertEqual(result.coverage['opaque_reasons']['source_unqualified'], 1)
                self.assertEqual(result.outputs[0]['guard_status'], 'opaque')
        qualified = capture_xml(original.replace(b'<RSLogix5000Content>',
                                                b'<RSLogix5000Content xmlns="urn:logix">'))[-1]
        self.assertEqual(qualified.coverage['node_kinds']['pass_through'], 1)

    def test_control_flow_and_unknown_calls_remain_distinct_opaque_contributors(self):
        inputs = current(('[JSR(R,0)JSR(R,0),SFR(R,S)]MSG(A)OTE(D)'
                          'PrivatePlantInstruction(A)OTL(D);', 'RET()SBR(A);'))
        result = inputs[-1]
        counts = result.coverage['opaque_opcodes']
        guards = result.coverage['opaque_guard_opcodes']
        self.assertEqual({key: value for key, value in counts.items() if value},
                         {'JSR': 2, 'RET': 1, 'SBR': 1, 'SFR': 1, 'withheld': 1})
        self.assertEqual({key: value for key, value in guards.items() if value},
                         {'JSR': 2, 'SFR': 2, 'withheld': 1})
        self.assertEqual(result.coverage['guard_statuses']['opaque'], 2)
        self.assertGreater(sum(guards.values()), result.coverage['guard_statuses']['opaque'])
        rendered = render_condition_summary(build_condition_summary(*inputs))
        self.assertNotIn('PrivatePlantInstruction', rendered)
        self.assertNotIn('condition_node_', rendered)

    def test_current_output_guard_precedes_its_own_malformed_transfer(self):
        result = current(('OTE(A,B)OTE(D);',))[-1]
        self.assertEqual([row['guard_status'] for row in result.outputs], ['modeled', 'opaque'])
        self.assertEqual(result.coverage['opaque_opcodes']['OTE'], 1)
        self.assertEqual(result.coverage['opaque_guard_opcodes']['OTE'], 1)

    def test_many_shared_prefix_branches_do_not_expand_contributor_counts(self):
        inputs = current(('JSR(R,0)' + '[MSG(A),MVM(A,1,B)]' * 120 + 'OTE(D);',))
        result = inputs[-1]
        self.assertEqual(result.coverage['opaque_guard_opcodes']['JSR'], 1)
        self.assertEqual(result.coverage['opaque_opcodes']['JSR'], 1)
        self.assertEqual(len(result.nodes), 362)
        validate_condition_summary(build_condition_summary(*inputs))

    def test_replay_rejects_forged_diagnostics_signature_and_source_qualification(self):
        inputs = current(('MSG(A)JSR(R,0)OTE(D);',))
        mutations = (
            lambda r: r.coverage['opaque_guard_opcodes'].update(JSR=0),
            lambda r: r.coverage['opaque_opcodes'].update(JSR=2),
            lambda r: r.nodes[1].update(reason='source_unqualified'),
            lambda r: r.nodes[2].update(kind='pass_through', has_opaque=False),
        )
        for mutate in mutations:
            changed = deepcopy(inputs[-1])
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ConditionError):
                validate_conditions(*inputs[:-1], changed)
        with self.assertRaises(ConditionError):
            validate_conditions(*inputs[:-1], replace(inputs[-1], schema_version=3,
                                                     analyzer_version='condition-analysis-3'))

    def test_summary_rejects_open_or_inconsistent_diagnostics(self):
        report = build_condition_summary(*current(('JSR(R,0)OTE(D);',)))
        mutations = (
            lambda r: r['coverage']['opaque_opcodes'].update(PrivateName=0),
            lambda r: r['coverage']['opaque_guard_opcodes'].update(PrivateName=0),
            lambda r: r['coverage']['opaque_opcodes'].update(JSR=0),
            lambda r: r['coverage']['opaque_guard_opcodes'].update(JSR=0),
            lambda r: r['coverage']['opaque_guard_opcodes'].update(JSR=2),
            lambda r: r['coverage']['opaque_guard_opcodes'].update(SFR=1),
            lambda r: r['coverage']['opaque_opcodes'].update(JSR=True),
        )
        for mutate in mutations:
            changed = deepcopy(report)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ConditionSummaryError):
                validate_condition_summary(changed)

    def test_private_and_public_caps_remain_enforced(self):
        inputs = current()
        for limit in ('MAX_RECORDS', 'MAX_CONDITION_BYTES', 'MAX_EVIDENCE_IDS'):
            with self.subTest(limit=limit), patch(f'plc_workbench.conditions.{limit}', 1):
                with self.assertRaises(ConditionError):
                    analyze_conditions(*inputs[:-1], schema_version=4)
        report = build_condition_summary(*inputs)
        with patch('plc_workbench.condition_summary.MAX_REPORT_V4_BYTES', 1):
            with self.assertRaises(ConditionSummaryError):
                render_condition_summary(report)
        # Independent upper bound: every coverage integer widened to its largest
        # permitted scalar width, even though such simultaneous maxima cannot
        # satisfy population conservation. Revision is also maximum width.
        widest = deepcopy(report)
        widest['tool_revision'] = {'commit': 'f' * 40, 'worktree': 'modified'}
        for key, value in widest['coverage'].items():
            widest['coverage'][key] = ({name: MAX_RECORDS for name in value} if isinstance(value, dict)
                                      else 2_000_000 if key == 'branch_legs' else MAX_RECORDS)
        size = len(json.dumps(widest, ensure_ascii=True, sort_keys=True, indent=2) + '\n')
        self.assertLessEqual(size, MAX_REPORT_V4_BYTES)
        self.assertEqual(set(report['coverage']['opaque_opcodes']), OPAQUE_OPCODES)

    def test_legacy_private_models_and_summaries_remain_byte_identical(self):
        expected = {
            1: ('c113a3a3b6556ee2ba6eccb02e4d5d2745551218870dea061dc2b1fa851c6333',
                '20f680cd9fd41f884debfc4ad57b9335def7493a71914cf72b1f13cc893705ca'),
            2: ('95d3188b8657dfb63d3e6e4a70b59c3321f3dd4f7c814e3e312a5173214eb38c',
                'f85819c79116c7516b1fbf0c60e2a900313f65ebd7d121ad68969f235cacf072'),
            3: ('bb621c60c7e782b13f7c2e14e36eba7c3b4da44246a7c98323a2850dd1ae06df',
                '31112b8098572cd524580c5c1c09732ff8f20d801eee454c7c1b10da7e6828c0'),
        }
        for version, hashes in expected.items():
            with self.subTest(version=version):
                inputs = capture(LEGACY_TEXTS, schema_version=version)
                rendered = render_conditions_json(inputs[-1]), render_condition_summary(build_condition_summary(*inputs))
                self.assertEqual(tuple(hashlib.sha256(value.encode()).hexdigest() for value in rendered), hashes)
                self.assertNotIn('opaque_opcodes', inputs[-1].coverage)


if __name__ == '__main__':
    unittest.main()
