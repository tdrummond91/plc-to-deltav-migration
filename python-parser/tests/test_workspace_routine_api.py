"""Routine pages use complete saved source and keep unsupported evidence visible."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from plc_workbench.workspace_classification import _qualify_source
from test_workspace import running_workspace, saved_analysis
from test_workspace_connections import multi_routine, routine
from test_workspace_map_api import save_map_fixture, save_map_inputs


class WorkspaceRoutineApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixtures.cleanup)
        cls.runs = Path(cls.fixtures.name) / 'runs'
        cls.bus = save_map_fixture(cls.runs)
        cls.changed = saved_analysis(cls.runs, controller='ChangedRoutineSource')
        cls.inventory = json.loads((cls.bus / 'inventory.json').read_text(encoding='utf-8'))
        unsupported = (
            '<Routine Name="Foreign" Type="RLL" xmlns:x="urn:extension" x:flag="1">'
            '<RLLContent><Rung Number="10" Type="N"><Text>XIC(Input)OTE(Output);</Text></Rung>'
            '</RLLContent></Routine>'
            '<Routine Name="Structured" Type="ST"><STContent><Line Number="0">Output := Input;</Line>'
            '</STContent></Routine>'
            '<Routine Name="Empty" Type="RLL"><RLLContent/></Routine>'
            '<Routine Name="Unspecified"><RLLContent><Rung Number="4" Type="N">'
            '<Text>XIO(Input)OTE(Output);</Text></Rung></RLLContent></Routine>')
        rich = ('<Routine Name="Branches" Type="RLL"><RLLContent>'
                '<Rung Number="9" Type="N"><Text>XIC(Input)[XIO(Inhibit),XIC(Bypass)]OTE(Output);</Text>'
                '<Comment>Commentaire invente</Comment></Rung>'
                '<Rung Number="2" Type="N"><Text>UnsupportedCall(A,B);</Text></Rung>'
                '<Rung Number="1" Type="N"><Text>XIC(Unfinished</Text></Rung>'
                '</RLLContent></Routine>')
        programs = f'<Program Name="Review"><Routines>{unsupported}{rich}</Routines></Program>'
        cls.mixed = save_map_inputs(cls.runs, multi_routine(programs))
        aois = '<AddOnInstructionDefinitions>' + ''.join(
            f'<AddOnInstructionDefinition Name="{name}"><Routines>' + routine('Logic', 'XIC(Input)OTE(Output);')
            + '</Routines></AddOnInstructionDefinition>' for name in ('FirstWidget', 'SecondWidget')) + '</AddOnInstructionDefinitions>'
        cls.aoi_run = save_map_inputs(cls.runs, multi_routine(
            '<Program Name="MainProgram"><Routines>' + routine('Logic', 'XIC(Input)OTE(Output);')
            + '</Routines></Program>', extra=aois))

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name) / 'project.sqlite'

    def import_run(self, client, run: Path | None = None) -> dict:
        return client.post('/api/import', {'path': str(run or self.bus),
                                          'expected_revision': client.get('/api/state')['revision']})

    def get(self, client, **query) -> dict:
        return client.get('/api/routine-ladder?' + urlencode(query))

    def test_program_metadata_and_paging_reach_every_original_rung_without_scope_collision(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.import_run(client)
            first, second = state['routines']
            self.assertEqual(first['name'], second['name'])
            self.assertNotEqual(first['program_id'], second['program_id'])
            self.assertEqual((first['program_name'], second['program_name']), ('First', 'Second'))
            self.assertIn('/ First', first['program_path'])
            self.assertEqual(first['scope_id'], first['program_id'])
            self.assertEqual(first['scope_path'], first['program_path'])
            self.assertEqual(first['scope_kind'], 'program')
            first_page = self.get(client, routine=first['id'], run_id=state['active_run'])
            self.assertEqual((first_page['page_size'], first_page['pages'], first_page['total']), (20, 14, 270))
            actual = [row for page in range(1, first_page['pages'] + 1)
                      for row in self.get(client, routine=first['id'], page=page)['items']]
            expected = [row for row in self.inventory['rungs'] if row['parent_id'] == first['id']]
            self.assertEqual(len(actual), len(expected))
            self.assertEqual([row['id'] for row in actual], [row['id'] for row in expected])
            for shown, captured in zip(actual, expected):
                for key, value in captured.items():
                    self.assertEqual(shown[key], value)
            self.assertEqual(self.get(client, routine=first['id'], page=100)['page'], 14)
            self.assertEqual(self.get(client, routine=second['id'])['total'], 1)
            self.assertEqual(client.get('/api/state')['revision'], state['revision'])
            self.assertEqual(first_page['run_id'], state['active_run'])
            self.assertEqual(first_page['revision'], state['revision'])

    def test_same_named_routines_in_distinct_aois_have_distinct_explicit_scopes(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.import_run(client, self.aoi_run)
            self.assertEqual(len(state['routines']), 3)
            self.assertEqual({row['name'] for row in state['routines']}, {'Logic'})
            aois = [row for row in state['routines'] if row['scope_kind'] == 'aoi']
            self.assertEqual(len(aois), 2)
            self.assertEqual({row['scope_name'] for row in aois}, {'FirstWidget', 'SecondWidget'})
            self.assertEqual(len({row['scope_id'] for row in aois}), 2)
            self.assertEqual(len({row['scope_path'] for row in aois}), 2)
            for routine_row in aois:
                self.assertEqual(routine_row['program_id'], '')
                self.assertEqual(routine_row['program_name'], '')
                self.assertEqual(routine_row['program_path'], '')
                response = self.get(client, routine=routine_row['id'])
                self.assertEqual(response['routine']['scope_id'], routine_row['scope_id'])
                self.assertEqual(response['routine']['scope_kind'], 'aoi')
                self.assertEqual(response['total'], 1)
                self.assertEqual(response['items'][0]['parent_id'], routine_row['id'])
            program = next(row for row in state['routines'] if row['scope_kind'] == 'program')
            self.assertEqual(program['scope_name'], 'MainProgram')
            self.assertEqual(program['scope_id'], program['program_id'])

    def test_captured_source_order_branches_unknown_blocks_and_unparsed_text_are_preserved(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.import_run(client, self.mixed)
            routine_id = next(row['id'] for row in state['routines'] if row['name'] == 'Branches')
            page = self.get(client, routine=routine_id)
            self.assertTrue(page['available'])
            self.assertEqual([row['number'] for row in page['items']], ['9', '2', '1'])
            first, opaque, incomplete = page['items']
            self.assertTrue(first['source_qualified'])
            self.assertEqual(first['comment'], 'Commentaire invente')
            self.assertEqual(first['structure']['items'][1]['kind'], 'branch')
            self.assertEqual(len(first['structure']['items'][1]['legs']), 2)
            self.assertEqual([item['opcode'] for item in first['instructions']], ['XIC', 'XIO', 'XIC', 'OTE'])
            self.assertEqual(opaque['instructions'][0]['arguments'], ['A', 'B'])
            self.assertEqual(opaque['instructions'][0]['opcode'], 'UnsupportedCall')
            self.assertEqual(incomplete['text'], 'XIC(Unfinished')
            self.assertNotEqual(incomplete['parse_status'], 'parsed')

    def test_unqualified_and_non_ladder_routines_keep_source_evidence_without_diagram_eligibility(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.import_run(client, self.mixed)
            routines = {row['name']: row['id'] for row in state['routines']}
            foreign = self.get(client, routine=routines['Foreign'])
            self.assertFalse(foreign['available'])
            self.assertFalse(foreign['routine']['source_qualified'])
            self.assertEqual(foreign['total'], 1)
            self.assertEqual(foreign['items'][0]['text'], 'XIC(Input)OTE(Output);')
            self.assertFalse(foreign['items'][0]['source_qualified'])
            self.assertIn('unsupported source qualification', foreign['notice'])
            structured = self.get(client, routine=routines['Structured'])
            self.assertFalse(structured['available'])
            self.assertEqual(structured['routine']['type'], 'ST')
            self.assertEqual(structured['routine']['source_id'], routines['Structured'])
            self.assertEqual(structured['items'], [])
            self.assertIn('exported as ST', structured['notice'])
            unspecified = self.get(client, routine=routines['Unspecified'])
            self.assertFalse(unspecified['available'])
            self.assertEqual(unspecified['total'], 1)
            self.assertFalse(unspecified['items'][0]['source_qualified'])
            self.assertIn('an unspecified routine type', unspecified['notice'])
            empty = self.get(client, routine=routines['Empty'])
            self.assertTrue(empty['available'])
            self.assertEqual((empty['total'], empty['page'], empty['pages']), (0, 1, 1))
            self.assertIn('protected or omitted source', empty['notice'])

    def test_request_validation_and_stale_run_guard(self):
        with running_workspace(self.project, self.runs) as client:
            self.assertEqual(client.request('/api/routine-ladder?routine=missing')[0], 400)
            state = self.import_run(client)
            identifier = state['routines'][0]['id']
            rung_id = self.get(client, routine=identifier)['items'][0]['id']
            for bad in ({}, {'routine': 'missing'}, {'routine': rung_id}, {'routine': 'x' * 257},
                        {'routine': identifier, 'page': 0}, {'routine': identifier, 'page': -1},
                        {'routine': identifier, 'page': 'not-a-page'}, {'routine': identifier, 'page': 1.5},
                        {'routine': identifier, 'page': 1_000_001}, {'routine': identifier, 'run_id': 'x' * 257}):
                with self.subTest(query=bad):
                    self.assertEqual(client.request('/api/routine-ladder?' + urlencode(bad))[0], 400)
            updated = self.import_run(client, self.changed)
            status, result = client.request('/api/routine-ladder?' + urlencode(
                {'routine': identifier, 'run_id': state['active_run']}))
            self.assertEqual(status, 400)
            self.assertIn('source analysis changed', result['error'])
            current = self.get(client, routine=updated['routines'][0]['id'], run_id=updated['active_run'])
            self.assertEqual(current['run_id'], updated['active_run'])
            self.assertEqual(current['total'], 60)

    def test_cached_qualification_without_report_connection_build_or_analysis(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.import_run(client)
            with (patch('plc_workbench.workspace_classification._qualify_source', wraps=_qualify_source) as qualify,
                  patch('plc_workbench.workspace_report.read_report_data', side_effect=AssertionError('No full report')),
                  patch('plc_workbench.workspace.Workspace._connection_index', side_effect=AssertionError('No connections')),
                  patch('plc_workbench.workspace_map.LadderMapIndex', side_effect=AssertionError('No map index')),
                  patch('plc_workbench.source.analyze_snapshot', side_effect=AssertionError('No analysis rerun'))):
                self.get(client, routine=state['routines'][0]['id'])
                self.get(client, routine=state['routines'][0]['id'], page=2)
                self.get(client, routine=state['routines'][1]['id'])
                self.assertEqual(qualify.call_count, 1)

    def test_existing_english_wording_is_looked_up_only_for_the_visible_page(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.import_run(client)
            service = Mock()
            service.status.return_value = {'presentation_mode': 'english'}
            looked_up = []

            def lookup(texts):
                texts = list(texts)
                looked_up.extend(texts)
                return {text: {'status': 'translated', 'text': f'English: {text}'} for text in texts}

            service.lookup_many.side_effect = lookup
            with patch('plc_workbench.workspace.Workspace._translator', return_value=service):
                page = self.get(client, routine=state['routines'][0]['id'], page=2)
            self.assertEqual(page['presentation_mode'], 'english')
            self.assertEqual(len(looked_up), 20)
            self.assertEqual(looked_up, [row['comment'] for row in page['items']])
            for row in page['items']:
                self.assertEqual(row['wording']['comment']['text'], f"English: {row['comment']}")
                self.assertFalse(row['comment'].startswith('English:'))
            service.start.assert_not_called()
            self.assertEqual(client.get('/api/state')['revision'], state['revision'])


if __name__ == '__main__':
    unittest.main()
