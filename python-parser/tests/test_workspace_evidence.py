"""Diagnostics expose fixed reasons and measurements, never source text."""
import json
import unittest

from plc_workbench.workspace_evidence import diagnostic, evidence_notice


class WorkspaceEvidenceTests(unittest.TestCase):
    def test_capacity_notice_identifies_stage_and_measurement(self) -> None:
        result = diagnostic('field_io', 'index_bytes_limit', 100, 99)
        self.assertEqual(result, {'stage': 'field_io', 'reason': 'index_bytes_limit',
                                  'actual': 100, 'limit': 99})
        text = evidence_notice(result)
        self.assertIn('[field_io/index_bytes_limit]', text)
        self.assertIn('Measured 100; limit 99.', text)
        self.assertIn('capacity fix', text)

    def test_unknown_identifiers_extra_fields_and_noninteger_metrics_do_not_escape(self) -> None:
        private = 'PRIVATE_SOURCE_PATH_TAG_AND_DESCRIPTION'
        safe = {'stage': 'evidence', 'reason': 'invalid_evidence'}
        for stage, code in ((private, 'index_bytes_limit'), ('field_io', private),
                            ([], 'invalid_evidence'), ('source', {})):
            with self.subTest(stage=stage, code=code):
                self.assertEqual(diagnostic(stage, code, 12, 1), safe)
                self.assertNotIn(private, evidence_notice({'stage': stage, 'reason': code}))
        for value in (private, True, -1, 1.0, 2 ** 64, {'private': private}):
            with self.subTest(value=value):
                result = diagnostic('source', 'source_bytes_limit', value, value)
                self.assertEqual(set(result), {'stage', 'reason'})
        result = diagnostic('access', 'artifact_unavailable')
        result.update(exception=private, traceback=private, path=private)
        self.assertNotIn(private, evidence_notice(result))
        self.assertIn('[access/artifact_unavailable]', evidence_notice(result))
        self.assertNotIn(private, json.dumps(diagnostic(private, private)))

    def test_all_shared_loader_stages_can_keep_a_fixed_reason(self) -> None:
        for stage in ('source', 'inventory', 'references', 'calculations', 'access',
                      'tag_data', 'variable_index', 'field_io', 'field_signals', 'io_annotations'):
            with self.subTest(stage=stage):
                result = diagnostic(stage, 'projection_failed')
                self.assertEqual(result['stage'], stage)
                self.assertIn(f'[{stage}/projection_failed]', evidence_notice(result))


if __name__ == '__main__':
    unittest.main()
