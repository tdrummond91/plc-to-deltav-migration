"""Publication counts remain closed, source-free and conservatively bounded."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.output_context_summary import (OutputContextSummaryError,
    build_output_context_summary, render_output_context_summary, validate_output_context_summary)
from test_output_context import capture, capture_xml, namespace
from test_relationships import tag


class OutputContextSummaryTests(unittest.TestCase):
    def test_canonical_summary_preserves_counts_without_names_values_or_ids(self) -> None:
        args = capture(('OTE(D);', 'MOV(923781,D)XIC(D)CPT(A,D+D)OTL(D);'))
        summary = build_output_context_summary(*args, revision={'commit': 'a' * 40, 'worktree': 'clean'})
        text = render_output_context_summary(summary)
        self.assertLess(len(text.encode()), 4096)
        self.assertEqual(json.loads(text), summary)
        self.assertEqual(summary['coverage'], args[-1].coverage)
        self.assertEqual(summary['exporter_version'], 'output-context-summary-1')
        for forbidden in ('923781', 'instruction_', 'condition_node_', 'operand_', 'Invented'):
            self.assertNotIn(forbidden, text)
        self.assertEqual(summary['coverage']['noncoil_writers_total'], 1)

    def test_empty_unparsed_gap_stateful_opaque_and_unknown_populations_validate(self) -> None:
        for text in (';', 'BROKEN(', 'XIC(A);', 'OTE();', 'ote(A);', 'XIC(Missing)OTE(D);',
                     'MYSTERY(A)OTE(D);', 'ONS(D)OTE(D);', 'OTE(D)PID(D,A,B,C,0,0,0);',
                     'OTE(Missing);', 'OTE(D[A]);', 'OTE(D)CPT(A,D+D);', '[XIC(D),]OTE(D);'):
            with self.subTest(text=text):
                args = capture((text,))
                summary = build_output_context_summary(*args)
                validate_output_context_summary(summary)
                self.assertEqual(summary['status'], args[-1].status)

    def test_namespace_rejections_and_authored_hint_qualification_validate(self) -> None:
        xml = capture(('OTE(D);', 'XIC(Bad)ONS(D)OTE(Bad);'), tags=tag('D') + tag('Bad', 'D'))[0].data.decode()
        args = capture_xml(namespace(xml).replace('AliasFor="D"', 'x:AliasFor="D"'))
        summary = build_output_context_summary(*args)
        self.assertEqual(summary['coverage']['targets_by_status']['namespace_gap'], 1)
        self.assertEqual(summary['coverage']['condition_read_statuses']['namespace_gap'], 2)
        xml = capture(rung_xml='<Rung><Comment>alarm pump sensor</Comment><Text>OTE(D);</Text></Rung>')[0].data.decode()
        args = capture_xml(namespace(xml).replace('<Comment>', '<x:Comment>').replace('</Comment>', '</x:Comment>'))
        summary = build_output_context_summary(*args)
        self.assertEqual(summary['coverage']['rungs_with_unqualified_hints'], 1)
        self.assertEqual(sum(summary['coverage']['unqualified_hints_by_category'].values()), 3)

    def test_foreign_keys_boolean_counts_invalid_revisions_and_constants_are_rejected(self) -> None:
        good = build_output_context_summary(*capture())
        for mutate in (lambda s: s.update(source_name='private'),
                       lambda s: s['coverage']['outputs_by_opcode'].update(SECRET=1),
                       lambda s: s['coverage'].update(source_rungs=True),
                       lambda s: s['coverage'].update(source_rungs=-1),
                       lambda s: s['tool_revision'].update(commit='private'),
                       lambda s: s['tool_revision'].update(worktree='private'),
                       lambda s: s.update(schema_version=True),
                       lambda s: s.update(execution_analysis='complete'),
                       lambda s: s.update(status='partial')):
            bad = deepcopy(good)
            mutate(bad)
            with self.assertRaises(OutputContextSummaryError):
                validate_output_context_summary(bad)

    def test_exact_output_address_read_and_role_partitions_are_enforced(self) -> None:
        good = build_output_context_summary(*capture(('XIC(D)OTE(D);', 'MOV(1,D)ONS(D)OTL(D);')))
        for field in ('outputs_total', 'source_outputs', 'output_rungs', 'rung_contexts_total',
                      'addresses_total', 'condition_reads_total', 'noncoil_writers_total'):
            bad = deepcopy(good)
            bad['coverage'][field] += 1
            with self.subTest(field=field), self.assertRaises(OutputContextSummaryError):
                validate_output_context_summary(bad)
        for group, key in (('outputs_by_opcode', 'OTE'), ('targets_by_status', 'exact_address'),
                           ('contexts_by_status', 'modeled'), ('guard_statuses', 'modeled'),
                           ('actions_by_status', 'recognized'), ('endpoint_kinds', 'tag'),
                           ('address_profiles', 'write_only'), ('accepted_operands_by_role', 'write'),
                           ('condition_read_kinds', 'predicate'), ('condition_read_statuses', 'accepted')):
            bad = deepcopy(good)
            bad['coverage'][group][key] += 1
            with self.subTest(group=group), self.assertRaises(OutputContextSummaryError):
                validate_output_context_summary(bad)

    def test_reader_writer_unknown_and_namespace_address_capacities_are_enforced(self) -> None:
        good = build_output_context_summary(*capture(('OTE(D)XIC(D);',)))
        for mutate in (lambda c: c.update(addresses_with_noncoil_writers=1),
                       lambda c: c.update(addresses_with_unknown_roles=1),
                       lambda c: c.update(addresses_with_namespace_uses=1),
                       lambda c: c.update(addresses_without_readers=1),
                       lambda c: c.update(addresses_with_multiple_coils=1),
                       lambda c: c.update(outputs_with_stateful_conditions=2),
                       lambda c: c.update(outputs_with_branches=2),
                       lambda c: c.update(source_operands=1),
                       lambda c: c.update(source_condition_nodes=0),
                       lambda c: c.update(accepted_expression_uses=1),
                       lambda c: c.update(rungs_with_hints=1)):
            bad = deepcopy(good)
            mutate(bad['coverage'])
            with self.assertRaises(OutputContextSummaryError):
                validate_output_context_summary(bad)

    def test_condition_statuses_and_hint_category_rung_capacity_are_enforced(self) -> None:
        args = capture(rung_xml='<Rung><Comment>alarm</Comment><Text>XIC(Missing)ONS(A)OTE(D);</Text></Rung>')
        good = build_output_context_summary(*args)
        for mutate in (lambda c: c['contexts_by_status'].update(binding_gaps=0, stateful=1),
                       lambda c: c['hints_by_category'].update(alarm=2),
                       lambda c: c['unqualified_hints_by_category'].update(alarm=1),
                       lambda c: c['targets_by_status'].update(exact_address=0, signature_unresolved=1)):
            bad = deepcopy(good)
            mutate(bad['coverage'])
            with self.assertRaises(OutputContextSummaryError):
                validate_output_context_summary(bad)

    def test_replay_authentication_and_private_public_size_limits_are_enforced(self) -> None:
        args = capture()
        broken = deepcopy(args[-1])
        broken.outputs[0]['target_operand_id'] = 'private-source'
        with self.assertRaises(OutputContextSummaryError) as caught:
            build_output_context_summary(*args[:-1], broken)
        self.assertNotIn('private-source', str(caught.exception))
        good = build_output_context_summary(*args)
        for name in ('MAX_OUTPUT_CONTEXT_RECORDS', 'MAX_OUTPUT_CONTEXT_BYTES', 'MAX_OUTPUT_CONTEXT_JSON_BYTES'):
            with patch(f'plc_workbench.output_context_summary.{name}', 1), self.assertRaises(OutputContextSummaryError):
                validate_output_context_summary(good)
        with patch('plc_workbench.output_context_summary.MAX_REPORT_BYTES', 20), self.assertRaises(OutputContextSummaryError):
            render_output_context_summary(good)


if __name__ == '__main__':
    unittest.main()
