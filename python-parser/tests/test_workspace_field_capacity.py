"""Large invented field exports remain complete through save/import and paging."""
from contextlib import closing
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.workspace import Workspace
from plc_workbench.workspace_application import ApplicationCapacityError, ApplicationIndex
from plc_workbench.workspace_application import MAX_INDEX_BYTES as APPLICATION_LIMIT
from plc_workbench.workspace_field_io import FieldIOError, FieldIOIndex
from plc_workbench.workspace_field_io import MAX_INDEX_BYTES as FIELD_LIMIT
from plc_workbench.workspace_field_signals import FieldSignalError, FieldSignalIndex
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


def mixed_field_inputs():
    """Invented size envelope; includes members that are not field wires."""
    channels = ''.join(f'<DataValueMember Name="Ch{i}Data" DataType="REAL" '
                       'Radix="Float" Value="0.0"/>' for i in range(96))
    status = ''.join(f'<DataValueMember Name="Status{i}" DataType="DINT" '
                     'Radix="Decimal" Value="0"/>' for i in range(64))
    config = ''.join(f'<DataValueMember Name="Setting{i}" DataType="DINT" '
                     f'Radix="Decimal" Value="{i}"/>' for i in range(128))
    description = ('Invented module data declaration: contains channel measurements, '
                   'diagnostic status and configuration evidence for this synthetic capacity test.')
    comments = ('<Comments><Comment Operand=".Ch95Data">'
                '<LocalizedComment Lang="fr">Mesure inventee du canal</LocalizedComment>'
                '<LocalizedComment Lang="en">Invented channel measurement</LocalizedComment>'
                '</Comment></Comments>')
    modules = []
    aliases = []
    for slot in range(1, 101):
        card = module(f'MixedCard{slot}', slot, 'INVENTED', data=channels + status)
        for tag in ('InputTag', 'OutputTag'):
            card = card.replace(f'<{tag}>', f'<{tag}><Description>{description}</Description>' + comments)
        card = card.replace('<ConfigTag/>', f'<ConfigTag><Description>{description}</Description>'
            f'<Data Format="Decorated"><Structure DataType="InventedConfig">{config}'
            '</Structure></Data></ConfigTag>')
        modules.append(card)
        aliases.append(f'<Tag Name="ChannelAlias{slot}" TagType="Alias" '
            f'AliasFor="Local:{slot}:I.Ch95Data"><Description>Invented alias wording {slot}</Description></Tag>')
    rungs = tuple(f'MOV(ChannelAlias{1+i%100},Local:{1+i%100}:O.Ch95Data)'
                  f'NEQ(Local:{1+i%100}:I.Status0,0)OTE(InternalBool);' for i in range(600))
    return field_inputs(rungs, modules=''.join(modules), extra_tags=''.join(aliases))


class FieldCapacityTests(unittest.TestCase):
    def test_saved_mixed_export_exceeds_old_caps_and_keeps_config_aliases_and_edits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = mixed_field_inputs()
            saved = save_map_inputs(root / 'runs', inputs)
            with closing(Workspace(root / 'review.sqlite', root / 'runs')) as workspace:
                state = workspace.import_run(str(saved), 0)
                before = workspace.store.state()
                run_id = state['active_run']
                query = {'run_id': run_id, 'page_size': 500}
                field = workspace.field_signals(query)
                self.assertTrue(field['available'], field.get('notice'))
                self.assertEqual(field['coverage']['signals_total'], 19201)
                self.assertEqual(field['coverage']['captured_addresses_total'], 45101)
                self.assertEqual(field['coverage']['excluded_addresses'], 25900)
                self.assertEqual(field['signals']['pages'], 39)
                first_ids = {row['id'] for row in field['signals']['items']}
                last = workspace.field_signals(dict(query, page=39))
                self.assertEqual(len(last['signals']['items']), 201)
                self.assertFalse(first_ids & {row['id'] for row in last['signals']['items']})
                found = workspace.field_signals(dict(query, query='ChannelAlias100'))
                self.assertEqual(found['signals']['total'], 1)
                row = found['signals']['items'][0]
                self.assertEqual(row['address'], 'Local:100:I.Ch95Data')
                self.assertEqual(row['suggested_target_name'], 'ChannelAlias100')
                self.assertEqual(row['description_selection']['candidate_count'], 5)
                self.assertTrue(row['description_selection']['conflict'])
                self.assertEqual({note['language'] for note in row['source_annotations']
                                  if note['kind'] == 'member_comment'}, {'fr', 'en'})
                detail = workspace.field_signals(dict(query, signal_id=row['id']))['selected_signal']
                self.assertEqual(detail['direct_rungs']['total'], 6)
                self.assertEqual(detail['binding'], row['binding'])
                # Status/configuration evidence remains browsable, not promoted
                # to physical wire signals to make a capacity test pass.
                self.assertEqual(workspace.field_signals(dict(query, query='Status63'))['signals']['total'], 0)
                app = workspace.application(dict(query, query='Local:100:C.Setting127'))
                self.assertTrue(app['available'], app.get('notice'))
                self.assertEqual(app['registers']['total'], 1)
                register = workspace.application(dict(query,
                    register_id=app['registers']['items'][0]['id']))['selected_register']
                self.assertEqual(register['values'][0]['value'], '127')
                self.assertEqual(register['io_direction'], 'configuration')
                self.assertEqual(workspace.store.state(), before)
                index = workspace._field_io_cache[run_id]
                self.assertGreater(index._budget, 32 * 1024 * 1024)
                self.assertLess(index._budget, FIELD_LIMIT)
                self.assertGreater(workspace._field_signal_cache[1]._budget, 24 * 1024 * 1024)
                self.assertLess(workspace._field_signal_cache[1]._budget, SIGNAL_LIMIT)
                self.assertGreater(workspace._application_cache[run_id]._budget, 96 * 1024 * 1024)
                self.assertLess(workspace._application_cache[run_id]._budget, APPLICATION_LIMIT)
                # The old policy fails with authenticated, valid evidence;
                # lower guard overrides still fail closed after this change.
                with patch('plc_workbench.workspace_field_io.MAX_INDEX_BYTES', 32 * 1024 * 1024), \
                        self.assertRaises(FieldIOError) as failed:
                    FieldIOIndex(index.base)
                self.assertEqual(failed.exception.diagnostic['reason'], 'index_bytes_limit')
                with patch('plc_workbench.workspace_field_signals.MAX_INDEX_BYTES', 24 * 1024 * 1024), \
                        self.assertRaises(FieldSignalError) as failed:
                    FieldSignalIndex(index)
                self.assertEqual(failed.exception.diagnostic['reason'], 'index_bytes_limit')
                with patch('plc_workbench.workspace_application.MAX_INDEX_BYTES', 96 * 1024 * 1024), \
                        self.assertRaises(ApplicationCapacityError):
                    ApplicationIndex(index)
                workspace.mutate({'op': 'signal', 'binding': row['binding'],
                    'target_name': 'DV_MIXED_IN', 'field_type': row['field_type']}, before['revision'])
                self.assertEqual(workspace.store.artifact('snapshot.L5X'), inputs[0].data)
            with closing(Workspace(root / 'review.sqlite', root / 'runs')) as reopened:
                retained = reopened.field_signals(dict(query, query='DV_MIXED_IN'))
                self.assertTrue(retained['available'], retained.get('notice'))
                self.assertEqual(retained['signals']['total'], 1)
                self.assertEqual(retained['signals']['items'][0]['binding'], row['binding'])
                self.assertEqual(retained['signals']['items'][0]['saved_signal']['target_name'], 'DV_MIXED_IN')

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
