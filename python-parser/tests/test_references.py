"""Independent, synthetic scope and evidence tests; never use private exports."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from plc_workbench.references import ReferenceError, analyze_references, validate_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes

FIXTURE = Path(__file__).resolve().parents[2] / 'public/fixtures/synthetic/controller_demo.L5X'


def tag(name: str, target: str | None = None) -> str:
    attributes = 'TagType="Base" DataType="DINT"' if target is None else f'TagType="Alias" AliasFor="{target}"'
    return f'<Tag Name="{name}" {attributes}/>'


def routine(text: str) -> str:
    return ('<Routines><Routine Name="Main" Type="RLL"><RLLContent>'
            f'<Rung Number="0" Type="N"><Text><![CDATA[{text}]]></Text></Rung>'
            '</RLLContent></Routine></Routines>')


def program(text: str, tags: str = '', name: str = 'P') -> str:
    return f'<Program Name="{name}"><Tags>{tags}</Tags>{routine(text)}</Program>'


def inventory(tags: str = '', programs: str = '', extras: str = ''):
    return analyze_snapshot(snapshot_from_bytes((
        '<RSLogix5000Content><Controller Name="Demo">'
        f'<Tags>{tags}</Tags><Programs>{programs}</Programs>{extras}'
        '</Controller></RSLogix5000Content>'
    ).encode()))


def analyze(tags: str = '', text: str = '', local_tags: str = ''):
    return analyze_references(inventory(tags, program(text, local_tags)))


def named(result, name: str, scope: str | None = None):
    return next(row for row in result.symbols if row['name'] == name
                and (scope is None or row['scope_id'] == scope))


class ReferenceTests(unittest.TestCase):
    def test_case_insensitive_local_shadowing_and_separate_programs(self) -> None:
        result = analyze_references(inventory(tag('Signal'),
            program('XIC(sIGNAL);', tag('Signal'), 'One') +
            program('XIC(SIGNAL);', name='Two')))
        first, second = result.operands
        local = named(result, 'Signal', first['scope_id'])
        self.assertEqual(first['symbol_id'], local['id'])
        self.assertNotEqual(second['symbol_id'], local['id'])
        self.assertEqual(second['symbol_id'], result.symbols[0]['id'])
        self.assertEqual(result.status, 'complete')

    def test_duplicate_local_names_are_ambiguous_without_controller_fallback(self) -> None:
        result = analyze(tag('Signal'), 'XIC(signal);', tag('Signal') + tag('SIGNAL'))
        self.assertEqual(result.operands[0]['status'], 'ambiguous')
        self.assertIsNone(result.operands[0]['symbol_id'])
        self.assertEqual(result.coverage['ambiguous_symbol_groups'], 1)
        self.assertEqual(len({row['id'] for row in result.symbols}), 3)
        self.assertEqual(result.status, 'partial')

    def test_controller_alias_uses_declaring_scope_and_composes_suffixes(self) -> None:
        result = analyze(tag('Base') + tag('A', 'B[2]') + tag('B', 'Base.Member'),
                         'XIC(A.3);', tag('Base') + tag('B'))
        operand = result.operands[0]
        self.assertEqual(operand['status'], 'root_bound')
        self.assertEqual(operand['symbol_id'], named(result, 'A')['id'])
        self.assertEqual(operand['target_id'], result.symbols[0]['id'])
        self.assertEqual(operand['suffix'], '.Member[2].3')
        self.assertEqual(operand['alias_chain'], [named(result, 'A')['id'], named(result, 'B')['id']])
        alias = next(row for row in result.aliases if row['source_id'] == named(result, 'A')['id'])
        self.assertEqual(alias['symbol_id'], named(result, 'B')['id'])
        self.assertEqual(alias['target_id'], result.symbols[0]['id'])
        self.assertEqual(alias['suffix'], '.Member[2]')

    def test_unused_aliases_have_cycles_missing_and_ambiguous_targets(self) -> None:
        result = analyze(tag('A', 'B') + tag('B', 'A') + tag('Gone', 'Missing') +
                         tag('Dup') + tag('DUP') + tag('D', 'dup') +
                         '<Tag Name="NoTarget" TagType="Alias"/>', 'XIC(A);')
        statuses = {row['source_id']: row['status'] for row in result.aliases}
        for name, expected in [('A', 'alias_cycle'), ('B', 'alias_cycle'),
                               ('Gone', 'unresolved'), ('D', 'ambiguous'),
                               ('NoTarget', 'unsupported_address')]:
            self.assertEqual(statuses[named(result, name)['id']], expected)
        self.assertEqual(result.operands[0]['status'], 'alias_cycle')
        self.assertIsNone(result.operands[0]['target_id'])
        self.assertEqual(result.status, 'partial')

    def test_alias_depth_is_bounded_and_exact_limit_can_reach_base(self) -> None:
        aliases = ''.join(tag(f'A{i}', f'A{i+1}' if i < 64 else 'Base') for i in range(65))
        result = analyze(tag('Base') + aliases, 'XIC(A0)XIC(A1);')
        self.assertEqual(result.operands[0]['status'], 'alias_depth_limit')
        self.assertEqual(len(result.operands[0]['alias_chain']), 64)
        self.assertEqual(result.operands[1]['status'], 'root_bound')
        self.assertEqual(len(result.operands[1]['alias_chain']), 64)

    def test_aoi_isolation_and_alias_parameter_local_restriction(self) -> None:
        extra = ('<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="AOI">'
                 '<Parameters><Parameter Name="Input" DataType="BOOL"/>'
                 '<Parameter Name="Alias" AliasFor="Local.Member"/>'
                 '<Parameter Name="BadAlias" AliasFor="Input"/></Parameters>'
                 '<LocalTags><LocalTag Name="Local" DataType="DINT"/></LocalTags>'
                 + routine('XIC(Input)XIC(Local)XIC(ControllerOnly)XIC(Alias);') +
                 '</AddOnInstructionDefinition></AddOnInstructionDefinitions>')
        result = analyze_references(inventory(tag('ControllerOnly') + tag('Input'), extras=extra))
        self.assertEqual([row['status'] for row in result.operands],
                         ['root_bound', 'root_bound', 'unresolved', 'root_bound'])
        self.assertEqual(result.operands[0]['target_id'], named(result, 'Input', result.operands[0]['scope_id'])['id'])
        self.assertEqual(result.operands[3]['target_id'], named(result, 'Local')['id'])
        self.assertEqual(result.operands[3]['suffix'], '.Member')
        self.assertEqual(result.aliases[1]['status'], 'unresolved')
        self.assertEqual(result.aliases[1]['reason'], 'aoi_alias_target_not_local')

    def test_never_resolves_between_distinct_controllers(self) -> None:
        raw = ('<RSLogix5000Content><Controller Name="One"><Tags>' + tag('OnlyOne') +
               '</Tags></Controller><Controller Name="Two"><Programs>' +
               program('XIC(OnlyOne);') + '</Programs></Controller></RSLogix5000Content>')
        result = analyze_references(analyze_snapshot(snapshot_from_bytes(raw.encode())))
        self.assertEqual(result.operands[0]['status'], 'unresolved')

    def test_direct_members_module_roots_and_static_arrays_bind_only_root(self) -> None:
        result = analyze(tag('Local:1:I') + tag('Array') + tag('Struct'),
                         'XIC(Local:1:I.Data.0)MOV(Array[1, 2],Struct.NotDeclared[999].7);')
        self.assertEqual([row['status'] for row in result.operands], ['root_bound'] * 3)
        self.assertEqual([row['suffix'] for row in result.operands],
                         ['.Data.0', '[1, 2]', '.NotDeclared[999].7'])
        self.assertEqual(result.member_validation, 'not_implemented')

    def test_dynamic_indices_qualifications_and_bad_addresses_remain_opaque(self) -> None:
        result = analyze(tag('Array') + tag('Index') + tag('A'),
                         r'XIC(Array[Index])XIC(Program:P.A)XIC(\P.A)'
                         'XIC(A + Index)XIC(Array[-1])XIC(A..Field)XIC(A.1.Field);')
        self.assertTrue(all(row['status'] == 'unsupported_address' for row in result.operands))
        self.assertTrue(all(row['symbol_id'] is None for row in result.operands))
        self.assertEqual(result.operands[0]['raw_text'], 'Array[Index]')
        self.assertEqual([row['reason'] for row in result.operands], [
            'non_static_array_index', 'program_qualified_address',
            'backslash_qualified_address', 'malformed_address', 'malformed_address',
            'malformed_address', 'malformed_address',
        ])

    def test_dynamic_index_reason_requires_complete_recognizable_bracket_expression(self) -> None:
        dynamic = ['Array[Index + 1]', 'Array[(Index + 1) * 2]',
                   'Array[1, Index.Member]', 'Array[1+2]']
        malformed = ['Array[]', 'Array[Index +]', 'Array[1,,2]',
                     'Array[Index) + 1]', 'Array[Index]Extra', 'Array[-1]']
        # Build captured occurrences directly for delimiter-malformed addresses;
        # the ladder parser rightly rejects some of these before binding.
        source = inventory(tag('Array'), program('XIC(Array);'))
        instruction = source.rungs[0].instructions[0]
        for address, reason in [(x, 'non_static_array_index') for x in dynamic] + [
                (x, 'malformed_address') for x in malformed]:
            with self.subTest(address=address):
                rung = replace(source.rungs[0], instructions=[replace(
                    instruction, arguments=(address,))])
                result = analyze_references(replace(source, rungs=[rung]))
                self.assertEqual(result.operands[0]['status'], 'unsupported_address')
                self.assertEqual(result.operands[0]['reason'], reason)

    def test_alias_failure_reasons_describe_terminal_target_not_caller(self) -> None:
        result = analyze(tag('First', 'Second') + tag('Second', 'Absent:I.Data') +
                         tag('Indirect', 'Array[Index]') +
                         tag('EmptyTarget', '') + tag('AbsentPlain', 'Gone'),
                         'XIC(First)XIC(Indirect)XIC(EmptyTarget)XIC(AbsentPlain);')
        self.assertEqual([row['reason'] for row in result.operands], [
            'colon_root_not_declared', 'non_static_array_index', 'empty_address',
            'root_not_declared',
        ])
        alias = next(row for row in result.aliases
                     if row['source_id'] == named(result, 'First')['id'])
        self.assertEqual(alias['reason'], 'colon_root_not_declared')
        self.assertEqual(result.operands[0]['symbol_id'], named(result, 'First')['id'])

    def test_invalid_scope_is_distinct_from_missing_root(self) -> None:
        source = inventory(tag('A'), program('XIC(A);'))
        rung = replace(source.rungs[0], scope_id='not_a_scope')
        result = analyze_references(replace(source, rungs=[rung]))
        self.assertEqual(result.operands[0]['status'], 'unresolved')
        self.assertEqual(result.operands[0]['reason'], 'invalid_scope')

    def test_long_addresses_have_fixed_length_reason_and_other_statuses_no_reason(self) -> None:
        with patch('plc_workbench.references.MAX_ADDRESS_LENGTH', 5):
            result = analyze(tag('A'), 'XIC(TooLong)XIC(A)MOV(1,A)JMP(Label)Custom(A);')
        self.assertEqual(result.operands[0]['reason'], 'address_length_limit')
        self.assertTrue(all(row['reason'] is None for row in result.operands[1:]))

    def test_numeric_and_string_literals_never_create_symbol_edges(self) -> None:
        values = ['-1', '+1.5E-2', '.25', '2#1010_0101', '8#77', '16#A0_FF',
                  "'fiction'", "'it$'s synthetic'", '"double"', "'double''quote'"]
        result = analyze(tag('Dest'), ''.join(f'MOV({value},Dest)' for value in values) + ';')
        for row in result.operands[::2]:
            self.assertEqual(row['status'], 'literal', row['raw_text'])
            self.assertIsNone(row['symbol_id'])
            self.assertIsNone(row['target_id'])
        self.assertTrue(all(row['status'] == 'root_bound' for row in result.operands[1::2]))

    def test_expressions_unknown_opcodes_and_metadata_never_guess_tag_mentions(self) -> None:
        result = analyze(tag('Known') + tag('Label'),
                         'CPT(Known,Known + 1)PrivateAOI(Known)JSR(Known,0)'
                         'GSV(Known,Known,Known,Known)LBL(Label)JMP(Label);')
        self.assertEqual([row['status'] for row in result.operands],
                         ['root_bound', 'unsupported_expression', 'unsupported_instruction',
                          'unsupported_instruction', 'unsupported_instruction',
                          *(['unsupported_instruction'] * 4), 'non_data', 'non_data'])
        self.assertTrue(all(row['symbol_id'] is None for row in result.operands[1:]))

    def test_arity_mismatches_empty_slots_and_zero_argument_instructions_count_as_gaps(self) -> None:
        result = analyze(tag('A'), 'XIC(A,A)ADD(A,,A)MOV()Unknown();')
        self.assertEqual([row['status'] for row in result.operands],
                         ['argument_count_mismatch', 'argument_count_mismatch',
                          'root_bound', 'empty', 'root_bound'])
        self.assertEqual(result.coverage['instructions_total'], 4)
        self.assertEqual(result.coverage['instructions_catalogued'], 1)
        self.assertEqual(result.coverage['operands_total'], 5)
        self.assertEqual(result.status, 'partial')

    def test_occurrences_determinism_snapshot_change_and_no_source_mutation(self) -> None:
        source = inventory(tag('A'), program('ADD(A,A,A)XIC(A);'))
        before = source.to_dict()
        first = analyze_references(source)
        second = analyze_references(source)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(source.to_dict(), before)
        self.assertEqual(len({row['id'] for row in first.operands}), 4)
        self.assertEqual([row['argument_index'] for row in first.operands], [0, 1, 2, 0])
        changed = inventory(tag('A'), program('ADD(A,A,A)XIC(A);'), '<Extra/>')
        self.assertTrue({row['id'] for row in first.operands}.isdisjoint(
            {row['id'] for row in analyze_references(changed).operands}))
        detached = first.to_dict()
        detached['symbols'][0]['attributes']['Name'] = 'Changed'
        self.assertEqual(first.symbols[0]['attributes']['Name'], 'A')

    def test_unnamed_and_unnameable_symbols_are_explicit_even_when_unused(self) -> None:
        result = analyze('<Tag TagType="Base"/>' + tag('contains space'), ';')
        self.assertEqual(result.coverage['unnamed_symbols'], 2)
        self.assertEqual(len(result.symbols), 2)
        self.assertEqual(result.status, 'partial')

    def test_failed_rungs_are_not_counted_as_analyzed(self) -> None:
        source = inventory(tag('A'), program('XIC(A);', name='Good') + program('XIC(A)', name='Bad'))
        result = analyze_references(source)
        self.assertEqual(result.coverage['rungs_total'], 2)
        self.assertEqual(result.coverage['rungs_analyzed'], 1)
        self.assertEqual(result.coverage['source_status'], 'partial')
        self.assertEqual(result.coverage['operands_total'], 1)

    def test_operand_budget_fails_with_fixed_safe_message(self) -> None:
        source = inventory(tag('PRIVATE_NAME'), program('ADD(PRIVATE_NAME,1,PRIVATE_NAME);'))
        with patch('plc_workbench.references.MAX_OPERANDS', 2):
            with self.assertRaisesRegex(ReferenceError, '^Reference analysis exceeds the operand limit[.]$'):
                analyze_references(source)
        with patch('plc_workbench.references.MAX_OPERANDS', 3):
            self.assertEqual(len(analyze_references(source).operands), 3)
        with self.assertRaisesRegex(ReferenceError, '^Unsupported source inventory version[.]$'):
            analyze_references(replace(source, parser_version='PRIVATE_NAME'))

    def test_repeated_alias_evidence_has_a_global_budget(self) -> None:
        source = inventory(tag('PRIVATE_BASE') + tag('PRIVATE_ALIAS', 'PRIVATE_BASE.Member'),
                           program('XIC(PRIVATE_ALIAS)XIC(PRIVATE_ALIAS);'))
        result = analyze_references(source)
        one_record = len(result.aliases[0]['alias_chain'][0]) + len('.Member')
        with patch('plc_workbench.references.MAX_EXPANDED_EVIDENCE_CHARS', one_record * 3):
            self.assertEqual(analyze_references(source).status, 'complete')
        with patch('plc_workbench.references.MAX_EXPANDED_EVIDENCE_CHARS', one_record * 3 - 1):
            with self.assertRaisesRegex(ReferenceError, '^Reference analysis exceeds the expanded-evidence limit[.]$'):
                analyze_references(source)

    def test_catalogued_timer_pid_and_copy_slots_only_bind_roots(self) -> None:
        result = analyze(''.join(tag(name) for name in ['Timer', 'Loop', 'PV', 'CV', 'Data', 'Out']),
                         'TON(Timer,1000,0)TOF(Timer,0,0)RTO(Timer,0,0)RES(Timer)'
                         'OSR(Data.0,Out)OSF(Data.1,Out)COP(Data[0],Out,1)CPS(Data[1],Out,1)'
                         'PID(Loop,PV,0,CV,0,0,0);')
        self.assertEqual(result.coverage['instructions_catalogued'], 9)
        self.assertEqual(result.status, 'complete')
        self.assertEqual([row['status'] for row in result.operands[-7:]],
                         ['root_bound', 'root_bound', 'literal', 'root_bound',
                          'literal', 'literal', 'literal'])
        self.assertEqual(result.effect_analysis, 'not_implemented')
        mismatch = analyze(tag('Loop'), 'PID(Loop);')
        self.assertEqual(mismatch.operands[0]['status'], 'argument_count_mismatch')
        self.assertIsNone(mismatch.operands[0]['symbol_id'])

    def test_alias_expansion_budget_keeps_raw_evidence_and_prevents_complete_binding(self) -> None:
        with patch('plc_workbench.references.MAX_ADDRESS_LENGTH', 12):
            result = analyze(tag('B') + tag('A', 'B.Member'), 'XIC(A.Member);')
        self.assertEqual(result.operands[0]['status'], 'unsupported_address')
        self.assertEqual(result.operands[0]['raw_text'], 'A.Member')
        self.assertIsNone(result.operands[0]['target_id'])
        self.assertEqual(result.operands[0]['reason'], 'expanded_suffix_limit')

    def test_independently_authored_fixture_known_bindings(self) -> None:
        source = analyze_snapshot(snapshot_from_bytes(FIXTURE.read_bytes()))
        result = analyze_references(source)
        self.assertEqual(len(result.symbols), 15)
        self.assertEqual(len(result.aliases), 1)
        self.assertEqual(result.aliases[0]['status'], 'root_bound')
        self.assertEqual(result.coverage['rungs_analyzed'], 9)
        self.assertEqual(result.coverage['instructions_total'], 25)
        self.assertEqual(result.coverage['instructions_catalogued'], 24)
        self.assertEqual(result.coverage['operands_total'], 30)
        aliases = [row for row in result.operands if row['raw_text'] == 'RunAlias']
        self.assertEqual(aliases[0]['target_id'], named(result, 'Run')['id'])
        local = [row for row in result.operands if row['raw_text'] == 'LocalSignal']
        self.assertEqual(len(local), 3)
        self.assertEqual(len({row['target_id'] for row in local}), 2)
        self.assertEqual(result.status, 'partial')

    def test_canonical_validation_uses_captured_inventory_without_source_io(self) -> None:
        source = inventory(tag('Base') + tag('Alias', 'Base.Member'), program('XIC(Alias);'))
        result = analyze_references(source)
        before = result.to_dict()
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('unexpected source read')):
            self.assertIsNone(validate_references(source, result))
        self.assertEqual(result.to_dict(), before)

    def test_validation_rejects_changed_links_evidence_statuses_and_counts(self) -> None:
        source = inventory(tag('Base') + tag('Alias', 'Base.Member'), program('XIC(Alias);'))
        result = analyze_references(source)
        changes = [
            (('operands', 0, 'target_id'), 'tag_wrong_snapshot'),
            (('operands', 0, 'symbol_id'), None),
            (('operands', 0, 'alias_chain', 0), 'tag_wrong_snapshot'),
            (('operands', 0, 'raw_text'), 'PRIVATE_WRONG_TEXT'),
            (('operands', 0, 'suffix'), '.WrongMember'),
            (('operands', 0, 'status'), 'literal'),
            (('operands', 0, 'reason'), 'root_not_declared'),
            (('operands', 0, 'argument_index'), False),
            (('aliases', 0, 'raw_target'), 'PRIVATE_WRONG_TARGET'),
            (('aliases', 0, 'target_id'), 'tag_wrong_snapshot'),
            (('aliases', 0, 'alias_chain'), []),
            (('aliases', 0, 'reason'), 'PRIVATE_INVENTED_REASON'),
            (('symbols', 0, 'attributes', 'DataType'), 'BOOL'),
            (('symbols', 0, 'name_origin'), 'module_name'),
            (('symbols', 0, 'name_reason'), 'PRIVATE_INVENTED_REASON'),
            (('coverage', 'operands_total'), 1.0),
            (('snapshot', 'id'), 'sha256:wrong_snapshot'),
        ]
        for path, value in changes:
            with self.subTest(path=path):
                changed = deepcopy(result)
                container = vars(changed)
                for key in path[:-1]:
                    container = container[key]
                container[path[-1]] = value
                with self.assertRaisesRegex(ReferenceError, '^Reference records do not match the source inventory[.]$'):
                    validate_references(source, changed)

    def test_validation_rejects_wrong_metadata_and_record_shapes(self) -> None:
        source = inventory(tag('A'), program('XIC(A);'))
        result = analyze_references(source)
        changes = [
            {'schema_version': True}, {'analyzer_version': 'PRIVATE_UNKNOWN_VERSION'},
            {'analyzer_version': 'source-references-2'},
            {'semantic_analysis': 'implemented'}, {'effect_analysis': 'implemented'},
            {'member_validation': 'implemented'}, {'analysis_scope': 'everything'},
            {'status': 'partial'}, {'operands': tuple(result.operands)},
            {'symbols': None},
        ]
        for change in changes:
            with self.subTest(field=next(iter(change))):
                with self.assertRaisesRegex(ReferenceError, '^Reference records do not match the source inventory[.]$'):
                    validate_references(source, replace(result, **change))
        # A lookalike publisher object must not execute its custom serializer.
        class Payload:
            def to_dict(self):
                raise AssertionError('untrusted serializer executed')

        with self.assertRaises(ReferenceError):
            validate_references(source, Payload())

    def test_validation_handles_cyclic_records_and_custom_scalars_safely(self) -> None:
        source = inventory(tag('A'), program('XIC(A);'))
        result = analyze_references(source)
        cyclic = deepcopy(result)
        cyclic.operands[0]['alias_chain'] = cyclic.operands
        with self.assertRaisesRegex(ReferenceError, '^Reference records do not match the source inventory[.]$'):
            validate_references(source, cyclic)

        class UntrustedInt(int):
            def __eq__(self, other):
                raise AssertionError('untrusted equality executed')

        changed = deepcopy(result)
        changed.operands[0]['argument_index'] = UntrustedInt(0)
        with self.assertRaises(ReferenceError):
            validate_references(source, changed)

    def test_validation_rejects_extra_fields_and_records_from_another_snapshot(self) -> None:
        source = inventory(tag('A'), program('XIC(A);'))
        result = analyze_references(source)
        other = inventory(tag('A'), program('XIC(A);'), '<Extra/>')
        with self.assertRaises(ReferenceError):
            validate_references(other, result)
        result.operands[0]['unexpected_field'] = 'PRIVATE_EXTRA_VALUE'
        with self.assertRaises(ReferenceError):
            validate_references(source, result)


if __name__ == '__main__':
    unittest.main()
