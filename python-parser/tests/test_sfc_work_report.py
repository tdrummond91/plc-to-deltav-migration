"""Work-envelope integration using invented SFC evidence and public history."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import work_check
from plc_workbench.reference_summary import build_reference_summary
from plc_workbench.references import analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes

from test_unmatched_sample_report import REVISION, SOURCE, report

SFC_SOURCE = SOURCE.replace(b'</Routines>', b'''<Routine Name="PrivateChart" Type="SFC">
<SFCContent><Step ID="1" Operand="PRIVATE_STEP" InitialStep="true"/>
<Transition ID="2" Operand="PRIVATE_TRANS"><Condition><STContent>
<Line Number="0"><![CDATA[PRIVATE_VALUE > 932;]]></Line></STContent></Condition></Transition>
<DirectedLink FromID="1" ToID="2"/></SFCContent></Routine></Routines>''')
PREVIOUS = Path(__file__).resolve().parents[2] / 'public/inspection/work-check-20261015T012257Z-0878989d.json'
PREVIOUS_SFC = Path(__file__).resolve().parents[2] / 'public/inspection/work-check-20261015T015742Z-873f283d.json'


class SfcWorkReportTests(unittest.TestCase):
    def test_current_work16_keeps_separate_summary_without_changing_reference_contract(self) -> None:
        payload = report(SFC_SOURCE)
        self.assertEqual((payload['schema_version'], payload['workflow_version']), (20, 'work-check-20'))
        analysis = payload['analysis']
        self.assertEqual(analysis['reference_summary']['schema_version'], 12)
        self.assertEqual(analysis['sfc_structure_summary']['source_sfc_routines'], 1)
        self.assertEqual(analysis['sfc_structure_summary']['status'], 'complete')
        self.assertEqual(analysis['status'], 'partial')
        rendered = work_check.render_work_check_report(payload)
        for private in ('PRIVATE_', '932', 'PrivateChart', 'FromID', 'snapshot', 'raw_name'):
            self.assertNotIn(private, rendered)
        self.assertEqual(json.loads(rendered), payload)
        inventory = analyze_snapshot(snapshot_from_bytes(SFC_SOURCE))
        self.assertEqual(build_reference_summary(inventory, analyze_references(inventory), revision=REVISION),
                         analysis['reference_summary'])

    def test_frozen_work11_keeps_sfc1_and_rejects_new_summary_pair(self) -> None:
        before = PREVIOUS_SFC.read_bytes()
        old = json.loads(before)
        self.assertEqual((old['schema_version'], old['analysis']['sfc_structure_summary']['schema_version']), (11, 1))
        self.assertEqual(json.loads(work_check.render_work_check_report(old)), old)
        current = report(SFC_SOURCE)
        self.assertEqual(current['analysis']['sfc_structure_summary']['schema_version'], 2)
        changed = deepcopy(current)
        changed.update(schema_version=11, workflow_version='work-check-11')
        del changed['analysis']['access_summary']
        del changed['analysis']['tag_data_summary']
        del changed['analysis']['pid_summary']
        del changed['analysis']['pid_member_summary']
        del changed['analysis']['calculation_summary']
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(changed)
        changed = deepcopy(old)
        changed.update(schema_version=12, workflow_version='work-check-12')
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(changed)
        self.assertEqual(PREVIOUS_SFC.read_bytes(), before)

    def test_source_population_revision_and_summary_presence_must_match(self) -> None:
        original = report(SFC_SOURCE)
        for mutate in (
            lambda p: p['analysis'].pop('sfc_structure_summary'),
            lambda p: p['analysis'].update(sfc_structure_summary=None),
            lambda p: p['analysis']['sfc_structure_summary']['tool_revision'].update(commit='b' * 40),
        ):
            changed = deepcopy(original)
            mutate(changed)
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(changed)
        changed = deepcopy(original)
        changed['analysis']['sfc_structure_summary'] = report()['analysis']['sfc_structure_summary']
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(changed)

    def test_historical_work10_is_frozen_and_report_bytes_remain_unchanged(self) -> None:
        before = PREVIOUS.read_bytes()
        old = json.loads(before)
        self.assertEqual((old['schema_version'], old['analysis']['reference_summary']['schema_version']), (10, 12))
        self.assertNotIn('sfc_structure_summary', old['analysis'])
        self.assertEqual(json.loads(work_check.render_work_check_report(old)), old)
        old['analysis']['sfc_structure_summary'] = report()['analysis']['sfc_structure_summary']
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(old)
        self.assertEqual(PREVIOUS.read_bytes(), before)

    def test_actual_analysis_saves_sfc_artifacts_and_preserves_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(SFC_SOURCE)
            result = work_check._analyze(root, source, root, REVISION)
            self.assertEqual(result['status'], 'partial')
            self.assertTrue(result['private_run_saved'])
            saved, = (root / 'confidential/workspaces/work-check').glob('run-*')
            manifest = json.loads((saved / 'manifest.json').read_bytes())
            self.assertEqual(manifest['schema_version'], 21)
            self.assertEqual(manifest['artifact_kind'], 'source_reference_sfc_access_tag_data_pid_member_calculation_rung_relationship_condition_review_run')
            self.assertEqual(set(manifest['artifacts']), {'snapshot.L5X', 'inventory.json', 'overview.txt',
                'references.json', 'references.txt', 'sfc-structure.json', 'sfc-structure.txt', 'review.html', 'access.json', 'tag-data.json', 'pid.json', 'pid-members.json', 'calculations.json', 'rung-analysis.json', 'relationships.json', 'boolean-conditions.json'})
            sfc = json.loads((saved / 'sfc-structure.json').read_bytes())
            self.assertEqual(sfc['status'], 'complete')
            self.assertIn('PRIVATE_VALUE', (saved / 'sfc-structure.txt').read_text(encoding='utf-8'))
            self.assertEqual((saved / 'snapshot.L5X').read_bytes(), SFC_SOURCE)
            self.assertEqual(source.read_bytes(), SFC_SOURCE)

    def test_sfc_error_produces_fixed_failure_envelope_without_summary(self) -> None:
        from plc_workbench.sfc_structure import SfcStructureError
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(SFC_SOURCE)
            with patch('plc_workbench.sfc_structure.analyze_sfc_structure',
                       side_effect=SfcStructureError('PRIVATE_FAILURE_VALUE')):
                result = work_check._analyze(root, source, root, REVISION)
            self.assertEqual(result['failure_code'], 'sfc_structure_error')
            self.assertFalse(result['private_run_saved'])
            self.assertIsNone(result['sfc_structure_summary'])
            self.assertIsNone(result['reference_summary'])
            payload = report()
            result.pop('diagnostic_sample')
            result.pop('targeted_samples', None)
            self.assertIsNone(result.pop('custom_instruction_summary'))
            self.assertIsNone(result.pop('indexed_access_summary'))
            self.assertIsNone(result.pop('sfr_summary'))
            self.assertIsNone(result.pop('aoi_body_summary'))
            self.assertIsNone(result.pop('pid_connection_summary'))
            self.assertIsNone(result.pop('calculation_path_summary'))
            self.assertIsNone(result.pop('output_context_summary'))
            self.assertIsNone(result.pop('stateful_object_summary'))
            payload.update(schema_version=27, workflow_version='work-check-27',
                           analysis=result, status='failed', diagnostic_sample=None)
            rendered = work_check.render_work_check_report(payload)
            self.assertNotIn('PRIVATE_FAILURE_VALUE', rendered)
            old = json.loads(PREVIOUS.read_bytes())
            old.update(analysis={k: v for k, v in result.items() if k not in ('sfc_structure_summary', 'access_summary', 'tag_data_summary', 'pid_summary', 'pid_member_summary', 'calculation_summary', 'rung_analysis_summary', 'relationship_summary', 'condition_summary', 'binding_context_summary')},
                       status='failed')
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(old)


if __name__ == '__main__':
    unittest.main()
