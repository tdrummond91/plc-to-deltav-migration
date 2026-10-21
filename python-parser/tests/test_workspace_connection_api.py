"""Local source-use API, caching and list-preview limits with invented exports."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from plc_workbench.pid import analyze_pid
from plc_workbench.pid_members import analyze_pid_members
from plc_workbench.project_store import ProjectError
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.storage import save_run
from plc_workbench.tag_data import analyze_tag_data
from plc_workbench.workspace import Workspace, PAGE_SIZE
from plc_workbench.workspace_connections import ConnectionIndex
from test_relationships import capture
from test_workspace import running_workspace


def saved_connections(runs: Path, *, changed: bool = False) -> Path:
    first = ('CPT(C,(A+B)/2)CPT(D,A**2)CPT(T,B+99);' if changed else
             'CPT(C,(A+B)/2)CPT(D,A**2)CPT(T,B+1);')
    inputs = capture((first, 'XIC(A)[XIC(B),[XIO(C),]]OTE(D);', 'OTE(B);',
                      *('XIC(B)OTE(C);' for _ in range(58))))
    snapshot, inventory, references, access, calculations, rungs, relationships = inputs
    tag_data = analyze_tag_data(snapshot, inventory)
    pid = analyze_pid(snapshot, inventory, references, tag_data)
    members = analyze_pid_members(snapshot, inventory, references, tag_data, pid)
    return save_run(runs, snapshot, inventory, references=references,
                    sfc_structure=analyze_sfc_structure(snapshot, inventory), include_review=True,
                    access=access, tag_data=tag_data, pid=pid, pid_members=members,
                    calculations=calculations, rung_analysis=rungs, relationships=relationships)


class WorkspaceConnectionAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.captures = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.captures.cleanup)
        cls.runs = Path(cls.captures.name) / 'runs'
        cls.first = saved_connections(cls.runs)
        cls.later = saved_connections(cls.runs, changed=True)
        cls.inventory = json.loads((cls.first / 'inventory.json').read_text(encoding='utf-8'))

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / 'project.sqlite'
        self.workspace = Workspace(self.project, self.runs)
        self.addCleanup(self.workspace.close)
        self.run_id = self.workspace.import_run(str(self.first), 0)['active_run']
        self.focus = self.inventory['rungs'][2]['id']

    def replace(self, name: str, data: bytes | None) -> None:
        connection = self.workspace.store.connection
        if data is None:
            connection.execute('DELETE FROM artifacts WHERE run_id=? AND name=?', (self.run_id, name))
        else:
            connection.execute('UPDATE artifacts SET data=? WHERE run_id=? AND name=?', (data, self.run_id, name))
        connection.commit()

    def test_connections_are_read_only_and_one_index_is_reused_across_navigation(self) -> None:
        before = self.workspace.store.state()
        changes = self.workspace.store.connection.total_changes
        with patch('plc_workbench.workspace_connections.ConnectionIndex', wraps=ConnectionIndex) as constructor:
            first = self.workspace.connections({'id': self.focus})
            other = self.workspace.connections({'id': self.inventory['rungs'][0]['id'], 'scope': 'routine'})
            self.assertTrue(first['available'])
            self.assertTrue(other['available'])
            self.assertEqual(constructor.call_count, 1)
        self.assertEqual(self.workspace.store.state(), before)
        self.assertEqual(self.workspace.store.connection.total_changes, changes)

    def test_instruction_selection_maps_to_own_rung_and_exact_signal_filter(self) -> None:
        instruction = self.inventory['rungs'][0]['instructions'][1]['id']
        view = self.workspace.connections({'id': instruction})
        self.assertEqual(view['focus']['id'], self.inventory['rungs'][0]['id'])
        selected = view['signals'][0]['id']
        focused = self.workspace.connections({'id': instruction, 'signal_id': selected})
        self.assertEqual([row['id'] for row in focused['signals']], [selected])
        self.assertEqual(focused['pagination']['total'], 1)

    def test_new_import_and_restore_rebuild_cache_even_for_same_run_identifier(self) -> None:
        with patch('plc_workbench.workspace_connections.ConnectionIndex', wraps=ConnectionIndex) as constructor:
            self.workspace.connections({'id': self.focus})
            backup = Path(self.workspace.backup()['path'])
            state = self.workspace.import_run(str(self.later), self.workspace.store.state()['revision'])
            later_rung = self.workspace.store.inventory()['rungs'][2]['id']
            self.assertNotEqual(later_rung, self.focus)
            self.assertEqual(self.workspace.connections({'id': later_rung})['focus']['id'], later_rung)
            self.assertEqual(constructor.call_count, 2)
            restored = self.workspace.restore(backup.name, state['revision'])
            self.assertEqual(restored['active_run'], self.run_id)
            self.assertEqual(self.workspace.connections({'id': self.focus})['focus']['id'], self.focus)
            self.assertEqual(constructor.call_count, 3)
            # Restoring the very same source snapshot still invalidates the cache.
            again = Path(self.workspace.backup()['path'])
            self.workspace.restore(again.name, self.workspace.store.state()['revision'])
            self.workspace.connections({'id': self.focus})
            self.assertEqual(constructor.call_count, 4)

    def test_missing_companion_is_unavailable_without_hiding_original_rung(self) -> None:
        self.replace('relationships.json', None)
        view = self.workspace.connections({'id': self.focus})
        self.assertFalse(view['available'])
        self.assertIn('does not mean there are no connections', view['notice'])
        self.assertEqual(self.workspace.source(self.focus)['source']['text'], 'OTE(B);')

    def test_damaged_optional_evidence_is_unavailable_and_error_does_not_echo_source(self) -> None:
        valid = (self.first / 'relationships.json').read_bytes()
        bad = json.loads(valid)
        bad['addresses'][0]['target_id'] = 'private-foreign-evidence'
        for payload in (b'{"private-broken":', b'[]', json.dumps(bad).encode(),
                        b'{"schema_version":1,' + valid.lstrip()[1:], b'[' * 2000):
            with self.subTest(payload=payload[:20]):
                self.replace('relationships.json', payload)
                with closing(Workspace(self.project, self.runs)) as fresh:
                    view = fresh.connections({'id': self.focus})
                    self.assertFalse(view['available'])
                    self.assertNotIn('private-', view['notice'])
                    self.assertNotIn('signals', view)

    def test_predecode_limit_stops_oversized_companion_before_json_parsing(self) -> None:
        self.workspace.state()  # Load inventory before testing the optional companion read.
        raw = self.workspace.store.artifact('references.json', self.run_id)
        with patch('plc_workbench.workspace_connections.MAX_ARTIFACT_BYTES', 8), \
             patch('plc_workbench.workspace.json.loads', wraps=json.loads) as decode, \
             patch('plc_workbench.workspace_connections.ConnectionIndex', wraps=ConnectionIndex) as constructor:
            view = self.workspace.connections({'id': self.focus})
        self.assertFalse(view['available'])
        self.assertFalse(constructor.called)
        self.assertFalse(any(call.args and call.args[0] == raw for call in decode.call_args_list))

    def test_failed_index_is_cached_until_active_run_changes(self) -> None:
        self.replace('relationships.json', b'[]')
        with patch('plc_workbench.workspace_connections.ConnectionIndex', wraps=ConnectionIndex) as constructor:
            self.assertFalse(self.workspace.connections({'id': self.focus})['available'])
            self.assertFalse(self.workspace.connections({'id': self.focus})['available'])
            self.assertEqual(constructor.call_count, 1)
            self.workspace.import_run(str(self.later), self.workspace.store.state()['revision'])
            fresh_id = self.workspace.store.inventory()['rungs'][2]['id']
            self.assertTrue(self.workspace.connections({'id': fresh_id})['available'])
            self.assertEqual(constructor.call_count, 2)

    def test_empty_project_explains_import_and_invalid_selection_is_an_error(self) -> None:
        with closing(Workspace(Path(self.temporary.name) / 'empty.sqlite', self.runs)) as empty:
            result = empty.connections({'id': 'foreign'})
            self.assertFalse(result['available'])
            self.assertIn('Import', result['notice'])
        for query in ({'id': 'foreign'}, {'id': self.focus, 'scope': 'plant'},
                      {'id': self.focus, 'page': 'bad'}, {'id': self.focus, 'endpoint_page': '0'},
                      {'id': self.focus, 'signal_id': 'foreign'}):
            with self.subTest(query=query), self.assertRaises(ProjectError):
                self.workspace.connections(query)

    def test_list_preview_contains_only_two_visible_instructions_and_their_calculations(self) -> None:
        with patch.object(self.workspace, '_calculation_detail', wraps=self.workspace._calculation_detail) as details:
            page = self.workspace.rungs({})
        self.assertEqual(len(page['items']), PAGE_SIZE)
        self.assertEqual(details.call_count, PAGE_SIZE)
        first = page['items'][0]['preview']
        expected = self.inventory['rungs'][0]['instructions'][:2]
        self.assertEqual(first['instruction_count'], 3)
        self.assertEqual(first['instructions'], expected)
        ids = {row['id'] for row in expected}
        self.assertEqual({row['id'] for row in first['calculations']['occurrences']}, ids)
        self.assertEqual({row['instruction_id'] for row in first['calculations']['nodes']}, ids)
        self.assertEqual(page['items'][1]['preview']['branch_count'], 2)
        visible_ids = {row['id'] for row in self.inventory['rungs'][:PAGE_SIZE]}
        self.assertEqual({row['id'] for row in page['items']}, visible_ids)
        with patch.object(self.workspace, '_calculation_detail', wraps=self.workspace._calculation_detail) as details:
            second = self.workspace.rungs({'page': '2'})
        self.assertEqual(len(second['items']), 11)
        self.assertEqual(details.call_count, 11)

    def test_http_route_pages_exact_signal_and_rejects_foreign_origin(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            view = client.get('/api/connections?' + urlencode({'id': self.focus}))
            selected = next(row for row in view['signals'] if row['label'] == 'B')
            second = client.get('/api/connections?' + urlencode({
                'id': self.focus, 'signal_id': selected['id'], 'endpoint_page': 2,
            }))
            self.assertEqual(len(second['signals']), 1)
            self.assertEqual(second['signals'][0]['endpoints']['page'], 2)
            first_ids = {row['id'] for row in selected['readers']}
            second_ids = {row['id'] for row in second['signals'][0]['readers']}
            self.assertFalse(first_ids & second_ids)
            self.assertEqual(client.request('/api/connections?id=foreign')[0], 400)
            self.assertEqual(client.request('/api/connections?id=' + self.focus,
                                           headers={'Origin': 'https://outside.invalid'})[0], 403)
            for name in ('connections.js', 'connections.css'):
                status, body = client.request('/' + name)
                self.assertEqual(status, 200)
                self.assertTrue(body)


if __name__ == '__main__':
    unittest.main()
