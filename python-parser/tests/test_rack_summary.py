"""Rack diagnostics stay private; only closed, reconciled counts are shared."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from plc_workbench.reference_reporting import render_reference_text
from plc_workbench.reference_summary import (
    ReferenceSummaryError, build_reference_summary, render_reference_summary,
    validate_reference_summary,
)
from plc_workbench.references import analyze_references
from plc_workbench.source import analyze_snapshot, snapshot_from_bytes
from plc_workbench.storage import save_run
from plc_workbench.summary_output import SummaryOutputError, publish_summary
from plc_workbench.work_check import validate_work_check_report


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'public/fixtures/synthetic/rack_io_gap_demo.L5X'
REVISION = {'commit': 'a' * 40, 'worktree': 'clean'}


def records(data: bytes | None = None):
    snapshot = snapshot_from_bytes(FIXTURE.read_bytes() if data is None else data)
    source = analyze_snapshot(snapshot)
    references = analyze_references(source)
    report = build_reference_summary(source, references, revision=REVISION)
    return snapshot, source, references, report


class RackSummaryTests(unittest.TestCase):
    def test_candidates_reconcile_without_promoting_bindings(self) -> None:
        _, source, references, report = records()
        rack = report['rack_candidates']
        self.assertEqual((source.schema_version, references.schema_version), (3, 6))
        self.assertEqual((report['schema_version'], report['source_summary']['schema_version']), (12, 4))
        self.assertEqual(rack['declarations']['total'], 2)
        self.assertEqual(rack['declarations']['named'], 2)
        self.assertEqual(rack['declarations']['by_direction'], {'input': 1, 'output': 1})
        for group, total in (('aliases', 1), ('direct_operands', 2), ('alias_operands', 1)):
            self.assertEqual(rack['matches'][group]['total'], total)
            self.assertEqual(rack['matches'][group]['by_status']['unique_candidate'], total)
        self.assertEqual(report['symbols']['total'], 4)
        self.assertEqual(report['operands']['by_status']['root_bound'], 2)
        self.assertEqual(report['operands']['by_status']['unresolved'], 3)
        self.assertEqual(report['aliases']['by_status']['unresolved'], 1)
        self.assertEqual(report['module_io']['total'], 3)
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(rack['backing_mapping'], 'not_analyzed')

    def test_renaming_private_roots_and_values_preserves_public_report(self) -> None:
        data = FIXTURE.read_bytes()
        first = records(data)
        second = records(data.replace(b'Remote', b'PRIVATE_REMOTE').replace(b'RackCard', b'PRIVATE_CARD')
                         .replace(b'ProbeAlias', b'PRIVATE_ALIAS').replace(b'Data.0', b'PRIVATE_FIELD.6'))
        self.assertEqual(first[3], second[3])
        rendered = render_reference_summary(second[3])
        for value in ('PRIVATE_', 'Remote:3:I', 'source_id', 'candidate_id', 'terminal_root',
                      'lookup_scope_id', second[0].id, second[0].sha256):
            self.assertNotIn(value, rendered)

    def test_ordinary_declaration_at_candidate_root_keeps_binding_priority(self) -> None:
        data = FIXTURE.read_bytes().replace(b'<InputTag/>', b'<InputTag Name="Remote:3:I"/>')
        _, _, references, report = records(data)
        # The ordinary input declaration binds both the direct use and alias;
        # the separate rack candidate does not create a symbol ambiguity.
        self.assertEqual(references.operands[0]['status'], 'root_bound')
        self.assertEqual(references.operands[1]['status'], 'root_bound')
        self.assertEqual(references.aliases[0]['status'], 'root_bound')
        matches = report['rack_candidates']['matches']
        self.assertEqual(matches['aliases']['total'], 0)
        self.assertEqual(matches['alias_operands']['total'], 0)
        self.assertEqual(matches['direct_operands']['by_status']['unique_candidate'], 1)
        self.assertEqual(matches['direct_operands']['by_status']['no_candidate_match'], 1)
        self.assertEqual(report['rack_candidates']['declarations']['named'], 2)

    def test_closed_fields_and_count_relationships_are_enforced(self) -> None:
        original = records()[3]
        mutations = (
            lambda r: r['rack_candidates'].update(PRIVATE_NAME='PRIVATE_VALUE'),
            lambda r: r['rack_candidates'].update(backing_mapping='resolved'),
            lambda r: r['rack_candidates']['declarations'].update(named=1),
            lambda r: r['rack_candidates']['declarations'].update(total=True),
            lambda r: r['rack_candidates']['declarations']['by_direction'].update(input=2),
            lambda r: r['rack_candidates']['declarations']['by_name_origin'].update(explicit_name=0),
            lambda r: r['rack_candidates']['declarations']['unavailable_by_reason'].update(PRIVATE_REASON=0),
            lambda r: r['rack_candidates']['matches'].update(PRIVATE_GROUP={}),
            lambda r: r['rack_candidates']['matches']['aliases'].update(total=2),
            lambda r: r['rack_candidates']['matches']['direct_operands']['by_status'].update(unique_candidate=False),
            lambda r: r.update(status='complete'),
        )
        for index, mutate in enumerate(mutations):
            report = deepcopy(original)
            mutate(report)
            with self.subTest(index=index), self.assertRaises(ReferenceSummaryError) as caught:
                render_reference_summary(report)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_match_denominators_cannot_be_moved_between_population_types(self) -> None:
        report = records()[3]
        matches = report['rack_candidates']['matches']
        matches['aliases']['total'] -= 1
        matches['aliases']['by_status']['unique_candidate'] -= 1
        matches['direct_operands']['total'] += 1
        matches['direct_operands']['by_status']['unique_candidate'] += 1
        with self.assertRaises(ReferenceSummaryError):
            validate_reference_summary(report)

        report = records()[3]
        statuses = report['rack_candidates']['matches']['alias_operands']['by_status']
        statuses['no_candidate_match'], statuses['unique_candidate'] = 1, 0
        with self.assertRaises(ReferenceSummaryError):
            validate_reference_summary(report)

    def test_impossible_positive_match_buckets_are_rejected(self) -> None:
        data = FIXTURE.read_bytes()
        for altered, status in (
            (data.replace(b'ParentModule="Remote"', b'ParentModule="Absent"'), 'unique_candidate'),
            (data.replace(b'<OutAliasTag/>', b''), 'ambiguous_candidate'),
            (data, 'candidate_names_unavailable'),
        ):
            report = records(altered)[3]
            group = report['rack_candidates']['matches']['aliases']
            group['by_status'] = dict.fromkeys(group['by_status'], 0)
            group['by_status'][status] = group['total']
            with self.subTest(status=status), self.assertRaises(ReferenceSummaryError):
                validate_reference_summary(report)

    def test_alias_mediated_matches_require_an_unresolved_colon_alias(self) -> None:
        data = FIXTURE.read_bytes().replace(
            b'<Tag Name="ProbeAlias" TagType="Alias" AliasFor="Remote:3:I.Data.0"/>', b'')
        report = records(data)[3]
        matches = report['rack_candidates']['matches']
        self.assertEqual(matches['aliases']['total'], 0)
        matches['direct_operands'], matches['alias_operands'] = matches['alias_operands'], matches['direct_operands']
        with self.assertRaises(ReferenceSummaryError):
            validate_reference_summary(report)

    def test_private_candidate_and_match_evidence_cannot_be_forged(self) -> None:
        _, source, original, _ = records()
        mutations = (
            lambda r: r.rack_candidates['candidates'][0].update(name='PRIVATE:I'),
            lambda r: r.rack_candidates['candidates'][0].update(backing_status='resolved'),
            lambda r: r.rack_candidates['matches']['aliases'][0].update(candidate_count=True),
            lambda r: r.rack_candidates['matches']['aliases'][0].update(terminal_root='PRIVATE:I'),
            lambda r: r.rack_candidates['matches']['direct_operands'].clear(),
        )
        for index, mutate in enumerate(mutations):
            references = deepcopy(original)
            mutate(references)
            with self.subTest(index=index), self.assertRaises(ReferenceSummaryError):
                build_reference_summary(source, references)

    def test_private_persistence_and_text_keep_evidence_and_limits(self) -> None:
        snapshot, source, references, _ = records()
        with tempfile.TemporaryDirectory() as folder:
            run = save_run(Path(folder), snapshot, source, references=references)
            self.assertEqual((run / 'snapshot.L5X').read_bytes(), snapshot.data)
            saved = json.loads((run / 'references.json').read_text(encoding='utf-8'))
            self.assertEqual(saved, references.to_dict())
            manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual((manifest['schema_version'], manifest['analyzer_version']), (2, 'source-references-9'))
            self.assertEqual(manifest['parser_version'], 'source-inventory-3')
            text = (run / 'references.txt').read_text(encoding='utf-8')
            self.assertEqual(text, render_reference_text(references, inventory=source))
            self.assertIn('Remote:3:I', text)
            self.assertIn('backing mapping not analyzed', text)
            self.assertIn('matching is inconclusive', text)

    def test_public_writer_accepts_new_counts_and_rejects_private_links(self) -> None:
        report = records()[3]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'rack.json'
            publish_summary(path, render_reference_summary(report), input_path=root / 'invented.L5X')
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), report)
            report['rack_candidates']['matches']['aliases']['candidate_id'] = 'PRIVATE_LINK'
            rejected = root / 'rejected.json'
            with self.assertRaises(SummaryOutputError):
                publish_summary(rejected, json.dumps(report), input_path=root / 'invented.L5X')
            self.assertFalse(rejected.exists())

    def test_all_returned_work_reports_remain_unchanged_and_valid(self) -> None:
        paths = list((ROOT / 'public/inspection').glob('work-check-*.json'))
        self.assertGreaterEqual(len(paths), 7)
        for path in paths:
            before = path.read_bytes()
            with self.subTest(report=path.name):
                validate_work_check_report(json.loads(before))
                self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
