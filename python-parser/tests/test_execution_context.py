"""Invented source declarations and controls challenge execution-context bounds."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access, render_access_json
from plc_workbench.calculations import analyze_calculations
from plc_workbench.conditions import analyze_conditions, render_conditions_json
from plc_workbench.execution_context import (ExecutionContextError, analyze_execution_context,
    render_execution_context_json, validate_execution_context)
from plc_workbench.references import analyze_references
from plc_workbench.relationships import analyze_relationships
from plc_workbench.rung_analysis import analyze_rungs
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def routine(name: str = 'Main', text: str = ';', *, content: str | None = None,
            language: str = 'RLL') -> str:
    body = content if content is not None else f'<RLLContent><Rung Number="0" Type="N"><Text>{text}</Text></Rung></RLLContent>'
    return f'<Routine Name="{name}" Type="{language}">{body}</Routine>'


def program(name: str = 'P', routines: str | None = None,
            attributes: str = 'Type="Normal" MainRoutineName="Main"') -> str:
    return f'<Program Name="{name}" {attributes}><Routines>{routines if routines is not None else routine()}</Routines></Program>'


def task(schedules: str = '<ScheduledProgram Name="P"/>', *, attributes: str = 'Type="Periodic" Rate="10.000" Priority="6" Watchdog="500"',
         events: str = '') -> str:
    return f'<Task Name="TaskA" {attributes}>{events}<ScheduledPrograms>{schedules}</ScheduledPrograms></Task>'


def document(programs: str | None = None, *, tasks: str = '', tags: str = '',
             extra: str = '', root_attributes: str = '') -> str:
    return (f'<RSLogix5000Content {root_attributes}><Controller Name="C"><Tags>{tags}</Tags>'
        f'<Tasks>{tasks}</Tasks><Programs>{programs if programs is not None else program()}</Programs>{extra}'
        '</Controller></RSLogix5000Content>')


def capture_xml(xml: str):
    snapshot = snapshot_from_bytes(xml.encode())
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    calculations = analyze_calculations(snapshot, inventory, references)
    access = analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
    rungs = analyze_rungs(snapshot, inventory, references, access, calculations)
    relationships = analyze_relationships(snapshot, inventory, references, access, calculations, rungs)
    args = snapshot, inventory, references, access, calculations, rungs, relationships
    conditions = analyze_conditions(*args, schema_version=3)
    return (*args, conditions, analyze_execution_context(*args, conditions))


def capture(text: str = 'JSR(Sub,0);', **kwargs):
    return capture_xml(document(program(routines=routine(text=text) + routine('Sub')), **kwargs))


def tag(name: str, *, alias: str | None = None, attributes: str = '') -> str:
    attrs = f'TagType="Alias" AliasFor="{alias}"' if alias else 'TagType="Base" DataType="BOOL"'
    return f'<Tag Name="{name}" {attrs} {attributes}/>'


class ExecutionContextTests(unittest.TestCase):
    def test_raw_task_metadata_event_info_and_repeated_schedule_order(self) -> None:
        args = capture(tasks=task('<ScheduledProgram Name="P"/><ScheduledProgram Name="P"/>',
            events='<EventInfo EventTrigger="EVENT" EventTag="AlarmValue" EnableTimeout="true"/>'))
        result = args[-1]
        self.assertEqual(result.tasks[0]['raw_attributes']['Rate'], '10.000')
        self.assertEqual(result.tasks[0]['raw_attributes']['Watchdog'], '500')
        self.assertEqual(result.tasks[0]['event_info'][0]['raw_attributes']['EventTag'], 'AlarmValue')
        self.assertEqual([row['ordinal'] for row in result.schedules], [1, 2])
        self.assertEqual(len(result.programs[0]['schedule_ids']), 2)
        self.assertEqual([row['status'] for row in result.schedules], ['unique_candidate'] * 2)
        self.assertEqual(result.status, 'complete')
        validate_execution_context(*args)
        self.assertEqual(result.to_dict(), json.loads(render_execution_context_json(result)))

    def test_schedule_name_shapes_ambiguity_and_controller_locality(self) -> None:
        programs = program('P') + program('p') + program('Q')
        schedules = ''.join(f'<ScheduledProgram {attrs}/>' for attrs in
            ('Name="P"', 'Name="Q"', 'Name="Absent"', '', 'Name=""', 'Name=" Q "'))
        result = capture_xml(document(programs, tasks=task(schedules)))[-1]
        self.assertEqual([row['status'] for row in result.schedules],
            ['ambiguous_candidate', 'unique_candidate', 'missing_candidate', 'absent', 'empty', 'unsupported_name'])
        self.assertEqual(len(result.schedules[0]['candidate_program_ids']), 2)
        first = document(program('A'), tasks=task('<ScheduledProgram Name="B"/>'))
        second = '<Controller Name="Other"><Programs>' + program('B') + '</Programs></Controller>'
        result = capture_xml(first.replace('</RSLogix5000Content>', second + '</RSLogix5000Content>'))[-1]
        self.assertEqual(result.schedules[0]['status'], 'missing_candidate')

    def test_designations_remain_separate_and_program_type_is_not_defaulted(self) -> None:
        result = capture_xml(document(program(routines=routine('Same'),
            attributes='MainRoutineName="same" FaultRoutineName="SAME"')))[-1]
        self.assertEqual([row['kind'] for row in result.designations], ['main', 'fault'])
        self.assertEqual([row['status'] for row in result.designations], ['unique_candidate'] * 2)
        self.assertEqual(len(result.routine_contexts[0]['designation_ids']), 2)
        self.assertNotIn('Type', result.programs[0]['raw_attributes'])
        self.assertEqual(result.coverage['programs_missing_type'], 1)
        for attrs, expected in (('', 'absent'), ('MainRoutineName=""', 'empty'),
                ('MainRoutineName=" Main "', 'unsupported_name'), ('MainRoutineName="Lost"', 'missing_candidate')):
            with self.subTest(attrs=attrs):
                result = capture_xml(document(program(attributes=attrs)))[-1]
                self.assertEqual(result.designations[0]['status'], expected)
        result = capture_xml(document(program(routines=routine() + routine('main'))))[-1]
        self.assertEqual(result.designations[0]['status'], 'ambiguous_candidate')

    def test_namespace_attributes_ancestors_targets_and_event_info_preserve_gaps(self) -> None:
        base = document(program(), tasks=task(events='<EventInfo EventTrigger="EVENT"/>'), root_attributes='xmlns:x="urn:foreign"')
        for old, new, group in ((' Priority=', ' x:Priority=', 'tasks'),
                ('<Programs>', '<x:Programs>','programs'),
                ('MainRoutineName=', 'x:MainRoutineName=', 'programs')):
            xml = base.replace(old, new)
            if old == '<Programs>':
                xml = xml.replace('</Programs>', '</x:Programs>')
            result = capture_xml(xml)[-1]
            self.assertFalse(result.to_dict()[group][0]['qualified'])
            self.assertEqual(result.schedules[0]['status'], 'namespace_gap')
            self.assertEqual(len(result.schedules[0]['candidate_program_ids']), 1)
            self.assertIsNone(result.schedules[0]['target_program_id'])
        result = capture_xml(base.replace('EventTrigger=', 'x:EventTrigger='))[-1]
        self.assertFalse(result.tasks[0]['event_info'][0]['qualified'])
        self.assertEqual(result.coverage['event_info_by_qualification']['namespace_gap'], 1)
        result = capture_xml(base.replace('<Routines>', '<x:Routines>').replace('</Routines>', '</x:Routines>'))[-1]
        self.assertEqual(result.designations[0]['status'], 'namespace_gap')
        self.assertEqual(result.designations[0]['lexical_status'], 'unique_candidate')

    def test_every_jsr_target_status_keeps_raw_shape_and_reference_evidence(self) -> None:
        args = capture('JSR()JSR(,)JSR(Bad.Name,0)JSR(Lost,0)JSR(Sub,02,A,,B);')
        result = args[-1]
        self.assertEqual([row['lexical_status'] for row in result.calls],
            [row['status'] for row in args[2].routine_targets['occurrences']])
        self.assertEqual([row['status'] for row in result.calls], ['missing_target_field',
            'empty_target_field', 'unsupported_target_name', 'missing_candidate', 'unique_candidate'])
        self.assertEqual(result.calls[-1]['raw_arguments'], ['Sub', '02', 'A', '', 'B'])
        self.assertEqual(result.calls[-1]['empty_argument_indices'], [3])
        self.assertEqual(result.calls[-1]['argument_shape'], 'empty_fields')
        self.assertNotIn('input_count', result.calls[-1])
        self.assertNotIn('parameter_roles', result.calls[-1])
        self.assertEqual(result.parameter_roles, 'not_analyzed')
        self.assertEqual(result.calls[0]['guard_status'], 'modeled')
        self.assertEqual(result.calls[1]['guard_status'], 'opaque')

    def test_incoming_guards_preserve_branch_opaque_and_namespace_isolation(self) -> None:
        tags = tag('A') + tag('B', attributes='x:Marker="foreign"')
        args = capture('[XIC(A)JSR(Sub,0),XIC(B)]JSR(Sub,0);', tags=tags,
                       root_attributes='xmlns:x="urn:foreign"')
        first, after_join = args[-1].calls
        self.assertEqual(first['guard_quality'], 'modeled')
        self.assertFalse(first['has_branch'])
        self.assertEqual(after_join['guard_quality'], 'namespace_gap')
        self.assertTrue(after_join['has_branch'])
        nodes = {row['id']: row for row in args[7].nodes}
        self.assertFalse(nodes[first['guard_id']]['has_opaque'])
        self.assertTrue(nodes[after_join['guard_id']]['has_opaque'])
        args = capture('[MYSTERY(A),XIC(A)JSR(Sub,0)]JSR(Sub,0);', tags=tag('A'))
        self.assertEqual([row['guard_quality'] for row in args[-1].calls], ['modeled', 'opaque'])

    def test_alias_and_expression_guard_dependencies_are_qualified(self) -> None:
        for prior in ('XIC(Bad)', 'MOV(Bad,A)', 'CPT(A,Bad+1)'):
            with self.subTest(prior=prior):
                args = capture(prior + 'JSR(Sub,0);', tags=tag('A') + tag('Bad', alias='A', attributes='x:Marker="foreign"'),
                               root_attributes='xmlns:x="urn:foreign"')
                self.assertEqual(args[-1].calls[0]['guard_quality'], 'namespace_gap')
                self.assertEqual(args[-1].calls[0]['status'], 'unique_candidate')
        result = capture('ONS(A)JSR(Sub,0);', tags=tag('A'))[-1]
        self.assertEqual(result.calls[0]['guard_quality'], 'stateful')
        result = capture('XIC(Missing)JSR(Sub,0);')[-1]
        self.assertEqual(result.calls[0]['guard_quality'], 'binding_gaps')

    def test_jump_label_candidates_are_routine_local_and_content_specific(self) -> None:
        text = 'JMP(Next)LBL(Next)LBL(NEXT)JMP(Lost)JMP(Elsewhere)SBR(A,B)RET(A);'
        result = capture_xml(document(program(routines=routine(text=text) + routine('Other', 'LBL(Elsewhere);'))))[-1]
        self.assertEqual([row['status'] for row in result.control_occurrences],
            ['ambiguous_candidate'] * 3 + ['missing_candidate'] * 2 + ['not_applicable'] * 2 + ['unique_candidate'])
        self.assertEqual(len(result.control_occurrences[0]['candidate_label_instruction_ids']), 2)
        content = ('<RLLContent OnlineEditType="Original"><Rung Number="9" Type="N"><Text>JMP(L);</Text></Rung></RLLContent>'
            '<RLLContent OnlineEditType="Pending"><Rung Number="0" Type="N"><Text>LBL(L);</Text></Rung></RLLContent>')
        result = capture_xml(document(program(routines=routine(content=content))))[-1]
        jump, label = result.control_occurrences
        self.assertEqual(jump['status'], 'missing_candidate')
        self.assertEqual(jump['other_edit_candidate_ids'], [label['instruction_id']])
        self.assertNotEqual(jump['content_locator'], label['content_locator'])
        self.assertEqual(result.routine_contexts[0]['body_status'], 'rll_structure_partial')

    def test_control_shapes_are_lexical_and_source_positions_are_retained(self) -> None:
        result = capture('JMP()JMP(,)JMP(Bad.Name)LBL( )SBR()RET(,);')[-1]
        self.assertEqual([row['status'] for row in result.control_occurrences],
            ['absent', 'invalid_field_count', 'unsupported_name', 'absent', 'not_applicable', 'not_applicable'])
        self.assertEqual([row['source_start'] for row in result.control_occurrences],
                         sorted(row['source_start'] for row in result.control_occurrences))
        self.assertEqual(result.coverage['source_control_opcodes'], {'JMP': 3, 'JSR': 0, 'LBL': 1, 'RET': 1, 'SBR': 1})

    def test_partial_languages_missing_bodies_and_cycles_are_not_execution(self) -> None:
        routines = routine(text='JSR(Main,0)JSR(Text,0)JSR(MissingBody,0);')
        routines += routine('Text', content='<STContent/>', language='ST') + routine('MissingBody', content='')
        args = capture_xml(document(program(routines=routines)))
        self.assertEqual([row['body_status'] for row in args[-1].routine_contexts],
            ['rll_structure_parsed', 'language_unmodeled', 'rll_structure_partial'])
        self.assertEqual([row['status'] for row in args[-1].calls], ['unique_candidate'] * 3)
        self.assertTrue(args[-1].routine_contexts[0]['in_lexical_call_cycle'])
        self.assertEqual(args[-1].execution_analysis, 'not_implemented')
        self.assertEqual(args[-1].status, 'partial')

    def test_canonical_replay_rejects_all_groups_counts_links_and_bool_integers(self) -> None:
        args = capture('JSR(Sub,0)JMP(L)LBL(L);', tasks=task())
        result = args[-1]
        before = render_access_json(args[3]), render_conditions_json(args[7])
        for group in ('tasks', 'programs', 'schedules', 'designations', 'calls', 'control_occurrences', 'routine_contexts'):
            broken = deepcopy(result)
            getattr(broken, group)[0]['id'] = 'private-marker'
            with self.subTest(group=group), self.assertRaises(ExecutionContextError) as caught:
                validate_execution_context(*args[:-1], broken)
            self.assertNotIn('private-marker', str(caught.exception))
        for mutate in (lambda r: r.coverage.update(calls_total=True),
                lambda r: r.calls[0].update(guard_id='forged'),
                lambda r: r.schedules[0].update(ordinal=True),
                lambda r: r.programs[0]['schedule_ids'].clear(),
                lambda r: r.calls[0].update(target_routine_id=None)):
            broken = deepcopy(result)
            mutate(broken)
            with self.assertRaises(ExecutionContextError):
                validate_execution_context(*args[:-1], broken)
        self.assertEqual(before, (render_access_json(args[3]), render_conditions_json(args[7])))
        self.assertEqual(render_execution_context_json(result), render_execution_context_json(analyze_execution_context(*args[:-1])))

    def test_exact_conditions3_and_prior_chain_are_authenticated(self) -> None:
        args = capture()
        for conditions in (replace(args[7], schema_version=True),
                analyze_conditions(*args[:7], schema_version=2)):
            with self.assertRaises(ExecutionContextError):
                analyze_execution_context(*args[:7], conditions)
        forged = deepcopy(args[2])
        forged.routine_targets['occurrences'][0]['target_routine_id'] = 'private-marker'
        with self.assertRaises(ExecutionContextError):
            analyze_execution_context(*args[:2], forged, *args[3:-1])

    def test_cycles_and_resource_caps_reject_with_source_free_errors(self) -> None:
        args = capture('JSR(Sub,0)JMP(L)LBL(L);', tasks=task())
        broken = deepcopy(args[-1])
        broken.calls[0]['raw_arguments'].append(broken.calls)
        with self.assertRaises(ExecutionContextError):
            render_execution_context_json(broken)
        for limit in ('MAX_EXECUTION_CONTEXT_RECORDS', 'MAX_EXECUTION_CONTEXT_BYTES',
                      'MAX_EXECUTION_CONTEXT_JSON_BYTES', 'MAX_EVIDENCE_IDS'):
            with self.subTest(limit=limit), patch(f'plc_workbench.execution_context.{limit}', 1), self.assertRaises(ExecutionContextError):
                analyze_execution_context(*args[:-1])
        xml = document(program(routines=routine(text='JMP(L)LBL(L)LBL(L)LBL(L);')))
        args = capture_xml(xml)
        with patch('plc_workbench.execution_context.MAX_EVIDENCE_IDS', 5), self.assertRaises(ExecutionContextError):
            analyze_execution_context(*args[:-1])


if __name__ == '__main__':
    unittest.main()
