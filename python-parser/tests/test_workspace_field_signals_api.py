"""Signal names and cross-rung packages survive real HTTP and project reloads."""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from plc_workbench.project_store import ProjectError, RevisionConflict
from plc_workbench.workspace import Workspace
from test_workspace import running_workspace
from test_workspace_field_io import field_inputs, module
from test_workspace_map_api import save_map_inputs


class WorkspaceFieldSignalAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixtures.cleanup)
        cls.runs = Path(cls.fixtures.name) / 'runs'
        cls.inputs = field_inputs(texts=('MOV(Local:3:I.Ch0Data,InternalReal);',
            'GRT(InternalReal,10)OTE(InternalBool);', 'XIC(InputAlias)OTE(Local:2:O.Data.0);',
            'XIC(Local:1:I.Data.1)OTE(Local:2:O.Data.1);'))
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

    def mutate(self, command: dict) -> dict:
        return self.workspace.mutate(command, self.workspace.store.state()['revision'])

    def rows(self, **query) -> list:
        return self.workspace.field_signals(dict(self.query, **query))['signals']['items']

    def save(self, row: dict, name: str = 'DV_SIGNAL') -> dict:
        state = self.mutate({'op': 'signal', 'binding': row['binding'], 'target_name': name,
            'description': 'Reviewed signal', 'field_type': row['field_type']})
        return next(item for item in state['signals'] if item['target_name'] == name)

    def test_flat_channels_share_cache_and_reads_leave_original_and_project_unchanged(self) -> None:
        before = self.workspace.store.state()
        original = self.workspace.store.artifact('snapshot.L5X')
        first = self.workspace.field_signals(self.query)
        cached = self.workspace._field_signal_cache[1]
        self.assertTrue(first['available'])
        self.assertNotIn('modules', first)
        kinds = {row['field_type'] for row in first['signals']['items']}
        self.assertTrue({'di', 'do', 'ai', 'ao'}.issubset(kinds))
        row = next(row for row in first['signals']['items'] if row['field_type'] == 'di')
        self.assertIn('controller', row['hardware'])
        with patch('plc_workbench.workspace_report.read_report_data', side_effect=AssertionError('No report replay')):
            detail = self.workspace.field_signals(dict(self.query, signal_id=row['id']))
        self.assertIs(cached, self.workspace._field_signal_cache[1])
        self.assertEqual(detail['selected_signal']['binding']['run_id'], self.run_id)
        self.assertEqual(self.workspace.store.state(), before)
        self.assertEqual(self.workspace.store.artifact('snapshot.L5X'), original)

    def test_usage_filter_is_global_and_does_not_change_bindings_or_reviews(self) -> None:
        before = self.workspace.store.state()
        original = self.workspace.store.artifact('snapshot.L5X')
        all_rows = self.workspace.field_signals(dict(self.query, page_size=500))
        counts = all_rows['coverage']['usage_counts']
        self.assertEqual(sum(counts.values()), all_rows['signals']['total'])
        self.assertGreater(counts['referenced'], 0)
        self.assertGreater(counts['not_found'], 0)
        selected_ids = set()
        for status in ('referenced', 'possible_indirect', 'not_found', 'unknown'):
            response = self.workspace.field_signals(dict(self.query, usage=status, page_size=10))
            self.assertEqual(response['signals']['total'], counts[status])
            for page in range(1, response['signals']['pages'] + 1):
                rows = self.workspace.field_signals(dict(self.query, usage=status, page_size=10,
                                                        page=page))['signals']['items']
                self.assertTrue(all(row['usage']['status'] == status for row in rows))
                for row in rows:
                    self.assertNotIn(row['id'], selected_ids)
                    selected_ids.add(row['id'])
                    unfiltered = next(item for item in all_rows['signals']['items'] if item['id'] == row['id'])
                    self.assertEqual(row['binding'], unfiltered['binding'])
        self.assertEqual(selected_ids, {row['id'] for row in all_rows['signals']['items']})
        self.assertEqual(self.workspace.store.state(), before)
        self.assertEqual(self.workspace.store.artifact('snapshot.L5X'), original)

    def test_http_usage_detail_is_independent_from_unresolved_physical_mapping(self) -> None:
        inputs = field_inputs(('MOV(Local:8:I.Ch0Data,InternalReal);',),
                              modules=module('UnmappedCard', 8, 'INVENTED'))
        saved = save_map_inputs(self.runs, inputs)
        state = self.workspace.import_run(str(saved), self.workspace.store.state()['revision'])
        with running_workspace(self.project, self.runs) as client:
            query = {'run_id': state['active_run'], 'usage': 'referenced'}
            response = client.get('/api/field-signals?' + urlencode(query))
            self.assertTrue(response['available'])
            self.assertEqual(response['signals']['total'], 1)
            row = response['signals']['items'][0]
            self.assertEqual(row['mapping_status'], 'review_mapping')
            self.assertEqual(row['field_type'], 'unknown')
            self.assertEqual(row['usage']['direct_count'], 1)
            self.assertEqual(row['usage']['roles']['read'], 1)
            detail = client.get('/api/field-signals?' + urlencode(dict(query, signal_id=row['id'])))['selected_signal']
            self.assertEqual(detail['usage'], row['usage'])
            self.assertEqual(detail['direct_uses']['items'][0]['rung_id'], inputs[1].rungs[0].id)
            self.assertEqual(client.request('/api/field-signals?' + urlencode(dict(query, usage='active')))[0], 400)
            self.assertEqual(client.get('/api/state')['revision'], state['revision'])

    def test_source_occurrences_survive_unknown_roles_and_unrelated_internal_gaps(self) -> None:
        inputs = field_inputs(('XIC(MissingInternal);', 'CTU(Local:1:I.Data,0,0);',
                               'Mystery(Local:3:I.Ch0Data);'))
        saved = save_map_inputs(self.runs, inputs)
        state = self.workspace.import_run(str(saved), self.workspace.store.state()['revision'])
        query = {'run_id': state['active_run'], 'page_size': 500}
        response = self.workspace.field_signals(query)
        self.assertTrue(response['available'])
        scan = response['coverage']['reference_scan']
        self.assertEqual((scan['rungs_total'], scan['rungs_scanned'], scan['rungs_not_scanned']), (3, 3, 0))
        self.assertTrue(scan['complete'])
        self.assertIn('unsupported_instructions', scan['role_gap_reasons'])
        self.assertIn('unresolved_references', scan['role_gap_reasons'])
        rows = {row['address']: row for row in response['signals']['items']}
        used = rows['Local:3:I.Ch0Data']
        self.assertEqual(used['usage']['status'], 'referenced')
        self.assertEqual(used['usage']['roles']['unknown'], 1)
        self.assertEqual(rows['Local:1:I.Data.0']['usage']['status'], 'possible_indirect')
        self.assertEqual(rows['Local:4:O.Ch0Data']['usage']['status'], 'not_found')
        detail = self.workspace.field_signals(dict(query, signal_id=used['id']))['selected_signal']
        self.assertEqual(detail['direct_uses']['items'][0]['opcode'], 'Mystery')
        self.assertEqual(detail['direct_uses']['items'][0]['rung_id'], inputs[1].rungs[2].id)
        self.assertEqual(detail['binding'], used['binding'])
        self.assertEqual(self.workspace.store.state()['revision'], state['revision'])

    def test_resolved_copy_range_filters_and_reopens_saved_names_without_source_changes(self) -> None:
        leaves = ('<ArrayMember Name="Data" DataType="REAL" Dimensions="4">' +
                  ''.join(f'<Element Index="[{i}]" Value="0"/>' for i in range(4)) + '</ArrayMember>')
        inputs = field_inputs(('CPS(Local:8:I.Data[1],Buffer[0],2);',) * 13,
            modules=module('ArrayCard', 8, 'INVENTED', data=leaves),
            extra_tags='<Tag Name="Buffer" DataType="REAL" Dimensions="4"/>')
        run = save_map_inputs(self.runs, inputs)
        state = self.workspace.import_run(str(run), self.workspace.store.state()['revision'])
        self.query = {'run_id': state['active_run']}
        rows = self.rows(usage='referenced')
        self.assertEqual({row['address'] for row in rows}, {'Local:8:I.Data[1]', 'Local:8:I.Data[2]'})
        row = next(row for row in rows if row['address'] == 'Local:8:I.Data[2]')
        self.assertEqual((row['usage']['direct_count'], row['usage']['resolved_count']), (0, 13))
        saved = self.save(row, 'KEEP_RANGE_NAME')
        source = self.workspace.store.artifact('snapshot.L5X')
        before = self.workspace.store.state()
        with closing(Workspace(self.project, self.runs)) as reopened:
            detail = reopened.field_signals(dict(self.query, signal_id=row['id']))['selected_signal']
            self.assertEqual(detail['binding'], row['binding'])
            self.assertEqual(detail['saved_signal']['id'], saved['id'])
            self.assertEqual(detail['saved_signal']['target_name'], 'KEEP_RANGE_NAME')
            self.assertEqual(detail['usage']['resolved_uses'][0]['rung_id'], inputs[1].rungs[0].id)
            self.assertEqual(detail['direct_uses']['total'], 0)
            self.assertEqual(detail['direct_rungs']['total'], 13)
            page2 = reopened.field_signals(dict(self.query, signal_id=row['id'], rung_page=2))['selected_signal']['direct_rungs']
            self.assertEqual(len(page2['items']), 1)
            self.assertEqual(page2['items'][-1]['id'], inputs[1].rungs[12].id)
            self.assertEqual(detail['direct_rungs']['items'][0]['id'], inputs[1].rungs[0].id)
            self.assertEqual(detail['direct_rungs']['items'][0]['association_reason'], 'statically_resolved_address_use')
            self.assertEqual(reopened.store.state(), before)
            self.assertEqual(reopened.store.artifact('snapshot.L5X'), source)

    def test_recovered_earlier_reference_preserves_existing_saved_signal_binding(self) -> None:
        inputs = field_inputs(('Mystery(Local:3:I.CH0DATA);',
                               'MOV(Local:3:I.Ch0Data,InternalReal);'))
        run = save_map_inputs(self.runs, inputs)
        state = self.workspace.import_run(str(run), self.workspace.store.state()['revision'])
        self.query = {'run_id': state['active_run']}
        # Reconstruct the previous workspace projection, which admitted only
        # original-catalog bindings, without rewriting the saved analysis.
        with patch('plc_workbench.workspace_field_io.reference_binding',
                   side_effect=lambda base, ref, access=None: dict(ref)):
            before = next(row for row in self.rows() if row['address'] == 'Local:3:I.Ch0Data')
        saved = self.save(before, 'KEEP_REVIEWED_NAME')
        source = self.workspace.store.artifact('snapshot.L5X')
        with closing(Workspace(self.project, self.runs)) as reopened:
            response = reopened.field_signals(dict(self.query, signal_id=before['id']))
            after = response['selected_signal']
            self.assertEqual(after['binding'], before['binding'])
            self.assertEqual(after['address'], before['address'])
            self.assertEqual(after['usage']['direct_count'], 2)
            self.assertEqual(after['saved_signal']['id'], saved['id'])
            self.assertTrue(after['saved_signal']['active'])
            self.assertFalse(after['saved_signal']['needs_revalidation'])
            revised = reopened.mutate({'op': 'signal', 'id': saved['id'],
                'confirm': True, 'target_name': 'KEEP_REVIEWED_NAME',
                'description': 'Still editable after reference recovery', 'field_type': 'ai'},
                reopened.store.state()['revision'])
            self.assertEqual(revised['signals'][0]['description'], 'Still editable after reference recovery')
            self.assertEqual(reopened.store.artifact('snapshot.L5X'), source)

    def test_partial_scan_reports_absence_with_analysis_scope_and_preserves_exact_positives(self) -> None:
        inputs = field_inputs(('XIC(InputAlias);', 'XIC(Broken'))
        saved = save_map_inputs(self.runs, inputs)
        state = self.workspace.import_run(str(saved), self.workspace.store.state()['revision'])
        query = {'run_id': state['active_run'], 'page_size': 500}
        response = self.workspace.field_signals(query)
        scan = response['coverage']['reference_scan']
        self.assertEqual((scan['rungs_total'], scan['rungs_scanned'], scan['rungs_not_scanned']), (2, 1, 1))
        self.assertFalse(scan['complete'])
        self.assertIn('unparsed_rungs', scan['gap_reasons'])
        rows = {row['address']: row for row in response['signals']['items']}
        self.assertEqual(rows['Local:1:I.Data.0']['usage']['status'], 'referenced')
        self.assertEqual(rows['Local:3:I.Ch0Data']['usage']['status'], 'not_found')
        absent = self.workspace.field_signals(dict(query, usage='not_found'))
        self.assertEqual(absent['coverage']['reference_scan'], scan)
        self.assertTrue(all(row['usage']['status'] == 'not_found' for row in absent['signals']['items']))

    def test_siblings_keep_independent_names_and_package_roles_survive_legacy_edits(self) -> None:
        rows = self.rows(field_type='di', section='signals')
        self.assertEqual(len(rows), 2)
        first, second = self.save(rows[0], 'DV_FIRST'), self.save(rows[1], 'DV_SECOND')
        rungs = self.workspace.store.inventory()['rungs'][:2]
        group = self.mutate({'op': 'group', 'name': 'Tank loop', 'signal_ids': [first['id']],
            'member_ids': [row['id'] for row in rungs],
            'member_roles': {rungs[0]['id']: 'scaling', rungs[1]['id']: 'alarm'}})['groups'][0]
        self.mutate({'op': 'group', 'id': group['id'], 'name': 'Tank package', 'member_ids': group['member_ids']})
        result = self.workspace.field_signals(dict(self.query, query='Tank package', signal_id=rows[0]['id']))
        self.assertEqual(result['signals']['total'], 1)
        self.assertEqual(result['selected_signal']['packages'][0]['member_count'], 2)
        self.assertEqual(self.workspace.store.state()['groups'][0]['member_roles'], group['member_roles'])
        self.assertEqual(self.rows(query='DV_SECOND')[0]['saved_signal']['id'], second['id'])
        self.assertEqual(len(self.rows(query='DV_')), 2)
        with closing(Workspace(self.project, self.runs)) as reopened:
            saved = reopened.store.state()
            self.assertEqual({row['target_name'] for row in saved['signals']}, {'DV_FIRST', 'DV_SECOND'})
            self.assertEqual(saved['groups'][0]['signal_ids'], [first['id']])

    def test_fabricated_channel_and_signature_are_rejected_before_revision_changes(self) -> None:
        row = self.rows(field_type='ai')[0]
        revision = self.workspace.store.state()['revision']
        for key, value in (('evidence_signature', '0' * 64), ('suffix', '.Ch99Data'),
                           ('address_id', 'made-up'), ('root_id', 'made-up'), ('run_id', 'other')):
            binding = dict(row['binding'], **{key: value})
            with self.subTest(key=key), self.assertRaises(ProjectError):
                self.mutate({'op': 'signal', 'binding': binding, 'target_name': 'Invalid'})
        self.assertEqual(self.workspace.store.state()['revision'], revision)

    def test_changed_source_retains_name_and_package_until_explicit_correspondence(self) -> None:
        original = self.rows(field_type='di')[0]
        saved = self.save(original)
        group = self.mutate({'op': 'group', 'name': 'Retained package', 'signal_ids': [saved['id']]})['groups'][0]
        changed = self.workspace.import_run(str(self.later), self.workspace.store.state()['revision'])
        retained = changed['signals'][0]
        self.assertEqual(retained['target_name'], 'DV_SIGNAL')
        self.assertFalse(retained['active'])
        self.assertEqual(changed['groups'][0]['unresolved_signal_ids'], [saved['id']])
        with self.assertRaises(RevisionConflict):
            self.workspace.field_signals(self.query)
        with self.assertRaises(ProjectError):
            self.mutate({'op': 'signal', 'id': saved['id'], 'confirm': True})
        self.query['run_id'] = changed['active_run']
        new = self.rows(field_type='di')[0]
        rebound = self.mutate({'op': 'signal_rebind', 'id': saved['id'], 'binding': new['binding']})
        self.assertEqual(rebound['signals'][0]['id'], saved['id'])
        self.assertEqual(rebound['groups'][0]['signal_ids'], group['signal_ids'])
        self.assertTrue(rebound['signals'][0]['needs_revalidation'])
        confirmed = self.mutate({'op': 'signal', 'id': saved['id'], 'confirm': True})
        self.assertFalse(confirmed['signals'][0]['needs_revalidation'])
        self.assertEqual(len(confirmed['signals'][0]['binding_history']), 1)

    def test_changed_projection_signature_requires_rebind_before_confirmation(self) -> None:
        row = self.rows(field_type='ai')[0]
        saved = self.save(row)
        index = self.workspace._field_signal_cache[1]
        index.signals[row['id']]['binding']['evidence_signature'] = 'f' * 64
        with self.assertRaises(ProjectError):
            self.mutate({'op': 'signal', 'id': saved['id'], 'confirm': True})
        selected = self.workspace.field_signals(dict(self.query, signal_id=row['id']))['selected_signal']
        self.assertTrue(selected['saved_signal']['needs_revalidation'])
        self.mutate({'op': 'signal_rebind', 'id': saved['id'], 'binding': selected['binding']})
        confirmed = self.mutate({'op': 'signal', 'id': saved['id'], 'confirm': True})
        self.assertFalse(confirmed['signals'][0]['needs_revalidation'])

    def test_v1_backup_is_copied_before_migration_and_never_rewritten(self) -> None:
        backup = Path(self.workspace.backup()['path'])
        with closing(sqlite3.connect(backup)) as connection:
            connection.execute('DROP TABLE signals')
            connection.execute('PRAGMA user_version=1')
            connection.commit()
        before = backup.read_bytes()
        restored = self.workspace.restore(backup.name, self.workspace.store.state()['revision'])
        self.assertNotEqual(restored['project_path'], str(backup))
        self.assertEqual(backup.read_bytes(), before)
        self.assertEqual(self.workspace.store.connection.execute('PRAGMA user_version').fetchone()[0], 2)
        self.assertEqual(restored['signals'], [])

    def test_list_does_not_repeat_package_members_or_signal_binding_history(self) -> None:
        row = self.rows(field_type='ai')[0]
        saved = self.save(row)
        self.mutate({'op': 'group', 'name': 'Large retained package', 'signal_ids': [saved['id']]})
        large = deepcopy(self.workspace.store.state())
        large['groups'][0]['member_ids'] = ['rung_' + str(number).zfill(64) for number in range(10_000)]
        large['signals'][0]['binding_history'] = [saved['binding']] * 1000
        with patch.object(self.workspace.store, 'state', return_value=large):
            view = self.workspace.field_signals(dict(self.query, signal_id=row['id']))
        selected = view['selected_signal']
        self.assertNotIn('binding_history', selected['saved_signal'])
        self.assertEqual(selected['saved_signal']['binding_history_count'], 1000)
        self.assertNotIn('member_ids', selected['packages'][0])
        self.assertEqual(selected['packages'][0]['member_count'], 10_000)
        self.assertLess(len(json.dumps(view)), 100_000)

    def test_http_assets_validation_conflicts_and_signal_roundtrip(self) -> None:
        with running_workspace(self.project, self.runs) as client:
            route = '/api/field-signals?' + urlencode(self.query)
            result = client.get(route)
            row = result['signals']['items'][0]
            state = client.mutate({'op': 'signal', 'binding': row['binding'], 'target_name': 'HTTP_SIGNAL'})
            self.assertEqual(client.get(route)['signals']['items'][0]['saved_signal']['target_name'], 'HTTP_SIGNAL')
            stale = {'command': {'op': 'signal', 'id': state['signals'][0]['id'], 'target_name': 'Lost'},
                     'expected_revision': state['revision'] - 1}
            self.assertEqual(client.request('/api/mutate', payload=stale)[0], 409)
            for asset in ('/field-signals.js', '/field-signals.css'):
                self.assertEqual(client.request(asset)[0], 200)
            for bad in ('/api/field-signals', route + '&page=0', route + '&signal_id=foreign'):
                self.assertEqual(client.request(bad)[0], 400)
            self.assertEqual(client.request(route, headers={'Origin': 'https://outside.invalid'})[0], 403)


if __name__ == '__main__':
    unittest.main()
