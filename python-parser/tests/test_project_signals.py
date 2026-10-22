"""Revisioned signal decisions remain distinct from immutable source evidence."""
from __future__ import annotations

from contextlib import closing
import hashlib
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.project_store import ProjectError, ProjectStore, RevisionConflict
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.storage import save_run
from test_project_store import attach


def signal_run(folder: Path, *, change: str = '', analysis: bytes | None = None) -> Path:
    source = ('<RSLogix5000Content><Controller Name="Invented"><Modules>'
        '<Module Name="Card" CatalogNumber="1756-IB16" Vendor="1" ParentModule="Local" ParentModPortId="1">'
        '<Ports><Port Id="1" Type="ICP" Address="1" Upstream="true"/></Ports>'
        '<Communications><Connections><Connection Name="Data"><InputTag>'
        '<Data Format="Decorated"><Structure DataType="InventedInput">'
        '<DataValueMember Name="Data" DataType="DINT" Value="0"/>'
        '</Structure></Data></InputTag></Connection></Connections></Communications>'
        '</Module></Modules><Tags><Tag Name="Internal" DataType="DINT"/></Tags>'
        '<Programs><Program Name="Main"><Routines><Routine Name="Logic" Type="RLL"><RLLContent>'
        '<Rung Number="0" Type="N"><Comment>Invented ' + change + '</Comment>'
        '<Text><![CDATA[XIC(Local:1:I.Data.0)OTE(Internal.0);]]></Text></Rung>'
        '</RLLContent></Routine></Routines></Program></Programs></Controller></RSLogix5000Content>').encode()
    snapshot = snapshot_from_bytes(source)
    run = save_run(folder, snapshot, analyze_snapshot(snapshot))
    if analysis is not None:
        attach(run, 'invented-analysis.json', analysis)
    return run


def signal_binding(store: ProjectStore, suffix: str = '.Data.0', *, signature: str = 'a' * 64) -> dict:
    state, inventory = store.state(), store.inventory()
    root = next(row for row in inventory['entities'] if row['kind'] == 'module_input_tag')
    normalized = re.sub(r'\.[A-Za-z_][A-Za-z0-9_]*', lambda match: match.group().lower(), suffix)
    return {'run_id': state['active_run'], 'snapshot_id': inventory['snapshot']['id'],
            'root_id': root['id'], 'suffix': suffix, 'evidence_signature': signature,
            'address_id': 'field_address_' + hashlib.sha256((root['id'] + '\0' + normalized).encode()).hexdigest()}


class ProjectSignalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'project.sqlite'
        self.store = ProjectStore(self.path)
        self.addCleanup(lambda: self.store.close())
        self.first_run = signal_run(self.root / 'runs')
        self.store.import_run(self.first_run)
        self.rung = self.store.inventory()['rungs'][0]['id']

    def change(self, command: dict) -> dict:
        return self.store.mutate(command, self.store.state()['revision'])

    def adopt(self, suffix: str = '.Data.0', **fields) -> dict:
        state = self.change({'op': 'signal', 'binding': signal_binding(self.store, suffix),
                             'target_name': 'PUMP_FEEDBACK', 'description': 'Reviewed engineering wording',
                             'field_type': 'di', **fields})
        return state['signals'][-1]

    def test_signal_edits_are_portable_and_do_not_change_captured_source(self) -> None:
        original = self.store.artifact('snapshot.L5X')
        signal = self.adopt()
        self.assertTrue(signal['id'].startswith('signal-'))
        self.assertTrue(signal['active'])
        self.assertFalse(signal['needs_revalidation'])
        changed = self.change({'op': 'signal', 'id': signal['id'], 'target_name': 'PUMP_RUNNING',
                               'description': 'Revised wording', 'field_type': 'unknown'})
        saved = changed['signals'][0]
        self.assertEqual(saved['binding'], signal['binding'])
        self.assertEqual(saved['field_type'], 'unknown')  # Reviewed metadata is separate from derived classification.
        self.assertEqual(self.store.artifact('snapshot.L5X'), original)
        backup = self.store.backup(self.root / 'backup.sqlite')
        with ProjectStore(backup) as reopened:
            self.assertEqual(reopened.state(), changed)
            self.assertEqual(reopened.artifact('snapshot.L5X'), original)

    def test_empty_target_name_adopts_a_signal_without_inventing_a_name(self) -> None:
        signal = self.adopt(target_name='', description='')
        self.assertEqual(signal['target_name'], '')
        self.assertEqual(signal['description'], '')

    def test_sibling_channels_and_case_variants_have_distinct_correct_identity(self) -> None:
        first = self.adopt()
        second = self.adopt('.Data.1', target_name='SECOND_POINT')
        self.assertNotEqual(first['id'], second['id'])
        self.assertNotEqual(first['binding']['address_id'], second['binding']['address_id'])
        before = self.store.state()
        with self.assertRaisesRegex(ProjectError, 'already has an engineering record'):
            self.adopt('.data.0')
        self.assertEqual(self.store.state(), before)

    def test_packages_keep_signal_ids_and_source_roles_separate_and_many_to_many(self) -> None:
        signal = self.adopt()
        state = self.change({'op': 'group', 'name': 'Pump package', 'member_ids': [self.rung],
                             'signal_ids': [signal['id']], 'member_roles': {self.rung: 'alarm'}})
        group = state['groups'][0]
        self.assertEqual(group['member_ids'], [self.rung])
        self.assertEqual(group['signal_ids'], [signal['id']])
        self.assertEqual(group['unresolved_signal_ids'], [])
        self.change({'op': 'group', 'name': 'Other package', 'member_ids': [], 'signal_ids': [signal['id']]})
        state = self.change({'op': 'group', 'id': group['id'], 'name': 'Renamed package', 'member_ids': [self.rung]})
        kept = next(row for row in state['groups'] if row['id'] == group['id'])
        self.assertEqual(kept['signal_ids'], [signal['id']])
        self.assertEqual(kept['member_roles'], {self.rung: 'alarm'})
        state = self.change({'op': 'group', 'id': group['id'], 'name': 'Renamed package', 'member_ids': []})
        kept = next(row for row in state['groups'] if row['id'] == group['id'])
        self.assertEqual(kept['member_roles'], {})
        self.assertEqual(kept['signal_ids'], [signal['id']])
        self.assertEqual(len(state['signals']), 1)

    def test_import_preserves_names_membership_and_requires_explicit_signal_correspondence(self) -> None:
        old = self.adopt()
        self.change({'op': 'group', 'name': 'Package', 'member_ids': [], 'signal_ids': [old['id']]})
        changed = self.store.import_run(signal_run(self.root / 'runs', change='new source'))
        retained = changed['signals'][0]
        self.assertEqual(retained['target_name'], old['target_name'])
        self.assertFalse(retained['active'])
        self.assertTrue(retained['needs_revalidation'])
        self.assertEqual(changed['groups'][0]['unresolved_signal_ids'], [old['id']])
        with self.assertRaisesRegex(ProjectError, 'Reconnect'):
            self.change({'op': 'signal', 'id': old['id'], 'confirm': True})
        new_binding = signal_binding(self.store)
        rebound = self.change({'op': 'signal_rebind', 'id': old['id'], 'binding': new_binding})
        saved = rebound['signals'][0]
        self.assertEqual(saved['id'], old['id'])
        self.assertEqual(saved['binding'], new_binding)
        self.assertEqual(saved['binding_history'][0]['binding'], old['binding'])
        self.assertEqual(saved['target_name'], old['target_name'])
        self.assertTrue(saved['active'])
        self.assertTrue(saved['needs_revalidation'])
        self.assertEqual(rebound['groups'][0]['signal_ids'], [old['id']])
        self.assertEqual(rebound['groups'][0]['unresolved_signal_ids'], [])
        renamed = self.change({'op': 'signal', 'id': old['id'], 'target_name': 'RENAMED'})
        self.assertTrue(renamed['signals'][0]['needs_revalidation'])
        confirmed = self.change({'op': 'signal', 'id': old['id'], 'confirm': True})
        self.assertFalse(confirmed['signals'][0]['needs_revalidation'])

    def test_same_snapshot_rerun_can_be_confirmed_after_analysis_changes(self) -> None:
        old = self.adopt()
        unchanged = self.store.import_run(signal_run(self.root / 'runs'))
        self.assertTrue(unchanged['signals'][0]['active'])
        self.assertFalse(unchanged['signals'][0]['needs_revalidation'])
        changed = self.store.import_run(signal_run(self.root / 'runs', analysis=b'{"revision":2}'))
        self.assertEqual(changed['signals'][0]['revalidation_reasons'], ['parser_evidence_changed'])
        self.assertEqual(changed['signals'][0]['binding'], old['binding'])
        confirmed = self.change({'op': 'signal', 'id': old['id'], 'confirm': True})
        self.assertFalse(confirmed['signals'][0]['needs_revalidation'])
        self.assertNotEqual(confirmed['signals'][0]['proposal_digest'], old['proposal_digest'])

    def test_new_projection_signature_allows_explicit_same_address_rebind(self) -> None:
        old = self.adopt()
        replacement = dict(old['binding'], evidence_signature='b' * 64)
        rebound = self.change({'op': 'signal_rebind', 'id': old['id'], 'binding': replacement})
        self.assertEqual(rebound['signals'][0]['binding'], replacement)
        self.assertTrue(rebound['signals'][0]['needs_revalidation'])
        before = self.store.state()
        with self.assertRaisesRegex(ProjectError, 'already bound'):
            self.change({'op': 'signal_rebind', 'id': old['id'], 'binding': replacement})
        self.assertEqual(self.store.state(), before)

    def test_rebind_collisions_never_overwrite_another_signal(self) -> None:
        first, second = self.adopt(), self.adopt('.Data.1')
        before = self.store.state()
        with self.assertRaisesRegex(ProjectError, 'already has an engineering record'):
            self.change({'op': 'signal_rebind', 'id': first['id'], 'binding': second['binding']})
        self.assertEqual(self.store.state(), before)

    def test_explicit_source_correspondence_retains_package_member_role(self) -> None:
        signal = self.adopt()
        self.change({'op': 'review', 'source_ids': [self.rung], 'fields': {'meaning': 'Alarm logic'}})
        self.change({'op': 'group', 'name': 'Package', 'member_ids': [self.rung],
                     'signal_ids': [signal['id']], 'member_roles': {self.rung: 'alarm'}})
        self.store.import_run(signal_run(self.root / 'runs', change='changed rung'))
        current = self.store.inventory()['rungs'][0]['id']
        state = self.change({'op': 'rebind', 'from_id': self.rung, 'to_id': current})
        self.assertEqual(state['groups'][0]['member_roles'], {self.rung: 'alarm', current: 'alarm'})
        self.assertEqual(state['groups'][0]['signal_ids'], [signal['id']])

    def test_signal_and_package_edits_undo_without_deleting_saved_evidence(self) -> None:
        old = self.adopt()
        self.change({'op': 'group', 'name': 'Package', 'member_ids': [], 'signal_ids': [old['id']]})
        self.change({'op': 'signal', 'id': old['id'], 'target_name': 'CHANGED'})
        undone = self.change({'op': 'undo'})
        self.assertEqual(undone['signals'][0]['target_name'], old['target_name'])
        self.assertEqual(undone['groups'][0]['signal_ids'], [old['id']])
        self.change({'op': 'undo'})
        undone = self.change({'op': 'undo'})
        self.assertEqual(undone['signals'], [])
        self.assertEqual(undone['groups'], [])
        self.assertTrue(self.store.artifact('snapshot.L5X'))

    def test_rebind_undo_restores_previous_binding_and_history(self) -> None:
        old = self.adopt()
        self.change({'op': 'signal_rebind', 'id': old['id'],
                     'binding': dict(old['binding'], evidence_signature='b' * 64)})
        undone = self.change({'op': 'undo'})
        self.assertEqual(undone['signals'][0], old)

    def test_invalid_bindings_and_metadata_do_not_create_history(self) -> None:
        valid = signal_binding(self.store)
        entity = next(row for row in self.store.inventory()['entities'] if row['kind'] == 'tag')
        variants = [None, {}, dict(valid, extra='not allowed'), dict(valid, snapshot_id='wrong'),
                    dict(valid, run_id='missing'), dict(valid, root_id=entity['id']),
                    dict(valid, suffix='.Data[Other]'), dict(valid, suffix=''),
                    dict(valid, suffix=' .Data.0'), dict(valid, suffix='.Data.1'),
                    dict(valid, address_id='field_address_invented'), dict(valid, evidence_signature=True),
                    dict(valid, evidence_signature='A' * 64)]
        before = self.store.state()
        for binding in variants:
            with self.subTest(binding=binding), self.assertRaises(ProjectError):
                self.change({'op': 'signal', 'binding': binding})
            self.assertEqual(self.store.state(), before)
        for fields in ({'field_type': []}, {'field_type': 'BOOL'}, {'confirm': 1},
                       {'target_name': 'x' * 161}, {'description': 'x' * 4001}, {'extra': 'ignored'}):
            with self.subTest(fields=fields), self.assertRaises(ProjectError):
                self.change({'op': 'signal', 'binding': valid, **fields})
            self.assertEqual(self.store.state(), before)

    def test_group_signal_and_role_forgeries_do_not_write(self) -> None:
        signal = self.adopt()
        before = self.store.state()
        for fields in ({'signal_ids': ['missing']}, {'signal_ids': [signal['id'], signal['id']]},
                       {'member_roles': {'missing': 'alarm'}}, {'member_roles': {self.rung: 'invented'}},
                       {'member_roles': {self.rung: True}}, {'member_roles': []},
                       {'member_ids': [signal['binding']['address_id']]}):
            with self.subTest(fields=fields), self.assertRaises(ProjectError):
                self.change({'op': 'group', 'name': 'Package', 'member_ids': [self.rung], **fields})
            self.assertEqual(self.store.state(), before)

    def test_existing_binding_is_immutable_and_historical_selection_cannot_create_new_record(self) -> None:
        signal = self.adopt()
        with self.assertRaisesRegex(ProjectError, 'explicit signal correspondence'):
            self.change({'op': 'signal', 'id': signal['id'], 'binding': signal['binding'], 'target_name': 'X'})
        self.store.import_run(signal_run(self.root / 'runs', change='later'))
        with self.assertRaisesRegex(ProjectError, 'active source'):
            self.change({'op': 'signal', 'binding': signal['binding']})

    def test_stale_revision_and_bounded_history_fail_atomically(self) -> None:
        stale = self.store.state()['revision']
        signal = self.adopt()
        before = self.store.state()
        with self.assertRaises(RevisionConflict):
            self.store.mutate({'op': 'signal', 'id': signal['id'], 'target_name': 'STALE'}, stale)
        with patch('plc_workbench.project_store.MAX_SIGNAL_BINDINGS', 0), self.assertRaises(ProjectError):
            self.change({'op': 'signal_rebind', 'id': signal['id'],
                         'binding': dict(signal['binding'], evidence_signature='b' * 64)})
        with patch('plc_workbench.project_store.MAX_SIGNALS', 1), self.assertRaises(ProjectError):
            self.adopt('.Data.1')
        self.assertEqual(self.store.state(), before)

    def test_schema_one_upgrade_preserves_every_prior_row_and_old_history_undo(self) -> None:
        self.change({'op': 'review', 'source_ids': [self.rung], 'fields': {'DeltaV name': 'LEGACY'}})
        before = self.store.state()
        self.store.close()
        with closing(sqlite3.connect(self.path)) as database:
            database.execute('DROP TABLE signals')
            database.execute('PRAGMA user_version=1')
            database.commit()
            legacy = {table: database.execute(f'SELECT * FROM {table}').fetchall()
                      for table in ('project', 'runs', 'artifacts', 'history', 'reviews', 'groups', 'rules', 'categories')}
        self.store = ProjectStore(self.path)
        with closing(sqlite3.connect(self.path)) as database:
            self.assertEqual(database.execute('PRAGMA user_version').fetchone()[0], 2)
            for table, rows in legacy.items():
                self.assertEqual(database.execute(f'SELECT * FROM {table}').fetchall(), rows)
        upgraded = self.store.state()
        self.assertEqual(upgraded['revision'], before['revision'])
        self.assertEqual(upgraded['reviews'], before['reviews'])
        self.assertEqual(upgraded['signals'], [])
        self.assertEqual(self.change({'op': 'undo'})['reviews'], {})
        self.assertEqual(self.adopt()['target_name'], 'PUMP_FEEDBACK')


if __name__ == '__main__':
    unittest.main()
