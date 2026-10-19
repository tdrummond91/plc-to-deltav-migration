"""Invented source evidence for SFC/RLL links and explicitly unbound hints."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from html import escape
import json
import unittest
from unittest.mock import patch

from plc_workbench.access import analyze_access
from plc_workbench.calculations import analyze_calculations
from plc_workbench.references import analyze_references
from plc_workbench.relationships import analyze_relationships
from plc_workbench.rung_analysis import analyze_rungs
from plc_workbench.sfc_conditions import analyze_sfc_conditions
from plc_workbench.sfc_context import (SfcContextError, analyze_sfc_context,
    render_sfc_context_json, validate_sfc_context, _match)
from plc_workbench.sfc_structure import analyze_sfc_structure
from plc_workbench.sfr_context import analyze_sfr_context
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from test_module_io import LOCAL, communications, module, port


def transition(text: str = 'A', identifier: str = '10') -> str:
    return f'<Transition ID="{identifier}"><Condition><STContent><Line Number="0">{escape(text)}</Line></STContent></Condition></Transition>'


def step(operand: str = 'State', identifier: str = '1') -> str:
    return f'<Step ID="{identifier}" Operand="{operand}" InitialStep="false"/>'


def chart(body: str, name: str = 'Chart', edits: str = '') -> str:
    return f'<Routine Name="{name}" Type="SFC"><SFCContent>{body}</SFCContent>{edits}</Routine>'


def fixture(*, text: str = 'A', body: str | None = None, rungs: tuple[str, ...] = (),
        tags: str = '', local: str = '', peers: str = '', edits: str = '',
        other_programs: str = '', modules: str = '') -> str:
    rung_text = ''.join(f'<Rung Number="{n}"><Text>{escape(text)}</Text></Rung>' for n, text in enumerate(rungs))
    return ('<RSLogix5000Content xmlns:x="urn:foreign"><Controller Name="C"><Tags>'
        '<Tag Name="A" DataType="BOOL"/><Tag Name="B" DataType="BOOL"/>'
        '<Tag Name="State" DataType="SFC_STEP"/><Tag Name="Array" DataType="SFC_STEP" Dimensions="4"/>'
        f'{tags}</Tags><Modules>{modules}</Modules><Programs><Program Name="P"><Tags>{local}</Tags><Routines>'
        + chart(transition(text) if body is None else body, edits=edits) + peers
        + f'<Routine Name="Logic" Type="RLL"><RLLContent>{rung_text}</RLLContent></Routine>'
        f'</Routines></Program>{other_programs}</Programs></Controller></RSLogix5000Content>')


def capture_xml(xml: str):
    snapshot = snapshot_from_bytes(xml.encode())
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    calculations = analyze_calculations(snapshot, inventory, references)
    access = analyze_access(inventory, references, schema_version=4, snapshot=snapshot, calculations=calculations)
    rungs = analyze_rungs(snapshot, inventory, references, access, calculations)
    relationships = analyze_relationships(snapshot, inventory, references, access, calculations, rungs)
    structure = analyze_sfc_structure(snapshot, inventory)
    sfr = analyze_sfr_context(snapshot, inventory, references, access, calculations, structure, schema_version=2)
    conditions = analyze_sfc_conditions(snapshot, inventory, references, structure)
    args = snapshot, inventory, references, access, calculations, rungs, relationships, structure, sfr, conditions
    return (*args, analyze_sfc_context(*args))


def capture(**kwargs):
    return capture_xml(fixture(**kwargs))


class SfcContextTests(unittest.TestCase):
    def test_empty_chart_and_literal_only_have_complete_empty_relationships(self):
        for args in (capture(body=''), capture(text='1')):
            with self.subTest(transitions=args[-1].coverage['source_transitions']):
                self.assertEqual(args[-1].status, 'complete')
                self.assertEqual(args[-1].references, [])
                validate_sfc_context(*args)

    def test_exact_addresses_intern_once_without_reader_writer_pairs(self):
        args = capture(text='A OR A', rungs=('XIC(A)OTE(A);', 'XIC(A)OTE(A);'))
        before = deepcopy(args[:-1])
        result = args[-1]
        self.assertEqual(len(result.references), 2)
        self.assertEqual(len(result.addresses), 1)
        address = result.addresses[0]
        self.assertEqual(len(address['condition_reference_ids']), 2)
        self.assertEqual(len(address['read_operand_ids']), 2)
        self.assertEqual(len(address['write_operand_ids']), 2)
        self.assertEqual(address['relationship_address_id'], args[6].addresses[0]['id'])
        self.assertEqual(result.to_dict(), json.loads(render_sfc_context_json(result)))
        validate_sfc_context(*args)
        self.assertEqual(before, args[:-1])

    def test_read_write_unknown_and_expression_occurrences_are_distinct(self):
        result = capture(text='A', rungs=('XIC(A)OTE(A)ONS(A)PID(A,B,B,B,0,0,0)CPT(B,A+A);',))[-1]
        self.assertEqual(result.coverage['accepted_operands_by_role'], {'read': 1, 'read_write': 1, 'unknown': 1, 'write': 1})
        self.assertEqual(result.coverage['accepted_expression_uses'], 2)
        self.assertEqual(len(result.addresses[0]['write_operand_ids']), 1)
        self.assertEqual(result.status, 'partial')

    def test_aliases_and_local_shadowing_retain_declaration_scope(self):
        tags = '<Tag Name="AliasA" TagType="Alias" AliasFor="A"/>'
        args = capture(text='A OR AliasA', local='<Tag Name="A" DataType="BOOL"/>',
                       tags=tags, rungs=('OTE(A)OTE(AliasA);',))
        self.assertEqual(len(args[-1].addresses), 2)
        self.assertNotEqual(*[row['target_id'] for row in args[-1].addresses])
        self.assertEqual([len(row['write_operand_ids']) for row in args[-1].addresses], [1, 1])

    def test_steps_match_exact_or_literal_member_boundary_not_array_overlap(self):
        body = step('State.X', '1') + step('Array[0]', '2') + step('Array', '3')
        body += transition('State.X OR State.X.Y OR State.XY OR Array[0].X OR Array[00].X')
        args = capture(body=body)
        result = args[-1]
        self.assertEqual([len(row['step_link_ids']) for row in result.references], [1, 1, 0, 1, 0])
        self.assertEqual(result.coverage['step_links_by_match'], {'base_member': 2, 'exact': 1})

    def test_duplicate_steps_and_edits_and_peers_never_choose_execution(self):
        body = step() + step(identifier='2') + transition('State.X')
        edits = '<SFCContent OnlineEditType="PendingEdits">' + step(identifier='3') + '</SFCContent>'
        args = capture(body=body, edits=edits, peers=chart(step(identifier='4'), 'Peer'))
        result = args[-1]
        self.assertEqual(result.coverage['step_links_by_relation'], {'same_content': 2, 'other_edit': 1, 'peer_chart': 1})
        self.assertEqual(result.coverage['references_with_multiple_steps'], 1)
        self.assertEqual(len(result.references[0]['step_link_ids']), 4)
        self.assertEqual(result.edit_selection, 'not_implemented')

    def test_step_index_skips_thousand_unrelated_suffixes_per_reference(self):
        body = ''.join(step(f'State.Step{n}', str(n)) for n in range(1000))
        body += ''.join(transition(f'State.Reference{n}', str(1000 + n)) for n in range(1000))
        for variant in (body, body.replace('State', 'Missing')):
            with self.subTest(bound=variant is body), patch('plc_workbench.sfc_context._match', wraps=_match) as matches:
                result = capture(body=variant)[-1]
                self.assertEqual(result.coverage['references_total'], 1000)
                self.assertEqual(result.coverage['source_steps'], 1000)
                self.assertEqual(result.step_links, [])
                self.assertEqual(matches.call_count, 0)

    def test_step_index_restores_source_order_across_exact_and_member_keys(self):
        body = step('State', '1') + step('State.X.Y', '2') + step('State.X', '3')
        body += transition('State.X.Y')
        args = capture(body=body)
        self.assertEqual([row['step_element_id'] for row in args[-1].step_links],
                         [row['element_id'] for row in args[8].steps])
        self.assertEqual([row['match_kind'] for row in args[-1].step_links], ['base_member', 'exact', 'base_member'])
        lexical = capture(body=body.replace('State', 'Missing'))
        self.assertEqual([row['step_element_id'] for row in lexical[-1].step_links],
                         [row['element_id'] for row in lexical[8].steps])
        self.assertTrue(all(row['evidence'] == 'lexical_hint' for row in lexical[-1].step_links))

    def test_boolean_spelling_is_a_gap_hint_not_a_value_or_rebound_symbol(self):
        result = capture(text='TRUE OR FALSE', tags='<Tag Name="TRUE" DataType="BOOL"/>')[-1]
        self.assertEqual(result.coverage['references_by_status'], {'binding_gap': 1, 'exact_address': 1, 'namespace_gap': 0})
        self.assertEqual(result.gaps[0]['kind'], 'root_missing')
        self.assertEqual(result.gaps[0]['lexical_kind'], 'boolean_word')
        self.assertEqual(result.gaps[0]['root_text'], 'FALSE')

    def test_root_missing_and_alias_target_gap_remain_distinct(self):
        tags = '<Tag Name="Broken" TagType="Alias" AliasFor="Missing.Member"/>'
        result = capture(text='Missing.X OR Broken', tags=tags)[-1]
        self.assertEqual([row['kind'] for row in result.gaps], ['root_missing', 'alias_chain_gap'])
        self.assertEqual([row['root_text'] for row in result.gaps], ['Missing', 'Missing'])
        self.assertNotEqual(*[row['lookup_scope_id'] for row in result.gaps])

    def test_only_outside_eligible_scope_declarations_are_gap_candidates(self):
        other = '<Program Name="Q"><Tags><Tag Name="Missing" DataType="BOOL"/></Tags></Program>'
        args = capture(text='Missing', other_programs=other)
        gap = args[-1].gaps[0]
        self.assertEqual(len(gap['outside_scope_entity_ids']), 1)
        self.assertIsNone(args[-1].references[0]['address_id'])
        self.assertEqual(args[-1].coverage['gaps_with_outside_declarations'], 1)

    def test_outside_foreign_declaration_is_retained_but_not_qualified(self):
        other = '<Program Name="Q"><Tags><x:Tag Name="Missing" DataType="BOOL"/></Tags></Program>'
        result = capture(text='Missing', other_programs=other)[-1]
        self.assertEqual(result.gaps[0]['outside_scope_entity_ids'], [])
        self.assertEqual(len(result.gaps[0]['unqualified_outside_scope_entity_ids']), 1)

    def test_unbound_step_lexical_hints_preserve_scope_and_namespace(self):
        body = step('Missing') + '<Step ID="3" Operand="Missing" x:Marker="foreign"/>' + transition('Missing.X')
        other = '<Program Name="Q"><Routines>' + chart(step('Missing'), 'Peer') + '</Routines></Program>'
        result = capture(body=body, other_programs=other)[-1]
        self.assertEqual(result.coverage['step_links_by_evidence'], {'bound_identity': 0, 'lexical_hint': 2})
        self.assertEqual(result.coverage['unqualified_step_links'], 1)
        self.assertEqual(result.coverage['gaps_with_lexical_steps'], 1)
        self.assertEqual(result.addresses, [])

    def test_namespace_confounded_rll_use_is_quarantined_per_occurrence(self):
        xml = fixture(rungs=('OTE(A);', 'OTE(A);')).replace('<Text>OTE(A);</Text>', '<Text x:Name="foreign">OTE(A);</Text>', 1)
        args = capture_xml(xml)
        self.assertEqual(len(args[6].addresses[0]['write_operand_ids']), 2)
        address = args[-1].addresses[0]
        self.assertEqual(len(address['write_operand_ids']), 1)
        self.assertEqual(len(address['unqualified_operand_ids_by_role']['write']), 1)
        self.assertEqual(args[-1].coverage['addresses_with_rejected_uses'], 1)

    def test_foreign_alias_chain_cannot_be_promoted_by_final_target(self):
        tags = '<Tag Name="AliasA" TagType="Alias" AliasFor="A" x:Marker="foreign"/>'
        result = capture(text='AliasA', tags=tags)[-1]
        self.assertEqual(result.references[0]['status'], 'namespace_gap')
        self.assertEqual(result.addresses, [])

    def test_inferred_module_name_needs_qualified_port_and_parent_chain(self):
        modules = LOCAL + module(communications=communications('<InputTag/>'))
        qualified = capture(text='Local:3:I.Data', modules=modules)[-1]
        self.assertEqual(qualified.references[0]['status'], 'exact_address')
        modules = modules.replace('<Port Id="1" Type="ICP" Address="3" Upstream="true"/>',
                                  '<Port Id="1" Type="ICP" Address="3" Upstream="true" x:Marker="foreign"/>')
        args = capture(text='Local:3:I.Data', modules=modules)
        self.assertEqual(args[9].references[0]['binding_status'], 'root_bound')
        self.assertEqual(args[-1].references[0]['status'], 'namespace_gap')
        self.assertEqual(args[-1].addresses, [])

    def test_explicit_module_name_does_not_require_unrelated_port(self):
        modules = module(ports='<x:Port Id="1"/>', communications=communications('<InputTag Name="Device:I"/>'))
        result = capture(text='Device:I.Data', modules=modules)[-1]
        self.assertEqual(result.references[0]['status'], 'exact_address')

    def test_unsupported_expression_does_not_invent_partial_relationships(self):
        result = capture(text='A + UNKNOWN_FUNC(B)')[-1]
        self.assertEqual(result.references, [])
        self.assertEqual(result.coverage['source_unparsed_transitions'], 1)
        self.assertEqual(result.status, 'partial')

    def test_canonical_replay_rejects_foreign_input_and_every_forged_collection(self):
        args = capture(body=step() + transition('State.X OR Missing'), rungs=('OTE(State.X);',))
        for name in ('references', 'addresses', 'step_links', 'gaps'):
            result = deepcopy(args[-1])
            getattr(result, name)[0]['id'] = 'forged'
            with self.subTest(collection=name), self.assertRaises(SfcContextError):
                validate_sfc_context(*args[:-1], result)
        for index in (2, 3, 4, 5, 6, 7, 8, 9):
            inputs = list(deepcopy(args[:-1]))
            inputs[index].snapshot['id'] = 'forged'
            with self.subTest(dependency=index), self.assertRaises(SfcContextError):
                analyze_sfc_context(*inputs)

    def test_native_container_cycles_depth_types_and_record_limit_are_rejected(self):
        result = capture()[-1]
        forged = deepcopy(result)
        forged.references.append(forged.references)
        with self.assertRaises(SfcContextError):
            render_sfc_context_json(forged)
        with self.assertRaises(SfcContextError):
            render_sfc_context_json(replace(result, coverage={'foreign': object()}))
        with patch('plc_workbench.sfc_context.MAX_SFC_CONTEXT_RECORDS', 1), self.assertRaises(SfcContextError):
            render_sfc_context_json(result)

    def test_generation_and_render_resource_limits_fail_source_free(self):
        args = capture(text='A OR A', rungs=('OTE(A);',))
        for name in ('MAX_SFC_CONTEXT_BYTES', 'MAX_SFC_CONTEXT_JSON_BYTES', 'MAX_EVIDENCE_IDS'):
            with self.subTest(limit=name), patch(f'plc_workbench.sfc_context.{name}', 1):
                with self.assertRaisesRegex(SfcContextError, '^SFC context evidence is inconsistent or exceeds its limits[.]$'):
                    analyze_sfc_context(*args[:-1])


if __name__ == '__main__':
    unittest.main()
