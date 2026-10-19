"""Assembly aggregate contracts keep source fields out and reject false totals."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest

from plc_workbench.engineering_assemblies import GROUP_BYTES, build_engineering_assemblies
from plc_workbench.engineering_assemblies_summary import (EngineeringAssembliesSummaryError,
    MAX_REPORT_BYTES, build_engineering_assemblies_summary,
    render_engineering_assemblies_summary, validate_engineering_assemblies_summary)
from test_engineering_assemblies import empty, provider_data, supplemental_data


class EngineeringAssembliesSummaryTests(unittest.TestCase):
    def summary(self) -> dict:
        return build_engineering_assemblies_summary(build_engineering_assemblies(provider_data()),
            {'commit': 'a' * 40, 'worktree': 'clean'})

    def summary2(self) -> dict:
        return build_engineering_assemblies_summary(
            build_engineering_assemblies(supplemental_data(), schema_version=2))

    def test_schema2_closed_exclusion_cross_tab_and_supplemental_count_are_source_free(self) -> None:
        summary = self.summary2()
        rendered = render_engineering_assemblies_summary(summary)
        self.assertEqual(summary['schema_version'], 2)
        self.assertEqual(summary['analyzer_version'], 'engineering-assemblies-2')
        self.assertEqual(summary['exporter_version'], 'engineering-assemblies-summary-2')
        self.assertEqual(summary['coverage']['supplemental_addresses_total'], 5)
        self.assertEqual(summary['coverage']['excluded_by_provider_reason']['sfc_context']['binding_or_namespace'], 1)
        self.assertEqual(summary['coverage']['excluded_by_provider_reason']['file_operations']['dynamic_address'], 1)
        for forbidden in ('PRIVATE', 'synthetic-snapshot', 'sfc_reference_', '.FileOnly', 'relationship_address_'):
            self.assertNotIn(forbidden, rendered)
        self.assertEqual(json.loads(rendered), summary)

    def test_schema2_cross_tab_cannot_disagree_with_either_exclusion_marginal(self) -> None:
        mutations = (
            lambda c: c['excluded_by_provider_reason']['sfc_context'].update(binding_or_namespace=0),
            lambda c: c['excluded_by_provider_reason']['sfc_context'].update(PRIVATE_EXTRA=1),
            lambda c: c['excluded_by_provider_reason'].update(PRIVATE_EXTRA={}),
            lambda c: c['excluded_by_provider_reason']['sfc_context'].update(binding_or_namespace=True),
            lambda c: c.update(supplemental_addresses_total=True),
            lambda c: c.update(supplemental_addresses_total=c['groups_total'] + 1),
        )
        for index, mutate in enumerate(mutations):
            summary = self.summary2()
            mutate(summary['coverage'])
            with self.subTest(index=index), self.assertRaises(EngineeringAssembliesSummaryError):
                validate_engineering_assemblies_summary(summary)
        summary = self.summary2()
        cross_tab = summary['coverage']['excluded_by_provider_reason']
        cross_tab['sfc_context']['binding_or_namespace'] = 0
        cross_tab['sfc_context']['dynamic_address'] = 1
        with self.assertRaises(EngineeringAssembliesSummaryError):
            validate_engineering_assemblies_summary(summary)

    def test_versioned_coverage_contracts_reject_mixed_schemas(self) -> None:
        for original, coverage in ((self.summary(), self.summary2()['coverage']),
                (self.summary2(), self.summary()['coverage'])):
            original['coverage'] = coverage
            with self.assertRaises(EngineeringAssembliesSummaryError):
                validate_engineering_assemblies_summary(original)
        empty2 = build_engineering_assemblies_summary(build_engineering_assemblies(empty(), schema_version=2))
        self.assertEqual(empty2['status'], 'complete')
        self.assertEqual(empty2['coverage']['supplemental_addresses_total'], 0)

    def test_schema2_maximum_width_count_envelope_stays_within_existing_budget(self) -> None:
        def grow(value):
            if type(value) is int:
                return 10**12
            if type(value) is dict:
                return {key: grow(item) for key, item in value.items()}
            return value
        result = json.dumps(grow(self.summary2()), sort_keys=True, indent=2) + '\n'
        self.assertLess(len(result.encode('utf-8')), MAX_REPORT_BYTES)

    def test_summary_contains_only_closed_counts_and_revision_and_fits_budget(self) -> None:
        summary = self.summary()
        rendered = render_engineering_assemblies_summary(summary)
        self.assertEqual(json.loads(rendered), summary)
        self.assertLess(len(rendered.encode()), MAX_REPORT_BYTES)
        for forbidden in ('Pump', 'Permit', 'operand_', 'relationship_address_', 'assembly_membership_'):
            self.assertNotIn(forbidden, rendered)

    def test_unknown_keys_and_boolean_counts_are_rejected_at_each_level(self) -> None:
        for path in ((), ('coverage',), ('coverage', 'memberships_by_provider'), ('tool_revision',)):
            value = self.summary()
            target = value
            for key in path:
                target = target[key]
            target['PRIVATE_EXTRA'] = 1
            with self.subTest(path=path), self.assertRaises(EngineeringAssembliesSummaryError):
                validate_engineering_assemblies_summary(value)
        for field in ('groups_total', 'memberships_total', 'retained_bytes'):
            value = self.summary()
            value['coverage'][field] = True
            with self.subTest(field=field), self.assertRaises(EngineeringAssembliesSummaryError):
                validate_engineering_assemblies_summary(value)

    def test_membership_provider_relation_and_exclusion_partitions_are_exact(self) -> None:
        for bucket, key in (('memberships_by_provider', 'signal_context'),
                ('memberships_by_relation', 'guard_condition'),
                ('excluded_by_provider', 'signal_context'), ('excluded_by_reason', 'missing_address'),
                ('providers_by_status', 'complete')):
            value = self.summary()
            value['coverage'][bucket][key] += 1
            with self.subTest(bucket=bucket), self.assertRaises(EngineeringAssembliesSummaryError):
                validate_engineering_assemblies_summary(value)

    def test_provider_relation_forgery_fails_even_when_global_totals_match(self) -> None:
        value = self.summary()
        value['coverage']['memberships_by_relation']['pid_slot'] -= 1
        value['coverage']['memberships_by_relation']['calculation_input'] += 1
        with self.assertRaises(EngineeringAssembliesSummaryError):
            validate_engineering_assemblies_summary(value)

    def test_impossible_groups_flags_and_resource_counts_are_rejected(self) -> None:
        for key, changed in (('groups_total', 0), ('multirung_groups', 100_000),
                ('multiprovider_groups', 100_000), ('groups_with_boundary_flags', 100_000),
                ('source_gap_buckets', 1000), ('source_gap_counts', 0),
                ('visited_rows', 500_001), ('retained_bytes', 32_767)):
            value = self.summary()
            value['coverage'][key] = changed
            with self.subTest(key=key), self.assertRaises(EngineeringAssembliesSummaryError):
                validate_engineering_assemblies_summary(value)
        for field in ('groups_by_flag', 'memberships_by_flag'):
            value = self.summary()
            value['coverage'][field]['unknown_role'] = 10**12
            with self.subTest(field=field), self.assertRaises(EngineeringAssembliesSummaryError):
                validate_engineering_assemblies_summary(value)
        value = self.summary()
        value['coverage']['visited_rows'] = value['coverage']['visited_links'] = 0
        with self.assertRaises(EngineeringAssembliesSummaryError):
            validate_engineering_assemblies_summary(value)
        value = self.summary()
        value['coverage']['retained_bytes'] = 32_768 + value['coverage']['groups_total'] * GROUP_BYTES
        with self.assertRaises(EngineeringAssembliesSummaryError):
            validate_engineering_assemblies_summary(value)

    def test_false_complete_and_truncation_statuses_are_rejected(self) -> None:
        for field, changed in (('status', 'complete'), ('scan_status', 'truncated')):
            value = self.summary()
            value[field] = changed
            with self.subTest(field=field), self.assertRaises(EngineeringAssembliesSummaryError):
                validate_engineering_assemblies_summary(value)
        data = deepcopy(provider_data())
        data['signal_context']['outputs'][0]['guard_dependencies']['traversal_status'] = 'truncated'
        validate_engineering_assemblies_summary(build_engineering_assemblies_summary(build_engineering_assemblies(data)))

    def test_provider_required_flag_populations_cannot_be_erased(self) -> None:
        for flag in ('selector_or_array_span', 'stateful_guard'):
            value = self.summary()
            value['coverage']['memberships_by_flag'][flag] = 0
            value['coverage']['groups_by_flag'][flag] = 0
            with self.subTest(flag=flag), self.assertRaises(EngineeringAssembliesSummaryError):
                validate_engineering_assemblies_summary(value)
        value = self.summary()
        value['coverage']['memberships_by_relation']['read'] -= 1
        value['coverage']['memberships_by_relation']['unknown'] += 1
        value['coverage']['memberships_by_flag']['unknown_role'] = 0
        value['coverage']['groups_by_flag']['unknown_role'] = 0
        with self.assertRaises(EngineeringAssembliesSummaryError):
            validate_engineering_assemblies_summary(value)

    def test_revision_versions_and_boolean_constants_are_strict(self) -> None:
        for field, changed in (('schema_version', True), ('analyzer_version', 'PRIVATE'),
                ('status', True), ('scan_status', 1)):
            value = self.summary()
            value[field] = changed
            with self.subTest(field=field), self.assertRaises(EngineeringAssembliesSummaryError):
                validate_engineering_assemblies_summary(value)
        for revision in ({'commit': None, 'worktree': 'clean'},
                {'commit': 'A' * 40, 'worktree': 'clean'},
                {'commit': 'a' * 40, 'worktree': 'unavailable'},
                {'commit': 'a' * 40, 'worktree': True}):
            value = self.summary()
            value['tool_revision'] = revision
            with self.subTest(revision=revision), self.assertRaises(EngineeringAssembliesSummaryError):
                validate_engineering_assemblies_summary(value)

    def test_empty_complete_summary_and_unsupported_result_are_distinct(self) -> None:
        result = build_engineering_assemblies(empty())
        summary = build_engineering_assemblies_summary(result)
        self.assertEqual(summary['status'], 'complete')
        self.assertEqual(summary['tool_revision'], {'commit': None, 'worktree': 'unavailable'})
        result['schema_version'] = 2
        with self.assertRaises(EngineeringAssembliesSummaryError):
            build_engineering_assemblies_summary(result)


if __name__ == '__main__':
    unittest.main()
