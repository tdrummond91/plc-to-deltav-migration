"""Invented rack diagnostics; candidate matches never become root bindings."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from plc_workbench import module_io, rack_candidates
from plc_workbench.rack_candidates import build_rack_candidates, RackCandidateError
from plc_workbench.references import analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


FIXTURE = Path(__file__).resolve().parents[2] / 'public/fixtures/synthetic/rack_io_gap_demo.L5X'
LOCAL = ('<Module Name="Local" ParentModule="Local" ParentModPortId="1"><Ports>'
         '<Port Id="1" Type="ICP" Address="0" Upstream="false"/></Ports></Module>')


def card(name: str = 'Card', slot: str = '3', *, parent: str = 'Local',
         port_type: str = 'ICP', children: str = '<InAliasTag/><OutAliasTag/>',
         connection_attributes: str = '', extra_ports: str = '') -> str:
    return (f'<Module Name="{name}" ParentModule="{parent}" ParentModPortId="1">'
            f'<Ports><Port Id="1" Type="{port_type}" Address="{slot}" Upstream="true"/>'
            f'{extra_ports}</Ports><Communications><Connections>'
            f'<RackConnection {connection_attributes}>{children}</RackConnection>'
            '</Connections></Communications></Module>')


def tag(name: str, target: str | None = None) -> str:
    return (f'<Tag Name="{name}" TagType="Base"/>' if target is None else
            f'<Tag Name="{name}" TagType="Alias" AliasFor="{target}"/>')


def routine(text: str) -> str:
    return ('<Routines><Routine Name="Main" Type="RLL"><RLLContent><Rung Number="0" Type="N">'
            f'<Text><![CDATA[{text}]]></Text></Rung></RLLContent></Routine></Routines>')


def program(text: str, tags: str = '') -> str:
    return f'<Programs><Program Name="P"><Tags>{tags}</Tags>{routine(text)}</Program></Programs>'


def controller(modules: str, text: str = '', tags: str = '', *, name: str = 'Invented',
               extra: str = '') -> str:
    return (f'<Controller Name="{name}"><Modules>{modules}</Modules><Tags>{tags}</Tags>'
            f'{program(text) if text else ""}{extra}</Controller>')


def inventory(body: str):
    return analyze_snapshot(snapshot_from_bytes(
        f'<RSLogix5000Content>{body}</RSLogix5000Content>'.encode()))


def diagnostics(source):
    references = analyze_references(source)
    return build_rack_candidates(source, references.aliases, references.operands)


class RackCandidateTests(unittest.TestCase):
    def test_fixture_candidates_match_separate_populations_without_binding(self) -> None:
        source = analyze_snapshot(snapshot_from_bytes(FIXTURE.read_bytes()))
        references = analyze_references(source)
        before_source, before_references = source.to_dict(), references.to_dict()
        value = build_rack_candidates(source, references.aliases, references.operands)
        self.assertEqual([row['name'] for row in value['candidates']], ['Remote:3:I', 'Remote:3:O'])
        self.assertEqual([row['backing_status'] for row in value['candidates']], ['not_analyzed'] * 2)
        for group, count in [('aliases', 1), ('direct_operands', 2), ('alias_operands', 1)]:
            self.assertEqual(len(value['matches'][group]), count)
            self.assertEqual({row['status'] for row in value['matches'][group]}, {'unique_candidate'})
            self.assertTrue(all(row['candidate_count'] == 1 for row in value['matches'][group]))
        candidate_ids = {row['source_id'] for row in value['candidates']}
        self.assertTrue(all(row['candidate_id'] in candidate_ids
                            for group in value['matches'].values() for row in group))
        self.assertEqual([row['status'] for row in references.operands],
                         ['unresolved', 'unresolved', 'unresolved', 'root_bound', 'root_bound'])
        self.assertTrue(candidate_ids.isdisjoint(row['id'] for row in references.symbols))
        self.assertEqual(source.to_dict(), before_source)
        self.assertEqual(references.to_dict(), before_references)

    def test_empty_inventory_has_empty_fixed_shape(self) -> None:
        self.assertEqual(build_rack_candidates(inventory(controller('')), [], []),
                         {'candidates': [], 'matches': {'aliases': [], 'direct_operands': [], 'alias_operands': []}})

    def test_candidate_source_links_and_direction_are_exact(self) -> None:
        source = inventory(controller(LOCAL + card()))
        by_id = {entity.id: entity for entity in source.entities}
        rows = build_rack_candidates(source, [], [])['candidates']
        for row, direction, kind in zip(rows, ('input', 'output'),
                                       ('module_rack_input_alias', 'module_rack_output_alias')):
            self.assertEqual(set(row), {'source_id', 'connection_id', 'module_id', 'scope_id',
                                       'direction', 'name', 'name_origin', 'reason', 'backing_status'})
            self.assertEqual(by_id[row['source_id']].kind, kind)
            self.assertEqual(by_id[row['source_id']].parent_id, row['connection_id'])
            self.assertEqual(by_id[row['connection_id']].parent_id, row['module_id'])
            self.assertEqual(by_id[row['module_id']].scope_id, row['scope_id'])
            self.assertEqual(row['direction'], direction)
            self.assertEqual(row['name_origin'], 'backplane_slot')
            self.assertIsNone(row['reason'])

    def test_duplicate_declarations_remain_ambiguous(self) -> None:
        source = inventory(controller(LOCAL + card(children='<InAliasTag/><InAliasTag/>'),
                                      'XIC(Local:3:I.Data);'))
        value = diagnostics(source)
        self.assertEqual(len({row['source_id'] for row in value['candidates']}), 2)
        match = value['matches']['direct_operands'][0]
        self.assertEqual((match['status'], match['candidate_count'], match['candidate_id']),
                         ('ambiguous_candidate', 2, None))

    def test_alias_terminal_uses_declaration_scope_despite_program_shadowing(self) -> None:
        tags = tag('First', 'Second') + tag('Second', 'LOCAL:3:i.Data')
        source = inventory(controller(LOCAL + card(), tags=tags,
                                      extra=program('XIC(First);', tag('Second'))))
        value = diagnostics(source)
        controller_id = next(e.id for e in source.entities if e.kind == 'controller')
        self.assertEqual(len(value['matches']['aliases']), 2)
        match = value['matches']['alias_operands'][0]
        self.assertEqual(match['terminal_root'], 'LOCAL:3:i')
        self.assertEqual(match['lookup_scope_id'], controller_id)
        self.assertEqual(match['status'], 'unique_candidate')
        self.assertEqual(value['matches']['direct_operands'], [])

    def test_program_fallback_reaches_own_controller_candidates(self) -> None:
        source = inventory(controller(LOCAL + card(), 'XIC(local:3:i);'))
        value = diagnostics(source)
        program_id = next(e.id for e in source.entities if e.kind == 'program')
        row = value['matches']['direct_operands'][0]
        self.assertEqual(row['lookup_scope_id'], program_id)
        self.assertEqual(row['status'], 'unique_candidate')

    def test_aoi_isolation_and_other_controller_are_outside_visible_scope(self) -> None:
        aoi = ('<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="Isolated">'
               + routine('XIC(Local:3:I);') + '</AddOnInstructionDefinition></AddOnInstructionDefinitions>')
        source = inventory(controller(LOCAL + card(), name='One', extra=aoi)
                           + controller('', 'XIC(Local:3:I);', name='Two'))
        rows = diagnostics(source)['matches']['direct_operands']
        self.assertEqual(len(rows), 2)
        self.assertEqual([row['status'] for row in rows], ['outside_visible_scope'] * 2)
        self.assertEqual([row['candidate_count'] for row in rows], [1, 1])
        self.assertTrue(all(row['candidate_id'] is None for row in rows))

    def test_visible_exact_match_precedes_unavailable_names(self) -> None:
        source = inventory(controller(LOCAL + card() + card('Incomplete', parent='Absent'),
                                      'XIC(Local:3:I);'))
        row = diagnostics(source)['matches']['direct_operands'][0]
        self.assertEqual((row['status'], row['candidate_count']), ('unique_candidate', 1))

    def test_unavailable_is_uncertainty_and_precedes_outside_scope(self) -> None:
        source = inventory(controller(LOCAL + card(), name='One')
                           + controller(card(parent='Absent'), 'XIC(Local:3:I)XIC(Missing:8:O);', name='Two'))
        rows = diagnostics(source)['matches']['direct_operands']
        self.assertEqual([row['status'] for row in rows], ['candidate_names_unavailable'] * 2)
        self.assertEqual([row['candidate_count'] for row in rows], [2, 2])
        self.assertTrue(all(row['candidate_id'] is None for row in rows))

    def test_unmatched_root_and_suffix_remain_unmatched(self) -> None:
        source = inventory(controller(LOCAL + card(), 'XIC(Local:3:I2)XIC(Unknown:3:I);'))
        rows = diagnostics(source)['matches']['direct_operands']
        self.assertEqual([row['status'] for row in rows], ['no_candidate_match'] * 2)
        self.assertEqual([row['candidate_count'] for row in rows], [0, 0])

    def test_only_missing_colon_roots_enter_diagnostics(self) -> None:
        source = inventory(controller(LOCAL + card(),
                                      'XIC(Known)XIC(Missing)XIC(Known[Index])XIC(Bad?)NOP();',
                                      tag('Known')))
        self.assertTrue(all(not rows for rows in diagnostics(source)['matches'].values()))

    def test_rack_attributes_are_preserved_but_do_not_generate_names(self) -> None:
        for children, attributes in [('<InAliasTag Name="Claimed:I"/>', ''),
                                     ('<InAliasTag AliasFor="Backing:I.Data"/>', ''),
                                     ('<InAliasTag/>', 'InputTagSuffix="I2"')]:
            source = inventory(controller(LOCAL + card(children=children, connection_attributes=attributes)))
            before = source.to_dict()
            row = build_rack_candidates(source, [], [])['candidates'][0]
            self.assertEqual((row['name'], row['name_origin'], row['reason']),
                             (None, 'unavailable', 'unsupported_rack_attributes'))
            self.assertEqual(source.to_dict(), before)

    def test_direct_ethernet_rack_aliases_are_not_guessed(self) -> None:
        bridge = ('<Module Name="Bridge" ParentModule="Local" ParentModPortId="1"><Ports>'
                  '<Port Id="1" Type="ICP" Address="2" Upstream="true"/>'
                  '<Port Id="2" Type="Ethernet" Address="192.0.2.1" Upstream="false"/></Ports></Module>')
        ethernet_card = card(parent='Bridge', port_type='Ethernet', slot='192.0.2.2').replace(
            'ParentModPortId="1"', 'ParentModPortId="2"')
        source = inventory(controller(LOCAL + bridge + ethernet_card))
        rows = build_rack_candidates(source, [], [])['candidates']
        self.assertEqual([row['reason'] for row in rows], ['unsupported_rack_port_type'] * 2)

    def test_unexpected_rack_text_or_children_never_produce_candidates(self) -> None:
        for children in ('<InAliasTag>Opaque</InAliasTag>',
                         '<InAliasTag><Unexpected/></InAliasTag>',
                         'Opaque<InAliasTag/>', '<Unexpected/><InAliasTag/>',
                         '<Description>Opaque</Description><InAliasTag/>'):
            with self.subTest(children=children):
                source = inventory(controller(LOCAL + card(children=children)))
                row = build_rack_candidates(source, [], [])['candidates'][0]
                self.assertEqual((row['name'], row['reason']), (None, 'unsupported_rack_content'))
        source = inventory(controller(LOCAL + card(children=' \n <InAliasTag> \t </InAliasTag> \n ')))
        self.assertEqual(build_rack_candidates(source, [], [])['candidates'][0]['name'], 'Local:3:I')

    def test_checked_topology_rejects_incomplete_duplicate_and_unsupported_contexts(self) -> None:
        cases = [
            (LOCAL + card(parent='Missing'), 'missing_parent_module'),
            (LOCAL + LOCAL + card(), 'ambiguous_parent_module'),
            (LOCAL + card(slot='03'), 'invalid_slot'),
            (LOCAL.replace('Type="ICP"', 'Type="Unknown"') + card(port_type='Unknown'), 'unsupported_port_type'),
            (LOCAL + card(extra_ports='<Port Id="1" Type="ICP" Address="9" Upstream="false"/>'), 'invalid_upstream_port'),
        ]
        for modules, reason in cases:
            with self.subTest(reason=reason):
                rows = build_rack_candidates(inventory(controller(modules)), [], [])['candidates']
                self.assertTrue(all(row['reason'] == reason and row['name'] is None for row in rows))

    def test_malformed_private_parent_and_scope_links_are_unavailable(self) -> None:
        source = inventory(controller(LOCAL + card()))
        original = next(e for e in source.entities if e.kind == 'module_rack_input_alias')
        for change, expected in [({'parent_id': None}, 'missing_connection_context'),
                                 ({'scope_id': None}, 'missing_module_context')]:
            changed = replace(source, entities=[replace(e, **change) if e.id == original.id else e
                                                for e in source.entities])
            row = build_rack_candidates(changed, [], [])['candidates'][0]
            self.assertEqual(row['reason'], expected)

    def test_limits_bound_names_topology_and_repeated_terminal_evidence(self) -> None:
        source = inventory(controller(LOCAL + card(), 'XIC(Local:3:I)XIC(Local:3:I);'))
        references = analyze_references(source)
        with patch.object(module_io, 'MAX_IO_NAME_LENGTH', 9):
            rows = build_rack_candidates(source, [], [])['candidates']
            self.assertTrue(all(row['name'] == f"Local:3:{'I' if row['direction'] == 'input' else 'O'}" for row in rows))
        with patch.object(module_io, 'MAX_IO_NAME_LENGTH', 8):
            rows = build_rack_candidates(source, [], [])['candidates']
            self.assertEqual([row['reason'] for row in rows], ['name_length_limit'] * 2)
        with patch.object(module_io, 'MAX_TOPOLOGY_DEPTH', 1):
            rows = build_rack_candidates(source, [], [])['candidates']
            self.assertEqual([row['reason'] for row in rows], ['topology_depth_limit'] * 2)
        value = build_rack_candidates(source, references.aliases, references.operands)
        rows = value['candidates'] + value['matches']['direct_operands']
        total_characters = sum(len(item) for row in rows for item in row.values() if isinstance(item, str))
        self.assertGreater(total_characters, 36)  # Source IDs/scopes are also retained evidence.
        with patch.object(rack_candidates, 'MAX_EXPANDED_EVIDENCE_CHARS', total_characters):
            value = build_rack_candidates(source, references.aliases, references.operands)
            self.assertEqual(len(value['matches']['direct_operands']), 2)
        for budget in (17, 36, total_characters - 1):
            with self.subTest(budget=budget), patch.object(rack_candidates, 'MAX_EXPANDED_EVIDENCE_CHARS', budget):
                with self.assertRaisesRegex(RackCandidateError, '^Rack candidate analysis exceeds the expanded-evidence limit[.]$'):
                    build_rack_candidates(source, references.aliases, references.operands)

    def test_ordinary_module_names_are_unchanged_by_rack_candidate_building(self) -> None:
        source = analyze_snapshot(snapshot_from_bytes(FIXTURE.read_bytes()))
        before = module_io.derive_module_io_names(source)
        self.assertEqual([row['name'] for row in before.values()], ['Remote:I', 'Remote:O', 'Remote:3:C'])
        build_rack_candidates(source, [], [])
        self.assertEqual(module_io.derive_module_io_names(source), before)

    def test_candidate_building_does_not_read_source_again(self) -> None:
        source = inventory(controller(LOCAL + card(), 'XIC(Local:3:I);'))
        references = analyze_references(source)
        before = deepcopy(references.operands)
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('unexpected source IO')):
            self.assertEqual(build_rack_candidates(source, references.aliases, references.operands)
                             ['matches']['direct_operands'][0]['status'], 'unique_candidate')
        self.assertEqual(references.operands, before)


if __name__ == '__main__':
    unittest.main()
