"""Large invented field exports remain complete through save/import and paging."""
from contextlib import closing
from pathlib import Path
import tempfile
import unittest

from plc_workbench.workspace import Workspace
from plc_workbench.workspace_field_io import MAX_INDEX_BYTES as FIELD_LIMIT
from plc_workbench.workspace_field_signals import MAX_INDEX_BYTES as SIGNAL_LIMIT
from test_workspace_field_io import field_inputs, module
from test_workspace_map_api import save_map_inputs


def large_field_inputs():
    leaves = ''.join(f'<DataValueMember Name="Ch{i}Data" DataType="REAL" '
                     'Radix="Float" Value="0.0"/>' for i in range(56))
    comments = '<Comments>' + ''.join(f'<Comment Operand=".Ch{i}Data">'
        f'Invented channel {i} description</Comment>' for i in range(56)) + '</Comments>'
    modules = ''.join(module(f'Card{slot}', slot, 'INVENTED', data=leaves)
        .replace('<InputTag>', '<InputTag>' + comments)
        .replace('<OutputTag>', '<OutputTag>' + comments) for slot in range(1, 101))
    rungs = tuple(f'MOV(Local:{1+i%100}:I.Ch{i%56}Data,Local:{1+i%100}:O.Ch{i%56}Data);'
                  for i in range(4606))
    return field_inputs(rungs, modules=modules)


class FieldCapacityTests(unittest.TestCase):
    def test_saved_large_field_analysis_keeps_every_channel_and_late_page(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = large_field_inputs()
            saved = save_map_inputs(root / 'runs', inputs)
            with closing(Workspace(root / 'review.sqlite', root / 'runs')) as workspace:
                state = workspace.import_run(str(saved), 0)
                before = workspace.store.state()
                query = {'run_id': state['active_run'], 'page_size': 500}
                field = workspace.field_signals(query)
                self.assertTrue(field['available'], field.get('notice'))
                self.assertEqual(field['coverage']['signals_total'], 11201)
                self.assertEqual(field['coverage']['captured_addresses_total'], 11501)
                self.assertEqual(field['signals']['pages'], 23)
                first_ids = {row['id'] for row in field['signals']['items']}
                last = workspace.field_signals(dict(query, page=23))
                self.assertEqual(len(last['signals']['items']), 201)
                self.assertFalse(first_ids & {row['id'] for row in last['signals']['items']})
                found = workspace.field_signals(dict(query, query='Local:100:O.Ch55Data'))
                self.assertEqual(found['signals']['total'], 1)
                row = found['signals']['items'][0]
                self.assertEqual(row['description'], 'Invented channel 55 description')
                self.assertEqual(row['source_metadata']['radix'], 'Float')
                self.assertEqual(row['hardware']['name'], 'Card100')
                self.assertEqual(row['description_selection']['basis'], 'exact_member_comment')
                self.assertEqual(row['description_selection']['candidate_count'], 2)
                detail = workspace.field_signals(dict(query, signal_id=row['id']))['selected_signal']
                self.assertGreater(detail['direct_rungs']['total'], 0)
                self.assertEqual(detail['binding'], row['binding'])
                app = workspace.application(dict(query, query='Local:100:O.Ch55Data'))
                self.assertTrue(app['available'], app.get('notice'))
                self.assertEqual(app['registers']['total'], 1)
                register = workspace.application(dict(query,
                    register_id=app['registers']['items'][0]['id']))['selected_register']
                self.assertEqual(register['datatype'], 'REAL')
                self.assertEqual(register['values'][0]['value'], '0.0')
                self.assertEqual(register['description'], row['description'])
                self.assertEqual(workspace.store.state(), before)
                edited = workspace.mutate({'op': 'signal', 'binding': row['binding'],
                    'target_name': 'DV_SYNTHETIC_OUT', 'field_type': row['field_type']}, before['revision'])
                reviewed = workspace.field_signals(dict(query, query='DV_SYNTHETIC_OUT'))
                self.assertEqual(reviewed['signals']['total'], 1)
                self.assertEqual(reviewed['signals']['items'][0]['saved_signal']['target_name'],
                                 'DV_SYNTHETIC_OUT')
                self.assertEqual(workspace.store.state()['revision'], edited['revision'])
                self.assertLess(workspace._field_io_cache[state['active_run']]._budget, FIELD_LIMIT)
                self.assertLess(workspace._field_signal_cache[1]._budget, SIGNAL_LIMIT)
                self.assertEqual(workspace.store.artifact('snapshot.L5X'), inputs[0].data)


if __name__ == '__main__':
    unittest.main()
