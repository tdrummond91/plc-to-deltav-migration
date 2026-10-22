"""Immutable variable requests, source-safe failures, and bounded lazy caches."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from plc_workbench.project_store import ProjectError
from plc_workbench.workspace import Workspace
from plc_workbench.workspace_variables import VariableIndex
from test_workspace import running_workspace
from test_workspace_map_api import save_map_inputs
from test_workspace_variables import inputs, tag, decorated


class WorkspaceVariableAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixtures.cleanup)
        cls.runs = Path(cls.fixtures.name) / 'runs'
        cls.inputs = inputs(('TON(T,?,?);', 'MOV(1,T.PRE);'),
                            tag(data='<Data Format="L5K">[0,2500,42]</Data>' + decorated()))
        cls.first = save_map_inputs(cls.runs, cls.inputs)
        cls.later_inputs = inputs(('TON(T,?,?);',), tag(data=decorated('7000')))
        cls.later = save_map_inputs(cls.runs, cls.later_inputs)
        cls.instruction_id = cls.inputs[1].rungs[0].instructions[0].id

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name) / 'project.sqlite'
        self.workspace = Workspace(self.project, self.runs)
        self.addCleanup(self.workspace.close)
        self.run_id = self.workspace.import_run(str(self.first), 0)['active_run']
        self.query = {'run_id': self.run_id, 'instruction_id': self.instruction_id, 'variable': 'T.PRE'}

    def change_artifact(self, name: str, raw: bytes | None) -> None:
        connection = self.workspace.store.connection
        if raw is None:
            connection.execute('DELETE FROM artifacts WHERE run_id=? AND name=?', (self.run_id, name))
        else:
            connection.execute('UPDATE artifacts SET data=? WHERE run_id=? AND name=?', (raw, self.run_id, name))
        connection.commit()

    def test_requests_share_one_index_and_do_not_copy_inventory_or_write_state_again(self) -> None:
        before = self.workspace.store.state()
        changes = self.workspace.store.connection.total_changes
        with patch('plc_workbench.workspace_variables.VariableIndex', wraps=VariableIndex) as constructor, \
             patch.object(self.workspace.store, 'inventory', wraps=self.workspace.store.inventory) as inventory:
            first = self.workspace.variable(self.query)
            second = self.workspace.variable(dict(self.query, variable='T.ACC'))
        self.assertEqual(first['display_value']['value'], '2500')
        self.assertEqual(second['display_value']['value'], '42')
        self.assertEqual(constructor.call_count, 1)
        self.assertEqual(inventory.call_count, 1)
        self.assertFalse(first['historical'])
        self.assertEqual(self.workspace.store.state(), before)
        self.assertEqual(self.workspace.store.connection.total_changes, changes)

    def test_historical_lookup_returns_old_values_and_keeps_current_selection(self) -> None:
        self.workspace.variable(self.query)
        latest = self.workspace.import_run(str(self.later), self.workspace.store.state()['revision'])
        before, loaded = self.workspace.store.state(), self.workspace._run
        old = self.workspace.variable(self.query)
        new = self.workspace.variable({'run_id': latest['active_run'],
            'instruction_id': self.later_inputs[1].rungs[0].instructions[0].id, 'variable': 'T.PRE'})
        self.assertTrue(old['historical'])
        self.assertFalse(new['historical'])
        self.assertEqual(old['display_value']['value'], '2500')
        self.assertEqual(new['display_value']['value'], '7000')
        self.assertEqual(self.workspace.store.state(), before)
        self.assertEqual(self.workspace._run, loaded)
        with self.assertRaises(ProjectError):
            self.workspace.variable(dict(self.query, run_id=latest['active_run']))

    def test_all_query_identities_are_required_and_instructions_constrain_variables(self) -> None:
        for key in self.query:
            missing = dict(self.query)
            del missing[key]
            with self.subTest(key=key), self.assertRaises(ProjectError):
                self.workspace.variable(missing)
        for query in (dict(self.query, variable='Other.PRE'), dict(self.query, variable='x' * 4097),
                      dict(self.query, variable='T.PRE\n'), dict(self.query, run_id='foreign'),
                      dict(self.query, instruction_id='foreign')):
            with self.subTest(query=query), self.assertRaises(ProjectError):
                self.workspace.variable(query)

    def test_missing_stored_data_is_explicit_but_keeps_declaration_and_writers(self) -> None:
        self.change_artifact('tag-data.json', None)
        view = self.workspace.variable(self.query)
        self.assertTrue(view['available'])
        self.assertIsNone(view['display_value'])
        self.assertEqual(view['captured_values'], [])
        self.assertEqual(view['declaration']['datatype'], 'TIMER')
        self.assertGreater(view['writers_total'], 0)
        self.assertTrue(any('tag-data evidence is absent' in text for text in view['limitations']))

    def test_missing_access_keeps_actual_operand_lookup_without_inventing_writers(self) -> None:
        self.change_artifact('access.json', None)
        query = dict(self.query, instruction_id=self.inputs[1].rungs[1].instructions[0].id)
        view = self.workspace.variable(query)
        self.assertEqual(view['display_value']['value'], '2500')
        self.assertEqual(view['writers'], [])
        self.assertTrue(any('access evidence is absent' in text for text in view['limitations']))
        with self.assertRaises(ProjectError):
            self.workspace.variable(self.query)

    def test_forged_or_malformed_optional_evidence_returns_source_free_unavailable(self) -> None:
        original = self.workspace.store.artifact('tag-data.json', self.run_id)
        forged = json.loads(original)
        forged['elements'][1]['attributes']['Value'] = 'private-corruption'
        for raw in (b'[]', b'{"private-corruption":', b'[' * 2000,
                    json.dumps(forged).encode(), b'{"schema_version":1,' + original.lstrip()[1:]):
            with self.subTest(raw=raw[:20]):
                self.change_artifact('tag-data.json', raw)
                with closing(Workspace(self.project, self.runs)) as fresh:
                    view = fresh.variable(self.query)
                self.assertFalse(view['available'])
                self.assertNotIn('private-corruption', json.dumps(view))
                self.assertEqual(view['captured_values'], [])
                self.assertIsNone(view['declaration'])
                self.assertEqual(view['run_id'], self.run_id)

    def test_predecode_size_limit_and_failed_index_are_cached(self) -> None:
        with patch('plc_workbench.workspace_variables.MAX_ARTIFACT_BYTES', 8), \
             patch('plc_workbench.workspace_variables.VariableIndex', wraps=VariableIndex) as constructor:
            first = self.workspace.variable(self.query)
            second = self.workspace.variable(self.query)
        self.assertFalse(first['available'])
        self.assertFalse(second['available'])
        self.assertEqual(constructor.call_count, 0)

    def test_restore_invalidates_variable_cache_even_for_same_saved_run(self) -> None:
        with patch('plc_workbench.workspace_variables.VariableIndex', wraps=VariableIndex) as constructor:
            self.workspace.variable(self.query)
            backup = Path(self.workspace.backup()['path'])
            self.workspace.restore(backup.name, self.workspace.store.state()['revision'])
            self.workspace.variable(self.query)
        self.assertEqual(constructor.call_count, 2)

    def test_http_route_echoes_immutable_identity_and_enforces_origin(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            route = '/api/variable?' + urlencode(self.query)
            view = client.get(route)
            self.assertEqual(view['display_value']['value'], '2500')
            for key, value in self.query.items():
                self.assertEqual(view[key], value)
            self.assertEqual(client.request('/api/variable?variable=T.PRE')[0], 400)
            self.assertEqual(client.request(route, headers={'Origin': 'https://outside.invalid'})[0], 403)
            self.assertEqual(client.request('/variable-help-content.js')[0], 200)

    def test_analysis_http_policy_allows_only_trusted_hosted_reads_and_popups(self) -> None:
        original = self.workspace.store.artifact('review.html', self.run_id)
        self.change_artifact('review.html', original.replace(b'</body>',
            b'<script>globalThis.PRIVATE_IMPORTED_EXECUTABLE=true;</script></body>'))
        with running_workspace(self.project, self.runs) as client:
            status, page = client.request('/analysis')
            self.assertEqual(status, 200)
            self.assertNotIn(b'PRIVATE_IMPORTED_EXECUTABLE', page)
            policy = client.last_headers['content-security-policy']
            directives = {parts[0]: parts[1:] for item in policy.split(';')
                          if (parts := item.strip().split())}
            self.assertEqual(directives['connect-src'], ["'self'"])
            self.assertEqual(directives['sandbox'], ['allow-scripts', 'allow-same-origin',
                                                   'allow-popups', 'allow-popups-to-escape-sandbox'])
            self.assertEqual(directives['frame-ancestors'], ["'none'"])
            for kind in ('script', 'style'):
                self.assertEqual(len(directives[kind + '-src']), 1)
                digest = directives[kind + '-src'][0]
                self.assertRegex(digest, r"^'sha256-[A-Za-z0-9+/]{43}='$")
                self.assertIn(digest.encode(), page)
            self.assertNotIn('unsafe-inline', policy)
            for directive in ('default-src', 'form-action', 'object-src', 'frame-src'):
                self.assertEqual(directives[directive], ["'none'"])
            query = '/api/variable?' + urlencode(self.query)
            self.assertEqual(client.get(query)['display_value']['value'], '2500')
            self.assertEqual(client.request('/api/source?' + urlencode({
                'id': self.instruction_id, 'run_id': self.run_id}))[0], 200)
            self.assertEqual(client.request(query, headers={'Origin': 'null'})[0], 403)
            self.assertEqual(client.request(query, headers={'Origin': 'https://outside.invalid'})[0], 403)
            self.assertEqual(client.request('/api/mutate', payload={}, headers={'X-Workspace-Token': ''})[0], 403)


if __name__ == '__main__':
    unittest.main()
