"""Invented module/alias comments retain their exact owner, member and language."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.workspace_classification import _qualify_source
from plc_workbench.workspace_io_comments import IOCommentError, collect_io_annotations


def fixture(body: str):
    source = ('<RSLogix5000Content xmlns:x="urn:foreign"><Controller Name="C">'
              + body + '</Controller></RSLogix5000Content>').encode()
    inventory = analyze_snapshot(snapshot_from_bytes(source))
    qualified = _qualify_source(source, inventory.to_dict())[0]
    return source, inventory, qualified


class WorkspaceIOCommentsTests(unittest.TestCase):
    def test_module_member_and_alias_prose_retain_provenance_and_localizations(self):
        source, inventory, qualified = fixture('''<Modules><Module Name="M">
        <Description>Invented card description</Description><Communications><Connections>
        <Connection Name="Data"><InputTag><Comments>
        <Comment Operand=".Data.0">Retour pompe</Comment>
        <Comment Operand="Ch0Data"><LocalizedComment Lang="fr">Pression</LocalizedComment>
        <LocalizedComment Lang="en">Pressure</LocalizedComment></Comment>
        </Comments><Data><Description>Not prose ownership</Description></Data></InputTag>
        </Connection></Connections></Communications></Module></Modules>
        <Tags><Tag Name="PumpFeedback" TagType="Alias" AliasFor="M:I.Data.0">
        <Description>Invented pump feedback</Description></Tag></Tags>''')
        before = deepcopy(inventory)
        notes = collect_io_annotations(source, inventory, qualified)
        module = next(e for e in inventory.entities if e.kind == 'module')
        root = next(e for e in inventory.entities if e.kind == 'module_input_tag')
        alias = next(e for e in inventory.entities if e.kind == 'tag')
        self.assertEqual(notes[module.id, ''][0]['text'], 'Invented card description')
        self.assertEqual(notes[root.id, '.data.0'][0]['text'], 'Retour pompe')
        self.assertEqual([(row['language'], row['text']) for row in notes[root.id, '.ch0data']],
                         [('fr', 'Pression'), ('en', 'Pressure')])
        self.assertEqual(notes[alias.id, ''][0]['kind'], 'source_description')
        self.assertEqual(inventory, before)
        self.assertEqual(len({row['id'] for rows in notes.values() for row in rows}), 5)

    def test_foreign_or_nested_data_and_dynamic_members_are_not_assigned(self):
        source, inventory, qualified = fixture('''<Tags><Tag Name="T" DataType="DINT">
        <Comments><Comment Operand=".Data[Index]">Dynamic</Comment>
        <Comment Operand=".Data.00">Ambiguous index</Comment>
        <Comment Operand=".Data.0" x:Extra="x">Foreign attribute</Comment>
        <Comment Operand=".Data.1"><x:LocalizedComment Lang="fr">Foreign prose</x:LocalizedComment></Comment>
        <Comment Operand=".Data.2"><Nested>Not a supported note</Nested></Comment>
        <Comment Operand=".Data.3">Valid note</Comment></Comments>
        <Data><Comments><Comment Operand=".Data.4">Not a source annotation</Comment></Comments></Data>
        <Extension><Description>Not a direct description</Description></Extension>
        </Tag></Tags>''')
        notes = collect_io_annotations(source, inventory, qualified)
        self.assertEqual([(key[1], row['text']) for key, values in notes.items() for row in values],
                         [('.data.3', 'Valid note')])

    def test_duplicate_notes_remain_separate_and_never_choose_a_winner(self):
        source, inventory, qualified = fixture('''<Tags><Tag Name="T"><Comments>
        <Comment Operand=".Data.1">First wording</Comment><Comment Operand=".DATA.1">Other wording</Comment>
        </Comments></Tag></Tags>''')
        notes = collect_io_annotations(source, inventory, qualified)
        self.assertEqual([row['text'] for row in next(iter(notes.values()))], ['First wording', 'Other wording'])

    def test_unqualified_owners_wrong_snapshot_and_limits_fail_safely(self):
        source, inventory, qualified = fixture('<Tags><Tag Name="T"><Description>PRIVATE_TEXT</Description></Tag></Tags>')
        self.assertEqual(collect_io_annotations(source, inventory, {}), {})
        with self.assertRaises(IOCommentError):
            collect_io_annotations(source + b' ', inventory, qualified)
        for limit in ('MAX_ANNOTATIONS', 'MAX_ANNOTATION_CHARS'):
            with patch('plc_workbench.workspace_io_comments.' + limit, 0), self.assertRaisesRegex(
                    IOCommentError, '^Saved I/O annotation evidence is inconsistent or exceeds its limits.$'):
                collect_io_annotations(source, inventory, qualified)

    def test_owner_filter_applies_before_budgets_without_bypassing_qualification(self):
        internal = ''.join(f'<Tag Name="Internal{i}"><Comments><Comment Operand=".Value">'
                           + 'Unrelated prose ' * 20 + '</Comment></Comments></Tag>' for i in range(100))
        source, inventory, qualified = fixture('<Tags><Tag Name="Selected"><Description>Field note</Description>'
                                              '</Tag>' + internal + '</Tags>')
        owner = next(row for row in inventory.entities if row.name == 'Selected')
        with patch('plc_workbench.workspace_io_comments.MAX_ANNOTATIONS', 1), \
                patch('plc_workbench.workspace_io_comments.MAX_ANNOTATION_CHARS', len('Field note')):
            notes = collect_io_annotations(source, inventory, qualified, owner_ids={owner.id})
            self.assertEqual(notes[owner.id, ''][0]['text'], 'Field note')
            self.assertEqual(collect_io_annotations(source, inventory, qualified, owner_ids=set()), {})
            self.assertEqual(collect_io_annotations(source, inventory, {}, owner_ids={owner.id}), {})
            with self.assertRaises(IOCommentError):
                collect_io_annotations(source, inventory, qualified)
        with patch('plc_workbench.workspace_io_comments.MAX_ANNOTATION_CHARS', len('Field note') - 1), \
                self.assertRaises(IOCommentError):
            collect_io_annotations(source, inventory, qualified, owner_ids={owner.id})


if __name__ == '__main__':
    unittest.main()
