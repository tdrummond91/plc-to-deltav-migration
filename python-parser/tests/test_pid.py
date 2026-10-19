"""Invented PID source evidence, without runtime or numeric interpretation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.pid import (
    SLOT_NAMES, PidError, analyze_pid, render_pid_json, validate_pid,
)
from plc_workbench.references import analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.tag_data import analyze_tag_data


PID_STRUCTURE = ('<Structure DataType="PID"><DataValueMember Name="SP" DataType="REAL" '
                 'Value="001.50"/><DataValueMember Name="KP" DataType="REAL" Value="-0"/>'
                 '</Structure>')
DECORATED = f'<Data Format="Decorated">{PID_STRUCTURE}</Data>'


def tag(data: str = DECORATED, name: str = 'Loop', datatype: str = 'PID', attrs: str = '') -> str:
    return f'<Tag Name="{name}" TagType="Base" DataType="{datatype}"{attrs}>{data}</Tag>'


def call(root: str = 'Loop', opcode: str = 'PID') -> str:
    return f'{opcode}({root},PV,0,CV,0,0,0)'


def capture(text: str = '', tags: str = '', namespace: str = ''):
    xml = (f'<RSLogix5000Content{namespace}><Controller Name="Invented"><Tags>{tags}</Tags>'
           '<Programs><Program Name="P"><Routines><Routine Name="R" Type="RLL"><RLLContent>'
           f'<Rung Number="0" Type="N"><Text><![CDATA[{text}]]></Text></Rung>'
           '</RLLContent></Routine></Routines></Program></Programs></Controller></RSLogix5000Content>')
    return capture_xml(xml)


def capture_xml(xml: str):
    snapshot = snapshot_from_bytes(xml.encode())
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    tag_data = analyze_tag_data(snapshot, inventory)
    result = analyze_pid(snapshot, inventory, references, tag_data)
    return snapshot, inventory, references, tag_data, result


class PidTests(unittest.TestCase):
    def test_ascii_casing_occurrences_and_seven_slot_source_links(self) -> None:
        inputs = capture(call() + call(opcode='pid') + 'XIC(PV);', tag() + tag('', 'PV', 'REAL'))
        snapshot, inventory, references, tag_data, result = inputs
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.coverage['occurrences_total'], 2)
        self.assertEqual(result.coverage['source_instructions'], 3)
        self.assertEqual(result.coverage['source_operands'], 15)
        self.assertEqual(result.coverage['distinct_backing_owners'], 1)
        self.assertEqual([row['slot'] for row in result.operands], list(SLOT_NAMES) * 2)
        by_reference = {row['id']: row for row in references.operands}
        for operand in result.operands:
            original = by_reference[operand['id']]
            self.assertEqual(operand['binding_status'], original['status'])
            self.assertEqual(operand['argument_index'], original['argument_index'])
            self.assertNotIn('raw_text', operand)
        for index, occurrence in enumerate(result.occurrences):
            self.assertEqual(occurrence['id'], inventory.rungs[0].instructions[index].id)
            self.assertEqual(occurrence['rung_id'], inventory.rungs[0].id)
            self.assertEqual(occurrence['storage_status'], 'linked')
            self.assertEqual(len(occurrence['structure_candidates'][0]['member_ids']), 2)
        validate_pid(*inputs)
        self.assertEqual(json.loads(render_pid_json(result)), result.to_dict())
        self.assertEqual(result.to_dict(), analyze_pid(snapshot, inventory, references, tag_data).to_dict())

    def test_malformed_signatures_keep_occurrences_but_all_slots_unknown(self) -> None:
        text = 'PID(Loop,PV)PID(Loop,PV,,CV,0,0,0)PID();'
        *_, result = capture(text, tag())
        self.assertEqual(result.coverage['occurrences_total'], 3)
        self.assertEqual(result.coverage['occurrences_by_signature'], {
            'argument_count_mismatch': 2, 'empty_argument': 1, 'recognized': 0})
        self.assertEqual({row['slot'] for row in result.operands}, {'unknown'})
        for occurrence in result.occurrences:
            self.assertEqual(occurrence['storage_status'], 'signature_unresolved')
            self.assertIsNone(occurrence['backing_owner_id'])
            self.assertEqual(occurrence['structure_candidates'], [])
        self.assertEqual(result.status, 'partial')

    def test_non_pid_and_unicode_lookalikes_do_not_promote_occurrences(self) -> None:
        *_, empty = capture('XIC(Loop);', tag())
        self.assertEqual(empty.coverage['occurrences_total'], 0)
        self.assertEqual(empty.status, 'complete')
        *_, unicode = capture(call(opcode='P\u0131D') + ';', tag())
        self.assertEqual(unicode.coverage['occurrences_total'], 0)
        self.assertNotIn('linked', [row['storage_status'] for row in unicode.occurrences])

    def test_root_aliases_share_owner_but_expanded_suffixes_stay_gaps(self) -> None:
        aliases = ('<Tag Name="Alias" TagType="Alias" AliasFor="Loop"/>'
                   '<Tag Name="Member" TagType="Alias" AliasFor="Loop.SP"/>')
        inputs = capture(call('Alias') + call('Member') + call('Loop[0]') + ';', tag() + aliases)
        result = inputs[-1]
        self.assertEqual([row['storage_status'] for row in result.occurrences],
                         ['linked', 'suffix_not_empty', 'suffix_not_empty'])
        self.assertEqual(result.coverage['distinct_backing_owners'], 1)
        self.assertEqual(len({row['backing_owner_id'] for row in result.occurrences}), 1)
        for occurrence in result.occurrences:
            self.assertEqual(occurrence['content_ids'], [inputs[-2].contents[0]['id']])
        self.assertEqual(result.occurrences[1]['structure_candidates'], [])

    def test_unbound_first_slot_keeps_binding_status_and_no_storage_claim(self) -> None:
        *_, result = capture(call('Missing') + call('0') + ';')
        self.assertEqual([row['storage_status'] for row in result.occurrences],
                         ['first_operand_unbound'] * 2)
        self.assertEqual(result.operands[0]['binding_status'], 'unresolved')
        self.assertEqual(result.operands[7]['binding_status'], 'literal')
        self.assertEqual(result.coverage['distinct_backing_owners'], 0)

    def test_declared_type_and_every_dimensions_spelling_are_conservative_gaps(self) -> None:
        for datatype in ('REAL', 'PID ', '\u03a1ID', ''):
            with self.subTest(datatype=datatype):
                *_, result = capture(call() + ';', tag(datatype=datatype))
                occurrence = result.occurrences[0]
                self.assertEqual(occurrence['storage_status'], 'declaration_not_pid')
                self.assertTrue(occurrence['backing_owner_id'])
                self.assertEqual(len(occurrence['content_ids']), 1)
        for dimensions in ('0', '', '1', '2,3', 'bad'):
            with self.subTest(dimensions=dimensions):
                *_, result = capture(call() + ';', tag(attrs=f' Dimensions="{dimensions}"'))
                self.assertEqual(result.occurrences[0]['storage_status'], 'dimensions_unmodeled')
                self.assertEqual(result.occurrences[0]['structure_candidates'], [])
                self.assertTrue(result.occurrences[0]['content_ids'])
        *_, lower = capture(call() + ';', tag(datatype='pid'))
        self.assertEqual(lower.occurrences[0]['storage_status'], 'linked')

    def test_no_data_opaque_only_and_wrong_decorated_shapes_have_explicit_gaps(self) -> None:
        cases = (
            ('', 'no_data'),
            ('<Data Format="L5K">[1,2]</Data>', 'no_decorated_data'),
            ('<Data Format="String">text</Data>', 'no_decorated_data'),
            ('<Data Format="Decorated"/>', 'no_pid_structure'),
            ('<Data Format="Decorated"><DataValue Value="7"/></Data>', 'no_pid_structure'),
            ('<Data Format="Decorated"><Structure DataType="OTHER"/></Data>', 'no_pid_structure'),
            ('<Data Format="Decorated"><Array><Element Index="[0]">' + PID_STRUCTURE
             + '</Element></Array></Data>', 'no_pid_structure'),
        )
        for data, expected in cases:
            with self.subTest(expected=expected, data=data):
                *_, result = capture(call() + ';', tag(data))
                self.assertEqual(result.occurrences[0]['storage_status'], expected)
                self.assertEqual(result.status, 'partial')
                self.assertEqual(result.coverage['backing_owners_without_data'], int(not data))

    def test_all_representations_roots_and_duplicate_direct_members_remain_separate(self) -> None:
        structure = ('<Structure DataType="PID"><DataValueMember Name="SP" Value="1"/>'
                     '<DataValueMember Name="SP" Value="2"/><StructureMember Name="Nested">'
                     '<DataValueMember Name="SP" Value="3"/></StructureMember></Structure>')
        data = (f'<Data Format="Decorated">{structure}{structure}</Data>'
                f'<DefaultData Format="Decorated">{PID_STRUCTURE}</DefaultData>'
                '<Data Format="L5K">[private-uninterpreted]</Data>'
                '<DefaultData Format="Vendor">private-alternative</DefaultData>')
        inputs = capture(call() + call() + ';', tag(data))
        tag_data, result = inputs[-2:]
        occurrence = result.occurrences[0]
        self.assertEqual(occurrence['content_ids'], [row['id'] for row in tag_data.contents])
        self.assertEqual(len(occurrence['decorated_content_ids']), 2)
        self.assertEqual(len(occurrence['structure_candidates']), 3)
        self.assertEqual([len(row['member_ids']) for row in occurrence['structure_candidates']], [3, 3, 2])
        self.assertEqual(result.coverage['representation_occurrences'], 8)
        self.assertEqual(result.coverage['structure_occurrences'], 6)
        self.assertEqual(result.coverage['direct_member_occurrences'], 16)
        self.assertEqual(result.coverage['occurrences_with_multiple_structures'], 2)
        self.assertEqual(result.coverage['distinct_backing_owners'], 1)
        self.assertEqual(result.status, 'complete')
        self.assertEqual(tag_data.status, 'partial')
        rendered = render_pid_json(result)
        for private in ('private-uninterpreted', 'private-alternative', '001.50', 'Nested'):
            self.assertNotIn(private, rendered)

    def test_mixed_text_and_unmodeled_descendants_prevent_safe_structure_selection(self) -> None:
        for data in (
            f'<Data Format="Decorated">mixed{PID_STRUCTURE}</Data>',
            '<Data Format="Decorated"><Structure DataType="PID">mixed</Structure></Data>',
            '<Data Format="Decorated"><Structure DataType="PID"><Unexpected/></Structure></Data>',
            '<Data Format="Decorated"><Structure DataType="PID"><DataValueMember Name="SP"/>'
            '</Structure></Data>',
            '<Data Format="Decorated"><Structure DataType="PID"><StructureMember Name="N">'
            '<Unexpected/></StructureMember></Structure></Data>',
        ):
            with self.subTest(data=data):
                *_, result = capture(call() + ';', tag(data))
                self.assertEqual(result.occurrences[0]['storage_status'], 'no_pid_structure')

    def test_namespace_provenance_controls_owner_declaration_envelope_and_structure(self) -> None:
        *_, coherent = capture(call() + ';', tag(), ' xmlns="urn:coherent"')
        self.assertEqual(coherent.occurrences[0]['storage_status'], 'linked')
        cases = (
            (tag().replace('<Tag ', '<x:Tag ').replace('</Tag>', '</x:Tag>'),
             'owner_namespace_unsupported'),
            (tag().replace('DataType="PID"', 'x:DataType="PID"', 1), 'declaration_not_pid'),
            (tag().replace('<Data ', '<x:Data ').replace('</Data>', '</x:Data>'), 'no_decorated_data'),
            (tag().replace('<Structure ', '<x:Structure ').replace('</Structure>', '</x:Structure>'),
             'no_pid_structure'),
            (tag().replace('<Structure DataType=', '<Structure x:DataType='), 'no_pid_structure'),
            (tag(attrs=' x:Dimensions="1"'), 'dimensions_unmodeled'),
        )
        for declaration, expected in cases:
            with self.subTest(expected=expected, declaration=declaration):
                *_, result = capture(call() + ';', declaration, ' xmlns:x="urn:foreign"')
                self.assertEqual(result.occurrences[0]['storage_status'], expected)
                self.assertEqual(result.occurrences[0]['structure_candidates'], [])
                self.assertEqual(len(result.occurrences[0]['content_ids']), 1)

    def test_repeated_missing_and_opaque_owners_have_distinct_and_occurrence_counts(self) -> None:
        *_, result = capture(call('MissingData') * 2 + call('Opaque') * 3 + ';',
                             tag('', 'MissingData') + tag('<Data Format="Raw">opaque</Data>', 'Opaque'))
        c = result.coverage
        self.assertEqual(c['distinct_backing_owners'], 2)
        self.assertEqual(c['backing_owners_without_data'], 1)
        self.assertEqual(c['backing_owners_with_opaque_only'], 1)
        self.assertEqual(c['occurrences_without_data'], 2)
        self.assertEqual(c['occurrences_with_opaque_only'], 3)

    def test_binding_alias_and_scope_namespace_provenance_gates_canonical_links(self) -> None:
        ordinary = capture(call('Alias') + ';', tag(), ' xmlns:x="urn:foreign"')[0].data.decode()
        local_alias = '<Tags><Tag Name="Alias" TagType="Alias" AliasFor="Loop"/></Tags>'
        base = ordinary.replace('<Program Name="P">', '<Program Name="P">' + local_alias)
        self.assertEqual(capture_xml(base)[-1].occurrences[0]['storage_status'], 'linked')
        for xml in (
            base.replace('AliasFor="Loop"', 'x:AliasFor="Loop"'),
            base.replace('TagType="Alias"', 'x:TagType="Alias"'),
            base.replace('Name="Alias"', 'x:Name="Alias"'),
            base.replace('Name="Loop"', 'x:Name="Loop"'),
            base.replace('Name="P"', 'x:Name="P"'),
            base.replace('Name="Invented"', 'x:Name="Invented"'),
            base.replace('<Program ', '<x:Program ').replace('</Program>', '</x:Program>'),
            base.replace('<Rung ', '<x:Rung ').replace('</Rung>', '</x:Rung>'),
            base.replace('<Text>', '<x:Text>').replace('</Text>', '</x:Text>'),
            base.replace(local_alias, local_alias.replace('<Tag ', '<x:Tag ').replace('</Tag>', '</x:Tag>')),
        ):
            with self.subTest(xml=xml):
                inputs = capture_xml(xml)
                reference, occurrence = inputs[2].operands[0], inputs[-1].occurrences[0]
                self.assertEqual(reference['status'], 'root_bound')
                self.assertEqual(occurrence['storage_status'], 'binding_namespace_unsupported')
                self.assertEqual(occurrence['backing_owner_id'], reference['target_id'])
                self.assertEqual(len(occurrence['content_ids']), 1)
                self.assertEqual(occurrence['structure_candidates'], [])
        # An unrelated foreign extension does not invalidate an ordinary path.
        unrelated = base.replace('</Controller>', '<Vendor><x:Extension x:Name="Unused"/></Vendor></Controller>')
        self.assertEqual(capture_xml(unrelated)[-1].occurrences[0]['storage_status'], 'linked')

    def test_snapshot_inventory_references_and_tag_data_are_authenticated(self) -> None:
        inputs = capture(call() + ';', tag())
        for index, mutate in (
            (1, lambda value: value.counts.update(controller_tags=True)),
            (2, lambda value: value.operands[0].update(target_id='source-secret')),
            (3, lambda value: value.elements[0]['attributes'].update(DataType='source-secret')),
            (3, lambda value: value.contents.append(value.contents)),
        ):
            changed = list(deepcopy(inputs[:-1]))
            mutate(changed[index])
            with self.subTest(index=index), self.assertRaisesRegex(
                    PidError, '^PID evidence is inconsistent or exceeds its limits\\.$'):
                analyze_pid(*changed)
        with self.assertRaises(PidError):
            analyze_pid(replace(inputs[0], size_bytes=True), *inputs[1:-1])
        other = capture(call() + ';', tag(name='Different'))[0]
        with self.assertRaises(PidError):
            analyze_pid(other, *inputs[1:-1])

    def test_canonical_replay_rejects_private_links_slots_counts_cycles_and_extra_keys(self) -> None:
        inputs = capture(call() + ';', tag())
        for mutate in (
            lambda r: r.occurrences[0].update(backing_owner_id='source-secret'),
            lambda r: r.occurrences[0]['content_ids'].clear(),
            lambda r: r.occurrences[0]['structure_candidates'][0]['member_ids'].reverse(),
            lambda r: r.operands[0].update(slot='process_variable'),
            lambda r: r.operands[0].update(argument_index=True),
            lambda r: r.coverage.update(occurrences_total=True),
            lambda r: r.occurrences.append(r.occurrences),
            lambda r: r.__dict__.update(private='source-secret'),
        ):
            forged = deepcopy(inputs[-1])
            mutate(forged)
            with self.subTest(mutate=mutate), self.assertRaises(PidError):
                validate_pid(*inputs[:-1], forged)
        with self.assertRaises(PidError):
            validate_pid(*inputs[:-1], inputs[-1].to_dict())

    def test_record_and_byte_capacities_reject_before_emitting_evidence(self) -> None:
        inputs = capture(call() + call() + ';', tag())
        for constant, limit in (('MAX_PID_OCCURRENCES', 1), ('MAX_PID_OPERANDS', 13),
                                ('MAX_PID_EVIDENCE_BYTES', 100), ('MAX_PID_JSON_BYTES', 100)):
            with self.subTest(constant=constant), patch(f'plc_workbench.pid.{constant}', limit):
                with self.assertRaises(PidError):
                    analyze_pid(*inputs[:-1])
        for mutate in (lambda r: r.occurrences.append(r.occurrences),
                       lambda r: r.coverage.update(occurrences_total=True),
                       lambda r: r.operands[0].update(slot=object())):
            forged = deepcopy(inputs[-1])
            mutate(forged)
            with self.assertRaises(PidError):
                render_pid_json(forged)


if __name__ == '__main__':
    unittest.main()
