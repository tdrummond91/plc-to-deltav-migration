"""Selected annotation links verify exact owner/run and preserve full source prose."""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from plc_workbench.project_store import ProjectError
from plc_workbench.workspace import Workspace
from plc_workbench.workspace_field_signals import FieldSignalIndex
from test_workspace import running_workspace
from test_workspace_field_io import build as field_io, field_inputs, module
from test_workspace_field_signals import find
from test_workspace_map_api import save_map_inputs
from test_workspace_signal_context import BOOLEAN, STATUS
from test_workspace_type_descriptions import definition, member, with_types


class SourceAnnotationAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.runs, self.project = root / 'runs', root / 'project.sqlite'
        self.text = 'Invented full member description ' * 30 + 'End of annotation'
        self.inputs = with_types(field_inputs((BOOLEAN,), extra_tags=STATUS),
            definition('InventedModule', member('Ch0Data', description=self.text)))
        self.run = save_map_inputs(self.runs, self.inputs)
        signal = find(FieldSignalIndex(field_io(self.inputs)), 'Local:3:I.Ch0Data')
        self.owner = signal['description_origin']['owner_id']
        self.annotation = signal['description_origin']['annotation_id']
        self.workspace = Workspace(self.project, self.runs)
        self.addCleanup(self.workspace.close)
        self.run_id = self.workspace.import_run(str(self.run), 0)['active_run']

    def test_cold_annotation_request_reads_one_full_member_without_building_field_index(self) -> None:
        before = deepcopy(self.workspace.store.state())
        source = self.workspace.store.artifact('snapshot.L5X')
        self.assertEqual(self.workspace._field_io_cache, {})
        with patch.object(self.workspace, '_field_io_index', side_effect=AssertionError('No full field projection')):
            result = self.workspace.source(self.owner, self.run_id, self.annotation)
        note = result['selected_annotation']
        self.assertEqual(note, {'id': self.annotation, 'owner_id': self.owner,
            'owner_name': 'InventedModule.Ch0Data', 'owner_suffix': '.Ch0Data',
            'text': self.text, 'kind': 'datatype_member_description', 'language': None,
            'locator': note['locator']})
        self.assertTrue(note['locator'].endswith('/Members[1]/Member[1]/Description[1]'))
        self.assertEqual(result['run_id'], self.run_id)
        self.assertFalse(result['historical'])
        self.assertEqual(self.workspace._field_io_cache, {})
        self.assertNotIn('members', result)
        self.assertEqual(self.workspace.store.state(), before)
        self.assertEqual(self.workspace.store.artifact('snapshot.L5X'), source)

    def test_plain_source_request_does_not_load_annotation_or_variable_indexes(self) -> None:
        with patch.object(self.workspace, '_variable_index', side_effect=AssertionError('No requested annotation')):
            result = self.workspace.source(self.owner, self.run_id)
        self.assertNotIn('selected_annotation', result)

    def test_implicit_module_root_owner_name_is_resolved_in_cold_and_cached_source(self) -> None:
        card = module('InputCard', 1, '1756-IB16').replace('<InputTag>',
            '<InputTag><Comments><Comment Operand="Data">Invented word description</Comment></Comments>')
        captured = field_inputs(('XIC(Local:1:I.Data.1);',), modules=card)
        origin = find(FieldSignalIndex(field_io(captured)), 'Local:1:I.Data.1')['description_origin']
        saved = save_map_inputs(self.runs, captured)
        run_id = self.workspace.import_run(str(saved), self.workspace.store.state()['revision'])['active_run']
        for cached in (False, True):
            with self.subTest(cached=cached):
                if cached:
                    self.workspace.field_signals({'run_id': run_id})
                note = self.workspace.source(origin['owner_id'], run_id, origin['annotation_id'])['selected_annotation']
                self.assertEqual(note['owner_name'], 'Local:1:I')
                self.assertEqual(note['owner_suffix'], '.data')
                self.assertEqual(note['text'], 'Invented word description')

    def test_selected_wording_uses_full_original_for_local_translation_cache_lookup(self) -> None:
        translation = {'status': 'translated', 'text': 'Invented English member wording'}
        with patch.object(self.workspace, '_wording', return_value=('english', {self.text: translation})) as lookup:
            result = self.workspace.source(self.owner, self.run_id, self.annotation)
        self.assertEqual(result['presentation_mode'], 'english')
        self.assertEqual(result['selected_annotation']['wording'], translation)
        self.assertEqual(result['selected_annotation']['text'], self.text)
        self.assertEqual(lookup.call_args.args[0][0]['text'], self.text)
        self.assertEqual(lookup.call_args.args[1], 'text')

    def test_cached_field_note_and_internal_result_note_keep_exact_full_original_text(self) -> None:
        response = self.workspace.field_signals({'run_id': self.run_id, 'page_size': 500})
        with patch('plc_workbench.workspace_source_annotations.collect_io_annotations', side_effect=AssertionError('Use cached note')):
            result = self.workspace.source(self.owner, self.run_id, self.annotation)
        self.assertEqual(result['selected_annotation']['text'], self.text)
        context = next(row['use_context'] for row in response['signals']['items'] if row.get('use_context'))
        result = self.workspace.source(context['description_source_id'], self.run_id, context['description_annotation_id'])
        self.assertEqual(result['selected_annotation']['text'], 'Invented two-limit permissive')
        self.assertEqual(result['selected_annotation']['kind'], 'source_description')
        # The plain tag source is still independent from the explicitly selected note.
        self.assertNotIn('selected_annotation', self.workspace.source(context['description_source_id'], self.run_id))

    def test_http_owner_and_annotation_validation_return_fixed_errors_without_mutation(self) -> None:
        other = next(entity.id for entity in self.inputs[1].entities if entity.name == 'InternalBool')
        before = deepcopy(self.workspace.store.state())
        with running_workspace(self.project, self.runs) as client:
            route = '/api/source?' + urlencode({'id': self.owner, 'run_id': self.run_id, 'annotation': self.annotation})
            self.assertEqual(client.get(route)['selected_annotation']['text'], self.text)
            for owner, annotation in ((other, self.annotation), (self.owner, 'io_annotation_' + '0' * 64),
                                      (self.owner, ''), (self.owner, 'unbounded-' * 100)):
                status, error = client.request('/api/source?' + urlencode({'id': owner, 'run_id': self.run_id, 'annotation': annotation}))
                self.assertEqual(status, 400)
                self.assertNotIn(self.text, str(error))
            self.assertEqual(client.request(route + '&annotation=' + self.annotation)[0], 400)
            self.assertEqual(client.request(route + '&annotation=')[0], 400)
            self.assertEqual(client.get('/api/state')['revision'], before['revision'])
        self.assertEqual(self.workspace.store.state(), before)
        with self.assertRaises(ProjectError):
            self.workspace.source(self.owner, self.run_id, '')

    def test_historical_annotation_is_bound_to_selected_run_and_restores_active_source(self) -> None:
        revised = with_types(field_inputs((BOOLEAN,), extra_tags=STATUS),
            definition('InventedModule', member('Ch0Data', description='New annotation')))
        saved = save_map_inputs(self.runs, revised)
        state = self.workspace.import_run(str(saved), self.workspace.store.state()['revision'])
        active = state['active_run']
        before = deepcopy(self.workspace.store.state())
        source = self.workspace.store.artifact('snapshot.L5X')
        with self.assertRaises(ProjectError):
            self.workspace.source(self.owner, active, self.annotation)
        result = self.workspace.source(self.owner, self.run_id, self.annotation)
        self.assertTrue(result['historical'])
        self.assertEqual(result['selected_annotation']['text'], self.text)
        self.assertEqual(self.workspace._run, active)
        self.assertEqual(self.workspace.store.state(), before)
        self.assertEqual(self.workspace.store.artifact('snapshot.L5X'), source)
        with closing(Workspace(self.project, self.runs)) as reopened:
            result = reopened.source(self.owner, self.run_id, self.annotation)
            self.assertTrue(result['historical'])
            self.assertEqual(result['selected_annotation']['text'], self.text)

    def test_selected_annotation_budget_fails_without_truncating_or_changing_source(self) -> None:
        before = deepcopy(self.workspace.store.state())
        with patch('plc_workbench.workspace_source_annotations.MAX_RESPONSE_BYTES', 1), self.assertRaises(ProjectError):
            self.workspace.source(self.owner, self.run_id, self.annotation)
        self.assertEqual(self.workspace.store.state(), before)
        self.assertEqual(self.workspace.source(self.owner, self.run_id, self.annotation)['selected_annotation']['text'], self.text)


if __name__ == '__main__':
    unittest.main()
