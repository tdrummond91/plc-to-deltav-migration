"""Invented rack references join canonical backing addresses without remapping history."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access
from plc_workbench.calculations import analyze_calculations
from plc_workbench.references import analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.source_reuse import source_reuse_scope
from plc_workbench.tag_data import analyze_tag_data
from plc_workbench.workspace_field_io import FieldIOError, FieldIOIndex
from plc_workbench.workspace_rack_references import RackReferenceIndex
from plc_workbench.workspace_signal_usage import SignalUsageIndex
from plc_workbench.workspace_usage_ranges import UsageRangeResolver
from plc_workbench.workspace_variables import VariableIndex
from test_rack_backing_context import capture, fixture


def evidence(text: str) -> list:
    snapshot = snapshot_from_bytes(text.encode())
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    calculations = analyze_calculations(snapshot, inventory, references)
    access = analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
    data = analyze_tag_data(snapshot, inventory)
    return [snapshot.data, *[json.loads(json.dumps(asdict(value)))
                            for value in (inventory, references, access, data, calculations)]]


def index(text: str | None = None) -> FieldIOIndex:
    return FieldIOIndex(VariableIndex(*evidence(text if text is not None else fixture(sfc=''))))


class WorkspaceRackReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        scope = source_reuse_scope()
        scope.__enter__()
        self.addCleanup(scope.__exit__, None, None, None)

    def test_recovery_matches_existing_proven_rack_overlay_with_source_roles(self) -> None:
        parts = capture(fixture(sfc=''))
        values = [parts[0].data, *[json.loads(json.dumps(asdict(parts[position])))
                                  for position in (1, 2, 3, 9, 4)]]
        before = deepcopy(values)
        field = FieldIOIndex(VariableIndex(*values))
        recovered = [use for address in field.addresses.values() for use in address['uses']
                     if use.get('binding_basis') == 'qualified_rack_slot_source_correspondence']
        expected = [use for use in parts[-1].uses if use['kind'] == 'rll' and use['disposition'] == 'associated']
        self.assertEqual({use['id'] for use in recovered}, {use['source_id'] for use in expected})
        self.assertEqual(sorted(use['role'] for use in recovered), ['read', 'read', 'write'])
        refs = {row['id']: row for row in parts[2].operands}
        for use in recovered:
            self.assertEqual(use['rung_id'], refs[use['id']]['rung_id'])
            self.assertEqual(use['instruction_id'], refs[use['id']]['instruction_id'])
            self.assertTrue(use['path'].endswith('Rung ' + use['rung_number']))
        self.assertEqual(field.coverage['rack_recovered_reference_uses'], 3)
        self.assertEqual(field.coverage['rack_aliases_unresolved'], 0)
        self.assertEqual(values, before)
        scan = SignalUsageIndex(field).scan_summary()
        self.assertNotIn('unresolved_references', scan['role_gap_reasons'])

    def test_exact_alias_descriptions_follow_backing_member_and_not_every_slot(self) -> None:
        text = fixture(sfc='').replace('AliasFor="Remote:3:I.Data.0"/>',
            'AliasFor="Remote:3:I.Data.0"><Description>Invented inlet position</Description></Tag>')
        field = index(text)
        chosen = next(row for row in field.addresses.values() if row.get('rack_mapping')
                      and row['direction'] == 'input')
        self.assertEqual(chosen['address'], 'Remote:I.Slot[3].Data.0')
        self.assertEqual(chosen['datatype'], 'BOOL')
        self.assertEqual(chosen['description'], 'Invented inlet position')
        self.assertEqual(chosen['aliases'][0]['name'], 'ProbeAlias')
        self.assertEqual(chosen['rack_mapping']['logical_address'], 'Remote:3:I.Data.0')
        self.assertEqual(field.modules[chosen['rack_mapping']['module_id']]['name'], 'RackCard')
        self.assertTrue(all(row['description'] != 'Invented inlet position' for row in field.addresses.values()
                            if row['id'] != chosen['id']))

    def test_legacy_backing_address_identity_and_spelling_are_preserved(self) -> None:
        text = fixture(rungs=('XIC(Remote:I.slot[3].data.0);', 'XIC(ProbeAlias);'), sfc='')
        values = evidence(text)
        with patch.object(RackReferenceIndex, 'resolve', return_value=None):
            legacy = FieldIOIndex(VariableIndex(*values))
        current = FieldIOIndex(VariableIndex(*values))
        before = next(row for row in legacy.addresses.values() if row['suffix'] == '.slot[3].data.0')
        after = current.addresses[before['id']]
        for key in ('id', 'root_id', 'suffix', 'address', 'group_member_ids'):
            self.assertEqual(after[key], before[key])
        self.assertEqual(len(before['uses']), 1)
        self.assertEqual(len(after['uses']), 2)

    def test_alias_type_checks_apply_before_caller_suffix_and_respect_local_shadowing(self) -> None:
        tags = ('<Tag Name="Word" TagType="Alias" DataType="DINT" AliasFor="Remote:3:I.Data"/>'
                '<Tag Name="Wrong" TagType="Alias" DataType="REAL" AliasFor="Remote:3:I.Data.1"/>'
                '<Tag Name="ArrayAlias" TagType="Alias" Dimensions="2" AliasFor="Remote:3:I.Data.2"/>')
        text = fixture(rungs=('XIC(Word.3);', 'XIC(Wrong);', 'XIC(ArrayAlias);', 'XIC(ProbeAlias);'),
                       tags=tags, sfc='')
        text = text.replace('<Program Name="SyntheticProbe">',
                            '<Program Name="SyntheticProbe"><Tags><Tag Name="ProbeAlias" DataType="BOOL"/></Tags>')
        field = index(text)
        recovered = [use for row in field.addresses.values() for use in row['uses'] if 'binding_basis' in use]
        self.assertEqual([use['variable'] for use in recovered], ['Word.3'])
        self.assertEqual(recovered[0]['backing_address'], 'Remote:I.Slot[3].Data.3')

    def test_invalid_topology_headers_protection_and_representation_never_recover(self) -> None:
        original = fixture(sfc='')
        cases = {
            'unsupported_adapter': original.replace('CatalogNumber="1756-EN2T"', 'CatalogNumber="1756-EN2TR"'),
            'wrong_vendor': original.replace('Vendor="1"', 'Vendor="2"'),
            'foreign_modules': original.replace('<Modules>', '<Modules xmlns="urn:foreign">'),
            'protected_backing': original.replace('<InputTag>', '<InputTag Protected="true">'),
            'wrong_header': original.replace('AB:1756_CNB_SLOT:I:0', 'AB:1756_CNB_SLOT:O:0'),
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                field = index(text)
                self.assertFalse(any(row.get('rack_mapping') for row in field.addresses.values()
                                     if row['direction'] == 'input'))
        # Two same-named rack modules are ambiguous, even with identical data.
        start, end = original.index('<Module Name="RackCard"'), original.index('</Module>', original.index('<Module Name="RackCard"')) + len('</Module>')
        duplicate = original[:end] + original[start:end] + original[end:]
        self.assertFalse(any(row.get('rack_mapping') for row in index(duplicate).addresses.values()))

    def test_word_use_resolves_bits_and_bad_members_do_not_get_promoted(self) -> None:
        text = fixture(rungs=('MOV(Remote:3:I.Data,Stored);', 'XIC(Remote:3:I.Data.32);',
                              'XIC(Remote:3:I.Data[0]);', 'XIC(Remote:3:O.Fault);'),
                       tags='<Tag Name="Stored" DataType="DINT"/>', sfc='')
        field = index(text)
        point = next(row for row in field.addresses.values() if row.get('rack_mapping')
                     and row['rack_mapping']['logical_suffix'] == '.Data.0')
        usage = SignalUsageIndex(field).summary(point)
        self.assertEqual(usage['status'], 'referenced')
        self.assertEqual(usage['resolved_uses'][0]['reason'], 'whole_word')
        self.assertEqual(field.coverage['rack_recovered_reference_uses'], 1)

    def test_cpt_rack_leaves_preserve_occurrence_ids_and_resolve_word_members(self) -> None:
        for operand, expected_kind in (('Remote:3:I.Data', 'whole_word'), ('ProbeAlias', None)):
            with self.subTest(operand=operand):
                text = fixture(rungs=(f'CPT(Result,{operand}+1);',),
                               tags='<Tag Name="Result" DataType="DINT"/>', sfc='')
                field = index(text)
                point = next(row for row in field.addresses.values() if row.get('rack_mapping')
                             and row['rack_mapping']['logical_suffix'] == '.Data.0')
                helper = SignalUsageIndex(field)
                usage = helper.summary(point)
                self.assertEqual(usage['status'], 'referenced')
                self.assertEqual(field.coverage['rack_recovered_reference_uses'], 1)
                leaf = field.base._access.expression_uses[0]
                uses = usage['resolved_uses'] if expected_kind else point['uses']
                self.assertEqual(len(uses), 1)
                self.assertEqual(uses[0]['id'], leaf['id'])
                self.assertEqual(uses[0]['instruction_id'], leaf['instruction_id'])
                self.assertEqual(uses[0]['rung_id'], leaf['rung_id'])
                self.assertEqual(uses[0]['variable'], operand)
                self.assertEqual(uses[0]['role'], 'read')
                if expected_kind:
                    self.assertEqual(uses[0]['reason'], expected_kind)
                self.assertNotIn('unresolved_references', helper.scan_summary()['role_gap_reasons'])

    def test_no_tag_data_cannot_recover_and_retained_data_has_finite_budget(self) -> None:
        values = evidence(fixture(sfc=''))
        values[4] = None
        field = FieldIOIndex(VariableIndex(*values))
        self.assertEqual(field.coverage['rack_recovered_reference_uses'], 0)
        with patch('plc_workbench.workspace_rack_references.MAX_INDEX_BYTES', 1):
            with self.assertRaises(FieldIOError) as caught:
                index()
        self.assertEqual(caught.exception.diagnostic['reason'], 'index_bytes_limit')
        self.assertEqual(caught.exception.diagnostic['limit'], 1)

    def test_copy_fill_ranges_match_backing_spelling_for_both_operands(self) -> None:
        tags = ('<Tag Name="Buffer" DataType="DINT" Dimensions="10"/>'
                '<Tag Name="OutputProbe" TagType="Alias" DataType="BOOL" AliasFor="Remote:3:O.Data.0"/>')
        cases = (
            ('COP(Remote:3:I.Data,Buffer[0],1);', {'input': 'read'}),
            ('CPS(Buffer[0],Remote:3:O.Data,1);', {'output': 'write'}),
            ('COP(Remote:3:I.Data,Remote:3:O.Data,1);', {'input': 'read', 'output': 'write'}),
            ('CPS(Remote:3:I.Data,Remote:3:O.Data,1);', {'input': 'read', 'output': 'write'}),
            ('FLL(0,Remote:3:O.Data,1);', {'output': 'write'}),
            ('FLL(Remote:3:I.Data,Remote:3:O.Data,1);', {'input': 'read', 'output': 'write'}),
            ('FLL(Remote:3:I.Data,Buffer[0],4);', {'input': 'read'}),
        )
        for rung, roles in cases:
            with self.subTest(rung=rung):
                outcomes = []
                for spelling in (rung, rung.replace('Remote:3:I', 'Remote:I.Slot[3]')
                                      .replace('Remote:3:O', 'Remote:O.Slot[3]')):
                    field = index(fixture(rungs=(spelling,), tags=tags, sfc=''))
                    helper = SignalUsageIndex(field)
                    results = {}
                    for direction, role in roles.items():
                        point = next(row for row in field.addresses.values() if row.get('rack_mapping')
                                     and row['rack_mapping']['logical_suffix'] == '.Data.0'
                                     and row['direction'] == direction)
                        usage = helper.summary(point)
                        self.assertEqual(usage['status'], 'referenced')
                        self.assertEqual(usage['resolved_count'], 1)
                        self.assertEqual(usage['possible_count'], 0)
                        use = usage['resolved_uses'][0]
                        self.assertEqual(use['reason'], 'fixed_range')
                        self.assertEqual(use['role'], role)
                        results[direction] = (usage['status'], usage['roles'], use['reason'], use['explanation'])
                    outcomes.append(results)
                self.assertEqual(outcomes[0], outcomes[1])

    def test_rack_copy_fill_ranges_do_not_bypass_bounds_alias_or_source_checks(self) -> None:
        tags = ('<Tag Name="Buffer" DataType="DINT" Dimensions="10"/>'
                '<Tag Name="Length" DataType="DINT"/>'
                '<Tag Name="Wrong" TagType="Alias" DataType="REAL" AliasFor="Remote:3:I.Data"/>'
                '<Tag Name="OutputProbe" TagType="Alias" DataType="BOOL" AliasFor="Remote:3:O.Data.0"/>')
        for rung in ('COP(Remote:3:I.Data,Buffer[0],2);',
                     'CPS(Buffer[0],Remote:3:O.Data,2);',
                     'FLL(Remote:3:I.Data,Remote:3:O.Data,2);',
                     'FLL(Remote:3:I.Data,Buffer[9],2);',
                     'COP(Remote:3:I.Data,Buffer[10],1);',
                     'COP(Remote:3:I.Data,Buffer[0],Length);',
                     'COP(Remote:3:I.Data,Buffer[0],-1);',
                     'FLL(Wrong,Remote:3:O.Data,1);'):
            with self.subTest(rung=rung):
                field = index(fixture(rungs=(rung,), tags=tags, sfc=''))
                helper = SignalUsageIndex(field)
                points = [row for row in field.addresses.values() if row.get('rack_mapping')
                          and row['rack_mapping']['logical_suffix'] == '.Data.0']
                self.assertTrue(points)
                self.assertTrue(all(helper.summary(point)['resolved_count'] == 0 for point in points))
        field = index(fixture(rungs=('FLL(Remote:3:I.Data,Remote:3:O.Data,0);',), tags=tags, sfc=''))
        helper = SignalUsageIndex(field)
        self.assertTrue(all(helper.summary(row)['status'] == 'not_found' for row in field.addresses.values()
                            if row.get('rack_mapping') and row['rack_mapping']['logical_suffix'] == '.Data.0'))
        with self.assertRaises(ValueError):
            UsageRangeResolver(field.base, index().rack_references)


if __name__ == '__main__':
    unittest.main()
