"""Closed candidate counts retain exact source populations without identities."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.signal_context_summary import (MAX_REPORT_V5_BYTES, SignalContextSummaryError,
    build_signal_context_summary, render_signal_context_summary, validate_signal_context_summary)
from test_signal_candidates import capture, capture_xml, described, namespace, tag, MODULES


class SignalCandidateSummaryTests(unittest.TestCase):
    def test_closed_counts_distinguish_pairs_targets_categories_and_visits(self) -> None:
        args = capture(('XIC(PrivateSource)XIO(PrivateSource)OTE(PrivateTarget);',),
            tags=described('PrivateSource', 'alarm sensor') + described('PrivateTarget', 'pump alarm'))
        summary = build_signal_context_summary(*args)
        rendered = render_signal_context_summary(summary)
        c = summary['coverage']
        self.assertEqual(summary['schema_version'], 5)
        self.assertEqual(c['candidate_pairs_total'], 2)
        self.assertEqual(c['candidate_outputs_with_pairs'], 1)
        self.assertEqual(c['candidate_outputs_with_target_categories'], 1)
        self.assertEqual(c['candidate_pairs_by_seed'], {'both': 2, 'condition_only': 0, 'target_only': 0})
        self.assertEqual(c['candidate_target_categories']['alarm'], 1)
        self.assertEqual(c['candidate_condition_categories']['alarm'], 2)
        self.assertEqual(c['candidate_index_category_links'], 6)
        for forbidden in ('PrivateSource', 'PrivateTarget', 'candidate_context', 'condition_read_id', 'content_locator'):
            self.assertNotIn(forbidden, rendered)

    def test_empty_unconditional_unbound_and_stateful_cases_validate(self) -> None:
        for text in (';', 'BROKEN(', 'XIC(A);', 'OTE(Pump);', 'XIC(Alarm)OTE(Missing);',
                'EQU(1,2)XIC(S:FS)OTE(Pump);', 'XIC(Missing)OTE(Pump);',
                'XIC(Alarm)MYSTERY(A)OTE(Pump);', 'XIC(Alarm)ONS(A)OTL(Pump);'):
            with self.subTest(text=text):
                validate_signal_context_summary(build_signal_context_summary(*capture((text,),
                    tags=tag('A') + tag('Pump') + tag('Alarm'))))

    def test_module_seed_counts_do_not_require_authored_wording(self) -> None:
        summary = build_signal_context_summary(*capture(('XIC(M:I.Data.0)OTE(M:O.Data.1);',), modules=MODULES))
        c = summary['coverage']
        self.assertEqual(c['candidate_authored_link_visits'], 0)
        self.assertEqual(c['candidate_index_category_links'], 0)
        self.assertEqual(c['candidate_condition_categories']['module_input'], 1)
        self.assertEqual(c['candidate_target_categories']['module_output'], 1)
        validate_signal_context_summary(summary)

    def test_closed_maps_false_types_ranges_and_impossible_populations_are_rejected(self) -> None:
        good = build_signal_context_summary(*capture(('XIC(Alarm)XIO(Alarm)OTE(Pump);',),
            tags=tag('Alarm') + tag('Pump')))
        changes = (
            lambda c: c['candidate_target_categories'].update(secret=1),
            lambda c: c['candidate_scans_by_status'].update(complete=99),
            lambda c: c.update(candidate_pairs_total=True),
            lambda c: c.update(candidate_pairs_total=-1),
            lambda c: c.update(candidate_pairs_total=10**12 + 1),
            lambda c: c.update(candidate_pairs_total=1),
            lambda c: c.update(candidate_outputs_with_pairs=0),
            lambda c: c.update(candidate_outputs_with_target_categories=0),
            lambda c: c.update(candidate_authored_link_visits=0),
            lambda c: c.update(candidate_index_category_links=0),
            lambda c: c.update(candidate_index_category_links=100001),
            lambda c: c.update(candidate_dependency_visits=0),
            lambda c: c['candidate_pairs_by_seed'].update(target_only=3),
            lambda c: c['candidate_pairs_by_kind'].update(xic=3),
            lambda c: c['candidate_pairs_by_guard_quality'].update(modeled=0, namespace_gap=2),
            lambda c: c['candidate_target_categories'].update(module_input=1),
            lambda c: c['candidate_condition_categories'].update(module_output=1),
            lambda c: c['candidate_condition_categories'].update(alarm=0),
            lambda c: c['candidate_target_categories'].update(equipment=2),
        )
        for index, mutate in enumerate(changes):
            broken = deepcopy(good)
            mutate(broken['coverage'])
            with self.subTest(change=index), self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(broken)
        two_targets = build_signal_context_summary(*capture(('XIC(A)OTE(Pump);', 'XIC(A)OTE(Pump);'),
            tags=tag('A') + tag('Pump')))
        two_targets['coverage']['candidate_outputs_with_target_categories'] = 1
        two_targets['coverage']['candidate_target_categories']['equipment'] = 1
        with self.assertRaises(SignalContextSummaryError):
            validate_signal_context_summary(two_targets)
        module_summary = build_signal_context_summary(*capture(('XIC(M:I.Data.0)OTE(M:O.Data.1);',), modules=MODULES))
        for map_key, opposite in (('candidate_condition_categories', 'module_output'),
                ('candidate_target_categories', 'module_input')):
            broken = deepcopy(module_summary)
            broken['coverage'][map_key][opposite] = 1
            with self.subTest(map_key=map_key), self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(broken)

    def test_all_candidate_limits_keep_partial_summaries_replayable(self) -> None:
        for cap in ('MAX_CANDIDATE_AUTHORED_VISITS', 'MAX_CANDIDATE_INDEX_LINKS',
                'MAX_CANDIDATE_DEPENDENCY_VISITS', 'MAX_CANDIDATE_PAIRS', 'MAX_CANDIDATE_BYTES'):
            with self.subTest(cap=cap), patch(f'plc_workbench.signal_candidates.{cap}', 0):
                summary = build_signal_context_summary(*capture(('XIC(Alarm)OTE(Pump);',),
                    tags=tag('Alarm') + tag('Pump')))
            validate_signal_context_summary(summary)
            self.assertEqual(summary['status'], 'partial')
            summary['status'] = 'complete'
            with self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(summary)

    def test_partial_pair_budget_and_inherited_scans_remain_valid(self) -> None:
        for module, cap in (('signal_candidates', 'MAX_CANDIDATE_PAIRS'),
                ('signal_dependencies', 'MAX_DEPENDENCY_LINKS'), ('signal_authored', 'MAX_AUTHORED_USE_VISITS')):
            with self.subTest(cap=cap), patch(f'plc_workbench.{module}.{cap}', 1):
                summary = build_signal_context_summary(*capture(('XIC(Alarm)XIO(Alarm)OTE(Pump);',),
                    tags=tag('Alarm') + tag('Pump')))
            validate_signal_context_summary(summary)
            self.assertEqual(summary['coverage']['candidate_scans_by_status']['truncated'], 1)

    def test_maximum_width_counts_fit_versioned_summary_budget(self) -> None:
        summary = build_signal_context_summary(*capture(('XIC(Alarm)OTE(Pump);',),
            tags=tag('Alarm') + tag('Pump')))
        summary['tool_revision'] = {'commit': 'f' * 40, 'worktree': 'unavailable'}
        for key, value in summary['coverage'].items():
            summary['coverage'][key] = {name: 10**12 for name in value} if isinstance(value, dict) else 10**12
        # Deliberately inconsistent counts give a conservative serialized width;
        # this is not a report accepted for publication.
        self.assertLess(len((json.dumps(summary, indent=2, sort_keys=True) + '\n').encode()), MAX_REPORT_V5_BYTES)

    def test_versioned_caps_and_canonical_candidate_links_are_authenticated(self) -> None:
        args = capture(('XIC(Alarm)OTE(Pump);',), tags=tag('Alarm') + tag('Pump'))
        good = build_signal_context_summary(*args)
        for cap in ('MAX_SIGNAL_CONTEXT_V5_BYTES', 'MAX_SIGNAL_CONTEXT_V5_JSON_BYTES',
                'MAX_CANDIDATE_AUTHORED_VISITS', 'MAX_CANDIDATE_INDEX_LINKS',
                'MAX_CANDIDATE_DEPENDENCY_VISITS', 'MAX_CANDIDATE_PAIRS', 'MAX_CANDIDATE_BYTES'):
            with self.subTest(cap=cap), patch(f'plc_workbench.signal_context_summary.{cap}', 0), self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(good)
        with patch('plc_workbench.signal_context_summary.MAX_REPORT_V5_BYTES', 1), self.assertRaises(SignalContextSummaryError):
            render_signal_context_summary(good)
        broken = deepcopy(args[-1])
        broken.outputs[0]['candidate_context']['conditions'][0]['categories'].clear()
        with self.assertRaises(SignalContextSummaryError):
            build_signal_context_summary(*args[:-1], broken)


if __name__ == '__main__':
    unittest.main()
