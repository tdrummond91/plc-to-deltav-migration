"""Closed file-operation counts reject publication drift and source leakage."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest

from plc_workbench.file_operation_summary import (FileOperationSummaryError,
    build_file_operation_summary, render_file_operation_summary, validate_file_operation_summary)
from test_file_operations import capture


class FileOperationSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.args = capture()
        cls.summary = build_file_operation_summary(*cls.args)

    def test_closed_roundtrip_has_no_source_values(self) -> None:
        rendered = render_file_operation_summary(self.summary)
        self.assertEqual(json.loads(rendered), self.summary)
        self.assertNotIn('A[R.POS]', rendered)
        self.assertNotIn('raw_text', rendered)
        self.assertLess(len(rendered.encode()), 8192)
        self.assertEqual(self.summary['coverage']['source_selected_operands'], 24)

    def test_arities_differ_for_malformed_source_without_inventing_slots(self) -> None:
        args = capture(('COP(A,B)AVE()FAL(R,?,?,ALL,D,1)SQO(A,1,D,R,?,?);',))
        summary = build_file_operation_summary(*args)
        validate_file_operation_summary(summary)
        self.assertEqual(summary['coverage']['signatures']['argument_count_mismatch'], 2)

    def test_mutated_closed_counts_and_bool_are_rejected(self) -> None:
        mutations = [('occurrences_total', 999), ('source_selected_operands', 23),
            ('newly_classified_slots', 17), ('pseudo_operands_total', 5),
            ('expression_references_total', 0), ('controls_with_data', 99), ('slots_total', True)]
        for key, value in mutations:
            with self.subTest(key=key):
                summary = deepcopy(self.summary)
                summary['coverage'][key] = value
                with self.assertRaises(FileOperationSummaryError):
                    validate_file_operation_summary(summary)

    def test_extra_fields_revision_and_status_are_rejected(self) -> None:
        for update in ({'invented_tag': 'PrivateSource'}, {'schema_version': True}, {'status': 'partial'},
                       {'tool_revision': {'commit': 'SECRET', 'worktree': 'clean'}}):
            with self.subTest(update=update):
                summary = {**deepcopy(self.summary), **update}
                with self.assertRaises(FileOperationSummaryError):
                    validate_file_operation_summary(summary)

    def test_valid_revision_and_nested_count_keys(self) -> None:
        summary = build_file_operation_summary(*self.args, revision={'commit': 'a'*40, 'worktree': 'clean'})
        self.assertEqual(summary['tool_revision']['commit'], 'a'*40)
        summary['coverage']['occurrences_by_opcode']['PRIVATE'] = 0
        with self.assertRaises(FileOperationSummaryError):
            validate_file_operation_summary(summary)

    def test_recognized_signatures_reconcile_exact_role_and_pseudo_counts(self) -> None:
        for field, changed in (('slots_by_role', {'read': 0, 'write': 0, 'unknown': 7}),
                               ('pseudo_operands_total', 4), ('newly_classified_instructions', 2)):
            with self.subTest(field=field):
                summary = deepcopy(self.summary)
                if isinstance(changed, dict):
                    summary['coverage'][field].update(changed)
                else:
                    summary['coverage'][field] = changed
                with self.assertRaises(FileOperationSummaryError):
                    validate_file_operation_summary(summary)


if __name__ == '__main__':
    unittest.main()
