"""Unary-math workflow contracts using invented inputs and public history."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from plc_workbench import work_check

from test_unmatched_sample_report import SOURCE, report


ROOT = Path(__file__).resolve().parents[2]
RETURNED = ROOT / 'public/inspection/work-check-20261014T191741Z-2009d02d.json'
MATH_SOURCE = SOURCE.replace(
    b'XIC(MysteryRack:7:I.Data[2].3)OTE(A);', b'ABS(A,A)LN(2,A)SQR(A,A);',
)


class MathReportTests(unittest.TestCase):
    def test_previous_flag_report_remains_readable_with_its_exact_contract(self) -> None:
        before = RETURNED.read_bytes()
        payload = json.loads(before)
        self.assertEqual((payload['schema_version'],
                          payload['analysis']['reference_summary']['schema_version']), (4, 6))
        self.assertEqual(payload['analysis']['reference_summary']['operands']['by_status']['system_flag'], 1)
        self.assertIsNone(payload['diagnostic_sample'])
        self.assertEqual(json.loads(work_check.render_work_check_report(payload)), payload)
        self.assertEqual(RETURNED.read_bytes(), before)

    def test_current_math_report_uses_new_pair_without_changing_source_contract(self) -> None:
        payload = report(MATH_SOURCE)
        self.assertEqual((payload['schema_version'], payload['workflow_version']), (17, 'work-check-17'))
        nested = payload['analysis']['reference_summary']
        self.assertEqual((nested['schema_version'], nested['analyzer_version']), (12, 'source-references-9'))
        self.assertEqual(nested['source_summary']['schema_version'], 4)
        self.assertEqual(nested['coverage']['instructions_catalogued'], 3)
        self.assertEqual(nested['operands']['by_status']['root_bound'], 5)
        self.assertEqual(nested['operands']['by_status']['literal'], 1)
        self.assertEqual(nested['operands']['by_status']['unsupported_instruction'], 0)
        self.assertEqual(payload['status'], 'passed')
        self.assertIsNone(payload['diagnostic_sample'])
        work_check.validate_work_check_report(payload)
        mismatched = deepcopy(payload)
        mismatched.update(schema_version=4, workflow_version='work-check-4')
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(mismatched)
        old = json.loads(RETURNED.read_bytes())
        old.update(schema_version=5, workflow_version='work-check-5')
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(old)

    def test_saved_math_run_preserves_source_and_records_current_analyzer(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            path = root / 'invented.L5X'
            path.write_bytes(MATH_SOURCE)
            result = work_check._analyze(root, path, root, {'commit': 'a' * 40, 'worktree': 'clean'})
            self.assertTrue(result['private_run_saved'])
            self.assertIsNone(result['diagnostic_sample'])
            saved, = (root / 'confidential/workspaces/work-check').glob('run-*')
            references = json.loads((saved / 'references.json').read_text(encoding='utf-8'))
            self.assertEqual((references['schema_version'], references['analyzer_version']),
                             (6, 'source-references-9'))
            self.assertEqual([item['raw_text'] for item in references['operands']], ['A', 'A', '2', 'A', 'A', 'A'])
            self.assertEqual((saved / 'snapshot.L5X').read_bytes(), MATH_SOURCE)
            self.assertEqual(path.read_bytes(), MATH_SOURCE)

    def test_previous_flag_envelope_still_rejects_known_samples_despite_other_gaps(self) -> None:
        cases = (
            (SOURCE.replace(b'XIC(', b'XIC(S:FS)XIC('),
             {'kind': 'direct_unmatched_colon_operand', 'opcode': 'XIC', 'argument_index': 0, 'raw_text': 'S:FS'}),
            (SOURCE.replace(b'XIC(MysteryRack:7:I.Data[2].3)OTE(A);', b'TON(A,?,Preset?)OTE(A);'),
             {'kind': 'direct_malformed_operand', 'opcode': 'TON', 'argument_index': 1, 'raw_text': '?'}),
        )
        for source, known_sample in cases:
            payload = report(source)
            payload.update(schema_version=4, workflow_version='work-check-4')
            del payload['analysis']['sfc_structure_summary']
            del payload['analysis']['access_summary']
            del payload['analysis']['tag_data_summary']
            del payload['analysis']['pid_summary']
            del payload['analysis']['pid_member_summary']
            del payload['analysis']['reference_summary']['routine_instruction_shapes']
            del payload['analysis']['reference_summary']['routine_targets']
            del payload['analysis']['reference_summary']['routine_target_metadata']
            del payload['analysis']['reference_summary']['routine_graph']
            payload['analysis']['reference_summary'].update(
                schema_version=6, exporter_version='reference-summary-6', analyzer_version='source-references-5',
            )
            self.assertIsNotNone(payload['diagnostic_sample'])
            work_check.validate_work_check_report(payload)
            payload['diagnostic_sample'] = known_sample
            with self.subTest(sample=known_sample), self.assertRaises(ValueError):
                work_check.validate_work_check_report(payload)


if __name__ == '__main__':
    unittest.main()
