"""Classification browsing and reviewed migration decisions use invented source."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from test_workspace import running_workspace, saved_analysis


class WorkspaceClassificationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixture.cleanup)
        cls.runs = Path(cls.fixture.name) / 'runs'
        cls.first = saved_analysis(cls.runs)
        cls.second = saved_analysis(cls.runs, controller='ChangedClassificationSource')

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name) / 'project.sqlite'

    def imported(self, client):
        return client.post('/api/import', {'path': str(self.first), 'expected_revision': 0})

    def adopt(self, client, proposal):
        state = client.get('/api/state')
        return client.post('/api/classification/adopt', {
            'proposal_id': proposal['id'], 'run_id': state['active_run'],
            'expected_revision': state['revision'], 'author': 'Invented reviewer'})

    def test_browse_is_read_only_and_categories_are_not_physical_output_guesses(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.imported(client)
            with patch('plc_workbench.workspace_classification.build_classification',
                       wraps=__import__('plc_workbench.workspace_classification', fromlist=['build_classification']).build_classification) as builder:
                first = client.get('/api/classification?category=dc')
                self.assertGreater(first['total'], 0)
                self.assertEqual(first, client.get('/api/classification?category=dc'))
                self.assertEqual(builder.call_count, 1)
            self.assertTrue(all('dc' in row['effective_category_ids'] for row in first['items']))
            self.assertEqual(client.get('/api/classification?category=do')['total'], 0)
            after = client.get('/api/state')
            self.assertEqual(after['revision'], state['revision'])
            self.assertEqual(after['groups'], [])
            self.assertEqual(after['reviews'], {})
            self.assertIn('ac', {row['id'] for row in after['classification_categories']})

    def test_adoption_is_idempotent_and_metadata_persists_without_rewriting_source(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.imported(client)
            row = client.get('/api/classification?category=dc')['items'][0]
            original_rungs = client.get('/api/rungs')
            adopted = self.adopt(client, row)
            group_id = adopted['selected_group_id']
            self.assertEqual(adopted['revision'], state['revision'] + 1)
            repeated = self.adopt(client, row)
            self.assertEqual(repeated['revision'], adopted['revision'])
            self.assertEqual(repeated['selected_group_id'], group_id)
            edited = client.mutate({'op': 'group', 'id': group_id,
                'name': 'Reviewed discrete calculation', 'member_ids': row['member_ids'],
                'function_categories': ['dc', 'alarm'], 'migration_status': 'replace',
                'migration_note': 'Keep behavior; use our target class.'})
            group = next(item for item in edited['groups'] if item['id'] == group_id)
            self.assertEqual(group['proposal_id'], row['id'])
            self.assertEqual(group['function_categories'], ['dc', 'alarm'])
            filtered = client.get('/api/classification?category=alarm&migration=replace')
            self.assertEqual(filtered['total'], 1)
            self.assertEqual(filtered['items'][0]['saved_group_id'], group_id)
            for previous, current in zip(original_rungs['items'], client.get('/api/rungs')['items']):
                self.assertEqual(previous['id'], current['id'])
                self.assertEqual(previous['text'], current['text'])
                self.assertEqual(previous['proposals'], current['proposals'])
            self.assertEqual(edited['reviews'], {})
        with running_workspace(self.project, self.runs) as client:
            group = client.get('/api/state')['groups'][0]
            self.assertEqual(group['migration_status'], 'replace')
            self.assertEqual(group['function_categories'], ['dc', 'alarm'])

    def test_exclusion_filter_never_hides_unreviewed_or_changed_proposals(self):
        with running_workspace(self.project, self.runs) as client:
            self.imported(client)
            initial = client.get('/api/classification')
            self.assertEqual(client.get('/api/classification?migration=in_scope')['total'], initial['total'])
            row = initial['items'][0]
            group_id = self.adopt(client, row)['selected_group_id']
            client.mutate({'op': 'group', 'id': group_id, 'name': row['name'][:160],
                'member_ids': row['member_ids'], 'migration_status': 'exclude'})
            self.assertEqual(client.get('/api/classification?migration=in_scope')['total'], initial['total'] - 1)
            # Simulate a provider update carried only in the report payload.
            workspace = client.server.workspace
            key, projection = workspace._classification_cache
            changed = deepcopy(projection)
            target = next(item for item in changed['groups'] if item['id'] == row['id'])
            target['limitations'].append('New captured dependency requires review.')
            workspace._classification_cache = (key, changed)
            self.assertEqual(client.get('/api/classification?migration=in_scope')['total'], initial['total'])
            stale = client.get('/api/classification?migration=investigate')['items']
            self.assertTrue(next(item for item in stale if item['id'] == row['id'])['needs_revalidation'])
            # An explicit review of the current group signs the current proposal.
            client.mutate({'op': 'group', 'id': group_id, 'name': row['name'][:160],
                'member_ids': row['member_ids'], 'migration_status': 'exclude'})
            self.assertEqual(client.get('/api/classification?migration=exclude')['total'], 1)
            changed['groups'] = [item for item in changed['groups'] if item['id'] != row['id']]
            workspace._classification_cache = (key, changed)
            self.assertTrue(client.get('/api/state')['groups'][0]['needs_revalidation'])

    def test_removed_members_cannot_exclude_the_original_proposal_scope(self):
        with running_workspace(self.project, self.runs) as client:
            self.imported(client)
            initial = client.get('/api/classification')
            row = initial['items'][0]
            group_id = self.adopt(client, row)['selected_group_id']
            for members in (row['member_ids'][:1], []):
                edited = client.mutate({'op': 'group', 'id': group_id, 'name': 'Reviewed subset',
                    'member_ids': members, 'function_categories': ['alarm'], 'migration_status': 'exclude'})
                self.assertEqual(edited['groups'][0]['migration_status'], 'exclude')
                self.assertEqual(edited['groups'][0]['member_ids'], members)
                self.assertEqual(client.get('/api/classification?migration=in_scope')['total'], initial['total'])
                self.assertEqual(client.get('/api/classification?migration=exclude')['total'], 0)
                proposals = client.get('/api/classification?migration=investigate')['items']
                retained = next(item for item in proposals if item['id'] == row['id'])
                self.assertTrue(retained['migration_scope_limited'])
                self.assertEqual(retained['saved_member_count'], len(members))
                self.assertEqual(retained['member_ids'], row['member_ids'])
                self.assertEqual(retained['effective_category_ids'], row['category_ids'])

    def test_changed_export_retains_saved_decisions_and_invalid_adoptions_make_no_changes(self):
        with running_workspace(self.project, self.runs) as client:
            self.imported(client)
            row = client.get('/api/classification')['items'][0]
            first = self.adopt(client, row)
            for payload in ({'proposal_id': 'missing', 'run_id': first['active_run'], 'expected_revision': first['revision']},
                            {'proposal_id': row['id'], 'run_id': first['active_run'], 'expected_revision': 0}):
                self.assertIn(client.request('/api/classification/adopt', payload=payload)[0], (400, 409))
            self.assertEqual(client.get('/api/state')['revision'], first['revision'])
            second = client.post('/api/import', {'path': str(self.second), 'expected_revision': first['revision']})
            retained = second['groups'][0]
            self.assertEqual(retained['proposal_id'], row['id'])
            self.assertTrue(retained['needs_revalidation'])
            self.assertTrue(retained['unresolved_member_ids'])
            current = client.get('/api/classification')
            self.assertTrue(all(item['saved_group_id'] is None for item in current['items']))
            self.assertEqual(client.request('/api/classification?category=not-real')[0], 400)
            self.assertEqual(client.request('/api/classification?migration=not-real')[0], 400)
            self.assertEqual(client.request('/classification.js')[0], 200)


if __name__ == '__main__':
    unittest.main()
