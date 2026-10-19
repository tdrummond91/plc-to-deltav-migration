"""Closed aggregate contract for the extended explicit-access catalogue."""
from __future__ import annotations

from copy import deepcopy
from itertools import product
import json
import unittest

from plc_workbench.access import analyze_access
from plc_workbench.access_summary import (
    CONSTANTS, VERSION2_CONSTANTS, AccessSummaryError, build_access_summary,
    render_access_summary, validate_access_summary,
)
from plc_workbench.references import analyze_references
from test_access import source, tag
from test_access_summary import legacy_report


def report(text: str, version: int = 3, tags: str | None = None):
    inventory = source(text, tag('A') if tags is None else tags)
    references = analyze_references(inventory)
    return build_access_summary(inventory, references,
                                analyze_access(inventory, references, schema_version=version))


class ExtendedAccessSummaryTests(unittest.TestCase):
    def test_closed_summary_publishes_no_source_spelling_or_identifier(self) -> None:
        summary = report('CTU(SECRET,?,16#BEEF)MSG(SECRET.Member)GSV(SECRET,,SECRET,SECRET)'
                         'SSV(SECRET,,SECRET,12345)SFR(SECRET,0)SFR(SECRET,SECRET.Member);',
                         tags=tag('SECRET'))
        self.assertEqual(set(summary), set(CONSTANTS) | {'status', 'coverage', 'tool_revision'})
        self.assertEqual((summary['schema_version'], summary['exporter_version']), (3, 'access-summary-3'))
        self.assertEqual(summary['coverage']['extended_instructions'], {
            'counter': 1, 'message': 1, 'system_get': 1, 'system_set': 1,
            'sfc_reset_step': 1, 'sfc_reset_initial': 1})
        self.assertEqual(summary['coverage']['extended_bound_operands'], 4)
        rendered = render_access_summary(summary)
        for withheld in ('SECRET', 'Member', 'BEEF', '12345', 'CTU', 'MSG', 'GSV', 'SSV', 'SFR',
                         'alias_chain', 'binding_reason'):
            self.assertNotIn(withheld, rendered)
        self.assertNotRegex(rendered, r'(?:operand|entity|rung)_[0-9a-f]{64}')
        self.assertEqual(json.loads(rendered), summary)

    def test_frozen_versions_reject_all_new_fields_and_current_metadata(self) -> None:
        for old in (legacy_report(), report('TON(A,?,0)MSG(A);', version=2)):
            validate_access_summary(old)
            for mutate in (
                lambda s: s.update(schema_version=3),
                lambda s: s.update(analyzer_version='instruction-access-3'),
                lambda s: s.update(exporter_version='access-summary-3'),
                lambda s: s['coverage'].update(extended_bound_operands=0),
                lambda s: s['coverage'].update(counter_invalid_forms=0),
                lambda s: s['coverage'].update(extended_instructions={}),
                lambda s: s['coverage'].update(counter_pseudo_operands_by_kind={}),
            ):
                candidate = deepcopy(old)
                mutate(candidate)
                with self.subTest(version=old['schema_version'], mutation=mutate), self.assertRaises(AccessSummaryError):
                    validate_access_summary(candidate)
        legacy2 = report('MSG(A);', version=2)
        self.assertEqual({key: legacy2[key] for key in VERSION2_CONSTANTS}, VERSION2_CONSTANTS)
        self.assertEqual(legacy2['coverage']['operands_by_role']['unknown'], 1)
        # A four-slot classified system vector is still impossible in v2.
        current = report('GSV(TASK,,Status,A);')
        old = {**current, **VERSION2_CONSTANTS}
        for key in ('extended_instructions', 'counter_pseudo_operands_by_kind', 'counter_invalid_forms', 'extended_bound_operands'):
            old['coverage'].pop(key)
        with self.assertRaises(AccessSummaryError):
            validate_access_summary(old)

    def test_family_role_and_pseudo_partitions_reject_impossible_combinations(self) -> None:
        mutations = [
            lambda c: c['extended_instructions'].update(counter=True),
            lambda c: c['extended_instructions'].update(extra=0),
            lambda c: c['extended_instructions'].update(counter=2),
            lambda c: c['extended_instructions'].update(message=1),
            lambda c: c['extended_instructions'].update(counter=0, system_get=1),
            lambda c: c['counter_pseudo_operands_by_kind'].update(placeholder=0),
            lambda c: c['counter_pseudo_operands_by_kind'].update(integer_literal=True),
            lambda c: c.update(counter_invalid_forms=1),
            lambda c: c.update(extended_bound_operands=0),
            lambda c: c.update(extended_bound_operands=2),
            lambda c: c.update(extended_bound_operands=True),
            lambda c: c.update(extended_instructions=c),
        ]
        for mutate in mutations:
            candidate = report('CTU(A,?,0);')
            mutate(candidate['coverage'])
            with self.subTest(mutation=mutate), self.assertRaises(AccessSummaryError):
                validate_access_summary(candidate)
        # Inventing a family whose slots fit can still exhaust the instruction
        # count incorrectly. Removing its vector leaves two operandless rows.
        candidate = report('ONS(A)JMP(Label)LBL(Label);')
        candidate['coverage']['extended_instructions']['counter'] = 1
        candidate['coverage']['counter_pseudo_operands_by_kind']['placeholder'] = 2
        candidate['coverage']['extended_bound_operands'] = 1
        with self.assertRaises(AccessSummaryError):
            validate_access_summary(candidate)

    def test_fresh_bound_counts_must_fit_bound_roles_and_older_slot_capacity(self) -> None:
        # Global totals alone would permit one bound extended operand, but
        # the only bound operand is a write and MSG needs read-write.
        candidate = report('MSG(Missing)OTE(A);')
        candidate['coverage']['extended_bound_operands'] = 1
        with self.assertRaises(AccessSummaryError):
            validate_access_summary(candidate)
        # All data slots in this report belong to the extension.
        for text in ('MSG(A);', 'GSV(TASK,,Status,A);', 'SSV(TASK,,Status,A);', 'SFR(R,A);'):
            candidate = report(text)
            candidate['coverage']['extended_bound_operands'] = 0
            with self.subTest(text=text), self.assertRaises(AccessSummaryError):
                validate_access_summary(candidate)
        candidate = report('SFR(R,0);')
        candidate['coverage']['extended_bound_operands'] = 1
        with self.assertRaises(AccessSummaryError):
            validate_access_summary(candidate)

    def test_invalid_forms_have_exact_three_slot_capacity_and_empty_maximum_four(self) -> None:
        candidate = report('CTU(A,A,?)TON(A,A,?);')
        self.assertEqual(candidate['coverage']['counter_invalid_forms'], 1)
        self.assertEqual(candidate['coverage']['instructions_by_status']['unsupported_operand_form'], 2)
        validate_access_summary(candidate)
        candidate['coverage']['counter_invalid_forms'] = 3
        with self.assertRaises(AccessSummaryError):
            validate_access_summary(candidate)
        for total in (2, 4):
            candidate = report('CTD(A,A,?);')
            candidate['coverage']['operands_total'] = total
            candidate['coverage']['operands_by_role']['unknown'] = total
            candidate['coverage']['unlinked_operands'] = total
            with self.subTest(total=total), self.assertRaises(AccessSummaryError):
                validate_access_summary(candidate)
        candidate = report('GSV(TASK,,Status,);')
        validate_access_summary(candidate)
        candidate['coverage']['operands_total'] = 5
        candidate['coverage']['operands_by_role']['unknown'] = 5
        candidate['coverage']['unlinked_operands'] = 5
        with self.assertRaises(AccessSummaryError):
            validate_access_summary(candidate)

    def test_mixed_old_and_new_shapes_pass_without_relaxing_old_catalogue_capacity(self) -> None:
        # Enumerated real signatures exercise every new family mixed with
        # zero-to-three-slot older catalogue patterns and all binding classes.
        patterns = ('CTU(A,?,0)', 'CTD(A,1,?)', 'MSG(A)', 'GSV(TASK,,Status,A)',
                    'SSV(TASK,,Status,1)', 'SSV(TASK,,Status,A)', 'SFR(R,A)', 'SFR(R,0)',
                    'TON(A,?,?)', 'MVM(A,1,A)', 'OSF(A,A)', 'SWPB(A,REVERSE,A)',
                    'LIM(0,A,1)', 'JMP(Label)', 'MSG(Missing)', 'CTU(A,A,?)', 'GSV(TASK,,Status,)')
        for first, second in product(patterns, repeat=2):
            with self.subTest(first=first, second=second):
                validate_access_summary(report(first + second + ';'))
        candidate = report('MSG(A)SWPB(A,REVERSE,A);')
        candidate['coverage']['operands_by_role'].update(read=0, read_write=2)
        candidate['coverage']['bound_by_role'].update(read=0, read_write=2)
        with self.assertRaises(AccessSummaryError):
            validate_access_summary(candidate)


if __name__ == '__main__':
    unittest.main()
