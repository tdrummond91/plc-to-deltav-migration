"""Public reference-report boundary tests using independently invented inputs."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest

from plc_workbench.reference_summary import (
    CONSTANTS, V8_CONSTANTS, V9_CONSTANTS, V10_CONSTANTS, V11_CONSTANTS, MAX_REPORT_BYTES,
    ReferenceSummaryError, build_reference_summary,
    render_reference_summary, validate_reference_summary,
)
from plc_workbench.references import analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes


def inventory(secret: str = 'PRIVATE_SENTINEL', *, reverse: bool = False):
    rungs = [
        f'XIC({secret}_INPUT)OTE({secret}_ALIAS);',
        f'MOV(7263.125,{secret}_OUTPUT);',
        f'CPT({secret}_OUTPUT,{secret}_INPUT+1);',
        f'{secret}_OPCODE({secret}_TARGET);',
    ]
    if reverse:
        rungs.reverse()
    rung_xml = ''.join(
        f'<Rung Number="{number + 900}" Type="N"><Comment>{secret}_COMMENT</Comment>'
        f'<Text>{rung}</Text></Rung>' for number, rung in enumerate(rungs)
    )
    xml = (
        f'<RSLogix5000Content Owner="{secret}_OWNER"><Controller Name="{secret}_CONTROLLER">'
        f'<Tags><Tag Name="{secret}_INPUT" TagType="Base" DataType="REAL"/>'
        f'<Tag Name="{secret}_OUTPUT" TagType="Base" DataType="REAL"/>'
        f'<Tag Name="{secret}_ALIAS" TagType="Alias" AliasFor="{secret}_INPUT"/>'
        f'<Tag Name="{secret}_BROKEN_ALIAS" TagType="Alias" AliasFor="{secret}_ABSENT"/></Tags>'
        f'<Programs><Program Name="{secret}_PROGRAM"><Routines>'
        f'<Routine Name="{secret}_ROUTINE" Type="RLL"><RLLContent>{rung_xml}</RLLContent>'
        '</Routine></Routines></Program></Programs></Controller></RSLogix5000Content>'
    ).encode()
    return analyze_snapshot(snapshot_from_bytes(xml))


def complete_inventory():
    return analyze_snapshot(snapshot_from_bytes(
        b'<RSLogix5000Content><Controller Name="C"><Tags>'
        b'<Tag Name="A" TagType="Base"/><Tag Name="B" TagType="Base"/></Tags>'
        b'<Programs><Program Name="P"><Routines><Routine Name="R" Type="RLL">'
        b'<RLLContent><Rung Number="0" Type="N"><Text>XIC(A)OTE(B);</Text></Rung>'
        b'</RLLContent></Routine></Routines></Program></Programs></Controller></RSLogix5000Content>'
    ))


def graph_inventory(*, add_aoi: bool = False):
    aoi = (
        b'<AddOnInstructionDefinitions><AddOnInstructionDefinition Name="PRIVATE_AOI">'
        b'<Routines><Routine Name="PRIVATE_AOI_RLL" Type="RLL"><RLLContent/></Routine>'
        b'<Routine Name="PRIVATE_AOI_ST" Type="ST"/>'
        b'<Routine Name="PRIVATE_AOI_ST_2" Type="ST"/>'
        b'<Routine Name="PRIVATE_AOI_ST_3" Type="ST"/></Routines>'
        b'</AddOnInstructionDefinition></AddOnInstructionDefinitions>'
    ) if add_aoi else b''
    return analyze_snapshot(snapshot_from_bytes(
        b'<RSLogix5000Content><Controller Name="PRIVATE_CONTROLLER">' + aoi + b'<Programs>'
        b'<Program Name="PRIVATE_PROGRAM" MainRoutineName="PRIVATE_A"><Routines>'
        b'<Routine Name="PRIVATE_A" Type="RLL"><RLLContent><Rung Number="0" Type="N">'
        b'<Text>JSR(PRIVATE_B)JSR(PRIVATE_B)JSR(PRIVATE_A)JSR(PRIVATE_C)JSR(PRIVATE_MISSING);'
        b'</Text></Rung></RLLContent></Routine>'
        b'<Routine Name="PRIVATE_B" Type="RLL"><RLLContent><Rung Number="0" Type="N">'
        b'<Text>JSR(PRIVATE_A);</Text></Rung></RLLContent></Routine>'
        b'<Routine Name="PRIVATE_C" Type="ST"/>'
        b'<Routine Name="PRIVATE_D" Type="RLL"/>'
        b'<Routine Name="PRIVATE_E" Type="RLL"><RLLContent/></Routine>'
        b'</Routines></Program><Program Name="PRIVATE_OTHER"/>'
        b'</Programs></Controller></RSLogix5000Content>'
    ))


class ReferenceSummaryTests(unittest.TestCase):
    def test_graph_validator_rejects_partition_coherent_but_impossible_graphs(self) -> None:
        source = graph_inventory()
        original = build_reference_summary(source, analyze_references(source))
        two_rll = analyze_snapshot(snapshot_from_bytes(
            b'<RSLogix5000Content><Controller Name="C"><Programs><Program Name="P"><Routines>'
            b'<Routine Name="A" Type="RLL"><RLLContent><Rung Number="0" Type="N">'
            b'<Text>JSR(A)JSR(B)JSR(B)JSR(B);</Text></Rung></RLLContent></Routine>'
            b'<Routine Name="B" Type="RLL"><RLLContent><Rung Number="0" Type="N">'
            b'<Text>JSR(A);</Text></Rung></RLLContent></Routine>'
            b'</Routines></Program></Programs></Controller></RSLogix5000Content>'
        ))
        two_report = build_reference_summary(two_rll, analyze_references(two_rll))
        three_programs = analyze_snapshot(snapshot_from_bytes(
            b'<RSLogix5000Content><Controller Name="C"><Programs><Program Name="P"><Routines>'
            b'<Routine Name="A" Type="RLL"><RLLContent><Rung Number="0" Type="N">'
            b'<Text>JSR(B)JSR(C)JSR(A);</Text></Rung></RLLContent></Routine>'
            b'<Routine Name="B" Type="RLL"><RLLContent><Rung Number="0" Type="N">'
            b'<Text>JSR(A);</Text></Rung></RLLContent></Routine>'
            b'<Routine Name="C" Type="ST"/></Routines></Program>'
            b'<Program Name="Q"/><Program Name="S"/>'
            b'</Programs></Controller></RSLogix5000Content>'
        ))
        three_report = build_reference_summary(three_programs, analyze_references(three_programs))
        with_aoi = graph_inventory(add_aoi=True)
        aoi_report = build_reference_summary(with_aoi, analyze_references(with_aoi))
        cases = (
            ('cycle edges exceed possible pairs', original,
             lambda g: g['cycles'].update(edges=4)),
            ('partial bodies exceed failed routine count', original,
             lambda g: g['nodes']['by_body_status'].update(
                 rll_structure_parsed=2, rll_structure_partial=2)),
            ('cyclic nodes exceed available RLL callers', three_report,
             lambda g: g['cycles'].update(nodes=3)),
            ('main candidates require disjoint program-owned declarations', three_report,
             lambda g: g['programs']['main_designations'].update(
                 absent=0, unique_candidate=1, ambiguous_candidate=2)),
            ('edges exceed grouped-pair capacity with exact self count', two_report,
             lambda g: g['edges'].update(total=4, extra_call_occurrences=1)),
            ('AOI language declarations cannot supply a program target', aoi_report,
             lambda g: (g['nodes']['by_language'].update(RLL=5, ST=0),
                        g['nodes']['by_body_status'].update(
                            rll_structure_parsed=4, language_unmodeled=0))),
            ('distinct targets exceed call-weighted graph-language capacity', aoi_report,
             lambda g: (g['nodes']['by_language'].update(RLL=1, ST=4),
                        g['nodes']['by_body_status'].update(
                            rll_structure_parsed=0, language_unmodeled=4),
                        g['cycles'].update(nodes=1, edges=1))),
        )
        for label, base, mutate in cases:
            report = deepcopy(base)
            mutate(report['routine_graph'])
            graph = report['routine_graph']
            # All mutations preserve the visible partitions and call accounting.
            self.assertEqual(sum(graph['nodes']['by_language'].values()), graph['nodes']['total'])
            self.assertEqual(sum(graph['nodes']['by_body_status'].values()), graph['nodes']['total'])
            self.assertEqual(sum(graph['programs']['main_designations'].values()), graph['programs']['total'])
            self.assertEqual(graph['calls']['linked'] - graph['edges']['total'],
                             graph['edges']['extra_call_occurrences'])
            with self.subTest(case=label), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)

    def test_graph_counts_keep_cycle_and_repeat_observations_without_topology(self) -> None:
        source = graph_inventory()
        report = build_reference_summary(source, analyze_references(source))
        graph = report['routine_graph']
        self.assertEqual(graph['nodes'], {
            'total': 5,
            'by_language': {'RLL': 4, 'FBD': 0, 'SFC': 0, 'ST': 1, 'missing': 0, 'other': 0},
            'by_body_status': {'rll_structure_parsed': 3, 'rll_structure_partial': 1,
                               'language_unmodeled': 1},
        })
        self.assertEqual(graph['programs']['total'], 2)
        self.assertEqual(graph['programs']['main_designations']['unique_candidate'], 1)
        self.assertEqual(graph['programs']['main_designations']['absent'], 1)
        self.assertEqual(graph['calls'], {'total': 6, 'linked': 5, 'unlinked': 1})
        self.assertEqual(graph['edges'], {'total': 4, 'repeated_pairs': 1,
                                        'extra_call_occurrences': 1, 'self_pairs': 1})
        self.assertEqual(graph['cycles'], {'components': 1, 'nodes': 2, 'edges': 3})
        self.assertEqual((graph['participating_nodes'], graph['isolated_nodes']), (3, 2))
        self.assertEqual(graph['execution'], 'not_analyzed')
        rendered = render_reference_summary(report)
        for forbidden in ('PRIVATE', source.snapshot['sha256'], 'routine_id', 'program_id',
                          'instruction_ids', 'raw_name', 'cyclic_components'):
            self.assertNotIn(forbidden, rendered)

    def test_graph_validator_rejects_private_fields_types_and_inconsistent_counts(self) -> None:
        source = graph_inventory()
        original = build_reference_summary(source, analyze_references(source))
        cases = [
            lambda g: g.update(execution='analyzed'),
            lambda g: g.update(program_id='PRIVATE'),
            lambda g: g['nodes']['by_language'].update(PRIVATE=0),
            lambda g: g['nodes'].update(total=6),
            lambda g: g['nodes']['by_language'].update(RLL=3, ST=2),
            lambda g: g['nodes']['by_body_status'].update(rll_structure_parsed=4, rll_structure_partial=0),
            lambda g: g['nodes']['by_body_status'].update(rll_structure_partial=2, language_unmodeled=0),
            lambda g: g['programs'].update(total=1),
            lambda g: g['programs']['main_designations'].update(absent=0),
            lambda g: g['calls'].update(total=7, unlinked=2),
            lambda g: g['calls'].update(linked=4, unlinked=2),
            lambda g: g['edges'].update(total=6),
            lambda g: g['edges'].update(extra_call_occurrences=2),
            lambda g: g['edges'].update(repeated_pairs=2),
            lambda g: g['edges'].update(repeated_pairs=0),
            lambda g: g['edges'].update(self_pairs=2),
            lambda g: g.update(participating_nodes=2, isolated_nodes=3),
            lambda g: g.update(isolated_nodes=3),
            lambda g: g['cycles'].update(nodes=4, edges=4),
            lambda g: g['cycles'].update(edges=1),
            lambda g: g['cycles'].update(components=0),
            lambda g: g['cycles'].update(components=2),
            lambda g: g['cycles'].update(components=0, nodes=0, edges=0),
        ]
        for bad_count in (True, -1, 1.5, 10**15):
            cases.extend((
                lambda g, value=bad_count: g['nodes'].update(total=value),
                lambda g, value=bad_count: g['nodes']['by_language'].update(RLL=value),
                lambda g, value=bad_count: g['programs']['main_designations'].update(absent=value),
                lambda g, value=bad_count: g['calls'].update(linked=value),
                lambda g, value=bad_count: g['edges'].update(repeated_pairs=value),
                lambda g, value=bad_count: g['cycles'].update(nodes=value),
                lambda g, value=bad_count: g.update(participating_nodes=value),
            ))
        for mutate in cases:
            report = deepcopy(original)
            mutate(report['routine_graph'])
            with self.subTest(mutate=mutate), self.assertRaises(ReferenceSummaryError) as caught:
                render_reference_summary(report)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_frozen_v8_keeps_exact_old_fields_and_analyzer_metadata(self) -> None:
        source = complete_inventory()
        current = build_reference_summary(source, analyze_references(source))
        historical = deepcopy(current)
        historical.update(V8_CONSTANTS)
        del historical['routine_instruction_shapes']
        del historical['routine_targets']
        del historical['routine_target_metadata']
        del historical['routine_graph']
        self.assertEqual(V8_CONSTANTS['analyzer_version'], 'source-references-7')
        self.assertEqual(CONSTANTS['analyzer_version'], 'source-references-9')
        self.assertEqual(set(historical), set(current) - {
            'routine_instruction_shapes', 'routine_targets', 'routine_target_metadata', 'routine_graph',
        })
        self.assertEqual(json.loads(render_reference_summary(historical)), historical)
        for base, changes in (
            (historical, {'schema_version': 9}),
            (historical, {'exporter_version': 'reference-summary-9'}),
            (current, {'schema_version': 8}),
            (current, {'exporter_version': 'reference-summary-8'}),
            (historical, {'analyzer_version': 'source-references-8'}),
            (current, {'analyzer_version': 'source-references-7'}),
        ):
            report = deepcopy(base)
            report.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)

    def test_frozen_v9_keeps_shapes_and_rejects_even_zero_target_counts(self) -> None:
        source = complete_inventory()
        current = build_reference_summary(source, analyze_references(source))
        historical = deepcopy(current)
        historical.update(V9_CONSTANTS)
        del historical['routine_targets']
        del historical['routine_target_metadata']
        del historical['routine_graph']
        self.assertEqual(V9_CONSTANTS['analyzer_version'], 'source-references-7')
        self.assertEqual(set(historical), set(current) - {
            'routine_targets', 'routine_target_metadata', 'routine_graph',
        })
        self.assertEqual(historical['routine_instruction_shapes'], current['routine_instruction_shapes'])
        self.assertEqual(json.loads(render_reference_summary(historical)), historical)
        historical['routine_targets'] = deepcopy(current['routine_targets'])
        with self.assertRaises(ReferenceSummaryError):
            validate_reference_summary(historical)

    def test_current_requires_target_counts_and_analyzer_metadata(self) -> None:
        source = complete_inventory()
        current = build_reference_summary(source, analyze_references(source))
        for mutate in (
            lambda report: report.pop('routine_targets'),
            lambda report: report.update(analyzer_version=V9_CONSTANTS['analyzer_version']),
            lambda report: report['routine_targets'].update(occurrences=[]),
        ):
            report = deepcopy(current)
            mutate(report)
            with self.subTest(mutate=mutate), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)

    def test_frozen_v10_preserves_candidates_and_rejects_new_metadata(self) -> None:
        source = complete_inventory()
        current = build_reference_summary(source, analyze_references(source))
        historical = deepcopy(current)
        historical.update(V10_CONSTANTS)
        del historical['routine_target_metadata']
        del historical['routine_graph']
        self.assertEqual(V10_CONSTANTS['analyzer_version'], 'source-references-8')
        self.assertEqual(set(historical), set(current) - {'routine_target_metadata', 'routine_graph'})
        self.assertEqual(historical['routine_targets'], current['routine_targets'])
        self.assertEqual(json.loads(render_reference_summary(historical)), historical)
        for base, changes in (
            (historical, {'routine_target_metadata': current['routine_target_metadata']}),
            (historical, {'exporter_version': CONSTANTS['exporter_version']}),
            (current, {'schema_version': 10}),
            (current, {'exporter_version': V10_CONSTANTS['exporter_version']}),
        ):
            report = deepcopy(base)
            report.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)

    def test_frozen_v11_preserves_metadata_and_excludes_graph_counts(self) -> None:
        source = complete_inventory()
        current = build_reference_summary(source, analyze_references(source))
        historical = deepcopy(current)
        historical.update(V11_CONSTANTS)
        del historical['routine_graph']
        self.assertEqual(V11_CONSTANTS['analyzer_version'], 'source-references-8')
        self.assertEqual(set(historical), set(current) - {'routine_graph'})
        self.assertEqual(historical['routine_target_metadata'], current['routine_target_metadata'])
        self.assertEqual(json.loads(render_reference_summary(historical)), historical)
        for base, mutate in (
            (historical, lambda r: r.update(routine_graph=current['routine_graph'])),
            (historical, lambda r: r.update(analyzer_version=CONSTANTS['analyzer_version'])),
            (current, lambda r: r.pop('routine_graph')),
            (current, lambda r: r.update(analyzer_version=V11_CONSTANTS['analyzer_version'])),
        ):
            report = deepcopy(base)
            mutate(report)
            with self.subTest(mutate=mutate), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)

    def test_target_metadata_counts_calls_and_rejects_private_labels_or_inconsistent_partitions(self) -> None:
        source = analyze_snapshot(snapshot_from_bytes(
            b'<RSLogix5000Content><Controller Name="PRIVATE_CONTROLLER"><Programs>'
            b'<Program Name="PRIVATE_PROGRAM"><Routines><Routine Name="PRIVATE_CALLER" Type="RLL">'
            b'<RLLContent><Rung Number="0" Type="N"><Text>'
            b'JSR(PRIVATE_TARGET)JSR(PRIVATE_TARGET)JSR(PRIVATE_MISSING);'
            b'</Text></Rung></RLLContent></Routine>'
            b'<Routine Name="PRIVATE_TARGET" Type="ST"/></Routines></Program>'
            b'</Programs></Controller></RSLogix5000Content>'
        ))
        original = build_reference_summary(source, analyze_references(source))
        metadata = original['routine_target_metadata']
        self.assertEqual(original['routine_targets']['distinct_targets'], 1)
        self.assertEqual(metadata['total'], 2)
        self.assertEqual(metadata['by_program_type']['absent'], 2)
        self.assertEqual(metadata['unclassified_context_by_program_type']['absent'], 2)
        self.assertEqual(metadata['by_target_language']['ST'], 2)
        rendered = render_reference_summary(original)
        for forbidden in ('PRIVATE', source.snapshot['sha256'], 'program_id', 'target_routine_id'):
            self.assertNotIn(forbidden, rendered)
        for mutate in (
            lambda m: m.update(total=1),
            lambda m: m['by_program_type'].update(absent=1),
            lambda m: m['by_target_language'].update(ST=1),
            lambda m: m['unclassified_context_by_program_type'].update(absent=1),
            lambda m: m['unclassified_context_by_program_type'].update(absent=0, explicit_normal=2),
            lambda m: m.update(program_id='PRIVATE_PROGRAM'),
            lambda m: m['by_program_type'].update(PRIVATE_TYPE=0),
            lambda m: m['by_target_language'].update(PRIVATE_TYPE=0),
            lambda m: m.update(program_type_semantics='analyzed'),
            lambda m: m['by_program_type'].update(absent=True),
        ):
            report = deepcopy(original)
            mutate(report['routine_target_metadata'])
            with self.subTest(mutate=mutate), self.assertRaises(ReferenceSummaryError) as caught:
                render_reference_summary(report)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_routine_target_counts_reject_invalid_types_partitions_bounds_and_private_labels(self) -> None:
        def candidate_report(*, single_routine: bool = False) -> dict:
            extra_routines = '' if single_routine else (
                '<Routine Name="PRIVATE_FAULT" Type="RLL"><RLLContent/></Routine>'
                '<Routine Name="PRIVATE_SPARE1" Type="RLL"><RLLContent/></Routine>'
                '<Routine Name="PRIVATE_SPARE2" Type="RLL"><RLLContent/></Routine>'
            )
            third_target = 'PRIVATE_CURRENT' if single_routine else 'PRIVATE_FAULT'
            xml = (
                '<RSLogix5000Content><Controller Name="PRIVATE_CONTROLLER"><Programs>'
                '<Program Name="PRIVATE_PROGRAM" Type="Normal" FaultRoutineName="PRIVATE_FAULT">'
                '<Routines><Routine Name="PRIVATE_CURRENT" Type="RLL"><RLLContent>'
                '<Rung Number="0" Type="N"><Text>'
                f'JSR(PRIVATE_CURRENT)JSR(PRIVATE_CURRENT)JSR({third_target})'
                'JSR(PRIVATE_MISSING)JSR();</Text></Rung></RLLContent></Routine>'
                f'{extra_routines}</Routines></Program></Programs></Controller></RSLogix5000Content>'
            ).encode('utf-8')
            source = analyze_snapshot(snapshot_from_bytes(xml))
            return build_reference_summary(source, analyze_references(source))

        original = candidate_report()
        single = candidate_report(single_routine=True)
        self.assertEqual(original['routine_targets']['total'], 5)
        self.assertEqual(original['routine_targets']['by_status']['unique_candidate'], 3)
        self.assertEqual(original['routine_targets']['unique_by_target_context']['fault_routine'], 1)
        self.assertEqual(original['routine_targets']['distinct_targets'], 2)
        self.assertEqual(single['source_summary']['counts']['routines'], 1)
        self.assertEqual(single['routine_targets']['distinct_targets'], 1)

        def no_unique_candidates(targets: dict) -> None:
            targets['by_status'].update(unique_candidate=0, missing_candidate=4)
            for key in targets['unique_by_target_context']:
                targets['unique_by_target_context'][key] = 0

        def ambiguous_in_one_routine(targets: dict) -> None:
            targets['by_status'].update(unique_candidate=2, ambiguous_candidate=1)
            targets['unique_by_target_context']['current_routine'] = 2

        cases = [
            ('total differs from JSR while status partition reconciles', original,
             lambda t: (t.update(total=6), t['by_status'].update(missing_candidate=2))),
            ('status partition differs from total', original,
             lambda t: t['by_status'].update(missing_candidate=2)),
            ('context partition differs from unique', original,
             lambda t: t['unique_by_target_context'].update(current_routine=3)),
            ('unique requires a distinct target', original, lambda t: t.update(distinct_targets=0)),
            ('no unique forbids distinct targets', original, no_unique_candidates),
            ('distinct exceeds unique but fits source routines', original,
             lambda t: t.update(distinct_targets=4)),
            ('distinct exceeds source routines but fits unique', single,
             lambda t: t.update(distinct_targets=2)),
            ('ambiguity requires two routine envelopes', single, ambiguous_in_one_routine),
            ('missing target field differs from zero field JSR', original,
             lambda t: t['by_status'].update(missing_target_field=0, missing_candidate=2)),
            ('private nested key', original, lambda t: t.update(raw_target_name='PRIVATE_TARGET')),
            ('private status label', original, lambda t: t['by_status'].update(PRIVATE_STATUS=0)),
            ('private context label', original,
             lambda t: t['unique_by_target_context'].update(PRIVATE_CONTEXT=0)),
            ('private analysis scope', original, lambda t: t.update(analysis_scope='PRIVATE_SCOPE')),
        ]
        for value in (True, -1, 0.5):
            cases.extend((
                (f'total count {value!r}', original, lambda t, v=value: t.update(total=v)),
                (f'distinct count {value!r}', original, lambda t, v=value: t.update(distinct_targets=v)),
                (f'status count {value!r}', original,
                 lambda t, v=value: t['by_status'].update(unique_candidate=v)),
                (f'context count {value!r}', original,
                 lambda t, v=value: t['unique_by_target_context'].update(current_routine=v)),
            ))
        for label, base, mutate in cases:
            report = deepcopy(base)
            mutate(report['routine_targets'])
            with self.subTest(case=label), self.assertRaises(ReferenceSummaryError) as caught:
                render_reference_summary(report)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_private_details_and_source_identity_do_not_cross_boundary(self) -> None:
        source = inventory()
        references = analyze_references(source)
        report = build_reference_summary(source, references)
        rendered = render_reference_summary(report)
        for forbidden in ('PRIVATE', 'SENTINEL', '7263.125', source.snapshot['sha256'],
                          source.snapshot['id'], 'raw_text', 'scope_id', 'alias_chain', 'target_id'):
            self.assertNotIn(forbidden, rendered)
        self.assertEqual(report['symbols']['total'], 4)
        self.assertEqual(report['symbols']['by_kind'], {
            'tag': 4, 'aoi_local_tag': 0, 'aoi_parameter': 0,
            'module_input_tag': 0, 'module_output_tag': 0, 'module_config_tag': 0,
        })
        self.assertEqual(report['aliases']['total'], 2)
        self.assertEqual(report['aliases']['by_status']['root_bound'], 1)
        self.assertEqual(report['aliases']['by_status']['unresolved'], 1)
        self.assertEqual(report['operands']['total'], 7)
        self.assertEqual(report['coverage']['rungs_analyzed'], 4)
        self.assertEqual(report['coverage']['instructions_total'], 5)
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['semantic_analysis'], 'not_implemented')
        self.assertEqual(report['effect_analysis'], 'not_implemented')
        self.assertEqual(report['member_validation'], 'not_implemented')
        self.assertLess(len(rendered.encode()), MAX_REPORT_BYTES)
        self.assertEqual(json.loads(rendered), report)

    def test_renaming_and_rung_reordering_preserve_public_report(self) -> None:
        first = inventory()
        second = inventory('DIFFERENT_SECRET', reverse=True)
        self.assertEqual(
            render_reference_summary(build_reference_summary(first, analyze_references(first))),
            render_reference_summary(build_reference_summary(second, analyze_references(second))),
        )

    def test_complete_applies_only_to_declared_root_binding_scope(self) -> None:
        source = complete_inventory()
        report = build_reference_summary(source, analyze_references(source))
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['analysis_scope'], 'scoped_root_bindings')
        self.assertEqual(report['operands']['by_status']['root_bound'], 2)
        self.assertEqual(report['coverage']['instructions_catalogued'], 2)
        self.assertEqual(report['member_validation'], 'not_implemented')

    def test_aoi_aliases_are_counted_beyond_ordinary_tag_aliases(self) -> None:
        source = analyze_snapshot(snapshot_from_bytes(
            b'<RSLogix5000Content><Controller Name="C"><AddOnInstructionDefinitions>'
            b'<AddOnInstructionDefinition Name="D"><Parameters>'
            b'<Parameter Name="Alias" AliasFor="Local"/></Parameters>'
            b'<LocalTags><LocalTag Name="Local"/></LocalTags>'
            b'</AddOnInstructionDefinition></AddOnInstructionDefinitions></Controller></RSLogix5000Content>'
        ))
        report = build_reference_summary(source, analyze_references(source))
        self.assertEqual(report['source_summary']['counts']['aliases'], 0)
        self.assertEqual(report['aliases']['total'], 1)
        self.assertEqual(report['symbols']['by_kind'], {
            'tag': 0, 'aoi_local_tag': 1, 'aoi_parameter': 1,
            'module_input_tag': 0, 'module_output_tag': 0, 'module_config_tag': 0,
        })
        validate_reference_summary(report)

    def test_code_revision_is_nested_once_and_validated(self) -> None:
        source = inventory()
        revision = {'commit': 'a' * 40, 'worktree': 'modified'}
        report = build_reference_summary(source, analyze_references(source), revision=revision)
        self.assertNotIn('tool_revision', report)
        self.assertEqual(report['source_summary']['tool_revision'], revision)
        with self.assertRaises(ReferenceSummaryError):
            build_reference_summary(source, analyze_references(source),
                                    revision={**revision, 'branch': 'PRIVATE_BRANCH'})

    def test_paired_snapshot_and_core_metadata_fail_closed(self) -> None:
        source = inventory()
        references = analyze_references(source)
        with self.assertRaises(ReferenceSummaryError):
            build_reference_summary(inventory('DIFFERENT_SECRET'), references)
        for field, value in (
            ('schema_version', True), ('schema_version', 2),
            ('analyzer_version', 'PRIVATE_VERSION'), ('analysis_scope', 'PRIVATE_SCOPE'),
            ('semantic_analysis', 'implemented'), ('effect_analysis', 'implemented'),
            ('member_validation', 'implemented'), ('status', 'PRIVATE_STATUS'),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ReferenceSummaryError):
                build_reference_summary(source, replace(references, **{field: value}))

    def test_private_record_vocabulary_cannot_create_public_labels(self) -> None:
        source = inventory()
        original = analyze_references(source)
        for mutate in (
            lambda p: p.update(PRIVATE_NEW_FIELD='PRIVATE_VALUE'),
            lambda p: p['symbols'][0].update(kind='PRIVATE_KIND'),
            lambda p: p['aliases'][0].update(status='PRIVATE_STATUS'),
            lambda p: p['operands'][0].update(status='PRIVATE_STATUS'),
            lambda p: p['coverage'].update(PRIVATE_KEY=1),
        ):
            references = deepcopy(original)
            mutate(vars(references))
            with self.assertRaises(ReferenceSummaryError) as caught:
                build_reference_summary(source, references)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_occurrence_accounting_rejects_missing_duplicated_or_crossed_records(self) -> None:
        source = inventory()
        original = analyze_references(source)
        for mutate in (
            lambda p: p['symbols'].pop(),
            lambda p: p['symbols'].__setitem__(1, deepcopy(p['symbols'][0])),
            lambda p: p['aliases'].pop(),
            lambda p: p['aliases'].__setitem__(1, deepcopy(p['aliases'][0])),
            lambda p: p['operands'].pop(),
            lambda p: p['operands'].__setitem__(1, deepcopy(p['operands'][0])),
            lambda p: p['operands'][0].update(raw_text='PRIVATE_REPLACED_OPERAND'),
            lambda p: p['operands'][0].update(argument_index=True),
            lambda p: p['operands'][0].update(rung_id='PRIVATE_OTHER_RUNG'),
            lambda p: p['coverage'].update(operands_total=0),
            lambda p: p['coverage'].update(source_status='PRIVATE_STATUS'),
        ):
            references = deepcopy(original)
            mutate(vars(references))
            with self.assertRaises(ReferenceSummaryError):
                build_reference_summary(source, references)

    def test_mutated_private_bindings_are_rejected_before_aggregation(self) -> None:
        source = inventory()
        original = analyze_references(source)
        # Each mutation leaves occurrence counts intact, so count reconciliation
        # alone cannot detect a false binding or a changed source alias target.
        mutations = (
            ('operands', 0, 'target_id', 'PRIVATE_DANGLING_TARGET'),
            ('operands', 0, 'target_id', original.symbols[1]['id']),
            ('operands', 0, 'symbol_id', None),
            ('operands', 0, 'alias_chain', ['PRIVATE_INVENTED_CHAIN']),
            ('operands', 0, 'status', 'unresolved'),
            ('aliases', 0, 'raw_target', 'PRIVATE_CHANGED_ALIAS_TARGET'),
            ('aliases', 0, 'target_id', 'PRIVATE_DANGLING_TARGET'),
            ('aliases', 0, 'symbol_id', None),
            ('aliases', 0, 'alias_chain', []),
            ('aliases', 0, 'status', 'unresolved'),
        )
        for group, index, field, value in mutations:
            records = deepcopy(getattr(original, group))
            self.assertNotEqual(records[index][field], value)
            records[index][field] = value
            mutated = replace(original, **{group: records})
            with self.subTest(group=group, field=field), self.assertRaises(ReferenceSummaryError) as caught:
                build_reference_summary(source, mutated)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_validator_rejects_unknown_fields_and_private_labels_at_every_layer(self) -> None:
        source = inventory()
        original = build_reference_summary(source, analyze_references(source))
        for mutate in (
            lambda r: r.update(source_path='PRIVATE_SOURCE'),
            lambda r: r['symbols'].update(names=['PRIVATE_NAME']),
            lambda r: r['symbols']['by_kind'].update(PRIVATE_KIND=1),
            lambda r: r['aliases']['by_status'].update(PRIVATE_ALIAS_STATUS=1),
            lambda r: r['operands']['by_status'].update(PRIVATE_OPERAND_STATUS=1),
            lambda r: r['coverage'].update(PRIVATE_COVERAGE=1),
            lambda r: r['source_summary']['counts'].update(PRIVATE_COUNT=1),
            lambda r: r['source_summary'].update(schema_version=1),
            lambda r: r.update(schema_version=True),
            lambda r: r.update(sharing_status='PRIVATE_POLICY'),
        ):
            report = deepcopy(original)
            mutate(report)
            with self.assertRaises(ReferenceSummaryError) as caught:
                render_reference_summary(report)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_counts_are_bounded_integers_and_reconcile_with_source(self) -> None:
        source = inventory()
        original = build_reference_summary(source, analyze_references(source))
        for value in (True, -1, 1.5, float('nan'), 10**15, 'PRIVATE_COUNT'):
            report = deepcopy(original)
            report['coverage']['instructions_catalogued'] = value
            with self.subTest(value=value), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)
        for mutate in (
            lambda r: r['symbols'].update(total=500),
            lambda r: r['symbols'].update(unnamed=500),
            lambda r: r['symbols'].update(ambiguous_groups=500),
            lambda r: r['aliases'].update(total=0),
            lambda r: r['operands'].update(total=0),
            lambda r: r['operands']['by_status'].update(root_bound=500),
            lambda r: r['coverage'].update(rungs_total=0),
            lambda r: r['coverage'].update(rungs_analyzed=0),
            lambda r: r['coverage'].update(instructions_total=0),
            lambda r: r['coverage'].update(instructions_catalogued=500),
        ):
            report = deepcopy(original)
            mutate(report)
            with self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)

    def test_complete_cannot_hide_source_or_reference_gaps(self) -> None:
        source = complete_inventory()
        original = build_reference_summary(source, analyze_references(source))

        def make_unresolved(report: dict) -> None:
            report['operands']['by_status'].update(root_bound=1, unresolved=1)
            report['operands']['by_reason']['unresolved']['root_not_declared'] = 1

        for mutate in (
            lambda r: r['source_summary'].update(status='partial'),
            lambda r: r['coverage'].update(instructions_catalogued=1),
            lambda r: r['symbols'].update(unnamed=1),
            lambda r: r['symbols'].update(ambiguous_groups=1),
            make_unresolved,
        ):
            report = deepcopy(original)
            mutate(report)
            with self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)
            report['status'] = 'partial'
            validate_reference_summary(report)
        source = inventory()
        report = build_reference_summary(source, analyze_references(source))
        report['status'] = 'complete'
        with self.assertRaises(ReferenceSummaryError):
            validate_reference_summary(report)


if __name__ == '__main__':
    unittest.main()
