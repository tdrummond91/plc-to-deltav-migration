"""Candidate graph tests use invented source, never plant private records."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import replace
from html import escape
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.reference_reporting import render_reference_json, render_reference_text
from plc_workbench.references import ReferenceError, analyze_references, validate_references
from plc_workbench.routine_graph import ROUTINE_GRAPH_CONSTANTS, RoutineGraphError, build_routine_graph
from plc_workbench.routine_targets import build_routine_targets
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.storage import StorageError, save_run


def routine(name: str, *texts: str, language: str | None = 'RLL', content: str | None = None) -> str:
    attributes = '' if language is None else f' Type="{language}"'
    if content is None:
        content = '<RLLContent>' + ''.join(
            f'<Rung Number="{index}" Type="N"><Text>{escape(text)}</Text></Rung>'
            for index, text in enumerate(texts)) + '</RLLContent>'
    return f'<Routine Name="{escape(name, quote=True)}"{attributes}>{content}</Routine>'


def program(name: str, *routines: str, attributes: str = '') -> str:
    return f'<Program Name="{name}" {attributes}><Routines>{"".join(routines)}</Routines></Program>'


def snapshot(*programs: str, extra: str = ''):
    data = (f'<RSLogix5000Content><Controller Name="PRIVATE_CONTROLLER"><Tags><Tag Name="A"/>'
            f'</Tags><Programs>{"".join(programs)}</Programs>{extra}</Controller></RSLogix5000Content>').encode()
    return snapshot_from_bytes(data)


def inventory(*programs: str, extra: str = ''):
    return analyze_snapshot(snapshot(*programs, extra=extra))


def graph(source):
    return build_routine_graph(source, build_routine_targets(source))


class RoutineGraphTests(unittest.TestCase):
    def test_grouped_chain_repeated_occurrences_and_isolated_nodes(self) -> None:
        source = inventory(program('PRIVATE_P', routine('A', 'JSR(B)JSR(B);'),
                                   routine('B', 'JSR(C);'), routine('C'), routine('Isolated')))
        result = graph(source)
        self.assertEqual(len(result['nodes']), 4)
        self.assertEqual(len(result['edges']), 2)
        self.assertEqual([len(edge['instruction_ids']) for edge in result['edges']], [2, 1])
        self.assertEqual(result['edges'][0]['instruction_ids'], [i.id for i in source.rungs[0].instructions])
        self.assertEqual(result['unlinked_instruction_ids'], [])
        self.assertEqual(result['cyclic_components'], [])
        self.assertEqual(result['main_designations'][0]['status'], 'absent')
        self.assertEqual({key: result[key] for key in ROUTINE_GRAPH_CONSTANTS}, ROUTINE_GRAPH_CONSTANTS)

    def test_program_local_identity_and_nonunique_calls_remain_unlinked(self) -> None:
        source = inventory(program('PRIVATE_P', routine('Caller',
            'JSR(Other)JSR(Missing)JSR()JSR(Duplicate);'), routine('Duplicate'), routine('DUPLICATE')),
            program('PRIVATE_Q', routine('Other', 'JSR(Other);')))
        targets = build_routine_targets(source)
        result = build_routine_graph(source, targets)
        self.assertEqual(result['unlinked_instruction_ids'],
                         [row['instruction_id'] for row in targets['occurrences'][:4]])
        self.assertEqual(len(result['edges']), 1)
        edge = result['edges'][0]
        self.assertEqual(edge['caller_routine_id'], edge['target_routine_id'])
        self.assertEqual(result['cyclic_components'], [[edge['caller_routine_id']]])

    def test_main_designations_all_six_statuses_without_program_type_gate(self) -> None:
        source = inventory(
            program('Absent', routine('Target')),
            program('Empty', routine('Target'), attributes='MainRoutineName=""'),
            program('Unsupported', routine('Target'), attributes='MainRoutineName=" Target "'),
            program('Missing', routine('Target'), attributes='MainRoutineName="Elsewhere"'),
            program('Ambiguous', routine('Target'), routine('TARGET'), attributes='MainRoutineName="target"'),
            program('Unique', routine('Target'), attributes='MainRoutineName="tArGeT"'))
        mains = graph(source)['main_designations']
        self.assertEqual([row['status'] for row in mains],
                         ['absent', 'empty', 'unsupported_name', 'missing_candidate',
                          'ambiguous_candidate', 'unique_candidate'])
        self.assertEqual([row['candidate_count'] for row in mains], [0, 0, 0, 0, 2, 1])
        self.assertIsNone(mains[0]['raw_name'])
        self.assertEqual(mains[1]['raw_name'], '')
        self.assertEqual(mains[2]['raw_name'], ' Target ')
        self.assertIsNotNone(mains[-1]['target_routine_id'])

    def test_main_raw_declarations_no_cross_program_or_unicode_fallback(self) -> None:
        source = inventory(program('PRIVATE_P', routine(' Target '), routine('K'),
                                   attributes='MainRoutineName="Target"'),
                           program('PRIVATE_Q', routine('Target'), attributes='MainRoutineName="\u212a"'),
                           program('PRIVATE_R', attributes='MainRoutineName="Target"'))
        self.assertEqual([row['status'] for row in graph(source)['main_designations']],
                         ['missing_candidate', 'unsupported_name', 'missing_candidate'])

    def test_missing_rll_content_differs_from_valid_empty_rll_body(self) -> None:
        source = inventory(program('PRIVATE_P', routine('Empty'), routine('Missing', content=''),
            routine('Mismatch', content='<STContent/>'), routine('Unexpected', content='<RLLContent/><Other/>')))
        nodes = graph(source)['nodes']
        self.assertEqual([node['body_status'] for node in nodes],
                         ['rll_structure_parsed'] + ['rll_structure_partial'] * 3)
        self.assertTrue(all(node['rung_counts'] == {'parsed': 0, 'failed': 0, 'preserved_unsupported': 0}
                            for node in nodes))

    def test_partial_routines_keep_parsed_edges_and_owned_rung_dispositions(self) -> None:
        source = inventory(program('PRIVATE_P', routine('Caller', 'JSR(Target);', 'BROKEN('),
                                   routine('Target'), routine('Outside', content=
                                       '<RLLContent/><Rung><Text>JSR(Target);</Text></Rung>')))
        result = graph(source)
        self.assertEqual(result['nodes'][0]['body_status'], 'rll_structure_partial')
        self.assertEqual(result['nodes'][0]['rung_counts'], {'parsed': 1, 'failed': 1, 'preserved_unsupported': 0})
        self.assertEqual(result['nodes'][2]['body_status'], 'rll_structure_partial')
        self.assertEqual(result['nodes'][2]['rung_counts']['preserved_unsupported'], 1)
        self.assertEqual(len(result['edges']), 1)
        self.assertEqual(result['edges'][0]['caller_routine_id'], result['nodes'][0]['routine_id'])

    def test_unmodeled_languages_and_protected_body_gaps_are_not_hidden(self) -> None:
        source = inventory(program('PRIVATE_P', routine('Caller',
            'JSR(FBDTarget)JSR(SFCTarget)JSR(STTarget)JSR(Protected);'),
            routine('FBDTarget', language='FBD', content='<FBDContent/>'),
            routine('SFCTarget', language='SFC', content='<SFCContent/>'),
            routine('STTarget', language='ST', content='<STContent/>'),
            routine('Missing', language=None, content=''), routine('Other', language='LD', content=''),
            routine('Protected', content='<EncodedData>PRIVATE_ENCODED</EncodedData>')))
        result = graph(source)
        self.assertEqual([node['language'] for node in result['nodes']], ['RLL', 'FBD', 'SFC', 'ST', 'missing', 'other', 'RLL'])
        self.assertEqual(Counter(node['body_status'] for node in result['nodes']),
                         {'rll_structure_parsed': 1, 'rll_structure_partial': 1, 'language_unmodeled': 5})
        self.assertEqual(len(result['edges']), 4)

    def test_aoi_and_mismatched_program_ownership_are_excluded_from_nodes(self) -> None:
        extra = ('<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="PRIVATE_AOI"><Routines>'
                 + routine('Caller', 'JSR(Target);') + routine('Target')
                 + '</Routines></AddOnInstructionDefinition></AddOnInstructionDefinitions>')
        source = inventory(program('PRIVATE_P', routine('Good')), extra=extra)
        result = graph(source)
        self.assertEqual(len(result['nodes']), 1)
        self.assertEqual(len(result['unlinked_instruction_ids']), 1)
        good = next(entity for entity in source.entities if entity.name == 'Good')
        source = replace(source, entities=[replace(entity, scope_id=None) if entity.id == good.id else entity
                                          for entity in source.entities])
        self.assertEqual(graph(source)['nodes'], [])

    def test_disconnected_cycles_self_edges_and_external_edges(self) -> None:
        source = inventory(program('PRIVATE_P', routine('A', 'JSR(B)JSR(C);'), routine('B', 'JSR(A);'),
            routine('C', 'JSR(C)JSR(Isolated);'), routine('D', 'JSR(E);'), routine('E', 'JSR(D);'), routine('Isolated')))
        result = graph(source)
        ids = {entity.name: entity.id for entity in source.entities if entity.kind == 'routine'}
        self.assertEqual(result['cyclic_components'], sorted([
            sorted([ids['A'], ids['B']]), [ids['C']], sorted([ids['D'], ids['E']])]))
        self.assertEqual(len(result['edges']), 7)

    def test_long_chain_and_cycle_use_iterative_traversal(self) -> None:
        length = 1200
        source = inventory(program('PRIVATE_P', *(routine(f'R{index}',
            f'JSR(R{index + 1});' if index + 1 < length else 'JSR(R0);') for index in range(length))))
        result = graph(source)
        self.assertEqual(len(result['nodes']), length)
        self.assertEqual(len(result['edges']), length)
        self.assertEqual(len(result['cyclic_components']), 1)
        self.assertEqual(len(result['cyclic_components'][0]), length)

    def test_graph_bounds_and_wrapper_messages_are_source_free(self) -> None:
        source = inventory(program('PRIVATE_P', routine('Caller', 'JSR(Target)JSR(Caller);'), routine('Target'),
                                   attributes='MainRoutineName="PRIVATE_MAIN_NAME"'))
        targets = build_routine_targets(source)
        for constant, limit in [('MAX_ROUTINE_GRAPH_NODES', 1), ('MAX_ROUTINE_GRAPH_EDGES', 1),
                                ('MAX_ROUTINE_GRAPH_OCCURRENCES', 1), ('MAX_ROUTINE_GRAPH_NAME_LENGTH', 4),
                                ('MAX_ROUTINE_GRAPH_EVIDENCE_CHARS', 1)]:
            with self.subTest(constant=constant), patch(f'plc_workbench.routine_graph.{constant}', limit):
                with self.assertRaisesRegex(RoutineGraphError, '^Routine graph analysis exceeds its evidence limits.$'):
                    build_routine_graph(source, targets)
                with self.assertRaisesRegex(ReferenceError, '^Routine graph analysis could not complete within its evidence contract.$'):
                    analyze_references(source)

    def test_exact_evidence_bound_counts_repeated_ids_main_names_and_components(self) -> None:
        source = inventory(program('PRIVATE_P', routine('Caller', 'JSR(Caller)JSR(Caller);'),
                                   attributes='MainRoutineName="Caller"'))
        result = graph(source)
        pending = [result]
        size = 0
        while pending:
            item = pending.pop()
            if type(item) is str:
                size += len(item)
            elif type(item) is dict:
                pending.extend(item.values())
            elif type(item) is list:
                pending.extend(item)
        with patch('plc_workbench.routine_graph.MAX_ROUTINE_GRAPH_EVIDENCE_CHARS', size):
            self.assertEqual(graph(source), result)
        with patch('plc_workbench.routine_graph.MAX_ROUTINE_GRAPH_EVIDENCE_CHARS', size - 1):
            with self.assertRaises(RoutineGraphError):
                graph(source)

    def test_graph_does_not_change_targets_catalog_or_operand_bindings(self) -> None:
        source = inventory(program('PRIVATE_P', routine('Caller', 'XIC(A)JSR(Target,0,A)SBR(A)RET(A);'), routine('Target')))
        before = deepcopy(source.to_dict())
        targets = build_routine_targets(source)
        result = analyze_references(source)
        self.assertEqual(source.to_dict(), before)
        self.assertEqual(result.routine_targets, targets)
        self.assertEqual(result.coverage['instructions_catalogued'], 1)
        self.assertEqual(result.operands[0]['status'], 'root_bound')
        self.assertTrue(all(row['status'] == 'unsupported_instruction' for row in result.operands[1:]))
        self.assertEqual((result.schema_version, result.analyzer_version), (6, 'source-references-9'))
        validate_references(source, result)

    def test_canonical_graph_tampering_rejected_before_private_write(self) -> None:
        original = snapshot(program('PRIVATE_P', routine('Caller', 'JSR(Target);'), routine('Target')))
        source = analyze_snapshot(original)
        result = analyze_references(source)
        forged_graphs = []
        for group, index, changes in [('nodes', 0, {'body_status': 'language_unmodeled'}),
            ('nodes', 0, {'program_id': 'PRIVATE_WRONG'}), ('edges', 0, {'instruction_ids': []}),
            ('edges', 0, {'target_routine_id': 'PRIVATE_WRONG'}),
            ('main_designations', 0, {'candidate_count': True})]:
            candidate = deepcopy(result.routine_graph)
            candidate[group][index].update(changes)
            forged_graphs.append(candidate)
        for changes in ({'cyclic_components': [['PRIVATE_WRONG']]}, {'unlinked_instruction_ids': ['PRIVATE_WRONG']},
                        {'execution': 'simulated'}, {'PRIVATE_KEY': 1}):
            candidate = deepcopy(result.routine_graph)
            candidate.update(changes)
            forged_graphs.append(candidate)
        for candidate in forged_graphs:
            forged = replace(result, routine_graph=candidate)
            with self.assertRaises(ReferenceError):
                validate_references(source, forged)
            with tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / 'never-created'
                with self.assertRaises(StorageError):
                    save_run(destination, original, source, references=forged)
                self.assertFalse(destination.exists())

    def test_private_json_and_text_keep_provenance_and_explicit_uncertainty(self) -> None:
        source = inventory(program('PRIVATE_P', routine('PRIVATE_CALLER', 'JSR(PRIVATE_TARGET)JSR(PRIVATE_CALLER);'),
                                   routine('PRIVATE_TARGET', language='SFC', content='<SFCContent/>'),
                                   attributes='MainRoutineName="PRIVATE_CALLER"'))
        result = analyze_references(source)
        self.assertEqual(json.loads(render_reference_json(result)), result.to_dict())
        text = render_reference_text(result, inventory=source)
        self.assertIn('Declared program-local JSR candidate graph:', text)
        self.assertIn('PRIVATE_CALLER', text)
        self.assertIn('PRIVATE_TARGET', text)
        self.assertIn('language_unmodeled', text)
        self.assertIn('not establish runtime entry or reachability', text)
        self.assertIn('Cycles describe candidate edges only', text)
        self.assertIn(result.routine_graph['edges'][0]['instruction_ids'][0], text)
        self.assertIn('Declared program-local JSR candidate graph:', render_reference_text(result))


if __name__ == '__main__':
    unittest.main()
