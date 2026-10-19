"""Routine candidates from invented L5X evidence and frozen public reports only."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import replace
from html import escape
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import work_check
from plc_workbench.reference_reporting import render_reference_json, render_reference_text
from plc_workbench.reference_summary import build_reference_summary, render_reference_summary
from plc_workbench.references import ReferenceError, analyze_references, validate_references
from plc_workbench.routine_shapes import build_routine_instruction_shapes
from plc_workbench.routine_targets import (
    ROUTINE_TARGET_CONSTANTS, RoutineTargetError, build_routine_targets,
)
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.storage import StorageError, save_run

from test_unmatched_sample_report import report

ROOT = Path(__file__).resolve().parents[2]
PREVIOUS_REPORT = ROOT / 'public/inspection/work-check-20261014T212041Z-8cac2026.json'


def routine(name: str, text: str | None = None, language: str = 'RLL') -> str:
    body = '' if text is None else (
        f'<RLLContent><Rung Number="0" Type="N"><Text>{escape(text)}</Text>'
        '</Rung></RLLContent>'
    )
    return f'<Routine Name="{escape(name, quote=True)}" Type="{language}">{body}</Routine>'


def program(name: str, *routines: str, attributes: str = 'Type="Normal"', tags: str = '') -> str:
    return (f'<Program Name="{name}" {attributes}><Tags>{tags}</Tags>'
            f'<Routines>{"".join(routines)}</Routines></Program>')


def source_bytes(*programs: str, aoi: str = '') -> bytes:
    return (f'<RSLogix5000Content><Controller Name="PRIVATE_CONTROLLER">'
            f'<Tags><Tag Name="PRIVATE_CONTROLLER_TAG"/></Tags><Programs>{"".join(programs)}</Programs>'
            f'{aoi}</Controller></RSLogix5000Content>').encode()


def inventory(*programs: str, aoi: str = ''):
    return analyze_snapshot(snapshot_from_bytes(source_bytes(*programs, aoi=aoi)))


def rows(source):
    return analyze_references(source).routine_targets['occurrences']


class RoutineTargetTests(unittest.TestCase):
    def test_program_identity_ascii_case_and_separate_tag_namespace(self) -> None:
        source = inventory(
            program('PRIVATE_P1', routine('Caller', 'jsr( tArGeT ,0)JSR(Elsewhere)JSR(PRIVATE_CONTROLLER_TAG);'),
                    routine('Target'), tags='<Tag Name="Target"/>'),
            program('PRIVATE_P2', routine('Target'), routine('Elsewhere')),
        )
        # Source parser currently trims slots; the candidate builder must also
        # preserve raw argument text when the captured record contains it.
        rung = source.rungs[0]
        first = replace(rung.instructions[0], arguments=(' tArGeT ', '0'))
        source = replace(source, rungs=[replace(rung, instructions=[first, *rung.instructions[1:]])])
        actual = rows(source)
        target = next(e for e in source.entities if e.kind == 'routine' and e.name == 'Target')
        self.assertEqual([r['status'] for r in actual],
                         ['unique_candidate', 'missing_candidate', 'missing_candidate'])
        self.assertEqual(actual[0]['target_routine_id'], target.id)
        self.assertEqual(actual[0]['raw_target_name'], ' tArGeT ')
        self.assertEqual(actual[0]['candidate_count'], 1)

    def test_case_collisions_ambiguous_but_declaration_whitespace_is_raw(self) -> None:
        source = inventory(program('PRIVATE_P', routine('Caller', 'JSR(Target)JSR(Spaced);'),
                                   routine('Target'), routine('TARGET'), routine(' Spaced ')))
        actual = rows(source)
        self.assertEqual([r['status'] for r in actual], ['ambiguous_candidate', 'missing_candidate'])
        self.assertEqual(actual[0]['candidate_count'], 2)
        self.assertIsNone(actual[0]['target_routine_id'])
        self.assertEqual(actual[0]['target_context'], 'not_analyzed')

    def test_context_uses_normal_attributes_and_identity_with_priority(self) -> None:
        source = inventory(program(
            'PRIVATE_P', routine('Caller', 'JSR(Caller)JSR(ENTRY)JSR(Handler)JSR(MainRoutine)JSR(FaultRoutine);'),
            routine('Entry'), routine('Handler'), routine('MainRoutine'), routine('FaultRoutine'),
            attributes='Type="Normal" MainRoutineName="entry" FaultRoutineName="HANDLER"',
        ))
        self.assertEqual([r['target_context'] for r in rows(source)],
                         ['current_routine', 'main_routine', 'fault_routine', 'other_routine', 'other_routine'])
        source = inventory(program('PRIVATE_P', routine('Caller', 'JSR(Caller)JSR(Entry);'), routine('Entry'),
                                   attributes='Type="Normal" MainRoutineName="Caller" FaultRoutineName="Entry"'))
        self.assertEqual([r['target_context'] for r in rows(source)], ['current_routine', 'fault_routine'])
        source = inventory(program('PRIVATE_P', routine('Caller', 'JSR(Entry);'), routine('Entry'),
                                   attributes='Type="Normal" MainRoutineName="Entry" FaultRoutineName="Entry"'))
        self.assertEqual(rows(source)[0]['target_context'], 'main_routine')

    def test_unmodeled_languages_and_protected_envelopes_are_candidates(self) -> None:
        targets = [routine(f'Target_{language}', language=language) for language in ('FBD', 'LD', 'SFC', 'ST')]
        protected = '<Routine Name="Protected" Type="RLL"><EncodedData>PRIVATE_ENCODED</EncodedData></Routine>'
        source = inventory(program('PRIVATE_P', routine('Caller',
            'JSR(Target_FBD)JSR(Target_LD)JSR(Target_SFC)JSR(Target_ST)JSR(Protected);'), *targets, protected))
        self.assertEqual(len(rows(source)), 5)
        self.assertEqual(Counter(r['status'] for r in rows(source)), {'unique_candidate': 5})
        self.assertEqual(source.status, 'partial')

    def test_missing_empty_unsupported_and_static_identifier_lexical_names(self) -> None:
        source = inventory(program('PRIVATE_P', routine('Caller',
            'JSR()JSR(,0)JSR( \n ,A)JSR(Program:P.Target)JSR(Target.Member)'
            'JSR(Target+1)JSR(Target[0])JSR("Target")JSR(_Target)JSR(123)JSR(\u212a);'),
            routine('_Target'), routine('K')))
        rung = source.rungs[0]
        instructions = list(rung.instructions)
        instructions[2] = replace(instructions[2], arguments=(' \n ', 'A'))
        source = replace(source, rungs=[replace(rung, instructions=instructions)])
        actual = rows(source)
        self.assertEqual([r['status'] for r in actual],
            ['missing_target_field', 'empty_target_field', 'empty_target_field']
            + ['unsupported_target_name'] * 5 + ['unique_candidate'] + ['unsupported_target_name'] * 2)
        self.assertIsNone(actual[0]['raw_target_name'])
        self.assertEqual(actual[1]['raw_target_name'], '')
        self.assertEqual(actual[2]['raw_target_name'], ' \n ')
        for item in actual:
            self.assertEqual(set(item), {'instruction_id', 'rung_id', 'caller_routine_id', 'program_id',
                                        'raw_target_name', 'status', 'candidate_count', 'target_routine_id',
                                        'target_context'})

    def test_aoi_and_invalid_ownership_fail_closed_with_missing_field_precedence(self) -> None:
        aoi = ('<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="PRIVATE_AOI">'
               '<Routines>' + routine('Caller', 'JSR()JSR(,0)JSR(Target);') + routine('Target')
               + '</Routines></AddOnInstructionDefinition></AddOnInstructionDefinitions>')
        source = inventory(aoi=aoi)
        actual = rows(source)
        self.assertEqual([r['status'] for r in actual],
                         ['missing_target_field', 'unsupported_context', 'unsupported_context'])
        self.assertTrue(all(r['program_id'] is None for r in actual))
        base = inventory(program('PRIVATE_P', routine('Caller', 'JSR(Target);'), routine('Target')),
                         program('PRIVATE_Q', routine('Other')))
        caller = next(e for e in base.entities if e.name == 'Caller')
        other_program = next(e for e in base.entities if e.name == 'PRIVATE_Q')
        malformed = [replace(base, rungs=[replace(base.rungs[0], parent_id=None)]),
                     replace(base, rungs=[replace(base.rungs[0], parent_id=other_program.id)]),
                     replace(base, rungs=[replace(base.rungs[0], scope_id=other_program.id)]),
                     replace(base, entities=[replace(e, scope_id=other_program.id) if e.id == caller.id else e
                                             for e in base.entities]),
                     replace(base, entities=[replace(e, parent_id=other_program.id) if e.id == caller.id else e
                                             for e in base.entities])]
        for forged in malformed:
            with self.subTest(forged=forged.rungs[0].parent_id):
                self.assertEqual(rows(forged)[0]['status'], 'unsupported_context')
                self.assertIsNone(rows(forged)[0]['program_id'])

    def test_phase_sequence_missing_and_unknown_types_only_classify_explicit_context(self) -> None:
        for attributes in ('Type="EquipmentPhase"', 'Type="Sequence"', 'Type="EquipmentSequence"', '', 'Type="Unknown"'):
            with self.subTest(attributes=attributes):
                source = inventory(program('PRIVATE_P', routine('Running',
                    'JSR(Running)JSR(Entry)JSR(Handler)JSR(Stopping)JSR(Custom);'),
                    routine('Entry'), routine('Handler'), routine('Stopping'), routine('Custom'),
                    attributes=attributes + ' MainRoutineName="Entry" FaultRoutineName="Handler"'))
                actual = rows(source)
                self.assertEqual(Counter(r['status'] for r in actual), {'unique_candidate': 5})
                self.assertEqual([r['target_context'] for r in actual],
                    ['current_routine', 'main_routine', 'fault_routine', 'not_analyzed', 'not_analyzed'])
                self.assertTrue(all(r['program_id'] is not None and r['target_routine_id'] is not None
                                    for r in actual))

    def test_raw_attribute_names_and_unicode_attributes_do_not_invent_context(self) -> None:
        for attribute in ('MainRoutineName=" Entry "', 'MainRoutineName="\u212a"'):
            source = inventory(program('PRIVATE_P', routine('Caller', 'JSR(Entry)JSR(K);'),
                routine('Entry'), routine('K'), attributes='Type="Normal" ' + attribute))
            self.assertEqual([r['target_context'] for r in rows(source)], ['other_routine', 'other_routine'])
        long_name = 'T' * 41
        source = inventory(program('PRIVATE_P', routine('Caller', f'JSR({long_name});'), routine(long_name)))
        self.assertEqual(rows(source)[0]['status'], 'unique_candidate')

    def test_parameters_catalogue_root_bindings_and_shape_observations_stay_independent(self) -> None:
        source = inventory(program('PRIVATE_P', routine('Caller',
            'XIC(A)JSR(Target)JSR(Target,0,A)JSR(Target,PRIVATE_EXPRESSION+1,,A)SBR(A)RET(A);'),
            routine('Target'), tags='<Tag Name="A"/>'))
        before = deepcopy(source.to_dict())
        result = analyze_references(source)
        self.assertEqual(source.to_dict(), before)
        self.assertEqual(Counter(r['status'] for r in result.routine_targets['occurrences']), {'unique_candidate': 3})
        self.assertEqual(result.coverage['instructions_catalogued'], 1)
        self.assertEqual(result.operands[0]['status'], 'root_bound')
        self.assertTrue(all(r['status'] == 'unsupported_instruction' for r in result.operands[1:]))
        self.assertEqual(result.routine_targets, {**ROUTINE_TARGET_CONSTANTS,
                                                'occurrences': result.routine_targets['occurrences']})
        self.assertEqual(build_routine_instruction_shapes(source)['by_opcode']['JSR']['total'], 3)
        self.assertEqual((result.schema_version, result.analyzer_version), (6, 'source-references-9'))
        validate_references(source, result)

    def test_parsed_only_jsr_ascii_opcodes_and_raw_ids(self) -> None:
        source = inventory(program('PRIVATE_P', routine('Caller', 'JSR(Target)jsr(Target)SBR(Target)RET(Target);'),
            routine('Failed', 'JSR(Target)BROKEN('), routine('Target'),
            '<Routine Name="STCaller" Type="ST"><STContent>JSR(Target);</STContent></Routine>'))
        result = build_routine_targets(source)
        self.assertEqual(len(result['occurrences']), 2)
        rung = next(r for r in source.rungs if r.parse_status == 'parsed')
        self.assertEqual([r['instruction_id'] for r in result['occurrences']], [i.id for i in rung.instructions[:2]])
        self.assertTrue(all(r['rung_id'] == rung.id and r['caller_routine_id'] == rung.parent_id
                            for r in result['occurrences']))
        fabricated = replace(source, rungs=[replace(rung, instructions=[replace(rung.instructions[0], opcode='J\u017fR')])])
        self.assertEqual(build_routine_targets(fabricated)['occurrences'], [])

    def test_occurrence_raw_name_and_aggregate_evidence_limits_are_fixed_source_free(self) -> None:
        source = inventory(program('PRIVATE_P', routine('Caller', 'JSR()JSR()JSR();')))
        with patch('plc_workbench.routine_targets.MAX_ROUTINE_TARGET_OCCURRENCES', 2):
            with self.assertRaisesRegex(RoutineTargetError, '^Routine target analysis exceeds its evidence limits.$'):
                build_routine_targets(source)
            with self.assertRaisesRegex(ReferenceError, '^Routine target analysis could not complete within its evidence contract.$'):
                analyze_references(source)
        source = inventory(program('PRIVATE_P', routine('Caller', 'JSR(PRIVATE_TARGET);')))
        with patch('plc_workbench.routine_targets.MAX_ROUTINE_TARGET_NAME_LENGTH', 5):
            with self.assertRaises(RoutineTargetError) as caught:
                build_routine_targets(source)
            self.assertNotIn('PRIVATE', str(caught.exception))
        unbounded = build_routine_targets(source)
        size = sum(len(v) for v in ROUTINE_TARGET_CONSTANTS.values()) + sum(
            len(v) for v in unbounded['occurrences'][0].values() if type(v) is str)
        with patch('plc_workbench.routine_targets.MAX_ROUTINE_TARGET_EVIDENCE_CHARS', size):
            self.assertEqual(build_routine_targets(source), unbounded)
        with patch('plc_workbench.routine_targets.MAX_ROUTINE_TARGET_EVIDENCE_CHARS', size - 1):
            with self.assertRaises(RoutineTargetError):
                build_routine_targets(source)

    def test_canonical_validation_catches_target_context_count_and_type_forgery_before_save(self) -> None:
        data = source_bytes(program('PRIVATE_P', routine('Caller', 'JSR(Target);'), routine('Target')))
        snapshot = snapshot_from_bytes(data)
        source = analyze_snapshot(snapshot)
        result = analyze_references(source)
        updates = [{'target_routine_id': 'PRIVATE_WRONG'}, {'candidate_count': 2}, {'candidate_count': True},
                   {'target_context': 'main_routine'}, {'status': 'missing_candidate'}, {'program_id': None},
                   {'raw_target_name': 'PRIVATE_CHANGED'}, {'instruction_id': 'PRIVATE_CHANGED'}]
        for changes in updates:
            payload = deepcopy(result.routine_targets)
            payload['occurrences'][0].update(changes)
            forged = replace(result, routine_targets=payload)
            with self.subTest(changes=changes), self.assertRaises(ReferenceError):
                validate_references(source, forged)
            with tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / 'never-created'
                with self.assertRaises(StorageError):
                    save_run(destination, snapshot, source, references=forged)
                self.assertFalse(destination.exists())
        for updates in ({'parameter_roles': True}, {'call_validation': 'validated'}, {'PRIVATE_KEY': 1}):
            payload = deepcopy(result.routine_targets)
            payload.update(updates)
            with self.assertRaises(ReferenceError):
                validate_references(source, replace(result, routine_targets=payload))

    def test_private_text_and_json_explain_candidates_without_root_binding_claims(self) -> None:
        source = inventory(program('PRIVATE_P', routine('Caller', 'JSR( Target ,0);'), routine('Target')))
        rung = source.rungs[0]
        source = replace(source, rungs=[replace(rung, instructions=[
            replace(rung.instructions[0], arguments=(' Target ', '0'))])])
        result = analyze_references(source)
        self.assertEqual(json.loads(render_reference_json(result)), result.to_dict())
        text = render_reference_text(result, inventory=source)
        self.assertIn('JSR first-field routine candidates (separate routine namespace)', text)
        self.assertIn("' Target ' -> unique_candidate", text)
        self.assertIn('context: other_routine', text)
        self.assertIn('call legality and parameter roles are not analyzed', text)
        self.assertIn('Target -> unsupported_instruction', text.replace(' Target ', 'Target'))

    def test_current_public_versions_exclude_private_evidence_and_frozen_v9_stays_exact(self) -> None:
        data = source_bytes(program('PRIVATE_P', routine('PRIVATE_CALLER',
                                  'JSR(PRIVATE_TARGET)JSR(PRIVATE_MISSING)JSR();'), routine('PRIVATE_TARGET')))
        source = analyze_snapshot(snapshot_from_bytes(data))
        references = analyze_references(source)
        summary = build_reference_summary(source, references)
        rendered = render_reference_summary(summary)
        self.assertEqual(summary['schema_version'], 12)
        self.assertEqual(summary['analyzer_version'], 'source-references-9')
        for forbidden in ('PRIVATE_', source.snapshot['id'], source.snapshot['sha256'], 'raw_target_name',
                          'instruction_id', 'target_routine_id', 'caller_routine_id', 'program_id'):
            self.assertNotIn(forbidden, rendered)
        current = report(data)
        self.assertEqual((current['schema_version'], current['workflow_version']), (12, 'work-check-12'))
        self.assertNotIn('PRIVATE_', work_check.render_work_check_report(current))
        frozen = json.loads(PREVIOUS_REPORT.read_text(encoding='utf-8'))
        self.assertEqual((frozen['schema_version'], frozen['analysis']['reference_summary']['schema_version']), (7, 9))
        self.assertEqual(json.loads(work_check.render_work_check_report(frozen)), frozen)


if __name__ == '__main__':
    unittest.main()
