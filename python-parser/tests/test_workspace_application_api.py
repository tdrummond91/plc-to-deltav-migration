"""Application browsing shares authenticated evidence and never writes reviews."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from plc_workbench.project_store import ProjectError
from plc_workbench.workspace import Workspace
from plc_workbench.workspace_application import ApplicationError, ApplicationIndex
from plc_workbench.workspace_variables import VariableIndex
from test_workspace import running_workspace
from test_workspace_field_io import field_inputs, module
from test_workspace_map_api import save_map_inputs


class WorkspaceApplicationAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixtures.cleanup)
        cls.runs = Path(cls.fixtures.name) / 'runs'
        cls.inputs = field_inputs()
        cls.first = save_map_inputs(cls.runs, cls.inputs)
        cls.later = save_map_inputs(cls.runs, field_inputs(modules=module('LaterCard', 1, '1756-IB16')))

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name) / 'project.sqlite'
        self.workspace = Workspace(self.project, self.runs)
        self.addCleanup(self.workspace.close)
        self.run_id = self.workspace.import_run(str(self.first), 0)['active_run']
        self.query = {'run_id': self.run_id}

    def test_readonly_shared_index_and_canonical_source_links(self) -> None:
        before = self.workspace.store.state()
        changes = self.workspace.store.connection.total_changes
        with patch('plc_workbench.workspace_variables.VariableIndex', wraps=VariableIndex) as base, \
             patch('plc_workbench.workspace_application.ApplicationIndex', wraps=ApplicationIndex) as application:
            view = self.workspace.application(self.query)
            self.workspace.field_io(self.query)
            self.workspace.application(dict(self.query, direction='input'))
        self.assertTrue(view['available'])
        self.assertEqual((base.call_count, application.call_count), (1, 1))
        self.assertEqual(self.workspace.store.state(), before)
        self.assertEqual(self.workspace.store.connection.total_changes, changes)
        for row in view['registers']['items']:
            detail = self.workspace.application(dict(self.query, register_id=row['id']))
            self.assertEqual(detail['selected_register']['id'], row['id'])
            self.assertIn(row['source_id'], self.workspace._variable_index(self.run_id)._entities)

    def test_historical_browsing_does_not_change_active_run(self) -> None:
        self.workspace.application(self.query)
        newer = self.workspace.import_run(str(self.later), self.workspace.store.state()['revision'])
        before, loaded = self.workspace.store.state(), self.workspace._run
        old = self.workspace.application(self.query)
        new = self.workspace.application({'run_id': newer['active_run']})
        self.assertTrue(old['historical'])
        self.assertFalse(new['historical'])
        self.assertEqual((old['modules']['total'], new['modules']['total']), (6, 2))
        self.assertEqual(self.workspace.store.state(), before)
        self.assertEqual(self.workspace._run, loaded)

    def test_failed_evidence_is_cached_without_leaking_parser_errors(self) -> None:
        db = self.workspace.store.connection
        db.execute('UPDATE artifacts SET data=? WHERE run_id=? AND name=?',
                   (b'{"PRIVATE_CORRUPTION":', self.run_id, 'references.json'))
        db.commit()
        with patch('plc_workbench.workspace_application.ApplicationIndex', wraps=ApplicationIndex) as constructor:
            first = self.workspace.application(self.query)
            second = self.workspace.application(self.query)
        self.assertFalse(first['available'])
        self.assertFalse(second['available'])
        self.assertNotIn('PRIVATE_CORRUPTION', str(first))
        self.assertEqual(first['reason'], 'evidence_unavailable')
        self.assertEqual(constructor.call_count, 0)

    def test_shared_failure_is_identified_on_both_pages_and_keeps_saved_state(self) -> None:
        before = self.workspace.store.state()
        original = self.workspace.store.artifact('snapshot.L5X')
        db = self.workspace.store.connection
        db.execute('UPDATE artifacts SET data=? WHERE run_id=? AND name=?',
                   (b'{"PRIVATE_TAG_DATA":', self.run_id, 'tag-data.json'))
        db.commit()
        for method in (self.workspace.application, self.workspace.field_signals, self.workspace.field_io):
            result = method(self.query)
            self.assertFalse(result['available'])
            self.assertEqual(result['diagnostic'], {'stage': 'tag_data', 'reason': 'invalid_evidence'})
            self.assertIn('[tag_data/invalid_evidence]', result['notice'])
            self.assertNotIn('PRIVATE_TAG_DATA', str(result))
        self.assertEqual(self.workspace.store.state(), before)
        self.assertEqual(self.workspace.store.artifact('snapshot.L5X'), original)

    def test_shared_capacity_failure_survives_cached_reads_and_does_not_change_run(self) -> None:
        before = self.workspace.store.state()
        with patch('plc_workbench.workspace_variables.MAX_INDEX_BYTES', 1):
            first = self.workspace.application(self.query)
        second = self.workspace.field_signals(self.query)
        self.assertFalse(first['available'])
        self.assertFalse(second['available'])
        self.assertEqual(first['diagnostic'], second['diagnostic'])
        self.assertEqual(first['diagnostic']['stage'], 'variable_index')
        self.assertEqual(first['diagnostic']['reason'], 'index_bytes_limit')
        self.assertEqual(first['diagnostic']['limit'], 1)
        self.assertGreater(first['diagnostic']['actual'], 1)
        self.assertEqual(self.workspace.store.state(), before)

    def test_http_reports_shared_loader_stage_without_exception_or_source_text(self) -> None:
        db = self.workspace.store.connection
        db.execute('UPDATE artifacts SET data=? WHERE run_id=? AND name=?',
                   (b'{"PRIVATE_TAG_DATA":', self.run_id, 'tag-data.json'))
        db.commit()
        with running_workspace(self.project, self.runs) as client:
            before = client.get('/api/state')
            for route in ('/api/application?', '/api/field-signals?', '/api/field-io?'):
                result = client.get(route + urlencode(self.query))
                self.assertFalse(result['available'])
                self.assertEqual(result['diagnostic'], {'stage': 'tag_data', 'reason': 'invalid_evidence'})
                self.assertNotIn('PRIVATE_TAG_DATA', str(result))
                self.assertIn('[tag_data/invalid_evidence]', result['notice'])
            self.assertEqual(client.get('/api/state'), before)


    def test_projection_capacity_is_cached_and_explained_without_altering_the_run(self) -> None:
        before = self.workspace.store.state()
        with patch('plc_workbench.workspace_application.MAX_INDEX_BYTES', 1), \
             patch('plc_workbench.workspace_application.ApplicationIndex', wraps=ApplicationIndex) as constructor:
            first = self.workspace.application(self.query)
            second = self.workspace.application(self.query)
        self.assertFalse(first['available'])
        self.assertEqual(first['reason'], 'application_capacity')
        self.assertIn('saved analysis is still present', first['notice'])
        self.assertIn('Re-running an unchanged analysis will not resolve', first['notice'])
        self.assertEqual(second['reason'], first['reason'])
        self.assertEqual(constructor.call_count, 1)
        self.assertEqual(self.workspace.store.state(), before)

    def test_invalid_projection_reason_does_not_leak_exception_content(self) -> None:
        with patch('plc_workbench.workspace_application.ApplicationIndex',
                   side_effect=ApplicationError('PRIVATE_SOURCE_DETAIL')):
            result = self.workspace.application(self.query)
        self.assertEqual(result['reason'], 'application_evidence_invalid')
        self.assertNotIn('PRIVATE_SOURCE_DETAIL', str(result))

    def test_restore_invalidates_projection(self) -> None:
        with patch('plc_workbench.workspace_application.ApplicationIndex', wraps=ApplicationIndex) as constructor:
            self.workspace.application(self.query)
            backup = Path(self.workspace.backup()['path'])
            self.workspace.restore(backup.name, self.workspace.store.state()['revision'])
            self.workspace.application(self.query)
        self.assertEqual(constructor.call_count, 2)

    def test_restore_clears_failure_before_a_different_layer_fails_on_the_same_run(self) -> None:
        backup = Path(self.workspace.backup()['path'])
        with patch('plc_workbench.workspace_variables.MAX_INDEX_BYTES', 1):
            failed = self.workspace.application(self.query)
        self.assertEqual(failed['diagnostic']['stage'], 'variable_index')
        self.workspace.restore(backup.name, self.workspace.store.state()['revision'])
        self.assertFalse(self.workspace._evidence_failures)
        with patch('plc_workbench.workspace_field_io.MAX_INDEX_BYTES', 1):
            failed = self.workspace.application(self.query)
        self.assertEqual(failed['diagnostic']['stage'], 'field_io')
        self.assertEqual(failed['diagnostic']['reason'], 'index_bytes_limit')

    def test_translation_is_cached_wording_and_does_not_mutate_evidence(self) -> None:
        class CachedTranslator:
            def status(self):
                return {'presentation_mode': 'both'}

            def lookup_many(self, texts):
                return {text: {'state': 'ready', 'text': 'Cached English', 'original': text} for text in texts}

        original = deepcopy(self.workspace.store.inventory(self.run_id))
        with patch.object(self.workspace, '_translator', return_value=CachedTranslator()):
            view = self.workspace.application(self.query)
        row = next(row for row in view['modules']['items'] if row['description'])
        self.assertEqual(row['wording']['description']['text'], 'Cached English')
        self.assertNotEqual(row['description'], 'Cached English')
        self.assertEqual(self.workspace.store.inventory(self.run_id), original)

    def test_response_limit_and_http_boundary(self) -> None:
        with patch('plc_workbench.workspace_application.MAX_RESPONSE_BYTES', 20):
            with self.assertRaises(ProjectError):
                self.workspace.application(self.query)
        with running_workspace(self.project, self.runs) as client:
            route = '/api/application?' + urlencode(self.query)
            self.assertTrue(client.get(route)['available'])
            for path in ('/api/application', route + '&page=0', route + '&register_id=foreign',
                         route + '&module_id=foreign', route + '&direction=physical'):
                self.assertEqual(client.request(path)[0], 400)
            self.assertEqual(client.request(route, headers={'Origin': 'https://outside.invalid'})[0], 403)
            for path in ('/application-map.js', '/application-map.css'):
                self.assertEqual(client.request(path)[0], 200)

    def test_long_selected_wording_uses_full_translation_cache_key(self) -> None:
        description = 'Invented exact member wording. ' * 90
        inputs = field_inputs(extra_tags='<Tag Name="LongDescription" DataType="REAL">'
                              f'<Description>{description}</Description></Tag>')
        run = save_map_inputs(self.runs, inputs)
        current = self.workspace.import_run(str(run), self.workspace.store.state()['revision'])
        seen = []

        class CachedTranslator:
            def status(self):
                return {'presentation_mode': 'en'}

            def lookup_many(self, texts):
                originals = list(texts)
                seen.extend(originals)
                return {value: {'state': 'ready', 'text': 'Full cached wording', 'original': value}
                        for value in originals if value == description}

        with patch.object(self.workspace, '_translator', return_value=CachedTranslator()):
            query = {'run_id': current['active_run'], 'query': 'LongDescription'}
            view = self.workspace.application(query)
            row = view['registers']['items'][0]
            detail = self.workspace.application(dict(query, register_id=row['id']))['selected_register']
        self.assertIn(description, seen)
        self.assertEqual(row['wording']['description']['text'], 'Full cached wording')
        self.assertEqual(detail['source_annotations'][0]['wording']['text'], 'Full cached wording')


if __name__ == '__main__':
    unittest.main()
