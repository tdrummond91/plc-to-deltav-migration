"""Invented direct guard memberships retain provenance and bounded gaps."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from plc_workbench.signal_context import (SignalContextError, analyze_signal_context,
    render_signal_context_json, signal_context_constants, validate_signal_context)
from plc_workbench.signal_dependencies import DEPENDENCY_COVERAGE_KEYS
from test_signal_context import capture as base_capture, capture_xml as base_capture_xml, namespace, tag, typed_tag


def capture(*args, **kwargs):
    parts = base_capture(*args, **kwargs)
    return (*parts[:-1], analyze_signal_context(*parts[:-1], schema_version=4))


def capture_xml(xml: str):
    parts = base_capture_xml(xml)
    return (*parts[:-1], analyze_signal_context(*parts[:-1], schema_version=4))


def read_ids(output):
    return output['guard_dependencies']['condition_read_ids']


class SignalDependencyTests(unittest.TestCase):
    def test_v3_bytes_and_all_historical_default_versions_are_preserved(self) -> None:
        args = base_capture(('XIC(A)OTL(D);', 'XIO(D)OTU(D);'))
        historical = {version: render_signal_context_json(analyze_signal_context(*args[:-1], schema_version=version))
            for version in (1, 2, 3)}
        result = analyze_signal_context(*args[:-1], schema_version=4)
        reduced = deepcopy(result)
        for output in reduced.outputs:
            del output['guard_dependencies']
        for address in reduced.addresses:
            del address['dependent_output_ids']
        for key in DEPENDENCY_COVERAGE_KEYS:
            del reduced.coverage[key]
        reduced = replace(reduced, **signal_context_constants(3))
        self.assertEqual(render_signal_context_json(reduced), historical[3])
        for version in (1, 2, 3):
            self.assertEqual(render_signal_context_json(analyze_signal_context(*args[:-1], schema_version=version)),
                historical[version])
        self.assertEqual(render_signal_context_json(analyze_signal_context(*args[:-1])), historical[1])
        validate_signal_context(*args[:-1], result)

    def test_sibling_later_and_shared_prefix_contacts_follow_exact_dag(self) -> None:
        result = capture(('XIC(A)[XIC(B)OTE(C),XIO(C)OTE(D)]OTE(B)XIC(D);',))[-1]
        prefix, left, right, later = result.condition_reads
        first, second, join = result.outputs
        self.assertEqual(set(read_ids(first)), {prefix['id'], left['id']})
        self.assertEqual(set(read_ids(second)), {prefix['id'], right['id']})
        self.assertEqual(set(read_ids(join)), {prefix['id'], left['id'], right['id']})
        self.assertEqual(len(read_ids(join)), 3)
        self.assertTrue(all(later['id'] not in read_ids(output) for output in result.outputs))
        prefix_address = next(row for row in result.addresses if row['id'] == prefix['source_address_id'])
        self.assertEqual(prefix_address['dependent_output_ids'], [row['id'] for row in result.outputs])

    def test_comparisons_literals_flags_storage_and_unbound_slots_stay_distinct(self) -> None:
        result = capture(('EQU(A,1)XIC(S:FS)XIO(Missing)ONS(B)OTE(D);',))[-1]
        output = result.outputs[0]
        self.assertEqual(set(read_ids(output)), {row['id'] for row in result.condition_reads})
        self.assertEqual(result.coverage['dependency_reads_by_kind'],
            {'comparison': 2, 'ons_storage': 1, 'xic': 1, 'xio': 1})
        self.assertEqual(result.coverage['dependency_reads_by_status'],
            {'exact_address': 2, 'identity_gap': 0, 'literal': 1, 'namespace_gap': 0, 'system_flag': 1, 'unbound': 1})
        self.assertEqual(result.coverage['dependency_reverse_links_total'], 2)
        self.assertEqual(output['guard_quality'], 'binding_gaps')
        self.assertTrue(output['has_stateful'])

    def test_repeated_occurrences_retain_ids_but_reverse_output_is_unique(self) -> None:
        result = capture(('XIC(A)XIO(A)EQU(A,A)OTE(D);',))[-1]
        self.assertEqual(len(read_ids(result.outputs[0])), 4)
        self.assertEqual(len(set(read_ids(result.outputs[0]))), 4)
        address = next(row for row in result.addresses if row['condition_read_ids'])
        self.assertEqual(address['dependent_output_ids'], [result.outputs[0]['id']])
        self.assertEqual(result.coverage['dependency_read_links_total'], 4)
        self.assertEqual(result.coverage['dependency_reverse_links_total'], 1)

    def test_aliases_match_exact_spelling_and_not_nearby_members(self) -> None:
        result = capture(('XIC(Alias)XIO(B.x)OTE(D);',),
            tags=tag('B') + tag('D') + tag('Alias', 'B.X'))[-1]
        self.assertNotEqual(result.condition_reads[0]['source_address_id'], result.condition_reads[1]['source_address_id'])
        self.assertEqual(result.coverage['dependency_addresses_with_dependents'], 2)
        self.assertTrue(all(len(row['dependent_output_ids']) == 1
            for row in result.addresses if row['condition_read_ids']))

    def test_shared_guard_is_scanned_once_while_output_occurrences_remain_distinct(self) -> None:
        one = capture(('[XIC(A),XIO(B)]OTE(D);',))[-1]
        many = capture(('[XIC(A),XIO(B)]' + 'OTE(D)' * 40 + ';',))[-1]
        for key in ('dependency_unique_guards_total', 'dependency_visited_nodes',
                'dependency_visited_edges', 'dependency_cached_read_ids'):
            self.assertEqual(many.coverage[key], one.coverage[key])
        self.assertEqual(many.coverage['dependency_unique_guards_total'], 1)
        self.assertEqual(many.coverage['dependency_read_links_total'], 80)
        self.assertEqual(many.coverage['dependency_reverse_links_total'], 80)

    def test_empty_bypass_and_unconditional_outputs_do_not_claim_required_inputs(self) -> None:
        result = capture(('OTE(D);', '[XIC(A),]OTE(B);', 'XIC(C);'))[-1]
        self.assertEqual(read_ids(result.outputs[0]), [])
        self.assertEqual(result.outputs[0]['guard_dependencies']['traversal_status'], 'complete')
        self.assertEqual(result.coverage['dependency_outputs_without_reads_complete'], 1)
        self.assertEqual(len(read_ids(result.outputs[1])), 1)
        self.assertTrue(result.outputs[1]['has_branch'])
        no_consumer = next(row for row in result.addresses if row['condition_read_ids'] == [result.condition_reads[-1]['id']])
        self.assertEqual(no_consumer['dependent_output_ids'], [])

    def test_opaque_and_stateful_guards_remain_flagged_source_memberships(self) -> None:
        result = capture(('XIC(A)MYSTERY(B)OTE(D);', 'XIC(A)ONS(B)OTL(C);'))[-1]
        self.assertEqual([row['guard_quality'] for row in result.outputs], ['opaque', 'stateful'])
        self.assertEqual(result.coverage['dependency_reverse_links_by_guard_quality'],
            {'binding_gaps': 0, 'modeled': 0, 'namespace_gap': 0, 'opaque': 1, 'stateful': 2})
        self.assertEqual(result.shutdown_analysis, 'not_implemented')

    def test_namespace_gap_blocks_reverse_even_for_qualified_sibling_reads(self) -> None:
        xml = namespace(base_capture(('[XIC(A),XIC(B)]OTE(D);',))[0].data.decode())
        xml = xml.replace('Name="B" TagType=', 'Name="B" x:Marker="foreign" TagType=')
        result = capture_xml(xml)[-1]
        self.assertEqual(result.outputs[0]['guard_quality'], 'namespace_gap')
        self.assertEqual(len(read_ids(result.outputs[0])), 2)
        self.assertEqual(result.coverage['dependency_reads_by_status']['exact_address'], 1)
        self.assertEqual(result.coverage['dependency_reverse_links_total'], 0)
        self.assertTrue(all(not row['dependent_output_ids'] for row in result.addresses))

    def test_unresolved_output_target_does_not_hide_its_qualified_incoming_reads(self) -> None:
        result = capture(('XIC(A)OTE(Missing);',))[-1]
        self.assertEqual(result.outputs[0]['target_status'], 'unbound')
        self.assertEqual(result.addresses[0]['dependent_output_ids'], [result.outputs[0]['id']])
        self.assertEqual(result.coverage['dependency_outputs_with_dependents'], 1)

    def test_data_operations_and_timer_producers_do_not_create_boolean_transfer(self) -> None:
        result = capture(('MOV(A,B)OTE(D);', 'XIC(A)TON(T,?,?);', 'XIC(T.DN)OTL(D);'),
            tags=tag('A') + tag('B') + tag('D') + typed_tag('T'))[-1]
        self.assertEqual(read_ids(result.outputs[0]), [])
        self.assertEqual(read_ids(result.outputs[1]), [result.condition_reads[-1]['id']])
        self.assertEqual(result.coverage['dependency_read_links_total'], 1)
        self.assertEqual(result.coverage['dependency_reverse_links_total'], 1)

    def test_cross_rung_cycles_and_multiple_writers_stay_direct_occurrences(self) -> None:
        result = capture(('XIC(A)OTE(B);', 'XIO(B)OTL(A);', 'XIC(C)OTU(A);', 'MOV(D,A);'))[-1]
        self.assertTrue(all(len(read_ids(row)) == 1 for row in result.outputs))
        a_address = next(row for row in result.addresses if row['id'] == result.condition_reads[0]['source_address_id'])
        self.assertEqual(a_address['dependent_output_ids'], [result.outputs[0]['id']])
        self.assertEqual(a_address['output_ids'], [row['id'] for row in result.outputs[1:]])
        self.assertEqual(len(a_address['noncoil_writer_operand_ids']), 1)
        self.assertEqual(result.coverage['dependency_read_links_total'], 3)

    def test_source_edits_and_routines_preserve_each_writer_and_its_own_guard(self) -> None:
        xml = base_capture(('XIC(A)OTE(D);',))[0].data.decode()
        start, end = xml.index('<RLLContent>'), xml.index('</RLLContent>') + len('</RLLContent>')
        contents = ('<RLLContent Type="Original"><Rung><Text>XIC(A)OTE(D);</Text></Rung></RLLContent>'
            '<RLLContent Type="Pending"><Rung><Text>XIO(B)OTE(D);</Text></Rung></RLLContent>')
        xml = xml[:start] + contents + xml[end:]
        start, end = xml.index('<Routine '), xml.index('</Routine>') + len('</Routine>')
        xml = xml[:end] + xml[start:end].replace('Name="R"', 'Name="Other"') + xml[end:]
        result = capture_xml(xml)[-1]
        self.assertEqual(len(result.outputs), 4)
        self.assertEqual(len({row['content_locator'] for row in result.outputs}), 4)
        self.assertEqual(len({row['routine_id'] for row in result.outputs}), 2)
        for output in result.outputs:
            linked = [row for row in result.condition_reads if row['id'] in read_ids(output)]
            self.assertEqual(len(linked), 1)
            self.assertEqual(linked[0]['rung_id'], output['rung_id'])

    def test_all_scan_and_retention_limits_are_explicit_and_replayable(self) -> None:
        args = base_capture(('XIC(A)OTE(D);', 'XIO(B)OTE(C);'))
        for name in ('MAX_GUARD_DEPENDENCY_NODES', 'MAX_GUARD_DEPENDENCY_EDGES',
                'MAX_DEPENDENCY_VISITED_NODES', 'MAX_DEPENDENCY_VISITED_EDGES',
                'MAX_DEPENDENCY_LINKS', 'MAX_DEPENDENCY_CACHE_READS'):
            with self.subTest(name=name), patch(f'plc_workbench.signal_dependencies.{name}', 0):
                result = analyze_signal_context(*args[:-1], schema_version=4)
                self.assertEqual(result.status, 'partial')
                self.assertGreater(result.coverage['dependency_traversals_by_status']['truncated'], 0)
                validate_signal_context(*args[:-1], result)

    def test_forward_reverse_retention_is_atomic_and_repeated_reads_cost_one(self) -> None:
        args = base_capture(('XIC(A)XIO(A)OTE(D);',))
        for limit, forward, reverse, status in ((1, 0, 0, 'truncated'), (2, 1, 1, 'truncated'), (3, 2, 1, 'complete')):
            with self.subTest(limit=limit), patch('plc_workbench.signal_dependencies.MAX_DEPENDENCY_LINKS', limit):
                result = analyze_signal_context(*args[:-1], schema_version=4)
                self.assertEqual(result.coverage['dependency_read_links_total'], forward)
                self.assertEqual(result.coverage['dependency_reverse_links_total'], reverse)
                self.assertEqual(result.outputs[0]['guard_dependencies']['traversal_status'], status)
                validate_signal_context(*args[:-1], result)

    def test_tampered_indices_counts_and_versions_are_rejected_source_free(self) -> None:
        args = capture(('XIC(A)OTE(D);',))
        for mutate in (lambda r: r.outputs[0]['guard_dependencies']['condition_read_ids'].clear(),
                lambda r: r.addresses[0]['dependent_output_ids'].append('PRIVATE'),
                lambda r: r.coverage.update(dependency_cached_read_ids=True),
                lambda r: r.outputs[0]['guard_dependencies'].update(traversal_status='PRIVATE')):
            broken = deepcopy(args[-1])
            mutate(broken)
            with self.assertRaises(SignalContextError) as caught:
                validate_signal_context(*args[:-1], broken)
            self.assertNotIn('PRIVATE', str(caught.exception))
        for version in (True, 0, 6, '4'):
            with self.subTest(version=version), self.assertRaises(SignalContextError):
                analyze_signal_context(*args[:-1], schema_version=version)
        for cap in ('MAX_SIGNAL_CONTEXT_V4_BYTES', 'MAX_SIGNAL_CONTEXT_V4_JSON_BYTES'):
            with patch(f'plc_workbench.signal_context.{cap}', 1), self.assertRaises(SignalContextError):
                render_signal_context_json(args[-1])


if __name__ == '__main__':
    unittest.main()
