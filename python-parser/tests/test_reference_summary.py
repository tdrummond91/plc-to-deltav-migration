"""Public reference-report boundary tests using independently invented inputs."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import unittest

from plc_workbench.reference_summary import (
    MAX_REPORT_BYTES, ReferenceSummaryError, build_reference_summary,
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


class ReferenceSummaryTests(unittest.TestCase):
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
