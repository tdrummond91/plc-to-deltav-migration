"""Returned audit contains counts, never source strings or review decisions."""
from contextlib import closing
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from plc_workbench.workspace import Workspace
from test_workspace import running_workspace
from test_workspace_field_io import field_inputs, module
from test_workspace_map_api import save_map_inputs


class SignalAuditTests(unittest.TestCase):
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
                self.assertEqual(audit['inventory']['field_signal_addresses'], len(rows))
                self.assertEqual(audit['usage_counts']['referenced'], 1)
                self.assertGreater(audit['usage_counts']['not_found'], 0)
                for usage, count in audit['usage_counts'].items():
                    self.assertEqual(sum(audit['description_origins_by_usage'][usage].values()), count)
                    self.assertEqual(sum(audit['field_types_by_usage'][usage].values()), count)
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
