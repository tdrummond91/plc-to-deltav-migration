"""Returned audit contains counts, never source strings or review decisions."""
from contextlib import closing
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from plc_workbench.workspace import Workspace
from plc_workbench.workspace_signal_audit import build_audit
from test_workspace import running_workspace
from test_workspace_field_io import field_inputs, module
from test_workspace_field_signals import build
from test_workspace_map_api import save_map_inputs
from test_workspace_type_descriptions import definition, member, with_types
from test_workspace_signal_context import BOOLEAN, with_rung_comment


class SignalAuditTests(unittest.TestCase):
    def test_rung_context_audit_distinguishes_available_comment_and_remaining_blank_reasons(self) -> None:
        captured = with_rung_comment(field_inputs((BOOLEAN, 'XIC(Broken'),
            extra_tags='<Tag Name="Status" DataType="BOOL"/>'), 'SECRET_RUNG_WORDING')
        audit = build_audit(build(captured, related=False))
        self.assertEqual(audit['rung_comment_contexts_by_usage']['referenced'], 2)
        self.assertEqual(sum(audit['described_result_contexts_by_usage'].values()), 0)
        reasons = audit['description_diagnostics']['context_reason_counts']
        self.assertEqual(reasons['rung_comment'], 2)
        self.assertGreater(reasons['no_direct_use'], 0)
        self.assertEqual(sum(reasons.values()), audit['inventory']['field_signal_addresses'])
        case = audit['description_diagnostics']['anonymous_cases']['use_context']
        self.assertTrue(case['present'])
        self.assertEqual(case['context_kind_flags'], {'result_description': False, 'rung_comment': True})
        self.assertFalse(case['context_scope_complete'])
        rendered = json.dumps(audit)
        for secret in ('SECRET', 'Status', 'Local:', captured[1].rungs[0].id):
            self.assertNotIn(secret, rendered)

    def test_member_diagnostics_distinguish_missing_definition_blank_and_available_wording(self) -> None:
        for definitions, status in (('', 'no_type_definition'),
                (definition('InventedModule', member('Ch0Data', description='')), 'no_description'),
                (definition('InventedModule', member('Ch0Data', description='SECRET_PRESSURE')), 'available'),
                (definition('InventedModule', member('DifferentMember')), 'member_not_declared')):
            with self.subTest(status=status):
                captured = with_types(field_inputs(('MOV(Local:8:I.Ch0Data,InternalReal);',),
                    modules=module('SECRET_CARD', 8, 'INVENTED')), definitions)
                audit = build_audit(build(captured, related=False))
                diagnostics = audit['description_diagnostics']
                self.assertGreater(diagnostics['member_lookup_counts'][status], 0)
                profile = diagnostics['anonymous_cases']['type_member_inherited']
                self.assertEqual(profile['present'], status == 'available')
                if profile['present']:
                    self.assertEqual(profile['member_facts']['description_count'], 1)
                    self.assertEqual(profile['member_facts']['member_depth'], 1)
                    self.assertTrue(profile['member_lookup_flags']['available'])
                    self.assertTrue(profile['origin_flags']['type_member'])
                rendered = json.dumps(audit)
                for secret in ('SECRET', 'InventedModule', 'Ch0Data', 'DifferentMember', 'io_annotation_'):
                    self.assertNotIn(secret, rendered)

    def test_http_audit_censuses_all_rows_without_source_or_review_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs, project = root / 'runs', root / 'project.sqlite'
            source = field_inputs(('MOV(Local:8:I.Ch0Data,InternalReal);',),
                                  modules=module('SECRET_CARD', 8, 'INVENTED'))
            run = save_map_inputs(runs, source)
            with closing(Workspace(project, runs)) as workspace:
                state = workspace.import_run(str(run), 0)
                run_id = state['active_run']
                rows = workspace.field_signals({'run_id': run_id})['signals']['items']
                workspace.mutate({'op': 'signal', 'binding': rows[0]['binding'],
                    'target_name': 'SECRET_REVIEW', 'description': 'SECRET_COMMENT',
                    'field_type': rows[0]['field_type']}, state['revision'])
                before = workspace.store.state()
                snapshot = workspace.store.artifact('snapshot.L5X')
                # A census reuses the prepared projection, even while the
                # caller has search/usage/pagination filters on screen.
                with patch('plc_workbench.workspace_report.read_report_data',
                           side_effect=AssertionError('Do not reopen the full report')):
                    response = workspace.field_signal_audit({'run_id': run_id,
                        'query': 'NO_MATCH', 'usage': 'not_found', 'page_size': 10})
                audit = response['audit']
                self.assertEqual(audit['schema_version'], 3)
                self.assertEqual(audit['inventory']['field_signal_addresses'], len(rows))
                self.assertEqual(audit['usage_counts']['referenced'], 1)
                self.assertGreater(audit['usage_counts']['not_found'], 0)
                for usage, count in audit['usage_counts'].items():
                    self.assertEqual(sum(audit['description_origins_by_usage'][usage].values()), count)
                    self.assertEqual(sum(audit['field_types_by_usage'][usage].values()), count)
                diagnostics = audit['description_diagnostics']
                self.assertEqual(sum(diagnostics['context_reason_counts'].values()), len(rows))
                self.assertEqual(sum(diagnostics['member_lookup_counts'].values()), len(rows))
                self.assertEqual(diagnostics['member_lookup_counts']['no_type_definition'], len(rows))
                self.assertEqual(diagnostics['signals_with_retained_candidate_scope']['module_description'], len(rows))
                self.assertEqual(diagnostics['signals_with_truncated_candidate_list'], 0)
                cases = diagnostics['anonymous_cases']
                self.assertEqual(set(cases), {'used_missing', 'used_inherited', 'unreferenced_missing',
                    'unreferenced_inherited', 'type_member_inherited', 'use_context'})
                self.assertTrue(cases['used_inherited']['present'])
                self.assertTrue(cases['unreferenced_inherited']['present'])
                self.assertFalse(cases['type_member_inherited']['present'])
                for case in cases.values():
                    if case['present']:
                        self.assertEqual(sum(case['usage_flags'].values()), 1)
                        self.assertEqual(sum(case['origin_flags'].values()), 1)
                        self.assertEqual(sum(case['member_lookup_flags'].values()), 1)
                        self.assertLessEqual(sum(case['retained_candidate_scope_counts'].values()), case['candidate_count'])
                        self.assertEqual(case['alias_count'], 0)
                    else:
                        self.assertEqual(case, {'present': False})
                self.assertEqual(workspace.store.state(), before)
                self.assertEqual(workspace.store.artifact('snapshot.L5X'), snapshot)
                rendered = json.dumps(audit)
                for secret in ('SECRET', 'Local:', 'InternalReal', run_id, str(project), snapshot.decode()):
                    self.assertNotIn(secret, rendered)
                def closed(value: object) -> None:
                    if type(value) is dict:
                        for item in value.values():
                            closed(item)
                    else:
                        self.assertIn(type(value), (int, bool))
                closed(audit)
            with running_workspace(project, runs) as client:
                received = client.get('/api/field-signals-audit?' + urlencode({'run_id': run_id}))
                self.assertEqual(received['audit'], audit)
                self.assertEqual(received['run_id'], run_id)
                status, rejected = client.request('/api/field-signals-audit?' + urlencode({'run_id': 'stale-run'}))
                self.assertEqual(status, 400)
                self.assertIn('changed', rejected['error'])

    def test_an_unavailable_index_does_not_export_a_misleading_empty_census(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with closing(Workspace(root / 'project.sqlite', root / 'runs')) as workspace:
                run = save_map_inputs(root / 'runs', field_inputs())
                state = workspace.import_run(str(run), 0)
                with patch.object(workspace, '_field_signal_index', return_value=None):
                    from plc_workbench.project_store import ProjectError
                    with self.assertRaisesRegex(ProjectError, 'unavailable'):
                        workspace.field_signal_audit({'run_id': state['active_run']})
