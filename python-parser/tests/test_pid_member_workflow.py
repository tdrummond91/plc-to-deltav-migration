"""PID member companion contracts using invented captures and temporary files."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import work_check
from plc_workbench.pid_members import FIELD_CATALOG, PidMemberError, analyze_pid_members
from plc_workbench.pid_member_summary import PidMemberSummaryError, validate_pid_member_summary
from plc_workbench.review import ReviewError, build_review_data, render_review_json, validate_review_data
from plc_workbench.review_html import ReviewHtmlError, render_review_html
from plc_workbench.storage import StorageError, _write_artifact, save_run

from test_pid_workflow import DATA, ROOT, arguments as pid_arguments, captured as pid_captured
from test_review_html import ParsedPage
from test_review_workflow import invoke
from test_unmatched_sample_report import REVISION, report


def captured(data: bytes = DATA):
    parts = pid_captured(data)
    return (*parts, analyze_pid_members(parts[0], parts[1], parts[2], parts[5], parts[6]))


def arguments(parts: tuple) -> dict:
    return pid_arguments(parts) | {'pid_members': parts[7]}


def options(parts: tuple) -> dict:
    return {key: arguments(parts)[key] for key in ('access', 'tag_data', 'pid', 'pid_members')}


class PidMemberReviewStorageTests(unittest.TestCase):
    def test_bundled_member_labels_and_groups_match_documented_python_catalog(self) -> None:
        source = (ROOT / 'python-parser/src/plc_workbench/review_assets/report.js').read_text(encoding='utf-8')
        labels = json.JSONDecoder().raw_decode(source.split('const PID_MEMBER_LABELS = ', 1)[1].lstrip())[0]
        groups = json.JSONDecoder().raw_decode(source.split('const PID_MEMBER_GROUPS = ', 1)[1].lstrip())[0]
        headers = json.JSONDecoder().raw_decode(source.split('const PID_MEMBER_HEADERS = ', 1)[1].lstrip())[0]
        self.assertEqual(labels, {name: row['label'] for name, row in FIELD_CATALOG.items()})
        self.assertEqual(headers, {name: {key: row[key] for key in ('datatype', 'kind')}
                                  for name, row in FIELD_CATALOG.items()})
        expected_groups = {group: sorted(name for name, row in FIELD_CATALOG.items() if row['group'] == group)
                           for group in {row['group'] for row in FIELD_CATALOG.values()}}
        self.assertEqual({group: sorted(names) for group, names in groups.items()}, expected_groups)

    def test_review5_manifest8_hash_twelve_artifacts_and_preserve_pid1_and_omitted_path(self) -> None:
        parts = captured()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            old = save_run(workspace, *parts[:2], **pid_arguments(parts))
            old_files = {path.name: path.read_bytes() for path in old.iterdir()}
            old_manifest = json.loads(old_files['manifest.json'])
            self.assertEqual((old_manifest['schema_version'], old_manifest['review_schema_version']), (7, 4))
            self.assertNotIn('pid-members.json', old_files)
            self.assertFalse(any(key.startswith('pid_member_') for key in old_manifest))
            old_payload = json.loads(ParsedPage(old_files['review.html'].decode()).scripts[0][1])
            self.assertNotIn('pid_members', old_payload)
            saved = save_run(workspace, *parts[:2], **arguments(parts))
            manifest = json.loads((saved / 'manifest.json').read_bytes())
            self.assertEqual((manifest['schema_version'], manifest['artifact_kind']),
                             (8, 'source_reference_sfc_access_tag_data_pid_member_review_run'))
            self.assertEqual((manifest['review_schema_version'], manifest['review_version']), (5, 'engineering-review-5'))
            self.assertEqual((manifest['pid_member_schema_version'], manifest['pid_member_analyzer_version'],
                              manifest['pid_member_catalog_version']), (1, 'pid-members-1', 'rockwell-pid-fields-1'))
            self.assertEqual(len(manifest['artifacts']), 12)
            private = json.loads((saved / 'pid-members.json').read_bytes())
            self.assertEqual(private, parts[7].to_dict())
            payload = json.loads(ParsedPage((saved / 'review.html').read_text(encoding='utf-8')).scripts[0][1])
            self.assertEqual(payload['pid_members'], private)
            for key in old_payload.keys() - {'schema_version', 'report_version', 'analysis_scope', 'status'}:
                self.assertEqual(payload[key], old_payload[key])
            validate_review_data(*parts[:4], payload, **options(parts))
            for name, details in manifest['artifacts'].items():
                content = (saved / name).read_bytes()
                self.assertEqual(details, {'sha256': hashlib.sha256(content).hexdigest(), 'size_bytes': len(content)})
                if name in old_files and name != 'review.html':
                    self.assertEqual(content, old_files[name])
            self.assertEqual({path.name: path.read_bytes() for path in old.iterdir()}, old_files)

    def test_dependencies_foreign_forged_and_cyclic_members_fail_before_allocation(self) -> None:
        parts = captured()
        full = arguments(parts)
        foreign = captured(DATA.replace(b'937291', b'937292'))[-1]
        forged = deepcopy(parts[-1])
        forged.coverage['members_total'] += 1
        cycle = deepcopy(parts[-1])
        cycle.coverage['private_extra'] = cycle.coverage
        variants = [dict(pid_members=parts[-1]), dict(full, include_review=False), dict(full, pid=None),
                    dict(full, tag_data=None), dict(full, access=None), dict(full, references=None),
                    dict(full, sfc_structure=None), dict(full, pid_members=foreign),
                    dict(full, pid_members=forged), dict(full, pid_members=cycle),
                    dict(full, pid_members=replace(parts[-1], schema_version=True))]
        with tempfile.TemporaryDirectory() as directory:
            for index, kwargs in enumerate(variants):
                workspace = Path(directory) / str(index)
                with self.subTest(index=index), self.assertRaises(StorageError):
                    save_run(workspace, *parts[:2], **kwargs)
                self.assertFalse(workspace.exists())
        payload = build_review_data(*parts[:4], **options(parts))
        payload['pid_members']['coverage']['members_total'] += 1
        with self.assertRaises(ReviewError):
            validate_review_data(*parts[:4], payload, **options(parts))

    def test_html_version_pairs_and_required_or_forbidden_companions_are_strict(self) -> None:
        parts = captured()
        all_options = options(parts)
        for version in range(1, 6):
            kwargs = {key: all_options[key] for key in tuple(all_options)[:version - 1]}
            original = build_review_data(*parts[:4], **kwargs)
            mutations = [lambda p: p.update(schema_version=True),
                         lambda p: p.update(report_version='engineering-review-0')]
            for companion, minimum in (('access', 2), ('tag_data', 3), ('pid', 4), ('pid_members', 5)):
                if version >= minimum:
                    mutations.extend((lambda p, key=companion: p.pop(key),
                                      lambda p, key=companion: p.update({key: None})))
                else:
                    mutations.append(lambda p, key=companion: p.update({key: {}}))
            for mutate in mutations:
                candidate = deepcopy(original)
                mutate(candidate)
                with self.subTest(version=version, mutate=mutate), self.assertRaises(ReviewHtmlError):
                    render_review_html(candidate)

    def test_review5_retains_budgets_and_rejects_before_allocating(self) -> None:
        parts = captured()
        data = build_review_data(*parts[:4], **options(parts))
        exact = len(render_review_json(data).encode('utf-8'))
        with patch('plc_workbench.review.MAX_REVIEW_BYTES', 1):
            with patch('plc_workbench.review.MAX_REVIEW_V3_BYTES', exact):
                self.assertEqual(build_review_data(*parts[:4], **options(parts)), data)
            with patch('plc_workbench.review.MAX_REVIEW_V3_BYTES', exact - 1), self.assertRaises(ReviewError):
                build_review_data(*parts[:4], **options(parts))
        with patch('plc_workbench.review_html.MAX_REVIEW_HTML_BYTES', 1), \
                patch('plc_workbench.review_html.MAX_REVIEW_PAYLOAD_BYTES', 1):
            self.assertIn('review-data', render_review_html(data))
        with tempfile.TemporaryDirectory() as directory:
            for index, limit in enumerate(('review.MAX_REVIEW_V3_BYTES', 'review_html.MAX_REVIEW_V3_PAYLOAD_BYTES',
                                          'review_html.MAX_REVIEW_V3_HTML_BYTES')):
                workspace = Path(directory) / str(index)
                with self.subTest(limit=limit), patch(f'plc_workbench.{limit}', 1), self.assertRaises(StorageError):
                    save_run(workspace, *parts[:2], **arguments(parts))
                self.assertFalse(workspace.exists())

    def test_render_failure_precedes_allocation_and_write_failure_never_finalizes(self) -> None:
        parts = captured()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / 'not-created'
            with patch('plc_workbench.pid_members.render_pid_members_json', side_effect=PidMemberError('PRIVATE_FAILURE')):
                with self.assertRaises(StorageError) as raised:
                    save_run(workspace, *parts[:2], **arguments(parts))
            self.assertNotIn('PRIVATE_FAILURE', str(raised.exception))
            self.assertFalse(workspace.exists())

            def fail(destination, run_dir, name, data):
                if name == 'pid-members.json':
                    raise OSError('PRIVATE_DISK_DETAIL')
                return _write_artifact(destination, run_dir, name, data)

            with patch('plc_workbench.storage._write_artifact', side_effect=fail), self.assertRaises(StorageError):
                save_run(workspace, *parts[:2], **arguments(parts))
            saved, = workspace.iterdir()
            self.assertFalse((saved / 'manifest.json').exists())

    def test_cli_captures_once_and_sanitizes_member_failure(self) -> None:
        from plc_workbench.source import capture_snapshot
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'invented.L5X'
            source.write_bytes(DATA)

            def capture_then_replace(path):
                snapshot = capture_snapshot(path)
                source.write_bytes(b'changed live input')
                return snapshot

            workspace = Path(directory) / 'runs'
            with patch('plc_workbench.source.capture_snapshot', side_effect=capture_then_replace) as capture, \
                    patch('plc_workbench.pid_members.analyze_pid_members', wraps=analyze_pid_members) as analyze:
                code, output, error = invoke(['review', str(source), '--workspace', str(workspace)])
            capture.assert_called_once_with(source)
            analyze.assert_called_once()
            self.assertEqual((code, error), (3, ''))
            saved, = workspace.iterdir()
            self.assertIn(str(saved / 'review.html'), output)
            self.assertEqual((saved / 'snapshot.L5X').read_bytes(), DATA)
            self.assertEqual(json.loads((saved / 'pid-members.json').read_bytes()), captured()[-1].to_dict())
            source.write_bytes(DATA)
            with patch('plc_workbench.pid_members.analyze_pid_members', side_effect=PidMemberError('PRIVATE_FAILURE')):
                code, output, error = invoke(['review', str(source), '--workspace', str(Path(directory) / 'failed')])
            self.assertEqual((code, output), (1, ''))
            self.assertNotIn('PRIVATE_FAILURE', error)
            self.assertFalse((Path(directory) / 'failed').exists())


class PidMemberWorkReportTests(unittest.TestCase):
    def test_latest_return_population_has_room_for_synthetic_member_summary(self) -> None:
        # This estimates report size from invented catalog headers. It does not
        # assert that the unseen work-machine member headers match the catalog.
        headers = ''.join(
            f'<ArrayMember Name="{name}" DataType="{row["datatype"]}" Dimensions="17"/>'
            if row['kind'] == 'array_member' else
            f'<DataValueMember Name="{name}" DataType="{row["datatype"]}" Value="0"/>'
            for name, row in FIELD_CATALOG.items())
        invented = DATA.replace(b'<DataValueMember Name="SP" DataType="REAL" Value="937291"/>', headers.encode())
        summary = report(invented)['analysis']['pid_member_summary']
        coverage = summary['coverage']
        returned = json.loads((ROOT / 'public/inspection/work-check-20261015T131431Z-51134c51.json').read_bytes())
        population = returned['analysis']['pid_summary']['coverage']['distinct_backing_owners']
        for key, value in coverage.items():
            if isinstance(value, dict):
                coverage[key] = {name: count * population for name, count in value.items()}
            elif key != 'source_pid_partial':
                coverage[key] *= population
        summary['tool_revision'] = deepcopy(returned['tool_revision'])
        validate_pid_member_summary(summary)
        returned.update(schema_version=17, workflow_version='work-check-17')
        returned['analysis']['pid_member_summary'] = summary
        rendered = work_check.render_work_check_report(returned)
        self.assertLess(len(rendered.encode('utf-8')), work_check.MAX_REPORT_BYTES)
        for private in ('937291', 'owner_id', 'element_id', 'raw_text'):
            self.assertNotIn(private, json.dumps(summary))

    def test_work17_is_count_only_and_historical_work16_is_frozen(self) -> None:
        payload = report(DATA)
        self.assertEqual((payload['schema_version'], payload['workflow_version']), (19, 'work-check-19'))
        self.assertEqual(payload['analysis']['pid_member_summary']['schema_version'], 1)
        rendered = work_check.render_work_check_report(payload)
        self.assertEqual(json.loads(rendered), payload)
        self.assertLess(len(rendered.encode()), 32 * 1024)
        for private in ('PRIVATE_', '937291', 'snapshot', 'instruction_id', 'owner_id', 'content_id', 'raw_text'):
            self.assertNotIn(private, rendered)
        paths = [path for path in (ROOT / 'public/inspection').glob('work-check-*.json')
                 if json.loads(path.read_bytes())['schema_version'] == 16]
        self.assertTrue(paths)
        for path in paths:
            before = path.read_bytes()
            historical = json.loads(before)
            self.assertEqual(json.loads(work_check.render_work_check_report(historical)), historical)
            for mutate in (lambda p: p.update(schema_version=17, workflow_version='work-check-17'),
                           lambda p: p['analysis'].update(pid_member_summary=payload['analysis']['pid_member_summary']),
                           lambda p: p['analysis'].update(pid_member_summary=None)):
                changed = deepcopy(historical)
                mutate(changed)
                with self.subTest(path=path.name, mutate=mutate), self.assertRaises(ValueError):
                    work_check.validate_work_check_report(changed)
            self.assertEqual(path.read_bytes(), before)

    def test_summary_presence_revision_versions_and_closed_keys(self) -> None:
        for mutate in (lambda p: p['analysis'].pop('pid_member_summary'),
                       lambda p: p['analysis'].update(pid_member_summary=None),
                       lambda p: p['analysis']['pid_member_summary']['tool_revision'].update(commit='b' * 40),
                       lambda p: p['analysis']['pid_member_summary'].update(schema_version=True),
                       lambda p: p['analysis']['pid_member_summary'].update(schema_version=2),
                       lambda p: p['analysis']['pid_member_summary'].update(private='PRIVATE'),
                       lambda p: p['analysis'].update(private='PRIVATE'),
                       lambda p: p['analysis']['pid_summary'].update(schema_version=2)):
            candidate = report(DATA)
            mutate(candidate)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)

    def test_distinct_member_counts_are_bounded_by_pid_links_and_captured_tag_data(self) -> None:
        repeated = DATA.replace(b'PID(A,1,0,A,0,0,0);', b'PID(A,1,0,A,0,0,0)PID(A,1,0,A,0,0,0);')
        candidate = report(repeated)
        coverage = candidate['analysis']['pid_member_summary']['coverage']
        self.assertEqual((coverage['structures_total'], coverage['members_total'], coverage['distinct_backing_owners']), (1, 1, 1))
        self.assertEqual(candidate['analysis']['pid_summary']['coverage']['direct_member_occurrences'], 2)
        work_check.validate_work_check_report(candidate)
        extra_structure = DATA.replace(b'</Structure></Data>',
            b'</Structure><Structure DataType="PID"><DataValueMember Name="SP" DataType="REAL" Value="1"/></Structure></Data>')
        extra_member = DATA.replace(b'</Structure></Data>',
            b'<DataValueMember Name="SP" DataType="REAL" Value="1"/></Structure></Data>')
        second_owner = DATA.replace(b'</Tags>', b'<Tag Name="B" TagType="Base" DataType="PID">'
            b'<Data Format="Decorated"><Structure DataType="PID"><DataValueMember Name="SP" DataType="REAL" Value="1"/>'
            b'</Structure></Data></Tag></Tags>')
        both_owners = second_owner.replace(b'PID(A,1,0,A,0,0,0);', b'PID(A,1,0,A,0,0,0)PID(B,1,0,A,0,0,0);')
        for target, donor in ((DATA, extra_member), (DATA, extra_structure), (second_owner, both_owners),
                              (repeated, extra_member), (repeated, extra_structure)):
            candidate = report(target)
            transplanted = report(donor)['analysis']['pid_member_summary']
            validate_pid_member_summary(transplanted)
            candidate['analysis']['pid_member_summary'] = transplanted
            with self.subTest(target=target == repeated, donor=donor == extra_structure), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)

    def test_source_pid_status_and_overall_status_are_reconciled(self) -> None:
        candidate = report(DATA)
        members = candidate['analysis']['pid_member_summary']
        self.assertEqual(members['coverage']['source_pid_partial'], 0)
        members['coverage']['source_pid_partial'] = 1
        # Missing documented fields keep this companion partial independently.
        validate_pid_member_summary(members)
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)
        candidate = report(DATA)
        candidate['analysis']['status'] = 'complete'
        candidate['status'] = 'passed'
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)

    def test_pid_populations_cannot_be_omitted_or_undercounted_by_unique_summary(self) -> None:
        empty = DATA.replace(b'PID(A,1,0,A,0,0,0);', b'XIC(A);')
        for target, donor in ((DATA, empty),
                              (DATA.replace(b'</Structure></Data>', b'<DataValueMember Name="KP" DataType="REAL" Value="1"/></Structure></Data>'), DATA),
                              (DATA.replace(b'</Structure></Data>', b'</Structure><Structure DataType="PID"/></Data>'), DATA)):
            candidate = report(target)
            transplanted = report(donor)['analysis']['pid_member_summary']
            validate_pid_member_summary(transplanted)
            candidate['analysis']['pid_member_summary'] = transplanted
            with self.subTest(donor_is_empty=donor == empty), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        # Two different backing owners cannot disappear through deduplication;
        # one owner reused by two occurrences remains valid in the earlier test.
        two_owners = DATA.replace(b'</Tags>', b'<Tag Name="B" TagType="Base" DataType="PID">'
            b'<Data Format="Decorated"><Structure DataType="PID"><DataValueMember Name="SP" DataType="REAL" Value="1"/>'
            b'</Structure></Data></Tag></Tags>').replace(b'PID(A,1,0,A,0,0,0);',
            b'PID(A,1,0,A,0,0,0)PID(B,1,0,A,0,0,0);')
        candidate = report(two_owners)
        candidate['analysis']['pid_member_summary']['coverage']['distinct_backing_owners'] = 1
        validate_pid_member_summary(candidate['analysis']['pid_member_summary'])
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)
        fewer_members = two_owners.replace(b'<DataValueMember Name="SP" DataType="REAL" Value="937291"/>', b'')
        more_structures = two_owners.replace(b'</Structure></Data>',
            b'</Structure><Structure DataType="PID"/></Data>', 1)
        for target, donor in ((two_owners, fewer_members), (more_structures, two_owners)):
            candidate = report(target)
            candidate['analysis']['pid_member_summary'] = report(donor)['analysis']['pid_member_summary']
            validate_pid_member_summary(candidate['analysis']['pid_member_summary'])
            with self.subTest(target_extra_structure=target == more_structures), self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        # A second backing owner without candidate structures cannot be counted
        # as a member owner merely because the first owner has two structures.
        one_linked = DATA.replace(b'</Structure></Data>', b'</Structure><Structure DataType="PID"/></Data>')
        one_linked = one_linked.replace(b'</Tags>', b'<Tag Name="B" TagType="Base" DataType="PID"/></Tags>')
        one_linked = one_linked.replace(b'PID(A,1,0,A,0,0,0);', b'PID(A,1,0,A,0,0,0)PID(B,1,0,A,0,0,0);')
        candidate = report(one_linked)
        candidate['analysis']['pid_member_summary']['coverage']['distinct_backing_owners'] = 2
        validate_pid_member_summary(candidate['analysis']['pid_member_summary'])
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)
    def test_failure_not_run_null_summaries_and_member_error_are_versioned(self) -> None:
        original = report(DATA)
        for state in ('failed', 'not_run'):
            candidate = deepcopy(original)
            candidate['analysis'] = {'status': state, 'failure_code': 'pid_member_error' if state == 'failed' else None,
                'private_run_saved': False, 'reference_summary': None, 'sfc_structure_summary': None,
                'access_summary': None, 'tag_data_summary': None, 'pid_summary': None, 'pid_member_summary': None, 'calculation_summary': None}
            candidate.update(status='failed', diagnostic_sample=None)
            if state == 'not_run':
                candidate['tests']['application'] = work_check.unavailable_result('not_run')
            work_check.validate_work_check_report(candidate)
            candidate['analysis']['pid_member_summary'] = original['analysis']['pid_member_summary']
            with self.assertRaises(ValueError):
                work_check.validate_work_check_report(candidate)
        candidate = deepcopy(original)
        candidate.update(schema_version=16, workflow_version='work-check-16', status='failed', diagnostic_sample=None)
        candidate['analysis'] = {'status': 'failed', 'failure_code': 'pid_member_error', 'private_run_saved': False,
            'reference_summary': None, 'sfc_structure_summary': None, 'access_summary': None, 'tag_data_summary': None,
            'pid_summary': None}
        with self.assertRaises(ValueError):
            work_check.validate_work_check_report(candidate)

    def test_runner_passes_captured_members_once_and_sanitizes_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'invented.L5X'
            source.write_bytes(DATA)
            with patch.object(work_check, 'capture_snapshot', wraps=work_check.capture_snapshot) as capture, \
                    patch.object(work_check, 'analyze_pid_members', wraps=analyze_pid_members) as analyze, \
                    patch.object(work_check, 'save_run') as save:
                outcome = work_check._analyze(root, source, root, REVISION)
            capture.assert_called_once_with(source)
            analyze.assert_called_once()
            self.assertEqual(save.call_args.args[1].data, DATA)
            self.assertEqual(save.call_args.kwargs['pid_members'].to_dict(), captured()[-1].to_dict())
            self.assertIsNotNone(outcome['pid_member_summary'])
            for target, error, expected, saved in (
                ('analyze_pid_members', PidMemberError('PRIVATE_FAILURE'), 'pid_member_error', False),
                ('build_pid_member_summary', PidMemberSummaryError('PRIVATE_FAILURE'), 'summary_error', True),
            ):
                with patch.object(work_check, target, side_effect=error), patch.object(work_check, 'save_run'):
                    outcome = work_check._analyze(root, source, root, REVISION)
                self.assertEqual((outcome['failure_code'], outcome['private_run_saved']), (expected, saved))
                for key in ('reference_summary', 'sfc_structure_summary', 'access_summary', 'tag_data_summary',
                            'pid_summary', 'pid_member_summary', 'calculation_summary'):
                    self.assertIsNone(outcome[key])
                self.assertNotIn('PRIVATE_FAILURE', json.dumps(outcome))
                self.assertIn('PRIVATE_FAILURE', (root / 'analysis.log').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
