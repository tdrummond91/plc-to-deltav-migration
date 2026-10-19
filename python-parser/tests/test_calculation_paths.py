"""Invented ladder cases challenge static source-region and identity boundaries."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access, render_access_json
from plc_workbench.calculation_paths import (CalculationPathError, analyze_calculation_paths,
    render_calculation_paths_json, validate_calculation_paths)
from plc_workbench.calculations import analyze_calculations
from plc_workbench.conditions import analyze_conditions, render_conditions_json
from plc_workbench.references import analyze_references
from plc_workbench.relationships import analyze_relationships, render_relationships_json
from plc_workbench.rung_analysis import analyze_rungs
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from test_relationships import capture as capture_relationships, tag


def capture(texts=('MOV(A,B)ADD(B,1,C);',), **kwargs):
    args = capture_relationships(texts, **kwargs)
    conditions = analyze_conditions(*args, schema_version=3)
    return (*args, conditions, analyze_calculation_paths(*args, conditions))


def capture_xml(xml: str):
    snapshot = snapshot_from_bytes(xml.encode())
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    calculations = analyze_calculations(snapshot, inventory, references)
    access = analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
    rungs = analyze_rungs(snapshot, inventory, references, access, calculations)
    relationships = analyze_relationships(snapshot, inventory, references, access, calculations, rungs)
    args = (snapshot, inventory, references, access, calculations, rungs, relationships)
    conditions = analyze_conditions(*args, schema_version=3)
    return (*args, conditions, analyze_calculation_paths(*args, conditions))


class CalculationPathTests(unittest.TestCase):
    def test_series_links_keep_exact_existing_ids_and_older_companions(self) -> None:
        args = capture()
        result = args[-1]
        originals = (render_access_json(args[3]), render_relationships_json(args[6]), render_conditions_json(args[7]))
        self.assertEqual(result.coverage['links_total'], 1)
        self.assertEqual(result.coverage['regions_total'], 1)
        self.assertEqual(result.status, 'complete')
        producer, consumer = result.occurrences
        link = result.links[0]
        self.assertEqual(link['producer_instruction_id'], producer['id'])
        self.assertEqual(link['consumer_instruction_id'], consumer['id'])
        self.assertEqual(link['address_id'], producer['destination_address_id'])
        self.assertEqual(link['write_operand_id'], producer['destination_operand_id'])
        self.assertIn(link['read_id'], consumer['input_operand_ids'])
        self.assertEqual(link['region_id'], producer['region_id'])
        self.assertEqual(link['region_id'], consumer['region_id'])
        validate_calculation_paths(*args)
        self.assertEqual(json.loads(render_calculation_paths_json(result)), result.to_dict())
        self.assertEqual(originals, (render_access_json(args[3]), render_relationships_json(args[6]), render_conditions_json(args[7])))

    def test_nested_sibling_legs_and_join_never_reuse_external_writer(self) -> None:
        args = capture(('MOV(A,B)[ADD(B,1,C)MOV(C,D),MOV(A,B)[MOV(B,C)ADD(C,1,D),MOV(B,C)ADD(C,1,D)]ADD(D,1,C)]ADD(B,1,C);',))
        result = args[-1]
        self.assertEqual(len(result.links), 3)
        blocks = {row['id']: row for row in result.occurrences}
        for link in result.links:
            left, right = (blocks[link[key]] for key in ('producer_instruction_id', 'consumer_instruction_id'))
            self.assertEqual(left['region_id'], right['region_id'])
            self.assertGreater(left['branch_depth'], 0)
        self.assertNotIn(result.occurrences[0]['id'], {link['producer_instruction_id'] for link in result.links})
        self.assertNotIn(result.occurrences[-1]['id'], {link['consumer_instruction_id'] for link in result.links})
        self.assertEqual(result.coverage['branched_regions'], 5)
        self.assertEqual(result.coverage['region_blocks_total'], len(result.occurrences))

    def test_empty_bypass_and_repeated_rungs_are_hard_boundaries(self) -> None:
        args = capture(('MOV(A,B)[,]ADD(B,1,C);', 'ADD(B,1,D);'))
        result = args[-1]
        self.assertEqual(len(result.occurrences), 3)
        self.assertEqual(result.links, [])
        self.assertEqual(len(result.regions), 3)
        self.assertEqual(result.regions[0]['end_reason'], 'branch_fork')
        self.assertEqual(result.regions[1]['start_reason'], 'branch_join')

    def test_predicates_preserve_region_but_change_incoming_context(self) -> None:
        result = capture(('MOV(A,B)XIC(D)EQU(A,1)ADD(B,1,C);',))[-1]
        self.assertEqual(result.coverage['preserved_predicates'], 2)
        self.assertEqual(len(result.regions), 1)
        self.assertEqual(len(result.links), 1)
        link = result.links[0]
        self.assertNotEqual(link['producer_condition_id'], link['consumer_condition_id'])
        self.assertEqual(result.condition_usage, 'incoming_context_not_write_guard')
        self.assertEqual(result.reaching_definitions, 'not_implemented')

    def test_unbound_predicate_is_barrier_and_context_keeps_binding_gap(self) -> None:
        result = capture(('MOV(A,B)XIC(Missing)ADD(B,1,C)MOV(C,D);',))[-1]
        self.assertEqual(result.coverage['preserved_predicates'], 0)
        self.assertEqual(result.coverage['barriers_by_reason']['unresolved_operand'], 1)
        self.assertEqual(len(result.links), 1)
        self.assertEqual(result.occurrences[1]['condition_quality'], 'binding_gaps')
        self.assertEqual(result.occurrences[1]['status'], 'eligible')
        self.assertEqual(result.status, 'partial')

    def test_same_root_suffix_or_whole_owner_overwrites_prior_memory(self) -> None:
        for middle in ('MOV(A,B.Y)', 'MOV(A,B)', 'MOV(A,B.x)'):
            with self.subTest(middle=middle):
                result = capture((f'MOV(A,B.X){middle}ADD(B.X,1,C);',))[-1]
                self.assertEqual(result.links, [])
                self.assertEqual(result.coverage['overlap_invalidations'], 1)
        result = capture(('MOV(A,B.X)MOV(A,D)ADD(B.X,1,C);',))[-1]
        self.assertEqual(len(result.links), 1)

    def test_unknown_calls_coils_timers_and_stateful_blocks_are_barriers(self) -> None:
        for middle in ('MYSTERY(A)', 'JSR(Target,0)', 'OTE(D)', 'TON(T,1,0)', 'ONS(D)', 'COP(A,B,1)'):
            with self.subTest(middle=middle):
                result = capture((f'MOV(A,B){middle}ADD(B,1,C)MOV(C,D);',))[-1]
                self.assertEqual(result.coverage['barriers_by_reason']['other_instruction'], 1)
                self.assertEqual(len(result.links), 1)
                self.assertEqual(result.links[0]['producer_instruction_id'], result.occurrences[1]['id'])
                self.assertEqual(result.occurrences[1]['status'], 'eligible')
        result = capture(('MYSTERY(A)MOV(A,B)MOV(B,C);',))[-1]
        self.assertEqual(result.coverage['condition_quality']['opaque'], 2)
        self.assertEqual(len(result.links), 1)
        result = capture(('ONS(D)MOV(A,B)MOV(B,C);',))[-1]
        self.assertEqual(result.coverage['condition_quality']['stateful'], 2)

    def test_aliases_share_only_valid_exact_final_identity(self) -> None:
        tags = tag('A') + tag('B') + tag('C') + tag('Alias', 'B.X')
        result = capture(('MOV(A,Alias)ADD(B.X,Alias,C);',), tags=tags)[-1]
        self.assertEqual(len(result.links), 2)
        self.assertEqual(len({link['address_id'] for link in result.links}), 1)
        tags += tag('Bit', 'B.1')
        result = capture(('MOV(A,B.X)MOV(Bit.Member,C)ADD(B.X,1,C);',), tags=tags)[-1]
        self.assertEqual(result.coverage['gap_reasons']['invalid_identity'], 1)
        self.assertEqual(result.links, [])

    def test_scope_shadowing_does_not_join_same_spelled_roots(self) -> None:
        source = capture(('MOV(A,B)ADD(B,1,C);',))[0].data.decode()
        source = source.replace('<Program Name="P">', '<Program Name="P"><Tags>' + tag('B') + '</Tags>')
        program = source[source.index('<Program Name="P">'):source.index('</Programs>')]
        source = source.replace('</Programs>', program.replace('Name="P"', 'Name="Q"') + '</Programs>')
        result = capture_xml(source)[-1]
        self.assertEqual(len(result.links), 2)
        self.assertNotEqual(result.links[0]['address_id'], result.links[1]['address_id'])
        self.assertNotEqual(result.occurrences[0]['scope_id'], result.occurrences[2]['scope_id'])

    def test_malformed_signatures_expressions_and_dynamic_selectors_are_gaps(self) -> None:
        cases = {'MOV(A)': 'access_not_classified', 'CPT(C,ATAN2(A,B))': 'unsupported_expression',
                 'MOV(A[B],C)': 'unresolved_operand', 'CPT(C,A[B]+1)': 'unresolved_operand'}
        for block, reason in cases.items():
            with self.subTest(block=block):
                result = capture((f'MOV(A,B){block}ADD(B,1,D);',))[-1]
                self.assertEqual(result.coverage['gap_reasons'][reason], 1)
                self.assertEqual(result.links, [])
                self.assertEqual(len(result.occurrences), 3)
                self.assertEqual(result.occurrences[1]['status'], 'gap')
                self.assertEqual(result.regions[1]['end_reason'], 'block_gap')

    def test_literals_clr_and_all_ten_opcodes_have_dossiers_without_values(self) -> None:
        args = capture(('CLR(B)MOV(932871,B)ADD(B,1,C)SUB(C,1,B)MUL(B,2,C)DIV(C,2,B)ABS(B,C)LN(C,B)SQR(B,C)CPT(B,12+13);',))
        result = args[-1]
        self.assertEqual(result.coverage['occurrences_total'], 10)
        self.assertTrue(all(count == 1 for count in result.coverage['blocks_by_opcode'].values()))
        self.assertEqual(result.occurrences[0]['input_operand_ids'], [])
        self.assertEqual(len(result.occurrences[1]['input_operand_ids']), 1)
        self.assertEqual(result.occurrences[-1]['expression_use_ids'], [])
        self.assertNotIn('932871', render_calculation_paths_json(result))
        self.assertEqual(result.coverage['literal_input_operands'], 5)

    def test_cpt_repeated_leaves_read_before_own_write(self) -> None:
        result = capture(('MOV(A,B)CPT(B,B+B)CPT(C,B+B);',))[-1]
        self.assertEqual(len(result.links), 4)
        first, second, third = result.occurrences
        self.assertEqual([link['producer_instruction_id'] for link in result.links], [first['id']] * 2 + [second['id']] * 2)
        self.assertEqual(len({link['read_id'] for link in result.links}), 4)
        self.assertTrue(all(link['read_kind'] == 'expression' for link in result.links))
        self.assertEqual(capture(('CPT(B,B+B);',))[-1].links, [])

    def test_namespace_operand_ancestry_and_prior_context_are_quarantined(self) -> None:
        original = capture(('MOV(A,B)MOV(B,C)MOV(C,D);',))[0].data.decode()
        original = original.replace('<RSLogix5000Content>', '<RSLogix5000Content xmlns:x="urn:foreign">')
        unsupported_alias = original.replace(tag('A'), '<Tag Name="A" TagType="Alias" x:AliasFor="T"/>')
        cases = (unsupported_alias,
                 original.replace('<Program Name="P"', '<Program x:Name="P"'),
                 original.replace('<Text>', '<x:Text>').replace('</Text>', '</x:Text>'))
        for xml in cases:
            with self.subTest(xml=xml):
                result = capture_xml(xml)[-1]
                self.assertEqual(result.links, [])
                self.assertEqual(result.coverage['blocks_by_status']['gap'], 3)
                self.assertEqual(result.occurrences[-1]['condition_quality'], 'unavailable')
        # The same conservative propagation covers CPT leaves, not just slots.
        xml = unsupported_alias.replace('MOV(A,B)MOV(B,C)MOV(C,D)', 'CPT(B,A+1)MOV(B,C)MOV(C,D)')
        self.assertEqual(capture_xml(xml)[-1].coverage['blocks_by_status']['gap'], 3)

    def test_namespace_alias_chain_is_rejected_without_changing_binding(self) -> None:
        xml = capture(('MOV(A,B)MOV(B,C);',), tags=tag('A') + tag('B') + tag('C', 'B'))[0].data.decode()
        xml = xml.replace('<RSLogix5000Content>', '<RSLogix5000Content xmlns:x="urn:foreign">')
        xml = xml.replace('AliasFor="B"', 'x:AliasFor="B"')
        args = capture_xml(xml)
        self.assertEqual(args[-1].coverage['gap_reasons']['namespace_gap'], 1)
        self.assertEqual(args[-1].links, [])
        self.assertTrue(all(row['binding_status'] == 'root_bound' for row in args[3].operands))

    def test_unparsed_and_empty_rungs_have_no_fabricated_regions(self) -> None:
        result = capture((';', 'BROKEN(', 'XIC(A);'))[-1]
        self.assertEqual(result.regions, [])
        self.assertEqual(result.occurrences, [])
        self.assertEqual(result.coverage['unparsed_rungs'], 1)
        self.assertEqual(result.status, 'partial')

    def test_branch_walk_does_not_expand_combinatorial_paths(self) -> None:
        # Twenty sequential forks imply over a million possible combinations;
        # retain only their forty source-local calculation blocks.
        result = capture((''.join('[MOV(A,B),MOV(A,C)]' for _ in range(20)) + ';',))[-1]
        self.assertEqual(len(result.occurrences), 40)
        self.assertEqual(len(result.regions), 40)
        self.assertEqual(result.links, [])

    def test_canonical_replay_rejects_cross_region_link_and_count_tampering(self) -> None:
        args = capture()
        for field, value in (('region_id', 'forged'), ('producer_condition_id', None), ('read_kind', 'expression')):
            broken = deepcopy(args[-1])
            broken.links[0][field] = value
            with self.subTest(field=field), self.assertRaises(CalculationPathError):
                validate_calculation_paths(*args[:-1], broken)
        broken = deepcopy(args[-1])
        broken.regions[0]['blocks_count'] += 1
        with self.assertRaises(CalculationPathError):
            validate_calculation_paths(*args[:-1], broken)
        bad_conditions = replace(args[7], coverage={**args[7].coverage, 'nodes_total': 0})
        with self.assertRaises(CalculationPathError):
            analyze_calculation_paths(*args[:7], bad_conditions)
        old_conditions = analyze_conditions(*args[:7], schema_version=2)
        with self.assertRaises(CalculationPathError):
            analyze_calculation_paths(*args[:7], old_conditions)

    def test_native_serializer_and_incremental_limits_reject_source_free(self) -> None:
        args = capture()
        for name, limit in (('MAX_CALCULATION_PATH_RECORDS', 1), ('MAX_CALCULATION_PATH_BYTES', 20),
                            ('MAX_CALCULATION_PATH_JSON_BYTES', 20)):
            with self.subTest(name=name), patch('plc_workbench.calculation_paths.' + name, limit), self.assertRaises(CalculationPathError):
                analyze_calculation_paths(*args[:-1])
        for bad in (True, 1.5, object()):
            forged = deepcopy(args[-1])
            forged.coverage['source_rungs'] = bad
            with self.subTest(bad=type(bad)), self.assertRaises(CalculationPathError):
                render_calculation_paths_json(forged)
        cyclic = deepcopy(args[-1])
        cyclic.occurrences.append(cyclic.occurrences)
        with self.assertRaises(CalculationPathError) as caught:
            render_calculation_paths_json(cyclic)
        self.assertNotIn('MOV', str(caught.exception))

    def test_deterministic_source_order_and_region_membership(self) -> None:
        args = capture(('[MOV(A,B)ADD(B,1,C),MOV(A,B)CPT(C,B+B)]MOV(A,B)MOV(B,C);',))
        result = args[-1]
        self.assertEqual(render_calculation_paths_json(result), render_calculation_paths_json(analyze_calculation_paths(*args[:-1])))
        instructions = [row.id for rung in args[1].rungs for row in rung.instructions]
        self.assertEqual([row['id'] for row in result.occurrences], instructions)
        for region in result.regions:
            members = [row for row in result.occurrences if row['region_id'] == region['id']]
            self.assertEqual(len(members), region['blocks_count'])
            self.assertTrue(all(row['rung_id'] == region['rung_id'] and row['branch_depth'] == region['branch_depth'] for row in members))


if __name__ == '__main__':
    unittest.main()
