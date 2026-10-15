"""Observation-only routine field tests: invented inputs and public report bytes."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import tempfile
import unittest

from plc_workbench import work_check
from plc_workbench.reference_reporting import render_reference_json, render_reference_text
from plc_workbench.reference_summary import (
    build_reference_summary, render_reference_summary,
)
from plc_workbench.references import analyze_references
from plc_workbench.routine_shapes import (
    MAX_COUNT, RoutineShapeError, build_routine_instruction_shapes,
    validate_routine_instruction_shapes,
)
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.storage import save_run
from plc_workbench.summary import build_summary

from test_unmatched_sample_report import report


ROOT = Path(__file__).resolve().parents[2]
PREVIOUS_REPORT = ROOT / 'public/inspection/work-check-20261014T205025Z-cc9c4184.json'


def source_bytes(*rungs: str, name: str = 'PRIVATE_SENTINEL') -> bytes:
    rung_xml = ''.join(
        f'<Rung Number="{number}" Type="N"><Text>{escape(text)}</Text></Rung>'
        for number, text in enumerate(rungs)
    )
    return (
        f'<RSLogix5000Content><Controller Name="{name}"><Tags><Tag Name="A" TagType="Base"/>'
        f'</Tags><Programs><Program Name="{name}_PROGRAM"><Routines>'
        f'<Routine Name="{name}_ROUTINE" Type="RLL"><RLLContent>{rung_xml}</RLLContent>'
        '</Routine></Routines></Program></Programs></Controller></RSLogix5000Content>'
    ).encode()


def inventory(*rungs: str):
    return analyze_snapshot(snapshot_from_bytes(source_bytes(*rungs)))


def context(source) -> dict:
    references = analyze_references(source)
    return {
        'source_summary': build_summary(source),
        'instructions_catalogued': references.coverage['instructions_catalogued'],
        'operands_total': len(references.operands),
        'unsupported_instruction_slots': sum(
            item['status'] == 'unsupported_instruction' for item in references.operands
        ),
    }


class RoutineShapeTests(unittest.TestCase):
    def test_jsr_exact_second_zero_and_arity_bins_do_not_normalize_numbers(self) -> None:
        source = inventory(
            'JSR()JSR(PRIVATE_TARGET)JSR(PRIVATE_TARGET,0)JSR(PRIVATE_TARGET,\n 0 \n)'
            'JSR(PRIVATE_TARGET,00)JSR(PRIVATE_TARGET,+0)JSR(PRIVATE_TARGET,"0")'
            "JSR(PRIVATE_TARGET,'0')JSR(PRIVATE_TARGET,)JSR(PRIVATE_TARGET,0.0)"
            'JSR(PRIVATE_TARGET,０)JSR(PRIVATE_TARGET,0,PRIVATE_DATA)'
            'JSR(PRIVATE_TARGET,00,PRIVATE_DATA,PRIVATE_DATA);',
        )
        shapes = build_routine_instruction_shapes(source)
        self.assertEqual(shapes['by_opcode']['JSR'], {
            'total': 13, 'argument_slots': 26, 'noncanonical_spelling': 0,
            'by_arity': {
                'zero_fields': 1, 'one_field': 1, 'two_fields_second_zero': 2,
                'two_fields_second_other': 7, 'three_or_more_second_zero': 1,
                'three_or_more_second_other': 1,
            },
        })
        validate_routine_instruction_shapes(shapes, **context(source))

    def test_sbr_ret_field_counts_include_empty_slots_without_roles(self) -> None:
        source = inventory('SBR()SBR(A)SBR(A,)SBR(A,0,B,C)RET()RET(A)RET(,)RET(A,B,C);')
        shapes = build_routine_instruction_shapes(source)
        for opcode, slots in (('SBR', 7), ('RET', 6)):
            self.assertEqual(shapes['by_opcode'][opcode], {
                'total': 4, 'argument_slots': slots, 'noncanonical_spelling': 0,
                'by_arity': {'zero_fields': 1, 'one_field': 1, 'two_fields': 1, 'three_or_more': 1},
            })
        validate_routine_instruction_shapes(shapes, **context(source))
        self.assertEqual(shapes['parameter_roles'], 'not_analyzed')
        self.assertEqual(shapes['target_resolution'], 'not_analyzed')

    def test_mixed_case_counts_share_withheld_budget_and_failed_rungs_are_excluded(self) -> None:
        data = source_bytes('JSR(A,0)jsr(A,0)JsR(A)sbr()Ret(A)PRIVATE_OTHER(A);',
                            'JSR(PRIVATE_FAILED,0)BROKEN(')
        data = data.replace(b'</Routines>', b'<Routine Name="PRIVATE_ST" Type="ST">'
                            b'<STContent>JSR(PRIVATE_ST_TARGET,0);</STContent></Routine></Routines>')
        source = analyze_snapshot(snapshot_from_bytes(data))
        shapes = build_routine_instruction_shapes(source)
        self.assertEqual(set(shapes['by_opcode']), {'JSR', 'SBR', 'RET'})
        self.assertEqual(shapes['by_opcode']['JSR']['total'], 3)
        self.assertEqual(shapes['by_opcode']['JSR']['noncanonical_spelling'], 2)
        self.assertEqual(shapes['by_opcode']['SBR']['noncanonical_spelling'], 1)
        self.assertEqual(shapes['by_opcode']['RET']['noncanonical_spelling'], 1)
        source_counts = build_summary(source)['instructions']['counts']
        self.assertEqual(source_counts, {'JSR': 1, 'withheld': 5})
        validate_routine_instruction_shapes(shapes, **context(source))

    def test_observations_leave_inventory_bindings_catalog_and_private_schema_unchanged(self) -> None:
        source = inventory('XIC(A)JSR(PRIVATE_TARGET,0,A)SBR(A)RET(A);')
        references = analyze_references(source)
        before = deepcopy(source.to_dict())
        private_before = references.to_dict()
        shapes = build_routine_instruction_shapes(source)
        self.assertEqual(source.to_dict(), before)
        self.assertEqual(analyze_references(source).to_dict(), private_before)
        self.assertEqual(references.coverage['instructions_catalogued'], 1)
        self.assertEqual((references.schema_version, references.analyzer_version),
                         (6, 'source-references-9'))
        self.assertNotIn('routine_instruction_shapes', private_before)
        self.assertEqual(json.loads(render_reference_json(references)), private_before)
        other = analyze_snapshot(snapshot_from_bytes(source_bytes(
            'RET(DIFFERENT_DATA)SBR(DIFFERENT_DATA)JSR(DIFFERENT_TARGET,0,DIFFERENT_DATA)XIC(A);',
            name='OTHER_SENTINEL',
        )))
        self.assertEqual(shapes, build_routine_instruction_shapes(other))
        rendered = json.dumps(shapes)
        for forbidden in ('PRIVATE', 'OTHER_SENTINEL', 'DIFFERENT', source.snapshot['sha256'],
                          'raw_text', 'scope_id', 'instruction_id', 'target_id'):
            self.assertNotIn(forbidden, rendered)

    def test_strict_fixed_keys_constants_and_count_types_fail_source_free(self) -> None:
        source = inventory('JSR(A,0)SBR(A)RET(A);')
        original = build_routine_instruction_shapes(source)
        mutations = [
            lambda p: p.update(PRIVATE_KEY='PRIVATE_VALUE'),
            lambda p: p.update(parameter_roles='PRIVATE_VALUE'),
            lambda p: p.update(target_resolution=True),
            lambda p: p['by_opcode'].update(PRIVATE_OPCODE=p['by_opcode']['JSR']),
            lambda p: p['by_opcode']['JSR'].update(PRIVATE_FIELD=1),
            lambda p: p['by_opcode']['JSR']['by_arity'].update(PRIVATE_BIN=0),
            lambda p: p['by_opcode']['JSR'].update(by_arity=[]),
        ]
        for count in (True, -1, 1.0, 'PRIVATE_VALUE', MAX_COUNT + 1):
            mutations.append(lambda p, count=count: p['by_opcode']['JSR'].update(total=count))
        for mutate in mutations:
            value = deepcopy(original)
            mutate(value)
            with self.assertRaises(RoutineShapeError) as caught:
                validate_routine_instruction_shapes(value, **context(source))
            self.assertEqual(str(caught.exception), 'Routine instruction shape validation failed.')

    def test_partitions_minimum_slots_and_exact_small_arity_slots_are_required(self) -> None:
        source = inventory('JSR(A,0)JSR(A,0,B,C)SBR(A)RET(,);')
        original = build_routine_instruction_shapes(source)
        for mutate in (
            lambda p: p['by_opcode']['JSR']['by_arity'].update(zero_fields=1),
            lambda p: p['by_opcode']['JSR'].update(argument_slots=4),
            lambda p: p['by_opcode']['SBR'].update(argument_slots=2),
            lambda p: p['by_opcode']['RET'].update(argument_slots=1),
            lambda p: p['by_opcode']['JSR'].update(noncanonical_spelling=3),
        ):
            value = deepcopy(original)
            mutate(value)
            with self.assertRaises(RoutineShapeError):
                validate_routine_instruction_shapes(value, **context(source))
        # Large arity is a lower bound, not a fabricated exact field count.
        validate_routine_instruction_shapes(original, **context(source))

    def test_named_opcode_reconciliation_and_shared_case_budget_are_required(self) -> None:
        source = inventory('JSR(A,0)jsr(A,0)sbr(A)ret(A)PRIVATE_OTHER(A);')
        shapes = build_routine_instruction_shapes(source)
        for mutate in (
            lambda c: c['source_summary']['instructions']['counts'].update(JSR=0),
            lambda c: c['source_summary']['instructions']['counts'].update(withheld=2),
            lambda c: c['source_summary']['instructions']['counts'].update(withheld=True),
        ):
            supplied = context(source)
            mutate(supplied)
            with self.assertRaises(RoutineShapeError):
                validate_routine_instruction_shapes(shapes, **supplied)
        validate_routine_instruction_shapes(shapes, **context(source))

    def test_total_and_operand_slots_stay_within_uncatalogued_and_unsupported_bounds(self) -> None:
        source = inventory('JSR(A,0)RET(A)XIC(A);')
        shapes = build_routine_instruction_shapes(source)
        for key, count in (('instructions_catalogued', 2), ('instructions_catalogued', 4),
                           ('operands_total', 2), ('unsupported_instruction_slots', 2),
                           ('unsupported_instruction_slots', True)):
            supplied = context(source)
            supplied[key] = count
            with self.subTest(key=key, count=count), self.assertRaises(RoutineShapeError):
                validate_routine_instruction_shapes(shapes, **supplied)
        validate_routine_instruction_shapes(shapes, **context(source))

    def test_current_public_pair_and_previous_report_bytes_are_compatible(self) -> None:
        source = inventory('JSR(PRIVATE_TARGET,0)SBR(A)RET(A);')
        nested = build_reference_summary(source, analyze_references(source))
        self.assertEqual((nested['schema_version'], nested['exporter_version'], nested['analyzer_version']),
                         (12, 'reference-summary-12', 'source-references-9'))
        self.assertEqual(nested['routine_instruction_shapes'], build_routine_instruction_shapes(source))
        payload = report(source_bytes('JSR(PRIVATE_TARGET,0)SBR(A)RET(A);'))
        self.assertEqual((payload['schema_version'], payload['workflow_version']), (20, 'work-check-20'))
        self.assertEqual(json.loads(work_check.render_work_check_report(payload)), payload)
        rendered = render_reference_summary(nested)
        self.assertNotIn('PRIVATE', rendered)
        before = PREVIOUS_REPORT.read_bytes()
        self.assertEqual(sha256(before).hexdigest(),
                         '56afcf9e549402c4ad871746e0d3ca07bfc4dfe5f6e9a5d4637f2aa52ff0d7a9')
        previous = json.loads(before)
        self.assertEqual((previous['schema_version'],
                          previous['analysis']['reference_summary']['schema_version']), (6, 8))
        self.assertNotIn('routine_instruction_shapes', previous['analysis']['reference_summary'])
        self.assertEqual(json.loads(work_check.render_work_check_report(previous)), previous)
        self.assertEqual(PREVIOUS_REPORT.read_bytes(), before)

    def test_private_text_addition_reports_fixed_counts_without_field_values(self) -> None:
        snapshot = snapshot_from_bytes(source_bytes('JSR(PRIVATE_TARGET,0)jsr(PRIVATE_TARGET,00)SBR()RET();'))
        source = analyze_snapshot(snapshot)
        references = analyze_references(source)
        rendered = render_reference_text(references, inventory=source)
        section = rendered.split('Parsed RLL routine instruction field shapes', 1)[1].split('Declarations:', 1)[0]
        self.assertIn('Parameter roles are not analyzed; first-field JSR candidates are listed separately.', section)
        self.assertIn('JSR: total=2 argument_slots=4 noncanonical_spelling=1', section)
        self.assertIn('two_fields_second_zero: 1', section)
        self.assertIn('two_fields_second_other: 1', section)
        self.assertIn('SBR: total=1 argument_slots=0', section)
        self.assertIn('RET: total=1 argument_slots=0', section)
        self.assertNotIn('PRIVATE', section)
        self.assertNotIn('routine_instruction_shapes', render_reference_json(references))
        with tempfile.TemporaryDirectory() as folder:
            saved = save_run(Path(folder), snapshot, source, references=references)
            self.assertEqual((saved / 'references.txt').read_text(encoding='utf-8'), rendered)
            self.assertEqual(json.loads((saved / 'references.json').read_bytes()), references.to_dict())


if __name__ == '__main__':
    unittest.main()
