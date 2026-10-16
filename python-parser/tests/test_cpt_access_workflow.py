"""CPT access uses authenticated calculation leaves without changing references."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import work_check
from plc_workbench.access import analyze_access, render_access_json
from plc_workbench.access_summary import validate_access_summary
from plc_workbench.calculation_summary import validate_calculation_summary
from plc_workbench.review import ReviewError, build_review_data, validate_review_data
from plc_workbench.storage import StorageError, save_run

from test_access_workflow import ROOT, ladder
from test_calculation_workflow import arguments, captured as old_captured, options
from test_review_workflow import invoke
from test_unmatched_sample_report import REVISION, report as old_report


SOURCE = ladder('CPT(A,A+A)CPT(A,937291)CPT(A,PRIVATE_FUNCTION(A));')


def captured(data: bytes = SOURCE):
    parts = old_captured(data)
    access = analyze_access(parts[1], parts[2], schema_version=4,
                            snapshot=parts[0], calculations=parts[-1])
    return (*parts[:4], access, *parts[5:])


def report(data: bytes = SOURCE):
    return old_report(data, schema_version=21)


class CptAccessWorkflowTests(unittest.TestCase):
    def test_review6_manifest9_replays_access_versions_and_preserves_other_artifacts(self) -> None:
        current = captured()
        with tempfile.TemporaryDirectory() as directory:
            original = None
            for version in (2, 3, 4):
                access = current[4] if version == 4 else analyze_access(*current[1:3], schema_version=version)
                parts = (*current[:4], access, *current[5:])
                payload = build_review_data(*parts[:4], **options(parts))
                validate_review_data(*parts[:4], payload, **options(parts))
                self.assertEqual(payload['schema_version'], 6)
                self.assertEqual(payload['access'], access.to_dict())
                saved = save_run(Path(directory), *parts[:2], **arguments(parts))
                files = {path.name: path.read_bytes() for path in saved.iterdir()}
                manifest = json.loads(files['manifest.json'])
                self.assertEqual((manifest['schema_version'], len(manifest['artifacts'])), (9, 13))
                self.assertEqual(manifest['access_schema_version'], version)
                self.assertEqual(manifest['access_analyzer_version'], f'instruction-access-{version}')
                self.assertEqual(files['access.json'], render_access_json(access).encode('utf-8'))
                for name, details in manifest['artifacts'].items():
                    self.assertEqual(details, {'sha256': hashlib.sha256(files[name]).hexdigest(),
                                               'size_bytes': len(files[name])})
                    if original is not None and name not in {'access.json', 'review.html'}:
                        self.assertEqual(files[name], original[name])
                original = files

    def test_access4_requires_current_authenticated_calculations_before_publication(self) -> None:
        parts = captured()
        legacy = old_captured(SOURCE, schema_version=1)
        foreign = old_captured(SOURCE.replace(b'A+A', b'A-A'))[-1]
        forged = deepcopy(parts[-1])
        forged.coverage['nodes_total'] += 1
        for calculation in (None, legacy[-1], foreign, forged):
            kwargs = dict(options(parts), calculations=calculation)
            with self.subTest(calculation=calculation is None), self.assertRaises(ReviewError):
                build_review_data(*parts[:4], **kwargs)
            with tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory) / 'not-created'
                with self.assertRaises(StorageError):
                    save_run(workspace, *parts[:2], **dict(arguments(parts), calculations=calculation))
                self.assertFalse(workspace.exists())
        # Access3 continues to accept calculation1 and the old optional path.
        payload = build_review_data(*legacy[:4], **options(legacy))
        self.assertEqual((payload['access']['schema_version'], payload['calculations']['schema_version']), (3, 1))
        no_calculation = build_review_data(*legacy[:4], **dict(options(legacy), calculations=None))
        self.assertEqual(no_calculation['schema_version'], 5)

    def test_cli_and_runner_save_access4_using_the_captured_calculations(self) -> None:
        parts = captured()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(SOURCE)
            code, output, error = invoke(['review', str(source), '--workspace', str(root / 'runs')])
            self.assertEqual((code, error), (3, ''))
            saved, = (root / 'runs').iterdir()
            self.assertIn(str(saved / 'review.html'), output)
            self.assertEqual(json.loads((saved / 'access.json').read_bytes()), parts[4].to_dict())
            with patch.object(work_check, 'save_run', return_value=root / 'saved') as save:
                outcome = work_check._analyze(root, source, root, REVISION)
            self.assertIsNone(outcome['failure_code'])
            self.assertEqual(save.call_args.kwargs['access'].schema_version, 4)
            self.assertEqual(save.call_args.kwargs['calculations'].to_dict(), parts[-1].to_dict())
            current = report()
            outcome.pop('diagnostic_sample')
            outcome.pop('targeted_samples', None)
            self.assertIsNotNone(outcome.pop('custom_instruction_summary'))
            self.assertIsNotNone(outcome.pop('indexed_access_summary'))
            self.assertIsNotNone(outcome.pop('sfr_summary'))
            self.assertIsNotNone(outcome.pop('aoi_body_summary'))
            self.assertIsNotNone(outcome.pop('pid_connection_summary'))
            self.assertIsNotNone(outcome.pop('rung_analysis_summary'))
            self.assertIsNotNone(outcome.pop('relationship_summary'))
            self.assertIsNotNone(outcome.pop('condition_summary'))
            self.assertIsNotNone(outcome.pop('binding_context_summary'))
            self.assertEqual(outcome, current['analysis'])

    def test_work21_has_separate_leaf_reads_and_exact_calculation_populations(self) -> None:
        payload = report()
        work_check.validate_work_check_report(payload)
        self.assertEqual((payload['schema_version'], payload['workflow_version']), (21, 'work-check-21'))
        access = payload['analysis']['access_summary']
        coverage = access['coverage']
        self.assertEqual((access['schema_version'], access['analyzer_version']), (4, 'instruction-access-4'))
        self.assertEqual(coverage['calculation_instructions'], 3)
        self.assertEqual(coverage['expression_containers_by_status'], {'parsed': 2, 'unsupported': 1})
        self.assertEqual(coverage['expression_uses_total'], 2)
        self.assertEqual(coverage['expression_uses_by_binding']['root_bound'], 2)
        self.assertEqual(coverage['expression_indexed_roots'], 1)
        self.assertEqual(coverage['operands_total'], 6)
        self.assertEqual(coverage['operands_by_role']['expression_read'], 3)
        self.assertEqual(coverage['bound_by_role']['expression_read'], 0)
        self.assertEqual(coverage['linked_operands'], 3)
        self.assertEqual(coverage['instructions_by_status']['classified'], 3)
        self.assertEqual(coverage['operands_by_role']['write'], 3)
        self.assertEqual(access['status'], 'partial')
        prior = old_report(SOURCE)
        for name, value in prior['analysis'].items():
            if name != 'access_summary':
                self.assertEqual(payload['analysis'][name], value)
        rendered = work_check.render_work_check_report(payload)
        for private in ('PRIVATE_', '937291', 'A+A', 'node_id', 'instruction_id', 'target_id'):
            self.assertNotIn(private, rendered)

    def test_work20_and_work21_reject_exchanged_nested_versions(self) -> None:
        previous, current = old_report(SOURCE), report()
        for original, donor in ((previous, current), (current, previous)):
            candidate = deepcopy(original)
            candidate['analysis']['access_summary'] = donor['analysis']['access_summary']
            validate_access_summary(candidate['analysis']['access_summary'])
            with self.subTest(version=candidate['schema_version']), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        legacy = old_report(SOURCE, schema_version=18)
        candidate = deepcopy(current)
        candidate['analysis']['calculation_summary'] = legacy['analysis']['calculation_summary']
        validate_calculation_summary(candidate['analysis']['calculation_summary'])
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)

    def test_matching_source_totals_do_not_allow_mismatched_calculation_leaves(self) -> None:
        pairs = (
            ('CPT(A,A+A);', 'CPT(A,A);'),
            ('CPT(A,A);', 'CPT(A,PRIVATE_MISSING);'),
            ('CPT(A,A);', 'CPT(A,PRIVATE_FUNCTION(A));'),
            ('CPT(A,937291);', 'MOV(A,A);'),
        )
        for target, donor in pairs:
            candidate = report(ladder(target))
            candidate['analysis']['access_summary'] = report(ladder(donor))['analysis']['access_summary']
            validate_access_summary(candidate['analysis']['access_summary'])
            with self.subTest(target=target, donor=donor), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)

    def test_one_withheld_opcode_cannot_supply_timer_and_cpt_populations(self) -> None:
        candidate = report(ladder('ton(A,?,?)MOV(A,A);'))
        donor = report(ladder('ton(A,?,?)cpt(A,A);'))
        for name in ('access_summary', 'calculation_summary'):
            candidate['analysis'][name] = donor['analysis'][name]
        validate_access_summary(candidate['analysis']['access_summary'])
        validate_calculation_summary(candidate['analysis']['calculation_summary'])
        self.assertEqual(candidate['analysis']['reference_summary']['source_summary']['instructions']['counts'],
                         {'MOV': 1, 'withheld': 1})
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)
        work_check.validate_work_check_report(donor)

    def test_pid_and_cpt_share_withheld_capacity_including_invalid_pid_signatures(self) -> None:
        for instruction in ('pid(A,A,A,A,A,A,A)', 'pid(A,A)', 'pid(A,,A,A,A,A,A)'):
            payload = report(ladder(instruction + 'cpt(A,A);'))
            work_check.validate_work_check_report(payload)
            counts = payload['analysis']['reference_summary']['source_summary']['instructions']['counts']
            self.assertEqual(counts, {'withheld': 2})
            self.assertEqual(payload['analysis']['pid_summary']['coverage']['occurrences_total'], 1)
            counts.update(withheld=1, MOV=1)
            # Both instruction populations independently fit the one withheld
            # occurrence, but they cannot consume that same occurrence twice.
            with self.subTest(instruction=instruction), self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)

    def test_cpt_bound_destination_cannot_also_cover_extended_bound_write(self) -> None:
        for extended in ('GSV(X,,Y,A)', 'SFR(PRIVATE_ROUTINE,A)'):
            payload = report(ladder('CPT(A,A)' + extended + 'XIC(Missing);'))
            work_check.validate_work_check_report(payload)
            coverage = payload['analysis']['access_summary']['coverage']
            self.assertEqual(coverage['bound_by_role']['write'], 2)
            self.assertEqual(coverage['extended_bound_operands'], 1)
            coverage['bound_by_role']['write'] -= 1
            coverage['bound_by_role']['read'] += 1
            validate_access_summary(payload['analysis']['access_summary'])
            with self.subTest(extended=extended), self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)

    def test_shared_bound_roles_allow_mixed_and_partially_unbound_extended_slots(self) -> None:
        cases = (
            ('CPT(A,A)GSV(X,,Y,A)SSV(X,,Y,A)MSG(A)CTU(A,?,?)SFR(PRIVATE_ROUTINE,A);', 5),
            ('CPT(A,A)GSV(X,,Y,Missing)SSV(X,,Y,A)MSG(A);', 2),
            ('CPT(Missing,A)GSV(X,,Y,A)SSV(X,,Y,Missing)MSG(A);', 2),
            ('CPT(A,A)GSV(X,,Y,A)SSV(X,,Y,A)MSG(Missing)ONS(A);', 2),
            ('CPT(Missing,A)GSV(X,,Y,Missing)OTE(A);', 0),
            ('CPT(Missing,A)SFR(PRIVATE_ROUTINE,Missing)OTE(A);', 0),
        )
        for text, count in cases:
            payload = report(ladder(text))
            with self.subTest(text=text):
                work_check.validate_work_check_report(payload)
                self.assertEqual(payload['analysis']['access_summary']['coverage']['extended_bound_operands'], count)

    def test_bound_writes_need_either_bound_cpt_extended_or_legacy_slots(self) -> None:
        for extended in ('GSV(X,,Y,Missing)', 'SFR(PRIVATE_ROUTINE,Missing)', ''):
            payload = report(ladder('CPT(Missing,A)' + extended + 'XIC(A);'))
            work_check.validate_work_check_report(payload)
            coverage = payload['analysis']['access_summary']['coverage']
            self.assertEqual(coverage['extended_bound_operands'], 0)
            self.assertEqual(payload['analysis']['calculation_summary']['coverage']['destination_root_bound'], 0)
            coverage['bound_by_role']['write'] += 1
            coverage['bound_by_role']['read'] -= 1
            validate_access_summary(payload['analysis']['access_summary'])
            with self.subTest(extended=extended), self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)

    def test_invalid_signatures_keep_all_slots_unknown_and_do_not_create_leaf_reads(self) -> None:
        payload = report(ladder('CPT(A)CPT(A,,A)CPT(,A)CPT(A,);'))
        work_check.validate_work_check_report(payload)
        coverage = payload['analysis']['access_summary']['coverage']
        self.assertEqual(coverage['calculation_instructions'], 0)
        self.assertEqual(coverage['operands_by_role']['unknown'], 8)
        self.assertEqual(coverage['expression_uses_total'], 0)
        self.assertEqual(coverage['expression_containers_by_status'], {'parsed': 0, 'unsupported': 0})

    def test_more_leaves_than_legacy_slots_are_valid_and_have_bounded_roots(self) -> None:
        payload = report(ladder('CPT(A,' + '+'.join(['A'] * 12) + ');'))
        work_check.validate_work_check_report(payload)
        coverage = payload['analysis']['access_summary']['coverage']
        self.assertEqual((coverage['operands_total'], coverage['expression_uses_total']), (2, 12))
        self.assertEqual(coverage['expression_indexed_roots'], 1)
        candidate = deepcopy(payload)
        candidate['analysis']['access_summary']['coverage']['expression_indexed_roots'] = 2
        validate_access_summary(candidate['analysis']['access_summary'])
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)

    def test_all_historical_reports_remain_valid_without_rewriting(self) -> None:
        paths = list((ROOT / 'public/inspection').glob('work-check-*.json'))
        self.assertGreaterEqual(len(paths), 27)
        for path in paths:
            before = path.read_bytes()
            payload = json.loads(before)
            self.assertEqual(json.loads(work_check.render_work_check_report(payload)), payload)
            self.assertEqual(path.read_bytes(), before)
        self.assertLess(len(work_check.render_work_check_report(report()).encode('utf-8')), 32 * 1024)
        self.assertEqual(work_check.MAX_REPORT_BYTES, 32 * 1024)

    def test_latest_return_has_room_for_new_fixed_cpt_fields(self) -> None:
        # This is an envelope capacity projection from returned aggregates,
        # not a claim about unshared private source or distinct expression roots.
        path = ROOT / 'public/inspection/work-check-20261015T155437Z-fb15196b.json'
        payload = json.loads(path.read_bytes())
        access = payload['analysis']['access_summary']
        c = access['coverage']
        calculation = payload['analysis']['calculation_summary']['coverage']
        recognized = calculation['occurrences_by_signature']['recognized']
        bound = calculation['destination_root_bound']
        payload.update(schema_version=21, workflow_version='work-check-21')
        access.update(schema_version=4, analyzer_version='instruction-access-4', exporter_version='access-summary-4')
        c['instructions_by_status']['classified'] += recognized
        c['instructions_by_status']['unsupported_instruction'] -= recognized
        c['operands_by_role']['unknown'] -= 2 * recognized
        c['operands_by_role']['write'] += recognized
        c['operands_by_role']['expression_read'] = recognized
        c['bound_by_role']['unknown'] -= bound
        c['bound_by_role']['write'] += bound
        c['bound_by_role']['expression_read'] = 0
        c.update(calculation_instructions=recognized,
                 expression_containers_by_status={key: calculation['expressions_by_status'][key]
                                                  for key in ('parsed', 'unsupported')},
                 expression_uses_total=calculation['reference_occurrences'],
                 expression_uses_by_binding=calculation['reference_by_binding'],
                 expression_indexed_roots=calculation['reference_by_binding']['root_bound'],
                 expressions_with_binding_gaps=calculation['expressions_with_binding_gaps'])
        rendered = work_check.render_work_check_report(payload)
        self.assertLess(len(rendered.encode('utf-8')), 32 * 1024)


if __name__ == '__main__':
    unittest.main()
