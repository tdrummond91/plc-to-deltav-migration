"""Source-family filtering agrees across the map and editable rung inventory."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from plc_workbench.workspace_classification import _qualify_source
from plc_workbench.workspace_map import LadderMapIndex
from test_workspace import running_workspace, saved_analysis
from test_workspace_connections import multi_routine
from test_workspace_map_api import save_map_fixture, save_map_inputs
from test_relationships import tag


class WorkspaceRungFamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixtures.cleanup)
        cls.runs = Path(cls.fixtures.name) / 'runs'
        cls.bus = save_map_fixture(cls.runs)
        cls.mixed = saved_analysis(cls.runs, first_texts=(
            'CPT(Result,Input+1);', 'XIC(Input)OTE(Output);', 'Mystery(Input);', ';', 'XIC(Input'))
        foreign = ('<Program Name="P"><Routines><Routine Name="R" Type="RLL"><RLLContent>'
                   '<Rung Number="0" Type="N" xmlns:x="urn:extension" x:flag="1"><Text>OTE(A);</Text></Rung>'
                   '<Rung Number="1" Type="N"><Text>XIC(A);</Text></Rung>'
                   '</RLLContent></Routine></Routines></Program>')
        cls.foreign = save_map_inputs(cls.runs, multi_routine(foreign, tag('A')))

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name) / 'project.sqlite'

    def import_run(self, client, run: Path) -> dict:
        return client.post('/api/import', {'path': str(run),
                                          'expected_revision': client.get('/api/state')['revision']})

    def rungs(self, client, **query) -> dict:
        return client.get('/api/rungs?' + urlencode(query))

    def test_empty_project_and_invalid_family(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            self.assertEqual(self.rungs(client)['families'], [])
            self.assertEqual(self.rungs(client, family='calculation')['total'], 0)
            for invalid in ('Not a family', 'x' * 81):
                self.assertEqual(client.request('/api/rungs?' + urlencode({'family': invalid}))[0], 400)

    def test_map_and_rungs_share_cached_qualification_and_family_counts(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            state = self.import_run(client, self.bus)
            with (patch('plc_workbench.workspace_classification._qualify_source', wraps=_qualify_source) as qualify,
                  patch('plc_workbench.workspace_map.LadderMapIndex', wraps=LadderMapIndex) as constructor,
                  patch('plc_workbench.workspace_report.read_report_data', side_effect=AssertionError('No full report'))):
                ordinary = self.rungs(client)
                overview = client.get('/api/ladder-map')
                self.rungs(client, family='boolean_condition')
                source = client.get('/api/source?' + urlencode({'id': ordinary['items'][0]['id']}))
                instruction = client.get('/api/source?' + urlencode({'id': source['source']['instructions'][0]['id']}))
                self.assertEqual(qualify.call_count, 1)
                self.assertEqual(constructor.call_count, 1)
            self.assertEqual(ordinary['families'], overview['families'])
            self.assertEqual(ordinary['total'], overview['total'])
            self.assertEqual(ordinary['items'][0]['families'], overview['items'][0]['families'])
            self.assertTrue(ordinary['items'][0]['source_qualified'])
            self.assertTrue(source['source_qualified'])
            self.assertTrue(instruction['source_qualified'])
            self.assertEqual(client.get('/api/state')['revision'], state['revision'])

    def test_family_intersects_routine_search_review_status_category_and_group(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            state = self.import_run(client, self.mixed)
            first_routine, other_routine = [row['id'] for row in state['routines']]
            calculation = self.rungs(client, family='calculation')['items'][0]
            state = client.mutate({'op': 'category', 'name': 'Reviewed calculation'})
            category = next(row['id'] for row in state['categories'] if row['name'] == 'Reviewed calculation')
            client.mutate({'op': 'review', 'source_ids': [calculation['id']], 'category_ids': [category],
                           'status': 'confirmed', 'fields': {'purpose': 'Unique checked transformation'}})
            state = client.mutate({'op': 'group', 'name': 'Checked group', 'member_ids': [calculation['id']]})
            group = next(row['id'] for row in state['groups'] if row['name'] == 'Checked group')
            filters = {'family': 'calculation', 'routine': first_routine, 'category': category,
                       'status': 'confirmed', 'group': group, 'query': 'Unique checked transformation'}
            match = self.rungs(client, **filters)
            self.assertEqual([row['id'] for row in match['items']], [calculation['id']])
            # Each existing filter continues to narrow a source-family selection.
            for key, value in (('family', 'boolean_output'), ('routine', other_routine),
                               ('category', 'different-category'), ('status', 'unreviewed'),
                               ('group', 'different-group'), ('query', 'absent description')):
                with self.subTest(filter=key):
                    self.assertEqual(self.rungs(client, **dict(filters, **{key: value}))['total'], 0)
            self.assertEqual(self.rungs(client, category=category)['total'], 1)
            self.assertEqual(self.rungs(client)['total'], 105)
            self.assertEqual(match['families'], self.rungs(client)['families'])

    def test_all_matching_rungs_remain_reachable_across_pages(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            self.import_run(client, self.bus)
            expected = []
            for page in (1, 2):
                expected.extend(client.get('/api/ladder-map?' + urlencode(
                    {'family': 'boolean_condition', 'page': page}))['items'])
            first = self.rungs(client, family='boolean_condition')
            pages = (first['total'] + first['page_size'] - 1) // first['page_size']
            actual = [row for page in range(1, pages + 1)
                      for row in self.rungs(client, family='boolean_condition', page=page)['items']]
            self.assertEqual([row['id'] for row in actual], [row['id'] for row in expected])
            self.assertEqual(len(actual), first['total'])
            self.assertEqual(len({row['id'] for row in actual}), len(actual))
            self.assertGreater(pages, 1)

    def test_unsupported_source_stays_unknown_and_import_refreshes_choices(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            self.import_run(client, self.mixed)
            self.assertEqual(self.rungs(client, family='calculation')['total'], 1)
            self.assertEqual(self.rungs(client, family='unknown')['total'], 1)
            self.assertEqual(self.rungs(client, family='unparsed')['total'], 1)
            self.assertEqual(self.rungs(client, family='empty')['total'], 1)
            self.import_run(client, self.foreign)
            unknown = self.rungs(client, family='unknown')
            self.assertEqual(unknown['total'], 1)
            self.assertEqual(unknown['items'][0]['families'], ['unknown'])
            self.assertFalse(unknown['items'][0]['source_qualified'])
            detail = client.get('/api/source?' + urlencode({'id': unknown['items'][0]['id']}))
            instruction = client.get('/api/source?' + urlencode({'id': detail['source']['instructions'][0]['id']}))
            self.assertFalse(detail['source_qualified'])
            self.assertFalse(instruction['source_qualified'])
            self.assertEqual(self.rungs(client, family='boolean_output')['total'], 0)
            self.assertEqual(self.rungs(client, family='boolean_condition')['total'], 1)
            self.assertEqual(self.rungs(client, family='calculation')['total'], 0)
            self.assertEqual(unknown['families'], client.get('/api/ladder-map')['families'])


if __name__ == '__main__':
    unittest.main()
