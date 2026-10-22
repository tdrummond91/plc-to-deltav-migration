"""Immutable field-I/O browsing, shared evidence cache, and HTTP boundaries."""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from plc_workbench.project_store import ProjectError
from plc_workbench.workspace import Workspace
from plc_workbench.workspace_field_io import FieldIOIndex
from plc_workbench.workspace_variables import VariableIndex
from test_workspace import running_workspace
from test_workspace_field_io import field_inputs, module
from test_workspace_map_api import save_map_inputs


class WorkspaceFieldIOAPITests(unittest.TestCase):
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

    def test_field_and_variable_requests_share_authentication_without_state_changes(self) -> None:
        before = self.workspace.store.state()
        changes = self.workspace.store.connection.total_changes
        with patch('plc_workbench.workspace_variables.VariableIndex', wraps=VariableIndex) as constructor, \
             patch.object(self.workspace.store, 'inventory', wraps=self.workspace.store.inventory) as inventory, \
             patch('plc_workbench.workspace_field_io.FieldIOIndex', wraps=FieldIOIndex) as field:
            first = self.workspace.field_io(self.query)
            self.workspace.variable({'run_id': self.run_id,
                'instruction_id': self.inputs[1].rungs[0].instructions[0].id, 'variable': 'InputAlias'})
            second = self.workspace.field_io(dict(self.query, field_type='di'))
        self.assertTrue(first['available'])
        self.assertEqual(second['modules']['total'], 1)
        self.assertEqual((constructor.call_count, inventory.call_count, field.call_count), (1, 1, 1))
        self.assertEqual(self.workspace.store.state(), before)
        self.assertEqual(self.workspace.store.connection.total_changes, changes)

    def test_historical_fields_preserve_active_run_and_filters(self) -> None:
        self.workspace.field_io(self.query)
        newer = self.workspace.import_run(str(self.later), self.workspace.store.state()['revision'])
        before, loaded = self.workspace.store.state(), self.workspace._run
        old = self.workspace.field_io(dict(self.query, field_type='ao'))
        new = self.workspace.field_io({'run_id': newer['active_run'], 'field_type': 'ao'})
        self.assertTrue(old['historical'])
        self.assertFalse(new['historical'])
        self.assertEqual(old['modules']['total'], 1)
        self.assertEqual(new['modules']['total'], 0)
        self.assertEqual(self.workspace.store.state(), before)
        self.assertEqual(self.workspace._run, loaded)

    def test_source_ids_group_modules_without_inventing_channel_memberships(self) -> None:
        view = self.workspace.field_io(dict(self.query, field_type='di'))
        module_id = view['modules']['items'][0]['id']
        card = self.workspace.field_io(dict(self.query, module_id=module_id))
        members = card['selected_module']['group_member_ids']
        self.assertEqual(members, [module_id])
        state = self.workspace.mutate({'op': 'group', 'name': 'Selected field card', 'member_ids': members},
                                      self.workspace.store.state()['revision'])
        self.assertEqual(state['groups'][0]['member_ids'], members)
        with self.assertRaises(ProjectError):
            self.workspace.mutate({'op': 'group', 'name': 'Invalid channel ID',
                'member_ids': [card['addresses']['items'][0]['id']]}, state['revision'])

    def test_missing_access_and_data_keep_module_classes_but_not_guessed_points(self) -> None:
        connection = self.workspace.store.connection
        connection.execute("DELETE FROM artifacts WHERE run_id=? AND name IN ('access.json','tag-data.json')", (self.run_id,))
        connection.commit()
        view = self.workspace.field_io(self.query)
        card = next(row for row in view['modules']['items'] if row['field_type'] == 'di')
        detail = self.workspace.field_io(dict(self.query, module_id=card['id']))
        point = next(row for row in detail['addresses']['items'] if row['suffix'] == '.Data.0')
        self.assertIsNone(point['channel'])
        self.assertEqual(point['uses'][0]['role'], 'unknown')
        self.assertTrue(any('tag-data' in line for line in detail['limitations']))

    def test_failed_evidence_returns_fixed_unavailable_and_is_cached(self) -> None:
        connection = self.workspace.store.connection
        connection.execute('UPDATE artifacts SET data=? WHERE run_id=? AND name=?',
                           (b'{"PRIVATE_CORRUPTION":', self.run_id, 'references.json'))
        connection.commit()
        with patch('plc_workbench.workspace_field_io.FieldIOIndex', wraps=FieldIOIndex) as field:
            first = self.workspace.field_io(self.query)
            second = self.workspace.field_io(self.query)
        self.assertFalse(first['available'])
        self.assertFalse(second['available'])
        self.assertNotIn('PRIVATE_CORRUPTION', json.dumps(first))
        self.assertEqual(field.call_count, 0)

    def test_restore_clears_both_shared_and_field_projection_caches(self) -> None:
        with patch('plc_workbench.workspace_field_io.FieldIOIndex', wraps=FieldIOIndex) as field:
            self.workspace.field_io(self.query)
            backup = Path(self.workspace.backup()['path'])
            self.workspace.restore(backup.name, self.workspace.store.state()['revision'])
            self.workspace.field_io(self.query)
        self.assertEqual(field.call_count, 2)

    def test_cached_wording_is_only_a_visible_presentation_layer(self) -> None:
        class CachedTranslator:
            def status(self):
                return {'presentation_mode': 'both'}

            def lookup_many(self, texts):
                return {text: {'state': 'ready', 'text': 'Cached English wording', 'original': text} for text in texts}

        original = deepcopy(self.workspace.store.inventory(self.run_id))
        with patch.object(self.workspace, '_translator', return_value=CachedTranslator()):
            view = self.workspace.field_io(dict(self.query, field_type='di'))
            row = view['modules']['items'][0]
            detail = self.workspace.field_io(dict(self.query, module_id=row['id']))
        self.assertEqual(view['presentation_mode'], 'both')
        self.assertEqual(row['description'], 'Invented DiscreteIn module')
        self.assertEqual(row['wording']['description']['text'], 'Cached English wording')
        self.assertEqual(detail['selected_module']['wording']['description']['text'], 'Cached English wording')
        self.assertEqual(self.workspace.store.inventory(self.run_id), original)

    def test_http_filters_identity_and_origin_fail_closed(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            route = '/api/field-io?' + urlencode(dict(self.query, field_type='di'))
            response = client.get(route)
            self.assertEqual(response['run_id'], self.run_id)
            self.assertEqual(response['modules']['total'], 1)
            self.assertEqual(response['coverage']['modules_by_field_type'], {'di': 1, 'do': 1, 'ai': 1, 'ao': 1, 'unknown': 2})
            for route in ('/api/field-io', '/api/field-io?' + urlencode(dict(self.query, page='0')),
                          '/api/field-io?' + urlencode(dict(self.query, module_id='foreign'))):
                self.assertEqual(client.request(route)[0], 400)
            self.assertEqual(client.request('/api/field-io?' + urlencode(self.query),
                headers={'Origin': 'https://outside.invalid'})[0], 403)


if __name__ == '__main__':
    unittest.main()
