"""Declared metadata observations from invented evidence and public reports."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import replace
from html import escape
import json
from pathlib import Path
import tempfile
import unittest

from plc_workbench.reference_reporting import render_reference_json, render_reference_text
from plc_workbench.reference_summary import build_reference_summary, render_reference_summary
from plc_workbench.references import ReferenceError, analyze_references, validate_references
from plc_workbench.routine_metadata import (
    PROGRAM_TYPE_BUCKETS, ROUTINE_METADATA_CONSTANTS, RoutineMetadataError,
    build_routine_target_metadata, validate_routine_target_metadata,
)
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.storage import save_run
from plc_workbench.summary import build_summary
from plc_workbench.work_check import render_work_check_report


def routine(name: str, *, language: str | None = 'RLL', text: str | None = None,
            body: str = '') -> str:
    attribute = '' if language is None else f' Type="{escape(language, quote=True)}"'
    if text is not None:
        body = '<RLLContent><Rung Number="0" Type="N"><Text>' + escape(text) + '</Text></Rung></RLLContent>'
    return f'<Routine Name="{name}"{attribute}>{body}</Routine>'


def program(index: int, *routines: str, program_type: str | None = None,
            attributes: str = '') -> str:
    attribute = '' if program_type is None else f' Type="{escape(program_type, quote=True)}"'
    return (f'<Program Name="PRIVATE_PROGRAM_{index}"{attribute} {attributes}>'
            '<Tags><Tag Name="PRIVATE_DATA"/></Tags><Routines>'
            + ''.join(routines) + '</Routines></Program>')


def evidence(*programs: str):
    data = ('<RSLogix5000Content><Controller Name="PRIVATE_CONTROLLER"><Programs>'
            + ''.join(programs) + '</Programs></Controller></RSLogix5000Content>').encode()
    snapshot = snapshot_from_bytes(data)
    source = analyze_snapshot(snapshot)
    return snapshot, source, analyze_references(source)


def validation_context(source, references) -> dict:
    rows = references.routine_targets['occurrences']
    return {
        'routine_targets': {
            'by_status': Counter(row['status'] for row in rows),
            'unique_by_target_context': Counter(
                row['target_context'] for row in rows if row['status'] == 'unique_candidate'),
            'distinct_targets': len({row['target_routine_id'] for row in rows
                                     if row['status'] == 'unique_candidate'}),
        },
        'source_summary': build_summary(source),
    }


class RoutineMetadataTests(unittest.TestCase):
    def test_exact_program_type_attributes_distinguish_absent_empty_and_explicit(self) -> None:
        types = (None, '', 'Normal', 'EquipmentPhase', 'Sequence', 'EquipmentSequence',
                 'normal', ' Normal ', ' ', 'Ｎormal', 'PRIVATE_UNKNOWN')
        _, source, refs = evidence(*(program(index, routine('Caller', text='JSR(Target);'),
            routine('Target'), program_type=value) for index, value in enumerate(types)))
        metadata = build_routine_target_metadata(source, refs.routine_targets)
        expected = dict.fromkeys(PROGRAM_TYPE_BUCKETS, 0)
        expected.update(absent=1, empty=1, explicit_normal=1, explicit_equipment_phase=1,
                        explicit_sequence=1, other_explicit=6)
        self.assertEqual(metadata['by_program_type'], expected)
        unknown = dict(expected, explicit_normal=0)
        self.assertEqual(metadata['unclassified_context_by_program_type'], unknown)
        self.assertEqual(metadata['total'], 11)
        validate_routine_target_metadata(metadata, **validation_context(source, refs))
        self.assertNotIn('PRIVATE', json.dumps(metadata))

    def test_target_languages_count_repeated_non_rll_and_protected_envelopes(self) -> None:
        languages = ('RLL', 'FBD', 'SFC', 'ST', None, '', 'rll', 'Sequence', 'PRIVATE_LANGUAGE')
        targets = [routine(f'Target{index}', language=value) for index, value in enumerate(languages)]
        targets.append(routine('Protected', body='<EncodedData>PRIVATE_SECRET</EncodedData>'))
        calls = ''.join(f'JSR(Target{index})' for index in range(len(languages)))
        _, source, refs = evidence(program(0, routine('Caller', text=calls + 'JSR(Target1)JSR(Protected);'),
                                           *targets))
        metadata = build_routine_target_metadata(source, refs.routine_targets)
        self.assertEqual(metadata['by_target_language'],
                         {'RLL': 2, 'FBD': 2, 'SFC': 1, 'ST': 1, 'missing': 1, 'other': 4})
        self.assertEqual(metadata['total'], 11)
        self.assertEqual(len({row['target_routine_id'] for row in refs.routine_targets['occurrences']}), 10)
        self.assertEqual(source.status, 'partial')
        validate_routine_target_metadata(metadata, **validation_context(source, refs))

    def test_known_contexts_excluded_from_unclassified_partition_and_zero_profile(self) -> None:
        _, source, refs = evidence(program(0, routine('Caller', text='JSR(Caller)JSR(Entry)JSR(Fault)JSR(Target);'),
            routine('Entry'), routine('Fault'), routine('Target'), program_type='Sequence',
            attributes='MainRoutineName="Entry" FaultRoutineName="Fault"'))
        metadata = build_routine_target_metadata(source, refs.routine_targets)
        self.assertEqual(metadata['by_program_type']['explicit_sequence'], 4)
        self.assertEqual(metadata['unclassified_context_by_program_type']['explicit_sequence'], 1)
        validate_routine_target_metadata(metadata, **validation_context(source, refs))
        _, source, refs = evidence(program(0, routine('Caller', text='JSR(Missing)JSR();')))
        metadata = build_routine_target_metadata(source, refs.routine_targets)
        self.assertEqual(metadata['total'], 0)
        self.assertTrue(all(sum(metadata[key].values()) == 0 for key in
            ('by_program_type', 'by_target_language', 'unclassified_context_by_program_type')))
        context = validation_context(source, refs)
        context['routine_targets']['by_status']['unique_candidate'] = 0
        context['routine_targets']['unique_by_target_context']['not_analyzed'] = 0
        validate_routine_target_metadata(metadata, **context)

    def test_validator_rejects_types_keys_partitions_contexts_and_language_provenance(self) -> None:
        _, source, refs = evidence(program(0, routine('Caller', text='JSR(Target)JSR(Target);'), routine('Target')))
        good = build_routine_target_metadata(source, refs.routine_targets)
        context = validation_context(source, refs)
        mutations = [lambda p: p.update(total=True), lambda p: p.update(total=-1),
                     lambda p: p.update(total=10**12 + 1), lambda p: p.update(PRIVATE_KEY=1),
                     lambda p: p.update(target_execution='known'),
                     lambda p: p['by_program_type'].update(absent=1),
                     lambda p: p['by_program_type'].update(absent='2'),
                     lambda p: p['by_target_language'].update(RLL=0, FBD=2),
                     lambda p: p['by_target_language'].update(RLL=0, missing=2),
                     lambda p: p['by_target_language'].update(RLL=0, other=2),
                     lambda p: p['unclassified_context_by_program_type'].update(absent=0, empty=2),
                     lambda p: p['unclassified_context_by_program_type'].update(absent=0, explicit_normal=2)]
        for change in mutations:
            forged = deepcopy(good)
            change(forged)
            with self.subTest(forged=forged), self.assertRaisesRegex(RoutineMetadataError,
                    '^Routine target metadata validation failed.$'):
                validate_routine_target_metadata(forged, **context)
        for group in ('by_program_type', 'by_target_language', 'unclassified_context_by_program_type'):
            forged = deepcopy(good)
            forged[group].pop(next(iter(forged[group])))
            with self.assertRaises(RoutineMetadataError):
                validate_routine_target_metadata(forged, **context)
        # Keep every profile partition coherent while violating candidate
        # relationships; these must not pass merely because all sums agree.
        forged = deepcopy(good)
        forged['unclassified_context_by_program_type']['absent'] = 0
        forged_context = deepcopy(context)
        forged_context['routine_targets']['unique_by_target_context'].update(not_analyzed=0, other_routine=2)
        with self.assertRaises(RoutineMetadataError):
            validate_routine_target_metadata(forged, **forged_context)
        _, language_source, language_refs = evidence(program(0, routine('Caller', text='JSR(Target)JSR(Target);'),
                                                            routine('Target', language='FBD')))
        language_profile = build_routine_target_metadata(language_source, language_refs.routine_targets)
        language_context = validation_context(language_source, language_refs)
        language_context['routine_targets']['distinct_targets'] = 2
        with self.assertRaises(RoutineMetadataError):
            validate_routine_target_metadata(language_profile, **language_context)
        language_context['routine_targets']['distinct_targets'] = 1
        language_context['routine_targets']['unique_by_target_context'].update(not_analyzed=0, current_routine=2)
        language_profile['unclassified_context_by_program_type']['absent'] = 0
        with self.assertRaises(RoutineMetadataError):
            validate_routine_target_metadata(language_profile, **language_context)

    def test_broken_private_joins_fail_with_source_free_errors(self) -> None:
        _, source, refs = evidence(program(0, routine('Caller', text='JSR(Target);'), routine('Target')))
        for changed in ({'program_id': 'PRIVATE_WRONG'}, {'target_routine_id': None},
                        {'target_context': 'PRIVATE_WRONG'}, {'target_context': 'not_analyzed'}):
            targets = deepcopy(refs.routine_targets)
            targets['occurrences'][0].update(changed)
            # not_analyzed is allowed for absent Type, but never explicit Normal.
            if changed == {'target_context': 'not_analyzed'}:
                program_entity = next(e for e in source.entities if e.kind == 'program')
                candidate_source = replace(source, entities=[replace(e, attributes={'Type': 'Normal'})
                    if e.id == program_entity.id else e for e in source.entities])
            else:
                candidate_source = source
            with self.assertRaisesRegex(RoutineMetadataError, '^Routine target metadata validation failed.$'):
                build_routine_target_metadata(candidate_source, targets)

    def test_profile_is_independent_of_parameters_operands_and_private_json_contract(self) -> None:
        _, source, refs = evidence(program(0, routine('Caller',
            text='XIC(PRIVATE_DATA)JSR(Target,0,PRIVATE_DATA)JSR(Target,PRIVATE_DATA+1);'), routine('Target')))
        before_source, before_refs = deepcopy(source.to_dict()), deepcopy(refs.to_dict())
        metadata = build_routine_target_metadata(source, refs.routine_targets)
        self.assertEqual(source.to_dict(), before_source)
        self.assertEqual(refs.to_dict(), before_refs)
        self.assertEqual((refs.schema_version, refs.analyzer_version), (5, 'source-references-8'))
        self.assertEqual(metadata['total'], 2)
        self.assertEqual(refs.operands[0]['status'], 'root_bound')
        self.assertTrue(all(row['status'] == 'unsupported_instruction' for row in refs.operands[1:]))
        self.assertEqual(json.loads(render_reference_json(refs)), before_refs)
        self.assertNotIn('routine_target_metadata', before_refs)
        validate_references(source, refs)
        targets = deepcopy(refs.routine_targets)
        targets['occurrences'][0]['target_routine_id'] = 'PRIVATE_WRONG'
        with self.assertRaises(ReferenceError):
            validate_references(source, replace(refs, routine_targets=targets))

    def test_private_text_and_saved_manifest_include_metadata_only_with_inventory(self) -> None:
        snapshot, source, refs = evidence(program(0, routine('Caller', text='JSR(Target);'), routine('Target')))
        text = render_reference_text(refs, inventory=source)
        self.assertIn('Unique JSR candidate metadata (call-weighted observations only)', text)
        self.assertIn('by_program_type:\n    absent: 1', text)
        self.assertIn('Program Type semantics and target execution are not analyzed.', text)
        self.assertIn('JSR first-field routine candidates', text)
        self.assertNotIn('Unique JSR candidate metadata', render_reference_text(refs))
        with tempfile.TemporaryDirectory() as directory:
            run = save_run(Path(directory) / 'workspace', snapshot, source, references=refs)
            self.assertEqual((run / 'references.txt').read_text(encoding='utf-8'), text)
            self.assertEqual(json.loads((run / 'references.json').read_text(encoding='utf-8')), refs.to_dict())

    def test_current_public_profile_is_closed_and_frozen_v10_reports_stay_unchanged(self) -> None:
        _, source, refs = evidence(program(0, routine('PRIVATE_CALLER', text='JSR(PRIVATE_TARGET);'),
                                           routine('PRIVATE_TARGET'), program_type='PRIVATE_TYPE'))
        summary = build_reference_summary(source, refs)
        self.assertEqual(summary['schema_version'], 11)
        self.assertEqual(summary['routine_target_metadata'], build_routine_target_metadata(source, refs.routine_targets))
        self.assertEqual(set(summary['routine_target_metadata']), set(ROUTINE_METADATA_CONSTANTS) | {
            'total', 'by_program_type', 'by_target_language', 'unclassified_context_by_program_type'})
        rendered = render_reference_summary(summary)
        for forbidden in ('PRIVATE_', source.snapshot['id'], source.snapshot['sha256'], 'program_id',
                          'target_routine_id', 'instruction_id', 'raw_target_name'):
            self.assertNotIn(forbidden, rendered)
        report_folder = Path(__file__).resolve().parents[2] / 'public/inspection'
        frozen = [json.loads(path.read_text(encoding='utf-8')) for path in report_folder.glob('work-check-*.json')]
        previous = next(report for report in frozen if report['analysis']['reference_summary']['schema_version'] == 10)
        self.assertNotIn('routine_target_metadata', previous['analysis']['reference_summary'])
        self.assertEqual(json.loads(render_work_check_report(previous)), previous)


if __name__ == '__main__':
    unittest.main()
