"""First-scan report compatibility using invented XML and public historical evidence."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from plc_workbench import work_check
from plc_workbench.summary_output import SummaryOutputError, publish_summary

from test_unmatched_sample_report import SOURCE, report


ROOT = Path(__file__).resolve().parents[2]
RETURNED = ROOT / 'public/inspection/work-check-20261014T183844Z-26f5b84a.json'


class SystemFlagReportTests(unittest.TestCase):
    def test_returned_first_scan_sample_preserves_original_contract(self) -> None:
        before = RETURNED.read_bytes()
        payload = json.loads(before)
        self.assertEqual((payload['schema_version'], payload['analysis']['reference_summary']['schema_version']), (3, 5))
        self.assertEqual(payload['diagnostic_sample'], {
            'kind': 'direct_unmatched_colon_operand', 'opcode': 'XIC', 'argument_index': 0, 'raw_text': 'S:FS',
        })
        self.assertEqual(json.loads(work_check.render_work_check_report(payload)), payload)
        self.assertEqual(RETURNED.read_bytes(), before)

    def test_current_report_classifies_flag_and_has_no_mystery_sample(self) -> None:
        payload = report(SOURCE.replace(b'MysteryRack:7:I.Data[2].3', b'S:FS'))
        self.assertEqual((payload['schema_version'], payload['workflow_version']), (7, 'work-check-7'))
        nested = payload['analysis']['reference_summary']
        self.assertEqual((nested['schema_version'], nested['analyzer_version']), (9, 'source-references-7'))
        self.assertEqual(nested['operands']['by_status']['system_flag'], 1)
        self.assertEqual(nested['operands']['by_status']['unresolved'], 0)
        self.assertEqual(nested['rack_candidates']['matches']['direct_operands']['total'], 0)
        self.assertIsNone(payload['diagnostic_sample'])
        self.assertEqual(payload['status'], 'passed')
        work_check.validate_work_check_report(payload)

    def test_current_sample_rejection_is_role_specific_despite_another_gap(self) -> None:
        original = report(SOURCE.replace(b'XIC(', b'XIC(S:FS)XIO(s:fs)XIC('))
        self.assertEqual(original['analysis']['reference_summary']['rack_candidates']['matches']
                         ['direct_operands']['by_status']['no_candidate_match'], 1)
        for opcode in ('XIC', 'XIO'):
            for raw in ('S:FS', 's:fs', ' S:fS '):
                payload = deepcopy(original)
                payload['diagnostic_sample'].update(opcode=opcode, raw_text=raw)
                with self.subTest(opcode=opcode, raw=raw), self.assertRaises(ValueError):
                    work_check.validate_work_check_report(payload)
        work_check.validate_work_check_report(original)

    def test_other_roles_and_suffixed_spelling_keep_their_existing_gap(self) -> None:
        cases = (
            SOURCE.replace(b'XIC(MysteryRack:7:I.Data[2].3)', b'OTE(S:FS)'),
            SOURCE.replace(b'MysteryRack:7:I.Data[2].3', b'S:FS.Member'),
        )
        for data in cases:
            payload = report(data)
            self.assertEqual(payload['analysis']['reference_summary']['operands']['by_status']['system_flag'], 0)
            self.assertIsNotNone(payload['diagnostic_sample'])
            work_check.validate_work_check_report(payload)

    def test_current_and_historical_envelopes_reject_mixed_nested_versions(self) -> None:
        current = report()
        old = json.loads(RETURNED.read_bytes())
        for base, replacements in (
            (current, {'schema_version': 3, 'workflow_version': 'work-check-3'}),
            (old, {'schema_version': 4, 'workflow_version': 'work-check-4'}),
            (current, {'workflow_version': 'work-check-3'}),
        ):
            payload = deepcopy(base)
            payload.update(replacements)
            for sample in (payload['diagnostic_sample'], None):
                payload['diagnostic_sample'] = sample
                with self.subTest(replacements=replacements, sample=sample), self.assertRaises(ValueError):
                    work_check.validate_work_check_report(payload)

    def test_saved_analysis_uses_new_reference_contract_and_preserves_raw_flag(self) -> None:
        data = SOURCE.replace(b'MysteryRack:7:I.Data[2].3', b's:Fs')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            path = root / 'invented.L5X'
            path.write_bytes(data)
            result = work_check._analyze(root, path, root, {'commit': 'a' * 40, 'worktree': 'clean'})
            self.assertTrue(result['private_run_saved'])
            self.assertIsNone(result['diagnostic_sample'])
            saved, = (root / 'confidential/workspaces/work-check').glob('run-*')
            refs = json.loads((saved / 'references.json').read_text(encoding='utf-8'))
            self.assertEqual((refs['schema_version'], refs['analyzer_version']), (4, 'source-references-7'))
            self.assertEqual(refs['operands'][0]['raw_text'], 's:Fs')
            self.assertEqual(refs['operands'][0]['status'], 'system_flag')
            self.assertEqual((saved / 'snapshot.L5X').read_bytes(), data)
            self.assertEqual(path.read_bytes(), data)

    def test_publication_accepts_null_and_rejects_known_flag_as_unmatched(self) -> None:
        payload = report(SOURCE.replace(b'MysteryRack:7:I.Data[2].3', b'S:FS'))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / 'report.json'
            publish_summary(output, json.dumps(payload), input_path=root / 'invented.L5X')
            self.assertEqual(json.loads(output.read_text()), payload)
            bad = report(SOURCE.replace(b'XIC(', b'XIC(S:FS)XIC('))
            bad['diagnostic_sample']['raw_text'] = 'S:FS'
            with self.assertRaises(SummaryOutputError):
                publish_summary(root / 'bad.json', json.dumps(bad), input_path=root / 'invented.L5X')
            self.assertFalse((root / 'bad.json').exists())


if __name__ == '__main__':
    unittest.main()
