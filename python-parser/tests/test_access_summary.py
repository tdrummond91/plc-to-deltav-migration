"""Publication tests for aggregate-only explicit operand access coverage."""
from __future__ import annotations

from copy import deepcopy
from itertools import product
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access
from plc_workbench.access_summary import (
    CONSTANTS, AccessSummaryError, build_access_summary, render_access_summary,
    validate_access_summary, _catalogue_capacity,
)
from plc_workbench.references import analyze_references
from test_access import source, tag


def report(text: str = 'XIC(A)MOV(A,B);', tags: str | None = None):
    inventory = source(text, tag('A') + tag('B') if tags is None else tags)
    references = analyze_references(inventory)
    result = analyze_access(inventory, references)
    return build_access_summary(inventory, references, result)


class AccessSummaryTests(unittest.TestCase):
    def test_report_contains_only_counts_fixed_metadata_status_and_revision(self) -> None:
        secret = 'PRIVATE_SENTINEL'
        inventory = source(f'XIC({secret}.Member)MOV(7263.125,{secret}){secret}();', tag(secret))
        references = analyze_references(inventory)
        result = analyze_access(inventory, references)
        summary = build_access_summary(inventory, references, result,
                                       revision={'commit': 'a' * 40, 'worktree': 'modified'})
        rendered = render_access_summary(summary)
        self.assertEqual(set(summary), set(CONSTANTS) | {'status', 'coverage', 'tool_revision'})
        for withheld in (secret, '7263.125', 'Member', inventory.snapshot['id'],
                         'XIC', 'MOV', result.instructions[0]['id'], result.operands[0]['id']):
            self.assertNotIn(withheld, rendered)
        self.assertEqual(json.loads(rendered), summary)
        self.assertEqual(summary['coverage']['instructions_total'], 3)
        self.assertEqual(summary['coverage']['operands_total'], 3)
        self.assertEqual(summary['status'], 'partial')

    def test_renaming_reordering_and_suffix_changes_do_not_leak_into_summary(self) -> None:
        first = report('XIC(A.Member)MOV(1,B);')
        second = report('MOV(2,Y.Other)XIC(X[999]);', tag('X') + tag('Y'))
        self.assertEqual(first, second)

    def test_binding_gaps_exactly_determine_status_with_other_coverage_gaps(self) -> None:
        for text, expected, gaps in (
            ('XIC(S:FS)MOV(1,A)JMP(Label);', 'complete', 0),
            ('MOV(1,2);', 'partial', 1), ('XIC(Missing);', 'partial', 1),
            ('AFI();', 'partial', 0), ('MOV(A,);', 'partial', 0),
            ('XIC(A', 'partial', 0), (';', 'complete', 0),
        ):
            with self.subTest(text=text):
                summary = report(text)
                self.assertEqual(summary['status'], expected)
                self.assertEqual(summary['coverage']['access_gap_operands'], gaps)
                forged = deepcopy(summary)
                forged['status'] = 'partial' if expected == 'complete' else 'complete'
                with self.assertRaises(AccessSummaryError):
                    validate_access_summary(forged)

    def test_validation_rejects_extra_keys_boolean_counts_cycles_and_types(self) -> None:
        mutations = [
            lambda s: s.update(name='PRIVATE_SENTINEL'),
            lambda s: s.update(schema_version=True),
            lambda s: s.update(status=[]),
            lambda s: s['coverage'].update(instructions_total=True),
            lambda s: s['coverage']['operands_by_role'].update(read=True),
            lambda s: s['coverage']['bound_by_role'].update(extra=0),
            lambda s: s['coverage'].update(operands_by_role=s),
            lambda s: s['tool_revision'].update(worktree=[]),
            lambda s: s['tool_revision'].update(commit='PRIVATE_SENTINEL'),
            lambda s: s['tool_revision'].update(extra=None),
            lambda s: s['coverage'].update(source_rungs=-1),
            lambda s: s['coverage'].update(source_rungs=10**12 + 1),
        ]
        for mutate in mutations:
            candidate = report()
            mutate(candidate)
            with self.subTest(mutation=mutate), self.assertRaisesRegex(AccessSummaryError, '^Access summary'):
                validate_access_summary(candidate)

    def test_partitions_capacities_and_bindings_are_checked(self) -> None:
        mutations = [
            lambda c: c.update(instructions_total=3),
            lambda c: c.update(operands_total=4),
            lambda c: c.update(linked_operands=2),
            lambda c: c.update(unlinked_operands=1),
            lambda c: c.update(indexed_roots=0),
            lambda c: c.update(indexed_roots=4),
            lambda c: c.update(unparsed_rungs=2),
            lambda c: c.update(source_rungs=0),
            lambda c: c.update(access_gap_operands=1),
            lambda c: c['bound_by_role'].update(read=3),
            lambda c: c['bound_by_role'].update(non_data=1),
            lambda c: (c['instructions_by_status'].update(classified=1), c.update(instructions_total=1),
                       c['operands_by_role'].update(read=0, write=3),
                       c['bound_by_role'].update(read=0, write=3)),
            lambda c: (c['operands_by_role'].update(read=0, unknown=2),
                       c['bound_by_role'].update(read=0, unknown=2)),
        ]
        for mutate in mutations:
            candidate = report()
            mutate(candidate['coverage'])
            with self.subTest(mutation=mutate), self.assertRaises(AccessSummaryError):
                validate_access_summary(candidate)

    def test_invalid_signature_counts_have_capacity_and_empty_argument_lower_bounds(self) -> None:
        summary = report('MOV(A,);')
        summary['coverage']['instructions_by_status']['empty_argument'] = 3
        summary['coverage']['instructions_total'] = 3
        with self.assertRaises(AccessSummaryError):
            validate_access_summary(summary)
        summary = report('MOV(A,);')
        coverage = summary['coverage']
        coverage.update(operands_total=4, unlinked_operands=3)
        coverage['operands_by_role']['unknown'] = 4
        with self.assertRaises(AccessSummaryError):
            validate_access_summary(summary)

    def test_partition_coherent_but_impossible_classified_role_combinations_fail(self) -> None:
        # Three slots still partition and bind correctly, but SWPB's selector
        # can never coexist with read-write storage in one classified signature.
        summary = report('SWPB(A,REVERSE,A);')
        summary['coverage']['operands_by_role'].update(read=0, read_write=1)
        summary['coverage']['bound_by_role'].update(read=0, read_write=1)
        with self.assertRaises(AccessSummaryError):
            validate_access_summary(summary)
        # A read-write instruction contributes zero (ONS/OSR) or two (MVM)
        # reads. The odd read cannot fit when every instruction has storage.
        for text in ('ONS(A);', 'ONS(A)ONS(A);'):
            summary = report(text)
            coverage = summary['coverage']
            coverage['operands_by_role']['read'] = 1
            coverage['bound_by_role']['read'] = 1
            coverage['operands_total'] += 1
            coverage['linked_operands'] += 1
            with self.subTest(text=text), self.assertRaises(AccessSummaryError):
                validate_access_summary(summary)

    def test_closed_form_capacity_matches_exhaustive_small_signature_combinations(self) -> None:
        # Independently enumerate the eleven allowed (read, write, RW, selector)
        # shapes and all aggregate counts through six instructions. Infeasible
        # vectors are included; this checks the arithmetic capacity derivation.
        signatures = {
            (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 1, 1, 0),
            (1, 1, 0, 0), (2, 0, 1, 0), (1, 1, 0, 1), (2, 1, 0, 0),
            (2, 0, 0, 0), (3, 0, 0, 0), (0, 0, 0, 1),
        }
        possible = {(0, 0, 0, 0)}
        for instructions in range(7):
            for vector in product(range(3 * instructions + 1), *[range(instructions + 1)] * 3):
                roles = dict(zip(('read', 'write', 'read_write', 'non_data'), vector, strict=True))
                self.assertEqual(_catalogue_capacity(instructions, roles), vector in possible,
                                 (instructions, vector))
            possible = {tuple(a + b for a, b in zip(vector, signature, strict=True))
                        for vector in possible for signature in signatures}

    def test_builder_authenticates_before_projection_and_error_is_source_free(self) -> None:
        inventory = source('XIC(A);', tag('A'))
        references = analyze_references(inventory)
        result = analyze_access(inventory, references)
        result.operands[0]['role'] = 'PRIVATE_SENTINEL'
        with self.assertRaises(AccessSummaryError) as context:
            build_access_summary(inventory, references, result)
        self.assertNotIn('PRIVATE_SENTINEL', str(context.exception))

    def test_revision_and_coverage_are_copied_and_render_size_is_bounded(self) -> None:
        inventory = source('XIC(A);', tag('A'))
        references = analyze_references(inventory)
        result = analyze_access(inventory, references)
        revision = {'commit': 'b' * 40, 'worktree': 'clean'}
        summary = build_access_summary(inventory, references, result, revision=revision)
        revision['worktree'] = 'modified'
        result.coverage['operands_by_role']['read'] = 999
        self.assertEqual(summary['tool_revision']['worktree'], 'clean')
        self.assertEqual(summary['coverage']['operands_by_role']['read'], 1)
        with patch('plc_workbench.access_summary.MAX_REPORT_BYTES', 10):
            with self.assertRaises(AccessSummaryError):
                render_access_summary(summary)


if __name__ == '__main__':
    unittest.main()
