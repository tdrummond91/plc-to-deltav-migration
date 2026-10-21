"""Invented XML proves English inputs are prose, source-bound and complete."""
from copy import deepcopy
import unittest

from plc_workbench.references import analyze_references
from plc_workbench.sfc_conditions import analyze_sfc_conditions
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.source import SourceError, analyze_snapshot, snapshot_from_bytes
from plc_workbench.translation_catalog import collect_annotations


SOURCE = b'''<RSLogix5000Content xmlns:x="urn:unsupported"><Controller Name="NePasTraduire">
<Description>  Controle invente  </Description><DataTypes><DataType Name="T"><Members>
<Member Name="Bit"><Description>Capteur de niveau</Description></Member></Members></DataType></DataTypes>
<Tags><Tag Name="MotMarche" DataType="BOOL"><Description><LocalizedDescription Lang="fr">Pompe arretee</LocalizedDescription>
<LocalizedDescription Lang="en">Pump stopped</LocalizedDescription></Description><Comments><Comment Operand=".0">Bit de retour</Comment></Comments>
<Data><Description>Stored data, not prose</Description><DataValue Value="Do not translate"/></Data></Tag></Tags>
<Programs><Program Name="P"><Routines><Routine Name="L" Type="RLL"><RLLContent>
<Rung Number="0"><Comment>Pompe arretee</Comment><Text>XIC(MotMarche)OTE(Sortie);</Text></Rung></RLLContent></Routine>
<Routine Name="F" Type="FBD"><FBDContent><Sheet><TextBox ID="3"><Text>Pression basse</Text></TextBox></Sheet></FBDContent></Routine>
<Routine Name="S" Type="SFC"><SFCContent><TextBox ID="4"><Text>Attendre le retour</Text></TextBox>
<Transition ID="5"><Condition><STContent><Line Number="0"><![CDATA[MotMarche (* Retour present *)]]></Line></STContent></Condition></Transition>
</SFCContent></Routine></Routines></Program></Programs>
<x:Wrapper><x:Description>Unsupported namespace wording</x:Description></x:Wrapper>
</Controller></RSLogix5000Content>'''


class TranslationCatalogTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = snapshot_from_bytes(SOURCE)
        self.inventory = analyze_snapshot(self.snapshot)
        self.sfc = analyze_sfc_structure(self.snapshot, self.inventory)

    def test_all_known_prose_and_localizations_retain_exact_text_and_occurrence(self):
        inventory = self.inventory.to_dict()
        original = deepcopy(inventory)
        result = collect_annotations(SOURCE, inventory, self.sfc.to_dict())
        texts = [e['original'] for e in result['entries']]
        self.assertEqual(texts.count('Pompe arretee'), 2)
        for text in ['  Controle invente  ', 'Capteur de niveau', 'Pump stopped',
                     'Bit de retour', 'Pression basse', 'Attendre le retour']:
            self.assertIn(text, texts)
        for text in ['Stored data, not prose', 'Do not translate', 'MotMarche',
                     'XIC(MotMarche)OTE(Sortie);', 'Unsupported namespace wording']:
            self.assertNotIn(text, texts)
        self.assertEqual(result['coverage']['unique_texts'], len(set(texts)))
        self.assertEqual(result['coverage']['namespace_exclusions'], 1)
        self.assertEqual(len({e['id'] for e in result['entries']}), len(texts))
        rung = next(e for e in result['entries'] if '/Rung[' in e['locator'])
        self.assertEqual(rung['owner_id'], inventory['rungs'][0]['id'])
        self.assertEqual(inventory, original)
        self.assertEqual(SOURCE, self.snapshot.data)

    def test_validated_condition_comment_spans_only(self):
        conditions = analyze_sfc_conditions(self.snapshot, self.inventory,
                                            analyze_references(self.inventory), self.sfc).to_dict()
        result = collect_annotations(SOURCE, self.inventory.to_dict(), self.sfc.to_dict(), conditions)
        self.assertIn('(* Retour present *)', [e['original'] for e in result['entries']])
        self.assertEqual(result['coverage']['captured_structured_text_comments'], 1)
        conditions['comments'][0]['raw_text'] = 'Not the snapshot comment'
        invalid = collect_annotations(SOURCE, self.inventory.to_dict(), self.sfc.to_dict(), conditions)
        self.assertEqual(invalid['coverage']['captured_structured_text_comments'], 0)

    def test_snapshot_mismatch_and_dtd_reject_without_source_disclosure(self):
        changed = deepcopy(self.inventory.to_dict())
        changed['snapshot']['sha256'] = 'wrong'
        with self.assertRaises(SourceError):
            collect_annotations(SOURCE, changed)
        source = b'<!DOCTYPE RSLogix5000Content><RSLogix5000Content/>'
        snapshot = snapshot_from_bytes(source)
        with self.assertRaises(SourceError):
            collect_annotations(source, {'snapshot': {'id': snapshot.id, 'sha256': snapshot.sha256,
                                                       'size_bytes': snapshot.size_bytes}})


if __name__ == '__main__':
    unittest.main()
