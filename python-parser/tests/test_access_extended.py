"""Source-bound evidence for counters, messages, system slots and SFC reset."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import AccessError, analyze_access, render_access_json, validate_access
from plc_workbench.access_summary import build_access_summary, render_access_summary
from plc_workbench.references import _Resolver, analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from test_access import source, tag, program


BASELINE_TEXT = ('TON(A,?,0)CTU(A,?,0)CTD(A,1,2)MSG(A)GSV(TASK,,Status,A)'
                 'SSV(TASK,,Status,A)SFR(R,A)SFR(R,0)MOV(A,B);')


def analyze(text: str, tags: str = '', local_tags: str = ''):
    inventory = source(text, tags, local_tags)
    references = analyze_references(inventory)
    return inventory, references, analyze_access(inventory, references)


class ExtendedAccessTests(unittest.TestCase):
    def test_legacy_access_and_reference_bytes_reproduce_captured_baseline(self) -> None:
        # SHA256 values captured from 760448e before changing either layer.
        inventory = source(BASELINE_TEXT, tag('A') + tag('B'))
        references = analyze_references(inventory)
        before = deepcopy(references.to_dict())
        access2 = analyze_access(inventory, references, schema_version=2)
        outputs = {
            'cd6051f45c78ce08b6ed75caf1a6f49f43211b4f5c05c2ec392c031c0edd683c': render_access_json(access2),
            '3f37e1f696de9c6b1dfa46a9606a1d778a643ca544dfb7888970128e44c51aa5':
                render_access_summary(build_access_summary(inventory, references, access2)),
            '73b3e1da537ba6bd678a83e07153d8e09b1d98600f50e9604a514df621dd9c7d':
                json.dumps(references.to_dict(), sort_keys=True),
        }
        for digest, text in outputs.items():
            self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), digest)
        access3 = analyze_access(inventory, references)
        self.assertEqual(references.to_dict(), before)
        self.assertEqual(access3.schema_version, 3)
        self.assertTrue(all('binding_origin' not in row for row in access2.operands))
        validate_access(inventory, references, access2)
        validate_access(inventory, references, access3)

    def test_all_new_roles_bind_only_explicit_data_slots(self) -> None:
        inventory, references, result = analyze(BASELINE_TEXT, tag('A') + tag('B') + tag('TASK') + tag('Status') + tag('R'))
        self.assertEqual([row['role'] for row in result.operands],
                         ['read_write', 'non_data', 'non_data'] * 3 + ['read_write'] +
                         ['non_data'] * 3 + ['write'] + ['non_data'] * 3 + ['read'] +
                         ['non_data', 'write', 'non_data', 'non_data', 'read', 'write'])
        self.assertEqual(result.coverage['extended_instructions'], {
            'counter': 2, 'message': 1, 'system_get': 1, 'system_set': 1,
            'sfc_reset_step': 1, 'sfc_reset_initial': 1})
        self.assertEqual(result.coverage['extended_bound_operands'], 6)
        self.assertEqual(result.coverage['bound_by_role']['non_data'], 0)
        self.assertEqual(result.coverage['counter_pseudo_operands_by_kind'], {'placeholder': 1, 'integer_literal': 3})
        self.assertEqual(result.status, 'complete')
        for row, reference in zip(result.operands, references.operands, strict=True):
            self.assertEqual(row['id'], reference['id'])
            self.assertEqual(row['source_reference_status'], reference['status'])
            if row['binding_origin'] == 'access_non_data':
                self.assertEqual((row['binding_status'], row['target_id'], row['symbol_id'], row['suffix'], row['alias_chain']),
                                 ('non_data', None, None, '', []))
            elif row['binding_origin'] == 'access_resolver':
                self.assertEqual(reference['status'], 'unsupported_instruction')
        validate_access(inventory, references, result)

    def test_fresh_resolution_preserves_scope_shadow_alias_suffix_and_module_shape(self) -> None:
        inventory = source('MSG(LocalAlias.Member)GSV(TASK,,Status,Local:1:I.Data[2]);',
                           tag('Shared') + tag('Local:1:I'),
                           tag('Shared') + tag('LocalAlias', 'Shared[1]'),
                           program('MSG(Shared);', name='Q'))
        references = analyze_references(inventory)
        result = analyze_access(inventory, references)
        alias, module, other = result.operands[0], result.operands[4], result.operands[5]
        self.assertEqual(alias['suffix'], '[1].Member')
        self.assertNotEqual(alias['symbol_id'], alias['target_id'])
        self.assertEqual(alias['alias_chain'], [alias['symbol_id']])
        self.assertNotEqual(alias['target_id'], other['target_id'])
        self.assertEqual(module['binding_status'], 'root_bound')
        self.assertEqual(module['suffix'], '.Data[2]')
        self.assertEqual(result.coverage['extended_bound_operands'], 3)

    def test_aoi_scope_isolated_from_controller_and_parameter_aliases_follow_existing_rules(self) -> None:
        raw = ('<RSLogix5000Content><Controller Name="C"><Tags>' + tag('Outside') + '</Tags>'
               '<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="AO">'
               '<Parameters><Parameter Name="Param" DataType="DINT" Usage="InOut"/></Parameters>'
               '<LocalTags><LocalTag Name="Local" DataType="DINT"/></LocalTags>'
               '<Routines><Routine Name="Logic" Type="RLL"><RLLContent><Rung Number="0" Type="N">'
               '<Text><![CDATA[MSG(Param)MSG(Local)MSG(Outside);]]></Text></Rung></RLLContent>'
               '</Routine></Routines></AddOnInstructionDefinition></AddOnInstructionDefinitions>'
               '</Controller></RSLogix5000Content>')
        inventory = analyze_snapshot(snapshot_from_bytes(raw.encode()))
        result = analyze_access(inventory, analyze_references(inventory))
        self.assertEqual([row['binding_status'] for row in result.operands], ['root_bound', 'root_bound', 'unresolved'])
        self.assertEqual(result.coverage['access_gap_operands'], 1)

    def test_invalid_counter_pseudoforms_fail_whole_signature_without_resolution(self) -> None:
        for opcode in ('CTU', 'CTD'):
            for value in ('A', 'A.Member', 'A[0]', 'A+1', '1.0', '1e2', '"1"', '1_000',
                          '2#2', '8#8', '16#G', '2#_1', '2#1_', '16#F__F', '+?', 'TRUE'):
                for index in (1, 2):
                    fields = ['A', '?', '?']
                    fields[index] = value
                    with self.subTest(opcode=opcode, value=value, index=index):
                        inventory = source(f'{opcode}({",".join(fields)});', tag('A'))
                        references = analyze_references(inventory)
                        with patch('plc_workbench.access._Resolver', side_effect=AssertionError('Must not resolve')):
                            result = analyze_access(inventory, references)
                        self.assertEqual(result.instructions[0]['status'], 'unsupported_operand_form')
                        self.assertTrue(all(row['role'] == 'unknown' and row['binding_origin'] == 'source_references'
                                            for row in result.operands))
                        self.assertEqual(result.coverage['counter_invalid_forms'], 1)
                        self.assertEqual(result.coverage['extended_instructions']['counter'], 0)
                        self.assertEqual(sum(result.coverage['counter_pseudo_operands_by_kind'].values()), 0)

    def test_counter_pseudo_literals_are_lexical_nondata_without_value_conversion(self) -> None:
        for value in ('?', '0', '+0', '-0', '0123', '-999999999999999999999999',
                      '2#1_0', '+2#0', '-8#7_0', '8#123', '16#f_F', '+16#0A', '-16#BEEF'):
            with self.subTest(value=value):
                _, _, result = analyze(f'ctu(A,{value},?)CTD(A,?,{value});', tag('A'))
                self.assertEqual(result.status, 'complete')
                self.assertEqual(result.coverage['extended_instructions']['counter'], 2)
                pseudo = [row for row in result.operands if row['reason'] == 'counter_pseudo_operand']
                self.assertEqual(len(pseudo), 4)
                self.assertTrue(all(row['binding_status'] == 'non_data' for row in pseudo))

    def test_only_blank_system_instance_is_permitted_and_arity_has_priority(self) -> None:
        cases = [('GSV(TASK,,Status,A)', 'classified'), ('SSV(TASK, ,Status,1)', 'classified'),
                 ('GSV(,,Status,A)', 'empty_argument'), ('GSV(TASK,,,A)', 'empty_argument'),
                 ('GSV(TASK,,Status,)', 'empty_argument'), ('GSV(TASK,,A)', 'argument_count_mismatch'),
                 ('MSG()', 'argument_count_mismatch'), ('SFR(R,)', 'empty_argument'),
                 ('CTU(A,,A)', 'empty_argument'), ('CTU(A,?,A,?)', 'argument_count_mismatch')]
        for text, status in cases:
            with self.subTest(text=text):
                _, _, result = analyze(text + ';', tag('A'))
                self.assertEqual(result.instructions[0]['status'], status)
                if status != 'classified':
                    self.assertTrue(all(row['role'] == 'unknown' for row in result.operands))
                    self.assertEqual(result.coverage['counter_invalid_forms'], 0)

    def test_sfr_only_exact_zero_is_initial_sentinel_other_literals_are_write_gaps(self) -> None:
        for value, initial in (('0', True), (' 0 ', True), ('+0', False), ('-0', False),
                               ('00', False), ('0.0', False), ('16#0', False), ('1', False), ('"0"', False)):
            with self.subTest(value=value):
                _, _, result = analyze(f'SFR(UncheckedRoutine,{value});')
                row = result.operands[1]
                self.assertEqual(row['role'], 'non_data' if initial else 'write')
                self.assertEqual(result.coverage['extended_instructions']['sfc_reset_initial'], int(initial))
                self.assertEqual(result.coverage['access_gap_operands'], int(not initial))
                self.assertEqual(result.status, 'complete' if initial else 'partial')
        _, _, result = analyze('SFR(UncheckedRoutine,A.UnknownMember);', tag('A'))
        self.assertEqual(result.operands[1]['binding_status'], 'root_bound')
        self.assertEqual(result.member_validation, 'not_implemented')
        self.assertEqual(result.execution_analysis, 'not_implemented')

    def test_new_bindings_report_gaps_without_silent_guesses(self) -> None:
        _, _, result = analyze('MSG(Missing)MSG(0)GSV(TASK,,Status,A[Index])'
                               'SSV(TASK,,Status,123)SFR(R,Cycle);', tag('A') + tag('Cycle', 'Cycle'))
        data = [row for row in result.operands if row['binding_origin'] == 'access_resolver']
        self.assertEqual([row['binding_status'] for row in data],
                         ['unresolved', 'literal', 'unsupported_address', 'literal', 'alias_cycle'])
        self.assertEqual(data[2]['binding_reason'], 'non_static_array_index')
        self.assertEqual(result.coverage['access_gap_operands'], 4)
        self.assertEqual(result.coverage['extended_bound_operands'], 0)
        self.assertEqual(result.roots, [])

    def test_provenance_coverage_metadata_and_version_tampering_are_rejected(self) -> None:
        inventory, references, result = analyze('MSG(Alias)GSV(TASK,,Status,A);', tag('A') + tag('Alias', 'A'))
        mutations = [
            lambda r: r.operands[0].update(binding_origin='source_references'),
            lambda r: r.operands[0].update(source_reference_status='root_bound'),
            lambda r: r.operands[0].update(binding_reason='invented'),
            lambda r: r.operands[0]['alias_chain'].clear(),
            lambda r: r.operands[1].update(target_id=result.operands[0]['target_id']),
            lambda r: r.coverage.update(extended_bound_operands=0),
            lambda r: r.coverage['extended_instructions'].update(message=True),
            lambda r: vars(r).update(schema_version=2),
            lambda r: vars(r).update(analyzer_version='instruction-access-2'),
        ]
        for mutate in mutations:
            candidate = deepcopy(result)
            mutate(candidate)
            with self.subTest(mutation=mutate), self.assertRaises(AccessError):
                validate_access(inventory, references, candidate)
        for version in (True, 1, 4, '3', None):
            with self.subTest(version=version), self.assertRaises(AccessError):
                analyze_access(inventory, references, schema_version=version)

    def test_ascii_opcodes_and_evidence_limits_apply_before_expansion(self) -> None:
        inventory = source('MSG(A);', tag('A'))
        rung = inventory.rungs[0]
        forged = replace(inventory, rungs=[replace(rung, instructions=[replace(rung.instructions[0], opcode='M\u017fG')])])
        result = analyze_access(forged, analyze_references(forged))
        self.assertEqual(result.instructions[0]['status'], 'unsupported_instruction')
        references = analyze_references(inventory)
        for limit in ('MAX_INSTRUCTIONS', 'MAX_OPERANDS', 'MAX_ACCESS_BYTES'):
            with self.subTest(limit=limit), patch(f'plc_workbench.access.{limit}', 0), self.assertRaises(AccessError):
                analyze_access(inventory, references)

    def test_repeated_fresh_alias_expansion_is_rejected_before_remaining_resolution_or_render(self) -> None:
        inventory = source('MSG(Alias.Member)' * 5 + ';', tag('Base') + tag('Alias', 'Base[123]'))
        references = analyze_references(inventory)
        resolver = _Resolver(inventory)
        binding = resolver.resolve('Alias.Member', inventory.rungs[0].scope_id)
        cost = len(binding['suffix']) + sum(map(len, binding['alias_chain']))
        with patch('plc_workbench.access.MAX_EXPANDED_EVIDENCE_CHARS', 2 * cost - 1), \
                patch('plc_workbench.access._Resolver', return_value=resolver), \
                patch.object(resolver, 'resolve', wraps=resolver.resolve) as resolve, \
                patch('plc_workbench.access.render_access_json') as render:
            with self.assertRaises(AccessError):
                analyze_access(inventory, references)
            # The second occurrence exhausts the budget. Later traversals and
            # the final whole-result serialization must never occur.
            self.assertEqual(resolve.call_count, 2)
            render.assert_not_called()

    def test_inherited_suffix_and_chain_copies_share_the_new_expansion_budget(self) -> None:
        inventory = source('XIC(Alias.Member)' * 3 + ';', tag('Base') + tag('Alias', 'Base[123]'))
        references = analyze_references(inventory)
        cost = sum(len(row['suffix']) + sum(map(len, row['alias_chain']))
                   for row in references.operands)
        with patch('plc_workbench.access.MAX_EXPANDED_EVIDENCE_CHARS', cost):
            result = analyze_access(inventory, references)
            self.assertEqual(result.coverage['linked_operands'], 3)
        with patch('plc_workbench.access.MAX_EXPANDED_EVIDENCE_CHARS', cost - 1), \
                patch('plc_workbench.access._Resolver') as resolver, \
                patch('plc_workbench.access.render_access_json') as render:
            with self.assertRaises(AccessError):
                analyze_access(inventory, references)
            resolver.assert_not_called()
            render.assert_not_called()
        before = render_access_json(analyze_access(inventory, references, schema_version=2))
        with patch('plc_workbench.access.MAX_EXPANDED_EVIDENCE_CHARS', 0):
            legacy = analyze_access(inventory, references, schema_version=2)
        self.assertEqual(render_access_json(legacy), before)


if __name__ == '__main__':
    unittest.main()
