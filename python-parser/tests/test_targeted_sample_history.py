"""Durable sample releases use only invented local files and no subprocesses."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from plc_workbench import targeted_sample_history as history
from plc_workbench import work_check
from plc_workbench.work_check import render_work_check_report
from plc_workbench.targeted_samples import MAX_BYTES, REQUEST_ID, render_targeted_samples_json
from test_targeted_sample_workflow import record, report
from test_rack_backing_context_workflow import report as current_report
from test_control_interpretation_workflow import report as previous_report
from test_save_diagnostics import failed_report


def journal(root: Path) -> Path:
    return root / 'confidential' / 'work-check-samples' / f'{REQUEST_ID}.json'


def publish(root: Path, payload: dict, filename: str = 'work-check-first.json') -> Path:
    path = root / 'public' / 'inspection' / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_work_check_report(payload), encoding='utf-8')
    return path


class TargetedSampleHistoryTests(unittest.TestCase):
    def test_first_selection_is_reserved_before_any_publication_and_never_rotates(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            builder = Mock(return_value=record())
            first = history.resolve_targeted_samples(root, builder)
            self.assertEqual(first, history.sample_envelope('selected', record()))
            builder.assert_called_once_with()
            self.assertEqual(json.loads(journal(root).read_bytes()), record())
            self.assertFalse((root / 'public').exists())
            # A failed publication/commit cannot cause the next run to select
            # another rung, even when that next run has another source export.
            next_builder = Mock(return_value=record(151))
            again = history.resolve_targeted_samples(root, next_builder)
            self.assertEqual(again, history.sample_envelope('replayed', record()))
            next_builder.assert_not_called()
            self.assertEqual(list(journal(root).parent.iterdir()), [journal(root)])

    def test_fresh_clone_recovers_public_record_without_selector(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            publish(root, report())
            builder = Mock(side_effect=AssertionError('No new selection.'))
            outcome = history.resolve_targeted_samples(root, builder)
            self.assertEqual(outcome, history.sample_envelope('replayed', record()))
            self.assertEqual(json.loads(journal(root).read_bytes()), record())
            builder.assert_not_called()

    def test_history_read_envelope_matches_current_work_report_budget(self) -> None:
        self.assertEqual(history.MAX_WORK_REPORT_BYTES,
                         work_check._report_limit(work_check._CONSTANTS['schema_version']))
        self.assertEqual(history.MAX_HISTORY_FILES, 512)
        self.assertEqual(history.MAX_HISTORY_BYTES, 32 * 1024 * 1024)

    def test_current_report_above_64k_replays_original_frozen_record_without_selection(self) -> None:
        payload = current_report()
        expected = payload['targeted_samples']['record']
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            path = publish(root, payload)
            original = path.read_bytes()
            self.assertGreater(len(original), 64 * 1024)
            self.assertLessEqual(len(original), history.MAX_WORK_REPORT_BYTES)
            builder = Mock(side_effect=AssertionError('No new selection.'))
            for _ in range(2):
                self.assertEqual(history.resolve_targeted_samples(root, builder),
                                 history.sample_envelope('replayed', expected))
                self.assertEqual(json.loads(journal(root).read_bytes()), expected)
                self.assertEqual(path.read_bytes(), original)
            builder.assert_not_called()

    def test_historical_versions_reject_raw_files_above_their_own_budgets(self) -> None:
        for payload in (failed_report(1), report(), previous_report()):
            version = payload['schema_version']
            encoded = render_work_check_report(payload).encode('utf-8')
            content = encoded + b' ' * (work_check._report_limit(version) + 1 - len(encoded))
            self.assertLess(len(content), history.MAX_WORK_REPORT_BYTES)
            with self.subTest(version=version), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                path = root / 'public/inspection/work-check-padded.json'
                path.parent.mkdir(parents=True)
                path.write_bytes(content)
                builder = Mock(side_effect=AssertionError('No new selection.'))
                self.assertEqual(history.resolve_targeted_samples(root, builder),
                                 history.sample_envelope('unavailable'))
                self.assertFalse(journal(root).exists())
                self.assertEqual(path.read_bytes(), content)
                builder.assert_not_called()

    def test_current_raw_file_at_limit_replays_but_over_limit_fails_closed(self) -> None:
        payload = current_report()
        expected = payload['targeted_samples']['record']
        encoded = render_work_check_report(payload).encode('utf-8')
        for extra in (0, 1):
            content = encoded + b' ' * (history.MAX_WORK_REPORT_BYTES + extra - len(encoded))
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                path = root / 'public/inspection/work-check-current.json'
                path.parent.mkdir(parents=True)
                path.write_bytes(content)
                builder = Mock(side_effect=AssertionError('No new selection.'))
                outcome = history.resolve_targeted_samples(root, builder)
                self.assertEqual(outcome, history.sample_envelope('unavailable') if extra
                                 else history.sample_envelope('replayed', expected))
                self.assertEqual(journal(root).exists(), not extra)
                self.assertEqual(path.read_bytes(), content)
                builder.assert_not_called()

    def test_identical_public_replays_and_local_reservation_agree(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            history.resolve_targeted_samples(root, lambda: record())
            publish(root, report())
            historical = report(151)
            historical['targeted_samples'] = history.sample_envelope('replayed', record())
            publish(root, historical, 'work-check-second.json')
            self.assertEqual(history.resolve_targeted_samples(root, lambda: record(151)),
                             history.sample_envelope('replayed', record()))

    def test_conflicting_private_and_public_or_public_records_withhold(self) -> None:
        for private in (False, True):
            with self.subTest(private=private), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                if private:
                    history.resolve_targeted_samples(root, lambda: record())
                else:
                    publish(root, report())
                publish(root, report(151), 'work-check-second.json')
                builder = Mock(return_value=record())
                self.assertEqual(history.resolve_targeted_samples(root, builder), history.sample_envelope('unavailable'))
                builder.assert_not_called()

    def test_unavailable_established_release_never_falls_back_to_fresh_selection(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            payload = report()
            payload['targeted_samples'] = history.sample_envelope('unavailable')
            publish(root, payload)
            builder = Mock(return_value=record())
            self.assertEqual(history.resolve_targeted_samples(root, builder), history.sample_envelope('unavailable'))
            builder.assert_not_called()
            # A surviving valid reservation supplies the missing immutable data.
            journal(root).parent.mkdir(parents=True)
            journal(root).write_text(render_targeted_samples_json(record()), encoding='utf-8')
            self.assertEqual(history.resolve_targeted_samples(root, builder)['status'], 'replayed')

    def test_failed_tests_do_not_establish_release_but_legacy_history_is_validated(self) -> None:
        from test_save_diagnostics import failed_report
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            payload = failed_report(27)
            payload.update(schema_version=28, workflow_version='work-check-28', targeted_samples=history.sample_envelope())
            publish(root, payload)
            publish(root, failed_report(1), 'work-check-legacy.json')
            self.assertEqual(history.resolve_targeted_samples(root, lambda: record())['status'], 'selected')

    def test_selection_error_before_reservation_can_retry_after_fix(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            payload = report()
            payload['targeted_samples'] = history.sample_envelope('unavailable', reason='selection_error')
            publish(root, payload)
            self.assertEqual(history.resolve_targeted_samples(root, lambda: record())['status'], 'selected')

    def test_malformed_duplicate_or_oversized_history_blocks_reuse_and_new_selection(self) -> None:
        originals = [b'{', b'{"schema_version":1,"schema_version":1}',
                     b' ' * (history.MAX_WORK_REPORT_BYTES + 1),
                     json.dumps(dict(report(), unexpected='SECRET')).encode()]
        for content in originals:
            for existing in (False, True):
                with self.subTest(size=len(content), existing=existing), tempfile.TemporaryDirectory() as folder:
                    root = Path(folder).resolve()
                    if existing:
                        history.resolve_targeted_samples(root, lambda: record())
                    path = root / 'public/inspection/work-check-bad.json'
                    path.parent.mkdir(parents=True)
                    path.write_bytes(content)
                    builder = Mock(return_value=record())
                    outcome = history.resolve_targeted_samples(root, builder)
                    self.assertEqual(outcome, history.sample_envelope('unavailable'))
                    self.assertNotIn('SECRET', json.dumps(outcome))
                    builder.assert_not_called()

    def test_malformed_private_record_is_not_overwritten(self) -> None:
        for content in (b'{', b' ' * (MAX_BYTES + 1), b'{"schema_version":1,"schema_version":1}'):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                path = journal(root)
                path.parent.mkdir(parents=True)
                path.write_bytes(content)
                builder = Mock(return_value=record())
                self.assertEqual(history.resolve_targeted_samples(root, builder)['status'], 'unavailable')
                self.assertEqual(path.read_bytes(), content)
                builder.assert_not_called()

    def test_history_count_and_total_byte_limits_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            publish(root, report())
            for field, limit in (('MAX_HISTORY_FILES', 0), ('MAX_HISTORY_BYTES', 1)):
                with patch.object(history, field, limit):
                    builder = Mock(return_value=record())
                    self.assertEqual(history.resolve_targeted_samples(root, builder)['status'], 'unavailable')
                    builder.assert_not_called()

    def test_atomic_equal_winner_replays_and_conflicting_winner_withholds(self) -> None:
        for equal in (True, False):
            with self.subTest(equal=equal), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                winner = record() if equal else record(151)

                def race(temporary, destination):
                    destination.write_text(render_targeted_samples_json(winner), encoding='utf-8')
                    raise FileExistsError

                with patch.object(history.os, 'link', side_effect=race):
                    outcome = history.resolve_targeted_samples(root, lambda: record())
                self.assertEqual(outcome['status'], 'replayed' if equal else 'unavailable')
                self.assertEqual(json.loads(journal(root).read_bytes()), winner)
                self.assertEqual(list(journal(root).parent.iterdir()), [journal(root)])

    def test_failed_reservation_is_not_released_and_builder_errors_are_separate(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with patch.object(history.os, 'link', side_effect=OSError('PRIVATE_FAILURE')):
                outcome = history.resolve_targeted_samples(root, lambda: record())
            self.assertEqual(outcome, history.sample_envelope('unavailable'))
            self.assertFalse(journal(root).exists())
            self.assertEqual(list(journal(root).parent.iterdir()), [])
            outcome = history.resolve_targeted_samples(root, Mock(side_effect=ValueError('PRIVATE_FAILURE')))
            self.assertEqual(outcome, history.sample_envelope('unavailable', reason='selection_error'))
            self.assertNotIn('PRIVATE_FAILURE', json.dumps(outcome))

    def test_symlink_public_file_and_ancestors_cannot_redirect_history_or_reservations(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder).resolve()
            outside = base / 'outside'
            outside.mkdir()
            for name in ('public', 'confidential'):
                root = base / name
                root.mkdir()
                try:
                    (root / name).symlink_to(outside, target_is_directory=True)
                except OSError:
                    self.skipTest('Windows symlink permission is unavailable.')
                builder = Mock(return_value=record())
                self.assertEqual(history.resolve_targeted_samples(root, builder)['status'], 'unavailable')
                builder.assert_not_called()
                self.assertEqual(list(outside.iterdir()), [])
            root = base / 'file'
            path = publish(root, report())
            linked = path.with_name('work-check-link.json')
            linked.symlink_to(path)
            self.assertEqual(history.resolve_targeted_samples(root, lambda: record())['status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
