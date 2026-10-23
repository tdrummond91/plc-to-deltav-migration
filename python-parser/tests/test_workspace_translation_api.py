"""Actual loopback routes keep translations separate from captured/reviewed data."""
from __future__ import annotations

from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from plc_workbench.workspace_translation import TranslationService
from plc_workbench.workspace import Workspace
from plc_workbench.workspace_report import refresh_report
from test_prepare_english import report_overlay, saved_prose_analysis
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
        cls.prose = saved_prose_analysis(cls.runs)
        cls.prose_second = saved_prose_analysis(cls.runs, controller='AnotherInventedTranslation')

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project.sqlite'
        self.calls = []
        self.available = True
        self.callback = None

        def service(path):
            return TranslationService(path,
                engine_factory=lambda _: FakeEngine(self.calls, callback=self.callback),
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

    def test_incomplete_wording_is_not_pending_after_new_import_or_restart(self):
        def incomplete(text):
            if text == 'Arreter la pompe':
                return {'text': text, 'status': 'needs_review', 'translated_segments': 0, 'retained_segments': 1}
            if text == 'Niveau bas':
                return {'text': 'Low niveau', 'status': 'needs_review', 'translated_segments': 1, 'retained_segments': 1}
            return {'text': text, 'status': 'translated'}

        self.callback = incomplete
        with running_workspace(self.project, self.runs) as client:
            first = client.post('/api/import', {'path': str(self.prose), 'expected_revision': 0})
            client.post('/api/translation', {'presentation_mode': 'english', 'prepare': True, 'run_id': first['active_run']})
            status = self.complete(client)
            self.assertEqual((status['failed'], status['partial']), (1, 1))
            calls = self.calls.copy()
            client.post('/api/import', {'path': str(self.prose_second), 'expected_revision': first['revision']})
            status = self.complete(client)
            self.assertEqual((status['cached'], status['completed']), (status['total'], status['total']))
            self.assertEqual((status['cached_incomplete'], status['new_texts'], status['retry_texts']), (2, 0, 0))
            self.assertEqual(self.calls, calls)
        with running_workspace(self.project, self.runs) as client:
            status = self.complete(client)
            self.assertEqual((status['cached'], status['completed']), (status['total'], status['total']))
            self.assertEqual((status['failed'], status['partial'], status['cached_incomplete']), (1, 1, 2))
            self.assertEqual(self.calls, calls)
            client.post('/api/translation', {'presentation_mode': 'english', 'prepare': True, 'run_id': status['run_id']})
            self.complete(client)
            self.assertEqual(self.calls, calls)
            client.post('/api/translation', {'presentation_mode': 'english', 'prepare': True, 'retry': True, 'run_id': status['run_id']})
            status = self.complete(client)
            self.assertEqual(status['retry_texts'], status['total'])
            self.assertEqual(len(self.calls), len(calls) * 2)

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

    def test_english_mode_search_and_lists_keep_originals_and_instruction_code(self):
        with running_workspace(self.project, self.runs) as client:
            imported = client.post('/api/import', {'path': str(self.prose), 'expected_revision': 0})
            client.post('/api/translation', {'presentation_mode': 'english', 'prepare': True,
                                           'run_id': imported['active_run']})
            self.assertEqual(self.complete(client)['state'], 'complete')
            rungs = client.get('/api/rungs?' + urlencode({'query': 'English: Arreter'}))
            self.assertEqual((rungs['total'], rungs['presentation_mode']), (1, 'english'))
            self.assertEqual(rungs['items'][0]['comment'], 'Arreter la pompe')
            self.assertEqual(rungs['items'][0]['wording']['comment']['text'], 'English: Arreter la pompe')
            self.assertEqual(rungs['items'][0]['text'], 'XIC(Input)OTE(Output);')
            objects = client.get('/api/objects?' + urlencode({'query': 'English: Niveau'}))
            self.assertEqual(objects['total'], 1)
            row = objects['items'][0]
            self.assertEqual(row['description'], 'Niveau bas')
            self.assertFalse(row['description_is_code'])
            self.assertEqual(row['wording']['description']['text'], 'English: Niveau bas')
            instructions = client.get('/api/objects?kind=instruction')['items']
            self.assertEqual({row['description'] for row in instructions},
                             {'XIC(Input)', 'OTE(Output)', 'XIO(Input)', 'OTL(Output)'})
            self.assertTrue(all(row['description_is_code'] and row['wording']['description'] is None for row in instructions))
            self.assertTrue(all('XIC(' not in text and 'OTE(' not in text for text in self.calls))
            self.assertEqual(client.get('/api/state')['revision'], imported['revision'])
            client.post('/api/translation', {'presentation_mode': 'original', 'prepare': False,
                                           'run_id': imported['active_run']})
            self.assertTrue(client.get('/api/translation')['enabled'])
        with running_workspace(self.project, self.runs) as client:
            status = self.complete(client)
            self.assertEqual(status['presentation_mode'], 'original')
            self.assertEqual(status['cached'], status['total'])
            client.post('/api/translation', {'presentation_mode': 'both', 'run_id': status['run_id']})
            self.assertEqual(client.get('/api/rungs')['presentation_mode'], 'both')

    def test_original_report_keeps_usable_english_overlay_and_cache_refreshes(self):
        with running_workspace(self.project, self.runs) as client:
            imported = client.post('/api/import', {'path': str(self.prose), 'expected_revision': 0})
            before = client.get('/analysis?language=original')
            self.assertEqual(report_overlay(before)['translations'], [])
            client.post('/api/translation', {'presentation_mode': 'original', 'prepare': True,
                                           'run_id': imported['active_run']})
            state = self.complete(client)
            self.assertEqual(state['presentation_mode'], 'original')
            self.assertGreater(state['write_generation'], 0)
            after = client.get('/analysis?language=original')
            self.assertNotEqual(before, after)
            overlay = report_overlay(after)
            self.assertEqual(overlay['language'], 'original')
            english = {row['original']: row['text'] for row in overlay['translations']}
            self.assertEqual(english['Arreter la pompe'], 'English: Arreter la pompe')
            self.assertEqual(client.get('/analysis?language=original'), after)
            self.assertEqual(report_overlay(client.get('/analysis?language=english'))['language'], 'english')
            self.assertEqual(client.request('/analysis?language=invalid')[0], 400)

    def test_report_cache_refreshes_when_a_retry_becomes_interrupted(self):
        self.callback = lambda text: {'text': f'English portion. {text}', 'status': 'needs_review',
            'translated_segments': 1, 'retained_segments': 1}
        with running_workspace(self.project, self.runs) as client:
            imported = client.post('/api/import', {'path': str(self.prose), 'expected_revision': 0})
            client.post('/api/translation', {'presentation_mode': 'english', 'prepare': True,
                'run_id': imported['active_run']})
            self.complete(client)
            service = client.server.workspace._translator()
            source = 'Arreter la pompe'
            with patch('plc_workbench.workspace_report.refresh_report', wraps=refresh_report) as render:
                client.get('/analysis?language=english')
                client.get('/analysis?language=english')
                self.assertEqual(render.call_count, 1)
                service._begin_attempt((source,), 'test-fr-en-v1')
                client.get('/analysis?language=english')
                self.assertEqual(render.call_count, 2)
                self.assertFalse(render.call_args.kwargs['translations'][source]['interrupted'])
                service._fail('Saved test interruption')
                client.get('/analysis?language=english')
                self.assertEqual(render.call_count, 3)
                self.assertTrue(render.call_args.kwargs['translations'][source]['interrupted'])
                self.assertEqual(render.call_args.kwargs['translations'][source]['text'], f'English portion. {source}')

    def test_report_navigation_uses_saved_language_without_a_query_override(self):
        with running_workspace(self.project, self.runs) as client:
            imported = client.post('/api/import', {'path': str(self.prose), 'expected_revision': 0})
            for language in ('english', 'both', 'original'):
                with self.subTest(language=language):
                    client.post('/api/translation', {'presentation_mode': language,
                        'prepare': False, 'run_id': imported['active_run']})
                    # The Home cards and Page menu open /analysis#view=patterns
                    # or overview. Fragments stay in the browser; the server
                    # receives /analysis and applies the saved language.
                    self.assertEqual(report_overlay(client.get('/analysis'))['language'], language)
            self.assertEqual(client.get('/api/state')['revision'], imported['revision'])

    def test_historical_translation_poll_uses_prose_cache_without_source_or_calculation_reload(self):
        with running_workspace(self.project, self.runs) as client:
            first = client.post('/api/import', {'path': str(self.prose), 'expected_revision': 0})
            old_rung = client.get('/api/rungs')['items'][0]
            old_instruction = client.get('/api/objects?kind=instruction')['items'][0]
            client.post('/api/translation', {'presentation_mode': 'english', 'prepare': True,
                                           'run_id': first['active_run']})
            self.complete(client)
            second = client.post('/api/import', {'path': str(self.prose_second), 'expected_revision': first['revision']})
            self.complete(client)
            store = client.server.workspace.store
            query = '/api/translation?' + urlencode({'source_id': old_rung['id'], 'run_id': first['active_run']})
            with patch.object(Workspace, 'source', side_effect=AssertionError('Do not rebuild full source on polling')), patch.object(
                    Workspace, '_calculation_detail', side_effect=AssertionError('Do not load calculations on polling')), patch.object(
                    store, 'inventory', wraps=store.inventory) as inventories:
                first_poll = client.get(query)
                second_poll = client.get(query)
                instruction_poll = client.get('/api/translation?' + urlencode({
                    'source_id': old_instruction['id'], 'run_id': first['active_run']}))
            self.assertEqual(inventories.call_count, 1)
            self.assertEqual(first_poll['fields'], second_poll['fields'])
            self.assertEqual(first_poll['fields']['comment']['text'], 'English: ' + old_rung['comment'])
            self.assertEqual(first_poll['run_id'], second['active_run'])
            self.assertEqual(instruction_poll['fields'], {})

    def test_bad_modes_and_stale_preparation_do_not_change_preferences(self):
        with running_workspace(self.project, self.runs) as client:
            state = client.post('/api/import', {'path': str(self.prose), 'expected_revision': 0})
            for mode in ('cloud', None, ['english']):
                self.assertEqual(client.request('/api/translation', payload={
                    'presentation_mode': mode, 'run_id': state['active_run']})[0], 400)
            self.assertEqual(client.request('/api/translation', payload={
                'presentation_mode': 'english', 'prepare': True, 'run_id': 'stale-run'})[0], 409)
            self.assertEqual(client.get('/api/translation')['presentation_mode'], 'original')
            self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
