"""Development-only loopback checks of the editable workspace using invented L5X."""
from __future__ import annotations

from contextlib import closing, contextmanager
import http.client
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
from typing import Iterator
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from plc_workbench.access import analyze_access
from plc_workbench.calculations import analyze_calculations
from plc_workbench.pid import analyze_pid
from plc_workbench.pid_members import analyze_pid_members
from plc_workbench.project_store import ProjectError
from plc_workbench.references import analyze_references
from plc_workbench.rung_analysis import analyze_rungs
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.storage import save_run
from plc_workbench.tag_data import analyze_tag_data
from plc_workbench.workspace import Workspace, WorkspaceServer, main


LONG_TEXT = 'XIC(Input)' * 25 + 'OTE(Output);'
LONG_COMMENT = 'Invented verification description: ' + 'full original description; ' * 15 + '\u00e9'


def saved_analysis(runs: Path, *, first_texts: tuple[str, ...] = (),
                   controller: str = 'InventedWorkspace') -> Path:
    """Use the real capture/publish path, including source and proposed analysis."""
    routines = []
    for name, count in (('FirstRoutine', 60), ('SecondRoutine', 45)):
        rungs = ''.join(
            f'<Rung Number="{index}" Type="N"><Text><![CDATA['
            + (first_texts[index] if name == 'FirstRoutine' and index < len(first_texts)
               else LONG_TEXT if name == 'FirstRoutine' and index == 0 else 'XIC(Input)OTE(Output);')
            + ']]></Text><Comment><![CDATA['
            + (LONG_COMMENT if name == 'FirstRoutine' and index == 0 else f'{name} source {index}')
            + ']]></Comment></Rung>'
            for index in range(count)
        )
        routines.append(f'<Routine Name="{name}" Type="RLL"><RLLContent>{rungs}</RLLContent></Routine>')
    xml = (f'<RSLogix5000Content><Controller Name="{controller}"><Programs>'
           '<Program Name="InventedProgram"><Tags>'
           '<Tag Name="Input" TagType="Base" DataType="BOOL"/>'
           '<Tag Name="Output" TagType="Base" DataType="BOOL"/>'
           '</Tags><Routines>' + ''.join(routines)
           + '</Routines></Program></Programs></Controller></RSLogix5000Content>')
    snapshot = snapshot_from_bytes(xml.encode('utf-8'))
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    calculations = analyze_calculations(snapshot, inventory, references)
    access = analyze_access(inventory, references, schema_version=4,
                            snapshot=snapshot, calculations=calculations)
    tag_data = analyze_tag_data(snapshot, inventory)
    pid = analyze_pid(snapshot, inventory, references, tag_data)
    members = analyze_pid_members(snapshot, inventory, references, tag_data, pid)
    rungs = analyze_rungs(snapshot, inventory, references, access, calculations)
    return save_run(runs, snapshot, inventory, references=references,
                    sfc_structure=analyze_sfc_structure(snapshot, inventory), include_review=True,
                    access=access, tag_data=tag_data, pid=pid, pid_members=members,
                    calculations=calculations, rung_analysis=rungs)


class Client:
    def __init__(self, server: WorkspaceServer):
        self.server = server
        self.last_headers: dict[str, str] = {}

    def request(self, route: str, *, payload: dict | None = None,
                headers: dict[str, str] | None = None,
                raw: bytes | None = None) -> tuple[int, object]:
        write = payload is not None or raw is not None
        body = raw if raw is not None else json.dumps(payload).encode('utf-8') if write else None
        request_headers = {'Content-Type': 'application/json',
                           'X-Workspace-Token': self.server.token} if write else {}
        request_headers.update(headers or {})
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=5)
        try:
            connection.request('POST' if write else 'GET', route, body=body, headers=request_headers)
            response = connection.getresponse()
            self.last_headers = {key.casefold(): value for key, value in response.getheaders()}
            data = response.read()
            value = json.loads(data) if 'application/json' in response.getheader('Content-Type', '') else data
            return response.status, value
        finally:
            connection.close()

    def get(self, route: str) -> dict:
        status, value = self.request(route)
        if status != 200:
            raise AssertionError(f'GET {route}: {status} {value}')
        return value

    def post(self, route: str, payload: dict) -> dict:
        status, value = self.request(route, payload=payload)
        if status != 200:
            raise AssertionError(f'POST {route}: {status} {value}')
        return value

    def mutate(self, command: dict) -> dict:
        return self.post('/api/mutate', {'command': command,
                                        'expected_revision': self.get('/api/state')['revision']})


@contextmanager
def running_workspace(project: Path, runs: Path) -> Iterator[Client]:
    # SQLite's owning thread is the real server thread, as it is in main().
    ready = threading.Event()
    servers: list[WorkspaceServer] = []
    errors: list[BaseException] = []

    def serve() -> None:
        try:
            workspace = Workspace(project, runs)
            try:
                server = WorkspaceServer(('127.0.0.1', 0), workspace)
                servers.append(server)
                ready.set()
                try:
                    server.serve_forever(poll_interval=0.02)
                finally:
                    server.server_close()
            finally:
                workspace.close()
        except BaseException as exc:
            errors.append(exc)
            ready.set()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        if not ready.wait(10):
            raise AssertionError('Local workspace did not start.')
        if errors:
            raise errors[0]
        yield Client(servers[0])
    finally:
        if servers:
            servers[0].shutdown()
        thread.join(timeout=10)
        if thread.is_alive():
            raise AssertionError('Local workspace did not stop.')
        if errors:
            raise errors[0]


class WorkspaceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.captures = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.captures.cleanup)
        cls.runs = Path(cls.captures.name) / 'completed runs'
        cls.first_run = saved_analysis(cls.runs)
        cls.rerun = saved_analysis(cls.runs)
        cls.inventory = json.loads((cls.first_run / 'inventory.json').read_text(encoding='utf-8'))

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / 'private project' / 'engineering.sqlite'

    def import_run(self, client: Client, run: Path | None = None) -> dict:
        return client.post('/api/import', {'path': str(run or self.first_run),
                                          'expected_revision': client.get('/api/state')['revision']})

    def test_empty_project_does_not_substitute_a_practice_source(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            state = client.get('/api/state')
            self.assertIsNone(state['active_run'])
            self.assertEqual(state['source']['rung_count'], 0)
            self.assertEqual(state['routines'], [])
            self.assertEqual(client.get('/api/rungs')['items'], [])
            self.assertEqual(state['reviews'], {})
            self.assertEqual({row['path'] for row in client.get('/api/runs')['items']},
                             {str(self.first_run), str(self.rerun)})

    def test_every_rung_can_be_reached_across_pages_and_same_number_routines(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            state = self.import_run(client)
            self.assertEqual(state['source']['rung_count'], 105)
            pages = [client.get(f'/api/rungs?page={page}') for page in (1, 2, 3)]
            self.assertEqual([len(page['items']) for page in pages], [50, 50, 5])
            self.assertTrue(all(page['total'] == 105 for page in pages))
            rows = [row for page in pages for row in page['items']]
            self.assertEqual({row['id'] for row in rows}, {row['id'] for row in self.inventory['rungs']})
            self.assertEqual(len({row['id'] for row in rows}), 105)
            zeros = [row for row in rows if row['number'] == '0']
            self.assertEqual(len(zeros), 2)
            self.assertEqual(len({row['path'] for row in zeros}), 2)
            self.assertEqual(sorted(row['count'] for row in state['routines']), [45, 60])
            for routine in state['routines']:
                selected = client.get('/api/rungs?' + urlencode({'routine': routine['id']}))
                self.assertEqual(selected['total'], routine['count'])
                self.assertTrue(all(routine['name'] in row['path'] for row in selected['items']))
            selected = client.get('/api/rungs?' + urlencode({'query': 'verification description'}))
            self.assertEqual(selected['total'], 1)
            self.assertEqual(selected['items'][0]['comment'], LONG_COMMENT)

    def test_full_source_instructions_and_bound_tags_are_linked_without_truncation(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            self.import_run(client)
            original = self.inventory['rungs'][0]
            detail = client.get('/api/source?' + urlencode({'id': original['id']}))
            self.assertEqual(detail['source'], original)
            self.assertEqual(detail['source']['text'], LONG_TEXT)
            self.assertEqual(detail['source']['comment'], LONG_COMMENT)
            self.assertTrue(detail['proposals'])
            self.assertEqual(detail['review'], {})
            tag_ids = {row['id'] for row in self.inventory['entities'] if row['kind'] == 'tag'}
            linked_ids = {row['id'] for row in detail['related']}
            self.assertTrue(tag_ids.issubset(linked_ids))
            for instruction in original['instructions']:
                block = client.get('/api/source?' + urlencode({'id': instruction['id']}))
                self.assertEqual(block['source'], instruction)
                self.assertIn(original['id'], {row['id'] for row in block['related']})
                self.assertTrue(block['operands'])
            for identifier in tag_ids:
                self.assertEqual(client.get('/api/source?' + urlencode({'id': identifier}))['kind'], 'tag')

    def test_recategorize_regroup_reopen_and_rerun_preserve_changes_and_source(self) -> None:
        original = self.inventory['rungs'][0]
        with running_workspace(self.project, self.runs) as client:
            self.import_run(client)
            before = client.get('/api/source?' + urlencode({'id': original['id']}))
            state = client.mutate({'op': 'category', 'name': 'Invented permissive'})
            category = next(row['id'] for row in state['categories'] if row['name'] == 'Invented permissive')
            state = client.mutate({'op': 'review', 'source_ids': [original['id']],
                                  'category_ids': [category], 'status': 'confirmed',
                                  'fields': {'purpose': 'Verified invented permissive'}})
            state = client.mutate({'op': 'group', 'name': 'Invented control group',
                                  'member_ids': [original['id'], self.inventory['rungs'][60]['id']]})
            expected_review = state['reviews'][original['id']]
            group_id = state['groups'][0]['id']
            self.assertEqual(client.get('/api/rungs?' + urlencode({'group': group_id}))['total'], 2)
        with running_workspace(self.project, self.runs) as client:
            state = client.get('/api/state')
            self.assertEqual(state['reviews'][original['id']], expected_review)
            self.assertEqual(state['groups'][0]['id'], group_id)
            state = self.import_run(client, self.rerun)
            self.assertEqual(state['reviews'][original['id']]['category_ids'], [category])
            self.assertEqual(state['reviews'][original['id']]['status'], 'confirmed')
            self.assertFalse(state['reviews'][original['id']]['needs_revalidation'])
            after = client.get('/api/source?' + urlencode({'id': original['id']}))
            self.assertEqual(after['source'], before['source'])
            self.assertEqual(after['proposals'], before['proposals'])
            self.assertEqual(after['review']['fields'], {'purpose': 'Verified invented permissive'})
        self.assertEqual(json.loads((self.first_run / 'inventory.json').read_text(encoding='utf-8')), self.inventory)

    def test_stale_browser_cannot_overwrite_newer_review(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            state = self.import_run(client)
            outdated = state['revision']
            state = client.mutate({'op': 'category', 'name': 'Newer category'})
            status, response = client.request('/api/mutate', payload={
                'command': {'op': 'category', 'name': 'Stale category'}, 'expected_revision': outdated})
            self.assertEqual(status, 409)
            self.assertIn('error', response)
            self.assertEqual(client.get('/api/state'), state)

    def test_import_and_mutation_require_the_callers_current_revision(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            initial = client.get('/api/state')
            for extra in ({}, {'expected_revision': None}, {'expected_revision': True}):
                with self.subTest(extra=extra):
                    status, response = client.request('/api/import', payload={'path': str(self.first_run), **extra})
                    self.assertEqual(status, 400)
                    self.assertIn('error', response)
                    self.assertEqual(client.get('/api/state'), initial)
            state = self.import_run(client)
            self.assertEqual(client.request('/api/import', payload={
                'path': str(self.rerun), 'expected_revision': initial['revision']})[0], 409)
            self.assertEqual(client.request('/api/mutate', payload={
                'command': {'op': 'category', 'name': 'Missing revision'}})[0], 400)
            self.assertEqual(client.get('/api/state'), state)

    def test_structural_rule_matches_keep_parallel_branches_distinct_from_series(self) -> None:
        runs = Path(self.temporary.name) / 'pattern runs'
        run = saved_analysis(runs, first_texts=(
            '[XIC(Input),XIC(Input)]OTE(Output);',
            'XIC(Input)XIC(Input)OTE(Output);',
            '[XIC(Output),XIC(Output)]OTE(Input);',
        ))
        inventory = json.loads((run / 'inventory.json').read_text(encoding='utf-8'))
        parallel, series, other_parallel = inventory['rungs'][:3]
        with running_workspace(self.project, runs) as client:
            state = self.import_run(client, run)
            matches = client.get('/api/rule-matches?' + urlencode({'source_id': parallel['id']}))
            self.assertEqual({row['id'] for row in matches['items']}, {parallel['id'], other_parallel['id']})
            self.assertEqual(matches['total'], 2)
            self.assertEqual(client.get('/api/rule-matches?' + urlencode({'source_id': series['id']}))['total'], 1)
            category_id = state['categories'][0]['id']
            state = client.mutate({'op': 'rule', 'name': 'Parallel invented permissives',
                                  'source_id': parallel['id'], 'category_ids': [category_id]})
            rule_id = state['rules'][0]['id']
            for source in (parallel, other_parallel):
                detail = client.get('/api/source?' + urlencode({'id': source['id']}))
                self.assertEqual([row['rule_id'] for row in detail['rule_proposals']], [rule_id])
                self.assertEqual(detail['source'], source)
                self.assertEqual(detail['review'], {})
            self.assertEqual(client.get('/api/source?' + urlencode({'id': series['id']}))['rule_proposals'], [])
            client.mutate({'op': 'rule', 'id': rule_id, 'enabled': False})
            self.assertEqual(client.get('/api/source?' + urlencode({'id': parallel['id']}))['rule_proposals'], [])

    def test_historical_source_read_preserves_the_active_source_and_projection(self) -> None:
        runs = Path(self.temporary.name) / 'history runs'
        previous = saved_analysis(runs)
        revised = saved_analysis(runs, first_texts=('XIO(Input)OTE(Output);',), controller='RevisedWorkspace')
        current_inventory = json.loads((revised / 'inventory.json').read_text(encoding='utf-8'))
        original = self.inventory['rungs'][0]
        with running_workspace(self.project, runs) as client:
            prior_state = self.import_run(client, previous)
            prior_run_id = prior_state['active_run']
            client.mutate({'op': 'review', 'source_ids': [original['id']],
                           'fields': {'purpose': 'Keep this earlier evidence'}, 'status': 'confirmed'})
            state = self.import_run(client, revised)
            current_page = client.get('/api/rungs')
            current_detail = client.get('/api/source?' + urlencode({'id': current_inventory['rungs'][0]['id']}))
            historical = client.get('/api/source?' + urlencode({'id': original['id'], 'run_id': prior_run_id}))
            self.assertTrue(historical['historical'])
            self.assertEqual(historical['run_id'], prior_run_id)
            self.assertEqual(historical['source'], original)
            self.assertEqual(historical['review']['fields'], {'purpose': 'Keep this earlier evidence'})
            self.assertFalse(historical['review']['active'])
            self.assertTrue(historical['review']['needs_revalidation'])
            instruction_id = original['instructions'][0]['id']
            old_instruction = client.get('/api/source?' + urlencode({'id': instruction_id, 'run_id': prior_run_id}))
            self.assertEqual(old_instruction['source'], original['instructions'][0])
            self.assertTrue(old_instruction['historical'])
            self.assertEqual(client.get('/api/state'), state)
            self.assertEqual(client.get('/api/rungs'), current_page)
            self.assertEqual(client.get('/api/source?' + urlencode({'id': current_inventory['rungs'][0]['id']})), current_detail)
            self.assertEqual(client.request('/api/source?' + urlencode({'id': original['id']}))[0], 400)
            self.assertEqual(client.get('/api/state'), state)
            current_id = current_inventory['rungs'][0]['id']
            self.assertEqual({row['source_id'] for row in state['pending_reviews']}, {original['id']})
            state = client.mutate({'op': 'rebind', 'from_id': original['id'], 'to_id': current_id})
            self.assertEqual({row['source_id'] for row in state['pending_reviews']}, {current_id})
            self.assertEqual(state['reviews'][current_id]['previous_source_id'], original['id'])
            self.assertTrue(state['reviews'][current_id]['needs_revalidation'])
            state = client.mutate({'op': 'review', 'source_ids': [current_id], 'status': 'confirmed'})
            self.assertEqual(state['pending_reviews'], [])
            self.assertIn(original['id'], state['reviews'])
            self.assertEqual(state['reviews'][current_id]['fields'], {'purpose': 'Keep this earlier evidence'})

    def test_report_is_sandboxed_without_editor_or_same_origin_access(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            self.import_run(client)
            status, report = client.request('/analysis')
            self.assertEqual(status, 200)
            self.assertIn(b'InventedWorkspace', report)
            directives = {parts[0]: parts[1:] for item in client.last_headers['content-security-policy'].split(';')
                          if (parts := item.strip().split())}
            self.assertEqual(directives['sandbox'], ['allow-scripts'])
            self.assertNotIn('allow-same-origin', directives['sandbox'])
            self.assertEqual(directives['connect-src'], ["'none'"])
            self.assertEqual(directives['default-src'], ["'none'"])
            self.assertEqual(directives['form-action'], ["'none'"])
            self.assertEqual(directives['frame-ancestors'], ["'none'"])
            self.assertEqual(client.last_headers['cache-control'], 'no-store')
            self.assertEqual(client.last_headers['referrer-policy'], 'no-referrer')
            # A sandboxed report has opaque Origin:null and cannot read the API.
            self.assertEqual(client.request('/api/state', headers={'Origin': 'null'})[0], 403)
            client.get('/api/state')
            self.assertIn("connect-src 'self'", client.last_headers['content-security-policy'])

    def test_token_host_origin_and_cross_site_refusals_do_not_mutate_project(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            before = self.import_run(client)
            change = {'command': {'op': 'category', 'name': 'Untrusted category'},
                      'expected_revision': before['revision']}
            for headers in ({'X-Workspace-Token': ''}, {'X-Workspace-Token': 'incorrect'},
                            {'Host': 'example.invalid'}, {'Origin': 'https://example.invalid'},
                            {'Sec-Fetch-Site': 'cross-site'}):
                with self.subTest(headers=headers):
                    status, response = client.request('/api/mutate', payload=change, headers=headers)
                    self.assertEqual(status, 403)
                    self.assertIn('error', response)
                    self.assertEqual(client.get('/api/state'), before)
            for headers in ({'Host': 'example.invalid'}, {'Origin': 'https://example.invalid'}):
                self.assertEqual(client.request('/api/state', headers=headers)[0], 403)

    def test_routes_do_not_serve_filesystem_or_import_an_unselected_folder(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            state = client.get('/api/state')
            private_file = Path(self.temporary.name) / 'private.txt'
            private_file.write_text('Invented private marker', encoding='utf-8')
            for route in ('/../private.txt', '/%2e%2e/private.txt', '/snapshot.L5X',
                          '/confidential/private.txt', '/api/artifact?path=' + str(private_file)):
                with self.subTest(route=route):
                    status, response = client.request(route)
                    self.assertEqual(status, 404)
                    self.assertNotIn('Invented private marker', str(response))
            status, response = client.request('/api/import', payload={
                'path': str(private_file.parent), 'expected_revision': state['revision']})
            self.assertEqual(status, 400)
            self.assertIn('error', response)
            self.assertEqual(client.get('/api/state'), state)

    def test_backup_reopens_with_review_and_original_artifacts(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            self.import_run(client)
            state = client.mutate({'op': 'category', 'name': 'Portable classification'})
            category_id = next(row['id'] for row in state['categories'] if row['name'] == 'Portable classification')
            source_id = self.inventory['rungs'][0]['id']
            client.mutate({'op': 'rule', 'name': 'Portable structural proposal',
                           'source_id': source_id, 'category_ids': [category_id]})
            client.mutate({'op': 'review', 'source_ids': [source_id], 'category_ids': [category_id],
                           'status': 'confirmed', 'fields': {'purpose': 'Portable review'}})
            state = client.mutate({'op': 'group', 'name': 'Portable group', 'member_ids': [source_id]})
            backup = Path(client.post('/api/backup', {})['path'])
            original = client.get('/api/source?' + urlencode({'id': source_id}))
        self.assertTrue(backup.is_file())
        self.assertNotEqual(backup, self.project)
        with closing(sqlite3.connect(backup)) as connection:
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        with running_workspace(backup, Path(self.temporary.name) / 'no original runs') as client:
            restored = client.get('/api/state')
            for key in ('categories', 'groups', 'reviews', 'rules', 'history', 'runs', 'active_run'):
                self.assertEqual(restored[key], state[key], key)
            self.assertEqual(restored['revision'], state['revision'])
            self.assertEqual(restored['source']['rung_count'], 105)
            self.assertEqual(client.get('/api/source?' + urlencode({'id': source_id})), original)
            status, page = client.request('/analysis')
            self.assertEqual(status, 200)
            self.assertIn(b'InventedWorkspace', page)
            next_state = client.mutate({'op': 'review', 'source_ids': [source_id],
                                       'fields': {'purpose': 'Edited restored project'}})
            self.assertEqual(next_state['revision'], restored['revision'] + 1)
            self.assertEqual(next_state['reviews'][source_id]['fields']['purpose'], 'Edited restored project')
        with running_workspace(backup, Path(self.temporary.name) / 'still no original runs') as client:
            self.assertEqual(client.get('/api/state')['reviews'][source_id]['fields']['purpose'],
                             'Edited restored project')
        with running_workspace(self.project, self.runs) as client:
            self.assertEqual(client.get('/api/state')['reviews'][source_id]['fields']['purpose'], 'Portable review')

    def test_restore_creates_an_editable_copy_preserving_original_and_backup(self) -> None:
        project = Path(self.temporary.name) / 'confidential' / 'projects' / 'engineering.sqlite'
        source_id = self.inventory['rungs'][0]['id']
        with running_workspace(project, self.runs) as client:
            self.import_run(client)
            saved = client.mutate({'op': 'review', 'source_ids': [source_id],
                                   'fields': {'purpose': 'Before backup'}, 'status': 'confirmed'})
            backup = Path(client.post('/api/backup', {})['path'])
            backup_bytes = backup.read_bytes()
            changed = client.mutate({'op': 'review', 'source_ids': [source_id],
                                     'fields': {'purpose': 'After backup'}})
            listed = client.get('/api/backups')['items']
            self.assertEqual([row['name'] for row in listed], [backup.name])
            self.assertGreater(listed[0]['size_bytes'], 0)
            self.assertEqual(client.request('/api/restore', payload={
                'name': backup.name, 'expected_revision': saved['revision']})[0], 409)
            for name in ('../' + backup.name, str(backup), 'missing.sqlite'):
                with self.subTest(name=name):
                    self.assertEqual(client.request('/api/restore', payload={
                        'name': name, 'expected_revision': changed['revision']})[0], 400)
                    self.assertEqual(client.get('/api/state'), changed)
            restored = client.post('/api/restore', {'name': backup.name,
                                                    'expected_revision': changed['revision']})
            restored_path = Path(restored['project_path'])
            self.assertNotEqual(restored_path, project)
            self.assertNotEqual(restored_path, backup)
            self.assertEqual(restored['reviews'][source_id]['fields']['purpose'], 'Before backup')
            self.assertEqual(restored['revision'], saved['revision'])
            self.assertEqual(json.loads((project.parent / 'last-project.json').read_text(encoding='utf-8')),
                             {'filename': restored_path.name})
            self.assertEqual(backup.read_bytes(), backup_bytes)
            edited = client.mutate({'op': 'review', 'source_ids': [source_id],
                                    'fields': {'purpose': 'Edited restored copy'}})
            self.assertEqual(edited['revision'], saved['revision'] + 1)
        with running_workspace(project, self.runs) as client:
            self.assertEqual(client.get('/api/state')['reviews'][source_id]['fields']['purpose'], 'After backup')
        with running_workspace(restored_path, self.runs) as client:
            self.assertEqual(client.get('/api/state')['reviews'][source_id]['fields']['purpose'], 'Edited restored copy')
        selected: list[dict] = []

        def observe_launch(server: WorkspaceServer, **kwargs: object) -> None:
            selected.append(server.workspace.state())

        previous_directory = Path.cwd()
        try:
            os.chdir(self.temporary.name)
            with patch('plc_workbench.workspace.WorkspaceServer.serve_forever', new=observe_launch):
                self.assertEqual(main(['--runs', str(self.runs), '--port', '0', '--no-browser']), 0)
        finally:
            os.chdir(previous_directory)
        self.assertEqual(selected[0]['project_path'], str(restored_path))
        self.assertEqual(selected[0]['reviews'][source_id]['fields']['purpose'], 'Edited restored copy')

    def test_historical_load_failure_does_not_leave_partial_source_cache(self) -> None:
        workspace = Workspace(self.project, self.runs)
        try:
            previous = workspace.import_run(str(self.first_run), workspace.state()['revision'])
            workspace.import_run(str(self.rerun), previous['revision'])
            baseline = workspace.state()
            baseline_rungs = workspace.rungs({})
            source_id = self.inventory['rungs'][0]['id']
            with patch.object(workspace.store, 'analysis', side_effect=ProjectError('Invented read failure')):
                with self.assertRaisesRegex(ProjectError, 'Invented read failure'):
                    workspace.source(source_id, previous['active_run'])
            self.assertEqual(workspace.state(), baseline)
            self.assertEqual(workspace.rungs({}), baseline_rungs)
            self.assertTrue(workspace.source(source_id)['proposals'])
        finally:
            workspace.close()

    def test_restoring_rotates_write_token_even_when_old_tab_revision_matches(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            old_page = self.import_run(client)
            old_token = client.server.token
            backup = Path(client.post('/api/backup', {})['path'])
            changed = client.mutate({'op': 'category', 'name': 'Change after backup'})
            restored = client.post('/api/restore', {'name': backup.name,
                                                    'expected_revision': changed['revision']})
            self.assertEqual(restored['revision'], old_page['revision'])
            self.assertNotEqual(restored['workspace_token'], old_token)
            baseline = client.get('/api/state')
            old_request = {'command': {'op': 'category', 'name': 'Saved from the stale tab'},
                           'expected_revision': old_page['revision']}
            self.assertEqual(client.request('/api/mutate', payload=old_request,
                                            headers={'X-Workspace-Token': old_token})[0], 403)
            self.assertEqual(client.get('/api/state'), baseline)
            status, updated = client.request('/api/mutate', payload={
                'command': {'op': 'category', 'name': 'Saved from the restored project'},
                'expected_revision': baseline['revision'],
            }, headers={'X-Workspace-Token': restored['workspace_token']})
            self.assertEqual(status, 200)
            self.assertEqual(updated['revision'], baseline['revision'] + 1)
            self.assertIn('Saved from the restored project', {row['name'] for row in updated['categories']})
            detail = client.get('/api/source?' + urlencode({'id': self.inventory['rungs'][0]['id']}))
            self.assertEqual(detail['revision'], updated['revision'])

    def test_malformed_requests_fail_cleanly_and_leave_server_available(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            baseline = self.import_run(client)
            change = {'command': {'op': 'category', 'name': 'Do not create'},
                      'expected_revision': baseline['revision']}
            self.assertEqual(client.request('/api/mutate', payload=change,
                                            headers={'X-Workspace-Token': '\u00e9'})[0], 403)
            for raw in (b'{broken', b'{"command":' + b'[' * 1500 + b'0' + b']' * 1500 + b'}'):
                with self.subTest(size=len(raw)):
                    self.assertEqual(client.request('/api/mutate', raw=raw)[0], 400)
                    self.assertEqual(client.get('/api/state'), baseline)

    def test_accepted_connection_has_a_finite_read_timeout(self) -> None:
        workspace = Workspace(self.project, self.runs)
        try:
            server = WorkspaceServer(('127.0.0.1', 0), workspace)
            connection = Mock()
            address = ('127.0.0.1', 1234)
            try:
                with patch('http.server.HTTPServer.get_request', return_value=(connection, address)):
                    self.assertEqual(server.get_request(), (connection, address))
                connection.settimeout.assert_called_once()
                timeout = connection.settimeout.call_args.args[0]
                self.assertGreater(timeout, 0)
                self.assertLessEqual(timeout, 10)
            finally:
                server.server_close()
        finally:
            workspace.close()

    def test_launcher_only_listens_locally_without_git_or_external_requests(self) -> None:
        with patch('plc_workbench.workspace.WorkspaceServer.serve_forever'), \
                patch('plc_workbench.workspace.webbrowser.open') as browser, \
                patch('subprocess.Popen', side_effect=AssertionError('Launcher spawned a process')), \
                patch('socket.create_connection', side_effect=AssertionError('Launcher contacted a remote host')), \
                patch('urllib.request.urlopen', side_effect=AssertionError('Launcher requested a URL')):
            self.assertEqual(main(['--project', str(self.project), '--runs', str(self.runs),
                                   '--port', '0', '--no-browser']), 0)
            browser.assert_not_called()
        with running_workspace(self.project, self.runs) as client:
            self.assertEqual(client.get('/api/state')['source']['rung_count'], 0)

    def test_automatic_launch_imports_exact_run_after_binding_before_browser(self) -> None:
        servers: list[WorkspaceServer] = []
        events: list[str] = []
        expected = json.loads((self.first_run / 'manifest.json').read_text())['run_id']

        def bind(address: tuple[str, int], workspace: Workspace) -> WorkspaceServer:
            server = WorkspaceServer(address, workspace)
            servers.append(server)
            events.append('bound')
            self.assertIsNone(workspace.state()['active_run'])
            return server

        def open_browser(url: str) -> bool:
            events.append('browser')
            state = servers[0].workspace.state()
            self.assertEqual(url, servers[0].origin)
            self.assertEqual(state['active_run'], expected)
            self.assertEqual(state['source']['rung_count'], 105)
            self.assertIn('105 captured rungs', state['startup_notice'])
            self.assertIn('Analysis ready', state['startup_notice'])
            return True

        def serve(server: WorkspaceServer, **_: object) -> None:
            events.append('serving')
            self.assertEqual(server.workspace.state()['active_run'], expected)

        with patch('plc_workbench.workspace.WorkspaceServer', side_effect=bind), \
                patch.object(WorkspaceServer, 'serve_forever', new=serve), \
                patch('plc_workbench.workspace.webbrowser.open', side_effect=open_browser):
            self.assertEqual(main(['--project', str(self.project), '--runs', str(self.runs),
                                   '--import-run', str(self.first_run), '--port', '0']), 0)
        self.assertEqual(events, ['bound', 'browser', 'serving'])
        self.assertEqual(servers[0].socket.fileno(), -1)
        with self.assertRaises(sqlite3.ProgrammingError):
            servers[0].workspace.store.connection.execute('SELECT 1')

    def test_automatic_failed_import_closes_resources_without_opening_browser(self) -> None:
        workspace = Workspace(self.project, self.runs)
        workspace.close()
        before = self.project.read_bytes()
        for run in (self.runs / 'missing-run', Path(self.temporary.name)):
            servers: list[WorkspaceServer] = []

            def bind(address: tuple[str, int], selected: Workspace) -> WorkspaceServer:
                server = WorkspaceServer(address, selected)
                servers.append(server)
                return server

            with self.subTest(run=run), \
                    patch('plc_workbench.workspace.WorkspaceServer', side_effect=bind), \
                    patch.object(WorkspaceServer, 'serve_forever') as serve, \
                    patch('plc_workbench.workspace.webbrowser.open') as browser:
                self.assertEqual(main(['--project', str(self.project), '--runs', str(self.runs),
                                       '--import-run', str(run), '--port', '0']), 1)
                browser.assert_not_called()
                serve.assert_not_called()
            self.assertEqual(self.project.read_bytes(), before)
            self.assertEqual(servers[0].socket.fileno(), -1)
            with self.assertRaises(sqlite3.ProgrammingError):
                servers[0].workspace.store.connection.execute('SELECT 1')

    def test_automatic_occupied_port_does_not_import_or_change_database(self) -> None:
        workspace = Workspace(self.project, self.runs)
        server = WorkspaceServer(('127.0.0.1', 0), workspace)
        try:
            before = workspace.state()
            before_bytes = self.project.read_bytes()
            with patch.object(Workspace, 'import_run') as import_run, \
                    patch('plc_workbench.workspace.webbrowser.open') as browser:
                self.assertEqual(main(['--project', str(self.project), '--runs', str(self.runs),
                                       '--import-run', str(self.first_run),
                                       '--port', str(server.server_address[1])]), 1)
                import_run.assert_not_called()
                browser.assert_not_called()
            self.assertEqual(workspace.state(), before)
            self.assertEqual(self.project.read_bytes(), before_bytes)
        finally:
            server.server_close()
            workspace.close()

    def test_automatic_invalid_selection_fails_before_creating_fallback(self) -> None:
        previous_directory = Path.cwd()
        try:
            for index, content in enumerate(('{broken', '[]', '{"filename":"../outside.sqlite"}',
                                             '{"filename":"missing.sqlite"}', ' ' * 1025)):
                with self.subTest(content=content[:50]):
                    case = Path(self.temporary.name) / f'case-{index}'
                    projects = case / 'confidential' / 'projects'
                    projects.mkdir(parents=True)
                    pointer = projects / 'last-project.json'
                    pointer.write_text(content, encoding='utf-8')
                    os.chdir(case)
                    with patch('plc_workbench.workspace.Workspace') as construct, \
                            patch('plc_workbench.workspace.webbrowser.open') as browser:
                        self.assertEqual(main(['--runs', str(self.runs), '--port', '0',
                                               '--import-run', str(self.first_run)]), 1)
                        construct.assert_not_called()
                        browser.assert_not_called()
                    self.assertFalse((projects / 'engineering.sqlite').exists())
                    self.assertEqual(pointer.read_text(encoding='utf-8'), content)
        finally:
            os.chdir(previous_directory)

    def test_automatic_import_uses_selected_restored_project_and_preserves_reviews(self) -> None:
        projects = Path(self.temporary.name) / 'confidential' / 'projects'
        restored = projects / 'restored-selection.sqlite'
        workspace = Workspace(restored, self.runs)
        try:
            initial = workspace.import_run(str(self.first_run), workspace.state()['revision'])
            source_id = self.inventory['rungs'][0]['id']
            workspace.store.mutate({'op': 'review', 'source_ids': [source_id], 'status': 'confirmed',
                                    'fields': {'purpose': 'Keep my correction'}}, initial['revision'])
        finally:
            workspace.close()
        pointer = projects / 'last-project.json'
        pointer.write_text(json.dumps({'filename': restored.name}), encoding='utf-8')
        observed: list[dict] = []

        def serve(server: WorkspaceServer, **_: object) -> None:
            observed.append(server.workspace.state())

        previous_directory = Path.cwd()
        try:
            os.chdir(self.temporary.name)
            with patch.object(WorkspaceServer, 'serve_forever', new=serve), \
                    patch('plc_workbench.workspace.webbrowser.open') as browser:
                self.assertEqual(main(['--runs', str(self.runs), '--import-run', str(self.rerun),
                                       '--port', '0', '--no-browser']), 0)
                browser.assert_not_called()
        finally:
            os.chdir(previous_directory)
        self.assertEqual(observed[0]['project_path'], str(restored))
        self.assertEqual(observed[0]['reviews'][source_id]['fields']['purpose'], 'Keep my correction')
        self.assertEqual(observed[0]['reviews'][source_id]['status'], 'confirmed')
        expected = json.loads((self.rerun / 'manifest.json').read_text())['run_id']
        self.assertEqual(observed[0]['active_run'], expected)
        self.assertFalse((projects / 'engineering.sqlite').exists())

    def test_automatic_invalid_selected_database_never_creates_fallback(self) -> None:
        projects = Path(self.temporary.name) / 'confidential' / 'projects'
        projects.mkdir(parents=True)
        selected = projects / 'selected.sqlite'
        selected.write_bytes(b'This is not a project database')
        (projects / 'last-project.json').write_text(json.dumps({'filename': selected.name}), encoding='utf-8')
        previous_directory = Path.cwd()
        try:
            os.chdir(self.temporary.name)
            with patch('plc_workbench.workspace.webbrowser.open') as browser, \
                    patch.object(Workspace, 'import_run') as import_run:
                self.assertEqual(main(['--runs', str(self.runs), '--port', '0',
                                       '--import-run', str(self.first_run)]), 1)
                browser.assert_not_called()
                import_run.assert_not_called()
        finally:
            os.chdir(previous_directory)
        self.assertFalse((projects / 'engineering.sqlite').exists())
        self.assertEqual(selected.read_bytes(), b'This is not a project database')

    def test_exclusive_listener_can_reopen_same_port_after_clean_shutdown(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            port = client.server.server_address[1]
            client.get('/api/state')
        workspace = Workspace(self.project, self.runs)
        try:
            server = WorkspaceServer(('127.0.0.1', port), workspace)
            server.server_close()
        finally:
            workspace.close()

    def test_manual_invalid_selection_retains_explanatory_fallback(self) -> None:
        projects = Path(self.temporary.name) / 'confidential' / 'projects'
        projects.mkdir(parents=True)
        (projects / 'last-project.json').write_text('{broken', encoding='utf-8')
        observed: list[dict] = []

        def serve(server: WorkspaceServer, **_: object) -> None:
            observed.append(server.workspace.state())

        previous_directory = Path.cwd()
        try:
            os.chdir(self.temporary.name)
            with patch.object(WorkspaceServer, 'serve_forever', new=serve):
                self.assertEqual(main(['--runs', str(self.runs), '--port', '0', '--no-browser']), 0)
        finally:
            os.chdir(previous_directory)
        self.assertEqual(observed[0]['project_path'], str(projects / 'engineering.sqlite'))
        self.assertIn('default project is open', observed[0]['startup_notice'])
        self.assertEqual(observed[0]['source']['rung_count'], 0)


if __name__ == '__main__':
    unittest.main()
