"""Closed public execution-context counts reject impossible or private content."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.execution_context_summary import (ExecutionContextSummaryError,
    build_execution_context_summary, render_execution_context_summary, validate_execution_context_summary)
from test_execution_context import capture, capture_xml, document, program, routine, tag, task


class ExecutionContextSummaryTests(unittest.TestCase):
    def test_canonical_summary_contains_counts_only(self) -> None:
        args = capture('JSR(Sub,0268945)JMP(LabelSecret)LBL(LabelSecret)SBR(A)RET(A);',
            tasks=task(events='<EventInfo EventTag="PrivateEventTag"/>'))
        summary = build_execution_context_summary(*args, revision={'commit': 'a' * 40, 'worktree': 'clean'})
        text = render_execution_context_summary(summary)
        self.assertEqual(json.loads(text), summary)
        self.assertLessEqual(len(text.encode()), 8192)
        self.assertEqual(summary['coverage'], args[-1].coverage)
        self.assertEqual(summary['exporter_version'], 'execution-context-summary-1')
        for forbidden in ('0268945', 'LabelSecret', 'PrivateEventTag', 'condition_node_',
                          'execution_call_', 'source_locator', 'sha256:', 'raw_attributes'):
            self.assertNotIn(forbidden, text)

    def test_empty_partial_shape_namespace_and_ambiguity_summaries_validate(self) -> None:
        documents = [document(programs=''), document(program(routines='')),
            document(program(routines=routine(content=''))),
            document(program(routines=routine(language='ST', content='<STContent/>'))),
            document(program('P') + program('p'), tasks=task()),
            document(program(attributes='MainRoutineName="" FaultRoutineName="Lost"')),
            document(program(), tasks=task(events='<EventInfo x:Marker="foreign"/>'), root_attributes='xmlns:x="urn:foreign"'),
            document(program(), tasks=task('<ScheduledProgram/><ScheduledProgram Name=""/>')),
            document(program(routines=routine() + routine('main')))]
        for xml in documents:
            with self.subTest(xml=xml):
                summary = build_execution_context_summary(*capture_xml(xml))
                validate_execution_context_summary(summary)
        for text in (';', 'BROKEN(', 'JSR()', 'JSR(,)', 'JSR(Sub,0)', 'JSR(Lost,0);',
                     'JMP()JMP(,)JMP(Bad.Name)SBR()RET();', 'LBL(L)LBL(L)JMP(L);',
                     'XIC(Missing)JSR(Sub,0);', 'ONS(A)JSR(Sub,0);', '[MYSTERY(A),]JSR(Sub,0);'):
            with self.subTest(text=text):
                summary = build_execution_context_summary(*capture(text, tags=tag('A')))
                validate_execution_context_summary(summary)
        args = capture('XIC(B)JSR(Sub,0);', tags=tag('B', attributes='x:Marker="foreign"'),
                       root_attributes='xmlns:x="urn:foreign"')
        self.assertEqual(build_execution_context_summary(*args)['coverage']['guards_by_quality']['namespace_gap'], 1)

    def test_foreign_keys_booleans_revisions_and_constants_are_rejected(self) -> None:
        good = build_execution_context_summary(*capture())
        for mutate in (lambda s: s.update(source_name='private-marker'),
                lambda s: s['coverage']['source_control_opcodes'].update(SECRET=1),
                lambda s: s['coverage'].update(source_tasks=True),
                lambda s: s['coverage'].update(source_tasks=-1),
                lambda s: s['tool_revision'].update(commit='private-marker'),
                lambda s: s['tool_revision'].update(worktree='private-marker'),
                lambda s: s.update(schema_version=True),
                lambda s: s.update(execution_analysis='complete'),
                lambda s: s.update(status='partial')):
            bad = deepcopy(good)
            mutate(bad)
            with self.assertRaises(ExecutionContextSummaryError) as caught:
                validate_execution_context_summary(bad)
            self.assertNotIn('private-marker', str(caught.exception))

    def test_exact_partitions_source_totals_and_association_totals_are_enforced(self) -> None:
        good = build_execution_context_summary(*capture('JSR(Sub,0)JMP(L)LBL(L);', tasks=task()))
        for key in ('tasks_total', 'programs_total', 'schedules_total', 'designations_total',
                'calls_total', 'control_occurrences_total', 'routine_contexts_total', 'source_tasks',
                'source_programs', 'source_schedules', 'source_routines', 'event_info_total',
                'evidence_links', 'schedule_candidate_links', 'designation_candidate_links',
                'call_candidate_links', 'label_candidate_links'):
            bad = deepcopy(good)
            bad['coverage'][key] += 1
            with self.subTest(key=key), self.assertRaises(ExecutionContextSummaryError):
                validate_execution_context_summary(bad)
        for group, values in good['coverage'].items():
            if not isinstance(values, dict):
                continue
            bad = deepcopy(good)
            bad['coverage'][group][next(iter(values))] += 1
            with self.subTest(group=group), self.assertRaises(ExecutionContextSummaryError):
                validate_execution_context_summary(bad)

    def test_source_guard_argument_and_candidate_capacities_are_enforced(self) -> None:
        good = build_execution_context_summary(*capture('JSR(Sub,0)JMP(L)LBL(L);', tasks=task()))
        for mutate in (lambda c: c.update(source_instructions=0),
                lambda c: c.update(source_condition_nodes=0),
                lambda c: c.update(source_operands=0),
                lambda c: c.update(source_rungs=0),
                lambda c: c.update(unparsed_rungs=10),
                lambda c: c.update(programs_missing_type=10),
                lambda c: c.update(main_designation_gaps=10),
                lambda c: c.update(programs_with_schedules=0),
                lambda c: c.update(routines_with_incoming_calls=0),
                lambda c: c.update(routines_with_outgoing_calls=0),
                lambda c: c.update(routines_with_controls=0),
                lambda c: c.update(routines_with_designations=0),
                lambda c: c.update(routines_in_lexical_cycles=10),
                lambda c: c.update(guards_with_branches=10),
                lambda c: c.update(guards_with_stateful_conditions=10),
                lambda c: c.update(guards_with_namespace_gaps=1),
                lambda c: c.update(argument_fields=0),
                lambda c: c.update(empty_argument_fields=1),
                lambda c: c.update(other_edit_candidate_links=10, evidence_links=c['evidence_links'] + 10)):
            bad = deepcopy(good)
            mutate(bad['coverage'])
            with self.assertRaises(ExecutionContextSummaryError):
                validate_execution_context_summary(bad)

    def test_replay_and_private_public_resource_caps_are_enforced(self) -> None:
        args = capture(tasks=task())
        broken = deepcopy(args[-1])
        broken.calls[0]['guard_id'] = 'private-marker'
        with self.assertRaises(ExecutionContextSummaryError) as caught:
            build_execution_context_summary(*args[:-1], broken)
        self.assertNotIn('private-marker', str(caught.exception))
        good = build_execution_context_summary(*args)
        for name in ('MAX_EXECUTION_CONTEXT_RECORDS', 'MAX_EXECUTION_CONTEXT_BYTES',
                     'MAX_EXECUTION_CONTEXT_JSON_BYTES', 'MAX_EVIDENCE_IDS'):
            with patch(f'plc_workbench.execution_context_summary.{name}', 1), self.assertRaises(ExecutionContextSummaryError):
                validate_execution_context_summary(good)
        with patch('plc_workbench.execution_context_summary.MAX_REPORT_BYTES', 20), self.assertRaises(ExecutionContextSummaryError):
            render_execution_context_summary(good)


if __name__ == '__main__':
    unittest.main()
