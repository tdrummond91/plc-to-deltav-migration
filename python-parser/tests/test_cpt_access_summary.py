"""Closed count-only CPT access publication and historical version boundaries."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest

from plc_workbench.access import analyze_access
from plc_workbench.access_summary import (
    VERSION4_CONSTANTS, AccessSummaryError, build_access_summary,
    render_access_summary, validate_access_summary,
)
from test_access_summary import legacy_report
from test_calculations import capture, tag
from test_cpt_access import evidence


def report(expression: str = 'A + A * B', **kwargs):
    snapshot, inventory, references, calculations, result = evidence(expression, **kwargs)
    return build_access_summary(inventory, references, result, snapshot=snapshot, calculations=calculations)


class CptAccessSummaryTests(unittest.TestCase):
    def test_count_only_contract_has_distinct_source_slots_and_expression_reads(self) -> None:
        summary = report('SECRET + SECRET.Member', destination='DESTINATION', tags=tag('SECRET') + tag('DESTINATION'))
        self.assertEqual(set(summary), set(VERSION4_CONSTANTS) | {'status', 'coverage', 'tool_revision'})
        self.assertEqual(summary['status'], 'complete')
        coverage = summary['coverage']
        self.assertEqual(coverage['operands_total'], 2)
        self.assertEqual(coverage['operands_by_role']['expression_read'], 1)
        self.assertEqual(coverage['operands_by_role']['read'], 0)
        self.assertEqual(coverage['expression_uses_total'], 2)
        self.assertEqual(coverage['expression_uses_by_binding']['root_bound'], 2)
        self.assertEqual(coverage['expression_indexed_roots'], 1)
        self.assertEqual(coverage['linked_operands'], 1)
        rendered = render_access_summary(summary)
        for withheld in ('SECRET', 'DESTINATION', 'Member', 'CPT', 'alias_chain', 'binding_reason'):
            self.assertNotIn(withheld, rendered)
        self.assertNotRegex(rendered, r'(?:operand|entity|rung)_[0-9a-f]{64}')
        self.assertEqual(json.loads(rendered), summary)

    def test_companion_authentication_is_required_before_summary_projection(self) -> None:
        snapshot, inventory, references, calculations, access = evidence()
        with self.assertRaises(AccessSummaryError):
            build_access_summary(inventory, references, access)
        forged = deepcopy(calculations)
        forged.nodes[0]['binding']['target_id'] = 'forged'
        with self.assertRaises(AccessSummaryError):
            build_access_summary(inventory, references, access, snapshot=snapshot, calculations=forged)

    def test_role_and_container_equations_reject_inconsistent_aggregates(self) -> None:
        mutations = (
            lambda c: c.update(calculation_instructions=True),
            lambda c: c.update(calculation_instructions=0),
            lambda c: c['operands_by_role'].update(expression_read=0, read=1),
            lambda c: c['bound_by_role'].update(expression_read=1),
            lambda c: c['expression_containers_by_status'].update(parsed=0),
            lambda c: c['expression_containers_by_status'].update(unsupported=1),
            lambda c: c['expression_containers_by_status'].update(other=0),
            lambda c: c['expression_uses_by_binding'].update(extra=0),
            lambda c: c['expression_uses_by_binding'].update(root_bound=True),
            lambda c: c.update(expression_uses_total=2),
            lambda c: c.update(expression_indexed_roots=0),
            lambda c: c.update(expression_indexed_roots=4),
            lambda c: c.update(expressions_with_binding_gaps=1),
            lambda c: c.update(expression_uses_by_binding=c),
        )
        for mutate in mutations:
            candidate = report()
            mutate(candidate['coverage'])
            with self.subTest(mutation=mutate), self.assertRaises(AccessSummaryError):
                validate_access_summary(candidate)

    def test_leaf_limits_and_gap_counts_cannot_exceed_parsed_expression_capacity(self) -> None:
        base = report('Missing + A')
        mutations = (
            lambda c: c.update(expressions_with_binding_gaps=0),
            lambda c: c.update(expressions_with_binding_gaps=2),
            lambda c: c['expression_containers_by_status'].update(parsed=0, unsupported=1),
            lambda c: c.update(expression_uses_total=257,
                               expression_uses_by_binding=dict(c['expression_uses_by_binding'], root_bound=256)),
        )
        for mutate in mutations:
            candidate = deepcopy(base)
            mutate(candidate['coverage'])
            with self.subTest(mutation=mutate), self.assertRaises(AccessSummaryError):
                validate_access_summary(candidate)

    def test_status_distinguishes_unsupported_syntax_leaf_gaps_and_destination_gaps(self) -> None:
        cases = ({'expression': '1 + 2'}, {'expression': 'A'}, {'expression': 'A +'},
                 {'expression': 'Missing'}, {'expression': 'A', 'destination': 'Missing'},
                 {'text': 'CPT(D);'}, {'text': 'CPT(D,);'})
        for index, kwargs in enumerate(cases):
            with self.subTest(kwargs=kwargs):
                candidate = report(**kwargs)
                self.assertEqual(candidate['status'], 'complete' if index < 2 else 'partial')
                candidate['status'] = 'partial' if index < 2 else 'complete'
                with self.assertRaises(AccessSummaryError):
                    validate_access_summary(candidate)

    def test_gapped_expression_count_can_contain_the_claimed_unbound_leaves(self) -> None:
        candidate = report(text='CPT(D,Missing)CPT(D,Missing);')
        candidate['coverage']['expression_uses_total'] = 257
        candidate['coverage']['expression_uses_by_binding']['unresolved'] = 257
        candidate['coverage']['expressions_with_binding_gaps'] = 1
        with self.assertRaises(AccessSummaryError):
            validate_access_summary(candidate)

    def test_catalogue_capacity_subtracts_cpt_before_existing_families(self) -> None:
        for text in ('CPT(D,A);', 'CPT(D,A)CPT(D,1);',
                     'CPT(D,A)ONS(A)MOV(A,D)TON(A,?,0)CTU(A,?,0)MSG(A)GSV(TASK,,Status,A)'
                     'SSV(TASK,,Status,A)SFR(R,A)SFR(R,0)MVM(A,1,D)SWPB(A,REVERSE,D);',
                     'CPT(D,A)CPT(D,A,B)CPT(,A)CTU(A,B,0)OTHER();'):
            with self.subTest(text=text):
                validate_access_summary(report(text=text))
        candidate = report(text='CPT(D,A)XIC(A);')
        # Inventing a second CPT steals an instruction and requires another
        # destination write that the remaining ordinary catalogue cannot supply.
        c = candidate['coverage']
        c['calculation_instructions'] = 2
        c['expression_containers_by_status']['parsed'] = 2
        c['operands_by_role'].update(expression_read=2, read=0)
        c['bound_by_role']['read'] = 0
        c.update(linked_operands=1, unlinked_operands=2, indexed_roots=1)
        with self.assertRaises(AccessSummaryError):
            validate_access_summary(candidate)

    def test_legacy_contracts_reject_new_roles_fields_and_metadata(self) -> None:
        _, inventory, references, _ = capture('A + B')
        old_reports = [legacy_report()] + [build_access_summary(inventory, references,
            analyze_access(inventory, references, schema_version=version)) for version in (2, 3)]
        for old in old_reports:
            validate_access_summary(old)
            for mutate in (lambda s: s['coverage'].update(expression_uses_total=0),
                           lambda s: s['coverage']['operands_by_role'].update(expression_read=0),
                           lambda s: s.update(analyzer_version='instruction-access-4'),
                           lambda s: s.update(exporter_version='access-summary-4')):
                candidate = deepcopy(old)
                mutate(candidate)
                with self.subTest(version=old['schema_version'], mutation=mutate), self.assertRaises(AccessSummaryError):
                    validate_access_summary(candidate)


if __name__ == '__main__':
    unittest.main()
