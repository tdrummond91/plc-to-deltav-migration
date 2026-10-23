"""Requested page sizes reach every source row without altering project evidence."""
from __future__ import annotations

import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from plc_workbench.project_store import ProjectError
from plc_workbench.workspace_paging import GRAPH_SIZES, LIST_SIZES, page_size
from plc_workbench.workspace_connections import ConnectionError
from test_workspace import running_workspace
from test_workspace_connections import multi_routine
from test_workspace_map_api import save_map_fixture, save_map_inputs


class PageSizeValidationTests(unittest.TestCase):
    def test_supported_sizes_and_each_legacy_default_are_preserved(self):
        for default in (20, 24, 50, 250):
            self.assertEqual(page_size({}, default), default)
            for size in (*LIST_SIZES, default):
                for value in (size, str(size)):
                    with self.subTest(default=default, value=value):
                        self.assertEqual(page_size({'page_size': value}, default), size)
        for default in (8, 12, 80):
            self.assertEqual(page_size({}, default, graph=True), default)
            for size in (*GRAPH_SIZES, default):
                self.assertEqual(page_size({'count': str(size)}, default, key='count', graph=True), size)

    def test_noninteger_unicode_oversized_and_unadvertised_sizes_are_rejected(self):
        invalid = (True, False, None, [], {}, 10.0, 10.5, '', ' 10', '10 ', '+10', '-10',
                   '10.0', '1e2', '\u0661\u0660', '\uff11\uff10', '9' * 10000, 10**100,
                   0, 1, 11, 25, 49, 51, 501, 1000)
        for value in invalid:
            with self.subTest(value=str(value)[:30]):
                with self.assertRaisesRegex(ProjectError, 'available page sizes'):
                    page_size({'page_size': value}, 50, error=ProjectError)
        for default in (8, 12, 80):
            for value in (20, 200, 500, *(set((8, 12, 80)) - {default})):
                with self.subTest(default=default, graph=value), self.assertRaises(ValueError):
                    page_size({'page_size': value}, default, graph=True)


class WorkspacePagingApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixtures.cleanup)
        cls.runs = Path(cls.fixtures.name) / 'runs'
        cls.bus = save_map_fixture(cls.runs)
        cls.bus_inventory = json.loads((cls.bus / 'inventory.json').read_text(encoding='utf-8'))
        declarations = ''.join(f'<Tag Name="Line{number:03}" TagType="Base" DataType="BOOL"/>' for number in range(64))
        declarations += ''.join(f'<Tag Name="Spare{number:03}" TagType="Base" DataType="BOOL"/>' for number in range(260))
        texts = [''.join(f'OTE(Line{number:03})' for number in range(32)) + ';']
        texts += [f'XIC(Line{number:03})OTE(Line{number + 32:03});' for number in range(32)]
        rungs = ''.join(f'<Rung Number="{number}" Type="N"><Text>{text}</Text></Rung>'
                        for number, text in enumerate(texts))
        program = ('<Program Name="Paging"><Tags>' + declarations + '</Tags><Routines>'
                   '<Routine Name="AllSignals" Type="RLL"><RLLContent>' + rungs
                   + '</RLLContent></Routine></Routines></Program>')
        cls.wide = save_map_inputs(cls.runs, multi_routine(program))
        cls.wide_inventory = json.loads((cls.wide / 'inventory.json').read_text(encoding='utf-8'))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / 'project.sqlite'

    def imported(self, client, run: Path | None = None):
        return client.post('/api/import', {'path': str(run or self.bus), 'expected_revision': 0})

    def get(self, client, route: str, **query):
        return client.get(route + '?' + urlencode(query))

    def collect(self, client, route: str, size: int, **query):
        first = self.get(client, route, page_size=size, **query)
        self.assertEqual(first['page_size'], size)
        pages = max(1, math.ceil(first['total'] / size))
        if 'pages' in first:
            self.assertEqual(first['pages'], pages)
        rows = list(first['items'])
        for number in range(2, pages + 1):
            response = self.get(client, route, page_size=size, page=number, **query)
            self.assertEqual(response['page'], number)
            self.assertEqual(response['total'], first['total'])
            self.assertEqual(response['page_size'], size)
            self.assertLessEqual(len(response['items']), size)
            rows.extend(response['items'])
        self.assertEqual(len(rows), first['total'])
        self.assertEqual(len({row['id'] for row in rows}), first['total'])
        return rows

    def test_rung_and_object_pages_keep_complete_identity_order_and_filters(self):
        with running_workspace(self.project, self.runs) as client:
            before = self.imported(client, self.wide)
            for route in ('/api/rungs', '/api/objects'):
                with self.subTest(route=route):
                    default = client.get(route)
                    self.assertEqual(default['page_size'], 50)
                    small = self.collect(client, route, 10)
                    large = self.collect(client, route, 500)
                    self.assertEqual([row['id'] for row in small], [row['id'] for row in large])
                    self.assertEqual(default['items'], large[:50])
            filtered = self.collect(client, '/api/objects', 10, kind='tag', query='Spare')
            self.assertEqual(len(filtered), 260)
            self.assertTrue(all(row['kind'] == 'tag' and row['name'].startswith('Spare') for row in filtered))
            self.assertEqual(client.get('/api/state')['revision'], before['revision'])
            self.assertEqual(client.get('/api/state')['reviews'], {})

    def test_routine_ladder_10_and_500_cover_all_270_complete_original_rungs(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.imported(client)
            routine = state['routines'][0]['id']
            self.assertEqual(self.get(client, '/api/routine-ladder', routine=routine)['page_size'], 20)
            expected = [row for row in self.bus_inventory['rungs'] if row['parent_id'] == routine]
            self.assertEqual(len(expected), 270)
            for size in (10, 500):
                rows = self.collect(client, '/api/routine-ladder', size, routine=routine, run_id=state['active_run'])
                self.assertEqual([row['id'] for row in rows], [row['id'] for row in expected])
                for actual, original in zip(rows, expected):
                    for key in ('text', 'instructions', 'structure', 'comment', 'parse_status'):
                        self.assertEqual(actual.get(key), original.get(key))
            self.assertEqual(self.get(client, '/api/routine-ladder', routine=routine, page_size=500, page=999)['page'], 1)
            self.assertEqual(client.get('/api/state')['revision'], state['revision'])

    def test_classification_and_map_sizes_change_pages_without_omitting_evidence(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.imported(client, self.wide)
            default = client.get('/api/classification')
            self.assertEqual(default['page_size'], 50)
            self.assertGreater(default['total'], 10)
            for route in ('/api/classification', '/api/ladder-map'):
                small = self.collect(client, route, 10)
                large = self.collect(client, route, 500)
                self.assertEqual([row['id'] for row in small], [row['id'] for row in large])
            self.assertEqual(client.get('/api/ladder-map')['page_size'], 250)
            self.assertEqual(client.get('/api/state')['revision'], state['revision'])
            self.assertEqual(client.get('/api/state')['groups'], [])

    def test_connections_and_map_links_signal_paging_reaches_all_32_exact_signals(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.imported(client, self.wide)
            focus = self.wide_inventory['rungs'][0]['id']
            default = self.get(client, '/api/connections', id=focus)
            self.assertEqual(default['pagination'], {'page': 1, 'pages': 3, 'page_size': 12, 'total': 32, 'has_more': True})
            expected = self.get(client, '/api/connections', id=focus, page_size=50)['signals']
            actual = []
            for number in range(1, 5):
                response = self.get(client, '/api/connections', id=focus, page_size=10, page=number)
                self.assertEqual(response['pagination']['pages'], 4)
                self.assertLessEqual(len(response['signals']), 10)
                actual.extend(response['signals'])
            self.assertEqual([row['id'] for row in actual], [row['id'] for row in expected])
            self.assertEqual(len(set(row['id'] for row in actual)), 32)
            self.assertTrue(all(row['endpoints']['page_size'] == 8 for row in expected))
            links = self.get(client, '/api/ladder-map/links', ids=focus)
            self.assertEqual((links['total'], links['page_size']), (32, 80))
            smaller = [row for number in range(1, 5) for row in self.get(
                client, '/api/ladder-map/links', ids=focus, page_size=10, page=number)['signals']]
            self.assertEqual([row['id'] for row in smaller], [row['id'] for row in links['signals']])
            self.assertEqual(client.get('/api/state')['revision'], state['revision'])

    def test_connection_endpoint_sizes_keep_all_267_readers_in_their_source_scope(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.imported(client)
            focus = self.bus_inventory['rungs'][0]['id']
            initial = self.get(client, '/api/connections', id=focus)
            shared = next(row for row in initial['signals'] if row['label'] == 'Shared')
            self.assertEqual(shared['endpoints']['totals']['readers'], 267)
            self.assertEqual(shared['endpoints']['page_size'], 8)
            expected = {row['id'] for row in self.bus_inventory['rungs'][1:268]}
            for size in (10, 50):
                readers = []
                pages = math.ceil(267 / size)
                for number in range(1, pages + 1):
                    row = self.get(client, '/api/connections', id=focus, signal_id=shared['id'],
                                   endpoint_page_size=size, endpoint_page=number)['signals'][0]
                    self.assertEqual(row['endpoints']['pages'], pages)
                    self.assertEqual(row['endpoints']['page_size'], size)
                    self.assertLessEqual(len(row['readers']), size)
                    readers.extend(endpoint['id'] for endpoint in row['readers'])
                self.assertEqual(len(readers), 267)
                self.assertEqual(set(readers), expected)
            self.assertEqual(client.get('/api/state')['revision'], state['revision'])

    def test_http_invalid_sizes_fail_without_project_changes(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.imported(client)
            focus = self.bus_inventory['rungs'][0]['id']
            routes = [('/api/rungs', {}), ('/api/objects', {}), ('/api/classification', {}),
                      ('/api/ladder-map', {}), ('/api/routine-ladder', {'routine': state['routines'][0]['id']})]
            for route, query in routes:
                for value in ('true', '10.0', '9' * 200, '\u0661\u0660', '51'):
                    with self.subTest(route=route, value=value[:20]):
                        status, response = client.request(route + '?' + urlencode({**query, 'page_size': value}))
                        self.assertEqual(status, 400)
                        self.assertIn('page size', response['error'])
            for route, query in (('/api/connections', {'id': focus}), ('/api/ladder-map/links', {'ids': focus})):
                for value in (200, 500, '10.0', '\uff11\uff10'):
                    with self.subTest(route=route, graph_size=value):
                        self.assertEqual(client.request(route + '?' + urlencode({**query, 'page_size': value}))[0], 400)
            for value in (12, 200, 500, 'False'):
                self.assertEqual(client.request('/api/connections?' + urlencode(
                    {'id': focus, 'endpoint_page_size': value}))[0], 400)
            self.assertEqual(client.get('/api/state')['revision'], state['revision'])

    def test_connection_response_size_cap_fails_explicitly_instead_of_truncating(self):
        from test_workspace_connections import build
        from test_relationships import capture

        inputs = capture(('MOV(A,B);', 'XIC(B)OTE(C);'))
        index = build(inputs)
        focus = inputs[1].rungs[0].id
        self.assertTrue(index.view(focus)['signals'])
        with running_workspace(self.project, self.runs) as client:
            self.imported(client)
            with patch('plc_workbench.workspace_connections.MAX_VIEW_BYTES', 1):
                status, payload = client.request('/api/connections?' + urlencode({'id': self.bus_inventory['rungs'][0]['id']}))
                self.assertEqual(status, 400)
                self.assertIn('Choose fewer', payload['error'])
        with patch('plc_workbench.workspace_connections.MAX_VIEW_BYTES', 1):
            with self.assertRaisesRegex(ConnectionError, 'Choose fewer'):
                index.view(focus, page_size=100, endpoint_page_size=100)
        self.assertTrue(index.view(focus)['signals'])
