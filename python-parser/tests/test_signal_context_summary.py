"""Signal summary counts remain closed, consistent, and source-free."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.signal_context_summary import (SignalContextSummaryError,
    build_signal_context_summary, render_signal_context_summary, validate_signal_context_summary)
from test_signal_context import capture, capture_xml, namespace, tag, typed_tag


class SignalContextSummaryTests(unittest.TestCase):
    def test_canonical_counts_only_summary(self) -> None:
        args = capture(('XIC(SecretPump)OTE(D);',), tags=tag('SecretPump') + tag('D'))
        summary = build_signal_context_summary(*args, revision={'commit': 'a' * 40, 'worktree': 'clean'})
        rendered = render_signal_context_summary(summary)
        self.assertEqual(json.loads(rendered), summary)
        self.assertEqual(summary['coverage'], args[-1].coverage)
        self.assertLessEqual(len(rendered.encode()), 8192)
        for forbidden in ('SecretPump', 'condition_node_', 'output_context_', 'content_locator',
                          'operand:', 'sha256:', 'raw_attributes'):
            self.assertNotIn(forbidden, rendered)

    def test_empty_partial_literal_stateful_and_namespace_cases_validate(self) -> None:
        for texts in ((';',), ('BROKEN(',), ('XIC(A);',), ('EQU(A,1)ONS(B)OTE(D);',),
                      ('OTE(Missing);',), ('XIC(Missing)OTE(D);',), ('MYSTERY(A)OTE(D);',),
                      ('OTE(A)MOV(B,A)CPT(B,A+A)PID(A,B,C,D,0,0,0);',)):
            with self.subTest(texts=texts):
                validate_signal_context_summary(build_signal_context_summary(*capture(texts)))
        args = capture(('TON(T,?,?);', 'XIC(T.DN)OTE(D);'), tags=typed_tag('T') + tag('D'))
        validate_signal_context_summary(build_signal_context_summary(*args))
        xml = namespace(args[0].data.decode()).replace('<Routine ', '<Routine x:Marker="foreign" ')
        validate_signal_context_summary(build_signal_context_summary(*capture_xml(xml)))

    def test_closed_keys_types_revisions_and_scope_constants(self) -> None:
        good = build_signal_context_summary(*capture())
        for mutate in (lambda s: s.update(source_name='private-marker'),
                       lambda s: s['coverage']['reads_by_kind'].update(SECRET=1),
                       lambda s: s['coverage'].update(source_rungs=True),
                       lambda s: s['coverage'].update(source_rungs=-1),
                       lambda s: s.update(schema_version=True),
                       lambda s: s.update(execution_analysis='complete'),
                       lambda s: s.update(status='partial'),
                       lambda s: s['tool_revision'].update(commit='private-marker'),
                       lambda s: s['tool_revision'].update(worktree='private-marker')):
            broken = deepcopy(good)
            mutate(broken)
            with self.assertRaises(SignalContextSummaryError) as caught:
                validate_signal_context_summary(broken)
            self.assertNotIn('private-marker', str(caught.exception))

    def test_exact_partitions_and_complete_predicate_intake(self) -> None:
        good = build_signal_context_summary(*capture(('XIC(A)EQU(B,1)ONS(C)OTE(D);',)))
        for key in ('outputs_total', 'condition_reads_total', 'addresses_total', 'rung_contexts_total',
                    'source_rungs', 'source_outputs', 'source_predicate_operands', 'source_ons_storage_operands',
                    'stateful_associations_total', 'noncoil_writers_total'):
            broken = deepcopy(good)
            broken['coverage'][key] += 1
            with self.subTest(key=key), self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(broken)
        for group in ('outputs_by_opcode', 'targets_by_status', 'guards_by_quality', 'reads_by_kind',
                      'reads_by_status', 'endpoint_kinds', 'address_profiles', 'rungs_by_qualification',
                      'stateful_associations_by_kind', 'stateful_associations_by_qualification'):
            broken = deepcopy(good)
            broken['coverage'][group][next(iter(broken['coverage'][group]))] += 1
            with self.subTest(group=group), self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(broken)

    def test_source_usage_hints_and_association_capacities(self) -> None:
        good = build_signal_context_summary(*capture())
        for mutate in (lambda c: c.update(source_rungs=0),
                       lambda c: c.update(source_instructions=0),
                       lambda c: c.update(source_operands=0),
                       lambda c: c.update(source_condition_nodes=0),
                       lambda c: c.update(source_addresses=0),
                       lambda c: c.update(source_stateful_objects=1_000_000),
                       lambda c: c.update(accepted_expression_uses=1),
                       lambda c: c.update(addresses_with_multiple_coils=1),
                       lambda c: c.update(addresses_with_noncoil_writers=1),
                       lambda c: c.update(addresses_with_unknown_roles=1),
                       lambda c: c.update(addresses_with_rejected_uses=1),
                       lambda c: c.update(outputs_with_branches=2),
                       lambda c: c.update(outputs_with_stateful_conditions=2),
                       lambda c: c.update(rungs_with_hints=1),
                       lambda c: c['hints_by_category'].update(equipment=1)):
            broken = deepcopy(good)
            mutate(broken['coverage'])
            with self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(broken)

    def test_replay_and_resource_caps(self) -> None:
        args = capture()
        broken = deepcopy(args[-1])
        broken.condition_reads[0]['kind'] = 'private-marker'
        with self.assertRaises(SignalContextSummaryError) as caught:
            build_signal_context_summary(*args[:-1], broken)
        self.assertNotIn('private-marker', str(caught.exception))
        good = build_signal_context_summary(*args)
        for name in ('MAX_SIGNAL_CONTEXT_RECORDS', 'MAX_SIGNAL_CONTEXT_BYTES',
                     'MAX_SIGNAL_CONTEXT_JSON_BYTES', 'MAX_EVIDENCE_IDS'):
            with patch(f'plc_workbench.signal_context_summary.{name}', 1), self.assertRaises(SignalContextSummaryError):
                validate_signal_context_summary(good)
        with patch('plc_workbench.signal_context_summary.MAX_REPORT_BYTES', 1), self.assertRaises(SignalContextSummaryError):
            render_signal_context_summary(good)


if __name__ == '__main__':
    unittest.main()
