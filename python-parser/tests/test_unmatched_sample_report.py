"""Closed unmatched-address feedback from invented inputs; no subprocess IO."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench.diagnostic_sample import build_diagnostic_sample
from plc_workbench.reference_summary import build_reference_summary, render_reference_summary
from plc_workbench.references import analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from plc_workbench import work_check


ROOT = Path(__file__).resolve().parents[2]
REVISION = {'commit': 'a' * 40, 'worktree': 'clean'}
SOURCE = b'''<RSLogix5000Content><Controller Name="PRIVATE_CONTROLLER">
<Tags><Tag Name="A" TagType="Base"/></Tags><Programs><Program Name="PRIVATE_PROGRAM">
<Routines><Routine Name="PRIVATE_ROUTINE" Type="RLL"><RLLContent>
<Rung Number="907" Type="N"><Comment>PRIVATE_COMMENT</Comment>
<Text>XIC(MysteryRack:7:I.Data[2].3)OTE(A);</Text></Rung>
</RLLContent></Routine></Routines></Program></Programs></Controller></RSLogix5000Content>'''


def report(data: bytes = SOURCE) -> dict:
    from plc_workbench.access import analyze_access
    from plc_workbench.access_summary import build_access_summary
    from plc_workbench.sfc_structure import analyze_sfc_structure
    from plc_workbench.sfc_summary import build_sfc_summary
    snapshot = snapshot_from_bytes(data)
    inventory = analyze_snapshot(snapshot)
    references = analyze_references(inventory)
    nested = build_reference_summary(inventory, references, revision=REVISION)
    sfc = build_sfc_summary(snapshot, inventory,
        analyze_sfc_structure(snapshot, inventory), revision=REVISION)
    access = build_access_summary(inventory, references, analyze_access(inventory, references), revision=REVISION)
    status = 'partial' if 'partial' in (nested['status'], sfc['status'], access['status']) else 'complete'
    result = {
        'schema_version': 1, 'status': 'passed',
        'counts': {'tests_run': 1, 'failures': 0, 'errors': 0, 'skipped': 0,
                   'expected_failures': 0, 'unexpected_successes': 0},
        'failed_test_ids': [], 'failure_ids_omitted': 0,
    }
    return {
        'schema_version': 14, 'report_kind': 'l5x_work_machine_check', 'workflow_version': 'work-check-14',
        'run_id': '20261014T180000Z-1234abcd', 'tool_revision': deepcopy(REVISION),
        'tests': {'application': deepcopy(result), 'helpers': deepcopy(result)},
        'analysis': {'status': status, 'failure_code': None, 'private_run_saved': True,
                     'reference_summary': nested,
                     'sfc_structure_summary': sfc, 'access_summary': access},
        'status': 'passed' if status == 'complete' else 'partial',
        'diagnostic_sample': build_diagnostic_sample(inventory, references),
    }


class UnmatchedSampleReportTests(unittest.TestCase):
    def test_new_report_keeps_only_one_operand_and_closed_metadata(self) -> None:
        payload = report()
        rendered = work_check.render_work_check_report(payload)
        self.assertEqual(json.loads(rendered), payload)
        self.assertEqual(payload['diagnostic_sample'], {
            'kind': 'direct_unmatched_colon_operand', 'opcode': 'XIC', 'argument_index': 0,
            'raw_text': 'MysteryRack:7:I.Data[2].3',
        })
        for private in ('PRIVATE_', 'rung_id', 'source_id', 'candidate_id', 'terminal_root'):
            self.assertNotIn(private, rendered)
        nested = payload['analysis']['reference_summary']
        self.assertEqual((nested['schema_version'], nested['source_summary']['schema_version']), (12, 4))
        self.assertNotIn('MysteryRack', render_reference_summary(nested))

    def test_schema2_rejects_new_kind_but_preserves_null_and_malformed(self) -> None:
        payload = report()
        payload.update(schema_version=2, workflow_version='work-check-2')
        del payload['analysis']['sfc_structure_summary']
        del payload['analysis']['access_summary']
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)
        payload['diagnostic_sample'] = None
        work_check.validate_work_check_report(payload)
        malformed = report(SOURCE.replace(b'MysteryRack:7:I.Data[2].3', b'Unknown?'))
        malformed.update(schema_version=2, workflow_version='work-check-2')
        del malformed['analysis']['sfc_structure_summary']
        del malformed['analysis']['access_summary']
        self.assertEqual(malformed['diagnostic_sample']['kind'], 'direct_malformed_operand')
        work_check.validate_work_check_report(malformed)

    def test_current_envelope_requires_current_rack_reference_contract(self) -> None:
        payload = report()
        nested = payload['analysis']['reference_summary']
        del nested['routine_instruction_shapes']
        del nested['routine_targets']
        del nested['routine_target_metadata']
        del nested['routine_graph']
        self.assertEqual(nested['operands']['by_status'].pop('system_flag'), 0)
        nested.update(schema_version=4, exporter_version='reference-summary-4', analyzer_version='source-references-3')
        del nested['rack_candidates']
        source = nested['source_summary']
        source.update(schema_version=3, exporter_version='aggregate-summary-3', parser_version='source-inventory-2')
        for key in ('module_rack_connections', 'module_rack_input_aliases', 'module_rack_output_aliases'):
            del source['counts'][key]
        for sample in (payload['diagnostic_sample'], None):
            payload['diagnostic_sample'] = sample
            with self.subTest(sample=sample), self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)

    def test_positive_direct_unmatched_population_is_required(self) -> None:
        sample = report()['diagnostic_sample']
        data = (ROOT / 'public/fixtures/synthetic/rack_io_gap_demo.L5X').read_bytes()
        payload = report(data)
        self.assertIsNone(payload['diagnostic_sample'])
        payload['diagnostic_sample'] = sample
        self.assertEqual(payload['analysis']['reference_summary']['rack_candidates']['matches']
                         ['direct_operands']['by_status']['no_candidate_match'], 0)
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)

    def test_sample_requires_observed_opcode_and_partial_analysis(self) -> None:
        payload = report()
        payload['diagnostic_sample']['opcode'] = 'RTO'
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(payload)
        complete = report(SOURCE.replace(b'MysteryRack:7:I.Data[2].3', b'A'))
        complete['diagnostic_sample'] = report()['diagnostic_sample']
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(complete)

    def test_failure_and_not_run_require_null(self) -> None:
        for state in ('failed', 'not_run'):
            payload = report()
            payload['analysis'] = {'status': state, 'failure_code': 'read_error' if state == 'failed' else None,
                                   'private_run_saved': False, 'reference_summary': None,
                                   'sfc_structure_summary': None, 'access_summary': None}
            payload['status'] = 'failed'
            if state == 'not_run':
                result = payload['tests']['application']
                result.update(status='failed', failed_test_ids=['test_synthetic.Example.test_failure'])
                result['counts']['failures'] = 1
            with self.subTest(state=state), self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)
            payload['diagnostic_sample'] = None
            work_check.validate_work_check_report(payload)

    def test_version_hybrids_extra_fields_and_wrong_kind_syntax_are_rejected(self) -> None:
        for mutate in (
            lambda p: p.update(schema_version=True),
            lambda p: p.update(workflow_version='work-check-2'),
            lambda p: p.pop('diagnostic_sample'),
            lambda p: p['diagnostic_sample'].update(rung='PRIVATE'),
            lambda p: p['diagnostic_sample'].update(raw_text='Missing?'),
            lambda p: p['diagnostic_sample'].update(kind='direct_malformed_operand'),
        ):
            payload = report()
            mutate(payload)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                work_check.render_work_check_report(payload)

    def test_publisher_enforces_new_kind_contract_and_no_overwrite(self) -> None:
        payload = report()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / 'feedback.json'
            publish_summary(output, json.dumps(payload), input_path=root / 'invented.L5X')
            before = output.read_bytes()
            self.assertEqual(json.loads(before), payload)
            with self.assertRaises(SummaryOutputError):
                publish_summary(output, json.dumps(payload), input_path=root / 'invented.L5X')
            payload.update(schema_version=2, workflow_version='work-check-2')
            del payload['analysis']['sfc_structure_summary']
            del payload['analysis']['access_summary']
            rejected = root / 'rejected.json'
            with self.assertRaises(SummaryOutputError):
                publish_summary(rejected, json.dumps(payload), input_path=root / 'invented.L5X')
            self.assertFalse(rejected.exists())
            self.assertEqual(output.read_bytes(), before)

    def test_real_analysis_captures_once_and_saves_same_private_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(SOURCE)
            with patch.object(work_check, 'capture_snapshot', wraps=work_check.capture_snapshot) as capture:
                result = work_check._analyze(root, source, root, REVISION)
            capture.assert_called_once_with(source)
            self.assertEqual(result['status'], 'partial')
            self.assertTrue(result['private_run_saved'])
            self.assertEqual(result['diagnostic_sample'], report()['diagnostic_sample'])
            saved, = (root / 'confidential/workspaces/work-check').glob('run-*')
            self.assertEqual((saved / 'snapshot.L5X').read_bytes(), SOURCE)
            self.assertEqual(source.read_bytes(), SOURCE)
            references = json.loads((saved / 'references.json').read_text(encoding='utf-8'))
            self.assertEqual(references['operands'][0]['raw_text'], result['diagnostic_sample']['raw_text'])

    def test_all_returned_reports_remain_valid_and_unchanged(self) -> None:
        paths = list((ROOT / 'public/inspection').glob('work-check-*.json'))
        self.assertGreaterEqual(len(paths), 8)
        for path in paths:
            before = path.read_bytes()
            with self.subTest(path=path.name):
                work_check.validate_work_check_report(json.loads(before))
                self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
