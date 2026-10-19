"""PID publication exposes a closed count schema, never private PID settings."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from plc_workbench.pid_summary import (
    CONSTANTS, PidSummaryError, build_pid_summary, render_pid_summary, validate_pid_summary,
)
from test_pid import DECORATED, PID_STRUCTURE, call, capture, capture_xml, tag


def summary(text: str = '', tags: str = '', namespace: str = ''):
    return build_pid_summary(*capture(text, tags, namespace))


class PidSummaryTests(unittest.TestCase):
    def test_closed_summary_is_small_deterministic_and_has_no_source_strings(self) -> None:
        inputs = capture(call('SecretLoop') + ';', tag(name='SecretLoop'))
        report = build_pid_summary(*inputs)
        self.assertEqual(set(report), set(CONSTANTS) | {'status', 'tool_revision', 'coverage'})
        self.assertEqual(report['schema_version'], 1)
        self.assertEqual(report['policy_version'], 2)
        self.assertEqual(report['report_kind'], 'l5x_pid_review_summary')
        rendered = render_pid_summary(report)
        self.assertEqual(json.loads(rendered), report)
        self.assertEqual(rendered, render_pid_summary(deepcopy(report)))
        self.assertLess(len(rendered.encode()), 5000)
        for secret in ('SecretLoop', 'Invented', '001.50', inputs[0].sha256,
                       inputs[-1].occurrences[0]['id'], inputs[-2].elements[0]['id']):
            self.assertNotIn(secret, rendered)
        self.assertEqual(report['semantic_analysis'], 'not_implemented')
        self.assertEqual(report['numeric_analysis'], 'not_implemented')

    def test_equal_evidence_shapes_rename_without_public_changes(self) -> None:
        first = summary(call('A') + ';', tag(name='A'))
        second = summary(call('B') + ';', tag(name='B').replace('001.50', '999.25'))
        self.assertEqual(first, second)

    def test_empty_population_and_source_parsing_gaps_have_exact_status(self) -> None:
        report = summary('XIC(Absent);')
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['coverage']['occurrences_total'], 0)
        self.assertEqual(report['coverage']['source_operands'], 1)
        validate_pid_summary(report)
        malformed = summary('PID(Loop')
        self.assertEqual(malformed['status'], 'partial')
        self.assertEqual(malformed['coverage']['unparsed_rungs'], 1)
        malformed['status'] = 'complete'
        with self.assertRaises(PidSummaryError):
            validate_pid_summary(malformed)

    def test_signature_and_storage_gaps_and_complete_multiple_roots_validate(self) -> None:
        cases = [
            ('PID();', ''), ('PID(Loop,PV);', tag()), ('PID(Loop,PV,,CV,0,0,0);', tag()),
            (call() + ';', tag('')), (call() + ';', tag(datatype='REAL')),
            (call() + ';', tag(attrs=' Dimensions="0"')),
            (call('Loop.SP') + ';', tag()), (call('Missing') + ';', ''),
            (call() + ';', tag('<Data Format="L5K">opaque</Data>')),
            (call() + ';', tag('<Data Format="Decorated"/>')),
        ]
        for text, tags in cases:
            with self.subTest(text=text, tags=tags):
                report = summary(text, tags)
                self.assertEqual(report['status'], 'partial')
                validate_pid_summary(report)
        report = summary(call() * 2 + ';', tag(f'<Data Format="Decorated">{PID_STRUCTURE * 2}</Data>'
                                              + DECORATED + '<Data Format="L5K">opaque</Data>'))
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['coverage']['structure_occurrences'], 6)
        self.assertEqual(report['coverage']['occurrences_with_multiple_representations'], 2)
        validate_pid_summary(report)

    def test_namespace_gaps_validate_without_importing_raw_namespace(self) -> None:
        cases = [
            tag().replace('<Tag ', '<x:Tag ').replace('</Tag>', '</x:Tag>'),
            tag().replace('DataType="PID"', 'x:DataType="PID"', 1),
            tag().replace('<Data ', '<x:Data ').replace('</Data>', '</x:Data>'),
            tag().replace('<Structure ', '<x:Structure ').replace('</Structure>', '</x:Structure>'),
        ]
        for declaration in cases:
            with self.subTest(declaration=declaration):
                report = summary(call() + ';', declaration, ' xmlns:x="urn:private-namespace"')
                self.assertEqual(report['status'], 'partial')
                self.assertNotIn('private-namespace', render_pid_summary(report))
        raw = capture(call() + ';', tag(), ' xmlns:x="urn:foreign"')[0].data.decode()
        report = build_pid_summary(*capture_xml(raw.replace('Name="P"', 'x:Name="P"')))
        self.assertEqual(report['coverage']['storage_by_status']['binding_namespace_unsupported'], 1)
        validate_pid_summary(report)

    def test_every_metadata_and_nested_key_boundary_is_closed(self) -> None:
        valid = summary(call() + ';', tag())
        mutations = (
            lambda s: s.update(schema_version=True),
            lambda s: s.update(policy_version=True),
            lambda s: s.update(private_name='SecretLoop'),
            lambda s: s.update(status=[]),
            lambda s: s.update(semantic_analysis='implemented'),
            lambda s: s['coverage'].update(occurrences_total=True),
            lambda s: s['coverage'].update(occurrences_total=1.0),
            lambda s: s['coverage'].update(occurrences_total=-1),
            lambda s: s['coverage'].update(occurrences_total=10**13),
            lambda s: s['coverage'].update(private=0),
            lambda s: s['coverage']['operands_by_slot'].update(setpoint=0),
            lambda s: s['coverage']['operands_by_binding'].update(root_bound=True),
            lambda s: s['coverage'].update(storage_by_status=s),
        )
        for mutate in mutations:
            forged = deepcopy(valid)
            mutate(forged)
            with self.subTest(mutate=mutate), self.assertRaisesRegex(
                    PidSummaryError, '^PID summary validation failed; no summary was produced\\.$'):
                validate_pid_summary(forged)

    def test_partition_totals_slot_counts_and_storage_status_are_reconciled(self) -> None:
        valid = summary(call() + ';', tag())
        for key, entry in (
            ('occurrences_by_signature', 'recognized'), ('operands_by_slot', 'process_variable'),
            ('operands_by_binding', 'root_bound'), ('storage_by_status', 'linked'),
        ):
            forged = deepcopy(valid)
            forged['coverage'][key][entry] += 1
            with self.subTest(key=key), self.assertRaises(PidSummaryError):
                validate_pid_summary(forged)
        forged = deepcopy(valid)
        forged['coverage']['operands_by_slot']['process_variable'] -= 1
        forged['coverage']['operands_by_slot']['unknown'] += 1
        with self.assertRaises(PidSummaryError):
            validate_pid_summary(forged)
        forged = deepcopy(valid)
        forged['status'] = 'partial'
        with self.assertRaises(PidSummaryError):
            validate_pid_summary(forged)

    def test_signature_binding_counts_cannot_imply_seven_argument_arity_mismatch(self) -> None:
        report = summary('PID(A,B,C,D,E,F);')
        c = report['coverage']
        for key in ('source_operands', 'operands_total'):
            c[key] = 7
        c['operands_by_slot']['unknown'] = 7
        c['operands_by_binding']['argument_count_mismatch'] = 7
        with self.assertRaises(PidSummaryError):
            validate_pid_summary(report)
        report = summary('PID(A,B,,D,E,F,G);')
        c = report['coverage']['operands_by_binding']
        c['empty'] -= 1
        c['unresolved'] += 1
        with self.assertRaises(PidSummaryError):
            validate_pid_summary(report)

    def test_presence_and_owner_counts_require_realizable_partitions(self) -> None:
        valid = summary(call() * 2 + ';', tag())
        mutations = (
            lambda c: c.update(distinct_backing_owners=3, backing_owners_with_data=3),
            lambda c: c.update(distinct_backing_owners=0, backing_owners_with_data=0),
            lambda c: c.update(occurrences_with_backing_owner=1),
            lambda c: c.update(occurrences_with_data=0, occurrences_without_data=2),
            lambda c: c.update(backing_owners_with_opaque_only=1),
            lambda c: c.update(occurrences_with_opaque_only=1),
            lambda c: c.update(occurrences_with_multiple_representations=1),
            lambda c: c.update(occurrences_with_multiple_structures=1),
            lambda c: c.update(source_instructions=1),
            lambda c: c.update(source_operands=13),
            lambda c: c.update(source_rungs=0),
        )
        for mutate in mutations:
            forged = deepcopy(valid)
            mutate(forged['coverage'])
            with self.subTest(mutate=mutate), self.assertRaises(PidSummaryError):
                validate_pid_summary(forged)

    def test_structure_member_and_representation_counts_have_positive_capacity(self) -> None:
        valid = summary(call() + ';', tag())
        mutations = (
            lambda c: c.update(structure_occurrences=0),
            lambda c: c.update(structure_occurrences=2),
            lambda c: c.update(representation_occurrences=0),
            lambda c: c.update(representation_occurrences=2),
            lambda c: c.update(decorated_representation_occurrences=0),
            lambda c: c.update(direct_member_occurrences=250001),
        )
        for mutate in mutations:
            forged = deepcopy(valid)
            mutate(forged['coverage'])
            with self.subTest(mutate=mutate), self.assertRaises(PidSummaryError):
                validate_pid_summary(forged)
        no_pid = summary('XIC(Loop);')
        no_pid['coverage']['direct_member_occurrences'] = 1
        with self.assertRaises(PidSummaryError):
            validate_pid_summary(no_pid)

    def test_summary_capacities_include_private_evidence_bytes(self) -> None:
        report = summary(call() * 2 + ';', tag(DECORATED + DECORATED))
        for constant, limit in (
            ('MAX_PID_OCCURRENCES', 1), ('MAX_PID_OPERANDS', 13),
            ('MAX_TAG_DATA_OWNERS', 0), ('MAX_TAG_DATA_CONTENTS', 1),
            ('MAX_TAG_DATA_ELEMENTS', 1), ('MAX_ELEMENTS', 0),
            ('MAX_PID_EVIDENCE_BYTES', 1), ('MAX_PID_JSON_BYTES', 1),
        ):
            with self.subTest(constant=constant), patch(f'plc_workbench.pid_summary.{constant}', limit):
                with self.assertRaises(PidSummaryError):
                    validate_pid_summary(report)
        with patch('plc_workbench.pid_summary.MAX_REPORT_BYTES', 100):
            with self.assertRaises(PidSummaryError):
                render_pid_summary(report)

    def test_builder_authenticates_every_layer_before_copying_or_rendering(self) -> None:
        inputs = capture(call() + ';', tag())
        for index, mutate in (
            (1, lambda value: value.counts.update(controller_tags=True)),
            (2, lambda value: value.operands[0].update(target_id='private-id')),
            (3, lambda value: value.contents[0].update(direct_text='private-setting')),
            (4, lambda value: value.occurrences.append(value.occurrences)),
            (4, lambda value: value.coverage.update(occurrences_total=True)),
        ):
            changed = list(deepcopy(inputs))
            mutate(changed[index])
            with self.subTest(index=index), self.assertRaises(PidSummaryError):
                build_pid_summary(*changed)
        other_snapshot = capture('XIC(Other);')[0]
        with self.assertRaises(PidSummaryError):
            build_pid_summary(other_snapshot, *inputs[1:])

    def test_revision_policy_is_closed_and_builder_does_not_alias_input(self) -> None:
        inputs = capture(call() + ';', tag())
        revision = {'commit': 'a' * 40, 'worktree': 'modified'}
        report = build_pid_summary(*inputs, revision=revision)
        revision['commit'] = 'b' * 40
        self.assertEqual(report['tool_revision']['commit'], 'a' * 40)
        for invalid in (
            {'commit': None, 'worktree': 'clean'}, {'commit': 'a' * 40, 'worktree': 'unavailable'},
            {'commit': True, 'worktree': 'modified'}, {'commit': 'A' * 40, 'worktree': 'clean'},
            {'commit': None, 'worktree': 'unavailable', 'secret': 'value'},
            {'commit': None, 'worktree': ['unavailable']},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(PidSummaryError):
                build_pid_summary(*inputs, revision=invalid)


if __name__ == '__main__':
    unittest.main()
