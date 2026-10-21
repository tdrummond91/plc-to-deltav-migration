"""Actual loopback routes keep translations separate from captured/reviewed data."""
from __future__ import annotations

from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from plc_workbench.workspace_translation import TranslationService
from test_workspace import running_workspace, saved_analysis
from test_workspace_translation import FakeEngine


class WorkspaceTranslationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixture.cleanup)
        cls.runs = Path(cls.fixture.name) / 'runs'
        cls.first = saved_analysis(cls.runs)
        cls.second = saved_analysis(cls.runs, controller='AnotherInventedController')

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project.sqlite'
        self.calls = []
        self.available = True

        def service(path):
            return TranslationService(path,
                engine_factory=lambda _: FakeEngine(self.calls),
                availability_provider=lambda _: {'available': self.available,
                    'model_id': 'test-fr-en-v1', 'message': 'Install local translation' if not self.available else 'Ready'})

        self.factory = patch('plc_workbench.workspace_translation.TranslationService', service)
        self.factory.start()
        self.addCleanup(self.factory.stop)

    def complete(self, client):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = client.get('/api/translation')
            if state['state'] != 'running':
                return state
            time.sleep(.01)
        self.fail('Invented translation batch did not finish')

    def import_first(self, client):
        return client.post('/api/import', {'path': str(self.first), 'expected_revision': 0})

    def test_enable_translates_prose_only_and_reopen_reuses_without_revision_change(self):
        with running_workspace(self.project, self.runs) as client:
            imported = self.import_first(client)
            rung = client.get('/api/rungs')['items'][0]
            original = client.get('/api/source?' + urlencode({'id': rung['id']}))
            self.assertFalse(client.get('/api/translation')['enabled'])
            self.assertEqual(self.calls, [])
            client.post('/api/translation', {'enabled': True, 'run_id': imported['active_run']})
            complete = self.complete(client)
            self.assertEqual(complete['state'], 'complete')
            self.assertEqual(complete['total'], 105)
            self.assertNotIn(rung['text'], self.calls)
            result = client.get('/api/translation?' + urlencode({'source_id': rung['id']}))
            self.assertEqual(result['fields']['comment']['text'], 'English: ' + rung['comment'])
            self.assertEqual(client.get('/api/source?' + urlencode({'id': rung['id']})), original)
            self.assertEqual(client.get('/api/state')['revision'], imported['revision'])
        calls = len(self.calls)
        with running_workspace(self.project, self.runs) as client:
            complete = self.complete(client)
            self.assertTrue(complete['enabled'])
            self.assertEqual(complete['cached'], complete['total'])
            self.assertEqual(len(self.calls), calls)

    def test_new_run_reuses_same_prose_and_stale_enable_rejected(self):
        with running_workspace(self.project, self.runs) as client:
            first = self.import_first(client)
            client.post('/api/translation', {'enabled': True, 'run_id': first['active_run']})
            self.complete(client)
            second = client.post('/api/import', {'path': str(self.second), 'expected_revision': first['revision']})
            state = self.complete(client)
            self.assertEqual(state['run_id'], second['active_run'])
            self.assertEqual(state['cached'], state['total'])
            self.assertEqual(client.request('/api/translation', payload={'enabled': False, 'run_id': first['active_run']})[0], 409)
            self.assertEqual(client.request('/api/translation?source_id=does-not-exist')[0], 400)

    def test_no_model_still_opens_source_and_can_display_cached_english(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.import_first(client)
            client.post('/api/translation', {'enabled': True, 'run_id': state['active_run']})
            self.complete(client)
            self.available = False
            rung = client.get('/api/rungs')['items'][0]
            result = client.get('/api/translation?' + urlencode({'source_id': rung['id']}))
            self.assertFalse(result['available'])
            self.assertTrue(result['fields']['comment']['text'])
            self.assertEqual(client.get('/api/state')['revision'], state['revision'])

    def test_routes_require_session_and_assets_stay_local(self):
        with running_workspace(self.project, self.runs) as client:
            for asset in ('reading-layout.js', 'reading-layout.css', 'translation.js', 'translation.css'):
                self.assertEqual(client.request('/' + asset)[0], 200)
            self.assertEqual(client.request('/api/translation', payload={'enabled': True},
                headers={'Origin': 'https://unrelated.invalid'})[0], 403)
            self.assertEqual(client.request('/api/translation', payload={'enabled': 'true'})[0], 400)
            self.assertEqual(self.calls, [])

    def test_restore_does_not_attach_previous_projects_translation_settings(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.import_first(client)
            client.post('/api/translation', {'enabled': True, 'run_id': state['active_run']})
            self.complete(client)
            backup = client.post('/api/backup', {})
            client.post('/api/restore', {'name': Path(backup['path']).name, 'expected_revision': state['revision']})
            self.assertFalse(client.get('/api/translation')['enabled'])


if __name__ == '__main__':
    unittest.main()
