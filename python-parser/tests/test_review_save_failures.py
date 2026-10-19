"""Versioned report budgets and source-free save failure categories."""
from __future__ import annotations

from copy import deepcopy
import errno
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import review, review_html, storage
from test_condition_workflow import captured, options, arguments
from test_relationship_workflow import options as previous_options


class ReviewSaveFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parts = captured()
        cls.current = review.build_review_data(*cls.parts[:4], **options(cls.parts))
        cls.previous = review.build_review_data(*cls.parts[:4], **previous_options(cls.parts))

    def test_condition_review_budget_adds_only_one_bounded_companion(self) -> None:
        self.assertEqual(review.MAX_REVIEW_V3_BYTES, 128 * 1024 * 1024)
        self.assertEqual(review.MAX_REVIEW_V9_BYTES, 160 * 1024 * 1024)
        self.assertEqual(review_html.MAX_REVIEW_V3_PAYLOAD_BYTES, 128 * 1024 * 1024)
        self.assertEqual(review_html.MAX_REVIEW_V3_HTML_BYTES, 160 * 1024 * 1024)
        self.assertEqual(review_html.MAX_REVIEW_V9_PAYLOAD_BYTES, 160 * 1024 * 1024)
        self.assertEqual(review_html.MAX_REVIEW_V9_HTML_BYTES, 192 * 1024 * 1024)

    def test_new_budget_does_not_change_earlier_versions(self) -> None:
        with patch.object(review, 'MAX_REVIEW_V3_BYTES', 1):
            review.render_review_json(self.current)
            with self.assertRaises(review.ReviewSizeLimitError):
                review.render_review_json(self.previous)
        with patch.object(review, 'MAX_REVIEW_V9_BYTES', 1):
            review.render_review_json(self.previous)
            with self.assertRaises(review.ReviewSizeLimitError):
                review.render_review_json(self.current)
        for suffix in ('PAYLOAD_BYTES', 'HTML_BYTES'):
            with patch.object(review_html, f'MAX_REVIEW_V3_{suffix}', 1):
                review_html.render_review_html(self.current)
                with self.assertRaises(review_html.ReviewHtmlSizeLimitError):
                    review_html.render_review_html(self.previous)
            with patch.object(review_html, f'MAX_REVIEW_V9_{suffix}', 1):
                review_html.render_review_html(self.previous)
                with self.assertRaises(review_html.ReviewHtmlSizeLimitError):
                    review_html.render_review_html(self.current)

    def test_exact_utf8_payload_and_final_html_boundaries(self) -> None:
        data = deepcopy(self.current)
        data['findings'][0:0] = [{'message': '\u00e9\u754c<&>'}]
        size = len(review.render_review_json(data).encode('utf-8'))
        with patch.object(review, 'MAX_REVIEW_V9_BYTES', size):
            review.render_review_json(data)
        with patch.object(review, 'MAX_REVIEW_V9_BYTES', size - 1):
            with self.assertRaises(review.ReviewSizeLimitError):
                review.render_review_json(data)
        page_size = len(review_html.render_review_html(data).encode('utf-8'))
        with patch.object(review_html, 'MAX_REVIEW_V9_PAYLOAD_BYTES', size), \
                patch.object(review_html, 'MAX_REVIEW_V9_HTML_BYTES', page_size):
            review_html.render_review_html(data)
        for name, limit in (('MAX_REVIEW_V9_PAYLOAD_BYTES', size - 1),
                            ('MAX_REVIEW_V9_HTML_BYTES', page_size - 1)):
            with patch.object(review_html, name, limit):
                with self.assertRaises(review_html.ReviewHtmlSizeLimitError):
                    review_html.render_review_html(data)

    def test_size_rejection_survives_canonical_build_validation_and_storage(self) -> None:
        with patch.object(review, 'MAX_REVIEW_V9_BYTES', 1):
            with self.assertRaises(review.ReviewSizeLimitError):
                review.build_review_data(*self.parts[:4], **options(self.parts))
            with self.assertRaises(review.ReviewSizeLimitError):
                review.validate_review_data(*self.parts[:4], self.current, **options(self.parts))
        for target in ('review.MAX_REVIEW_V9_BYTES', 'review_html.MAX_REVIEW_V9_PAYLOAD_BYTES',
                       'review_html.MAX_REVIEW_V9_HTML_BYTES'):
            with tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'unallocated'
                with patch(f'plc_workbench.{target}', 1), self.assertRaises(storage.StorageError) as caught:
                    storage.save_run(destination, *self.parts[:2], **arguments(self.parts))
                self.assertEqual(caught.exception.code, 'review_size_limit')
                self.assertFalse(destination.exists())

    def test_authentication_and_asset_failure_are_distinct_and_allocate_nothing(self) -> None:
        cases = ((review, 'build_review_data', review.ReviewError('PRIVATE_AUTH'), 'review_validation_error'),
                 (review_html, 'render_review_html', review_html.ReviewHtmlError('PRIVATE_RENDER'), 'review_render_error'))
        for module, name, error, code in cases:
            with tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'unallocated'
                with patch.object(module, name, side_effect=error), self.assertRaises(storage.StorageError) as caught:
                    storage.save_run(destination, *self.parts[:2], **arguments(self.parts))
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn('PRIVATE', str(caught.exception))
                self.assertFalse(destination.exists())

    def test_filesystem_failure_never_finalizes_and_does_not_echo_os_text(self) -> None:
        for error in (OSError(errno.ENOSPC, 'PRIVATE_DISK'), PermissionError('PRIVATE_ACCESS'),
                      RuntimeError('PRIVATE_OTHER')):
            with tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'runs'
                with patch.object(storage, '_write_artifact', side_effect=error), self.assertRaises(storage.StorageError) as caught:
                    storage.save_run(destination, *self.parts[:2], **arguments(self.parts))
                self.assertEqual(caught.exception.code, 'save_io_error' if isinstance(error, OSError) else 'save_error')
                self.assertNotIn('PRIVATE', str(caught.exception))
                self.assertFalse(list(destination.glob('*/manifest.json')))

    def test_workspace_rejection_is_a_fixed_code(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with patch.object(storage, '_checkout_root', return_value=root):
                with self.assertRaises(storage.StorageError) as caught:
                    storage.save_run(root / 'public', *self.parts[:2], **arguments(self.parts))
            self.assertEqual(caught.exception.code, 'save_workspace_error')
            self.assertFalse((root / 'public').exists())


if __name__ == '__main__':
    unittest.main()
