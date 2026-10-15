"""Extended access overlays remain distinct from frozen source references."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from plc_workbench import work_check
from plc_workbench.access import analyze_access, render_access_json
from plc_workbench.access_summary import validate_access_summary
from plc_workbench.reference_reporting import render_reference_json
from plc_workbench.review import ReviewError, build_review_data, validate_review_data
from plc_workbench.storage import save_run

from test_access_workflow import ROOT, ladder
from test_calculation_workflow import arguments, captured, options
from test_unmatched_sample_report import report


EXTENDED = ('CTU(A,?,?)CTD(A,100,0)MSG(A)GSV(Task,,ScanTime,A)'
            'SSV(Task,PRIVATE_TASK,Priority,A)SFR(PRIVATE_SFC,A)SFR(PRIVATE_SFC,0);')


class ExtendedAccessWorkflowTests(unittest.TestCase):
    def test_review_and_manifest_replay_nested_versions_without_changing_other_artifacts(self) -> None:
        parts = captured(ladder(EXTENDED))
        legacy_access = analyze_access(parts[1], parts[2], schema_version=2)
        legacy_parts = (*parts[:4], legacy_access, *parts[5:])
        reference_bytes = render_reference_json(parts[2]).encode('utf-8')
        with tempfile.TemporaryDirectory() as directory:
            prior_files = None
            for evidence in (legacy_parts, parts):
                access = evidence[4]
                payload = build_review_data(*evidence[:4], **options(evidence))
                self.assertEqual(payload['schema_version'], 6)
                self.assertEqual(payload['access'], access.to_dict())
                validate_review_data(*evidence[:4], payload, **options(evidence))
                saved = save_run(Path(directory), *evidence[:2], **arguments(evidence))
                files = {path.name: path.read_bytes() for path in saved.iterdir()}
                manifest = json.loads(files['manifest.json'])
                self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (9, 13))
                self.assertEqual(manifest['access_schema_version'], access.schema_version)
                self.assertEqual(manifest['access_analyzer_version'], access.analyzer_version)
                self.assertEqual(files['access.json'], render_access_json(access).encode('utf-8'))
                self.assertEqual(files['references.json'], reference_bytes)
                for name, details in manifest['artifacts'].items():
                    self.assertEqual(details, {'sha256': hashlib.sha256(files[name]).hexdigest(),
                                               'size_bytes': len(files[name])})
                    if prior_files is not None and name not in {'access.json', 'review.html'}:
                        self.assertEqual(files[name], prior_files[name])
                prior_files = files
                wrong = parts if evidence is legacy_parts else legacy_parts
                with self.assertRaises(ReviewError):
                    validate_review_data(*evidence[:4], payload, **options(wrong))
        self.assertEqual(legacy_access.coverage['instructions_by_status']['unsupported_instruction'], 7)
        self.assertEqual(parts[4].coverage['instructions_by_status']['classified'], 7)

    def test_current_work_overlays_extend_bindings_and_keep_reference6_unchanged(self) -> None:
        data = ladder(EXTENDED)
        current = report(data)
        old = report(data, schema_version=19)
        self.assertEqual((current['schema_version'], current['workflow_version']), (20, 'work-check-20'))
        access = current['analysis']['access_summary']
        coverage = access['coverage']
        self.assertEqual((access['schema_version'], access['analyzer_version']), (3, 'instruction-access-3'))
        self.assertEqual(coverage['extended_instructions'], {'counter': 2, 'message': 1,
            'system_get': 1, 'system_set': 1, 'sfc_reset_step': 1, 'sfc_reset_initial': 1})
        self.assertEqual(coverage['counter_pseudo_operands_by_kind'], {'placeholder': 2, 'integer_literal': 2})
        self.assertEqual(coverage['extended_bound_operands'], 6)
        self.assertEqual(coverage['linked_operands'], 6)
        self.assertEqual(coverage['operands_by_role'],
                         {'read': 1, 'write': 2, 'read_write': 3, 'non_data': 13, 'unknown': 0})
        for key, value in old['analysis'].items():
            if key != 'access_summary':
                self.assertEqual(current['analysis'][key], value)
        self.assertEqual(current['analysis']['reference_summary']['operands']['by_status']['root_bound'], 0)
        self.assertEqual((access['status'], current['status']), ('complete', 'partial'))
        for item in (current, old):
            work_check.validate_work_check_report(item)
        rendered = work_check.render_work_check_report(current)
        for private in ('PRIVATE_', 'ScanTime', 'Priority', 'raw_text', 'alias_chain', 'binding_origin', 'target_id'):
            self.assertNotIn(private, rendered)

    def test_work19_and_work20_require_exact_nested_access_versions(self) -> None:
        data = ladder(EXTENDED)
        old, current = report(data, schema_version=19), report(data)
        for original, donor in ((old, current), (current, old)):
            candidate = deepcopy(original)
            candidate['analysis']['access_summary'] = donor['analysis']['access_summary']
            validate_access_summary(candidate['analysis']['access_summary'])
            with self.subTest(version=candidate['schema_version']), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)

    def test_current_contract_keeps_all_returned_reports_and_fixed_size_budget(self) -> None:
        paths = list((ROOT / 'public/inspection').glob('work-check-*.json'))
        self.assertGreaterEqual(len(paths), 26)
        for path in paths:
            before = path.read_bytes()
            payload = json.loads(before)
            self.assertEqual(json.loads(work_check.render_work_check_report(payload)), payload)
            self.assertEqual(path.read_bytes(), before)
        # Add zero-valued version3 fields to the actual largest returned
        # envelope. This establishes size headroom without inventing coverage.
        returned = json.loads((ROOT / 'public/inspection/work-check-20261015T150939Z-d534a725.json').read_bytes())
        access = returned['analysis']['access_summary']
        access.update(schema_version=3, analyzer_version='instruction-access-3', exporter_version='access-summary-3')
        empty = report(ladder('XIC(A);'))['analysis']['access_summary']['coverage']
        for key in ('extended_instructions', 'counter_pseudo_operands_by_kind',
                    'counter_invalid_forms', 'extended_bound_operands'):
            access['coverage'][key] = empty[key]
        returned.update(schema_version=20, workflow_version='work-check-20')
        rendered = work_check.render_work_check_report(returned)
        self.assertLess(len(rendered.encode('utf-8')), 32 * 1024)
        self.assertEqual(work_check.MAX_REPORT_BYTES, 32 * 1024)

    def test_invalid_counter_forms_remain_unknown_without_consuming_timer_capacity(self) -> None:
        payload = report(ladder('CTU(A,A,0)CTD(A,1.5,0)TON(A,A,0);'))
        coverage = payload['analysis']['access_summary']['coverage']
        self.assertEqual(coverage['counter_invalid_forms'], 2)
        self.assertEqual(coverage['instructions_by_status']['unsupported_operand_form'], 3)
        self.assertEqual(coverage['operands_by_role']['unknown'], 9)
        self.assertEqual(coverage['extended_bound_operands'], 0)
        self.assertEqual(coverage['counter_pseudo_operands_by_kind'], {'placeholder': 0, 'integer_literal': 0})
        work_check.validate_work_check_report(payload)

    def test_source_family_and_reference_populations_reject_feasible_transplants(self) -> None:
        cases = (
            ('TON(A,?,?);', 'CTU(A,?,?);'),
            ('ONS(A);', 'MSG(A);'),
            ('GSV(Task,,ScanTime,A);', 'SSV(Task,,Priority,A);'),
            ('CTU(A,A,0);', 'TON(A,A,0);'),
            ('PID(A,A,A);', 'CTU(A,A,0);'),
        )
        for target, donor in cases:
            candidate = report(ladder(target))
            candidate['analysis']['access_summary'] = report(ladder(donor))['analysis']['access_summary']
            validate_access_summary(candidate['analysis']['access_summary'])
            with self.subTest(target=target, donor=donor), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)

    def test_one_withheld_opcode_cannot_supply_both_timer_and_system_family(self) -> None:
        candidate = report(ladder('ton(A,?,?)GSV(Task,,ScanTime,A);'))
        donor = report(ladder('ton(A,?,?)SSV(Task,,Priority,A);'))
        candidate['analysis']['access_summary'] = donor['analysis']['access_summary']
        validate_access_summary(candidate['analysis']['access_summary'])
        self.assertEqual(candidate['analysis']['reference_summary']['source_summary']['instructions']['counts'],
                         {'GSV': 1, 'withheld': 1})
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)

    def test_case_variants_and_optional_system_instance_are_valid_in_actual_envelope(self) -> None:
        payload = report(ladder('ctu(A,?,?)CtD(A,5,0)msg(A)gSv(Task,,ScanTime,A)'
                                'ssv(Task,,Priority,A)sfr(PRIVATE_SFC,A)sFr(PRIVATE_SFC,0);'))
        work_check.validate_work_check_report(payload)
        self.assertEqual(payload['analysis']['reference_summary']['source_summary']['instructions']['counts'],
                         {'withheld': 7})
        self.assertEqual(payload['analysis']['access_summary']['coverage']['instructions_by_status']['classified'], 7)


if __name__ == '__main__':
    unittest.main()
