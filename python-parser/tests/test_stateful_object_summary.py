"""Closed aggregate partitions expose gaps without publishing source evidence."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.stateful_object_summary import (StatefulObjectSummaryError,
    build_stateful_object_summary, render_stateful_object_summary, validate_stateful_object_summary)
from test_stateful_objects import capture, capture_xml, decorated, namespace, typed_tag
from test_relationships import tag


class StatefulObjectSummaryTests(unittest.TestCase):
    def test_canonical_closed_counts_have_no_source_names_values_or_ids(self) -> None:
        args = capture(('TON(PrivateClock,923456,654321)RES(PrivateClock)XIC(PrivateClock.DN);',),
                       tags=typed_tag('PrivateClock', data=decorated()))
        summary = build_stateful_object_summary(*args, revision={'commit': 'a' * 40, 'worktree': 'clean'})
        text = render_stateful_object_summary(summary)
        self.assertEqual(json.loads(text), summary)
        self.assertEqual(summary['coverage'], args[-1].coverage)
        self.assertLess(len(text.encode()), 4096)
        for secret in ('PrivateClock', '923456', '654321', '712345', 'instruction_', 'relationship_address_', 'tag_data_element_'):
            self.assertNotIn(secret, text)

    def test_empty_unparsed_malformed_and_mixed_source_populations_validate(self) -> None:
        cases = (';', 'BROKEN(', 'TON();', 'TON(T,?,?);', 'TON(T,?,?)CTU(T,?,?)RES(T);',
            'RES(R);', 'RES(A);', 'XIC(Missing)TON(T,?,?);', 'ONS(A)TON(T,?,?);',
            'MYSTERY(A)TON(T,?,?);', 'TON(T,?,?)PID(T,A,B,C,0,0,0);',
            'TON(T.Nested,?,?)TON(T.Nested.Deeper,?,?)XIC(T.Nested.Deeper.DN);',
            'TON(T,?,?)CPT(B,T.ACC+T.ACC);')
        for text in cases:
            with self.subTest(text=text):
                args = capture((text,))
                summary = build_stateful_object_summary(*args)
                validate_stateful_object_summary(summary)
                self.assertEqual(summary['status'], args[-1].status)

    def test_namespace_rejected_members_and_conflicting_stored_types_validate(self) -> None:
        args = capture(('TON(T,?,?);', 'XIC(Bad)RES(T);'),
            tags=typed_tag('T', data=decorated() + decorated('COUNTER')) + tag('Bad', 'T.DN'))
        xml = namespace(args[0].data.decode()).replace('AliasFor="T.DN"', 'x:AliasFor="T.DN"')
        summary = build_stateful_object_summary(*capture_xml(xml))
        self.assertEqual(summary['coverage']['rejected_operands_by_role']['read'], 1)
        self.assertEqual(summary['coverage']['stored_types_by_status']['mismatch'], 3)

    def test_foreign_keys_booleans_negative_counts_bad_constants_and_revisions_rejected(self) -> None:
        good = build_stateful_object_summary(*capture())
        for mutate in (lambda s: s.update(private='value'),
                       lambda s: s['coverage']['occurrences_by_opcode'].update(SECRET=1),
                       lambda s: s['coverage'].update(source_rungs=True),
                       lambda s: s['coverage'].update(source_rungs=-1),
                       lambda s: s.update(schema_version=True),
                       lambda s: s.update(execution_analysis='implemented'),
                       lambda s: s.update(status='partial'),
                       lambda s: s['tool_revision'].update(commit='secret'),
                       lambda s: s['tool_revision'].update(worktree='secret')):
            bad = deepcopy(good)
            mutate(bad)
            with self.assertRaises(StatefulObjectSummaryError):
                validate_stateful_object_summary(bad)

    def test_exact_partitions_and_link_population_bounds_reject_tampering(self) -> None:
        good = build_stateful_object_summary(*capture(tags=tag('A') + typed_tag('T', data=decorated())))
        for field in ('occurrences_total', 'objects_total', 'address_uses_total', 'stored_data_total',
                      'producer_occurrences', 'reset_occurrences', 'matched_reset_occurrences',
                      'objects_with_resets', 'objects_with_data', 'objects_without_data'):
            bad = deepcopy(good)
            bad['coverage'][field] += 1
            with self.subTest(field=field), self.assertRaises(StatefulObjectSummaryError):
                validate_stateful_object_summary(bad)
        for group, key in (('occurrences_by_opcode', 'TON'), ('targets_by_status', 'exact_address'),
                           ('contexts_by_status', 'modeled'), ('objects_by_family', 'timer'),
                           ('declarations_by_kind', 'timer'), ('bounds_by_status', 'scalar'),
                           ('uses_by_kind', 'whole_control'), ('members_by_status', 'known'),
                           ('stored_data_by_status', 'qualified'), ('stored_types_by_status', 'matching')):
            bad = deepcopy(good)
            bad['coverage'][group][key] += 1
            with self.subTest(group=group), self.assertRaises(StatefulObjectSummaryError):
                validate_stateful_object_summary(bad)
        bad = deepcopy(good)
        bad['coverage']['accepted_operands_by_role']['read_write'] = 0
        with self.assertRaises(StatefulObjectSummaryError):
            validate_stateful_object_summary(bad)

    def test_nested_object_associations_may_repeat_source_operands_without_false_unique_claims(self) -> None:
        args = capture(('TON(T,?,?)TON(T.Nested,?,?)XIC(T.Nested.DN)CPT(B,T.Nested.ACC+T.Nested.ACC);',))
        summary = build_stateful_object_summary(*args)
        self.assertEqual(summary['coverage']['accepted_expression_uses'], 4)
        self.assertEqual(summary['coverage']['source_expression_uses'], 2)
        validate_stateful_object_summary(summary)

    def test_resource_counts_and_serialization_limit_reject_source_free(self) -> None:
        args = capture()
        summary = build_stateful_object_summary(*args)
        bad = deepcopy(summary)
        bad['coverage']['source_data_elements'] = 250_001
        with self.assertRaises(StatefulObjectSummaryError):
            validate_stateful_object_summary(bad)
        bad = deepcopy(summary)
        bad['coverage']['accepted_operands_by_role']['read'] = 300_000
        with self.assertRaises(StatefulObjectSummaryError):
            validate_stateful_object_summary(bad)
        with patch('plc_workbench.stateful_object_summary.MAX_REPORT_BYTES', 1), self.assertRaises(StatefulObjectSummaryError):
            render_stateful_object_summary(summary)
        broken = deepcopy(args[-1])
        broken.objects[0]['family'] = 'secret'
        with self.assertRaises(StatefulObjectSummaryError) as caught:
            build_stateful_object_summary(*args[:-1], broken)
        self.assertNotIn('secret', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
