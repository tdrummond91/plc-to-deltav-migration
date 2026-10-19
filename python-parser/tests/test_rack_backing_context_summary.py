"""Closed aggregate partitions for source rack correspondences."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench import rack_backing_context_summary as module
from plc_workbench.rack_backing_context import MAX_RECORDS
from plc_workbench.rack_backing_context_summary import (build_rack_backing_context_summary,
    validate_rack_backing_context_summary, render_rack_backing_context_summary,
    RackBackingContextSummaryError)
from plc_workbench.source_reuse import source_reuse_scope
from test_rack_backing_context import capture, fixture


def summary(text=None):
    return build_rack_backing_context_summary(*capture(text))


class RackBackingContextSummaryTests(unittest.TestCase):
    def setUp(self):
        scope = source_reuse_scope()
        scope.__enter__()
        self.addCleanup(scope.__exit__, None, None, None)

    def test_fixed_public_counts_no_source_evidence_and_revision_copy(self):
        parts = capture()
        revision = {'commit': 'a' * 40, 'worktree': 'modified'}
        result = build_rack_backing_context_summary(*parts, tool_revision=revision)
        revision['commit'] = 'b' * 40
        self.assertEqual(result['tool_revision']['commit'], 'a' * 40)
        self.assertEqual(result['coverage']['source_candidate_addresses'], 2)
        self.assertEqual(result['coverage']['source_candidate_uses'], 3)
        self.assertEqual(result['coverage']['source_sfc_binding_gaps'], 2)
        self.assertEqual(result['coverage']['uses_total'], 5)
        encoded = render_rack_backing_context_summary(result)
        self.assertEqual(result, json.loads(encoded))
        for raw in ('ProbeAlias', 'Remote', 'CNB', 'Data.0', '.Slot', '192.0.2', 'candidate_id',
                    'member_element_id', 'backing_suffix', parts[1].snapshot['id']):
            self.assertNotIn(raw, encoded)
        self.assertEqual(result['binding_effect'], 'independent_overlay')
        self.assertEqual(result['physical_mapping'], 'not_proven')

    def test_empty_and_partial_populations_have_exact_status(self):
        empty = '<RSLogix5000Content><Controller Name="Invented"/></RSLogix5000Content>'
        self.assertEqual(summary(empty)['status'], 'complete')
        partial = summary(fixture(sfc='Missing', rungs=('XIC(Remote:3:I.Data.32);',)))
        self.assertEqual(partial['status'], 'partial')
        self.assertEqual(partial['coverage']['rll_uses_by_disposition']['bit_out_of_range'], 1)
        self.assertEqual(partial['coverage']['sfc_uses_by_disposition']['non_rack_gap'], 1)

    def test_unknown_nested_keys_types_constants_and_revision_are_rejected(self):
        good = summary()
        changes = (
            lambda p: p.update(PRIVATE_SENTINEL=1),
            lambda p: p['coverage'].update(PRIVATE_SENTINEL=1),
            lambda p: p['coverage']['roots_by_disposition'].update(PRIVATE_SENTINEL=1),
            lambda p: p['coverage'].__setitem__('roots_total', True),
            lambda p: p['coverage']['roots_by_disposition'].__setitem__('associated', 2.0),
            lambda p: p.__setitem__('schema_version', True),
            lambda p: p.__setitem__('binding_effect', 'root_bound'),
            lambda p: p.__setitem__('physical_mapping', 'proven'),
            lambda p: p['tool_revision'].__setitem__('commit', 'PRIVATE_SENTINEL'),
        )
        for change in changes:
            forged = deepcopy(good)
            change(forged)
            with self.assertRaisesRegex(RackBackingContextSummaryError, '^Rack backing context summary validation failed'):
                validate_rack_backing_context_summary(forged)

    def test_count_conservation_and_feasible_populations_reject_mutations(self):
        good = summary()
        for key in ('source_rack_declarations', 'source_candidate_addresses', 'source_candidate_uses',
                    'source_candidate_roots', 'source_sfc_binding_gaps', 'roots_total',
                    'addresses_total', 'uses_total', 'rll_addresses', 'sfc_addresses', 'shared_addresses'):
            forged = deepcopy(good)
            forged['coverage'][key] += 1
            with self.subTest(key=key), self.assertRaises(RackBackingContextSummaryError):
                validate_rack_backing_context_summary(forged)
        for key in ('roots_by_direction', 'addresses_by_direction', 'roots_by_disposition',
                    'addresses_by_disposition', 'rll_uses_by_disposition', 'sfc_uses_by_disposition',
                    'associated_uses_by_role'):
            forged = deepcopy(good)
            first = next(iter(forged['coverage'][key]))
            forged['coverage'][key][first] += 1
            with self.subTest(key=key), self.assertRaises(RackBackingContextSummaryError):
                validate_rack_backing_context_summary(forged)
        forged = deepcopy(good)
        forged['coverage']['associated_predicate_uses'] = 3
        with self.assertRaises(RackBackingContextSummaryError):
            validate_rack_backing_context_summary(forged)
        forged = deepcopy(good)
        forged['coverage']['associated_sfc_addresses'] = 0
        with self.assertRaises(RackBackingContextSummaryError):
            validate_rack_backing_context_summary(forged)

    def test_forged_companion_cannot_be_summarized(self):
        parts = list(capture())
        parts[-1] = deepcopy(parts[-1])
        parts[-1].uses[0]['source_id'] = 'PRIVATE_SENTINEL'
        with self.assertRaises(RackBackingContextSummaryError):
            build_rack_backing_context_summary(*parts)

    def test_failed_roots_and_addresses_cannot_keep_successful_uses(self):
        good = summary(fixture(sfc=''))
        forged = deepcopy(good)
        c = forged['coverage']
        c['roots_by_disposition']['family_unsupported'] = c['roots_by_disposition']['associated']
        c['roots_by_disposition']['associated'] = 0
        c['addresses_by_disposition']['suffix_unsupported'] = c['addresses_by_disposition']['associated']
        c['addresses_by_disposition']['associated'] = 0
        c['rll_uses_by_disposition']['suffix_unsupported'] = c['rll_uses_by_disposition']['associated']
        c['rll_uses_by_disposition']['associated'] = 0
        c['associated_rll_addresses'] = c['associated_predicate_uses'] = c['associated_output_uses'] = 0
        c['associated_uses_by_role'] = dict.fromkeys(c['associated_uses_by_role'], 0)
        forged['status'] = 'partial'
        with self.assertRaises(RackBackingContextSummaryError):
            validate_rack_backing_context_summary(forged)
        forged = deepcopy(good)
        forged['coverage']['roots_by_direction'] = {'input': 2, 'output': 0}
        forged['coverage']['addresses_by_direction'] = {'input': 2, 'output': 0}
        with self.assertRaises(RackBackingContextSummaryError):
            validate_rack_backing_context_summary(forged)
        forged = deepcopy(good)
        c = forged['coverage']
        c['addresses_by_disposition']['associated'] -= 1
        c['addresses_by_disposition']['suffix_unsupported'] += 1
        c['associated_rll_addresses'] -= 1
        with self.assertRaises(RackBackingContextSummaryError):
            validate_rack_backing_context_summary(forged)

    def test_worst_width_and_exact_boundary_are_bounded(self):
        result = summary()
        # Every fixed field at its widest scalar width is a conservative byte
        # ceiling; it need not be a feasible count population.
        widest = deepcopy(result)
        widest['tool_revision'] = {'commit': 'f' * 40, 'worktree': 'unavailable'}
        for key, value in widest['coverage'].items():
            if type(value) is dict:
                for name in value:
                    value[name] = MAX_RECORDS
            else:
                widest['coverage'][key] = MAX_RECORDS
        width = len(json.dumps(widest, ensure_ascii=True, sort_keys=True, separators=(',', ':')) + '\n')
        self.assertLessEqual(width, module.MAX_REPORT_BYTES)
        size = len(render_rack_backing_context_summary(result))
        with patch.object(module, 'MAX_REPORT_BYTES', size):
            self.assertEqual(len(render_rack_backing_context_summary(result)), size)
        with patch.object(module, 'MAX_REPORT_BYTES', size - 1):
            with self.assertRaises(RackBackingContextSummaryError):
                render_rack_backing_context_summary(result)


if __name__ == '__main__':
    unittest.main()
