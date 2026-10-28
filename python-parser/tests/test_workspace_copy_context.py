"""Invented byte-copy destinations supply bounded, traceable signal wording."""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.workspace import Workspace
from plc_workbench.workspace_signal_context import CONTEXT_REASONS, SignalContextIndex
from test_workspace_field_io import field_inputs, module
from test_workspace_field_signals import build, find, query
from test_workspace_map_api import save_map_inputs
from test_workspace_signal_context import with_rung_comment
from test_workspace_signal_usage import recapture


RESULT = '<Tag Name="Copied" DataType="REAL"><Description>Invented copied rate</Description></Tag>'


def copy_inputs(texts=('COP(Local:8:I.Data[4],Copied,1);',), *, tags=RESULT,
                dtype='INT', dimensions='8', comments=''):
    data = (f'<ArrayMember Name="Data" DataType="{dtype}" Dimensions="{dimensions}">'
            '<Element Index="[4]" Value="0"/><Element Index="[5]" Value="0"/>'
            '</ArrayMember>')
    card = module('InventedRegisters', 8, 'INVENTED', data=data)
    if comments:
        card = card.replace('<InputTag>', '<InputTag><Comments>' + comments + '</Comments>')
    return field_inputs(texts, modules=card, extra_tags=tags)


class CopyContextTests(unittest.TestCase):
    def test_two_source_words_share_one_cop_or_cps_destination_without_renaming(self) -> None:
        for opcode in ('COP', 'CPS'):
            with self.subTest(opcode=opcode):
                inputs = copy_inputs((f'{opcode}(Local:8:I.Data[4],Copied,1);',))
                index = build(inputs, related=False)
                source_before = deepcopy(index.field_io.base._access.operands)
                rows = [find(index, f'Local:8:I.Data[{number}]') for number in (4, 5)]
                destination = next(entity for entity in inputs[1].entities if entity.name == 'Copied')
                for row in rows:
                    self.assertEqual(row['use_context']['kind'], 'copy_result')
                    self.assertEqual(row['use_context']['description'], 'Invented copied rate')
                    self.assertEqual(row['use_context']['result_name'], 'Copied')
                    self.assertEqual(row['use_context']['description_owner_name'], 'Copied')
                    self.assertEqual(row['use_context']['result_id'], destination.id)
                    self.assertEqual(row['use_context']['description_source_id'], destination.id)
                    self.assertEqual(row['use_context']['rung_id'], inputs[1].rungs[0].id)
                    self.assertEqual(row['use_context']['basis'], 'single_fixed_copy_destination')
                    self.assertIn('copies source bytes', row['use_context']['notice'])
                    self.assertEqual(row['suggested_target_name'], row['address'])
                    self.assertEqual(row['description'], 'Invented InventedRegisters module')
                    self.assertEqual(index.context.reason(row['id']), 'result_description')
                self.assertEqual(rows[0]['use_context'], rows[1]['use_context'])
                self.assertEqual(rows[0]['use_count'], 1)
                self.assertEqual(rows[1]['use_count'], 0)
                self.assertEqual(len(index.context._rungs), 1)
                self.assertEqual(index.coverage['use_context_total'], 2)
                self.assertEqual(index.view(query(query='copied rate'))['signals']['total'], 2)
                self.assertEqual(index.field_io.base._access.operands, source_before)

    def test_equal_width_source_and_single_array_destination_element(self) -> None:
        tags = ('<Tag Name="Copied" DataType="REAL" Dimensions="5">'
                '<Comments><Comment Operand="[2]">Invented third value</Comment>'
                '<Comment Operand="[3]">Different next value</Comment></Comments></Tag>')
        index = build(copy_inputs(('COP(Local:8:I.Data[4],Copied[2],1);',),
                                 tags=tags, dtype='REAL'), related=False)
        context = find(index, 'Local:8:I.Data[4]')['use_context']
        self.assertEqual(context['description'], 'Invented third value')
        self.assertEqual(context['result_name'], 'Copied[2]')
        self.assertEqual(context['result_suffix'], '[2]')
        self.assertIsNone(find(index, 'Local:8:I.Data[5]')['use_context'])

    def test_source_and_destination_aliases_retain_exact_wording_owner(self) -> None:
        tags = (RESULT + '<Tag Name="WordAlias" TagType="Alias" AliasFor="Local:8:I.Data[4]"/>'
                '<Tag Name="CopiedAlias" TagType="Alias" AliasFor="Copied">'
                '<Description>Invented alias result</Description></Tag>')
        # Alias wording and base wording intentionally differ: the selector
        # keeps the exact destination alias as its most-specific owner.
        index = build(copy_inputs(('COP(WordAlias,CopiedAlias,1);',), tags=tags), related=False)
        for number in (4, 5):
            context = find(index, f'Local:8:I.Data[{number}]')['use_context']
            self.assertEqual(context['description'], 'Invented alias result')
            self.assertEqual(context['result_name'], 'CopiedAlias')
            self.assertEqual(context['description_owner_name'], 'CopiedAlias')
            self.assertEqual(context['description_source_id'], context['result_id'])

    def test_specific_source_wording_precedes_copy_context_on_each_covered_word(self) -> None:
        comments = '<Comment Operand="Data[5]">Invented source second word</Comment>'
        tags = RESULT + ('<Tag Name="WordAlias" TagType="Alias" AliasFor="Local:8:I.Data[4]">'
                         '<Description>Invented source first word</Description></Tag>')
        index = build(copy_inputs(tags=tags, comments=comments), related=False)
        for number, wording in ((4, 'Invented source first word'), (5, 'Invented source second word')):
            row = find(index, f'Local:8:I.Data[{number}]')
            self.assertEqual(row['description'], wording)
            self.assertIsNone(row['use_context'])
            self.assertEqual(index.context.reason(row['id']), 'specific_source')

    def test_enable_contact_does_not_inherit_destination_description(self) -> None:
        # The condition is a different field address in the same rung.
        index = build(copy_inputs(('NEQ(Local:8:I.Data[5],0)COP(Local:8:I.Data[0],Copied,1);',)), related=False)
        self.assertIsNone(find(index, 'Local:8:I.Data[5]')['use_context'])
        self.assertEqual(find(index, 'Local:8:I.Data[0]')['use_context']['result_name'], 'Copied')

    def test_zero_dynamic_multiple_destination_and_partial_word_lengths_do_not_guess(self) -> None:
        array = ('<Tag Name="Copied" DataType="REAL" Dimensions="5"><Comments>'
                 '<Comment Operand="[0]">First only</Comment>'
                 '<Comment Operand="[1]">Second only</Comment></Comments></Tag>')
        cases = (
            ('COP(Local:8:I.Data[4],Copied,0);', RESULT, 'INT'),
            ('COP(Local:8:I.Data[4],Copied,Length);', RESULT + '<Tag Name="Length" DataType="DINT"/>', 'INT'),
            ('COP(Local:8:I.Data[4],Copied[0],2);', array, 'INT'),
            ('COP(Local:8:I.Data[4],Copied,1);', RESULT.replace('REAL', 'INT'), 'DINT'),
        )
        for text, tags, dtype in cases:
            with self.subTest(text=text, dtype=dtype):
                index = build(copy_inputs((text,), tags=tags, dtype=dtype), related=False)
                for number in (4, 5):
                    row = find(index, f'Local:8:I.Data[{number}]')
                    self.assertIsNone(row['use_context'])
                    self.assertIn(index.context.reason(row['id']), CONTEXT_REASONS)

    def test_unknown_layout_and_source_or_destination_overrun_do_not_guess(self) -> None:
        cases = (
            copy_inputs(dtype='Unknown'),
            copy_inputs(dimensions='5'),
            copy_inputs(('COP(Local:8:I.Data[4],Copied[2],1);',),
                        tags=RESULT.replace('DataType="REAL"', 'DataType="REAL" Dimensions="2"')),
        )
        for inputs in cases:
            with self.subTest(source=inputs[0].data[-120:]):
                index = build(inputs, related=False)
                self.assertIsNone(find(index, 'Local:8:I.Data[4]')['use_context'])

    def test_overlapping_copy_is_rejected_even_with_described_destination_alias(self) -> None:
        for target in ('Local:8:I.Data[4]', 'Local:8:I.Data[4].0'):
            tags = (f'<Tag Name="Copied" TagType="Alias" AliasFor="{target}">'
                    '<Description>Invented overlap</Description></Tag>')
            index = build(copy_inputs(tags=tags), related=False)
            self.assertIsNone(find(index, 'Local:8:I.Data[4]')['use_context'])

    def test_other_uses_block_single_destination_attribution_for_covered_source_word(self) -> None:
        variants = (
            'MOV(Local:8:I.Data[5],InternalReal);',
            'COP(Local:8:I.Data[5],Other,1);',
            'MOV(Local:8:I.Data[Index],InternalReal);',
            'Mystery(Local:8:I.Data[5]);',
        )
        tags = RESULT + '<Tag Name="Other" DataType="REAL"/><Tag Name="Index" DataType="DINT"/>'
        for extra in variants:
            with self.subTest(extra=extra):
                index = build(copy_inputs(('COP(Local:8:I.Data[4],Copied,1);', extra), tags=tags), related=False)
                self.assertIsNone(find(index, 'Local:8:I.Data[5]')['use_context'])
        index = build(copy_inputs(('XIC(Local:8:I.Data[4].0)COP(Local:8:I.Data[4],Copied,1);',)), related=False)
        self.assertIsNone(find(index, 'Local:8:I.Data[4]')['use_context'])

    def test_conflicting_destination_wording_does_not_fall_back_to_rung_comment(self) -> None:
        tags = RESULT.replace('</Description>', '</Description><Description>Other definition</Description>')
        index = build(with_rung_comment(copy_inputs(tags=tags)), related=False)
        for number in (4, 5):
            row = find(index, f'Local:8:I.Data[{number}]')
            self.assertIsNone(row['use_context'])
            self.assertEqual(index.context.reason(row['id']), 'conflicting_wording')

    def test_qualified_rung_comment_is_fallback_for_both_source_words(self) -> None:
        index = build(with_rung_comment(copy_inputs(tags='<Tag Name="Copied" DataType="REAL"/>')),
                      related=False)
        for number in (4, 5):
            context = find(index, f'Local:8:I.Data[{number}]')['use_context']
            self.assertEqual(context['description_kind'], 'rung_comment')
            self.assertEqual(context['kind'], 'copy_result')
            self.assertEqual(context['description_owner_name'], 'Rung 0')

    def test_no_array_expansion_and_capacity_failure_clears_copy_metadata(self) -> None:
        index = build(copy_inputs(dimensions='100000000'), related=False)
        self.assertLess(len(index.signals), 20)
        self.assertEqual(len(index.context._copies), 1)
        with patch('plc_workbench.workspace_signal_context.MAX_CONTEXT_BYTES', 1):
            context = SignalContextIndex(index.field_io, index.usage)
        self.assertFalse(context.available)
        self.assertEqual(context._copies, {})
        self.assertEqual(context._signals, {})
        self.assertEqual(context._rungs, {})

    def test_unqualified_rung_does_not_supply_copy_context(self) -> None:
        source = copy_inputs()[0].data.replace(b'<Rung ', b'<Rung xmlns:x="urn:foreign" x:Extra="1" ')
        index = build(recapture(source), related=False)
        self.assertFalse(index.context._signals)


class CopyContextAPITests(unittest.TestCase):
    def test_saved_run_supplies_full_cached_translation_links_and_retains_decisions(self) -> None:
        wording = 'Description francaise inventee ' * 50 + 'Derniere phrase'
        inputs = copy_inputs(tags=RESULT.replace('Invented copied rate', wording))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = save_map_inputs(root / 'runs', inputs)
            with closing(Workspace(root / 'project.sqlite', root / 'runs')) as workspace:
                run_id = workspace.import_run(str(run), 0)['active_run']
                initial = workspace.field_signals({'run_id': run_id, 'page_size': 500})
                row = next(row for row in initial['signals']['items'] if row['address'] == 'Local:8:I.Data[5]')
                # Preserve a reviewer-selected name while displaying derived wording.
                workspace.mutate({'op': 'signal', 'binding': row['binding'], 'target_name': 'REVIEWED_WORD'},
                                 workspace.store.state()['revision'])
                before = workspace.store.state()
                snapshot = workspace.store.artifact('snapshot.L5X')
                looked_up = []
                class CachedTranslator:
                    def status(self):
                        return {'presentation_mode': 'both'}
                    def lookup_many(self, texts):
                        texts = list(texts)
                        looked_up.extend(texts)
                        return {text: {'state': 'ready', 'text': 'Cached invented copy description',
                                       'original': text} for text in texts}
                with patch.object(workspace, '_translator', return_value=CachedTranslator()):
                    response = workspace.field_signals({'run_id': run_id, 'page_size': 500})
                rows = [row for row in response['signals']['items'] if row.get('use_context')]
                self.assertEqual(len(rows), 2)
                self.assertIn(wording, looked_up)
                for row in rows:
                    context = row['use_context']
                    self.assertEqual(context['wording']['text'], 'Cached invented copy description')
                    self.assertEqual(context['description_kind'], 'result_description')
                    source = workspace.source(context['description_source_id'], run_id,
                                              context['description_annotation_id'])
                    self.assertEqual(source['kind'], 'tag')
                    self.assertEqual(source['source']['description'], wording)
                    self.assertTrue(workspace.source(context['rung_id'], run_id)['source_qualified'])
                self.assertEqual(workspace.store.state(), before)
                self.assertEqual(workspace.store.artifact('snapshot.L5X'), snapshot)


if __name__ == '__main__':
    unittest.main()
