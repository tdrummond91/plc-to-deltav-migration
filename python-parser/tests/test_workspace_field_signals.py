"""Invented channel identities and optional related logic remain evidence bounded."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from plc_workbench.workspace_field_signals import FieldSignalError, FieldSignalIndex, validate_query
from test_workspace_connections import build as connections
from test_workspace_field_io import build as field_io, field_inputs, module


def build(inputs=None, *, related: bool = True) -> FieldSignalIndex:
    captured = inputs or field_inputs()
    return FieldSignalIndex(field_io(captured), connections(captured) if related else None)


def query(**kwargs) -> dict:
    return {'run_id': 'invented-run', **kwargs}


def find(index: FieldSignalIndex, address: str) -> dict:
    return next(row for row in index.signals.values() if row['address'].casefold() == address.casefold())


class WorkspaceFieldSignalTests(unittest.TestCase):
    def test_documented_channel_rows_exclude_aggregates_faults_configuration_and_echo(self) -> None:
        index = build()
        view = index.view(query(section='signals'))
        self.assertEqual({row['address']: row['field_type'] for row in view['signals']['items']}, {
            'Local:1:I.Data.0': 'di', 'Local:2:O.Data.0': 'do',
            'Local:3:I.Ch0Data': 'ai', 'Local:4:O.Ch0Data': 'ao'})
        self.assertEqual(view['coverage']['documented_by_field_type'], dict.fromkeys(('di', 'do', 'ai', 'ao'), 1))
        all_rows = list(index.signals.values())
        self.assertFalse(any(row['direction'] == 'configuration' or row['suffix'] in {'', '.Data', '.Fault.0'}
                             for row in all_rows))
        self.assertFalse(any(row['address'].startswith('Local:2:I.') for row in all_rows))
        self.assertFalse(any(row['address'].startswith('Local:4:I.') for row in all_rows))
        self.assertFalse(view['coverage']['capacity_expansion'])
        self.assertEqual(find(index, 'Local:1:I.Data.0')['hardware']['slot'], '1')

    def test_aliases_and_case_spelling_deduplicate_to_one_member_not_whole_root(self) -> None:
        aliases = ('<Tag Name="SecondAlias" TagType="Alias" AliasFor="InputAlias"/>'
                   '<Tag Name="ThirdAlias" TagType="Alias" AliasFor="Local:1:I.data.0"/>')
        captured = field_inputs(('XIC(InputAlias)XIC(SecondAlias)XIC(ThirdAlias);',
                                 'XIC(Local:1:I.Data.1);'), extra_tags=aliases)
        index = build(captured)
        row = find(index, 'Local:1:I.Data.0')
        self.assertEqual({alias['name'] for alias in row['aliases']}, {'InputAlias', 'SecondAlias', 'ThirdAlias'})
        self.assertEqual((row['use_count'], row['rung_count']), (3, 1))
        self.assertNotEqual(row['id'], find(index, 'Local:1:I.Data.1')['id'])
        self.assertEqual(row['root_id'], find(index, 'Local:1:I.Data.1')['root_id'])
        detail = index.view(query(signal_id=row['id']))['selected_signal']
        self.assertEqual(detail['direct_rungs']['total'], 1)
        self.assertEqual(detail['direct_uses']['total'], 3)
        self.assertEqual(detail['grouping_scope'], 'exact_module_member')
        self.assertFalse(detail['automatic_membership'])
        self.assertNotIn('group_member_ids', detail)

    def test_hart_and_mixed_captured_members_are_candidates_without_invented_channels(self) -> None:
        cards = module('Hart', 1, '1756-IF8IH') + module('Combo', 2, '1756-IF4FXOF2F')
        captured = field_inputs(('MOV(Local:1:I.Ch0Data,InternalReal);',), modules=cards)
        index = build(captured)
        view = index.view(query(field_type='ai'))
        self.assertEqual(view['signals']['total'], 3)  # HART Ch0/Data.0 alias + combo input Ch0.
        self.assertTrue(all(row['mapping_status'] == 'review_mapping' for row in view['signals']['items']))
        self.assertTrue(all(row['field_type'] == 'unknown' and row['channel'] is None for row in view['signals']['items']))
        self.assertEqual(index.view(query(field_type='ao'))['signals']['total'], 1)
        self.assertFalse(any(row['address'].startswith('Local:1:O.') for row in index.signals.values()))
        self.assertEqual(index.view(query(section='signals'))['signals']['total'], 0)
        self.assertEqual(index.coverage['documented_total'], 0)
        self.assertEqual(index.coverage['candidates_by_field_type']['ai'], 3)

    def test_unknown_catalogs_remain_unknown_and_controller_network_members_are_excluded(self) -> None:
        cards = module('Unknown', 1, 'UNKNOWN') + module('Network', 2, '1756-EN2T') + module('CPU', 3, '1756-L81E')
        index = build(field_inputs(('XIC(InputAlias);',), modules=cards))
        self.assertTrue(index.signals)
        for row in index.signals.values():
            self.assertEqual(row['hardware']['name'], 'Unknown')
            expected = ['ai'] if row['suffix'] == '.Ch0Data' and row['direction'] == 'input' else (
                ['ao'] if row['suffix'] == '.Ch0Data' and row['direction'] == 'output' else [])
            self.assertEqual(row['candidate_field_types'], expected)
            self.assertIsNone(row['channel'])
            self.assertEqual(row['field_type'], 'unknown')
        self.assertEqual(index.view(query(field_type='ai'))['signals']['total'], 1)

    def test_alias_name_and_channel_metadata_are_unsaved_source_proposals(self) -> None:
        data = '<DataValueMember Name="Ch2Data" DataType="REAL" Radix="Float" Value="1.5"/>'
        card = module('Unknown', 1, 'UNKNOWN', data=data).replace('<InputTag>', '<InputTag ExternalAccess="Read/Write">')
        alias = ('<Tag Name="LevelInput" TagType="Alias" AliasFor="Local:1:I.Ch2Data" '
                 'ExternalAccess="Read Only"><Description>Invented level input</Description></Tag>')
        index = build(field_inputs(('MOV(LevelInput,InternalReal);',), modules=card, extra_tags=alias))
        row = find(index, 'Local:1:I.Ch2Data')
        self.assertEqual(row['suggested_target_name'], 'LevelInput')
        self.assertEqual(row['target_name_basis'], 'alias')
        self.assertEqual(row['suggested_field_type'], 'ai')
        self.assertEqual(row['mapping_reason'], 'qualified_floating_channel_requires_review')
        self.assertEqual(row['mapping_status'], 'review_mapping')
        self.assertEqual(row['field_type'], 'unknown')
        metadata = row['source_metadata']
        self.assertEqual(metadata['tag_type'], 'Alias')
        self.assertEqual(metadata['alias_for'], 'Local:1:I.Ch2Data')
        self.assertEqual(metadata['data_type'], 'REAL')
        self.assertEqual(metadata['radix'], 'Float')
        self.assertEqual(metadata['external_access'], 'Read Only')
        output = find(index, 'Local:1:O.Ch2Data')
        self.assertEqual(output['suggested_target_name'], output['address'])
        self.assertEqual(output['target_name_basis'], 'base_address')
        self.assertEqual(output['suggested_field_type'], 'ao')

    def test_floating_channel_hint_rejects_conflicts_status_and_ambiguous_values(self) -> None:
        leaf = '<DataValueMember Name="Ch0Data" DataType="REAL" Radix="Float" Value="1.5"/>'
        for data in (leaf.replace('REAL', 'DINT'), leaf.replace('Float', 'Hex'), leaf + leaf,
                     leaf.replace('Ch0Data', 'Status'), leaf.replace('Ch0Data', 'Fault')):
            with self.subTest(data=data):
                index = build(field_inputs((), modules=module('Unknown', 1, 'UNKNOWN', data=data)), related=False)
                self.assertFalse(any(row['suggested_field_type'] in {'ai', 'ao'} for row in index.signals.values()))
        card = module('Unknown', 1, 'UNKNOWN', data=leaf).replace('</InputTag>',
            '<Data Format="Decorated"><Structure DataType="OtherProfile"/></Data></InputTag>')
        index = build(field_inputs((), modules=card), related=False)
        self.assertEqual(find(index, 'Local:1:I.Ch0Data')['suggested_field_type'], 'unknown')

    def test_selected_page_sizes_cover_controller_rows_and_detail_rungs(self) -> None:
        notes = ''.join(f'<Comment Operand="Ch{i}Data">Point {i}</Comment>' for i in range(51))
        card = module('Hart', 1, '1756-IF8IH').replace('<InputTag>', '<InputTag><Comments>' + notes + '</Comments>')
        index = build(field_inputs(('MOV(Local:1:I.Ch0Data,InternalReal);',) * 23, modules=card))
        first = index.view(query(field_type='ai', page_size='10'))
        count = first['signals']['total']
        pages = [index.view(query(field_type='ai', page_size=10, page=page))['signals']['items']
                 for page in range(1, first['signals']['pages'] + 1)]
        self.assertEqual(len({row['id'] for page in pages for row in page}), count)
        self.assertEqual(first['controller_counts'][0]['total'], count)
        self.assertEqual(first['controller_counts'][0]['controller_name'], 'C')
        self.assertEqual(len(index.view(query(field_type='ai', page_size=500))['signals']['items']), count)
        row = find(index, 'Local:1:I.Ch0Data')
        detail = index.view(query(signal_id=row['id'], detail_page_size=10, rung_page=3))['selected_signal']
        self.assertEqual((detail['direct_rungs']['page_size'], len(detail['direct_rungs']['items'])), (10, 3))
        self.assertEqual(index.view(query(signal_id=row['id'], detail_page_size=50))['selected_signal']['direct_uses']['total'], 23)

    def test_saved_binding_is_exact_detached_and_independent_of_presentation(self) -> None:
        index = build()
        row = find(index, 'Local:3:I.Ch0Data')
        anchor = index.anchor(row['id'])
        self.assertEqual(set(anchor), {'snapshot_id', 'root_id', 'suffix', 'address_id', 'evidence_signature'})
        self.assertRegex(anchor['evidence_signature'], r'^[0-9a-f]{64}$')
        self.assertEqual(anchor['address_id'], row['id'])
        view = index.view(query(signal_id=row['id']))
        view['selected_signal']['binding']['suffix'] = '.Changed'
        view['selected_signal']['hardware']['controller']['name'] = 'Changed'
        anchor['suffix'] = '.Changed'
        self.assertEqual(index.anchor(row['id'])['suffix'], '.Ch0Data')
        self.assertEqual(row['hardware']['controller']['name'], 'C')

    def test_paging_filtering_and_full_annotation_search_do_not_lose_rows(self) -> None:
        notes = ''.join(f'<Comment Operand="Ch{i}Data">Point {i}</Comment>' for i in range(31))
        notes += '<Comment Operand="Ch30Data">' + 'Long prose ' * 70 + 'TailNeedle</Comment>'
        card = module('Hart', 1, '1756-IF8IH').replace('<InputTag>', '<InputTag><Comments>' + notes + '</Comments>')
        index = build(field_inputs((), modules=card), related=False)
        first = index.view(query(field_type='ai'))['signals']
        second = index.view(query(field_type='ai', page=2))['signals']
        self.assertEqual((len(first['items']), first['total'], first['pages']), (24, 32, 2))
        self.assertEqual(len(second['items']), 8)
        self.assertEqual(len({row['id'] for row in first['items'] + second['items']}), 32)
        found = index.view(query(query='tailneedle'))['signals']['items']
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['address'].lower(), 'local:1:i.ch30data')
        self.assertNotIn('TailNeedle', ' '.join(note['text'] for note in found[0]['source_annotations']))
        self.assertEqual(index.view(query(page=999))['signals']['page'], 2)

    def test_direct_cpt_and_one_hop_related_candidates_keep_reasons_and_do_not_recurse(self) -> None:
        captured = field_inputs((
            'CPT(InternalReal,Local:3:I.Ch0Data*2);',
            'GRT(InternalReal,90)OTE(InternalBool);',
            'XIC(InternalBool)OTE(Deep);',
            'ADD(InternalReal,1,Other);',
        ), extra_tags='<Tag Name="Deep" DataType="BOOL"/><Tag Name="Other" DataType="REAL"/>')
        index = build(captured)
        row = find(index, 'Local:3:I.Ch0Data')
        detail = index.view(query(signal_id=row['id']))['selected_signal']
        self.assertEqual(detail['direct_uses']['items'][0]['opcode'], 'CPT')
        self.assertEqual(detail['direct_rungs']['items'][0]['candidate_role'], 'scaling')
        related = detail['related_rungs']
        self.assertEqual({rung['id'] for rung in related['items']}, {captured[1].rungs[i].id for i in (1, 3)})
        self.assertNotIn(captured[1].rungs[2].id, {rung['id'] for rung in related['items']})
        compare = next(rung for rung in related['items'] if rung['id'] == captured[1].rungs[1].id)
        self.assertEqual(compare['candidate_role'], 'logic')  # Comparison + coil does not prove an alarm.
        self.assertEqual(compare['associations'][0]['address'], 'InternalReal')
        self.assertEqual(compare['associations'][0]['from_roles'], ['writers'])
        self.assertEqual(compare['associations'][0]['related_roles'], ['readers'])
        self.assertEqual(compare['association_reason'], 'shared_address_with_direct_use_rung')
        self.assertFalse(related['traversal']['truncated'])

    def test_relation_qualification_blocks_foreign_sources_and_never_joins_scoped_names(self) -> None:
        from test_workspace_connections import multi_routine
        from test_workspace_variables import program
        tags = '<Tag Name="InternalReal" DataType="REAL"/>'
        programs = program('One', ('XIC(LocalFlag)MOV(Local:1:I.Ch0Data,InternalReal);',),
                           '<Tag Name="LocalFlag" DataType="BOOL"/>')
        programs += program('Two', ('XIC(LocalFlag)OTE(Other);',),
                            '<Tag Name="LocalFlag" DataType="BOOL"/><Tag Name="Other" DataType="BOOL"/>')
        programs += program('Foreign', ('MOV(InternalReal,Elsewhere);',)).replace(
            '<Rung ', '<Rung xmlns:x="urn:foreign" x:Unsupported="yes" ')
        local = ('<Module Name="Local" ParentModule="Local" ParentModPortId="1"><Ports>'
                 '<Port Id="1" Type="ICP" Address="0" Upstream="false"/></Ports></Module>')
        captured = multi_routine(programs, tags, '<Modules>' + local + module('Input', 1, '1756-IF8') + '</Modules>')
        index = build(captured)
        row = find(index, 'Local:1:I.Ch0Data')
        detail = index.view(query(signal_id=row['id']))['selected_signal']
        self.assertEqual(detail['related_rungs']['total'], 0)

    def test_common_global_signal_and_direct_expansion_limits_report_incompleteness(self) -> None:
        texts = ('MOV(Local:3:I.Ch0Data,InternalReal);',) + ('GRT(InternalReal,1);',) * 70
        index = build(field_inputs(texts))
        row = find(index, 'Local:3:I.Ch0Data')
        related = index.view(query(signal_id=row['id']))['selected_signal']['related_rungs']
        self.assertEqual(related['total'], 0)
        self.assertTrue(related['traversal']['truncated'])
        self.assertEqual(related['traversal']['high_fanout_bridges_skipped'], 1)
        self.assertTrue(related['total_is_lower_bound'])
        many = build(field_inputs(('MOV(Local:3:I.Ch0Data,InternalReal);',) * 35))
        row = find(many, 'Local:3:I.Ch0Data')
        detail = many.view(query(signal_id=row['id']))['selected_signal']
        self.assertEqual(detail['direct_rungs']['total'], 35)
        self.assertEqual(len(detail['direct_rungs']['items']), 12)
        self.assertEqual(detail['related_rungs']['traversal']['direct_rungs_examined'], 32)
        self.assertTrue(detail['related_rungs']['traversal']['truncated'])

    def test_missing_connections_keeps_direct_evidence_and_never_reanalyzes_on_view(self) -> None:
        index = build(related=False)
        row = find(index, 'Local:3:I.Ch0Data')
        with patch('plc_workbench.source.analyze_snapshot', side_effect=AssertionError('analysis rerun')):
            detail = index.view(query(signal_id=row['id']))['selected_signal']
        self.assertEqual(detail['direct_uses']['total'], 2)
        self.assertFalse(detail['related_rungs']['available'])
        self.assertEqual(detail['related_rungs']['total'], 0)

    def test_saved_name_description_and_package_search_is_request_local_and_keeps_filters(self) -> None:
        index = build()
        di = find(index, 'Local:1:I.Data.0')
        ai = find(index, 'Local:3:I.Ch0Data')
        saved = {di['id']: 'DV_SWITCH Unit_Package One description', ai['id']: 'DV_PRESSURE Unit_Package Two'}
        self.assertEqual(index.view(query(query='dv_switch'), extra_search=saved)['signals']['total'], 1)
        self.assertEqual(index.view(query(query='unit_package'), extra_search=saved)['signals']['total'], 2)
        self.assertEqual(index.view(query(query='unit_package', field_type='ai'), extra_search=saved)['signals']['total'], 1)
        self.assertEqual(index.view(query(query='local:3:i'), extra_search=saved)['signals']['total'], 1)
        self.assertEqual(index.view(query(query='dv_switch'))['signals']['total'], 0)
        self.assertEqual(index.view(query(query='unit_package'), extra_search={})['signals']['total'], 0)
        self.assertEqual(saved[di['id']], 'DV_SWITCH Unit_Package One description')
        for invalid in ([], {di['id']: []}, {di['id']: 'X' * 32769}):
            with self.subTest(invalid_type=type(invalid)), self.assertRaises(FieldSignalError):
                index.view(query(), extra_search=invalid)

    def test_direct_uses_and_related_pages_follow_source_order_without_duplicate_rung_loss(self) -> None:
        texts = ('CPT(InternalReal,Local:3:I.Ch0Data*2);', 'MOV(Local:3:I.Ch0Data,Other);')
        texts += tuple(f'GRT(InternalReal,{number})OTE(InternalBool);' for number in range(25))
        captured = field_inputs(texts, extra_tags='<Tag Name="Other" DataType="REAL"/>')
        index = build(captured)
        signal_id = find(index, 'Local:3:I.Ch0Data')['id']
        detail = index.view(query(signal_id=signal_id))['selected_signal']
        self.assertEqual([row['opcode'] for row in detail['direct_uses']['items']], ['CPT', 'MOV'])
        pages = [index.view(query(signal_id=signal_id, related_page=number))['selected_signal']['related_rungs']
                 for number in (1, 2, 3)]
        self.assertEqual([len(page['items']) for page in pages], [12, 12, 1])
        self.assertEqual([row['id'] for page in pages for row in page['items']],
                         [rung.id for rung in captured[1].rungs[2:]])
        self.assertTrue(all(page['total'] == 25 and not page['total_is_lower_bound'] for page in pages))

    def test_query_identity_budget_and_connection_snapshot_rejections_are_fixed(self) -> None:
        for values in ({'run_id': ''}, {'field_type': 'status'}, {'section': 'all-data'}, {'page': True},
                       {'use_page': '0'}, {'related_page': '1000000'}, {'query': '\n'}, {'signal_id': []}):
            with self.subTest(values=values), self.assertRaises(FieldSignalError):
                validate_query(query(**values))
        index = build()
        for values in ({'signal_id': 'missing'}, {'module_id': 'missing'}):
            with self.subTest(values=values), self.assertRaises(FieldSignalError):
                index.view(query(**values))
        with self.assertRaises(FieldSignalError):
            FieldSignalIndex(field_io(), connections(field_inputs(('XIC(InternalBool);',))))
        with patch('plc_workbench.workspace_field_signals.MAX_INDEX_BYTES', 1), self.assertRaises(FieldSignalError):
            build(related=False)
        with patch('plc_workbench.workspace_field_signals.MAX_RESPONSE_BYTES', 1), self.assertRaises(FieldSignalError):
            index.view(query())


if __name__ == '__main__':
    unittest.main()
