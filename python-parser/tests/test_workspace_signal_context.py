"""Invented result context and reversible filtering retain source provenance."""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.workspace import Workspace
from plc_workbench.workspace_field_signals import FieldSignalError, FieldSignalIndex, validate_query
from plc_workbench.workspace_signal_context import CONTEXT_REASONS, SignalContextIndex
from test_workspace_field_io import build as field_io, field_inputs, module
from test_workspace_field_signals import build, find, query
from test_workspace_map_api import save_map_inputs
from test_workspace_signal_usage import recapture


STATUS = '<Tag Name="Status" DataType="BOOL"><Description>Invented two-limit permissive</Description></Tag>'
RESULT = '<Tag Name="Result" DataType="REAL"><Description>Invented scaled measurement</Description></Tag>'
BOOLEAN = 'XIC(Local:1:I.Data.1)XIO(Local:1:I.Data.2)OTE(Status);'


def with_rung_comment(inputs, text: str = 'Invented calculated speed'):
    from xml.sax.saxutils import escape
    source = inputs[0].data.replace(b'<Text>', f'<Comment>{escape(text)}</Comment><Text>'.encode(), 1)
    return recapture(source)


class SignalContextTests(unittest.TestCase):
    def test_two_inputs_share_described_boolean_result_without_replacing_source(self) -> None:
        inputs = field_inputs((BOOLEAN,), extra_tags=STATUS)
        index = build(inputs, related=False)
        root = next(entity for entity in inputs[1].entities if entity.name == 'Status')
        for spelling in ('Local:1:I.Data.1', 'Local:1:I.Data.2'):
            row = find(index, spelling)
            self.assertEqual(row['description'], 'Invented DiscreteIn module')
            self.assertEqual(row['description_origin']['kind'], 'module')
            self.assertFalse(row['description_origin']['specific'])
            context = row['use_context']
            self.assertEqual(context['description'], 'Invented two-limit permissive')
            self.assertEqual(context['kind'], 'boolean_result')
            self.assertEqual(context['result_name'], 'Status')
            self.assertEqual(context['result_id'], root.id)
            self.assertEqual(context['description_source_id'], root.id)
            self.assertEqual(context['rung_id'], inputs[1].rungs[0].id)
            self.assertIn('Rung 0', context['path'])
            self.assertIn('not the field signal', context['notice'])
        self.assertEqual(len(index.context._rungs), 1)
        self.assertEqual(index.coverage['use_context_total'], 2)

    def test_calculation_and_expression_reads_use_a_unique_described_result(self) -> None:
        for text in ('ADD(Local:3:I.Ch0Data,2,Result);',
                     'MOV(Local:3:I.Ch0Data,Result);',
                     'CPT(Result,Local:3:I.Ch0Data*2+1);',
                     '[XIC(Local:1:I.Data.1),XIO(Local:1:I.Data.2)]OTE(Status);'):
            with self.subTest(text=text):
                index = build(field_inputs((text,), extra_tags=RESULT + STATUS), related=False)
                row = find(index, 'Local:1:I.Data.1' if text.startswith('[') else 'Local:3:I.Ch0Data')
                self.assertIsNotNone(row['use_context'])
                self.assertEqual(row['use_context']['kind'],
                                 'boolean_result' if text.startswith('[') else 'calculation_result')

    def test_weighted_two_register_calculation_shares_result_context_for_both_inputs(self) -> None:
        data = '<ArrayMember Name="Data" DataType="DINT" Dimensions="8">'
        data += ''.join(f'<Element Index="[{number}]" Value="0"/>' for number in (4, 5))
        data += '</ArrayMember>'
        inputs = field_inputs(('CPT(Result,((Local:8:I.Data[4]*256)+Local:8:I.Data[5])/1000);',),
            modules=module('RegisterCard', 8, 'INVENTED', data=data), extra_tags=RESULT)
        index = build(inputs, related=False)
        rows = [find(index, f'Local:8:I.Data[{number}]') for number in (4, 5)]
        result_id = next(entity.id for entity in inputs[1].entities if entity.name == 'Result')
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        for row in rows:
            self.assertEqual(row['usage']['status'], 'referenced')
            self.assertEqual((row['use_count'], row['rung_count']), (1, 1))
            self.assertEqual(row['description'], 'Invented RegisterCard module')
            self.assertEqual(row['description_origin']['kind'], 'module')
            self.assertEqual(row['use_context']['description'], 'Invented scaled measurement')
            self.assertEqual(row['use_context']['kind'], 'calculation_result')
            self.assertEqual(row['use_context']['result_id'], result_id)
            self.assertEqual(row['use_context']['rung_id'], inputs[1].rungs[0].id)
            self.assertEqual(row['direct_uses']['items'][0]['role'], 'read')
            self.assertEqual(row['direct_uses']['items'][0]['opcode'], 'CPT')
        self.assertEqual(rows[0]['use_context'], rows[1]['use_context'])
        self.assertEqual(index.coverage['use_context_total'], 2)

    def test_multiple_use_multiple_outputs_and_unsupported_effects_do_not_guess_context(self) -> None:
        cases = (
            (BOOLEAN, BOOLEAN),
            (BOOLEAN[:-1] + 'OTE(InternalBool);',),
            ('XIC(Local:1:I.Data.1)OTE(Status)OTE(Status);',),
            ('Mystery(Local:1:I.Data.1)OTE(Status);',),
            ('XIC(Local:1:I.Data.1)ONS(InternalBool)OTE(Status);',),
            ('XIC(Local:1:I.Data.1)OTL(Status);',),
            ('XIC(Local:1:I.Data.1)OTU(Status);',),
            ('XIC(Local:1:I.Data.1)TON(Timer,0,0)OTE(Status);',),
            ('XIC(Missing)XIC(Local:1:I.Data.1)OTE(Status);',),
            ('[XIC(Local:1:I.Data.1),]OTE(Status);',),
        )
        for texts in cases:
            with self.subTest(texts=texts):
                index = build(field_inputs(texts, extra_tags=STATUS + '<Tag Name="Timer" DataType="TIMER"/>'), related=False)
                self.assertIsNone(find(index, 'Local:1:I.Data.1')['use_context'])

    def test_result_readback_and_opaque_expression_are_not_simple_calculation_context(self) -> None:
        for text in ('ADD(Local:3:I.Ch0Data,Result,Result);',
                     'CPT(Result,Result+Local:3:I.Ch0Data);',
                     'CPT(Result,Unsupported(Local:3:I.Ch0Data));'):
            with self.subTest(text=text):
                index = build(field_inputs((text,), extra_tags=RESULT), related=False)
                self.assertIsNone(find(index, 'Local:3:I.Ch0Data')['use_context'])

    def test_unknown_other_use_or_dynamic_possible_use_blocks_single_use_context(self) -> None:
        for extra in ('Mystery(Local:1:I.Data.1);', 'MOV(Local:1:I.Data,InternalReal);',
                      'XIC(Local:1:I.Data.[Index]);'):
            with self.subTest(extra=extra):
                index = build(field_inputs((BOOLEAN, extra), extra_tags=STATUS + '<Tag Name="Index" DataType="DINT"/>'), related=False)
                self.assertIsNone(find(index, 'Local:1:I.Data.1')['use_context'])
        data = '<ArrayMember Name="Data" DataType="REAL" Dimensions="2"><Element Index="[0]" Value="0"/></ArrayMember>'
        inputs = field_inputs(('MOV(Local:8:I.Data[0],Result);', 'MOV(Local:8:I.Data[Index],InternalReal);'),
            modules=module('Array', 8, 'INVENTED', data=data),
            extra_tags=RESULT + '<Tag Name="Index" DataType="DINT"/>')
        index = build(inputs, related=False)
        self.assertTrue(index.usage.scan_summary()['complete'])
        self.assertIsNone(find(index, 'Local:8:I.Data[0]')['use_context'])

    def test_specific_channel_or_alias_description_takes_precedence(self) -> None:
        cards = module('Input', 1, '1756-IB16').replace('<InputTag>', '<InputTag><Comments>'
            '<Comment Operand="Data.1">Invented specific limit</Comment></Comments>')
        inputs = field_inputs(('XIC(InputAlias)XIC(Local:1:I.Data.1)OTE(Status);',), modules=cards, extra_tags=STATUS)
        index = build(inputs, related=False)
        alias = find(index, 'Local:1:I.Data.0')
        channel = find(index, 'Local:1:I.Data.1')
        for row, kind in ((alias, 'alias'), (channel, 'channel')):
            self.assertEqual(row['description_origin']['kind'], kind)
            self.assertTrue(row['description_origin']['specific'])
            self.assertIsNotNone(row['description_origin']['owner_id'])
            self.assertIsNone(row['use_context'])

    def test_result_alias_and_program_scope_preserve_description_owner(self) -> None:
        alias = '<Tag Name="ResultAlias" TagType="Alias" AliasFor="InternalBool"><Description>Invented alias result</Description></Tag>'
        index = build(field_inputs((BOOLEAN.replace('Status', 'ResultAlias'),), extra_tags=alias), related=False)
        context = find(index, 'Local:1:I.Data.1')['use_context']
        self.assertEqual((context['result_name'], context['description']), ('ResultAlias', 'Invented alias result'))
        self.assertEqual(context['result_id'], context['description_source_id'])
        local = STATUS.replace('two-limit permissive', 'local result')
        index = build(field_inputs((BOOLEAN,), extra_tags=STATUS, local_tags=local), related=False)
        self.assertEqual(find(index, 'Local:1:I.Data.1')['use_context']['description'], 'Invented local result')

    def test_conflicting_result_descriptions_and_generic_parent_wording_are_not_context(self) -> None:
        for result in (
            STATUS.replace('</Description>', '</Description><Description>Other wording</Description>'),
            '<Tag Name="Status" DataType="Invented"><Description>Generic parent</Description></Tag>',
        ):
            member = '.State' if 'Invented' in result and 'Generic' in result else ''
            index = build(field_inputs((BOOLEAN.replace('OTE(Status)', f'OTE(Status{member})'),), extra_tags=result), related=False)
            self.assertIsNone(find(index, 'Local:1:I.Data.1')['use_context'])

    def test_unqualified_rungs_cannot_supply_result_context(self) -> None:
        source = field_inputs((BOOLEAN,), extra_tags=STATUS)[0].data
        variants = (source.replace(b'<Rung ', b'<Rung xmlns:x="urn:foreign" x:Unsupported="yes" '),)
        for source in variants:
            with self.subTest(source=source[-80:]):
                index = build(recapture(source), related=False)
                self.assertFalse(index.context._signals)

    def test_unrelated_scan_gaps_keep_qualified_result_context_without_unique_source_claim(self) -> None:
        source = field_inputs((BOOLEAN,), extra_tags=STATUS)[0].data
        variants = (source.replace(b'</RLLContent>', b'</RLLContent><EncodedData>Invented</EncodedData>'),
            source.replace(b'</RLLContent>', b'<Rung Number="1" Type="N"><Text>XIC(Broken</Text></Rung></RLLContent>'))
        for changed in variants:
            with self.subTest(source=changed[-80:]):
                index = build(recapture(changed), related=False)
                context = find(index, 'Local:1:I.Data.1')['use_context']
                self.assertEqual(context['description_kind'], 'result_description')
                self.assertFalse(context['scope_complete'])
                self.assertTrue(context['scope_gap_reasons'])
                self.assertIn('does not establish that the signal has only one use', context['notice'])

    def test_two_register_cpt_uses_qualified_rung_comment_when_result_has_no_description(self) -> None:
        data = '<ArrayMember Name="Data" DataType="DINT" Dimensions="8">'
        data += ''.join(f'<Element Index="[{number}]" Value="0"/>' for number in (4, 5))
        data += '</ArrayMember>'
        inputs = with_rung_comment(field_inputs(
            ('CPT(Result,((Local:8:I.Data[4]*256)+Local:8:I.Data[5])/1000);',),
            modules=module('RegisterCard', 8, 'INVENTED', data=data),
            extra_tags='<Tag Name="Result" DataType="REAL"/>'))
        index = build(inputs, related=False)
        for number in (4, 5):
            row = find(index, f'Local:8:I.Data[{number}]')
            context = row['use_context']
            self.assertEqual(context['description'], 'Invented calculated speed')
            self.assertEqual(context['description_kind'], 'rung_comment')
            self.assertEqual(context['description_basis'], 'rung_comment')
            self.assertEqual(context['description_source_id'], inputs[1].rungs[0].id)
            self.assertEqual(context['description_owner_name'], 'Rung 0')
            self.assertIsNone(context['description_annotation_id'])
            self.assertEqual(index.context.reason(row['id']), 'rung_comment')
            self.assertEqual(index.context.full_description(context['rung_id']), context['description'])
            self.assertEqual(row['description'], 'Invented RegisterCard module')
        self.assertEqual(len(index.context._rungs), 1)
        self.assertEqual(index.view(query(query='calculated speed'))['signals']['total'], 2)

    def test_specific_source_and_result_wording_precede_rung_comment(self) -> None:
        cards = module('Input', 1, '1756-IB16').replace('<InputTag>', '<InputTag><Comments>'
            '<Comment Operand="Data.1">Invented specific limit</Comment></Comments>')
        index = build(with_rung_comment(field_inputs((BOOLEAN,), modules=cards, extra_tags=STATUS)), related=False)
        source = find(index, 'Local:1:I.Data.1')
        self.assertIsNone(source['use_context'])
        self.assertEqual(index.context.reason(source['id']), 'specific_source')
        inherited = find(index, 'Local:1:I.Data.2')['use_context']
        self.assertEqual(inherited['description_kind'], 'result_description')
        self.assertEqual(inherited['description'], 'Invented two-limit permissive')

    def test_conflicting_result_wording_does_not_hide_conflict_behind_rung_comment(self) -> None:
        tags = STATUS.replace('</Description>', '</Description><Description>Other wording</Description>')
        index = build(with_rung_comment(field_inputs((BOOLEAN,), extra_tags=tags)), related=False)
        row = find(index, 'Local:1:I.Data.1')
        self.assertIsNone(row['use_context'])
        self.assertEqual(index.context.reason(row['id']), 'conflicting_wording')

    def test_foreign_duplicate_and_nested_rung_comments_are_not_inherited(self) -> None:
        source = field_inputs((BOOLEAN,), extra_tags='<Tag Name="Status" DataType="BOOL"/>')[0].data
        variants = (
            '<x:Comment xmlns:x="urn:foreign">Invented foreign</x:Comment>',
            '<Comment xmlns:x="urn:foreign" x:Extra="yes">Invented foreign attribute</Comment>',
            '<Comment>First wording</Comment><Comment>Other wording</Comment>',
            '<Comment Protected="true">Invented protected wording</Comment>',
            '<Comment><LocalizedComment Lang="en-US">Invented nested</LocalizedComment></Comment>',
        )
        for annotation in variants:
            with self.subTest(annotation=annotation):
                inputs = recapture(source.replace(b'<Text>', annotation.encode() + b'<Text>', 1))
                index = build(inputs, related=False)
                row = find(index, 'Local:1:I.Data.1')
                self.assertIsNone(row['use_context'])
                self.assertIn(index.context.reason(row['id']), {'unqualified_wording', 'no_wording'})

    def test_comment_context_rejects_multi_outputs_other_uses_and_unresolved_conditions(self) -> None:
        tags = '<Tag Name="Status" DataType="BOOL"/><Tag Name="Index" DataType="DINT"/>'
        variants = ((BOOLEAN, BOOLEAN), (BOOLEAN, 'MOV(Local:1:I.Data,InternalReal);'),
            (BOOLEAN, 'XIC(Local:1:I.Data.[Index]);'),
            (BOOLEAN[:-1] + 'OTE(InternalBool);',),
            ('[XIC(Local:1:I.Data.1)OTE(Status),XIC(Local:1:I.Data.2)OTE(InternalBool)];',),
            ('XIC(Missing)XIC(Local:1:I.Data.1)OTE(Status);',))
        for texts in variants:
            with self.subTest(texts=texts):
                index = build(with_rung_comment(field_inputs(texts, extra_tags=tags)), related=False)
                row = find(index, 'Local:1:I.Data.1')
                self.assertIsNone(row['use_context'])
                self.assertIn(index.context.reason(row['id']), CONTEXT_REASONS)
                self.assertNotEqual(index.context.reason(row['id']), 'rung_comment')

    def test_branched_conditions_and_undescribed_alias_can_inherit_known_rung_comment(self) -> None:
        tags = ('<Tag Name="UndescribedAlias" TagType="Alias" AliasFor="Local:1:I.Data.2"/>'
                '<Tag Name="Status" DataType="BOOL"/>')
        inputs = with_rung_comment(field_inputs(
            ('[XIC(Local:1:I.Data.1),XIO(UndescribedAlias)]OTE(Status);',), extra_tags=tags))
        index = build(inputs, related=False)
        for bit in (1, 2):
            context = find(index, f'Local:1:I.Data.{bit}')['use_context']
            self.assertEqual(context['description_kind'], 'rung_comment')
            self.assertEqual(context['description_source_id'], inputs[1].rungs[0].id)

    def test_rung_context_preserves_full_original_text_and_is_scoped_when_other_rung_unread(self) -> None:
        wording = 'Commentaire francais invente ' * 60 + 'Fin specifique'
        inputs = with_rung_comment(field_inputs((BOOLEAN, 'XIC(Broken'),
            extra_tags='<Tag Name="Status" DataType="BOOL"/>'), wording)
        index = build(inputs, related=False)
        row = find(index, 'Local:1:I.Data.1')
        self.assertTrue(wording.startswith(row['use_context']['description']))
        self.assertFalse(row['use_context']['scope_complete'])
        self.assertIn('unparsed_rungs', row['use_context']['scope_gap_reasons'])
        self.assertEqual(index.context.reason(row['id']), 'rung_comment')
        self.assertEqual(index.context.full_description(inputs[1].rungs[0].id), wording)

    def test_protected_rung_ancestor_cannot_supply_comment_context(self) -> None:
        inputs = with_rung_comment(field_inputs((BOOLEAN,), extra_tags='<Tag Name="Status" DataType="BOOL"/>'))
        for marker in (b'<Rung ', b'<Routine '):
            with self.subTest(marker=marker):
                source = inputs[0].data.replace(marker, marker + b'Protected="1" ', 1)
                index = build(recapture(source), related=False)
                row = find(index, 'Local:1:I.Data.1')
                self.assertIsNone(row['use_context'])
                self.assertEqual(index.context.reason(row['id']), 'unqualified_wording')

    def test_all_context_diagnostics_are_closed_and_do_not_require_detail_expansion(self) -> None:
        index = build(with_rung_comment(field_inputs((BOOLEAN,), extra_tags='<Tag Name="Status" DataType="BOOL"/>')),
                      related=False)
        self.assertEqual(set(index.context.reason(identifier) for identifier in index.signals),
                         {'rung_comment', 'specific_source', 'no_direct_use'})
        with patch('plc_workbench.workspace_signal_context.MAX_CONTEXT_BYTES', 1):
            context = SignalContextIndex(index.field_io, index.usage)
        row = find(index, 'Local:1:I.Data.1')
        self.assertEqual(context.reason(row['id']), 'capacity')
        self.assertEqual(context._rung_reasons, {})
        self.assertEqual(context._uncertain_roots, set())

    def test_other_source_languages_keep_explicitly_rll_scoped_context(self) -> None:
        source = field_inputs((BOOLEAN,), extra_tags=STATUS)[0].data
        chart = b'<Routine Name="Chart" Type="SFC"><SFCContent/></Routine>'
        index = build(recapture(source.replace(b'</Routines>', chart + b'</Routines>')), related=False)
        self.assertEqual(index.usage.scan_summary()['gap_reasons'], ['unsupported_routines'])
        context = find(index, 'Local:1:I.Data.1')['use_context']
        self.assertIsNotNone(context)
        self.assertIn('single matched RLL use rung', context['notice'])
        self.assertIn('Other source languages are outside this lookup', context['notice'])

    def test_recovered_rack_reads_use_same_context_and_canonical_hardware_row(self) -> None:
        from test_rack_backing_context import fixture
        from test_workspace_rack_references import index as rack_index
        field = rack_index(fixture(rungs=('XIC(ProbeAlias)XIO(Remote:3:I.Data.1)OTE(Status);',), tags=STATUS, sfc=''))
        before = deepcopy(field.base._access)
        index = FieldSignalIndex(field)
        for suffix in ('.Data.0', '.Data.1'):
            row = find(index, 'Remote:I.Slot[3]' + suffix)
            self.assertEqual(row['hardware']['name'], 'RackCard')
            self.assertEqual(row['rack_mapping']['logical_suffix'], suffix)
            self.assertEqual(row['use_context']['description'], 'Invented two-limit permissive')
        self.assertEqual(field.base._access, before)
        field = rack_index(fixture(rungs=('CPT(Result,ProbeAlias+1);',), tags=RESULT, sfc=''))
        index = FieldSignalIndex(field)
        context = find(index, 'Remote:I.Slot[3].Data.0')['use_context']
        self.assertEqual(context['description'], 'Invented scaled measurement')
        self.assertEqual(context['kind'], 'calculation_result')

    def test_exact_result_member_comment_keeps_member_and_owner_link(self) -> None:
        tags = '<Tag Name="Status" DataType="Invented"><Description>Generic result structure</Description><Comments>'
        tags += '<Comment Operand=".State">Invented member result</Comment></Comments></Tag>'
        index = build(field_inputs((BOOLEAN.replace('OTE(Status)', 'OTE(Status.State)'),), extra_tags=tags), related=False)
        context = find(index, 'Local:1:I.Data.1')['use_context']
        self.assertEqual(context['description'], 'Invented member result')
        self.assertEqual(context['result_suffix'], '.State')
        self.assertEqual(context['result_name'], 'Status.State')
        self.assertEqual(context['result_id'], context['description_source_id'])

    def test_backing_payload_wording_is_generic_and_search_includes_full_context(self) -> None:
        card = module('Analog', 3, 'INVENTED').replace('<InputTag>',
            '<InputTag><Description>Generic payload wording</Description>')
        index = build(field_inputs((), modules=card), related=False)
        row = find(index, 'Local:3:I.Ch0Data')
        self.assertEqual(row['description_origin']['kind'], 'backing')
        self.assertFalse(row['description_origin']['specific'])
        self.assertNotIn(row['id'], {item['id'] for item in index.view(query(hide_empty=1))['signals']['items']})
        text = 'Invented result context ' * 40 + 'SpecificTail'
        index = build(field_inputs((BOOLEAN,), extra_tags=STATUS.replace('Invented two-limit permissive', text)), related=False)
        result = index.view(query(query='specifictail', hide_empty=1))
        self.assertEqual(result['signals']['total'], 2)
        self.assertEqual(index.view(query(query='status'))['signals']['total'], 2)

    def test_context_reads_are_detached_and_never_change_bindings_or_captured_evidence(self) -> None:
        field = field_io(field_inputs((BOOLEAN,), extra_tags=STATUS))
        before = deepcopy(field.addresses)
        index = FieldSignalIndex(field)
        row = find(index, 'Local:1:I.Data.1')
        binding = deepcopy(row['binding'])
        row['use_context']['description'] = 'Changed'
        row['description_origin']['label'] = 'Changed'
        fresh = find(index, 'Local:1:I.Data.1')
        self.assertEqual(fresh['use_context']['description'], 'Invented two-limit permissive')
        self.assertEqual(fresh['binding'], binding)
        self.assertEqual(field.addresses, before)
        with patch('plc_workbench.workspace_signal_context.MAX_CONTEXT_BYTES', 1):
            bounded = SignalContextIndex(field, index.usage)
        self.assertFalse(bounded.available)
        self.assertEqual((bounded._rungs, bounded._signals, bounded._budget), ({}, {}, 0))

    def test_empty_filter_is_global_reversible_and_preserves_specific_wording_and_saved_rows(self) -> None:
        leaves = ''.join(f'<DataValueMember Name="Ch{i}Data" DataType="REAL" Value="0.0"/>' for i in range(15))
        card = module('Analog', 3, 'INVENTED', data=leaves).replace('<InputTag>', '<InputTag><Comments>'
            '<Comment Operand="Ch2Data">Invented useful annotation</Comment></Comments>')
        index = build(field_inputs(('MOV(Local:3:I.Ch0Data,Result);',), modules=card, extra_tags=RESULT), related=False)
        before = index.view(query(page_size=10))
        empty = find(index, 'Local:3:I.Ch1Data')
        self.assertEqual(empty['description_origin']['kind'], 'module')
        filtered = index.view(query(hide_empty='1', page_size=10), preserve_signal_ids={empty['id']})
        self.assertGreater(filtered['filtering']['hidden_empty_count'], 10)
        self.assertEqual(filtered['filtering']['preserved_empty_count'], 1)
        self.assertEqual(filtered['signals']['total'], 3)
        self.assertEqual(filtered['controller_counts'][0]['total'], 3)
        self.assertEqual({row['address'] for row in filtered['signals']['items']},
                         {'Local:3:I.Ch0Data', 'Local:3:I.Ch2Data', 'Local:3:I.Ch1Data'})
        self.assertEqual(index.view(query(hide_empty=0, page_size=10)), before)
        selected = index.view(query(hide_empty=1, signal_id=empty['id']))
        self.assertEqual(selected['selected_signal']['id'], empty['id'])
        self.assertNotIn(empty['id'], {row['id'] for row in selected['signals']['items']})
        search = index.view(query(hide_empty=1, query='useful annotation'))
        self.assertEqual((search['signals']['total'], search['filtering']['total_before_hide']), (1, 1))

    def test_unknown_usage_and_conflicting_specific_notes_are_never_hidden(self) -> None:
        card = module('Analog', 3, 'INVENTED').replace('<InputTag>', '<InputTag><Comments>'
            '<Comment Operand="Ch0Data">First</Comment><Comment Operand="Ch0Data">Other</Comment></Comments>')
        index = build(field_inputs((), modules=card), related=False)
        row = find(index, 'Local:3:I.Ch0Data')
        self.assertTrue(row['description_origin']['specific'])
        self.assertTrue(row['description_origin']['conflict'])
        self.assertIn(row['id'], {item['id'] for item in index.view(query(hide_empty=1))['signals']['items']})
        index = build(field_inputs(('XIC(Broken',)), related=False)
        self.assertEqual(index.view(query(hide_empty=1))['filtering']['hidden_empty_count'], 0)

    def test_filter_query_rejects_non_boolean_values_and_invalid_preservation(self) -> None:
        for value in (True, False, None, 'true', 'yes', 2, '01', [], {}):
            with self.subTest(value=value), self.assertRaises(FieldSignalError):
                validate_query(query(hide_empty=value))
        index = build(field_inputs(()), related=False)
        for value in ([], {'a': 1}, {1}, {'a' * 257}):
            with self.subTest(value=value), self.assertRaises(FieldSignalError):
                index.view(query(), preserve_signal_ids=value)


class SignalContextAPITests(unittest.TestCase):
    def test_rung_comment_uses_full_cached_translation_and_existing_source_link(self) -> None:
        wording = 'Commentaire de vitesse invente ' * 35 + 'Fin unique'
        inputs = with_rung_comment(field_inputs((BOOLEAN,), extra_tags='<Tag Name="Status" DataType="BOOL"/>'), wording)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = save_map_inputs(root / 'runs', inputs)
            with closing(Workspace(root / 'project.sqlite', root / 'runs')) as workspace:
                run_id = workspace.import_run(str(run), 0)['active_run']
                snapshot = workspace.store.artifact('snapshot.L5X')
                before = workspace.store.state()
                looked_up = []
                class CachedTranslator:
                    def status(self):
                        return {'presentation_mode': 'both'}
                    def lookup_many(self, texts):
                        texts = list(texts)
                        looked_up.extend(texts)
                        return {text: {'state': 'ready', 'text': 'Cached invented speed description',
                                       'original': text} for text in texts}
                with patch.object(workspace, '_translator', return_value=CachedTranslator()):
                    response = workspace.field_signals({'run_id': run_id, 'page_size': 500})
                row = next(row for row in response['signals']['items'] if row.get('use_context'))
                context = row['use_context']
                self.assertEqual(context['description_kind'], 'rung_comment')
                self.assertIsNone(context['description_annotation_id'])
                self.assertIn(wording, looked_up)
                self.assertEqual(context['wording']['text'], 'Cached invented speed description')
                source = workspace.source(context['description_source_id'], run_id)
                self.assertEqual(source['kind'], 'rung')
                self.assertTrue(source['source_qualified'])
                self.assertEqual(source['source']['comment'], wording)
                self.assertEqual(workspace.store.state(), before)
                self.assertEqual(workspace.store.artifact('snapshot.L5X'), snapshot)

    def test_cached_full_result_wording_and_saved_empty_packages_survive_reopen(self) -> None:
        wording = 'Description francaise inventee ' * 40 + 'Fin unique'
        inputs = field_inputs((BOOLEAN,), extra_tags=STATUS.replace('Invented two-limit permissive', wording))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = save_map_inputs(root / 'runs', inputs)
            project = root / 'project.sqlite'
            with closing(Workspace(project, root / 'runs')) as workspace:
                run_id = workspace.import_run(str(run), 0)['active_run']
                request = {'run_id': run_id, 'page_size': 500}
                response = workspace.field_signals(request)
                unused = next(row for row in response['signals']['items'] if row['usage']['status'] == 'not_found'
                              and not row['description_origin']['specific'])
                saved = workspace.mutate({'op': 'signal', 'binding': unused['binding'], 'target_name': 'KEEP_EMPTY'},
                                         workspace.store.state()['revision'])['signals'][0]
                workspace.mutate({'op': 'group', 'name': 'Reviewed package', 'signal_ids': [saved['id']]},
                                 workspace.store.state()['revision'])
                source = workspace.store.artifact('snapshot.L5X')
                before = deepcopy(workspace.store.state())
            with closing(Workspace(project, root / 'runs')) as workspace:
                looked_up = []
                class CachedTranslator:
                    def status(self):
                        return {'presentation_mode': 'both'}
                    def lookup_many(self, texts):
                        texts = list(texts)
                        looked_up.extend(texts)
                        return {text: {'state': 'ready', 'text': 'Cached English context', 'original': text} for text in texts}
                with patch.object(workspace, '_translator', return_value=CachedTranslator()):
                    response = workspace.field_signals(dict(request, hide_empty='1'))
                row = next(row for row in response['signals']['items'] if row['id'] == unused['id'])
                self.assertEqual(row['saved_signal']['target_name'], 'KEEP_EMPTY')
                self.assertEqual(row['packages'][0]['name'], 'Reviewed package')
                self.assertEqual(row['binding'], unused['binding'])
                self.assertEqual(response['filtering']['preserved_empty_count'], 1)
                context_row = next(row for row in response['signals']['items'] if row.get('use_context'))
                self.assertIn(wording, looked_up)
                self.assertEqual(context_row['use_context']['wording']['text'], 'Cached English context')
                self.assertEqual(context_row['description'], 'Invented DiscreteIn module')
                self.assertNotEqual(context_row['use_context']['description'], 'Cached English context')
                self.assertEqual(workspace.store.state(), before)
                self.assertEqual(workspace.store.artifact('snapshot.L5X'), source)


if __name__ == '__main__':
    unittest.main()
