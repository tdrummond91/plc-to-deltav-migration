"""Annotation publication counts from invented SFC evidence and frozen V1 reports."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from plc_workbench.sfc_summary import (
    CONSTANTS_V1, SfcSummaryError, build_sfc_summary, render_sfc_summary,
    validate_sfc_summary,
)
from test_sfc_summary import sfc_fixture


def annotation_summary(content: str):
    return build_sfc_summary(*sfc_fixture(
        '<Routine Name="PRIVATE_SEQUENCE" Type="SFC"><SFCContent>'
        f'{content}</SFCContent></Routine>'
    ))


def legacy_summary(summary):
    """Convert a no-child-text synthetic summary to the exact historical keys."""
    old = deepcopy(summary)
    old.update(CONSTANTS_V1)
    for key in ('annotations', 'annotation_endpoints', 'annotation_text'):
        old['counts'].pop(key)
    old['counts']['elements']['by_kind'].pop('text_box_text')
    old['counts']['issues']['by_code'].pop('annotation_endpoint_unresolved')
    return old


class SfcAnnotationSummaryTests(unittest.TestCase):
    def test_resolved_pairs_repetition_and_annotation_text_remain_count_only(self) -> None:
        summary = annotation_summary(
            '<TextBox ID="1" Name="PRIVATE_BOX">PRIVATE_DIRECT<Text>PRIVATE_CHILD</Text></TextBox>'
            '<Step ID="2"><Action ID="3" Name="PRIVATE_ACTION"/></Step>'
            '<Attachment FromID="01" ToID="3"/><Attachment FromID="1" ToID="3"/>'
            '<DirectedLink FromID="2" ToID="2"/>'
        )
        counts = summary['counts']
        self.assertEqual(summary['schema_version'], 2)
        self.assertEqual(counts['annotations'], {
            'total': 2, 'by_status': {'resolved': 2, 'unresolved': 0},
            'distinct_text_boxes': 1, 'distinct_targets': 1,
        })
        self.assertEqual(counts['annotation_endpoints']['by_status']['resolved'], 4)
        self.assertEqual(counts['links']['by_status']['resolved'], 1)
        self.assertEqual(counts['annotation_text'], {
            'text_boxes': 1, 'by_shape': {'empty': 0, 'direct_only': 0, 'child_only': 0, 'mixed': 1},
            'child_elements': 1, 'total_characters': len('PRIVATE_DIRECTPRIVATE_CHILD'),
        })
        rendered = render_sfc_summary(summary)
        self.assertNotIn('PRIVATE', rendered)
        self.assertNotIn('element_id', rendered)
        self.assertEqual(summary['status'], 'complete')

    def test_endpoint_failures_and_distinct_counts_require_fully_resolved_pairs(self) -> None:
        summary = annotation_summary(
            '<TextBox ID="1"/><Step ID="2"/><Step ID="3"/><Stop ID="03"/>'
            '<Attachment ToID="2"/><Attachment FromID="-1" ToID="2"/>'
            '<Attachment FromID="404" ToID="2"/><Attachment FromID="3" ToID="2"/>'
            '<Attachment FromID="2" ToID="1"/>'
        )
        counts = summary['counts']
        self.assertEqual(counts['annotations'], {
            'total': 5, 'by_status': {'resolved': 0, 'unresolved': 5},
            'distinct_text_boxes': 0, 'distinct_targets': 0,
        })
        self.assertEqual(counts['annotation_endpoints']['by_status'], {
            'resolved': 4, 'missing_attribute': 1, 'invalid_id': 1,
            'missing_target': 1, 'ambiguous_target': 1, 'unsupported_kind': 2,
        })
        self.assertEqual(counts['issues']['by_code']['annotation_endpoint_unresolved'], 6)
        validate_sfc_summary(summary)
        altered = deepcopy(summary)
        altered['counts']['annotations']['distinct_targets'] = 1
        with self.assertRaises(SfcSummaryError):
            validate_sfc_summary(altered)

    def test_closed_partitions_distinct_resource_and_impossible_target_counts(self) -> None:
        summary = annotation_summary('<TextBox ID="1"/><Step ID="2"/>'
                                     '<Attachment FromID="1" ToID="2"/>')
        mutations = [
            lambda s: s['counts']['annotations'].update(total=True),
            lambda s: s['counts']['annotations'].update(distinct_text_boxes=2),
            lambda s: s['counts']['annotations'].update(distinct_targets=0),
            lambda s: s['counts']['annotation_endpoints']['by_status'].update(resolved=1),
            lambda s: s['counts']['annotation_endpoints']['by_status'].update(PRIVATE_FIELD=0),
            lambda s: s['counts']['issues']['by_code'].update(annotation_endpoint_unresolved=1),
        ]
        for mutation in mutations:
            altered = deepcopy(summary)
            mutation(altered)
            with self.subTest(mutation=mutation), self.assertRaises(SfcSummaryError):
                validate_sfc_summary(altered)
        with patch('plc_workbench.sfc_summary.MAX_SFC_ANNOTATIONS', 0), self.assertRaises(SfcSummaryError):
            validate_sfc_summary(summary)
        # Duplicate ID members cannot be claimed as distinct resolved endpoints.
        altered = deepcopy(summary)
        altered['counts']['blocks'].update(duplicate_groups=1, duplicate_members=2)
        altered['counts']['issues']['by_code']['block_id_duplicate'] = 2
        altered['counts']['issues']['total'] = 2
        altered['status'] = 'partial'
        with self.assertRaises(SfcSummaryError):
            validate_sfc_summary(altered)

    def test_shape_profiles_include_empty_children_and_whitespace_character_evidence(self) -> None:
        summary = annotation_summary(
            '<TextBox ID="1"/>'
            '<TextBox ID="2">PRIVATE_DIRECT</TextBox>'
            '<TextBox ID="3"><Text/></TextBox>'
            '<TextBox ID="4">X<Text>Y</Text><Text> </Text></TextBox>'
            '<TextBox ID="5">   </TextBox>'
        )
        text = summary['counts']['annotation_text']
        self.assertEqual(text['by_shape'], {'empty': 2, 'direct_only': 1, 'child_only': 1, 'mixed': 1})
        self.assertEqual(text['child_elements'], 3)
        self.assertEqual(text['total_characters'], len('PRIVATE_DIRECTXY    '))
        for field, value in (('child_elements', 0), ('total_characters', True), ('text_boxes', 0)):
            altered = deepcopy(summary)
            altered['counts']['annotation_text'][field] = value
            with self.subTest(field=field), self.assertRaises(SfcSummaryError):
                validate_sfc_summary(altered)
        with patch('plc_workbench.sfc_summary.MAX_SFC_EVIDENCE_CHARS', 1), self.assertRaises(SfcSummaryError):
            validate_sfc_summary(summary)

    def test_historical_report_bytes_validate_and_version_hybrids_are_rejected(self) -> None:
        report_path = (Path(__file__).resolve().parents[2] / 'public' / 'inspection'
                       / 'work-check-20261015T015742Z-873f283d.json')
        before = report_path.read_bytes()
        report = json.loads(before)
        old = report['analysis']['sfc_structure_summary']
        self.assertEqual(old['schema_version'], 1)
        validate_sfc_summary(old)
        self.assertEqual(json.loads(render_sfc_summary(old)), old)
        self.assertEqual(report_path.read_bytes(), before)
        current = annotation_summary('')
        hybrids = [deepcopy(old), deepcopy(current), deepcopy(old), deepcopy(current)]
        hybrids[0].update(schema_version=2)
        hybrids[1].update(schema_version=1)
        hybrids[2]['counts']['annotations'] = current['counts']['annotations']
        hybrids[3]['counts']['elements']['by_kind'].pop('text_box_text')
        for hybrid in hybrids:
            with self.subTest(version=hybrid['schema_version']), self.assertRaises(SfcSummaryError):
                validate_sfc_summary(hybrid)

    def test_historical_direct_text_issue_eligibility_is_frozen(self) -> None:
        current = annotation_summary('<TextBox ID="1">PRIVATE_DIRECT</TextBox>')
        old = legacy_summary(current)
        for candidate in (old, current):
            candidate['status'] = 'partial'
            candidate['counts']['issues']['total'] = 2
            candidate['counts']['issues']['by_code']['unexpected_direct_text'] = 2
        # V1 allowed unexpected text on both the content and TextBox. In V2,
        # TextBox text is opaque annotation evidence; only the content is eligible.
        validate_sfc_summary(old)
        with self.assertRaises(SfcSummaryError):
            validate_sfc_summary(current)
        old['counts']['issues']['total'] = 3
        old['counts']['issues']['by_code']['unexpected_direct_text'] = 3
        with self.assertRaises(SfcSummaryError):
            validate_sfc_summary(old)


if __name__ == '__main__':
    unittest.main()
