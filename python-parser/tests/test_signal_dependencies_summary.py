"""Closed counts authenticate direct memberships without exporting addresses."""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from plc_workbench.signal_context_summary import (SignalContextSummaryError,
    build_signal_context_summary, render_signal_context_summary, validate_signal_context_summary)
from test_signal_dependencies import capture, capture_xml, namespace, tag


class SignalDependencySummaryTests(unittest.TestCase):
    def test_counts_only_summary_retains_source_population_and_membership_counts(self) -> None:
        args = capture(('XIC(PrivateAlarm)XIO(PrivateAlarm)OTE(PrivatePump);',),
            tags=tag('PrivateAlarm') + tag('PrivatePump'))
        summary = build_signal_context_summary(*args)
        rendered = render_signal_context_summary(summary)
        self.assertEqual(summary['schema_version'], 4)
        self.assertEqual(summary['coverage']['condition_reads_total'], 2)
        self.assertEqual(summary['coverage']['dependency_read_links_total'], 2)
        self.assertEqual(summary['coverage']['dependency_reverse_links_total'], 1)
        self.assertLess(len(rendered.encode('utf-8')), 20 * 1024)
        for text in ('PrivateAlarm', 'PrivatePump', 'condition_read_ids', 'dependent_output_ids',
                'condition_node_', 'content_locator', 'output_context_'):
            self.assertNotIn(text, rendered)

    def test_empty_unconditional_literal_only_and_unresolved_cases_validate(self) -> None:
        for texts in ((';',), ('BROKEN(',), ('XIC(A);',), ('OTE(D);',), ('XIC(A)OTE(Missing);',),
                ('EQU(1,2)XIC(S:FS)OTE(D);',), ('XIC(Missing)OTE(D);',),
                ('XIC(A)MYSTERY(B)OTE(D);',), ('XIC(A)ONS(B)OTE(D);',)):
            with self.subTest(texts=texts):
                validate_signal_context_summary(build_signal_context_summary(*capture(texts)))

    def test_namespace_guard_retains_read_counts_but_zero_reverse_links(self) -> None:
        xml = namespace(capture(('[XIC(A),XIC(B)]OTE(D);',))[0].data.decode())
        xml = xml.replace('Name="B" TagType=', 'Name="B" x:Marker="foreign" TagType=')
        summary = build_signal_context_summary(*capture_xml(xml))
        self.assertEqual(summary['coverage']['dependency_outputs_with_exact_reads'], 1)
        self.assertEqual(summary['coverage']['dependency_outputs_with_dependents'], 0)
        validate_signal_context_summary(summary)
        summary['coverage']['dependency_reverse_links_by_guard_quality']['namespace_gap'] = 1
        with self.assertRaises(SignalContextSummaryError):
            validate_signal_context_summary(summary)

    def test_closed_maps_impossible_populations_and_false_types_are_rejected(self) -> None:
        good = build_signal_context_summary(*capture(('XIC(A)XIO(A)OTE(D);', 'OTE(B);')))
        changes = (
            lambda c: c['dependency_traversals_by_status'].update(secret=1),
            lambda c: c['dependency_traversals_by_status'].update(complete=99),
            lambda c: c.update(dependency_unique_guards_total=0),
            lambda c: c.update(dependency_visited_nodes=0),
            lambda c: c.update(dependency_visited_edges=10**10),
            lambda c: c.update(dependency_cached_read_ids=0),
            lambda c: c.update(dependency_cached_read_ids=100001),
            lambda c: c.update(dependency_read_links_total=1),
            lambda c: c.update(dependency_reverse_links_total=0),
            lambda c: c.update(dependency_outputs_with_reads=0),
            lambda c: c.update(dependency_outputs_with_exact_reads=0),
            lambda c: c.update(dependency_outputs_with_dependents=0),
            lambda c: c.update(dependency_addresses_with_dependents=0),
            lambda c: c.update(dependency_outputs_without_reads_complete=0),
            lambda c: c.update(dependency_visited_nodes=True),
            lambda c: c['dependency_reads_by_kind'].update(xic=2, xio=0),
            lambda c: c['dependency_reads_by_status'].update(exact_address=0, literal=2),
            lambda c: c['dependency_outputs_with_reads_by_guard_quality'].update(modeled=0, stateful=1),
            lambda c: c['dependency_reverse_links_by_guard_quality'].update(modeled=0, namespace_gap=1),
        )
        for index, mutate in enumerate(changes):
            broken = deepcopy(good)
            mutate(broken['coverage'])
            with self.subTest(change=index), self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(broken)

    def test_all_truncation_modes_keep_partial_summaries_valid(self) -> None:
        for cap in ('MAX_GUARD_DEPENDENCY_NODES', 'MAX_GUARD_DEPENDENCY_EDGES',
                'MAX_DEPENDENCY_VISITED_NODES', 'MAX_DEPENDENCY_VISITED_EDGES',
                'MAX_DEPENDENCY_LINKS', 'MAX_DEPENDENCY_CACHE_READS'):
            with self.subTest(cap=cap), patch(f'plc_workbench.signal_dependencies.{cap}', 0):
                summary = build_signal_context_summary(*capture(('XIC(A)OTE(D);',)))
            validate_signal_context_summary(summary)
            self.assertEqual(summary['status'], 'partial')
            summary['status'] = 'complete'
            with self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(summary)

    def test_forward_reverse_atomic_retention_respects_summary_equations(self) -> None:
        for limit in (1, 2, 3):
            with self.subTest(limit=limit), patch('plc_workbench.signal_dependencies.MAX_DEPENDENCY_LINKS', limit):
                summary = build_signal_context_summary(*capture(('XIC(A)XIO(A)OTE(D);',)))
            validate_signal_context_summary(summary)
            c = summary['coverage']
            self.assertLessEqual(c['dependency_read_links_total'] + c['dependency_reverse_links_total'], limit)

    def test_versioned_caps_and_canonical_indices_are_authenticated(self) -> None:
        args = capture(('XIC(A)OTE(D);',))
        good = build_signal_context_summary(*args)
        for cap in ('MAX_SIGNAL_CONTEXT_V4_BYTES', 'MAX_SIGNAL_CONTEXT_V4_JSON_BYTES'):
            with self.subTest(cap=cap), patch(f'plc_workbench.signal_context_summary.{cap}', 1), self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(good)
        with patch('plc_workbench.signal_context_summary.MAX_REPORT_V4_BYTES', 1), self.assertRaises(SignalContextSummaryError):
            render_signal_context_summary(good)
        for cap in ('MAX_DEPENDENCY_LINKS', 'MAX_DEPENDENCY_CACHE_READS',
                'MAX_GUARD_DEPENDENCY_NODES', 'MAX_GUARD_DEPENDENCY_EDGES',
                'MAX_DEPENDENCY_VISITED_NODES', 'MAX_DEPENDENCY_VISITED_EDGES'):
            with self.subTest(cap=cap), patch(f'plc_workbench.signal_context_summary.{cap}', 0), self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(good)
        broken = deepcopy(args[-1])
        broken.outputs[0]['guard_dependencies']['condition_read_ids'].clear()
        with self.assertRaises(SignalContextSummaryError):
            build_signal_context_summary(*args[:-1], broken)


if __name__ == '__main__':
    unittest.main()
