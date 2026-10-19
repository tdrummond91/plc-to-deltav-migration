"""Invented source exercises structural candidates without execution claims."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access, render_access_json
from plc_workbench.calculations import analyze_calculations, render_calculation_json
from plc_workbench.references import analyze_references
from plc_workbench.rung_analysis import (
    RungAnalysisError, analyze_rungs, render_rung_analysis_json, validate_rung_analysis,
)
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def capture(texts: tuple[str, ...] = ('XIC(A)OTE(D);',), *, tags: str | None = None,
            rung_xml: str | None = None, modules: str = ''):
    if tags is None:
        tags = ''.join(f'<Tag Name="{name}" TagType="Base" DataType="DINT"/>' for name in ('A', 'B', 'C', 'D', 'T'))
    rungs = rung_xml if rung_xml is not None else ''.join(
        f'<Rung Number="{i}" Type="N"><Text><![CDATA[{text}]]></Text></Rung>' for i, text in enumerate(texts))
    xml = (f'<RSLogix5000Content><Controller Name="Invented"><Tags>{tags}</Tags>{modules}<Programs>'
           f'<Program Name="P"><Routines><Routine Name="R" Type="RLL"><RLLContent>{rungs}</RLLContent>'
           '</Routine></Routines></Program></Programs></Controller></RSLogix5000Content>')
    snapshot = snapshot_from_bytes(xml.encode())
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    calculations = analyze_calculations(snapshot, inventory, references)
    access = analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
    result = analyze_rungs(snapshot, inventory, references, access, calculations)
    return snapshot, inventory, references, access, calculations, result


def rules(result, rung_index: int = 0) -> set[str]:
    ids = result.rungs[rung_index]['candidate_ids']
    return {c['rule_id'] for c in result.candidates if c['id'] in ids}


class RungAnalysisTests(unittest.TestCase):
    def test_series_output_motif_retains_each_block_and_slot(self) -> None:
        inputs = capture(('XIC(A)XIO(B)OTE(D);',))
        result = inputs[-1]
        rung = result.rungs[0]
        self.assertEqual((rung['structure'], rung['identification']), ('series', 'identified'))
        self.assertEqual(rung['block_ids'], [i.id for i in inputs[1].rungs[0].instructions])
        self.assertEqual(rung['first_block_ids'], rung['block_ids'][:1])
        self.assertEqual(rung['last_block_ids'], rung['block_ids'][-1:])
        self.assertEqual(rung['result_kind'], 'single_known_result')
        self.assertEqual(len(rung['operand_ids_by_role']['read']), 2)
        self.assertIn('boolean_assign', rules(result))
        self.assertTrue(all(c['review_status'] == 'unreviewed' for c in result.candidates))
        validate_rung_analysis(*inputs[:-1], result)

    def test_parallel_contacts_rejoin_before_single_output(self) -> None:
        *_, result = capture(('[XIC(A),XIO(B)]OTE(D);',))
        rung = result.rungs[0]
        self.assertEqual(rung['first_block_ids'], rung['block_ids'][:2])
        self.assertEqual(rung['last_block_ids'], rung['block_ids'][2:])
        self.assertEqual((rung['branch_count'], rung['branch_legs'], rung['empty_legs']), (1, 2, 0))
        self.assertIn('boolean_assign', rules(result))

    def test_nullable_suffix_keeps_preceding_terminal_in_source_order(self) -> None:
        *_, result = capture(('XIC(A)[XIO(B),];', 'XIC(A)[,];', '[,XIC(A)]XIO(B)[XIC(C),];'))
        a, b, c = result.rungs
        self.assertEqual(a['last_block_ids'], a['block_ids'])
        self.assertEqual(b['last_block_ids'], b['block_ids'])
        self.assertEqual(c['first_block_ids'], c['block_ids'][:2])
        self.assertEqual(c['last_block_ids'], c['block_ids'][1:])
        self.assertEqual(a['empty_legs'], 1)
        self.assertFalse(a['nullable'])

    def test_output_bypass_and_trailing_contact_do_not_claim_boolean_motif(self) -> None:
        *_, result = capture(('[XIC(A)OTE(D),];', 'OTE(D)XIC(A);', '[OTE(D),XIC(A)];'))
        for index in range(3):
            self.assertNotIn('boolean_assign', rules(result, index))
        self.assertTrue(result.rungs[0]['nullable'])
        self.assertEqual(result.rungs[0]['result_kind'], 'single_known_result')

    def test_latch_and_unlatch_are_distinct_and_stateful(self) -> None:
        *_, result = capture(('XIC(A)OTL(D);', 'XIC(A)OTU(D);'))
        self.assertIn('boolean_latch', rules(result, 0))
        self.assertIn('boolean_unlatch', rules(result, 1))
        self.assertEqual([r['result_kind'] for r in result.rungs], ['stateful_or_external'] * 2)

    def test_each_rung_and_parsed_instruction_including_empty_and_unparsed(self) -> None:
        *_, result = capture((';', '[,];', 'XIC(A', 'Mystery(A);'))
        self.assertEqual([r['structure'] for r in result.rungs], ['empty', 'branched', 'unparsed', 'series'])
        self.assertEqual([r['identification'] for r in result.rungs], ['empty', 'empty', 'unparsed', 'unidentified'])
        self.assertEqual(len(result.blocks), 1)
        self.assertEqual(result.coverage['unknown_blocks'], 1)
        self.assertEqual(result.coverage['source_rungs'], 4)

    def test_result_addresses_preserve_same_root_different_suffixes(self) -> None:
        *_, result = capture(('MOV(A,D.Left)MOV(B,D.Right);', 'MOV(A,D.Left)MOV(B,D.Left);'))
        self.assertEqual([r['result_kind'] for r in result.rungs], ['multiple_known_results', 'single_known_result'])
        self.assertEqual(len(result.rungs[1]['result_operand_ids']), 2)

    def test_unknown_blocks_and_known_mnemonic_are_not_promoted_to_roles(self) -> None:
        *_, result = capture(('XIC(A)Mystery(D)OTE(D);', 'ALMD(A);', 'AVE(A,B,C);'))
        self.assertEqual(result.rungs[0]['identification'], 'partial')
        self.assertNotIn('boolean_assign', rules(result))
        self.assertEqual(result.rungs[1]['identification'], 'unidentified')
        self.assertEqual(result.blocks[3]['identification'], 'known_mnemonic')
        alarms = [c for c in result.candidates if c['category'] == 'alarm']
        self.assertEqual(alarms[0]['basis'], 'known_mnemonic')
        self.assertIn('instruction_effects_not_analyzed', alarms[0]['missing_evidence'])

    def test_pid_signature_is_recognized_without_effects_or_loop_config(self) -> None:
        *_, result = capture(('PID(A,B,C,D,0,0,0);', 'PID(A,B);', 'PID(A,B,,D,0,0,0);'))
        self.assertEqual([b['identification'] for b in result.blocks], ['signature_known', 'unknown', 'unknown'])
        self.assertIn('pid_control_instruction_signature', rules(result))
        self.assertEqual(result.rungs[0]['operand_ids_by_role']['unknown'], result.blocks[0]['operand_ids'])
        self.assertEqual(result.rungs[0]['result_kind'], 'stateful_or_external')
        self.assertEqual(result.rungs[1]['result_kind'], 'no_known_result')
        self.assertNotIn('pid_control_instruction_signature', rules(result, 1))

    def test_cpt_reads_separate_from_source_slots_and_whole_unsupported_expression(self) -> None:
        *_, result = capture(('CPT(D,A+A*B);', 'CPT(D,A+);', 'CPT(D,Missing+A);'))
        one, two, three = result.rungs
        self.assertEqual(len(one['expression_use_ids']), 3)
        self.assertEqual(len(one['operand_ids_by_role']['expression_read']), 1)
        self.assertEqual(one['operand_ids_by_role']['read'], [])
        self.assertEqual(two['expression_use_ids'], [])
        self.assertEqual(two['identification'], 'partial')
        self.assertEqual(len(three['expression_gap_use_ids']), 1)
        self.assertEqual(result.coverage['source_operands'], 6)
        self.assertEqual(result.coverage['expression_uses'], 5)

    def test_unbound_write_keeps_gap_and_no_execution_output_claim(self) -> None:
        *_, result = capture(('XIC(A)OTE(Missing);', 'XIC(A);'))
        self.assertEqual(result.rungs[0]['identification'], 'partial')
        self.assertEqual(len(result.rungs[0]['access_gap_operand_ids']), 1)
        self.assertEqual(result.rungs[0]['result_kind'], 'no_known_result')
        self.assertEqual(result.rungs[1]['result_kind'], 'no_known_result')
        self.assertNotIn('dead', render_rung_analysis_json(result).lower())

    def test_unresolved_results_do_not_invent_distinct_known_addresses(self) -> None:
        *_, result = capture(('MOV(A,Missing)MOV(B,Missing);',
                              'MOV(A,D)MOV(B,Missing);', 'CPT(12,A+A);'))
        self.assertEqual([r['result_kind'] for r in result.rungs],
                         ['no_known_result', 'single_known_result', 'no_known_result'])
        self.assertEqual([len(r['result_operand_ids']) for r in result.rungs], [2, 2, 1])
        self.assertEqual([len(r['access_gap_operand_ids']) for r in result.rungs], [2, 1, 1])

    def test_comments_ambiguity_and_missing_metadata_explicit_without_text_copies(self) -> None:
        xml = ('<Rung><Text>OTE(D);</Text><Comment>alarm invented</Comment></Rung>'
               '<Rung Number="1" Type="N"><Text>OTE(D);</Text><Comment>a</Comment><Comment>b</Comment></Rung>'
               '<Rung Number="2" Type="N"><Text>OTE(D);</Text><Comment> </Comment></Rung>')
        *_, result = capture(rung_xml=xml)
        self.assertEqual([r['comment_status'] for r in result.rungs], ['present', 'ambiguous', 'absent'])
        self.assertEqual(result.rungs[0]['missing_metadata'], ['number', 'type'])
        self.assertIn('alarm_text_hint', rules(result))
        self.assertNotIn('alarm invented', render_rung_analysis_json(result))

    def test_text_hints_are_weak_whole_words_with_original_source_ids(self) -> None:
        tags = ('<Tag Name="ALARM_PUMP" TagType="Base" DataType="DINT"/>'
                '<Tag Name="Pumpkin" TagType="Base" DataType="DINT"/>')
        inputs = capture(('OTE(ALARM_PUMP);', 'OTE(Pumpkin);'), tags=tags)
        result = inputs[-1]
        hints = [c for c in result.candidates if c['basis'] == 'text_hint']
        self.assertEqual({c['category'] for c in hints}, {'alarm', 'equipment'})
        entity = next(e for e in inputs[1].entities if e.name == 'ALARM_PUMP')
        self.assertTrue(all(c['evidence_ids'] == [entity.id] for c in hints))
        self.assertTrue(all('name_or_comment_is_not_behavior' in c['missing_evidence'] for c in hints))
        self.assertNotIn('equipment_text_hint', rules(result, 1))

    def test_io_candidates_require_declared_module_roots(self) -> None:
        modules = ('<Modules><Module Name="M"><Communications><Connections><Connection Name="C">'
                   '<InputTag Name="M:I"/><OutputTag Name="M:O"/>'
                   '</Connection></Connections></Communications></Module></Modules>')
        *_, result = capture(('XIC(M:I.Data.0)OTE(M:O.Data.0);', 'OTE(D);'), modules=modules)
        self.assertIn('io_input_module_root', rules(result))
        self.assertIn('io_output_module_root', rules(result))
        self.assertNotIn('io_output_module_root', rules(result, 1))

    def test_declared_pid_structure_suggests_loop_logic_without_pid_execution(self) -> None:
        tags = ('<Tag Name="Loop" TagType="Base" DataType="PID"/>'
                '<Tag Name="D" TagType="Base" DataType="REAL"/>')
        *_, result = capture(('MOV(Loop.SP,D);', 'PID(Loop,D,0,D,0,0,0);'), tags=tags)
        self.assertIn('pid_declared_structure', rules(result))
        self.assertNotIn('pid_declared_structure', rules(result, 1))
        candidate = next(c for c in result.candidates if c['rule_id'] == 'pid_declared_structure')
        self.assertEqual(candidate['basis'], 'declaration_type')
        self.assertIn('pid_execution_not_established', candidate['missing_evidence'])
        self.assertEqual(result.blocks[0]['family'], 'data_transfer')
        self.assertEqual(result.rungs[0]['result_kind'], 'single_known_result')

    def test_original_companions_stay_byte_identical(self) -> None:
        inputs = capture(('CPT(D,A+A);',))
        before = render_access_json(inputs[3]), render_calculation_json(inputs[4])
        repeated = analyze_rungs(*inputs[:-1])
        self.assertEqual(render_rung_analysis_json(repeated), render_rung_analysis_json(inputs[-1]))
        self.assertEqual(before, (render_access_json(inputs[3]), render_calculation_json(inputs[4])))

    def test_forged_snapshot_inventory_access_and_calculations_rejected(self) -> None:
        inputs = capture()
        mutations = (
            (0, lambda x: replace(x, data=x.data + b' ')),
            (1, lambda x: replace(x, rungs=[])),
            (3, lambda x: replace(x, schema_version=3)),
            (4, lambda x: replace(x, schema_version=1)),
        )
        for index, mutate in mutations:
            args = list(inputs[:-1])
            args[index] = mutate(args[index])
            with self.subTest(index=index), self.assertRaises(RungAnalysisError):
                analyze_rungs(*args)

    def test_canonical_replay_rejects_candidate_frontier_and_count_changes(self) -> None:
        inputs = capture()
        mutations = (
            lambda r: r.rungs[0]['last_block_ids'].reverse(),
            lambda r: r.rungs[0].update(nullable=True),
            lambda r: r.candidates[0].update(basis='text_hint'),
            lambda r: r.coverage.update(source_rungs=99),
            lambda r: r.blocks.reverse(),
        )
        for mutate in mutations[1:]:  # one terminal reversed is unchanged
            candidate = deepcopy(inputs[-1])
            mutate(candidate)
            with self.subTest(mutation=mutate), self.assertRaises(RungAnalysisError):
                validate_rung_analysis(*inputs[:-1], candidate)

    def test_incremental_record_link_text_and_render_limits(self) -> None:
        inputs = capture()
        for key, value in (('MAX_RECORDS', 1), ('MAX_EVIDENCE_IDS', 1), ('MAX_RUNG_ANALYSIS_BYTES', 500), ('MAX_HINT_CHARACTERS', 1)):
            with self.subTest(limit=key), patch('plc_workbench.rung_analysis.' + key, value), self.assertRaises(RungAnalysisError):
                analyze_rungs(*inputs[:-1])

    def test_custom_hooks_cycles_and_extra_fields_rejected_before_serialization(self) -> None:
        class Hostile:
            def __deepcopy__(self, memo):
                raise AssertionError('hook invoked')
            def __eq__(self, other):
                raise AssertionError('hook invoked')
        inputs = capture()
        result = inputs[-1]
        for value in (Hostile(), {'custom': Hostile()}):
            candidate = replace(result, coverage=value)
            with self.assertRaises(RungAnalysisError):
                candidate.to_dict()
        cycle = []
        cycle.append(cycle)
        with self.assertRaises(RungAnalysisError):
            render_rung_analysis_json(replace(result, rungs=cycle))
        vars(result)['extra'] = 'unrecognized'
        with self.assertRaises(RungAnalysisError):
            render_rung_analysis_json(result)


if __name__ == '__main__':
    unittest.main()
