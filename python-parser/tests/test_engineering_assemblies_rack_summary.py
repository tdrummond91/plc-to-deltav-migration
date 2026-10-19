"""Closed rack assembly coverage exports counts, never correspondence records."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest

from plc_workbench.engineering_assemblies import build_engineering_assemblies
from plc_workbench.engineering_assemblies_summary import (
    EngineeringAssembliesSummaryError, MAX_REPORT_BYTES,
    build_engineering_assemblies_summary, render_engineering_assemblies_summary,
    validate_engineering_assemblies_summary)
from test_engineering_assemblies_rack import rack_data


class EngineeringAssembliesRackSummaryTests(unittest.TestCase):
    def summary(self, version: int = 3) -> dict:
        return build_engineering_assemblies_summary(
            build_engineering_assemblies(rack_data(), schema_version=version))

    def test_schema3_closed_source_free_counts_match_accepted_memberships(self) -> None:
        data = rack_data()
        result = build_engineering_assemblies(data, schema_version=3)
        summary = build_engineering_assemblies_summary(result)
        text = render_engineering_assemblies_summary(summary)
        self.assertEqual(summary['schema_version'], 3)
        self.assertEqual(summary['exporter_version'], 'engineering-assemblies-summary-3')
        self.assertEqual(summary['coverage']['rack_memberships_total'],
            sum(bool(row['rack_source_use_ids']) for row in result['memberships']))
        self.assertEqual(sum(summary['coverage']['rack_memberships_by_relation'].values()),
            summary['coverage']['rack_memberships_total'])
        self.assertEqual(json.loads(text), summary)
        for private in ('ProbeAlias', 'Permit', 'Remote', 'Dest', '.Slot[', 'rack_backing_use_',
                'relationship_address_', 'source_id', 'snapshot', 'rack_source_use_ids'):
            self.assertNotIn(private, text)

    def test_new_counts_reject_open_vocabulary_bools_and_impossible_partitions(self) -> None:
        mutations = (
            lambda c: c.update(rack_memberships_total=True),
            lambda c: c.update(rack_memberships_total=c['rack_memberships_total'] + 1),
            lambda c: c['rack_memberships_by_relation'].update(PRIVATE=1),
            lambda c: c['rack_memberships_by_relation'].update(read=True),
            lambda c: c['rack_memberships_by_relation'].update(sfc_reference=-1),
            lambda c: c['known_non_address_guard_inputs_by_kind'].update(PRIVATE=1),
            lambda c: c['known_non_address_guard_inputs_by_kind'].update(literal=True),
            lambda c: c['known_non_address_guard_inputs_by_kind'].update(system_flag=10**12),
        )
        for index, mutate in enumerate(mutations):
            value = self.summary()
            mutate(value['coverage'])
            with self.subTest(index=index), self.assertRaises(EngineeringAssembliesSummaryError):
                validate_engineering_assemblies_summary(value)

    def test_recovered_relation_cannot_exceed_total_even_if_recovered_sum_matches(self) -> None:
        value = self.summary()
        c = value['coverage']
        delta = c['memberships_by_relation']['sfc_reference'] + 1 - c['rack_memberships_by_relation']['sfc_reference']
        c['rack_memberships_by_relation']['sfc_reference'] += delta
        c['rack_memberships_total'] += delta
        with self.assertRaises(EngineeringAssembliesSummaryError):
            validate_engineering_assemblies_summary(value)

    def test_unknown_role_is_never_qualified_by_rack_source_overlay(self) -> None:
        value = self.summary()
        c = value['coverage']
        for key in ('rack_memberships_by_relation', 'memberships_by_relation'):
            c[key]['read'] -= 1
            c[key]['unknown'] += 1
        c['memberships_by_flag']['unknown_role'] += 1
        with self.assertRaises(EngineeringAssembliesSummaryError):
            validate_engineering_assemblies_summary(value)

    def test_historical_versions_keep_their_closed_coverage_unchanged(self) -> None:
        for version in (1, 2):
            value = self.summary(version)
            text = render_engineering_assemblies_summary(value)
            self.assertNotIn('rack_memberships', text)
            self.assertNotIn('known_non_address', text)
            value['coverage'] = deepcopy(self.summary()['coverage'])
            with self.subTest(version=version), self.assertRaises(EngineeringAssembliesSummaryError):
                validate_engineering_assemblies_summary(value)
        value = self.summary()
        value['coverage'] = self.summary(2)['coverage']
        with self.assertRaises(EngineeringAssembliesSummaryError):
            validate_engineering_assemblies_summary(value)

    def test_widest_closed_schema3_summary_stays_inside_existing_eight_kib(self) -> None:
        def grow(value):
            if type(value) is int:
                return 10**12
            if type(value) is dict:
                return {key: grow(child) for key, child in value.items()}
            return value
        text = json.dumps(grow(self.summary()), sort_keys=True, indent=2) + '\n'
        self.assertLess(len(text.encode()), MAX_REPORT_BYTES)

    def test_summary_does_not_mutate_and_forged_version_fails_closed(self) -> None:
        result = build_engineering_assemblies(rack_data(), schema_version=3)
        before = deepcopy(result)
        build_engineering_assemblies_summary(result)
        self.assertEqual(result, before)
        for field, bad in (('schema_version', True), ('analyzer_version', 'PRIVATE')):
            value = deepcopy(result)
            value[field] = bad
            with self.subTest(field=field), self.assertRaises(EngineeringAssembliesSummaryError):
                build_engineering_assemblies_summary(value)


if __name__ == '__main__':
    unittest.main()
