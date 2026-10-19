"""Invented call boundaries retain lexical evidence without parameter roles."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch

from plc_workbench import execution_context as execution
from plc_workbench.execution_context_summary import (
    ExecutionContextSummaryError, build_execution_context_summary,
    render_execution_context_summary, validate_execution_context_summary,
)
from test_execution_context import capture, capture_xml, document, program, routine, tag


def capture_v2(xml=None):
    parts = capture_xml(xml) if xml is not None else capture()
    return (*parts[:-1], execution.analyze_execution_context(*parts[:-1], schema_version=2))


def source(calls='JSR(Sub,0);', body='SBR(Input)RET(Output);', *, tags=None, target=None, extra=''):
    return document(program(routines=routine(text=calls) + (routine('Sub', body) if target is None else target)) + extra,
                    tags=tag('Input') + tag('Output') if tags is None else tags)


class RoutineBoundaryTests(unittest.TestCase):
    def test_schema1_default_and_explicit_bytes_are_frozen(self):
        parts = capture()
        private = execution.render_execution_context_json(parts[-1])
        public = render_execution_context_summary(build_execution_context_summary(*parts))
        self.assertEqual(hashlib.sha256(private.encode()).hexdigest(),
                         'd935fe9a554c1412efc4af2351dc85ee2819946021849d170410afd1b0a7bba5')
        self.assertEqual(hashlib.sha256(public.encode()).hexdigest(),
                         '7e928d73d3cc66b12fbfef6fa2679c1dfcec15bd1634a1d879f3a5f00da35355')
        self.assertEqual(private, execution.render_execution_context_json(
            execution.analyze_execution_context(*parts[:-1], schema_version=1)))
        self.assertTrue(execution._V2_FIELDS.isdisjoint(parts[-1].to_dict()))
        with self.assertRaises(execution.ExecutionContextError):
            execution.render_execution_context_json(replace(parts[-1], argument_contexts=[{}]))

    def test_repeated_calls_share_exact_content_boundaries_and_keep_fields_unassigned(self):
        parts = capture_v2(source(calls='JSR(Sub,0)JSR(Sub,1,Input)JSR(Sub,1,Output);'))
        result = parts[-1]
        contents = {row['id']: row for row in result.boundary_contents}
        self.assertEqual(len(result.call_boundaries), 3)
        self.assertEqual(len({row['target_content_id'] for row in result.call_boundaries}), 1)
        target = contents[result.call_boundaries[0]['target_content_id']]
        self.assertEqual((len(target['sbr_control_ids']), len(target['ret_control_ids'])), (1, 1))
        self.assertEqual(result.coverage['boundary_sbr_occurrences'], 1)
        self.assertEqual(result.coverage['sbr_target_calls_by_shape']['three_or_more_second_other'], 2)
        self.assertEqual(result.coverage['distinct_associated_contents'], 1)
        self.assertTrue(all(row['boundary_profile'] == 'sbr_and_ret' for row in result.call_boundaries))
        operand_ids = {row['id'] for row in parts[2].operands}
        self.assertTrue(all(row['operand_id'] in operand_ids for row in result.argument_contexts))
        self.assertEqual(result.parameter_roles, 'not_analyzed')
        self.assertEqual(result.parameter_types, 'not_analyzed')
        self.assertEqual(result.call_validation, 'not_analyzed')
        self.assertTrue(all('role' not in row and 'parameter_index' not in row for row in result.argument_contexts))
        self.assertTrue(all(row['status'] == 'unsupported_instruction' for row in parts[2].operands))
        before = [deepcopy(item.to_dict()) for item in parts[1:-1]]
        execution.validate_execution_context(*parts)
        self.assertEqual(before, [item.to_dict() for item in parts[1:-1]])

    def test_decimal_second_fields_are_spelling_observations_only(self):
        fields = ('0', '00', '1', '+0', '-0', '0.0', "'0'", 'Input', '')
        parts = capture_v2(source(calls=''.join(f'JSR(Sub,{value})' for value in fields) + 'JSR(Sub)JSR();'))
        result = parts[-1]
        self.assertEqual([row['second_field_kind'] for row in result.call_boundaries],
            ['exact_zero', 'other_ascii_decimal', 'other_ascii_decimal', 'other', 'other', 'other', 'other', 'other', 'empty', 'absent', 'absent'])
        self.assertTrue(all('input_count' not in row and 'input_parameters' not in row for row in result.call_boundaries))
        validate_execution_context_summary(build_execution_context_summary(*parts))

    def test_multiple_returns_are_preserved_without_selecting_an_exit(self):
        result = capture_v2(source(body='SBR(Input)RET(Output)RET(Input);'))[-1]
        target = next(row for row in result.boundary_contents if row['sbr_control_ids'])
        self.assertEqual(len(target['ret_control_ids']), 2)
        self.assertEqual(result.coverage['ret_target_calls_by_shape']['two_fields_second_zero'], 1)
        self.assertEqual(result.execution_analysis, 'not_implemented')

    def test_missing_multiple_unsupported_and_incomplete_target_contents_stay_distinct(self):
        variants = (
            (routine('Sub', content=''), 'missing_content'),
            (routine('Sub', content='<RLLContent/><RLLContent/>'), 'multiple_contents'),
            (routine('Sub', content='<RLLContent/><STContent/>'), 'multiple_contents'),
            (routine('Sub', language='ST', content='<STContent/>'), 'unsupported_language'),
            (routine('Sub', content='<STContent/>'), 'unsupported_context'),
            (routine('Sub', content='<RLLContent><Unexpected/></RLLContent>'), 'incomplete_content'),
            (routine('Sub', 'BROKEN('), 'incomplete_content'),
            (routine('Sub', content='<RLLContent><Rung Number="0"/></RLLContent>'), 'incomplete_content'),
        )
        for target, expected in variants:
            with self.subTest(expected=expected, target=target):
                parts = capture_v2(source(target=target))
                row = parts[-1].call_boundaries[0]
                self.assertEqual(row['status'], expected)
                self.assertEqual(row['boundary_profile'], 'not_available')
                if expected == 'multiple_contents': self.assertIsNone(row['target_content_id'])
                validate_execution_context_summary(build_execution_context_summary(*parts))

    def test_namespaces_and_protection_block_content_and_field_associations(self):
        for marker, status in (('x:Marker="foreign"', 'namespace_gap'), ('Protected="false"', 'protected'),
                               ('IsEncrypted="true"', 'protected')):
            with self.subTest(marker=marker):
                xml = source().replace('<RSLogix5000Content ', '<RSLogix5000Content xmlns:x="urn:foreign" ')
                xml = xml.replace('<RLLContent>', f'<RLLContent {marker}>')
                parts = capture_v2(xml)
                self.assertEqual(parts[-1].call_boundaries[0]['status'], status)
                non_targets = [row for row in parts[-1].argument_contexts if row['status'] != 'routine_target']
                self.assertTrue(all(row['status'] == status for row in non_targets))
                self.assertTrue(all(row['target_id'] is None for row in non_targets))
                validate_execution_context_summary(build_execution_context_summary(*parts))
        target = routine('Sub', content='<RLLContent/><EncodedData/>')
        self.assertEqual(capture_v2(source(target=target))[-1].call_boundaries[0]['status'], 'protected')
        target = routine('Sub', content='<Description xmlns="urn:foreign"/><RLLContent/>')
        self.assertEqual(capture_v2(source(target=target))[-1].call_boundaries[0]['status'], 'namespace_gap')

    def test_program_scope_duplicate_targets_and_controller_locality_are_preserved(self):
        first = program('P', routine(text='JSR(Sub,Input);') + routine('Sub', 'SBR(Input);'))
        second = program('Q', routine(text='JSR(Sub,Output);') + routine('Sub', 'RET(Output);'))
        parts = capture_v2(document(first + second, tags=tag('Input') + tag('Output')))
        self.assertEqual([row['boundary_profile'] for row in parts[-1].call_boundaries], ['sbr_only', 'ret_only'])
        self.assertEqual(parts[-1].coverage['distinct_associated_contents'], 2)
        duplicate = routine('Sub') + routine('sub')
        result = capture_v2(source(target=duplicate))[-1]
        self.assertEqual(result.call_boundaries[0]['status'], 'target_unavailable')
        self.assertIsNone(result.call_boundaries[0]['target_content_id'])
        self.assertEqual(capture_v2(source(calls='JSR(Missing,0);'))[-1].call_boundaries[0]['status'], 'target_unavailable')

    def test_uncalled_boundaries_are_not_inflated_into_call_counts(self):
        parts = capture_v2(source(calls='NOP();'))
        c = parts[-1].coverage
        self.assertEqual((c['boundary_sbr_occurrences'], c['boundary_ret_occurrences']), (1, 1))
        self.assertEqual(c['call_boundaries_total'], 0)
        self.assertEqual(sum(c['sbr_target_calls_by_shape'].values()), 0)
        validate_execution_context_summary(build_execution_context_summary(*parts))

    def test_aoi_owned_boundaries_do_not_acquire_program_tag_candidates(self):
        aoi = ('<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="Widget"><Routines>'
               + routine('Logic', 'SBR(Input)RET(Output);')
               + '</Routines></AddOnInstructionDefinition></AddOnInstructionDefinitions>')
        parts = capture_v2(document(extra=aoi, tags=tag('Input') + tag('Output')))
        self.assertEqual(parts[-1].coverage['unprofiled_boundary_occurrences'], 2)
        self.assertEqual(parts[-1].coverage['argument_contexts_by_status']['unsupported_context'], 2)
        validate_execution_context_summary(build_execution_context_summary(*parts))

    def test_lexical_candidates_preserve_aliases_static_suffixes_and_unresolved_reasons(self):
        tags = tag('Root') + tag('Alias', alias='Root.Part') + tag('Loop', alias='Loop')
        calls = 'JSR(Sub,Alias[2],Root.Unknown,Root[Index],Missing,Loop,1);'
        parts = capture_v2(source(calls=calls, body='RET();', tags=tags))
        rows = parts[-1].argument_contexts
        self.assertEqual([row['status'] for row in rows], ['routine_target', 'root_bound_candidate',
            'root_bound_candidate', 'unsupported_address', 'unresolved', 'alias_cycle', 'literal'])
        self.assertEqual(rows[1]['suffix'], '.Part[2]')
        self.assertEqual(len(rows[1]['alias_chain']), 1)
        self.assertEqual(rows[2]['suffix'], '.Unknown')
        self.assertEqual(rows[3]['reason'], 'non_static_array_index')
        self.assertEqual(rows[4]['reason'], 'root_not_declared')
        validate_execution_context_summary(build_execution_context_summary(*parts))

    def test_program_shadowing_and_alias_declaration_scope_are_kept(self):
        tags = tag('Root') + tag('GlobalAlias', alias='Root')
        xml = source(calls='JSR(Sub,Root,GlobalAlias);', body='RET();', tags=tags)
        xml = xml.replace('<Routines>', '<Tags>' + tag('Root') + '</Tags><Routines>', 1)
        parts = capture_v2(xml)
        names = {entity.id: entity for entity in parts[1].entities}
        local, alias = parts[-1].argument_contexts[1:]
        self.assertNotEqual(local['target_id'], alias['target_id'])
        self.assertEqual(names[names[local['target_id']].scope_id].kind, 'program')
        self.assertEqual(names[names[alias['target_id']].scope_id].kind, 'controller')

    def test_foreign_or_protected_alias_targets_do_not_form_candidates(self):
        for marker, status in (('x:Marker="foreign"', 'namespace_gap'), ('Protected="true"', 'protected')):
            xml = source(calls='JSR(Sub,Alias);', body='RET();', tags=tag('Root', attributes=marker) + tag('Alias', alias='Root'))
            xml = xml.replace('<RSLogix5000Content ', '<RSLogix5000Content xmlns:x="urn:foreign" ')
            row = capture_v2(xml)[-1].argument_contexts[1]
            self.assertEqual(row['status'], status)
            self.assertIsNone(row['target_id'])
            self.assertEqual(row['alias_chain'], [])

    def test_two_edits_never_select_one_boundary_content(self):
        target = routine('Sub', content=(
            '<RLLContent Type="Original"><Rung Number="0"><Text>SBR(Input);</Text></Rung></RLLContent>'
            '<RLLContent Type="Edited"><Rung Number="0"><Text>RET(Output);</Text></Rung></RLLContent>'))
        result = capture_v2(source(target=target))[-1]
        self.assertEqual(result.call_boundaries[0]['status'], 'multiple_contents')
        self.assertIsNone(result.call_boundaries[0]['target_content_id'])
        profiles = [row for row in result.boundary_contents if row['raw_attributes']]
        self.assertEqual([row['raw_attributes']['Type'] for row in profiles], ['Original', 'Edited'])

    def test_replay_rejects_forged_links_roles_counts_and_versions(self):
        parts = capture_v2(source())
        changes = (
            lambda r: r.call_boundaries[0].update(target_content_id=r.boundary_contents[0]['id']),
            lambda r: r.boundary_contents[-1]['ret_control_ids'].clear(),
            lambda r: r.argument_contexts[1].update(status='root_bound_candidate'),
            lambda r: r.argument_contexts[-1].update(argument_index=17),
            lambda r: r.coverage.update(distinct_associated_contents=0),
        )
        for change in changes:
            bad = deepcopy(parts[-1]); change(bad)
            with self.assertRaises(execution.ExecutionContextError): execution.validate_execution_context(*parts[:-1], bad)
        for version in (True, 0, 4, '2'):
            with self.assertRaises(execution.ExecutionContextError):
                execution.analyze_execution_context(*parts[:-1], schema_version=version)

    def test_new_rows_and_links_obey_resource_bounds_before_rendering(self):
        parts = capture_v2(source(calls='JSR(Sub,Input)' * 20 + ';'))
        rendered = execution.render_execution_context_json(parts[-1])
        with patch('plc_workbench.execution_context.MAX_EXECUTION_CONTEXT_JSON_BYTES', len(rendered.encode())):
            self.assertEqual(execution.render_execution_context_json(parts[-1]), rendered)
        with patch('plc_workbench.execution_context.MAX_EXECUTION_CONTEXT_JSON_BYTES', len(rendered.encode()) - 1):
            with self.assertRaises(execution.ExecutionContextError): execution.validate_execution_context(*parts)
        base = execution.analyze_execution_context(*parts[:-1])
        with patch('plc_workbench.execution_context.MAX_EVIDENCE_IDS', base.coverage['evidence_links']):
            with self.assertRaises(execution.ExecutionContextError): execution._with_boundaries(parts[0], parts[1], parts[2], base)
        with patch('plc_workbench.execution_context.MAX_EXECUTION_CONTEXT_BYTES', len(execution.render_execution_context_json(base).encode()) + 95):
            with self.assertRaises(execution.ExecutionContextError): execution._with_boundaries(parts[0], parts[1], parts[2], base)
        bad = deepcopy(parts[-1]); bad.argument_contexts.append(bad.argument_contexts)
        with self.assertRaises(execution.ExecutionContextError): execution.render_execution_context_json(bad)


class RoutineBoundarySummaryTests(unittest.TestCase):
    def test_summary_is_closed_and_uses_no_source_text_or_identities(self):
        summary = build_execution_context_summary(*capture_v2(source()))
        text = render_execution_context_summary(summary)
        self.assertEqual(json.loads(text), summary)
        self.assertEqual(summary['schema_version'], 2)
        self.assertLess(len(text.encode()), 8192)
        for token in ('Main', 'Input', 'Output', 'source_locator', 'execution_call_', 'operand_', 'sha256:'):
            self.assertNotIn(token, text)

    def test_maximum_width_bound_fits_the_existing_eight_kib_summary_cap(self):
        summary = build_execution_context_summary(*capture_v2(source()))
        for key, value in summary['coverage'].items():
            summary['coverage'][key] = ({name: execution.MAX_EVIDENCE_IDS for name in value}
                if isinstance(value, dict) else execution.MAX_EVIDENCE_IDS)
        summary['tool_revision'] = {'commit': 'a' * 40, 'worktree': 'modified'}
        # Deliberately simultaneous, infeasible maxima are a serialization upper
        # bound: every schema2 scalar is explicitly limited to MAX_EVIDENCE_IDS.
        self.assertLess(len((json.dumps(summary, sort_keys=True, indent=2) + '\n').encode()), 8192)

    def test_public_partitions_and_cross_population_bounds_reject_forgery(self):
        good = build_execution_context_summary(*capture_v2(source()))
        changes = (
            lambda s: s.update(schema_version=True),
            lambda s: s.update(parameter_roles='mapped'),
            lambda s: s['coverage']['argument_contexts_by_status'].update(write=1),
            lambda s: s['coverage'].update(boundary_contents_total=True),
            lambda s: s['coverage'].update(boundary_evidence_links=0),
            lambda s: s['coverage'].update(distinct_associated_contents=0),
            lambda s: s['coverage'].update(calls_with_target_content=0),
            lambda s: s['coverage'].update(argument_alias_links=1),
            lambda s: s['coverage']['calls_by_boundary_profile'].update(sbr_and_ret=0, not_available=1),
            lambda s: s['coverage']['calls_by_second_field_kind'].update(exact_zero=0, other=1),
            lambda s: s['coverage']['argument_contexts_by_opcode'].update(JSR=1, SBR=2),
            lambda s: s['coverage'].update(boundary_rungs_total=execution.MAX_EVIDENCE_IDS + 1),
        )
        for change in changes:
            bad = deepcopy(good); change(bad)
            with self.assertRaises(ExecutionContextSummaryError): validate_execution_context_summary(bad)
        with patch('plc_workbench.execution_context_summary.MAX_REPORT_BYTES', 100):
            with self.assertRaises(ExecutionContextSummaryError): render_execution_context_summary(good)

    def test_summary_cannot_invent_content_without_an_owning_program_routine(self):
        bad = build_execution_context_summary(*capture_v2(document(programs='')))
        bad['coverage'].update(boundary_contents_total=1, boundary_evidence_links=1)
        bad['coverage']['boundary_contents_by_status']['qualified_rll'] = 1
        with self.assertRaises(ExecutionContextSummaryError): validate_execution_context_summary(bad)


if __name__ == '__main__':
    unittest.main()
