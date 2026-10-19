"""Invented source challenges bounded contact presence and scoped coil groups."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from plc_workbench.signal_context import (SignalContextError, analyze_signal_context,
    render_signal_context_json, signal_context_constants, validate_signal_context)
from plc_workbench.signal_patterns import PATTERN_COVERAGE_KEYS
from test_signal_context import capture as base_capture, capture_xml as base_capture_xml, namespace, tag, typed_tag


def capture(*args, **kwargs):
    parts = base_capture(*args, **kwargs)
    return (*parts[:-1], analyze_signal_context(*parts[:-1], schema_version=2))


def capture_xml(xml: str):
    parts = base_capture_xml(xml)
    return (*parts[:-1], analyze_signal_context(*parts[:-1], schema_version=2))


class SignalPatternTests(unittest.TestCase):
    def test_v1_default_and_bytes_are_preserved(self) -> None:
        args = base_capture(('XIC(D)OTE(D);', 'OTL(D);', 'OTU(D);'))
        old = render_signal_context_json(args[-1])
        new = analyze_signal_context(*args[:-1], schema_version=2)
        reduced = deepcopy(new)
        for output in reduced.outputs:
            del output['guard_patterns']
        for address in reduced.addresses:
            del address['coil_contexts']
        for key in PATTERN_COVERAGE_KEYS:
            del reduced.coverage[key]
        reduced = replace(reduced, **signal_context_constants(1))
        self.assertEqual(render_signal_context_json(reduced), old)
        self.assertEqual(old, render_signal_context_json(analyze_signal_context(*args[:-1])))
        self.assertEqual(new.schema_version, 2)
        validate_signal_context(*args[:-1], new)

    def test_self_contacts_follow_actual_guard_and_preserve_polarities(self) -> None:
        result = capture(('[XIC(B)OTE(B),XIO(D)OTE(D)]OTE(B);',))[-1]
        left, right, join = (row['guard_patterns'] for row in result.outputs)
        first, second = (row['id'] for row in result.condition_reads)
        self.assertEqual(left['self_xic_read_ids'], [first])
        self.assertEqual(left['self_xio_read_ids'], [])
        self.assertEqual(right['self_xic_read_ids'], [])
        self.assertEqual(right['self_xio_read_ids'], [second])
        self.assertEqual(join['self_xic_read_ids'], [first])
        self.assertEqual(join['self_xio_read_ids'], [])
        both = capture(('XIC(D)XIO(D)OTE(D);',))[-1].outputs[0]['guard_patterns']
        self.assertEqual(len(both['self_xic_read_ids']), 1)
        self.assertEqual(len(both['self_xio_read_ids']), 1)
        self.assertNotIn('seal_in', both)

    def test_comparisons_and_storage_are_not_self_contacts(self) -> None:
        result = capture(('EQU(D,1)ONS(D)OTE(D);',))[-1]
        pattern = result.outputs[0]['guard_patterns']
        self.assertEqual(pattern['self_xic_read_ids'], [])
        self.assertEqual(pattern['self_xio_read_ids'], [])
        self.assertEqual(result.outputs[0]['guard_quality'], 'stateful')

    def test_aliases_match_exact_expanded_address_not_shared_roots(self) -> None:
        result = capture(('XIC(Alias)XIO(B.x)OTE(B.X);',),
            tags=tag('B') + tag('Alias', 'B.X'))[-1]
        pattern = result.outputs[0]['guard_patterns']
        self.assertEqual(pattern['self_xic_read_ids'], [result.condition_reads[0]['id']])
        self.assertEqual(pattern['self_xio_read_ids'], [])

    def test_set_reset_groups_retain_all_actions_and_same_content_only(self) -> None:
        result = capture(('OTL(D);', 'OTU(D);', 'OTE(D);', 'OTL(A);'))[-1]
        groups = [group for address in result.addresses for group in address['coil_contexts']]
        group = next(group for group in groups if group['has_set_reset'])
        self.assertEqual([len(group[f'{opcode}_output_ids']) for opcode in ('ote', 'otl', 'otu')], [1, 1, 1])
        self.assertEqual(result.coverage['pattern_set_reset_contexts'], 1)
        self.assertEqual(result.coverage['pattern_addresses_with_set_reset'], 1)
        xml = base_capture(('OTL(D);',))[0].data.decode()
        start, end = xml.index('<RLLContent>'), xml.index('</RLLContent>') + len('</RLLContent>')
        contents = ('<RLLContent Type="Original"><Rung><Text>OTL(D);</Text></Rung></RLLContent>'
            '<RLLContent Type="Pending"><Rung><Text>OTU(D);</Text></Rung></RLLContent>')
        separate = capture_xml(xml[:start] + contents + xml[end:])[-1]
        self.assertEqual(len(separate.addresses[0]['coil_contexts']), 2)
        self.assertEqual(separate.coverage['pattern_set_reset_contexts'], 0)

    def test_set_reset_different_routines_are_distinct_even_without_edit_attributes(self) -> None:
        xml = base_capture(('OTL(D);',))[0].data.decode()
        start, end = xml.index('<Routine '), xml.index('</Routine>') + len('</Routine>')
        routine = xml[start:end]
        extra = routine.replace('Name="R"', 'Name="Other"').replace('OTL(D)', 'OTU(D)')
        result = capture_xml(xml[:end] + extra + xml[end:])[-1]
        self.assertEqual(result.coverage['pattern_coil_contexts_total'], 2)
        self.assertEqual(result.coverage['pattern_set_reset_contexts'], 0)

    def test_timer_contacts_require_typed_known_members_and_contact_in_guard(self) -> None:
        args = capture(('TON(T,?,?);', '[XIC(T.DN),XIC(A)]XIO(T.TT)XIC(T.EN)OTE(D);',
                        'EQU(T.DN,1)XIC(T.ACC)OTE(B);', 'RES(T);'),
            tags=typed_tag('T') + tag('A') + tag('B') + tag('D'))
        result = args[-1]
        first, second = (row['guard_patterns'] for row in result.outputs)
        self.assertEqual({row['member'] for row in first['timer_contacts']}, {'DN', 'TT', 'EN'})
        self.assertTrue(all(row['object_id'] == args[10].objects[0]['id'] for row in first['timer_contacts']))
        self.assertEqual(second['timer_contacts'], [])
        self.assertEqual(result.coverage['pattern_outputs_with_timer_contacts'], 1)
        self.assertEqual(len(args[10].objects[0]['reset_ids']), 1)
        # The timer-free parallel branch remains in the guard; presence does
        # not imply that the timer contact is required on every path.
        self.assertTrue(result.outputs[0]['has_branch'])

    def test_timer_type_conflict_counter_unknown_and_out_of_bounds_do_not_qualify(self) -> None:
        cases = (
            (('TON(T,?,?);', 'XIC(T.DN)OTE(D);'), typed_tag('T', 'DINT')),
            (('CTU(T,?,?);', 'XIC(T.DN)OTE(D);'), typed_tag('T', 'COUNTER')),
            (('TON(T,?,?);', 'CTU(T,?,?);', 'XIC(T.DN)OTE(D);'), typed_tag('T')),
            (('TON(T[9],?,?);', 'XIC(T[9].DN)OTE(D);'), typed_tag('T', dimensions='2')),
            (('TON(T,?,?);', 'XIC(T.UNKNOWN)OTE(D);'), typed_tag('T')),
        )
        for texts, tags in cases:
            with self.subTest(texts=texts):
                result = capture(texts, tags=tags + tag('D'))[-1]
                self.assertEqual(result.outputs[0]['guard_patterns']['timer_contacts'], [])

    def test_foreign_contact_and_control_declarations_are_not_promoted(self) -> None:
        args = base_capture(('TON(T,?,?);', 'XIC(T.DN)XIC(D)OTE(D);'), tags=typed_tag('T') + tag('D'))
        xml = namespace(args[0].data.decode()).replace('Name="T" TagType=', 'Name="T" x:Marker="foreign" TagType=')
        result = capture_xml(xml)[-1]
        self.assertEqual(result.outputs[0]['guard_patterns']['timer_contacts'], [])
        self.assertEqual(result.outputs[0]['guard_quality'], 'namespace_gap')
        xml = namespace(args[0].data.decode()).replace('<RLLContent>', '<RLLContent x:Marker="foreign">')
        result = capture_xml(xml)[-1]
        self.assertEqual(result.outputs[0]['guard_patterns']['self_xic_read_ids'], [])
        self.assertEqual(result.coverage['pattern_coil_contexts_total'], 0)

    def test_shared_guard_walk_is_cached_and_duplicate_dag_nodes_are_not_counted_twice(self) -> None:
        one = capture(('[XIC(A),XIO(B)]XIC(D)OTE(D);',))[-1]
        many = capture(('[XIC(A),XIO(B)]XIC(D)' + 'OTE(D)' * 40 + ';',))[-1]
        self.assertEqual(many.coverage['pattern_unique_guards_total'], 1)
        self.assertEqual(many.coverage['pattern_visited_nodes'], one.coverage['pattern_visited_nodes'])
        self.assertEqual(many.coverage['pattern_visited_edges'], one.coverage['pattern_visited_edges'])
        self.assertEqual(many.coverage['pattern_self_contacts_by_kind']['xic'], 40)
        self.assertEqual(one.outputs[0]['guard_patterns']['self_xic_read_ids'], [one.condition_reads[-1]['id']])

    def test_all_resource_exhaustion_is_explicit_and_replayable(self) -> None:
        args = base_capture(('XIC(D)OTE(D);', 'XIO(D)OTE(D);'))
        for name in ('MAX_GUARD_PATTERN_NODES', 'MAX_GUARD_PATTERN_EDGES',
                'MAX_PATTERN_VISITED_NODES', 'MAX_PATTERN_VISITED_EDGES',
                'MAX_PATTERN_LINKS', 'MAX_PATTERN_CACHE_CONTACTS'):
            with self.subTest(name=name), patch(f'plc_workbench.signal_patterns.{name}', 0):
                result = analyze_signal_context(*args[:-1], schema_version=2)
                self.assertEqual(result.status, 'partial')
                self.assertGreater(result.coverage['pattern_traversals_by_status']['truncated'], 0)
                validate_signal_context(*args[:-1], result)

    def test_canonical_replay_rejects_forged_links_and_version_types(self) -> None:
        args = capture(('XIC(D)OTL(D);', 'OTU(D);'))
        for mutate in (lambda r: r.outputs[0]['guard_patterns']['self_xic_read_ids'].clear(),
                lambda r: r.addresses[0]['coil_contexts'][0].update(has_set_reset=False),
                lambda r: r.coverage.update(pattern_unique_guards_total=True)):
            broken = deepcopy(args[-1])
            mutate(broken)
            with self.assertRaises(SignalContextError):
                validate_signal_context(*args[:-1], broken)
        for version in (True, 0, 6, '2'):
            with self.subTest(version=version), self.assertRaises(SignalContextError):
                analyze_signal_context(*args[:-1], schema_version=version)
        for bound in ('MAX_SIGNAL_CONTEXT_V2_BYTES', 'MAX_SIGNAL_CONTEXT_V2_JSON_BYTES'):
            with patch(f'plc_workbench.signal_context.{bound}', 1), self.assertRaises(SignalContextError):
                render_signal_context_json(args[-1])


if __name__ == '__main__':
    unittest.main()
