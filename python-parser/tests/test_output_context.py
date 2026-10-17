"""Invented ladders challenge Boolean source context without process claims."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access, render_access_json
from plc_workbench.calculations import analyze_calculations
from plc_workbench.conditions import analyze_conditions, render_conditions_json
from plc_workbench.output_context import (OutputContextError, analyze_output_context,
    render_output_context_json, validate_output_context)
from plc_workbench.references import analyze_references
from plc_workbench.relationships import analyze_relationships, render_relationships_json
from plc_workbench.rung_analysis import analyze_rungs
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from test_relationships import capture as capture_relationships, tag
from test_module_io import LOCAL, module, port, communications


def capture(texts=('XIC(A)OTE(D);',), **kwargs):
    args = capture_relationships(texts, **kwargs)
    conditions = analyze_conditions(*args, schema_version=3)
    return (*args, conditions, analyze_output_context(*args, conditions))


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
    return (*args, conditions, analyze_output_context(*args, conditions))


def namespace(xml: str) -> str:
    return xml.replace('<RSLogix5000Content>', '<RSLogix5000Content xmlns:x="urn:invented-foreign">')


class OutputContextTests(unittest.TestCase):
    def test_all_coils_keep_actions_guard_ids_and_unchanged_older_evidence(self) -> None:
        args = capture(('XIC(D)OTE(D)OTL(D);', 'XIO(D)OTU(D);'))
        before = (render_access_json(args[3]), render_relationships_json(args[6]), render_conditions_json(args[7]))
        result = args[-1]
        self.assertEqual(result.coverage['outputs_by_opcode'], {'OTE': 1, 'OTL': 1, 'OTU': 1})
        self.assertEqual([row['action'] for row in result.outputs], ['assign_condition', 'set_if_true', 'clear_if_true'])
        self.assertEqual([row['condition_output_id'] for row in result.outputs], [row['id'] for row in args[7].outputs])
        self.assertEqual([row['guard_id'] for row in result.outputs], [row['guard_id'] for row in args[7].outputs])
        self.assertEqual(len(result.addresses), 1)
        self.assertEqual(result.addresses[0]['output_ids'], [row['id'] for row in result.outputs])
        self.assertEqual(result.coverage['addresses_with_multiple_coils'], 1)
        self.assertEqual(result.status, 'complete')
        validate_output_context(*args)
        self.assertEqual(result.to_dict(), json.loads(render_output_context_json(result)))
        self.assertEqual(before, (render_access_json(args[3]), render_relationships_json(args[6]), render_conditions_json(args[7])))

    def test_noncoil_writers_unknown_roles_and_expression_reads_remain_separate(self) -> None:
        result = capture(('OTE(D);', 'MOV(1,D)ONS(D)PID(D,A,B,C,0,0,0)CPT(A,D+D)XIC(D);'))[-1]
        address = result.addresses[0]
        self.assertEqual({key: len(address[f'{key}_operand_ids']) for key in ('read', 'write', 'read_write', 'unknown')},
                         {'read': 1, 'write': 2, 'read_write': 1, 'unknown': 1})
        self.assertEqual(len(address['expression_use_ids']), 2)
        self.assertEqual(len(address['noncoil_writer_operand_ids']), 2)
        self.assertEqual(result.coverage['condition_read_kinds'], {'ons_storage': 1, 'predicate': 1})
        self.assertEqual(result.coverage['accepted_expression_uses'], 2)
        self.assertEqual(result.coverage['addresses_with_unknown_roles'], 1)
        self.assertEqual(result.status, 'partial')

    def test_aliases_group_exact_suffix_only_and_keep_root_member_distinctions(self) -> None:
        tags = tag('A') + tag('B') + tag('Alias', 'B.X')
        result = capture(('OTE(Alias)OTL(B.X)OTU(B.x)OTE(B)XIC(B.X);',), tags=tags)[-1]
        self.assertEqual(len(result.addresses), 3)
        self.assertEqual(sorted(len(row['output_ids']) for row in result.addresses), [1, 1, 2])
        self.assertEqual(result.outputs[0]['target_address_id'], result.outputs[1]['target_address_id'])
        self.assertEqual(result.condition_reads[0]['source_address_id'], result.outputs[0]['target_address_id'])
        self.assertEqual(result.condition_reads[0]['status'], 'accepted')
        self.assertEqual(result.coverage['addresses_without_readers'], 2)

    def test_condition_reads_use_actual_nodes_without_sibling_or_pair_expansion(self) -> None:
        args = capture(('[XIC(D)OTE(A),XIO(D)OTE(B)]OTE(C);', 'OTE(D);'))
        result = args[-1]
        self.assertEqual(len(result.condition_reads), 2)
        nodes = {row['id']: row for row in args[7].nodes}
        left, right = result.condition_reads
        operands = {row['id']: row for row in args[3].operands}
        self.assertNotEqual(left['condition_node_id'], right['condition_node_id'])
        for row in result.condition_reads:
            self.assertEqual(nodes[row['condition_node_id']]['operand_ids'], [row['id']])
            self.assertEqual(nodes[row['condition_node_id']]['instruction_id'], operands[row['id']]['instruction_id'])
            self.assertEqual(set(row), {'id', 'condition_node_id', 'source_address_id', 'kind', 'status'})
            self.assertNotIn('output_ids', row)
        left_guard = nodes[result.outputs[0]['guard_id']]
        right_guard = nodes[result.outputs[1]['guard_id']]
        self.assertIn(left['condition_node_id'], left_guard['child_ids'])
        self.assertNotIn(left['condition_node_id'], right_guard['child_ids'])
        self.assertTrue(result.outputs[2]['has_branch'])

    def test_repeated_predicates_and_self_feedback_are_source_occurrences(self) -> None:
        args = capture(('XIC(D)XIC(D)ONS(D)OTE(D);',))
        result = args[-1]
        self.assertEqual(len(result.condition_reads), 3)
        self.assertEqual(len({row['id'] for row in result.condition_reads}), 3)
        self.assertEqual(result.coverage['condition_read_kinds'], {'predicate': 2, 'ons_storage': 1})
        self.assertEqual(result.outputs[0]['context_status'], 'stateful')
        self.assertTrue(result.outputs[0]['has_stateful'])
        self.assertEqual(result.execution_analysis, 'not_implemented')
        self.assertEqual(result.shutdown_analysis, 'not_implemented')

    def test_unresolved_targets_remain_in_order_with_no_invented_addresses(self) -> None:
        tags = tag('A') + tag('B', 'A.1')
        result = capture(('OTE(Missing)OTL(A[B])OTU(B.Member)OTE()ote(A);',), tags=tags)[-1]
        self.assertEqual(len(result.outputs), 5)
        self.assertEqual([row['target_status'] for row in result.outputs],
                         ['unbound', 'unbound', 'identity_gap', 'signature_unresolved', 'exact_address'])
        self.assertTrue(all(row['target_address_id'] is None for row in result.outputs[:4]))
        self.assertEqual(result.outputs[3]['action'], 'unresolved')
        self.assertEqual(len(result.addresses), 1)

    def test_binding_gap_opaque_and_stateful_guard_qualifications_survive(self) -> None:
        result = capture(('XIC(Missing)OTE(D);', 'MYSTERY(A)OTE(D);', 'ONS(A)OTE(D);'))[-1]
        self.assertEqual([row['context_status'] for row in result.outputs], ['binding_gaps', 'opaque', 'stateful'])
        self.assertTrue(result.outputs[0]['has_binding_gap'])
        self.assertTrue(result.outputs[1]['has_opaque'])
        self.assertEqual(result.status, 'partial')

    def test_namespace_alias_targets_and_other_uses_are_explicitly_rejected(self) -> None:
        xml = capture(('OTE(D);', 'XIC(Bad)OTE(Bad)CPT(A,Bad+Bad);'),
                      tags=tag('A') + tag('D') + tag('Bad', 'D'))[0].data.decode()
        args = capture_xml(namespace(xml).replace('AliasFor="D"', 'x:AliasFor="D"'))
        result = args[-1]
        self.assertEqual(result.outputs[1]['target_status'], 'namespace_gap')
        self.assertIsNone(result.outputs[1]['target_address_id'])
        self.assertEqual(result.outputs[1]['context_status'], 'namespace_gap')
        address = result.addresses[0]
        self.assertEqual(len(address['rejected_operand_ids']), 2)
        self.assertEqual(len(address['rejected_expression_use_ids']), 2)
        self.assertEqual(address['read_operand_ids'], [])
        self.assertEqual(len(address['write_operand_ids']), 1)
        self.assertEqual(result.condition_reads[0]['status'], 'namespace_gap')
        self.assertNotIn('address_id', result.condition_reads[0])
        self.assertEqual(result.condition_reads[0]['source_address_id'], address['id'])
        self.assertEqual(args[7].outputs[1]['target_status'], 'exact_address')

    def test_namespace_prior_expression_and_predicate_context_propagate(self) -> None:
        for prior in ('XIC(Bad)', 'MOV(Bad,A)', 'CPT(A,Bad+1)'):
            xml = capture((f'{prior}ONS(D)OTE(D);',), tags=tag('A') + tag('D') + tag('Bad', 'A'))[0].data.decode()
            result = capture_xml(namespace(xml).replace('AliasFor="A"', 'x:AliasFor="A"'))[-1]
            with self.subTest(prior=prior):
                self.assertEqual(result.outputs[0]['target_status'], 'exact_address')
                self.assertEqual(result.outputs[0]['context_status'], 'namespace_gap')
                self.assertTrue(result.outputs[0]['has_namespace_gap'])
                self.assertEqual(result.condition_reads[-1]['status'], 'namespace_gap')

    def test_namespace_context_follows_dag_ancestry_not_sibling_proximity(self) -> None:
        xml = capture(('[XIC(Bad)OTE(A),XIC(D)OTE(B)]OTE(C);', 'OTE(D);'),
                      tags=tag('A') + tag('B') + tag('C') + tag('D') + tag('Bad', 'D'))[0].data.decode()
        result = capture_xml(namespace(xml).replace('AliasFor="D"', 'x:AliasFor="D"'))[-1]
        self.assertEqual([row['context_status'] for row in result.outputs],
                         ['namespace_gap', 'modeled', 'namespace_gap', 'modeled'])
        self.assertEqual([row['status'] for row in result.condition_reads], ['namespace_gap', 'accepted'])
        self.assertTrue(all(row['target_status'] == 'exact_address' for row in result.outputs))

    def test_program_scope_shadowing_keeps_same_spelling_in_distinct_groups(self) -> None:
        xml = capture(('XIC(D)OTE(D);',))[0].data.decode()
        xml = xml.replace('<Program Name="P">', '<Program Name="P"><Tags>' + tag('D') + '</Tags>')
        program = xml[xml.index('<Program Name="P">'):xml.index('</Programs>')]
        xml = xml.replace('</Programs>', program.replace('Name="P"', 'Name="Q"') + '</Programs>')
        result = capture_xml(xml)[-1]
        self.assertEqual(len(result.addresses), 2)
        self.assertNotEqual(result.outputs[0]['target_address_id'], result.outputs[1]['target_address_id'])
        self.assertEqual([row['source_address_id'] for row in result.condition_reads],
                         [row['target_address_id'] for row in result.outputs])

    def test_namespace_rung_text_or_program_attributes_quarantine_every_target(self) -> None:
        xml = namespace(capture(('XIC(A)OTE(D);',))[0].data.decode())
        for modified in (xml.replace('<Program Name=', '<Program x:Name='),
                         xml.replace('<Text>', '<x:Text>').replace('</Text>', '</x:Text>')):
            result = capture_xml(modified)[-1]
            self.assertEqual(result.outputs[0]['target_status'], 'namespace_gap')
            self.assertEqual(result.outputs[0]['context_status'], 'namespace_gap')
            self.assertEqual(result.addresses, [])

    def test_module_root_kinds_do_not_claim_channels_or_physical_meaning(self) -> None:
        modules = ('<Modules><Module Name="Invented"><Communications><ConfigTag Name="Rack:C"/>'
                   '<Connections><Connection Name="Data"><InputTag Name="Rack:I"/>'
                   '<OutputTag Name="Rack:O"/></Connection></Connections></Communications></Module></Modules>')
        result = capture(('OTE(Rack:O.Data.0)OTE(Rack:I.Data.1)OTE(Rack:C.Enable)OTE(A);',), modules=modules)[-1]
        self.assertEqual([row['endpoint_kind'] for row in result.addresses],
                         ['module_output', 'module_input', 'module_config', 'tag'])
        self.assertEqual(result.physical_mapping, 'not_implemented')
        self.assertTrue(all('channel' not in row for row in result.addresses))

    def test_implicit_module_naming_checks_parent_ports_and_foreign_attributes(self) -> None:
        modules = '<Modules>' + LOCAL + module(communications=communications('<OutputTag/>')) + '</Modules>'
        xml = namespace(capture(('OTE(Local:3:O.Data.0);',), modules=modules)[0].data.decode())
        self.assertEqual(capture_xml(xml)[-1].outputs[0]['target_status'], 'exact_address')
        for modified in (xml.replace(' Address=', ' x:Address='),
                         xml.replace(' Upstream=', ' x:Upstream='),
                         xml.replace('ParentModule="Local"', 'x:ParentModule="Local"')):
            with self.subTest(modified=modified):
                result = capture_xml(modified)[-1]
                self.assertEqual(result.outputs[0]['target_status'], 'namespace_gap')
                self.assertEqual(result.addresses, [])

    def test_hints_are_rung_wide_text_only_and_do_not_spread_between_rungs(self) -> None:
        rungs = ('<Rung Number="0"><Comment>alarm pump sensor</Comment>'
                 '<Text>[XIC(A)OTE(B),XIO(A)OTE(D)];</Text></Rung>'
                 '<Rung Number="1"><Text>OTE(D)ALMA(A);</Text></Rung>')
        result = capture(rung_xml=rungs)[-1]
        first, second = result.rung_contexts
        self.assertEqual(len(first['output_ids']), 2)
        self.assertTrue(all(len(rows) == 1 for rows in first['candidate_ids_by_category'].values()))
        self.assertFalse(any(second['candidate_ids_by_category'].values()))
        self.assertTrue(all('candidate_ids' not in row for row in result.outputs))
        self.assertEqual(result.hint_scope, 'rung_wide_only')

    def test_foreign_comment_description_and_name_hints_keep_unqualified_ids(self) -> None:
        xml = capture(rung_xml='<Rung><Comment>alarm</Comment><Text>OTE(D);</Text></Rung>')[0].data.decode()
        modified = namespace(xml).replace('<Comment>', '<x:Comment>').replace('</Comment>', '</x:Comment>')
        result = capture_xml(modified)[-1]
        self.assertEqual(result.coverage['hints_by_category']['alarm'], 0)
        self.assertEqual(result.coverage['unqualified_hints_by_category']['alarm'], 1)
        for attribute in ('<Description>pump</Description>', '<x:Description>pump</x:Description>'):
            xml = namespace(capture(('OTE(D);',))[0].data.decode())
            xml = xml.replace(tag('D'), '<Tag Name="D" TagType="Base" DataType="DINT">' + attribute + '</Tag>')
            result = capture_xml(xml)[-1]
            expected = 'unqualified_hints_by_category' if 'x:' in attribute else 'hints_by_category'
            self.assertEqual(result.coverage[expected]['equipment'], 1)

    def test_empty_unparsed_and_lowercase_sources_keep_honest_scope(self) -> None:
        result = capture((';', 'BROKEN(', 'xic(A)ote(D);'))[-1]
        self.assertEqual(len(result.outputs), 1)
        self.assertEqual(result.outputs[0]['opcode'], 'OTE')
        self.assertEqual(result.coverage['unparsed_rungs'], 1)
        self.assertEqual(result.status, 'partial')
        self.assertEqual(capture((';',))[-1].status, 'complete')

    def test_linear_evidence_size_despite_many_possible_guard_paths(self) -> None:
        args = capture(('OTE(D);', ''.join('[XIC(D),XIO(D)]' for _ in range(20)) + 'OTE(A)OTL(B);'))
        result = args[-1]
        self.assertEqual(len(result.outputs), 3)
        self.assertEqual(len(result.condition_reads), 40)
        self.assertEqual(len(result.rung_contexts), 2)
        self.assertLess(len(render_output_context_json(result)), 70_000)

    def test_canonical_replay_rejects_tampered_links_flags_counts_and_source(self) -> None:
        args = capture(('XIC(D)OTE(D);',))
        for mutate in (lambda r: r.outputs[0].update(target_address_id='invented'),
                       lambda r: r.outputs[0].update(has_branch=True),
                       lambda r: r.condition_reads[0].update(condition_node_id='invented'),
                       lambda r: r.addresses[0]['read_operand_ids'].clear(),
                       lambda r: r.coverage.update(source_rungs=True)):
            broken = deepcopy(args[-1])
            mutate(broken)
            with self.assertRaises(OutputContextError) as caught:
                validate_output_context(*args[:-1], broken)
            self.assertNotIn('invented', str(caught.exception))
        bad_conditions = replace(args[7], coverage={**args[7].coverage, 'nodes_total': 0})
        with self.assertRaises(OutputContextError):
            analyze_output_context(*args[:7], bad_conditions)
        with self.assertRaises(OutputContextError):
            analyze_output_context(*args[:7], analyze_conditions(*args[:7], schema_version=2))

    def test_incremental_and_render_resource_limits_are_source_free(self) -> None:
        args = capture()
        for constant in ('MAX_OUTPUT_CONTEXT_RECORDS', 'MAX_OUTPUT_CONTEXT_BYTES', 'MAX_OUTPUT_CONTEXT_JSON_BYTES'):
            with patch(f'plc_workbench.output_context.{constant}', 1), self.assertRaises(OutputContextError):
                analyze_output_context(*args[:-1])
        cyclic = deepcopy(args[-1])
        cyclic.outputs.append(cyclic.outputs)
        with self.assertRaises(OutputContextError):
            render_output_context_json(cyclic)
        broken = deepcopy(args[-1])
        broken.coverage['source_rungs'] = object()
        with self.assertRaises(OutputContextError):
            render_output_context_json(broken)

    def test_source_order_and_serialization_are_deterministic(self) -> None:
        args = capture(('OTE(D);', '[XIC(D)OTE(A),XIO(D)OTE(B)]OTE(C);'))
        self.assertEqual(render_output_context_json(args[-1]), render_output_context_json(analyze_output_context(*args[:-1])))
        instructions = [row.id for rung in args[1].rungs for row in rung.instructions
                        if row.opcode.upper() in {'OTE', 'OTL', 'OTU'}]
        self.assertEqual([row['instruction_id'] for row in args[-1].outputs], instructions)


if __name__ == '__main__':
    unittest.main()
