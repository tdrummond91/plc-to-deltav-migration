"""The complete map stays paged, source-bound and read-only on invented exports."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.tag_data import analyze_tag_data
from plc_workbench.pid import analyze_pid
from plc_workbench.pid_members import analyze_pid_members
from plc_workbench.storage import save_run
from plc_workbench.workspace_connections import ConnectionIndex
from plc_workbench.workspace_map import LadderMapIndex
from test_workspace import running_workspace, saved_analysis
from test_workspace_connections import multi_routine, routine
from test_relationships import capture, tag


def save_map_fixture(runs: Path) -> Path:
    texts = ['OTE(Shared);'] + ['XIC(Shared)OTE(Output);'] * 267 + ['XIC(Shared', ';']
    rungs = ''.join(f'<Rung Number="{i}" Type="N"><Text><![CDATA[{text}]]></Text>'
                    '<Comment><![CDATA[' + ('x' * 300 + 'find-beyond-preview' if i == 200 else f'Invented rung {i}')
                    + ']]></Comment></Rung>' for i, text in enumerate(texts))
    programs = ('<Program Name="First"><Tags>' + tag('Shared') + tag('Output') + '</Tags><Routines>'
                '<Routine Name="Main" Type="RLL"><RLLContent>' + rungs + '</RLLContent></Routine>'
                '</Routines></Program><Program Name="Second"><Tags>' + tag('Shared') + tag('Output')
                + '</Tags><Routines>' + routine('Main', 'XIC(Shared)OTE(Output);') + '</Routines></Program>')
    return save_map_inputs(runs, multi_routine(programs))


def save_map_inputs(runs: Path, inputs) -> Path:
    snapshot, inventory, references, access, calculations, rungs, relationships = inputs
    tag_data = analyze_tag_data(snapshot, inventory)
    pid = analyze_pid(snapshot, inventory, references, tag_data)
    members = analyze_pid_members(snapshot, inventory, references, tag_data, pid)
    return save_run(runs, snapshot, inventory, references=references, access=access,
                    calculations=calculations, rung_analysis=rungs, relationships=relationships,
                    tag_data=tag_data, pid=pid, pid_members=members,
                    sfc_structure=analyze_sfc_structure(snapshot, inventory), include_review=True)


class WorkspaceMapApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixture.cleanup)
        cls.runs = Path(cls.fixture.name) / 'runs'
        cls.complete = save_map_fixture(cls.runs)
        cls.without_connections = saved_analysis(cls.runs, controller='NoConnections')
        foreign = ('<Program Name="P"><Routines><Routine Name="R" Type="RLL"><RLLContent>'
                   '<Rung Number="0" Type="N"><Text xmlns="urn:extension">OTE(A);</Text></Rung>'
                   '<Rung Number="1" Type="N"><Text xmlns="urn:extension">XIC(A);</Text></Rung>'
                   '</RLLContent></Routine></Routines></Program>')
        cls.foreign_text = save_map_inputs(cls.runs, multi_routine(foreign, tag('A')))

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name) / 'project.sqlite'

    def import_run(self, client, path=None):
        return client.post('/api/import', {'path': str(path or self.complete),
                                          'expected_revision': client.get('/api/state')['revision']})

    def get(self, client, route='/api/ladder-map', **query):
        return client.get(route + '?' + urlencode(query))

    def test_complete_index_is_paged_and_searches_beyond_preview_without_source_payload(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.import_run(client)
            with patch('plc_workbench.workspace_report.read_report_data', side_effect=AssertionError('No full report')):
                first = self.get(client, run_id=state['active_run'])
                second = self.get(client, page=2)
                match = self.get(client, query='find-beyond-preview')
            self.assertEqual((first['total'], first['pages'], len(first['items'])), (271, 2, 250))
            self.assertEqual(len(second['items']), 21)
            self.assertEqual(len({row['id'] for row in first['items'] + second['items']}), 271)
            self.assertEqual(match['total'], 1)
            self.assertNotIn('find-beyond-preview', match['items'][0]['comment_preview'])
            self.assertEqual(len(match['items'][0]['comment_preview']), 240)
            for row in first['items'] + second['items']:
                self.assertNotIn('text', row)
                self.assertNotIn('structure', row)
                self.assertNotIn('arguments', row)
                self.assertLessEqual(len(row['opcodes']), 12)
            self.assertEqual(self.get(client, family='unparsed')['total'], 1)
            self.assertEqual(self.get(client, family='empty')['total'], 1)
            self.assertEqual(client.get('/api/state')['revision'], state['revision'])

    def test_bus_has_offscreen_counts_and_signal_filter_reaches_all_pages_without_scope_collision(self):
        with running_workspace(self.project, self.runs) as client:
            self.import_run(client)
            first = self.get(client)
            writer, reader = first['items'][:2]
            links = self.get(client, '/api/ladder-map/links', ids=writer['id'] + ',' + reader['id'])
            shared = next(row for row in links['signals'] if row['label'] == 'Shared')
            self.assertEqual(shared['writers'], [writer['id']])
            self.assertEqual(shared['readers'], [reader['id']])
            self.assertEqual(shared['totals']['readers'], 267)
            self.assertEqual(shared['outside_counts']['readers'], 266)
            self.assertNotIn('edges', links)
            filtered = self.get(client, signal_id=shared['id'])
            last = self.get(client, signal_id=shared['id'], page=2)
            self.assertEqual((filtered['total'], len(filtered['items']), len(last['items'])), (268, 250, 18))
            self.assertTrue(all(row['routine_id'] == writer['routine_id'] for row in last['items']))
            self.assertEqual(self.get(client, '/api/ladder-map/links', ids=writer['id'], direction='inputs')['total'], 0)

    def test_existing_connections_and_map_reuse_one_authenticated_index(self):
        with running_workspace(self.project, self.runs) as client:
            self.import_run(client)
            with patch('plc_workbench.workspace_connections.ConnectionIndex', wraps=ConnectionIndex) as constructor:
                first = self.get(client)
                rung = first['items'][0]['id']
                client.get('/api/connections?' + urlencode({'id': rung}))
                self.get(client, '/api/ladder-map/links', ids=rung)
                self.assertEqual(constructor.call_count, 1)

    def test_missing_connections_keep_every_rung_and_import_invalidates_cached_index(self):
        with running_workspace(self.project, self.runs) as client:
            old = self.import_run(client)
            before = self.get(client)
            updated = self.import_run(client, self.without_connections)
            after = self.get(client)
            self.assertTrue(before['connection_available'])
            self.assertFalse(after['connection_available'])
            self.assertEqual(after['total'], 105)
            self.assertNotEqual(after['run_id'], before['run_id'])
            self.assertIn('does not mean', after['connection_notice'])
            links = self.get(client, '/api/ladder-map/links', ids=after['items'][0]['id'])
            self.assertFalse(links['available'])
            self.assertEqual(links['signals'], [])
            self.assertEqual(client.request('/api/ladder-map?' + urlencode({'run_id': old['active_run']}))[0], 400)
            self.assertEqual(client.get('/api/state')['revision'], updated['revision'])

    def test_invalid_selections_are_rejected_even_when_connections_unavailable(self):
        with running_workspace(self.project, self.runs) as client:
            self.import_run(client, self.without_connections)
            first = self.get(client)
            rung = first['items'][0]['id']
            for route, query in (
                ('', {'page': 0}), ('', {'page': 1000001}), ('', {'routine': 'foreign'}),
                ('', {'family': 'not-a-family'}), ('', {'query': 'x' * 501}),
                ('', {'signal_id': 'foreign'}), ('/links', {'ids': 'foreign'}),
                ('/links', {'ids': ','.join(row['id'] for row in first['items'][:81])}),
                ('/links', {'ids': rung + ',' + rung}), ('/links', {'direction': 'runtime'}),
                ('/detail', {'id': 'foreign'}), ('/detail', {'run_id': 'old', 'id': rung}),
            ):
                with self.subTest(route=route, query=query):
                    status, _ = client.request('/api/ladder-map' + route + '?' + urlencode(query))
                    self.assertEqual(status, 400)

    def test_bounded_detail_uses_source_and_saved_block_identification_without_review_changes(self):
        with running_workspace(self.project, self.runs) as client:
            state = self.import_run(client)
            row = self.get(client, query='find-beyond-preview')['items'][0]
            detail = self.get(client, '/api/ladder-map/detail', id=row['id'])
            self.assertIn('find-beyond-preview', detail['description'])
            self.assertEqual([block['opcode'] for block in detail['blocks']], ['XIC', 'OTE'])
            self.assertTrue(detail['source_qualified'])
            self.assertNotIn('arguments', detail['blocks'][0])
            child = self.get(client, '/api/ladder-map/detail', id=detail['blocks'][0]['id'])
            self.assertEqual(child['kind'], 'instruction')
            self.assertEqual(child['links'][0]['id'], row['id'])
            self.assertEqual(client.get('/api/state')['revision'], state['revision'])

    def test_namespace_qualification_agrees_between_overview_filters_and_hover_and_is_cached(self):
        from plc_workbench.workspace_classification import _qualify_source
        with running_workspace(self.project, self.runs) as client:
            self.import_run(client, self.foreign_text)
            with patch('plc_workbench.workspace_classification._qualify_source', wraps=_qualify_source) as qualifier:
                overview = self.get(client)
                unknown = self.get(client, family='unknown')
                boolean = self.get(client, family='boolean_output')
                first = overview['items'][0]
                detail = self.get(client, '/api/ladder-map/detail', id=first['id'])
                instruction = self.get(client, '/api/ladder-map/detail', id=detail['blocks'][0]['id'])
                self.assertEqual(qualifier.call_count, 1)
            self.assertEqual(first['families'], ['unknown'])
            self.assertFalse(first['source_qualified'])
            self.assertEqual(unknown['total'], 2)
            self.assertIn(first['id'], [row['id'] for row in unknown['items']])
            self.assertEqual(boolean['total'], 0)
            self.assertFalse(detail['source_qualified'])
            self.assertEqual(detail['blocks'][0]['family'], 'unknown')
            self.assertFalse(instruction['source_qualified'])
            self.assertEqual(instruction['blocks'][0]['family'], 'unknown')

    def test_foreign_text_cannot_create_directed_or_unknown_signal_edges(self):
        with running_workspace(self.project, self.runs) as client:
            self.import_run(client, self.foreign_text)
            overview = self.get(client)
            self.assertEqual(overview['total'], 2)
            ids = ','.join(row['id'] for row in overview['items'])
            links = self.get(client, '/api/ladder-map/links', ids=ids)
            self.assertTrue(links['available'])
            self.assertEqual(links['signals'], [])
            self.assertEqual(links['coverage']['unqualified_rungs'], 2)
            self.assertEqual(links['coverage']['unqualified_visible_rungs'], 2)
            self.assertEqual(links['coverage']['unqualified_uses'], 2)
            self.assertEqual(links['coverage']['unqualified_visible_uses'], 2)
            self.assertEqual(links['coverage']['rejected_signal_count'], 1)
            self.assertIn('Unsupported XML source associations are omitted', links['notice'])
            self.assertIn('Unsupported XML source associations are omitted', overview['connection_notice'])


class LadderMapDetailTests(unittest.TestCase):
    def test_unqualified_rung_and_alias_are_omitted_from_bus_counts_and_signal_filter(self):
        from plc_workbench.workspace_classification import _qualify_source
        for qualification_gap in ('rung', 'alias'):
            attributes = ' xmlns:x="urn:extension" x:flag="1"' if qualification_gap == 'rung' else ''
            writer = 'BadAlias' if qualification_gap == 'alias' else 'A'
            programs = ('<Program Name="P"><Routines><Routine Name="R" Type="RLL"><RLLContent>'
                        f'<Rung Number="0" Type="N"{attributes}><Text>OTE({writer});</Text></Rung>'
                        '<Rung Number="1" Type="N"><Text>XIC(A);</Text></Rung>'
                        '</RLLContent></Routine></Routines></Program>')
            tags = tag('A')
            if qualification_gap == 'alias':
                tags += '<Tag Name="BadAlias" TagType="Alias" AliasFor="A" xmlns:x="urn:extension" x:flag="1"/>'
            snapshot, inventory, refs, access, calculations, _, relationships = multi_routine(programs, tags)
            index = ConnectionIndex(inventory, refs, access, relationships, calculations)
            entities, rungs, _ = _qualify_source(snapshot.data, asdict(inventory))
            index.qualify_map(entities, rungs)
            ids = [rung.id for rung in inventory.rungs]
            result = index.map_links(ids)
            with self.subTest(gap=qualification_gap):
                self.assertEqual(len(result['signals']), 1)
                signal = result['signals'][0]
                self.assertEqual(signal['writers'], [])
                self.assertEqual(signal['readers'], [ids[1]])
                self.assertEqual(signal['unknown'], [])
                self.assertEqual(signal['totals']['writers'], 0)
                self.assertEqual(signal['outside_counts']['writers'], 0)
                self.assertEqual(index.signal_rungs(signal['id']), frozenset({ids[1]}))
                self.assertEqual(result['coverage']['unqualified_uses'], 1)

    def test_bus_paging_reports_omitted_signals_and_keeps_unknown_roles_separate(self):
        texts = (' '.join(f'MOV(A{i},Output)' for i in range(90)) + ';', 'PID(Output,A0,A1,A2,0,0,0);')
        tags = ''.join(tag(f'A{i}') for i in range(90)) + tag('Output')
        snapshot, inventory, refs, access, calculations, _, relationships = capture(texts, tags=tags)
        index = ConnectionIndex(inventory, refs, access, relationships, calculations)
        from plc_workbench.workspace_classification import _qualify_source
        entities, rungs, _ = _qualify_source(snapshot.data, asdict(inventory))
        index.qualify_map(entities, rungs)
        identifiers = [rung.id for rung in inventory.rungs]
        first = index.map_links(identifiers)
        second = index.map_links(identifiers, page=2)
        self.assertEqual((first['total'], first['pages'], len(first['signals']), len(second['signals'])), (91, 2, 80, 11))
        self.assertEqual((first['omitted_signals'], second['omitted_signals']), (11, 80))
        output = next(row for row in first['signals'] + second['signals'] if row['label'] == 'Output')
        self.assertEqual(output['unknown'], [identifiers[1]])
        self.assertEqual(output['writers'], [identifiers[0]])
        self.assertEqual(output['readers'], [])

    def detail(self, programs: str, extra: str, *, name='Widget'):
        from plc_workbench.workspace_classification import _qualify_source
        inputs = multi_routine(programs, extra=extra)
        inventory = asdict(inputs[1])
        entities, rungs, _ = _qualify_source(inputs[0].data, inventory)
        index = LadderMapIndex(inventory, asdict(inputs[5]), rung_ok=rungs)
        instruction = next(row for row in index.sources.values() if row.get('opcode') == name)
        return index, entities, rungs, index.detail(instruction['id'], entity_ok=entities, rung_ok=rungs)

    def test_aoi_hover_links_only_unique_qualified_declaration_and_preserves_parameters(self):
        programs = '<Program Name="P"><Routines>' + routine('R', 'Widget(A);') + '</Routines></Program>'
        definition = ('<AddOnInstructionDefinition Name="Widget"><Description>Invented helper</Description><Parameters>'
                      '<Parameter Name="Enable" DataType="BOOL" Usage="Input"><Description>Input gate</Description>'
                      '</Parameter></Parameters></AddOnInstructionDefinition>')
        index, entities, rungs, detail = self.detail(programs, '<AddOnInstructionDefinitions>' + definition + '</AddOnInstructionDefinitions>')
        target = next(row for row in detail['links'] if row['kind'] == 'aoi_definition_candidate')
        self.assertIn('not confirmed', detail['limitations'][0])
        declaration = index.detail(target['id'], entity_ok=entities, rung_ok=rungs)
        self.assertEqual(declaration['parameters'][0]['name'], 'Enable')
        self.assertEqual(declaration['parameters'][0]['attributes']['DataType'], 'BOOL')
        _, _, _, ambiguous = self.detail(programs, '<AddOnInstructionDefinitions>' + definition * 2 + '</AddOnInstructionDefinitions>')
        self.assertFalse(any(row['kind'] == 'aoi_definition_candidate' for row in ambiguous['links']))
        foreign = definition.replace('<AddOnInstructionDefinition ', '<AddOnInstructionDefinition xmlns="urn:extension" ')
        _, _, _, unqualified = self.detail(programs, '<AddOnInstructionDefinitions>' + foreign + '</AddOnInstructionDefinitions>')
        self.assertFalse(any(row['kind'] == 'aoi_definition_candidate' for row in unqualified['links']))
        self.assertTrue(any('qualification' in value for value in unqualified['limitations']))

    def test_large_detail_is_bounded_but_reports_remaining_source_items(self):
        programs = '<Program Name="P"><Routines>' + routine('R', 'XIC(A)' * 90 + ';') + '</Routines></Program>'
        inputs = multi_routine(programs, tag('A'))
        inventory = asdict(inputs[1])
        rung = inventory['rungs'][0]
        index = LadderMapIndex(inventory, asdict(inputs[5]), rung_ok={rung['id']: True})
        detail = index.detail(rung['id'], entity_ok={}, rung_ok={rung['id']: True})
        self.assertEqual(detail['block_count'], 90)
        self.assertEqual(len(detail['blocks']), 64)
        self.assertTrue(detail['blocks_truncated'])


if __name__ == '__main__':
    unittest.main()
