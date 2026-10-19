"""Invented source-only rack correspondences; no hardware or live values."""
from copy import deepcopy
from dataclasses import replace
from html import escape
import json
import unittest
from unittest.mock import patch

from plc_workbench import rack_backing_context as module
from plc_workbench.access import analyze_access
from plc_workbench.binding_context import analyze_binding_context
from plc_workbench.calculations import analyze_calculations
from plc_workbench.conditions import analyze_conditions
from plc_workbench.rack_backing_context import (analyze_rack_backing_context,
    validate_rack_backing_context, render_rack_backing_context_json, RackBackingContextError)
from plc_workbench.rack_backing_summary import build_rack_backing_summary, render_rack_backing_summary
from plc_workbench.references import analyze_references
from plc_workbench.relationships import analyze_relationships
from plc_workbench.rung_analysis import analyze_rungs
from plc_workbench.sfc_conditions import analyze_sfc_conditions
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.source import snapshot_from_bytes, analyze_snapshot
from plc_workbench.source_reuse import source_reuse_scope
from plc_workbench.tag_data import analyze_tag_data
from test_rack_backing_summary import source, slot_data


def fixture(*, rungs: tuple[str, ...] | None = None, sfc: str = 'ProbeAlias OR Remote:3:I.Data.0',
            tags: str = '', output_l5k: bool = True) -> str:
    # The native header spelling is an independently authored structural
    # fixture, not a certificate of a real EN2T configuration or import.
    text = source(data=slot_data(), catalog='1756-EN2T')
    output = slot_data('O') + ('<Data Format="L5K">[987]</Data>' if output_l5k else '')
    text = text.replace('<OutputTag/>', f'<OutputTag>{output}</OutputTag>')
    text = text.replace('<Tag Name="ProbeAlias"', tags + '<Tag Name="ProbeAlias"')
    if rungs is not None:
        start = text.index('<RLLContent>')
        end = text.index('</RLLContent>', start) + len('</RLLContent>')
        body = ''.join(f'<Rung Number="{index}" Type="N"><Text>{escape(rung)}</Text></Rung>'
                       for index, rung in enumerate(rungs))
        text = text[:start] + '<RLLContent>' + body + '</RLLContent>' + text[end:]
    if sfc:
        chart = ('<Routine Name="Chart" Type="SFC"><SFCContent><Transition ID="10">'
                 '<Condition><STContent><Line Number="0">' + escape(sfc)
                 + '</Line></STContent></Condition></Transition></SFCContent></Routine>')
        text = text.replace('</Routines>', chart + '</Routines>')
    return text


def capture(text: str | None = None):
    snapshot = snapshot_from_bytes((fixture() if text is None else text).encode())
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    calculations = analyze_calculations(snapshot, inventory, references)
    access = analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
    rungs = analyze_rungs(snapshot, inventory, references, access, calculations)
    relationships = analyze_relationships(snapshot, inventory, references, access, calculations, rungs)
    conditions = analyze_conditions(snapshot, inventory, references, access, calculations, rungs, relationships, schema_version=6)
    binding = analyze_binding_context(snapshot, inventory, references, access, calculations, rungs, relationships, conditions)
    tags = analyze_tag_data(snapshot, inventory)
    structure = analyze_sfc_structure(snapshot, inventory)
    sfc = analyze_sfc_conditions(snapshot, inventory, references, structure)
    parts = snapshot, inventory, references, access, calculations, rungs, relationships, conditions, binding, tags, structure, sfc
    return (*parts, analyze_rack_backing_context(*parts))


class RackBackingContextTests(unittest.TestCase):
    def setUp(self):
        scope = source_reuse_scope()
        scope.__enter__()
        self.addCleanup(scope.__exit__, None, None, None)

    def test_source_paths_join_rll_and_sfc_without_changing_prior_models(self):
        parts = capture()
        before = deepcopy(parts[1:-1])
        result = parts[-1]
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.coverage['roots_by_disposition']['associated'], 2)
        self.assertEqual(result.coverage['rll_uses_by_disposition']['associated'], 3)
        self.assertEqual(result.coverage['sfc_uses_by_disposition']['associated'], 2)
        self.assertEqual(result.coverage['shared_addresses'], 1)
        self.assertEqual(len(result.addresses), 2)
        self.assertEqual({row['backing_suffix'] for row in result.addresses}, {'.Slot[3].Data.0'})
        self.assertTrue(all(row['data_type'] == 'BOOL' for row in result.addresses))
        self.assertEqual(result.coverage['associated_predicate_uses'], 2)
        self.assertEqual(result.coverage['associated_output_uses'], 1)
        self.assertEqual(parts[8].coverage['candidate_address_uses'], 3)
        self.assertEqual(parts[11].coverage['references_by_binding']['unresolved'], 2)
        self.assertEqual(result.to_dict(), json.loads(render_rack_backing_context_json(result)))
        validate_rack_backing_context(*parts)
        self.assertEqual(before, parts[1:-1])

    def test_scalar_members_bits_and_whole_slot_preserve_exact_suffix(self):
        suffixes = ('', '.Data', '.Fault', '.Data.31', '.data.00', '.Data.32', '.Fault.99',
                    '.Data[-1]', '.Data[0]', '.Data.Data', '.Unknown', '.0')
        result = capture(fixture(rungs=tuple(f'XIC(Remote:3:I{suffix});' for suffix in suffixes), sfc=''))[-1]
        outcomes = {row['suffix']: row for row in result.addresses}
        for suffix in suffixes[:5]:
            self.assertEqual(outcomes[suffix]['disposition'], 'associated', suffix)
            self.assertEqual(outcomes[suffix]['backing_suffix'], '.Slot[3]' + suffix)
        self.assertEqual(outcomes['.Data.32']['disposition'], 'bit_out_of_range')
        self.assertEqual(outcomes['.Fault.99']['disposition'], 'bit_out_of_range')
        for suffix in ('.Data[0]', '.Data.Data', '.Unknown', '.0'):
            self.assertEqual(outcomes[suffix]['disposition'], 'suffix_unsupported')
        self.assertNotIn('.Data[-1]', outcomes)  # Remains the historical dynamic-index gap.
        output = capture(fixture(rungs=('XIC(Remote:3:O.Fault);',), sfc=''))[-1]
        self.assertEqual(output.addresses[0]['disposition'], 'member_unavailable')

    def test_alias_targets_are_typed_before_caller_suffix_and_bad_metadata_is_retained(self):
        tags = ('<Tag Name="Word" TagType="Alias" DataType="DINT" AliasFor="Remote:3:I.Data"/>'
                '<Tag Name="Bit" TagType="Alias" DataType="BOOL" AliasFor="Word.1"/>')
        text = fixture(tags=tags, rungs=('XIC(Word.1)XIC(Bit);',), sfc='Bit')
        good = capture(text)[-1]
        self.assertEqual(good.coverage['rll_uses_by_disposition']['associated'], 2)
        self.assertEqual(good.coverage['sfc_uses_by_disposition']['associated'], 1)
        for old, new in (('DataType="DINT" AliasFor=', 'DataType="REAL" AliasFor='),
                         ('Name="Word" TagType=', 'Name="Word" Dimensions="1" TagType=')):
            result = capture(text.replace(old, new))[-1]
            self.assertEqual(result.coverage['rll_uses_by_disposition']['alias_metadata_unqualified'], 2)
            self.assertEqual(result.coverage['sfc_uses_by_disposition']['alias_metadata_unqualified'], 1)
            self.assertEqual(result.coverage['roots_by_disposition']['associated'], 2)
        composed = capture(fixture(tags='<Tag Name="Bad" TagType="Alias" AliasFor="Remote:3:I.Data"/>',
                                   rungs=('XIC(Bad.Data);',), sfc='Bad.Data'))[-1]
        self.assertEqual(composed.coverage['rll_uses_by_disposition']['suffix_unsupported'], 1)
        self.assertEqual(composed.coverage['sfc_uses_by_disposition']['suffix_unsupported'], 1)

    def test_alias_values_do_not_rescue_a_missing_target(self):
        text = fixture().replace('AliasFor="Remote:3:I.Data.0"/>',
            'AliasFor="Missing:3:I.Data.0"><Data Format="Decorated"><DataValue DataType="BOOL" Value="1"/></Data></Tag>')
        result = capture(text)[-1]
        self.assertEqual(result.coverage['sfc_uses_by_disposition']['candidate_unavailable'], 1)
        self.assertEqual(result.coverage['sfc_uses_by_disposition']['associated'], 1)

    def test_occurrence_and_alias_source_qualification_are_independent_of_good_roots(self):
        base = fixture(rungs=('XIC(ProbeAlias);',), sfc='ProbeAlias')
        for old, new, rll, sfc in (
            ('<RLLContent>', '<RLLContent xmlns="urn:foreign">', 1, 0),
            ('<Text>', '<Text xmlns="urn:foreign">', 1, 0),
            ('<Rung Number=', '<Rung Protected="false" Number=', 1, 0),
            ('<Tag Name="ProbeAlias"', '<Tag SourceKey="" Name="ProbeAlias"', 1, 1),
            ('<Transition ID=', '<Transition Protected="false" ID=', 0, 1),
        ):
            with self.subTest(new=new):
                result = capture(base.replace(old, new))[-1]
                self.assertEqual(result.coverage['roots_by_disposition']['associated'], 2)
                self.assertEqual(result.coverage['rll_uses_by_disposition']['source_unqualified'], rll)
                self.assertEqual(result.coverage['sfc_uses_by_disposition']['source_unqualified'], sfc)

    def test_root_failures_never_produce_destination_paths(self):
        base = fixture()
        variants = (
            base.replace('CatalogNumber="1756-EN2T"', 'CatalogNumber="PRIVATE_OTHER"'),
            base.replace('<Modules>', '<Modules xmlns="urn:foreign">'),
            base.replace('<Modules>', '<Modules Protected="false">'),
            base.replace('Name="Remote"', 'Name="Remote" UserDefinedCatalogNumber="1756-EN2T"'),
            base.replace('Name="Slot"', 'Name="Data"'),
            base.replace('Index="[3]"', 'Index="[4]"'),
            base.replace('<Tag Name="ProbeAlias"', '<Tag Name="Remote:I"/><Tag Name="ProbeAlias"'),
            base.replace('<InputTag>', '<InputTag Name="Wrong:I">'),
        )
        for text in variants:
            with self.subTest(text=text[:40]):
                result = capture(text)[-1]
                self.assertGreater(sum(row['disposition'] != 'associated' for row in result.roots), 0)
                self.assertTrue(all(row['backing_suffix'] is None for row in result.addresses
                                    if row['disposition'] != 'associated'))

    def test_duplicate_rack_declarations_and_decorated_formats_fail_closed(self):
        duplicate = fixture().replace('<InAliasTag/>', '<InAliasTag/><InAliasTag/>')
        result = capture(duplicate)[-1]
        self.assertEqual(result.coverage['roots_by_disposition']['duplicate_candidate_name'], 2)
        self.assertEqual(result.coverage['sfc_uses_by_disposition']['candidate_ambiguous'], 2)
        duplicate_data = fixture().replace(slot_data(), slot_data() + slot_data())
        self.assertEqual(capture(duplicate_data)[-1].coverage['roots_by_disposition']['representation_ambiguous'], 1)
        baseline = capture(fixture(output_l5k=False))[-1]
        alternatives = capture(fixture(output_l5k=True))[-1]
        self.assertEqual(baseline.coverage, alternatives.coverage)

    def test_captured_type_grammar_is_not_a_product_profile_catalogue(self):
        invented = fixture().replace('1756_CNB_', '1756_INDEPENDENT_')
        self.assertEqual(capture(invented)[-1].coverage['roots_by_disposition']['associated'], 2)
        for text in (invented.replace('AB:1756_', 'AB:1794_'),
                     invented.replace('_SLOT:I:0', '_SLOT:O:0')):
            self.assertEqual(capture(text)[-1].coverage['roots_by_disposition']['associated'],
                             0 if 'AB:1794_' in text else 1)

    def test_common_namespace_and_uninterpreted_values_keep_structural_proof(self):
        text = fixture().replace('<RSLogix5000Content ', '<RSLogix5000Content xmlns="urn:logix" ', 1)
        text = text.replace(' Value="0"', ' Value="PRIVATE_UNINTERPRETED_VALUE"')
        result = capture(text)[-1]
        self.assertEqual(result.coverage['roots_by_disposition']['associated'], 2)
        self.assertEqual(result.coverage['rll_uses_by_disposition']['associated'], 3)
        self.assertNotIn('PRIVATE_UNINTERPRETED_VALUE', render_rack_backing_context_json(result))
        missing = capture(fixture().replace(' Value="0"', ''))[-1]
        self.assertEqual(missing.coverage['roots_by_disposition']['shape_unsupported'], 2)

    def test_full_projected_address_length_is_bounded(self):
        text = fixture(rungs=('XIC(Remote:3:I.Data.0);',), sfc='')
        length = len('Remote:I.Slot[3].Data.0')
        with patch.object(module, 'MAX_ADDRESS_LENGTH', length):
            self.assertEqual(capture(text)[-1].addresses[0]['disposition'], 'associated')
        with patch.object(module, 'MAX_ADDRESS_LENGTH', length - 1):
            self.assertEqual(capture(text)[-1].addresses[0]['disposition'], 'suffix_unsupported')

    def test_sfc_nonrack_gaps_and_unbound_suffixes_are_explicit(self):
        result = capture(fixture(sfc='Missing OR TRUE OR Remote:3:I.Data.32'))[-1]
        self.assertEqual(result.coverage['source_sfc_binding_gaps'], 3)
        self.assertEqual(result.coverage['sfc_uses_by_disposition']['non_rack_gap'], 2)
        self.assertEqual(result.coverage['sfc_uses_by_disposition']['bit_out_of_range'], 1)

    def test_controller_alias_target_scope_and_ordinary_shadowing(self):
        local = ('<Tags><Tag Name="Remote:3:I" DataType="DINT"/>'
                 '<Tag Name="Remote:I" DataType="DINT"/></Tags>')
        text = fixture(rungs=('XIC(ProbeAlias)XIC(Remote:3:I.Data.0);',),
                       sfc='ProbeAlias OR Remote:3:I.Data.0').replace(
                           '<Program Name="SyntheticProbe">', '<Program Name="SyntheticProbe">' + local)
        result = capture(text)[-1]
        self.assertEqual(result.coverage['rll_uses_by_disposition']['associated'], 1)
        self.assertEqual(result.coverage['sfc_uses_by_disposition']['associated'], 1)
        self.assertEqual(result.coverage['source_sfc_binding_gaps'], 1)

    def test_repeated_uses_share_addresses_and_index_shapes_once(self):
        text = fixture(rungs=tuple('XIC(ProbeAlias);' for _ in range(500)),
                       sfc=' OR '.join('ProbeAlias' for _ in range(40)))
        with patch.object(module, '_rack_shapes', wraps=module._rack_shapes) as shapes:
            result = capture(text)[-1]
        self.assertEqual(shapes.call_count, 1)
        self.assertEqual(len(result.addresses), 1)
        self.assertEqual(len(result.uses), 540)
        self.assertEqual(result.coverage['shared_addresses'], 1)
        self.assertLess(len(render_rack_backing_context_json(result)), module.MAX_CONTEXT_BYTES)

    def test_old_rack_diagnostics_are_unchanged_by_evidence_callback(self):
        parts = capture()
        for version in (1, 2):
            before = build_rack_backing_summary(parts[0], parts[1], parts[2], parts[9], schema_version=version)
            analyze_rack_backing_context(*parts[:-1])
            after = build_rack_backing_summary(parts[0], parts[1], parts[2], parts[9], schema_version=version)
            self.assertEqual(render_rack_backing_summary(before), render_rack_backing_summary(after))

    def test_canonical_replay_rejects_each_forged_row_family_and_companion(self):
        parts = capture()
        for name in ('roots', 'addresses', 'uses'):
            forged = deepcopy(parts[-1])
            getattr(forged, name)[0]['disposition'] = 'PRIVATE_FORGERY'
            with self.assertRaisesRegex(RackBackingContextError, '^Rack backing context does not match'):
                validate_rack_backing_context(*parts[:-1], forged)
        changed = deepcopy(parts[11])
        changed.references[0]['binding']['suffix'] = '.Data.31'
        with self.assertRaises(RackBackingContextError):
            analyze_rack_backing_context(*parts[:11], changed)
        with self.assertRaises(RackBackingContextError):
            validate_rack_backing_context(*parts[:-1], replace(parts[-1], schema_version=True))

    def test_limits_fail_before_serialization_and_at_exact_output_boundary(self):
        parts = capture()
        result = parts[-1]
        size = len(render_rack_backing_context_json(result))
        with patch.object(module, 'MAX_CONTEXT_BYTES', size):
            self.assertEqual(len(render_rack_backing_context_json(result)), size)
        with patch.object(module, 'MAX_CONTEXT_BYTES', size - 1):
            with self.assertRaises(RackBackingContextError):
                render_rack_backing_context_json(result)
        with patch.object(module, 'MAX_RECORDS', 1), patch('json.JSONEncoder.iterencode', side_effect=AssertionError):
            with self.assertRaises(RackBackingContextError):
                render_rack_backing_context_json(result)
        with patch.object(module, 'MAX_EVIDENCE_IDS', 1):
            with self.assertRaises(RackBackingContextError):
                analyze_rack_backing_context(*parts[:-1])
        cycle = deepcopy(result)
        cycle.roots.append(cycle.roots)
        with self.assertRaises(RackBackingContextError):
            render_rack_backing_context_json(cycle)


if __name__ == '__main__':
    unittest.main()
