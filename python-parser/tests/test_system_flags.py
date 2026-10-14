"""Exact S:FS contact-role recognition using invented in-memory source only."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch

from plc_workbench.reference_reporting import render_reference_json, render_reference_text
from plc_workbench.references import (
    ALIAS_STATUSES, OPERAND_STATUSES, ReferenceError, _address, _system_flag,
    analyze_references, validate_references,
)
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def inventory(text: str, *, tags: str = ''):
    return analyze_snapshot(snapshot_from_bytes((
        '<RSLogix5000Content><Controller Name="Invented"><Tags>'
        '<Tag Name="Destination" TagType="Base"/>' + tags + '</Tags>'
        '<Programs><Program Name="Synthetic"><Routines><Routine Name="Main" Type="RLL">'
        '<RLLContent><Rung Number="0" Type="N"><Text><![CDATA[' + text + ']]></Text></Rung>'
        '</RLLContent></Routine></Routines></Program></Programs></Controller></RSLogix5000Content>'
    ).encode()))


class SystemFlagTests(unittest.TestCase):
    def assert_system_flag(self, operand: dict) -> None:
        self.assertEqual(operand['status'], 'system_flag')
        self.assertIsNone(operand['symbol_id'])
        self.assertIsNone(operand['target_id'])
        self.assertIsNone(operand['reason'])
        self.assertEqual(operand['suffix'], '')
        self.assertEqual(operand['alias_chain'], [])

    def test_both_contact_roles_classify_without_creating_symbols_or_effects(self) -> None:
        source = inventory('XIC(S:FS)XIO(S:FS);')
        before = source.to_dict()
        result = analyze_references(source)
        self.assertEqual(len(result.operands), 2)
        for operand in result.operands:
            self.assert_system_flag(operand)
        self.assertEqual([row['name'] for row in result.symbols], ['Destination'])
        self.assertEqual(result.aliases, [])
        self.assertEqual(result.rack_candidates['matches'],
                         {'aliases': [], 'direct_operands': [], 'alias_operands': []})
        self.assertEqual(result.coverage['instructions_catalogued'], 2)
        self.assertEqual(result.coverage['operands_total'], 2)
        self.assertEqual(result.status, 'complete')
        self.assertEqual((result.schema_version, result.analyzer_version), (4, 'source-references-5'))
        self.assertEqual((source.schema_version, source.parser_version), (3, 'source-inventory-3'))
        for field in ('semantic_analysis', 'effect_analysis', 'member_validation'):
            self.assertEqual(getattr(result, field), 'not_implemented')
        self.assertIn('system_flag', OPERAND_STATUSES)
        self.assertNotIn('system_flag', ALIAS_STATUSES)
        self.assertEqual(source.to_dict(), before)
        validate_references(source, result)

    def test_case_and_outer_whitespace_keep_raw_occurrence_evidence_and_ids(self) -> None:
        source = inventory('xic(s:fs)xIo(S:fS);')
        rung = source.rungs[0]
        first = replace(rung.instructions[0], arguments=(' \ts:Fs\n ',))
        second = replace(rung.instructions[1], arguments=('S:fS',))
        source = replace(source, rungs=[replace(rung, instructions=[first, second])])
        before = source.to_dict()
        result = analyze_references(source)
        self.assertEqual([row['raw_text'] for row in result.operands], [' \ts:Fs\n ', 'S:fS'])
        for operand, instruction in zip(result.operands, (first, second)):
            self.assert_system_flag(operand)
            identity = f"{source.snapshot['id']}\0{instruction.id}\0{0}"
            self.assertEqual(operand['id'], 'operand_' + hashlib.sha256(identity.encode()).hexdigest())
            self.assertEqual(operand['instruction_id'], instruction.id)
            self.assertEqual(operand['rung_id'], rung.id)
            self.assertEqual(operand['scope_id'], rung.scope_id)
            self.assertEqual(operand['argument_index'], 0)
        self.assertEqual(source.to_dict(), before)
        validate_references(source, result)

    def test_helper_is_exact_ascii_spelling_role_and_position_not_a_namespace_rule(self) -> None:
        for opcode in ('XIC', 'XIO', 'xic', 'xIo'):
            for raw in ('S:FS', 's:fs', ' \tS:fS\n '):
                self.assertTrue(_system_flag(opcode, 0, raw))
        for opcode, position, raw in [
            ('MOV', 0, 'S:FS'), ('XIC', 1, 'S:FS'), ('XIO', -1, 'S:FS'),
            ('XIC', False, 'S:FS'), ('XIC', 0.0, 'S:FS'), ('XIC', 0, 'S:FS.Member'),
            ('XIC', 0, 'S:FS[0]'), ('XIC', 0, 'S:FS0'), ('XIC', 0, 'S:FS:Extra'),
            ('XIC', 0, 'S:DN'), ('XIC', 0, 'SFS'), ('XIC', 0, 'S :FS'),
            ('XIC', 0, '\u017f:FS'), ('X\u0131C', 0, 'S:FS'), ('XIC', 0, '"S:FS"'),
        ]:
            with self.subTest(opcode=opcode, position=position, raw=raw):
                self.assertFalse(_system_flag(opcode, position, raw))
        # The general address grammar is unchanged; context supplies recognition.
        self.assertEqual(_address('S:FS'), (('S:FS', ''), None))

    def test_wrong_arity_and_unknown_instruction_precede_flag_recognition(self) -> None:
        for opcode in ('XIC', 'XIO'):
            for arguments in ('', 'S:FS,Destination', 'S:FS,S:FS,S:FS'):
                result = analyze_references(inventory(f'{opcode}({arguments});'))
                with self.subTest(opcode=opcode, arguments=arguments):
                    self.assertEqual(result.coverage['instructions_catalogued'], 0)
                    self.assertEqual(result.status, 'partial')
                    self.assertTrue(all(row['status'] == 'argument_count_mismatch' for row in result.operands))
        result = analyze_references(inventory('PRIVATE_CONTACT(S:FS);'))
        self.assertEqual(result.operands[0]['status'], 'unsupported_instruction')

    def test_other_roles_keep_existing_lookup_expression_and_label_rules(self) -> None:
        result = analyze_references(inventory(
            'OTE(S:FS)MOV(S:FS,Destination)CPT(Destination,S:FS)JMP(S:FS)LBL(S:FS);'))
        self.assertEqual([row['status'] for row in result.operands], [
            'unresolved', 'unresolved', 'root_bound', 'root_bound',
            'unsupported_expression', 'non_data', 'non_data',
        ])
        self.assertEqual(result.operands[0]['reason'], 'colon_root_not_declared')
        self.assertEqual(result.status, 'partial')

    def test_members_indices_lookalikes_and_other_flags_remain_explicit_gaps(self) -> None:
        operands = ('S:FS.Data', 'S:FS[0]', 'S:FS:More', 'S:FS0', 'S:DN', 'SFS',
                    'S:FS[Index]', 'S :FS', '\u017f:FS')
        source = inventory(''.join(f'XIC({raw})' for raw in operands) + ';')
        result = analyze_references(source)
        self.assertEqual([row['status'] for row in result.operands],
                         ['unresolved'] * 6 + ['unsupported_address'] * 3)
        self.assertEqual(result.operands[6]['reason'], 'non_static_array_index')
        self.assertEqual(result.status, 'partial')

    def test_quotes_remain_literals_and_empty_contact_slot_remains_empty(self) -> None:
        result = analyze_references(inventory('XIC("S:FS")XIO(\'S:FS\');'))
        self.assertEqual([row['status'] for row in result.operands], ['literal', 'literal'])
        source = inventory('XIC(S:FS);')
        rung = source.rungs[0]
        instruction = replace(rung.instructions[0], arguments=(' \t ',))
        source = replace(source, rungs=[replace(rung, instructions=[instruction])])
        self.assertEqual(analyze_references(source).operands[0]['status'], 'empty')

    def test_alias_targets_do_not_acquire_system_flag_semantics(self) -> None:
        tags = ('<Tag Name="First" TagType="Alias" AliasFor="Second"/>'
                '<Tag Name="Second" TagType="Alias" AliasFor="s:fs"/>')
        result = analyze_references(inventory('XIC(First)XIO(Second)XIC(S:FS);', tags=tags))
        self.assertEqual([row['status'] for row in result.operands], ['unresolved', 'unresolved', 'system_flag'])
        self.assertEqual([row['reason'] for row in result.aliases], ['colon_root_not_declared'] * 2)
        self.assertEqual(len(result.operands[0]['alias_chain']), 2)
        self.assertEqual(len(result.operands[1]['alias_chain']), 1)
        self.assertTrue(all(row['status'] == 'unresolved' for row in result.aliases))
        self.assertEqual(result.status, 'partial')

    def test_direct_flag_is_not_bound_to_a_coincident_invented_tag_name(self) -> None:
        source = inventory('XIC(S:FS)MOV(S:FS,Destination);',
                           tags='<Tag Name="S:FS" TagType="Base"/>')
        result = analyze_references(source)
        self.assert_system_flag(result.operands[0])
        self.assertEqual(result.operands[1]['status'], 'root_bound')
        self.assertEqual(result.operands[1]['target_id'], result.symbols[1]['id'])

    def test_canonical_validation_rejects_reclassified_forged_or_old_private_records(self) -> None:
        source = inventory('XIC(S:FS);')
        result = analyze_references(source)
        for fields in ({'status': 'non_data'}, {'status': 'unresolved', 'reason': 'colon_root_not_declared'},
                       {'target_id': result.symbols[0]['id']}, {'symbol_id': result.symbols[0]['id']},
                       {'suffix': '.Data'}, {'alias_chain': [result.symbols[0]['id']]},
                       {'raw_text': 'S:DN'}, {'argument_index': False}):
            changed = deepcopy(result)
            changed.operands[0].update(fields)
            with self.subTest(fields=fields), self.assertRaises(ReferenceError):
                validate_references(source, changed)
        for schema, analyzer in ((3, 'source-references-4'), (4, 'source-references-4'),
                                 (3, 'source-references-5'), (2, 'source-references-3')):
            with self.subTest(schema=schema, analyzer=analyzer), self.assertRaises(ReferenceError):
                validate_references(source, replace(result, schema_version=schema, analyzer_version=analyzer))

    def test_operand_and_expanded_evidence_limits_still_apply(self) -> None:
        with patch('plc_workbench.references.MAX_OPERANDS', 1):
            with self.assertRaisesRegex(ReferenceError, '^Reference analysis exceeds the operand limit[.]$'):
                analyze_references(inventory('XIC(S:FS)XIO(S:FS);'))
        with patch('plc_workbench.references.MAX_EXPANDED_EVIDENCE_CHARS', 0):
            self.assertEqual(analyze_references(inventory('XIC(S:FS);')).status, 'complete')
            with self.assertRaisesRegex(ReferenceError, '^Reference analysis exceeds the expanded-evidence limit[.]$'):
                analyze_references(inventory('XIC(S:FS)XIC(Destination.Member);'))

    def test_private_reports_explain_flag_and_retain_raw_evidence_without_runtime_values(self) -> None:
        result = analyze_references(inventory('XIC(s:fs);'))
        text = render_reference_text(result)
        self.assertIn('system_flag identifies the direct S:FS instruction operand in XIC/XIO.', text)
        self.assertIn('No runtime first-scan value or execution behavior is simulated.', text)
        self.assertIn('s:fs -> system_flag', text)
        payload = json.loads(render_reference_json(result))
        self.assertEqual(payload['schema_version'], 4)
        self.assertEqual(payload['operands'][0]['raw_text'], 's:fs')
        self.assertNotIn('value', payload['operands'][0])


if __name__ == '__main__':
    unittest.main()
